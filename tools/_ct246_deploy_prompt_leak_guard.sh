#!/bin/bash
set -euo pipefail
ROOT=/opt/engel
TS="$(date -u +%Y%m%dT%H%M%SZ)"
BK="$ROOT/backups/discord_prompt_leak_${TS}"
mkdir -p "$BK"
cp -a "$ROOT/tools/engel_discord_bridge.py" "$BK/" || true
cp -a "$ROOT/tools/engel_persona_guard.py" "$BK/" || true
cp -a /tmp/engel_discord_bridge.py "$ROOT/tools/engel_discord_bridge.py"
cp -a /tmp/engel_persona_guard.py "$ROOT/tools/engel_persona_guard.py"
cp -a /tmp/verify_engel_discord_prompt_leak_guard.py "$ROOT/tools/"
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
echo "=== NEEDLES ==="
grep -n 'finalize_discord_public_reply\|discord_reply_looks_like_prompt_leak\|We are in a Discord\|DISCORD_LEAK_FALLBACK' \
  "$ROOT/tools/engel_discord_bridge.py" | head -30
echo "=== VERIFIER ==="
cd "$ROOT/tools"
/opt/engel/.venv/bin/python verify_engel_discord_prompt_leak_guard.py
echo "=== ONLINE ==="
journalctl -u engel-discord-bridge.service -u engel-discord-desk-sales.service --since "1 minute ago" --no-pager | grep -iE 'online as|ERROR|prompt-leak' | tail -20 || true
