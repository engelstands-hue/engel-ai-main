param(
    [string]$Python = ""
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
if (-not $Python) {
    $RuntimePython = Join-Path $Root "runtime\python310\python.exe"
    if (Test-Path -LiteralPath $RuntimePython) {
        $Python = $RuntimePython
    } else {
        $Python = "python"
    }
}

Push-Location $Root
try {
    & $Python "tools\update_sub_engel_desktop_from_main.py"
    if ($LASTEXITCODE -ne 0) {
        throw "Sub-Engel desktop updater failed with exit code $LASTEXITCODE."
    }

    & $Python "tools\verify_sub_engel_desktop_server_update.py"
    if ($LASTEXITCODE -ne 0) {
        throw "Sub-Engel desktop verifier failed with exit code $LASTEXITCODE."
    }
} finally {
    Pop-Location
}
