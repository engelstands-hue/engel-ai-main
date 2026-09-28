param(
    [string]$ProxmoxHost = "proxmox",
    [string]$RemoteUser = "root",
    [string]$VMID = "246",
    [string]$RemoteRoot = ""
)

$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$LocalPrepareScript = Join-Path $ProjectRoot "scripts\proxmox\prepare_engel_vault_ssh_target.sh"
$RemotePrepareScript = "/root/prepare_engel_vault_ssh_target.sh"

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

function ConvertTo-RemoteCommand {
    param([string[]]$Parts)
    return ($Parts | ForEach-Object {
        if ($_ -match "^[A-Za-z0-9_./:-]+$") {
            $_
        } else {
            "'" + ($_ -replace "'", "'\''") + "'"
        }
    }) -join " "
}

if (-not (Test-Path -LiteralPath $LocalPrepareScript -PathType Leaf)) {
    throw "Missing local Proxmox prepare script: $LocalPrepareScript"
}

Assert-SafeRemoteToken -Label "ProxmoxHost" -Value $ProxmoxHost -Pattern "^[A-Za-z0-9_.-]+$"
Assert-SafeRemoteToken -Label "RemoteUser" -Value $RemoteUser -Pattern "^[A-Za-z_][A-Za-z0-9_-]*$"
Assert-SafeRemoteToken -Label "VMID" -Value $VMID -Pattern "^[0-9]+$"
if (-not [string]::IsNullOrWhiteSpace($RemoteRoot)) {
    Assert-SafeRemoteToken -Label "RemoteRoot" -Value $RemoteRoot -Pattern "^(/opt/engel|/mnt/engel-hdd-vault)(/[A-Za-z0-9_.-]+)*$"
}

$sshOk = Test-NetConnection -ComputerName $ProxmoxHost -Port 22 -InformationLevel Quiet -WarningAction SilentlyContinue
if (-not $sshOk) {
    throw "Proxmox SSH port 22 is not reachable on $ProxmoxHost."
}

Write-Host "Copying SSH target prepare script to ${RemoteUser}@${ProxmoxHost}:${RemotePrepareScript}"
& scp $LocalPrepareScript "${RemoteUser}@${ProxmoxHost}:${RemotePrepareScript}"
if ($LASTEXITCODE -ne 0) {
    throw "scp failed while copying $LocalPrepareScript"
}

$args = @("bash", $RemotePrepareScript, "--vmid", $VMID)
if (-not [string]::IsNullOrWhiteSpace($RemoteRoot)) {
    $args += @("--remote-root", $RemoteRoot)
}

$remoteCommand = ConvertTo-RemoteCommand $args

Write-Host "Preparing guarded Proxmox SSH target. You may be prompted for the Proxmox password."
& ssh -tt "${RemoteUser}@${ProxmoxHost}" $remoteCommand
if ($LASTEXITCODE -ne 0) {
    throw "Remote SSH target preparation failed."
}
