param()

$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$RuntimePythonw = Join-Path $ProjectRoot "runtime\python310\pythonw.exe"
$RuntimePython = Join-Path $ProjectRoot "runtime\python310\python.exe"
$PythonExe = if (Test-Path -LiteralPath $RuntimePythonw -PathType Leaf) {
    $RuntimePythonw
} elseif (Test-Path -LiteralPath $RuntimePython -PathType Leaf) {
    $RuntimePython
} else {
    "pythonw.exe"
}

$App = Join-Path $ProjectRoot "tools\engel_connection_loop_doctor_app.py"
if (-not (Test-Path -LiteralPath $App -PathType Leaf)) {
    throw "Engel Connection Doctor App was not found: $App"
}

$QuotedApp = '"' + $App + '"'
Start-Process -FilePath $PythonExe -ArgumentList $QuotedApp -WorkingDirectory $ProjectRoot
