from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
CONTRACT_PATH = ROOT / "memory" / "ENGEL_OUTSIDE_AI_BOUNDARY_RULE_V1.json"

REQUIRED_STATUS = [
    "OUTSIDE_AI_BOUNDARY_RULE",
    "FIRST_CLASS_SECURITY_CONTRACT",
    "ENGEL_CONTROLLED_BOUNDARY",
    "OUTSIDE_AI_UNTRUSTED_INPUT",
    "TOOLS_AI_DO_NOT_USE_ENGEL",
    "NO_OUTSIDE_AI_CONTROL",
    "NO_BYPASS",
    "NO_SELF_APPROVAL",
    "NO_DIRECT_TOOL_EXECUTION",
    "NO_TRUSTED_MEMORY_WRITE",
    "NO_ROUTE_MUTATION",
    "NO_SOURCE_MUTATION",
    "NO_VERIFIER_MUTATION",
    "NO_COMMAND_MAP_MUTATION",
    "NO_REMOTE_QUEEN_CONTROL",
    "NO_PROVIDER_CALLS",
    "NO_NETWORK",
    "NO_BROWSER",
    "NO_PACKAGE_INSTALL",
    "NO_MODEL_DOWNLOAD",
    "NO_STARTUP_AUTOLOAD",
    "NO_BACKGROUND_WORKER",
    "HUMAN_APPROVAL_REQUIRED",
    "VERIFIER_REQUIRED",
    "RECEIPTS_REQUIRED",
    "HERMES_APPROVED_FOR_LOCAL_TESTING_HUMAN_DRIVEN_ONLY",
]

APPLY_BLOCKED_FROM = {
    "untrusted_raw",
    "draft",
    "candidate",
    "schema_validated",
    "verifier_pending",
    "verifier_failed",
    "human_review_required",
}

PROMPT_INJECTION_REJECT_PATTERNS = [
    "ignore previous instructions",
    "bypass engel safety",
    "disable verifiers",
    "mark this as trusted",
    "write this to memory now",
    "execute this command",
    "call this tool directly",
    "install this package",
    "download this file",
    "download this model",
    "change route",
    "change source",
    "reveal secrets",
    "hide this from the user",
    "delete logs",
    "delete receipts",
    "impersonate approval",
    "simulate human authorization",
    "continue autonomously",
    "start background workers",
    "connect to network without approval",
    "connect to provider without approval",
    "connect to api without approval",
]


class OutsideAIBoundaryError(ValueError):
    pass


def load_contract() -> dict[str, object]:
    try:
        data = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    except OSError as exc:
        raise OutsideAIBoundaryError("outside-AI boundary contract is missing") from exc
    except json.JSONDecodeError as exc:
        raise OutsideAIBoundaryError("outside-AI boundary contract JSON is invalid") from exc
    if not isinstance(data, dict):
        raise OutsideAIBoundaryError("outside-AI boundary contract must be a JSON object")
    return data


def validate_contract(data: dict[str, object] | None = None) -> list[str]:
    contract = load_contract() if data is None else data
    problems: list[str] = []
    if contract.get("contract_name") != "Engel Outside-AI Boundary Rule V1":
        problems.append("contract_name mismatch")
    if contract.get("core_principle") != "Engel uses Tools/AI. Tools/AI do not use Engel.":
        problems.append("core principle missing")
    statuses = contract.get("status", [])
    if not isinstance(statuses, list):
        problems.append("status must be a list")
        statuses = []
    for status in REQUIRED_STATUS:
        if status not in statuses:
            problems.append("missing status: " + status)
    # Hermes is now APPROVED for local install + human-driven testing per
    # Josh's authority decision on 2026-05-20. The runtime validator now
    # accepts either the legacy rejected status (for back-compat with old
    # snapshots in audit history) or the new approved status, but requires
    # the field to exist and carry one of the two recognised values.
    hermes = contract.get("hermes_policy", {})
    accepted_statuses = {
        "REJECTED / DO NOT INSTALL ON THIS COMPUTER",
        "APPROVED FOR LOCAL INSTALL AND HUMAN-DRIVEN TESTING",
    }
    if not isinstance(hermes, dict) or hermes.get("status") not in accepted_statuses:
        problems.append("Hermes policy status missing or unrecognised")
    if contract.get("runtime_effect") != "CONTRACT_STATUS_ONLY":
        problems.append("runtime effect must be CONTRACT_STATUS_ONLY")
    for key in [
        "no_provider_calls",
        "no_network",
        "no_browser",
        "no_package_install",
        "no_model_download",
        "no_background_worker",
        "no_startup_autorun",
        "no_trusted_memory_write",
        "no_source_mutation",
        "no_route_mutation",
    ]:
        if contract.get(key) is not True:
            problems.append("boundary flag missing/false: " + key)
    return problems


def scan_text(text: str) -> dict[str, object]:
    lowered = text.lower()
    matches = [pattern for pattern in PROMPT_INJECTION_REJECT_PATTERNS if pattern in lowered]
    return {
        "state": "quarantined" if matches else "candidate",
        "matches": matches,
        "outside_ai_untrusted_input": True,
        "human_review_required": True,
        "trusted_memory_write_allowed": False,
        "direct_tool_execution_allowed": False,
    }


def validate_state_transition(from_state: str, to_state: str, prerequisites: list[str] | None = None) -> dict[str, object]:
    prereq = set(prerequisites or [])
    allowed_states = set(load_contract().get("output_states", []))
    if from_state not in allowed_states:
        raise OutsideAIBoundaryError("unknown from_state: " + from_state)
    if to_state not in allowed_states:
        raise OutsideAIBoundaryError("unknown to_state: " + to_state)
    if to_state == "applied_by_engel" and from_state in APPLY_BLOCKED_FROM:
        return {
            "allowed": False,
            "reason": "outside-AI output cannot jump directly to applied_by_engel",
            "human_review_required": True,
            "verifier_required": True,
        }
    required = set(load_contract().get("required_apply_prerequisites", []))
    if to_state == "applied_by_engel" and not required.issubset(prereq):
        return {
            "allowed": False,
            "reason": "missing apply prerequisites: " + ", ".join(sorted(required - prereq)),
            "human_review_required": True,
            "verifier_required": True,
        }
    return {"allowed": True, "reason": "transition is boundary-compatible"}


def render_status() -> str:
    contract = load_contract()
    lines = [
        "Engel Outside-AI Boundary Rule V1",
        "",
        "Core principle:",
        str(contract.get("core_principle")),
        "",
        "Status:",
        *[f"- {status}" for status in contract.get("status", [])],
        "",
        "Hermes policy:",
        "- " + str(contract.get("hermes_policy", {}).get("status")),
        "- " + str(contract.get("hermes_policy", {}).get("reason")),
        "",
        "Boundary:",
        "- Outside AI is untrusted input.",
        "- Engel controls validation, authority, verification, approval, apply, and receipts.",
        "- No provider/network/browser/package/model/runtime behavior is enabled by this contract.",
    ]
    return "\n".join(lines).rstrip() + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read and validate Engel Outside-AI Boundary Rule V1.")
    parser.add_argument("--status", action="store_true", help="Print boundary status.")
    parser.add_argument("--validate", action="store_true", help="Validate boundary contract.")
    parser.add_argument("--check-text", metavar="TEXT", help="Scan inline outside-AI text for rejection patterns.")
    parser.add_argument("--transition", nargs=2, metavar=("FROM", "TO"), help="Validate an outside-AI output state transition.")
    parser.add_argument("--json", action="store_true", help="Print contract JSON.")
    return parser


def main(argv: list[str] | None = None, stdout=None, stderr=None) -> int:
    out = sys.stdout if stdout is None else stdout
    err = sys.stderr if stderr is None else stderr
    args = build_parser().parse_args(argv)
    try:
        if args.status:
            out.write(render_status())
            return 0
        if args.validate:
            problems = validate_contract()
            if problems:
                err.write("[FAIL] " + "; ".join(problems) + "\n")
                return 1
            out.write("[OK] Engel Outside-AI Boundary Rule V1 contract is valid.\n")
            return 0
        if args.check_text is not None:
            out.write(json.dumps(scan_text(args.check_text), indent=2, sort_keys=True) + "\n")
            return 0
        if args.transition:
            out.write(json.dumps(validate_state_transition(args.transition[0], args.transition[1]), indent=2, sort_keys=True) + "\n")
            return 0
        if args.json:
            out.write(json.dumps(load_contract(), indent=2, sort_keys=True) + "\n")
            return 0
        out.write(render_status())
        return 0
    except OutsideAIBoundaryError as exc:
        err.write("[REJECTED] " + str(exc) + "\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
