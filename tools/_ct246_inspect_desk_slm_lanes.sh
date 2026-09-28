#!/bin/bash
set -euo pipefail
echo "=== DESK UNIT ENV (NIM + PROACTIVE + MODEL) ==="
for d in research product community support sales ops; do
  echo "==== $d ===="
  echo "-- drop-ins --"
  ls -la "/etc/systemd/system/engel-discord-desk-${d}.service.d/" 2>/dev/null || true
  for f in /etc/systemd/system/engel-discord-desk-${d}.service.d/*.conf; do
    echo "FILE $f"
    cat "$f"
  done
  echo "-- live environ (filtered) --"
  PID="$(systemctl show -p MainPID --value engel-discord-desk-${d}.service)"
  tr '\0' '\n' < "/proc/${PID}/environ" 2>/dev/null | grep -E 'PROACTIVE|NIM|NVIDIA|MODEL|DESK_NAME|CHANNEL|ENGEL_ROOT|CHAT_' | sort || true
done
echo "=== MAIN BRIDGE FILTERED ==="
PID="$(systemctl show -p MainPID --value engel-discord-bridge.service)"
tr '\0' '\n' < "/proc/${PID}/environ" 2>/dev/null | grep -E 'PROACTIVE|NIM|NVIDIA|MODEL|DESK_NAME|CHANNEL' | sort || true
echo "=== LOCAL MODELS ON CT246 ==="
ls -la /opt/engel/models 2>/dev/null | head -40 || true
find /opt/engel -maxdepth 3 -iname '*.gguf' 2>/dev/null | head -30 || true
echo "=== CHARTERS / NIM MAP PRESENT ==="
ls -la /opt/engel/memory/ENGEL_DISCORD_DESK_CHARTERS_V1.json /opt/engel/memory/ENGEL_NVIDIA_NIM_LANE_MAP_V1.json 2>/dev/null || true
echo "=== PROACTIVE STATE SILENCE ==="
for d in research product community support sales ops; do
  python3 -c "import json; d=json.load(open('/opt/engel/desks/$d/run/discord_bridge/proactive_state.json')); print('$d', {k:d.get(k) for k in ['owner_silenced','owner_silence_reason','last_post_at_utc','kind']})"
done
