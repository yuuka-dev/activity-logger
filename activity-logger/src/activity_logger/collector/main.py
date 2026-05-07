"""コレクター常駐デーモン."""

from __future__ import annotations

import logging
import signal
import time
from datetime import UTC, datetime

from activity_logger.collector.poller import get_foreground_window_info, get_idle_seconds
from activity_logger.collector.session import Session
from activity_logger.config import AppConfig
from activity_logger.storage.database import Database, SessionRecord

logger = logging.getLogger(__name__)


class Collector:
    """前面ウィンドウを定期ポーリングしてセッションを記録する."""

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._db = Database(config.resolve_db_path())
        self._current: Session | None = None
        self._running = False

    def _is_excluded(self, exe: str) -> bool:
        return exe in self._config.filter.excluded_executables

    def _flush_session(self, session: Session) -> None:
        """セッションを DB に書き出す."""
        session.close()
        rec = SessionRecord(
            id=session.db_id,
            executable=session.executable,
            window_title=session.window_title,
            started_at=session.started_at,
            ended_at=datetime.now(UTC),
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

        if info is None or self._is_excluded(info.executable):
            # ウィンドウなし or 除外アプリ → 現セッションをアイドル扱い
            if self._current:
                self._current.tick(is_idle=True)
            return

        # アプリ切替を検出
        if self._current and (
            self._current.executable != info.executable or self._current.pid != info.pid
        ):
            self._flush_session(self._current)
            self._current = None

        if self._current is None:
            self._current = Session(
                executable=info.executable,
                window_title=info.window_title,
                pid=info.pid,
            )
        else:
            # ウィンドウタイトルは随時更新（タブ切替等）
            self._current.window_title = info.window_title
            self._current.tick(is_idle=is_idle)

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
            if self._current:
                self._flush_session(self._current)
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
