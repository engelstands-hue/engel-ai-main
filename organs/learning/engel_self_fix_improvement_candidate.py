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
VERIFIER_CANDIDATE_DIR = PROJECT_ROOT / "reports" / "verifier_improvement_candidates"
OUTPUT_DIR = PROJECT_ROOT / "reports" / "self_fix_improvement_candidates"
TOOL_VERSION = "ENGEL_SELF_FIX_IMPROVEMENT_CANDIDATE_V1"

TOOL_STATUS = [
    "SELF_FIX_IMPROVEMENT_CANDIDATE_ONLY",
    "FROM_UNTRUSTED_RESEARCH_CHAIN",
    "NO_SELF_FIX_POLICY_UPDATE",
    "NO_SELF_FIX_RUNNER_ACTIVATION",
    "NO_VERIFIER_UPDATE",
    "NO_SOURCE_MUTATION",
    "NO_PATCH_APPLY",
    "NOT_TRUSTED_MEMORY",
    "HUMAN_REVIEW_REQUIRED",
    "NO_PROVIDER_CALLS",
    "NO_NETWORK",
    "NO_BROWSER",
    "NO_BACKGROUND_WORKER",
    "NO_RUNTIME_TRIGGER",
]

CANDIDATE_LABELS = [
    "SELF_FIX_IMPROVEMENT_CANDIDATE_ONLY",
    "FROM_UNTRUSTED_RESEARCH_CHAIN",
    "NOT_TRUSTED_MEMORY",
    "HUMAN_REVIEW_REQUIRED",
    "NO_SELF_FIX_POLICY_UPDATE",
    "NO_SELF_FIX_RUNNER_ACTIVATION",
    "NO_SOURCE_MUTATION",
    "NO_PATCH_APPLY",
    "NO_VERIFIER_UPDATE",
    "NO_AUTOMATION_TRIGGERED",
]

CANDIDATE_FIELDS = [
    "self_fix_improvement_candidate_id",
    "source_input_type",
    "source_input_id",
    "source_input_path",
    "topic_id",
    "topic_title",
    "created_at",
    "trust_status",
    "candidate_summary",
    "candidate_details",
    "self_fix_relevance",
    "related_low_risk_classes",
    "related_high_risk_stop_classes",
    "suggested_runner_boundary",
    "suggested_verification_requirement",
    "suggested_receipt_requirement",
    "escalation_notes",
    "uncertainty_notes",
    "safety_notes",
    "required_human_review",
    "required_core_continuity_review",
    "not_trusted_memory",
    "no_self_fix_policy_update",
    "no_self_fix_runner_activation",
    "no_source_mutation",
    "no_patch_apply",
]

LOW_RISK_SELF_FIX_CLASSES = [
    "stale_pid_cleanup",
    "report_hash_refresh",
    "generated_report_metadata_update",
    "docs_drift_alignment",
    "core_continuity_missing_verified_node",
    "verifier_expectation_update_for_existing_committed_contract",
    "generated_artifact_cleanup",
    "read_only_status_surface_reference_update",
    "codex_bridge_report_reference_update",
    "known_safe_path_label_or_status_correction",
]

HIGH_RISK_STOP_CLASSES = [
    "provider_api_network_browser_activation",
    "model_loading_or_inference",
    "trusted_memory_write",
    "route_startup_source_behavior_mutation",
    "background_worker_or_autonomous_loop",
    "package_refresh_or_live_exe_promotion",
    "file_import_copy_move_sync",
    "queue_runtime_or_worker_activation",
    "security_authority_hierarchy_change",
    "deletion_of_unknown_or_unclassified_files",
]

LESSON_FIELD_HEADINGS = {
    "Lesson Candidate Id": "lesson_candidate_id",
    "Source Research Note Id": "source_research_note_id",
    "Topic Id": "topic_id",
    "Topic Title": "topic_title",
    "Candidate Summary": "candidate_summary",
    "Candidate Details": "candidate_details",
    "Evidence From Note": "evidence_from_note",
    "Possible Self Fix Relevance": "possible_self_fix_relevance",
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

VERIFIER_FIELD_HEADINGS = {
    "Verifier Improvement Candidate Id": "verifier_improvement_candidate_id",
    "Source Lesson Candidate Id": "source_lesson_candidate_id",
    "Source Memory Candidate Proposal Id": "source_memory_candidate_proposal_id",
    "Topic Id": "topic_id",
    "Topic Title": "topic_title",
    "Candidate Summary": "candidate_summary",
    "Proposed Verifier Focus": "proposed_verifier_focus",
    "Suggested Check Scope": "suggested_check_scope",
    "Evidence From Source": "evidence_from_source",
    "Safety Notes": "safety_notes",
    "Uncertainty Notes": "uncertainty_notes",
}

BOUNDARY_TEXT = [
    "Self-fix improvement candidates are not self-fix policy updates.",
    "Self-fix improvement candidates do not activate a self-fix runner.",
    "Self-fix improvement candidates are not source patches.",
    "Self-fix improvement candidates are not verifier updates.",
    "Self-fix improvement candidates are not trusted memory.",
    "This tool does not mutate source, apply patches, edit verifiers, write trusted memory, call providers, use network, open browser, trigger runtime behavior, or start background workers.",
]


class SelfFixImprovementCandidateError(ValueError):
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
        raise SelfFixImprovementCandidateError("URLs are not accepted.")
    if file_name.startswith("\\\\"):
        raise SelfFixImprovementCandidateError("UNC paths are not accepted.")
    if any(marker in file_name for marker in ("*", "?", "[")):
        raise SelfFixImprovementCandidateError("Wildcard report names are not accepted.")
    if any(separator in file_name for separator in ("\\", "/")):
        raise SelfFixImprovementCandidateError("Only a report file name is accepted, not a path.")
    if ".." in file_name or ":" in file_name:
        raise SelfFixImprovementCandidateError("Path traversal and drive names are not accepted.")
    if not re.fullmatch(r"[A-Za-z0-9._-]+\.md", file_name):
        raise SelfFixImprovementCandidateError("Report names must be safe .md file names.")


def resolve_bounded_input(folder: Path, file_name: str, label: str) -> Path:
    reject_unsafe_report_name(file_name)
    bounded_root = folder.resolve()
    candidate = (bounded_root / file_name).resolve()
    if not is_relative_to(candidate, bounded_root):
        raise SelfFixImprovementCandidateError(label + " path escaped the bounded reports folder.")
    if not candidate.exists() or not candidate.is_file():
        raise SelfFixImprovementCandidateError(label + " report does not exist in the bounded reports folder.")
    if candidate.name == ".gitkeep":
        raise SelfFixImprovementCandidateError(label + " must be a candidate report, not .gitkeep.")
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
    return "self_fix_improvement_candidate_" + hashlib.sha256(seed).hexdigest()[:16]


def source_summary(source_kind: str, sections: dict[str, str], raw_text: str) -> tuple[str, str, str]:
    if source_kind == "lesson":
        summary = sections.get("possible_self_fix_relevance") or sections.get("candidate_summary") or first_nonempty_line(raw_text)
        evidence = sections.get("evidence_from_note") or sections.get("candidate_details") or first_nonempty_line(raw_text)
    elif source_kind == "memory_proposal":
        summary = sections.get("proposed_memory_summary") or sections.get("reason_to_remember") or first_nonempty_line(raw_text)
        evidence = sections.get("evidence_chain") or sections.get("safety_notes") or first_nonempty_line(raw_text)
    else:
        summary = sections.get("candidate_summary") or sections.get("proposed_verifier_focus") or first_nonempty_line(raw_text)
        evidence = sections.get("evidence_from_source") or sections.get("suggested_check_scope") or first_nonempty_line(raw_text)
    uncertainty = sections.get("uncertainty_notes") or "Source remains untrusted and may be incomplete."
    return summary, evidence, uncertainty


def source_input_id(source_kind: str, sections: dict[str, str]) -> str:
    if source_kind == "lesson":
        return sections.get("lesson_candidate_id", "unknown_lesson_candidate")
    if source_kind == "memory_proposal":
        return sections.get("memory_candidate_proposal_id", "unknown_memory_candidate_proposal")
    return sections.get("verifier_improvement_candidate_id", "unknown_verifier_improvement_candidate")


def source_input_type(source_kind: str) -> str:
    if source_kind == "lesson":
        return "lesson_candidate"
    if source_kind == "memory_proposal":
        return "memory_candidate_proposal"
    return "verifier_improvement_candidate"


def matched_classes(text: str, class_names: list[str]) -> list[str]:
    lowered = text.lower()
    return [name for name in class_names if name.lower() in lowered]


def render_list(items: list[str]) -> str:
    if not items:
        return "- none_detected"
    return "\n".join(f"- {item}" for item in items)


def classify_self_fix_relevance(raw_text: str, summary: str, evidence: str) -> str:
    combined = " ".join([raw_text, summary, evidence]).lower()
    relevance: list[str] = []
    if matched_classes(combined, LOW_RISK_SELF_FIX_CLASSES):
        relevance.append("low-risk self-fix class")
    if matched_classes(combined, HIGH_RISK_STOP_CLASSES):
        relevance.append("high-risk stop class")
    if "verifier" in combined or "verification" in combined:
        relevance.append("verifier-before-fix behavior")
    if "receipt" in combined or "rollback" in combined:
        relevance.append("receipt/rollback behavior")
    if "escalat" in combined or "human" in combined:
        relevance.append("escalation behavior")
    if "runner" in combined or "autopilot" in combined:
        relevance.append("future runner design")
    if not relevance:
        relevance.append("future runner design")
    return "; ".join(relevance)


def build_candidate_from_path(source_kind: str, file_name: str) -> dict[str, str]:
    if source_kind == "lesson":
        source_path = resolve_bounded_input(LESSON_DIR, file_name, "Lesson candidate")
        heading_map = LESSON_FIELD_HEADINGS
    elif source_kind == "memory_proposal":
        source_path = resolve_bounded_input(MEMORY_PROPOSAL_DIR, file_name, "Memory candidate proposal")
        heading_map = MEMORY_FIELD_HEADINGS
    elif source_kind == "verifier_candidate":
        source_path = resolve_bounded_input(VERIFIER_CANDIDATE_DIR, file_name, "Verifier improvement candidate")
        heading_map = VERIFIER_FIELD_HEADINGS
    else:
        raise SelfFixImprovementCandidateError("source_kind must be lesson, memory_proposal, or verifier_candidate")

    raw_text = source_path.read_text(encoding="utf-8", errors="replace")
    sections = parse_markdown_sections(raw_text, heading_map)
    summary, evidence, uncertainty = source_summary(source_kind, sections, raw_text)
    low_risk_classes = matched_classes(raw_text + "\n" + summary + "\n" + evidence, LOW_RISK_SELF_FIX_CLASSES)
    high_risk_classes = matched_classes(raw_text + "\n" + summary + "\n" + evidence, HIGH_RISK_STOP_CLASSES)
    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    return {
        "self_fix_improvement_candidate_id": make_candidate_id(source_kind, file_name, timestamp),
        "source_input_type": source_input_type(source_kind),
        "source_input_id": source_input_id(source_kind, sections),
        "source_input_path": project_relative(source_path),
        "topic_id": sections.get("topic_id", "unknown_topic"),
        "topic_title": sections.get("topic_title", "unknown_topic_title"),
        "created_at": timestamp,
        "trust_status": "SELF_FIX_IMPROVEMENT_CANDIDATE_ONLY / FROM_UNTRUSTED_RESEARCH_CHAIN / NOT_TRUSTED_MEMORY / HUMAN_REVIEW_REQUIRED / NO_SELF_FIX_RUNNER_ACTIVATION",
        "candidate_summary": summary,
        "candidate_details": "Possible self-fix improvement candidate derived from an untrusted research-chain artifact.\n\nEvidence from source:\n" + evidence,
        "self_fix_relevance": classify_self_fix_relevance(raw_text, summary, evidence),
        "related_low_risk_classes": render_list(low_risk_classes),
        "related_high_risk_stop_classes": render_list(high_risk_classes),
        "suggested_runner_boundary": "Candidate-only. Any future runner design must stay bounded to pre-approved low-risk classes, stop on high-risk classes, require verifier support, and remain inactive until separately approved.",
        "suggested_verification_requirement": "Human review must define a targeted verifier before any policy or runner change. Standard guard verifiers must still pass.",
        "suggested_receipt_requirement": "Any future self-fix behavior must create a receipt with files changed, verification result, safety scan, commit hash, rollback notes, and reason if stopped.",
        "escalation_notes": "Escalate to human review before any self-fix policy update, runner activation, source mutation, verifier update, route/startup change, provider/network/browser behavior, or trusted-memory write.",
        "uncertainty_notes": uncertainty,
        "safety_notes": "No self-fix policy was updated. No self-fix runner was activated. No verifier was updated. No source was mutated. No patch was applied. No trusted memory was written. No automation was triggered.",
        "required_human_review": "true",
        "required_core_continuity_review": "true",
        "not_trusted_memory": "true",
        "no_self_fix_policy_update": "true",
        "no_self_fix_runner_activation": "true",
        "no_source_mutation": "true",
        "no_patch_apply": "true",
    }


def render_candidate(candidate: dict[str, str]) -> str:
    lines = [
        "# Engel Self-Fix Improvement Candidate V1",
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
        lines.extend([f"## {field}", str(candidate.get(field, "")), ""])
    return "\n".join(lines).rstrip() + "\n"


def safe_output_filename(candidate: dict[str, str]) -> str:
    source = re.sub(r"[^A-Za-z0-9_-]+", "_", Path(candidate.get("source_input_path", "source")).name).strip("_").lower()
    candidate_id = re.sub(r"[^A-Za-z0-9_-]+", "_", candidate["self_fix_improvement_candidate_id"]).strip("_").lower()
    return f"{candidate_id}_{source}.md"


def write_candidate(candidate: dict[str, str]) -> Path:
    output_dir = OUTPUT_DIR.resolve()
    root = PROJECT_ROOT.resolve()
    if not is_relative_to(output_dir, root):
        raise SelfFixImprovementCandidateError("Self-fix improvement candidate output folder escaped the project root.")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = (output_dir / safe_output_filename(candidate)).resolve()
    if not is_relative_to(output_path, output_dir):
        raise SelfFixImprovementCandidateError("Self-fix improvement candidate output path escaped reports\\self_fix_improvement_candidates.")
    output_path.write_text(render_candidate(candidate), encoding="utf-8")
    return output_path


def usage_text() -> str:
    return textwrap.dedent(
        """\
        Engel Self-Fix Improvement Candidate V1

        Status:
        SELF_FIX_IMPROVEMENT_CANDIDATE_ONLY / FROM_UNTRUSTED_RESEARCH_CHAIN / NO_SELF_FIX_POLICY_UPDATE / NO_SELF_FIX_RUNNER_ACTIVATION / NOT_TRUSTED_MEMORY / NO_RUNTIME_TRIGGER

        Usage:
          python engel_self_fix_improvement_candidate.py --lesson <lesson-file-name> --dry-run
          python engel_self_fix_improvement_candidate.py --memory-proposal <proposal-file-name> --dry-run
          python engel_self_fix_improvement_candidate.py --verifier-candidate <candidate-file-name> --dry-run
          python engel_self_fix_improvement_candidate.py --lesson <lesson-file-name> --write
          python engel_self_fix_improvement_candidate.py --memory-proposal <proposal-file-name> --write
          python engel_self_fix_improvement_candidate.py --verifier-candidate <candidate-file-name> --write

        Boundary:
          Reads one explicit untrusted research-chain candidate from a bounded reports folder and
          writes only candidate reports to reports\\self_fix_improvement_candidates when --write is
          supplied. It does not update self-fix policy, activate a runner, modify verifiers, mutate
          source, apply patches, write trusted memory, call providers, use network, open browser,
          trigger runtime behavior, or start background workers.
        """
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=True, description="Create untrusted self-fix improvement candidate reports.")
    parser.add_argument("--lesson", metavar="LESSON_FILE_NAME", help="Read one lesson candidate from reports\\lesson_candidates.")
    parser.add_argument("--memory-proposal", metavar="PROPOSAL_FILE_NAME", help="Read one memory candidate proposal from reports\\memory_candidates.")
    parser.add_argument("--verifier-candidate", metavar="CANDIDATE_FILE_NAME", help="Read one verifier improvement candidate from reports\\verifier_improvement_candidates.")
    parser.add_argument("--dry-run", action="store_true", help="Print the candidate only; do not write a file.")
    parser.add_argument("--write", action="store_true", help="Write the candidate only to reports\\self_fix_improvement_candidates.")
    return parser


def main(argv: list[str] | None = None, stdout=None, stderr=None) -> int:
    out = stdout if stdout is not None else sys.stdout
    err = stderr if stderr is not None else sys.stderr
    parser = build_parser()
    args = parser.parse_args(argv)
    if not any([args.lesson, args.memory_proposal, args.verifier_candidate, args.dry_run, args.write]):
        out.write(usage_text())
        return 0
    provided = [item for item in [args.lesson, args.memory_proposal, args.verifier_candidate] if item]
    if len(provided) != 1:
        err.write("Choose exactly one explicit --lesson, --memory-proposal, or --verifier-candidate input.\n")
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
        elif args.memory_proposal:
            candidate = build_candidate_from_path("memory_proposal", args.memory_proposal)
        else:
            candidate = build_candidate_from_path("verifier_candidate", args.verifier_candidate)
        rendered = render_candidate(candidate)
        if args.write:
            path = write_candidate(candidate)
            out.write(f"WROTE_SELF_FIX_IMPROVEMENT_CANDIDATE: {project_relative(path)}\n")
            out.write("NO_SELF_FIX_POLICY_UPDATE / NO_SELF_FIX_RUNNER_ACTIVATION / NO_VERIFIER_UPDATE / NO_SOURCE_MUTATION / NOT_TRUSTED_MEMORY / NO_AUTOMATION_TRIGGERED\n")
        else:
            out.write(rendered)
        return 0
    except SelfFixImprovementCandidateError as exc:
        err.write(f"[REJECTED] {exc}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
