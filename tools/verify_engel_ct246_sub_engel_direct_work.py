#!/usr/bin/env python3
"""Offline verifier for CT246's direct Sub-Engel dispatch client."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys


ROOT = Path(__file__).resolve().parents[1]
TEST_ROOT = ROOT / "runtime" / "verify_ct246_sub_transport"
os.environ["ENGEL_SUB_ENGEL_TRANSPORT_ROOT"] = str(TEST_ROOT)

MODULE_PATH = ROOT / "tools" / "engel_ct246_sub_engel_direct_work.py"
spec = importlib.util.spec_from_file_location("verify_ct246_direct_module", MODULE_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError(f"cannot load {MODULE_PATH}")
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    resolved = TEST_ROOT.resolve()
    require((ROOT / "runtime").resolve() in resolved.parents, f"unsafe test root: {resolved}")
    if TEST_ROOT.exists():
        shutil.rmtree(TEST_ROOT)
    module.WORK_ORDERS.mkdir(parents=True)
    order_path = module.WORK_ORDERS / "VERIFY-CT246-DIRECT.json"
    order = {
        "schema": "engel_sub_engel_work_order_v1",
        "id": "VERIFY-CT246-DIRECT",
        "target": "windows_sub_engel",
        "order_text": "Review this architecture and return two concrete risks.",
        "selected_node": {
            "node_id": "DESKTOP-UE5A6GG",
            "url": "http://198.51.100.227:8776",
        },
        "proof_required": True,
    }
    module.write_json(order_path, order)
    calls: list[dict] = []

    def fake_run_action(action: str, **kwargs):
        calls.append({"action": action, **kwargs})
        direct = {
            "schema": "engel_sub_engel_direct_work_receipt_v1",
            "ok": True,
            "transport": "ct246_authenticated_direct_http",
            "order_id": order["id"],
            "worker_engine": "peft_lora_transformers",
            "worker_output": "Risk one. Risk two.",
            "local_llm_attempted": True,
            "persistent_memory": {"ok": True, "status": "recorded"},
            "training_processes_unchanged": True,
            "session_token": "must-not-leak",
        }
        return {
            "ok": True,
            "result": {
                "return_code": 0,
                "stdout": json.dumps(direct),
                "session_token": "must-not-leak",
            },
        }

    receipt = module.dispatch(order_path, fake_run_action)
    require(receipt.get("ok") is True, f"dispatch failed: {receipt}")
    require(calls and calls[0].get("action") == "direct_work.execute", "wrong remote action")
    payload = calls[0].get("payload") or {}
    require("command" not in payload, "dispatch used shell command")
    require(payload.get("work_order", {}).get("order_text") == order["order_text"], "order text changed")
    require(receipt.get("container") == "CT246", "container proof missing")
    require(receipt.get("server_hostname") == "engel-ai-main", "server hostname proof missing")
    require(receipt.get("proxmox_node") == "engel-spine-01", "Proxmox node proof missing")
    require(receipt.get("transport") == "ct246_authenticated_direct_http", "wrong transport")
    require(receipt.get("google_drive_used") is False, "Google Drive must be false")
    require(receipt.get("power_vault_used") is False, "PowerVault must be false")
    require(receipt.get("local_llm_attempted") is True, "local LLM proof missing")
    returned = Path(str(receipt.get("returned_file") or ""))
    audit = Path(str(receipt.get("server_receipt_file") or ""))
    require(returned.is_file(), "returned work file missing")
    require(audit.is_file(), "server audit receipt missing")
    require(module.BUS.is_file(), "Meeting Room bus event missing")
    persisted = returned.read_text(encoding="utf-8")
    require("must-not-leak" not in persisted, "session token leaked into persisted receipt")
    require("[redacted]" in persisted, "redaction proof missing")

    print("ENGEL_CT246_SUB_DIRECT_DISPATCH_VERIFY_PASS")
    print(f"returned_file={returned}")
    print("container=CT246")
    print("google_drive_used=false")
    print("power_vault_used=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
