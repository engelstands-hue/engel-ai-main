#!/usr/bin/env python3
"""Build Engel's CT-owned codebase inventory and failure ownership map."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any


ROOT = Path(os.environ.get("ENGEL_APP_ROOT") or Path(__file__).resolve().parents[1]).resolve()
STATE_ROOT = Path(os.environ.get("ENGEL_CODEBASE_INVENTORY_ROOT") or ROOT / "run" / "self_update" / "codebase")
INVENTORY_PATH = STATE_ROOT / "ownership_map.json"
MAX_HASH_BYTES = 8 * 1024 * 1024


SURFACE_RULES: dict[str, dict[str, Any]] = {
    "chat": {
        "owner": "ct246_engel_ai_main",
        "services": ["engel-main-chat", "engel-memory-search"],
        "files": [
            "tools/engel_main_server_chat_http_service.py",
            "tools/engel_main_local_model_worker.py",
            "tools/engel_mode_gate.py",
            "tools/engel_memory_search.py",
            "engel_flutter_main/lib/main.dart",
        ],
        "verifiers": [
            "tools/verify_engel_main_server_chat_service.py",
            "tools/verify_engel_chat_memory_quality_gate.py",
            "tools/verify_nt3_retrieve_once.py",
        ],
        "keywords": ["chat", "reply", "repeat", "memory", "identity", "slow", "timeout", "local llm"],
    },
    "discord": {
        "owner": "ct246_engel_ai_main",
        "services": ["engel-discord-bridge", "engel-main-chat"],
        "files": [
            "tools/engel_discord_bridge.py",
            "tools/engel_main_server_chat_http_service.py",
        ],
        "verifiers": [
            "tools/verify_engel_discord_identity_guard.py",
            "tools/verify_engel_discord_local_first_proof.py",
        ],
        "keywords": ["discord", "owner gate", "engelz", "discord reply", "discord leak"],
    },
    "meeting_room": {
        "owner": "ct246_engel_ai_main",
        "services": ["engel-agent-meeting-room"],
        "files": [
            "tools/engel_meeting_room_lan_server.py",
            "tools/engel_agent_meeting_room.py",
            "tools/run_engel_ui_chat_meeting_room_llm.py",
            "engel3d_office_main/src",
        ],
        "verifiers": [
            "tools/verify_engel_agent_meeting_room.py",
            "tools/verify_engel_meeting_room_lan_server.py",
            "tools/verify_engel_meeting_room_device_skill_routing.py",
            "tools/verify_engel_authoritative_meeting_room_completion.py",
        ],
        "keywords": ["meeting room", "agent room", "fake work", "animation", "job card", "room"],
    },
    "models": {
        "owner": "ct246_engel_ai_main",
        "services": ["engel-main-chat", "engel-local-model-worker"],
        "files": [
            "tools/engel_main_local_model_worker.py",
            "tools/engel_large_chat_llm.py",
            "tools/engel_model_promotion_gate.py",
            "memory/ENGEL_COSMOS3_COLLECTION_MANIFEST_V1.json",
        ],
        "verifiers": [
            "tools/verify_engel_model_inventory.py",
            "tools/verify_engel_model_promotion_gate.py",
            "tools/verify_engel_trained_lora_adapter_canary.py",
        ],
        "keywords": ["model", "adapter", "lora", "gguf", "quantized", "canary", "inference"],
    },
    "provider_bridges": {
        "owner": "rog_controller",
        "services": ["engel-main-chat", "ROG provider bridge workers"],
        "files": [
            "tools/engel_chatgpt_browser_bridge_http_service.py",
            "tools/engel_claude_cli_bridge_http_service.py",
            "tools/engel_codex_cli_bridge_http_service.py",
            "tools/engel_gemini_api_bridge_http_service.py",
            "tools/engel_grok_cli_bridge_http_service.py",
            "tools/engel_main_server_chat_http_service.py",
        ],
        "verifiers": [
            "tools/verify_engel_provider_bridge_chat_routing.py",
            "tools/verify_engel_chatgpt_browser_bridge.py",
        ],
        "keywords": ["provider", "bridge", "chatgpt", "claude", "codex", "grok", "gemini", "api"],
    },
    "workers": {
        "owner": "ct246_engel_ai_main",
        "services": ["engel-remote-worker-receiver", "engel-agent-meeting-room"],
        "files": [
            "remote_workers",
            "mobile/engel_remote_worker/lib/main.dart",
            "mobile/engel_remote_worker/lib/remote_worker_packet.dart",
            "mobile/engel_remote_worker/lib/remote_worker_result.dart",
            "tools/reconnect_engel_remote_workers.ps1",
        ],
        "verifiers": [
            "tools/verify_engel_fleet_capability_parity.py",
            "tools/verify_engel_multi_android_remote_workers.py",
            "tools/verify_engel_remote_worker_result_intake.py",
        ],
        "keywords": ["worker", "phone", "android", "alpha", "beta", "gamma", "claim", "return", "device"],
    },
    "sub_engel": {
        "owner": "sub_desktop",
        "services": ["Sub-Engel remote node", "engel-device-work-broker"],
        "files": [
            "remote_workers/windows_sub_engel",
            "remote_workers/sub_engel_os_worker",
            "tools/engel_sub_node_remote_control.py",
        ],
        "verifiers": [
            "tools/verify_engel_sub_node_remote_control.py",
            "tools/verify_engel_fleet_capability_parity.py",
        ],
        "keywords": ["sub-engel", "sub engel", "sub desktop", "pairing", "198.51.100.227", "training guard"],
    },
    "storage": {
        "owner": "ct246_engel_ai_main",
        "services": ["engel-runtime-path-boundary"],
        "files": [
            "tools/engel_runtime_path_normalizer.py",
            "memory/ENGEL_STORAGE_LOCATION_REGISTRY_V1.json",
            "memory/ENGEL_SYSTEM_TOPOLOGY_REGISTRY_V1.json",
        ],
        "verifiers": [
            "tools/verify_engel_runtime_path_normalizer.py",
            "tools/verify_engel_storage_location_registry.py",
        ],
        "keywords": ["storage", "disk", "ssd", "hdd", "archive", "mount", "path leak", "space"],
    },
    "desktop_ui": {
        "owner": "rog_controller",
        "services": ["EngelAIMain.exe"],
        "files": [
            "engel_flutter_main/lib/main.dart",
            "engel_flutter_main/test/widget_test.dart",
            "engel_flutter_main/windows/runner",
        ],
        "verifiers": [
            "tools/verify_engel_current_release_manifest.py",
            "engel_flutter_main/test/widget_test.dart",
        ],
        "keywords": ["ui", "desktop", "window", "panel", "button", "preview", "flutter", "screen"],
    },
    "self_upgrade": {
        "owner": "ct246_engel_ai_main",
        "services": ["engel-self-upgrade"],
        "files": [
            "engel_self_upgrade_system.py",
            "tools/engel_self_upgrade_router.py",
            "tools/engel_self_upgrade_apply_gate.py",
            "tools/engel_self_upgrade_apply_engine.py",
            "tools/engel_universal_reps_runtime.py",
            "tools/engel_conical_self_upgrade_cycle.py",
            "tools/engel_local_self_upgrade_planner.py",
            "tools/engel_self_patch_quorum.py",
            "tools/engel_deployment_rollback_automation.py",
            "tools/engel_conical_failure_to_issue.py",
            "tools/engel_self_upgrade_loop_stream.py",
            "tools/engel_primary_goal_completion_audit.py",
            "tools/engel_self_upgrade_catalog_router.py",
            "tools/engel_device_broker.py",
            "memory/ENGEL_PRIMARY_GOAL_V1.json",
            "memory/ENGEL_SELF_UPGRADE_SYSTEM_CATALOG_V1.json",
        ],
        "verifiers": [
            "tools/verify_engel_self_upgrade_system.py",
            "tools/verify_engel_runtime_path_normalizer.py",
            "tools/verify_engel_conical_self_upgrade_cycle.py",
            "tools/verify_engel_local_self_upgrade_planner.py",
            "tools/verify_engel_authoritative_meeting_room_completion.py",
            "tools/verify_engel_self_upgrade_http_api.py",
            "tools/verify_engel_self_patch_quorum.py",
            "tools/verify_engel_deployment_rollback_automation.py",
            "tools/verify_engel_conical_failure_to_issue.py",
            "tools/verify_engel_self_upgrade_loop_stream.py",
            "tools/verify_engel_primary_goal_completion_audit.py",
            "tools/verify_engel_self_upgrade_catalog_router.py",
            "tools/verify_engel_device_broker.py",
            "tools/verify_engel_dispatch_broker_wiring.py",
        ],
        "keywords": ["self upgrade", "self repair", "patch", "rollback", "reps", "goal", "goal completion", "acceptance criteria", "introspection", "cycle", "quorum", "catalog", "broker"],
    },
}


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _authority_location(relative: str) -> str:
    normalized = relative.replace("\\", "/")
    if normalized == "remote_workers/windows_sub_engel" or normalized.startswith("remote_workers/windows_sub_engel/"):
        return "sub_desktop"
    if normalized == "remote_workers/sub_engel_os_worker" or normalized.startswith("remote_workers/sub_engel_os_worker/"):
        return "sub_desktop"
    if normalized.startswith("engel_flutter_main/") or normalized.startswith("mobile/") or normalized.endswith(".ps1"):
        return "rog_controller"
    if any(
        normalized.startswith(prefix)
        for prefix in (
            "tools/engel_chatgpt_browser_bridge_",
            "tools/engel_claude_cli_bridge_",
            "tools/engel_codex_cli_bridge_",
            "tools/engel_gemini_api_bridge_",
            "tools/engel_grok_cli_bridge_",
        )
    ):
        return "rog_controller"
    return "ct246"


def _file_record(root: Path, relative: str) -> dict[str, Any]:
    path = root / relative
    exists = path.exists()
    is_file = exists and path.is_file()
    authority = _authority_location(relative)
    canonical_path = (
        "D:/b.WorkSpace/Engel App/" + relative
        if authority == "rog_controller"
        else "Sub-Engel managed source: " + relative
        if authority == "sub_desktop"
        else "/opt/engel/" + relative
    )
    record: dict[str, Any] = {
        "relative_path": relative,
        "authority_location": authority,
        "canonical_path": canonical_path,
        "exists_on_scan_root": exists,
        "kind": "file" if is_file else "directory" if exists else "declared",
    }
    if is_file:
        size = path.stat().st_size
        record["size_bytes"] = size
        record["sha256"] = _sha256(path) if size <= MAX_HASH_BYTES else "skipped_size_limit"
    return record


def build_inventory(root: Path = ROOT) -> dict[str, Any]:
    scan_root = root.resolve(strict=False)
    surfaces: dict[str, Any] = {}
    all_paths: set[str] = set()
    existing_count = 0
    for surface, rule in SURFACE_RULES.items():
        files = [_file_record(scan_root, path) for path in rule["files"]]
        verifiers = [_file_record(scan_root, path) for path in rule["verifiers"]]
        existing_count += sum(1 for item in files + verifiers if item["exists_on_scan_root"])
        all_paths.update(item["relative_path"] for item in files + verifiers)
        surfaces[surface] = {
            "surface": surface,
            "owner": rule["owner"],
            "services": list(rule["services"]),
            "files": files,
            "verifiers": verifiers,
            "failure_keywords": list(rule["keywords"]),
            "declared_file_count": len(files),
            "existing_file_count": sum(1 for item in files if item["exists_on_scan_root"]),
            "existing_verifier_count": sum(1 for item in verifiers if item["exists_on_scan_root"]),
        }
    return {
        "schema": "ENGEL_CODEBASE_OWNERSHIP_MAP_V1",
        "ok": True,
        "status": "inventory built",
        "goal": "Conical Agentic Sentient Self Upgrading System",
        "source_of_truth": "CT246 /opt/engel",
        "scan_root": str(scan_root),
        "controller_source_root": "D:/b.WorkSpace/Engel App",
        "surface_count": len(surfaces),
        "declared_unique_path_count": len(all_paths),
        "existing_path_reference_count": existing_count,
        "authority_locations": ["ct246", "rog_controller", "sub_desktop"],
        "surfaces": surfaces,
        "generated_at_utc": now_utc(),
    }


def write_inventory(payload: dict[str, Any], path: Path = INVENTORY_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temp, path)
    return path


def load_inventory(path: Path = INVENTORY_PATH) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"inventory missing: {path}")
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict) or payload.get("schema") != "ENGEL_CODEBASE_OWNERSHIP_MAP_V1":
        raise ValueError("inventory schema mismatch")
    return payload


def resolve_failure(text: str, inventory: dict[str, Any]) -> dict[str, Any]:
    lowered = str(text or "").casefold()
    normalized = " ".join(
        token
        for token in re.split(r"[^a-z0-9]+", lowered)
        if token
    )
    matches: list[dict[str, Any]] = []
    for surface, item in inventory.get("surfaces", {}).items():
        keywords = []
        for word in item.get("failure_keywords", []):
            normalized_word = " ".join(
                token
                for token in re.split(r"[^a-z0-9]+", str(word).casefold())
                if token
            )
            if normalized_word and normalized_word in normalized:
                keywords.append(word)
        surface_phrase = " ".join(
            token
            for token in re.split(r"[^a-z0-9]+", str(surface).casefold())
            if token
        )
        surface_named = bool(surface_phrase and surface_phrase in normalized)
        if not keywords:
            if not surface_named:
                continue
        matches.append(
            {
                "surface": surface,
                "score": len(keywords) + (4 if surface_named else 0),
                "matched_keywords": keywords,
                "surface_named": surface_named,
                "owner": item.get("owner"),
                "services": item.get("services", []),
                "files": [entry.get("relative_path") for entry in item.get("files", [])],
                "verifiers": [entry.get("relative_path") for entry in item.get("verifiers", [])],
            }
        )
    matches.sort(key=lambda item: (-int(item["score"]), str(item["surface"])))
    return {
        "schema": "ENGEL_FAILURE_OWNER_RESOLUTION_V1",
        "ok": bool(matches),
        "status": "owner resolved" if matches else "no owner match",
        "failure_text": text,
        "primary": matches[0] if matches else None,
        "matches": matches,
        "resolved_at_utc": now_utc(),
    }


def _emit(payload: dict[str, Any], exit_on_false: bool = False) -> int:
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 1 if exit_on_false and payload.get("ok") is not True else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Engel codebase inventory and ownership map.")
    sub = parser.add_subparsers(dest="command", required=True)
    scan = sub.add_parser("scan")
    scan.add_argument("--root", default=str(ROOT))
    scan.add_argument("--output", default=str(INVENTORY_PATH))
    sub.add_parser("status")
    owners = sub.add_parser("owners")
    owners.add_argument("--surface", required=True, choices=sorted(SURFACE_RULES))
    resolve = sub.add_parser("resolve-failure")
    resolve.add_argument("--text", required=True)
    args = parser.parse_args(argv)

    try:
        if args.command == "scan":
            payload = build_inventory(Path(args.root))
            output = write_inventory(payload, Path(args.output))
            payload["inventory_path"] = str(output)
            return _emit(payload)
        inventory = load_inventory()
        if args.command == "status":
            return _emit(
                {
                    "schema": "ENGEL_CODEBASE_INVENTORY_STATUS_V1",
                    "ok": True,
                    "status": inventory.get("status"),
                    "goal": inventory.get("goal"),
                    "inventory_path": str(INVENTORY_PATH),
                    "generated_at_utc": inventory.get("generated_at_utc"),
                    "surface_count": inventory.get("surface_count"),
                    "declared_unique_path_count": inventory.get("declared_unique_path_count"),
                    "existing_path_reference_count": inventory.get("existing_path_reference_count"),
                }
            )
        if args.command == "owners":
            return _emit(inventory["surfaces"][args.surface])
        if args.command == "resolve-failure":
            return _emit(resolve_failure(args.text, inventory), exit_on_false=True)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return _emit({"schema": "ENGEL_CODEBASE_INVENTORY_ERROR_V1", "ok": False, "error": str(exc)}, True)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
