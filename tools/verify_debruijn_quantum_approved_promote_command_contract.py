#!/usr/bin/env python3
"""Verify ENGEL_DEBRUIJN_QUANTUM_APPROVED_PROMOTE_COMMAND_CONTRACT_V1.

Mode: static contract validation. No runtime, apply, build, promote, route addition,
provider/model/network, or any source/route/queue/trusted-memory mutation.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_TEXT = r"D:\b.WorkSpace\Engel App"

CONTRACT_ID = "ENGEL_DEBRUIJN_QUANTUM_APPROVED_PROMOTE_COMMAND_CONTRACT_V1"
CONTRACT_JSON = ROOT / "memory" / f"{CONTRACT_ID}.json"
CONTRACT_MD = ROOT / "memory" / f"{CONTRACT_ID}.md"
ENGEL_APP = ROOT / "engel_app.py"

PASS_MARKER = "DEBRUIJN_QUANTUM_APPROVED_PROMOTE_COMMAND_CONTRACT_VERIFICATION_PASS"

EXPECTED_COMMAND_NAME = "engel ai debruijn quantum promote"
EXPECTED_APPROVAL_PHRASE = "APPROVE_DEBRUIJN_QUANTUM_GRAPH_PROMOTE_V1"
EXPECTED_EXACT_COMMAND = (
    "engel ai debruijn quantum promote "
    "APPROVE_DEBRUIJN_QUANTUM_GRAPH_PROMOTE_V1 build_receipt=<receipt_path>"
)

FALSE_FLAGS = [
    "command_route_added_now",
    "approved_promote_command_enabled_now",
    "actual_promote_enabled_now",
    "live_write_enabled_now",
    "dist_write_enabled_now",
    "backup_write_enabled_now",
    "build_execution_enabled_now",
    "pyinstaller_enabled_now",
    "git_stage_commit_enabled_now",
    "source_mutation_enabled_now",
    "route_mutation_enabled_now",
    "queue_mutation_enabled_now",
    "trusted_memory_write_enabled_now",
    "memory_promotion_enabled_now",
    "provider_api_enabled_now",
    "network_enabled_now",
    "local_llm_inference_enabled_now",
    "background_worker_enabled_now",
    "autorun_enabled_now",
    "scheduler_enabled_now",
    "startup_hook_enabled_now",
]

REQUIRED_INPUT_REQUIREMENT_KEYS = [
    "must_reference_valid_build_receipt",
    "build_receipt_must_be_inside_workspace",
    "build_receipt_must_be_json_under_reports_debruijn_quantum_build_receipts",
    "build_receipt_must_have_engine_id_debruijn_quantum_build_promote_engine",
    "build_receipt_must_have_human_review_required_true",
    "build_receipt_must_not_contain_password_or_salt_or_hash_or_token_values",
    "live_target_must_be_pre_declared_in_promote_lane_contract",
    "backup_plan_must_be_pre_declared_in_promote_lane_contract",
    "staged_artifact_must_exist_before_live_promote",
    "live_smoke_must_be_pre_declared_in_promote_lane_contract",
]

REQUIRED_GATE_TERMS = [
    "approved promote command contract exists",
    "approved promote command verifier passes",
    "build/promote engine verifier passes",
    "Global Password Gate verifier passes",
    "verifier timeout lane classification contract verifier passes",
    "exact approval phrase present",
    "build_receipt path inside workspace",
    "no unsafe dirty files",
    "no staged unapproved files",
]

REQUIRED_RECEIPT_FIELDS = [
    "receipt_id",
    "engine_id",
    "lane_id",
    "action_type",
    "started_at",
    "ended_at",
    "input_build_receipt_path",
    "build_receipt_engine_id",
    "build_receipt_final_status",
    "approval_detected",
    "approval_phrase_name",
    "password_gate_result",
    "backup_paths",
    "promoted_artifact_paths",
    "live_smoke_result",
    "final_verifier_results",
    "timeout_lane_classification",
    "files_changed",
    "forbidden_actions_not_performed",
    "final_status",
    "human_review_required",
]

REQUIRED_MUST_NEVER_CONTAIN = [
    "raw password",
    "password hash",
    "password salt",
    "token/secret values",
    "unredacted secret-like config",
]

REQUIRED_FORBIDDEN_TERMS = [
    "actual promote in this slice",
    "any live write",
    "any backup write",
    "PyInstaller execution",
    "arbitrary command execution",
    "provider/network/model/local LLM",
    "package install",
    "trusted-memory write",
    "memory promotion",
    "promote without approval phrase",
    "promote without password gate",
    "local password config commit",
    "broad git staging",
]


class Check:
    def __init__(self) -> None:
        self.failures: list[str] = []

    def _emit(self, level: str, msg: str) -> None:
        safe = msg.encode("ascii", "backslashreplace").decode("ascii")
        print(f"{level} {safe}", flush=True)

    def pass_(self, msg: str) -> None:
        self._emit("PASS", msg)

    def info(self, msg: str) -> None:
        self._emit("INFO", msg)

    def fail(self, msg: str) -> None:
        self.failures.append(msg)
        self._emit("FAIL", msg)


def normalize(text: str) -> str:
    return " ".join(text.lower().replace("\\", " ").split())


def has_phrase(blob: str, phrase: str) -> bool:
    return normalize(phrase) in blob


def check_workspace(check: Check) -> bool:
    if ROOT.resolve(strict=False) != Path(WORKSPACE_TEXT).resolve(strict=False):
        check.fail(f"verifier must run inside {WORKSPACE_TEXT}; got {ROOT}")
        return False
    check.pass_(f"workspace root matches {WORKSPACE_TEXT}")
    return True


def check_files(check: Check) -> dict[str, Any] | None:
    if not CONTRACT_JSON.exists():
        check.fail(f"contract JSON missing: {CONTRACT_JSON}")
        return None
    check.pass_("contract JSON present")
    if not CONTRACT_MD.exists():
        check.fail(f"contract MD missing: {CONTRACT_MD}")
        return None
    check.pass_("contract MD present")
    try:
        data = json.loads(CONTRACT_JSON.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        check.fail(f"contract JSON parse failed: {exc}")
        return None
    if not isinstance(data, dict):
        check.fail("contract JSON top-level value must be an object")
        return None
    check.pass_("contract JSON parsed")
    return data


def check_identity(check: Check, data: dict[str, Any]) -> None:
    if data.get("contract_id") != CONTRACT_ID:
        check.fail(f"contract_id mismatch: {data.get('contract_id')}")
        return
    if data.get("status") != "contract_only":
        check.fail("status must be 'contract_only'")
        return
    if data.get("active_workspace") != WORKSPACE_TEXT:
        check.fail("active_workspace mismatch")
        return
    if data.get("command_name") != EXPECTED_COMMAND_NAME:
        check.fail(f"command_name expected {EXPECTED_COMMAND_NAME!r}")
        return
    if data.get("approval_phrase") != EXPECTED_APPROVAL_PHRASE:
        check.fail(f"approval_phrase expected {EXPECTED_APPROVAL_PHRASE!r}")
        return
    check.pass_("identity fields match contract")


def check_flags(check: Check, data: dict[str, Any]) -> None:
    flags = data.get("current_enabled_flags")
    if not isinstance(flags, dict):
        check.fail("current_enabled_flags must be an object")
        return
    for flag in FALSE_FLAGS:
        if flags.get(flag) is not False:
            check.fail(f"current_enabled_flags.{flag} must be false")
            return
    check.pass_("all current_enabled_flags are false")


def check_route_syntax(check: Check, data: dict[str, Any]) -> None:
    syntax = data.get("future_route_syntax")
    if not isinstance(syntax, dict):
        check.fail("future_route_syntax must be an object")
        return
    if syntax.get("exact_command") != EXPECTED_EXACT_COMMAND:
        check.fail(f"exact_command mismatch; got {syntax.get('exact_command')}")
        return
    allowed = syntax.get("allowed_arguments")
    if not isinstance(allowed, list) or EXPECTED_APPROVAL_PHRASE not in allowed or "build_receipt=<receipt_path>" not in allowed:
        check.fail("allowed_arguments missing approval phrase or build_receipt token")
        return
    rejected = syntax.get("rejected_arguments")
    if not isinstance(rejected, list) or not rejected:
        check.fail("rejected_arguments must be a non-empty list")
        return
    if syntax.get("rejection_must_be_pre_password_gate") is not True:
        check.fail("rejection_must_be_pre_password_gate must be true")
        return
    if syntax.get("no_route_added_now") is not True:
        check.fail("no_route_added_now must be true")
        return
    check.pass_("future route syntax declared correctly with only build_receipt argument allowed")


def check_input_requirements(check: Check, data: dict[str, Any]) -> None:
    req = data.get("approved_promote_input_requirements")
    if not isinstance(req, dict):
        check.fail("approved_promote_input_requirements must be an object")
        return
    for key in REQUIRED_INPUT_REQUIREMENT_KEYS:
        if key not in req:
            check.fail(f"input requirement missing: {key}")
            return
    check.pass_("approved_promote_input_requirements declared")


def check_gates(check: Check, data: dict[str, Any]) -> None:
    gates = data.get("protected_action_gates")
    if not isinstance(gates, list):
        check.fail("protected_action_gates must be a list")
        return
    blob = normalize(json.dumps(gates))
    missing = [term for term in REQUIRED_GATE_TERMS if not has_phrase(blob, term)]
    if missing:
        check.fail(f"protected_action_gates missing: {missing}")
        return
    check.pass_("protected_action_gates cover required terms")


def check_receipt_model(check: Check, data: dict[str, Any]) -> None:
    model = data.get("receipt_model")
    if not isinstance(model, dict):
        check.fail("receipt_model must be an object")
        return
    if model.get("receipt_folder") != "reports\\debruijn_quantum_promote_receipts\\":
        check.fail("receipt_model.receipt_folder mismatch")
        return
    fields = model.get("required_fields")
    if not isinstance(fields, list):
        check.fail("receipt_model.required_fields must be a list")
        return
    missing = [f for f in REQUIRED_RECEIPT_FIELDS if f not in fields]
    if missing:
        check.fail(f"receipt_model required fields missing: {missing}")
        return
    never = model.get("must_never_contain")
    if not isinstance(never, list):
        check.fail("receipt_model.must_never_contain must be a list")
        return
    blob = normalize(json.dumps(never))
    for term in REQUIRED_MUST_NEVER_CONTAIN:
        if not has_phrase(blob, term):
            check.fail(f"must_never_contain missing term: {term}")
            return
    check.pass_("receipt_model declared with required fields and secret exclusions")


def check_forbidden(check: Check, data: dict[str, Any]) -> None:
    forbidden = data.get("forbidden_behavior")
    if not isinstance(forbidden, list):
        check.fail("forbidden_behavior must be a list")
        return
    blob = normalize(json.dumps(forbidden))
    missing = [term for term in REQUIRED_FORBIDDEN_TERMS if not has_phrase(blob, term)]
    if missing:
        check.fail(f"forbidden_behavior missing terms: {missing}")
        return
    check.pass_("forbidden_behavior covers required terms")


def check_route_state_is_fail_closed_or_absent(check: Check) -> None:
    """The contract is contract-only at authorship time; once the V1 fail-closed route
    lands, the route exists but must remain fail-closed (disabled-reason marker present,
    no actual promote enabled). This check accepts either state: absent, or present and
    fail-closed. The runtime route verifier enforces the deeper safety properties.
    """
    if not ENGEL_APP.exists():
        check.fail("engel_app.py missing")
        return
    text = ENGEL_APP.read_text(encoding="utf-8", errors="ignore")
    route_present = 'msg.lower().startswith("engel ai debruijn quantum promote")' in text
    handler_present = "def debruijn_quantum_approved_promote_command_v1" in text
    if not route_present and not handler_present:
        check.pass_("no approved promote command route in engel_app.py (contract-only state)")
        return
    if route_present != handler_present:
        check.fail("approved promote command route/handler presence is inconsistent")
        return
    if "PROMOTE_EXECUTION_NOT_IMPLEMENTED" not in text:
        check.fail("approved promote command route exists but disabled-reason marker is missing")
        return
    if "approved_promote_command_enabled_now: false" not in text:
        check.fail("approved promote command route exists but safety flag string is missing")
        return
    check.pass_("approved promote command route exists in fail-closed V1 form")


def check_md_includes_expected_command(check: Check) -> None:
    text = CONTRACT_MD.read_text(encoding="utf-8", errors="ignore")
    if EXPECTED_EXACT_COMMAND not in text:
        check.fail("contract MD missing exact future command text")
        return
    check.pass_("contract MD includes exact future command text")


def main() -> int:
    check = Check()
    print("ENGEL_DEBRUIJN_QUANTUM_APPROVED_PROMOTE_COMMAND_CONTRACT_VERIFIER")
    print(f"ROOT {ROOT}")
    print("Mode: contract validation only; no runtime, apply, build, promote, route, provider, network, or mutation.")
    if not check_workspace(check):
        return 1
    data = check_files(check)
    if data is None:
        return 1
    check_identity(check, data)
    check_flags(check, data)
    check_route_syntax(check, data)
    check_input_requirements(check, data)
    check_gates(check, data)
    check_receipt_model(check, data)
    check_forbidden(check, data)
    check_md_includes_expected_command(check)
    check_route_state_is_fail_closed_or_absent(check)
    if check.failures:
        print(f"FAIL approved promote command contract verification failed with {len(check.failures)} issue(s)")
        return 1
    print(PASS_MARKER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
