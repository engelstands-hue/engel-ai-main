#!/usr/bin/env python3
"""Verify Engel Main UI Meeting Room handoff through the Rust bridge."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import sys


ROOT = Path(__file__).resolve().parents[1]
VERIFY_ROOT = ROOT / "runtime" / "rust_meeting_room_bridge_verifier"
LIVE_ORDER_DIR = ROOT / "runtime" / "meeting_room" / "main_ui_orders"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def assert_inside(path: Path, root: Path) -> None:
    resolved_path = path.resolve()
    resolved_root = root.resolve()
    path_text = str(resolved_path).removeprefix("\\\\?\\").lower()
    root_text = str(resolved_root).removeprefix("\\\\?\\").lower().rstrip("\\/")
    require(
        path_text == root_text
        or path_text.startswith(root_text + "\\")
        or path_text.startswith(root_text + "/"),
        f"{resolved_path} escaped {resolved_root}",
    )


def prepare_fake_engel_root() -> None:
    if VERIFY_ROOT.exists():
        shutil.rmtree(VERIFY_ROOT)
    VERIFY_ROOT.mkdir(parents=True, exist_ok=True)
    # Rust root discovery requires Engel markers. The fake root keeps the
    # bridge verification away from the live Meeting Room state.
    (VERIFY_ROOT / "engel_ai.py").write_text("# verifier marker\n", encoding="utf-8")
    (VERIFY_ROOT / "engel_agent_meeting_room.py").write_text(
        "# verifier marker\n",
        encoding="utf-8",
    )


def main() -> int:
    sys.path.insert(0, str(ROOT))
    prepare_fake_engel_root()
    before_live_names = {
        path.name for path in LIVE_ORDER_DIR.glob("MAIN-*.json")
    } if LIVE_ORDER_DIR.exists() else set()

    old_runtime = os.environ.get("ENGEL_MEETING_ROOM_RUNTIME")
    old_strict = os.environ.get("ENGEL_MEETING_ROOM_RUST_STRICT")
    old_root = os.environ.get("ENGEL_MEETING_ROOM_RUST_ROOT")
    old_write_dispatch = os.environ.get("ENGEL_MEETING_ROOM_RUST_WRITE_DISPATCH")
    old_dispatch_root = os.environ.get("ENGEL_MEETING_ROOM_RUST_DISPATCH_ROOT")
    old_allow_live_dispatch = os.environ.get("ENGEL_MEETING_ROOM_RUST_ALLOW_LIVE_DISPATCH")
    dispatch_root = VERIFY_ROOT / "rust_dispatch_packets"
    os.environ["ENGEL_MEETING_ROOM_RUNTIME"] = "rust"
    os.environ["ENGEL_MEETING_ROOM_RUST_STRICT"] = "1"
    os.environ["ENGEL_MEETING_ROOM_RUST_ROOT"] = str(VERIFY_ROOT)
    os.environ["ENGEL_MEETING_ROOM_RUST_WRITE_DISPATCH"] = "1"
    os.environ["ENGEL_MEETING_ROOM_RUST_DISPATCH_ROOT"] = str(dispatch_root)
    os.environ.pop("ENGEL_MEETING_ROOM_RUST_ALLOW_LIVE_DISPATCH", None)
    try:
        from engel_agent_meeting_room import (
            complete_order_from_engel_main_ui,
            submit_order_from_engel_main_ui,
        )
        from engel_rust_meeting_room_bridge import return_intake_via_rust

        submit = submit_order_from_engel_main_ui(
            "Create a polished browser game with touch controls and use Windows Sub-Engel node to return status for Rust bridge verification.",
            source="Rust Meeting Room bridge verifier",
        )
        require(submit.get("accepted") is True, f"submit was not accepted: {submit}")
        require(submit.get("runtime") == "engel-ai-rs", f"submit was not Rust-backed: {submit}")
        order_id = str(submit.get("order_id") or "")
        require(order_id.startswith("MAIN-"), f"bad order_id: {order_id}")
        order_path = Path(str(submit.get("order_path") or ""))
        assert_inside(order_path, VERIFY_ROOT)
        require(order_path.is_file(), f"Rust bridge order path missing: {order_path}")

        complete = complete_order_from_engel_main_ui(
            order_id,
            "Rust bridge verifier main reply.",
            source="Rust Meeting Room bridge verifier",
        )
        require(complete.get("accepted") is True, f"complete was not accepted: {complete}")
        require(
            complete.get("runtime") == "engel-ai-rs",
            f"complete was not Rust-backed: {complete}",
        )
        require(
            "Collaboration dialogue" in str(complete.get("summary") or ""),
            f"completion summary missing collaboration dialogue: {complete}",
        )
        completed_path = Path(str(complete.get("order_path") or ""))
        assert_inside(completed_path, VERIFY_ROOT)
        record = json.loads(completed_path.read_text(encoding="utf-8"))
        require(record.get("native_completion") is True, "order record missing native_completion")
        require(record.get("completed_at"), "order record missing completed_at")
        require(record.get("station_results"), "order record missing station_results")
        dispatch_writes = record.get("dispatch_writes") or []
        require(len(dispatch_writes) >= 2, f"expected dispatch writes in record: {record}")
        require(
            int(complete.get("dispatch_write_count") or 0) >= 2,
            f"completion missing dispatch write count: {complete}",
        )
        packet_file_count = 0
        receipt_file_count = 0
        for write in dispatch_writes:
            packet_path = Path(str(write.get("packet_path") or ""))
            assert_inside(packet_path, dispatch_root)
            require(packet_path.is_file(), f"dispatch packet missing: {packet_path}")
            packet_file_count += 1
            receipt = write.get("receipt_path")
            if receipt:
                receipt_path = Path(str(receipt))
                assert_inside(receipt_path, dispatch_root)
                require(receipt_path.is_file(), f"dispatch receipt missing: {receipt_path}")
                receipt_file_count += 1
        require(packet_file_count >= 2, f"missing dispatch packet files: {dispatch_writes}")
        require(receipt_file_count >= 1, f"missing Android dispatch receipt: {dispatch_writes}")
        station_outcomes = record.get("station_outcomes") or []
        android_packet = next(
            (
                (outcome.get("dispatch_packet") or {})
                for outcome in station_outcomes
                if (outcome.get("dispatch_packet") or {}).get("dispatch_kind")
                == "android_remote_worker_assignment"
            ),
            {},
        )
        packet_id = str(android_packet.get("packet_id") or "")
        worker_id = str(android_packet.get("worker_target") or "android_worker_alpha")
        require(packet_id, f"missing Android dispatch packet in station outcomes: {record}")
        returned_dir = VERIFY_ROOT / "remote_workers" / "communication_queen_assignments" / "returned"
        returned_dir.mkdir(parents=True, exist_ok=True)
        returned_path = returned_dir / f"verifier_{packet_id}_result.json"
        returned_payload = {
            "result_version": "1",
            "packet_id": packet_id,
            "worker_device": "engel_remote_worker_flutter",
            "worker_id": worker_id,
            "trust_level": "untrusted_until_engel_review",
            "result_type": "draft_result_json",
            "requires_review": True,
            "safe_to_auto_apply": False,
            "draft_text": "Python bridge verifier returned worker result for Rust Meeting Room intake.",
            "suggested_next_step": "Review inside Engel AI Main.",
            "device_capabilities": {
                "connectivity": {"transports": ["wifi", "lan"]},
                "app": {"version": "verifier", "build_number": 1},
            },
        }
        returned_path.write_text(json.dumps(returned_payload, indent=2), encoding="utf-8")
        intake = return_intake_via_rust(
            order_id,
            source="Rust Meeting Room bridge verifier",
        )
        require(intake.get("accepted") is True, f"return intake was not accepted: {intake}")
        require(intake.get("runtime") == "engel-ai-rs", f"return intake was not Rust-backed: {intake}")
        require(int(intake.get("ingested_count") or 0) == 1, f"return intake did not ingest: {intake}")
        record = json.loads(completed_path.read_text(encoding="utf-8"))
        require(record.get("native_return_intake") is True, "order record missing native_return_intake")
        require(record.get("meeting_room_return_intake"), "order record missing return intake ledger")

        live_order_path = LIVE_ORDER_DIR / f"{order_id}.json"
        after_live_names = {
            path.name for path in LIVE_ORDER_DIR.glob("MAIN-*.json")
        } if LIVE_ORDER_DIR.exists() else set()
        require(not live_order_path.exists(), f"Rust bridge wrote live order path: {live_order_path}")
        require(
            before_live_names == after_live_names,
            "Rust bridge changed the live Meeting Room order directory",
        )
        payload = {
            "ok": True,
            "runtime": "engel-ai-rs",
            "verification": "python Engel Main UI Meeting Room Rust bridge",
            "order_id": order_id,
            "order_path": str(order_path),
            "completed_order_path": str(completed_path),
            "mutates_live_room_state": False,
            "mutates_live_assignment_root": False,
            "live_order_count": len(after_live_names),
            "station_result_count": len(record.get("station_results") or []),
            "collaboration_turn_count": len(record.get("collaboration_dialogue") or []),
            "dispatch_write_count": int(complete.get("dispatch_write_count") or 0),
            "return_intake_count": int(intake.get("ingested_count") or 0),
            "packet_file_count": packet_file_count,
            "receipt_file_count": receipt_file_count,
            "dispatch_root": str(dispatch_root),
            "returned_result_path": str(returned_path),
        }
        print(json.dumps(payload, indent=2))
        return 0
    finally:
        if old_runtime is None:
            os.environ.pop("ENGEL_MEETING_ROOM_RUNTIME", None)
        else:
            os.environ["ENGEL_MEETING_ROOM_RUNTIME"] = old_runtime
        if old_strict is None:
            os.environ.pop("ENGEL_MEETING_ROOM_RUST_STRICT", None)
        else:
            os.environ["ENGEL_MEETING_ROOM_RUST_STRICT"] = old_strict
        if old_root is None:
            os.environ.pop("ENGEL_MEETING_ROOM_RUST_ROOT", None)
        else:
            os.environ["ENGEL_MEETING_ROOM_RUST_ROOT"] = old_root
        if old_write_dispatch is None:
            os.environ.pop("ENGEL_MEETING_ROOM_RUST_WRITE_DISPATCH", None)
        else:
            os.environ["ENGEL_MEETING_ROOM_RUST_WRITE_DISPATCH"] = old_write_dispatch
        if old_dispatch_root is None:
            os.environ.pop("ENGEL_MEETING_ROOM_RUST_DISPATCH_ROOT", None)
        else:
            os.environ["ENGEL_MEETING_ROOM_RUST_DISPATCH_ROOT"] = old_dispatch_root
        if old_allow_live_dispatch is None:
            os.environ.pop("ENGEL_MEETING_ROOM_RUST_ALLOW_LIVE_DISPATCH", None)
        else:
            os.environ["ENGEL_MEETING_ROOM_RUST_ALLOW_LIVE_DISPATCH"] = old_allow_live_dispatch
        if VERIFY_ROOT.exists():
            shutil.rmtree(VERIFY_ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
