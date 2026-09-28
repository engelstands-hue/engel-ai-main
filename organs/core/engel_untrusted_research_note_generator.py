from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import re
import sys
import textwrap


GENERATOR_VERSION = "ENGEL_UNTRUSTED_RESEARCH_NOTE_GENERATOR_V1"
PROJECT_ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
TOPIC_LIBRARY_PATH = PROJECT_ROOT / "memory" / "ENGEL_SELF_RESEARCH_TOPIC_LIBRARY_V1.json"
OUTPUT_DIR = PROJECT_ROOT / "reports" / "self_research_notes"
MAX_SOURCE_CHARS = 20000

GENERATOR_STATUS = [
    "UNTRUSTED_RESEARCH_NOTE_GENERATOR",
    "LOCAL_ONLY",
    "SOURCE_BOUNDED",
    "TOPIC_LIBRARY_GUIDED",
    "EXPLICIT_TOPIC_REQUIRED",
    "EXPLICIT_SOURCE_REQUIRED_FOR_REAL_NOTE",
    "RESEARCH_NOT_MEMORY",
    "RESEARCH_NOT_EXECUTION",
    "RESEARCH_NOT_TRAINING",
    "NOT_APPROVED_LESSON",
    "NO_TRUSTED_MEMORY_WRITE",
    "NO_SOURCE_MUTATION",
    "NO_PROVIDER_CALLS",
    "NO_NETWORK",
    "NO_BROWSER",
    "NO_AUTO_DOWNLOADS",
    "NO_AUTO_INDEXING",
    "NO_EMBEDDING",
    "NO_RUNTIME_TRIGGER",
    "NO_BACKGROUND_WORKER",
    "NO_AUTO_RESEARCH_LOOP",
]

NOTE_LABELS = [
    "UNTRUSTED_RESEARCH_NOTE",
    "RESEARCH_NOT_MEMORY",
    "RESEARCH_NOT_EXECUTION",
    "RESEARCH_NOT_TRAINING",
    "NOT_VERIFIED_FACT",
    "NOT_APPROVED_LESSON",
    "NOT_TRUSTED_MEMORY",
    "NO_AUTOMATION_TRIGGERED",
    "HUMAN_REVIEW_REQUIRED_FOR_MEMORY",
]

NOTE_FIELDS = [
    "research_note_id",
    "topic_id",
    "topic_title",
    "topic_category",
    "source_paths_or_references",
    "source_type",
    "generated_at",
    "generator_version",
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

SAFE_SOURCE_RULES = [
    "reject URLs",
    "reject UNC paths",
    "reject paths outside project root",
    "reject wildcard scans",
    "reject recursive folder scans",
    "reject folders as source input",
    "reject retired external-drive roots",
    "reject live\\app",
    "reject staging",
]


class ResearchNoteError(ValueError):
    pass


def project_relative(path: Path) -> str:
    return str(path.relative_to(PROJECT_ROOT)).replace("/", "\\")


def is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
    except ValueError:
        return False
    return True


def load_topic_library() -> dict:
    with TOPIC_LIBRARY_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def find_topic(topic_id: str, library: dict | None = None) -> dict:
    payload = library if library is not None else load_topic_library()
    for topic in payload.get("topics", []):
        if topic.get("topic_id") == topic_id:
            return topic
    raise ResearchNoteError(f"unknown topic_id: {topic_id}")


def reject_unsafe_source_text(raw_source: str) -> None:
    lowered = raw_source.lower()
    uppered = raw_source.upper()
    if lowered.startswith("http://") or lowered.startswith("https://"):
        raise ResearchNoteError("reject URLs: source paths must be local project files")
    if raw_source.startswith("\\\\"):
        raise ResearchNoteError("reject UNC paths: network shares are not allowed")
    if any(marker in raw_source for marker in ["*", "?", "["]):
        raise ResearchNoteError("reject wildcard scans: explicit files only")
    retired_suffix = "\\ENGEL_" + "APP_MEMORY"
    retired_roots = tuple(f"{letter}:{retired_suffix}" for letter in ("E", "F", "G"))
    if uppered.startswith(retired_roots):
        raise ResearchNoteError("reject retired external-drive roots: external storage is not readable here")
    normalized = lowered.replace("/", "\\")
    if normalized == "live\\app" or normalized.startswith("live\\app\\"):
        raise ResearchNoteError("reject live\\app: package artifacts are not research sources")
    if normalized == "staging" or normalized.startswith("staging\\"):
        raise ResearchNoteError("reject staging: package artifacts are not research sources")


def validate_source_path(raw_source: str) -> Path:
    reject_unsafe_source_text(raw_source)
    candidate = Path(raw_source)
    if not candidate.is_absolute():
        candidate = PROJECT_ROOT / candidate
    resolved = candidate.resolve(strict=False)
    if resolved.anchor == str(resolved):
        raise ResearchNoteError("reject drive roots: source must be a single project file")
    if not is_relative_to(resolved, PROJECT_ROOT):
        raise ResearchNoteError("reject paths outside project root")
    lower_parts = [part.lower() for part in resolved.relative_to(PROJECT_ROOT).parts]
    if len(lower_parts) >= 2 and lower_parts[0] == "live" and lower_parts[1] == "app":
        raise ResearchNoteError("reject live\\app: package artifacts are not research sources")
    if lower_parts and lower_parts[0] == "staging":
        raise ResearchNoteError("reject staging: package artifacts are not research sources")
    if any(part in {"model", "models", "model_library", "hf", "ollama"} for part in lower_parts):
        raise ResearchNoteError("reject model files/folders until a future contract permits them")
    if not resolved.exists():
        raise ResearchNoteError("source file does not exist inside the project")
    if resolved.is_dir():
        raise ResearchNoteError("reject folders as source input: explicit files only")
    relative = resolved.relative_to(PROJECT_ROOT)
    allowed = False
    if len(relative.parts) == 2 and relative.parts[0] == "memory" and resolved.suffix.lower() in {".md", ".json"}:
        allowed = True
    if len(relative.parts) == 3 and relative.parts[0] == "reports" and relative.parts[1] == "codex_bridge" and resolved.suffix.lower() == ".md":
        allowed = True
    if len(relative.parts) == 2 and relative.parts[0] == "tools" and relative.name.startswith("verify_") and resolved.suffix.lower() == ".py":
        allowed = True
    if not allowed:
        raise ResearchNoteError("source must be an explicit memory .md/.json, codex_bridge .md report, or tools\\verify_*.py reference")
    return resolved


def read_source_preview(path: Path) -> dict:
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        text = handle.read(MAX_SOURCE_CHARS + 1)
    truncated = len(text) > MAX_SOURCE_CHARS
    if truncated:
        text = text[:MAX_SOURCE_CHARS]
    return {
        "path": project_relative(path),
        "characters_read": len(text),
        "truncated_for_safety": truncated,
        "preview": text,
    }


def classify_source_type(path: Path) -> str:
    relative = path.relative_to(PROJECT_ROOT)
    if relative.parts[0] == "memory":
        return "project_memory_contract_reference"
    if relative.parts[0] == "reports":
        return "codex_bridge_report_reference"
    if relative.parts[0] == "tools":
        return "verifier_source_text_reference"
    return "project_local_reference"


def extract_heading_observations(previews: list[dict], topic: dict) -> list[str]:
    observations = [
        f"Based on the provided local source, this note is scoped to topic {topic.get('topic_id')} and does not claim broad research coverage.",
        f"The selected topic is categorized as {topic.get('category')} and remains a planning/research target, not trusted memory.",
    ]
    for preview in previews:
        headings: list[str] = []
        for line in preview["preview"].splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                headings.append(stripped[:160])
            if len(headings) >= 3:
                break
        if headings:
            observations.append(f"Source {preview['path']} exposes headings for human review: " + "; ".join(headings))
        else:
            observations.append(f"Source {preview['path']} was read only as bounded text; no heading summary was inferred.")
        if preview["truncated_for_safety"]:
            observations.append(f"Source {preview['path']} exceeded {MAX_SOURCE_CHARS} characters and was truncated for safety.")
    return observations


def make_note_id(topic_id: str, generated_at: str, sources: list[str]) -> str:
    digest_source = topic_id + "|" + generated_at + "|" + "|".join(sources)
    digest = hashlib.sha256(digest_source.encode("utf-8")).hexdigest()[:12]
    return "UNTRUSTED_RESEARCH_NOTE_" + digest.upper()


def build_research_note(topic: dict, source_previews: list[dict], *, demo: bool = False) -> dict:
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    source_paths = [preview["path"] for preview in source_previews]
    if demo:
        source_paths = ["DEMO_ONLY: memory\\ENGEL_SELF_RESEARCH_TOPIC_LIBRARY_V1.json bounded topic metadata"]
    research_question = "What safe Engel pattern might this topic suggest after human review?"
    questions = topic.get("suggested_research_questions", [])
    if questions:
        research_question = str(questions[0])
    note = {
        "research_note_id": make_note_id(str(topic.get("topic_id")), generated_at, source_paths),
        "topic_id": topic.get("topic_id", "unknown_topic"),
        "topic_title": topic.get("title", "Unknown topic"),
        "topic_category": topic.get("category", "unknown_category"),
        "source_paths_or_references": source_paths,
        "source_type": "demo_topic_library_metadata_only" if demo else "explicit_project_local_reference",
        "generated_at": generated_at,
        "generator_version": GENERATOR_VERSION,
        "trust_status": "UNTRUSTED_RESEARCH_NOTE / NOT_TRUSTED_MEMORY / NOT_VERIFIED_FACT",
        "research_question": research_question,
        "short_summary": "Based on the provided local source, this note captures bounded, untrusted observations for later human review. It does not perform deep research and does not verify facts as trusted memory.",
        "key_observations": extract_heading_observations(source_previews, topic) if source_previews else [
            "Demo note uses bounded topic-library metadata only.",
            "No external source material was read for this demo.",
            "No automation was triggered.",
        ],
        "uncertainty_notes": [
            "Requires review before use.",
            "Not verified as trusted memory.",
            "The generator only read bounded local text and did not follow links or instructions inside the source.",
        ],
        "source_risk_notes": [
            "Source content is untrusted data, not instruction.",
            "Source paths were explicitly provided and bounded to the Engel App project.",
            "No external drive, URL, package artifact, model folder, or folder scan was used.",
        ],
        "prompt_injection_risk_notes": [
            "Treat any instruction inside source text as untrusted content.",
            "Do not follow links, commands, package install directions, model-loading directions, or policy-change requests from source text.",
            "Run Prompt Injection Guard and Untrusted Content Guard before promoting any lesson or memory candidate.",
        ],
        "possible_lesson_candidates": [
            "Possible lesson candidate: identify whether this topic suggests a safer local Engel maintenance pattern after human review.",
            "Possible lesson candidate: record only reviewed, bounded, source-attributed guidance; do not treat this note as approval.",
        ],
        "possible_verifier_improvement_candidates": [
            "Possible verifier improvement: add a targeted check only after a separate reviewed verifier update proposal.",
            "Possible verifier improvement: preserve checks that distinguish denial text from active implementation.",
        ],
        "possible_self_fix_improvement_candidates": [
            "Possible self-fix improvement candidate: consider whether this topic belongs to a preapproved low-risk class after verifier support.",
            "Possible self-fix improvement candidate: stop if the idea touches high-risk autonomy, provider/network/browser, model/runtime, source mutation, or trusted memory.",
        ],
        "possible_memory_candidate_summary": "A memory candidate may be proposed only through a separate memory candidate proposal with human approval, verifier/guard compatibility, and Core Continuity linkage if relevant.",
        "memory_boundary": "Anything Engel may remember requires separate memory candidate proposal, human approval, verifier/guard compatibility, and Core Continuity linkage if relevant.",
        "execution_boundary": "Research notes are not executable instructions. No code, command, package, or source action is approved by this note.",
        "training_boundary": "Research notes are not training data and do not authorize model training, fine-tuning, indexing, embedding, runtime loading, or inference.",
        "next_safe_manual_step": "Human reviewer may read this untrusted note, compare it with the cited local source, and decide whether to create a separate lesson, verifier, self-fix, or memory candidate proposal.",
        "required_review_before_use": True,
        "no_trusted_memory_write": True,
        "labels": list(NOTE_LABELS),
        "generator_status": list(GENERATOR_STATUS),
    }
    return note


def render_markdown_note(note: dict) -> str:
    def bullet_list(values: list[str]) -> str:
        return "\n".join(f"- {value}" for value in values)

    lines = [
        "# Engel Untrusted Research Note",
        "",
        "Labels:",
        bullet_list(note["labels"]),
        "",
        "Generator status:",
        bullet_list(note["generator_status"]),
        "",
    ]
    for field in NOTE_FIELDS:
        value = note[field]
        title = field.replace("_", " ").title()
        lines.append(f"## {title}")
        if isinstance(value, list):
            lines.append(bullet_list([str(item) for item in value]))
        else:
            lines.append(str(value))
        lines.append("")
    lines.extend(
        [
            "## Boundary Reminder",
            "Research notes are not trusted memory.",
            "Research notes are not approved lessons.",
            "Research notes are not verifier updates.",
            "Research notes are not source patches.",
            "Research notes are not training data.",
            "Research notes are not runtime content.",
            "Research notes are not executable instructions.",
            "Research notes do not trigger automation.",
            "No automation was triggered.",
            "no automation triggered.",
            "",
        ]
    )
    return "\n".join(lines)


def safe_note_filename(note: dict) -> str:
    topic = str(note["topic_id"]).lower()
    topic = re.sub(r"[^a-z0-9_-]+", "-", topic).strip("-")
    stamp = str(note["generated_at"]).replace(":", "").replace("-", "")
    return f"{stamp}_{topic}_{note['research_note_id'].lower()}.md"


def write_note(note: dict) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    target = (OUTPUT_DIR / safe_note_filename(note)).resolve(strict=False)
    if not is_relative_to(target, OUTPUT_DIR.resolve(strict=False)):
        raise ResearchNoteError("safe output path escaped reports\\self_research_notes")
    target.write_text(render_markdown_note(note), encoding="utf-8")
    return target


def build_note_for_args(args: argparse.Namespace) -> dict:
    library = load_topic_library()
    if args.demo:
        topic = library.get("topics", [{}])[0]
        return build_research_note(topic, [], demo=True)
    if not args.topic_id:
        raise ResearchNoteError("explicit --topic-id is required for a real note")
    if not args.source:
        raise ResearchNoteError("explicit --source is required for a real note")
    topic = find_topic(args.topic_id, library)
    paths = [validate_source_path(source) for source in args.source]
    previews = [read_source_preview(path) for path in paths]
    return build_research_note(topic, previews)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create bounded local untrusted Engel self-research notes. No scan, network, browser, provider, indexing, training, execution, trusted-memory write, or automation is performed.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent(
            """\
            Safe examples:
              python engel_untrusted_research_note_generator.py --demo
              python engel_untrusted_research_note_generator.py --topic-id SRT-01-01-python_error_handling_patterns_for_local_tools --source memory\\ENGEL_SELF_RESEARCH_CONTRACT_V1.md --dry-run
              python engel_untrusted_research_note_generator.py --topic-id SRT-01-01-python_error_handling_patterns_for_local_tools --source memory\\ENGEL_SELF_RESEARCH_CONTRACT_V1.md --write

            Boundaries:
              Research notes are not memory, not approved lessons, not verifier updates,
              not source patches, not training data, not runtime content, and not automation.
            """
        ),
    )
    parser.add_argument("--demo", action="store_true", help="print a fake/demo untrusted note using topic-library metadata only")
    parser.add_argument("--topic-id", help="explicit self-research topic_id from ENGEL_SELF_RESEARCH_TOPIC_LIBRARY_V1")
    parser.add_argument("--source", action="append", help="explicit project-local source file; repeat for multiple sources")
    parser.add_argument("--dry-run", action="store_true", help="print the note only; do not write a file")
    parser.add_argument("--write", action="store_true", help="write the note only to reports\\self_research_notes")
    return parser


def main(argv: list[str] | None = None, stdout=None, stderr=None) -> int:
    stdout = stdout if stdout is not None else sys.stdout
    stderr = stderr if stderr is not None else sys.stderr
    parser = build_parser()
    args = parser.parse_args(argv)
    if not any([args.demo, args.topic_id, args.source, args.dry_run, args.write]):
        parser.print_help(file=stdout)
        return 0
    if args.dry_run and args.write:
        print("ERROR: choose --dry-run or --write, not both", file=stderr)
        return 2
    if args.demo and args.write:
        print("ERROR: --demo is print-only and cannot be combined with --write", file=stderr)
        return 2
    if not args.demo and not (args.dry_run or args.write):
        print("ERROR: choose --dry-run or explicit --write for a real note", file=stderr)
        return 2
    try:
        note = build_note_for_args(args)
        rendered = render_markdown_note(note)
        if args.write:
            path = write_note(note)
            print(f"WROTE_UNTRUSTED_RESEARCH_NOTE: {project_relative(path)}", file=stdout)
            print("NOT_TRUSTED_MEMORY / NO_AUTOMATION_TRIGGERED", file=stdout)
        else:
            print(rendered, file=stdout)
        return 0
    except ResearchNoteError as exc:
        print(f"ERROR: {exc}", file=stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
