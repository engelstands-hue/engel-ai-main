#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import os
import py_compile
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "engel_app.py"
SELF = Path(__file__).resolve()
COMMANDS_DOC = ROOT / "memory" / "ENGEL_COMMANDS.md"
ROUTE_MATRIX = ROOT / "memory" / "ROUTE_VERIFICATION_SET_V1.json"
STORAGE_ROOT = ROOT / "reports" / "agent_skill_candidates"
SCAFFOLD_VERIFIER = ROOT / "tools" / "verify_agent_skill_candidate_scaffold.py"
ROUTE_METADATA_VERIFIER = ROOT / "tools" / "verify_route_metadata_contract.py"

APPROVAL_PHRASE = "APPROVE_CREATE_AGENT_SKILL_CANDIDATE_SCAFFOLD_V1"

FALSE_FIELDS = [
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

EXECUTABLE_SUFFIXES = {
    ".py",
    ".ps1",
    ".bat",
    ".cmd",
    ".exe",
    ".dll",
    ".sh",
    ".pyd",
    ".pyc",
    ".zip",
}

EXCLUDE_DIRS = {
    ".git",
    "build",
    "dist",
    "__pycache__",
    ".venv",
    "venv",
    "node_modules",
}


class CheckFailure(Exception):
    pass


def rel(path: Path) -> str:
    try:
        return str(path.resolve(strict=False).relative_to(ROOT.resolve(strict=False))).replace("/", "\\")
    except ValueError:
        return str(path)


def print_result(label: str, status: str, detail: str = "") -> None:
    suffix = f" {detail}" if detail else ""
    print(f"{status} {label}{suffix}")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def compile_sources() -> None:
    for path in [APP, SELF]:
        require(path.exists(), f"missing source file: {rel(path)}")
        py_compile.compile(str(path), doraise=True)
        print_result("py_compile", "PASS", rel(path))


def import_engel_app() -> Any:
    root_text = str(ROOT)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)
    spec = importlib.util.spec_from_file_location("engel_app", APP)
    require(spec is not None and spec.loader is not None, "could not load engel_app spec")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    print_result("engel_app import", "PASS", "main guarded; no GUI launched")
    return module


def command_segment() -> str:
    source = read_text(APP)
    start = source.find("AGENT_SKILL_CANDIDATE_SCAFFOLD_APPROVAL_PHRASE_V1")
    end = source.find("def operator_manual_v2_summary", start)
    require(start >= 0 and end > start, "candidate scaffold command source segment not found")
    return source[start:end]


def check_static_source() -> None:
    source = read_text(APP)
    segment = command_segment()
    for needle in [
        "agent_skill_candidate_scaffold_command_v1",
        "engel ai candidate scaffold",
        "engel_agent_skill_candidate_scaffold",
        APPROVAL_PHRASE,
        "reports",
        "agent_skill_candidates",
        "candidate_only",
        "untrusted_candidate",
        "Scaffold verifier did not pass",
        "Agent/Skill Candidate Scaffold Help",
        "agent example",
        "skill example",
        "Approval phrase required",
        "Missing fields:",
        "Rejected fields:",
    ]:
        require(needle in source, f"engel_app missing command marker: {needle}")
    require(segment.count("(\"engel ai candidate scaffold\", None)") == 1, "command segment must preserve one route surface")
    for alias in [
        "\"create agent candidate\"",
        "\"create skill candidate\"",
        "\"agent skill candidate scaffold\"",
        "\"agent candidate draft\"",
        "\"skill candidate draft\"",
    ]:
        require(alias not in segment, f"command segment must not add alias route: {alias}")
    forbidden_calls = [
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
    ]
    hits = [needle for needle in forbidden_calls if needle in segment]
    require(not hits, f"command segment contains forbidden live/runtime calls: {hits}")
    for field in FALSE_FIELDS:
        true_pattern = re.compile(rf"['\"]?{re.escape(field)}['\"]?\s*[:=]\s*(?:True|true|\$true)\b")
        require(not true_pattern.search(segment), f"command segment sets {field} true")
    require("subprocess.run" in segment, "command segment should run scaffold verifier for persistent writes")
    print_result("command source markers", "PASS")
    print_result("command static safety", "PASS")


def storage_snapshot() -> list[str]:
    if not STORAGE_ROOT.exists():
        return []
    return sorted(rel(path) for path in STORAGE_ROOT.rglob("*"))


def live_registry_paths() -> list[Path]:
    paths: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        current = Path(dirpath)
        parts = {part.lower() for part in current.relative_to(ROOT).parts} if current != ROOT else set()
        dirnames[:] = [dirname for dirname in dirnames if dirname.lower() not in EXCLUDE_DIRS]
        if parts & EXCLUDE_DIRS:
            continue
        for filename in filenames:
            lower = filename.lower()
            if "registry" in lower and ("agent" in lower or "skill" in lower or "live" in lower):
                paths.append(current / filename)
    return sorted(paths)


def file_mtime_snapshot(paths: list[Path]) -> dict[str, float]:
    snapshot: dict[str, float] = {}
    for path in paths:
        if path.exists():
            snapshot[rel(path)] = path.stat().st_mtime
    return snapshot


def check_no_executable_files_in_candidate_storage() -> None:
    require(STORAGE_ROOT.exists() and STORAGE_ROOT.is_dir(), "candidate storage root missing")
    for path in STORAGE_ROOT.rglob("*"):
        if path.is_file() and path.suffix.lower() in EXECUTABLE_SUFFIXES:
            raise CheckFailure(f"executable file in candidate storage: {rel(path)}")
    print_result("candidate storage executable scan", "PASS")


def assert_blocked(text: str, reason: str) -> None:
    lower = text.lower()
    require("blocked" in lower, reason + " should be blocked")
    require("files created: none" in lower, reason + " should create no files")
    require("runtime enabled: no" in lower, reason + " should keep runtime disabled")
    require("trusted-memory write: no" in lower, reason + " should keep trusted memory disabled")


def assert_discovery(text: str, reason: str) -> None:
    lower = text.lower()
    require("agent/skill candidate scaffold help" in lower, reason + " should show help")
    require("approval phrase" in lower, reason + " should mention approval")
    require("files created: none" in lower, reason + " should create no files")
    require("candidate-only" in lower, reason + " should state candidate-only")
    require("untrusted" in lower, reason + " should state untrusted")
    require("runtime off" in lower, reason + " should state runtime OFF")
    require("autorun off" in lower, reason + " should state autorun OFF")
    require("trusted-memory write off" in lower, reason + " should state trusted-memory OFF")
    require("external ai off" in lower, reason + " should state external AI OFF")
    require("human review required" in lower, reason + " should state human review required")


def validate_temp_candidate_json(path: Path, expected_type: str) -> None:
    data = json.loads(read_text(path))
    require(data.get("candidate_type") == expected_type, f"{rel(path)} candidate_type mismatch")
    require(data.get("status") == "candidate_only", f"{rel(path)} status must be candidate_only")
    require(data.get("trust_status") == "untrusted_candidate", f"{rel(path)} trust_status must be untrusted_candidate")
    for field in FALSE_FIELDS:
        require(data.get(field) is False, f"{rel(path)} {field} must be false")
    if expected_type == "skill":
        require(data.get("install_enabled") is False, f"{rel(path)} install_enabled must be false")
    if expected_type == "agent":
        require(data.get("collaboration_room_allowed") is False, f"{rel(path)} collaboration_room_allowed must be false")


def run_command_behavior_checks(app: Any) -> None:
    before_storage = storage_snapshot()
    registry_paths = live_registry_paths()
    before_registry = file_mtime_snapshot(registry_paths)

    for command, reason, expected_terms in [
        ("engel ai candidate scaffold", "bare discovery", ["agent example:", "skill example:"]),
        ("engel ai candidate scaffold help", "help discovery", ["agent example:", "skill example:"]),
        ("engel ai candidate scaffold examples", "examples discovery", ["agent example:", "skill example:"]),
        ("engel ai candidate scaffold agent example", "agent example discovery", ["agent example:"]),
        ("engel ai candidate scaffold skill example", "skill example discovery", ["skill example:"]),
    ]:
        output = app.agent_skill_candidate_scaffold_command_v1(command)
        assert_discovery(output, reason)
        lower = output.lower()
        for term in expected_terms:
            require(term in lower, reason + " missing expected example term: " + term)

    missing_approval = app.agent_skill_candidate_scaffold_command_v1(
        'engel ai candidate scaffold type=agent id=cmd_missing_approval name="No Approval" purpose="No approval test."'
    )
    assert_blocked(missing_approval, "missing approval")
    require(APPROVAL_PHRASE in missing_approval, "missing approval response must include approval phrase")
    require("Corrected command:" in missing_approval, "missing approval response must include corrected command")
    require("cmd_missing_approval" in missing_approval, "missing approval response must preserve candidate id in corrected command")

    missing_fields = app.agent_skill_candidate_scaffold_command_v1(
        f'engel ai candidate scaffold {APPROVAL_PHRASE} type=agent id=cmd_missing_fields'
    )
    assert_blocked(missing_fields, "missing required fields")
    require("Missing fields:" in missing_fields, "missing fields response must list missing fields")
    require("name=<name>" in missing_fields, "missing fields response must list missing name")
    require("purpose=<purpose>" in missing_fields, "missing fields response must list missing purpose")

    invalid_id = app.agent_skill_candidate_scaffold_command_v1(
        f'engel ai candidate scaffold {APPROVAL_PHRASE} type=agent id=../bad name="Bad ID" purpose="Bad id test."'
    )
    assert_blocked(invalid_id, "invalid candidate id")

    dangerous_flag = app.agent_skill_candidate_scaffold_command_v1(
        f'engel ai candidate scaffold {APPROVAL_PHRASE} type=agent id=cmd_bad_flag name="Bad Flag" purpose="Bad flag test." runtime_enabled=true'
    )
    assert_blocked(dangerous_flag, "dangerous true flag")
    require("Rejected fields:" in dangerous_flag, "dangerous flag response must list rejected fields")
    require("runtime_enabled" in dangerous_flag, "dangerous flag response must name runtime_enabled")
    for field in FALSE_FIELDS:
        require(field in dangerous_flag, f"dangerous flag response must list forbidden field: {field}")

    reports_root = ROOT / "reports"
    with tempfile.TemporaryDirectory(prefix="agent_skill_candidate_command_selftest_", dir=str(reports_root)) as temp_name:
        temp_root = Path(temp_name)
        temp_storage = temp_root / "agent_skill_candidates"
        temp_receipts = temp_root / "codex_bridge"
        agent_result = app.agent_skill_candidate_scaffold_command_v1(
            f'engel ai candidate scaffold {APPROVAL_PHRASE} type=agent id=cmd_selftest_agent name="Command Selftest Agent" purpose="Verifier-only temporary candidate scaffold"',
            storage_root=temp_storage,
            receipt_root=temp_receipts,
            approved_storage_roots=(temp_storage,),
            run_verifier=False,
        )
        skill_result = app.agent_skill_candidate_scaffold_command_v1(
            f'engel ai candidate scaffold {APPROVAL_PHRASE} type=skill id=cmd_selftest_skill skill_name="Command Selftest Skill" description="Verifier-only temporary skill scaffold"',
            storage_root=temp_storage,
            receipt_root=temp_receipts,
            approved_storage_roots=(temp_storage,),
            run_verifier=False,
        )
        for output, expected_id, expected_type in [
            (agent_result, "cmd_selftest_agent", "agent"),
            (skill_result, "cmd_selftest_skill", "skill"),
        ]:
            lower = output.lower()
            require("agent/skill candidate scaffold created" in lower, "temp command should create scaffold")
            require("candidate_only" in lower and "untrusted_candidate" in lower, "temp command output must state candidate boundary")
            require("runtime_enabled: false" in lower, "temp command output must state runtime false")
            require("trusted_memory_write_allowed: false" in lower, "temp command output must state trusted-memory false")
            json_path = temp_storage / f"{expected_id}.{expected_type}.json"
            md_path = temp_storage / f"{expected_id}.{expected_type}.md"
            receipt_path = temp_receipts / f"ENGEL_AGENT_SKILL_CANDIDATE_SCAFFOLD_{expected_id}.md"
            require(json_path.exists(), f"missing temp JSON: {json_path}")
            require(md_path.exists(), f"missing temp Markdown: {md_path}")
            require(receipt_path.exists(), f"missing temp receipt: {receipt_path}")
            validate_temp_candidate_json(json_path, expected_type)
            receipt = read_text(receipt_path).lower()
            require("not live" in receipt and "not installed" in receipt and "not runnable" in receipt, "receipt missing inactive safety terms")

    after_storage = storage_snapshot()
    after_registry = file_mtime_snapshot(registry_paths)
    require(after_storage == before_storage, "command verifier modified actual candidate storage")
    require(after_registry == before_registry, "command verifier modified live registry-like files")
    print_result("command refusal checks", "PASS")
    print_result("temp command write checks", "PASS")
    print_result("actual candidate storage unchanged", "PASS")
    print_result("live registry modification check", "PASS", str(len(registry_paths)))


def check_docs_and_route_metadata() -> None:
    commands = read_text(COMMANDS_DOC)
    matrix = json.loads(read_text(ROUTE_MATRIX))
    for needle in [
        "engel ai candidate scaffold",
        "engel ai candidate scaffold help",
        "agent example",
        "skill example",
        APPROVAL_PHRASE,
        "candidate_only",
        "untrusted_candidate",
    ]:
        require(needle in commands, f"ENGEL_COMMANDS missing {needle}")
    entries = matrix.get("route_regression_matrix_entries", [])
    require(isinstance(entries, list), "route_regression_matrix_entries must be a list")
    by_command = {entry.get("command"): entry for entry in entries if isinstance(entry, dict)}
    required_commands = [
        "engel ai candidate scaffold APPROVE_CREATE_AGENT_SKILL_CANDIDATE_SCAFFOLD_V1 type=<agent|skill> id=<candidate_id> name_or_skill_name=<name> purpose_or_description=<text>",
    ]
    for command in required_commands:
        entry = by_command.get(command)
        require(isinstance(entry, dict), f"route matrix missing command: {command}")
        require(entry.get("approval_token") == APPROVAL_PHRASE, f"route matrix approval token mismatch: {command}")
        require(entry.get("implemented_now") is True, f"route matrix should mark implemented: {command}")
        require(entry.get("should_execute_in_test") is False, f"persistent candidate route must not execute in broad tests: {command}")
        require(entry.get("candidate_only") is True, f"route matrix missing candidate_only true: {command}")
        require(entry.get("untrusted_candidate") is True, f"route matrix missing untrusted_candidate true: {command}")
        for field in [
            "no_live_registration",
            "no_runtime_enablement",
            "no_autorun_enablement",
            "no_provider_call",
            "no_network_call",
            "no_queue_mutation",
            "no_route_mutation",
            "no_trusted_memory_write",
        ]:
            require(entry.get(field) is True, f"route matrix missing {field}: {command}")
    expectations = matrix.get("agent_skill_candidate_scaffold_command_expectations")
    require(isinstance(expectations, dict), "route matrix missing agent_skill_candidate_scaffold_command_expectations")
    require(expectations.get("approval_phrase_required") == APPROVAL_PHRASE, "expectations approval phrase mismatch")
    require(expectations.get("runtime_enabled") is False, "expectations runtime must be false")
    require(expectations.get("autorun_enabled") is False, "expectations autorun must be false")
    require(expectations.get("trusted_memory_write_enabled") is False, "expectations trusted memory must be false")
    print_result("command docs alignment", "PASS")
    print_result("route metadata alignment", "PASS")


def run_required_verifier(path: Path, pass_marker: str, label: str) -> None:
    result = subprocess.run(
        [sys.executable, str(path)],
        cwd=str(ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    require(result.returncode == 0, label + " failed:\n" + result.stdout)
    require(pass_marker in result.stdout, label + " pass marker missing")
    print_result(label, "PASS")


def main() -> int:
    failures: list[str] = []
    print("ENGEL_AGENT_SKILL_CANDIDATE_SCAFFOLD_COMMAND_VERIFIER")
    print(f"ROOT {ROOT}")
    print("Mode: local static/temp-route verification only; no persistent candidate, live agent/skill, provider, model, trusted-memory, build, or package behavior")
    try:
        compile_sources()
        check_static_source()
        app = import_engel_app()
        require(hasattr(app, "agent_skill_candidate_scaffold_command_v1"), "command handler missing")
        check_no_executable_files_in_candidate_storage()
        run_command_behavior_checks(app)
        check_docs_and_route_metadata()
        run_required_verifier(SCAFFOLD_VERIFIER, "AGENT_SKILL_CANDIDATE_SCAFFOLD_VERIFICATION_PASS", "scaffold verifier")
        run_required_verifier(ROUTE_METADATA_VERIFIER, "ROUTE_METADATA_CONTRACT_VERIFICATION_PASS", "route metadata verifier")
    except (CheckFailure, py_compile.PyCompileError, SyntaxError, json.JSONDecodeError, OSError, subprocess.SubprocessError) as exc:
        failures.append(str(exc))

    if failures:
        print_result("agent/skill candidate scaffold command checks", "FAIL", f"failures={len(failures)}")
        for failure in failures:
            print_result("agent/skill candidate scaffold command check", "FAIL", failure)
        print("AGENT_SKILL_CANDIDATE_SCAFFOLD_COMMAND_VERIFICATION_FAIL")
        return 1

    print_result("command source compile checks", "PASS")
    print_result("approval/refusal checks", "PASS")
    print_result("temp command self-test", "PASS")
    print_result("candidate storage persistence check", "PASS")
    print_result("route metadata/docs checks", "PASS")
    print("AGENT_SKILL_CANDIDATE_SCAFFOLD_COMMAND_VERIFICATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
