param(
    [Parameter(Mandatory = $true)]
    [string]$VaultRoot,

    [switch]$Machine,
    [switch]$CurrentProcessOnly
)

$ErrorActionPreference = "Stop"

function Resolve-FullPath {
    param([string]$PathText)
    $expanded = [Environment]::ExpandEnvironmentVariables($PathText.Trim().Trim('"'))
    if ([string]::IsNullOrWhiteSpace($expanded)) {
        throw "VaultRoot is empty."
    }
    return $expanded
}

function Test-ForbiddenVaultRoot {
    param([string]$PathText)
    $full = Resolve-FullPath $PathText
    $normalized = $full.TrimEnd('\').ToUpperInvariant()
    $forbidden = @(
        "E:\ENGEL_APP_MEMORY",
        "F:\ENGEL_APP_MEMORY",
        "G:\ENGEL_APP_MEMORY",
        "D:\B.WORKSPACE\ENGEL APP"
    )
    foreach ($item in $forbidden) {
        if ($normalized -eq $item -or $normalized.StartsWith($item + "\")) {
            throw "Refusing to set ENGEL_VAULT_MEMORY_ROOT to a source or workspace path: $full"
        }
    }
    return $full
}

$resolvedRoot = Test-ForbiddenVaultRoot $VaultRoot

if (-not (Test-Path -LiteralPath $resolvedRoot -PathType Container)) {
    throw "VaultRoot does not exist or is not a directory: $resolvedRoot"
}

$env:ENGEL_VAULT_MEMORY_ROOT = $resolvedRoot

if (-not $CurrentProcessOnly) {
    $target = if ($Machine) { [EnvironmentVariableTarget]::Machine } else { [EnvironmentVariableTarget]::User }
    [Environment]::SetEnvironmentVariable("ENGEL_VAULT_MEMORY_ROOT", $resolvedRoot, $target)
}

Write-Host "ENGEL_VAULT_MEMORY_ROOT=$resolvedRoot"
Write-Host "Restart Engel AI Main after setting a User or Machine environment variable."
