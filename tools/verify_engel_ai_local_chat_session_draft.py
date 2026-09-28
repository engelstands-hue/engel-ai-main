from __future__ import annotations

import ast
import importlib.util
import io
import json
import py_compile
import subprocess
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "engel_ai_local_chat_session_draft.py"
VERIFIER = ROOT / "tools" / "verify_engel_ai_local_chat_session_draft.py"
GUI_HOST = ROOT / "engel_companion.py"
READINESS = ROOT / "engel_ai_runtime_readiness.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_AI_LOCAL_CHAT_PANEL_SESSION_DRAFT_V1.md"
REPORT_ROOT = ROOT / "reports" / "ai_local_chat_session_draft"
LOGS = REPORT_ROOT / "logs"
RECEIPTS = REPORT_ROOT / "receipts"
PLAN_REPORTS = REPORT_ROOT / "reports"
EXAMPLES = REPORT_ROOT / "examples"
COMMANDS = ROOT / "memory" / "ENGEL_COMMANDS.md"
CODEX_VERIFY = ROOT / "scripts" / "codex_verify.ps1"

CHAIN_VERIFIERS = [
    ROOT / "tools" / "verify_engel_ai_local_chat_prompt_draft.py",
    ROOT / "tools" / "verify_engel_ai_bounded_local_chat_smoke.py",
    ROOT / "tools" / "verify_engel_ai_local_chat_panel_enable_bounded_run.py",
    ROOT / "tools" / "verify_engel_ai_read_only_local_chat_panel_integration.py",
    ROOT / "tools" / "verify_engel_ai_first_response_output_filter_tuning.py",
    ROOT / "tools" / "verify_engel_ai_runtime_readiness.py",
    ROOT / "tools" / "verify_engel_memory_roots_storage_layout.py",
]


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def run_command(args: list[str], timeout: int = 120) -> subprocess.CompletedProcess[str]:
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
    require(result.returncode == 0, "command failed: " + " ".join(args) + "\n" + result.stdout + result.stderr)
    return result


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    require(spec is not None and spec.loader is not None, "could not load module spec")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class FakeRun:
    returncode = 0
    stdout = "usage: llama-cli --simple-io --no-display-prompt --single-turn --log-disable --offline"
    stderr = ""


class FakeProcess:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.args = args
        self.kwargs = kwargs
        self.returncode = 0
        self.pid = 1234

    def communicate(self, timeout: int | None = None) -> tuple[str, str]:
        return "Engel session draft fixture output\n", ""

    def poll(self) -> int:
        return self.returncode


def capture_main(module: Any, args: list[str]) -> tuple[int, dict[str, Any]]:
    stream = io.StringIO()
    with patch.object(sys, "argv", ["engel_ai_local_chat_session_draft.py", *args]), redirect_stdout(stream):
        code = module.main()
    text = stream.getvalue()
    payload = json.loads(text) if text.strip().startswith("{") else {}
    return code, payload


def configure_fixture_module(module: Any, temp_root: Path) -> None:
    report_root = temp_root / "reports" / "ai_local_chat_session_draft"
    module.PROJECT_ROOT = temp_root
    module.BOUNDED_SMOKE_RECEIPT_DIR = temp_root / "reports" / "ai_bounded_local_chat_smoke" / "receipts"
    module.PROMPT_DRAFT_RECEIPT_DIR = temp_root / "reports" / "ai_local_chat_prompt_draft" / "receipts"
    module.REPORT_ROOT = report_root
    module.LOG_DIR = report_root / "logs"
    module.RECEIPT_DIR = report_root / "receipts"
    module.PLAN_REPORT_DIR = report_root / "reports"
    module.EXAMPLE_DIR = report_root / "examples"
    module.CODEX_REPORT = temp_root / "reports" / "codex_bridge" / "ENGEL_AI_LOCAL_CHAT_PANEL_SESSION_DRAFT_V1.md"
    module.RUNTIME_PATH = temp_root / "llama-cli.exe"
    module.MODEL_FILE = temp_root / "tiny_seed.gguf"
    module.RUNTIME_PATH.write_text("fixture runtime", encoding="utf-8")
    module.MODEL_FILE.write_text("fixture model", encoding="utf-8")
    module.BOUNDED_SMOKE_RECEIPT_DIR.mkdir(parents=True, exist_ok=True)
    module.PROMPT_DRAFT_RECEIPT_DIR.mkdir(parents=True, exist_ok=True)
    (module.BOUNDED_SMOKE_RECEIPT_DIR / "BOUNDED_LOCAL_CHAT_SMOKE_fixture.json").write_text(
        json.dumps(
            {
                "bounded_local_chat_smoke_version": "1",
                "bounded_local_chat_smoke_passed": True,
                "output_marked_untrusted": True,
                "model_output_trusted": False,
                "runtime_ready_for_inference": False,
                "open_chat_enabled": False,
            }
        ),
        encoding="utf-8",
    )
    (module.PROMPT_DRAFT_RECEIPT_DIR / "LOCAL_CHAT_PROMPT_DRAFT_fixture.json").write_text(
        json.dumps(
            {
                "local_chat_prompt_draft_version": "1",
                "local_chat_prompt_draft_passed": True,
                "output_marked_untrusted": True,
                "model_output_trusted": False,
                "runtime_ready_for_inference": False,
                "open_chat_enabled": False,
            }
        ),
        encoding="utf-8",
    )
    module.list_runtime_processes = lambda: []
    module.subprocess.run = lambda *args, **kwargs: FakeRun()
    module.subprocess.Popen = FakeProcess


def check_files_compile_and_report() -> None:
    for path in [MODULE, VERIFIER, GUI_HOST, READINESS, COMMANDS, CODEX_VERIFY, *CHAIN_VERIFIERS]:
        require(path.exists(), "missing required path: " + str(path.relative_to(ROOT)))
    run_command([sys.executable, "-m", "py_compile", str(MODULE)], timeout=120)
    run_command([sys.executable, "-m", "py_compile", str(VERIFIER)], timeout=120)
    run_command([sys.executable, "-m", "py_compile", str(GUI_HOST)], timeout=120)
    module = load_module("engel_ai_local_chat_session_draft_for_report", MODULE)
    capture_main(module, ["status"])
    for path in [REPORT, REPORT_ROOT, LOGS, RECEIPTS, PLAN_REPORTS, EXAMPLES]:
        require(path.exists(), "missing generated path: " + str(path.relative_to(ROOT)))


def check_module_static_safety() -> None:
    source = read(MODULE)
    tree = ast.parse(source)
    for needle in [
        "APPROVE_LOCAL_CHAT_SESSION_DRAFT_TURN",
        "PROMPT_MAX_LENGTH = 500",
        "TURN_MAX = 3",
        "N_PREDICT = 96",
        "subprocess.DEVNULL",
        "shell=False",
        "timeout=",
        "Popen",
        "human_typed_gui_or_cli_argument",
        "prompt_from_file",
        "prompt_from_memory",
        "prompt_from_model_output",
        "hidden_context_added",
        "prior_turns_included_as_prompt_context",
        "output_marked_untrusted",
        "model_output_trusted",
        "session_transcript_trusted",
        "automatic_next_turn_enabled",
        "trusted_memory_write_enabled",
        "approved_memory_write_enabled",
        "source_route_queue_mutation",
        "provider_api_enabled",
        "runtime_ready_for_inference",
        "open_chat_enabled",
        "persistent_chat_loop_enabled",
        "server_enabled",
        "LOCAL CHAT SESSION DRAFT TURN PASSED",
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
        "session_transcript_trusted\": True",
        "automatic_next_turn_enabled\": True",
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
    module = load_module("engel_ai_local_chat_session_draft_fixture", MODULE)
    with tempfile.TemporaryDirectory() as temp_text:
        temp_root = Path(temp_text)
        configure_fixture_module(module, temp_root)

        for args in [["status"], ["preview", "--prompt", "hello"], ["json"]]:
            code, payload = capture_main(module, args)
            require(code == 0, "command failed: " + " ".join(args))
            require(isinstance(payload, dict), "command did not return object: " + " ".join(args))

        refusal_cases = [
            (["run-turn", "--prompt", "hello", "--turn", "1"], "missing approval"),
            (["run-turn", "--prompt", "hello", "--turn", "1", "--approval", "WRONG"], "wrong approval"),
            (["run-turn", "--prompt", "", "--turn", "1", "--approval", module.APPROVAL_TOKEN], "empty prompt"),
            (["run-turn", "--prompt", "x" * 501, "--turn", "1", "--approval", module.APPROVAL_TOKEN], "over-length prompt"),
            (["run-turn", "--prompt", "file:memory/ENGEL_COMMANDS.md", "--turn", "1", "--approval", module.APPROVAL_TOKEN], "file import prompt"),
            (["run-turn", "--prompt", "hello", "--turn", "0", "--approval", module.APPROVAL_TOKEN], "turn below 1"),
            (["run-turn", "--prompt", "hello", "--turn", "4", "--approval", module.APPROVAL_TOKEN], "turn over 3"),
        ]
        for args, label in refusal_cases:
            code, payload = capture_main(module, args)
            require(code == 2 or payload.get("command_executed") is False, label + " must refuse")
            require(payload.get("command_executed") is False, label + " must not execute command")

        code, receipt = capture_main(module, ["run-turn", "--prompt", "hello from Engel", "--turn", "1", "--approval", module.APPROVAL_TOKEN])
        require(code == 0, "approved fixture run failed")
        for key, expected in {
            "approval_token_verified": True,
            "prior_bounded_local_chat_smoke_passed": True,
            "prior_local_chat_prompt_draft_passed": True,
            "turn_number": 1,
            "turn_max": 3,
            "prompt_length": 16,
            "prompt_max_length": 500,
            "prompt_from_file": False,
            "prompt_from_memory": False,
            "prompt_from_model_output": False,
            "hidden_context_added": False,
            "prior_turns_included_as_prompt_context": False,
            "command_executed": True,
            "runtime_process_started": True,
            "runtime_process_exited": True,
            "timed_out": False,
            "interrupted": False,
            "orphan_process_detected": False,
            "output_captured": True,
            "output_marked_untrusted": True,
            "model_output_trusted": False,
            "session_transcript_trusted": False,
            "persistent_chat_loop_enabled": False,
            "automatic_next_turn_enabled": False,
            "server_enabled": False,
            "trusted_memory_write_enabled": False,
            "approved_memory_write_enabled": False,
            "runtime_ready_for_inference": False,
            "open_chat_enabled": False,
            "local_chat_session_draft_turn_passed": True,
        }.items():
            require(receipt.get(key) == expected, "fixture receipt field mismatch: " + key)
        require(receipt.get("n_predict", 999) <= 96, "n_predict is not bounded")
        require(receipt.get("receipt_path"), "approved fixture did not write receipt")


def check_gui_docs_readiness() -> None:
    gui = read(GUI_HOST)
    for needle in [
        "import engel_ai_local_chat_session_draft as local_ai_session_draft",
        "Engel Local AI — Session Draft",
        "LocalAISessionDraftPromptBox",
        "Draft session turn prompt",
        "0 / 500",
        "Max turns: 3",
        "REVIEW EXACT SESSION DRAFT PROMPT TO SEND",
        "Run Approved Turn",
        "Clear Draft Session View",
        "run_session_turn(prompt, turn_number, approval)",
        "local_ai_session_draft_approval_input.clear()",
        "UNTRUSTED LOCAL MODEL OUTPUT / UNTRUSTED LOCAL SESSION DRAFT",
        "Prior turns are not included as prompt context",
    ]:
        require(needle in gui, "GUI missing session draft text: " + needle)
    helper_start = gui.index("# ENGEL_AI_READ_ONLY_LOCAL_CHAT_PANEL_INTEGRATION_V1_START")
    helper_end = gui.index("# ENGEL_AI_READ_ONLY_LOCAL_CHAT_PANEL_INTEGRATION_V1_END")
    panel_start = gui.index("# ENGEL_AI_READ_ONLY_LOCAL_CHAT_PANEL_INTEGRATION_V1_PANEL_START")
    panel_end = gui.index("# ENGEL_AI_READ_ONLY_LOCAL_CHAT_PANEL_INTEGRATION_V1_PANEL_END")
    supervised_start = gui.find("Engel Local AI — Supervised Open Chat", panel_start, panel_end)
    panel_slice_end = supervised_start if supervised_start != -1 else panel_end
    combined = gui[helper_start:helper_end] + gui[panel_start:panel_slice_end]
    require("APPROVE_LOCAL_CHAT_SESSION_DRAFT_TURN" not in combined, "GUI must not store raw session draft approval token")
    for forbidden in ["shell=True", "llama-server.exe", "rpc-server.exe", "trusted_memory_write_enabled\": True", "runtime_ready_for_inference\": True", "open_chat_enabled\": True", "automatic_next_turn_enabled\": True"]:
        require(forbidden.lower() not in combined.lower(), "GUI session draft section contains forbidden text: " + forbidden)

    commands = read(COMMANDS)
    for needle in [
        "ai local chat session draft status",
        "ai local chat session draft preview",
        "ai local chat session draft run-turn",
        "companion local ai session draft panel",
    ]:
        require(needle in commands, "command docs missing: " + needle)

    readiness = read(READINESS)
    for needle in [
        "LOCAL_CHAT_SESSION_DRAFT_RECEIPTS",
        "local_chat_session_draft_entries",
        "latest_local_chat_session_draft",
        "local_chat_session_draft_passed",
        "bounded_session_draft_enabled",
        "ENGEL_AI_LOCAL_CHAT_PANEL_SESSION_REVIEW_V1",
    ]:
        require(needle in readiness, "readiness missing: " + needle)

    codex = read(CODEX_VERIFY)
    require("tools\\verify_engel_ai_local_chat_session_draft.py" in codex, "codex verify missing session draft verifier")

    report = read(REPORT)
    for needle in [
        "ENGEL_AI_LOCAL_CHAT_PANEL_SESSION_DRAFT_V1",
        "Engel Local AI — Session Draft",
        "Approval token stored: `False`",
        "Token clears after use: `True`",
        "runtime_ready_for_inference: `False`",
        "automatic_next_turn_enabled: `False`",
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
        print("ENGEL_AI_LOCAL_CHAT_SESSION_DRAFT_VERIFY_FAIL")
        print(str(exc))
        return 1
    print("ENGEL_AI_LOCAL_CHAT_SESSION_DRAFT_VERIFY_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
