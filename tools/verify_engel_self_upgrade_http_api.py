#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))


def require(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def main() -> int:
    import engel_main_server_chat_http_service as service
    import engel_self_upgrade_system as system

    failures: list[str] = []
    cycle_request = {
        "source": "chat_ui",
        "symptom": "fixture self-upgrade request",
        "severity": "low",
        "affected_surface": "chat",
        "diagnosis": "fixture diagnosis",
        "patch_plan": "fixture plan",
        "files_to_change": ["tools/fixture.py"],
        "operations": [
            {
                "op": "replace_text",
                "file": "tools/fixture.py",
                "old_text": "before",
                "new_text": "after",
            }
        ],
        "lesson": "fixture lesson",
    }

    def planner(_: dict[str, object]) -> dict[str, object]:
        return {
            "ok": True,
            "cycle_request": dict(cycle_request),
            "receipt_path": "reports/self_upgrade/local_plans/fixture.json",
        }

    plan = service._self_upgrade_plan_request(
        {"request_text": "fix the fixture"},
        planner_fn=planner,
    )
    require(plan.get("ok") is True, "plan endpoint helper rejected valid plan", failures)
    require(plan.get("provider_called") is False, "plan helper claimed a provider", failures)
    require(
        plan.get("source_mutation_performed") is False,
        "plan helper claimed source mutation",
        failures,
    )

    calls: list[dict[str, object]] = []

    def cycle_fn(request: dict[str, object], **kwargs: object) -> dict[str, object]:
        calls.append({"request": request, **kwargs})
        return {
            "schema": "ENGEL_CONICAL_SELF_UPGRADE_CYCLE_V1",
            "final_status": "blocked_at_distributed_work",
            "cycle_receipt_path": "reports/self_upgrade/cycles/fixture.json",
        }

    dry = service._self_upgrade_cycle_request(
        {"request_text": "fix the fixture"},
        planner_fn=planner,
        cycle_fn=cycle_fn,
    )
    require(dry.get("ok") is True, "dry cycle transport was not recorded", failures)
    require(
        dry.get("final_status") == "blocked_at_distributed_work"
        and dry.get("cycle_completed") is False,
        "fail-closed worker status was hidden",
        failures,
    )
    require(
        calls and calls[-1].get("dry_run") is True,
        "dry cycle invoked execute mode",
        failures,
    )

    calls.clear()
    refused = False
    try:
        service._self_upgrade_cycle_request(
            {
                "cycle_request": cycle_request,
                "execute": True,
                "fix_approval_token": "wrong",
                "gate_token": system.LOW_RISK_GATE_TOKEN,
                "apply_token": system.LOW_RISK_APPLY_TOKEN,
            },
            cycle_fn=cycle_fn,
        )
    except PermissionError:
        refused = True
    require(refused and not calls, "invalid execute approval reached the cycle", failures)

    approved = service._self_upgrade_cycle_request(
        {
            "cycle_request": cycle_request,
            "execute": True,
            "fix_approval_token": "APPROVE_FIX_CANDIDATE",
            "gate_token": system.ELEVATED_RISK_GATE_TOKEN,
            "apply_token": system.ELEVATED_RISK_APPLY_TOKEN,
        },
        cycle_fn=cycle_fn,
    )
    require(approved.get("mode") == "execute", "approved execute mode was lost", failures)
    require(
        calls and calls[-1].get("dry_run") is False,
        "approved request did not invoke execute mode",
        failures,
    )
    require(
        calls[-1].get("gate_token") == system.ELEVATED_RISK_GATE_TOKEN,
        "elevated gate token did not reach the governed cycle",
        failures,
    )

    require(
        service._loopback_client_address("127.0.0.1")
        and service._loopback_client_address("::1"),
        "loopback owner route was not recognized",
        failures,
    )
    require(
        not service._loopback_client_address("192.0.2.78"),
        "LAN worker address was accepted as owner control",
        failures,
    )

    source = (TOOLS / "engel_main_server_chat_http_service.py").read_text(
        encoding="utf-8"
    )
    require(
        '"/self-upgrade/status"' in source
        and '"/self-upgrade/plan"' in source
        and '"/self-upgrade/cycle"' in source,
        "HTTP routes are not registered",
        failures,
    )
    require(
        "_loopback_client_address(client_host)" in source,
        "self-upgrade control routes lack loopback enforcement",
        failures,
    )

    payload = {
        "schema": "ENGEL_SELF_UPGRADE_HTTP_API_VERIFICATION_V1",
        "ok": not failures,
        "failures": failures,
        "local_model_first": True,
        "provider_called": False,
        "invalid_execute_blocked_before_cycle": refused,
        "loopback_control_only": True,
    }
    print(json.dumps(payload, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
