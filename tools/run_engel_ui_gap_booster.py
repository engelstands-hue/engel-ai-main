#!/usr/bin/env python3
"""Add guarded extra Engel UI training turns during long paced waits."""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from engel_ui_prompt_training_support import redact, stamp  # noqa: E402
import run_engel_flutter_main_ui_prompt_training as ui  # noqa: E402


LATEST_STATUS = ROOT / "memory" / "training" / "ENGEL_CODE_CREATION_UI_TRAINING_LATEST_RUN.json"

BOOSTER_PROMPTS = [
    "Engel AI Main, create advanced code: implement a compact Python verifier that reads Engel meeting-room receipts, validates local_llm_only, cuda backend, selected device, and code artifact markers, then prints a signed JSON summary. Return fenced Python code and pytest tests.",
    "Engel AI Main, create advanced code: implement a Rust receipt scanner that parses JSONL training logs, validates prompt completion order, reports missing meeting-room orders, and includes unit tests. Return fenced Rust code.",
    "Engel AI Main, create advanced code: implement a TypeScript agent-routing policy module with typed device capabilities, deterministic selection, rejection reasons, and example tests. Return fenced TypeScript code.",
    "Engel AI Main, create advanced code: implement a PowerShell diagnostic module that checks Engel Main, Sub-Engel, CUDA llama.cpp, and local model paths without writing to C drive. Return fenced PowerShell code and Pester-style checks.",
    "Engel AI Main, create advanced code: implement a Go worker lease checker for meeting-room jobs with retry windows, dead-letter status, metrics counters, and table-driven tests. Return fenced Go code.",
    "Engel AI Main, create advanced code: implement a safe C ring-buffer receipt queue with bounds checks, clear ownership comments, and minimal unit-test examples. Return fenced C code.",
    "Engel AI Main, create advanced code: implement a Node.js local-only chat transcript auditor that detects provider API usage, missing CUDA proof, and absent code artifacts. Return fenced JavaScript code.",
]


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    if path.drive.lower() == "c:":
        raise RuntimeError(f"refusing to write booster log on C: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(redact(payload), sort_keys=True) + "\n")


def read_recent_events(path: Path, max_lines: int = 80) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[-max_lines:]
    events: list[dict[str, Any]] = []
    for line in lines:
        try:
            value = json.loads(line)
        except Exception:
            continue
        if isinstance(value, dict):
            events.append(value)
    return events


def current_training_state() -> dict[str, Any]:
    status = load_json(LATEST_STATUS)
    run_dir = Path(str(status.get("run_dir") or ""))
    events = read_recent_events(run_dir / "one_hour.log")
    latest = events[-1] if events else {}
    latest_complete = next(
        (event for event in reversed(events) if event.get("event") == "flutter_prompt_complete"),
        {},
    )
    return {
        "status": status,
        "run_dir": run_dir,
        "latest": latest,
        "latest_complete": latest_complete,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-gap-seconds", type=int, default=180)
    parser.add_argument("--timeout-seconds", type=int, default=90)
    parser.add_argument("--poll-seconds", type=float, default=10.0)
    parser.add_argument("--max-boosters", type=int, default=80)
    args = parser.parse_args()

    sent_for_completed: set[int] = set()
    sent = 0
    run_id = f"engel_ui_gap_booster_{stamp()}"
    hwnd, pid, process_path = ui._ensure_window()

    while sent < args.max_boosters:
        state = current_training_state()
        status = state["status"]
        run_dir = state["run_dir"]
        latest = state["latest"]
        latest_complete = state["latest_complete"]
        log_path = run_dir / "gap_booster.log"

        if not run_dir.exists():
            append_jsonl(
                ROOT / "reports" / "codex_bridge" / f"{run_id}.log",
                {"event": "gap_booster_waiting_for_run_dir", "run_id": run_id},
            )
            time.sleep(args.poll_seconds)
            continue

        if status.get("status") not in {"RUNNING", "STARTING"}:
            append_jsonl(
                log_path,
                {
                    "event": "gap_booster_finished",
                    "run_id": run_id,
                    "reason": "main_training_not_running",
                    "main_status": status.get("status"),
                    "boosters_sent": sent,
                },
            )
            return 0

        completed = int(latest.get("completed_prompts") or latest_complete.get("index") or 0)
        seconds_to_next = int(latest.get("seconds_to_next_prompt") or 0)
        if (
            latest.get("event") == "flutter_paced_wait"
            and seconds_to_next >= args.min_gap_seconds
            and completed > 0
            and completed not in sent_for_completed
        ):
            prompt = BOOSTER_PROMPTS[sent % len(BOOSTER_PROMPTS)]
            append_jsonl(
                log_path,
                {
                    "event": "gap_booster_start",
                    "run_id": run_id,
                    "after_main_completed_prompt": completed,
                    "seconds_to_next_prompt": seconds_to_next,
                    "prompt": prompt,
                },
            )
            result = ui.send_prompt_through_flutter(hwnd, prompt, args.timeout_seconds, sent + 1, run_id)
            sent += 1
            sent_for_completed.add(completed)
            append_jsonl(
                log_path,
                {
                    "event": "gap_booster_complete",
                    "run_id": run_id,
                    "after_main_completed_prompt": completed,
                    "status": result.get("status"),
                    "duration_seconds": result.get("duration_seconds"),
                    "order_id": result.get("order_id"),
                    "wrapper_receipt_path": result.get("wrapper_receipt_path"),
                    "local_llm_only": result.get("local_llm_only"),
                    "screenshot": result.get("screenshot"),
                },
            )
            print(
                json.dumps(
                    {
                        "event": "gap_booster_complete",
                        "run_id": run_id,
                        "boosters_sent": sent,
                        "after_main_completed_prompt": completed,
                        "status": result.get("status"),
                        "order_id": result.get("order_id"),
                    },
                    sort_keys=True,
                ),
                flush=True,
            )

        time.sleep(args.poll_seconds)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
