param([int]$RelayPort = 24892, [int]$RemotePort = 24891, [string]$CtHost = "192.168.4.50", [int]$CtPort = 24622, [string]$CtUser = "root", [string]$KeyPath = (Join-Path $env:USERPROFILE ".ssh\engel_ai_main_ct246_ed25519"), [int]$ReconnectSeconds = 15)
# OpenRouter relay + reverse tunnel (CT246 127.0.0.1:24891 -> ROG 127.0.0.1:24892).
# Mirrors Start-EngelMainServerChatTunnelPersistent.ps1. Local 24890 is reserved for Grok Imagine.
$App = Split-Path $PSScriptRoot -Parent
$Py = Join-Path $App "runtime\python310\pythonw.exe"
$Launch = Join-Path $App "tools\engel_hidden_launch.py"
$Relay = Join-Path $App "tools\engel_openrouter_bridge_http_service.py"
$Log = Join-Path $App "reports\codex_bridge\openrouter_relay_tunnel.log"
function Log([string]$m) { Add-Content -LiteralPath $Log -Value ("{0} {1}" -f (Get-Date -Format s), $m) }
function Ensure-Relay {
    try { Invoke-WebRequest "http://127.0.0.1:$RelayPort/health" -UseBasicParsing -TimeoutSec 3 | Out-Null; return } catch {}
    Start-Process -FilePath $Py -ArgumentList "`"$Launch`"","script","`"$Relay`"","--port",$RelayPort -WorkingDirectory $App
    Log "OpenRouter relay started on 127.0.0.1:$RelayPort"
    Start-Sleep -Seconds 3
}
do {
    Ensure-Relay
    Log "Opening tunnel CT:$RemotePort -> ROG:$RelayPort"
    & ssh -i $KeyPath -N -o BatchMode=yes -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=3 -o StrictHostKeyChecking=accept-new -R "127.0.0.1:${RemotePort}:127.0.0.1:${RelayPort}" -p $CtPort "${CtUser}@${CtHost}"
    Log "Tunnel exited with code $LASTEXITCODE"
    Start-Sleep -Seconds $ReconnectSeconds
} while ($true)
