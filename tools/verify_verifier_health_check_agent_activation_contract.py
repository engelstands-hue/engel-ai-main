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

CONTRACT_JSON = ROOT / "memory" / "ENGEL_VERIFIER_HEALTH_CHECK_AGENT_ACTIVATION_CONTRACT_V1.json"
CONTRACT_MD = ROOT / "memory" / "ENGEL_VERIFIER_HEALTH_CHECK_AGENT_ACTIVATION_CONTRACT_V1.md"
CONTRACT_REPORT = (
    ROOT
    / "reports"
    / "codex_bridge"
    / "ENGEL_VERIFIER_HEALTH_CHECK_AGENT_ACTIVATION_CONTRACT_V1.md"
)

CANDIDATE_JSON = ROOT / "reports" / "agent_skill_candidates" / "verifier_health_check.agent.json"
CANDIDATE_MD = ROOT / "reports" / "agent_skill_candidates" / "verifier_health_check.agent.md"
HUMAN_REVIEW_MD = ROOT / "reports" / "codex_bridge" / "ENGEL_AGENT_SKILL_FIRST_CANDIDATE_HUMAN_REVIEW_V1.md"
HUMAN_REVIEW_JSON = ROOT / "reports" / "codex_bridge" / "ENGEL_AGENT_SKILL_FIRST_CANDIDATE_HUMAN_REVIEW_V1.json"
REGISTRY_JSON = ROOT / "memory" / "ENGEL_AGENT_SKILL_APPROVED_INACTIVE_REGISTRY_V1.json"
REGISTRY_MD = ROOT / "memory" / "ENGEL_AGENT_SKILL_APPROVED_INACTIVE_REGISTRY_V1.md"
APPROVAL_RECEIPT = ROOT / "reports" / "codex_bridge" / "ENGEL_AGENT_SKILL_APPROVED_INACTIVE_verifier_health_check.md"

REQUIRED_VALUES = {
    "contract_id": "ENGEL_VERIFIER_HEALTH_CHECK_AGENT_ACTIVATION_CONTRACT_V1",
    "status": "contract_only",
    "active_workspace": r"D:\b.WorkSpace\Engel App",
    "agent_id": "verifier_health_check",
    "agent_name": "Verifier Health Check Agent",
    "activation_enabled_now": False,
    "runtime_enabled_now": False,
    "manual_run_enabled_now": False,
    "scheduled_run_enabled_now": False,
    "autorun_enabled_now": False,
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
    "activation_precondition_status",
    "activation_states",
    "allowed_manual_run_scope",
    "verifier_command_allowlist",
    "forbidden_behavior",
    "runtime_limits",
    "receipt_model",
    "future_command_concept",
    "future_verifier",
    "stop_conditions",
    "recommended_next_slice",
    "safety_preserved",
]

ALLOWED_PRECONDITION_STATUSES = {
    "ready_for_future_manual_run_contract",
    "blocked_until_approved_inactive",
    "blocked_missing_human_review",
    "blocked_missing_candidate",
    "blocked_missing_registry",
    "review_required",
}

ACTIVATION_STATES = {
    "approved_inactive",
    "activation_contract_defined",
    "manual_run_implementation_pending",
    "manual_run_enabled_future",
    "scheduled_safe_pending_future",
    "disabled",
    "blocked",
}

MANUAL_SCOPE_TRUE_FIELDS = [
    "run_fixed_allowlist_of_verifier_commands",
    "capture_stdout_stderr_summaries",
    "capture_exit_codes",
    "write_health_check_receipt",
    "return_pass_fail_blocker_summary",
    "enforce_runtime_timeout",
    "enforce_output_size_limits",
]

ALLOWED_OUTPUTS = {"report", "receipt", "status summary", "blocker notice"}

FORBIDDEN_BEHAVIOR_TERMS = [
    "arbitrary command execution",
    "discovered script execution",
    "source patching",
    "trusted-memory update",
    "route update",
    "queue update",
    "candidate promotion",
    "registry mutation",
    "automatic fix application",
    "commit",
    "stage",
    "build",
    "promote",
    "package install",
    "external AI task packet",
    "provider call",
    "network call",
    "local LLM inference",
    "Mobile runtime",
    "Remote Queen runtime",
    "self-activation",
    "self-scheduling",
    "background loop",
]

RECEIPT_FIELDS = [
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
]

RECEIPT_CONFIRMATIONS = [
    "no_source_files_edited",
    "no_routes_mutated",
    "no_queues_mutated",
    "no_trusted_memory_written",
    "no_external_ai_provider_network_called",
    "no_local_llm_inference_run",
    "no_packages_installed",
    "no_build_promote_stage_commit",
    "no_mobile_or_remote_queen_runtime_started",
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
    ("future_run_command_one", re.compile(r"engel ai agent run verifier_health_check", re.I)),
    ("future_run_command_two", re.compile(r"engel ai run approved agent verifier_health_check", re.I)),
    ("activate_verifier_health_check", re.compile(r"\bactivate_verifier_health_check\b", re.I)),
    ("run_verifier_health_check_agent", re.compile(r"\brun_verifier_health_check_agent\b", re.I)),
    ("verifier_health_check_runtime_enabled", re.compile(r"\bverifier_health_check_runtime_enabled\b", re.I)),
    ("manual_run_enabled_now_true", re.compile(r"\bmanual_run_enabled_now\s*[:=]\s*(?:True|true|\$true)\b")),
    ("scheduled_run_enabled_now_true", re.compile(r"\bscheduled_run_enabled_now\s*[:=]\s*(?:True|true|\$true)\b")),
    ("autorun_enabled_now_true", re.compile(r"\bautorun_enabled_now\s*[:=]\s*(?:True|true|\$true)\b")),
    ("run_allowlisted_verifiers_as_agent", re.compile(r"\brun_allowlisted_verifiers_as_agent\b", re.I)),
    ("agent_runtime_receipts", re.compile(r"\bagent_runtime_receipts\b", re.I)),
    ("subprocess_verifier_health_check", re.compile(r"\bsubprocess\b.*\bverifier_health_check\b", re.I)),
    ("background_worker", re.compile(r"\bbackground_worker\b", re.I)),
    ("scheduler", re.compile(r"\bscheduler\b", re.I)),
    ("startup_hook", re.compile(r"\bstartup_hook\b", re.I)),
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


def text_blob(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(text_blob(item) for pair in value.items() for item in pair)
    if isinstance(value, list):
        return " ".join(text_blob(item) for item in value)
    return str(value)


def norm(value: Any) -> str:
    return " ".join(str(value).lower().replace("\\", "/").replace("_", " ").replace("-", " ").split())


def require_required_files() -> None:
    required = [CONTRACT_JSON, CONTRACT_MD, CONTRACT_REPORT]
    missing = [rel(path) for path in required if not path.exists()]
    require(not missing, "missing activation contract files: " + ", ".join(missing))
    for path in required:
        print_result("PASS", "required activation contract file", rel(path))


def verify_contract_values(contract: dict[str, Any]) -> None:
    for key, expected in REQUIRED_VALUES.items():
        actual = contract.get(key)
        require(actual == expected, f"{key} expected {expected!r}, got {actual!r}")
    missing_keys = [key for key in REQUIRED_KEYS if key not in contract]
    require(not missing_keys, "missing required keys: " + ", ".join(missing_keys))
    print_result("PASS", "contract check result", f"values={len(REQUIRED_VALUES)} keys={len(REQUIRED_KEYS)}")


def verify_preconditions(contract: dict[str, Any]) -> None:
    preconditions = contract.get("activation_precondition_status")
    require(isinstance(preconditions, dict), "activation_precondition_status must be an object")
    status = preconditions.get("status")
    require(status in ALLOWED_PRECONDITION_STATUSES, f"precondition status is not allowed: {status!r}")

    expected_fields = [
        "candidate_json_exists",
        "candidate_md_exists",
        "human_review_report_md_exists",
        "human_review_report_json_exists",
        "approved_inactive_registry_exists",
        "approved_inactive_registry_md_exists",
        "approved_inactive_receipt_exists",
        "approved_inactive_entry_present",
    ]
    for field in expected_fields:
        require(field in preconditions, f"precondition field missing: {field}")

    actual_paths = {
        "candidate_json_exists": CANDIDATE_JSON.exists(),
        "candidate_md_exists": CANDIDATE_MD.exists(),
        "human_review_report_md_exists": HUMAN_REVIEW_MD.exists(),
        "human_review_report_json_exists": HUMAN_REVIEW_JSON.exists(),
        "approved_inactive_registry_exists": REGISTRY_JSON.exists(),
        "approved_inactive_registry_md_exists": REGISTRY_MD.exists(),
        "approved_inactive_receipt_exists": APPROVAL_RECEIPT.exists(),
    }
    for field, exists in actual_paths.items():
        require(preconditions.get(field) is exists, f"{field} contract={preconditions.get(field)!r} actual={exists!r}")

    registry_entry_present = False
    if REGISTRY_JSON.exists():
        registry = load_json(REGISTRY_JSON)
        entries = registry.get("entries", [])
        require(isinstance(entries, list), "approved inactive registry entries must be a list")
        for entry in entries:
            if isinstance(entry, dict) and entry.get("candidate_id") == "verifier_health_check":
                registry_entry_present = entry.get("status") == "approved_inactive"
                require(entry.get("trust_status") == "reviewed_but_inactive", "registry entry trust status mismatch")
                for field in [
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
                ]:
                    require(entry.get(field) is False, f"registry entry {field} must be false")
                break
    require(preconditions.get("approved_inactive_entry_present") is registry_entry_present, "approved inactive entry status mismatch")

    if status == "ready_for_future_manual_run_contract":
        require(registry_entry_present, "contract claims ready but registry entry is absent")
    if not registry_entry_present:
        require(status == "blocked_until_approved_inactive", "missing registry entry must be blocked_until_approved_inactive")
    print_result("PASS", "activation precondition result", str(status))


def verify_activation_states(contract: dict[str, Any]) -> None:
    states = contract.get("activation_states")
    require(isinstance(states, dict), "activation_states must be an object")
    allowed = states.get("allowed_states")
    require(isinstance(allowed, list), "activation_states.allowed_states must be a list")
    missing = sorted(ACTIVATION_STATES - set(str(item) for item in allowed))
    require(not missing, "missing activation states: " + ", ".join(missing))
    current = states.get("current_activation_state")
    require(current in {"activation_contract_defined", "blocked_until_approved_inactive"}, "invalid current activation state")
    for field in ["runtime_enabled_now", "manual_run_enabled_now", "scheduled_run_enabled_now", "autorun_enabled_now"]:
        require(contract.get(field) is False, f"{field} must be false")
    print_result("PASS", "activation state result", str(current))


def verify_manual_scope(contract: dict[str, Any]) -> None:
    scope = contract.get("allowed_manual_run_scope")
    require(isinstance(scope, dict), "allowed_manual_run_scope must be an object")
    require(scope.get("future_only") is True, "manual-run scope must be future_only")
    for field in MANUAL_SCOPE_TRUE_FIELDS:
        require(scope.get(field) is True, "manual-run scope missing true field: " + field)
    outputs = scope.get("allowed_outputs")
    require(isinstance(outputs, list), "allowed_outputs must be a list")
    require(set(outputs) == ALLOWED_OUTPUTS, "allowed_outputs must be report/receipt/status summary/blocker notice only")
    forbidden_outputs = norm(scope.get("forbidden_outputs", []))
    for term in [
        "source patch",
        "trusted memory update",
        "route update",
        "queue update",
        "candidate promotion",
        "registry mutation",
        "automatic fix application",
        "commit",
        "stage",
        "build",
        "promote",
        "external ai task packet",
    ]:
        require(norm(term) in forbidden_outputs, "manual-run forbidden output missing: " + term)
    print_result("PASS", "manual-run scope result", "report-only future scope")


def validate_command(command: str) -> None:
    require(command.startswith("python .\\tools\\verify_") or command == "powershell -ExecutionPolicy Bypass -File .\\scripts\\codex_verify.ps1", "command prefix not allowed: " + command)
    forbidden_tokens = ["*", "<", ">", "|", "&", ";", "`", "$(", "{", "}"]
    for token in forbidden_tokens:
        require(token not in command, "command contains forbidden shell/user placeholder token: " + command)
    lower = command.lower()
    for term in [" pip ", "pip.exe", "npm", "pnpm", "yarn", "conda", "poetry", "pipenv", "winget", "choco", "curl", "wget", "ollama", "llama-server", "openai "]:
        require(term not in lower, "command contains package/network/model tool term: " + command)


def verify_allowlist(contract: dict[str, Any]) -> None:
    allowlist = contract.get("verifier_command_allowlist")
    require(isinstance(allowlist, list) and allowlist, "verifier_command_allowlist must be a non-empty list")
    for item in allowlist:
        require(isinstance(item, dict), "allowlist item must be an object")
        command = item.get("command")
        require(isinstance(command, str) and command.strip(), "allowlist command must be a string")
        validate_command(command)
        script_path = item.get("script_path")
        require(isinstance(script_path, str) and script_path.strip(), "allowlist script_path must be present")
        script = ROOT / script_path
        required = item.get("required") is True
        if script.exists():
            print_result("PASS", "allowlisted verifier exists", script_path)
        elif required:
            raise CheckFailure("required allowlisted verifier is missing: " + script_path)
        else:
            print_result("INFO", "optional allowlisted verifier missing", script_path)

    optional = contract.get("optional_full_stack_command")
    if isinstance(optional, dict):
        command = optional.get("command")
        if isinstance(command, str) and command.strip():
            validate_command(command)
            script_path = optional.get("script_path")
            if isinstance(script_path, str) and script_path.strip():
                script = ROOT / script_path
                print_result("PASS" if script.exists() else "INFO", "optional full-stack command file", script_path)

    rules = contract.get("allowlist_rules")
    require(isinstance(rules, dict), "allowlist_rules must be an object")
    for field in [
        "literal_fixed_commands_only",
    ]:
        require(rules.get(field) is True, "allowlist rule must be true: " + field)
    for field in [
        "shell_interpolation_allowed",
        "user_supplied_command_text_allowed",
        "wildcard_execution_allowed",
        "run_files_discovered_by_scan_allowed",
        "package_manager_commands_allowed",
        "network_provider_model_commands_allowed",
        "arbitrary_script_execution_allowed",
    ]:
        require(rules.get(field) is False, "allowlist rule must be false: " + field)
    print_result("PASS", "allowlist result", f"commands={len(allowlist)}")


def verify_forbidden_behavior(contract: dict[str, Any]) -> None:
    forbidden = contract.get("forbidden_behavior")
    require(isinstance(forbidden, list), "forbidden_behavior must be a list")
    blob = norm(forbidden)
    missing = [term for term in FORBIDDEN_BEHAVIOR_TERMS if norm(term) not in blob]
    require(not missing, "forbidden_behavior missing terms: " + ", ".join(missing))
    print_result("PASS", "forbidden behavior result", f"terms={len(FORBIDDEN_BEHAVIOR_TERMS)}")


def verify_runtime_limits(contract: dict[str, Any]) -> None:
    limits = contract.get("runtime_limits")
    require(isinstance(limits, dict), "runtime_limits must be an object")
    numeric_limits = {
        "max_total_runtime_seconds": 600,
        "max_command_runtime_seconds": 120,
        "max_output_bytes_per_command": 20000,
        "max_commands_per_run": 20,
    }
    for field, maximum in numeric_limits.items():
        value = limits.get(field)
        require(isinstance(value, int), field + " must be an integer")
        require(0 < value <= maximum, f"{field} must be between 1 and {maximum}")
    require(limits.get("parallel_execution_enabled") is False, "parallel_execution_enabled must be false")
    require(limits.get("background_loop_enabled") is False, "background_loop_enabled must be false")
    require(limits.get("retry_loop_enabled") is False, "retry_loop_enabled must be false")
    require(limits.get("process_cleanup_check_required") is True, "process cleanup check must be required")
    print_result("PASS", "runtime limits result", "bounded future manual run")


def verify_receipt_model(contract: dict[str, Any]) -> None:
    receipt = contract.get("receipt_model")
    require(isinstance(receipt, dict), "receipt_model must be an object")
    require(receipt.get("future_receipt_root") == "reports\\agent_skill_runtime_receipts\\verifier_health_check\\", "future receipt root mismatch")
    require(receipt.get("write_receipts_now") is False, "receipt model must not write receipts now")
    fields = receipt.get("required_fields")
    require(isinstance(fields, list), "receipt_model.required_fields must be a list")
    missing = [field for field in RECEIPT_FIELDS if field not in fields]
    require(not missing, "receipt model missing fields: " + ", ".join(missing))
    confirmations = receipt.get("required_confirmations")
    require(isinstance(confirmations, dict), "receipt_model.required_confirmations must be an object")
    require(confirmations.get("files_changed_by_agent") == [], "files_changed_by_agent must be []")
    for field in RECEIPT_CONFIRMATIONS:
        require(confirmations.get(field) is True, "receipt confirmation missing: " + field)
    print_result("PASS", "receipt model result", f"fields={len(RECEIPT_FIELDS)} confirmations={len(RECEIPT_CONFIRMATIONS)}")


def verify_future_command_concept(contract: dict[str, Any]) -> None:
    concept = contract.get("future_command_concept")
    require(isinstance(concept, dict), "future_command_concept must be an object")
    commands = concept.get("candidate_commands")
    require(isinstance(commands, list), "future candidate commands must be a list")
    for command in ["engel ai agent run verifier_health_check", "engel ai run approved agent verifier_health_check"]:
        require(command in commands, "future command concept missing: " + command)
    require(concept.get("implemented_now") is False, "future command must not be implemented now")
    for field in [
        "requires_approved_inactive_registry_entry",
        "requires_activation_contract",
        "runs_only_allowlisted_commands",
        "writes_receipt",
        "manual_run_mode_requires_future_implementation",
    ]:
        require(concept.get(field) is True, "future command concept must require: " + field)
    require(concept.get("arbitrary_command_input_allowed") is False, "future command must reject arbitrary command input")
    require(concept.get("run_when_registry_runtime_enabled_false_allowed_now") is False, "future command must not run now")
    print_result("PASS", "future command concept result", "future-only and unimplemented")


def is_verifier_only(path: Path) -> bool:
    try:
        relative = path.relative_to(ROOT)
    except ValueError:
        return False
    return len(relative.parts) >= 2 and relative.parts[0] == "tools" and path.name.startswith("verify_")


def line_clearly_disabled(line: str) -> bool:
    lower = line.lower()
    safe_terms = [
        "false",
        "disabled",
        "not enabled",
        "future",
        "forbidden",
        "blocked",
        "review_required",
        "no ",
        "do not",
        "must not",
    ]
    return any(term in lower for term in safe_terms)


def broad_pattern_is_unrelated(line: str, hits: list[str]) -> bool:
    broad_hits = {"background_worker", "scheduler", "startup_hook"}
    if not any(hit in broad_hits for hit in hits):
        return False
    lower = line.lower()
    agent_terms = [
        "verifier_health_check",
        "agent_runtime_receipts",
        "manual_run",
        "activation_contract",
        "run approved agent",
        "agent run verifier_health_check",
    ]
    return not any(term in lower for term in agent_terms)


def is_expected_manual_run_command_implementation(path: Path) -> bool:
    rel_path = rel(path).replace("\\", "/")
    implementation_verifier = ROOT / "tools" / "verify_verifier_health_check_agent_manual_run_command.py"
    return rel_path == "engel_app.py" and implementation_verifier.exists()


def scan_active_source() -> None:
    scanned = 0
    findings: list[str] = []
    skipped_safe_context = 0
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [dirname for dirname in dirnames if dirname.lower() not in EXCLUDE_DIRS]
        current = Path(dirpath)
        for filename in filenames:
            path = current / filename
            if path == SELF:
                continue
            suffix = path.suffix.lower()
            if suffix in BINARY_SUFFIXES or suffix not in ACTIVE_SOURCE_SUFFIXES:
                continue
            scanned += 1
            try:
                lines = read_text(path).splitlines()
            except OSError:
                continue
            for line_number, line in enumerate(lines, start=1):
                hits = [label for label, pattern in ACTIVE_SOURCE_PATTERNS if pattern.search(line)]
                if not hits:
                    continue
                if broad_pattern_is_unrelated(line, hits):
                    skipped_safe_context += len(hits)
                    continue
                if is_verifier_only(path) or line_clearly_disabled(line) or is_expected_manual_run_command_implementation(path):
                    skipped_safe_context += len(hits)
                    continue
                findings.append(f"{rel(path)}:{line_number} hits={','.join(hits)}")
    for item in findings:
        print_result("REVIEW_REQUIRED", "active source finding", item)
    require(not findings, "active source scan found activation/runtime patterns requiring review")
    print_result("INFO", "active source files scanned", str(scanned))
    print_result("INFO", "safe disabled/verifier references", str(skipped_safe_context))
    print_result("PASS", "active source scan result", "failures=0 review_required=0")


def main() -> int:
    print("ENGEL_VERIFIER_HEALTH_CHECK_AGENT_ACTIVATION_CONTRACT_VERIFIER")
    print(f"ROOT {ROOT}")
    print("Mode: contract/static verification only; no agent activation, no agent run, no runtime receipts")
    try:
        py_compile.compile(str(SELF), doraise=True)
        print_result("PASS", "py_compile", rel(SELF))
        require_required_files()
        contract = load_json(CONTRACT_JSON)
        require(isinstance(contract, dict), "activation contract JSON must be an object")
        verify_contract_values(contract)
        verify_preconditions(contract)
        verify_activation_states(contract)
        verify_manual_scope(contract)
        verify_allowlist(contract)
        verify_forbidden_behavior(contract)
        verify_runtime_limits(contract)
        verify_receipt_model(contract)
        verify_future_command_concept(contract)
        scan_active_source()
    except py_compile.PyCompileError as exc:
        print_result("FAIL", "py_compile", str(exc))
        return 1
    except json.JSONDecodeError as exc:
        print_result("FAIL", "JSON parse", str(exc))
        return 1
    except (CheckFailure, OSError) as exc:
        print_result("FAIL", "verifier health check activation contract", str(exc))
        return 1
    except Exception as exc:
        print_result("FAIL", "unexpected verifier error", f"{type(exc).__name__}: {exc}")
        return 1

    print_result("PASS", "contract check result")
    print_result("PASS", "activation precondition result")
    print_result("PASS", "activation state result")
    print_result("PASS", "manual-run scope result")
    print_result("PASS", "verifier command allowlist result")
    print_result("PASS", "forbidden behavior result")
    print_result("PASS", "runtime limits result")
    print_result("PASS", "receipt model result")
    print_result("PASS", "future command concept result")
    print_result("PASS", "active source scan result")
    print("VERIFIER_HEALTH_CHECK_AGENT_ACTIVATION_CONTRACT_VERIFICATION_PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
