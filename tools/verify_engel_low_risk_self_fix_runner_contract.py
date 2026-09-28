from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_JSON = ROOT / "memory" / "ENGEL_LOW_RISK_SELF_FIX_RUNNER_CONTRACT_V1.json"
CONTRACT_MD = ROOT / "memory" / "ENGEL_LOW_RISK_SELF_FIX_RUNNER_CONTRACT_V1.md"
VERIFIER = ROOT / "tools" / "verify_engel_low_risk_self_fix_runner_contract.py"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_LOW_RISK_SELF_FIX_RUNNER_CONTRACT_V1.md"

REQUIRED_STATUSES = [
    "CONTRACT_ONLY",
    "LOW_RISK_SELF_FIX_RUNNER_POLICY",
    "RUNNER_NOT_IMPLEMENTED",
    "PREAPPROVED_LOW_RISK_FIXES_ONLY",
    "HIGH_RISK_CHANGES_STOP",
    "VERIFY_BEFORE_COMMIT",
    "RECEIPT_REQUIRED",
    "NO_PROVIDER_CALLS",
    "NO_NETWORK",
    "NO_BROWSER",
    "NO_MODEL_RUNTIME",
    "NO_TRUSTED_MEMORY_WRITE",
    "NO_PACKAGE_REFRESH",
    "NO_ROUTE_STARTUP_MUTATION",
    "NO_BACKGROUND_WORKER",
]

LOW_RISK_CLASSES = [
    "stale_pid_cleanup",
    "report_hash_refresh",
    "generated_report_metadata_update",
    "docs_drift_alignment",
    "core_continuity_missing_verified_node",
    "verifier_expectation_update_for_existing_committed_contract",
    "generated_artifact_cleanup",
    "read_only_status_surface_reference_update",
    "codex_bridge_report_reference_update",
    "known_safe_path_label_or_status_correction",
]

HIGH_RISK_CLASSES = [
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

RUNNER_FLOW = [
    "detect issue",
    "classify issue",
    "confirm allowed low-risk class",
    "prepare patch plan",
    "apply only bounded low-risk fix",
    "run targeted verifier",
    "run guard verifiers",
    "run scripts\\codex_verify.ps1",
    "create self-fix receipt",
    "commit only if all verification passes",
    "stop and report if risk is high or unclear",
]

RECEIPT_FIELDS = [
    "self_fix_run_id",
    "issue_detected",
    "classification",
    "allowed_low_risk_class",
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
]

BOUNDARY_TEXT = [
    "runner not implemented in this step",
    "future runner may only act inside allowed classes",
    "no provider/network/browser",
    "no model runtime",
    "no trusted memory write",
    "no package refresh",
    "no route/startup/source behavior mutation outside bounded fix scope",
    "no external drive access",
    "no arbitrary deletion",
    "no authority hierarchy bypass",
    "no prompt injection guard bypass",
    "no untrusted content guard bypass",
]


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read_all_text() -> str:
    return (
        CONTRACT_JSON.read_text(encoding="utf-8", errors="replace")
        + "\n"
        + CONTRACT_MD.read_text(encoding="utf-8", errors="replace")
        + "\n"
        + REPORT.read_text(encoding="utf-8", errors="replace")
    )


def check_files_exist() -> None:
    for path in [CONTRACT_JSON, CONTRACT_MD, VERIFIER, REPORT]:
        require(path.exists() and path.is_file(), "required file missing: " + str(path))


def check_json_shape() -> None:
    data = json.loads(CONTRACT_JSON.read_text(encoding="utf-8"))
    require(data.get("id") == "engel_low_risk_self_fix_runner_contract_v1", "contract id mismatch")
    require(data.get("type") == "low_risk_self_fix_runner_contract", "contract type mismatch")
    for status in REQUIRED_STATUSES:
        require(status in data.get("status", []), "contract JSON missing status: " + status)
    for class_name in LOW_RISK_CLASSES:
        require(class_name in data.get("allowed_low_risk_fix_classes", []), "contract JSON missing low-risk class: " + class_name)
    for class_name in HIGH_RISK_CLASSES:
        require(class_name in data.get("high_risk_stop_classes", []), "contract JSON missing high-risk class: " + class_name)
    for flow_step in RUNNER_FLOW:
        require(flow_step in data.get("runner_flow", []), "contract JSON missing runner flow step: " + flow_step)
    for field in RECEIPT_FIELDS:
        require(field in data.get("receipt_fields", []), "contract JSON missing receipt field: " + field)
    boundary = data.get("boundary", {})
    for key in [
        "runner_not_implemented_in_this_step",
        "future_runner_may_only_act_inside_allowed_classes",
        "no_provider_network_browser",
        "no_model_runtime",
        "no_trusted_memory_write",
        "no_package_refresh",
        "no_route_startup_source_behavior_mutation_outside_bounded_fix_scope",
        "no_external_drive_access",
        "no_arbitrary_deletion",
        "no_authority_hierarchy_bypass",
        "no_prompt_injection_guard_bypass",
        "no_untrusted_content_guard_bypass",
    ]:
        require(boundary.get(key) is True, "contract JSON boundary missing/false: " + key)
    require(boundary.get("runner_activation_enabled_by_contract") is False, "contract must not activate a runner")


def check_required_text() -> None:
    text = read_all_text()
    lower_text = text.lower()
    for needle in REQUIRED_STATUSES + LOW_RISK_CLASSES + HIGH_RISK_CLASSES + RUNNER_FLOW + RECEIPT_FIELDS + BOUNDARY_TEXT:
        require(needle in text, "contract missing required text: " + needle)
    for needle in [
        "targeted verifier",
        "guard verifiers",
        "scripts\\codex_verify.ps1",
        "focused safety scan",
        "final scoped process sweep",
        "git status review",
        "no active self-fix behavior",
        "no runner was implemented by this contract step",
    ]:
        require(needle in lower_text, "contract missing verification or implementation boundary text: " + needle)


def check_no_active_runner_implementation_in_contract() -> None:
    text = read_all_text().lower()
    forbidden_claims = [
        "runner implemented in this step: true",
        "runner_activation_enabled_by_contract\": true",
        "active runner implementation added",
        "provider call implementation added",
        "background worker implementation added",
        "route mutation implementation added",
        "startup mutation implementation added",
        "package refresh implementation added",
        "trusted_memory write implementation added",
    ]
    for claim in forbidden_claims:
        require(claim not in text, "contract contains forbidden active-runner claim: " + claim)


def check_forbidden_active_behavior() -> None:
    tree = ast.parse(VERIFIER.read_text(encoding="utf-8", errors="replace"))
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
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                require(alias.name.split(".")[0] not in forbidden_imports, "verifier imports forbidden module: " + alias.name)
        if isinstance(node, ast.ImportFrom) and node.module:
            require(node.module.split(".")[0] not in forbidden_imports, "verifier imports forbidden module: " + node.module)


def main() -> int:
    try:
        check_files_exist()
        check_json_shape()
        check_required_text()
        check_no_active_runner_implementation_in_contract()
        check_forbidden_active_behavior()
    except CheckFailure as exc:
        print("[FAIL]", exc)
        return 1
    print("[PASS] Engel low-risk self-fix runner contract verifier passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
