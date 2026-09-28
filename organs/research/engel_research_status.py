"""Engel Research Status — read-only views of research brain and overnight loop.

Wraps engel_research_brain_v2 public functions and the overnight loop status
file. All calls are read-only; no writes, no mutations, no research triggered.
"""
from __future__ import annotations

from pathlib import Path

_APP_ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
_REPORTS_DIR = _APP_ROOT / "reports"
_RESEARCH_DIR = _REPORTS_DIR / "research"
_OVERNIGHT_DIR = _REPORTS_DIR / "overnight"
_MEMORY_DIR = _APP_ROOT / "memory"
_LOOP_STATUS_FILE = _REPORTS_DIR / "OVERNIGHT_RESEARCH_LOOP_STATUS.md"
_LOOP_PID_FILE = _MEMORY_DIR / "overnight_research_loop.pid"
_LOOP_LOCK_FILE = _MEMORY_DIR / "overnight_research_loop.lock"
_STOP_FILE = _MEMORY_DIR / "overnight_research_loop.stop"


def _rb():
    """Import research brain; cache on first call."""
    import engel_research_brain_v2 as rb
    return rb


def _safe_call(func_name: str) -> str:
    try:
        rb = _rb()
        fn = getattr(rb, func_name)
        return str(fn())
    except Exception as exc:
        return f"[{func_name} unavailable: {exc}]"


def _read_file(path: Path, max_chars: int = 3000) -> str:
    if not path.exists():
        return f"[file not found: {path}]"
    try:
        text = path.read_text(encoding="utf-8", errors="replace").strip()
        if len(text) > max_chars:
            text = text[:max_chars] + "\n\n[TRUNCATED]"
        return text
    except Exception as exc:
        return f"[read error: {exc}]"


# ─── Research Brain ───────────────────────────────────────────────────────────

def render_research_brain_status() -> str:
    return _safe_call("research_brain_status")


def render_research_queue_status() -> str:
    return _safe_call("research_queue_status")


def render_research_next_best_topic() -> str:
    return _safe_call("research_next_best_topic")


def render_research_digest_latest() -> str:
    return _safe_call("research_digest_latest")


def render_research_toggle_status() -> str:
    return _safe_call("research_toggle_status")


def render_hive_mind_status() -> str:
    return _safe_call("hive_mind_status")


def render_worker_ants_status() -> str:
    return _safe_call("worker_ants_status")


def render_colony_status() -> str:
    return _safe_call("colony_status")


def render_colony_safety_status() -> str:
    return _safe_call("colony_safety_status")


def render_swarm_trails_status() -> str:
    return _safe_call("swarm_trails_status")


def render_learning_proposals_status() -> str:
    return _safe_call("learning_proposals_review")


def render_lesson_candidates_status() -> str:
    return _safe_call("lesson_candidates_status")


def render_colony_simulation_status() -> str:
    return _safe_call("colony_simulation_status")


# ─── Overnight Loop ───────────────────────────────────────────────────────────

def _loop_pid() -> int | None:
    try:
        pid_str = _LOOP_PID_FILE.read_text(encoding="utf-8").strip()
        pid = int(pid_str)
        import os
        os.kill(pid, 0)
        return pid
    except Exception:
        return None


def render_overnight_loop_status() -> str:
    running = _loop_pid()
    stop_pending = _STOP_FILE.exists()

    lines = [
        "# Engel Overnight Research Loop — Status",
        "",
        f"Loop running:   {'YES (PID ' + str(running) + ')' if running else 'NO'}",
        f"Stop pending:   {'YES' if stop_pending else 'NO'}",
        f"Lock file:      {'present' if _LOOP_LOCK_FILE.exists() else 'absent'}",
        "",
        "Status file:",
        "",
    ]
    lines.append(_read_file(_LOOP_STATUS_FILE))
    lines += [
        "",
        "To start loop:  python engel_overnight_loop.py",
        "To stop loop:   touch memory/overnight_research_loop.stop",
        "To clean stale: engel overnight loop cleanup",
    ]
    return "\n".join(lines)


def render_overnight_loop_cleanup() -> str:
    """Remove stale lock/stop/pid files when the loop is not running."""
    running = _loop_pid()
    if running:
        return (
            f"# Overnight Loop Cleanup — SKIPPED\n\n"
            f"Loop is still running (PID {running}). Stop it first."
        )
    removed: list[str] = []
    skipped: list[str] = []
    for path in (_LOOP_LOCK_FILE, _STOP_FILE, _LOOP_PID_FILE):
        if path.exists():
            try:
                path.unlink()
                removed.append(path.name)
            except Exception as exc:
                skipped.append(f"{path.name}: {exc}")
    lines = ["# Overnight Loop Cleanup"]
    if removed:
        lines += ["", "Removed:"] + [f"  - {n}" for n in removed]
    if skipped:
        lines += ["", "Could not remove:"] + [f"  - {n}" for n in skipped]
    if not removed and not skipped:
        lines += ["", "Nothing to remove — loop state is already clean."]
    return "\n".join(lines)


def render_research_overview() -> str:
    """Compact multi-section overview — brain + queue + loop in one view."""
    brain = _safe_call("research_brain_status")
    queue = _safe_call("research_queue_status")
    toggle = _safe_call("research_toggle_status")
    loop_running = _loop_pid()

    lines = [
        "# Engel Research Overview",
        "",
        f"Overnight loop: {'RUNNING' if loop_running else 'stopped'}",
        "",
        "─" * 50,
        "## Research Brain Status",
        "",
        brain[:600] + ("..." if len(brain) > 600 else ""),
        "",
        "─" * 50,
        "## Queue Status",
        "",
        queue[:600] + ("..." if len(queue) > 600 else ""),
        "",
        "─" * 50,
        "## Toggle Status",
        "",
        toggle[:300] + ("..." if len(toggle) > 300 else ""),
    ]
    return "\n".join(lines)
