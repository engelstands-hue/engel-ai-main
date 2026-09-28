from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
WORKER_ID = "android_worker_alpha"
WORKER_NAME = "Android Worker Alpha"
JOB_ID = "20260516T201324Z_android_worker_alpha_summarize_text_summarize_engel_remote_worke"
PHONE_ROOT = "/sdcard/EngelRemoteWorker/android_worker_alpha"
PHONE_PARENT = "/sdcard/EngelRemoteWorker"
REMOTE_JOB_PACKET = PHONE_ROOT + "/jobs/" + JOB_ID + ".json"
REMOTE_INPUT_FILE = PHONE_ROOT + "/reports/codex_bridge/ENGEL_MULTI_ANDROID_REMOTE_WORKERS_PROTOCOL_V1.md"
REMOTE_ASSIGNED_INPUT_FILE = PHONE_ROOT + "/inbox/assigned_inputs/" + JOB_ID + "/engel_multi_android_remote_worke.md"
REMOTE_FINISH_RUNNER = PHONE_ROOT + "/finish_alpha_job.py"

ALPHA_PACKAGE = ROOT / "remote_workers" / WORKER_ID
JOB_PACKET = ALPHA_PACKAGE / "jobs" / (JOB_ID + ".json")
INPUT_FILE = ROOT / "reports" / "codex_bridge" / "ENGEL_MULTI_ANDROID_REMOTE_WORKERS_PROTOCOL_V1.md"
ASSIGNED_INPUT_FILE = ALPHA_PACKAGE / "inbox" / "assigned_inputs" / JOB_ID / "engel_multi_android_remote_worke.md"
SETUP_RECEIPTS = ROOT / "reports" / "android_remote_worker_setup"
RUN_ATTEMPTS = ROOT / "reports" / "android_remote_worker_run_attempts"
KNOWN_USER_ANDROID_SDK = Path(r"C:\Users\ziese\AppData\Local\Android\Sdk")
KNOWN_USER_ADB = KNOWN_USER_ANDROID_SDK / "platform-tools" / "adb.exe"

PHONE_DIRS = [
    PHONE_ROOT + "/config",
    PHONE_ROOT + "/jobs",
    PHONE_ROOT + "/inbox",
    PHONE_ROOT + "/outbox",
    PHONE_ROOT + "/logs",
    PHONE_ROOT + "/receipts",
    PHONE_ROOT + "/status",
    PHONE_ROOT + "/reports/codex_bridge",
]

PHONE_BUTTON_DIRS = [
    PHONE_ROOT + "/config",
    PHONE_ROOT + "/inbox",
    PHONE_ROOT + "/inbox/queen_choices",
    PHONE_ROOT + "/shortcuts",
    PHONE_ROOT + "/termux_widget_shortcuts",
]

PHONE_BUTTON_UI_FILES = [
    ("start_remote_worker_ui.py", ALPHA_PACKAGE / "start_remote_worker_ui.py", PHONE_ROOT + "/start_remote_worker_ui.py"),
    ("remote_worker_phone_ui.py", ALPHA_PACKAGE / "remote_worker_phone_ui.py", PHONE_ROOT + "/remote_worker_phone_ui.py"),
    ("start_worker_ui.sh", ALPHA_PACKAGE / "start_worker_ui.sh", PHONE_ROOT + "/start_worker_ui.sh"),
    ("README_PHONE_BUTTON_SETUP.md", ALPHA_PACKAGE / "README_PHONE_BUTTON_SETUP.md", PHONE_ROOT + "/README_PHONE_BUTTON_SETUP.md"),
    (
        "communication_queen_choices.py",
        ALPHA_PACKAGE / "communication_queen_choices.py",
        PHONE_ROOT + "/communication_queen_choices.py",
    ),
    ("queen_choice_bridge.py", ALPHA_PACKAGE / "queen_choice_bridge.py", PHONE_ROOT + "/queen_choice_bridge.py"),
    (
        "queen_choice_policy.json",
        ALPHA_PACKAGE / "config" / "queen_choice_policy.json",
        PHONE_ROOT + "/config/queen_choice_policy.json",
    ),
    (
        "preapproved_worker_actions.json",
        ALPHA_PACKAGE / "config" / "preapproved_worker_actions.json",
        PHONE_ROOT + "/config/preapproved_worker_actions.json",
    ),
    (
        "EngelWorkerAlphaUI",
        ALPHA_PACKAGE / "termux_widget_shortcuts" / "EngelWorkerAlphaUI",
        PHONE_ROOT + "/termux_widget_shortcuts/EngelWorkerAlphaUI",
    ),
]

FINISH_RUNNER_FILES = [
    ("finish_alpha_job.py", ALPHA_PACKAGE / "finish_alpha_job.py", PHONE_ROOT + "/finish_alpha_job.py"),
    ("remote_worker_runner.py", ALPHA_PACKAGE / "remote_worker_runner.py", PHONE_ROOT + "/remote_worker_runner.py"),
    ("remote_worker_local_executor.py", ALPHA_PACKAGE / "remote_worker_local_executor.py", PHONE_ROOT + "/remote_worker_local_executor.py"),
    ("engel_multi_android_remote_worke.md", ASSIGNED_INPUT_FILE, REMOTE_ASSIGNED_INPUT_FILE),
]

PULL_FOLDERS = {
    "status": (PHONE_ROOT + "/status", ALPHA_PACKAGE / "status"),
    "outbox": (PHONE_ROOT + "/outbox", ALPHA_PACKAGE / "outbox"),
    "logs": (PHONE_ROOT + "/logs", ALPHA_PACKAGE / "logs"),
    "receipts": (PHONE_ROOT + "/receipts", ALPHA_PACKAGE / "receipts"),
}

ACK_FLAG = "--i-understand-this-uses-adb"
RUN_ACK_FLAG = "--i-approve-run-worker-on-phone"
FINISH_ACK_FLAG = "--i-approve-finish-alpha-worker"


class AndroidSetupError(RuntimeError):
    pass


def now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def receipt_stamp() -> str:
    return datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("/", "\\")
    except ValueError:
        return str(path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def quote_part(part: str) -> str:
    if not part:
        return '""'
    is_windows_absolute_path = len(part) > 2 and part[1] == ":" and part[2] in {"\\", "/"}
    if is_windows_absolute_path or any(ch.isspace() for ch in part) or '"' in part:
        return '"' + part.replace('"', '\\"') + '"'
    return part


def command_text(parts: list[str]) -> str:
    return " ".join(quote_part(part) for part in parts)


def adb_names() -> list[str]:
    return ["adb.exe", "adb"]


def adb_candidates() -> list[tuple[Path, str]]:
    candidates: list[tuple[Path, str]] = []
    for folder in os.environ.get("PATH", "").split(os.pathsep):
        if folder:
            for name in adb_names():
                candidates.append((Path(folder) / name, "PATH"))
    for env_name in ["ANDROID_HOME", "ANDROID_SDK_ROOT"]:
        env_value = os.environ.get(env_name)
        if env_value:
            for name in adb_names():
                candidates.append((Path(env_value) / "platform-tools" / name, env_name))
    candidates.append((KNOWN_USER_ADB, "known_user_sdk_path"))
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        candidates.append((Path(local_app_data) / "Android" / "Sdk" / "platform-tools" / "adb.exe", "LOCALAPPDATA_fallback"))
    return candidates


def validate_adb_override(adb_path: str) -> Path:
    candidate = Path(adb_path).expanduser()
    if candidate.name.lower() != "adb.exe":
        raise AndroidSetupError("--adb-path must point to a file named adb.exe")
    try:
        if not candidate.exists() or not candidate.is_file():
            raise AndroidSetupError("--adb-path does not exist or is not a file: " + str(candidate))
    except OSError as exc:
        raise AndroidSetupError("--adb-path could not be checked: " + str(exc)) from exc
    if candidate.parent.name.lower() != "platform-tools":
        raise AndroidSetupError("--adb-path must be an Android SDK platform-tools adb.exe path")
    return candidate


def discover_adb(explicit_adb_path: str | None = None) -> dict[str, Any]:
    if explicit_adb_path:
        candidate = validate_adb_override(explicit_adb_path)
        return {
            "found": True,
            "path": str(candidate),
            "source": "explicit_user_override",
            "display_executable": str(candidate),
            "error": "",
        }
    for candidate, source in adb_candidates():
        try:
            if candidate.exists() and candidate.is_file():
                return {
                    "found": True,
                    "path": str(candidate),
                    "source": source,
                    "display_executable": "adb" if source == "PATH" else str(candidate),
                    "error": "",
                }
        except OSError:
            continue
    return {
        "found": False,
        "path": "",
        "source": "not_found",
        "display_executable": "adb",
        "error": "adb was not found on PATH, ANDROID_HOME, ANDROID_SDK_ROOT, known user SDK path, or LOCALAPPDATA fallback",
    }


def find_adb(explicit_adb_path: str | None = None) -> Path | None:
    discovered = discover_adb(explicit_adb_path)
    if discovered["found"]:
        return Path(str(discovered["path"]))
    return None


def adb_base(
    device_id: str | None = None,
    explicit_adb_path: str | None = None,
    *,
    display: bool = False,
) -> list[str]:
    discovered = discover_adb(explicit_adb_path)
    if discovered["found"]:
        executable = str(discovered["display_executable"] if display else discovered["path"])
    else:
        executable = "adb"
    base = [executable]
    if device_id:
        base.extend(["-s", device_id])
    return base


def validate_local_sources() -> dict[str, Any]:
    problems: list[str] = []
    for path in [ALPHA_PACKAGE, JOB_PACKET, INPUT_FILE]:
        if not path.exists():
            problems.append("missing: " + rel(path))
    job: dict[str, Any] = {}
    if JOB_PACKET.exists():
        try:
            data = json.loads(JOB_PACKET.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                job = data
        except json.JSONDecodeError:
            problems.append("job packet is not valid JSON")
    expected = {
        "assigned_worker_id": WORKER_ID,
        "job_type": "summarize_text",
        "job_template": False,
        "real_job": True,
        "status": "prepared_for_manual_transfer",
        "created_by": "engel",
        "routed_by": "communication_queen",
        "manual_transfer_required": True,
        "offline_only": True,
        "on_device_autonomy_allowed": True,
        "autonomy_scope": "assigned_job_sandbox_only",
        "trusted_memory_write": False,
        "source_mutation": False,
        "route_mutation": False,
        "patch_apply": False,
        "provider_network": False,
        "model_runtime": False,
        "requires_human_review": True,
    }
    for key, value in expected.items():
        if job.get(key) != value:
            problems.append(f"job packet field mismatch: {key}")
    for forbidden in ["completed", "returned_to_engel", "trusted", "promoted", "applied"]:
        if job.get("status") == forbidden or job.get("assignment_status") == forbidden:
            problems.append("job packet has forbidden completion/trust status: " + forbidden)
    return {
        "worker_package": rel(ALPHA_PACKAGE),
        "job_packet": rel(JOB_PACKET),
        "input_file": rel(INPUT_FILE),
        "job_id": job.get("job_id", JOB_ID),
        "local_sources_ready": not problems,
        "problems": problems,
        "input_sha256": sha256_file(INPUT_FILE) if INPUT_FILE.exists() else "",
        "job_sha256": sha256_file(JOB_PACKET) if JOB_PACKET.exists() else "",
    }


def validate_phone_button_ui_sources() -> dict[str, Any]:
    problems: list[str] = []
    files: list[dict[str, str]] = []
    for label, local_path, remote_path in PHONE_BUTTON_UI_FILES:
        if not local_path.exists() or not local_path.is_file():
            problems.append("missing phone UI file: " + rel(local_path))
        files.append({"label": label, "local_path": rel(local_path), "remote_path": remote_path})
    return {
        "phone_button_ui_sources_ready": not problems,
        "files": files,
        "problems": problems,
        "no_fake_status_result_progress": True,
        "no_worker_execution_during_push": True,
    }


def validate_finish_runner_sources() -> dict[str, Any]:
    problems: list[str] = []
    files: list[dict[str, str]] = []
    for label, local_path, remote_path in FINISH_RUNNER_FILES:
        if not local_path.exists() or not local_path.is_file():
            problems.append("missing finish runner file: " + rel(local_path))
        files.append({"label": label, "local_path": rel(local_path), "remote_path": remote_path})
    return {
        "finish_runner_sources_ready": not problems,
        "files": files,
        "problems": problems,
        "no_worker_execution_during_push": True,
        "no_fake_results": True,
    }


def parse_devices(raw: str) -> list[dict[str, str]]:
    devices: list[dict[str, str]] = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.lower().startswith("list of devices"):
            continue
        parts = stripped.split()
        if len(parts) >= 2:
            devices.append({"serial": parts[0], "state": parts[1]})
    return devices


def run_command(parts: list[str], timeout: int = 60) -> dict[str, Any]:
    completed = subprocess.run(parts, capture_output=True, text=True, timeout=timeout, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return {
        "command": command_text(parts),
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def adb_shell_command(device_id: str | None, shell_command: str, explicit_adb_path: str | None = None, *, display: bool = False) -> list[str]:
    return adb_base(device_id, explicit_adb_path, display=display) + ["shell", shell_command]


def run_adb_shell(device_id: str, shell_command: str, explicit_adb_path: str | None = None, timeout: int = 60) -> dict[str, Any]:
    return run_command(adb_shell_command(device_id, shell_command, explicit_adb_path), timeout=timeout)


def adb_devices(run_adb_check: bool = True, explicit_adb_path: str | None = None) -> dict[str, Any]:
    discovered = discover_adb(explicit_adb_path)
    command = adb_base(explicit_adb_path=explicit_adb_path) + ["devices"]
    if not run_adb_check:
        return {
            "adb_found": bool(discovered["found"]),
            "adb_path": str(discovered["path"]),
            "adb_discovery_source": str(discovered["source"]),
            "command": command_text(command),
            "command_run": False,
            "devices": [],
            "authorized_devices": [],
            "raw_output": "",
            "error": str(discovered["error"]),
        }
    if not discovered["found"]:
        return {
            "adb_found": False,
            "adb_path": "",
            "adb_discovery_source": "not_found",
            "command": command_text(command),
            "command_run": False,
            "devices": [],
            "authorized_devices": [],
            "raw_output": "",
            "error": str(discovered["error"]),
        }
    try:
        result = run_command(command, timeout=20)
    except (OSError, subprocess.SubprocessError) as exc:
        return {
            "adb_found": True,
            "adb_path": str(discovered["path"]),
            "adb_discovery_source": str(discovered["source"]),
            "command": command_text(command),
            "command_run": True,
            "devices": [],
            "authorized_devices": [],
            "raw_output": "",
            "error": str(exc),
        }
    raw = str(result.get("stdout", "")) + str(result.get("stderr", ""))
    devices = parse_devices(raw)
    authorized = [device for device in devices if device.get("state") == "device"]
    return {
        "adb_found": True,
        "adb_path": str(discovered["path"]),
        "adb_discovery_source": str(discovered["source"]),
        "command": command_text(command),
        "command_run": True,
        "returncode": result.get("returncode"),
        "devices": devices,
        "authorized_devices": authorized,
        "raw_output": raw,
        "error": "" if result.get("returncode") == 0 else "adb devices returned non-zero",
    }


def select_device(device_id: str | None, devices_payload: dict[str, Any]) -> str:
    authorized = devices_payload.get("authorized_devices", [])
    if device_id:
        for device in authorized:
            if isinstance(device, dict) and device.get("serial") == device_id:
                return device_id
        raise AndroidSetupError("requested device id is not listed as authorized by adb devices")
    if len(authorized) != 1:
        raise AndroidSetupError("expected exactly one authorized Android device; actual authorized count: " + str(len(authorized)))
    device = authorized[0]
    if not isinstance(device, dict) or not device.get("serial"):
        raise AndroidSetupError("authorized device list is malformed")
    return str(device["serial"])


def selected_authorized_device(device_id: str | None = None, explicit_adb_path: str | None = None) -> tuple[str, dict[str, Any]]:
    devices_payload = adb_devices(run_adb_check=True, explicit_adb_path=explicit_adb_path)
    return select_device(device_id, devices_payload), devices_payload


def phone_path_exists(device_id: str, remote_path: str, explicit_adb_path: str | None = None, kind: str = "e") -> bool:
    result = run_adb_shell(device_id, f"test -{kind} {remote_path}", explicit_adb_path=explicit_adb_path, timeout=20)
    return result.get("returncode") == 0


def phone_artifact_status(device_id: str, explicit_adb_path: str | None = None) -> dict[str, Any]:
    returned_counts: dict[str, int] = {}
    returned_files: dict[str, list[str]] = {}
    for label, (remote_folder, _local_folder) in PULL_FOLDERS.items():
        names = remote_names(device_id, remote_folder, explicit_adb_path)
        returned_files[label] = names
        returned_counts[label] = len(names)
    return {
        "worker_folder_exists": phone_path_exists(device_id, PHONE_ROOT, explicit_adb_path, kind="d"),
        "job_packet_exists": phone_path_exists(device_id, REMOTE_JOB_PACKET, explicit_adb_path, kind="f"),
        "input_file_exists": phone_path_exists(device_id, REMOTE_INPUT_FILE, explicit_adb_path, kind="f"),
        "assigned_input_file_exists": phone_path_exists(device_id, REMOTE_ASSIGNED_INPUT_FILE, explicit_adb_path, kind="f"),
        "returned_file_counts": returned_counts,
        "returned_files": returned_files,
        "real_returned_files_present": any(count > 0 for count in returned_counts.values()),
    }


def python_checks(device_id: str, explicit_adb_path: str | None = None) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    for executable in ["python", "python3"]:
        result = run_adb_shell(device_id, executable + " --version", explicit_adb_path=explicit_adb_path, timeout=20)
        output = (str(result.get("stdout", "")) + str(result.get("stderr", ""))).strip()
        checks.append(
            {
                "python_command": executable,
                "available": result.get("returncode") == 0 and "Python" in output,
                "returncode": result.get("returncode"),
                "output": output,
                "command": result.get("command"),
            }
        )
    available = [check for check in checks if check["available"]]
    return {
        "python_available": bool(available),
        "preferred_python": str(available[0]["python_command"]) if available else "",
        "checks": checks,
        "no_install_performed": True,
        "no_worker_execution": True,
    }


def termux_check(device_id: str, explicit_adb_path: str | None = None) -> dict[str, Any]:
    result = run_adb_shell(device_id, "pm list packages", explicit_adb_path=explicit_adb_path, timeout=30)
    packages: list[str] = []
    for line in str(result.get("stdout", "")).splitlines():
        item = line.strip()
        if item.startswith("package:"):
            packages.append(item.split(":", 1)[1])
    termux_packages = [package for package in packages if "termux" in package.lower()]
    return {
        "termux_detected": bool(termux_packages),
        "termux_packages": termux_packages,
        "package_count": len(packages),
        "command": result.get("command"),
        "returncode": result.get("returncode"),
        "error": str(result.get("stderr", "")).strip(),
        "no_install_performed": True,
        "no_worker_execution": True,
    }


def mkdir_commands(device_id: str | None = None, explicit_adb_path: str | None = None, *, display: bool = False) -> list[list[str]]:
    return [adb_base(device_id, explicit_adb_path, display=display) + ["shell", "mkdir", "-p", *PHONE_DIRS]]


def push_commands(device_id: str | None = None, explicit_adb_path: str | None = None, *, display: bool = False) -> list[list[str]]:
    return [
        adb_base(device_id, explicit_adb_path, display=display) + ["push", str(ALPHA_PACKAGE), PHONE_PARENT + "/"],
        adb_base(device_id, explicit_adb_path, display=display) + ["push", str(JOB_PACKET), PHONE_ROOT + "/jobs/"],
        adb_base(device_id, explicit_adb_path, display=display) + ["push", str(INPUT_FILE), PHONE_ROOT + "/reports/codex_bridge/"],
    ]


def phone_button_mkdir_commands(device_id: str | None = None, explicit_adb_path: str | None = None, *, display: bool = False) -> list[list[str]]:
    return [adb_base(device_id, explicit_adb_path, display=display) + ["shell", "mkdir", "-p", *PHONE_BUTTON_DIRS]]


def phone_button_push_commands(device_id: str | None = None, explicit_adb_path: str | None = None, *, display: bool = False) -> list[list[str]]:
    commands: list[list[str]] = []
    for _label, local_path, remote_path in PHONE_BUTTON_UI_FILES:
        commands.append(adb_base(device_id, explicit_adb_path, display=display) + ["push", str(local_path), remote_path])
    return commands


def finish_runner_push_commands(device_id: str | None = None, explicit_adb_path: str | None = None, *, display: bool = False) -> list[list[str]]:
    commands: list[list[str]] = []
    for _label, local_path, remote_path in FINISH_RUNNER_FILES:
        commands.append(adb_base(device_id, explicit_adb_path, display=display) + ["push", str(local_path), remote_path])
    return commands


def finish_runner_mkdir_commands(device_id: str | None = None, explicit_adb_path: str | None = None, *, display: bool = False) -> list[list[str]]:
    return [
        adb_base(device_id, explicit_adb_path, display=display)
        + ["shell", "mkdir", "-p", PHONE_ROOT + "/inbox/assigned_inputs/" + JOB_ID]
    ]


def optional_manual_run_command(device_id: str | None = None, explicit_adb_path: str | None = None, *, display: bool = False) -> list[str]:
    return adb_base(device_id, explicit_adb_path, display=display) + ["shell", "cd " + PHONE_ROOT + " && python run_assigned_job.py"]


def one_line_termux_finish_command() -> str:
    shared = "/sdcard/EngelRemoteWorker/android_worker_alpha"
    home = "~/engel_remote_worker_alpha"
    return (
        "mkdir -p " + home
        + " && cp -r " + shared + "/* " + home + "/ 2>/dev/null; "
        + "cd " + home
        + " && python finish_alpha_job.py"
        + " && mkdir -p " + shared + "/status " + shared + "/outbox " + shared + "/logs " + shared + "/receipts"
        + " && cp -r status/* " + shared + "/status/ 2>/dev/null; "
        + "cp -r outbox/* " + shared + "/outbox/ 2>/dev/null; "
        + "cp -r logs/* " + shared + "/logs/ 2>/dev/null; "
        + "cp -r receipts/* " + shared + "/receipts/ 2>/dev/null"
    )


def prepare_command_lines(explicit_adb_path: str | None = None) -> list[str]:
    lines = [
        "# Android Worker Alpha ADB setup commands",
        "# These are setup/transfer commands only. Do not run the optional manual job command until you are ready on-device.",
        command_text(adb_base(explicit_adb_path=explicit_adb_path, display=True) + ["devices"]),
    ]
    lines.extend(command_text(command) for command in mkdir_commands(explicit_adb_path=explicit_adb_path, display=True))
    lines.extend(command_text(command) for command in push_commands(explicit_adb_path=explicit_adb_path, display=True))
    lines.extend(
        [
            "",
            "# Optional later manual run command. Not executed by --push.",
            "# Android must already have a human-installed Python-capable environment such as Termux.",
            command_text(optional_manual_run_command(explicit_adb_path=explicit_adb_path, display=True)),
            "",
            "# Optional later pull after the worker actually ran on-device.",
            command_text(adb_base(explicit_adb_path=explicit_adb_path, display=True) + ["shell", "ls", "-1", PHONE_ROOT + "/status"]),
            command_text(adb_base(explicit_adb_path=explicit_adb_path, display=True) + ["pull", PHONE_ROOT + "/status/<real-status-file>", str(ALPHA_PACKAGE / "status")]),
        ]
    )
    return lines


def prepare_run_command_lines(explicit_adb_path: str | None = None) -> list[str]:
    return [
        "# Android Worker Alpha on-device run preparation",
        "# These commands are for review only. Nothing in --prepare-run-command is executed.",
        "# The ADB shell run only works when python or python3 is available in the normal ADB shell context.",
        command_text(adb_base(explicit_adb_path=explicit_adb_path, display=True) + ["devices"]),
        command_text(adb_shell_command(None, "python --version", explicit_adb_path, display=True)),
        command_text(adb_shell_command(None, "python3 --version", explicit_adb_path, display=True)),
        command_text(adb_shell_command(None, "pm list packages", explicit_adb_path, display=True)),
        command_text(adb_shell_command(None, "test -d " + PHONE_ROOT + " && echo WORKER_FOLDER_OK", explicit_adb_path, display=True)),
        command_text(adb_shell_command(None, "test -f " + REMOTE_JOB_PACKET + " && echo JOB_PACKET_OK", explicit_adb_path, display=True)),
        command_text(adb_shell_command(None, "test -f " + REMOTE_INPUT_FILE + " && echo INPUT_FILE_OK", explicit_adb_path, display=True)),
        "",
        "# Optional later approved run command. Do not run until explicitly approved.",
        command_text(adb_shell_command(None, "cd " + PHONE_ROOT + " && python run_assigned_job.py", explicit_adb_path, display=True)),
        command_text(adb_shell_command(None, "cd " + PHONE_ROOT + " && python3 run_assigned_job.py", explicit_adb_path, display=True)),
        "",
        "# If Python is unavailable through ADB shell, run manually inside Termux after human setup:",
        "cd /sdcard/EngelRemoteWorker/android_worker_alpha",
        "cd ~/storage/shared/EngelRemoteWorker/android_worker_alpha",
        "python run_worker_status.py",
        "python run_assigned_job.py",
    ]


def prepare_phone_button_command_lines(explicit_adb_path: str | None = None) -> list[str]:
    lines = [
        "# Android Worker Alpha phone button UI commands",
        "# These commands are for review only. Nothing in --prepare-phone-button-commands is executed.",
        "# The phone button opens the Remote Worker UI only; it does not run during push.",
        command_text(adb_base(explicit_adb_path=explicit_adb_path, display=True) + ["devices"]),
    ]
    lines.extend(command_text(command) for command in phone_button_mkdir_commands(explicit_adb_path=explicit_adb_path, display=True))
    lines.extend(command_text(command) for command in phone_button_push_commands(explicit_adb_path=explicit_adb_path, display=True))
    lines.extend(
        [
            "",
            "# Check pushed UI files without running the UI or worker.",
            command_text(adb_shell_command(None, "test -f " + PHONE_ROOT + "/start_remote_worker_ui.py && echo PHONE_UI_START_OK", explicit_adb_path, display=True)),
            command_text(adb_shell_command(None, "test -f " + PHONE_ROOT + "/remote_worker_phone_ui.py && echo PHONE_UI_MAIN_OK", explicit_adb_path, display=True)),
            command_text(adb_shell_command(None, "test -f " + PHONE_ROOT + "/termux_widget_shortcuts/EngelWorkerAlphaUI && echo PHONE_UI_WIDGET_TEMPLATE_OK", explicit_adb_path, display=True)),
            "",
            "# Manual Termux launch after human setup:",
            "cd ~/storage/shared/EngelRemoteWorker/android_worker_alpha",
            "python start_remote_worker_ui.py",
            "",
            "# Direct shared-storage launch if available:",
            "cd /sdcard/EngelRemoteWorker/android_worker_alpha",
            "python start_remote_worker_ui.py",
            "",
            "# Optional Termux:Widget button setup is manual. Copy the shortcut template from:",
            PHONE_ROOT + "/termux_widget_shortcuts/EngelWorkerAlphaUI",
            "# into the Termux:Widget shortcuts folder documented by Termux.",
        ]
    )
    return lines


def prepare_one_line_termux_finish_lines() -> list[str]:
    return [
        "# Android Worker Alpha one-line Termux finish command",
        "# Paste this exact line into Termux if ADB shell Python is unavailable.",
        "# It copies the shared worker package into ~/engel_remote_worker_alpha, runs finish_alpha_job.py once,",
        "# then copies real status/outbox/log/receipt files back to shared storage for ADB pull.",
        "# It does not install packages, download files, run models, write trusted memory, or apply patches.",
        one_line_termux_finish_command(),
    ]


def collect_status(run_adb_check: bool = True, explicit_adb_path: str | None = None) -> dict[str, Any]:
    local = validate_local_sources()
    adb = adb_devices(run_adb_check=run_adb_check, explicit_adb_path=explicit_adb_path)
    phone: dict[str, Any] = {
        "checked": False,
        "worker_folder_exists": False,
        "job_packet_exists": False,
        "input_file_exists": False,
        "assigned_input_file_exists": False,
        "returned_file_counts": {},
        "real_returned_files_present": False,
        "note": "phone artifact checks require exactly one authorized device and adb status check",
    }
    if run_adb_check and adb.get("adb_found") and len(adb.get("authorized_devices", [])) == 1:
        selected = str(adb["authorized_devices"][0]["serial"])
        phone = phone_artifact_status(selected, explicit_adb_path)
        phone["checked"] = True
        phone["device_id"] = selected
    can_push = bool(local["local_sources_ready"] and adb.get("adb_found") and len(adb.get("authorized_devices", [])) == 1)
    return {
        "setup_name": "Android Studio Setup for First Real Android Remote Worker V1",
        "worker_id": WORKER_ID,
        "worker_name": WORKER_NAME,
        "phone_target_folder": PHONE_ROOT,
        "connection_mode": "bounded_adb_file_transfer_after_human_approval",
        "local_sources": local,
        "adb": adb,
        "phone": phone,
        "can_push_with_explicit_ack": can_push,
        "push_requires_flag": ACK_FLAG,
        "boundaries": {
            "setup_transfer_only": True,
            "no_worker_execution_during_push": True,
            "no_fake_results": True,
            "no_phone_control_loop": True,
            "no_termux_install_automation": True,
            "no_package_install_automation": True,
            "no_hermes_ollama_llama_cpp": True,
            "no_model_runtime": True,
            "no_network_server": True,
            "no_ssh": True,
            "no_cloud_sync": True,
            "no_adb_wireless": True,
            "no_background_worker": True,
            "no_startup_autorun": True,
            "no_trusted_memory_write": True,
            "no_patch_apply": True,
        },
    }


def render_status(payload: dict[str, Any]) -> str:
    local = payload["local_sources"]
    adb = payload["adb"]
    phone = payload.get("phone", {})
    lines = [
        "Android Studio Setup for First Real Android Remote Worker V1",
        "",
        f"Worker: {payload['worker_name']} ({payload['worker_id']})",
        f"Phone target folder: {payload['phone_target_folder']}",
        f"Worker package: {local['worker_package']}",
        f"Job packet: {local['job_packet']}",
        f"Input file: {local['input_file']}",
        f"Local sources ready: {local['local_sources_ready']}",
        f"ADB found: {adb['adb_found']}",
        f"ADB path: {adb.get('adb_path') or '(not found)'}",
        f"ADB discovery source: {adb.get('adb_discovery_source') or '(not found)'}",
        f"ADB command: {adb.get('command')}",
        f"ADB command run: {adb.get('command_run')}",
        f"Authorized device count: {len(adb.get('authorized_devices', []))}",
        f"Can push with explicit ack: {payload['can_push_with_explicit_ack']}",
        f"Phone artifact checks run: {phone.get('checked')}",
        f"Phone worker folder exists: {phone.get('worker_folder_exists')}",
        f"Phone job packet exists: {phone.get('job_packet_exists')}",
        f"Phone input file exists: {phone.get('input_file_exists')}",
        f"Phone assigned input file exists: {phone.get('assigned_input_file_exists')}",
        f"Phone returned files present: {phone.get('real_returned_files_present')}",
        "",
        "Devices:",
    ]
    devices = adb.get("devices", [])
    if devices:
        for device in devices:
            lines.append(f"- {device.get('serial')}: {device.get('state')}")
    else:
        lines.append("- (none reported)")
    if local["problems"]:
        lines.extend(["", "Local source problems:"])
        lines.extend("- " + problem for problem in local["problems"])
    if adb.get("error"):
        lines.extend(["", "ADB note:", "- " + str(adb["error"])])
    if phone.get("checked"):
        lines.extend(["", "Phone returned file counts:"])
        counts = phone.get("returned_file_counts", {})
        if isinstance(counts, dict):
            for label in ["status", "outbox", "logs", "receipts"]:
                lines.append(f"- {label}: {counts.get(label, 0)}")
    lines.extend(
        [
            "",
            "Safety:",
            "- ADB is a bounded setup/file-transfer bridge only.",
            "- --push requires --i-understand-this-uses-adb and does not run the worker job.",
            "- --pull-results copies only real returned files if they exist; it does not fake missing results.",
            "- No Termux/app/package/model install automation, Hermes/Ollama/llama.cpp path, network server, SSH, cloud sync, ADB wireless, background worker, startup autorun, trusted-memory write, or patch apply is enabled.",
        ]
    )
    return "\n".join(lines) + "\n"


def collect_python_check(device_id: str | None = None, explicit_adb_path: str | None = None) -> dict[str, Any]:
    selected, devices_payload = selected_authorized_device(device_id, explicit_adb_path)
    return {
        "check_name": "Android Worker Alpha ADB Python availability check",
        "device_id": selected,
        "adb": devices_payload,
        "python": python_checks(selected, explicit_adb_path),
        "no_install_performed": True,
        "no_worker_execution": True,
    }


def render_python_check(payload: dict[str, Any]) -> str:
    python_payload = payload["python"]
    lines = [
        "Android Worker Alpha ADB Python availability check",
        "",
        f"Device: {payload['device_id']}",
        f"Python available in ADB shell: {python_payload['python_available']}",
        f"Preferred Python command: {python_payload.get('preferred_python') or '(none)'}",
        "Checks:",
    ]
    for check in python_payload.get("checks", []):
        lines.append(
            f"- {check.get('python_command')}: available={check.get('available')} returncode={check.get('returncode')} output={check.get('output') or '(empty)'}"
        )
    lines.extend(
        [
            "",
            "Safety:",
            "- This check does not install Python or Termux.",
            "- This check does not run Android Worker Alpha.",
        ]
    )
    return "\n".join(lines) + "\n"


def collect_termux_check(device_id: str | None = None, explicit_adb_path: str | None = None) -> dict[str, Any]:
    selected, devices_payload = selected_authorized_device(device_id, explicit_adb_path)
    return {
        "check_name": "Android Worker Alpha ADB Termux package check",
        "device_id": selected,
        "adb": devices_payload,
        "termux": termux_check(selected, explicit_adb_path),
        "no_install_performed": True,
        "no_worker_execution": True,
    }


def render_termux_check(payload: dict[str, Any]) -> str:
    termux = payload["termux"]
    packages = termux.get("termux_packages", [])
    lines = [
        "Android Worker Alpha ADB Termux package check",
        "",
        f"Device: {payload['device_id']}",
        f"Termux detected: {termux['termux_detected']}",
        f"Termux packages: {', '.join(packages) if packages else '(none)'}",
        f"Package scan return code: {termux.get('returncode')}",
    ]
    if termux.get("error"):
        lines.extend(["", "ADB package scan note:", "- " + str(termux["error"])])
    lines.extend(
        [
            "",
            "Safety:",
            "- This check does not install Termux.",
            "- This check does not run Android Worker Alpha.",
        ]
    )
    return "\n".join(lines) + "\n"


def validate_phone_job_packet(device_id: str, explicit_adb_path: str | None = None) -> dict[str, Any]:
    result = run_adb_shell(device_id, "cat " + REMOTE_JOB_PACKET, explicit_adb_path=explicit_adb_path, timeout=30)
    if result.get("returncode") != 0:
        raise AndroidSetupError("phone job packet could not be read from " + REMOTE_JOB_PACKET)
    try:
        job = json.loads(str(result.get("stdout", "")))
    except json.JSONDecodeError as exc:
        raise AndroidSetupError("phone job packet is not valid JSON") from exc
    if not isinstance(job, dict):
        raise AndroidSetupError("phone job packet JSON root is not an object")
    expected = {
        "assigned_worker_id": WORKER_ID,
        "job_type": "summarize_text",
        "real_job": True,
        "job_template": False,
        "status": "prepared_for_manual_transfer",
    }
    problems = [key for key, value in expected.items() if job.get(key) != value]
    if problems:
        raise AndroidSetupError("phone job packet failed validation: " + ", ".join(problems))
    return job


def validate_run_prerequisites(device_id: str, explicit_adb_path: str | None = None) -> tuple[dict[str, Any], str]:
    phone = phone_artifact_status(device_id, explicit_adb_path)
    if not phone["worker_folder_exists"]:
        raise AndroidSetupError("phone worker folder is missing: " + PHONE_ROOT)
    if not phone["job_packet_exists"]:
        raise AndroidSetupError("phone job packet is missing: " + REMOTE_JOB_PACKET)
    if not phone["input_file_exists"]:
        raise AndroidSetupError("phone input file is missing: " + REMOTE_INPUT_FILE)
    job = validate_phone_job_packet(device_id, explicit_adb_path)
    python_payload = python_checks(device_id, explicit_adb_path)
    if not python_payload["python_available"]:
        raise AndroidSetupError("Python is not available in the normal ADB shell; open Termux manually or add a later approved Termux command bridge.")
    return job, str(python_payload["preferred_python"])


def write_run_attempt_receipt(
    device_id: str,
    command: list[str],
    result: dict[str, Any],
    python_command: str,
) -> Path:
    RUN_ATTEMPTS.mkdir(parents=True, exist_ok=True)
    path = RUN_ATTEMPTS / (receipt_stamp() + "_android_worker_alpha_adb_run_attempt_receipt.json")
    receipt = {
        "timestamp": now(),
        "device_id": device_id,
        "worker_id": WORKER_ID,
        "job_id": JOB_ID,
        "command_attempted": command_text(command),
        "stdout_summary": str(result.get("stdout", ""))[:4000],
        "stderr_summary": str(result.get("stderr", ""))[:4000],
        "exit_code": result.get("returncode"),
        "python_command_used": python_command,
        "no_fake_results": True,
        "no_trusted_memory_write": True,
        "no_patch_apply": True,
        "completion_not_trusted_until_pull_validation": True,
    }
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def run_worker_on_phone(device_id: str | None = None, explicit_adb_path: str | None = None) -> dict[str, Any]:
    selected, _devices_payload = selected_authorized_device(device_id, explicit_adb_path)
    job, python_command = validate_run_prerequisites(selected, explicit_adb_path)
    shell_command = "cd " + PHONE_ROOT + " && " + python_command + " run_assigned_job.py"
    command = adb_shell_command(selected, shell_command, explicit_adb_path)
    result = run_command(command, timeout=300)
    receipt_path = write_run_attempt_receipt(selected, command, result, python_command)
    return {
        "run_attempt_status": "attempted_once_on_phone",
        "device_id": selected,
        "worker_id": WORKER_ID,
        "job_id": job.get("job_id", JOB_ID),
        "python_command_used": python_command,
        "exit_code": result.get("returncode"),
        "receipt_path": rel(receipt_path),
        "no_fake_results": True,
        "no_trusted_memory_write": True,
        "no_patch_apply": True,
        "completion_not_trusted_until_pull_validation": True,
        "note": "Run attempt does not mark completion. Use --pull-results after real worker files exist.",
    }


def write_push_receipt(device_id: str, command_results: list[dict[str, Any]], status: str) -> Path:
    SETUP_RECEIPTS.mkdir(parents=True, exist_ok=True)
    path = SETUP_RECEIPTS / (receipt_stamp() + "_android_worker_alpha_adb_push_receipt.json")
    receipt = {
        "timestamp": now(),
        "device_id": device_id,
        "target_phone_folder": PHONE_ROOT,
        "files_pushed": [
            rel(ALPHA_PACKAGE),
            rel(JOB_PACKET),
            rel(INPUT_FILE),
        ],
        "job_id": JOB_ID,
        "worker_id": WORKER_ID,
        "setup_status": status,
        "job_status": "prepared_for_manual_transfer",
        "command_results": command_results,
        "no_worker_execution": True,
        "no_fake_results": True,
        "no_phone_control_loop": True,
        "no_trusted_memory_write": True,
        "no_patch_apply": True,
    }
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def write_phone_button_push_receipt(device_id: str, command_results: list[dict[str, Any]], status: str) -> Path:
    SETUP_RECEIPTS.mkdir(parents=True, exist_ok=True)
    path = SETUP_RECEIPTS / (receipt_stamp() + "_android_worker_alpha_phone_button_ui_push_receipt.json")
    receipt = {
        "timestamp": now(),
        "device_id": device_id,
        "target_phone_folder": PHONE_ROOT,
        "files_pushed": [item["local_path"] for item in validate_phone_button_ui_sources()["files"]],
        "remote_files": [item["remote_path"] for item in validate_phone_button_ui_sources()["files"]],
        "worker_id": WORKER_ID,
        "setup_status": status,
        "button_launcher": "Termux widget shortcut template plus start_remote_worker_ui.py",
        "no_worker_execution": True,
        "no_ui_execution_during_push": True,
        "no_app_package_install": True,
        "no_fake_results": True,
        "no_fake_status": True,
        "no_fake_progress": True,
        "no_phone_control_loop": True,
        "no_trusted_memory_write": True,
        "no_patch_apply": True,
    }
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def write_finish_runner_push_receipt(device_id: str, command_results: list[dict[str, Any]], status: str) -> Path:
    SETUP_RECEIPTS.mkdir(parents=True, exist_ok=True)
    path = SETUP_RECEIPTS / (receipt_stamp() + "_android_worker_alpha_finish_runner_push_receipt.json")
    receipt = {
        "timestamp": now(),
        "device_id": device_id,
        "target_phone_folder": PHONE_ROOT,
        "files_pushed": [item["local_path"] for item in validate_finish_runner_sources()["files"]],
        "remote_files": [item["remote_path"] for item in validate_finish_runner_sources()["files"]],
        "worker_id": WORKER_ID,
        "setup_status": status,
        "no_worker_execution": True,
        "no_pull_results": True,
        "no_fake_results": True,
        "no_trusted_memory_write": True,
        "no_patch_apply": True,
    }
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def write_finish_attempt_receipt(
    device_id: str,
    finish_status: str,
    command_attempted: list[str] | None,
    run_result: dict[str, Any] | None,
    pull_result: dict[str, Any] | None,
    block_reason: str,
    fallback_command: str,
) -> Path:
    RUN_ATTEMPTS.mkdir(parents=True, exist_ok=True)
    path = RUN_ATTEMPTS / (receipt_stamp() + "_android_worker_alpha_finish_attempt_receipt.json")
    receipt = {
        "timestamp": now(),
        "device_id": device_id,
        "worker_id": WORKER_ID,
        "job_id": JOB_ID,
        "finish_status": finish_status,
        "command_attempted": command_text(command_attempted) if command_attempted else "",
        "stdout_summary": str((run_result or {}).get("stdout", ""))[:4000],
        "stderr_summary": str((run_result or {}).get("stderr", ""))[:4000],
        "exit_code": (run_result or {}).get("returncode"),
        "pull_result": pull_result or {},
        "block_reason": block_reason,
        "one_line_termux_fallback": fallback_command,
        "no_fake_results": True,
        "no_trusted_memory_write": True,
        "no_patch_apply": True,
        "completion_not_trusted_until_pull_validation": True,
    }
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def run_push(device_id: str | None = None, explicit_adb_path: str | None = None) -> dict[str, Any]:
    local = validate_local_sources()
    if not local["local_sources_ready"]:
        raise AndroidSetupError("local setup sources are not ready: " + "; ".join(local["problems"]))
    devices_payload = adb_devices(run_adb_check=True, explicit_adb_path=explicit_adb_path)
    selected_device = select_device(device_id, devices_payload)
    results: list[dict[str, Any]] = []
    for command in [*mkdir_commands(selected_device, explicit_adb_path), *push_commands(selected_device, explicit_adb_path)]:
        result = run_command(command, timeout=120)
        results.append(result)
        if result.get("returncode") != 0:
            receipt_path = write_push_receipt(selected_device, results, "push_failed")
            raise AndroidSetupError("ADB setup command failed; receipt written to " + rel(receipt_path))
    receipt_path = write_push_receipt(selected_device, results, "pushed_for_manual_android_setup")
    return {
        "setup_status": "pushed_for_manual_android_setup",
        "device_id": selected_device,
        "target_phone_folder": PHONE_ROOT,
        "receipt_path": rel(receipt_path),
        "job_status": "prepared_for_manual_transfer",
        "no_worker_execution": True,
        "no_fake_results": True,
    }


def run_push_finish_runner(device_id: str | None = None, explicit_adb_path: str | None = None) -> dict[str, Any]:
    local = validate_finish_runner_sources()
    if not local["finish_runner_sources_ready"]:
        raise AndroidSetupError("finish runner sources are not ready: " + "; ".join(local["problems"]))
    devices_payload = adb_devices(run_adb_check=True, explicit_adb_path=explicit_adb_path)
    selected_device = select_device(device_id, devices_payload)
    results: list[dict[str, Any]] = []
    for command in [*finish_runner_mkdir_commands(selected_device, explicit_adb_path), *finish_runner_push_commands(selected_device, explicit_adb_path)]:
        result = run_command(command, timeout=120)
        results.append(result)
        if result.get("returncode") != 0:
            receipt_path = write_finish_runner_push_receipt(selected_device, results, "finish_runner_push_failed")
            raise AndroidSetupError("ADB finish runner push command failed; receipt written to " + rel(receipt_path))
    receipt_path = write_finish_runner_push_receipt(selected_device, results, "finish_runner_pushed")
    return {
        "setup_status": "finish_runner_pushed",
        "device_id": selected_device,
        "target_phone_folder": PHONE_ROOT,
        "receipt_path": rel(receipt_path),
        "files_pushed": local["files"],
        "no_worker_execution": True,
        "no_pull_results": True,
        "no_fake_results": True,
    }


def run_push_phone_button_ui(device_id: str | None = None, explicit_adb_path: str | None = None) -> dict[str, Any]:
    local = validate_phone_button_ui_sources()
    if not local["phone_button_ui_sources_ready"]:
        raise AndroidSetupError("phone button UI sources are not ready: " + "; ".join(local["problems"]))
    devices_payload = adb_devices(run_adb_check=True, explicit_adb_path=explicit_adb_path)
    selected_device = select_device(device_id, devices_payload)
    results: list[dict[str, Any]] = []
    for command in [*phone_button_mkdir_commands(selected_device, explicit_adb_path), *phone_button_push_commands(selected_device, explicit_adb_path)]:
        result = run_command(command, timeout=120)
        results.append(result)
        if result.get("returncode") != 0:
            receipt_path = write_phone_button_push_receipt(selected_device, results, "phone_button_ui_push_failed")
            raise AndroidSetupError("ADB phone button UI push command failed; receipt written to " + rel(receipt_path))
    receipt_path = write_phone_button_push_receipt(selected_device, results, "phone_button_ui_pushed")
    return {
        "setup_status": "phone_button_ui_pushed",
        "device_id": selected_device,
        "target_phone_folder": PHONE_ROOT,
        "receipt_path": rel(receipt_path),
        "files_pushed": local["files"],
        "no_worker_execution": True,
        "no_ui_execution_during_push": True,
        "no_fake_results": True,
        "no_app_package_install": True,
    }


def check_phone_ui(device_id: str | None = None, explicit_adb_path: str | None = None) -> dict[str, Any]:
    selected, devices_payload = selected_authorized_device(device_id, explicit_adb_path)
    checks: list[dict[str, Any]] = []
    for label, _local_path, remote_path in PHONE_BUTTON_UI_FILES:
        checks.append(
            {
                "label": label,
                "remote_path": remote_path,
                "exists": phone_path_exists(selected, remote_path, explicit_adb_path, kind="f"),
            }
        )
    return {
        "check_name": "Android Worker Alpha phone button UI file check",
        "device_id": selected,
        "adb": devices_payload,
        "phone_target_folder": PHONE_ROOT,
        "files": checks,
        "all_required_phone_ui_files_present": all(bool(item["exists"]) for item in checks),
        "no_ui_execution": True,
        "no_worker_execution": True,
        "no_fake_results": True,
    }


def render_phone_ui_check(payload: dict[str, Any]) -> str:
    lines = [
        "Android Worker Alpha phone button UI file check",
        "",
        f"Device: {payload['device_id']}",
        f"Phone target folder: {payload['phone_target_folder']}",
        f"All required phone UI files present: {payload['all_required_phone_ui_files_present']}",
        "",
        "Files:",
    ]
    for item in payload.get("files", []):
        lines.append(f"- {item.get('label')}: exists={item.get('exists')} path={item.get('remote_path')}")
    lines.extend(
        [
            "",
            "Safety:",
            "- This check does not run the phone UI.",
            "- This check does not run Android Worker Alpha.",
            "- This check does not create fake returned files.",
        ]
    )
    return "\n".join(lines) + "\n"


def remote_names(device_id: str, remote_folder: str, explicit_adb_path: str | None = None) -> list[str]:
    result = run_command(adb_base(device_id, explicit_adb_path) + ["shell", "ls", "-1", remote_folder], timeout=30)
    if result.get("returncode") != 0:
        return []
    names: list[str] = []
    for line in str(result.get("stdout", "")).splitlines():
        name = line.strip()
        if not name or name == ".gitkeep" or "/" in name or "\\" in name or name in {".", ".."}:
            continue
        names.append(name)
    return names


def write_pull_receipt(device_id: str, pulled_files: list[dict[str, str]]) -> Path:
    SETUP_RECEIPTS.mkdir(parents=True, exist_ok=True)
    path = SETUP_RECEIPTS / (receipt_stamp() + "_android_worker_alpha_adb_pull_receipt.json")
    receipt = {
        "timestamp": now(),
        "device_id": device_id,
        "source_phone_folder": PHONE_ROOT,
        "pulled_files": pulled_files,
        "job_id": JOB_ID,
        "worker_id": WORKER_ID,
        "pull_status": "real_returned_files_pulled",
        "no_fake_results": True,
        "no_completion_marked_by_setup_helper": True,
        "no_trusted_memory_write": True,
        "no_patch_apply": True,
    }
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def run_pull_results(device_id: str | None = None, explicit_adb_path: str | None = None) -> dict[str, Any]:
    devices_payload = adb_devices(run_adb_check=True, explicit_adb_path=explicit_adb_path)
    selected_device = select_device(device_id, devices_payload)
    pulled: list[dict[str, str]] = []
    for label, (remote_folder, local_folder) in PULL_FOLDERS.items():
        local_folder.mkdir(parents=True, exist_ok=True)
        for name in remote_names(selected_device, remote_folder, explicit_adb_path):
            remote_file = remote_folder + "/" + name
            result = run_command(adb_base(selected_device, explicit_adb_path) + ["pull", remote_file, str(local_folder)], timeout=120)
            if result.get("returncode") == 0:
                pulled.append({"category": label, "remote_path": remote_file, "local_folder": rel(local_folder), "filename": name})
    output: dict[str, Any] = {
        "device_id": selected_device,
        "pulled_file_count": len(pulled),
        "pulled_files": pulled,
        "no_fake_results": True,
        "no_completion_marked_by_setup_helper": True,
    }
    if pulled:
        output["receipt_path"] = rel(write_pull_receipt(selected_device, pulled))
    else:
        output["receipt_path"] = ""
        output["note"] = "No real returned files were found or pulled; no pull receipt was created."
    return output


def run_finish_alpha_worker(device_id: str | None = None, explicit_adb_path: str | None = None) -> dict[str, Any]:
    fallback = one_line_termux_finish_command()
    local = validate_local_sources()
    finish_local = validate_finish_runner_sources()
    if not local["local_sources_ready"]:
        raise AndroidSetupError("local setup sources are not ready: " + "; ".join(local["problems"]))
    if not finish_local["finish_runner_sources_ready"]:
        raise AndroidSetupError("finish runner sources are not ready: " + "; ".join(finish_local["problems"]))
    devices_payload = adb_devices(run_adb_check=True, explicit_adb_path=explicit_adb_path)
    selected_device = select_device(device_id, devices_payload)

    phone = phone_artifact_status(selected_device, explicit_adb_path)
    if not phone["worker_folder_exists"]:
        raise AndroidSetupError("phone worker shared folder is missing: " + PHONE_ROOT)
    if not phone["job_packet_exists"]:
        raise AndroidSetupError("phone job packet is missing: " + REMOTE_JOB_PACKET)
    if not phone["input_file_exists"]:
        raise AndroidSetupError("phone input file is missing: " + REMOTE_INPUT_FILE)
    termux = termux_check(selected_device, explicit_adb_path)
    if not termux.get("termux_detected"):
        receipt_path = write_finish_attempt_receipt(
            selected_device,
            "blocked_termux_missing",
            None,
            None,
            None,
            "Termux package was not detected.",
            fallback,
        )
        return {
            "finish_status": "blocked_termux_missing",
            "device_id": selected_device,
            "receipt_path": rel(receipt_path),
            "block_reason": "Termux package was not detected.",
            "one_line_termux_fallback": fallback,
            "no_fake_results": True,
        }

    push_result = run_push_finish_runner(selected_device, explicit_adb_path)
    finish_exists = phone_path_exists(selected_device, REMOTE_FINISH_RUNNER, explicit_adb_path, kind="f")
    if not finish_exists:
        raise AndroidSetupError("finish runner was not found on phone after push: " + REMOTE_FINISH_RUNNER)
    assigned_input_exists = phone_path_exists(selected_device, REMOTE_ASSIGNED_INPUT_FILE, explicit_adb_path, kind="f")
    if not assigned_input_exists:
        raise AndroidSetupError("assigned input file was not found on phone after finish runner push: " + REMOTE_ASSIGNED_INPUT_FILE)

    python_payload = python_checks(selected_device, explicit_adb_path)
    if not python_payload.get("python_available"):
        pull_result = run_pull_results(selected_device, explicit_adb_path)
        receipt_path = write_finish_attempt_receipt(
            selected_device,
            "blocked_python_unavailable_in_adb_shell",
            None,
            None,
            pull_result,
            "Termux Python is available only interactively. Open Termux and run: python finish_alpha_job.py",
            fallback,
        )
        return {
            "finish_status": "blocked_python_unavailable_in_adb_shell",
            "device_id": selected_device,
            "push_result": push_result,
            "pull_result": pull_result,
            "receipt_path": rel(receipt_path),
            "block_reason": "Termux Python is available only interactively. Open Termux and run: python finish_alpha_job.py",
            "one_line_termux_fallback": fallback,
            "no_fake_results": True,
            "no_completion_marked_by_setup_helper": True,
        }

    python_command = str(python_payload["preferred_python"])
    command = adb_shell_command(selected_device, "cd " + PHONE_ROOT + " && " + python_command + " finish_alpha_job.py", explicit_adb_path)
    run_result = run_command(command, timeout=300)
    pull_result = run_pull_results(selected_device, explicit_adb_path)
    finish_status = "ran_and_pulled_real_files" if run_result.get("returncode") == 0 and pull_result.get("pulled_file_count", 0) > 0 else "run_attempted_no_real_files_pulled"
    receipt_path = write_finish_attempt_receipt(
        selected_device,
        finish_status,
        command,
        run_result,
        pull_result,
        "" if run_result.get("returncode") == 0 else "finish runner returned non-zero",
        fallback,
    )
    return {
        "finish_status": finish_status,
        "device_id": selected_device,
        "push_result": push_result,
        "run_exit_code": run_result.get("returncode"),
        "pull_result": pull_result,
        "receipt_path": rel(receipt_path),
        "one_line_termux_fallback": fallback if finish_status != "ran_and_pulled_real_files" else "",
        "no_fake_results": True,
        "no_trusted_memory_write": True,
        "no_patch_apply": True,
        "completion_not_trusted_until_pull_validation": True,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bounded Android Studio/ADB setup helper for Android Worker Alpha.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--status", action="store_true", help="Check local setup sources and ADB device status without transfer.")
    mode.add_argument("--prepare-commands", action="store_true", help="Print exact ADB commands without executing them.")
    mode.add_argument("--check-python", action="store_true", help="Check whether python/python3 is available in the normal ADB shell.")
    mode.add_argument("--check-termux", action="store_true", help="Check whether a Termux package appears installed on the connected device.")
    mode.add_argument("--prepare-run-command", action="store_true", help="Print the exact optional on-device worker run commands without executing them.")
    mode.add_argument("--prepare-phone-button-commands", action="store_true", help="Print exact ADB commands for pushing the phone button UI without executing them.")
    mode.add_argument("--check-phone-ui", action="store_true", help="Check whether phone button UI files exist on the connected device without running them.")
    mode.add_argument("--push-phone-button-ui", action="store_true", help="Push phone button UI files only after explicit ADB acknowledgment.")
    mode.add_argument("--prepare-one-line-termux-finish", action="store_true", help="Print one exact Termux finish command without executing it.")
    mode.add_argument("--push-finish-runner", action="store_true", help="Push the non-interactive finish runner only after explicit ADB acknowledgment.")
    mode.add_argument("--finish-alpha-worker", action="store_true", help="Attempt the guarded finish flow for Android Worker Alpha after explicit approval.")
    mode.add_argument("--push", action="store_true", help="Create phone folders and push Worker Alpha package/job/input files only.")
    mode.add_argument("--pull-results", action="store_true", help="Pull only real returned status/result/log/receipt files if they exist.")
    mode.add_argument("--run-worker-on-phone", action="store_true", help="Run the already-pushed Worker Alpha job once on the phone after explicit approval.")
    parser.add_argument("--device-id", help="Optional explicit ADB serial when more than one authorized device is connected.")
    parser.add_argument("--adb-path", help=r"Optional explicit path to adb.exe, for example C:\Users\ziese\AppData\Local\Android\Sdk\platform-tools\adb.exe.")
    parser.add_argument(ACK_FLAG, action="store_true", dest="adb_ack", help="Required for --push, --push-phone-button-ui, --push-finish-runner, and --pull-results.")
    parser.add_argument(RUN_ACK_FLAG, action="store_true", dest="run_ack", help="Required for --run-worker-on-phone.")
    parser.add_argument(FINISH_ACK_FLAG, action="store_true", dest="finish_ack", help="Required for --finish-alpha-worker.")
    parser.add_argument("--no-adb-check", action="store_true", help="For --status only: print adb command without running adb devices.")
    return parser


def main(argv: list[str] | None = None, stdout=None, stderr=None) -> int:
    out = stdout if stdout is not None else sys.stdout
    err = stderr if stderr is not None else sys.stderr
    args = build_parser().parse_args(argv)
    try:
        if args.prepare_commands:
            out.write("\n".join(prepare_command_lines(args.adb_path)) + "\n")
        elif args.check_python:
            out.write(render_python_check(collect_python_check(args.device_id, args.adb_path)))
        elif args.check_termux:
            out.write(render_termux_check(collect_termux_check(args.device_id, args.adb_path)))
        elif args.prepare_run_command:
            out.write("\n".join(prepare_run_command_lines(args.adb_path)) + "\n")
        elif args.prepare_phone_button_commands:
            out.write("\n".join(prepare_phone_button_command_lines(args.adb_path)) + "\n")
        elif args.check_phone_ui:
            out.write(render_phone_ui_check(check_phone_ui(args.device_id, args.adb_path)))
        elif args.push_phone_button_ui:
            if not args.adb_ack:
                raise AndroidSetupError("--push-phone-button-ui requires " + ACK_FLAG)
            out.write(json.dumps(run_push_phone_button_ui(args.device_id, args.adb_path), indent=2, sort_keys=True) + "\n")
        elif args.prepare_one_line_termux_finish:
            out.write("\n".join(prepare_one_line_termux_finish_lines()) + "\n")
        elif args.push_finish_runner:
            if not args.adb_ack:
                raise AndroidSetupError("--push-finish-runner requires " + ACK_FLAG)
            out.write(json.dumps(run_push_finish_runner(args.device_id, args.adb_path), indent=2, sort_keys=True) + "\n")
        elif args.finish_alpha_worker:
            if not args.finish_ack:
                raise AndroidSetupError("--finish-alpha-worker requires " + FINISH_ACK_FLAG)
            out.write(json.dumps(run_finish_alpha_worker(args.device_id, args.adb_path), indent=2, sort_keys=True) + "\n")
        elif args.push:
            if not args.adb_ack:
                raise AndroidSetupError("--push requires " + ACK_FLAG)
            out.write(json.dumps(run_push(args.device_id, args.adb_path), indent=2, sort_keys=True) + "\n")
        elif args.run_worker_on_phone:
            if not args.run_ack:
                raise AndroidSetupError("--run-worker-on-phone requires " + RUN_ACK_FLAG)
            out.write(json.dumps(run_worker_on_phone(args.device_id, args.adb_path), indent=2, sort_keys=True) + "\n")
        elif args.pull_results:
            if not args.adb_ack:
                raise AndroidSetupError("--pull-results requires " + ACK_FLAG)
            out.write(json.dumps(run_pull_results(args.device_id, args.adb_path), indent=2, sort_keys=True) + "\n")
        else:
            payload = collect_status(run_adb_check=not args.no_adb_check, explicit_adb_path=args.adb_path)
            out.write(render_status(payload))
        return 0
    except AndroidSetupError as exc:
        err.write("Android Worker Alpha ADB setup blocked: " + str(exc) + "\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
