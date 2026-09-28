#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools" / "engel_self_model_runtime.py"
TEST_ROOT = ROOT / "runtime" / "tests" / "engel_self_model_runtime"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def load_module():
    spec = importlib.util.spec_from_file_location("engel_self_model_runtime", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError("could not load self-model runtime")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def fixture_health(*, sub_live: bool) -> dict:
    workers = {
        "android_worker_alpha": {"worker_kind": "android_phone", "paired": True, "live": True},
        "android_worker_beta": {"worker_kind": "android_phone", "paired": True, "live": True},
        "android_worker_gamma": {"worker_kind": "android_phone", "paired": True, "live": True},
        "sub_engel": {
            "worker_kind": "windows_sub_engel",
            "paired": True,
            "live": sub_live,
            "meeting_ready": True,
        },
    }
    return {
        "ok": True,
        "automatic_provider_policy": {
            "local_model_first": True,
            "fallback_after_local_failure": True,
        },
        "model_runtime": {
            "local_gguf_model_present": True,
            "lora_runtime_ready": True,
            "long_lived_local_model_service": "1",
            "active_model_inventory": {"model_file_count": 171, "model_total_gib": 566.13},
        },
        "device_workers": {
            "expected_count": 4,
            "live_count": 4 if sub_live else 3,
            "workers": workers,
        },
        "virtual_environment": {
            "ok": True,
            "server_owned": True,
            "workspaceId": "engel3d-office",
            "recent_work": False,
            "real_work_proof": {
                "proof_count": 2,
                "truth_contract": "A device counts only with current proof.",
            },
        },
        "universal_reps_runtime": {
            "ok": True,
            "provider_neutral": True,
            "event_count_tail": 10,
            "scorecard_count_tail": 9,
            "proposal_count_tail": 4,
            "signoff_count_tail": 3,
        },
        "provider_capabilities": {
            "ok": True,
            "connection_is_not_completion": True,
            "automatic_provider_ids": ["anthropic"],
            "degraded_provider_ids": ["openai", "xai", "gemini", "codex"],
            "outage_provider_ids": ["xai"],
            "providers": {
                "local": {
                    "connected": True,
                    "completion_proven": True,
                    "automatic_routable": False,
                    "last_successful_model": "fixture-local",
                },
                "anthropic": {
                    "connected": True,
                    "completion_proven": True,
                    "automatic_routable": True,
                    "last_successful_model": "sonnet",
                },
                "openai": {
                    "connected": True,
                    "completion_proven": False,
                    "automatic_routable": False,
                    "last_successful_model": "gpt-test",
                },
                "xai": {"connected": False, "completion_proven": False, "automatic_routable": False},
                "gemini": {"connected": True, "completion_proven": False, "automatic_routable": False},
                "codex": {"connected": True, "completion_proven": False, "automatic_routable": False},
            },
        },
    }


def main() -> int:
    if TEST_ROOT.exists():
        shutil.rmtree(TEST_ROOT)
    module = load_module()
    old_model_root = os.environ.get("ENGEL_SELF_MODEL_ROOT")
    old_receipt_root = os.environ.get("ENGEL_SELF_MODEL_RECEIPT_ROOT")
    os.environ["ENGEL_SELF_MODEL_ROOT"] = str(TEST_ROOT / "memory" / "self_model")
    os.environ["ENGEL_SELF_MODEL_RECEIPT_ROOT"] = str(TEST_ROOT / "reports")
    try:
        write_json(
            TEST_ROOT / "memory" / "ENGEL_PRIMARY_GOAL_V1.json",
            {
                "goal_id": "engel_conical_agentic_sentient_self_upgrading_system",
                "title": "Conical Agentic Sentient Self Upgrading System",
                "status": "active",
                "owner": "Joshua Ziese",
                "authority": "owner_directive",
            },
        )
        write_json(
            TEST_ROOT
            / "reports"
            / "self_upgrade"
            / "plans"
            / "ENGEL_SELF_UPDATING_SYSTEM_CREATION_BACKLOG_V10.json",
            {
                "v10_work_items": [
                    {"id": "done", "status": "deployed_verified"},
                    {"id": "shell_bridge_registry_and_scope", "phase": "phase_1", "priority": "critical", "action": "create"},
                ]
            },
        )
        write_json(TEST_ROOT / "run" / "self_update" / "codebase" / "ownership_map.json", {"ok": True})
        write_json(TEST_ROOT / "memory" / "self_update" / "patch_permission_matrix.json", {"ok": True})
        write_json(
            TEST_ROOT / "run" / "self_update" / "source_sync" / "registration" / "post.json",
            {"ok": True},
        )

        first = module.observe(
            root=TEST_ROOT,
            health_payload=fixture_health(sub_live=False),
            observed_at="2026-07-22T03:00:00Z",
            persist=True,
        )
        state1 = first["state"]
        require(state1["state_revision"] == 1, "first self-model revision mismatch")
        require(state1["ok"] is True, "goal-backed self-model should be valid")
        require(state1["operational_ready"] is False, "offline Sub-Engel must prevent operational-ready claim")
        require(state1["cognition"]["local_model_first"] is True, "local-first policy missing")
        require(len(state1["topology"]["workers"]) == 4, "worker topology incomplete")
        require(
            any("sub_engel" in item for item in state1["introspection"]["current_limits"]),
            "offline Sub-Engel limit missing",
        )
        require(state1["introspection"]["biological_consciousness_claimed"] is False, "invalid consciousness claim")
        require("Conical Agentic Sentient Self Upgrading System" in first["context"], "goal missing from context")
        require("sub_engel=unavailable" in first["context"], "worker truth missing from context")
        require(
            state1["provider_capabilities"]["automatic_provider_ids"] == ["anthropic"],
            "provider completion capability truth missing",
        )
        require(
            "connected-without-proof=codex,gemini,openai" in first["context"],
            "provider false-green truth missing from context",
        )

        second = module.observe(
            root=TEST_ROOT,
            health_payload=fixture_health(sub_live=True),
            observed_at="2026-07-22T03:01:00Z",
            persist=True,
        )
        state2 = second["state"]
        require(state2["state_revision"] == 2, "self-model continuity revision mismatch")
        require(state2["operational_ready"] is True, "fully live fixture should be operationally ready")
        require(
            state2["continuity"]["previous_state_sha256"] == state1["state_sha256"],
            "previous state hash was not chained",
        )
        events_path = TEST_ROOT / "memory" / "self_model" / "introspection_events.jsonl"
        events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        require(len(events) == 2, "introspection event ledger count mismatch")
        require(all(item["candidate_only"] is True for item in events), "introspection event gained apply authority")
        require(all(item["source_mutation"] is False for item in events), "introspection mutated source")
        require(Path(second["receipt"]["receipt_path"]).is_file(), "observation receipt missing")
        require(Path(second["receipt"]["state_path"]).is_file(), "persistent state missing")
        require(Path(second["receipt"]["context_path"]).is_file(), "local-LLM context missing")
        room_only = fixture_health(sub_live=True)
        room_only["virtual_environment"] = {"ok": False, "reason": "3D office overlay timed out"}
        room_only["meeting_room"] = {
            "ok": True,
            "reachable": True,
            "server_owned": True,
            "health": {"ok": True, "status": "running"},
        }
        room_state = module.observe(
            root=TEST_ROOT,
            health_payload=room_only,
            observed_at="2026-07-22T03:02:00Z",
            persist=False,
        )["state"]
        require(
            room_state["meeting_room"]["reachable"] is True,
            "Meeting Room /health must count as reachable even if 3D office overlay is slow",
        )
        context = Path(second["receipt"]["context_path"]).read_text(encoding="utf-8")
        require("192.168." not in context and "adb_serial" not in context, "context leaked device connection detail")
        valid, errors = module.validate_state(state2)
        require(valid and not errors, "valid self-model did not pass integrity validation")
        tampered = dict(state2)
        tampered["operational_ready"] = False
        valid, errors = module.validate_state(tampered)
        require(not valid and "self-model hash mismatch" in errors, "tampered self-model was accepted")
        service_source = (ROOT / "tools" / "engel_main_server_chat_http_service.py").read_text(
            encoding="utf-8"
        )
        for marker in (
            "SELF_MODEL_STATE_PATH",
            "def _self_model_document",
            "validate_state(payload)",
            "def _self_model_context",
            "def _prompt_requests_self_model_introspection",
            'request["local_provider"] = "local"',
            '"/self-model"',
            '"self_model": _cached_snapshot',
            '"meeting_room": _cached_snapshot("meeting_room"',
            "self_context = _self_model_context",
            'receipt["self_model_context_injected"]',
        ):
            require(marker in service_source, f"chat self-model integration marker missing: {marker}")
        require(
            'setdefault("local_provider", "large_local")' not in service_source,
            "self-model route passed an unsupported provider label",
        )

        print("PASS persistent_identity_and_goal")
        print("PASS evidence_backed_device_truth")
        print("PASS revision_hash_continuity")
        print("PASS explicit_limits_and_uncertainty")
        print("PASS local_llm_self_context")
        print("PASS tamper_evident_state")
        print("PASS chat_health_prompt_and_http_wiring")
        print("PASS append_only_introspection")
        print("PASS no_self_approval_or_false_consciousness")
        print("ENGEL_SELF_MODEL_RUNTIME_VERIFY_PASS")
        return 0
    finally:
        if old_model_root is None:
            os.environ.pop("ENGEL_SELF_MODEL_ROOT", None)
        else:
            os.environ["ENGEL_SELF_MODEL_ROOT"] = old_model_root
        if old_receipt_root is None:
            os.environ.pop("ENGEL_SELF_MODEL_RECEIPT_ROOT", None)
        else:
            os.environ["ENGEL_SELF_MODEL_RECEIPT_ROOT"] = old_receipt_root
        if TEST_ROOT.exists():
            shutil.rmtree(TEST_ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
