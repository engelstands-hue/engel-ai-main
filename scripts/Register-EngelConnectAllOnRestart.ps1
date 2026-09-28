<#
.SYNOPSIS
  Register (and start now) the watcher that runs Connect-EngelAllDevices.ps1
  whenever Engel AI Main restarts on the ROG.

.DESCRIPTION
  Creates a scheduled task "EngelConnectAllOnMainRestart" that launches the
  persistent Watch-EngelMainRestart.ps1 loop at logon (survives reboot), then
  starts it immediately for the current session. The watcher is single-instance
  (named mutex), so starting twice is harmless.

  Remove with:  Unregister-ScheduledTask -TaskName EngelConnectAllOnMainRestart -Confirm:$false
#>
param(
    [string]$TaskName = "EngelConnectAllOnMainRestart",
    [switch]$NoStartNow
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$Watcher = Join-Path $ProjectRoot "scripts\Watch-EngelMainRestart.ps1"
if (-not (Test-Path -LiteralPath $Watcher)) { throw "watcher not found: $Watcher" }

$psArgs = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$Watcher`""
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $psArgs -WorkingDirectory $ProjectRoot
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -MultipleInstances IgnoreNew `
    -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) `
    -StartWhenAvailable

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Principal $principal -Settings $settings -Force | Out-Null
Write-Host "Registered scheduled task '$TaskName' (runs at logon)."

if (-not $NoStartNow) {
    # Start the watcher for this session immediately (mutex prevents duplicates).
    Start-Process -FilePath "powershell.exe" -ArgumentList @(
        "-NoProfile","-ExecutionPolicy","Bypass","-WindowStyle","Hidden","-File",('"' + $Watcher + '"')
    ) -WindowStyle Hidden | Out-Null
    Write-Host "Watcher started for the current session."
}
Write-Host "Remove with: Unregister-ScheduledTask -TaskName $TaskName -Confirm:`$false"
