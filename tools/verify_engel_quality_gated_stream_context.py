#!/usr/bin/env python3
"""Prove desktop SSE chat uses CT246's canonical gate and isolated context."""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import engel_main_server_chat_http_service as service  # noqa: E402


class _FakeHandler:
    def __init__(self) -> None:
        self.wfile = io.BytesIO()
        self.status = 0

    def send_response(self, status: int) -> None:
        self.status = status

    def send_header(self, *_args: Any) -> None:
        return None

    def end_headers(self) -> None:
        return None


def main() -> int:
    request = {
        "prompt": "Compare the evidence for the same curb-adapter survey package.",
        "source": "engel_ai_main_ui",
        "client": "rog_desktop_controller",
        "provider": "local",
        "metadata": {"conversation_id": "rog-ui-verifier"},
    }
    expected_scope = "engel_ai_main_desktop:rog-ui-verifier"
    assert service._chat_context_scope(request) == expected_scope

    originals = {
        "read_json": service._read_json,
        "run_chat_turn": service._run_chat_turn,
        "recent": service._recent_chat_context,
        "semantic": service._semantic_memory_context,
        "append": service._append_jsonl,
        "quick_request": service._request_prefers_quick_local_chat,
        "quick_prompt": service._prompt_requests_short_casual_fast_model,
        "default_fast": service._prompt_allows_default_fast_local_chat,
        "live": service._prompt_requests_live_runtime_status,
        "build": service._prompt_requests_build_status,
        "reps": service._prompt_requests_reps_template,
        "media": service._prompt_requests_media_artifact,
        "bridge": service._explicit_provider_bridge_requested,
        "buffered": service._prompt_requires_buffered_quality_gate,
        "single": service._prompt_requests_single_sentence,
    }
    calls: list[str] = []

    def fake_recent(*_args: Any, **kwargs: Any) -> str:
        assert kwargs.get("context_scope") == expected_scope, kwargs
        return "User: Establish the curb location first.\nAssistant: Use the survey control line."

    try:
        service._recent_chat_context = fake_recent
        service._semantic_memory_context = lambda *_args, **_kwargs: "FORBIDDEN DISCORD PUMP-SMOKE CONTEXT"
        context = service._big_lane_memory(request["prompt"], request)
        assert "survey control line" in context, context
        assert "FORBIDDEN DISCORD" not in context, context

        semantic_calls: list[str] = []
        service._recent_chat_context = lambda *_args, **_kwargs: ""
        service._semantic_memory_context = lambda value: semantic_calls.append(value) or "FORBIDDEN GLOBAL RECALL"
        first_turn_context = service._big_lane_memory(
            "Start an unrelated isolated desktop review.",
            request,
        )
        assert "FORBIDDEN GLOBAL RECALL" not in first_turn_context, first_turn_context
        assert not semantic_calls, semantic_calls

        discord_new_topic_request = {
            "source": "discord",
            "metadata": {"discord_channel_id": "room", "discord_author_id": "owner"},
        }
        new_topic_context = service._big_lane_memory(
            "Engel, open a different chat topic: verifying a new inspection log.",
            discord_new_topic_request,
        )
        assert "FORBIDDEN GLOBAL RECALL" not in new_topic_context, new_topic_context
        assert not semantic_calls, semantic_calls

        service._read_json = lambda *_args, **_kwargs: dict(request)
        service._append_jsonl = lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("stream handler attempted a second direct memory write")
        )
        for name in (
            "_request_prefers_quick_local_chat",
            "_prompt_requests_short_casual_fast_model",
            "_prompt_allows_default_fast_local_chat",
            "_prompt_requests_live_runtime_status",
            "_prompt_requests_build_status",
            "_prompt_requests_reps_template",
            "_prompt_requests_media_artifact",
            "_explicit_provider_bridge_requested",
            "_prompt_requires_buffered_quality_gate",
            "_prompt_requests_single_sentence",
        ):
            setattr(service, name, lambda *_args, **_kwargs: False)

        def fake_turn(prompt: str, turn_request: dict[str, Any], _started: float) -> tuple[dict[str, Any], str]:
            calls.append(prompt)
            assert service._chat_context_scope(turn_request) == expected_scope
            reply = "The accepted local answer keeps the survey evidence scoped."
            return (
                {
                    "ok": True,
                    "status": "quality gate passed",
                    "assistant_reply": reply,
                    "provider": "local-gguf",
                    "runtime_provider": "ct246-local-gguf",
                    "training_sample_eligible": True,
                    "persistent_chat_memory_appended": True,
                    "chat_context_scope": expected_scope,
                },
                reply,
            )

        service._run_chat_turn = fake_turn
        handler = _FakeHandler()
        service.Handler._handle_chat_stream_inner(handler)
        output = handler.wfile.getvalue().decode("utf-8")
        assert handler.status == 200, handler.status
        assert len(calls) == 1, calls
        assert "local-llama-cpp-large-chat-gguf-stream" not in output, output
        events = []
        for line in output.splitlines():
            if not line.startswith("data: ") or line == "data: [DONE]":
                continue
            events.append(json.loads(line[6:]))
        done = next(item for item in events if item.get("done") is True)
        assert done.get("ok") is True, done
        assert done.get("receipt", {}).get("training_sample_eligible") is True, done
    finally:
        service._read_json = originals["read_json"]
        service._run_chat_turn = originals["run_chat_turn"]
        service._recent_chat_context = originals["recent"]
        service._semantic_memory_context = originals["semantic"]
        service._append_jsonl = originals["append"]
        service._request_prefers_quick_local_chat = originals["quick_request"]
        service._prompt_requests_short_casual_fast_model = originals["quick_prompt"]
        service._prompt_allows_default_fast_local_chat = originals["default_fast"]
        service._prompt_requests_live_runtime_status = originals["live"]
        service._prompt_requests_build_status = originals["build"]
        service._prompt_requests_reps_template = originals["reps"]
        service._prompt_requests_media_artifact = originals["media"]
        service._explicit_provider_bridge_requested = originals["bridge"]
        service._prompt_requires_buffered_quality_gate = originals["buffered"]
        service._prompt_requests_single_sentence = originals["single"]

    print(
        json.dumps(
            {
                "ok": True,
                "schema": "engel_quality_gated_stream_context_verifier_v1",
                "canonical_stream_turns": len(calls),
                "direct_stream_memory_write": False,
                "desktop_conversation_scope": expected_scope,
                "cross_surface_semantic_bleed_blocked": True,
                "isolated_first_turn_global_recall_blocked": True,
                "explicit_new_topic_global_recall_blocked": True,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
