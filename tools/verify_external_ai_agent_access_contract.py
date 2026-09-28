#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

CONTRACT_JSON = ROOT / "memory" / "ENGEL_COLLAB_ROOM_EXTERNAL_AI_AGENT_ACCESS_CONTRACT_V1.json"
CONTRACT_MD = ROOT / "memory" / "ENGEL_COLLAB_ROOM_EXTERNAL_AI_AGENT_ACCESS_CONTRACT_V1.md"
CONTRACT_REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_COLLAB_ROOM_EXTERNAL_AI_AGENT_ACCESS_CONTRACT_V1.md"

OPTIONAL_FILES = [
    ROOT / "memory" / "ENGEL_AGENT_SKILL_COLLAB_ROOM_CONTRACT_V1.json",
    ROOT / "memory" / "ENGEL_AGENT_SKILL_COLLAB_ROOM_CONTRACT_V1.md",
    ROOT / "reports" / "codex_bridge" / "ENGEL_AGENT_SKILL_COLLAB_ROOM_CONTRACT_V1.md",
    ROOT / "tools" / "verify_agent_skill_collab_room_contract.py",
    ROOT / "reports" / "codex_bridge" / "ENGEL_LOCAL_LLM_AGENT_HYBRID_MODE_CLOSEOUT_REVIEW_V1.md",
    ROOT / "memory" / "ENGEL_OUTSIDE_AI_BOUNDARY_CONTRACT_V1.md",
    ROOT / "memory" / "ENGEL_DE_BRUIJN_IMPORT_BOUNDARY_CONTRACT_V1.json",
    ROOT / "tools" / "verify_untrusted_content_policy.py",
    ROOT / "tools" / "verify_de_bruijn_import_boundaries.py",
]

REQUIRED_TOP_LEVEL_VALUES = {
    "contract_id": "ENGEL_COLLAB_ROOM_EXTERNAL_AI_AGENT_ACCESS_CONTRACT_V1",
    "status": "contract_only",
    "active_workspace": r"D:\b.WorkSpace\Engel App",
    "external_ai_agent_access_enabled_now": False,
    "default_external_access_mode": "DISABLED",
    "local_engel_external_ai_fallback_allowed": False,
    "all_external_lanes_enabled_now": False,
    "approved_handoff_required": True,
    "external_output_trusted_by_default": False,
    "trusted_memory_write_allowed": False,
    "source_mutation_allowed_default": False,
    "route_mutation_allowed": False,
    "queue_mutation_allowed_default": False,
    "provider_api_allowed_default": False,
    "network_allowed_default": False,
    "package_install_allowed_default": False,
}

REQUIRED_TOP_LEVEL_KEYS = [
    "external_agent_lane_schema",
    "external_task_packet_schema",
    "external_result_schema",
    "universal_lane_rules",
    "lane_examples",
    "collaboration_room_rules",
    "future_ui_controls",
    "future_verifier",
    "forbidden_behaviors",
    "stop_conditions",
    "recommended_next_slice",
    "safety_preserved",
]

LANE_SCHEMA_FIELDS = [
    "lane_id",
    "agent_name",
    "agent_type",
    "provider_or_runtime",
    "local_or_online",
    "access_mode",
    "approved",
    "allowed_workspace",
    "allowed_inputs",
    "allowed_outputs",
    "forbidden_actions",
    "network_allowed",
    "provider_api_allowed",
    "local_model_allowed",
    "browser_allowed",
    "source_editing_allowed",
    "command_execution_allowed",
    "trusted_memory_write_allowed",
    "route_mutation_allowed",
    "queue_mutation_allowed",
    "package_install_allowed",
    "subagent_spawning_allowed",
    "approval_required_before_send",
    "verifier_required_after_result",
    "receipt_required",
    "output_trust_status",
]

TASK_PACKET_FIELDS = [
    "task_id",
    "room_id",
    "requested_by",
    "target_lane",
    "purpose",
    "files_in_scope",
    "files_forbidden",
    "allowed_actions",
    "forbidden_actions",
    "done_definition",
    "verifier_commands",
    "safety_boundaries",
    "expected_output",
    "approval_token_required",
    "created_at",
    "receipt_path",
]

RESULT_SCHEMA_FIELDS = [
    "result_id",
    "task_id",
    "lane_id",
    "output_type",
    "files_changed",
    "commands_run",
    "verifier_results",
    "safety_notes",
    "trust_status",
    "human_review_required",
    "apply_allowed",
    "receipt_path",
]

REQUIRED_LANE_EXAMPLES = [
    "Codex Code Agent Lane",
    "Claude Code Agent Lane",
    "ChatGPT Planning/Review Lane",
    "Gemini Research/Review Lane",
    "Local LLM Worker Lane",
    "Local Code Model Lane",
    "Verifier/Test Agent Lane",
    "Documentation Agent Lane",
    "Security Review Agent Lane",
    "UI/Design Agent Lane",
    "Browser Research Agent Lane",
]

LANE_EXAMPLE_KEYS = [
    "intended_use",
    "access_mode",
    "allowed_outputs",
    "forbidden_actions",
    "approval_needs",
    "verifier_needs",
]

RULE_CONCEPTS = {
    "explicit approval before first use": ["explicit approval", "approval before first use"],
    "task packet before work": ["task packet"],
    "provider/runtime/type labeling": ["provider/runtime/type", "provider", "runtime"],
    "no external AI as Local Engel": ["not pretend to be local engel", "external ai becoming local engel voice"],
    "no Local Engel fallback": ["not be an online fallback", "silently fall back"],
    "untrusted worker output": ["untrusted worker output", "untrusted until reviewed"],
    "verifier/review before adoption": ["verifier", "review", "adoption"],
    "no trusted-memory write": ["trusted-memory writes forbidden", "write trusted memory"],
    "no automatic patch apply": ["patch application forbidden", "auto-apply", "automatic patch apply"],
    "no package install without separate approval": ["package install forbidden", "package install"],
    "no provider/network unless lane policy allows": ["network/provider access forbidden", "provider/api/network"],
    "no subagent spawning unless approved": ["subagent spawning forbidden", "self-spawning"],
    "no Mobile/Remote Queen control": ["Mobile and Remote Queen control forbidden", "Mobile or Remote Queen control"],
}

ROOM_MAY_CONCEPTS = {
    "prepare task packet": ["prepare task packets", "prepare a task packet"],
    "ask Josh to approve handoff": ["ask Josh to approve", "approve handoff"],
    "ingest result as untrusted": ["ingest external results as untrusted", "untrusted worker output"],
    "run verifiers": ["run verifiers"],
    "produce summary/report": ["produce summaries", "produce summary", "reports"],
}

ROOM_MAY_NOT_CONCEPTS = {
    "silently call external AI": ["silently call external ai"],
    "auto-send tasks": ["auto-send tasks"],
    "auto-apply external output": ["auto-apply external output"],
    "external output writes trusted memory": ["external output write trusted memory"],
    "external output mutates source without approval": ["mutate source without verified approval"],
    "external AI becomes Engel voice": ["external ai become engel voice"],
    "external agent expands permissions": ["expand their own permissions"],
}

FUTURE_UI_CONCEPTS = {
    "External AI Access OFF / Manual Handoff / Approved Room Tool / Local Only": ["External AI Access", "Manual Handoff", "Approved Room Tool", "Local Only"],
    "Available lanes list": ["Available lanes"],
    "Lane trust status": ["Lane trust status"],
    "Lane provider/runtime": ["Lane provider/runtime"],
    "Send to selected AI button": ["Send to selected AI"],
    "Require approval before send ON": ["Require approval before send", "ON"],
    "External output trust untrusted": ["External output trust", "untrusted"],
    "Apply external result disabled until verified": ["Apply external result", "disabled until verified"],
    "View task packet": ["View task packet"],
    "View result receipt": ["View result receipt"],
    "Revoke lane access": ["Revoke lane access"],
    "Pause all external lanes": ["Pause all external lanes"],
}

FORBIDDEN_BEHAVIOR_CONCEPTS = {
    "hidden external AI fallback": ["hidden external AI fallback"],
    "silent Codex/Claude/ChatGPT/Gemini handoff": ["silent Codex/Claude/ChatGPT/Gemini handoff"],
    "external AI becoming Local Engel voice": ["external AI becoming Local Engel voice"],
    "automatic source editing": ["automatic source editing", "source/route/queue mutation"],
    "trusted-memory write by external AI": ["external AI writing trusted memory", "trusted-memory write"],
    "unreviewed patch apply": ["automatic patch apply", "unreviewed patch apply"],
    "background provider/API calls": ["background provider/API calls"],
    "self-spawning subagents": ["self-spawning subagents"],
    "creating live agents/skills without approval": ["creating live agents/skills without approval"],
    "Mobile/Remote Queen/runtime control": ["Mobile or Remote Queen control"],
    "unapproved package install": ["package install"],
    "unapproved network/provider access": ["provider/API/network"],
}

SOURCE_SUFFIXES = {".py", ".ps1", ".bat", ".cmd", ".sh", ".psm1", ".spec"}
BINARY_SUFFIXES = {
    ".exe",
    ".dll",
    ".pyd",
    ".pyc",
    ".pyo",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".zip",
    ".7z",
    ".tar",
    ".gz",
    ".pyz",
    ".pkg",
}

EXCLUDE_DIRS = {
    ".git",
    "build",
    "dist",
    "live",
    "backups",
    "__pycache__",
    ".venv",
    "venv",
    "node_modules",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}

ACTIVE_SOURCE_PATTERNS = [
    "enable_external_ai_agent_access",
    "start_external_ai_agent",
    "run_external_ai_agent",
    "call_external_ai_agent",
    "silent_codex_handoff",
    "silent_claude_handoff",
    "silent_chatgpt_handoff",
    "silent_gemini_handoff",
    "local_engel_fallback_to_external",
    "external_ai_auto_apply",
    "apply_external_agent_output",
    "external_ai_write_trusted_memory",
    "external_ai_route_mutation",
    "external_ai_queue_mutation",
    "external_ai_package_install",
    "external_ai_spawn_subagents",
    "external_ai_mobile_runtime",
    "external_ai_remote_queen_runtime",
]

SAFE_CONTEXT_HINTS = [
    "blocked",
    "disabled",
    "forbidden",
    "future-only",
    "future only",
    "must not",
    "not enabled",
    "review_required",
    "review required",
    "verifier",
]


class CheckFailure(Exception):
    pass


def rel(path: Path) -> str:
    return str(path.resolve(strict=False).relative_to(ROOT.resolve(strict=False))).replace("/", "\\")


def print_result(label: str, status: str, detail: str = "") -> None:
    suffix = f" {detail}" if detail else ""
    print(f"{status} {label}{suffix}")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def load_contract() -> dict[str, Any]:
    missing = [path for path in [CONTRACT_JSON, CONTRACT_MD, CONTRACT_REPORT] if not path.exists()]
    if missing:
        for path in missing:
            print_result("required file", "FAIL", rel(path))
        raise CheckFailure("required external AI access contract evidence is missing")
    print_result("required files", "PASS", "contract JSON, markdown, and report exist")
    for path in OPTIONAL_FILES:
        if path.exists():
            print_result("optional evidence", "INFO", rel(path))
        else:
            print_result("optional evidence", "SKIP", rel(path))
    try:
        data = json.loads(read_text(CONTRACT_JSON))
    except json.JSONDecodeError as exc:
        raise CheckFailure(f"contract JSON does not parse: {exc}") from exc
    print_result("contract JSON parse", "PASS", rel(CONTRACT_JSON))
    return data


def lower_text(value: Any) -> str:
    return json.dumps(value, sort_keys=True).lower()


def combined_contract_text(data: dict[str, Any]) -> str:
    return "\n".join(
        [
            json.dumps(data, sort_keys=True),
            read_text(CONTRACT_MD),
            read_text(CONTRACT_REPORT),
        ]
    )


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def check_required_values(data: dict[str, Any]) -> None:
    for key, expected in REQUIRED_TOP_LEVEL_VALUES.items():
        actual = data.get(key)
        require(actual == expected, f"{key} expected {expected!r}, got {actual!r}")
        print_result("contract value", "PASS", f"{key}={actual!r}")
    for key in REQUIRED_TOP_LEVEL_KEYS:
        require(key in data, f"missing required JSON key: {key}")
    print_result("required JSON keys", "PASS", str(len(REQUIRED_TOP_LEVEL_KEYS)))


def required_fields(container: Any, key: str) -> list[str]:
    require(isinstance(container, dict), f"{key} must be an object")
    fields = container.get("required_fields")
    require(isinstance(fields, list), f"{key}.required_fields must be a list")
    return [str(field) for field in fields]


def check_field_list(actual: list[str], expected: list[str], label: str) -> None:
    missing = [field for field in expected if field not in actual]
    require(not missing, f"{label} missing fields: {missing}")
    print_result(label, "PASS", f"{len(expected)} required fields present")


def check_schema_sections(data: dict[str, Any]) -> None:
    lane_schema = data.get("external_agent_lane_schema")
    task_schema = data.get("external_task_packet_schema")
    result_schema = data.get("external_result_schema")

    check_field_list(required_fields(lane_schema, "external_agent_lane_schema"), LANE_SCHEMA_FIELDS, "lane schema")
    lane_defaults = lane_schema.get("required_default_values", {})
    expected_lane_defaults = {
        "approved": False,
        "network_allowed": False,
        "provider_api_allowed": False,
        "source_editing_allowed": False,
        "command_execution_allowed": False,
        "trusted_memory_write_allowed": False,
        "route_mutation_allowed": False,
        "queue_mutation_allowed": False,
        "package_install_allowed": False,
        "subagent_spawning_allowed": False,
        "approval_required_before_send": True,
        "verifier_required_after_result": True,
        "receipt_required": True,
        "output_trust_status": "untrusted_until_reviewed",
    }
    for key, expected in expected_lane_defaults.items():
        require(lane_defaults.get(key) == expected, f"lane default {key} expected {expected!r}, got {lane_defaults.get(key)!r}")
    print_result("lane schema defaults", "PASS")

    check_field_list(required_fields(task_schema, "external_task_packet_schema"), TASK_PACKET_FIELDS, "task packet schema")
    task_defaults = task_schema.get("defaults", {})
    require(task_defaults.get("approval_token_required") is True, "task packet approval_token_required default must be true")
    print_result("task packet defaults", "PASS")

    check_field_list(required_fields(result_schema, "external_result_schema"), RESULT_SCHEMA_FIELDS, "result schema")
    result_defaults = result_schema.get("required_default_values", {})
    require(result_defaults.get("trust_status") == "untrusted_worker_output", "result trust_status default must be untrusted_worker_output")
    require(result_defaults.get("human_review_required") is True, "result human_review_required default must be true")
    require(result_defaults.get("apply_allowed") is False, "result apply_allowed default must be false")
    print_result("result schema defaults", "PASS")


def has_all_terms(text: str, terms: list[str]) -> bool:
    lower = text.lower()
    return all(term.lower() in lower for term in terms)


def has_any_phrase(text: str, phrases: list[str]) -> bool:
    lower = text.lower()
    return any(phrase.lower() in lower for phrase in phrases)


def check_concepts(text: str, concepts: dict[str, list[str]], label: str) -> None:
    for concept, phrases in concepts.items():
        require(has_any_phrase(text, phrases), f"{label} missing concept: {concept}")
    print_result(label, "PASS", str(len(concepts)))


def check_universal_rules(data: dict[str, Any], text: str) -> None:
    rules = data.get("universal_lane_rules")
    require(isinstance(rules, list) and rules, "universal_lane_rules must be a non-empty list")
    check_concepts("\n".join(str(rule) for rule in rules) + "\n" + text, RULE_CONCEPTS, "universal lane rules")


def check_lane_examples(data: dict[str, Any]) -> None:
    examples = data.get("lane_examples")
    require(isinstance(examples, list), "lane_examples must be a list")
    names = {str(item.get("agent_name", "")) for item in examples if isinstance(item, dict)}
    missing = [name for name in REQUIRED_LANE_EXAMPLES if name not in names]
    require(not missing, f"lane_examples missing examples: {missing}")
    for example in examples:
        require(isinstance(example, dict), "each lane example must be an object")
        example_name = str(example.get("agent_name", example.get("lane_id", "<unnamed>")))
        missing_keys = [key for key in LANE_EXAMPLE_KEYS if key not in example]
        require(not missing_keys, f"{example_name} missing keys: {missing_keys}")
    print_result("lane examples", "PASS", f"{len(REQUIRED_LANE_EXAMPLES)} required lanes present")


def check_room_rules(data: dict[str, Any], text: str) -> None:
    room_rules = data.get("collaboration_room_rules")
    require(isinstance(room_rules, dict), "collaboration_room_rules must be an object")
    may_text = "\n".join(str(item) for item in room_rules.get("may", [])) + "\n" + text
    may_not_text = "\n".join(str(item) for item in room_rules.get("may_not", [])) + "\n" + text
    check_concepts(may_text, ROOM_MAY_CONCEPTS, "collaboration room may rules")
    check_concepts(may_not_text, ROOM_MAY_NOT_CONCEPTS, "collaboration room may-not rules")


def check_future_ui(data: dict[str, Any], text: str) -> None:
    controls = data.get("future_ui_controls")
    require(isinstance(controls, list), "future_ui_controls must be a list")
    controls_text = "\n".join(str(item) for item in controls) + "\n" + text
    for concept, terms in FUTURE_UI_CONCEPTS.items():
        require(has_all_terms(controls_text, terms), f"future UI controls missing: {concept}")
    print_result("future UI controls", "PASS", str(len(FUTURE_UI_CONCEPTS)))


def check_forbidden_behaviors(data: dict[str, Any], text: str) -> None:
    forbidden = data.get("forbidden_behaviors")
    require(isinstance(forbidden, list), "forbidden_behaviors must be a list")
    forbidden_text = "\n".join(str(item) for item in forbidden) + "\n" + text
    check_concepts(forbidden_text, FORBIDDEN_BEHAVIOR_CONCEPTS, "forbidden behavior checks")


def should_skip(path: Path) -> bool:
    if path.suffix.lower() in BINARY_SUFFIXES:
        return True
    try:
        rel_parts = tuple(part.lower() for part in path.relative_to(ROOT).parts)
    except ValueError:
        return True
    if any(part in EXCLUDE_DIRS for part in rel_parts):
        return True
    if rel_parts and rel_parts[0] in {"memory", "reports"}:
        return True
    return False


def iter_active_source_files():
    for dirpath, dirnames, filenames in os.walk(ROOT):
        current = Path(dirpath)
        try:
            rel_parts = tuple(part.lower() for part in current.relative_to(ROOT).parts)
        except ValueError:
            rel_parts = ()
        kept: list[str] = []
        for dirname in dirnames:
            parts = rel_parts + (dirname.lower(),)
            if dirname.lower() in EXCLUDE_DIRS:
                continue
            if parts and parts[0] in {"memory", "reports"}:
                continue
            kept.append(dirname)
        dirnames[:] = kept
        for filename in filenames:
            path = current / filename
            if not path.is_file() or should_skip(path):
                continue
            if path.suffix.lower() in SOURCE_SUFFIXES:
                yield path


def context_has_guard(text: str, start: int) -> bool:
    window = text[max(0, start - 260) : min(len(text), start + 260)].lower()
    return any(hint in window for hint in SAFE_CONTEXT_HINTS)


def is_verifier(path: Path) -> bool:
    key = rel(path).lower()
    return key.startswith("tools\\verify_") or path.name.lower().startswith("verify_")


def scan_active_source() -> tuple[int, list[str], list[str], int]:
    scanned = 0
    failures: list[str] = []
    review_required: list[str] = []
    verifier_references = 0
    pattern_regexes = [(pattern, re.compile(re.escape(pattern), re.IGNORECASE)) for pattern in ACTIVE_SOURCE_PATTERNS]
    own_path = Path(__file__).resolve()

    for path in iter_active_source_files():
        scanned += 1
        text = read_text(path)
        matched_verifier = False
        for label, regex in pattern_regexes:
            for match in regex.finditer(text):
                if path.resolve() == own_path or is_verifier(path):
                    matched_verifier = True
                    continue
                finding = f"{rel(path)}: {label}"
                if context_has_guard(text, match.start()):
                    review_required.append(finding)
                    print_result("active source pattern", "REVIEW_REQUIRED", finding)
                else:
                    failures.append(finding)
                    print_result("active source pattern", "FAIL", finding)
        if matched_verifier:
            verifier_references += 1

    print_result("active source files scanned", "INFO", str(scanned))
    print_result("safe verifier forbidden-pattern references", "INFO", str(verifier_references))
    return scanned, failures, review_required, verifier_references


def main() -> int:
    failures: list[str] = []
    review_required: list[str] = []

    print("ENGEL_EXTERNAL_AI_AGENT_ACCESS_CONTRACT_VERIFIER")
    print(f"ROOT {ROOT}")
    print("Mode: local static verification only; no external AI/runtime/network/tool launch")

    try:
        data = load_contract()
        full_text = combined_contract_text(data)
        check_required_values(data)
        check_schema_sections(data)
        check_universal_rules(data, full_text)
        check_lane_examples(data)
        check_room_rules(data, full_text)
        check_future_ui(data, full_text)
        check_forbidden_behaviors(data, full_text)
        scanned, source_failures, source_review, safe_refs = scan_active_source()
        failures.extend(source_failures)
        review_required.extend(source_review)
    except CheckFailure as exc:
        failures.append(str(exc))

    print_result("contract checks", "FAIL" if failures else "PASS", f"failures={len(failures)}")
    print_result("review required findings", "INFO", str(len(review_required)))
    for item in review_required[:40]:
        print_result("review required", "REVIEW_REQUIRED", item)
    if len(review_required) > 40:
        print_result("review required", "INFO", f"{len(review_required) - 40} additional findings suppressed")

    if failures:
        for failure in failures:
            print_result("external AI access contract check", "FAIL", failure)
        print("EXTERNAL_AI_AGENT_ACCESS_CONTRACT_VERIFICATION_FAIL")
        return 1

    print_result("contract JSON boundary checks", "PASS")
    print_result("lane schema checks", "PASS")
    print_result("task packet schema checks", "PASS")
    print_result("result schema checks", "PASS")
    print_result("lane example checks", "PASS")
    print_result("collaboration room behavior checks", "PASS")
    print_result("future UI control checks", "PASS")
    print_result("forbidden behavior checks", "PASS")
    print_result("active source scan result", "PASS")
    print("EXTERNAL_AI_AGENT_ACCESS_CONTRACT_VERIFICATION_PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
