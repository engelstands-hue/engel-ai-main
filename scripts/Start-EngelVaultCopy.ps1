param(
    [string]$VaultRoot = $env:ENGEL_VAULT_MEMORY_ROOT,
    [switch]$Run,
    [switch]$SkipE,
    [switch]$SkipF,
    [switch]$SkipG
)

$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$ReceiptDir = Join-Path $ProjectRoot "reports\vault_migration"
$Stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$ReceiptPath = Join-Path $ReceiptDir "ENGEL_VAULT_COPY_$Stamp.json"

function Resolve-FullPath {
    param([string]$PathText)
    if ($null -eq $PathText) {
        $PathText = ""
    }
    $expanded = [Environment]::ExpandEnvironmentVariables($PathText.Trim().Trim('"'))
    if ([string]::IsNullOrWhiteSpace($expanded)) {
        throw "VaultRoot is empty. Set ENGEL_VAULT_MEMORY_ROOT or pass -VaultRoot."
    }
    return $expanded
}

function Assert-NotSourceOrWorkspace {
    param([string]$PathText)
    $normalized = (Resolve-FullPath $PathText).TrimEnd('\').ToUpperInvariant()
    $lowered = $normalized.ToLowerInvariant()
    $offlinePowerVaultTokens = @(
        "engel-vault-main",
        "engel-vault-share",
        "powervault",
        "/mnt/engel-vault",
        "\mnt\engel-vault",
        "/dev/sdc"
    )
    foreach ($token in $offlinePowerVaultTokens) {
        if ($lowered.Contains($token.ToLowerInvariant())) {
            throw "Refusing offline PowerVault/CT245 VaultRoot: $PathText. Use the verified Dell PowerEdge engel-hdd-vault lane only."
        }
    }
    $forbidden = @(
        "E:\ENGEL_APP_MEMORY",
        "F:\ENGEL_APP_MEMORY",
        "G:\ENGEL_APP_MEMORY",
        "D:\B.WORKSPACE\ENGEL APP"
    )
    foreach ($item in $forbidden) {
        if ($normalized -eq $item -or $normalized.StartsWith($item + "\")) {
            throw "Refusing to use source/workspace path as VaultRoot: $PathText"
        }
    }
}

function New-DirectoryIfMissing {
    param([string]$PathText)
    if (-not (Test-Path -LiteralPath $PathText -PathType Container)) {
        New-Item -ItemType Directory -Path $PathText -Force | Out-Null
    }
}

function Invoke-SafeRobocopy {
    param(
        [string]$Source,
        [string]$Destination
    )
    if (-not (Test-Path -LiteralPath $Source -PathType Container)) {
        return @{
            source = $Source
            destination = $Destination
            skipped = $true
            reason = "source_missing"
            robocopy_exit_code = $null
        }
    }
    New-DirectoryIfMissing $Destination
    $args = @(
        $Source,
        $Destination,
        "/E",
        "/COPY:DAT",
        "/DCOPY:DAT",
        "/R:2",
        "/W:5",
        "/XJ",
        "/FFT",
        "/MT:8",
        "/NP",
        "/NFL",
        "/NDL"
    )
    & robocopy @args | Out-Host
    $code = $LASTEXITCODE
    return @{
        source = $Source
        destination = $Destination
        skipped = $false
        robocopy_exit_code = $code
        ok = ($code -le 7)
    }
}

$ResolvedVaultRoot = Resolve-FullPath $VaultRoot
Assert-NotSourceOrWorkspace $ResolvedVaultRoot

if (-not (Test-Path -LiteralPath $ResolvedVaultRoot -PathType Container)) {
    if (-not $Run) {
        Write-Host "PLAN ONLY: Vault root does not exist yet: $ResolvedVaultRoot"
    } else {
        New-DirectoryIfMissing $ResolvedVaultRoot
    }
}

$sources = @()
if (-not $SkipE) { $sources += @{ drive = "E"; source = "E:\ENGEL_APP_MEMORY"; destination = (Join-Path $ResolvedVaultRoot "sources\E\ENGEL_APP_MEMORY") } }
if (-not $SkipF) { $sources += @{ drive = "F"; source = "F:\ENGEL_APP_MEMORY"; destination = (Join-Path $ResolvedVaultRoot "sources\F\ENGEL_APP_MEMORY") } }
if (-not $SkipG) { $sources += @{ drive = "G"; source = "G:\ENGEL_APP_MEMORY"; destination = (Join-Path $ResolvedVaultRoot "sources\G\ENGEL_APP_MEMORY") } }

$receipt = [ordered]@{
    schema = "engel_vault_copy_receipt_v1"
    created_at_utc = (Get-Date).ToUniversalTime().ToString("o")
    vault_root = $ResolvedVaultRoot
    mode = $(if ($Run) { "run" } else { "plan_only" })
    safety = [ordered]@{
        copy_first = $true
        source_delete_allowed = $false
        source_move_allowed = $false
        target_purge_allowed = $false
        robocopy_mirror_used = $false
        direct_block_device_write_allowed = $false
        secret_inspection_allowed = $false
    }
    sources = @()
}

foreach ($entry in $sources) {
    $row = [ordered]@{
        drive = $entry.drive
        source = $entry.source
        destination = $entry.destination
        source_present = (Test-Path -LiteralPath $entry.source -PathType Container)
        destination_present_before = (Test-Path -LiteralPath $entry.destination -PathType Container)
    }
    if ($Run) {
        $copy = Invoke-SafeRobocopy -Source $entry.source -Destination $entry.destination
        foreach ($key in $copy.Keys) {
            $row[$key] = $copy[$key]
        }
        $row["destination_present_after"] = (Test-Path -LiteralPath $entry.destination -PathType Container)
    } else {
        $row["planned_only"] = $true
    }
    $receipt.sources += $row
}

New-DirectoryIfMissing $ReceiptDir
$receipt | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $ReceiptPath -Encoding UTF8

Write-Host "Receipt: $ReceiptPath"
if (-not $Run) {
    Write-Host "Plan only. Re-run with -Run only after the verified Dell PowerEdge engel-hdd-vault file target is reachable."
}
