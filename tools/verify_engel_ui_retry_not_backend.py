#!/usr/bin/env python3
"""Retries of Sub-Engel-check + last app build must go through Flutter Main Chat."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
for entry in (str(ROOT), str(TOOLS)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import engel_build_lane as build_lane
import engel_main_local_model_worker as worker
import engel_main_server_chat_http_service as chat
import enqueue_engel_ui_chat as ui_inbox


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    retry_prompt = "Check again Sub-Engel says it is connected. Then Continue."
    flutter_retry = (
        "Check again Sub-Engel says it is connected. Then overwrite and rebuild: "
        "Recreate this using Flutter."
    )
    require(
        build_lane.is_continue_or_retry_build_request(retry_prompt) is True,
        "check-again + continue is not a UI retry/build order",
    )
    require(
        build_lane.is_continue_or_retry_build_request("please continue") is False,
        "bare continue became a build retry",
    )
    require(
        worker._requested_router_work_order(retry_prompt) is True,
        "Flutter worker would still stream the retry to Cosmic Swarm/Grok",
    )
    require(
        chat._prompt_is_router_work_order(retry_prompt) is True,
        "chat service would still let force_provider send the retry to Grok",
    )
    require(
        build_lane.is_build_request(flutter_retry) is not None,
        "explicit Flutter recreate retry is not a build order",
    )
    last = build_lane.resolve_last_incomplete_build_request()
    if last:
        continued = build_lane.resolve_continued_build_request(retry_prompt)
        require(continued is not None, "retry did not resolve the last app build")
        require(
            "overwrite and rebuild" in continued.casefold(),
            f"retry did not keep overwrite rebuild wording: {continued!r}",
        )
        require(
            worker._requested_app_build(retry_prompt) == continued,
            "worker still treats the UI retry as ordinary chat",
        )
    service_src = (TOOLS / "engel_main_server_chat_http_service.py").read_text(encoding="utf-8")
    live_at = service_src.find(
        "if not strict_local_llm_training and _prompt_requests_live_runtime_status(prompt):"
    )
    nested_at = service_src.find("if not _prompt_is_router_work_order(prompt, request):")
    grok_at = service_src.find("_explicit_provider_bridge_requested(prompt, request)")
    require(live_at != -1 and nested_at != -1 and grok_at != -1, "live/router/Grok markers missing")
    require(live_at < nested_at < grok_at, "retry/build can still lose to a live-status-only Grok skip")
    require("i'll verify" in service_src.casefold(), "promise detector missing I'll verify")
    dart = (ROOT / "engel_flutter_main" / "lib" / "main.dart").read_text(encoding="utf-8")
    require("_drainUiChatInbox" in dart, "Flutter inbox drain missing")
    require("await _submitChatDraft(inboxMetadata: inboxMetadata);" in dart, "inbox retry does not Send")
    require("Retry in chat composer" in dart, "operator retry is still labeled as training")
    inbox_src = (TOOLS / "enqueue_engel_ui_chat.py").read_text(encoding="utf-8")
    require("ui_chat_inbox" in inbox_src, "visible UI inbox helper missing")
    require("run_engel_ui_chat_meeting_room_llm" in inbox_src, "helper must name the backend path it avoids")
    require(
        ui_inbox.UI_CHAT_INBOX_REQUEST_DIR == ROOT / "runtime" / "ui_chat_inbox" / "requests",
        "UI inbox is not the Flutter Main chat inbox",
    )
    print("ENGEL_UI_RETRY_NOT_BACKEND_VERIFY_PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"FAIL verify_engel_ui_retry_not_backend: {exc}")
        raise SystemExit(2) from exc
