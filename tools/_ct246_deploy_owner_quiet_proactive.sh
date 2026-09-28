#!/bin/bash
# Deploy owner-quiet proactive fix to CT246 desks. Keeps ENGEL_DISCORD_PROACTIVE=0.
set -euo pipefail
ROOT=/opt/engel
TS="$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$ROOT/tools" "$ROOT/backups/discord_owner_quiet_${TS}"
for f in engel_discord_desk_proactive.py engel_discord_bridge.py verify_engel_discord_owner_quiet_proactive.py; do
  if [[ -f "$ROOT/tools/$f" ]]; then
    cp -a "$ROOT/tools/$f" "$ROOT/backups/discord_owner_quiet_${TS}/$f"
  fi
done
cp -a /tmp/engel_discord_desk_proactive.py "$ROOT/tools/engel_discord_desk_proactive.py"
cp -a /tmp/engel_discord_bridge.py "$ROOT/tools/engel_discord_bridge.py"
cp -a /tmp/verify_engel_discord_owner_quiet_proactive.py "$ROOT/tools/verify_engel_discord_owner_quiet_proactive.py"
# Keep spam killed until Josh re-enables proactive explicitly.
for d in research product community support sales ops; do
  f="/etc/systemd/system/engel-discord-desk-${d}.service.d/30-proactive.conf"
  printf '%s\n' \
    '[Service]' \
    'Environment=ENGEL_DISCORD_PROACTIVE=0' \
    'Environment=ENGEL_DISCORD_PROACTIVE_INTERVAL_SECONDS=3600' \
    > "$f"
  # Also stamp silence into existing state so even a mistaken re-enable stays quiet.
  state="$ROOT/desks/${d}/run/discord_bridge/proactive_state.json"
  if [[ -f "$state" ]]; then
    /opt/engel/.venv/bin/python - << PY
import json, time
from pathlib import Path
from datetime import datetime, timezone
p = Path("$state")
data = json.loads(p.read_text(encoding="utf-8"))
if not isinstance(data, dict):
    data = {}
now = time.time()
data["owner_silenced"] = True
data["owner_silence_reason"] = "josh_spam_stop_20260910"
data["owner_silence_at_utc"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z")
data["owner_silence_until_unix"] = now + 604800
p.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print("silenced", p)
PY
  fi
done
systemctl daemon-reload
systemctl restart \
  engel-discord-desk-research.service \
  engel-discord-desk-product.service \
  engel-discord-desk-community.service \
  engel-discord-desk-support.service \
  engel-discord-desk-sales.service \
  engel-discord-desk-ops.service
sleep 4
echo "=== unit active ==="
systemctl is-active \
  engel-discord-desk-research.service \
  engel-discord-desk-product.service \
  engel-discord-desk-community.service \
  engel-discord-desk-support.service \
  engel-discord-desk-sales.service \
  engel-discord-desk-ops.service
echo "=== proactive env + idle proof ==="
for d in research product community support sales ops; do
  echo "-- $d --"
  tr '\0' '\n' < "/proc/$(systemctl show -p MainPID --value engel-discord-desk-${d}.service)/environ" | grep PROACTIVE || true
  journalctl -u "engel-discord-desk-${d}.service" --since "1 minute ago" --no-pager | grep -iE 'PROACTIVE|proactive|online|ERROR|silen' | tail -8 || true
done
echo "=== verifier ==="
cd "$ROOT/tools"
/opt/engel/.venv/bin/python verify_engel_discord_owner_quiet_proactive.py
echo "=== phrase path check ==="
/opt/engel/.venv/bin/python - << 'PY'
from pathlib import Path
import tempfile, os, sys
sys.path.insert(0, "/opt/engel/tools")
from engel_discord_desk_proactive import (
    note_owner_silence, owner_silence_active, should_post, clear_owner_silence
)
os.environ["ENGEL_DISCORD_PROACTIVE"] = "1"
with tempfile.TemporaryDirectory() as tmp:
    run = Path(tmp)
    note_owner_silence(run, reason="owner_stop")
    ok, status = should_post(desk_name="research", run_dir=run, channel_id="1", token="x", force=True)
    assert ok is False and "owner silenced" in status, (ok, status)
    clear_owner_silence(run)
    silenced, _ = owner_silence_active(run)
    assert silenced is False
print("STOP_PHRASE_CODE_PATH_OK")
# Bridge source phrase coverage
text = Path("/opt/engel/tools/engel_discord_bridge.py").read_text(encoding="utf-8")
for needle in ("owner_requested_full_quiet", "apply_owner_full_quiet", "OWNER_QUIET_ACK_REPLY", '"done"', '"finished"'):
    assert needle in text, needle
print("BRIDGE_OWNER_QUIET_SOURCE_OK")
PY
echo "=== state silence flags ==="
for d in research product community support sales ops; do
  python3 -c "import json; d=json.load(open('/opt/engel/desks/$d/run/discord_bridge/proactive_state.json')); print('$d', 'silenced='+str(d.get('owner_silenced')), 'reason='+str(d.get('owner_silence_reason')))"
done
