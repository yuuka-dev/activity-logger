"""CLI エントリーポイント."""

from __future__ import annotations

import sys


def app() -> None:
    """メインエントリーポイント．

    サブコマンド:
        collect  コレクターを起動
        web      Web UI を起動
        (なし)   TUI を起動
    """
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    match cmd:
        case "collect":
            _run_collector()
        case "web":
            _run_web()
        case _:
            _run_tui()


def _run_tui() -> None:
    from activity_logger.config import AppConfig
    from activity_logger.tui.app import ActivityLoggerApp

    config = AppConfig.load()
    ActivityLoggerApp(config).run()


def _run_collector() -> None:
    from activity_logger.collector.main import run

    run()


def _run_web() -> None:
    from activity_logger.web.server import main as web_main

    web_main()
