---
name: "engel-local-speech-whisper-piper"
description: "Offline STT/TTS pair staged from shared-room: faster-whisper-base and Piper Amy ONNX."
version: "1.0.0"
source: "engel-ai-main-server"
created_at_utc: "2026-08-25T21:48:52Z"
updated_at_utc: "2026-08-25T21:48:52Z"
---

# Engel Local Speech Whisper Piper

## Purpose

Offline STT/TTS pair staged from shared-room: faster-whisper-base and Piper Amy ONNX.

## Trigger Conditions

- whisper piper
- local speech
- offline tts stt

## Operating Instructions

Models are under runtime/next_stage/speech. CT246 already has Nemotron ASR; this is a second local pair. Do not pip-install unless Josh approves a package step. Do not call cloud TTS.

## Save Contract

- Save durable outputs under Engel AI Main storage, not temporary chat state.
- Update the Engel skill registry after changes.
- Include a receipt path or registry key in the response when this skill creates or changes files.
- Do not expose secrets in skill files, receipts, chat replies, or logs.
