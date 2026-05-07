"""Web UI サーバー（ManicTime 風タイムライン）."""

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


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    """フロントエンド HTML を返す."""
    html_path = files("activity_logger.web") / "static" / "index.html"
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


@app.get("/api/timeline")
def get_timeline(date: str = Query(default="")) -> dict:
    """指定日のタイムラインデータを返す."""
    db, config = _init()

    if not date:
        date = datetime.now(JST).strftime("%Y-%m-%d")

    day_start = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=JST)
    day_end = day_start + timedelta(days=1)

    sessions = db.query_sessions(
        min_duration=config.session.min_duration_sec,
        since=day_start,
        until=day_end,
        excluded_executables=config.filter.excluded_executables or None,
        limit=2000,
    )

    segments = [
        {
            "executable": s.executable,
            "window_title": s.window_title,
            "start": s.started_at.isoformat(),
            "end": (s.ended_at or datetime.now(JST)).isoformat(),
            "active_seconds": s.active_seconds,
            "idle_seconds": s.idle_seconds,
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

    return {"date": date, "segments": segments, "summary": summary}


def main() -> None:
    """エントリーポイント: Web UI を起動する."""
    import uvicorn

    print("Activity Logger Web UI: http://127.0.0.1:8080")
    uvicorn.run(app, host="127.0.0.1", port=8080, log_level="info")
