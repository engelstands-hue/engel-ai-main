from __future__ import annotations

import ast
from contextlib import redirect_stdout
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "engel_ai_first_response_output_filter_tuning.py"
VERIFIER = ROOT / "tools" / "verify_engel_ai_first_response_output_filter_tuning.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_AI_FIRST_RESPONSE_OUTPUT_FILTER_TUNING_V1.md"
REPORT_ROOT = ROOT / "reports" / "ai_first_response_output_filter_tuning"
DIAGNOSTICS = REPORT_ROOT / "diagnostics"
RECEIPTS = REPORT_ROOT / "receipts"
PLAN_REPORTS = REPORT_ROOT / "reports"
EXAMPLES = REPORT_ROOT / "examples"
COMMANDS = ROOT / "memory" / "ENGEL_COMMANDS.md"
CODEX_VERIFY = ROOT / "scripts" / "codex_verify.ps1"
READINESS = ROOT / "engel_ai_runtime_readiness.py"
EXIT_FIX_RECEIPTS = ROOT / "reports" / "ai_first_local_response_smoke_exit_fix" / "receipts"

EXIT_FIX_VERIFIER = ROOT / "tools" / "verify_engel_ai_first_local_response_smoke_exit_fix.py"
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
    "ai first response output filter tuning status",
    "ai first response output filter tuning diagnose-latest",
    "ai first response output filter tuning reclassify-latest-preview",
    "ai first response output filter tuning json",
]

FORBIDDEN_IMPORTS = {
    "requests",
    "urllib",
    "socket",
    "webbrowser",
    "subprocess",
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
    "Popen",
    "run",
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
    EXIT_FIX_VERIFIER,
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


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
        RECEIPTS,
        PLAN_REPORTS,
        EXAMPLES,
        COMMANDS,
        CODEX_VERIFY,
        READINESS,
        EXIT_FIX_RECEIPTS,
        *CHAIN_VERIFIERS,
    ]:
        require(path.exists(), "missing required path: " + str(path.relative_to(ROOT)))


def check_static_safety() -> None:
    source = read(MODULE)
    tree = ast.parse(source)
    for needle in [
        "clean_single_turn_exit_but_filter_too_strict",
        "unsafe_prompt_loop_confirmed",
        "unsafe_interactive_wait_confirmed",
        "server_or_persistent_mode_detected",
        "ambiguous_needs_replay",
        "real_failure",
        "fatal_interactive_wait",
        "fatal_prompt_loop",
        "fatal_server_startup",
        "fatal_persistent_chat",
        "suspicious_command_menu_banner",
        "suspicious_prompt_marker",
        "benign_llama_banner",
        "benign_help_scaffolding",
        "benign_prompt_echo",
        "benign_generation_stats_after_exit",
        "clean_expected_token",
        "marker_classes",
        "fatal_markers_fail_always",
        "suspicious_markers_require_context",
        "benign_markers_do_not_fail_alone",
        "historical_receipt_modified",
        "model_output_trusted",
        "runtime_ready_for_inference",
        "FIRST RESPONSE OUTPUT FILTER TUNING PASSED",
    ]:
        require(needle in source, "module missing required text: " + needle)
    for forbidden in [
        "subprocess",
        "shell=True",
        "Popen",
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
    ]:
        require(forbidden.lower() not in source.lower(), "module contains forbidden behavior text: " + forbidden)
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


def baseline_receipt(**overrides) -> dict[str, object]:
    data: dict[str, object] = {
        "exit_code": 0,
        "timed_out": False,
        "interrupted": False,
        "orphan_process_detected": False,
        "runtime_process_exited": True,
        "expected_token_seen": True,
        "output_marked_untrusted": True,
        "output_captured": True,
        "server_enabled": False,
        "persistent_chat_loop_enabled": False,
        "trusted_memory_write_enabled": False,
    }
    data.update(overrides)
    return data


def classify(module, text: str, **receipt_overrides) -> dict[str, object]:
    return module.classify_evidence(baseline_receipt(**receipt_overrides), text, "")


def check_classifier_fixtures() -> None:
    module = load_module("engel_ai_first_response_output_filter_tuning_fixtures", MODULE)
    clean_menu = """Loading model...
build      : b9198-a6d6183db
modalities : text
available commands:
  /exit or Ctrl+C     stop or exit
  /regen              regenerate the last response
  /clear              clear the chat history

> Reply with exactly: Engel

Engel

[ Prompt: 120.9 t/s | Generation: 79.3 t/s ]

Exiting...
"""
    result = classify(module, clean_menu)
    require(result["diagnosis_classification"] == "clean_single_turn_exit_but_filter_too_strict", "clean single-turn fixture was not reclassified")
    require(result["first_response_smoke_passed_after_tuning_preview"] is True, "clean fixture did not pass preview")
    require(not result["marker_classes"]["fatal"], "clean fixture has fatal markers")
    require(result["marker_classes"]["suspicious"], "clean fixture should keep suspicious menu markers")
    require(result["marker_classes"]["benign"], "clean fixture should contain benign markers")

    server = classify(module, "Engel\nserver listening on port 8080\n")
    require(server["diagnosis_classification"] == "server_or_persistent_mode_detected", "server startup fixture did not fail")
    require("fatal_server_startup" in server["fatal_marker_types"], "server fatal marker missing")

    waiting = classify(module, "Engel\nwaiting for input\n")
    require(waiting["diagnosis_classification"] == "unsafe_interactive_wait_confirmed", "waiting-for-input fixture did not fail")
    require("fatal_interactive_wait" in waiting["fatal_marker_types"], "waiting fatal marker missing")

    prompt_loop = classify(module, "Engel\n>\n>\n")
    require(prompt_loop["diagnosis_classification"] == "unsafe_prompt_loop_confirmed", "prompt-loop fixture did not fail")
    require("fatal_prompt_loop" in prompt_loop["fatal_marker_types"], "prompt-loop fatal marker missing")

    nonzero = classify(module, "Engel\n", exit_code=1)
    require(nonzero["diagnosis_classification"] == "real_failure", "nonzero exit fixture did not fail")

    orphan = classify(module, "Engel\n", orphan_process_detected=True)
    require(orphan["diagnosis_classification"] == "real_failure", "orphan fixture did not fail")

    no_token = classify(module, "no expected token\n", expected_token_seen=False)
    require(no_token["diagnosis_classification"] == "ambiguous_needs_replay", "missing token fixture should need replay")

    for result in [clean_menu and classify(module, clean_menu), server, waiting, prompt_loop, nonzero, orphan]:
        require(result["model_output_trusted"] is False, "fixture trusted model output")
        require(result["runtime_ready_for_inference"] is False, "fixture enabled runtime readiness")
        require(result["chat_enabled"] is False, "fixture enabled chat")
        require(result["server_enabled"] is False, "fixture enabled server")
        require(result["trusted_memory_write_enabled"] is False, "fixture enabled trusted memory")


def check_runtime_commands_and_history() -> None:
    module = load_module("engel_ai_first_response_output_filter_tuning_commands", MODULE)
    source_receipts = sorted(EXIT_FIX_RECEIPTS.glob("FIRST_LOCAL_RESPONSE_SMOKE_EXIT_FIX_*.json"))
    require(source_receipts, "missing source exit-fix receipt")
    latest_source = source_receipts[-1]
    before_hash = sha256(latest_source)
    for command in ["status", "diagnose-latest", "json"]:
        code, output = capture_main(module, [command])
        require(code == 0, "command failed: " + command)
        require(output.strip(), "empty output for command: " + command)
        parsed = json.loads(output)
        if command == "diagnose-latest":
            require(parsed["source_exit_fix_receipt"], "diagnosis missing source receipt")
            require(parsed["historical_receipt_modified"] is False, "diagnosis modified historical receipt")
            require(parsed["diagnosis_classification"] == "clean_single_turn_exit_but_filter_too_strict", "historical evidence classification mismatch")
            require(parsed["first_response_smoke_passed_after_tuning_preview"] is True, "historical evidence should pass preview")
            require(parsed["marker_classes"]["fatal"] == [], "historical evidence should not have fatal markers")
    require(sha256(latest_source) == before_hash, "read-only commands modified historical exit-fix receipt")


def check_fixture_reclassify_command() -> None:
    module = load_module("engel_ai_first_response_output_filter_tuning_reclassify", MODULE)
    with tempfile.TemporaryDirectory(prefix="engel_output_filter_tuning_") as temp_text:
        temp = Path(temp_text)
        module.PROJECT_ROOT = temp
        module.EXIT_FIX_RECEIPT_DIR = temp / "reports" / "ai_first_local_response_smoke_exit_fix" / "receipts"
        module.REPORT_ROOT = temp / "reports" / "ai_first_response_output_filter_tuning"
        module.DIAGNOSTIC_DIR = module.REPORT_ROOT / "diagnostics"
        module.RECEIPT_DIR = module.REPORT_ROOT / "receipts"
        module.PLAN_REPORT_DIR = module.REPORT_ROOT / "reports"
        module.EXAMPLE_DIR = module.REPORT_ROOT / "examples"
        module.CODEX_REPORT = temp / "reports" / "codex_bridge" / "ENGEL_AI_FIRST_RESPONSE_OUTPUT_FILTER_TUNING_V1.md"
        module.EXIT_FIX_RECEIPT_DIR.mkdir(parents=True)
        log_dir = temp / "reports" / "ai_first_local_response_smoke_exit_fix" / "logs"
        log_dir.mkdir(parents=True)
        stdout_path = log_dir / "fixture_stdout.txt"
        stderr_path = log_dir / "fixture_stderr.txt"
        stdout_path.write_text("available commands:\n  /exit or Ctrl+C\n> Reply with exactly: Engel\nEngel\n[ Prompt: 1 t/s | Generation: 1 t/s ]\nExiting...\n", encoding="utf-8")
        stderr_path.write_text("", encoding="utf-8")
        source_receipt = module.EXIT_FIX_RECEIPT_DIR / "FIRST_LOCAL_RESPONSE_SMOKE_EXIT_FIX_20260518T043342Z_tiny_seed.json"
        source_receipt.write_text(
            json.dumps(
                {
                    "first_local_response_smoke_exit_fix_version": "1",
                    "exit_code": 0,
                    "timed_out": False,
                    "interrupted": False,
                    "orphan_process_detected": False,
                    "runtime_process_exited": True,
                    "expected_token_seen": True,
                    "output_marked_untrusted": True,
                    "output_captured": True,
                    "server_enabled": False,
                    "persistent_chat_loop_enabled": False,
                    "trusted_memory_write_enabled": False,
                    "stdout_log_path": str(stdout_path.relative_to(temp)),
                    "stderr_log_path": str(stderr_path.relative_to(temp)),
                    "selected_command_style": "simple_io_no_display",
                    "command_args": ["fixture", "--single-turn"],
                    "final_decision": "fixture",
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        before_hash = sha256(source_receipt)
        code, output = capture_main(module, ["reclassify-latest-preview"])
        require(code == 0, "fixture reclassify command failed")
        parsed = json.loads(output)
        require(parsed["diagnosis_classification"] == "clean_single_turn_exit_but_filter_too_strict", "fixture reclassify classification mismatch")
        require(parsed["historical_receipt_modified"] is False, "fixture reclassify modified history flag")
        require(parsed["receipt_path"], "fixture reclassify did not write tuning receipt")
        require((temp / parsed["receipt_path"]).exists(), "fixture tuning receipt missing")
        require((temp / parsed["report_path"]).exists(), "fixture tuning report missing")
        require(sha256(source_receipt) == before_hash, "fixture reclassify modified source receipt")


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
    require("tools\\verify_engel_ai_first_response_output_filter_tuning.py" in codex, "codex verify missing output filter tuning verifier")
    readiness = read(READINESS)
    for needle in [
        "FIRST_RESPONSE_OUTPUT_FILTER_TUNING_RECEIPTS",
        "latest_first_response_output_filter_tuning",
        "first_response_output_filter_tuning_passed",
        "ENGEL_AI_FIRST_RESPONSE_OUTPUT_FILTER_TUNING_V1",
        "ENGEL_AI_BOUNDED_LOCAL_CHAT_SMOKE_V1",
    ]:
        require(needle in readiness, "readiness missing output filter tuning integration: " + needle)
    report = read(REPORT)
    for needle in [
        "ENGEL_AI_FIRST_RESPONSE_OUTPUT_FILTER_TUNING_V1",
        "Source Exit-Fix Receipt",
        "Marker Classification Table",
        "Fatal markers found",
        "Suspicious markers found",
        "Benign markers found",
        "Diagnosis classification",
        "Historical receipt unchanged",
        "Full Codex verifier result",
        "Packaging skipped",
        "This phase tunes output classification only.",
    ]:
        require(needle in report, "report missing required text: " + needle)


def main() -> int:
    try:
        module = load_module("engel_ai_first_response_output_filter_tuning_bootstrap", MODULE)
        capture_main(module, ["status"])
        check_files()
        check_static_safety()
        check_classifier_fixtures()
        check_runtime_commands_and_history()
        check_fixture_reclassify_command()
        check_docs_registration_and_readiness()
        check_downstream_verifiers()
    except CheckFailure as exc:
        print("ENGEL_AI_FIRST_RESPONSE_OUTPUT_FILTER_TUNING_VERIFY_FAIL")
        print(str(exc))
        return 1
    print("ENGEL_AI_FIRST_RESPONSE_OUTPUT_FILTER_TUNING_VERIFY_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
