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
    CLOSED = auto()


def _now() -> datetime:
    return datetime.now(JST)


@dataclass
class Session:
    """1 つのアプリ使用セッションを追跡する．

    状態遷移:
        ACTIVE ──5分無入力──▶ IDLE
        ACTIVE / IDLE ──アプリ切替──▶ CLOSED
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
        """ポーリング 1 回分の経過時間を加算する."""
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

    def close(self, now: datetime | None = None) -> None:
        """セッションを終了する."""
        now = now or _now()
        self.state = SessionState.CLOSED
        self._last_tick = now
