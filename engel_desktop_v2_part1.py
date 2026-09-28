"""Engel Desktop V2 Ã¢â‚¬â€ simplified TEL-style operator interface.

Clean dark layout with four functional panels:
  - System Monitor  (CPU / RAM / Disk / Network live readouts)
  - Agent Chat      (single-turn conversation with Engel AI)
  - Goal Queue      (VantaMoth tasks, progress, next/blocker)
  - Model Route     (active model selector + status)

Design principles from TEL screenshot:
  - Near-black background with subtle card borders
  - Green accent for live/active state
  - No toolbars, no menus, no cluttered tabs
  - Every panel fits in one screen without scrolling
"""
from __future__ import annotations

import engel_temp_policy  # noqa: F401
import datetime
import ctypes
import json
import os
import platform
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

from engel_project_paths import resolve_engel_app_root

ENGEL_APP_ROOT = resolve_engel_app_root(__file__)
GOAL_QUEUE_FILE = ENGEL_APP_ROOT / "memory" / "GOAL_QUEUE_STATE.json"
ENGEL_ICON_PATHS = (
    ENGEL_APP_ROOT / "assets" / "branding" / "final" / "engel_icon_final.ico",
    ENGEL_APP_ROOT / "assets" / "branding" / "engel_icon.ico",
)
DEVICE_STATUS_ADAPTERS = (
    "local_windows_pc",
    "android_usb_adb_live",
    "android_wifi_lan_pairing",
    "android_registry_future_slots",
    "sub_engel_lan_pair_session",
    "sub_engel_hardwire_future_slot",
)
_SINGLE_INSTANCE_MUTEX = None


def _ensure_project_on_path() -> None:
    names = (
        "engel_project_paths",
        "engel_android_worker_prompt_signals",
        "engel_remote_worker_lan_pairing",
        "engel_remote_worker_link_manager",
        "engel_adb_worker_manager",
        "engel_phone_wake_manager",
        "engel_ui_system_actions",
        "engel_device_capability_registry",
    )
    try:
        from engel_project_paths import prefer_workspace_modules
    except ImportError:
        # Bundled Engel.exe may have a stale engel_project_paths.py without
        # prefer_workspace_modules. Use the inline fallback so the GUI still
        # boots; the workspace version will get loaded on next exe rebuild.
        prefer_workspace_modules = _inline_prefer_workspace_modules
    prefer_workspace_modules(*names, caller_file=__file__)


def _inline_prefer_workspace_modules(*names: str, caller_file: object | None = None) -> None:
    """Fallback for stale PyInstaller bundles whose engel_project_paths.py
    predates the prefer_workspace_modules helper. Same intent: make sure the
    workspace D: copy wins over any extracted _MEI / pyinstaller_tmp copy."""
    import os
    import sys

    candidate = None
    if caller_file is not None:
        directory = os.path.dirname(os.path.abspath(str(caller_file)))
        while directory and directory != os.path.dirname(directory):
            marker = os.path.join(directory, "engel_project_paths.py")
            lowered = directory.replace("\\", "/").lower()
            if os.path.isfile(marker) and "pyinstaller_tmp" not in lowered and "/_mei" not in lowered:
                candidate = directory
                break
            directory = os.path.dirname(directory)
    if not candidate:
        candidate = r"D:\b.WorkSpace\Engel App"
    if os.path.isdir(candidate):
        if candidate in sys.path:
            sys.path.remove(candidate)
        sys.path.insert(0, candidate)
    for name in names:
        module = sys.modules.get(name)
        if module is None:
            continue
        path_text = (getattr(module, "__file__", "") or "").replace("\\", "/").lower()
        if "pyinstaller_tmp" in path_text or "/_mei" in path_text:
            sys.modules.pop(name, None)


def _engel_icon() -> QIcon:
    for path in ENGEL_ICON_PATHS:
        if path.exists():
            return QIcon(str(path))
    return QIcon()


def _is_port_open(host: str = "127.0.0.1", port: int = 8787, timeout: float = 0.35) -> bool:
    hosts = (host,)
    if host in {"127.0.0.1", "localhost"}:
        hosts = ("127.0.0.1", "::1")
    for candidate in hosts:
        try:
            with socket.create_connection((candidate, int(port)), timeout=timeout):
                return True
        except OSError:
            pass
    return False


def _clean_ui_text(text: str) -> str:
    """Keep packaged UI text readable even when old mojibake literals remain."""
    value = str(text or "")
    for old, new in {
        "ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦": "...",
        "Ã¢â‚¬Â¦": "...",
        "ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â": "-",
        "Ã¢â‚¬â€": "-",
        "Ãƒâ€šÃ‚Â·": "|",
        "Ã‚Â·": "|",
        "ÃƒÂ¢Ã¢â‚¬ÂÃ¢â‚¬Å¡": "|",
        "Ã¢â€â€š": "|",
        "ÃƒÂ¢Ã¢â‚¬â€Ã‚Â": "*",
        "Ã¢â€”Â": "*",
        "ÃƒÂ¢Ã…â€œÃ¢â‚¬Å“": "[x]",
        "Ã¢Å“â€œ": "[x]",
        "ÃƒÂ¢Ã¢â‚¬â€Ã¢â‚¬Â¹": "[ ]",
        "Ã¢â€”â€¹": "[ ]",
        "ÃƒÂ¢Ã…â€™Ã‚Â¬": "",
        "Ã¢Å’Â¬": "",
        "ÃƒÂ¢Ã‚Â¬Ã‚Â¡": "",
        "Ã¢Â¬Â¡": "",
        "ÃƒÂ¢Ã…Â¡Ã¢â‚¬Ëœ": ">",
        "Ã¢Å¡â€˜": ">",
        "ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬Ëœ": "+",
        "Ã¢â€ â€˜": "+",
    }.items():
        value = value.replace(old, new)
    value = value.strip()
    if "ENGEL AI" in value:
        return "ENGEL AI"
    if "Desktop V2" in value and "local-first" in value:
        return "local-first"
    if "Meeting Room" in value:
        return "Meeting Room"
    if "Octogent" in value:
        return "Octogent"
    if "routes loaded" in value:
        return "* " + value.split("routes loaded", 1)[0].strip("* ").strip() + " routes loaded"
    if "routes loading" in value:
        return "* routes loading..."
    if "SAFE MODE" in value:
        return "* SAFE MODE"
    if "no provider" in value:
        return "no provider | no network | no background worker"
    if value in {"|", "||"}:
        return "|"
    return value


def _sanitize_widget_texts(root: QWidget) -> None:
    for label in root.findChildren(QLabel):
        cleaned = _clean_ui_text(label.text())
        if cleaned != label.text():
            label.setText(cleaned)
    for button in root.findChildren(QPushButton):
        cleaned = _clean_ui_text(button.text())
        if cleaned != button.text():
            button.setText(cleaned)
    for line_edit in root.findChildren(QLineEdit):
        cleaned = _clean_ui_text(line_edit.placeholderText())
        if cleaned != line_edit.placeholderText():
            line_edit.setPlaceholderText(cleaned)
    for tabs in root.findChildren(QTabWidget):
        for index in range(tabs.count()):
            cleaned = _clean_ui_text(tabs.tabText(index))
            if cleaned != tabs.tabText(index):
                tabs.setTabText(index, cleaned)
    for list_widget in root.findChildren(QListWidget):
        for index in range(list_widget.count()):
            item = list_widget.item(index)
            cleaned = _clean_ui_text(item.text())
            if cleaned != item.text():
                item.setText(cleaned)


def _is_unhelpful_chat_reply(reply: str) -> bool:
    lowered = str(reply or "").casefold()
    if not lowered.strip():
        return True
    bad_fragments = (
        "engel desktop v2 is already running",
        "not opening a second window",
        "(no response)",
        "empty response",
        "don't have a live ai connected",
        "do not have a live ai connected",
        "i don't have a live ai connected",
        "i do not have a live ai connected",
        "connect me to an external ai",
        "for full intelligent answers",
        "for full ai conversation",
        "browser ai connect",
        "system action that needs explicit approval",
        "use the exact engel command syntax",
    )
    return any(fragment in lowered for fragment in bad_fragments)


def _clean_chat_reply_for_ui(reply: str) -> str:
    """Trim process receipts so the main chat reads like an answer."""
    text = str(reply or "").strip()
    if not text:
        return text
    for marker in ("\nSafety:", "\nResume this session with:"):
        if marker in text:
            text = text.split(marker, 1)[0].rstrip()
    return text.strip()


def _local_bridge_reply_for_meeting_order(user_text: str) -> str:
    """Use Engel's local bridge when the provider lane only produced guidance."""
    artifact_kind = ""
    try:
        from engel_ui_executable_results import _infer_kind

        artifact_kind = str(_infer_kind(user_text) or "")
    except Exception:
        artifact_kind = ""
    if artifact_kind:
        return (
            "Engel local bridge is connected. I routed this through the Agent "
            f"Meeting Room, selected the matching station path, and will finalize "
            f"the requested {artifact_kind} artifact into the project results folder."
        )
    return (
        "Engel local bridge is connected. I routed this through the Agent Meeting "
        "Room, selected the matching agent/device path, and recorded the result "
        "back through the main UI."
    )

# Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬ Qt import (PyQt6 preferred, PySide6 fallback) Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
try:
    from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal
    from PyQt6.QtGui import QColor, QIcon
    from PyQt6.QtWidgets import (
        QApplication, QWidget, QMainWindow,
        QVBoxLayout, QHBoxLayout, QGridLayout,
        QLabel, QLineEdit, QPushButton, QTextEdit,
        QFrame, QProgressBar, QComboBox,
        QListWidget, QListWidgetItem, QScrollArea, QTabWidget,
    )
    HAS_QT = True
except ImportError:
    try:
        from PySide6.QtCore import Qt, QTimer, QThread
        from PySide6.QtCore import Signal as pyqtSignal  # type: ignore[assignment]
        from PySide6.QtGui import QColor, QIcon
        from PySide6.QtWidgets import (
            QApplication, QWidget, QMainWindow,
            QVBoxLayout, QHBoxLayout, QGridLayout,
            QLabel, QLineEdit, QPushButton, QTextEdit,
            QFrame, QProgressBar, QComboBox,
            QListWidget, QListWidgetItem, QScrollArea, QTabWidget,
        )
        HAS_QT = True
    except ImportError:
        HAS_QT = False

# Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬ Palette Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
BG       = "#0d0d14"
BG_GLASS = "rgba(13, 13, 20, 168)"
CARD     = "#12121c"
CARD_GLASS = "rgba(18, 18, 28, 176)"
CARD2    = "#16162a"
CARD2_GLASS = "rgba(22, 22, 42, 184)"
BORDER   = "#1e1e30"
BORDER2  = "#2a2a45"
TEXT     = "#c8c8e8"
DIM      = "#5a5a7a"
GREEN    = "#00e87a"
AMBER    = "#ffaa00"
RED      = "#ff4455"
BLUE     = "#44aaff"
PURPLE   = "#aa77ff"
FONT     = "Consolas, 'Cascadia Mono', 'Courier New', monospace"
DEFAULT_WINDOW_OPACITY = 0.94


def _ui_opacity(*names: str, default: float = DEFAULT_WINDOW_OPACITY) -> float:
    """Read a clamped window opacity from the environment."""
    for name in names:
        raw = os.environ.get(name)
        if not raw:
            continue
        try:
            return max(0.55, min(1.0, float(raw)))
        except ValueError:
            return default
    return default


def _env_enabled(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _claim_desktop_single_instance() -> bool:
    """Prevent accidental duplicate Desktop V2 windows from chat/process launches."""
    global _SINGLE_INSTANCE_MUTEX
    if os.name != "nt":
        return True
    try:
        kernel32 = ctypes.windll.kernel32
        mutex = kernel32.CreateMutexW(None, False, "Local\\EngelDesktopV2SingleInstance")
        if not mutex:
            return True
        already_exists = kernel32.GetLastError() == 183  # ERROR_ALREADY_EXISTS
        if already_exists:
            kernel32.CloseHandle(mutex)
            return False
        _SINGLE_INSTANCE_MUTEX = mutex
        return True
    except Exception:
        return True

STYLESHEET = f"""
QMainWindow, QWidget {{
    background: {BG_GLASS};
    color: {TEXT};
    font-family: {FONT};
    font-size: 9pt;
}}
QFrame.card {{
    background: {CARD_GLASS};
    border: 1px solid {BORDER};
    border-radius: 6px;
}}
QLabel.title {{
    color: {TEXT};
    font-weight: 700;
    font-size: 10pt;
}}
QLabel.stat-key {{
    color: {DIM};
    font-size: 8pt;
}}
QLabel.stat-val {{
    color: {GREEN};
    font-weight: 700;
    font-size: 9pt;
}}
QLabel.dim {{
    color: {DIM};
    font-size: 8pt;
}}
QLineEdit {{
    background: {CARD2_GLASS};
    border: 1px solid {BORDER2};
    border-radius: 4px;
    color: {TEXT};
    padding: 4px 8px;
    font-family: {FONT};
    font-size: 9pt;
}}
QLineEdit:focus {{
    border-color: {GREEN};
}}
QPushButton {{
    background: {CARD_GLASS};
    color: {GREEN};
    border: 1px solid {BORDER2};
    border-radius: 4px;
    padding: 4px 12px;
    font-weight: 700;
    font-size: 9pt;
    min-height: 24px;
}}
QPushButton:hover {{
    background: {CARD2};
    border-color: {GREEN};
    color: #ffffff;
}}
QPushButton:pressed {{
    background: #0d1f15;
}}
QPushButton#send_btn {{
    background: {GREEN};
    color: {BG};
    border: none;
    font-weight: 900;
    min-width: 60px;
}}
QPushButton#send_btn:hover {{
    background: #00ff88;
    color: {BG};
}}
QTextEdit {{
    background: {BG_GLASS};
    border: none;
    color: {TEXT};
    font-family: {FONT};
    font-size: 9pt;
    padding: 4px;
    selection-background-color: #1a3a2a;
}}
QProgressBar {{
    background: {CARD2_GLASS};
    border: 1px solid {BORDER};
    border-radius: 3px;
    height: 6px;
    text-align: center;
}}
QProgressBar::chunk {{
    background: {GREEN};
    border-radius: 3px;
}}
QComboBox {{
    background: {CARD_GLASS};
    border: 1px solid {BORDER2};
    border-radius: 4px;
    color: {TEXT};
    padding: 3px 8px;
    font-family: {FONT};
    font-size: 9pt;
}}
QComboBox::drop-down {{
    border: none;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 6px;
    border: none;
}}
QScrollBar::handle:vertical {{
    background: {BORDER2};
    border-radius: 3px;
    min-height: 20px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
"""

# Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬ System stats helper Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
def _get_system_stats() -> dict:
    stats: dict = {}
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory()
        disk_root = ENGEL_APP_ROOT.anchor or "C:\\"
        disk = psutil.disk_usage(disk_root)
        net = psutil.net_io_counters()
        stats["cpu"] = f"{cpu:.0f}%"
        stats["ram"] = f"{mem.percent:.0f}% ({mem.used / (1024**3):.1f}/{mem.total / (1024**3):.1f}GB)"
        stats["disk"] = f"{disk.percent:.0f}% ({disk.used // (1024**3):.0f}/{disk.total // (1024**3):.0f}GB)"
        stats["disk_root"] = disk_root
        stats["net_sent"] = f"{net.bytes_sent / (1024**2):.0f}M"
        stats["net_recv"] = f"{net.bytes_recv / (1024**2):.0f}M"
        stats["gpu"] = _get_gpu_usage_label()
    except ImportError:
        stats["cpu"] = "N/A"
        stats["ram"] = "N/A (install psutil)"
        stats["disk"] = "N/A"
        stats["net_sent"] = "N/A"
        stats["net_recv"] = "N/A"
        stats["gpu"] = _get_gpu_usage_label()
    except Exception as exc:
        stats["error"] = str(exc)
        stats.setdefault("gpu", _get_gpu_usage_label())
    stats["time"] = datetime.datetime.now().strftime("%H:%M:%S")
    stats["host"] = platform.node()
    stats["os"]   = platform.system() + " " + platform.release()
    return stats


def _run_short_command(cmd: list[str], timeout: float = 1.5) -> subprocess.CompletedProcess[str] | None:
    try:
        kwargs = {
            "capture_output": True,
            "text": True,
            "timeout": timeout,
            "shell": False,
        }
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0
            kwargs["startupinfo"] = startupinfo
            if hasattr(subprocess, "CREATE_NO_WINDOW"):
                kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        return subprocess.run(cmd, **kwargs)
    except Exception:
        return None


def _engel_rs_candidates() -> list[Path]:
    env_path = os.environ.get("ENGEL_AI_RS_EXE", "").strip()
    candidates: list[Path] = []
    if env_path:
        candidates.append(Path(env_path))
    candidates.extend(
        [
            ENGEL_APP_ROOT / "runtime" / "temp" / "engel-rust-rewrite" / "cargo-target" / "debug" / "engel-ai-rs.exe",
            ENGEL_APP_ROOT / "runtime" / "temp" / "engel-rust-rewrite" / "cargo-target" / "release" / "engel-ai-rs.exe",
            ENGEL_APP_ROOT / "rust" / "engel-core-rs" / "target" / "debug" / "engel-ai-rs.exe",
            ENGEL_APP_ROOT / "rust" / "engel-core-rs" / "target" / "release" / "engel-ai-rs.exe",
        ]
    )
    seen: set[str] = set()
    unique: list[Path] = []
    for path in candidates:
        key = str(path).lower()
        if key not in seen:
            seen.add(key)
            unique.append(path)
    return unique


def _find_engel_rs_exe() -> Path | None:
    for path in _engel_rs_candidates():
        if path.exists():
            return path
    return None


def _pretty_json_if_possible(text: str) -> str:
    stripped = (text or "").strip()
    if not stripped:
        return ""
    try:
        return json.dumps(json.loads(stripped), indent=2, sort_keys=True)
    except Exception:
        return stripped


def _run_engel_rs(args: list[str], timeout: float = 60.0) -> str:
    exe = _find_engel_rs_exe()
    if exe is None:
        searched = "\n".join(f"  - {path}" for path in _engel_rs_candidates())
        return "Rust runtime not found. Searched:\n" + searched
    env = os.environ.copy()
    env["ENGEL_APP_ROOT"] = str(ENGEL_APP_ROOT)
    env["ENGEL_AI_RS_EXE"] = str(exe)
    cmd = [str(exe), *args]
    kwargs = {
        "cwd": str(ENGEL_APP_ROOT),
        "env": env,
        "capture_output": True,
        "text": True,
        "timeout": timeout,
        "shell": False,
    }
    if os.name == "nt":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0
        kwargs["startupinfo"] = startupinfo
        if hasattr(subprocess, "CREATE_NO_WINDOW"):
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    try:
        proc = subprocess.run(cmd, **kwargs)
    except subprocess.TimeoutExpired:
        return f"TIMEOUT after {timeout:.0f}s\nCommand: {' '.join(cmd)}"
    except Exception as exc:
        return f"ERROR running Rust command: {type(exc).__name__}: {exc}\nCommand: {' '.join(cmd)}"

    stdout = _pretty_json_if_possible(proc.stdout)
    stderr = (proc.stderr or "").strip()
    parts = [
        f"Command: {' '.join(cmd)}",
        f"Exit: {proc.returncode}",
    ]
    if stdout:
        parts.append("stdout:\n" + stdout)
    if stderr:
        parts.append("stderr:\n" + stderr)
    return "\n\n".join(parts)


def _get_gpu_usage_label() -> str:
    """Best-effort local GPU usage without adding a new dependency."""
    query = [
        "nvidia-smi",
        "--query-gpu=utilization.gpu,memory.used,memory.total,name",
        "--format=csv,noheader,nounits",
    ]
    proc = _run_short_command(query, timeout=1.2)
    if proc is not None and proc.returncode == 0 and proc.stdout.strip():
        gpus: list[str] = []
        for line in proc.stdout.splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 4:
                util, used, total, name = parts[:4]
                short_name = name.replace("NVIDIA", "").replace("GeForce", "").strip() or "GPU"
                gpus.append(f"{util}% ({used}/{total}MB) {short_name[:16]}")
        if gpus:
            return " | ".join(gpus[:2])
    return "N/A"


def _parse_proc_stat(text: str) -> tuple[int, int] | None:
    first = next((line for line in text.splitlines() if line.startswith("cpu ")), "")
    parts = first.split()[1:]
    if len(parts) < 5:
        return None
    try:
        nums = [int(float(p)) for p in parts[:8]]
    except ValueError:
        return None
    idle = nums[3] + nums[4]
    total = sum(nums)
    return total, idle


def _format_android_cpu(serial: str, adb_call) -> str:
    first = adb_call("shell", "cat /proc/stat", serial=serial, timeout=2)
    if first is None or first.returncode != 0:
        return "N/A"
    snap_a = _parse_proc_stat(first.stdout)
    time.sleep(0.08)
    second = adb_call("shell", "cat /proc/stat", serial=serial, timeout=2)
    if second is None or second.returncode != 0:
        return "N/A"
    snap_b = _parse_proc_stat(second.stdout)
    if not snap_a or not snap_b:
        return "N/A"
    total_delta = snap_b[0] - snap_a[0]
    idle_delta = snap_b[1] - snap_a[1]
    if total_delta <= 0:
        return "N/A"
    return f"{max(0, min(100, (1 - (idle_delta / total_delta)) * 100)):.0f}%"


def _format_android_ram(serial: str, adb_call) -> str:
    proc = adb_call("shell", "cat /proc/meminfo", serial=serial, timeout=2)
    if proc is None or proc.returncode != 0:
        return "N/A"
    values: dict[str, int] = {}
    for line in proc.stdout.splitlines():
        if ":" not in line:
            continue
        key, rest = line.split(":", 1)
        raw = rest.strip().split()[0:1]
        if not raw:
            continue
        try:
            values[key] = int(raw[0])
        except ValueError:
            pass
    total = values.get("MemTotal", 0)
    available = values.get("MemAvailable", values.get("MemFree", 0))
    if total <= 0:
        return "N/A"
    used = max(0, total - available)
    pct = used / total * 100
    return f"{pct:.0f}% ({used / 1048576:.1f}/{total / 1048576:.1f}GB)"


def _format_android_disk(serial: str, adb_call) -> str:
    proc = adb_call("shell", "df -k /sdcard 2>/dev/null || df -k /data", serial=serial, timeout=2)
    if proc is None or proc.returncode != 0:
        return "N/A"
    for line in proc.stdout.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 5:
            continue
        try:
            total = int(parts[1])
            used = int(parts[2])
        except ValueError:
            continue
        if total > 0:
            return f"{used / total * 100:.0f}% ({used // 1048576}/{total // 1048576}GB)"
    return "N/A"


def _format_android_net(serial: str, adb_call) -> str:
    proc = adb_call("shell", "cat /proc/net/dev", serial=serial, timeout=2)
    if proc is None or proc.returncode != 0:
        return "N/A"
    rx = 0
    tx = 0
    for line in proc.stdout.splitlines():
        if ":" not in line:
            continue
        iface, rest = line.split(":", 1)
        if iface.strip() == "lo":
            continue
        fields = rest.split()
        if len(fields) >= 16:
            try:
                rx += int(fields[0])
                tx += int(fields[8])
            except ValueError:
                pass
    if rx == 0 and tx == 0:
        return "N/A"
    return f"{tx / (1024**2):.0f}M/{rx / (1024**2):.0f}M"


def _read_local_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _registered_android_device_rows(connected_serials: set[str]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    phone_map = _read_local_json(ENGEL_APP_ROOT / "memory" / "ENGEL_PHONE_DEVICE_MAP_V1.json")
    for phone in phone_map.get("phones", []):
        if not isinstance(phone, dict):
            continue
        serial = str(phone.get("adb_serial", "")).strip()
        if not serial or serial in connected_serials:
            continue
        rows.append({
            "label": str(phone.get("marketing_name") or phone.get("model") or "Registered Android Phone"),
            "serial": serial,
            "workers": str(phone.get("assigned_worker_name") or phone.get("assigned_worker_id") or "registered worker"),
            "status": "registered / offline (USB or WiFi/LAN)",
            "cpu": "N/A",
            "ram": "N/A",
            "disk": "N/A",
            "net": "N/A",
            "gpu": "N/A",
        })
    for worker in phone_map.get("unassigned_workers", []):
        if not isinstance(worker, dict):
            continue
        rows.append({
            "label": str(worker.get("worker_id", "future_android_worker")),
            "serial": "future device slot",
            "workers": str(worker.get("status", "pending assignment")),
            "status": "future / unassigned (USB or WiFi/LAN)",
            "cpu": "N/A",
            "ram": "N/A",
            "disk": "N/A",
            "net": "N/A",
            "gpu": "N/A",
        })
    return rows


def _registered_android_lan_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    try:
        import engel_remote_worker_link_manager as link_mgr
        state = link_mgr.link_status()
    except Exception:
        state = {}
    identity = state.get("paired_phone_identity") if isinstance(state, dict) else None
    receiver_running = bool(state.get("receiver_running")) if isinstance(state, dict) else False
    last_seen = str(state.get("last_seen_utc") or "") if isinstance(state, dict) else ""
    host = str(state.get("host") or "0.0.0.0") if isinstance(state, dict) else "0.0.0.0"
    port = str(state.get("port") or "8765") if isinstance(state, dict) else "8765"
    if receiver_running or last_seen or isinstance(identity, dict):
        worker_id = str((identity or {}).get("worker_id") or "android_remote_worker")
        remote = str((identity or {}).get("remote_address") or f"{host}:{port}")
        rows.append({
            "label": "Android Remote Worker WiFi/LAN",
            "serial": remote,
            "workers": worker_id,
            "status": "WiFi/LAN paired or receiver ready",
            "cpu": "N/A",
            "ram": "N/A",
            "disk": "N/A",
            "net": f"{host}:{port}",
            "gpu": "N/A",
        })
    else:
        rows.append({
            "label": "Android Remote Worker WiFi/LAN",
            "serial": f"{host}:{port}",
            "workers": "pair from phone or future device",
            "status": "future / WiFi-LAN not paired",
            "cpu": "N/A",
            "ram": "N/A",
            "disk": "N/A",
            "net": "N/A",
            "gpu": "N/A",
        })
    return rows


def _latest_windows_sub_engel_checkin() -> dict:
    checkin_dir = ENGEL_APP_ROOT / "remote_nodes" / "windows_sub_engel" / "checkins"
    try:
        paths = sorted(checkin_dir.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
    except Exception:
        return {}
    for path in paths:
        data = _read_local_json(path)
        if data:
            return data
    return {}


def _windows_sub_engel_registry_details() -> tuple[str, list[str]]:
    checkin = _latest_windows_sub_engel_checkin()
    node = checkin.get("node") if isinstance(checkin.get("node"), dict) else {}
    network = checkin.get("network") if isinstance(checkin.get("network"), dict) else {}
    ready = _read_local_json(ENGEL_APP_ROOT / "runtime" / "windows_sub_engel_bootstrap" / "latest_node_ready.json")
    hostname = str(
        node.get("hostname")
        or node.get("computer_name")
        or ready.get("computer_name")
        or ""
    ).strip()
    ips: list[str] = []
    for values in (
        node.get("ip_addresses"),
        network.get("ip_addresses"),
        ready.get("node_ip"),
        ready.get("remote_addr"),
    ):
        if isinstance(values, str):
            values = [values]
        if isinstance(values, list):
            for value in values:
                text = str(value).strip()
                if text and text not in ips:
                    ips.append(text)
    return hostname, ips


def _registered_sub_engel_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    session_paths = [
        ENGEL_APP_ROOT / "remote_nodes" / "sub_engel" / "session.json",
        ENGEL_APP_ROOT / "remote_nodes" / "windows_sub_engel" / "session.json",
    ]
    for path in session_paths:
        session = _read_local_json(path)
        if not session:
            continue
        node_kind = str(session.get("node_kind") or session.get("role") or "Sub-Engel Node")
        hostname = str(session.get("hostname") or session.get("computer_name") or "").strip()
        ips: list[str] = []
        for value in session.get("last_known_ips") or session.get("local_ips") or []:
            text = str(value).strip()
            if text:
                ips.append(text)
        if path.parent.name == "windows_sub_engel":
            registry_hostname, registry_ips = _windows_sub_engel_registry_details()
            hostname = hostname or registry_hostname
            for ip in registry_ips:
                if ip not in ips:
                    ips.append(ip)
        label = f"{node_kind} / {hostname}" if hostname else node_kind
        url = str(session.get("url") or path.parent.name)
        transport = str(session.get("connection_family") or "LAN/WiFi")
        rows.append({
            "label": label,
            "serial": url,
            "workers": "allowed actions: " + str(len(session.get("allowed_actions", []))),
            "status": f"paired {transport} diagnostics session stored",
            "cpu": "N/A",
            "ram": "N/A",
            "disk": "N/A",
            "net": ", ".join(ips) if ips else "N/A",
            "gpu": "N/A",
        })
    if not rows:
        rows.append({
            "label": "Sub-Engel Node",
            "serial": "future WiFi/LAN or hardwire pair-gated node slot",
            "workers": "pair first for bounded diagnostics",
            "status": "future / WiFi-LAN or hardwire not paired",
            "cpu": "N/A",
            "ram": "N/A",
            "disk": "N/A",
            "net": "N/A",
            "gpu": "N/A",
        })
    return rows


def _get_connected_device_stats() -> list[dict[str, str]]:
    """Read-only stats for connected devices plus registered future slots."""
    devices: list[dict[str, str]] = []
    connected_serials: set[str] = set()
    try:
        import engel_adb_worker_manager as adb
        if not getattr(adb, "_ADB").exists():
            devices.extend(_registered_android_lan_rows())
            devices.extend(_registered_android_device_rows(connected_serials))
            devices.extend(_registered_sub_engel_rows())
            return devices
        serials = adb._connected_serials()
        connected_serials = set(serials)
        for serial in serials:
            label = getattr(adb, "_DEVICE_LABELS", {}).get(serial, serial)
            workers = adb._worker_on_device(serial)
            devices.append({
                "label": label,
                "serial": serial,
                "workers": ", ".join(workers) if workers else "no workers",
                "status": "connected via USB ADB",
                "cpu": _format_android_cpu(serial, adb._adb),
                "ram": _format_android_ram(serial, adb._adb),
                "disk": _format_android_disk(serial, adb._adb),
                "net": _format_android_net(serial, adb._adb),
                "gpu": "N/A",
            })
    except Exception:
        pass
    devices.extend(_registered_android_lan_rows())
    devices.extend(_registered_android_device_rows(connected_serials))
    devices.extend(_registered_sub_engel_rows())
    return devices


# Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬ Card frame helper Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
def make_card() -> QFrame:
    f = QFrame()
    f.setObjectName("card")
    f.setStyleSheet(f"QFrame#card {{ background: {CARD}; border: 1px solid {BORDER}; border-radius: 6px; }}")
    return f


def make_label(text: str, cls: str = "", color: str = TEXT, bold: bool = False, size: int = 9) -> QLabel:
    lbl = QLabel(text)
    style = f"color: {color}; font-size: {size}pt;"
    if bold:
        style += " font-weight: 700;"
    lbl.setStyleSheet(style)
    return lbl


# Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬ System Monitor Panel Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
class SystemMonitorPanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background: {CARD}; border: 1px solid {BORDER}; border-radius: 6px;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        # Header
        hdr = QHBoxLayout()
        title = make_label("System Monitor", bold=True, size=10, color=TEXT)
        self.time_lbl = make_label("--:--:--", color=DIM, size=8)
        hdr.addWidget(title)
        hdr.addStretch()
        hdr.addWidget(self.time_lbl)
        layout.addLayout(hdr)

        layout.addWidget(self._divider())

        # Stats grid
        self.cpu_val  = make_label("--",  color=GREEN, bold=True)
        self.ram_val  = make_label("--",  color=AMBER, bold=True)
        self.disk_val = make_label("--",  color=BLUE,  bold=True)
        self.net_val  = make_label("--",  color=PURPLE, bold=True)
        self.gpu_val  = make_label("--",  color=GREEN, bold=True)
        self.host_val = make_label("--",  color=DIM, size=8)
        self.os_val   = make_label("--",  color=DIM, size=8)
        self.disk_unit_lbl = make_label("--", color=DIM, size=7)

        grid = QGridLayout()
        grid.setSpacing(4)
        grid.setColumnStretch(1, 1)
        for row, (key, val, unit) in enumerate([
            ("CPU",  self.cpu_val,  "load"),
            ("RAM",  self.ram_val,  "used"),
            ("Disk", self.disk_val, self.disk_unit_lbl),
            ("Net",  self.net_val,  "sent"),
            ("GPU",  self.gpu_val,  "load"),
        ]):
            grid.addWidget(make_label(key, color=DIM, size=8), row, 0)
            grid.addWidget(val, row, 1)
            if isinstance(unit, str):
                grid.addWidget(make_label(unit, color=DIM, size=7), row, 2)
            else:
                grid.addWidget(unit, row, 2)
        layout.addLayout(grid)

        layout.addWidget(self._divider())
        layout.addWidget(self.host_val)
        layout.addWidget(self.os_val)

        layout.addWidget(self._divider())
        self.devices_title = make_label("Connected / Future Devices", color=TEXT, bold=True, size=9)
        layout.addWidget(self.devices_title)

        self.devices_scroll = QScrollArea()
        self.devices_scroll.setWidgetResizable(True)
        self.devices_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.devices_scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self.devices_wrap = QWidget()
        self.devices_wrap.setStyleSheet("background: transparent;")
        self.devices_layout = QVBoxLayout(self.devices_wrap)
        self.devices_layout.setContentsMargins(0, 0, 0, 0)
        self.devices_layout.setSpacing(6)
        self.devices_scroll.setWidget(self.devices_wrap)
        layout.addWidget(self.devices_scroll, 1)

        # Auto-refresh
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(3000)
        self.refresh()

    def _divider(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet(f"color: {BORDER2}; background: {BORDER2}; max-height: 1px;")
        return line

    def refresh(self):
        s = _get_system_stats()
        self.time_lbl.setText(s.get("time", "--"))
        self.cpu_val.setText(s.get("cpu", "--"))
        self.ram_val.setText(s.get("ram", "--"))
        self.disk_val.setText(s.get("disk", "--"))
        self.disk_unit_lbl.setText(s.get("disk_root", "--"))
        self.gpu_val.setText(s.get("gpu", "--"))
        sent = s.get("net_sent", "--")
        recv = s.get("net_recv", "--")
        self.net_val.setText(f"{sent}/{recv}")
        self.host_val.setText(s.get("host", ""))
        self.os_val.setText(s.get("os", ""))
        self._refresh_devices()

    def _clear_device_rows(self):
        while self.devices_layout.count():
            item = self.devices_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _device_metric_row(self, parent: QVBoxLayout, label: str, value: str, color: str = TEXT):
        row = QHBoxLayout()
        row.setSpacing(4)
        key = make_label(label, color=DIM, size=7)
        key.setFixedWidth(30)
        val = make_label(value, color=color, size=8, bold=True)
        val.setWordWrap(True)
        row.addWidget(key)
        row.addWidget(val, 1)
        parent.addLayout(row)

    def _device_block(self, device: dict[str, str]) -> QFrame:
        block = QFrame()
        block.setStyleSheet(
            f"QFrame {{ background: {CARD2_GLASS}; border: 1px solid {BORDER2}; border-radius: 4px; }}"
        )
        box = QVBoxLayout(block)
        box.setContentsMargins(8, 6, 8, 6)
        box.setSpacing(3)
        title = make_label(device.get("label", "Device"), color=GREEN, size=8, bold=True)
        title.setWordWrap(True)
        box.addWidget(title)
        status_color = GREEN if "connected" in device.get("status", "") or "paired" in device.get("status", "") else DIM
        status = make_label(device.get("status", ""), color=status_color, size=7, bold=True)
        status.setWordWrap(True)
        box.addWidget(status)
        serial = make_label(device.get("serial", ""), color=DIM, size=7)
        serial.setWordWrap(True)
        box.addWidget(serial)
        workers = make_label(device.get("workers", ""), color=BLUE, size=7)
        workers.setWordWrap(True)
        box.addWidget(workers)
        self._device_metric_row(box, "CPU", device.get("cpu", "N/A"), GREEN)
        self._device_metric_row(box, "RAM", device.get("ram", "N/A"), AMBER)
        self._device_metric_row(box, "Disk", device.get("disk", "N/A"), BLUE)
        self._device_metric_row(box, "Net", device.get("net", "N/A"), PURPLE)
        self._device_metric_row(box, "GPU", device.get("gpu", "N/A"), DIM)
        return block

    def _refresh_devices(self):
        self._clear_device_rows()
        devices = _get_connected_device_stats()
        if not devices:
            empty = make_label("No worker devices connected.", color=DIM, size=8)
            empty.setWordWrap(True)
            self.devices_layout.addWidget(empty)
            self.devices_layout.addStretch()
            return
        for device in devices:
            self.devices_layout.addWidget(self._device_block(device))
        self.devices_layout.addStretch()


# Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬ Goal Queue Panel Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
class GoalQueuePanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background: {CARD}; border: 1px solid {BORDER}; border-radius: 6px;")
        self._tasks: list[dict] = []
        self._project = "VantaMoth"
        self._load()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        # Header
        hdr = QHBoxLayout()
        hdr.addWidget(make_label("Goal Queue", bold=True, size=10))
        hdr.addStretch()
        self.pct_lbl = make_label("0%", color=GREEN, bold=True)
        hdr.addWidget(self.pct_lbl)
        layout.addLayout(hdr)

        # Project row
        proj_row = QHBoxLayout()
        proj_row.addWidget(make_label(">", color=GREEN))
        self.proj_lbl = make_label(self._project, color=TEXT)
        proj_row.addWidget(self.proj_lbl)
        proj_row.addStretch()
        layout.addLayout(proj_row)

        # Add task input
        add_row = QHBoxLayout()
        add_row.addWidget(make_label("+", color=DIM))
        self.task_input = QLineEdit()
        self.task_input.setPlaceholderText("Add task...")
        self.task_input.returnPressed.connect(self._add_task)
        add_row.addWidget(self.task_input)
        add_btn = QPushButton("+")
        add_btn.setFixedWidth(32)
        add_btn.clicked.connect(self._add_task)
        add_row.addWidget(add_btn)
        layout.addLayout(add_row)

        # Progress bar
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(6)
        layout.addWidget(self.progress)

        # Next / Blocker meta
        meta_layout = QGridLayout()
        meta_layout.setSpacing(2)
        meta_layout.addWidget(make_label("Next",    color=DIM, size=8), 0, 0)
        self.next_lbl = make_label("Build Company", color=TEXT, bold=True)
        meta_layout.addWidget(self.next_lbl, 0, 1)
        meta_layout.addWidget(make_label("Blocker", color=DIM, size=8), 1, 0)
        self.blocker_lbl = make_label("None", color=GREEN)
        meta_layout.addWidget(self.blocker_lbl, 1, 1)
        layout.addLayout(meta_layout)

        # Active header
        active_row = QHBoxLayout()
        active_row.addWidget(make_label("Active", bold=True, size=9))
        active_row.addStretch()
        self.active_lbl = make_label("0/1", color=DIM, size=8)
        active_row.addWidget(self.active_lbl)
        layout.addLayout(active_row)

        # Task list
        self.task_list = QListWidget()
        self.task_list.setStyleSheet(
            f"QListWidget {{ background: {BG}; border: 1px solid {BORDER}; border-radius: 4px; }}"
            f"QListWidget::item {{ padding: 4px 6px; color: {TEXT}; }}"
            f"QListWidget::item:selected {{ background: #1a2a1a; }}"
        )
        self.task_list.setFixedHeight(100)
        self.task_list.itemDoubleClicked.connect(self._toggle_task)
        layout.addWidget(self.task_list)
        layout.addStretch()
        self._refresh()

    # Ã¢â€â‚¬Ã¢â€â‚¬ persistence Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
    def _load(self):
        try:
            if GOAL_QUEUE_FILE.exists():
                data = json.loads(GOAL_QUEUE_FILE.read_text(encoding="utf-8"))
                self._project = data.get("project", "VantaMoth")
                self._tasks   = data.get("tasks", [])
        except Exception:
            pass

    def _save(self):
        try:
            GOAL_QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
            GOAL_QUEUE_FILE.write_text(
                json.dumps({"project": self._project, "tasks": self._tasks}, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass

    def _add_task(self):
        text = self.task_input.text().strip()
        if not text:
            return
        self._tasks.append({"title": text, "status": "active"})
        self.task_input.clear()
        self._save()
        self._refresh()

    def _toggle_task(self, item: QListWidgetItem):
        row = self.task_list.row(item)
        if 0 <= row < len(self._tasks):
            t = self._tasks[row]
            t["status"] = "active" if t["status"] == "done" else "done"
            self._save()
            self._refresh()

    def _refresh(self):
        total = len(self._tasks)
        done  = sum(1 for t in self._tasks if t["status"] == "done")
        pct   = int(done / total * 100) if total else 0
        self.pct_lbl.setText(f"{pct}%")
        self.progress.setValue(pct)
        active = [t for t in self._tasks if t["status"] == "active"]
        pending = [t for t in self._tasks if t["status"] not in ("done",)]
        self.next_lbl.setText(pending[0]["title"] if pending else "Build Company")
        self.blocker_lbl.setText("None")
        self.active_lbl.setText(f"{len(active)}/{max(1, total)}")
        self.task_list.clear()
        for t in self._tasks:
            icon = "[x] " if t["status"] == "done" else "[ ] "
            item = QListWidgetItem(icon + t["title"])
            if t["status"] == "done":
                item.setForeground(QColor(DIM))
            self.task_list.addItem(item)


# Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬ Model load worker thread Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
class _ModelLoadWorker(QThread):
    finished = pyqtSignal(str)   # emits result text

    def __init__(self, slug: str):
        super().__init__()
        self._slug = slug

    def run(self):
        try:
            _ensure_project_on_path()
            from engel_local_model_manager import render_models_load
            result = render_models_load(self._slug)
            self.finished.emit(result)
        except Exception as exc:
            self.finished.emit(f"ERROR: {exc}")


# Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬ Local Model Panel Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
class ModelRoutePanel(QFrame):
    """Live model selector backed by engel_local_model_manager.
    Model loading runs in a QThread so the GUI never freezes."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background: {CARD}; border: 1px solid {BORDER}; border-radius: 6px;")
        self._models: list[dict] = []
        self._load_thread: Optional[_ModelLoadWorker] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(5)

        # Header
        hdr = QHBoxLayout()
        hdr.addWidget(make_label("Local Models", bold=True, size=10))
        hdr.addStretch()
        self.active_dot = make_label("*", color=DIM, size=9)
        hdr.addWidget(self.active_dot)
        layout.addLayout(hdr)

        layout.addWidget(self._divider())

        # Active model display
        layout.addWidget(make_label("Active", color=DIM, size=8))
        self.active_lbl = make_label("0.5B seed (default)", color=DIM, bold=True, size=8)
        self.active_lbl.setWordWrap(True)
        layout.addWidget(self.active_lbl)

        # Model picker
        layout.addWidget(make_label("Switch model", color=DIM, size=8))
        self.model_combo = QComboBox()
        self.model_combo.setToolTip("Select a GGUF model to load")
        layout.addWidget(self.model_combo)

        # Action buttons
        btn_row = QHBoxLayout()
        self.load_btn = QPushButton("Load")
        self.load_btn.setFixedHeight(22)
        self.load_btn.clicked.connect(self._load_model)
        btn_row.addWidget(self.load_btn)
        self.unload_btn = QPushButton("Unload")
        self.unload_btn.setFixedHeight(22)
        self.unload_btn.clicked.connect(self._unload_model)
        btn_row.addWidget(self.unload_btn)
        layout.addLayout(btn_row)

        layout.addWidget(self._divider())

        # Status line
        self.status_lbl = make_label("No model loaded", color=DIM, size=8)
        self.status_lbl.setWordWrap(True)
        layout.addWidget(self.status_lbl)
        layout.addStretch()

        self._populate_models()
        self._refresh_status()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh_status)
        self._timer.start(5000)

    def _divider(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet(f"color: {BORDER2}; background: {BORDER2}; max-height: 1px;")
        return line

    def _populate_models(self):
        try:
            _ensure_project_on_path()
            from engel_local_model_manager import _find_gguf_files
            self._models = _find_gguf_files()
        except Exception:
            self._models = []
        self.model_combo.clear()
        for m in self._models:
            self.model_combo.addItem(f"{m['slug']}  ({m['size_gb']}GB)", userData=m['slug'])
        if not self._models:
            self.model_combo.addItem("(no models found)")

    def _refresh_status(self):
        try:
            import engel_local_model_manager as mgr
            if mgr.get_active_model() is not None:
                self.active_dot.setStyleSheet(f"color: {GREEN};")
                slug = mgr._LOADED_MODEL_SLUG or "loaded"
                self.active_lbl.setText(slug)
                self.active_lbl.setStyleSheet(f"color: {GREEN}; font-weight: 700; font-size: 8pt;")
                try:
                    size_gb = round(Path(mgr._LOADED_MODEL_PATH).stat().st_size / 1e9, 2)
                    self.status_lbl.setText(f"Loaded - {size_gb}GB")
                except Exception:
                    self.status_lbl.setText("Loaded")
                self.status_lbl.setStyleSheet(f"color: {GREEN}; font-size: 8pt;")
            else:
                self.active_dot.setStyleSheet(f"color: {DIM};")
                self.active_lbl.setText("0.5B seed (default)")
                self.active_lbl.setStyleSheet(f"color: {DIM}; font-size: 8pt;")
                self.status_lbl.setText("No model loaded")
                self.status_lbl.setStyleSheet(f"color: {DIM}; font-size: 8pt;")
        except Exception as exc:
            self.status_lbl.setText(f"err: {exc}")

    def _load_model(self):
        if self._load_thread and self._load_thread.isRunning():
            return  # already loading
        idx = self.model_combo.currentIndex()
        slug = self.model_combo.itemData(idx)
        if not slug:
            return
        self.load_btn.setEnabled(False)
        self.status_lbl.setText("Loading... (may take 10-30s for large models)")
        self.status_lbl.setStyleSheet(f"color: {AMBER}; font-size: 8pt;")
        self._load_thread = _ModelLoadWorker(slug)
        self._load_thread.finished.connect(self._on_load_done)
        self._load_thread.start()

    def _on_load_done(self, result: str):
        self.load_btn.setEnabled(True)
        if "ERROR" in result:
            self.status_lbl.setText("Load failed - see logs")
            self.status_lbl.setStyleSheet(f"color: {RED}; font-size: 8pt;")
        else:
            self._refresh_status()

    def _unload_model(self):
        if self._load_thread and self._load_thread.isRunning():
            return
        try:
            from engel_local_model_manager import render_models_unload
            render_models_unload()
            self._refresh_status()
        except Exception as exc:
            self.status_lbl.setText(f"unload err: {exc}")


# Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬ Chat query worker thread Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
class _ChatWorker(QThread):
    finished = pyqtSignal(str)

    def __init__(self, text: str, mode: str):
        super().__init__()
        self._text = text
        self._mode = mode  # "auto" | "local"

    def run(self):
        try:
            _ensure_project_on_path()
            if self._mode == "local":
                from engel_offline_seed_llm import (
                    offline_seed_llm_gate_enabled,
                    run_offline_seed_llm_for_companion_chat,
                )
                if not offline_seed_llm_gate_enabled():
                    self.finished.emit("[Local model gate is off. Set ENGEL_OFFLINE_SEED_LLM_ENABLED=1]")
                    return
                resp = run_offline_seed_llm_for_companion_chat(self._text)
                reply = resp.response or "(empty response)"
            else:
                from engel_communication_router import route_companion_text_or_command
                result = route_companion_text_or_command(self._text, context="DESKTOP_V2")
                reply = result.response or "(no response)"
            self.finished.emit(reply)
        except Exception as exc:
            self.finished.emit(f"(error: {exc})")


# Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬ Agent Chat Panel Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
class AgentChatPanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background: {CARD}; border: 1px solid {BORDER}; border-radius: 6px;")
        self._mode = "auto"  # "auto" | "local"
        self._chat_thread: Optional[_ChatWorker] = None
        self._pending_meeting_order_id: Optional[str] = None
        self._pending_user_text: Optional[str] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        # Header
        hdr = QHBoxLayout()
        hdr.addWidget(make_label("Agent Chat", bold=True, size=10))
        hdr.addStretch()
        self.status_dot = make_label("* Online", color=GREEN, size=8)
        hdr.addWidget(self.status_dot)
        layout.addLayout(hdr)

        # Transcript
        self.transcript = QTextEdit()
        self.transcript.setReadOnly(True)
        self.transcript.setMinimumHeight(120)
        self.transcript.setStyleSheet(
            f"QTextEdit {{ background: {BG}; border: 1px solid {BORDER}; border-radius: 4px; color: {TEXT}; padding: 6px; }}"
        )
        self.transcript.setPlainText("Engel AI online. What do you want to work on?")
        layout.addWidget(self.transcript, 1)

        # Input row
        input_row = QHBoxLayout()
        self.msg_input = QLineEdit()
        self.msg_input.setPlaceholderText("Message Engel...")
        self.msg_input.returnPressed.connect(self._send)
        input_row.addWidget(self.msg_input, 1)
        self.send_btn = QPushButton("Send")
        self.send_btn.setObjectName("send_btn")
        self.send_btn.clicked.connect(self._send)
        input_row.addWidget(self.send_btn)
        layout.addLayout(input_row)

        # Mode buttons
        mode_row = QHBoxLayout()
        self.auto_btn = QPushButton("Auto")
        self.auto_btn.setFixedHeight(22)
        self.auto_btn.setToolTip("Route through all Engel commands + local LLM fallback")
        self.auto_btn.clicked.connect(lambda: self._set_mode("auto"))
        mode_row.addWidget(self.auto_btn)

        self.local_btn = QPushButton("Local")
        self.local_btn.setFixedHeight(22)
        self.local_btn.setToolTip("Force local GGUF model only (offline)")
        self.local_btn.clicked.connect(lambda: self._set_mode("local"))
        mode_row.addWidget(self.local_btn)

        self.stop_btn = QPushButton("Clear")
        self.stop_btn.setFixedHeight(22)
        self.stop_btn.setToolTip("Clear transcript")
        self.stop_btn.clicked.connect(self._clear)
        mode_row.addWidget(self.stop_btn)
        layout.addLayout(mode_row)

        self._set_mode("auto")

    def _set_mode(self, mode: str):
        self._mode = mode
        if mode == "auto":
            self.auto_btn.setStyleSheet(f"background: {GREEN}; color: {BG}; font-weight: 900;")
            self.local_btn.setStyleSheet("")
            self.status_dot.setText("* Auto")
            self.status_dot.setStyleSheet(f"color: {GREEN}; font-size: 8pt;")
        else:
            self.local_btn.setStyleSheet(f"background: {BLUE}; color: {BG}; font-weight: 900;")
            self.auto_btn.setStyleSheet("")
            self.status_dot.setText("* Local")
            self.status_dot.setStyleSheet(f"color: {BLUE}; font-size: 8pt;")

    def _clear(self):
        self.transcript.setPlainText("Engel AI online. What do you want to work on?")

    def _send(self):
        text = self.msg_input.text().strip()
        if not text:
            return
        if self._chat_thread and self._chat_thread.isRunning():
            return  # busy
        self.msg_input.clear()
        self.transcript.append(f"\nYou: {text}")

        # Local chat-command intercept Ã¢â‚¬â€ open the Meeting Room directly
        # rather than routing through the provider/bridge.
        normalised = text.lower().strip().rstrip("?").strip()
        meeting_phrases = {
            "meeting room",
            "open meeting room",
            "agent meeting room",
            "open agent meeting room",
            "where is the meeting room",
            "where is the agent meeting room",
            "show meeting room",
            "launch meeting room",
        }
        if normalised in meeting_phrases:
            self.transcript.append(
                "\nEngel: Meeting Room stays display-only. Use the top button to view it; "
                "chat input will not open extra windows."
            )
            return

        system_action = ""
        try:
            _ensure_project_on_path()
            from engel_ui_system_actions import classify_ui_system_action, run_ui_system_action

            system_action = classify_ui_system_action(text)
            system_result = run_ui_system_action(text)
        except Exception as exc:
            system_result = {
                "accepted": False,
                "summary": f"System connection action failed ({type(exc).__name__}: {exc})",
            }
        if system_action and not system_result.get("accepted"):
            self.transcript.append(
                "\nEngel: " + str(system_result.get("summary") or "System connection action failed.")
            )
            return
        if system_result.get("accepted"):
            self.transcript.append("\nEngel: " + str(system_result.get("summary") or "System action finished."))
            return

        self._pending_meeting_order_id = None
        self._pending_user_text = text
        meeting_note = self._stage_order_to_meeting_room(text)
        if meeting_note:
            self.transcript.append(f"\nMeeting Room: {meeting_note}")

        self.send_btn.setEnabled(False)
        self._chat_thread = _ChatWorker(text, self._mode)
        self._chat_thread.finished.connect(self._on_reply)
        self._chat_thread.start()

    def _stage_order_to_meeting_room(self, text: str) -> str:
        try:
            from engel_agent_meeting_room import submit_order_from_engel_main_ui
            result = submit_order_from_engel_main_ui(text, source="Desktop V2 Agent Chat")
        except Exception as exc:
            return f"order handoff failed ({type(exc).__name__}: {exc})"
        if not result.get("accepted"):
            return ""
        self._pending_meeting_order_id = str(result.get("order_id") or "")
        return str(result.get("summary") or "order staged")

    def _format_executable_result(self, result: dict) -> str:
        files = [str(path) for path in result.get("files", []) if str(path)]
        lines = [
            "",
            "Engel Result: " + str(result.get("summary") or "Created local artifact."),
            "Folder: " + str(result.get("artifact_dir") or ""),
        ]
        for path in files[:6]:
            lines.append("- " + path)
        return "\n".join(lines)

    def _on_reply(self, reply: str):
        self.send_btn.setEnabled(True)
        reply = _clean_chat_reply_for_ui(reply)
        order_id = self._pending_meeting_order_id
        user_text = self._pending_user_text
        self._pending_meeting_order_id = None
        self._pending_user_text = None
        if order_id and _is_unhelpful_chat_reply(reply):
            reply = _local_bridge_reply_for_meeting_order(user_text or "")
        meeting_summary = ""
        returned_previews = []
        if order_id:
            try:
                from engel_agent_meeting_room import complete_order_from_engel_main_ui
                result = complete_order_from_engel_main_ui(
                    order_id,
                    reply,
                    source="Desktop V2 Agent Chat",
                )
                if result.get("accepted"):
                    meeting_summary = str(result.get("summary") or "")
                    previews = result.get("returned_previews")
                    if isinstance(previews, list):
                        returned_previews = [str(item) for item in previews]
            except Exception as exc:
                self.transcript.append(f"\nMeeting Room: result handoff failed ({type(exc).__name__}: {exc})")
        if returned_previews:
            preview_text = "\n- ".join(returned_previews[:3])
            reply = (
                "Done. I routed this through the Agent Meeting Room and got the result back.\n"
                f"- {preview_text}"
            )
        elif order_id and _is_unhelpful_chat_reply(reply):
            reply = (
                "I routed this through the Agent Meeting Room and assigned the matching agent station. "
                "The work packet is recorded for the selected agent/device path."
            )
        self.transcript.append(f"\nEngel: {reply}")
        if meeting_summary:
            self.transcript.append(f"\nMeeting Room: {meeting_summary}")
        if order_id and user_text:
            try:
                from engel_ui_executable_results import execute_ui_result_request
                artifact_result = execute_ui_result_request(
                    user_text,
                    meeting_summary=meeting_summary,
                    returned_previews=returned_previews,
                )
                if artifact_result.get("accepted"):
                    self.transcript.append(self._format_executable_result(artifact_result))
            except Exception as exc:
                self.transcript.append(f"\nEngel Result: artifact creation failed ({type(exc).__name__}: {exc})")


# Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬ Route Browser Panel Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
