"""Web UI サーバー."""

from __future__ import annotations

from datetime import datetime, timedelta
from importlib.resources import files
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse

from activity_logger.config import AppConfig
from activity_logger.storage.database import Database

JST = ZoneInfo("Asia/Tokyo")

app = FastAPI(title="Activity Logger")

_db: Database | None = None
_config: AppConfig | None = None


def _init() -> tuple[Database, AppConfig]:
    global _db, _config
    if _db is None:
        _config = AppConfig.load()
        _db = Database(_config.resolve_db_path())
    return _db, _config  # type: ignore[return-value]


def _resolve_range(
    date_range: str,
) -> tuple[datetime | None, datetime | None]:
    """日付レンジ名を (since, until) に変換する."""
    now = datetime.now(JST)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    match date_range:
        case "today":
            return today, None
        case "this_week":
            return today - timedelta(days=now.weekday()), None
        case "this_month":
            return today.replace(day=1), None
        case "all":
            return None, None
        case _:
            return today, None


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    """フロントエンド HTML を返す."""
    html_path = files("activity_logger.web") / "static" / "index.html"
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


@app.get("/api/sessions")
def get_sessions(
    date_range: str = Query(default="today"),
    min_duration: int = Query(default=0),
    search: str = Query(default=""),
) -> dict:
    """セッション一覧 + サマリを返す."""
    db, config = _init()

    threshold = min_duration if min_duration > 0 else config.session.min_duration_sec
    since, until = _resolve_range(date_range)
    excluded = config.filter.excluded_executables or None

    sessions = db.query_sessions(
        min_duration=threshold,
        executable=search or None,
        since=since,
        until=until,
        excluded_executables=excluded,
        limit=2000,
    )

    rows = [
        {
            "id": s.id,
            "executable": s.executable,
            "window_title": s.window_title,
            "started_at": s.started_at.isoformat(),
            "ended_at": (s.ended_at or datetime.now(JST)).isoformat(),
            "active_seconds": s.active_seconds,
            "idle_seconds": s.idle_seconds,
            "pid": s.pid,
        }
        for s in sessions
    ]

    # exe 別サマリ
    agg: dict[str, dict] = {}
    for s in sessions:
        if s.executable not in agg:
            agg[s.executable] = {
                "executable": s.executable,
                "total_active": 0.0,
                "total_idle": 0.0,
                "session_count": 0,
            }
        agg[s.executable]["total_active"] += s.active_seconds
        agg[s.executable]["total_idle"] += s.idle_seconds
        agg[s.executable]["session_count"] += 1

    summary = sorted(agg.values(), key=lambda x: x["total_active"], reverse=True)

    return {"sessions": rows, "summary": summary}


def main() -> None:
    """エントリーポイント: Web UI を起動する."""
    import uvicorn

    print("Activity Logger Web UI: http://127.0.0.1:8080")
    uvicorn.run(app, host="127.0.0.1", port=8080, log_level="info")
