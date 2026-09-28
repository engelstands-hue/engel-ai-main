from __future__ import annotations

import ast
from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "engel_ai_llama_cpp_runtime_candidate_validation.py"
VERIFIER = ROOT / "tools" / "verify_engel_ai_llama_cpp_runtime_candidate_validation.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_AI_LLAMA_CPP_RUNTIME_CANDIDATE_VALIDATION_V1.md"
REPORT_ROOT = ROOT / "reports" / "ai_llama_cpp_runtime_candidate_validation"
DIAGNOSTICS = REPORT_ROOT / "diagnostics"
LOGS = REPORT_ROOT / "logs"
RECEIPTS = REPORT_ROOT / "receipts"
MANIFESTS = REPORT_ROOT / "manifests"
EXAMPLES = REPORT_ROOT / "examples"
COMMANDS = ROOT / "memory" / "ENGEL_COMMANDS.md"
CODEX_VERIFY = ROOT / "scripts" / "codex_verify.ps1"
READINESS = ROOT / "engel_ai_runtime_readiness.py"
SWAP_PLAN_VERIFIER = ROOT / "tools" / "verify_engel_ai_llama_cpp_runtime_swap_plan.py"
COMPATIBILITY_VERIFIER = ROOT / "tools" / "verify_engel_ai_llama_cpp_compatibility_matrix.py"
NO_GENERATION_VERIFIER = ROOT / "tools" / "verify_engel_ai_no_generation_load_check.py"
READINESS_VERIFIER = ROOT / "tools" / "verify_engel_ai_runtime_readiness.py"

REQUIRED_COMMANDS = [
    "ai llama.cpp runtime candidate validation status",
    "ai llama.cpp runtime candidate validation list-candidates",
    "ai llama.cpp runtime candidate validation inspect-candidate",
    "ai llama.cpp runtime candidate validation probe-safe",
    "ai llama.cpp runtime candidate validation preview-no-generation",
    "ai llama.cpp runtime candidate validation validate-no-generation",
    "ai llama.cpp runtime candidate validation json",
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
    "run",
    "call",
    "check_call",
    "check_output",
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
        LOGS,
        RECEIPTS,
        MANIFESTS,
        EXAMPLES,
        COMMANDS,
        CODEX_VERIFY,
        READINESS,
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
        "APPROVE_RUNTIME_CANDIDATE_NO_GENERATION_VALIDATION",
        "status",
        "list-candidates",
        "inspect-candidate",
        "probe-safe",
        "preview-no-generation",
        "validate-no-generation",
        "json",
        "subprocess.Popen",
        "shell=False",
        "timeout=timeout_seconds",
        "subprocess.TimeoutExpired",
        "KeyboardInterrupt",
        "stop_started_process",
        "terminate()",
        "kill()",
        "llama-server.exe",
        "inventory-only",
        "n_predict",
        "N_PREDICT",
        "load check",
        "llama_cli_prompt_no_generation_offline",
        "RUNTIME CANDIDATE VALIDATED FOR NO-GENERATION REVIEW",
        "RUNTIME CANDIDATE VALIDATION FAILED",
        "RUNTIME CANDIDATE VALIDATION BLOCKED",
        "registered_runtime_changed",
        "runtime_ready_for_inference",
        "inference_enabled",
        "chat_enabled",
        "server_enabled",
        "auto_load_enabled",
        "trusted_memory_write_enabled",
        "source_route_queue_mutation",
    ]:
        require(needle in source, "module missing required safety text: " + needle)
    for forbidden in [
        "shell=True",
        "subprocess.run",
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
        "write_trusted_memory",
        "registered_runtime_changed\": True",
        "runtime_ready_for_inference\": True",
        "inference_enabled\": True",
        "chat_enabled\": True",
        "server_enabled\": True",
        "auto_load_enabled\": True",
        "trusted_memory_write_enabled\": True",
    ]:
        require(forbidden.lower() not in source.lower(), "module contains forbidden behavior text: " + forbidden)
    popen_seen = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                require(alias.name.split(".")[0] not in FORBIDDEN_IMPORTS, "forbidden import: " + alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            require(node.module.split(".")[0] not in FORBIDDEN_IMPORTS, "forbidden import: " + node.module)
        elif isinstance(node, ast.While):
            raise CheckFailure("module contains forbidden worker loop")
        elif isinstance(node, ast.Call):
            func = node.func
            name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ""
            if isinstance(func, ast.Name) and name == "exec":
                raise CheckFailure("module contains forbidden call: exec")
            require(name not in FORBIDDEN_CALLS, "module contains forbidden call: " + name)
            if isinstance(func, ast.Attribute) and func.attr == "Popen":
                popen_seen = True
                shell_keywords = [kw for kw in node.keywords if kw.arg == "shell"]
                require(shell_keywords, "Popen must set shell explicitly")
                require(isinstance(shell_keywords[0].value, ast.Constant) and shell_keywords[0].value.value is False, "Popen shell must be false")
    require(popen_seen, "module must use bounded subprocess control")


def configure_fixture_module(module, temp: Path) -> tuple[Path, list[list[str]]]:
    report_root = temp / "reports" / "ai_llama_cpp_runtime_candidate_validation"
    module.REPORT_ROOT = report_root
    module.DIAGNOSTIC_DIR = report_root / "diagnostics"
    module.LOG_DIR = report_root / "logs"
    module.RECEIPT_DIR = report_root / "receipts"
    module.MANIFEST_DIR = report_root / "manifests"
    module.EXAMPLE_DIR = report_root / "examples"
    module.CODEX_REPORT = temp / "codex" / "ENGEL_AI_LLAMA_CPP_RUNTIME_CANDIDATE_VALIDATION_V1.md"
    module.PROJECT_ROOT = temp / "repo"
    module.PROJECT_ROOT.mkdir()
    candidate_root = temp / "E" / "ENGEL_APP_MEMORY" / "runtimes" / "llama.cpp" / "candidates"
    candidate = candidate_root / "fixture-build"
    candidate.mkdir(parents=True)
    for name in ["llama-cli.exe", "llama-completion.exe", "llama-tokenize.exe", "llama-server.exe"]:
        (candidate / name).write_text("fixture exe\n", encoding="utf-8")
    (candidate / "runtime.dll").write_text("fixture dll\n", encoding="utf-8")
    module.APPROVED_CANDIDATE_ROOTS = [
        candidate_root,
        temp / "F" / "ENGEL_APP_MEMORY" / "runtimes" / "llama.cpp" / "candidates",
    ]
    module.RUNTIME_PATH_CONFIG = temp / "runtime_path_config.json"
    module.RUNTIME_PATH_CONFIG.write_text(json.dumps({"runtime_binary_path": "E:\\ENGEL_APP_MEMORY\\runtimes\\llama.cpp\\llama-win-x64\\llama-cli.exe"}), encoding="utf-8")
    model = temp / "tiny.gguf"
    model.write_text("fixture model\n", encoding="utf-8")
    module.model_path_for_key = lambda model_key: model
    calls: list[list[str]] = []

    def fake_run(args: list[str], timeout_seconds: int, stdin_text: str | None = None):
        calls.append(args)
        joined = " ".join(args)
        stdout = ""
        if "--help" in args:
            stdout = "-m --model -p --prompt -n --n-predict -c --ctx-size -t --threads --simple-io --no-display-prompt --log-disable --no-conversation --offline --no-warmup --list-devices"
        elif "--version" in args:
            stdout = "llama fixture version"
        elif "--list-devices" in args:
            stdout = "CPU fixture"
        elif "-m" in args and "-n" in args:
            stdout = "fixture no-generation validation"
        return module.ExecutionResult(
            command_executed=True,
            runtime_process_started=True,
            runtime_process_exited=True,
            timeout_seconds=timeout_seconds,
            exit_code=0,
            stdout_text=stdout,
            stderr_text="",
            stdout_truncated=False,
            stderr_truncated=False,
            timed_out=False,
            interrupted=False,
            orphan_process_detected=False,
            runtime_process_id=123,
            cleanup_action="none",
            error=None,
        )

    module.run_bounded_command = fake_run
    return candidate, calls


def check_commands_and_receipts() -> None:
    module = load_module("engel_ai_llama_cpp_runtime_candidate_validation_fixture", MODULE)
    with tempfile.TemporaryDirectory() as raw:
        temp = Path(raw)
        candidate, calls = configure_fixture_module(module, temp)
        for args in [
            ["status"],
            ["list-candidates"],
            ["inspect-candidate", str(candidate)],
            ["json"],
        ]:
            code, output = capture_main(module, args)
            require(code == 0, "command failed: " + " ".join(args))
            data = json.loads(output)
            require(data, "command produced empty JSON: " + " ".join(args))

        code, output = capture_main(module, ["validate-no-generation", str(candidate), "tiny_seed"])
        require(code != 0, "missing approval token accepted")
        data = json.loads(output)
        require(data.get("approval_token_verified") is False, "missing token should not verify")
        require(data.get("registered_runtime_changed") is False, "registered runtime changed on missing token")

        code, output = capture_main(module, ["validate-no-generation", str(candidate), "tiny_seed", "--approval", "WRONG"])
        require(code != 0, "wrong approval token accepted")
        data = json.loads(output)
        require(data.get("approval_token_verified") is False, "wrong token should not verify")

        code, output = capture_main(module, ["validate-no-generation", str(candidate), "daily_local", "--approval", "APPROVE_RUNTIME_CANDIDATE_NO_GENERATION_VALIDATION"])
        require(code != 0, "non-tiny model accepted")
        data = json.loads(output)
        require(data.get("model_key") == "daily_local", "non-tiny refusal receipt missing model key")

        code, output = capture_main(module, ["probe-safe", str(candidate)])
        require(code == 0, "safe probe fixture failed")
        data = json.loads(output)
        require(data.get("safe_probes_passed") is True, "safe probes did not pass in fixture")

        code, output = capture_main(module, ["preview-no-generation", str(candidate), "tiny_seed"])
        require(code == 0, "preview command failed")
        data = json.loads(output)
        require(data.get("command_preview_only") is True, "preview must remain inert")
        require(data.get("candidate_commands"), "preview did not build candidate commands")

        code, output = capture_main(module, ["validate-no-generation", str(candidate), "tiny_seed", "--approval", "APPROVE_RUNTIME_CANDIDATE_NO_GENERATION_VALIDATION"])
        require(code == 0, "approved fixture validation failed")
        receipt = json.loads(output)
        for key in [
            "inference_enabled",
            "chat_enabled",
            "server_enabled",
            "auto_load_enabled",
            "trusted_memory_write_enabled",
            "runtime_ready_for_inference",
            "registered_runtime_changed",
        ]:
            require(receipt.get(key) is False, "receipt safety field must be false: " + key)
        require(receipt.get("n_predict") == 0, "n_predict must remain zero")
        require(receipt.get("candidate_runtime_ready_for_swap_review") is True, "successful candidate not marked ready for swap review")
        require(receipt.get("candidate_validation_passed") is True, "fixture validation did not pass")
        require(not any("server" in " ".join(call).lower() for call in calls), "server executable was run in fixture")

        approved = str(candidate)
        rejected = [
            str(ROOT),
            "C:\\temp\\candidate",
            "D:\\other\\candidate",
            "G:\\ENGEL_APP_MEMORY\\models\\manual_downloads",
            str(module.APPROVED_CANDIDATE_ROOTS[0] / ".." / "escape"),
            str(module.APPROVED_CANDIDATE_ROOTS[0] / "wsl-ubuntu-build"),
            str(module.APPROVED_CANDIDATE_ROOTS[0] / "docker-build"),
            str(module.APPROVED_CANDIDATE_ROOTS[0] / ("her" + "mes-build")),
        ]
        accepted_shape = module.validate_candidate_path(approved)
        require(accepted_shape.get("candidate_under_approved_root") is True, "approved candidate path rejected")
        for bad in rejected:
            result = module.validate_candidate_path(bad)
            require(result.get("candidate_under_approved_root") is False, "unsafe candidate path accepted: " + bad)


def check_docs_and_registration() -> None:
    report = read(REPORT)
    for needle in [
        "ENGEL_AI_LLAMA_CPP_RUNTIME_CANDIDATE_VALIDATION_V1",
        "Candidate Folder",
        "Safe Probes",
        "Candidate Validation Result",
        "Registered runtime unchanged",
        "This phase validates a manually placed runtime candidate only.",
    ]:
        require(needle in report, "report missing: " + needle)
    commands = read(COMMANDS)
    for command in REQUIRED_COMMANDS:
        require(command in commands, "ENGEL_COMMANDS missing command: " + command)
    codex_verify = read(CODEX_VERIFY)
    require("tools\\verify_engel_ai_llama_cpp_runtime_candidate_validation.py" in codex_verify, "codex verify missing candidate validation verifier")
    readiness = read(READINESS)
    for needle in [
        "LLAMA_CPP_RUNTIME_CANDIDATE_VALIDATION_RECEIPTS",
        "latest_llama_cpp_runtime_candidate_validation",
        "candidate_runtime_ready_for_swap_review",
        "ENGEL_AI_LLAMA_CPP_RUNTIME_SWAP_APPROVAL_V1",
    ]:
        require(needle in readiness, "readiness missing candidate validation integration: " + needle)


def main() -> int:
    try:
        check_files()
        check_static_safety()
        check_commands_and_receipts()
        check_docs_and_registration()
    except CheckFailure as exc:
        print("ENGEL_AI_LLAMA_CPP_RUNTIME_CANDIDATE_VALIDATION_VERIFY_FAIL")
        print(str(exc))
        return 1
    print("ENGEL_AI_LLAMA_CPP_RUNTIME_CANDIDATE_VALIDATION_VERIFY_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
