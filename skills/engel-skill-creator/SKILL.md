---
name: "engel-skill-creator"
description: "Creates, saves, lists, and verifies Engel AI Main skills from real chat or HTTP requests."
version: "1.0.0"
source: "engel-ai-main-server"
created_at_utc: "2026-06-29T05:06:34Z"
updated_at_utc: "2026-06-29T05:06:34Z"
---

# Engel Skill Creator

## Purpose

Creates, saves, lists, and verifies Engel AI Main skills from real chat or HTTP requests.

## Trigger Conditions

- Use this skill when the user asks Engel AI Main to handle Engel Skill Creator.
- Use this skill when the request names Engel Skill Creator.

## Operating Instructions

When the user asks Engel AI Main to create or save a skill, write a SKILL.md file, mirror it to managed skills, update ENGEL_SAVED_SKILL_REGISTRY.json, append a creation event, and return the receipt path without exposing secrets.

## Save Contract

- Save durable outputs under Engel AI Main storage, not temporary chat state.
- Update the Engel skill registry after changes.
- Include a receipt path or registry key in the response when this skill creates or changes files.
- Do not expose secrets in skill files, receipts, chat replies, or logs.
