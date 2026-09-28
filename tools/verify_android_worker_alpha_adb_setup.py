from __future__ import annotations

import ast
import importlib.util
import io
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "tools" / "setup_android_worker_alpha_adb.py"
CONTRACT_JSON = ROOT / "memory" / "ENGEL_ANDROID_STUDIO_REMOTE_WORKER_SETUP_V1.json"
CONTRACT_MD = ROOT / "memory" / "ENGEL_ANDROID_STUDIO_REMOTE_WORKER_SETUP_V1.md"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_ANDROID_STUDIO_REMOTE_WORKER_SETUP_V1.md"
FOLLOWUP_REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_ANDROID_STUDIO_ADB_PATH_FIX_V1.md"
RUN_EXTENSION_REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_ANDROID_WORKER_ALPHA_ON_DEVICE_RUN_EXTENSION_V1.md"
PHONE_BUTTON_UI_REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_ANDROID_WORKER_ALPHA_PHONE_BUTTON_UI_V1.md"
FINISH_SETUP_REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_ANDROID_WORKER_ALPHA_FINISH_SETUP_V1.md"
FORBIDDEN_SECOND_HELPER = ROOT / "tools" / "setup_android_worker_alpha_termux_adb.py"
ALPHA_PACKAGE = ROOT / "remote_workers" / "android_worker_alpha"
FINISH_RUNNER = ALPHA_PACKAGE / "finish_alpha_job.py"
JOB_PACKET = ALPHA_PACKAGE / "jobs" / "20260516T201324Z_android_worker_alpha_summarize_text_summarize_engel_remote_worke.json"
INPUT_FILE = ROOT / "reports" / "codex_bridge" / "ENGEL_MULTI_ANDROID_REMOTE_WORKERS_PROTOCOL_V1.md"
KNOWN_USER_ADB = Path(r"C:\Users\ziese\AppData\Local\Android\Sdk\platform-tools\adb.exe")
SYSTEM_INTEGRATION = ROOT / "engel_system_integration_status.py"
CORE_JSON = ROOT / "memory" / "ENGEL_CORE_CONTINUITY_MAP_V1.json"
CORE_MD = ROOT / "memory" / "ENGEL_CORE_CONTINUITY_MAP_V1.md"
COMMANDS = ROOT / "memory" / "ENGEL_COMMANDS.md"
CODEX_VERIFY = ROOT / "scripts" / "codex_verify.ps1"

REQUIRED_STATUS_LABELS = [
    "ANDROID_STUDIO_REMOTE_WORKER_SETUP",
    "ANDROID_WORKER_ALPHA_SETUP",
    "ADB_FILE_TRANSFER_ONLY",
    "HUMAN_APPROVED_TRANSPORT_ONLY",
    "MANUAL_TRANSFER_BRIDGE",
    "COMMUNICATION_QUEEN_ROUTING_REQUIRED",
    "REMOTE_WORKER_NOT_QUEEN",
    "REAL_JOB_PACKET_ONLY",
    "REAL_INPUT_FILE_ONLY",
    "NO_WORKER_EXECUTION_DURING_PUSH",
    "NO_FAKE_STATUS",
    "NO_FAKE_RESULT",
    "NO_FAKE_PROGRESS",
    "NO_FAKE_LOG",
    "NO_FAKE_WORKER_RECEIPT",
    "NO_JOB_COMPLETION_MARKING",
    "NO_TERMUX_INSTALL_AUTOMATION",
    "NO_PACKAGE_INSTALL_AUTOMATION",
    "NO_HERMES_OLLAMA_LLAMA_CPP_PATH",
    "NO_MODEL_RUNTIME",
    "NO_PROVIDER_NETWORK_BROWSER",
    "NO_NETWORK_SERVER",
    "NO_SSH",
    "NO_CLOUD_SYNC",
    "NO_ADB_WIRELESS",
    "NO_PHONE_CONTROL_LOOP",
    "NO_SECOND_ADB_HOOK",
    "PYTHON_TERMUX_STATUS_CHECK_ONLY",
    "RUN_WORKER_REQUIRES_EXPLICIT_APPROVAL",
    "RUN_WORKER_ON_PHONE_ONLY",
    "COMPLETION_NOT_TRUSTED_UNTIL_PULL_VALIDATION",
    "NO_BACKGROUND_WORKER",
    "NO_STARTUP_AUTORUN",
    "NO_TRUSTED_MEMORY_WRITE",
    "NO_PATCH_APPLY",
]

FORBIDDEN_IMPORTS = {
    "requests",
    "urllib",
    "socket",
    "webbrowser",
    "openai",
    "threading",
    "multiprocessing",
}


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def load_json(path: Path) -> dict[str, object]:
    data = json.loads(read(path))
    require(isinstance(data, dict), "JSON root is not object: " + str(path.relative_to(ROOT)))
    return data


def load_module():
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location("setup_android_worker_alpha_adb", HELPER)
    require(spec is not None and spec.loader is not None, "could not load setup helper")
    module = importlib.util.module_from_spec(spec)
    sys.modules["setup_android_worker_alpha_adb"] = module
    spec.loader.exec_module(module)
    return module


def check_files_exist() -> None:
    for path in [HELPER, CONTRACT_JSON, CONTRACT_MD, ALPHA_PACKAGE, JOB_PACKET, INPUT_FILE, FINISH_RUNNER]:
        require(path.exists(), "required file/folder missing: " + str(path.relative_to(ROOT)))
    require(not FORBIDDEN_SECOND_HELPER.exists(), "duplicate Termux/ADB helper must not exist")


def check_contract() -> None:
    data = load_json(CONTRACT_JSON)
    text = read(CONTRACT_MD)
    require(data.get("contract_name") == "Android Studio Setup for First Real Android Remote Worker V1", "contract name mismatch")
    require(data.get("worker_id") == "android_worker_alpha", "worker id mismatch")
    require(data.get("phone_target_folder") == "/sdcard/EngelRemoteWorker/android_worker_alpha/", "phone target folder mismatch")
    require(data.get("known_android_sdk_path") == r"C:\Users\ziese\AppData\Local\Android\Sdk", "known Android SDK path missing")
    require(data.get("expected_adb_path") == r"C:\Users\ziese\AppData\Local\Android\Sdk\platform-tools\adb.exe", "expected ADB path missing")
    discovery_order = data.get("adb_discovery_order", [])
    for phrase in [
        "explicit --adb-path override",
        "PATH",
        "ANDROID_HOME\\platform-tools\\adb.exe",
        "ANDROID_SDK_ROOT\\platform-tools\\adb.exe",
        r"C:\Users\ziese\AppData\Local\Android\Sdk\platform-tools\adb.exe",
        r"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe",
    ]:
        require(phrase in discovery_order, "ADB discovery order missing: " + phrase)
    require(data.get("explicit_adb_ack_required") == "--i-understand-this-uses-adb", "explicit ADB ack flag missing")
    require(data.get("explicit_run_ack_required") == "--i-approve-run-worker-on-phone", "explicit run approval flag missing")
    require(data.get("run_attempt_receipt_folder") == "reports\\android_remote_worker_run_attempts\\", "run-attempt receipt folder missing")
    extension = data.get("on_device_run_extension", {})
    require(isinstance(extension, dict), "on-device run extension missing")
    require(extension.get("no_second_helper_or_hook") is True, "contract must block second helper/hook")
    require(extension.get("check_python_mode") == "--check-python", "check-python mode missing")
    require(extension.get("check_termux_mode") == "--check-termux", "check-termux mode missing")
    require(extension.get("prepare_run_command_mode") == "--prepare-run-command", "prepare-run-command mode missing")
    require(extension.get("run_worker_on_phone_mode") == "--run-worker-on-phone --i-approve-run-worker-on-phone", "run-worker mode missing/ungated")
    require(extension.get("completion_not_trusted_until_pull_validation") is True, "completion validation boundary missing")
    for label in REQUIRED_STATUS_LABELS:
        require(label in data.get("status_labels", []), "contract missing status label: " + label)
        require(label in text, "contract Markdown missing status label: " + label)
    boundary = data.get("hard_safety_boundaries", {})
    for key in [
        "no_worker_execution_during_push",
        "no_fake_status",
        "no_fake_result",
        "no_fake_progress",
        "no_fake_log",
        "no_fake_worker_receipt",
        "no_job_completion_marking",
        "no_termux_install_automation",
        "no_app_install_automation",
        "no_package_install_automation",
        "no_hermes",
        "no_ollama",
        "no_llama_cpp",
        "no_model_runtime",
        "no_model_inference",
        "no_network_server",
        "no_ssh",
        "no_cloud_sync",
        "no_adb_wireless",
        "no_continuous_adb_loop",
        "no_phone_control_loop",
        "no_second_adb_hook",
        "no_worker_run_without_explicit_approval",
        "no_completion_trust_without_pull_validation",
        "no_provider_network_browser",
        "no_trusted_memory_write",
        "no_memory_promotion",
        "no_patch_apply",
        "no_background_worker",
        "no_startup_autorun",
    ]:
        require(boundary.get(key) is True, "contract boundary missing/false: " + key)
    for phrase in [
        "Android phone is an Android Remote Worker / Mobile Worker, not a Queen",
        "python tools\\setup_android_worker_alpha_adb.py --prepare-commands",
        "python tools\\setup_android_worker_alpha_adb.py --push --i-understand-this-uses-adb",
        "python tools\\setup_android_worker_alpha_adb.py --pull-results --i-understand-this-uses-adb",
        "python tools\\setup_android_worker_alpha_adb.py --check-python",
        "python tools\\setup_android_worker_alpha_adb.py --check-termux",
        "python tools\\setup_android_worker_alpha_adb.py --prepare-run-command",
        "python tools\\setup_android_worker_alpha_adb.py --run-worker-on-phone --i-approve-run-worker-on-phone",
        r"C:\Users\ziese\AppData\Local\Android\Sdk",
        r"C:\Users\ziese\AppData\Local\Android\Sdk\platform-tools\adb.exe",
        r"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe",
        "--adb-path",
        '"C:\\Users\\ziese\\AppData\\Local\\Android\\Sdk\\platform-tools\\adb.exe" devices',
        "`--push` does not run this command",
        "Do not install Hermes, Ollama, or llama.cpp",
    ]:
        require(phrase in text, "contract Markdown missing: " + phrase)


def check_helper_static() -> None:
    source = read(HELPER)
    tree = ast.parse(source)
    require("--status" in source, "helper missing --status")
    require("--prepare-commands" in source, "helper missing --prepare-commands")
    require("--check-python" in source, "helper missing --check-python")
    require("--check-termux" in source, "helper missing --check-termux")
    require("--prepare-run-command" in source, "helper missing --prepare-run-command")
    require("--prepare-phone-button-commands" in source, "helper missing --prepare-phone-button-commands")
    require("--check-phone-ui" in source, "helper missing --check-phone-ui")
    require("--push-phone-button-ui" in source, "helper missing --push-phone-button-ui")
    require("--prepare-one-line-termux-finish" in source, "helper missing --prepare-one-line-termux-finish")
    require("--push-finish-runner" in source, "helper missing --push-finish-runner")
    require("--finish-alpha-worker" in source, "helper missing --finish-alpha-worker")
    require("--run-worker-on-phone" in source, "helper missing --run-worker-on-phone")
    require("--push" in source, "helper missing --push")
    require("--pull-results" in source, "helper missing --pull-results")
    require("--adb-path" in source, "helper missing --adb-path")
    require("--i-understand-this-uses-adb" in source, "helper missing explicit ADB approval flag")
    require("--i-approve-run-worker-on-phone" in source, "helper missing explicit worker-run approval flag")
    require("--i-approve-finish-alpha-worker" in source, "helper missing explicit finish approval flag")
    for phrase in [
        r"C:\Users\ziese\AppData\Local\Android\Sdk",
        "known_user_sdk_path",
        "LOCALAPPDATA_fallback",
        "validate_adb_override",
        "adb_discovery_source",
        "display_executable",
        "ANDROID_HOME",
        "ANDROID_SDK_ROOT",
        "python_checks",
        "termux_check",
        "prepare_run_command_lines",
        "run_worker_on_phone",
        "prepare_phone_button_command_lines",
        "check_phone_ui",
        "run_push_phone_button_ui",
        "write_phone_button_push_receipt",
        "one_line_termux_finish_command",
        "run_push_finish_runner",
        "run_finish_alpha_worker",
        "write_finish_attempt_receipt",
        "write_run_attempt_receipt",
        "completion_not_trusted_until_pull_validation",
        "reports\" / \"android_remote_worker_run_attempts",
    ]:
        require(phrase in source, "helper missing ADB discovery support: " + phrase)
    require("run_push" in source and "run_pull_results" in source, "helper missing push/pull functions")
    require("optional_manual_run_command" in source, "helper missing optional manual run printer")
    require("run_push" in source and "optional_manual_run_command" in source, "helper missing push/manual separation")
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                require(root not in FORBIDDEN_IMPORTS, "helper imports forbidden package: " + alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            root = node.module.split(".")[0]
            require(root not in FORBIDDEN_IMPORTS, "helper imports forbidden package: " + node.module)
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                require(func.id not in {"eval", "exec", "__import__"}, "helper uses forbidden dynamic call: " + func.id)
            elif isinstance(func, ast.Attribute):
                require(not (func.attr == "run" and any(keyword.arg == "shell" and getattr(keyword.value, "value", None) is True for keyword in node.keywords)), "helper must not use shell=True")
        elif isinstance(node, ast.While):
            raise CheckFailure("helper contains while loop")
    forbidden_snippets = [
        "adb tcpip",
        "adb connect",
        "adb install",
        "pkg install",
        "pip install",
        "termux-setup-storage",
        "socket.",
        "requests.",
        "webbrowser.",
        "openai.",
        "progress_percent",
        "\"real_result\": True",
        "\"real_status\": True",
    ]
    for snippet in forbidden_snippets:
        require(snippet not in source, "helper contains forbidden active/setup snippet: " + snippet)
    require("write_push_receipt" in source, "push receipt writer missing")
    require("write_phone_button_push_receipt" in source, "phone button UI push receipt writer missing")
    require("write_finish_attempt_receipt" in source, "finish attempt receipt writer missing")
    require("write_pull_receipt" in source, "pull receipt writer missing")
    require("no_worker_execution" in source, "push receipt must record no worker execution")
    require("no_fake_results" in source, "receipts must record no fake results")
    require("no_phone_control_loop" in source, "push receipt must record no phone control loop")
    require("pm list packages" in source, "helper missing Termux package status check")
    require("python --version" in source and "python3 --version" in source, "helper missing Python availability checks")
    require('"cd " + PHONE_ROOT + " && " + python_command + " run_assigned_job.py"' in source, "helper must construct only the fixed Worker Alpha run command")
    require("phone_button_push_commands" in source, "helper missing phone button UI push command builder")
    require("--push-phone-button-ui requires " in source, "phone button UI push must require explicit ADB ack")
    require("finish_runner_push_commands" in source, "helper missing finish runner push command builder")
    require("--push-finish-runner requires " in source, "finish runner push must require explicit ADB ack")
    require("--finish-alpha-worker requires " in source, "finish mode must require explicit finish approval")


def check_helper_runtime_non_mutating() -> None:
    module = load_module()
    payload = module.collect_status(run_adb_check=False)
    require(payload.get("worker_id") == "android_worker_alpha", "status worker id mismatch")
    require(payload.get("phone_target_folder") == "/sdcard/EngelRemoteWorker/android_worker_alpha", "status target folder mismatch")
    require(payload.get("local_sources", {}).get("local_sources_ready") is True, "local setup sources are not ready")
    require(payload.get("boundaries", {}).get("no_worker_execution_during_push") is True, "status boundary missing no worker execution")
    if KNOWN_USER_ADB.exists():
        adb = payload.get("adb", {})
        require(adb.get("adb_found") is True, "known user SDK ADB should be discovered when present")
        require(adb.get("adb_path") == str(KNOWN_USER_ADB), "known user SDK ADB path mismatch")
        require(
            adb.get("adb_discovery_source")
            in {"ANDROID_HOME", "ANDROID_SDK_ROOT", "known_user_sdk_path", "PATH", "LOCALAPPDATA_fallback"},
            "known ADB discovery source mismatch",
        )
        override_payload = module.collect_status(run_adb_check=False, explicit_adb_path=str(KNOWN_USER_ADB))
        require(override_payload.get("adb", {}).get("adb_discovery_source") == "explicit_user_override", "explicit --adb-path source mismatch")
    out = io.StringIO()
    err = io.StringIO()
    require(module.main(["--status", "--no-adb-check"], stdout=out, stderr=err) == 0, "--status --no-adb-check failed")
    status_text = out.getvalue()
    for phrase in [
        "Android Studio Setup for First Real Android Remote Worker V1",
        "ADB command run: False",
        "ADB discovery source:",
        "ADB command:",
        "Phone artifact checks run:",
        "Can push with explicit ack:",
        "does not fake missing results",
    ]:
        require(phrase.lower() in status_text.lower(), "status output missing: " + phrase)
    out = io.StringIO()
    require(module.main(["--prepare-commands"], stdout=out, stderr=err) == 0, "--prepare-commands failed")
    commands = out.getvalue()
    adb_source = payload.get("adb", {}).get("adb_discovery_source")
    if KNOWN_USER_ADB.exists() and adb_source != "PATH":
        require('"' + str(KNOWN_USER_ADB) + '" devices' in commands, "--prepare-commands must print full quoted known ADB path when discovered outside PATH")
    if adb_source == "PATH":
        require("adb devices" in commands, "--prepare-commands must print plain adb when discovered from PATH")
    for phrase in [
        "devices",
        "mkdir -p",
        "push",
        "/sdcard/EngelRemoteWorker/android_worker_alpha",
        "remote_workers",
        "ENGEL_MULTI_ANDROID_REMOTE_WORKERS_PROTOCOL_V1.md",
        "Optional later manual run command",
        "python run_assigned_job.py",
    ]:
        require(phrase in commands, "prepare commands missing: " + phrase)
    out = io.StringIO()
    require(module.main(["--prepare-run-command"], stdout=out, stderr=err) == 0, "--prepare-run-command failed")
    run_commands = out.getvalue()
    for phrase in [
        "Nothing in --prepare-run-command is executed",
        "python --version",
        "python3 --version",
        "pm list packages",
        "cd /sdcard/EngelRemoteWorker/android_worker_alpha && python run_assigned_job.py",
        "cd ~/storage/shared/EngelRemoteWorker/android_worker_alpha",
    ]:
        require(phrase in run_commands, "prepare-run-command output missing: " + phrase)
    out = io.StringIO()
    require(module.main(["--prepare-phone-button-commands"], stdout=out, stderr=err) == 0, "--prepare-phone-button-commands failed")
    phone_button_commands = out.getvalue()
    for phrase in [
        "Nothing in --prepare-phone-button-commands is executed",
        "start_remote_worker_ui.py",
        "remote_worker_phone_ui.py",
        "termux_widget_shortcuts/EngelWorkerAlphaUI",
        "cd ~/storage/shared/EngelRemoteWorker/android_worker_alpha",
        "python start_remote_worker_ui.py",
    ]:
        require(phrase in phone_button_commands, "prepare-phone-button-commands output missing: " + phrase)
    phone_button_push_commands = [module.command_text(command) for command in module.phone_button_push_commands()]
    require(not any("run_assigned_job.py" in command for command in phone_button_push_commands), "--push-phone-button-ui command list must not run worker job")
    require(not any("start_remote_worker_ui.py &&" in command for command in phone_button_push_commands), "--push-phone-button-ui command list must not run phone UI")
    out = io.StringIO()
    require(module.main(["--prepare-one-line-termux-finish"], stdout=out, stderr=err) == 0, "--prepare-one-line-termux-finish failed")
    one_line = out.getvalue()
    for phrase in [
        "Paste this exact line into Termux",
        "cd ~/engel_remote_worker_alpha",
        "python finish_alpha_job.py",
        "cp -r receipts/* /sdcard/EngelRemoteWorker/android_worker_alpha/receipts/",
    ]:
        require(phrase in one_line, "one-line Termux finish output missing: " + phrase)
    finish_push_commands = [module.command_text(command) for command in module.finish_runner_push_commands()]
    require(not any("finish_alpha_job.py &&" in command for command in finish_push_commands), "--push-finish-runner command list must not run finish runner")
    require(not any("run_assigned_job.py" in command for command in finish_push_commands), "--push-finish-runner command list must not run worker job")
    push_commands = [module.command_text(command) for command in module.push_commands()]
    require(not any("run_assigned_job.py" in command for command in push_commands), "--push command list must not run worker job")
    out = io.StringIO()
    err = io.StringIO()
    require(module.main(["--push"], stdout=out, stderr=err) == 2, "--push without ack must block")
    require("--push requires --i-understand-this-uses-adb" in err.getvalue(), "--push missing explicit ack block message")
    out = io.StringIO()
    err = io.StringIO()
    require(module.main(["--push-phone-button-ui"], stdout=out, stderr=err) == 2, "--push-phone-button-ui without ack must block")
    require("--push-phone-button-ui requires --i-understand-this-uses-adb" in err.getvalue(), "--push-phone-button-ui missing explicit ack block message")
    out = io.StringIO()
    err = io.StringIO()
    require(module.main(["--push-finish-runner"], stdout=out, stderr=err) == 2, "--push-finish-runner without ack must block")
    require("--push-finish-runner requires --i-understand-this-uses-adb" in err.getvalue(), "--push-finish-runner missing explicit ack block message")
    out = io.StringIO()
    err = io.StringIO()
    require(module.main(["--finish-alpha-worker"], stdout=out, stderr=err) == 2, "--finish-alpha-worker without approval must block")
    require("--finish-alpha-worker requires --i-approve-finish-alpha-worker" in err.getvalue(), "--finish-alpha-worker missing explicit approval block message")
    out = io.StringIO()
    err = io.StringIO()
    require(module.main(["--run-worker-on-phone"], stdout=out, stderr=err) == 2, "--run-worker-on-phone without approval must block")
    require("--run-worker-on-phone requires --i-approve-run-worker-on-phone" in err.getvalue(), "--run-worker-on-phone missing explicit approval block message")
    if KNOWN_USER_ADB.exists():
        out = io.StringIO()
        err = io.StringIO()
        require(module.main(["--status", "--no-adb-check", "--adb-path", str(KNOWN_USER_ADB)], stdout=out, stderr=err) == 0, "--status --adb-path --no-adb-check failed")
        status_text = out.getvalue()
        require("explicit_user_override" in status_text, "explicit --adb-path status missing discovery source")
        require('"' + str(KNOWN_USER_ADB) + '" devices' in status_text, "explicit --adb-path status missing quoted command")


def check_no_fake_returned_files_created_by_static_paths() -> None:
    for folder_name in ["status", "outbox", "logs", "receipts"]:
        folder = ALPHA_PACKAGE / folder_name
        require(folder.exists(), "Alpha folder missing: " + folder_name)
    job = load_json(JOB_PACKET)
    require(job.get("status") == "prepared_for_manual_transfer", "job packet must remain prepared_for_manual_transfer")
    for field in ["progress_percent", "current_step", "completed_at", "output_ready"]:
        require(field not in job, "job packet must not include fake worker runtime field: " + field)


def check_system_core_commands_and_report() -> None:
    system = read(SYSTEM_INTEGRATION)
    for phrase in [
        "android_studio_remote_worker_setup",
        "Android Studio Setup for First Real Android Remote Worker V1",
        r"tools\\setup_android_worker_alpha_adb.py",
        r"tools\\verify_android_worker_alpha_adb_setup.py",
        "bounded ADB file-transfer bridge",
        "no worker execution during push",
    ]:
        require(phrase in system, "System Integration missing: " + phrase)
    core = load_json(CORE_JSON)
    node = core.get("android_studio_remote_worker_setup_v1")
    require(isinstance(node, dict), "Core Continuity setup node missing")
    require(node.get("type") == "android_studio_remote_worker_setup", "Core Continuity setup node type mismatch")
    for label in REQUIRED_STATUS_LABELS:
        require(label in node.get("status", []), "Core Continuity node missing status: " + label)
        require(label in read(CORE_MD), "Core Continuity Markdown missing status: " + label)
    for path in [
        "tools\\setup_android_worker_alpha_adb.py",
        "tools\\verify_android_worker_alpha_adb_setup.py",
        r"memory\ENGEL_ANDROID_STUDIO_REMOTE_WORKER_SETUP_V1.json",
        r"memory\ENGEL_ANDROID_STUDIO_REMOTE_WORKER_SETUP_V1.md",
        r"reports\codex_bridge\ENGEL_ANDROID_STUDIO_REMOTE_WORKER_SETUP_V1.md",
        r"reports\codex_bridge\ENGEL_ANDROID_WORKER_ALPHA_ON_DEVICE_RUN_EXTENSION_V1.md",
    ]:
        require(path in node.get("files", []), "Core Continuity setup node missing file: " + path)
    for key in [
        "android_studio_remote_worker_setup_worker_execution_during_push_enabled_by_map",
        "android_studio_remote_worker_setup_fake_results_enabled_by_map",
        "android_studio_remote_worker_setup_termux_install_automation_enabled_by_map",
        "android_studio_remote_worker_setup_package_install_automation_enabled_by_map",
        "android_studio_remote_worker_setup_hermes_ollama_llama_cpp_enabled_by_map",
        "android_studio_remote_worker_setup_model_runtime_enabled_by_map",
        "android_studio_remote_worker_setup_network_server_enabled_by_map",
        "android_studio_remote_worker_setup_ssh_enabled_by_map",
        "android_studio_remote_worker_setup_cloud_sync_enabled_by_map",
        "android_studio_remote_worker_setup_adb_wireless_enabled_by_map",
        "android_studio_remote_worker_setup_phone_control_loop_enabled_by_map",
        "android_studio_remote_worker_setup_trusted_memory_write_enabled_by_map",
        "android_studio_remote_worker_setup_patch_apply_enabled_by_map",
        "android_studio_remote_worker_setup_background_worker_enabled_by_map",
        "android_studio_remote_worker_setup_startup_autorun_enabled_by_map",
    ]:
        require(core.get("safety", {}).get(key) is False, "Core safety flag should be false: " + key)
    commands = read(COMMANDS)
    for phrase in [
        "android worker alpha adb setup status",
        "android worker alpha adb setup status explicit path",
        "android worker alpha adb prepare commands",
        "android worker alpha adb check python",
        "android worker alpha adb check termux",
        "android worker alpha adb prepare run command",
        "android worker alpha adb prepare phone button commands",
        "android worker alpha adb check phone ui",
        "android worker alpha adb push phone button ui",
        "android worker alpha adb run worker on phone",
        "android worker alpha adb push",
        "android worker alpha adb pull results",
    ]:
        require(phrase in commands, "command docs missing: " + phrase)
    require("tools\\verify_android_worker_alpha_adb_setup.py" in read(CODEX_VERIFY), "codex verifier script missing Android Worker Alpha ADB setup verifier")
    require(REPORT.exists(), "setup report missing")
    report = read(REPORT)
    for phrase in [
        "Android Studio Setup for First Real Android Remote Worker V1",
        "files changed",
        "setup helper behavior",
        "Android Studio/ADB boundary",
        "phone target folder",
        "job packet path",
        "input file path",
        "whether any ADB commands were actually run",
        "whether any files were actually pushed",
        "no worker job was run during setup",
        "no fake status/result/progress/log/receipt was created",
        "no memory was promoted or trusted memory written",
        "no patch apply occurred",
        "verifier results",
        "packaging skipped",
        "working tree note",
    ]:
        require(phrase.lower() in report.lower(), "setup report missing: " + phrase)
    require(FOLLOWUP_REPORT.exists(), "ADB path fix report missing")
    followup = read(FOLLOWUP_REPORT)
    for phrase in [
        "Engel Android Studio ADB Path Fix V1",
        r"C:\Users\ziese\AppData\Local\Android\Sdk",
        r"C:\Users\ziese\AppData\Local\Android\Sdk\platform-tools\adb.exe",
        "ADB discovery behavior",
        "status output summary",
        "prepare-commands behavior",
        "no push was run",
        "no worker job was run",
        "no fake result/status/progress/log/receipt was created",
        "no phone-control loop was created",
        "verifier results",
        "packaging skipped",
    ]:
        require(phrase.lower() in followup.lower(), "ADB path fix report missing: " + phrase)
    require(RUN_EXTENSION_REPORT.exists(), "on-device run extension report missing")
    run_report = read(RUN_EXTENSION_REPORT)
    for phrase in [
        "Engel Android Worker Alpha On-Device Run Extension V1",
        "no second helper/hook was created",
        "--check-python",
        "--check-termux",
        "--prepare-run-command",
        "--run-worker-on-phone",
        "worker was not run",
        "no fake status/result/progress/log/receipt was created",
        "no trusted-memory write occurred",
        "no patch apply occurred",
        "verifier results",
        "packaging skipped",
    ]:
        require(phrase.lower() in run_report.lower(), "on-device run extension report missing: " + phrase)
    if PHONE_BUTTON_UI_REPORT.exists():
        phone_button_report = read(PHONE_BUTTON_UI_REPORT)
        for phrase in [
            "Engel Android Worker Alpha Phone Button UI V1",
            "no duplicate ADB helper was created",
            "--prepare-phone-button-commands",
            "--check-phone-ui",
            "--push-phone-button-ui --i-understand-this-uses-adb",
            "no app/package install occurred",
            "no worker job was run",
            "no fake status/result/progress/log/receipt was created",
            "no trusted-memory write occurred",
            "no patch apply occurred",
            "verifier results",
            "packaging skipped",
        ]:
            require(phrase.lower() in phone_button_report.lower(), "phone button UI report missing: " + phrase)
    if FINISH_SETUP_REPORT.exists():
        finish_report = read(FINISH_SETUP_REPORT)
        for phrase in [
            "Engel Android Worker Alpha Finish Setup V1",
            "--prepare-one-line-termux-finish",
            "--push-finish-runner",
            "--finish-alpha-worker --i-approve-finish-alpha-worker",
            "no fake results were created",
            "no trusted-memory write occurred",
            "no patch apply occurred",
            "verifier results",
            "packaging skipped",
        ]:
            require(phrase.lower() in finish_report.lower(), "finish setup report missing: " + phrase)


def main() -> int:
    checks = [
        ("files_exist", check_files_exist),
        ("contract", check_contract),
        ("helper_static", check_helper_static),
        ("helper_runtime_non_mutating", check_helper_runtime_non_mutating),
        ("no_fake_returned_files_created_by_static_paths", check_no_fake_returned_files_created_by_static_paths),
        ("system_core_commands_and_report", check_system_core_commands_and_report),
    ]
    failures: list[str] = []
    for name, fn in checks:
        try:
            fn()
            print("PASS " + name)
        except CheckFailure as exc:
            failures.append(f"{name}: {exc}")
            print("FAIL " + name + ": " + str(exc))
        except Exception as exc:
            failures.append(f"{name}: unexpected error: {exc}")
            print("FAIL " + name + ": unexpected error: " + str(exc))
    if failures:
        print("\nAndroid Worker Alpha ADB setup verifier FAILED")
        for failure in failures:
            print("- " + failure)
        return 1
    print("\nAndroid Worker Alpha ADB setup verifier PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
