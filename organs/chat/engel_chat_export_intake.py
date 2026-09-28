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
INTAKE_ROOT = PROJECT_ROOT / "library_intake" / "chat_exports"
INCOMING_DIR = INTAKE_ROOT / "incoming"
REVIEWED_DIR = INTAKE_ROOT / "reviewed"
INVALID_DIR = INTAKE_ROOT / "invalid"
EXAMPLES_DIR = INTAKE_ROOT / "examples"
REPORTS_DIR = PROJECT_ROOT / "reports" / "chat_export_intake"
MEMORY_CANDIDATE_PROPOSAL_ROOT = PROJECT_ROOT / "reports" / "memory_candidate_proposals"

ALLOWED_EXTENSIONS = {".md", ".txt"}
MAX_CHAT_EXPORT_BYTES = 2 * 1024 * 1024
SUMMARY_PREVIEW_CHARS = 1800
CONTENT_PREVIEW_CHARS = 900
FINAL_DECISION = "UNTRUSTED REVIEW ONLY — NOT APPLIED"

RISK_PATTERNS = {
    "powershell": r"\bpowershell\b",
    "cmd_exe": r"\bcmd\.exe\b",
    "bash": r"\bbash\b",
    "wsl": r"\bwsl\b",
    "curl": r"\bcurl\b",
    "invoke_webrequest": r"\binvoke-webrequest\b",
    "execute": r"\bexecute\b",
    "apply_patch": r"\bapply patch\b|\bapply patches\b",
    "write_memory": r"\bwrite memory\b",
    "trusted_memory": r"\btrusted memory\b",
    "mutate_route": r"\bmutate route\b|\broute mutation\b",
    "mutate_queue": r"\bmutate queue\b|\bqueue mutation\b",
    "source_mutation": r"\bsource mutation\b|\bmutate source\b",
    "ignore_previous_instructions": r"\bignore previous instructions\b",
    "bypass": r"\bbypass\b",
}

TOPIC_PATTERNS = {
    "Flutter SDK setup": [
        "flutter sdk",
        "flutter --version",
        "flutter doctor",
        "dart",
    ],
    "Android SDK cmdline-tools and license fix": [
        "cmdline-tools",
        "sdkmanager",
        "android licenses",
        "android-licenses",
    ],
    "WSL/Ubuntu removal and disabled state": [
        "wsl",
        "ubuntu",
        "removed and disabled",
        "disabled state",
    ],
    "Engel Remote Worker Android scaffold": [
        "remote worker android",
        "android scaffold",
        "engel remote worker",
    ],
    "Flutter Windows desktop support": [
        "windows desktop support",
        "flutter build windows",
        "engel_remote_worker.exe",
    ],
    "Remote Worker Phase 2 GUI and manual packet import/export": [
        "phase 2",
        "manual packet import",
        "packet import/export",
        "draft result json",
    ],
    "Remote Worker Phase 3 PC-side manual result intake planning": [
        "phase 3",
        "pc-side manual result intake",
        "remote worker result intake",
    ],
    "Outside-AI / Hermes remains rejected / do not install boundary": [
        "outside-ai",
        "her" + "mes",
        "do not install",
        "rejected",
    ],
    "Engel safety boundaries for remote workers": [
        "safety boundaries",
        "remote worker",
        "no direct control",
        "engel controls",
    ],
    "Manual review-only worker output": [
        "review-only",
        "requires_review",
        "safe_to_auto_apply",
        "untrusted",
    ],
    "Engel library/memory intake from chat exports": [
        "chat export",
        "library building",
        "memory-candidate",
        "memory candidate",
    ],
}

LIBRARY_CATEGORY_RULES = {
    "Remote Worker architecture": ["remote worker", "android", "flutter"],
    "Engel safety boundary history": ["safety", "outside-ai", "her" + "mes", "wsl"],
    "Build and toolchain history": ["flutter", "android sdk", "cmdline-tools", "windows desktop"],
    "Manual intake and review workflows": ["intake", "review-only", "memory candidate", "library"],
}


@dataclass
class ChatExportValidation:
    source_path: str
    source_hash: str | None
    file_size: int | None
    valid_for_intake: bool
    validation_status: str
    errors: list[str]
    warnings: list[str]
    risk_flags: list[str]
    detected_topics: list[str]
    recommended_memory_candidate_topics: list[str]
    recommended_library_categories: list[str]
    bounded_summary: str
    content_preview: str


@dataclass
class ChatExportIntakeReceipt:
    receipt_path: str
    validation: ChatExportValidation
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


def bounded_text(text: str, limit: int) -> str:
    clean = text.replace("\r\n", "\n").strip()
    if len(clean) <= limit:
        return clean
    return clean[:limit] + "\n[preview truncated]"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_chat_export(path: Path) -> tuple[str | None, int | None, str | None, list[str]]:
    errors: list[str] = []
    if not path.exists() or not path.is_file():
        return None, None, None, ["source file does not exist"]
    if path.suffix.lower() not in ALLOWED_EXTENSIONS:
        errors.append("unsupported extension; Phase 1 accepts .txt and .md only")
    if not is_within_project(path):
        errors.append("source file must be inside the Engel App project root")
    try:
        size = path.stat().st_size
    except OSError as exc:
        return None, None, None, [f"could not stat source file: {exc}"]
    if size > MAX_CHAT_EXPORT_BYTES:
        errors.append(f"source file exceeds max chat export size of {MAX_CHAT_EXPORT_BYTES} bytes")
    if errors:
        return None, size, None, errors
    try:
        raw = path.read_bytes()
    except OSError as exc:
        return None, size, None, [f"could not read source file: {exc}"]
    if b"\x00" in raw[:4096]:
        return None, size, None, ["binary-looking file rejected"]
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("utf-8", errors="replace")
    return text, size, sha256_file(path), []


def risk_flags_for_text(text: str) -> list[str]:
    flags = []
    for flag, pattern in RISK_PATTERNS.items():
        if re.search(pattern, text, re.IGNORECASE):
            flags.append(flag)
    return sorted(set(flags))


def detect_topics(text: str) -> list[str]:
    lowered = text.lower()
    topics: list[str] = []
    for topic, needles in TOPIC_PATTERNS.items():
        if any(needle in lowered for needle in needles):
            topics.append(topic)
    return topics


def recommended_library_categories(text: str, topics: list[str]) -> list[str]:
    lowered = (text + "\n" + "\n".join(topics)).lower()
    categories: list[str] = []
    for category, needles in LIBRARY_CATEGORY_RULES.items():
        if any(needle in lowered for needle in needles):
            categories.append(category)
    return categories


def extractive_summary(text: str, topics: list[str]) -> str:
    lines = [line.strip() for line in text.replace("\r\n", "\n").splitlines()]
    useful: list[str] = []
    for line in lines:
        if not line:
            continue
        if line.startswith("#") or line.startswith("-") or line.startswith("*"):
            useful.append(line[:240])
        elif any(needle in line.lower() for needle in ["flutter", "android", "remote worker", "engel", "her" + "mes", "wsl", "intake", "review"]):
            useful.append(line[:240])
        if len(useful) >= 10:
            break
    if not useful:
        useful = [line[:240] for line in lines if line][:8]
    topic_line = "Detected topics: " + (", ".join(topics) if topics else "none detected")
    preview = "\n".join(["Extractive bounded summary.", topic_line, *useful])
    return bounded_text(preview, SUMMARY_PREVIEW_CHARS)


def memory_candidate_topics(topics: list[str]) -> list[str]:
    if not topics:
        return ["Review chat export for possible Engel project history memory candidates"]
    return [f"Review and possibly preserve project history: {topic}" for topic in topics[:8]]


def validate_chat_export(path: Path) -> ChatExportValidation:
    text, size, digest, read_errors = read_chat_export(path)
    if text is None:
        return ChatExportValidation(
            source_path=project_relative(path),
            source_hash=digest,
            file_size=size,
            valid_for_intake=False,
            validation_status="invalid",
            errors=read_errors,
            warnings=[],
            risk_flags=[],
            detected_topics=[],
            recommended_memory_candidate_topics=[],
            recommended_library_categories=[],
            bounded_summary="",
            content_preview="",
        )
    topics = detect_topics(text)
    risks = risk_flags_for_text(text)
    warnings = []
    if risks:
        warnings.append("risky command-like or trust-related text found; content remains inert source material")
    if not topics:
        warnings.append("no known Engel project topics detected")
    return ChatExportValidation(
        source_path=project_relative(path),
        source_hash=digest,
        file_size=size,
        valid_for_intake=True,
        validation_status="valid_for_untrusted_review",
        errors=[],
        warnings=warnings,
        risk_flags=risks,
        detected_topics=topics,
        recommended_memory_candidate_topics=memory_candidate_topics(topics),
        recommended_library_categories=recommended_library_categories(text, topics),
        bounded_summary=extractive_summary(text, topics),
        content_preview=bounded_text(text, CONTENT_PREVIEW_CHARS),
    )


def incoming_chat_exports() -> list[Path]:
    if not INCOMING_DIR.exists():
        return []
    try:
        return sorted(
            [path for path in INCOMING_DIR.iterdir() if path.is_file() and path.suffix.lower() in ALLOWED_EXTENSIONS],
            key=lambda item: item.name.lower(),
        )
    except OSError:
        return []


def latest_report() -> Path | None:
    if not REPORTS_DIR.exists():
        return None
    reports = sorted(REPORTS_DIR.glob("CHAT_EXPORT_INTAKE_*.md"), key=lambda item: item.stat().st_mtime)
    return reports[-1] if reports else None


def render_status() -> str:
    files = incoming_chat_exports()
    valid = 0
    invalid = 0
    for path in files:
        result = validate_chat_export(path)
        if result.valid_for_intake:
            valid += 1
        else:
            invalid += 1
    latest = latest_report()
    return "\n".join(
        [
            "Engel Chat Export Intake V1",
            "Mode: manual / local / untrusted source material / review-only",
            f"Incoming folder: {project_relative(INCOMING_DIR)}",
            f"Reviewed folder: {project_relative(REVIEWED_DIR)}",
            f"Invalid folder: {project_relative(INVALID_DIR)}",
            f"Reports folder: {project_relative(REPORTS_DIR)}",
            f"Memory proposal root: {project_relative(MEMORY_CANDIDATE_PROPOSAL_ROOT)}",
            f"incoming chat export files: {len(files)}",
            f"valid-looking chat exports: {valid}",
            f"invalid-looking chat exports: {invalid}",
            f"latest report: {project_relative(latest) if latest else '(none)'}",
            "No watcher, no auto-import, no execution, no trusted-memory write, no source/route/queue mutation.",
        ]
    )


def render_list() -> str:
    files = incoming_chat_exports()
    if not files:
        return "No incoming chat export .md or .txt files found."
    lines = ["Incoming chat export files:"]
    for path in files:
        result = validate_chat_export(path)
        topics = ", ".join(result.detected_topics[:3]) if result.detected_topics else "no known topic"
        lines.append(f"- {project_relative(path)} | {result.validation_status} | topics={topics}")
    return "\n".join(lines)


def render_validation(result: ChatExportValidation) -> str:
    topic_lines = [f"- {topic}" for topic in result.detected_topics] if result.detected_topics else ["- none"]
    lines = [
        "Chat export validation",
        f"source: {result.source_path}",
        f"status: {result.validation_status}",
        f"valid_for_intake: {result.valid_for_intake}",
        f"file_size: {result.file_size}",
        "detected_topics:",
        *topic_lines,
    ]
    if result.errors:
        lines.append("errors:")
        lines.extend(f"- {error}" for error in result.errors)
    if result.warnings:
        lines.append("warnings:")
        lines.extend(f"- {warning}" for warning in result.warnings)
    if result.risk_flags:
        lines.append("risk_flags:")
        lines.extend(f"- {flag}" for flag in result.risk_flags)
    lines.append(FINAL_DECISION)
    return "\n".join(lines)


def safe_source_stem(path_text: str) -> str:
    stem = Path(path_text).stem or "chat_export"
    clean = re.sub(r"[^A-Za-z0-9_.-]+", "_", stem)
    return clean[:80] or "chat_export"


def receipt_path_for(result: ChatExportValidation, timestamp: str | None = None) -> Path:
    stamp = timestamp or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return REPORTS_DIR / f"CHAT_EXPORT_INTAKE_{stamp}_{safe_source_stem(result.source_path)}.md"


def write_intake_receipt(
    result: ChatExportValidation,
    receipt_path: Path | None = None,
    intake_timestamp: str | None = None,
) -> ChatExportIntakeReceipt:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = receipt_path or receipt_path_for(result)
    timestamp = intake_timestamp or datetime.now(timezone.utc).isoformat()
    topics = "\n".join(f"- {topic}" for topic in result.detected_topics) or "- none"
    memory_topics = "\n".join(f"- {topic}" for topic in result.recommended_memory_candidate_topics) or "- none"
    categories = "\n".join(f"- {category}" for category in result.recommended_library_categories) or "- none"
    risks = "\n".join(f"- {risk}" for risk in result.risk_flags) or "- none"
    warnings = "\n".join(f"- {warning}" for warning in result.warnings) or "- none"
    errors = "\n".join(f"- {error}" for error in result.errors) or "- none"
    text = f"""# Chat Export Intake Receipt

## Intake

- intake timestamp: `{timestamp}`
- source path: `{result.source_path}`
- SHA-256: `{result.source_hash or "(unavailable)"}`
- file size: `{result.file_size}`
- validation status: `{result.validation_status}`
- final decision: **{FINAL_DECISION}**

## Detected Project / Topic Keywords

{topics}

## Bounded Summary

```text
{result.bounded_summary}
```

## Risk Flags

{risks}

## Warnings

{warnings}

## Errors

{errors}

## Recommended Memory-Candidate Topics

{memory_topics}

These are untrusted suggestions only. They are not trusted memory and are not approved for promotion.

## Recommended Library Categories

{categories}

These are library-index candidate categories only. They are pending human review and approval.

## Content Preview

```text
{result.content_preview}
```

## Boundary

This receipt does not execute, apply, promote, route, queue, trust, or write trusted memory from chat content.

Imported ChatGPT or outside-AI chat content is untrusted source material only.
"""
    path.write_text(text, encoding="utf-8")
    return ChatExportIntakeReceipt(str(path), result, FINAL_DECISION)


def intake_chat_export(
    path: Path,
    receipt_path: Path | None = None,
    intake_timestamp: str | None = None,
) -> ChatExportIntakeReceipt:
    result = validate_chat_export(path)
    return write_intake_receipt(result, receipt_path=receipt_path, intake_timestamp=intake_timestamp)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Manual intake for untrusted ChatGPT/chat export source material.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    sub.add_parser("list")
    validate_parser = sub.add_parser("validate")
    validate_parser.add_argument("path")
    intake_parser = sub.add_parser("intake")
    intake_parser.add_argument("path")
    args = parser.parse_args(argv)

    if args.command == "status":
        print(render_status())
        return 0
    if args.command == "list":
        print(render_list())
        return 0
    if args.command == "validate":
        result = validate_chat_export(Path(args.path))
        print(render_validation(result))
        return 0 if result.valid_for_intake else 1
    if args.command == "intake":
        receipt = intake_chat_export(Path(args.path))
        print(render_validation(receipt.validation))
        print(f"receipt: {receipt.receipt_path}")
        return 0 if receipt.validation.valid_for_intake else 1
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
