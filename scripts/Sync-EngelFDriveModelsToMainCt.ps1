param(
    [string]$SourceRoot = "D:\b.WorkSpace\Engel App\runtime\models",
    [string]$TargetRoot = "/opt/engel/models-active",
    [string]$CtHost = "192.0.2.50",
    [int]$CtSshPort = 24622,
    [string]$CtUser = "root",
    [string]$SshKeyPath = "$env:USERPROFILE\.ssh\engel_ai_main_ct246_ed25519",
    [string]$ReceiptRoot = "D:\b.WorkSpace\Engel App\reports\vault_migration",
    [switch]$WhatIfOnly,
    [switch]$AllowVaultUse
)

$ErrorActionPreference = "Stop"

function New-UtcStamp {
    return [DateTime]::UtcNow.ToString("yyyyMMddTHHmmssZ")
}

function ConvertTo-RemoteSafePath {
    param([Parameter(Mandatory = $true)][string]$Path)
    return "'" + $Path.Replace("'", "'`"`"'") + "'"
}

function Get-RelativeUnixPath {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$Path
    )
    $rootFull = [System.IO.Path]::GetFullPath($Root).TrimEnd('\')
    $pathFull = [System.IO.Path]::GetFullPath($Path)
    $relative = $pathFull.Substring($rootFull.Length).TrimStart('\')
    return $relative.Replace('\', '/')
}

function Invoke-CtSsh {
    param([Parameter(Mandatory = $true)][string]$Command)
    $sshArgs = @("-i", $SshKeyPath, "-p", [string]$CtSshPort, "$CtUser@$CtHost", $Command)
    $output = & ssh @sshArgs
    if ($LASTEXITCODE -ne 0) {
        throw "ssh failed with exit $LASTEXITCODE for command: $Command"
    }
    return $output
}

if (-not (Test-Path -LiteralPath $SourceRoot)) {
    throw "SourceRoot not found: $SourceRoot"
}
if (-not (Test-Path -LiteralPath $SshKeyPath)) {
    throw "SSH key not found: $SshKeyPath"
}
$OfflineCt245Mount = "/mnt/" + "engel-vault"
if (-not $AllowVaultUse -and $TargetRoot.TrimEnd("/") -like "$OfflineCt245Mount*") {
    throw "CT245 offline-vault storage is disabled. Use CT246 SSD /opt/engel or Dell HDD /mnt/engel-hdd-vault."
}

New-Item -ItemType Directory -Force -Path $ReceiptRoot | Out-Null
$stamp = New-UtcStamp
$manifestPath = Join-Path $ReceiptRoot "ENGEL_CT246_MODEL_TRANSFER_MANIFEST_$stamp.json"
$progressPath = Join-Path $ReceiptRoot "ENGEL_CT246_MODEL_TRANSFER_PROGRESS_$stamp.jsonl"
$receiptPath = Join-Path $ReceiptRoot "ENGEL_CT246_MODEL_TRANSFER_RECEIPT_$stamp.json"

$files = @(Get-ChildItem -LiteralPath $SourceRoot -Recurse -File -Force -ErrorAction Stop | Sort-Object FullName)
$manifestItems = @(
    foreach ($file in $files) {
        $relative = Get-RelativeUnixPath -Root $SourceRoot -Path $file.FullName
        [pscustomobject]@{
            relative_path = $relative
            source_path = $file.FullName
            target_path = "$TargetRoot/$relative"
            bytes = [int64]$file.Length
            last_write_utc = $file.LastWriteTimeUtc.ToString("o")
        }
    }
)
$totalBytes = [int64](($manifestItems | Measure-Object -Property bytes -Sum).Sum)
$manifest = [ordered]@{
    schema = "engel_f_drive_model_transfer_manifest_v1"
    created_at_utc = [DateTime]::UtcNow.ToString("o")
    source_root = $SourceRoot
    target_root = $TargetRoot
    ct = "$CtUser@$CtHost`:$CtSshPort"
    file_count = $manifestItems.Count
    total_bytes = $totalBytes
    total_gib = [math]::Round($totalBytes / 1GB, 3)
    items = $manifestItems
}
$manifest | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $manifestPath -Encoding UTF8

if ($WhatIfOnly) {
    $receipt = [ordered]@{
        schema = "engel_f_drive_model_transfer_receipt_v1"
        ok = $true
        status = "manifest only"
        manifest_path = $manifestPath
        file_count = $manifestItems.Count
        total_bytes = $totalBytes
        total_gib = [math]::Round($totalBytes / 1GB, 3)
        copied_count = 0
        skipped_count = 0
        failed_count = 0
        created_at_utc = [DateTime]::UtcNow.ToString("o")
    }
    $receipt | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $receiptPath -Encoding UTF8
    $receipt | ConvertTo-Json -Depth 5
    exit 0
}

Invoke-CtSsh "mkdir -p $(ConvertTo-RemoteSafePath $TargetRoot) /opt/engel/memory/models /opt/engel/reports/vault_migration" | Out-Null

$copied = 0
$skipped = 0
$failed = 0
$verifiedBytes = [int64]0
$started = Get-Date
$failures = New-Object System.Collections.Generic.List[object]

foreach ($item in $manifestItems) {
    $remotePath = [string]$item.target_path
    $remoteDir = $remotePath.Substring(0, $remotePath.LastIndexOf('/'))
    $remoteQuoted = ConvertTo-RemoteSafePath $remotePath
    $remoteDirQuoted = ConvertTo-RemoteSafePath $remoteDir
    $remoteSizeText = ""
    try {
        $remoteSizeText = Invoke-CtSsh "if [ -f $remoteQuoted ]; then stat -c %s $remoteQuoted; else echo MISSING; fi"
    } catch {
        $remoteSizeText = "MISSING"
    }
    $remoteSize = -1L
    $parsedRemoteSize = 0L
    if ([Int64]::TryParse(($remoteSizeText | Select-Object -First 1), [ref]$parsedRemoteSize)) {
        $remoteSize = $parsedRemoteSize
    }
    if ($remoteSize -eq [int64]$item.bytes) {
        $skipped++
        $verifiedBytes += [int64]$item.bytes
        [pscustomobject]@{
            utc = [DateTime]::UtcNow.ToString("o")
            status = "already-present"
            relative_path = $item.relative_path
            bytes = [int64]$item.bytes
        } | ConvertTo-Json -Compress | Add-Content -LiteralPath $progressPath -Encoding UTF8
        continue
    }

    try {
        Invoke-CtSsh "mkdir -p $remoteDirQuoted" | Out-Null
        $tmpRemote = "$remotePath.engel-copying"
        $scpTarget = "$CtUser@$CtHost`:$tmpRemote"
        & scp -p -i $SshKeyPath -P $CtSshPort -- ([string]$item.source_path) $scpTarget
        if ($LASTEXITCODE -ne 0) {
            throw "scp failed with exit $LASTEXITCODE"
        }
        $tmpQuoted = ConvertTo-RemoteSafePath $tmpRemote
        Invoke-CtSsh "actual=`$(stat -c %s $tmpQuoted); expected=$($item.bytes); if [ `"x`$actual`" != `"x`$expected`" ]; then echo `"SIZE_MISMATCH tmp=`$actual expected=`$expected`"; exit 7; fi; mv -f $tmpQuoted $remoteQuoted" | Out-Null
        $copied++
        $verifiedBytes += [int64]$item.bytes
        [pscustomobject]@{
            utc = [DateTime]::UtcNow.ToString("o")
            status = "copied"
            relative_path = $item.relative_path
            bytes = [int64]$item.bytes
        } | ConvertTo-Json -Compress | Add-Content -LiteralPath $progressPath -Encoding UTF8
    } catch {
        $failed++
        $failure = [pscustomobject]@{
            relative_path = $item.relative_path
            source_path = $item.source_path
            target_path = $remotePath
            bytes = [int64]$item.bytes
            error = $_.Exception.Message
        }
        $failures.Add($failure) | Out-Null
        $failure | ConvertTo-Json -Compress | Add-Content -LiteralPath $progressPath -Encoding UTF8
    }
}

$finished = Get-Date
$receiptStatus = if ($failed -eq 0) { "finished" } else { "finished with failures" }
$failureItems = if ($failures.Count -gt 0) { @($failures.ToArray()) } else { @() }
$receipt = [ordered]@{
    schema = "engel_f_drive_model_transfer_receipt_v1"
    ok = ($failed -eq 0)
    status = $receiptStatus
    source_root = $SourceRoot
    target_root = $TargetRoot
    manifest_path = $manifestPath
    progress_path = $progressPath
    file_count = $manifestItems.Count
    total_bytes = $totalBytes
    total_gib = [math]::Round($totalBytes / 1GB, 3)
    copied_count = $copied
    skipped_count = $skipped
    failed_count = $failed
    verified_bytes = $verifiedBytes
    verified_gib = [math]::Round($verifiedBytes / 1GB, 3)
    started_at_utc = $started.ToUniversalTime().ToString("o")
    finished_at_utc = $finished.ToUniversalTime().ToString("o")
    elapsed_seconds = [math]::Round(($finished - $started).TotalSeconds, 3)
    failures = $failureItems
}
$receipt | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $receiptPath -Encoding UTF8

& scp -p -i $SshKeyPath -P $CtSshPort -- $manifestPath "$CtUser@$CtHost`:/opt/engel/memory/models/ENGEL_F_DRIVE_MODEL_TRANSFER_MANIFEST.json" | Out-Null
& scp -p -i $SshKeyPath -P $CtSshPort -- $receiptPath "$CtUser@$CtHost`:/opt/engel/reports/vault_migration/ENGEL_F_DRIVE_MODEL_TRANSFER_RECEIPT.json" | Out-Null

$receipt | ConvertTo-Json -Depth 8
if ($failed -ne 0) {
    exit 2
}
