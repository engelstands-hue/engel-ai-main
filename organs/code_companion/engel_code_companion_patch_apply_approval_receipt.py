from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import engel_code_companion_patch_apply_dry_run as patch_apply_dry_run


PROJECT_ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
APPLY_DRY_RUN_ROOT = PROJECT_ROOT / "reports" / "code_companion_patch_apply_dry_runs"
APPROVAL_ROOT = PROJECT_ROOT / "reports" / "code_companion_patch_apply_approvals"
EXAMPLES_DIR = APPROVAL_ROOT / "examples"
RECEIPTS_DIR = APPROVAL_ROOT / "receipts"

MAX_INPUT_BYTES = 1024 * 1024
MAX_PREVIEW_CHARS = 1600
MAX_REPORT_CHARS = 18000

DRY_RUN_FINAL_DECISION = patch_apply_dry_run.FINAL_DECISION
APPROVAL_FINAL_DECISION = "PROTECTED PATCH APPROVAL RECEIPT ONLY \u2014 NOT APPROVED \u2014 NOT APPLIED"

REQUIRED_APPROVALS = [
    "human_review",
    "approval_token",
    "password_gate_for_protected_actions",
    "verifier_pass_required",
]

REQUIRED_BLOCKED_ACTIONS = [
    "approve_without_human_review",
    "collect_or_store_password",
    "collect_or_store_approval_token",
    "apply_patch_without_approval",
    "edit_source_without_approval",
    "execute_commands_from_dry_run",
    "mutate_routes",
    "mutate_queue",
    "write_trusted_memory",
    "auto_apply",
    "provider_call",
    "browser_task",
    "download",
    "install_package",
]

RISK_PATTERNS = {
    "powershell": r"\bpowershell\b",
    "cmd_exe": r"\bcmd\.exe\b",
    "bash": r"\bbash\b",
    "wsl": r"\bwsl\b",
    "curl": r"\bcurl\b",
    "invoke_webrequest": r"\binvoke-webrequest\b",
    "download": r"\bdownload\b",
    "install": r"\binstall\b",
    "apply_patch": r"\bapply patch\b|\bapply patches\b",
    "modify_source": r"\bmodify source\b|\bedit source\b|\bsource mutation\b",
    "write_memory": r"\bwrite memory\b",
    "trusted_memory": r"\btrusted memory\b|\btrusted-memory\b",
    "mutate_route": r"\bmutate route\b|\bmutate routes\b|\broute mutation\b",
    "mutate_queue": r"\bmutate queue\b|\bqueue mutation\b",
    "auto_apply": r"\bauto apply\b|\bauto-apply\b",
    "bypass": r"\bbypass\b",
    "ignore_previous_instructions": r"\bignore previous instructions\b",
    "disable_verifier": r"\bdisable verifier\b|\bskip verifier\b",
    "approve_this": r"\bapprove this\b",
    "promote_this": r"\bpromote this\b",
    "token": r"\btoken\b",
    "secret": r"\bsecret\b",
    "password": r"\bpassword\b",
    "delete_files": r"\bdelete files\b|\bdelete\b",
    "exfiltrate": r"\bexfiltrate\b",
    "run_this_command": r"\brun this command\b",
    "execute_this": r"\bexecute this\b",
    "chmod": r"\bchmod\b",
    "registry": r"\bregistry\b",
    "firewall": r"\bfirewall\b",
}


class PatchApplyApprovalReceiptError(ValueError):
    pass


@dataclass
class DryRunValidation:
    dry_run_path: str
    valid: bool
    dry_run_id: str | None
    status: str | None
    errors: list[str]
    warnings: list[str]


@dataclass
class ApprovalReceiptResult:
    receipt_json: str
    receipt_markdown: str
    receipt: dict[str, Any]


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def project_relative(path: Path) -> str:
    try:
        return str(path.resolve(strict=False).relative_to(PROJECT_ROOT.resolve(strict=False))).replace("/", "\\")
    except ValueError:
        return str(path.resolve(strict=False))


def is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.resolve(strict=False).relative_to(parent.resolve(strict=False))
        return True
    except ValueError:
        return False


def safe_slug(value: str, limit: int = 150) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip()).strip("._-")
    return (cleaned or "patch_apply_approval_receipt")[:limit]


def timestamp_slug(value: str) -> str:
    return safe_slug(value.replace(":", "").replace("-", ""), 40)


def bounded_text(value: Any, limit: int = MAX_PREVIEW_CHARS) -> str:
    clean = str(value if value is not None else "").replace("\r\n", "\n").strip()
    if len(clean) <= limit:
        return clean
    return clean[:limit] + "\n[preview truncated]"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_folders(root: Path = APPROVAL_ROOT, receipts_dir: Path = RECEIPTS_DIR) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "examples").mkdir(parents=True, exist_ok=True)
    receipts_dir.mkdir(parents=True, exist_ok=True)


def risk_flags_for_text(text: str) -> list[str]:
    flags: list[str] = []
    for flag, pattern in RISK_PATTERNS.items():
        if re.search(pattern, text, re.IGNORECASE):
            flags.append(flag)
    return sorted(set(flags))


def load_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PatchApplyApprovalReceiptError(f"could not read JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise PatchApplyApprovalReceiptError("JSON root must be an object")
    return payload


def resolve_dry_run_path(raw_path: str | Path) -> Path:
    text = str(raw_path)
    if not text or text.startswith(("http://", "https://", "\\\\")):
        raise PatchApplyApprovalReceiptError("dry-run path must be an explicit local Phase 5 dry-run path")
    if any(marker in text for marker in ("*", "?", "[")):
        raise PatchApplyApprovalReceiptError("wildcards are not allowed")
    path = Path(text)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    resolved = path.resolve(strict=False)
    if resolved.is_dir():
        resolved = resolved / "dry_run.json"
    if not resolved.exists() or not resolved.is_file():
        raise PatchApplyApprovalReceiptError("dry_run.json does not exist")
    if not is_relative_to(resolved, PROJECT_ROOT):
        raise PatchApplyApprovalReceiptError("dry-run path must stay inside Engel App")
    if not is_relative_to(resolved, APPLY_DRY_RUN_ROOT):
        raise PatchApplyApprovalReceiptError("Phase 6 accepts Phase 5 patch apply dry-runs only")
    if resolved.suffix.lower() != ".json":
        raise PatchApplyApprovalReceiptError("dry-run input must be JSON")
    if resolved.name != "dry_run.json" and resolved.parent != APPLY_DRY_RUN_ROOT / "examples":
        raise PatchApplyApprovalReceiptError("dry-run input must be a dry_run.json file or the Phase 5 example JSON")
    if resolved.suffix.lower() in {".patch", ".diff"}:
        raise PatchApplyApprovalReceiptError("dry-run input must not be a patch/diff file")
    if resolved.stat().st_size > MAX_INPUT_BYTES:
        raise PatchApplyApprovalReceiptError(f"dry-run input exceeds max size of {MAX_INPUT_BYTES} bytes")
    return resolved


def validate_dry_run_for_receipt(raw_path: str | Path) -> DryRunValidation:
    try:
        dry_run_path = resolve_dry_run_path(raw_path)
        payload = load_json_object(dry_run_path)
    except PatchApplyApprovalReceiptError as exc:
        return DryRunValidation(str(raw_path), False, None, None, [str(exc)], [])
    errors = list(patch_apply_dry_run.validate_dry_run_payload(payload))
    expected_false = [
        "safe_to_auto_apply",
        "patch_applied",
        "source_files_modified",
        "application_enabled_in_this_phase",
    ]
    expected_true = [
        "requires_review",
        "approval_token_required",
        "password_gate_required",
        "verifier_pass_required",
    ]
    for field in expected_false:
        if payload.get(field) is not False:
            errors.append(f"{field} must be false")
    for field in expected_true:
        if payload.get(field) is not True:
            errors.append(f"{field} must be true")
    if payload.get("status") != "apply_dry_run_preview":
        errors.append("status must be apply_dry_run_preview")
    if payload.get("final_decision") != DRY_RUN_FINAL_DECISION:
        errors.append("final_decision must be " + DRY_RUN_FINAL_DECISION)
    if payload.get("approval_token_present") is not False:
        errors.append("approval_token_present must be false before Phase 6 receipt")
    if payload.get("password_verified") is not False:
        errors.append("password_verified must be false before Phase 6 receipt")
    return DryRunValidation(
        dry_run_path=project_relative(dry_run_path),
        valid=not errors,
        dry_run_id=str(payload.get("dry_run_id")) if payload.get("dry_run_id") else None,
        status=str(payload.get("status")) if payload.get("status") else None,
        errors=errors,
        warnings=[],
    )


def load_validated_dry_run(raw_path: str | Path) -> tuple[Path, dict[str, Any], DryRunValidation]:
    dry_run_path = resolve_dry_run_path(raw_path)
    validation = validate_dry_run_for_receipt(dry_run_path)
    if not validation.valid:
        raise PatchApplyApprovalReceiptError("source dry-run is invalid for approval receipt: " + "; ".join(validation.errors))
    return dry_run_path, load_json_object(dry_run_path), validation


def approval_receipt_id_for(dry_run_id: str, created_at: str) -> str:
    return f"{timestamp_slug(created_at)}_{safe_slug(dry_run_id, 100)}_approval_receipt"


def risk_flags_for_dry_run(dry_run_path: Path, dry_run: dict[str, Any]) -> list[str]:
    existing = dry_run.get("risk_flags") if isinstance(dry_run.get("risk_flags"), list) else []
    text = json.dumps(dry_run, sort_keys=True)
    for companion in ["README.md", "risk_review.md", "simulated_change_summary.md", "verification_plan.md"]:
        path = dry_run_path.parent / companion
        if path.exists() and path.is_file() and path.stat().st_size <= MAX_INPUT_BYTES:
            try:
                text += "\n" + path.read_text(encoding="utf-8", errors="replace")[:MAX_PREVIEW_CHARS]
            except OSError:
                pass
    return sorted(set([str(item) for item in existing if isinstance(item, str)] + risk_flags_for_text(text)))


def target_files_for_receipt(dry_run: dict[str, Any]) -> list[str]:
    targets: list[str] = []
    raw = dry_run.get("target_files_checked")
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict) and isinstance(item.get("target_file"), str):
                targets.append(item["target_file"])
            elif isinstance(item, str):
                targets.append(item)
    return targets[:80]


def verification_plan_for_receipt(dry_run: dict[str, Any]) -> list[dict[str, Any]]:
    plan: list[dict[str, Any]] = []
    raw = dry_run.get("verification_plan")
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            command = item.get("command")
            purpose = item.get("purpose")
            if not isinstance(command, str) or not command.strip():
                continue
            plan.append(
                {
                    "command": command.strip()[:260],
                    "purpose": bounded_text(purpose, 320),
                    "manual_only": True,
                    "executed_by_approval_receipt": False,
                    "verifier_pass_recorded_for_apply": False,
                }
            )
    if not plan:
        plan.append(
            {
                "command": ".\\scripts\\codex_verify.ps1",
                "purpose": "Run the full Engel verifier in a future explicitly requested apply phase.",
                "manual_only": True,
                "executed_by_approval_receipt": False,
                "verifier_pass_recorded_for_apply": False,
            }
        )
    return plan


def build_approval_receipt_payload(dry_run_path: Path, dry_run: dict[str, Any], created_at: str | None = None) -> dict[str, Any]:
    stamp = created_at or now_utc()
    dry_run_id = str(dry_run.get("dry_run_id", "unknown_dry_run"))
    return {
        "approval_receipt_version": "1",
        "approval_receipt_id": approval_receipt_id_for(dry_run_id, stamp),
        "created_at": stamp,
        "created_by": "Engel Code Companion",
        "source_dry_run_id": dry_run_id,
        "source_dry_run_path": project_relative(dry_run_path),
        "source_dry_run_hash": sha256_file(dry_run_path),
        "trust_level": "untrusted_until_human_approved",
        "status": "approval_receipt_review_only",
        "requires_review": True,
        "safe_to_auto_apply": False,
        "patch_applied": False,
        "source_files_modified": False,
        "application_enabled_in_this_phase": False,
        "approval_collection_enabled": False,
        "password_collection_enabled": False,
        "human_review_required": True,
        "human_review_completed": False,
        "approval_token_required": True,
        "approval_token_present": False,
        "approval_token_verified": False,
        "password_gate_required": True,
        "password_verified": False,
        "verifier_pass_required": True,
        "verifier_pass_recorded_for_apply": False,
        "apply_authorized": False,
        "eligible_for_future_apply_consideration": True,
        "required_approvals_before_apply": list(REQUIRED_APPROVALS),
        "blocked_actions": list(REQUIRED_BLOCKED_ACTIONS),
        "target_files": target_files_for_receipt(dry_run),
        "protected_path_flags": list(dry_run.get("protected_path_flags", [])) if isinstance(dry_run.get("protected_path_flags"), list) else [],
        "risk_flags": risk_flags_for_dry_run(dry_run_path, dry_run),
        "verification_plan": verification_plan_for_receipt(dry_run),
        "final_decision": APPROVAL_FINAL_DECISION,
    }


def validate_approval_receipt_payload(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required_strings = [
        "approval_receipt_version",
        "approval_receipt_id",
        "created_at",
        "created_by",
        "source_dry_run_id",
        "source_dry_run_path",
        "source_dry_run_hash",
        "trust_level",
        "status",
        "final_decision",
    ]
    for field in required_strings:
        if not isinstance(payload.get(field), str) or not str(payload.get(field)).strip():
            errors.append(f"{field} must be a non-empty string")
    expected = {
        "created_by": "Engel Code Companion",
        "trust_level": "untrusted_until_human_approved",
        "status": "approval_receipt_review_only",
        "final_decision": APPROVAL_FINAL_DECISION,
    }
    for field, value in expected.items():
        if payload.get(field) != value:
            errors.append(f"{field} must be {value}")
    expected_false = [
        "safe_to_auto_apply",
        "patch_applied",
        "source_files_modified",
        "application_enabled_in_this_phase",
        "approval_collection_enabled",
        "password_collection_enabled",
        "human_review_completed",
        "approval_token_present",
        "approval_token_verified",
        "password_verified",
        "verifier_pass_recorded_for_apply",
        "apply_authorized",
    ]
    expected_true = [
        "requires_review",
        "human_review_required",
        "approval_token_required",
        "password_gate_required",
        "verifier_pass_required",
    ]
    for field in expected_false:
        if payload.get(field) is not False:
            errors.append(f"{field} must be false")
    for field in expected_true:
        if payload.get(field) is not True:
            errors.append(f"{field} must be true")
    blocked = payload.get("blocked_actions")
    if not isinstance(blocked, list):
        errors.append("blocked_actions must be a list")
    else:
        missing = [item for item in REQUIRED_BLOCKED_ACTIONS if item not in blocked]
        if missing:
            errors.append("blocked_actions missing required entries: " + ", ".join(missing))
    approvals = payload.get("required_approvals_before_apply")
    if not isinstance(approvals, list):
        errors.append("required_approvals_before_apply must be a list")
    else:
        missing = [item for item in REQUIRED_APPROVALS if item not in approvals]
        if missing:
            errors.append("required_approvals_before_apply missing required entries: " + ", ".join(missing))
    return errors


def receipt_json_path_for(receipt: dict[str, Any], receipts_dir: Path = RECEIPTS_DIR) -> Path:
    stamp = timestamp_slug(str(receipt.get("created_at", "receipt")))
    receipt_id = safe_slug(str(receipt.get("approval_receipt_id", "approval_receipt")))
    return receipts_dir / f"PATCH_APPLY_APPROVAL_RECEIPT_{stamp}_{receipt_id}.json"


def receipt_markdown_path_for(receipt: dict[str, Any], receipts_dir: Path = RECEIPTS_DIR) -> Path:
    stamp = timestamp_slug(str(receipt.get("created_at", "receipt")))
    receipt_id = safe_slug(str(receipt.get("approval_receipt_id", "approval_receipt")))
    return receipts_dir / f"PATCH_APPLY_APPROVAL_RECEIPT_{stamp}_{receipt_id}.md"


def lines_for_values(values: list[Any]) -> str:
    cleaned = [value for value in values if value not in {None, ""}]
    return "\n".join(f"- `{value}`" for value in cleaned) if cleaned else "- none"


def render_receipt_markdown(receipt: dict[str, Any]) -> str:
    verification = "\n".join(
        f"- `{item.get('command')}` - {bounded_text(item.get('purpose', ''), 240)}"
        for item in receipt.get("verification_plan", [])
        if isinstance(item, dict)
    ) or "- none"
    text = f"""# Code Companion Protected Patch Apply Approval Receipt

## Receipt

- timestamp: `{receipt.get("created_at")}`
- approval_receipt_id: `{receipt.get("approval_receipt_id")}`
- source dry-run path: `{receipt.get("source_dry_run_path")}`
- source dry-run SHA-256: `{receipt.get("source_dry_run_hash")}`
- status: `{receipt.get("status")}`
- final decision: **{receipt.get("final_decision")}**

## Target Files

{lines_for_values(receipt.get("target_files", []))}

## Risk Flags

{lines_for_values(receipt.get("risk_flags", []))}

## Protected Path Flags

{lines_for_values(receipt.get("protected_path_flags", []))}

## Required Approvals Before Apply

{lines_for_values(receipt.get("required_approvals_before_apply", []))}

## Remaining Gates

- human_review_completed: `{receipt.get("human_review_completed")}`
- approval_token_present: `{receipt.get("approval_token_present")}`
- password_verified: `{receipt.get("password_verified")}`
- verifier_pass_recorded_for_apply: `{receipt.get("verifier_pass_recorded_for_apply")}`
- apply_authorized: `{receipt.get("apply_authorized")}`

## Verification Plan

{verification}

## Boundary

No source files were modified.

No patch was applied.

No commands from the dry-run were executed.

No trusted memory was written.

No approval token was collected or stored.

No password was collected or stored.

Future apply remains blocked.
"""
    if len(text) > MAX_REPORT_CHARS:
        text = text[:MAX_REPORT_CHARS] + "\n[approval receipt truncated]\n"
    return text


def write_receipt_outputs(receipt: dict[str, Any], receipts_dir: Path = RECEIPTS_DIR) -> ApprovalReceiptResult:
    receipts_dir.mkdir(parents=True, exist_ok=True)
    json_path = receipt_json_path_for(receipt, receipts_dir)
    markdown_path = receipt_markdown_path_for(receipt, receipts_dir)
    json_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(render_receipt_markdown(receipt), encoding="utf-8")
    return ApprovalReceiptResult(str(json_path), str(markdown_path), receipt)


def create_approval_receipt(
    raw_dry_run: str | Path,
    *,
    receipts_dir: Path = RECEIPTS_DIR,
    created_at: str | None = None,
) -> ApprovalReceiptResult:
    dry_run_path, dry_run, _validation = load_validated_dry_run(raw_dry_run)
    receipt = build_approval_receipt_payload(dry_run_path, dry_run, created_at=created_at)
    errors = validate_approval_receipt_payload(receipt)
    if errors:
        raise PatchApplyApprovalReceiptError("generated approval receipt failed validation: " + "; ".join(errors))
    ensure_folders(APPROVAL_ROOT, receipts_dir)
    return write_receipt_outputs(receipt, receipts_dir)


def receipt_files(receipts_dir: Path = RECEIPTS_DIR) -> list[Path]:
    if not receipts_dir.exists():
        return []
    return sorted([path for path in receipts_dir.iterdir() if path.is_file() and path.suffix.lower() == ".json"], key=lambda item: item.name.lower())


def render_status(root: Path = APPROVAL_ROOT, receipts_dir: Path = RECEIPTS_DIR) -> str:
    ensure_folders(root, receipts_dir)
    return "\n".join(
        [
            "Code Companion patch apply approval receipt status",
            f"Approval root: {project_relative(root)}",
            f"Examples: {project_relative(root / 'examples')}",
            f"Receipts: {project_relative(receipts_dir)}",
            f"Approval receipt count: {len(receipt_files(receipts_dir))}",
            "approval_receipt_only: true",
            "approval_collection_enabled: false",
            "password_collection_enabled: false",
            "patch_application_enabled: false",
            "source_mutation_enabled: false",
            "trusted_memory_write_enabled: false",
        ]
    )


def render_list(receipts_dir: Path = RECEIPTS_DIR) -> str:
    lines = ["Code Companion patch apply approval receipts:"]
    receipts = receipt_files(receipts_dir)
    if not receipts:
        lines.append("- none")
    for path in receipts:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            lines.append(f"- {project_relative(path)} invalid")
            continue
        lines.append(
            "- "
            + f"{payload.get('approval_receipt_id')} | dry_run={payload.get('source_dry_run_id')} | "
            + f"status={payload.get('status')} | human_review_required={payload.get('human_review_required')} | "
            + f"approval_token_required={payload.get('approval_token_required')} | "
            + f"approval_token_present={payload.get('approval_token_present')} | "
            + f"password_gate_required={payload.get('password_gate_required')} | "
            + f"password_verified={payload.get('password_verified')} | "
            + f"verifier_pass_required={payload.get('verifier_pass_required')} | "
            + f"patch_applied={payload.get('patch_applied')}"
        )
    return "\n".join(lines)


def render_validate(raw_dry_run: str | Path) -> str:
    validation = validate_dry_run_for_receipt(raw_dry_run)
    lines = [
        f"Dry-run path: {validation.dry_run_path}",
        f"Valid for approval receipt: {validation.valid}",
        f"Dry-run ID: {validation.dry_run_id or '(unknown)'}",
        f"Status: {validation.status or '(unknown)'}",
    ]
    if validation.errors:
        lines.append("Errors:")
        lines.extend(f"- {error}" for error in validation.errors)
    if validation.warnings:
        lines.append("Warnings:")
        lines.extend(f"- {warning}" for warning in validation.warnings)
    lines.append("approval_collection_enabled: false")
    lines.append("password_collection_enabled: false")
    lines.append("patch_application_enabled: false")
    return "\n".join(lines)


def render_requirements(raw_dry_run: str | Path) -> str:
    validation = validate_dry_run_for_receipt(raw_dry_run)
    lines = [render_validate(raw_dry_run), "", "Future apply remains blocked until:"]
    for requirement in REQUIRED_APPROVALS:
        lines.append(f"- {requirement}")
    lines.extend(
        [
            "human_review_completed: false",
            "approval_token_present: false",
            "password_verified: false",
            "verifier_pass_recorded_for_apply: false",
            "apply_authorized: false",
        ]
    )
    return "\n".join(lines)


def resolve_output_for_show(raw: str | Path) -> Path:
    text = str(raw)
    path = Path(text)
    candidates: list[Path] = []
    if path.is_absolute() or "\\" in text or "/" in text:
        candidates.append(path if path.is_absolute() else PROJECT_ROOT / path)
    else:
        slug = safe_slug(text)
        candidates.extend(
            [
                RECEIPTS_DIR / f"PATCH_APPLY_APPROVAL_RECEIPT_{slug}.md",
                RECEIPTS_DIR / f"PATCH_APPLY_APPROVAL_RECEIPT_{slug}.json",
            ]
        )
        if RECEIPTS_DIR.exists():
            candidates.extend(sorted(RECEIPTS_DIR.glob(f"*{slug}*.md")))
            candidates.extend(sorted(RECEIPTS_DIR.glob(f"*{slug}*.json")))
    for candidate in candidates:
        resolved = candidate.resolve(strict=False)
        if resolved.exists() and resolved.is_file() and is_relative_to(resolved, APPROVAL_ROOT):
            return resolved
    raise PatchApplyApprovalReceiptError("approval receipt not found")


def render_show(raw: str | Path) -> str:
    path = resolve_output_for_show(raw)
    text = path.read_text(encoding="utf-8", errors="replace")
    return bounded_text(text, 6000)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Engel Code Companion protected patch apply approval receipt.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="Show approval receipt folders and disabled approval/apply status.")
    sub.add_parser("list", help="List approval receipts.")
    validate = sub.add_parser("validate-dry-run", help="Validate one Phase 5 dry-run for approval receipt.")
    validate.add_argument("dry_run")
    receipt = sub.add_parser("receipt", help="Write a protected approval receipt. Does not approve or apply.")
    receipt.add_argument("dry_run")
    show = sub.add_parser("show", help="Show a bounded approval receipt.")
    show.add_argument("target")
    requirements = sub.add_parser("requirements", help="Show future apply requirements for a Phase 5 dry-run.")
    requirements.add_argument("dry_run")
    approve_stub = sub.add_parser("approve", help="Refuse approval collection in Phase 6.")
    approve_stub.add_argument("dry_run", nargs="?")
    apply_stub = sub.add_parser("apply", help="Refuse patch application in Phase 6.")
    apply_stub.add_argument("dry_run", nargs="?")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "status":
            print(render_status())
            return 0
        if args.command == "list":
            print(render_list())
            return 0
        if args.command == "validate-dry-run":
            validation = validate_dry_run_for_receipt(args.dry_run)
            print(render_validate(args.dry_run))
            return 0 if validation.valid else 2
        if args.command == "receipt":
            result = create_approval_receipt(args.dry_run)
            print("Protected patch apply approval receipt written:")
            print(result.receipt_json)
            print(result.receipt_markdown)
            print(APPROVAL_FINAL_DECISION)
            return 0
        if args.command == "show":
            print(render_show(args.target))
            return 0
        if args.command == "requirements":
            validation = validate_dry_run_for_receipt(args.dry_run)
            print(render_requirements(args.dry_run))
            return 0 if validation.valid else 2
        if args.command == "approve":
            print("Approval collection is not enabled in Phase 6.")
            return 2
        if args.command == "apply":
            print("Patch application is not enabled in Phase 6.")
            return 2
    except PatchApplyApprovalReceiptError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
