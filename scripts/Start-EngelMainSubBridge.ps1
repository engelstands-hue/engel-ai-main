<#
.SYNOPSIS
  Starts Engel AI Main's receive-only Sub-Engel pairing bridge and auto-pair watcher.

.DESCRIPTION
  The bridge binds 0.0.0.0:8788 but accepts node-ready callbacks only from the
  explicitly configured Sub-Engel IP. It does not expose the legacy bootstrap
  installer/package endpoints, so starting Main cannot downgrade the Sub build.
#>
param(
    [string]$ControllerIp = "192.0.2.40",
    [int]$Port = 8788,
    [string]$AllowedNodeIp = "198.51.100.227",
    [int]$WaitSeconds = 20
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$PythonExe = Join-Path $ProjectRoot "runtime\python310\pythonw.exe"
$BridgeScript = Join-Path $ProjectRoot "tools\windows_sub_engel_wired_bootstrap_server.py"
$WatcherScript = Join-Path $ProjectRoot "tools\watch_windows_sub_engel_pairing.py"
$RuntimeDir = Join-Path $ProjectRoot "runtime\device_cluster_controller"
$ReceiptDir = Join-Path $ProjectRoot "reports\sub_engel_remote_control"
$HealthUrl = "http://127.0.0.1:$Port/health"

foreach ($path in @($PythonExe, $BridgeScript, $WatcherScript)) {
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Required Engel Main Sub bridge file is missing: $path"
    }
}
New-Item -ItemType Directory -Force -Path $RuntimeDir, $ReceiptDir | Out-Null

function Get-MatchingProcess {
    param([string]$ScriptName)
    @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object {
            $_.Name -match '^pythonw?\.exe$' -and
            $_.CommandLine -and
            $_.CommandLine.IndexOf($ScriptName, [StringComparison]::OrdinalIgnoreCase) -ge 0
        })
}

function Test-BridgeHealth {
    try {
        $health = Invoke-RestMethod -Uri $HealthUrl -TimeoutSec 3
        return (
            $health.ok -eq $true -and
            $health.mode -eq "node-ready-receiver" -and
            @($health.allowed_node_ips) -contains $AllowedNodeIp
        )
    } catch {
        return $false
    }
}

$bridgeProcesses = @(Get-MatchingProcess "windows_sub_engel_wired_bootstrap_server.py")
if (-not (Test-BridgeHealth)) {
    if ($bridgeProcesses.Count -gt 0) {
        throw "Port $Port is owned by an unhealthy/stale Engel bridge process; refusing an unverified duplicate."
    }
    $bridgeOut = Join-Path $RuntimeDir "windows_sub_main_bridge.out.log"
    $bridgeErr = Join-Path $RuntimeDir "windows_sub_main_bridge.err.log"
    Start-Process -FilePath $PythonExe -WorkingDirectory $ProjectRoot -WindowStyle Hidden -ArgumentList @(
        "`"$BridgeScript`"",
        "--host", "0.0.0.0",
        "--port", "$Port",
        "--controller-ip", $ControllerIp,
        "--ready-only",
        "--allowed-node-ip", $AllowedNodeIp
    ) -RedirectStandardOutput $bridgeOut -RedirectStandardError $bridgeErr | Out-Null
}

$deadline = [DateTime]::UtcNow.AddSeconds([Math]::Max(1, $WaitSeconds))
while ([DateTime]::UtcNow -lt $deadline -and -not (Test-BridgeHealth)) {
    Start-Sleep -Milliseconds 400
}
if (-not (Test-BridgeHealth)) {
    throw "Engel Main Sub bridge did not become healthy at $HealthUrl."
}

$watcherProcesses = @(Get-MatchingProcess "watch_windows_sub_engel_pairing.py")
if ($watcherProcesses.Count -eq 0) {
    $watcherOut = Join-Path $RuntimeDir "windows_sub_auto_pair_watcher_current.out.log"
    $watcherErr = Join-Path $RuntimeDir "windows_sub_auto_pair_watcher_current.err.log"
    Start-Process -FilePath $PythonExe -WorkingDirectory $ProjectRoot -WindowStyle Hidden -ArgumentList @(
        "`"$WatcherScript`"",
        "--server-only"
    ) -RedirectStandardOutput $watcherOut -RedirectStandardError $watcherErr | Out-Null
    Start-Sleep -Milliseconds 600
    $watcherProcesses = @(Get-MatchingProcess "watch_windows_sub_engel_pairing.py")
}
if ($watcherProcesses.Count -eq 0) {
    throw "Engel Main Sub auto-pair watcher did not start."
}

$listener = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue |
    Select-Object -First 1
$receipt = [ordered]@{
    schema = "engel_main_sub_bridge_start_v1"
    generated_at_utc = [DateTime]::UtcNow.ToString("o")
    ok = [bool]$listener
    bind = if ($listener) { "$($listener.LocalAddress):$($listener.LocalPort)" } else { "" }
    bridge_pid = if ($listener) { $listener.OwningProcess } else { 0 }
    allowed_node_ip = $AllowedNodeIp
    ready_only = $true
    watcher_mode = "server-only-direct-http"
    watcher_pids = @($watcherProcesses | ForEach-Object { $_.ProcessId })
    stale_sub_payload_exposed = $false
}
$json = $receipt | ConvertTo-Json -Depth 5
$encoding = New-Object System.Text.UTF8Encoding($false)
[IO.File]::WriteAllText((Join-Path $ReceiptDir "ENGEL_MAIN_SUB_BRIDGE_LATEST.json"), $json, $encoding)
$json
