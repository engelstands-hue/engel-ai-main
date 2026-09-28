#!/usr/bin/env python3
"""
Static verifier for ENGEL_GUARDIAN_WATCHDOG_AGENT_CONTRACT_V1.

This verifier is contract-only. It reads JSON/markdown contract files and
does not import Engel runtime modules, start watchdogs, inspect live
processes, restore files, build, promote, or mutate routes/queues/source.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


_FILE = globals().get("__file__")
if not _FILE or not isinstance(_FILE, str) or _FILE.startswith("<"):
    ROOT = Path.cwd()
else:
    try:
        ROOT = Path(_FILE).resolve().parents[1]
    except (OSError, ValueError, IndexError):
        ROOT = Path.cwd()

CONTRACT_JSON = ROOT / "memory" / "ENGEL_GUARDIAN_WATCHDOG_AGENT_CONTRACT_V1.json"
CONTRACT_MD = ROOT / "memory" / "ENGEL_GUARDIAN_WATCHDOG_AGENT_CONTRACT_V1.md"
EXPECTED_WORKSPACE = r"D:\b.WorkSpace\Engel App"
EXPECTED_CONTRACT_ID = "ENGEL_GUARDIAN_WATCHDOG_AGENT_CONTRACT_V1"
SUCCESS_MARKER = "GUARDIAN_WATCHDOG_CONTRACT_VERIFICATION_PASS"

REQUIRED_MODES = [
    "OFF",
    "MONITOR_ONLY",
    "RESTART_ON_CRASH",
    "UPDATE_GUARD",
    "RESTORE_LAST_GOOD",
]

FALSE_FLAGS = [
    "watchdog_enabled_now",
    "watchdog_running_now",
    "auto_restart_enabled_now",
    "auto_restore_enabled_now",
    "trusted_memory_write_allowed",
    "source_mutation_allowed",
    "route_mutation_allowed",
    "queue_mutation_allowed",
    "provider_api_allowed",
    "network_allowed",
    "local_llm_inference_allowed",
    "mobile_runtime_allowed",
    "remote_queen_runtime_allowed",
    "build_allowed_now",
    "promote_allowed_now",
    "service_or_scheduler_creation_allowed_now",
    "process_kill_allowed_now",
    "engel_start_stop_allowed_now",
    "restore_files_allowed_now",
]

TRUE_FLAGS = [
    "automatic_restore_requires_future_verified_configuration",
    "single_instance_required",
    "restart_loop_limit_required",
    "failed_update_quarantine_required_before_restore",
]

REQUIRED_UI_FIELDS = [
    "watchdog_state",
    "target",
    "health",
    "last_heartbeat_time",
    "last_crash_receipt",
    "last_update_receipt",
    "restart_attempts_in_current_window",
    "last_known_good_baseline_id",
    "restore_eligibility",
]

REQUIRED_LAST_KNOWN_GOOD_KEYS = [
    "baseline_id_required",
    "target_path_required",
    "sha256_required",
    "file_size_required",
    "build_or_promotion_receipt_reference_required",
    "smoke_or_verifier_receipt_reference_required",
    "backup_folder_reference_required",
    "restore_allowlist_required",
    "verifier_pass_required",
]

REQUIRED_CRASH_RECEIPT_FIELDS = [
    "receipt_id",
    "timestamp",
    "mode",
    "target_path",
    "event_type",
    "action_taken",
    "action_refused_reason",
    "safety_flags",
]

REQUIRED_RESTORE_RULE_KEYS = [
    "restore_disabled_now",
    "future_verified_configuration_required",
    "failed_update_quarantine_required",
    "last_known_good_metadata_required",
    "restore_target_allowlist_required",
    "dry_run_preview_required",
    "failed_files_preserved_before_replace",
    "receipt_required",
    "restore_loop_prevention_required",
    "build_or_promote_forbidden",
]

REQUIRED_RESTART_LIMIT_KEYS = [
    "required",
    "max_restart_attempts_per_window_required",
    "cooldown_required",
    "max_consecutive_failed_restarts_required",
    "receipt_per_attempt_required",
]


class CheckFailure(Exception):
    pass


def fail(message: str) -> None:
    raise CheckFailure(message)


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def pass_line(label: str) -> None:
    print(f"PASS {label}")


def load_contract() -> dict[str, object]:
    require(CONTRACT_JSON.exists(), f"missing contract JSON: {CONTRACT_JSON}")
    try:
        data = json.loads(CONTRACT_JSON.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"contract JSON does not parse: {exc}")
    require(isinstance(data, dict), "contract JSON root must be an object")
    pass_line("contract_json_exists_and_parses")
    return data


def check_markdown_exists() -> None:
    require(CONTRACT_MD.exists(), f"missing contract markdown: {CONTRACT_MD}")
    text = CONTRACT_MD.read_text(encoding="utf-8", errors="replace")
    for needle in [
        "OFF",
        "MONITOR_ONLY",
        "RESTART_ON_CRASH",
        "UPDATE_GUARD",
        "RESTORE_LAST_GOOD",
        "Small UI / Status Design",
        "Last-Known-Good Model",
        "Crash Detection Model",
        "Crash Receipt Model",
        "Restore Rules",
    ]:
        require(needle in text, f"contract markdown missing: {needle}")
    pass_line("contract_markdown_exists_and_documents_watchdog_model")


def check_identity(data: dict[str, object]) -> None:
    expected = {
        "contract_id": EXPECTED_CONTRACT_ID,
        "status": "contract_only",
        "active_workspace": EXPECTED_WORKSPACE,
    }
    for key, value in expected.items():
        require(data.get(key) == value, f"{key} must be {value!r}")
    pass_line("contract_identity")


def check_current_disabled_flags(data: dict[str, object]) -> None:
    for key in FALSE_FLAGS:
        require(data.get(key) is False, f"{key} must be false")
    for key in TRUE_FLAGS:
        require(data.get(key) is True, f"{key} must be true")
    pass_line("current_watchdog_restart_restore_permissions_disabled")
    pass_line("mutation_provider_network_llm_mobile_remote_queen_permissions_false")


def check_modes(data: dict[str, object]) -> None:
    modes = data.get("modes")
    require(isinstance(modes, list), "modes must be a list")
    require(modes, "modes must not be empty")
    by_name: dict[str, dict[str, object]] = {}
    for item in modes:
        require(isinstance(item, dict), "each mode entry must be an object")
        mode_name = item.get("mode")
        require(isinstance(mode_name, str), "each mode entry must have a string mode")
        by_name[mode_name] = item
    missing = [mode for mode in REQUIRED_MODES if mode not in by_name]
    extra = sorted(set(by_name) - set(REQUIRED_MODES))
    require(not missing, f"missing modes: {missing}")
    require(not extra, f"unexpected modes present: {extra}")
    require(by_name["OFF"].get("enabled_now") is True, "OFF mode must be enabled_now true")
    for mode in REQUIRED_MODES:
        if mode == "OFF":
            continue
        entry = by_name[mode]
        require(entry.get("enabled_now") is False, f"{mode} must be enabled_now false")
        require(
            isinstance(entry.get("future_behavior"), str) and entry.get("future_behavior"),
            f"{mode} must document future_behavior",
        )
    pass_line("allowed_modes_exist")
    pass_line("forbidden_modes_disabled_and_no_unknown_modes")


def check_mode_rules(data: dict[str, object]) -> None:
    rules = data.get("mode_configuration_rules")
    require(isinstance(rules, list) and rules, "mode_configuration_rules must be a non-empty list")
    combined = "\n".join(str(rule) for rule in rules)
    for needle in [
        "configuration states, not human approval levels",
        "Default mode is OFF",
        "RESTART_ON_CRASH",
        "RESTORE_LAST_GOOD",
        "No mode grants trusted-memory",
    ]:
        require(needle in combined, f"mode configuration rules missing: {needle}")
    pass_line("mode_configuration_rules_exist")


def check_ui(data: dict[str, object]) -> None:
    ui = data.get("small_ui_status_design")
    require(isinstance(ui, dict), "small_ui_status_design must be an object")
    fields = ui.get("fields")
    require(isinstance(fields, list), "small_ui_status_design.fields must be a list")
    missing = [field for field in REQUIRED_UI_FIELDS if field not in fields]
    require(not missing, f"missing UI fields: {missing}")
    forbidden_controls = ui.get("forbidden_first_version_controls")
    require(
        isinstance(forbidden_controls, list) and "restore" in forbidden_controls and "local_llm" in forbidden_controls,
        "small UI forbidden controls must include restore and local_llm",
    )
    require(ui.get("first_version_controls") == "status_only", "first UI version must be status_only")
    pass_line("ui_fields_exist")


def check_last_known_good(data: dict[str, object]) -> None:
    model = data.get("last_known_good_model")
    require(isinstance(model, dict), "last_known_good_model must be an object")
    for key in REQUIRED_LAST_KNOWN_GOOD_KEYS:
        require(model.get(key) is True, f"last_known_good_model.{key} must be true")
    pass_line("last_known_good_schema_exists")


def check_crash_detection(data: dict[str, object]) -> None:
    model = data.get("crash_detection_model")
    require(isinstance(model, dict), "crash_detection_model must be an object")
    signals = model.get("future_signals")
    forbidden = model.get("forbidden_detection_behaviors")
    require(isinstance(signals, list) and len(signals) >= 3, "crash_detection_model.future_signals incomplete")
    require(isinstance(forbidden, list), "crash_detection_model.forbidden_detection_behaviors must be a list")
    for item in ["provider_calls", "network_calls", "local_llm_inference", "process_kill"]:
        require(item in forbidden, f"crash detection forbidden behavior missing: {item}")
    pass_line("crash_detection_schema_exists")


def check_crash_receipt(data: dict[str, object]) -> None:
    receipt = data.get("crash_receipt_model")
    require(isinstance(receipt, dict), "crash_receipt_model must be an object")
    locations = receipt.get("future_locations")
    formats = receipt.get("formats")
    fields = receipt.get("required_fields")
    require(isinstance(locations, list) and locations, "crash receipt future_locations must be non-empty")
    require(isinstance(formats, list) and ".md" in formats and ".json" in formats, "crash receipts must allow .md and .json")
    require(isinstance(fields, list), "crash receipt required_fields must be a list")
    missing = [field for field in REQUIRED_CRASH_RECEIPT_FIELDS if field not in fields]
    require(not missing, f"missing crash receipt required fields: {missing}")
    require(receipt.get("not_trusted_memory") is True, "crash receipts must be not_trusted_memory")
    require(
        receipt.get("does_not_authorize_restore_or_promotion") is True,
        "crash receipts must not authorize restore or promotion",
    )
    pass_line("crash_receipt_schema_exists")


def check_restart_loop_limits(data: dict[str, object]) -> None:
    limits = data.get("restart_loop_limits")
    require(isinstance(limits, dict), "restart_loop_limits must be an object")
    for key in REQUIRED_RESTART_LIMIT_KEYS:
        require(limits.get(key) is True, f"restart_loop_limits.{key} must be true")
    require(limits.get("fallback_mode_after_limit") == "MONITOR_ONLY", "restart fallback mode must be MONITOR_ONLY")
    pass_line("restart_loop_limits_exist")


def check_restore_rules(data: dict[str, object]) -> None:
    rules = data.get("restore_rules")
    require(isinstance(rules, dict), "restore_rules must be an object")
    for key in REQUIRED_RESTORE_RULE_KEYS:
        require(rules.get(key) is True, f"restore_rules.{key} must be true")
    quarantine = data.get("failed_update_quarantine")
    require(isinstance(quarantine, dict), "failed_update_quarantine must be an object")
    require(quarantine.get("required_before_restore") is True, "failed_update_quarantine.required_before_restore must be true")
    pass_line("restore_rules_exist")
    pass_line("failed_update_quarantine_before_restore_exists")


def check_future_sequence(data: dict[str, object]) -> None:
    sequence = data.get("future_implementation_sequence")
    require(isinstance(sequence, list) and sequence, "future_implementation_sequence must be a non-empty list")
    require(
        sequence[0] == "ENGEL_GUARDIAN_WATCHDOG_CONTRACT_VERIFIER_V1",
        "future implementation sequence must start with contract verifier",
    )
    for item in [
        "ENGEL_GUARDIAN_WATCHDOG_STATUS_MODEL_V1",
        "ENGEL_GUARDIAN_WATCHDOG_UI_STATUS_V1",
        "ENGEL_GUARDIAN_WATCHDOG_MONITOR_ONLY_V1",
        "ENGEL_GUARDIAN_WATCHDOG_RESTORE_CONTRACT_V1",
    ]:
        require(item in sequence, f"future implementation sequence missing: {item}")
    require(
        data.get("recommended_next_slice") == "ENGEL_GUARDIAN_WATCHDOG_CONTRACT_VERIFIER_V1",
        "recommended_next_slice must point to this verifier slice",
    )
    pass_line("future_implementation_sequence_exists")


def check_safety_preserved(data: dict[str, object]) -> None:
    safety = data.get("safety_preserved")
    require(isinstance(safety, dict), "safety_preserved must be an object")
    for key, value in safety.items():
        require(value is False, f"safety_preserved.{key} must be false")
    pass_line("safety_preserved_records_no_runtime_or_mutation")


def main() -> int:
    print("INFO Guardian Watchdog contract verifier")
    print("INFO Mode: contract-only, read-only source check")
    try:
        data = load_contract()
        check_markdown_exists()
        check_identity(data)
        check_current_disabled_flags(data)
        check_modes(data)
        check_mode_rules(data)
        check_ui(data)
        check_last_known_good(data)
        check_crash_detection(data)
        check_crash_receipt(data)
        check_restart_loop_limits(data)
        check_restore_rules(data)
        check_future_sequence(data)
        check_safety_preserved(data)
    except CheckFailure as exc:
        print(f"FAIL {exc}")
        return 1

    print(SUCCESS_MARKER)
    return 0


if __name__ == "__main__":
    sys.exit(main())
