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

import engel_code_companion_patch_bundle_draft as patch_bundle_draft


PROJECT_ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
BUNDLE_ROOT = PROJECT_ROOT / "reports" / "code_companion_patch_bundles"
BUNDLE_EXAMPLES = BUNDLE_ROOT / "examples"
GATE_ROOT = PROJECT_ROOT / "reports" / "code_companion_patch_application_gates"
GATE_EXAMPLES = GATE_ROOT / "examples"
RECEIPTS_DIR = GATE_ROOT / "receipts"
DRY_RUNS_DIR = GATE_ROOT / "dry_runs"

MAX_BUNDLE_BYTES = 1024 * 1024
MAX_PROPOSED_FILE_BYTES = 256 * 1024
MAX_PREVIEW_CHARS = 1600
MAX_REPORT_CHARS = 18000

GATE_FINAL_DECISION = "PROTECTED APPLICATION GATE ONLY — NOT APPLIED"
DRY_RUN_FINAL_DECISION = "DRY RUN ONLY — NOT APPLIED"

REQUIRED_GATE_BLOCKED_ACTIONS = [
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
    "run_this_command": r"\brun this command\b",
    "execute_this": r"\bexecute this\b",
    "chmod": r"\bchmod\b",
    "registry": r"\bregistry\b",
    "firewall": r"\bfirewall\b",
}

PROTECTED_PREFIXES = [
    ("memory\\", "protected_memory_path"),
    ("prompts\\", "protected_prompt_path"),
    ("scripts\\", "protected_script_path"),
    ("tools\\", "protected_tool_path"),
    ("live\\", "protected_live_path"),
    ("staging\\", "protected_staging_path"),
    ("routes\\", "protected_route_path"),
    ("mobile\\engel_remote_worker\\android\\", "protected_android_platform_path"),
]

APPLY_SUFFIXES = {".patch", ".diff"}


class PatchApplicationGateError(ValueError):
    pass


@dataclass
class BundleGateValidation:
    bundle_path: str
    valid: bool
    bundle_id: str | None
    status: str | None
    errors: list[str]
    warnings: list[str]


@dataclass
class GateCreationResult:
    gate_json: str
    gate_markdown: str
    gate: dict[str, Any]


@dataclass
class DryRunCreationResult:
    dry_run_json: str
    dry_run_markdown: str
    dry_run: dict[str, Any]


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
    return (cleaned or "patch_application_gate")[:limit]


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


def ensure_folders(
    gate_root: Path = GATE_ROOT,
    receipts_dir: Path = RECEIPTS_DIR,
    dry_runs_dir: Path = DRY_RUNS_DIR,
) -> None:
    gate_root.mkdir(parents=True, exist_ok=True)
    (gate_root / "examples").mkdir(parents=True, exist_ok=True)
    receipts_dir.mkdir(parents=True, exist_ok=True)
    dry_runs_dir.mkdir(parents=True, exist_ok=True)


def risk_flags_for_text(text: str) -> list[str]:
    flags: list[str] = []
    for flag, pattern in RISK_PATTERNS.items():
        if re.search(pattern, text, re.IGNORECASE):
            flags.append(flag)
    return sorted(set(flags))


def resolve_bundle_path(raw_path: str | Path) -> Path:
    text = str(raw_path)
    if not text or text.startswith(("http://", "https://", "\\\\")):
        raise PatchApplicationGateError("bundle path must be an explicit local Phase 3 bundle path")
    if any(marker in text for marker in ("*", "?", "[")):
        raise PatchApplicationGateError("wildcards are not allowed")
    path = Path(text)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    resolved = path.resolve(strict=False)
    if resolved.is_dir():
        resolved = resolved / "bundle.json"
    if not resolved.exists() or not resolved.is_file():
        raise PatchApplicationGateError("bundle.json does not exist")
    if not is_relative_to(resolved, PROJECT_ROOT):
        raise PatchApplicationGateError("bundle path must stay inside Engel App")
    if not (is_relative_to(resolved, BUNDLE_ROOT) or is_relative_to(resolved, BUNDLE_EXAMPLES)):
        raise PatchApplicationGateError("Phase 4 accepts Phase 3 patch bundle drafts only")
    if resolved.suffix.lower() != ".json":
        raise PatchApplicationGateError("bundle input must be bundle.json")
    if resolved.stat().st_size > MAX_BUNDLE_BYTES:
        raise PatchApplicationGateError(f"bundle input exceeds max size of {MAX_BUNDLE_BYTES} bytes")
    return resolved


def load_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PatchApplicationGateError(f"could not read JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise PatchApplicationGateError("JSON root must be an object")
    return payload


def validate_bundle_for_gate(raw_path: str | Path) -> BundleGateValidation:
    try:
        bundle_json = resolve_bundle_path(raw_path)
    except PatchApplicationGateError as exc:
        return BundleGateValidation(str(raw_path), False, None, None, [str(exc)], [])
    validation = patch_bundle_draft.validate_bundle_file(bundle_json)
    errors = list(validation.errors)
    warnings = list(validation.warnings)
    payload: dict[str, Any] | None = None
    try:
        payload = load_json_object(bundle_json)
    except PatchApplicationGateError as exc:
        errors.append(str(exc))
    if payload is not None:
        if payload.get("trust_level") in {"trusted", "approved", "trusted_memory"}:
            errors.append("bundle trust_level must not be trusted or approved")
        if payload.get("trust_level") != "untrusted_until_human_review":
            errors.append("bundle trust_level must be untrusted_until_human_review")
        if payload.get("status") != "draft_bundle_preview":
            errors.append("bundle status must be draft_bundle_preview")
        if payload.get("requires_review") is not True:
            errors.append("bundle requires_review must be true")
        if payload.get("safe_to_auto_apply") is not False:
            errors.append("bundle safe_to_auto_apply must be false")
        if payload.get("patch_applied") is not False:
            errors.append("bundle patch_applied must be false")
        for index, draft in enumerate(payload.get("proposed_file_drafts", [])):
            if isinstance(draft, dict):
                if draft.get("preview_only") is not True:
                    errors.append(f"proposed_file_drafts[{index}].preview_only must be true")
                if draft.get("source_file_modified") is not False:
                    errors.append(f"proposed_file_drafts[{index}].source_file_modified must be false")
        folder = bundle_json.parent
        if not is_relative_to(bundle_json, BUNDLE_EXAMPLES):
            for path in list(folder.glob("*")) + list((folder / "proposed_files").glob("*") if (folder / "proposed_files").exists() else []):
                if path.is_file() and path.suffix.lower() in APPLY_SUFFIXES:
                    errors.append("bundle contains apply-ready patch/diff file: " + project_relative(path))
    return BundleGateValidation(
        bundle_path=project_relative(bundle_json),
        valid=not errors,
        bundle_id=validation.bundle_id,
        status=validation.status,
        errors=errors,
        warnings=warnings,
    )


def load_validated_bundle(raw_path: str | Path) -> tuple[Path, dict[str, Any], BundleGateValidation]:
    bundle_json = resolve_bundle_path(raw_path)
    validation = validate_bundle_for_gate(bundle_json)
    if not validation.valid:
        raise PatchApplicationGateError("source bundle is invalid for gate review: " + "; ".join(validation.errors))
    return bundle_json, load_json_object(bundle_json), validation


def gate_id_for(bundle_id: str, created_at: str) -> str:
    return f"{timestamp_slug(created_at)}_{safe_slug(bundle_id, 100)}_application_gate"


def dry_run_id_for(bundle_id: str, created_at: str) -> str:
    return f"{timestamp_slug(created_at)}_{safe_slug(bundle_id, 100)}_dry_run"


def target_path_info(target_file: str) -> dict[str, Any]:
    raw = str(target_file or "").strip().replace("/", "\\")
    info: dict[str, Any] = {
        "target_file": raw,
        "exists": False,
        "inside_project": False,
        "protected_flags": [],
    }
    if not raw or raw in {"(undetermined)", "(no target file specified)"}:
        info["protected_flags"] = ["target_unverified"]
        return info
    if raw.startswith(("http://", "https://", "\\\\")) or any(marker in raw for marker in ("*", "?", "[")):
        info["protected_flags"] = ["target_not_writable_by_gate"]
        return info
    path = Path(raw)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    resolved = path.resolve(strict=False)
    inside = is_relative_to(resolved, PROJECT_ROOT)
    info["inside_project"] = inside
    if inside:
        relative = project_relative(resolved).lower()
        info["target_file"] = project_relative(resolved)
        info["exists"] = resolved.exists()
        flags: list[str] = []
        for prefix, flag in PROTECTED_PREFIXES:
            if relative.startswith(prefix):
                flags.append(flag)
        if "\\" not in relative and resolved.suffix.lower() == ".py":
            flags.append("protected_source_root_module")
        if "route" in relative:
            flags.append("protected_route_related_path")
        info["protected_flags"] = sorted(set(flags))
    else:
        info["protected_flags"] = ["outside_project_reference"]
    return info


def target_files_from_bundle(bundle: dict[str, Any]) -> list[str]:
    found: list[str] = []
    raw_targets = bundle.get("target_files")
    if isinstance(raw_targets, list):
        for item in raw_targets:
            if isinstance(item, str) and item not in found:
                found.append(item)
    drafts = bundle.get("proposed_file_drafts")
    if isinstance(drafts, list):
        for draft in drafts:
            if isinstance(draft, dict) and isinstance(draft.get("target_file"), str):
                value = draft["target_file"]
                if value not in found:
                    found.append(value)
    return found[:40]


def proposed_draft_files_from_bundle(bundle: dict[str, Any]) -> list[str]:
    drafts = []
    raw = bundle.get("proposed_file_drafts")
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict) and isinstance(item.get("draft_file"), str):
                drafts.append(item["draft_file"])
    return drafts[:40]


def proposed_file_text(bundle_json: Path, bundle: dict[str, Any]) -> str:
    pieces: list[str] = []
    for draft_file in proposed_draft_files_from_bundle(bundle):
        if not draft_file.startswith("proposed_files/"):
            continue
        path = bundle_json.parent / draft_file.replace("/", "\\")
        if not path.exists() or not path.is_file() or path.stat().st_size > MAX_PROPOSED_FILE_BYTES:
            continue
        try:
            pieces.append(path.read_text(encoding="utf-8", errors="replace")[:MAX_PREVIEW_CHARS])
        except OSError:
            continue
    return "\n".join(pieces)


def risk_flags_for_bundle(bundle_json: Path, bundle: dict[str, Any]) -> list[str]:
    existing = bundle.get("risk_flags") if isinstance(bundle.get("risk_flags"), list) else []
    text = json.dumps(bundle, sort_keys=True) + "\n" + proposed_file_text(bundle_json, bundle)
    return sorted(set([str(item) for item in existing if isinstance(item, str)] + risk_flags_for_text(text)))


def protected_path_flags_for_bundle(bundle: dict[str, Any]) -> list[str]:
    flags: list[str] = []
    for target_file in target_files_from_bundle(bundle):
        flags.extend(target_path_info(target_file).get("protected_flags", []))
    return sorted(set(str(item) for item in flags))


def verification_plan_for_bundle(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    raw = bundle.get("verification_plan")
    plan: list[dict[str, Any]] = []
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
                    "executed_by_gate": False,
                }
            )
    if not plan:
        plan.append(
            {
                "command": ".\\scripts\\codex_verify.ps1",
                "purpose": "Run the full Engel verifier before any future protected patch application.",
                "manual_only": True,
                "executed_by_gate": False,
            }
        )
    return plan


def build_gate_payload(bundle_json: Path, bundle: dict[str, Any], created_at: str | None = None) -> dict[str, Any]:
    stamp = created_at or now_utc()
    bundle_id = str(bundle.get("bundle_id", "unknown_bundle"))
    target_files = target_files_from_bundle(bundle)
    proposed_drafts = proposed_draft_files_from_bundle(bundle)
    risk_flags = risk_flags_for_bundle(bundle_json, bundle)
    return {
        "gate_version": "1",
        "gate_id": gate_id_for(bundle_id, stamp),
        "created_at": stamp,
        "created_by": "Engel Code Companion",
        "source_bundle_id": bundle_id,
        "source_bundle_path": project_relative(bundle_json),
        "source_bundle_hash": sha256_file(bundle_json),
        "trust_level": "untrusted_until_human_approved",
        "status": "gate_review_only",
        "requires_review": True,
        "safe_to_auto_apply": False,
        "patch_applied": False,
        "source_files_modified": False,
        "eligible_for_future_apply_consideration": True,
        "application_enabled_in_this_phase": False,
        "approval_token_required": True,
        "approval_token_present": False,
        "password_gate_required": True,
        "password_verified": False,
        "verifier_pass_required": True,
        "human_review_required": True,
        "required_approvals_before_apply": list(REQUIRED_APPROVALS),
        "blocked_actions": list(REQUIRED_GATE_BLOCKED_ACTIONS),
        "target_files": target_files,
        "proposed_draft_files": proposed_drafts,
        "protected_path_flags": protected_path_flags_for_bundle(bundle),
        "risk_flags": risk_flags,
        "verification_plan": verification_plan_for_bundle(bundle),
        "final_decision": GATE_FINAL_DECISION,
    }


def build_dry_run_payload(bundle_json: Path, bundle: dict[str, Any], created_at: str | None = None) -> dict[str, Any]:
    stamp = created_at or now_utc()
    bundle_id = str(bundle.get("bundle_id", "unknown_bundle"))
    target_details = [target_path_info(target_file) for target_file in target_files_from_bundle(bundle)]
    missing = [str(item["target_file"]) for item in target_details if not item.get("exists")]
    protected_flags: list[str] = []
    for item in target_details:
        protected_flags.extend(str(flag) for flag in item.get("protected_flags", []))
    return {
        "dry_run_version": "1",
        "dry_run_id": dry_run_id_for(bundle_id, stamp),
        "created_at": stamp,
        "source_bundle_id": bundle_id,
        "source_bundle_path": project_relative(bundle_json),
        "source_bundle_hash": sha256_file(bundle_json),
        "status": "dry_run_preview_only",
        "patch_applied": False,
        "source_files_modified": False,
        "safe_to_auto_apply": False,
        "requires_review": True,
        "target_files_checked": target_details,
        "proposed_draft_files_checked": proposed_draft_files_from_bundle(bundle),
        "missing_target_files": missing,
        "protected_path_flags": sorted(set(protected_flags)),
        "risk_flags": risk_flags_for_bundle(bundle_json, bundle),
        "verification_plan": verification_plan_for_bundle(bundle),
        "approval_token_required": True,
        "password_gate_required": True,
        "verifier_pass_required": True,
        "application_enabled_in_this_phase": False,
        "final_decision": DRY_RUN_FINAL_DECISION,
    }


def validate_gate_payload(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required_strings = [
        "gate_version",
        "gate_id",
        "created_at",
        "created_by",
        "source_bundle_id",
        "source_bundle_path",
        "source_bundle_hash",
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
        "status": "gate_review_only",
        "final_decision": GATE_FINAL_DECISION,
    }
    for field, value in expected.items():
        if payload.get(field) != value:
            errors.append(f"{field} must be {value}")
    required_false = ["safe_to_auto_apply", "patch_applied", "source_files_modified", "application_enabled_in_this_phase"]
    required_true = [
        "requires_review",
        "approval_token_required",
        "password_gate_required",
        "verifier_pass_required",
        "human_review_required",
    ]
    for field in required_false:
        if payload.get(field) is not False:
            errors.append(f"{field} must be false")
    for field in required_true:
        if payload.get(field) is not True:
            errors.append(f"{field} must be true")
    if payload.get("approval_token_present") is not False:
        errors.append("approval_token_present must be false in Phase 4")
    if payload.get("password_verified") is not False:
        errors.append("password_verified must be false in Phase 4")
    blocked = payload.get("blocked_actions")
    if not isinstance(blocked, list):
        errors.append("blocked_actions must be a list")
    else:
        missing = [item for item in REQUIRED_GATE_BLOCKED_ACTIONS if item not in blocked]
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


def validate_dry_run_payload(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in ["dry_run_version", "dry_run_id", "created_at", "source_bundle_id", "source_bundle_path", "status", "final_decision"]:
        if not isinstance(payload.get(field), str) or not str(payload.get(field)).strip():
            errors.append(f"{field} must be a non-empty string")
    if payload.get("status") != "dry_run_preview_only":
        errors.append("status must be dry_run_preview_only")
    if payload.get("final_decision") != DRY_RUN_FINAL_DECISION:
        errors.append("final_decision must be " + DRY_RUN_FINAL_DECISION)
    for field in ["patch_applied", "source_files_modified", "safe_to_auto_apply", "application_enabled_in_this_phase"]:
        if payload.get(field) is not False:
            errors.append(f"{field} must be false")
    if payload.get("requires_review") is not True:
        errors.append("requires_review must be true")
    return errors


def gate_json_path_for(gate: dict[str, Any], receipts_dir: Path = RECEIPTS_DIR) -> Path:
    return receipts_dir / f"PATCH_APPLICATION_GATE_{safe_slug(str(gate.get('gate_id', 'gate')))}.json"


def gate_markdown_path_for(gate: dict[str, Any], receipts_dir: Path = RECEIPTS_DIR) -> Path:
    return receipts_dir / f"PATCH_APPLICATION_GATE_{safe_slug(str(gate.get('gate_id', 'gate')))}.md"


def dry_run_json_path_for(dry_run: dict[str, Any], dry_runs_dir: Path = DRY_RUNS_DIR) -> Path:
    return dry_runs_dir / f"PATCH_APPLICATION_DRY_RUN_{safe_slug(str(dry_run.get('dry_run_id', 'dry_run')))}.json"


def dry_run_markdown_path_for(dry_run: dict[str, Any], dry_runs_dir: Path = DRY_RUNS_DIR) -> Path:
    return dry_runs_dir / f"PATCH_APPLICATION_DRY_RUN_{safe_slug(str(dry_run.get('dry_run_id', 'dry_run')))}.md"


def lines_for_values(values: list[Any]) -> str:
    return "\n".join(f"- `{value}`" for value in values) if values else "- none"


def render_gate_markdown(gate: dict[str, Any]) -> str:
    verification = "\n".join(
        f"- `{item.get('command')}` - {bounded_text(item.get('purpose', ''), 240)}"
        for item in gate.get("verification_plan", [])
        if isinstance(item, dict)
    ) or "- none"
    text = f"""# Code Companion Protected Patch Application Gate

## Gate

- timestamp: `{gate.get("created_at")}`
- gate_id: `{gate.get("gate_id")}`
- source bundle path: `{gate.get("source_bundle_path")}`
- source bundle SHA-256: `{gate.get("source_bundle_hash")}`
- status: `{gate.get("status")}`
- eligible for future apply consideration: `{gate.get("eligible_for_future_apply_consideration")}`
- application enabled in this phase: `{gate.get("application_enabled_in_this_phase")}`
- final decision: **{gate.get("final_decision")}**

## Target Files

{lines_for_values(gate.get("target_files", []))}

## Proposed Draft Files

{lines_for_values(gate.get("proposed_draft_files", []))}

## Protected Path Flags

{lines_for_values(gate.get("protected_path_flags", []))}

## Risk Flags

{lines_for_values(gate.get("risk_flags", []))}

## Required Approvals Before Apply

{lines_for_values(gate.get("required_approvals_before_apply", []))}

## Verification Plan

{verification}

## Boundary

No source files were modified.

No patch was applied.

No commands from the bundle were executed.

No trusted memory was written.

Approval token is required before any future apply.

Password/protected-action gate is required before any future apply.

Verifier pass is required before any future apply.
"""
    if len(text) > MAX_REPORT_CHARS:
        text = text[:MAX_REPORT_CHARS] + "\n[gate receipt truncated]\n"
    return text


def render_dry_run_markdown(dry_run: dict[str, Any]) -> str:
    verification = "\n".join(
        f"- `{item.get('command')}` - {bounded_text(item.get('purpose', ''), 240)}"
        for item in dry_run.get("verification_plan", [])
        if isinstance(item, dict)
    ) or "- none"
    target_lines = []
    for item in dry_run.get("target_files_checked", []):
        if isinstance(item, dict):
            target_lines.append(f"- `{item.get('target_file')}` exists={item.get('exists')} inside_project={item.get('inside_project')}")
    text = f"""# Code Companion Patch Application Dry Run

## Dry Run

- timestamp: `{dry_run.get("created_at")}`
- dry_run_id: `{dry_run.get("dry_run_id")}`
- source bundle path: `{dry_run.get("source_bundle_path")}`
- status: `{dry_run.get("status")}`
- final decision: **{dry_run.get("final_decision")}**

## Target Files Checked

{chr(10).join(target_lines) if target_lines else "- none"}

## Missing Target Files

{lines_for_values(dry_run.get("missing_target_files", []))}

## Proposed Draft Files Checked

{lines_for_values(dry_run.get("proposed_draft_files_checked", []))}

## Protected Path Flags

{lines_for_values(dry_run.get("protected_path_flags", []))}

## Risk Flags

{lines_for_values(dry_run.get("risk_flags", []))}

## Verification Plan

{verification}

## Boundary

Dry-run only. No source files were modified. No patch was applied. No bundle commands were executed.
"""
    if len(text) > MAX_REPORT_CHARS:
        text = text[:MAX_REPORT_CHARS] + "\n[dry-run report truncated]\n"
    return text


def write_gate_outputs(gate: dict[str, Any], receipts_dir: Path = RECEIPTS_DIR) -> GateCreationResult:
    receipts_dir.mkdir(parents=True, exist_ok=True)
    json_path = gate_json_path_for(gate, receipts_dir)
    markdown_path = gate_markdown_path_for(gate, receipts_dir)
    json_path.write_text(json.dumps(gate, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(render_gate_markdown(gate), encoding="utf-8")
    return GateCreationResult(str(json_path), str(markdown_path), gate)


def write_dry_run_outputs(dry_run: dict[str, Any], dry_runs_dir: Path = DRY_RUNS_DIR) -> DryRunCreationResult:
    dry_runs_dir.mkdir(parents=True, exist_ok=True)
    json_path = dry_run_json_path_for(dry_run, dry_runs_dir)
    markdown_path = dry_run_markdown_path_for(dry_run, dry_runs_dir)
    json_path.write_text(json.dumps(dry_run, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(render_dry_run_markdown(dry_run), encoding="utf-8")
    return DryRunCreationResult(str(json_path), str(markdown_path), dry_run)


def check_bundle(raw_bundle_path: str | Path, *, receipts_dir: Path = RECEIPTS_DIR, created_at: str | None = None) -> GateCreationResult:
    bundle_json, bundle, _validation = load_validated_bundle(raw_bundle_path)
    gate = build_gate_payload(bundle_json, bundle, created_at=created_at)
    errors = validate_gate_payload(gate)
    if errors:
        raise PatchApplicationGateError("generated gate failed validation: " + "; ".join(errors))
    ensure_folders(GATE_ROOT, receipts_dir, DRY_RUNS_DIR)
    return write_gate_outputs(gate, receipts_dir)


def dry_run_bundle(raw_bundle_path: str | Path, *, dry_runs_dir: Path = DRY_RUNS_DIR, created_at: str | None = None) -> DryRunCreationResult:
    bundle_json, bundle, _validation = load_validated_bundle(raw_bundle_path)
    dry_run = build_dry_run_payload(bundle_json, bundle, created_at=created_at)
    errors = validate_dry_run_payload(dry_run)
    if errors:
        raise PatchApplicationGateError("generated dry-run failed validation: " + "; ".join(errors))
    ensure_folders(GATE_ROOT, RECEIPTS_DIR, dry_runs_dir)
    return write_dry_run_outputs(dry_run, dry_runs_dir)


def gate_receipts(receipts_dir: Path = RECEIPTS_DIR) -> list[Path]:
    if not receipts_dir.exists():
        return []
    return sorted([path for path in receipts_dir.iterdir() if path.is_file() and path.suffix.lower() == ".json"], key=lambda item: item.name.lower())


def dry_run_reports(dry_runs_dir: Path = DRY_RUNS_DIR) -> list[Path]:
    if not dry_runs_dir.exists():
        return []
    return sorted([path for path in dry_runs_dir.iterdir() if path.is_file() and path.suffix.lower() == ".json"], key=lambda item: item.name.lower())


def render_status(
    gate_root: Path = GATE_ROOT,
    receipts_dir: Path = RECEIPTS_DIR,
    dry_runs_dir: Path = DRY_RUNS_DIR,
) -> str:
    ensure_folders(gate_root, receipts_dir, dry_runs_dir)
    return "\n".join(
        [
            "Code Companion patch application gate status",
            f"Gate root: {project_relative(gate_root)}",
            f"Receipts: {project_relative(receipts_dir)}",
            f"Dry runs: {project_relative(dry_runs_dir)}",
            f"Examples: {project_relative(gate_root / 'examples')}",
            f"Gate receipt count: {len(gate_receipts(receipts_dir))}",
            f"Dry-run report count: {len(dry_run_reports(dry_runs_dir))}",
            "report_only_default: true",
            "patch_application_enabled: false",
            "source_mutation_enabled: false",
            "approval_token_required: true",
            "password_gate_required: true",
            "verifier_pass_required: true",
        ]
    )


def render_list(receipts_dir: Path = RECEIPTS_DIR, dry_runs_dir: Path = DRY_RUNS_DIR) -> str:
    lines = ["Code Companion patch application gate receipts:"]
    receipts = gate_receipts(receipts_dir)
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
            + f"{payload.get('gate_id')} | bundle={payload.get('source_bundle_id')} | status={payload.get('status')} | "
            + f"eligible={payload.get('eligible_for_future_apply_consideration')} | "
            + f"approval_token_required={payload.get('approval_token_required')} | "
            + f"password_gate_required={payload.get('password_gate_required')} | "
            + f"verifier_required={payload.get('verifier_pass_required')} | "
            + f"patch_applied={payload.get('patch_applied')}"
        )
    lines.append("")
    lines.append("Code Companion patch application dry-run reports:")
    reports = dry_run_reports(dry_runs_dir)
    if not reports:
        lines.append("- none")
    for path in reports:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            lines.append(f"- {project_relative(path)} invalid")
            continue
        lines.append(
            "- "
            + f"{payload.get('dry_run_id')} | bundle={payload.get('source_bundle_id')} | status={payload.get('status')} | "
            + f"safe_to_auto_apply={payload.get('safe_to_auto_apply')} | patch_applied={payload.get('patch_applied')}"
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
                RECEIPTS_DIR / f"PATCH_APPLICATION_GATE_{slug}.md",
                RECEIPTS_DIR / f"PATCH_APPLICATION_GATE_{slug}.json",
                DRY_RUNS_DIR / f"PATCH_APPLICATION_DRY_RUN_{slug}.md",
                DRY_RUNS_DIR / f"PATCH_APPLICATION_DRY_RUN_{slug}.json",
            ]
        )
    for candidate in candidates:
        resolved = candidate.resolve(strict=False)
        if resolved.exists() and resolved.is_file() and is_relative_to(resolved, GATE_ROOT):
            return resolved
    raise PatchApplicationGateError("gate receipt or dry-run report not found")


def render_show(raw: str | Path) -> str:
    path = resolve_output_for_show(raw)
    text = path.read_text(encoding="utf-8", errors="replace")
    return bounded_text(text, 6000)


def render_validate(raw_bundle_path: str | Path) -> str:
    validation = validate_bundle_for_gate(raw_bundle_path)
    lines = [
        f"Bundle path: {validation.bundle_path}",
        f"Valid for protected gate review: {validation.valid}",
        f"Bundle ID: {validation.bundle_id or '(unknown)'}",
        f"Status: {validation.status or '(unknown)'}",
    ]
    if validation.errors:
        lines.append("Errors:")
        lines.extend(f"- {error}" for error in validation.errors)
    if validation.warnings:
        lines.append("Warnings:")
        lines.extend(f"- {warning}" for warning in validation.warnings)
    lines.append("Patch application enabled in Phase 4: false")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Engel Code Companion protected patch application gate.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="Show gate folders and report-only safety mode.")
    sub.add_parser("list", help="List gate receipts and dry-run reports.")
    validate = sub.add_parser("validate-bundle", help="Validate one Phase 3 bundle for gate review.")
    validate.add_argument("bundle")
    check = sub.add_parser("check", help="Write a protected application gate receipt. Does not apply patches.")
    check.add_argument("bundle")
    dry_run = sub.add_parser("dry-run", help="Write a dry-run eligibility report. Does not edit source.")
    dry_run.add_argument("bundle")
    show = sub.add_parser("show", help="Show a bounded gate receipt or dry-run report.")
    show.add_argument("target")
    requirements = sub.add_parser("requirements", help="Show future apply requirements for a Phase 3 bundle.")
    requirements.add_argument("bundle")
    apply_stub = sub.add_parser("apply", help="Refuse patch application in Phase 4.")
    apply_stub.add_argument("bundle", nargs="?")
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
        if args.command == "validate-bundle":
            result = validate_bundle_for_gate(args.bundle)
            print(render_validate(args.bundle))
            return 0 if result.valid else 2
        if args.command == "check":
            result = check_bundle(args.bundle)
            print("Protected application gate receipt written:")
            print(result.gate_json)
            print(result.gate_markdown)
            print(GATE_FINAL_DECISION)
            return 0
        if args.command == "dry-run":
            result = dry_run_bundle(args.bundle)
            print("Dry-run report written:")
            print(result.dry_run_json)
            print(result.dry_run_markdown)
            print(DRY_RUN_FINAL_DECISION)
            return 0
        if args.command == "show":
            print(render_show(args.target))
            return 0
        if args.command == "requirements":
            validation = validate_bundle_for_gate(args.bundle)
            print(render_validate(args.bundle))
            print("human_review_required: true")
            print("approval_token_required: true")
            print("password_gate_required: true")
            print("verifier_pass_required: true")
            print("application_enabled_in_this_phase: false")
            return 0 if validation.valid else 2
        if args.command == "apply":
            print("Patch application is not enabled in Phase 4.")
            return 2
    except PatchApplicationGateError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
