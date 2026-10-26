"""In-process run queue: visible positions, per-run progress streams, cancellation and spend accounting.

There is no global lock: up to `max_concurrent_runs` lectures are described at once and everyone else sees their
place in the queue. Each run's events are kept so a reconnecting browser can replay them.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from .asr import SpeechRecognizer
from .config import Settings
from .pipeline import Cancelled, PerceptionFailed, RunOptions, run_pipeline
from .store import Store
from .tf_client import AuthFailure, CreditExhausted, TokenFactory


class RunQueue:
    def __init__(self, settings: Settings, tf: TokenFactory, asr: SpeechRecognizer, store: Store) -> None:
        self.settings, self.tf, self.asr, self.store = settings, tf, asr, store
        self._slots = asyncio.Semaphore(settings.max_concurrent_runs)
        self._waiting: list[str] = []
        self._history: dict[str, list[dict[str, Any]]] = {}
        self._listeners: dict[str, set[asyncio.Queue]] = {}
        self._cancel: dict[str, asyncio.Event] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self.credit_exhausted = False

    def position(self, run_id: str) -> int:
        return self._waiting.index(run_id) + 1 if run_id in self._waiting else 0

    def _publish(self, run_id: str, event: dict[str, Any]) -> None:
        event = {**event, "at": time.time()}
        self._history.setdefault(run_id, []).append(event)
        for queue in self._listeners.get(run_id, set()):
            queue.put_nowait(event)

    def _publish_positions(self) -> None:
        for run_id in self._waiting:
            self._publish(run_id, {"type": "queued", "position": self.position(run_id)})

    def submit(self, run_id: str, video: Path, options: RunOptions, lane: str) -> None:
        self._cancel[run_id] = asyncio.Event()
        self._waiting.append(run_id)
        self._publish(run_id, {"type": "queued", "position": self.position(run_id)})
        self._tasks[run_id] = asyncio.create_task(self._run(run_id, video, options, lane))

    def cancel(self, run_id: str) -> bool:
        event = self._cancel.get(run_id)
        if event is None:
            return False
        event.set()
        task = self._tasks.get(run_id)
        if run_id in self._waiting or task is None:
            return True
        task.cancel()  # stop in-flight model calls too
        return True

    async def _run(self, run_id: str, video: Path, options: RunOptions, lane: str) -> None:
        workdir = self.store.run_dir(run_id)
        try:
            async with self._slots:
                if run_id in self._waiting:
                    self._waiting.remove(run_id)
                self._publish_positions()
                if self._cancel[run_id].is_set():
                    raise Cancelled("before start")
                self.store.update_run(run_id, status="running")
                self._publish(run_id, {"type": "running"})
                result = await run_pipeline(
                    video,
                    workdir,
                    settings=self.settings,
                    tf=self.tf,
                    asr=self.asr,
                    options=options,
                    progress=lambda e: self._publish(run_id, e),
                    cancel=self._cancel[run_id],
                )
                cost = result["ledger"]["summary"]["total_usd"]
                self.store.update_run(run_id, status="done", finished=time.time(), cost_usd=cost)
                self.store.add_spend(lane, cost)
                self._publish(run_id, {"type": "finished", "status": "done"})
        except (Cancelled, asyncio.CancelledError):
            if run_id in self._waiting:
                self._waiting.remove(run_id)
                self._publish_positions()
            self.store.update_run(run_id, status="cancelled", finished=time.time())
            self._publish(run_id, {"type": "finished", "status": "cancelled"})
        except CreditExhausted:
            self.credit_exhausted = True
            self.store.update_run(run_id, status="failed", finished=time.time(), error="credit_exhausted")
            self._publish(
                run_id,
                {
                    "type": "finished",
                    "status": "failed",
                    "error": "Live describing is paused (model credit exhausted). Recorded examples still work.",
                },
            )
        except PerceptionFailed as exc:
            self.store.update_run(run_id, status="failed", finished=time.time(), error=str(exc))
            self._publish(
                run_id,
                {
                    "type": "finished",
                    "status": "failed",
                    "error": "The video model could not read most of this video right now. Please try again in a few minutes.",
                },
            )
        except AuthFailure:
            self.store.update_run(run_id, status="failed", finished=time.time(), error="auth")
            self._publish(
                run_id,
                {
                    "type": "finished",
                    "status": "failed",
                    "error": "Live describing is temporarily unavailable.",
                },
            )
        except Exception as exc:
            self.store.update_run(
                run_id, status="failed", finished=time.time(), error=f"{type(exc).__name__}: {exc}"[:500]
            )
            self._publish(
                run_id,
                {"type": "finished", "status": "failed", "error": f"{type(exc).__name__}: {exc}"[:300]},
            )
        finally:
            self._tasks.pop(run_id, None)

    async def events(self, run_id: str) -> AsyncIterator[dict[str, Any]]:
        queue: asyncio.Queue = asyncio.Queue()
        for event in self._history.get(run_id, []):
            queue.put_nowait(event)
        self._listeners.setdefault(run_id, set()).add(queue)
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=10)
                except TimeoutError:
                    yield {"type": "heartbeat"}
                    continue
                yield event
                if event.get("type") == "finished":
                    return
        finally:
            self._listeners[run_id].discard(queue)
