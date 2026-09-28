#!/usr/bin/env python3
"""Verify ENGEL_DEBRUIJN_QUANTUM_APPROVED_PROMOTE_LANE_CONTRACT_V1.

Mode: static contract validation. No runtime, apply, build, promote, route addition,
provider/model/network, or any source/route/queue/trusted-memory mutation.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_TEXT = r"D:\b.WorkSpace\Engel App"

CONTRACT_ID = "ENGEL_DEBRUIJN_QUANTUM_APPROVED_PROMOTE_LANE_CONTRACT_V1"
CONTRACT_JSON = ROOT / "memory" / f"{CONTRACT_ID}.json"
CONTRACT_MD = ROOT / "memory" / f"{CONTRACT_ID}.md"

PASS_MARKER = "DEBRUIJN_QUANTUM_APPROVED_PROMOTE_LANE_CONTRACT_VERIFICATION_PASS"

EXPECTED_CALLING_ROUTE = (
    "engel ai debruijn quantum promote "
    "APPROVE_DEBRUIJN_QUANTUM_GRAPH_PROMOTE_V1 build_receipt=<receipt_path>"
)

EXPECTED_BUILD_COMMAND_IDS = (
    "build_engel_main_exe",
    "build_engel_super_swarm_exe",
    "build_approved_packaged_artifacts",
)

EXPECTED_TIMEOUT_LANE_ID = "long_running_verifier_stack"
EXPECTED_TIMEOUT_SOFT = 600
EXPECTED_TIMEOUT_HARD = 1200

FALSE_FLAGS = [
    "promote_lane_implementation_enabled_now",
    "promote_lane_execution_enabled_now",
    "actual_promote_enabled_now",
    "live_write_enabled_now",
    "backup_write_enabled_now",
    "dist_write_enabled_now",
    "build_execution_enabled_now",
    "pyinstaller_enabled_now",
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
    "build_receipt path must be inside workspace and JSON under reports/debruijn_quantum_build_receipts/",
    "build_receipt engine_id must equal debruijn_quantum_build_promote_engine",
    "Global Password Gate must pass redacted before lane runs any backup/promote step",
    "all required_pre_promote_verifiers must pass before the lane runs any backup/promote step",
    "lane writes the backup before touching the live target",
    "lane verifies the backup hash before replacing the live target",
    "lane never invokes a shell with shell=True",
    "lane uses bounded timeout per the timeout_lane_id (soft + hard ceilings)",
    "bounded soft timeout produces review_required classification",
    "bounded hard timeout produces blocked classification and cleanup verification",
    "lane writes only to the declared backup path and the declared live target path",
    "lane writes one promote receipt under reports/debruijn_quantum_promote_receipts/",
    "lane runs all required_post_promote_verifiers after the promote attempt",
    "lane never executes additional build commands",
    "lane never executes PyInstaller",
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
    "input_build_receipt_path",
    "build_receipt_engine_id",
    "build_receipt_final_status",
    "build_command_id",
    "candidate_id",
    "candidate_hash",
    "source_node_state_id",
    "target_node_state_id",
    "edge_transition_id",
    "edge_label",
    "approval_detected",
    "approval_phrase_name",
    "password_gate_result",
    "expected_staged_artifact_paths",
    "actual_staged_artifact_paths",
    "live_target_path",
    "backup_target_path",
    "backup_paths",
    "backup_hash_manifest",
    "promoted_artifact_paths",
    "live_smoke_command_id",
    "live_smoke_result",
    "timeout_lane_id",
    "timeout_seconds_soft",
    "timeout_seconds_hard",
    "elapsed_seconds",
    "timeout_classification",
    "pre_promote_verifier_results",
    "post_promote_verifier_results",
    "rollback_note",
    "files_changed",
    "forbidden_actions_not_performed",
    "cleanup_status",
    "final_status",
    "human_review_required",
]

REQUIRED_STATUS_VOCABULARY = [
    "PROMOTE_LANE_NOT_IMPLEMENTED",
    "PROMOTE_LANE_BLOCKED_BUILD_RECEIPT_MISSING",
    "PROMOTE_LANE_BLOCKED_BUILD_RECEIPT_INVALID",
    "PROMOTE_LANE_BLOCKED_STAGED_ARTIFACT_MISSING",
    "PROMOTE_LANE_BLOCKED_OUTSIDE_ALLOWLIST",
    "PROMOTE_LANE_BLOCKED_PRE_VERIFIER",
    "PROMOTE_LANE_BLOCKED_PASSWORD_GATE",
    "PROMOTE_LANE_BLOCKED_TIMEOUT_LANE_MISSING",
    "PROMOTE_LANE_BLOCKED_BACKUP_FAILED",
    "PROMOTE_LANE_TIMEOUT_BOUNDED_REVIEW_REQUIRED",
    "PROMOTE_LANE_TIMEOUT_HARD_BLOCKED",
    "PROMOTE_LANE_LIVE_SMOKE_FAIL_REVIEW_REQUIRED",
    "PROMOTE_LANE_POST_VERIFIER_FAIL_REVIEW_REQUIRED",
    "PROMOTE_LANE_PASS_REVIEW_REQUIRED",
]

REQUIRED_FORBIDDEN_PHRASES = [
    "promote without a valid approved_build_lane build receipt",
    "promote without a staged artifact that matches the build receipt",
    "promote without Global Password Gate pass",
    "writing to live before writing the verified backup",
    "shell=True invocation",
    "writes to dist or build during promote",
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
    "auto-promote based on traversal",
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
    if lane.get("lane_id") != "approved_graph_promote":
        check.fail("lane_identity.lane_id must be 'approved_graph_promote'")
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
    allowlist = data.get("live_target_allowlist")
    if not isinstance(allowlist, list) or len(allowlist) != len(EXPECTED_BUILD_COMMAND_IDS):
        check.fail(f"live_target_allowlist must have exactly {len(EXPECTED_BUILD_COMMAND_IDS)} entries")
        return
    seen_ids: list[str] = []
    for entry in allowlist:
        if not isinstance(entry, dict):
            check.fail("live_target_allowlist entries must be objects")
            return
        cid = entry.get("build_command_id")
        if cid not in EXPECTED_BUILD_COMMAND_IDS:
            check.fail(f"unexpected allowlist build_command_id: {cid}")
            return
        seen_ids.append(cid)
        staged = entry.get("expected_staged_artifact_paths")
        if not isinstance(staged, list) or not staged:
            check.fail(f"{cid} expected_staged_artifact_paths must be a non-empty list")
            return
        for s in staged:
            lowered = str(s).lower()
            if not lowered.startswith("build\\staging\\"):
                check.fail(f"{cid} staged artifact path must be under build\\staging\\: {s}")
                return
        live = entry.get("live_target_path")
        if not isinstance(live, str) or not live.lower().startswith("live\\"):
            check.fail(f"{cid} live_target_path must be under live\\: {live}")
            return
        backup = entry.get("backup_target_path")
        if not isinstance(backup, str) or not backup.lower().startswith("backups\\"):
            check.fail(f"{cid} backup_target_path must be under backups\\: {backup}")
            return
        smoke = entry.get("live_smoke_command_id")
        if not isinstance(smoke, str) or not smoke.startswith("live_smoke_"):
            check.fail(f"{cid} live_smoke_command_id must start with 'live_smoke_': {smoke}")
            return
        if entry.get("timeout_lane_id") != EXPECTED_TIMEOUT_LANE_ID:
            check.fail(f"{cid} timeout_lane_id must be {EXPECTED_TIMEOUT_LANE_ID}")
            return
        if entry.get("timeout_seconds_soft") != EXPECTED_TIMEOUT_SOFT:
            check.fail(f"{cid} timeout_seconds_soft must be {EXPECTED_TIMEOUT_SOFT}")
            return
        if entry.get("timeout_seconds_hard") != EXPECTED_TIMEOUT_HARD:
            check.fail(f"{cid} timeout_seconds_hard must be {EXPECTED_TIMEOUT_HARD}")
            return
    if sorted(seen_ids) != sorted(EXPECTED_BUILD_COMMAND_IDS):
        check.fail(f"allowlist build_command_id set mismatch; got {sorted(seen_ids)}")
        return
    check.pass_("live_target_allowlist matches the three expected build_command_ids with correct fields and live/backup/staging path constraints")


def check_pre_post_verifiers(check: Check, data: dict[str, Any]) -> None:
    pre = data.get("required_pre_promote_verifiers")
    post = data.get("required_post_promote_verifiers")
    if not isinstance(pre, list) or not pre:
        check.fail("required_pre_promote_verifiers must be a non-empty list")
        return
    if not isinstance(post, list) or not post:
        check.fail("required_post_promote_verifiers must be a non-empty list")
        return
    must_pre = [
        "tools\\verify_debruijn_quantum_approved_build_lane.py",
        "tools\\verify_debruijn_quantum_approved_build_lane_contract.py",
        "tools\\verify_verifier_timeout_lane_classification_contract.py",
        "tools\\verify_engel_global_password_gate.py",
    ]
    for v in must_pre:
        if v not in pre:
            check.fail(f"required_pre_promote_verifiers missing: {v}")
            return
    check.pass_("required pre/post promote verifier lists declared")


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
    if model.get("receipt_folder") != "reports\\debruijn_quantum_promote_receipts\\":
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
    if "backup_hash_manifest" not in fields or "rollback_note" not in fields:
        check.fail("lane_receipt_model.required_fields must include backup_hash_manifest and rollback_note")
        return
    check.pass_("lane_receipt_model declared with full required fields and secret exclusions")


def check_status_vocabulary(check: Check, data: dict[str, Any]) -> None:
    vocab = data.get("lane_status_vocabulary")
    if not isinstance(vocab, list):
        check.fail("lane_status_vocabulary must be a list")
        return
    missing = [s for s in REQUIRED_STATUS_VOCABULARY if s not in vocab]
    if missing:
        check.fail(f"lane_status_vocabulary missing: {missing}")
        return
    check.pass_("lane_status_vocabulary covers required status codes")


def check_v1_dependency_absent_behavior(check: Check, data: dict[str, Any]) -> None:
    text = data.get("v1_implementation_behavior_when_dependencies_absent")
    if not isinstance(text, str) or not text:
        check.fail("v1_implementation_behavior_when_dependencies_absent must be a non-empty string")
        return
    blob = normalize(text)
    for required in (
        "PROMOTE_LANE_NOT_IMPLEMENTED",
        "PROMOTE_LANE_BLOCKED_BUILD_RECEIPT_MISSING",
        "PROMOTE_LANE_BLOCKED_STAGED_ARTIFACT_MISSING",
        "without invoking subprocess",
        "without writing to live/backups",
        "review_required receipt",
    ):
        if not has_phrase(blob, required):
            check.fail(f"v1_implementation_behavior_when_dependencies_absent missing phrase: {required}")
            return
    check.pass_("v1_implementation_behavior_when_dependencies_absent declared with correct semantics")


def check_forbidden(check: Check, data: dict[str, Any]) -> None:
    forbidden = data.get("forbidden_behavior")
    if not isinstance(forbidden, list):
        check.fail("forbidden_behavior must be a list")
        return
    blob = normalize(json.dumps(forbidden))
    missing = [p for p in REQUIRED_FORBIDDEN_PHRASES if not has_phrase(blob, p)]
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
        "ENGEL_DEBRUIJN_QUANTUM_APPROVED_PROMOTE_LANE_CONTRACT_V1",
        "ENGEL_DEBRUIJN_QUANTUM_APPROVED_PROMOTE_LANE_VERIFIER_V1",
        "ENGEL_DEBRUIJN_QUANTUM_APPROVED_PROMOTE_LANE_V1",
        "ENGEL_DEBRUIJN_QUANTUM_APPROVED_PROMOTE_LANE_SOURCE_SMOKE_V1",
        "ENGEL_DEBRUIJN_QUANTUM_APPROVED_PROMOTE_LANE_CLOSEOUT_REVIEW_V1",
        "ENGEL_DEBRUIJN_QUANTUM_APPROVED_PROMOTE_LANE_SELECTIVE_COMMIT_V1",
    ]
    if [s for s in expected if s not in sequence]:
        check.fail("future_implementation_sequence missing expected slice IDs")
        return
    positions = [sequence.index(s) for s in expected]
    if positions != sorted(positions):
        check.fail("future_implementation_sequence has expected slices out of order")
        return
    check.pass_("future_implementation_sequence in expected order")


def check_md_includes_allowlist_table(check: Check) -> None:
    text = CONTRACT_MD.read_text(encoding="utf-8", errors="ignore")
    for cid in EXPECTED_BUILD_COMMAND_IDS:
        if cid not in text:
            check.fail(f"contract MD missing build_command_id mention: {cid}")
            return
    if "Live Target Allowlist" not in text:
        check.fail("contract MD missing 'Live Target Allowlist' section header")
        return
    check.pass_("contract MD includes the live target allowlist table and all three build_command_ids")


def main() -> int:
    check = Check()
    print("ENGEL_DEBRUIJN_QUANTUM_APPROVED_PROMOTE_LANE_CONTRACT_VERIFIER")
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
    check_pre_post_verifiers(check, data)
    check_lane_execution_rules(check, data)
    check_receipt_model(check, data)
    check_status_vocabulary(check, data)
    check_v1_dependency_absent_behavior(check, data)
    check_forbidden(check, data)
    check_sequence(check, data)
    check_md_includes_allowlist_table(check)
    if check.failures:
        print(f"FAIL approved promote lane contract verification failed with {len(check.failures)} issue(s)")
        return 1
    print(PASS_MARKER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
