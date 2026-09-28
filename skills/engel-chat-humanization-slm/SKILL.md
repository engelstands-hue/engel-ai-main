---
name: "engel-chat-humanization-slm"
description: "Humanization SLM that rewrites Engel AI Main chat-LLM drafts into first-person spoken replies. Communication lane, not live 7B."
version: "1.1.0"
source: "engel-ai-main"
created_at_utc: "2026-08-27T22:20:00Z"
updated_at_utc: "2026-08-27T23:10:00Z"
---

# Engel Chat Humanization SLM

## Purpose

Communication is the chat product. After the live chat LLM drafts an answer,
this small local GGUF rewrites the visible reply so it sounds like a person:

> I use Tesseract for OCR on images, it's the engine behind reading text from
> pictures. If you need help with OCR or anything else, just let me know!

It does **not** replace the live CT246 Qwen 7B + LoRA.

## Trigger Conditions

- humanization slm
- chat sounds robotic
- communicate like a person
- Discord talk voice

## Operating Instructions

- Module: `tools/engel_chat_humanization_slm.py`
- Layer 1: spoken-voice kernel (always, local). Strips AI-isms and status cards.
- Layer 2: 0.5B GGUF rewrite only when the kernel still sees a robotic draft.
- Wired in `tools/engel_main_server_chat_http_service.py` `_apply_chat_humanizer`
- Discord last pass: `source=discord_public` (kernel only, no second GGUF load)
- Model: existing `qwen2.5-0.5b-instruct` GGUF on CT246. CPU only. Live 7B stays on GPU.
- Keep chat LLM and 0.5B cached together (`ENGEL_LOCAL_MODEL_CACHE_MAX_MODELS=2` on chat service).
- Fail open. JSON/code/verifier turns and form-graded prompt-training turns (engineering Confirmed/Proof, math Result/Check, construction Sourced facts) are not rewritten. Communication training stays spoken.
- Disable with `ENGEL_HUMANIZATION_SLM=0`.
- Examples: `memory/personality/engel_humanization_examples.jsonl`

## Save Contract

- No trusted-memory writes.
- No secrets.
- Receipts may record `humanization_slm_used` / `humanization_slm_reason`.
