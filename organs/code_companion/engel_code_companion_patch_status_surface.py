from __future__ import annotations

from pathlib import Path
import sys


PROJECT_ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
RECEIPT_DIR = PROJECT_ROOT / "reports" / "code_companion_patch_receipts"
MAX_RECENT_RECEIPTS = 5

STATUS_LABELS = [
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

CONTRACT_STATUS = [
    "CONTRACT_ONLY",
    "CODE_COMPANION_LOW_RISK_PATCH_POLICY",
    "PREAPPROVED_LOW_RISK_PATCHES_ONLY",
    "VERIFY_BEFORE_COMMIT",
    "RECEIPT_REQUIRED",
    "STOP_ON_HIGH_RISK",
    "NO_PROVIDER_CALLS",
    "NO_NETWORK",
    "NO_BROWSER",
    "NO_MODEL_RUNTIME",
    "NO_TRUSTED_MEMORY_WRITE",
    "NO_PACKAGE_REFRESH",
    "NO_ROUTE_STARTUP_MUTATION",
    "NO_BACKGROUND_WORKER",
]

RUNNER_STATUS = [
    "CODE_COMPANION_LOW_RISK_PATCH_RUNNER",
    "PREAPPROVED_LOW_RISK_PATCHES_ONLY",
    "EXPLICIT_PATCH_CANDIDATE_REQUIRED",
    "VERIFY_BEFORE_COMMIT",
    "RECEIPT_REQUIRED",
    "STOP_ON_HIGH_RISK",
    "STOP_ON_UNCLEAR_RISK",
    "NO_COMMIT_AUTOMATION",
    "NO_PROVIDER_CALLS",
    "NO_NETWORK",
    "NO_BROWSER",
    "NO_MODEL_RUNTIME",
    "NO_TRUSTED_MEMORY_WRITE",
    "NO_PACKAGE_REFRESH",
    "NO_ROUTE_STARTUP_MUTATION",
    "NO_BACKGROUND_WORKER",
]

IMPLEMENTED_V1_PATCH_CLASSES = [
    "documentation_typo_or_label_fix",
    "generated_report_metadata_update",
    "codex_bridge_report_reference_update",
    "read_only_status_surface_label_fix",
]

DRY_RUN_ONLY_PATCH_CLASSES = [
    "report_hash_refresh",
    "verifier_expectation_update_for_existing_committed_contract",
    "core_continuity_report_only_index_update",
]

HIGH_RISK_STOP_CLASSES = [
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

NEXT_SAFE_STEPS = [
    "review patch candidates manually before runner use",
    "dry-run an explicit patch candidate before any apply",
    "apply only implemented V1 low-risk classes",
    "review generated patch receipts",
    "run verifier and guard commands outside the GUI before any commit",
    "keep broader patch runner work behind separate contracts",
]


def safe_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def receipt_files() -> list[Path]:
    if not RECEIPT_DIR.exists() or not RECEIPT_DIR.is_dir():
        return []
    files = [
        path
        for path in RECEIPT_DIR.iterdir()
        if path.is_file() and path.name != ".gitkeep" and path.suffix.lower() == ".md"
    ]
    files.sort(key=safe_mtime, reverse=True)
    return files


def receipt_count() -> int:
    return len(receipt_files())


def recent_receipt_names() -> list[str]:
    return [path.name for path in receipt_files()[:MAX_RECENT_RECEIPTS]]


def render_status() -> str:
    recent = recent_receipt_names()
    lines = [
        "CODE COMPANION PATCH STATUS",
        "",
        "Status:",
        *["- " + status for status in STATUS_LABELS],
        "",
        "GUI labels:",
        *["- " + label for label in GUI_LABELS],
        "",
        "Low-Risk Patch Apply Contract V1 status:",
        *["- " + status for status in CONTRACT_STATUS],
        "",
        "Low-Risk Patch Runner V1 status:",
        *["- " + status for status in RUNNER_STATUS],
        "",
        "Implemented V1 patch classes:",
        *["- " + class_name for class_name in IMPLEMENTED_V1_PATCH_CLASSES],
        "",
        "Dry-run-only patch classes:",
        *["- " + class_name for class_name in DRY_RUN_ONLY_PATCH_CLASSES],
        "",
        "High-risk stop classes:",
        *["- " + class_name for class_name in HIGH_RISK_STOP_CLASSES],
        "",
        "Patch receipts:",
        "- folder: reports\\code_companion_patch_receipts\\",
        "- non-recursive receipt count: " + str(receipt_count()),
        "- recent receipt filenames:",
    ]
    if recent:
        lines.extend("  - " + name for name in recent)
    else:
        lines.append("  - none")
    lines.extend(
        [
            "",
            "Boundaries:",
            "- no commit automation boundary",
            "- no patch apply button boundary",
            "- no source mutation button boundary",
            "- no verifier execution button boundary",
            "- no trusted memory write boundary",
            "- no provider/network/browser boundary",
            "- no model runtime boundary",
            "- no package refresh boundary",
            "- no route/startup/background-worker boundary",
            "- read-only GUI visibility only",
            "",
            "Next safe steps:",
            *["- " + step for step in NEXT_SAFE_STEPS],
            "",
            "CLI:",
            "- python engel_code_companion_patch_status_surface.py",
            "- python engel_code_companion_low_risk_patch_runner.py --status",
            "- python engel_code_companion_patch_receipt_viewer.py --list",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None, stdout=None, stderr=None) -> int:
    out = stdout if stdout is not None else sys.stdout
    err = stderr if stderr is not None else sys.stderr
    args = list(argv or [])
    if args:
        err.write("Code Companion patch status is read-only and accepts no arguments.\n")
        return 2
    out.write(render_status())
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
