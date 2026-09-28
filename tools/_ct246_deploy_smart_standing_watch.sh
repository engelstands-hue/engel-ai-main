#!/bin/bash
# Re-enable smart standing-watch with distinct per-desk SLM lanes.
set -euo pipefail
ROOT=/opt/engel
TS="$(date -u +%Y%m%dT%H%M%SZ)"
BK="$ROOT/backups/discord_smart_watch_${TS}"
mkdir -p "$BK" "$ROOT/tools" "$ROOT/memory"

for f in engel_discord_desk_proactive.py engel_discord_bridge.py engel_nvidia_discover.py verify_engel_discord_smart_standing_watch.py verify_engel_discord_owner_quiet_proactive.py; do
  if [[ -f "$ROOT/tools/$f" ]]; then cp -a "$ROOT/tools/$f" "$BK/$f"; fi
done
if [[ -f "$ROOT/memory/ENGEL_NVIDIA_NIM_LANE_MAP_V1.json" ]]; then
  cp -a "$ROOT/memory/ENGEL_NVIDIA_NIM_LANE_MAP_V1.json" "$BK/"
fi

cp -a /tmp/engel_discord_desk_proactive.py "$ROOT/tools/"
cp -a /tmp/engel_discord_bridge.py "$ROOT/tools/"
cp -a /tmp/engel_nvidia_discover.py "$ROOT/tools/"
cp -a /tmp/verify_engel_discord_smart_standing_watch.py "$ROOT/tools/"
cp -a /tmp/ENGEL_NVIDIA_NIM_LANE_MAP_V1.json "$ROOT/memory/"

# Distinct SLM per desk (existing Discover catalog — no new paid spend invented).
declare -A DESK_MODEL=(
  [research]="nvidia/nemotron-3-super-120b-a12b"
  [product]="nvidia/nemotron-3-ultra-550b-a55b"
  [community]="nvidia/nemotron-3-nano-omni-30b-a3b-reasoning"
  [support]="nvidia/nemotron-3.5-lightning-30b-a3b"
  [sales]="nvidia/nemotron-3-nano-30b-a3b"
  [ops]="nvidia/llama-3.3-nemotron-super-49b-v1.5"
)

for d in research product community support sales ops; do
  printf '%s\n' \
    '[Service]' \
    'Environment=ENGEL_PREFERRED_FALLBACK_PROVIDER=nvidia' \
    "Environment=ENGEL_NVIDIA_CHAT_MODEL=${DESK_MODEL[$d]}" \
    > "/etc/systemd/system/engel-discord-desk-${d}.service.d/30-nvidia-nim.conf"
  printf '%s\n' \
    '[Service]' \
    'Environment=ENGEL_DISCORD_PROACTIVE=1' \
    'Environment=ENGEL_DISCORD_PROACTIVE_INTERVAL_SECONDS=21600' \
    > "/etc/systemd/system/engel-discord-desk-${d}.service.d/30-proactive.conf"
  # Josh asked standing-watch BACK => clear spam-stop silence (resume).
  state="$ROOT/desks/${d}/run/discord_bridge/proactive_state.json"
  /opt/engel/.venv/bin/python - << PY
import json
from pathlib import Path
from datetime import datetime, timezone
p = Path("$state")
data = {}
if p.is_file():
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        data = {}
if not isinstance(data, dict):
    data = {}
data["owner_silenced"] = False
data["owner_silence_until_unix"] = 0.0
data["owner_silence_cleared_at_utc"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z")
data["owner_silence_clear_reason"] = "josh_resume_standing_watch_20260910"
data["schema"] = data.get("schema") or "engel_discord_proactive_state_v1"
data["desk"] = "$d"
data["slm_model"] = "${DESK_MODEL[$d]}"
p.parent.mkdir(parents=True, exist_ok=True)
p.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print("resumed", p, "model=${DESK_MODEL[$d]}")
PY
done

systemctl daemon-reload
systemctl restart \
  engel-discord-desk-research.service \
  engel-discord-desk-product.service \
  engel-discord-desk-community.service \
  engel-discord-desk-support.service \
  engel-discord-desk-sales.service \
  engel-discord-desk-ops.service
sleep 5

echo "=== ACTIVE ==="
systemctl is-active \
  engel-discord-desk-research.service \
  engel-discord-desk-product.service \
  engel-discord-desk-community.service \
  engel-discord-desk-support.service \
  engel-discord-desk-sales.service \
  engel-discord-desk-ops.service

echo "=== LIVE ENV PROOF (SLM + PROACTIVE) ==="
for d in research product community support sales ops; do
  PID="$(systemctl show -p MainPID --value engel-discord-desk-${d}.service)"
  echo "-- $d pid=$PID --"
  tr '\0' '\n' < "/proc/${PID}/environ" | grep -E 'PROACTIVE|NVIDIA_CHAT_MODEL|DESK_NAME' | sort
done

echo "=== JOURNAL ARMED (no force spam expected) ==="
sleep 8
for d in research product community support sales ops; do
  echo "-- $d --"
  journalctl -u "engel-discord-desk-${d}.service" --since "1 minute ago" --no-pager | grep -iE 'PROACTIVE|proactive|slm=|online|ERROR' | tail -12 || true
done

echo "=== NO IMMEDIATE POSTED=TRUE BLAST ==="
journalctl -u engel-discord-desk-research.service -u engel-discord-desk-product.service -u engel-discord-desk-community.service -u engel-discord-desk-support.service -u engel-discord-desk-sales.service -u engel-discord-desk-ops.service --since "2 minutes ago" --no-pager | grep -E 'posted=True|posted standing-watch' || echo "none_posted_yet_OK"

echo "=== VERIFIER ==="
cd "$ROOT/tools"
/opt/engel/.venv/bin/python verify_engel_discord_smart_standing_watch.py
/opt/engel/.venv/bin/python verify_engel_discord_owner_quiet_proactive.py || true

echo "=== DISTINCT MODEL SET ==="
/opt/engel/.venv/bin/python - << 'PY'
import os, sys
sys.path.insert(0, "/opt/engel/tools")
# Simulate each desk env
models = {}
from pathlib import Path
import re
for d in ["research","product","community","support","sales","ops"]:
    conf = Path(f"/etc/systemd/system/engel-discord-desk-{d}.service.d/30-nvidia-nim.conf").read_text()
    m = re.search(r"ENGEL_NVIDIA_CHAT_MODEL=(\S+)", conf)
    models[d] = m.group(1) if m else ""
print(models)
assert len(set(models.values())) == 6, models
print("DISTINCT_SLM_OK")
# Cooldown should still block force spam after last ~01:58 posts with 21600s interval
from engel_discord_desk_proactive import should_post, proactive_interval
from pathlib import Path
os.environ["ENGEL_DISCORD_PROACTIVE"] = "1"
os.environ["ENGEL_DISCORD_PROACTIVE_INTERVAL_SECONDS"] = "21600"
for d in models:
    ok, status = should_post(
        desk_name=d,
        run_dir=Path(f"/opt/engel/desks/{d}/run/discord_bridge"),
        channel_id="1",
        token="x",
        force=False,
    )
    print(d, "should_post", ok, status)
    assert ok is False, (d, status)
print("NO_IMMEDIATE_SPAM_COOLDOWN_OK interval=", proactive_interval())
PY
