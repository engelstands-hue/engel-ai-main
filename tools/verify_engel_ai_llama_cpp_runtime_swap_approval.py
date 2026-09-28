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
MODULE = ROOT / "engel_ai_llama_cpp_runtime_swap_approval.py"
VERIFIER = ROOT / "tools" / "verify_engel_ai_llama_cpp_runtime_swap_approval.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_AI_LLAMA_CPP_RUNTIME_SWAP_APPROVAL_V1.md"
REPORT_ROOT = ROOT / "reports" / "ai_llama_cpp_runtime_swap_approval"
RECEIPTS = REPORT_ROOT / "receipts"
PLAN_REPORTS = REPORT_ROOT / "reports"
EXAMPLES = REPORT_ROOT / "examples"
BACKUPS = REPORT_ROOT / "backups"
RUNTIME_PATH_CONFIG = ROOT / "reports" / "ai_runtime_path_config" / "manifests" / "engel_ai_local_runtime_path_config_manifest.json"
ALT_RECEIPTS = ROOT / "reports" / "ai_runtime_candidate_alt_command_style" / "receipts"
COMMANDS = ROOT / "memory" / "ENGEL_COMMANDS.md"
CODEX_VERIFY = ROOT / "scripts" / "codex_verify.ps1"
READINESS = ROOT / "engel_ai_runtime_readiness.py"

ALT_STYLE_VERIFIER = ROOT / "tools" / "verify_engel_ai_runtime_candidate_alt_command_style.py"
REPLAY_VERIFIER = ROOT / "tools" / "verify_engel_ai_runtime_candidate_validation_replay.py"
FAILURE_DIAGNOSIS_VERIFIER = ROOT / "tools" / "verify_engel_ai_runtime_candidate_failure_diagnosis.py"
CANDIDATE_VALIDATION_VERIFIER = ROOT / "tools" / "verify_engel_ai_llama_cpp_runtime_candidate_validation.py"
SWAP_PLAN_VERIFIER = ROOT / "tools" / "verify_engel_ai_llama_cpp_runtime_swap_plan.py"
COMPATIBILITY_VERIFIER = ROOT / "tools" / "verify_engel_ai_llama_cpp_compatibility_matrix.py"
NO_GENERATION_VERIFIER = ROOT / "tools" / "verify_engel_ai_no_generation_load_check.py"
READINESS_VERIFIER = ROOT / "tools" / "verify_engel_ai_runtime_readiness.py"
MEMORY_ROOTS_VERIFIER = ROOT / "tools" / "verify_engel_memory_roots_storage_layout.py"

REQUIRED_COMMANDS = [
    "ai llama cpp runtime swap approval status",
    "ai llama cpp runtime swap approval preview",
    "ai llama cpp runtime swap approval approve",
    "ai llama cpp runtime swap approval json",
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
    "Popen",
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
    ALT_STYLE_VERIFIER,
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
        RECEIPTS,
        PLAN_REPORTS,
        EXAMPLES,
        BACKUPS,
        RUNTIME_PATH_CONFIG,
        ALT_RECEIPTS,
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
        "APPROVE_LLAMA_CPP_RUNTIME_SWAP",
        "ad455381a65fbe432c3197156941c2f9b778fc0c",
        "llama-b9198-bin-win-cpu-x64",
        "llama-cli.exe",
        "llama-tokenize.exe",
        "llama-server.exe",
        "rpc-server.exe",
        "FORBIDDEN_SERVER_BINARIES",
        "RUNTIME_SWAP_APPROVAL",
        "rollback_previous_runtime_path_recorded",
        "first_local_response_smoke_allowed_next",
        "runtime_process_started",
        "model_loaded",
        "inference_enabled",
        "chat_enabled",
        "server_enabled",
        "auto_load_enabled",
        "trusted_memory_write_enabled",
        "runtime_ready_for_inference",
        "RUNTIME SWAP APPROVAL RECORDED",
        "RUNTIME SWAP APPROVAL BLOCKED",
        "tasklist",
        "shell=False",
    ]:
        require(needle in source, "module missing required text: " + needle)
    for forbidden in [
        "shell=True",
        "subprocess.Popen",
        "communicate(",
        "--model",
        "--prompt",
        "--n-predict",
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
        "runtime_ready_for_inference\": True",
        "inference_enabled\": True",
        "chat_enabled\": True",
        "server_enabled\": True",
        "trusted_memory_write_enabled\": True",
        "model_loaded\": True",
        "runtime_process_started\": True",
    ]:
        require(forbidden.lower() not in source.lower(), "module contains forbidden behavior text: " + forbidden)
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
            if isinstance(func, ast.Attribute) and func.attr == "run":
                shell_keywords = [kw for kw in node.keywords if kw.arg == "shell"]
                require(shell_keywords, "subprocess.run call missing shell keyword")
                require(isinstance(shell_keywords[0].value, ast.Constant) and shell_keywords[0].value.value is False, "subprocess.run shell must be false")
                require(node.args and isinstance(node.args[0], ast.List), "subprocess.run must use explicit args")
                first = node.args[0].elts[0]
                require(isinstance(first, ast.Constant) and first.value == "tasklist", "only tasklist subprocess is allowed")


def check_runtime_commands_and_tokens() -> None:
    module = load_module("engel_ai_llama_cpp_runtime_swap_approval_commands", MODULE)
    before_manifest = read(RUNTIME_PATH_CONFIG)
    before_receipts = sorted(RECEIPTS.glob("RUNTIME_SWAP_APPROVAL_*.json"))
    for command in ["status", "preview", "json"]:
        code, output = capture_main(module, [command])
        require(code == 0, "command failed: " + command)
        require(output.strip(), "empty output for command: " + command)
        json.loads(output)
    code, output = capture_main(module, ["approve"])
    require(code != 0, "approve without token must refuse")
    refused = json.loads(output)
    require(refused.get("approval_token_verified") is False, "missing token was accepted")
    require(refused.get("runtime_swap_approval_recorded") is False, "missing token recorded approval")
    code, output = capture_main(module, ["approve", "--approval", "WRONG"])
    require(code != 0, "approve wrong token must refuse")
    refused = json.loads(output)
    require(refused.get("approval_token_verified") is False, "wrong token was accepted")
    require(refused.get("runtime_swap_approval_recorded") is False, "wrong token recorded approval")
    require(read(RUNTIME_PATH_CONFIG) == before_manifest, "wrong/missing token changed runtime path config")
    require(sorted(RECEIPTS.glob("RUNTIME_SWAP_APPROVAL_*.json")) == before_receipts, "wrong/missing token wrote approval receipt")
    preview = json.loads(capture_main(module, ["preview"])[1])
    require(preview["preview_only"] is True, "preview must be preview only")
    require("REGISTERED RUNTIME NOT CHANGED" in preview["preview_message"], "preview must say registered runtime not changed")


def check_source_alt_receipt() -> None:
    receipts = sorted(ALT_RECEIPTS.glob("RUNTIME_CANDIDATE_ALT_COMMAND_STYLE_*.json"))
    require(receipts, "missing source alt command-style receipt")
    latest = json.loads(read(receipts[-1]))
    require(latest.get("alt_command_style_validation_passed") is True, "source alt validation must pass")
    require(latest.get("candidate_runtime_ready_for_swap_review") is True, "candidate must be ready for swap review")
    require(latest.get("selected_command_style") == "llama_tokenize_ids_count", "source style must be tokenize-only")
    require(latest.get("disqualifying_interactive_markers_found") is False, "source has interactive markers")
    require(latest.get("disqualifying_generation_markers_found") is False, "source has generation markers")
    require(latest.get("generated_text_detected") is False, "source has generated text")
    require(latest.get("registered_runtime_changed") is False, "source must not have changed runtime")
    require(latest.get("runtime_ready_for_inference") is False, "source must not mark inference ready")


def check_fixture_approval_without_runtime_execution() -> None:
    module = load_module("engel_ai_llama_cpp_runtime_swap_approval_fixture", MODULE)
    with tempfile.TemporaryDirectory(prefix="engel_swap_approval_") as temp_text:
        temp = Path(temp_text)
        module.PROJECT_ROOT = temp
        module.REPORT_ROOT = temp / "reports" / "ai_llama_cpp_runtime_swap_approval"
        module.RECEIPT_DIR = module.REPORT_ROOT / "receipts"
        module.PLAN_REPORT_DIR = module.REPORT_ROOT / "reports"
        module.EXAMPLE_DIR = module.REPORT_ROOT / "examples"
        module.BACKUP_DIR = module.REPORT_ROOT / "backups"
        module.CODEX_REPORT = temp / "reports" / "codex_bridge" / "ENGEL_AI_LLAMA_CPP_RUNTIME_SWAP_APPROVAL_V1.md"
        module.RUNTIME_PATH_CONFIG_MANIFEST = temp / "reports" / "ai_runtime_path_config" / "manifests" / "engel_ai_local_runtime_path_config_manifest.json"
        module.ALT_RECEIPT_DIR = temp / "reports" / "ai_runtime_candidate_alt_command_style" / "receipts"
        module.APPROVED_CANDIDATE_ROOT = temp / "approved" / "candidates"
        module.CANDIDATE_FOLDER = module.APPROVED_CANDIDATE_ROOT / "llama-b9198-bin-win-cpu-x64"
        module.CANDIDATE_RUNTIME_BINARY = module.CANDIDATE_FOLDER / "llama-cli.exe"
        module.CANDIDATE_TOKENIZE_BINARY = module.CANDIDATE_FOLDER / "llama-tokenize.exe"
        module.CURRENT_REGISTERED_RUNTIME = temp / "old" / "llama-cli.exe"
        module.CANDIDATE_FOLDER.mkdir(parents=True)
        module.CANDIDATE_RUNTIME_BINARY.write_text("fixture cli", encoding="utf-8")
        module.CANDIDATE_TOKENIZE_BINARY.write_text("fixture tokenize", encoding="utf-8")
        (module.CANDIDATE_FOLDER / "llama-server.exe").write_text("fixture server", encoding="utf-8")
        (module.CANDIDATE_FOLDER / "rpc-server.exe").write_text("fixture rpc", encoding="utf-8")
        module.RUNTIME_PATH_CONFIG_MANIFEST.parent.mkdir(parents=True)
        previous_manifest = {
            "runtime_path_config_version": "1",
            "created_at": "2026-05-17T18:36:51Z",
            "runtime_backend": "llama_cpp",
            "runtime_binary_path": str(module.CURRENT_REGISTERED_RUNTIME),
            "runtime_binary_present": True,
            "runtime_path_approved": True,
            "runtime_execution_enabled": False,
            "model_load_enabled": False,
            "inference_enabled": False,
            "trusted_memory_write_enabled": False,
        }
        module.RUNTIME_PATH_CONFIG_MANIFEST.write_text(json.dumps(previous_manifest), encoding="utf-8")
        module.ALT_RECEIPT_DIR.mkdir(parents=True)
        alt_receipt = {
            "runtime_candidate_alt_command_style_version": "1",
            "selected_command_style": "llama_tokenize_ids_count",
            "alt_command_style_validation_passed": True,
            "candidate_runtime_ready_for_swap_review": True,
            "disqualifying_interactive_markers_found": False,
            "disqualifying_generation_markers_found": False,
            "generated_text_detected": False,
            "registered_runtime_changed": False,
            "runtime_ready_for_inference": False,
            "candidate_folder": str(module.CANDIDATE_FOLDER),
        }
        (module.ALT_RECEIPT_DIR / "RUNTIME_CANDIDATE_ALT_COMMAND_STYLE_20260518T000000Z_fixture.json").write_text(json.dumps(alt_receipt), encoding="utf-8")
        module.list_runtime_processes = lambda: []
        result = module.approve_runtime_swap(module.APPROVAL_TOKEN)
        require(result["runtime_swap_approval_recorded"] is True, "fixture approval was not recorded")
        require(result["registration_mode"] == "config_updated", "fixture should update clear config")
        require(result["registered_runtime_changed"] is True, "fixture should record runtime path change")
        require(result["candidate_runtime_binary_path"].endswith("llama-cli.exe"), "candidate runtime must be llama-cli")
        require("llama-server.exe" not in result["candidate_runtime_binary_path"].lower(), "server binary was selected")
        require(result["rollback_previous_runtime_path_recorded"] is True, "rollback previous path not recorded")
        require(Path(temp / result["rollback_metadata_path"]).exists(), "rollback metadata missing")
        updated_manifest = json.loads(module.RUNTIME_PATH_CONFIG_MANIFEST.read_text(encoding="utf-8"))
        require(str(updated_manifest["runtime_binary_path"]).endswith("llama-cli.exe"), "config did not point to candidate cli")
        require(updated_manifest["previous_registered_runtime_path"] == str(module.CURRENT_REGISTERED_RUNTIME), "previous runtime path not preserved")
        require(updated_manifest["first_local_response_smoke_allowed_next"] is True, "first smoke not allowed next")
        for key in [
            "runtime_process_started",
            "model_loaded",
            "inference_enabled",
            "chat_enabled",
            "server_enabled",
            "auto_load_enabled",
            "trusted_memory_write_enabled",
            "provider_api_enabled",
            "source_route_queue_mutation",
            "runtime_ready_for_inference",
        ]:
            require(result[key] is False, "fixture safety field must be false: " + key)


def check_latest_receipt_and_config_if_present() -> None:
    receipts = sorted(RECEIPTS.glob("RUNTIME_SWAP_APPROVAL_*.json"))
    if not receipts:
        return
    latest_text = read(receipts[-1])
    latest = json.loads(latest_text)
    require(latest.get("runtime_swap_approval_version") == "1", "latest approval receipt version mismatch")
    require(latest.get("approval_token_name") == "APPROVE_LLAMA_CPP_RUNTIME_SWAP", "approval token name mismatch")
    require(latest.get("approval_token_verified") is True, "approval token was not verified")
    require(latest.get("source_validation_style") == "llama_tokenize_ids_count", "source validation style mismatch")
    require(latest.get("source_validation_passed") is True, "source validation must pass")
    require(latest.get("approved_candidate_root") is True, "candidate root not approved")
    require(str(latest.get("candidate_runtime_binary_path", "")).endswith("llama-cli.exe"), "approved runtime must point to llama-cli")
    require("llama-server.exe" not in str(latest.get("candidate_runtime_binary_path", "")).lower(), "server binary selected")
    require(latest.get("server_binary_selected") is False, "server binary selected flag must be false")
    require(latest.get("runtime_process_started") is False, "runtime process must not start")
    require(latest.get("model_loaded") is False, "model must not load")
    require(latest.get("rollback_previous_runtime_path_recorded") is True, "rollback previous path not recorded")
    require(latest.get("first_local_response_smoke_allowed_next") is True, "first smoke should be allowed next")
    for key in [
        "inference_enabled",
        "chat_enabled",
        "server_enabled",
        "auto_load_enabled",
        "trusted_memory_write_enabled",
        "provider_api_enabled",
        "source_route_queue_mutation",
        "runtime_ready_for_inference",
    ]:
        require(latest.get(key) is False, "receipt safety field must be false: " + key)
    if latest.get("registration_mode") == "config_updated":
        manifest = json.loads(read(RUNTIME_PATH_CONFIG))
        require(manifest.get("runtime_binary_path") == latest.get("candidate_runtime_binary_path"), "config path mismatch")
        require(manifest.get("runtime_swap_approval_receipt") == latest.get("receipt_path"), "config missing approval receipt reference")
        require(manifest.get("previous_registered_runtime_path") == latest.get("previous_registered_runtime_path"), "config rollback path mismatch")
        require(manifest.get("inference_enabled") is False, "config inference must remain false")
        require(manifest.get("model_load_enabled") is False, "config model load must remain false")
        require(manifest.get("runtime_execution_enabled") is False, "config runtime execution must remain false")


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
    require("tools\\verify_engel_ai_llama_cpp_runtime_swap_approval.py" in codex, "codex verify missing swap approval verifier")
    readiness = read(READINESS)
    for needle in [
        "LLAMA_CPP_RUNTIME_SWAP_APPROVAL_RECEIPTS",
        "latest_llama_cpp_runtime_swap_approval",
        "first_local_response_smoke_allowed_next",
        "ENGEL_AI_LLAMA_CPP_RUNTIME_SWAP_APPROVAL_V1",
        "ENGEL_AI_FIRST_LOCAL_RESPONSE_SMOKE_V1",
    ]:
        require(needle in readiness, "readiness missing swap approval integration: " + needle)
    report = read(REPORT)
    for needle in [
        "ENGEL_AI_LLAMA_CPP_RUNTIME_SWAP_APPROVAL_V1",
        "Source Alt-Command-Style Validation Result",
        "Rollback metadata",
        "Runtime not executed",
        "Packaging skipped",
        "This phase approves a validated runtime candidate for controlled future smoke testing only.",
    ]:
        require(needle in report, "report missing required text: " + needle)


def main() -> int:
    try:
        check_files()
        check_static_safety()
        check_runtime_commands_and_tokens()
        check_source_alt_receipt()
        check_fixture_approval_without_runtime_execution()
        check_latest_receipt_and_config_if_present()
        check_docs_registration_and_readiness()
        check_downstream_verifiers()
    except CheckFailure as exc:
        print("ENGEL_AI_LLAMA_CPP_RUNTIME_SWAP_APPROVAL_VERIFY_FAIL")
        print(str(exc))
        return 1
    print("ENGEL_AI_LLAMA_CPP_RUNTIME_SWAP_APPROVAL_VERIFY_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
