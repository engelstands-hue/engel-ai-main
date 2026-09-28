param(
    [double]$Minutes = 60,
    [double]$IntervalSeconds = 90,
    [int]$MaxTurns = 0,
    [string]$ChatUrl = "http://127.0.0.1:24680",
    [string]$RoomUrl = "http://127.0.0.1:8790",
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$OfficeLauncher = Join-Path $PSScriptRoot "Start-EngelAgentMeetingRoomOffice.ps1"
$Runner = Join-Path $ProjectRoot "tools\run_engel_agent_room_training_loop.py"
$VenvPython = Join-Path $ProjectRoot "runtime\browser_ai_venv\Scripts\python.exe"
$PythonExe = if (Test-Path -LiteralPath $VenvPython -PathType Leaf) { $VenvPython } else { "python" }

function Test-EngelHealth {
    param([string]$Url)
    try {
        $payload = Invoke-RestMethod -Uri $Url -TimeoutSec 8
        return [bool]($payload.ok -eq $true)
    } catch {
        return $false
    }
}

if (-not (Test-Path -LiteralPath $OfficeLauncher -PathType Leaf)) {
    throw "Missing office launcher: $OfficeLauncher"
}
if (-not (Test-Path -LiteralPath $Runner -PathType Leaf)) {
    throw "Missing training runner: $Runner"
}

if (-not (Test-EngelHealth "$ChatUrl/health") -or -not (Test-EngelHealth "$RoomUrl/health")) {
    & $OfficeLauncher -NoBrowser:$NoBrowser | Out-Null
}

if (-not (Test-EngelHealth "$ChatUrl/health")) {
    throw "Engel CT chat route is not healthy at $ChatUrl/health"
}
if (-not (Test-EngelHealth "$RoomUrl/health")) {
    throw "Engel Meeting Room route is not healthy at $RoomUrl/health"
}

$argsList = @(
    $Runner,
    "--minutes", ([string]$Minutes),
    "--interval-seconds", ([string]$IntervalSeconds),
    "--chat-url", $ChatUrl,
    "--room-url", $RoomUrl
)
if ($MaxTurns -gt 0) {
    $argsList += @("--max-turns", ([string]$MaxTurns))
}

& $PythonExe @argsList
