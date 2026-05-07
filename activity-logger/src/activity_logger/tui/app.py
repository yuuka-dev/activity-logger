"""Textual TUI アプリケーション."""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import DataTable, Footer, Header, Input, Select, Static

from activity_logger.config import AppConfig
from activity_logger.filter.query import SessionFilter
from activity_logger.storage.database import Database, SessionRecord


class ActivityLoggerApp(App):
    """アクティビティログ閲覧 TUI."""

    TITLE = "Activity Logger"

    CSS = """
    #filter-bar {
        height: 3;
        dock: top;
        layout: horizontal;
        padding: 0 1;
    }
    #filter-bar Input {
        width: 1fr;
    }
    #filter-bar Select {
        width: 20;
    }
    #main-area {
        layout: horizontal;
    }
    #session-table {
        width: 2fr;
    }
    #detail-panel {
        width: 1fr;
        padding: 1;
        border-left: solid $accent;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "終了"),
        Binding("s", "open_settings", "設定"),
        Binding("r", "refresh_data", "更新"),
    ]

    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self._config = config
        self._db = Database(config.resolve_db_path())
        self._filter = SessionFilter(self._db)
        self._sessions: list[SessionRecord] = []

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="filter-bar"):
            yield Input(placeholder="exe名で検索...", id="search-input")
            yield Select(
                [
                    ("今日", "today"),
                    ("今週", "this_week"),
                    ("今月", "this_month"),
                    ("全期間", "all"),
                ],
                value="today",
                id="date-range",
            )
            yield Select(
                [
                    ("5分以上", "300"),
                    ("10分以上", "600"),
                    ("30分以上", "1800"),
                    ("1時間以上", "3600"),
                ],
                value="600",
                id="min-duration",
            )
        with Horizontal(id="main-area"):
            yield DataTable(id="session-table")
            yield Static("セッションを選択してください", id="detail-panel")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#session-table", DataTable)
        table.add_columns("exe", "タイトル", "開始", "アクティブ", "アイドル")
        table.cursor_type = "row"
        self._refresh()

    def _refresh(self) -> None:
        """フィルタ条件でセッション一覧を再取得する."""
        search = self.query_one("#search-input", Input).value or None
        date_sel = self.query_one("#date-range", Select)
        date_range = str(date_sel.value) if date_sel.value != Select.BLANK else "today"
        dur_sel = self.query_one("#min-duration", Select)
        min_dur = float(dur_sel.value) if dur_sel.value != Select.BLANK else 600.0

        self._sessions = self._filter.query(
            min_duration_sec=min_dur,
            date_range=date_range,
            executable=search,
            excluded_executables=self._config.filter.excluded_executables or None,
        )

        table = self.query_one("#session-table", DataTable)
        table.clear()
        for s in self._sessions:
            table.add_row(
                s.executable,
                _truncate(s.window_title, 40),
                s.started_at.strftime("%m/%d %H:%M"),
                _format_duration(s.active_seconds),
                _format_duration(s.idle_seconds),
                key=str(s.id),
            )

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if not (event.row_key and event.row_key.value):
            return
        session = next(
            (s for s in self._sessions if str(s.id) == event.row_key.value),
            None,
        )
        if session:
            self._show_detail(session)

    def _show_detail(self, session: SessionRecord) -> None:
        """右ペインにセッション詳細を表示する."""
        panel = self.query_one("#detail-panel", Static)
        total = session.active_seconds + session.idle_seconds
        active_pct = (session.active_seconds / total * 100) if total > 0 else 0
        ended = session.ended_at.strftime("%Y-%m-%d %H:%M:%S") if session.ended_at else "進行中"
        detail = (
            f"[bold]{session.executable}[/bold]\n"
            f"{session.window_title}\n\n"
            f"PID: {session.pid}\n"
            f"開始: {session.started_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"終了: {ended}\n\n"
            f"アクティブ: {_format_duration(session.active_seconds)}\n"
            f"アイドル:   {_format_duration(session.idle_seconds)}\n"
            f"アクティブ率: {active_pct:.0f}%\n"
        )
        panel.update(detail)

    # --- イベントハンドラ ---

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "search-input":
            self._refresh()

    def on_select_changed(self, _event: Select.Changed) -> None:
        self._refresh()

    def action_refresh_data(self) -> None:
        self._refresh()

    def action_open_settings(self) -> None:
        from activity_logger.tui.settings_screen import SettingsScreen

        self.push_screen(SettingsScreen(self._config), callback=self._on_settings_closed)

    def _on_settings_closed(self, saved: bool | None) -> None:
        if saved:
            self._refresh()


def _truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


def _format_duration(seconds: float) -> str:
    h, remainder = divmod(int(seconds), 3600)
    m, s = divmod(remainder, 60)
    if h > 0:
        return f"{h}h{m:02d}m"
    return f"{m}m{s:02d}s"
