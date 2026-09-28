#!/usr/bin/env python3
"""Prove Engel's chat is grounded in its own real state before training on it.

Born from the 2026-07-29 self-build prompt-training work. Asking the local model
about Engel's own architecture is only useful if the chat turn carries Engel's
real context. Without it a 7B model does not fail loudly -- it invents a plausible
product ("Engel architecture v3.0, released March 15 2022 (Engel's official
website)", an "Engel sales team", a $500,000 budget) with confident fake sources.
Training on that teaches Engel to hallucinate about itself, which is strictly
worse than not training at all.

So this gate asks one self-fact question through the real chat route and requires
BOTH:
  1. the receipt to show at least one grounding context input actually loaded; and
  2. the reply to contain a fact that is verifiably true of this deployment.

Exit 0 = safe to train. Non-zero = fix grounding first.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

DEFAULT_CHAT_URL = "http://127.0.0.1:24680/chat"

PROMPT = (
    "In one short sentence, name the host and container your chat runtime is "
    "running on right now."
)

# Facts that are true of this deployment and that a model with no context cannot
# guess. Any single hit proves the turn saw Engel's real state. The humanizer voice
# layer deliberately rewrites raw identifiers into Engel's own aliases ("the Engel
# server container" for CT 246), so BOTH forms count -- a gate that fails on a
# correct answer gets ignored, which is worse than having no gate.
GROUND_TRUTH_TOKENS = (
    "engel-ai-main",
    "/opt/engel",
    "192.0.2.50",
    "ct 246",
    "ct246",
    "proxmox",
    "dell poweredge",
    "engel server container",
    "local engel server",
)

# Any one of these means real context reached the model.
CONTEXT_FLAGS = (
    "persistent_chat_history_loaded",
    "merged_personality_loaded",
    "trusted_chat_memory_loaded",
    "semantic_quality_scoped_context_used",
    "humanizer_reference_loaded",
)

CHECKS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    CHECKS.append((name, bool(ok), detail))
    print(("PASS " if ok else "FAIL ") + name + (f"  ({detail})" if detail else ""))


def _post(url: str, payload: dict, timeout: float) -> tuple[int, dict]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, json.loads(response.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, {"_raw": raw[:800]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--chat-url", default=DEFAULT_CHAT_URL)
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--json", action="store_true", help="print the receipt summary")
    args = parser.parse_args()

    try:
        status, payload = _post(
            args.chat_url,
            {
                "message": PROMPT,
                "local_only_training": True,
                "requested_provider": "local",
            },
            args.timeout,
        )
    except Exception as exc:  # noqa: BLE001 - a gate reports, it does not raise
        check("chat_route_reachable", False, f"{type(exc).__name__}: {exc}")
        print("\n0/1 checks passed")
        return 1
    check("chat_route_reachable", True, f"HTTP {status}")

    receipt = payload.get("receipt") if isinstance(payload.get("receipt"), dict) else {}
    reply = str(
        payload.get("assistant_reply") or payload.get("reply") or ""
    ).strip()
    check("chat_returned_a_reply", bool(reply), f"{len(reply)} chars")

    loaded = [flag for flag in CONTEXT_FLAGS if receipt.get(flag) is True]
    check(
        "grounding_context_loaded",
        bool(loaded),
        ("loaded: " + ", ".join(loaded)) if loaded else "no context input reported loaded",
    )

    low_reply = reply.casefold()
    hits = [token for token in GROUND_TRUTH_TOKENS if token in low_reply]
    check(
        "reply_cites_a_real_deployment_fact",
        bool(hits),
        ("cited: " + ", ".join(hits)) if hits else f"no real fact in reply: {reply[:180]!r}",
    )

    if args.json:
        print(
            json.dumps(
                {
                    "schema": "engel_chat_grounding_gate_v1",
                    "chat_url": args.chat_url,
                    "http_status": status,
                    "context_inputs_loaded": loaded,
                    "ground_truth_hits": hits,
                    "reply_chars": len(reply),
                    "receipt_status": receipt.get("status"),
                },
                indent=2,
                sort_keys=True,
            )
        )

    failed = [name for name, ok, _ in CHECKS if not ok]
    print(f"\n{len(CHECKS) - len(failed)}/{len(CHECKS)} checks passed")
    if failed:
        print(
            "Engel chat is NOT grounded in its own state. Training on self-build "
            "prompts now would teach invented facts. Fix the chat context inputs first."
        )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
