from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
VIEWER = ROOT / "engel_code_companion_patch_receipt_viewer.py"
VERIFIER = ROOT / "tools" / "verify_engel_code_companion_patch_receipt_viewer.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_CODE_COMPANION_PATCH_RECEIPT_VIEWER_V1.md"
RECEIPT_DIR = ROOT / "reports" / "code_companion_patch_receipts"
TEMP_RECEIPT = RECEIPT_DIR / "code_companion_patch_receipt_temp_viewer_verifier.md"

REQUIRED_STATUSES = [
    "CODE_COMPANION_PATCH_RECEIPT_VIEWER",
    "READ_ONLY_VIEWER",
    "LOCAL_ONLY",
    "BOUNDED_RECEIPTS_ONLY",
    "NO_RECEIPT_MUTATION",
    "NO_PATCH_APPLY",
    "NO_SOURCE_MUTATION",
    "NO_COMMIT",
    "NO_VERIFIER_EXECUTION",
    "NO_TRUSTED_MEMORY_WRITE",
    "NO_PROVIDER_CALLS",
    "NO_NETWORK",
    "NO_BROWSER",
    "NO_BACKGROUND_WORKER",
]

REQUIRED_FIELDS = [
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
]

FORBIDDEN_ACTIVE_SNIPPETS = [
    ".write_text(",
    ".unlink(",
    ".rename(",
    ".replace(",
    ".mkdir(",
    ".rglob(",
    "os.walk(",
    "subprocess.",
    "requests.",
    "webbrowser.",
    "openai.",
    "git commit",
]


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def cleanup_temp_receipt() -> None:
    if TEMP_RECEIPT.exists():
        TEMP_RECEIPT.unlink()


def load_viewer_module():
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    import engel_code_companion_patch_receipt_viewer as viewer

    return viewer


def check_files_exist() -> None:
    for path in [VIEWER, VERIFIER, REPORT]:
        require(path.exists() and path.is_file(), "required file missing: " + str(path))
    require(RECEIPT_DIR.exists() and RECEIPT_DIR.is_dir(), "bounded Code Companion patch receipt folder missing")


def check_required_text() -> None:
    text = read_text(VIEWER) + "\n" + read_text(REPORT)
    for needle in REQUIRED_STATUSES + REQUIRED_FIELDS:
        require(needle in text, "viewer missing status/field: " + needle)
    for needle in [
        "--list",
        "--show",
        "reports\\code_companion_patch_receipts",
        "non-recursive receipt count",
        "does not edit receipts",
        "delete receipts",
        "write receipts",
        "apply patches",
        "mutate source",
        "commit changes",
        "execute verifiers",
        "write trusted memory",
        "call providers",
        "background workers",
    ]:
        require(needle in text, "viewer missing CLI/boundary text: " + needle)


def check_no_forbidden_active_behavior() -> None:
    text = read_text(VIEWER)
    lowered = text.lower()
    for snippet in FORBIDDEN_IMPORT_LINES:
        require(snippet not in lowered, "viewer contains forbidden import: " + snippet)
    for snippet in FORBIDDEN_ACTIVE_SNIPPETS:
        require(snippet.lower() not in lowered, "viewer contains forbidden active snippet: " + snippet)


def check_runtime_smoke() -> None:
    viewer = load_viewer_module()
    list_text = viewer.render_receipt_list()
    for needle in [
        "CODE_COMPANION_PATCH_RECEIPT_VIEWER",
        "READ_ONLY_VIEWER",
        "reports\\code_companion_patch_receipts\\",
        "non-recursive receipt count",
    ]:
        require(needle in list_text, "viewer list output missing: " + needle)

    cleanup_temp_receipt()
    RECEIPT_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_RECEIPT.write_text(
        "# Temp Code Companion Patch Receipt\n\n"
        "## patch_run_id\n"
        "temp_patch_run\n\n"
        "## source_patch_candidate_id\n"
        "temp_patch_candidate\n\n"
        "## source_patch_candidate_path\n"
        "reports\\patch_candidates\\temp.md\n\n"
        "## patch_class\n"
        "documentation_typo_or_label_fix\n\n"
        "## mode\n"
        "dry-run\n\n"
        "## files_changed\n"
        "none\n\n"
        "## patch_summary\n"
        "viewer smoke fixture\n\n"
        "## verification_commands\n"
        "not run\n\n"
        "## verification_result\n"
        "not_run\n\n"
        "## safety_scan_result\n"
        "not_run\n\n"
        "## commit_hash\n"
        "not_committed_by_runner_v1\n\n"
        "## stopped\n"
        "false\n\n"
        "## stop_reason\n"
        "none\n\n"
        "## human_intervention_required\n"
        "true\n\n"
        "## rollback_notes\n"
        "manual\n\n"
        "## no_trusted_memory_write\n"
        "true\n\n"
        "## no_provider_network_browser\n"
        "true\n\n"
        "## no_background_worker\n"
        "true\n\n"
        "## no_package_refresh\n"
        "true\n\n"
        "## no_route_startup_mutation\n"
        "true\n",
        encoding="utf-8",
        newline="\n",
    )
    view_text = viewer.render_receipt_view(TEMP_RECEIPT.name)
    for field in REQUIRED_FIELDS:
        require(field in view_text, "viewer show output missing field: " + field)
    for unsafe_name in [
        "..\\outside.md",
        "memory\\receipt.md",
        "receipt*.md",
        "G:\\ENGEL_APP_MEMORY\\receipt.md",
        "\\\\server\\share\\receipt.md",
    ]:
        try:
            viewer.resolve_receipt_path(unsafe_name)
        except viewer.PatchReceiptViewerError:
            continue
        raise CheckFailure("viewer accepted unsafe receipt name: " + unsafe_name)
    cleanup_temp_receipt()


def check_report_text() -> None:
    text = read_text(REPORT)
    for needle in [
        "Engel Code Companion Patch Receipt Viewer V1",
        "Files Read First",
        "Files Created",
        "Viewer Behavior",
        "Read-Only Boundary",
        "Display Fields",
        "Smoke Results",
        "Verification Results",
        "Focused Safety Scan",
        "Packaging skipped",
        "Final Scoped Process Sweep",
        "Git Status Summary",
    ]:
        require(needle in text, "receipt viewer report missing text: " + needle)


def main() -> int:
    try:
        check_files_exist()
        check_required_text()
        check_no_forbidden_active_behavior()
        check_runtime_smoke()
        check_report_text()
    except CheckFailure as exc:
        cleanup_temp_receipt()
        print("[FAIL]", exc)
        return 1
    cleanup_temp_receipt()
    print("[PASS] Engel Code Companion patch receipt viewer verifier passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
