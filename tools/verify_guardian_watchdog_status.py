#!/usr/bin/env python3
"""
Static verifier for ENGEL_GUARDIAN_WATCHDOG_STATUS_TEMPLATE_V1.

This verifier checks a template-only Guardian Watchdog status-state shape
before any UI, runtime, monitor loop, restart, or restore implementation.
It does not import Engel runtime modules, inspect processes, start or stop
Engel, restore files, build, promote, or mutate routes/queues/source.
"""

from __future__ import annotations

import json
import subprocess
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

TEMPLATE_JSON = ROOT / "memory" / "ENGEL_GUARDIAN_WATCHDOG_STATUS_TEMPLATE_V1.json"
CONTRACT_VERIFIER = ROOT / "tools" / "verify_guardian_watchdog_contract.py"
EXPECTED_WORKSPACE = r"D:\b.WorkSpace\Engel App"
EXPECTED_CONTRACT_ID = "ENGEL_GUARDIAN_WATCHDOG_STATUS_TEMPLATE_V1"
CONTRACT_SUCCESS_MARKER = "GUARDIAN_WATCHDOG_CONTRACT_VERIFICATION_PASS"
SUCCESS_MARKER = "GUARDIAN_WATCHDOG_STATUS_VERIFICATION_PASS"

REQUIRED_FIELDS = [
    "watchdog_enabled",
    "watchdog_running",
    "watchdog_mode",
    "engel_status",
    "single_instance_lock_status",
    "last_known_good_backup",
    "last_known_good_hash_status",
    "last_crash_time",
    "last_restore_status",
    "restart_count",
    "restart_limit",
    "last_receipt_path",
    "source_mutation_allowed",
    "trusted_memory_write_allowed",
    "provider_api_allowed",
    "local_llm_inference_allowed",
    "mobile_runtime_allowed",
    "remote_queen_runtime_allowed",
]

FALSE_FLAGS = [
    "watchdog_enabled",
    "watchdog_running",
    "active_runtime_status",
    "restart_enabled",
    "restore_enabled",
    "auto_restart_enabled",
    "auto_restore_enabled",
    "process_monitoring_enabled",
    "process_action_enabled",
    "engel_start_stop_allowed",
    "process_kill_allowed",
    "restore_files_allowed",
    "build_allowed",
    "promote_allowed",
    "source_mutation_allowed",
    "route_mutation_allowed",
    "queue_mutation_allowed",
    "trusted_memory_write_allowed",
    "provider_api_allowed",
    "network_allowed",
    "local_llm_inference_allowed",
    "mobile_runtime_allowed",
    "remote_queen_runtime_allowed",
]

ALLOWED_MODES = [
    "OFF",
    "MONITOR_ONLY",
    "RESTART_ON_CRASH",
    "UPDATE_GUARD",
    "RESTORE_LAST_GOOD",
]


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def pass_line(label: str) -> None:
    print(f"PASS {label}")


def run_contract_verifier() -> None:
    require(CONTRACT_VERIFIER.exists(), f"missing contract verifier: {CONTRACT_VERIFIER}")
    result = subprocess.run(
        [sys.executable, str(CONTRACT_VERIFIER)],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        check=False,
    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if result.stdout:
        for line in result.stdout.splitlines():
            print(f"INFO contract_verifier {line}")
    if result.stderr:
        for line in result.stderr.splitlines():
            print(f"INFO contract_verifier_stderr {line}")
    require(result.returncode == 0, "contract verifier failed")
    require(CONTRACT_SUCCESS_MARKER in result.stdout, "contract verifier success marker missing")
    pass_line("contract_verifier_passes")


def load_template() -> dict[str, object]:
    require(TEMPLATE_JSON.exists(), f"missing status template JSON: {TEMPLATE_JSON}")
    try:
        data = json.loads(TEMPLATE_JSON.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CheckFailure(f"status template JSON does not parse: {exc}") from exc
    require(isinstance(data, dict), "status template root must be an object")
    pass_line("status_template_json_exists_and_parses")
    return data


def check_identity(data: dict[str, object]) -> None:
    require(data.get("contract_id") == EXPECTED_CONTRACT_ID, "status template contract_id mismatch")
    require(data.get("status") == "template_only", "status template must be template_only")
    require(data.get("active_workspace") == EXPECTED_WORKSPACE, "status template active_workspace mismatch")
    require(data.get("template_only") is True, "template_only must be true")
    require(data.get("active_runtime_status") is False, "active_runtime_status must be false")
    pass_line("status_template_identity")


def check_schema(data: dict[str, object]) -> None:
    schema = data.get("schema")
    require(isinstance(schema, dict), "schema must be an object")
    schema_required = schema.get("required_fields")
    require(isinstance(schema_required, list), "schema.required_fields must be a list")
    missing_from_template = [field for field in REQUIRED_FIELDS if field not in data]
    missing_from_schema = [field for field in REQUIRED_FIELDS if field not in schema_required]
    require(not missing_from_template, f"template missing required fields: {missing_from_template}")
    require(not missing_from_schema, f"schema.required_fields missing: {missing_from_schema}")
    allowed_modes = schema.get("allowed_watchdog_modes")
    require(allowed_modes == ALLOWED_MODES, "schema.allowed_watchdog_modes must match Guardian Watchdog modes")
    pass_line("status_template_schema_valid")


def check_defaults(data: dict[str, object]) -> None:
    require(data.get("watchdog_mode") == "OFF", "default watchdog_mode must be OFF")
    require(data.get("engel_status") == "unknown", "default engel_status must be unknown")
    require(data.get("single_instance_lock_status") == "not_created", "default single_instance_lock_status must be not_created")
    require(data.get("last_known_good_hash_status") == "not_checked", "default last_known_good_hash_status must be not_checked")
    require(data.get("last_crash_time") is None, "default last_crash_time must be null")
    require(data.get("last_restore_status") == "disabled", "default last_restore_status must be disabled")
    require(data.get("restart_count") == 0, "default restart_count must be 0")
    require(data.get("restart_limit") == 0, "default restart_limit must be 0")
    require(data.get("last_receipt_path") is None, "default last_receipt_path must be null")
    pass_line("default_mode_off_and_status_values_safe")


def check_last_known_good_backup(data: dict[str, object]) -> None:
    backup = data.get("last_known_good_backup")
    require(isinstance(backup, dict), "last_known_good_backup must be an object")
    require(backup.get("configured") is False, "last_known_good_backup.configured must be false")
    for key in ["baseline_id", "backup_path", "receipt_path"]:
        require(key in backup, f"last_known_good_backup missing {key}")
        require(backup.get(key) is None, f"last_known_good_backup.{key} must be null by default")
    pass_line("last_known_good_backup_default_unconfigured")


def check_disabled_flags(data: dict[str, object]) -> None:
    for key in FALSE_FLAGS:
        require(data.get(key) is False, f"{key} must be false")
    pass_line("no_restart_restore_enabled")
    pass_line("no_process_action_enabled")
    pass_line("no_mutation_provider_network_llm_mobile_remote_queen_enabled")


def check_notes(data: dict[str, object]) -> None:
    notes = data.get("notes")
    require(isinstance(notes, list) and notes, "notes must be a non-empty list")
    combined = "\n".join(str(note) for note in notes)
    for needle in [
        "template-only",
        "not an active runtime status file",
        "No watchdog process",
        "trusted-memory write",
    ]:
        require(needle in combined, f"status template notes missing: {needle}")
    pass_line("template_notes_confirm_no_runtime_status")


def main() -> int:
    print("INFO Guardian Watchdog status verifier")
    print("INFO Mode: template-only, no UI/runtime/process/restore behavior")
    try:
        run_contract_verifier()
        data = load_template()
        check_identity(data)
        check_schema(data)
        check_defaults(data)
        check_last_known_good_backup(data)
        check_disabled_flags(data)
        check_notes(data)
    except CheckFailure as exc:
        print(f"FAIL {exc}")
        return 1

    print(SUCCESS_MARKER)
    return 0


if __name__ == "__main__":
    sys.exit(main())
