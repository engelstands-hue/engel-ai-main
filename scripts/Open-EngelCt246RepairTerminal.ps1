$ErrorActionPreference = "Stop"

$remote = @'
set -e
printf "\n=== Engel CT 246 route repair ===\n"
hostname
printf "\n-- CT status before --\n"
pct status 246 || true
if ! pct status 246 2>/dev/null | grep -q running; then
  echo "Starting CT 246..."
  pct start 246
  sleep 8
fi
printf "\n-- CT status after --\n"
pct status 246
printf "\n-- CT network / SSH --\n"
pct exec 246 -- bash -lc "hostname; ip -4 addr show; systemctl enable --now ssh || systemctl enable --now ssh.service || true; systemctl restart ssh || systemctl restart ssh.service || true; systemctl is-active ssh || systemctl is-active ssh.service || true; ss -ltnp | grep -E ':22 ' || true"
printf "\n-- Host listener 24622 before --\n"
ss -ltnp | grep ':24622 ' || true
if ! ss -ltn | grep -q ':24622 '; then
  echo "Adding guarded iptables forward 192.0.2.50:24622 -> 10.246.0.2:22"
  sysctl -w net.ipv4.ip_forward=1 >/dev/null
  iptables -t nat -C PREROUTING -p tcp -d 192.0.2.50 --dport 24622 -j DNAT --to-destination 10.246.0.2:22 2>/dev/null || iptables -t nat -A PREROUTING -p tcp -d 192.0.2.50 --dport 24622 -j DNAT --to-destination 10.246.0.2:22
  iptables -t nat -C OUTPUT -p tcp -d 127.0.0.1 --dport 24622 -j DNAT --to-destination 10.246.0.2:22 2>/dev/null || iptables -t nat -A OUTPUT -p tcp -d 127.0.0.1 --dport 24622 -j DNAT --to-destination 10.246.0.2:22
  iptables -C FORWARD -p tcp -d 10.246.0.2 --dport 22 -j ACCEPT 2>/dev/null || iptables -A FORWARD -p tcp -d 10.246.0.2 --dport 22 -j ACCEPT
fi
printf "\n-- Host test --\n"
(timeout 3 bash -lc 'cat < /dev/null > /dev/tcp/127.0.0.1/24622') && echo "24622 open on host" || echo "24622 still not open"
printf "\n-- Chat service inside CT --\n"
pct exec 246 -- bash -lc "systemctl enable --now engel-main-chat.service || true; systemctl restart engel-main-chat.service || true; systemctl is-active engel-main-chat.service || true; curl -fsS http://127.0.0.1:8765/health || true"
printf "\n=== Done. Leave this window open until Codex verifies from ROG. ===\n"
'@

$encodedRemote = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($remote))
$sshCommand = "echo $encodedRemote | base64 -d >/tmp/engel_ct246_repair.sh; chmod +x /tmp/engel_ct246_repair.sh; bash /tmp/engel_ct246_repair.sh"

Write-Host "Engel CT 246 repair terminal"
Write-Host "Type the Proxmox root password when SSH asks."
Write-Host "No password is saved or printed."
ssh -tt -o StrictHostKeyChecking=accept-new root@192.0.2.50 $sshCommand
Write-Host ""
Write-Host "Repair command ended. You can leave this window open for Codex verification."
