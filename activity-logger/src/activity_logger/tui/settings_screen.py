"""設定画面（TUI から閾値・除外アプリを編集する）."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, ListItem, ListView, Static

from activity_logger.config import AppConfig


class SettingsScreen(ModalScreen[bool]):
    """設定編集モーダル."""

    CSS = """
    SettingsScreen {
        align: center middle;
    }
    #settings-container {
        width: 64;
        height: auto;
        max-height: 80%;
        border: thick $accent;
        padding: 1 2;
        background: $surface;
    }
    .setting-row {
        layout: horizontal;
        height: 3;
        margin-bottom: 1;
    }
    .setting-row Label {
        width: 26;
        content-align-vertical: middle;
    }
    .setting-row Input {
        width: 1fr;
    }
    #excluded-list {
        height: 8;
        margin: 1 0;
    }
    #button-bar {
        layout: horizontal;
        height: 3;
        align-horizontal: right;
        margin-top: 1;
    }
    #button-bar Button {
        margin-left: 1;
    }
    """

    BINDINGS = [("escape", "cancel", "キャンセル")]

    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self._config = config

    def compose(self) -> ComposeResult:
        with Vertical(id="settings-container"):
            yield Static("[bold]設定[/bold]")

            with Horizontal(classes="setting-row"):
                yield Label("アイドル閾値 (秒):")
                yield Input(str(self._config.idle.threshold_sec), id="idle-threshold")
            with Horizontal(classes="setting-row"):
                yield Label("最小記録時間 (秒):")
                yield Input(str(self._config.session.min_duration_sec), id="min-duration")
            with Horizontal(classes="setting-row"):
                yield Label("ポーリング間隔 (秒):")
                yield Input(str(self._config.collector.polling_interval_sec), id="poll-interval")

            yield Static("[bold]除外アプリ[/bold]")
            yield ListView(
                *[ListItem(Label(exe)) for exe in self._config.filter.excluded_executables],
                id="excluded-list",
            )
            with Horizontal(classes="setting-row"):
                yield Input(placeholder="exe名を入力して追加...", id="add-excluded")
                yield Button("追加", id="btn-add")
                yield Button("削除", variant="error", id="btn-remove")

            with Horizontal(id="button-bar"):
                yield Button("キャンセル", id="btn-cancel")
                yield Button("保存", variant="primary", id="btn-save")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        match event.button.id:
            case "btn-save":
                self._apply_and_save()
            case "btn-cancel":
                self.dismiss(False)
            case "btn-add":
                self._add_excluded()
            case "btn-remove":
                self._remove_excluded()

    def action_cancel(self) -> None:
        self.dismiss(False)

    def _add_excluded(self) -> None:
        inp = self.query_one("#add-excluded", Input)
        exe = inp.value.strip()
        if not exe or exe in self._config.filter.excluded_executables:
            return
        self._config.filter.excluded_executables.append(exe)
        lv = self.query_one("#excluded-list", ListView)
        lv.append(ListItem(Label(exe)))
        inp.value = ""

    def _remove_excluded(self) -> None:
        lv = self.query_one("#excluded-list", ListView)
        idx = lv.index
        if idx is None or idx < 0 or idx >= len(self._config.filter.excluded_executables):
            return
        self._config.filter.excluded_executables.pop(idx)
        item = lv.children[idx]
        item.remove()

    def _apply_and_save(self) -> None:
        """入力値をバリデーションして設定を保存する."""
        try:
            idle = int(self.query_one("#idle-threshold", Input).value)
            min_dur = int(self.query_one("#min-duration", Input).value)
            poll = int(self.query_one("#poll-interval", Input).value)
        except ValueError:
            self.notify("数値を入力してください", severity="error")
            return

        if idle < 1 or min_dur < 1 or poll < 1:
            self.notify("1 以上の値を入力してください", severity="error")
            return

        self._config.idle.threshold_sec = idle
        self._config.session.min_duration_sec = min_dur
        self._config.collector.polling_interval_sec = poll
        self._config.save()
        self.notify("設定を保存しました")
        self.dismiss(True)
