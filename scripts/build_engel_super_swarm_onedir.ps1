Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ($args.Count -ne 0) {
    throw "build_engel_super_swarm_onedir.ps1 accepts no arguments."
}

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location -LiteralPath $Root

$SpecPath = Join-Path $Root "EngelSuperSwarmHive3D.spec"
if (-not (Test-Path -LiteralPath $SpecPath -PathType Leaf)) {
    throw "Required spec file missing: EngelSuperSwarmHive3D.spec"
}

$StagingRoot = Join-Path $Root "build\staging"
$DistRoot = Join-Path $StagingRoot "pyinstaller_dist_super_swarm_onedir"
$WorkRoot = Join-Path $StagingRoot "pyinstaller_work_super_swarm_onedir"
$ExpectedOutputDir = Join-Path $StagingRoot "engel_super_swarm_onedir"
$ExpectedOutput = Join-Path $ExpectedOutputDir "EngelSuperSwarmHive3D.exe"
$EngelRuntimeHome = Join-Path $Root "runtime\home"
$EngelHome = Join-Path $EngelRuntimeHome ".engel"
$EngelCodeHome = Join-Path $EngelRuntimeHome ".engelcode"
$OpenEngelHome = Join-Path $EngelRuntimeHome ".openengel"
$EngelRuntimeConfig = Join-Path $Root "runtime\config"
$EngelRuntimeCache = Join-Path $Root "runtime\cache"
$EngelRuntimeData = Join-Path $Root "runtime\data"
$EngelRuntimeTmp = Join-Path $Root "runtime\tmp"
$EngelPyinstallerTmp = Join-Path $Root "runtime\pyinstaller_tmp"
$EngelPyinstallerConfig = Join-Path $Root "runtime\pyinstaller_config"

New-Item -ItemType Directory -Force -Path $StagingRoot, $EngelRuntimeHome, $EngelHome, $EngelCodeHome, $OpenEngelHome, $EngelRuntimeConfig, $EngelRuntimeCache, $EngelRuntimeData, $EngelRuntimeTmp, $EngelPyinstallerTmp, $EngelPyinstallerConfig | Out-Null
$env:HOME = $EngelRuntimeHome
$env:ENGEL_HOME = $EngelHome
$env:ENGELCODE_HOME = $EngelCodeHome
$env:OPENENGEL_HOME = $OpenEngelHome
$env:XDG_CONFIG_HOME = $EngelRuntimeConfig
$env:XDG_CACHE_HOME = $EngelRuntimeCache
$env:XDG_DATA_HOME = $EngelRuntimeData
$env:TEMP = $EngelRuntimeTmp
$env:TMP = $EngelRuntimeTmp
$env:TMPDIR = $EngelRuntimeTmp
$env:PYINSTALLER_CONFIG_DIR = $EngelPyinstallerConfig
$ResolvedStagingRoot = (Resolve-Path -LiteralPath $StagingRoot).Path.TrimEnd('\')
foreach ($PathToClear in @($DistRoot, $WorkRoot, $ExpectedOutputDir)) {
    $ResolvedPathToClear = [System.IO.Path]::GetFullPath($PathToClear).TrimEnd('\')
    if (-not $ResolvedPathToClear.StartsWith($ResolvedStagingRoot + "\", [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove output outside staging root: $ResolvedPathToClear"
    }
    if (Test-Path -LiteralPath $PathToClear) {
        Remove-Item -LiteralPath $PathToClear -Recurse -Force
    }
}
New-Item -ItemType Directory -Force -Path $DistRoot, $WorkRoot | Out-Null

$previousBundleMode = $env:ENGEL_SUPER_SWARM_BUNDLE_MODE
$previousUpx = $env:ENGEL_SUPER_SWARM_UPX
try {
    $env:ENGEL_SUPER_SWARM_BUNDLE_MODE = "onedir"
    $env:ENGEL_SUPER_SWARM_UPX = "0"
    $EngelPy = Join-Path $Root "runtime\python310\python.exe"
    if (-not (Test-Path -LiteralPath $EngelPy)) { $EngelPy = "python" }
    & $EngelPy -m PyInstaller --noconfirm --clean --distpath $DistRoot --workpath $WorkRoot $SpecPath
}
finally {
    if ($null -eq $previousBundleMode) {
        Remove-Item Env:\ENGEL_SUPER_SWARM_BUNDLE_MODE -ErrorAction SilentlyContinue
    } else {
        $env:ENGEL_SUPER_SWARM_BUNDLE_MODE = $previousBundleMode
    }
    if ($null -eq $previousUpx) {
        Remove-Item Env:\ENGEL_SUPER_SWARM_UPX -ErrorAction SilentlyContinue
    } else {
        $env:ENGEL_SUPER_SWARM_UPX = $previousUpx
    }
}

$BuiltDir = Join-Path $DistRoot "EngelSuperSwarmHive3D"
$BuiltExe = Join-Path $BuiltDir "EngelSuperSwarmHive3D.exe"
if (-not (Test-Path -LiteralPath $BuiltExe -PathType Leaf)) {
    throw "PyInstaller completed, but no onedir EngelSuperSwarmHive3D.exe output was found under build\staging."
}

Copy-Item -LiteralPath $BuiltDir -Destination $ExpectedOutputDir -Recurse -Force
if (-not (Test-Path -LiteralPath $ExpectedOutput -PathType Leaf)) {
    throw "Onedir staging copy failed: $ExpectedOutput"
}

Write-Output "BUILD_OUTPUT=build\staging\engel_super_swarm_onedir\EngelSuperSwarmHive3D.exe"
