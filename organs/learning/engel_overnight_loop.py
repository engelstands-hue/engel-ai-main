"""
Engel overnight research loop.

Explicit local orchestrator for Research ON / Overnight Loop ON. It only starts
the approved local runner script, writes loop status, sleeps between cycles, and
exits when the stop flag appears.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

from engel_overnight_support import (
    APP_ROOT,
    MEMORY_DIR,
    REPORTS_DIR,
    OVERNIGHT_DIR,
    ensure_base_dirs as _ensure_dirs,
    format_now as _now,
    pid_alive as _pid_alive,
    read_utf8_optional as _read,
    write_utf8 as _write,
)

RUNNER_SCRIPT = APP_ROOT / "engel_overnight_runner.py"
LOOP_PID_FILE = MEMORY_DIR / "overnight_research_loop.pid"
STOP_FILE = MEMORY_DIR / "overnight_research_loop.stop"
LOOP_LOCK_FILE = MEMORY_DIR / "overnight_research_loop.lock"
LOOP_STATUS_FILE = REPORTS_DIR / "OVERNIGHT_RESEARCH_LOOP_STATUS.md"
RUNNER_STATUS_FILE = OVERNIGHT_DIR / "OVERNIGHT_RUNNER_STATUS.md"

MIN_INTERVAL_SECONDS = 300
DEFAULT_INTERVAL_SECONDS = 1800
MAX_INTERVAL_SECONDS = 21600


def _acquire_lock() -> tuple[bool, str]:
    _ensure_dirs()
    if LOOP_LOCK_FILE.exists():
        owner = _read(LOOP_LOCK_FILE).strip()
        if owner.isdigit() and _pid_alive(int(owner)):
            return False, owner
        try:
            LOOP_LOCK_FILE.unlink()
        except Exception:
            return False, owner or "unknown"

    try:
        fd = os.open(str(LOOP_LOCK_FILE), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode("utf-8", errors="replace"))
        os.close(fd)
        return True, str(os.getpid())
    except FileExistsError:
        return False, _read(LOOP_LOCK_FILE).strip() or "unknown"


def _release_lock() -> None:
    try:
        if LOOP_LOCK_FILE.exists() and _read(LOOP_LOCK_FILE).strip() == str(os.getpid()):
            LOOP_LOCK_FILE.unlink()
    except Exception:
        pass


def _interval_seconds() -> int:
    raw = str(os.environ.get("ENGEL_OVERNIGHT_LOOP_INTERVAL_SECONDS", "")).strip()
    try:
        value = int(raw) if raw else DEFAULT_INTERVAL_SECONDS
    except Exception:
        value = DEFAULT_INTERVAL_SECONDS
    return max(MIN_INTERVAL_SECONDS, min(MAX_INTERVAL_SECONDS, value))


def _stop_requested() -> bool:
    return STOP_FILE.exists()


def _write_status(
    *,
    stage: str,
    cycle: str,
    runner_pid: str = "none",
    last_runner_exit: str = "none",
    detail: str = "",
    interval_seconds: int | None = None,
) -> None:
    if interval_seconds is None:
        interval_seconds = _interval_seconds()
    lines = [
        "# Overnight Research Loop Status",
        "",
        "Time: " + _now(),
        "Stage: " + stage,
        "Cycle: " + str(cycle),
        "Loop PID: " + str(os.getpid()),
        "Runner PID: " + str(runner_pid),
        "Last runner exit: " + str(last_runner_exit),
        "Sleep interval seconds: " + str(interval_seconds),
        "",
        "Detail:",
        detail if detail else "none",
        "",
        "Files:",
        "- PID: " + str(LOOP_PID_FILE),
        "- Stop flag: " + str(STOP_FILE),
        "- Status: " + str(LOOP_STATUS_FILE),
        "- Runner: " + str(RUNNER_SCRIPT),
        "- Runner status: " + str(RUNNER_STATUS_FILE),
        "",
        "Safety:",
        "- Explicit local loop process only.",
        "- Runs one staged local runner cycle per iteration.",
        "- No source fetch, source discovery, research brief, full-cycle, or auto-research route is called by the loop.",
        "- No provider/API/network call is made by the loop.",
        "- No web automation, login, clicking, sending, deleting, or external account action.",
        "- No trusted-memory mutation, source edit, queue mutation, digest/history mutation, or ALIVE_STATE mutation.",
    ]
    _write(LOOP_STATUS_FILE, "\n".join(lines))


def _runner_command() -> list[str]:
    return [sys.executable, str(RUNNER_SCRIPT)]


def _creationflags() -> int:
    try:
        return subprocess.CREATE_NO_WINDOW
    except Exception:
        return 0


def _run_one_cycle(cycle_number: int) -> int:
    _write_status(
        stage="RUNNING_RESEARCH",
        cycle=str(cycle_number),
        runner_pid="starting",
        detail="Starting one staged local runner cycle.",
    )
    proc = subprocess.Popen(
        _runner_command(),
        cwd=str(APP_ROOT),
        creationflags=_creationflags(),
    )
    _write_status(
        stage="RUNNING_RESEARCH",
        cycle=str(cycle_number),
        runner_pid=str(proc.pid),
        detail="Runner process started.",
    )

    while proc.poll() is None:
        if _stop_requested():
            try:
                proc.terminate()
            except Exception:
                pass
            try:
                proc.wait(timeout=10)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
            break
        time.sleep(2)

    return int(proc.returncode if proc.returncode is not None else -1)


def _sleep_until_next_cycle(interval_seconds: int, cycle_number: int, last_exit: int) -> None:
    _write_status(
        stage="SLEEPING",
        cycle=str(cycle_number),
        runner_pid="none",
        last_runner_exit=str(last_exit),
        detail="Runner cycle completed. Sleeping until next cycle or stop flag.",
        interval_seconds=interval_seconds,
    )
    remaining = interval_seconds
    while remaining > 0 and not _stop_requested():
        chunk = min(10, remaining)
        time.sleep(chunk)
        remaining -= chunk


def main() -> int:
    _ensure_dirs()

    ok, owner = _acquire_lock()
    if not ok:
        _write_status(
            stage="BLOCKED_DUPLICATE",
            cycle="none",
            runner_pid="none",
            last_runner_exit="none",
            detail="Duplicate loop start blocked. Existing owner PID: " + str(owner),
        )
        return 3

    try:
        _write(LOOP_PID_FILE, str(os.getpid()))

        if not RUNNER_SCRIPT.exists():
            _write_status(
                stage="ERROR",
                cycle="none",
                runner_pid="none",
                last_runner_exit="runner-missing",
                detail="Required runner script is missing: " + str(RUNNER_SCRIPT),
            )
            return 2

        if _stop_requested():
            _write_status(
                stage="OFF",
                cycle="none",
                runner_pid="none",
                last_runner_exit="stop-before-start",
                detail="Stop flag existed before the first cycle; no runner was started.",
            )
            return 0

        interval_seconds = _interval_seconds()
        cycle_number = 0
        _write_status(
            stage="STARTING",
            cycle="none",
            runner_pid="none",
            detail="Overnight research loop started.",
            interval_seconds=interval_seconds,
        )

        while not _stop_requested():
            cycle_number += 1
            last_exit = _run_one_cycle(cycle_number)
            if _stop_requested():
                break
            _sleep_until_next_cycle(interval_seconds, cycle_number, last_exit)

        _write_status(
            stage="OFF",
            cycle=str(cycle_number) if cycle_number else "none",
            runner_pid="none",
            last_runner_exit="stop-requested",
            detail="Stop flag detected. Overnight loop exited cleanly.",
            interval_seconds=interval_seconds,
        )
        return 0
    except Exception as exc:
        _write_status(
            stage="ERROR",
            cycle="unknown",
            runner_pid="none",
            last_runner_exit="loop-error",
            detail="Loop failed safely: " + str(exc),
        )
        return 1
    finally:
        _release_lock()


if __name__ == "__main__":
    raise SystemExit(main())
