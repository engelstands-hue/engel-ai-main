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
OUTPUT_DIR = PROJECT_ROOT / "reports" / "memory_candidates"
PROPOSAL_VERSION = "ENGEL_RESEARCH_MEMORY_CANDIDATE_PROPOSAL_V1"

PROPOSAL_STATUS = [
    "MEMORY_CANDIDATE_PROPOSAL_ONLY",
    "FROM_LESSON_CANDIDATE",
    "HUMAN_APPROVAL_REQUIRED",
    "NOT_TRUSTED_MEMORY",
    "NO_TRUSTED_MEMORY_WRITE",
    "NO_SOURCE_MUTATION",
    "NO_PATCH_APPLY",
    "NO_VERIFIER_UPDATE",
    "NO_SELF_FIX_POLICY_UPDATE",
    "NO_EXECUTION",
    "NO_TRAINING",
    "NO_INDEXING",
    "NO_EMBEDDING",
    "NO_PROVIDER_CALLS",
    "NO_NETWORK",
    "NO_BROWSER",
    "NO_BACKGROUND_WORKER",
]

PROPOSAL_LABELS = [
    "MEMORY_CANDIDATE_PROPOSAL_ONLY",
    "FROM_LESSON_CANDIDATE",
    "HUMAN_APPROVAL_REQUIRED",
    "NOT_TRUSTED_MEMORY",
    "NO_TRUSTED_MEMORY_WRITE",
    "NO_AUTOMATION_TRIGGERED",
]

PROPOSAL_FIELDS = [
    "memory_candidate_proposal_id",
    "source_lesson_candidate_id",
    "source_research_note_id",
    "topic_id",
    "topic_title",
    "proposed_at",
    "trust_status",
    "proposed_memory_summary",
    "reason_to_remember",
    "evidence_chain",
    "source_references",
    "safety_notes",
    "uncertainty_notes",
    "prompt_injection_review_needed",
    "authority_review_needed",
    "suggested_core_continuity_linkage",
    "required_human_approval",
    "required_verifier_compatibility",
    "not_trusted_memory",
    "no_trusted_memory_write",
    "no_source_mutation",
]

LESSON_FIELDS = [
    "lesson_candidate_id",
    "source_research_note_id",
    "source_note_path",
    "topic_id",
    "topic_title",
    "candidate_summary",
    "candidate_details",
    "confidence",
    "evidence_from_note",
    "uncertainty_notes",
    "safety_notes",
    "possible_verifier_relevance",
    "possible_self_fix_relevance",
    "memory_candidate_possible",
]

LESSON_HEADING_TO_FIELD = {field.replace("_", " ").title(): field for field in LESSON_FIELDS}

BOUNDARY_TEXT = [
    "Memory candidate proposals are not trusted memory.",
    "This tool does not update memory files, Core Continuity, source code, verifiers, or self-fix policy.",
    "Human approval and verifier/guard compatibility are required before anything can become memory.",
]


class MemoryCandidateProposalError(ValueError):
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
        raise MemoryCandidateProposalError("URLs are not accepted.")
    if file_name.startswith("\\\\"):
        raise MemoryCandidateProposalError("UNC paths are not accepted.")
    if any(marker in file_name for marker in ("*", "?", "[")):
        raise MemoryCandidateProposalError("Wildcard report names are not accepted.")
    if any(separator in file_name for separator in ("\\", "/")):
        raise MemoryCandidateProposalError("Only a report file name is accepted, not a path.")
    if ".." in file_name or ":" in file_name:
        raise MemoryCandidateProposalError("Path traversal and drive names are not accepted.")
    if not re.fullmatch(r"[A-Za-z0-9._-]+\.md", file_name):
        raise MemoryCandidateProposalError("Report names must be safe .md file names.")


def resolve_lesson_path(lesson_file_name: str) -> Path:
    reject_unsafe_report_name(lesson_file_name)
    lesson_dir = LESSON_DIR.resolve()
    candidate = (lesson_dir / lesson_file_name).resolve()
    if not is_relative_to(candidate, lesson_dir):
        raise MemoryCandidateProposalError("Lesson candidate path escaped reports\\lesson_candidates.")
    if not candidate.exists() or not candidate.is_file():
        raise MemoryCandidateProposalError("Lesson candidate does not exist in reports\\lesson_candidates.")
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
            current = LESSON_HEADING_TO_FIELD.get(line[3:].strip())
            buffer = []
            continue
        if current is not None:
            buffer.append(line)
    flush()
    return sections


def make_proposal_id(lesson_id: str, summary: str, timestamp: str) -> str:
    seed = f"{lesson_id}|{summary}|{timestamp}|{PROPOSAL_VERSION}".encode("utf-8")
    return "memory_candidate_proposal_" + hashlib.sha256(seed).hexdigest()[:16]


def read_lesson(lesson_file_name: str) -> tuple[Path, dict[str, str]]:
    lesson_path = resolve_lesson_path(lesson_file_name)
    text = lesson_path.read_text(encoding="utf-8", errors="replace")
    return lesson_path, parse_markdown_sections(text)


def build_memory_candidate_proposal(lesson_file_name: str) -> dict[str, str]:
    lesson_path, lesson = read_lesson(lesson_file_name)
    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    summary = lesson.get("memory_candidate_possible") or lesson.get("candidate_summary") or "Possible memory candidate requires human review."
    lesson_id = lesson.get("lesson_candidate_id", "unknown_lesson_candidate")
    proposal_id = make_proposal_id(lesson_id, summary, timestamp)
    source_note_id = lesson.get("source_research_note_id", "unknown_research_note")
    source_note_path = lesson.get("source_note_path", "unknown_source_note_path")
    source_lesson_path = str(lesson_path.relative_to(PROJECT_ROOT)).replace("/", "\\")
    return {
        "memory_candidate_proposal_id": proposal_id,
        "source_lesson_candidate_id": lesson_id,
        "source_research_note_id": source_note_id,
        "topic_id": lesson.get("topic_id", "unknown_topic"),
        "topic_title": lesson.get("topic_title", "unknown_topic_title"),
        "proposed_at": timestamp,
        "trust_status": "MEMORY_CANDIDATE_PROPOSAL_ONLY / FROM_LESSON_CANDIDATE / HUMAN_APPROVAL_REQUIRED / NOT_TRUSTED_MEMORY",
        "proposed_memory_summary": summary,
        "reason_to_remember": "Only if a human decides this untrusted lesson candidate should become a reviewed memory candidate after guard/verifier compatibility review.",
        "evidence_chain": f"Research note: {source_note_id}; lesson candidate: {lesson_id}; no trusted memory write occurred.",
        "source_references": f"- {source_note_path}\n- {source_lesson_path}",
        "safety_notes": "This proposal is not trusted memory and does not update Core Continuity, source code, verifiers, or self-fix policy.",
        "uncertainty_notes": lesson.get("uncertainty_notes", "Requires human review before use."),
        "prompt_injection_review_needed": "true",
        "authority_review_needed": "true",
        "suggested_core_continuity_linkage": "Suggestion only: link to Engel Self-Research Contract V1 and the Research Note to Memory Candidate chain after approval.",
        "required_human_approval": "true",
        "required_verifier_compatibility": "true",
        "not_trusted_memory": "true",
        "no_trusted_memory_write": "true",
        "no_source_mutation": "true",
    }


def render_proposal(proposal: dict[str, str]) -> str:
    lines = [
        "# Engel Research Memory Candidate Proposal V1",
        "",
        "Labels:",
        *[f"- {label}" for label in PROPOSAL_LABELS],
        "",
        "Proposal status:",
        *[f"- {status}" for status in PROPOSAL_STATUS],
        "",
        "Boundary:",
        *[f"- {item}" for item in BOUNDARY_TEXT],
        "",
    ]
    for field in PROPOSAL_FIELDS:
        lines.extend([f"## {field.replace('_', ' ').title()}", str(proposal.get(field, "")), ""])
    return "\n".join(lines).rstrip() + "\n"


def safe_output_filename(proposal: dict[str, str]) -> str:
    topic = re.sub(r"[^A-Za-z0-9_-]+", "_", proposal.get("topic_id", "unknown_topic")).strip("_").lower()
    proposal_id = re.sub(r"[^A-Za-z0-9_-]+", "_", proposal["memory_candidate_proposal_id"]).strip("_").lower()
    return f"{proposal_id}_{topic}.md"


def write_proposal(proposal: dict[str, str]) -> Path:
    output_dir = OUTPUT_DIR.resolve()
    root = PROJECT_ROOT.resolve()
    if not is_relative_to(output_dir, root):
        raise MemoryCandidateProposalError("Memory candidate proposal output folder escaped the project root.")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = (output_dir / safe_output_filename(proposal)).resolve()
    if not is_relative_to(output_path, output_dir):
        raise MemoryCandidateProposalError("Memory candidate proposal output path escaped reports\\memory_candidates.")
    output_path.write_text(render_proposal(proposal), encoding="utf-8")
    return output_path


def usage_text() -> str:
    return textwrap.dedent(
        """\
        Engel Research Memory Candidate Proposal V1

        Status:
        MEMORY_CANDIDATE_PROPOSAL_ONLY / FROM_LESSON_CANDIDATE / HUMAN_APPROVAL_REQUIRED / NOT_TRUSTED_MEMORY

        Usage:
          python engel_research_memory_candidate_proposal.py --lesson <lesson-file-name> --dry-run
          python engel_research_memory_candidate_proposal.py --lesson <lesson-file-name> --write

        Boundary:
          Reads one explicit lesson candidate from reports\\lesson_candidates and writes only proposals
          to reports\\memory_candidates when --write is supplied. It does not write trusted memory,
          update memory files, update Core Continuity, mutate source, update verifiers, update self-fix
          policy, execute, train, index, embed, call providers, use network, open browser, or start
          background workers.
        """
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=True, description="Create an unapproved memory candidate proposal from one lesson candidate.")
    parser.add_argument("--lesson", metavar="LESSON_FILE_NAME", help="Lesson candidate file name from reports\\lesson_candidates.")
    parser.add_argument("--dry-run", action="store_true", help="Print the proposal without writing.")
    parser.add_argument("--write", action="store_true", help="Write the proposal to reports\\memory_candidates.")
    return parser


def main(argv: list[str] | None = None, stdout=None, stderr=None) -> int:
    out = stdout if stdout is not None else sys.stdout
    err = stderr if stderr is not None else sys.stderr
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.lesson or (not args.dry_run and not args.write):
        out.write(usage_text())
        return 0
    if args.dry_run and args.write:
        err.write("Choose either --dry-run or --write, not both.\n")
        return 2
    try:
        proposal = build_memory_candidate_proposal(args.lesson)
        rendered = render_proposal(proposal)
        if args.dry_run:
            out.write(rendered)
            return 0
        output_path = write_proposal(proposal)
        out.write(f"WROTE_MEMORY_CANDIDATE_PROPOSAL {output_path.relative_to(PROJECT_ROOT)}\n")
        return 0
    except MemoryCandidateProposalError as exc:
        err.write(f"[REJECTED] {exc}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
