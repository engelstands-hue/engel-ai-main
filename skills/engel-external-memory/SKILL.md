---
name: "engel-external-memory"
description: "Where things live in Engel long-term storage: the CT246 vault topology (/opt/engel + /mnt/engel-hdd-vault) and the legacy E:/F:/G: drive-letter aliases. Use whenever a request involves GGUF model weights, llama.cpp runtimes, chat exports, archives, backups, receipts, 'where should X go', or any code that scans long-term storage."
version: "1.1.0"
source: "claude-skill-creator"
created_at_utc: "2026-08-04T14:56:01Z"
updated_at_utc: "2026-08-04T16:19:54Z"
---

# Engel External Memory

## Purpose

Keep storage decisions consistent with the **current** topology, and make sure every scanner uses the sanctioned scan-root helper instead of hard-coding drives.

## Source of truth

`memory/ENGEL_STORAGE_LOCATION_REGISTRY_V1.json` (last updated 2026-07-22, authority Josh > Engel guarded runtime). Status: `CT246_SERVER_ONLY / SSD_ACTIVE_RUNTIME / POWEREDGE_INTERNAL_HDD_ARCHIVE / EXTERNAL_STORAGE_PERMANENTLY_EXCLUDED / NO_AUTOMATIC_STORAGE_MUTATION`.

| Root | Role | Allowed content |
|---|---|---|
| `/opt/engel` (CT246 SSD, `engel-fast-ssd`) | Active runtime | Chat/model services, active local LLMs and adapters, persistent memory, Meeting Room state, current training state, receipts/logs/cache/self-update staging |
| `/mnt/engel-hdd-vault` (Dell PowerEdge RAIDZ2 ZFS, `engel-hdd-vault`) | **Archive only** | Model archives, dataset archives, completed training outputs, old checkpoints, snapshots, archive logs, transfer staging. Writes only after mount is verified; not an active inference surface |

**Permanently excluded** (no discovery, no probe, no mount, no reactivation route): external arrays and retired containers — `PowerVault`, `CT245`, `/mnt/engel-vault`, `engel-vault-main`, and the old laptop external drives.

## Legacy drive letters (aliases only)

The E:/F:/G: `ENGEL_APP_MEMORY` drive story (see `memory/project_engel_external_memory.md`) is historical. The letters survive as logical aliases in `engel_vault_paths.py`: F → `/opt/engel`, G → `/opt/engel/models-active`, E → `/mnt/engel-hdd-vault`. The **model scan order is still F → G → E** (`MODEL_SCAN_ORDER`), i.e. active runtime first, models-active second, archive last.

## Trigger Conditions

- Anyone asks "where should X go" for models, exports, archives, or runtimes.
- Code scans for GGUF weights, archived chats, or long-term receipts.
- llama.cpp, model loading, backups, vault mounts, or drive layout come up.

## The rules

- Scanners call `engel_vault_paths.model_scan_roots()` — never hard-code drive paths. `engel_local_model_manager._SCAN_ROOTS` is only a local fallback for bundled/dev models (`models/`, `runtime/models/` on D:).
- Path resolution goes through `engel_memory_root(drive)` / `engel_memory_path(drive, *parts)`, which prefer the vault and fall back to the alias roots. Vault root override: `ENGEL_HDD_VAULT_ROOT` env var (only `/mnt/engel-hdd-vault` is accepted).
- The vault is archive-only: no active inference from `/mnt/engel-hdd-vault`; archive copies only after `findmnt` verification.
- No automatic storage mutation — moves between runtime and archive are explicit, human-approved actions.
- Code/runtime stays on D: (`runtime/python310/`, `tools/platform-tools/` are app runtime, not long-term storage); nothing on C: (`feedback_no_c_drive.md`, enforced by `tools/verify_engel_c_drive_cleanup.py`).
- The D: `memory/` folder is the **project mirror of Claude harness memory** — it is not the vault and not an archive shelf; don't conflate them.

## Save Contract

- Read `memory/ENGEL_STORAGE_LOCATION_REGISTRY_V1.json` before changing any storage path or scanner; treat `memory/project_engel_external_memory.md` as history.
- Never probe, mount, or write to permanently excluded storage, and never write archives before mount verification.
- New scan sites go through `engel_vault_paths`; run the relevant verifier after changes.
