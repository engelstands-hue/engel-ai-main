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

import engel_code_companion_patch_plan_preview as patch_plan_preview


PROJECT_ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
PLAN_ROOT = PROJECT_ROOT / "reports" / "code_companion_patch_plans"
PLAN_EXAMPLES = PLAN_ROOT / "examples"
BUNDLE_ROOT = PROJECT_ROOT / "reports" / "code_companion_patch_bundles"
EXAMPLES_DIR = BUNDLE_ROOT / "examples"
RECEIPTS_DIR = BUNDLE_ROOT / "receipts"

MAX_PLAN_BYTES = 512 * 1024
MAX_PREVIEW_CHARS = 1400
MAX_RECEIPT_CHARS = 14000
FINAL_DECISION = "PATCH BUNDLE DRAFT ONLY — NOT APPLIED"

REQUIRED_BLOCKED_ACTIONS = [
    "apply_patch",
    "edit_source",
    "execute_commands",
    "mutate_routes",
    "mutate_queue",
    "write_trusted_memory",
    "auto_apply",
    "provider_call",
    "browser_task",
    "download",
    "install_package",
]

REQUIRED_APPROVALS = [
    "human_review",
    "approval_token",
    "password_gate_for_protected_actions",
    "verifier_pass_required",
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
}

EXECUTABLE_SUFFIXES = {".py", ".ps1", ".bat", ".cmd", ".sh", ".exe", ".dll", ".pyd", ".js", ".dart"}
APPLY_SUFFIXES = {".patch", ".diff"}


class PatchBundleDraftError(ValueError):
    pass


@dataclass
class BundleValidation:
    bundle_path: str
    valid: bool
    bundle_id: str | None
    source_plan_id: str | None
    title: str | None
    status: str | None
    errors: list[str]
    warnings: list[str]


@dataclass
class BundleCreationResult:
    bundle_folder: str
    bundle_json: str
    receipt_path: str
    bundle: dict[str, Any]


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


def safe_slug(value: str, limit: int = 140) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip()).strip("._-")
    return (cleaned or "patch_bundle_draft")[:limit]


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


def ensure_folders(bundle_root: Path = BUNDLE_ROOT, receipts_dir: Path = RECEIPTS_DIR) -> None:
    bundle_root.mkdir(parents=True, exist_ok=True)
    (bundle_root / "examples").mkdir(parents=True, exist_ok=True)
    receipts_dir.mkdir(parents=True, exist_ok=True)


def risk_flags_for_text(text: str) -> list[str]:
    flags: list[str] = []
    for flag, pattern in RISK_PATTERNS.items():
        if re.search(pattern, text, re.IGNORECASE):
            flags.append(flag)
    return sorted(set(flags))


def resolve_plan_path(raw_path: str | Path) -> Path:
    text = str(raw_path)
    if not text or text.startswith(("http://", "https://", "\\\\")):
        raise PatchBundleDraftError("patch plan path must be an explicit local file")
    if any(marker in text for marker in ("*", "?", "[")):
        raise PatchBundleDraftError("wildcards are not allowed")
    path = Path(text)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    resolved = path.resolve(strict=False)
    if not resolved.exists() or not resolved.is_file():
        raise PatchBundleDraftError("patch plan file does not exist")
    if not is_relative_to(resolved, PROJECT_ROOT):
        raise PatchBundleDraftError("patch plan file must stay inside Engel App")
    if not (is_relative_to(resolved, PLAN_ROOT) or is_relative_to(resolved, PLAN_EXAMPLES)):
        raise PatchBundleDraftError("Phase 3 accepts Phase 2 patch plan preview files only")
    if resolved.suffix.lower() != ".json":
        raise PatchBundleDraftError("patch plan must be a JSON file")
    if resolved.stat().st_size > MAX_PLAN_BYTES:
        raise PatchBundleDraftError(f"patch plan file exceeds max bundle input size of {MAX_PLAN_BYTES} bytes")
    return resolved


def load_plan_payload(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PatchBundleDraftError(f"could not read patch plan JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise PatchBundleDraftError("patch plan JSON root must be an object")
    return payload


def validate_source_plan(path: Path) -> dict[str, Any]:
    validation = patch_plan_preview.validate_plan_file(path)
    if not validation.valid:
        raise PatchBundleDraftError("source patch plan is invalid: " + "; ".join(validation.errors))
    payload = load_plan_payload(path)
    if payload.get("trust_level") != "untrusted_until_human_review":
        raise PatchBundleDraftError("source patch plan must remain untrusted_until_human_review")
    if payload.get("status") != "draft_plan_preview":
        raise PatchBundleDraftError("source patch plan must be draft_plan_preview")
    if payload.get("requires_review") is not True:
        raise PatchBundleDraftError("source patch plan must require review")
    if payload.get("safe_to_auto_apply") is not False:
        raise PatchBundleDraftError("source patch plan must not be safe to auto-apply")
    if payload.get("patch_applied") is not False:
        raise PatchBundleDraftError("source patch plan must not be marked patch_applied")
    return payload


def bundle_id_for(plan_id: str, created_at: str) -> str:
    return f"{timestamp_slug(created_at)}_{safe_slug(plan_id, 100)}_patch_bundle_draft"


def normalize_target_files(plan: dict[str, Any]) -> list[str]:
    found: list[str] = []
    likely_files = plan.get("likely_files")
    if isinstance(likely_files, list):
        for item in likely_files:
            if isinstance(item, str):
                found.append(item)
    proposed_changes = plan.get("proposed_changes")
    if isinstance(proposed_changes, list):
        for change in proposed_changes:
            if isinstance(change, dict) and isinstance(change.get("target_file"), str):
                found.append(change["target_file"])
    normalized: list[str] = []
    for item in found:
        text = item.strip().replace("/", "\\")
        if not text or text == "(undetermined)":
            continue
        if text.startswith(("http://", "https://", "\\\\")):
            continue
        if any(marker in text for marker in ("*", "?", "[")):
            continue
        path = Path(text)
        if path.is_absolute():
            resolved = path.resolve(strict=False)
            if not is_relative_to(resolved, PROJECT_ROOT):
                continue
            text = project_relative(resolved)
        if text not in normalized:
            normalized.append(text[:180])
        if len(normalized) >= 20:
            break
    return normalized


def source_path_status(target_file: str) -> str:
    if target_file in {"(undetermined)", "(no target file specified)"}:
        return "unverified"
    path = Path(target_file)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    resolved = path.resolve(strict=False)
    if not is_relative_to(resolved, PROJECT_ROOT):
        return "outside_project_rejected"
    return "exists" if resolved.exists() else "missing_or_unverified"


def proposed_file_name(target_file: str, index: int) -> str:
    base = target_file
    if base in {"(undetermined)", "(no target file specified)"}:
        base = f"undetermined_{index}"
    safe = safe_slug(base.replace("\\", "__").replace("/", "__"), 120)
    return f"{index:02d}_{safe}.proposed.md"


def normalize_verification_plan(plan: dict[str, Any]) -> list[dict[str, Any]]:
    raw = plan.get("verification_plan")
    normalized: list[dict[str, Any]] = []
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            command = item.get("command")
            purpose = item.get("purpose")
            if not isinstance(command, str) or not command.strip():
                continue
            normalized.append(
                {
                    "command": command.strip()[:240],
                    "purpose": bounded_text(purpose, 300),
                    "manual_only": True,
                    "executed_by_bundle_creation": False,
                }
            )
    if not normalized:
        normalized.append(
            {
                "command": ".\\scripts\\codex_verify.ps1",
                "purpose": "Run full Engel verifier before any future protected patch application.",
                "manual_only": True,
                "executed_by_bundle_creation": False,
            }
        )
    return normalized


def proposed_file_drafts_for_plan(plan: dict[str, Any], bundle_id: str) -> list[dict[str, Any]]:
    raw_changes = plan.get("proposed_changes")
    changes = raw_changes if isinstance(raw_changes, list) else []
    if not changes:
        changes = [
            {
                "target_file": "(undetermined)",
                "change_type": "unknown",
                "summary": "Insufficient detail for file-level draft.",
                "rationale": "The source patch plan did not include concrete proposed changes.",
                "risk": "unknown",
            }
        ]
    drafts: list[dict[str, Any]] = []
    for index, item in enumerate(changes, start=1):
        if not isinstance(item, dict):
            continue
        target_file = item.get("target_file")
        if not isinstance(target_file, str) or not target_file.strip():
            target_file = "(undetermined)"
        change_type = item.get("change_type")
        if change_type not in {"add", "modify", "remove", "docs_only", "tests_only", "verifier_only", "unknown"}:
            change_type = "unknown"
        draft_file = f"proposed_files/{proposed_file_name(target_file, index)}"
        drafts.append(
            {
                "target_file": target_file,
                "draft_file": draft_file,
                "change_type": change_type,
                "preview_only": True,
                "source_file_modified": False,
                "requires_manual_review": True,
                "source_status": source_path_status(target_file),
            }
        )
        if len(drafts) >= 20:
            break
    return drafts


def build_bundle(plan_path: Path, plan: dict[str, Any], source_hash: str, created_at: str | None = None) -> dict[str, Any]:
    stamp = created_at or now_utc()
    plan_id = str(plan.get("plan_id", "unknown_plan"))
    bundle_id = bundle_id_for(plan_id, stamp)
    target_files = normalize_target_files(plan)
    risk_flags = sorted(set(list(plan.get("risk_flags", [])) if isinstance(plan.get("risk_flags"), list) else []) | set(risk_flags_for_text(json.dumps(plan, sort_keys=True))))
    return {
        "bundle_version": "1",
        "bundle_id": bundle_id,
        "created_at": stamp,
        "created_by": "Engel Code Companion",
        "source_plan_id": plan_id,
        "source_plan_path": project_relative(plan_path),
        "source_plan_hash": source_hash,
        "trust_level": "untrusted_until_human_review",
        "status": "draft_bundle_preview",
        "requires_review": True,
        "safe_to_auto_apply": False,
        "patch_applied": False,
        "final_decision": FINAL_DECISION,
        "title": bounded_text(plan.get("title", "Patch bundle draft"), 180),
        "problem_summary": bounded_text(plan.get("problem_summary", ""), 1000),
        "bundle_summary": bounded_text(plan.get("proposed_patch_summary", ""), 1000),
        "target_files": target_files,
        "proposed_file_drafts": proposed_file_drafts_for_plan(plan, bundle_id),
        "verification_plan": normalize_verification_plan(plan),
        "risk_flags": risk_flags,
        "blocked_actions": list(REQUIRED_BLOCKED_ACTIONS),
        "required_approvals_before_apply": list(REQUIRED_APPROVALS),
        "notes": "Draft bundle only. No source files were modified.",
    }


def validate_bundle_payload(payload: dict[str, Any], bundle_path: Path | None = None) -> BundleValidation:
    errors: list[str] = []
    warnings: list[str] = []

    def required_string(field: str) -> str | None:
        value = payload.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{field} is required and must be a non-empty string")
            return None
        return value

    required_string("bundle_version")
    bundle_id = required_string("bundle_id")
    required_string("created_at")
    created_by = required_string("created_by")
    source_plan_id = required_string("source_plan_id")
    required_string("source_plan_path")
    required_string("source_plan_hash")
    trust_level = required_string("trust_level")
    status = required_string("status")
    title = required_string("title")
    required_string("problem_summary")
    required_string("bundle_summary")
    notes = required_string("notes")

    if created_by and created_by != "Engel Code Companion":
        errors.append("created_by must be Engel Code Companion")
    if trust_level and trust_level != "untrusted_until_human_review":
        errors.append("trust_level must be untrusted_until_human_review")
    if status and status != "draft_bundle_preview":
        errors.append("status must be draft_bundle_preview")
    if status and any(word in status.lower() for word in ["applied", "trusted", "complete", "completed"]):
        errors.append("status must not imply applied, trusted, or complete")
    if payload.get("requires_review") is not True:
        errors.append("requires_review must be true")
    if payload.get("safe_to_auto_apply") is not False:
        errors.append("safe_to_auto_apply must be false")
    if payload.get("patch_applied") is not False:
        errors.append("patch_applied must be false")
    if payload.get("final_decision") != FINAL_DECISION:
        errors.append("final_decision must be " + FINAL_DECISION)
    if notes and "No source files were modified" not in notes:
        warnings.append("notes should explicitly state no source files were modified")

    target_files = payload.get("target_files")
    if not isinstance(target_files, list) or not all(isinstance(item, str) for item in target_files):
        errors.append("target_files must be a list of strings")

    drafts = payload.get("proposed_file_drafts")
    if not isinstance(drafts, list):
        errors.append("proposed_file_drafts must be a list")
    else:
        for index, draft in enumerate(drafts):
            if not isinstance(draft, dict):
                errors.append(f"proposed_file_drafts[{index}] must be an object")
                continue
            if draft.get("preview_only") is not True:
                errors.append(f"proposed_file_drafts[{index}].preview_only must be true")
            if draft.get("source_file_modified") is not False:
                errors.append(f"proposed_file_drafts[{index}].source_file_modified must be false")
            if draft.get("requires_manual_review") is not True:
                errors.append(f"proposed_file_drafts[{index}].requires_manual_review must be true")
            draft_file = draft.get("draft_file")
            if not isinstance(draft_file, str) or not draft_file.startswith("proposed_files/"):
                errors.append(f"proposed_file_drafts[{index}].draft_file must be under proposed_files/")
            elif Path(draft_file).suffix.lower() not in {".md", ".txt"}:
                errors.append(f"proposed_file_drafts[{index}].draft_file must be preview .md or .txt")

    verification_plan = payload.get("verification_plan")
    if not isinstance(verification_plan, list) or not verification_plan:
        errors.append("verification_plan must be a non-empty list")
    else:
        for index, command in enumerate(verification_plan):
            if not isinstance(command, dict):
                errors.append(f"verification_plan[{index}] must be an object")
                continue
            if command.get("manual_only") is not True:
                errors.append(f"verification_plan[{index}].manual_only must be true")
            if command.get("executed_by_bundle_creation") is not False:
                errors.append(f"verification_plan[{index}].executed_by_bundle_creation must be false")
            if command.get("already_run") is True or command.get("executed") is True:
                errors.append(f"verification_plan[{index}] must not be marked already run or executed")

    blocked_actions = payload.get("blocked_actions")
    if not isinstance(blocked_actions, list):
        errors.append("blocked_actions must be a list")
    else:
        missing = [action for action in REQUIRED_BLOCKED_ACTIONS if action not in blocked_actions]
        if missing:
            errors.append("blocked_actions missing required entries: " + ", ".join(missing))

    approvals = payload.get("required_approvals_before_apply")
    if not isinstance(approvals, list):
        errors.append("required_approvals_before_apply must be a list")
    else:
        missing = [approval for approval in REQUIRED_APPROVALS if approval not in approvals]
        if missing:
            errors.append("required_approvals_before_apply missing required entries: " + ", ".join(missing))

    risk_flags = payload.get("risk_flags")
    if not isinstance(risk_flags, list) or not all(isinstance(item, str) for item in risk_flags):
        errors.append("risk_flags must be a list of strings")

    return BundleValidation(
        bundle_path=project_relative(bundle_path) if bundle_path else "(payload)",
        valid=not errors,
        bundle_id=bundle_id,
        source_plan_id=source_plan_id,
        title=title,
        status=status,
        errors=errors,
        warnings=warnings,
    )


def bundle_json_from_path(raw_path: str | Path) -> Path:
    path = Path(raw_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    resolved = path.resolve(strict=False)
    if resolved.is_dir():
        resolved = resolved / "bundle.json"
    return resolved


def validate_bundle_file(raw_path: str | Path) -> BundleValidation:
    path = bundle_json_from_path(raw_path)
    if not path.exists() or not path.is_file():
        return BundleValidation(project_relative(path), False, None, None, None, None, ["bundle.json does not exist"], [])
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return BundleValidation(project_relative(path), False, None, None, None, None, [f"could not parse bundle JSON: {exc}"], [])
    if not isinstance(payload, dict):
        return BundleValidation(project_relative(path), False, None, None, None, None, ["bundle JSON root must be an object"], [])
    result = validate_bundle_payload(payload, path)
    if is_relative_to(path, EXAMPLES_DIR):
        return result
    folder_errors, folder_warnings = validate_bundle_folder(path.parent, payload)
    result.errors.extend(folder_errors)
    result.warnings.extend(folder_warnings)
    result.valid = not result.errors
    return result


def validate_bundle_folder(folder: Path, payload: dict[str, Any]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if not folder.exists() or not folder.is_dir():
        return ["bundle folder does not exist"], warnings
    try:
        files = [path for path in folder.iterdir() if path.is_file()]
        proposed_root = folder / "proposed_files"
        proposed_files = [path for path in proposed_root.iterdir() if path.is_file()] if proposed_root.exists() else []
    except OSError as exc:
        return [f"could not inspect bundle folder: {exc}"], warnings
    for path in files + proposed_files:
        suffix = path.suffix.lower()
        if suffix in APPLY_SUFFIXES:
            errors.append("bundle contains apply-style patch/diff file: " + project_relative(path))
        if path.parent.name == "proposed_files" and suffix not in {".md", ".txt"}:
            errors.append("proposed_files must contain preview .md/.txt only: " + project_relative(path))
        if path.parent.name == "proposed_files" and suffix in EXECUTABLE_SUFFIXES:
            errors.append("proposed file draft must not be executable/importable source: " + project_relative(path))
        if path.is_file():
            try:
                text = path.read_text(encoding="utf-8", errors="replace")[:600]
            except OSError:
                continue
            if "PREVIEW ONLY" not in text and path.parent.name == "proposed_files":
                errors.append("proposed file draft missing PREVIEW ONLY banner: " + project_relative(path))
    expected = ["README.md", "proposed_changes.md", "verification_plan.md", "risk_review.md", "source_manifest.json"]
    for name in expected:
        if not (folder / name).exists():
            errors.append("bundle folder missing " + name)
    return errors, warnings


def bundle_folder_for(bundle: dict[str, Any], bundle_root: Path = BUNDLE_ROOT) -> Path:
    return bundle_root / safe_slug(str(bundle.get("bundle_id", "patch_bundle_draft")))


def write_markdown(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def write_bundle_files(bundle: dict[str, Any], bundle_root: Path = BUNDLE_ROOT) -> Path:
    ensure_folders(bundle_root, bundle_root / "receipts")
    folder = bundle_folder_for(bundle, bundle_root)
    folder.mkdir(parents=True, exist_ok=True)
    proposed_root = folder / "proposed_files"
    proposed_root.mkdir(parents=True, exist_ok=True)
    (folder / "bundle.json").write_text(json.dumps(bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_markdown(folder / "README.md", render_readme(bundle))
    write_markdown(folder / "proposed_changes.md", render_proposed_changes(bundle))
    write_markdown(folder / "verification_plan.md", render_verification_plan(bundle))
    write_markdown(folder / "risk_review.md", render_risk_review(bundle))
    (folder / "source_manifest.json").write_text(json.dumps(render_source_manifest(bundle), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    for draft in bundle.get("proposed_file_drafts", []):
        if not isinstance(draft, dict):
            continue
        draft_file = draft.get("draft_file")
        if not isinstance(draft_file, str) or not draft_file.startswith("proposed_files/"):
            continue
        draft_path = folder / draft_file.replace("/", "\\")
        draft_path.write_text(render_proposed_file_draft(bundle, draft), encoding="utf-8")
    return folder


def render_readme(bundle: dict[str, Any]) -> str:
    return f"""# Code Companion Patch Bundle Draft

Final decision: **{FINAL_DECISION}**

Bundle ID: `{bundle.get("bundle_id")}`

Status: `{bundle.get("status")}`

Trust level: `{bundle.get("trust_level")}`

This is an isolated review artifact. It is not a patch and it is not applied.

No source files were modified.

No patch was applied.

No commands from the plan were executed.

No trusted memory was written.
"""


def render_proposed_changes(bundle: dict[str, Any]) -> str:
    lines = [
        "# Proposed Changes Preview",
        "",
        "PREVIEW ONLY - NOT APPLIED",
        "",
        "These are human-readable draft notes only.",
        "",
        "## Bundle Summary",
        "",
        bounded_text(bundle.get("bundle_summary", "")),
        "",
        "## Proposed File Drafts",
        "",
    ]
    drafts = bundle.get("proposed_file_drafts", [])
    if not drafts:
        lines.append("Insufficient detail for file-level draft.")
    for draft in drafts:
        if isinstance(draft, dict):
            lines.append(f"- `{draft.get('target_file')}` -> `{draft.get('draft_file')}` ({draft.get('change_type')})")
    return "\n".join(lines) + "\n"


def render_verification_plan(bundle: dict[str, Any]) -> str:
    lines = [
        "# Verification Plan Preview",
        "",
        "PREVIEW ONLY - COMMANDS NOT RUN BY BUNDLE CREATION",
        "",
    ]
    for item in bundle.get("verification_plan", []):
        if isinstance(item, dict):
            lines.append(f"- `{item.get('command')}`")
            lines.append(f"  - purpose: {bounded_text(item.get('purpose', ''), 300)}")
            lines.append("  - manual_only: true")
            lines.append("  - executed_by_bundle_creation: false")
    return "\n".join(lines) + "\n"


def render_risk_review(bundle: dict[str, Any]) -> str:
    flags = bundle.get("risk_flags", [])
    risks = "\n".join(f"- {flag}" for flag in flags) if flags else "- none"
    approvals = "\n".join(f"- {item}" for item in bundle.get("required_approvals_before_apply", [])) or "- none"
    return f"""# Risk Review

PREVIEW ONLY - NOT APPLIED

## Risk Flags

{risks}

## Required Approvals Before Apply

{approvals}

No source, route, queue, or trusted-memory mutation is authorized by this bundle.
"""


def render_source_manifest(bundle: dict[str, Any]) -> dict[str, Any]:
    return {
        "bundle_id": bundle.get("bundle_id"),
        "source_plan_id": bundle.get("source_plan_id"),
        "source_plan_path": bundle.get("source_plan_path"),
        "source_plan_hash": bundle.get("source_plan_hash"),
        "target_files": bundle.get("target_files", []),
        "source_files_modified": False,
        "patch_applied": False,
        "safe_to_auto_apply": False,
    }


def render_proposed_file_draft(bundle: dict[str, Any], draft: dict[str, Any]) -> str:
    return f"""# Proposed File Draft

PREVIEW ONLY - NOT APPLIED

Target file: `{draft.get("target_file")}`

Change type: `{draft.get("change_type")}`

Preview only: `true`

Source file modified: `false`

Requires manual review: `true`

## Proposed Change Summary

```text
{bounded_text(bundle.get("bundle_summary", ""))}
```

## Human Review Notes

This file is a proposed review draft stored inside a reports bundle. It is not source code, not a patch, and not applied.
"""


def receipt_path_for(bundle: dict[str, Any], receipt_dir: Path = RECEIPTS_DIR) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return receipt_dir / f"PATCH_BUNDLE_DRAFT_{stamp}_{safe_slug(str(bundle.get('bundle_id', 'bundle')))}.md"


def write_receipt(bundle: dict[str, Any], folder: Path, receipt_dir: Path = RECEIPTS_DIR) -> Path:
    receipt_dir.mkdir(parents=True, exist_ok=True)
    path = receipt_path_for(bundle, receipt_dir)
    target_files = "\n".join(f"- `{item}`" for item in bundle.get("target_files", [])) or "- none"
    drafts = "\n".join(
        f"- `{item.get('draft_file')}` for `{item.get('target_file')}`"
        for item in bundle.get("proposed_file_drafts", [])
        if isinstance(item, dict)
    ) or "- none"
    verification = "\n".join(
        f"- `{item.get('command')}` - {bounded_text(item.get('purpose', ''), 220)}"
        for item in bundle.get("verification_plan", [])
        if isinstance(item, dict)
    ) or "- none"
    risks = "\n".join(f"- {item}" for item in bundle.get("risk_flags", [])) or "- none"
    approvals = "\n".join(f"- {item}" for item in bundle.get("required_approvals_before_apply", [])) or "- none"
    text = f"""# Code Companion Patch Bundle Draft Receipt

## Intake

- timestamp: `{now_utc()}`
- bundle ID: `{bundle.get("bundle_id")}`
- bundle folder: `{project_relative(folder)}`
- source plan path: `{bundle.get("source_plan_path")}`
- source plan SHA-256: `{bundle.get("source_plan_hash")}`
- validation status: `draft_bundle_preview`
- final decision: **{FINAL_DECISION}**

## Title

{bundle.get("title")}

## Problem Summary

```text
{bounded_text(bundle.get("problem_summary", ""))}
```

## Bundle Summary

```text
{bounded_text(bundle.get("bundle_summary", ""))}
```

## Target Files

{target_files}

## Proposed Draft Files

{drafts}

## Verification Plan Summary

{verification}

## Risk Flags

{risks}

## Required Approvals Before Apply

{approvals}

## Boundary

No source files were modified.

No patch was applied.

No commands from the plan were executed.

No trusted memory was written.

Bundle is untrusted until human review.
"""
    if len(text) > MAX_RECEIPT_CHARS:
        text = text[:MAX_RECEIPT_CHARS] + "\n[receipt truncated]\n"
    path.write_text(text, encoding="utf-8")
    return path


def create_patch_bundle_draft(
    raw_plan_path: str | Path,
    *,
    bundle_root: Path = BUNDLE_ROOT,
    receipt_dir: Path = RECEIPTS_DIR,
    created_at: str | None = None,
) -> BundleCreationResult:
    plan_path = resolve_plan_path(raw_plan_path)
    plan = validate_source_plan(plan_path)
    source_hash = sha256_file(plan_path)
    bundle = build_bundle(plan_path, plan, source_hash, created_at=created_at)
    validation = validate_bundle_payload(bundle)
    if not validation.valid:
        raise PatchBundleDraftError("generated bundle failed validation: " + "; ".join(validation.errors))
    ensure_folders(bundle_root, receipt_dir)
    folder = write_bundle_files(bundle, bundle_root)
    folder_validation = validate_bundle_file(folder)
    if not folder_validation.valid:
        raise PatchBundleDraftError("written bundle failed validation: " + "; ".join(folder_validation.errors))
    receipt = write_receipt(bundle, folder, receipt_dir)
    return BundleCreationResult(str(folder), str(folder / "bundle.json"), str(receipt), bundle)


def bundle_folders(bundle_root: Path = BUNDLE_ROOT) -> list[Path]:
    if not bundle_root.exists():
        return []
    try:
        return sorted(
            [
                path
                for path in bundle_root.iterdir()
                if path.is_dir() and path.name not in {"examples", "receipts"} and (path / "bundle.json").exists()
            ],
            key=lambda item: item.name.lower(),
        )
    except OSError:
        return []


def render_status(bundle_root: Path = BUNDLE_ROOT, receipt_dir: Path = RECEIPTS_DIR) -> str:
    ensure_folders(bundle_root, receipt_dir)
    folders = bundle_folders(bundle_root)
    statuses: dict[str, int] = {}
    for folder in folders:
        result = validate_bundle_file(folder)
        key = result.status or "invalid"
        statuses[key] = statuses.get(key, 0) + 1
    status_text = ", ".join(f"{key}={value}" for key, value in sorted(statuses.items())) or "none"
    return "\n".join(
        [
            "Engel Code Companion Patch Bundle Draft V1",
            "Mode: manual / local / isolated bundle / not applied",
            f"Bundle folder: {project_relative(bundle_root)}",
            f"Examples folder: {project_relative(bundle_root / 'examples')}",
            f"Receipts folder: {project_relative(receipt_dir)}",
            f"Patch bundle draft count: {len(folders)}",
            f"Status counts: {status_text}",
            "No patch apply, no source edits, no command execution, no trusted-memory write.",
        ]
    )


def render_list(bundle_root: Path = BUNDLE_ROOT) -> str:
    folders = bundle_folders(bundle_root)
    if not folders:
        return "No Code Companion patch bundle draft folders found."
    lines = ["Code Companion patch bundle drafts:"]
    for folder in folders:
        result = validate_bundle_file(folder)
        try:
            payload = json.loads((folder / "bundle.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = {}
        lines.append(
            f"- {project_relative(folder)} | valid={result.valid} | bundle_id={result.bundle_id or '(none)'} | "
            f"source_plan_id={result.source_plan_id or '(none)'} | title={result.title or '(none)'} | "
            f"status={result.status or '(none)'} | created_at={payload.get('created_at', '(none)')} | "
            f"safe_to_auto_apply={payload.get('safe_to_auto_apply', '(none)')} | patch_applied={payload.get('patch_applied', '(none)')}"
        )
    return "\n".join(lines)


def render_validation(result: BundleValidation) -> str:
    lines = [
        "Code Companion patch bundle validation",
        f"bundle: {result.bundle_path}",
        f"valid: {result.valid}",
        f"bundle_id: {result.bundle_id or '(none)'}",
        f"source_plan_id: {result.source_plan_id or '(none)'}",
        f"title: {result.title or '(none)'}",
        f"status: {result.status or '(none)'}",
    ]
    if result.errors:
        lines.append("errors:")
        lines.extend(f"- {error}" for error in result.errors)
    if result.warnings:
        lines.append("warnings:")
        lines.extend(f"- {warning}" for warning in result.warnings)
    lines.append(FINAL_DECISION)
    return "\n".join(lines)


def render_creation(result: BundleCreationResult) -> str:
    return "\n".join(
        [
            "Code Companion patch bundle draft created",
            f"bundle_folder: {project_relative(Path(result.bundle_folder))}",
            f"bundle_json: {project_relative(Path(result.bundle_json))}",
            f"receipt: {project_relative(Path(result.receipt_path))}",
            f"bundle_id: {result.bundle.get('bundle_id')}",
            f"source_plan_id: {result.bundle.get('source_plan_id')}",
            f"requires_review: {result.bundle.get('requires_review')}",
            f"safe_to_auto_apply: {result.bundle.get('safe_to_auto_apply')}",
            f"patch_applied: {result.bundle.get('patch_applied')}",
            FINAL_DECISION,
        ]
    )


def show_bundle(raw: str) -> str:
    path = Path(raw)
    if not path.is_absolute():
        maybe_path = PROJECT_ROOT / path
    else:
        maybe_path = path
    if maybe_path.exists():
        bundle_path = maybe_path
    else:
        matches = [folder for folder in bundle_folders() if folder.name == safe_slug(raw) or raw in folder.name]
        if not matches:
            raise PatchBundleDraftError("bundle not found by path or id")
        bundle_path = matches[0]
    result = validate_bundle_file(bundle_path)
    text = render_validation(result)
    json_path = bundle_json_from_path(bundle_path)
    if result.valid and json_path.exists():
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        text += "\n\nBundle summary:\n" + bounded_text(payload.get("bundle_summary", ""))
    return text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Isolated patch bundle draft generator for Engel Code Companion.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    sub.add_parser("list")
    validate_parser = sub.add_parser("validate")
    validate_parser.add_argument("path")
    create_parser = sub.add_parser("create")
    create_parser.add_argument("plan_path")
    show_parser = sub.add_parser("show")
    show_parser.add_argument("bundle")
    args = parser.parse_args(argv)

    try:
        if args.command == "status":
            print(render_status())
            return 0
        if args.command == "list":
            print(render_list())
            return 0
        if args.command == "validate":
            result = validate_bundle_file(args.path)
            print(render_validation(result))
            return 0 if result.valid else 1
        if args.command == "create":
            result = create_patch_bundle_draft(args.plan_path)
            print(render_creation(result))
            return 0
        if args.command == "show":
            print(show_bundle(args.bundle))
            return 0
    except PatchBundleDraftError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
