#!/usr/bin/env python3
"""Offline proof for the CT246 authenticated direct Sub-Engel route."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for item in (ROOT, ROOT / "tools"):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

import run_engel_ui_chat_meeting_room_llm as bridge  # noqa: E402


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="engel_sub_direct_verify_") as temp:
        calls: list[dict] = []

        def fake_run_action(action, **kwargs):
            calls.append({"action": action, **kwargs})
            direct = {
                "ok": True,
                "worker_engine": "local_llm_one_shot",
                "local_llm_attempted": True,
                "local_llm_completed": True,
                "worker_output": "review-only local-model Sub result",
            }
            return {
                "ok": True,
                "result": {
                    "return_code": 0,
                    "stdout": json.dumps(direct, indent=2, sort_keys=True),
                },
            }

        order = {
            "id": "TEST-SUB-DIRECT",
            "expected_return_folder": temp,
        }
        selected = {"node_id": "DESKTOP-UE5A6GG", "url": "http://sub.invalid:8776"}
        result = bridge._run_direct_sub_engel_work(
            "Review this modular floor-plan input list.", order, selected, fake_run_action
        )
        assert result.get("ok") is True and result.get("returned") is True, result
        assert calls and calls[0]["action"] == "direct_work.execute", calls
        sent_order = (calls[0].get("payload") or {}).get("work_order") or {}
        assert sent_order.get("order_text") == "Review this modular floor-plan input list."
        assert "command" not in (calls[0].get("payload") or {}), "direct work must not use a shell command"
        path = Path(str(result.get("path") or ""))
        packet = json.loads(path.read_text(encoding="utf-8"))
        assert packet["order_id"] == "TEST-SUB-DIRECT"
        assert packet["transport"] == "ct246_authenticated_direct_http"
        assert packet["model_output_trusted"] is False
        assert packet["auto_apply"] is False
        def fake_timeout(action, **kwargs):
            direct = {
                "ok": False,
                "worker_engine": "structured_worker_fallback",
                "local_llm_attempted": True,
                "local_llm_completed": False,
                "worker_output": "deterministic fallback",
            }
            return {
                "ok": False,
                "result": {"return_code": 3, "stdout": json.dumps(direct)},
            }

        failed = bridge._run_direct_sub_engel_work(
            "Review this timed-out request.", order, selected, fake_timeout
        )
        assert failed.get("ok") is False, failed

        original_root = bridge.ROOT
        original_resolver = bridge._ct246_authenticated_run_action
        original_post_json = bridge._post_json
        try:
            bridge.ROOT = Path(temp)
            bridge._ct246_authenticated_run_action = lambda: fake_run_action
            bridge._post_json = lambda *_args, **_kwargs: (_ for _ in ()).throw(
                AssertionError("CT246 direct dispatch looped back into its own HTTP listener")
            )
            in_process = bridge._create_sub_engel_work_dispatch(
                "Review this CT246 in-process Sub-Engel request."
            )
        finally:
            bridge.ROOT = original_root
            bridge._ct246_authenticated_run_action = original_resolver
            bridge._post_json = original_post_json
        assert in_process.get("ok") is True, in_process
        assert in_process.get("returned") is True, in_process
        assert (
            in_process.get("dispatch_transport")
            == "ct246_in_process_authenticated_action"
        ), in_process
    print("PASS: CT246 direct Sub route requires a completed local-model return")
    print("PASS: CT246 dispatch uses its paired node client without HTTP self-loopback")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
