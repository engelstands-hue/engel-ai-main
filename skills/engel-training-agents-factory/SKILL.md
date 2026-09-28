---
name: "engel-training-agents-factory"
description: "1,000-persona drill room, GospelComposer, JSONL export for Bible-companion LoRA. Not Engel AI Main chat identity."
version: "1.0.0"
source: "engel-ai-main-server"
created_at_utc: "2026-08-25T21:48:52Z"
updated_at_utc: "2026-08-25T21:48:52Z"
---

# Engel Training Agents Factory

## Purpose

1,000-persona drill room, GospelComposer, JSONL export for Bible-companion LoRA. Not Engel AI Main chat identity.

## Trigger Conditions

- training agents
- gospel composer
- 1000 personas
- drill room

## Operating Instructions

Code is runtime/next_stage/training_agents. Datasets are training_exports JSONL. Use for Bible-companion voice data only. Do not replace Engel AI Main identity LoRA with gospel preacher voice.

## Save Contract

- Save durable outputs under Engel AI Main storage, not temporary chat state.
- Update the Engel skill registry after changes.
- Include a receipt path or registry key in the response when this skill creates or changes files.
- Do not expose secrets in skill files, receipts, chat replies, or logs.
