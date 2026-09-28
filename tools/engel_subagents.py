#!/usr/bin/env python3
"""
Engel AI Main — sub-agents (sessions_spawn port).

Ported from OpenClaw (MIT): multi-agent routing + sessions_spawn. A top agent
fans work to independent sub-agents, each of which can run on a DIFFERENT AI
(its own failover chain). Every sub-agent is just an independent
engel_agent_failover_loop run, so each sub-task also escalates across providers.
Results are collected and can be synthesized by a final agent turn.

Reimplemented natively in Python; MIT-attributed.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, asdict
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engel_agent_failover_loop as _fl  # noqa: E402


@dataclass
class SubAgentResult:
    id: str
    task: str
    ok: bool
    reply: str
    lane: str
    provider: str
    elapsed_ms: int
    chain: str


def spawn_subagent(task: str, chain: Optional[list] = None, *, timeout_s: int = 60,
                   max_tokens: int = 512, agent_id: str = "") -> SubAgentResult:
    """Run one sub-task as an independent sub-agent (its own failover run)."""
    r = _fl.run_with_failover(task, chain=chain, timeout_s=timeout_s, max_tokens=max_tokens)
    return SubAgentResult(
        id=agent_id or ("sub-" + uuid.uuid4().hex[:6]),
        task=task, ok=r.ok, reply=r.reply, lane=r.lane, provider=r.provider,
        elapsed_ms=r.elapsed_ms, chain=",".join(chain) if chain else "default",
    )


def fan_out(subtasks: list[dict], *, timeout_s: int = 60, max_tokens: int = 512,
            max_workers: int = 4) -> list[SubAgentResult]:
    """Run many sub-agents in parallel. Each subtask = {task, chain?, id?}; each
    can target a different AI via its own chain."""
    with ThreadPoolExecutor(max_workers=max(1, min(max_workers, len(subtasks) or 1))) as ex:
        futs = [
            ex.submit(spawn_subagent, st["task"], st.get("chain"),
                      timeout_s=timeout_s, max_tokens=max_tokens, agent_id=st.get("id", ""))
            for st in subtasks
        ]
        return [f.result() for f in futs]


def orchestrate(main_task: str, subtasks: list[dict], *, synthesize: bool = True,
                synth_chain: Optional[list] = None, timeout_s: int = 60, max_tokens: int = 800) -> dict:
    """Fan `subtasks` to sub-agents, collect, then (optionally) have a final agent
    synthesize the answer to `main_task` from the sub-results."""
    results = fan_out(subtasks, timeout_s=timeout_s, max_tokens=max_tokens)
    out = {"main_task": main_task, "subagents": [asdict(r) for r in results]}
    if synthesize:
        joined = "\n\n".join(f"[sub-agent {r.id} via {r.provider}] {r.reply}" for r in results if r.ok)
        prompt = (f"{main_task}\n\nYou have these sub-agent results; synthesize one concise answer:\n{joined}")
        synth = _fl.run_with_failover(prompt, chain=synth_chain, timeout_s=timeout_s, max_tokens=max_tokens)
        out["synthesis"] = {"ok": synth.ok, "reply": synth.reply, "provider": synth.provider, "elapsed_ms": synth.elapsed_ms}
    return out


def _cli(argv: Optional[list[str]] = None) -> int:
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    ap = argparse.ArgumentParser(description="Engel sub-agents (sessions_spawn port).")
    ap.add_argument("--task", action="append", required=True, help="a sub-task (repeatable); form 'text' or 'chain=gemini-api|text'")
    ap.add_argument("--main", default="", help="main task to synthesize the sub-results into")
    ap.add_argument("--no-synth", action="store_true")
    args = ap.parse_args(argv)
    subtasks = []
    for t in args.task:
        if "|" in t and t.split("|", 1)[0].startswith("chain="):
            chain_part, text = t.split("|", 1)
            subtasks.append({"task": text, "chain": chain_part[len("chain="):].split(",")})
        else:
            subtasks.append({"task": t})
    if args.main:
        print(json.dumps(orchestrate(args.main, subtasks, synthesize=not args.no_synth), indent=2))
    else:
        for r in fan_out(subtasks):
            print(json.dumps(asdict(r), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
