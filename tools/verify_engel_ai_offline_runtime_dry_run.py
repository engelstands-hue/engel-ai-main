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
MODULE = ROOT / "engel_ai_offline_runtime_dry_run.py"
VERIFIER = ROOT / "tools" / "verify_engel_ai_offline_runtime_dry_run.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_AI_OFFLINE_RUNTIME_DRY_RUN_V1.md"
DRY_RUN_ROOT = ROOT / "reports" / "ai_runtime_dry_runs"
RECEIPTS = DRY_RUN_ROOT / "receipts"
CONFIGS = DRY_RUN_ROOT / "configs"
EXAMPLES = DRY_RUN_ROOT / "examples"
COMMANDS = ROOT / "memory" / "ENGEL_COMMANDS.md"
CODEX_VERIFY = ROOT / "scripts" / "codex_verify.ps1"
READINESS_VERIFIER = ROOT / "tools" / "verify_engel_ai_runtime_readiness.py"
APPROVAL_VERIFIER = ROOT / "tools" / "verify_engel_ai_model_review_approval.py"
INTAKE_VERIFIER = ROOT / "tools" / "verify_engel_ai_manual_model_file_intake.py"

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
    "ai offline runtime dry run status",
    "ai offline runtime dry run list-models",
    "ai offline runtime dry run validate-model",
    "ai offline runtime dry run preview",
    "ai offline runtime dry run dry-run",
    "ai offline runtime dry run dry-run-all",
    "ai offline runtime dry run json",
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
    spec = importlib.util.spec_from_file_location("engel_ai_offline_runtime_dry_run", MODULE)
    require(spec is not None and spec.loader is not None, "could not load offline runtime dry-run module")
    module = importlib.util.module_from_spec(spec)
    sys.modules["engel_ai_offline_runtime_dry_run"] = module
    spec.loader.exec_module(module)
    return module


def check_files() -> None:
    for path in [MODULE, VERIFIER, REPORT, DRY_RUN_ROOT, RECEIPTS, CONFIGS, EXAMPLES, READINESS_VERIFIER, APPROVAL_VERIFIER, INTAKE_VERIFIER]:
        require(path.exists(), "missing required path: " + str(path.relative_to(ROOT)))


def check_static_safety() -> None:
    source = read(MODULE)
    tree = ast.parse(source)
    for needle in [
        "COMMAND PREVIEW ONLY",
        "NOT EXECUTED",
        "MODEL NOT LOADED",
        "NO INFERENCE",
        "runtime_dry_run_ready",
        "model_loaded",
        "process_started",
        "command_executed",
        "llama_cpp_candidate",
        "not_configured",
    ]:
        require(needle in source, "module missing required safety text: " + needle)
    for forbidden in [
        "requests.",
        "socket.",
        "webbrowser.",
        "openai.",
        "anthropic.",
        "ollama",
        "llama_cpp.",
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
        require(forbidden not in source.lower(), "module contains forbidden behavior text: " + forbidden)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                require(alias.name.split(".")[0] not in FORBIDDEN_IMPORTS, "forbidden import: " + alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            require(node.module.split(".")[0] not in FORBIDDEN_IMPORTS, "forbidden import: " + node.module)
        elif isinstance(node, (ast.While, ast.AsyncFunctionDef)):
            raise CheckFailure("module contains forbidden worker shape")
        elif isinstance(node, ast.Call):
            func = node.func
            name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ""
            if isinstance(func, ast.Name) and name == "exec":
                raise CheckFailure("module contains forbidden call: exec")
            require(name not in FORBIDDEN_CALLS, "module contains forbidden call: " + name)


def capture_main(module, args: list[str]) -> tuple[int, str]:
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        code = module.main(args)
    return int(code), buffer.getvalue()


def assert_preview_only_config(config: dict, label: str) -> None:
    require("COMMAND PREVIEW ONLY" in str(config.get("command_preview", "")), label + " preview missing inert label")
    require("NOT EXECUTED" in str(config.get("command_preview", "")), label + " preview missing not executed label")
    for key in [
        "inference_enabled",
        "model_load_enabled",
        "process_start_enabled",
        "provider_api_enabled",
        "trusted_memory_write_enabled",
    ]:
        require(config.get(key) is False, label + " config safety value must be false: " + key)


def assert_receipt_safety(receipt: dict, label: str) -> None:
    require("MODEL NOT LOADED" in str(receipt.get("final_decision", "")), label + " final decision must say model not loaded")
    require("NO INFERENCE" in str(receipt.get("final_decision", "")), label + " final decision must say no inference")
    for key in [
        "runtime_ready",
        "approved_for_runtime",
        "inference_enabled",
        "auto_load_enabled",
        "model_loaded",
        "process_started",
        "command_executed",
        "provider_api_enabled",
        "trusted_memory_write_enabled",
    ]:
        require(receipt.get(key) is False, label + " receipt safety value must be false: " + key)
    require(receipt.get("runtime_dry_run_completed") is True, label + " dry run should be marked completed")
    ready = bool(receipt.get("runtime_dry_run_ready") is True)
    present = bool(receipt.get("runtime_binary_present") is True)
    require(ready == present, label + " readiness must follow honest runtime binary presence")
    if present:
        require(receipt.get("runtime_binary_path"), label + " present runtime binary must include a path")
        require("RUNTIME DRY-RUN RECORDED" in str(receipt.get("final_decision", "")), label + " present-runtime decision mismatch")
    else:
        require(receipt.get("runtime_dry_run_ready") is False, label + " missing runtime must not be dry-run ready")
        require("BLOCKED" in str(receipt.get("final_decision", "")), label + " missing-runtime decision mismatch")
    config = receipt.get("config_preview")
    if isinstance(config, dict):
        assert_preview_only_config(config, label)
    require("COMMAND PREVIEW ONLY" in str(receipt.get("command_preview", "")), label + " receipt preview missing inert label")


def check_existing_outputs_are_safe() -> None:
    if RECEIPTS.exists():
        for receipt_path in sorted(RECEIPTS.glob("*.json"))[-20:]:
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            assert_receipt_safety(receipt, "existing receipt " + receipt_path.name)
    if CONFIGS.exists():
        for config_path in sorted(CONFIGS.glob("*_config_preview.json"))[-20:]:
            config = json.loads(config_path.read_text(encoding="utf-8"))
            assert_preview_only_config(config, "existing config " + config_path.name)


def check_runtime_behavior() -> None:
    module = load_module()
    for command in ["status", "list-models", "json"]:
        code, output = capture_main(module, [command])
        require(code == 0, "command failed: " + command)
        require(output.strip(), "empty output for command: " + command)

    invalid = module.validate_model("not_a_model_key")
    require(invalid["valid"] is False, "missing/unapproved model key must refuse")

    with tempfile.TemporaryDirectory() as temp_name:
        temp = Path(temp_name)
        fake_model = temp / "tiny-runtime-fixture.gguf"
        fake_model.write_bytes(b"GGUF tiny runtime dry-run verifier fixture\n")
        approval_manifest = temp / "approval_manifest.json"
        dry_root = temp / "dry_runs"
        receipt_dir = dry_root / "receipts"
        config_dir = dry_root / "configs"
        examples = dry_root / "examples"
        dry_manifest = config_dir / "dry_run_manifest.json"
        missing_runtime_config = temp / "missing_runtime_path_config.json"
        missing_runtime_contract = temp / "missing_runtime_contract.json"
        approval_payload = {
            "manifest_version": "1",
            "entries": [
                {
                    "model_tier": "Tiny Seed Mode",
                    "model_name": "Qwen2.5-0.5B-Instruct GGUF",
                    "model_file_path": str(fake_model),
                    "approved_for_runtime_dry_run": True,
                    "runtime_dry_run_eligible": True,
                    "inference_enabled": False,
                    "auto_load_enabled": False,
                }
            ],
        }
        approval_manifest.write_text(json.dumps(approval_payload), encoding="utf-8")

        original_paths = (
            module.APPROVAL_MANIFEST,
            module.REPORT_ROOT,
            module.RECEIPT_DIR,
            module.CONFIG_DIR,
            module.EXAMPLES_DIR,
            module.DRY_RUN_MANIFEST,
            module.LOCAL_RUNTIME_PATH_CONFIG,
            module.OFFLINE_RUNTIME_CONTRACT,
        )
        module.APPROVAL_MANIFEST = approval_manifest
        module.REPORT_ROOT = dry_root
        module.RECEIPT_DIR = receipt_dir
        module.CONFIG_DIR = config_dir
        module.EXAMPLES_DIR = examples
        module.DRY_RUN_MANIFEST = dry_manifest
        try:
            validation = module.validate_model("tiny_seed")
            require(validation["valid"] is True, "tiny fixture approval should validate")

            module.LOCAL_RUNTIME_PATH_CONFIG = missing_runtime_config
            module.OFFLINE_RUNTIME_CONTRACT = missing_runtime_contract
            preview = module.build_config_preview("tiny_seed")
            assert_preview_only_config(preview, "missing-runtime fixture")
            result = module.dry_run_model("tiny_seed", created_at="2026-05-17T00:00:00Z")
            receipt_json = Path(result["receipt_json"])
            if not receipt_json.is_absolute():
                receipt_json = ROOT / receipt_json
            require(receipt_json.exists(), "dry-run receipt JSON missing")
            receipt = json.loads(receipt_json.read_text(encoding="utf-8"))
            assert_receipt_safety(receipt, "missing-runtime fixture")
            require(receipt["runtime_binary_present"] is False, "missing-runtime fixture should not require runtime binary")
            receipt_text = receipt_json.with_suffix(".md").read_text(encoding="utf-8")
            require("COMMAND PREVIEW ONLY" in receipt_text, "receipt markdown missing command preview label")
            require("No model was loaded" in receipt_text, "receipt markdown missing no-load statement")
            config_json = Path(result["config_json"])
            if not config_json.is_absolute():
                config_json = ROOT / config_json
            require(config_json.exists(), "config preview JSON missing")

            module.LOCAL_RUNTIME_PATH_CONFIG = original_paths[6]
            module.OFFLINE_RUNTIME_CONTRACT = original_paths[7]
            current_preview = module.build_config_preview("tiny_seed")
            assert_preview_only_config(current_preview, "current-runtime fixture")
            current_result = module.dry_run_model("tiny_seed", created_at="2026-05-17T00:00:01Z")
            current_receipt_json = Path(current_result["receipt_json"])
            if not current_receipt_json.is_absolute():
                current_receipt_json = ROOT / current_receipt_json
            current_receipt = json.loads(current_receipt_json.read_text(encoding="utf-8"))
            assert_receipt_safety(current_receipt, "current-runtime fixture")
            if current_receipt["runtime_binary_present"] is True:
                require(
                    str(current_receipt["runtime_binary_path"]) in current_receipt["command_preview"],
                    "present runtime path should appear only in inert command preview",
                )

            manifest = json.loads(dry_manifest.read_text(encoding="utf-8"))
            require(manifest["entry_count"] == 1, "dry-run manifest entry count mismatch")
            require(manifest["safety"]["inference_enabled"] is False, "manifest inference must remain false")
        finally:
            (
                module.APPROVAL_MANIFEST,
                module.REPORT_ROOT,
                module.RECEIPT_DIR,
                module.CONFIG_DIR,
                module.EXAMPLES_DIR,
                module.DRY_RUN_MANIFEST,
                module.LOCAL_RUNTIME_PATH_CONFIG,
                module.OFFLINE_RUNTIME_CONTRACT,
            ) = original_paths
    check_existing_outputs_are_safe()


def check_docs_and_registration() -> None:
    report = read(REPORT)
    for needle in [
        "ENGEL_AI_OFFLINE_RUNTIME_DRY_RUN_V1",
        "offline runtime wiring",
        "COMMAND PREVIEW ONLY",
        "does not load models",
        "Full codex verifier result",
    ]:
        require(needle in report, "report missing required text: " + needle)
    commands = read(COMMANDS)
    for command in REQUIRED_COMMANDS:
        require(command in commands, "ENGEL_COMMANDS missing command: " + command)
    codex = read(CODEX_VERIFY)
    require("tools\\verify_engel_ai_offline_runtime_dry_run.py" in codex, "codex verifier missing offline runtime dry-run verifier")


def main() -> int:
    try:
        check_files()
        check_static_safety()
        check_runtime_behavior()
        check_docs_and_registration()
    except CheckFailure as exc:
        print("[FAIL]", exc)
        return 1
    print("[PASS] Engel AI Offline Runtime Dry Run verifier passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
