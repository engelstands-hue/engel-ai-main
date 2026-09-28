#!/usr/bin/env python3
"""Verifier: the device broker is WIRED into live dispatch as a hard gate.

Closes the gap where engel_device_broker was a verified decision engine that
no dispatch path consulted (goal criterion: "Only reachable and capable
devices receive assignments"; forbidden: "routing work to DESKTOP-FIB17O7").

Checks (behavioral, against the real runner module):
  1. A forbidden device is hard-blocked even when the broker itself errors.
  2. With broker evidence, only broker-eligible workers pass the gate.
  3. A worker with NO broker evidence is blocked (fail-closed).
  4. A broker outage keeps non-forbidden workers on the heartbeat gate
     (narrowing never widening) and records the error honestly.
  5. The Sub-Engel forbidden block refuses a forbidden selected node and
     allows a normal one.
  6. The conical dispatch loop and phone dispatch actually consult the gate
     (source-level wiring assertions).

Emits {"ok": bool, ...}; exit 0 pass / 1 fail.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT), str(ROOT / "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

import engel_device_broker as broker  # noqa: E402
import run_engel_ui_chat_meeting_room_llm as runner  # noqa: E402

CHECKS: list[dict] = []


def record(name: str, ok: bool, detail: str = "") -> None:
    CHECKS.append({"check": name, "ok": bool(ok), "detail": detail})


def main() -> int:
    orig_decision = broker.broker_decision
    try:
        # 1. forbidden hard-block survives a broker crash -----------------------
        broker.broker_decision = lambda job_kind=None: (_ for _ in ()).throw(RuntimeError("boom"))
        gate = runner._broker_dispatch_gate(["DESKTOP-FIB17O7", "android_worker_alpha"])
        record("forbidden device hard-blocked even when the broker errors",
               "DESKTOP-FIB17O7" in gate["blocked"]
               and "DESKTOP-FIB17O7" not in gate["eligible"]
               and gate["consulted"] is False and bool(gate["broker_error"]),
               str(gate["blocked"]))

        # 4. broker outage narrows, never widens --------------------------------
        record("broker outage keeps non-forbidden workers on the heartbeat gate",
               gate["eligible"] == ["android_worker_alpha"], str(gate["eligible"]))

        # 2 + 3. broker evidence enforced via the REAL broker_decision function
        # against a fixture state file (integration-true: proves the gate reads
        # the decision's actual key shape, the lesson from the first wiring
        # fixture that hand-rolled a wrong-keyed decision and still passed).
        broker.broker_decision = orig_decision
        import json as _json
        import tempfile

        fixture_state = {
            "live_phone_required": True,
            "freshness_limit_seconds": 300.0,
            "workers": [
                {"worker_id": "android_worker_alpha", "paired": True,
                 "live_phone_connected": True, "adb_device_online": True,
                 "last_seen_age_seconds": 3.0, "phone_ip": "x"},
                {"worker_id": "android_worker_beta", "paired": True,
                 "live_phone_connected": True, "adb_device_online": True,
                 "last_seen_age_seconds": 999999.0, "phone_ip": "y"},
            ],
        }
        with tempfile.TemporaryDirectory() as td:
            state_path = Path(td) / "phone_state.json"
            state_path.write_text(_json.dumps(fixture_state), encoding="utf-8")
            orig_state = broker.PHONE_BRIDGE_STATE
            orig_sub = broker._sub_engel_candidates
            orig_transport = broker._sub_engel_server_transport_candidates
            orig_live_presence = broker._android_live_presence_candidates
            broker.PHONE_BRIDGE_STATE = state_path
            broker._sub_engel_candidates = lambda job_kind, now: []
            broker._sub_engel_server_transport_candidates = lambda job_kind, now: []
            broker._android_live_presence_candidates = lambda job_kind, now: []
            try:
                gate = runner._broker_dispatch_gate(
                    ["android_worker_alpha", "android_worker_beta", "android_worker_gamma"],
                    job_kind="return_status")
            finally:
                broker.PHONE_BRIDGE_STATE = orig_state
                broker._sub_engel_candidates = orig_sub
                broker._sub_engel_server_transport_candidates = orig_transport
                broker._android_live_presence_candidates = orig_live_presence
        record("only broker-eligible workers pass the gate (real broker, real key shape)",
               gate["consulted"] is True and gate["eligible"] == ["android_worker_alpha"]
               and "stale" in gate["blocked"].get("android_worker_beta", ""),
               str({k: gate[k] for k in ("eligible", "blocked")}))
        record("worker with no broker evidence is blocked (fail-closed)",
               gate["blocked"].get("android_worker_gamma") == "no broker evidence for this device",
               str(gate["blocked"].get("android_worker_gamma")))

        # 5. Sub-Engel forbidden node refusal -----------------------------------
        reason = runner._sub_engel_forbidden_block({"hostname": "DESKTOP-FIB17O7"})
        allowed = runner._sub_engel_forbidden_block({"hostname": "DESKTOP-UE5A6GG"})
        record("forbidden Sub-Engel node is refused; normal node allowed",
               bool(reason) and "forbidden" in reason and allowed == "",
               f"reason={reason!r} allowed={allowed!r}")

        # 6. wiring assertions ---------------------------------------------------
        source = (ROOT / "tools" / "run_engel_ui_chat_meeting_room_llm.py").read_text(
            encoding="utf-8", errors="replace")
        conical_wired = ("broker_gate = _broker_dispatch_gate(android_ids" in source
                         and "failed_worker_not_eligible" in source
                         and '"dispatch_broker_gate": broker_gate' in source)
        phone_wired = ("broker_gate = _broker_dispatch_gate(live_requested" in source
                       and '"device_broker_gate": broker_gate' in source)
        sub_wired = ("forbidden_reason = _sub_engel_forbidden_block(selected)" in source)
        record("conical, phone, and sub-engel dispatch paths consult the gate",
               conical_wired and phone_wired and sub_wired,
               f"conical={conical_wired} phone={phone_wired} sub={sub_wired}")

        import engel_communication_queen_assignment_producer as producer

        conical_types_valid = all(
            str(task.get("task_type") or "")
            in producer.WORKER_ALLOWED_TASK_TYPES.get(
                str(task.get("worker_id") or ""), set()
            )
            for task in runner.CONICAL_PHONE_TASKS
        )
        record(
            "every conical phone role uses a worker-approved task type",
            conical_types_valid,
            str(
                {
                    str(task.get("worker_id") or ""): str(
                        task.get("task_type") or ""
                    )
                    for task in runner.CONICAL_PHONE_TASKS
                }
            ),
        )
    finally:
        broker.broker_decision = orig_decision

    failed = [c for c in CHECKS if not c["ok"]]
    receipt = {
        "schema": "engel_dispatch_broker_wiring_verifier_v1",
        "goal_id": "engel_conical_agentic_sentient_self_upgrading_system",
        "ok": not failed,
        "checks_total": len(CHECKS),
        "checks_passed": sum(1 for c in CHECKS if c["ok"]),
        "checks_failed": len(failed),
        "failed_checks": failed,
        "checks": CHECKS,
    }
    print(json.dumps(receipt, indent=2, ensure_ascii=False))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
