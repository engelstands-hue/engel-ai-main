from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SURFACE = ROOT / "engel_code_companion_patch_status_surface.py"
VERIFIER = ROOT / "tools" / "verify_engel_code_companion_patch_status_surface.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_CODE_COMPANION_LOW_RISK_PATCH_GUI_STATUS_V1.md"
COMPANION = ROOT / "engel_companion.py"
RESEARCH_OFFICE = ROOT / "engel_research_office.py"
RECEIPT_DIR = ROOT / "reports" / "code_companion_patch_receipts"

REQUIRED_STATUSES = [
    "CODE_COMPANION_PATCH_STATUS_SURFACE",
    "READ_ONLY_STATUS",
    "LOW_RISK_PATCH_CONTRACT_VISIBLE",
    "LOW_RISK_PATCH_RUNNER_VISIBLE",
    "PATCH_RECEIPTS_VISIBLE",
    "NO_PATCH_APPLY_BUTTON",
    "NO_SOURCE_MUTATION_BUTTON",
    "NO_COMMIT_BUTTON",
    "NO_VERIFIER_EXECUTION_BUTTON",
    "NO_TRUSTED_MEMORY_WRITE",
    "NO_PROVIDER_CALLS",
    "NO_NETWORK",
    "NO_BROWSER",
    "NO_BACKGROUND_WORKER",
    "NO_STARTUP_AUTORUN",
]

GUI_LABELS = [
    "CODE COMPANION PATCH STATUS",
    "READ ONLY",
    "LOW RISK PATCHES ONLY",
    "CONTRACT VISIBLE",
    "RUNNER STATUS VISIBLE",
    "PATCH RECEIPTS VISIBLE",
    "NO PATCH APPLY BUTTON",
    "NO SOURCE MUTATION BUTTON",
    "NO COMMIT BUTTON",
    "NO VERIFIER EXECUTION BUTTON",
    "NO TRUSTED MEMORY WRITE",
    "NO PROVIDER NETWORK BROWSER",
    "NO BACKGROUND WORKER",
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
]


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def load_surface_module():
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    import engel_code_companion_patch_status_surface as surface

    return surface


def check_files_exist() -> None:
    for path in [SURFACE, VERIFIER, REPORT, COMPANION, RESEARCH_OFFICE]:
        require(path.exists() and path.is_file(), "required file missing: " + str(path))
    require(RECEIPT_DIR.exists() and RECEIPT_DIR.is_dir(), "Code Companion patch receipt folder missing")


def check_required_text() -> None:
    text = read_text(SURFACE) + "\n" + read_text(REPORT)
    for needle in REQUIRED_STATUSES + GUI_LABELS + IMPLEMENTED_CLASSES + DRY_RUN_ONLY_CLASSES + STOP_CLASSES:
        require(needle in text, "patch status surface missing required text: " + needle)
    for needle in [
        "reports\\code_companion_patch_receipts",
        "non-recursive receipt count",
        "Low-Risk Patch Apply Contract V1 status",
        "Low-Risk Patch Runner V1 status",
        "no commit automation boundary",
        "no patch apply button boundary",
        "no source mutation button boundary",
        "no provider/network/browser boundary",
        "Next safe steps",
    ]:
        require(needle in text, "patch status surface missing display/boundary text: " + needle)


def check_gui_integration() -> None:
    for path in [COMPANION, RESEARCH_OFFICE]:
        text = read_text(path)
        require(
            "engel_code_companion_patch_status_surface" in text,
            path.name + " does not import Code Companion patch status surface",
        )
        require(
            "code_companion_patch_status_surface.render_status()" in text,
            path.name + " does not render Code Companion patch status surface",
        )
        require("Code Companion Review" in text, path.name + " missing Code Companion Review tab label")


def check_no_forbidden_active_behavior() -> None:
    text = read_text(SURFACE)
    lowered = text.lower()
    for snippet in FORBIDDEN_IMPORT_LINES:
        require(snippet not in lowered, "status surface contains forbidden import: " + snippet)
    for snippet in FORBIDDEN_ACTIVE_SNIPPETS:
        require(snippet.lower() not in lowered, "status surface contains forbidden active snippet: " + snippet)


def check_runtime_smoke() -> None:
    surface = load_surface_module()
    output = surface.render_status()
    for needle in [
        "CODE COMPANION PATCH STATUS",
        "LOW_RISK_PATCH_CONTRACT_VISIBLE",
        "LOW_RISK_PATCH_RUNNER_VISIBLE",
        "PATCH_RECEIPTS_VISIBLE",
        "documentation_typo_or_label_fix",
        "report_hash_refresh",
        "provider/network/browser activation",
        "reports\\code_companion_patch_receipts\\",
        "non-recursive receipt count",
        "NO PATCH APPLY BUTTON",
        "NO COMMIT BUTTON",
    ]:
        require(needle in output, "status surface output missing: " + needle)


def check_report_text() -> None:
    text = read_text(REPORT)
    for needle in [
        "Engel Code Companion Low-Risk Patch GUI Status V1",
        "Files Read First",
        "Files Created",
        "Files Updated",
        "GUI Patch Status Behavior",
        "Visible Labels",
        "Smoke Results",
        "Verification Results",
        "Focused Safety Scan",
        "No unsafe GUI actions were exposed",
        "Packaging skipped",
        "Final Scoped Process Sweep",
        "Git Status Summary",
    ]:
        require(needle in text, "patch status report missing text: " + needle)


def main() -> int:
    try:
        check_files_exist()
        check_required_text()
        check_gui_integration()
        check_no_forbidden_active_behavior()
        check_runtime_smoke()
        check_report_text()
    except CheckFailure as exc:
        print("[FAIL]", exc)
        return 1
    print("[PASS] Engel Code Companion patch status surface verifier passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
