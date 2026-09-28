#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_JSON = ROOT / "memory" / "ENGEL_SELF_FIX_AUTOPILOT_CONTRACT_V1.json"
CONTRACT_MD = ROOT / "memory" / "ENGEL_SELF_FIX_AUTOPILOT_CONTRACT_V1.md"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_SELF_FIX_AUTOPILOT_CONTRACT_V1.md"
THIS_FILE = Path(__file__).resolve()


REQUIRED_STATUSES = [
    "CONTRACT_ONLY",
    "SELF_FIX_POLICY_ONLY",
    "LOW_RISK_AUTONOMY_PLANNED",
    "HUMAN_APPROVAL_NOT_REQUIRED_FOR_PREAPPROVED_LOW_RISK_FIXES",
    "HUMAN_APPROVAL_REQUIRED_FOR_HIGH_RISK_CHANGES",
    "NO_PROVIDER_CALLS",
    "NO_NETWORK",
    "NO_BACKGROUND_WORKERS",
    "NO_TRUSTED_MEMORY_WRITE",
    "NO_RUNTIME_EXPANSION",
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
]

SELF_FIX_FLOW = [
    "detect issue",
    "classify issue",
    "confirm class is pre-approved low-risk",
    "create patch candidate",
    "apply patch only inside allowed files/classes",
    "run targeted verifier",
    "run standard guard verifiers",
    "create self-fix receipt",
    "commit only if verifier stack passes",
    "report what was fixed",
]

RECEIPT_FIELDS = [
    "self_fix_id",
    "detected_issue",
    "risk_class",
    "preapproved_autopilot_class",
    "files_changed",
    "patch_summary",
    "verification_commands",
    "verification_result",
    "safety_scan_result",
    "commit_hash",
    "rollback_notes",
    "human_intervention_required",
    "reason_if_stopped",
]

BOUNDARY_PHRASES = [
    "call providers",
    "use network",
    "open browser",
    "load models",
    "run inference",
    "write trusted memory",
    "start background workers",
    "mutate startup/routes/source behavior",
    "package live app",
    "promote EXEs",
    "import/copy/move/sync real files",
    "scan external drives",
    "delete unknown files",
    "bypass authority hierarchy",
    "bypass prompt injection guard",
    "bypass untrusted content guard",
]

RUNNER_CANDIDATES = [
    ROOT / "engel_self_fix_autopilot.py",
    ROOT / "engel_self_fix_autopilot_runner.py",
    ROOT / "tools" / "run_engel_self_fix_autopilot.py",
    ROOT / "tools" / "engel_self_fix_autopilot_runner.py",
]


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read(path: Path) -> str:
    require(path.exists(), "missing required file: " + str(path.relative_to(ROOT)))
    require(path.is_file(), "required path is not a file: " + str(path.relative_to(ROOT)))
    return path.read_text(encoding="utf-8", errors="replace")


def normalize(text: str) -> str:
    return " ".join(text.lower().replace("`", "").replace("\\", "/").replace("-", " ").split())


def require_text(combined: str, needle: str, label: str) -> None:
    require(normalize(needle) in normalize(combined), label + " missing expected text: " + needle)


def load_contract() -> tuple[dict, str, str]:
    payload = json.loads(read(CONTRACT_JSON))
    md = read(CONTRACT_MD)
    return payload, json.dumps(payload, sort_keys=True), md


def check_files() -> None:
    read(CONTRACT_JSON)
    read(CONTRACT_MD)
    read(REPORT)


def check_statuses(payload: dict, combined: str) -> None:
    statuses = payload.get("status", [])
    require(isinstance(statuses, list), "status must be a list")
    for status in REQUIRED_STATUSES:
        require(status in statuses, "missing JSON status: " + status)
        require_text(combined, status, "status")


def check_classes(payload: dict, combined: str) -> None:
    low_risk = payload.get("preapproved_low_risk_autopilot_classes", [])
    high_risk = payload.get("high_risk_stop_classes", [])
    require(low_risk == LOW_RISK_CLASSES, "low-risk autopilot class list mismatch")
    require(high_risk == HIGH_RISK_STOP_CLASSES, "high-risk stop class list mismatch")
    for item in LOW_RISK_CLASSES:
        require_text(combined, item, "low-risk autopilot class")
    for item in HIGH_RISK_STOP_CLASSES:
        require_text(combined, item, "high-risk stop class")

    details = payload.get("preapproved_low_risk_class_details", {})
    require(isinstance(details, dict), "low-risk class details missing")
    for item in LOW_RISK_CLASSES:
        require(item in details, "missing low-risk class detail: " + item)

    stop_details = payload.get("high_risk_stop_details", {})
    require(isinstance(stop_details, dict), "high-risk stop details missing")
    for item in HIGH_RISK_STOP_CLASSES:
        require(item in stop_details, "missing high-risk stop detail: " + item)


def check_self_fix_flow(payload: dict, combined: str) -> None:
    flow = payload.get("self_fix_flow", [])
    require(flow == SELF_FIX_FLOW, "self-fix flow list mismatch")
    for item in SELF_FIX_FLOW:
        require_text(combined, item, "self-fix flow")

    controls = payload.get("self_fix_flow_controls", {})
    for key in [
        "detect_issue",
        "classify_issue",
        "confirm_class_is_preapproved_low_risk",
        "create_patch_candidate",
        "apply_patch_only_inside_allowed_files_classes",
        "run_targeted_verifier",
        "run_standard_guard_verifiers",
        "create_self_fix_receipt",
        "commit_only_if_verifier_stack_passes",
        "report_what_was_fixed",
        "stop_if_class_unknown",
        "stop_if_high_risk",
        "stop_if_verifier_fails",
    ]:
        require(controls.get(key) is True, "self-fix flow control must be true: " + key)


def check_receipt_fields(payload: dict, combined: str) -> None:
    fields = payload.get("self_fix_receipt_fields", [])
    require(fields == RECEIPT_FIELDS, "self-fix receipt field list mismatch")
    for field in RECEIPT_FIELDS:
        require_text(combined, field, "receipt field")


def check_boundary_denials(payload: dict, combined: str) -> None:
    for phrase in BOUNDARY_PHRASES:
        require_text(combined, phrase, "boundary denial")

    denials = payload.get("self_fix_boundary_denials", {})
    for key in [
        "no_provider_calls",
        "no_network",
        "no_browser_opening",
        "no_model_loading",
        "no_inference",
        "no_trusted_memory_write",
        "no_background_workers",
        "no_autonomous_background_loop",
        "no_startup_mutation",
        "no_route_mutation",
        "no_source_behavior_mutation",
        "no_package_live_app",
        "no_live_exe_promotion",
        "no_file_import",
        "no_file_copy",
        "no_file_move",
        "no_file_sync",
        "no_external_drive_scan",
        "no_unknown_file_deletion",
        "no_authority_hierarchy_bypass",
        "no_prompt_injection_guard_bypass",
        "no_untrusted_content_guard_bypass",
    ]:
        require(denials.get(key) is True, "boundary denial must be true: " + key)

    inactive = payload.get("inactive_behavior_denials", {})
    for key, value in inactive.items():
        require(value is False, "inactive behavior denial must be false: " + key)
    for key in [
        "active_self_fix_runner_exists",
        "autonomous_fix_execution_enabled",
        "provider_calls_enabled",
        "network_enabled",
        "browser_open_enabled",
        "model_loading_enabled",
        "inference_enabled",
        "trusted_memory_write_enabled",
        "background_workers_enabled",
        "autonomous_loop_enabled",
        "startup_mutation_enabled",
        "route_mutation_enabled",
        "source_behavior_mutation_enabled",
        "package_refresh_enabled",
        "live_exe_promotion_enabled",
        "file_import_enabled",
        "file_copy_enabled",
        "file_move_enabled",
        "file_sync_enabled",
        "external_drive_scan_enabled",
        "unknown_file_deletion_enabled",
        "authority_hierarchy_bypass_enabled",
        "prompt_injection_guard_bypass_enabled",
        "untrusted_content_guard_bypass_enabled",
    ]:
        require(key in inactive, "inactive behavior denial missing: " + key)


def check_policy_flags(payload: dict, combined: str) -> None:
    require_text(combined, "Engel should fix itself automatically for pre-approved low-risk maintenance classes, then verify and report.", "core principle")
    scope = payload.get("contract_scope", {})
    for key in [
        "contract_only",
        "planning_only",
        "verifier_step_only",
        "no_active_self_fix_runner_yet",
        "does_not_run_autonomous_fixes",
        "does_not_expand_runtime_authority",
    ]:
        require(scope.get(key) is True, "contract scope flag must be true: " + key)

    policy = payload.get("autopilot_policy", {})
    for key in [
        "future_low_risk_preapproved_fixes_do_not_require_repeated_human_approval",
        "future_preapproved_fix_must_match_exact_class",
        "future_preapproved_fix_must_stay_inside_allowed_files_and_classes",
        "future_preapproved_fix_must_run_targeted_verifier",
        "future_preapproved_fix_must_run_standard_guard_verifiers",
        "future_preapproved_fix_must_create_self_fix_receipt",
        "future_preapproved_fix_must_commit_only_after_verifier_stack_passes",
        "high_risk_changes_always_require_human_approval",
    ]:
        require(policy.get(key) is True, "autopilot policy flag must be true: " + key)


def check_no_active_runner_exists() -> None:
    for path in RUNNER_CANDIDATES:
        require(not path.exists(), "active self-fix runner candidate exists: " + str(path.relative_to(ROOT)))


def check_verifier_ast_safety() -> None:
    source = read(THIS_FILE)
    tree = ast.parse(source)
    allowed_import_roots = {"ast", "json", "pathlib"}
    forbidden_calls = {
        "run",
        "Popen",
        "system",
        "startfile",
        "copytree",
        "move",
        "rglob",
        "glob",
        "urlopen",
        "request",
        "connect",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                require(root in allowed_import_roots, "unexpected verifier import: " + alias.name)
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".", 1)[0]
            require(root in allowed_import_roots or node.module == "__future__", "unexpected verifier import-from: " + str(node.module))
        elif isinstance(node, ast.Call):
            name = ""
            if isinstance(node.func, ast.Name):
                name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                name = node.func.attr
                if name == "walk" and isinstance(node.func.value, ast.Name) and node.func.value.id == "ast":
                    continue
            require(name not in forbidden_calls, "forbidden active call in verifier: " + name)


def main() -> int:
    try:
        check_files()
        payload, payload_text, md = load_contract()
        require(payload.get("schema_name") == "engel_self_fix_autopilot_contract_v1", "schema_name mismatch")
        require(payload.get("schema_version") == "1.0", "schema_version mismatch")
        combined = payload_text + "\n" + md + "\n" + read(REPORT)
        check_statuses(payload, combined)
        check_classes(payload, combined)
        check_self_fix_flow(payload, combined)
        check_receipt_fields(payload, combined)
        check_boundary_denials(payload, combined)
        check_policy_flags(payload, combined)
        check_no_active_runner_exists()
        check_verifier_ast_safety()
    except (CheckFailure, json.JSONDecodeError, SyntaxError) as exc:
        print("FAIL: Engel Self-Fix Autopilot Contract V1 verifier")
        print("- " + str(exc))
        return 1

    print("PASS: Engel Self-Fix Autopilot Contract V1 verifier")
    print("- contract JSON, Markdown, and report exist and parse")
    print("- low-risk preapproved classes and high-risk stop classes are present")
    print("- self-fix flow and receipt fields are present")
    print("- no active self-fix runner or provider/network/browser/model/background-worker behavior is enabled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
