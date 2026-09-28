param(
    [Parameter(Mandatory = $true)]
    [string]$SharePath,

    [System.Management.Automation.PSCredential]$Credential,
    [string]$DriveLetter = "",
    [switch]$PersistEnvironment,
    [switch]$SkipWriteTest
)

$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$ReceiptDir = Join-Path $ProjectRoot "reports\vault_migration"
$Stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$ReceiptPath = Join-Path $ReceiptDir "ENGEL_VAULT_SHARE_CONNECT_$Stamp.json"

function New-DirectoryIfMissing {
    param([string]$PathText)
    if (-not (Test-Path -LiteralPath $PathText -PathType Container)) {
        New-Item -ItemType Directory -Path $PathText -Force | Out-Null
    }
}

function Assert-ValidSharePath {
    param([string]$PathText)
    $trimmed = $PathText.Trim().Trim('"').TrimEnd('\')
    if (-not $trimmed.StartsWith("\\")) {
        throw "SharePath must be a UNC path like \\server\EngelVault."
    }
    foreach ($blocked in @("E:\ENGEL_APP_MEMORY", "F:\ENGEL_APP_MEMORY", "G:\ENGEL_APP_MEMORY", "D:\b.WorkSpace\Engel App")) {
        if ($trimmed.ToUpperInvariant().StartsWith($blocked.ToUpperInvariant())) {
            throw "SharePath cannot point at a source or workspace path: $trimmed"
        }
    }
    return $trimmed
}

function Convert-DriveLetter {
    param([string]$Letter)
    $text = $Letter.Trim().TrimEnd(":")
    if (-not $text) {
        return ""
    }
    if ($text.Length -ne 1 -or $text -notmatch "^[A-Za-z]$") {
        throw "DriveLetter must be a single letter, for example V."
    }
    return ($text.ToUpperInvariant() + ":")
}

$resolvedShare = Assert-ValidSharePath $SharePath
$resolvedDrive = Convert-DriveLetter $DriveLetter

if ($Credential -eq $null) {
    $Credential = Get-Credential -Message "Enter Samba credentials for $resolvedShare"
}

if ($resolvedDrive) {
    $plainPassword = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
        [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Credential.Password)
    )
    try {
        $existing = Get-SmbMapping -LocalPath $resolvedDrive -ErrorAction SilentlyContinue
        if ($existing) {
            if ($existing.RemotePath -ne $resolvedShare) {
                throw "$resolvedDrive is already mapped to $($existing.RemotePath)"
            }
        } else {
            New-SmbMapping -LocalPath $resolvedDrive -RemotePath $resolvedShare -UserName $Credential.UserName -Password $plainPassword -Persistent $true | Out-Null
        }
    } finally {
        $plainPassword = $null
    }
    $rootForTests = $resolvedDrive + "\"
} else {
    $tempName = "EV" + (Get-Random -Minimum 1000 -Maximum 9999)
    New-PSDrive -Name $tempName -PSProvider FileSystem -Root $resolvedShare -Credential $Credential -ErrorAction Stop | Out-Null
    $rootForTests = $tempName + ":\"
}

try {
    if (-not (Test-Path -LiteralPath $rootForTests -PathType Container)) {
        throw "Vault share is not reachable: $resolvedShare"
    }

    foreach ($relative in @(
        "sources\E\ENGEL_APP_MEMORY",
        "sources\F\ENGEL_APP_MEMORY",
        "sources\G\ENGEL_APP_MEMORY",
        "receipts"
    )) {
        New-DirectoryIfMissing (Join-Path $rootForTests $relative)
    }

    $writeTestOk = $false
    if (-not $SkipWriteTest) {
        $testFile = Join-Path $rootForTests ("receipts\.engel_vault_write_test_" + $Stamp + ".txt")
        "Engel vault write test $Stamp" | Set-Content -LiteralPath $testFile -Encoding UTF8
        $writeTestOk = Test-Path -LiteralPath $testFile -PathType Leaf
        Remove-Item -LiteralPath $testFile -Force
    }

    $setRootScript = Join-Path $PSScriptRoot "Set-EngelVaultMemoryRoot.ps1"
    if ($PersistEnvironment) {
        & $setRootScript -VaultRoot $resolvedShare
    } else {
        & $setRootScript -VaultRoot $resolvedShare -CurrentProcessOnly
    }

    New-DirectoryIfMissing $ReceiptDir
    $receipt = [ordered]@{
        schema = "engel_vault_share_connect_receipt_v1"
        created_at_utc = (Get-Date).ToUniversalTime().ToString("o")
        share_path = $resolvedShare
        drive_letter = $resolvedDrive
        reachable = $true
        expected_layout_present = $true
        write_test_ok = $writeTestOk
        persisted_environment = [bool]$PersistEnvironment
        credential_value_logged = $false
        next_copy_command = ".\scripts\Start-EngelVaultCopy.ps1 -VaultRoot `"$resolvedShare`" -Run"
    }
    $receipt | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $ReceiptPath -Encoding UTF8
    Write-Host "ENGEL_VAULT_SHARE_CONNECT_OK"
    Write-Host "Share: $resolvedShare"
    if ($resolvedDrive) {
        Write-Host "Mapped drive: $resolvedDrive"
    }
    Write-Host "Receipt: $ReceiptPath"
    Write-Host "Next: .\scripts\Start-EngelVaultCopy.ps1 -VaultRoot `"$resolvedShare`" -Run"
} finally {
    if (-not $resolvedDrive -and $tempName) {
        Remove-PSDrive -Name $tempName -Force -ErrorAction SilentlyContinue
    }
}
