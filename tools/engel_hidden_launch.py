#!/usr/bin/env python3
"""
Engel hidden-service launcher.

Run a service under pythonw.exe (no console window) WITHOUT it crashing: under
pythonw sys.stdout/sys.stderr are None, so any service that prints (uvicorn /
llama_cpp.server, the bridge "listening on ..." lines) dies on the first write.
This shim points std streams at a per-service log file first, then runs the real
target in-process (so it stays in the task's process tree and Stop-ScheduledTask
still kills it).

Usage:
  pythonw engel_hidden_launch.py script <path.py> [args...]
  pythonw engel_hidden_launch.py module <dotted.module> [args...]
"""
import os
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / "runtime" / "logs"


def main() -> int:
    if len(sys.argv) < 3 or sys.argv[1] not in ("script", "module"):
        # nothing sane to run; exit quietly.
        return 2
    mode, target = sys.argv[1], sys.argv[2]
    rest = sys.argv[3:]

    # give std streams a real sink so prints never crash the service.
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        base = Path(target).stem if mode == "script" else target.replace(".", "_")
        logf = open(LOG_DIR / f"hidden_{base}.log", "a", encoding="utf-8", errors="replace")
        sys.stdout = logf
        sys.stderr = logf
    except Exception:
        # last resort: devnull, never crash the shim itself.
        devnull = open(os.devnull, "w")
        sys.stdout = devnull
        sys.stderr = devnull

    # present the target as if it were invoked directly.
    sys.argv = [target] + rest
    if mode == "module":
        runpy.run_module(target, run_name="__main__", alter_sys=True)
    else:
        runpy.run_path(str((ROOT / target) if not os.path.isabs(target) else target),
                       run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
