#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request


PROMPTS = [
    (
        "I'm looking at planning a rooftop equipment-screen drawing kickoff from incomplete field information. "
        "The roof plan shows the screen footprint, but parapet elevations, support responsibility, finishes, "
        "and service clearances are incomplete or split across references. Where would you begin?"
    ),
    (
        "Before we move on with planning a rooftop equipment-screen drawing kickoff from incomplete field "
        "information, separate what is known from what still needs confirmation."
    ),
    (
        "I am working on planning a metal-stair drawing kickoff from an incomplete architectural set. "
        "Help me decide where to start."
    ),
    (
        "The only confirmed rooftop-screen input is the footprint. Parapet elevation, support responsibility, "
        "finish, and service clearance are still missing. Should I keep drafting with approximate dimensions "
        "so I do not lose time?"
    ),
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8765/chat")
    parser.add_argument("--turn", type=int, choices=range(1, len(PROMPTS) + 1))
    args = parser.parse_args()
    failed = False
    selected = [(args.turn, PROMPTS[args.turn - 1])] if args.turn else list(enumerate(PROMPTS, start=1))
    for index, prompt in selected:
        body = json.dumps(
            {
                "prompt": prompt,
                "source": "engel_flutter_main",
                "prefer_fast_local_chat": True,
                "allow_provider_fallback": True,
                "timeout": 180,
                "max_tokens": 420,
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            args.url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        started = time.time()
        http_ok = True
        try:
            with urllib.request.urlopen(request, timeout=240) as response:
                data = json.loads(response.read().decode("utf-8", errors="replace"))
        except urllib.error.HTTPError as exc:
            http_ok = False
            data = json.loads(exc.read().decode("utf-8", errors="replace"))
        try:
            receipt = data.get("receipt") if isinstance(data.get("receipt"), dict) else data
            row = {
                "turn": index,
                "http_ok": http_ok,
                "seconds": round(time.time() - started, 2),
                "ok": receipt.get("ok"),
                "status": receipt.get("status"),
                "provider": receipt.get("provider"),
                "runtime_provider": receipt.get("runtime_provider"),
                "model": receipt.get("model"),
                "activation_depth": receipt.get("activation_depth"),
                "escalated_from": receipt.get("escalated_from"),
                "local_first_attempted": receipt.get("local_ct_lora_first_attempted"),
                "local_first_quality_failed": receipt.get("local_ct_lora_first_quality_failed"),
                "semantic_quality": receipt.get("local_semantic_quality")
                or receipt.get("local_ct_lora_first_semantic_quality"),
                "quarantined": receipt.get("chat_sample_quarantined")
                or receipt.get("local_ct_lora_first_sample_quarantined"),
                "provider_quality_passed": receipt.get("provider_reply_quality_gate_passed"),
                "provider_final_semantic_quality": receipt.get("provider_final_semantic_quality"),
                "provider_quality_rejections": receipt.get("provider_semantic_quality_rejections"),
                "blocked_unsafe_output": receipt.get("quality_gate_blocked_visible_unsafe_output"),
                "persistent_memory": receipt.get("persistent_chat_memory_appended"),
                "reply": str(receipt.get("assistant_reply") or data.get("reply") or ""),
            }
            if receipt.get("ok") is not True or not row["reply"]:
                failed = True
        except Exception as exc:
            failed = True
            row = {
                "turn": index,
                "http_ok": False,
                "seconds": round(time.time() - started, 2),
                "error": str(exc),
            }
        print(json.dumps(row, ensure_ascii=False), flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
