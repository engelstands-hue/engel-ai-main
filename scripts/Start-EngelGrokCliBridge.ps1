param(
    [string]$HostAddress = "127.0.0.1",
    [int]$Port = 24880,
    [switch]$Foreground
)

$ErrorActionPreference = "Stop"

function Test-BridgeHealth {
    param([string]$Url)
    try {
        $result = Invoke-RestMethod -Uri $Url -Method Get -TimeoutSec 2
        return [bool]($result.ok)
    } catch {
        return $false
    }
}

function Quote-ProcessArg {
    param([string]$Text)
    return '"' + ($Text -replace '"', '\"') + '"'
}

function Get-ExistingToolPath {
    param([string[]]$Candidates)
    foreach ($candidate in $Candidates) {
        if ($candidate -and (Test-Path -LiteralPath $candidate -PathType Container)) {
            return $candidate
        }
    }
    return ""
}

function Get-EngelCleanPath {
    param(
        [string]$ProjectRoot,
        [string]$GrokExe
    )
    $grokBin = Split-Path -Parent $GrokExe
    $gitDir = Get-ExistingToolPath @(
        (Join-Path $ProjectRoot "runtime\git\cmd"),
        (Join-Path $ProjectRoot "runtime\git\bin"),
        (Join-Path $ProjectRoot "runtime\tools\git\cmd"),
        (Join-Path (Split-Path -Parent $ProjectRoot) "flutter_local_sdk\bin\mingit\cmd"),
        (Join-Path (Split-Path -Parent $ProjectRoot) "flutter_local_sdk\bin\mingit\mingw64\bin"),
        (Join-Path (Split-Path -Parent $ProjectRoot) "flutter_windows_3.41.9-stable\flutter\bin\mingit\cmd"),
        (Join-Path (Split-Path -Parent $ProjectRoot) "flutter_windows_3.41.9-stable\flutter\bin\mingit\mingw64\bin"),
        "C:\Program Files\Git\cmd",
        "C:\Program Files\Git\bin",
        "C:\Program Files (x86)\Git\cmd",
        "C:\Program Files (x86)\Git\bin"
    )
    $prefix = @($grokBin, $gitDir) | Where-Object { $_ }
    $existing = @()
    foreach ($entry in ($env:Path -split ';')) {
        if (-not $entry) { continue }
        if (Test-Path -LiteralPath $entry -PathType Container) {
            $existing += $entry
        }
    }
    return (($prefix + $existing) | Select-Object -Unique) -join ';'
}

if ($Port -lt 1 -or $Port -gt 65535) {
    throw "Port must be from 1 to 65535."
}

$ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$BridgeScript = Join-Path $ProjectRoot "tools\engel_grok_cli_bridge_http_service.py"
$GrokExe = Join-Path $ProjectRoot "runtime\xai_grok_cli\bin\grok.exe"
$PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$FallbackPython = Join-Path $ProjectRoot "runtime\python310\python.exe"
$LogDir = Join-Path $env:LOCALAPPDATA "Engel AI Main\logs"
$LogPath = Join-Path $LogDir "grok-cli-bridge.log"
$ErrLogPath = Join-Path $LogDir "grok-cli-bridge.err.log"

if (-not (Test-Path -LiteralPath $BridgeScript -PathType Leaf)) {
    throw "Grok CLI bridge script missing: $BridgeScript"
}
if (-not (Test-Path -LiteralPath $GrokExe -PathType Leaf)) {
    throw "Grok CLI executable missing: $GrokExe"
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
    Write-Host "Engel Grok CLI bridge already online: $HealthUrl"
    exit 0
}

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$env:ENGEL_GROK_CLI_EXE = $GrokExe
# Super-account session is D:\b.WorkSpace\Engel App\.grok (C:\Users\ziese\.grok is a junction).
$env:USERPROFILE = $ProjectRoot
$env:GROK_BIN_DIR = (Split-Path -Parent $GrokExe)
$env:ENGEL_GROK_CLI_MODEL = "grok-4.6"
$env:ENGEL_GROK_API_FIRST = "0"
$env:ENGEL_GROK_CLI_REQUEST_TIMEOUT_SECONDS = "180"
$env:Path = Get-EngelCleanPath -ProjectRoot $ProjectRoot -GrokExe $GrokExe

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

# Agent Job Objects kill Start-Process children. WMI Create runs under
# WmiPrvSE so the Super-account Grok bridge survives after this script exits.
$launch = "cmd.exe /c start `"EngelGrokCliBridge`" /MIN `"$PythonExe`" $processArgumentLine >> `"$LogPath`" 2>> `"$ErrLogPath`""
$created = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{
    CommandLine = $launch
    CurrentDirectory = $ProjectRoot
}
if (-not $created -or [int]$created.ReturnValue -ne 0) {
    throw "Engel Grok CLI bridge failed to launch (WMI $($created.ReturnValue))."
}

$deadline = (Get-Date).AddSeconds(12)
while ((Get-Date) -lt $deadline) {
    if (Test-BridgeHealth -Url $HealthUrl) {
        $listen = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
        Write-Host "Engel Grok CLI bridge online: $HealthUrl pid=$($listen.OwningProcess)"
        exit 0
    }
    Start-Sleep -Milliseconds 400
}

throw "Engel Grok CLI bridge did not become healthy. See $LogPath"
