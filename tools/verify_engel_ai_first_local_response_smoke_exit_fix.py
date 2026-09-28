from __future__ import annotations

import ast
from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "engel_ai_first_local_response_smoke_exit_fix.py"
VERIFIER = ROOT / "tools" / "verify_engel_ai_first_local_response_smoke_exit_fix.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_AI_FIRST_LOCAL_RESPONSE_SMOKE_EXIT_FIX_V1.md"
REPORT_ROOT = ROOT / "reports" / "ai_first_local_response_smoke_exit_fix"
DIAGNOSTICS = REPORT_ROOT / "diagnostics"
LOGS = REPORT_ROOT / "logs"
RECEIPTS = REPORT_ROOT / "receipts"
PLAN_REPORTS = REPORT_ROOT / "reports"
EXAMPLES = REPORT_ROOT / "examples"
COMMANDS = ROOT / "memory" / "ENGEL_COMMANDS.md"
CODEX_VERIFY = ROOT / "scripts" / "codex_verify.ps1"
READINESS = ROOT / "engel_ai_runtime_readiness.py"
V1_RECEIPTS = ROOT / "reports" / "ai_first_local_response_smoke" / "receipts"
SWAP_RECEIPTS = ROOT / "reports" / "ai_llama_cpp_runtime_swap_approval" / "receipts"

FIRST_SMOKE_VERIFIER = ROOT / "tools" / "verify_engel_ai_first_local_response_smoke.py"
SWAP_APPROVAL_VERIFIER = ROOT / "tools" / "verify_engel_ai_llama_cpp_runtime_swap_approval.py"
ALT_STYLE_VERIFIER = ROOT / "tools" / "verify_engel_ai_runtime_candidate_alt_command_style.py"
REPLAY_VERIFIER = ROOT / "tools" / "verify_engel_ai_runtime_candidate_validation_replay.py"
FAILURE_DIAGNOSIS_VERIFIER = ROOT / "tools" / "verify_engel_ai_runtime_candidate_failure_diagnosis.py"
CANDIDATE_VALIDATION_VERIFIER = ROOT / "tools" / "verify_engel_ai_llama_cpp_runtime_candidate_validation.py"
SWAP_PLAN_VERIFIER = ROOT / "tools" / "verify_engel_ai_llama_cpp_runtime_swap_plan.py"
COMPATIBILITY_VERIFIER = ROOT / "tools" / "verify_engel_ai_llama_cpp_compatibility_matrix.py"
NO_GENERATION_VERIFIER = ROOT / "tools" / "verify_engel_ai_no_generation_load_check.py"
MEMORY_ROOTS_VERIFIER = ROOT / "tools" / "verify_engel_memory_roots_storage_layout.py"
READINESS_VERIFIER = ROOT / "tools" / "verify_engel_ai_runtime_readiness.py"

REQUIRED_COMMANDS = [
    "ai first local response smoke exit fix status",
    "ai first local response smoke exit fix diagnose-latest",
    "ai first local response smoke exit fix preview",
    "ai first local response smoke exit fix run",
    "ai first local response smoke exit fix json",
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
    "call",
    "check_call",
    "check_output",
    "rglob",
    "walk",
    "unlink",
    "rename",
}

CHAIN_VERIFIERS = [
    FIRST_SMOKE_VERIFIER,
    SWAP_APPROVAL_VERIFIER,
    ALT_STYLE_VERIFIER,
    REPLAY_VERIFIER,
    FAILURE_DIAGNOSIS_VERIFIER,
    CANDIDATE_VALIDATION_VERIFIER,
    SWAP_PLAN_VERIFIER,
    COMPATIBILITY_VERIFIER,
    NO_GENERATION_VERIFIER,
    MEMORY_ROOTS_VERIFIER,
    READINESS_VERIFIER,
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
        PLAN_REPORTS,
        EXAMPLES,
        COMMANDS,
        CODEX_VERIFY,
        READINESS,
        V1_RECEIPTS,
        SWAP_RECEIPTS,
        *CHAIN_VERIFIERS,
    ]:
        require(path.exists(), "missing required path: " + str(path.relative_to(ROOT)))


def check_static_safety() -> None:
    source = read(MODULE)
    tree = ast.parse(source)
    for needle in [
        "APPROVE_FIRST_LOCAL_RESPONSE_SMOKE_EXIT_FIX",
        "8be9dbf",
        "Reply with exactly: Engel",
        "tiny_seed",
        "qwen2.5-0.5b-instruct-q5_k_m.gguf",
        "llama-cli.exe",
        "llama-server.exe",
        "rpc-server.exe",
        "subprocess.Popen",
        "stdin=subprocess.DEVNULL",
        "shell=False",
        "timeout=timeout_seconds",
        "TimeoutExpired",
        "terminate()",
        "kill()",
        "--simple-io",
        "--no-display-prompt",
        "--single-turn",
        "--no-conversation",
        "selected_command_style",
        "expected_token_seen",
        "disqualifying_interactive_markers_found",
        "output_marked_untrusted",
        "model_output_trusted",
        "persistent_chat_loop_enabled",
        "runtime_ready_for_inference",
        "FIRST LOCAL RESPONSE SMOKE EXIT FIX PASSED",
        "FIRST LOCAL RESPONSE SMOKE EXIT FIX BLOCKED",
    ]:
        require(needle in source, "module missing required text: " + needle)
    for forbidden in [
        "shell=True",
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
        "trusted_memory_write_enabled\": True",
        "model_output_trusted\": True",
        "chat_enabled\": True",
        "server_enabled\": True",
        "persistent_chat_loop_enabled\": True",
        "runtime_ready_for_inference\": True",
        "inference_enabled\": True",
        "user_content_used_as_prompt\": True",
    ]:
        require(forbidden.lower() not in source.lower(), "module contains forbidden behavior text: " + forbidden)
    popen_seen = False
    marker_seen = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                require(alias.name.split(".")[0] not in FORBIDDEN_IMPORTS, "forbidden import: " + alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            require(node.module.split(".")[0] not in FORBIDDEN_IMPORTS, "forbidden import: " + node.module)
        elif isinstance(node, ast.While):
            raise CheckFailure("module contains forbidden persistent loop")
        elif isinstance(node, ast.Call):
            func = node.func
            name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ""
            if isinstance(func, ast.Name) and name == "exec":
                raise CheckFailure("module contains forbidden call: exec")
            require(name not in FORBIDDEN_CALLS, "module contains forbidden call: " + name)
            if isinstance(func, ast.Attribute) and func.attr == "Popen":
                popen_seen = True
                shell_keywords = [kw for kw in node.keywords if kw.arg == "shell"]
                stdin_keywords = [kw for kw in node.keywords if kw.arg == "stdin"]
                require(shell_keywords, "Popen missing shell keyword")
                require(isinstance(shell_keywords[0].value, ast.Constant) and shell_keywords[0].value.value is False, "Popen shell must be false")
                require(stdin_keywords, "Popen missing stdin keyword")
            if isinstance(func, ast.Attribute) and func.attr == "run":
                shell_keywords = [kw for kw in node.keywords if kw.arg == "shell"]
                require(shell_keywords, "subprocess.run missing shell keyword")
                require(isinstance(shell_keywords[0].value, ast.Constant) and shell_keywords[0].value.value is False, "subprocess.run shell must be false")
                require(node.args and isinstance(node.args[0], ast.List), "subprocess.run must use explicit args")
            if isinstance(func, ast.Name) and name == "marker_analysis":
                marker_seen = True
    require(popen_seen, "module must use one bounded Popen path for approved exit-fix smoke")
    require(marker_seen, "module must analyze disqualifying interactive markers")


def check_runtime_commands_and_token_refusals() -> None:
    module = load_module("engel_ai_first_local_response_smoke_exit_fix_commands", MODULE)
    for command in ["status", "diagnose-latest", "preview", "json"]:
        code, output = capture_main(module, [command])
        require(code == 0, "command failed: " + command)
        require(output.strip(), "empty output for command: " + command)
        parsed = json.loads(output)
        if command == "diagnose-latest":
            require(parsed["source_first_local_response_smoke_receipt"], "diagnosis missing source receipt")
            require(parsed["stdout_stderr_treated_as_untrusted"] is True, "diagnosis must keep logs untrusted")
            require("interactive_wait_after_output" in parsed["classifications"], "diagnosis must classify interactive wait")
        if command == "preview":
            require("COMMAND PREVIEW ONLY — NOT EXECUTED" in parsed["command_preview"], "preview missing inert label")
            require(parsed["prompt"] == "Reply with exactly: Engel", "preview prompt mismatch")
            require(parsed["user_content_used_as_prompt"] is False, "preview must reject user prompt content")
            require(parsed["n_predict"] in {4, 8}, "n_predict must be bounded")
            require(parsed["selected_command_style_supported"] is True, "selected command style must be help-supported")
            require("--single-turn" in parsed["command_args"], "selected style must include single-turn exit guard")
            require(parsed["stdin_mode"] == "devnull", "stdin must be devnull")
            for forbidden in ["llama-server.exe", "rpc-server.exe"]:
                require(forbidden not in " ".join(parsed["command_args"]).lower(), "preview selected server executable")

    before_receipts = sorted(RECEIPTS.glob("FIRST_LOCAL_RESPONSE_SMOKE_EXIT_FIX_*.json"))
    code, output = capture_main(module, ["run"])
    require(code != 0, "run without token must refuse")
    refused = json.loads(output)
    require(refused.get("approval_token_verified") is False, "missing token was accepted")
    require(refused.get("command_executed") is False, "missing token executed command")
    code, output = capture_main(module, ["run", "--approval", "WRONG"])
    require(code != 0, "run wrong token must refuse")
    refused = json.loads(output)
    require(refused.get("approval_token_verified") is False, "wrong token was accepted")
    require(refused.get("command_executed") is False, "wrong token executed command")
    require(sorted(RECEIPTS.glob("FIRST_LOCAL_RESPONSE_SMOKE_EXIT_FIX_*.json")) == before_receipts, "wrong/missing token wrote receipt")


def check_source_receipts() -> None:
    v1_receipts = sorted(V1_RECEIPTS.glob("FIRST_LOCAL_RESPONSE_SMOKE_*.json"))
    require(v1_receipts, "missing V1 first local response smoke receipt")
    latest_v1 = json.loads(read(v1_receipts[-1]))
    require(latest_v1.get("command_executed") is True, "source V1 smoke must have run")
    require(latest_v1.get("error") == "keyboard_interrupt", "source V1 failure should be keyboard_interrupt")
    require(latest_v1.get("exit_code") == 130, "source V1 exit code should be 130")
    require(latest_v1.get("expected_token_seen") is True, "source V1 should have seen expected token")
    require(latest_v1.get("output_marked_untrusted") is True, "source V1 output must be untrusted")
    require(latest_v1.get("runtime_ready_for_inference") is False, "source V1 runtime_ready must remain false")

    swap_receipts = sorted(SWAP_RECEIPTS.glob("RUNTIME_SWAP_APPROVAL_*.json"))
    require(swap_receipts, "missing runtime swap approval receipt")
    latest_swap = json.loads(read(swap_receipts[-1]))
    require(latest_swap.get("runtime_swap_approval_recorded") is True, "swap approval must be recorded")
    require(str(latest_swap.get("candidate_runtime_binary_path", "")).endswith("llama-cli.exe"), "approved runtime must be llama-cli")
    require(latest_swap.get("runtime_ready_for_inference") is False, "swap approval must keep runtime_ready false")
    require(latest_swap.get("chat_enabled") is False, "swap approval must keep chat false")
    require(latest_swap.get("server_enabled") is False, "swap approval must keep server false")


def check_fixture_run_without_real_model() -> None:
    module = load_module("engel_ai_first_local_response_smoke_exit_fix_fixture", MODULE)
    with tempfile.TemporaryDirectory(prefix="engel_first_smoke_exit_fix_") as temp_text:
        temp = Path(temp_text)
        module.PROJECT_ROOT = temp
        module.REPORT_ROOT = temp / "reports" / "ai_first_local_response_smoke_exit_fix"
        module.DIAGNOSTIC_DIR = module.REPORT_ROOT / "diagnostics"
        module.LOG_DIR = module.REPORT_ROOT / "logs"
        module.RECEIPT_DIR = module.REPORT_ROOT / "receipts"
        module.PLAN_REPORT_DIR = module.REPORT_ROOT / "reports"
        module.EXAMPLE_DIR = module.REPORT_ROOT / "examples"
        module.CODEX_REPORT = temp / "reports" / "codex_bridge" / "ENGEL_AI_FIRST_LOCAL_RESPONSE_SMOKE_EXIT_FIX_V1.md"
        module.V1_SMOKE_RECEIPT_DIR = temp / "reports" / "ai_first_local_response_smoke" / "receipts"
        module.SWAP_APPROVAL_RECEIPT_DIR = temp / "reports" / "ai_llama_cpp_runtime_swap_approval" / "receipts"
        module.RUNTIME_PATH_CONFIG_MANIFEST = temp / "reports" / "ai_runtime_path_config" / "manifests" / "manifest.json"
        module.EXPECTED_RUNTIME_PATH = temp / "candidate" / "llama-cli.exe"
        module.MODEL_FILE = temp / "models" / "tiny_seed.gguf"
        module.EXPECTED_RUNTIME_PATH.parent.mkdir(parents=True)
        module.MODEL_FILE.parent.mkdir(parents=True)
        module.EXPECTED_RUNTIME_PATH.write_text("fixture runtime", encoding="utf-8")
        module.MODEL_FILE.write_text("fixture model", encoding="utf-8")
        module.V1_SMOKE_RECEIPT_DIR.mkdir(parents=True)
        module.SWAP_APPROVAL_RECEIPT_DIR.mkdir(parents=True)
        stdout_path = temp / "reports" / "ai_first_local_response_smoke" / "logs" / "v1_stdout.txt"
        stderr_path = temp / "reports" / "ai_first_local_response_smoke" / "logs" / "v1_stderr.txt"
        stdout_path.parent.mkdir(parents=True)
        stdout_path.write_text("available commands:\n  /exit or Ctrl+C\n> Reply with exactly: Engel\nEngel\n> \n> \n", encoding="utf-8")
        stderr_path.write_text("", encoding="utf-8")
        v1 = {
            "first_local_response_smoke_version": "1",
            "command_executed": True,
            "error": "keyboard_interrupt",
            "exit_code": 130,
            "interrupted": True,
            "expected_token_seen": True,
            "output_marked_untrusted": True,
            "runtime_ready_for_inference": False,
            "chat_enabled": False,
            "server_enabled": False,
            "stdout_log_path": str(stdout_path.relative_to(temp)),
            "stderr_log_path": str(stderr_path.relative_to(temp)),
        }
        (module.V1_SMOKE_RECEIPT_DIR / "FIRST_LOCAL_RESPONSE_SMOKE_20260518T040203Z_tiny_seed.json").write_text(json.dumps(v1), encoding="utf-8")
        swap = {
            "runtime_swap_approval_version": "1",
            "runtime_swap_approval_recorded": True,
            "first_local_response_smoke_allowed_next": True,
            "candidate_runtime_binary_path": str(module.EXPECTED_RUNTIME_PATH),
            "receipt_path": "reports\\ai_llama_cpp_runtime_swap_approval\\receipts\\fixture.json",
            "runtime_ready_for_inference": False,
            "chat_enabled": False,
            "server_enabled": False,
        }
        (module.SWAP_APPROVAL_RECEIPT_DIR / "RUNTIME_SWAP_APPROVAL_20260518T000000Z_fixture.json").write_text(json.dumps(swap), encoding="utf-8")
        module.list_runtime_processes = lambda: []
        module.load_help_payload = lambda runtime_path=None: {
            "help_checked": True,
            "help_supported": True,
            "help_exit_code": 0,
            "supported_flags": ["--simple-io", "--no-display-prompt", "--single-turn", "--no-conversation"],
            "simple_io_supported": True,
            "no_display_prompt_supported": True,
            "no_conversation_supported": True,
            "single_turn_supported": True,
        }

        diagnosis = module.diagnose_latest_payload(write_diagnostic=True)
        require("interactive_wait_after_output" in diagnosis["classifications"], "fixture diagnosis missed interactive wait")

        def fake_run(args, timeout_seconds):
            require(isinstance(args, list) and args, "fixture args must be explicit")
            require("-p" in args and "Reply with exactly: Engel" in args, "fixture prompt mismatch")
            require("--simple-io" in args and "--no-display-prompt" in args and "--single-turn" in args, "fixture missing exit-fix flags")
            require("-n" in args and "8" in args, "fixture n_predict mismatch")
            return module.ExecutionResult(
                True,
                True,
                True,
                timeout_seconds,
                0,
                "Engel\n",
                "",
                False,
                False,
                False,
                False,
                False,
                runtime_process_id=123,
                cleanup_action="none",
            )

        module.run_bounded_process = fake_run
        result = module.run_exit_fix_smoke(module.APPROVAL_TOKEN)
        require(result["first_response_smoke_exit_fix_passed"] is True, "fixture exit fix did not pass")
        require(result["first_response_smoke_passed"] is True, "fixture should mark first smoke passed by exit fix")
        require(result["output_captured"] is True, "fixture output not captured")
        require(result["expected_token_seen"] is True, "fixture expected token not seen")
        require(result["disqualifying_interactive_markers_found"] is False, "fixture should not have interactive markers")
        require(result["output_marked_untrusted"] is True, "fixture output not marked untrusted")
        require(result["model_output_trusted"] is False, "fixture output was trusted")
        for key in [
            "trusted_memory_write_enabled",
            "source_route_queue_mutation",
            "provider_api_enabled",
            "chat_enabled",
            "server_enabled",
            "persistent_chat_loop_enabled",
            "auto_load_enabled",
            "runtime_ready_for_inference",
            "inference_enabled",
        ]:
            require(result[key] is False, "fixture safety field must be false: " + key)


def check_fixture_rejects_interactive_output() -> None:
    module = load_module("engel_ai_first_local_response_smoke_exit_fix_interactive_fixture", MODULE)
    with tempfile.TemporaryDirectory(prefix="engel_first_smoke_exit_fix_bad_") as temp_text:
        temp = Path(temp_text)
        module.PROJECT_ROOT = temp
        module.REPORT_ROOT = temp / "reports" / "ai_first_local_response_smoke_exit_fix"
        module.DIAGNOSTIC_DIR = module.REPORT_ROOT / "diagnostics"
        module.LOG_DIR = module.REPORT_ROOT / "logs"
        module.RECEIPT_DIR = module.REPORT_ROOT / "receipts"
        module.PLAN_REPORT_DIR = module.REPORT_ROOT / "reports"
        module.EXAMPLE_DIR = module.REPORT_ROOT / "examples"
        module.CODEX_REPORT = temp / "reports" / "codex_bridge" / "ENGEL_AI_FIRST_LOCAL_RESPONSE_SMOKE_EXIT_FIX_V1.md"
        module.V1_SMOKE_RECEIPT_DIR = temp / "reports" / "ai_first_local_response_smoke" / "receipts"
        module.SWAP_APPROVAL_RECEIPT_DIR = temp / "reports" / "ai_llama_cpp_runtime_swap_approval" / "receipts"
        module.EXPECTED_RUNTIME_PATH = temp / "candidate" / "llama-cli.exe"
        module.MODEL_FILE = temp / "models" / "tiny_seed.gguf"
        module.EXPECTED_RUNTIME_PATH.parent.mkdir(parents=True)
        module.MODEL_FILE.parent.mkdir(parents=True)
        module.EXPECTED_RUNTIME_PATH.write_text("fixture runtime", encoding="utf-8")
        module.MODEL_FILE.write_text("fixture model", encoding="utf-8")
        module.V1_SMOKE_RECEIPT_DIR.mkdir(parents=True)
        module.SWAP_APPROVAL_RECEIPT_DIR.mkdir(parents=True)
        (module.V1_SMOKE_RECEIPT_DIR / "FIRST_LOCAL_RESPONSE_SMOKE_20260518T040203Z_tiny_seed.json").write_text(
            json.dumps({"first_local_response_smoke_version": "1", "command_executed": True, "output_marked_untrusted": True, "runtime_ready_for_inference": False}),
            encoding="utf-8",
        )
        (module.SWAP_APPROVAL_RECEIPT_DIR / "RUNTIME_SWAP_APPROVAL_20260518T000000Z_fixture.json").write_text(
            json.dumps({"runtime_swap_approval_version": "1", "runtime_swap_approval_recorded": True, "candidate_runtime_binary_path": str(module.EXPECTED_RUNTIME_PATH), "runtime_ready_for_inference": False, "chat_enabled": False, "server_enabled": False}),
            encoding="utf-8",
        )
        module.list_runtime_processes = lambda: []
        module.load_help_payload = lambda runtime_path=None: {"help_checked": True, "help_supported": True, "supported_flags": ["--simple-io", "--no-display-prompt", "--single-turn", "--no-conversation"]}
        module.run_bounded_process = lambda args, timeout_seconds: module.ExecutionResult(True, True, True, timeout_seconds, 0, "available commands:\n/exit or Ctrl+C\nEngel\n> \n", "", False, False, False, False, False, runtime_process_id=321, cleanup_action="none")
        result = module.run_exit_fix_smoke(module.APPROVAL_TOKEN)
        require(result["first_response_smoke_exit_fix_passed"] is False, "interactive fixture should fail")
        require(result["disqualifying_interactive_markers_found"] is True, "interactive fixture marker not detected")


def check_latest_receipt_if_present() -> None:
    receipts = sorted(RECEIPTS.glob("FIRST_LOCAL_RESPONSE_SMOKE_EXIT_FIX_*.json"))
    if not receipts:
        return
    latest = json.loads(read(receipts[-1]))
    require(latest.get("first_local_response_smoke_exit_fix_version") == "1", "latest exit-fix receipt version mismatch")
    require(latest.get("approval_token_name") == "APPROVE_FIRST_LOCAL_RESPONSE_SMOKE_EXIT_FIX", "approval token name mismatch")
    require(latest.get("approval_token_verified") is True, "approval token not verified")
    require(latest.get("prompt") == "Reply with exactly: Engel", "receipt prompt mismatch")
    require(latest.get("prompt_is_fixed_inert") is True, "prompt must be fixed inert")
    require(latest.get("user_content_used_as_prompt") is False, "user content must not be prompt")
    require(latest.get("n_predict") in {4, 8}, "receipt n_predict mismatch")
    require(isinstance(latest.get("command_args"), list) and latest["command_args"], "command args must be explicit list")
    require("llama-server.exe" not in " ".join(latest["command_args"]).lower(), "server executable selected")
    require("rpc-server.exe" not in " ".join(latest["command_args"]).lower(), "rpc server selected")
    require(latest.get("stdin_mode") == "devnull", "stdin mode must be devnull")
    require(latest.get("output_marked_untrusted") is True, "output must be marked untrusted")
    require(latest.get("model_output_trusted") is False, "model output must not be trusted")
    for key in [
        "trusted_memory_write_enabled",
        "source_route_queue_mutation",
        "provider_api_enabled",
        "chat_enabled",
        "server_enabled",
        "persistent_chat_loop_enabled",
        "auto_load_enabled",
        "runtime_ready_for_inference",
        "inference_enabled",
    ]:
        require(latest.get(key) is False, "receipt safety field must be false: " + key)


def run_verifier(path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(path)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=False,
        timeout=180,
    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    require(result.returncode == 0, path.name + " failed: " + (result.stdout + result.stderr)[-1000:])


def check_downstream_verifiers() -> None:
    for path in CHAIN_VERIFIERS:
        run_verifier(path)


def check_docs_registration_and_readiness() -> None:
    commands = read(COMMANDS)
    for command in REQUIRED_COMMANDS:
        require(command in commands, "ENGEL_COMMANDS missing command: " + command)
    codex = read(CODEX_VERIFY)
    require("tools\\verify_engel_ai_first_local_response_smoke_exit_fix.py" in codex, "codex verify missing first smoke exit-fix verifier")
    readiness = read(READINESS)
    for needle in [
        "FIRST_LOCAL_RESPONSE_SMOKE_EXIT_FIX_RECEIPTS",
        "latest_first_local_response_smoke_exit_fix",
        "first_local_response_smoke_exit_fix_passed",
        "ENGEL_AI_FIRST_LOCAL_RESPONSE_SMOKE_EXIT_FIX_V1",
        "ENGEL_AI_BOUNDED_LOCAL_CHAT_SMOKE_V1",
    ]:
        require(needle in readiness, "readiness missing first smoke exit-fix integration: " + needle)
    report = read(REPORT)
    for needle in [
        "ENGEL_AI_FIRST_LOCAL_RESPONSE_SMOKE_EXIT_FIX_V1",
        "V1 Smoke Failure Context",
        "Selected command style",
        "interactive markers found",
        "Output marked untrusted",
        "Packaging skipped",
        "This phase fixes the bounded first local response smoke exit behavior only.",
    ]:
        require(needle in report, "report missing required text: " + needle)


def main() -> int:
    try:
        module = load_module("engel_ai_first_local_response_smoke_exit_fix_bootstrap", MODULE)
        capture_main(module, ["status"])
        check_files()
        check_static_safety()
        check_runtime_commands_and_token_refusals()
        check_source_receipts()
        check_fixture_run_without_real_model()
        check_fixture_rejects_interactive_output()
        check_latest_receipt_if_present()
        check_docs_registration_and_readiness()
        check_downstream_verifiers()
    except CheckFailure as exc:
        print("ENGEL_AI_FIRST_LOCAL_RESPONSE_SMOKE_EXIT_FIX_VERIFY_FAIL")
        print(str(exc))
        return 1
    print("ENGEL_AI_FIRST_LOCAL_RESPONSE_SMOKE_EXIT_FIX_VERIFY_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
