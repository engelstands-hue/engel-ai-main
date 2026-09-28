#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import py_compile
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()

CONTRACT_JSON = ROOT / "memory" / "ENGEL_AGENT_SKILL_APPROVE_INACTIVE_FLOW_COMMAND_CONTRACT_V1.json"
CONTRACT_MD = ROOT / "memory" / "ENGEL_AGENT_SKILL_APPROVE_INACTIVE_FLOW_COMMAND_CONTRACT_V1.md"
CONTRACT_REPORT = (
    ROOT
    / "reports"
    / "codex_bridge"
    / "ENGEL_AGENT_SKILL_APPROVE_INACTIVE_FLOW_COMMAND_CONTRACT_V1.md"
)

APP = ROOT / "engel_app.py"
COMMANDS_DOC = ROOT / "memory" / "ENGEL_COMMANDS.md"
ROUTE_MATRIX = ROOT / "memory" / "ROUTE_VERIFICATION_SET_V1.json"
CANDIDATE_STORAGE = ROOT / "reports" / "agent_skill_candidates"
REGISTRY_JSON = ROOT / "memory" / "ENGEL_AGENT_SKILL_APPROVED_INACTIVE_REGISTRY_V1.json"
REGISTRY_MD = ROOT / "memory" / "ENGEL_AGENT_SKILL_APPROVED_INACTIVE_REGISTRY_V1.md"
REAL_RECEIPT = ROOT / "reports" / "codex_bridge" / "ENGEL_AGENT_SKILL_APPROVED_INACTIVE_verifier_health_check.md"

APPROVAL_PHRASE = "APPROVE_AGENT_SKILL_APPROVED_INACTIVE_ENTRY_V1"
CANONICAL_COMMAND = f"engel ai approve inactive {APPROVAL_PHRASE} id=<candidate_id>"
REAL_COMMAND = f"engel ai approve inactive {APPROVAL_PHRASE} id=verifier_health_check"

REQUIRED_FILES = [CONTRACT_JSON, CONTRACT_MD, CONTRACT_REPORT, APP, COMMANDS_DOC, ROUTE_MATRIX]

REQUIRED_VALUES = {
    "contract_id": "ENGEL_AGENT_SKILL_APPROVE_INACTIVE_FLOW_COMMAND_CONTRACT_V1",
    "status": "contract_only",
    "active_workspace": r"D:\b.WorkSpace\Engel App",
    "command_enabled_now": False,
    "no_candidate_approved_now": True,
    "no_inactive_registry_entry_created_now": True,
    "runtime_enabled_now": False,
    "autorun_enabled_now": False,
    "external_ai_access_enabled_now": False,
    "approval_phrase": APPROVAL_PHRASE,
}

REQUIRED_KEYS = [
    "command_surface",
    "approval_phrase_meaning",
    "command_behavior",
    "command_input_schema",
    "command_output_schema",
    "registry_write_behavior",
    "approval_receipt_behavior",
    "forbidden_inputs",
    "future_verifier",
    "allowed_future_implementation_files",
    "stop_conditions",
    "recommended_next_slice",
    "safety_preserved",
]

FALSE_FIELDS = [
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

FORBIDDEN_INPUTS = [
    "output_path",
    "runtime_enabled=true",
    "autorun_enabled=true",
    "activate=true",
    "run=true",
    "install=true",
    "startup_load_allowed=true",
    "external_ai_access_allowed=true",
    "network_allowed=true",
    "provider_api_allowed=true",
    "trusted_memory_write_allowed=true",
    "source_mutation_allowed=true",
    "route_mutation_allowed=true",
    "queue_mutation_allowed=true",
    "package_install_allowed=true",
    "mobile_runtime_allowed=true",
    "remote_queen_runtime_allowed=true",
]

SUCCESS_OUTPUT_FIELDS = [
    "candidate_id",
    "candidate_type",
    "registry_entry_id",
    "registry_json_path",
    "registry_md_path",
    "approval_receipt_path",
    "status",
    "runtime_enabled",
    "autorun_enabled",
    "activation_contract_required",
    "not_live_statement",
    "not_runnable_statement",
    "next_required_slice",
]

BLOCKER_OUTPUT_FIELDS = [
    "blocker_type",
    "blocker_reason",
    "no_files_created",
    "recommended_next_action",
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
    "not_live",
    "not_runnable",
    "not_scheduled",
    "no_trusted_memory_write",
    "no_source_route_queue_mutation",
    "no_external_ai_provider_network_local_llm_access",
]

DEPENDENT_VERIFIERS = [
    ("approved inactive registry verifier", ROOT / "tools" / "verify_agent_skill_approved_inactive_registry.py", "AGENT_SKILL_APPROVED_INACTIVE_REGISTRY_VERIFICATION_PASS"),
    ("approve inactive flow verifier", ROOT / "tools" / "verify_agent_skill_approve_inactive_flow.py", "AGENT_SKILL_APPROVE_INACTIVE_FLOW_VERIFICATION_PASS"),
    ("candidate scaffold verifier", ROOT / "tools" / "verify_agent_skill_candidate_scaffold.py", "AGENT_SKILL_CANDIDATE_SCAFFOLD_VERIFICATION_PASS"),
    ("candidate pipeline verifier", ROOT / "tools" / "verify_agent_skill_candidate_pipeline.py", "AGENT_SKILL_CANDIDATE_PIPELINE_VERIFICATION_PASS"),
    ("route metadata verifier", ROOT / "tools" / "verify_route_metadata_contract.py", "ROUTE_METADATA_CONTRACT_VERIFICATION_PASS"),
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
    "memory",
}

ACTIVE_SOURCE_PATTERNS = [
    ("forbidden_approve_candidate_name", re.compile(r"\bapprove_inactive_candidate\b", re.I)),
    ("forbidden_move_candidate_name", re.compile(r"\bmove_candidate_to_inactive_registry\b", re.I)),
    ("forbidden_create_entry_name", re.compile(r"\bcreate_approved_inactive_entry\b", re.I)),
    ("activate_agent_call", re.compile(r"\bactivate_agent\s*\(", re.I)),
    ("activate_skill_call", re.compile(r"\bactivate_skill\s*\(", re.I)),
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
    ("queue_mutation_allowed_true", re.compile(r"\bqueue_mutation_allowed\s*[:=]\s*(?:True|true|\$true)\b")),
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


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def load_json(path: Path) -> Any:
    return json.loads(read_text(path))


def print_result(status: str, label: str, detail: str = "") -> None:
    suffix = f" {detail}" if detail else ""
    print(f"{status} {label}{suffix}")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def snapshot(paths: list[Path]) -> dict[str, str | None]:
    state: dict[str, str | None] = {}
    for path in paths:
        state[rel(path)] = sha256_file(path) if path.exists() else None
    return state


def compile_sources() -> None:
    for path in [APP, SELF]:
        py_compile.compile(str(path), doraise=True)
        print_result("PASS", "py_compile", rel(path))


def import_engel_app() -> Any:
    root_text = str(ROOT)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)
    spec = importlib.util.spec_from_file_location("engel_app", APP)
    require(spec is not None and spec.loader is not None, "could not load engel_app spec")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    print_result("PASS", "engel_app import", "main guarded; no GUI launched")
    return module


def verify_required_files() -> None:
    missing = [rel(path) for path in REQUIRED_FILES if not path.exists()]
    require(not missing, "missing required files: " + ", ".join(missing))
    print_result("PASS", "required files", str(len(REQUIRED_FILES)))


def verify_contract(contract: dict[str, Any]) -> None:
    for key, expected in REQUIRED_VALUES.items():
        require(contract.get(key) == expected, f"contract {key} expected {expected!r} got {contract.get(key)!r}")
    missing = [key for key in REQUIRED_KEYS if key not in contract]
    require(not missing, "contract missing required keys: " + ", ".join(missing))

    surface = contract.get("command_surface")
    require(isinstance(surface, dict), "command_surface must be an object")
    require((surface.get("canonical_command") or surface.get("canonical")) == CANONICAL_COMMAND, "canonical command mismatch")
    help_forms = surface.get("help_or_discovery_forms") or surface.get("help_forms")
    require(isinstance(help_forms, list), "help_or_discovery_forms must be a list")
    for form in ["engel ai approve inactive", "engel ai approve inactive help", "engel ai approve inactive examples"]:
        require(form in help_forms, "missing help form: " + form)
    if "discovery_forms_create_files" in surface:
        require(surface.get("discovery_forms_create_files") is False, "discovery forms must not create files")
    require(surface.get("one_surface_only") is True, "command surface must be one surface only")

    meaning = contract.get("approval_phrase_meaning")
    require(isinstance(meaning, dict), "approval_phrase_meaning must be an object")
    authorized = " ".join(str(item).lower() for item in meaning.get("authorizes_only", []))
    for term in ["registry", "receipt"]:
        require(term in authorized, "approval phrase authorized scope missing: " + term)
    not_authorized = " ".join(str(item).lower() for item in meaning.get("does_not_authorize", []))
    for term in ["runtime", "autorun", "install", "execution", "external ai", "web/network/provider", "trusted-memory writes", "source mutation", "route mutation", "queue mutation", "package install", "mobile runtime", "remote queen runtime"]:
        require(term in not_authorized, "approval phrase forbidden scope missing: " + term)

    behavior = contract.get("command_behavior")
    require(isinstance(behavior, dict), "command_behavior must be an object")
    for key in [
        "help_or_no_args",
        "missing_approval_phrase",
        "invalid_candidate_id",
        "missing_human_review_report",
        "candidate_dangerous_flags_true",
    ]:
        item = behavior.get(key)
        require(isinstance(item, dict), f"command_behavior {key} must be an object")
        require(item.get("creates_files") is False, f"command_behavior {key}.creates_files must be false")
    success = behavior.get("success_behavior") or behavior.get("correct_approval_and_all_gates_pass")
    require(isinstance(success, dict), "success_behavior must be an object")
    for key in ["runtime_enabled", "autorun_enabled", "startup_load_allowed", "auto_discovery_execution_allowed"]:
        require(success.get(key) is False, "success behavior must keep false: " + key)
    require(success.get("activation_contract_required") is True, "success behavior must keep activation contract required")
    if success.get("still_not_live_not_installed_not_runnable") is True:
        pass
    else:
        for key in ["states_not_live", "states_not_installed", "states_not_runnable"]:
            require(success.get(key) is True, "success behavior missing " + key)

    input_schema = contract.get("command_input_schema")
    require(isinstance(input_schema, dict), "command_input_schema must be an object")
    required = input_schema.get("required_fields") or input_schema.get("required")
    require(isinstance(required, list), "required input fields must be a list")
    for field in ["approval_phrase", "candidate_id"]:
        require(field in required, "required input field missing: " + field)
    forbidden = contract.get("forbidden_inputs")
    require(isinstance(forbidden, list), "forbidden_inputs must be a list")
    missing_forbidden = [item for item in FORBIDDEN_INPUTS if item not in forbidden]
    require(not missing_forbidden, "forbidden inputs missing: " + ", ".join(missing_forbidden))

    output = contract.get("command_output_schema")
    require(isinstance(output, dict), "command_output_schema must be an object")
    success_fields = output.get("success_output_required_fields")
    blocker_fields = output.get("blocker_output_required_fields")
    require(isinstance(success_fields, list), "success fields must be a list")
    require(isinstance(blocker_fields, list), "blocker fields must be a list")
    require(not [field for field in SUCCESS_OUTPUT_FIELDS if field not in success_fields], "success output fields incomplete")
    require(not [field for field in BLOCKER_OUTPUT_FIELDS if field not in blocker_fields], "blocker output fields incomplete")

    registry = contract.get("registry_write_behavior")
    require(isinstance(registry, dict), "registry_write_behavior must be an object")
    require(registry.get("may_create_json") == "memory\\ENGEL_AGENT_SKILL_APPROVED_INACTIVE_REGISTRY_V1.json", "registry JSON path mismatch")
    require(registry.get("may_create_markdown") == "memory\\ENGEL_AGENT_SKILL_APPROVED_INACTIVE_REGISTRY_V1.md", "registry Markdown path mismatch")
    for key in [
        "if_registry_exists_load_and_validate_first",
        "append_only_if_candidate_id_not_present",
        "revoked_or_blocked_entry_requires_separate_correction_flow",
    ]:
        require(registry.get(key) is True, "registry behavior must require " + key)
    for key in ["duplicate_entries_allowed", "delete_existing_entries_allowed"]:
        require(registry.get(key) is False, "registry behavior must disallow " + key)

    receipt = contract.get("approval_receipt_behavior")
    require(isinstance(receipt, dict), "approval_receipt_behavior must be an object")
    require(receipt.get("path_template") == "reports\\codex_bridge\\ENGEL_AGENT_SKILL_APPROVED_INACTIVE_<candidate_id>.md", "receipt path mismatch")
    receipt_fields = receipt.get("required_fields")
    require(isinstance(receipt_fields, list), "receipt fields must be a list")
    missing_receipt = [field for field in RECEIPT_FIELDS if field not in receipt_fields]
    require(not missing_receipt, "approval receipt fields missing: " + ", ".join(missing_receipt))
    print_result("PASS", "contract checks", "command contract remains disabled-by-contract but implementation-bound")


def command_segment() -> str:
    source = read_text(APP)
    start = source.find("AGENT_SKILL_APPROVED_INACTIVE_APPROVAL_PHRASE_V1")
    end = source.find("def operator_manual_v2_summary", start)
    require(start >= 0 and end > start, "approved inactive command source segment not found")
    return source[start:end]


def verify_static_source() -> None:
    source = read_text(APP)
    segment = command_segment()
    for needle in [
        "agent_skill_approved_inactive_flow_command_v1",
        "engel ai approve inactive",
        APPROVAL_PHRASE,
        "ENGEL_AGENT_SKILL_APPROVED_INACTIVE_REGISTRY_V1.json",
        "ENGEL_AGENT_SKILL_APPROVED_INACTIVE_REGISTRY_V1.md",
        "ENGEL_AGENT_SKILL_APPROVED_INACTIVE_",
        "Human review report required before approved inactive entry",
        "Candidate files not found in approved candidate storage",
        "approved inactive is not live",
        "approved inactive is not runnable",
    ]:
        require(needle in source, f"engel_app missing command marker: {needle}")
    require("approved_inactive_reply = agent_skill_approved_inactive_flow_command_v1(msg)" in source, "human command dispatcher does not call approved inactive command")
    require(source.count("engel ai approve inactive") >= 4, "approved inactive route/help markers missing")
    for alias in [
        "\"approve inactive candidate\"",
        "\"create approved inactive\"",
        "\"move candidate to inactive\"",
    ]:
        require(alias not in segment, "unexpected alias route present: " + alias)
    for forbidden in [
        "create_live_agent(",
        "enable_live_agent(",
        "start_live_agent(",
        "create_live_skill(",
        "enable_live_skill(",
        "install_live_skill(",
        "auto_register_agent(",
        "auto_register_skill(",
        "self_activate_agent(",
        "self_activate_skill(",
        "os.system(",
        "shell=True",
        "requests.",
        "socket.",
    ]:
        require(forbidden not in segment, "command segment contains forbidden behavior: " + forbidden)
    for field in FALSE_FIELDS:
        pattern = re.compile(rf"['\"]?{re.escape(field)}['\"]?\s*[:=]\s*(?:True|true|\$true)\b")
        require(not pattern.search(segment), f"command segment sets {field} true")
    print_result("PASS", "command source markers", "route exists and is wired")
    print_result("PASS", "command static safety", "no live/runtime/provider/source mutation patterns in command segment")


def assert_blocked(output: str, label: str) -> None:
    lower = output.lower()
    require("blocked" in lower, label + " must be blocked")
    require("no_files_created: true" in lower or "files created: none" in lower, label + " must create no files")
    require("runtime enabled: no" in lower, label + " must keep runtime disabled")
    require("autorun enabled: no" in lower, label + " must keep autorun disabled")
    require("trusted-memory write: no" in lower, label + " must keep trusted-memory write disabled")


def assert_help(output: str, label: str) -> None:
    lower = output.lower()
    require("agent/skill approved inactive help" in lower, label + " must show approved inactive help")
    require("engel ai approve inactive approve_agent_skill_approved_inactive_entry_v1 id=<candidate_id>" in lower, label + " must show canonical command")
    require("files created: none" in lower, label + " must create no files")
    require("not live" in lower, label + " must state not live")
    require("not installed" in lower, label + " must state not installed")
    require("not runnable" in lower, label + " must state not runnable")
    require("runtime off" in lower, label + " must state runtime OFF")
    require("autorun off" in lower, label + " must state autorun OFF")
    require("activation contract still required" in lower, label + " must state activation contract required")


def write_temp_candidate(temp_storage: Path, candidate_id: str, dangerous: dict[str, Any] | None = None) -> None:
    candidate = {
        "candidate_id": candidate_id,
        "candidate_type": "agent",
        "name": "Approved Inactive Command Selftest Agent",
        "purpose": "Verifier-only temporary approved inactive command test.",
        "description": "Verifier-only temporary approved inactive command test.",
        "owner": "Engel verifier",
        "created_by": "verify_agent_skill_approve_inactive_flow_command.py",
        "created_at": "2026-05-22T00:00:00Z",
        "status": "candidate_only",
        "trust_status": "untrusted_candidate",
        "allowed_inputs": ["local verifier command names"],
        "allowed_outputs": ["report-only receipts"],
        "allowed_context": [],
        "forbidden_context": ["trusted memory", "providers", "network"],
        "allowed_actions": ["report-only verifier summary planning"],
        "forbidden_actions": ["runtime", "autorun", "source mutation"],
        "allowed_files": ["reports"],
        "forbidden_files": ["memory trusted files", "routes", "queues"],
        "required_verifiers": ["verify_agent_skill_candidate_scaffold.py"],
        "required_human_review": True,
        "external_ai_lanes_requested": [],
        "collaboration_room_allowed": False,
        "approval_required_for_inactive_registry": True,
        "activation_contract_required": True,
        "receipt_required": True,
    }
    for field in FALSE_FIELDS:
        candidate[field] = False
    if dangerous:
        candidate.update(dangerous)
    temp_storage.mkdir(parents=True, exist_ok=True)
    (temp_storage / f"{candidate_id}.agent.json").write_text(json.dumps(candidate, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (temp_storage / f"{candidate_id}.agent.md").write_text(
        "# Approved Inactive Command Selftest Agent\n\n"
        "Status: candidate_only\n\n"
        "Trust status: untrusted_candidate\n\n"
        "This temporary verifier candidate is not live, not installed, not runnable, runtime OFF, autorun OFF, trusted-memory write OFF, source/route/queue mutation OFF, external AI OFF.\n",
        encoding="utf-8",
    )


def write_temp_review(temp_reviews: Path, candidate_id: str) -> None:
    temp_reviews.mkdir(parents=True, exist_ok=True)
    body = {
        "contract_id": "TEMP_HUMAN_REVIEW_SELFTEST",
        "status": "review_only",
        "active_workspace": str(ROOT),
        "candidate_id": candidate_id,
        "candidate_type": "agent",
        "approval_ready_now": False,
        "activation_ready_now": False,
        "safety_preserved": True,
    }
    (temp_reviews / "ENGEL_AGENT_SKILL_TEMP_HUMAN_REVIEW_V1.json").write_text(json.dumps(body, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (temp_reviews / "ENGEL_AGENT_SKILL_TEMP_HUMAN_REVIEW_V1.md").write_text(
        "# TEMP HUMAN REVIEW SELFTEST\n\nReview-only temporary file for approved inactive command verifier.\n",
        encoding="utf-8",
    )


def validate_temp_registry(temp_registry_json: Path, temp_registry_md: Path, temp_receipt: Path, candidate_id: str) -> None:
    require(temp_registry_json.exists(), "temp success did not create registry JSON")
    require(temp_registry_md.exists(), "temp success did not create registry Markdown")
    require(temp_receipt.exists(), "temp success did not create receipt")
    registry = load_json(temp_registry_json)
    require(registry.get("registry_id") == "ENGEL_AGENT_SKILL_APPROVED_INACTIVE_REGISTRY_V1", "registry id mismatch")
    require(registry.get("status") == "approved_inactive_registry", "registry status mismatch")
    for field in ["runtime_enabled", "autorun_enabled", "startup_load_allowed", "auto_discovery_execution_allowed"]:
        require(registry.get(field) is False, "registry top-level must keep false: " + field)
    entries = registry.get("entries")
    require(isinstance(entries, list) and len(entries) == 1, "temp registry must contain exactly one entry")
    entry = entries[0]
    require(entry.get("candidate_id") == candidate_id, "temp entry candidate_id mismatch")
    require(entry.get("status") == "approved_inactive", "temp entry status mismatch")
    require(entry.get("trust_status") == "reviewed_but_inactive", "temp entry trust status mismatch")
    require(entry.get("activation_contract_required") is True, "temp entry activation contract required")
    for field in FALSE_FIELDS:
        require(entry.get(field) is False, "temp entry must keep false: " + field)
    receipt_text = read_text(temp_receipt).lower()
    for token in [
        "candidate_id",
        "candidate_type",
        "source candidate json",
        "source candidate md",
        "human review report path",
        "verifier results",
        "registry entry id",
        "registry path",
        "approved inactive timestamp",
        "safety flags",
        "activation_contract_required",
        "not live",
        "not runnable",
        "not scheduled",
        "no trusted-memory write",
        "no source/route/queue mutation",
        "no external ai/provider/network/local llm access",
    ]:
        require(token in receipt_text, "temp receipt missing: " + token)


def run_command_behavior_checks(app: Any) -> None:
    actual_paths = [REGISTRY_JSON, REGISTRY_MD, REAL_RECEIPT]
    before = snapshot(actual_paths)
    storage_before = sorted(rel(path) for path in CANDIDATE_STORAGE.glob("*")) if CANDIDATE_STORAGE.exists() else []

    for command in ["engel ai approve inactive", "engel ai approve inactive help", "engel ai approve inactive examples"]:
        assert_help(app.agent_skill_approved_inactive_flow_command_v1(command), command)

    missing_approval = app.agent_skill_approved_inactive_flow_command_v1("engel ai approve inactive id=verifier_health_check")
    assert_blocked(missing_approval, "missing approval")
    require(APPROVAL_PHRASE in missing_approval, "missing approval response must include approval phrase")
    require(REAL_COMMAND in missing_approval, "missing approval response must show corrected command")

    invalid_id = app.agent_skill_approved_inactive_flow_command_v1(f"engel ai approve inactive {APPROVAL_PHRASE} id=..\\bad")
    assert_blocked(invalid_id, "invalid candidate id")
    require("candidate_id must" in invalid_id, "invalid id response should explain candidate_id rules")

    dangerous_input = app.agent_skill_approved_inactive_flow_command_v1(
        f"engel ai approve inactive {APPROVAL_PHRASE} id=verifier_health_check runtime_enabled=true"
    )
    assert_blocked(dangerous_input, "dangerous true input")
    require("runtime_enabled" in dangerous_input, "dangerous input response must mention runtime_enabled")

    reports_root = ROOT / "reports"
    with tempfile.TemporaryDirectory(prefix="approve_inactive_command_selftest_", dir=str(reports_root)) as temp_name:
        temp_root = Path(temp_name)
        temp_storage = temp_root / "agent_skill_candidates"
        temp_reviews = temp_root / "codex_bridge_reviews"
        temp_receipts = temp_root / "codex_bridge_receipts"
        temp_registry_json = temp_root / "memory" / "ENGEL_AGENT_SKILL_APPROVED_INACTIVE_REGISTRY_V1.json"
        temp_registry_md = temp_root / "memory" / "ENGEL_AGENT_SKILL_APPROVED_INACTIVE_REGISTRY_V1.md"

        missing_candidate = app.agent_skill_approved_inactive_flow_command_v1(
            f"engel ai approve inactive {APPROVAL_PHRASE} id=missing_selftest_candidate",
            candidate_storage_root=temp_storage,
            review_report_root=temp_reviews,
            registry_json_path=temp_registry_json,
            registry_md_path=temp_registry_md,
            receipt_root=temp_receipts,
            run_verifiers=False,
        )
        assert_blocked(missing_candidate, "missing candidate")
        require("candidate files not found" in missing_candidate.lower(), "missing candidate response must mention storage")

        write_temp_candidate(temp_storage, "missing_review_selftest")
        missing_review = app.agent_skill_approved_inactive_flow_command_v1(
            f"engel ai approve inactive {APPROVAL_PHRASE} id=missing_review_selftest",
            candidate_storage_root=temp_storage,
            review_report_root=temp_reviews,
            registry_json_path=temp_registry_json,
            registry_md_path=temp_registry_md,
            receipt_root=temp_receipts,
            run_verifiers=False,
        )
        assert_blocked(missing_review, "missing human review")
        require("human review report required" in missing_review.lower(), "missing review response must mention human review")
        require("ENGEL_AGENT_SKILL_FIRST_CANDIDATE_HUMAN_REVIEW_V1" in missing_review, "missing review response must recommend human review slice")

        write_temp_candidate(temp_storage, "dangerous_candidate_selftest", {"runtime_enabled": True})
        write_temp_review(temp_reviews, "dangerous_candidate_selftest")
        dangerous_candidate = app.agent_skill_approved_inactive_flow_command_v1(
            f"engel ai approve inactive {APPROVAL_PHRASE} id=dangerous_candidate_selftest",
            candidate_storage_root=temp_storage,
            review_report_root=temp_reviews,
            registry_json_path=temp_registry_json,
            registry_md_path=temp_registry_md,
            receipt_root=temp_receipts,
            run_verifiers=False,
        )
        assert_blocked(dangerous_candidate, "dangerous candidate flags")
        require("dangerous flags true" in dangerous_candidate.lower(), "dangerous candidate response must list dangerous flags")

        write_temp_candidate(temp_storage, "approved_command_selftest")
        write_temp_review(temp_reviews, "approved_command_selftest")
        success = app.agent_skill_approved_inactive_flow_command_v1(
            f"engel ai approve inactive {APPROVAL_PHRASE} id=approved_command_selftest",
            candidate_storage_root=temp_storage,
            review_report_root=temp_reviews,
            registry_json_path=temp_registry_json,
            registry_md_path=temp_registry_md,
            receipt_root=temp_receipts,
            run_verifiers=False,
            now_utc="2026-05-22T00:00:00Z",
        )
        lower = success.lower()
        require("agent/skill approved inactive created" in lower, "temp success should report created")
        require("status: approved_inactive" in lower, "temp success should state approved_inactive")
        require("runtime_enabled: false" in lower, "temp success should state runtime false")
        require("autorun_enabled: false" in lower, "temp success should state autorun false")
        require("activation_contract_required: true" in lower, "temp success should state activation contract required")
        validate_temp_registry(
            temp_registry_json,
            temp_registry_md,
            temp_receipts / "ENGEL_AGENT_SKILL_APPROVED_INACTIVE_approved_command_selftest.md",
            "approved_command_selftest",
        )
        duplicate = app.agent_skill_approved_inactive_flow_command_v1(
            f"engel ai approve inactive {APPROVAL_PHRASE} id=approved_command_selftest",
            candidate_storage_root=temp_storage,
            review_report_root=temp_reviews,
            registry_json_path=temp_registry_json,
            registry_md_path=temp_registry_md,
            receipt_root=temp_receipts,
            run_verifiers=False,
        )
        require("existing entry" in duplicate.lower(), "duplicate temp command should return existing entry instead of duplicating")
        registry = load_json(temp_registry_json)
        require(len(registry.get("entries", [])) == 1, "duplicate temp command created duplicate entry")

    after = snapshot(actual_paths)
    storage_after = sorted(rel(path) for path in CANDIDATE_STORAGE.glob("*")) if CANDIDATE_STORAGE.exists() else []
    require(before == after, "command verifier modified actual approved inactive registry or receipt")
    require(storage_before == storage_after, "command verifier modified actual candidate storage")
    print_result("PASS", "help/discovery behavior", "no approval needed and no files written")
    print_result("PASS", "blocker behavior", "missing approval, invalid id, missing candidate, missing review, and dangerous flags block")
    print_result("PASS", "temp success behavior", "registry JSON/MD and receipt created only under temp root")
    print_result("PASS", "persistent storage check", "actual candidate/registry files unchanged by verifier self-test")


def verify_docs_and_metadata() -> None:
    commands = read_text(COMMANDS_DOC)
    for needle in [
        "engel ai approve inactive",
        "engel ai approve inactive help",
        APPROVAL_PHRASE,
        "approved inactive",
        "not live",
        "not installed",
        "not runnable",
        "runtime OFF",
        "autorun OFF",
        "activation",
    ]:
        require(needle in commands, "ENGEL_COMMANDS missing: " + needle)

    matrix = load_json(ROUTE_MATRIX)
    entries = matrix.get("route_regression_matrix_entries", [])
    require(isinstance(entries, list), "route_regression_matrix_entries must be a list")
    entry = next((item for item in entries if isinstance(item, dict) and item.get("command") == CANONICAL_COMMAND), None)
    require(isinstance(entry, dict), "route matrix missing approved inactive command")
    require(entry.get("implemented_now") is True, "route matrix must mark command implemented")
    require(entry.get("should_execute_in_test") is False, "route matrix must not execute persistent command broadly")
    require(entry.get("approval_token") == APPROVAL_PHRASE, "route matrix approval token mismatch")
    require(entry.get("content_contract_ref") == "agent_skill_approve_inactive_flow_command_expectations", "route matrix content contract ref mismatch")
    for field in [
        "approved_inactive_only",
        "not_live",
        "not_installed",
        "not_runnable",
        "activation_contract_required",
        "no_live_registration",
        "no_install",
        "no_runtime_enablement",
        "no_autorun_enablement",
        "no_startup_load",
        "no_auto_discovery_execution",
        "no_provider_call",
        "no_network_call",
        "no_local_llm_inference",
        "no_queue_mutation",
        "no_route_mutation",
        "no_source_mutation_from_candidate",
        "no_trusted_memory_write",
    ]:
        require(entry.get(field) is True, "route matrix entry missing true field: " + field)

    expectations = matrix.get("agent_skill_approve_inactive_flow_command_expectations")
    require(isinstance(expectations, dict), "route matrix missing approved inactive expectations")
    require(expectations.get("command_entry_enabled") is True, "expectations command entry must be enabled")
    require(expectations.get("approval_phrase_required") == APPROVAL_PHRASE, "expectations approval phrase mismatch")
    require(expectations.get("registry_json") == "memory\\ENGEL_AGENT_SKILL_APPROVED_INACTIVE_REGISTRY_V1.json", "expectations registry JSON mismatch")
    require(expectations.get("activation_contract_required") is True, "expectations activation contract required")
    for field in [
        "runtime_enabled",
        "autorun_enabled",
        "startup_load_allowed",
        "auto_discovery_execution_allowed",
        "external_ai_access_enabled",
        "provider_network_enabled",
        "local_llm_inference_enabled",
        "trusted_memory_write_enabled",
        "source_mutation_from_candidate_enabled",
        "route_mutation_enabled",
        "queue_mutation_enabled",
        "package_install_enabled",
        "mobile_runtime_enabled",
        "remote_queen_runtime_enabled",
        "persistent_route_regression_execution_allowed",
    ]:
        require(expectations.get(field) is False, "expectations must keep false: " + field)
    print_result("PASS", "command docs alignment", rel(COMMANDS_DOC))
    print_result("PASS", "route metadata alignment", rel(ROUTE_MATRIX))


def should_scan_file(path: Path) -> bool:
    if path == SELF:
        return False
    if path.suffix.lower() not in ACTIVE_SOURCE_SUFFIXES or path.suffix.lower() in BINARY_SUFFIXES:
        return False
    parts = {part.lower() for part in path.relative_to(ROOT).parts} if path != ROOT else set()
    return not bool(parts & EXCLUDE_DIRS)


def verify_active_source_scan() -> None:
    scanned = 0
    findings: list[str] = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [dirname for dirname in dirnames if dirname.lower() not in EXCLUDE_DIRS]
        for filename in filenames:
            path = Path(dirpath) / filename
            if not should_scan_file(path):
                continue
            scanned += 1
            text = read_text(path)
            for label, pattern in ACTIVE_SOURCE_PATTERNS:
                if pattern.search(text):
                    if path.name.startswith("verify_") and path.parent.name == "tools":
                        continue
                    findings.append(f"{rel(path)} hit={label}")
    for item in findings:
        print_result("REVIEW_REQUIRED", "active source finding", item)
    require(not findings, "active source scan found unsafe approve-inactive/runtime patterns")
    print_result("INFO", "active source files scanned", str(scanned))
    print_result("PASS", "active source scan result", "failures=0 review_required=0")


def run_dependent_verifiers() -> None:
    for label, path, marker in DEPENDENT_VERIFIERS:
        if not path.exists():
            print_result("SKIP", label, rel(path) + " missing")
            continue
        result = subprocess.run(
            [sys.executable, str(path)],
            cwd=str(ROOT),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            timeout=240,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        require(result.returncode == 0, label + " failed:\n" + result.stdout)
        require(marker in result.stdout, label + " marker missing")
        print_result("PASS", label)


def main() -> int:
    print("ENGEL_AGENT_SKILL_APPROVE_INACTIVE_FLOW_COMMAND_VERIFIER")
    print(f"ROOT {ROOT}")
    print("Mode: local command-route verification; temp success only; no persistent approval by verifier")
    try:
        compile_sources()
        verify_required_files()
        contract = load_json(CONTRACT_JSON)
        verify_contract(contract)
        verify_static_source()
        app = import_engel_app()
        require(hasattr(app, "agent_skill_approved_inactive_flow_command_v1"), "approved inactive command handler missing")
        run_command_behavior_checks(app)
        verify_docs_and_metadata()
        verify_active_source_scan()
        run_dependent_verifiers()
    except py_compile.PyCompileError as exc:
        print_result("FAIL", "py_compile", str(exc))
        return 1
    except (CheckFailure, json.JSONDecodeError, OSError, subprocess.SubprocessError, SyntaxError) as exc:
        print_result("FAIL", "approve-inactive flow command verifier", str(exc))
        return 1
    except Exception as exc:
        print_result("FAIL", "unexpected verifier error", f"{type(exc).__name__}: {exc}")
        return 1

    print_result("PASS", "contract check result")
    print_result("PASS", "command surface result")
    print_result("PASS", "approval phrase result")
    print_result("PASS", "input/output schema result")
    print_result("PASS", "registry/receipt behavior result")
    print_result("PASS", "candidate inventory result")
    print_result("PASS", "active source scan result")
    print("AGENT_SKILL_APPROVE_INACTIVE_FLOW_COMMAND_VERIFICATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
