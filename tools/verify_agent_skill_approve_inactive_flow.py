#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import py_compile
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()

CONTRACT_JSON = ROOT / "memory" / "ENGEL_AGENT_SKILL_APPROVE_INACTIVE_FLOW_CONTRACT_V1.json"
CONTRACT_MD = ROOT / "memory" / "ENGEL_AGENT_SKILL_APPROVE_INACTIVE_FLOW_CONTRACT_V1.md"
CONTRACT_REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_AGENT_SKILL_APPROVE_INACTIVE_FLOW_CONTRACT_V1.md"

CANDIDATE_STORAGE = ROOT / "reports" / "agent_skill_candidates"
FUTURE_REGISTRY_JSON = ROOT / "memory" / "ENGEL_AGENT_SKILL_APPROVED_INACTIVE_REGISTRY_V1.json"
FUTURE_REGISTRY_MD = ROOT / "memory" / "ENGEL_AGENT_SKILL_APPROVED_INACTIVE_REGISTRY_V1.md"

OPTIONAL_EVIDENCE = [
    ROOT / "reports" / "codex_bridge" / "ENGEL_AGENT_SKILL_FIRST_CANDIDATE_PROPOSAL_V1.md",
    ROOT / "reports" / "codex_bridge" / "ENGEL_AGENT_SKILL_FIRST_CANDIDATE_HUMAN_REVIEW_V1.md",
    ROOT / "reports" / "codex_bridge" / "ENGEL_AGENT_SKILL_FIRST_CANDIDATE_HUMAN_REVIEW_V1.json",
    ROOT / "memory" / "ENGEL_AGENT_SKILL_APPROVED_INACTIVE_REGISTRY_CONTRACT_V1.json",
    ROOT / "tools" / "verify_agent_skill_approved_inactive_registry.py",
    ROOT / "tools" / "verify_agent_skill_candidate_scaffold.py",
    ROOT / "tools" / "verify_agent_skill_candidate_scaffold_command.py",
    ROOT / "tools" / "verify_agent_skill_candidate_pipeline.py",
    ROOT / "tools" / "verify_external_ai_agent_access_contract.py",
    ROOT / "tools" / "verify_untrusted_content_policy.py",
    ROOT / "tools" / "verify_de_bruijn_import_boundaries.py",
    ROOT / "tools" / "verify_engel_debruijn_quantum_automation_file_structure.py",
]

REQUIRED_VALUES = {
    "contract_id": "ENGEL_AGENT_SKILL_APPROVE_INACTIVE_FLOW_CONTRACT_V1",
    "status": "contract_only",
    "active_workspace": r"D:\b.WorkSpace\Engel App",
    "approve_inactive_enabled_now": False,
    "no_candidate_approved_now": True,
    "live_agent_creation_enabled_now": False,
    "live_skill_creation_enabled_now": False,
    "runtime_enabled_now": False,
    "autorun_enabled_now": False,
    "external_ai_access_enabled_now": False,
    "approval_phrase": "APPROVE_AGENT_SKILL_APPROVED_INACTIVE_ENTRY_V1",
}

REQUIRED_KEYS = [
    "future_command",
    "inactive_registry_files",
    "approval_receipt_schema",
    "validation_gates",
    "dangerous_flags_must_remain_false",
    "allowed_future_outputs",
    "forbidden_outputs",
    "rollback_correction_model",
    "future_verifier",
    "stop_conditions",
    "recommended_next_slice",
    "safety_preserved",
]

TOP_LEVEL_FALSE_VALUES = [
    "inactive_registry_entry_created_now",
    "approve_inactive_flow_implemented_now",
    "candidate_promotion_enabled_now",
    "trusted_memory_write_allowed",
    "source_mutation_allowed",
    "route_mutation_allowed",
    "queue_mutation_allowed",
    "network_allowed",
    "provider_api_allowed",
    "local_llm_inference_allowed",
    "package_install_allowed",
    "mobile_runtime_allowed",
    "remote_queen_runtime_allowed",
    "build_or_promote_allowed",
]

FUTURE_COMMAND_REQUIRED_TRUTHS = [
    "approval_phrase_required",
    "candidate_id_required",
    "candidate_type_required",
    "arbitrary_paths_rejected",
    "candidate_files_loaded_only_from_approved_candidate_storage",
    "human_review_report_required",
    "verifier_gates_required",
    "runtime_remains_false",
    "autorun_remains_false",
    "activation_contract_required_remains_true",
]

RECEIPT_FIELDS = [
    "candidate_id",
    "candidate_type",
    "source_candidate_json",
    "source_candidate_md",
    "human_review_report_path",
    "verifier_results",
    "registry_entry_id",
    "registry_path",
    "approved_inactive_timestamp",
    "safety_flags",
    "activation_contract_required",
    "not_live_statement",
    "not_runnable_statement",
    "not_scheduled_statement",
]

VALIDATION_GATE_PHRASES = [
    "candidate json exists",
    "candidate md exists",
    "candidate_id matches requested id",
    "candidate status is candidate_only or reviewed_candidate",
    "candidate trust_status is untrusted_candidate or reviewed_candidate",
    "human review report exists",
    "candidate schema/scaffold verifier passes",
    "approved inactive registry verifier passes",
    "untrusted content verifier passes",
    "authority hierarchy passes",
    "prompt injection guard passes",
    "external ai verifier passes",
    "all dangerous flags false",
    "receipt_required true",
    "activation_contract_required true",
]

DANGEROUS_FLAGS = [
    "runtime_enabled",
    "autorun_enabled",
    "install_enabled",
    "startup_load_allowed",
    "auto_discovery_execution_allowed",
    "trusted_memory_write_allowed",
    "source_mutation_allowed",
    "route_mutation_allowed",
    "queue_mutation_allowed",
    "network_allowed",
    "provider_api_allowed",
    "external_ai_access_allowed",
    "local_llm_inference_allowed",
    "package_install_allowed",
    "mobile_runtime_allowed",
    "remote_queen_runtime_allowed",
]

ALLOWED_OUTPUT_TERMS = [
    "inactive registry json",
    "inactive registry markdown",
    "one approved inactive registry entry",
    "one approval receipt",
]

FORBIDDEN_OUTPUT_TERMS = [
    "live runtime files",
    "startup hooks",
    "scheduler entries",
    "service entries",
    "route execution handlers",
    "trusted-memory entries",
    "source patches from candidate content",
    "external ai task packets",
    "model calls",
]

CANDIDATE_FALSE_FIELDS = [
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
    "install_enabled",
    "startup_load_allowed",
    "auto_discovery_execution_allowed",
    "external_ai_access_allowed",
    "local_llm_inference_allowed",
]

REGISTRY_FALSE_FIELDS = DANGEROUS_FLAGS

ACTIVE_SOURCE_SUFFIXES = {".py", ".ps1", ".bat", ".cmd", ".sh", ".psm1", ".spec"}
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
    ".pdf",
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
    "reports",
    "memory",
}

ACTIVE_SOURCE_PATTERNS = [
    ("approve_inactive_enabled_now_true", re.compile(r"\bapprove_inactive_enabled_now\s*[:=]\s*(?:True|true|\$true)\b")),
    ("approve_inactive_candidate", re.compile(r"\bapprove_inactive_candidate\b", re.I)),
    ("move_candidate_to_inactive_registry", re.compile(r"\bmove_candidate_to_inactive_registry\b", re.I)),
    ("create_approved_inactive_entry", re.compile(r"\bcreate_approved_inactive_entry\b", re.I)),
    ("activate_agent", re.compile(r"\bactivate_agent\b", re.I)),
    ("activate_skill", re.compile(r"\bactivate_skill\b", re.I)),
    ("runtime_enabled_true", re.compile(r"\bruntime_enabled\s*[:=]\s*(?:True|true|\$true)\b")),
    ("autorun_enabled_true", re.compile(r"\bautorun_enabled\s*[:=]\s*(?:True|true|\$true)\b")),
    ("external_ai_access_enabled_now_true", re.compile(r"\bexternal_ai_access_enabled_now\s*[:=]\s*(?:True|true|\$true)\b")),
    ("trusted_memory_write_allowed_true", re.compile(r"\btrusted_memory_write_allowed\s*[:=]\s*(?:True|true|\$true)\b")),
    ("source_mutation_allowed_true", re.compile(r"\bsource_mutation_allowed\s*[:=]\s*(?:True|true|\$true)\b")),
    ("route_mutation_allowed_true", re.compile(r"\broute_mutation_allowed\s*[:=]\s*(?:True|true|\$true)\b")),
    ("queue_mutation_allowed_true", re.compile(r"\bqueue_mutation_allowed\s*[:=]\s*(?:True|true|\$true)\b")),
    ("local_llm_inference_allowed_true", re.compile(r"\blocal_llm_inference_allowed\s*[:=]\s*(?:True|true|\$true)\b")),
    ("mobile_runtime_allowed_true", re.compile(r"\bmobile_runtime_allowed\s*[:=]\s*(?:True|true|\$true)\b")),
    ("remote_queen_runtime_allowed_true", re.compile(r"\bremote_queen_runtime_allowed\s*[:=]\s*(?:True|true|\$true)\b")),
]

SAFE_CONTEXT_HINTS = [
    "forbidden",
    "future",
    "disabled",
    "blocked",
    "not enabled",
    "must remain false",
    "review",
    "verifier",
    "pattern",
    "risk",
    "contract",
]


class CheckFailure(Exception):
    pass


def rel(path: Path) -> str:
    try:
        return str(path.resolve(strict=False).relative_to(ROOT.resolve(strict=False))).replace("/", "\\")
    except ValueError:
        return str(path)


def print_result(status: str, label: str, detail: str = "") -> None:
    suffix = f" {detail}" if detail else ""
    print(f"{status} {label}{suffix}")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CheckFailure(f"missing required JSON {rel(path)}") from exc
    except json.JSONDecodeError as exc:
        raise CheckFailure(f"invalid JSON {rel(path)}: {exc}") from exc


def normalized_text(values: Any) -> str:
    if isinstance(values, str):
        return values.lower()
    return json.dumps(values, sort_keys=True).lower()


def require_terms(values: Any, terms: list[str], label: str) -> None:
    text = normalized_text(values)
    missing = [term for term in terms if term.lower() not in text]
    require(not missing, f"{label} missing terms: {', '.join(missing)}")


def verify_required_files() -> None:
    required = [CONTRACT_JSON, CONTRACT_MD, CONTRACT_REPORT]
    missing = [rel(path) for path in required if not path.exists()]
    require(not missing, "missing required contract files: " + ", ".join(missing))
    print_result("PASS", "required contract files", "JSON, markdown, and report exist")
    for path in OPTIONAL_EVIDENCE:
        if path.exists():
            print_result("INFO", "optional evidence", rel(path))
        else:
            print_result("SKIP", "optional evidence missing", rel(path))


def verify_contract_values(contract: dict[str, Any]) -> None:
    for key, expected in REQUIRED_VALUES.items():
        require(contract.get(key) == expected, f"contract value mismatch {key}: expected {expected!r}, got {contract.get(key)!r}")
        print_result("PASS", "contract value", f"{key}={expected!r}")
    for key in TOP_LEVEL_FALSE_VALUES:
        require(contract.get(key) is False, f"{key} must be false")
    missing = [key for key in REQUIRED_KEYS if key not in contract]
    require(not missing, "missing required contract keys: " + ", ".join(missing))
    print_result("PASS", "required contract keys", str(len(REQUIRED_KEYS)))


def verify_future_command(contract: dict[str, Any]) -> None:
    future_command = contract.get("future_command")
    require(isinstance(future_command, dict), "future_command must be an object")
    require("engel ai" in normalized_text(future_command.get("route_shape", "")), "future_command must document one explicit Engel AI route shape")
    require(contract.get("approval_phrase") in future_command.get("route_shape", ""), "future_command route shape must include approval phrase")
    for key in FUTURE_COMMAND_REQUIRED_TRUTHS:
        require(future_command.get(key) is True, f"future_command.{key} must be true")
    require(future_command.get("command_enabled_now") is False, "future command must remain disabled now")
    print_result("PASS", "future command checks", "explicit route shape, approval phrase, storage, review, verifier, runtime, autorun, and activation boundaries documented")


def verify_receipt_schema(contract: dict[str, Any]) -> None:
    schema = contract.get("approval_receipt_schema")
    require(isinstance(schema, dict), "approval_receipt_schema must be an object")
    fields = schema.get("required_fields")
    require(isinstance(fields, list), "approval_receipt_schema.required_fields must be a list")
    missing = [field for field in RECEIPT_FIELDS if field not in fields]
    require(not missing, "approval receipt schema missing fields: " + ", ".join(missing))
    required_values = schema.get("required_values", {})
    require(required_values.get("activation_contract_required") is True, "receipt schema must keep activation_contract_required true")
    for key in ["runtime_enabled", "autorun_enabled", "startup_load_allowed", "auto_discovery_execution_allowed"]:
        require(required_values.get(key) is False, f"receipt schema required value {key} must be false")
    print_result("PASS", "approval receipt schema checks", f"{len(RECEIPT_FIELDS)} fields present")


def verify_validation_gates(contract: dict[str, Any]) -> None:
    gates = contract.get("validation_gates")
    require(isinstance(gates, list), "validation_gates must be a list")
    require_terms(gates, VALIDATION_GATE_PHRASES, "validation_gates")
    print_result("PASS", "validation gate checks", str(len(VALIDATION_GATE_PHRASES)))


def verify_dangerous_flags(contract: dict[str, Any]) -> None:
    flags = contract.get("dangerous_flags_must_remain_false")
    require(isinstance(flags, list), "dangerous_flags_must_remain_false must be a list")
    missing = [flag for flag in DANGEROUS_FLAGS if flag not in flags]
    require(not missing, "dangerous flag list missing: " + ", ".join(missing))
    required_entry_values = contract.get("future_registry_entry_required_values", {})
    for flag in DANGEROUS_FLAGS:
        if flag in required_entry_values:
            require(required_entry_values.get(flag) is False, f"future registry entry required value {flag} must be false")
    print_result("PASS", "dangerous flag checks", f"{len(DANGEROUS_FLAGS)} flags must remain false")


def verify_allowed_and_forbidden_outputs(contract: dict[str, Any]) -> None:
    allowed = contract.get("allowed_future_outputs")
    forbidden = contract.get("forbidden_outputs")
    require(isinstance(allowed, list), "allowed_future_outputs must be a list")
    require(isinstance(forbidden, list), "forbidden_outputs must be a list")
    require_terms(allowed, ALLOWED_OUTPUT_TERMS, "allowed_future_outputs")
    require_terms(forbidden, FORBIDDEN_OUTPUT_TERMS, "forbidden_outputs")
    print_result("PASS", "allowed/forbidden output checks", "future outputs limited to registry entry/receipt and forbidden live outputs documented")


def verify_rollback_model(contract: dict[str, Any]) -> None:
    rollback = contract.get("rollback_correction_model")
    require(isinstance(rollback, dict), "rollback_correction_model must be an object")
    require(rollback.get("incorrect_inactive_entry_silently_deleted") is False, "incorrect inactive entry must not be silently deleted")
    require(rollback.get("entry_marked_revoked_inactive_or_blocked_pending_review") is True, "incorrect entry must be marked revoked/block pending review")
    require(rollback.get("correction_receipt_written") is True, "correction receipt must be written")
    require(rollback.get("verifiers_rerun") is True, "verifiers must rerun")
    require(rollback.get("activation_occurs") is False, "rollback/correction must not activate")
    print_result("PASS", "rollback/correction checks", "revocation/blocking receipt and verifier rerun required; no activation")


def verify_registry_files(contract: dict[str, Any]) -> None:
    registry_files = contract.get("inactive_registry_files")
    require(isinstance(registry_files, dict), "inactive_registry_files must be an object")
    require(registry_files.get("json") == "memory\\ENGEL_AGENT_SKILL_APPROVED_INACTIVE_REGISTRY_V1.json", "inactive registry JSON path mismatch")
    require(registry_files.get("markdown") == "memory\\ENGEL_AGENT_SKILL_APPROVED_INACTIVE_REGISTRY_V1.md", "inactive registry Markdown path mismatch")
    require(registry_files.get("entries_created_now") is False, "inactive registry entries must not be created now")
    require(registry_files.get("runtime_enabled") is False, "inactive registry runtime_enabled must be false")
    require(registry_files.get("autorun_enabled") is False, "inactive registry autorun_enabled must be false")
    print_result("PASS", "inactive registry file contract checks", "future paths documented and disabled now")


def verify_candidate_inventory() -> None:
    if not CANDIDATE_STORAGE.exists():
        print_result("SKIP", "candidate inventory", "candidate storage does not exist")
        return
    json_files = sorted(CANDIDATE_STORAGE.glob("*.json"))
    md_files = sorted(CANDIDATE_STORAGE.glob("*.md"))
    for path in json_files:
        candidate = load_json(path)
        candidate_id = candidate.get("candidate_id", path.stem)
        if candidate_id == "verifier_health_check":
            require(candidate.get("status") == "candidate_only", "verifier_health_check must remain candidate_only")
            require(candidate.get("trust_status") == "untrusted_candidate", "verifier_health_check must remain untrusted_candidate")
            print_result("INFO", "candidate inventory", "verifier_health_check is still candidate-only and untrusted; not approved or moved")
        require(candidate.get("status") != "approved_inactive", f"candidate file has approved_inactive status without registry evidence: {rel(path)}")
        for field in CANDIDATE_FALSE_FIELDS:
            if field in candidate:
                require(candidate.get(field) is False, f"{rel(path)} has dangerous flag true or non-false: {field}")
        require(candidate.get("activation_contract_required") is True, f"{rel(path)} must require activation contract")
        require(candidate.get("receipt_required") is True, f"{rel(path)} must require receipt")
    print_result("PASS", "candidate inventory checks", f"json={len(json_files)} md={len(md_files)}")


def verify_inactive_registry_absence_or_safety() -> None:
    if not FUTURE_REGISTRY_JSON.exists() and not FUTURE_REGISTRY_MD.exists():
        print_result("SKIP", "future inactive registry", "no inactive registry exists yet; expected at this phase")
        return
    require(FUTURE_REGISTRY_JSON.exists(), "inactive registry Markdown exists without JSON registry")
    registry = load_json(FUTURE_REGISTRY_JSON)
    require(isinstance(registry.get("entries", []), list), "inactive registry entries must be a list")
    require(registry.get("runtime_enabled") is False, "registry-level runtime_enabled must be false")
    require(registry.get("autorun_enabled") is False, "registry-level autorun_enabled must be false")
    for entry in registry.get("entries", []):
        require(entry.get("activation_contract_required") is True, "registry entry activation_contract_required must be true")
        for field in REGISTRY_FALSE_FIELDS:
            if field in entry:
                require(entry.get(field) is False, f"registry entry dangerous flag must be false: {field}")
    print_result("PASS", "future inactive registry", f"entries={len(registry.get('entries', []))}")


def should_scan_file(path: Path) -> bool:
    if path == SELF:
        return False
    if path.suffix.lower() in BINARY_SUFFIXES:
        return False
    if path.suffix.lower() not in ACTIVE_SOURCE_SUFFIXES:
        return False
    parts = {part.lower() for part in path.parts}
    return not bool(parts & EXCLUDE_DIRS)


def is_safe_source_reference(path: Path, line: str) -> bool:
    if path.name.startswith("verify_") or path.parent.name == "tools":
        return True
    lowered = line.lower()
    return any(hint in lowered for hint in SAFE_CONTEXT_HINTS)


def verify_active_source_scan() -> None:
    failures: list[str] = []
    review_required: list[str] = []
    safe_references = 0
    scanned = 0
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [dirname for dirname in dirnames if dirname.lower() not in EXCLUDE_DIRS]
        for filename in filenames:
            path = Path(dirpath) / filename
            if not should_scan_file(path):
                continue
            scanned += 1
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                review_required.append(f"{rel(path)} read error {type(exc).__name__}")
                continue
            hits: list[str] = []
            for label, pattern in ACTIVE_SOURCE_PATTERNS:
                for match in pattern.finditer(text):
                    start = text.rfind("\n", 0, match.start()) + 1
                    end = text.find("\n", match.end())
                    if end == -1:
                        end = len(text)
                    line = text[start:end]
                    if is_safe_source_reference(path, line):
                        safe_references += 1
                    else:
                        hits.append(label)
            if hits:
                review_required.append(f"{rel(path)} hits={','.join(sorted(set(hits)))}")
    for item in review_required:
        print_result("REVIEW_REQUIRED", "active-source finding", item)
    require(not failures, "active source failures: " + "; ".join(failures))
    require(not review_required, "active source review required: " + "; ".join(review_required))
    print_result("INFO", "active source files scanned", str(scanned))
    print_result("INFO", "safe verifier/review references", str(safe_references))
    print_result("PASS", "active source scan result", "failures=0 review_required=0")


def verify_python_compile() -> None:
    py_compile.compile(str(SELF), doraise=True)
    print_result("PASS", "py_compile", rel(SELF))


def main() -> int:
    print("ENGEL_AGENT_SKILL_APPROVE_INACTIVE_FLOW_VERIFIER")
    print(f"ROOT {ROOT}")
    print("Mode: local static verification only; no approval, registry entry, runtime, provider, model, route, queue, or trusted-memory behavior")
    try:
        verify_python_compile()
        verify_required_files()
        contract = load_json(CONTRACT_JSON)
        print_result("PASS", "contract JSON parse", rel(CONTRACT_JSON))
        verify_contract_values(contract)
        verify_future_command(contract)
        verify_registry_files(contract)
        verify_receipt_schema(contract)
        verify_validation_gates(contract)
        verify_dangerous_flags(contract)
        verify_allowed_and_forbidden_outputs(contract)
        verify_rollback_model(contract)
        verify_candidate_inventory()
        verify_inactive_registry_absence_or_safety()
        verify_active_source_scan()
    except py_compile.PyCompileError as exc:
        print_result("FAIL", "py_compile", str(exc))
        return 1
    except CheckFailure as exc:
        print_result("FAIL", "approve-inactive flow verifier", str(exc))
        return 1

    print_result("PASS", "contract checks")
    print_result("PASS", "future command checks")
    print_result("PASS", "approval receipt schema checks")
    print_result("PASS", "validation gate checks")
    print_result("PASS", "dangerous flag checks")
    print_result("PASS", "allowed/forbidden output checks")
    print_result("PASS", "rollback/correction checks")
    print_result("PASS", "candidate inventory result")
    print_result("PASS", "inactive registry result")
    print_result("PASS", "active source scan result")
    print("AGENT_SKILL_APPROVE_INACTIVE_FLOW_VERIFICATION_PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
