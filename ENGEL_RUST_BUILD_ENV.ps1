param(
    [switch]$Persist
)

$ErrorActionPreference = "Stop"

$defaultLibclangPath = "D:\b.WorkSpace\Engel App\runtime\toolchains\libclang"
$libclangPath = $defaultLibclangPath
if (-not (Test-Path (Join-Path $libclangPath "libclang.dll"))) {
    $detectedLibclang = $null
    try {
        $detectedLibclang = (& where.exe libclang.dll 2>$null | Select-Object -First 1)
    } catch {
        $detectedLibclang = $null
    }
    if (-not [string]::IsNullOrWhiteSpace($detectedLibclang)) {
        $libclangPath = Split-Path -Parent $detectedLibclang
    }
}

$vars = [ordered]@{
    CARGO_HOME = "D:\b.WorkSpace\Engel App\runtime\cargo-home"
    LIBCLANG_PATH = $libclangPath
    CEF_PATH = "D:\b.WorkSpace\Engel App\runtime\runtimes\tauri-cef\146.0.9\cef_windows_x86_64"
    CMAKE_GENERATOR = "Ninja"
    CMAKE_MAKE_PROGRAM = "D:\b.WorkSpace\Engel App\runtime\tools\ninja\ninja.exe"
}

foreach ($path in @(
    $vars.CARGO_HOME,
    $vars.LIBCLANG_PATH,
    (Split-Path -Parent $vars.CMAKE_MAKE_PROGRAM)
)) {
    New-Item -ItemType Directory -Force $path | Out-Null
}

foreach ($entry in $vars.GetEnumerator()) {
    [Environment]::SetEnvironmentVariable($entry.Key, $entry.Value, "Process")
    if ($Persist) {
        [Environment]::SetEnvironmentVariable($entry.Key, $entry.Value, "User")
    }
}

$pathParts = @(
    (Split-Path -Parent $vars.CMAKE_MAKE_PROGRAM),
    $vars.CEF_PATH,
    $vars.LIBCLANG_PATH
)

$processPathParts = @($pathParts)
[array]::Reverse($processPathParts)
foreach ($part in $processPathParts) {
    $escaped = [Regex]::Escape($part)
    if ($env:PATH -notmatch "(^|;)$escaped(;|$)") {
        $env:PATH = "$part;$env:PATH"
    }
}

if ($Persist) {
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    if ([string]::IsNullOrWhiteSpace($userPath)) {
        $userPath = ""
    }
    foreach ($part in $pathParts) {
        $escaped = [Regex]::Escape($part)
        if ($userPath -notmatch "(^|;)$escaped(;|$)") {
            $userPath = if ($userPath.Length -eq 0) { $part } else { "$part;$userPath" }
        }
    }
    [Environment]::SetEnvironmentVariable("Path", $userPath, "User")
}

Write-Host "Engel Rust build environment loaded."
Write-Host "CARGO_HOME=$env:CARGO_HOME"
Write-Host "LIBCLANG_PATH=$env:LIBCLANG_PATH"
Write-Host "CEF_PATH=$env:CEF_PATH"
Write-Host "CMAKE_GENERATOR=$env:CMAKE_GENERATOR"
Write-Host "CMAKE_MAKE_PROGRAM=$env:CMAKE_MAKE_PROGRAM"
