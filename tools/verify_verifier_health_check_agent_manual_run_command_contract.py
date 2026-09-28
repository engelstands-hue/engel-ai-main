#!/usr/bin/env python3
"""Verify the Verifier Health Check Agent manual-run command contract.

This verifier is static/read-only. It does not implement or invoke the future
manual-run command, activate the agent, run verifiers through an agent, or write
runtime receipts.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_JSON = ROOT / "memory" / "ENGEL_VERIFIER_HEALTH_CHECK_AGENT_MANUAL_RUN_COMMAND_CONTRACT_V1.json"
CONTRACT_MD = ROOT / "memory" / "ENGEL_VERIFIER_HEALTH_CHECK_AGENT_MANUAL_RUN_COMMAND_CONTRACT_V1.md"
CONTRACT_REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_VERIFIER_HEALTH_CHECK_AGENT_MANUAL_RUN_COMMAND_CONTRACT_V1.md"

SUPPORTING_FILES = [
    ROOT / "memory" / "ENGEL_VERIFIER_HEALTH_CHECK_AGENT_MANUAL_RUN_CONTRACT_V1.json",
    ROOT / "tools" / "verify_verifier_health_check_agent_manual_run_contract.py",
    ROOT / "memory" / "ENGEL_VERIFIER_HEALTH_CHECK_AGENT_ACTIVATION_CONTRACT_V1.json",
    ROOT / "tools" / "verify_verifier_health_check_agent_activation_contract.py",
    ROOT / "memory" / "ENGEL_AGENT_SKILL_APPROVED_INACTIVE_REGISTRY_V1.json",
    ROOT / "tools" / "verify_agent_skill_approved_inactive_registry.py",
    ROOT / "tools" / "verify_engel_global_password_gate.py",
    ROOT / "memory" / "ENGEL_GLOBAL_PASSWORD_GATE_V1.json",
    ROOT / "engel_app.py",
    ROOT / "memory" / "ENGEL_COMMANDS.md",
    ROOT / "memory" / "ROUTE_VERIFICATION_SET_V1.json",
    ROOT / "tools" / "verify_route_metadata_contract.py",
    ROOT / "tools" / "verify_authority_hierarchy.py",
    ROOT / "tools" / "verify_prompt_injection_guard.py",
    ROOT / "tools" / "verify_untrusted_content_policy.py",
    ROOT / "tools" / "verify_de_bruijn_import_boundaries.py",
]

FALSE_FLAGS = [
    "command_implemented_now",
    "route_added_now",
    "runtime_enabled_now",
    "autorun_enabled_now",
    "background_execution_enabled_now",
    "scheduler_enabled_now",
    "startup_hook_enabled_now",
    "external_ai_enabled_now",
    "provider_api_enabled_now",
    "network_enabled_now",
    "local_llm_inference_enabled_now",
    "trusted_memory_write_enabled_now",
    "source_mutation_enabled_now",
    "route_mutation_enabled_now",
    "queue_mutation_enabled_now",
    "package_install_enabled_now",
    "build_promote_enabled_now",
]

REQUIRED_TOP_LEVEL_KEYS = [
    "future_command_gates",
    "future_input_contract",
    "future_output_contract",
    "future_receipt_requirements",
    "future_verifier",
    "safety_preserved",
    "recommended_next_slice",
]

REQUIRED_RECEIPT_FIELDS = [
    "receipt_id",
    "agent_id",
    "command",
    "registry_entry_id",
    "activation_contract_id",
    "manual_run_contract_id",
    "started_at",
    "ended_at",
    "commands_run",
    "commands_skipped",
    "exit_codes",
    "timeout_status",
    "output_truncation_status",
    "process_cleanup_result",
    "files_changed_by_agent",
    "final_status",
    "human_review_required",
    "forbidden_actions_not_performed",
]

FALSE_INPUT_KEYS = [
    "arbitrary_command_parameter_allowed",
    "user_supplied_script_path_allowed",
    "verifier_list_override_allowed",
    "wildcards_allowed",
    "shell_interpolation_allowed",
    "discovered_script_execution_allowed",
    "provider_model_network_arguments_allowed",
    "local_llm_arguments_allowed",
    "package_manager_arguments_allowed",
    "output_path_override_allowed",
    "git_arguments_allowed",
    "build_promote_arguments_allowed",
]

FALSE_OUTPUT_KEYS = [
    "trusted_memory_write_allowed",
    "memory_promotion_allowed",
    "route_mutation_allowed",
    "queue_mutation_allowed",
    "source_patch_allowed",
    "generated_code_patch_allowed",
    "external_ai_task_packet_allowed",
    "build_artifact_allowed",
    "promotion_artifact_allowed",
    "git_stage_commit_allowed",
    "provider_network_model_output_trusted",
    "local_llm_output_trusted",
]

EXCLUDED_DIRS = {
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

SOURCE_SUFFIXES = {".py", ".ps1", ".json", ".toml", ".yaml", ".yml"}

ACTIVE_PATTERNS = [
    ("future_command_string", re.compile(r"engel\s+ai\s+agent\s+run\s+verifier_health_check", re.I)),
    ("run_agent_function", re.compile(r"\brun_verifier_health_check_agent\b", re.I)),
    ("manual_run_function", re.compile(r"\bverifier_health_check_manual_run\b", re.I)),
    ("manual_run_command_enabled_true", re.compile(r"manual_run_command_enabled_now\s*[:=]\s*true", re.I)),
    ("command_implemented_true", re.compile(r"command_implemented_now\s*[:=]\s*true", re.I)),
    ("route_added_true", re.compile(r"route_added_now\s*[:=]\s*true", re.I)),
    ("runtime_enabled_true", re.compile(r"runtime_enabled_now\s*[:=]\s*true", re.I)),
    ("autorun_enabled_true", re.compile(r"autorun_enabled_now\s*[:=]\s*true", re.I)),
    ("background_enabled_true", re.compile(r"background_execution_enabled_now\s*[:=]\s*true", re.I)),
    ("scheduler_enabled_true", re.compile(r"scheduler_enabled_now\s*[:=]\s*true", re.I)),
    ("startup_hook_enabled_true", re.compile(r"startup_hook_enabled_now\s*[:=]\s*true", re.I)),
    ("run_allowlisted_verifiers_as_agent", re.compile(r"\brun_allowlisted_verifiers_as_agent\b", re.I)),
    ("runtime_receipts", re.compile(r"\bagent_skill_runtime_receipts\b", re.I)),
    ("subprocess_verifier_health_check", re.compile(r"subprocess[\s\S]{0,120}verifier_health_check", re.I)),
    ("trusted_memory_write_true", re.compile(r"trusted_memory_write_enabled_now\s*[:=]\s*true", re.I)),
    ("source_mutation_true", re.compile(r"source_mutation_enabled_now\s*[:=]\s*true", re.I)),
    ("route_mutation_true", re.compile(r"route_mutation_enabled_now\s*[:=]\s*true", re.I)),
    ("queue_mutation_true", re.compile(r"queue_mutation_enabled_now\s*[:=]\s*true", re.I)),
    ("external_ai_true", re.compile(r"external_ai_enabled_now\s*[:=]\s*true", re.I)),
    ("provider_api_true", re.compile(r"provider_api_enabled_now\s*[:=]\s*true", re.I)),
    ("network_true", re.compile(r"network_enabled_now\s*[:=]\s*true", re.I)),
    ("local_llm_true", re.compile(r"local_llm_inference_enabled_now\s*[:=]\s*true", re.I)),
]


class CheckFailure(Exception):
    pass


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def emit(status: str, message: str) -> None:
    print(f"{status} {message}")


def normalized_blob(value: Any) -> str:
    return json.dumps(value, sort_keys=True).lower()


def require_terms(blob: str, label: str, term_groups: Iterable[tuple[str, Iterable[str]]]) -> None:
    missing = []
    for name, terms in term_groups:
        if not any(term.lower() in blob for term in terms):
            missing.append(name)
    require(not missing, f"{label} missing required terms: {', '.join(missing)}")


def check_required_files() -> tuple[dict[str, Any], str, str]:
    required = [CONTRACT_JSON, CONTRACT_MD, CONTRACT_REPORT]
    missing = [rel(path) for path in required if not path.exists()]
    require(not missing, "missing required command contract files: " + ", ".join(missing))

    support_missing = [rel(path) for path in SUPPORTING_FILES if not path.exists()]
    require(not support_missing, "missing supporting files: " + ", ".join(support_missing))

    data = load_json(CONTRACT_JSON)
    md_text = read_text(CONTRACT_MD)
    report_text = read_text(CONTRACT_REPORT)
    emit("PASS", "required command contract and supporting files present")
    return data, md_text, report_text


def check_contract_values(data: dict[str, Any]) -> None:
    expected = {
        "contract_id": "ENGEL_VERIFIER_HEALTH_CHECK_AGENT_MANUAL_RUN_COMMAND_CONTRACT_V1",
        "status": "contract_only",
        "active_workspace": r"D:\b.WorkSpace\Engel App",
        "command_name": "engel ai agent run verifier_health_check",
    }
    for key, value in expected.items():
        require(data.get(key) == value, f"{key} mismatch")

    for flag in FALSE_FLAGS:
        require(data.get(flag) is False, f"{flag} must be false")

    for key in REQUIRED_TOP_LEVEL_KEYS:
        require(key in data, f"missing required key: {key}")

    require(data.get("safety_preserved") is True, "safety_preserved must be true")
    emit("PASS", f"contract checks values={len(expected) + len(FALSE_FLAGS)} keys={len(REQUIRED_TOP_LEVEL_KEYS)}")


def check_future_gates(data: dict[str, Any]) -> None:
    gates = data.get("future_command_gates")
    require(isinstance(gates, list) and gates, "future_command_gates must be a non-empty list")
    blob = normalized_blob(gates)
    require_terms(
        blob,
        "future command gates",
        [
            ("candidate file exists", ["candidate file exists"]),
            ("approved-inactive registry entry exists", ["registry entry exists", "approved-inactive registry entry exists"]),
            ("activation contract exists", ["activation contract exists"]),
            ("manual-run contract exists", ["manual-run contract exists"]),
            ("manual-run verifier passes", ["manual-run contract verifier passes", "manual-run verifier passes"]),
            ("global password gate", ["global password gate", "password gate"]),
            ("route verifier", ["route metadata verifier", "route metadata"]),
            ("docs verifier", ["command docs"]),
            ("command verifier", ["command implementation verifier", "command verifier"]),
            ("unsafe dirty state fails closed", ["unsafe dirty state"]),
        ],
    )
    emit("PASS", "future gate result documented and fail-closed")


def check_input_contract(data: dict[str, Any]) -> None:
    contract = data.get("future_input_contract")
    require(isinstance(contract, dict), "future_input_contract must be an object")
    require(contract.get("allowed_commands") == ["engel ai agent run verifier_health_check"], "allowed command must be exact and singular")

    optional_flags = contract.get("optional_future_flags", [])
    require(isinstance(optional_flags, list), "optional_future_flags must be a list")
    if optional_flags:
        require(optional_flags == ["--dry-run"], "only optional future --dry-run is permitted")

    for key in FALSE_INPUT_KEYS:
        require(contract.get(key) is False, f"future_input_contract.{key} must be false")

    command_text = " ".join(contract.get("allowed_commands", []))
    require("*" not in command_text and "$" not in command_text and "%" not in command_text, "allowed command contains wildcard/interpolation")
    emit("PASS", "input contract result fixed command only; arbitrary command inputs forbidden")


def check_output_contract(data: dict[str, Any]) -> None:
    contract = data.get("future_output_contract")
    require(isinstance(contract, dict), "future_output_contract must be an object")
    require(contract.get("human_readable_run_summary_allowed") is True, "human-readable summary must be allowed")
    require(contract.get("receipt_only") is True, "future output must be receipt-only")
    require(
        contract.get("receipt_folder") == "reports\\agent_skill_runtime_receipts\\verifier_health_check\\",
        "receipt folder mismatch",
    )

    for key in FALSE_OUTPUT_KEYS:
        require(contract.get(key) is False, f"future_output_contract.{key} must be false")

    emit("PASS", "output contract result receipt-only and mutation/provider outputs forbidden")


def check_receipt_requirements(data: dict[str, Any]) -> None:
    requirements = data.get("future_receipt_requirements")
    require(isinstance(requirements, list), "future_receipt_requirements must be a list")
    missing = [field for field in REQUIRED_RECEIPT_FIELDS if field not in requirements]
    require(not missing, "future_receipt_requirements missing: " + ", ".join(missing))

    required_values = data.get("future_receipt_required_values")
    require(isinstance(required_values, dict), "future_receipt_required_values must be an object")
    require(required_values.get("files_changed_by_agent") == [], "files_changed_by_agent must be required as []")
    require(required_values.get("human_review_required") is True, "human_review_required must be required true")

    confirmations = data.get("receipt_forbidden_action_confirmations", [])
    blob = normalized_blob(confirmations)
    require_terms(
        blob,
        "receipt confirmations",
        [
            ("no source files edited", ["no source files edited"]),
            ("no routes mutated", ["no routes mutated"]),
            ("no queues mutated", ["no queues mutated"]),
            ("no trusted memory written", ["no trusted memory written"]),
            ("no memory promoted", ["no memory promoted"]),
            ("no external/provider/network/model/local llm", ["external ai", "local llm"]),
            ("no package install", ["no package install"]),
            ("no build/promote/stage/commit", ["build promote stage or commit", "stage or commit"]),
            ("no runtime workers", ["background worker", "scheduler", "startup hook"]),
        ],
    )
    emit("PASS", "receipt requirement result required fields, empty file-change list, and human review documented")


def check_password_gate(data: dict[str, Any], md_text: str, report_text: str) -> None:
    handling = data.get("password_gate_handling")
    require(isinstance(handling, dict), "password_gate_handling must be an object")
    for key in [
        "actual_run_should_be_protected_action",
        "global_password_gate_required_if_project_policy_requires_manual_agent_runs",
        "password_values_must_not_be_logged",
        "password_values_must_not_be_committed",
        "local_config_may_be_enabled_but_must_remain_uncommitted",
    ]:
        require(handling.get(key) is True, f"password_gate_handling.{key} must be true")

    gate_source = read_text(ROOT / "tools" / "verify_engel_global_password_gate.py").lower()
    require("committed password gate template" in gate_source, "password gate verifier must check committed template")
    require("configured local password gate" in gate_source, "password gate verifier must allow configured local gate")
    require("head" in gate_source, "password gate verifier must inspect committed HEAD template")

    local_config = load_json(ROOT / "memory" / "ENGEL_GLOBAL_PASSWORD_GATE_V1.json")
    require(isinstance(local_config, dict), "local password gate config must parse as object")
    # Deliberately do not print or inspect secret values beyond shape/policy.
    require(handling.get("local_config_may_be_enabled_but_must_remain_uncommitted") is True, "local config policy missing")

    contract_text = read_text(CONTRACT_JSON) + "\n" + md_text + "\n" + report_text
    forbidden_secret_keys = [
        r'"password_hash"\s*:',
        r'"password_salt"\s*:',
        r'"salt"\s*:',
        r'"hash"\s*:',
        r'"raw_password"\s*:',
        r'"password_value"\s*:',
    ]
    for pattern in forbidden_secret_keys:
        require(not re.search(pattern, contract_text, re.I), "command contract appears to contain secret material key")

    emit("PASS", "password gate result future protected-action handling documented and no secret values exposed")


def check_future_verifier(data: dict[str, Any]) -> None:
    verifier = data.get("future_verifier")
    require(isinstance(verifier, dict), "future_verifier must be an object")
    require(
        verifier.get("path") == r"tools\verify_verifier_health_check_agent_manual_run_command_contract.py",
        "future verifier path mismatch",
    )
    require(verifier.get("status") == "future", "future verifier status must be future in the contract")
    blob = normalized_blob(verifier)
    require_terms(
        blob,
        "future verifier",
        [
            ("command contract exists", ["command contract exists"]),
            ("command not implemented", ["command is not implemented yet"]),
            ("route not added", ["route is not added yet"]),
            ("flags false", ["all now-enabled flags are false"]),
            ("password gate", ["password gate requirement"]),
            ("no mutation authority", ["no source route queue trusted-memory mutation authority"]),
            ("no provider/build/git authority", ["no provider network model local llm package build git authority"]),
        ],
    )
    emit("PASS", "future verifier result documented")


def is_excluded_path(path: Path) -> bool:
    parts = set(path.relative_to(ROOT).parts)
    if parts & EXCLUDED_DIRS:
        return True
    if path.parts[-2:] and "memory" in parts:
        # Memory files are documentation/contracts by policy for this scan,
        # except route metadata which is config-like and explicitly inspected.
        return path.name != "ROUTE_VERIFICATION_SET_V1.json"
    return False


def is_verifier_or_contract_context(path: Path) -> bool:
    rel_path = rel(path).replace("\\", "/")
    name = path.name.lower()
    if rel_path == "tools/verify_verifier_health_check_agent_manual_run_command_contract.py":
        return True
    if rel_path.startswith("tools/verify_"):
        return True
    if "contract" in name or "verifier" in name:
        return True
    return False


def is_expected_command_implementation_context(path: Path) -> bool:
    rel_path = rel(path).replace("\\", "/")
    implementation_verifier = ROOT / "tools" / "verify_verifier_health_check_agent_manual_run_command.py"
    return rel_path in {"engel_app.py", "memory/ROUTE_VERIFICATION_SET_V1.json"} and implementation_verifier.exists()


def iter_active_source_files() -> Iterable[Path]:
    for current_root, dirs, files in os.walk(ROOT):
        current = Path(current_root)
        dirs[:] = [name for name in dirs if name not in EXCLUDED_DIRS]
        for name in files:
            path = current / name
            if is_excluded_path(path):
                continue
            if path.suffix.lower() not in SOURCE_SUFFIXES:
                continue
            yield path


def check_active_source_scan() -> None:
    failures: list[str] = []
    safe_refs = 0
    scanned = 0
    for path in iter_active_source_files():
        try:
            data = path.read_bytes()
        except OSError:
            continue
        if b"\x00" in data:
            continue
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            continue
        scanned += 1
        for label, pattern in ACTIVE_PATTERNS:
            if not pattern.search(text):
                continue
            if is_verifier_or_contract_context(path) or is_expected_command_implementation_context(path):
                safe_refs += 1
                continue
            failures.append(f"{rel(path)}:{label}")

    emit("INFO", f"active source files scanned {scanned}")
    emit("INFO", f"safe verifier/contract references {safe_refs}")
    require(not failures, "active manual-run command implementation patterns found: " + "; ".join(failures[:20]))
    emit("PASS", "active source scan result no active command route/runtime behavior found")


def main() -> int:
    print("ENGEL_VERIFIER_HEALTH_CHECK_AGENT_MANUAL_RUN_COMMAND_CONTRACT_VERIFIER")
    print(f"ROOT {ROOT}")
    print("Mode: static command-contract verification only; no command, route, agent run, receipt, provider, model, or mutation")
    try:
        data, md_text, report_text = check_required_files()
        require(isinstance(data, dict), "command contract JSON must be an object")
        check_contract_values(data)
        check_future_gates(data)
        check_input_contract(data)
        check_output_contract(data)
        check_receipt_requirements(data)
        check_password_gate(data, md_text, report_text)
        check_future_verifier(data)
        check_active_source_scan()
    except CheckFailure as exc:
        emit("FAIL", str(exc))
        return 1
    except Exception as exc:  # pragma: no cover - defensive fail-closed path
        emit("FAIL", f"unexpected verifier error: {exc}")
        return 1

    emit("PASS", "contract check result")
    emit("PASS", "future gate result")
    emit("PASS", "input/output contract result")
    emit("PASS", "receipt requirement result")
    emit("PASS", "password gate result")
    emit("PASS", "active source scan result")
    print("VERIFIER_HEALTH_CHECK_AGENT_MANUAL_RUN_COMMAND_CONTRACT_VERIFICATION_PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
