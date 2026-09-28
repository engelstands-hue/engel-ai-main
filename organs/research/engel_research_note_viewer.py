from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys
import textwrap


PROJECT_ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
NOTE_DIR = PROJECT_ROOT / "reports" / "self_research_notes"

VIEWER_STATUS = [
    "READ_ONLY_VIEWER",
    "UNTRUSTED_RESEARCH_NOTE_VIEW_ONLY",
    "LOCAL_ONLY",
    "BOUNDED_REPORTS_ONLY",
    "NO_MEMORY_WRITE",
    "NO_PATCH_APPLY",
    "NO_SOURCE_MUTATION",
    "NO_EXECUTION",
    "NO_TRAINING",
    "NO_INDEXING",
    "NO_EMBEDDING",
    "NO_PROVIDER_CALLS",
    "NO_NETWORK",
    "NO_BROWSER",
    "NO_BACKGROUND_WORKER",
]

DISPLAY_FIELDS = [
    "research_note_id",
    "topic_id",
    "topic_title",
    "topic_category",
    "source_paths_or_references",
    "trust_status",
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
    "memory_boundary",
    "execution_boundary",
    "training_boundary",
    "next_safe_manual_step",
    "required_review_before_use",
    "no_trusted_memory_write",
]

BOUNDARY_TEXT = [
    "Research notes are displayed as untrusted local report artifacts only.",
    "The viewer does not edit notes, delete notes, write memory, apply patches, update verifiers, update self-fix policy, execute note content, index notes, embed notes, call providers, use network, open a browser, scan arbitrary folders, or start background workers.",
]

HEADING_TO_FIELD = {field.replace("_", " ").title(): field for field in DISPLAY_FIELDS}


class ResearchNoteViewerError(ValueError):
    pass


def is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
    except ValueError:
        return False
    return True


def reject_unsafe_note_name(note_file_name: str) -> None:
    lowered = note_file_name.lower()
    if lowered.startswith(("http://", "https://")):
        raise ResearchNoteViewerError("URLs are not accepted as research note names.")
    if note_file_name.startswith("\\\\"):
        raise ResearchNoteViewerError("UNC paths are not accepted as research note names.")
    if any(marker in note_file_name for marker in ("*", "?", "[")):
        raise ResearchNoteViewerError("Wildcard note names are not accepted.")
    if any(separator in note_file_name for separator in ("\\", "/")):
        raise ResearchNoteViewerError("Only a note file name is accepted, not a path.")
    if ".." in note_file_name or ":" in note_file_name:
        raise ResearchNoteViewerError("Path traversal and drive names are not accepted.")
    if not re.fullmatch(r"[A-Za-z0-9._-]+\.md", note_file_name):
        raise ResearchNoteViewerError("Research note names must be safe .md file names.")


def resolve_note_path(note_file_name: str) -> Path:
    reject_unsafe_note_name(note_file_name)
    note_dir = NOTE_DIR.resolve()
    candidate = (note_dir / note_file_name).resolve()
    if not is_relative_to(candidate, note_dir):
        raise ResearchNoteViewerError("Research note path escaped the bounded note folder.")
    if not candidate.exists() or not candidate.is_file():
        raise ResearchNoteViewerError("Research note does not exist in reports\\self_research_notes.")
    return candidate


def list_note_names() -> list[str]:
    if not NOTE_DIR.exists():
        return []
    note_dir = NOTE_DIR.resolve()
    names: list[str] = []
    for path in NOTE_DIR.iterdir():
        resolved = path.resolve()
        if path.is_file() and is_relative_to(resolved, note_dir) and path.suffix.lower() == ".md" and path.name != ".gitkeep":
            names.append(path.name)
    return sorted(names)


def parse_note_sections(text: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    current: str | None = None
    buffer: list[str] = []

    def flush() -> None:
        if current is not None:
            sections[current] = "\n".join(buffer).strip()

    for line in text.splitlines():
        if line.startswith("## "):
            flush()
            heading = line[3:].strip()
            current = HEADING_TO_FIELD.get(heading)
            buffer = []
            continue
        if current is not None:
            buffer.append(line)
    flush()
    return sections


def render_note_view(note_file_name: str) -> str:
    note_path = resolve_note_path(note_file_name)
    text = note_path.read_text(encoding="utf-8", errors="replace")
    sections = parse_note_sections(text)
    lines = [
        "Engel Research Note Viewer V1",
        "READ_ONLY_VIEWER / UNTRUSTED_RESEARCH_NOTE_VIEW_ONLY / LOCAL_ONLY",
        "",
        f"File: {note_path.name}",
        "",
        "Status labels:",
        *[f"- {status}" for status in VIEWER_STATUS],
        "",
        "Safety boundary:",
        *[f"- {item}" for item in BOUNDARY_TEXT],
        "",
        "Displayed note fields:",
    ]
    for field in DISPLAY_FIELDS:
        value = sections.get(field, "(not present)")
        lines.extend(["", f"{field}:", textwrap.indent(value, "  ")])
    return "\n".join(lines).rstrip() + "\n"


def usage_text() -> str:
    return textwrap.dedent(
        """\
        Engel Research Note Viewer V1

        Status:
        READ_ONLY_VIEWER / UNTRUSTED_RESEARCH_NOTE_VIEW_ONLY / LOCAL_ONLY / BOUNDED_REPORTS_ONLY

        Usage:
          python engel_research_note_viewer.py --list
          python engel_research_note_viewer.py --show <note-file-name>

        Boundary:
          Reads only reports\\self_research_notes by explicit file name. No memory write, patch apply,
          source mutation, execution, training, indexing, embedding, provider call, network, browser,
          or background worker behavior is enabled.
        """
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=True, description="Read-only viewer for untrusted Engel research notes.")
    parser.add_argument("--list", action="store_true", help="List bounded untrusted research note files.")
    parser.add_argument("--show", metavar="NOTE_FILE_NAME", help="Show one bounded untrusted research note by file name.")
    return parser


def main(argv: list[str] | None = None, stdout=None, stderr=None) -> int:
    out = stdout if stdout is not None else sys.stdout
    err = stderr if stderr is not None else sys.stderr
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.list and not args.show:
        out.write(usage_text())
        return 0
    if args.list and args.show:
        err.write("Choose either --list or --show, not both.\n")
        return 2
    try:
        if args.list:
            names = list_note_names()
            if not names:
                out.write("No untrusted research notes found in reports\\self_research_notes.\n")
                return 0
            out.write("Untrusted research notes:\n")
            for name in names:
                out.write(f"- {name}\n")
            return 0
        out.write(render_note_view(args.show))
        return 0
    except ResearchNoteViewerError as exc:
        err.write(f"[REJECTED] {exc}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
