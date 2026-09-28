#!/usr/bin/env python3
"""Owner Ask Engel must be an operator console, not a chat-only dead end."""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from engel_grok_cli_bridge_http_service import (  # noqa: E402
    _engel_prompt,
    normalize_discord_prompt,
    owner_prompt_is_discord_work,
    owner_prompt_is_operator_work,
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    grok = (ROOT / "tools" / "engel_grok_cli_bridge_http_service.py").read_text(encoding="utf-8")
    flutter = (ROOT / "engel_flutter_main" / "lib" / "main.dart").read_text(encoding="utf-8")
    worker = (ROOT / "tools" / "run_engel_ui_chat_meeting_room_llm.py").read_text(
        encoding="utf-8"
    )
    local_worker = (ROOT / "tools" / "engel_main_local_model_worker.py").read_text(
        encoding="utf-8"
    )
    service = (ROOT / "tools" / "engel_main_server_chat_http_service.py").read_text(
        encoding="utf-8"
    )
    require(
        owner_prompt_is_operator_work("Respond to Sub-Engel") is True,
        "Respond to Sub-Engel must be operator work",
    )
    require(
        owner_prompt_is_operator_work("fix discord collab") is True,
        "fix discord must be operator work",
    )
    require(
        owner_prompt_is_operator_work("what is a radio") is False,
        "casual questions stay chat",
    )
    require(
        owner_prompt_is_discord_work("Check out Discord Chat") is True,
        "Check out Discord Chat must use the live Discord bridge",
    )
    require(
        "discord" in normalize_discord_prompt("Check on The Dicord chat"),
        "Dicord typo must fold to discord",
    )
    require(
        owner_prompt_is_discord_work(
            "Check on The Dicord chat you keep repeating and not reading replies"
        )
        is True,
        "Dicord checkout must be Discord work",
    )
    require(
        owner_prompt_is_operator_work("Check out Discord Chat") is True,
        "Check out Discord Chat must be operator work",
    )
    require(
        owner_prompt_is_discord_work("what is discord") is False,
        "casual Discord questions stay chat",
    )
    require(
        "not an MCP server" in _engel_prompt("Check out Discord Chat", {}),
        "operator prompt must refuse the Discord MCP dodge",
    )
    require(
        "_owner_prompt_is_discord_checkout" in service
        and "_discord_checkout_turn" in service,
        "CT246 chat must intercept Discord checkout from live Engel bridge files",
    )
    require(
        "def _request_skips_operator_room_actions" in service
        and "if not source.startswith(\"discord\") and not _request_skips_operator_room_actions(request):"
        in service
        and '"training depth:" in text or "training task:" in text' in service,
        "training turns must stay on Chat and skip live Discord checkout",
    )
    require(
        "lowered.contains('training depth:')" in flutter
        and "lowered.contains('training task:')" in flutter,
        "Engel AI Main must not treat a training card as a Discord tab open",
    )
    require(
        "_chatPromptLooksLikeDiscordCheckout" in flutter,
        "Cosmic Swarm Ask Engel must detect Discord checkout",
    )
    require(
        "_owner_reply_to_sub_engel_chat_intercept" in local_worker
        and "_owner_discord_checkout_chat_intercept" in local_worker
        and local_worker.find("discord_checkout_reply = _owner_discord_checkout_chat_intercept")
        < local_worker.find("kernel_reply = _engel_agent_kernel_chat_intercept"),
        "Ask Engel reply-to-Sub-Engel must post to Discord before the agent kernel",
    )
    require(
        '"discord_posted": posted' in local_worker
        and "Did NOT post to Discord" in local_worker,
        "Ask Engel must not claim Discord reply done without a post",
    )
    require(
        "discordPosted != true" in flutter
        and "Did not post to Discord" in flutter,
        "Cosmic Swarm must not show Task completed without a Discord post",
    )
    require(
        "_owner_prompt_is_reply_to_sub_engel" in service
        and "/discord/reply-sub-engel" in service
        and "/discord/checkout" in service
        and "_normalize_discord_prompt" in service,
        "CT246 must own the Discord owner-reply post",
    )
    require(
        "operator console" in _engel_prompt("fix discord", {}),
        "operator prompt must name the operator console",
    )
    require(
        "Do not send him to a terminal" in _engel_prompt("fix discord", {}),
        "operator prompt must refuse terminal bounce",
    )
    require(
        "chat brain" in _engel_prompt("hello", {}),
        "casual chat still uses the chat-brain wrapper",
    )
    require(
        '"web_search,web_fetch,Agent"' in grok,
        "operator work must keep file/terminal tools",
    )
    require(
        "run_terminal_cmd,search_replace,web_search,web_fetch,Agent" in grok,
        "casual chat still blocks write/terminal tools",
    )
    require(
        'text.startswith("engel work")' in service and "is_work" in service,
        "CT246 Grok pipe must promote operator prompts to the build lane",
    )
    require(
        "_chatPromptLooksLikeOperatorWork" in flutter,
        "Cosmic Swarm Ask Engel must detect operator work",
    )
    require(
        "_agentWorkReviewPending || _chatPromptLooksLikeOperatorWork" in flutter,
        "Ask Engel Send must treat operator prompts as work",
    )
    require(
        r"fix|wire|pair|connect|repair|dispatch|collab|respond|install|launch" in worker,
        "UI chat worker must classify operator verbs as jobs",
    )
    print("PASS verify_engel_owner_operator_chat")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"FAIL verify_engel_owner_operator_chat: {exc}")
        raise SystemExit(2) from exc
