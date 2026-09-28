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


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "engel_ai_local_chat_session_review.py"
VERIFIER = ROOT / "tools" / "verify_engel_ai_local_chat_session_review.py"
GUI_HOST = ROOT / "engel_companion.py"
READINESS = ROOT / "engel_ai_runtime_readiness.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_AI_LOCAL_CHAT_PANEL_SESSION_REVIEW_V1.md"
REPORT_ROOT = ROOT / "reports" / "ai_local_chat_session_review"
REVIEWS = REPORT_ROOT / "reviews"
RECEIPTS = REPORT_ROOT / "receipts"
CANDIDATES = REPORT_ROOT / "memory_candidate_drafts"
PLAN_REPORTS = REPORT_ROOT / "reports"
EXAMPLES = REPORT_ROOT / "examples"
COMMANDS = ROOT / "memory" / "ENGEL_COMMANDS.md"
CODEX_VERIFY = ROOT / "scripts" / "codex_verify.ps1"

CHAIN_VERIFIERS = [
    ROOT / "tools" / "verify_engel_ai_local_chat_session_draft.py",
    ROOT / "tools" / "verify_engel_ai_local_chat_prompt_draft.py",
    ROOT / "tools" / "verify_engel_ai_bounded_local_chat_smoke.py",
    ROOT / "tools" / "verify_engel_ai_local_chat_panel_enable_bounded_run.py",
    ROOT / "tools" / "verify_engel_ai_read_only_local_chat_panel_integration.py",
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


def capture_main(module: Any, args: list[str]) -> tuple[int, dict[str, Any]]:
    stream = io.StringIO()
    with redirect_stdout(stream):
        code = module.main(args)
    text = stream.getvalue()
    payload = json.loads(text) if text.strip().startswith("{") else {}
    return code, payload


def configure_fixture_module(module: Any, temp_root: Path) -> None:
    report_root = temp_root / "reports" / "ai_local_chat_session_review"
    module.PROJECT_ROOT = temp_root
    module.SESSION_DRAFT_RECEIPT_DIR = temp_root / "reports" / "ai_local_chat_session_draft" / "receipts"
    module.REPORT_ROOT = report_root
    module.REVIEW_DIR = report_root / "reviews"
    module.RECEIPT_DIR = report_root / "receipts"
    module.MEMORY_CANDIDATE_DIR = report_root / "memory_candidate_drafts"
    module.PLAN_REPORT_DIR = report_root / "reports"
    module.EXAMPLE_DIR = report_root / "examples"
    module.CODEX_REPORT = temp_root / "reports" / "codex_bridge" / "ENGEL_AI_LOCAL_CHAT_PANEL_SESSION_REVIEW_V1.md"
    module.SESSION_DRAFT_RECEIPT_DIR.mkdir(parents=True, exist_ok=True)
    stdout_path = temp_root / "session_stdout.txt"
    stderr_path = temp_root / "session_stderr.txt"
    stdout_path.write_text("Fixture session output. This is untrusted evidence.\n", encoding="utf-8")
    stderr_path.write_text("", encoding="utf-8")
    (module.SESSION_DRAFT_RECEIPT_DIR / "LOCAL_CHAT_SESSION_DRAFT_fixture.json").write_text(
        json.dumps(
            {
                "local_chat_session_draft_version": "1",
                "local_chat_session_draft_turn_passed": True,
                "session_id": "fixture_session",
                "turn_number": 1,
                "prompt": "hello from Engel",
                "prompt_length": 16,
                "output_captured": True,
                "output_marked_untrusted": True,
                "model_output_trusted": False,
                "session_transcript_trusted": False,
                "runtime_ready_for_inference": False,
                "open_chat_enabled": False,
                "trusted_memory_write_enabled": False,
                "orphan_process_detected": False,
                "stdout_log_path": str(stdout_path),
                "stderr_log_path": str(stderr_path),
            }
        ),
        encoding="utf-8",
    )


def check_files_compile_and_report() -> None:
    for path in [MODULE, VERIFIER, GUI_HOST, READINESS, COMMANDS, CODEX_VERIFY, *CHAIN_VERIFIERS]:
        require(path.exists(), "missing required path: " + str(path.relative_to(ROOT)))
    run_command([sys.executable, "-m", "py_compile", str(MODULE)], timeout=120)
    run_command([sys.executable, "-m", "py_compile", str(VERIFIER)], timeout=120)
    run_command([sys.executable, "-m", "py_compile", str(GUI_HOST)], timeout=120)
    module = load_module("engel_ai_local_chat_session_review_for_report", MODULE)
    capture_main(module, ["status"])
    for path in [REPORT, REPORT_ROOT, REVIEWS, RECEIPTS, CANDIDATES, PLAN_REPORTS, EXAMPLES]:
        require(path.exists(), "missing generated path: " + str(path.relative_to(ROOT)))


def check_module_static_safety() -> None:
    source = read(MODULE)
    tree = ast.parse(source)
    for needle in [
        "APPROVE_SESSION_REVIEW_MEMORY_CANDIDATE_DRAFT",
        "local_chat_session_review_version",
        "local_chat_session_review_memory_candidate_draft_version",
        "candidate_type",
        "local_chat_session_review_candidate",
        "trust_state",
        "untrusted",
        "human_review_required",
        "promoted_to_trusted_memory",
        "trusted_memory_write_enabled",
        "approved_memory_write_enabled",
        "model_output_trusted",
        "automatic_learning_enabled",
        "runtime_process_started",
        "model_process_started",
        "runtime_ready_for_inference",
        "open_chat_enabled",
        "SESSION REVIEW RECORDED",
        "UNTRUSTED MEMORY CANDIDATE DRAFT CREATED",
    ]:
        require(needle in source, "module missing required text: " + needle)
    for forbidden in [
        "subprocess",
        "Popen",
        "shell=True",
        "llama-cli.exe",
        "llama-server.exe",
        "rpc-server.exe",
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
        "approved_memory_promotion",
        "promote_to_trusted_memory(",
        "trusted_memory_write_enabled\": True",
        "approved_memory_write_enabled\": True",
        "model_output_trusted\": True",
        "runtime_ready_for_inference\": True",
        "open_chat_enabled\": True",
    ]:
        require(forbidden.lower() not in source.lower(), "module contains forbidden behavior text: " + forbidden)
    for node in ast.walk(tree):
        if isinstance(node, ast.While):
            raise CheckFailure("module contains forbidden persistent loop")


def check_cli_and_fixture_review() -> None:
    module = load_module("engel_ai_local_chat_session_review_fixture", MODULE)
    with tempfile.TemporaryDirectory() as temp_text:
        temp_root = Path(temp_text)
        configure_fixture_module(module, temp_root)

        for args in [["status"], ["json"]]:
            code, payload = capture_main(module, args)
            require(code == 0, "command failed: " + " ".join(args))
            require(isinstance(payload, dict), "command did not return object: " + " ".join(args))

        code, review = capture_main(module, ["review-latest"])
        require(code == 0, "review-latest failed")
        for key, expected in {
            "output_marked_untrusted": True,
            "model_output_trusted": False,
            "session_transcript_trusted": False,
            "review_output_trusted": False,
            "trusted_memory_write_enabled": False,
            "approved_memory_write_enabled": False,
            "automatic_learning_enabled": False,
            "source_route_queue_mutation": False,
            "provider_api_enabled": False,
            "runtime_process_started": False,
            "model_process_started": False,
            "server_enabled": False,
            "persistent_chat_loop_enabled": False,
            "runtime_ready_for_inference": False,
            "open_chat_enabled": False,
            "eligible_for_memory_candidate_draft": True,
        }.items():
            require(review.get(key) == expected, "review field mismatch: " + key)
        require(review.get("receipt_path"), "review did not write receipt")

        code, blocked = capture_main(module, ["draft-memory-candidate"])
        require(code == 2, "candidate draft without approval must refuse")
        require(blocked.get("approval_token_verified") is False, "missing token not refused")
        code, blocked_wrong = capture_main(module, ["draft-memory-candidate", "--approval", "WRONG"])
        require(code == 2, "candidate draft wrong approval must refuse")
        require(blocked_wrong.get("approval_token_verified") is False, "wrong token not refused")

        code, candidate = capture_main(module, ["draft-memory-candidate", "--approval", module.APPROVAL_TOKEN])
        require(code == 0, "approved candidate draft failed")
        for key, expected in {
            "approval_token_verified": True,
            "candidate_type": "local_chat_session_review_candidate",
            "trust_state": "untrusted",
            "human_review_required": True,
            "promoted_to_trusted_memory": False,
            "trusted_memory_write_enabled": False,
            "approved_memory_write_enabled": False,
            "model_output_trusted": False,
            "automatic_learning_enabled": False,
            "source_route_queue_mutation": False,
            "provider_api_enabled": False,
            "runtime_ready_for_inference": False,
            "open_chat_enabled": False,
        }.items():
            require(candidate.get(key) == expected, "candidate field mismatch: " + key)
        require(candidate.get("candidate_json_path"), "candidate JSON path missing")
        require(candidate.get("candidate_markdown_path"), "candidate markdown path missing")


def check_gui_docs_readiness() -> None:
    gui = read(GUI_HOST)
    for needle in [
        "import engel_ai_local_chat_session_review as local_ai_session_review",
        "Engel Local AI — Session Review",
        "LocalAISessionReviewPreview",
        "LocalAIUntrustedMemoryCandidatePreview",
        "Review Latest Session Draft",
        "Draft Memory Candidate From Review",
        "Open Latest Review",
        "Open Latest Candidate Draft",
        "create_review_latest()",
        "draft_memory_candidate(approval)",
        "local_ai_session_review_approval_input.clear()",
        "UNTRUSTED MEMORY-CANDIDATE DRAFT",
        "Automatic learning: disabled",
        "Approved memory writes: disabled",
    ]:
        require(needle in gui, "GUI missing session review text: " + needle)
    helper_start = gui.index("# ENGEL_AI_READ_ONLY_LOCAL_CHAT_PANEL_INTEGRATION_V1_START")
    helper_end = gui.index("# ENGEL_AI_READ_ONLY_LOCAL_CHAT_PANEL_INTEGRATION_V1_END")
    panel_start = gui.index("# ENGEL_AI_READ_ONLY_LOCAL_CHAT_PANEL_INTEGRATION_V1_PANEL_START")
    panel_end = gui.index("# ENGEL_AI_READ_ONLY_LOCAL_CHAT_PANEL_INTEGRATION_V1_PANEL_END")
    supervised_start = gui.find("Engel Local AI — Supervised Open Chat", panel_start, panel_end)
    panel_slice_end = supervised_start if supervised_start != -1 else panel_end
    combined = gui[helper_start:helper_end] + gui[panel_start:panel_slice_end]
    require("APPROVE_SESSION_REVIEW_MEMORY_CANDIDATE_DRAFT" not in combined, "GUI must not store raw review approval token")
    for forbidden in ["shell=True", "llama-server.exe", "rpc-server.exe", "trusted_memory_write_enabled\": True", "approved_memory_write_enabled\": True", "runtime_ready_for_inference\": True", "open_chat_enabled\": True"]:
        require(forbidden.lower() not in combined.lower(), "GUI session review section contains forbidden text: " + forbidden)

    commands = read(COMMANDS)
    for needle in [
        "ai local chat session review status",
        "ai local chat session review review-latest",
        "ai local chat session review draft-memory-candidate",
        "companion local ai session review panel",
    ]:
        require(needle in commands, "command docs missing: " + needle)

    readiness = read(READINESS)
    for needle in [
        "LOCAL_CHAT_SESSION_REVIEW_RECEIPTS",
        "LOCAL_CHAT_SESSION_REVIEW_CANDIDATES",
        "local_chat_session_review_entries",
        "latest_local_chat_session_review",
        "local_chat_session_memory_candidate_draft_entries",
        "local_chat_session_review_passed",
        "local_chat_session_memory_candidate_draft_available",
        "ENGEL_AI_LOCAL_CHAT_SESSION_MEMORY_CANDIDATE_REVIEW_V1",
    ]:
        require(needle in readiness, "readiness missing: " + needle)

    codex = read(CODEX_VERIFY)
    require("tools\\verify_engel_ai_local_chat_session_review.py" in codex, "codex verify missing session review verifier")

    report = read(REPORT)
    for needle in [
        "ENGEL_AI_LOCAL_CHAT_PANEL_SESSION_REVIEW_V1",
        "Engel Local AI — Session Review",
        "Approval token stored: `False`",
        "runtime_process_started: `False`",
        "trusted_memory_write_enabled: `False`",
        "approved_memory_write_enabled: `False`",
        "automatic_learning_enabled: `False`",
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
        check_cli_and_fixture_review()
        check_gui_docs_readiness()
        check_chain_verifiers()
    except CheckFailure as exc:
        print("ENGEL_AI_LOCAL_CHAT_SESSION_REVIEW_VERIFY_FAIL")
        print(str(exc))
        return 1
    print("ENGEL_AI_LOCAL_CHAT_SESSION_REVIEW_VERIFY_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
