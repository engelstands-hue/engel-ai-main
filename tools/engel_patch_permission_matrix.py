#!/usr/bin/env python3
"""Engel self-upgrade actor/action authority matrix and decision engine."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any


ROOT = Path(os.environ.get("ENGEL_APP_ROOT") or Path(__file__).resolve().parents[1]).resolve()
MATRIX_PATH = Path(
    os.environ.get("ENGEL_PATCH_PERMISSION_MATRIX")
    or ROOT / "memory" / "self_update" / "patch_permission_matrix.json"
)
DECISION_ROOT = Path(
    os.environ.get("ENGEL_PATCH_PERMISSION_DECISIONS")
    or ROOT / "run" / "self_update" / "permissions" / "decisions"
)

ACTIONS = (
    "chat",
    "advise",
    "create_candidate_patch",
    "run_verifier",
    "execute_bounded_worker_task",
    "deploy_low_risk",
    "deploy_protected",
    "approve_protected",
    "spend_money",
    "promote_model",
    "screen_control",
    "write_candidate_memory",
    "write_trusted_memory",
    "modify_route_authority",
    "control_worker_shell",
    "control_worker_disk",
)

ACTORS: dict[str, dict[str, Any]] = {
    "owner_joshua": {
        "label": "Joshua Ziese",
        "kind": "owner",
        "rules": {action: "allow" for action in ACTIONS},
    },
    "ct246_engel_ai_main": {
        "label": "Engel AI Main CT246 orchestrator",
        "kind": "orchestrator",
        "rules": {
            "chat": "allow",
            "advise": "allow",
            "create_candidate_patch": "allow",
            "run_verifier": "allow",
            "execute_bounded_worker_task": "allow",
            "deploy_low_risk": "conditional",
            "deploy_protected": "conditional",
            "approve_protected": "deny",
            "spend_money": "conditional",
            "promote_model": "conditional",
            "screen_control": "conditional",
            "write_candidate_memory": "allow",
            "write_trusted_memory": "conditional",
            "modify_route_authority": "conditional",
            "control_worker_shell": "conditional",
            "control_worker_disk": "conditional",
        },
    },
    "local_llm": {
        "label": "CT246 local LLM",
        "kind": "model_advisor",
        "rules": {
            "chat": "allow",
            "advise": "allow",
            "create_candidate_patch": "allow",
            "run_verifier": "deny",
            "execute_bounded_worker_task": "deny",
            "write_candidate_memory": "allow",
        },
    },
    "codex_bridge": {
        "label": "Codex bridge",
        "kind": "code_advisor",
        "rules": {
            "chat": "allow",
            "advise": "allow",
            "create_candidate_patch": "allow",
            "run_verifier": "allow",
            "write_candidate_memory": "allow",
        },
    },
    "provider_bridge": {
        "label": "External provider bridge",
        "kind": "external_advisor",
        "rules": {
            "chat": "allow",
            "advise": "allow",
            "create_candidate_patch": "allow",
            "write_candidate_memory": "allow",
        },
    },
    "sub_engel": {
        "label": "Paired Sub-Engel worker",
        "kind": "bounded_worker",
        "rules": {
            "chat": "allow",
            "advise": "allow",
            "create_candidate_patch": "allow",
            "run_verifier": "allow",
            "execute_bounded_worker_task": "conditional",
            "write_candidate_memory": "allow",
        },
    },
    "android_worker": {
        "label": "Paired Android worker",
        "kind": "bounded_worker",
        "rules": {
            "chat": "allow",
            "advise": "allow",
            "run_verifier": "conditional",
            "execute_bounded_worker_task": "conditional",
        },
    },
    "rog_controller_automation": {
        "label": "ROG controller automation",
        "kind": "controller",
        "rules": {
            "chat": "allow",
            "advise": "allow",
            "create_candidate_patch": "allow",
            "run_verifier": "allow",
            "execute_bounded_worker_task": "allow",
            "deploy_low_risk": "conditional",
            "screen_control": "conditional",
            "write_candidate_memory": "allow",
            "control_worker_shell": "conditional",
            "control_worker_disk": "conditional",
        },
    },
    "discord_owner": {
        "label": "Authenticated Discord owner Engelz",
        "kind": "owner_surface",
        "rules": {
            "chat": "allow",
            "advise": "allow",
            "create_candidate_patch": "allow",
        },
    },
    "discord_non_owner": {
        "label": "Discord non-owner",
        "kind": "chat_only",
        "rules": {"chat": "allow"},
    },
}

CONDITIONS: dict[str, list[str]] = {
    "run_verifier": ["bounded_task", "worker_capability_proven", "receipt_required"],
    "execute_bounded_worker_task": ["bounded_task", "worker_paired", "worker_capability_proven", "receipt_required"],
    "deploy_low_risk": ["risk_low", "verifier_passed", "source_sync_proven", "rollback_ready"],
    "deploy_protected": ["owner_approved", "verifier_passed", "source_sync_proven", "rollback_ready"],
    "spend_money": ["owner_approved", "budget_receipt_present"],
    "promote_model": ["owner_approved", "canary_passed", "negative_eval_passed", "rollback_ready"],
    "screen_control": ["owner_approved", "bounded_task", "receipt_required"],
    "write_trusted_memory": ["owner_approved_or_direct_owner_memory_request", "receipt_required"],
    "modify_route_authority": ["owner_approved", "verifier_passed", "rollback_ready"],
    "control_worker_shell": ["owner_approved", "worker_paired", "bounded_task", "receipt_required"],
    "control_worker_disk": ["owner_approved", "worker_paired", "bounded_task", "receipt_required"],
}


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def build_matrix() -> dict[str, Any]:
    actors: dict[str, Any] = {}
    for actor, definition in ACTORS.items():
        rules = {action: definition.get("rules", {}).get(action, "deny") for action in ACTIONS}
        actors[actor] = {
            "label": definition["label"],
            "kind": definition["kind"],
            "rules": rules,
        }
    return {
        "schema": "ENGEL_PATCH_PERMISSION_MATRIX_V1",
        "ok": True,
        "status": "active",
        "goal": "Conical Agentic Sentient Self Upgrading System",
        "source_of_truth": "CT246 /opt/engel",
        "owner": "Joshua Ziese",
        "actions": list(ACTIONS),
        "actors": actors,
        "conditions": CONDITIONS,
        "global_rules": [
            "Only Joshua can approve a protected action.",
            "Local LLMs, Codex, providers, Sub-Engel, Android workers, and automation cannot approve their own work.",
            "Low-risk deployment requires verifier, source-sync, and rollback proof.",
            "Paid work, model promotion, trusted-memory promotion, screen control, route-authority changes, and worker shell/disk control are protected.",
            "A direct owner request to remember a fact satisfies owner intent for that exact trusted-memory write only.",
            "Discord non-owners are chat-only and receive no tool, shell, disk, deployment, model, memory, or approval authority.",
        ],
        "generated_at_utc": now_utc(),
    }


def write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)
    return path


def load_matrix(path: Path = MATRIX_PATH) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"could not read permission matrix: {path}") from exc
    if not isinstance(payload, dict) or payload.get("schema") != "ENGEL_PATCH_PERMISSION_MATRIX_V1":
        raise ValueError("permission matrix schema mismatch")
    return payload


def _condition_value(name: str, context: dict[str, Any]) -> bool:
    if name == "risk_low":
        return str(context.get("risk") or "").casefold() == "low"
    if name == "owner_approved_or_direct_owner_memory_request":
        return context.get("owner_approved") is True or context.get("direct_owner_memory_request") is True
    return context.get(name) is True


def decide(
    matrix: dict[str, Any],
    *,
    actor: str,
    action: str,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    context = dict(context or {})
    actors = matrix.get("actors", {})
    if actor not in actors:
        mode = "deny"
        reason = "unknown actor"
        requirements: list[str] = []
    elif action not in matrix.get("actions", []):
        mode = "deny"
        reason = "unknown action"
        requirements = []
    else:
        mode = str(actors[actor].get("rules", {}).get(action) or "deny")
        requirements = list(matrix.get("conditions", {}).get(action, [])) if mode == "conditional" else []
        reason = "matrix rule"

    checks = {name: _condition_value(name, context) for name in requirements}
    if mode == "allow":
        allowed = True
    elif mode == "conditional":
        allowed = bool(requirements) and all(checks.values())
        reason = "all conditions satisfied" if allowed else "required conditions missing"
    else:
        allowed = False
        reason = reason if reason != "matrix rule" else "actor has no authority for this action"

    if action == "approve_protected" and actor != "owner_joshua":
        allowed = False
        mode = "deny"
        reason = "only Joshua can approve protected actions"

    return {
        "schema": "ENGEL_PATCH_PERMISSION_DECISION_V1",
        "ok": True,
        "allowed": allowed,
        "decision": "allow" if allowed else "deny",
        "actor": actor,
        "action": action,
        "mode": mode,
        "reason": reason,
        "requirements": requirements,
        "condition_checks": checks,
        "context": context,
        "matrix_schema": matrix.get("schema"),
        "source_of_truth": "CT246 /opt/engel",
        "decided_at_utc": now_utc(),
    }


def _parse_context(raw: str) -> dict[str, Any]:
    if not raw:
        return {}
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("context JSON must be an object")
    return payload


def _emit(payload: dict[str, Any], output: Path | None = None) -> int:
    if output is not None:
        write_json(output, payload)
        payload = {**payload, "receipt_path": str(output)}
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload.get("ok") is True else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Engel patch permission and authority matrix.")
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build")
    build.add_argument("--output", default=str(MATRIX_PATH))
    sub.add_parser("status")
    check = sub.add_parser("check")
    check.add_argument("--actor", required=True)
    check.add_argument("--action", required=True)
    check.add_argument("--context-json", default="{}")
    check.add_argument("--output")
    args = parser.parse_args(argv)
    try:
        if args.command == "build":
            matrix = build_matrix()
            return _emit(matrix, Path(args.output))
        matrix = load_matrix()
        if args.command == "status":
            return _emit(
                {
                    "schema": "ENGEL_PATCH_PERMISSION_STATUS_V1",
                    "ok": True,
                    "status": matrix.get("status"),
                    "goal": matrix.get("goal"),
                    "matrix_path": str(MATRIX_PATH),
                    "actor_count": len(matrix.get("actors", {})),
                    "action_count": len(matrix.get("actions", [])),
                    "owner": matrix.get("owner"),
                }
            )
        if args.command == "check":
            decision = decide(
                matrix,
                actor=args.actor,
                action=args.action,
                context=_parse_context(args.context_json),
            )
            output = Path(args.output) if args.output else DECISION_ROOT / f"PERMISSION_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}.json"
            return _emit(decision, output)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return _emit({"schema": "ENGEL_PATCH_PERMISSION_ERROR_V1", "ok": False, "error": str(exc)})
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

