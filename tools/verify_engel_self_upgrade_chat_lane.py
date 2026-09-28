#!/usr/bin/env python3
"""Verify the desktop-chat entrypoint for non-applying self-upgrade reviews."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import engel_main_server_chat_http_service as service  # noqa: E402


def main() -> int:
    checks: list[dict[str, Any]] = []

    def record(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"check": name, "ok": bool(ok), "detail": detail})

    desktop_request = {
        "source": "engel_ai_main_ui",
        "conversation_id": "verifier",
    }
    natural = (
        "Review this Engel self-upgrade without applying: "
        "show immutable prompt-to-patch provenance in the governed cycle"
    )
    extracted = service._self_upgrade_chat_review_text(natural, desktop_request)
    record(
        "natural desktop request is recognized and bounded",
        extracted == "show immutable prompt-to-patch provenance in the governed cycle",
        extracted,
    )
    record(
        "Discord cannot invoke the self-upgrade chat control",
        service._self_upgrade_chat_review_text(
            natural,
            {"source": "discord", "metadata": {"discord_author_id": "owner"}},
        )
        == "",
    )
    record(
        "ordinary self-upgrade conversation does not trigger a cycle",
        service._self_upgrade_chat_review_text(
            "How does the self-upgrade review work?",
            desktop_request,
        )
        == "",
    )

    calls: list[dict[str, Any]] = []
    original = service._self_upgrade_cycle_request

    def fake_cycle(payload: dict[str, Any], **_: Any) -> dict[str, Any]:
        calls.append(payload)
        return {
            "ok": True,
            "final_status": "dry_run_complete",
            "local_model_first": True,
            "provider_called": False,
            "cycle": {
                "cycle_receipt_path": "reports/self_upgrade/cycles/test.json",
                "stages": [
                    {
                        "stage": "distributed_work",
                        "ok": True,
                        "required_worker_ids": [
                            "android_worker_alpha",
                            "android_worker_beta",
                            "android_worker_gamma",
                            "DESKTOP-UE5A6GG",
                        ],
                        "returned_worker_count": 4,
                    },
                    {
                        "stage": "provenance",
                        "ok": True,
                        "provenance_id": "prompt_patch_test",
                        "ledger_path": (
                            "reports/self_upgrade/provenance/"
                            "prompt_patch_ledger.jsonl"
                        ),
                    },
                ],
            },
        }

    service._self_upgrade_cycle_request = fake_cycle
    try:
        turn = service._self_upgrade_chat_review_turn(
            natural,
            desktop_request,
            time.perf_counter(),
        )
    finally:
        service._self_upgrade_cycle_request = original

    receipt, reply = turn if turn is not None else ({}, "")
    record(
        "chat lane hard-codes a dry run owned by Joshua",
        len(calls) == 1
        and calls[0].get("execute") is False
        and calls[0].get("actor") == "owner_joshua"
        and calls[0].get("source") == "engel_flutter_main_chat",
        json.dumps(calls[0] if calls else {}, sort_keys=True),
    )
    record(
        "visible reply proves four workers and immutable provenance",
        receipt.get("ok") is True
        and receipt.get("returned_worker_count") == 4
        and "4/4" in reply
        and "prompt_patch_test" in reply,
        reply,
    )
    record(
        "chat review cannot apply source or call a provider",
        receipt.get("dry_run") is True
        and receipt.get("source_mutation_performed") is False
        and receipt.get("provider_called") is False
        and receipt.get("provider_api_enabled") is False,
    )

    source = Path(service.__file__).read_text(encoding="utf-8")
    gate_at = source.index("self_upgrade_review = _self_upgrade_chat_review_turn(")
    build_at = source.index("build_receipt = _build_lane_receipt(", gate_at)
    record(
        "self-upgrade chat gate runs before generic build routing",
        gate_at < build_at,
    )

    failed = [item for item in checks if not item["ok"]]
    result = {
        "schema": "ENGEL_SELF_UPGRADE_CHAT_LANE_VERIFIER_V1",
        "goal_id": "engel_conical_agentic_sentient_self_upgrading_system",
        "ok": not failed,
        "checks_total": len(checks),
        "checks_passed": len(checks) - len(failed),
        "checks_failed": len(failed),
        "failed_checks": [item["check"] for item in failed],
        "checks": checks,
    }
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
