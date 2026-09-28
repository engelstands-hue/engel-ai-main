#!/bin/bash
set -euo pipefail
echo "=== MAIN BRIDGE ENV ==="
PID="$(systemctl show -p MainPID --value engel-discord-bridge.service)"
echo "pid=$PID"
tr '\0' '\n' < "/proc/${PID}/environ" | grep -E 'REPLY_MODE|CHANNEL|PEER|ENGAGED|DESK|HOUSE|YIELD|PROACTIVE|CHAT' | sort || true
echo "=== MAIN JOURNAL desk/yield/answer (2h) ==="
journalctl -u engel-discord-bridge.service --since "2 hours ago" --no-pager | grep -iE 'yield|desk|standing|should_answer|skip|mute|accepted|peer|house|proactive|barg|forum|thread' | tail -80 || true
echo "=== RECENT MAIN ACCEPTED MESSAGES ==="
journalctl -u engel-discord-bridge.service --since "3 hours ago" --no-pager | grep -iE 'message accepted|named-gap|reply|channel=' | tail -60 || true
echo "=== DESK JOURNALS standing-watch recent ==="
for d in research product community support sales ops; do
  echo "-- $d --"
  journalctl -u "engel-discord-desk-${d}.service" --since "3 hours ago" --no-pager | grep -iE 'standing|posted|proactive|accepted' | tail -15 || true
done
