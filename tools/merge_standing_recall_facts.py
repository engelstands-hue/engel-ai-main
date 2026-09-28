#!/usr/bin/env python3
"""Merge standing recall facts into Engel persistent memory. No secrets."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from urllib import request as urlrequest

ROOT = Path("/opt/engel")
INCOMING = Path("/tmp/engel_person_project_facts_incoming.jsonl")
FACT_PATH = ROOT / "memory" / "engel_person_project_facts.jsonl"
MEM_PATH = ROOT / "memory" / "persistent_chat" / "ENGEL_AI_MAIN_LLM_CHAT_MEMORY.jsonl"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def main() -> int:
    now = utc_now()
    FACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    MEM_PATH.parent.mkdir(parents=True, exist_ok=True)
    existing: set[str] = set()
    if FACT_PATH.is_file():
        for line in FACT_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                existing.add(" ".join(str(obj.get("fact") or "").casefold().split()))
    wrote = 0
    if INCOMING.is_file():
        rows = INCOMING.read_text(encoding="utf-8", errors="replace").splitlines()
    else:
        rows = []
    for line in rows:
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        fact = str(obj.get("fact") or "").strip()
        key = " ".join(fact.casefold().split())
        if not fact or key in existing:
            continue
        obj["saved_at_utc"] = now
        with FACT_PATH.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(obj, ensure_ascii=False) + "\n")
        with MEM_PATH.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(
                json.dumps(
                    {
                        "schema": "engel_persistent_chat_memory_v1",
                        "ok": True,
                        "prompt": "standing recall fact",
                        "assistant_reply": fact,
                        "assistant_output_text": fact,
                        "source": "discord_standing_recall",
                        "selected_provider": "durable-facts",
                        "memory_source": "engel-ai-main Discord standing recall",
                        "recall_eligible": True,
                        "context_eligible": True,
                        "training_turn": False,
                        "training_sample_eligible": False,
                        "created_at_utc": now,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
        wrote += 1
    print("ct246_facts_wrote", wrote)
    try:
        urlrequest.urlopen(
            urlrequest.Request(
                "http://127.0.0.1:8940/reindex",
                data=b"{}",
                headers={"Content-Type": "application/json"},
                method="POST",
            ),
            timeout=2,
        )
        print("reindex_ok")
    except Exception as exc:
        print("reindex_skip", type(exc).__name__)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
