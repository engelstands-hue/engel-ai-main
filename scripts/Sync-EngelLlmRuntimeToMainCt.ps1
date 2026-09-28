[CmdletBinding()]
param(
    [string]$CtHost = "192.0.2.50",
    [int]$CtPort = 24622,
    [string]$CtUser = "root",
    [string]$RuntimeRoot = "/opt/engel",
    [string]$VaultRoot = "/opt/engel/models-active",
    [string]$KeyPath = "$env:USERPROFILE\.ssh\engel_ai_main_ct246_ed25519",
    [switch]$InstallPythonRuntime,
    [switch]$AllowVaultUse
)

$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$Stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$StageRoot = Join-Path $ProjectRoot "runtime\temp\engel_llm_ct_sync_$Stamp"
$ReceiptDir = Join-Path $ProjectRoot "reports\ct_sync"
$ResolvedKeyPath = (Resolve-Path -LiteralPath $KeyPath).Path

$OfflineCt245Mount = "/mnt/" + "engel-vault"
if (-not $AllowVaultUse -and $VaultRoot.TrimEnd("/") -eq $OfflineCt245Mount) {
    throw "CT245 offline-vault storage is disabled. Use CT246 SSD /opt/engel or Dell HDD /mnt/engel-hdd-vault."
}

New-Item -ItemType Directory -Force -Path $StageRoot, $ReceiptDir | Out-Null

function Write-Utf8NoBom {
    param(
        [string]$Path,
        [string]$Text
    )
    $encoding = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $Text, $encoding)
}

function Assert-NotSecretPath {
    param([string]$Path)
    $clean = $Path.ToLowerInvariant()
    if ($clean -match "\\secrets(\\|$)" -or $clean -match "/secrets(/|$)") {
        throw "Refusing to copy secrets path to CT: $Path"
    }
}

function Invoke-Ct {
    param([string]$Command)
    & ssh -i $ResolvedKeyPath -p $CtPort -o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new "${CtUser}@${CtHost}" $Command
    if ($LASTEXITCODE -ne 0) {
        throw "CT command failed: $Command"
    }
}

function Copy-ToCt {
    param(
        [string]$LocalPath,
        [string]$RemotePath
    )
    Assert-NotSecretPath $LocalPath
    if (-not (Test-Path -LiteralPath $LocalPath -PathType Leaf)) {
        throw "Required local file missing: $LocalPath"
    }
    $remoteDir = [System.IO.Path]::GetDirectoryName($RemotePath).Replace("\", "/")
    Invoke-Ct "mkdir -p '$remoteDir'"
    & scp -i $ResolvedKeyPath -P $CtPort -o BatchMode=yes -o StrictHostKeyChecking=accept-new -- $LocalPath "${CtUser}@${CtHost}:$RemotePath"
    if ($LASTEXITCODE -ne 0) {
        throw "SCP failed: $LocalPath -> $RemotePath"
    }
}

Write-Host "Checking CT SSD runtime paths."
Invoke-Ct "test -d '$RuntimeRoot' && mkdir -p '$VaultRoot' && df -h '$RuntimeRoot'"

$codeFiles = @(
    @{ Local = "tools\engel_main_server_chat_http_service.py"; Remote = "$RuntimeRoot/tools/engel_main_server_chat_http_service.py" },
    @{ Local = "tools\engel_local_model_service.py"; Remote = "$RuntimeRoot/tools/engel_local_model_service.py" },
    @{ Local = "tools\run_engel_standalone_chat_llm.py"; Remote = "$RuntimeRoot/tools/run_engel_standalone_chat_llm.py" },
    @{ Local = "engel_vault_paths.py"; Remote = "$RuntimeRoot/engel_vault_paths.py" },
    @{ Local = "engel_large_chat_llm.py"; Remote = "$RuntimeRoot/engel_large_chat_llm.py" },
    @{ Local = "engel_llama_cli_runner.py"; Remote = "$RuntimeRoot/engel_llama_cli_runner.py" }
)

Write-Host "Deploying patched Engel chat/runtime code."
foreach ($item in $codeFiles) {
    Copy-ToCt (Join-Path $ProjectRoot $item.Local) $item.Remote
}

# (20260711 fix) live CT layout is /opt/engel/models-active/llm/<model>/ — the /llm/
# layer was missing from every model path, so these all resolved to nonexistent files
# and the script wrote dead paths into the live manifest + drop-in.
$registeredModels = @(
    "$VaultRoot/llm/qwen2.5-7b-instruct/qwen2.5-7b-instruct-q5_k_m.gguf",
    "$VaultRoot/llm/qwen2.5-coder-3b-instruct/qwen2.5-coder-3b-instruct-q5_k_m.gguf",
    "$VaultRoot/llm/qwen2.5-3b-instruct/qwen2.5-3b-instruct-q5_k_m.gguf",
    "$VaultRoot/llm/qwen2.5-0.5b-instruct/qwen2.5-0.5b-instruct-q5_k_m.gguf",
    "$VaultRoot/llm/mistral-7b-instruct-v0.3/Mistral-7B-Instruct-v0.3-Q4_K_M.gguf"
)

Write-Host "Registering CT246 SSD model paths; retired external E/F/G sources are not used."
$copiedModels = @()
foreach ($remoteModel in $registeredModels) {
    $exists = & ssh -i $ResolvedKeyPath -p $CtPort -o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new "${CtUser}@${CtHost}" "test -f '$remoteModel'"
    if ($LASTEXITCODE -eq 0) {
        $copiedModels += $remoteModel
    } else {
        Write-Warning "CT model path not present yet: $remoteModel"
    }
}

$loraName = "engel_standalone_lora_adapter_vipybdo0pgm6fl_20260704T233142Z"
$loraLocalDir = Join-Path $ProjectRoot "runtime\engel_lora_training_artifacts\$loraName"
# (20260711 fix) the live adapter home is models-active/lora/<adapter>, not the
# runpod/standalone_chat_llm chat-workspace dir (which holds receipts, not weights).
$loraRemoteDir = "$VaultRoot/lora/$loraName"
if (-not (Test-Path -LiteralPath $loraLocalDir -PathType Container)) {
    throw "LoRA artifact directory missing: $loraLocalDir"
}

Write-Host "Copying trained RunPod LoRA adapter artifacts to CT vault."
Get-ChildItem -LiteralPath $loraLocalDir -File | ForEach-Object {
    Copy-ToCt $_.FullName "$loraRemoteDir/$($_.Name)"
}

$sourceManifestPath = Join-Path $ProjectRoot "runtime\engel_standalone_chat_llm\trained_lora_adapter_manifest.json"
if (-not (Test-Path -LiteralPath $sourceManifestPath -PathType Leaf)) {
    throw "Trained LoRA manifest missing."
}

$manifest = Get-Content -LiteralPath $sourceManifestPath -Raw | ConvertFrom-Json
$baseRemote = "$VaultRoot/llm/qwen2.5-7b-instruct/qwen2.5-7b-instruct-q5_k_m.gguf"
$manifest.local_artifact_dir = $loraRemoteDir
$manifest.external_artifact_dir = $loraRemoteDir
$manifest.serving_base_gguf_model_path = $baseRemote
$manifest.conversion_receipt_path = "$loraRemoteDir/ENGEL_LORA_GGUF_CONVERSION_RECEIPT.json"
$manifest | Add-Member -NotePropertyName "ct_runtime_registered_at_utc" -NotePropertyValue ((Get-Date).ToUniversalTime().ToString("o")) -Force
$manifest | Add-Member -NotePropertyName "ct_runtime_root" -NotePropertyValue $RuntimeRoot -Force
$manifest | Add-Member -NotePropertyName "ct_vault_root" -NotePropertyValue $VaultRoot -Force

$ctManifestLocal = Join-Path $StageRoot "trained_lora_adapter_manifest.ct.json"
Write-Utf8NoBom $ctManifestLocal ($manifest | ConvertTo-Json -Depth 12)
Copy-ToCt $ctManifestLocal "$RuntimeRoot/runtime/engel_standalone_chat_llm/trained_lora_adapter_manifest.json"

$largeManifestSource = Join-Path $ProjectRoot "memory\models\ENGEL_LARGE_CHAT_LLM_MANIFEST.json"
if (Test-Path -LiteralPath $largeManifestSource -PathType Leaf) {
    $largeManifest = Get-Content -LiteralPath $largeManifestSource -Raw | ConvertFrom-Json
} else {
    $largeManifest = [pscustomobject]@{
        schema = "engel_large_chat_llm_manifest_v1"
        enabled_for_local_chat_when_present = $true
        minimum_model_store_gib = 0
        minimum_model_bytes = 0
        active_model_path = ""
        download_enabled = $false
        provider_calls_enabled = $false
        runpod_api_enabled = $false
    }
}
$largeManifest.model_store_root = "$VaultRoot/llm"
$largeManifest.extra_model_roots = @(
    "$VaultRoot",
    "$VaultRoot/llm",
    "/mnt/engel-hdd-vault/models-archive/llm"
)
$largeManifest.runpod_handoff_root = "$RuntimeRoot/runpod/large_chat_llm"
$largeManifest | Add-Member -NotePropertyName "ct_registered_at_utc" -NotePropertyValue ((Get-Date).ToUniversalTime().ToString("o")) -Force
$ctLargeManifestLocal = Join-Path $StageRoot "ENGEL_LARGE_CHAT_LLM_MANIFEST.ct.json"
Write-Utf8NoBom $ctLargeManifestLocal ($largeManifest | ConvertTo-Json -Depth 12)
Copy-ToCt $ctLargeManifestLocal "$RuntimeRoot/memory/models/ENGEL_LARGE_CHAT_LLM_MANIFEST.json"

$optionalMemoryFiles = @(
    @{ Local = "memory\personality\ENGEL_CHAT_PROVIDER_CONFIG.json"; Remote = "$RuntimeRoot/memory/personality/ENGEL_CHAT_PROVIDER_CONFIG.json" },
    @{ Local = "memory\personality\ENGEL_AI_MERGED_PERSONALITY.md"; Remote = "$RuntimeRoot/memory/personality/ENGEL_AI_MERGED_PERSONALITY.md" },
    @{ Local = "memory\models\ENGEL_EXTERNAL_MODEL_REGISTRY.json"; Remote = "$RuntimeRoot/memory/models/ENGEL_EXTERNAL_MODEL_REGISTRY.json" }
)
foreach ($item in $optionalMemoryFiles) {
    $local = Join-Path $ProjectRoot $item.Local
    if (Test-Path -LiteralPath $local -PathType Leaf) {
        Copy-ToCt $local $item.Remote
    }
}

if ($InstallPythonRuntime) {
    Write-Host "Installing CT Python inference runtime. This can take several minutes."
    Invoke-Ct "apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y cmake ninja-build python3-dev build-essential pkg-config"
    Invoke-Ct "'$RuntimeRoot/.venv/bin/python' -m pip install --no-cache-dir --upgrade numpy llama-cpp-python"
}

$dropIn = @"
set -e
mkdir -p /etc/systemd/system/engel-main-chat.service.d
cat > /etc/systemd/system/engel-main-chat.service.d/10-engel-runtime.conf <<'EOF'
[Service]
Environment=ENGEL_VAULT_MEMORY_ROOT=$VaultRoot
Environment=ENGEL_TRAINED_LORA_MANIFEST=$RuntimeRoot/runtime/engel_standalone_chat_llm/trained_lora_adapter_manifest.json
Environment=ENGEL_TRAINED_LORA_ARTIFACT_DIR=$loraRemoteDir
Environment=ENGEL_TRAINED_LORA_ADAPTER_GGUF=$loraRemoteDir/adapter_model.gguf
Environment=ENGEL_TRAINED_LORA_BASE_GGUF_MODEL=$baseRemote
Environment=ENGEL_LOCAL_GGUF_MODEL=$VaultRoot/llm/qwen2.5-coder-3b-instruct/qwen2.5-coder-3b-instruct-q5_k_m.gguf
Environment=ENGEL_LARGE_CHAT_LLM_ROOTS=${VaultRoot}:${VaultRoot}/llm:/mnt/engel-hdd-vault/models-archive/llm
Environment=ENGEL_LLAMA_CPP_RUNTIME_ROOTS=/opt/engel/runtime/llama.cpp:$RuntimeRoot/runtime/llama.cpp
Environment=ENGEL_MAIN_LOCAL_MODEL_N_GPU_LAYERS=0
Environment=ENGEL_MAIN_LOCAL_MODEL_CTX=4096
Environment=ENGEL_STANDALONE_CHAT_PROVIDER=local
EOF
systemctl daemon-reload
systemctl restart engel-main-chat.service
sleep 2
systemctl is-active engel-main-chat.service
curl -fsS http://127.0.0.1:8765/health >/tmp/engel-main-chat-health.json
"@

Write-Host "Registering CT service environment and restarting existing chat service."
$dropInPath = Join-Path $StageRoot "register_chat_runtime_dropin.sh"
Write-Utf8NoBom $dropInPath $dropIn
& scp -i $ResolvedKeyPath -P $CtPort -o BatchMode=yes -o StrictHostKeyChecking=accept-new -- $dropInPath "${CtUser}@${CtHost}:/tmp/register_chat_runtime_dropin.sh"
if ($LASTEXITCODE -ne 0) {
    throw "Failed to copy CT service drop-in registration script."
}
& ssh -i $ResolvedKeyPath -p $CtPort -o BatchMode=yes -o StrictHostKeyChecking=accept-new "${CtUser}@${CtHost}" "bash /tmp/register_chat_runtime_dropin.sh"
if ($LASTEXITCODE -ne 0) {
    throw "Failed to register CT service environment."
}

$remoteHealth = & ssh -i $ResolvedKeyPath -p $CtPort -o BatchMode=yes -o StrictHostKeyChecking=accept-new "${CtUser}@${CtHost}" "cat /tmp/engel-main-chat-health.json"
if ($LASTEXITCODE -ne 0) {
    throw "Failed to read CT chat health."
}

$receipt = [ordered]@{
    schema = "engel_llm_runtime_ct_sync_receipt_v1"
    ok = $true
    updated_at_utc = (Get-Date).ToUniversalTime().ToString("o")
    ct_host = $CtHost
    ct_port = $CtPort
    runtime_root = $RuntimeRoot
    vault_root = $VaultRoot
    copied_models = $copiedModels
    lora_remote_dir = $loraRemoteDir
    trained_lora_manifest = "$RuntimeRoot/runtime/engel_standalone_chat_llm/trained_lora_adapter_manifest.json"
    base_model = $baseRemote
    install_python_runtime_requested = [bool]$InstallPythonRuntime
    health = ($remoteHealth | ConvertFrom-Json)
}
$receiptPath = Join-Path $ReceiptDir "ENGEL_LLM_RUNTIME_CT_SYNC_$Stamp.json"
Write-Utf8NoBom $receiptPath ($receipt | ConvertTo-Json -Depth 12)
Write-Host "LLM CT sync receipt: $receiptPath"
Write-Host "CT chat health:"
$remoteHealth
