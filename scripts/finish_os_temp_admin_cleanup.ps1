param(
    [switch]$ApproveOsDriveCleanup
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Continue"

$ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path

if (-not $ApproveOsDriveCleanup) {
    throw "Refusing OS-drive temp cleanup without -ApproveOsDriveCleanup. C: is OS-only; this script is only for explicit admin cleanup of old OS temp leftovers."
}

if (-not $env:USERPROFILE) {
    throw "USERPROFILE is unavailable; refusing OS-drive cleanup."
}

if (-not $env:USERPROFILE.StartsWith("C:\", [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "USERPROFILE is not on C:; refusing because this script is only for explicit C: OS temp cleanup."
}

$TempRoot = Join-Path $env:USERPROFILE "AppData\Local\Temp"
$LogRoot = Join-Path $ProjectRoot "reports\c_drive_cleanup"
New-Item -ItemType Directory -Force -Path $LogRoot | Out-Null
$LogPath = Join-Path $LogRoot ("ADMIN_OS_TEMP_CLEANUP_" + (Get-Date -Format "yyyyMMdd_HHmmss") + ".log")

$Names = @(
    "_MEI463842",
    "_MEI364402",
    "_MEI384202",
    "_MEI215362"
)

"ADMIN_OS_TEMP_CLEANUP_START $(Get-Date -Format o)" | Tee-Object -FilePath $LogPath
"TEMP_ROOT=$TempRoot" | Tee-Object -FilePath $LogPath -Append

foreach ($Name in $Names) {
    $Path = Join-Path $TempRoot $Name
    $FullPath = [System.IO.Path]::GetFullPath($Path).TrimEnd("\")
    if (-not $FullPath.StartsWith($TempRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        "REFUSED_OUTSIDE_TEMP $FullPath" | Tee-Object -FilePath $LogPath -Append
        continue
    }
    if (-not (Test-Path -LiteralPath $FullPath)) {
        "MISSING $FullPath" | Tee-Object -FilePath $LogPath -Append
        continue
    }

    "TAKEOWN $FullPath" | Tee-Object -FilePath $LogPath -Append
    & takeown.exe /F $FullPath /R /D Y *>> $LogPath
    $Principal = "$env:USERDOMAIN\$env:USERNAME"
    $Grant = "${Principal}:(OI)(CI)F"
    "ICACLS $FullPath $Grant" | Tee-Object -FilePath $LogPath -Append
    & icacls.exe $FullPath /grant $Grant /T /C *>> $LogPath

    try {
        Remove-Item -LiteralPath $FullPath -Recurse -Force -ErrorAction Stop
        "REMOVED $FullPath" | Tee-Object -FilePath $LogPath -Append
    }
    catch {
        "FAILED $FullPath :: $($_.Exception.Message)" | Tee-Object -FilePath $LogPath -Append
    }
}

"ADMIN_OS_TEMP_CLEANUP_END $(Get-Date -Format o)" | Tee-Object -FilePath $LogPath -Append
