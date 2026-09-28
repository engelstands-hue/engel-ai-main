param(
    [string]$HostName = "192.0.2.50",
    [string]$UserName = "root"
)

$ErrorActionPreference = "Continue"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$ReportDir = Join-Path $RepoRoot "reports\proxmox"
New-Item -ItemType Directory -Force -Path $ReportDir | Out-Null

$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$Report = Join-Path $ReportDir "proxmox_readonly_check_$Stamp.txt"

@"
=== Engel Proxmox read-only check started $(Get-Date -Format o) ===
Target: $UserName@$HostName

Commands are read-only:
- hostname, uptime, pveversion
- pvesm status
- pct/qm list
- pct status/config/df for CT 245 and CT 246
- iSCSI, lsblk, vgs, lvs
- failed services and top processes
"@ | Tee-Object -FilePath $Report

$RemoteScript = @'
set +e
hostname
uptime
pveversion

printf '\n=== pvesm status ===\n'
pvesm status

printf '\n=== containers ===\n'
pct list

printf '\n=== VMs ===\n'
qm list

printf '\n=== CT 245 status/config ===\n'
pct status 245 || true
pct config 245 || true

printf '\n=== CT 246 status/config ===\n'
pct status 246 || true
pct config 246 || true

printf '\n=== CT 246 df ===\n'
pct exec 246 -- df -h || true

printf '\n=== CT 246 running Engel services ===\n'
pct exec 246 -- systemctl list-units --type=service --state=running --no-pager | grep -E 'engel|ssh|cron|network|dbus|systemd|postfix' || true

printf '\n=== iSCSI sessions ===\n'
iscsiadm -m session || true

printf '\n=== lsblk ===\n'
lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT,MODEL,SERIAL

printf '\n=== vgs ===\n'
vgs || true

printf '\n=== lvs ===\n'
lvs || true

printf '\n=== failed services ===\n'
systemctl --failed --no-pager || true

printf '\n=== top CPU processes ===\n'
ps -eo pid,comm,%cpu,%mem,args --sort=-%cpu | head -30

printf '\n=== recent apt/task related logs ===\n'
journalctl -n 120 --no-pager | grep -Ei 'apt|pve|error|failed' || true
'@

$RemoteScript | ssh -o StrictHostKeyChecking=accept-new "$UserName@$HostName" "bash -s" 2>&1 |
    Tee-Object -FilePath $Report -Append

"=== Engel Proxmox read-only check finished $(Get-Date -Format o) ===" |
    Tee-Object -FilePath $Report -Append

Write-Host ""
Write-Host "Report saved to: $Report"
Read-Host "Press Enter to close"
