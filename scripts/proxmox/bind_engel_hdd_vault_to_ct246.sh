#!/usr/bin/env bash
set -euo pipefail

APPROVAL=""
CTID="246"
HOST_SOURCE="/engel-hdd-vault"
CONTAINER_MOUNT="/mnt/engel-hdd-vault"
MOUNT_INDEX="1"
ALLOW_CT_RESTART="0"

usage() {
  cat <<'EOF'
Usage:
  bind_engel_hdd_vault_to_ct246.sh --approve BIND_ENGEL_HDD_VAULT_TO_CT246 [options]

Options:
  --ctid 246                         Engel AI Main CT ID. Only 246 is allowed.
  --host-source /engel-hdd-vault      Host-mounted Dell PowerEdge HDD/ZFS path.
  --container-mount /mnt/engel-hdd-vault
  --mount-index 1                     Proxmox mp index to use.
  --allow-ct-restart                  Restart CT 246 so the bind mount becomes visible.

Hard refusals:
  - CT 245
  - /mnt/engel-vault
  - engel-vault-main
  - PowerVault / iSCSI / /dev/sdc
  - disk creation, formatting, pvcreate, vgcreate, lvcreate
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --approve)
      APPROVAL="${2:-}"
      shift 2
      ;;
    --ctid)
      CTID="${2:-}"
      shift 2
      ;;
    --host-source)
      HOST_SOURCE="${2:-}"
      shift 2
      ;;
    --container-mount)
      CONTAINER_MOUNT="${2:-}"
      shift 2
      ;;
    --mount-index)
      MOUNT_INDEX="${2:-}"
      shift 2
      ;;
    --allow-ct-restart)
      ALLOW_CT_RESTART="1"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ "$APPROVAL" != "BIND_ENGEL_HDD_VAULT_TO_CT246" ]]; then
  echo "Missing approval token BIND_ENGEL_HDD_VAULT_TO_CT246." >&2
  exit 2
fi
if [[ "$CTID" != "246" ]]; then
  echo "Refusing CT $CTID. Engel AI Main HDD vault bind target is CT 246 only." >&2
  exit 3
fi
if [[ "$HOST_SOURCE" =~ engel-vault-main|PowerVault|powervault|/mnt/engel-vault|/dev/sdc|iscsi ]]; then
  echo "Refusing PowerVault/iSCSI/offline vault host source: $HOST_SOURCE" >&2
  exit 4
fi
if [[ "$CONTAINER_MOUNT" != "/mnt/engel-hdd-vault" ]]; then
  echo "Refusing container mount $CONTAINER_MOUNT. Use /mnt/engel-hdd-vault." >&2
  exit 5
fi
if [[ "$CONTAINER_MOUNT" == "/mnt/engel-vault" ]]; then
  echo "Refusing offline PowerVault mountpoint /mnt/engel-vault." >&2
  exit 6
fi
if ! [[ "$MOUNT_INDEX" =~ ^[0-9]+$ ]]; then
  echo "Mount index must be numeric." >&2
  exit 7
fi

for cmd in pct findmnt df; do
  command -v "$cmd" >/dev/null 2>&1 || {
    echo "Missing required command on Proxmox host: $cmd" >&2
    exit 8
  }
done

pct status "$CTID" >/dev/null

if [[ ! -d "$HOST_SOURCE" ]]; then
  echo "Host source does not exist: $HOST_SOURCE" >&2
  echo "Create or mount the Dell PowerEdge engel-hdd-vault ZFS dataset on the host first." >&2
  exit 9
fi

HOST_FINDMNT="$(findmnt -T "$HOST_SOURCE" -o TARGET,SOURCE,FSTYPE -n || true)"
if [[ -z "$HOST_FINDMNT" ]]; then
  echo "Host source is not on a mounted filesystem: $HOST_SOURCE" >&2
  exit 10
fi
if echo "$HOST_FINDMNT" | grep -Eiq 'iscsi|engel-vault-main|power|/dev/sdc'; then
  echo "Refusing host source because findmnt looks like PowerVault/iSCSI: $HOST_FINDMNT" >&2
  exit 11
fi

mkdir -p "$HOST_SOURCE"/{models-archive,datasets-archive,training-outputs,logs,snapshots,iso,old-models}

CURRENT_CONFIG="$(pct config "$CTID")"
if echo "$CURRENT_CONFIG" | grep -E "mp${MOUNT_INDEX}: " >/dev/null; then
  if echo "$CURRENT_CONFIG" | grep -F "mp${MOUNT_INDEX}: ${HOST_SOURCE},mp=${CONTAINER_MOUNT}" >/dev/null; then
    echo "Mount mp${MOUNT_INDEX} is already configured for $HOST_SOURCE -> $CONTAINER_MOUNT."
  else
    echo "Refusing to overwrite existing mp${MOUNT_INDEX}:" >&2
    echo "$CURRENT_CONFIG" | grep -E "mp${MOUNT_INDEX}: " >&2
    exit 12
  fi
else
  pct set "$CTID" "-mp${MOUNT_INDEX}" "${HOST_SOURCE},mp=${CONTAINER_MOUNT},backup=0"
fi

if [[ "$ALLOW_CT_RESTART" == "1" ]]; then
  status="$(pct status "$CTID" | awk '{print $2}')"
  if [[ "$status" == "running" ]]; then
    pct shutdown "$CTID" --timeout 60 || pct stop "$CTID"
    pct start "$CTID"
  fi
  pct exec "$CTID" -- findmnt -T "$CONTAINER_MOUNT"
  pct exec "$CTID" -- df -hT "$CONTAINER_MOUNT"
  pct exec "$CTID" -- test -d "$CONTAINER_MOUNT/models-archive"
else
  echo "Configured Proxmox bind mount. Restart CT 246 later for it to appear inside the container."
  echo "To apply now, rerun with --allow-ct-restart."
fi

cat <<EOF
ENGEL_HDD_VAULT_BIND_READY
ctid=$CTID
host_source=$HOST_SOURCE
container_mount=$CONTAINER_MOUNT
mount_index=mp$MOUNT_INDEX
backup=0
powervault_used=false
ct245_used=false
EOF
