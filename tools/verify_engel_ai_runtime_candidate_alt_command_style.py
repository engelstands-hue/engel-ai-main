from __future__ import annotations

import ast
from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "engel_ai_runtime_candidate_alt_command_style.py"
VERIFIER = ROOT / "tools" / "verify_engel_ai_runtime_candidate_alt_command_style.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_AI_RUNTIME_CANDIDATE_ALT_COMMAND_STYLE_V1.md"
REPORT_ROOT = ROOT / "reports" / "ai_runtime_candidate_alt_command_style"
DIAGNOSTICS = REPORT_ROOT / "diagnostics"
LOGS = REPORT_ROOT / "logs"
RECEIPTS = REPORT_ROOT / "receipts"
PLAN_REPORTS = REPORT_ROOT / "reports"
EXAMPLES = REPORT_ROOT / "examples"
COMMANDS = ROOT / "memory" / "ENGEL_COMMANDS.md"
CODEX_VERIFY = ROOT / "scripts" / "codex_verify.ps1"
READINESS = ROOT / "engel_ai_runtime_readiness.py"
REPLAY_VERIFIER = ROOT / "tools" / "verify_engel_ai_runtime_candidate_validation_replay.py"
FAILURE_DIAGNOSIS_VERIFIER = ROOT / "tools" / "verify_engel_ai_runtime_candidate_failure_diagnosis.py"
CANDIDATE_VALIDATION_VERIFIER = ROOT / "tools" / "verify_engel_ai_llama_cpp_runtime_candidate_validation.py"
SWAP_PLAN_VERIFIER = ROOT / "tools" / "verify_engel_ai_llama_cpp_runtime_swap_plan.py"
COMPATIBILITY_VERIFIER = ROOT / "tools" / "verify_engel_ai_llama_cpp_compatibility_matrix.py"
NO_GENERATION_VERIFIER = ROOT / "tools" / "verify_engel_ai_no_generation_load_check.py"
READINESS_VERIFIER = ROOT / "tools" / "verify_engel_ai_runtime_readiness.py"
MEMORY_ROOTS_VERIFIER = ROOT / "tools" / "verify_engel_memory_roots_storage_layout.py"

REQUIRED_COMMANDS = [
    "ai runtime candidate alt command style status",
    "ai runtime candidate alt command style inspect-help",
    "ai runtime candidate alt command style matrix",
    "ai runtime candidate alt command style preview",
    "ai runtime candidate alt command style validate-alt",
    "ai runtime candidate alt command style json",
]

FORBIDDEN_IMPORTS = {
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
    "rglob",
    "walk",
    "unlink",
    "rename",
}

CHAIN_VERIFIERS = [
    REPLAY_VERIFIER,
    FAILURE_DIAGNOSIS_VERIFIER,
    CANDIDATE_VALIDATION_VERIFIER,
    SWAP_PLAN_VERIFIER,
    COMPATIBILITY_VERIFIER,
    NO_GENERATION_VERIFIER,
    READINESS_VERIFIER,
    MEMORY_ROOTS_VERIFIER,
]


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
        LOGS,
        RECEIPTS,
        PLAN_REPORTS,
        EXAMPLES,
        COMMANDS,
        CODEX_VERIFY,
        READINESS,
        *CHAIN_VERIFIERS,
    ]:
        require(path.exists(), "missing required path: " + str(path.relative_to(ROOT)))


def check_static_safety() -> None:
    source = read(MODULE)
    tree = ast.parse(source)
    for needle in [
        "APPROVE_RUNTIME_CANDIDATE_ALT_STYLE_VALIDATION",
        "llama-b9198-bin-win-cpu-x64",
        "llama-tokenize.exe",
        "llama-cli.exe",
        "llama-server.exe",
        "rpc-server.exe",
        "FORBIDDEN_EXECUTABLES",
        "stdin=subprocess.DEVNULL",
        "shell=False",
        "TimeoutExpired",
        "output_marker_analysis",
        "tokenization_output_classified_non_generation",
        "disqualifying_interactive_markers_found",
        "disqualifying_generation_markers_found",
        "generated_text_detected",
        "registered_runtime_changed",
        "runtime_ready_for_inference",
        "runtime_no_generation_check_ready",
        "RUNTIME CANDIDATE ALT COMMAND STYLE PASSED",
    ]:
        require(needle in source, "module missing required text: " + needle)
    for forbidden in [
        "shell=True",
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
            if name in {"Popen", "run"}:
                shell_keywords = [kw for kw in node.keywords if kw.arg == "shell"]
                require(shell_keywords, "subprocess call missing explicit shell keyword")
                require(isinstance(shell_keywords[0].value, ast.Constant) and shell_keywords[0].value.value is False, "subprocess call does not force shell=False")


def check_runtime_commands() -> None:
    module = load_module("engel_ai_runtime_candidate_alt_command_style_verify", MODULE)
    for command in ["status", "inspect-help", "matrix", "preview", "json"]:
        code, output = capture_main(module, [command])
        require(code == 0, "command failed: " + command)
        require(output.strip(), "empty output for command: " + command)
        json.loads(output)

    matrix = json.loads(capture_main(module, ["matrix"])[1])
    selected = matrix.get("selected_alternate_command_style")
    require(isinstance(selected, dict), "matrix did not select a command style")
    require(selected.get("style_id") == "llama_tokenize_ids_count", "tokenize style must be selected first")
    require(selected.get("non_chat") is True, "selected style must be non-chat")
    require(selected.get("non_server") is True, "selected style must be non-server")
    require(selected.get("generation_requested") is False, "selected style must not request generation")
    require(isinstance(selected.get("command_args"), list) and selected.get("command_args"), "selected command must use explicit args")
    server_rows = [row for row in matrix["matrix"] if row["executable_name"] in {"llama-server.exe", "rpc-server.exe"}]
    require(server_rows, "server inventory rows missing")
    for row in server_rows:
        require(row["executable_role"] == "forbidden_inventory_only", "server row must be inventory-only")
        require(row["selection_eligible"] is False, "server row must not be selectable")
        require(row["selected"] is False, "server row must not be selected")
        require(row["command_args"] == [], "server row must not expose runnable args")

    code, output = capture_main(module, ["validate-alt"])
    require(code != 0, "validate-alt without token must refuse")
    refused = json.loads(output)
    require(refused.get("approval_token_verified") is False, "missing token was accepted")
    require(refused.get("command_executed") is False, "missing token executed command")
    code, output = capture_main(module, ["validate-alt", "--approval", "WRONG"])
    require(code != 0, "validate-alt wrong token must refuse")
    refused = json.loads(output)
    require(refused.get("approval_token_verified") is False, "wrong token was accepted")
    require(refused.get("command_executed") is False, "wrong token executed command")


def check_marker_fixtures() -> None:
    module = load_module("engel_ai_runtime_candidate_alt_command_style_markers", MODULE)
    dirty_interactive = module.output_marker_analysis("available commands:\n> load check\nCtrl+C\n", "", "llama_cli_devnull_n0")
    require(dirty_interactive["disqualifying_interactive_markers_found"] is True, "interactive marker fixture not rejected")
    dirty_generation = module.output_marker_analysis("load check\nI am generated text\n[ Prompt: 1 t/s | Generation: 100 t/s ]\n", "", "llama_cli_devnull_n0")
    require(dirty_generation["disqualifying_generation_markers_found"] is True, "generation marker fixture not rejected")
    require(dirty_generation["generated_text_detected"] is True, "generated text fixture not detected")
    tokenize = module.output_marker_analysis("[1078, 1779]\nTotal number of tokens: 2\n", "", "llama_tokenize_ids_count")
    require(tokenize["disqualifying_interactive_markers_found"] is False, "tokenize fixture marked interactive")
    require(tokenize["disqualifying_generation_markers_found"] is False, "tokenize fixture marked generation")
    require(tokenize["generated_text_detected"] is False, "tokenize fixture marked generated")
    require(tokenize["tokenization_output_classified_non_generation"] is True, "tokenize fixture not classified as non-generation")


def check_fixture_validation_without_real_process() -> None:
    module = load_module("engel_ai_runtime_candidate_alt_command_style_fixture", MODULE)
    with tempfile.TemporaryDirectory(prefix="engel_alt_style_") as temp_text:
        temp = Path(temp_text)
        module.PROJECT_ROOT = temp
        module.REPORT_ROOT = temp / "reports" / "ai_runtime_candidate_alt_command_style"
        module.DIAGNOSTIC_DIR = module.REPORT_ROOT / "diagnostics"
        module.LOG_DIR = module.REPORT_ROOT / "logs"
        module.RECEIPT_DIR = module.REPORT_ROOT / "receipts"
        module.PLAN_REPORT_DIR = module.REPORT_ROOT / "reports"
        module.EXAMPLE_DIR = module.REPORT_ROOT / "examples"
        module.CODEX_REPORT = temp / "reports" / "codex_bridge" / "ENGEL_AI_RUNTIME_CANDIDATE_ALT_COMMAND_STYLE_V1.md"
        module.APPROVED_CANDIDATE_ROOT = temp / "approved_candidates"
        module.CANDIDATE_FOLDER = module.APPROVED_CANDIDATE_ROOT / "llama-b9198-bin-win-cpu-x64"
        module.MODEL_FILE = temp / "models" / "tiny_seed.gguf"
        module.CANDIDATE_FOLDER.mkdir(parents=True)
        module.MODEL_FILE.parent.mkdir(parents=True)
        for name in ["llama-tokenize.exe", "llama-cli.exe", "llama-server.exe", "rpc-server.exe"]:
            (module.CANDIDATE_FOLDER / name).write_text("fixture placeholder", encoding="utf-8")
        module.MODEL_FILE.write_text("fixture model", encoding="utf-8")

        fake_selected = {
            "style_id": "llama_tokenize_ids_count",
            "executable_name": "llama-tokenize.exe",
            "command_args": ["fixture-tokenize", "-m", "fixture-model", "-p", "load check", "--ids", "--show-count", "--log-disable"],
            "stdin_devnull": True,
            "non_chat": True,
            "non_server": True,
            "generation_requested": False,
            "selection_eligible": True,
            "executable_path": str(module.CANDIDATE_FOLDER / "llama-tokenize.exe"),
        }
        module.build_matrix = lambda write_diagnostics=True: {"selected_alternate_command_style": fake_selected, "matrix": [fake_selected]}
        module.list_runtime_processes = lambda: []

        def fake_run(_args, timeout_seconds, *, stdin_devnull=True):
            require(stdin_devnull is True, "fixture validation did not close stdin")
            return module.ExecutionResult(
                True,
                True,
                True,
                timeout_seconds,
                0,
                "[1078, 1779]\nTotal number of tokens: 2\n",
                "",
                False,
                False,
                False,
                False,
                False,
                runtime_process_id=123,
                cleanup_action="none",
            )

        module.run_bounded_process = fake_run
        receipt = module.validate_alt(module.APPROVAL_TOKEN)
        require(receipt["alt_command_style_validation_passed"] is True, "fixture tokenize validation did not pass")
        require(receipt["candidate_runtime_ready_for_swap_review"] is True, "fixture did not become swap-review ready")
        for key in ["registered_runtime_changed", "runtime_ready_for_inference", "runtime_no_generation_check_ready", "inference_enabled", "chat_enabled", "server_enabled", "trusted_memory_write_enabled"]:
            require(receipt[key] is False, "fixture safety field not false: " + key)


def check_latest_receipt_and_report() -> None:
    report = read(REPORT)
    for needle in [
        "ENGEL_AI_RUNTIME_CANDIDATE_ALT_COMMAND_STYLE_V1",
        "Chat remains a future Engel goal",
        "llama_tokenize_ids_count",
        "Packaging skipped",
        "This phase protects future chat",
    ]:
        require(needle in report, "report missing required text: " + needle)
    receipts = sorted(RECEIPTS.glob("RUNTIME_CANDIDATE_ALT_COMMAND_STYLE_*.json"))
    require(receipts, "missing alt command-style validation receipt")
    latest_text = read(receipts[-1])
    latest = json.loads(latest_text)
    require("APPROVE_RUNTIME_CANDIDATE_ALT_STYLE_VALIDATION" not in latest_text, "receipt must not store raw approval token")
    require(latest.get("selected_command_style") == "llama_tokenize_ids_count", "latest receipt selected wrong style")
    require(latest.get("alt_command_style_validation_passed") is True, "latest alt validation should pass")
    require(latest.get("candidate_runtime_ready_for_swap_review") is True, "latest candidate should be ready for swap review")
    require(latest.get("runtime_ready_for_inference") is False, "latest receipt must not enable inference readiness")
    require(latest.get("runtime_no_generation_check_ready") is False, "latest receipt must not mark registered runtime ready")
    require(latest.get("registered_runtime_changed") is False, "registered runtime changed")
    require(latest.get("disqualifying_interactive_markers_found") is False, "interactive markers found")
    require(latest.get("disqualifying_generation_markers_found") is False, "generation markers found")
    require(latest.get("generated_text_detected") is False, "generated text detected")


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
    require("tools\\verify_engel_ai_runtime_candidate_alt_command_style.py" in codex, "codex verify missing alt command-style verifier")
    readiness = read(READINESS)
    for needle in [
        "RUNTIME_CANDIDATE_ALT_COMMAND_STYLE_RECEIPTS",
        "latest_runtime_candidate_alt_command_style",
        "ENGEL_AI_RUNTIME_CANDIDATE_ALT_COMMAND_STYLE_V1",
        "alt_command_style_validation_passed",
    ]:
        require(needle in readiness, "readiness missing alt command-style integration: " + needle)


def main() -> int:
    try:
        check_files()
        check_static_safety()
        check_runtime_commands()
        check_marker_fixtures()
        check_fixture_validation_without_real_process()
        check_latest_receipt_and_report()
        check_docs_registration_and_readiness()
        check_downstream_verifiers()
    except CheckFailure as exc:
        print("ENGEL_AI_RUNTIME_CANDIDATE_ALT_COMMAND_STYLE_VERIFY_FAIL")
        print(str(exc))
        return 1
    print("ENGEL_AI_RUNTIME_CANDIDATE_ALT_COMMAND_STYLE_VERIFY_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
