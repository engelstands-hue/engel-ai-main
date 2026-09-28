#!/usr/bin/env python3
"""Verify CT246 sparse-MoE routing without loading model weights."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
RECEIPT_DIR = ROOT / "reports" / "engel_sparse_moe_routing"


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def require(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def main() -> int:
    failures: list[str] = []
    import engel_main_server_chat_http_service as service

    explicit = service._sparse_moe_route_decision(
        "Use the Qwen3-30B-A3B MoE expert lane to answer this.",
        {},
    )
    complex_turn = service._sparse_moe_route_decision(
        "Analyze this distributed system architecture and compare the failure "
        "modes, constraints, tradeoffs, and migration plan. Then recommend the "
        "best design and explain the root cause risks.",
        {"complexity": "expert"},
    )
    simple = service._sparse_moe_route_decision("What time is it?", {})
    code = service._sparse_moe_route_decision(
        "Create a complete Python app.py file that prints hello.", {}
    )

    require(explicit.get("selected") is True, "explicit MoE selection failed", failures)
    require(explicit.get("explicit") is True, "explicit route not labelled", failures)
    require(
        complex_turn.get("selected") is True,
        "expert reasoning request did not auto-route to MoE",
        failures,
    )
    require(
        complex_turn.get("thinking_mode") is True,
        "expert reasoning request did not select thinking mode",
        failures,
    )
    require(simple.get("selected") is False, "simple chat over-routed to MoE", failures)
    require(
        code.get("selected") is False,
        "code artifact request bypassed the dedicated coder lane",
        failures,
    )

    payload = {
        "schema": "engel_sparse_moe_routing_verification_v1",
        "ok": not failures,
        "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        "container_target": "CT246",
        "storage_policy": "engel-fast-ssd active runtime",
        "power_vault_used": False,
        "model_runtime_loaded": False,
        "provider_called": False,
        "cases": {
            "explicit": explicit,
            "complex": complex_turn,
            "simple": simple,
            "code": code,
        },
        "failures": failures,
    }
    RECEIPT_DIR.mkdir(parents=True, exist_ok=True)
    receipt = RECEIPT_DIR / f"ENGEL_SPARSE_MOE_ROUTING_{utc_stamp()}.json"
    receipt.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({**payload, "receipt": str(receipt)}, indent=2, sort_keys=True))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
