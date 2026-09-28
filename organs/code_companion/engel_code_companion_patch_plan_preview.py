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

import engel_code_companion_fix_candidate_intake as fix_candidate_intake


PROJECT_ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
FIX_CANDIDATE_ROOT = PROJECT_ROOT / "reports" / "code_companion_fix_candidates"
FIX_CANDIDATE_EXAMPLES = FIX_CANDIDATE_ROOT / "examples"
PLAN_DIR = PROJECT_ROOT / "reports" / "code_companion_patch_plans"
EXAMPLES_DIR = PLAN_DIR / "examples"
RECEIPTS_DIR = PLAN_DIR / "receipts"

MAX_CANDIDATE_BYTES = 512 * 1024
MAX_RECEIPT_PREVIEW = 1000
FINAL_DECISION = "PATCH PLAN PREVIEW ONLY — NOT APPLIED"

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


class PatchPlanPreviewError(ValueError):
    pass


@dataclass
class PlanValidation:
    plan_path: str
    valid: bool
    plan_id: str | None
    source_candidate_id: str | None
    title: str | None
    status: str | None
    errors: list[str]
    warnings: list[str]


@dataclass
class PlanCreationResult:
    plan_path: str
    receipt_path: str
    plan: dict[str, Any]


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


def ensure_folders(plan_dir: Path = PLAN_DIR, receipt_dir: Path = RECEIPTS_DIR) -> None:
    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / "examples").mkdir(parents=True, exist_ok=True)
    receipt_dir.mkdir(parents=True, exist_ok=True)


def safe_slug(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip()).strip("._-")
    return (cleaned or "patch_plan_preview")[:120]


def timestamp_slug(value: str) -> str:
    return safe_slug(value.replace(":", "").replace("-", ""))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def bounded_text(value: Any, limit: int = MAX_RECEIPT_PREVIEW) -> str:
    clean = str(value if value is not None else "").replace("\r\n", "\n").strip()
    if len(clean) <= limit:
        return clean
    return clean[:limit] + "\n[preview truncated]"


def resolve_candidate_path(raw_path: str | Path) -> Path:
    text = str(raw_path)
    if not text or text.startswith(("http://", "https://", "\\\\")):
        raise PatchPlanPreviewError("candidate path must be an explicit local file")
    if any(marker in text for marker in ("*", "?", "[")):
        raise PatchPlanPreviewError("wildcards are not allowed")
    path = Path(text)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    resolved = path.resolve(strict=False)
    if not resolved.exists() or not resolved.is_file():
        raise PatchPlanPreviewError("candidate file does not exist")
    if not is_relative_to(resolved, PROJECT_ROOT):
        raise PatchPlanPreviewError("candidate file must stay inside Engel App")
    if not (is_relative_to(resolved, FIX_CANDIDATE_ROOT) or is_relative_to(resolved, FIX_CANDIDATE_EXAMPLES)):
        raise PatchPlanPreviewError("Phase 2 accepts Phase 1 fix candidate files only")
    if resolved.suffix.lower() != ".json":
        raise PatchPlanPreviewError("candidate must be a JSON file")
    if resolved.stat().st_size > MAX_CANDIDATE_BYTES:
        raise PatchPlanPreviewError(f"candidate file exceeds max plan input size of {MAX_CANDIDATE_BYTES} bytes")
    return resolved


def load_candidate_payload(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PatchPlanPreviewError(f"could not read candidate JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise PatchPlanPreviewError("candidate JSON root must be an object")
    return payload


def validate_source_candidate(path: Path) -> dict[str, Any]:
    validation = fix_candidate_intake.validate_candidate_file(path)
    if not validation.valid:
        raise PatchPlanPreviewError("source candidate is invalid: " + "; ".join(validation.errors))
    payload = load_candidate_payload(path)
    if payload.get("trust_level") != "untrusted_until_human_review":
        raise PatchPlanPreviewError("source candidate must remain untrusted_until_human_review")
    if payload.get("requires_review") is not True:
        raise PatchPlanPreviewError("source candidate must require review")
    if payload.get("safe_to_auto_apply") is not False:
        raise PatchPlanPreviewError("source candidate must not be safe to auto-apply")
    if payload.get("patch_applied") is not False:
        raise PatchPlanPreviewError("source candidate must not be marked patch_applied")
    return payload


def risk_flags_for_text(text: str) -> list[str]:
    flags: list[str] = []
    for flag, pattern in RISK_PATTERNS.items():
        if re.search(pattern, text, re.IGNORECASE):
            flags.append(flag)
    return sorted(set(flags))


def risk_flags_for_candidate(candidate: dict[str, Any]) -> list[str]:
    return risk_flags_for_text(json.dumps(candidate, sort_keys=True))


def normalize_likely_files(candidate: dict[str, Any]) -> list[str]:
    raw_files = candidate.get("likely_files")
    if not isinstance(raw_files, list):
        return []
    normalized: list[str] = []
    for item in raw_files:
        if not isinstance(item, str) or not item.strip():
            continue
        text = item.strip().replace("/", "\\")
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
        normalized.append(text[:180])
        if len(normalized) >= 20:
            break
    return normalized


def infer_change_type(target_file: str) -> str:
    lowered = target_file.lower()
    if lowered.endswith((".md", ".txt")):
        return "docs_only"
    if "\\test\\" in lowered or lowered.startswith("test\\") or lowered.endswith("_test.dart"):
        return "tests_only"
    if "verify_" in lowered or lowered.endswith(".ps1"):
        return "verifier_only"
    if target_file == "(undetermined)":
        return "unknown"
    return "modify"


def build_proposed_changes(candidate: dict[str, Any], likely_files: list[str]) -> list[dict[str, Any]]:
    summary = bounded_text(candidate.get("proposed_fix_summary", "Review candidate and draft a future patch."), 500)
    rationale = bounded_text(candidate.get("problem_summary", "Candidate requires human review before any patch."), 500)
    targets = likely_files or ["(undetermined)"]
    changes: list[dict[str, Any]] = []
    for target in targets:
        changes.append(
            {
                "target_file": target,
                "change_type": infer_change_type(target),
                "summary": summary,
                "rationale": rationale,
                "risk": "unknown" if target == "(undetermined)" else "medium",
                "requires_manual_review": True,
            }
        )
    return changes


def build_verification_plan(likely_files: list[str]) -> list[dict[str, Any]]:
    commands: list[dict[str, Any]] = [
        {
            "command": "python tools\\verify_engel_code_companion_patch_plan_preview.py",
            "purpose": "Verify the patch plan preview layer remains preview-only and safe.",
            "manual_only": True,
        },
        {
            "command": ".\\scripts\\codex_verify.ps1",
            "purpose": "Run the full Engel verifier before any future protected patch application.",
            "manual_only": True,
        },
    ]
    lowered = "\n".join(likely_files).lower()
    if any(item.endswith(".py") for item in likely_files):
        commands.insert(
            0,
            {
                "command": "python -m py_compile <reviewed_python_files>",
                "purpose": "Compile any reviewed Python files after a future human-approved patch.",
                "manual_only": True,
            },
        )
    if ".dart" in lowered or "mobile\\engel_remote_worker" in lowered:
        commands.extend(
            [
                {
                    "command": "flutter analyze",
                    "purpose": "Analyze Flutter changes after a future human-approved patch.",
                    "manual_only": True,
                },
                {
                    "command": "flutter test",
                    "purpose": "Run Flutter tests after a future human-approved patch.",
                    "manual_only": True,
                },
            ]
        )
    return commands


def plan_id_for(candidate_id: str, created_at: str) -> str:
    return f"{timestamp_slug(created_at)}_{safe_slug(candidate_id)}_patch_plan_preview"


def build_patch_plan(candidate_path: Path, candidate: dict[str, Any], source_hash: str, created_at: str | None = None) -> dict[str, Any]:
    stamp = created_at or now_utc()
    candidate_id = str(candidate.get("candidate_id", "unknown_candidate"))
    likely_files = normalize_likely_files(candidate)
    return {
        "plan_version": "1",
        "plan_id": plan_id_for(candidate_id, stamp),
        "created_at": stamp,
        "created_by": "Engel Code Companion",
        "source_candidate_id": candidate_id,
        "source_candidate_path": project_relative(candidate_path),
        "source_candidate_hash": source_hash,
        "trust_level": "untrusted_until_human_review",
        "status": "draft_plan_preview",
        "requires_review": True,
        "safe_to_auto_apply": False,
        "patch_applied": False,
        "title": bounded_text(candidate.get("title", "Patch plan preview"), 180),
        "problem_summary": bounded_text(candidate.get("problem_summary", ""), 900),
        "proposed_patch_summary": bounded_text(candidate.get("proposed_fix_summary", ""), 900),
        "likely_files": likely_files,
        "proposed_changes": build_proposed_changes(candidate, likely_files),
        "verification_plan": build_verification_plan(likely_files),
        "risk_flags": risk_flags_for_candidate(candidate),
        "blocked_actions": list(REQUIRED_BLOCKED_ACTIONS),
        "required_approvals_before_apply": list(REQUIRED_APPROVALS),
        "notes": "Preview only. No source files were modified.",
    }


def validate_plan_payload(payload: dict[str, Any], path: Path | None = None) -> PlanValidation:
    errors: list[str] = []
    warnings: list[str] = []

    def required_string(field: str) -> str | None:
        value = payload.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{field} is required and must be a non-empty string")
            return None
        return value

    required_string("plan_version")
    plan_id = required_string("plan_id")
    required_string("created_at")
    created_by = required_string("created_by")
    source_candidate_id = required_string("source_candidate_id")
    required_string("source_candidate_path")
    required_string("source_candidate_hash")
    trust_level = required_string("trust_level")
    status = required_string("status")
    title = required_string("title")
    required_string("problem_summary")
    required_string("proposed_patch_summary")
    notes = required_string("notes")

    if created_by and created_by != "Engel Code Companion":
        errors.append("created_by must be Engel Code Companion")
    if trust_level and trust_level != "untrusted_until_human_review":
        errors.append("trust_level must be untrusted_until_human_review")
    if status and status != "draft_plan_preview":
        errors.append("status must be draft_plan_preview")
    if status and any(word in status.lower() for word in ["applied", "trusted", "complete", "completed"]):
        errors.append("status must not imply applied, trusted, or complete")
    if payload.get("requires_review") is not True:
        errors.append("requires_review must be true")
    if payload.get("safe_to_auto_apply") is not False:
        errors.append("safe_to_auto_apply must be false")
    if payload.get("patch_applied") is not False:
        errors.append("patch_applied must be false")
    if notes and "No source files were modified" not in notes:
        warnings.append("notes should explicitly state no source files were modified")

    likely_files = payload.get("likely_files")
    if not isinstance(likely_files, list) or not all(isinstance(item, str) for item in likely_files):
        errors.append("likely_files must be a list of strings")

    proposed_changes = payload.get("proposed_changes")
    if not isinstance(proposed_changes, list) or not proposed_changes:
        errors.append("proposed_changes must be a non-empty list")
    else:
        for index, change in enumerate(proposed_changes):
            if not isinstance(change, dict):
                errors.append(f"proposed_changes[{index}] must be an object")
                continue
            if change.get("requires_manual_review") is not True:
                errors.append(f"proposed_changes[{index}].requires_manual_review must be true")
            if change.get("change_type") not in {"add", "modify", "remove", "docs_only", "tests_only", "verifier_only", "unknown"}:
                errors.append(f"proposed_changes[{index}].change_type is not allowed")

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

    return PlanValidation(
        plan_path=project_relative(path) if path else "(payload)",
        valid=not errors,
        plan_id=plan_id,
        source_candidate_id=source_candidate_id,
        title=title,
        status=status,
        errors=errors,
        warnings=warnings,
    )


def validate_plan_file(path: Path) -> PlanValidation:
    if not path.exists() or not path.is_file():
        return PlanValidation(project_relative(path), False, None, None, None, None, ["plan file does not exist"], [])
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return PlanValidation(project_relative(path), False, None, None, None, None, [f"could not parse plan JSON: {exc}"], [])
    if not isinstance(payload, dict):
        return PlanValidation(project_relative(path), False, None, None, None, None, ["plan JSON root must be an object"], [])
    return validate_plan_payload(payload, path)


def plan_path_for(plan: dict[str, Any], plan_dir: Path = PLAN_DIR) -> Path:
    return plan_dir / f"{safe_slug(str(plan.get('plan_id', 'patch_plan_preview')))}.json"


def receipt_path_for(plan: dict[str, Any], receipt_dir: Path = RECEIPTS_DIR) -> Path:
    return receipt_dir / f"{safe_slug(str(plan.get('plan_id', 'patch_plan_preview')))}.md"


def write_plan(plan: dict[str, Any], plan_dir: Path = PLAN_DIR) -> Path:
    ensure_folders(plan_dir, plan_dir / "receipts")
    path = plan_path_for(plan, plan_dir)
    path.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def write_receipt(plan: dict[str, Any], plan_path: Path, receipt_dir: Path = RECEIPTS_DIR) -> Path:
    receipt_dir.mkdir(parents=True, exist_ok=True)
    path = receipt_path_for(plan, receipt_dir)
    likely_files = "\n".join(f"- `{item}`" for item in plan.get("likely_files", [])) or "- none"
    changes = "\n".join(
        f"- `{item.get('target_file', '(unknown)')}`: {item.get('change_type', 'unknown')} - {bounded_text(item.get('summary', ''), 220)}"
        for item in plan.get("proposed_changes", [])
        if isinstance(item, dict)
    ) or "- none"
    verification = "\n".join(
        f"- `{item.get('command', '(unknown)')}` - {bounded_text(item.get('purpose', ''), 220)}"
        for item in plan.get("verification_plan", [])
        if isinstance(item, dict)
    ) or "- none"
    risks = "\n".join(f"- {item}" for item in plan.get("risk_flags", [])) or "- none"
    approvals = "\n".join(f"- {item}" for item in plan.get("required_approvals_before_apply", [])) or "- none"
    text = f"""# Code Companion Patch Plan Preview Receipt

## Intake

- timestamp: `{now_utc()}`
- plan ID: `{plan.get("plan_id")}`
- plan path: `{project_relative(plan_path)}`
- source candidate path: `{plan.get("source_candidate_path")}`
- source candidate SHA-256: `{plan.get("source_candidate_hash")}`
- validation status: `draft_plan_preview`
- final decision: **{FINAL_DECISION}**

## Title

{plan.get("title")}

## Problem Summary

```text
{bounded_text(plan.get("problem_summary", ""))}
```

## Proposed Patch Summary

```text
{bounded_text(plan.get("proposed_patch_summary", ""))}
```

## Likely Files

{likely_files}

## Proposed Changes

{changes}

## Verification Plan

{verification}

## Risk Flags

{risks}

## Required Approvals Before Apply

{approvals}

## Boundary

No source files were modified.

No patch was applied.

No commands from the candidate were executed.

No trusted memory was written.
"""
    path.write_text(text, encoding="utf-8")
    return path


def create_patch_plan_preview(
    raw_candidate_path: str | Path,
    *,
    plan_dir: Path = PLAN_DIR,
    receipt_dir: Path = RECEIPTS_DIR,
    created_at: str | None = None,
) -> PlanCreationResult:
    candidate_path = resolve_candidate_path(raw_candidate_path)
    candidate = validate_source_candidate(candidate_path)
    source_hash = sha256_file(candidate_path)
    plan = build_patch_plan(candidate_path, candidate, source_hash, created_at=created_at)
    validation = validate_plan_payload(plan)
    if not validation.valid:
        raise PatchPlanPreviewError("generated plan failed validation: " + "; ".join(validation.errors))
    ensure_folders(plan_dir, receipt_dir)
    plan_path = write_plan(plan, plan_dir)
    receipt_path = write_receipt(plan, plan_path, receipt_dir)
    return PlanCreationResult(str(plan_path), str(receipt_path), plan)


def plan_files(plan_dir: Path = PLAN_DIR) -> list[Path]:
    if not plan_dir.exists():
        return []
    try:
        return sorted(
            [path for path in plan_dir.iterdir() if path.is_file() and path.suffix.lower() == ".json"],
            key=lambda item: item.name.lower(),
        )
    except OSError:
        return []


def render_status(plan_dir: Path = PLAN_DIR, receipt_dir: Path = RECEIPTS_DIR) -> str:
    ensure_folders(plan_dir, receipt_dir)
    files = plan_files(plan_dir)
    statuses: dict[str, int] = {}
    for path in files:
        result = validate_plan_file(path)
        key = result.status or "invalid"
        statuses[key] = statuses.get(key, 0) + 1
    status_text = ", ".join(f"{key}={value}" for key, value in sorted(statuses.items())) or "none"
    return "\n".join(
        [
            "Engel Code Companion Patch Plan Preview V1",
            "Mode: manual / local / preview-only / not applied",
            f"Patch plan folder: {project_relative(plan_dir)}",
            f"Examples folder: {project_relative(plan_dir / 'examples')}",
            f"Receipts folder: {project_relative(receipt_dir)}",
            f"Patch plan preview count: {len(files)}",
            f"Status counts: {status_text}",
            "No patch apply, no source edits, no command execution, no trusted-memory write.",
        ]
    )


def render_list(plan_dir: Path = PLAN_DIR) -> str:
    files = plan_files(plan_dir)
    if not files:
        return "No Code Companion patch plan preview files found."
    lines = ["Code Companion patch plan previews:"]
    for path in files:
        result = validate_plan_file(path)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = {}
        lines.append(
            f"- {project_relative(path)} | valid={result.valid} | plan_id={result.plan_id or '(none)'} | "
            f"source_candidate_id={result.source_candidate_id or '(none)'} | title={result.title or '(none)'} | "
            f"status={result.status or '(none)'} | created_at={payload.get('created_at', '(none)')} | "
            f"safe_to_auto_apply={payload.get('safe_to_auto_apply', '(none)')} | patch_applied={payload.get('patch_applied', '(none)')}"
        )
    return "\n".join(lines)


def render_validation(result: PlanValidation) -> str:
    lines = [
        "Code Companion patch plan validation",
        f"plan: {result.plan_path}",
        f"valid: {result.valid}",
        f"plan_id: {result.plan_id or '(none)'}",
        f"source_candidate_id: {result.source_candidate_id or '(none)'}",
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


def render_creation(result: PlanCreationResult) -> str:
    return "\n".join(
        [
            "Code Companion patch plan preview created",
            f"plan: {project_relative(Path(result.plan_path))}",
            f"receipt: {project_relative(Path(result.receipt_path))}",
            f"plan_id: {result.plan.get('plan_id')}",
            f"source_candidate_id: {result.plan.get('source_candidate_id')}",
            f"requires_review: {result.plan.get('requires_review')}",
            f"safe_to_auto_apply: {result.plan.get('safe_to_auto_apply')}",
            f"patch_applied: {result.plan.get('patch_applied')}",
            FINAL_DECISION,
        ]
    )


def show_plan(raw: str) -> str:
    path = Path(raw)
    if not path.is_absolute():
        maybe_path = PROJECT_ROOT / path
    else:
        maybe_path = path
    if maybe_path.exists():
        plan_path = maybe_path
    else:
        matches = [path for path in plan_files() if path.stem == safe_slug(raw) or raw in path.stem]
        if not matches:
            raise PatchPlanPreviewError("plan not found by path or id")
        plan_path = matches[0]
    validation = validate_plan_file(plan_path)
    text = render_validation(validation)
    if validation.valid:
        payload = json.loads(plan_path.read_text(encoding="utf-8"))
        text += "\n\nProposed patch summary:\n" + bounded_text(payload.get("proposed_patch_summary", ""))
    return text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Human-review patch plan preview generator for Engel Code Companion.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    sub.add_parser("list")
    validate_parser = sub.add_parser("validate")
    validate_parser.add_argument("path")
    create_parser = sub.add_parser("create")
    create_parser.add_argument("candidate_path")
    show_parser = sub.add_parser("show")
    show_parser.add_argument("plan")
    args = parser.parse_args(argv)

    try:
        if args.command == "status":
            print(render_status())
            return 0
        if args.command == "list":
            print(render_list())
            return 0
        if args.command == "validate":
            result = validate_plan_file(Path(args.path))
            print(render_validation(result))
            return 0 if result.valid else 1
        if args.command == "create":
            result = create_patch_plan_preview(args.candidate_path)
            print(render_creation(result))
            return 0
        if args.command == "show":
            print(show_plan(args.plan))
            return 0
    except PatchPlanPreviewError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

