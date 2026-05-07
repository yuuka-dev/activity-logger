"""Win32 API ポーラー."""

from __future__ import annotations

import ctypes
import ctypes.wintypes
from dataclasses import dataclass

import psutil


@dataclass
class WindowInfo:
    """前面ウィンドウの情報."""

    hwnd: int
    pid: int
    executable: str
    window_title: str


def get_foreground_window_info() -> WindowInfo | None:
    """前面ウィンドウの情報を取得する．ウィンドウが無い場合は None."""
    hwnd = ctypes.windll.user32.GetForegroundWindow()
    if not hwnd:
        return None

    # ウィンドウタイトル取得
    length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
    if length == 0:
        return None
    buf = ctypes.create_unicode_buffer(length + 1)
    ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
    title = buf.value

    # PID 取得
    pid = ctypes.wintypes.DWORD()
    ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    pid_val = pid.value

    # プロセス名取得
    try:
        proc = psutil.Process(pid_val)
        exe_name = proc.name()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        exe_name = "unknown"

    return WindowInfo(hwnd=hwnd, pid=pid_val, executable=exe_name, window_title=title)


def get_idle_seconds() -> float:
    """マウス／キーボードの最終入力からの経過秒数を返す."""

    class LASTINPUTINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", ctypes.wintypes.UINT),
            ("dwTime", ctypes.wintypes.DWORD),
        ]

    lii = LASTINPUTINFO()
    lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
    if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii)):
        return 0.0

    tick_count = ctypes.windll.kernel32.GetTickCount()
    elapsed_ms = tick_count - lii.dwTime
    # GetTickCount は約 49.7 日でオーバーフローするため負数補正
    if elapsed_ms < 0:
        elapsed_ms += 0x1_0000_0000
    return elapsed_ms / 1000.0
