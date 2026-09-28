#!/bin/bash
set -euo pipefail
ROOT=/opt/engel
cd "$ROOT/tools"
/opt/engel/.venv/bin/python - <<'PY'
import types, sys
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
b.apply_discord_mouth_nvidia_brain(p, desk_name="main", prompt="collab")
assert p.get("force_provider") is False
assert p.get("automatic_provider_after_local_failure_only") is True
assert p["metadata"].get("discord_local_first") is True
assert p["metadata"].get("discord_nvidia_first") is False
assert "local_first" in str(p["metadata"].get("discord_brain") or "")
pack = b.build_desk_colony_status_pack(
    "android workers status and ask Engel AI Main", force=True
)
assert "ENGEL COLONY STATUS" in pack
assert "read-only" in pack.lower() or "cannot control" in pack.lower()
print("BRAIN_LOCAL_FIRST_OK")
print("COLONY_STATUS_PACK_OK")
print(pack[:700])

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
        self.parent = types.SimpleNamespace(
            id="1545919138235678822", name="ops", category=None, parent_id=None
        )
        self.name = "Ops"
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
a, r = b.main_desk_collab_decision(
    FakeMsg("ask Engel AI Main for device status help"), bot
)
print("desk_asks_main_decision", a, r)
assert a.startswith("allow"), (a, r)
print("MAIN_DESK_ASK_MAIN_OK")
PY

curl -sS --max-time 20 http://127.0.0.1:8765/health -o /tmp/engel_chat_health.json
/opt/engel/.venv/bin/python - <<'PY'
import json
from pathlib import Path
d = json.loads(Path("/tmp/engel_chat_health.json").read_text(encoding="utf-8"))
rp = d.get("resource_pressure") or {}
print(
    "health", d.get("ok"),
    "pressure", rp.get("pressure"),
    "py", rp.get("python_active_threads"),
    "proc", rp.get("threads_proc"),
    "anon_mb", int(rp.get("rss_anon_kb") or 0) // 1024,
    "http_max", rp.get("http_max_threads"),
)
assert d.get("ok") is True
assert "resource_pressure" in d
print("CHAT_HEALTH_OK")
PY
echo "=== LOAD ==="
uptime
echo "=== PROCESSES ==="
ps -eo pid,pcpu,rss,nlwp,cmd | grep -E 'engel_discord_bridge|engel_main_server_chat' | grep -v grep || true
CHAT_PID="$(systemctl show engel-main-chat.service -p MainPID --value)"
grep -E '^(Threads|VmRSS|RssAnon):' "/proc/${CHAT_PID}/status" || true
echo "=== DISCORD ONLINE ==="
journalctl -u engel-discord-bridge.service --since "2 minutes ago" --no-pager | grep -i online | tail -5 || true
journalctl -u engel-discord-desk-ops.service --since "2 minutes ago" --no-pager | grep -iE 'online|PROACTIVE' | tail -5 || true
set +e
/opt/engel/.venv/bin/python verify_engel_nvidia_nim.py
echo "NIM_VERIFY_EXIT=$?"
set -e
TS="$(date -u +%Y%m%dT%H%M%SZ)"
RECEIPT="/opt/engel/receipts/ct246_brain_colony_access_${TS}.txt"
{
  echo "ts=$TS"
  uptime
  systemctl is-active engel-main-chat.service engel-discord-bridge.service
} >"$RECEIPT"
echo "RECEIPT=$RECEIPT"
echo "PROOF_COMPLETE"
