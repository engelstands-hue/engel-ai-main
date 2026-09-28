param(
    [string]$CtHost = "192.0.2.50",
    [int]$CtPort = 24622,
    [string]$CtUser = "root",
    [string]$RuntimeRoot = "/opt/engel",
    [int]$ChatServicePort = 8765,
    [int]$MeetingRoomPort = 8790,
    [string]$KeyPath = (Join-Path $env:USERPROFILE ".ssh\engel_ai_main_ct246_ed25519"),
    [string]$TaskName = "EngelMainServerPersistentLink",
    [switch]$NoScheduledTask,
    [switch]$NoStartNow
)

$ErrorActionPreference = "Stop"

function Assert-Port {
    param([int]$Port, [string]$Name)
    if ($Port -lt 1 -or $Port -gt 65535) {
        throw "$Name must be a TCP port from 1 to 65535."
    }
}

function New-DirectoryIfMissing {
    param([string]$PathText)
    if (-not (Test-Path -LiteralPath $PathText -PathType Container)) {
        New-Item -ItemType Directory -Path $PathText -Force | Out-Null
    }
}

function Quote-BashSingle {
    param([string]$Text)
    if ($Text.Contains("'")) {
        throw "Refusing to single-quote text containing an apostrophe."
    }
    return "'" + $Text + "'"
}

function Copy-StageFile {
    param(
        [string]$RelativePath,
        [string]$StageSubdir,
        [switch]$Optional
    )
    $source = Join-Path $ProjectRoot $RelativePath
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
        if ($Optional) { return }
        throw "Required source file missing: $RelativePath"
    }
    $destDir = Join-Path $StageRoot $StageSubdir
    New-DirectoryIfMissing $destDir
    Copy-Item -LiteralPath $source -Destination $destDir -Force
}

function Invoke-KeySsh {
    param([string[]]$Arguments)
    & ssh -i $ResolvedKeyPath -p $CtPort -o BatchMode=yes -o StrictHostKeyChecking=accept-new @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "ssh command failed with exit code $LASTEXITCODE"
    }
}

foreach ($item in @(
    @{ Port = $CtPort; Name = "CtPort" },
    @{ Port = $ChatServicePort; Name = "ChatServicePort" },
    @{ Port = $MeetingRoomPort; Name = "MeetingRoomPort" }
)) {
    Assert-Port -Port $item.Port -Name $item.Name
}

if ($CtHost -notmatch "^[A-Za-z0-9_.-]+$") {
    throw "CtHost contains unsupported characters: $CtHost"
}
if ($CtUser -notmatch "^[A-Za-z_][A-Za-z0-9_-]*$") {
    throw "CtUser contains unsupported characters: $CtUser"
}
if ($RuntimeRoot -notmatch "^/[A-Za-z0-9_./-]+$") {
    throw "RuntimeRoot must be an absolute Linux path with simple characters."
}

$ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$TunnelScript = Join-Path $PSScriptRoot "Start-EngelMainServerChatTunnelPersistent.ps1"
if (-not (Test-Path -LiteralPath $TunnelScript -PathType Leaf)) {
    throw "Persistent tunnel script missing: $TunnelScript"
}

$sshOk = Test-NetConnection -ComputerName $CtHost -Port $CtPort -InformationLevel Quiet -WarningAction SilentlyContinue
if (-not $sshOk) {
    throw "Engel AI Main CT SSH route is not reachable: ${CtHost}:${CtPort}"
}

$ResolvedKeyPath = [System.IO.Path]::GetFullPath($KeyPath)
$KeyDir = Split-Path -Parent $ResolvedKeyPath
New-DirectoryIfMissing $KeyDir
if (-not (Test-Path -LiteralPath $ResolvedKeyPath -PathType Leaf)) {
    Write-Host "Generating Engel CT SSH key: $ResolvedKeyPath"
    $keyComment = "engel-ai-main-rog-$($env:COMPUTERNAME)"
    $sshKeygenArgs = @(
        "-t", "ed25519",
        "-f", $ResolvedKeyPath,
        "-N", "",
        "-C", $keyComment
    )
    & ssh-keygen @sshKeygenArgs
    if ($LASTEXITCODE -ne 0) {
        throw "ssh-keygen failed."
    }
}
$PubKeyPath = $ResolvedKeyPath + ".pub"
if (-not (Test-Path -LiteralPath $PubKeyPath -PathType Leaf)) {
    throw "Public key missing: $PubKeyPath"
}

$PublicKey = (Get-Content -LiteralPath $PubKeyPath -Raw).Trim()
if (-not $PublicKey.StartsWith("ssh-ed25519 ")) {
    throw "Unexpected public key format in $PubKeyPath"
}

$quotedPublicKey = Quote-BashSingle $PublicKey
$authorizeCommand = "umask 077; mkdir -p ~/.ssh; touch ~/.ssh/authorized_keys; grep -qxF $quotedPublicKey ~/.ssh/authorized_keys || printf '%s\n' $quotedPublicKey >> ~/.ssh/authorized_keys; chmod 700 ~/.ssh; chmod 600 ~/.ssh/authorized_keys; echo ENGEL_SSH_KEY_AUTHORIZED"
Write-Host "Authorizing the ROG SSH key on ${CtUser}@${CtHost}:${CtPort}. You may be asked for the CT root password once."
& ssh -p $CtPort -o StrictHostKeyChecking=accept-new "${CtUser}@${CtHost}" $authorizeCommand
if ($LASTEXITCODE -ne 0) {
    throw "SSH public key authorization failed."
}

Invoke-KeySsh -Arguments @("${CtUser}@${CtHost}", "echo ENGEL_SSH_KEY_OK")

$Stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$StageRoot = Join-Path $ProjectRoot ("runtime\temp\engel_persistent_agentic_install_" + $Stamp)
$RemoteStage = "/tmp/engel_persistent_agentic_install_$Stamp"
New-DirectoryIfMissing $StageRoot

$requiredRootFiles = @(
    "engel_vault_paths.py",
    "engel_large_chat_llm.py",
    "engel_agent_meeting_room.py",
    "engel_project_paths.py",
    "engel_temp_policy.py",
    "engel_android_worker_prompt_signals.py",
    "engel_prompt_bridge_selection.py"
)
$optionalRootFiles = @(
    "engel_device_capability_registry.py",
    "engel_rust_meeting_room_bridge.py",
    "engel_remote_worker_link_manager.py",
    "engel_communication_queen_assignment_producer.py",
    "engel_phone_wake_manager.py",
    "engel_trading_dashboard_bridge.py",
    "engel_os_bridge.py",
    "engel_agent_bridge.py",
    "engel_engel_agent_runner.py",
    "engel_code_factory_bridge.py",
    "engel_game_factory_bridge.py",
    "engel_architect_agent.py",
    "engel_sub_node_meeting_bridge.py",
    "engel_remote_worker_job_assignment.py",
    "engel_sub_node_remote_control.py",
    "engel_offline_seed_llm.py",
    "engel_local_multi_model_code.py",
    "engel_communication_router.py",
    "engel_adb_worker_manager.py",
    "engel_shared_drive_room.py",
    "engel_main_server_merge.py"
)
$requiredToolFiles = @(
    "tools\engel_main_server_chat_http_service.py",
    "tools\engel_local_model_service.py",
    "tools\engel_meeting_room_lan_server.py",
    "tools\run_engel_standalone_chat_llm.py"
)
$optionalMemoryFiles = @(
    "memory\ENGEL_MAIN_SERVER_MERGE_V1.json",
    "memory\ENGEL_MAIN_SERVER_MERGE_V1.md"
)
$optionalReportFiles = @(
    "reports\codex_bridge\ENGEL_MAIN_SERVER_MERGE_20260628.md"
)

foreach ($file in $requiredRootFiles) { Copy-StageFile $file "root" }
foreach ($file in $optionalRootFiles) { Copy-StageFile $file "root" -Optional }
foreach ($file in $requiredToolFiles) { Copy-StageFile $file "tools" }
foreach ($file in $optionalMemoryFiles) { Copy-StageFile $file "memory" -Optional }
foreach ($file in $optionalReportFiles) { Copy-StageFile $file "reports\codex_bridge" -Optional }

$remoteShellTemplate = @'
#!/usr/bin/env bash
set -euo pipefail

RUNTIME_ROOT="__RUNTIME_ROOT__"
STAGE="__REMOTE_STAGE__"
CHAT_PORT="__CHAT_PORT__"
MEETING_PORT="__MEETING_PORT__"

if [[ ! -d "$STAGE" ]]; then
  echo "Missing remote staging directory: $STAGE" >&2
  exit 2
fi

mkdir -p "$RUNTIME_ROOT"/{tools,logs,run,run/receipts,memory,reports/codex_bridge,runtime/meeting_room,runtime/meeting_room_server}

if compgen -G "$STAGE/root/*.py" >/dev/null; then
  cp -f "$STAGE"/root/*.py "$RUNTIME_ROOT"/
fi
cp -f "$STAGE"/tools/*.py "$RUNTIME_ROOT"/tools/
if compgen -G "$STAGE/memory/*" >/dev/null; then
  cp -f "$STAGE"/memory/* "$RUNTIME_ROOT"/memory/
fi
if compgen -G "$STAGE/reports/codex_bridge/*" >/dev/null; then
  cp -f "$STAGE"/reports/codex_bridge/* "$RUNTIME_ROOT"/reports/codex_bridge/
fi
chmod 0644 "$RUNTIME_ROOT"/*.py "$RUNTIME_ROOT"/tools/*.py 2>/dev/null || true

PY="$RUNTIME_ROOT/.venv/bin/python"
if [[ ! -x "$PY" ]]; then
  echo "Missing Engel Python venv interpreter: $PY" >&2
  exit 2
fi

"$PY" -m py_compile \
  "$RUNTIME_ROOT/tools/engel_main_server_chat_http_service.py" \
  "$RUNTIME_ROOT/tools/engel_meeting_room_lan_server.py" \
  "$RUNTIME_ROOT/tools/run_engel_standalone_chat_llm.py" \
  "$RUNTIME_ROOT/engel_agent_meeting_room.py"

cat >/etc/systemd/system/engel-agent-meeting-room.service <<UNIT
[Unit]
Description=Engel AI Main Agent Meeting Room
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$RUNTIME_ROOT
Environment=ENGEL_APP_ROOT=$RUNTIME_ROOT
Environment=ENGEL_MEETING_ROOM_SERVER_ROOT=$RUNTIME_ROOT/run/meeting_room_server
Environment=ENGEL_MEETING_ROOM_SERVER_HOST=127.0.0.1
Environment=ENGEL_MEETING_ROOM_SERVER_PORT=$MEETING_PORT
Environment=PYTHONUNBUFFERED=1
ExecStart=$PY $RUNTIME_ROOT/tools/engel_meeting_room_lan_server.py --host 127.0.0.1 --port $MEETING_PORT --startup-event
Restart=always
RestartSec=5
StandardOutput=append:$RUNTIME_ROOT/logs/engel_agent_meeting_room.service.log
StandardError=append:$RUNTIME_ROOT/logs/engel_agent_meeting_room.service.err.log

[Install]
WantedBy=multi-user.target
UNIT

cat >/etc/systemd/system/engel-main-chat.service <<UNIT
[Unit]
Description=Engel AI Main Long-Lived Chat Service
After=network-online.target engel-agent-meeting-room.service
Wants=network-online.target engel-agent-meeting-room.service

[Service]
Type=simple
WorkingDirectory=$RUNTIME_ROOT
Environment=ENGEL_APP_ROOT=$RUNTIME_ROOT
Environment=ENGEL_MAIN_SERVER_ENABLED=1
Environment=ENGEL_MAIN_LONG_LIVED_LOCAL_MODEL_SERVICE=1
Environment=ENGEL_MAIN_SERVER_MEETING_ROOM_URL=http://127.0.0.1:$MEETING_PORT
Environment=PYTHONUNBUFFERED=1
ExecStart=$PY $RUNTIME_ROOT/tools/engel_main_server_chat_http_service.py --host 127.0.0.1 --port $CHAT_PORT
Restart=always
RestartSec=5
StandardOutput=append:$RUNTIME_ROOT/logs/engel_main_chat.service.log
StandardError=append:$RUNTIME_ROOT/logs/engel_main_chat.service.err.log

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable --now engel-agent-meeting-room.service
systemctl enable --now engel-main-chat.service
systemctl restart engel-agent-meeting-room.service
systemctl restart engel-main-chat.service
sleep 3
systemctl is-active --quiet engel-agent-meeting-room.service
systemctl is-active --quiet engel-main-chat.service

"$PY" - <<PY
import json
import urllib.request

checks = [
    ("meeting_room", "http://127.0.0.1:$MEETING_PORT/health"),
    ("chat", "http://127.0.0.1:$CHAT_PORT/health"),
]
result = {"ok": True, "checks": []}
for name, url in checks:
    with urllib.request.urlopen(url, timeout=10) as response:
        payload = json.loads(response.read().decode("utf-8"))
    result["checks"].append({"name": name, "url": url, "ok": bool(payload.get("ok") is True), "status": payload.get("status", "")})
    if payload.get("ok") is not True:
        result["ok"] = False
print(json.dumps(result, indent=2, sort_keys=True))
raise SystemExit(0 if result["ok"] else 1)
PY

cat >"$RUNTIME_ROOT/run/receipts/ENGEL_PERSISTENT_AGENTIC_SYSTEM_${STAGE##*_}.json" <<JSON
{
  "schema": "engel_persistent_agentic_system_install_v1",
  "target": "engel-ai-main CT 246",
  "runtime_root": "$RUNTIME_ROOT",
  "chat_service": "engel-main-chat.service",
  "meeting_room_service": "engel-agent-meeting-room.service",
  "chat_port": $CHAT_PORT,
  "meeting_room_port": $MEETING_PORT,
  "storage_mutation_performed": false,
  "pct_set_performed": false,
  "disk_format_performed": false,
  "password_stored": false
}
JSON

echo "ENGEL_PERSISTENT_AGENTIC_SYSTEM_READY"
'@

$remoteShell = $remoteShellTemplate.
    Replace("__RUNTIME_ROOT__", $RuntimeRoot).
    Replace("__REMOTE_STAGE__", $RemoteStage).
    Replace("__CHAT_PORT__", [string]$ChatServicePort).
    Replace("__MEETING_PORT__", [string]$MeetingRoomPort)
$remoteScriptPath = Join-Path $StageRoot "install_persistent_agentic_system.sh"
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($remoteScriptPath, $remoteShell, $utf8NoBom)

Write-Host "Copying Engel persistent agentic system files to ${CtUser}@${CtHost}:${RemoteStage}"
& scp -i $ResolvedKeyPath -P $CtPort -r $StageRoot "${CtUser}@${CtHost}:${RemoteStage}"
if ($LASTEXITCODE -ne 0) {
    throw "scp failed. CT services were not installed."
}

Write-Host "Installing CT systemd services for chat and Agent Meeting Room."
Invoke-KeySsh -Arguments @("${CtUser}@${CtHost}", "bash '$RemoteStage/install_persistent_agentic_system.sh'")

if (-not $NoScheduledTask) {
    $psArgs = @(
        "-NoProfile",
        "-WindowStyle", "Hidden",
        "-ExecutionPolicy", "Bypass",
        "-File", "`"$TunnelScript`"",
        "-CtHost", "`"$CtHost`"",
        "-CtPort", [string]$CtPort,
        "-CtUser", "`"$CtUser`"",
        "-KeyPath", "`"$ResolvedKeyPath`""
    ) -join " "
    try {
        $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $psArgs
        $trigger = New-ScheduledTaskTrigger -AtLogOn
        $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Seconds 0)
        $settings.Hidden = $true
        Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Description "Keeps the ROG Engel AI Main app linked to CT 246 chat and Agent Meeting Room." -Force | Out-Null
        Write-Host "Installed Windows scheduled task: $TaskName"
    } catch {
        $startup = [Environment]::GetFolderPath("Startup")
        $cmdPath = Join-Path $startup "Engel Main Server Link.cmd"
        $cmd = "@echo off`r`nstart ""Engel Main Server Link"" /min powershell.exe $psArgs`r`n"
        Set-Content -LiteralPath $cmdPath -Value $cmd -Encoding ASCII
        Write-Warning "Scheduled task install failed; installed Startup fallback: $cmdPath"
    }

    if (-not $NoStartNow) {
        Start-Process -FilePath "powershell.exe" -ArgumentList $psArgs -WindowStyle Hidden
        Start-Sleep -Seconds 4
        Write-Host "Started persistent ROG tunnel process."
    }
}

$health = [ordered]@{
    schema = "engel_persistent_agentic_system_local_receipt_v1"
    created_at_utc = (Get-Date).ToUniversalTime().ToString("o")
    ct_host = $CtHost
    ct_port = $CtPort
    ct_user = $CtUser
    runtime_root = $RuntimeRoot
    ssh_key = $ResolvedKeyPath
    password_stored = $false
    scheduled_task = if ($NoScheduledTask) { "" } else { $TaskName }
    chat_local_url = "http://127.0.0.1:24680/health"
    meeting_room_local_url = "http://127.0.0.1:8790/health"
    storage_mutation_performed = $false
    pct_set_performed = $false
    disk_format_performed = $false
}
$ReceiptDir = Join-Path $ProjectRoot "reports\ct_sync"
New-DirectoryIfMissing $ReceiptDir
$ReceiptPath = Join-Path $ReceiptDir ("ENGEL_PERSISTENT_AGENTIC_SYSTEM_" + $Stamp + ".json")
$health | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $ReceiptPath -Encoding UTF8

Write-Host "Persistent Engel AI Main server link installed."
Write-Host "Chat URL for app: http://127.0.0.1:24680"
Write-Host "Agent Meeting Room URL for app: http://127.0.0.1:8790"
Write-Host "Local receipt: $ReceiptPath"
