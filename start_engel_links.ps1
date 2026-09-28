$ErrorActionPreference = "Stop"

$Root = "D:\b.WorkSpace\Engel App"
$Key = Join-Path $env:USERPROFILE ".ssh\engel_ct246_tunnel_key"
$Log = Join-Path $Root "logs\engel_links"

New-Item -ItemType Directory -Force $Log | Out-Null

Get-CimInstance Win32_Process | Where-Object {
    ($_.CommandLine -match "127\.0\.0\.1:24680:127\.0\.0\.1:8765") -or
    ($_.CommandLine -match "127\.0\.0\.1:24881:127\.0\.0\.1:24881") -or
    ($_.CommandLine -match "engel_rog_grok_cli_http_bridge.py")
} | ForEach-Object {
    try { Stop-Process -Id $_.ProcessId -Force } catch {}
}

Start-Sleep -Seconds 2

Start-Process -WindowStyle Hidden -FilePath "ssh.exe" -ArgumentList @(
    "-i", $Key,
    "-N",
    "-o", "ExitOnForwardFailure=yes",
    "-o", "ServerAliveInterval=30",
    "-o", "ServerAliveCountMax=3",
    "-o", "StrictHostKeyChecking=accept-new",
    "-L", "127.0.0.1:24680:127.0.0.1:8765",
    "-p", "24622",
    "root@engel-spine-01"
)

Start-Sleep -Seconds 3
"Engel CT246-only link started: $(Get-Date -Format s)" | Set-Content (Join-Path $Log "last_start.txt")
