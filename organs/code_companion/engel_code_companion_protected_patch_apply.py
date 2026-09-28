from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import engel_code_companion_patch_apply_approval_receipt as approval_receipt
import engel_code_companion_patch_apply_dry_run as patch_apply_dry_run
import engel_code_companion_patch_bundle_draft as patch_bundle_draft
import engel_code_companion_patch_class_allowlist as patch_class_allowlist
import engel_global_password_gate as password_gate


PROJECT_ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
APPROVAL_ROOT = PROJECT_ROOT / "reports" / "code_companion_patch_apply_approvals"
APPROVAL_RECEIPTS = APPROVAL_ROOT / "receipts"
APPROVAL_EXAMPLES = APPROVAL_ROOT / "examples"
DRY_RUN_ROOT = PROJECT_ROOT / "reports" / "code_companion_patch_apply_dry_runs"
BUNDLE_ROOT = PROJECT_ROOT / "reports" / "code_companion_patch_bundles"
APPLY_ROOT = PROJECT_ROOT / "reports" / "code_companion_patch_applies"
RECEIPTS_DIR = APPLY_ROOT / "receipts"
BACKUPS_DIR = APPLY_ROOT / "backups"
ROLLBACK_DIR = APPLY_ROOT / "rollback"
EXAMPLES_DIR = APPLY_ROOT / "examples"

APPROVAL_TOKEN = "APPROVE_PRODUCT_PATCH"
PROTECTED_ACTION_ID = "run_code_companion_low_risk_patch_apply"

MAX_CHANGED_FILES = 3
MAX_BYTES_PER_CHANGE = 20 * 1024
MAX_TOTAL_PATCH_BYTES = 50 * 1024
MAX_INPUT_BYTES = 1024 * 1024
MAX_REPORT_CHARS = 22000

APPLY_FINAL_DECISION = "PROTECTED PATCH APPLIED WITH HUMAN APPROVAL"
REFUSAL_FINAL_DECISION = "PROTECTED PATCH APPLY REFUSED \u2014 NOT APPLIED"
PASSWORD_GATE_REQUIRED_MESSAGE = "Protected password gate integration is required before real apply."

ALLOWED_PREFIXES = [
    "reports\\",
]

DENIED_PREFIXES = [
    "prompts\\",
    "routes\\",
    "live\\",
    "staging\\",
    "scripts\\",
    "tools\\",
    "mobile\\engel_remote_worker\\android\\",
    "memory\\",
]

DENIED_FILENAMES = {
    "engel_app.py",
    "engel_research_office.py",
    "engel_global_password_gate.py",
    "engel_protected_action_registry.py",
    "scripts\\codex_verify.ps1",
}

BLOCKED_SUFFIXES = {
    ".exe",
    ".dll",
    ".msi",
    ".bat",
    ".cmd",
    ".ps1",
    ".sh",
    ".zip",
    ".7z",
    ".rar",
    ".db",
    ".sqlite",
    ".bin",
    ".pyd",
}

REQUIRED_BLOCKED_ACTIONS = [
    "apply_patch_without_approval",
    "edit_source_without_approval",
    "execute_commands_from_bundle",
    "mutate_routes",
    "mutate_queue",
    "write_trusted_memory",
    "auto_apply",
    "provider_call",
    "browser_task",
    "download",
    "install_package",
]


class ProtectedPatchApplyError(ValueError):
    pass


@dataclass
class ChainValidation:
    approval_receipt_path: str
    valid: bool
    approval_receipt_id: str | None
    source_dry_run_id: str | None
    source_bundle_id: str | None
    errors: list[str]
    warnings: list[str]


@dataclass
class ApplyRefusal(Exception):
    reason: str
    chain: dict[str, Any] | None = None


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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


def safe_slug(value: str, limit: int = 150) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip()).strip("._-")
    return (cleaned or "protected_patch_apply")[:limit]


def timestamp_slug(value: str) -> str:
    return safe_slug(value.replace(":", "").replace("-", ""), 40)


def bounded_text(value: Any, limit: int = 1800) -> str:
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


def ensure_folders(root: Path = APPLY_ROOT) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "receipts").mkdir(parents=True, exist_ok=True)
    (root / "backups").mkdir(parents=True, exist_ok=True)
    (root / "rollback").mkdir(parents=True, exist_ok=True)
    (root / "examples").mkdir(parents=True, exist_ok=True)


def load_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProtectedPatchApplyError(f"could not read JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ProtectedPatchApplyError("JSON root must be an object")
    return payload


def resolve_approval_receipt_path(raw: str | Path) -> Path:
    text = str(raw)
    if not text or text.startswith(("http://", "https://", "\\\\")):
        raise ProtectedPatchApplyError("approval receipt path must be an explicit local Phase 6 receipt path")
    if any(marker in text for marker in ("*", "?", "[")):
        raise ProtectedPatchApplyError("wildcards are not allowed")
    path = Path(text)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    resolved = path.resolve(strict=False)
    if resolved.is_dir():
        raise ProtectedPatchApplyError("approval receipt input must be a receipt JSON file")
    if not resolved.exists() or not resolved.is_file():
        raise ProtectedPatchApplyError("approval receipt does not exist")
    if not is_relative_to(resolved, PROJECT_ROOT):
        raise ProtectedPatchApplyError("approval receipt must stay inside Engel App")
    if not (is_relative_to(resolved, APPROVAL_RECEIPTS) or is_relative_to(resolved, APPROVAL_EXAMPLES)):
        raise ProtectedPatchApplyError("Phase 7 accepts Phase 6 approval receipts only")
    if resolved.suffix.lower() != ".json":
        raise ProtectedPatchApplyError("approval receipt must be JSON")
    if resolved.stat().st_size > MAX_INPUT_BYTES:
        raise ProtectedPatchApplyError(f"approval receipt exceeds max size of {MAX_INPUT_BYTES} bytes")
    return resolved


def resolve_project_file_from_receipt(raw: Any, expected_root: Path) -> Path:
    if not isinstance(raw, str) or not raw.strip():
        raise ProtectedPatchApplyError("prior artifact path is missing")
    path = Path(raw)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    resolved = path.resolve(strict=False)
    if not resolved.exists() or not resolved.is_file():
        raise ProtectedPatchApplyError("prior artifact does not exist: " + str(raw))
    if not is_relative_to(resolved, expected_root):
        raise ProtectedPatchApplyError("prior artifact escaped expected phase folder: " + str(raw))
    if resolved.suffix.lower() != ".json":
        raise ProtectedPatchApplyError("prior artifact must be JSON: " + str(raw))
    if resolved.stat().st_size > MAX_INPUT_BYTES:
        raise ProtectedPatchApplyError("prior artifact exceeds max size")
    return resolved


def validate_approval_payload(payload: dict[str, Any]) -> list[str]:
    errors = approval_receipt.validate_approval_receipt_payload(payload)
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
            errors.append(f"approval receipt {field} must be false before Phase 7 apply")
    for field in expected_true:
        if payload.get(field) is not True:
            errors.append(f"approval receipt {field} must be true before Phase 7 apply")
    return errors


def load_validated_chain(raw_receipt: str | Path) -> tuple[Path, dict[str, Any], Path, dict[str, Any], Path, dict[str, Any], list[str]]:
    warnings: list[str] = []
    receipt_path = resolve_approval_receipt_path(raw_receipt)
    receipt = load_json_object(receipt_path)
    errors = validate_approval_payload(receipt)
    if errors:
        raise ProtectedPatchApplyError("approval receipt is invalid: " + "; ".join(errors))
    dry_run_path = resolve_project_file_from_receipt(receipt.get("source_dry_run_path"), DRY_RUN_ROOT)
    dry_run = load_json_object(dry_run_path)
    dry_errors = patch_apply_dry_run.validate_dry_run_payload(dry_run)
    if dry_errors:
        raise ProtectedPatchApplyError("source dry-run is invalid: " + "; ".join(dry_errors))
    if receipt.get("source_dry_run_hash") not in {"example_not_a_real_source_hash", sha256_file(dry_run_path)}:
        raise ProtectedPatchApplyError("approval receipt source dry-run hash mismatch")
    bundle_path = resolve_project_file_from_receipt(dry_run.get("source_bundle_path"), BUNDLE_ROOT)
    bundle = load_json_object(bundle_path)
    bundle_validation = patch_bundle_draft.validate_bundle_file(bundle_path)
    if not bundle_validation.valid:
        raise ProtectedPatchApplyError("source bundle is invalid: " + "; ".join(bundle_validation.errors))
    if dry_run.get("source_bundle_hash") not in {"example_not_a_real_source_hash", sha256_file(bundle_path)}:
        raise ProtectedPatchApplyError("dry-run source bundle hash mismatch")
    if is_relative_to(receipt_path, APPROVAL_EXAMPLES):
        warnings.append("example approval receipt is valid for validation only and cannot be applied")
    return receipt_path, receipt, dry_run_path, dry_run, bundle_path, bundle, warnings


def validate_chain(raw_receipt: str | Path) -> ChainValidation:
    try:
        receipt_path, receipt, _dry_run_path, dry_run, _bundle_path, bundle, warnings = load_validated_chain(raw_receipt)
    except ProtectedPatchApplyError as exc:
        return ChainValidation(str(raw_receipt), False, None, None, None, [str(exc)], [])
    return ChainValidation(
        approval_receipt_path=project_relative(receipt_path),
        valid=True,
        approval_receipt_id=str(receipt.get("approval_receipt_id")),
        source_dry_run_id=str(dry_run.get("dry_run_id")),
        source_bundle_id=str(bundle.get("bundle_id")),
        errors=[],
        warnings=warnings,
    )


def target_path_info(target_file: str) -> dict[str, Any]:
    raw = str(target_file or "").strip().replace("/", "\\")
    info: dict[str, Any] = {
        "target_file": raw,
        "inside_project": False,
        "allowed": False,
        "denied_reason": "",
        "exists": False,
        "patch_class": "default_deny",
        "policy_allowed": False,
    }
    if not raw or raw in {"(undetermined)", "(no target file specified)"}:
        info["denied_reason"] = "target file is undetermined"
        return info
    if raw.startswith(("http://", "https://", "\\\\")) or any(marker in raw for marker in ("*", "?", "[")):
        info["denied_reason"] = "target file is not a bounded local path"
        return info
    path = Path(raw)
    if path.is_absolute():
        resolved = path.resolve(strict=False)
    else:
        resolved = (PROJECT_ROOT / path).resolve(strict=False)
    if not is_relative_to(resolved, PROJECT_ROOT):
        info["denied_reason"] = "target file escapes project"
        return info
    rel = project_relative(resolved)
    lower = rel.lower()
    info["target_file"] = rel
    info["inside_project"] = True
    info["exists"] = resolved.exists()
    policy = patch_class_allowlist.classify_path(rel)
    info["patch_class"] = policy.get("patch_class", "default_deny")
    info["policy_allowed"] = bool(policy.get("allowed"))
    info["policy_reason"] = policy.get("reason", "")
    info["policy_required_constraints"] = policy.get("required_constraints", [])
    if not policy.get("allowed"):
        info["denied_reason"] = "target denied by Phase 11 patch class allowlist: " + str(policy.get("reason", "default deny"))
        return info
    if any(lower.startswith(prefix) for prefix in DENIED_PREFIXES):
        info["denied_reason"] = "target path is protected by default deny list"
        return info
    if lower in DENIED_FILENAMES or (("\\" not in lower) and lower.endswith(".py")):
        info["denied_reason"] = "root runtime/source files are denied in MVP"
        return info
    if resolved.suffix.lower() in BLOCKED_SUFFIXES:
        info["denied_reason"] = "binary/executable target suffix is denied"
        return info
    if not any(lower.startswith(prefix) for prefix in ALLOWED_PREFIXES):
        info["denied_reason"] = "target path is outside Phase 7 MVP allowlist"
        return info
    if resolved.exists() and not resolved.is_file():
        info["denied_reason"] = "target exists but is not a regular file"
        return info
    info["allowed"] = True
    return info


def extract_replacement_content(text: str) -> str | None:
    marker = "PHASE7_REPLACEMENT_CONTENT"
    if marker not in text:
        return None
    start = text.find(marker) + len(marker)
    remainder = text[start:].lstrip()
    fence = re.search(r"```(?:text|markdown|md)?\s*\n(.*?)\n```", remainder, re.DOTALL | re.IGNORECASE)
    if fence:
        return fence.group(1)
    return None


def collect_change_specs(bundle_path: Path, bundle: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    errors: list[str] = []
    changes: list[dict[str, Any]] = []
    drafts = bundle.get("proposed_file_drafts")
    if not isinstance(drafts, list):
        return [], ["bundle proposed_file_drafts must be a list"]
    for index, draft in enumerate(drafts, start=1):
        if not isinstance(draft, dict):
            errors.append(f"proposed_file_drafts[{index}] is not an object")
            continue
        if len(changes) >= MAX_CHANGED_FILES:
            errors.append(f"changed file count exceeds MVP limit of {MAX_CHANGED_FILES}")
            break
        if draft.get("preview_only") is not True or draft.get("source_file_modified") is not False:
            errors.append(f"proposed_file_drafts[{index}] is not preview-only/source-unmodified")
            continue
        change_type = str(draft.get("change_type", "unknown"))
        if change_type in {"remove", "unknown"}:
            errors.append(f"proposed_file_drafts[{index}] change_type {change_type} is not applyable in MVP")
            continue
        target_info = target_path_info(str(draft.get("target_file", "")))
        if not target_info.get("allowed"):
            errors.append(f"target rejected: {target_info.get('target_file')} / {target_info.get('denied_reason')}")
            continue
        draft_file = draft.get("draft_file")
        if not isinstance(draft_file, str) or not draft_file.startswith("proposed_files/"):
            errors.append(f"proposed_file_drafts[{index}] draft_file must stay under proposed_files/")
            continue
        draft_path = (bundle_path.parent / draft_file.replace("/", "\\")).resolve(strict=False)
        if not is_relative_to(draft_path, bundle_path.parent / "proposed_files"):
            errors.append(f"proposed_file_drafts[{index}] draft_file escaped proposed_files")
            continue
        if not draft_path.exists() or not draft_path.is_file():
            errors.append(f"draft file missing: {draft_file}")
            continue
        if draft_path.suffix.lower() not in {".md", ".txt"}:
            errors.append(f"draft file must be preview .md/.txt: {draft_file}")
            continue
        if draft_path.stat().st_size > MAX_BYTES_PER_CHANGE:
            errors.append(f"draft file exceeds per-change limit: {draft_file}")
            continue
        text = draft_path.read_text(encoding="utf-8", errors="strict")
        if "PREVIEW ONLY" not in text or "NOT APPLIED" not in text:
            errors.append(f"draft file missing preview-only banner: {draft_file}")
            continue
        replacement = extract_replacement_content(text)
        if replacement is None:
            errors.append(f"draft file lacks explicit PHASE7_REPLACEMENT_CONTENT fenced block: {draft_file}")
            continue
        encoded = replacement.encode("utf-8")
        if len(encoded) > MAX_BYTES_PER_CHANGE:
            errors.append(f"replacement content exceeds per-change limit: {draft_file}")
            continue
        if "\x00" in replacement:
            errors.append(f"replacement content contains binary null: {draft_file}")
            continue
        changes.append(
            {
                "target_file": target_info["target_file"],
                "target_path": str((PROJECT_ROOT / str(target_info["target_file"])).resolve(strict=False)),
                "patch_class": target_info.get("patch_class", "default_deny"),
                "change_type": change_type,
                "content": replacement,
                "bytes": len(encoded),
                "draft_file": project_relative(draft_path),
            }
        )
    total = sum(int(item["bytes"]) for item in changes)
    if total > MAX_TOTAL_PATCH_BYTES:
        errors.append(f"total patch bytes exceed MVP limit of {MAX_TOTAL_PATCH_BYTES}")
    return changes, errors


def preflight_context(raw_receipt: str | Path) -> dict[str, Any]:
    receipt_path, receipt, dry_run_path, dry_run, bundle_path, bundle, warnings = load_validated_chain(raw_receipt)
    changes, change_errors = collect_change_specs(bundle_path, bundle)
    safe_target_count = len(changes)
    errors = list(change_errors)
    if is_relative_to(receipt_path, APPROVAL_EXAMPLES):
        errors.append("example approval receipts cannot be applied")
    if not changes:
        errors.append("no concrete Phase 7 replacement changes are available")
    return {
        "approval_receipt_path": project_relative(receipt_path),
        "approval_receipt_id": receipt.get("approval_receipt_id"),
        "source_dry_run_path": project_relative(dry_run_path),
        "source_dry_run_id": dry_run.get("dry_run_id"),
        "source_bundle_path": project_relative(bundle_path),
        "source_bundle_id": bundle.get("bundle_id"),
        "valid_chain": True,
        "safe_target_count": safe_target_count,
        "changes": [{key: value for key, value in change.items() if key != "content"} for change in changes],
        "errors": errors,
        "warnings": warnings,
        "eligible_for_apply_attempt": not errors,
        "approval_token_required": APPROVAL_TOKEN,
        "password_gate_required": True,
        "protected_action_id": PROTECTED_ACTION_ID,
        "pre_apply_verifier_required": True,
        "post_apply_verifier_required": True,
        "auto_apply": False,
    }


def apply_id_for(receipt_id: str, created_at: str) -> str:
    return f"{timestamp_slug(created_at)}_{safe_slug(receipt_id, 90)}_protected_patch_apply"


def receipt_path_for(payload: dict[str, Any], receipts_dir: Path = RECEIPTS_DIR) -> Path:
    return receipts_dir / f"PROTECTED_PATCH_APPLY_{safe_slug(str(payload.get('apply_id', 'apply')))}.json"


def receipt_markdown_path_for(payload: dict[str, Any], receipts_dir: Path = RECEIPTS_DIR) -> Path:
    return receipts_dir / f"PROTECTED_PATCH_APPLY_{safe_slug(str(payload.get('apply_id', 'apply')))}.md"


def rollback_json_path_for(apply_id: str, rollback_dir: Path = ROLLBACK_DIR) -> Path:
    return rollback_dir / f"{safe_slug(apply_id)}_rollback.json"


def rollback_markdown_path_for(apply_id: str, rollback_dir: Path = ROLLBACK_DIR) -> Path:
    return rollback_dir / f"{safe_slug(apply_id)}_rollback.md"


def base_apply_payload(chain: dict[str, Any], created_at: str | None = None) -> dict[str, Any]:
    stamp = created_at or now_utc()
    apply_id = apply_id_for(str(chain.get("approval_receipt_id", "unknown_receipt")), stamp)
    return {
        "apply_version": "1",
        "apply_id": apply_id,
        "created_at": stamp,
        "created_by": "Engel Code Companion",
        "source_approval_receipt_path": chain.get("approval_receipt_path"),
        "source_dry_run_path": chain.get("source_dry_run_path"),
        "source_bundle_path": chain.get("source_bundle_path"),
        "human_confirmed": False,
        "approval_token_verified": False,
        "password_gate_verified": False,
        "pre_apply_verifier_passed": False,
        "post_apply_verifier_passed": False,
        "trusted_memory_written": False,
        "routes_mutated": False,
        "queues_mutated": False,
        "provider_calls_made": False,
        "patch_applied": False,
        "safe_to_auto_apply": False,
        "auto_apply": False,
        "files_changed": [],
        "backups": [],
        "hashes_before": [],
        "hashes_after": [],
        "rollback_available": False,
        "refusal_reason": "",
        "final_decision": REFUSAL_FINAL_DECISION,
    }


def render_apply_markdown(payload: dict[str, Any]) -> str:
    files = "\n".join(f"- `{item}`" for item in payload.get("files_changed", [])) or "- none"
    backups = "\n".join(f"- `{item.get('backup_path')}` for `{item.get('target_file')}`" for item in payload.get("backups", []) if isinstance(item, dict)) or "- none"
    text = f"""# Code Companion Protected Patch Apply Receipt

## Receipt

- apply_id: `{payload.get("apply_id")}`
- created_at: `{payload.get("created_at")}`
- final_decision: **{payload.get("final_decision")}**
- refusal_reason: `{payload.get("refusal_reason") or "(none)"}`

## Source Chain

- approval receipt: `{payload.get("source_approval_receipt_path")}`
- dry-run: `{payload.get("source_dry_run_path")}`
- bundle: `{payload.get("source_bundle_path")}`

## Gates

- human_confirmed: `{payload.get("human_confirmed")}`
- approval_token_verified: `{payload.get("approval_token_verified")}`
- password_gate_verified: `{payload.get("password_gate_verified")}`
- pre_apply_verifier_passed: `{payload.get("pre_apply_verifier_passed")}`
- post_apply_verifier_passed: `{payload.get("post_apply_verifier_passed")}`

## Files Changed

{files}

## Backups

{backups}

## Safety

- trusted_memory_written: `{payload.get("trusted_memory_written")}`
- routes_mutated: `{payload.get("routes_mutated")}`
- queues_mutated: `{payload.get("queues_mutated")}`
- provider_calls_made: `{payload.get("provider_calls_made")}`
- safe_to_auto_apply: `{payload.get("safe_to_auto_apply")}`
- auto_apply: `{payload.get("auto_apply")}`

No approval token or password is stored in this receipt.
"""
    if len(text) > MAX_REPORT_CHARS:
        text = text[:MAX_REPORT_CHARS] + "\n[apply receipt truncated]\n"
    return text


def write_apply_receipt(payload: dict[str, Any], receipts_dir: Path = RECEIPTS_DIR) -> tuple[Path, Path]:
    receipts_dir.mkdir(parents=True, exist_ok=True)
    json_path = receipt_path_for(payload, receipts_dir)
    markdown_path = receipt_markdown_path_for(payload, receipts_dir)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(render_apply_markdown(payload), encoding="utf-8")
    return json_path, markdown_path


def refusal_receipt(reason: str, chain: dict[str, Any] | None, *, receipts_dir: Path = RECEIPTS_DIR, created_at: str | None = None) -> dict[str, Any]:
    safe_chain = chain or {
        "approval_receipt_id": "invalid_or_missing_chain",
        "approval_receipt_path": "",
        "source_dry_run_path": "",
        "source_bundle_path": "",
    }
    payload = base_apply_payload(safe_chain, created_at=created_at)
    payload["refusal_reason"] = reason
    payload["final_decision"] = REFUSAL_FINAL_DECISION
    write_apply_receipt(payload, receipts_dir)
    return payload


def backup_targets(apply_id: str, changes: list[dict[str, Any]], backups_dir: Path = BACKUPS_DIR) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    backup_root = backups_dir / safe_slug(apply_id)
    backup_root.mkdir(parents=True, exist_ok=False)
    backups: list[dict[str, Any]] = []
    hashes_before: list[dict[str, Any]] = []
    for change in changes:
        target_file = str(change["target_file"])
        target_path = Path(str(change["target_path"]))
        backup_path = backup_root / safe_slug(target_file.replace("\\", "__"), 140)
        existed = target_path.exists()
        before_hash = sha256_file(target_path) if existed else None
        if existed:
            shutil.copy2(target_path, backup_path)
        else:
            backup_path.write_text("", encoding="utf-8")
        backups.append({"target_file": target_file, "backup_path": project_relative(backup_path), "existed": existed})
        hashes_before.append({"target_file": target_file, "sha256_before": before_hash, "existed": existed})
    return backups, hashes_before


def write_changes(changes: list[dict[str, Any]]) -> list[str]:
    changed: list[str] = []
    for change in changes:
        target_path = Path(str(change["target_path"]))
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(str(change["content"]), encoding="utf-8")
        changed.append(str(change["target_file"]))
    return changed


def rollback_metadata(payload: dict[str, Any], rollback_dir: Path = ROLLBACK_DIR) -> tuple[Path, Path]:
    rollback_dir.mkdir(parents=True, exist_ok=True)
    apply_id = str(payload.get("apply_id", "apply"))
    json_path = rollback_json_path_for(apply_id, rollback_dir)
    md_path = rollback_markdown_path_for(apply_id, rollback_dir)
    rollback = {
        "apply_id": apply_id,
        "files_changed": payload.get("files_changed", []),
        "backups": payload.get("backups", []),
        "hashes_before": payload.get("hashes_before", []),
        "hashes_after": payload.get("hashes_after", []),
        "rollback_available": payload.get("rollback_available", False),
        "manual_only": True,
        "note": "Rollback is manual unless a future protected rollback phase is implemented.",
    }
    json_path.write_text(json.dumps(rollback, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# Code Companion Protected Patch Apply Rollback Info",
        "",
        f"apply_id: `{apply_id}`",
        "",
        "Rollback is manual unless a future protected rollback phase is implemented.",
        "",
        "## Files Changed",
    ]
    lines.extend(f"- `{item}`" for item in payload.get("files_changed", []))
    lines.extend(["", "## Backups"])
    for item in payload.get("backups", []):
        if isinstance(item, dict):
            lines.append(f"- `{item.get('target_file')}` -> `{item.get('backup_path')}`")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def verify_password_gate(password_prompt: bool, config_path: str | Path | None = None) -> None:
    summary = password_gate.protected_action_gate_summary(PROTECTED_ACTION_ID)
    if not summary.get("ok") or summary.get("current_state") == "blocked":
        raise ApplyRefusal("Protected action registry did not allow the Code Companion low-risk patch apply action.")
    if not password_gate.is_global_password_gate_configured(config_path):
        raise ApplyRefusal(PASSWORD_GATE_REQUIRED_MESSAGE)
    if not password_prompt:
        raise ApplyRefusal(PASSWORD_GATE_REQUIRED_MESSAGE)
    try:
        password_gate.prompt_and_require_action(PROTECTED_ACTION_ID, config_path)
    except password_gate.PasswordGateError as exc:
        raise ApplyRefusal("Protected password gate did not pass: " + str(exc)) from exc


def run_pre_apply_verifiers() -> None:
    raise ApplyRefusal("Pre-apply verifier execution is not enabled for automatic apply in Phase 7.")


def run_post_apply_verifiers() -> None:
    raise ApplyRefusal("Post-apply verifier execution is not enabled for automatic apply in Phase 7.")


def protected_apply(
    raw_receipt: str | Path,
    *,
    approval_token: str | None,
    confirm_human_approved: bool,
    password_prompt: bool = False,
    password_config: str | Path | None = None,
    receipts_dir: Path = RECEIPTS_DIR,
    backups_dir: Path = BACKUPS_DIR,
    rollback_dir: Path = ROLLBACK_DIR,
    created_at: str | None = None,
) -> dict[str, Any]:
    ensure_folders()
    chain: dict[str, Any] | None = None
    try:
        context = preflight_context(raw_receipt)
        chain = context
        if not confirm_human_approved:
            raise ApplyRefusal("Human confirmation is required before protected apply.", chain)
        if str(approval_token or "").strip() != APPROVAL_TOKEN:
            raise ApplyRefusal("Explicit approval token APPROVE_PRODUCT_PATCH is required.", chain)
        if context["errors"]:
            raise ApplyRefusal("Apply preflight failed: " + "; ".join(context["errors"]), chain)
        verify_password_gate(password_prompt, password_config)
        run_pre_apply_verifiers()
        stamp = created_at or now_utc()
        payload = base_apply_payload(chain, created_at=stamp)
        payload["human_confirmed"] = True
        payload["approval_token_verified"] = True
        payload["password_gate_verified"] = True
        payload["pre_apply_verifier_passed"] = True
        _receipt_path, _receipt, _dry_path, _dry, bundle_path, bundle, _warnings = load_validated_chain(raw_receipt)
        changes, change_errors = collect_change_specs(bundle_path, bundle)
        if change_errors:
            raise ApplyRefusal("Apply change collection failed: " + "; ".join(change_errors), chain)
        backups, hashes_before = backup_targets(str(payload["apply_id"]), changes, backups_dir)
        payload["backups"] = backups
        payload["hashes_before"] = hashes_before
        payload["files_changed"] = write_changes(changes)
        payload["hashes_after"] = [{"target_file": item, "sha256_after": sha256_file(PROJECT_ROOT / item)} for item in payload["files_changed"]]
        run_post_apply_verifiers()
        payload["post_apply_verifier_passed"] = True
        payload["patch_applied"] = True
        payload["rollback_available"] = True
        payload["final_decision"] = APPLY_FINAL_DECISION
        rollback_metadata(payload, rollback_dir)
        write_apply_receipt(payload, receipts_dir)
        return payload
    except ApplyRefusal as exc:
        return refusal_receipt(exc.reason, exc.chain or chain, receipts_dir=receipts_dir, created_at=created_at)
    except ProtectedPatchApplyError as exc:
        return refusal_receipt(str(exc), chain, receipts_dir=receipts_dir, created_at=created_at)


def apply_receipt_files(receipts_dir: Path = RECEIPTS_DIR) -> list[Path]:
    if not receipts_dir.exists():
        return []
    return sorted([path for path in receipts_dir.iterdir() if path.is_file() and path.suffix.lower() == ".json"], key=lambda item: item.name.lower())


def render_status(root: Path = APPLY_ROOT) -> str:
    ensure_folders(root)
    return "\n".join(
        [
            "Code Companion protected patch apply MVP status",
            f"Apply root: {project_relative(root)}",
            f"Receipts: {project_relative(root / 'receipts')}",
            f"Backups: {project_relative(root / 'backups')}",
            f"Rollback: {project_relative(root / 'rollback')}",
            f"Examples: {project_relative(root / 'examples')}",
            f"Apply receipt count: {len(apply_receipt_files(root / 'receipts'))}",
            f"approval_token_required: {APPROVAL_TOKEN}",
            f"protected_action_id: {PROTECTED_ACTION_ID}",
            f"password_gate_configured: {password_gate.is_global_password_gate_configured()}",
            "auto_apply: false",
            "safe_to_auto_apply: false",
            "max_changed_files: 3",
            "max_bytes_per_change: 20480",
            "max_total_patch_bytes: 51200",
            "real_apply_enabled: false_until_password_gate_and_verifier_runner_are_satisfied",
        ]
    )


def render_validation(validation: ChainValidation) -> str:
    lines = [
        "Code Companion protected patch apply validation",
        f"approval_receipt_path: {validation.approval_receipt_path}",
        f"valid: {validation.valid}",
        f"approval_receipt_id: {validation.approval_receipt_id or '(none)'}",
        f"source_dry_run_id: {validation.source_dry_run_id or '(none)'}",
        f"source_bundle_id: {validation.source_bundle_id or '(none)'}",
    ]
    if validation.errors:
        lines.append("errors:")
        lines.extend(f"- {error}" for error in validation.errors)
    if validation.warnings:
        lines.append("warnings:")
        lines.extend(f"- {warning}" for warning in validation.warnings)
    return "\n".join(lines)


def render_preflight(raw_receipt: str | Path) -> str:
    try:
        context = preflight_context(raw_receipt)
    except ProtectedPatchApplyError as exc:
        return "Apply preflight valid: false\nerrors:\n- " + str(exc)
    lines = [
        "Code Companion protected patch apply preflight",
        f"approval_receipt_id: {context.get('approval_receipt_id')}",
        f"source_dry_run_id: {context.get('source_dry_run_id')}",
        f"source_bundle_id: {context.get('source_bundle_id')}",
        f"eligible_for_apply_attempt: {context.get('eligible_for_apply_attempt')}",
        f"approval_token_required: {context.get('approval_token_required')}",
        f"password_gate_required: {context.get('password_gate_required')}",
        f"pre_apply_verifier_required: {context.get('pre_apply_verifier_required')}",
        f"post_apply_verifier_required: {context.get('post_apply_verifier_required')}",
        "auto_apply: false",
        "",
        "Changes:",
    ]
    if context.get("changes"):
        for change in context["changes"]:
            lines.append(f"- `{change.get('target_file')}` bytes={change.get('bytes')} draft={change.get('draft_file')}")
    else:
        lines.append("- none")
    if context.get("errors"):
        lines.append("errors:")
        lines.extend(f"- {error}" for error in context["errors"])
    if context.get("warnings"):
        lines.append("warnings:")
        lines.extend(f"- {warning}" for warning in context["warnings"])
    return "\n".join(lines)


def resolve_apply_output(raw: str | Path) -> Path:
    text = str(raw)
    path = Path(text)
    candidates: list[Path] = []
    if path.is_absolute() or "\\" in text or "/" in text:
        candidates.append(path if path.is_absolute() else PROJECT_ROOT / path)
    else:
        slug = safe_slug(text)
        candidates.extend(sorted(RECEIPTS_DIR.glob(f"*{slug}*.md")))
        candidates.extend(sorted(RECEIPTS_DIR.glob(f"*{slug}*.json")))
    for candidate in candidates:
        resolved = candidate.resolve(strict=False)
        if resolved.exists() and resolved.is_file() and is_relative_to(resolved, APPLY_ROOT):
            return resolved
    raise ProtectedPatchApplyError("apply receipt not found")


def render_show(raw: str | Path) -> str:
    path = resolve_apply_output(raw)
    return bounded_text(path.read_text(encoding="utf-8", errors="replace"), 7000)


def render_rollback_info(raw: str | Path) -> str:
    path = resolve_apply_output(raw)
    payload = load_json_object(path) if path.suffix.lower() == ".json" else None
    apply_id = str(payload.get("apply_id")) if payload else safe_slug(path.stem)
    rollback_json = rollback_json_path_for(apply_id)
    rollback_md = rollback_markdown_path_for(apply_id)
    if rollback_md.exists():
        return bounded_text(rollback_md.read_text(encoding="utf-8", errors="replace"), 7000)
    return "\n".join(
        [
            "Rollback metadata not found.",
            f"apply_id: {apply_id}",
            "Rollback is manual unless a future protected rollback phase is implemented.",
            f"expected_json: {project_relative(rollback_json)}",
            f"expected_markdown: {project_relative(rollback_md)}",
        ]
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Engel Code Companion protected patch apply MVP.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="Show protected patch apply status.")
    validate = sub.add_parser("validate", help="Validate a Phase 6 approval receipt chain.")
    validate.add_argument("approval_receipt")
    preflight = sub.add_parser("preflight", help="Run non-mutating protected apply preflight.")
    preflight.add_argument("approval_receipt")
    apply_cmd = sub.add_parser("apply", help="Attempt protected tiny apply; fails closed unless all gates pass.")
    apply_cmd.add_argument("approval_receipt")
    apply_cmd.add_argument("--approval-token", default="")
    apply_cmd.add_argument("--confirm-human-approved", action="store_true")
    apply_cmd.add_argument("--password-prompt", action="store_true", help="Use the existing hidden password prompt. Never pass a password on the command line.")
    show = sub.add_parser("show", help="Show an apply receipt.")
    show.add_argument("target")
    rollback = sub.add_parser("rollback-info", help="Show rollback metadata for an apply receipt.")
    rollback.add_argument("target")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "status":
            print(render_status())
            return 0
        if args.command == "validate":
            validation = validate_chain(args.approval_receipt)
            print(render_validation(validation))
            return 0 if validation.valid else 2
        if args.command == "preflight":
            print(render_preflight(args.approval_receipt))
            try:
                context = preflight_context(args.approval_receipt)
                return 0 if context.get("eligible_for_apply_attempt") else 2
            except ProtectedPatchApplyError:
                return 2
        if args.command == "apply":
            result = protected_apply(
                args.approval_receipt,
                approval_token=args.approval_token,
                confirm_human_approved=bool(args.confirm_human_approved),
                password_prompt=bool(args.password_prompt),
            )
            print(result.get("final_decision"))
            if result.get("refusal_reason"):
                print("Refusal:", result.get("refusal_reason"))
            print("apply_id:", result.get("apply_id"))
            return 0 if result.get("patch_applied") is True else 2
        if args.command == "show":
            print(render_show(args.target))
            return 0
        if args.command == "rollback-info":
            print(render_rollback_info(args.target))
            return 0
    except ProtectedPatchApplyError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
