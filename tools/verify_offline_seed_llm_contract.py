from __future__ import annotations

import ast
import json
import re
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
CONTRACT_PATH = ROOT / "memory" / "OFFLINE_SEED_LLM_CONTRACT_V1.json"
DESIGN_PATH = ROOT / "memory" / "ENGEL_OFFLINE_SEED_LLM_DESIGN_V1.md"
ROUTE_MATRIX_PATH = ROOT / "memory" / "ROUTE_VERIFICATION_SET_V1.json"
COMMANDS_PATH = ROOT / "memory" / "ENGEL_COMMANDS.md"
ADAPTER_PATH = ROOT / "engel_offline_seed_llm.py"
INSTALL_HELPER_PATH = ROOT / "tools" / "prepare_offline_seed_llm_folder.py"

FALSE_FLAGS = [
    "offline_llm_enabled",
    "model_runtime_enabled",
    "runtime_enabled_by_default",
    "provider_fallback_enabled",
    "network_download_enabled",
    "auto_download_enabled",
    "command_execution_from_model_enabled",
    "trusted_memory_write_from_model_enabled",
    "queue_mutation_from_model_enabled",
    "route_mutation_from_model_enabled",
    "source_edit_from_model_enabled",
    "applied_learning_from_model_enabled",
    "autonomy_from_model_enabled",
    "model_output_trusted",
]

STATUS_ROUTES = [
    "offline seed llm status",
    "offline llm status",
    "engel mind seed status",
]

RUNTIME_FORBIDDEN_PATTERNS = [
    ("requests_call", r"\brequests\."),
    ("http_url", r"http://"),
    ("https_url", r"https://"),
    ("socket", r"\bsocket\b"),
    ("websocket", r"\bwebsocket\b"),
    ("openai", r"\bopenai\b"),
    ("anthropic", r"\banthropic\b"),
    ("api_key", r"\bapi_key\b"),
    ("localhost_ollama", r"localhost:11434"),
    ("ollama", r"\bollama\b"),
    ("subprocess", r"\bsubprocess\b"),
    ("threading", r"\bthreading\b"),
    ("multiprocessing", r"\bmultiprocessing\b"),
    ("while_true", r"\bwhile\s+True\b"),
    ("start_process", r"\bStart-Process\b"),
    ("os_system", r"\bos\.system\b"),
    ("popen", r"\bPopen\b"),
]


class CheckFailure(Exception):
    pass


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _read_text(path: Path) -> str:
    if not path.exists():
        raise CheckFailure("missing required file: " + _rel(path))
    return path.read_text(encoding="utf-8", errors="replace")


def _load_json(path: Path) -> object:
    try:
        return json.loads(_read_text(path))
    except json.JSONDecodeError as exc:
        raise CheckFailure("invalid JSON in " + _rel(path) + ": " + str(exc)) from exc


def _normalize(text: str) -> str:
    return " ".join(text.lower().replace("\\", "/").replace("`", "").split())


def _require_text(text: str, needle: str, label: str) -> None:
    if _normalize(needle) not in _normalize(text):
        raise CheckFailure(label + " missing expected text: " + needle)


def _assert_contract(data: object) -> None:
    if not isinstance(data, dict):
        raise CheckFailure("contract must be a JSON object")
    if data.get("contract_id") != "OFFLINE_SEED_LLM_CONTRACT_V1":
        raise CheckFailure("contract_id mismatch")
    if data.get("status") != "env_gated_runtime_adapter_default_off":
        raise CheckFailure("contract status must be env_gated_runtime_adapter_default_off")
    for flag in FALSE_FLAGS:
        if data.get(flag) is not False:
            raise CheckFailure("contract flag must be false: " + flag)
    if data.get("runtime_env_var") != "ENGEL_OFFLINE_SEED_LLM_ENABLED":
        raise CheckFailure("contract runtime_env_var mismatch")
    if data.get("env_gated_runtime_adapter_available") is not True:
        raise CheckFailure("contract must expose env_gated_runtime_adapter_available=true")
    for flag in [
        "guardian_required",
        "companion_chat_only_initially",
        "explicit_user_approval_required_for_runtime",
        "manual_install_only",
        "no_hidden_network",
        "no_auto_download",
    ]:
        if data.get(flag) is not True:
            raise CheckFailure("contract flag must be true: " + flag)
    boundary = data.get("model_output_boundary")
    if not isinstance(boundary, dict):
        raise CheckFailure("contract missing model_output_boundary")
    if boundary.get("trust_level") != "untrusted":
        raise CheckFailure("model_output_boundary trust_level must be untrusted")
    for key in [
        "may_execute_commands",
        "may_write_memory",
        "may_mutate_queues",
        "may_mutate_routes",
        "may_edit_source",
        "may_apply_learning",
        "may_start_research",
        "may_browse_or_call_network",
    ]:
        if boundary.get(key) is not False:
            raise CheckFailure("model_output_boundary flag must be false: " + key)


def _assert_design_doc(text: str) -> None:
    for phrase in [
        "Qwen2.5-0.5B-Instruct GGUF",
        "Model output is untrusted companion text only.",
        "The command router remains deterministic",
        "Model output cannot issue commands",
        "Guardian must scan model output",
        "Local GGUF inference is available only when `ENGEL_OFFLINE_SEED_LLM_ENABLED=1`",
        "Known commands, unsafe requests, and command-like unknowns must never be sent to the model.",
        "Fine-tuning, adaptation, embeddings, retrieval augmentation, and trusted-memory integration are separate future designs and are not enabled now.",
    ]:
        _require_text(text, phrase, "design doc")


def _assert_routes(matrix: object, commands_text: str) -> None:
    if not isinstance(matrix, dict):
        raise CheckFailure("route matrix must be a JSON object")
    entries = matrix.get("route_regression_matrix_entries")
    if not isinstance(entries, list):
        raise CheckFailure("route matrix missing route_regression_matrix_entries")
    entry_map = {str(entry.get("command")): entry for entry in entries if isinstance(entry, dict)}
    for route in STATUS_ROUTES:
        if route not in entry_map:
            raise CheckFailure("route matrix missing status route: " + route)
        entry = entry_map[route]
        if entry.get("implemented_now") is not True:
            raise CheckFailure("route must be implemented_now true: " + route)
        if entry.get("expected_behavior") != "READ_ONLY_STATUS_ONLY_NO_WRITE":
            raise CheckFailure("route expected_behavior mismatch: " + route)
        for flag in [
            "runtime_enabled",
            "runtime_enabled_by_default",
            "provider_fallback_enabled",
            "network_download_enabled",
            "auto_download_enabled",
            "command_execution_from_model_enabled",
            "trusted_memory_write_from_model_enabled",
            "queue_mutation_from_model_enabled",
            "route_mutation_from_model_enabled",
            "source_edit_from_model_enabled",
            "applied_learning_from_model_enabled",
            "autonomy_from_model_enabled",
        ]:
            if entry.get(flag) is not False:
                raise CheckFailure("route flag must be false for " + route + ": " + flag)
        if entry.get("runtime_env_var") != "ENGEL_OFFLINE_SEED_LLM_ENABLED":
            raise CheckFailure("route runtime_env_var mismatch: " + route)
        if entry.get("env_gated_runtime_adapter_available") is not True:
            raise CheckFailure("route must expose env-gated adapter availability: " + route)
        _require_text(commands_text, route, "ENGEL_COMMANDS")


def _assert_no_runtime_patterns(path: Path, label: str) -> None:
    text = _read_text(path)
    for name, pattern in RUNTIME_FORBIDDEN_PATTERNS:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            raise CheckFailure(label + " contains forbidden runtime pattern " + name + ": " + match.group(0))


def _assert_adapter_static() -> None:
    source = _read_text(ADAPTER_PATH)
    tree = ast.parse(source)
    blocked_imports = {
        "requests",
        "socket",
        "subprocess",
        "threading",
        "multiprocessing",
        "openai",
        "anthropic",
        "websocket",
    }
    blocked_calls = {"eval", "exec", "compile", "__import__"}
    top_level_blocked_imports = {"llama_cpp"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in blocked_imports:
                    raise CheckFailure("adapter imports blocked module: " + alias.name)
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if root in blocked_imports:
                raise CheckFailure("adapter imports from blocked module: " + str(node.module))
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in blocked_calls:
                raise CheckFailure("adapter calls blocked builtin: " + func.id)
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in top_level_blocked_imports:
                    raise CheckFailure("adapter has top-level local runtime import: " + alias.name)
        elif isinstance(node, ast.ImportFrom):
            if (node.module or "").split(".")[0] in top_level_blocked_imports:
                raise CheckFailure("adapter has top-level local runtime import: " + str(node.module))
    _assert_no_runtime_patterns(ADAPTER_PATH, "adapter")
    for required in [
        "def render_offline_seed_llm_status",
        "def offline_seed_llm_gate_enabled",
        "def guardian_filter_model_output",
        "def run_offline_seed_llm_for_companion_chat",
        "def build_guarded_companion_prompt",
        "def sanitize_model_output_as_untrusted",
        "ENGEL_OFFLINE_SEED_LLM_ENABLED",
        "from llama_cpp import Llama",
    ]:
        _require_text(source, required, "adapter")


def _assert_installer_static() -> None:
    source = _read_text(INSTALL_HELPER_PATH)
    _assert_no_runtime_patterns(INSTALL_HELPER_PATH, "install helper")
    for phrase in [
        "did not download anything",
        "No download, package install, runtime config write, inference, provider call, or network call was performed.",
        "MODEL_DIR.mkdir",
    ]:
        _require_text(source, phrase, "install helper")


def _run() -> list[str]:
    results: list[str] = []
    contract = _load_json(CONTRACT_PATH)
    _assert_contract(contract)
    results.append("PASS contract_json_and_disabled_flags")

    _assert_design_doc(_read_text(DESIGN_PATH))
    results.append("PASS design_doc_safety_boundary")

    _assert_adapter_static()
    results.append("PASS adapter_env_gated_no_top_level_runtime_imports")

    _assert_installer_static()
    results.append("PASS installer_manual_only_no_download")

    _assert_routes(_load_json(ROUTE_MATRIX_PATH), _read_text(COMMANDS_PATH))
    results.append("PASS route_metadata_and_command_docs")

    return results


def main() -> int:
    try:
        for line in _run():
            print(line)
        print()
        print("OFFLINE_SEED_LLM_CONTRACT_VERIFICATION_PASS")
        return 0
    except CheckFailure as exc:
        print("OFFLINE_SEED_LLM_CONTRACT_VERIFICATION_FAIL")
        print(str(exc))
        return 1


if __name__ == "__main__":
    sys.exit(main())
