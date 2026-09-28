param(
    [string]$CtHost = "192.0.2.50",
    [int]$CtPort = 24622,
    [string]$CtUser = "root",
    [string]$KeyPath = (Join-Path $env:USERPROFILE ".ssh\engel_ai_main_ct246_ed25519"),
    [switch]$SkipRemoteVerify
)

$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$ResolvedKeyPath = [System.IO.Path]::GetFullPath($KeyPath)
$Stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$StageRoot = Join-Path $ProjectRoot ("runtime\temp\engel_phone_bridge_sync_" + $Stamp)
$RemoteStage = "/tmp/engel_phone_bridge_sync_$Stamp"
$ReceiptDir = Join-Path $ProjectRoot "reports\ct_sync"
$ReceiptPath = Join-Path $ReceiptDir ("ENGEL_PHONE_BRIDGE_STATE_SYNC_" + $Stamp + ".json")

function New-DirectoryIfMissing {
    param([string]$PathText)
    if (-not (Test-Path -LiteralPath $PathText -PathType Container)) {
        New-Item -ItemType Directory -Path $PathText -Force | Out-Null
    }
}

function Copy-StageFile {
    param(
        [string]$RelativePath,
        [string]$StageSubdir,
        [switch]$Optional
    )
    $source = Join-Path $ProjectRoot $RelativePath
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
        if ($Optional) { return $false }
        throw "Required source file missing: $RelativePath"
    }
    $destDir = Join-Path $StageRoot $StageSubdir
    New-DirectoryIfMissing $destDir
    Copy-Item -LiteralPath $source -Destination $destDir -Force
    return $true
}

if ($CtHost -notmatch "^[A-Za-z0-9_.-]+$") {
    throw "CtHost contains unsupported characters: $CtHost"
}
if ($CtUser -notmatch "^[A-Za-z_][A-Za-z0-9_-]*$") {
    throw "CtUser contains unsupported characters: $CtUser"
}
if ($CtPort -lt 1 -or $CtPort -gt 65535) {
    throw "CtPort must be a TCP port from 1 to 65535."
}
if (-not (Test-Path -LiteralPath $ResolvedKeyPath -PathType Leaf)) {
    throw "Engel CT SSH key is missing: $ResolvedKeyPath"
}

$sshOk = Test-NetConnection -ComputerName $CtHost -Port $CtPort -InformationLevel Quiet -WarningAction SilentlyContinue
if (-not $sshOk) {
    throw "Engel AI Main CT SSH route is not reachable: ${CtHost}:${CtPort}"
}

New-DirectoryIfMissing $StageRoot
New-DirectoryIfMissing $ReceiptDir

$copied = [ordered]@{
    paired_state = Copy-StageFile "memory\phone_bridge\ENGEL_REMOTE_WORKERS_PAIRED.json" "memory\phone_bridge" -Optional
    lan_session_state = Copy-StageFile "remote_workers\lan_link_manager\session_state.json" "remote_workers\lan_link_manager" -Optional
    dedicated_pairing_code = Copy-StageFile "remote_workers\lan_pairing\dedicated_pairing_code.json" "remote_workers\lan_pairing" -Optional
    pairing_session = Copy-StageFile "remote_workers\lan_pairing\pairing_session.json" "remote_workers\lan_pairing" -Optional
    live_phone_verifier = Copy-StageFile "tools\verify_engel_live_phone_connection.py" "tools" -Optional
}

if (-not ($copied.paired_state -or $copied.lan_session_state)) {
    throw "No local Engel phone bridge state files were available to sync."
}

$remoteShellTemplate = @'
#!/usr/bin/env bash
set -euo pipefail

STAGE="__REMOTE_STAGE__"
STAMP="__STAMP__"

if [[ ! -d "$STAGE" ]]; then
  echo "Missing remote staging directory: $STAGE" >&2
  exit 2
fi
if [[ ! -d /opt/engel ]]; then
  echo "Missing Engel runtime root: /opt/engel" >&2
  exit 2
fi

mkdir -p /opt/engel/memory/phone_bridge
mkdir -p /opt/engel/remote_workers/lan_link_manager
mkdir -p /opt/engel/remote_workers/lan_pairing
mkdir -p /opt/engel/tools
mkdir -p /opt/engel/run/receipts

if [[ -d "$STAGE/memory/phone_bridge" ]]; then
  cp -f "$STAGE"/memory/phone_bridge/* /opt/engel/memory/phone_bridge/
fi
if [[ -d "$STAGE/remote_workers/lan_link_manager" ]]; then
  cp -f "$STAGE"/remote_workers/lan_link_manager/* /opt/engel/remote_workers/lan_link_manager/
fi
if [[ -d "$STAGE/remote_workers/lan_pairing" ]]; then
  cp -f "$STAGE"/remote_workers/lan_pairing/* /opt/engel/remote_workers/lan_pairing/
fi
if [[ -d "$STAGE/tools" ]]; then
  cp -f "$STAGE"/tools/* /opt/engel/tools/
fi

PYTHON="/opt/engel/.venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  PYTHON="python3"
fi

if [[ -f /opt/engel/memory/phone_bridge/ENGEL_REMOTE_WORKERS_PAIRED.json ]]; then
  "$PYTHON" -m json.tool /opt/engel/memory/phone_bridge/ENGEL_REMOTE_WORKERS_PAIRED.json >/dev/null
fi
if [[ -f /opt/engel/remote_workers/lan_link_manager/session_state.json ]]; then
  "$PYTHON" -m json.tool /opt/engel/remote_workers/lan_link_manager/session_state.json >/dev/null
fi
if [[ -f /opt/engel/remote_workers/lan_pairing/dedicated_pairing_code.json ]]; then
  "$PYTHON" -m json.tool /opt/engel/remote_workers/lan_pairing/dedicated_pairing_code.json >/dev/null
fi
if [[ -f /opt/engel/remote_workers/lan_pairing/pairing_session.json ]]; then
  "$PYTHON" -m json.tool /opt/engel/remote_workers/lan_pairing/pairing_session.json >/dev/null
fi

if [[ "__SKIP_REMOTE_VERIFY__" != "1" && -f /opt/engel/tools/verify_engel_live_phone_connection.py ]]; then
  "$PYTHON" /opt/engel/tools/verify_engel_live_phone_connection.py >/tmp/engel_live_phone_connection_sync_verify.json || true
fi

cat >"/opt/engel/run/receipts/ENGEL_PHONE_BRIDGE_STATE_SYNC_${STAMP}.json" <<JSON
{
  "schema": "engel_phone_bridge_state_sync_receipt_v1",
  "created_at_utc": "${STAMP}",
  "target": "engel-ai-main CT 246",
  "runtime_root": "/opt/engel",
  "phone_bridge_state_synced": true,
  "storage_mutation_performed": false,
  "pct_set_performed": false,
  "disk_format_performed": false,
  "background_worker_created": false
}
JSON

echo "ENGEL_PHONE_BRIDGE_STATE_SYNCED_TO_CT_246"
echo "Phone bridge: /opt/engel/memory/phone_bridge/ENGEL_REMOTE_WORKERS_PAIRED.json"
echo "LAN session: /opt/engel/remote_workers/lan_link_manager/session_state.json"
echo "Receipt: /opt/engel/run/receipts/ENGEL_PHONE_BRIDGE_STATE_SYNC_${STAMP}.json"
'@

$skipRemoteVerifyValue = if ($SkipRemoteVerify) { "1" } else { "0" }
$remoteShell = $remoteShellTemplate.Replace("__REMOTE_STAGE__", $RemoteStage).Replace("__STAMP__", $Stamp).Replace("__SKIP_REMOTE_VERIFY__", $skipRemoteVerifyValue)
$remoteScriptPath = Join-Path $StageRoot "sync_phone_bridge_to_ct.sh"
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($remoteScriptPath, $remoteShell, $utf8NoBom)

Write-Host "Copying Engel phone bridge state to ${CtUser}@${CtHost}:${RemoteStage}"
& scp -i $ResolvedKeyPath -P $CtPort -r $StageRoot "${CtUser}@${CtHost}:${RemoteStage}"
if ($LASTEXITCODE -ne 0) {
    throw "scp failed. No remote phone bridge state was activated."
}

Write-Host "Activating phone bridge state under /opt/engel on Engel AI Main CT 246."
& ssh -i $ResolvedKeyPath -p $CtPort -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=accept-new "${CtUser}@${CtHost}" "bash '$RemoteStage/sync_phone_bridge_to_ct.sh'"
if ($LASTEXITCODE -ne 0) {
    throw "remote phone bridge activation failed."
}

$receipt = [ordered]@{
    schema = "engel_phone_bridge_state_sync_local_receipt_v1"
    created_at_utc = (Get-Date).ToUniversalTime().ToString("o")
    target = "engel-ai-main CT 246"
    ct_host = $CtHost
    ct_port = $CtPort
    ct_user = $CtUser
    remote_stage = $RemoteStage
    local_stage = $StageRoot
    copied = $copied
    copied_to_opt_engel = $true
    storage_mutation_performed = $false
    pct_set_performed = $false
    disk_format_performed = $false
    background_worker_created = $false
}
$receipt | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $ReceiptPath -Encoding UTF8

Write-Host "Local receipt: $ReceiptPath"
