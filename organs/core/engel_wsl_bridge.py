"""Safe Engel AI WSL bridge.

This module exposes explicit WSL command IDs for Engel AI. The original
status commands remain read-only/status-only. Phase B adds bounded Stage 3
action command IDs for the recorded Ubuntu distro; those command IDs are
still fixed allowlist entries, not free-form shell passthrough.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable


WINDOWS_ENGEL_PROJECT_PATH = r"D:\b.WorkSpace\Engel App"
WSL_ENGEL_PROJECT_PATH = "/mnt/d/b.WorkSpace/Engel App"
PREFERRED_UBUNTU_STORAGE_ROOT = r"D:\WSL\Ubuntu"
UBUNTU_DISTRO_NAME = "Ubuntu"

DEFAULT_TIMEOUT_SECONDS = 8
MAX_TIMEOUT_SECONDS = 120
MAX_OUTPUT_CHARS = 4000

BLOCKED_COMMAND_WORDS = {
    "sudo",
    "su",
    "curl",
    "wget",
    "ssh",
    "scp",
    "rsync",
    "rm",
    "rmdir",
    "del",
    "mv",
    "cp",
    "chmod",
    "chown",
    "mount",
    "umount",
    "systemctl",
    "service",
    "nohup",
    "setsid",
    "npx",
    "docker",
    "powershell",
    "cmd.exe",
    "explorer.exe",
}

STAGE3_PACKAGE_MANAGER_WORDS = {
    "apt",
    "apt-get",
    "snap",
    "pip",
    "pip3",
    "pipx",
    "uv",
    "cargo",
    "rustup",
    "npm",
    "pnpm",
    "yarn",
    "ollama",
    "llama",
}

BLOCKED_ARG_SEQUENCES = (
    ("python", "-m", "pip", "install"),
    ("python3", "-m", "pip", "install"),
    ("pip", "install"),
    ("pip3", "install"),
    ("npm", "install"),
)


@dataclass(frozen=True)
class BridgeCommand:
    command_id: str
    argv: tuple[str, ...]
    description: str
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
    read_only: bool = True
    mutates_files: bool = False
    requires_ubuntu: bool = False
    stage3_action: bool = False
    writes_engel_source: bool = False


@dataclass(frozen=True)
class CommandResult:
    command_id: str
    argv: tuple[str, ...]
    status: str
    returncode: int | None
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False
    error: str = ""
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS

    def as_dict(self) -> dict[str, Any]:
        return {
            "command_id": self.command_id,
            "argv": list(self.argv),
            "status": self.status,
            "returncode": self.returncode,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "timed_out": self.timed_out,
            "error": self.error,
            "timeout_seconds": self.timeout_seconds,
        }


Runner = Callable[..., subprocess.CompletedProcess[str]]


APPROVED_WSL_COMMANDS: dict[str, BridgeCommand] = {
    "wsl.status": BridgeCommand(
        command_id="wsl.status",
        argv=("wsl.exe", "--status"),
        description="Windows-side WSL status",
    ),
    "wsl.version": BridgeCommand(
        command_id="wsl.version",
        argv=("wsl.exe", "--version"),
        description="Windows-side WSL version",
    ),
    "wsl.distros": BridgeCommand(
        command_id="wsl.distros",
        argv=("wsl.exe", "-l", "-v"),
        description="Windows-side WSL distro list",
    ),
    "wsl.ubuntu.uname": BridgeCommand(
        command_id="wsl.ubuntu.uname",
        argv=("wsl.exe", "-d", UBUNTU_DISTRO_NAME, "--", "uname", "-a"),
        description="Ubuntu kernel/status check",
        requires_ubuntu=True,
    ),
    "wsl.ubuntu.pwd": BridgeCommand(
        command_id="wsl.ubuntu.pwd",
        argv=("wsl.exe", "-d", UBUNTU_DISTRO_NAME, "--", "pwd"),
        description="Ubuntu current directory check",
        requires_ubuntu=True,
    ),
    "wsl.ubuntu.python_version": BridgeCommand(
        command_id="wsl.ubuntu.python_version",
        argv=("wsl.exe", "-d", UBUNTU_DISTRO_NAME, "--", "python3", "--version"),
        description="Ubuntu python3 version check",
        requires_ubuntu=True,
    ),
    "wsl.ubuntu.node_version": BridgeCommand(
        command_id="wsl.ubuntu.node_version",
        argv=("wsl.exe", "-d", UBUNTU_DISTRO_NAME, "--", "node", "--version"),
        description="Ubuntu node version check",
        requires_ubuntu=True,
    ),
    "wsl.ubuntu.git_version": BridgeCommand(
        command_id="wsl.ubuntu.git_version",
        argv=("wsl.exe", "-d", UBUNTU_DISTRO_NAME, "--", "git", "--version"),
        description="Ubuntu git version check",
        requires_ubuntu=True,
    ),
    "wsl.ubuntu.engel_path_exists": BridgeCommand(
        command_id="wsl.ubuntu.engel_path_exists",
        argv=("wsl.exe", "-d", UBUNTU_DISTRO_NAME, "--", "test", "-d", WSL_ENGEL_PROJECT_PATH),
        description="Ubuntu can see the Engel project path",
        requires_ubuntu=True,
    ),
    "wsl.ubuntu.list_mnt_d_workspace": BridgeCommand(
        command_id="wsl.ubuntu.list_mnt_d_workspace",
        argv=("wsl.exe", "-d", UBUNTU_DISTRO_NAME, "--", "ls", "/mnt/d/b.WorkSpace"),
        description="Ubuntu can list the D drive workspace root",
        requires_ubuntu=True,
    ),
    "wsl.ubuntu.engel_evolution_lab_help": BridgeCommand(
        command_id="wsl.ubuntu.engel_evolution_lab_help",
        argv=("wsl.exe", "-d", UBUNTU_DISTRO_NAME, "--", "uv", "run", "engel_darwin", "--help"),
        description="Ubuntu prints Engel Evolution Lab help via upstream engel_darwin CLI - read-only, Stage 3 authorized",
        timeout_seconds=20,
        requires_ubuntu=True,
    ),
    "wsl.ubuntu.engel_knowledge_graph_help": BridgeCommand(
        command_id="wsl.ubuntu.engel_knowledge_graph_help",
        argv=("wsl.exe", "-d", UBUNTU_DISTRO_NAME, "--", "engel_graphify", "--help"),
        description="Ubuntu prints Engel Knowledge Graph help via upstream engel_graphify CLI - read-only, Stage 3 authorized",
        timeout_seconds=20,
        requires_ubuntu=True,
    ),
    "wsl.ubuntu.engel_evolution_engine_help": BridgeCommand(
        command_id="wsl.ubuntu.engel_evolution_engine_help",
        argv=("wsl.exe", "-d", UBUNTU_DISTRO_NAME, "--", "engel_evolver", "--help"),
        description="Ubuntu prints Engel Evolution Engine help via upstream engel_evolver CLI - read-only, Stage 3 authorized",
        timeout_seconds=20,
        requires_ubuntu=True,
    ),
    "wsl.ubuntu.engel_evolution_lab_run_example": BridgeCommand(
        command_id="wsl.ubuntu.engel_evolution_lab_run_example",
        argv=(
            "wsl.exe",
            "-d",
            UBUNTU_DISTRO_NAME,
            "--",
            "bash",
            "-lc",
            "set -e; mkdir -p /tmp/engel_phase_b/darwin_parrot /tmp/engel_phase_b/uv/engel_darwin; "
            "export UV_PROJECT_ENVIRONMENT=/tmp/engel_phase_b/uv/engel_darwin; "
            "cd '/mnt/d/b.WorkSpace/Engel App/engel_evolution_lab_main'; "
            "uv run engel_darwin parrot --num_iterations 1 --output_dir /tmp/engel_phase_b/darwin_parrot",
        ),
        description="Run the Engel Evolution Lab parrot example in WSL Ubuntu with output under /tmp/engel_phase_b",
        timeout_seconds=120,
        read_only=False,
        mutates_files=True,
        requires_ubuntu=True,
        stage3_action=True,
        writes_engel_source=False,
    ),
    "wsl.ubuntu.engel_knowledge_graph_build": BridgeCommand(
        command_id="wsl.ubuntu.engel_knowledge_graph_build",
        argv=(
            "wsl.exe",
            "-d",
            UBUNTU_DISTRO_NAME,
            "--",
            "bash",
            "-lc",
            "set -e; mkdir -p /tmp/engel_phase_b/graphify; "
            "export OLLAMA_BASE_URL=${OLLAMA_BASE_URL:-http://127.0.0.1:11434}; "
            "cd '/mnt/d/b.WorkSpace/Engel App/engel_knowledge_graph_main'; "
            "python3 -m engel_graphify extract engel_graphify --backend ollama --out /tmp/engel_phase_b/graphify --no-cluster",
        ),
        description="Run a bounded Engel Knowledge Graph extraction with output under /tmp/engel_phase_b",
        timeout_seconds=120,
        read_only=False,
        mutates_files=True,
        requires_ubuntu=True,
        stage3_action=True,
        writes_engel_source=False,
    ),
    "wsl.ubuntu.engel_evolution_engine_run": BridgeCommand(
        command_id="wsl.ubuntu.engel_evolution_engine_run",
        argv=(
            "wsl.exe",
            "-d",
            UBUNTU_DISTRO_NAME,
            "--",
            "bash",
            "-lc",
            "set -e; mkdir -p /tmp/engel_phase_b/evolver_run; "
            "cd /tmp/engel_phase_b/evolver_run; "
            "ENGEL_EVOLVER_REPO_ROOT=/tmp/engel_phase_b/evolver_run "
            "node '/mnt/d/b.WorkSpace/Engel App/engel_evolution_engine_main/index.js' run",
        ),
        description="Run Engel Evolution Engine once from the vendored source with runtime state under /tmp/engel_phase_b",
        timeout_seconds=120,
        read_only=False,
        mutates_files=True,
        requires_ubuntu=True,
        stage3_action=True,
        writes_engel_source=False,
    ),
}

INTERNAL_COMMAND_IDS = {
    "wsl.paths",
    "wsl.self_test",
}

CLI_COMMANDS = ("status", "distros", "tools", "paths", "self-test", "json")


def _clean_output(text: Any, *, limit: int = MAX_OUTPUT_CHARS) -> str:
    if isinstance(text, bytes):
        value = text.decode("utf-8", errors="replace")
    else:
        value = str(text or "")
    value = value.replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n")
    value = value.strip()
    if len(value) > limit:
        return value[:limit] + "\n[output truncated]"
    return value


def _safe_timeout(seconds: int | float | None) -> int:
    try:
        value = int(seconds if seconds is not None else DEFAULT_TIMEOUT_SECONDS)
    except (TypeError, ValueError):
        value = DEFAULT_TIMEOUT_SECONDS
    return max(1, min(value, MAX_TIMEOUT_SECONDS))


def _argv_has_blocked_sequence(argv: tuple[str, ...]) -> bool:
    lowered = tuple(part.casefold() for part in argv)
    for sequence in BLOCKED_ARG_SEQUENCES:
        size = len(sequence)
        for index in range(0, len(lowered) - size + 1):
            if lowered[index:index + size] == sequence:
                return True
    return False


def validate_approved_commands() -> list[str]:
    """Return validation errors for the fixed allowlist."""
    errors: list[str] = []
    for command_id, command in APPROVED_WSL_COMMANDS.items():
        if not command.argv:
            errors.append(command_id + " has no argv")
            continue
        if command.argv[0] != "wsl.exe":
            errors.append(command_id + " does not start with wsl.exe")
        if command.timeout_seconds > MAX_TIMEOUT_SECONDS:
            errors.append(command_id + " exceeds max timeout")
        if command.stage3_action:
            if command.read_only:
                errors.append(command_id + " is a Stage 3 action but is marked read-only")
            if not command.mutates_files:
                errors.append(command_id + " is a Stage 3 action but does not declare bounded mutation")
            if command.writes_engel_source:
                errors.append(command_id + " writes Engel source from WSL")
        elif not command.read_only or command.mutates_files:
            errors.append(command_id + " is not read-only")
        for arg in command.argv:
            token = str(arg).casefold()
            if token in BLOCKED_COMMAND_WORDS:
                errors.append(command_id + " contains blocked argv token: " + str(arg))
        if _argv_has_blocked_sequence(command.argv) and not command.stage3_action:
            errors.append(command_id + " contains blocked package-install argv sequence")
    return errors


def command_metadata(command_id: str) -> dict[str, Any]:
    command = APPROVED_WSL_COMMANDS.get(str(command_id or ""))
    if command is None:
        return {}
    return {
        "command_id": command.command_id,
        "argv": list(command.argv),
        "description": command.description,
        "timeout_seconds": command.timeout_seconds,
        "read_only": command.read_only,
        "mutates_files": command.mutates_files,
        "requires_ubuntu": command.requires_ubuntu,
        "stage3_action": command.stage3_action,
        "writes_engel_source": command.writes_engel_source,
    }


def run_command_id(command_id: str, *, runner: Runner | None = None) -> CommandResult:
    command = APPROVED_WSL_COMMANDS.get(str(command_id or ""))
    if command is None:
        return CommandResult(
            command_id=str(command_id or ""),
            argv=(),
            status="blocked",
            returncode=None,
            error="Command id is not in the Engel WSL bridge allowlist.",
        )
    validation_errors = validate_approved_commands()
    if validation_errors:
        return CommandResult(
            command_id=command.command_id,
            argv=command.argv,
            status="blocked",
            returncode=None,
            error="Allowlist validation failed: " + "; ".join(validation_errors),
            timeout_seconds=command.timeout_seconds,
        )
    timeout_seconds = _safe_timeout(command.timeout_seconds)
    run_fn = runner or subprocess.run
    try:
        completed = run_fn(
            list(command.argv),
            capture_output=True,
            text=True,
            check=False,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
        )
    except FileNotFoundError as exc:
        return CommandResult(
            command_id=command.command_id,
            argv=command.argv,
            status="missing",
            returncode=None,
            error=str(exc),
            timeout_seconds=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        return CommandResult(
            command_id=command.command_id,
            argv=command.argv,
            status="timeout",
            returncode=None,
            stdout=_clean_output(exc.stdout),
            stderr=_clean_output(exc.stderr),
            timed_out=True,
            error="Command timed out.",
            timeout_seconds=timeout_seconds,
        )
    except Exception as exc:
        return CommandResult(
            command_id=command.command_id,
            argv=command.argv,
            status="error",
            returncode=None,
            error=type(exc).__name__ + ": " + str(exc),
            timeout_seconds=timeout_seconds,
        )
    status = "pass" if completed.returncode == 0 else "warn"
    return CommandResult(
        command_id=command.command_id,
        argv=command.argv,
        status=status,
        returncode=completed.returncode,
        stdout=_clean_output(completed.stdout),
        stderr=_clean_output(completed.stderr),
        timeout_seconds=timeout_seconds,
    )


def _distro_names_from_output(output: str) -> list[str]:
    names: list[str] = []
    for line in _clean_output(output, limit=12000).splitlines():
        cleaned = line.replace("*", " ").strip()
        if not cleaned:
            continue
        if "NAME" in cleaned and "STATE" in cleaned and "VERSION" in cleaned:
            continue
        if cleaned.startswith("Windows Subsystem"):
            continue
        first = cleaned.split()[0]
        if first and first not in names:
            names.append(first)
    return names


def collect_wsl_status(*, runner: Runner | None = None) -> dict[str, Any]:
    status_result = run_command_id("wsl.status", runner=runner)
    version_result = run_command_id("wsl.version", runner=runner)
    distros_result = run_command_id("wsl.distros", runner=runner)
    distro_output = "\n".join([distros_result.stdout, distros_result.stderr])
    distro_names = _distro_names_from_output(distro_output)
    ubuntu_registered = UBUNTU_DISTRO_NAME in distro_names
    ubuntu_like = [name for name in distro_names if name.casefold().startswith("ubuntu")]
    wsl_available = any(
        result.status != "missing"
        for result in (status_result, version_result, distros_result)
    )
    wsl_usable = wsl_available and any(
        result.returncode == 0
        for result in (status_result, version_result, distros_result)
    )
    return {
        "wsl_executable": shutil.which("wsl.exe") or shutil.which("wsl") or "wsl.exe",
        "wsl_available": wsl_available,
        "wsl_usable": wsl_usable,
        "ubuntu_registered": ubuntu_registered,
        "ubuntu_like_distros": ubuntu_like,
        "distro_names": distro_names,
        "commands": {
            "wsl.status": status_result.as_dict(),
            "wsl.version": version_result.as_dict(),
            "wsl.distros": distros_result.as_dict(),
        },
    }


def collect_distro_status(*, runner: Runner | None = None) -> dict[str, Any]:
    status = collect_wsl_status(runner=runner)
    return {
        "wsl_available": status["wsl_available"],
        "ubuntu_registered": status["ubuntu_registered"],
        "ubuntu_like_distros": status["ubuntu_like_distros"],
        "distro_names": status["distro_names"],
        "commands": {
            "wsl.distros": status["commands"]["wsl.distros"],
            "wsl.version": status["commands"]["wsl.version"],
        },
    }


def collect_path_status(*, runner: Runner | None = None) -> dict[str, Any]:
    status = collect_wsl_status(runner=runner)
    ubuntu_storage_exists = Path(PREFERRED_UBUNTU_STORAGE_ROOT).exists()
    payload: dict[str, Any] = {
        "windows_engel_project_path": WINDOWS_ENGEL_PROJECT_PATH,
        "wsl_engel_project_path": WSL_ENGEL_PROJECT_PATH,
        "preferred_ubuntu_storage_root": PREFERRED_UBUNTU_STORAGE_ROOT,
        "preferred_ubuntu_storage_root_exists": ubuntu_storage_exists,
        "ubuntu_must_not_live_inside_engel_repo": True,
        "wsl_available": status["wsl_available"],
        "ubuntu_registered": status["ubuntu_registered"],
        "commands": {},
    }
    if status["ubuntu_registered"]:
        path_result = run_command_id("wsl.ubuntu.engel_path_exists", runner=runner)
        list_result = run_command_id("wsl.ubuntu.list_mnt_d_workspace", runner=runner)
        payload["ubuntu_can_see_engel_project"] = path_result.returncode == 0
        payload["commands"] = {
            "wsl.ubuntu.engel_path_exists": path_result.as_dict(),
            "wsl.ubuntu.list_mnt_d_workspace": list_result.as_dict(),
        }
    else:
        payload["ubuntu_can_see_engel_project"] = None
    return payload


def collect_tool_status(*, runner: Runner | None = None) -> dict[str, Any]:
    status = collect_wsl_status(runner=runner)
    payload: dict[str, Any] = {
        "wsl_available": status["wsl_available"],
        "ubuntu_registered": status["ubuntu_registered"],
        "commands": {},
        "warnings": [],
    }
    if not status["wsl_available"]:
        payload["warnings"].append(
            "WSL is not currently available on this machine. No install was attempted."
        )
        return payload
    if not status["ubuntu_registered"]:
        payload["warnings"].append(
            "WSL is available, but Ubuntu is not installed or not registered. No install was attempted."
        )
        return payload
    for command_id in (
        "wsl.ubuntu.uname",
        "wsl.ubuntu.python_version",
        "wsl.ubuntu.node_version",
        "wsl.ubuntu.git_version",
    ):
        result = run_command_id(command_id, runner=runner)
        payload["commands"][command_id] = result.as_dict()
        if result.returncode != 0:
            payload["warnings"].append(command_id + " did not pass; this is a readiness warning.")
    return payload


def collect_self_test(*, runner: Runner | None = None) -> dict[str, Any]:
    status = collect_wsl_status(runner=runner)
    paths = collect_path_status(runner=runner)
    tools = collect_tool_status(runner=runner)
    warnings: list[str] = []
    failures: list[str] = []
    if not status["wsl_available"]:
        warnings.append(
            "WSL is not currently available on this machine. Install Ubuntu manually or through an explicit approved install step. No install was attempted."
        )
    elif not status["ubuntu_registered"]:
        warnings.append(
            "WSL is available, but Ubuntu is not installed or not registered. No install was attempted."
        )
    if paths["preferred_ubuntu_storage_root_exists"] is False:
        warnings.append(
            "Preferred D:\\WSL\\Ubuntu storage folder is not present. This is informational only. No folder was created."
        )
    if status["ubuntu_registered"] and paths.get("ubuntu_can_see_engel_project") is False:
        failures.append("Ubuntu is registered but cannot see the Engel project path through /mnt/d.")
    warnings.extend(str(item) for item in tools.get("warnings", []))
    summary = "pass"
    if failures:
        summary = "fail"
    elif warnings:
        summary = "warn"
    return {
        "summary": summary,
        "warnings": warnings,
        "failures": failures,
        "status": status,
        "paths": paths,
        "tools": tools,
        "safety": bridge_safety_summary(),
    }


def bridge_safety_summary() -> dict[str, bool]:
    return {
        "local_only": True,
        "status_routes_read_only": True,
        "phase_b_stage3_actions_available": True,
        "allowlisted_commands_only": True,
        "timeout_bounded": True,
        "no_free_form_shell": True,
        "no_wsl_install": True,
        "no_ubuntu_import_unregister": True,
        "package_install_requires_fixed_stage3_command_id": True,
        "no_sudo": True,
        "no_hidden_background_worker": True,
        "no_provider_calls": True,
        "no_browser": True,
        "no_arbitrary_outbound_network": True,
        "no_memory_source_archive_mutation": True,
        "no_wsl_source_mutation": True,
    }


def _command_line(result: dict[str, Any]) -> str:
    argv = result.get("argv", [])
    return " ".join(str(part) for part in argv)


def _format_command_result(result: dict[str, Any]) -> list[str]:
    lines = [
        "- " + str(result.get("command_id", "")),
        "  argv: " + _command_line(result),
        "  status: " + str(result.get("status", "")),
        "  returncode: " + str(result.get("returncode")),
    ]
    stdout = str(result.get("stdout", "") or "")
    stderr = str(result.get("stderr", "") or "")
    error = str(result.get("error", "") or "")
    if stdout:
        lines.append("  stdout: " + stdout.replace("\n", " | "))
    if stderr:
        lines.append("  stderr: " + stderr.replace("\n", " | "))
    if error:
        lines.append("  error: " + error.replace("\n", " | "))
    return lines


def _safety_lines() -> list[str]:
    return [
        "Safety:",
        "- Local, explicit, allowlisted, and timeout-bounded.",
        "- Status routes remain read-only/status-only.",
        "- Phase B Stage 3 action routes are fixed command IDs only; no free-form shell passthrough.",
        "- No WSL install, Ubuntu import/unregister, sudo, browser spawn, provider call, arbitrary outbound network, trusted-memory write, Engel source mutation from WSL, archive migration/copy/sync/delete, or hidden startup action.",
        "- Runtime Dependency contract: ask 'wsl ubuntu runtime status' for the Stage 2/3 authorization boundary.",
    ]


def render_wsl_status(_payload: str = "", *, runner: Runner | None = None) -> str:
    payload = collect_wsl_status(runner=runner)
    lines = [
        "Engel WSL Bridge V1 - status",
        "",
        "WSL executable: " + str(payload["wsl_executable"]),
        "WSL available: " + ("yes" if payload["wsl_available"] else "no"),
        "WSL appears usable: " + ("yes" if payload["wsl_usable"] else "no"),
        "Ubuntu registered: " + ("yes" if payload["ubuntu_registered"] else "no"),
        "Distros detected: " + (", ".join(payload["distro_names"]) or "none"),
    ]
    if not payload["wsl_available"]:
        lines.extend(
            [
                "",
                "WSL is not currently available on this machine. Install Ubuntu manually or through an explicit approved install step. No install was attempted.",
            ]
        )
    elif not payload["ubuntu_registered"]:
        lines.extend(
            [
                "",
                "WSL is available, but Ubuntu is not installed or not registered. No install was attempted.",
            ]
        )
    lines.extend(["", "Command results:"])
    for result in payload["commands"].values():
        lines.extend(_format_command_result(result))
    lines.extend(["", *_safety_lines()])
    return "\n".join(lines)


def render_wsl_distros(_payload: str = "", *, runner: Runner | None = None) -> str:
    payload = collect_distro_status(runner=runner)
    lines = [
        "Engel WSL Bridge V1 - distros",
        "",
        "WSL available: " + ("yes" if payload["wsl_available"] else "no"),
        "Ubuntu registered: " + ("yes" if payload["ubuntu_registered"] else "no"),
        "Distros detected: " + (", ".join(payload["distro_names"]) or "none"),
    ]
    if not payload["wsl_available"]:
        lines.extend(["", "WSL is not currently available on this machine. No install was attempted."])
    elif not payload["ubuntu_registered"]:
        lines.extend(["", "WSL is available, but Ubuntu is not installed or not registered. No install was attempted."])
    lines.extend(["", "Command results:"])
    for result in payload["commands"].values():
        lines.extend(_format_command_result(result))
    lines.extend(["", *_safety_lines()])
    return "\n".join(lines)


def render_wsl_tools(_payload: str = "", *, runner: Runner | None = None) -> str:
    payload = collect_tool_status(runner=runner)
    lines = [
        "Engel WSL Bridge V1 - Linux tool readiness",
        "",
        "WSL available: " + ("yes" if payload["wsl_available"] else "no"),
        "Ubuntu registered: " + ("yes" if payload["ubuntu_registered"] else "no"),
    ]
    warnings = payload.get("warnings", [])
    if warnings:
        lines.extend(["", "Warnings:"])
        lines.extend("- " + str(warning) for warning in warnings)
    lines.extend(["", "Command results:"])
    commands = payload.get("commands", {})
    if commands:
        for result in commands.values():
            lines.extend(_format_command_result(result))
    else:
        lines.append("- No Ubuntu tool commands were run.")
    lines.extend(["", *_safety_lines()])
    return "\n".join(lines)


def render_wsl_paths(_payload: str = "", *, runner: Runner | None = None) -> str:
    payload = collect_path_status(runner=runner)
    lines = [
        "Engel WSL Bridge V1 - paths",
        "",
        "Windows Engel project path: " + payload["windows_engel_project_path"],
        "WSL Engel project path: " + payload["wsl_engel_project_path"],
        "Preferred Ubuntu storage root: " + payload["preferred_ubuntu_storage_root"],
        "Preferred Ubuntu storage root exists: " + ("yes" if payload["preferred_ubuntu_storage_root_exists"] else "no"),
        "Ubuntu must not be installed inside the Engel repo: yes",
        "Ubuntu can see Engel project: " + str(payload["ubuntu_can_see_engel_project"]),
    ]
    if not payload["preferred_ubuntu_storage_root_exists"]:
        lines.extend(
            [
                "",
                "Preferred D:\\WSL\\Ubuntu storage folder is not present. This is informational only. No folder was created.",
            ]
        )
    if not payload["wsl_available"]:
        lines.extend(["", "WSL is not currently available on this machine. No install was attempted."])
    elif not payload["ubuntu_registered"]:
        lines.extend(["", "WSL is available, but Ubuntu is not installed or not registered. No install was attempted."])
    lines.extend(["", "Command results:"])
    commands = payload.get("commands", {})
    if commands:
        for result in commands.values():
            lines.extend(_format_command_result(result))
    else:
        lines.append("- No Ubuntu path commands were run.")
    lines.extend(["", *_safety_lines()])
    return "\n".join(lines)


def render_wsl_self_test(_payload: str = "", *, runner: Runner | None = None) -> str:
    payload = collect_self_test(runner=runner)
    lines = [
        "Engel WSL Bridge V1 - self-test",
        "",
        "Summary: " + str(payload["summary"]).upper(),
    ]
    if payload["warnings"]:
        lines.extend(["", "Warnings:"])
        lines.extend("- " + str(warning) for warning in payload["warnings"])
    if payload["failures"]:
        lines.extend(["", "Failures:"])
        lines.extend("- " + str(failure) for failure in payload["failures"])
    lines.extend(
        [
            "",
            "Status:",
            "- WSL available: " + ("yes" if payload["status"]["wsl_available"] else "no"),
            "- WSL appears usable: " + ("yes" if payload["status"]["wsl_usable"] else "no"),
            "- Ubuntu registered: " + ("yes" if payload["status"]["ubuntu_registered"] else "no"),
            "- Preferred Ubuntu storage exists: " + ("yes" if payload["paths"]["preferred_ubuntu_storage_root_exists"] else "no"),
            "- Ubuntu can see Engel project: " + str(payload["paths"]["ubuntu_can_see_engel_project"]),
            "",
            *_safety_lines(),
        ]
    )
    return "\n".join(lines)


def collect_json_status(*, runner: Runner | None = None) -> dict[str, Any]:
    return {
        "bridge": "ENGEL_WSL_BRIDGE_V1",
        "paths": {
            "windows_engel_project_path": WINDOWS_ENGEL_PROJECT_PATH,
            "wsl_engel_project_path": WSL_ENGEL_PROJECT_PATH,
            "preferred_ubuntu_storage_root": PREFERRED_UBUNTU_STORAGE_ROOT,
        },
        "allowlist": {
            command_id: command_metadata(command_id)
            for command_id in sorted(APPROVED_WSL_COMMANDS)
        },
        "internal_command_ids": sorted(INTERNAL_COMMAND_IDS),
        "status": collect_wsl_status(runner=runner),
        "tool_status": collect_tool_status(runner=runner),
        "path_status": collect_path_status(runner=runner),
        "self_test": collect_self_test(runner=runner),
        "safety": bridge_safety_summary(),
    }


def render_json_status(*, runner: Runner | None = None) -> str:
    return json.dumps(collect_json_status(runner=runner), indent=2, sort_keys=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Safe read-only Engel WSL bridge for status and readiness checks."
    )
    subparsers = parser.add_subparsers(dest="command")
    for command in CLI_COMMANDS:
        subparsers.add_parser(command)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    command = args.command or "status"
    if command == "status":
        print(render_wsl_status())
        return 0
    if command == "distros":
        print(render_wsl_distros())
        return 0
    if command == "tools":
        print(render_wsl_tools())
        return 0
    if command == "paths":
        print(render_wsl_paths())
        return 0
    if command == "self-test":
        print(render_wsl_self_test())
        return 0
    if command == "json":
        print(render_json_status())
        return 0
    print("Unknown Engel WSL bridge command: " + str(command))
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
