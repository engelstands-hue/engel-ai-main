from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import re
import sys
import textwrap


PROJECT_ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
NOTE_DIR = PROJECT_ROOT / "reports" / "self_research_notes"
OUTPUT_DIR = PROJECT_ROOT / "reports" / "lesson_candidates"
EXTRACTOR_VERSION = "ENGEL_LESSON_CANDIDATE_EXTRACTOR_V1"

EXTRACTOR_STATUS = [
    "LESSON_CANDIDATE_ONLY",
    "FROM_UNTRUSTED_RESEARCH_NOTE",
    "NOT_TRUSTED_MEMORY",
    "NOT_APPROVED_LESSON",
    "NO_VERIFIER_UPDATE",
    "NO_SELF_FIX_POLICY_UPDATE",
    "NO_SOURCE_MUTATION",
    "NO_PATCH_APPLY",
    "NO_EXECUTION",
    "NO_TRAINING",
    "NO_INDEXING",
    "NO_EMBEDDING",
    "NO_PROVIDER_CALLS",
    "NO_NETWORK",
    "NO_BROWSER",
    "NO_BACKGROUND_WORKER",
]

CANDIDATE_LABELS = [
    "LESSON_CANDIDATE_ONLY",
    "FROM_UNTRUSTED_RESEARCH_NOTE",
    "NOT_TRUSTED_MEMORY",
    "NOT_APPROVED_LESSON",
    "HUMAN_REVIEW_REQUIRED",
    "NO_AUTOMATION_TRIGGERED",
]

CANDIDATE_FIELDS = [
    "lesson_candidate_id",
    "source_research_note_id",
    "source_note_path",
    "topic_id",
    "topic_title",
    "extracted_at",
    "trust_status",
    "candidate_summary",
    "candidate_details",
    "confidence",
    "evidence_from_note",
    "uncertainty_notes",
    "safety_notes",
    "possible_verifier_relevance",
    "possible_self_fix_relevance",
    "memory_candidate_possible",
    "required_review_before_use",
    "not_trusted_memory",
    "no_source_mutation",
    "no_verifier_update",
    "no_self_fix_policy_update",
]

NOTE_FIELDS = [
    "research_note_id",
    "topic_id",
    "topic_title",
    "topic_category",
    "source_paths_or_references",
    "research_question",
    "short_summary",
    "key_observations",
    "uncertainty_notes",
    "source_risk_notes",
    "prompt_injection_risk_notes",
    "possible_lesson_candidates",
    "possible_verifier_improvement_candidates",
    "possible_self_fix_improvement_candidates",
    "possible_memory_candidate_summary",
]

NOTE_HEADING_TO_FIELD = {field.replace("_", " ").title(): field for field in NOTE_FIELDS}

BOUNDARY_TEXT = [
    "Lesson candidates are not trusted memory.",
    "Lesson candidates are not approved lessons.",
    "Lesson candidates do not update verifiers.",
    "Lesson candidates do not update self-fix policy.",
    "Lesson candidates do not mutate source or apply patches.",
    "Human review is required before any use.",
]


class LessonCandidateError(ValueError):
    pass


def is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
    except ValueError:
        return False
    return True


def reject_unsafe_report_name(file_name: str) -> None:
    lowered = file_name.lower()
    if lowered.startswith(("http://", "https://")):
        raise LessonCandidateError("URLs are not accepted.")
    if file_name.startswith("\\\\"):
        raise LessonCandidateError("UNC paths are not accepted.")
    if any(marker in file_name for marker in ("*", "?", "[")):
        raise LessonCandidateError("Wildcard report names are not accepted.")
    if any(separator in file_name for separator in ("\\", "/")):
        raise LessonCandidateError("Only a report file name is accepted, not a path.")
    if ".." in file_name or ":" in file_name:
        raise LessonCandidateError("Path traversal and drive names are not accepted.")
    if not re.fullmatch(r"[A-Za-z0-9._-]+\.md", file_name):
        raise LessonCandidateError("Report names must be safe .md file names.")


def resolve_note_path(note_file_name: str) -> Path:
    reject_unsafe_report_name(note_file_name)
    note_dir = NOTE_DIR.resolve()
    candidate = (note_dir / note_file_name).resolve()
    if not is_relative_to(candidate, note_dir):
        raise LessonCandidateError("Research note path escaped reports\\self_research_notes.")
    if not candidate.exists() or not candidate.is_file():
        raise LessonCandidateError("Research note does not exist in reports\\self_research_notes.")
    return candidate


def parse_markdown_sections(text: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    current: str | None = None
    buffer: list[str] = []

    def flush() -> None:
        if current is not None:
            sections[current] = "\n".join(buffer).strip()

    for line in text.splitlines():
        if line.startswith("## "):
            flush()
            current = NOTE_HEADING_TO_FIELD.get(line[3:].strip())
            buffer = []
            continue
        if current is not None:
            buffer.append(line)
    flush()
    return sections


def split_candidates(raw: str) -> list[str]:
    candidates: list[str] = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("- "):
            stripped = stripped[2:].strip()
        if stripped:
            candidates.append(stripped)
    return candidates


def make_candidate_id(note_id: str, summary: str, timestamp: str) -> str:
    seed = f"{note_id}|{summary}|{timestamp}|{EXTRACTOR_VERSION}".encode("utf-8")
    return "lesson_candidate_" + hashlib.sha256(seed).hexdigest()[:16]


def read_note(note_file_name: str) -> tuple[Path, dict[str, str]]:
    note_path = resolve_note_path(note_file_name)
    text = note_path.read_text(encoding="utf-8", errors="replace")
    return note_path, parse_markdown_sections(text)


def build_lesson_candidate(note_file_name: str) -> dict[str, str]:
    note_path, note = read_note(note_file_name)
    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    possible_lessons = split_candidates(note.get("possible_lesson_candidates", ""))
    summary = possible_lessons[0] if possible_lessons else "Possible lesson candidate requires manual review before any use."
    details = "\n".join(f"- {item}" for item in possible_lessons) if possible_lessons else "- No explicit lesson candidate was present; this placeholder remains unapproved."
    evidence = note.get("key_observations", "No trusted evidence; source note remains untrusted.")
    candidate_id = make_candidate_id(note.get("research_note_id", "unknown_note"), summary, timestamp)
    return {
        "lesson_candidate_id": candidate_id,
        "source_research_note_id": note.get("research_note_id", "unknown_note"),
        "source_note_path": str(note_path.relative_to(PROJECT_ROOT)).replace("/", "\\"),
        "topic_id": note.get("topic_id", "unknown_topic"),
        "topic_title": note.get("topic_title", "unknown_topic_title"),
        "extracted_at": timestamp,
        "trust_status": "LESSON_CANDIDATE_ONLY / FROM_UNTRUSTED_RESEARCH_NOTE / NOT_TRUSTED_MEMORY / NOT_APPROVED_LESSON",
        "candidate_summary": summary,
        "candidate_details": details,
        "confidence": "low_to_medium; derived only from a bounded untrusted research note",
        "evidence_from_note": evidence,
        "uncertainty_notes": note.get("uncertainty_notes", "Requires human review before use."),
        "safety_notes": "No automation was triggered. This is not trusted memory, not an approved lesson, not a verifier update, and not a self-fix policy update.",
        "possible_verifier_relevance": note.get("possible_verifier_improvement_candidates", "Requires review before verifier relevance can be trusted."),
        "possible_self_fix_relevance": note.get("possible_self_fix_improvement_candidates", "Requires review before self-fix relevance can be trusted."),
        "memory_candidate_possible": note.get("possible_memory_candidate_summary", "Only possible after separate memory candidate proposal and human approval."),
        "required_review_before_use": "Human review, guard compatibility, and verifier compatibility are required before use.",
        "not_trusted_memory": "true",
        "no_source_mutation": "true",
        "no_verifier_update": "true",
        "no_self_fix_policy_update": "true",
    }


def render_candidate(candidate: dict[str, str]) -> str:
    lines = [
        "# Engel Lesson Candidate V1",
        "",
        "Labels:",
        *[f"- {label}" for label in CANDIDATE_LABELS],
        "",
        "Extractor status:",
        *[f"- {status}" for status in EXTRACTOR_STATUS],
        "",
        "Boundary:",
        *[f"- {item}" for item in BOUNDARY_TEXT],
        "",
    ]
    for field in CANDIDATE_FIELDS:
        lines.extend([f"## {field.replace('_', ' ').title()}", str(candidate.get(field, "")), ""])
    return "\n".join(lines).rstrip() + "\n"


def safe_output_filename(candidate: dict[str, str]) -> str:
    topic = re.sub(r"[^A-Za-z0-9_-]+", "_", candidate.get("topic_id", "unknown_topic")).strip("_").lower()
    candidate_id = re.sub(r"[^A-Za-z0-9_-]+", "_", candidate["lesson_candidate_id"]).strip("_").lower()
    return f"{candidate_id}_{topic}.md"


def write_candidate(candidate: dict[str, str]) -> Path:
    output_dir = OUTPUT_DIR.resolve()
    root = PROJECT_ROOT.resolve()
    if not is_relative_to(output_dir, root):
        raise LessonCandidateError("Lesson candidate output folder escaped the project root.")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = (output_dir / safe_output_filename(candidate)).resolve()
    if not is_relative_to(output_path, output_dir):
        raise LessonCandidateError("Lesson candidate output path escaped reports\\lesson_candidates.")
    output_path.write_text(render_candidate(candidate), encoding="utf-8")
    return output_path


def usage_text() -> str:
    return textwrap.dedent(
        """\
        Engel Lesson Candidate Extractor V1

        Status:
        LESSON_CANDIDATE_ONLY / FROM_UNTRUSTED_RESEARCH_NOTE / NOT_TRUSTED_MEMORY / NOT_APPROVED_LESSON

        Usage:
          python engel_lesson_candidate_extractor.py --note <note-file-name> --dry-run
          python engel_lesson_candidate_extractor.py --note <note-file-name> --write

        Boundary:
          Reads one explicit note from reports\\self_research_notes and writes only candidate reports to
          reports\\lesson_candidates when --write is supplied. It does not create trusted memory,
          update verifiers, update self-fix policy, mutate source, apply patches, execute, train,
          index, embed, call providers, use network, open browser, or start background workers.
        """
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=True, description="Extract untrusted lesson candidates from one Engel research note.")
    parser.add_argument("--note", metavar="NOTE_FILE_NAME", help="Research note file name from reports\\self_research_notes.")
    parser.add_argument("--dry-run", action="store_true", help="Print the lesson candidate without writing.")
    parser.add_argument("--write", action="store_true", help="Write the candidate to reports\\lesson_candidates.")
    return parser


def main(argv: list[str] | None = None, stdout=None, stderr=None) -> int:
    out = stdout if stdout is not None else sys.stdout
    err = stderr if stderr is not None else sys.stderr
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.note or (not args.dry_run and not args.write):
        out.write(usage_text())
        return 0
    if args.dry_run and args.write:
        err.write("Choose either --dry-run or --write, not both.\n")
        return 2
    try:
        candidate = build_lesson_candidate(args.note)
        rendered = render_candidate(candidate)
        if args.dry_run:
            out.write(rendered)
            return 0
        output_path = write_candidate(candidate)
        out.write(f"WROTE_LESSON_CANDIDATE {output_path.relative_to(PROJECT_ROOT)}\n")
        return 0
    except LessonCandidateError as exc:
        err.write(f"[REJECTED] {exc}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
