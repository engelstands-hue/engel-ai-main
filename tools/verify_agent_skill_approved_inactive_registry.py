#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()

CONTRACT_JSON = ROOT / "memory" / "ENGEL_AGENT_SKILL_APPROVED_INACTIVE_REGISTRY_CONTRACT_V1.json"
CONTRACT_MD = ROOT / "memory" / "ENGEL_AGENT_SKILL_APPROVED_INACTIVE_REGISTRY_CONTRACT_V1.md"
CONTRACT_REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_AGENT_SKILL_APPROVED_INACTIVE_REGISTRY_CONTRACT_V1.md"

CANDIDATE_STORAGE = ROOT / "reports" / "agent_skill_candidates"
FUTURE_REGISTRY_JSON = ROOT / "memory" / "ENGEL_AGENT_SKILL_APPROVED_INACTIVE_REGISTRY_V1.json"
FUTURE_REGISTRY_MD = ROOT / "memory" / "ENGEL_AGENT_SKILL_APPROVED_INACTIVE_REGISTRY_V1.md"

OPTIONAL_EVIDENCE = [
    ROOT / "reports" / "codex_bridge" / "ENGEL_AGENT_SKILL_FIRST_CANDIDATE_PROPOSAL_V1.md",
    ROOT / "reports" / "codex_bridge" / "ENGEL_AGENT_SKILL_FIRST_CANDIDATE_HUMAN_REVIEW_V1.md",
    ROOT / "reports" / "codex_bridge" / "ENGEL_AGENT_SKILL_FIRST_CANDIDATE_HUMAN_REVIEW_V1.json",
    ROOT / "tools" / "verify_agent_skill_candidate_scaffold.py",
    ROOT / "tools" / "verify_agent_skill_candidate_scaffold_command.py",
    ROOT / "tools" / "verify_agent_skill_candidate_pipeline.py",
    ROOT / "tools" / "verify_external_ai_agent_access_contract.py",
    ROOT / "tools" / "verify_untrusted_content_policy.py",
    ROOT / "tools" / "verify_de_bruijn_import_boundaries.py",
]

REQUIRED_VALUES = {
    "contract_id": "ENGEL_AGENT_SKILL_APPROVED_INACTIVE_REGISTRY_CONTRACT_V1",
    "status": "contract_only",
    "active_workspace": r"D:\b.WorkSpace\Engel App",
    "no_candidate_approved_now": True,
    "approved_inactive_registry_created_now": False,
    "live_agent_creation_enabled_now": False,
    "live_skill_creation_enabled_now": False,
    "runtime_enabled_now": False,
    "autorun_enabled_now": False,
    "external_ai_access_enabled_now": False,
    "trusted_memory_write_allowed": False,
    "source_mutation_allowed": False,
    "route_mutation_allowed": False,
    "queue_mutation_allowed": False,
    "network_allowed": False,
    "provider_api_allowed": False,
    "local_llm_inference_allowed": False,
    "package_install_allowed": False,
    "mobile_runtime_allowed": False,
    "remote_queen_runtime_allowed": False,
}

REQUIRED_KEYS = [
    "lifecycle_states",
    "future_registry_location",
    "inactive_registry_entry_schema",
    "promotion_to_inactive_rules",
    "approved_inactive_not_meaning",
    "future_verifier",
    "future_implementation_sequence",
    "stop_conditions",
    "recommended_next_slice",
    "safety_preserved",
]

LIFECYCLE_STATES = {
    "candidate_only",
    "reviewed_candidate",
    "approved_inactive",
    "activation_contract_required",
    "active_runtime_enabled",
    "autorun_enabled",
}

ENTRY_FIELDS = [
    "registry_entry_id",
    "candidate_id",
    "candidate_type",
    "name",
    "source_candidate_json",
    "source_candidate_md",
    "review_report",
    "approval_receipt",
    "approved_inactive_at",
    "approved_by",
    "status",
    "trust_status",
    "allowed_inputs",
    "allowed_outputs",
    "allowed_actions",
    "forbidden_actions",
    "required_verifiers",
    "activation_contract_required",
    "runtime_enabled",
    "autorun_enabled",
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
    "receipt_path",
    "verifier_results",
]

ENTRY_FALSE_FIELDS = [
    "runtime_enabled",
    "autorun_enabled",
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
]

PROMOTION_RULE_PHRASES = [
    "candidate json exists",
    "candidate markdown exists",
    "candidate status is candidate_only or reviewed_candidate",
    "candidate trust_status is untrusted_candidate or reviewed_candidate",
    "candidate human-review report exists",
    "required verifiers pass",
    "no dangerous flags are true",
    "inactive registry entry is created",
    "approval receipt is written",
    "activation_contract_required remains true",
    "runtime_enabled remains false",
    "autorun_enabled remains false",
]

NOT_MEANING_TERMS = [
    "installed",
    "active",
    "runnable",
    "scheduled",
    "startup-loaded",
    "trusted-memory writer",
    "source editor",
    "external ai caller",
    "web agent",
    "local llm runtime user",
    "remote queen runtime user",
    "mobile runtime user",
]

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
}

ACTIVE_SOURCE_PATTERNS = [
    ("approve_inactive_agent_now", re.compile(r"\bapprove_inactive_agent_now\b", re.I)),
    ("approve_inactive_skill_now", re.compile(r"\bapprove_inactive_skill_now\b", re.I)),
    ("create_approved_inactive_registry_entry", re.compile(r"\bcreate_approved_inactive_registry_entry\b", re.I)),
    ("activate_agent", re.compile(r"\bactivate_agent\b", re.I)),
    ("activate_skill", re.compile(r"\bactivate_skill\b", re.I)),
    ("runtime_enabled_true", re.compile(r"\bruntime_enabled\s*[:=]\s*(?:True|true|\$true)\b")),
    ("autorun_enabled_true", re.compile(r"\bautorun_enabled\s*[:=]\s*(?:True|true|\$true)\b")),
    ("startup_load_allowed_true", re.compile(r"\bstartup_load_allowed\s*[:=]\s*(?:True|true|\$true)\b")),
    (
        "auto_discovery_execution_allowed_true",
        re.compile(r"\bauto_discovery_execution_allowed\s*[:=]\s*(?:True|true|\$true)\b"),
    ),
    (
        "trusted_memory_write_allowed_true",
        re.compile(r"\btrusted_memory_write_allowed\s*[:=]\s*(?:True|true|\$true)\b"),
    ),
    ("source_mutation_allowed_true", re.compile(r"\bsource_mutation_allowed\s*[:=]\s*(?:True|true|\$true)\b")),
    ("route_mutation_allowed_true", re.compile(r"\broute_mutation_allowed\s*[:=]\s*(?:True|true|\$true)\b")),
    (
        "external_ai_access_allowed_true",
        re.compile(r"\bexternal_ai_access_allowed\s*[:=]\s*(?:True|true|\$true)\b"),
    ),
    (
        "local_llm_inference_allowed_true",
        re.compile(r"\blocal_llm_inference_allowed\s*[:=]\s*(?:True|true|\$true)\b"),
    ),
    ("mobile_runtime_allowed_true", re.compile(r"\bmobile_runtime_allowed\s*[:=]\s*(?:True|true|\$true)\b")),
    (
        "remote_queen_runtime_allowed_true",
        re.compile(r"\bremote_queen_runtime_allowed\s*[:=]\s*(?:True|true|\$true)\b"),
    ),
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


def fail(message: str) -> None:
    raise CheckFailure(message)


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(read_text(path))
    require(isinstance(data, dict), f"{rel(path)} must contain a JSON object")
    return data


def normalized(value: Any) -> str:
    return " ".join(str(value).lower().replace("\\", "/").replace("_", "_").split())


def require_files() -> None:
    missing = [path for path in [CONTRACT_JSON, CONTRACT_MD, CONTRACT_REPORT] if not path.exists()]
    require(not missing, "missing required contract files: " + ", ".join(rel(path) for path in missing))
    print_result("PASS", "required contract files", "JSON, markdown, and report exist")
    if CANDIDATE_STORAGE.exists():
        print_result("INFO", "optional evidence", rel(CANDIDATE_STORAGE))
    else:
        print_result("SKIP", "optional evidence", rel(CANDIDATE_STORAGE))
    for path in OPTIONAL_EVIDENCE:
        print_result("INFO" if path.exists() else "SKIP", "optional evidence", rel(path))


def check_contract_values(data: dict[str, Any]) -> None:
    for key, expected in REQUIRED_VALUES.items():
        actual = data.get(key)
        require(actual == expected, f"contract value {key} expected {expected!r}, got {actual!r}")
        print_result("PASS", "contract value", f"{key}={actual!r}")
    missing = [key for key in REQUIRED_KEYS if key not in data]
    require(not missing, "missing required contract keys: " + ", ".join(missing))
    print_result("PASS", "required contract keys", str(len(REQUIRED_KEYS)))


def check_lifecycle_states(data: dict[str, Any]) -> None:
    states = data.get("lifecycle_states")
    require(isinstance(states, list), "lifecycle_states must be a list")
    present = {
        str(item.get("state", "")).strip()
        for item in states
        if isinstance(item, dict)
    } | {str(item).strip() for item in states if isinstance(item, str)}
    missing = sorted(LIFECYCLE_STATES - present)
    require(not missing, "missing lifecycle states: " + ", ".join(missing))
    state_by_name = {item.get("state"): item for item in states if isinstance(item, dict)}
    for future_state in ["active_runtime_enabled", "autorun_enabled"]:
        item = state_by_name.get(future_state, {})
        require(item.get("future_only") is True, f"{future_state} must be future_only true")
    print_result("PASS", "lifecycle state checks", ", ".join(sorted(LIFECYCLE_STATES)))


def check_future_registry_location(data: dict[str, Any]) -> None:
    location = data.get("future_registry_location")
    require(isinstance(location, dict), "future_registry_location must be an object")
    require(location.get("json") == r"memory\ENGEL_AGENT_SKILL_APPROVED_INACTIVE_REGISTRY_V1.json", "registry JSON path mismatch")
    require(location.get("markdown") == r"memory\ENGEL_AGENT_SKILL_APPROVED_INACTIVE_REGISTRY_V1.md", "registry Markdown path mismatch")
    require(location.get("created_now") is False, "future registry location must say created_now false")

    if not FUTURE_REGISTRY_JSON.exists():
        require(not FUTURE_REGISTRY_MD.exists(), "future registry Markdown exists without registry JSON")
        print_result("SKIP", "future registry file", "no inactive registry exists yet")
        return

    require(FUTURE_REGISTRY_MD.exists(), "future registry JSON exists but Markdown companion is missing")
    registry = load_json(FUTURE_REGISTRY_JSON)
    require(isinstance(registry.get("entries"), list), "future registry entries must be a list")
    require(registry.get("runtime_enabled") is False, "future registry runtime_enabled must be false")
    require(registry.get("autorun_enabled") is False, "future registry autorun_enabled must be false")
    require(registry.get("status") in {"registry_contract_only", "approved_inactive_registry"}, "future registry status is not recognized")
    for index, entry in enumerate(registry["entries"]):
        validate_registry_entry(entry, index)
    print_result("PASS", "future registry file", f"entries={len(registry['entries'])}")


def check_entry_schema(data: dict[str, Any]) -> None:
    schema = data.get("inactive_registry_entry_schema")
    require(isinstance(schema, dict), "inactive_registry_entry_schema must be an object")
    required_fields = schema.get("required_fields")
    require(isinstance(required_fields, list), "entry required_fields must be a list")
    missing = [field for field in ENTRY_FIELDS if field not in required_fields]
    require(not missing, "missing inactive registry entry schema fields: " + ", ".join(missing))
    values = schema.get("required_values")
    require(isinstance(values, dict), "entry required_values must be an object")
    require(values.get("status") == "approved_inactive", "entry status required value mismatch")
    require(values.get("trust_status") == "reviewed_but_inactive", "entry trust_status required value mismatch")
    require(values.get("activation_contract_required") is True, "activation_contract_required must be true")
    for field in ENTRY_FALSE_FIELDS:
        require(values.get(field) is False, f"{field} must be required false")
    print_result("PASS", "inactive registry schema checks", f"{len(ENTRY_FIELDS)} fields present")


def check_promotion_rules(data: dict[str, Any]) -> None:
    rules = data.get("promotion_to_inactive_rules")
    require(isinstance(rules, list), "promotion_to_inactive_rules must be a list")
    joined = normalized(" ".join(str(item) for item in rules))
    missing = [phrase for phrase in PROMOTION_RULE_PHRASES if normalized(phrase) not in joined]
    require(not missing, "missing promotion-to-inactive rule phrases: " + ", ".join(missing))
    print_result("PASS", "promotion-to-inactive rule checks", str(len(PROMOTION_RULE_PHRASES)))


def check_not_meaning(data: dict[str, Any]) -> None:
    meanings = data.get("approved_inactive_not_meaning")
    require(isinstance(meanings, list), "approved_inactive_not_meaning must be a list")
    joined = normalized(" ".join(str(item) for item in meanings))
    missing = [term for term in NOT_MEANING_TERMS if normalized(term) not in joined]
    require(not missing, "approved inactive not-meaning list missing: " + ", ".join(missing))
    print_result("PASS", "approved-inactive boundary checks", str(len(NOT_MEANING_TERMS)))


def project_path(value: Any) -> Path:
    require(isinstance(value, str) and value.strip(), "entry path value must be a non-empty string")
    path = (ROOT / value).resolve(strict=False)
    try:
        path.relative_to(ROOT.resolve(strict=False))
    except ValueError as exc:
        raise CheckFailure(f"entry path escapes workspace: {value}") from exc
    return path


def validate_registry_entry(entry: Any, index: int) -> None:
    require(isinstance(entry, dict), f"registry entry {index} must be an object")
    missing = [field for field in ENTRY_FIELDS if field not in entry]
    require(not missing, f"registry entry {index} missing fields: " + ", ".join(missing))
    require(entry.get("status") == "approved_inactive", f"registry entry {index} status must be approved_inactive")
    require(entry.get("trust_status") == "reviewed_but_inactive", f"registry entry {index} trust_status mismatch")
    require(entry.get("activation_contract_required") is True, f"registry entry {index} activation contract required")
    for field in ENTRY_FALSE_FIELDS:
        require(entry.get(field) is False, f"registry entry {index} {field} must be false")
    for field in ["source_candidate_json", "source_candidate_md", "review_report", "approval_receipt", "receipt_path"]:
        path = project_path(entry.get(field))
        require(path.exists(), f"registry entry {index} references missing {field}: {rel(path)}")
    require(entry.get("candidate_type") in {"agent", "skill"}, f"registry entry {index} invalid candidate_type")


def validate_candidate_json(path: Path) -> dict[str, Any]:
    data = load_json(path)
    require(data.get("status") == "candidate_only", f"{rel(path)} status must remain candidate_only")
    require(data.get("trust_status") == "untrusted_candidate", f"{rel(path)} trust_status must remain untrusted_candidate")
    for field in CANDIDATE_FALSE_FIELDS:
        require(data.get(field) is False, f"{rel(path)} {field} must be false")
    if data.get("candidate_type") == "skill":
        require(data.get("install_enabled") is False, f"{rel(path)} install_enabled must be false")
    if data.get("candidate_type") == "agent":
        require(data.get("collaboration_room_allowed") is False, f"{rel(path)} collaboration_room_allowed must be false")
    return data


def validate_candidate_markdown(path: Path) -> None:
    text = read_text(path).lower()
    require("candidate_only" in text or "candidate-only" in text, f"{rel(path)} must state candidate-only")
    require("untrusted_candidate" in text or "untrusted candidate" in text, f"{rel(path)} must state untrusted candidate")
    for token in [
        "runtime off",
        "autorun off",
        "trusted-memory write off",
        "source/route/queue mutation off",
        "external ai off",
    ]:
        require(token in text, f"{rel(path)} missing safety statement: {token}")


def check_candidate_inventory() -> tuple[int, int]:
    if not CANDIDATE_STORAGE.exists():
        print_result("SKIP", "candidate inventory", "candidate storage directory does not exist")
        return 0, 0
    json_files = sorted(CANDIDATE_STORAGE.glob("*.json"))
    md_files = sorted(CANDIDATE_STORAGE.glob("*.md"))
    for path in json_files:
        data = validate_candidate_json(path)
        if data.get("candidate_id") == "verifier_health_check":
            print_result("INFO", "candidate inventory", "verifier_health_check is still candidate-only; not approved or moved")
    for path in md_files:
        validate_candidate_markdown(path)
    require(not list(CANDIDATE_STORAGE.glob("*.py")), "candidate storage must not contain Python files")
    print_result("PASS", "candidate inventory checks", f"json={len(json_files)} md={len(md_files)}")
    return len(json_files), len(md_files)


def should_skip_dir(dirname: str) -> bool:
    return dirname.lower() in EXCLUDE_DIRS


def is_verifier_only(path: Path) -> bool:
    try:
        relative = path.relative_to(ROOT)
    except ValueError:
        return False
    parts = relative.parts
    return bool(parts) and parts[0] == "tools" and path.name.startswith("verify_")


def scan_active_source() -> tuple[int, int, int]:
    scanned = 0
    verifier_references = 0
    findings: list[str] = []
    review_required: list[str] = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        current = Path(dirpath)
        dirnames[:] = [dirname for dirname in dirnames if not should_skip_dir(dirname)]
        for filename in filenames:
            path = current / filename
            if path == SELF:
                continue
            suffix = path.suffix.lower()
            if suffix in BINARY_SUFFIXES or suffix not in ACTIVE_SOURCE_SUFFIXES:
                continue
            scanned += 1
            text = read_text(path)
            hits = [name for name, pattern in ACTIVE_SOURCE_PATTERNS if pattern.search(text)]
            if not hits:
                continue
            if is_verifier_only(path):
                verifier_references += len(hits)
                print_result("INFO", "verifier-only active-source reference", f"{rel(path)} hits={','.join(hits)}")
                continue
            review_required.append(f"{rel(path)} hits={','.join(hits)}")
    for item in review_required:
        print_result("REVIEW_REQUIRED", "active source finding", item)
    if review_required:
        findings.extend(review_required)
    require(not findings, "active source scan found approved-inactive/runtime patterns requiring review")
    print_result("INFO", "active source files scanned", str(scanned))
    print_result("INFO", "safe verifier references", str(verifier_references))
    print_result("PASS", "active source scan result", "failures=0 review_required=0")
    return scanned, verifier_references, len(findings)


def main() -> int:
    print("ENGEL_AGENT_SKILL_APPROVED_INACTIVE_REGISTRY_VERIFIER")
    print(f"ROOT {ROOT}")
    print("Mode: local static verification only; no approval, registry entry, runtime, provider, model, or trusted-memory behavior")
    try:
        require_files()
        data = load_json(CONTRACT_JSON)
        print_result("PASS", "contract JSON parse", rel(CONTRACT_JSON))
        check_contract_values(data)
        check_lifecycle_states(data)
        check_future_registry_location(data)
        check_entry_schema(data)
        check_promotion_rules(data)
        check_not_meaning(data)
        check_candidate_inventory()
        scan_active_source()
    except CheckFailure as exc:
        print_result("FAIL", "approved inactive registry verification", str(exc))
        return 1
    except json.JSONDecodeError as exc:
        print_result("FAIL", "JSON parse", str(exc))
        return 1
    except Exception as exc:
        print_result("FAIL", "unexpected verifier error", f"{type(exc).__name__}: {exc}")
        return 1

    print("PASS contract checks")
    print("PASS lifecycle state checks")
    print("PASS future registry location checks")
    print("PASS inactive registry schema checks")
    print("PASS promotion rule checks")
    print("PASS approved-inactive boundary checks")
    print("PASS candidate inventory result")
    print("PASS active source scan result")
    print("AGENT_SKILL_APPROVED_INACTIVE_REGISTRY_VERIFICATION_PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
