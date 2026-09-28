Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ($args.Count -ne 0) {
    throw "build_engel_super_swarm_exe.ps1 accepts no arguments."
}

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location -LiteralPath $Root

$SpecPath = Join-Path $Root "EngelSuperSwarmHive3D.spec"
if (-not (Test-Path -LiteralPath $SpecPath -PathType Leaf)) {
    throw "Required spec file missing: EngelSuperSwarmHive3D.spec"
}

$StagingRoot = Join-Path $Root "build\staging"
$DistRoot = Join-Path $StagingRoot "pyinstaller_dist_super_swarm"
$WorkRoot = Join-Path $StagingRoot "pyinstaller_work_super_swarm"
$ExpectedOutput = Join-Path $StagingRoot "engel_super_swarm.exe"
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

New-Item -ItemType Directory -Force -Path $StagingRoot, $DistRoot, $WorkRoot, $EngelRuntimeHome, $EngelHome, $EngelCodeHome, $OpenEngelHome, $EngelRuntimeConfig, $EngelRuntimeCache, $EngelRuntimeData, $EngelRuntimeTmp, $EngelPyinstallerTmp, $EngelPyinstallerConfig | Out-Null
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

$EngelPy = Join-Path $Root "runtime\python310\python.exe"
if (-not (Test-Path -LiteralPath $EngelPy)) { $EngelPy = "python" }
& $EngelPy -m PyInstaller --noconfirm --clean --distpath $DistRoot --workpath $WorkRoot $SpecPath

$Candidates = @(
    (Join-Path $DistRoot "EngelSuperSwarmHive3D.exe"),
    (Join-Path $DistRoot "EngelSuperSwarmHive3D\EngelSuperSwarmHive3D.exe")
)

$BuiltExe = $null
foreach ($Candidate in $Candidates) {
    if (Test-Path -LiteralPath $Candidate -PathType Leaf) {
        $BuiltExe = $Candidate
        break
    }
}

if ($null -eq $BuiltExe) {
    throw "PyInstaller completed, but no allowlisted EngelSuperSwarmHive3D.exe output was found under build\staging."
}

Copy-Item -LiteralPath $BuiltExe -Destination $ExpectedOutput -Force
Write-Output "BUILD_OUTPUT=build\staging\engel_super_swarm.exe"
