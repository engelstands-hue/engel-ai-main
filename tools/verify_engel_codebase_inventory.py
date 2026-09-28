#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shutil
import sys


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools" / "engel_codebase_inventory.py"
TEST_ROOT = ROOT / "runtime" / "tests" / "engel_codebase_inventory"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def load_module():
    spec = importlib.util.spec_from_file_location("engel_codebase_inventory", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError("could not load codebase inventory")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    module = load_module()
    if TEST_ROOT.exists():
        shutil.rmtree(TEST_ROOT)
    TEST_ROOT.mkdir(parents=True)
    try:
        inventory = module.build_inventory(ROOT)
        require(inventory["ok"] is True, "inventory failed")
        require(inventory["goal"] == "Conical Agentic Sentient Self Upgrading System", "goal missing")
        required = {
            "chat",
            "discord",
            "meeting_room",
            "models",
            "provider_bridges",
            "workers",
            "sub_engel",
            "storage",
            "desktop_ui",
            "self_upgrade",
        }
        require(required.issubset(inventory["surfaces"]), "required surface missing")
        for surface in required:
            item = inventory["surfaces"][surface]
            require(item["owner"], f"{surface} owner missing")
            require(item["services"], f"{surface} services missing")
            require(item["files"], f"{surface} files missing")
            require(item["verifiers"], f"{surface} verifiers missing")

        chat = inventory["surfaces"]["chat"]
        require(any(x["relative_path"] == "tools/engel_main_server_chat_http_service.py" and x["exists_on_scan_root"] for x in chat["files"]), "chat service owner file missing")
        storage = inventory["surfaces"]["storage"]
        require(any(x["relative_path"] == "tools/engel_runtime_path_normalizer.py" and x["exists_on_scan_root"] for x in storage["files"]), "storage boundary owner file missing")
        ui = inventory["surfaces"]["desktop_ui"]
        require(all(x["authority_location"] == "rog_controller" for x in ui["files"]), "desktop UI authority must stay on ROG")
        sub = inventory["surfaces"]["sub_engel"]
        require(any(x["authority_location"] == "sub_desktop" for x in sub["files"]), "Sub-Engel source authority missing")

        output = TEST_ROOT / "ownership_map.json"
        module.write_inventory(inventory, output)
        loaded = module.load_inventory(output)
        require(loaded["surface_count"] == inventory["surface_count"], "inventory round trip failed")

        cases = {
            "Discord is leaking owner data": "discord",
            "The local LLM adapter canary regressed": "models",
            "Android worker gamma heartbeat has no claim return": "workers",
            "The Flutter preview panel button is broken": "desktop_ui",
            "The archive mount path leaked into active runtime": "storage",
            "Self upgrade rollback patch failed": "self_upgrade",
        }
        for text, expected in cases.items():
            result = module.resolve_failure(text, inventory)
            require(result["ok"] is True, f"failure did not resolve: {text}")
            matched = {item["surface"] for item in result["matches"]}
            require(expected in matched, f"{text} did not map to {expected}")

        print("PASS surface_ownership")
        print("PASS service_and_verifier_mapping")
        print("PASS source_presence")
        print("PASS inventory_round_trip")
        print("PASS failure_owner_resolution")
        print("ENGEL_CODEBASE_INVENTORY_VERIFY_PASS")
        return 0
    finally:
        if TEST_ROOT.exists():
            shutil.rmtree(TEST_ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
