#!/usr/bin/env python3
import json
import urllib.error
import urllib.request


def post(payload, timeout=180):
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        "http://127.0.0.1:8765/chat",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode()
            return resp.status, json.loads(raw)
    except urllib.error.HTTPError as e:
        raw = e.read().decode(errors="replace")
        try:
            data = json.loads(raw) if raw else {}
        except Exception:
            data = {"raw": raw[:800]}
        return e.code, data


def summarize(label, code, data):
    print(f"=== {label} HTTP={code} ===")
    keep = {
        "ok": data.get("ok"),
        "status": data.get("status"),
        "provider": data.get("provider"),
        "runtime_provider": data.get("runtime_provider"),
        "selected_provider": (data.get("receipt") or {}).get("selected_provider")
        if isinstance(data.get("receipt"), dict)
        else data.get("selected_provider"),
        "reply": str(data.get("reply") or data.get("assistant_reply") or "")[:280],
        "failure_class": (data.get("receipt") or {}).get("failure_class")
        if isinstance(data.get("receipt"), dict)
        else None,
    }
    print(json.dumps(keep, sort_keys=True))


# 1) UI-style review ask (what Josh asked in Engel AI Main)
code, data = post(
    {
        "prompt": (
            "Review this and make sure we can send and receive real messages and comments "
            "in Engel AI Main. Be honest if something is broken."
        ),
        "max_tokens": 180,
        "timeout": 120,
        "source": "engel_ai_main_ui",
        "prefer_fast_local_chat": True,
    }
)
summarize("ui_review", code, data)

# 2) Short ping with UI source
code2, data2 = post(
    {
        "prompt": "Say only: ENGEL_MAIN_OK",
        "max_tokens": 24,
        "timeout": 90,
        "source": "engel_ai_main_ui",
        "prefer_fast_local_chat": True,
    }
)
summarize("ui_ping", code2, data2)
