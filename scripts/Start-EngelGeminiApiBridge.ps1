param(
    [string]$HostAddress = "127.0.0.1",
    [int]$Port = 24886,
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

if ($Port -lt 1 -or $Port -gt 65535) {
    throw "Port must be from 1 to 65535."
}

$ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$BridgeScript = Join-Path $ProjectRoot "tools\engel_gemini_api_bridge_http_service.py"
$PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$FallbackPython = Join-Path $ProjectRoot "runtime\python310\python.exe"
$LogDir = Join-Path $env:LOCALAPPDATA "Engel AI Main\logs"
$LogPath = Join-Path $LogDir "gemini-api-bridge.log"
$ErrLogPath = Join-Path $LogDir "gemini-api-bridge.err.log"

if (-not (Test-Path -LiteralPath $BridgeScript -PathType Leaf)) {
    throw "Gemini API bridge script missing: $BridgeScript"
}
if (-not (Test-Path -LiteralPath $PythonExe -PathType Leaf)) {
    if (Test-Path -LiteralPath $FallbackPython -PathType Leaf) {
        $PythonExe = $FallbackPython
    } else {
        $PythonExe = "python"
    }
}

$HealthUrl = "http://${HostAddress}:${Port}/health"
if (Test-BridgeHealth -Url $HealthUrl) {
    Write-Host "Engel Gemini API bridge already online: $HealthUrl"
    exit 0
}

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

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

$deadline = (Get-Date).AddSeconds(15)
while ((Get-Date) -lt $deadline) {
    if (Test-BridgeHealth -Url $HealthUrl) {
        Write-Host "Engel Gemini API bridge online: $HealthUrl pid=$($process.Id)"
        exit 0
    }
    Start-Sleep -Milliseconds 400
}

throw "Engel Gemini API bridge did not become healthy. See $LogPath"
