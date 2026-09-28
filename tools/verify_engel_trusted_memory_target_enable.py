from __future__ import annotations

import ast
import importlib.util
import io
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "engel_trusted_memory_target_enable.py"
TARGET_MODULE = ROOT / "engel_trusted_memory_target.py"
REGISTRY = ROOT / "engel_protected_action_registry.py"
TARGET_CONTRACT = ROOT / "memory" / "ENGEL_TRUSTED_MEMORY_TARGET_CONTRACT_V1.json"

PASS_MARKER = "ENGEL_TRUSTED_MEMORY_TARGET_ENABLE_VERIFICATION_PASS"
ACTION_ID = "enable_trusted_memory_target"
APPROVAL_PHRASE = "APPROVE_TRUSTED_MEMORY_TARGET_ENABLE_V1"

FORBIDDEN_IMPORTS = {
    "requests",
    "urllib",
    "socket",
    "webbrowser",
    "openai",
    "threading",
    "multiprocessing",
    "chromadb",
    "faiss",
    "llama",
    "ollama",
}


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def load_module(path: Path, name: str):
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location(name, path)
    require(spec is not None and spec.loader is not None, "could not load module: " + name)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def check_files() -> None:
    for path in [MODULE, TARGET_MODULE, REGISTRY, TARGET_CONTRACT]:
        require(path.exists() and path.is_file(), "missing required file: " + str(path.relative_to(ROOT)))


def check_static_safety() -> None:
    source = read(MODULE)
    tree = ast.parse(source)
    for needle in [
        APPROVAL_PHRASE,
        ACTION_ID,
        "--enable",
        "--password-prompt",
        "redacted_pass",
        "trusted_memory_entry_written: false",
        "APPROVE_PROMOTE_MEMORY_CANDIDATE"[:8],
    ]:
        require(needle in source, "target enable module missing text: " + needle)
    require("--password " not in source and "--password=" not in source, "target enable module must not accept password argument")
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                require(alias.name.split(".")[0] not in FORBIDDEN_IMPORTS, "forbidden import: " + alias.name)
        if isinstance(node, ast.ImportFrom) and node.module:
            require(node.module.split(".")[0] not in FORBIDDEN_IMPORTS, "forbidden import: " + node.module)
        if isinstance(node, ast.While):
            raise CheckFailure("target enable module contains while loop")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            require(node.func.id not in {"eval", "exec", "__import__"}, "dynamic execution call found")


def check_registry_action() -> None:
    registry = load_module(REGISTRY, "engel_protected_action_registry")
    action = registry.get_action(ACTION_ID)
    require(isinstance(action, dict), "registry missing target enable action")
    require(action.get("password_required") is True, "target enable action must require password")
    require(action.get("approval_token_required") is True, "target enable action must require approval phrase/token")
    require(action.get("contract_required") is True, "target enable action must require contract")
    require(action.get("verifier_required") is True, "target enable action must require verifier")
    require(action.get("receipt_required") is True, "target enable action must require receipt")
    require(action.get("risk_level") == "high", "target enable action must be high risk")


def check_target_contract_state() -> None:
    data = json.loads(read(TARGET_CONTRACT))
    target = data.get("target", {})
    require(isinstance(target, dict), "target object missing")
    require(target.get("target_path") == "memory\\ENGEL_TRUSTED_MEMORY_V1.jsonl", "target path mismatch")
    require(target.get("target_format") == "jsonl", "target format mismatch")
    require(target.get("allowed_write_mode") == "append_only", "target write mode mismatch")
    if target.get("enabled") is True:
        require(target.get("status") == "enabled_for_password_gated_candidate_promotion", "enabled target status mismatch")
        receipt = str(target.get("enablement_receipt_path", ""))
        require(receipt.startswith("reports\\memory_promotion_receipts\\"), "enabled target receipt path mismatch")
        require((ROOT / receipt).exists(), "enabled target receipt is missing")
    else:
        require(target.get("enabled") is False, "target enabled flag must be boolean")
        require(target.get("status") == "disabled_until_human_target_approval", "disabled target status mismatch")


def check_runtime_smoke() -> None:
    module = load_module(MODULE, "engel_trusted_memory_target_enable")
    out = io.StringIO()
    err = io.StringIO()
    require(module.main(["--status"], stdout=out, stderr=err) == 0, "status smoke failed")
    payload = json.loads(out.getvalue())
    require(payload.get("writes_memory_entries") is False, "status must confirm no memory entry writes")

    out = io.StringIO()
    err = io.StringIO()
    require(module.main(["--enable", "WRONG_PHRASE", "--password-prompt"], stdout=out, stderr=err) == 2, "wrong phrase did not fail closed")
    require("exact target-enable approval phrase required" in err.getvalue(), "wrong phrase rejection missing")

    out = io.StringIO()
    err = io.StringIO()
    require(module.main(["--enable", APPROVAL_PHRASE], stdout=out, stderr=err) == 2, "missing password prompt did not fail closed")
    require("requires --password-prompt" in err.getvalue(), "missing password prompt rejection missing")


def check_target_runtime_compatible() -> None:
    target_module = load_module(TARGET_MODULE, "engel_trusted_memory_target")
    payload = target_module.status_payload()
    require(payload["target"]["target_path"] == "memory\\ENGEL_TRUSTED_MEMORY_V1.jsonl", "target runtime path mismatch")
    require(payload["target"]["target_format"] == "jsonl", "target runtime format mismatch")
    require(payload["target"]["append_only"] is True, "target runtime append_only mismatch")


def main() -> int:
    try:
        check_files()
        check_static_safety()
        check_registry_action()
        check_target_contract_state()
        check_runtime_smoke()
        check_target_runtime_compatible()
    except CheckFailure as exc:
        print("[FAIL]", exc)
        return 1
    print("[PASS] Engel trusted-memory target enable implementation verifier passed.")
    print(PASS_MARKER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
