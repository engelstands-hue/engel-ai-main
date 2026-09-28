# Wiki One — how to walk this Windows body

This folder is **Wiki One**: one map of the Windows body on `LAPTOP-0KUVK82E`.

The map is not trusted memory. It is orientation. Code still wins if a card and a file disagree — fix the card.

## Universes

| Mark | Meaning |
|---|---|
| live | In force. Implement against these. |
| leftover | Present, not the main path. Touch only if that path is in scope. |
| ghost | Named but not wired. Do not implement against these. |
| peer | Lives on another nest (CT246, Sub-Engel, phones). This body talks to it. |

## Walk

1. Open `wiki/ONE.md`. That is the one map.
2. Find the organ you will touch. Read **does**, **talks to**, **hits**, **does not hit**.
3. Open `wiki/effects/CONTEXT.md` if the change spans more than one organ.
4. Auto lanes also load `wiki/organs.json` (same organs, machine shape).

## Land CODE

The whole Engel AI Main **reads Wiki One before CODE** and **updates it for all organ changes**.

1. Read `wiki/ONE.md` and `wiki/CONTRACT.md`.
2. If an organ, talks-to, source, home, or duty changed, update `wiki/ONE.md` and `wiki/organs.json` in the same job.
3. Land the smallest safe change.
4. **Stamp Journal** so the other organs can see what happened:

```text
D:\b.WorkSpace\Engel App\runtime\python310\python.exe tools\stamp_wiki_one_journal.py --wiki-read --lane grok --worker <name> --organs face,router --summary "one line" --files "path1;path2" --receipt "reports/codex_bridge/<NAME>.md"
```

`--wiki-read` is the worker asserting they opened `wiki/ONE.md`. The stamp tool refuses without it. If the map changed, include organ `wiki_one` in the stamp.

Journal writes only:

- `wiki/journal/JOURNAL.jsonl` (append-only)
- `wiki/journal/LATEST.md`

Not trusted memory. Not `ALIVE_STATE`. Not digest/history. Not queue mutation.

## Authority

Josh > Guardian > Engel/runtime.

This Windows machine is the face/controller. CT246 is the runtime body. Sub-Engel is DESKTOP-UE5A6GG.
