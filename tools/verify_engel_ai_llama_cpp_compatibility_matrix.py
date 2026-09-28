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
MODULE = ROOT / "engel_ai_llama_cpp_compatibility_matrix.py"
VERIFIER = ROOT / "tools" / "verify_engel_ai_llama_cpp_compatibility_matrix.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_AI_LLAMA_CPP_COMPATIBILITY_MATRIX_V1.md"
REPORT_ROOT = ROOT / "reports" / "ai_llama_cpp_compatibility"
DIAGNOSTICS = REPORT_ROOT / "diagnostics"
LOGS = REPORT_ROOT / "logs"
RECEIPTS = REPORT_ROOT / "receipts"
MATRICES = REPORT_ROOT / "matrices"
EXAMPLES = REPORT_ROOT / "examples"
COMMANDS = ROOT / "memory" / "ENGEL_COMMANDS.md"
CODEX_VERIFY = ROOT / "scripts" / "codex_verify.ps1"
READINESS = ROOT / "engel_ai_runtime_readiness.py"
NO_GENERATION_VERIFIER = ROOT / "tools" / "verify_engel_ai_no_generation_load_check.py"
LOCAL_RUNTIME_VERIFIER = ROOT / "tools" / "verify_engel_ai_local_runtime_path_config.py"
OFFLINE_DRY_RUN_VERIFIER = ROOT / "tools" / "verify_engel_ai_offline_runtime_dry_run.py"
READINESS_VERIFIER = ROOT / "tools" / "verify_engel_ai_runtime_readiness.py"

REQUIRED_COMMANDS = [
    "ai llama.cpp compatibility matrix status",
    "ai llama.cpp compatibility matrix inventory",
    "ai llama.cpp compatibility matrix probe-safe",
    "ai llama.cpp compatibility matrix matrix",
    "ai llama.cpp compatibility matrix preview-candidates",
    "ai llama.cpp compatibility matrix probe-candidates",
    "ai llama.cpp compatibility matrix json",
]

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
        REPORT_ROOT,
        DIAGNOSTICS,
        LOGS,
        RECEIPTS,
        MATRICES,
        EXAMPLES,
        COMMANDS,
        CODEX_VERIFY,
        READINESS,
        NO_GENERATION_VERIFIER,
        LOCAL_RUNTIME_VERIFIER,
        OFFLINE_DRY_RUN_VERIFIER,
        READINESS_VERIFIER,
    ]:
        require(path.exists(), "missing required path: " + str(path.relative_to(ROOT)))


def check_static_safety() -> None:
    source = read(MODULE)
    tree = ast.parse(source)
    for needle in [
        "APPROVE_LLAMA_CPP_COMPAT_MATRIX_PROBE",
        "subprocess.Popen",
        "shell=False",
        "timeout=timeout_seconds",
        "terminate()",
        "kill()",
        "subprocess.TimeoutExpired",
        "KeyboardInterrupt",
        "stop_started_process",
        "run_bounded_command",
        "MAX_CANDIDATE_PROBES",
        "SAFE_PROBE_TIMEOUT_SECONDS",
        "CANDIDATE_TIMEOUT_SECONDS",
        "llama-server.exe",
        "rpc-server.exe",
        "inventory_only",
        "safe_to_run_help",
        "safe_to_run_model_probe",
        "--help",
        "--version",
        "--list-devices",
        "--n-predict",
        "N_PREDICT",
        "load check",
        "COMMAND PREVIEW ONLY",
        "LLAMA CPP COMPATIBILITY MATRIX RECORDED",
        "LLAMA CPP COMPATIBILITY PROBE PASSED",
        "LLAMA CPP COMPATIBILITY PROBE BLOCKED",
        "LLAMA CPP COMPATIBILITY PROBE FAILED",
        "normal_inference_enabled",
        "chat_enabled",
        "server_enabled",
        "trusted_memory_write_enabled",
        "runtime_ready_for_inference",
        "source_route_queue_mutation",
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
        "Invoke-WebRequest",
        "curl ",
        "wsl.exe",
        "docker.",
        ".rglob(",
        "os.walk(",
        "write_trusted_memory",
        "normal_inference_enabled\": True",
        "chat_enabled\": True",
        "server_enabled\": True",
        "trusted_memory_write_enabled\": True",
        "runtime_ready_for_inference\": True",
    ]:
        require(forbidden.lower() not in source.lower(), "module contains forbidden behavior text: " + forbidden)
    popen_seen = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                require(alias.name.split(".")[0] not in FORBIDDEN_IMPORTS, "forbidden import: " + alias.name)
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
    require(popen_seen, "module must use bounded subprocess control")


def configure_fixture_module(module, temp: Path) -> list[list[str]]:
    runtime = temp / "runtime"
    runtime.mkdir()
    for name in ["llama-cli.exe", "llama-completion.exe", "llama-server.exe", "rpc-server.exe", "llama-tokenize.exe"]:
        (runtime / name).write_text("fixture exe\n", encoding="utf-8")
    report_root = temp / "reports" / "ai_llama_cpp_compatibility"
    module.REPORT_ROOT = report_root
    module.DIAGNOSTIC_DIR = report_root / "diagnostics"
    module.LOG_DIR = report_root / "logs"
    module.RECEIPT_DIR = report_root / "receipts"
    module.MATRIX_DIR = report_root / "matrices"
    module.EXAMPLE_DIR = report_root / "examples"
    module.RUNTIME_FOLDERS = [runtime]
    module.ensure_folders()

    calls: list[list[str]] = []

    def fake_validate_model(model_key: str):
        if model_key != "tiny_seed":
            return {"valid": False, "reason": "compatibility_matrix_tiny_seed_only", "model_key": model_key}
        return {
            "valid": True,
            "reason": "valid_compatibility_matrix_target",
            "model_key": "tiny_seed",
            "model_tier": "Tiny Seed Mode",
            "model_name": "Qwen2.5-0.5B-Instruct GGUF",
            "model_file_path": str(temp / "tiny.gguf"),
        }

    def fake_run_bounded_command(args, *, timeout_seconds, stdin_text=None):
        calls.append(list(args))
        require(isinstance(args, list), "subprocess args must be explicit list")
        require("llama-server.exe" not in str(args[0]).lower(), "server executable must not be run")
        require("rpc-server.exe" not in str(args[0]).lower(), "rpc server executable must not be run")
        binary = Path(args[0]).name.lower()
        probe = args[1] if len(args) > 1 else ""
        if probe == "--help":
            if binary == "llama-cli.exe":
                stdout = "-m, --model FNAME\n-p, --prompt PROMPT\n-n, --n-predict N\n-c, --ctx-size N\n-t, --threads N\n--simple-io\n--no-display-prompt\n--log-disable\n--no-conversation\n--list-devices\n"
            elif binary == "llama-completion.exe":
                stdout = "-m, --model FNAME\n-p, --prompt PROMPT\n-n, --n-predict N\n-c, --ctx-size N\n-t, --threads N\n--simple-io\n--no-display-prompt\n--log-disable\n--offline\n--no-warmup\n--list-devices\n"
            else:
                stdout = "--help\n--version\n"
        elif probe == "--version":
            stdout = "llama.cpp fixture version\n"
        elif probe == "--list-devices":
            stdout = "CPU fixture\n"
        else:
            stdout = ""
        return module.ExecutionResult(
            command_executed=True,
            runtime_process_started=True,
            runtime_process_exited=True,
            timeout_seconds=timeout_seconds,
            exit_code=0,
            stdout_text=stdout,
            stderr_text="",
            stdout_truncated=False,
            stderr_truncated=False,
            orphan_process_detected=False,
            timed_out=False,
            interrupted=False,
            runtime_process_id=12345,
            cleanup_action=None,
            error=None,
        )

    module.validate_model = fake_validate_model
    module.run_bounded_command = fake_run_bounded_command
    return calls


def check_runtime_behavior() -> None:
    module = load_module("engel_ai_llama_cpp_compatibility_matrix", MODULE)
    with tempfile.TemporaryDirectory() as temp_name:
        temp = Path(temp_name)
        calls = configure_fixture_module(module, temp)

        for command in ["status", "inventory", "probe-safe", "matrix", "json"]:
            code, output = capture_main(module, [command])
            require(code == 0, "command failed: " + command)
            require(output.strip(), "empty output for command: " + command)

        code, output = capture_main(module, ["preview-candidates", "tiny_seed"])
        require(code == 0, "preview-candidates failed")
        preview = json.loads(output)
        require(preview["command_preview_only"] is True, "preview must be marked preview-only")
        require("COMMAND PREVIEW ONLY" in output, "preview must not claim execution")
        require(preview["runtime_ready_for_inference"] is False, "preview must keep runtime not ready")

        code, output = capture_main(module, ["probe-candidates", "tiny_seed", "--approval", "WRONG_TOKEN"])
        require(code == 2 and "approval_token_rejected" in output, "wrong token must refuse")

        code, output = capture_main(module, ["probe-candidates", "daily_local", "--approval", "APPROVE_LLAMA_CPP_COMPAT_MATRIX_PROBE"])
        require(code == 2 and "tiny_seed" in output, "non-tiny model must refuse")

        code, output = capture_main(module, ["probe-candidates", "tiny_seed", "--approval", "APPROVE_LLAMA_CPP_COMPAT_MATRIX_PROBE"])
        require(code == 0, "approved fixture candidate probe should pass")
        payload = json.loads(output)
        require(payload["probe_status"] == "passed", "fixture candidate probe should pass")
        receipt = payload["receipts"][0]
        require(receipt["compatibility_probe_version"] == "1", "receipt version mismatch")
        require(receipt["approval_token_name"] == "APPROVE_LLAMA_CPP_COMPAT_MATRIX_PROBE", "receipt must not store raw token")
        require(receipt["approval_token_verified"] is True, "receipt must verify token")
        require(receipt["model_key"] == "tiny_seed", "receipt must use tiny_seed")
        require(receipt["n_predict"] == 0, "receipt n_predict must be zero")
        require(receipt["candidate_probe_passed"] is True, "fixture receipt should pass")
        require(receipt["runtime_no_generation_check_ready"] is True, "successful probe can mark no-generation ready")
        require(receipt["runtime_ready_for_inference"] is False, "successful probe must not mark inference ready")
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
        ]:
            require(receipt[key] is False, "receipt safety flag must be false: " + key)
        require(any("llama-cli.exe" in call[0] and "-n" in call and "0" in call for call in calls), "fixture must run a no-generation candidate")
        require(not any("llama-server.exe" in call[0].lower() or "rpc-server.exe" in call[0].lower() for call in calls), "server executable must not be run")

        blocked_execution = module.ExecutionResult(
            command_executed=False,
            runtime_process_started=False,
            runtime_process_exited=False,
            timeout_seconds=module.CANDIDATE_TIMEOUT_SECONDS,
            exit_code=None,
            stdout_text="",
            stderr_text="blocked",
            stdout_truncated=False,
            stderr_truncated=False,
            orphan_process_detected=False,
            timed_out=False,
        )
        blocked_receipt = module.receipt_for_execution(None, blocked_execution, module.validate_model("tiny_seed"), created_at="2026-05-17T00:00:00Z", stdout_log_path=None, stderr_log_path=None)
        require(blocked_receipt["final_decision"] == module.FINAL_DECISION_PROBE_BLOCKED, "blocked receipt final decision mismatch")

    readiness = load_module("engel_ai_runtime_readiness_for_compatibility_matrix", READINESS)
    payload = readiness.readiness_payload()
    runtime = payload["runtime_boundaries"]
    require(runtime["runtime_ready_for_inference"] is False, "readiness must keep runtime inference readiness false")
    require(chat_disabled_or_scoped_supervised(runtime), "readiness must keep chat disabled or scoped to supervised local GUI session")


def check_docs_and_registration() -> None:
    report = read(REPORT)
    for needle in [
        "ENGEL_AI_LLAMA_CPP_COMPATIBILITY_MATRIX_V1",
        "bounded llama.cpp compatibility matrix",
        "V1/V2/V3/V4 No-Generation State",
        "Runtime Folders Inspected",
        "Binaries Inventoried",
        "Safe Probes Run",
        "Supported Flag Matrix",
        "Candidate Command Styles",
        "APPROVE_LLAMA_CPP_COMPAT_MATRIX_PROBE",
        "LLAMA CPP COMPATIBILITY MATRIX RECORDED",
        "LLAMA CPP COMPATIBILITY PROBE PASSED",
        "LLAMA CPP COMPATIBILITY PROBE BLOCKED",
        "LLAMA CPP COMPATIBILITY PROBE FAILED",
        "Packaging skipped",
        "This phase builds a bounded llama.cpp compatibility matrix only",
    ]:
        require(needle in report, "report missing required text: " + needle)
    commands = read(COMMANDS)
    for command in REQUIRED_COMMANDS:
        require(command in commands, "commands doc missing: " + command)
    codex = read(CODEX_VERIFY)
    require("tools\\verify_engel_ai_llama_cpp_compatibility_matrix.py" in codex, "codex verifier missing compatibility matrix verifier")


def main() -> int:
    try:
        check_files()
        check_static_safety()
        check_runtime_behavior()
        check_docs_and_registration()
    except CheckFailure as exc:
        print("[FAIL] " + str(exc))
        return 1
    print("[PASS] Engel AI llama.cpp Compatibility Matrix verifier passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
