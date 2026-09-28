# Engel Storage Map

## Storage Roles

| Path / Storage | Role | Location | Policy |
|---|---|---|---|
| `D:\b.WorkSpace\Engel App` | ROG source workspace and Queen-side app source | ROG laptop | Source of current local docs and app tree |
| `/opt/engel` | Fast SSD server runtime | CT 246 on `engel-fast-ssd` | Active runtime only |
| `/opt/engel/app` | Migrated Engel App code target | CT 246 | Migration target for app code after approval |
| `/opt/engel/.venv` | Python virtual environment | CT 246 | Runtime dependency environment |
| `/opt/engel/core` | Core scripts | CT 246 | Server body core runtime scripts |
| `/opt/engel/memory` | Active memory | CT 246 | Fast active memory and registry files |
| `/opt/engel/models-active` | Active fast models | CT 246 | Fast model working set only |
| `/opt/engel/cache` | Cache/temp | CT 246 | Rebuildable cache |
| `/opt/engel/logs` | Runtime logs | CT 246 | Active logs, archive to vault as needed |
| `/opt/engel/run` | Runtime state | CT 246 | Current process/session state |
| `/opt/engel/scripts` | Helper scripts | CT 246 | Controlled helper scripts |
| `/mnt/engel-vault` | Large PowerVault vault mount | CT 246, backed by `engel-vault-main` | Long-lived vault; not normal CT backup |

## Vault Layout

| Vault path | Purpose | Policy |
|---|---|---|
| `/mnt/engel-vault/models-archive` | Long-term model archives | Large models live here unless active |
| `/mnt/engel-vault/backups` | Backup sets | Staged and verified backups only |
| `/mnt/engel-vault/datasets` | Training/eval datasets | Dataset archive and transfer target |
| `/mnt/engel-vault/memory` | Memory archive | Long-lived memory history |
| `/mnt/engel-vault/transfers` | Inbound/outbound transfer staging | Verify before activation |
| `/mnt/engel-vault/logs` | Archived logs | Keep active logs small on fast SSD |
| `/mnt/engel-vault/sources/F/ENGEL_APP_MEMORY` | F-drive model/runtime archive copied to CT | Registered in aggregate transfer manifest |

## PowerVault Facts

| Item | Value |
|---|---|
| Array | Dell PowerVault MD3200i |
| Proxmox storage ID | `engel-vault-main` |
| VG | `engel-vault-vg` |
| Thinpool | `engel-vault-thin` |
| Type | `lvmthin` |
| Confirmed iSCSI path | Proxmox `192.168.130.10/24` -> target `192.168.130.101:3260` |
| Proxmox disk when active | `/dev/sdc` Dell MD32xxi, about 27.2T |
| MDSM mapping | host `engel-spine-01`, LUN 0 |
| Controller 0 MGMT | `192.0.2.91` |
| Controller 1 MGMT | `192.0.2.92` |
| Multipath | pending, not complete |

## Backup Policy

The large vault mount is intentionally excluded from normal CT backups with `backup=0`. Vault data must use staged, explicit backup plans approved by Josh. Do not include the large mount in automatic CT backups unless Josh approves.

