from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import re
import sys
import textwrap


PROJECT_ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
LESSON_DIR = PROJECT_ROOT / "reports" / "lesson_candidates"
MEMORY_PROPOSAL_DIR = PROJECT_ROOT / "reports" / "memory_candidates"
OUTPUT_DIR = PROJECT_ROOT / "reports" / "verifier_improvement_candidates"
TOOL_VERSION = "ENGEL_VERIFIER_IMPROVEMENT_CANDIDATE_V1"

TOOL_STATUS = [
    "VERIFIER_IMPROVEMENT_CANDIDATE_ONLY",
    "FROM_UNTRUSTED_LESSON_OR_MEMORY_PROPOSAL",
    "NO_VERIFIER_UPDATE",
    "NO_SOURCE_MUTATION",
    "NO_PATCH_APPLY",
    "NOT_TRUSTED_MEMORY",
    "HUMAN_REVIEW_REQUIRED",
    "NO_PROVIDER_CALLS",
    "NO_NETWORK",
    "NO_BROWSER",
    "NO_BACKGROUND_WORKER",
]

CANDIDATE_LABELS = [
    "VERIFIER_IMPROVEMENT_CANDIDATE_ONLY",
    "NO_VERIFIER_UPDATE",
    "NO_SOURCE_MUTATION",
    "HUMAN_REVIEW_REQUIRED",
    "NOT_TRUSTED_MEMORY",
    "NO_AUTOMATION_TRIGGERED",
]

CANDIDATE_FIELDS = [
    "verifier_improvement_candidate_id",
    "source_kind",
    "source_file_name",
    "source_path",
    "source_lesson_candidate_id",
    "source_memory_candidate_proposal_id",
    "topic_id",
    "topic_title",
    "created_at",
    "tool_version",
    "trust_status",
    "candidate_summary",
    "proposed_verifier_focus",
    "suggested_check_scope",
    "evidence_from_source",
    "uncertainty_notes",
    "safety_notes",
    "required_human_review",
    "not_trusted_memory",
    "no_verifier_update",
    "no_source_mutation",
    "no_patch_apply",
]

LESSON_FIELD_HEADINGS = {
    "Lesson Candidate Id": "lesson_candidate_id",
    "Source Research Note Id": "source_research_note_id",
    "Topic Id": "topic_id",
    "Topic Title": "topic_title",
    "Candidate Summary": "candidate_summary",
    "Candidate Details": "candidate_details",
    "Evidence From Note": "evidence_from_note",
    "Possible Verifier Relevance": "possible_verifier_relevance",
    "Safety Notes": "safety_notes",
    "Uncertainty Notes": "uncertainty_notes",
}

MEMORY_FIELD_HEADINGS = {
    "Memory Candidate Proposal Id": "memory_candidate_proposal_id",
    "Source Lesson Candidate Id": "source_lesson_candidate_id",
    "Source Research Note Id": "source_research_note_id",
    "Topic Id": "topic_id",
    "Topic Title": "topic_title",
    "Proposed Memory Summary": "proposed_memory_summary",
    "Reason To Remember": "reason_to_remember",
    "Evidence Chain": "evidence_chain",
    "Safety Notes": "safety_notes",
    "Uncertainty Notes": "uncertainty_notes",
}

BOUNDARY_TEXT = [
    "Verifier improvement candidates are not verifier updates.",
    "Verifier improvement candidates are not source patches.",
    "Verifier improvement candidates are not trusted memory.",
    "This tool does not modify tools\\verify_*.py.",
    "This tool does not mutate source, apply patches, execute code, call providers, use network, open browser, or start background workers.",
]


class VerifierImprovementCandidateError(ValueError):
    pass


def is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
    except ValueError:
        return False
    return True


def project_relative(path: Path) -> str:
    return str(path.relative_to(PROJECT_ROOT)).replace("/", "\\")


def reject_unsafe_report_name(file_name: str) -> None:
    lowered = file_name.lower()
    if lowered.startswith(("http://", "https://")):
        raise VerifierImprovementCandidateError("URLs are not accepted.")
    if file_name.startswith("\\\\"):
        raise VerifierImprovementCandidateError("UNC paths are not accepted.")
    if any(marker in file_name for marker in ("*", "?", "[")):
        raise VerifierImprovementCandidateError("Wildcard report names are not accepted.")
    if any(separator in file_name for separator in ("\\", "/")):
        raise VerifierImprovementCandidateError("Only a report file name is accepted, not a path.")
    if ".." in file_name or ":" in file_name:
        raise VerifierImprovementCandidateError("Path traversal and drive names are not accepted.")
    if not re.fullmatch(r"[A-Za-z0-9._-]+\.md", file_name):
        raise VerifierImprovementCandidateError("Report names must be safe .md file names.")


def resolve_bounded_input(folder: Path, file_name: str, label: str) -> Path:
    reject_unsafe_report_name(file_name)
    bounded_root = folder.resolve()
    candidate = (bounded_root / file_name).resolve()
    if not is_relative_to(candidate, bounded_root):
        raise VerifierImprovementCandidateError(label + " path escaped the bounded reports folder.")
    if not candidate.exists() or not candidate.is_file():
        raise VerifierImprovementCandidateError(label + " report does not exist in the bounded reports folder.")
    if candidate.name == ".gitkeep":
        raise VerifierImprovementCandidateError(label + " must be a candidate report, not .gitkeep.")
    return candidate


def parse_markdown_sections(text: str, heading_map: dict[str, str]) -> dict[str, str]:
    sections: dict[str, str] = {}
    current: str | None = None
    buffer: list[str] = []

    def flush() -> None:
        if current is not None:
            sections[current] = "\n".join(buffer).strip()

    for line in text.splitlines():
        if line.startswith("## "):
            flush()
            current = heading_map.get(line[3:].strip())
            buffer = []
            continue
        if current is not None:
            buffer.append(line)
    flush()
    return sections


def first_nonempty_line(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and not stripped.startswith("```"):
            return stripped[:240]
    return "No concise source summary was available; human review is required."


def make_candidate_id(source_kind: str, file_name: str, timestamp: str) -> str:
    seed = f"{source_kind}|{file_name}|{timestamp}|{TOOL_VERSION}".encode("utf-8")
    return "verifier_improvement_candidate_" + hashlib.sha256(seed).hexdigest()[:16]


def source_summary_for_lesson(sections: dict[str, str], raw_text: str) -> tuple[str, str, str]:
    summary = sections.get("possible_verifier_relevance") or sections.get("candidate_summary") or first_nonempty_line(raw_text)
    evidence = sections.get("evidence_from_note") or sections.get("candidate_details") or first_nonempty_line(raw_text)
    uncertainty = sections.get("uncertainty_notes") or "Source lesson candidate remains untrusted and may be incomplete."
    return summary, evidence, uncertainty


def source_summary_for_memory_proposal(sections: dict[str, str], raw_text: str) -> tuple[str, str, str]:
    summary = sections.get("proposed_memory_summary") or sections.get("reason_to_remember") or first_nonempty_line(raw_text)
    evidence = sections.get("evidence_chain") or sections.get("safety_notes") or first_nonempty_line(raw_text)
    uncertainty = sections.get("uncertainty_notes") or "Source memory candidate proposal remains untrusted and unapproved."
    return summary, evidence, uncertainty


def build_candidate_from_path(source_kind: str, file_name: str) -> dict[str, str]:
    if source_kind == "lesson":
        source_path = resolve_bounded_input(LESSON_DIR, file_name, "Lesson candidate")
        raw_text = source_path.read_text(encoding="utf-8", errors="replace")
        sections = parse_markdown_sections(raw_text, LESSON_FIELD_HEADINGS)
        summary, evidence, uncertainty = source_summary_for_lesson(sections, raw_text)
        source_lesson_id = sections.get("lesson_candidate_id", "unknown_lesson_candidate")
        source_memory_id = ""
    elif source_kind == "memory_proposal":
        source_path = resolve_bounded_input(MEMORY_PROPOSAL_DIR, file_name, "Memory candidate proposal")
        raw_text = source_path.read_text(encoding="utf-8", errors="replace")
        sections = parse_markdown_sections(raw_text, MEMORY_FIELD_HEADINGS)
        summary, evidence, uncertainty = source_summary_for_memory_proposal(sections, raw_text)
        source_lesson_id = sections.get("source_lesson_candidate_id", "unknown_lesson_candidate")
        source_memory_id = sections.get("memory_candidate_proposal_id", "unknown_memory_candidate_proposal")
    else:
        raise VerifierImprovementCandidateError("source_kind must be lesson or memory_proposal")

    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    return {
        "verifier_improvement_candidate_id": make_candidate_id(source_kind, file_name, timestamp),
        "source_kind": source_kind,
        "source_file_name": file_name,
        "source_path": project_relative(source_path),
        "source_lesson_candidate_id": source_lesson_id,
        "source_memory_candidate_proposal_id": source_memory_id,
        "topic_id": sections.get("topic_id", "unknown_topic"),
        "topic_title": sections.get("topic_title", "unknown_topic_title"),
        "created_at": timestamp,
        "tool_version": TOOL_VERSION,
        "trust_status": "VERIFIER_IMPROVEMENT_CANDIDATE_ONLY / FROM_UNTRUSTED_LESSON_OR_MEMORY_PROPOSAL / NOT_TRUSTED_MEMORY / HUMAN_REVIEW_REQUIRED",
        "candidate_summary": summary,
        "proposed_verifier_focus": "Possible verifier improvement candidate derived from an untrusted lesson or memory proposal. Human review must decide whether any verifier expectation is useful.",
        "suggested_check_scope": "Candidate-only suggestion; any real verifier update requires separate human approval, source review, and a dedicated implementation step.",
        "evidence_from_source": evidence,
        "uncertainty_notes": uncertainty,
        "safety_notes": "No verifier was updated. No source was mutated. No patch was applied. No trusted memory was written. No automation was triggered.",
        "required_human_review": "true",
        "not_trusted_memory": "true",
        "no_verifier_update": "true",
        "no_source_mutation": "true",
        "no_patch_apply": "true",
    }


def render_candidate(candidate: dict[str, str]) -> str:
    lines = [
        "# Engel Verifier Improvement Candidate V1",
        "",
        "Labels:",
        *[f"- {label}" for label in CANDIDATE_LABELS],
        "",
        "Candidate status:",
        *[f"- {status}" for status in TOOL_STATUS],
        "",
        "Boundary:",
        *[f"- {item}" for item in BOUNDARY_TEXT],
        "",
    ]
    for field in CANDIDATE_FIELDS:
        lines.extend([f"## {field.replace('_', ' ').title()}", str(candidate.get(field, "")), ""])
    return "\n".join(lines).rstrip() + "\n"


def safe_output_filename(candidate: dict[str, str]) -> str:
    source = re.sub(r"[^A-Za-z0-9_-]+", "_", candidate.get("source_file_name", "source")).strip("_").lower()
    candidate_id = re.sub(r"[^A-Za-z0-9_-]+", "_", candidate["verifier_improvement_candidate_id"]).strip("_").lower()
    return f"{candidate_id}_{source}.md"


def write_candidate(candidate: dict[str, str]) -> Path:
    output_dir = OUTPUT_DIR.resolve()
    root = PROJECT_ROOT.resolve()
    if not is_relative_to(output_dir, root):
        raise VerifierImprovementCandidateError("Verifier improvement candidate output folder escaped the project root.")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = (output_dir / safe_output_filename(candidate)).resolve()
    if not is_relative_to(output_path, output_dir):
        raise VerifierImprovementCandidateError("Verifier improvement candidate output path escaped reports\\verifier_improvement_candidates.")
    output_path.write_text(render_candidate(candidate), encoding="utf-8")
    return output_path


def usage_text() -> str:
    return textwrap.dedent(
        """\
        Engel Verifier Improvement Candidate V1

        Status:
        VERIFIER_IMPROVEMENT_CANDIDATE_ONLY / FROM_UNTRUSTED_LESSON_OR_MEMORY_PROPOSAL / NO_VERIFIER_UPDATE / NOT_TRUSTED_MEMORY

        Usage:
          python engel_verifier_improvement_candidate.py --lesson <lesson-file-name> --dry-run
          python engel_verifier_improvement_candidate.py --lesson <lesson-file-name> --write
          python engel_verifier_improvement_candidate.py --memory-proposal <proposal-file-name> --dry-run
          python engel_verifier_improvement_candidate.py --memory-proposal <proposal-file-name> --write

        Boundary:
          Reads one explicit lesson candidate from reports\\lesson_candidates or one explicit memory
          candidate proposal from reports\\memory_candidates. Writes only candidate reports to
          reports\\verifier_improvement_candidates when --write is supplied. It does not modify
          tools\\verify_*.py, mutate source, write trusted memory, apply patches, execute code,
          call providers, use network, open browser, or start background workers.
        """
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=True, description="Create untrusted verifier improvement candidate reports.")
    parser.add_argument("--lesson", metavar="LESSON_FILE_NAME", help="Read one lesson candidate from reports\\lesson_candidates.")
    parser.add_argument("--memory-proposal", metavar="PROPOSAL_FILE_NAME", help="Read one memory candidate proposal from reports\\memory_candidates.")
    parser.add_argument("--dry-run", action="store_true", help="Print the candidate only; do not write a file.")
    parser.add_argument("--write", action="store_true", help="Write the candidate only to reports\\verifier_improvement_candidates.")
    return parser


def main(argv: list[str] | None = None, stdout=None, stderr=None) -> int:
    out = stdout if stdout is not None else sys.stdout
    err = stderr if stderr is not None else sys.stderr
    parser = build_parser()
    args = parser.parse_args(argv)
    if not any([args.lesson, args.memory_proposal, args.dry_run, args.write]):
        out.write(usage_text())
        return 0
    if args.lesson and args.memory_proposal:
        err.write("Choose either --lesson or --memory-proposal, not both.\n")
        return 2
    if not args.lesson and not args.memory_proposal:
        err.write("Choose one explicit --lesson or --memory-proposal input.\n")
        return 2
    if args.dry_run and args.write:
        err.write("Choose either --dry-run or --write, not both.\n")
        return 2
    if not args.dry_run and not args.write:
        err.write("Choose --dry-run or explicit --write.\n")
        return 2
    try:
        if args.lesson:
            candidate = build_candidate_from_path("lesson", args.lesson)
        else:
            candidate = build_candidate_from_path("memory_proposal", args.memory_proposal)
        rendered = render_candidate(candidate)
        if args.write:
            path = write_candidate(candidate)
            out.write(f"WROTE_VERIFIER_IMPROVEMENT_CANDIDATE: {project_relative(path)}\n")
            out.write("NO_VERIFIER_UPDATE / NO_SOURCE_MUTATION / NOT_TRUSTED_MEMORY / NO_AUTOMATION_TRIGGERED\n")
        else:
            out.write(rendered)
        return 0
    except VerifierImprovementCandidateError as exc:
        err.write(f"[REJECTED] {exc}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
