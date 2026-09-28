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
MODULE_PATH = PROJECT_ROOT / "engel_ai_local_open_chat_supervised_run.py"
GUI_PATH = PROJECT_ROOT / "engel_companion.py"
READINESS_PATH = PROJECT_ROOT / "engel_ai_runtime_readiness.py"
REPORT_PATH = PROJECT_ROOT / "reports" / "codex_bridge" / "ENGEL_AI_LOCAL_OPEN_CHAT_SUPERVISED_RUN_V1.md"
COMMANDS_PATH = PROJECT_ROOT / "memory" / "ENGEL_COMMANDS.md"
CODEX_VERIFY = PROJECT_ROOT / "scripts" / "codex_verify.ps1"
REPORT_ROOT = PROJECT_ROOT / "reports" / "ai_local_open_chat_supervised_run"

REQUIRED_DIRS = [
    REPORT_ROOT / "logs",
    REPORT_ROOT / "receipts",
    REPORT_ROOT / "sessions",
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
    return importlib.import_module("engel_ai_local_open_chat_supervised_run")


def capture_main(module: Any, args: list[str]) -> tuple[int, str]:
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        code = module.main(args)
    return int(code), buffer.getvalue()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def configure_temp_paths(module: Any, temp_root: Path) -> None:
    phase_root = temp_root / "reports" / "ai_local_open_chat_supervised_run"
    context_root = temp_root / "reports" / "ai_local_approved_memory_context_preview"
    source_root = temp_root / "reports" / "ai_local_chat_session_memory_candidate_review_and_approved_write"
    readback_root = temp_root / "reports" / "ai_local_approved_memory_readback"

    module.PROJECT_ROOT = temp_root
    module.REPORT_ROOT = phase_root
    module.LOG_DIR = phase_root / "logs"
    module.RECEIPT_DIR = phase_root / "receipts"
    module.SESSION_DIR = phase_root / "sessions"
    module.PLAN_REPORT_DIR = phase_root / "reports"
    module.EXAMPLE_DIR = phase_root / "examples"
    module.CODEX_REPORT = temp_root / "reports" / "codex_bridge" / "ENGEL_AI_LOCAL_OPEN_CHAT_SUPERVISED_RUN_V1.md"
    module.RUNTIME_PATH = temp_root / "missing-runtime.exe"
    module.MODEL_FILE = temp_root / "missing-model.gguf"

    context = module.approved_context
    context.PROJECT_ROOT = temp_root
    context.APPROVED_RECORD_DIR = source_root / "approved_memory_records"
    context.ROLLBACK_DIR = source_root / "rollback"
    context.READBACK_RECEIPT_DIR = readback_root / "receipts"
    context.REPORT_ROOT = context_root
    context.CONTEXT_DIR = context_root / "contexts"
    context.LOG_DIR = context_root / "logs"
    context.RECEIPT_DIR = context_root / "receipts"
    context.PLAN_REPORT_DIR = context_root / "reports"
    context.EXAMPLE_DIR = context_root / "examples"
    context.CODEX_REPORT = temp_root / "reports" / "codex_bridge" / "ENGEL_AI_LOCAL_APPROVED_MEMORY_CONTEXT_PREVIEW_V1.md"

    for folder in [
        module.LOG_DIR,
        module.RECEIPT_DIR,
        module.SESSION_DIR,
        module.PLAN_REPORT_DIR,
        module.EXAMPLE_DIR,
        module.CODEX_REPORT.parent,
        context.APPROVED_RECORD_DIR,
        context.ROLLBACK_DIR,
        context.READBACK_RECEIPT_DIR,
        context.CONTEXT_DIR,
        context.LOG_DIR,
        context.RECEIPT_DIR,
        context.PLAN_REPORT_DIR,
        context.EXAMPLE_DIR,
    ]:
        folder.mkdir(parents=True, exist_ok=True)

    write_json(
        context.APPROVED_RECORD_DIR / "APPROVED_LOCAL_CHAT_MEMORY_RECORD_safeid.json",
        {
            "approved_local_chat_memory_record_version": "1",
            "approved_memory_scope": "approved_local_chat_memory_record_only",
            "source_model_output_trusted": False,
            "candidate_content_obeyed": False,
            "deterministic_guardian_gates_passed": True,
            "trusted_memory_write_enabled_global": False,
            "prompt_summary": "Safe approved local memory context.",
            "bounded_summary": "A bounded visible approved memory context exists.",
        },
    )
    write_json(context.ROLLBACK_DIR / "ROLLBACK_APPROVED_LOCAL_CHAT_MEMORY_RECORD_safeid.json", {"rollback_metadata_version": "1"})
    write_json(
        context.READBACK_RECEIPT_DIR / "LOCAL_APPROVED_MEMORY_READBACK_safeid.json",
        {
            "local_approved_memory_readback_version": "1",
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


def fixture_tests(module: Any) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        temp_root = Path(tmp)
        configure_temp_paths(module, temp_root)
        for command in [["status"], ["preview", "--prompt", "hello"], ["json"]]:
            code, output = capture_main(module, command)
            require(code == 0, "command failed: " + " ".join(command))
            require(output.strip().startswith("{"), "command did not emit JSON: " + " ".join(command))

        preview = json.loads(capture_main(module, ["preview", "--prompt", "hello"])[1])
        require(preview.get("command_executed") is False, "preview executed command")
        require(preview.get("runtime_process_started") is False, "preview ran runtime")
        require("APPROVED LOCAL CHAT MEMORY CONTEXT" in preview.get("constructed_prompt_preview", ""), "preview missing visible context")
        require("UNTRUSTED LOCAL SESSION TRANSCRIPT" in preview.get("constructed_prompt_preview", ""), "preview missing untrusted transcript label")

        empty = json.loads(capture_main(module, ["send", "--prompt", ""])[1])
        require(empty.get("command_executed") is False, "empty prompt executed command")
        require(empty.get("human_approval_token_required") is False, "send unexpectedly requires approval token")

        long_prompt = "x" * (module.PROMPT_MAX_LENGTH + 1)
        over = json.loads(capture_main(module, ["send", "--prompt", long_prompt])[1])
        require(over.get("command_executed") is False, "over-length prompt executed command")

        missing_runtime = json.loads(capture_main(module, ["send", "--prompt", "hello"])[1])
        require(missing_runtime.get("command_executed") is False, "missing runtime fixture executed command")
        require(missing_runtime.get("open_chat_enabled") is True, "supervised scope must be represented even on blocked send")
        require(missing_runtime.get("open_chat_scope") == "supervised_local_gui_session_only", "open chat scope missing")

        session = module.load_session()
        session["turns"] = [{"turn_number": i + 1, "user_prompt": "u", "model_output_preview": "m"} for i in range(module.SESSION_TURN_MAX)]
        module.save_session(session)
        full = json.loads(capture_main(module, ["send", "--prompt", "hello"])[1])
        require(full.get("command_executed") is False, "turn-limit fixture executed command")


def static_checks(module: Any) -> None:
    for path in [MODULE_PATH, GUI_PATH, READINESS_PATH, Path(__file__)]:
        require(path.exists(), "missing file: " + str(path))
        py_compile.compile(str(path), doraise=True)

    module.main(["status"])
    module_text = read_text(MODULE_PATH)
    gui_text = read_text(GUI_PATH)
    readiness_text = read_text(READINESS_PATH)
    commands_text = read_text(COMMANDS_PATH)
    codex_text = read_text(CODEX_VERIFY)

    for folder in REQUIRED_DIRS:
        require(folder.exists(), "required folder missing: " + str(folder))
    require(REPORT_PATH.exists(), "bridge report missing")
    report_text = read_text(REPORT_PATH)
    require("supervised local open chat" in report_text.lower(), "report missing supervised chat summary")
    require("Packaging skipped" in report_text, "report does not mark packaging skipped")
    require("ENGEL_AI_PERSISTENT_CHAT_SUPERVISED_RUNTIME_PLAN_V1" in report_text, "future persistent chat plan missing")
    require("ENGEL_AI_PROVIDER_CLOUD_BRIDGE_PLAN_V1" in report_text, "future provider/cloud bridge plan missing")

    for marker in [
        "PROMPT_MAX_LENGTH = 1000",
        "SESSION_TURN_MAX = 10",
        "MAX_APPROVED_MEMORY_CONTEXT_CHARS = 1500",
        "MAX_TRANSCRIPT_CONTEXT_CHARS = 2000",
        "N_PREDICT = 192",
        "shell=False",
        "stdin=subprocess.DEVNULL",
        "TIMEOUT_SECONDS = 180",
        "human_approval_token_required",
        "supervised_local_open_chat",
        "supervised_local_gui_session_only",
        "APPROVED LOCAL CHAT MEMORY CONTEXT",
        "UNTRUSTED LOCAL SESSION TRANSCRIPT",
        "output_marked_untrusted",
        "model_output_trusted",
        "memory_write_performed",
        "persistent_chat_loop_enabled",
        "background_worker_enabled",
        "startup_auto_load_enabled",
    ]:
        require(marker in module_text, "module missing marker: " + marker)
    require("APPROVE_" not in module_text, "supervised chat module must not use an approval token")
    require("shell=True" not in module_text, "module contains shell=True")
    for forbidden in ["requests.", "urllib", "webbrowser", "openai", "anthropic", "wsl.exe", "docker", "Hermes"]:
        require(forbidden.lower() not in module_text.lower(), "forbidden provider/runtime marker in module: " + forbidden)

    for marker in [
        "Engel Local AI — Supervised Open Chat",
        "Enable Supervised Local Chat",
        "Send Local Message",
        "Clear Local Session",
        "Open Latest Receipt",
        "LocalAISupervisedOpenChatTranscript",
        "local_ai_supervised_open_chat_enabled = False",
        "send_supervised_message(prompt)",
        "UNTRUSTED LOCAL SESSION TRANSCRIPT",
        "Output: UNTRUSTED",
        "Persistent chat: disabled",
        "Server mode: disabled",
        "Provider/cloud: disabled",
        "Trusted memory write: disabled",
        "Approved memory write: disabled",
        "Startup auto-load: disabled",
        "Hidden context: disabled",
    ]:
        require(marker in gui_text, "GUI missing marker: " + marker)
    section_start = gui_text.index("Engel Local AI — Supervised Open Chat")
    next_section = gui_text.find("self.local_ai_status_note = QLabel", section_start)
    section = gui_text[section_start: next_section if next_section != -1 else section_start + 9000]
    require("APPROVE_LOCAL_OPEN_CHAT" not in section, "GUI stores an approval token for supervised open chat")
    require("subprocess.run" not in section and "subprocess.Popen" not in section, "GUI duplicates runtime subprocess logic")
    require(".clicked.connect(self.send_local_ai_supervised_open_chat_message)" in gui_text, "send button not wired")
    require(".clicked.connect(self.enable_local_ai_supervised_open_chat)" in gui_text, "enable button not wired")
    require("enable_local_ai_supervised_open_chat" in gui_text and "send_supervised_message(prompt)" in gui_text, "GUI must run only through send path")

    for marker in [
        "local_open_chat_supervised_run_available",
        "open_chat_scope",
        "chat_scope",
        "supervised_local_gui_session_only",
        "ENGEL_AI_PERSISTENT_CHAT_SUPERVISED_RUNTIME_PLAN_V1",
        "runtime_ready_for_inference",
    ]:
        require(marker in readiness_text, "readiness missing marker: " + marker)

    require("supervised local open chat" in commands_text.lower(), "command docs missing supervised open chat")
    require("verify_engel_ai_local_open_chat_supervised_run.py" in codex_text, "codex verifier registration missing")


def chained_verifiers() -> None:
    verifiers = [
        "tools/verify_engel_ai_local_approved_memory_context_preview.py",
        "tools/verify_engel_ai_local_approved_memory_readback.py",
        "tools/verify_engel_ai_local_chat_session_memory_candidate_review_and_approved_write.py",
        "tools/verify_engel_ai_local_chat_session_review.py",
        "tools/verify_engel_ai_local_chat_session_draft.py",
        "tools/verify_engel_ai_local_chat_prompt_draft.py",
        "tools/verify_engel_ai_bounded_local_chat_smoke.py",
        "tools/verify_engel_ai_runtime_readiness.py",
        "tools/verify_engel_memory_roots_storage_layout.py",
    ]
    for verifier in verifiers:
        path = PROJECT_ROOT / verifier
        require(path.exists(), "required predecessor verifier missing: " + verifier)
        py_compile.compile(str(path), doraise=True)


def main() -> int:
    module = load_module()
    static_checks(module)
    fixture_tests(module)
    chained_verifiers()
    print("ENGEL_AI_LOCAL_OPEN_CHAT_SUPERVISED_RUN_VERIFY_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
