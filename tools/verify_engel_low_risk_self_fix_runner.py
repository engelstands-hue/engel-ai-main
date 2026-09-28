from __future__ import annotations

import ast
import importlib.util
import io
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "engel_low_risk_self_fix_runner.py"
VERIFIER = ROOT / "tools" / "verify_engel_low_risk_self_fix_runner.py"
CONTRACT_VERIFIER = ROOT / "tools" / "verify_engel_low_risk_self_fix_runner_contract.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_LOW_RISK_SELF_FIX_RUNNER_V1.md"
RECEIPT_DIR = ROOT / "reports" / "self_fix_receipts"

REQUIRED_STATUSES = [
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

FUTURE_CLASSES = [
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

RECEIPT_FIELDS = [
    "self_fix_run_id",
    "issue_detected",
    "classification",
    "allowed_low_risk_class",
    "mode",
    "files_changed",
    "patch_summary",
    "verification_commands",
    "verification_result",
    "safety_scan_result",
    "commit_hash",
    "rollback_notes",
    "stopped",
    "stop_reason",
    "human_intervention_required",
    "no_trusted_memory_write",
    "no_provider_network_browser",
    "no_background_worker",
]


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read_runner_source() -> str:
    return RUNNER.read_text(encoding="utf-8", errors="replace")


def load_runner():
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location("engel_low_risk_self_fix_runner", RUNNER)
    require(spec is not None and spec.loader is not None, "could not load runner module spec")
    module = importlib.util.module_from_spec(spec)
    sys.modules["engel_low_risk_self_fix_runner"] = module
    spec.loader.exec_module(module)
    return module


def check_files_exist() -> None:
    for path in [RUNNER, VERIFIER, CONTRACT_VERIFIER, REPORT]:
        require(path.exists() and path.is_file(), "required file missing: " + str(path))
    require(RECEIPT_DIR.exists() and RECEIPT_DIR.is_dir(), "bounded self-fix receipt folder missing")
    require((RECEIPT_DIR / ".gitkeep").exists(), "bounded self-fix receipt placeholder missing")


def check_required_text() -> None:
    text = read_runner_source() + "\n" + REPORT.read_text(encoding="utf-8", errors="replace")
    for needle in REQUIRED_STATUSES:
        require(needle in text, "runner missing required status: " + needle)
    for needle in [
        "--status",
        "--dry-run",
        "--apply",
        "--issue",
        "--password-prompt",
        "engel_global_password_gate",
        "run_low_risk_self_fix_apply",
        "clear_stale_pid_file",
        "Protected action requires --password-prompt.",
        "reports",
        "self_fix_receipts",
        "must not kill processes",
        "does not commit automatically",
    ]:
        require(needle in text, "runner missing required CLI/boundary text: " + needle)
    for class_name in IMPLEMENTED_V1_CLASSES + FUTURE_CLASSES + HIGH_RISK_STOP_CLASSES:
        require(class_name in text, "runner missing required class: " + class_name)
    for field in RECEIPT_FIELDS:
        require(field in text, "runner missing receipt field: " + field)


def check_class_limits() -> None:
    module = load_runner()
    require(
        module.IMPLEMENTED_LOW_RISK_FIX_CLASSES == IMPLEMENTED_V1_CLASSES,
        "implemented V1 classes are not limited to the requested four classes",
    )
    require(module.FUTURE_LOW_RISK_FIX_CLASSES == FUTURE_CLASSES, "future low-risk class list mismatch")
    require(module.HIGH_RISK_STOP_CLASSES == HIGH_RISK_STOP_CLASSES, "high-risk stop class list mismatch")


def check_forbidden_imports_and_calls() -> None:
    tree = ast.parse(read_runner_source())
    forbidden_imports = {
        "requests",
        "urllib",
        "socket",
        "webbrowser",
        "openai",
        "glob",
        "shutil",
        "threading",
        "multiprocessing",
    }
    forbidden_names = {"exec", "eval", "__import__"}
    forbidden_attributes = {"walk", "rglob", "copy", "copytree", "move", "rename"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                require(alias.name.split(".")[0] not in forbidden_imports, "runner imports forbidden module: " + alias.name)
        if isinstance(node, ast.ImportFrom) and node.module:
            require(node.module.split(".")[0] not in forbidden_imports, "runner imports forbidden module: " + node.module)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            require(node.func.id not in forbidden_names, "runner uses forbidden dynamic execution call: " + node.func.id)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            require(node.func.attr not in forbidden_attributes, "runner uses forbidden filesystem call: " + node.func.attr)


def check_runtime_smoke() -> None:
    module = load_runner()

    out = io.StringIO()
    err = io.StringIO()
    require(module.main(["--status"], stdout=out, stderr=err) == 0, "runner --status failed")
    status_text = out.getvalue()
    for needle in ["LOW_RISK_SELF_FIX_RUNNER", "stale_pid_cleanup", "STOP_ON_HIGH_RISK", "NO_TRUSTED_MEMORY_WRITE"]:
        require(needle in status_text, "status output missing: " + needle)

    out = io.StringIO()
    err = io.StringIO()
    require(module.main(["--dry-run", "--issue", "stale_pid_cleanup"], stdout=out, stderr=err) == 0, "stale PID dry-run failed")
    stale_text = out.getvalue()
    for needle in ["self_fix_run_id", "stale_pid_cleanup", "NO_PROVIDER_NETWORK_BROWSER", "no_trusted_memory_write"]:
        require(needle in stale_text, "stale dry-run missing: " + needle)

    for issue in IMPLEMENTED_V1_CLASSES:
        out = io.StringIO()
        err = io.StringIO()
        require(module.main(["--dry-run", "--issue", issue], stdout=out, stderr=err) == 0, "implemented dry-run failed: " + issue)

    out = io.StringIO()
    err = io.StringIO()
    require(
        module.main(["--apply", "--issue", "stale_pid_cleanup"], stdout=out, stderr=err) == 2,
        "apply without password prompt was not refused",
    )
    require("Protected action requires --password-prompt." in err.getvalue(), "missing password prompt refusal missing")

    out = io.StringIO()
    err = io.StringIO()
    require(
        module.main(["--dry-run", "--issue", "provider_api_network_browser_activation"], stdout=out, stderr=err) == 1,
        "high-risk issue was not refused",
    )
    require("HIGH_RISK_STOP" in out.getvalue(), "high-risk refusal missing HIGH_RISK_STOP")

    out = io.StringIO()
    err = io.StringIO()
    require(
        module.main(["--dry-run", "--issue", "docs_drift_alignment"], stdout=out, stderr=err) == 1,
        "future class was not stopped",
    )
    require("FUTURE_LOW_RISK_NOT_IMPLEMENTED" in out.getvalue(), "future class refusal missing boundary")


def main() -> int:
    try:
        check_files_exist()
        check_required_text()
        check_class_limits()
        check_forbidden_imports_and_calls()
        check_runtime_smoke()
    except CheckFailure as exc:
        print("[FAIL]", exc)
        return 1
    print("[PASS] Engel low-risk self-fix runner verifier passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
