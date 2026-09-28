#!/usr/bin/env python3
"""Verify Engel Code Companion Low-Risk Patch Apply Contract V1."""

import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_JSON = ROOT / "memory" / "ENGEL_CODE_COMPANION_LOW_RISK_PATCH_APPLY_CONTRACT_V1.json"
CONTRACT_MD = ROOT / "memory" / "ENGEL_CODE_COMPANION_LOW_RISK_PATCH_APPLY_CONTRACT_V1.md"
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_CODE_COMPANION_LOW_RISK_PATCH_APPLY_CONTRACT_V1.md"

FORBIDDEN_RUNNER_FILES = [
    ROOT / "engel_code_companion_low_risk_patch_apply.py",
    ROOT / "tools" / "engel_code_companion_low_risk_patch_apply.py",
    ROOT / "tools" / "engel_code_companion_low_risk_patch_runner.py",
]

SEPARATE_RUNNER_FILES = [
    ROOT / "engel_code_companion_low_risk_patch_runner.py",
    ROOT / "tools" / "verify_engel_code_companion_low_risk_patch_runner.py",
    ROOT / "reports" / "codex_bridge" / "ENGEL_CODE_COMPANION_LOW_RISK_PATCH_RUNNER_V1.md",
]

REQUIRED_STATUSES = [
    "CONTRACT_ONLY",
    "CODE_COMPANION_LOW_RISK_PATCH_POLICY",
    "PATCH_RUNNER_NOT_IMPLEMENTED",
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

ALLOWED_CLASSES = [
    "report_hash_refresh",
    "codex_bridge_report_reference_update",
    "read_only_status_surface_label_fix",
    "verifier_expectation_update_for_existing_committed_contract",
    "core_continuity_report_only_index_update",
    "documentation_typo_or_label_fix",
    "generated_report_metadata_update",
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
]

REQUIRED_FLOW = [
    "read patch candidate",
    "classify risk",
    "confirm allowed low-risk patch class",
    "prepare patch plan",
    "apply only bounded low-risk patch",
    "run verifier plan",
    "run guard verifiers",
    "create patch receipt",
    "commit only if all verification passes",
    "stop on unclear/high risk",
]

REQUIRED_RECEIPT_FIELDS = [
    "code_companion_patch_apply_run_id",
    "source_patch_candidate_id",
    "source_patch_candidate_path",
    "risk_classification",
    "allowed_low_risk_patch_class",
    "files_changed",
    "patch_summary",
    "verifier_plan_path",
    "verification_commands",
    "verification_result",
    "guard_verifier_result",
    "focused_safety_scan_result",
    "final_process_sweep_result",
    "git_status_summary",
    "commit_hash",
    "rollback_notes",
    "stopped",
    "stop_reason",
    "human_intervention_required",
]

REQUIRED_BOUNDARY_KEYS = [
    "contract_only",
    "patch_runner_not_implemented",
    "does_not_apply_patches",
    "does_not_mutate_source",
    "does_not_commit",
    "does_not_execute_verifiers",
    "does_not_write_trusted_memory",
    "does_not_call_providers",
    "does_not_use_network",
    "does_not_open_browser",
    "does_not_start_model_runtime",
    "does_not_refresh_packages",
    "does_not_mutate_routes_or_startup",
    "does_not_start_background_worker",
    "preapproved_low_risk_patches_only",
    "verify_before_commit_required",
    "receipt_required",
    "stop_on_high_or_unclear_risk",
]

FORBIDDEN_ACTIVE_PATTERNS = [
    r"(?m)^\s*import\s+(requests|urllib|socket|webbrowser|openai|subprocess|glob|shutil|threading|multiprocessing)\b",
    r"(?m)^\s*from\s+(requests|urllib|socket|webbrowser|openai|subprocess|glob|shutil|threading|multiprocessing)\b",
    r"(?m)^\s*def\s+.*(apply|patch|commit|execute|run_verifier|refresh|promote|worker)",
    r"(?m)^\s*class\s+.*(Runner|Apply|Patch)",
    r"\bsubprocess\.",
    r"\brequests\.",
    r"\bwebbrowser\.",
    r"\bsocket\.",
    r"\bopenai\.",
    r"\beval\s*\(",
    r"\bexec\s*\(",
]


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read(path: Path) -> str:
    require(path.exists(), "missing required file: " + str(path))
    return path.read_text(encoding="utf-8", errors="replace")


def check_files() -> None:
    for path in [CONTRACT_JSON, CONTRACT_MD, REPORT]:
        require(path.exists(), "missing required file: " + str(path))
        require(path.is_file(), "required path is not a file: " + str(path))


def check_json() -> None:
    data = json.loads(read(CONTRACT_JSON))
    require(data.get("type") == "code_companion_low_risk_patch_apply_contract", "contract JSON type mismatch")
    require(data.get("authority") == "Josh > Guardian > Engel/runtime", "contract JSON authority mismatch")
    for status in REQUIRED_STATUSES:
        require(status in data.get("status", []), "contract JSON missing status: " + status)
    for class_name in ALLOWED_CLASSES:
        require(class_name in data.get("allowed_future_low_risk_patch_classes", []), "contract JSON missing allowed class: " + class_name)
    for class_name in HIGH_RISK_STOP_CLASSES:
        require(class_name in data.get("high_risk_stop_classes", []), "contract JSON missing high-risk stop class: " + class_name)
    for step in REQUIRED_FLOW:
        require(step in data.get("required_patch_flow", []), "contract JSON missing flow step: " + step)
    for field in REQUIRED_RECEIPT_FIELDS:
        require(field in data.get("required_receipt_fields", []), "contract JSON missing receipt field: " + field)
    boundaries = data.get("boundaries", {})
    for key in REQUIRED_BOUNDARY_KEYS:
        require(boundaries.get(key) is True, "contract JSON boundary missing/false: " + key)


def check_text() -> None:
    text = read(CONTRACT_MD) + "\n" + read(REPORT)
    for status in REQUIRED_STATUSES:
        require(status in text, "contract markdown/report missing status: " + status)
    for class_name in ALLOWED_CLASSES:
        require(class_name in text, "contract markdown/report missing allowed class: " + class_name)
    for class_name in HIGH_RISK_STOP_CLASSES:
        require(class_name in text, "contract markdown/report missing high-risk stop class: " + class_name)
    for step in REQUIRED_FLOW:
        require(step in text, "contract markdown/report missing flow step: " + step)
    for field in REQUIRED_RECEIPT_FIELDS:
        require(field in text, "contract markdown/report missing receipt field: " + field)
    for phrase in [
        "contract-only",
        "No patch runner is implemented",
        "No patch is applied",
        "No source is mutated",
        "No verifier is executed",
        "No commit",
        "trusted-memory write",
        "Josh > Guardian > Engel/runtime",
    ]:
        require(phrase in text, "contract markdown/report missing boundary phrase: " + phrase)


def check_no_runner_implementation() -> None:
    for path in FORBIDDEN_RUNNER_FILES:
        require(not path.exists(), "unexpected patch runner implementation file exists: " + str(path))
    for path in [CONTRACT_JSON, CONTRACT_MD, REPORT]:
        text = read(path)
        for pattern in FORBIDDEN_ACTIVE_PATTERNS:
            require(not re.search(pattern, text), "contract/report contains active forbidden pattern: " + pattern)


def check_separate_runner_if_present() -> None:
    runner_path = SEPARATE_RUNNER_FILES[0]
    if not runner_path.exists():
        return
    for path in SEPARATE_RUNNER_FILES:
        require(path.exists(), "separate runner artifact missing: " + str(path))
        require(path.is_file(), "separate runner artifact is not a file: " + str(path))
    runner_text = read(runner_path)
    for phrase in [
        "CODE_COMPANION_LOW_RISK_PATCH_RUNNER",
        "EXPLICIT_PATCH_CANDIDATE_REQUIRED",
        "PREAPPROVED_LOW_RISK_PATCHES_ONLY",
        "NO_COMMIT_AUTOMATION",
        "NO_PROVIDER_CALLS",
        "NO_NETWORK",
        "NO_BROWSER",
        "NO_MODEL_RUNTIME",
        "NO_TRUSTED_MEMORY_WRITE",
        "NO_PACKAGE_REFRESH",
        "NO_ROUTE_STARTUP_MUTATION",
        "NO_BACKGROUND_WORKER",
    ]:
        require(phrase in runner_text, "separate runner missing safety phrase: " + phrase)


def main() -> int:
    try:
        check_files()
        check_json()
        check_text()
        check_no_runner_implementation()
        check_separate_runner_if_present()
    except CheckFailure as exc:
        print("FAIL: " + str(exc))
        return 1
    print("OK: Engel Code Companion Low-Risk Patch Apply Contract V1 verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
