from __future__ import annotations

from pathlib import Path
import sys


PROJECT_ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
RECEIPT_DIR = PROJECT_ROOT / "reports" / "self_fix_receipts"

STATUS = [
    "STATUS_SURFACE_ONLY",
    "READ_ONLY_VIEW",
    "LOW_RISK_SELF_FIX_VISIBLE",
    "RECEIPTS_VISIBLE",
    "NO_FIX_EXECUTION",
    "NO_APPLY",
    "NO_COMMIT",
    "NO_TRUSTED_MEMORY_WRITE",
    "NO_SOURCE_MUTATION",
    "NO_PROVIDER_CALLS",
    "NO_NETWORK",
    "NO_BROWSER",
    "NO_MODEL_RUNTIME",
    "NO_PACKAGE_REFRESH",
    "NO_BACKGROUND_WORKER",
]

RUNNER_STATUS = [
    "LOW_RISK_SELF_FIX_RUNNER",
    "PREAPPROVED_LOW_RISK_FIXES_ONLY",
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
]

IMPLEMENTED_V1_CLASSES = [
    "stale_pid_cleanup",
    "report_hash_refresh",
    "generated_report_metadata_update",
    "generated_artifact_cleanup",
]

FUTURE_LOW_RISK_CLASSES = [
    "docs_drift_alignment",
    "core_continuity_missing_verified_node",
    "verifier_expectation_update_for_existing_committed_contract",
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
    "arbitrary_source_refactor",
    "external_drive_access",
    "package_manager_change",
]


def receipt_count() -> int:
    if not RECEIPT_DIR.exists() or not RECEIPT_DIR.is_dir():
        return 0
    count = 0
    for path in RECEIPT_DIR.iterdir():
        if path.is_file() and path.name != ".gitkeep":
            count += 1
    return count


def render_status() -> str:
    receipt_folder = "reports\\self_fix_receipts\\"
    lines = [
        "Engel Low-Risk Self-Fix Status Surface V1",
        "",
        "Surface status:",
        *[f"- {status}" for status in STATUS],
        "",
        "Runner status:",
        *[f"- {status}" for status in RUNNER_STATUS],
        "",
        "Implemented V1 low-risk classes:",
        *[f"- {class_name}" for class_name in IMPLEMENTED_V1_CLASSES],
        "",
        "Future low-risk classes:",
        *[f"- {class_name}" for class_name in FUTURE_LOW_RISK_CLASSES],
        "",
        "High-risk stop classes:",
        *[f"- {class_name}" for class_name in HIGH_RISK_STOP_CLASSES],
        "",
        "Receipt folder:",
        f"- {receipt_folder}",
        f"- non-recursive receipt count: {receipt_count()}",
        "",
        "Safety boundaries:",
        "- verification-before-commit boundary is active.",
        "- no trusted-memory boundary is active.",
        "- no provider/network/browser/model/package-refresh boundary is active.",
        "- no route/startup/background-worker boundary is active.",
        "- status surface does not run fixes.",
        "- status surface has no apply mode.",
        "- status surface does not commit.",
        "- status surface does not delete files.",
        "- status surface does not mutate source.",
        "- status surface does not write trusted memory.",
        "- status surface does not recursively scan folders.",
        "",
        "CLI:",
        "- python engel_low_risk_self_fix_status_surface.py",
    ]
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None, stdout=None, stderr=None) -> int:
    out = stdout if stdout is not None else sys.stdout
    err = stderr if stderr is not None else sys.stderr
    args = list(argv or [])
    if args:
        err.write("This status surface takes no arguments and is read-only.\n")
        return 2
    out.write(render_status())
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
