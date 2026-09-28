from __future__ import annotations

import contextlib
import importlib
import io
import json
import py_compile
import sys
import tempfile
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = PROJECT_ROOT / "engel_ai_local_approved_memory_context_preview.py"
GUI_PATH = PROJECT_ROOT / "engel_companion.py"
READINESS_PATH = PROJECT_ROOT / "engel_ai_runtime_readiness.py"
REPORT_PATH = PROJECT_ROOT / "reports" / "codex_bridge" / "ENGEL_AI_LOCAL_APPROVED_MEMORY_CONTEXT_PREVIEW_V1.md"
COMMANDS_PATH = PROJECT_ROOT / "memory" / "ENGEL_COMMANDS.md"
CODEX_VERIFY = PROJECT_ROOT / "scripts" / "codex_verify.ps1"
REPORT_ROOT = PROJECT_ROOT / "reports" / "ai_local_approved_memory_context_preview"

REQUIRED_DIRS = [
    REPORT_ROOT / "contexts",
    REPORT_ROOT / "logs",
    REPORT_ROOT / "receipts",
    REPORT_ROOT / "reports",
    REPORT_ROOT / "examples",
]


def fail(message: str) -> None:
    raise AssertionError(message)


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def load_module():
    sys.path.insert(0, str(PROJECT_ROOT))
    return importlib.import_module("engel_ai_local_approved_memory_context_preview")


def capture_main(module: Any, args: list[str]) -> tuple[int, str]:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = module.main(args)
    return int(code), buf.getvalue()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def configure_temp_paths(module: Any, temp_root: Path) -> Path:
    source_root = temp_root / "reports" / "ai_local_chat_session_memory_candidate_review_and_approved_write"
    readback_root = temp_root / "reports" / "ai_local_approved_memory_readback"
    phase_root = temp_root / "reports" / "ai_local_approved_memory_context_preview"
    module.PROJECT_ROOT = temp_root
    module.APPROVED_RECORD_DIR = source_root / "approved_memory_records"
    module.ROLLBACK_DIR = source_root / "rollback"
    module.READBACK_RECEIPT_DIR = readback_root / "receipts"
    module.REPORT_ROOT = phase_root
    module.CONTEXT_DIR = phase_root / "contexts"
    module.LOG_DIR = phase_root / "logs"
    module.RECEIPT_DIR = phase_root / "receipts"
    module.PLAN_REPORT_DIR = phase_root / "reports"
    module.EXAMPLE_DIR = phase_root / "examples"
    module.CODEX_REPORT = temp_root / "reports" / "codex_bridge" / "ENGEL_AI_LOCAL_APPROVED_MEMORY_CONTEXT_PREVIEW_V1.md"
    module.RUNTIME_PATH = temp_root / "missing-runtime.exe"
    module.MODEL_FILE = temp_root / "missing-model.gguf"
    for folder in [
        module.APPROVED_RECORD_DIR,
        module.ROLLBACK_DIR,
        module.READBACK_RECEIPT_DIR,
        module.CONTEXT_DIR,
        module.LOG_DIR,
        module.RECEIPT_DIR,
        module.PLAN_REPORT_DIR,
        module.EXAMPLE_DIR,
        module.CODEX_REPORT.parent,
    ]:
        folder.mkdir(parents=True, exist_ok=True)
    record = module.APPROVED_RECORD_DIR / "APPROVED_LOCAL_CHAT_MEMORY_RECORD_safeid.json"
    rollback = module.ROLLBACK_DIR / "ROLLBACK_APPROVED_LOCAL_CHAT_MEMORY_RECORD_safeid.json"
    readback = module.READBACK_RECEIPT_DIR / "LOCAL_APPROVED_MEMORY_READBACK_safeid.json"
    write_json(
        record,
        {
            "approved_local_chat_memory_record_version": "1",
            "approval_basis": "deterministic_guardian_gates_passed",
            "human_approval_required": False,
            "approval_token_required": False,
            "approved_memory_scope": "approved_local_chat_memory_record_only",
            "source_model_output_trusted": False,
            "candidate_content_obeyed": False,
            "deterministic_guardian_gates_passed": True,
            "trusted_memory_write_enabled_global": False,
            "runtime_ready_for_inference": False,
            "open_chat_enabled": False,
            "prompt_summary": "Remember that Engel completed bounded local memory readback.",
            "bounded_summary": "Approved local chat memory readback exists as visible evidence only, not hidden context.",
        },
    )
    write_json(rollback, {"rollback_metadata_version": "1", "trusted_memory_target_touched": False})
    write_json(
        readback,
        {
            "local_approved_memory_readback_version": "1",
            "approved_record_path": "reports\\ai_local_chat_session_memory_candidate_review_and_approved_write\\approved_memory_records\\APPROVED_LOCAL_CHAT_MEMORY_RECORD_safeid.json",
            "memory_write_performed": False,
            "global_trusted_memory": False,
            "used_as_hidden_prompt_context": False,
            "automatic_context_injection_enabled": False,
            "runtime_process_started": False,
            "model_process_started": False,
            "runtime_ready_for_inference": False,
            "open_chat_enabled": False,
        },
    )
    return record


def fixture_tests(module: Any) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        temp_root = Path(tmp)
        configure_temp_paths(module, temp_root)
        for command in ["status", "list", "json", "preview-context"]:
            code, output = capture_main(module, [command])
            require(code == 0, f"{command} did not return 0")
            require(output.strip().startswith("{"), f"{command} did not produce JSON")

        preview_receipts = sorted(module.RECEIPT_DIR.glob("LOCAL_APPROVED_MEMORY_CONTEXT_PREVIEW_*.json"))
        require(preview_receipts, "context preview receipt missing")
        preview = json.loads(preview_receipts[-1].read_text(encoding="utf-8"))
        require(preview.get("approval_required_for_preview") is False, "preview unexpectedly requires approval")
        require(preview.get("visible_context_only") is True, "context is not visible-only")
        require(preview.get("hidden_prompt_context") is False, "hidden prompt context enabled")
        require(preview.get("automatic_context_injection_enabled") is False, "automatic context injection enabled")
        require(preview.get("global_trusted_memory") is False, "context became global trusted memory")
        require(preview.get("memory_write_performed") is False, "preview wrote memory")
        context_text = (temp_root / preview["context_preview_path"]).read_text(encoding="utf-8", errors="replace")
        require("APPROVED LOCAL CHAT MEMORY CONTEXT" in context_text, "context label missing")
        require(len(context_text) <= module.MAX_CONTEXT_CHARS + 200, "context exceeded bounded size")

        wrong_code, wrong_output = capture_main(module, ["run-with-preview-context", "--prompt", "hello", "--approval", "WRONG"])
        require(wrong_code == 0, "wrong-token run command did not return 0")
        wrong = json.loads(wrong_output)
        require(wrong.get("approval_token_verified") is False, "wrong token was accepted")
        require(wrong.get("command_executed") is False, "wrong-token path executed command")

        missing_code, missing_output = capture_main(module, ["run-with-preview-context", "--prompt", "hello"])
        require(missing_code == 0, "missing-token run command did not return 0")
        missing = json.loads(missing_output)
        require(missing.get("approval_token_verified") is False, "missing token was accepted")
        require(missing.get("command_executed") is False, "missing-token path executed command")

        empty_code, empty_output = capture_main(module, ["run-with-preview-context", "--prompt", "", "--approval", module.APPROVAL_TOKEN])
        require(empty_code == 0, "empty-prompt run command did not return 0")
        empty = json.loads(empty_output)
        require(empty.get("command_executed") is False, "empty prompt executed command")

        long_prompt = "x" * (module.PROMPT_MAX_LENGTH + 1)
        long_code, long_output = capture_main(module, ["run-with-preview-context", "--prompt", long_prompt, "--approval", module.APPROVAL_TOKEN])
        require(long_code == 0, "over-length run command did not return 0")
        over = json.loads(long_output)
        require(over.get("command_executed") is False, "over-length prompt executed command")

        valid_code, valid_output = capture_main(module, ["run-with-preview-context", "--prompt", "Use visible context.", "--approval", module.APPROVAL_TOKEN])
        require(valid_code == 0, "missing-runtime blocked run did not return 0")
        valid = json.loads(valid_output)
        require(valid.get("command_executed") is False, "fixture run executed despite missing runtime")


def static_checks(module: Any) -> None:
    require(MODULE_PATH.exists(), "module missing")
    require(GUI_PATH.exists(), "GUI host missing")
    py_compile.compile(str(MODULE_PATH), doraise=True)
    py_compile.compile(str(GUI_PATH), doraise=True)
    py_compile.compile(str(READINESS_PATH), doraise=True)
    py_compile.compile(str(Path(__file__)), doraise=True)

    module.main(["status"])
    module_text = read_text(MODULE_PATH)
    gui_text = read_text(GUI_PATH)
    readiness_text = read_text(READINESS_PATH)
    commands_text = read_text(COMMANDS_PATH)
    codex_text = read_text(CODEX_VERIFY)

    for folder in REQUIRED_DIRS:
        require(folder.exists(), f"required folder missing: {folder}")
    require(REPORT_PATH.exists(), "bridge report missing")
    report_text = read_text(REPORT_PATH)
    require("visible bounded approved local chat memory context" in report_text.lower(), "report missing visible context summary")
    require("Packaging skipped" in report_text, "report does not mark packaging skipped")

    for marker in [
        "APPROVE_LOCAL_APPROVED_MEMORY_CONTEXT_RUN",
        "PROMPT_MAX_LENGTH = 500",
        "MAX_CONTEXT_CHARS = 1500",
        "MAX_RECORDS = 3",
        "N_PREDICT = 96",
        "shell=False",
        "stdin=subprocess.DEVNULL",
        "timeout=HELP_TIMEOUT_SECONDS",
        "timeout=PROCESS_LIST_TIMEOUT_SECONDS",
        "visible_context_only",
        "hidden_prompt_context",
        "automatic_context_injection_enabled",
        "global_trusted_memory",
        "memory_write_performed",
        "output_marked_untrusted",
        "model_output_trusted",
    ]:
        require(marker in module_text, f"module missing marker: {marker}")
    require("shell=True" not in module_text, "module contains shell=True")
    for forbidden in ["requests.", "urllib", "webbrowser"]:
        require(forbidden not in module_text, f"forbidden provider/server marker in module: {forbidden}")

    for marker in [
        "Engel Local AI — Approved Memory Context Preview",
        "LocalAIApprovedMemoryContextPreviewBox",
        "Context run prompt",
        "0 / 500",
        "Run One Context Prompt",
        "Build Visible Context Preview",
        "Open Latest Context Run Receipt",
        "run_with_preview_context(prompt, approval)",
        "local_ai_approved_memory_context_approval_input.clear()",
        "UNTRUSTED LOCAL MODEL OUTPUT",
        "Hidden prompt context: disabled",
        "Automatic context injection: disabled",
    ]:
        require(marker in gui_text, f"GUI missing marker: {marker}")
    helper_start = gui_text.index("# ENGEL_AI_READ_ONLY_LOCAL_CHAT_PANEL_INTEGRATION_V1_START")
    helper_end = gui_text.index("# ENGEL_AI_READ_ONLY_LOCAL_CHAT_PANEL_INTEGRATION_V1_END")
    panel_start = gui_text.index("# ENGEL_AI_READ_ONLY_LOCAL_CHAT_PANEL_INTEGRATION_V1_PANEL_START")
    panel_end = gui_text.index("# ENGEL_AI_READ_ONLY_LOCAL_CHAT_PANEL_INTEGRATION_V1_PANEL_END")
    supervised_start = gui_text.find("Engel Local AI — Supervised Open Chat", panel_start, panel_end)
    panel_slice_end = supervised_start if supervised_start != -1 else panel_end
    combined = gui_text[helper_start:helper_end] + gui_text[panel_start:panel_slice_end]
    require("APPROVE_LOCAL_APPROVED_MEMORY_CONTEXT_RUN" not in combined, "GUI must not store raw context-run approval token")
    for forbidden in ["shell=True", "llama-server.exe", "rpc-server.exe", "trusted_memory_write_enabled\": True", "runtime_ready_for_inference\": True", "open_chat_enabled\": True"]:
        require(forbidden.lower() not in combined.lower(), "GUI context section contains forbidden text: " + forbidden)

    for marker in [
        "local_approved_memory_context_preview_available",
        "local_approved_memory_context_run_passed",
        "approved_local_memory_visible_context_run_available",
        "hidden_prompt_context_enabled",
        "automatic_context_injection_enabled",
        "ENGEL_AI_LOCAL_MEMORY_AWARE_CHAT_DRAFT_V1",
    ]:
        require(marker in readiness_text, f"readiness missing marker: {marker}")
    require("approved memory context preview" in commands_text.lower(), "command docs missing context preview")
    require("verify_engel_ai_local_approved_memory_context_preview.py" in codex_text, "codex verifier registration missing")


def chained_verifiers() -> None:
    verifiers = [
        "tools/verify_engel_ai_local_approved_memory_readback.py",
        "tools/verify_engel_ai_local_chat_session_memory_candidate_review_and_approved_write.py",
        "tools/verify_engel_ai_local_chat_session_review.py",
        "tools/verify_engel_ai_local_chat_session_draft.py",
        "tools/verify_engel_ai_local_chat_prompt_draft.py",
        "tools/verify_engel_ai_bounded_local_chat_smoke.py",
        "tools/verify_engel_ai_local_chat_panel_enable_bounded_run.py",
        "tools/verify_engel_ai_read_only_local_chat_panel_integration.py",
        "tools/verify_engel_ai_runtime_readiness.py",
        "tools/verify_engel_memory_roots_storage_layout.py",
    ]
    for verifier in verifiers:
        path = PROJECT_ROOT / verifier
        require(path.exists(), f"required predecessor verifier missing: {verifier}")
        py_compile.compile(str(path), doraise=True)


def main() -> int:
    module = load_module()
    static_checks(module)
    fixture_tests(module)
    chained_verifiers()
    print("ENGEL_AI_LOCAL_APPROVED_MEMORY_CONTEXT_PREVIEW_VERIFY_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
