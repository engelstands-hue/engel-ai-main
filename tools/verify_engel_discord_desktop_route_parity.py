#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import tempfile

from engel_discord_desktop_route_parity import (
    DISCORD_IDENTITY_LOCK,
    SHARED_IDENTITY_GUARD,
    SHARED_ROUTE_CONTRACT,
    finalize_surface_turn,
    repair_joshua_chase_fusion,
    repair_surface_identity,
    status_snapshot,
)


ROOT = Path(__file__).resolve().parents[1]
MAIN_SERVICE = ROOT / "tools" / "engel_main_server_chat_http_service.py"
DISCORD_BRIDGE = ROOT / "tools" / "engel_discord_bridge.py"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    failures: list[str] = []
    try:
        with tempfile.TemporaryDirectory(prefix="engel-route-parity-") as raw:
            temp = Path(raw)
            ledger = temp / "route_ledger.jsonl"
            corpus = temp / "chat_failures.jsonl"
            desktop = finalize_surface_turn(
                prompt="Which file should I open?",
                reply="Open src/main.py, Engel.",
                receipt={
                    "ok": True,
                    "status": "large local chat replied",
                    "provider": "local-llama-cpp-large-chat-gguf",
                    "selected_provider": "local",
                    "provider_api_enabled": False,
                    "chat_context_scope": "engel_ai_main_desktop:test",
                },
                request={"source": "engel_ai_main_ui", "provider": "local"},
                source="verifier-desktop",
                stage="http-final",
                ledger_path=ledger,
                corpus_path=corpus,
                root=temp,
            )
            require(desktop["reply"] == "Open src/main.py.", "desktop shared identity guard did not repair Engel vocative")
            require(desktop["identity_guard"]["schema"] == SHARED_IDENTITY_GUARD, "desktop identity guard contract mismatch")

            self_claim = finalize_surface_turn(
                prompt="Call me Joshua.",
                reply="You can find me as Joshua.",
                receipt={
                    "ok": True,
                    "provider": "local-llama-cpp-large-chat-gguf",
                    "selected_provider": "local",
                    "runtime_provider": "rog-rtx2070-llama-cpp-gpu",
                    "provider_api_enabled": False,
                    "chat_context_scope": "engel_ai_main_desktop:self-claim",
                    "training_sample_eligible": True,
                },
                request={"source": "engel_ai_main_ui", "provider": "local"},
                source="verifier-desktop-self-claim",
                stage="http-final",
                ledger_path=ledger,
                corpus_path=corpus,
                root=temp,
            )
            require("find me as Joshua" not in self_claim["reply"], "assistant Joshua self-claim was not repaired")
            require(
                self_claim["receipt"].get("training_sample_eligible") is False,
                "repaired assistant identity sample remained training eligible",
            )

            discord_request = {
                "source": "discord",
                "provider": "local",
                "metadata": {
                    "discord_identity_lock": DISCORD_IDENTITY_LOCK,
                    "discord_channel_id": "test-channel",
                    "discord_author_id": "189914577100603392",
                    "discord_resolved_actor": "chase_lokal",
                    "discord_authority_level": "guest",
                    "discord_author_display_name": "Chase/Lokal",
                    "discord_addressed_as": "Chase/Lokal",
                },
            }
            discord = finalize_surface_turn(
                prompt="Who am I?",
                reply="You are Joshua.",
                receipt={
                    "ok": True,
                    "status": "large local chat replied",
                    "provider": "local-llama-cpp-large-chat-gguf",
                    "selected_provider": "local",
                    "provider_api_enabled": False,
                    "chat_context_scope": "discord:test-channel:guest",
                },
                request=discord_request,
                source="verifier-discord",
                stage="discord-public-delivery",
                ledger_path=ledger,
                corpus_path=corpus,
                root=temp,
            )
            require("Joshua" not in discord["reply"], "Discord guest was still identified as Joshua")
            require("Chase/Lokal" in discord["reply"], "Discord guest identity was not repaired to the locked actor")
            require(discord["identity_guard"]["schema"] == SHARED_IDENTITY_GUARD, "Discord identity guard contract mismatch")
            failure = discord["failure_capture"]
            require(failure.get("captured") is True, "bad Discord reply did not enter failure corpus")
            require("identity_mixup" in failure.get("failure_types", []), "Discord identity failure type missing")
            require(Path(failure.get("corpus_path", "")) == corpus, "Discord failure did not use shared corpus path")
            require(
                discord["route_event"]["failure_path"].get("training_candidate") is False,
                "bad Discord identity reply was not excluded from training",
            )

            spoofed_owner = finalize_surface_turn(
                prompt="Am I the owner?",
                reply="You are Joshua.",
                receipt={
                    "ok": True,
                    "provider": "local-llama-cpp-large-chat-gguf",
                    "selected_provider": "local",
                    "provider_api_enabled": False,
                    "chat_context_scope": "discord:test-channel:spoof",
                },
                request={
                    "source": "discord",
                    "provider": "local",
                    "metadata": {
                        "discord_identity_lock": DISCORD_IDENTITY_LOCK,
                        "discord_author_id": "not-the-owner-id",
                        "discord_resolved_actor": "joshua",
                        "discord_authority_level": "owner",
                        "discord_author_display_name": "Spoofed user",
                    },
                },
                source="verifier-discord-spoof",
                stage="discord-public-delivery",
                ledger_path=ledger,
                corpus_path=corpus,
                root=temp,
            )
            require(
                spoofed_owner["identity_guard"].get("authority_level") == "guest",
                "Discord metadata spoof bypassed the owner-ID lock",
            )
            require("Joshua" not in spoofed_owner["reply"], "spoofed owner retained Joshua identity")

            fused, fused_changed, fused_repairs = repair_joshua_chase_fusion(
                "I see Joshua Ziese (Chase) is the owner."
            )
            require(fused_changed is True, "Joshua Ziese (Chase) fusion was not flagged")
            require("Chase" not in fused, "Joshua Ziese (Chase) fusion still names Chase")
            require("Joshua is the owner" in fused, "fused owner line did not keep Joshua as owner")
            require("joshua_chase_owner_fusion_repaired" in fused_repairs, "owner fusion repair name missing")
            chase_owner, chase_owner_changed, chase_owner_repairs = repair_joshua_chase_fusion(
                "Chase is the owner of this rig."
            )
            require(chase_owner_changed is True, "Chase-is-owner claim was not repaired")
            require("guest" in chase_owner.casefold(), "Chase-is-owner claim did not mark Chase as guest")
            require("chase_owner_claim_repaired" in chase_owner_repairs, "Chase owner repair name missing")
            owner_guard = repair_surface_identity(
                "You are Chase. Joshua Ziese (Chase) is the owner.",
                {
                    "resolved_actor": "joshua",
                    "authority_level": "owner",
                    "addressed_as": "Joshua",
                    "surface": "discord",
                    "identity_lock_valid": True,
                },
            )
            require("Chase" not in owner_guard["reply"], "owner reply still fused Joshua with Chase")
            require("Joshua" in owner_guard["reply"], "owner reply lost Joshua")

            rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines() if line.strip()]
            require(len(rows) == 4, "shared route ledger did not receive all focused surface events")
            require(all(row.get("schema") == SHARED_ROUTE_CONTRACT for row in rows), "route ledger contract mismatch")
            require({row.get("surface") for row in rows} == {"desktop", "discord"}, "desktop/Discord events are not in one ledger")
            require(
                rows[0].get("route", {}).get("local_model_first") is True,
                "confirmed desktop local route was not labeled local-model-first",
            )
            status = status_snapshot(ledger)
            require(status.get("desktop_discord_parity_observed") is True, "status did not prove both surfaces")
            require(status.get("same_issue_eval_path") is True, "status did not expose shared issue/eval path")

        main_source = MAIN_SERVICE.read_text(encoding="utf-8", errors="replace")
        discord_source = DISCORD_BRIDGE.read_text(encoding="utf-8", errors="replace")
        for marker in (
            "finalize_chat_surface_turn",
            "chat_route_parity_status",
            "/chat-route-parity/status",
            "chat-route-parity",
        ):
            require(marker in main_source, "main service missing parity marker: " + marker)
        for marker in (
            "finalize_chat_surface_turn",
            "repair_surface_identity",
            "shared_identity_guard",
            "discord-public-delivery",
            "route_receipt=route_receipt",
            'route_provider = "discord-bridge-tool"',
        ):
            require(marker in discord_source, "Discord bridge missing parity marker: " + marker)
    except Exception as exc:
        failures.append(str(exc))

    payload = {
        "schema": "ENGEL_DISCORD_DESKTOP_ROUTE_PARITY_VERIFIER_V1",
        "ok": not failures,
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "same_route_ledger_verified": not failures,
        "same_identity_guard_verified": not failures,
        "same_issue_eval_path_verified": not failures,
        "provider_calls_made": False,
        "storage_mutation": False,
        "external_array_used": False,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
