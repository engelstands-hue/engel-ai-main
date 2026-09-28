param(
    [string]$DesktopPath = ([Environment]::GetFolderPath("Desktop"))
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$ModeScript = Join-Path $PSScriptRoot "Engel-ComputerMode.ps1"
$PowerShellPath = Join-Path $env:WINDIR "System32\WindowsPowerShell\v1.0\powershell.exe"

if (-not (Test-Path -LiteralPath $ModeScript -PathType Leaf)) {
    throw "Missing: $ModeScript"
}
if (-not (Test-Path -LiteralPath $DesktopPath -PathType Container)) {
    throw "Desktop path missing: $DesktopPath"
}

function Set-ShortcutRunAsAdmin([string]$ShortcutPath) {
    $bytes = [System.IO.File]::ReadAllBytes($ShortcutPath)
    if ($bytes.Length -gt 0x15) {
        $bytes[0x15] = $bytes[0x15] -bor 0x20
        [System.IO.File]::WriteAllBytes($ShortcutPath, $bytes)
    }
}

function New-ModeShortcut {
    param(
        [string]$Name,
        [string]$ModeArg,
        [string]$Description
    )
    $shortcutPath = Join-Path $DesktopPath ($Name + ".lnk")
    $args = '-NoProfile -ExecutionPolicy Bypass -File "{0}" -Mode {1}' -f $ModeScript, $ModeArg
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = $PowerShellPath
    $shortcut.Arguments = $args
    $shortcut.WorkingDirectory = $ProjectRoot
    $shortcut.Description = $Description
    $shortcut.WindowStyle = 1
    $exeIcon = Join-Path $ProjectRoot "engel_flutter_main\build\windows\x64\runner\Release\EngelAIMain.exe"
    if (Test-Path -LiteralPath $exeIcon) {
        $shortcut.IconLocation = "$exeIcon,0"
    }
    $shortcut.Save()
    Set-ShortcutRunAsAdmin $shortcutPath
    return $shortcutPath
}

$clean = New-ModeShortcut -Name "Engel Clean Computer" -ModeArg "clean" `
    -Description "Pause Engel backends + optional ASUS/Razer helpers so you can use the PC."
$regular = New-ModeShortcut -Name "Engel Regular Mode" -ModeArg "regular" `
    -Description "Restore Engel link tasks/services to regular operation."
$status = New-ModeShortcut -Name "Engel Computer Mode Status" -ModeArg "status" `
    -Description "Show Clean/Regular status and what is using RAM."

[pscustomobject]@{
    ok = $true
    clean_shortcut = $clean
    regular_shortcut = $regular
    status_shortcut = $status
    script = $ModeScript
} | ConvertTo-Json -Depth 4
