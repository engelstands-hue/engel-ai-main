#!/usr/bin/env python3
"""Read-only Code Companion candidate finder.

This tool looks only at known local reports and bounded candidate folders. It
creates Code Companion candidate reports, not patches, not source edits, and not
trusted memory.
"""

import argparse
import hashlib
from datetime import datetime, timezone
from pathlib import Path
import sys


PROJECT_ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
OUTPUT_DIR = PROJECT_ROOT / "reports" / "code_companion_candidates"

STATUSES = [
    "CODE_COMPANION_CANDIDATE_FINDER",
    "READ_ONLY_CANDIDATE_FINDER",
    "LOCAL_ONLY",
    "BOUNDED_REPORTS_ONLY",
    "KNOWN_PATHS_ONLY",
    "NO_RECURSIVE_SCAN",
    "NO_SOURCE_MUTATION",
    "NO_PATCH_APPLY",
    "NO_COMMIT",
    "NO_TRUSTED_MEMORY_WRITE",
    "NO_PROVIDER_CALLS",
    "NO_NETWORK",
    "NO_BROWSER",
    "NO_MODEL_RUNTIME",
    "NO_BACKGROUND_WORKER",
]

LABELS = [
    "CODE_COMPANION_CANDIDATE",
    "READ_ONLY_CANDIDATE",
    "NOT_PATCH",
    "NOT_APPROVED_CHANGE",
    "NO_SOURCE_MUTATION",
    "NO_PATCH_APPLY",
    "HUMAN_REVIEW_REQUIRED",
    "VERIFY_BEFORE_USE",
]

CANDIDATE_FIELDS = [
    "code_companion_candidate_id",
    "candidate_type",
    "title",
    "source_signal",
    "source_report_path",
    "detected_at",
    "risk_class",
    "why_it_matters",
    "likely_files_involved",
    "suggested_next_step",
    "suggested_verification_commands",
    "safety_boundary",
    "not_patch",
    "no_source_mutation",
    "no_patch_apply",
    "human_review_required",
]

CANDIDATE_TYPES = [
    "missing_verifier_coverage_candidate",
    "core_continuity_drift_candidate",
    "report_linkage_candidate",
    "status_surface_visibility_candidate",
    "verifier_improvement_waiting_candidate",
    "self_fix_improvement_waiting_candidate",
    "candidate_review_backlog_candidate",
    "daily_cycle_receipt_review_candidate",
    "low_risk_self_fix_opportunity_candidate",
    "package_visibility_followup_candidate",
]

KNOWN_REPORTS = [
    PROJECT_ROOT / "reports" / "codex_bridge" / "ENGEL_CORE_CONTINUITY_MAP_AI_GROWTH_VISIBILITY_REFRESH_UPDATE.md",
    PROJECT_ROOT / "reports" / "codex_bridge" / "ENGEL_AI_GROWTH_VISIBILITY_PACKAGE_REFRESH.md",
    PROJECT_ROOT / "reports" / "codex_bridge" / "ENGEL_AI_GROWTH_UPDATED_SOURCE_GUI_SMOKE.md",
    PROJECT_ROOT / "reports" / "codex_bridge" / "ENGEL_RESEARCH_TO_FIX_LOOP_V1.md",
    PROJECT_ROOT / "reports" / "codex_bridge" / "ENGEL_VERIFIER_IMPROVEMENT_CANDIDATE_V1.md",
    PROJECT_ROOT / "reports" / "codex_bridge" / "ENGEL_SELF_FIX_IMPROVEMENT_CANDIDATE_V1.md",
    PROJECT_ROOT / "reports" / "codex_bridge" / "ENGEL_LOW_RISK_SELF_FIX_RUNNER_V2.md",
    PROJECT_ROOT / "reports" / "codex_bridge" / "ENGEL_DAILY_CYCLE_RUNNER_V1.md",
    PROJECT_ROOT / "reports" / "codex_bridge" / "ENGEL_CANDIDATE_REVIEW_DASHBOARD_V1.md",
    PROJECT_ROOT / "reports" / "codex_bridge" / "ENGEL_MEMORY_PROMOTION_WRITER_V1.md",
]

BOUNDED_FOLDERS = [
    PROJECT_ROOT / "reports" / "codex_bridge",
    PROJECT_ROOT / "reports" / "verifier_improvement_candidates",
    PROJECT_ROOT / "reports" / "self_fix_improvement_candidates",
    PROJECT_ROOT / "reports" / "self_fix_receipts",
    PROJECT_ROOT / "reports" / "daily_cycle_receipts",
    PROJECT_ROOT / "reports" / "memory_candidates",
]


def relative_path(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT)).replace("/", "\\")
    except ValueError:
        return str(path)


def bounded_file_count(folder: Path) -> int:
    if not folder.exists() or not folder.is_dir():
        return 0
    return sum(1 for child in folder.iterdir() if child.is_file() and child.name != ".gitkeep")


def first_existing_report() -> str:
    for path in KNOWN_REPORTS:
        if path.exists() and path.is_file():
            return relative_path(path)
    return "reports\\codex_bridge"


def make_candidate_id(candidate_type: str, detected_at: str) -> str:
    digest = hashlib.sha256((candidate_type + detected_at).encode("utf-8")).hexdigest()[:12]
    return "code_companion_candidate_" + candidate_type + "_" + digest


def candidate_templates() -> list[dict[str, object]]:
    detected_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    report_path = first_existing_report()
    folder_counts = {relative_path(folder): bounded_file_count(folder) for folder in BOUNDED_FOLDERS}
    backlog_count = sum(folder_counts.values())
    commands = [
        "python tools\\verify_engel_code_companion_candidate_finder.py",
        "python tools\\verify_engel_core_continuity_map.py",
        "python tools\\verify_untrusted_content_guard.py",
        "python tools\\verify_prompt_injection_guard.py",
        "python tools\\verify_authority_hierarchy.py",
    ]
    base_boundary = (
        "Candidate only. Read-only report signal. No source mutation, no patch apply, "
        "no commit, no trusted memory write, no provider/network/browser/model runtime, "
        "and no background worker."
    )
    titles = {
        "missing_verifier_coverage_candidate": "Check whether a recent candidate surface needs verifier coverage",
        "core_continuity_drift_candidate": "Review Core Continuity linkage for recent AI growth updates",
        "report_linkage_candidate": "Review report linkage between AI growth and Code Companion planning",
        "status_surface_visibility_candidate": "Review status surface visibility for Code Companion dashboards",
        "verifier_improvement_waiting_candidate": "Review waiting verifier improvement candidates",
        "self_fix_improvement_waiting_candidate": "Review waiting self-fix improvement candidates",
        "candidate_review_backlog_candidate": "Review candidate backlog counts",
        "daily_cycle_receipt_review_candidate": "Review daily cycle receipt signals",
        "low_risk_self_fix_opportunity_candidate": "Review low-risk self-fix opportunity signals",
        "package_visibility_followup_candidate": "Review package visibility follow-up signals",
    }
    candidates: list[dict[str, object]] = []
    for candidate_type in CANDIDATE_TYPES:
        candidates.append(
            {
                "code_companion_candidate_id": make_candidate_id(candidate_type, detected_at),
                "candidate_type": candidate_type,
                "title": titles[candidate_type],
                "source_signal": "Known bounded reports and non-recursive candidate folder counts",
                "source_report_path": report_path,
                "detected_at": detected_at,
                "risk_class": "planning_only_low_risk",
                "why_it_matters": (
                    "This gives Code Companion a reviewable task signal without scanning source, "
                    "applying a patch, or treating the signal as approved work. "
                    f"Current bounded candidate/receipt file count: {backlog_count}."
                ),
                "likely_files_involved": [report_path],
                "suggested_next_step": "Human review may decide whether to turn this into a patch candidate plan.",
                "suggested_verification_commands": commands,
                "safety_boundary": base_boundary,
                "not_patch": True,
                "no_source_mutation": True,
                "no_patch_apply": True,
                "human_review_required": True,
            }
        )
    return candidates


def render_candidate(candidate: dict[str, object]) -> str:
    lines = [
        "# Engel Code Companion Candidate V1",
        "",
        "Status:",
        *["- " + status for status in STATUSES],
        "",
        "Labels:",
        *["- " + label for label in LABELS],
        "",
    ]
    for field in CANDIDATE_FIELDS:
        value = candidate[field]
        lines.append("## " + field)
        if isinstance(value, list):
            lines.extend("- " + str(item) for item in value)
        elif isinstance(value, bool):
            lines.append("true" if value else "false")
        else:
            lines.append(str(value))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def safe_file_name(candidate: dict[str, object]) -> str:
    candidate_id = str(candidate["code_companion_candidate_id"])
    return candidate_id + ".md"


def print_status() -> None:
    print("Engel Code Companion Candidate Finder V1")
    print("Status: " + " / ".join(STATUSES))
    print("Output folder: " + relative_path(OUTPUT_DIR))
    print("Known bounded folders:")
    for folder in BOUNDED_FOLDERS:
        print("- " + relative_path(folder) + f" ({bounded_file_count(folder)} files)")
    print("Boundary: read-only candidate finder; no source mutation, patch apply, commit, provider, network, browser, trusted memory, model runtime, or background worker.")


def print_candidates(candidates: list[dict[str, object]]) -> None:
    for candidate in candidates:
        print("- " + str(candidate["code_companion_candidate_id"]) + ": " + str(candidate["title"]))


def write_candidates(candidates: list[dict[str, object]]) -> list[Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for candidate in candidates:
        path = OUTPUT_DIR / safe_file_name(candidate)
        path.write_text(render_candidate(candidate), encoding="utf-8", newline="\n")
        written.append(path)
    return written


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Find bounded Code Companion candidate tasks without scanning source or applying changes."
    )
    parser.add_argument("--status", action="store_true", help="Print finder status and safety boundary.")
    parser.add_argument("--dry-run", action="store_true", help="Print candidate summaries without writing files.")
    parser.add_argument("--write-candidates", action="store_true", help="Write candidate reports to the bounded output folder.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not (args.status or args.dry_run or args.write_candidates):
        parser.print_help()
        print()
        print("Safe usage: choose --status, --dry-run, or --write-candidates.")
        return 0

    candidates = candidate_templates()
    if args.status:
        print_status()
    if args.dry_run:
        print("Dry-run candidate summaries:")
        print_candidates(candidates)
    if args.write_candidates:
        written = write_candidates(candidates)
        print("Wrote Code Companion candidate reports:")
        for path in written:
            print("- " + relative_path(path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
