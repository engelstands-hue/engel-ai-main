from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import engel_code_companion_protected_patch_apply as protected_patch_apply
import engel_global_password_gate as global_password_gate
import engel_protected_action_registry as protected_action_registry


PROJECT_ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
RECEIPT_DIR = PROJECT_ROOT / "reports" / "code_companion_password_gate_integration"
APPROVAL_TOKEN = protected_patch_apply.APPROVAL_TOKEN
PROTECTED_ACTION_ID = protected_patch_apply.PROTECTED_ACTION_ID

CHECK_FINAL_DECISION = "PASSWORD GATE INTEGRATION CHECK \u2014 NOT APPLIED"
UNCONFIGURED_FINAL_DECISION = "PASSWORD GATE UNCONFIGURED \u2014 APPLY BLOCKED"
REFUSED_FINAL_DECISION = "PROTECTED APPLY REFUSED \u2014 NOT APPLIED"
GATE_PASS_FINAL_DECISION = "PASSWORD GATE SMOKE PASS \u2014 NO SOURCE APPLY"


@dataclass(frozen=True)
class IntegrationReceipt:
    json_path: str
    markdown_path: str
    payload: dict[str, Any]


class PasswordGateIntegrationError(ValueError):
    pass


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def safe_stamp(value: str) -> str:
    return value.replace(":", "").replace("-", "").replace("+00:00", "Z")


def is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.resolve(strict=False).relative_to(parent.resolve(strict=False))
        return True
    except ValueError:
        return False


def project_relative(path: Path) -> str:
    try:
        return str(path.resolve(strict=False).relative_to(PROJECT_ROOT.resolve(strict=False))).replace("/", "\\")
    except ValueError:
        return str(path.resolve(strict=False))


def ensure_receipt_dir(receipt_dir: Path = RECEIPT_DIR) -> None:
    receipt_dir.mkdir(parents=True, exist_ok=True)


def token_state(token: str | None) -> dict[str, bool]:
    token_text = str(token or "")
    token_present = bool(token_text)
    return {
        "approval_token_present": token_present,
        "approval_token_verified": token_text == APPROVAL_TOKEN,
    }


def gate_status() -> dict[str, Any]:
    protected_apply_present = (PROJECT_ROOT / "engel_code_companion_protected_patch_apply.py").exists()
    password_gate_present = (PROJECT_ROOT / "engel_global_password_gate.py").exists()
    registry_present = (PROJECT_ROOT / "engel_protected_action_registry.py").exists()
    password_status = global_password_gate.global_password_gate_status()
    action_summary = global_password_gate.protected_action_gate_summary(PROTECTED_ACTION_ID)
    registry_action = protected_action_registry.get_action(PROTECTED_ACTION_ID)
    password_configured = bool(password_status.get("configured") is True)
    action_available = bool(action_summary.get("ok") and action_summary.get("current_state") != "blocked")
    return {
        "protected_apply_module_present": protected_apply_present,
        "global_password_gate_present": password_gate_present,
        "protected_action_registry_present": registry_present,
        "protected_action_id": PROTECTED_ACTION_ID,
        "protected_action_registered": registry_action is not None,
        "protected_action_available": action_available,
        "approval_token_required": True,
        "required_approval_token": APPROVAL_TOKEN,
        "password_gate_required": True,
        "password_gate_configured": password_configured,
        "password_gate_config_valid": bool(password_status.get("config_valid")),
        "password_collection_enabled_in_this_phase": False,
        "patch_application_enabled": False,
        "auto_apply": False,
        "trusted_memory_write": False,
        "source_files_modified": False,
        "routes_mutated": False,
        "queues_mutated": False,
        "provider_calls_made": False,
        "gate_summary": {
            "ok": action_summary.get("ok"),
            "risk_level": action_summary.get("risk_level"),
            "password_required": action_summary.get("password_required"),
            "approval_token_required": True,
            "contract_required": action_summary.get("contract_required"),
            "verifier_required": action_summary.get("verifier_required"),
            "receipt_required": action_summary.get("receipt_required"),
            "current_state": action_summary.get("current_state"),
        },
    }


def base_receipt(action: str, final_decision: str, *, created_at: str | None = None) -> dict[str, Any]:
    stamp = created_at or now_utc()
    status = gate_status()
    receipt_status = dict(status)
    receipt_status["required_approval_token"] = "REQUIRED_TOKEN_REDACTED"
    return {
        "receipt_version": "1",
        "created_at": stamp,
        "created_by": "Engel Code Companion",
        "action": action,
        "protected_action_id": PROTECTED_ACTION_ID,
        "approval_token_required": True,
        "approval_token_present": False,
        "approval_token_verified": False,
        "password_gate_required": True,
        "password_gate_configured": bool(status["password_gate_configured"]),
        "password_verified": False,
        "patch_applied": False,
        "source_files_modified": False,
        "trusted_memory_written": False,
        "routes_mutated": False,
        "queues_mutated": False,
        "provider_calls_made": False,
        "auto_apply": False,
        "password_or_approval_token_stored": False,
        "password_collection_enabled_in_this_phase": False,
        "patch_application_enabled": False,
        "status": receipt_status,
        "smoke_cases": [],
        "final_decision": final_decision,
        "note": "No password or approval token was stored.",
    }


def write_receipt(payload: dict[str, Any], receipt_dir: Path = RECEIPT_DIR) -> IntegrationReceipt:
    ensure_receipt_dir(receipt_dir)
    stamp = safe_stamp(str(payload.get("created_at", now_utc())))
    action = str(payload.get("action", "password_gate_integration")).lower().replace(" ", "_").replace("-", "_")
    stem = f"PASSWORD_GATE_INTEGRATION_{stamp}_{action}"
    json_path = receipt_dir / f"{stem}.json"
    markdown_path = receipt_dir / f"{stem}.md"
    write_lf_text(json_path, json.dumps(payload, indent=2, sort_keys=True) + "\n")
    write_lf_text(markdown_path, render_receipt_markdown(payload))
    return IntegrationReceipt(project_relative(json_path), project_relative(markdown_path), payload)


def write_lf_text(path: Path, text: str) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def render_receipt_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Code Companion Password Gate Integration Receipt",
        "",
        f"- timestamp: `{payload.get('created_at')}`",
        f"- action: `{payload.get('action')}`",
        f"- approval_token_required: `{payload.get('approval_token_required')}`",
        f"- approval_token_present: `{payload.get('approval_token_present')}`",
        f"- approval_token_verified: `{payload.get('approval_token_verified')}`",
        f"- password_gate_required: `{payload.get('password_gate_required')}`",
        f"- password_gate_configured: `{payload.get('password_gate_configured')}`",
        f"- password_verified: `{payload.get('password_verified')}`",
        f"- patch_applied: `{payload.get('patch_applied')}`",
        f"- source_files_modified: `{payload.get('source_files_modified')}`",
        f"- trusted_memory_written: `{payload.get('trusted_memory_written')}`",
        f"- routes_mutated: `{payload.get('routes_mutated')}`",
        f"- queues_mutated: `{payload.get('queues_mutated')}`",
        f"- provider_calls_made: `{payload.get('provider_calls_made')}`",
        f"- final_decision: `{payload.get('final_decision')}`",
        "",
        "No password or approval token was stored.",
        "No source files were modified.",
        "No patch was applied.",
        "No trusted memory was written.",
    ]
    cases = payload.get("smoke_cases")
    if isinstance(cases, list) and cases:
        lines.extend(["", "## Smoke Cases"])
        for case in cases:
            if isinstance(case, dict):
                lines.append(
                    "- "
                    + str(case.get("case"))
                    + ": token_present="
                    + str(case.get("approval_token_present"))
                    + ", token_verified="
                    + str(case.get("approval_token_verified"))
                    + ", refused="
                    + str(case.get("refused"))
                    + ", reason="
                    + str(case.get("reason"))
                )
    return "\n".join(lines) + "\n"


def check(receipt_dir: Path = RECEIPT_DIR, *, created_at: str | None = None) -> IntegrationReceipt:
    payload = base_receipt("check", CHECK_FINAL_DECISION, created_at=created_at)
    return write_receipt(payload, receipt_dir)


def smoke_refusal(receipt_dir: Path = RECEIPT_DIR, *, created_at: str | None = None) -> IntegrationReceipt:
    status = gate_status()
    cases: list[dict[str, Any]] = []
    for name, token in [("missing_token", None), ("wrong_token", "WRONG_APPROVAL_TOKEN"), ("correct_token", APPROVAL_TOKEN)]:
        token_result = token_state(token)
        if not token_result["approval_token_verified"]:
            cases.append(
                {
                    "case": name,
                    **token_result,
                    "password_gate_checked": False,
                    "password_verified": False,
                    "refused": True,
                    "reason": "Exact approval token is required.",
                }
            )
            continue
        try:
            protected_patch_apply.verify_password_gate(password_prompt=False)
        except protected_patch_apply.ApplyRefusal as exc:
            reason = str(exc.reason)
        else:
            reason = "Password gate unexpectedly passed without password collection."
        cases.append(
            {
                "case": name,
                **token_result,
                "password_gate_checked": True,
                "password_verified": False,
                "refused": True,
                "reason": reason,
            }
        )

    if not status["password_gate_configured"]:
        final_decision = UNCONFIGURED_FINAL_DECISION
    else:
        final_decision = REFUSED_FINAL_DECISION
    payload = base_receipt("smoke-refusal", final_decision, created_at=created_at)
    payload["approval_token_present"] = True
    payload["approval_token_verified"] = True
    payload["smoke_cases"] = cases
    return write_receipt(payload, receipt_dir)


def validate_receipt(path: str | Path) -> tuple[bool, list[str]]:
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = PROJECT_ROOT / candidate
    resolved = candidate.resolve(strict=False)
    errors: list[str] = []
    if not resolved.exists() or not resolved.is_file():
        return False, ["receipt file does not exist"]
    if not is_relative_to(resolved, RECEIPT_DIR) and "temp" not in str(resolved).lower():
        errors.append("receipt must be a password-gate integration receipt or verifier temp receipt")
    if resolved.suffix.lower() != ".json":
        errors.append("receipt must be JSON")
        return False, errors
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return False, [f"could not read receipt: {exc}"]
    required_false = [
        "password_verified",
        "patch_applied",
        "source_files_modified",
        "trusted_memory_written",
        "routes_mutated",
        "queues_mutated",
        "provider_calls_made",
        "auto_apply",
        "password_or_approval_token_stored",
        "password_collection_enabled_in_this_phase",
        "patch_application_enabled",
    ]
    required_true = ["approval_token_required", "password_gate_required"]
    for field in required_false:
        if payload.get(field) is not False:
            errors.append(f"{field} must be false")
    for field in required_true:
        if payload.get(field) is not True:
            errors.append(f"{field} must be true")
    if "APPROVE_PRODUCT_PATCH" in resolved.read_text(encoding="utf-8"):
        errors.append("receipt contains raw approval token")
    if payload.get("note") != "No password or approval token was stored.":
        errors.append("receipt missing no-storage note")
    if payload.get("final_decision") not in {
        CHECK_FINAL_DECISION,
        UNCONFIGURED_FINAL_DECISION,
        REFUSED_FINAL_DECISION,
        GATE_PASS_FINAL_DECISION,
    }:
        errors.append("unknown final decision")
    return not errors, errors


def render_status() -> str:
    return json.dumps(gate_status(), indent=2, sort_keys=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Code Companion password gate integration smoke.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="Show integration status without writing receipts.")
    check_cmd = sub.add_parser("check", help="Write a bounded integration check receipt.")
    check_cmd.add_argument("--receipt-dir", default=str(RECEIPT_DIR))
    smoke = sub.add_parser("smoke-refusal", help="Write a refusal smoke receipt.")
    smoke.add_argument("--receipt-dir", default=str(RECEIPT_DIR))
    validate = sub.add_parser("validate-receipt", help="Validate one integration receipt.")
    validate.add_argument("receipt_path")
    args = parser.parse_args(argv)

    if args.command == "status":
        print(render_status())
        return 0
    if args.command == "check":
        result = check(Path(args.receipt_dir))
        print(json.dumps(result.payload, indent=2, sort_keys=True))
        print("receipt_json:", result.json_path)
        print("receipt_markdown:", result.markdown_path)
        return 0
    if args.command == "smoke-refusal":
        result = smoke_refusal(Path(args.receipt_dir))
        print(json.dumps(result.payload, indent=2, sort_keys=True))
        print("receipt_json:", result.json_path)
        print("receipt_markdown:", result.markdown_path)
        return 0
    if args.command == "validate-receipt":
        valid, errors = validate_receipt(args.receipt_path)
        if valid:
            print("receipt_valid: true")
            return 0
        print("receipt_valid: false")
        for error in errors:
            print("-", error)
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
