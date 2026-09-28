#!/bin/bash
set -euo pipefail
echo "=== BEFORE proactive.conf ==="
for d in research product community support sales ops; do
  f="/etc/systemd/system/engel-discord-desk-${d}.service.d/30-proactive.conf"
  echo "-- $d --"
  cat "$f" 2>/dev/null || echo missing
done
echo "=== DISABLING PROACTIVE ==="
for d in research product community support sales ops; do
  f="/etc/systemd/system/engel-discord-desk-${d}.service.d/30-proactive.conf"
  printf '%s\n' \
    '[Service]' \
    'Environment=ENGEL_DISCORD_PROACTIVE=0' \
    'Environment=ENGEL_DISCORD_PROACTIVE_INTERVAL_SECONDS=3600' \
    > "$f"
done
systemctl daemon-reload
systemctl restart \
  engel-discord-desk-research.service \
  engel-discord-desk-product.service \
  engel-discord-desk-community.service \
  engel-discord-desk-support.service \
  engel-discord-desk-sales.service \
  engel-discord-desk-ops.service
sleep 4
echo "=== AFTER restart ==="
systemctl is-active \
  engel-discord-desk-research.service \
  engel-discord-desk-product.service \
  engel-discord-desk-community.service \
  engel-discord-desk-support.service \
  engel-discord-desk-sales.service \
  engel-discord-desk-ops.service
for d in research product community support sales ops; do
  echo "-- $d conf --"
  cat "/etc/systemd/system/engel-discord-desk-${d}.service.d/30-proactive.conf"
  echo "-- $d env --"
  tr '\0' '\n' < "/proc/$(systemctl show -p MainPID --value engel-discord-desk-${d}.service)/environ" 2>/dev/null | grep PROACTIVE || true
done
echo "=== journal since restart ==="
for d in research product community support sales ops; do
  echo "-- $d --"
  journalctl -u "engel-discord-desk-${d}.service" --since "1 minute ago" --no-pager | grep -iE 'PROACTIVE|proactive|online|ERROR|idle' | tail -12 || true
done
echo "=== last proactive posts from states ==="
for d in research product community support sales ops; do
  echo "-- $d --"
  cat "/opt/engel/desks/${d}/run/discord_bridge/proactive_state.json" 2>/dev/null || echo missing
done
