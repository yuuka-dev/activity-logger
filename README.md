# activity-logger

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/)
[![Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://docs.astral.sh/ruff/)

> **閾値フィルタ付き Windows アクティビティロガー**: 前面ウィンドウを追跡し，10分以上の有意なセッションだけを記録・可視化する

## 概要

### なぜ作ったのか

- ActivityWatch 等の既存ツールは粒度が細かすぎて，ちょっと触っただけのアプリまで記録される
- 「10分以上使ったアプリだけ知りたい」という閾値フィルタの思想を持つツールが存在しない
- 自分の PC 使用パターンを振り返るために，**ノイズを切り捨てた有意なセッションログ**が欲しかった

## 主な機能

- **閾値フィルタ**: 10分未満の短時間利用はノイズとして除外（閾値は設定変更可）
- **アイドル検出**: マウス／キーボード無入力 5分でアイドル判定，アクティブ時間のみカウント
- **ManicTime 風 Web UI**: 24時間タイムラインバーでアプリ使用を色分け可視化
- **TUI ビューア**: ターミナルから素早く確認できる Textual ベースの 3 ペイン画面
- **設定の TUI 編集**: 閾値・除外アプリを TUI のモーダルから変更・保存
- **疎結合設計**: collector（常駐）と viewer（TUI / Web）は SQLite 経由で完全分離

## 技術スタック

| カテゴリ | 技術 |
|---|---|
| 言語 | Python 3.12+ |
| Win32 API | `ctypes`（GetForegroundWindow, GetLastInputInfo） |
| プロセス情報 | `psutil` |
| データストア | SQLite（WAL モード） |
| TUI | Textual |
| Web UI | FastAPI + Vanilla JS |
| パッケージ管理 | uv |
| リンタ / フォーマッタ | Ruff |
| 依存解析 | import-linter, pydeps |

## アーキテクチャ

```
src/activity_logger/
├── config.py            # 設定ファイル読み書き（共有）
├── collector/           # L0: Win32 API ポーラー（常駐デーモン）
│   ├── poller.py        #     GetForegroundWindow + GetLastInputInfo
│   ├── session.py       #     ACTIVE / IDLE / CLOSED 状態機械
│   └── main.py          #     メインループ + シグナルハンドリング
├── storage/             # L1: SQLite 永続化層（WAL モード）
│   └── database.py      #     sessions テーブル CRUD + 条件検索
├── filter/              # L2: 閾値フィルタ・集計ロジック
│   └── query.py         #     日付レンジ / exe 別サマリ
├── tui/                 # L3: Textual TUI（閲覧・設定編集）
│   ├── app.py           #     3 ペイン構成
│   └── settings_screen.py
├── web/                 # L3: Web UI（ManicTime 風タイムライン）
│   ├── server.py        #     FastAPI
│   └── static/index.html
└── cli/                 # L4: エントリーポイント
    └── main.py
```

レイヤー間の依存は上位→下位の一方向のみ（`import-linter` で強制）．
collector と viewer は直接通信せず，必ず SQLite を介する．

詳細は [CLAUDE.md](CLAUDE.md) を参照（リポジトリには含まれません）．

## はじめ方

### 前提条件

- Windows 10 / 11
- Python 3.12+
- [uv](https://docs.astral.sh/uv/)（`winget install astral-sh.uv`）

### セットアップ

```bash
git clone https://github.com/yuuka-dev/activity-logger.git
cd activity-logger/activity-logger
uv sync
```

### 使い方

```bash
# 1. コレクターを起動（バックグラウンドでウィンドウ追跡開始）
.venv/Scripts/activity-collector

# 2-a. Web UI で確認（ManicTime 風タイムライン）
.venv/Scripts/activity-logger web
# → http://127.0.0.1:8080

# 2-b. TUI で確認（ターミナル内）
.venv/Scripts/activity-logger
```

### グローバルインストール（pipx / uv tool）

```bash
uv tool install ./activity-logger
# → activity-logger, activity-collector, activity-web が PATH に登録される
```

### TUI キーバインド

| キー | 操作 |
|---|---|
| `r` | データ更新 |
| `s` | 設定画面を開く |
| `q` | 終了 |

### 設定

設定ファイルは `%LOCALAPPDATA%/activity-logger/config.toml` に自動生成される．

```toml
[idle]
threshold_sec = 300          # アイドル判定: 5分

[session]
min_duration_sec = 600       # 最小記録時間: 10分

[collector]
polling_interval_sec = 5     # ポーリング間隔

[storage]
db_path = ""                 # 空 = デフォルト

[filter]
excluded_executables = []    # 除外アプリ (例: ["SearchUI.exe"])
```

TUI の設定画面（`s` キー）からも編集可能．

### テスト

```bash
uv run pytest
```

## デモ

**Web UI**: `activity-logger web` → http://127.0.0.1:8080

| 機能 | スクリーンショット |
|---|---|
| タイムライン（24h カラーセグメント） | ![タイムライン](./SampleImage/timeline.png) |
| アプリ使用サマリ | ![サマリ](./SampleImage/summary.png) |

## ライセンス

MIT License
