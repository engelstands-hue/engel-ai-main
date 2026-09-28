param(
    [string]$ShortcutName = "Engel Grok Bot",
    [string]$DesktopPath = ([Environment]::GetFolderPath("Desktop"))
)

$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$Launcher = Join-Path $ProjectRoot "launch_engel_grok_bot.bat"
$IconPath = Join-Path $ProjectRoot "assets\branding\final\engel_icon_final.ico"
$RepoShortcut = Join-Path $ProjectRoot ($ShortcutName + ".lnk")

if (-not (Test-Path -LiteralPath $Launcher -PathType Leaf)) {
    throw "Launcher missing: $Launcher"
}
if (-not (Test-Path -LiteralPath $DesktopPath -PathType Container)) {
    throw "Desktop path missing: $DesktopPath"
}

$shell = New-Object -ComObject WScript.Shell

function Write-EngelGrokBotShortcut {
    param([string]$Path)
    $shortcut = $shell.CreateShortcut($Path)
    $shortcut.TargetPath = $Launcher
    $shortcut.WorkingDirectory = $ProjectRoot
    $shortcut.Description = "Open Engel Grok Bot on the shared cluster computer (CT 246 + Meeting Room + workers)."
    $shortcut.WindowStyle = 1
    if (Test-Path -LiteralPath $IconPath -PathType Leaf) {
        $shortcut.IconLocation = "$IconPath,0"
    }
    $shortcut.Save()
}

$DesktopShortcut = Join-Path $DesktopPath ($ShortcutName + ".lnk")
Write-EngelGrokBotShortcut -Path $DesktopShortcut
Write-EngelGrokBotShortcut -Path $RepoShortcut

[pscustomobject]@{
    ok = $true
    shortcut_path = $DesktopShortcut
    repo_shortcut_path = $RepoShortcut
    target = $Launcher
    working_directory = $ProjectRoot
    icon = $(if (Test-Path -LiteralPath $IconPath -PathType Leaf) { $IconPath } else { "" })
} | ConvertTo-Json -Depth 4
