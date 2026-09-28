<#
.SYNOPSIS
    Install the real Sub-Engel Discord worker on the Sub-Engel node (the living-room PC).

.DESCRIPTION
    Replaces the earlier stub bot that answered every prompt with one hardcoded
    "Standing by." sentence. The new worker answers from real node state, and holds a
    bounded conversation with Engel AI Main in Discord.

    Run this ON DESKTOP-UE5A6GG (or whichever machine runs the Sub-Engel bot), in an
    ordinary PowerShell window. It does not need admin unless you ask for -AtLogon.

.PARAMETER Token
    The Sub-Engel Discord bot token. If omitted the script keeps whatever token is
    already stored at <NodeRoot>\state\discord.env.

.PARAMETER NodeRoot
    Sub-Engel node root. Defaults to D:\EngelWindowsSubNode.

.PARAMETER AtLogon
    Also register a scheduled task so the worker starts at logon.

.EXAMPLE
    .\Install-SubEngelDiscordWorker.ps1 -Token "<the sub-engel bot token>"

.EXAMPLE
    .\Install-SubEngelDiscordWorker.ps1 -AtLogon
#>
[CmdletBinding()]
param(
    [string]$Token,
    [string]$NodeRoot = "D:\EngelWindowsSubNode",
    [switch]$AtLogon,
    [switch]$Yes
)

$ErrorActionPreference = "Stop"

function Say([string]$text) { Write-Host "[sub-engel] $text" }

$workerSource = Join-Path $PSScriptRoot "engel_sub_engel_discord_worker.py"
if (-not (Test-Path $workerSource)) {
    throw "engel_sub_engel_discord_worker.py must sit next to this script (looked in $PSScriptRoot)."
}

if (-not (Test-Path $NodeRoot)) {
    throw "Node root $NodeRoot does not exist. Pass -NodeRoot with the right path."
}

$stateDir = Join-Path $NodeRoot "state"
$binDir = Join-Path $NodeRoot "bin"
foreach ($dir in @($stateDir, $binDir)) {
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
}

# ---- 1. warn about the old stub still holding the bot session -----------------
Say "checking for an already-running Sub-Engel bot..."
$running = Get-CimInstance Win32_Process -Filter "Name like '%python%'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -and $_.CommandLine -match 'discord' }
if ($running) {
    Write-Warning "A Discord bot process is already running on this machine:"
    foreach ($proc in $running) {
        $line = $proc.CommandLine
        if ($line.Length -gt 160) { $line = $line.Substring(0, 160) + "..." }
        Write-Warning ("  PID {0}: {1}" -f $proc.ProcessId, $line)
    }
    Write-Warning "Two bots on the SAME token will both answer, or fight over the gateway session."
    Write-Warning "Stop the old one first:  Stop-Process -Id <PID>"
    $answer = "n"
    if ($Yes) {
        $answer = "y"
        Say " -Yes: stopping the existing Discord python process so this worker is the only mouth."
    } else {
        $answer = Read-Host "Stop those processes now? (y/N)"
    }
    if ($answer -match '^(y|yes)$') {
        foreach ($proc in $running) {
            try {
                Stop-Process -Id $proc.ProcessId -Force -ErrorAction Stop
                Say "stopped PID $($proc.ProcessId)"
            } catch {
                Write-Warning "could not stop PID $($proc.ProcessId): $($_.Exception.Message)"
            }
        }
    } else {
        Say "leaving them running - stop them yourself before starting the new worker."
    }
}

# ---- 2. find python ------------------------------------------------------------
$python = $null
foreach ($candidate in @("python", "py")) {
    $cmd = Get-Command $candidate -ErrorAction SilentlyContinue
    if ($cmd) { $python = $cmd.Source; break }
}
if (-not $python) { throw "No python found on PATH. Install Python 3.10+ and re-run." }
Say "using python: $python"

# ---- 3. install the worker ------------------------------------------------------
$workerTarget = Join-Path $binDir "engel_sub_engel_discord_worker.py"
Copy-Item $workerSource $workerTarget -Force
Say "installed worker -> $workerTarget"

# ---- 4. token ------------------------------------------------------------------
$envFile = Join-Path $stateDir "discord.env"
if ($Token) {
    # Written with restrictive ACLs; this file holds a bot token.
    Set-Content -Path $envFile -Value "SUB_ENGEL_DISCORD_BOT_TOKEN=$Token" -Encoding utf8
    try {
        $acl = Get-Acl $envFile
        $acl.SetAccessRuleProtection($true, $false)
        $rule = New-Object System.Security.AccessControl.FileSystemAccessRule(
            "$env:USERDOMAIN\$env:USERNAME", "FullControl", "Allow")
        $acl.SetAccessRule($rule)
        Set-Acl -Path $envFile -AclObject $acl
    } catch {
        Write-Warning "could not tighten ACLs on $envFile : $($_.Exception.Message)"
    }
    Say "token stored at $envFile (owner-only)"
} elseif (Test-Path $envFile) {
    Say "keeping the existing token at $envFile"
} else {
    Write-Warning "No token given and none stored. Re-run with -Token '<sub-engel bot token>'."
}

# ---- 5. dependency --------------------------------------------------------------
Say "checking discord.py..."
& $python -c "import discord" 2>$null
if ($LASTEXITCODE -ne 0) {
    Say "installing discord.py..."
    & $python -m pip install --quiet --upgrade "discord.py"
    if ($LASTEXITCODE -ne 0) { throw "pip install discord.py failed." }
}

# ---- 6. prove the gates before going live ---------------------------------------
Say "running offline selftest..."
& $python $workerTarget --selftest
if ($LASTEXITCODE -ne 0) { throw "selftest failed - not starting the worker." }

Say "node report:"
& $python $workerTarget --report

# ---- 7. launcher ----------------------------------------------------------------
$launcher = Join-Path $binDir "Start-SubEngelDiscordWorker.ps1"
$launcherBody = @"
`$env:SUB_ENGEL_NODE_STATE_DIR = "$stateDir"
`$env:SUB_ENGEL_DISCORD_CHANNEL_IDS = "1148755186752430163"
`$env:SUB_ENGEL_DISCORD_PEER_BOT_IDS = "1506157762785312808"
`$env:SUB_ENGEL_DISCORD_PEER_MAX_TURNS = "12"
& "$python" "$workerTarget"
"@
Set-Content -Path $launcher -Value $launcherBody -Encoding utf8
Say "launcher written -> $launcher"

if ($AtLogon) {
    $taskName = "EngelSubEngelDiscordWorker"
    $action = New-ScheduledTaskAction -Execute "powershell.exe" `
        -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$launcher`""
    $trigger = New-ScheduledTaskTrigger -AtLogOn
    try {
        Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
            -Description "Sub-Engel Discord worker (talks to Engel AI Main)" -Force | Out-Null
        Say "scheduled task '$taskName' registered (starts at logon)"
    } catch {
        Write-Warning "could not register the scheduled task: $($_.Exception.Message)"
        Write-Warning "Run this script from an elevated PowerShell if you want -AtLogon."
    }
}

Write-Host ""
if ($Yes) {
    Say "starting the worker now"
    powershell -NoProfile -ExecutionPolicy Bypass -File $launcher
} else {
    Say "done. Start it now with:"
    Write-Host "    powershell -NoProfile -ExecutionPolicy Bypass -File `"$launcher`"" -ForegroundColor Cyan
}
Write-Host ""
Say "then in Discord #general try:  @Sub-Engel status"
Say "and:  @Engel ask Sub-Engel what its pairing state is"
