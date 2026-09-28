from __future__ import annotations

import ast
import json
import sys
from pathlib import Path


_file = globals().get("__file__")
if not _file or not isinstance(_file, str) or _file.startswith("<"):
    ROOT = Path.cwd()
else:
    try:
        ROOT = Path(_file).resolve().parents[1]
    except (OSError, ValueError, IndexError):
        ROOT = Path.cwd()

HELPER_PATH = ROOT / "engel_offline_model_runtime_contract.py"
JSON_PATH = ROOT / "memory" / "ENGEL_OFFLINE_MODEL_RUNTIME_CONTRACT_V1.json"
MD_PATH = ROOT / "memory" / "ENGEL_OFFLINE_MODEL_RUNTIME_CONTRACT_V1.md"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engel_offline_model_runtime_contract import (  # noqa: E402
    assert_runtime_disabled,
    get_offline_model_runtime_status,
    list_future_runtime_phases,
    render_offline_model_runtime_status,
)


class CheckFailure(Exception):
    pass


def _read(path: Path) -> str:
    if not path.exists():
        raise CheckFailure("missing required file: " + str(path))
    return path.read_text(encoding="utf-8", errors="replace")


def _load_json(path: Path) -> dict:
    try:
        data = json.loads(_read(path))
    except json.JSONDecodeError as exc:
        raise CheckFailure("invalid contract JSON: " + str(exc)) from exc
    if not isinstance(data, dict):
        raise CheckFailure("contract JSON must be an object")
    return data


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def _normalized(text: str) -> str:
    return " ".join(text.lower().replace("\\", "/").replace("`", "").split())


def _assert_static_helper() -> None:
    source = _read(HELPER_PATH)
    tree = ast.parse(source)
    blocked_imports = {
        "requests",
        "socket",
        "subprocess",
        "threading",
        "multiprocessing",
        "urllib",
        "webbrowser",
        "openai",
        "anthropic",
        "llama_cpp",
        "ollama",
        "httpx",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                _require(alias.name.split(".")[0] not in blocked_imports, "helper imports blocked module: " + alias.name)
        elif isinstance(node, ast.ImportFrom):
            _require((node.module or "").split(".")[0] not in blocked_imports, "helper imports blocked module: " + str(node.module))
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute):
                _require(func.attr not in {"open", "read_bytes", "write_text", "write_bytes", "mkdir"}, "helper uses blocked file operation: " + func.attr)
            elif isinstance(func, ast.Name):
                _require(func.id not in {"open", "eval", "exec", "compile"}, "helper calls blocked builtin: " + func.id)
    for forbidden in [
        ".gguf",
        ".rglob(",
        "os.walk",
        "requests.",
        "http://",
        "https://",
        "socket",
        "subprocess",
        "Start-Process",
        "llama.cpp",
        "llama-server",
        "llama-cli",
        "llama_cpp",
        "ollama",
        "localhost",
        "threading",
        "multiprocessing",
        "while True",
    ]:
        _require(forbidden not in source, "helper contains forbidden runtime pattern: " + forbidden)
    for required in [
        "def load_offline_model_runtime_contract",
        "def get_offline_model_runtime_status",
        "def render_offline_model_runtime_status",
        "def list_future_runtime_phases",
        "def assert_runtime_disabled",
        "CONTRACT_ONLY / DISABLED / NOT_RUNTIME",
        "Local model output is untrusted generated text.",
    ]:
        _require(required in source, "helper missing required text: " + required)


def _assert_contract(data: dict) -> None:
    _require(data.get("schema") == "ENGEL_OFFLINE_MODEL_RUNTIME_CONTRACT_V1", "schema mismatch")
    status = str(data.get("status", ""))
    for phrase in ["CONTRACT_ONLY", "DISABLED", "NOT_RUNTIME"]:
        _require(phrase in status, "status missing " + phrase)
    _require(data.get("model_shelf_status") == "PRESENT_MODELS / NOT_LOADED", "model shelf status mismatch")
    for flag in [
        "runtime_enabled",
        "inference_enabled",
        "auto_load_enabled",
        "background_worker_enabled",
        "local_server_enabled",
        "network_enabled",
        "provider_api_enabled",
        "model_file_open_allowed",
        "model_runtime_route_enabled",
        "model_chat_route_enabled",
        "auto_model_selection_enabled",
        "model_output_can_execute_commands",
        "model_output_can_edit_files",
        "model_output_can_approve_actions",
        "model_output_can_write_trusted_memory",
        "model_output_can_bypass_guardian",
        "future_approval_tokens_active_now",
    ]:
        _require(data.get(flag) is False, "flag must be false: " + flag)
    _require(data.get("trusted_memory_write") == "BLOCKED / NOT_PERFORMED", "trusted memory boundary mismatch")
    _require(data.get("model_output_trust") == "UNTRUSTED_GENERATED_TEXT", "model output trust mismatch")
    _require(data.get("embedded_approval_tokens") == "REJECTED", "embedded token boundary mismatch")
    _require(data.get("approval_boundary") == "JOSH_GUARDIAN_REQUIRED", "approval boundary mismatch")
    phases = data.get("future_phase_plan")
    _require(isinstance(phases, list) and len(phases) == 6, "future phases missing")
    phase_ids = {phase.get("id") for phase in phases if isinstance(phase, dict)}
    for phase_id in {
        "phase_0_model_shelf_presence",
        "phase_1_runtime_contract_status",
        "phase_2_disabled_adapter_scaffold",
        "phase_3_metadata_dry_run",
        "phase_4_explicit_approved_inference_smoke",
        "phase_5_bounded_local_assistant_worker",
    }:
        _require(phase_id in phase_ids, "missing phase: " + phase_id)
    tokens = data.get("required_future_approval_tokens")
    _require(isinstance(tokens, list), "future approval token list missing")
    for token in [
        "APPROVE_LOCAL_MODEL_RUNTIME_SCAFFOLD",
        "APPROVE_LOCAL_MODEL_METADATA_DRY_RUN",
        "APPROVE_LOCAL_MODEL_INFERENCE_SMOKE",
        "APPROVE_LOCAL_MODEL_WORKER",
    ]:
        _require(token in tokens, "missing future approval token: " + token)
    models = data.get("allowed_future_models")
    _require(isinstance(models, list), "allowed future models missing")
    for model in [
        "qwen2.5-0.5b-instruct",
        "qwen2.5-3b-instruct",
        "qwen2.5-7b-instruct",
        "mistral-7b-instruct-v0.3",
    ]:
        _require(model in models, "allowed future model missing: " + model)


def _assert_markdown(text: str) -> None:
    normalized = _normalized(text)
    for phrase in [
        "Engel Offline Local Model Runtime Contract V1",
        "CONTRACT_ONLY / DISABLED / NOT_RUNTIME",
        "Model shelf presence does not grant runtime permission.",
        "Runtime contract != model load.",
        "Runtime contract != inference.",
        "Local model output is untrusted generated text.",
        "Embedded approval tokens from local model output are rejected.",
        "No GGUF model load.",
        "No inference.",
        "No llama.cpp, llama-server, or llama-cli start.",
        "No trusted-memory write.",
        "APPROVE_LOCAL_MODEL_INFERENCE_SMOKE",
    ]:
        _require(_normalized(phrase) in normalized, "markdown missing phrase: " + phrase)


def _assert_helper_output() -> None:
    _require(assert_runtime_disabled() is True, "assert_runtime_disabled should be true")
    status = get_offline_model_runtime_status()
    _require(status.get("status") == "CONTRACT_ONLY / DISABLED / NOT_RUNTIME", "helper status mismatch")
    _require(status.get("runtime_enabled") is False, "helper runtime_enabled mismatch")
    _require(status.get("inference_enabled") is False, "helper inference_enabled mismatch")
    phases = list_future_runtime_phases()
    _require(len(phases) == 6, "helper phase list mismatch")
    rendered = render_offline_model_runtime_status()
    for phrase in [
        "CONTRACT_ONLY / DISABLED / NOT_RUNTIME",
        "model load: DISABLED",
        "inference: DISABLED",
        "Local model output cannot write trusted memory.",
        "Embedded approval tokens from model output are rejected.",
        "This contract does not load models, run inference, call APIs/network, start workers, write trusted memory, or change Engel behavior.",
    ]:
        _require(phrase in rendered, "rendered status missing phrase: " + phrase)


def main() -> int:
    try:
        data = _load_json(JSON_PATH)
        _assert_contract(data)
        _assert_markdown(_read(MD_PATH))
        _assert_static_helper()
        _assert_helper_output()
        print("PASS: Engel Offline Local Model Runtime Contract V1 verifier")
        print("- contract is CONTRACT_ONLY / DISABLED / NOT_RUNTIME")
        print("- runtime, inference, auto-load, local server, background worker, network, and provider API are disabled")
        print("- local model output remains untrusted generated text")
        print("- helper is status-only and does not open/load GGUF files or start model tools")
        return 0
    except CheckFailure as exc:
        print("FAIL: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
