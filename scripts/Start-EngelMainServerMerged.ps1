param(
    [string]$CtHost = "192.0.2.50",
    [int]$CtPort = 24622,
    [string]$CtUser = "root",
    [string]$RuntimeRoot = "/opt/engel",
    [switch]$NoProbe,
    [switch]$ForceNew,
    [switch]$AllowDuplicate
)

$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$ExePath = Join-Path $ProjectRoot "engel_flutter_main\build\windows\x64\runner\Release\EngelAIMain.exe"
if (-not (Test-Path -LiteralPath $ExePath -PathType Leaf)) {
    throw "Engel AI Main release executable was not found: $ExePath"
}

$existing = @(Get-Process -Name "EngelAIMain" -ErrorAction SilentlyContinue)
if ($existing.Count -gt 0) {
    if ($AllowDuplicate) {
        Write-Warning "Launching a duplicate Engel AI Main window because -AllowDuplicate was supplied."
        Write-Warning "Existing process IDs: $($existing.Id -join ', ')"
    } elseif ($ForceNew) {
        Write-Host "Restarting Engel AI Main cleanly; stopping existing process IDs: $($existing.Id -join ', ')"
        $existing | Stop-Process -Force -ErrorAction SilentlyContinue
        $deadline = (Get-Date).AddSeconds(12)
        do {
            Start-Sleep -Milliseconds 250
            $remaining = @(Get-Process -Name "EngelAIMain" -ErrorAction SilentlyContinue)
        } while ($remaining.Count -gt 0 -and (Get-Date) -lt $deadline)
        if ($remaining.Count -gt 0) {
            throw "Could not stop existing Engel AI Main processes: $($remaining.Id -join ', ')"
        }
    } else {
        Write-Host "Engel AI Main is already running; not launching a duplicate process."
        Write-Host "Running process IDs: $($existing.Id -join ', ')"
        Write-Host "Use -ForceNew to restart the current Engel window, or -AllowDuplicate only for isolated testing."
        return
    }
}

if ($CtHost -notmatch "^[A-Za-z0-9_.-]+$") {
    throw "CtHost contains unsupported characters: $CtHost"
}
if ($CtUser -notmatch "^[A-Za-z_][A-Za-z0-9_-]*$") {
    throw "CtUser contains unsupported characters: $CtUser"
}
if ($CtPort -lt 1 -or $CtPort -gt 65535) {
    throw "CtPort must be a TCP port from 1 to 65535."
}

if (-not $NoProbe) {
    $reachable = Test-NetConnection -ComputerName $CtHost -Port $CtPort -InformationLevel Quiet -WarningAction SilentlyContinue
    if (-not $reachable) {
        Write-Warning "CT 246 SSH route did not answer on ${CtHost}:${CtPort}. Starting UI anyway with server merge environment."
    }
}

$old = @{}
foreach ($key in @(
    "ENGEL_MAIN_SERVER_ENABLED",
    "ENGEL_MAIN_SERVER_HOST",
    "ENGEL_MAIN_SERVER_SSH_PORT",
    "ENGEL_MAIN_SERVER_SSH_USER",
    "ENGEL_MAIN_SERVER_RUNTIME_ROOT",
    "ENGEL_MAIN_SERVER_CT_ID",
    "ENGEL_MAIN_SERVER_CT_HOSTNAME",
    "ENGEL_MAIN_SERVER_CHAT_URL",
    "ENGEL_MAIN_SERVER_CHAT_REQUIRED",
    "ENGEL_MAIN_ALLOW_LAPTOP_LOCAL_FALLBACK",
    "ENGEL_MEETING_ROOM_SERVER_URL",
    "ENGEL_STANDALONE_CHAT_PROVIDER"
)) {
    $old[$key] = [Environment]::GetEnvironmentVariable($key, "Process")
}

try {
    $env:ENGEL_MAIN_SERVER_ENABLED = "1"
    $env:ENGEL_MAIN_SERVER_HOST = $CtHost
    $env:ENGEL_MAIN_SERVER_SSH_PORT = [string]$CtPort
    $env:ENGEL_MAIN_SERVER_SSH_USER = $CtUser
    $env:ENGEL_MAIN_SERVER_RUNTIME_ROOT = $RuntimeRoot
    $env:ENGEL_MAIN_SERVER_CT_ID = "246"
    $env:ENGEL_MAIN_SERVER_CT_HOSTNAME = "engel-ai-main"
    $env:ENGEL_MAIN_SERVER_CHAT_URL = "http://127.0.0.1:24680"
    $env:ENGEL_MAIN_SERVER_CHAT_REQUIRED = "1"
    $env:ENGEL_MAIN_ALLOW_LAPTOP_LOCAL_FALLBACK = "0"
    $env:ENGEL_MEETING_ROOM_SERVER_URL = "http://127.0.0.1:8790"
    if (-not $env:ENGEL_STANDALONE_CHAT_PROVIDER) {
        $env:ENGEL_STANDALONE_CHAT_PROVIDER = "local"
    }

    Start-Process -FilePath $ExePath -WorkingDirectory (Split-Path -Parent $ExePath)
    Write-Host "Started Engel AI Main with server merge environment."
    Write-Host "Server peer: ${CtUser}@${CtHost}:${CtPort}"
    Write-Host "Runtime root: $RuntimeRoot"
    Write-Host "Chat URL: http://127.0.0.1:24680"
    Write-Host "Agent Meeting Room URL: http://127.0.0.1:8790"
    Write-Host "Laptop local fallback: disabled unless ENGEL_MAIN_SERVER_CHAT_REQUIRED=0"
}
finally {
    foreach ($entry in $old.GetEnumerator()) {
        if ($null -eq $entry.Value) {
            Remove-Item -Path ("Env:\" + $entry.Key) -ErrorAction SilentlyContinue
        } else {
            Set-Item -Path ("Env:\" + $entry.Key) -Value $entry.Value
        }
    }
}
