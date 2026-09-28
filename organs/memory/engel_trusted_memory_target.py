from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys


ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
CONTRACT_JSON = ROOT / "memory" / "ENGEL_TRUSTED_MEMORY_TARGET_CONTRACT_V1.json"
ALLOWED_MEMORY_ROOT = ROOT / "memory"
ENABLE_CONTRACT_ID = "ENGEL_TRUSTED_MEMORY_TARGET_ENABLE_CONTRACT_V1"
DISABLED_STATUS = "disabled_until_human_target_approval"
ENABLED_STATUS = "enabled_for_password_gated_candidate_promotion"

REQUIRED_STATUS = [
    "TRUSTED_MEMORY_TARGET_CONTRACT",
    "TARGET_EXPLICIT",
    "DISABLED_UNTIL_HUMAN_TARGET_APPROVAL",
    "APPEND_ONLY_JSONL",
    "STRUCTURED_ENTRIES_ONLY",
    "MEMORY_CANDIDATES_ARE_NOT_MEMORY",
    "HUMAN_APPROVAL_REQUIRED",
    "PASSWORD_GATE_REQUIRED",
    "RECEIPT_REQUIRED",
    "VERIFIER_REQUIRED",
    "PROMOTION_BLOCKED_WHILE_DISABLED",
    "NO_AUTO_PROMOTION",
    "NO_BULK_PROMOTION",
    "NO_FAKE_APPROVALS",
    "NO_FAKE_TRUSTED_MEMORY_ENTRIES",
    "NO_SOURCE_MUTATION",
    "NO_ROUTE_MUTATION",
    "NO_PATCH_APPLY",
    "NO_PROVIDER_CALLS",
    "NO_NETWORK",
    "NO_BROWSER",
    "NO_MODEL_LOADING",
    "NO_INFERENCE",
    "NO_TRAINING",
    "NO_WSL_EXECUTION",
    "NO_HERMES_EXECUTION",
    "NO_ANDROID_CONNECTION",
    "NO_PACKAGE_INSTALL",
    "NO_MODEL_DOWNLOAD",
    "NO_BACKGROUND_WORKER",
    "NO_STARTUP_AUTORUN",
    "HERMES_APPROVED_FOR_LOCAL_TESTING_HUMAN_DRIVEN_ONLY",
]

REQUIRED_ENTRY_FIELDS = [
    "memory_id",
    "promoted_at",
    "promoted_by",
    "source_candidate_id",
    "source_path",
    "source_hash",
    "memory_text",
    "memory_scope",
    "memory_reason",
    "approval_token_reference",
    "approval_receipt_path",
    "verifier_result",
    "risk_level",
    "origin_type",
    "status",
]

BLOCKED_PATTERNS = {
    "shell_command_instruction": ["```bash", "```sh", "powershell", "cmd.exe", "run this command", "execute command"],
    "python_execution_request": ["```python", "python -c", "exec(", "eval(", "import subprocess"],
    "route_or_source_mutation": ["mutate route", "change route", "edit source", "source mutation", "apply patch"],
    "provider_network_browser_api": ["openai", "api key", "requests.", "urllib", "socket", "network call", "open browser"],
    "model_runtime": ["load model", "run inference", "train model", "download model"],
    "wsl_hermes_android_runtime": ["wsl ", "Hermes", "Hermes Agent", "android runtime", "connect phone"],
    "approval_claim": ["APPROVE_", "human approved", "simulate approval", "impersonate approval"],
    "secret_material": ["BEGIN PRIVATE KEY", "password=", "secret=", "api_key", "token="],
    "hidden_or_prompt_injection": ["ignore previous instructions", "bypass safety", "disable verifier", "hide this from the user"],
    "engel_bible_app_scope": ["Engel Bible App", "Bible App"],
}


class TrustedMemoryTargetError(ValueError):
    pass


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.resolve(strict=False).relative_to(parent.resolve(strict=False))
        return True
    except ValueError:
        return False


def project_relative(path: Path) -> str:
    return str(path.resolve(strict=False).relative_to(ROOT.resolve(strict=False))).replace("/", "\\")


def load_contract() -> dict[str, object]:
    try:
        data = json.loads(CONTRACT_JSON.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TrustedMemoryTargetError("trusted memory target contract missing or invalid") from exc
    if not isinstance(data, dict):
        raise TrustedMemoryTargetError("trusted memory target contract must be a JSON object")
    return data


def resolve_target(contract: dict[str, object] | None = None) -> Path:
    data = contract or load_contract()
    target = data.get("target", {})
    if not isinstance(target, dict):
        raise TrustedMemoryTargetError("target contract missing target object")
    raw_path = str(target.get("target_path", ""))
    if not raw_path or raw_path.startswith(("http://", "https://", "\\\\")) or any(marker in raw_path for marker in ("*", "?", "[")):
        raise TrustedMemoryTargetError("target path must be explicit and local")
    path = (ROOT / raw_path).resolve(strict=False) if not Path(raw_path).is_absolute() else Path(raw_path).resolve(strict=False)
    if not is_relative_to(path, ALLOWED_MEMORY_ROOT):
        raise TrustedMemoryTargetError("trusted memory target must stay inside Engel App memory folder")
    return path


def validate_target_contract() -> dict[str, object]:
    data = load_contract()
    target = data.get("target", {})
    if not isinstance(target, dict):
        raise TrustedMemoryTargetError("target object missing")
    path = resolve_target(data)
    statuses = data.get("status", [])
    if not isinstance(statuses, list):
        raise TrustedMemoryTargetError("status must be a list")
    missing_status = [status for status in REQUIRED_STATUS if status not in statuses]
    if missing_status:
        raise TrustedMemoryTargetError("contract missing status labels: " + ", ".join(missing_status))
    if target.get("target_format") != "jsonl":
        raise TrustedMemoryTargetError("trusted memory target format must be jsonl")
    if target.get("allowed_write_mode") != "append_only" or target.get("append_only") is not True:
        raise TrustedMemoryTargetError("trusted memory target must be append-only")
    if target.get("human_approval_required") is not True:
        raise TrustedMemoryTargetError("human approval must be required")
    if target.get("password_gate_required") is not True:
        raise TrustedMemoryTargetError("password gate must be required")
    if target.get("receipt_required") is not True or target.get("verifier_required") is not True:
        raise TrustedMemoryTargetError("receipt and verifier must be required")
    enabled = target.get("enabled")
    target_status = target.get("status")
    if enabled is False:
        if target_status != DISABLED_STATUS:
            raise TrustedMemoryTargetError("disabled target status mismatch")
        promotion_allowed = False
        write_blocked_reason = DISABLED_STATUS
    elif enabled is True:
        if target_status != ENABLED_STATUS:
            raise TrustedMemoryTargetError("enabled target status mismatch")
        if target.get("enabled_by_contract") != ENABLE_CONTRACT_ID:
            raise TrustedMemoryTargetError("enabled target must reference target-enable contract")
        receipt_path = str(target.get("enablement_receipt_path", "")).strip()
        if not receipt_path:
            raise TrustedMemoryTargetError("enabled target must reference enablement receipt")
        receipt = (ROOT / receipt_path).resolve(strict=False)
        receipt_root = (ROOT / "reports" / "memory_promotion_receipts").resolve(strict=False)
        if not is_relative_to(receipt, receipt_root) or not receipt.exists():
            raise TrustedMemoryTargetError("enabled target receipt must exist under reports\\memory_promotion_receipts")
        promotion_allowed = True
        write_blocked_reason = "target_enabled_requires_per_memory_approval_and_writer_enablement"
    else:
        raise TrustedMemoryTargetError("target enabled flag must be boolean")
    allowed_fields = data.get("allowed_entry_fields", [])
    if not isinstance(allowed_fields, list):
        raise TrustedMemoryTargetError("allowed_entry_fields must be a list")
    missing_fields = [field for field in REQUIRED_ENTRY_FIELDS if field not in allowed_fields]
    if missing_fields:
        raise TrustedMemoryTargetError("allowed entry fields missing: " + ", ".join(missing_fields))
    boundary = data.get("safety_boundary", {})
    if not isinstance(boundary, dict):
        raise TrustedMemoryTargetError("safety boundary missing")
    if boundary.get("trusted_memory_write_enabled_now") is not False:
        raise TrustedMemoryTargetError("trusted memory write must be disabled now")
    return {
        "target_id": target.get("target_id"),
        "target_path": project_relative(path),
        "target_format": target.get("target_format"),
        "target_status": target.get("status"),
        "enabled": enabled,
        "append_only": target.get("append_only"),
        "max_entry_size": target.get("max_entry_size"),
        "enablement_receipt_path": target.get("enablement_receipt_path", ""),
        "enabled_by_contract": target.get("enabled_by_contract", ""),
        "promotion_allowed": promotion_allowed,
        "write_blocked_reason": write_blocked_reason,
    }


def warning_flags_for_text(text: str) -> list[str]:
    lowered = text.lower()
    flags: list[str] = []
    for flag, patterns in BLOCKED_PATTERNS.items():
        if any(pattern.lower() in lowered for pattern in patterns):
            flags.append(flag)
    return flags


def validate_memory_entry(entry: object) -> dict[str, object]:
    data = load_contract()
    target = data["target"]
    if not isinstance(entry, dict):
        raise TrustedMemoryTargetError("trusted memory entry must be an object")
    allowed = set(data.get("allowed_entry_fields", []))
    unknown = sorted(set(entry) - allowed)
    if unknown:
        raise TrustedMemoryTargetError("trusted memory entry contains unknown fields: " + ", ".join(unknown))
    missing = [field for field in REQUIRED_ENTRY_FIELDS if field not in entry]
    if missing:
        raise TrustedMemoryTargetError("trusted memory entry missing fields: " + ", ".join(missing))
    if entry.get("status") != "trusted_promoted":
        raise TrustedMemoryTargetError("trusted memory entry status must be trusted_promoted")
    memory_text = str(entry.get("memory_text", ""))
    if len(memory_text.encode("utf-8")) > int(target.get("max_entry_size", 8192)):
        raise TrustedMemoryTargetError("trusted memory entry exceeds max_entry_size")
    flags = warning_flags_for_text(memory_text)
    if flags:
        raise TrustedMemoryTargetError("trusted memory entry blocked by warning flags: " + ", ".join(flags))
    return {
        "valid": True,
        "warning_flags": [],
        "entry_hash": hashlib.sha256(json.dumps(entry, sort_keys=True).encode("utf-8")).hexdigest(),
    }


def preview_promoted_entry(candidate: dict[str, object], approval_receipt_path: str = "") -> dict[str, object]:
    timestamp = now_utc()
    source_candidate_id = str(candidate.get("candidate_id", candidate.get("source_candidate_id", "unknown_candidate")))
    source_hash = str(candidate.get("source_hash", ""))
    seed = f"{source_candidate_id}|{source_hash}|{timestamp}".encode("utf-8")
    return {
        "memory_id": "trusted_memory_" + hashlib.sha256(seed).hexdigest()[:16],
        "promoted_at": timestamp,
        "promoted_by": "Engel-controlled human-approved promotion flow",
        "source_candidate_id": source_candidate_id,
        "source_path": str(candidate.get("source_path", "")),
        "source_hash": source_hash,
        "memory_text": str(candidate.get("proposed_memory_text", "")),
        "memory_scope": str(candidate.get("scope", "Engel App")),
        "memory_reason": str(candidate.get("reason", "human-approved memory candidate")),
        "approval_token_reference": "APPROVE_PROMOTE_MEMORY_CANDIDATE",
        "approval_receipt_path": approval_receipt_path,
        "verifier_result": "verifier_required_before_write",
        "risk_level": str(candidate.get("risk_level", "human_review_required")),
        "origin_type": str(candidate.get("source_type", "memory_candidate_proposal")),
        "status": "trusted_promoted",
    }


def promotion_allowed() -> bool:
    return bool(validate_target_contract().get("promotion_allowed"))


def write_blocked_reason() -> str:
    return str(validate_target_contract().get("write_blocked_reason"))


def status_payload() -> dict[str, object]:
    target = validate_target_contract()
    return {
        "schema_version": "1.0",
        "generated_at": now_utc(),
        "module": "Engel Trusted Memory Target Contract V1",
        "status": REQUIRED_STATUS,
        "target": target,
        "promotion_allowed": bool(target.get("promotion_allowed")),
        "write_blocked_reason": str(target.get("write_blocked_reason")),
        "safety_boundary": {
            "trusted_memory_write_enabled_now": False,
            "auto_promote_memory": False,
            "bulk_promote_memory": False,
            "fake_approvals": False,
            "fake_trusted_memory_entries": False,
            "source_mutation": False,
            "route_mutation": False,
            "provider_network_browser": False,
            "wsl_hermes_android": False,
            "model_runtime": False,
            "worker_startup": False,
        },
    }


def render_status() -> str:
    payload = status_payload()
    target = payload["target"]
    assert isinstance(target, dict)
    lines = [
        "Engel Trusted Memory Target Contract V1",
        "",
        "Status:",
        *[f"- {status}" for status in REQUIRED_STATUS],
        "",
        f"Target path: {target['target_path']}",
        f"Target format: {target['target_format']}",
        f"Target status: {target['target_status']}",
        f"Promotion allowed: {payload['promotion_allowed']}",
        f"Write blocked reason: {payload['write_blocked_reason']}",
        "",
        "Ambiguous trusted memory target means promotion blocked.",
        "Memory candidates are not memory.",
    ]
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Engel Trusted Memory Target Contract V1.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--status", action="store_true", help="Show trusted memory target status.")
    mode.add_argument("--validate", action="store_true", help="Validate trusted memory target contract.")
    mode.add_argument("--json", action="store_true", help="Print structured target status JSON.")
    return parser


def main(argv: list[str] | None = None, stdout=None, stderr=None) -> int:
    out = stdout if stdout is not None else sys.stdout
    err = stderr if stderr is not None else sys.stderr
    args = build_parser().parse_args(argv)
    try:
        if args.validate:
            out.write(json.dumps(validate_target_contract(), indent=2, sort_keys=True) + "\n")
            return 0
        if args.json:
            out.write(json.dumps(status_payload(), indent=2, sort_keys=True) + "\n")
            return 0
        out.write(render_status())
        return 0
    except TrustedMemoryTargetError as exc:
        err.write(f"[STOPPED] {exc}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
