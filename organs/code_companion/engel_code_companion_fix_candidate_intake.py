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


PROJECT_ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
CANDIDATE_DIR = PROJECT_ROOT / "reports" / "code_companion_fix_candidates"
EXAMPLES_DIR = CANDIDATE_DIR / "examples"
RECEIPTS_DIR = CANDIDATE_DIR / "receipts"

ALLOWED_SOURCE_ROOTS = [
    PROJECT_ROOT / "reports" / "remote_worker_results",
    PROJECT_ROOT / "reports" / "chat_export_intake",
    PROJECT_ROOT / "reports" / "codex_bridge",
    PROJECT_ROOT / "reports" / "communication_queen_assignments",
    PROJECT_ROOT / "reports" / "remote_worker_auto_assignment",
    PROJECT_ROOT / "reports" / "remote_worker_duplicate_guards",
]

ALLOWED_EXTENSIONS = {".md", ".txt", ".json"}
MAX_SOURCE_BYTES = 1024 * 1024
MAX_TEXT_PREVIEW = 1200
MAX_SUMMARY_CHARS = 900

SOURCE_TYPES = {
    "remote_worker_result",
    "chat_export_intake",
    "verifier_report",
    "codex_bridge_report",
}

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

REQUIRED_REVIEW_REQUIREMENTS = [
    "human_review",
    "verifier_required",
    "approval_token_required_before_apply",
    "password_gate_required_before_protected_action",
]

RISK_PATTERNS = {
    "run_this_command": r"\brun this command\b",
    "powershell": r"\bpowershell\b",
    "cmd_exe": r"\bcmd\.exe\b",
    "bash": r"\bbash\b",
    "wsl": r"\bwsl\b",
    "curl": r"\bcurl\b",
    "invoke_webrequest": r"\binvoke-webrequest\b",
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
}

ISSUE_NEEDLES = [
    "fail",
    "failed",
    "failure",
    "error",
    "rejected",
    "invalid",
    "blocked",
    "duplicate",
    "missing",
    "mismatch",
    "overflow",
    "regression",
    "unsafe",
    "warning",
    "should add",
    "needs",
]


class FixCandidateIntakeError(ValueError):
    pass


@dataclass
class CandidateValidation:
    candidate_path: str
    valid: bool
    candidate_id: str | None
    title: str | None
    status: str | None
    errors: list[str]
    warnings: list[str]


@dataclass
class IntakeResult:
    candidate_path: str
    receipt_path: str
    candidate: dict[str, Any]
    risk_flags: list[str]


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


def ensure_folders(candidate_dir: Path = CANDIDATE_DIR, receipts_dir: Path = RECEIPTS_DIR) -> None:
    candidate_dir.mkdir(parents=True, exist_ok=True)
    (candidate_dir / "examples").mkdir(parents=True, exist_ok=True)
    receipts_dir.mkdir(parents=True, exist_ok=True)


def bounded_text(value: str, limit: int = MAX_TEXT_PREVIEW) -> str:
    clean = value.replace("\r\n", "\n").strip()
    if len(clean) <= limit:
        return clean
    return clean[:limit] + "\n[preview truncated]"


def safe_slug(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip()).strip("._-")
    return (cleaned or "fix_candidate")[:96]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_source_path(raw_path: str | Path) -> Path:
    text = str(raw_path)
    if not text or text.startswith(("http://", "https://", "\\\\")):
        raise FixCandidateIntakeError("source path must be an explicit local file")
    if any(marker in text for marker in ("*", "?", "[")):
        raise FixCandidateIntakeError("wildcards are not allowed")
    path = Path(text)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    resolved = path.resolve(strict=False)
    if not resolved.exists() or not resolved.is_file():
        raise FixCandidateIntakeError("source file does not exist")
    if not is_relative_to(resolved, PROJECT_ROOT):
        raise FixCandidateIntakeError("source file must stay inside Engel App")
    if not any(is_relative_to(resolved, root) for root in ALLOWED_SOURCE_ROOTS):
        allowed = ", ".join(project_relative(root) for root in ALLOWED_SOURCE_ROOTS)
        raise FixCandidateIntakeError("source path is outside allowed report roots: " + allowed)
    if resolved.suffix.lower() not in ALLOWED_EXTENSIONS:
        raise FixCandidateIntakeError("source extension must be .md, .txt, or .json")
    if resolved.stat().st_size > MAX_SOURCE_BYTES:
        raise FixCandidateIntakeError(f"source file exceeds max intake size of {MAX_SOURCE_BYTES} bytes")
    return resolved


def read_source_text(path: Path) -> str:
    raw = path.read_bytes()
    if b"\x00" in raw[:4096]:
        raise FixCandidateIntakeError("binary-looking source file rejected")
    return raw.decode("utf-8", errors="replace")


def risk_flags_for_text(text: str) -> list[str]:
    flags: list[str] = []
    for flag, pattern in RISK_PATTERNS.items():
        if re.search(pattern, text, re.IGNORECASE):
            flags.append(flag)
    return sorted(set(flags))


def infer_source_type(path: Path, text: str) -> str:
    rel = project_relative(path).lower()
    lowered = text.lower()
    if rel.startswith("reports\\remote_worker_results\\"):
        return "remote_worker_result"
    if rel.startswith("reports\\chat_export_intake\\"):
        return "chat_export_intake"
    if "verifier" in rel or "verifier" in lowered or "engel_codex_verify_fail" in lowered:
        return "verifier_report"
    return "codex_bridge_report"


def extract_relevant_lines(text: str, limit: int = 6) -> list[str]:
    lines = [line.strip(" -\t") for line in text.replace("\r\n", "\n").splitlines()]
    relevant: list[str] = []
    for line in lines:
        if not line:
            continue
        lowered = line.lower()
        if any(needle in lowered for needle in ISSUE_NEEDLES):
            relevant.append(line[:220])
        if len(relevant) >= limit:
            break
    if relevant:
        return relevant
    for line in lines:
        if line and not line.startswith("```"):
            relevant.append(line[:220])
        if len(relevant) >= min(3, limit):
            break
    return relevant


def infer_title(path: Path, text: str) -> str:
    for line in text.replace("\r\n", "\n").splitlines():
        clean = line.strip()
        if clean.startswith("#"):
            title = clean.lstrip("#").strip()
            if title:
                return title[:120]
    stem = path.stem.replace("_", " ").strip()
    return stem[:120] or "Untrusted fix candidate draft"


def infer_likely_files(text: str) -> list[str]:
    pattern = r"\b(?:[A-Za-z0-9_.-]+\\)+(?:[A-Za-z0-9_.-]+)(?:\.(?:py|ps1|json|md|txt|dart|yaml|yml))\b"
    found: list[str] = []
    for match in re.finditer(pattern, text[:MAX_SOURCE_BYTES]):
        value = match.group(0)
        if value not in found and not value.lower().startswith(("live\\", "staging\\")):
            found.append(value[:180])
        if len(found) >= 12:
            break
    return found


def problem_summary_from_text(path: Path, text: str) -> str:
    lines = extract_relevant_lines(text)
    if not lines:
        return "No explicit failure was extracted from the bounded source report."
    joined = " ".join(lines)
    return bounded_text(joined, MAX_SUMMARY_CHARS)


def proposed_fix_from_text(text: str) -> str:
    lowered = text.lower()
    if "duplicate" in lowered and ("claim" in lowered or "return" in lowered):
        return "Review the duplicate claim or duplicate return guard path. Draft only; do not apply without verifier and human approval."
    if "verifier" in lowered and ("fail" in lowered or "failed" in lowered):
        return "Investigate the reported verifier failure and prepare a bounded patch proposal after human review."
    if "rejected" in lowered or "invalid" in lowered:
        return "Review the rejection or invalid-state cause and prepare a narrow correction proposal if confirmed by local evidence."
    if "missing" in lowered or "mismatch" in lowered:
        return "Check the referenced missing or mismatched artifact and draft a minimal candidate fix if local files confirm it."
    return "No automatic fix is proposed. Preserve this as an untrusted review observation for a human Code Companion pass."


def candidate_id_for(source_path: str, source_hash: str, created_at: str) -> str:
    seed = f"ENGEL_CODE_COMPANION_FIX_CANDIDATE_INTAKE_V1|{source_path}|{source_hash}|{created_at}".encode("utf-8")
    return "code_companion_fix_candidate_" + hashlib.sha256(seed).hexdigest()[:16]


def build_candidate_from_source(path: Path, text: str, source_hash: str, created_at: str | None = None) -> dict[str, Any]:
    stamp = created_at or now_utc()
    rel_source = project_relative(path)
    source_type = infer_source_type(path, text)
    title = infer_title(path, text)
    return {
        "candidate_version": "1",
        "candidate_id": candidate_id_for(rel_source, source_hash, stamp),
        "created_at": stamp,
        "created_by": "Engel Code Companion",
        "source_type": source_type,
        "source_path": rel_source,
        "source_hash": source_hash,
        "trust_level": "untrusted_until_human_review",
        "requires_review": True,
        "safe_to_auto_apply": False,
        "patch_applied": False,
        "title": title,
        "problem_summary": problem_summary_from_text(path, text),
        "proposed_fix_summary": proposed_fix_from_text(text),
        "likely_files": infer_likely_files(text),
        "blocked_actions": list(REQUIRED_BLOCKED_ACTIONS),
        "review_requirements": list(REQUIRED_REVIEW_REQUIREMENTS),
        "status": "draft_untrusted",
    }


def validate_candidate_payload(payload: dict[str, Any], source_path: Path | None = None) -> CandidateValidation:
    errors: list[str] = []
    warnings: list[str] = []

    def require_string(field: str) -> str | None:
        value = payload.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{field} is required and must be a non-empty string")
            return None
        return value

    require_string("candidate_version")
    candidate_id = require_string("candidate_id")
    require_string("created_at")
    created_by = require_string("created_by")
    source_type = require_string("source_type")
    require_string("source_path")
    require_string("source_hash")
    trust_level = require_string("trust_level")
    title = require_string("title")
    require_string("problem_summary")
    require_string("proposed_fix_summary")
    status = require_string("status")

    if created_by and created_by != "Engel Code Companion":
        errors.append("created_by must be Engel Code Companion")
    if source_type and source_type not in SOURCE_TYPES:
        errors.append("source_type is not allowed")
    if trust_level and trust_level != "untrusted_until_human_review":
        errors.append("trust_level must be untrusted_until_human_review")
    if payload.get("requires_review") is not True:
        errors.append("requires_review must be true")
    if payload.get("safe_to_auto_apply") is not False:
        errors.append("safe_to_auto_apply must be false")
    if payload.get("patch_applied") is not False:
        errors.append("patch_applied must be false")
    if payload.get("status") == "applied":
        errors.append("candidate status must not be applied")

    likely_files = payload.get("likely_files")
    if not isinstance(likely_files, list) or not all(isinstance(item, str) for item in likely_files):
        errors.append("likely_files must be a list of strings")

    blocked_actions = payload.get("blocked_actions")
    if not isinstance(blocked_actions, list):
        errors.append("blocked_actions must be a list")
    else:
        missing = [action for action in REQUIRED_BLOCKED_ACTIONS if action not in blocked_actions]
        if missing:
            errors.append("blocked_actions missing required entries: " + ", ".join(missing))

    review_requirements = payload.get("review_requirements")
    if not isinstance(review_requirements, list):
        errors.append("review_requirements must be a list")
    else:
        missing = [item for item in REQUIRED_REVIEW_REQUIREMENTS if item not in review_requirements]
        if missing:
            errors.append("review_requirements missing required entries: " + ", ".join(missing))

    combined = "\n".join(str(payload.get(field, "")) for field in ["problem_summary", "proposed_fix_summary", "title"])
    if risk_flags_for_text(combined):
        warnings.append("candidate text contains risky terms; keep strict human review")

    return CandidateValidation(
        candidate_path=project_relative(source_path) if source_path else "(payload)",
        valid=not errors,
        candidate_id=candidate_id,
        title=title,
        status=status,
        errors=errors,
        warnings=warnings,
    )


def validate_candidate_file(path: Path) -> CandidateValidation:
    if not path.exists() or not path.is_file():
        return CandidateValidation(project_relative(path), False, None, None, None, ["candidate file does not exist"], [])
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return CandidateValidation(project_relative(path), False, None, None, None, [f"could not parse candidate JSON: {exc}"], [])
    if not isinstance(payload, dict):
        return CandidateValidation(project_relative(path), False, None, None, None, ["candidate JSON root must be an object"], [])
    return validate_candidate_payload(payload, path)


def candidate_path_for(candidate: dict[str, Any], candidate_dir: Path = CANDIDATE_DIR) -> Path:
    stamp = str(candidate.get("created_at", now_utc())).replace(":", "").replace("-", "")
    stamp = stamp.replace("+0000", "Z").replace("+00:00", "Z")
    return candidate_dir / f"{safe_slug(stamp)}_{safe_slug(str(candidate.get('candidate_id', 'candidate')))}.json"


def receipt_path_for(candidate: dict[str, Any], receipts_dir: Path = RECEIPTS_DIR) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return receipts_dir / f"CODE_COMPANION_FIX_CANDIDATE_INTAKE_{stamp}_{safe_slug(str(candidate.get('candidate_id', 'candidate')))}.md"


def write_candidate(candidate: dict[str, Any], candidate_dir: Path = CANDIDATE_DIR) -> Path:
    ensure_folders(candidate_dir, candidate_dir / "receipts")
    path = candidate_path_for(candidate, candidate_dir)
    path.write_text(json.dumps(candidate, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def write_receipt(
    candidate: dict[str, Any],
    candidate_path: Path,
    risk_flags: list[str],
    receipt_dir: Path = RECEIPTS_DIR,
    source_preview: str = "",
) -> Path:
    receipt_dir.mkdir(parents=True, exist_ok=True)
    path = receipt_path_for(candidate, receipt_dir)
    risks = "\n".join(f"- {flag}" for flag in risk_flags) or "- none"
    likely_files = "\n".join(f"- `{item}`" for item in candidate.get("likely_files", [])) or "- none"
    text = f"""# Engel Code Companion Fix Candidate Intake Receipt

## Intake

- candidate ID: `{candidate.get("candidate_id")}`
- candidate path: `{project_relative(candidate_path)}`
- source type: `{candidate.get("source_type")}`
- source path: `{candidate.get("source_path")}`
- source SHA-256: `{candidate.get("source_hash")}`
- trust level: `{candidate.get("trust_level")}`
- requires_review: `{candidate.get("requires_review")}`
- safe_to_auto_apply: `{candidate.get("safe_to_auto_apply")}`
- patch_applied: `{candidate.get("patch_applied")}`
- status: `{candidate.get("status")}`

## Candidate Summary

Title: {candidate.get("title")}

Problem summary:

```text
{candidate.get("problem_summary")}
```

Proposed fix summary:

```text
{candidate.get("proposed_fix_summary")}
```

## Likely Files

{likely_files}

## Risk Flags

{risks}

## Source Preview

```text
{source_preview}
```

## Boundary

This intake created an untrusted fix candidate draft only.

No patch was applied. No source, route, queue, or trusted memory was mutated. No command from the source report was executed.
"""
    path.write_text(text, encoding="utf-8")
    return path


def intake_source_file(
    raw_path: str | Path,
    *,
    candidate_dir: Path = CANDIDATE_DIR,
    receipt_dir: Path = RECEIPTS_DIR,
    created_at: str | None = None,
) -> IntakeResult:
    source_path = resolve_source_path(raw_path)
    text = read_source_text(source_path)
    digest = sha256_file(source_path)
    candidate = build_candidate_from_source(source_path, text, digest, created_at=created_at)
    validation = validate_candidate_payload(candidate)
    if not validation.valid:
        raise FixCandidateIntakeError("generated candidate failed validation: " + "; ".join(validation.errors))
    ensure_folders(candidate_dir, receipt_dir)
    candidate_path = write_candidate(candidate, candidate_dir)
    risk_flags = risk_flags_for_text(text)
    receipt_path = write_receipt(
        candidate,
        candidate_path,
        risk_flags,
        receipt_dir=receipt_dir,
        source_preview=bounded_text(text, 700),
    )
    return IntakeResult(str(candidate_path), str(receipt_path), candidate, risk_flags)


def candidate_files(candidate_dir: Path = CANDIDATE_DIR) -> list[Path]:
    if not candidate_dir.exists():
        return []
    try:
        return sorted(
            [
                path
                for path in candidate_dir.iterdir()
                if path.is_file() and path.suffix.lower() == ".json"
            ],
            key=lambda item: item.name.lower(),
        )
    except OSError:
        return []


def render_status(candidate_dir: Path = CANDIDATE_DIR, receipts_dir: Path = RECEIPTS_DIR) -> str:
    ensure_folders(candidate_dir, receipts_dir)
    candidates = candidate_files(candidate_dir)
    valid = 0
    invalid = 0
    for path in candidates:
        result = validate_candidate_file(path)
        if result.valid:
            valid += 1
        else:
            invalid += 1
    lines = [
        "Engel Code Companion Fix Candidate Intake V1",
        "Mode: manual / local / untrusted / draft-only",
        f"Candidate folder: {project_relative(candidate_dir)}",
        f"Receipt folder: {project_relative(receipts_dir)}",
        f"Candidate count: {len(candidates)}",
        f"Valid-looking candidates: {valid}",
        f"Invalid-looking candidates: {invalid}",
        "No patch apply, no source edits, no route mutation, no trusted-memory write, no command execution.",
    ]
    return "\n".join(lines)


def render_list(candidate_dir: Path = CANDIDATE_DIR) -> str:
    candidates = candidate_files(candidate_dir)
    if not candidates:
        return "No Code Companion fix candidate files found."
    lines = ["Code Companion fix candidate files:"]
    for path in candidates:
        result = validate_candidate_file(path)
        lines.append(
            f"- {project_relative(path)} | valid={result.valid} | "
            f"id={result.candidate_id or '(none)'} | title={result.title or '(none)'} | status={result.status or '(none)'}"
        )
    return "\n".join(lines)


def render_validation(result: CandidateValidation) -> str:
    lines = [
        "Code Companion fix candidate validation",
        f"candidate: {result.candidate_path}",
        f"valid: {result.valid}",
        f"candidate_id: {result.candidate_id or '(none)'}",
        f"title: {result.title or '(none)'}",
        f"status: {result.status or '(none)'}",
    ]
    if result.errors:
        lines.append("errors:")
        lines.extend(f"- {error}" for error in result.errors)
    if result.warnings:
        lines.append("warnings:")
        lines.extend(f"- {warning}" for warning in result.warnings)
    lines.append("UNTRUSTED FIX CANDIDATE DRAFT ONLY - NOT APPLIED")
    return "\n".join(lines)


def render_intake(result: IntakeResult) -> str:
    risks = ", ".join(result.risk_flags) if result.risk_flags else "none"
    return "\n".join(
        [
            "Code Companion fix candidate intake",
            f"candidate: {project_relative(Path(result.candidate_path))}",
            f"receipt: {project_relative(Path(result.receipt_path))}",
            f"candidate_id: {result.candidate.get('candidate_id')}",
            f"trust_level: {result.candidate.get('trust_level')}",
            f"requires_review: {result.candidate.get('requires_review')}",
            f"safe_to_auto_apply: {result.candidate.get('safe_to_auto_apply')}",
            f"patch_applied: {result.candidate.get('patch_applied')}",
            f"risk_flags: {risks}",
            "UNTRUSTED FIX CANDIDATE DRAFT ONLY - NOT APPLIED",
        ]
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Manual intake for untrusted Engel Code Companion fix candidate drafts.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    sub.add_parser("list")
    validate_parser = sub.add_parser("validate")
    validate_parser.add_argument("path")
    intake_parser = sub.add_parser("intake")
    intake_parser.add_argument("path")
    args = parser.parse_args(argv)

    try:
        if args.command == "status":
            print(render_status())
            return 0
        if args.command == "list":
            print(render_list())
            return 0
        if args.command == "validate":
            result = validate_candidate_file(Path(args.path))
            print(render_validation(result))
            return 0 if result.valid else 1
        if args.command == "intake":
            result = intake_source_file(args.path)
            print(render_intake(result))
            return 0
    except FixCandidateIntakeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
