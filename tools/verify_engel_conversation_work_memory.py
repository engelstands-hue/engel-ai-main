#!/usr/bin/env python3
"""Agents speak work, not status logs, and conversations stay compressed off swap."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for folder in (ROOT, ROOT / "tools", ROOT / "organs" / "core"):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

import engel_context_compaction as compaction  # noqa: E402

CHECKS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    CHECKS.append((name, ok, detail))
    print(("PASS " if ok else "FAIL ") + name + (f" — {detail}" if detail and not ok else ""))


LOG = (
    "Local Engel training job started under Engel AI Main control. "
    "Package refreshed with 408 rows. Runner PID: 1134283. "
    "Log: /opt/engel/runtime/training_runs/ENGEL_TRAINING_RUN_20261005_082317.log. "
    "RunPod was not used. I will not mark the model upgraded until Engel writes and verifies the local training receipts."
)
ROOM_LOG = (
    "Sent that through the Agent Meeting Room on CT246. "
    "Order MAIN-20261005T105743036673 is recorded. "
    "Room result: UI Agent: Assigned, Code Agent: Assigned, Research Agent: Assigned"
)
WORK = "The public price for a 10M-token training pass is lower than the 100M pass."


def main() -> int:
    check("log_detected", compaction.looks_like_status_log(LOG))
    check("room_log_detected", compaction.looks_like_status_log(ROOM_LOG))
    check("work_kept", compaction.looks_like_status_log(WORK) is False)

    spoken = compaction.replace_status_log_with_work("train the llm", LOG)
    check("spoken_has_no_pid", "Runner PID" not in spoken and "1134283" not in spoken)
    check("spoken_has_no_log_path", "/opt/engel/runtime" not in spoken)
    check("spoken_keeps_row_count", "408" in spoken)

    room = compaction.visible_meeting_room_work(
        {
            "ok": True,
            "completion": {
                "station_results": [
                    "UI Agent: Assigned",
                    "Code Agent: Assigned",
                    "Research Agent: Assigned",
                ],
                "station_outcomes": [
                    {
                        "agent": "Research Agent",
                        "status": "Returned",
                        "reply": WORK,
                    }
                ],
                "summary": "Meeting Room updated: UI Agent: Assigned, Code Agent: Assigned",
            },
        },
        "Gather current market rates for AI model training.",
    )
    check("room_speaks_work", WORK in room, room)
    check("room_hides_assigned", "Assigned" not in room, room)

    swapping = (
        "MemTotal: 1000000 kB\n"
        "MemAvailable: 400000 kB\n"
        "SwapTotal: 8000000 kB\n"
        "SwapFree: 3500000 kB\n"
    )
    idle = (
        "MemTotal: 1000000 kB\n"
        "MemAvailable: 800000 kB\n"
        "SwapTotal: 8000000 kB\n"
        "SwapFree: 8000000 kB\n"
    )
    host_swap = compaction.read_host_memory(swapping)
    host_idle = compaction.read_host_memory(idle)
    check("swap_in_use_blocks_process", host_swap["new_process_allowed"] is False)
    check("idle_swap_allows_process", host_idle["new_process_allowed"] is True)
    blocked = compaction.training_spoken_reply(started=False, blocked_reason="swap", swap_in_use=True)
    check("swap_reply_refuses_runner", "did not start" in blocked.casefold())
    duplicate = compaction.training_spoken_reply(started=False, blocked_reason="already_running")
    check("duplicate_reply_refuses_second_runner", "second runner" in duplicate.casefold())

    with tempfile.TemporaryDirectory() as tmp:
        compaction.STATE_DIR = Path(tmp)
        state = compaction.maintain_conversation(
            [
                {"role": "user", "content": "What is the training price?"},
                {"role": "assistant", "content": WORK},
                {"role": "assistant", "content": LOG},
                {"role": "user", "content": "Keep going on the price comparison."},
            ],
            thread_id="desk-research",
            meminfo=swapping,
            write=True,
        )
        check("digest_omits_log", "Runner PID" not in state["context"] and "1134283" not in json.dumps(state["recent"]))
        check("digest_keeps_work", "10M-token" in state["context"] or "price" in state["context"])
        check("swap_marks_maintained_state", state["swap_in_use"] is True and state["new_process_allowed"] is False)
        path = Path(state["state_path"])
        check("one_maintained_file", path.is_file() and path.name == "maintained_desk-research.json")
        again = compaction.maintain_conversation(
            [{"role": "user", "content": "Continue the same price comparison."}],
            thread_id="desk-research",
            meminfo=idle,
            write=True,
        )
        files = list(Path(tmp).glob("maintained_*.json"))
        check("overwrite_does_not_grow_files", len(files) == 1 and again["state_path"] == state["state_path"])

    failed = [name for name, ok, _detail in CHECKS if not ok]
    print(f"{len(CHECKS) - len(failed)}/{len(CHECKS)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
