#!/usr/bin/env python3
"""Verify the saved link-manager Rust control bridge without mutating live state."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
VERIFY_ROOT = ROOT / "runtime" / "rust_link_manager_control_bridge_verifier"
MISSING_ROOT = ROOT / "runtime" / "rust_link_manager_control_bridge_missing_claim_verifier"
RUST_EXE = ROOT / "rust" / "engel-core-rs" / "target" / "debug" / "engel-ai-rs.exe"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def prepare_root(root: Path, *, claim_lock: bool) -> None:
    if root.exists():
        shutil.rmtree(root)
    (root / "remote_workers" / "lan_link_manager").mkdir(parents=True, exist_ok=True)
    (root / "reports" / "remote_worker_lan_link_manager").mkdir(parents=True, exist_ok=True)
    (root / "tools").mkdir(parents=True, exist_ok=True)
    (root / "engel_ai.py").write_text("# verifier marker\n", encoding="utf-8")
    (root / "engel_agent_meeting_room.py").write_text("# verifier marker\n", encoding="utf-8")
    if claim_lock:
        (root / "tools" / "verify_engel_remote_worker_claim_lock.py").write_text(
            "# verifier marker\n",
            encoding="utf-8",
        )


def read_state(root: Path) -> dict[str, Any]:
    path = root / "remote_workers" / "lan_link_manager" / "session_state.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(payload, dict), f"expected state object at {path}")
    return payload


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


def patch_manager_root(manager: Any, root: Path) -> None:
    manager.PROJECT_ROOT = root
    manager.RUNTIME_ROOT = root / "remote_workers" / "lan_link_manager"
    manager.STATE_PATH = manager.RUNTIME_ROOT / "session_state.json"
    manager.LOG_PATH = manager.RUNTIME_ROOT / "link_manager.log"
    manager.REPORT_DIR = root / "reports" / "remote_worker_lan_link_manager"
    manager.LAN_RECEIVER_SCRIPT = root / "engel_remote_worker_lan_pairing.py"
    manager.CLAIM_LOCK_VERIFIER = root / "tools" / "verify_engel_remote_worker_claim_lock.py"


def main() -> int:
    sys.path.insert(0, str(ROOT))
    require(RUST_EXE.is_file(), f"missing Rust executable: {RUST_EXE}")
    prepare_root(VERIFY_ROOT, claim_lock=True)
    prepare_root(MISSING_ROOT, claim_lock=False)

    import engel_remote_worker_link_manager as manager

    originals = {
        "PROJECT_ROOT": manager.PROJECT_ROOT,
        "RUNTIME_ROOT": manager.RUNTIME_ROOT,
        "STATE_PATH": manager.STATE_PATH,
        "LOG_PATH": manager.LOG_PATH,
        "REPORT_DIR": manager.REPORT_DIR,
        "LAN_RECEIVER_SCRIPT": manager.LAN_RECEIVER_SCRIPT,
        "CLAIM_LOCK_VERIFIER": manager.CLAIM_LOCK_VERIFIER,
    }
    old_health = manager._receiver_health_ok
    old_env = {
        manager.RUST_LINK_MANAGER_BRIDGE_ENV: os.environ.get(manager.RUST_LINK_MANAGER_BRIDGE_ENV),
        manager.RUST_LINK_MANAGER_STRICT_ENV: os.environ.get(manager.RUST_LINK_MANAGER_STRICT_ENV),
        manager.RUST_LINK_MANAGER_ROOT_ENV: os.environ.get(manager.RUST_LINK_MANAGER_ROOT_ENV),
        manager.RUST_EXE_ENV: os.environ.get(manager.RUST_EXE_ENV),
    }

    try:
        for key in [
            manager.RUST_LINK_MANAGER_BRIDGE_ENV,
            manager.RUST_LINK_MANAGER_STRICT_ENV,
            manager.RUST_LINK_MANAGER_ROOT_ENV,
        ]:
            os.environ.pop(key, None)
        os.environ[manager.RUST_EXE_ENV] = str(RUST_EXE)
        manager._receiver_health_ok = lambda host, port: False
        patch_manager_root(manager, VERIFY_ROOT)

        default_status = manager.rust_control_bridge_status()
        require(default_status.get("rust_link_manager_bridge_enabled") is False, "bridge must default off")
        require(
            default_status.get("rust_link_manager_bridge_effective_enabled") is False,
            "bridge effective state must default off",
        )
        require(default_status.get("rust_link_manager_bridge_env_enabled") is False, "env bridge must be off")

        enabled_status = manager.enable_rust_control_bridge()
        require(enabled_status.get("rust_link_manager_bridge_enabled") is True, f"enable failed: {enabled_status}")
        require(
            enabled_status.get("rust_link_manager_bridge_effective_enabled") is True,
            f"effective bridge not enabled: {enabled_status}",
        )
        require(enabled_status.get("rust_link_manager_bridge_source") == "persistent_state", "must use saved switch")
        require(enabled_status.get("rust_link_manager_bridge_strict") is True, "saved switch must be strict")

        enabled = manager.enable_auto_worker()
        require(enabled.get("runtime") == "engel-ai-rs", f"enable not Rust-backed: {enabled}")
        require(enabled.get("bridge") == "python-link-manager-rust-lan-link", f"missing bridge marker: {enabled}")
        require(enabled.get("bridge_source") == "persistent_state", f"wrong bridge source: {enabled}")
        require(enabled.get("auto_worker_enabled") is True, f"enable failed: {enabled}")
        require(enabled.get("check_now_requested") is True, f"enable did not request check-now: {enabled}")
        require(safety_ok(enabled), f"enable safety drifted: {enabled}")

        checked = manager.check_now()
        require(checked.get("runtime") == "engel-ai-rs", f"check-now not Rust-backed: {checked}")
        require(checked.get("bridge_source") == "persistent_state", f"wrong check bridge source: {checked}")
        require(checked.get("check_now_requested") is True, f"check-now failed: {checked}")
        require(safety_ok(checked), f"check-now safety drifted: {checked}")

        disabled = manager.disable_auto_worker()
        require(disabled.get("runtime") == "engel-ai-rs", f"disable not Rust-backed: {disabled}")
        require(disabled.get("bridge_source") == "persistent_state", f"wrong disable bridge source: {disabled}")
        require(disabled.get("auto_worker_enabled") is False, f"disable failed: {disabled}")
        require(disabled.get("auto_worker_paused") is True, f"disable did not pause worker: {disabled}")
        require(disabled.get("check_now_requested") is False, f"disable did not clear check-now: {disabled}")
        require(safety_ok(disabled), f"disable safety drifted: {disabled}")

        stored = read_state(VERIFY_ROOT)
        require("pairing_code" not in stored, "stored state leaked pairing_code")
        require(safety_ok(stored), f"stored state safety drifted: {stored}")

        disabled_status = manager.disable_rust_control_bridge()
        require(disabled_status.get("rust_link_manager_bridge_enabled") is False, "saved switch did not disable")
        require(
            disabled_status.get("rust_link_manager_bridge_effective_enabled") is False,
            "effective bridge did not disable",
        )
        fallback_checked = manager.check_now()
        require(fallback_checked.get("runtime") != "engel-ai-rs", f"fallback still used Rust: {fallback_checked}")
        require(fallback_checked.get("check_now_requested") is True, f"fallback check-now failed: {fallback_checked}")
        require(safety_ok(fallback_checked), f"fallback safety drifted: {fallback_checked}")

        patch_manager_root(manager, MISSING_ROOT)
        missing_status = manager.enable_rust_control_bridge()
        require(missing_status.get("rust_link_manager_bridge_enabled") is True, "missing-root bridge not enabled")
        missing = manager.enable_auto_worker()
        require(missing.get("ok") is False, f"missing claim-lock unexpectedly enabled: {missing}")
        require(int(missing.get("status_code") or 0) in {502, 503}, f"missing status mismatch: {missing}")

        receipt_text = "\n".join(
            path.read_text(encoding="utf-8", errors="replace")
            for path in (VERIFY_ROOT / "reports" / "remote_worker_lan_link_manager").glob(
                "REMOTE_WORKER_LINK_MANAGER_*rust-control-bridge*.md"
            )
        )
        require("pairing_code" not in receipt_text, "receipt leaked pairing_code")

        payload = {
            "ok": True,
            "runtime": "engel-ai-rs",
            "verification": "saved Python link-manager Rust control bridge",
            "bridge": "python-link-manager-rust-lan-link",
            "default_bridge_enabled": default_status.get("rust_link_manager_bridge_enabled"),
            "enabled_bridge": enabled_status.get("rust_link_manager_bridge_enabled"),
            "enabled_effective_bridge": enabled_status.get("rust_link_manager_bridge_effective_enabled"),
            "enabled_source": enabled_status.get("rust_link_manager_bridge_source"),
            "env_bridge_enabled": enabled_status.get("rust_link_manager_bridge_env_enabled"),
            "enabled_auto_worker": enabled.get("auto_worker_enabled"),
            "checked_now_requested": checked.get("check_now_requested"),
            "disabled_auto_worker": disabled.get("auto_worker_enabled"),
            "disabled_auto_worker_paused": disabled.get("auto_worker_paused"),
            "fallback_after_disable_used_python": fallback_checked.get("runtime") != "engel-ai-rs",
            "missing_claim_lock_refused": missing.get("ok") is False,
            "missing_claim_lock_status_code": missing.get("status_code"),
            "pairing_code_stripped": "pairing_code" not in stored,
            "safety_clamps_ok": safety_ok(stored) and safety_ok(fallback_checked),
            "mutates_live_link_state": False,
            "mutates_live_pairing_token": False,
            "mutates_live_assignment_root": False,
        }
        return 0 if print_json_after_cleanup(payload) else 1
    finally:
        manager._receiver_health_ok = old_health
        for key, value in originals.items():
            setattr(manager, key, value)
        for key, value in old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
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
    print(json.dumps(payload, indent=2, sort_keys=True))
    return bool(payload["ok"])


if __name__ == "__main__":
    raise SystemExit(main())
