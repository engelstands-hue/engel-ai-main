#!/usr/bin/env python3
"""Verify Python link-manager state controls can delegate to Rust LAN link commands."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
VERIFY_ROOT = ROOT / "runtime" / "rust_link_manager_bridge_verifier"
MISSING_ROOT = ROOT / "runtime" / "rust_link_manager_bridge_missing_claim_verifier"
STATE_PATH = VERIFY_ROOT / "remote_workers" / "lan_link_manager" / "session_state.json"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def prepare_root(root: Path, *, claim_lock: bool) -> None:
    if root.exists():
        shutil.rmtree(root)
    (root / "remote_workers" / "lan_link_manager").mkdir(parents=True, exist_ok=True)
    (root / "engel_ai.py").write_text("# verifier marker\n", encoding="utf-8")
    (root / "engel_agent_meeting_room.py").write_text("# verifier marker\n", encoding="utf-8")
    if claim_lock:
        (root / "tools").mkdir(parents=True, exist_ok=True)
        (root / "tools" / "verify_engel_remote_worker_claim_lock.py").write_text(
            "# verifier marker\n",
            encoding="utf-8",
        )


def seed_unsafe_state() -> None:
    payload = {
        "manager": "Engel Remote Worker Link Manager",
        "phone_role": "Dedicated Engel Remote Worker",
        "control_direction": "Engel controls phone",
        "phone_does_not_control_engel": False,
        "host": "127.0.0.1",
        "port": 8765,
        "pairing_code": "SHOULD_NOT_SURVIVE",
        "auto_apply": True,
        "safe_to_auto_apply": True,
        "trusted_memory_write": True,
        "source_mutation": True,
        "route_mutation": True,
        "queue_mutation_from_phone": True,
        "provider_calls": True,
    }
    STATE_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def safety_ok(payload: dict[str, Any]) -> bool:
    return (
        payload.get("phone_does_not_control_engel") is True
        and payload.get("auto_apply") is False
        and payload.get("safe_to_auto_apply") is False
        and payload.get("trusted_memory_write") is False
        and payload.get("source_mutation") is False
        and payload.get("route_mutation") is False
        and payload.get("queue_mutation_from_phone") is False
        and payload.get("provider_calls") is False
    )


def main() -> int:
    sys.path.insert(0, str(ROOT))
    prepare_root(VERIFY_ROOT, claim_lock=True)
    prepare_root(MISSING_ROOT, claim_lock=False)
    seed_unsafe_state()

    old_bridge = os.environ.get("ENGEL_REMOTE_WORKER_LINK_MANAGER_RUST_BRIDGE")
    old_strict = os.environ.get("ENGEL_REMOTE_WORKER_LINK_MANAGER_RUST_STRICT")
    old_root = os.environ.get("ENGEL_REMOTE_WORKER_LINK_MANAGER_RUST_ROOT")
    os.environ["ENGEL_REMOTE_WORKER_LINK_MANAGER_RUST_BRIDGE"] = "1"
    os.environ["ENGEL_REMOTE_WORKER_LINK_MANAGER_RUST_STRICT"] = "1"
    os.environ["ENGEL_REMOTE_WORKER_LINK_MANAGER_RUST_ROOT"] = str(VERIFY_ROOT)
    try:
        import engel_remote_worker_link_manager as manager

        enabled = manager.enable_auto_worker()
        require(enabled.get("runtime") == "engel-ai-rs", f"enable not Rust-backed: {enabled}")
        require(
            enabled.get("bridge") == "python-link-manager-rust-lan-link",
            f"enable missing bridge marker: {enabled}",
        )
        require(enabled.get("auto_worker_enabled") is True, f"enable failed: {enabled}")
        require(enabled.get("check_now_requested") is True, f"enable did not request check: {enabled}")
        require(safety_ok(enabled), f"enable safety fields drifted: {enabled}")

        checked = manager.check_now()
        require(checked.get("runtime") == "engel-ai-rs", f"check-now not Rust-backed: {checked}")
        require(checked.get("check_now_requested") is True, f"check-now failed: {checked}")
        require(safety_ok(checked), f"check-now safety fields drifted: {checked}")

        disabled = manager.disable_auto_worker()
        require(disabled.get("runtime") == "engel-ai-rs", f"disable not Rust-backed: {disabled}")
        require(disabled.get("auto_worker_enabled") is False, f"disable failed: {disabled}")
        require(disabled.get("auto_worker_paused") is True, f"disable did not pause worker: {disabled}")
        require(disabled.get("check_now_requested") is False, f"disable did not clear check: {disabled}")
        require(safety_ok(disabled), f"disable safety fields drifted: {disabled}")

        stored = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        require("pairing_code" not in stored, "Rust bridge stored pairing_code in link state")
        require(safety_ok(stored), f"stored state safety fields drifted: {stored}")

        os.environ["ENGEL_REMOTE_WORKER_LINK_MANAGER_RUST_ROOT"] = str(MISSING_ROOT)
        missing = manager.enable_auto_worker()
        require(missing.get("ok") is False, f"missing claim lock unexpectedly enabled: {missing}")
        require(
            int(missing.get("status_code") or 0) in {502, 503},
            f"missing claim lock status mismatch: {missing}",
        )

        payload = {
            "ok": True,
            "runtime": "engel-ai-rs",
            "verification": "python link-manager Rust LAN link bridge",
            "bridge": "python-link-manager-rust-lan-link",
            "enabled_auto_worker": enabled.get("auto_worker_enabled"),
            "checked_now_requested": checked.get("check_now_requested"),
            "disabled_auto_worker": disabled.get("auto_worker_enabled"),
            "disabled_auto_worker_paused": disabled.get("auto_worker_paused"),
            "missing_claim_lock_refused": missing.get("ok") is False,
            "missing_claim_lock_status_code": missing.get("status_code"),
            "pairing_code_stripped": "pairing_code" not in stored,
            "safety_clamps_ok": safety_ok(stored),
            "mutates_live_link_state": False,
            "mutates_live_pairing_token": False,
            "mutates_live_assignment_root": False,
        }
        return 0 if print_json_after_cleanup(payload) else 1
    finally:
        if old_bridge is None:
            os.environ.pop("ENGEL_REMOTE_WORKER_LINK_MANAGER_RUST_BRIDGE", None)
        else:
            os.environ["ENGEL_REMOTE_WORKER_LINK_MANAGER_RUST_BRIDGE"] = old_bridge
        if old_strict is None:
            os.environ.pop("ENGEL_REMOTE_WORKER_LINK_MANAGER_RUST_STRICT", None)
        else:
            os.environ["ENGEL_REMOTE_WORKER_LINK_MANAGER_RUST_STRICT"] = old_strict
        if old_root is None:
            os.environ.pop("ENGEL_REMOTE_WORKER_LINK_MANAGER_RUST_ROOT", None)
        else:
            os.environ["ENGEL_REMOTE_WORKER_LINK_MANAGER_RUST_ROOT"] = old_root
        for root in [VERIFY_ROOT, MISSING_ROOT]:
            if root.exists():
                shutil.rmtree(root)


def print_json_after_cleanup(payload: dict[str, Any]) -> bool:
    for root in [VERIFY_ROOT, MISSING_ROOT]:
        if root.exists():
            shutil.rmtree(root)
    payload["temp_root"] = str(VERIFY_ROOT)
    payload["missing_temp_root"] = str(MISSING_ROOT)
    payload["temp_root_removed"] = not VERIFY_ROOT.exists()
    payload["missing_temp_root_removed"] = not MISSING_ROOT.exists()
    payload["ok"] = (
        bool(payload.get("ok"))
        and payload["temp_root_removed"]
        and payload["missing_temp_root_removed"]
    )
    print(json.dumps(payload, indent=2))
    return bool(payload["ok"])


if __name__ == "__main__":
    raise SystemExit(main())
