"""閾値フィルタ・集計ロジック."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from activity_logger.storage.database import Database, SessionRecord


@dataclass
class ExeSummary:
    """実行ファイルごとの集計."""

    executable: str
    total_active_seconds: float
    total_idle_seconds: float
    session_count: int


class SessionFilter:
    """セッション検索・集計を行う."""

    def __init__(self, db: Database) -> None:
        self._db = db

    def query(
        self,
        *,
        min_duration_sec: float = 600,
        date_range: str = "today",
        executable: str | None = None,
        excluded_executables: list[str] | None = None,
    ) -> list[SessionRecord]:
        """フィルタ条件を指定してセッションを取得する."""
        since, until = _resolve_date_range(date_range)
        return self._db.query_sessions(
            min_duration=min_duration_sec,
            executable=executable,
            since=since,
            until=until,
            excluded_executables=excluded_executables,
        )

    def summarize_by_exe(
        self,
        sessions: list[SessionRecord],
    ) -> list[ExeSummary]:
        """セッション一覧を実行ファイルごとに集計する."""
        agg: dict[str, ExeSummary] = {}
        for s in sessions:
            if s.executable not in agg:
                agg[s.executable] = ExeSummary(
                    executable=s.executable,
                    total_active_seconds=0,
                    total_idle_seconds=0,
                    session_count=0,
                )
            entry = agg[s.executable]
            entry.total_active_seconds += s.active_seconds
            entry.total_idle_seconds += s.idle_seconds
            entry.session_count += 1
        return sorted(agg.values(), key=lambda e: e.total_active_seconds, reverse=True)


def _resolve_date_range(name: str) -> tuple[datetime | None, datetime | None]:
    """日付レンジ名を (since, until) に変換する."""
    now = datetime.now(UTC)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    match name:
        case "today":
            return today_start, None
        case "this_week":
            week_start = today_start - timedelta(days=now.weekday())
            return week_start, None
        case "this_month":
            month_start = today_start.replace(day=1)
            return month_start, None
        case "all":
            return None, None
        case _:
            return today_start, None
