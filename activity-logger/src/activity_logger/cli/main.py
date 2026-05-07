"""CLI エントリーポイント."""

from __future__ import annotations

import sys


def app() -> None:
    """TUI を起動する．

    サブコマンド "collect" が渡された場合はコレクターを起動する．
    """
    if len(sys.argv) > 1 and sys.argv[1] == "collect":
        _run_collector()
    else:
        _run_tui()


def _run_tui() -> None:
    from activity_logger.config import AppConfig
    from activity_logger.tui.app import ActivityLoggerApp

    config = AppConfig.load()
    ActivityLoggerApp(config).run()


def _run_collector() -> None:
    from activity_logger.collector.main import run

    run()
