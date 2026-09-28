#!/usr/bin/env python3
"""Engel neuro/self-upgrade DRILL SESSION — sustained training through the
real chat lane.

Sends bounded rounds of catalog-grounded questions about the governed
self-upgrade system and the neuron-transfer system to the live chat service,
scores each reply against expected keywords, and writes a session receipt.
Every turn also lands in persistent chat memory + chat receipts, so the
session feeds the daily training-dataset flywheel with real exemplars.

Read/ask only: no source mutation, no trusted-memory write, no dispatch.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECEIPT_DIR = ROOT / "reports" / "llm_training" / "drill_sessions"

# (question, [expected keyword alternatives — ANY hit scores the check])
DRILLS = [
    ("Which tool runs your governed self-upgrade cycle?", ["engel_conical_self_upgrade_cycle"]),
    ("Where is your self-upgrade routing catalog?", ["ENGEL_SELF_UPGRADE_SYSTEM_CATALOG", "catalog_router"]),
    ("What is your self-patch quorum?", ["pre-apply", "veto", "five", "members", "quorum"]),
    ("What happens when a patch fails its verifiers after deploy?", ["rollback", "restore", "backup"]),
    ("How do you decide which phone gets work?", ["broker", "eligible", "fresh", "paired"]),
    ("Which device is forbidden from receiving work?", ["FIB17O7", "fib17o7", "forbidden"]),
    ("What are your provider pipes?", ["bridge", "tunnel", "24883", "24885", "24887", "24889", "loopback"]),
    ("What happens to failed conical jobs?", ["issue", "intake", "deduped", "bounded"]),
    ("What is NT-1 in your neuron transfer system?", ["activation depth", "depth", "label"]),
    ("What is NT-2?", ["escalat", "threshold", "confidence", "tau", "quick"]),
    ("What is NT-3?", ["retrieve-once", "memo", "recall", "once"]),
    ("What does activation depth 2 mean?", ["big lane", "big-lane", "GPU", "rog"]),
    ("What does runs_inference false mean on a reply?", ["no model", "deterministic", "template", "without the model"]),
    ("Where do you see your neuron telemetry?", ["Self-Upgrade Loop", "panel", "loop_stream", "nt"]),
    ("Can you claim a deployment without a receipt?", ["no", "never", "receipt"]),
    ("What tokens gate a real self-patch apply?", ["APPROVE_FIX_CANDIDATE", "token", "approval"]),
    ("Who alone can approve your protected changes?", ["Joshua", "owner"]),
    ("What is your rollback sibling file for the live model?", ["bak", "backup", "rollback"]),
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ask(base_url: str, prompt: str, timeout: int) -> "dict":
    req = urllib.request.Request(
        base_url.rstrip("/") + "/chat",
        data=json.dumps({"prompt": prompt}).encode("utf-8"),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def run_session(base_url: str, rounds: int, timeout: int) -> "dict":
    turns = []
    passed = 0
    for round_no in range(1, rounds + 1):
        for question, expects in DRILLS:
            started = time.perf_counter()
            try:
                response = ask(base_url, question, timeout)
            except Exception as exc:
                turns.append({"round": round_no, "q": question, "ok": False,
                              "error": str(exc)[:120]})
                continue
            reply = str(response.get("assistant_reply") or "")
            receipt = response.get("receipt") or {}
            hit = any(e.lower() in reply.lower() for e in expects)
            passed += 1 if hit else 0
            turns.append({
                "round": round_no,
                "q": question,
                "ok": hit,
                "expected_any": expects,
                "reply_head": reply[:180],
                "activation_depth": receipt.get("activation_depth"),
                "latency_s": round(time.perf_counter() - started, 1),
            })
    total = len(turns)
    session = {
        "schema": "ENGEL_NEURO_DRILL_SESSION_V1",
        "goal_id": "engel_conical_agentic_sentient_self_upgrading_system",
        "ran_at_utc": _now(),
        "base_url": base_url,
        "rounds": rounds,
        "turns_total": total,
        "turns_passed": passed,
        "pass_rate": round(passed / max(1, total), 3),
        "weak_turns": [t for t in turns if not t.get("ok")],
        "turns": turns,
        "actor_note": "drill through the real chat lane; every turn lands in persistent "
                      "memory + receipts and feeds the daily dataset flywheel",
    }
    RECEIPT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = session["ran_at_utc"].replace(":", "").replace("-", "")[:15]
    out = RECEIPT_DIR / f"drill_session_{stamp}.json"
    out.write_text(json.dumps(session, indent=1, ensure_ascii=False), encoding="utf-8")
    session["receipt_path"] = str(out)
    return session


def main(argv: "list[str] | None" = None) -> int:
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    parser = argparse.ArgumentParser(description="Engel neuro/self-upgrade drill session")
    parser.add_argument("--base-url", default="http://127.0.0.1:8765")
    parser.add_argument("--rounds", type=int, default=1)
    parser.add_argument("--timeout", type=int, default=150)
    args = parser.parse_args(argv)
    session = run_session(args.base_url, args.rounds, args.timeout)
    print(json.dumps({k: session[k] for k in
                      ("turns_total", "turns_passed", "pass_rate", "receipt_path")}, indent=1))
    for t in session["weak_turns"][:8]:
        print("WEAK:", t["q"], "->", str(t.get("reply_head") or t.get("error"))[:100])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
