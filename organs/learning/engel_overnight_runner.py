"""
Engel overnight research runner.

One explicit, local, single-cycle runner for the Research ON gateway. This
runner delegates only to the staged Engel research-brain functions that are
already read-only or dry-run. It does not perform source fetching, web
discovery, provider calls, full-cycle research, learning apply, queue cleanup,
digest/history mutation, or ALIVE_STATE mutation.
"""

from __future__ import annotations

import os
import sys
import time
import traceback
from pathlib import Path

from engel_overnight_support import (
    APP_ROOT,
    MEMORY_DIR,
    OVERNIGHT_DIR,
    ensure_base_dirs as _ensure_dirs,
    format_now as _now,
    pid_alive as _pid_alive,
    read_utf8_optional as _read,
    stamp_compact as _stamp,
    write_utf8 as _write,
)

RUNNER_STATUS_FILE = OVERNIGHT_DIR / "OVERNIGHT_RUNNER_STATUS.md"
RUNNER_LOCK_FILE = MEMORY_DIR / "overnight_runner_single_instance_v2runnera.lock"

SAFE_CYCLE_NAME = "STAGED_LOCAL_RESEARCH_BRAIN"


def _trim(text: str, limit: int = 3500) -> str:
    text = str(text or "")
    if len(text) <= limit:
        return text
    return text[:limit] + "\n\n[TRUNCATED]"


def _acquire_lock() -> tuple[bool, str]:
    _ensure_dirs()
    if RUNNER_LOCK_FILE.exists():
        owner = _read(RUNNER_LOCK_FILE).strip()
        if owner.isdigit() and _pid_alive(int(owner)):
            return False, owner
        try:
            RUNNER_LOCK_FILE.unlink()
        except Exception:
            return False, owner or "unknown"

    try:
        fd = os.open(str(RUNNER_LOCK_FILE), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode("utf-8", errors="replace"))
        os.close(fd)
        return True, str(os.getpid())
    except FileExistsError:
        return False, _read(RUNNER_LOCK_FILE).strip() or "unknown"


def _release_lock() -> None:
    try:
        if RUNNER_LOCK_FILE.exists() and _read(RUNNER_LOCK_FILE).strip() == str(os.getpid()):
            RUNNER_LOCK_FILE.unlink()
    except Exception:
        pass


def _format_status(
    *,
    status: str,
    cycle_id: str,
    started: str,
    finished: str = "",
    elapsed_seconds: float | None = None,
    steps: list[tuple[str, str, str]] | None = None,
    detail: str = "",
) -> str:
    steps = steps or []
    lines = [
        "# Research Runner Status",
        "",
        "Time: " + _now(),
        "Status: " + status,
        "PID: " + str(os.getpid() if status.upper().startswith("RUNNING") else "none"),
        "Cycle ID: " + cycle_id,
        "Safe cycle: " + SAFE_CYCLE_NAME,
        "Started: " + started,
        "Finished: " + (finished if finished else "pending"),
        "Elapsed seconds: " + ("pending" if elapsed_seconds is None else str(round(elapsed_seconds, 3))),
        "",
        "Approval boundary:",
        "- No APPROVE token supplied by this runner.",
        "- No APPROVE_REPORT token supplied by this runner.",
        "- Exact approval-gated routes remain separate user commands.",
        "",
        "## Steps",
    ]

    if steps:
        for name, result, _text in steps:
            lines.append("- " + name + ": " + result)
    else:
        lines.append("- none yet")

    if detail:
        lines += ["", "## Detail", detail]

    if steps:
        lines += ["", "## Latest Step Output"]
        latest_name, _latest_result, latest_text = steps[-1]
        lines += ["Step: " + latest_name, "", "```text", _trim(latest_text), "```"]

    lines += [
        "",
        "Safety:",
        "- Existing staged local research-brain functions only.",
        "- No source fetch, source discovery, research brief, full-cycle, or auto-research route was called.",
        "- No provider/API/network call was made by this runner.",
        "- No web automation, login, clicking, sending, deleting, or external account action.",
        "- No trusted-memory mutation, source edit, queue mutation, digest/history mutation, or ALIVE_STATE mutation.",
    ]
    return "\n".join(lines)


def _call_step(name: str, func) -> tuple[str, str, str]:
    text = func()
    return name, "OK", str(text)


def run_cycle() -> int:
    _ensure_dirs()
    cycle_id = "overnight_runner_" + _stamp() + "_" + str(os.getpid())
    started = _now()
    start_monotonic = time.monotonic()
    steps: list[tuple[str, str, str]] = []

    _write(
        RUNNER_STATUS_FILE,
        _format_status(
            status="RUNNING_RESEARCH",
            cycle_id=cycle_id,
            started=started,
            steps=steps,
            detail="Runner started the staged local research-brain cycle.",
        ),
    )

    if str(APP_ROOT) not in sys.path:
        sys.path.insert(0, str(APP_ROOT))

    try:
        import engel_research_brain_v2 as rb
    except Exception as exc:
        detail = "Could not import engel_research_brain_v2: " + str(exc)
        _write(
            RUNNER_STATUS_FILE,
            _format_status(
                status="ERROR",
                cycle_id=cycle_id,
                started=started,
                finished=_now(),
                elapsed_seconds=time.monotonic() - start_monotonic,
                steps=steps,
                detail=detail,
            ),
        )
        return 2

    safe_steps = [
        ("research_brain_status", rb.research_brain_status),
        ("research_queue_status", rb.research_queue_status),
        ("research_next_best_topic", rb.research_next_best_topic),
        ("learning_proposals_build", rb.learning_proposals_build),
        ("learning_proposals_review", rb.learning_proposals_review),
        ("research_completion_digest", rb.research_completion_digest),
        ("research_digest_latest", rb.research_digest_latest),
    ]

    try:
        for name, func in safe_steps:
            steps.append(_call_step(name, func))
            _write(
                RUNNER_STATUS_FILE,
                _format_status(
                    status="RUNNING_RESEARCH",
                    cycle_id=cycle_id,
                    started=started,
                    steps=steps,
                    detail="Staged local research-brain cycle is running.",
                ),
            )

        _write(
            RUNNER_STATUS_FILE,
            _format_status(
                status="COMPLETE",
                cycle_id=cycle_id,
                started=started,
                finished=_now(),
                elapsed_seconds=time.monotonic() - start_monotonic,
                steps=steps,
                detail="Staged local research-brain cycle completed.",
            ),
        )
        return 0
    except Exception as exc:
        steps.append(("runner_exception", "ERROR", traceback.format_exc()))
        _write(
            RUNNER_STATUS_FILE,
            _format_status(
                status="ERROR",
                cycle_id=cycle_id,
                started=started,
                finished=_now(),
                elapsed_seconds=time.monotonic() - start_monotonic,
                steps=steps,
                detail="Runner failed safely: " + str(exc),
            ),
        )
        return 1


def main() -> int:
    _ensure_dirs()
    ok, owner = _acquire_lock()
    if not ok:
        _write(
            RUNNER_STATUS_FILE,
            _format_status(
                status="BLOCKED_DUPLICATE",
                cycle_id="duplicate_start_" + _stamp(),
                started=_now(),
                finished=_now(),
                elapsed_seconds=0,
                detail="Runner duplicate start blocked. Existing owner PID: " + str(owner),
            ),
        )
        return 3

    try:
        return run_cycle()
    finally:
        _release_lock()


if __name__ == "__main__":
    raise SystemExit(main())
