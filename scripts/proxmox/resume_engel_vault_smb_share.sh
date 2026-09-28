#!/usr/bin/env bash
set -euo pipefail

VMID="245"
SMB_USER="engel"
SMB_PASSWORD=""

usage() {
  cat <<'USAGE'
Resume Engel vault SMB share setup for an already-created Proxmox LXC.

This is for the case where the LXC and vault disk were created, but apt failed
while installing Samba inside the container.

Options:
  --vmid ID                Existing LXC VMID, default 245
  --smb-user NAME          Samba user, default engel
  --smb-password VALUE     Samba password; if omitted, generated and printed once
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --vmid) VMID="${2:-}"; shift 2 ;;
    --smb-user) SMB_USER="${2:-}"; shift 2 ;;
    --smb-password) SMB_PASSWORD="${2:-}"; shift 2 ;;
    --help|-h) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ "$(id -u)" != "0" ]]; then
  echo "Run as root on the Proxmox host." >&2
  exit 2
fi

for command_name in pct openssl; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "Missing required command on Proxmox host: $command_name" >&2
    exit 2
  fi
done

if [[ ! "$SMB_USER" =~ ^[a-z_][a-z0-9_-]*$ ]]; then
  echo "SMB user must match ^[a-z_][a-z0-9_-]*$: $SMB_USER" >&2
  exit 2
fi

if [[ "$SMB_PASSWORD" == *"'"* || "$SMB_PASSWORD" == *$'\n'* || "$SMB_PASSWORD" == *$'\r'* ]]; then
  echo "SMB password cannot contain single quotes or newlines for this guarded script." >&2
  exit 2
fi

if ! pct status "$VMID" >/dev/null 2>&1; then
  echo "Container VMID $VMID does not exist." >&2
  exit 3
fi

if [[ -z "$SMB_PASSWORD" ]]; then
  SMB_PASSWORD="$(openssl rand -base64 24 | tr -d '\n')"
  GENERATED_PASSWORD="1"
else
  GENERATED_PASSWORD="0"
fi

status="$(pct status "$VMID" | awk '{print $2}')"
if [[ "$status" != "running" ]]; then
  pct start "$VMID"
  sleep 10
fi

echo "Configuring signed HTTP Debian repositories with broken-proxy apt settings inside CT $VMID..."
pct exec "$VMID" -- bash -lc "set -euo pipefail
cat >/etc/apt/sources.list <<'APTCONF'
deb http://deb.debian.org/debian bookworm main contrib non-free-firmware
deb http://deb.debian.org/debian bookworm-updates main contrib non-free-firmware
deb http://security.debian.org/debian-security bookworm-security main contrib non-free-firmware
APTCONF
cat >/etc/apt/apt.conf.d/99engel-broken-proxy <<'APTCONF'
Acquire::http::Pipeline-Depth \"0\";
Acquire::http::No-Cache \"true\";
Acquire::http::No-Store \"true\";
Acquire::Queue-Mode \"access\";
Acquire::BrokenProxy \"true\";
Acquire::Retries \"5\";
APTCONF
rm -f /etc/apt/sources.list.d/*.list /etc/apt/sources.list.d/*.sources 2>/dev/null || true
rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/partial/* 2>/dev/null || true
apt-get clean
"

echo "Installing Samba inside CT $VMID..."
pct exec "$VMID" -- bash -lc 'set -euo pipefail; dpkg --configure -a || true; apt-get update; DEBIAN_FRONTEND=noninteractive apt-get -f install -y || true; DEBIAN_FRONTEND=noninteractive apt-get --fix-missing install -y ca-certificates samba'

echo "Configuring Engel vault folders and Samba user..."
pct exec "$VMID" -- bash -lc "set -euo pipefail
mkdir -p /srv/engel-vault/ENGEL_APP_MEMORY/sources/E/ENGEL_APP_MEMORY
mkdir -p /srv/engel-vault/ENGEL_APP_MEMORY/sources/F/ENGEL_APP_MEMORY
mkdir -p /srv/engel-vault/ENGEL_APP_MEMORY/sources/G/ENGEL_APP_MEMORY
mkdir -p /srv/engel-vault/ENGEL_APP_MEMORY/receipts
id -u '$SMB_USER' >/dev/null 2>&1 || useradd --system --home /srv/engel-vault --shell /usr/sbin/nologin '$SMB_USER'
chown -R '$SMB_USER':'$SMB_USER' /srv/engel-vault/ENGEL_APP_MEMORY
chmod -R 0770 /srv/engel-vault/ENGEL_APP_MEMORY
"

pct exec "$VMID" -- bash -lc "set -euo pipefail
printf '%s\n%s\n' '$SMB_PASSWORD' '$SMB_PASSWORD' | smbpasswd -s -a '$SMB_USER'
smbpasswd -e '$SMB_USER'
"

pct exec "$VMID" -- bash -lc "set -euo pipefail
cp /etc/samba/smb.conf /etc/samba/smb.conf.engel-backup-\$(date -u +%Y%m%dT%H%M%SZ) 2>/dev/null || true
cat >/etc/samba/smb.conf <<SMBCONF
[global]
   server role = standalone server
   map to guest = never
   usershare allow guests = no
   disable netbios = yes
   smb ports = 445
   min protocol = SMB2
   server string = Engel Vault Share

[EngelVault]
   path = /srv/engel-vault/ENGEL_APP_MEMORY
   valid users = $SMB_USER
   read only = no
   browseable = yes
   create mask = 0660
   directory mask = 0770
   follow symlinks = no
   wide links = no
SMBCONF
systemctl enable --now smbd
systemctl restart smbd
"

CT_IP="$(pct exec "$VMID" -- hostname -I | awk '{print $1}')"
if [[ -z "$CT_IP" ]]; then
  CT_IP="<container-ip-not-detected>"
fi

cat <<RESULT

ENGEL_VAULT_SMB_SHARE_READY
Container VMID: $VMID
Container IP: $CT_IP
SMB share: \\\\$CT_IP\\EngelVault
SMB user: $SMB_USER
Password generated: $GENERATED_PASSWORD
SMB password: $SMB_PASSWORD

Windows next step:
  .\\scripts\\Connect-EngelVaultShare.ps1 -SharePath "\\\\$CT_IP\\EngelVault" -PersistEnvironment

Keep E/F/G connected until the copy and verification complete.
RESULT
