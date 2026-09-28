param(
    [string]$HostAddress = "127.0.0.1",
    [int]$Port = 8790,
    [string]$ServerRoot = "",
    [switch]$Foreground
)

$ErrorActionPreference = "Stop"

$AppRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Python = Join-Path $AppRoot "runtime\python310\python.exe"
$ServerScript = Join-Path $AppRoot "tools\engel_meeting_room_lan_server.py"
$ReportDir = Join-Path $AppRoot "reports\meeting_room_server"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python runtime not found: $Python"
}
if (-not (Test-Path -LiteralPath $ServerScript)) {
    throw "Meeting Room server script not found: $ServerScript"
}

if ([string]::IsNullOrWhiteSpace($ServerRoot)) {
    $ServerRoot = Join-Path $AppRoot "runtime\meeting_room_server"
}
$ResolvedServerRoot = [System.IO.Path]::GetFullPath($ServerRoot)
if ($ResolvedServerRoot.StartsWith("C:\", [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to store Engel Meeting Room server state on C:. Use the project runtime path or CT246 fast SSD /opt/engel/run."
}

New-Item -ItemType Directory -Force -Path $ResolvedServerRoot | Out-Null
New-Item -ItemType Directory -Force -Path $ReportDir | Out-Null

$HealthUrl = "http://127.0.0.1:$Port/health"
try {
    $ExistingHealth = Invoke-RestMethod -Uri $HealthUrl -TimeoutSec 3
    if ($ExistingHealth.ok -eq $true -or $ExistingHealth.status -eq "running") {
        [pscustomobject]@{
            ok = $true
            already_running = $true
            url = "http://${HostAddress}:$Port"
            health_url = $HealthUrl
            status = $ExistingHealth.status
            server_root = $ExistingHealth.server_root
            app_root = $AppRoot
            c_drive_used = $false
        } | ConvertTo-Json -Depth 4
        exit 0
    }
} catch {
    # Not running yet; continue into normal startup.
}

$env:ENGEL_MEETING_ROOM_SERVER_ROOT = $ResolvedServerRoot
$env:ENGEL_MEETING_ROOM_SERVER_HOST = $HostAddress
$env:ENGEL_MEETING_ROOM_SERVER_PORT = [string]$Port

$ArgsList = @(
    "tools\engel_meeting_room_lan_server.py",
    "--host", $HostAddress,
    "--port", [string]$Port,
    "--startup-event"
)

if ($Foreground) {
    & $Python @ArgsList
    exit $LASTEXITCODE
}

$Out = Join-Path $ReportDir "meeting_room_lan_server_stdout.log"
$Err = Join-Path $ReportDir "meeting_room_lan_server_stderr.log"
$Process = Start-Process -FilePath $Python `
    -ArgumentList $ArgsList `
    -WorkingDirectory $AppRoot `
    -RedirectStandardOutput $Out `
    -RedirectStandardError $Err `
    -WindowStyle Hidden `
    -PassThru

Start-Sleep -Seconds 2
$Health = Invoke-RestMethod -Uri $HealthUrl -TimeoutSec 10

[pscustomobject]@{
    ok = $true
    pid = $Process.Id
    url = "http://${HostAddress}:$Port"
    health_url = $HealthUrl
    status = $Health.status
    server_root = $ResolvedServerRoot
    app_root = $AppRoot
    stdout = $Out
    stderr = $Err
    c_drive_used = $false
} | ConvertTo-Json -Depth 4
