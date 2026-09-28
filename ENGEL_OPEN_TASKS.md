# Engel Open Tasks

## Pending Infrastructure Tasks

| Task | Status | Notes |
|---|---|---|
| Second iSCSI path / multipath | pending | Do not assume complete |
| Final `/mnt/engel-vault` mount verification | pending current health pass | Documented checks only in this task |
| Full migration from `D:\b.WorkSpace\Engel App` to `/opt/engel/app` | pending Josh approval | Plan only, not executed |
| Connected device registry completion | pending | Phones/desktops/laptops need exact identity and paths |
| GPU worker integration | pending | Requires device role, health checks, approval, stop rule |
| Backup system | pending | Vault backup design and external backup policy needed |
| Service startup automation | pending | Must obey startup policy and avoid uncontrolled loops |
| Phone beta pairing | pending | Historical context says alpha paired, beta did not |
| Agent meeting room worker selection visibility | pending review | Device-specific work assignment must be explicit |
| Active model promotion from vault archive to fast models | pending approval | Must define active set and rollback |

## Documentation Follow-Up

- Review unknown / pending review rows in `ENGEL_FILE_MANIFEST.md`.
- Decide which generated/runtime/cache/build artifacts should stay on ROG only, migrate to vault, or regenerate on server.
- Decide exact app-code migration window and verification method.

