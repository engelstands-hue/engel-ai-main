#!/bin/bash
# Applied on CT246 by Set-EngelGifSearchKeys.ps1. Merges the scp'd key file into the
# root-only Discord secret env, restarts the bridge, and VERIFIES with a live search
# so success means search actually works. Prints RESULT:<keycount>:<search_source>.
f=/opt/engel/run/secrets/discord.env
src=/tmp/engel_gifkeys.env
mkdir -p "$(dirname "$f")"; touch "$f"
grep -vE "^ENGEL_(TENOR|GIPHY)_API_KEY=" "$f" > "$f.tmp" 2>/dev/null || true
cat "$src" >> "$f.tmp"
mv -f "$f.tmp" "$f"
chmod 600 "$f"
shred -u "$src" 2>/dev/null || rm -f "$src"
systemctl restart engel-discord-bridge.service
sleep 2
n=$(grep -cE "^ENGEL_(TENOR|GIPHY)_API_KEY=" "$f")
source=$(
  set -a; . "$f"; set +a
  /opt/engel/.venv/bin/python - <<'PY' 2>/dev/null
import sys, asyncio
sys.path.insert(0, "/opt/engel/tools")
import engel_discord_bridge as d
paths, s = asyncio.run(d.fetch_real_gifs("happy dog", 1))
print(s if (paths and s) else "none")
PY
)
echo "RESULT:${n}:${source:-none}"
