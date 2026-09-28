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
MODULE = ROOT / "engel_ai_llama_cpp_runtime_swap_plan.py"
VERIFIER = ROOT / "tools" / "verify_engel_ai_llama_cpp_runtime_swap_plan.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_AI_LLAMA_CPP_RUNTIME_SWAP_PLAN_V1.md"
REPORT_ROOT = ROOT / "reports" / "ai_llama_cpp_runtime_swap_plan"
MANIFESTS = REPORT_ROOT / "manifests"
RECEIPTS = REPORT_ROOT / "receipts"
PLAN_REPORTS = REPORT_ROOT / "reports"
EXAMPLES = REPORT_ROOT / "examples"
COMMANDS = ROOT / "memory" / "ENGEL_COMMANDS.md"
CODEX_VERIFY = ROOT / "scripts" / "codex_verify.ps1"
READINESS = ROOT / "engel_ai_runtime_readiness.py"
COMPATIBILITY_VERIFIER = ROOT / "tools" / "verify_engel_ai_llama_cpp_compatibility_matrix.py"
NO_GENERATION_VERIFIER = ROOT / "tools" / "verify_engel_ai_no_generation_load_check.py"
LOCAL_RUNTIME_VERIFIER = ROOT / "tools" / "verify_engel_ai_local_runtime_path_config.py"
READINESS_VERIFIER = ROOT / "tools" / "verify_engel_ai_runtime_readiness.py"

REQUIRED_COMMANDS = [
    "ai llama.cpp runtime swap plan status",
    "ai llama.cpp runtime swap plan inventory-current",
    "ai llama.cpp runtime swap plan plan",
    "ai llama.cpp runtime swap plan manual-placement-instructions",
    "ai llama.cpp runtime swap plan validate-candidate-folder",
    "ai llama.cpp runtime swap plan json",
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
        MANIFESTS,
        RECEIPTS,
        PLAN_REPORTS,
        EXAMPLES,
        COMMANDS,
        CODEX_VERIFY,
        READINESS,
        COMPATIBILITY_VERIFIER,
        NO_GENERATION_VERIFIER,
        LOCAL_RUNTIME_VERIFIER,
        READINESS_VERIFIER,
    ]:
        require(path.exists(), "missing required path: " + str(path.relative_to(ROOT)))


def check_static_safety() -> None:
    source = read(MODULE)
    tree = ast.parse(source)
    for needle in [
        "status",
        "inventory-current",
        "plan",
        "manual-placement-instructions",
        "validate-candidate-folder",
        "json",
        "runtime_swap_plan_version",
        "runtime_swap_plan_receipt_version",
        "ENGEL_AI_LLAMA_CPP_RUNTIME_CANDIDATE_VALIDATION_V1",
        "RUNTIME SWAP PLAN RECORDED",
        "manual_download_required",
        "engel_download_enabled",
        "engel_install_enabled",
        "runtime_execution_enabled_in_this_phase",
        "model_load_enabled_in_this_phase",
        "inference_enabled",
        "chat_enabled",
        "server_enabled",
        "trusted_memory_write_enabled",
        "source_route_queue_mutation",
        "server_binary_inventory_only",
        "llama-server.exe",
        "rpc-server.exe",
        "APPROVED_CANDIDATE_ROOTS",
        "QUARANTINE_ROOTS",
    ]:
        require(needle in source, "module missing required safety text: " + needle)
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
        "normal_inference_enabled\": True",
        "inference_enabled\": True",
        "chat_enabled\": True",
        "server_enabled\": True",
        "trusted_memory_write_enabled\": True",
        "runtime_ready_for_inference\": True",
        "model_load_enabled_in_this_phase\": True",
        "runtime_execution_enabled_in_this_phase\": True",
        "engel_download_enabled\": True",
        "engel_install_enabled\": True",
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
            if isinstance(func, ast.Name) and name == "exec":
                raise CheckFailure("module contains forbidden call: exec")
            require(name not in FORBIDDEN_CALLS, "module contains forbidden call: " + name)


def safe_probe_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for binary in ["llama-cli.exe", "llama-completion.exe"]:
        for probe in ["--help", "--version", "--list-devices"]:
            rows.append(
                {
                    "binary": binary,
                    "probe": probe,
                    "process_exited": True,
                    "timed_out": False,
                    "orphan_process_detected": False,
                }
            )
    return rows


def configure_fixture_module(module, temp: Path) -> None:
    report_root = temp / "reports" / "ai_llama_cpp_runtime_swap_plan"
    module.REPORT_ROOT = report_root
    module.MANIFEST_DIR = report_root / "manifests"
    module.RECEIPT_DIR = report_root / "receipts"
    module.PLAN_REPORT_DIR = report_root / "reports"
    module.EXAMPLE_DIR = report_root / "examples"
    module.CODEX_REPORT = temp / "codex" / "ENGEL_AI_LLAMA_CPP_RUNTIME_SWAP_PLAN_V1.md"

    compat_root = temp / "reports" / "ai_llama_cpp_compatibility"
    module.COMPATIBILITY_MATRIX_DIR = compat_root / "matrices"
    module.COMPATIBILITY_RECEIPT_DIR = compat_root / "receipts"
    module.COMPATIBILITY_MATRIX_DIR.mkdir(parents=True)
    module.COMPATIBILITY_RECEIPT_DIR.mkdir(parents=True)
    matrix = {
        "compatibility_matrix_version": "1",
        "created_at": "2026-05-17T21:27:42Z",
        "recommended_candidate_id": "llama_cli_simple_io",
        "safe_probe_results": safe_probe_rows(),
        "final_decision": "LLAMA CPP COMPATIBILITY MATRIX RECORDED",
    }
    (module.COMPATIBILITY_MATRIX_DIR / "LLAMA_CPP_COMPATIBILITY_MATRIX_fixture.json").write_text(json.dumps(matrix), encoding="utf-8")
    probe = {
        "compatibility_probe_version": "1",
        "created_at": "2026-05-17T21:27:43Z",
        "candidate_id": "llama_cli_simple_io",
        "candidate_probe_passed": False,
        "final_decision": "LLAMA CPP COMPATIBILITY PROBE FAILED",
    }
    (module.COMPATIBILITY_RECEIPT_DIR / "LLAMA_CPP_COMPATIBILITY_PROBE_fixture.json").write_text(json.dumps(probe), encoding="utf-8")

    runtime = temp / "E" / "ENGEL_APP_MEMORY" / "runtimes" / "llama.cpp" / "llama-win-x64"
    cuda = temp / "E" / "ENGEL_APP_MEMORY" / "runtimes" / "llama.cpp" / "llama-win-cuda-x64"
    runtime.mkdir(parents=True)
    cuda.mkdir(parents=True)
    for name in ["llama-cli.exe", "llama-completion.exe", "llama-server.exe"]:
        (runtime / name).write_text("fixture exe\n", encoding="utf-8")
    module.CURRENT_RUNTIME_BINARY = runtime / "llama-cli.exe"
    module.CURRENT_RUNTIME_FOLDERS = [runtime, cuda]
    module.APPROVED_RUNTIME_ROOTS = [
        temp / "E" / "ENGEL_APP_MEMORY" / "runtimes",
        temp / "F" / "ENGEL_APP_MEMORY" / "runtimes",
    ]
    module.APPROVED_CANDIDATE_ROOTS = [
        temp / "E" / "ENGEL_APP_MEMORY" / "runtimes" / "llama.cpp" / "candidates",
        temp / "F" / "ENGEL_APP_MEMORY" / "runtimes" / "llama.cpp" / "candidates",
    ]
    module.QUARANTINE_ROOTS = [
        temp / "E" / "ENGEL_APP_MEMORY" / "runtimes" / "llama.cpp" / "quarantine",
        temp / "F" / "ENGEL_APP_MEMORY" / "runtimes" / "llama.cpp" / "quarantine",
    ]
    module.RUNTIME_PATH_CONFIG = temp / "runtime_path_config.json"
    module.RUNTIME_PATH_CONFIG.write_text(json.dumps({"runtime_binary_path": str(runtime / "llama-cli.exe")}), encoding="utf-8")
    module.NO_GENERATION_RECEIPT_DIR = temp / "reports" / "ai_no_generation_load_checks" / "receipts"
    module.NO_GENERATION_RECEIPT_DIR.mkdir(parents=True)


def check_commands() -> None:
    module = load_module("engel_ai_llama_cpp_runtime_swap_plan_fixture", MODULE)
    with tempfile.TemporaryDirectory() as raw:
        temp = Path(raw)
        configure_fixture_module(module, temp)
        for args in [
            ["status"],
            ["inventory-current"],
            ["manual-placement-instructions"],
            ["json"],
        ]:
            code, output = capture_main(module, args)
            require(code == 0, "command failed: " + " ".join(args))
            data = json.loads(output)
            require(data, "command produced empty JSON: " + " ".join(args))

        code, output = capture_main(module, ["plan"])
        require(code == 0, "plan command failed")
        manifest = json.loads(output)
        for key in [
            "manual_download_required",
            "engel_download_enabled",
            "engel_install_enabled",
            "runtime_execution_enabled_in_this_phase",
            "model_load_enabled_in_this_phase",
            "inference_enabled",
            "chat_enabled",
            "server_enabled",
            "trusted_memory_write_enabled",
        ]:
            expected = True if key == "manual_download_required" else False
            require(manifest.get(key) is expected, "manifest safety field mismatch: " + key)
        require(manifest.get("current_runtime", {}).get("runtime_ready_for_inference") is False, "manifest must keep runtime_ready_for_inference false")
        require(manifest.get("next_validation_phase") == "ENGEL_AI_LLAMA_CPP_RUNTIME_CANDIDATE_VALIDATION_V1", "missing next validation phase")
        require((module.MANIFEST_DIR).exists(), "plan did not create manifest folder")
        require(list(module.MANIFEST_DIR.glob("LLAMA_CPP_RUNTIME_SWAP_PLAN_*.json")), "plan did not write manifest")
        require(list(module.RECEIPT_DIR.glob("LLAMA_CPP_RUNTIME_SWAP_PLAN_RECEIPT_*.json")), "plan did not write receipt")

        approved = str(module.APPROVED_CANDIDATE_ROOTS[0] / "future-build")
        code, output = capture_main(module, ["validate-candidate-folder", approved])
        require(code == 0, "approved candidate root shape rejected")
        data = json.loads(output)
        require(data.get("accepted_shape") is True, "approved candidate root shape not accepted")
        for bad_path in [
            str(ROOT),
            "C:\\temp\\llama.cpp\\candidate",
            str(module.APPROVED_CANDIDATE_ROOTS[0] / ".." / "escape"),
            str(module.APPROVED_CANDIDATE_ROOTS[0] / "wsl-ubuntu-build"),
            str(module.APPROVED_CANDIDATE_ROOTS[0] / "docker-hermes-build"),
        ]:
            code, output = capture_main(module, ["validate-candidate-folder", bad_path])
            require(code != 0, "unsafe candidate path accepted: " + bad_path)
            data = json.loads(output)
            require(data.get("accepted_shape") is False, "unsafe candidate path marked accepted: " + bad_path)


def check_docs_and_registration() -> None:
    report = read(REPORT)
    for needle in [
        "ENGEL_AI_LLAMA_CPP_RUNTIME_SWAP_PLAN_V1",
        "Current blocker",
        "Manual Placement Instructions",
        "Candidate Acceptance Criteria",
        "ENGEL_AI_LLAMA_CPP_RUNTIME_CANDIDATE_VALIDATION_V1",
        "This phase records a runtime swap plan only.",
    ]:
        require(needle in report, "report missing: " + needle)
    commands = read(COMMANDS)
    for command in REQUIRED_COMMANDS:
        require(command in commands, "ENGEL_COMMANDS missing command: " + command)
    codex_verify = read(CODEX_VERIFY)
    require("tools\\verify_engel_ai_llama_cpp_runtime_swap_plan.py" in codex_verify, "codex verify missing runtime swap verifier")
    readiness = read(READINESS)
    for needle in [
        "LLAMA_CPP_RUNTIME_SWAP_MANIFESTS",
        "latest_llama_cpp_runtime_swap_plan",
        "latest_llama_cpp_runtime_swap_receipt",
        "Manually place alternate llama.cpp Windows runtime candidate",
    ]:
        require(needle in readiness, "readiness missing runtime swap integration: " + needle)


def main() -> int:
    try:
        check_files()
        check_static_safety()
        check_commands()
        check_docs_and_registration()
    except CheckFailure as exc:
        print("ENGEL_AI_LLAMA_CPP_RUNTIME_SWAP_PLAN_VERIFY_FAIL")
        print(str(exc))
        return 1
    print("ENGEL_AI_LLAMA_CPP_RUNTIME_SWAP_PLAN_VERIFY_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
