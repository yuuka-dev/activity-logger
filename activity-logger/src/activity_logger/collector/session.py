"""セッション状態機械."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")


class SessionState(Enum):
    """セッションの状態."""

    ACTIVE = auto()
    IDLE = auto()
    BACKGROUND = auto()
    CLOSED = auto()


def _now() -> datetime:
    return datetime.now(JST)


@dataclass
class Session:
    """1 つのアプリ使用セッションを追跡する．

    状態遷移:
        ACTIVE ──5分無入力──▶ IDLE ──入力復帰──▶ ACTIVE
        ACTIVE / IDLE ──アプリ切替──▶ BACKGROUND ──復帰──▶ ACTIVE
        BACKGROUND ──閾値超過──▶ CLOSED
    """

    executable: str
    window_title: str
    pid: int
    state: SessionState = SessionState.ACTIVE
    started_at: datetime = field(default_factory=_now)
    active_seconds: float = 0.0
    idle_seconds: float = 0.0
    db_id: int | None = None
    _last_tick: datetime = field(default_factory=_now, repr=False)

    def tick(self, *, is_idle: bool, now: datetime | None = None) -> None:
        """前面にいるとき: ポーリング 1 回分の経過時間を加算する."""
        now = now or _now()
        elapsed = (now - self._last_tick).total_seconds()
        self._last_tick = now

        if elapsed <= 0:
            return

        if is_idle:
            self.idle_seconds += elapsed
            self.state = SessionState.IDLE
        else:
            self.active_seconds += elapsed
            self.state = SessionState.ACTIVE

    def to_background(self, now: datetime | None = None) -> None:
        """非前面に移行．last_tick を更新して時間加算を停止する."""
        now = now or _now()
        self._last_tick = now
        self.state = SessionState.BACKGROUND

    def resume(self, now: datetime | None = None) -> None:
        """バックグラウンドから前面復帰．背景時間をカウントしないよう last_tick をリセット."""
        now = now or _now()
        self._last_tick = now
        self.state = SessionState.ACTIVE

    def seconds_since_last_tick(self, now: datetime | None = None) -> float:
        """最後に前面だった時刻からの経過秒数."""
        now = now or _now()
        return (now - self._last_tick).total_seconds()

    def close(self, now: datetime | None = None) -> None:
        """セッションを終了する."""
        now = now or _now()
        self.state = SessionState.CLOSED
        self._last_tick = now
