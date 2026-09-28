---
name: "engel-market-regimes"
description: "Local 100-year market-regime research skill staged from the storage-pull SKILL.md."
version: "1.0.0"
source: "engel-ai-main-server"
created_at_utc: "2026-08-25T21:48:52Z"
updated_at_utc: "2026-08-25T21:48:52Z"
---

# Engel Market Regimes

## Purpose

Local 100-year market-regime research skill staged from the storage-pull SKILL.md.

## Trigger Conditions

- market regimes
- 100 year crash
- regime research

## Operating Instructions

Source essay is runtime/next_stage/skills_source/market-regimes.SKILL.md. Use it as local research. Do not place live trades from it. Pair with the paper trading desk, not CLOB posting.

## Save Contract

- Save durable outputs under Engel AI Main storage, not temporary chat state.
- Update the Engel skill registry after changes.
- Include a receipt path or registry key in the response when this skill creates or changes files.
- Do not expose secrets in skill files, receipts, chat replies, or logs.
