param(
    [int]$Port = 3000,
    [string]$HostName = "127.0.0.1",
    [int]$ChatLocalPort = 24680,
    [int]$ServerRuntimePort = 8765,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$OneSystemLauncher = Join-Path $PSScriptRoot "Start-EngelMainOneSystem.ps1"
$LocalRuntimeDir = Join-Path $ProjectRoot "runtime\engel3d_office_main"
$PidPath = Join-Path $LocalRuntimeDir "server.pid"

function Test-HealthOk {
    param([string]$Url, [int]$TimeoutSec = 4)
    try {
        $payload = Invoke-RestMethod -Uri $Url -TimeoutSec $TimeoutSec
        return [bool]($payload.ok -eq $true)
    } catch {
        return $false
    }
}

function Stop-OldLocalOfficeDev {
    $candidatePids = @()
    if (Test-Path -LiteralPath $PidPath -PathType Leaf) {
        $pidText = (Get-Content -LiteralPath $PidPath -Raw).Trim()
        if ($pidText -match '^\d+$') {
            $candidatePids += [int]$pidText
        }
    }
    Get-NetTCPConnection -LocalAddress $HostName -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        ForEach-Object { $candidatePids += [int]$_.OwningProcess }
    $candidatePids = $candidatePids | Sort-Object -Unique
    foreach ($candidatePid in $candidatePids) {
        $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$candidatePid" -ErrorAction SilentlyContinue
        if ($null -eq $proc) { continue }
        $cmd = [string]$proc.CommandLine
        if ($cmd -like "*engel3d_office_main*" -or $cmd -like "*server/index.js --dev*") {
            Stop-Process -Id $candidatePid -Force -ErrorAction SilentlyContinue
        }
    }
}

if (-not (Test-Path -LiteralPath $OneSystemLauncher -PathType Leaf)) {
    throw "One-system launcher missing: $OneSystemLauncher"
}

Stop-OldLocalOfficeDev

& $OneSystemLauncher -SkipConnectionTest -NoLaunchApp -OfficeLocalPort $Port | Out-Null

$deadline = (Get-Date).AddSeconds(35)
do {
    $chatOk = Test-HealthOk "http://127.0.0.1:24680/health"
    $meetingOk = Test-HealthOk "http://127.0.0.1:8790/health"
    $officeOk = Test-HealthOk "http://${HostName}:$Port/api/health"
    if ($chatOk -and $meetingOk -and $officeOk) {
        break
    }
    Start-Sleep -Seconds 2
} while ((Get-Date) -lt $deadline)

if (-not (Test-HealthOk "http://127.0.0.1:24680/health" -TimeoutSec 6)) {
    throw "Engel CT chat tunnel is not healthy at http://127.0.0.1:24680/health."
}
if (-not (Test-HealthOk "http://127.0.0.1:8790/health" -TimeoutSec 6)) {
    throw "Engel CT meeting room tunnel is not healthy at http://127.0.0.1:8790/health."
}
if (-not (Test-HealthOk "http://${HostName}:$Port/api/health" -TimeoutSec 6)) {
    throw "Engel server-hosted office is not healthy at http://${HostName}:$Port/api/health."
}

$RogChatTunnelUrl = "http://127.0.0.1:$ChatLocalPort"
$OfficeServerRuntimeUrl = "http://127.0.0.1:$ServerRuntimePort"
$NowMs = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
$studioPatch = @{
    gateway = @{
        url = $OfficeServerRuntimeUrl
        token = ""
        adapterType = "custom"
        profiles = @{
            custom = @{
                url = $OfficeServerRuntimeUrl
                token = ""
            }
        }
        lastKnownGood = @{
            url = $OfficeServerRuntimeUrl
            token = ""
            adapterType = "custom"
        }
    }
    activeFloorId = "custom-second"
    officeFloors = @{
        "custom-second" = @{
            gatewayUrl = $OfficeServerRuntimeUrl
            provider = "custom"
            runtimeProfileId = "custom-default"
            status = "connected"
            lastKnownGoodAt = $NowMs
            lastErrorCode = ""
            lastErrorMessage = ""
        }
    }
}
Invoke-RestMethod `
    -Uri "http://${HostName}:$Port/api/studio" `
    -Method Put `
    -ContentType "application/json" `
    -Body ($studioPatch | ConvertTo-Json -Depth 8) `
    -TimeoutSec 10 | Out-Null

$runtimeState = Invoke-RestMethod -Uri "http://127.0.0.1:24680/state" -TimeoutSec 8
$virtualState = Invoke-RestMethod -Uri "http://127.0.0.1:8790/virtual-environments/engel3d-office/presence" -TimeoutSec 8
$url = "http://${HostName}:$Port/office?engelServerRoom=1"

if (-not $NoBrowser) {
    Start-Process $url | Out-Null
}

[pscustomobject]@{
    ok = $true
    url = $url
    server_hosted = $true
    rog_browser_role = "viewer/controller"
    office_process_location = "CT 246 engel-ai-main"
    active_runtime_storage = "engel-fast-ssd"
    custom_runtime_url = $OfficeServerRuntimeUrl
    office_server_runtime_url = $OfficeServerRuntimeUrl
    rog_chat_tunnel_url = $RogChatTunnelUrl
    meeting_room_url = "http://127.0.0.1:8790"
    ct_model = $runtimeState.runtime.active_model
    virtual_agent_count = $virtualState.agents.Count
    virtual_status_counts = $virtualState.status_counts
    phone_alpha = $runtimeState.active.'android-worker-alpha'[0]
    phone_beta = $runtimeState.active.'android-worker-beta'[0]
} | ConvertTo-Json -Depth 8
