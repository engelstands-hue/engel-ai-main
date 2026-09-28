#!/bin/bash
set -euo pipefail
echo "=== HEALTH ==="
curl -sS --max-time 20 http://127.0.0.1:8765/health -o /tmp/engel_chat_health.json
/opt/engel/.venv/bin/python -c '
import json
from pathlib import Path
p = Path("/tmp/engel_chat_health.json")
d = json.loads(p.read_text(encoding="utf-8"))
rp = d.get("resource_pressure") or {}
print("health_ok", d.get("ok"), "pressure", rp.get("pressure"),
      "py_threads", rp.get("python_active_threads"),
      "proc_threads", rp.get("threads_proc"),
      "in_flight", rp.get("chat_in_flight"),
      "http_max", rp.get("http_max_threads"),
      "anon_mb", int(rp.get("rss_anon_kb") or 0)//1024)
assert d.get("ok") is True
assert "resource_pressure" in d
assert int(rp.get("http_max_threads") or 0) >= 16
print("CHAT_HEALTH_RESOURCE_OK")
'
echo "=== LOAD / MEM ==="
uptime
free -h
echo "=== TOP CPU ==="
ps -eo pid,pcpu,rss,nlwp,cmd --sort=-pcpu | head -20
echo "=== CHAT PROC ==="
CHAT_PID="$(systemctl show engel-main-chat.service -p MainPID --value)"
echo "chat_pid=$CHAT_PID nrestarts=$(systemctl show engel-main-chat.service -p NRestarts --value)"
if [[ -n "$CHAT_PID" && "$CHAT_PID" != "0" ]]; then
  grep -E '^(Threads|VmRSS|RssAnon):' "/proc/${CHAT_PID}/status" || true
fi
echo "=== DISCORD CPU ==="
ps -eo pid,pcpu,rss,nlwp,cmd | grep -E 'engel_discord_bridge' | grep -v grep || true
echo "=== ENV PROOF ==="
systemctl show engel-main-chat.service -p Environment --no-pager | tr ' ' '\n' | grep -E 'ENGEL_CHAT_|ENGEL_LOCAL_MODEL_THREADS|ENGEL_LOCAL_MODEL_CACHE' || true
systemctl show engel-discord-bridge.service -p Environment --no-pager | tr ' ' '\n' | grep -E 'ENGEL_DISCORD_PEER|ENGEL_DISCORD_STORM|ENGEL_DISCORD_WORK|ENGEL_DISCORD_DESK_PEER|ENGEL_DISCORD_HOUSE' || true
echo "=== JOURNAL ==="
journalctl -u engel-main-chat.service --since "5 minutes ago" --no-pager | grep -iE 'http_max_threads|resource-growth|listening on|ERROR|Traceback' | tail -15 || true
journalctl -u engel-discord-bridge.service --since "5 minutes ago" --no-pager | grep -iE 'online|peer-storm|ERROR' | tail -10 || true
for d in product research sales; do
  journalctl -u "engel-discord-desk-${d}.service" --since "5 minutes ago" --no-pager | grep -iE 'online|peer-storm|ERROR' | tail -5 || true
done
TS=$(date -u +%Y%m%dT%H%M%SZ)
RECEIPT="/opt/engel/receipts/ct246_chat_memory_peer_storm_proof_${TS}.txt"
{
  echo "ts=$TS"
  echo "chat_pid=$CHAT_PID"
  uptime
  free -h
  grep -E '^(Threads|VmRSS|RssAnon):' "/proc/${CHAT_PID}/status" || true
  ps -eo pid,pcpu,rss,nlwp,cmd | grep -E 'engel_discord_bridge' | grep -v grep || true
} >"$RECEIPT"
echo "RECEIPT=$RECEIPT"
echo "PROOF_OK"
