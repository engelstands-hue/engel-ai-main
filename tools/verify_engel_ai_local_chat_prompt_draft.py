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
MODULE = ROOT / "engel_ai_local_chat_prompt_draft.py"
VERIFIER = ROOT / "tools" / "verify_engel_ai_local_chat_prompt_draft.py"
GUI_HOST = ROOT / "engel_companion.py"
READINESS = ROOT / "engel_ai_runtime_readiness.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_AI_LOCAL_CHAT_PANEL_HUMAN_PROMPT_DRAFT_V1.md"
REPORT_ROOT = ROOT / "reports" / "ai_local_chat_prompt_draft"
LOGS = REPORT_ROOT / "logs"
RECEIPTS = REPORT_ROOT / "receipts"
PLAN_REPORTS = REPORT_ROOT / "reports"
EXAMPLES = REPORT_ROOT / "examples"
COMMANDS = ROOT / "memory" / "ENGEL_COMMANDS.md"
CODEX_VERIFY = ROOT / "scripts" / "codex_verify.ps1"

BOUNDED_SMOKE_VERIFIER = ROOT / "tools" / "verify_engel_ai_bounded_local_chat_smoke.py"
PANEL_RUN_VERIFIER = ROOT / "tools" / "verify_engel_ai_local_chat_panel_enable_bounded_run.py"
READ_ONLY_PANEL_VERIFIER = ROOT / "tools" / "verify_engel_ai_read_only_local_chat_panel_integration.py"
FILTER_TUNING_VERIFIER = ROOT / "tools" / "verify_engel_ai_first_response_output_filter_tuning.py"
READINESS_VERIFIER = ROOT / "tools" / "verify_engel_ai_runtime_readiness.py"
MEMORY_ROOTS_VERIFIER = ROOT / "tools" / "verify_engel_memory_roots_storage_layout.py"

CHAIN_VERIFIERS = [
    BOUNDED_SMOKE_VERIFIER,
    PANEL_RUN_VERIFIER,
    READ_ONLY_PANEL_VERIFIER,
    FILTER_TUNING_VERIFIER,
    READINESS_VERIFIER,
    MEMORY_ROOTS_VERIFIER,
]


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff")


def run_command(args: list[str], timeout: int = 420) -> str:
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


def fixture_bounded_smoke_receipt(folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "BOUNDED_LOCAL_CHAT_SMOKE_20260518T050000Z_tiny_seed.json").write_text(
        json.dumps(
            {
                "bounded_local_chat_smoke_version": "1",
                "bounded_local_chat_smoke_passed": True,
                "output_marked_untrusted": True,
                "model_output_trusted": False,
                "runtime_ready_for_inference": False,
                "open_chat_enabled": False,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


def configure_fixture_module(module, temp_root: Path) -> None:
    report_root = temp_root / "reports" / "ai_local_chat_prompt_draft"
    module.PROJECT_ROOT = temp_root
    module.BOUNDED_SMOKE_RECEIPT_DIR = temp_root / "reports" / "ai_bounded_local_chat_smoke" / "receipts"
    module.REPORT_ROOT = report_root
    module.LOG_DIR = report_root / "logs"
    module.RECEIPT_DIR = report_root / "receipts"
    module.PLAN_REPORT_DIR = report_root / "reports"
    module.EXAMPLE_DIR = report_root / "examples"
    module.CODEX_REPORT = temp_root / "reports" / "codex_bridge" / "ENGEL_AI_LOCAL_CHAT_PANEL_HUMAN_PROMPT_DRAFT_V1.md"
    module.RUNTIME_PATH = temp_root / "llama-cli.exe"
    module.MODEL_FILE = temp_root / "tiny_seed.gguf"
    module.RUNTIME_PATH.write_text("fixture runtime\n", encoding="utf-8")
    module.MODEL_FILE.write_text("fixture model\n", encoding="utf-8")
    fixture_bounded_smoke_receipt(module.BOUNDED_SMOKE_RECEIPT_DIR)
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
        stdout_text="Hello from fixture.\n",
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
    for path in [MODULE, VERIFIER, GUI_HOST, READINESS, COMMANDS, CODEX_VERIFY, *CHAIN_VERIFIERS]:
        require(path.exists(), "missing required path: " + str(path.relative_to(ROOT)))
    run_command([sys.executable, "-m", "py_compile", str(MODULE)], timeout=120)
    run_command([sys.executable, "-m", "py_compile", str(VERIFIER)], timeout=120)
    run_command([sys.executable, "-m", "py_compile", str(GUI_HOST)], timeout=120)
    module = load_module("engel_ai_local_chat_prompt_draft_for_report", MODULE)
    capture_main(module, ["status"])
    for path in [REPORT, REPORT_ROOT, LOGS, RECEIPTS, PLAN_REPORTS, EXAMPLES]:
        require(path.exists(), "missing generated path: " + str(path.relative_to(ROOT)))


def check_module_static_safety() -> None:
    source = read(MODULE)
    tree = ast.parse(source)
    for needle in [
        "APPROVE_LOCAL_CHAT_PROMPT_DRAFT",
        "PROMPT_MAX_LENGTH = 500",
        "N_PREDICT = 64",
        "subprocess.DEVNULL",
        "shell=False",
        "timeout=",
        "Popen",
        "human_typed_gui_or_cli_argument",
        "prompt_from_file",
        "prompt_from_memory",
        "prompt_from_model_output",
        "hidden_context_added",
        "output_marked_untrusted",
        "model_output_trusted",
        "trusted_memory_write_enabled",
        "approved_memory_write_enabled",
        "source_route_queue_mutation",
        "provider_api_enabled",
        "runtime_ready_for_inference",
        "open_chat_enabled",
        "persistent_chat_loop_enabled",
        "server_enabled",
        "LOCAL CHAT PROMPT DRAFT PASSED",
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
        "approved_memory_write_enabled\": True",
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
    module = load_module("engel_ai_local_chat_prompt_draft_fixture", MODULE)
    with tempfile.TemporaryDirectory() as temp_text:
        temp_root = Path(temp_text)
        configure_fixture_module(module, temp_root)

        for args in [["status"], ["preview", "--prompt", "hello"], ["json"]]:
            code, payload = capture_main(module, args)
            require(code == 0, "command failed: " + " ".join(args))
            require(isinstance(payload, dict), "command did not return object: " + " ".join(args))

        refusal_cases = [
            (["run", "--prompt", "hello"], "missing approval"),
            (["run", "--prompt", "hello", "--approval", "WRONG"], "wrong approval"),
            (["run", "--prompt", "", "--approval", module.APPROVAL_TOKEN], "empty prompt"),
            (["run", "--prompt", "x" * 501, "--approval", module.APPROVAL_TOKEN], "over-length prompt"),
            (["run", "--prompt", "file:memory/ENGEL_COMMANDS.md", "--approval", module.APPROVAL_TOKEN], "file import prompt"),
        ]
        for args, label in refusal_cases:
            code, payload = capture_main(module, args)
            require(code == 2 or payload.get("command_executed") is False, label + " must refuse")
            require(payload.get("command_executed") is False, label + " must not execute command")

        code, receipt = capture_main(module, ["run", "--prompt", "hello from Engel", "--approval", module.APPROVAL_TOKEN])
        require(code == 0, "approved fixture run failed")
        for key, expected in {
            "approval_token_verified": True,
            "prior_bounded_local_chat_smoke_passed": True,
            "prompt_length": 16,
            "prompt_max_length": 500,
            "prompt_from_file": False,
            "prompt_from_memory": False,
            "prompt_from_model_output": False,
            "hidden_context_added": False,
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
            "approved_memory_write_enabled": False,
            "runtime_ready_for_inference": False,
            "open_chat_enabled": False,
            "local_chat_prompt_draft_passed": True,
        }.items():
            require(receipt.get(key) == expected, "fixture receipt field mismatch: " + key)
        require(receipt.get("n_predict", 999) <= 64, "n_predict is not bounded")
        require(receipt.get("receipt_path"), "approved fixture did not write receipt")


def check_gui_docs_readiness() -> None:
    gui = read(GUI_HOST)
    for needle in [
        "import engel_ai_local_chat_prompt_draft as local_ai_prompt_draft",
        "Engel Local AI — Human Prompt Draft",
        "LocalAIHumanPromptDraftBox",
        "Draft prompt",
        "0 / 500",
        "REVIEW EXACT PROMPT TO SEND",
        "Run One Bounded Draft Prompt",
        "run_prompt_draft(prompt, approval)",
        "local_ai_prompt_draft_approval_input.clear()",
        "UNTRUSTED LOCAL MODEL OUTPUT",
        "No hidden context, files, memory, reports, logs, chat exports, or model output are appended.",
    ]:
        require(needle in gui, "GUI missing prompt draft text: " + needle)
    helper_start = gui.index("# ENGEL_AI_READ_ONLY_LOCAL_CHAT_PANEL_INTEGRATION_V1_START")
    helper_end = gui.index("# ENGEL_AI_READ_ONLY_LOCAL_CHAT_PANEL_INTEGRATION_V1_END")
    panel_start = gui.index("# ENGEL_AI_READ_ONLY_LOCAL_CHAT_PANEL_INTEGRATION_V1_PANEL_START")
    panel_end = gui.index("# ENGEL_AI_READ_ONLY_LOCAL_CHAT_PANEL_INTEGRATION_V1_PANEL_END")
    supervised_start = gui.find("Engel Local AI — Supervised Open Chat", panel_start, panel_end)
    panel_slice_end = supervised_start if supervised_start != -1 else panel_end
    combined = gui[helper_start:helper_end] + gui[panel_start:panel_slice_end]
    require("APPROVE_LOCAL_CHAT_PROMPT_DRAFT" not in combined, "GUI must not store raw prompt draft approval token")
    for forbidden in ["shell=True", "llama-server.exe", "rpc-server.exe", "trusted_memory_write_enabled\": True", "runtime_ready_for_inference\": True", "open_chat_enabled\": True"]:
        require(forbidden.lower() not in combined.lower(), "GUI prompt draft section contains forbidden text: " + forbidden)

    commands = read(COMMANDS)
    for needle in [
        "ai local chat prompt draft status",
        "ai local chat prompt draft preview",
        "ai local chat prompt draft run",
        "companion local ai human prompt draft panel",
    ]:
        require(needle in commands, "command docs missing: " + needle)

    readiness = read(READINESS)
    for needle in [
        "LOCAL_CHAT_PROMPT_DRAFT_RECEIPTS",
        "local_chat_prompt_draft_entries",
        "latest_local_chat_prompt_draft",
        "local_chat_prompt_draft_passed",
        "bounded_human_prompt_enabled",
        "ENGEL_AI_LOCAL_CHAT_PANEL_SESSION_DRAFT_V1",
    ]:
        require(needle in readiness, "readiness missing: " + needle)

    codex = read(CODEX_VERIFY)
    require("tools\\verify_engel_ai_local_chat_prompt_draft.py" in codex, "codex verify missing prompt draft verifier")

    report = read(REPORT)
    for needle in [
        "ENGEL_AI_LOCAL_CHAT_PANEL_HUMAN_PROMPT_DRAFT_V1",
        "Engel Local AI — Human Prompt Draft",
        "Approval token stored: `False`",
        "Token clears after use: `True`",
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
        check_module_static_safety()
        check_cli_and_fixture_run()
        check_gui_docs_readiness()
        check_chain_verifiers()
    except CheckFailure as exc:
        print("ENGEL_AI_LOCAL_CHAT_PROMPT_DRAFT_VERIFY_FAIL")
        print(str(exc))
        return 1
    print("ENGEL_AI_LOCAL_CHAT_PROMPT_DRAFT_VERIFY_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
