---
name: "engel-grok-bot"
description: "Named persistent Engel Grok Bot teammates on the shared cluster computer (CT 246, Meeting Room, Android workers, Sub-Engel). Use when the user says grok bot, create a bot, message a bot, or wants an AI teammate that uses the whole Engel system."
version: "1.0.0"
source: "engel-ai-main"
created_at_utc: "2026-08-17T00:00:00Z"
updated_at_utc: "2026-08-17T00:00:00Z"
---

# Engel Grok Bot

## Purpose

Give Josh named persistent teammates that work across the Engel cluster, not only this laptop. A Bot keeps memory and files. Every Bot shares one Engel computer: CT 246, the ROG controller, Meeting Room, Android workers, and Sub-Engel.

## Trigger Conditions

- "grok bot", "create grok bot", "message grok bot", "handoff grok bot"
- User wants an AI teammate, a persistent named agent, or Grok Bot-style handoff
- Work should use the server, phones, Meeting Room, or other limbs — not chat drafts only

## Operating Instructions

1. Open the desktop shortcut **Engel Grok Bot**. That must show the computer window (browser, filesystem, terminal), not the old black status console.
2. The screen is current Engel AI Main: Cosmic Swarm OS / `EngelAIMain.exe` talking to `http://127.0.0.1:24680`.
3. Use **Open Engel AI Main** to show the live chat UI from the screenshot.
4. Status/phrases still work: `python engel_ai.py ask "grok bot status"`
5. Text-only fallback: `python engel_grok_bot.py --console`
6. Do not create Android jobs, call providers, start loops, or write trusted memory from this skill.

## Shared computer

- CT 246 `/opt/engel` is the persistent body
- Local tunnels: `http://127.0.0.1:24680` (chat) and `http://127.0.0.1:8790` (Meeting Room)
- Workers: `remote_workers/android_worker_*`, Sub-Engel, Windows-sub
- State: `runtime/grok_bots/`
- Contract: `memory/ENGEL_GROK_BOT_CONTRACT_V1.md`

## Save Contract

- Append-only working notes and receipts only
- Meeting Room handoff is staging, not Send Job
- Record lessons through REPS
- Josh > Guardian > Engel/runtime
