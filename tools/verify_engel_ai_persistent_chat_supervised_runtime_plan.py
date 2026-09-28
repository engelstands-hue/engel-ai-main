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
MODULE_PATH = PROJECT_ROOT / "engel_ai_persistent_chat_supervised_runtime_plan.py"
GUI_PATH = PROJECT_ROOT / "engel_companion.py"
READINESS_PATH = PROJECT_ROOT / "engel_ai_runtime_readiness.py"
PLAN_JSON = PROJECT_ROOT / "memory" / "ENGEL_AI_PERSISTENT_CHAT_SUPERVISED_RUNTIME_PLAN_V1.json"
PLAN_MD = PROJECT_ROOT / "memory" / "ENGEL_AI_PERSISTENT_CHAT_SUPERVISED_RUNTIME_PLAN_V1.md"
REPORT_PATH = PROJECT_ROOT / "reports" / "codex_bridge" / "ENGEL_AI_PERSISTENT_CHAT_SUPERVISED_RUNTIME_PLAN_V1.md"
REPORT_ROOT = PROJECT_ROOT / "reports" / "ai_persistent_chat_supervised_runtime_plan"
COMMANDS_PATH = PROJECT_ROOT / "memory" / "ENGEL_COMMANDS.md"
CODEX_VERIFY = PROJECT_ROOT / "scripts" / "codex_verify.ps1"

CHAIN_VERIFIERS = [
    PROJECT_ROOT / "tools" / "verify_engel_ai_local_open_chat_supervised_run.py",
    PROJECT_ROOT / "tools" / "verify_engel_ai_local_approved_memory_context_preview.py",
    PROJECT_ROOT / "tools" / "verify_engel_ai_local_approved_memory_readback.py",
    PROJECT_ROOT / "tools" / "verify_engel_ai_local_chat_session_memory_candidate_review_and_approved_write.py",
    PROJECT_ROOT / "tools" / "verify_engel_ai_local_chat_session_draft.py",
    PROJECT_ROOT / "tools" / "verify_engel_ai_bounded_local_chat_smoke.py",
    PROJECT_ROOT / "tools" / "verify_engel_ai_runtime_readiness.py",
    PROJECT_ROOT / "tools" / "verify_engel_memory_roots_storage_layout.py",
]

REQUIRED_DIRS = [
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


def load_module() -> Any:
    sys.path.insert(0, str(PROJECT_ROOT))
    return importlib.import_module("engel_ai_persistent_chat_supervised_runtime_plan")


def capture_main(module: Any, args: list[str]) -> tuple[int, str]:
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        code = module.main(args)
    return int(code), buffer.getvalue()


def configure_temp_paths(module: Any, temp_root: Path) -> None:
    module.PROJECT_ROOT = temp_root
    module.MEMORY_PLAN_JSON = temp_root / "memory" / "ENGEL_AI_PERSISTENT_CHAT_SUPERVISED_RUNTIME_PLAN_V1.json"
    module.MEMORY_PLAN_MD = temp_root / "memory" / "ENGEL_AI_PERSISTENT_CHAT_SUPERVISED_RUNTIME_PLAN_V1.md"
    module.REPORT_ROOT = temp_root / "reports" / "ai_persistent_chat_supervised_runtime_plan"
    module.RECEIPT_DIR = module.REPORT_ROOT / "receipts"
    module.PLAN_REPORT_DIR = module.REPORT_ROOT / "reports"
    module.EXAMPLE_DIR = module.REPORT_ROOT / "examples"
    module.CODEX_REPORT = temp_root / "reports" / "codex_bridge" / "ENGEL_AI_PERSISTENT_CHAT_SUPERVISED_RUNTIME_PLAN_V1.md"
    module.SUPERVISED_OPEN_CHAT_RECEIPTS = temp_root / "reports" / "ai_local_open_chat_supervised_run" / "receipts"
    module.RUNTIME_PATH = str(temp_root / "runtime" / "llama-cli.exe")
    module.MODEL_FILE = str(temp_root / "models" / "tiny.gguf")
    module.SUPERVISED_OPEN_CHAT_RECEIPTS.mkdir(parents=True, exist_ok=True)
    (temp_root / "runtime").mkdir(parents=True, exist_ok=True)
    (temp_root / "models").mkdir(parents=True, exist_ok=True)
    (temp_root / "runtime" / "llama-cli.exe").write_text("fixture runtime\n", encoding="utf-8")
    (temp_root / "models" / "tiny.gguf").write_text("fixture model\n", encoding="utf-8")
    (module.SUPERVISED_OPEN_CHAT_RECEIPTS / "LOCAL_OPEN_CHAT_SUPERVISED_TURN_fixture.json").write_text(
        json.dumps(
            {
                "local_open_chat_supervised_run_version": "1",
                "local_open_chat_supervised_turn_passed": True,
                "open_chat_enabled": True,
                "open_chat_scope": "supervised_local_gui_session_only",
                "chat_enabled": True,
                "chat_scope": "supervised_local_gui_session_only",
                "persistent_chat_loop_enabled": False,
                "server_enabled": False,
                "provider_api_enabled": False,
                "trusted_memory_write_enabled": False,
                "runtime_ready_for_inference": False,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def check_cli_fixture(module: Any) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        temp_root = Path(tmp)
        configure_temp_paths(module, temp_root)
        for args in [["status"], ["plan"], ["json"]]:
            code, output = capture_main(module, args)
            require(code == 0, "command failed: " + " ".join(args))
            payload = json.loads(output)
            require(payload.get("persistent_chat_enabled") is False, "persistent chat must stay disabled")
            require(payload.get("persistent_runtime_enabled") is False, "persistent runtime must stay disabled")
            require(payload.get("true_long_lived_model_process_enabled") is False, "long-lived process must stay disabled")
            require(payload.get("server_enabled") is False, "server must stay disabled")
            require(payload.get("provider_api_enabled") is False, "provider must stay disabled")
            require(payload.get("startup_auto_load_enabled") is False, "startup auto-load must stay disabled")
            require(payload.get("trusted_memory_write_enabled") is False, "trusted memory write must stay disabled")
            require(payload.get("approved_memory_write_enabled") is False, "approved memory write must stay disabled")
            require(payload.get("source_route_queue_mutation") is False, "source/route/queue mutation must stay disabled")
            require(payload.get("runtime_process_started") is False, "command must not start runtime")
            require(payload.get("model_process_started") is False, "command must not start model")
            require(payload.get("recommended_next_mode") == "supervised_persistent_gui_session_repeated_bounded_calls", "wrong recommendation")
            require(payload.get("stop_button_required") is True or args[0] != "plan", "stop button requirement missing")
            require(payload.get("panic_cleanup_required") is True or args[0] != "plan", "panic cleanup requirement missing")
            require(payload.get("orphan_cleanup_required") is True or args[0] != "plan", "orphan cleanup requirement missing")
            require(payload.get("crash_receipt_required") is True or args[0] != "plan", "crash receipt requirement missing")
        require(module.MEMORY_PLAN_JSON.exists(), "fixture plan JSON not written")
        require(module.MEMORY_PLAN_MD.exists(), "fixture plan Markdown not written")
        require(module.CODEX_REPORT.exists(), "fixture bridge report not written")
        require(any(module.RECEIPT_DIR.glob("PERSISTENT_CHAT_SUPERVISED_RUNTIME_PLAN_*.json")), "fixture receipt not written")


def check_static_files(module: Any) -> None:
    for path in [MODULE_PATH, GUI_PATH, READINESS_PATH, Path(__file__)]:
        require(path.exists(), "missing file: " + str(path))
        py_compile.compile(str(path), doraise=True)
    module.main(["status"])
    for path in [PLAN_JSON, PLAN_MD, REPORT_PATH, COMMANDS_PATH, CODEX_VERIFY]:
        require(path.exists(), "missing required file: " + str(path))
    for folder in REQUIRED_DIRS:
        require(folder.exists(), "required folder missing: " + str(folder))
    json.loads(read_text(PLAN_JSON))

    module_text = read_text(MODULE_PATH)
    gui_text = read_text(GUI_PATH)
    readiness_text = read_text(READINESS_PATH)
    commands_text = read_text(COMMANDS_PATH)
    codex_text = read_text(CODEX_VERIFY)
    report_text = read_text(REPORT_PATH)

    for marker in [
        "persistent_chat_supervised_runtime_plan_version",
        "persistent_chat_enabled",
        "persistent_runtime_enabled",
        "true_long_lived_model_process_enabled",
        "supervised_persistent_gui_session_repeated_bounded_calls",
        "ENGEL_AI_PERSISTENT_CHAT_SUPERVISED_SESSION_V1",
        "ENGEL_AI_PERSISTENT_MODEL_PROCESS_SUPERVISED_RUNTIME_V1",
        "MAX_SESSION_TURNS = 20",
        "MAX_IDLE_SECONDS = 300",
        "MAX_RUNTIME_MINUTES = 30",
        "MAX_PROMPT_CHARS_PER_TURN = 1000",
        "MAX_RESPONSE_TOKENS_PER_TURN = 192",
        "MAX_TRANSCRIPT_CONTEXT_CHARS = 4000",
        "stop_button_required",
        "panic_cleanup_required",
        "orphan_cleanup_required",
        "crash_receipt_required",
        "stop_receipt_required",
        "orphan_cleanup_receipt_required",
    ]:
        require(marker in module_text, "module missing marker: " + marker)
    for forbidden in [
        "subprocess",
        "Popen",
        "shell=True",
        "llama-server.exe",
        "rpc-server.exe",
        "ollama",
        "requests.",
        "urllib",
        "webbrowser",
        "openai",
        "anthropic",
        "wsl.exe",
        "docker",
        "pip install",
        "Invoke-WebRequest",
        "curl ",
    ]:
        require(forbidden.lower() not in module_text.lower(), "module contains forbidden behavior text: " + forbidden)

    for marker in [
        "Engel Local AI — Persistent Chat Runtime Plan",
        "Refresh Persistent Plan Status",
        "Open Persistent Plan",
        "Open Latest Plan Receipt",
        "Persistent runtime enabled: false",
        "True long-lived model process: not enabled",
        "Stop button required: yes",
        "Panic cleanup required: yes",
        "Crash/orphan receipts required: yes",
        "ENGEL_AI_PERSISTENT_CHAT_SUPERVISED_SESSION_V1",
    ]:
        require(marker in gui_text, "GUI missing marker: " + marker)
    section_start = gui_text.index("Engel Local AI — Persistent Chat Runtime Plan")
    section_end = gui_text.find("self.local_ai_status_note = QLabel", section_start)
    section = gui_text[section_start: section_end if section_end != -1 else section_start + 5000]
    require("Start Persistent Chat" not in section, "GUI must not include Start Persistent Chat button in this phase")
    require("subprocess.run" not in section and "subprocess.Popen" not in section, "GUI plan section must not run subprocesses")

    for marker in [
        "PERSISTENT_CHAT_SUPERVISED_RUNTIME_PLAN_RECEIPTS",
        "persistent_chat_supervised_runtime_plan_entries",
        "persistent_chat_plan_available",
        "recommended_persistent_next_mode",
        "ENGEL_AI_PERSISTENT_CHAT_SUPERVISED_SESSION_V1",
    ]:
        require(marker in readiness_text, "readiness missing marker: " + marker)
    require("persistent chat supervised runtime plan" in commands_text.lower(), "command docs missing plan command")
    require("tools\\verify_engel_ai_persistent_chat_supervised_runtime_plan.py" in codex_text, "codex verify missing verifier")
    require("Persistent chat is not enabled" in report_text, "bridge report must state persistent chat is not enabled")

    for verifier in CHAIN_VERIFIERS:
        require(verifier.exists(), "missing chained verifier: " + str(verifier))
        py_compile.compile(str(verifier), doraise=True)


def main() -> int:
    try:
        module = load_module()
        check_static_files(module)
        check_cli_fixture(module)
    except Exception as exc:
        print("ENGEL_AI_PERSISTENT_CHAT_SUPERVISED_RUNTIME_PLAN_VERIFY_FAIL")
        print(str(exc))
        return 1
    print("ENGEL_AI_PERSISTENT_CHAT_SUPERVISED_RUNTIME_PLAN_VERIFY_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
