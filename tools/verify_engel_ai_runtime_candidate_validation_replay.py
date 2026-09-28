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
MODULE = ROOT / "engel_ai_runtime_candidate_validation_replay.py"
VERIFIER = ROOT / "tools" / "verify_engel_ai_runtime_candidate_validation_replay.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_AI_RUNTIME_CANDIDATE_VALIDATION_REPLAY_V1.md"
REPORT_ROOT = ROOT / "reports" / "ai_runtime_candidate_validation_replay"
LOGS = REPORT_ROOT / "logs"
RECEIPTS = REPORT_ROOT / "receipts"
PLAN_REPORTS = REPORT_ROOT / "reports"
EXAMPLES = REPORT_ROOT / "examples"
COMMANDS = ROOT / "memory" / "ENGEL_COMMANDS.md"
CODEX_VERIFY = ROOT / "scripts" / "codex_verify.ps1"
READINESS = ROOT / "engel_ai_runtime_readiness.py"
FAILURE_DIAGNOSIS_VERIFIER = ROOT / "tools" / "verify_engel_ai_runtime_candidate_failure_diagnosis.py"
CANDIDATE_VALIDATION_VERIFIER = ROOT / "tools" / "verify_engel_ai_llama_cpp_runtime_candidate_validation.py"
SWAP_PLAN_VERIFIER = ROOT / "tools" / "verify_engel_ai_llama_cpp_runtime_swap_plan.py"
COMPATIBILITY_VERIFIER = ROOT / "tools" / "verify_engel_ai_llama_cpp_compatibility_matrix.py"
NO_GENERATION_VERIFIER = ROOT / "tools" / "verify_engel_ai_no_generation_load_check.py"
READINESS_VERIFIER = ROOT / "tools" / "verify_engel_ai_runtime_readiness.py"

REQUIRED_COMMANDS = [
    "ai runtime candidate validation replay status",
    "ai runtime candidate validation replay preview",
    "ai runtime candidate validation replay replay",
    "ai runtime candidate validation replay json",
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
        LOGS,
        RECEIPTS,
        PLAN_REPORTS,
        EXAMPLES,
        COMMANDS,
        CODEX_VERIFY,
        READINESS,
        FAILURE_DIAGNOSIS_VERIFIER,
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
        "APPROVE_RUNTIME_CANDIDATE_VALIDATION_REPLAY",
        "llama-b9198-bin-win-cpu-x64",
        "tiny_seed",
        "llama_cli_prompt_no_generation_offline_replay",
        "shell=False",
        "TimeoutExpired",
        "KeyboardInterrupt",
        "post_process_interruption",
        "output_marker_analysis",
        "disqualifying_interactive_markers_found",
        "disqualifying_generation_markers_found",
        "generated_text_detected",
        "registered_runtime_changed",
        "runtime_ready_for_inference",
        "inference_enabled",
        "chat_enabled",
        "server_enabled",
        "trusted_memory_write_enabled",
        "RUNTIME CANDIDATE VALIDATION REPLAY FAILED",
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


def configure_fixture_module(module, temp: Path) -> None:
    module.PROJECT_ROOT = temp
    module.REPORT_ROOT = temp / "reports" / "ai_runtime_candidate_validation_replay"
    module.LOG_DIR = module.REPORT_ROOT / "logs"
    module.RECEIPT_DIR = module.REPORT_ROOT / "receipts"
    module.PLAN_REPORT_DIR = module.REPORT_ROOT / "reports"
    module.EXAMPLE_DIR = module.REPORT_ROOT / "examples"
    module.CODEX_REPORT = temp / "reports" / "codex_bridge" / "ENGEL_AI_RUNTIME_CANDIDATE_VALIDATION_REPLAY_V1.md"
    module.APPROVED_CANDIDATE_ROOT = temp / "approved_candidates"
    module.CANDIDATE_FOLDER = module.APPROVED_CANDIDATE_ROOT / "llama-b9198-bin-win-cpu-x64"
    module.CANDIDATE_BINARY = module.CANDIDATE_FOLDER / "llama-cli.exe"
    module.MODEL_FILE = temp / "models" / "tiny_seed.gguf"
    module.CANDIDATE_FOLDER.mkdir(parents=True)
    module.MODEL_FILE.parent.mkdir(parents=True)
    module.CANDIDATE_BINARY.write_text("fixture executable placeholder", encoding="utf-8")
    module.MODEL_FILE.write_text("fixture model placeholder", encoding="utf-8")


def check_runtime_fixture_behavior() -> None:
    module = load_module("engel_ai_runtime_candidate_validation_replay_verify", MODULE)
    with tempfile.TemporaryDirectory() as temp_text:
        temp = Path(temp_text)
        configure_fixture_module(module, temp)

        code, output = capture_main(module, ["status"])
        require(code == 0, "status command failed")
        status = json.loads(output)
        require(status.get("runtime_ready_for_inference") is False, "status enabled runtime readiness")

        code, output = capture_main(module, ["preview"])
        require(code == 0, "preview command failed")
        preview = json.loads(output)
        require(preview.get("command_preview_only") is True, "preview did not mark preview-only")
        require("-n" in preview.get("command_args", []) and "0" in preview.get("command_args", []), "preview missing n_predict zero")

        code, output = capture_main(module, ["json"])
        require(code == 0, "json command failed")
        json.loads(output)

        code, output = capture_main(module, ["replay"])
        require(code != 0, "replay without token did not refuse")
        refused = json.loads(output)
        require(refused.get("approval_token_verified") is False, "missing token was treated as approved")
        require(refused.get("command_executed") is False, "missing token executed command")

        code, output = capture_main(module, ["replay", "--approval", "WRONG"])
        require(code != 0, "replay with wrong token did not refuse")
        refused = json.loads(output)
        require(refused.get("command_executed") is False, "wrong token executed command")

        dirty = module.output_marker_analysis(
            "Loading model...\navailable commands:\n> load check\nI\n[ Prompt: 1 t/s | Generation: 1000000.0 t/s ]\nExiting...\n",
            "",
        )
        require(dirty["disqualifying_interactive_markers_found"] is True, "interactive marker fixture not rejected")
        require(dirty["disqualifying_generation_markers_found"] is True, "generation marker fixture not rejected")
        require(dirty["generated_text_detected"] is True, "generated text fixture not detected")

        clean = module.output_marker_analysis("loading model\nload time = 1 ms\nno predictions requested\nexiting\n", "")
        require(clean["disqualifying_interactive_markers_found"] is False, "clean fixture marked interactive")
        require(clean["disqualifying_generation_markers_found"] is False, "clean fixture marked generation")
        require(clean["generated_text_detected"] is False, "clean fixture marked generated")

        module.list_llama_processes = lambda: []

        def fake_dirty_run(_args, timeout_seconds):
            return module.ExecutionResult(
                True,
                True,
                True,
                timeout_seconds,
                0,
                "Loading model...\navailable commands:\n> load check\nI\n[ Prompt: 1 t/s | Generation: 1000000.0 t/s ]\nExiting...\n",
                "",
                False,
                False,
                False,
                False,
                False,
                False,
            )

        module.run_bounded_command = fake_dirty_run
        dirty_receipt = module.replay(module.APPROVAL_TOKEN)
        require(dirty_receipt.get("candidate_validation_replay_passed") is False, "dirty output replay passed")
        require(dirty_receipt.get("registered_runtime_changed") is False, "dirty replay changed runtime")
        require(dirty_receipt.get("runtime_ready_for_inference") is False, "dirty replay enabled runtime")

        def fake_clean_run(_args, timeout_seconds):
            return module.ExecutionResult(
                True,
                True,
                True,
                timeout_seconds,
                0,
                "loading model\nno predictions requested\nexiting\n",
                "",
                False,
                False,
                False,
                False,
                False,
                False,
            )

        module.run_bounded_command = fake_clean_run
        clean_receipt = module.replay(module.APPROVAL_TOKEN)
        require(clean_receipt.get("candidate_validation_replay_passed") is True, "clean fixture replay did not pass")
        for key in [
            "runtime_ready_for_inference",
            "inference_enabled",
            "chat_enabled",
            "server_enabled",
            "trusted_memory_write_enabled",
            "registered_runtime_changed",
        ]:
            require(clean_receipt.get(key) is False, "clean fixture safety field not false: " + key)


def check_docs_and_registration() -> None:
    report = read(REPORT)
    for needle in [
        "ENGEL_AI_RUNTIME_CANDIDATE_VALIDATION_REPLAY_V1",
        "Why Replay Exists",
        "Registered runtime changed",
        "This phase replays one bounded candidate validation",
    ]:
        require(needle in report, "report missing: " + needle)
    commands = read(COMMANDS)
    for command in REQUIRED_COMMANDS:
        require(command in commands, "ENGEL_COMMANDS missing command: " + command)
    codex_verify = read(CODEX_VERIFY)
    require("tools\\verify_engel_ai_runtime_candidate_validation_replay.py" in codex_verify, "codex_verify missing replay verifier")
    readiness = read(READINESS)
    for needle in [
        "RUNTIME_CANDIDATE_VALIDATION_REPLAY_RECEIPTS",
        "latest_runtime_candidate_validation_replay",
        "ENGEL_AI_LLAMA_CPP_RUNTIME_SWAP_APPROVAL_V1",
        "runtime_ready_for_inference",
    ]:
        require(needle in readiness, "readiness missing replay integration: " + needle)


def main() -> int:
    try:
        check_files()
        check_static_safety()
        check_runtime_fixture_behavior()
        check_docs_and_registration()
    except CheckFailure as exc:
        print("ENGEL_AI_RUNTIME_CANDIDATE_VALIDATION_REPLAY_VERIFY_FAIL")
        print(str(exc))
        return 1
    print("ENGEL_AI_RUNTIME_CANDIDATE_VALIDATION_REPLAY_VERIFY_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
