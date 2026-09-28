from __future__ import annotations

import argparse
from datetime import datetime, timezone
import getpass
import hashlib
import hmac
import json
from pathlib import Path
import re
import secrets
import sys
import textwrap
import unicodedata

import engel_protected_action_registry as protected_action_registry


PROJECT_ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "memory" / "ENGEL_GLOBAL_PASSWORD_GATE_V1.json"
TEST_CONFIG_ROOT = PROJECT_ROOT / "reports" / "temp_password_gate_tests"
ALGORITHM = "PBKDF2-HMAC-SHA256"
HASH_NAME = "sha256"
MIN_ITERATIONS = 200_000
DEFAULT_ITERATIONS = 260_000
MIN_PASSWORD_LENGTH = 12
PASSWORD_CANONICALIZATION = "NFKC"
ACTION_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]{1,127}$")

STATUS_LABELS = [
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

ALLOWED_CONFIG_KEYS = {
    "schema_version",
    "configured",
    "algorithm",
    "salt",
    "password_hash",
    "password_canonicalization",
    "iterations",
    "created_at",
    "updated_at",
    "status_labels",
    "config_note",
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

QUOTE_OR_COMMENT_MARKERS = ('"', "'", "`", ";", "--", "/*", "*/", "#")
METACHARACTERS = set("|&$<>=!?")
BRACKET_OR_PATH_MARKERS = set("()[]{}\\/")
ENCODING_OR_URL_MARKERS = ("%", "+", "://")
PROMPT_UNLOCK_PHRASES = (
    "bypass",
    "approve all",
    "unlock all",
    "ignore previous instructions",
    "disable safety",
    "grant full access",
)


class PasswordGateError(ValueError):
    pass


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
    except ValueError:
        return False
    return True


def resolve_config_path(raw_path: str | Path | None = None) -> Path:
    if raw_path is None or str(raw_path).strip() == "":
        return DEFAULT_CONFIG_PATH
    raw_text = str(raw_path).strip()
    candidate = Path(raw_text)
    if candidate.is_absolute():
        resolved_absolute = candidate.resolve(strict=False)
        if resolved_absolute == DEFAULT_CONFIG_PATH.resolve(strict=False):
            return resolved_absolute
        if not is_relative_to(resolved_absolute, TEST_CONFIG_ROOT.resolve(strict=False)):
            raise PasswordGateError("Custom password gate config path must be project-local test/dev path.")
        resolved = resolved_absolute
    else:
        resolved = (PROJECT_ROOT / candidate).resolve(strict=False)
    root = PROJECT_ROOT.resolve()
    if not is_relative_to(resolved, root):
        raise PasswordGateError("Custom password gate config path must stay inside the project.")
    relative_parts = [part.lower() for part in resolved.relative_to(root).parts]
    if len(relative_parts) < 3 or relative_parts[0] != "reports" or relative_parts[1] != "temp_password_gate_tests":
        raise PasswordGateError("Custom config path is limited to reports\\temp_password_gate_tests\\*.json.")
    if any(part in {"live", "staging", "model", "models", "hf", "ollama", "package", "packages"} for part in relative_parts):
        raise PasswordGateError("Custom config path may not point at package, live, staging, or model folders.")
    if resolved.suffix.lower() != ".json":
        raise PasswordGateError("Custom password gate config must be a JSON file.")
    return resolved


def _default_unconfigured_config() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "configured": False,
        "algorithm": ALGORITHM,
        "salt": "",
        "password_hash": "",
        "password_canonicalization": PASSWORD_CANONICALIZATION,
        "iterations": DEFAULT_ITERATIONS,
        "created_at": "",
        "updated_at": "",
        "status_labels": list(STATUS_LABELS),
        "config_note": "Local hash metadata only. No secret is displayed by status commands.",
    }


def _validate_hex_field(name: str, value: object, expected_min_bytes: int) -> None:
    if not isinstance(value, str) or not value:
        raise PasswordGateError("Password gate config is invalid.")
    try:
        decoded = bytes.fromhex(value)
    except ValueError as exc:
        raise PasswordGateError("Password gate config is invalid.") from exc
    if len(decoded) < expected_min_bytes:
        raise PasswordGateError("Password gate config is invalid.")


def _validate_config(data: object) -> dict[str, object]:
    if not isinstance(data, dict):
        raise PasswordGateError("Password gate config is invalid.")
    keys = set(data.keys())
    forbidden = keys.intersection(FORBIDDEN_CONFIG_KEYS)
    if forbidden:
        raise PasswordGateError("Password gate config is invalid.")
    unknown = keys.difference(ALLOWED_CONFIG_KEYS)
    if unknown:
        raise PasswordGateError("Password gate config is invalid.")
    required = {
        "schema_version",
        "configured",
        "algorithm",
        "salt",
        "password_hash",
        "iterations",
        "created_at",
        "updated_at",
        "status_labels",
        "config_note",
    }
    if not required.issubset(keys):
        raise PasswordGateError("Password gate config is invalid.")
    if data.get("schema_version") != "1.0":
        raise PasswordGateError("Password gate config is invalid.")
    if data.get("algorithm") != ALGORITHM:
        raise PasswordGateError("Password gate config is invalid.")
    canonicalization = data.get("password_canonicalization", PASSWORD_CANONICALIZATION)
    if canonicalization != PASSWORD_CANONICALIZATION:
        raise PasswordGateError("Password gate config is invalid.")
    if not isinstance(data.get("configured"), bool):
        raise PasswordGateError("Password gate config is invalid.")
    iterations = data.get("iterations")
    if not isinstance(iterations, int) or iterations < MIN_ITERATIONS:
        raise PasswordGateError("Password gate config is invalid.")
    labels = data.get("status_labels")
    if not isinstance(labels, list) or not all(isinstance(item, str) for item in labels):
        raise PasswordGateError("Password gate config is invalid.")
    if data.get("configured") is True:
        _validate_hex_field("salt", data.get("salt"), 16)
        _validate_hex_field("password_hash", data.get("password_hash"), 32)
        if not str(data.get("created_at", "")).strip() or not str(data.get("updated_at", "")).strip():
            raise PasswordGateError("Password gate config is invalid.")
    return dict(data)


def load_password_gate_config(config_path: str | Path | None = None) -> dict[str, object]:
    path = resolve_config_path(config_path)
    if not path.exists():
        return _default_unconfigured_config()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PasswordGateError("Password gate config is invalid.") from exc
    return _validate_config(data)


def build_password_gate_config(password: str, *, created_at: str | None = None) -> dict[str, object]:
    _validate_new_password(password)
    timestamp = created_at or now_utc()
    salt = secrets.token_bytes(32)
    canonical_password = _canonicalize_password_secret(password)
    password_hash = hashlib.pbkdf2_hmac(HASH_NAME, canonical_password.encode("utf-8"), salt, DEFAULT_ITERATIONS).hex()
    return {
        "schema_version": "1.0",
        "configured": True,
        "algorithm": ALGORITHM,
        "salt": salt.hex(),
        "password_hash": password_hash,
        "password_canonicalization": PASSWORD_CANONICALIZATION,
        "iterations": DEFAULT_ITERATIONS,
        "created_at": timestamp,
        "updated_at": timestamp,
        "status_labels": list(STATUS_LABELS),
        "config_note": "Local hash metadata only. No secret is displayed by status commands.",
    }


def write_password_gate_config(config: dict[str, object], config_path: str | Path | None = None) -> Path:
    path = resolve_config_path(config_path)
    validated = _validate_config(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(validated, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def is_global_password_gate_configured(config_path: str | Path | None = None) -> bool:
    try:
        config = load_password_gate_config(config_path)
    except PasswordGateError:
        return False
    return bool(config.get("configured") is True)


def _hash_candidate_password(candidate: str, config: dict[str, object]) -> str:
    salt = bytes.fromhex(str(config["salt"]))
    if config.get("password_canonicalization") == PASSWORD_CANONICALIZATION:
        candidate = _canonicalize_password_secret(candidate)
    return hashlib.pbkdf2_hmac(
        HASH_NAME,
        candidate.encode("utf-8"),
        salt,
        int(config["iterations"]),
    ).hex()


def verify_global_password(password: str, config_path: str | Path | None = None) -> bool:
    try:
        config = load_password_gate_config(config_path)
        if config.get("configured") is not True:
            return False
        candidate_hash = _hash_candidate_password(password, config)
        expected_hash = str(config["password_hash"])
    except (PasswordGateError, ValueError, TypeError):
        return False
    return hmac.compare_digest(candidate_hash, expected_hash)


def _validate_new_password(password: str) -> None:
    if not isinstance(password, str):
        raise PasswordGateError("Password was rejected.")
    canonical_password = _canonicalize_password_secret(password)
    if len(canonical_password) < MIN_PASSWORD_LENGTH:
        raise PasswordGateError("Password was rejected.")
    if not canonical_password.strip():
        raise PasswordGateError("Password was rejected.")
    if password != password.strip():
        raise PasswordGateError("Password was rejected.")


def _canonicalize_password_secret(password: str) -> str:
    if not isinstance(password, str):
        raise PasswordGateError("Password was rejected.")
    return unicodedata.normalize(PASSWORD_CANONICALIZATION, password)


def setup_password_gate(config_path: str | Path | None = None) -> Path:
    first = getpass.getpass("Enter new Engel global password: ")
    second = getpass.getpass("Confirm new Engel global password: ")
    if first != second:
        raise PasswordGateError("Password setup did not complete.")
    config = build_password_gate_config(first)
    return write_password_gate_config(config, config_path)


def change_password_gate(config_path: str | Path | None = None) -> Path:
    current = getpass.getpass("Enter current Engel global password: ")
    if not verify_global_password(current, config_path):
        raise PasswordGateError("Password change did not complete.")
    first = getpass.getpass("Enter new Engel global password: ")
    second = getpass.getpass("Confirm new Engel global password: ")
    if first != second:
        raise PasswordGateError("Password change did not complete.")
    old_config = load_password_gate_config(config_path)
    config = build_password_gate_config(first, created_at=str(old_config.get("created_at") or now_utc()))
    config["updated_at"] = now_utc()
    return write_password_gate_config(config, config_path)


def reject_injection_style_action_id(value: object) -> None:
    if not isinstance(value, str):
        raise PasswordGateError("Action ID rejected.")
    raw = value
    canonical = unicodedata.normalize("NFKC", raw).strip()
    if not canonical:
        raise PasswordGateError("Action ID rejected.")
    if len(canonical) > 128:
        raise PasswordGateError("Action ID rejected.")
    if canonical != raw.strip():
        raise PasswordGateError("Action ID rejected.")
    if any(unicodedata.category(character).startswith("C") for character in raw):
        raise PasswordGateError("Action ID rejected.")
    lowered = canonical.lower()
    if any(marker in canonical for marker in QUOTE_OR_COMMENT_MARKERS):
        raise PasswordGateError("Action ID rejected.")
    if any(character in METACHARACTERS for character in canonical):
        raise PasswordGateError("Action ID rejected.")
    if any(character in BRACKET_OR_PATH_MARKERS for character in canonical):
        raise PasswordGateError("Action ID rejected.")
    if any(marker in canonical for marker in ENCODING_OR_URL_MARKERS):
        raise PasswordGateError("Action ID rejected.")
    if any(phrase in lowered for phrase in PROMPT_UNLOCK_PHRASES):
        raise PasswordGateError("Action ID rejected.")
    if any(character.isspace() for character in canonical):
        raise PasswordGateError("Action ID rejected.")
    if not ACTION_ID_PATTERN.fullmatch(canonical):
        raise PasswordGateError("Action ID rejected.")


def canonicalize_action_id(value: object) -> str:
    reject_injection_style_action_id(value)
    return unicodedata.normalize("NFKC", str(value)).strip()


def is_safe_action_id(value: object) -> bool:
    try:
        canonicalize_action_id(value)
    except PasswordGateError:
        return False
    return True


def require_registered_action(action_id: object) -> dict[str, object]:
    canonical = canonicalize_action_id(action_id)
    action = protected_action_registry.get_action(canonical)
    if action is None:
        raise PasswordGateError("Unknown protected action.")
    return action


def require_password_for_action(action_id: object, password: str, config_path: str | Path | None = None) -> dict[str, object]:
    action = require_registered_action(action_id)
    if action.get("risk_level") == "blocked" or str(action.get("current_state", "")).lower() == "blocked":
        raise PasswordGateError("Protected action is blocked.")
    if not action.get("password_required"):
        return {
            "ok": True,
            "action_id": action["action_id"],
            "password_required": False,
            "message": "Action does not require password verification.",
        }
    if not is_global_password_gate_configured(config_path):
        raise PasswordGateError("Global password gate is not configured. Run: python engel_global_password_gate.py --setup")
    if not verify_global_password(password, config_path):
        raise PasswordGateError("Password verification failed.")
    return {
        "ok": True,
        "action_id": action["action_id"],
        "password_required": True,
        "message": "Password verified; action-specific contracts, verifiers, receipts, and authority still apply.",
    }


def prompt_and_require_action(action_id: object, config_path: str | Path | None = None) -> dict[str, object]:
    action = require_registered_action(action_id)
    if action.get("risk_level") == "blocked" or str(action.get("current_state", "")).lower() == "blocked":
        raise PasswordGateError("Protected action is blocked.")
    if not action.get("password_required"):
        return {
            "ok": True,
            "action_id": action["action_id"],
            "password_required": False,
            "message": "Action does not require password verification.",
        }
    if not is_global_password_gate_configured(config_path):
        raise PasswordGateError("Global password gate is not configured. Run: python engel_global_password_gate.py --setup")
    password = getpass.getpass("Enter Engel global password: ")
    return require_password_for_action(action_id, password, config_path)


def protected_action_gate_summary(action_id: object) -> dict[str, object]:
    try:
        action = require_registered_action(action_id)
        canonical = str(action["action_id"])
        return {
            "ok": True,
            "action_id": canonical,
            "configured": is_global_password_gate_configured(),
            "risk_level": action.get("risk_level"),
            "password_required": action.get("password_required"),
            "approval_token_required": action.get("approval_token_required"),
            "contract_required": action.get("contract_required"),
            "verifier_required": action.get("verifier_required"),
            "receipt_required": action.get("receipt_required"),
            "current_state": action.get("current_state"),
            "blocked_reason": action.get("blocked_reason"),
            "safety_boundary": action.get("safety_boundary"),
        }
    except PasswordGateError as exc:
        return {"ok": False, "reason": str(exc), "configured": is_global_password_gate_configured()}


def global_password_gate_status(config_path: str | Path | None = None) -> dict[str, object]:
    path = resolve_config_path(config_path)
    try:
        config = load_password_gate_config(path)
        configured = bool(config.get("configured") is True)
        active_password_canonicalization = str(config.get("password_canonicalization") or "legacy_exact_utf8")
        config_valid = True
        config_error = ""
    except PasswordGateError as exc:
        configured = False
        active_password_canonicalization = "invalid_config_fail_closed"
        config_valid = False
        config_error = str(exc)
    registry_summary = protected_action_registry.registry_summary()
    return {
        "status_labels": list(STATUS_LABELS),
        "configured": configured,
        "config_valid": config_valid,
        "config_error": config_error,
        "config_path": str(path.relative_to(PROJECT_ROOT.resolve())) if is_relative_to(path, PROJECT_ROOT.resolve()) else "outside_project_rejected",
        "algorithm": ALGORITHM,
        "password_canonicalization": PASSWORD_CANONICALIZATION,
        "active_password_canonicalization": active_password_canonicalization,
        "iterations_minimum": MIN_ITERATIONS,
        "protected_action_count": registry_summary["action_count"],
        "view_only_count": registry_summary["risk_counts"]["view_only"],
        "low_risk_gated_count": registry_summary["risk_counts"]["low"],
        "medium_risk_gated_count": registry_summary["risk_counts"]["medium"],
        "high_risk_gated_count": registry_summary["risk_counts"]["high"],
        "blocked_count": registry_summary["risk_counts"]["blocked"],
        "security_notes": [
            "Password protects actions; it does not bypass safety.",
            "Password does not approve high-risk actions by itself.",
            "Contracts, verifiers, receipts, and authority hierarchy still apply.",
            "Blocked actions remain blocked even with password.",
            "Action IDs use strict allowlists and canonicalization.",
            "SQL-injection-style, Unicode, encoding, whitespace, and prompt-injection bypass attempts are rejected.",
        ],
    }


def render_status(config_path: str | Path | None = None) -> str:
    status = global_password_gate_status(config_path)
    configured_text = "CONFIGURED" if status["configured"] else "NOT CONFIGURED"
    validity_text = "VALID" if status["config_valid"] else "INVALID / FAIL CLOSED"
    lines = [
        "Engel Global Password-Gated Action Layer V1",
        "",
        "Status:",
        *[f"- {label}" for label in STATUS_LABELS],
        "",
        "Password gate:",
        f"- configured: {configured_text}",
        f"- config_valid: {validity_text}",
        f"- config_path: {status['config_path']}",
        f"- algorithm: {ALGORITHM}",
        f"- password_canonicalization: {PASSWORD_CANONICALIZATION}",
        f"- active_password_canonicalization: {status['active_password_canonicalization']}",
        f"- minimum_iterations: {MIN_ITERATIONS}",
        "",
        "Protected Action Registry summary:",
        f"- view-only: {status['view_only_count']}",
        f"- low-risk gated: {status['low_risk_gated_count']}",
        f"- medium-risk gated: {status['medium_risk_gated_count']}",
        f"- high-risk gated: {status['high_risk_gated_count']}",
        f"- blocked: {status['blocked_count']}",
        "",
        "Security notes:",
        *[f"- {note}" for note in status["security_notes"]],
    ]
    if not status["configured"]:
        lines.extend(
            [
                "",
                "Setup:",
                "- Global password gate is not configured. Run: python engel_global_password_gate.py --setup",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage Engel global local password gate.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--status", action="store_true", help="Show password gate status without exposing secrets.")
    mode.add_argument("--setup", action="store_true", help="Configure the local password gate using hidden prompts.")
    mode.add_argument("--verify", action="store_true", help="Verify the local password using a hidden prompt.")
    mode.add_argument("--change", action="store_true", help="Change the local password using hidden prompts.")
    parser.add_argument(
        "--config",
        metavar="PROJECT_LOCAL_TEST_CONFIG",
        help="Optional project-local test/dev config path under reports\\temp_password_gate_tests\\.",
    )
    return parser


def main(argv: list[str] | None = None, stdout=None, stderr=None) -> int:
    out = sys.stdout if stdout is None else stdout
    err = sys.stderr if stderr is None else stderr
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        config_path = resolve_config_path(args.config)
    except PasswordGateError as exc:
        err.write(f"[STOPPED] {exc}\n")
        return 2
    if not any([args.status, args.setup, args.verify, args.change]):
        out.write(render_status(config_path))
        return 0
    try:
        if args.status:
            out.write(render_status(config_path))
            return 0
        if args.setup:
            setup_password_gate(config_path)
            out.write("Global password gate configured. Secret was not displayed.\n")
            return 0
        if args.verify:
            candidate = getpass.getpass("Enter Engel global password: ")
            if verify_global_password(candidate, config_path):
                out.write("Global password gate verification passed.\n")
                return 0
            err.write("Global password gate verification failed.\n")
            return 1
        if args.change:
            change_password_gate(config_path)
            out.write("Global password gate changed. Secret was not displayed.\n")
            return 0
    except PasswordGateError as exc:
        err.write(f"[STOPPED] {exc}\n")
        return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
