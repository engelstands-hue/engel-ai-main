#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_JSON = ROOT / "memory" / "ENGEL_DEBRUIJN_QUANTUM_APPROVED_BUILD_SCRIPT_ALLOWLIST_CONTRACT_V1.json"
CONTRACT_MD = ROOT / "memory" / "ENGEL_DEBRUIJN_QUANTUM_APPROVED_BUILD_SCRIPT_ALLOWLIST_CONTRACT_V1.md"
REPORT_MD = ROOT / "reports" / "codex_bridge" / "ENGEL_DEBRUIJN_QUANTUM_APPROVED_BUILD_SCRIPT_ALLOWLIST_CONTRACT_V1.md"
PASS_MARKER = "DEBRUIJN_QUANTUM_APPROVED_BUILD_SCRIPT_ALLOWLIST_CONTRACT_VERIFICATION_PASS"

EXPECTED_COMMANDS = {
    "build_engel_main_exe": {
        "script_path": "scripts\\build_engel_main_exe.ps1",
        "spec_path": "Engel.spec",
        "expected_output_paths": ["build\\staging\\engel_main.exe"],
    },
    "build_engel_super_swarm_exe": {
        "script_path": "scripts\\build_engel_super_swarm_exe.ps1",
        "spec_path": "EngelSuperSwarmHive3D.spec",
        "expected_output_paths": ["build\\staging\\engel_super_swarm.exe"],
    },
    "build_approved_packaged_artifacts": {
        "script_path": "scripts\\build_approved_packaged_artifacts.ps1",
        "spec_path": None,
        "expected_output_paths": ["build\\staging\\engel_main.exe", "build\\staging\\engel_super_swarm.exe"],
    },
}

FALSE_FLAGS = [
    "build_execution_enabled_now",
    "approved_build_lane_execution_enabled_now",
    "pyinstaller_execution_enabled_now",
    "live_write_enabled_now",
    "dist_write_enabled_now",
    "backup_write_enabled_now",
    "promote_enabled_now",
    "git_stage_commit_enabled_now",
    "trusted_memory_write_enabled_now",
    "provider_api_enabled_now",
    "network_enabled_now",
    "local_llm_inference_enabled_now",
    "background_worker_enabled_now",
    "autorun_enabled_now",
    "scheduler_enabled_now",
    "startup_hook_enabled_now",
]

FORBIDDEN_SCRIPT_PATTERNS = [
    r"\bgit\s+add\b",
    r"\bgit\s+commit\b",
    r"\bgit\s+push\b",
    r"\bpip\s+install\b",
    r"\bnpm\s+install\b",
    r"Invoke-WebRequest",
    r"Start-BitsTransfer",
    r"curl\s+",
    r"wget\s+",
    r"trusted_memory",
    r"ENGEL_TRUSTED_MEMORY",
    r"password",
    r"salt",
    r"hash",
]


class Verifier:
    def __init__(self) -> None:
        self.failures: list[str] = []

    def pass_(self, message: str) -> None:
        print(f"PASS {message}")

    def fail(self, message: str) -> None:
        print(f"FAIL {message}")
        self.failures.append(message)

    def require(self, condition: bool, message: str) -> None:
        if condition:
            self.pass_(message)
        else:
            self.fail(message)


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path} did not contain a JSON object")
    return data


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("/", "\\")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def validate_contract(v: Verifier, data: dict[str, Any]) -> None:
    v.require(data.get("contract_id") == "ENGEL_DEBRUIJN_QUANTUM_APPROVED_BUILD_SCRIPT_ALLOWLIST_CONTRACT_V1", "contract_id matches")
    v.require(data.get("status") == "contract_static_allowlist_only", "status is contract_static_allowlist_only")
    v.require(data.get("active_workspace") == r"D:\b.WorkSpace\Engel App", "active workspace is bounded")
    v.require(data.get("build_lane_dependency") == "ENGEL_DEBRUIJN_QUANTUM_APPROVED_BUILD_LANE_CONTRACT_V1", "build lane dependency declared")
    flags = data.get("current_enabled_flags")
    v.require(isinstance(flags, dict), "current_enabled_flags object present")
    if isinstance(flags, dict):
        for flag in FALSE_FLAGS:
            v.require(flags.get(flag) is False, f"{flag} is false")

    scripts = data.get("allowed_build_scripts")
    v.require(isinstance(scripts, list) and len(scripts) == 3, "three allowed build scripts declared")
    by_command = {item.get("command_id"): item for item in scripts if isinstance(item, dict)}
    for command_id, expected in EXPECTED_COMMANDS.items():
        item = by_command.get(command_id)
        v.require(isinstance(item, dict), f"{command_id} allowlist entry present")
        if not isinstance(item, dict):
            continue
        v.require(item.get("script_path") == expected["script_path"], f"{command_id} script path exact")
        v.require(item.get("spec_path") == expected["spec_path"], f"{command_id} spec path exact")
        v.require(item.get("exact_arguments") == [], f"{command_id} takes no arguments")
        v.require(item.get("allowed_write_roots") == ["build\\staging\\"], f"{command_id} write root limited to build staging")
        v.require(item.get("expected_output_paths") == expected["expected_output_paths"], f"{command_id} expected outputs exact")
        v.require(item.get("forbidden_output_paths") == ["live\\", "dist\\", "backups\\"], f"{command_id} forbidden outputs exact")
        v.require(isinstance(item.get("required_pre_verifiers"), list) and item["required_pre_verifiers"], f"{command_id} pre-verifiers declared")
        v.require(isinstance(item.get("required_post_verifiers"), list) and item["required_post_verifiers"], f"{command_id} post-verifiers declared")

    forbidden = "\n".join(str(item).lower() for item in data.get("forbidden_behavior", []))
    for term in [
        "arbitrary command execution",
        "user-supplied shell command",
        "live write",
        "dist write",
        "backup write",
        "promotion",
        "git add",
        "git add .",
        "git add -a",
        "trusted-memory write",
        "password/salt/hash exposure",
    ]:
        v.require(term in forbidden, f"forbidden behavior includes {term}")


def validate_scripts(v: Verifier, data: dict[str, Any]) -> None:
    scripts = data.get("allowed_build_scripts") or []
    by_command = {item.get("command_id"): item for item in scripts if isinstance(item, dict)}
    for command_id, expected in EXPECTED_COMMANDS.items():
        item = by_command.get(command_id) or {}
        script_rel = item.get("script_path") or expected["script_path"]
        script_path = ROOT / script_rel
        v.require(script_path.exists(), f"{script_rel} exists")
        if not script_path.exists():
            continue
        text = read_text(script_path)
        lower = text.lower()
        v.require("$args.count -ne 0" in lower, f"{script_rel} rejects arguments")
        v.require("set-strictmode" in lower, f"{script_rel} uses strict mode")
        v.require("build\\staging" in lower, f"{script_rel} uses build staging")
        v.require("git add" not in lower and "git commit" not in lower, f"{script_rel} has no git staging/commit")
        v.require("pip install" not in lower and "npm install" not in lower, f"{script_rel} has no package install")
        v.require("invoke-webrequest" not in lower and "start-bitstransfer" not in lower, f"{script_rel} has no network download helper")
        if expected["spec_path"]:
            v.require(expected["spec_path"].lower() in lower, f"{script_rel} references exact spec")
            v.require("python -m pyinstaller" in lower, f"{script_rel} invokes PyInstaller only through python -m")
        for pattern in FORBIDDEN_SCRIPT_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                v.fail(f"{script_rel} contains forbidden pattern {pattern}")
        v.require(rel(script_path) == script_rel, f"{script_rel} remains inside workspace")


def main() -> int:
    v = Verifier()
    for path in [CONTRACT_JSON, CONTRACT_MD, REPORT_MD]:
        v.require(path.exists(), f"{rel(path)} exists")
    if not CONTRACT_JSON.exists():
        return 1
    try:
        data = load_json(CONTRACT_JSON)
        v.pass_("contract JSON parses")
    except Exception as exc:
        v.fail(f"contract JSON parse failed: {exc}")
        return 1

    validate_contract(v, data)
    validate_scripts(v, data)

    if v.failures:
        print(f"FAIL verification failed with {len(v.failures)} issue(s)")
        return 1
    print(PASS_MARKER)
    return 0


if __name__ == "__main__":
    sys.exit(main())
