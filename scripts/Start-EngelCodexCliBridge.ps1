param(
    [string]$HostAddress = "127.0.0.1",
    [int]$Port = 24888,
    [string]$CodexExe = "",
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

function Resolve-CodexExecutable {
    param([string]$Configured)
    $candidates = @()
    if ($Configured) {
        $candidates += $Configured
    }
    $found = Get-Command codex.cmd -ErrorAction SilentlyContinue
    if ($found -and $found.Source) {
        $candidates += $found.Source
    }
    $found = Get-Command codex.exe -ErrorAction SilentlyContinue
    if ($found -and $found.Source) {
        $candidates += $found.Source
    }
    $found = Get-Command codex -ErrorAction SilentlyContinue
    if ($found -and $found.Source) {
        $candidates += $found.Source
    }
    $candidates += @(
        "D:\npm-global\codex.cmd",
        "$env:APPDATA\npm\codex.cmd",
        "$env:USERPROFILE\.vscode\extensions\openai.chatgpt-26.5623.101652-win32-x64\bin\windows-x86_64\codex.exe"
    )
    foreach ($candidate in ($candidates | Where-Object { $_ } | Select-Object -Unique)) {
        if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) {
            continue
        }
        if ([System.IO.Path]::GetExtension($candidate).ToLowerInvariant() -eq ".ps1") {
            $cmdSibling = [System.IO.Path]::ChangeExtension($candidate, ".cmd")
            if (Test-Path -LiteralPath $cmdSibling -PathType Leaf) {
                return $cmdSibling
            }
            $exeSibling = [System.IO.Path]::ChangeExtension($candidate, ".exe")
            if (Test-Path -LiteralPath $exeSibling -PathType Leaf) {
                return $exeSibling
            }
            continue
        }
        return $candidate
    }
    return ""
}

function Get-BridgeProcesses {
    param([string]$ScriptPath, [int]$ListenPort)
    $escaped = [regex]::Escape($ScriptPath)
    Get-CimInstance Win32_Process | Where-Object {
        $_.CommandLine -match $escaped -and
        $_.CommandLine -match "--port[`" ]+$ListenPort(\s|`"|$)"
    }
}

if ($Port -lt 1 -or $Port -gt 65535) {
    throw "Port must be from 1 to 65535."
}

$ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$BridgeScript = Join-Path $ProjectRoot "tools\engel_codex_cli_bridge_http_service.py"
$PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$FallbackPython = Join-Path $ProjectRoot "runtime\python310\python.exe"
$LogDir = Join-Path $env:LOCALAPPDATA "Engel AI Main\logs"
$LogPath = Join-Path $LogDir "codex-cli-bridge.log"
$ErrLogPath = Join-Path $LogDir "codex-cli-bridge.err.log"

if (-not (Test-Path -LiteralPath $BridgeScript -PathType Leaf)) {
    throw "Codex CLI bridge script missing: $BridgeScript"
}
$CodexExe = Resolve-CodexExecutable -Configured $CodexExe
if (-not $CodexExe -or -not (Test-Path -LiteralPath $CodexExe -PathType Leaf)) {
    throw "Codex CLI executable missing. Install or sign into Codex first, then rerun this bridge."
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
    Write-Host "Engel Codex CLI bridge already online: $HealthUrl"
    exit 0
}
$bridgeProcesses = @(Get-BridgeProcesses -ScriptPath $BridgeScript -ListenPort $Port)
if ($bridgeProcesses.Count -gt 0) {
    Write-Host "Restarting unhealthy Codex CLI bridge process(es): $($bridgeProcesses.Count)"
    foreach ($p in $bridgeProcesses) {
        Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Seconds 1
}

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$env:ENGEL_CODEX_CLI_EXE = $CodexExe
$env:ENGEL_CODEX_CLI_CHAT_WORKSPACE = $ProjectRoot
if (-not $env:ENGEL_CODEX_CLI_MODEL) {
    # gpt-5.4 was retired for ChatGPT-account Codex (2026-08-01); gpt-5.5 and
    # gpt-5.4-mini are the supported slugs on this account.
    $env:ENGEL_CODEX_CLI_MODEL = "gpt-5.5"
}

$codexDir = Split-Path -Parent $CodexExe
if ($codexDir -and (Test-Path -LiteralPath $codexDir -PathType Container)) {
    $env:Path = (($codexDir, ($env:Path -split ';' | Where-Object { $_ })) | Select-Object -Unique) -join ';'
}

# codex.cmd is an npm shim that invokes node at runtime; the bridge inherits
# THIS process env, so node's directory must be on Path or every codex call
# fails with "'node' is not recognized" regardless of where codex.cmd lives.
$nodeCmd = Get-Command node -ErrorAction SilentlyContinue
$nodeDir = if ($nodeCmd -and $nodeCmd.Source) { Split-Path -Parent $nodeCmd.Source }
           elseif (Test-Path "C:\Program Files\nodejs\node.exe") { "C:\Program Files\nodejs" }
           else { $null }
if ($nodeDir -and (($env:Path -split ';') -notcontains $nodeDir)) {
    $env:Path = "$nodeDir;$env:Path"
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

$deadline = (Get-Date).AddSeconds(15)
while ((Get-Date) -lt $deadline) {
    if (Test-BridgeHealth -Url $HealthUrl) {
        Write-Host "Engel Codex CLI bridge online: $HealthUrl pid=$($process.Id)"
        exit 0
    }
    Start-Sleep -Milliseconds 400
}

throw "Engel Codex CLI bridge did not become healthy. See $LogPath"
