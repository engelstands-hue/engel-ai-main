from __future__ import annotations

import ast
from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "engel_ai_runtime_readiness.py"
GUI = ROOT / "tools" / "engel_ai_runtime_readiness_dashboard.py"
VERIFIER = ROOT / "tools" / "verify_engel_ai_runtime_readiness.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_AI_RUNTIME_READINESS_DASHBOARD_V1.md"
COMMANDS = ROOT / "memory" / "ENGEL_COMMANDS.md"
CODEX_VERIFY = ROOT / "scripts" / "codex_verify.ps1"

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
    "write_text",
    "write_bytes",
    "mkdir",
    "unlink",
    "rename",
}

REQUIRED_COMMANDS = [
    "ai runtime readiness status",
    "ai runtime readiness json",
    "ai runtime readiness models",
    "ai runtime readiness libraries",
    "ai runtime readiness safety",
    "ai runtime readiness remote-worker",
    "ai runtime readiness code-companion",
    "ai runtime readiness next",
    "ai runtime readiness dashboard",
]

REQUIRED_MODEL_TIERS = [
    "Tiny Seed Mode",
    "Daily Local Mode",
    "Research Worker Mode",
    "Alternative Research Worker",
]


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def load_module():
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location("engel_ai_runtime_readiness", MODULE)
    require(spec is not None and spec.loader is not None, "could not load readiness module")
    module = importlib.util.module_from_spec(spec)
    sys.modules["engel_ai_runtime_readiness"] = module
    spec.loader.exec_module(module)
    return module


def check_files() -> None:
    for path in [MODULE, GUI, VERIFIER, REPORT, COMMANDS, CODEX_VERIFY]:
        require(path.exists() and path.is_file(), "missing required file: " + str(path.relative_to(ROOT)))


def check_source_safety(path: Path, *, gui: bool = False) -> None:
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
        "Invoke-WebRequest",
        "curl ",
        "wsl.exe",
        "docker.",
        ".rglob(",
        "os.walk(",
        "write_text(",
        "write_bytes(",
        "mkdir(",
    ]:
        require(forbidden.lower() not in source.lower(), f"{path.name} contains forbidden behavior text: {forbidden}")
    if gui:
        for required in [
            "Engel AI Runtime Readiness Dashboard",
            "READ ONLY",
            "NO INFERENCE",
            "NO MODEL LOAD",
            "NO CLOUD",
            "NO DOWNLOADS",
            "NO TRUSTED MEMORY WRITE",
            "NO AUTO-APPLY",
            "Refresh",
            "Copy Summary",
            "Copy JSON",
            "Close",
        ]:
            require(required in source, "GUI missing required read-only text: " + required)
        for forbidden_button in [
            "Start Inference",
            "Load Model",
            "Download Model",
            "Install Package",
            "Enable Cloud",
            "Write Memory",
            "Apply Patch",
            "Start Worker Automatically",
            "Run Provider",
            "Bypass Safety",
        ]:
            require(forbidden_button not in source, "GUI contains forbidden button label: " + forbidden_button)
    else:
        for required in [
            "NOT_READY_FOR_INFERENCE",
            "READY_FOR_MANUAL_MODEL_INTAKE",
            "READY_FOR_LIBRARY_REVIEW",
            "READY_FOR_REMOTE_WORKER_SMOKE",
            "BLOCKED_ITEMS_PRESENT",
            "inference_enabled",
            "model_auto_load_enabled",
            "provider_api_enabled",
            "download_enabled",
            "trusted_memory_write_enabled",
            "engel_code_companion_password_gate_integration.py",
            "ENGEL_REMOTE_WORKER_PHASE_12_ENGEL_CONTROLLED_PHONE_LINK_MANAGER.md",
        ]:
            require(required in source, "readiness source missing required text: " + required)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                require(alias.name.split(".")[0] not in FORBIDDEN_IMPORTS, "forbidden import: " + alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            require(node.module.split(".")[0] not in FORBIDDEN_IMPORTS, "forbidden import: " + node.module)
        elif isinstance(node, (ast.While, ast.AsyncFunctionDef)):
            raise CheckFailure(f"{path.name} contains forbidden worker shape")
        elif isinstance(node, ast.Call):
            func = node.func
            name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ""
            if isinstance(func, ast.Name) and name == "exec":
                raise CheckFailure(f"{path.name} contains forbidden call: exec")
            require(name not in FORBIDDEN_CALLS, f"{path.name} contains forbidden call: {name}")


def capture_main(module, args: list[str]) -> str:
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        code = module.main(args)
    require(code == 0, "command failed: " + " ".join(args))
    return buffer.getvalue()


def check_runtime_commands() -> None:
    module = load_module()
    payload = module.readiness_payload()
    require(payload["mode"] == "read_only_readiness_reporting", "mode mismatch")
    require("NOT_READY_FOR_INFERENCE" in payload["overall_readiness"], "inference readiness must stay blocked")
    safety = payload["safety_flags"]
    for key in [
        "inference_enabled",
        "model_auto_load_enabled",
        "provider_api_enabled",
        "download_enabled",
        "package_install_enabled",
        "trusted_memory_write_enabled",
        "source_mutation_enabled",
        "route_mutation_enabled",
        "queue_mutation_enabled",
        "background_workers_enabled",
        "auto_apply_enabled",
    ]:
        require(safety[key] is False, "safety flag must be false: " + key)

    models = payload["model_inventory"]["expected_tiers"]
    require(len(models) == 4, "expected four model tiers")
    tiers = {model["tier"] for model in models}
    for tier in REQUIRED_MODEL_TIERS:
        require(tier in tiers, "missing model tier: " + tier)
    for model in models:
        require(model["manual_approval_required"] is True, "model must require manual approval")
        require(model["auto_load_enabled"] is False, "model autoload must be false")
        require(model["inference_enabled"] is False, "model inference must be false")
        require(model["download_enabled"] is False, "model download must be false")
        expected_path = model["expected_path"]
        if expected_path != "unknown":
            actual = Path(expected_path)
            if actual.exists() and actual.is_file():
                require(str(model["status"]).startswith("present"), "present file must not be reported missing")
            else:
                require(model["status"] in {"missing", "unknown"}, "missing file must not be faked as installed")

    runtime = payload["runtime_boundaries"]
    require(runtime["runtime_enabled"] is False, "runtime must remain disabled")
    require(runtime["inference_enabled"] is False, "runtime inference must remain disabled")
    require(runtime["local_server_enabled"] is False, "local server must remain disabled")
    require(payload["library_readiness"]["auto_indexing_enabled"] is False, "auto indexing must be false")
    require(payload["library_readiness"]["recursive_scan_enabled"] is False, "recursive scan must be false")
    require(payload["remote_worker_status"]["auto_apply"] is False, "remote worker auto-apply must be false")
    require(payload["code_companion_status"]["protected_apply_blocks_ai_setup"] is False, "protected apply must not block AI setup")
    require(payload["code_companion_status"]["password_gate_config_valid"] is True, "password gate status must be represented")

    for command in ["status", "models", "libraries", "safety", "remote-worker", "code-companion", "next"]:
        output = capture_main(module, [command])
        require(output.strip(), "empty output for command: " + command)
    json_output = capture_main(module, ["json"])
    parsed = json.loads(json_output)
    require(parsed["dashboard_version"] == "1", "json command did not emit dashboard payload")


def check_docs_and_registration() -> None:
    report = read(REPORT)
    for needle in [
        "ENGEL_AI_RUNTIME_READINESS_DASHBOARD_V1",
        "read-only readiness reporting",
        "This phase is read-only readiness reporting.",
        "NOT_READY_FOR_INFERENCE",
        "Model tiers represented",
        "Safety boundaries",
        "Full codex verifier result",
        "Packaging skipped",
    ]:
        require(needle in report, "report missing required text: " + needle)
    commands = read(COMMANDS)
    for command in REQUIRED_COMMANDS:
        require(command in commands, "ENGEL_COMMANDS missing command: " + command)
    codex = read(CODEX_VERIFY)
    require("tools\\verify_engel_ai_runtime_readiness.py" in codex, "codex verifier missing readiness verifier")


def main() -> int:
    try:
        check_files()
        check_source_safety(MODULE)
        check_source_safety(GUI, gui=True)
        check_runtime_commands()
        check_docs_and_registration()
    except CheckFailure as exc:
        print("[FAIL]", exc)
        return 1
    print("[PASS] Engel AI Runtime Readiness Dashboard verifier passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
