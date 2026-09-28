#!/usr/bin/env python3
"""Verify Engel Code Companion Patch Candidate V1."""

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "engel_code_companion_patch_candidate.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_CODE_COMPANION_PATCH_CANDIDATE_V1.md"
INPUT_DIR = ROOT / "reports" / "code_companion_candidates"
OUTPUT_DIR = ROOT / "reports" / "patch_candidates"

REQUIRED_STATUSES = [
    "CODE_COMPANION_PATCH_CANDIDATE",
    "PATCH_CANDIDATE_ONLY",
    "FROM_CODE_COMPANION_CANDIDATE",
    "PLAN_ONLY",
    "NO_SOURCE_MUTATION",
    "NO_PATCH_APPLY",
    "NO_COMMIT",
    "NO_VERIFIER_UPDATE",
    "NO_SELF_FIX_POLICY_UPDATE",
    "NO_TRUSTED_MEMORY_WRITE",
    "NO_PROVIDER_CALLS",
    "NO_NETWORK",
    "NO_BROWSER",
    "NO_MODEL_RUNTIME",
    "NO_BACKGROUND_WORKER",
]

REQUIRED_LABELS = [
    "PATCH_CANDIDATE_ONLY",
    "PLAN_ONLY",
    "NOT_APPLIED",
    "NO_SOURCE_MUTATION",
    "NO_PATCH_APPLY",
    "NO_COMMIT",
    "HUMAN_REVIEW_REQUIRED",
    "VERIFY_BEFORE_USE",
]

REQUIRED_FIELDS = [
    "patch_candidate_id",
    "source_candidate_id",
    "source_candidate_path",
    "created_at",
    "title",
    "risk_class",
    "files_likely_involved",
    "proposed_changes",
    "do_not_touch",
    "verification_commands",
    "focused_safety_scan_terms",
    "rollback_notes",
    "commit_plan",
    "definition_of_done",
    "safety_boundary",
    "not_applied",
    "no_source_mutation",
    "no_patch_apply",
    "human_review_required",
]

REQUIRED_CLI = ["--candidate", "--dry-run", "--write"]
ALLOWED_IMPORT_ROOTS = {"argparse", "hashlib", "datetime", "pathlib", "re", "sys", "textwrap"}
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
    for needle in REQUIRED_STATUSES + REQUIRED_LABELS + REQUIRED_FIELDS + REQUIRED_CLI:
        require(needle in combined, "missing required text: " + needle)
    for phrase in [
        "read one explicit candidate file from reports\\code_companion_candidates",
        "write only to reports\\patch_candidates",
        "This must not apply the patch",
        "No source edits",
        "No patch apply",
        "No commits",
    ]:
        require(phrase in combined, "missing boundary phrase: " + phrase)
    require("reports\\code_companion_candidates" in combined, "missing bounded input folder")
    require("reports\\patch_candidates" in combined, "missing bounded output folder")
    check_imports(source)
    for pattern in FORBIDDEN_ACTIVE_PATTERNS:
        require(not re.search(pattern, source), "source contains forbidden active pattern: " + pattern)


def check_folders() -> None:
    require(INPUT_DIR.exists() and INPUT_DIR.is_dir(), "missing bounded input folder")
    require(OUTPUT_DIR.exists() and OUTPUT_DIR.is_dir(), "missing bounded output folder")


def main() -> int:
    try:
        check_folders()
        check_source_and_report()
    except CheckFailure as exc:
        print("FAIL: " + str(exc))
        return 1
    print("OK: Engel Code Companion Patch Candidate V1 verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
