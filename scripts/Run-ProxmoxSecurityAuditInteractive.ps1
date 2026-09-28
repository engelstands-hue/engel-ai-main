param(
    [string]$HostName = "192.0.2.50",
    [string]$UserName = "root"
)

$ErrorActionPreference = "Continue"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$ReportDir = Join-Path $RepoRoot "reports\proxmox"
New-Item -ItemType Directory -Force -Path $ReportDir | Out-Null

$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$Report = Join-Path $ReportDir "proxmox_security_audit_$Stamp.txt"

@"
=== Engel Proxmox security audit started $(Get-Date -Format o) ===
Target: $UserName@$HostName

READ-ONLY AUDIT. This script does not change firewall, SSH, packages, users, disks, VMs, or containers.
"@ | Tee-Object -FilePath $Report

$RemoteScript = @'
set +e

section() {
  printf '\n=== %s ===\n' "$1"
}

section "host identity"
hostname
date -Iseconds
uptime
pveversion

section "network identity and routes"
ip -br addr
ip route

section "listening network services"
ss -ltnup

section "proxmox storage and guests"
pvesm status
pct list
qm list

section "proxmox users"
pveum user list || true

section "proxmox groups"
pveum group list || true

section "proxmox ACLs"
pveum acl list || true

section "proxmox user config metadata"
if [ -f /etc/pve/user.cfg ]; then
  sed -E 's/(token|secret|password|key):[^[:space:]]+/\1:<redacted>/gi' /etc/pve/user.cfg
else
  echo "/etc/pve/user.cfg missing"
fi

section "firewall status"
pve-firewall status || true

section "firewall config files"
for f in /etc/pve/firewall/cluster.fw /etc/pve/nodes/*/host.fw /etc/pve/lxc/*.fw; do
  [ -e "$f" ] || continue
  echo "--- $f ---"
  sed -E 's/(token|secret|password|key):[^[:space:]]+/\1:<redacted>/gi' "$f"
done

section "nft ruleset summary"
nft list ruleset 2>/dev/null | sed -n '1,260p' || true

section "ssh effective config"
sshd -T 2>/dev/null | grep -Ei '^(port|listenaddress|permitrootlogin|passwordauthentication|pubkeyauthentication|kbdinteractiveauthentication|challengeresponseauthentication|allowusers|allowgroups|x11forwarding|allowtcpforwarding|permitopen|gatewayports|maxauthtries|loglevel|clientalive)' || true

section "ssh config files"
for f in /etc/ssh/sshd_config /etc/ssh/sshd_config.d/*.conf; do
  [ -e "$f" ] || continue
  echo "--- $f ---"
  sed -E 's/(password|secret|token|key)[[:space:]]+[^[:space:]]+/\1 <redacted>/gi' "$f"
done

section "root authorized key fingerprints"
if [ -f /root/.ssh/authorized_keys ]; then
  n=0
  while IFS= read -r line; do
    n=$((n+1))
    tmp="/tmp/engel_ak_$n.pub"
    printf '%s\n' "$line" > "$tmp"
    printf 'authorized_keys line %s: ' "$n"
    ssh-keygen -lf "$tmp" 2>/dev/null || echo "unreadable key"
    rm -f "$tmp"
  done < /root/.ssh/authorized_keys
else
  echo "none"
fi

section "users with login shells"
awk -F: '$7 ~ /(bash|sh|zsh)$/ {printf "%s uid=%s home=%s shell=%s\n",$1,$3,$6,$7}' /etc/passwd

section "sudoers snippets"
ls -la /etc/sudoers /etc/sudoers.d 2>/dev/null
for f in /etc/sudoers.d/*; do
  [ -f "$f" ] || continue
  echo "--- $f ---"
  sed -E 's/(password|secret|token|key)[[:space:]]+[^[:space:]]+/\1 <redacted>/gi' "$f"
done

section "recent successful logins"
last -n 60 || true

section "recent failed logins"
lastb -n 60 2>/dev/null || true

section "recent ssh and proxmox auth events"
journalctl -u ssh -u pvedaemon -u pveproxy --since '7 days ago' --no-pager |
  grep -Ei 'accepted|failed|failure|invalid|authentication|root@pam|from ' |
  tail -260 || true

section "failed services"
systemctl --failed --no-pager || true

section "running services of interest"
systemctl list-units --type=service --state=running --no-pager |
  grep -Ei 'pve|ssh|firewall|cron|systemd|zfs|postfix|nginx|apache|cockpit|docker|container|engel' || true

section "timers"
systemctl list-timers --all --no-pager | sed -n '1,120p'

section "cron and recent persistence files"
ls -la /etc/cron.d /etc/cron.daily /etc/cron.hourly /etc/cron.weekly /var/spool/cron/crontabs 2>/dev/null
find /etc/systemd/system /etc/cron.d /etc/cron.daily /etc/cron.hourly /etc/cron.weekly /var/spool/cron -type f -mtime -14 -ls 2>/dev/null | sed -n '1,180p'

section "package repositories"
grep -Rhsn '^[[:space:]]*[^#[:space:]]' /etc/apt/sources.list /etc/apt/sources.list.d/*.list /etc/apt/sources.list.d/*.sources 2>/dev/null || true

section "upgradable packages"
apt list --upgradable 2>/dev/null | sed -n '1,120p' || true

section "disk and pool status"
lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT,MODEL,SERIAL
zpool status 2>/dev/null || true
vgs 2>/dev/null || true
lvs 2>/dev/null || true

section "top CPU and memory processes"
ps -eo pid,user,comm,%cpu,%mem,args --sort=-%cpu | head -35
printf '\n--- top memory ---\n'
ps -eo pid,user,comm,%cpu,%mem,args --sort=-%mem | head -35

section "security interpretation hints"
cat <<'EOF'
CHECK THESE MANUALLY:
- Proxmox UI/SSH should only be reachable from trusted LAN/VPN, never public internet.
- Prefer per-user admin accounts with TFA; keep root as break-glass only.
- Verify API tokens in /etc/pve/user.cfg are expected; revoke stale tokens.
- If firewall is disabled, stage LAN allow rules before enabling default DROP.
- Do not harden SSH root/password settings until key-based emergency access is verified.
EOF
'@

$RemoteScript | ssh -o StrictHostKeyChecking=accept-new "$UserName@$HostName" "bash -s" 2>&1 |
    Tee-Object -FilePath $Report -Append

"=== Engel Proxmox security audit finished $(Get-Date -Format o) ===" |
    Tee-Object -FilePath $Report -Append

Write-Host ""
Write-Host "Report saved to: $Report"
Read-Host "Press Enter to close"
