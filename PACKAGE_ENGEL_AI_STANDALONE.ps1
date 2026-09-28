param(
    [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"

$appRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$tauriApp = Join-Path $appRoot "engel_main\app"
$targetDebug = Join-Path $tauriApp "src-tauri\target\debug"
$outDir = Join-Path $appRoot "dist\EngelAI-Standalone"
$referenceDir = Join-Path $outDir "reference-ui"

& (Join-Path $appRoot "ENGEL_RUST_BUILD_ENV.ps1") | Out-Host
$env:VITE_ENGEL_LOCAL_DESKTOP_BYPASS = "true"

if (-not $SkipBuild) {
    Push-Location $tauriApp
    try {
        $previousErrorActionPreference = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        $buildOutput = pnpm exec tauri build --debug --no-bundle -- --bin Engel 2>&1
        $buildExitCode = $LASTEXITCODE
        $ErrorActionPreference = $previousErrorActionPreference
        $buildOutput | ForEach-Object { Write-Host $_ }
        if ($buildExitCode -ne 0) {
            throw "Tauri build failed with exit code $buildExitCode"
        }
    } finally {
        if ($previousErrorActionPreference) {
            $ErrorActionPreference = $previousErrorActionPreference
        }
        Pop-Location
    }
}

$resolvedDist = Resolve-Path -LiteralPath (Join-Path $appRoot "dist")
if (Test-Path -LiteralPath $outDir) {
    $resolvedOut = Resolve-Path -LiteralPath $outDir
    if (-not $resolvedOut.Path.StartsWith($resolvedDist.Path, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove unexpected output path: $($resolvedOut.Path)"
    }
    $packagedExe = Join-Path $resolvedOut.Path "EngelAI.exe"
    Get-Process EngelAI -ErrorAction SilentlyContinue |
        Where-Object { $_.Path -eq $packagedExe } |
        Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 500
    Remove-Item -LiteralPath $resolvedOut.Path -Recurse -Force
}

New-Item -ItemType Directory -Force $outDir | Out-Null
New-Item -ItemType Directory -Force $referenceDir | Out-Null

$builtExe = Join-Path $targetDebug "Engel.exe"
if (-not (Test-Path -LiteralPath $builtExe)) {
    throw "Built Engel.exe was not found: $builtExe"
}

Copy-Item -LiteralPath $builtExe -Destination (Join-Path $outDir "EngelAI.exe") -Force

$runtimePatterns = @(
    "*.dll",
    "*.pak",
    "*.bin",
    "*.dat",
    "*.json",
    "bootstrap*.exe"
)

foreach ($pattern in $runtimePatterns) {
    Get-ChildItem -LiteralPath $targetDebug -Filter $pattern -File -ErrorAction SilentlyContinue |
        Copy-Item -Destination $outDir -Force
}

$locales = Join-Path $targetDebug "locales"
if (Test-Path -LiteralPath $locales) {
    Copy-Item -LiteralPath $locales -Destination (Join-Path $outDir "locales") -Recurse -Force
}

$icon = Join-Path $tauriApp "src-tauri\icons\icon.ico"
if (Test-Path -LiteralPath $icon) {
    Copy-Item -LiteralPath $icon -Destination (Join-Path $outDir "EngelAI.ico") -Force
}

$oldMain = Join-Path $appRoot "dist\EngelAI.exe"
$oldHive = Join-Path $appRoot "dist\EngelSuperSwarmHive3D.exe"
if (Test-Path -LiteralPath $oldMain) {
    Copy-Item -LiteralPath $oldMain -Destination (Join-Path $referenceDir "EngelAI-original.exe") -Force
}
if (Test-Path -LiteralPath $oldHive) {
    Copy-Item -LiteralPath $oldHive -Destination (Join-Path $referenceDir "EngelSuperSwarmHive3D-original.exe") -Force
}

@"
@echo off
setlocal
cd /d "%~dp0"
start "Engel AI" "%~dp0EngelAI.exe" %*
"@ | Set-Content -LiteralPath (Join-Path $outDir "START_ENGEL_AI.cmd") -Encoding ASCII

@"
Engel AI Standalone
===================

Run:
  EngelAI.exe

This folder is self-contained for the Rust/Tauri CEF desktop shell. Runtime state
defaults to the bundled runtime folder on the ROG controller. CT246
(/opt/engel) remains the active server runtime and /mnt/engel-hdd-vault is the
Dell HDD archive lane.

Preserved reference UI executables:
  reference-ui\EngelAI-original.exe
  reference-ui\EngelSuperSwarmHive3D-original.exe
"@ | Set-Content -LiteralPath (Join-Path $outDir "README.txt") -Encoding ASCII

Write-Host "Standalone Engel AI package created:"
Write-Host $outDir
Get-ChildItem -LiteralPath $outDir -Force | Select-Object Mode,Name,Length
