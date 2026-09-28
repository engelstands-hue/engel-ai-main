#!/usr/bin/env python3
"""Verify the Verifier Health Check Agent manual-run command implementation.

This verifier is static/read-only. It does not invoke the command, prompt for a
password, activate the agent, run verifier commands through the agent, or create
runtime receipts.
"""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "engel_app.py"
COMMANDS = ROOT / "memory" / "ENGEL_COMMANDS.md"
ROUTES = ROOT / "memory" / "ROUTE_VERIFICATION_SET_V1.json"
CONTRACT = ROOT / "memory" / "ENGEL_VERIFIER_HEALTH_CHECK_AGENT_MANUAL_RUN_COMMAND_CONTRACT_V1.json"
MANUAL_RUN_CONTRACT = ROOT / "memory" / "ENGEL_VERIFIER_HEALTH_CHECK_AGENT_MANUAL_RUN_CONTRACT_V1.json"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_VERIFIER_HEALTH_CHECK_AGENT_MANUAL_RUN_COMMAND_V1.md"

COMMAND = "engel ai agent run verifier_health_check"
DRY_RUN_COMMAND = COMMAND + " --dry-run"
PROTECTED_ACTION_ID = "run_verifier_stack"
RECEIPT_ROOT = "reports\\agent_skill_runtime_receipts\\verifier_health_check\\"

EXPECTED_ALLOWLIST = [
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
    r"python .\tools\verify_debruijn_quantum_candidate_proposals.py",
    r"python .\tools\verify_debruijn_quantum_entanglement_groups.py",
    r"python .\tools\verify_debruijn_quantum_backend_status_consistency.py",
    r"python .\tools\verify_engel_debruijn_quantum_automation_file_structure.py",
    r"powershell -ExecutionPolicy Bypass -File .\scripts\codex_verify.ps1",
]

REQUIRED_RECEIPT_FIELDS = [
    "receipt_id",
    "agent_id",
    "command",
    "registry_entry_id",
    "activation_contract_id",
    "manual_run_contract_id",
    "command_contract_id",
    "started_at",
    "ended_at",
    "run_mode",
    "commands_requested",
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

FORBIDDEN_ALLOWLIST_NEEDLES = [
    "git ",
    "git\\",
    "pip ",
    "pip.exe",
    "python -m",
    "pyinstaller",
    "npm ",
    "winget ",
    "curl ",
    "http://",
    "https://",
    "ollama",
    "llama-server",
    "openai",
    "provider",
    "build ",
    "promote",
]

FORBIDDEN_FUNCTION_NEEDLES = [
    "shell=True",
    "Popen(",
    "requests.",
    "urllib.",
    "socket.",
    "webbrowser.",
    "os.system",
    "eval(",
    "exec(",
    "git add",
    "git commit",
    "pip install",
    "pyinstaller",
    "start_worker",
    "startup_hook",
    "schedule.",
]


class CheckFailure(Exception):
    pass


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def read_text(path: Path) -> str:
    if not path.exists():
        raise CheckFailure("missing required file: " + rel(path))
    return path.read_text(encoding="utf-8", errors="replace")


def load_json(path: Path) -> Any:
    return json.loads(read_text(path))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def emit(status: str, message: str) -> None:
    print(f"{status} {message}")


def normalize(text: str) -> str:
    return " ".join(text.lower().replace("\\", "/").replace("`", "").split())


def function_block(source: str, function_name: str) -> str:
    marker = "def " + function_name + "("
    start = source.find(marker)
    require(start >= 0, "missing function: " + function_name)
    next_match = re.search(r"\ndef [A-Za-z0-9_]+\(", source[start + 1 :])
    if next_match:
        return source[start : start + 1 + next_match.start()]
    return source[start:]


def check_required_files() -> tuple[str, dict[str, Any], dict[str, Any]]:
    source = read_text(APP)
    contract = load_json(CONTRACT)
    manual = load_json(MANUAL_RUN_CONTRACT)
    read_text(COMMANDS)
    load_json(ROUTES)
    emit("PASS", "required files present")
    return source, contract, manual


def check_contracts(contract: dict[str, Any], manual: dict[str, Any]) -> None:
    require(contract.get("contract_id") == "ENGEL_VERIFIER_HEALTH_CHECK_AGENT_MANUAL_RUN_COMMAND_CONTRACT_V1", "command contract id mismatch")
    require(contract.get("status") == "contract_only", "command contract must remain contract_only")
    require(contract.get("command_name") == COMMAND, "command contract command mismatch")
    require(manual.get("contract_id") == "ENGEL_VERIFIER_HEALTH_CHECK_AGENT_MANUAL_RUN_CONTRACT_V1", "manual-run contract id mismatch")
    allowlist = manual.get("verifier_command_allowlist")
    require(isinstance(allowlist, list), "manual-run allowlist missing")
    missing = [command for command in EXPECTED_ALLOWLIST if command not in allowlist]
    require(not missing, "manual-run contract allowlist missing: " + ", ".join(missing))
    limits = manual.get("runtime_limits", {})
    require(limits.get("max_total_runtime_seconds") <= 600, "max total runtime too high")
    require(limits.get("max_command_runtime_seconds") <= 120, "max command runtime too high")
    require(limits.get("max_output_bytes_per_command") <= 20000, "max output bytes too high")
    require(limits.get("max_commands_per_run") <= 25, "max command count too high")
    emit("PASS", "contract alignment result")


def check_route_source(source: str) -> None:
    block = function_block(source, "verifier_health_check_agent_manual_run_command_v1")
    handler = function_block(source, "handle_human_command_mode_cli")
    require("VERIFIER_HEALTH_CHECK_MANUAL_RUN_COMMAND_V1" in source, "missing command constant")
    require(COMMAND in source, "exact command string missing")
    require(DRY_RUN_COMMAND in source, "dry-run command string missing")
    require("verifier_health_check_agent_manual_run_command_v1(msg)" in handler, "command not wired into human command router")
    require('lower not in {VERIFIER_HEALTH_CHECK_MANUAL_RUN_COMMAND_V1, VERIFIER_HEALTH_CHECK_MANUAL_RUN_DRY_RUN_COMMAND_V1}' in block, "strict command parser missing")
    require("Unsupported agent manual-run command" in block, "unsupported agent run blocker missing")
    broad_dynamic_patterns = [
        r"agent_id\s*=\s*",
        r"candidate_id\s*=\s*msg",
        r"split\(\)\[[0-9]\]",
        r"startswith\(\"engel ai agent run \"\).*return\s+.*run",
    ]
    for pattern in broad_dynamic_patterns:
        require(not re.search(pattern, block, re.S), "potential wildcard agent-run parsing found: " + pattern)
    emit("PASS", "route exists exactly and wildcard agent-run route is blocked")


def check_password_gate(source: str) -> None:
    block = function_block(source, "verifier_health_check_agent_manual_run_command_v1")
    static_gate = function_block(source, "_verifier_health_check_static_gate_result_v1")
    require("prompt_and_require_action" in block, "real run does not prompt through password gate")
    require(PROTECTED_ACTION_ID in source, "protected action id missing")
    require("password_gate_status: pass (redacted)" in block, "redacted password gate success summary missing")
    require("no password requested in dry-run" in block, "dry-run password policy missing")
    require("password_hash" not in block and "salt" not in block, "command block references password secret fields")
    require("protected_action_gate_summary" in static_gate, "static gate summary missing")
    emit("PASS", "password gate result protected and redacted")


def check_allowlist(source: str) -> None:
    allowlist_block = source[source.find("VERIFIER_HEALTH_CHECK_ALLOWLIST_V1") : source.find("def _verifier_health_check_project_rel_v1")]
    require("VERIFIER_HEALTH_CHECK_ALLOWLIST_V1" in allowlist_block, "allowlist constant missing")
    for command in EXPECTED_ALLOWLIST:
        require(command in allowlist_block, "allowlist missing command: " + command)
    require(allowlist_block.count('"command":') == len(EXPECTED_ALLOWLIST), "allowlist command count mismatch")
    lowered = allowlist_block.lower()
    unsafe = [needle for needle in FORBIDDEN_ALLOWLIST_NEEDLES if needle in lowered]
    require(not unsafe, "unsafe command in allowlist: " + ", ".join(unsafe))
    require("*" not in allowlist_block and "$(" not in allowlist_block and "%*" not in allowlist_block, "allowlist contains wildcard/interpolation")
    emit("PASS", "fixed allowlist result")


def check_subprocess_safety(source: str) -> None:
    run_one = function_block(source, "_verifier_health_check_run_one_command_v1")
    run_all = function_block(source, "_verifier_health_check_run_allowlist_v1")
    require("subprocess.run(" in run_one, "subprocess.run missing")
    require("list(item[\"argv\"])" in run_one, "subprocess argv list missing")
    require("cwd=ROOT" in run_one, "subprocess cwd root missing")
    require("capture_output=True" in run_one, "subprocess capture_output missing")
    require("timeout=timeout" in run_one, "subprocess timeout missing")
    require("shell=True" not in run_one, "shell=True used in verifier health check command")
    require("Popen(" not in run_one, "Popen used in verifier health check command")
    require("VERIFIER_HEALTH_CHECK_MAX_TOTAL_RUNTIME_SECONDS_V1" in run_all, "total runtime limit missing")
    require("VERIFIER_HEALTH_CHECK_MAX_COMMAND_RUNTIME_SECONDS_V1 = 120" in source, "per-command timeout constant mismatch")
    require("VERIFIER_HEALTH_CHECK_MAX_OUTPUT_BYTES_PER_COMMAND_V1 = 20000" in source, "output byte limit mismatch")
    for needle in FORBIDDEN_FUNCTION_NEEDLES:
        require(needle not in run_one, "forbidden subprocess function needle: " + needle)
    emit("PASS", "subprocess safety result argv-only bounded local execution")


def check_receipt_behavior(source: str) -> None:
    receipt_block = function_block(source, "_verifier_health_check_write_receipt_v1")
    render_block = function_block(source, "_verifier_health_check_receipt_markdown_v1")
    dry_block = function_block(source, "verifier_health_check_agent_manual_run_command_v1")
    require("VERIFIER_HEALTH_CHECK_RECEIPT_ROOT_V1" in receipt_block, "fixed receipt root missing")
    require("verifier_health_check_manual_run_" in receipt_block, "receipt filename prefix missing")
    require("receipt_path.write_text" in receipt_block, "receipt write missing")
    require("receipt_written: no" in dry_block, "dry-run no-receipt statement missing")
    for field in REQUIRED_RECEIPT_FIELDS:
        require(field in receipt_block or field in render_block, "receipt missing required field: " + field)
    for phrase in [
        "no source files edited",
        "no routes mutated",
        "no queues mutated",
        "no trusted memory written",
        "no memory promoted",
        "no external AI/provider/network called",
        "no local LLM inference run",
        "no packages installed",
        "no build/promote/stage/commit",
        "no mobile-worker or remote-queen-worker runtime started",
        "no background worker/scheduler/startup hook created",
        "no generated proposals applied/trusted/promoted",
    ]:
        require(phrase in receipt_block, "receipt missing forbidden action confirmation: " + phrase)
    emit("PASS", "receipt behavior result fixed report-only receipt")


def check_docs_and_route_metadata() -> None:
    commands = read_text(COMMANDS)
    routes = load_json(ROUTES)
    normalized_commands = normalize(commands)
    for phrase in [
        COMMAND,
        DRY_RUN_COMMAND,
        "password-gated/manual-run-only",
        "fixed local verifier allowlist",
        "report-only receipt",
        "no arbitrary command/script/output override",
        "no autorun",
        "no source/route/queue/trusted-memory mutation",
    ]:
        require(normalize(phrase) in normalized_commands, "ENGEL_COMMANDS missing: " + phrase)

    entries = routes.get("route_regression_matrix_entries")
    require(isinstance(entries, list), "route matrix entries missing")
    matches = [entry for entry in entries if isinstance(entry, dict) and entry.get("command") == COMMAND]
    require(len(matches) == 1, "route metadata must contain exactly one manual-run command entry")
    entry = matches[0]
    for key in [
        "implemented_now",
        "approved_inactive_registry_required",
        "activation_contract_required",
        "manual_run_contract_required",
        "manual_run_command_contract_required",
        "fixed_allowlist_only",
        "receipt_only_output",
        "dry_run_supported",
        "no_arbitrary_command_input",
        "no_script_discovery",
        "no_autorun_enablement",
        "no_background_worker",
        "no_scheduler",
        "no_startup_load",
        "no_provider_call",
        "no_network_call",
        "no_local_llm_inference",
        "no_source_mutation",
        "no_route_mutation",
        "no_queue_mutation",
        "no_trusted_memory_write",
        "no_package_install",
        "no_git_stage_commit",
        "no_build_promote",
    ]:
        require(entry.get(key) is True, "route metadata flag must be true: " + key)
    require(entry.get("should_execute_in_test") is False, "route metadata should not execute protected command in generic tests")
    expectations = routes.get("verifier_health_check_agent_manual_run_command_expectations")
    require(isinstance(expectations, dict), "manual-run command expectations missing")
    require(expectations.get("receipt_root") == RECEIPT_ROOT, "expectation receipt root mismatch")
    require(expectations.get("password_gate_required_for_real_run") is True, "password gate expectation missing")
    emit("PASS", "docs and route metadata result")


def check_active_source_scan(source: str) -> None:
    function_names = [
        "verifier_health_check_agent_manual_run_command_v1",
        "_verifier_health_check_run_one_command_v1",
        "_verifier_health_check_run_allowlist_v1",
        "_verifier_health_check_write_receipt_v1",
    ]
    combined = "\n".join(function_block(source, name) for name in function_names)
    active_forbidden = [
        "start_worker",
        "startup_hook",
        "scheduler_enabled_now = True",
        "background_execution_enabled_now = True",
        "external_ai_enabled_now = True",
        "provider_api_enabled_now = True",
        "network_enabled_now = True",
        "local_llm_inference_enabled_now = True",
        "trusted_memory_write_enabled_now = True",
        "source_mutation_enabled_now = True",
        "route_mutation_enabled_now = True",
        "queue_mutation_enabled_now = True",
        "package_install_enabled_now = True",
        "build_promote_enabled_now = True",
        "write trusted memory",
        "git commit",
        "git add",
        "pip install",
    ]
    lowered = combined.lower()
    findings = [needle for needle in active_forbidden if needle.lower() in lowered]
    require(not findings, "active forbidden behavior found: " + ", ".join(findings))
    emit("PASS", "active source scan result no forbidden runtime expansion")


def check_verifier_source_static() -> None:
    tree = ast.parse(read_text(Path(__file__)))
    forbidden_imports = {"requests", "urllib", "socket", "webbrowser", "subprocess"}
    forbidden_calls = {"exec", "eval", "open"}
    forbidden_methods = {"write_text", "write_bytes", "unlink", "rename", "mkdir"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                require(alias.name.split(".")[0] not in forbidden_imports, "verifier imports forbidden module: " + alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            require(module.split(".")[0] not in forbidden_imports, "verifier imports forbidden module: " + module)
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                require(func.id not in forbidden_calls, "verifier calls forbidden function: " + func.id)
            if isinstance(func, ast.Attribute):
                require(func.attr not in forbidden_methods, "verifier calls forbidden method: " + func.attr)
    emit("PASS", "verifier source is static/read-only")


def main() -> int:
    print("ENGEL_VERIFIER_HEALTH_CHECK_AGENT_MANUAL_RUN_COMMAND_VERIFIER")
    print(f"ROOT {ROOT}")
    print("Mode: static implementation verification only; no command invocation, password prompt, agent run, or receipt write")
    try:
        source, contract, manual = check_required_files()
        check_contracts(contract, manual)
        check_route_source(source)
        check_password_gate(source)
        check_allowlist(source)
        check_subprocess_safety(source)
        check_receipt_behavior(source)
        check_docs_and_route_metadata()
        check_active_source_scan(source)
        check_verifier_source_static()
    except CheckFailure as exc:
        emit("FAIL", str(exc))
        return 1
    except Exception as exc:  # pragma: no cover - defensive fail-closed path
        emit("FAIL", "unexpected verifier error: " + type(exc).__name__ + ": " + str(exc))
        return 1

    emit("PASS", "command implementation result")
    emit("PASS", "password gate result")
    emit("PASS", "fixed allowlist result")
    emit("PASS", "subprocess safety result")
    emit("PASS", "receipt behavior result")
    emit("PASS", "route metadata/docs result")
    print("VERIFIER_HEALTH_CHECK_AGENT_MANUAL_RUN_COMMAND_VERIFICATION_PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
