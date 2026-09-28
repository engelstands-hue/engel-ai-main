#!/bin/bash
set -euo pipefail
ROOT=/opt/engel
TS="$(date -u +%Y%m%dT%H%M%SZ)"
BK="$ROOT/backups/discord_main_charter_collab_${TS}"
mkdir -p "$BK"
cp -a "$ROOT/tools/engel_discord_bridge.py" "$BK/"
cp -a /tmp/engel_discord_bridge.py "$ROOT/tools/engel_discord_bridge.py"
cp -a /tmp/verify_engel_discord_main_desk_charter_collab.py "$ROOT/tools/"
# Shared bridge is the ExecStart target for Main + all desks.
systemctl restart engel-discord-bridge.service \
  engel-discord-desk-research.service \
  engel-discord-desk-product.service \
  engel-discord-desk-community.service \
  engel-discord-desk-support.service \
  engel-discord-desk-sales.service \
  engel-discord-desk-ops.service
sleep 5
echo "=== ACTIVE ==="
systemctl is-active engel-discord-bridge.service \
  engel-discord-desk-research.service \
  engel-discord-desk-product.service \
  engel-discord-desk-community.service \
  engel-discord-desk-support.service \
  engel-discord-desk-sales.service \
  engel-discord-desk-ops.service
echo "=== SOURCE NEEDLES ON CT246 ==="
grep -n 'main_desk_collab_decision\|Main suppresses desk off-topic\|allow_charter\|collaborating in the\|main_should_yield_desk_lane' \
  "$ROOT/tools/engel_discord_bridge.py" | head -40
echo "=== VERIFIER ==="
cd "$ROOT/tools"
/opt/engel/.venv/bin/python verify_engel_discord_main_desk_charter_collab.py
echo "=== FOCUSED DECISION PROOF ==="
/opt/engel/.venv/bin/python - << 'PY'
import types, sys
sys.path.insert(0, "/opt/engel/tools")
# Minimal discord stub if import needs it — bridge already imported discord at boot;
# for offline decision test, import helpers after stubs.
import importlib
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
import engel_discord_bridge as b
# Force Main mouth (no desk name)
b.DESK_NAME = ""

class FakeAuthor:
    def __init__(self, bot=True, id="1545926475700502608"):
        self.bot = bot
        self.id = id
        self.mentions = []

class FakeChannel:
    def __init__(self, id="1546242141779525673", parent_id="1545917511122427964"):
        self.id = id
        self.parent_id = parent_id
        self.parent = types.SimpleNamespace(id=parent_id, name="product", category=None, parent_id=None)
        self.name = "Product desk — standing watch"
        self.category = None
        self.guild = types.SimpleNamespace(id="0")

class FakeMsg:
    def __init__(self, content, bot=True):
        self.content = content
        self.author = FakeAuthor(bot=bot)
        self.channel = FakeChannel()
        self.mentions = []
        self.attachments = []

bot = types.SimpleNamespace(id="1545916677269758124", mentioned_in=lambda m: False)

# On-charter product standing-watch → allow
m1 = FakeMsg("Engel Product on standing watch. Focus this cycle: roadmap and MVP scope.")
a1, r1 = b.main_desk_collab_decision(m1, bot)
print("on_charter", a1, r1)
assert a1 == "allow_charter", (a1, r1)

# Off-topic → suppress
m2 = FakeMsg("Want to talk about random weather GIFs and nothing product related?")
a2, r2 = b.main_desk_collab_decision(m2, bot)
print("off_charter", a2, r2)
assert a2 == "suppress", (a2, r2)

# Josh summon → allow_summon
m3 = FakeMsg("engel help with the product roadmap", bot=False)
m3.author = FakeAuthor(bot=False, id="DISCORD_OWNER_USER_ID")
a3, r3 = b.main_desk_collab_decision(m3, bot)
print("summon", a3, r3)
assert a3 == "allow_summon", (a3, r3)

print("MAIN_DESK_CHARTER_COLLAB_DECISION_OK")
print("lane_from_thread", b.discord_matching_desk_for_chat(m1))
assert b.discord_matching_desk_for_chat(m1) == "product"
print("DESK_LANE_RESOLVE_OK")
PY
echo "=== UNITS ONLINE ==="
journalctl -u engel-discord-bridge.service --since "1 minute ago" --no-pager | grep -iE 'online|ERROR|charter|suppress|collab' | tail -20 || true
for d in product research; do
  journalctl -u "engel-discord-desk-${d}.service" --since "1 minute ago" --no-pager | grep -iE 'online|PROACTIVE|ERROR' | tail -8 || true
done
