#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    import engel_agent_meeting_room as room

    failures: list[str] = []

    def require(condition: bool, message: str) -> None:
        if not condition:
            failures.append(message)

    temp_root = ROOT / "runtime" / "temp"
    temp_root.mkdir(parents=True, exist_ok=True)
    saved = {
        "runtime": room.RUNTIME_ROOM_DIR,
        "orders": room.ORDER_DIR,
        "state": room.ROOM_STATE_FILE,
        "reports": room.REPORTS_DIR,
        "memory_orders": room.SELF_UPGRADE_WORK_ORDER_DIR,
        "runtime_orders": room.SELF_UPGRADE_RUNTIME_WORK_ORDER_DIR,
        "dispatch": room.dispatch_station_work,
    }
    dispatch_calls: list[str] = []
    try:
        with tempfile.TemporaryDirectory(
            prefix="authoritative_room_verify_",
            dir=temp_root,
        ) as raw_temp:
            fixture = Path(raw_temp)
            room.RUNTIME_ROOM_DIR = fixture / "runtime"
            room.ORDER_DIR = room.RUNTIME_ROOM_DIR / "main_ui_orders"
            room.ROOM_STATE_FILE = room.RUNTIME_ROOM_DIR / "room_state.json"
            room.REPORTS_DIR = fixture / "reports"
            room.SELF_UPGRADE_WORK_ORDER_DIR = fixture / "memory_orders"
            room.SELF_UPGRADE_RUNTIME_WORK_ORDER_DIR = fixture / "runtime_orders"
            room.dispatch_station_work = lambda *_args, **_kwargs: (
                dispatch_calls.append("called") or ("Needs Review", "unexpected")
            )

            participants = [
                room.Participant(
                    name="Engel Core / Engel Orchestration Skill",
                    kind="agent",
                    type_label="Engel Core",
                    skill_label="Engel Orchestration Skill",
                )
            ]
            participants.extend(
                room.Participant(
                    name=f"Android Phone {label} Agent / Android Worker {label} Skill",
                    kind="agent",
                    type_label=f"Android Phone {label} Agent",
                    skill_label=f"Android Worker {label} Skill",
                    equipment=f"Android App Worker {label}",
                )
                for label in ("Alpha", "Beta", "Gamma")
            )
            participants.extend(
                [
                    room.Participant(
                        name="Windows Sub-Engel Agent / Windows Sub-Engel Worker Skill",
                        kind="agent",
                        type_label="Windows Sub-Engel Agent",
                        skill_label="Windows Sub-Engel Worker Skill",
                        equipment="Windows Sub-Engel Node - LAN check-in",
                    ),
                    room.Participant(
                        name="Verifier Agent / Verification Skill",
                        kind="agent",
                        type_label="Verifier Agent",
                        skill_label="Verification Skill",
                    ),
                ]
            )
            room._save_state(
                room.RoomState(
                    created_at=room._now_iso(),
                    participants=participants,
                )
            )

            order_id = "fixture-authoritative-success"
            room.ORDER_DIR.mkdir(parents=True, exist_ok=True)
            order_path = room.ORDER_DIR / f"{order_id}.json"
            order_path.write_text(
                json.dumps(
                    {
                        "order_id": order_id,
                        "order_text": "Review one bounded self-upgrade candidate.",
                        "job_type": "summarize_text",
                        "station_rows": list(range(len(participants))),
                    }
                ),
                encoding="utf-8",
            )
            workers = [
                {
                    "worker_id": worker_id,
                    "returned": True,
                    "status": "returned",
                    "contribution": f"{worker_id} verified candidate-only output",
                }
                for worker_id in sorted(room._AUTHORITATIVE_CYCLE_WORKERS)
            ]
            result = room.complete_order_from_engel_main_ui(
                order_id,
                "Cycle completed as dry_run_complete with four exact returns.",
                source="Engel conical self-upgrade cycle",
                authoritative_worker_results=workers,
                authoritative_final_status="dry_run_complete",
            )
            record = json.loads(order_path.read_text(encoding="utf-8"))
            require(result.get("accepted") is True, "authoritative completion was rejected")
            require(
                result.get("dispatch_performed") is False and not dispatch_calls,
                "authoritative completion redispatched station work",
            )
            require(
                record.get("authoritative_cycle_completion", {}).get(
                    "returned_worker_count"
                )
                == 4,
                "authoritative completion did not bind four returns",
            )
            require(
                all(
                    item.get("status") == "Returned"
                    for item in record.get("station_outcomes", [])
                ),
                "successful cycle did not project terminal station states",
            )

            rejected = room.complete_order_from_engel_main_ui(
                order_id,
                "forged",
                source="untrusted caller",
                authoritative_worker_results=workers,
                authoritative_final_status="dry_run_complete",
            )
            require(
                rejected.get("accepted") is False,
                "untrusted caller could invoke authoritative completion",
            )
            rejected_missing = room.complete_order_from_engel_main_ui(
                order_id,
                "incomplete",
                source="Engel conical self-upgrade cycle",
                authoritative_worker_results=workers[:3],
                authoritative_final_status="dry_run_complete",
            )
            require(
                rejected_missing.get("accepted") is False,
                "successful cycle accepted fewer than four exact returns",
            )
    finally:
        room.RUNTIME_ROOM_DIR = saved["runtime"]
        room.ORDER_DIR = saved["orders"]
        room.ROOM_STATE_FILE = saved["state"]
        room.REPORTS_DIR = saved["reports"]
        room.SELF_UPGRADE_WORK_ORDER_DIR = saved["memory_orders"]
        room.SELF_UPGRADE_RUNTIME_WORK_ORDER_DIR = saved["runtime_orders"]
        room.dispatch_station_work = saved["dispatch"]

    payload = {
        "schema": "ENGEL_AUTHORITATIVE_MEETING_ROOM_COMPLETION_VERIFICATION_V1",
        "ok": not failures,
        "failures": failures,
        "station_dispatch_calls": len(dispatch_calls),
        "provider_called": False,
        "source_mutation_performed": False,
    }
    print(json.dumps(payload, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
