#!/usr/bin/env python3
"""Four-hour Engel AI prompt training — delegates to the real UI creation trainer.

The earlier JSONL-only runner was misleading: it did not require phone returns,
artifacts, or Engel memory candidates. Real training that saves into Engel AI uses:

  tools/run_engel_ui_input_creation_training_loop.py

That path sends plain user prompts through the real Desktop V2 chat panel,
waits for Android worker returns over LAN, creates real artifacts, and writes:

  - reports/meeting_rooms/ENGEL_UI_INPUT_CREATION_TRAINING_HOUR_*.json
  - reports/memory_candidates/ENGEL_UI_INPUT_CREATION_TRAINING_HOUR_*_candidate_memory.md
  - memory/project_engel_ui_input_creation_training_20260526.md (append-only project memory)

Default: 4 cycles x 60 minutes x 60 jobs = 4 hours, strict verification.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOOP_RUNNER = ROOT / "tools" / "run_engel_ui_input_creation_training_loop.py"
HOUR_RUNNER = ROOT / "tools" / "run_engel_ui_input_creation_training_hour.py"
PY = ROOT / "runtime" / "python310" / "python.exe"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cycles", type=int, default=4, help="One-hour cycles (default 4 = 4 hours)")
    parser.add_argument("--minutes", type=float, default=60.0, help="Minutes per cycle")
    parser.add_argument("--target-jobs", type=int, default=60, help="Prompts per cycle")
    parser.add_argument("--per-job-timeout", type=float, default=240.0)
    parser.add_argument("--prompt-start-index", type=int, default=0, help="0 = continue after last full hour receipt")
    parser.add_argument("--skip-final-wait", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="Print command only")
    args = parser.parse_args(argv)

    if not LOOP_RUNNER.is_file() or not HOUR_RUNNER.is_file():
        print("FAIL: real training runners missing under tools/")
        return 1

    python = str(PY if PY.is_file() else Path(sys.executable))
    command = [
        python,
        str(LOOP_RUNNER),
        "--cycles",
        str(max(1, args.cycles)),
        "--minutes",
        str(args.minutes),
        "--target-jobs",
        str(max(1, args.target_jobs)),
        "--per-job-timeout",
        str(max(5.0, args.per_job_timeout)),
        "--prompt-start-index",
        str(max(0, args.prompt_start_index)),
    ]
    if args.skip_final_wait:
        command.append("--skip-final-wait")

    env = os.environ.copy()
    env.setdefault("PYTHONPATH", str(ROOT))
    env.setdefault("QT_QPA_PLATFORM", "offscreen")
    env.setdefault("ENGEL_MEETING_ROOM_ANDROID_RETURN_WAIT_SECONDS", "90")
    env.setdefault("ENGEL_TRAINING_RETURN_GRACE_SECONDS", "60")
    env.setdefault("ENGEL_EXECUTABLE_RESULTS_DIR", str(ROOT / "artifacts" / "engel_ui_results"))

    print("Engel four-hour REAL training (saves to Engel AI memory candidates)")
    print("Command:", " ".join(command))
    print("Saves: reports/memory_candidates + memory/project_engel_ui_input_creation_training_20260526.md")
    if args.dry_run:
        return 0

    proc = subprocess.run(command, cwd=str(ROOT), env=env)
    print(
        json.dumps(
            {
                "event": "four_hour_training_finished",
                "exit_code": proc.returncode,
                "honest_complete": proc.returncode == 0,
                "check_receipts": "reports/meeting_rooms/ENGEL_UI_INPUT_CREATION_TRAINING_LOOP_*.json",
                "check_memory": "reports/memory_candidates/ENGEL_UI_INPUT_CREATION_TRAINING_HOUR_*_candidate_memory.md",
            },
            indent=2,
        )
    )
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
