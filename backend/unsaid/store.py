"""Persistent state: runs, sessions and the spend ledger used for caps (SQLite on the shared filesystem)."""

from __future__ import annotations

import contextlib
import json
import sqlite3
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    session TEXT NOT NULL,
    lane TEXT NOT NULL,
    title TEXT NOT NULL,
    status TEXT NOT NULL,
    created REAL NOT NULL,
    finished REAL,
    cost_usd REAL DEFAULT 0,
    error TEXT DEFAULT '',
    ip TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS runs_session ON runs(session);
CREATE TABLE IF NOT EXISTS spend (
    day TEXT NOT NULL,
    lane TEXT NOT NULL,
    usd REAL NOT NULL,
    PRIMARY KEY (day, lane)
);
"""


MEDIA_SUFFIXES = {".mp4", ".mov", ".webm", ".m4v", ".mkv", ".wav", ".jpg", ".jpeg", ".png"}


def today() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")


class Store:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.runs_dir = data_dir / "runs"
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        # journal_mode=DELETE: WAL is unsafe on network filesystems.
        self._db = sqlite3.connect(data_dir / "unsaid.db", check_same_thread=False, isolation_level=None)
        self._db.execute("PRAGMA journal_mode=DELETE")
        self._db.executescript(SCHEMA)

    def _q(self, sql: str, args: tuple = ()) -> list[sqlite3.Row]:
        with self._lock:
            self._db.row_factory = sqlite3.Row
            return list(self._db.execute(sql, args))

    def create_run(self, run_id: str, session: str, lane: str, title: str, ip: str) -> None:
        self._q(
            "INSERT INTO runs (id, session, lane, title, status, created, ip) VALUES (?, ?, ?, ?, 'queued', ?, ?)",
            (run_id, session, lane, title, time.time(), ip),
        )

    def update_run(self, run_id: str, **fields: Any) -> None:
        if not fields:
            return
        cols = ", ".join(f"{k} = ?" for k in fields)
        self._q(f"UPDATE runs SET {cols} WHERE id = ?", (*fields.values(), run_id))

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        rows = self._q("SELECT * FROM runs WHERE id = ?", (run_id,))
        return dict(rows[0]) if rows else None

    def runs_for_session(self, session: str, limit: int = 20) -> list[dict[str, Any]]:
        rows = self._q("SELECT * FROM runs WHERE session = ? ORDER BY created DESC LIMIT ?", (session, limit))
        return [dict(r) for r in rows]

    def count_recent(self, *, session: str | None = None, ip: str | None = None, seconds: float) -> int:
        since = time.time() - seconds
        if session is not None:
            return self._q(
                "SELECT COUNT(*) AS n FROM runs WHERE session = ? AND created > ?", (session, since)
            )[0]["n"]
        return self._q("SELECT COUNT(*) AS n FROM runs WHERE ip = ? AND created > ?", (ip, since))[0]["n"]

    def add_spend(self, lane: str, usd: float) -> None:
        self._q(
            "INSERT INTO spend (day, lane, usd) VALUES (?, ?, ?) ON CONFLICT(day, lane) DO UPDATE SET usd = usd + ?",
            (today(), lane, usd, usd),
        )

    def spend_today(self, lane: str) -> float:
        rows = self._q("SELECT usd FROM spend WHERE day = ? AND lane = ?", (today(), lane))
        return rows[0]["usd"] if rows else 0.0

    def spend_this_month(self) -> float:
        rows = self._q("SELECT COALESCE(SUM(usd), 0) AS s FROM spend WHERE day LIKE ?", (today()[:7] + "%",))
        return rows[0]["s"]

    def fail_orphans(self) -> int:
        """Runs left queued or running by a previous process can never finish; say so instead of hanging."""
        with self._lock:
            cursor = self._db.execute(
                "UPDATE runs SET status = 'failed', error = 'interrupted by a server restart', finished = ? "
                "WHERE status IN ('queued', 'running')",
                (time.time(),),
            )
            return cursor.rowcount

    def run_dir(self, run_id: str) -> Path:
        return self.runs_dir / run_id

    def result(self, run_id: str) -> dict[str, Any] | None:
        path = self.run_dir(run_id) / "result.json"
        return json.loads(path.read_text()) if path.exists() else None

    def count_pending(self, *, session: str, ip: str) -> int:
        """Runs still queued or running for this browser or this address."""
        return self._q(
            "SELECT COUNT(*) AS n FROM runs WHERE status IN ('queued', 'running') AND (session = ? OR (ip != '' AND ip = ?))",
            (session, ip),
        )[0]["n"]

    def delete_run(self, run_id: str) -> None:
        self._q("DELETE FROM runs WHERE id = ?", (run_id,))

    def purge_media(self, older_than_seconds: float = 24 * 3600) -> int:
        """Delete live runs' media (the upload, its audio, clips and frames) after the retention period.

        Results and text tracks stay, so a result page still opens; its player says the video was deleted.
        """
        removed = 0
        cutoff = time.time() - older_than_seconds
        for run in self.runs_dir.glob("*/"):
            for path in run.iterdir():
                if path.suffix.lower() in MEDIA_SUFFIXES:
                    with contextlib.suppress(FileNotFoundError):
                        if path.stat().st_mtime < cutoff:
                            path.unlink()
                            removed += 1
        return removed
