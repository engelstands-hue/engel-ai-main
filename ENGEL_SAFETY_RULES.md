# Engel Safety Rules

## Authority Rules

1. Josh is final authority.
2. ROG is Queen orchestrator and emergency fallback.
3. Engel runtime is below Josh and safety gates.
4. Worker devices do not act without explicit assignment.
5. Unknown devices/components do not receive active work.

## Documentation-Only Scope For This Task

Allowed:

- Read-only local inspection of `D:\b.WorkSpace\Engel App`.
- Creating/updating documentation files inside `D:\b.WorkSpace\Engel App`.
- Generating a local file manifest without reading secret contents.

Denied:

- Migration execution.
- Service startup.
- Proxmox/storage changes.
- PowerVault/iSCSI/multipath changes.
- Destructive file operations.
- Moving, renaming, deleting, or reorganizing existing files.
- Deployment commands.
- Autonomous workers or uncontrolled loops.

## Storage Safety

- Do not wipe, delete, reformat, repartition, `pvcreate`, `vgcreate`, `lvcreate`, recreate, overwrite, or destroy `/dev/sdc`.
- Do not destructively modify `local`, `local-lvm`, `pve`, `engel-fast-ssd`, or `engel-vault-main`.
- Do not assume multipath is complete.
- Do not include the large vault mount in normal CT backups unless Josh approves.
- Keep `backup=0` intentional for the large vault mount.

## Migration Safety

- Migration requires staged backup/copy/verify/activate/rollback checkpoints.
- ROG source stays intact until server copy is verified.
- External drives are not disconnected until Josh approves after verification.
- Unknown/pending review files are not promoted into active runtime.

## Worker Safety

- No autonomous worker swarms.
- No recursive loops.
- No blind phone dispatch by shared role name.
- Every worker needs device identity, scope, stop rule, and health check.
- Heavy GPU/build/storage work requires approval.

## Secrets Safety

- Do not print, summarize, copy, or store API keys, SSH private keys, tokens, passwords, or secrets.
- Secret folders are documented as pending review without content inspection.
- `.env` and similar config files are classified by path/name only.

## Destructive Operation Approval

Any destructive or infrastructure-changing action requires a separate Josh approval packet naming:

- exact target
- exact command class
- expected result
- backup/rollback point
- verification command
- stop condition

