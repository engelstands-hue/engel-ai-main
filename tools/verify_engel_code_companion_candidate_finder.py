#!/usr/bin/env python3
"""Verify Engel Code Companion Candidate Finder V1."""

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "engel_code_companion_candidate_finder.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_CODE_COMPANION_CANDIDATE_FINDER_V1.md"
OUTPUT_DIR = ROOT / "reports" / "code_companion_candidates"

REQUIRED_STATUSES = [
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

REQUIRED_TYPES = [
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

REQUIRED_LABELS = [
    "CODE_COMPANION_CANDIDATE",
    "READ_ONLY_CANDIDATE",
    "NOT_PATCH",
    "NOT_APPROVED_CHANGE",
    "NO_SOURCE_MUTATION",
    "NO_PATCH_APPLY",
    "HUMAN_REVIEW_REQUIRED",
    "VERIFY_BEFORE_USE",
]

REQUIRED_FIELDS = [
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

REQUIRED_FOLDERS = [
    "reports\\codex_bridge",
    "reports\\verifier_improvement_candidates",
    "reports\\self_fix_improvement_candidates",
    "reports\\self_fix_receipts",
    "reports\\daily_cycle_receipts",
    "reports\\memory_candidates",
    "reports\\code_companion_candidates",
]

REQUIRED_CLI = ["--status", "--dry-run", "--write-candidates"]
ALLOWED_IMPORT_ROOTS = {"argparse", "hashlib", "datetime", "pathlib", "sys", "textwrap"}
FORBIDDEN_IMPORT_ROOTS = {
    "requests",
    "urllib",
    "socket",
    "webbrowser",
    "openai",
    "subprocess",
    "os",
    "glob",
    "shutil",
    "threading",
    "multiprocessing",
    "chromadb",
    "faiss",
    "llama",
    "ollama",
}
FORBIDDEN_ACTIVE_PATTERNS = [
    r"os\.walk\s*\(",
    r"\.rglob\s*\(",
    r"subprocess\.",
    r"eval\s*\(",
    r"exec\s*\(",
    r"\.unlink\s*\(",
    r"\.rename\s*\(",
]


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read(path: Path) -> str:
    require(path.exists(), "missing required file: " + str(path))
    return path.read_text(encoding="utf-8")


def check_imports(source: str) -> None:
    for match in re.finditer(r"(?m)^\s*import\s+([A-Za-z0-9_., ]+)", source):
        roots = [name.strip().split(".")[0] for name in match.group(1).split(",")]
        for root in roots:
            require(root in ALLOWED_IMPORT_ROOTS, "unexpected import root: " + root)
            require(root not in FORBIDDEN_IMPORT_ROOTS, "forbidden import root: " + root)
    for match in re.finditer(r"(?m)^\s*from\s+([A-Za-z0-9_.]+)\s+import\s+", source):
        root = match.group(1).split(".")[0]
        require(root in ALLOWED_IMPORT_ROOTS, "unexpected import-from root: " + root)
        require(root not in FORBIDDEN_IMPORT_ROOTS, "forbidden import-from root: " + root)


def check_source_and_report() -> None:
    source = read(SOURCE)
    report = read(REPORT)
    combined = source + "\n" + report
    for needle in REQUIRED_STATUSES + REQUIRED_TYPES + REQUIRED_LABELS + REQUIRED_FIELDS + REQUIRED_FOLDERS + REQUIRED_CLI:
        require(needle in combined, "missing required text: " + needle)
    for phrase in [
        "read-only candidate finder",
        "write candidate reports only to reports\\code_companion_candidates",
        "No source mutation",
        "No patch apply",
        "No trusted memory",
    ]:
        require(phrase in combined, "missing boundary phrase: " + phrase)
    require("iterdir()" in source, "candidate finder must use non-recursive bounded folder listing")
    check_imports(source)
    for pattern in FORBIDDEN_ACTIVE_PATTERNS:
        require(not re.search(pattern, source), "source contains forbidden active pattern: " + pattern)


def check_output_folder() -> None:
    require(OUTPUT_DIR.exists() and OUTPUT_DIR.is_dir(), "missing output folder")


def main() -> int:
    try:
        check_output_folder()
        check_source_and_report()
    except CheckFailure as exc:
        print("FAIL: " + str(exc))
        return 1
    print("OK: Engel Code Companion Candidate Finder V1 verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
