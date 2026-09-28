#!/usr/bin/env python3
"""
Engel hidden-process WAIT wrapper.

For a long-running task that must launch an EXTERNAL windowless process and STAY
RUNNING (so Task Scheduler keeps the task in the Running state). Used for the two
ssh tunnels: `conhost --headless` was wrong — it exits right after spawning the
powershell, so the task flips to Ready, the lifecycle controller thinks the tunnel
died, and restarts it every minute (orphaned duplicates pile up, all fighting for
the same CT246 forward ports).

This runs under pythonw (no console of its own), spawns the target with
CREATE_NO_WINDOW (no console for it or its ssh child either), and BLOCKS on it — so
pythonw is the task's process and the task stays Running for the tunnel's whole life.
Task Scheduler's job object still terminates pythonw + the child tree on stop.

Usage:  pythonw engel_run_hidden.py <exe> [args...]
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CREATE_NO_WINDOW = 0x08000000

# pythonw has null std streams; give them a sink so an error can't crash the wrapper.
try:
    (ROOT / "runtime" / "logs").mkdir(parents=True, exist_ok=True)
    _f = open(ROOT / "runtime" / "logs" / "run_hidden.log", "a", encoding="utf-8", errors="replace")
    sys.stdout = _f
    sys.stderr = _f
except Exception:
    pass


def main() -> int:
    cmd = sys.argv[1:]
    if not cmd:
        return 2
    try:
        proc = subprocess.Popen(cmd, creationflags=CREATE_NO_WINDOW, cwd=str(ROOT))
        return proc.wait()
    except Exception as exc:
        print(f"run_hidden error launching {cmd!r}: {exc}", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
