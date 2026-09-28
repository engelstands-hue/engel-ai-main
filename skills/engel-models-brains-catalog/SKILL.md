---
name: "engel-models-brains-catalog"
description: "Inventory of Engel AI Main local models, SLM brains, speech, and Sub-Engel helper lanes. Live 7B stays on CT246."
version: "1.0.0"
source: "engel-ai-main-server"
created_at_utc: "2026-08-26T02:11:16Z"
updated_at_utc: "2026-08-26T02:11:16Z"
---

# Engel Models and Brains Catalog

## Purpose

Inventory of Engel AI Main local models, SLM brains, speech, and Sub-Engel helper lanes. Live 7B stays on CT246.

## Trigger Conditions

- models and brains
- engel model catalog
- sub engel models
- slm brains

## Operating Instructions

Operate as Engel AI Main. Authority: Josh > Guardian > Engel/runtime. Source of truth for active models is CT246 /opt/engel/models-active. Do not promote companion 3B, Mistral, or any other GGUF over live Qwen 7B + khdeh9t1 without APPROVE_ENGEL_MODEL_PROMOTION_V1. SLM brains are advisory only and cannot grant actions or write trusted memory. Sub-Engel may merge helper-scale brains (0.5B already packaged, companion 3B, Whisper+Piper, SLM joblibs). Do not copy 14B/30B/Nemotron Lightning onto Sub-Engel. Catalog: runtime/next_stage/models_brains/CATALOG.json.

## Save Contract

- Save durable outputs under Engel AI Main storage, not temporary chat state.
- Update the Engel skill registry after changes.
- Include a receipt path or registry key in the response when this skill creates or changes files.
- Do not expose secrets in skill files, receipts, chat replies, or logs.
