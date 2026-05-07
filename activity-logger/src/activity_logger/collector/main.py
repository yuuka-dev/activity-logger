"""コレクター常駐デーモン."""

from __future__ import annotations

import logging
import signal
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from activity_logger.collector.poller import get_foreground_window_info, get_idle_seconds
from activity_logger.collector.session import Session, SessionState
from activity_logger.config import AppConfig
from activity_logger.storage.database import Database, SessionRecord

JST = ZoneInfo("Asia/Tokyo")
logger = logging.getLogger(__name__)


class Collector:
    """前面ウィンドウを定期ポーリングしてセッションを記録する．

    セッションはアプリ（exe:pid）ごとに保持し，
    非前面が閾値秒数を超えたときに初めて DB に書き出して閉じる．
    """

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._db = Database(config.resolve_db_path())
        self._sessions: dict[str, Session] = {}
        self._prev_fg_key: str | None = None
        self._running = False

    @staticmethod
    def _key(exe: str, pid: int) -> str:
        return f"{exe}:{pid}"

    def _is_excluded(self, exe: str) -> bool:
        return exe in self._config.filter.excluded_executables

    def _flush_session(self, session: Session) -> None:
        """セッションを DB に書き出す."""
        now = datetime.now(JST)
        session.close(now=now)
        rec = SessionRecord(
            id=session.db_id,
            executable=session.executable,
            window_title=session.window_title,
            started_at=session.started_at,
            ended_at=now,
            active_seconds=session.active_seconds,
            idle_seconds=session.idle_seconds,
            pid=session.pid,
        )
        if session.db_id is None:
            session.db_id = self._db.insert_session(rec)
        else:
            rec.id = session.db_id
            self._db.update_session(rec)

    def _poll(self) -> None:
        """1 回分のポーリングを実行する."""
        info = get_foreground_window_info()
        idle_sec = get_idle_seconds()
        is_idle = idle_sec >= self._config.idle.threshold_sec
        now = datetime.now(JST)

        fg_key: str | None = None

        if info and not self._is_excluded(info.executable):
            fg_key = self._key(info.executable, info.pid)

            # 新規 or 復帰
            if fg_key not in self._sessions:
                self._sessions[fg_key] = Session(
                    executable=info.executable,
                    window_title=info.window_title,
                    pid=info.pid,
                )
            else:
                session = self._sessions[fg_key]
                # バックグラウンドから復帰 → 背景時間をスキップ
                if session.state == SessionState.BACKGROUND:
                    session.resume(now=now)

            session = self._sessions[fg_key]
            session.window_title = info.window_title
            session.tick(is_idle=is_idle, now=now)

        # 前面から離れたセッションを BACKGROUND にする
        if fg_key != self._prev_fg_key and self._prev_fg_key in self._sessions:
            prev = self._sessions[self._prev_fg_key]
            if prev.state != SessionState.CLOSED:
                prev.to_background(now=now)

        self._prev_fg_key = fg_key

        # 閾値超過のバックグラウンドセッションを閉じる
        threshold = self._config.idle.threshold_sec
        for key in list(self._sessions):
            if key == fg_key:
                continue
            session = self._sessions[key]
            if session.seconds_since_last_tick(now=now) >= threshold:
                self._flush_session(session)
                del self._sessions[key]

    def run(self) -> None:
        """メインループ．SIGINT / SIGTERM で停止する."""
        self._running = True
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        interval = self._config.collector.polling_interval_sec
        logger.info("コレクター開始 (間隔: %ds)", interval)
        try:
            while self._running:
                try:
                    self._poll()
                except Exception:
                    logger.exception("ポーリング中にエラー発生")
                time.sleep(interval)
        finally:
            for session in self._sessions.values():
                self._flush_session(session)
            self._db.close()
            logger.info("コレクター停止")

    def _signal_handler(self, signum: int, _frame: object) -> None:
        logger.info("シグナル %d を受信，停止します", signum)
        self._running = False


def run() -> None:
    """エントリーポイント: コレクターを起動する."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    config = AppConfig.load()
    Collector(config).run()
