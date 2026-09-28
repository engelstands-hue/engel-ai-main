#!/usr/bin/env python3
"""Verify the ENGEL_VERIFIER_TIMEOUT_LANE_CLASSIFICATION_CONTRACT_V1 contract.

Mode: static contract validation. No runtime/apply/build/promote execution, no routes
added, no provider/model/network/local LLM calls, no source/route/queue/trusted-memory
mutation, no git stage/commit, no password values exposed.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_TEXT = r"D:\b.WorkSpace\Engel App"

CONTRACT_ID = "ENGEL_VERIFIER_TIMEOUT_LANE_CLASSIFICATION_CONTRACT_V1"
CONTRACT_JSON = ROOT / "memory" / f"{CONTRACT_ID}.json"
CONTRACT_MD = ROOT / "memory" / f"{CONTRACT_ID}.md"

PASS_MARKER = "VERIFIER_TIMEOUT_LANE_CLASSIFICATION_CONTRACT_VERIFICATION_PASS"

REQUIRED_LANES = (
    "quick_smoke_check",
    "standard_verifier_stack",
    "long_running_verifier_stack",
    "report_only_timeout_classification",
)

BOUNDED_LANES = (
    "quick_smoke_check",
    "standard_verifier_stack",
    "long_running_verifier_stack",
)

REQUIRED_CLASSIFICATION_RULES = [
    "bounded timeout never silently ignored",
    "bounded timeout never silently treated as pass",
    "bounded timeout never silently treated as fail",
    "soft breach raises review_required",
    "hard breach blocks the protected action",
    "every protected action records a timeout_lane_classification field in its receipt",
    "every receipt records started_at and ended_at in UTC",
    "cleanup failure after timeout blocks build/promote regardless of lane",
    "long-running lane requires explicit allowlist in the calling contract",
    "report-only lane never satisfies a protected-action gate",
]

REQUIRED_RECEIPT_FIELDS = [
    "lane_id",
    "max_seconds_soft",
    "max_seconds_hard",
    "started_at",
    "ended_at",
    "elapsed_seconds",
    "timeout_classification",
    "cleanup_status",
    "human_review_required",
]

REQUIRED_FORBIDDEN_BEHAVIOR = [
    "ignoring a bounded timeout",
    "treating a timeout as silent pass",
    "treating a timeout as silent fail",
    "extending a lane beyond its hard ceiling without an explicit allowlist override",
    "bypassing cleanup verification after a timeout",
    "running long-running verifier stack without contract allowlisting",
    "treating report-only lane as gate-satisfying",
]

FALSE_FLAGS = [
    "actual_apply_enabled_now",
    "actual_build_enabled_now",
    "actual_promote_enabled_now",
    "command_route_added_now",
    "pyinstaller_enabled_now",
    "live_write_enabled_now",
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
    "verifier_helper_implemented_now",
    "approved_build_lane_enabled_now",
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
        check.fail(f"status must be 'contract_only', got {data.get('status')}")
        return
    if data.get("active_workspace") != WORKSPACE_TEXT:
        check.fail(f"active_workspace mismatch: {data.get('active_workspace')}")
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


def check_lanes(check: Check, data: dict[str, Any]) -> None:
    lanes = data.get("lanes")
    if not isinstance(lanes, dict):
        check.fail("lanes must be an object")
        return
    for name in REQUIRED_LANES:
        if name not in lanes:
            check.fail(f"missing lane: {name}")
            return
    check.pass_(f"all four required lanes present: {', '.join(REQUIRED_LANES)}")
    for name in BOUNDED_LANES:
        lane = lanes[name]
        soft = lane.get("max_seconds_soft")
        hard = lane.get("max_seconds_hard")
        if not isinstance(soft, int) or not isinstance(hard, int):
            check.fail(f"lane {name}: soft/hard ceilings must be integers")
            return
        if soft > hard:
            check.fail(f"lane {name}: soft ({soft}s) exceeds hard ({hard}s)")
            return
        if soft <= 0 or hard <= 0:
            check.fail(f"lane {name}: ceilings must be positive")
            return
    check.pass_("bounded lanes have ordered positive integer ceilings")
    report_only = lanes["report_only_timeout_classification"]
    if report_only.get("max_seconds_soft") is not None or report_only.get("max_seconds_hard") is not None:
        check.fail("report_only lane must have null ceilings")
        return
    check.pass_("report_only_timeout_classification has null ceilings")


def check_classification_rules(check: Check, data: dict[str, Any]) -> None:
    rules = data.get("classification_rules")
    if not isinstance(rules, list):
        check.fail("classification_rules must be a list")
        return
    blob = normalize(json.dumps(rules))
    missing = [r for r in REQUIRED_CLASSIFICATION_RULES if not has_phrase(blob, r)]
    if missing:
        check.fail(f"classification_rules missing: {missing}")
        return
    check.pass_("classification_rules cover all ten boundary rules")


def check_receipt_fields(check: Check, data: dict[str, Any]) -> None:
    fields = data.get("required_receipt_fields_when_lane_is_used")
    if not isinstance(fields, list):
        check.fail("required_receipt_fields_when_lane_is_used must be a list")
        return
    missing = [f for f in REQUIRED_RECEIPT_FIELDS if f not in fields]
    if missing:
        check.fail(f"required receipt fields missing: {missing}")
        return
    check.pass_("required receipt fields list is complete")


def check_forbidden_behavior(check: Check, data: dict[str, Any]) -> None:
    forbidden = data.get("forbidden_behavior")
    if not isinstance(forbidden, list):
        check.fail("forbidden_behavior must be a list")
        return
    blob = normalize(json.dumps(forbidden))
    missing = [item for item in REQUIRED_FORBIDDEN_BEHAVIOR if not has_phrase(blob, item)]
    if missing:
        check.fail(f"forbidden_behavior missing: {missing}")
        return
    check.pass_("forbidden_behavior list is complete")


def check_md_includes_lane_table(check: Check) -> None:
    text = CONTRACT_MD.read_text(encoding="utf-8", errors="ignore")
    lower = text.lower()
    for name in REQUIRED_LANES:
        if name not in lower:
            check.fail(f"contract MD missing lane mention: {name}")
            return
    if "| lane_id |" not in lower and "lane_id" not in lower:
        check.fail("contract MD missing lane table or lane_id column")
        return
    check.pass_("contract MD includes the lane table and all four lane IDs")


def main() -> int:
    check = Check()
    print("ENGEL_VERIFIER_TIMEOUT_LANE_CLASSIFICATION_CONTRACT_VERIFIER")
    print(f"ROOT {ROOT}")
    print("Mode: contract validation only; no runtime, apply, build, promote, route, provider, network, or mutation.")
    if not check_workspace(check):
        return 1
    data = check_files(check)
    if data is None:
        return 1
    check_identity(check, data)
    check_flags(check, data)
    check_lanes(check, data)
    check_classification_rules(check, data)
    check_receipt_fields(check, data)
    check_forbidden_behavior(check, data)
    check_md_includes_lane_table(check)
    if check.failures:
        print(f"FAIL timeout lane classification contract verification failed with {len(check.failures)} issue(s)")
        return 1
    print(PASS_MARKER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
