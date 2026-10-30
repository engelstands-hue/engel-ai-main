#!/usr/bin/env python3
"""One OpenAI-compatible chat call for a provider that already has a secret.

The secret is a function argument. This module does not read it, log it, or
store it. Claude is not a provider here.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

OPENROUTER_CHAT_COMPLETIONS_URL = "https://openrouter.ai/api/v1/chat/completions"


def complete_chat(
    url: str,
    secret: str,
    prompt: str,
    request: dict[str, Any] | None = None,
    *,
    provider: str,
) -> dict[str, Any]:
    """POST one small chat completion. Returns the bridge result shape."""
    request = request if isinstance(request, dict) else {}
    model = str(request.get("model") or request.get("provider_model") or "").strip()
    if not str(secret or "").strip():
        return {
            "ok": False,
            "provider": provider,
            "assistant_reply": "",
            "error": f"{provider} bridge has no secret loaded",
            "attempts": [],
        }
    if not model:
        return {
            "ok": False,
            "provider": provider,
            "assistant_reply": "",
            "error": f"{provider} bridge has no model id",
            "attempts": [],
        }
    try:
        max_tokens = int(request.get("max_tokens") or request.get("max_completion_tokens") or 256)
    except (TypeError, ValueError):
        max_tokens = 256
    max_tokens = max(16, min(1024, max_tokens))
    try:
        temperature = float(request.get("temperature") or 0.2)
    except (TypeError, ValueError):
        temperature = 0.2
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": str(prompt or "")}],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    body = json.dumps(payload).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {secret}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://engel.local/model-parts",
        "X-Title": "Engel AI Main",
    }
    call = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(call, timeout=60) as response:
            raw = response.read().decode("utf-8", errors="replace")
            status = int(getattr(response, "status", 200) or 200)
    except urllib.error.HTTPError as exc:
        return {
            "ok": False,
            "provider": provider,
            "assistant_reply": "",
            "error": f"http {exc.code}",
            "attempts": [{"provider": provider, "model": model, "ok": False, "status_code": exc.code}],
        }
    except Exception as exc:
        return {
            "ok": False,
            "provider": provider,
            "assistant_reply": "",
            "error": type(exc).__name__,
            "attempts": [{"provider": provider, "model": model, "ok": False, "error": type(exc).__name__}],
        }
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {
            "ok": False,
            "provider": provider,
            "assistant_reply": "",
            "error": "response was not json",
            "attempts": [{"provider": provider, "model": model, "ok": False, "status_code": status}],
        }
    choices = data.get("choices") if isinstance(data, dict) else None
    message = {}
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        maybe = choices[0].get("message")
        if isinstance(maybe, dict):
            message = maybe
    reply = str(message.get("content") or "").strip()
    return {
        "ok": bool(reply),
        "provider": provider,
        "model": model,
        "assistant_reply": reply,
        "error": "" if reply else "empty reply",
        "attempts": [{"provider": provider, "model": model, "ok": bool(reply), "status_code": status}],
        "bridge_kind": "openai_compatible",
    }
