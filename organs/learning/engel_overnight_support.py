"""
Shared filesystem and process helpers for engel_overnight_loop and engel_overnight_runner.

Behavior matches the previous inlined implementations in those scripts (paths, timestamps,
UTF-8 read/write, Windows PID checks).
"""

from __future__ import annotations

import datetime
import os
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parent
MEMORY_DIR = APP_ROOT / "memory"
REPORTS_DIR = APP_ROOT / "reports"
OVERNIGHT_DIR = REPORTS_DIR / "overnight"


def format_now() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def stamp_compact() -> str:
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


def ensure_base_dirs() -> None:
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    OVERNIGHT_DIR.mkdir(parents=True, exist_ok=True)


def read_utf8_optional(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def write_utf8(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text + ("\n" if not text.endswith("\n") else ""), encoding="utf-8")


def pid_alive(pid: int) -> bool:
    try:
        pid = int(pid)
    except Exception:
        return False
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            import ctypes

            process_query_limited_information = 0x1000
            still_active = 259
            handle = ctypes.windll.kernel32.OpenProcess(
                process_query_limited_information, False, pid
            )
            if not handle:
                return False
            code = ctypes.c_ulong()
            ok = ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
            ctypes.windll.kernel32.CloseHandle(handle)
            return bool(ok) and code.value == still_active
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except Exception:
        return False
