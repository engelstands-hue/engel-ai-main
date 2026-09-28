---
name: "engel-trading-desk-disarmed"
description: "Survival/Live TypeScript desk UI and sim engine. CLOB posting stays disarmed."
version: "1.0.0"
source: "engel-ai-main-server"
created_at_utc: "2026-08-25T21:48:52Z"
updated_at_utc: "2026-08-25T21:48:52Z"
---

# Engel Trading Desk Disarmed

## Purpose

Survival/Live TypeScript desk UI and sim engine. CLOB posting stays disarmed.

## Trigger Conditions

- trading desk
- survival desk
- polymarket desk

## Operating Instructions

Code is runtime/next_stage/trading_desk. Read DISARMED.md first. Paper/sim and corroboration notes are allowed. Do not set POLYMARKET_PRIVATE_KEY. Live orders need a later Josh call with a risk budget.

## Save Contract

- Save durable outputs under Engel AI Main storage, not temporary chat state.
- Update the Engel skill registry after changes.
- Include a receipt path or registry key in the response when this skill creates or changes files.
- Do not expose secrets in skill files, receipts, chat replies, or logs.
