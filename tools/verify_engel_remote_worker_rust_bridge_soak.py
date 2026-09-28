#!/usr/bin/env python3
"""Verify managed LAN receiver Rust bridge soak state without starting a receiver."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
VERIFY_ROOT = ROOT / "runtime" / "rust_lan_endpoint_bridge_soak_verifier"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def prepare_root(root: Path) -> None:
    if root.exists():
        shutil.rmtree(root)
    (root / "remote_workers" / "lan_link_manager").mkdir(parents=True, exist_ok=True)
    (root / "reports" / "remote_worker_lan_link_manager").mkdir(parents=True, exist_ok=True)
    (root / "tools").mkdir(parents=True, exist_ok=True)
    (root / "engel_ai.py").write_text("# verifier marker\n", encoding="utf-8")
    (root / "engel_agent_meeting_room.py").write_text("# verifier marker\n", encoding="utf-8")
    (root / "engel_remote_worker_lan_pairing.py").write_text("# verifier marker\n", encoding="utf-8")
    (root / "tools" / "verify_engel_remote_worker_claim_lock.py").write_text(
        "# verifier marker\n",
        encoding="utf-8",
    )


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(payload, dict), f"expected JSON object at {path}")
    return payload


def main() -> int:
    sys.path.insert(0, str(ROOT))
    prepare_root(VERIFY_ROOT)

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

    try:
        manager.PROJECT_ROOT = VERIFY_ROOT
        manager.RUNTIME_ROOT = VERIFY_ROOT / "remote_workers" / "lan_link_manager"
        manager.STATE_PATH = manager.RUNTIME_ROOT / "session_state.json"
        manager.LOG_PATH = manager.RUNTIME_ROOT / "link_manager.log"
        manager.REPORT_DIR = VERIFY_ROOT / "reports" / "remote_worker_lan_link_manager"
        manager.LAN_RECEIVER_SCRIPT = VERIFY_ROOT / "engel_remote_worker_lan_pairing.py"
        manager.CLAIM_LOCK_VERIFIER = VERIFY_ROOT / "tools" / "verify_engel_remote_worker_claim_lock.py"

        default_status = manager.rust_bridge_soak_status()
        require(default_status.get("rust_lan_endpoint_bridge_soak_enabled") is False, "soak must default off")
        require(default_status.get("rust_lan_endpoint_bridge_env_keys") == [], "default env keys must be empty")

        enabled = manager.enable_rust_bridge_soak()
        require(enabled.get("rust_lan_endpoint_bridge_soak_enabled") is True, f"enable failed: {enabled}")
        require(enabled.get("rust_lan_endpoint_bridge_strict") is True, f"strict not enabled: {enabled}")
        require(enabled.get("rust_lan_endpoint_bridge_root") == str(VERIFY_ROOT), f"root mismatch: {enabled}")
        require(enabled.get("rust_lan_endpoint_bridge_requires_receiver_restart") is False, "stopped receiver needs no restart")

        env = manager.receiver_environment()
        expected_env = {
            manager.RUST_LAN_ENDPOINT_BRIDGE_ENV,
            manager.RUST_LAN_ENDPOINT_STRICT_ENV,
            manager.RUST_LAN_ENDPOINT_ROOT_ENV,
        }
        env_keys = set(manager.receiver_bridge_env_overrides().keys())
        require(expected_env.issubset(env_keys), f"missing bridge env keys: {sorted(env_keys)}")
        require(env[manager.RUST_LAN_ENDPOINT_BRIDGE_ENV] == "1", "bridge env must be enabled")
        require(env[manager.RUST_LAN_ENDPOINT_STRICT_ENV] == "1", "strict env must be enabled")
        require(env[manager.RUST_LAN_ENDPOINT_ROOT_ENV] == str(VERIFY_ROOT), "bridge root env mismatch")
        require("pairing_code" not in json.dumps(read_json(manager.STATE_PATH)), "state leaked pairing_code")

        command = manager.receiver_command("127.0.0.1", 8765, False)
        require(manager.RUST_LAN_ENDPOINT_BRIDGE_ENV not in command, "receiver command must not inline env")
        require("--allow-lan" not in command, "receiver command changed allow-lan flag unexpectedly")

        state = read_json(manager.STATE_PATH)
        state["link_status"] = "running"
        state["receiver_pid"] = None
        state["started_by_link_manager"] = False
        state["receiver_rust_lan_endpoint_bridge_enabled"] = False
        manager.STATE_PATH.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        manager._receiver_health_ok = lambda host, port: True
        running_enabled = manager.enable_rust_bridge_soak()
        require(
            running_enabled.get("rust_lan_endpoint_bridge_requires_receiver_restart") is True,
            f"running non-bridged receiver must require restart: {running_enabled}",
        )

        state = read_json(manager.STATE_PATH)
        state["receiver_rust_lan_endpoint_bridge_enabled"] = True
        manager.STATE_PATH.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        disabled = manager.disable_rust_bridge_soak()
        require(disabled.get("rust_lan_endpoint_bridge_soak_enabled") is False, f"disable failed: {disabled}")
        require(
            disabled.get("rust_lan_endpoint_bridge_requires_receiver_restart") is True,
            f"running bridged receiver must require restart after disable: {disabled}",
        )

        stored = read_json(manager.STATE_PATH)
        receipt_text = "\n".join(
            path.read_text(encoding="utf-8", errors="replace")
            for path in manager.REPORT_DIR.glob("REMOTE_WORKER_LINK_MANAGER_*rust-bridge-soak*.md")
        )
        require("pairing_code" not in json.dumps(stored), "stored state leaked pairing_code")
        require("SHOULD_NOT_SURVIVE" not in receipt_text, "receipt leaked synthetic secret")

        payload = {
            "ok": True,
            "runtime": "python-link-manager",
            "bridge_target_runtime": "engel-ai-rs",
            "verification": "managed LAN receiver Rust bridge soak",
            "default_soak_enabled": default_status.get("rust_lan_endpoint_bridge_soak_enabled"),
            "enabled_soak": enabled.get("rust_lan_endpoint_bridge_soak_enabled"),
            "strict_enabled": enabled.get("rust_lan_endpoint_bridge_strict"),
            "env_keys": sorted(env_keys),
            "bridge_env_enabled": env[manager.RUST_LAN_ENDPOINT_BRIDGE_ENV] == "1",
            "bridge_env_strict": env[manager.RUST_LAN_ENDPOINT_STRICT_ENV] == "1",
            "bridge_env_root_matches": env[manager.RUST_LAN_ENDPOINT_ROOT_ENV] == str(VERIFY_ROOT),
            "restart_required_when_stopped": enabled.get("rust_lan_endpoint_bridge_requires_receiver_restart"),
            "restart_required_when_running_non_bridged": running_enabled.get(
                "rust_lan_endpoint_bridge_requires_receiver_restart"
            ),
            "restart_required_when_running_bridged_disabled": disabled.get(
                "rust_lan_endpoint_bridge_requires_receiver_restart"
            ),
            "receiver_command_unchanged": manager.RUST_LAN_ENDPOINT_BRIDGE_ENV not in command,
            "pairing_code_stripped": "pairing_code" not in json.dumps(stored),
            "mutates_live_link_state": False,
            "mutates_live_pairing_token": False,
            "mutates_live_assignment_root": False,
        }
        return 0 if print_json_after_cleanup(payload) else 1
    finally:
        manager._receiver_health_ok = old_health
        for key, value in originals.items():
            setattr(manager, key, value)
        if VERIFY_ROOT.exists():
            shutil.rmtree(VERIFY_ROOT)


def print_json_after_cleanup(payload: dict[str, Any]) -> bool:
    if VERIFY_ROOT.exists():
        shutil.rmtree(VERIFY_ROOT)
    payload["temp_root"] = str(VERIFY_ROOT)
    payload["temp_root_removed"] = not VERIFY_ROOT.exists()
    payload["ok"] = bool(payload.get("ok")) and payload["temp_root_removed"]
    print(json.dumps(payload, indent=2, sort_keys=True))
    return bool(payload["ok"])


if __name__ == "__main__":
    raise SystemExit(main())
