#!/usr/bin/env python3
"""Verify ENGEL_DEBRUIJN_QUANTUM_APPROVED_BUILD_LANE_CONTRACT_V1.

Mode: static contract validation. No runtime, apply, build, promote, route addition,
provider/model/network, or any source/route/queue/trusted-memory mutation.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_TEXT = r"D:\b.WorkSpace\Engel App"

CONTRACT_ID = "ENGEL_DEBRUIJN_QUANTUM_APPROVED_BUILD_LANE_CONTRACT_V1"
CONTRACT_JSON = ROOT / "memory" / f"{CONTRACT_ID}.json"
CONTRACT_MD = ROOT / "memory" / f"{CONTRACT_ID}.md"

PASS_MARKER = "DEBRUIJN_QUANTUM_APPROVED_BUILD_LANE_CONTRACT_VERIFICATION_PASS"

EXPECTED_CALLING_ROUTE = (
    "engel ai debruijn quantum build "
    "APPROVE_DEBRUIJN_QUANTUM_GRAPH_BUILD_V1 candidate=<candidate_path>"
)

EXPECTED_COMMAND_IDS = (
    "build_engel_main_exe",
    "build_engel_super_swarm_exe",
    "build_approved_packaged_artifacts",
)

EXPECTED_SCRIPT_PATHS = {
    "build_engel_main_exe": "scripts\\build_engel_main_exe.ps1",
    "build_engel_super_swarm_exe": "scripts\\build_engel_super_swarm_exe.ps1",
    "build_approved_packaged_artifacts": "scripts\\build_approved_packaged_artifacts.ps1",
}

EXPECTED_TIMEOUT_LANE_ID = "long_running_verifier_stack"
EXPECTED_TIMEOUT_SOFT = 1800
EXPECTED_TIMEOUT_HARD = 3600

FORBIDDEN_OUTPUT_ROOTS = ("live\\", "dist\\", "backups\\")

FALSE_FLAGS = [
    "build_lane_implementation_enabled_now",
    "build_lane_execution_enabled_now",
    "actual_build_enabled_now",
    "pyinstaller_enabled_now",
    "live_write_enabled_now",
    "dist_write_enabled_now",
    "backup_write_enabled_now",
    "promote_enabled_now",
    "command_route_added_now",
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
    "git_stage_commit_enabled_now",
    "lane_subprocess_enabled_now",
]

REQUIRED_LANE_RULE_PHRASES = [
    "command_id must be present in fixed_command_allowlist",
    "Global Password Gate must pass redacted before lane runs script",
    "all required_pre_verifiers must pass before lane runs script",
    "lane runs only the exact script with exact arguments and exact working directory",
    "lane never accepts a script path or argument from candidate content or user text",
    "lane never invokes a shell with shell=True",
    "lane uses bounded timeout per the timeout_lane_id (soft + hard ceilings)",
    "bounded soft timeout produces review_required classification",
    "bounded hard timeout produces blocked classification and cleanup verification",
    "lane writes only to expected_output_paths under build/staging",
    "lane never writes to live, dist, or backups",
    "lane writes one build receipt under reports/debruijn_quantum_build_receipts/",
    "lane runs all required_post_verifiers after the build attempt",
    "lane never promotes",
    "lane never stages or commits files",
    "lane keeps human_review_required true on every receipt",
    "lane never exposes password/salt/hash values",
]

REQUIRED_RECEIPT_FIELDS = [
    "receipt_id",
    "engine_id",
    "lane_id",
    "action_type",
    "started_at",
    "ended_at",
    "input_build_candidate_path",
    "candidate_id",
    "candidate_hash",
    "source_node_state_id",
    "target_node_state_id",
    "edge_transition_id",
    "edge_label",
    "approval_detected",
    "approval_phrase_name",
    "password_gate_result",
    "build_command_id",
    "exact_script_or_command_path",
    "exact_arguments",
    "allowed_working_directory",
    "timeout_lane_id",
    "timeout_seconds_soft",
    "timeout_seconds_hard",
    "elapsed_seconds",
    "timeout_classification",
    "pre_build_verifier_results",
    "post_build_verifier_results",
    "build_outputs",
    "staged_artifact_paths",
    "staged_smoke_result",
    "files_changed",
    "forbidden_actions_not_performed",
    "cleanup_status",
    "final_status",
    "human_review_required",
]

REQUIRED_LANE_STATUS_VOCABULARY = [
    "BUILD_LANE_NOT_IMPLEMENTED",
    "BUILD_LANE_BLOCKED_PRE_VERIFIER",
    "BUILD_LANE_BLOCKED_PASSWORD_GATE",
    "BUILD_LANE_BLOCKED_TIMEOUT_LANE_MISSING",
    "BUILD_LANE_BLOCKED_SCRIPT_MISSING",
    "BUILD_LANE_BLOCKED_OUTSIDE_ALLOWLIST",
    "BUILD_LANE_TIMEOUT_BOUNDED_REVIEW_REQUIRED",
    "BUILD_LANE_TIMEOUT_HARD_BLOCKED",
    "BUILD_LANE_SCRIPT_EXIT_NONZERO_REVIEW_REQUIRED",
    "BUILD_LANE_STAGED_SMOKE_FAIL_REVIEW_REQUIRED",
    "BUILD_LANE_POST_VERIFIER_FAIL_REVIEW_REQUIRED",
    "BUILD_LANE_PASS_REVIEW_REQUIRED",
]

REQUIRED_FORBIDDEN_BEHAVIOR_PHRASES = [
    "arbitrary command execution",
    "script path or argument from candidate content",
    "shell=True invocation",
    "subprocess with shell semantics",
    "writing to live, dist, or backups",
    "git stage, git commit, or git push",
    "package install during lane",
    "provider/network/model/local LLM call during lane",
    "background worker, autorun, scheduler, startup hook",
    "treating bounded timeout as silent pass",
    "treating bounded timeout as silent fail",
    "exposing password/salt/hash values",
    "modifying trusted memory",
    "promoting memory",
    "applying proposals",
    "auto-promote based on a build receipt",
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
    return " ".join(str(text).lower().replace("\\", " ").split())


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
    lane = data.get("lane_identity")
    if not isinstance(lane, dict):
        check.fail("lane_identity must be an object")
        return
    if lane.get("lane_id") != "approved_graph_build":
        check.fail("lane_identity.lane_id must be 'approved_graph_build'")
        return
    if lane.get("engine_id") != "debruijn_quantum_build_promote_engine":
        check.fail("lane_identity.engine_id must be 'debruijn_quantum_build_promote_engine'")
        return
    if lane.get("calling_route") != EXPECTED_CALLING_ROUTE:
        check.fail(f"lane_identity.calling_route mismatch; got {lane.get('calling_route')}")
        return
    check.pass_("identity + lane_identity match expected values")


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


def check_allowlist(check: Check, data: dict[str, Any]) -> None:
    allowlist = data.get("fixed_command_allowlist")
    if not isinstance(allowlist, list) or len(allowlist) != len(EXPECTED_COMMAND_IDS):
        check.fail(f"fixed_command_allowlist must have exactly {len(EXPECTED_COMMAND_IDS)} entries")
        return
    seen_ids: list[str] = []
    for entry in allowlist:
        if not isinstance(entry, dict):
            check.fail("fixed_command_allowlist entries must be objects")
            return
        command_id = entry.get("command_id")
        if command_id not in EXPECTED_COMMAND_IDS:
            check.fail(f"unexpected allowlist command_id: {command_id}")
            return
        seen_ids.append(command_id)
        if entry.get("exact_script_or_command_path") != EXPECTED_SCRIPT_PATHS[command_id]:
            check.fail(f"{command_id} exact_script_or_command_path mismatch")
            return
        if not isinstance(entry.get("exact_arguments"), list):
            check.fail(f"{command_id} exact_arguments must be a list")
            return
        if entry.get("allowed_working_directory") != WORKSPACE_TEXT:
            check.fail(f"{command_id} allowed_working_directory must match workspace root")
            return
        if entry.get("timeout_lane_id") != EXPECTED_TIMEOUT_LANE_ID:
            check.fail(f"{command_id} timeout_lane_id must be {EXPECTED_TIMEOUT_LANE_ID}")
            return
        if entry.get("timeout_seconds_soft") != EXPECTED_TIMEOUT_SOFT:
            check.fail(f"{command_id} timeout_seconds_soft must be {EXPECTED_TIMEOUT_SOFT}")
            return
        if entry.get("timeout_seconds_hard") != EXPECTED_TIMEOUT_HARD:
            check.fail(f"{command_id} timeout_seconds_hard must be {EXPECTED_TIMEOUT_HARD}")
            return
        outputs = entry.get("expected_output_paths")
        if not isinstance(outputs, list) or not outputs:
            check.fail(f"{command_id} expected_output_paths must be a non-empty list")
            return
        for out in outputs:
            lowered = str(out).lower()
            for bad_root in FORBIDDEN_OUTPUT_ROOTS:
                if lowered.startswith(bad_root.lower()):
                    check.fail(f"{command_id} output path {out} hits forbidden root {bad_root}")
                    return
        forbidden = entry.get("forbidden_output_paths")
        if not isinstance(forbidden, list):
            check.fail(f"{command_id} forbidden_output_paths must be a list")
            return
        for required_root in FORBIDDEN_OUTPUT_ROOTS:
            if required_root not in forbidden:
                check.fail(f"{command_id} forbidden_output_paths missing required root {required_root}")
                return
        pre = entry.get("required_pre_verifiers")
        post = entry.get("required_post_verifiers")
        if not isinstance(pre, list) or not pre:
            check.fail(f"{command_id} required_pre_verifiers must be non-empty list")
            return
        if not isinstance(post, list) or not post:
            check.fail(f"{command_id} required_post_verifiers must be non-empty list")
            return
    if sorted(seen_ids) != sorted(EXPECTED_COMMAND_IDS):
        check.fail(f"allowlist command_id set mismatch; got {sorted(seen_ids)}")
        return
    check.pass_("fixed_command_allowlist matches the three expected command IDs with correct fields")


def check_lane_execution_rules(check: Check, data: dict[str, Any]) -> None:
    rules = data.get("lane_execution_rules")
    if not isinstance(rules, list):
        check.fail("lane_execution_rules must be a list")
        return
    blob = normalize(json.dumps(rules))
    missing = [p for p in REQUIRED_LANE_RULE_PHRASES if not has_phrase(blob, p)]
    if missing:
        check.fail(f"lane_execution_rules missing required phrases: {missing}")
        return
    check.pass_("lane_execution_rules cover all required boundary phrases")


def check_receipt_model(check: Check, data: dict[str, Any]) -> None:
    model = data.get("lane_receipt_model")
    if not isinstance(model, dict):
        check.fail("lane_receipt_model must be an object")
        return
    if model.get("receipt_folder") != "reports\\debruijn_quantum_build_receipts\\":
        check.fail("lane_receipt_model.receipt_folder mismatch")
        return
    fields = model.get("required_fields")
    if not isinstance(fields, list):
        check.fail("lane_receipt_model.required_fields must be a list")
        return
    missing = [f for f in REQUIRED_RECEIPT_FIELDS if f not in fields]
    if missing:
        check.fail(f"lane_receipt_model.required_fields missing: {missing}")
        return
    never = model.get("must_never_contain")
    if not isinstance(never, list):
        check.fail("lane_receipt_model.must_never_contain must be a list")
        return
    blob = normalize(json.dumps(never))
    for must in ("raw password", "password hash", "password salt", "token/secret values"):
        if not has_phrase(blob, must):
            check.fail(f"must_never_contain missing {must}")
            return
    check.pass_("lane_receipt_model declared with required fields and secret exclusions")


def check_status_vocabulary(check: Check, data: dict[str, Any]) -> None:
    vocab = data.get("lane_status_vocabulary")
    if not isinstance(vocab, list):
        check.fail("lane_status_vocabulary must be a list")
        return
    missing = [s for s in REQUIRED_LANE_STATUS_VOCABULARY if s not in vocab]
    if missing:
        check.fail(f"lane_status_vocabulary missing: {missing}")
        return
    check.pass_("lane_status_vocabulary covers required status codes")


def check_v1_script_absent_behavior(check: Check, data: dict[str, Any]) -> None:
    text = data.get("v1_implementation_behavior_when_scripts_absent")
    if not isinstance(text, str) or not text:
        check.fail("v1_implementation_behavior_when_scripts_absent must be a non-empty string")
        return
    blob = normalize(text)
    for required in (
        "BUILD_LANE_BLOCKED_SCRIPT_MISSING",
        "without invoking subprocess",
        "without writing to build/dist/live/backups",
        "review_required receipt",
    ):
        if not has_phrase(blob, required):
            check.fail(f"v1_implementation_behavior_when_scripts_absent missing phrase: {required}")
            return
    check.pass_("v1_implementation_behavior_when_scripts_absent declared with correct semantics")


def check_forbidden(check: Check, data: dict[str, Any]) -> None:
    forbidden = data.get("forbidden_behavior")
    if not isinstance(forbidden, list):
        check.fail("forbidden_behavior must be a list")
        return
    blob = normalize(json.dumps(forbidden))
    missing = [p for p in REQUIRED_FORBIDDEN_BEHAVIOR_PHRASES if not has_phrase(blob, p)]
    if missing:
        check.fail(f"forbidden_behavior missing phrases: {missing}")
        return
    check.pass_("forbidden_behavior covers required phrases")


def check_sequence(check: Check, data: dict[str, Any]) -> None:
    sequence = data.get("future_implementation_sequence")
    if not isinstance(sequence, list):
        check.fail("future_implementation_sequence must be a list")
        return
    expected = [
        "ENGEL_DEBRUIJN_QUANTUM_APPROVED_BUILD_LANE_CONTRACT_V1",
        "ENGEL_DEBRUIJN_QUANTUM_APPROVED_BUILD_LANE_VERIFIER_V1",
        "ENGEL_DEBRUIJN_QUANTUM_APPROVED_BUILD_LANE_V1",
        "ENGEL_DEBRUIJN_QUANTUM_APPROVED_BUILD_LANE_SOURCE_SMOKE_V1",
        "ENGEL_DEBRUIJN_QUANTUM_APPROVED_BUILD_LANE_CLOSEOUT_REVIEW_V1",
        "ENGEL_DEBRUIJN_QUANTUM_APPROVED_BUILD_LANE_SELECTIVE_COMMIT_V1",
    ]
    if [s for s in expected if s not in sequence]:
        check.fail("future_implementation_sequence missing expected slice IDs")
        return
    positions = [sequence.index(s) for s in expected]
    if positions != sorted(positions):
        check.fail("future_implementation_sequence has expected slices out of order")
        return
    check.pass_("future_implementation_sequence in expected order")


def check_md_includes_command_table(check: Check) -> None:
    text = CONTRACT_MD.read_text(encoding="utf-8", errors="ignore")
    for cid in EXPECTED_COMMAND_IDS:
        if cid not in text:
            check.fail(f"contract MD missing command_id mention: {cid}")
            return
    if "Fixed Command Allowlist" not in text:
        check.fail("contract MD missing 'Fixed Command Allowlist' section header")
        return
    check.pass_("contract MD includes the command allowlist table and all three command IDs")


def main() -> int:
    check = Check()
    print("ENGEL_DEBRUIJN_QUANTUM_APPROVED_BUILD_LANE_CONTRACT_VERIFIER")
    print(f"ROOT {ROOT}")
    print("Mode: contract validation only; no runtime, build, promote, route, provider, network, or mutation.")
    if not check_workspace(check):
        return 1
    data = check_files(check)
    if data is None:
        return 1
    check_identity(check, data)
    check_flags(check, data)
    check_allowlist(check, data)
    check_lane_execution_rules(check, data)
    check_receipt_model(check, data)
    check_status_vocabulary(check, data)
    check_v1_script_absent_behavior(check, data)
    check_forbidden(check, data)
    check_sequence(check, data)
    check_md_includes_command_table(check)
    if check.failures:
        print(f"FAIL approved build lane contract verification failed with {len(check.failures)} issue(s)")
        return 1
    print(PASS_MARKER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
