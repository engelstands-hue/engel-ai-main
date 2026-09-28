#!/usr/bin/env python3
"""
Engel AI Main — context compaction routes for long runs.

Ported from OpenClaw (MIT): PreemptiveCompactionRoute
(fits | compact_only | truncate_tool_results_only | compact_then_truncate) +
AgentContextPruningConfig (cache-ttl style pruning of old tool results). Keeps a
long, multi-turn / multi-tool run inside a token budget instead of growing the
context unbounded — the mechanism that lets a run "keep going" past context
limits (see engel_agent_failover_loop's outer loop).

A context is a list of message dicts: {role: user|assistant|tool|system, content: str}.
compact_context() estimates the budget, picks a route, applies it, and returns
the compacted messages + a receipt. Tool-result summarization can optionally use
a real LLM via a `summarizer` callback (e.g. engel_agent_failover_loop); the
default is a fast deterministic digest so this stays testable offline.

Reimplemented natively in Python; MIT-attributed.
"""
from __future__ import annotations

from typing import Callable, Optional

ROUTES = ("fits", "compact_only", "truncate_tool_results_only", "compact_then_truncate")


def estimate_tokens(text: str) -> int:
    """Cheap token estimate (~4 chars/token), matching OpenClaw's coarse budgeting."""
    return max(1, len(text or "") // 4)


def total_tokens(messages: list[dict]) -> int:
    return sum(estimate_tokens(str(m.get("content") or "")) for m in messages)


def plan_compaction(messages: list[dict], budget_tokens: int, pressure: float = 0.9) -> str:
    """Pick a PreemptiveCompactionRoute for the given context + budget."""
    limit = int(budget_tokens * pressure)
    used = total_tokens(messages)
    if used <= limit:
        return "fits"
    tool_toks = sum(estimate_tokens(str(m.get("content") or "")) for m in messages if m.get("role") == "tool")
    # If tool results dominate, trim them first; if that alone can't fit, do both.
    if tool_toks >= 0.4 * used:
        # would truncating tool results to a floor get us under budget?
        non_tool = used - tool_toks
        if non_tool <= limit:
            return "truncate_tool_results_only"
        return "compact_then_truncate"
    return "compact_only"


def truncate_tool_results(messages: list[dict], keep_last: int = 2, max_chars: int = 1200) -> list[dict]:
    """Cache-ttl style pruning: the newest `keep_last` tool results stay full;
    older tool results are trimmed to `max_chars` with a truncation notice."""
    tool_idxs = [i for i, m in enumerate(messages) if m.get("role") == "tool"]
    keep = set(tool_idxs[-keep_last:]) if keep_last > 0 else set()
    out = []
    for i, m in enumerate(messages):
        if m.get("role") == "tool" and i not in keep:
            c = str(m.get("content") or "")
            if len(c) > max_chars:
                trimmed = c[:max_chars]
                m = {**m, "content": trimmed + f"\n…[tool result truncated, {len(c)-max_chars} chars pruned]"}
        out.append(m)
    return out


def _deterministic_digest(messages: list[dict]) -> str:
    lines = []
    for m in messages:
        role = m.get("role", "?")
        content = str(m.get("content") or "").strip().replace("\n", " ")
        head = content[:140] + ("…" if len(content) > 140 else "")
        lines.append(f"- {role}: {head}")
    return "Earlier conversation (compacted):\n" + "\n".join(lines)


def compact_messages(messages: list[dict], keep_last: int = 6,
                     summarizer: Optional[Callable[[str], str]] = None) -> list[dict]:
    """Replace older turns with a single compacted summary message, keeping the
    most recent `keep_last`. Uses `summarizer(text)->str` (e.g. an LLM) if given,
    else a deterministic digest."""
    if len(messages) <= keep_last:
        return messages
    system = [m for m in messages if m.get("role") == "system"]
    body = [m for m in messages if m.get("role") != "system"]
    if len(body) <= keep_last:
        return messages
    older, recent = body[:-keep_last], body[-keep_last:]
    raw = "\n".join(f"{m.get('role')}: {m.get('content')}" for m in older)
    try:
        summary = summarizer(raw) if summarizer else _deterministic_digest(older)
    except Exception:
        summary = _deterministic_digest(older)
    compacted = {"role": "system", "content": summary, "compacted": True, "compacted_from": len(older)}
    return system + [compacted] + recent


def compact_context(messages: list[dict], budget_tokens: int = 6000, *,
                    pressure: float = 0.9, keep_last: int = 6,
                    tool_keep_last: int = 2, tool_max_chars: int = 1200,
                    summarizer: Optional[Callable[[str], str]] = None) -> dict:
    """Plan + apply compaction to fit `budget_tokens`. Returns
    {messages, route, before_tokens, after_tokens, budget}."""
    before = total_tokens(messages)
    route = plan_compaction(messages, budget_tokens, pressure)
    out = list(messages)
    if route in ("truncate_tool_results_only", "compact_then_truncate"):
        out = truncate_tool_results(out, tool_keep_last, tool_max_chars)
    if route in ("compact_only", "compact_then_truncate"):
        out = compact_messages(out, keep_last, summarizer)
    return {
        "messages": out, "route": route,
        "before_tokens": before, "after_tokens": total_tokens(out),
        "budget": budget_tokens, "saved_tokens": before - total_tokens(out),
    }


if __name__ == "__main__":
    # Self-test with a synthetic long context (a few big tool results + many turns).
    msgs = [{"role": "system", "content": "You are Engel."}]
    for i in range(10):
        msgs.append({"role": "user", "content": f"user question number {i} " * 20})
        msgs.append({"role": "assistant", "content": f"assistant answer number {i} " * 20})
        if i % 3 == 0:
            msgs.append({"role": "tool", "content": ("TOOL OUTPUT LINE " * 400)})  # big tool result
    for budget in (20000, 6000, 2000):
        res = compact_context(msgs, budget_tokens=budget)
        print(f"budget={budget:5d}  route={res['route']:26s} {res['before_tokens']}->{res['after_tokens']} tok "
              f"(saved {res['saved_tokens']}, msgs {len(msgs)}->{len(res['messages'])})")
