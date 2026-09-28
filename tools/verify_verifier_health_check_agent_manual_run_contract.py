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

CONTRACT_JSON = ROOT / "memory" / "ENGEL_VERIFIER_HEALTH_CHECK_AGENT_MANUAL_RUN_CONTRACT_V1.json"
CONTRACT_MD = ROOT / "memory" / "ENGEL_VERIFIER_HEALTH_CHECK_AGENT_MANUAL_RUN_CONTRACT_V1.md"
CONTRACT_REPORT = (
    ROOT
    / "reports"
    / "codex_bridge"
    / "ENGEL_VERIFIER_HEALTH_CHECK_AGENT_MANUAL_RUN_CONTRACT_V1.md"
)

LIFECYCLE_REVIEW_JSON = (
    ROOT
    / "reports"
    / "codex_bridge"
    / "ENGEL_AGENT_SKILL_LIFECYCLE_STABILITY_REVIEW_V1.json"
)
LIFECYCLE_REVIEW_MD = (
    ROOT
    / "reports"
    / "codex_bridge"
    / "ENGEL_AGENT_SKILL_LIFECYCLE_STABILITY_REVIEW_V1.md"
)
CANDIDATE_JSON = ROOT / "reports" / "agent_skill_candidates" / "verifier_health_check.agent.json"
CANDIDATE_MD = ROOT / "reports" / "agent_skill_candidates" / "verifier_health_check.agent.md"
REGISTRY_JSON = ROOT / "memory" / "ENGEL_AGENT_SKILL_APPROVED_INACTIVE_REGISTRY_V1.json"
REGISTRY_MD = ROOT / "memory" / "ENGEL_AGENT_SKILL_APPROVED_INACTIVE_REGISTRY_V1.md"
APPROVAL_RECEIPT = (
    ROOT
    / "reports"
    / "codex_bridge"
    / "ENGEL_AGENT_SKILL_APPROVED_INACTIVE_verifier_health_check.md"
)
ACTIVATION_JSON = ROOT / "memory" / "ENGEL_VERIFIER_HEALTH_CHECK_AGENT_ACTIVATION_CONTRACT_V1.json"
ACTIVATION_MD = ROOT / "memory" / "ENGEL_VERIFIER_HEALTH_CHECK_AGENT_ACTIVATION_CONTRACT_V1.md"
ACTIVATION_REPORT = (
    ROOT
    / "reports"
    / "codex_bridge"
    / "ENGEL_VERIFIER_HEALTH_CHECK_AGENT_ACTIVATION_CONTRACT_V1.md"
)

REQUIRED_VALUES = {
    "contract_id": "ENGEL_VERIFIER_HEALTH_CHECK_AGENT_MANUAL_RUN_CONTRACT_V1",
    "status": "contract_only",
    "active_workspace": r"D:\b.WorkSpace\Engel App",
    "agent_id": "verifier_health_check",
    "manual_run_enabled_now": False,
    "runtime_enabled_now": False,
    "autorun_enabled_now": False,
    "scheduled_run_enabled_now": False,
    "background_execution_enabled_now": False,
    "external_ai_access_enabled_now": False,
    "provider_api_enabled_now": False,
    "network_enabled_now": False,
    "local_llm_inference_enabled_now": False,
    "trusted_memory_write_enabled_now": False,
    "source_mutation_enabled_now": False,
    "route_mutation_enabled_now": False,
    "queue_mutation_enabled_now": False,
    "package_install_enabled_now": False,
    "mobile_runtime_enabled_now": False,
    "remote_queen_runtime_enabled_now": False,
}

REQUIRED_KEYS = [
    "precondition_status",
    "manual_run_states",
    "future_command_concept",
    "verifier_command_allowlist",
    "runtime_limits",
    "receipt_model",
    "forbidden_behavior",
    "future_verifier",
    "stop_conditions",
    "recommended_next_slice",
    "safety_preserved",
]

MANUAL_RUN_STATES = {
    "manual_run_contract_defined",
    "manual_run_verifier_pending",
    "manual_run_command_pending",
    "manual_run_enabled_future",
    "manual_run_blocked",
    "disabled",
}

EXPECTED_REQUIRED_COMMANDS = {
    r"python .\tools\verify_agent_skill_candidate_pipeline.py",
    r"python .\tools\verify_agent_skill_candidate_scaffold.py",
    r"python .\tools\verify_agent_skill_candidate_scaffold_command.py",
    r"python .\tools\verify_agent_skill_approved_inactive_registry.py",
    r"python .\tools\verify_agent_skill_approve_inactive_flow.py",
    r"python .\tools\verify_agent_skill_approve_inactive_flow_command.py",
    r"python .\tools\verify_external_ai_agent_access_contract.py",
    r"python .\tools\verify_verifier_health_check_agent_activation_contract.py",
    r"python .\tools\verify_verifier_health_check_agent_manual_run_contract.py",
    r"python .\tools\verify_verifier_health_check_agent_manual_run_command_contract.py",
    r"python .\tools\verify_untrusted_content_policy.py",
    r"python .\tools\verify_de_bruijn_import_boundaries.py",
    r"python .\tools\verify_route_metadata_contract.py",
    r"python .\tools\verify_authority_hierarchy.py",
    r"python .\tools\verify_prompt_injection_guard.py",
    r"python .\tools\verify_engel_core_continuity_map.py",
}

EXPECTED_OPTIONAL_COMMANDS = {
    r"python .\tools\verify_debruijn_quantum_candidate_proposals.py",
    r"python .\tools\verify_debruijn_quantum_entanglement_groups.py",
    r"python .\tools\verify_debruijn_quantum_backend_status_consistency.py",
    r"python .\tools\verify_engel_debruijn_quantum_automation_file_structure.py",
    r"powershell -ExecutionPolicy Bypass -File .\scripts\codex_verify.ps1",
}

RECEIPT_FIELDS = {
    "receipt_id",
    "agent_id",
    "registry_entry_id",
    "run_mode",
    "started_at",
    "ended_at",
    "commands_requested",
    "commands_run",
    "commands_skipped",
    "exit_codes",
    "verifier_results",
    "timeout_status",
    "output_truncation_status",
    "files_changed_by_agent",
    "forbidden_actions_not_performed",
    "final_status",
    "human_review_required",
    "process_cleanup_result",
}

REQUIRED_RECEIPT_CONFIRMATIONS = [
    "no_source_files_edited",
    "no_routes_mutated",
    "no_queues_mutated",
    "no_trusted_memory_written",
    "no_memory_promoted",
    "no_external_ai_provider_network_called",
    "no_local_llm_inference_run",
    "no_packages_installed",
    "no_build_promote_stage_commit",
    "no_mobile_or_remote_queen_runtime_started",
    "no_background_worker_scheduler_or_startup_hook_created",
]

FORBIDDEN_TERMS = [
    "arbitrary shell command",
    "arbitrary Python module execution",
    "discovered script execution",
    "package install",
    "provider network model call",
    "local LLM inference",
    "source patching",
    "trusted-memory write",
    "memory promotion",
    "route update",
    "queue update",
    "candidate promotion",
    "registry mutation except receipt reference if separately approved",
    "automatic fix application",
    "generated proposal application",
    "commit stage build promote",
    "agent activation",
    "agent creation",
    "skill creation",
    "self-scheduling",
    "self-autorun",
    "background loop",
    "startup hook",
    "Remote Queen runtime",
    "Mobile runtime",
]

ACTIVE_SOURCE_SUFFIXES = {".py", ".ps1", ".bat", ".cmd", ".sh", ".psm1", ".spec", ".json"}
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
CONFIG_FILES_TO_SCAN = [
    ROOT / "memory" / "ROUTE_VERIFICATION_SET_V1.json",
    ROOT / "memory" / "ENGEL_COMMANDS.md",
]

ACTIVE_PATTERNS = [
    ("future_command", re.compile(r"engel ai agent run verifier_health_check", re.I)),
    ("run_agent_function", re.compile(r"\brun_verifier_health_check_agent\b", re.I)),
    ("manual_run_function", re.compile(r"\bverifier_health_check_manual_run\b", re.I)),
    ("manual_run_enabled_now_true", re.compile(r"\bmanual_run_enabled_now\s*[:=]\s*(?:True|true|\$true)\b")),
    ("runtime_enabled_now_true", re.compile(r"\bruntime_enabled_now\s*[:=]\s*(?:True|true|\$true)\b")),
    ("autorun_enabled_now_true", re.compile(r"\bautorun_enabled_now\s*[:=]\s*(?:True|true|\$true)\b")),
    ("scheduled_run_enabled_now_true", re.compile(r"\bscheduled_run_enabled_now\s*[:=]\s*(?:True|true|\$true)\b")),
    (
        "background_execution_enabled_now_true",
        re.compile(r"\bbackground_execution_enabled_now\s*[:=]\s*(?:True|true|\$true)\b"),
    ),
    ("run_allowlisted_verifiers_as_agent", re.compile(r"\brun_allowlisted_verifiers_as_agent\b", re.I)),
    ("runtime_receipts", re.compile(r"\bagent_skill_runtime_receipts\b", re.I)),
    ("subprocess_verifier_health_check", re.compile(r"\bsubprocess\b.*\bverifier_health_check\b", re.I)),
    ("scheduler", re.compile(r"\bscheduler\b", re.I)),
    ("startup_hook", re.compile(r"\bstartup_hook\b", re.I)),
    ("start_worker", re.compile(r"\bstart_worker\b", re.I)),
    (
        "trusted_memory_write_enabled_now_true",
        re.compile(r"\btrusted_memory_write_enabled_now\s*[:=]\s*(?:True|true|\$true)\b"),
    ),
    ("source_mutation_enabled_now_true", re.compile(r"\bsource_mutation_enabled_now\s*[:=]\s*(?:True|true|\$true)\b")),
    ("route_mutation_enabled_now_true", re.compile(r"\broute_mutation_enabled_now\s*[:=]\s*(?:True|true|\$true)\b")),
    ("queue_mutation_enabled_now_true", re.compile(r"\bqueue_mutation_enabled_now\s*[:=]\s*(?:True|true|\$true)\b")),
    (
        "external_ai_access_enabled_now_true",
        re.compile(r"\bexternal_ai_access_enabled_now\s*[:=]\s*(?:True|true|\$true)\b"),
    ),
    ("provider_api_enabled_now_true", re.compile(r"\bprovider_api_enabled_now\s*[:=]\s*(?:True|true|\$true)\b")),
    ("network_enabled_now_true", re.compile(r"\bnetwork_enabled_now\s*[:=]\s*(?:True|true|\$true)\b")),
    (
        "local_llm_inference_enabled_now_true",
        re.compile(r"\blocal_llm_inference_enabled_now\s*[:=]\s*(?:True|true|\$true)\b"),
    ),
    ("mobile_runtime_enabled_now_true", re.compile(r"\bmobile_runtime_enabled_now\s*[:=]\s*(?:True|true|\$true)\b")),
    (
        "remote_queen_runtime_enabled_now_true",
        re.compile(r"\bremote_queen_runtime_enabled_now\s*[:=]\s*(?:True|true|\$true)\b"),
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


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def load_json(path: Path) -> Any:
    return json.loads(read_text(path))


def norm(value: Any) -> str:
    return " ".join(str(value).lower().replace("\\", "/").replace("_", " ").replace("-", " ").split())


def require_files(paths: list[Path], label: str) -> None:
    missing = [rel(path) for path in paths if not path.exists()]
    require(not missing, f"{label} missing: " + ", ".join(missing))
    print_result("PASS", label, f"count={len(paths)}")


def verify_required_files() -> None:
    require_files([CONTRACT_JSON, CONTRACT_MD, CONTRACT_REPORT], "required manual-run contract files present")
    require_files(
        [
            LIFECYCLE_REVIEW_MD,
            LIFECYCLE_REVIEW_JSON,
            CANDIDATE_JSON,
            CANDIDATE_MD,
            REGISTRY_JSON,
            REGISTRY_MD,
            APPROVAL_RECEIPT,
            ACTIVATION_JSON,
            ACTIVATION_MD,
            ACTIVATION_REPORT,
        ],
        "supporting lifecycle files present",
    )


def verify_contract_values(contract: dict[str, Any]) -> None:
    for key, expected in REQUIRED_VALUES.items():
        actual = contract.get(key)
        require(actual == expected, f"{key} expected {expected!r}, got {actual!r}")
    missing = [key for key in REQUIRED_KEYS if key not in contract]
    require(not missing, "missing required keys: " + ", ".join(missing))
    print_result("PASS", "contract checks", f"values={len(REQUIRED_VALUES)} keys={len(REQUIRED_KEYS)}")


def verify_preconditions(contract: dict[str, Any]) -> None:
    preconditions = contract.get("precondition_status")
    require(isinstance(preconditions, dict), "precondition_status must be an object")
    status = preconditions.get("status")
    require(status in {"ready_for_manual_run_contract_only", "blocked_until_preconditions_met"}, f"unexpected precondition status {status!r}")

    candidate = load_json(CANDIDATE_JSON)
    require(candidate.get("candidate_id") == "verifier_health_check", "candidate id mismatch")
    require(candidate.get("status") == "candidate_only", "candidate status must remain candidate_only")
    require(candidate.get("trust_status") == "untrusted_candidate", "candidate trust_status must remain untrusted_candidate")

    registry = load_json(REGISTRY_JSON)
    entries = registry.get("entries", [])
    require(isinstance(entries, list), "registry entries must be a list")
    entry = next((item for item in entries if isinstance(item, dict) and item.get("candidate_id") == "verifier_health_check"), None)
    require(entry is not None, "approved-inactive registry entry missing")
    require(entry.get("status") == "approved_inactive", "registry entry must be approved_inactive")
    require(entry.get("trust_status") == "reviewed_but_inactive", "registry entry trust status mismatch")

    activation = load_json(ACTIVATION_JSON)
    require(activation.get("status") == "contract_only", "activation contract must remain contract_only")
    for field in [
        "runtime_enabled_now",
        "autorun_enabled_now",
        "manual_run_enabled_now",
        "scheduled_run_enabled_now",
        "background_workers_enabled_now",
        "external_ai_access_enabled_now",
        "provider_api_enabled_now",
        "network_enabled_now",
        "local_llm_inference_enabled_now",
        "trusted_memory_write_enabled_now",
        "source_mutation_enabled_now",
        "route_mutation_enabled_now",
        "queue_mutation_enabled_now",
    ]:
        require(activation.get(field) is False, f"activation contract {field} must be false")

    lifecycle = load_json(LIFECYCLE_REVIEW_JSON)
    require(lifecycle.get("lifecycle_stable_now") is True, "lifecycle stability review must be stable")
    require(lifecycle.get("blocked") is False, "lifecycle stability review must not be blocked")

    expected = {
        "candidate_exists": True,
        "approved_inactive_registry_exists": True,
        "registry_entry_exists": True,
        "activation_contract_exists": True,
        "activation_contract_verifier_passes": True,
        "lifecycle_stability_review_stable": True,
        "runtime_remains_false": True,
        "autorun_remains_false": True,
        "manual_run_remains_false_now": True,
    }
    for key, value in expected.items():
        require(preconditions.get(key) is value, f"precondition {key} must be {value!r}")
    if status == "ready_for_manual_run_contract_only":
        require(entry is not None, "contract claims ready but registry entry is absent")
    print_result("PASS", "precondition result", str(status))


def verify_manual_run_states(contract: dict[str, Any]) -> None:
    states = contract.get("manual_run_states")
    require(isinstance(states, dict), "manual_run_states must be an object")
    allowed = states.get("allowed_states")
    require(isinstance(allowed, list), "manual_run_states.allowed_states must be a list")
    missing = sorted(MANUAL_RUN_STATES - set(str(item) for item in allowed))
    require(not missing, "missing manual-run states: " + ", ".join(missing))
    current = states.get("current_manual_run_state")
    require(current in {"manual_run_contract_defined", "blocked_until_preconditions_met"}, "invalid current manual-run state")
    for field in ["manual_run_enabled_now", "runtime_enabled_now", "autorun_enabled_now", "scheduled_run_enabled_now"]:
        require(contract.get(field) is False, f"{field} must be false")
    print_result("PASS", "manual-run state result", str(current))


def verify_future_command_concept(contract: dict[str, Any]) -> None:
    concept = contract.get("future_command_concept")
    require(isinstance(concept, dict), "future_command_concept must be an object")
    require(concept.get("implemented_now") is False, "future command must remain unimplemented")
    require(concept.get("canonical_future_command") == "engel ai agent run verifier_health_check", "canonical future command mismatch")
    for field in [
        "requires_approved_inactive_registry_entry",
        "requires_activation_contract",
        "requires_manual_run_contract",
        "runs_only_allowlisted_commands",
        "writes_report_only_receipt",
        "fail_closed_if_registry_contract_or_verifier_check_fails",
    ]:
        require(concept.get(field) is True, f"future command must require {field}")
    for field in [
        "arbitrary_command_input_allowed",
        "discovered_script_execution_allowed",
        "background_or_autorun_allowed",
    ]:
        require(concept.get(field) is False, f"future command must disable {field}")
    print_result("PASS", "future command concept result", "future-only")


def script_path_from_command(command: str) -> Path | None:
    python_prefix = "python .\\"
    ps_prefix = "powershell -ExecutionPolicy Bypass -File .\\"
    if command.startswith(python_prefix):
        return ROOT / command[len(python_prefix) :]
    if command.startswith(ps_prefix):
        return ROOT / command[len(ps_prefix) :]
    return None


def validate_allowlisted_command(command: str) -> None:
    require(command.startswith("python .\\tools\\verify_") or command == r"powershell -ExecutionPolicy Bypass -File .\scripts\codex_verify.ps1", "command prefix not allowed: " + command)
    for token in ["*", "<", ">", "|", "&", ";", "`", "$(", "{", "}"]:
        require(token not in command, "command contains wildcard/interpolation/user placeholder token: " + command)
    lower = f" {command.lower()} "
    blocked_terms = [
        " pip ",
        " pip.exe ",
        " npm ",
        " pnpm ",
        " yarn ",
        " conda ",
        " poetry ",
        " pipenv ",
        " winget ",
        " choco ",
        " curl ",
        " wget ",
        " git add ",
        " git commit ",
        " git push ",
        " build ",
        " pyinstaller ",
        " ollama ",
        " llama-server ",
        " openai ",
        " model-server ",
    ]
    for term in blocked_terms:
        require(term not in lower, "command contains forbidden tool/action term: " + command)


def verify_allowlist(contract: dict[str, Any]) -> None:
    allowlist = contract.get("verifier_command_allowlist")
    require(isinstance(allowlist, list) and allowlist, "verifier_command_allowlist must be a non-empty list")
    commands = []
    for item in allowlist:
        require(isinstance(item, str), "allowlist entries must be literal command strings")
        command = item.strip()
        require(command, "allowlist command must not be blank")
        validate_allowlisted_command(command)
        commands.append(command)
        script = script_path_from_command(command)
        require(script is not None, "could not derive script path for command: " + command)
        if script.exists():
            print_result("PASS", "allowlisted file exists", rel(script))
        elif command in EXPECTED_OPTIONAL_COMMANDS:
            print_result("INFO", "optional allowlisted file missing", rel(script))
        else:
            raise CheckFailure("required allowlisted file missing: " + rel(script))

    command_set = set(commands)
    missing_required = sorted(EXPECTED_REQUIRED_COMMANDS - command_set)
    require(not missing_required, "missing required allowlist commands: " + ", ".join(missing_required))
    unexpected = sorted(command_set - EXPECTED_REQUIRED_COMMANDS - EXPECTED_OPTIONAL_COMMANDS)
    require(not unexpected, "unexpected allowlist commands: " + ", ".join(unexpected))
    print_result("PASS", "allowlist result", f"commands={len(commands)}")


def verify_runtime_limits(contract: dict[str, Any]) -> None:
    limits = contract.get("runtime_limits")
    require(isinstance(limits, dict), "runtime_limits must be an object")
    maximums = {
        "max_total_runtime_seconds": 600,
        "max_command_runtime_seconds": 120,
        "max_output_bytes_per_command": 20000,
        "max_commands_per_run": 25,
    }
    for key, maximum in maximums.items():
        value = limits.get(key)
        require(isinstance(value, int), f"{key} must be an integer")
        require(0 < value <= maximum, f"{key} must be between 1 and {maximum}")
    for key in ["parallel_execution_enabled", "retry_loop_enabled", "background_execution_enabled"]:
        require(limits.get(key) is False, f"{key} must be false")
    require(limits.get("process_cleanup_required") is True, "process_cleanup_required must be true")
    print_result("PASS", "runtime limits result", "bounded")


def verify_receipt_model(contract: dict[str, Any]) -> None:
    receipt = contract.get("receipt_model")
    require(isinstance(receipt, dict), "receipt_model must be an object")
    expected_folder = "reports\\agent_skill_runtime_receipts\\verifier_health_check\\"
    require(receipt.get("future_receipt_folder") == expected_folder, "receipt folder mismatch")
    require(receipt.get("write_receipts_now") is False, "receipt model must not write receipts now")
    fields = receipt.get("required_fields")
    require(isinstance(fields, list), "receipt_model.required_fields must be a list")
    missing_fields = sorted(RECEIPT_FIELDS - set(str(item) for item in fields))
    require(not missing_fields, "receipt model missing fields: " + ", ".join(missing_fields))
    confirmations = receipt.get("required_confirmations")
    require(isinstance(confirmations, dict), "receipt_model.required_confirmations must be an object")
    require(confirmations.get("files_changed_by_agent") == [], "files_changed_by_agent must be []")
    require(confirmations.get("run_mode") == "manual_run_only", "receipt run_mode must be manual_run_only")
    for key in REQUIRED_RECEIPT_CONFIRMATIONS:
        require(confirmations.get(key) is True, f"receipt confirmation missing: {key}")
    print_result("PASS", "receipt model result", f"fields={len(RECEIPT_FIELDS)}")


def verify_forbidden_behavior(contract: dict[str, Any]) -> None:
    forbidden = contract.get("forbidden_behavior")
    require(isinstance(forbidden, list), "forbidden_behavior must be a list")
    blob = norm(forbidden)
    missing = [term for term in FORBIDDEN_TERMS if norm(term) not in blob]
    require(not missing, "forbidden_behavior missing terms: " + ", ".join(missing))
    print_result("PASS", "forbidden behavior result", f"terms={len(FORBIDDEN_TERMS)}")


def verify_future_verifier_and_safety(contract: dict[str, Any]) -> None:
    future = contract.get("future_verifier")
    require(isinstance(future, dict), "future_verifier must be an object")
    require(future.get("path") == "tools\\verify_verifier_health_check_agent_manual_run_contract.py", "future verifier path mismatch")
    checks = future.get("planned_checks")
    require(isinstance(checks, list) and checks, "future verifier planned_checks must be a list")
    required_fragments = [
        "manual-run contract exists",
        "approved-inactive entry exists",
        "activation contract exists",
        "manual_run_enabled_now is false",
        "allowlist is literal and fixed",
        "runtime limits exist",
        "receipt model exists",
        "forbidden behavior is documented",
    ]
    checks_blob = norm(checks)
    for fragment in required_fragments:
        require(norm(fragment) in checks_blob, "future verifier planned check missing: " + fragment)

    safety = contract.get("safety_preserved")
    require(isinstance(safety, dict), "safety_preserved must be an object")
    false_fields = [
        "manual_run_command_implemented",
        "agent_activated",
        "agent_run",
        "verifier_commands_run_through_agent",
        "runtime_enabled",
        "autorun_enabled",
        "scheduled_or_background_startup_behavior",
        "external_ai_provider_network_behavior",
        "local_llm_inference",
        "trusted_memory_write",
        "memory_promotion",
        "source_mutation",
        "route_mutation",
        "queue_mutation",
        "package_install",
        "mobile_or_remote_queen_runtime",
        "build_or_promote",
        "staging_or_commit",
        "files_outside_workspace_changed",
    ]
    for field in false_fields:
        require(safety.get(field) is False, f"safety_preserved {field} must be false")
    print_result("PASS", "future verifier and safety result")


def is_verifier_file(path: Path) -> bool:
    try:
        relative = path.relative_to(ROOT)
    except ValueError:
        return False
    return len(relative.parts) >= 2 and relative.parts[0] == "tools" and path.name.startswith("verify_")


def line_is_disabled_or_future(line: str) -> bool:
    lower = line.lower()
    return any(
        term in lower
        for term in [
            "false",
            "disabled",
            "future",
            "forbidden",
            "blocked",
            "review_required",
            "must not",
            "do not",
            "no ",
            "not ",
        ]
    )


def generic_hit_is_unrelated(line: str, labels: list[str]) -> bool:
    generic = {"scheduler", "startup_hook", "start_worker"}
    if not any(label in generic for label in labels):
        return False
    lower = line.lower()
    related_terms = [
        "verifier_health_check",
        "manual_run",
        "agent_skill_runtime_receipts",
        "run_allowlisted_verifiers_as_agent",
        "approved agent",
    ]
    return not any(term in lower for term in related_terms)


def is_expected_command_implementation_context(path: Path) -> bool:
    rel_path = rel(path).replace("\\", "/")
    implementation_verifier = ROOT / "tools" / "verify_verifier_health_check_agent_manual_run_command.py"
    return rel_path in {
        "engel_app.py",
        "memory/ROUTE_VERIFICATION_SET_V1.json",
        "memory/ENGEL_COMMANDS.md",
    } and implementation_verifier.exists()


def scan_active_source() -> None:
    scanned = 0
    safe_refs = 0
    findings: list[str] = []

    def scan_path(path: Path) -> None:
        nonlocal scanned, safe_refs, findings
        if path == SELF:
            return
        scanned += 1
        try:
            lines = read_text(path).splitlines()
        except OSError:
            return
        for line_number, line in enumerate(lines, start=1):
            hits = [label for label, pattern in ACTIVE_PATTERNS if pattern.search(line)]
            if not hits:
                continue
            if (
                generic_hit_is_unrelated(line, hits)
                or is_verifier_file(path)
                or line_is_disabled_or_future(line)
                or is_expected_command_implementation_context(path)
            ):
                safe_refs += len(hits)
                continue
            findings.append(f"{rel(path)}:{line_number} hits={','.join(hits)}")

    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [name for name in dirnames if name.lower() not in EXCLUDE_DIRS]
        base = Path(dirpath)
        for filename in filenames:
            path = base / filename
            suffix = path.suffix.lower()
            if suffix in BINARY_SUFFIXES or suffix not in ACTIVE_SOURCE_SUFFIXES:
                continue
            scan_path(path)
    for config_path in CONFIG_FILES_TO_SCAN:
        if config_path.exists():
            scan_path(config_path)
    for finding in findings:
        print_result("REVIEW_REQUIRED", "active source finding", finding)
    require(not findings, "active source scan found likely manual-run/runtime implementation")
    print_result("INFO", "active source files scanned", str(scanned))
    print_result("INFO", "safe disabled/verifier references", str(safe_refs))
    print_result("PASS", "active source scan result", "no active manual-run/runtime behavior found")


def main() -> int:
    print("ENGEL_VERIFIER_HEALTH_CHECK_AGENT_MANUAL_RUN_CONTRACT_VERIFIER")
    print(f"ROOT {ROOT}")
    print(
        "Mode: contract/static verification only; no manual-run command, agent activation, agent run, receipt creation, provider, model, or mutation"
    )
    try:
        py_compile.compile(str(SELF), doraise=True)
        print_result("PASS", "py_compile", rel(SELF))
        verify_required_files()
        contract = load_json(CONTRACT_JSON)
        require(isinstance(contract, dict), "manual-run contract JSON must be an object")
        verify_contract_values(contract)
        verify_preconditions(contract)
        verify_manual_run_states(contract)
        verify_future_command_concept(contract)
        verify_allowlist(contract)
        verify_runtime_limits(contract)
        verify_receipt_model(contract)
        verify_forbidden_behavior(contract)
        verify_future_verifier_and_safety(contract)
        scan_active_source()
    except py_compile.PyCompileError as exc:
        print_result("FAIL", "py_compile", str(exc))
        return 1
    except json.JSONDecodeError as exc:
        print_result("FAIL", "JSON parse", str(exc))
        return 1
    except (CheckFailure, OSError) as exc:
        print_result("FAIL", "manual-run contract verification", str(exc))
        return 1
    except Exception as exc:
        print_result("FAIL", "unexpected verifier error", f"{type(exc).__name__}: {exc}")
        return 1

    print_result("PASS", "contract check result")
    print_result("PASS", "precondition result")
    print_result("PASS", "manual-run state result")
    print_result("PASS", "future command concept result")
    print_result("PASS", "allowlist result")
    print_result("PASS", "runtime limits result")
    print_result("PASS", "receipt model result")
    print_result("PASS", "forbidden behavior result")
    print_result("PASS", "active source scan result")
    print("VERIFIER_HEALTH_CHECK_AGENT_MANUAL_RUN_CONTRACT_VERIFICATION_PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
