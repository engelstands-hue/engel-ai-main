#!/bin/bash
# Deploy chat memory discipline + Discord peer-storm guards to CT246.
set -euo pipefail
ROOT=/opt/engel
TS="$(date -u +%Y%m%dT%H%M%SZ)"
BK="$ROOT/backups/chat_memory_peer_storm_${TS}"
mkdir -p "$BK" "$ROOT/run/discord_bridge/storm" \
  /etc/systemd/system/engel-main-chat.service.d

echo "=== BACKUP ==="
cp -a "$ROOT/tools/engel_main_server_chat_http_service.py" "$BK/" 2>/dev/null || true
cp -a "$ROOT/tools/engel_discord_bridge.py" "$BK/" 2>/dev/null || true
cp -a "$ROOT/tools/engel_chat_health_watchdog.py" "$BK/" 2>/dev/null || true

echo "=== INSTALL SOURCES ==="
cp -a /tmp/engel_main_server_chat_http_service.py "$ROOT/tools/"
cp -a /tmp/engel_discord_bridge.py "$ROOT/tools/"
cp -a /tmp/engel_chat_health_watchdog.py "$ROOT/tools/"
cp -a /tmp/verify_engel_chat_memory_discipline.py "$ROOT/tools/"
cp -a /tmp/verify_engel_discord_peer_storm_guard.py "$ROOT/tools/"
cp -a /tmp/95-chat-memory-discipline.conf \
  /etc/systemd/system/engel-main-chat.service.d/95-chat-memory-discipline.conf

# Peer-storm env for Main + desks (drop-in shared by pattern).
for unit in engel-discord-bridge \
  engel-discord-desk-research engel-discord-desk-product \
  engel-discord-desk-community engel-discord-desk-support \
  engel-discord-desk-sales engel-discord-desk-ops; do
  ddir="/etc/systemd/system/${unit}.service.d"
  mkdir -p "$ddir"
  cat >"$ddir/95-peer-storm-guard.conf" <<'EOF'
[Service]
Environment=ENGEL_DISCORD_PEER_MAX_TURNS=4
Environment=ENGEL_DISCORD_PEER_COOLDOWN_SECONDS=12
Environment=ENGEL_DISCORD_WORK_COLLAB_MAX_TURNS=32
Environment=ENGEL_DISCORD_DESK_PEER_MAX_TURNS=2
Environment=ENGEL_DISCORD_DESK_PEER_COOLDOWN_SECONDS=30
Environment=ENGEL_DISCORD_STORM_WINDOW_SECONDS=45
Environment=ENGEL_DISCORD_STORM_BOT_MSG_THRESHOLD=4
Environment=ENGEL_DISCORD_PEER_TURNS_IDLE_RESET_SECONDS=1800
Environment=ENGEL_DISCORD_HOUSE_PEER_MAX_TURNS=6
Environment=ENGEL_DISCORD_STORM_DIR=/opt/engel/run/discord_bridge/storm
EOF
done

systemctl daemon-reload

echo "=== RESTART CHAT + DISCORD ==="
systemctl restart engel-main-chat.service
systemctl restart engel-discord-bridge.service \
  engel-discord-desk-research.service \
  engel-discord-desk-product.service \
  engel-discord-desk-community.service \
  engel-discord-desk-support.service \
  engel-discord-desk-sales.service \
  engel-discord-desk-ops.service
systemctl try-restart engel-chat-health-watchdog.service 2>/dev/null || true
sleep 8

echo "=== ACTIVE ==="
systemctl is-active engel-main-chat.service \
  engel-discord-bridge.service \
  engel-discord-desk-research.service \
  engel-discord-desk-product.service \
  engel-discord-desk-community.service \
  engel-discord-desk-support.service \
  engel-discord-desk-sales.service \
  engel-discord-desk-ops.service

echo "=== SOURCE NEEDLES ==="
grep -n 'BoundedThreadingHTTPServer\|ENGEL_CHAT_MAX_IN_FLIGHT\|resource_pressure' \
  "$ROOT/tools/engel_main_server_chat_http_service.py" | head -20
grep -n 'DESK_PEER_MAX_TURNS\|try_claim_peer_message\|channel_peer_storm_active\|WORK_COLLAB_MAX_TURNS' \
  "$ROOT/tools/engel_discord_bridge.py" | head -30

echo "=== VERIFIERS ==="
cd "$ROOT/tools"
/opt/engel/.venv/bin/python verify_engel_chat_memory_discipline.py
/opt/engel/.venv/bin/python verify_engel_discord_peer_storm_guard.py
/opt/engel/.venv/bin/python verify_engel_discord_main_desk_charter_collab.py || true
/opt/engel/.venv/bin/python verify_engel_discord_smart_standing_watch.py || true
/opt/engel/.venv/bin/python verify_engel_discord_owner_quiet_proactive.py || true
/opt/engel/.venv/bin/python verify_engel_discord_prompt_leak_guard.py || true

echo "=== HEALTH + RESOURCE PRESSURE ==="
curl -sS --max-time 25 http://127.0.0.1:8765/health -o /tmp/engel_chat_health.json
/opt/engel/.venv/bin/python - <<'PY'
import json
from pathlib import Path
d = json.loads(Path("/tmp/engel_chat_health.json").read_text(encoding="utf-8"))
rp = d.get("resource_pressure") or {}
print(
    "health_ok", d.get("ok"),
    "pressure", rp.get("pressure"),
    "py_threads", rp.get("python_active_threads"),
    "proc_threads", rp.get("threads_proc"),
    "in_flight", rp.get("chat_in_flight"),
    "http_max", rp.get("http_max_threads"),
)
assert d.get("ok") is True
assert "resource_pressure" in d
assert int(rp.get("http_max_threads") or 0) >= 16
print("CHAT_HEALTH_RESOURCE_OK")
PY

echo "=== PROCESS CPU/RAM SNAPSHOT ==="
ps -eo pid,pcpu,rss,nlwp,cmd --sort=-pcpu | head -25
echo "--- chat unit ---"
systemctl show engel-main-chat.service -p MainPID,NRestarts,ActiveState --no-pager
CHAT_PID="$(systemctl show engel-main-chat.service -p MainPID --value)"
if [[ -n "$CHAT_PID" && "$CHAT_PID" != "0" ]]; then
  grep -E '^(Threads|VmRSS|RssAnon):' "/proc/${CHAT_PID}/status" || true
fi
echo "--- discord bridges ---"
ps -eo pid,pcpu,rss,cmd | grep -E 'engel_discord_bridge' | grep -v grep || true

RECEIPT="$ROOT/receipts/ct246_chat_memory_peer_storm_fix_${TS}.txt"
{
  echo "ts=$TS"
  echo "backup=$BK"
  echo "chat_pid=$CHAT_PID"
  systemctl is-active engel-main-chat.service engel-discord-bridge.service
  date -u
} >"$RECEIPT"
echo "RECEIPT=$RECEIPT"
echo "DEPLOY_CHAT_MEMORY_PEER_STORM_OK"
