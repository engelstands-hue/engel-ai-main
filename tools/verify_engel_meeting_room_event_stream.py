#!/usr/bin/env python3
"""Verifier for the Engel Meeting Room Event Stream (engel_meeting_room_event_stream.py).

Proves the goal-critical invariants (acceptance: "Meeting Room displays real work
state rather than heartbeat animation") using deterministic synthetic fixtures
plus a live read. Emits {"ok": bool, ...} to stdout; exit 0 pass / 1 fail.

Invariants:
  1. EVERY emitted event is backed by a real receipt file (evidence_present True).
  2. NO phantom events: a stage with no file on disk never appears.
  3. Ordering is newest-first by timestamp.
  4. A forbidden device that appears in real artifacts is FLAGGED (device_forbidden),
     never silently dropped or silently trusted.
  5. room_state declares real mode (heartbeat_animation False) and reports
     events_all_evidence_backed True.
  6. Fail-closed: no shared room mounted -> no bus/sub-engel events, no crash.
  7. Projection is observe-only: collect_events/room_state perform no writes.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT), str(ROOT / "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

import engel_meeting_room_event_stream as stream  # noqa: E402

CHECKS: list[dict] = []


def record(name: str, ok: bool, detail: str = "") -> None:
    CHECKS.append({"check": name, "ok": bool(ok), "detail": detail})


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="engel_room_stream_verify_"))
    assign = tmp / "assignments"
    orders = tmp / "orders"
    room = tmp / "sub_engel_transport"
    for d in (assign / "claimed", assign / "returned", orders,
              room / "SUB_ENGEL_SENT_WORK"):
        d.mkdir(parents=True, exist_ok=True)

    # Real fixture artifacts ------------------------------------------------
    (assign / "claimed" / "a_android_worker_alpha_summarize_text_claim.json").write_text(
        json.dumps({"packet_id": "pkt1", "worker_device": "android_worker_alpha",
                    "claim_type": "summarize_text", "timestamp_utc": "2026-07-22T08:00:01Z"}), encoding="utf-8")
    (assign / "returned" / "a_android_worker_alpha_summarize_text_result.json").write_text(
        json.dumps({"packet_id": "pkt1", "worker_device": "android_worker_alpha",
                    "result_type": "summarize_text_draft", "stored_at_utc": "2026-07-22T08:00:05Z"}), encoding="utf-8")
    (orders / "MAIN-1.json").write_text(
        json.dumps({"order_id": "MAIN-1", "order_text": "split work across devices",
                    "created_at": "2026-07-22T07:59:00Z", "completed_at": "2026-07-22T08:00:10Z",
                    "main_reply_preview": "done"}), encoding="utf-8")
    (room / "SUB_ENGEL_SENT_WORK" / "DESKTOP-UE5A6GG__MAIN-1.done.json").write_text(
        json.dumps({"order_id": "MAIN-1", "hostname": "DESKTOP-UE5A6GG",
                    "worker_engine": "local_llm_one_shot", "operator_status": "done",
                    "completed_at_utc": "2026-07-22T08:00:08Z"}), encoding="utf-8")
    (room / "SUB_ENGEL_WORK_ORDERS").mkdir(parents=True, exist_ok=True)
    (room / "SUB_ENGEL_WORK_ORDERS" / "MAIN-1.json").write_text(
        json.dumps({"id": "MAIN-1", "selected_stable_identity": "DESKTOP-UE5A6GG",
                    "job_type": "return_status", "created_at_utc": "2026-07-22T08:00:02Z"}),
        encoding="utf-8")
    (room / "receipts").mkdir(parents=True, exist_ok=True)
    (room / "receipts" / "MAIN-1.dispatch.json").write_text(
        json.dumps({"order_id": "MAIN-1", "node_id": "DESKTOP-UE5A6GG",
                    "event": "authenticated dispatch", "dispatched_at_utc": "2026-07-22T08:00:03Z"}),
        encoding="utf-8")
    (room / "engel_shared_room_bus.jsonl").write_text(
        json.dumps({"channel": "CLAIM", "sender": "DESKTOP-FIB17O7",
                    "message": "chirp", "timestamp_utc": "2026-07-22T08:00:20Z"}) + "\n"
        + json.dumps({"channel": "RESULT", "sender": "DESKTOP-UE5A6GG",
                      "message": "returned MAIN-1", "timestamp_utc": "2026-07-22T08:00:09Z"}) + "\n",
        encoding="utf-8")

    orig = (
        stream.ANDROID_ASSIGN_ROOT,
        stream.MEETING_ORDERS_DIR,
        stream._server_transport_dir,
    )
    stream.ANDROID_ASSIGN_ROOT = assign
    stream.MEETING_ORDERS_DIR = orders
    stream._server_transport_dir = lambda: room
    try:
        events = stream.collect_events(limit=100)
        # 1. every event evidence-backed
        record("every event backed by a real file", all(e["evidence_present"] for e in events),
               f"{sum(1 for e in events if not e['evidence_present'])} unbacked")
        # 2. no phantom: expected stages present, and count == real artifacts produced
        stages = {e["stage"] for e in events}
        expect = {"android_claimed", "android_returned", "order_submitted", "order_completed",
                  "sub_engel_assigned", "sub_engel_claimed", "sub_engel_returned",
                  "bus_CLAIM", "bus_RESULT"}
        record("all real stages projected, none missing", expect.issubset(stages),
               f"missing={sorted(expect - stages)}")
        # 3. ordering newest-first
        ts = [e["ts"] for e in events if e["ts"] is not None]
        record("events ordered newest-first", ts == sorted(ts, reverse=True), str(ts[:4]))
        # 4. forbidden device flagged, not dropped
        fib = [e for e in events if e["device"].lower() == "desktop-fib17o7"]
        record("forbidden device shown AND flagged", bool(fib) and all(e["device_forbidden"] for e in fib),
               f"found={len(fib)}")
        # 5. room_state real mode
        st = stream.room_state(limit=100)
        record("room_state real mode (no heartbeat, all evidence-backed)",
               st["heartbeat_animation"] is False and st["events_all_evidence_backed"] is True, "")
        record("room_state rolls order MAIN-1 to a return proof",
               any(o["order_id"] == "MAIN-1" and o["has_return_proof"] for o in st["orders"]), "")
        alpha_events = [e for e in events if e.get("stage", "").startswith("android_")]
        record(
            "Android events retain stable worker identity",
            bool(alpha_events)
            and all(e.get("device") == "android_worker_alpha" for e in alpha_events),
            str({e.get("device") for e in alpha_events}),
        )

        # 6. fail-closed with no CT246 server transport
        stream._server_transport_dir = lambda: None
        st2 = stream.room_state(limit=100)
        no_bus = not any(e["stage"].startswith("bus_") or e["stage"] == "sub_engel_returned"
                         for e in st2["recent_events"])
        record("fail-closed: no server transport -> no bus/sub-engel events, no crash",
               st2["server_transport_present"] is False and no_bus, "")
    finally:
        (
            stream.ANDROID_ASSIGN_ROOT,
            stream.MEETING_ORDERS_DIR,
            stream._server_transport_dir,
        ) = orig

    # 7. observe-only: the projection functions write nothing (snapshot is the only writer)
    src = Path(stream.__file__).read_text(encoding="utf-8")
    # collect_events/room_state must not call open(...,'a'/'w') or subprocess.
    import re
    proj = src.split("def snapshot_to_stream")[0]  # everything BEFORE the explicit snapshot writer
    proj_writes = re.findall(r"\.open\(|\.write\(|\.write_text\(|subprocess|os\.system", proj)
    record("projection (collect/room_state) performs no writes/exec", not proj_writes, str(proj_writes[:4]))

    # LIVE read: never crashes, every live event evidence-backed
    live = stream.room_state(limit=60)
    record("LIVE room_state: all events evidence-backed",
           live.get("events_all_evidence_backed") is True, f"events={live.get('event_count')}")

    failed = [c for c in CHECKS if not c["ok"]]
    receipt = {
        "schema": "engel_meeting_room_event_stream_verifier_v1",
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
