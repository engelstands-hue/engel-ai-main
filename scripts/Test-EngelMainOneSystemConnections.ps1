param(
    [string]$CtHost = "192.0.2.50",
    [int]$CtPort = 24622,
    [string]$CtUser = "root",
    [string]$RuntimeRoot = "/opt/engel",
    [string]$KeyPath = (Join-Path $env:USERPROFILE ".ssh\engel_ai_main_ct246_ed25519"),
    [string]$TaskName = "EngelMainServerPersistentLink",
    [switch]$Json,
    [switch]$NoExitCode
)

$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$ResolvedKeyPath = [System.IO.Path]::GetFullPath($KeyPath)
$ChatHealthUrl = "http://127.0.0.1:24680/health"
$MeetingHealthUrl = "http://127.0.0.1:8790/health"
$ExePath = Join-Path $ProjectRoot "engel_flutter_main\build\windows\x64\runner\Release\EngelAIMain.exe"
$DesktopShortcut = Join-Path ([Environment]::GetFolderPath("Desktop")) "Engel AI Main - One System.lnk"
$Checks = New-Object System.Collections.Generic.List[object]

function Add-Check {
    param(
        [string]$Name,
        [bool]$Ok,
        [string]$Status,
        [object]$Details = $null
    )
    $Checks.Add([ordered]@{
        name = $Name
        ok = $Ok
        status = $Status
        details = $Details
    }) | Out-Null
}

function Test-PortQuiet {
    param([string]$HostName, [int]$Port)
    return [bool](Test-NetConnection -ComputerName $HostName -Port $Port -InformationLevel Quiet -WarningAction SilentlyContinue)
}

function Read-Health {
    param([string]$Url)
    try {
        $payload = Invoke-RestMethod -Uri $Url -TimeoutSec 8
        return @{ ok = [bool]($payload.ok -eq $true); payload = $payload; error = "" }
    } catch {
        return @{ ok = $false; payload = $null; error = $_.Exception.Message }
    }
}

function Invoke-Ct {
    param([string]$Command)
    if (-not (Test-Path -LiteralPath $ResolvedKeyPath -PathType Leaf)) {
        return @{ exit_code = 2; output = "missing key: $ResolvedKeyPath" }
    }
    $output = & ssh -i $ResolvedKeyPath -p $CtPort -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=accept-new "${CtUser}@${CtHost}" $Command 2>&1
    return @{ exit_code = $LASTEXITCODE; output = (($output | Out-String).Trim()) }
}

$ctTcp = Test-PortQuiet -HostName $CtHost -Port $CtPort
Add-Check "ct_ssh_tcp" $ctTcp "CT SSH route ${CtHost}:${CtPort}" @{ host = $CtHost; port = $CtPort }

$keyExists = Test-Path -LiteralPath $ResolvedKeyPath -PathType Leaf
Add-Check "rog_ssh_key_exists" $keyExists $ResolvedKeyPath @{ public_key_exists = (Test-Path -LiteralPath ($ResolvedKeyPath + ".pub") -PathType Leaf) }

$sshAuth = Invoke-Ct "printf ENGEL_SSH_KEY_OK"
Add-Check "ct_ssh_key_auth" ($sshAuth.exit_code -eq 0 -and $sshAuth.output -match "ENGEL_SSH_KEY_OK") $sshAuth.output @{ exit_code = $sshAuth.exit_code }

$chatSvc = Invoke-Ct "systemctl is-active engel-main-chat.service"
Add-Check "ct_chat_service" ($chatSvc.exit_code -eq 0 -and $chatSvc.output -eq "active") $chatSvc.output @{ service = "engel-main-chat.service" }

$meetingSvc = Invoke-Ct "systemctl is-active engel-agent-meeting-room.service"
Add-Check "ct_meeting_room_service" ($meetingSvc.exit_code -eq 0 -and $meetingSvc.output -eq "active") $meetingSvc.output @{ service = "engel-agent-meeting-room.service" }

$ctChatHealth = Invoke-Ct "curl -fsS http://127.0.0.1:8765/health"
Add-Check "ct_chat_health" ($ctChatHealth.exit_code -eq 0 -and $ctChatHealth.output -match '"ok"\s*:\s*true') "CT chat health" @{ exit_code = $ctChatHealth.exit_code; output = $ctChatHealth.output }

$ctMeetingHealth = Invoke-Ct "curl -fsS http://127.0.0.1:8790/health"
Add-Check "ct_meeting_room_health" ($ctMeetingHealth.exit_code -eq 0 -and $ctMeetingHealth.output -match '"ok"\s*:\s*true') "CT meeting room health" @{ exit_code = $ctMeetingHealth.exit_code; output = $ctMeetingHealth.output }

$chatTcp = Test-PortQuiet -HostName "127.0.0.1" -Port 24680
Add-Check "rog_chat_tunnel_tcp" $chatTcp "ROG local chat tunnel 127.0.0.1:24680" $null

$meetingTcp = Test-PortQuiet -HostName "127.0.0.1" -Port 8790
Add-Check "rog_meeting_room_tunnel_tcp" $meetingTcp "ROG local meeting room tunnel 127.0.0.1:8790" $null

$chatHealth = Read-Health $ChatHealthUrl
Add-Check "rog_chat_health" $chatHealth.ok $ChatHealthUrl $chatHealth

$meetingHealth = Read-Health $MeetingHealthUrl
Add-Check "rog_meeting_room_health" $meetingHealth.ok $MeetingHealthUrl $meetingHealth

try {
    $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop
    Add-Check "windows_logon_task" $true $task.State @{ task_name = $TaskName }
} catch {
    Add-Check "windows_logon_task" $false $_.Exception.Message @{ task_name = $TaskName }
}

$exeExists = Test-Path -LiteralPath $ExePath -PathType Leaf
Add-Check "engel_release_exe" $exeExists $ExePath $null

$running = @(Get-Process -Name "EngelAIMain" -ErrorAction SilentlyContinue)
Add-Check "engel_app_process" ($running.Count -gt 0) ("process_count=" + $running.Count) @{ ids = @($running | ForEach-Object { $_.Id }) }

$shortcutExists = Test-Path -LiteralPath $DesktopShortcut -PathType Leaf
Add-Check "desktop_shortcut" $shortcutExists $DesktopShortcut $null

$allOk = -not @($Checks | Where-Object { $_.ok -ne $true }).Count
$Stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$ReceiptDir = Join-Path $ProjectRoot "reports\ct_sync"
New-Item -ItemType Directory -Force -Path $ReceiptDir | Out-Null
$ReceiptPath = Join-Path $ReceiptDir ("ENGEL_ONE_SYSTEM_CONNECTIONS_" + $Stamp + ".json")
$Receipt = [ordered]@{
    schema = "engel_one_system_connection_debug_v1"
    ok = $allOk
    created_at_utc = (Get-Date).ToUniversalTime().ToString("o")
    project_root = $ProjectRoot
    ct_host = $CtHost
    ct_port = $CtPort
    ct_user = $CtUser
    runtime_root = $RuntimeRoot
    chat_health_url = $ChatHealthUrl
    meeting_room_health_url = $MeetingHealthUrl
    receipt_path = $ReceiptPath
    storage_mutation_performed = $false
    pct_set_performed = $false
    disk_format_performed = $false
    checks = $Checks
}
$Receipt | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $ReceiptPath -Encoding UTF8

if ($Json) {
    $Receipt | ConvertTo-Json -Depth 12
} else {
    Write-Host ("Engel One System connections: " + ($(if ($allOk) { "OK" } else { "CHECK FAILURES" })))
    foreach ($check in $Checks) {
        $mark = if ($check.ok) { "PASS" } else { "FAIL" }
        Write-Host ("{0} {1}: {2}" -f $mark, $check.name, $check.status)
    }
    Write-Host "Receipt: $ReceiptPath"
}

if (-not $allOk -and -not $NoExitCode) {
    exit 1
}
