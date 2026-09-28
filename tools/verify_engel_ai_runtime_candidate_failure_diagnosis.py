from __future__ import annotations

from contextlib import redirect_stdout
import ast
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "engel_ai_runtime_candidate_failure_diagnosis.py"
VERIFIER = ROOT / "tools" / "verify_engel_ai_runtime_candidate_failure_diagnosis.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_AI_RUNTIME_CANDIDATE_FAILURE_DIAGNOSIS_V1.md"
REPORT_ROOT = ROOT / "reports" / "ai_runtime_candidate_failure_diagnosis"
DIAGNOSTICS = REPORT_ROOT / "diagnostics"
RECEIPTS = REPORT_ROOT / "receipts"
PLAN_REPORTS = REPORT_ROOT / "reports"
EXAMPLES = REPORT_ROOT / "examples"
COMMANDS = ROOT / "memory" / "ENGEL_COMMANDS.md"
CODEX_VERIFY = ROOT / "scripts" / "codex_verify.ps1"
READINESS = ROOT / "engel_ai_runtime_readiness.py"
CANDIDATE_VALIDATION_VERIFIER = ROOT / "tools" / "verify_engel_ai_llama_cpp_runtime_candidate_validation.py"
SWAP_PLAN_VERIFIER = ROOT / "tools" / "verify_engel_ai_llama_cpp_runtime_swap_plan.py"
COMPATIBILITY_VERIFIER = ROOT / "tools" / "verify_engel_ai_llama_cpp_compatibility_matrix.py"
NO_GENERATION_VERIFIER = ROOT / "tools" / "verify_engel_ai_no_generation_load_check.py"
READINESS_VERIFIER = ROOT / "tools" / "verify_engel_ai_runtime_readiness.py"

REQUIRED_COMMANDS = [
    "ai runtime candidate failure diagnosis status",
    "ai runtime candidate failure diagnosis diagnose-latest",
    "ai runtime candidate failure diagnosis diagnose-receipt",
    "ai runtime candidate failure diagnosis reclassify-receipt-preview",
    "ai runtime candidate failure diagnosis json",
]

FORBIDDEN_IMPORTS = {
    "subprocess",
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
    "run",
    "call",
    "check_call",
    "check_output",
    "Popen",
    "rglob",
    "walk",
    "unlink",
    "rename",
}


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
        RECEIPTS,
        PLAN_REPORTS,
        EXAMPLES,
        COMMANDS,
        CODEX_VERIFY,
        READINESS,
        CANDIDATE_VALIDATION_VERIFIER,
        SWAP_PLAN_VERIFIER,
        COMPATIBILITY_VERIFIER,
        NO_GENERATION_VERIFIER,
        READINESS_VERIFIER,
    ]:
        require(path.exists(), "missing required path: " + str(path.relative_to(ROOT)))


def check_static_safety() -> None:
    source = read(MODULE)
    tree = ast.parse(source)
    for needle in [
        "status",
        "diagnose-latest",
        "diagnose-receipt",
        "reclassify-receipt-preview",
        "contradictory_receipt_state",
        "possible_clean_no_generation_exit_needs_replay",
        "historical_receipt_modified",
        "registered_runtime_changed",
        "runtime_ready_for_inference",
        "inference_enabled",
        "chat_enabled",
        "server_enabled",
        "trusted_memory_write_enabled",
        "provider_api_enabled",
        "source_route_queue_mutation",
        "HISTORICAL RECEIPT UNCHANGED",
        "runtime_output_flags",
    ]:
        require(needle in source, "module missing required diagnosis text: " + needle)
    for forbidden in [
        "subprocess",
        "shell=True",
        "Popen",
        "ollama",
        "requests.",
        "socket.",
        "webbrowser.",
        "openai.",
        "anthropic.",
        "pip install",
        "Invoke-WebRequest",
        "curl ",
        "wsl.exe",
        "docker.",
        ".rglob(",
        "os.walk(",
        ".rename(",
        ".unlink(",
        "runtime_ready_for_inference\": True",
        "inference_enabled\": True",
        "chat_enabled\": True",
        "server_enabled\": True",
        "trusted_memory_write_enabled\": True",
        "registered_runtime_changed\": True",
    ]:
        require(forbidden.lower() not in source.lower(), "module contains forbidden behavior text: " + forbidden)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                require(alias.name.split(".")[0] not in FORBIDDEN_IMPORTS, "forbidden import: " + alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            require(node.module.split(".")[0] not in FORBIDDEN_IMPORTS, "forbidden import: " + node.module)
        elif isinstance(node, ast.Call):
            func = node.func
            name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ""
            require(name not in FORBIDDEN_CALLS, "module contains forbidden call: " + name)


def configure_fixture_module(module, temp: Path) -> Path:
    module.PROJECT_ROOT = temp
    report_root = temp / "reports" / "ai_runtime_candidate_failure_diagnosis"
    module.REPORT_ROOT = report_root
    module.DIAGNOSTIC_DIR = report_root / "diagnostics"
    module.RECEIPT_DIR = report_root / "receipts"
    module.PLAN_REPORT_DIR = report_root / "reports"
    module.EXAMPLE_DIR = report_root / "examples"
    module.CODEX_REPORT = temp / "reports" / "codex_bridge" / "ENGEL_AI_RUNTIME_CANDIDATE_FAILURE_DIAGNOSIS_V1.md"
    validation_root = temp / "reports" / "ai_llama_cpp_runtime_candidate_validation"
    receipt_dir = validation_root / "receipts"
    log_dir = validation_root / "logs"
    receipt_dir.mkdir(parents=True)
    log_dir.mkdir(parents=True)
    module.CANDIDATE_VALIDATION_RECEIPTS = receipt_dir
    stdout = log_dir / "fixture_stdout.txt"
    stderr = log_dir / "fixture_stderr.txt"
    stdout.write_text(
        "Loading model...\navailable commands:\n  /exit or Ctrl+C stop or exit\n> load check\nI\n[ Prompt: 1 t/s | Generation: 1000000.0 t/s ]\nExiting...\n",
        encoding="utf-8",
    )
    stderr.write_text("", encoding="utf-8")
    receipt = {
        "runtime_candidate_validation_version": "1",
        "created_at": "2026-05-17T22:45:26Z",
        "candidate_folder": "F:\\ENGEL_APP_MEMORY\\runtimes\\llama.cpp\\candidates\\fixture",
        "selected_command_style": "llama_cli_prompt_no_generation_offline",
        "exit_code": 0,
        "runtime_process_started": True,
        "runtime_process_exited": True,
        "timed_out": False,
        "interrupted": True,
        "orphan_process_detected": False,
        "candidate_validation_passed": False,
        "command_executed": True,
        "stdout_log_path": module.project_relative(stdout),
        "stderr_log_path": module.project_relative(stderr),
        "registered_runtime_changed": False,
        "runtime_ready_for_inference": False,
    }
    receipt_path = receipt_dir / "RUNTIME_CANDIDATE_VALIDATION_fixture.json"
    receipt_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    return receipt_path


def check_commands() -> None:
    module = load_module("engel_ai_runtime_candidate_failure_diagnosis_fixture", MODULE)
    with tempfile.TemporaryDirectory() as raw:
        temp = Path(raw)
        receipt_path = configure_fixture_module(module, temp)
        before = receipt_path.read_bytes()
        for args in [["status"], ["json"]]:
            code, output = capture_main(module, args)
            require(code == 0, "command failed: " + " ".join(args))
            require(json.loads(output), "command produced empty JSON")

        code, output = capture_main(module, ["reclassify-receipt-preview", module.project_relative(receipt_path)])
        require(code == 0, "preview command failed")
        preview = json.loads(output)
        require(preview.get("preview_only") is True, "preview did not mark preview_only")
        require(preview.get("diagnosis_classification") == "contradictory_receipt_state", "preview did not classify contradiction")
        require(preview.get("historical_receipt_modified") is False, "preview claims historical mutation")
        require(receipt_path.read_bytes() == before, "preview modified historical receipt")

        code, output = capture_main(module, ["diagnose-receipt", module.project_relative(receipt_path)])
        require(code == 0, "diagnose-receipt failed")
        diagnosis = json.loads(output)
        require(diagnosis.get("diagnosis_classification") == "contradictory_receipt_state", "diagnose-receipt did not classify contradiction")
        for key in [
            "inference_enabled",
            "chat_enabled",
            "server_enabled",
            "trusted_memory_write_enabled",
            "runtime_ready_for_inference",
            "registered_runtime_changed",
            "historical_receipt_modified",
        ]:
            require(diagnosis.get(key) is False, "diagnosis safety field must be false: " + key)
        require(receipt_path.read_bytes() == before, "diagnose-receipt modified historical receipt")

        code, output = capture_main(module, ["diagnose-latest"])
        require(code == 0, "diagnose-latest failed")
        latest = json.loads(output)
        require(latest.get("diagnosis_classification") == "contradictory_receipt_state", "diagnose-latest did not classify contradiction")
        require(list(module.RECEIPT_DIR.glob("RUNTIME_CANDIDATE_FAILURE_DIAGNOSIS_*.json")), "diagnosis receipt not written")


def check_docs_and_registration() -> None:
    report = read(REPORT)
    for needle in [
        "ENGEL_AI_RUNTIME_CANDIDATE_FAILURE_DIAGNOSIS_V1",
        "Contradiction observed",
        "Historical receipt modified: false",
        "This phase diagnoses candidate validation evidence only.",
    ]:
        require(needle in report, "report missing: " + needle)
    commands = read(COMMANDS)
    for command in REQUIRED_COMMANDS:
        require(command in commands, "ENGEL_COMMANDS missing command: " + command)
    codex_verify = read(CODEX_VERIFY)
    require("tools\\verify_engel_ai_runtime_candidate_failure_diagnosis.py" in codex_verify, "codex verify missing failure diagnosis verifier")
    readiness = read(READINESS)
    for needle in [
        "RUNTIME_CANDIDATE_FAILURE_DIAGNOSIS_RECEIPTS",
        "latest_runtime_candidate_failure_diagnosis",
        "ENGEL_AI_RUNTIME_CANDIDATE_VALIDATION_REPLAY_V1",
    ]:
        require(needle in readiness, "readiness missing failure diagnosis integration: " + needle)
    candidate_validation = read(ROOT / "engel_ai_llama_cpp_runtime_candidate_validation.py")
    for needle in ["post_process_interruption", "runtime_output_contract_flags", "output_contract_ok"]:
        require(needle in candidate_validation, "candidate validator missing interpretation fix: " + needle)


def main() -> int:
    try:
        check_files()
        check_static_safety()
        check_commands()
        check_docs_and_registration()
    except CheckFailure as exc:
        print("ENGEL_AI_RUNTIME_CANDIDATE_FAILURE_DIAGNOSIS_VERIFY_FAIL")
        print(str(exc))
        return 1
    print("ENGEL_AI_RUNTIME_CANDIDATE_FAILURE_DIAGNOSIS_VERIFY_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
