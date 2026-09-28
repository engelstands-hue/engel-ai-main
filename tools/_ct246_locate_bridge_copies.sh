#!/bin/bash
set -euo pipefail
echo "=== where desks load bridge from ==="
for d in research product; do
  echo "-- $d --"
  systemctl cat "engel-discord-desk-${d}.service" 2>/dev/null | grep -E 'ExecStart|WorkingDirectory|PYTHONPATH|ENGEL_ROOT' | head -20
done
systemctl cat engel-discord-bridge.service 2>/dev/null | grep -E 'ExecStart|WorkingDirectory|PYTHONPATH' | head -20
ls -la /opt/engel/desks/product/tools/engel_discord_bridge.py /opt/engel/tools/engel_discord_bridge.py 2>/dev/null || true
