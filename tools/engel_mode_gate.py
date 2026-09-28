#!/usr/bin/env python3
"""Engel mode gate — route chat by TYPE of thinking, not topic.

Implements the salience-network analog from /opt/engel/memory/cognitive_routing_model.md
(designed by Joshua + Engel in the Discord thread, night of 2026-07-03/04):

    mode gate first, model second.

Modes:
  reflex        greetings / confirmations / single-word turns -> small local model,
                no reasoning pass
  memory_recall "what did we decide about X" -> nomic-embed semantic search FIRST;
                a high-score hit can BE the answer
  convergent    step-by-step derivation, code, formal verification -> full lane,
                chain-of-thought on (default cascade already leads with these)
  divergent     brainstorming / open conversation / creative framing -> chat lane,
                higher temperature, no forced reasoning pass

Safety contract:
  * OFF unless ENGEL_MODE_GATE_ENABLED=1 (systemd drop-in; delete drop-in = revert).
  * Fail-open: any exception inside the gate returns mode "unknown" and the chat
    service continues its normal cascade untouched.
  * Every decision is annotated into the turn receipt (mode_gate section) so the
    dispatch can be tuned from real data instead of guesses.
  * v1 classification is deterministic heuristics (zero added latency). The
    classify_with_model() hook exists for the 0.5B classifier upgrade but is not
    called unless ENGEL_MODE_GATE_LLM_CLASSIFIER=1.
"""
from __future__ import annotations

import json
import os
import re
import urllib.request
from typing import Any

MEMORY_SEARCH_URL = os.environ.get(
    "ENGEL_MODE_GATE_MEMORY_URL", "http://127.0.0.1:8940/search"
)
MEMORY_SCORE_THRESHOLD = float(os.environ.get("ENGEL_MODE_GATE_MEMORY_SCORE", "0.60"))


def gate_enabled() -> bool:
    return str(os.environ.get("ENGEL_MODE_GATE_ENABLED", "")).strip().lower() in {
        "1", "true", "yes", "on",
    }


# --------------------------------------------------------------------------- modes

_REFLEX_EXACT = {
    "hi", "hello", "hey", "yo", "sup", "good morning", "good evening",
    "good night", "gm", "gn", "ok", "okay", "k", "kk", "yes", "no", "yep",
    "nope", "yeah", "nah", "thanks", "thank you", "ty", "thx", "cool",
    "nice", "great", "lol", "haha", "wow", "hmm", "sure", "fine", "got it",
    "sounds good", "roger", "copy", "done", "stop", "wait", "continue", "go",
}

_MEMORY_PATTERNS = re.compile(
    r"\b(what did (we|you|i) (decide|say|talk|agree)|do you remember|"
    r"remind me (what|about|of)|what was (the|our|that)|did we (already|ever)|"
    r"what have (we|you) (done|built|saved)|where did (we|you) (put|save|leave)|"
    r"recall|from (our|the) (last|previous|earlier) (chat|conversation|session|thread))\b",
    re.I,
)

_CONVERGENT_PATTERNS = re.compile(
    r"\b(prove|derive|calculate|compute|solve|debug|fix this|step[- ]by[- ]step|"
    r"exactly|verify|check (this|whether|if)|write (a |the )?(code|function|script|"
    r"class|test)|refactor|implement|algorithm|equation|integral|derivative|"
    r"formal|theorem|why does .* fail|root cause|stack ?trace|error message)\b",
    re.I,
)

_DIVERGENT_PATTERNS = re.compile(
    r"\b(brainstorm|ideas? for|imagine|what if|could we|creative|meme|joke|story|"
    r"name (for|ideas)|riff on|explore|possibilities|wild|fun way|how might)\b",
    re.I,
)


def classify_mode(prompt: str) -> dict[str, Any]:
    """Deterministic heuristic classification. Returns a dict with mode,
    confidence, and the signal that fired. Never raises."""
    try:
        text = " ".join((prompt or "").split()).strip()
        low = text.lower().rstrip("!?. ")
        words = low.split()
        if low in _REFLEX_EXACT or (len(words) <= 2 and len(low) <= 14 and not _MEMORY_PATTERNS.search(low)):
            return {"mode": "reflex", "confidence": 0.9, "signal": "short-social"}
        if _MEMORY_PATTERNS.search(low):
            return {"mode": "memory_recall", "confidence": 0.8, "signal": "recall-phrase"}
        convergent = bool(_CONVERGENT_PATTERNS.search(low))
        divergent = bool(_DIVERGENT_PATTERNS.search(low))
        if convergent and not divergent:
            return {"mode": "convergent", "confidence": 0.7, "signal": "analytic-verb"}
        if divergent and not convergent:
            return {"mode": "divergent", "confidence": 0.7, "signal": "associative-verb"}
        if convergent and divergent:
            # exploring a technical idea: divergent framing wins (explore vs verify)
            return {"mode": "divergent", "confidence": 0.55, "signal": "mixed-explore"}
        return {"mode": "unknown", "confidence": 0.0, "signal": "no-heuristic-match"}
    except Exception as exc:  # fail-open, always
        return {"mode": "unknown", "confidence": 0.0, "signal": f"gate-error:{exc}"}


def classify_with_model(prompt: str) -> dict[str, Any] | None:
    """Optional 0.5B LLM classifier upgrade path. Disabled unless
    ENGEL_MODE_GATE_LLM_CLASSIFIER=1; v1 intentionally ships heuristics-only."""
    if str(os.environ.get("ENGEL_MODE_GATE_LLM_CLASSIFIER", "")).strip() != "1":
        return None
    return None  # reserved for the next iteration


# --------------------------------------------------------------------------- memory lane

def memory_search(query: str, k: int = 4, timeout: float = 8.0) -> list[dict[str, Any]]:
    """Query the nomic-embed semantic memory service. Returns [] on any failure."""
    try:
        body = json.dumps({"query": query, "k": k}).encode("utf-8")
        req = urllib.request.Request(
            MEMORY_SEARCH_URL, data=body, headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        hits = data.get("results") or data.get("hits") or []
        return [h for h in hits if isinstance(h, dict)]
    except Exception:
        return []


def memory_recall_reply(prompt: str) -> dict[str, Any] | None:
    """If semantic memory answers the recall question confidently, compose an
    answer FROM memory (the embed result is the answer). Returns None when
    memory is not confident enough — caller falls through to the normal lane."""
    hits = memory_search(prompt)
    if not hits:
        return None
    top = hits[0]
    try:
        score = float(top.get("score") or 0.0)
    except (TypeError, ValueError):
        return None
    if score < MEMORY_SCORE_THRESHOLD:
        return None
    lines = ["From Engel's memory:"]
    cited: list[str] = []
    for hit in hits[:3]:
        try:
            if float(hit.get("score") or 0.0) < MEMORY_SCORE_THRESHOLD - 0.08:
                continue
        except (TypeError, ValueError):
            continue
        text = " ".join(str(hit.get("text") or "").split())
        source = str(hit.get("source") or "memory")
        if text:
            lines.append(f"- {text[:400]}  (source: {source})")
            cited.append(source)
    if len(lines) == 1:
        return None
    lines.append(
        "That is what is saved. Want me to expand on any part or update it?"
    )
    return {
        "reply": "\n".join(lines),
        "top_score": score,
        "sources": cited,
        "hit_count": len(cited),
    }


# --------------------------------------------------------------------------- dispatch hints

def dispatch_hints(mode: str, request: dict[str, Any]) -> dict[str, Any]:
    """Non-destructive request hints per mode. Only fills values the caller
    did not explicitly set."""
    hints: dict[str, Any] = {}
    if mode == "divergent" and not request.get("temperature"):
        hints["temperature"] = 0.45
    if mode == "convergent" and not request.get("temperature"):
        hints["temperature"] = 0.15
    if mode == "reflex" and not request.get("max_tokens"):
        hints["max_tokens"] = 160
    return hints
