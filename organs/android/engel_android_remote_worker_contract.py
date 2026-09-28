from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import textwrap

from engel_branding import ENGEL_COMMUNICATION_ROUTER_NAME, is_engel_communication_router_name


ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
PLAN_PATH = ROOT / "memory" / "ENGEL_ANDROID_REMOTE_WORKER_PLAN_V1.json"

REQUIRED_TOP_LEVEL_FIELDS = [
    "plan_name",
    "schema_version",
    "purpose",
    "role",
    "device_type",
    "controlled_by",
    "routing_owner",
    "not_a_queen",
    "status",
    "communication_flow",
    "safety_boundaries",
    "allowed_task_types",
    "forbidden_task_types",
    "connection_phases",
    "task_packet_schema",
    "report_packet_schema",
    "approval_requirements",
    "verification_requirements",
    "android_ui_concept",
    "manual_controls",
    "safety_ui_text",
    "future_phases",
    "limitations",
]

REQUIRED_TASK_PACKET_FIELDS = [
    "packet_id",
    "created_at",
    "created_by",
    "routing_owner",
    "target_worker_id",
    "worker_type",
    "task_type",
    "title",
    "instructions",
    "input_text",
    "safety_level",
    "approval_token_required",
    "expires_at",
    "forbidden_actions",
    "expected_report_fields",
]

REQUIRED_REPORT_PACKET_FIELDS = [
    "packet_id",
    "task_packet_id",
    "from_worker_id",
    "to",
    "completed_at",
    "status",
    "summary",
    "result_text",
    "warnings",
    "errors",
    "actions_taken",
    "actions_refused",
    "needs_engel_verification",
    "trusted_memory_write_requested",
    "queen_behavior_requested",
]

FORBIDDEN_BEHAVIOR_NOTES = [
    "phone connection",
    "socket",
    "API calls",
    "provider calls",
    "browser/network",
    "background workers",
    "queue mutation",
    "route mutation",
    "memory mutation",
    "source mutation",
    "trusted memory write",
    "fake live connection data",
]


class ContractError(Exception):
    pass


def load_plan() -> dict[str, object]:
    try:
        data = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ContractError("Android Remote Worker plan file could not be read.") from exc
    except json.JSONDecodeError as exc:
        raise ContractError("Android Remote Worker plan JSON is invalid.") from exc
    if not isinstance(data, dict):
        raise ContractError("Android Remote Worker plan must be a JSON object.")
    return data


def validate_plan(data: dict[str, object]) -> list[str]:
    errors: list[str] = []
    for field in REQUIRED_TOP_LEVEL_FIELDS:
        if field not in data:
            errors.append("missing top-level field: " + field)
    if data.get("role") != "remote_worker":
        errors.append("role must be remote_worker")
    if data.get("device_type") != "android_phone":
        errors.append("device_type must be android_phone")
    if not is_engel_communication_router_name(data.get("controlled_by")):
        errors.append("controlled_by must be Engel Communication Router")
    if not is_engel_communication_router_name(data.get("routing_owner")):
        errors.append("routing_owner must be Engel Communication Router")
    if data.get("not_a_queen") is not True:
        errors.append("not_a_queen must be true")
    if data.get("status") != "scaffold-only":
        errors.append("status must be scaffold-only")

    task_schema = data.get("task_packet_schema")
    if not isinstance(task_schema, dict):
        errors.append("task_packet_schema must be an object")
    else:
        fields = task_schema.get("required_fields")
        fixed = task_schema.get("fixed_values")
        if not isinstance(fields, list):
            errors.append("task_packet_schema.required_fields must be a list")
        else:
            for field in REQUIRED_TASK_PACKET_FIELDS:
                if field not in fields:
                    errors.append("task packet missing field: " + field)
        if not isinstance(fixed, dict):
            errors.append("task_packet_schema.fixed_values must be an object")
        else:
            if not is_engel_communication_router_name(fixed.get("created_by")):
                errors.append("task packet created_by must be Engel Communication Router")
            if not is_engel_communication_router_name(fixed.get("routing_owner")):
                errors.append("task packet routing_owner must be Engel Communication Router")
            if fixed.get("worker_type") != "android_remote_worker":
                errors.append("task packet worker_type must be android_remote_worker")

    report_schema = data.get("report_packet_schema")
    if not isinstance(report_schema, dict):
        errors.append("report_packet_schema must be an object")
    else:
        fields = report_schema.get("required_fields")
        fixed = report_schema.get("fixed_values")
        if not isinstance(fields, list):
            errors.append("report_packet_schema.required_fields must be a list")
        else:
            for field in REQUIRED_REPORT_PACKET_FIELDS:
                if field not in fields:
                    errors.append("report packet missing field: " + field)
        if not isinstance(fixed, dict):
            errors.append("report_packet_schema.fixed_values must be an object")
        else:
            if not is_engel_communication_router_name(fixed.get("to")):
                errors.append("report packet destination must be Engel Communication Router")
            if fixed.get("needs_engel_verification") is not True:
                errors.append("report packet must require Engel verification")
            if fixed.get("trusted_memory_write_requested") is not False:
                errors.append("report packet must not request trusted memory writes")
            if fixed.get("queen_behavior_requested") is not False:
                errors.append("report packet must not request Queen behavior")

    boundaries = data.get("safety_boundaries")
    if not isinstance(boundaries, dict):
        errors.append("safety_boundaries must be an object")
    else:
        for key in [
            "phone_is_not_a_queen",
            "communication_queen_controls_routing",
            "no_direct_core_access",
            "worker_output_untrusted_until_verified",
            "engel_verification_required",
            "human_approval_required",
            "no_runtime_phone_connection",
            "no_network_runtime",
            "no_background_worker",
            "no_autonomy",
            "no_queue_mutation",
            "no_route_mutation",
            "no_source_mutation",
            "no_trusted_memory_write",
            "no_fake_live_android_connection",
        ]:
            if boundaries.get(key) is not True:
                errors.append("safety boundary must be true: " + key)
    return errors


def status_summary(data: dict[str, object]) -> str:
    statuses = data.get("status_labels", [])
    if not isinstance(statuses, list):
        statuses = []
    phases = data.get("connection_phases", [])
    phase_one = "Only Phase 1 is implemented now."
    if isinstance(phases, list):
        for phase in phases:
            if isinstance(phase, dict) and phase.get("phase") == 1 and phase.get("implemented_now") is True:
                phase_one = "Phase 1 scaffold is implemented; runtime phone connection is not implemented."
    return textwrap.dedent(
        f"""
        Engel Android Remote Worker Plan V1

        Role: {data.get('role')}
        Device type: {data.get('device_type')}
        Controlled by: {data.get('controlled_by')}
        Routing owner: {data.get('routing_owner')}
        Not a Queen: {data.get('not_a_queen')}
        Status: {data.get('status')}

        {phase_one}

        Status labels:
        {chr(10).join('- ' + str(label) for label in statuses)}

        Boundary:
        - Android Remote Worker cannot command Engel Core directly.
        - All messages route through {ENGEL_COMMUNICATION_ROUTER_NAME}.
        - Worker reports are untrusted until Engel verification and human approval.
        - No runtime phone connection, network runtime, background worker, autonomy, queue mutation, route mutation, source mutation, or trusted-memory write is enabled.
        """
    ).strip() + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only Android Remote Worker contract status.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--status", action="store_true", help="Print safe contract status.")
    mode.add_argument("--validate", action="store_true", help="Validate the contract.")
    mode.add_argument("--json", action="store_true", help="Print contract JSON.")
    return parser


def main(argv: list[str] | None = None, stdout=None, stderr=None) -> int:
    out = stdout if stdout is not None else sys.stdout
    err = stderr if stderr is not None else sys.stderr
    args = build_parser().parse_args(argv)
    try:
        data = load_plan()
    except ContractError as exc:
        err.write(str(exc) + "\n")
        return 1
    errors = validate_plan(data)
    if args.json:
        out.write(json.dumps(data, indent=2, sort_keys=True) + "\n")
        return 0 if not errors else 1
    if args.validate:
        if errors:
            out.write("Android Remote Worker contract validation FAILED\n")
            for error in errors:
                out.write("- " + error + "\n")
            return 1
        out.write("Android Remote Worker contract validation PASSED\n")
        return 0
    out.write(status_summary(data))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
