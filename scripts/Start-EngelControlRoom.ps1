param(
    [switch]$InstallShortcut
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$PythonW = Join-Path $ProjectRoot "runtime\python310\pythonw.exe"
$Python = Join-Path $ProjectRoot "runtime\python310\python.exe"
$Script = Join-Path $ProjectRoot "run_engel_control_room.py"
$Data = "D:\EngelControlRoom_build\dist\data"
$Icon = "D:\EngelControlRoom_build\dist\EngelControlRoom.exe"

if (-not (Test-Path -LiteralPath $Script)) {
    throw "Missing $Script"
}
if (-not (Test-Path -LiteralPath $PythonW)) { $PythonW = $Python }

$env:ENGEL_CR_DATA = $Data

if ($InstallShortcut) {
    $desktop = [Environment]::GetFolderPath("Desktop")
    $lnk = Join-Path $desktop "Engel AI Control Room.lnk"
    $shell = New-Object -ComObject WScript.Shell
    $sc = $shell.CreateShortcut($lnk)
    $sc.TargetPath = $PythonW
    $sc.Arguments = '"{0}"' -f $Script
    $sc.WorkingDirectory = $ProjectRoot
    $sc.Description = "Engel AI Control Room conical live face"
    if (Test-Path -LiteralPath $Icon) { $sc.IconLocation = "$Icon,0" }
    $sc.WindowStyle = 1
    $sc.Save()
    Write-Output ("shortcut " + $lnk)
}

Start-Process -FilePath $PythonW -ArgumentList @("`"$Script`"") -WorkingDirectory $ProjectRoot
Write-Output "started"
