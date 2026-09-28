param(
    [string]$CtHost = "192.0.2.50",
    [int]$CtPort = 24622,
    [string]$RemoteUser = "root",
    [switch]$SkipRemoteVerify
)

$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$Stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$StageRoot = Join-Path $ProjectRoot ("runtime\temp\engel_ct_cluster_record_sync_" + $Stamp)
$RemoteStage = "/tmp/engel_cluster_record_sync_$Stamp"
$LocalReceiptDir = Join-Path $ProjectRoot "reports\ct_sync"
$LocalReceiptPath = Join-Path $LocalReceiptDir ("ENGEL_CLUSTER_RECORD_SYNC_" + $Stamp + ".json")

function New-DirectoryIfMissing {
    param([string]$PathText)
    if (-not (Test-Path -LiteralPath $PathText -PathType Container)) {
        New-Item -ItemType Directory -Path $PathText -Force | Out-Null
    }
}

function Copy-StageFile {
    param(
        [string]$RelativePath,
        [string]$StageSubdir
    )
    $source = Join-Path $ProjectRoot $RelativePath
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
        throw "Required source file missing: $RelativePath"
    }
    $destDir = Join-Path $StageRoot $StageSubdir
    New-DirectoryIfMissing $destDir
    Copy-Item -LiteralPath $source -Destination $destDir -Force
}

if ($CtHost -notmatch "^[A-Za-z0-9_.-]+$") {
    throw "CtHost contains unsupported characters: $CtHost"
}
if ($RemoteUser -notmatch "^[A-Za-z_][A-Za-z0-9_-]*$") {
    throw "RemoteUser contains unsupported characters: $RemoteUser"
}
if ($CtPort -lt 1 -or $CtPort -gt 65535) {
    throw "CtPort must be a TCP port from 1 to 65535."
}

$sshOk = Test-NetConnection -ComputerName $CtHost -Port $CtPort -InformationLevel Quiet -WarningAction SilentlyContinue
if (-not $sshOk) {
    throw "Engel AI Main CT SSH route is not reachable: ${CtHost}:${CtPort}"
}

New-DirectoryIfMissing $StageRoot
New-DirectoryIfMissing (Join-Path $StageRoot "memory")
New-DirectoryIfMissing (Join-Path $StageRoot "reports\codex_bridge")
New-DirectoryIfMissing (Join-Path $StageRoot "tools")
New-DirectoryIfMissing (Join-Path $StageRoot "core")

Copy-StageFile "memory\ENGEL_STORAGE_LOCATION_REGISTRY_V1.json" "memory"
Copy-StageFile "memory\ENGEL_STORAGE_LOCATION_REGISTRY_V1.md" "memory"
Copy-StageFile "memory\ENGEL_MAIN_SERVER_MERGE_V1.json" "memory"
Copy-StageFile "memory\ENGEL_MAIN_SERVER_MERGE_V1.md" "memory"
Copy-StageFile "memory\ENGEL_AI_MAIN_CLUSTER_BUILD_STATE_V1.json" "memory"
Copy-StageFile "memory\ENGEL_AI_MAIN_CLUSTER_BUILD_STATE_V1.md" "memory"
Copy-StageFile "memory\ENGEL_MAIN_TRUSTED_VAULT_STORAGE_V1.json" "memory"
Copy-StageFile "memory\ENGEL_VAULT_OFFLINE_INTENTIONAL_SSD_ONLY_20260630.json" "memory"
Copy-StageFile "memory\ENGEL_SYSTEM_TOPOLOGY_REGISTRY_V1.json" "memory"
Copy-StageFile "memory\ENGEL_SELF_UPGRADE_VERIFIER_MATRIX_V1.json" "memory"
Copy-StageFile "memory\ENGEL_SELF_UPGRADE_SYSTEM_CONTRACT_V1.md" "memory"
Copy-StageFile "reports\codex_bridge\ENGEL_MAIN_SERVER_MERGE_20260628.md" "reports\codex_bridge"
Copy-StageFile "reports\codex_bridge\ENGEL_AI_MAIN_CLUSTER_BUILD_STATE_20260628.md" "reports\codex_bridge"
Copy-StageFile "tools\verify_engel_storage_location_registry.py" "tools"
Copy-StageFile "tools\verify_engel_main_server_merge.py" "tools"
Copy-StageFile "tools\verify_engel_ai_main_cluster_build_state.py" "tools"
Copy-StageFile "tools\engel_main_server_chat_http_service.py" "tools"
Copy-StageFile "tools\engel_local_model_service.py" "tools"
Copy-StageFile "tools\engel_meeting_room_lan_server.py" "tools"
Copy-StageFile "tools\run_engel_standalone_chat_llm.py" "tools"

Copy-StageFile "engel_large_chat_llm.py" "core"
Copy-StageFile "engel_agent_meeting_room.py" "core"
Copy-StageFile "engel_project_paths.py" "core"
Copy-StageFile "engel_temp_policy.py" "core"
Copy-StageFile "engel_android_worker_prompt_signals.py" "core"
Copy-StageFile "engel_prompt_bridge_selection.py" "core"
Copy-StageFile "engel_main_server_merge.py" "core"

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

mkdir -p /opt/engel/memory
mkdir -p /opt/engel/reports/codex_bridge
mkdir -p /opt/engel/tools
mkdir -p /opt/engel/core
mkdir -p /opt/engel/run/receipts

cp -f "$STAGE"/memory/* /opt/engel/memory/
cp -f "$STAGE"/tools/* /opt/engel/tools/
cp -f "$STAGE"/core/* /opt/engel/core/
cp -f "$STAGE"/core/engel_large_chat_llm.py /opt/engel/engel_large_chat_llm.py
cp -f "$STAGE"/core/engel_agent_meeting_room.py /opt/engel/engel_agent_meeting_room.py
cp -f "$STAGE"/core/engel_project_paths.py /opt/engel/engel_project_paths.py
cp -f "$STAGE"/core/engel_temp_policy.py /opt/engel/engel_temp_policy.py
cp -f "$STAGE"/core/engel_android_worker_prompt_signals.py /opt/engel/engel_android_worker_prompt_signals.py
cp -f "$STAGE"/core/engel_prompt_bridge_selection.py /opt/engel/engel_prompt_bridge_selection.py
cp -f "$STAGE"/core/engel_main_server_merge.py /opt/engel/engel_main_server_merge.py

chmod 0644 /opt/engel/memory/ENGEL_STORAGE_LOCATION_REGISTRY_V1.*
chmod 0644 /opt/engel/memory/ENGEL_SYSTEM_TOPOLOGY_REGISTRY_V1.json
chmod 0644 /opt/engel/memory/ENGEL_SELF_UPGRADE_VERIFIER_MATRIX_V1.json
chmod 0644 /opt/engel/memory/ENGEL_SELF_UPGRADE_SYSTEM_CONTRACT_V1.md
chmod 0644 /opt/engel/tools/engel_main_server_chat_http_service.py
chmod 0644 /opt/engel/tools/engel_local_model_service.py
chmod 0644 /opt/engel/tools/engel_meeting_room_lan_server.py
chmod 0644 /opt/engel/tools/run_engel_standalone_chat_llm.py
chmod 0644 /opt/engel/engel_large_chat_llm.py
chmod 0644 /opt/engel/core/engel_large_chat_llm.py
chmod 0644 /opt/engel/engel_agent_meeting_room.py
chmod 0644 /opt/engel/core/engel_agent_meeting_room.py
chmod 0644 /opt/engel/engel_project_paths.py
chmod 0644 /opt/engel/core/engel_project_paths.py
chmod 0644 /opt/engel/engel_temp_policy.py
chmod 0644 /opt/engel/core/engel_temp_policy.py
chmod 0644 /opt/engel/engel_android_worker_prompt_signals.py
chmod 0644 /opt/engel/core/engel_android_worker_prompt_signals.py
chmod 0644 /opt/engel/engel_prompt_bridge_selection.py
chmod 0644 /opt/engel/core/engel_prompt_bridge_selection.py
chmod 0644 /opt/engel/engel_main_server_merge.py
chmod 0644 /opt/engel/core/engel_main_server_merge.py

PYTHON="/opt/engel/.venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  PYTHON="python3"
fi

"$PYTHON" -m json.tool /opt/engel/memory/ENGEL_STORAGE_LOCATION_REGISTRY_V1.json >/dev/null
"$PYTHON" -m json.tool /opt/engel/memory/ENGEL_SYSTEM_TOPOLOGY_REGISTRY_V1.json >/dev/null
"$PYTHON" -m json.tool /opt/engel/memory/ENGEL_SELF_UPGRADE_VERIFIER_MATRIX_V1.json >/dev/null

if [[ "__SKIP_REMOTE_VERIFY__" != "1" ]]; then
  "$PYTHON" /opt/engel/tools/verify_engel_storage_location_registry.py
fi

cat >"/opt/engel/run/receipts/ENGEL_CLUSTER_RECORD_SYNC_${STAMP}.json" <<JSON
{
  "schema": "engel_cluster_record_sync_receipt_v1",
  "created_at_utc": "${STAMP}",
  "target": "engel-ai-main CT 246",
  "runtime_root": "/opt/engel",
  "memory_updated": true,
  "reports_updated": true,
  "tools_updated": true,
  "storage_mutation_performed": false,
  "pct_set_performed": false,
  "mount_created": false,
  "backup_setting_changed": false
}
JSON

echo "ENGEL_CLUSTER_RECORDS_SYNCED_TO_CT_246"
echo "Memory: /opt/engel/memory"
echo "Reports: /opt/engel/reports/codex_bridge"
echo "Receipt: /opt/engel/run/receipts/ENGEL_CLUSTER_RECORD_SYNC_${STAMP}.json"
'@

$skipRemoteVerifyValue = if ($SkipRemoteVerify) { "1" } else { "0" }
$remoteShell = $remoteShellTemplate.Replace("__REMOTE_STAGE__", $RemoteStage).Replace("__STAMP__", $Stamp).Replace("__SKIP_REMOTE_VERIFY__", $skipRemoteVerifyValue)
$remoteScriptPath = Join-Path $StageRoot "sync_to_ct.sh"
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($remoteScriptPath, $remoteShell, $utf8NoBom)

Write-Host "Copying cluster records to ${RemoteUser}@${CtHost}:${RemoteStage}"
& scp -P $CtPort -r $StageRoot "${RemoteUser}@${CtHost}:${RemoteStage}"
if ($LASTEXITCODE -ne 0) {
    throw "scp failed. No remote records were activated."
}

Write-Host "Activating records under /opt/engel on Engel AI Main CT 246."
& ssh -p $CtPort "${RemoteUser}@${CtHost}" "bash '$RemoteStage/sync_to_ct.sh'"
if ($LASTEXITCODE -ne 0) {
    throw "remote activation failed."
}

New-DirectoryIfMissing $LocalReceiptDir
$receipt = [ordered]@{
    schema = "engel_cluster_record_sync_local_receipt_v1"
    created_at_utc = (Get-Date).ToUniversalTime().ToString("o")
    target = "engel-ai-main CT 246"
    ct_host = $CtHost
    ct_port = $CtPort
    remote_user = $RemoteUser
    remote_stage = $RemoteStage
    local_stage = $StageRoot
    copied_to_opt_engel = $true
    storage_mutation_performed = $false
    pct_set_performed = $false
    mount_created = $false
    backup_setting_changed = $false
}
$receipt | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $LocalReceiptPath -Encoding UTF8

Write-Host "Local receipt: $LocalReceiptPath"
