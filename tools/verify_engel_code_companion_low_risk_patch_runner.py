from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "engel_code_companion_low_risk_patch_runner.py"
VERIFIER = ROOT / "tools" / "verify_engel_code_companion_low_risk_patch_runner.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_CODE_COMPANION_LOW_RISK_PATCH_RUNNER_V1.md"
PATCH_CANDIDATE_DIR = ROOT / "reports" / "patch_candidates"
RECEIPT_DIR = ROOT / "reports" / "code_companion_patch_receipts"
TEMP_HIGH_RISK = PATCH_CANDIDATE_DIR / "code_companion_patch_candidate_temp_high_risk_verifier.md"
TEMP_LOW_RISK = PATCH_CANDIDATE_DIR / "code_companion_patch_candidate_temp_low_risk_verifier.md"
TEMP_TARGET = ROOT / "reports" / "codex_bridge" / "code_companion_low_risk_patch_runner_temp_fixture.md"

REQUIRED_STATUSES = [
    "CODE_COMPANION_LOW_RISK_PATCH_RUNNER",
    "PREAPPROVED_LOW_RISK_PATCHES_ONLY",
    "EXPLICIT_PATCH_CANDIDATE_REQUIRED",
    "VERIFY_BEFORE_COMMIT",
    "RECEIPT_REQUIRED",
    "STOP_ON_HIGH_RISK",
    "STOP_ON_UNCLEAR_RISK",
    "NO_PROVIDER_CALLS",
    "NO_NETWORK",
    "NO_BROWSER",
    "NO_MODEL_RUNTIME",
    "NO_TRUSTED_MEMORY_WRITE",
    "NO_PACKAGE_REFRESH",
    "NO_ROUTE_STARTUP_MUTATION",
    "NO_BACKGROUND_WORKER",
    "NO_COMMIT_AUTOMATION",
]

IMPLEMENTED_CLASSES = [
    "documentation_typo_or_label_fix",
    "generated_report_metadata_update",
    "codex_bridge_report_reference_update",
    "read_only_status_surface_label_fix",
]

DRY_RUN_ONLY_CLASSES = [
    "report_hash_refresh",
    "verifier_expectation_update_for_existing_committed_contract",
    "core_continuity_report_only_index_update",
]

STOP_CLASSES = [
    "runtime behavior change",
    "provider/network/browser activation",
    "model loading/inference",
    "trusted memory write",
    "route/startup mutation",
    "package refresh/live promotion",
    "GUI action button addition",
    "security/authority hierarchy change",
    "queue/runtime activation",
    "background worker/autonomous loop",
    "arbitrary refactor",
    "external drive access",
    "package manager change",
    "live/staging artifact mutation",
    "binary file mutation",
    "unknown source file mutation",
]

RECEIPT_FIELDS = [
    "patch_run_id",
    "source_patch_candidate_id",
    "source_patch_candidate_path",
    "patch_class",
    "mode",
    "files_changed",
    "patch_summary",
    "verification_commands",
    "verification_result",
    "safety_scan_result",
    "commit_hash",
    "stopped",
    "stop_reason",
    "human_intervention_required",
    "rollback_notes",
    "no_trusted_memory_write",
    "no_provider_network_browser",
    "no_background_worker",
    "no_package_refresh",
    "no_route_startup_mutation",
]

FORBIDDEN_IMPORT_LINES = [
    "import requests",
    "from requests",
    "import urllib",
    "from urllib",
    "import socket",
    "from socket",
    "import webbrowser",
    "from webbrowser",
    "import openai",
    "from openai",
    "import subprocess",
    "from subprocess",
    "import glob",
    "from glob",
    "import shutil",
    "from shutil",
    "import threading",
    "from threading",
    "import multiprocessing",
    "from multiprocessing",
    "import chromadb",
    "import faiss",
    "import llama",
    "import ollama",
]

FORBIDDEN_ACTIVE_SNIPPETS = [
    ".rglob(",
    "os.walk(",
    "webbrowser.",
    "requests.",
    "urllib.",
    "socket.",
    "openai.",
    "subprocess.",
    "threading.",
    "multiprocessing.",
    "git commit",
    "PyInstaller",
    "Copy-Item",
    "trusted_memory.write",
]


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def cleanup_temp_files() -> None:
    for path in [TEMP_HIGH_RISK, TEMP_LOW_RISK, TEMP_TARGET]:
        if path.exists():
            path.unlink()


def check_files_exist() -> None:
    for path in [RUNNER, VERIFIER, REPORT]:
        require(path.exists() and path.is_file(), "required file missing: " + str(path))
    require(PATCH_CANDIDATE_DIR.exists() and PATCH_CANDIDATE_DIR.is_dir(), "patch candidate folder missing")
    require(RECEIPT_DIR.exists() and RECEIPT_DIR.is_dir(), "patch receipt folder missing")
    require((RECEIPT_DIR / ".gitkeep").exists(), "patch receipt folder placeholder missing")


def check_required_text() -> None:
    text = read_text(RUNNER) + "\n" + read_text(REPORT)
    for needle in REQUIRED_STATUSES + IMPLEMENTED_CLASSES + DRY_RUN_ONLY_CLASSES + STOP_CLASSES + RECEIPT_FIELDS:
        require(needle in text, "runner missing required text: " + needle)
    for needle in [
        "--status",
        "--patch-candidate",
        "--dry-run",
        "--apply",
        "--password-prompt",
        "engel_global_password_gate",
        "run_code_companion_low_risk_patch_apply",
        "Protected action requires --password-prompt.",
        "reports\\patch_candidates",
        "reports\\code_companion_patch_receipts",
        "reports\\codex_bridge\\*.md",
        "memory\\*.md",
        "memory\\*.json",
        "read-only status surface Python files",
        "no commit automation",
        "not_committed_by_runner_v1",
        "not_run_by_runner_v1_no_shell_execution",
    ]:
        require(needle in text, "runner missing CLI/boundary text: " + needle)


def check_forbidden_imports_and_active_behavior() -> None:
    text = read_text(RUNNER)
    lowered = text.lower()
    for snippet in FORBIDDEN_IMPORT_LINES:
        require(snippet not in lowered, "runner contains forbidden import: " + snippet)
    for snippet in FORBIDDEN_ACTIVE_SNIPPETS:
        require(snippet.lower() not in lowered, "runner contains forbidden active snippet: " + snippet)


def load_runner_module():
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    import engel_code_companion_low_risk_patch_runner as runner

    return runner


def write_temp_candidate(path: Path, text: str) -> None:
    PATCH_CANDIDATE_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def check_runtime_smoke() -> None:
    runner = load_runner_module()
    status = runner.render_status()
    for needle in [
        "CODE_COMPANION_LOW_RISK_PATCH_RUNNER",
        "documentation_typo_or_label_fix",
        "report_hash_refresh",
        "STOP_ON_HIGH_RISK",
        "NO_COMMIT_AUTOMATION",
    ]:
        require(needle in status, "runner status output missing: " + needle)

    cleanup_temp_files()
    write_temp_candidate(
        TEMP_HIGH_RISK,
        text=(
            "# Temp high-risk Code Companion patch candidate\n\n"
            "## patch_candidate_id\n"
            "temp_high_risk\n\n"
            "## patch_class\n"
            "provider/network/browser activation\n\n"
            "## patch_summary\n"
            "Request provider/network/browser activation for refusal smoke.\n"
        ),
    )
    high_risk = runner.evaluate_patch_candidate(TEMP_HIGH_RISK.name, "dry-run")
    require(high_risk["stopped"] is True, "high-risk patch candidate was not refused")
    require("STOP_ON_HIGH_RISK" in high_risk["stop_reason"], "high-risk refusal missing STOP_ON_HIGH_RISK")

    TEMP_TARGET.write_text("Alpha label\n", encoding="utf-8", newline="\n")
    write_temp_candidate(
        TEMP_LOW_RISK,
        text=(
            "# Temp low-risk Code Companion patch candidate\n\n"
            "## patch_candidate_id\n"
            "temp_low_risk\n\n"
            "## patch_class\n"
            "documentation_typo_or_label_fix\n\n"
            "## target_file\n"
            "reports\\codex_bridge\\code_companion_low_risk_patch_runner_temp_fixture.md\n\n"
            "## find_text\n"
            "Alpha label\n\n"
            "## replace_text\n"
            "Alpha label fixed\n\n"
            "## patch_summary\n"
            "Dry-run a harmless documentation label change in a temporary report fixture.\n"
        ),
    )
    low_risk = runner.evaluate_patch_candidate(TEMP_LOW_RISK.name, "dry-run")
    require(low_risk["stopped"] is False, "low-risk documentation dry-run was unexpectedly stopped")
    require(low_risk["files_changed"] == [], "dry-run changed files")
    require(TEMP_TARGET.read_text(encoding="utf-8") == "Alpha label\n", "dry-run mutated target fixture")

    import io

    out = io.StringIO()
    err = io.StringIO()
    require(
        runner.main(["--patch-candidate", TEMP_LOW_RISK.name, "--apply"], stdout=out, stderr=err) == 2,
        "apply without password prompt was not refused",
    )
    require("Protected action requires --password-prompt." in err.getvalue(), "missing password prompt refusal missing")
    cleanup_temp_files()


def check_report_text() -> None:
    text = read_text(REPORT)
    for needle in [
        "Engel Code Companion Low-Risk Patch Runner V1",
        "Files Read First",
        "Files Created",
        "Runner Behavior",
        "Implemented V1 Classes",
        "Dry-Run-Only Classes",
        "High-Risk Stop Classes",
        "CLI Behavior",
        "Smoke Results",
        "Verification Results",
        "Focused Safety Scan",
        "No commit automation",
        "Packaging skipped",
        "Final Scoped Process Sweep",
        "Git Status Summary",
    ]:
        require(needle in text, "runner report missing text: " + needle)


def main() -> int:
    try:
        check_files_exist()
        check_required_text()
        check_forbidden_imports_and_active_behavior()
        check_runtime_smoke()
        check_report_text()
    except CheckFailure as exc:
        cleanup_temp_files()
        print("[FAIL]", exc)
        return 1
    cleanup_temp_files()
    print("[PASS] Engel Code Companion low-risk patch runner verifier passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
