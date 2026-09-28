"""Read-only view of the overnight research runner status file.

Never imports engel_overnight_runner directly — no side effects, no lock
acquisition, no process spawning. Safe to call from any route handler.
"""
from __future__ import annotations

from pathlib import Path

_APP_ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
_MEMORY_DIR = _APP_ROOT / "memory"
_OVERNIGHT_DIR = _MEMORY_DIR / "overnight"
_STATUS_FILE = _OVERNIGHT_DIR / "OVERNIGHT_RUNNER_STATUS.md"
_LOCK_FILE = _MEMORY_DIR / "overnight_runner_single_instance_v2runnera.lock"


def render_overnight_status() -> str:
    lines = ["# Engel Overnight Runner — Status View", ""]

    if not _STATUS_FILE.exists():
        lines += [
            "No status file found.",
            "",
            f"Expected: {_STATUS_FILE}",
            "",
            "The overnight runner has not been executed yet in this workspace.",
            "Run it manually:",
            "  python engel_overnight_runner.py",
        ]
        return "\n".join(lines)

    try:
        content = _STATUS_FILE.read_text(encoding="utf-8", errors="replace").strip()
    except Exception as exc:
        lines += [f"Could not read status file: {exc}"]
        return "\n".join(lines)

    lock_active = False
    if _LOCK_FILE.exists():
        try:
            pid_str = _LOCK_FILE.read_text(encoding="utf-8", errors="replace").strip()
            if pid_str.isdigit():
                import os
                try:
                    os.kill(int(pid_str), 0)
                    lock_active = True
                except OSError:
                    pass
        except Exception:
            pass

    lines += [
        "Lock file active: " + ("YES — runner may be running (PID " + _LOCK_FILE.read_text(encoding="utf-8", errors="replace").strip() + ")" if lock_active else "no"),
        "",
        "--- Status file contents ---",
        "",
        content,
    ]
    return "\n".join(lines)
