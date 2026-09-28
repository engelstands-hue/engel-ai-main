$ErrorActionPreference = "Stop"

throw @"
BLOCKED PERMANENTLY: CT245 / engel-vault-share / PowerVault is not part of Engel AI Main.
This legacy setup launcher has no reactivation route.

Current approved storage path:
  Dell PowerEdge internal HDD/ZFS pool: engel-hdd-vault
  CT: 246
  CT mount: /mnt/engel-hdd-vault
  Backup flag: backup=0

Do not use:
  CT 245
  engel-vault-share
  CT245 offline-vault storage
  retired CT245 storage ID
  /mnt/engel-vault
  /dev/sdc
  iSCSI

Use instead:
  .\scripts\Install-EngelPowerEdgeHddVaultBind.ps1 -ProxmoxHost 192.0.2.50 -HostSource /engel-hdd-vault -ContainerMount /mnt/engel-hdd-vault -MountIndex 1 -AllowCtRestart
"@
