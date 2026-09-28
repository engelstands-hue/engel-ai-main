<#
.SYNOPSIS
  Creates the narrowly scoped Windows Firewall rule for Sub-Engel -> Main 8788.
#>
param(
    [string]$AllowedNodeIp = "198.51.100.227",
    [int]$Port = 8788
)

$ErrorActionPreference = "Stop"
$principal = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Administrator elevation is required to modify Windows Firewall."
}

$RuleName = "EngelAIMain-SubEngel-8788"
$DisplayName = "Engel AI Main Sub-Engel Bridge 8788"
$ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$PythonExe = (Resolve-Path -LiteralPath (Join-Path $ProjectRoot "runtime\python310\pythonw.exe")).Path
$ReceiptDir = Join-Path $ProjectRoot "reports\sub_engel_remote_control"
New-Item -ItemType Directory -Force -Path $ReceiptDir | Out-Null
$existing = Get-NetFirewallRule -Name $RuleName -ErrorAction SilentlyContinue
if ($existing) {
    Set-NetFirewallRule -Name $RuleName -Enabled True -Direction Inbound -Action Allow -Profile Any -Program $PythonExe
    $existing | Get-NetFirewallPortFilter | Set-NetFirewallPortFilter -Protocol TCP -LocalPort $Port
    $existing | Get-NetFirewallAddressFilter | Set-NetFirewallAddressFilter -RemoteAddress $AllowedNodeIp
} else {
    New-NetFirewallRule `
        -Name $RuleName `
        -DisplayName $DisplayName `
        -Enabled True `
        -Direction Inbound `
        -Action Allow `
        -Profile Any `
        -Program $PythonExe `
        -Protocol TCP `
        -LocalPort $Port `
        -RemoteAddress $AllowedNodeIp | Out-Null
}

$rule = Get-NetFirewallRule -Name $RuleName
$portFilter = $rule | Get-NetFirewallPortFilter
$addressFilter = $rule | Get-NetFirewallAddressFilter
$receipt = [ordered]@{
    schema = "engel_main_sub_bridge_firewall_v1"
    generated_at_utc = [DateTime]::UtcNow.ToString("o")
    ok = (
        $rule.Enabled -eq "True" -and
        $rule.Direction -eq "Inbound" -and
        $rule.Action -eq "Allow" -and
        $portFilter.Protocol -eq "TCP" -and
        "$($portFilter.LocalPort)" -eq "$Port" -and
        @($addressFilter.RemoteAddress) -contains $AllowedNodeIp
    )
    name = $RuleName
    display_name = $DisplayName
    local_port = $portFilter.LocalPort
    protocol = $portFilter.Protocol
    remote_address = @($addressFilter.RemoteAddress)
    program = $PythonExe
}
$json = $receipt | ConvertTo-Json -Depth 4
$encoding = New-Object System.Text.UTF8Encoding($false)
[IO.File]::WriteAllText((Join-Path $ReceiptDir "ENGEL_MAIN_SUB_BRIDGE_FIREWALL_LATEST.json"), $json, $encoding)
$json
