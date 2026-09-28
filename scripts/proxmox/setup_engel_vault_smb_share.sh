#!/usr/bin/env bash
set -euo pipefail

cat >&2 <<'BLOCKED'
BLOCKED PERMANENTLY: CT245 / engel-vault-share / PowerVault is not part of Engel AI Main.
This legacy setup script has no reactivation route.

Current approved storage path:
  Dell PowerEdge internal HDD/ZFS pool: engel-hdd-vault
  CT: 246
  CT mount: /mnt/engel-hdd-vault
  Backup flag: backup=0

Do not use:
  CT 245
  engel-vault-share
  PowerVault
  engel-vault-main
  /mnt/engel-vault
  /dev/sdc
  iSCSI

Use instead:
  scripts/proxmox/bind_engel_hdd_vault_to_ct246.sh
BLOCKED

exit 2
