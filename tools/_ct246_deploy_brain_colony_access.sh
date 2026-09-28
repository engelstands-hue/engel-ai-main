#!/bin/bash
# Deploy local-first brain + desk colony status pack (keeps peer-storm/memory guards).
set -euo pipefail
ROOT=/opt/engel
TS="$(date -u +%Y%m%dT%H%M%SZ)"
BK="$ROOT/backups/discord_brain_colony_access_${TS}"
mkdir -p "$BK" "$ROOT/run/discord_bridge/storm" "$ROOT/memory"

echo "=== BACKUP ==="
cp -a "$ROOT/tools/engel_discord_bridge.py" "$BK/" 2>/dev/null || true
cp -a "$ROOT/memory/ENGEL_NVIDIA_NIM_LANE_MAP_V1.json" "$BK/" 2>/dev/null || true

echo "=== INSTALL ==="
cp -a /tmp/engel_discord_bridge.py "$ROOT/tools/"
cp -a /tmp/engel_main_server_chat_http_service.py "$ROOT/tools/" 2>/dev/null || true
cp -a /tmp/engel_chat_health_watchdog.py "$ROOT/tools/" 2>/dev/null || true
cp -a /tmp/ENGEL_NVIDIA_NIM_LANE_MAP_V1.json "$ROOT/memory/"
cp -a /tmp/verify_engel_discord_peer_storm_guard.py "$ROOT/tools/"
cp -a /tmp/verify_engel_nvidia_nim.py "$ROOT/tools/"
cp -a /tmp/verify_engel_chat_memory_discipline.py "$ROOT/tools/" 2>/dev/null || true

systemctl restart engel-discord-bridge.service \
  engel-discord-desk-research.service \
  engel-discord-desk-product.service \
  engel-discord-desk-community.service \
  engel-discord-desk-support.service \
  engel-discord-desk-sales.service \
  engel-discord-desk-ops.service
# Chat already has memory discipline; restart only if source updated this pass.
if [[ -f /tmp/engel_main_server_chat_http_service.py ]]; then
  systemctl restart engel-main-chat.service || true
fi
sleep 8

echo "=== ACTIVE ==="
systemctl is-active engel-main-chat.service engel-discord-bridge.service \
  engel-discord-desk-research.service engel-discord-desk-product.service \
  engel-discord-desk-community.service engel-discord-desk-support.service \
  engel-discord-desk-sales.service engel-discord-desk-ops.service

echo "=== NEEDLES ==="
grep -n 'discord_local_first\|discord_nvidia_first = False\|force_provider\] = False\|build_desk_colony_status_pack\|desk_asks_main\|BoundedThreadingHTTPServer\|DESK_PEER_MAX_TURNS' \
  "$ROOT/tools/engel_discord_bridge.py" "$ROOT/tools/engel_main_server_chat_http_service.py" | head -40

echo "=== VERIFIERS ==="
cd "$ROOT/tools"
/opt/engel/.venv/bin/python verify_engel_discord_peer_storm_guard.py
/opt/engel/.venv/bin/python verify_engel_nvidia_nim.py
/opt/engel/.venv/bin/python verify_engel_chat_memory_discipline.py
/opt/engel/.venv/bin/python verify_engel_discord_main_desk_charter_collab.py
/opt/engel/.venv/bin/python verify_engel_discord_prompt_leak_guard.py
/opt/engel/.venv/bin/python verify_engel_discord_smart_standing_watch.py
/opt/engel/.venv/bin/python verify_engel_discord_owner_quiet_proactive.py

echo "=== BRAIN + COLONY PROOF ==="
/opt/engel/.venv/bin/python - <<'PY'
import types, sys, json
sys.path.insert(0, "/opt/engel/tools")
discord = types.ModuleType("discord")
class _Dummy: pass
discord.Client = _Dummy
discord.Message = _Dummy
discord.ClientUser = _Dummy
discord.DMChannel = _Dummy
discord.Intents = types.SimpleNamespace(default=lambda: types.SimpleNamespace(message_content=True))
discord.Status = types.SimpleNamespace(online="online")
discord.Game = lambda *a, **k: None
sys.modules["discord"] = discord
sys.modules.setdefault("aiohttp", types.ModuleType("aiohttp"))
import engel_discord_bridge as b
b.DESK_NAME = "ops"
p = {"prefer_fast_local_chat": True, "metadata": {}}
b.apply_discord_mouth_nvidia_brain(p, desk_name="main", prompt="collab with desks")
assert p.get("force_provider") is False
assert p.get("automatic_provider_after_local_failure_only") is True
assert p["metadata"].get("discord_local_first") is True
assert p["metadata"].get("discord_nvidia_first") is False
assert "nim:" in str(p["metadata"].get("discord_brain") or "")
pack = b.build_desk_colony_status_pack("android workers status and ask Engel AI Main", force=True)
assert "ENGEL COLONY STATUS" in pack
assert "read-only" in pack.lower() or "cannot control" in pack.lower()
print("BRAIN_LOCAL_FIRST_OK")
print("COLONY_STATUS_PACK_OK")
print(pack[:500])
# Main desk_asks_main path
b.DESK_NAME = ""
class FakeAuthor:
    def __init__(self):
        self.bot = True
        self.id = "1545932762748428288"
        self.mentions = []
class FakeChannel:
    def __init__(self):
        self.id = "1546242144065294477"
        self.parent_id = "1545919138235678822"
        self.parent = types.SimpleNamespace(id="1545919138235678822", name="ops", category=None, parent_id=None)
        self.name = "Ops desk"
        self.category = None
        self.guild = types.SimpleNamespace(id="0")
class FakeMsg:
    def __init__(self, content):
        self.content = content
        self.author = FakeAuthor()
        self.channel = FakeChannel()
        self.mentions = []
        self.attachments = []
bot = types.SimpleNamespace(id="1506157762785312808", mentioned_in=lambda m: False)
a, r = b.main_desk_collab_decision(FakeMsg("ask Engel AI Main for device status help"), bot)
print("desk_asks_main_decision", a, r)
assert a.startswith("allow"), (a, r)
print("MAIN_DESK_ASK_MAIN_OK")
PY

echo "=== HEALTH / CPU ==="
curl -sS --max-time 20 http://127.0.0.1:8765/health -o /tmp/engel_chat_health.json || true
/opt/engel/.venv/bin/python -c 'import json;from pathlib import Path;d=json.loads(Path("/tmp/engel_chat_health.json").read_text());rp=d.get("resource_pressure") or {};print("health",d.get("ok"),"pressure",rp.get("pressure"),"threads",rp.get("python_active_threads"),rp.get("threads_proc"),"anon_mb",int(rp.get("rss_anon_kb") or 0)//1024)'
uptime
ps -eo pid,pcpu,rss,nlwp,cmd | grep -E 'engel_discord_bridge|engel_main_server_chat' | grep -v grep || true
CHAT_PID=$(systemctl show engel-main-chat.service -p MainPID --value)
grep -E '^(Threads|VmRSS|RssAnon):' /proc/$CHAT_PID/status || true

RECEIPT="$ROOT/receipts/ct246_brain_colony_access_${TS}.txt"
{
  echo "ts=$TS"
  echo "backup=$BK"
  uptime
  systemctl is-active engel-main-chat.service engel-discord-bridge.service
} >"$RECEIPT"
echo "RECEIPT=$RECEIPT"
echo "DEPLOY_BRAIN_COLONY_ACCESS_OK"
