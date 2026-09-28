param(
    [string]$CtHost = "192.0.2.50",
    [int]$CtPort = 24622,
    [string]$CtUser = "root",
    [string]$RuntimeRoot = "/opt/engel",
    [string]$KeyPath = (Join-Path $env:USERPROFILE ".ssh\engel_ai_main_ct246_ed25519"),
    [int]$OfficeLocalPort = 3000,
    [switch]$SkipConnectionTest,
    [switch]$ForceNewApp,
    [switch]$NoLaunchApp,
    # Continuous phone-worker reconnect is opt-in.  The previous default
    # started a hidden 60-second loop on every one-system launch, creating
    # duplicate reconnect cycles and a new report log every minute.
    [switch]$EnablePhoneBridgeSync
)

$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$TunnelScript = Join-Path $PSScriptRoot "Start-EngelMainServerChatTunnelPersistent.ps1"
$PhoneBridgeSyncLoop = Join-Path $PSScriptRoot "Start-EngelPhoneBridgeSyncLoop.ps1"
$MergedLauncher = Join-Path $PSScriptRoot "Start-EngelMainServerMerged.ps1"
$ConnectionTest = Join-Path $PSScriptRoot "Test-EngelMainOneSystemConnections.ps1"
$ResolvedKeyPath = [System.IO.Path]::GetFullPath($KeyPath)

function Test-HealthOk {
    param([string]$Url)
    try {
        $payload = Invoke-RestMethod -Uri $Url -TimeoutSec 4
        return [bool]($payload.ok -eq $true)
    } catch {
        return $false
    }
}

function Wait-HealthOk {
    param([string]$Url, [int]$Seconds = 18)
    $deadline = (Get-Date).AddSeconds($Seconds)
    do {
        if (Test-HealthOk $Url) { return $true }
        Start-Sleep -Seconds 2
    } while ((Get-Date) -lt $deadline)
    return $false
}

if (-not (Test-Path -LiteralPath $ResolvedKeyPath -PathType Leaf)) {
    throw "Engel CT SSH key is missing: $ResolvedKeyPath. Run scripts\Install-EngelMainPersistentAgenticSystem.ps1 once."
}
if ($EnablePhoneBridgeSync -and -not (Test-Path -LiteralPath $PhoneBridgeSyncLoop -PathType Leaf)) {
    throw "Engel phone bridge sync loop is missing: $PhoneBridgeSyncLoop"
}

$chatOk = Test-HealthOk "http://127.0.0.1:24680/health"
$meetingOk = Test-HealthOk "http://127.0.0.1:8790/health"
$officeOk = Test-HealthOk "http://127.0.0.1:$OfficeLocalPort/api/health"
if (-not ($chatOk -and $meetingOk -and $officeOk)) {
    $task = Get-ScheduledTask -TaskName "EngelMainServerPersistentLink" -ErrorAction SilentlyContinue
    if ($null -ne $task) {
        Start-ScheduledTask -TaskName "EngelMainServerPersistentLink" -ErrorAction SilentlyContinue
    }
    $args = @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", "`"$TunnelScript`"",
        "-CtHost", "`"$CtHost`"",
        "-CtPort", [string]$CtPort,
        "-CtUser", "`"$CtUser`"",
        "-KeyPath", "`"$ResolvedKeyPath`"",
        "-OfficeLocalPort", [string]$OfficeLocalPort
    ) -join " "
    Start-Process -FilePath "powershell.exe" -ArgumentList $args -WindowStyle Hidden
    [void](Wait-HealthOk "http://127.0.0.1:24680/health" -Seconds 18)
    [void](Wait-HealthOk "http://127.0.0.1:8790/health" -Seconds 18)
    [void](Wait-HealthOk "http://127.0.0.1:$OfficeLocalPort/api/health" -Seconds 18)
}

if ($EnablePhoneBridgeSync) {
    $phoneSyncArgs = @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", "`"$PhoneBridgeSyncLoop`"",
        "-CtHost", "`"$CtHost`"",
        "-CtPort", [string]$CtPort,
        "-CtUser", "`"$CtUser`"",
        "-KeyPath", "`"$ResolvedKeyPath`"",
        "-IntervalSeconds", "60"
    ) -join " "
    Start-Process -FilePath "powershell.exe" -ArgumentList $phoneSyncArgs -WindowStyle Hidden
} else {
    Write-Host "Phone bridge reconnect loop not started (opt-in: -EnablePhoneBridgeSync)."
}

if (-not $SkipConnectionTest) {
    & $ConnectionTest -CtHost $CtHost -CtPort $CtPort -CtUser $CtUser -RuntimeRoot $RuntimeRoot -KeyPath $ResolvedKeyPath -NoExitCode
}

if (-not $NoLaunchApp) {
    if ($ForceNewApp) {
        & $MergedLauncher -CtHost $CtHost -CtPort $CtPort -CtUser $CtUser -RuntimeRoot $RuntimeRoot -NoProbe -ForceNew
    } else {
        & $MergedLauncher -CtHost $CtHost -CtPort $CtPort -CtUser $CtUser -RuntimeRoot $RuntimeRoot -NoProbe
    }
}
