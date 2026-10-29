"""In-process run queue: visible positions, per-run progress streams, cancellation and spend accounting.

There is no global lock: up to `max_concurrent_runs` lectures are described at once and everyone else sees their
place in the queue. Public runs may use all slots but one, so a judge's run always finds a free slot. Each run's
events are kept for a while so a reconnecting browser can replay them.

Every model call is charged to the day's spend when the run ends, however it ends, and a run that reaches its slot
after the day's budget is gone does not start. When Token Factory itself fails (credit, keys, every model in a
chain), live runs pause for a while and the app serves its recorded examples.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from .asr import SpeechRecognizer
from .config import Settings
from .ledger import Ledger
from .pipeline import Cancelled, PerceptionFailed, RunOptions, run_pipeline
from .store import Store
from .tf_client import AuthFailure, CreditExhausted, TokenFactory, TokenFactoryError

log = logging.getLogger(__name__)

PROVIDER_FAILURES_BEFORE_PAUSE = 3
FORGET_AFTER_SECONDS = 600  # keep a finished run's events this long for reconnecting browsers
# Intermediate media a finished run no longer needs: the audio track, segment clips, stills and check frames.
INTERMEDIATE = ("audio.wav", "s[0-9]*.mp4", "s[0-9]*_*.jpg", "check_*")


class OverBudget(Exception):
    pass


class RunQueue:
    def __init__(self, settings: Settings, tf: TokenFactory, asr: SpeechRecognizer, store: Store) -> None:
        self.settings, self.tf, self.asr, self.store = settings, tf, asr, store
        self._slots = asyncio.Semaphore(settings.max_concurrent_runs)
        self._public_slots = asyncio.Semaphore(max(1, settings.max_concurrent_runs - 1))
        self._waiting: list[str] = []
        self._lanes: dict[str, str] = {}  # queued or running run -> lane
        self._history: dict[str, list[dict[str, Any]]] = {}
        self._listeners: dict[str, set[asyncio.Queue]] = {}
        self._cancel: dict[str, asyncio.Event] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self._provider_failures = 0
        self.paused_until = 0.0  # every lane: credit or keys
        self.public_paused_until = 0.0  # public lane only: the models are failing, keep judges' slot usable
        self.pause_reason = ""

    # ---- state ---------------------------------------------------------------------------------------------------

    def paused_for(self, lane: str) -> bool:
        now = time.time()
        return now < self.paused_until or (lane != "judge" and now < self.public_paused_until)

    def pause(self, seconds: float, reason: str, *, public_only: bool = False) -> None:
        until = time.time() + seconds
        if public_only:
            self.public_paused_until = max(self.public_paused_until, until)
        else:
            self.paused_until = max(self.paused_until, until)
        self.pause_reason = reason
        log.warning(
            "live runs paused for %.0f s%s: %s", seconds, " (public lane)" if public_only else "", reason
        )

    def active(self, lane: str | None = None) -> int:
        """Runs queued or running, in one lane or in all."""
        return sum(1 for value in self._lanes.values() if lane is None or value == lane)

    def committed_usd(self, lane: str) -> float:
        """Spend already recorded today plus a reserve for every run of this lane still queued or running. The runs
        are counted in the store, where a run is registered before its upload is read, so concurrent requests see
        each other's reserve."""
        return self.store.spend_today(lane) + self.store.count_active(lane) * self.settings.run_reserve_usd

    def over_budget(self, lane: str, *, reserve_new: bool) -> bool:
        """`reserve_new`: may one more run join this lane (its own row not yet counted)? Otherwise: may a run that
        reached its slot start, given what has really been spent?"""
        cap = self.settings.judge_daily_usd if lane == "judge" else self.settings.public_daily_usd
        extra = self.settings.run_reserve_usd if reserve_new else 0.0
        today = self.committed_usd(lane) if reserve_new else self.store.spend_today(lane)
        return (
            today + extra > cap or self.store.spend_this_month() + extra > self.settings.monthly_ceiling_usd
        )

    def position(self, run_id: str) -> int:
        return self._waiting.index(run_id) + 1 if run_id in self._waiting else 0

    def knows(self, run_id: str) -> bool:
        return run_id in self._history

    # ---- events --------------------------------------------------------------------------------------------------

    def _publish(self, run_id: str, event: dict[str, Any]) -> None:
        event = {**event, "at": time.time()}
        history = self._history.setdefault(run_id, [])
        if event["type"] == "tick" and history and history[-1]["type"] == "tick":
            history[-1] = event  # a reconnecting browser needs only the latest count
        else:
            history.append(event)
        for queue in self._listeners.get(run_id, set()):
            queue.put_nowait(event)

    def _publish_positions(self) -> None:
        for run_id in self._waiting:
            self._publish(run_id, {"type": "queued", "position": self.position(run_id)})

    def _finish(self, run_id: str, status: str, error: str = "", detail: str = "") -> None:
        """Record how a run ended: `error` is shown to the visitor, `detail` only goes to the server log."""
        if detail:
            log.warning("run %s %s: %s", run_id, status, detail)
        self.store.update_run(run_id, status=status, finished=time.time(), error=error[:500])
        self._publish(run_id, {"type": "finished", "status": status, **({"error": error} if error else {})})

    def _forget(self, run_id: str) -> None:
        if not self._listeners.get(run_id):
            for table in (self._history, self._listeners, self._cancel):
                table.pop(run_id, None)

    # ---- runs ----------------------------------------------------------------------------------------------------

    def submit(self, run_id: str, video: Path, options: RunOptions, lane: str) -> None:
        self._cancel[run_id] = asyncio.Event()
        self._lanes[run_id] = lane
        self._waiting.append(run_id)
        self._publish(run_id, {"type": "queued", "position": self.position(run_id)})
        self._tasks[run_id] = asyncio.create_task(self._run(run_id, video, options, lane))

    def cancel(self, run_id: str) -> bool:
        event = self._cancel.get(run_id)
        if event is None:
            return False
        event.set()
        task = self._tasks.get(run_id)
        if task is not None:
            task.cancel()  # leaves the queue at once, or stops in-flight model calls
        return True

    def _provider_failed(self) -> None:
        self._provider_failures += 1
        if self._provider_failures >= PROVIDER_FAILURES_BEFORE_PAUSE:
            self._provider_failures = 0
            self.pause(600, "the models are not answering reliably", public_only=True)

    async def _run(self, run_id: str, video: Path, options: RunOptions, lane: str) -> None:
        workdir = self.store.run_dir(run_id)
        ledger = Ledger()
        started = False
        interrupted = (
            False  # stopped or timed out mid-run: a call cut off has no usage, so charge the reserve
        )
        try:
            async with contextlib.AsyncExitStack() as slots:
                if lane != "judge":
                    await slots.enter_async_context(self._public_slots)
                await slots.enter_async_context(self._slots)
                if run_id in self._waiting:
                    self._waiting.remove(run_id)
                self._publish_positions()
                if self._cancel[run_id].is_set():
                    raise Cancelled("before start")
                if self.paused_for(lane) or self.over_budget(lane, reserve_new=False):
                    raise OverBudget
                started = True
                self.store.update_run(run_id, status="running")
                self._publish(run_id, {"type": "running"})
                await asyncio.wait_for(
                    run_pipeline(
                        video,
                        workdir,
                        settings=self.settings,
                        tf=self.tf,
                        asr=self.asr,
                        options=options,
                        progress=lambda e: self._publish(run_id, e),
                        cancel=self._cancel[run_id],
                        ledger=ledger,
                    ),
                    self.settings.run_timeout_seconds,
                )
                self._provider_failures = 0
                self._finish(run_id, "done")
        except (Cancelled, asyncio.CancelledError):
            interrupted = started
            self._finish(run_id, "cancelled")
        except OverBudget:
            self._finish(
                run_id,
                "failed",
                "Live describing is paused for now: today's budget is used up or the models are busy. "
                "The recorded examples always work.",
            )
        except CreditExhausted as exc:
            self.pause(3600, "Token Factory credit is exhausted")
            self._finish(
                run_id,
                "failed",
                "Live describing is paused (model credit exhausted). Recorded examples still work.",
                f"credit_exhausted: {exc}",
            )
        except AuthFailure as exc:
            self.pause(900, "Token Factory rejected the API keys")
            self._finish(run_id, "failed", "Live describing is temporarily unavailable.", f"auth: {exc}")
        except TimeoutError:
            interrupted = started
            self._finish(
                run_id,
                "failed",
                "This video took too long to describe and was stopped. Please try a shorter clip.",
                "run timeout",
            )
        except (PerceptionFailed, TokenFactoryError) as exc:
            if isinstance(
                exc, TokenFactoryError
            ):  # a broken upload also fails perception; it is not the models
                self._provider_failed()
            self._finish(
                run_id,
                "failed",
                "The models could not finish this video right now. Please try again in a few minutes.",
                f"{type(exc).__name__}: {exc}",
            )
        except Exception as exc:
            log.exception("run %s failed", run_id)
            self._finish(
                run_id,
                "failed",
                "Something went wrong while describing this video. Please try again, or try another clip.",
                f"{type(exc).__name__}: {exc}",
            )
        finally:
            charge = (
                max(ledger.total_cost, self.settings.run_reserve_usd) if interrupted else ledger.total_cost
            )
            if charge:
                self.store.add_spend(lane, charge)
            if ledger.total_cost:
                self.store.update_run(run_id, cost_usd=round(ledger.total_cost, 6))
            if run_id in self._waiting:
                self._waiting.remove(run_id)
                self._publish_positions()
            self._tasks.pop(run_id, None)
            self._lanes.pop(run_id, None)
            for pattern in INTERMEDIATE:
                for path in workdir.glob(pattern):
                    path.unlink(missing_ok=True)
            with contextlib.suppress(RuntimeError):
                asyncio.get_running_loop().call_later(FORGET_AFTER_SECONDS, self._forget, run_id)

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
