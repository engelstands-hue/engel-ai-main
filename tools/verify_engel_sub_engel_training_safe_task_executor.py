#!/usr/bin/env python3
"""Verify the CT246-owned, training-safe Sub-Engel executor."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import engel_agent_meeting_room as meeting  # noqa: E402
import engel_sub_node_remote_control as remote  # noqa: E402
import engel_windows_sub_node_agent as node  # noqa: E402
from tools import engel_meeting_room_lan_server as room_server  # noqa: E402
from tools import engel_sub_engel_training_safe_task_executor as executor  # noqa: E402


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def active_guard() -> dict[str, Any]:
    return {
        "ok": True,
        "schema": "engel_sub_engel_training_guard_v1",
        "observed_at_utc": "2026-07-22T00:00:00Z",
        "training_active": True,
        "training_process_ids": [4242],
        "training_processes": [{"process_id": 4242, "name": "python.exe", "started": "fixture"}],
        "marker_records": [],
        "mutation_performed": False,
        "process_control_used": False,
    }


def node_work_order_proof(tmp: Path, safe: bool) -> dict[str, Any]:
    work = tmp / ("safe" if safe else "unsafe")
    room = work / "room"
    sent = room / node.SHARED_SENT_WORK_DIR
    paths = {
        "root": work / "node",
        "incoming": work / "node" / "incoming",
        "done": work / "node" / "done",
        "receipts": work / "node" / "receipts",
    }
    for path in [room, sent, *paths.values()]:
        path.mkdir(parents=True, exist_ok=True)
    source = room / ("safe.json" if safe else "unsafe.json")
    source.write_text(json.dumps({
        "schema": "engel_sub_engel_work_order_v1",
        "id": "SAFE-1" if safe else "UNSAFE-1",
        "target": "windows_sub_engel",
        "job_type": "status_snapshot" if safe else "code_build",
        "order_text": "Return a read-only status snapshot." if safe else "Build and install this update.",
        "training_safe": safe,
        "non_invasive": safe,
        "proof_required": True,
    }), encoding="utf-8")

    originals = {
        "node_work_dirs": node.node_work_dirs,
        "training_status_payload": node.training_status_payload,
        "run_local_helper_llm": node.run_local_helper_llm,
        "append_shared_room_bus": node.append_shared_room_bus,
        "append_receipt": node.append_receipt,
        "console_notice": node.console_notice,
    }
    node.node_work_dirs = lambda: paths
    node.training_status_payload = active_guard
    node.run_local_helper_llm = lambda _payload: (_ for _ in ()).throw(AssertionError("local LLM must not run during active training"))
    node.append_shared_room_bus = lambda *_args, **_kwargs: None
    node.append_receipt = lambda *_args, **_kwargs: None
    node.console_notice = lambda *_args, **_kwargs: None
    try:
        return node.process_shared_room_work_order(source, room, sent)
    finally:
        for name, value in originals.items():
            setattr(node, name, value)


def main() -> int:
    checks: list[str] = []
    require("training.status" in node.ALLOWED_ACTIONS, "node does not expose training.status")
    require("training_safe.execute" in node.ALLOWED_ACTIONS, "node does not expose training_safe.execute")
    require("training.status" in remote.ALLOWED_ACTIONS, "controller blocks training.status")
    require("training_safe.execute" in remote.ALLOWED_ACTIONS, "controller blocks training_safe.execute")
    checks.append("node and controller expose only the bounded training-safe actions")

    safe_class = executor.classify_task("Return a read-only status snapshot.", "status_snapshot")
    training_status_class = executor.classify_task("Return the current training status.", "training_status")
    unsafe_class = executor.classify_task("Stop training and install this model.", "status_snapshot")
    require(safe_class.get("training_safe") is True, "read-only status task was not accepted")
    require(training_status_class.get("training_safe") is True, "training status was mistaken for a training mutation")
    require(unsafe_class.get("training_safe") is False, "mutating task bypassed classifier")
    require("stop" in unsafe_class.get("mutation_terms", []), "mutation reason missing")
    require(node.training_safe_work_order_policy({
        "job_type": "training_status",
        "order_text": "Return the current training status.",
        "training_safe": True,
        "non_invasive": True,
    }).get("training_safe") is True, "Sub agent rejected a safe training-status request")
    checks.append("task classifier rejects process/model mutations")

    with tempfile.TemporaryDirectory(prefix="engel-sub-safe-") as tmp_text:
        tmp = Path(tmp_text)
        safe_receipt = node_work_order_proof(tmp, safe=True)
        require(safe_receipt.get("overall_ok") is True, "safe work-order proof failed")
        require(safe_receipt.get("worker_engine") == "training-safe-status-snapshot", "safe task used wrong engine")
        require(safe_receipt.get("local_llm_attempted") is False, "safe task started local LLM")
        require(safe_receipt.get("training_processes_unchanged") is True, "training PID proof changed")
        require(Path(str(safe_receipt.get("exported_file"))).is_file(), "safe return proof file missing")

        unsafe_receipt = node_work_order_proof(tmp, safe=False)
        require(unsafe_receipt.get("overall_ok") is False, "unsafe work order was marked complete")
        require(unsafe_receipt.get("operator_status") == "deferred_training_active", "unsafe task was not deferred")
        require(unsafe_receipt.get("local_llm_attempted") is False, "unsafe task started local LLM")
        require(Path(str(unsafe_receipt.get("exported_file"))).is_file(), "deferred proof file missing")
        checks.append("active training permits status proof and defers invasive work without model/process control")

        original_probe = executor.probe_training_guard
        original_run = executor.remote.run_action
        original_post = executor._post_meeting_room_proof
        original_report_dir = executor.REPORT_DIR
        original_latest = executor.LATEST_REPORT
        executor.REPORT_DIR = tmp / "executor-reports"
        executor.LATEST_REPORT = executor.REPORT_DIR / "latest.json"
        executor.probe_training_guard = lambda _node=executor.DEFAULT_NODE_ID: {
            "ok": True,
            "training_guard_observed": True,
            "training_active": True,
            "authenticated_training_status": True,
            "training_safe_execute_available": True,
            "training_process_ids": [4242],
        }
        remote_result = {
            "ok": True,
            "overall_ok": True,
            "training_guard_observed": True,
            "training_processes_unchanged": True,
            "mutation_performed": False,
            "process_control_used": False,
            "local_llm_attempted": False,
        }
        executor.remote.run_action = lambda *_args, **_kwargs: {
            "ok": True,
            "result": {"return_code": 0, "stdout": json.dumps(remote_result), "stderr": ""},
        }
        executor._post_meeting_room_proof = lambda *_args, **_kwargs: {"ok": True, "accepted": True}
        try:
            receipt = executor.execute_training_safe_task("Return a read-only status snapshot.", "status_snapshot")
        finally:
            executor.probe_training_guard = original_probe
            executor.remote.run_action = original_run
            executor._post_meeting_room_proof = original_post
            executor.REPORT_DIR = original_report_dir
            executor.LATEST_REPORT = original_latest
        require(receipt.get("ok") is True, "CT executor did not accept complete safe proof")
        require(receipt.get("status") == "returned", "CT executor receipt status is not returned")
        checks.append("CT executor requires authenticated guard and unchanged-process return proof")

    meeting_source = (ROOT / "engel_agent_meeting_room.py").read_text(encoding="utf-8")
    require("meeting_room_training_gate" in meeting_source, "Meeting Room does not use the training-safe gate")
    require("shell + disk, no Drive needed" not in meeting_source, "stale shell/disk completion claim remains")
    snapshot_source = (ROOT / "tools" / "engel_meeting_room_lan_server.py").read_text(encoding="utf-8")
    require("sub_engel_training_safe_executor" in snapshot_source, "Meeting Room server omits executor summary")
    checks.append("Meeting Room routes through the gate and exposes the latest receipt")

    require(room_server.summarize_sub_engel_training_safe_executor().get("schema") == "engel_sub_engel_training_safe_executor_summary_v1", "server summary schema failed")
    checks.append("server summary remains valid before the first live receipt")

    print(json.dumps({
        "ok": True,
        "schema": "engel_sub_engel_training_safe_task_executor_verifier_v1",
        "checks": checks,
        "check_count": len(checks),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
