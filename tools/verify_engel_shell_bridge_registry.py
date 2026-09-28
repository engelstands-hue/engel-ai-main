#!/usr/bin/env python3
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from engel_patch_permission_matrix import build_matrix  # noqa: E402
from engel_shell_bridge_registry import (  # noqa: E402
    REQUIRED_BRIDGE_IDS,
    _chat_receipt_success,
    atomic_write_json,
    build_registry,
    status,
    validate_registry,
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def fixture_health(now: datetime) -> dict:
    provider = lambda enabled=True, usable=True, secret=False, route=True: {
        "enabled": enabled,
        "usable": usable,
        "secret_present": secret,
        "local_route": {"enabled": True, "ok": route},
    }
    workers = {
        worker_id: {
            "label": worker_id,
            "paired": True,
            "live": True,
            "authenticated_presence": True,
            "last_seen_utc": iso(now),
        }
        for worker_id in ("android_worker_alpha", "android_worker_beta", "android_worker_gamma")
    }
    return {
        "ok": True,
        "model_runtime": {
            "local_gguf_model_present": True,
            "lora_runtime_ready": True,
            "long_lived_local_model_service": "1",
        },
        "provider_bridges": {
            "providers": {
                "openai": provider(secret=True, route=False),
                "anthropic": provider(secret=False, route=True),
                "xai": provider(usable=False, route=False),
                "gemini": provider(secret=True, route=True),
                "codex": provider(secret=False, route=True),
            }
        },
        "phone_bridge": {"ok": True, "workers": workers},
        "sub_engel_bridge": {
            "ok": True,
            "workers": {
                "DESKTOP-UE5A6GG": {
                    "label": "Windows Sub-Engel",
                    "paired": True,
                    "live": False,
                    "meeting_ready": True,
                    "last_seen_utc": iso(now - timedelta(days=4)),
                    "allowed_actions": ["main.shell", "disk.control"],
                    "latest_return": {"present": False},
                }
            },
        },
        "universal_reps_runtime": {
            "ok": True,
            "recent_events": [
                {
                    "event_id": "reps_event_fixture",
                    "kind": "verification",
                    "updated_at_utc": iso(now),
                }
            ],
        },
        "self_model": {
            "ok": True,
            "state_revision": 4,
            "state_sha256": "a" * 64,
            "observed_at_utc": iso(now),
        },
    }


def main() -> int:
    now = datetime(2026, 7, 22, 3, 0, tzinfo=timezone.utc)
    with tempfile.TemporaryDirectory(prefix="engel_bridge_registry_") as temporary:
        root = Path(temporary)
        atomic_write_json(
            root / "memory" / "self_update" / "patch_permission_matrix.json",
            build_matrix(),
        )
        receipts = root / "reports" / "engel_standalone_chat_llm" / "chat_receipts"
        write_json(
            receipts / "local.json",
            {
                "ok": True,
                "selected_provider": "local",
                "provider": "local-llama-cpp-large-chat-gguf",
                "runtime_provider": "fixture-local",
                "status": "large local chat replied",
                "assistant_reply": "Local completion proof.",
                "updated_at_utc": iso(now),
            },
        )
        write_json(
            receipts / "claude.json",
            {
                "ok": True,
                "selected_provider": "anthropic",
                "provider": "Claude/Anthropic",
                "runtime_provider": "sonnet",
                "status": "provider bridge replied",
                "provider_bridge_used": True,
                "provider_reply_quality_gate_passed": True,
                "provider_final_semantic_quality": {"ok": True},
                "assistant_reply": "Qualified provider completion proof.",
                "updated_at_utc": iso(now),
            },
        )
        require(
            _chat_receipt_success(
                {
                    "ok": True,
                    "selected_provider": "gemini",
                    "status": "provider bridge unavailable",
                    "provider_bridge_used": False,
                    "assistant_reply": "Provider unavailable.",
                },
                "gemini",
            )
            is False,
            "top-level ok unavailable receipt became a provider completion",
        )
        write_json(
            root
            / "remote_workers"
            / "communication_queen_assignments"
            / "returned"
            / "alpha.json",
            {
                "worker_id": "android_worker_alpha",
                "result_type": "bounded_task_result",
                "completed_at_utc": iso(now),
            },
        )
        room = {
            "ok": True,
            "server_owned": True,
            "latest_order": {
                "order_id": "MAIN-FIXTURE",
                "completed_at": iso(now),
            },
        }
        registry = build_registry(
            fixture_health(now),
            root=root,
            meeting_room=room,
            service_states={"engel-discord-bridge.service": True},
            observed_at=now,
        )
        bridges = registry["bridges"]
        require(registry["ok"] is True, str(registry.get("validation_errors")))
        require(REQUIRED_BRIDGE_IDS.issubset(bridges), "required bridge set incomplete")
        require(bridges["local_llm"]["usable"] is True, "local completion proof not accepted")
        require(bridges["claude"]["usable"] is True, "Claude completion proof not accepted")
        require(bridges["gemini"]["connected"] is True, "Gemini fixture should be connected")
        require(bridges["gemini"]["usable"] is False, "connected provider became usable without completion")
        require("gemini" in registry["connected_without_completion_proof"], "false-green provider not exposed")
        require(bridges["sub_engel"]["connected"] is False, "stale paired Sub was treated as connected")
        require(bridges["sub_engel"]["usable"] is False, "stale paired Sub was treated as usable")
        require(bridges["android_worker_alpha"]["usable"] is True, "fresh phone return not accepted")
        require(bridges["android_worker_beta"]["connected"] is True, "live beta fixture not connected")
        require(bridges["android_worker_beta"]["usable"] is False, "heartbeat became completion proof")
        require(bridges["discord"]["connected"] is True, "Discord service state not registered")
        require(bridges["discord"]["usable"] is False, "Discord process became completion proof")

        for bridge_id, item in bridges.items():
            require(item["authority_scope"].get("approve_protected") != "allow", f"{bridge_id} can approve")
            require(not (item["usable"] and not item["completion_proven"]), f"{bridge_id} false-green")
        serialized = json.dumps(registry, sort_keys=True).casefold()
        for secret_key in ("secret_source", "value_length", "api_key", "access_token", "refresh_token"):
            require(secret_key not in serialized, f"secret metadata leaked: {secret_key}")

        path = root / "run" / "self_update" / "bridges" / "bridge_registry.json"
        atomic_write_json(path, registry)
        fresh = status(path, observed_at=now + timedelta(seconds=10))
        require(fresh["registry_fresh"] is True, "fresh registry marked stale")
        stale = status(path, observed_at=now + timedelta(hours=1))
        require(stale["registry_fresh"] is False, "stale registry marked fresh")
        require(not stale["usable_bridge_ids"], "stale registry kept usable bridges")

        tampered = deepcopy(registry)
        tampered["bridges"]["gemini"]["usable"] = True
        valid, errors = validate_registry(tampered)
        require(valid is False and errors, "usable-without-proof tamper was accepted")

    checks = [
        "required_bridge_inventory",
        "connection_separate_from_completion",
        "local_and_provider_completion_receipts",
        "sub_live_pairing_truth",
        "android_heartbeat_not_completion",
        "discord_owner_and_public_scope",
        "no_bridge_self_approval",
        "no_secret_metadata",
        "stale_registry_fail_closed",
        "tamper_rejection",
    ]
    for check in checks:
        print(f"PASS {check}")
    print("ENGEL_SHELL_BRIDGE_REGISTRY_VERIFY_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
