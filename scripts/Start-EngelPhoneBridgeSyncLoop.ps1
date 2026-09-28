param(
    [string]$CtHost = "192.0.2.50",
    [int]$CtPort = 24622,
    [string]$CtUser = "root",
    [string]$KeyPath = (Join-Path $env:USERPROFILE ".ssh\engel_ai_main_ct246_ed25519"),
    [int]$IntervalSeconds = 60,
    [switch]$Once
)

$ErrorActionPreference = "Stop"

if ($IntervalSeconds -lt 15) {
    throw "IntervalSeconds must be at least 15."
}

$ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$ReconnectScript = Join-Path $ProjectRoot "tools\reconnect_engel_remote_workers.ps1"
$SyncScript = Join-Path $PSScriptRoot "Sync-EngelPhoneBridgeStateToMainCt.ps1"
$ResolvedKeyPath = [System.IO.Path]::GetFullPath($KeyPath)
$LogPath = Join-Path $env:LOCALAPPDATA "Engel AI Main\logs\phone-bridge-sync-loop.log"

function Write-LoopLog {
    param([string]$Message)
    $line = "{0} {1}" -f (Get-Date).ToUniversalTime().ToString("o"), $Message
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $LogPath) | Out-Null
    Add-Content -LiteralPath $LogPath -Value $line -Encoding UTF8
    Write-Host $line
}

foreach ($required in @($ReconnectScript, $SyncScript, $ResolvedKeyPath)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        throw "Required file missing: $required"
    }
}

$createdNew = $true
$mutex = $null
if (-not $Once) {
    $mutex = New-Object System.Threading.Mutex($true, "Local\EngelPhoneBridgeStateSyncLoop", [ref]$createdNew)
    if (-not $createdNew) {
        Write-LoopLog "Phone bridge sync loop is already running; exiting duplicate."
        exit 0
    }
}

try {
    do {
        try {
            Write-LoopLog "Refreshing local phone bridge state."
            & $ReconnectScript | ForEach-Object { Write-LoopLog ("reconnect: " + $_) }

            Write-LoopLog "Syncing phone bridge state to Engel AI Main CT 246."
            & $SyncScript -CtHost $CtHost -CtPort $CtPort -CtUser $CtUser -KeyPath $ResolvedKeyPath -SkipRemoteVerify |
                ForEach-Object { Write-LoopLog ("sync: " + $_) }
            Write-LoopLog "Phone bridge sync cycle complete."
        } catch {
            Write-LoopLog ("ERROR: " + $_.Exception.Message)
        }

        if ($Once) {
            break
        }
        Start-Sleep -Seconds $IntervalSeconds
    } while ($true)
}
finally {
    if ($mutex -ne $null) {
        if ($createdNew) {
            $mutex.ReleaseMutex()
        }
        $mutex.Dispose()
    }
}
