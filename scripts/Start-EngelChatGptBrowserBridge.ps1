param(
    [string]$HostAddress = "127.0.0.1",
    [int]$Port = 24884,
    [switch]$Foreground
)

$ErrorActionPreference = "Stop"

function Test-BridgeHealth {
    param([string]$Url)
    try {
        $result = Invoke-RestMethod -Uri $Url -Method Get -TimeoutSec 3
        return [bool]($result.ok)
    } catch {
        return $false
    }
}

function Quote-ProcessArg {
    param([string]$Text)
    return '"' + ($Text -replace '"', '\"') + '"'
}

function Get-BridgeProcesses {
    param([string]$ScriptPath, [int]$ListenPort)
    $escaped = [regex]::Escape($ScriptPath)
    Get-CimInstance Win32_Process | Where-Object {
        $_.CommandLine -match $escaped -and
        $_.CommandLine -match "--port[`" ]+$ListenPort(\s|`"|$)"
    }
}

function Get-WorkerProcesses {
    param([string]$ProjectRoot)
    $workerPath = Join-Path $ProjectRoot "tools\engel_chatgpt_browser_worker.py"
    $escaped = [regex]::Escape($workerPath)
    Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match $escaped }
}

if ($Port -lt 1 -or $Port -gt 65535) {
    throw "Port must be from 1 to 65535."
}

$ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$BridgeScript = Join-Path $ProjectRoot "tools\engel_chatgpt_browser_bridge_http_service.py"
$PythonExe = Join-Path $ProjectRoot "runtime\browser_ai_venv\Scripts\python.exe"
$FallbackPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$LogDir = Join-Path $env:LOCALAPPDATA "Engel AI Main\logs"
$LogPath = Join-Path $LogDir "chatgpt-browser-bridge.log"
$ErrLogPath = Join-Path $LogDir "chatgpt-browser-bridge.err.log"

if (-not (Test-Path -LiteralPath $BridgeScript -PathType Leaf)) {
    throw "ChatGPT browser bridge script missing: $BridgeScript"
}
if (-not (Test-Path -LiteralPath $PythonExe -PathType Leaf)) {
    if (Test-Path -LiteralPath $FallbackPython -PathType Leaf) {
        $PythonExe = $FallbackPython
    } else {
        $PythonExe = "python"
    }
}

$HealthUrl = "http://${HostAddress}:${Port}/health"
$bridgeProcesses = @(Get-BridgeProcesses -ScriptPath $BridgeScript -ListenPort $Port)
$workerProcesses = @(Get-WorkerProcesses -ProjectRoot $ProjectRoot)
if ((Test-BridgeHealth -Url $HealthUrl) -and $bridgeProcesses.Count -eq 1 -and $workerProcesses.Count -le 1) {
    Write-Host "Engel ChatGPT browser bridge already online: $HealthUrl"
    exit 0
}
if ($bridgeProcesses.Count -gt 0) {
    Write-Host "Restarting ChatGPT browser bridge to remove duplicate/stale processes: $($bridgeProcesses.Count)"
    foreach ($p in $bridgeProcesses) {
        Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
    }
}
if ($workerProcesses.Count -gt 1) {
    Write-Host "Stopping duplicate ChatGPT browser workers: $($workerProcesses.Count)"
    foreach ($p in $workerProcesses) {
        Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
    }
    $workerPidPath = Join-Path $ProjectRoot "runtime\browser_ai_chatgpt_bridge\worker.pid"
    Remove-Item -LiteralPath $workerPidPath -Force -ErrorAction SilentlyContinue
}
if ($bridgeProcesses.Count -gt 0 -or $workerProcesses.Count -gt 1) {
    Start-Sleep -Seconds 1
}

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
if ([string]::IsNullOrWhiteSpace($env:ENGEL_BROWSER_AI_HEADLESS)) {
    $env:ENGEL_BROWSER_AI_HEADLESS = "1"
}
if ([string]::IsNullOrWhiteSpace($env:ENGEL_BROWSER_AI_HIDE_MODE)) {
    $env:ENGEL_BROWSER_AI_HIDE_MODE = "offscreen"
}

$argsList = @(
    $BridgeScript,
    "--host", $HostAddress,
    "--port", [string]$Port
)
$processArgumentLine = ($argsList | ForEach-Object { Quote-ProcessArg ([string]$_) }) -join " "

if ($Foreground) {
    & $PythonExe @argsList
    exit $LASTEXITCODE
}

$process = Start-Process `
    -FilePath $PythonExe `
    -ArgumentList $processArgumentLine `
    -WorkingDirectory $ProjectRoot `
    -WindowStyle Hidden `
    -RedirectStandardOutput $LogPath `
    -RedirectStandardError $ErrLogPath `
    -PassThru

$deadline = (Get-Date).AddSeconds(20)
while ((Get-Date) -lt $deadline) {
    if (Test-BridgeHealth -Url $HealthUrl) {
        Write-Host "Engel ChatGPT browser bridge online: $HealthUrl pid=$($process.Id)"
        exit 0
    }
    Start-Sleep -Milliseconds 500
}

throw "Engel ChatGPT browser bridge did not become healthy. See $LogPath"
