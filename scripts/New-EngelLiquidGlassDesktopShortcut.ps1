param(
    [string]$ShortcutName = "Engel AI Main",
    [string]$DesktopPath = ([Environment]::GetFolderPath("Desktop"))
)

$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$ExePath = Join-Path $ProjectRoot "engel_flutter_main\build\windows\x64\runner\Release\EngelAIMain.exe"

if (-not (Test-Path -LiteralPath $ExePath -PathType Leaf)) {
    throw "Release EngelAIMain.exe missing: $ExePath. Build with flutter build windows --release first."
}
if (-not (Test-Path -LiteralPath $DesktopPath -PathType Container)) {
    throw "Desktop path missing: $DesktopPath"
}

$ShortcutPath = Join-Path $DesktopPath ($ShortcutName + ".lnk")
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($ShortcutPath)
$shortcut.TargetPath = $ExePath
$shortcut.WorkingDirectory = Split-Path -Parent $ExePath
$shortcut.Description = "Engel AI Main — Liquid Glass Operator Console (Chat, Status, Settings)."
$shortcut.IconLocation = "$ExePath,0"
$shortcut.Save()

[pscustomobject]@{
    ok = $true
    shortcut_path = $ShortcutPath
    target = $ExePath
    working_directory = (Split-Path -Parent $ExePath)
} | ConvertTo-Json -Depth 4
