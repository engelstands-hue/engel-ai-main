from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "engel_global_password_gate.py"
REGISTRY = ROOT / "engel_protected_action_registry.py"
CONFIG = ROOT / "memory" / "ENGEL_GLOBAL_PASSWORD_GATE_V1.json"
TEMPLATE = ROOT / "memory" / "ENGEL_GLOBAL_PASSWORD_GATE_TEMPLATE_V1.json"
VERIFIER = ROOT / "tools" / "verify_engel_global_password_gate.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_GLOBAL_PASSWORD_GATED_ACTION_LAYER_V1.md"
TEMP_CONFIG = ROOT / "reports" / "temp_password_gate_tests" / "verifier_global_password_gate.json"

REQUIRED_STATUS_LABELS = [
    "GLOBAL_PASSWORD_GATED_ACTION_LAYER",
    "LOCAL_ONLY",
    "PASSWORD_REQUIRED_FOR_PROTECTED_ACTIONS",
    "PASSWORD_HASH_ONLY",
    "NO_PLAINTEXT_PASSWORD_STORAGE",
    "NO_DEFAULT_PASSWORD",
    "NO_PASSWORD_LOGGING",
    "CANONICALIZE_BEFORE_VALIDATE",
    "NORMALIZE_UNICODE_INPUTS",
    "STRICT_ACTION_ALLOWLIST",
    "BLOCK_INJECTION_STYLE_BYPASS",
    "BLOCK_UNICODE_ENCODING_BYPASS",
    "BLOCK_PROMPT_INJECTION_UNLOCK",
    "BLOCK_APPROVE_ALL_PATTERN",
    "ACTION_SPECIFIC_CONTRACTS_STILL_REQUIRED",
    "AUTHORITY_HIERARCHY_STILL_REQUIRED",
    "GUARDS_STILL_REQUIRED",
    "RECEIPTS_REQUIRED_FOR_WRITES",
    "DRY_RUN_BEFORE_APPLY",
    "STOP_ON_HIGH_RISK",
    "STOP_ON_UNCLEAR_RISK",
    "FAIL_CLOSED_ON_CONFIG_ERROR",
    "FAIL_CLOSED_ON_UNKNOWN_ACTION",
    "NO_PROVIDER_CALLS",
    "NO_NETWORK",
    "NO_BROWSER",
    "NO_MODEL_RUNTIME",
    "NO_BACKGROUND_WORKER",
    "NO_STARTUP_AUTORUN",
    "NO_SAFETY_BYPASS",
]

FORBIDDEN_IMPORTS = {
    "requests",
    "urllib",
    "socket",
    "webbrowser",
    "openai",
    "subprocess",
    "threading",
    "multiprocessing",
    "chromadb",
    "faiss",
    "llama",
    "ollama",
}

FORBIDDEN_CONFIG_KEYS = {
    "plaintext_password",
    "password",
    "raw_password",
    "default_password",
    "recovery_password",
    "password_hint_with_secret",
    "bypass_token",
    "token_that_bypasses_password",
    "master_key",
    "admin_password",
}


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def load_gate():
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location("engel_global_password_gate", GATE)
    require(spec is not None and spec.loader is not None, "could not load global password gate")
    module = importlib.util.module_from_spec(spec)
    sys.modules["engel_global_password_gate"] = module
    spec.loader.exec_module(module)
    return module


def cleanup_temp_config() -> None:
    if TEMP_CONFIG.exists():
        TEMP_CONFIG.unlink()
    try:
        TEMP_CONFIG.parent.rmdir()
    except OSError:
        pass


def check_files_exist() -> None:
    for path in [GATE, REGISTRY, CONFIG, TEMPLATE, VERIFIER]:
        require(path.exists() and path.is_file(), "required file missing: " + str(path.relative_to(ROOT)))


def check_required_text() -> None:
    text = read(GATE)
    for label in REQUIRED_STATUS_LABELS:
        require(label in text, "global password gate missing status label: " + label)
    for needle in [
        "hashlib.pbkdf2_hmac",
        "hmac.compare_digest",
        "secrets.token_bytes",
        "getpass.getpass",
        "unicodedata.normalize",
        "^[a-z][a-z0-9_]{1,127}$",
        "canonicalize_action_id",
        "is_safe_action_id",
        "reject_injection_style_action_id",
        "require_registered_action",
        "require_password_for_action",
        "protected_action_gate_summary",
        "--status",
        "--setup",
        "--verify",
        "--change",
        "--config",
        "Global password gate is not configured. Run: python engel_global_password_gate.py --setup",
    ]:
        require(needle in text, "global password gate missing required text: " + needle)
    require("--password " not in text and "--password=" not in text, "global gate accepts password on command line")


def check_config_file() -> None:
    data = json.loads(CONFIG.read_text(encoding="utf-8"))
    require(isinstance(data, dict), "password gate config is not an object")
    for key in FORBIDDEN_CONFIG_KEYS:
        require(key not in data, "password gate config contains forbidden key: " + key)
    for key in ["configured", "algorithm", "salt", "password_hash", "iterations", "status_labels"]:
        require(key in data, "password gate config missing allowed storage key: " + key)
    committed = load_committed_config_template()
    require(committed.get("configured") is False, "committed password gate template should be unconfigured")
    require(committed.get("password_hash") == "" and committed.get("salt") == "", "committed template must not include active hash metadata")
    if data["configured"] is False:
        require(data["password_hash"] == "" and data["salt"] == "", "unconfigured worktree config must not include active hash metadata")
        return
    require(data["configured"] is True, "password gate configured flag must be boolean")
    require_configured_hash_metadata(data)


def load_committed_config_template() -> dict:
    data = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    require(isinstance(data, dict), "committed password gate template is not an object")
    for key in FORBIDDEN_CONFIG_KEYS:
        require(key not in data, "committed password gate template contains forbidden key: " + key)
    return data


def require_configured_hash_metadata(data: dict) -> None:
    require(data.get("algorithm") == "PBKDF2-HMAC-SHA256", "configured local password gate algorithm mismatch")
    iterations = data.get("iterations")
    require(isinstance(iterations, int) and iterations >= 200_000, "configured local password gate iterations too low")
    for key, expected_length in [("salt", 64), ("password_hash", 64)]:
        value = data.get(key)
        require(isinstance(value, str) and len(value) == expected_length, "configured local password gate metadata is malformed")
        try:
            bytes.fromhex(value)
        except ValueError as exc:
            raise CheckFailure("configured local password gate metadata is malformed") from exc


def check_ast_safety() -> None:
    tree = ast.parse(read(GATE))
    forbidden_names = {"exec", "eval", "__import__"}
    forbidden_attrs = {"walk", "rglob", "glob", "startfile"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                require(alias.name.split(".")[0] not in FORBIDDEN_IMPORTS, "global gate imports forbidden module: " + alias.name)
        if isinstance(node, ast.ImportFrom) and node.module:
            require(node.module.split(".")[0] not in FORBIDDEN_IMPORTS, "global gate imports forbidden module: " + node.module)
        if isinstance(node, ast.While):
            raise CheckFailure("global gate contains while loop")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            require(node.func.id not in forbidden_names, "global gate uses forbidden dynamic execution call: " + node.func.id)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            require(node.func.attr not in forbidden_attrs, "global gate uses forbidden scan/start call: " + node.func.attr)


def check_runtime_smoke() -> None:
    gate = load_gate()
    status = gate.render_status()
    for needle in [
        "GLOBAL_PASSWORD_GATED_ACTION_LAYER",
        "Password protects actions; it does not bypass safety.",
        "Blocked actions remain blocked even with password.",
        "Action IDs use strict allowlists and canonicalization.",
    ]:
        require(needle in status, "status smoke missing: " + needle)

    cleanup_temp_config()
    test_secret = "Verifier passphrase only"
    config = gate.build_password_gate_config(test_secret, created_at="2026-05-15T00:00:00Z")
    gate.write_password_gate_config(config, TEMP_CONFIG.relative_to(ROOT))
    require(gate.is_global_password_gate_configured(TEMP_CONFIG.relative_to(ROOT)), "temp config was not configured")
    require(gate.verify_global_password(test_secret, TEMP_CONFIG.relative_to(ROOT)), "temp password did not verify")
    require(not gate.verify_global_password("wrong verifier phrase", TEMP_CONFIG.relative_to(ROOT)), "wrong password verified")
    try:
        gate.require_password_for_action("enable_network", test_secret, TEMP_CONFIG.relative_to(ROOT))
    except gate.PasswordGateError as exc:
        require("blocked" in str(exc).lower(), "blocked action refusal did not mention blocked")
    else:
        raise CheckFailure("blocked action was allowed")

    require(gate.is_safe_action_id("run_code_companion_low_risk_patch_apply"), "registered action id failed safety check")
    require(
        gate.canonicalize_action_id(" run_code_companion_low_risk_patch_apply ") == "run_code_companion_low_risk_patch_apply",
        "leading/trailing whitespace did not normalize to registered action id",
    )
    malformed_ids = [
        "run code companion",
        "run/code/companion",
        "bad%encoded",
        "bad'action",
        "bad--comment",
        "Ａction",
        "approve all",
        "unlock all",
        "x" * 140,
        "http://action",
    ]
    for action_id in malformed_ids:
        require(not gate.is_safe_action_id(action_id), "malformed action id was accepted")
    cleanup_temp_config()


def check_report_if_present() -> None:
    if not REPORT.exists():
        return
    text = read(REPORT)
    for needle in [
        "Engel Global Password-Gated Action Layer V1",
        "password hashing/storage approach",
        "input normalization and injection-bypass protection approach",
        "protected action registry summary",
        "password gate does not bypass contracts/verifiers/authority/guards",
        "blocked actions remain blocked",
        "offensive SQLi/bypass content from reference images was not copied",
    ]:
        require(needle in text, "global password report missing text: " + needle)


def main() -> int:
    try:
        check_files_exist()
        check_required_text()
        check_config_file()
        check_ast_safety()
        check_runtime_smoke()
        check_report_if_present()
    except CheckFailure as exc:
        cleanup_temp_config()
        print("[FAIL]", exc)
        return 1
    cleanup_temp_config()
    print("[PASS] Engel global password gate verifier passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
