param(
    [switch]$Fix,
    [switch]$Gui,
    [switch]$App,
    [switch]$Json
)

$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$RuntimePython = Join-Path $ProjectRoot "runtime\python310\python.exe"
$RuntimePythonw = Join-Path $ProjectRoot "runtime\python310\pythonw.exe"
$PythonExe = if (Test-Path -LiteralPath $RuntimePython -PathType Leaf) { $RuntimePython } else { "python" }
$PythonAppExe = if (Test-Path -LiteralPath $RuntimePythonw -PathType Leaf) { $RuntimePythonw } elseif (Test-Path -LiteralPath $RuntimePython -PathType Leaf) { $RuntimePython } else { "pythonw.exe" }
$Doctor = Join-Path $ProjectRoot "tools\engel_connection_loop_doctor.py"
$DoctorGui = Join-Path $ProjectRoot "tools\engel_connection_loop_doctor_gui.py"
$DoctorApp = Join-Path $ProjectRoot "tools\engel_connection_loop_doctor_app.py"

if ($Gui -or $App) {
    $target = if (Test-Path -LiteralPath $DoctorApp -PathType Leaf) { $DoctorApp } else { $DoctorGui }
    $quotedTarget = '"' + $target + '"'
    Start-Process -FilePath $PythonAppExe -ArgumentList $quotedTarget -WorkingDirectory $ProjectRoot
    return
}

$argsList = @($Doctor)
if ($Json) { $argsList += "--json" }
if ($Fix) { $argsList += "--fix" }

& $PythonExe @argsList
exit $LASTEXITCODE
