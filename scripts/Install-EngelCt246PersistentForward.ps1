$ErrorActionPreference = "Stop"

$remote = @'
set -euo pipefail

HOST_IP="192.0.2.50"
CT_ID="246"
CT_IP="10.246.0.2"
HOST_PORT="24622"
CT_PORT="22"
SCRIPT_PATH="/usr/local/sbin/engel-ct246-port-forward.sh"
SERVICE_PATH="/etc/systemd/system/engel-ct246-port-forward.service"
SYSCTL_PATH="/etc/sysctl.d/99-engel-ct246-forward.conf"

echo "=== Installing persistent Engel CT 246 SSH forward ==="
hostname

if ! command -v pct >/dev/null 2>&1; then
  echo "ERROR: pct not found. This must run on the Proxmox host." >&2
  exit 2
fi

if ! pct status "$CT_ID" >/dev/null 2>&1; then
  echo "ERROR: CT $CT_ID was not found." >&2
  exit 3
fi

cat > "$SYSCTL_PATH" <<EOF
net.ipv4.ip_forward=1
EOF
sysctl -p "$SYSCTL_PATH" >/dev/null

cat > "$SCRIPT_PATH" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

HOST_IP="192.0.2.50"
CT_IP="10.246.0.2"
HOST_PORT="24622"
CT_PORT="22"

sysctl -w net.ipv4.ip_forward=1 >/dev/null

iptables -w 30 -t nat -C PREROUTING -p tcp -d "$HOST_IP" --dport "$HOST_PORT" -j DNAT --to-destination "$CT_IP:$CT_PORT" 2>/dev/null \
  || iptables -w 30 -t nat -A PREROUTING -p tcp -d "$HOST_IP" --dport "$HOST_PORT" -j DNAT --to-destination "$CT_IP:$CT_PORT"

# Remove the legacy loopback-only OUTPUT rule. It could not provide an honest
# self-test because Linux does not route a 127/8 source to the CT bridge.
while iptables -w 30 -t nat -C OUTPUT -p tcp -d 127.0.0.1 --dport "$HOST_PORT" -j DNAT --to-destination "$CT_IP:$CT_PORT" 2>/dev/null; do
  iptables -w 30 -t nat -D OUTPUT -p tcp -d 127.0.0.1 --dport "$HOST_PORT" -j DNAT --to-destination "$CT_IP:$CT_PORT"
done

iptables -w 30 -t nat -C OUTPUT -p tcp -d "$HOST_IP" --dport "$HOST_PORT" -j DNAT --to-destination "$CT_IP:$CT_PORT" 2>/dev/null \
  || iptables -w 30 -t nat -A OUTPUT -p tcp -d "$HOST_IP" --dport "$HOST_PORT" -j DNAT --to-destination "$CT_IP:$CT_PORT"

iptables -w 30 -C FORWARD -p tcp -d "$CT_IP" --dport "$CT_PORT" -j ACCEPT 2>/dev/null \
  || iptables -w 30 -A FORWARD -p tcp -d "$CT_IP" --dport "$CT_PORT" -j ACCEPT

exit 0
EOF
chmod 0755 "$SCRIPT_PATH"

cat > "$SERVICE_PATH" <<EOF
[Unit]
Description=Engel CT 246 persistent SSH port forward
After=network-online.target pve-container@246.service
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=$SCRIPT_PATH
RemainAfterExit=yes
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable engel-ct246-port-forward.service
systemctl restart engel-ct246-port-forward.service

if ! pct status "$CT_ID" | grep -q running; then
  echo "Starting CT $CT_ID..."
  pct start "$CT_ID"
  sleep 8
fi

pct exec "$CT_ID" -- bash -lc 'systemctl enable --now ssh || systemctl enable --now ssh.service || true; systemctl restart ssh || systemctl restart ssh.service || true; systemctl is-active ssh || systemctl is-active ssh.service || true'

echo ""
echo "-- Service status --"
systemctl is-enabled engel-ct246-port-forward.service
systemctl is-active engel-ct246-port-forward.service

echo ""
echo "-- Forward rules --"
iptables -t nat -S | grep -E "24622|10.246.0.2" || true
iptables -S FORWARD | grep -E "10.246.0.2.*22" || true

echo ""
echo "-- Host local test --"
if timeout 3 bash -lc 'cat < /dev/null > /dev/tcp/192.0.2.50/24622'; then
  echo "PASS host local 192.0.2.50:24622 open"
else
  echo "ERROR: host local 192.0.2.50:24622 self-test failed" >&2
  exit 5
fi

mkdir -p /root/engel-receipts
cat > /root/engel-receipts/engel_ct246_persistent_forward.json <<EOF
{
  "schema": "engel_ct246_persistent_forward_v1",
  "ok": true,
  "host_ip": "$HOST_IP",
  "ct_id": $CT_ID,
  "ct_ip": "$CT_IP",
  "host_port": $HOST_PORT,
  "ct_port": $CT_PORT,
  "script_path": "$SCRIPT_PATH",
  "service_path": "$SERVICE_PATH",
  "sysctl_path": "$SYSCTL_PATH",
  "storage_mutation_performed": false,
  "vault_used": false,
  "installed_at_utc": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF

echo ""
echo "=== Persistent forward installed ==="
echo "Receipt: /root/engel-receipts/engel_ct246_persistent_forward.json"
'@

$encodedRemote = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($remote))
$sshCommand = "echo $encodedRemote | base64 -d >/tmp/install_engel_ct246_persistent_forward.sh; chmod +x /tmp/install_engel_ct246_persistent_forward.sh; bash /tmp/install_engel_ct246_persistent_forward.sh"

Write-Host "Engel CT 246 persistent forward installer"
Write-Host "Type the Proxmox root password when SSH asks."
Write-Host "No password is saved or printed."
ssh -tt -o StrictHostKeyChecking=accept-new root@192.0.2.50 $sshCommand
