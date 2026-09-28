---
name: "engel-sub-engel-reconnect"
description: "Sub-Engel reconnect and proof contract from the Hermes patch: health URLs, proof JSON keys, no-C rule."
version: "1.0.0"
source: "engel-ai-main-server"
created_at_utc: "2026-08-25T21:48:52Z"
updated_at_utc: "2026-08-25T21:48:52Z"
---

# Engel Sub-Engel Reconnect

## Purpose

Sub-Engel reconnect and proof contract from the Hermes patch: health URLs, proof JSON keys, no-C rule.

## Trigger Conditions

- sub-engel reconnect
- sub engel proof
- hermes sub-engel

## Operating Instructions

Scripts are staged at runtime/next_stage/hermes_sub_engel. Treat reconnect as valid only when proof JSON has mainHealthReachable, localHealthReachable, nodeReadyStatus=accepted, mainPairedTime, sessionExpiration, nodeStatus=0, netStatus=0. Do not print pairing codes or tokens. Newer GUI is runtime/next_stage/sub_engel_gui.

## Save Contract

- Save durable outputs under Engel AI Main storage, not temporary chat state.
- Update the Engel skill registry after changes.
- Include a receipt path or registry key in the response when this skill creates or changes files.
- Do not expose secrets in skill files, receipts, chat replies, or logs.
