#!/usr/bin/env python3
"""Verify the Sub-Engel authenticated direct-work action without network access."""

from __future__ import annotations

import importlib
import inspect
import json
import os
import shutil
import sys
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEST_ROOT = ROOT / "runtime" / "verify_sub_direct_work"
os.environ["ENGEL_WINDOWS_SUB_NODE_ROOT"] = str(TEST_ROOT)
os.environ["ENGEL_WINDOWS_SUB_NODE_STATE"] = str(TEST_ROOT / "state")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

node = importlib.import_module("engel_windows_sub_node_agent")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def decode(action_result: dict) -> dict:
    return json.loads(str(action_result.get("stdout") or "{}"))


def order(order_id: str, text: str = "Summarize this task for Engel Main review.") -> dict:
    return {
        "schema": node.DIRECT_WORK_SCHEMA,
        "id": order_id,
        "order_text": text,
        "target": "windows_sub_engel",
        "job_type": "meeting_work",
        "proof_required": True,
    }


def main() -> int:
    resolved = TEST_ROOT.resolve()
    runtime_root = (ROOT / "runtime").resolve()
    require(runtime_root in resolved.parents, f"unsafe verifier root: {resolved}")
    if TEST_ROOT.exists():
        shutil.rmtree(TEST_ROOT)

    node.training_status_payload = lambda: {
        "schema": "engel_training_guard_v1",
        "observed_at_utc": node.utc_stamp(),
        "training_active": False,
        "training_process_ids": [],
    }
    node.run_local_helper_llm = lambda payload: {
        "ok": True,
        "engine": "peft_lora_transformers",
        "llm_attempted": True,
        "output": f"Reviewed: {payload['order_text']}",
        "status": {"runtime_mode": "peft_lora_transformers"},
        "trained_lora_adapter": {"present": True},
    }
    node.record_persistent_memory_episode = lambda *_args, **_kwargs: {
        "ok": True,
        "status": "recorded",
        "mutation_performed": True,
    }

    require(node.DIRECT_WORK_ACTION in node.ALLOWED_ACTIONS, "direct action is not allowlisted")
    require(
        node.PARAM_ACTION_HANDLERS.get(node.DIRECT_WORK_ACTION) is node.action_direct_work_execute,
        "direct action is not routed to its handler",
    )
    source = inspect.getsource(node.action_direct_work_execute).lower()
    for forbidden in ("google drive", "main.shell", "subprocess", "powershell", "shared_room"):
        require(forbidden not in source, f"direct action contains forbidden transport/execution marker: {forbidden}")

    order_id = f"VERIFY-DIRECT-{uuid.uuid4().hex[:10]}"
    first = node.run_allowed_action(node.DIRECT_WORK_ACTION, {"work_order": order(order_id)})
    first_payload = decode(first)
    require(first.get("return_code") == 0, f"direct action failed: {first_payload}")
    require(first_payload.get("ok") is True, f"direct receipt not successful: {first_payload}")
    require(first_payload.get("transport") == "ct246_authenticated_direct_http", "wrong transport")
    require(first_payload.get("local_llm_attempted") is True, "local LLM proof missing")
    require(first_payload.get("worker_engine") == "peft_lora_transformers", "wrong worker engine")
    require(first_payload.get("persistent_memory", {}).get("status") == "recorded", "memory proof missing")
    require(first_payload.get("auto_apply") is False, "model output must remain review-only")
    require(Path(first_payload["incoming_file"]).is_file(), "incoming order was not persisted")
    require(Path(first_payload["done_file"]).is_file(), "done receipt was not persisted")
    require(Path(first_payload["receipt_file"]).is_file(), "audit receipt was not persisted")

    replay = node.run_allowed_action(node.DIRECT_WORK_ACTION, {"work_order": order(order_id)})
    replay_payload = decode(replay)
    require(replay.get("return_code") == 0, f"idempotent replay failed: {replay_payload}")
    require(replay_payload.get("idempotent_replay") is True, "replay was not identified")
    require(replay_payload.get("order_sha256") == first_payload.get("order_sha256"), "replay hash changed")

    collision = node.run_allowed_action(
        node.DIRECT_WORK_ACTION,
        {"work_order": order(order_id, "Different content under the same id.")},
    )
    require(collision.get("return_code") != 0, "same-id different-content collision was accepted")

    node.training_status_payload = lambda: {
        "schema": "engel_training_guard_v1",
        "observed_at_utc": node.utc_stamp(),
        "training_active": True,
        "training_process_ids": [9876],
    }
    guarded_id = f"VERIFY-GUARD-{uuid.uuid4().hex[:10]}"
    guarded = node.run_allowed_action(
        node.DIRECT_WORK_ACTION,
        {"work_order": order(guarded_id, "Build and install a new application.")},
    )
    guarded_payload = decode(guarded)
    require(guarded.get("return_code") != 0, "mutating work ran while training was active")
    require(guarded_payload.get("operator_status") == "deferred_training_active", "training deferral missing")
    require(guarded_payload.get("training_processes_unchanged") is True, "training process proof changed")
    require(guarded_payload.get("worker_engine") == "training-guard", "training guard engine missing")

    rejected = node.run_allowed_action(
        node.DIRECT_WORK_ACTION,
        {"work_order": {**order(f"VERIFY-WRONG-{uuid.uuid4().hex[:10]}"), "target": "android_worker"}},
    )
    rejected_payload = decode(rejected)
    require(rejected.get("return_code") != 0, "wrong-target order was accepted")
    require("does not target" in str(rejected_payload.get("error") or ""), "wrong-target reason missing")

    print("ENGEL_SUB_DIRECT_WORK_VERIFY_PASS")
    print(f"transport={first_payload['transport']}")
    print(f"worker_engine={first_payload['worker_engine']}")
    print("google_drive_used=false")
    print("shell_used=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
