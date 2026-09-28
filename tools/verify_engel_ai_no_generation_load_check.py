from __future__ import annotations

import ast
from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "engel_ai_no_generation_load_check.py"
VERIFIER = ROOT / "tools" / "verify_engel_ai_no_generation_load_check.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_AI_NO_GENERATION_LOAD_CHECK_V1.md"
REPORT_V2 = ROOT / "reports" / "codex_bridge" / "ENGEL_AI_NO_GENERATION_LOAD_CHECK_V2.md"
REPORT_V3 = ROOT / "reports" / "codex_bridge" / "ENGEL_AI_NO_GENERATION_LOAD_CHECK_V3.md"
REPORT_V4 = ROOT / "reports" / "codex_bridge" / "ENGEL_AI_NO_GENERATION_LOAD_CHECK_V4.md"
REPORT_ROOT = ROOT / "reports" / "ai_no_generation_load_checks"
RECEIPTS = REPORT_ROOT / "receipts"
LOGS = REPORT_ROOT / "logs"
EXAMPLES = REPORT_ROOT / "examples"
DIAGNOSTICS = REPORT_ROOT / "diagnostics"
COMMANDS = ROOT / "memory" / "ENGEL_COMMANDS.md"
CODEX_VERIFY = ROOT / "scripts" / "codex_verify.ps1"
READINESS = ROOT / "engel_ai_runtime_readiness.py"
LOCAL_RUNTIME_VERIFIER = ROOT / "tools" / "verify_engel_ai_local_runtime_path_config.py"
OFFLINE_DRY_RUN_VERIFIER = ROOT / "tools" / "verify_engel_ai_offline_runtime_dry_run.py"
MODEL_APPROVAL_VERIFIER = ROOT / "tools" / "verify_engel_ai_model_review_approval.py"
READINESS_VERIFIER = ROOT / "tools" / "verify_engel_ai_runtime_readiness.py"

FORBIDDEN_IMPORTS = {
    "requests",
    "urllib",
    "socket",
    "webbrowser",
    "threading",
    "multiprocessing",
    "asyncio",
    "http",
    "ftplib",
    "smtplib",
    "openai",
    "anthropic",
}

FORBIDDEN_CALLS = {
    "eval",
    "__import__",
    "compile",
    "system",
    "startfile",
    "run",
    "call",
    "check_call",
    "check_output",
    "rglob",
    "walk",
    "unlink",
    "rename",
}

REQUIRED_COMMANDS = [
    "ai no-generation load check status",
    "ai no-generation load check validate",
    "ai no-generation load check check",
    "ai no-generation load check check-v2",
    "ai no-generation load check check-v3",
    "ai no-generation load check check-v4",
    "ai no-generation load check command-preview",
    "ai no-generation load check command-preview-v3",
    "ai no-generation load check command-preview-v4",
    "ai no-generation load check diagnose-cli",
    "ai no-generation load check probe-minimal",
    "ai no-generation load check list",
    "ai no-generation load check show",
    "ai no-generation load check json",
]


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def load_module(name: str, path: Path):
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location(name, path)
    require(spec is not None and spec.loader is not None, "could not load module: " + path.name)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def chat_disabled_or_scoped_supervised(runtime: dict) -> bool:
    if runtime.get("chat_enabled") is False:
        return True
    return (
        runtime.get("chat_enabled") is True
        and runtime.get("open_chat_enabled") is True
        and runtime.get("chat_scope") == "supervised_local_gui_session_only"
        and runtime.get("open_chat_scope") == "supervised_local_gui_session_only"
        and runtime.get("local_open_chat_supervised_run_available") is True
        and runtime.get("persistent_chat_loop_enabled") is False
        and runtime.get("server_enabled") is False
        and runtime.get("provider_api_enabled") is False
        and runtime.get("trusted_memory_write_enabled") is False
        and runtime.get("runtime_ready_for_inference") is False
    )


def capture_main(module, args: list[str]) -> tuple[int, str]:
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        code = module.main(args)
    return int(code), buffer.getvalue()


def check_files() -> None:
    for path in [
        MODULE,
        VERIFIER,
        REPORT,
        REPORT_V2,
        REPORT_V3,
        REPORT_V4,
        REPORT_ROOT,
        RECEIPTS,
        LOGS,
        EXAMPLES,
        DIAGNOSTICS,
        READINESS,
        LOCAL_RUNTIME_VERIFIER,
        OFFLINE_DRY_RUN_VERIFIER,
        MODEL_APPROVAL_VERIFIER,
        READINESS_VERIFIER,
    ]:
        require(path.exists(), "missing required path: " + str(path.relative_to(ROOT)))


def check_static_safety() -> None:
    source = read(MODULE)
    tree = ast.parse(source)
    for needle in [
        "APPROVE_NO_GENERATION_LOAD_CHECK",
        "subprocess.Popen",
        "shell=False",
        "timeout=timeout_seconds",
        "terminate()",
        "kill()",
        "subprocess.TimeoutExpired",
        "KeyboardInterrupt",
        "stop_started_process",
        "run_cli_help_check",
        "run_diagnostic_command",
        "build_no_generation_command_plan",
        "build_no_generation_command_plan_v3",
        "build_no_generation_command_plan_v4",
        "completion_binary_for_runtime",
        "direct_runtime_binary_inventory",
        "run_minimal_exit_probes",
        "check-v2",
        "check-v3",
        "check-v4",
        "command-preview",
        "command-preview-v3",
        "command-preview-v4",
        "diagnose-cli",
        "probe-minimal",
        "interrupted",
        "timeout_expired",
        "keyboard_interrupt",
        "DEFAULT_V2_TIMEOUT_SECONDS",
        "DEFAULT_V3_TIMEOUT_SECONDS",
        "DEFAULT_V4_TIMEOUT_SECONDS",
        "MINIMAL_PROBE_TIMEOUT_SECONDS",
        "--n-predict",
        "str(N_PREDICT)",
        "--prompt",
        "load check",
        "--no-conversation",
        "--no-display-prompt",
        "--log-disable",
        "--offline",
        "--simple-io",
        "--no-warmup",
        "--list-devices",
        "llama-completion.exe",
        "llama-bench.exe",
        "llama-server.exe",
        "stdin=subprocess.DEVNULL",
        "command_style",
        "selected_prompt_flag",
        "non_interactive_mode",
        "stdin_mode",
        "help_checked",
        "server_enabled",
        "chat_enabled",
        "runtime_ready_for_inference",
        "runtime_process_id",
        "cleanup_action",
        "V2 FAILED OR BLOCKED",
        "V3 FAILED OR BLOCKED",
        "V4 BLOCKED",
        "FAILED OR INTERRUPTED",
        "NO-GENERATION LOAD CHECK",
    ]:
        require(needle in source, "module missing required safety text: " + needle)
    for forbidden in [
        "shell=True",
        "subprocess.run",
        "ollama",
        "requests.",
        "socket.",
        "webbrowser.",
        "openai.",
        "anthropic.",
        "pip install",
        "invoke-webrequest",
        "curl ",
        "wsl.exe",
        "docker.",
        ".rglob(",
        "os.walk(",
        "write_trusted_memory",
        "auto_load_enabled\": True",
        "normal_inference_enabled\": True",
    ]:
        require(forbidden.lower() not in source.lower(), "module contains forbidden behavior text: " + forbidden)
    popen_seen = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                require(root not in FORBIDDEN_IMPORTS, "forbidden import: " + alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            require(node.module.split(".")[0] not in FORBIDDEN_IMPORTS, "forbidden import: " + node.module)
        elif isinstance(node, ast.While):
            raise CheckFailure("module contains forbidden worker loop")
        elif isinstance(node, ast.Call):
            func = node.func
            name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ""
            if isinstance(func, ast.Name) and name == "exec":
                raise CheckFailure("module contains forbidden call: exec")
            require(name not in FORBIDDEN_CALLS, "module contains forbidden call: " + name)
            if isinstance(func, ast.Attribute) and func.attr == "Popen":
                popen_seen = True
                shell_keywords = [kw for kw in node.keywords if kw.arg == "shell"]
                require(shell_keywords, "Popen must set shell explicitly")
                require(isinstance(shell_keywords[0].value, ast.Constant) and shell_keywords[0].value.value is False, "Popen shell must be false")
    require(popen_seen, "module must use a bounded process start for the explicit check")


def check_runtime_behavior() -> None:
    module = load_module("engel_ai_no_generation_load_check", MODULE)
    for command in ["status", "list", "json"]:
        code, output = capture_main(module, [command])
        require(code == 0, "command failed: " + command)
        require(output.strip(), "empty output for command: " + command)
    unknown = module.validate_model("unknown_model")
    require(unknown["valid"] is False and unknown["reason"] == "unknown_model_key", "unknown model key must refuse")

    code, output = capture_main(module, ["check", "tiny_seed", "--approval", "WRONG_TOKEN"])
    require(code == 2 and "approval_token_rejected" in output, "wrong token must refuse")

    with tempfile.TemporaryDirectory() as temp_name:
        temp = Path(temp_name)
        fake_model = temp / "tiny-fixture.gguf"
        fake_model.write_bytes(b"GGUF no-generation verifier fixture\n")
        approval_manifest = temp / "approval_manifest.json"
        runtime_config = temp / "missing_runtime_config.json"
        dry_manifest = temp / "dry_run_manifest.json"
        approval_manifest.write_text(
            json.dumps(
                {
                    "entries": [
                        {
                            "model_tier": "Tiny Seed Mode",
                            "model_name": "Qwen2.5-0.5B-Instruct GGUF",
                            "model_file_path": str(fake_model),
                            "approved_for_runtime_dry_run": True,
                            "runtime_dry_run_eligible": True,
                            "inference_enabled": False,
                            "auto_load_enabled": False,
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        dry_manifest.write_text(
            json.dumps(
                {
                    "entries": [
                        {
                            "model_key": "tiny_seed",
                            "runtime_dry_run_ready": True,
                            "runtime_binary_present": False,
                            "inference_enabled": False,
                            "auto_load_enabled": False,
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        original_paths = (
            module.MODEL_APPROVAL_MANIFEST,
            module.RUNTIME_PATH_CONFIG,
            module.RUNTIME_DRY_RUN_MANIFEST,
        )
        module.MODEL_APPROVAL_MANIFEST = approval_manifest
        module.RUNTIME_PATH_CONFIG = runtime_config
        module.RUNTIME_DRY_RUN_MANIFEST = dry_manifest
        try:
            missing_runtime = module.validate_model("tiny_seed")
            require(missing_runtime["valid"] is False, "missing runtime path must refuse")
            require(missing_runtime["reason"] in {"runtime_path_not_approved", "runtime_binary_missing"}, "missing runtime reason mismatch")
            code, output = capture_main(module, ["check", "tiny_seed", "--approval", "APPROVE_NO_GENERATION_LOAD_CHECK"])
            require(code == 2 and "runtime_" in output, "approved check must refuse if runtime config is missing")
        finally:
            (
                module.MODEL_APPROVAL_MANIFEST,
                module.RUNTIME_PATH_CONFIG,
                module.RUNTIME_DRY_RUN_MANIFEST,
            ) = original_paths

    validation = {
        "model_key": "tiny_seed",
        "model_tier": "Tiny Seed Mode",
        "model_name": "Qwen2.5-0.5B-Instruct GGUF",
        "model_file_path": r"G:\ENGEL_APP_MEMORY\models\manual_downloads\qwen2.5-0.5b-instruct\tiny.gguf",
        "runtime": {
            "runtime_binary_path": r"E:\ENGEL_APP_MEMORY\runtimes\llama.cpp\llama-win-x64\llama-cli.exe",
        },
    }
    command = module.build_no_generation_command(validation["runtime"]["runtime_binary_path"], validation["model_file_path"])
    require(isinstance(command, list), "command must be an explicit argument list")
    require("--n-predict" in command and "0" in command, "command must request zero prediction")
    require("--prompt" in command and "load check" in command, "command must use the fixed inert prompt")
    require("--no-conversation" in command, "V2 command must explicitly disable conversation auto-mode")
    require("--no-display-prompt" in command, "V2 command must suppress prompt display when supported")
    require("--log-disable" in command, "V2 command must disable llama logging when supported")
    require("--offline" in command, "V2 command must force llama offline mode when supported")
    for forbidden_arg in ["--server", "--interactive", "-i", "--conversation", "--chat", "--host", "--port", "--model-url", "--hf-repo", "--docker-repo"]:
        require(forbidden_arg not in command, "command must not use server, chat, or interactive mode: " + forbidden_arg)
    for unsafe_command in [
        command + ["--interactive"],
        command + ["--server"],
        [r"E:\ENGEL_APP_MEMORY\runtimes\llama.cpp\llama-win-x64\llama-server.exe"] + command[1:],
    ]:
        try:
            module.validate_command_args(unsafe_command)
        except module.LoadCheckError:
            pass
        else:
            raise CheckFailure("unsafe command argument was accepted")
    help_result = module.HelpCheckResult(
        help_checked=True,
        help_check_command_executed=True,
        help_check_process_started=True,
        help_check_exit_code=0,
        help_check_timed_out=False,
        help_check_interrupted=False,
        help_text="-p, --prompt PROMPT\n-n, --n-predict N\n--no-conversation\n--no-display-prompt\n--log-disable\n--offline\n--simple-io\n",
        help_text_truncated=False,
    )
    command_plan = module.build_no_generation_command_plan(validation["runtime"]["runtime_binary_path"], validation["model_file_path"], help_result)
    require(command_plan.command_style == "prompt_argument_no_generation", "V2 command style mismatch")
    require(command_plan.stdin_mode == "devnull", "V2 prompt-argument command must use DEVNULL stdin")
    require(command_plan.non_interactive_mode is True, "V2 command plan must be non-interactive")
    require("--no-conversation" in command_plan.args, "V2 plan must disable conversation mode")
    require("--simple-io" in command_plan.args, "V2 plan must use simple IO when supported")
    completion_help = module.HelpCheckResult(
        help_checked=True,
        help_check_command_executed=True,
        help_check_process_started=True,
        help_check_exit_code=0,
        help_check_timed_out=False,
        help_check_interrupted=False,
        help_text="-p, --prompt PROMPT\n-n, --n-predict N\n--no-display-prompt\n--log-disable\n--offline\n--simple-io\n--no-warmup\n",
        help_text_truncated=False,
    )
    command_plan_v3 = module.build_no_generation_command_plan_v3(validation["runtime"]["runtime_binary_path"], validation["model_file_path"], help_result, completion_help)
    require(command_plan_v3.command_style == "llama_completion_prompt_no_generation", "V3 command style mismatch")
    require(command_plan_v3.execution_binary_path.endswith("llama-completion.exe"), "V3 must select llama-completion sibling")
    require(command_plan_v3.stdin_mode == "devnull", "V3 prompt-argument command must use DEVNULL stdin")
    require(command_plan_v3.non_interactive_mode is True, "V3 command plan must be non-interactive")
    require("--no-conversation" not in command_plan_v3.args, "V3 completion command must avoid llama-cli-only conversation flag")
    require("--no-warmup" in command_plan_v3.args, "V3 command must disable warmup when supported")
    require("--n-predict" in command_plan_v3.args and "0" in command_plan_v3.args, "V3 command must request zero prediction")
    runtime_folder, inventory = module.direct_runtime_binary_inventory(validation["runtime"]["runtime_binary_path"])
    require(runtime_folder.endswith("llama-win-x64"), "V4 inventory must stay inside the direct runtime folder")
    require([row["binary"] for row in inventory] == ["llama-cli.exe", "llama-completion.exe", "llama-bench.exe", "llama-server.exe"], "V4 inventory must record expected direct binaries")
    require(any(row["server_mode_forbidden"] is True for row in inventory if row["binary"] == "llama-server.exe"), "V4 must mark server binary as forbidden inventory only")
    v4_probe_payload = {
        "safe_candidate_identified": False,
        "blocked_reason": "fixture_no_clean_exit_mode",
        "minimal_probe_results": [],
        "no_model_probe_results": [],
    }
    command_plan_v4, blocked_reason = module.build_no_generation_command_plan_v4(validation, v4_probe_payload)
    require(command_plan_v4 is None, "V4 fixture must block when no clean exit candidate is identified")
    require(blocked_reason == "fixture_no_clean_exit_mode", "V4 blocked reason mismatch")
    execution = module.ExecutionResult(
        command_executed=True,
        runtime_process_started=True,
        runtime_process_exited=True,
        timeout_seconds=120,
        exit_code=0,
        stdout_text="",
        stderr_text="",
        stdout_truncated=False,
        stderr_truncated=False,
        orphan_process_detected=False,
        timed_out=False,
    )
    receipt = module.build_receipt_payload(validation, command_plan.args, execution, command_plan=command_plan, created_at="2026-05-17T00:00:00Z")
    require(receipt["no_generation_load_check_version"] == "2", "V2 receipt version mismatch")
    require(receipt["command_style"] == "prompt_argument_no_generation", "V2 receipt command style mismatch")
    require(receipt["selected_prompt_flag"] == "--prompt", "V2 receipt prompt flag mismatch")
    require(receipt["non_interactive_mode"] is True, "V2 receipt must be non-interactive")
    require(receipt["stdin_mode"] == "devnull", "V2 receipt stdin mode mismatch")
    require(receipt["help_checked"] is True and receipt["help_check_exit_code"] == 0, "V2 receipt must record help check")
    for key in [
        "no_generation_requested",
        "command_executed",
        "runtime_process_started",
        "runtime_process_exited",
        "approval_token_verified",
    ]:
        require(receipt[key] is True, "receipt value must be true: " + key)
    require(receipt["n_predict"] == 0, "receipt n_predict must be zero")
    for key in [
        "normal_inference_enabled",
        "chat_enabled",
        "server_enabled",
        "auto_load_enabled",
        "trusted_memory_write_enabled",
        "provider_api_enabled",
        "source_route_queue_mutation",
        "orphan_process_detected",
        "timed_out",
        "interrupted",
        "runtime_ready_for_inference",
    ]:
        require(receipt[key] is False, "receipt value must be false: " + key)
    require(receipt["final_decision"] == module.FINAL_DECISION_V2_PASS, "passing receipt must use V2 pass final decision")
    receipt_v3 = module.build_receipt_payload(validation, command_plan_v3.args, execution, version="3", command_plan=command_plan_v3, created_at="2026-05-17T00:00:02Z")
    require(receipt_v3["no_generation_load_check_version"] == "3", "V3 receipt version mismatch")
    require(receipt_v3["diagnosis_mode"] is True, "V3 receipt must record diagnosis mode")
    require(receipt_v3["execution_binary_path"].endswith("llama-completion.exe"), "V3 receipt must record execution binary")
    require(receipt_v3["selected_command_style"] == "llama_completion_prompt_no_generation", "V3 receipt command style mismatch")
    require(receipt_v3["no_generation_load_check_passed"] is True, "V3 fixture receipt should pass")
    require(receipt_v3["final_decision"] == module.FINAL_DECISION_V3_PASS, "passing receipt must use V3 pass final decision")
    blocked_execution = module.ExecutionResult(
        command_executed=False,
        runtime_process_started=False,
        runtime_process_exited=False,
        timeout_seconds=module.DEFAULT_V4_TIMEOUT_SECONDS,
        exit_code=None,
        stdout_text="",
        stderr_text="fixture blocked",
        stdout_truncated=False,
        stderr_truncated=False,
        orphan_process_detected=False,
        timed_out=False,
    )
    receipt_v4 = module.build_receipt_payload(validation, [], blocked_execution, version="4", created_at="2026-05-17T00:00:03Z")
    require(receipt_v4["no_generation_load_check_version"] == "4", "V4 receipt version mismatch")
    require(receipt_v4["diagnosis_mode"] is True, "V4 receipt must record diagnosis mode")
    require(receipt_v4["command_executed"] is False, "V4 blocked receipt must not claim command execution")
    require(receipt_v4["runtime_process_started"] is False, "V4 blocked receipt must not claim process start")
    require(receipt_v4["model_load_check_attempted"] is False, "V4 blocked receipt must not claim model load")
    require(receipt_v4["no_generation_requested"] is True, "V4 blocked receipt must preserve no-generation request")
    require(receipt_v4["n_predict"] == 0, "V4 receipt n_predict must be zero")
    require(receipt_v4["final_decision"] == module.FINAL_DECISION_V4_BLOCKED, "V4 blocked receipt must use blocked final decision")
    for key in [
        "normal_inference_enabled",
        "chat_enabled",
        "server_enabled",
        "auto_load_enabled",
        "trusted_memory_write_enabled",
        "provider_api_enabled",
        "source_route_queue_mutation",
        "runtime_ready_for_inference",
    ]:
        require(receipt_v4[key] is False, "V4 receipt value must be false: " + key)
    long_text, truncated = module.bounded_text("x" * (module.MAX_LOG_CHARS + 20))
    require(truncated is True and len(long_text) <= module.MAX_LOG_CHARS + 20, "logs must be bounded")

    original_popen = module.subprocess.Popen

    class TimeoutProcess:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs
            self.pid = 41001
            self.returncode = None
            self.terminated = False
            self.killed = False
            self.communicate_calls = 0

        def communicate(self, input=None, timeout=None):
            self.communicate_calls += 1
            if self.communicate_calls == 1:
                raise module.subprocess.TimeoutExpired(cmd=command, timeout=timeout)
            self.returncode = -15
            return "timeout stdout", "timeout stderr"

        def terminate(self):
            self.terminated = True

        def kill(self):
            self.killed = True
            self.returncode = -9

        def poll(self):
            return self.returncode

    class KeyboardProcess(TimeoutProcess):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.pid = 41002

        def communicate(self, input=None, timeout=None):
            self.communicate_calls += 1
            if self.communicate_calls == 1:
                raise KeyboardInterrupt
            self.returncode = -15
            return "interrupt stdout", "interrupt stderr"

    try:
        timeout_processes = []

        def fake_timeout_popen(*args, **kwargs):
            process = TimeoutProcess(*args, **kwargs)
            timeout_processes.append(process)
            return process

        module.subprocess.Popen = fake_timeout_popen
        timeout_result = module.execute_no_generation_command(command, timeout_seconds=1)
        require(timeout_processes and timeout_processes[0].terminated is True, "timeout must terminate the started process")
        require(timeout_result.timed_out is True, "timeout result must record timed_out")
        require(timeout_result.interrupted is False, "timeout result must not record interrupted")
        require(timeout_result.runtime_process_started is True, "timeout result must record process start")
        require(timeout_result.runtime_process_exited is True, "timeout result must record process exit")
        require(timeout_result.orphan_process_detected is False, "timeout fixture must not report an orphan")
        require(timeout_result.runtime_process_id == 41001, "timeout result must record started process id")

        keyboard_processes = []

        def fake_keyboard_popen(*args, **kwargs):
            process = KeyboardProcess(*args, **kwargs)
            keyboard_processes.append(process)
            return process

        module.subprocess.Popen = fake_keyboard_popen
        interrupt_result = module.execute_no_generation_command(command, timeout_seconds=120)
        require(keyboard_processes and keyboard_processes[0].terminated is True, "KeyboardInterrupt must terminate the started process")
        require(interrupt_result.interrupted is True, "KeyboardInterrupt result must record interrupted")
        require(interrupt_result.timed_out is False, "KeyboardInterrupt result must not record timed_out")
        require(interrupt_result.runtime_process_exited is True, "KeyboardInterrupt result must record process exit")
        require(interrupt_result.orphan_process_detected is False, "KeyboardInterrupt fixture must not report an orphan")
        require(interrupt_result.error and "keyboard_interrupt" in interrupt_result.error, "KeyboardInterrupt result must record error")
        interrupt_receipt = module.build_receipt_payload(validation, command_plan.args, interrupt_result, command_plan=command_plan, created_at="2026-05-17T00:00:01Z")
        require(interrupt_receipt["interrupted"] is True, "interrupted receipt must record interrupted")
        require(interrupt_receipt["no_generation_load_check_passed"] is False, "interrupted receipt must fail")
        require(interrupt_receipt["runtime_no_generation_check_ready"] is False, "interrupted receipt must not ready runtime")
        require(interrupt_receipt["final_decision"] == module.FINAL_DECISION_V2_INTERRUPTED, "interrupted receipt must use V2 interrupted final decision")

        def fake_raising_popen(*args, **kwargs):
            raise OSError("fixture launch failure")

        module.subprocess.Popen = fake_raising_popen
        launch_failure = module.execute_no_generation_command(command, timeout_seconds=1)
        require(launch_failure.command_executed is False, "launch failure must not claim command execution")
        require(launch_failure.runtime_process_started is False, "launch failure must not claim process start")
    finally:
        module.subprocess.Popen = original_popen

    readiness = load_module("engel_ai_runtime_readiness_for_no_generation", READINESS)
    payload = readiness.readiness_payload()
    runtime = payload["runtime_boundaries"]
    require(runtime["no_generation_load_check_module_present"] is True, "readiness must see no-generation module")
    require(runtime["runtime_ready_for_inference"] is False, "readiness must keep runtime inference readiness false")
    require(chat_disabled_or_scoped_supervised(runtime), "readiness must keep chat disabled or scoped to supervised local GUI session")
    require(payload["safety_flags"]["inference_enabled"] is False, "readiness inference flag must remain false")


def check_docs_and_registration() -> None:
    report = read(REPORT)
    for needle in [
        "ENGEL_AI_NO_GENERATION_LOAD_CHECK_V1",
        "no-generation",
        "no chat",
        "no server",
        "APPROVE_NO_GENERATION_LOAD_CHECK",
        "n_predict=0",
        "KeyboardInterrupt",
        "FAILED OR INTERRUPTED",
        "Packaging skipped",
    ]:
        require(needle in report, "report missing required text: " + needle)
    report_v2 = read(REPORT_V2)
    for needle in [
        "ENGEL_AI_NO_GENERATION_LOAD_CHECK_V2",
        "Non-Interactive Exit Fix",
        "check-v2",
        "command-preview",
        "diagnose-cli",
        "--no-conversation",
        "--simple-io",
        "--n-predict 0",
        "NO-GENERATION LOAD CHECK V2 RECORDED",
        "NO-GENERATION LOAD CHECK V2 FAILED OR BLOCKED",
        "NO-GENERATION LOAD CHECK V2 FAILED OR INTERRUPTED",
        "Packaging skipped",
    ]:
        require(needle in report_v2, "V2 report missing required text: " + needle)
    report_v3 = read(REPORT_V3)
    for needle in [
        "ENGEL_AI_NO_GENERATION_LOAD_CHECK_V3",
        "llama-cli Exit Compatibility Diagnosis",
        "check-v3",
        "command-preview-v3",
        "diagnose-cli",
        "llama-completion.exe",
        "llama_completion_prompt_no_generation",
        "--n-predict 0",
        "NO-GENERATION LOAD CHECK V3 RECORDED",
        "NO-GENERATION LOAD CHECK V3 FAILED OR BLOCKED",
        "NO-GENERATION LOAD CHECK V3 FAILED OR INTERRUPTED",
        "Packaging skipped",
    ]:
        require(needle in report_v3, "V3 report missing required text: " + needle)
    report_v4 = read(REPORT_V4)
    for needle in [
        "ENGEL_AI_NO_GENERATION_LOAD_CHECK_V4",
        "llama.cpp Minimal Exit Probe",
        "probe-minimal",
        "check-v4",
        "command-preview-v4",
        "llama-cli.exe --help",
        "llama-cli.exe --version",
        "llama-completion.exe --help",
        "llama-completion.exe --version",
        "llama-server.exe",
        "--list-devices",
        "NO-GENERATION LOAD CHECK V4 RECORDED",
        "NO-GENERATION LOAD CHECK V4 BLOCKED",
        "NO-GENERATION LOAD CHECK V4 FAILED",
        "NO-GENERATION LOAD CHECK V4 FAILED OR INTERRUPTED",
        "Packaging skipped",
        "This phase probes llama.cpp exit compatibility only",
    ]:
        require(needle in report_v4, "V4 report missing required text: " + needle)
    commands = read(COMMANDS)
    for command in REQUIRED_COMMANDS:
        require(command in commands, "command docs missing: " + command)
    codex = read(CODEX_VERIFY)
    require("tools\\verify_engel_ai_no_generation_load_check.py" in codex, "codex verifier missing no-generation verifier")


def main() -> int:
    try:
        check_files()
        check_static_safety()
        check_runtime_behavior()
        check_docs_and_registration()
    except CheckFailure as exc:
        print("[FAIL] " + str(exc))
        return 1
    print("[PASS] Engel AI No-Generation Load Check verifier passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
