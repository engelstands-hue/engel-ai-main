from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
INTAKE_ROOT = PROJECT_ROOT / "remote_workers" / "manual_result_intake"
INCOMING_DIR = INTAKE_ROOT / "incoming"
REVIEWED_DIR = INTAKE_ROOT / "reviewed"
INVALID_DIR = INTAKE_ROOT / "invalid"
EXAMPLES_DIR = INTAKE_ROOT / "examples"
REPORTS_DIR = PROJECT_ROOT / "reports" / "remote_worker_results"
MAX_RESULT_BYTES = 1024 * 1024
PREVIEW_CHARS = 800

REQUIRED_TRUST_LEVEL = "untrusted_until_engel_review"
REQUIRED_WORKER_DEVICE_PREFIX = "engel_remote_worker"
FINAL_DECISION_TEXT = "UNTRUSTED REVIEW ONLY — NOT APPLIED"

FORBIDDEN_TRUE_FIELDS = {
    "auto_apply",
    "safe_to_auto_apply",
    "trusted",
    "write_trusted_memory",
    "execute_commands",
    "mutate_source",
    "mutate_routes",
    "mutate_queue",
    "control_engel",
}

RISK_PATTERNS = {
    "command_execution_request": r"\brun this command\b|\bexecute\b",
    "powershell_reference": r"\bpowershell\b",
    "cmd_reference": r"\bcmd\.exe\b",
    "bash_reference": r"\bbash\b",
    "wsl_reference": r"\bwsl\b",
    "download_request": r"\bcurl\b|\binvoke-webrequest\b|\bdownload\b",
    "trusted_memory_request": r"\bwrite memory\b|\btrusted memory\b",
    "patch_apply_request": r"\bapply patch\b|\bauto apply\b",
    "source_mutation_request": r"\bmodify source\b|\bmutate source\b",
    "route_mutation_request": r"\bmutate route\b",
    "queue_mutation_request": r"\bqueue this\b|\bmutate queue\b",
    "bypass_request": r"\bbypass\b|\bignore previous instructions\b",
}


@dataclass
class ValidationResult:
    source_path: str
    source_hash: str | None
    valid_json: bool
    valid_for_review: bool
    validation_status: str
    packet_id: str | None
    worker_device: str | None
    result_type: str | None
    review_target: str | None
    trust_level: str | None
    requires_review: bool | None
    safe_to_auto_apply: bool | None
    errors: list[str]
    warnings: list[str]
    risk_flags: list[str]
    draft_text_preview: str
    suggested_next_step_preview: str


@dataclass
class IntakeReceipt:
    receipt_path: str
    validation: ValidationResult
    final_decision: str


def project_relative(path: Path) -> str:
    try:
        return str(path.resolve(strict=False).relative_to(PROJECT_ROOT.resolve(strict=False))).replace("/", "\\")
    except ValueError:
        return str(path.resolve(strict=False))


def is_within_project(path: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(PROJECT_ROOT.resolve(strict=False))
        return True
    except ValueError:
        return False


def bounded_preview(value: Any, limit: int = PREVIEW_CHARS) -> str:
    if value is None:
        return ""
    text = str(value).replace("\r\n", "\n").strip()
    if len(text) <= limit:
        return text
    return text[:limit] + "\n[preview truncated]"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_result_text(path: Path) -> tuple[str | None, list[str], str | None]:
    errors: list[str] = []
    if not path.exists() or not path.is_file():
        return None, ["source file does not exist"], None
    if path.suffix.lower() != ".json":
        errors.append("source file must be a .json file")
    if not is_within_project(path):
        errors.append("source file must be inside the Engel App project root")
    try:
        size = path.stat().st_size
    except OSError as exc:
        return None, [f"could not stat source file: {exc}"], None
    if size > MAX_RESULT_BYTES:
        errors.append(f"source file exceeds max result size of {MAX_RESULT_BYTES} bytes")
    if errors:
        return None, errors, None
    try:
        text = path.read_text(encoding="utf-8")
        digest = sha256_file(path)
    except OSError as exc:
        return None, [f"could not read source file: {exc}"], None
    return text, [], digest


def parse_json_object(text: str) -> tuple[dict[str, Any] | None, str | None]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        return None, f"invalid JSON: {exc}"
    if not isinstance(payload, dict):
        return None, "result JSON root must be an object"
    return payload, None


def truthy(value: Any) -> bool:
    if value is True:
        return True
    if isinstance(value, str) and value.strip().lower() == "true":
        return True
    return False


def collect_string_values(value: Any) -> list[str]:
    found: list[str] = []

    def visit(node: Any) -> None:
        if isinstance(node, str):
            found.append(node)
        elif isinstance(node, dict):
            for child in node.values():
                visit(child)
        elif isinstance(node, list):
            for child in node:
                visit(child)

    visit(value)
    return found


def forbidden_true_field_errors(value: Any, prefix: str = "") -> list[str]:
    errors: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            child_path = f"{prefix}.{key_text}" if prefix else key_text
            if key_text.lower() in FORBIDDEN_TRUE_FIELDS and truthy(child):
                errors.append(f"forbidden safety override is true: {child_path}")
            errors.extend(forbidden_true_field_errors(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            errors.extend(forbidden_true_field_errors(child, f"{prefix}[{index}]"))
    return errors


def risk_flags_for_payload(payload: dict[str, Any]) -> list[str]:
    text = "\n".join(collect_string_values(payload)).lower()
    flags: list[str] = []
    for flag, pattern in RISK_PATTERNS.items():
        if re.search(pattern, text, re.IGNORECASE):
            flags.append(flag)
    return sorted(set(flags))


def validate_payload(payload: dict[str, Any], source_path: Path, source_hash: str | None) -> ValidationResult:
    errors: list[str] = []
    warnings: list[str] = []

    result_version = payload.get("result_version")
    packet_id = payload.get("packet_id")
    worker_device = payload.get("worker_device")
    trust_level = payload.get("trust_level")
    result_type = payload.get("result_type")
    review_target = payload.get("review_target")
    requires_review = payload.get("requires_review")
    safe_to_auto_apply = payload.get("safe_to_auto_apply")
    draft_text = payload.get("draft_text")
    suggested_next_step = payload.get("suggested_next_step")

    if result_version in (None, ""):
        errors.append("result_version is required")
    if not isinstance(packet_id, str) or not packet_id.strip():
        errors.append("packet_id is required and must be non-empty")
    if not isinstance(worker_device, str) or not worker_device.strip():
        errors.append("worker_device is required")
    elif not worker_device.startswith(REQUIRED_WORKER_DEVICE_PREFIX):
        warnings.append("worker_device is not the expected Engel Remote Worker prefix")
    if not isinstance(trust_level, str) or REQUIRED_TRUST_LEVEL not in trust_level:
        errors.append("trust_level must include untrusted_until_engel_review")
    if requires_review is not True:
        errors.append("requires_review must be true")
    if safe_to_auto_apply is not False:
        errors.append("safe_to_auto_apply must be false")
    if not isinstance(result_type, str) or not result_type.strip():
        errors.append("result_type is required")
    if "draft_text" not in payload:
        errors.append("draft_text is required")
    elif not isinstance(draft_text, str):
        errors.append("draft_text must be a string")
    elif draft_text.strip() == "":
        warnings.append("draft_text is empty")

    errors.extend(forbidden_true_field_errors(payload))
    risk_flags = risk_flags_for_payload(payload)
    if risk_flags:
        warnings.append("risky text detected; stricter human review required")

    valid = not errors
    return ValidationResult(
        source_path=project_relative(source_path),
        source_hash=source_hash,
        valid_json=True,
        valid_for_review=valid,
        validation_status="valid_for_review" if valid else "invalid",
        packet_id=packet_id if isinstance(packet_id, str) else None,
        worker_device=worker_device if isinstance(worker_device, str) else None,
        result_type=result_type if isinstance(result_type, str) else None,
        review_target=review_target if isinstance(review_target, str) else None,
        trust_level=trust_level if isinstance(trust_level, str) else None,
        requires_review=requires_review if isinstance(requires_review, bool) else None,
        safe_to_auto_apply=safe_to_auto_apply if isinstance(safe_to_auto_apply, bool) else None,
        errors=errors,
        warnings=warnings,
        risk_flags=risk_flags,
        draft_text_preview=bounded_preview(draft_text),
        suggested_next_step_preview=bounded_preview(suggested_next_step),
    )


def validate_result_file(path: Path) -> ValidationResult:
    text, read_errors, digest = read_result_text(path)
    if text is None:
        return ValidationResult(
            source_path=project_relative(path),
            source_hash=digest,
            valid_json=False,
            valid_for_review=False,
            validation_status="invalid",
            packet_id=None,
            worker_device=None,
            result_type=None,
            review_target=None,
            trust_level=None,
            requires_review=None,
            safe_to_auto_apply=None,
            errors=read_errors,
            warnings=[],
            risk_flags=[],
            draft_text_preview="",
            suggested_next_step_preview="",
        )
    payload, parse_error = parse_json_object(text)
    if payload is None:
        return ValidationResult(
            source_path=project_relative(path),
            source_hash=digest,
            valid_json=False,
            valid_for_review=False,
            validation_status="invalid",
            packet_id=None,
            worker_device=None,
            result_type=None,
            review_target=None,
            trust_level=None,
            requires_review=None,
            safe_to_auto_apply=None,
            errors=[parse_error or "invalid JSON"],
            warnings=[],
            risk_flags=[],
            draft_text_preview="",
            suggested_next_step_preview="",
        )
    return validate_payload(payload, path, digest)


def incoming_json_files() -> list[Path]:
    if not INCOMING_DIR.exists():
        return []
    try:
        return sorted(
            [path for path in INCOMING_DIR.iterdir() if path.is_file() and path.suffix.lower() == ".json"],
            key=lambda item: item.name.lower(),
        )
    except OSError:
        return []


def latest_report() -> Path | None:
    if not REPORTS_DIR.exists():
        return None
    reports = sorted(REPORTS_DIR.glob("REMOTE_WORKER_RESULT_INTAKE_*.md"), key=lambda item: item.stat().st_mtime)
    return reports[-1] if reports else None


def render_status() -> str:
    files = incoming_json_files()
    valid = 0
    invalid = 0
    for path in files:
        result = validate_result_file(path)
        if result.valid_for_review:
            valid += 1
        else:
            invalid += 1
    latest = latest_report()
    lines = [
        "Engel Remote Worker Result Intake V1",
        "Mode: manual / local / untrusted / review-only",
        f"Incoming folder: {project_relative(INCOMING_DIR)}",
        f"Reviewed folder: {project_relative(REVIEWED_DIR)}",
        f"Invalid folder: {project_relative(INVALID_DIR)}",
        f"Reports folder: {project_relative(REPORTS_DIR)}",
        f"incoming JSON files: {len(files)}",
        f"valid-looking result files: {valid}",
        f"invalid-looking result files: {invalid}",
        f"latest report: {project_relative(latest) if latest else '(none)'}",
        "No watcher, no auto-import, no execution, no auto-apply.",
    ]
    return "\n".join(lines)


def render_list() -> str:
    files = incoming_json_files()
    if not files:
        return "No incoming Remote Worker result JSON files found."
    lines = ["Incoming Remote Worker result JSON files:"]
    for path in files:
        result = validate_result_file(path)
        packet = result.packet_id or "invalid"
        lines.append(f"- {project_relative(path)} | {result.validation_status} | packet_id={packet}")
    return "\n".join(lines)


def render_validation(result: ValidationResult) -> str:
    lines = [
        "Remote Worker result validation",
        f"source: {result.source_path}",
        f"status: {result.validation_status}",
        f"valid_for_review: {result.valid_for_review}",
        f"packet_id: {result.packet_id or '(none)'}",
        f"worker_device: {result.worker_device or '(none)'}",
        f"result_type: {result.result_type or '(none)'}",
        f"requires_review: {result.requires_review}",
        f"safe_to_auto_apply: {result.safe_to_auto_apply}",
    ]
    if result.errors:
        lines.append("errors:")
        lines.extend(f"- {item}" for item in result.errors)
    if result.warnings:
        lines.append("warnings:")
        lines.extend(f"- {item}" for item in result.warnings)
    if result.risk_flags:
        lines.append("risk_flags:")
        lines.extend(f"- {item}" for item in result.risk_flags)
    lines.append(FINAL_DECISION_TEXT)
    return "\n".join(lines)


def safe_packet_id(packet_id: str | None) -> str:
    if not packet_id:
        return "invalid"
    clean = re.sub(r"[^A-Za-z0-9_.-]+", "_", packet_id.strip())
    return clean[:80] or "invalid"


def receipt_path_for(result: ValidationResult, timestamp: str | None = None) -> Path:
    stamp = timestamp or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return REPORTS_DIR / f"REMOTE_WORKER_RESULT_INTAKE_{stamp}_{safe_packet_id(result.packet_id)}.md"


def write_receipt(
    result: ValidationResult,
    receipt_path: Path | None = None,
    intake_timestamp: str | None = None,
) -> IntakeReceipt:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = receipt_path or receipt_path_for(result)
    errors = "\n".join(f"- {item}" for item in result.errors) or "- none"
    warnings = "\n".join(f"- {item}" for item in result.warnings) or "- none"
    risk_flags = "\n".join(f"- {item}" for item in result.risk_flags) or "- none"
    timestamp = intake_timestamp or datetime.now(timezone.utc).isoformat()
    text = f"""# Remote Worker Result Intake Receipt

## Intake

- intake timestamp: `{timestamp}`
- source path: `{result.source_path}`
- source SHA-256: `{result.source_hash or "(unavailable)"}`
- validation status: `{result.validation_status}`
- final decision: **{FINAL_DECISION_TEXT}**

## Result Metadata

- packet ID: `{result.packet_id or "(none)"}`
- worker device: `{result.worker_device or "(none)"}`
- result type: `{result.result_type or "(none)"}`
- review target: `{result.review_target or "(none)"}`
- trust level: `{result.trust_level or "(none)"}`
- requires_review: `{result.requires_review}`
- safe_to_auto_apply: `{result.safe_to_auto_apply}`

## Validation Errors

{errors}

## Safety Warnings

{warnings}

## Risk Flags

{risk_flags}

## Draft Text Preview

```text
{result.draft_text_preview}
```

## Suggested Next Step Preview

```text
{result.suggested_next_step_preview}
```

## Boundary

This receipt does not promote, execute, or trust Remote Worker output.

Remote Worker result intake is manual, untrusted, review-only, and never auto-applies output.
"""
    path.write_text(text, encoding="utf-8")
    return IntakeReceipt(str(path), result, FINAL_DECISION_TEXT)


def intake_result_file(
    path: Path,
    receipt_path: Path | None = None,
    intake_timestamp: str | None = None,
) -> IntakeReceipt:
    result = validate_result_file(path)
    return write_receipt(result, receipt_path, intake_timestamp=intake_timestamp)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Manual PC-side intake for untrusted Remote Worker result JSON.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    sub.add_parser("list")
    validate_parser = sub.add_parser("validate")
    validate_parser.add_argument("path")
    intake_parser = sub.add_parser("intake")
    intake_parser.add_argument("path")
    ingest_parser = sub.add_parser("ingest")
    ingest_parser.add_argument("path")
    args = parser.parse_args(argv)

    if args.command == "status":
        print(render_status())
        return 0
    if args.command == "list":
        print(render_list())
        return 0
    if args.command == "validate":
        result = validate_result_file(Path(args.path))
        print(render_validation(result))
        return 0 if result.valid_for_review else 1
    if args.command in {"intake", "ingest"}:
        receipt = intake_result_file(Path(args.path))
        print(render_validation(receipt.validation))
        print(f"receipt: {receipt.receipt_path}")
        return 0 if receipt.validation.valid_for_review else 1
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
