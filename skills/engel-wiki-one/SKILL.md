---
name: "engel-wiki-one"
description: "Wiki One map of the Windows body. Workers and auto read it before they land CODE, then stamp Journal."
version: "1.0.0"
---

# Engel Wiki One

## Purpose

Canonical second brain for Engel AI Main Cosmic Swarm OS (`EngelAIMain.exe`) and every worker lane. Every organ, what it does, who it talks to. Read `wiki/ONE.md` before CODE. Update `wiki/ONE.md` and `wiki/organs.json` when organs change. Stamp Journal after.

## Trigger Conditions

- Any source edit, route change, verifier, or auto apply on this tree.
- Phrases: wiki one, windows body map, who talks to whom, stamp journal, land CODE.

## Operating Instructions

1. Read `wiki/ONE.md` and `wiki/CONTRACT.md`.
2. Open the organ row you will touch. If more than one organ, read `wiki/effects/CONTEXT.md`.
3. Auto lanes also load `wiki/organs.json`.
4. If an organ, talks-to, source, or duty changed, update `wiki/ONE.md` and `wiki/organs.json` in the same job.
5. Land the smallest safe change.
6. Stamp Journal:

```text
D:\b.WorkSpace\Engel App\runtime\python310\python.exe tools\stamp_wiki_one_journal.py --wiki-read --lane <lane> --worker <name> --organs <id,id> --summary "one line" --files "a.py;b.py" --receipt "reports/codex_bridge/<NAME>.md"
```

Do not stamp without `--wiki-read`. Journal is not trusted memory.

## Save Contract

- Map: `wiki/ONE.md` + `wiki/organs.json`
- Journal: `wiki/journal/JOURNAL.jsonl` + `wiki/journal/LATEST.md`
- No C: writes. No trusted-memory. No `ALIVE_STATE`. This laptop is not Sub-Engel and not CT246.
