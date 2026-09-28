#!/usr/bin/env python3
"""
Engel AI Main — usage & cost tracking.

Ported concept from OpenClaw (MIT) usage-cost tooling: record token usage per
provider/model and estimate spend. Local lanes (ROG GPU, CT246 local) are free;
cloud lanes are priced from an editable table. Pairs with engel_verbose's
/usage footer and the failover loop, so every AI turn can be logged and totalled.

Records append to runtime/usage/engel_usage.jsonl. `report` aggregates by
provider/model with an estimated cost.

Rates are approximate public $/1M-token (input, output) and are easy to edit;
they are an ESTIMATE, not a bill. MIT-attributed.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
USAGE_DIR = ROOT / "runtime" / "usage"
USAGE_LOG = USAGE_DIR / "engel_usage.jsonl"

# model/lane -> ($/1M input, $/1M output). Local lanes are free. Edit freely.
COST_PER_M = {
    "rog-rtx2070-gpu": (0.0, 0.0),
    "rog-rtx2070-llama-cpp-gpu": (0.0, 0.0),
    "ct246-local": (0.0, 0.0),
    "gemini-2.5-flash": (0.075, 0.30),
    "gemini-flash-latest": (0.075, 0.30),
    "sonnet": (3.0, 15.0),
    "grok-composer-2.5-fast": (0.20, 0.50),
    "gpt-5.4": (1.25, 10.0),
}


def estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    rate = COST_PER_M.get(model)
    if rate is None:
        # unknown cloud model: assume a modest default; local ids resolve to 0 above
        rate = (0.5, 1.5)
    inp, out = rate
    return round((prompt_tokens / 1_000_000) * inp + (completion_tokens / 1_000_000) * out, 6)


def record(provider: str, model: str, prompt_tokens: int, completion_tokens: int,
           lane: str = "", elapsed_ms: int = 0) -> dict:
    cost = estimate_cost(model, prompt_tokens, completion_tokens)
    rec = {
        "at_utc": datetime.now(timezone.utc).isoformat(),
        "provider": provider, "model": model, "lane": lane,
        "prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
        "est_cost_usd": cost, "elapsed_ms": elapsed_ms,
    }
    USAGE_DIR.mkdir(parents=True, exist_ok=True)
    with open(USAGE_LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec) + "\n")
    return rec


def record_from_run(run_result, prompt: str) -> dict:
    """Convenience: record from an engel_agent_failover_loop RunResult."""
    pt = max(1, len(prompt.split()))
    ct = max(1, len((run_result.reply or "").split()))
    model = getattr(run_result, "lane", "") or run_result.provider
    return record(run_result.provider, model, pt, ct, lane=run_result.lane, elapsed_ms=run_result.elapsed_ms)


def report() -> dict:
    if not USAGE_LOG.exists():
        return {"records": 0, "by_model": {}, "total_cost_usd": 0.0, "total_tokens": 0}
    by_model: dict[str, dict] = {}
    total_cost = 0.0
    total_tokens = 0
    n = 0
    for line in USAGE_LOG.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        n += 1
        m = r.get("model") or r.get("provider") or "?"
        agg = by_model.setdefault(m, {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "cost_usd": 0.0})
        agg["calls"] += 1
        agg["prompt_tokens"] += int(r.get("prompt_tokens", 0))
        agg["completion_tokens"] += int(r.get("completion_tokens", 0))
        agg["cost_usd"] = round(agg["cost_usd"] + float(r.get("est_cost_usd", 0.0)), 6)
        total_cost = round(total_cost + float(r.get("est_cost_usd", 0.0)), 6)
        total_tokens += int(r.get("total_tokens", 0))
    return {"records": n, "by_model": by_model, "total_cost_usd": round(total_cost, 4), "total_tokens": total_tokens}


def _cli(argv: Optional[list[str]] = None) -> int:
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    ap = argparse.ArgumentParser(description="Engel usage & cost tracking (OpenClaw usage-cost port).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    rc = sub.add_parser("record")
    rc.add_argument("--provider", required=True)
    rc.add_argument("--model", required=True)
    rc.add_argument("--prompt-tokens", type=int, required=True)
    rc.add_argument("--completion-tokens", type=int, required=True)
    sub.add_parser("report")
    a = ap.parse_args(argv)
    if a.cmd == "record":
        print(json.dumps(record(a.provider, a.model, a.prompt_tokens, a.completion_tokens), indent=2))
    elif a.cmd == "report":
        rep = report()
        print("=== Engel usage report ===")
        print(f"  records: {rep['records']}  total tokens: {rep['total_tokens']}  est cost: ${rep['total_cost_usd']}")
        for model, agg in sorted(rep["by_model"].items(), key=lambda kv: -kv[1]["cost_usd"]):
            print(f"  {model:28} calls={agg['calls']:3} tok={agg['prompt_tokens']}+{agg['completion_tokens']} "
                  f"${agg['cost_usd']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
