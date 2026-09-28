from __future__ import annotations

import ast
import importlib.util
import io
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SURFACE = ROOT / "engel_low_risk_self_fix_status_surface.py"
VERIFIER = ROOT / "tools" / "verify_engel_low_risk_self_fix_status_surface.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_LOW_RISK_SELF_FIX_STATUS_SURFACE_V1.md"
RECEIPT_DIR = ROOT / "reports" / "self_fix_receipts"

REQUIRED_STATUSES = [
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

IMPLEMENTED_CLASSES = [
    "stale_pid_cleanup",
    "report_hash_refresh",
    "generated_report_metadata_update",
    "generated_artifact_cleanup",
]

FUTURE_CLASSES = [
    "docs_drift_alignment",
    "core_continuity_missing_verified_node",
    "verifier_expectation_update_for_existing_committed_contract",
    "read_only_status_surface_reference_update",
    "codex_bridge_report_reference_update",
    "known_safe_path_label_or_status_correction",
]

STOP_CLASSES = [
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


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read_surface() -> str:
    return SURFACE.read_text(encoding="utf-8", errors="replace")


def load_surface():
    spec = importlib.util.spec_from_file_location("engel_low_risk_self_fix_status_surface", SURFACE)
    require(spec is not None and spec.loader is not None, "could not load status surface module")
    module = importlib.util.module_from_spec(spec)
    sys.modules["engel_low_risk_self_fix_status_surface"] = module
    spec.loader.exec_module(module)
    return module


def check_files_exist() -> None:
    for path in [SURFACE, VERIFIER, REPORT]:
        require(path.exists() and path.is_file(), "required file missing: " + str(path))
    require(RECEIPT_DIR.exists() and RECEIPT_DIR.is_dir(), "receipt folder missing")


def check_required_text() -> None:
    text = read_surface() + "\n" + REPORT.read_text(encoding="utf-8", errors="replace")
    for needle in REQUIRED_STATUSES + IMPLEMENTED_CLASSES + FUTURE_CLASSES + STOP_CLASSES:
        require(needle in text, "status surface missing required text: " + needle)
    for needle in [
        "reports\\self_fix_receipts",
        "non-recursive receipt count",
        "verification-before-commit boundary",
        "no trusted-memory boundary",
        "no provider/network/browser/model/package-refresh boundary",
        "no route/startup/background-worker boundary",
        "read-only",
        "does not run fixes",
        "no apply mode",
        "does not commit",
    ]:
        require(needle in text, "status surface missing boundary/display text: " + needle)


def check_forbidden_active_behavior() -> None:
    tree = ast.parse(read_surface())
    forbidden_imports = {
        "requests",
        "urllib",
        "socket",
        "webbrowser",
        "openai",
        "subprocess",
        "glob",
        "shutil",
        "threading",
        "multiprocessing",
        "ctypes",
    }
    forbidden_calls = {"exec", "eval", "__import__"}
    forbidden_attributes = {
        "walk",
        "rglob",
        "glob",
        "unlink",
        "remove",
        "rmdir",
        "rename",
        "replace",
        "write_text",
        "mkdir",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                require(alias.name.split(".")[0] not in forbidden_imports, "forbidden import in status surface: " + alias.name)
        if isinstance(node, ast.ImportFrom) and node.module:
            require(node.module.split(".")[0] not in forbidden_imports, "forbidden import in status surface: " + node.module)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            require(node.func.id not in forbidden_calls, "forbidden dynamic execution call: " + node.func.id)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            require(node.func.attr not in forbidden_attributes, "forbidden mutation/scan call: " + node.func.attr)


def check_runtime_smoke() -> None:
    module = load_surface()
    out = io.StringIO()
    err = io.StringIO()
    require(module.main([], stdout=out, stderr=err) == 0, "status surface main failed")
    output = out.getvalue()
    for needle in [
        "Engel Low-Risk Self-Fix Status Surface V1",
        "STATUS_SURFACE_ONLY",
        "READ_ONLY_VIEW",
        "LOW_RISK_SELF_FIX_VISIBLE",
        "stale_pid_cleanup",
        "provider_api_network_browser_activation",
        "reports\\self_fix_receipts\\",
        "non-recursive receipt count",
        "no trusted-memory boundary",
    ]:
        require(needle in output, "status smoke output missing: " + needle)
    out = io.StringIO()
    err = io.StringIO()
    require(module.main(["--apply"], stdout=out, stderr=err) == 2, "status surface accepted an argument")
    require("read-only" in err.getvalue(), "argument rejection missing read-only boundary")


def main() -> int:
    try:
        check_files_exist()
        check_required_text()
        check_forbidden_active_behavior()
        check_runtime_smoke()
    except CheckFailure as exc:
        print("[FAIL]", exc)
        return 1
    print("[PASS] Engel low-risk self-fix status surface verifier passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
