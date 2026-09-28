param(
    [string]$ProxmoxHost = "192.0.2.50",
    [string]$RemoteUser = "root",
    [int]$CTID = 246,
    [string]$HostSource = "/engel-hdd-vault",
    [string]$ContainerMount = "/mnt/engel-hdd-vault",
    [int]$MountIndex = 1,
    [switch]$AllowCtRestart
)

$ErrorActionPreference = "Stop"

# The remote Proxmox script enforces backup=0 and refuses CT245 offline-vault paths.
if ($CTID -ne 246) {
    throw "Refusing to bind storage to CT $CTID. Engel AI Main target must be CT 246."
}
$OfflineCt245StorageId = "engel-" + "vault-main"
$OfflineCt245Mount = "/mnt/" + "engel-vault"
$OfflineCt245Device = "/dev/" + "sdc"
if ($HostSource -match [regex]::Escape($OfflineCt245StorageId) -or $HostSource -match [regex]::Escape($OfflineCt245Mount) -or $HostSource -match [regex]::Escape($OfflineCt245Device)) {
    throw "Refusing CT245 offline-vault storage path. Use Dell PowerEdge engel-hdd-vault only."
}
if ($ContainerMount -ne "/mnt/engel-hdd-vault") {
    throw "Refusing mountpoint $ContainerMount. Dell PowerEdge HDD vault must mount at /mnt/engel-hdd-vault."
}
if ($MountIndex -lt 0 -or $MountIndex -gt 9) {
    throw "MountIndex must be between 0 and 9."
}

$ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$LocalSetupScript = Join-Path $ProjectRoot "scripts\proxmox\bind_engel_hdd_vault_to_ct246.sh"
$RemoteSetupScript = "/root/bind_engel_hdd_vault_to_ct246.sh"

if (-not (Test-Path -LiteralPath $LocalSetupScript -PathType Leaf)) {
    throw "Missing local Proxmox bind script: $LocalSetupScript"
}

$webOk = Test-NetConnection -ComputerName $ProxmoxHost -Port 8006 -InformationLevel Quiet -WarningAction SilentlyContinue
$sshOk = Test-NetConnection -ComputerName $ProxmoxHost -Port 22 -InformationLevel Quiet -WarningAction SilentlyContinue
if (-not $webOk) {
    throw "Proxmox web port 8006 is not reachable on $ProxmoxHost."
}
if (-not $sshOk) {
    throw "Proxmox SSH port 22 is not reachable on $ProxmoxHost."
}

Write-Host "Copying Dell PowerEdge HDD vault bind script to ${RemoteUser}@${ProxmoxHost}:${RemoteSetupScript}"
scp $LocalSetupScript "${RemoteUser}@${ProxmoxHost}:${RemoteSetupScript}"

$args = @(
    "bash",
    $RemoteSetupScript,
    "--approve",
    "BIND_ENGEL_HDD_VAULT_TO_CT246",
    "--ctid",
    "$CTID",
    "--host-source",
    $HostSource,
    "--container-mount",
    $ContainerMount,
    "--mount-index",
    "$MountIndex"
)

if ($AllowCtRestart) {
    $args += "--allow-ct-restart"
}

$remoteCommand = ($args | ForEach-Object {
    if ($_ -match "^[A-Za-z0-9_./:-]+$") {
        $_
    } else {
        "'" + ($_ -replace "'", "'\''") + "'"
    }
}) -join " "

Write-Host "Running guarded Dell PowerEdge HDD vault bind setup. You may be prompted for the Proxmox password."
ssh -tt "${RemoteUser}@${ProxmoxHost}" $remoteCommand
