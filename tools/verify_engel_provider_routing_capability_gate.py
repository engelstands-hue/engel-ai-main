#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import importlib.util
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
SERVICE_PATH = TOOLS / "engel_main_server_chat_http_service.py"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def load_service():
    spec = importlib.util.spec_from_file_location("engel_provider_routing_gate_under_test", SERVICE_PATH)
    require(spec is not None and spec.loader is not None, "chat service could not load")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def capability_map(observed: datetime) -> dict[str, Any]:
    providers: dict[str, dict[str, Any]] = {}
    for provider in ("local", "openai", "anthropic", "xai", "gemini", "codex", "nvidia"):
        automatic = provider == "anthropic"
        providers[provider] = {
            "provider_id": provider,
            "enabled": True,
            "connected": provider != "xai",
            "completion_proven": provider in {"local", "anthropic"},
            "automatic_routable": automatic,
            "explicit_attempt_allowed": provider != "local",
            "last_automatic_route_proof": (
                {"automatic_route_qualified": True} if provider in {"local", "anthropic"} else {}
            ),
        }
    return {
        "schema": "ENGEL_PROVIDER_COMPLETION_CAPABILITY_MAP_V1",
        "ok": True,
        "observed_at_utc": observed.isoformat().replace("+00:00", "Z"),
        "providers": providers,
        "automatic_provider_ids": ["anthropic"],
        "degraded_provider_ids": ["openai", "xai", "gemini", "codex", "nvidia"],
        "outage_provider_ids": ["xai"],
        "connection_is_not_completion": True,
    }


def main() -> int:
    service = load_service()
    now = datetime.now(timezone.utc)
    current_map = capability_map(now)
    old_cache = service._cached_snapshot
    old_values = {
        key: os.environ.get(key)
        for key in (
            "ENGEL_AUTO_BRIDGE_ROUTING_ENABLED",
            "ENGEL_GEMINI_BRIDGE_ENABLED",
        )
    }

    def fake_cache(name: str, builder, ttl_seconds: float | None = None):
        if name == "provider_capabilities":
            return current_map
        return old_cache(name, builder, ttl_seconds)

    try:
        os.environ["ENGEL_AUTO_BRIDGE_ROUTING_ENABLED"] = "1"
        os.environ["ENGEL_GEMINI_BRIDGE_ENABLED"] = "1"
        service._cached_snapshot = fake_cache

        candidates, reason = service._provider_candidates_for_prompt(
            "Please review and debug this Python code.",
            {"_automatic_local_failure_fallback": True},
        )
        require(reason == "code_or_review", "coding route classification changed")
        require(candidates == ["anthropic"], "automatic route admitted an unproved provider")

        candidates, reason = service._provider_candidates_for_prompt(
            "Use Gemini for this answer.",
            {"provider": "gemini", "force_provider": True},
        )
        require(reason == "explicit_provider", "explicit provider route was not preserved")
        require(candidates == ["gemini"], "degraded explicit owner provider was blocked")

        stale_map = capability_map(now - timedelta(minutes=10))
        current_map.clear()
        current_map.update(stale_map)
        candidates, reason = service._provider_candidates_for_prompt(
            "Debug this API code.",
            {"_automatic_local_failure_fallback": True},
        )
        require(reason == "code_or_review", "stale-map route classification changed")
        require(candidates == [], "stale capability map did not fail closed")

        # (2026-08-14) INVOKED vs MENTIONED: a provider name in conversation must not
        # become an explicit route. Live loop: "is grok working?" routed to the
        # unloaded xai bridge -> canned "Grok/xAI ... is not usable" -> the follow-up
        # question about that message contained "grok" again, forever.
        for mention in (
            "is grok working?",
            "why does it say grok is not usable right now?",
            "what do you think about claude?",
            "the grok bridge has no secret loaded",
            "I googled the error message yesterday",
        ):
            _, reason = service._provider_candidates_for_prompt(mention, {})
            require(
                reason != "explicit_provider",
                f"a mere mention routed as explicit: {mention!r} -> {reason}",
            )
        for directive in (
            "ask grok to check this",
            "grok, what do you think?",
            "switch to gemini for this one",
            "use claude for the review",
        ):
            _, reason = service._provider_candidates_for_prompt(directive, {})
            require(
                str(reason).startswith("explicit_provider"),
                f"a genuine directive no longer routes: {directive!r} -> {reason}",
            )
        _, reason = service._provider_candidates_for_prompt(
            "don't use grok, answer locally", {}
        )
        require(
            reason != "explicit_provider",
            "a negated provider directive still routed",
        )

        # CT's desktop worker carries the turn budget in ``timeout`` while
        # provider adapters historically read only ``timeout_seconds``.  Keep
        # both fields covered so a longer user-approved turn reaches every
        # provider instead of silently reverting to the short bridge default.
        require(
            service._provider_request_timeout_seconds(
                {"timeout": 90}, 18, minimum=15, maximum=300
            )
            == 90,
            "provider timeout did not inherit the CT/UI timeout field",
        )
        require(
            service._provider_request_timeout_seconds(
                {"timeout": 90, "timeout_seconds": 45},
                18,
                minimum=15,
                maximum=300,
            )
            == 45,
            "explicit provider timeout_seconds did not take precedence",
        )
        require(
            service._provider_request_timeout_seconds(
                {"timeout": 900}, 18, minimum=15, maximum=300
            )
            == 300,
            "provider timeout ceiling was not enforced",
        )

        print("PASS automatic_routes_require_fresh_completion_proof")
        print("PASS degraded_explicit_owner_route_remains_attemptable")
        print("PASS stale_capability_map_fails_closed")
        print("PASS provider_mention_does_not_route")
        print("PASS provider_directive_still_routes")
        print("PASS provider_timeout_contract_accepts_ui_budget")
        print("PASS provider_timeout_contract_preserves_explicit_budget")
        print("PASS provider_timeout_contract_clamps_ceiling")
        print("ENGEL_PROVIDER_ROUTING_CAPABILITY_GATE_VERIFY_PASS")
        return 0
    finally:
        service._cached_snapshot = old_cache
        for key, value in old_values.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


if __name__ == "__main__":
    raise SystemExit(main())
