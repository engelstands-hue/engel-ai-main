param(
    [string]$CtHost = "192.0.2.50",
    [int]$CtPort = 24622,
    [string]$CtUser = "root",
    [string]$LocalBind = "127.0.0.1",
    [int]$LocalPort = 24680,
    [int]$RemotePort = 8765
)

$ErrorActionPreference = "Stop"

if ($CtPort -lt 1 -or $CtPort -gt 65535 -or $LocalPort -lt 1 -or $LocalPort -gt 65535 -or $RemotePort -lt 1 -or $RemotePort -gt 65535) {
    throw "Ports must be in the TCP range 1-65535."
}

$sshOk = Test-NetConnection -ComputerName $CtHost -Port $CtPort -InformationLevel Quiet -WarningAction SilentlyContinue
if (-not $sshOk) {
    throw "CT SSH route is not reachable: ${CtHost}:${CtPort}"
}

Write-Host "Opening ROG -> engel-ai-main chat tunnel."
Write-Host "Local URL for Engel AI Main: http://${LocalBind}:${LocalPort}"
Write-Host "Remote CT service: 127.0.0.1:${RemotePort}"
Write-Host "Leave this PowerShell window open while using server chat."
Write-Host ""

ssh -N -L "${LocalBind}:${LocalPort}:127.0.0.1:${RemotePort}" -p $CtPort "${CtUser}@${CtHost}"
