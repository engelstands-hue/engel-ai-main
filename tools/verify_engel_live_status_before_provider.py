#!/usr/bin/env python3
"""Live 'what I'm actually running' must probe CT246, not ask Grok to check later."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / "tools" / "engel_main_server_chat_http_service.py"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    source = SERVICE.read_text(encoding="utf-8")
    require(
        "what i'm actually running" in source.casefold()
        or "what i am actually running" in source.casefold(),
        "live-status detector missing Cosmic Swarm button phrase",
    )
    require("live evidence" in source.casefold(), "live-status detector missing live-evidence phrase")
    require("def _reply_is_status_promise(" in source, "promise detector missing")
    require("No self-upgrade cycle ran from this message" in source, "live reply must not fake a cycle")
    require(
        "I will not call backlog names current work without a current receipt" in source,
        "live reply must not advertise the stale executor backlog as running work",
    )
    live_at = source.find("if not strict_local_llm_training and _prompt_requests_live_runtime_status(prompt):")
    grok_at = source.find("_explicit_provider_bridge_requested(prompt, request)")
    require(live_at != -1 and grok_at != -1, "live-status or provider markers missing")
    require(live_at < grok_at, "live status still sits after Grok/provider")
    require('"ct_live_status_chat": 0' in source, "live status must be depth 0")
    print("PASS verify_engel_live_status_before_provider")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"FAIL verify_engel_live_status_before_provider: {exc}")
        raise SystemExit(2) from exc
