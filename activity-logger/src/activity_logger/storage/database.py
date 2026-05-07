"""SQLite 永続化層."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class SessionRecord:
    """セッションレコード."""

    id: int | None
    executable: str
    window_title: str
    started_at: datetime
    ended_at: datetime | None
    active_seconds: float
    idle_seconds: float
    pid: int


_SCHEMA = """\
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    executable TEXT NOT NULL,
    window_title TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    active_seconds REAL NOT NULL DEFAULT 0,
    idle_seconds REAL NOT NULL DEFAULT 0,
    pid INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sessions_started ON sessions(started_at);
CREATE INDEX IF NOT EXISTS idx_sessions_exe ON sessions(executable);
"""


class Database:
    """SQLite データベースラッパー（WAL モード）."""

    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path))
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(_SCHEMA)

    def insert_session(self, rec: SessionRecord) -> int:
        """セッションを挿入し，自動採番された id を返す."""
        cur = self._conn.execute(
            """INSERT INTO sessions
               (executable, window_title, started_at, ended_at,
                active_seconds, idle_seconds, pid)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                rec.executable,
                rec.window_title,
                rec.started_at.isoformat(),
                rec.ended_at.isoformat() if rec.ended_at else None,
                rec.active_seconds,
                rec.idle_seconds,
                rec.pid,
            ),
        )
        self._conn.commit()
        return cur.lastrowid  # type: ignore[return-value]

    def update_session(self, rec: SessionRecord) -> None:
        """既存セッションを更新する."""
        self._conn.execute(
            """UPDATE sessions SET
               ended_at = ?, active_seconds = ?, idle_seconds = ?, window_title = ?
               WHERE id = ?""",
            (
                rec.ended_at.isoformat() if rec.ended_at else None,
                rec.active_seconds,
                rec.idle_seconds,
                rec.window_title,
                rec.id,
            ),
        )
        self._conn.commit()

    def query_sessions(
        self,
        *,
        min_duration: float = 0,
        executable: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        excluded_executables: list[str] | None = None,
        limit: int = 500,
    ) -> list[SessionRecord]:
        """条件を指定してセッションを検索する."""
        conditions = ["ended_at IS NOT NULL", "active_seconds >= ?"]
        params: list[object] = [min_duration]

        if executable:
            conditions.append("executable LIKE ?")
            params.append(f"%{executable}%")
        if since:
            conditions.append("started_at >= ?")
            params.append(since.isoformat())
        if until:
            conditions.append("started_at <= ?")
            params.append(until.isoformat())
        if excluded_executables:
            placeholders = ", ".join("?" for _ in excluded_executables)
            conditions.append(f"executable NOT IN ({placeholders})")
            params.extend(excluded_executables)

        where = " AND ".join(conditions)
        rows = self._conn.execute(
            f"""SELECT id, executable, window_title, started_at, ended_at,
                       active_seconds, idle_seconds, pid
               FROM sessions WHERE {where}
               ORDER BY started_at DESC LIMIT ?""",
            [*params, limit],
        ).fetchall()

        return [
            SessionRecord(
                id=r[0],
                executable=r[1],
                window_title=r[2],
                started_at=datetime.fromisoformat(r[3]),
                ended_at=datetime.fromisoformat(r[4]) if r[4] else None,
                active_seconds=r[5],
                idle_seconds=r[6],
                pid=r[7],
            )
            for r in rows
        ]

    def get_executables(self) -> list[str]:
        """記録済みの実行ファイル名一覧を返す."""
        rows = self._conn.execute(
            "SELECT DISTINCT executable FROM sessions ORDER BY executable"
        ).fetchall()
        return [r[0] for r in rows]

    def close(self) -> None:
        self._conn.close()
