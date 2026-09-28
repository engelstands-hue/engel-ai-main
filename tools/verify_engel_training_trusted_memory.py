from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "engel_training_trusted_memory.py"
APP = ROOT / "engel_app.py"
TARGET_CONTRACT_JSON = ROOT / "memory" / "ENGEL_TRUSTED_MEMORY_TARGET_CONTRACT_V1.json"
TARGET_CONTRACT_MD = ROOT / "memory" / "ENGEL_TRUSTED_MEMORY_TARGET_CONTRACT_V1.md"
DEFAULT_SOURCE = ROOT / "library_intake" / "Engel AI 4-Hour Local LLM Training Prompt"
TRUSTED_MEMORY = ROOT / "memory" / "ENGEL_TRUSTED_MEMORY_V1.jsonl"


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read(path: Path) -> str:
    require(path.exists() and path.is_file(), "missing required file: " + str(path.relative_to(ROOT)))
    return path.read_text(encoding="utf-8", errors="replace")


def load_module():
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location("engel_training_trusted_memory", MODULE)
    require(spec is not None and spec.loader is not None, "could not load training trusted-memory module")
    module = importlib.util.module_from_spec(spec)
    sys.modules["engel_training_trusted_memory"] = module
    spec.loader.exec_module(module)
    return module


def check_static_module() -> None:
    source = read(MODULE)
    tree = ast.parse(source)
    for needle in [
        "DEFAULT_PROMPT_PATH",
        "TRUSTED_MEMORY_PATH",
        "RECEIPT_ROOT",
        "DIRECT_HUMAN_REQUEST_TRAINING_PROMPT_TO_TRUSTED_MEMORY_20260521",
        "def build_entries(",
        "def write_direct_training_trusted_memory(",
        "def append_trusted_memory(",
        "def render_status(",
        "def render_preview(",
        "def render_write_result(",
        "TRUSTED_MEMORY_PATH.open(\"a\"",
        "engel_trusted_memory_target.validate_memory_entry",
    ]:
        require(needle in source, "module missing required text: " + needle)
    for forbidden in [
        "requests",
        "urllib",
        "socket",
        "webbrowser",
        "subprocess",
        "multiprocessing",
        "threading",
        "TRUSTED_MEMORY_PATH.write_text",
        "TRUSTED_MEMORY_PATH.open(\"w\"",
        "TRUSTED_MEMORY_PATH.unlink",
    ]:
        require(forbidden not in source, "module contains forbidden text: " + forbidden)
    forbidden_imports = {"requests", "urllib", "socket", "webbrowser", "subprocess", "threading", "multiprocessing", "shutil"}
    forbidden_calls = {"eval", "exec", "__import__", "Popen", "system", "run", "check_call", "check_output", "rglob", "glob", "walk", "unlink", "remove", "rename"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                require(alias.name.split(".")[0] not in forbidden_imports, "forbidden import: " + alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            require(node.module.split(".")[0] not in forbidden_imports, "forbidden import from: " + node.module)
        elif isinstance(node, ast.Call):
            func = node.func
            name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ""
            require(name not in forbidden_calls, "forbidden call: " + name)


def check_runtime_preview() -> None:
    module = load_module()
    require(DEFAULT_SOURCE.exists(), "default 4-hour training prompt missing")
    status = module.render_status()
    preview = module.render_preview()
    for text in [
        "READY / DIRECT_TRUSTED_MEMORY / APPEND_ONLY_JSONL",
        "training memory direct write",
        "No source edit",
        "No route mutation",
    ]:
        require(text in status + preview, "status/preview missing text: " + text)
    entries = module.build_entries(None, "PREVIEW_RECEIPT")
    require(len(entries) >= 10, "expected at least 10 trusted-memory entries from training prompt")
    memory_ids = {str(entry.get("memory_id")) for entry in entries}
    require(len(memory_ids) == len(entries), "memory IDs must be unique")
    for entry in entries:
        require(entry.get("status") == "trusted_promoted", "entry status must be trusted_promoted")
        require(entry.get("origin_type") == "local_training_prompt_direct_trusted_memory", "entry origin type mismatch")
        require("memory_text" in entry and str(entry["memory_text"]).strip(), "entry missing memory text")


def check_app_route() -> None:
    app = read(APP)
    for needle in [
        "import engel_training_trusted_memory as training_memory",
        "training memory status",
        "training memory preview",
        "training memory direct write",
        "training_memory.write_direct_training_trusted_memory",
    ]:
        require(needle in app, "engel_app missing route text: " + needle)


def check_contract_exception() -> None:
    data = json.loads(read(TARGET_CONTRACT_JSON))
    md = read(TARGET_CONTRACT_MD)
    exception = data.get("direct_training_memory_exception")
    require(isinstance(exception, dict), "target contract missing direct training exception")
    require(exception.get("status") == "enabled_by_direct_human_request", "exception status mismatch")
    require(exception.get("target_path") == "memory\\ENGEL_TRUSTED_MEMORY_V1.jsonl", "exception target path mismatch")
    require(exception.get("general_candidate_promotion_still_blocked") is True, "general promotion should remain blocked")
    for needle in [
        "Direct Training Memory Exception",
        "engel_training_trusted_memory.py",
        "enabled_by_direct_human_request",
        "general candidate promotion remains blocked",
    ]:
        require(needle in md, "target contract markdown missing: " + needle)


def check_existing_trusted_memory_file_if_present() -> None:
    if not TRUSTED_MEMORY.exists():
        return
    module = load_module()
    matched = 0
    for line in TRUSTED_MEMORY.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        require(isinstance(payload, dict), "trusted memory line must be JSON object")
        if payload.get("origin_type") == "local_training_prompt_direct_trusted_memory":
            module.engel_trusted_memory_target.validate_memory_entry(payload)
            matched += 1
    require(matched >= 1, "trusted memory file exists but no direct training trusted-memory entries were found")


def main() -> int:
    try:
        check_static_module()
        check_runtime_preview()
        check_app_route()
        check_contract_exception()
        check_existing_trusted_memory_file_if_present()
    except CheckFailure as exc:
        print("[FAIL]", exc)
        return 1
    print("[PASS] Engel training trusted-memory verifier passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
