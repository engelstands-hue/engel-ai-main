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
MODULE = ROOT / "engel_ai_local_runtime_path_config.py"
VERIFIER = ROOT / "tools" / "verify_engel_ai_local_runtime_path_config.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_AI_LOCAL_RUNTIME_PATH_CONFIG_V1.md"
CONFIG_ROOT = ROOT / "reports" / "ai_runtime_path_config"
RECEIPTS = CONFIG_ROOT / "receipts"
MANIFESTS = CONFIG_ROOT / "manifests"
EXAMPLES = CONFIG_ROOT / "examples"
COMMANDS = ROOT / "memory" / "ENGEL_COMMANDS.md"
CODEX_VERIFY = ROOT / "scripts" / "codex_verify.ps1"
OFFLINE_DRY_RUN = ROOT / "engel_ai_offline_runtime_dry_run.py"
READINESS = ROOT / "engel_ai_runtime_readiness.py"
OFFLINE_DRY_RUN_VERIFIER = ROOT / "tools" / "verify_engel_ai_offline_runtime_dry_run.py"
MODEL_APPROVAL_VERIFIER = ROOT / "tools" / "verify_engel_ai_model_review_approval.py"
READINESS_VERIFIER = ROOT / "tools" / "verify_engel_ai_runtime_readiness.py"

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

REQUIRED_COMMANDS = [
    "ai local runtime path config status",
    "ai local runtime path config roots",
    "ai local runtime path config validate-root",
    "ai local runtime path config validate-runtime",
    "ai local runtime path config set-runtime",
    "ai local runtime path config manifest",
    "ai local runtime path config json",
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


def check_files() -> None:
    for path in [
        MODULE,
        VERIFIER,
        REPORT,
        CONFIG_ROOT,
        RECEIPTS,
        MANIFESTS,
        EXAMPLES,
        OFFLINE_DRY_RUN,
        READINESS,
        OFFLINE_DRY_RUN_VERIFIER,
        MODEL_APPROVAL_VERIFIER,
        READINESS_VERIFIER,
    ]:
        require(path.exists(), "missing required path: " + str(path.relative_to(ROOT)))


def check_static_safety() -> None:
    for path in [MODULE, OFFLINE_DRY_RUN, READINESS]:
        source = read(path)
        tree = ast.parse(source)
        for forbidden in [
            "requests.",
            "socket.",
            "webbrowser.",
            "openai.",
            "anthropic.",
            "ollama",
            "llama.cpp server",
            "start_llama",
            "pip install",
            "invoke-webrequest",
            "curl ",
            "wsl.exe",
            "docker.",
            ".rglob(",
            "os.walk(",
        ]:
            require(forbidden not in source.lower(), path.name + " contains forbidden behavior text: " + forbidden)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    require(alias.name.split(".")[0] not in FORBIDDEN_IMPORTS, "forbidden import in " + path.name + ": " + alias.name)
            elif isinstance(node, ast.ImportFrom) and node.module:
                require(node.module.split(".")[0] not in FORBIDDEN_IMPORTS, "forbidden import in " + path.name + ": " + node.module)
            elif isinstance(node, (ast.While, ast.AsyncFunctionDef)):
                raise CheckFailure(path.name + " contains forbidden worker shape")
            elif isinstance(node, ast.Call):
                func = node.func
                name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ""
                if isinstance(func, ast.Name) and name == "exec":
                    raise CheckFailure(path.name + " contains forbidden call: exec")
                require(name not in FORBIDDEN_CALLS, path.name + " contains forbidden call: " + name)

    source = read(MODULE)
    for needle in [
        "APPROVE_LOCAL_RUNTIME_PATH",
        "E:\\ENGEL_APP_MEMORY",
        "F:\\ENGEL_APP_MEMORY",
        "G:\\ENGEL_APP_MEMORY",
        "Western Digital SATA 6Gb/s disk drive",
        "Seagate FireCuda Gaming 1TB hard drive P/N 3EDAP6-500",
        "ONN flash memory",
        "durable_runtime_and_large_library_storage",
        "general_engel_memory_and_library_expansion",
        "existing_manual_model_storage",
        "alternate_runtime_root",
        "existing_model_root",
        "outside_approved_runtime_roots_rejected",
        "LOCAL RUNTIME PATH RECORDED",
        "NOT EXECUTED",
        "NO MODEL LOAD",
        "NO INFERENCE",
        "runtime_execution_enabled",
        "model_load_enabled",
        "inference_enabled",
    ]:
        require(needle in source, "runtime path module missing required text: " + needle)
    require("LOCAL_RUNTIME_PATH_CONFIG" in read(OFFLINE_DRY_RUN), "offline dry-run must read local runtime path config")
    require("RUNTIME_PATH_CONFIG_MANIFEST" in read(READINESS), "readiness must represent runtime path config")


def capture_main(module, args: list[str]) -> tuple[int, str]:
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        code = module.main(args)
    return int(code), buffer.getvalue()


def check_runtime_behavior() -> None:
    module = load_module("engel_ai_local_runtime_path_config", MODULE)
    for command in ["status", "roots", "manifest", "json"]:
        code, output = capture_main(module, [command])
        require(code == 0, "command failed: " + command)
        require(output.strip(), "empty output for command: " + command)

    payload = json.loads(capture_main(module, ["json"])[1])
    root_paths = {root["path"] for root in payload["approved_roots"]}
    require(r"E:\ENGEL_APP_MEMORY" in root_paths, "E root must be represented")
    require(r"F:\ENGEL_APP_MEMORY" in root_paths, "F root must be represented")
    require(r"G:\ENGEL_APP_MEMORY" in root_paths, "G root must be represented")
    require(payload["preferred_runtime_root"] == r"E:\ENGEL_APP_MEMORY\runtimes", "preferred runtime root mismatch")
    require(payload["alternate_runtime_root"] == r"F:\ENGEL_APP_MEMORY\runtimes", "alternate runtime root mismatch")
    require(payload["existing_model_root"] == r"G:\ENGEL_APP_MEMORY\models\manual_downloads", "existing model root mismatch")
    for key in [
        "execution_enabled",
        "runtime_execution_enabled",
        "inference_enabled",
        "model_load_enabled",
        "auto_start_enabled",
        "provider_api_enabled",
        "download_enabled",
        "install_enabled",
        "trusted_memory_write_enabled",
        "source_route_queue_mutation",
        "recursive_scan_enabled",
    ]:
        require(payload["safety_flags"][key] is False, "safety flag must remain false: " + key)

    e_root = module.validate_root(r"E:\ENGEL_APP_MEMORY")
    f_root = module.validate_root(r"F:\ENGEL_APP_MEMORY")
    g_root = module.validate_root(r"G:\ENGEL_APP_MEMORY")
    require(e_root["valid"] is True, "E root must validate as approved")
    require(f_root["valid"] is True, "F root must validate as approved")
    require(g_root["valid"] is True, "G root must validate as approved")
    require(f_root["approved_role"] == "general_engel_memory_and_library_expansion", "F root role mismatch")
    require(g_root["approved_role"] == "existing_manual_model_storage", "G root role mismatch")
    rejected = module.validate_root(r"D:\not_engel_memory")
    require(rejected["valid"] is False and rejected["reason"] == "root_not_approved", "arbitrary root must be rejected")
    traversal = module.validate_root(r"..\unsafe_runtime_root")
    require(traversal["valid"] is False and traversal["reason"] == "path_traversal_rejected", "path traversal must be rejected")
    missing = module.validate_runtime(r"E:\ENGEL_APP_MEMORY\runtimes\llama.cpp\llama-cli.exe")
    if missing["runtime_binary_present"] is False:
        require(missing["valid"] is False and missing["reason"] == "runtime_binary_missing", "missing runtime binary must be honest")
    g_runtime_status, _ = module.runtime_root_status(Path(r"G:\ENGEL_APP_MEMORY\not-a-runtime.exe"), allow_example_fixture=False)
    require(g_runtime_status == "approved_engel_root_but_not_runtime_root", "G root must not be treated as a runtime root")
    f_runtime_status, _ = module.runtime_root_status(Path(r"F:\ENGEL_APP_MEMORY\runtimes\llama.cpp\llama-cli.exe"), allow_example_fixture=False)
    require(f_runtime_status == "alternate_runtime_root", "F runtime root must be recognized as alternate")

    EXAMPLES.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="verifier_runtime_path_", dir=EXAMPLES) as temp_name:
        fixture_folder = Path(temp_name)
        fixture = fixture_folder / "llama-cli.exe"
        fixture.write_bytes(b"tiny fake exe fixture; never executed\n")
        valid = module.validate_runtime(str(fixture))
        require(valid["valid"] is True, "example fixture runtime should validate")
        require(valid["root_status"] == "example_fixture", "example fixture root status mismatch")

        with tempfile.TemporaryDirectory() as output_name:
            output = Path(output_name)
            receipt_dir = output / "receipts"
            manifest_path = output / "manifests" / "runtime_config.json"
            try:
                module.set_runtime(str(fixture), backend="llama_cpp", approval_token=None, receipt_dir=receipt_dir, manifest_path=manifest_path)
            except module.RuntimePathConfigError as exc:
                require(str(exc) == "approval_token_rejected", "missing token refusal mismatch")
            else:
                raise CheckFailure("missing approval token must refuse")
            try:
                module.set_runtime(str(fixture), backend="llama_cpp", approval_token="WRONG_TOKEN", receipt_dir=receipt_dir, manifest_path=manifest_path)
            except module.RuntimePathConfigError as exc:
                require(str(exc) == "approval_token_rejected", "wrong token refusal mismatch")
            else:
                raise CheckFailure("wrong approval token must refuse")
            result = module.set_runtime(
                str(fixture),
                backend="llama_cpp",
                approval_token="APPROVE_LOCAL_RUNTIME_PATH",
                receipt_dir=receipt_dir,
                manifest_path=manifest_path,
                created_at="2026-05-17T00:00:00Z",
            )
            receipt = json.loads(Path(result["receipt_json"]).read_text(encoding="utf-8"))
            require(receipt["final_decision"] == module.FINAL_DECISION_SUCCESS, "receipt final decision mismatch")
            require(receipt["approval_token_name"] == "APPROVE_LOCAL_RUNTIME_PATH", "receipt token name mismatch")
            require(receipt["approval_token_verified"] is True, "receipt token verification mismatch")
            for key in [
                "runtime_execution_enabled",
                "model_load_enabled",
                "inference_enabled",
                "auto_start_enabled",
                "provider_api_enabled",
                "download_enabled",
                "install_enabled",
                "trusted_memory_write_enabled",
            ]:
                require(receipt[key] is False, "receipt safety value must be false: " + key)

            dry = load_module("engel_ai_offline_runtime_dry_run_for_path_config", OFFLINE_DRY_RUN)
            original_config = dry.LOCAL_RUNTIME_PATH_CONFIG
            dry.LOCAL_RUNTIME_PATH_CONFIG = manifest_path
            try:
                runtime = dry.runtime_status()
                require(runtime["runtime_backend"] == "llama_cpp", "dry-run must use configured llama_cpp backend")
                require(runtime["runtime_binary_present"] is True, "dry-run must see fixture binary as present")
                require(runtime["runtime_process_start_enabled"] is False, "dry-run must keep process start disabled")
            finally:
                dry.LOCAL_RUNTIME_PATH_CONFIG = original_config

    readiness = load_module("engel_ai_runtime_readiness_for_path_config", READINESS)
    readiness_payload = readiness.readiness_payload()
    runtime_boundaries = readiness_payload["runtime_boundaries"]
    require(runtime_boundaries["preferred_runtime_root"] == r"E:\ENGEL_APP_MEMORY\runtimes", "readiness preferred runtime root mismatch")
    require(runtime_boundaries["alternate_runtime_root"] == r"F:\ENGEL_APP_MEMORY\runtimes", "readiness alternate runtime root mismatch")
    require(len(runtime_boundaries["approved_engel_roots"]) == 3, "readiness must represent all three Engel roots")
    require(runtime_boundaries["runtime_path_config_status"]["runtime_execution_enabled"] is False, "readiness runtime execution must remain false")
    require(runtime_boundaries["runtime_path_config_status"]["inference_enabled"] is False, "readiness inference must remain false")


def check_docs_and_registration() -> None:
    report = read(REPORT)
    for needle in [
        "ENGEL_AI_LOCAL_RUNTIME_PATH_CONFIG_V1",
        "E:\\ENGEL_APP_MEMORY",
        "F:\\ENGEL_APP_MEMORY",
        "G:\\ENGEL_APP_MEMORY",
        "Alternate runtime root",
        "APPROVE_LOCAL_RUNTIME_PATH",
        "does not execute the runtime",
        "does not load models",
        "does not run inference",
        "Packaging skipped",
    ]:
        require(needle in report, "report missing required text: " + needle)
    commands = read(COMMANDS)
    for command in REQUIRED_COMMANDS:
        require(command in commands, "command docs missing: " + command)
    codex_verify = read(CODEX_VERIFY)
    require("tools\\verify_engel_ai_local_runtime_path_config.py" in codex_verify, "codex verifier missing local runtime path verifier")


def main() -> int:
    try:
        check_files()
        check_static_safety()
        check_runtime_behavior()
        check_docs_and_registration()
    except CheckFailure as exc:
        print("[FAIL] " + str(exc))
        return 1
    print("[PASS] Engel AI Local Runtime Path Config verifier passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
