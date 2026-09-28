#!/bin/bash
set -euo pipefail
echo "=== MAIN BRIDGE PROACTIVE ==="
systemctl cat engel-discord-bridge.service 2>/dev/null | grep -i PROACTIVE || echo none
PID="$(systemctl show -p MainPID --value engel-discord-bridge.service)"
tr '\0' '\n' < "/proc/${PID}/environ" 2>/dev/null | grep PROACTIVE || echo "main env: no PROACTIVE"
echo "=== IDLE COUNTS ==="
for d in research product community support sales ops; do
  c="$(journalctl -u "engel-discord-desk-${d}.service" --since '15 minutes ago' --no-pager | grep -c 'PROACTIVE/INITIATE idle' || true)"
  echo "${d} idle_lines=${c}"
done
echo "=== ARMED OR POSTED SINCE RESTART ==="
journalctl -u engel-discord-desk-research.service -u engel-discord-desk-product.service -u engel-discord-desk-community.service -u engel-discord-desk-support.service -u engel-discord-desk-sales.service -u engel-discord-desk-ops.service --since '15 minutes ago' --no-pager | grep -E 'PROACTIVE/INITIATE armed|posted proactive|posted=True' || echo none_armed_or_posted
echo "=== HASHES ==="
md5sum /opt/engel/tools/engel_discord_desk_proactive.py /opt/engel/tools/engel_discord_bridge.py
echo "=== SOURCE NEEDLES ==="
grep -n 'owner_requested_full_quiet\|note_owner_silence\|owner silenced\|OWNER_QUIET_ACK' /opt/engel/tools/engel_discord_desk_proactive.py /opt/engel/tools/engel_discord_bridge.py | head -40
