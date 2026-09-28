# Starts the Engel Grok Imagine HTTP service on the ROG (LAN port 24890).
# Idempotent: if the port already answers /health, leaves it alone.
$ErrorActionPreference = "Stop"
$root = "D:\b.WorkSpace\Engel App"
$py = Join-Path $root "runtime\python310\python.exe"
$svc = Join-Path $root "tools\engel_grok_imagine_http_service.py"
$logDir = Join-Path $root "runtime\grok_imagine"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Force $logDir | Out-Null }
$log = Join-Path $logDir "imagine_http_service.log"

try {
    $health = Invoke-RestMethod -Uri "http://127.0.0.1:24890/health" -TimeoutSec 3
    if ($health.ok) { Write-Output "Engel Grok Imagine service already healthy on 24890."; exit 0 }
} catch { }

Start-Process -FilePath $py -ArgumentList "`"$svc`"" -WindowStyle Hidden `
    -RedirectStandardOutput $log -RedirectStandardError ($log + ".err") -WorkingDirectory $root
Start-Sleep -Seconds 3
try {
    $health = Invoke-RestMethod -Uri "http://127.0.0.1:24890/health" -TimeoutSec 5
    Write-Output "Engel Grok Imagine service started on 24890 (busy=$($health.busy))."
} catch {
    Write-Output "Engel Grok Imagine service did not answer /health after start: $_"
    exit 1
}
