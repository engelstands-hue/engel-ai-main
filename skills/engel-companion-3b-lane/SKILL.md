---
name: "engel-companion-3b-lane"
description: "Merged Qwen2 3B Engel companion GGUF for Daily Local / phone RAM lane. Not live 7B chat."
version: "1.0.0"
source: "engel-ai-main-server"
created_at_utc: "2026-08-25T21:48:52Z"
updated_at_utc: "2026-08-25T21:48:52Z"
---

# Engel Companion 3B Lane

## Purpose

Merged Qwen2 3B Engel companion GGUF for Daily Local / phone RAM lane. Not live 7B chat.

## Trigger Conditions

- companion 3b
- daily local mode
- engel-companion-002

## Operating Instructions

Weights: runtime/gpu_models/engel-companion-002.gguf (Engel Merged 3b). This fills Daily Local Mode. Do not promote over the live CT246 Qwen 7B LoRA without APPROVE_ENGEL_MODEL_PROMOTION_V1.

## Save Contract

- Save durable outputs under Engel AI Main storage, not temporary chat state.
- Update the Engel skill registry after changes.
- Include a receipt path or registry key in the response when this skill creates or changes files.
- Do not expose secrets in skill files, receipts, chat replies, or logs.
