param(
    [string]$CtHost = "192.0.2.50",
    [int]$CtPort = 24622,
    [string]$RemoteUser = "root",
    [string]$KeyPath = (Join-Path $env:USERPROFILE ".ssh\engel_ai_main_ct246_ed25519"),
    [switch]$SkipBuild,
    [switch]$NoRestart
)

$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$ResolvedKeyPath = [System.IO.Path]::GetFullPath($KeyPath)
$Stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$ReceiptDir = Join-Path $ProjectRoot "reports\ct_sync"
$ReceiptPath = Join-Path $ReceiptDir ("ENGEL_WORKSPACE_SYSTEM_MAP_SYNC_" + $Stamp + ".json")

function Require-File {
    param([string]$RelativePath)
    $path = Join-Path $ProjectRoot $RelativePath
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Required file missing: $RelativePath"
    }
    return $path
}

if (-not (Test-Path -LiteralPath $ResolvedKeyPath -PathType Leaf)) {
    throw "Missing CT SSH key: $ResolvedKeyPath"
}

$tcpOk = Test-NetConnection -ComputerName $CtHost -Port $CtPort -InformationLevel Quiet -WarningAction SilentlyContinue
if (-not $tcpOk) {
    throw "Engel AI Main CT SSH route is not reachable: ${CtHost}:${CtPort}"
}

if (-not $SkipBuild) {
    $builder = Require-File "tools\build_engel_workspace_system_registry.py"
    & python $builder
    if ($LASTEXITCODE -ne 0) {
        throw "Workspace registry build failed."
    }
}

$files = @(
    @{ src = "runtime\engel_workspace_system_registry.json"; dest = "/opt/engel/runtime/" },
    @{ src = "runtime\engel_workspace_orchestration_map.json"; dest = "/opt/engel/runtime/" },
    @{ src = "runtime\engel_workspace_full_manifest.jsonl"; dest = "/opt/engel/runtime/" },
    @{ src = "reports\codex_bridge\ENGEL_WORKSPACE_SYSTEM_REGISTRY.md"; dest = "/opt/engel/reports/codex_bridge/" },
    @{ src = "reports\codex_bridge\ENGEL_WORKSPACE_ORCHESTRATION_MAP.md"; dest = "/opt/engel/reports/codex_bridge/" },
    @{ src = "reports\codex_bridge\ENGEL_WORKSPACE_FULL_MANIFEST_SUMMARY.md"; dest = "/opt/engel/reports/codex_bridge/" },
    @{ src = "reports\codex_bridge\ENGEL_WORKSPACE_ONE_SYSTEM_INTEGRATION_20260629.md"; dest = "/opt/engel/reports/codex_bridge/" },
    @{ src = "tools\engel_chat_humanizer.py"; dest = "/opt/engel/tools/" },
    @{ src = "tools\build_engel_workspace_system_registry.py"; dest = "/opt/engel/tools/" },
    @{ src = "tools\engel_main_server_chat_http_service.py"; dest = "/opt/engel/tools/" }
)

$sshBase = @(
    "-i", $ResolvedKeyPath,
    "-p", "$CtPort",
    "-o", "BatchMode=yes",
    "-o", "ConnectTimeout=8",
    "-o", "StrictHostKeyChecking=accept-new",
    "${RemoteUser}@${CtHost}"
)
$scpBase = @(
    "-i", $ResolvedKeyPath,
    "-P", "$CtPort",
    "-o", "BatchMode=yes",
    "-o", "ConnectTimeout=8",
    "-o", "StrictHostKeyChecking=accept-new"
)

& ssh @sshBase "mkdir -p /opt/engel/runtime /opt/engel/reports/codex_bridge /opt/engel/tools /opt/engel/run/receipts"
if ($LASTEXITCODE -ne 0) {
    throw "Remote directory preparation failed."
}

$copied = New-Object System.Collections.Generic.List[object]
foreach ($item in $files) {
    $srcPath = Require-File $item.src
    $remoteSpec = "${RemoteUser}@${CtHost}:$($item.dest)"
    & scp @scpBase $srcPath $remoteSpec
    if ($LASTEXITCODE -ne 0) {
        throw "scp failed for $($item.src)"
    }
    $copied.Add([ordered]@{
        source = $item.src
        destination = $item.dest
        bytes = (Get-Item -LiteralPath $srcPath).Length
    }) | Out-Null
}

$verifyCmd = @"
set -euo pipefail
python3 -m json.tool /opt/engel/runtime/engel_workspace_system_registry.json >/dev/null
python3 -m json.tool /opt/engel/runtime/engel_workspace_orchestration_map.json >/dev/null
test -s /opt/engel/runtime/engel_workspace_full_manifest.jsonl
test -s /opt/engel/reports/codex_bridge/ENGEL_WORKSPACE_SYSTEM_REGISTRY.md
test -s /opt/engel/reports/codex_bridge/ENGEL_WORKSPACE_ORCHESTRATION_MAP.md
test -s /opt/engel/tools/engel_chat_humanizer.py
test -s /opt/engel/tools/engel_main_server_chat_http_service.py
python3 -m py_compile /opt/engel/tools/engel_chat_humanizer.py /opt/engel/tools/engel_main_server_chat_http_service.py
wc -l /opt/engel/runtime/engel_workspace_full_manifest.jsonl
"@

$verifyOut = & ssh @sshBase $verifyCmd 2>&1
if ($LASTEXITCODE -ne 0) {
    throw "Remote workspace map verification failed: $verifyOut"
}

$serviceStatus = ""
if (-not $NoRestart) {
    $serviceStatus = (& ssh @sshBase "systemctl restart engel-main-chat.service && systemctl is-active engel-main-chat.service" 2>&1 | Out-String).Trim()
    if ($LASTEXITCODE -ne 0) {
        throw "Remote chat service restart failed: $serviceStatus"
    }
}

New-Item -ItemType Directory -Force -Path $ReceiptDir | Out-Null
$receipt = [ordered]@{
    schema = "engel_workspace_system_map_sync_v1"
    ok = $true
    created_at_utc = (Get-Date).ToUniversalTime().ToString("o")
    project_root = $ProjectRoot
    ct_host = $CtHost
    ct_port = $CtPort
    remote_runtime_root = "/opt/engel"
    copied = $copied
    remote_verify_output = (($verifyOut | Out-String).Trim())
    chat_service_status = $serviceStatus
    storage_mutation_performed = $false
    pct_set_performed = $false
    disk_format_performed = $false
}
$receipt | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $ReceiptPath -Encoding UTF8
Write-Host "ENGEL_WORKSPACE_SYSTEM_MAP_SYNCED_TO_CT_246"
Write-Host "Receipt: $ReceiptPath"
Write-Host "Remote verify: $($receipt.remote_verify_output)"
if (-not $NoRestart) {
    Write-Host "Chat service: $serviceStatus"
}
