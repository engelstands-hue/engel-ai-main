#!/usr/bin/env python3
"""Prove normal Electron chat cannot bypass CT246's canonical router."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import engel_main_local_model_worker as worker  # noqa: E402


def _forbidden(*_args: Any, **_kwargs: Any) -> Any:
    raise AssertionError("Electron chat called the direct provider failover")


def _exercise(payload: dict[str, Any]) -> dict[str, Any]:
    originals = {
        "fleet": worker._run_fleet_dispatch,
        "info": worker._is_info_question,
        "stream": worker._stream_server_chat,
        "server": worker._main_server_fast_chat,
        "failover": worker._run_failover_chat,
    }
    old_laptop_fallback = os.environ.get("ENGEL_MAIN_ALLOW_LAPTOP_LOCAL_FALLBACK")
    try:
        worker._run_fleet_dispatch = lambda *_args, **_kwargs: None
        worker._is_info_question = lambda *_args, **_kwargs: True
        worker._stream_server_chat = lambda *_args, **_kwargs: None
        worker._main_server_fast_chat = lambda *_args, **_kwargs: None
        worker._run_failover_chat = _forbidden
        os.environ["ENGEL_MAIN_ALLOW_LAPTOP_LOCAL_FALLBACK"] = "off"
        return worker._handle(payload)
    finally:
        worker._run_fleet_dispatch = originals["fleet"]
        worker._is_info_question = originals["info"]
        worker._stream_server_chat = originals["stream"]
        worker._main_server_fast_chat = originals["server"]
        worker._run_failover_chat = originals["failover"]
        if old_laptop_fallback is None:
            os.environ.pop("ENGEL_MAIN_ALLOW_LAPTOP_LOCAL_FALLBACK", None)
        else:
            os.environ["ENGEL_MAIN_ALLOW_LAPTOP_LOCAL_FALLBACK"] = old_laptop_fallback


def main() -> int:
    prompt = "Explain why rain forms in two clear sentences."
    for failover in (False, True):
        result = _exercise(
            {
                "id": f"ct-route-{int(failover)}",
                "command": "chat",
                "prompt": prompt,
                "stream": True,
                "failover": failover,
                "timeout": 10,
                "max_tokens": 64,
            }
        )
        assert result.get("ok") is False, result
        assert result.get("main_server_chat_service_required") is True, result
        assert result.get("failover_used") is not True, result

    wrapped = (
        "Engel code capability context: Preferred language lanes: C, Python. "
        "Use only the language relevant to the operator request.\n\n"
        "Operator request follows:\n"
        "A wall-panel shop drawing confirms the module widths and grid lines."
    )
    assert worker._operator_request_text(wrapped).startswith("A wall-panel"), wrapped
    assert worker._server_prompt_override_for_truth_route(
        worker._operator_request_text(wrapped)
    ).startswith("A wall-panel")

    class _Response:
        def __init__(self, body: bytes) -> None:
            self.body = body

        def __enter__(self) -> "_Response":
            return self

        def __exit__(self, *_args: Any) -> None:
            return None

        def read(self) -> bytes:
            return self.body

    captured: dict[str, Any] = {}
    original_urlopen = worker.urllib.request.urlopen
    try:
        def fake_urlopen(req: Any, **_kwargs: Any) -> _Response:
            captured.update(json.loads(req.data.decode("utf-8")))
            return _Response(
                json.dumps(
                    {
                        "ok": True,
                        "assistant_reply": "Safe work only.",
                        "receipt": {
                            "ok": True,
                            "provider": "local",
                            "runtime_provider": "ct246-local-gguf",
                            "persistent_chat_memory_appended": True,
                        },
                    }
                ).encode("utf-8")
            )

        worker.urllib.request.urlopen = fake_urlopen
        receipt = worker._main_server_fast_chat(
            wrapped,
            10,
            64,
            0.1,
            conversation_id="rog-ui-verifier",
        )
    finally:
        worker.urllib.request.urlopen = original_urlopen
    assert receipt is not None and receipt.get("ok") is True, receipt
    assert captured.get("prompt", "").startswith("A wall-panel"), captured
    assert "Engel code capability context:" not in captured.get("prompt", ""), captured
    assert (
        captured.get("metadata", {}).get("conversation_id")
        == "rog-ui-verifier"
    ), captured

    class _StreamResponse:
        def __iter__(self) -> Any:
            events = [
                {"activity": "quality_gated_local_chat", "elapsed_seconds": 1},
                {
                    "done": True,
                    "ok": False,
                    "assistant_reply": "The unsafe drafts were blocked.",
                    "receipt": {
                        "ok": False,
                        "status": "chat quality gate blocked unsafe drafts",
                        "assistant_reply": "The unsafe drafts were blocked.",
                        "training_sample_eligible": False,
                        "persistent_chat_memory_appended": True,
                    },
                },
            ]
            return iter(
                [("data: " + json.dumps(event) + "\n\n").encode("utf-8") for event in events]
                + [b"data: [DONE]\n\n"]
            )

        def close(self) -> None:
            return None

    original_urlopen = worker.urllib.request.urlopen
    try:
        worker.urllib.request.urlopen = lambda *_args, **_kwargs: _StreamResponse()
        blocked = worker._stream_server_chat(
            "Keep missing evidence open.",
            "blocked-stream-verifier",
            10,
            64,
            0.1,
            conversation_id="rog-ui-verifier",
        )
    finally:
        worker.urllib.request.urlopen = original_urlopen
    assert blocked is not None, blocked
    assert blocked.get("ok") is False, blocked
    assert blocked.get("assistant_reply") == "The unsafe drafts were blocked.", blocked

    print(
        json.dumps(
            {
                "ok": True,
                "schema": "engel_worker_ct_chat_route_verifier_v1",
                "normal_chat_requires_ct246": True,
                "legacy_failover_flag_requires_ct246": True,
                "ui_capability_wrapper_removed_before_ct246": True,
                "ct246_receipt_required_for_success": True,
                "desktop_conversation_id_forwarded": True,
                "canonical_quality_block_retry_suppressed": True,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
