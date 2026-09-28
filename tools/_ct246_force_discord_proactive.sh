#!/bin/bash
set -euo pipefail

# Force one standing-watch post per desk using systemd Environment + EnvironmentFile.
# Does not print secrets.

desks=(research product community support sales ops)

for d in "${desks[@]}"; do
  unit="engel-discord-desk-${d}.service"
  echo "=== ${d} ==="

  # Export Environment= lines from the unit (CHANNEL_ID, PROACTIVE, etc.)
  while IFS= read -r part; do
    [ -z "$part" ] && continue
    case "$part" in
      *=*) export "$part" ;;
    esac
  done < <(systemctl show "$unit" -p Environment --value | xargs -n1 printf '%s\n')

  # Source EnvironmentFiles without echoing values
  while IFS= read -r line; do
    # systemctl EnvironmentFiles format: /path (ignore_errors)
    f="${line%% *}"
    f="${f#(}"
    f="${f%)}"
    if [ -f "$f" ]; then
      set -a
      # shellcheck disable=SC1090
      . "$f"
      set +a
    fi
  done < <(systemctl show "$unit" -p EnvironmentFiles --value | tr ' ' '\n' | sed '/^$/d')

  export ENGEL_ROOT="/opt/engel/desks/${d}"
  export ENGEL_DISCORD_DESK_NAME="$d"
  export ENGEL_DISCORD_PROACTIVE="${ENGEL_DISCORD_PROACTIVE:-1}"

  echo "CHANNEL_ID=${ENGEL_DISCORD_CHANNEL_ID:-MISSING}"
  echo "TOKEN_SET=$([ -n "${ENGEL_DISCORD_BOT_TOKEN:-${DISCORD_BOT_TOKEN:-}}" ] && echo yes || echo no)"

  /opt/engel/.venv/bin/python /opt/engel/tools/engel_discord_bridge.py --post-proactive-now || true
done

echo "=== recent research journal ==="
journalctl -u engel-discord-desk-research.service -n 30 --no-pager | grep -E "PROACTIVE|proactive|posted|forum|ERROR|online" || true
