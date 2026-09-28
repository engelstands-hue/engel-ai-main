#!/usr/bin/env python3
"""Verify Engel Code Companion Verifier Plan V1."""

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "engel_code_companion_verifier_plan.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_CODE_COMPANION_VERIFIER_PLAN_V1.md"
INPUT_DIR = ROOT / "reports" / "patch_candidates"
OUTPUT_DIR = ROOT / "reports" / "verifier_plans"

REQUIRED_STATUSES = [
    "CODE_COMPANION_VERIFIER_PLAN",
    "VERIFIER_PLAN_ONLY",
    "FROM_PATCH_CANDIDATE",
    "NO_TEST_EXECUTION_BY_DEFAULT",
    "NO_PATCH_APPLY",
    "NO_SOURCE_MUTATION",
    "NO_COMMIT",
    "NO_VERIFIER_UPDATE",
    "NO_TRUSTED_MEMORY_WRITE",
    "NO_PROVIDER_CALLS",
    "NO_NETWORK",
    "NO_BROWSER",
    "NO_BACKGROUND_WORKER",
]

REQUIRED_LABELS = [
    "VERIFIER_PLAN_ONLY",
    "NOT_EXECUTED",
    "NO_PATCH_APPLY",
    "NO_SOURCE_MUTATION",
    "HUMAN_REVIEW_REQUIRED",
    "VERIFY_BEFORE_USE",
]

REQUIRED_FIELDS = [
    "verifier_plan_id",
    "source_patch_candidate_id",
    "source_patch_candidate_path",
    "created_at",
    "risk_class",
    "targeted_verifiers",
    "guard_verifiers",
    "optional_gui_smoke",
    "optional_package_smoke",
    "final_process_sweep",
    "git_status_check",
    "focused_safety_scan_terms",
    "not_executed",
    "no_patch_apply",
    "no_source_mutation",
    "human_review_required",
]

REQUIRED_CLI = ["--patch-candidate", "--dry-run", "--write"]
ALLOWED_IMPORT_ROOTS = {"argparse", "hashlib", "datetime", "pathlib", "re", "sys"}
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
        "read one explicit patch candidate from reports\\patch_candidates",
        "write only to reports\\verifier_plans",
        "must not apply the patch",
        "should not execute the verifier plan by default",
        "No patch apply",
        "No verifier execution by default",
    ]:
        require(phrase in combined, "missing boundary phrase: " + phrase)
    require("reports\\patch_candidates" in combined, "missing bounded input folder")
    require("reports\\verifier_plans" in combined, "missing bounded output folder")
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
    print("OK: Engel Code Companion Verifier Plan V1 verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
