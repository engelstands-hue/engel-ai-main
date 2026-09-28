#!/usr/bin/env python3
"""Drop one prompt into Engel Flutter Main's visible Chat composer.

This is the operator-retry path: Engel types the text into its own composer
and presses Send through `_submitChatDraft`. Do not use
`run_engel_ui_chat_meeting_room_llm.py` for a retry the user should see.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
UI_CHAT_INBOX_REQUEST_DIR = ROOT / "runtime" / "ui_chat_inbox" / "requests"
UI_CHAT_INBOX_RESULT_DIR = ROOT / "runtime" / "ui_chat_inbox" / "results"


def iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def enqueue_visible_ui_chat_prompt(
    prompt: str,
    *,
    source: str = "operator_retry",
    metadata: dict[str, Any] | None = None,
    wait_accept_seconds: float = 0.0,
) -> dict[str, Any]:
    """Write one inbox request the Flutter Main chat watcher will Send."""
    text = str(prompt or "").strip()
    if not text:
        return {"ok": False, "accepted": False, "status": "empty prompt"}
    UI_CHAT_INBOX_REQUEST_DIR.mkdir(parents=True, exist_ok=True)
    UI_CHAT_INBOX_RESULT_DIR.mkdir(parents=True, exist_ok=True)
    unique = hashlib.sha1(
        f"{text}{time.time()}{os.getpid()}".encode("utf-8")
    ).hexdigest()[:8]
    request_id = f"retry_{stamp()}_p{os.getpid()}_{unique}"
    result_path = UI_CHAT_INBOX_RESULT_DIR / f"{request_id}.json"
    payload: dict[str, Any] = {
        "schema": "engel_ui_chat_inbox_request_v1",
        "request_id": request_id,
        "prompt": text,
        "source": source,
        "created_at_utc": iso_now(),
        "metadata": {
            "kind": "operator_retry" if source == "operator_retry" else source,
            "surface": "engel_flutter_main",
        },
    }
    if isinstance(metadata, dict) and metadata:
        merged = dict(payload["metadata"])
        merged.update(metadata)
        payload["metadata"] = merged
    temp_path = UI_CHAT_INBOX_REQUEST_DIR / f"{request_id}.json.tmp"
    temp_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    request_path = UI_CHAT_INBOX_REQUEST_DIR / f"{request_id}.json"
    temp_path.replace(request_path)
    record: dict[str, Any] = {
        "ok": True,
        "accepted": False,
        "request_id": request_id,
        "request_path": str(request_path),
        "result_path": str(result_path),
        "status": "queued for Engel Flutter Main chat composer",
        "prompt": text,
        "source": source,
    }
    if wait_accept_seconds <= 0:
        return record
    deadline = time.time() + wait_accept_seconds
    while time.time() < deadline:
        if result_path.is_file():
            try:
                accepted = json.loads(result_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                time.sleep(0.3)
                continue
            if accepted.get("accepted") is True:
                accepted["ok"] = True
                accepted["request_id"] = request_id
                accepted["request_path"] = str(request_path)
                accepted["result_path"] = str(result_path)
                return accepted
            accepted["ok"] = False
            accepted["request_id"] = request_id
            return accepted
        time.sleep(0.3)
    record["ok"] = False
    record["status"] = (
        "Engel Flutter Main did not pick the prompt up from the chat inbox "
        f"within {wait_accept_seconds:g}s (is Engel AI Main open on this UI?)"
    )
    return record


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Send one retry through Engel Flutter Main Chat, not the backend CLI"
    )
    parser.add_argument("prompt", nargs="+", help="text to type into the visible composer")
    parser.add_argument(
        "--wait-accept",
        type=float,
        default=90.0,
        help="seconds to wait for the app to accept the prompt (0 = queue only)",
    )
    args = parser.parse_args(argv)
    prompt = " ".join(args.prompt).strip()
    record = enqueue_visible_ui_chat_prompt(
        prompt,
        wait_accept_seconds=float(args.wait_accept or 0.0),
    )
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0 if record.get("ok") is True else 2


if __name__ == "__main__":
    raise SystemExit(main())
