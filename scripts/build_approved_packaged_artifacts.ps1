Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ($args.Count -ne 0) {
    throw "build_approved_packaged_artifacts.ps1 accepts no arguments."
}

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location -LiteralPath $Root

$MainScript = Join-Path $Root "scripts\build_engel_main_exe.ps1"
$SuperSwarmScript = Join-Path $Root "scripts\build_engel_super_swarm_exe.ps1"

if (-not (Test-Path -LiteralPath $MainScript -PathType Leaf)) {
    throw "Required script missing: scripts\build_engel_main_exe.ps1"
}
if (-not (Test-Path -LiteralPath $SuperSwarmScript -PathType Leaf)) {
    throw "Required script missing: scripts\build_engel_super_swarm_exe.ps1"
}

& $MainScript
& $SuperSwarmScript
Write-Output "BUILD_OUTPUT=build\staging"
