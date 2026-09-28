param(
    [string]$ShortcutName = "Engel AI Agent Meeting Room Office",
    [string]$DesktopPath = ([Environment]::GetFolderPath("Desktop"))
)

$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$Launcher = Join-Path $PSScriptRoot "Start-EngelAgentMeetingRoomOffice.ps1"

if (-not (Test-Path -LiteralPath $Launcher -PathType Leaf)) {
    throw "Launcher script missing: $Launcher"
}
if (-not (Test-Path -LiteralPath $DesktopPath -PathType Container)) {
    throw "Desktop path missing: $DesktopPath"
}

$ShortcutPath = Join-Path $DesktopPath ($ShortcutName + ".lnk")
$PowerShellPath = Join-Path $env:WINDIR "System32\WindowsPowerShell\v1.0\powershell.exe"
$Arguments = '-NoProfile -ExecutionPolicy Bypass -File "{0}"' -f $Launcher

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($ShortcutPath)
$shortcut.TargetPath = $PowerShellPath
$shortcut.Arguments = $Arguments
$shortcut.WorkingDirectory = $ProjectRoot
$shortcut.Description = "Start Engel3D Agent Meeting Room connected to Engel AI Main CT 246."
$shortcut.Save()

[pscustomobject]@{
    ok = $true
    shortcut_path = $ShortcutPath
    target = $PowerShellPath
    arguments = $Arguments
    working_directory = $ProjectRoot
} | ConvertTo-Json -Depth 4
