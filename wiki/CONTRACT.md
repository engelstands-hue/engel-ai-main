# Wiki One contract — whole Engel AI Main

Wiki One is the **canonical second brain** of Engel AI Main. Engel AI Main is **LIVE**. Organs are **alive**. Every organ, what it does, who it talks to. Wiki One does not write the `ALIVE_STATE` file.

It is not optional orientation. The whole system — including Cosmic Swarm OS (`EngelAIMain.exe`) Home, Wiki tab, and Ask Engel — must **read** it and **update** it.

Authority: Josh > Guardian > Engel/runtime.

## Who must know

Every Engel AI Main lane:

- Grok, Claude, Codex, Cursor, ChatGPT
- local LLMs and CT246 Engel AI Main
- Meeting Room agents and Grok Bots
- Android workers
- Sub-Engel
- auto scripts and verifiers

This Windows machine is the face/controller. CT246 is the runtime body. Sub-Engel is DESKTOP-UE5A6GG.

## Read

Before landing CODE, dispatch, or changing an organ, read:

- `wiki/ONE.md` (the map)
- the organ row you will touch
- `wiki/effects/CONTEXT.md` if more than one organ

Auto lanes also load `wiki/organs.json`.

## Update

Update Wiki One in the **same job** when any of these change:

- an organ is added, renamed, retired, or moved
- what an organ does
- who it talks to
- its sources, home, hits, or does-not-hit
- a new lane, nest, share, tunnel, or duty that other parts must know

Update both:

- `wiki/ONE.md`
- `wiki/organs.json`

Keep them in sync. Code still wins if they disagree — then fix the wiki.

## Stamp

After CODE, stamp Journal:

```text
D:\b.WorkSpace\Engel App\runtime\python310\python.exe tools\stamp_wiki_one_journal.py --wiki-read --lane <lane> --worker <name> --organs <ids> --summary "one line" --files "a.py;b.py" --receipt "reports/codex_bridge/<NAME>.md"
```

If the map itself changed, include `wiki_one` in `--organs`.

## Not this

- Not trusted memory
- Not `ALIVE_STATE`
- Not digest/history
- Not ICM file moves
- Chat routes `wiki one` / `wiki journal` / `update wiki one` are read-only status. Workers still edit the wiki files.

## Phrases

- wiki one
- wiki journal
- update wiki one
