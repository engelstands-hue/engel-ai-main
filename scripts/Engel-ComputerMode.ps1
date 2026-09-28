<#
.SYNOPSIS
  Toggle this ROG laptop between Clean (free the PC) and Regular (Engel stack on).

.DESCRIPTION
  Clean mode stops Engel backends/watchdogs/tunnels, pauses Engel scheduled tasks that
  would revive them, and optionally stops vendor bloat services (ASUS/Razer helpers).
  Regular mode restores the saved task/service states and starts the One System tunnel.

  Does NOT stop: Windows Explorer, DWM, Defender, NVIDIA display stack, Cursor, or
  other apps you are actively using.

.PARAMETER Mode
  clean | regular | toggle | status
#>
[CmdletBinding()]
param(
    [ValidateSet("clean", "regular", "toggle", "status")]
    [string]$Mode = "toggle",
    [bool]$IncludeVendorBloat = $true,
    [bool]$IncludeSurvivalDesk = $true,
    [bool]$IncludeWindowsExtras = $true,
    [switch]$NoPause,
    [switch]$Quiet
)

$ErrorActionPreference = "Continue"
$ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$StateDir = Join-Path $ProjectRoot "runtime\computer_mode"
$StatePath = Join-Path $StateDir "state.json"
$ReceiptDir = Join-Path $ProjectRoot "reports\computer_mode"
$EngelAiRs = Join-Path $ProjectRoot "rust\engel-core-rs\target\debug\engel-ai-rs.exe"
$OneSystem = Join-Path $PSScriptRoot "Start-EngelMainOneSystem.ps1"

$EngelTasksToPause = @(
    "EngelChatLinkSvc",
    "EngelConnectAllOnMainRestart",
    "EngelGpuTunnelSvc",
    "EngelChatGptBrowserBridge",
    "EngelCodexCliBridge",
    "EngelGeminiApiBridge",
    "EngelGrokHeadlessBroker",
    "EngelGrokImagineService",
    "EngelModelExpressServer",
    "EngelRogGpuImageServer",
    "EngelRogGpuModelServer",
    "Engel AI Main One Day Local First Chat Training"
)

$VendorServices = @(
    # ASUS / Armoury / Aura / GlideX
    "ArmouryCrateService",
    "ArmouryCrateControlInterface",
    "AsusAppService",
    "ASUSOptimization",
    "ASUSSoftwareManager",
    "ASUSSwitch",
    "ASUSSystemAnalysis",
    "ASUSSystemDiagnosis",
    "AsusCertService",
    "AsusPTPService",
    "AsHidCtrlService",
    "asus",
    "AsusMultiAntennaSvc",
    "LightingService",
    "ROG Live Service",
    "Aura Wallpaper Service",
    "GameSDK Service",
    "GlideXService",
    "GlideXServiceExt",
    "GlideXNearService",
    "GlideXRemoteService",
    "RefreshRateService",
    "NahimicService",
    # Razer
    "Razer Game Manager Service 3",
    "Razer Update Service",
    # Leftover / unused helpers
    "SMmonitor",                 # Dell Modular Disk monitor (not needed on this ROG)
    "FlexNet Licensing Service"  # Macrovision license helper
)

# User-mode processes that stay alive even after some services stop
$VendorProcessNames = @(
    "asus_framework",
    "asusns",
    "ASUS_FRQ_Control",
    "AcPowerNotification",
    "ArmouryCrate",
    "ArmourySwAgent",
    "ArmourySocketServer",
    "ArmouryHtmlDebugServer",
    "AuraWallpaperService",
    "GameSDK",
    "GlideXService",
    "GlideXServiceExt",
    "GlideXNearService",
    "GlideXRemoteService",
    "NahimicService",
    "NahimicSvc32",
    "NahimicSvc64",
    "RefreshRateService",
    "SDXHelper",
    "SMmonitor",
    "OneApp.IGCC.WinService",
    "Virtual Pet",
    "RZSurroundHelper",
    "adb"
)

# Optional Windows extras that are nice-to-have, not required to use the PC
$WindowsExtraServices = @(
    "GamingServices",
    "GamingServicesNet",
    "ClickToRunSvc"   # Office background click-to-run
)

$WindowsExtraProcessNames = @(
    "Widgets",
    "WidgetService",
    "CrossDeviceService",
    "CrossDeviceResume",
    "PhoneExperienceHost",
    "GameBar",
    "GameBarFTServer",
    "XboxPcAppFT"
)

# HKCU/HKLM Run values to pause in Clean (saved + restored in Regular)
$AutorunPauseNames = @(
    "Steam",
    "Virtual Pet",
    "EngelAIControlRoom",
    "GoogleDriveFS",
    "RZSurroundHelper"
)

function Write-Info([string]$Message) {
    if (-not $Quiet) { Write-Host $Message }
}

function Ensure-Dir([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) {
        New-Item -ItemType Directory -Path $Path -Force | Out-Null
    }
}

function Test-IsAdmin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($id)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Get-MemorySnapshot {
    $os = Get-CimInstance Win32_OperatingSystem
    $total = [math]::Round($os.TotalVisibleMemorySize / 1MB, 1)
    $free = [math]::Round($os.FreePhysicalMemory / 1MB, 1)
    $used = [math]::Round($total - $free, 1)
    return [pscustomobject]@{
        total_gb = $total
        used_gb = $used
        free_gb = $free
        used_pct = [math]::Round(($used / [math]::Max($total, 0.1)) * 100, 0)
    }
}

function Get-ProcessHits {
    $hits = @()
    Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | ForEach-Object {
        $cmd = [string]$_.CommandLine
        $name = [string]$_.Name
        $match = $false
        if ($name -match '^(engel-ai-rs|llama-server|llama_cpp)\.exe$') { $match = $true }
        if ($cmd -match 'Engel App\\scripts\\Start-Engel|engel_ai_main_ct246|lan-receiver serve|watch-android-link|watch-auto-pair|serve-bootstrap') { $match = $true }
        if ($IncludeSurvivalDesk -and $cmd -match 'Engel-Survival\\.*server\.mjs') { $match = $true }
        if ($match) {
            $short = $cmd
            if ($short.Length -gt 160) { $short = $short.Substring(0, 160) + "..." }
            $hits += [pscustomobject]@{
                pid = $_.ProcessId
                name = $name
                cmd = $short
            }
        }
    }
    return $hits
}

function Read-State {
    if (-not (Test-Path -LiteralPath $StatePath)) {
        return [pscustomobject]@{
            mode = "regular"
            saved_task_states = @{}
            saved_service_states = @{}
            updated_at_utc = $null
        }
    }
    return (Get-Content -LiteralPath $StatePath -Raw | ConvertFrom-Json)
}

function Write-State($State) {
    Ensure-Dir $StateDir
    $State.updated_at_utc = [DateTime]::UtcNow.ToString("o")
    ($State | ConvertTo-Json -Depth 8) | Set-Content -LiteralPath $StatePath -Encoding UTF8
}

function Write-Receipt([string]$Action, $Payload) {
    Ensure-Dir $ReceiptDir
    $stamp = Get-Date -Format "yyyyMMddTHHmmss"
    $path = Join-Path $ReceiptDir ("COMPUTER_MODE_{0}_{1}.md" -f $stamp, $Action)
    $utc = [DateTime]::UtcNow.ToString("o")
    $admin = Test-IsAdmin
    $json = ($Payload | ConvertTo-Json -Depth 8)
    $content = @"
# Engel Computer Mode - $Action

- utc: $utc
- mode_requested: $Mode
- admin: $admin
- include_vendor_bloat: $IncludeVendorBloat
- include_survival_desk: $IncludeSurvivalDesk

``````json
$json
``````
"@
    Set-Content -LiteralPath $path -Value $content -Encoding UTF8
    return $path
}

function Stop-EngelBackends {
    $stopped = @()
    if (Test-Path -LiteralPath $EngelAiRs) {
        try {
            & $EngelAiRs lan-link disable-auto-worker 2>$null | Out-Null
            & $EngelAiRs lan-link stop --approve APPROVE_REMOTE_WORKER_LINK_PROCESS_CONTROL 2>$null | Out-Null
            $stopped += "lan-link stop approved"
        } catch {
            $stopped += ("lan-link stop error: {0}" -f $_.Exception.Message)
        }
    }

    Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | ForEach-Object {
        $cmd = [string]$_.CommandLine
        $name = [string]$_.Name
        $kill = $false
        if ($name -match '^(engel-ai-rs|llama-server)\.exe$') { $kill = $true }
        if ($cmd -match 'Start-EngelMainServerChatTunnelPersistent|Start-EngelRogGpuTunnelPersistent|Start-EngelPhoneBridgeSyncLoop') { $kill = $true }
        if ($cmd -match 'engel_ai_main_ct246_ed25519') { $kill = $true }
        if ($cmd -match 'lan-receiver serve|watch-android-link|watch-auto-pair|serve-bootstrap') { $kill = $true }
        if ($IncludeSurvivalDesk -and $cmd -match 'Engel-Survival\\.*server\.mjs') { $kill = $true }
        if ($kill) {
            try {
                Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop
                $stopped += ("killed pid {0} ({1})" -f $_.ProcessId, $name)
            } catch {
                $stopped += ("kill failed pid {0}: {1}" -f $_.ProcessId, $_.Exception.Message)
            }
        }
    }
    return $stopped
}

function Pause-EngelTasks($State) {
    $saved = @{}
    if ($State.saved_task_states) {
        $State.saved_task_states.PSObject.Properties | ForEach-Object { $saved[$_.Name] = $_.Value }
    }
    $changed = @()
    $taskNames = @($EngelTasksToPause)
    if ($IncludeSurvivalDesk) { $taskNames += "EngelSurvivalDesk" }
    foreach ($name in $taskNames) {
        $task = Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
        if ($null -eq $task) { continue }
        if (-not $saved.ContainsKey($name)) {
            $saved[$name] = [string]$task.State
        }
        try {
            if ($task.State -eq "Running") {
                Stop-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
            }
            Disable-ScheduledTask -TaskName $name -ErrorAction Stop | Out-Null
            $changed += ("disabled {0} (was {1})" -f $name, $saved[$name])
        } catch {
            $changed += ("task {0}: {1}" -f $name, $_.Exception.Message)
        }
    }
    $State.saved_task_states = $saved
    return $changed
}

function Restore-EngelTasks($State) {
    $changed = @()
    $saved = @{}
    if ($State.saved_task_states) {
        $State.saved_task_states.PSObject.Properties | ForEach-Object { $saved[$_.Name] = [string]$_.Value }
    }
    foreach ($name in $saved.Keys) {
        $prev = [string]$saved[$name]
        $task = Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
        if ($null -eq $task) {
            $changed += ("missing task {0}" -f $name)
            continue
        }
        try {
            if ($prev -ne "Disabled") {
                Enable-ScheduledTask -TaskName $name -ErrorAction Stop | Out-Null
                $changed += ("enabled {0}" -f $name)
            } else {
                Disable-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue | Out-Null
                $changed += ("kept disabled {0}" -f $name)
            }
        } catch {
            $changed += ("restore {0}: {1}" -f $name, $_.Exception.Message)
        }
    }
    return $changed
}

function Stop-NamedProcesses([string[]]$Names) {
    $stopped = @()
    foreach ($name in $Names) {
        Get-Process -Name $name -ErrorAction SilentlyContinue | ForEach-Object {
            try {
                Stop-Process -Id $_.Id -Force -ErrorAction Stop
                $stopped += ("killed {0} pid {1}" -f $name, $_.Id)
            } catch {
                $stopped += ("kill failed {0} pid {1}: {2}" -f $name, $_.Id, $_.Exception.Message)
            }
        }
    }
    return $stopped
}

function Stop-ServiceList([string[]]$Names, $State, [string]$Bucket) {
    $changed = @()
    if (-not (Test-IsAdmin)) {
        $changed += ("{0} skipped (not elevated)" -f $Bucket)
        return $changed
    }
    $saved = @{}
    $prop = "saved_service_states"
    if ($State.$prop) {
        $State.$prop.PSObject.Properties | ForEach-Object { $saved[$_.Name] = $_.Value }
    }
    foreach ($name in $Names) {
        $svc = Get-Service -Name $name -ErrorAction SilentlyContinue
        if ($null -eq $svc) { continue }
        if (-not $saved.ContainsKey($name)) {
            $saved[$name] = [pscustomobject]@{
                status = [string]$svc.Status
                start_type = [string]$svc.StartType
                bucket = $Bucket
            }
        }
        try {
            if ($svc.Status -eq "Running") {
                Stop-Service -Name $name -Force -ErrorAction Stop
                $changed += ("stopped service {0}" -f $name)
            }
        } catch {
            $changed += ("service {0} stop: {1}" -f $name, $_.Exception.Message)
        }
    }
    $State.$prop = $saved
    return $changed
}

function Pause-Autoruns($State) {
    $changed = @()
    $saved = @{}
    if ($State.saved_autoruns) {
        $State.saved_autoruns.PSObject.Properties | ForEach-Object { $saved[$_.Name] = $_.Value }
    }
    $roots = @(
        "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run",
        "HKLM:\Software\Microsoft\Windows\CurrentVersion\Run"
    )
    foreach ($root in $roots) {
        if (-not (Test-Path $root)) { continue }
        foreach ($name in $AutorunPauseNames) {
            try {
                $item = Get-ItemProperty -Path $root -Name $name -ErrorAction SilentlyContinue
                if ($null -eq $item) { continue }
                $value = [string]($item.$name)
                if ([string]::IsNullOrWhiteSpace($value)) { continue }
                $key = "{0}|{1}" -f $root, $name
                if (-not $saved.ContainsKey($key)) {
                    $saved[$key] = $value
                }
                if ($root -like "HKLM:*" -and -not (Test-IsAdmin)) {
                    $changed += ("autorun {0} needs admin to pause" -f $name)
                    continue
                }
                Remove-ItemProperty -Path $root -Name $name -ErrorAction Stop
                $changed += ("paused autorun {0}" -f $name)
            } catch {
                $changed += ("autorun {0}: {1}" -f $name, $_.Exception.Message)
            }
        }
    }
    # Playwright chromium auto-launch left by Engel tooling (name varies)
    $hkcu = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
    if (Test-Path $hkcu) {
        Get-Item $hkcu | Select-Object -ExpandProperty Property | Where-Object { $_ -like "GoogleChromeAutoLaunch_*" } | ForEach-Object {
            $name = $_
            try {
                $value = [string](Get-ItemProperty -Path $hkcu -Name $name).$name
                $key = "{0}|{1}" -f $hkcu, $name
                if (-not $saved.ContainsKey($key)) { $saved[$key] = $value }
                Remove-ItemProperty -Path $hkcu -Name $name -ErrorAction Stop
                $changed += ("paused autorun {0}" -f $name)
            } catch {
                $changed += ("autorun {0}: {1}" -f $name, $_.Exception.Message)
            }
        }
    }
    $State.saved_autoruns = $saved
    return $changed
}

function Restore-Autoruns($State) {
    $changed = @()
    if (-not $State.saved_autoruns) { return $changed }
    $State.saved_autoruns.PSObject.Properties | ForEach-Object {
        $key = $_.Name
        $value = [string]$_.Value
        $parts = $key.Split("|", 2)
        if ($parts.Count -ne 2) { return }
        $root = $parts[0]
        $name = $parts[1]
        try {
            if ($root -like "HKLM:*" -and -not (Test-IsAdmin)) {
                $changed += ("autorun restore {0} needs admin" -f $name)
                return
            }
            if (-not (Test-Path $root)) { return }
            Set-ItemProperty -Path $root -Name $name -Value $value -ErrorAction Stop
            $changed += ("restored autorun {0}" -f $name)
        } catch {
            $changed += ("autorun restore {0}: {1}" -f $name, $_.Exception.Message)
        }
    }
    return $changed
}

function Stop-VendorBloat($State) {
    $changed = @()
    if (-not $IncludeVendorBloat) { return $changed }
    $changed += Stop-ServiceList -Names $VendorServices -State $State -Bucket "vendor"
    $changed += Stop-NamedProcesses -Names $VendorProcessNames
    if (-not (Test-IsAdmin)) {
        $changed += "vendor services need Administrator - desktop Clean shortcut will elevate"
    }
    return $changed
}

function Stop-WindowsExtras($State) {
    $changed = @()
    if (-not $IncludeWindowsExtras) { return $changed }
    $changed += Stop-ServiceList -Names $WindowsExtraServices -State $State -Bucket "windows_extra"
    $changed += Stop-NamedProcesses -Names $WindowsExtraProcessNames
    return $changed
}

function Restore-VendorBloat($State) {
    $changed = @()
    if (-not $IncludeVendorBloat) { return $changed }
    if (-not (Test-IsAdmin)) {
        $changed += "vendor restore skipped (not elevated)"
        return $changed
    }
    if (-not $State.saved_service_states) { return $changed }
    $State.saved_service_states.PSObject.Properties | ForEach-Object {
        $name = $_.Name
        $prev = $_.Value
        $svc = Get-Service -Name $name -ErrorAction SilentlyContinue
        if ($null -eq $svc) {
            $changed += ("missing service {0}" -f $name)
            return
        }
        $wantRunning = $false
        if ($prev.status -eq "Running") { $wantRunning = $true }
        if ($prev.Status -eq "Running") { $wantRunning = $true }
        try {
            if ($wantRunning) {
                Start-Service -Name $name -ErrorAction Stop
                $changed += ("started service {0}" -f $name)
            }
        } catch {
            $changed += ("service {0} start: {1}" -f $name, $_.Exception.Message)
        }
    }
    return $changed
}

function Invoke-Clean {
    $state = Read-State
    $memBefore = Get-MemorySnapshot
    $taskChanges = Pause-EngelTasks $state
    $procChanges = Stop-EngelBackends
    $svcChanges = @()
    $svcChanges += Stop-VendorBloat $state
    $svcChanges += Stop-WindowsExtras $state
    $autorunChanges = Pause-Autoruns $state
    # Second pass: kill leftover vendor processes after services stop
    if ($IncludeVendorBloat) {
        Start-Sleep -Milliseconds 500
        $procChanges += Stop-NamedProcesses -Names $VendorProcessNames
    }
    Start-Sleep -Seconds 1
    $state.mode = "clean"
    Write-State $state
    $memAfter = Get-MemorySnapshot
    $payload = [pscustomobject]@{
        mode = "clean"
        memory_before = $memBefore
        memory_after = $memAfter
        tasks = $taskChanges
        processes = $procChanges
        services = $svcChanges
        autoruns = $autorunChanges
        remaining_hits = @(Get-ProcessHits)
    }
    $receipt = Write-Receipt "clean" $payload
    Write-Info "CLEAN mode on - Engel backends + vendor bloat paused."
    Write-Info ("Memory now: {0} GB used / {1} GB total ({2} pct); free {3} GB" -f `
        $memAfter.used_gb, $memAfter.total_gb, $memAfter.used_pct, $memAfter.free_gb)
    Write-Info ("Receipt: {0}" -f $receipt)
    if (-not (Test-IsAdmin)) {
        Write-Info "Tip: approve UAC on the Clean shortcut so ASUS/GlideX/Nahimic services actually stop."
    }
    return $payload
}

function Invoke-Regular {
    $state = Read-State
    $memBefore = Get-MemorySnapshot
    $taskChanges = Restore-EngelTasks $state
    $svcChanges = Restore-VendorBloat $state
    $autorunChanges = Restore-Autoruns $state

    $started = @()
    $chatLink = Get-ScheduledTask -TaskName "EngelChatLinkSvc" -ErrorAction SilentlyContinue
    if ($null -ne $chatLink -and $chatLink.State -ne "Disabled") {
        try {
            Start-ScheduledTask -TaskName "EngelChatLinkSvc" -ErrorAction Stop
            $started += "started EngelChatLinkSvc"
        } catch {
            $started += ("EngelChatLinkSvc start: {0}" -f $_.Exception.Message)
        }
    } elseif (Test-Path -LiteralPath $OneSystem) {
        try {
            Start-Process -FilePath "powershell.exe" -ArgumentList @(
                "-NoProfile", "-ExecutionPolicy", "Bypass",
                "-File", ("`"{0}`"" -f $OneSystem),
                "-NoLaunchApp", "-SkipConnectionTest"
            ) -WindowStyle Hidden
            $started += "launched Start-EngelMainOneSystem.ps1 -NoLaunchApp"
        } catch {
            $started += ("one-system start: {0}" -f $_.Exception.Message)
        }
    }

    if ($IncludeSurvivalDesk) {
        $surv = Get-ScheduledTask -TaskName "EngelSurvivalDesk" -ErrorAction SilentlyContinue
        if ($null -ne $surv -and $surv.State -ne "Disabled") {
            try {
                Start-ScheduledTask -TaskName "EngelSurvivalDesk" -ErrorAction SilentlyContinue
                $started += "started EngelSurvivalDesk"
            } catch { }
        }
    }

    $state.mode = "regular"
    Write-State $state
    $memAfter = Get-MemorySnapshot
    $payload = [pscustomobject]@{
        mode = "regular"
        memory_before = $memBefore
        memory_after = $memAfter
        tasks = $taskChanges
        services = $svcChanges
        autoruns = $autorunChanges
        started = $started
        process_hits = @(Get-ProcessHits)
    }
    $receipt = Write-Receipt "regular" $payload
    Write-Info "REGULAR mode on - Engel link tasks + saved services/autoruns restored."
    Write-Info ("Memory now: {0} GB used / {1} GB total ({2} pct); free {3} GB" -f `
        $memAfter.used_gb, $memAfter.total_gb, $memAfter.used_pct, $memAfter.free_gb)
    Write-Info ("Receipt: {0}" -f $receipt)
    return $payload
}

function Show-Status {
    $state = Read-State
    $mem = Get-MemorySnapshot
    $hits = @(Get-ProcessHits)
    $cursorMb = 0.0
    $cursorCount = 0
    Get-Process Cursor -ErrorAction SilentlyContinue | ForEach-Object {
        $cursorMb += ($_.WorkingSet64 / 1MB)
        $cursorCount += 1
    }
    $bloat = Get-Process -ErrorAction SilentlyContinue | Where-Object {
        $VendorProcessNames -contains $_.Name -or $WindowsExtraProcessNames -contains $_.Name
    } | Group-Object Name | ForEach-Object {
        [pscustomobject]@{
            Name = $_.Name
            Count = $_.Count
            MB = [math]::Round((($_.Group | Measure-Object WorkingSet64 -Sum).Sum)/1MB, 1)
        }
    } | Sort-Object MB -Descending

    $modeLabel = if ($state.mode) { $state.mode } else { "unknown" }
    Write-Info "=== Engel Computer Mode status ==="
    Write-Info ("mode: {0}" -f $modeLabel)
    Write-Info ("memory: {0} GB used / {1} GB total ({2} pct); free {3} GB" -f $mem.used_gb, $mem.total_gb, $mem.used_pct, $mem.free_gb)
    Write-Info ("Cursor (this chat IDE): {0:N0} MB across {1} processes - keep while working here" -f $cursorMb, $cursorCount)
    Write-Info ("Engel/backend process hits: {0}" -f $hits.Count)
    foreach ($h in $hits) {
        Write-Info ("  - pid {0} {1}" -f $h.pid, $h.name)
    }
    Write-Info ("Optional bloat still running: {0}" -f @($bloat).Count)
    foreach ($b in $bloat) {
        Write-Info ("  - {0} x{1} ({2} MB)" -f $b.Name, $b.Count, $b.MB)
    }
    Write-Info ""
    Write-Info "KEEP to run PC: Explorer, DWM, Defender, NVIDIA display, audio/input, Cursor (if using it)."
    Write-Info "CLEAN pauses: Engel tunnels/models, ASUS GlideX/Armoury/Aura/Nahimic, Razer helpers, Dell SMmonitor,"
    Write-Info "  Widgets/Phone Link/Xbox services, Steam/Virtual Pet/Control Room autoruns."
    Write-Info "Windows Cached RAM is free-on-demand, not wasted."
    return [pscustomobject]@{
        mode = $state.mode
        memory = $mem
        cursor_mb = [math]::Round($cursorMb, 1)
        hits = $hits
        bloat = @($bloat)
    }
}

Ensure-Dir $StateDir
Ensure-Dir $ReceiptDir

# Clean/Regular need elevation to pause Engel scheduled tasks + vendor services.
if ($Mode -in @("clean", "regular", "toggle") -and -not (Test-IsAdmin)) {
    $argList = @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", ("`"{0}`"" -f $MyInvocation.MyCommand.Path),
        "-Mode", $Mode,
        "-IncludeVendorBloat", ($(if ($IncludeVendorBloat) { "1" } else { "0" })),
        "-IncludeSurvivalDesk", ($(if ($IncludeSurvivalDesk) { "1" } else { "0" })),
        "-IncludeWindowsExtras", ($(if ($IncludeWindowsExtras) { "1" } else { "0" }))
    )
    if ($NoPause) { $argList += "-NoPause" }
    if ($Quiet) { $argList += "-Quiet" }
    try {
        $p = Start-Process -FilePath (Join-Path $env:WINDIR "System32\WindowsPowerShell\v1.0\powershell.exe") `
            -Verb RunAs -ArgumentList $argList -Wait -PassThru
        exit $p.ExitCode
    } catch {
        Write-Info "Elevation canceled or failed. Continuing without admin (tasks/services that need admin will be skipped)."
    }
}

$result = $null
switch ($Mode) {
    "status" { $result = Show-Status }
    "clean" { $result = Invoke-Clean }
    "regular" { $result = Invoke-Regular }
    "toggle" {
        $state = Read-State
        if ([string]$state.mode -eq "clean") {
            $result = Invoke-Regular
        } else {
            $result = Invoke-Clean
        }
    }
}

if (-not $NoPause -and -not $Quiet) {
    Write-Host ""
    Write-Host "Press Enter to close..."
    [void][Console]::ReadLine()
}

$result | ConvertTo-Json -Depth 6
