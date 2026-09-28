param(
    [string]$CtHost = "192.0.2.50",
    [int]$CtPort = 24622,
    [string]$CtUser = "root",
    [string]$RuntimeRoot = "/opt/engel",
    [int]$ServicePort = 8765,
    [string]$KeyPath = "$env:USERPROFILE\.ssh\engel_ai_main_ct246_ed25519"
)

$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$copyFiles = @(
    @{ Local = (Join-Path $ProjectRoot "tools\engel_main_server_chat_http_service.py"); Remote = "$RuntimeRoot/tools/engel_main_server_chat_http_service.py" },
    # The chat service imports this module at process start.  Omitting it makes
    # /rag/status fail with "No module named 'engel_rag_runtime'" even though
    # the UI and server routes were deployed successfully.
    @{ Local = (Join-Path $ProjectRoot "tools\engel_rag_runtime.py"); Remote = "$RuntimeRoot/tools/engel_rag_runtime.py" },
    @{ Local = (Join-Path $ProjectRoot "tools\engel_ai_systems_runtime.py"); Remote = "$RuntimeRoot/tools/engel_ai_systems_runtime.py" },
    @{ Local = (Join-Path $ProjectRoot "tools\engel_build_preference_dataset.py"); Remote = "$RuntimeRoot/tools/engel_build_preference_dataset.py" },
    @{ Local = (Join-Path $ProjectRoot "tools\engel_build_lane.py"); Remote = "$RuntimeRoot/tools/engel_build_lane.py" },
    @{ Local = (Join-Path $ProjectRoot "tools\engel_main_local_model_worker.py"); Remote = "$RuntimeRoot/tools/engel_main_local_model_worker.py" },
    @{ Local = (Join-Path $ProjectRoot "tools\engel_workspace_scaffold.py"); Remote = "$RuntimeRoot/tools/engel_workspace_scaffold.py" },
    @{ Local = (Join-Path $ProjectRoot "tools\engel_meeting_room_lan_server.py"); Remote = "$RuntimeRoot/tools/engel_meeting_room_lan_server.py" },
    @{ Local = (Join-Path $ProjectRoot "tools\engel_local_model_service.py"); Remote = "$RuntimeRoot/tools/engel_local_model_service.py" },
    @{ Local = (Join-Path $ProjectRoot "tools\engel_memory_search.py"); Remote = "$RuntimeRoot/tools/engel_memory_search.py" },
    @{ Local = (Join-Path $ProjectRoot "tools\run_engel_standalone_chat_llm.py"); Remote = "$RuntimeRoot/tools/run_engel_standalone_chat_llm.py" },
    @{ Local = (Join-Path $ProjectRoot "engel_vault_paths.py"); Remote = "$RuntimeRoot/engel_vault_paths.py" },
    @{ Local = (Join-Path $ProjectRoot "engel_large_chat_llm.py"); Remote = "$RuntimeRoot/engel_large_chat_llm.py" }
)

foreach ($item in $copyFiles) {
    $path = $item.Local
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Required service file missing: $path"
    }
}

if ($CtPort -lt 1 -or $CtPort -gt 65535) {
    throw "CtPort must be a TCP port from 1 to 65535."
}
if ($ServicePort -lt 1 -or $ServicePort -gt 65535) {
    throw "ServicePort must be a TCP port from 1 to 65535."
}

$sshCommonArgs = @("-o", "StrictHostKeyChecking=accept-new")
$scpCommonArgs = @("-o", "StrictHostKeyChecking=accept-new")
if ($KeyPath -and (Test-Path -LiteralPath $KeyPath -PathType Leaf)) {
    $ResolvedKeyPath = (Resolve-Path -LiteralPath $KeyPath).Path
    $sshCommonArgs = @("-i", $ResolvedKeyPath, "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=accept-new")
    $scpCommonArgs = @("-i", $ResolvedKeyPath, "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=accept-new")
}

$sshOk = Test-NetConnection -ComputerName $CtHost -Port $CtPort -InformationLevel Quiet -WarningAction SilentlyContinue
if (-not $sshOk) {
    throw "CT SSH route is not reachable: ${CtHost}:${CtPort}"
}

Write-Host "Copying Engel server chat service to ${CtUser}@${CtHost}:${RuntimeRoot}/tools"
& ssh @sshCommonArgs -p $CtPort "${CtUser}@${CtHost}" "mkdir -p '$RuntimeRoot/tools' '$RuntimeRoot/logs' '$RuntimeRoot/run'"
if ($LASTEXITCODE -ne 0) {
    throw "Remote directory prepare failed."
}

foreach ($item in $copyFiles) {
    & scp @scpCommonArgs -P $CtPort $item.Local "${CtUser}@${CtHost}:$($item.Remote)"
    if ($LASTEXITCODE -ne 0) {
        throw "Copy failed for $($item.Local)"
    }
}

$remote = @"
set -e
PY="$RuntimeRoot/.venv/bin/python"
if [ ! -x "`$PY" ]; then PY="python3"; fi
if systemctl cat engel-main-chat.service >/dev/null 2>&1; then
  install -d -m 0755 /etc/systemd/system/engel-main-chat.service.d
  printf '%s\n' '[Service]' 'Environment=ENGEL_LOCAL_CHAT_AUTO_BRIDGE_FALLBACK=1' > /etc/systemd/system/engel-main-chat.service.d/40-local-failure-provider-fallback.conf
  systemctl daemon-reload
  systemctl stop engel-main-chat.service 2>/dev/null || true
  pkill -f "engel_main_server_chat_http_service.py.*--port ${ServicePort}" 2>/dev/null || true
  systemctl reset-failed engel-main-chat.service 2>/dev/null || true
  systemctl start engel-main-chat.service
else
  pkill -f "engel_main_server_chat_http_service.py.*--port ${ServicePort}" 2>/dev/null || true
  export ENGEL_OPENAI_BRIDGE_ENABLED="`${ENGEL_OPENAI_BRIDGE_ENABLED:-1}"
  export ENGEL_CHATGPT_BROWSER_BRIDGE_ENABLED="`${ENGEL_CHATGPT_BROWSER_BRIDGE_ENABLED:-1}"
  export ENGEL_ANTHROPIC_BRIDGE_ENABLED="`${ENGEL_ANTHROPIC_BRIDGE_ENABLED:-1}"
  export ENGEL_CLAUDE_CLI_BRIDGE_ENABLED="`${ENGEL_CLAUDE_CLI_BRIDGE_ENABLED:-1}"
  export ENGEL_XAI_BRIDGE_ENABLED="`${ENGEL_XAI_BRIDGE_ENABLED:-1}"
  export ENGEL_GROK_CLI_BRIDGE_ENABLED="`${ENGEL_GROK_CLI_BRIDGE_ENABLED:-1}"
  export ENGEL_GEMINI_BRIDGE_ENABLED="`${ENGEL_GEMINI_BRIDGE_ENABLED:-1}"
  export ENGEL_GEMINI_API_BRIDGE_ENABLED="`${ENGEL_GEMINI_API_BRIDGE_ENABLED:-1}"
  export ENGEL_ROG_GEMINI_API_BRIDGE_URL="`${ENGEL_ROG_GEMINI_API_BRIDGE_URL:-http://127.0.0.1:24887}"
  export ENGEL_PROVIDER_BRIDGE_ERROR_AS_VISIBLE_REPLY="`${ENGEL_PROVIDER_BRIDGE_ERROR_AS_VISIBLE_REPLY:-0}"
  export ENGEL_LOCAL_CHAT_AUTO_BRIDGE_FALLBACK="`${ENGEL_LOCAL_CHAT_AUTO_BRIDGE_FALLBACK:-1}"
  export ENGEL_LOCAL_GGUF_MODEL="`${ENGEL_LOCAL_GGUF_MODEL:-$RuntimeRoot/models-active/llm/engel-qwen2.5-1.5b-deepreason/engel-qwen2.5-1.5b-deepreason-q5_k_m.gguf}"
  nohup "`$PY" "$RuntimeRoot/tools/engel_main_server_chat_http_service.py" --host 127.0.0.1 --port ${ServicePort} > "$RuntimeRoot/logs/engel_main_server_chat_http_service.log" 2>&1 &
  echo `$! > "$RuntimeRoot/run/engel_main_server_chat_http_service.pid"
fi
if systemctl is-active --quiet engel-agent-meeting-room.service 2>/dev/null; then
  systemctl restart engel-agent-meeting-room.service
fi
if systemctl is-active --quiet engel-memory-search.service 2>/dev/null; then
  systemctl restart engel-memory-search.service
fi
# Warm the embedding model and prove the index before declaring the deployment
# ready.  A process-only /health check used to leave the first RAG request to
# load the model and time out in the UI.
for attempt in 1 2 3 4 5; do
  if curl -fsS --max-time 60 -H 'Content-Type: application/json' \
    --data '{"query":"Engel AI Main CT246 runtime authority","k":1}' \
    'http://127.0.0.1:8940/search' >/dev/null; then
    break
  fi
  if [ "`$attempt" = 5 ]; then
    echo 'engel-memory-search failed its semantic warm probe' >&2
    exit 1
  fi
  sleep 2
done
curl -fsS "http://127.0.0.1:${ServicePort}/health"
"@
$remote = $remote -replace "`r`n", "`n"

Write-Host "Starting Engel server chat service on CT localhost:${ServicePort}"
$localTempScript = Join-Path ([System.IO.Path]::GetTempPath()) ("engel_start_main_chat_{0}.sh" -f ([System.Guid]::NewGuid().ToString("N")))
$remoteTempScript = "/tmp/engel_start_main_chat_$([System.Guid]::NewGuid().ToString("N")).sh"
try {
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($localTempScript, $remote, $utf8NoBom)
    & scp @scpCommonArgs -P $CtPort $localTempScript "${CtUser}@${CtHost}:$remoteTempScript"
    if ($LASTEXITCODE -ne 0) {
        throw "Remote start script copy failed."
    }
    & ssh @sshCommonArgs -p $CtPort "${CtUser}@${CtHost}" "bash '$remoteTempScript'; rc=`$?; rm -f '$remoteTempScript'; exit `$rc"
} finally {
    Remove-Item -LiteralPath $localTempScript -Force -ErrorAction SilentlyContinue
}
if ($LASTEXITCODE -ne 0) {
    throw "Remote service start or health check failed."
}

Write-Host ""
Write-Host "Engel server chat service is running on CT localhost:${ServicePort}."
Write-Host "Next, keep a tunnel open from the ROG laptop:"
Write-Host "  .\scripts\Start-EngelMainServerChatTunnel.ps1"
