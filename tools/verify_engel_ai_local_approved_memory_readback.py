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
MODULE_PATH = PROJECT_ROOT / "engel_ai_local_approved_memory_readback.py"
GUI_PATH = PROJECT_ROOT / "engel_companion.py"
READINESS_PATH = PROJECT_ROOT / "engel_ai_runtime_readiness.py"
REPORT_PATH = PROJECT_ROOT / "reports" / "codex_bridge" / "ENGEL_AI_LOCAL_APPROVED_MEMORY_READBACK_V1.md"
COMMANDS_PATH = PROJECT_ROOT / "memory" / "ENGEL_COMMANDS.md"
CODEX_VERIFY = PROJECT_ROOT / "scripts" / "codex_verify.ps1"
REPORT_ROOT = PROJECT_ROOT / "reports" / "ai_local_approved_memory_readback"

REQUIRED_DIRS = [
    REPORT_ROOT / "readbacks",
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
    return importlib.import_module("engel_ai_local_approved_memory_readback")


def capture_main(module: Any, args: list[str]) -> tuple[int, str]:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = module.main(args)
    return int(code), buf.getvalue()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def configure_temp_paths(module: Any, temp_root: Path) -> tuple[Path, Path, Path]:
    source_root = temp_root / "reports" / "ai_local_chat_session_memory_candidate_review_and_approved_write"
    readback_root = temp_root / "reports" / "ai_local_approved_memory_readback"
    module.PROJECT_ROOT = temp_root
    module.SOURCE_ROOT = source_root
    module.APPROVED_RECORD_DIR = source_root / "approved_memory_records"
    module.ROLLBACK_DIR = source_root / "rollback"
    module.WRITE_RECEIPT_DIR = source_root / "receipts"
    module.REPORT_ROOT = readback_root
    module.READBACK_DIR = readback_root / "readbacks"
    module.RECEIPT_DIR = readback_root / "receipts"
    module.PLAN_REPORT_DIR = readback_root / "reports"
    module.EXAMPLE_DIR = readback_root / "examples"
    module.CODEX_REPORT = temp_root / "reports" / "codex_bridge" / "ENGEL_AI_LOCAL_APPROVED_MEMORY_READBACK_V1.md"
    for folder in [
        module.APPROVED_RECORD_DIR,
        module.ROLLBACK_DIR,
        module.WRITE_RECEIPT_DIR,
        module.READBACK_DIR,
        module.RECEIPT_DIR,
        module.PLAN_REPORT_DIR,
        module.EXAMPLE_DIR,
        module.CODEX_REPORT.parent,
    ]:
        folder.mkdir(parents=True, exist_ok=True)
    record = module.APPROVED_RECORD_DIR / "APPROVED_LOCAL_CHAT_MEMORY_RECORD_safeid.json"
    rollback = module.ROLLBACK_DIR / "ROLLBACK_APPROVED_LOCAL_CHAT_MEMORY_RECORD_safeid.json"
    write_receipt = module.WRITE_RECEIPT_DIR / "APPROVED_LOCAL_CHAT_MEMORY_WRITE_safeid.json"
    write_json(
        record,
        {
            "approved_local_chat_memory_record_version": "1",
            "approval_basis": "deterministic_guardian_gates_passed",
            "human_approval_required": False,
            "approval_token_required": False,
            "approved_memory_scope": "approved_local_chat_memory_record_only",
            "source_candidate_path": "reports\\ai_local_chat_session_review\\memory_candidate_drafts\\candidate.json",
            "source_review_receipt": "reports\\ai_local_chat_session_memory_candidate_review_and_approved_write\\receipts\\review.json",
            "source_model_output_trusted": False,
            "candidate_content_obeyed": False,
            "deterministic_guardian_gates_passed": True,
            "trusted_memory_write_enabled_global": False,
            "runtime_ready_for_inference": False,
            "open_chat_enabled": False,
            "bounded_summary": "A bounded approved local chat memory record summary. This is not hidden prompt context.",
        },
    )
    write_json(rollback, {"rollback_metadata_version": "1", "trusted_memory_target_touched": False})
    write_json(
        write_receipt,
        {
            "local_chat_session_memory_candidate_approved_write_version": "1",
            "approved_memory_record_path": "reports\\ai_local_chat_session_memory_candidate_review_and_approved_write\\approved_memory_records\\APPROVED_LOCAL_CHAT_MEMORY_RECORD_safeid.json",
            "deterministic_guardian_gates_passed": True,
            "runtime_process_started": False,
            "model_process_started": False,
        },
    )
    return record, rollback, write_receipt


def fixture_tests(module: Any) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        temp_root = Path(tmp)
        record, _rollback, _write_receipt = configure_temp_paths(module, temp_root)
        for command in ["status", "list", "json", "read-latest", "read-all"]:
            code, output = capture_main(module, [command])
            require(code == 0, f"{command} did not return 0")
            require(output.strip().startswith("{"), f"{command} did not produce JSON")
        receipts = sorted(module.RECEIPT_DIR.glob("LOCAL_APPROVED_MEMORY_READBACK_*.json"))
        require(receipts, "readback receipt missing")
        receipt = json.loads(receipts[-1].read_text(encoding="utf-8"))
        require(receipt.get("approval_required_for_readback") is False, "readback unexpectedly requires approval")
        require(receipt.get("memory_write_performed") is False, "readback wrote memory")
        require(receipt.get("global_trusted_memory") is False, "record became global trusted memory")
        require(receipt.get("used_as_hidden_prompt_context") is False, "record became hidden prompt context")
        require(receipt.get("automatic_context_injection_enabled") is False, "automatic context injection enabled")
        require(receipt.get("runtime_process_started") is False, "runtime process started during readback")
        require(receipt.get("model_process_started") is False, "model process started during readback")

        validation = module.validate_record(record)
        require(not validation.get("risk_flags"), "safe fixture produced risk flags")

    with tempfile.TemporaryDirectory() as tmp:
        temp_root = Path(tmp)
        record, rollback, _write_receipt = configure_temp_paths(module, temp_root)
        rollback.unlink()
        validation = module.validate_record(record)
        require("rollback_metadata_present_invalid" in validation.get("risk_flags", []), "missing rollback was not flagged")

    with tempfile.TemporaryDirectory() as tmp:
        temp_root = Path(tmp)
        record, _rollback, _write_receipt = configure_temp_paths(module, temp_root)
        write_json(record, {"approved_local_chat_memory_record_version": "1", "global_trusted_memory": True})
        validation = module.validate_record(record)
        require(validation.get("risk_flags"), "malformed record fixture was not rejected/not trusted")


def static_checks() -> None:
    require(MODULE_PATH.exists(), "module missing")
    require(GUI_PATH.exists(), "GUI host missing")
    py_compile.compile(str(MODULE_PATH), doraise=True)
    py_compile.compile(str(GUI_PATH), doraise=True)
    py_compile.compile(str(READINESS_PATH), doraise=True)
    py_compile.compile(str(Path(__file__)), doraise=True)

    module_text = read_text(MODULE_PATH)
    gui_text = read_text(GUI_PATH)
    readiness_text = read_text(READINESS_PATH)
    commands_text = read_text(COMMANDS_PATH)
    codex_text = read_text(CODEX_VERIFY)

    require("APPROVE_" not in module_text, "readback module contains approval-token gate")
    for forbidden in ["subprocess", "Popen", "llama-cli.exe", "llama-tokenize.exe", "llama-server.exe", "rpc-server.exe", "ollama", "requests.", "urllib", "webbrowser", "WSL", "Docker", "Hermes"]:
        require(forbidden not in module_text, f"forbidden runtime/provider marker in module: {forbidden}")
    for marker in [
        "approved_record_schema_valid",
        "rollback_metadata_present",
        "source_write_receipt_present",
        "global_trusted_memory",
        "used_as_hidden_prompt_context",
        "automatic_context_injection_enabled",
        "candidate_content_obeyed",
        "memory_write_performed",
        "runtime_ready_for_inference",
        "open_chat_enabled",
    ]:
        require(marker in module_text, f"missing readback marker: {marker}")

    for folder in REQUIRED_DIRS:
        require(folder.exists(), f"required folder missing: {folder}")
    require(REPORT_PATH.exists(), "bridge report missing")
    report_text = read_text(REPORT_PATH)
    require("readback/status" in report_text, "report does not document readback/status")
    require("Packaging skipped" in report_text, "report does not mark packaging skipped")

    for marker in [
        "Engel Local AI — Approved Memory Readback",
        "Global trusted memory: disabled",
        "Hidden prompt context: disabled",
        "Automatic context injection: disabled",
        "Read Latest Approved Record",
        "Read All Approved Records",
        "Open Latest Readback",
        "local_ai_approved_memory_readback",
    ]:
        require(marker in gui_text, f"GUI missing marker: {marker}")
    section_start = gui_text.index("Engel Local AI — Approved Memory Readback")
    next_section = gui_text.find("Engel Local AI — Approved Memory Context Preview", section_start)
    section = gui_text[section_start: next_section if next_section != -1 else section_start + 9000]
    require("APPROVE_" not in section, "readback GUI section asks for approval token")
    require("approval_input" not in section, "readback GUI section introduced approval input")
    require("No model is run" in section or "no model run" in section.lower(), "GUI section does not state no model run")

    for marker in [
        "local_approved_memory_readback_available",
        "approved_local_chat_memory_record_count",
        "global_trusted_memory_enabled",
        "automatic_context_injection_enabled",
        "ENGEL_AI_LOCAL_APPROVED_MEMORY_CONTEXT_PREVIEW_V1",
    ]:
        require(marker in readiness_text, f"readiness missing marker: {marker}")
    require("approved memory readback" in commands_text.lower(), "command docs missing approved memory readback")
    require("verify_engel_ai_local_approved_memory_readback.py" in codex_text, "codex verifier registration missing")


def chained_verifiers() -> None:
    verifiers = [
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
    static_checks()
    module = load_module()
    fixture_tests(module)
    chained_verifiers()
    print("ENGEL_AI_LOCAL_APPROVED_MEMORY_READBACK_VERIFY_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
