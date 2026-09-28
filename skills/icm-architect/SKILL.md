---
name: "icm-architect"
description: "Apply ICM Architect (folder structure as agent architecture) from D:\\b.WorkSpace\\icm-architect-main to the current Engel AI Main app. Use when Josh says ICM this, structure Engel for agents, audit this folder, or use icm-architect-main on this app."
version: "1.0.0"
source: "icm-architect-main"
created_at_utc: "2026-08-17T00:00:00Z"
updated_at_utc: "2026-08-17T00:00:00Z"
---

# ICM Architect on Engel AI Main

## Purpose

Use the ICM Architect pack at `D:\b.WorkSpace\icm-architect-main\icm-architect-main` on the current Engel AI Main app at `D:\b.WorkSpace\Engel App`.

ICM replaces extra orchestration with folders, contracts, and a walkable catalog. This Engel apply-run inventories and proposes. It does not move Engel source.

## Operating Instructions

1. Read the pack `SKILL.md`, then `references/core.md`.
2. Work in `memory/icm/engel-ai-main/` — that is the catalog.
3. Phrases: `icm status`, `icm audit`, `icm workspace`, `icm outputs`, `icm routing`.
4. Grok Bot filesystem includes the ICM pack and the Engel ICM workspace.
5. Current face stays `EngelAIMain.exe` / Cosmic Swarm OS.
6. Stop before any file move. Josh must approve a written map.

## Save Contract

- Writes only under `memory/icm/engel-ai-main/stages/*/output/`
- No trusted-memory writes, no queue mutation, no provider calls
- Authority: Josh > Guardian > Engel/runtime
