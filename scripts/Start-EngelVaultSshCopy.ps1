param(
    [string]$ProxmoxHost = "proxmox",
    [string]$RemoteUser = "root",
    [string]$VMID = "245",
    [string]$RemoteRoot = "",
    [switch]$Run,
    [switch]$SkipPrepare,
    [switch]$SkipE,
    [switch]$SkipF,
    [switch]$SkipG
)

$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$ReceiptDir = Join-Path $ProjectRoot "reports\vault_migration"
$Stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$ReceiptPath = Join-Path $ReceiptDir "ENGEL_VAULT_SSH_COPY_$Stamp.json"

$source_delete_allowed = $false
$source_move_allowed = $false
$target_purge_allowed = $false
$direct_block_device_write_allowed = $false

function New-DirectoryIfMissing {
    param([string]$PathText)
    if (-not (Test-Path -LiteralPath $PathText -PathType Container)) {
        New-Item -ItemType Directory -Path $PathText -Force | Out-Null
    }
}

function Assert-SafeRemoteToken {
    param(
        [string]$Label,
        [string]$Value,
        [string]$Pattern
    )
    if ($Value -notmatch $Pattern) {
        throw "$Label contains unsupported characters: $Value"
    }
}

Assert-SafeRemoteToken -Label "ProxmoxHost" -Value $ProxmoxHost -Pattern "^[A-Za-z0-9_.-]+$"
Assert-SafeRemoteToken -Label "RemoteUser" -Value $RemoteUser -Pattern "^[A-Za-z_][A-Za-z0-9_-]*$"
Assert-SafeRemoteToken -Label "VMID" -Value $VMID -Pattern "^[0-9]+$"

if ([string]::IsNullOrWhiteSpace($RemoteRoot)) {
    $RemoteRoot = "/var/lib/lxc/$VMID/rootfs/srv/engel-vault/ENGEL_APP_MEMORY"
}

Assert-SafeRemoteToken -Label "RemoteRoot" -Value $RemoteRoot -Pattern "^/var/lib/lxc/[0-9]+/rootfs/srv/engel-vault/ENGEL_APP_MEMORY(/[A-Za-z0-9_.-]+)*$"
if ($RemoteRoot -notlike "/var/lib/lxc/$VMID/rootfs/srv/engel-vault/ENGEL_APP_MEMORY*") {
    throw "RemoteRoot must match the selected VMID $VMID."
}

$sshOk = Test-NetConnection -ComputerName $ProxmoxHost -Port 22 -InformationLevel Quiet -WarningAction SilentlyContinue
if (-not $sshOk) {
    throw "Proxmox SSH port 22 is not reachable on $ProxmoxHost."
}

$scpCommand = Get-Command scp -ErrorAction Stop
$sshCommand = Get-Command ssh -ErrorAction Stop

if ($Run -and -not $SkipPrepare) {
    $prepareScript = Join-Path $PSScriptRoot "Prepare-EngelVaultSshTarget.ps1"
    & $prepareScript -ProxmoxHost $ProxmoxHost -RemoteUser $RemoteUser -VMID $VMID -RemoteRoot $RemoteRoot
}

$sources = @()
if (-not $SkipE) { $sources += [ordered]@{ drive = "E"; source = "E:\ENGEL_APP_MEMORY" } }
if (-not $SkipF) { $sources += [ordered]@{ drive = "F"; source = "F:\ENGEL_APP_MEMORY" } }
if (-not $SkipG) { $sources += [ordered]@{ drive = "G"; source = "G:\ENGEL_APP_MEMORY" } }

$receipt = [ordered]@{
    schema = "engel_vault_ssh_copy_receipt_v1"
    created_at_utc = (Get-Date).ToUniversalTime().ToString("o")
    proxmox_host = $ProxmoxHost
    remote_user = $RemoteUser
    vmid = $VMID
    remote_root = $RemoteRoot
    mode = $(if ($Run) { "run" } else { "plan_only" })
    transfer_method = "scp_recursive_copy"
    safety = [ordered]@{
        copy_first = $true
        source_delete_allowed = $source_delete_allowed
        source_move_allowed = $source_move_allowed
        target_purge_allowed = $target_purge_allowed
        robocopy_mirror_used = $false
        direct_block_device_write_allowed = $direct_block_device_write_allowed
        package_install_used = $false
        secret_inspection_allowed = $false
    }
    sources = @()
}

foreach ($entry in $sources) {
    $drive = $entry.drive
    $source = $entry.source
    $remoteParent = "$RemoteRoot/sources/$drive"
    $remoteDestination = "$remoteParent/ENGEL_APP_MEMORY"
    $sourcePresent = Test-Path -LiteralPath $source -PathType Container

    $row = [ordered]@{
        drive = $drive
        source = $source
        remote_parent = $remoteParent
        remote_destination = $remoteDestination
        source_present = $sourcePresent
    }

    if (-not $sourcePresent) {
        $row["skipped"] = $true
        $row["reason"] = "source_missing"
        $receipt.sources += $row
        continue
    }

    if (-not $Run) {
        $row["planned_only"] = $true
        $receipt.sources += $row
        continue
    }

    Write-Host "Preparing remote parent for drive ${drive}: $remoteParent"
    $mkdirCommand = "mkdir -p $remoteParent && test -d $remoteParent"
    & $sshCommand.Source "${RemoteUser}@${ProxmoxHost}" $mkdirCommand
    $mkdirCode = $LASTEXITCODE
    $row["remote_prepare_exit_code"] = $mkdirCode
    if ($mkdirCode -ne 0) {
        $row["ok"] = $false
        $row["reason"] = "remote_parent_prepare_failed"
        $receipt.sources += $row
        continue
    }

    Write-Host "Copying ${drive}:\ENGEL_APP_MEMORY to Proxmox vault with scp. This may take a long time."
    $remoteSpec = "${RemoteUser}@${ProxmoxHost}:$remoteParent/"
    & $scpCommand.Source -r -p $source $remoteSpec
    $copyCode = $LASTEXITCODE
    $row["scp_exit_code"] = $copyCode
    $row["ok"] = ($copyCode -eq 0)
    if ($copyCode -ne 0) {
        $row["reason"] = "scp_failed_or_interrupted"
    }
    $receipt.sources += $row
}

New-DirectoryIfMissing $ReceiptDir
$receipt | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $ReceiptPath -Encoding UTF8

Write-Host "Receipt: $ReceiptPath"
if (-not $Run) {
    Write-Host "Plan only. Re-run with -Run after reviewing the target."
}
