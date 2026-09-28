from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import re
import sys
import textwrap

import engel_lesson_candidate_extractor as lesson_extractor
import engel_research_memory_candidate_proposal as memory_proposal
import engel_untrusted_research_note_generator as note_generator


PROJECT_ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
RECEIPT_DIR = PROJECT_ROOT / "reports" / "memory_candidates"
RUNNER_VERSION = "ENGEL_SELF_LEARNING_MINI_RUNNER_V1"

RUNNER_STATUS = [
    "SELF_LEARNING_MINI_RUNNER",
    "LOCAL_ONLY",
    "ONE_TOPIC_ONE_SOURCE_ONLY",
    "CANDIDATE_LEARNING_ONLY",
    "UNTRUSTED_OUTPUTS_ONLY",
    "NOT_TRUSTED_MEMORY",
    "NO_TRUSTED_MEMORY_WRITE",
    "NO_SOURCE_MUTATION",
    "NO_VERIFIER_UPDATE",
    "NO_SELF_FIX_POLICY_UPDATE",
    "NO_PROVIDER_CALLS",
    "NO_NETWORK",
    "NO_BROWSER",
    "NO_AUTO_DOWNLOADS",
    "NO_AUTO_INDEXING",
    "NO_MODEL_TRAINING",
    "NO_RUNTIME_TRIGGER",
    "NO_BACKGROUND_WORKER",
]

RUNNER_OUTPUT_LABELS = [
    "UNTRUSTED",
    "CANDIDATE_ONLY",
    "NOT_TRUSTED_MEMORY",
    "NO_AUTOMATION_TRIGGERED",
    "HUMAN_REVIEW_REQUIRED",
]

RECEIPT_FIELDS = [
    "self_learning_run_id",
    "topic_id",
    "source",
    "research_note_path",
    "lesson_candidate_path",
    "memory_candidate_proposal_path",
    "trust_status",
    "outputs_created",
    "safety_boundary",
    "next_safe_step",
]

SOURCE_BOUNDARY_TEXT = [
    "one topic per run",
    "one source per run",
    "explicit topic required outside demo",
    "explicit source required outside demo",
    "output only to approved candidate/report folders",
    "no trusted-memory paths",
    "reject URLs through the existing source validator",
    "reject UNC paths through the existing source validator",
    "reject paths outside project root through the existing source validator",
    "reject external drives through the existing source validator",
    "reject wildcards through the existing source validator",
    "reject live/staging artifacts through the existing source validator",
    "reject model folders through the existing source validator",
    "no folder scanning",
]

SAFETY_BOUNDARY = (
    "UNTRUSTED / CANDIDATE_ONLY / NOT_TRUSTED_MEMORY / NO_AUTOMATION_TRIGGERED / "
    "HUMAN_REVIEW_REQUIRED. No trusted memory write, source mutation, verifier update, "
    "self-fix policy update, provider call, network, browser, download, indexing, embedding, "
    "model training, inference, runtime trigger, background worker, or auto research loop."
)


class SelfLearningMiniRunnerError(ValueError):
    pass


def is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
    except ValueError:
        return False
    return True


def project_relative(path: Path) -> str:
    return str(path.relative_to(PROJECT_ROOT)).replace("/", "\\")


def add_runner_labels(labels: list[str]) -> list[str]:
    result = list(labels)
    for label in RUNNER_OUTPUT_LABELS:
        if label not in result:
            result.append(label)
    return result


def render_with_runner_labels(rendered: str) -> str:
    label_block = "\n".join(f"- {label}" for label in RUNNER_OUTPUT_LABELS)
    marker = "Labels:\n"
    if marker in rendered:
        return rendered.replace(marker, marker + label_block + "\n", 1)
    return "Labels:\n" + label_block + "\n\n" + rendered


def make_run_id(topic_id: str, source: str, timestamp: str) -> str:
    seed = f"{topic_id}|{source}|{timestamp}|{RUNNER_VERSION}".encode("utf-8")
    return "self_learning_run_" + hashlib.sha256(seed).hexdigest()[:16]


def safe_slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", value).strip("_").lower() or "unknown"


def note_sections_from_note(note: dict) -> dict[str, str]:
    rendered_note = note_generator.render_markdown_note(note)
    return lesson_extractor.parse_markdown_sections(rendered_note)


def build_candidate_from_note(note: dict, note_path_label: str) -> dict[str, str]:
    sections = note_sections_from_note(note)
    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    possible_lessons = lesson_extractor.split_candidates(sections.get("possible_lesson_candidates", ""))
    summary = possible_lessons[0] if possible_lessons else "Possible lesson candidate requires manual review before any use."
    details = "\n".join(f"- {item}" for item in possible_lessons) if possible_lessons else "- No explicit lesson candidate was present; this placeholder remains unapproved."
    note_id = sections.get("research_note_id", "unknown_note")
    return {
        "lesson_candidate_id": lesson_extractor.make_candidate_id(note_id, summary, timestamp),
        "source_research_note_id": note_id,
        "source_note_path": note_path_label,
        "topic_id": sections.get("topic_id", "unknown_topic"),
        "topic_title": sections.get("topic_title", "unknown_topic_title"),
        "extracted_at": timestamp,
        "trust_status": "LESSON_CANDIDATE_ONLY / FROM_UNTRUSTED_RESEARCH_NOTE / NOT_TRUSTED_MEMORY / NOT_APPROVED_LESSON / UNTRUSTED / CANDIDATE_ONLY / HUMAN_REVIEW_REQUIRED",
        "candidate_summary": summary,
        "candidate_details": details,
        "confidence": "low_to_medium; derived only from a bounded untrusted research note",
        "evidence_from_note": sections.get("key_observations", "No trusted evidence; source note remains untrusted."),
        "uncertainty_notes": sections.get("uncertainty_notes", "Requires human review before use."),
        "safety_notes": "No automation was triggered. This is not trusted memory, not an approved lesson, not a verifier update, and not a self-fix policy update.",
        "possible_verifier_relevance": sections.get("possible_verifier_improvement_candidates", "Requires review before verifier relevance can be trusted."),
        "possible_self_fix_relevance": sections.get("possible_self_fix_improvement_candidates", "Requires review before self-fix relevance can be trusted."),
        "memory_candidate_possible": sections.get("possible_memory_candidate_summary", "Only possible after separate memory candidate proposal and human approval."),
        "required_review_before_use": "Human review, guard compatibility, and verifier compatibility are required before use.",
        "not_trusted_memory": "true",
        "no_source_mutation": "true",
        "no_verifier_update": "true",
        "no_self_fix_policy_update": "true",
    }


def build_proposal_from_candidate(candidate: dict[str, str], lesson_path_label: str) -> dict[str, str]:
    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    summary = candidate.get("memory_candidate_possible") or candidate.get("candidate_summary") or "Possible memory candidate requires human review."
    lesson_id = candidate.get("lesson_candidate_id", "unknown_lesson_candidate")
    source_note_id = candidate.get("source_research_note_id", "unknown_research_note")
    return {
        "memory_candidate_proposal_id": memory_proposal.make_proposal_id(lesson_id, summary, timestamp),
        "source_lesson_candidate_id": lesson_id,
        "source_research_note_id": source_note_id,
        "topic_id": candidate.get("topic_id", "unknown_topic"),
        "topic_title": candidate.get("topic_title", "unknown_topic_title"),
        "proposed_at": timestamp,
        "trust_status": "MEMORY_CANDIDATE_PROPOSAL_ONLY / FROM_LESSON_CANDIDATE / HUMAN_APPROVAL_REQUIRED / NOT_TRUSTED_MEMORY / UNTRUSTED / CANDIDATE_ONLY",
        "proposed_memory_summary": summary,
        "reason_to_remember": "Only if a human decides this untrusted candidate should become reviewed memory after guard/verifier compatibility review.",
        "evidence_chain": f"Research note: {source_note_id}; lesson candidate: {lesson_id}; no trusted memory write occurred.",
        "source_references": f"- {candidate.get('source_note_path', 'unknown_source_note_path')}\n- {lesson_path_label}",
        "safety_notes": "This proposal is not trusted memory and does not update Core Continuity, source code, verifiers, or self-fix policy.",
        "uncertainty_notes": candidate.get("uncertainty_notes", "Requires human review before use."),
        "prompt_injection_review_needed": "true",
        "authority_review_needed": "true",
        "suggested_core_continuity_linkage": "Suggestion only; Core Continuity is not mutated by this runner.",
        "required_human_approval": "true",
        "required_verifier_compatibility": "true",
        "not_trusted_memory": "true",
        "no_trusted_memory_write": "true",
        "no_source_mutation": "true",
    }


def write_labeled_candidate(candidate: dict[str, str]) -> Path:
    output_dir = lesson_extractor.OUTPUT_DIR.resolve()
    if not is_relative_to(output_dir, PROJECT_ROOT.resolve()):
        raise SelfLearningMiniRunnerError("lesson candidate output folder escaped project root")
    lesson_extractor.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = (output_dir / lesson_extractor.safe_output_filename(candidate)).resolve()
    if not is_relative_to(output_path, output_dir):
        raise SelfLearningMiniRunnerError("lesson candidate output path escaped reports\\lesson_candidates")
    output_path.write_text(render_with_runner_labels(lesson_extractor.render_candidate(candidate)), encoding="utf-8")
    return output_path


def write_labeled_proposal(proposal: dict[str, str]) -> Path:
    output_dir = memory_proposal.OUTPUT_DIR.resolve()
    if not is_relative_to(output_dir, PROJECT_ROOT.resolve()):
        raise SelfLearningMiniRunnerError("memory candidate output folder escaped project root")
    memory_proposal.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = (output_dir / memory_proposal.safe_output_filename(proposal)).resolve()
    if not is_relative_to(output_path, output_dir):
        raise SelfLearningMiniRunnerError("memory candidate output path escaped reports\\memory_candidates")
    output_path.write_text(render_with_runner_labels(memory_proposal.render_proposal(proposal)), encoding="utf-8")
    return output_path


def build_receipt(run_id: str, topic_id: str, source: str, note_path: str, candidate_path: str, proposal_path: str) -> dict[str, str]:
    outputs = [
        f"research_note_path={note_path}",
        f"lesson_candidate_path={candidate_path}",
        f"memory_candidate_proposal_path={proposal_path}",
    ]
    return {
        "self_learning_run_id": run_id,
        "topic_id": topic_id,
        "source": source,
        "research_note_path": note_path,
        "lesson_candidate_path": candidate_path,
        "memory_candidate_proposal_path": proposal_path,
        "trust_status": "UNTRUSTED / CANDIDATE_ONLY / NOT_TRUSTED_MEMORY / HUMAN_REVIEW_REQUIRED",
        "outputs_created": "\n".join(f"- {item}" for item in outputs),
        "safety_boundary": SAFETY_BOUNDARY,
        "next_safe_step": "Human reviewer may inspect the untrusted note, lesson candidate, and memory candidate proposal before any separate approval path.",
    }


def render_receipt(receipt: dict[str, str]) -> str:
    lines = [
        "# Engel Self-Learning Mini Runner Receipt V1",
        "",
        "Labels:",
        *[f"- {label}" for label in RUNNER_OUTPUT_LABELS],
        "",
        "Runner status:",
        *[f"- {status}" for status in RUNNER_STATUS],
        "",
    ]
    for field in RECEIPT_FIELDS:
        lines.extend([f"## {field.replace('_', ' ').title()}", str(receipt.get(field, "")), ""])
    return "\n".join(lines).rstrip() + "\n"


def write_receipt(receipt: dict[str, str]) -> Path:
    output_dir = RECEIPT_DIR.resolve()
    if not is_relative_to(output_dir, PROJECT_ROOT.resolve()):
        raise SelfLearningMiniRunnerError("receipt output folder escaped project root")
    RECEIPT_DIR.mkdir(parents=True, exist_ok=True)
    target = (output_dir / f"{safe_slug(receipt['self_learning_run_id'])}_{safe_slug(receipt['topic_id'])}_receipt.md").resolve()
    if not is_relative_to(target, output_dir):
        raise SelfLearningMiniRunnerError("receipt output path escaped reports\\memory_candidates")
    target.write_text(render_receipt(receipt), encoding="utf-8")
    return target


def build_note_from_topic_and_source(topic_id: str, source: str) -> tuple[dict, Path]:
    topic = note_generator.find_topic(topic_id)
    source_path = note_generator.validate_source_path(source)
    preview = note_generator.read_source_preview(source_path)
    note = note_generator.build_research_note(topic, [preview])
    note["labels"] = add_runner_labels(note.get("labels", []))
    return note, source_path


def build_demo_bundle() -> tuple[dict, dict[str, str], dict[str, str], dict[str, str]]:
    library = note_generator.load_topic_library()
    topic = library.get("topics", [{}])[0]
    note = note_generator.build_research_note(topic, [], demo=True)
    note["labels"] = add_runner_labels(note.get("labels", []))
    candidate = build_candidate_from_note(note, "DEMO_ONLY_NOT_WRITTEN.md")
    proposal = build_proposal_from_candidate(candidate, "DEMO_ONLY_NOT_WRITTEN.md")
    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    run_id = make_run_id(str(note.get("topic_id", "demo_topic")), "DEMO_ONLY", timestamp)
    receipt = build_receipt(run_id, str(note.get("topic_id", "demo_topic")), "DEMO_ONLY", "DEMO_ONLY_NOT_WRITTEN.md", "DEMO_ONLY_NOT_WRITTEN.md", "DEMO_ONLY_NOT_WRITTEN.md")
    return note, candidate, proposal, receipt


def render_bundle(note: dict, candidate: dict[str, str], proposal: dict[str, str], receipt: dict[str, str], *, mode: str) -> str:
    sections = [
        "# Engel Self-Learning Mini Runner V1",
        "",
        f"Mode: {mode}",
        "",
        "Runner labels:",
        *[f"- {label}" for label in RUNNER_OUTPUT_LABELS],
        "",
        "Runner status:",
        *[f"- {status}" for status in RUNNER_STATUS],
        "",
        "Source boundaries:",
        *[f"- {item}" for item in SOURCE_BOUNDARY_TEXT],
        "",
        "## Candidate Learning Summary",
        f"- topic_id: {note.get('topic_id')}",
        f"- topic_title: {note.get('topic_title')}",
        f"- research_note_id: {note.get('research_note_id')}",
        f"- lesson_candidate_id: {candidate.get('lesson_candidate_id')}",
        f"- memory_candidate_proposal_id: {proposal.get('memory_candidate_proposal_id')}",
        "- trust_status: UNTRUSTED / CANDIDATE_ONLY / NOT_TRUSTED_MEMORY / HUMAN_REVIEW_REQUIRED",
        "",
        "## Research Note Preview",
        note_generator.render_markdown_note(note),
        "",
        "## Lesson Candidate Preview",
        render_with_runner_labels(lesson_extractor.render_candidate(candidate)),
        "",
        "## Memory Candidate Proposal Preview",
        render_with_runner_labels(memory_proposal.render_proposal(proposal)),
        "",
        "## Self-Learning Receipt Preview",
        render_receipt(receipt),
    ]
    return "\n".join(sections).rstrip() + "\n"


def run_dry(topic_id: str, source: str) -> str:
    note, source_path = build_note_from_topic_and_source(topic_id, source)
    candidate = build_candidate_from_note(note, "DRY_RUN_NOT_WRITTEN.md")
    proposal = build_proposal_from_candidate(candidate, "DRY_RUN_NOT_WRITTEN.md")
    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    run_id = make_run_id(topic_id, project_relative(source_path), timestamp)
    receipt = build_receipt(run_id, topic_id, project_relative(source_path), "DRY_RUN_NOT_WRITTEN.md", "DRY_RUN_NOT_WRITTEN.md", "DRY_RUN_NOT_WRITTEN.md")
    return render_bundle(note, candidate, proposal, receipt, mode="DRY_RUN")


def run_write_candidates(topic_id: str, source: str) -> str:
    note, source_path = build_note_from_topic_and_source(topic_id, source)
    note_path = note_generator.write_note(note)
    candidate = lesson_extractor.build_lesson_candidate(note_path.name)
    candidate["trust_status"] = candidate["trust_status"] + " / UNTRUSTED / CANDIDATE_ONLY / HUMAN_REVIEW_REQUIRED"
    candidate_path = write_labeled_candidate(candidate)
    proposal = memory_proposal.build_memory_candidate_proposal(candidate_path.name)
    proposal["trust_status"] = proposal["trust_status"] + " / UNTRUSTED / CANDIDATE_ONLY"
    proposal_path = write_labeled_proposal(proposal)
    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    run_id = make_run_id(topic_id, project_relative(source_path), timestamp)
    receipt = build_receipt(run_id, topic_id, project_relative(source_path), project_relative(note_path), project_relative(candidate_path), project_relative(proposal_path))
    receipt_path = write_receipt(receipt)
    receipt["outputs_created"] = receipt["outputs_created"] + f"\n- self_learning_receipt_path={project_relative(receipt_path)}"
    receipt_path.write_text(render_receipt(receipt), encoding="utf-8")
    return render_bundle(note, candidate, proposal, receipt, mode="WRITE_CANDIDATES") + f"\nWROTE_SELF_LEARNING_RECEIPT {project_relative(receipt_path)}\n"


def usage_text() -> str:
    return textwrap.dedent(
        """\
        Engel Self-Learning Mini Runner V1

        Status:
        SELF_LEARNING_MINI_RUNNER / LOCAL_ONLY / ONE_TOPIC_ONE_SOURCE_ONLY / CANDIDATE_LEARNING_ONLY / UNTRUSTED_OUTPUTS_ONLY / NOT_TRUSTED_MEMORY

        Usage:
          python engel_self_learning_mini_runner.py --demo
          python engel_self_learning_mini_runner.py --topic-id <topic_id> --source <project-local-file> --dry-run
          python engel_self_learning_mini_runner.py --topic-id <topic_id> --source <project-local-file> --write-candidates

        Boundaries:
          One topic and one source only. Explicit topic required outside demo. Explicit source required outside demo.
          Output only to approved candidate/report folders; no trusted-memory paths. No scan, wildcard,
          external drive read, live/staging read, model folder read, provider call, network, browser,
          download, indexing, embedding, model training, inference, execution, source mutation, verifier
          update, self-fix policy update, trusted-memory write, background worker, or auto research loop.
        """
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=True, description="Run one bounded self-learning candidate pipeline for one topic and one local source.")
    parser.add_argument("--demo", action="store_true", help="Print a demo-only candidate learning bundle; no files are written.")
    parser.add_argument("--topic-id", action="append", help="One explicit self-research topic id. Repeated use is rejected.")
    parser.add_argument("--source", action="append", help="One explicit project-local source file. Repeated use is rejected.")
    parser.add_argument("--dry-run", action="store_true", help="Print the candidate learning bundle without writing outputs.")
    parser.add_argument("--write-candidates", action="store_true", help="Write untrusted note, lesson candidate, memory candidate proposal, and receipt to bounded report folders.")
    return parser


def require_single(values: list[str] | None, label: str) -> str:
    if values is None:
        raise SelfLearningMiniRunnerError(f"explicit {label} required outside demo")
    if len(values) != 1:
        raise SelfLearningMiniRunnerError(f"ONE_TOPIC_ONE_SOURCE_ONLY: exactly one {label} is allowed")
    return values[0]


def main(argv: list[str] | None = None, stdout=None, stderr=None) -> int:
    out = stdout if stdout is not None else sys.stdout
    err = stderr if stderr is not None else sys.stderr
    parser = build_parser()
    args = parser.parse_args(argv)
    if not any([args.demo, args.topic_id, args.source, args.dry_run, args.write_candidates]):
        out.write(usage_text())
        return 0
    if args.demo:
        if any([args.topic_id, args.source, args.dry_run, args.write_candidates]):
            err.write("Use --demo by itself.\n")
            return 2
        note, candidate, proposal, receipt = build_demo_bundle()
        out.write(render_bundle(note, candidate, proposal, receipt, mode="DEMO_ONLY"))
        return 0
    if args.dry_run and args.write_candidates:
        err.write("Choose either --dry-run or --write-candidates, not both.\n")
        return 2
    if not args.dry_run and not args.write_candidates:
        out.write(usage_text())
        return 0
    try:
        topic_id = require_single(args.topic_id, "--topic-id")
        source = require_single(args.source, "--source")
        if args.dry_run:
            out.write(run_dry(topic_id, source))
            return 0
        out.write(run_write_candidates(topic_id, source))
        return 0
    except (SelfLearningMiniRunnerError, note_generator.ResearchNoteError, lesson_extractor.LessonCandidateError, memory_proposal.MemoryCandidateProposalError) as exc:
        err.write(f"[REJECTED] {exc}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
