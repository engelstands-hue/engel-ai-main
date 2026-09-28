param(
    [string]$ProxmoxIp = "192.0.2.50",
    [string[]]$Names = @("engel-spine-01", "proxmox", "pve")
)

$ErrorActionPreference = "Stop"

function Test-IsElevated {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Test-IPv4Literal {
    param([string]$Ip)
    $address = $null
    return [System.Net.IPAddress]::TryParse($Ip, [ref]$address) -and $address.AddressFamily -eq [System.Net.Sockets.AddressFamily]::InterNetwork
}

if (-not (Test-IsElevated)) {
    throw "Run this script from an elevated PowerShell prompt."
}

if (-not (Test-IPv4Literal $ProxmoxIp)) {
    throw "Invalid IPv4 address: $ProxmoxIp"
}

$cleanNames = @()
foreach ($name in $Names) {
    $trimmed = ""
    if (-not [string]::IsNullOrWhiteSpace($name)) {
        $trimmed = $name.Trim()
    }
    if ($trimmed -and $trimmed -match "^[A-Za-z0-9][A-Za-z0-9.-]*$") {
        $cleanNames += $trimmed
    }
}
if (-not $cleanNames) {
    throw "No valid host names were provided."
}

$hostsPath = Join-Path $env:SystemRoot "System32\drivers\etc\hosts"
$existing = Get-Content -LiteralPath $hostsPath -Raw -ErrorAction Stop
$line = "$ProxmoxIp " + ($cleanNames -join " ")

$needsEntry = $true
foreach ($name in $cleanNames) {
    if ($existing -match "(?im)^\s*$([regex]::Escape($ProxmoxIp))\s+.*\b$([regex]::Escape($name))\b") {
        $needsEntry = $false
    }
}

if ($needsEntry) {
    $stamp = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
    Add-Content -LiteralPath $hostsPath -Value "`r`n# Engel Proxmox management discovered $stamp`r`n$line" -Encoding ASCII
    Write-Host "Added hosts entry: $line"
} else {
    Write-Host "Hosts entry already present for $ProxmoxIp."
}

ipconfig /flushdns | Out-Host

foreach ($name in $cleanNames) {
    $resolved = Resolve-DnsName $name -ErrorAction SilentlyContinue | Where-Object { $_.IPAddress -eq $ProxmoxIp }
    if ($resolved) {
        Write-Host "$name resolves to $ProxmoxIp"
    } else {
        Write-Warning "$name did not resolve to $ProxmoxIp yet"
    }
}

$webOk = Test-NetConnection -ComputerName $ProxmoxIp -Port 8006 -InformationLevel Quiet -WarningAction SilentlyContinue
$sshOk = Test-NetConnection -ComputerName $ProxmoxIp -Port 22 -InformationLevel Quiet -WarningAction SilentlyContinue
Write-Host "Proxmox web 8006 reachable: $webOk"
Write-Host "Proxmox SSH 22 reachable: $sshOk"
