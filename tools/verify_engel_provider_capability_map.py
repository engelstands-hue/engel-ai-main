#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
import tempfile


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools" / "engel_provider_capability_map.py"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def load_module():
    spec = importlib.util.spec_from_file_location("engel_provider_capability_map_under_test", MODULE_PATH)
    require(spec is not None and spec.loader is not None, "module could not load")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_receipt(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def integrated(provider: str, when: datetime, *, success: bool, quality: bool, route: str, model: str) -> dict:
    return {
        "schema": "engel_main_server_provider_bridge_chat_receipt_v1",
        "ok": True,
        "status": "provider bridge replied" if success else "provider bridge unavailable",
        "updated_at_utc": when.isoformat().replace("+00:00", "Z"),
        "selected_provider": provider,
        "provider_bridge_used": success,
        "provider_reply_quality_gate_passed": quality,
        "provider_final_semantic_quality": {"ok": quality},
        "provider_bridge_route_reason": route,
        "runtime_provider": model,
        "assistant_reply": "verified fixture reply" if success else "provider unavailable",
        "prompt": "fixture prompt must never enter the map",
        "secret_source": {"value_length": 99},
    }


def direct(schema: str, when: datetime, *, success: bool, model: str) -> dict:
    return {
        "schema": schema,
        "ok": success,
        "status": "direct completion returned" if success else "direct completion failed",
        "updated_at_utc": when.isoformat().replace("+00:00", "Z"),
        "runtime_provider": model,
        "assistant_reply": "direct reply" if success else "",
    }


def health(module, *, connected: dict[str, bool]) -> tuple[dict, dict]:
    bridges = {}
    provider_status = {"providers": {}}
    for provider, definition in module.PROVIDERS.items():
        bridges[definition["bridge_id"]] = {
            "enabled": True,
            "connected": connected.get(provider, True),
            "completion_proven": False,
            "usable": False,
        }
        if provider != "local":
            provider_status["providers"][provider] = {
                "enabled": True,
                "secret_present": connected.get(provider, True),
                "local_route": {"ok": connected.get(provider, True)},
            }
    return {"bridges": bridges}, provider_status


def main() -> int:
    module = load_module()
    observed = datetime(2026, 7, 22, 3, 0, tzinfo=timezone.utc)
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        receipt_root = root / "reports" / "engel_standalone_chat_llm" / "chat_receipts"
        write_receipt(
            receipt_root / "local.json",
            {
                "schema": "engel_standalone_chat_llm_reply_v1",
                "ok": True,
                "status": "large local chat replied",
                "updated_at_utc": (observed - timedelta(minutes=2)).isoformat(),
                "selected_provider": "local",
                "runtime_provider": "local-model",
                "assistant_reply": "local fixture reply",
            },
        )
        write_receipt(receipt_root / "claude.json", integrated("anthropic", observed - timedelta(minutes=4), success=True, quality=True, route="code_or_review", model="sonnet"))
        write_receipt(receipt_root / "openai_success.json", integrated("openai", observed - timedelta(hours=2), success=True, quality=True, route="chat_or_customer", model="gpt-test"))
        write_receipt(
            root / "reports" / "chatgpt_browser_bridge" / "failure.json",
            direct("engel_chatgpt_browser_bridge_chat_receipt_v1", observed - timedelta(minutes=1), success=False, model="browser"),
        )
        write_receipt(
            root / "reports" / "gemini_api_bridge" / "direct_only.json",
            direct("engel_gemini_api_bridge_chat_receipt_v1", observed - timedelta(minutes=3), success=True, model="gemini-test"),
        )
        write_receipt(receipt_root / "codex_stale.json", integrated("codex", observed - timedelta(days=2), success=True, quality=True, route="code_or_review", model="codex-test"))
        write_receipt(receipt_root / "xai_unavailable.json", integrated("xai", observed - timedelta(minutes=5), success=False, quality=False, route="current_or_social", model=""))

        bridge_registry, provider_status = health(module, connected={"xai": False})
        state_path = root / "map.json"
        payload = module.build_capability_map(
            bridge_registry,
            provider_status,
            root=root,
            observed_at=observed,
            persist=True,
            state_path=state_path,
        )
        errors = module.validate_capability_map(payload, observed_at=observed)
        require(not errors, "map validation failed: " + ", ".join(errors))
        providers = payload["providers"]
        require(providers["local"]["completion_proven"] is True, "local completion missing")
        require(providers["local"]["automatic_routable"] is False, "local model was mislabeled as provider escalation")
        require(providers["local"]["degraded"] is False, "healthy local completion was marked degraded")
        require(providers["anthropic"]["automatic_routable"] is True, "fresh Claude completion should route")
        require(providers["anthropic"]["last_successful_model"] == "sonnet", "last model missing")
        require(providers["anthropic"]["proven_task_families"][0]["task_family"] == "coding_review", "evidence-backed strength missing")
        require(providers["openai"]["automatic_routable"] is False, "newer failure must degrade OpenAI")
        require(providers["openai"]["outage"] is True, "OpenAI outage missing")
        require(providers["gemini"]["connected"] is True, "Gemini connection fixture missing")
        require(providers["gemini"]["automatic_routable"] is False, "direct-only success must not auto-route")
        require(providers["codex"]["automatic_routable"] is False, "stale Codex proof must fail closed")
        require(providers["xai"]["automatic_routable"] is False, "disconnected Grok must not route")
        require(
            module.filter_automatic_candidates(
                ["openai", "anthropic", "gemini", "codex"],
                payload,
                observed_at=observed,
            )
            == ["anthropic"],
            "automatic filter mismatch",
        )
        require(module.explicit_attempt_allowed("openai", payload) is True, "explicit degraded attempt should remain allowed")

        serialized = json.dumps(payload).casefold()
        for forbidden in ["fixture prompt", "verified fixture reply", "secret_source", "value_length"]:
            require(forbidden not in serialized, "sensitive/content field leaked: " + forbidden)

        stale = module.load_status(state_path, observed_at=observed + timedelta(seconds=module.MAP_MAX_AGE_SECONDS + 1))
        require(stale["ok"] is False and stale["automatic_provider_ids"] == [], "stale map did not fail closed")

        unavailable = integrated("gemini", observed - timedelta(minutes=1), success=False, quality=False, route="explicit_provider", model="")
        write_receipt(receipt_root / "gemini_unavailable.json", unavailable)
        second = module.build_capability_map(bridge_registry, provider_status, root=root, observed_at=observed, persist=False)
        require(second["providers"]["gemini"]["completion_proven"] is False, "ok:true unavailable receipt counted as completion")

    print("ENGEL_PROVIDER_CAPABILITY_MAP_VERIFY_PASS")
    print("- connected state remains separate from completion proof")
    print("- newer failures, stale proofs, and direct-only proofs fail closed for automatic routing")
    print("- explicit owner attempts remain available for enabled degraded providers")
    print("- model, receipt, and evidence-backed task strengths are recorded without prompt/reply or secret metadata")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
