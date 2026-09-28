param(
    [string]$ProxmoxHost = "proxmox",
    [string]$RemoteUser = "root",
    [string]$VMID = "245"
)

$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$LocalResumeScript = Join-Path $ProjectRoot "scripts\proxmox\resume_engel_vault_smb_share.sh"
$RemoteResumeScript = "/root/resume_engel_vault_smb_share.sh"

if (-not (Test-Path -LiteralPath $LocalResumeScript -PathType Leaf)) {
    throw "Missing local Proxmox resume script: $LocalResumeScript"
}

$webOk = Test-NetConnection -ComputerName $ProxmoxHost -Port 8006 -InformationLevel Quiet -WarningAction SilentlyContinue
$sshOk = Test-NetConnection -ComputerName $ProxmoxHost -Port 22 -InformationLevel Quiet -WarningAction SilentlyContinue
if (-not $webOk) {
    throw "Proxmox web port 8006 is not reachable on $ProxmoxHost."
}
if (-not $sshOk) {
    throw "Proxmox SSH port 22 is not reachable on $ProxmoxHost."
}

Write-Host "Copying resume script to ${RemoteUser}@${ProxmoxHost}:${RemoteResumeScript}"
scp $LocalResumeScript "${RemoteUser}@${ProxmoxHost}:${RemoteResumeScript}"

$remoteCommand = "bash $RemoteResumeScript --vmid $VMID"
Write-Host "Resuming guarded Proxmox share setup. You may be prompted for the Proxmox password."
ssh -tt "${RemoteUser}@${ProxmoxHost}" $remoteCommand
