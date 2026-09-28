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

import engel_code_companion_patch_application_gate as patch_application_gate
import engel_code_companion_patch_bundle_draft as patch_bundle_draft


PROJECT_ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
BUNDLE_ROOT = PROJECT_ROOT / "reports" / "code_companion_patch_bundles"
BUNDLE_EXAMPLES = BUNDLE_ROOT / "examples"
GATE_ROOT = PROJECT_ROOT / "reports" / "code_companion_patch_application_gates"
GATE_RECEIPTS = GATE_ROOT / "receipts"
GATE_DRY_RUNS = GATE_ROOT / "dry_runs"
APPLY_DRY_RUN_ROOT = PROJECT_ROOT / "reports" / "code_companion_patch_apply_dry_runs"
EXAMPLES_DIR = APPLY_DRY_RUN_ROOT / "examples"
RECEIPTS_DIR = APPLY_DRY_RUN_ROOT / "receipts"
ROOT_SIMULATED_FILES_DIR = APPLY_DRY_RUN_ROOT / "simulated_files"
ROOT_DIFF_PREVIEWS_DIR = APPLY_DRY_RUN_ROOT / "diff_previews"

MAX_INPUT_BYTES = 1024 * 1024
MAX_TARGET_BYTES = 512 * 1024
MAX_PREVIEW_CHARS = 1800
MAX_REPORT_CHARS = 22000

FINAL_DECISION = "PATCH APPLY DRY RUN ONLY — NOT APPLIED"
SIMULATED_FILE_BANNER = "PREVIEW ONLY — NOT APPLIED"
DIFF_PREVIEW_BANNER = "PREVIEW DIFF ONLY — NOT APPLY-READY"

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


class PatchApplyDryRunError(ValueError):
    pass


@dataclass
class DryRunInput:
    bundle_json: Path
    bundle: dict[str, Any]
    gate_json: Path | None
    gate: dict[str, Any] | None


@dataclass
class InputValidation:
    input_path: str
    valid: bool
    source_bundle_id: str | None
    source_gate_id: str | None
    errors: list[str]
    warnings: list[str]


@dataclass
class SimulationResult:
    dry_run_folder: str
    dry_run_json: str
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
    return (cleaned or "patch_apply_dry_run")[:limit]


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


def ensure_folders(root: Path = APPLY_DRY_RUN_ROOT) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "examples").mkdir(parents=True, exist_ok=True)
    (root / "receipts").mkdir(parents=True, exist_ok=True)
    (root / "simulated_files").mkdir(parents=True, exist_ok=True)
    (root / "diff_previews").mkdir(parents=True, exist_ok=True)


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
        raise PatchApplyDryRunError(f"could not read JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise PatchApplyDryRunError("JSON root must be an object")
    return payload


def resolve_local_file(raw_path: str | Path) -> Path:
    text = str(raw_path)
    if not text or text.startswith(("http://", "https://", "\\\\")):
        raise PatchApplyDryRunError("input must be an explicit local Code Companion path")
    if any(marker in text for marker in ("*", "?", "[")):
        raise PatchApplyDryRunError("wildcards are not allowed")
    path = Path(text)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    resolved = path.resolve(strict=False)
    if resolved.is_dir():
        bundle_candidate = resolved / "bundle.json"
        dry_run_candidate = resolved / "dry_run.json"
        if bundle_candidate.exists():
            resolved = bundle_candidate
        elif dry_run_candidate.exists():
            resolved = dry_run_candidate
    if not resolved.exists() or not resolved.is_file():
        raise PatchApplyDryRunError("input file does not exist")
    if not is_relative_to(resolved, PROJECT_ROOT):
        raise PatchApplyDryRunError("input must stay inside Engel App")
    if resolved.stat().st_size > MAX_INPUT_BYTES:
        raise PatchApplyDryRunError(f"input exceeds max size of {MAX_INPUT_BYTES} bytes")
    return resolved


def classify_input(path: Path) -> str:
    if is_relative_to(path, BUNDLE_ROOT) or is_relative_to(path, BUNDLE_EXAMPLES):
        if path.name == "bundle.json" or path.parent == BUNDLE_EXAMPLES:
            return "bundle"
    if is_relative_to(path, GATE_RECEIPTS) or is_relative_to(path, GATE_DRY_RUNS):
        if path.suffix.lower() == ".json":
            return "gate"
    raise PatchApplyDryRunError("Phase 5 accepts only Phase 3 bundles or Phase 4 gate receipts/dry-run reports")


def bundle_json_from_payload_path(source_bundle_path: str) -> Path:
    path = Path(source_bundle_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    resolved = path.resolve(strict=False)
    if resolved.is_dir():
        resolved = resolved / "bundle.json"
    return resolved


def validate_gate_payload_for_input(gate_path: Path, gate: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    status = gate.get("status")
    if status == "gate_review_only":
        errors.extend(patch_application_gate.validate_gate_payload(gate))
        if gate.get("application_enabled_in_this_phase") is not False:
            errors.append("gate application_enabled_in_this_phase must be false")
    elif status == "dry_run_preview_only":
        errors.extend(patch_application_gate.validate_dry_run_payload(gate))
        if gate.get("application_enabled_in_this_phase") is not False:
            errors.append("gate dry-run application_enabled_in_this_phase must be false")
    else:
        errors.append("Phase 4 gate input must be gate_review_only or dry_run_preview_only")
    if gate.get("safe_to_auto_apply") is True:
        errors.append("gate safe_to_auto_apply must not be true")
    if gate.get("patch_applied") is not False:
        errors.append("gate patch_applied must be false")
    if gate.get("source_files_modified") is not False:
        errors.append("gate source_files_modified must be false")
    if gate.get("requires_review") is not True:
        errors.append("gate requires_review must be true")
    if "source_bundle_path" not in gate:
        errors.append("gate must reference source_bundle_path")
    if gate_path.suffix.lower() in {".patch", ".diff"}:
        errors.append("gate input must not be a patch/diff file")
    return errors


def validate_bundle_payload_for_input(bundle_path: Path, bundle: dict[str, Any]) -> list[str]:
    result = patch_application_gate.validate_bundle_for_gate(bundle_path)
    errors = list(result.errors)
    if bundle.get("safe_to_auto_apply") is True:
        errors.append("bundle safe_to_auto_apply must not be true")
    if bundle.get("requires_review") is not True:
        errors.append("bundle requires_review must be true")
    if bundle.get("patch_applied") is not False:
        errors.append("bundle patch_applied must be false")
    if bundle.get("source_files_modified") is True:
        errors.append("bundle source_files_modified must not be true")
    return errors


def resolve_dry_run_input(raw_path: str | Path) -> DryRunInput:
    input_path = resolve_local_file(raw_path)
    kind = classify_input(input_path)
    if kind == "bundle":
        bundle_path = input_path
        bundle = load_json_object(bundle_path)
        errors = validate_bundle_payload_for_input(bundle_path, bundle)
        if errors:
            raise PatchApplyDryRunError("bundle is invalid for apply dry-run: " + "; ".join(errors))
        return DryRunInput(bundle_path, bundle, None, None)
    gate_path = input_path
    gate = load_json_object(gate_path)
    gate_errors = validate_gate_payload_for_input(gate_path, gate)
    if gate_errors:
        raise PatchApplyDryRunError("gate input is invalid for apply dry-run: " + "; ".join(gate_errors))
    bundle_path = bundle_json_from_payload_path(str(gate.get("source_bundle_path", "")))
    if not bundle_path.exists() or not bundle_path.is_file():
        raise PatchApplyDryRunError("source bundle referenced by gate does not exist")
    if not (is_relative_to(bundle_path, BUNDLE_ROOT) or is_relative_to(bundle_path, BUNDLE_EXAMPLES)):
        raise PatchApplyDryRunError("source bundle referenced by gate must stay under Phase 3 bundle folders")
    bundle = load_json_object(bundle_path)
    bundle_errors = validate_bundle_payload_for_input(bundle_path, bundle)
    if bundle_errors:
        raise PatchApplyDryRunError("gate source bundle is invalid: " + "; ".join(bundle_errors))
    return DryRunInput(bundle_path, bundle, gate_path, gate)


def validate_input(raw_path: str | Path) -> InputValidation:
    try:
        resolved = resolve_dry_run_input(raw_path)
    except PatchApplyDryRunError as exc:
        return InputValidation(str(raw_path), False, None, None, [str(exc)], [])
    return InputValidation(
        input_path=project_relative(resolved.gate_json or resolved.bundle_json),
        valid=True,
        source_bundle_id=str(resolved.bundle.get("bundle_id")),
        source_gate_id=str(resolved.gate.get("gate_id") or resolved.gate.get("dry_run_id")) if resolved.gate else None,
        errors=[],
        warnings=[],
    )


def dry_run_id_for(bundle_id: str, created_at: str) -> str:
    return f"{timestamp_slug(created_at)}_{safe_slug(bundle_id, 100)}_apply_dry_run"


def target_path_info(target_file: str) -> dict[str, Any]:
    info = patch_application_gate.target_path_info(target_file)
    path_text = str(info.get("target_file") or "")
    path = Path(path_text)
    if path_text and info.get("inside_project"):
        path = PROJECT_ROOT / path
        resolved = path.resolve(strict=False)
        if resolved.exists() and resolved.is_file():
            info["sha256_before"] = sha256_file(resolved)
            info["size_bytes"] = resolved.stat().st_size
        else:
            info["sha256_before"] = None
            info["size_bytes"] = None
    else:
        info["sha256_before"] = None
        info["size_bytes"] = None
    return info


def existing_target_preview(target_file: str) -> str:
    info = patch_application_gate.target_path_info(target_file)
    if not info.get("inside_project") or not info.get("exists"):
        return ""
    path = PROJECT_ROOT / str(info.get("target_file"))
    resolved = path.resolve(strict=False)
    if not resolved.exists() or not resolved.is_file() or resolved.stat().st_size > MAX_TARGET_BYTES:
        return ""
    try:
        return resolved.read_text(encoding="utf-8", errors="replace")[:MAX_PREVIEW_CHARS]
    except OSError:
        return ""


def proposed_draft_preview(bundle_json: Path, draft_file: str) -> str:
    if not draft_file.startswith("proposed_files/"):
        return ""
    path = bundle_json.parent / draft_file.replace("/", "\\")
    if not path.exists() or not path.is_file() or path.stat().st_size > MAX_TARGET_BYTES:
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:MAX_PREVIEW_CHARS]
    except OSError:
        return ""


def collect_target_infos(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    return [target_path_info(target) for target in patch_application_gate.target_files_from_bundle(bundle)]


def collect_hashes(target_infos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    hashes: list[dict[str, Any]] = []
    for info in target_infos:
        hashes.append(
            {
                "target_file": info.get("target_file"),
                "exists": bool(info.get("exists")),
                "sha256_before": info.get("sha256_before"),
                "size_bytes": info.get("size_bytes"),
                "source_file_modified": False,
            }
        )
    return hashes


def risk_flags_for_dry_run(input_data: DryRunInput) -> list[str]:
    existing = input_data.bundle.get("risk_flags") if isinstance(input_data.bundle.get("risk_flags"), list) else []
    gate_risks = input_data.gate.get("risk_flags") if input_data.gate and isinstance(input_data.gate.get("risk_flags"), list) else []
    text = json.dumps(input_data.bundle, sort_keys=True)
    if input_data.gate:
        text += "\n" + json.dumps(input_data.gate, sort_keys=True)
    for draft in input_data.bundle.get("proposed_file_drafts", []):
        if isinstance(draft, dict) and isinstance(draft.get("draft_file"), str):
            text += "\n" + proposed_draft_preview(input_data.bundle_json, draft["draft_file"])
    return sorted(set([str(item) for item in existing + gate_risks if isinstance(item, str)] + risk_flags_for_text(text)))


def verification_plan(input_data: DryRunInput) -> list[dict[str, Any]]:
    source = input_data.gate if input_data.gate and isinstance(input_data.gate.get("verification_plan"), list) else input_data.bundle
    raw = source.get("verification_plan") if isinstance(source, dict) else None
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
                    "executed_by_dry_run": False,
                }
            )
    if not plan:
        plan.append(
            {
                "command": ".\\scripts\\codex_verify.ps1",
                "purpose": "Run the full Engel verifier before any future protected patch application.",
                "manual_only": True,
                "executed_by_dry_run": False,
            }
        )
    return plan


def build_dry_run_payload(input_data: DryRunInput, created_at: str | None = None) -> dict[str, Any]:
    stamp = created_at or now_utc()
    bundle_id = str(input_data.bundle.get("bundle_id", "unknown_bundle"))
    target_infos = collect_target_infos(input_data.bundle)
    protected_flags: list[str] = []
    for info in target_infos:
        protected_flags.extend(str(flag) for flag in info.get("protected_flags", []))
    missing = [str(info.get("target_file")) for info in target_infos if not info.get("exists")]
    dry_run_id = dry_run_id_for(bundle_id, stamp)
    return {
        "dry_run_version": "1",
        "dry_run_id": dry_run_id,
        "created_at": stamp,
        "created_by": "Engel Code Companion",
        "source_bundle_id": bundle_id,
        "source_bundle_path": project_relative(input_data.bundle_json),
        "source_bundle_hash": sha256_file(input_data.bundle_json),
        "source_gate_id": str(input_data.gate.get("gate_id") or input_data.gate.get("dry_run_id")) if input_data.gate else None,
        "source_gate_path": project_relative(input_data.gate_json) if input_data.gate_json else None,
        "source_gate_hash": sha256_file(input_data.gate_json) if input_data.gate_json else None,
        "trust_level": "untrusted_until_human_approved",
        "status": "apply_dry_run_preview",
        "requires_review": True,
        "safe_to_auto_apply": False,
        "patch_applied": False,
        "source_files_modified": False,
        "application_enabled_in_this_phase": False,
        "approval_token_required": True,
        "approval_token_present": False,
        "password_gate_required": True,
        "password_verified": False,
        "verifier_pass_required": True,
        "human_review_required": True,
        "target_files_checked": target_infos,
        "target_file_hashes_before": collect_hashes(target_infos),
        "simulated_files": [],
        "diff_previews": [],
        "missing_target_files": missing,
        "protected_path_flags": sorted(set(protected_flags)),
        "risk_flags": risk_flags_for_dry_run(input_data),
        "verification_plan": verification_plan(input_data),
        "blocked_actions": list(REQUIRED_BLOCKED_ACTIONS),
        "final_decision": FINAL_DECISION,
    }


def validate_dry_run_payload(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in ["dry_run_version", "dry_run_id", "created_at", "created_by", "source_bundle_id", "source_bundle_path", "trust_level", "status", "final_decision"]:
        if not isinstance(payload.get(field), str) or not str(payload.get(field)).strip():
            errors.append(f"{field} must be a non-empty string")
    expected = {
        "created_by": "Engel Code Companion",
        "trust_level": "untrusted_until_human_approved",
        "status": "apply_dry_run_preview",
        "final_decision": FINAL_DECISION,
    }
    for field, value in expected.items():
        if payload.get(field) != value:
            errors.append(f"{field} must be {value}")
    for field in ["safe_to_auto_apply", "patch_applied", "source_files_modified", "application_enabled_in_this_phase"]:
        if payload.get(field) is not False:
            errors.append(f"{field} must be false")
    for field in ["requires_review", "approval_token_required", "password_gate_required", "verifier_pass_required", "human_review_required"]:
        if payload.get(field) is not True:
            errors.append(f"{field} must be true")
    if payload.get("approval_token_present") is not False:
        errors.append("approval_token_present must be false in Phase 5")
    if payload.get("password_verified") is not False:
        errors.append("password_verified must be false in Phase 5")
    blocked = payload.get("blocked_actions")
    if not isinstance(blocked, list):
        errors.append("blocked_actions must be a list")
    else:
        missing = [action for action in REQUIRED_BLOCKED_ACTIONS if action not in blocked]
        if missing:
            errors.append("blocked_actions missing required entries: " + ", ".join(missing))
    return errors


def dry_run_folder_for(dry_run: dict[str, Any], root: Path = APPLY_DRY_RUN_ROOT) -> Path:
    return root / safe_slug(str(dry_run.get("dry_run_id", "apply_dry_run")))


def simulated_file_name(target_file: str, index: int) -> str:
    base = target_file or f"undetermined_{index}"
    safe = safe_slug(base.replace("\\", "__").replace("/", "__"), 120)
    return f"{index:02d}_{safe}.simulated.md"


def render_simulated_file(dry_run: dict[str, Any], bundle: dict[str, Any], draft: dict[str, Any], draft_preview: str) -> str:
    return f"""# Simulated File Preview

{SIMULATED_FILE_BANNER}

target_file: `{draft.get("target_file")}`

source_file_modified: false

patch_applied: false

safe_to_auto_apply: false

dry_run_id: `{dry_run.get("dry_run_id")}`

## Proposed Bundle Summary

```text
{bounded_text(bundle.get("bundle_summary", ""))}
```

## Proposed Draft Content Preview

```text
{bounded_text(draft_preview)}
```

This file is a simulated preview stored under reports only. It is not source code and is not applied.
"""


def write_simulated_files(folder: Path, dry_run: dict[str, Any], input_data: DryRunInput) -> list[dict[str, Any]]:
    simulated_root = folder / "simulated_files"
    simulated_root.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    drafts = input_data.bundle.get("proposed_file_drafts")
    if not isinstance(drafts, list):
        drafts = []
    if not drafts:
        drafts = [{"target_file": "(undetermined)", "draft_file": "", "change_type": "unknown"}]
    for index, draft in enumerate(drafts, start=1):
        if not isinstance(draft, dict):
            continue
        target = str(draft.get("target_file", "(undetermined)"))
        filename = simulated_file_name(target, index)
        path = simulated_root / filename
        draft_preview = proposed_draft_preview(input_data.bundle_json, str(draft.get("draft_file", "")))
        path.write_text(render_simulated_file(dry_run, input_data.bundle, draft, draft_preview), encoding="utf-8")
        results.append(
            {
                "target_file": target,
                "simulated_file": project_relative(path),
                "preview_only": True,
                "source_file_modified": False,
                "patch_applied": False,
            }
        )
    return results


def render_diff_preview(dry_run: dict[str, Any], input_data: DryRunInput) -> str:
    lines = [
        "# Diff Preview",
        "",
        DIFF_PREVIEW_BANNER,
        "",
        "This is a human-readable preview only. It is not a `.patch` or `.diff` file and contains no apply command.",
        "",
    ]
    drafts = input_data.bundle.get("proposed_file_drafts")
    if not isinstance(drafts, list):
        drafts = []
    if not drafts:
        lines.append("No file-level proposed drafts were present in the bundle.")
    for draft in drafts:
        if not isinstance(draft, dict):
            continue
        target = str(draft.get("target_file", "(undetermined)"))
        lines.extend(
            [
                f"## `{target}`",
                "",
                "```text",
                "PREVIEW DIFF ONLY - NOT APPLY-READY",
                f"target_file: {target}",
                f"change_type: {draft.get('change_type', 'unknown')}",
                "source_file_modified: false",
                "patch_applied: false",
                "",
                "Existing target preview:",
                bounded_text(existing_target_preview(target), 700) or "(missing or not previewed)",
                "",
                "Proposed draft preview:",
                bounded_text(proposed_draft_preview(input_data.bundle_json, str(draft.get("draft_file", ""))), 700) or "(no proposed draft preview)",
                "```",
                "",
            ]
        )
    return "\n".join(lines)


def render_readme(dry_run: dict[str, Any]) -> str:
    return f"""# Code Companion Patch Apply Dry-Run

status: {FINAL_DECISION}

dry_run_id: `{dry_run.get("dry_run_id")}`

source bundle path: `{dry_run.get("source_bundle_path")}`

source gate path: `{dry_run.get("source_gate_path") or "(none)"}`

No source files were modified.

No patch was applied.

No commands were executed.

No trusted memory was written.

Approval token/password/verifier gates remain required.
"""


def render_source_hashes(dry_run: dict[str, Any]) -> dict[str, Any]:
    return {
        "dry_run_id": dry_run.get("dry_run_id"),
        "patch_applied": False,
        "source_files_modified": False,
        "target_file_hashes_before": dry_run.get("target_file_hashes_before", []),
    }


def render_change_summary(dry_run: dict[str, Any]) -> str:
    return f"""# Simulated Change Summary

{FINAL_DECISION}

## Missing Target Files

{lines_for_values(dry_run.get("missing_target_files", []))}

## Protected Path Flags

{lines_for_values(dry_run.get("protected_path_flags", []))}

## Simulated Files

{lines_for_values([item.get("simulated_file") for item in dry_run.get("simulated_files", []) if isinstance(item, dict)])}

No live source path was written.
"""


def render_risk_review(dry_run: dict[str, Any]) -> str:
    return f"""# Risk Review

{FINAL_DECISION}

## Risk Flags

{lines_for_values(dry_run.get("risk_flags", []))}

## Protected Path Flags

{lines_for_values(dry_run.get("protected_path_flags", []))}

## Blocked Actions

{lines_for_values(dry_run.get("blocked_actions", []))}
"""


def render_verification_plan(dry_run: dict[str, Any]) -> str:
    lines = [
        "# Verification Plan",
        "",
        "Verification commands listed here were not run by dry-run simulation.",
        "",
    ]
    for item in dry_run.get("verification_plan", []):
        if isinstance(item, dict):
            lines.append(f"- `{item.get('command')}`")
            lines.append(f"  - purpose: {bounded_text(item.get('purpose', ''), 300)}")
            lines.append("  - manual_only: true")
            lines.append("  - executed_by_dry_run: false")
    return "\n".join(lines) + "\n"


def lines_for_values(values: list[Any]) -> str:
    cleaned = [value for value in values if value not in {None, ""}]
    return "\n".join(f"- `{value}`" for value in cleaned) if cleaned else "- none"


def write_dry_run_files(dry_run: dict[str, Any], input_data: DryRunInput, root: Path = APPLY_DRY_RUN_ROOT) -> Path:
    folder = dry_run_folder_for(dry_run, root)
    folder.mkdir(parents=True, exist_ok=True)
    simulated = write_simulated_files(folder, dry_run, input_data)
    diff_path = folder / "diff_preview.md"
    diff_path.write_text(render_diff_preview(dry_run, input_data), encoding="utf-8")
    dry_run["simulated_files"] = simulated
    dry_run["diff_previews"] = [project_relative(diff_path)]
    (folder / "dry_run.json").write_text(json.dumps(dry_run, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (folder / "README.md").write_text(render_readme(dry_run), encoding="utf-8")
    (folder / "source_file_hashes.json").write_text(json.dumps(render_source_hashes(dry_run), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (folder / "simulated_change_summary.md").write_text(render_change_summary(dry_run), encoding="utf-8")
    (folder / "risk_review.md").write_text(render_risk_review(dry_run), encoding="utf-8")
    (folder / "verification_plan.md").write_text(render_verification_plan(dry_run), encoding="utf-8")
    errors = validate_dry_run_payload(dry_run)
    if errors:
        raise PatchApplyDryRunError("written dry-run failed validation: " + "; ".join(errors))
    return folder


def simulate(raw_input: str | Path, *, root: Path = APPLY_DRY_RUN_ROOT, created_at: str | None = None) -> SimulationResult:
    input_data = resolve_dry_run_input(raw_input)
    dry_run = build_dry_run_payload(input_data, created_at=created_at)
    errors = validate_dry_run_payload(dry_run)
    if errors:
        raise PatchApplyDryRunError("generated dry-run failed validation: " + "; ".join(errors))
    ensure_folders(root)
    folder = write_dry_run_files(dry_run, input_data, root)
    return SimulationResult(str(folder), str(folder / "dry_run.json"), dry_run)


def dry_run_folders(root: Path = APPLY_DRY_RUN_ROOT) -> list[Path]:
    if not root.exists():
        return []
    return sorted(
        [
            path
            for path in root.iterdir()
            if path.is_dir() and path.name not in {"examples", "receipts", "simulated_files", "diff_previews"} and (path / "dry_run.json").exists()
        ],
        key=lambda item: item.name.lower(),
    )


def render_status(root: Path = APPLY_DRY_RUN_ROOT) -> str:
    ensure_folders(root)
    return "\n".join(
        [
            "Code Companion patch apply dry-run simulator status",
            f"Dry-run root: {project_relative(root)}",
            f"Examples: {project_relative(root / 'examples')}",
            f"Receipts: {project_relative(root / 'receipts')}",
            f"Root simulated files: {project_relative(root / 'simulated_files')}",
            f"Root diff previews: {project_relative(root / 'diff_previews')}",
            f"Dry-run count: {len(dry_run_folders(root))}",
            "simulator_only: true",
            "patch_application_enabled: false",
            "source_mutation_enabled: false",
            "trusted_memory_write_enabled: false",
        ]
    )


def render_list(root: Path = APPLY_DRY_RUN_ROOT) -> str:
    lines = ["Code Companion patch apply dry-run records:"]
    folders = dry_run_folders(root)
    if not folders:
        lines.append("- none")
    for folder in folders:
        path = folder / "dry_run.json"
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            lines.append(f"- {project_relative(folder)} invalid")
            continue
        lines.append(
            "- "
            + f"{payload.get('dry_run_id')} | bundle={payload.get('source_bundle_id')} | gate={payload.get('source_gate_id')} | "
            + f"status={payload.get('status')} | patch_applied={payload.get('patch_applied')} | "
            + f"source_files_modified={payload.get('source_files_modified')} | safe_to_auto_apply={payload.get('safe_to_auto_apply')}"
        )
    return "\n".join(lines)


def render_validate(raw_path: str | Path) -> str:
    validation = validate_input(raw_path)
    lines = [
        f"Input path: {validation.input_path}",
        f"Valid for apply dry-run simulation: {validation.valid}",
        f"Source bundle ID: {validation.source_bundle_id or '(unknown)'}",
        f"Source gate ID: {validation.source_gate_id or '(none)'}",
    ]
    if validation.errors:
        lines.append("Errors:")
        lines.extend(f"- {error}" for error in validation.errors)
    if validation.warnings:
        lines.append("Warnings:")
        lines.extend(f"- {warning}" for warning in validation.warnings)
    lines.append("Patch application enabled in Phase 5: false")
    return "\n".join(lines)


def resolve_dry_run_folder(raw: str | Path, root: Path = APPLY_DRY_RUN_ROOT) -> Path:
    text = str(raw)
    path = Path(text)
    candidates: list[Path] = []
    if path.is_absolute() or "\\" in text or "/" in text:
        candidate = path if path.is_absolute() else PROJECT_ROOT / path
        candidates.append(candidate if candidate.is_dir() else candidate.parent)
    else:
        candidates.append(root / safe_slug(text))
    for candidate in candidates:
        resolved = candidate.resolve(strict=False)
        if resolved.exists() and resolved.is_dir() and (resolved / "dry_run.json").exists() and is_relative_to(resolved, root):
            return resolved
    raise PatchApplyDryRunError("apply dry-run folder not found")


def render_show(raw: str | Path) -> str:
    folder = resolve_dry_run_folder(raw)
    summary = folder / "README.md"
    payload = folder / "dry_run.json"
    text = ""
    if summary.exists():
        text += summary.read_text(encoding="utf-8", errors="replace")
    if payload.exists():
        text += "\n\n```json\n" + bounded_text(payload.read_text(encoding="utf-8", errors="replace"), 3500) + "\n```\n"
    return bounded_text(text, 7000)


def render_compare(raw: str | Path) -> str:
    folder = resolve_dry_run_folder(raw)
    diff = folder / "diff_preview.md"
    if not diff.exists():
        raise PatchApplyDryRunError("diff preview not found")
    return bounded_text(diff.read_text(encoding="utf-8", errors="replace"), 7000)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Engel Code Companion patch apply dry-run simulator.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="Show dry-run simulator folders and disabled apply status.")
    sub.add_parser("list", help="List apply dry-run records.")
    validate = sub.add_parser("validate-input", help="Validate a Phase 3 bundle or Phase 4 gate input.")
    validate.add_argument("input")
    simulate_cmd = sub.add_parser("simulate", help="Create a reports-only apply dry-run simulation.")
    simulate_cmd.add_argument("input")
    show = sub.add_parser("show", help="Show a bounded dry-run summary.")
    show.add_argument("target")
    compare = sub.add_parser("compare", help="Show the report-only diff preview for a dry-run.")
    compare.add_argument("target")
    apply_stub = sub.add_parser("apply", help="Refuse patch application in Phase 5.")
    apply_stub.add_argument("target", nargs="?")
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
        if args.command == "validate-input":
            result = validate_input(args.input)
            print(render_validate(args.input))
            return 0 if result.valid else 2
        if args.command == "simulate":
            result = simulate(args.input)
            print("Patch apply dry-run written:")
            print(result.dry_run_folder)
            print(result.dry_run_json)
            print(FINAL_DECISION)
            return 0
        if args.command == "show":
            print(render_show(args.target))
            return 0
        if args.command == "compare":
            print(render_compare(args.target))
            return 0
        if args.command == "apply":
            print("Patch application is not enabled in Phase 5.")
            return 2
    except PatchApplyDryRunError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
