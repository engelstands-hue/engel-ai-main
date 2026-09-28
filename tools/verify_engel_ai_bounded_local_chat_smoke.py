from __future__ import annotations

import ast
from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import py_compile
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "engel_ai_bounded_local_chat_smoke.py"
VERIFIER = ROOT / "tools" / "verify_engel_ai_bounded_local_chat_smoke.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_AI_BOUNDED_LOCAL_CHAT_ENABLE_V1.md"
REPORT_ROOT = ROOT / "reports" / "ai_bounded_local_chat_smoke"
LOGS = REPORT_ROOT / "logs"
RECEIPTS = REPORT_ROOT / "receipts"
PLAN_REPORTS = REPORT_ROOT / "reports"
EXAMPLES = REPORT_ROOT / "examples"
COMMANDS = ROOT / "memory" / "ENGEL_COMMANDS.md"
CODEX_VERIFY = ROOT / "scripts" / "codex_verify.ps1"
READINESS = ROOT / "engel_ai_runtime_readiness.py"
COMPANION = ROOT / "engel_companion.py"

PANEL_VERIFIER = ROOT / "tools" / "verify_engel_ai_read_only_local_chat_panel_integration.py"
FILTER_TUNING_VERIFIER = ROOT / "tools" / "verify_engel_ai_first_response_output_filter_tuning.py"
EXIT_FIX_VERIFIER = ROOT / "tools" / "verify_engel_ai_first_local_response_smoke_exit_fix.py"
FIRST_SMOKE_VERIFIER = ROOT / "tools" / "verify_engel_ai_first_local_response_smoke.py"
SWAP_APPROVAL_VERIFIER = ROOT / "tools" / "verify_engel_ai_llama_cpp_runtime_swap_approval.py"
MEMORY_ROOTS_VERIFIER = ROOT / "tools" / "verify_engel_memory_roots_storage_layout.py"
READINESS_VERIFIER = ROOT / "tools" / "verify_engel_ai_runtime_readiness.py"

CHAIN_VERIFIERS = [
    PANEL_VERIFIER,
    FILTER_TUNING_VERIFIER,
    EXIT_FIX_VERIFIER,
    FIRST_SMOKE_VERIFIER,
    SWAP_APPROVAL_VERIFIER,
    MEMORY_ROOTS_VERIFIER,
    READINESS_VERIFIER,
]


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff")


def run_command(args: list[str], timeout: int = 360) -> str:
    result = subprocess.run(
        args,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=False,
        timeout=timeout,
    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    require(result.returncode == 0, "command failed: " + " ".join(args) + "\n" + (result.stdout + result.stderr)[-1600:])
    return result.stdout + result.stderr


def load_module(name: str, path: Path):
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location(name, path)
    require(spec is not None and spec.loader is not None, "could not load module: " + path.name)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def capture_main(module, args: list[str]) -> tuple[int, dict[str, object]]:
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        code = int(module.main(args))
    text = buffer.getvalue()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise CheckFailure("command did not print JSON: " + str(exc) + "\n" + text[-800:])
    return code, payload


def fixture_filter_receipt(folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "FIRST_RESPONSE_OUTPUT_FILTER_TUNING_20260518T045406Z_tiny_seed.json").write_text(
        json.dumps(
            {
                "first_response_output_filter_tuning_version": "1",
                "diagnosis_classification": "clean_single_turn_exit_but_filter_too_strict",
                "first_response_smoke_passed_after_tuning_preview": True,
                "output_marked_untrusted": True,
                "runtime_ready_for_inference": False,
                "chat_enabled": False,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


def configure_fixture_module(module, temp_root: Path) -> None:
    report_root = temp_root / "reports" / "ai_bounded_local_chat_smoke"
    module.PROJECT_ROOT = temp_root
    module.FILTER_TUNING_RECEIPT_DIR = temp_root / "reports" / "ai_first_response_output_filter_tuning" / "receipts"
    module.REPORT_ROOT = report_root
    module.LOG_DIR = report_root / "logs"
    module.RECEIPT_DIR = report_root / "receipts"
    module.PLAN_REPORT_DIR = report_root / "reports"
    module.EXAMPLE_DIR = report_root / "examples"
    module.CODEX_REPORT = temp_root / "reports" / "codex_bridge" / "ENGEL_AI_BOUNDED_LOCAL_CHAT_ENABLE_V1.md"
    module.RUNTIME_PATH = temp_root / "llama-cli.exe"
    module.MODEL_FILE = temp_root / "tiny_seed.gguf"
    module.RUNTIME_PATH.write_text("fixture runtime\n", encoding="utf-8")
    module.MODEL_FILE.write_text("fixture model\n", encoding="utf-8")
    fixture_filter_receipt(module.FILTER_TUNING_RECEIPT_DIR)
    module.list_runtime_processes = lambda: []
    module.load_help_payload = lambda runtime_path=module.RUNTIME_PATH: {
        "help_checked": True,
        "help_supported": True,
        "help_exit_code": 0,
        "supported_flags": list(module.SUGGESTED_FLAGS),
        "unsupported_suggested_flags": [],
        "help_error": None,
    }
    module.run_bounded_process = lambda args, timeout=module.TIMEOUT_SECONDS: module.ExecutionResult(
        command_executed=True,
        runtime_process_started=True,
        runtime_process_exited=True,
        timeout_seconds=timeout,
        exit_code=0,
        stdout_text="I am local.\n",
        stderr_text="",
        stdout_truncated=False,
        stderr_truncated=False,
        timed_out=False,
        interrupted=False,
        orphan_process_detected=False,
        runtime_process_id=1234,
        cleanup_action="none",
    )


def check_files_compile_and_report() -> None:
    for path in [MODULE, VERIFIER, COMMANDS, CODEX_VERIFY, READINESS, COMPANION, *CHAIN_VERIFIERS]:
        require(path.exists(), "missing required path: " + str(path.relative_to(ROOT)))
    run_command([sys.executable, "-m", "py_compile", str(MODULE)], timeout=120)
    run_command([sys.executable, "-m", "py_compile", str(VERIFIER)], timeout=120)
    module = load_module("engel_ai_bounded_local_chat_smoke_for_report", MODULE)
    capture_main(module, ["status"])
    for path in [REPORT, REPORT_ROOT, LOGS, RECEIPTS, PLAN_REPORTS, EXAMPLES]:
        require(path.exists(), "missing required generated path: " + str(path.relative_to(ROOT)))


def check_static_safety() -> None:
    source = read(MODULE)
    tree = ast.parse(source)
    for needle in [
        "APPROVE_BOUNDED_LOCAL_CHAT_SMOKE",
        "You are Engel local smoke test. Answer in one short sentence: I am local.",
        "N_PREDICT = 24",
        "subprocess.DEVNULL",
        "shell=False",
        "timeout=",
        "Popen",
        "command_args",
        "output_marked_untrusted",
        "model_output_trusted",
        "trusted_memory_write_enabled",
        "source_route_queue_mutation",
        "provider_api_enabled",
        "runtime_ready_for_inference",
        "open_chat_enabled",
        "persistent_chat_loop_enabled",
        "server_enabled",
        "BOUNDED LOCAL CHAT SMOKE PASSED",
        "ENGEL_AI_LOCAL_CHAT_PANEL_ENABLE_BOUNDED_RUN_V1",
        "FORBIDDEN_EXECUTABLE_NAMES",
        "llama-cli.exe",
    ]:
        require(needle in source, "module missing required text: " + needle)
    for forbidden in [
        "shell=True",
        "requests.",
        "urllib.",
        "socket.",
        "webbrowser.",
        "openai.",
        "anthropic.",
        "pip install",
        "invoke-webrequest",
        "curl ",
        "wsl.exe",
        "docker.",
        "hermes",
        "write_trusted_memory",
        "trusted_memory_write_enabled\": True",
        "model_output_trusted\": True",
        "runtime_ready_for_inference\": True",
        "open_chat_enabled\": True",
        "chat_enabled\": True",
        "server_enabled\": True",
        "persistent_chat_loop_enabled\": True",
    ]:
        require(forbidden.lower() not in source.lower(), "module contains forbidden behavior text: " + forbidden)
    for node in ast.walk(tree):
        if isinstance(node, ast.While):
            raise CheckFailure("module contains forbidden persistent loop")


def check_cli_and_fixture_run() -> None:
    module = load_module("engel_ai_bounded_local_chat_smoke_fixture", MODULE)
    with tempfile.TemporaryDirectory() as temp_text:
        temp_root = Path(temp_text)
        configure_fixture_module(module, temp_root)

        for args in [["status"], ["preview"], ["json"]]:
            code, payload = capture_main(module, args)
            require(code == 0, "command failed: " + " ".join(args))
            require(isinstance(payload, dict), "command did not return an object: " + " ".join(args))

        code, missing = capture_main(module, ["run"])
        require(code == 2, "missing approval token must refuse")
        require(missing.get("approval_token_verified") is False, "missing token must not verify")
        require(missing.get("command_executed") is False, "missing token must not execute command")
        require(not list(module.RECEIPT_DIR.glob("BOUNDED_LOCAL_CHAT_SMOKE_*.json")), "missing token wrote a receipt")

        code, wrong = capture_main(module, ["run", "--approval", "WRONG"])
        require(code == 2, "wrong approval token must refuse")
        require(wrong.get("approval_token_verified") is False, "wrong token must not verify")
        require(wrong.get("command_executed") is False, "wrong token must not execute command")

        code, receipt = capture_main(module, ["run", "--approval", module.APPROVAL_TOKEN])
        require(code == 0, "approved fixture run failed")
        for key, expected in {
            "approval_token_verified": True,
            "prior_first_response_smoke_passed": True,
            "prompt_is_fixed_test_prompt": True,
            "user_content_used_as_prompt": False,
            "command_executed": True,
            "runtime_process_started": True,
            "runtime_process_exited": True,
            "timed_out": False,
            "interrupted": False,
            "orphan_process_detected": False,
            "output_captured": True,
            "output_marked_untrusted": True,
            "model_output_trusted": False,
            "persistent_chat_loop_enabled": False,
            "server_enabled": False,
            "trusted_memory_write_enabled": False,
            "provider_api_enabled": False,
            "runtime_ready_for_inference": False,
            "open_chat_enabled": False,
            "bounded_local_chat_smoke_passed": True,
        }.items():
            require(receipt.get(key) is expected, f"fixture receipt expected {key}={expected!r}")
        require(receipt.get("exit_code") == 0, "fixture receipt must exit cleanly")
        require(receipt.get("n_predict") == 24, "n_predict must be bounded at 24")
        require(receipt.get("prompt") == module.FIXED_PROMPT, "prompt must be fixed")
        require(receipt.get("next_safe_action") == module.NEXT_SUCCESS_ACTION, "success next action mismatch")
        require(Path(temp_root / str(receipt.get("receipt_path"))).exists(), "fixture receipt file missing")
        require(Path(temp_root / str(receipt.get("stdout_log_path"))).exists(), "fixture stdout log missing")
        saved = json.loads(Path(temp_root / str(receipt.get("receipt_path"))).read_text(encoding="utf-8"))
        require("approval" not in saved, "receipt must not store an approval field")
        require(saved.get("approval_token_name") == module.APPROVAL_TOKEN, "receipt may record token name only")

        module.run_bounded_process = lambda args, timeout=module.TIMEOUT_SECONDS: module.ExecutionResult(
            command_executed=True,
            runtime_process_started=True,
            runtime_process_exited=True,
            timeout_seconds=timeout,
            exit_code=0,
            stdout_text="I am local.\nserver listening on 127.0.0.1\n",
            stderr_text="",
            stdout_truncated=False,
            stderr_truncated=False,
            timed_out=False,
            interrupted=False,
            orphan_process_detected=False,
        )
        code, failed = capture_main(module, ["run", "--approval", module.APPROVAL_TOKEN])
        require(code == 0, "approved unsafe fixture should still write evidence")
        require(failed.get("bounded_local_chat_smoke_passed") is False, "server marker must fail")


def check_docs_readiness_and_panel() -> None:
    commands = read(COMMANDS)
    for needle in [
        "ai bounded local chat smoke status",
        "ai bounded local chat smoke preview",
        "ai bounded local chat smoke run",
        "ai bounded local chat smoke json",
        "APPROVE_BOUNDED_LOCAL_CHAT_SMOKE",
        "open_chat_enabled remain false",
    ]:
        require(needle in commands, "command docs missing: " + needle)

    codex = read(CODEX_VERIFY)
    require("tools\\verify_engel_ai_bounded_local_chat_smoke.py" in codex, "codex verify missing bounded smoke verifier")

    readiness = read(READINESS)
    for needle in [
        "BOUNDED_LOCAL_CHAT_SMOKE_RECEIPTS",
        "bounded_local_chat_smoke_entries",
        "latest_bounded_local_chat_smoke",
        "bounded_local_chat_smoke_passed",
        "ENGEL_AI_LOCAL_CHAT_PANEL_ENABLE_BOUNDED_RUN_V1",
        "open_chat_enabled",
    ]:
        require(needle in readiness, "readiness missing: " + needle)

    companion = read(COMPANION)
    for needle in [
        "bounded_local_chat_smoke_status_label",
        "BOUNDED LOCAL CHAT SMOKE PASSED",
        "OUTPUT UNTRUSTED",
        "UNTRUSTED LOCAL MODEL OUTPUT",
        "local_ai_approval_input",
        "run_local_ai_bounded_smoke_from_panel",
        "run_chat_smoke(approval)",
        "local_ai_approval_input.clear()",
    ]:
        require(needle in companion, "Companion Local AI panel missing: " + needle)
    helper_section = companion.split("# ENGEL_AI_READ_ONLY_LOCAL_CHAT_PANEL_INTEGRATION_V1_START", 1)[1].split(
        "# ENGEL_AI_READ_ONLY_LOCAL_CHAT_PANEL_INTEGRATION_V1_END", 1
    )[0]
    panel_section = companion.split("# ENGEL_AI_READ_ONLY_LOCAL_CHAT_PANEL_INTEGRATION_V1_PANEL_START", 1)[1].split(
        "# ENGEL_AI_READ_ONLY_LOCAL_CHAT_PANEL_INTEGRATION_V1_PANEL_END", 1
    )[0]
    combined = helper_section + "\n" + panel_section
    require("APPROVE_BOUNDED_LOCAL_CHAT_SMOKE" not in combined, "GUI must not store raw approval token")
    require("local_ai_run_button.clicked.connect(self.run_local_ai_bounded_smoke_from_panel)" in panel_section, "Companion run button must be wired to bounded handler")
    for forbidden in ["subprocess", "Popen", "llama-server.exe", "rpc-server.exe", "openai", "anthropic", "webbrowser"]:
        require(forbidden.lower() not in combined.lower(), "GUI panel contains forbidden behavior/text: " + forbidden)

    report = read(REPORT)
    for needle in [
        "ENGEL_AI_BOUNDED_LOCAL_CHAT_ENABLE_V1",
        "Run button: `disabled / fail-closed`",
        "GUI model run on open/refresh: `False`",
        "Output marked untrusted",
        "runtime_ready_for_inference: `False`",
        "open_chat_enabled: `False`",
        "Packaging skipped",
    ]:
        require(needle in report, "report missing: " + needle)


def check_chain_verifiers() -> None:
    for verifier in CHAIN_VERIFIERS:
        py_compile.compile(str(verifier), doraise=True)


def main() -> int:
    try:
        check_files_compile_and_report()
        check_static_safety()
        check_cli_and_fixture_run()
        check_docs_readiness_and_panel()
        check_chain_verifiers()
    except CheckFailure as exc:
        print("ENGEL_AI_BOUNDED_LOCAL_CHAT_SMOKE_VERIFY_FAIL")
        print(str(exc))
        return 1
    print("ENGEL_AI_BOUNDED_LOCAL_CHAT_SMOKE_VERIFY_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
