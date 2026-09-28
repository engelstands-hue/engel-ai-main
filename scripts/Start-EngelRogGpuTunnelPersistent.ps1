<#
.SYNOPSIS
  Persistent reverse SSH tunnel exposing the ROG GPU model server
  (127.0.0.1:8899) to CT246 at 127.0.0.1:8899, so the CT chat service can route
  its large-chat lane to the ROG GPU. Auto-reconnects on drop. Single-instance.
#>
$ErrorActionPreference = "Continue"
$createdNew = $false
$mutex = New-Object System.Threading.Mutex($true, "Local\EngelRogGpuTunnel", [ref]$createdNew)
if (-not $createdNew) { return }
$key = Join-Path $env:USERPROFILE ".ssh\engel_ai_main_ct246_ed25519"
$log = Join-Path $env:LOCALAPPDATA "Engel AI Main\logs\rog-gpu-tunnel.log"
New-Item -ItemType Directory -Force -Path (Split-Path $log) | Out-Null
try {
    while ($true) {
        "[$(Get-Date -Format s)] connecting reverse tunnels ROG:8899+8931 -> CT246:8899+8931" | Add-Content -LiteralPath $log
        & ssh -i "$key" -o BatchMode=yes -o StrictHostKeyChecking=accept-new `
            -o ServerAliveInterval=30 -o ServerAliveCountMax=3 -o ExitOnForwardFailure=yes `
            -p 24622 -N -R 8899:127.0.0.1:8899 -R 8931:127.0.0.1:8931 root@192.0.2.50 *>> $log
        "[$(Get-Date -Format s)] tunnel dropped; reconnecting in 5s" | Add-Content -LiteralPath $log
        Start-Sleep -Seconds 5
    }
} finally {
    if ($createdNew) { $mutex.ReleaseMutex() }
    $mutex.Dispose()
}
