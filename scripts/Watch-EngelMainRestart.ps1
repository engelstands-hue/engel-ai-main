<#
.SYNOPSIS
  Persistent watcher: run Connect-EngelAllDevices.ps1 whenever Engel AI Main
  (EngelAIMain.exe) starts or restarts on the ROG.

.DESCRIPTION
  Polls for the EngelAIMain.exe PID every few seconds. A NEW pid (first
  appearance, or a different pid than last seen = a restart) triggers a full
  connect-all pass after a short grace period so the app + tunnel can finish
  initializing. Single-instance via a named mutex. Logs every trigger.

  Register at logon so it survives reboots:
    Register-EngelConnectAllOnRestart.ps1   (companion script)
#>
param(
    [int]$PollSeconds = 5,
    [int]$GraceSeconds = 8,
    [switch]$RunOnceIfPresent   # for testing: fire once now if app is up, then exit
)

$ErrorActionPreference = "Continue"
$ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$ConnectScript = Join-Path $ProjectRoot "scripts\Connect-EngelAllDevices.ps1"
$LogDir = Join-Path $env:LOCALAPPDATA "Engel AI Main\logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$LogPath = Join-Path $LogDir "connect-all-watch.log"

function Write-WatchLog {
    param([string]$Message)
    $line = "{0}  {1}" -f ([DateTime]::UtcNow.ToString("s") + "Z"), $Message
    Add-Content -LiteralPath $LogPath -Value $line -Encoding UTF8
    Write-Host $line
}

function Invoke-ConnectAll {
    param([string]$TriggerReason)
    Write-WatchLog "Engel Main $TriggerReason -> connect-all in ${GraceSeconds}s grace"
    Start-Sleep -Seconds $GraceSeconds
    $env:ENGEL_CONNECT_ALL_TRIGGER = $TriggerReason
    try {
        & powershell -NoProfile -ExecutionPolicy Bypass -File $ConnectScript -Quiet *>$null
        $latest = Join-Path $ProjectRoot "reports\connect_all\ENGEL_CONNECT_ALL_LATEST.json"
        if (Test-Path -LiteralPath $latest) {
            $r = Get-Content -Raw -LiteralPath $latest | ConvertFrom-Json
            Write-WatchLog ("connect-all done: connected {0}/{1}; flagged {2} [{3}]" -f $r.connected, $r.total, $r.flagged_count, ($r.flagged -join '; '))
        } else {
            Write-WatchLog "connect-all ran but no receipt found"
        }
    } catch {
        Write-WatchLog "connect-all FAILED to launch: $($_.Exception.Message)"
    }
}

function Get-EngelMainPid {
    $p = Get-Process EngelAIMain -ErrorAction SilentlyContinue | Sort-Object StartTime | Select-Object -First 1
    if ($p) { return $p.Id } else { return $null }
}

if ($RunOnceIfPresent) {
    $curPid = Get-EngelMainPid
    if ($curPid) { Invoke-ConnectAll -TriggerReason "run-once-test (pid $curPid)" }
    else { Write-WatchLog "run-once: EngelAIMain not running, nothing to do" }
    return
}

# Single-instance guard
$createdNew = $false
$mutex = New-Object System.Threading.Mutex($true, "Local\EngelConnectAllRestartWatcher", [ref]$createdNew)
if (-not $createdNew) { Write-WatchLog "watcher already running; exiting duplicate"; return }

Write-WatchLog "Engel connect-all restart watcher started (poll ${PollSeconds}s, grace ${GraceSeconds}s)"
$lastPid = $null
try {
    while ($true) {
        $curPid = Get-EngelMainPid
        if ($curPid -and $curPid -ne $lastPid) {
            $reason = if ($null -eq $lastPid) { "detected (pid $curPid)" } else { "restart (pid $lastPid -> $curPid)" }
            Invoke-ConnectAll -TriggerReason $reason
        }
        $lastPid = $curPid
        Start-Sleep -Seconds $PollSeconds
    }
} finally {
    if ($createdNew) { $mutex.ReleaseMutex() }
    $mutex.Dispose()
}
