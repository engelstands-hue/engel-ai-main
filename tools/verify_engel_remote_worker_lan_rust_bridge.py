#!/usr/bin/env python3
"""Verify Python LAN worker endpoints can delegate claim/return state to Rust."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
VERIFY_ROOT = ROOT / "runtime" / "rust_remote_worker_lan_bridge_verifier"
ASSIGNMENT_ROOT = VERIFY_ROOT / "remote_workers" / "communication_queen_assignments"
APPROVED_DIR = ASSIGNMENT_ROOT / "approved"
CLAIMED_DIR = ASSIGNMENT_ROOT / "claimed"
RETURNED_DIR = ASSIGNMENT_ROOT / "returned"
DUPLICATE_DIR = ASSIGNMENT_ROOT / "duplicate_returns"


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


def json_count(path: Path) -> int:
    return len(list(path.glob("*.json"))) if path.exists() else 0


def prepare_fake_root() -> None:
    if VERIFY_ROOT.exists():
        shutil.rmtree(VERIFY_ROOT)
    APPROVED_DIR.mkdir(parents=True, exist_ok=True)
    CLAIMED_DIR.mkdir(parents=True, exist_ok=True)
    RETURNED_DIR.mkdir(parents=True, exist_ok=True)
    DUPLICATE_DIR.mkdir(parents=True, exist_ok=True)
    (VERIFY_ROOT / "engel_ai.py").write_text("# verifier marker\n", encoding="utf-8")
    (VERIFY_ROOT / "engel_agent_meeting_room.py").write_text("# verifier marker\n", encoding="utf-8")
    (VERIFY_ROOT / "tools").mkdir(parents=True, exist_ok=True)
    (VERIFY_ROOT / "tools" / "verify_engel_remote_worker_claim_lock.py").write_text(
        "# verifier marker\n",
        encoding="utf-8",
    )
    packet = {
        "packet_version": "1",
        "packet_id": "python_rust_bridge_packet_alpha",
        "created_at": "2026-05-31T00:00:00Z",
        "created_by": "Engel Communication Router",
        "approved_by": "Engel Core",
        "approval_scope": "remote_worker_assignment_only",
        "assignment_mode": "remote_worker_auto",
        "trust_level": "untrusted_until_reviewed",
        "worker_target": "android_worker_alpha",
        "task_type": "summarize_text",
        "title": "Python LAN endpoint Rust bridge verification",
        "instructions": "Return a bounded review-only status result.",
        "source_summary": "",
        "source_refs": [],
        "allowed_outputs": ["draft_result_json"],
        "blocked_actions": [
            "execute_commands",
            "write_trusted_memory",
            "mutate_queue",
            "mutate_routes",
            "mutate_source",
            "control_engel",
            "auto_apply_fixes",
        ],
        "requires_review": True,
        "safe_to_auto_apply": False,
        "not_trusted_memory": True,
        "no_direct_control": True,
        "risk_flags": [],
    }
    (APPROVED_DIR / "python_rust_bridge_packet_alpha.json").write_text(
        json.dumps(packet, indent=2),
        encoding="utf-8",
    )


def valid_result(packet_id: str = "python_rust_bridge_packet_alpha") -> dict[str, Any]:
    return {
        "result_version": "1",
        "packet_id": packet_id,
        "worker_device": "engel_remote_worker_flutter",
        "worker_id": "android_worker_alpha",
        "trust_level": "untrusted_until_engel_review",
        "result_type": "draft_result_json",
        "requires_review": True,
        "safe_to_auto_apply": False,
        "draft_text": "Python endpoint delegated this result to Rust for review-only storage.",
        "pairing_code": "SHOULD_NOT_BE_STORED",
    }


def main() -> int:
    sys.path.insert(0, str(ROOT))
    prepare_fake_root()
    old_bridge = os.environ.get("ENGEL_REMOTE_WORKER_LAN_RUST_BRIDGE")
    old_strict = os.environ.get("ENGEL_REMOTE_WORKER_LAN_RUST_STRICT")
    old_root = os.environ.get("ENGEL_REMOTE_WORKER_LAN_RUST_ROOT")
    os.environ["ENGEL_REMOTE_WORKER_LAN_RUST_BRIDGE"] = "1"
    os.environ["ENGEL_REMOTE_WORKER_LAN_RUST_STRICT"] = "1"
    os.environ["ENGEL_REMOTE_WORKER_LAN_RUST_ROOT"] = str(VERIFY_ROOT)
    try:
        from engel_remote_worker_lan_pairing import (
            next_assignment_response,
            return_result_response,
        )

        claim_http, claim = next_assignment_response(
            worker_id="android_worker_alpha",
            worker_device="engel_remote_worker_flutter",
        )
        require(claim_http == 200, f"claim http status mismatch: {claim_http} {claim}")
        require(claim.get("runtime") == "engel-ai-rs", f"claim not Rust-backed: {claim}")
        require(
            claim.get("bridge") == "python-lan-endpoint-rust-state-machine",
            f"claim missing bridge marker: {claim}",
        )
        require(claim.get("status") == "assignment_ready", f"claim failed: {claim}")
        for key in ["claim_receipt_path", "claimed_assignment_path", "claim_lock_path"]:
            assert_inside(Path(str(claim.get(key) or "")), VERIFY_ROOT)

        returned_http, returned = return_result_response(
            valid_result(),
            remote_address="127.0.0.1",
        )
        require(returned_http == 200, f"return http status mismatch: {returned_http} {returned}")
        require(returned.get("runtime") == "engel-ai-rs", f"return not Rust-backed: {returned}")
        require(returned.get("accepted") is True, f"return not accepted: {returned}")
        returned_path = Path(str(returned.get("returned_result_path") or ""))
        assert_inside(returned_path, VERIFY_ROOT)
        stored = json.loads(returned_path.read_text(encoding="utf-8"))
        require("pairing_code" not in stored, "stored Rust return leaked pairing_code")
        require(stored.get("safe_to_auto_apply") is False, "stored result safe_to_auto_apply drifted")
        require(stored.get("trusted_memory_write") is False, "stored result trusted_memory_write drifted")

        duplicate_http, duplicate = return_result_response(
            valid_result(),
            remote_address="127.0.0.1",
        )
        require(duplicate_http == 409, f"duplicate http status mismatch: {duplicate_http} {duplicate}")
        require(
            duplicate.get("status") == "duplicate_return_rejected",
            f"duplicate was not rejected: {duplicate}",
        )

        missing_http, missing = return_result_response(
            valid_result("missing_claim_packet"),
            remote_address="127.0.0.1",
        )
        require(missing_http == 409, f"missing-claim http status mismatch: {missing_http} {missing}")
        require(missing.get("status") == "return_rejected", f"missing claim not rejected: {missing}")

        unsafe = valid_result()
        unsafe["requires_review"] = False
        unsafe["safe_to_auto_apply"] = True
        unsafe["auto_apply"] = True
        unsafe_http, unsafe_response = return_result_response(unsafe, remote_address="127.0.0.1")
        require(unsafe_http == 400, f"unsafe http status mismatch: {unsafe_http} {unsafe_response}")
        require(
            unsafe_response.get("status") == "invalid_return_result",
            f"unsafe result not rejected: {unsafe_response}",
        )

        payload = {
            "ok": True,
            "runtime": "engel-ai-rs",
            "verification": "python LAN worker endpoint Rust bridge",
            "bridge": "python-lan-endpoint-rust-state-machine",
            "claim_http_status": claim_http,
            "return_http_status": returned_http,
            "duplicate_http_status": duplicate_http,
            "missing_claim_http_status": missing_http,
            "unsafe_http_status": unsafe_http,
            "claim_status": claim.get("status"),
            "return_accepted": returned.get("accepted"),
            "duplicate_status": duplicate.get("status"),
            "missing_claim_status": missing.get("status"),
            "unsafe_status": unsafe_response.get("status"),
            "pairing_code_stripped": "pairing_code" not in stored,
            "safe_to_auto_apply": stored.get("safe_to_auto_apply"),
            "trusted_memory_write": stored.get("trusted_memory_write"),
            "claimed_json_count": json_count(CLAIMED_DIR),
            "returned_json_count": json_count(RETURNED_DIR),
            "duplicate_json_count": json_count(DUPLICATE_DIR),
            "mutates_live_assignment_root": False,
            "mutates_live_returned_results": False,
        }
        require(payload["claimed_json_count"] == 2, f"bad claimed count: {payload}")
        require(payload["returned_json_count"] == 1, f"bad returned count: {payload}")
        require(payload["duplicate_json_count"] == 1, f"bad duplicate count: {payload}")
        return 0 if print_json_after_cleanup(payload) else 1
    finally:
        if old_bridge is None:
            os.environ.pop("ENGEL_REMOTE_WORKER_LAN_RUST_BRIDGE", None)
        else:
            os.environ["ENGEL_REMOTE_WORKER_LAN_RUST_BRIDGE"] = old_bridge
        if old_strict is None:
            os.environ.pop("ENGEL_REMOTE_WORKER_LAN_RUST_STRICT", None)
        else:
            os.environ["ENGEL_REMOTE_WORKER_LAN_RUST_STRICT"] = old_strict
        if old_root is None:
            os.environ.pop("ENGEL_REMOTE_WORKER_LAN_RUST_ROOT", None)
        else:
            os.environ["ENGEL_REMOTE_WORKER_LAN_RUST_ROOT"] = old_root
        if VERIFY_ROOT.exists():
            shutil.rmtree(VERIFY_ROOT)


def print_json_after_cleanup(payload: dict[str, Any]) -> bool:
    removed = False
    try:
        if VERIFY_ROOT.exists():
            shutil.rmtree(VERIFY_ROOT)
        removed = not VERIFY_ROOT.exists()
    finally:
        payload["temp_root"] = str(VERIFY_ROOT)
        payload["temp_root_removed"] = removed
        payload["ok"] = bool(payload.get("ok")) and removed
        print(json.dumps(payload, indent=2))
    return bool(payload["ok"])


if __name__ == "__main__":
    raise SystemExit(main())
