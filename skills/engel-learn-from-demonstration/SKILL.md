---
name: "engel-learn-from-demonstration"
description: "Turn a local screen recording of a task into a reusable Engel skill. Cursor-host paths rewritten off."
version: "1.0.0"
source: "engel-ai-main-server"
created_at_utc: "2026-08-25T21:48:52Z"
updated_at_utc: "2026-08-25T21:48:52Z"
---

# Engel Learn From Demonstration

## Purpose

Turn a local screen recording of a task into a reusable Engel skill. Cursor-host paths rewritten off.

## Trigger Conditions

- learn from demonstration
- watch me do it
- teach recording

## Operating Instructions

Original workflow is runtime/next_stage/skills_source/learn-from-demonstration.SKILL.md. Keep the loop: wait for recording finalize, claim one session, watch it, write an Engel SKILL.md, register via engel_skill_agent_creator. Do not call Cursor-only tools. Do not store secrets from the recording. Rewrite Cursor-host paths off.

## Save Contract

- Save durable outputs under Engel AI Main storage, not temporary chat state.
- Update the Engel skill registry after changes.
- Include a receipt path or registry key in the response when this skill creates or changes files.
- Do not expose secrets in skill files, receipts, chat replies, or logs.
