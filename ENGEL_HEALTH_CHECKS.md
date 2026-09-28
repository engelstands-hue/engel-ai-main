# Engel Health Checks

This file documents commands only. These commands were not executed by this documentation task.

## Proxmox Host Checks

```bash
hostname
pvesm status
pct status 246
pct config 246
iscsiadm -m session
lsblk
pvs
vgs
lvs
ip -br addr
```

Expected state:

- Hostname: `engel-spine-01`.
- Storage `engel-vault-main` active when PowerVault path is healthy.
- CT 246 exists as `engel-ai-main`.
- iSCSI session active to `192.168.130.101:3260`.
- `/dev/sdc` visible when PowerVault is active.
- `engel-vault-vg` and `engel-vault-thin` active.

## Engel AI Main CT Checks

```bash
hostname
ip -br addr
df -h
free -h
nproc
python3 --version
/opt/engel/.venv/bin/python --version
systemctl status ssh
test -d /opt/engel
test -d /mnt/engel-vault
```

Expected state:

- Hostname: `engel-ai-main`.
- Internal CT address includes `10.246.0.2/24`.
- Python 3.11 available.
- `/opt/engel` exists.
- `/mnt/engel-vault` exists and is mounted before vault-dependent runtime.
- SSH enabled for approved ROG route `ssh root@192.0.2.50 -p 24622`.

## PowerVault Checks

Documented expected checks:

- MDSM reports array status `Optimal`.
- Controller 0 MGMT `192.0.2.91` reachable.
- Controller 1 MGMT `192.0.2.92` reachable.
- iSCSI session active to `192.168.130.101:3260`.
- `/dev/sdc` visible on Proxmox when active.
- `engel-vault-main` active in Proxmox.
- Second iSCSI path / multipath remains pending until explicitly completed.

## ROG Route Checks

```powershell
Test-NetConnection 192.0.2.50 -Port 22
Test-NetConnection 192.0.2.50 -Port 24622
ssh root@192.0.2.50 -p 24622 hostname
```

These are documented checks only, not executed here.

