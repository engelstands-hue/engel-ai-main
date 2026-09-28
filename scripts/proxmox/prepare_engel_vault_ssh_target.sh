#!/usr/bin/env bash
set -euo pipefail

VMID="245"
REMOTE_ROOT=""

usage() {
  cat <<'USAGE'
Prepare the already-created Engel vault LXC mount for SSH/SCP transfer.

This script must run on the Proxmox host as root.

Safety properties:
  - Uses the existing CT and existing /srv/engel-vault mount.
  - Does not install packages.
  - Does not create, delete, format, or resize Proxmox storage.
  - Does not move VMs.
  - Does not touch iSCSI or multipath.
  - Creates only the expected Engel APP MEMORY directories.

Options:
  --vmid ID                 Existing LXC VMID, default 245
  --remote-root PATH        Host-visible target root. Default:
                            /var/lib/lxc/<vmid>/rootfs/srv/engel-vault/ENGEL_APP_MEMORY
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --vmid) VMID="${2:-}"; shift 2 ;;
    --remote-root) REMOTE_ROOT="${2:-}"; shift 2 ;;
    --help|-h) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ "$(id -u)" != "0" ]]; then
  echo "Run as root on the Proxmox host." >&2
  exit 2
fi

for command_name in pct findmnt awk grep readlink; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "Missing required command on Proxmox host: $command_name" >&2
    exit 2
  fi
done

if [[ ! "$VMID" =~ ^[0-9]+$ ]]; then
  echo "VMID must be numeric: $VMID" >&2
  exit 2
fi

ROOTFS="/var/lib/lxc/${VMID}/rootfs"
VAULT_MOUNT="${ROOTFS}/srv/engel-vault"
DEFAULT_ROOT="${VAULT_MOUNT}/ENGEL_APP_MEMORY"
TARGET_ROOT="${REMOTE_ROOT:-$DEFAULT_ROOT}"

if [[ "$TARGET_ROOT" != /* || "$TARGET_ROOT" == *".."* ]]; then
  echo "Remote root must be an absolute path without '..': $TARGET_ROOT" >&2
  exit 2
fi

case "$TARGET_ROOT/" in
  "$VAULT_MOUNT"/*) ;;
  *)
    echo "Remote root must stay inside the CT vault mount: $VAULT_MOUNT" >&2
    echo "Requested remote root: $TARGET_ROOT" >&2
    exit 2
    ;;
esac

if ! pct status "$VMID" >/dev/null 2>&1; then
  echo "Container VMID $VMID does not exist." >&2
  exit 3
fi

if ! pct config "$VMID" | grep -q "mp=/srv/engel-vault"; then
  echo "Container VMID $VMID does not have the expected /srv/engel-vault mountpoint." >&2
  pct config "$VMID" >&2
  exit 3
fi

status="$(pct status "$VMID" | awk '{print $2}')"
if [[ "$status" != "running" ]]; then
  pct start "$VMID"
  sleep 10
fi

if [[ ! -d "$ROOTFS" ]]; then
  echo "Container rootfs is not visible on the Proxmox host: $ROOTFS" >&2
  exit 3
fi

if [[ ! -d "$VAULT_MOUNT" ]]; then
  echo "Vault mount path is not visible on the Proxmox host: $VAULT_MOUNT" >&2
  exit 3
fi

mount_target="$(findmnt -T "$VAULT_MOUNT" -no TARGET | head -n 1 || true)"
mount_source="$(findmnt -T "$VAULT_MOUNT" -no SOURCE | head -n 1 || true)"
mount_fstype="$(findmnt -T "$VAULT_MOUNT" -no FSTYPE | head -n 1 || true)"

if [[ "$mount_target" != "$VAULT_MOUNT" ]]; then
  echo "Refusing to use $VAULT_MOUNT because it is not a dedicated mounted vault target." >&2
  echo "findmnt target: ${mount_target:-<none>}" >&2
  findmnt -T "$VAULT_MOUNT" >&2 || true
  exit 3
fi

mkdir -p "$TARGET_ROOT/sources/E/ENGEL_APP_MEMORY"
mkdir -p "$TARGET_ROOT/sources/F/ENGEL_APP_MEMORY"
mkdir -p "$TARGET_ROOT/sources/G/ENGEL_APP_MEMORY"
mkdir -p "$TARGET_ROOT/receipts"

resolved_mount="$(readlink -f "$VAULT_MOUNT")"
resolved_target="$(readlink -f "$TARGET_ROOT")"

case "$resolved_target/" in
  "$resolved_mount"/*) ;;
  *)
    echo "Resolved target escaped the vault mount." >&2
    echo "Resolved mount: $resolved_mount" >&2
    echo "Resolved target: $resolved_target" >&2
    exit 3
    ;;
esac

cat <<RESULT

ENGEL_VAULT_SSH_TARGET_READY
Container VMID: $VMID
Host-visible target root: $TARGET_ROOT
Mount target: $mount_target
Mount source: $mount_source
Mount type: $mount_fstype

Windows next step:
  .\\scripts\\Start-EngelVaultSshCopy.ps1 -Run

Keep E/F/G connected until the copy and verification complete.
RESULT
