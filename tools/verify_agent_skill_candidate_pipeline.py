#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

CONTRACT_JSON = ROOT / "memory" / "ENGEL_AGENT_SKILL_CANDIDATE_PIPELINE_CONTRACT_V1.json"
CONTRACT_MD = ROOT / "memory" / "ENGEL_AGENT_SKILL_CANDIDATE_PIPELINE_CONTRACT_V1.md"
CONTRACT_REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_AGENT_SKILL_CANDIDATE_PIPELINE_CONTRACT_V1.md"

OPTIONAL_EVIDENCE = [
    ROOT / "tools" / "verify_external_ai_agent_access_contract.py",
    ROOT / "reports" / "codex_bridge" / "ENGEL_EXTERNAL_AI_AGENT_ACCESS_VERIFIER_V1.md",
    ROOT / "memory" / "ENGEL_COLLAB_ROOM_EXTERNAL_AI_AGENT_ACCESS_CONTRACT_V1.json",
    ROOT / "tools" / "verify_untrusted_content_policy.py",
    ROOT / "tools" / "verify_de_bruijn_import_boundaries.py",
]

REQUIRED_VALUES = {
    "contract_id": "ENGEL_AGENT_SKILL_CANDIDATE_PIPELINE_CONTRACT_V1",
    "status": "contract_only",
    "active_workspace": r"D:\b.WorkSpace\Engel App",
    "live_agent_creation_enabled_now": False,
    "live_skill_creation_enabled_now": False,
    "candidate_creation_allowed_future": True,
    "candidate_runtime_enabled_default": False,
    "candidate_autorun_enabled_default": False,
    "trusted_memory_write_allowed": False,
    "source_mutation_allowed_default": False,
    "route_mutation_allowed": False,
    "queue_mutation_allowed_default": False,
    "network_allowed_default": False,
    "provider_api_allowed_default": False,
    "package_install_allowed_default": False,
    "mobile_runtime_allowed": False,
    "remote_queen_runtime_allowed": False,
}

REQUIRED_KEYS = [
    "pipeline_stages",
    "candidate_storage_policy",
    "candidate_agent_schema",
    "candidate_skill_schema",
    "forbidden_candidate_behaviors",
    "candidate_creation_rules",
    "inactive_registry_boundary",
    "external_ai_lane_interaction",
    "future_verifier",
    "stop_conditions",
    "recommended_next_slice",
    "safety_preserved",
]

PIPELINE_STAGES = [
    "IDEA",
    "CANDIDATE_SPEC",
    "STATIC_SAFETY_SCAN",
    "HUMAN_REVIEW",
    "APPROVED_INACTIVE",
    "ACTIVATION_CONTRACT",
    "RUNTIME_SMOKE",
    "ENGEL_ON_AUTORUN",
]

AGENT_FIELDS = [
    "candidate_id",
    "candidate_type",
    "name",
    "purpose",
    "description",
    "owner",
    "created_by",
    "created_at",
    "status",
    "trust_status",
    "allowed_inputs",
    "allowed_outputs",
    "allowed_context",
    "forbidden_context",
    "allowed_actions",
    "forbidden_actions",
    "allowed_files",
    "forbidden_files",
    "required_verifiers",
    "required_human_review",
    "external_ai_lanes_requested",
    "collaboration_room_allowed",
    "runtime_enabled",
    "autorun_enabled",
    "trusted_memory_write_allowed",
    "source_mutation_allowed",
    "route_mutation_allowed",
    "queue_mutation_allowed",
    "network_allowed",
    "provider_api_allowed",
    "package_install_allowed",
    "mobile_runtime_allowed",
    "remote_queen_runtime_allowed",
    "approval_required_for_inactive_registry",
    "activation_contract_required",
    "receipt_required",
]

SKILL_FIELDS = [
    "candidate_id",
    "candidate_type",
    "skill_name",
    "description",
    "trigger_conditions",
    "input_schema",
    "output_schema",
    "owner",
    "created_by",
    "created_at",
    "status",
    "trust_status",
    "allowed_files",
    "forbidden_files",
    "allowed_actions",
    "forbidden_actions",
    "required_verifiers",
    "required_human_review",
    "external_ai_lanes_requested",
    "install_enabled",
    "runtime_enabled",
    "autorun_enabled",
    "trusted_memory_write_allowed",
    "source_mutation_allowed",
    "route_mutation_allowed",
    "queue_mutation_allowed",
    "network_allowed",
    "provider_api_allowed",
    "package_install_allowed",
    "mobile_runtime_allowed",
    "remote_queen_runtime_allowed",
    "approval_required_for_inactive_registry",
    "activation_contract_required",
    "receipt_required",
]

REQUIRED_FALSE_FIELDS = [
    "runtime_enabled",
    "autorun_enabled",
    "trusted_memory_write_allowed",
    "source_mutation_allowed",
    "route_mutation_allowed",
    "queue_mutation_allowed",
    "network_allowed",
    "provider_api_allowed",
    "package_install_allowed",
    "mobile_runtime_allowed",
    "remote_queen_runtime_allowed",
]

FORBIDDEN_BEHAVIOR_CONCEPTS = {
    "running automatically": ["run automatically"],
    "self-activating": ["self-activate"],
    "self-registering as live": ["self-register as live"],
    "writing trusted memory": ["write trusted memory"],
    "promoting candidate memory": ["promote candidate memory"],
    "mutating source": ["mutate source"],
    "mutating routes": ["mutate routes"],
    "mutating queues": ["mutate queues"],
    "installing packages": ["install packages"],
    "calling providers/network": ["call providers or network", "providers/network"],
    "using external AI without approval": ["use external ai lanes without separate approval"],
    "starting local LLM inference": ["start local llm inference"],
    "starting model servers": ["start model servers"],
    "enabling Mobile runtime": ["enable mobile runtime"],
    "enabling Remote Queen runtime": ["enable remote queen runtime"],
    "creating new live agents/skills": ["create new live agents or live skills"],
    "bypassing Global Password Gate": ["bypass global password gate"],
    "bypassing approval tokens": ["bypass approval tokens"],
    "bypassing verifiers": ["bypass verifiers"],
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

TRUE_VALUE = r"(?:True|true|\$true)"
TRUE_FLAG_END = r"(?=$|[\s,;\]\}\)])"

ACTIVE_SOURCE_PATTERNS = [
    ("create_live_agent", re.compile(r"\bcreate_live_agent\b", re.I)),
    ("enable_live_agent", re.compile(r"\benable_live_agent\b", re.I)),
    ("start_live_agent", re.compile(r"\bstart_live_agent\b", re.I)),
    ("create_live_skill", re.compile(r"\bcreate_live_skill\b", re.I)),
    ("enable_live_skill", re.compile(r"\benable_live_skill\b", re.I)),
    ("install_live_skill", re.compile(r"\binstall_live_skill\b", re.I)),
    (
        "candidate_runtime_enabled true",
        re.compile(rf"['\"]?\bcandidate_runtime_enabled\b['\"]?\s*[:=]\s*{TRUE_VALUE}{TRUE_FLAG_END}", re.I),
    ),
    (
        "candidate_autorun_enabled true",
        re.compile(rf"['\"]?\bcandidate_autorun_enabled\b['\"]?\s*[:=]\s*{TRUE_VALUE}{TRUE_FLAG_END}", re.I),
    ),
    (
        "trusted_memory_write_allowed true",
        re.compile(rf"['\"]?\btrusted_memory_write_allowed\b['\"]?\s*[:=]\s*{TRUE_VALUE}{TRUE_FLAG_END}", re.I),
    ),
    (
        "source_mutation_allowed true",
        re.compile(rf"['\"]?\bsource_mutation_allowed\b['\"]?\s*[:=]\s*{TRUE_VALUE}{TRUE_FLAG_END}", re.I),
    ),
    (
        "route_mutation_allowed true",
        re.compile(rf"['\"]?\broute_mutation_allowed\b['\"]?\s*[:=]\s*{TRUE_VALUE}{TRUE_FLAG_END}", re.I),
    ),
    (
        "provider_api_allowed true",
        re.compile(rf"['\"]?\bprovider_api_allowed\b['\"]?\s*[:=]\s*{TRUE_VALUE}{TRUE_FLAG_END}", re.I),
    ),
    (
        "network_allowed true",
        re.compile(rf"['\"]?\bnetwork_allowed\b['\"]?\s*[:=]\s*{TRUE_VALUE}{TRUE_FLAG_END}", re.I),
    ),
    (
        "mobile_runtime_allowed true",
        re.compile(rf"['\"]?\bmobile_runtime_allowed\b['\"]?\s*[:=]\s*{TRUE_VALUE}{TRUE_FLAG_END}", re.I),
    ),
    (
        "remote_queen_runtime_allowed true",
        re.compile(rf"['\"]?\bremote_queen_runtime_allowed\b['\"]?\s*[:=]\s*{TRUE_VALUE}{TRUE_FLAG_END}", re.I),
    ),
    ("auto_register_skill", re.compile(r"\bauto_register_skill\b", re.I)),
    ("auto_register_agent", re.compile(r"\bauto_register_agent\b", re.I)),
    ("self_activate_agent", re.compile(r"\bself_activate_agent\b", re.I)),
    ("self_activate_skill", re.compile(r"\bself_activate_skill\b", re.I)),
]

CANDIDATE_DIRS = [
    ROOT / "reports" / "agent_skill_candidates",
    ROOT / "data" / "agent_skill_candidates",
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

REVIEW_REQUIRED_HINTS = [
    "review_required",
    "review required",
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


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def load_contract() -> dict[str, Any]:
    missing = [path for path in [CONTRACT_JSON, CONTRACT_MD, CONTRACT_REPORT] if not path.exists()]
    if missing:
        for path in missing:
            print_result("required contract file", "FAIL", rel(path))
        raise CheckFailure("required candidate pipeline contract evidence is missing")
    print_result("required contract files", "PASS", "JSON, markdown, and report exist")
    for path in OPTIONAL_EVIDENCE:
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


def combined_text(data: dict[str, Any]) -> str:
    return "\n".join([json.dumps(data, sort_keys=True), read_text(CONTRACT_MD), read_text(CONTRACT_REPORT)])


def check_contract_values(data: dict[str, Any]) -> None:
    for key, expected in REQUIRED_VALUES.items():
        actual = data.get(key)
        require(actual == expected, f"{key} expected {expected!r}, got {actual!r}")
        print_result("contract value", "PASS", f"{key}={actual!r}")
    missing = [key for key in REQUIRED_KEYS if key not in data]
    require(not missing, f"missing required contract keys: {missing}")
    print_result("required contract keys", "PASS", str(len(REQUIRED_KEYS)))


def check_pipeline_stages(data: dict[str, Any]) -> None:
    stages = data.get("pipeline_stages")
    require(isinstance(stages, list), "pipeline_stages must be a list")
    actual = {str(item.get("stage", "")) for item in stages if isinstance(item, dict)}
    missing = [stage for stage in PIPELINE_STAGES if stage not in actual]
    require(not missing, f"pipeline_stages missing: {missing}")
    print_result("pipeline stage checks", "PASS", ", ".join(PIPELINE_STAGES))


def check_storage_policy(data: dict[str, Any], text: str) -> None:
    policy = data.get("candidate_storage_policy")
    require(isinstance(policy, dict), "candidate_storage_policy must be an object")
    roots = [str(item) for item in policy.get("future_allowed_roots", [])]
    require("reports\\agent_skill_candidates\\" in roots or "data\\agent_skill_candidates\\" in roots, "candidate storage roots must include reports or data agent_skill_candidates")
    require(policy.get("trust_status_default") == "untrusted_candidate", "candidate specs must be untrusted by default")
    require(policy.get("separated_from_runtime") is True, "candidate storage must be separated from runtime")
    require(policy.get("separated_from_live_registries") is True, "candidate storage must be separated from live registries")
    require(policy.get("not_runtime_authority") is True, "candidate storage must not be runtime authority")
    require(policy.get("no_execution") is True, "candidate storage must not execute")
    require(policy.get("no_auto_load") is True, "candidate storage must not auto-load")
    lower = text.lower()
    require("no live registration occurs" in lower or "no live registration" in lower, "contract must document no live registration from candidates")
    require("runtime" in lower and ("separate from runtime" in lower or "separated from runtime" in lower), "contract must document runtime separation")
    require(
        policy.get("not_runtime_authority") is True
        and policy.get("no_execution") is True
        and ("runtime activation" in lower or "runtime, worker" in lower or "does not run" in lower),
        "contract must document no runtime activation from candidate storage",
    )
    print_result("candidate storage policy", "PASS")


def schema_required_fields(data: dict[str, Any], key: str) -> list[str]:
    schema = data.get(key)
    require(isinstance(schema, dict), f"{key} must be an object")
    fields = schema.get("required_fields")
    require(isinstance(fields, list), f"{key}.required_fields must be a list")
    return [str(field) for field in fields]


def check_schema(data: dict[str, Any], key: str, expected_fields: list[str], expected_type: str, label: str) -> None:
    fields = schema_required_fields(data, key)
    missing = [field for field in expected_fields if field not in fields]
    require(not missing, f"{label} missing fields: {missing}")
    required_values = data[key].get("required_values", {})
    require(required_values.get("candidate_type") == expected_type, f"{label} candidate_type must be {expected_type}")
    require(required_values.get("status") == "candidate_only", f"{label} status must be candidate_only")
    require(required_values.get("trust_status") == "untrusted_candidate", f"{label} trust_status must be untrusted_candidate")
    for field in REQUIRED_FALSE_FIELDS:
        if field in expected_fields:
            require(required_values.get(field) is False, f"{label} {field} must default false")
    if expected_type == "skill":
        require(required_values.get("install_enabled") is False, "skill install_enabled must default false")
    if expected_type == "agent":
        require(required_values.get("collaboration_room_allowed") is False, "agent collaboration_room_allowed must default false")
    require(required_values.get("approval_required_for_inactive_registry") is True, f"{label} approval_required_for_inactive_registry must be true")
    require(required_values.get("activation_contract_required") is True, f"{label} activation_contract_required must be true")
    require(required_values.get("receipt_required") is True, f"{label} receipt_required must be true")
    print_result(label, "PASS", f"{len(expected_fields)} fields present")


def has_any_phrase(text: str, phrases: list[str]) -> bool:
    lower = text.lower()
    return any(phrase.lower() in lower for phrase in phrases)


def check_forbidden_behaviors(data: dict[str, Any], text: str) -> None:
    behaviors = data.get("forbidden_candidate_behaviors")
    require(isinstance(behaviors, list), "forbidden_candidate_behaviors must be a list")
    behavior_text = "\n".join(str(item) for item in behaviors) + "\n" + text
    for concept, phrases in FORBIDDEN_BEHAVIOR_CONCEPTS.items():
        require(has_any_phrase(behavior_text, phrases), f"forbidden behavior missing: {concept}")
    print_result("forbidden behavior checks", "PASS", str(len(FORBIDDEN_BEHAVIOR_CONCEPTS)))


def check_external_ai_interaction(data: dict[str, Any]) -> None:
    interaction = data.get("external_ai_lane_interaction")
    require(isinstance(interaction, dict), "external_ai_lane_interaction must be an object")
    expected = {
        "candidate_may_request_lanes": True,
        "lane_request_is_permission": False,
        "external_ai_access_enabled_default": False,
        "task_packet_required": True,
        "approval_required_before_send": True,
        "external_output_trust_status": "untrusted_worker_output",
        "external_output_can_activate_candidate": False,
        "external_output_can_write_trusted_memory": False,
    }
    for key, expected_value in expected.items():
        require(interaction.get(key) == expected_value, f"external_ai_lane_interaction {key} expected {expected_value!r}, got {interaction.get(key)!r}")
    print_result("external AI lane interaction checks", "PASS")


def check_candidate_json(path: Path, data: Any) -> list[str]:
    failures: list[str] = []
    if not isinstance(data, dict):
        return [f"{rel(path)}: candidate JSON must be an object"]
    ctype = str(data.get("candidate_type", ""))
    if ctype not in {"agent", "skill"}:
        failures.append(f"{rel(path)}: candidate_type must be agent or skill")
        expected_fields: list[str] = []
    elif ctype == "agent":
        expected_fields = AGENT_FIELDS
    else:
        expected_fields = SKILL_FIELDS
    missing_fields = [field for field in expected_fields if field not in data]
    if missing_fields:
        failures.append(f"{rel(path)}: missing required candidate fields: {missing_fields}")
    if data.get("status") != "candidate_only":
        failures.append(f"{rel(path)}: status must be candidate_only")
    if data.get("trust_status") != "untrusted_candidate":
        failures.append(f"{rel(path)}: trust_status must be untrusted_candidate")
    false_fields = REQUIRED_FALSE_FIELDS.copy()
    if ctype == "skill":
        false_fields.append("install_enabled")
    if ctype == "agent":
        false_fields.append("collaboration_room_allowed")
    for field in false_fields:
        if field not in data:
            failures.append(f"{rel(path)}: {field} must be present and false")
        elif data.get(field) is not False:
            failures.append(f"{rel(path)}: {field} must be false")
    for field in [
        "approval_required_for_inactive_registry",
        "activation_contract_required",
        "receipt_required",
    ]:
        if field not in data:
            failures.append(f"{rel(path)}: {field} must be present and true")
        elif data.get(field) is not True:
            failures.append(f"{rel(path)}: {field} must be true")
    if data.get("external_ai_lanes_requested") and data.get("external_ai_access_enabled_default") is True:
        failures.append(f"{rel(path)}: external AI request cannot enable external AI access")
    return failures


def markdown_says_false(text: str, field: str) -> bool:
    field_pattern = re.escape(field)
    patterns = [
        rf"`?{field_pattern}`?\s*[:=]\s*(?:`?false`?|`?no`?)",
        rf"`?{field_pattern}`?\s+is\s+(?:`?false`?|`?no`?)",
    ]
    return any(re.search(pattern, text, re.I) for pattern in patterns)


def check_candidate_markdown(path: Path, text: str) -> list[str]:
    lower = text.lower()
    failures: list[str] = []
    required_terms = ["candidate_only", "untrusted_candidate"]
    for term in required_terms:
        if term not in lower:
            failures.append(f"{rel(path)}: markdown candidate missing {term}")
    for field in REQUIRED_FALSE_FIELDS:
        if not markdown_says_false(text, field):
            failures.append(f"{rel(path)}: markdown candidate must say {field} false")
    forbidden_true = [
        "runtime_enabled: true",
        "autorun_enabled: true",
        "trusted_memory_write_allowed: true",
        "source_mutation_allowed: true",
        "route_mutation_allowed: true",
        "queue_mutation_allowed: true",
        "network_allowed: true",
        "provider_api_allowed: true",
        "package_install_allowed: true",
        "mobile_runtime_allowed: true",
        "remote_queen_runtime_allowed: true",
    ]
    for phrase in forbidden_true:
        if phrase in lower:
            failures.append(f"{rel(path)}: forbidden enabled flag {phrase}")
    return failures


def scan_candidate_storage() -> tuple[int, list[str]]:
    scanned = 0
    failures: list[str] = []
    existing_dirs = [path for path in CANDIDATE_DIRS if path.exists()]
    if not existing_dirs:
        print_result("candidate storage scan", "SKIP", "no candidate storage directories exist yet")
        return scanned, failures

    for directory in existing_dirs:
        print_result("candidate storage directory", "INFO", rel(directory))
        for path in sorted(directory.rglob("*")):
            if path.is_dir():
                continue
            if path.suffix.lower() not in {".json", ".md"}:
                failures.append(f"{rel(path)}: candidate storage may contain only JSON/MD files")
                continue
            scanned += 1
            if path.suffix.lower() == ".json":
                try:
                    candidate = json.loads(read_text(path))
                except json.JSONDecodeError as exc:
                    failures.append(f"{rel(path)}: invalid JSON: {exc}")
                    continue
                failures.extend(check_candidate_json(path, candidate))
            else:
                failures.extend(check_candidate_markdown(path, read_text(path)))
    if failures:
        print_result("candidate storage scan", "FAIL", f"files_scanned={scanned}")
    else:
        print_result("candidate storage scan", "PASS", f"files_scanned={scanned}")
    return scanned, failures


def should_skip(path: Path) -> bool:
    if path.suffix.lower() in BINARY_SUFFIXES:
        return True
    try:
        parts = tuple(part.lower() for part in path.relative_to(ROOT).parts)
    except ValueError:
        return True
    if any(part in EXCLUDE_DIRS for part in parts):
        return True
    if parts and parts[0] == "reports":
        return True
    if parts and parts[0] == "memory" and path.suffix.lower() not in SOURCE_SUFFIXES:
        return True
    return False


def iter_source_files():
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
            if parts and parts[0] == "reports":
                continue
            kept.append(dirname)
        dirnames[:] = kept
        for filename in filenames:
            path = current / filename
            if path.is_file() and not should_skip(path) and path.suffix.lower() in SOURCE_SUFFIXES:
                yield path


def is_verifier(path: Path) -> bool:
    key = rel(path).lower()
    return key.startswith("tools\\verify_") or path.name.lower().startswith("verify_")


def context_has_guard(text: str, start: int) -> bool:
    window = text[max(0, start - 260) : min(len(text), start + 260)].lower()
    return any(hint in window for hint in SAFE_CONTEXT_HINTS)


def context_requires_review(text: str, start: int) -> bool:
    window = text[max(0, start - 260) : min(len(text), start + 260)].lower()
    return any(hint in window for hint in REVIEW_REQUIRED_HINTS)


def scan_active_source() -> tuple[int, list[str], list[str], int]:
    own_path = Path(__file__).resolve()
    scanned = 0
    failures: list[str] = []
    review_required: list[str] = []
    safe_verifier_refs = 0
    safe_guarded_refs = 0
    for path in iter_source_files():
        scanned += 1
        text = read_text(path)
        matched_verifier = False
        for label, pattern in ACTIVE_SOURCE_PATTERNS:
            for match in pattern.finditer(text):
                if path.resolve() == own_path or is_verifier(path):
                    matched_verifier = True
                    continue
                finding = f"{rel(path)}: {label}"
                if context_requires_review(text, match.start()):
                    review_required.append(finding)
                    print_result("active source pattern", "REVIEW_REQUIRED", finding)
                elif context_has_guard(text, match.start()):
                    safe_guarded_refs += 1
                else:
                    failures.append(finding)
                    print_result("active source pattern", "FAIL", finding)
        if matched_verifier:
            safe_verifier_refs += 1
    print_result("active source files scanned", "INFO", str(scanned))
    print_result("safe verifier forbidden-pattern references", "INFO", str(safe_verifier_refs))
    print_result("safe guarded forbidden-pattern references", "INFO", str(safe_guarded_refs))
    return scanned, failures, review_required, safe_verifier_refs


def main() -> int:
    failures: list[str] = []
    review_required: list[str] = []

    print("ENGEL_AGENT_SKILL_CANDIDATE_PIPELINE_VERIFIER")
    print(f"ROOT {ROOT}")
    print("Mode: local static verification only; no agent/skill/runtime/provider/model launch")

    try:
        data = load_contract()
        text = combined_text(data)
        check_contract_values(data)
        check_pipeline_stages(data)
        check_storage_policy(data, text)
        check_schema(data, "candidate_agent_schema", AGENT_FIELDS, "agent", "agent schema checks")
        check_schema(data, "candidate_skill_schema", SKILL_FIELDS, "skill", "skill schema checks")
        check_forbidden_behaviors(data, text)
        check_external_ai_interaction(data)
        _candidate_scanned, candidate_failures = scan_candidate_storage()
        failures.extend(candidate_failures)
        _source_scanned, source_failures, source_review, _safe_refs = scan_active_source()
        failures.extend(source_failures)
        review_required.extend(source_review)
        failures.extend(f"review required active source finding: {item}" for item in source_review)
    except CheckFailure as exc:
        failures.append(str(exc))

    print_result("review required findings", "INFO", str(len(review_required)))
    for item in review_required[:40]:
        print_result("review required", "REVIEW_REQUIRED", item)
    if len(review_required) > 40:
        print_result("review required", "INFO", f"{len(review_required) - 40} additional findings suppressed")

    if failures:
        print_result("candidate pipeline checks", "FAIL", f"failures={len(failures)}")
        for failure in failures:
            print_result("candidate pipeline check", "FAIL", failure)
        print("AGENT_SKILL_CANDIDATE_PIPELINE_VERIFICATION_FAIL")
        return 1

    print_result("contract checks", "PASS")
    print_result("pipeline stage checks", "PASS")
    print_result("candidate storage checks", "PASS")
    print_result("agent schema checks", "PASS")
    print_result("skill schema checks", "PASS")
    print_result("forbidden behavior checks", "PASS")
    print_result("external AI interaction checks", "PASS")
    print_result("active source scan result", "PASS")
    print("AGENT_SKILL_CANDIDATE_PIPELINE_VERIFICATION_PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
