"""設定ファイルの読み書き."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from platformdirs import user_config_dir, user_data_dir


def _config_dir() -> Path:
    return Path(user_config_dir("activity-logger", appauthor=False))


def _default_config_path() -> Path:
    return _config_dir() / "config.toml"


@dataclass
class IdleConfig:
    """アイドル検出設定."""

    threshold_sec: int = 300  # 5分


@dataclass
class SessionConfig:
    """セッション記録設定."""

    min_duration_sec: int = 600  # 10分


@dataclass
class CollectorConfig:
    """コレクター設定."""

    polling_interval_sec: int = 5


@dataclass
class StorageConfig:
    """ストレージ設定."""

    db_path: str = ""  # 空文字 = デフォルト（platformdirs）


@dataclass
class FilterConfig:
    """フィルタ設定."""

    excluded_executables: list[str] = field(default_factory=list)


@dataclass
class AppConfig:
    """アプリケーション全体の設定."""

    idle: IdleConfig = field(default_factory=IdleConfig)
    session: SessionConfig = field(default_factory=SessionConfig)
    collector: CollectorConfig = field(default_factory=CollectorConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    filter: FilterConfig = field(default_factory=FilterConfig)

    _path: Path | None = field(default=None, repr=False)

    @classmethod
    def load(cls, path: Path | None = None) -> AppConfig:
        """設定ファイルを読み込む．存在しなければデフォルト値で新規作成する."""
        path = path or _default_config_path()
        if not path.exists():
            cfg = cls(_path=path)
            cfg.save()
            return cfg
        with open(path, "rb") as f:
            data = tomllib.load(f)
        return cls(
            idle=IdleConfig(**data.get("idle", {})),
            session=SessionConfig(**data.get("session", {})),
            collector=CollectorConfig(**data.get("collector", {})),
            storage=StorageConfig(**data.get("storage", {})),
            filter=FilterConfig(**data.get("filter", {})),
            _path=path,
        )

    def save(self, path: Path | None = None) -> None:
        """設定ファイルに書き出す."""
        path = path or self._path or _default_config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(_serialize_toml(self))

    def resolve_db_path(self) -> Path:
        """DB ファイルの絶対パスを返す."""
        if self.storage.db_path:
            return Path(self.storage.db_path)
        return Path(user_data_dir("activity-logger", appauthor=False)) / "activity.db"


def _serialize_toml(cfg: AppConfig) -> str:
    """AppConfig を TOML 文字列に変換する."""
    excluded = ", ".join(f'"{e}"' for e in cfg.filter.excluded_executables)
    return (
        f"[idle]\n"
        f"threshold_sec = {cfg.idle.threshold_sec}\n"
        f"\n"
        f"[session]\n"
        f"min_duration_sec = {cfg.session.min_duration_sec}\n"
        f"\n"
        f"[collector]\n"
        f"polling_interval_sec = {cfg.collector.polling_interval_sec}\n"
        f"\n"
        f"[storage]\n"
        f'db_path = "{cfg.storage.db_path}"\n'
        f"\n"
        f"[filter]\n"
        f"excluded_executables = [{excluded}]\n"
    )
