# Engel Migration Plan

This is a plan only. No migration was executed by this documentation task.

## Migration Goal

Move the ROG-side Engel App source tree from:

```text
D:\b.WorkSpace\Engel App
```

to the server body target:

```text
engel-ai-main:/opt/engel/app
```

Large archives, model payloads, datasets, backups, and heavy transfer roots map to:

```text
engel-ai-main:/mnt/engel-vault
```

## Staged Migration Design

| Stage | Objective | Approval checkpoint | Verification checkpoint | Rollback checkpoint |
|---|---|---|---|---|
| 0. Documentation | Map system, storage, devices, roles, unknowns | Josh accepts docs | Docs exist, manifest generated | No runtime change |
| 1. Backup plan | Define backup source and destination | Josh approves exact backup plan | Backup receipt/checksum plan | Do not copy if backup incomplete |
| 2. Copy dry run | Compare source/target path plan without activating | Josh approves copy command set | File count/size plan | No target activation |
| 3. Copy app code | Copy app-safe source to `/opt/engel/app` | Josh approves migration window | File count, checksum/sample import checks | Keep ROG source untouched |
| 4. Copy heavy payloads | Copy models/archives/datasets to `/mnt/engel-vault` | Josh approves heavy copy list | Manifests, exact sizes, no temp files | Keep original external source until verified |
| 5. Server activate | Point CT runtime to `/opt/engel/app` after checks | Josh approves activation | Chat, meeting room, model service health | Revert app path to prior CT runtime |
| 6. ROG merge | ROG app uses CT body by default | Josh approves one-system mode | ROG UI chat and meeting room route to CT | ROG local fallback remains |
| 7. External disconnect | Disconnect external drives only after verification | Josh approves removal | Server has all required data and backups | Keep drives attached until verified |

## Classification-Based Target Map

| Category | Target |
|---|---|
| Core runtime | `/opt/engel/app` or `/opt/engel/core` after review |
| Orchestrator/controller | `/opt/engel/app` plus ROG shortcut/tunnel policy |
| Agent / worker / tool / prompt / config | `/opt/engel/app` with role-specific subfolders retained |
| App backend/frontend/UI/mini-game | `/opt/engel/app` preserving relative paths |
| Memory | Active memory to `/opt/engel/memory`; archive memory to `/mnt/engel-vault/memory` |
| Models | Active set to `/opt/engel/models-active`; archives to `/mnt/engel-vault/models-archive` |
| Databases | Case-by-case; active DB fast SSD, archives vault |
| Logs/cache/build artifacts | Usually vault/archive or regenerate; not activated blindly |
| Unknown / pending review | Do not migrate into active runtime until classified |

## Required Migration Receipts

Every migration execution must write:

- source path
- target path
- file count
- byte count
- skipped files
- failed files
- checksum strategy or exact-size verification
- no-temp-file confirmation
- rollback point
- Josh approval reference

## Forbidden In This Plan

- No storage mutation.
- No Proxmox storage changes.
- No destructive file changes.
- No source deletion.
- No external drive disconnect until verified and approved.
- No automatic activation after copy.

