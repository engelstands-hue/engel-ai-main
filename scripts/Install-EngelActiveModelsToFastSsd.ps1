[CmdletBinding()]
param(
    [string]$CtHost = "192.0.2.50",
    [int]$CtPort = 24622,
    [string]$CtUser = "root",
    [string]$RuntimeRoot = "/opt/engel",
    [string]$VaultRoot = "/mnt/engel-hdd-vault",
    [string]$KeyPath = (Join-Path $env:USERPROFILE ".ssh\engel_ai_main_ct246_ed25519"),
    [switch]$AllowVaultUse
)

$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$RuntimeDir = Join-Path $ProjectRoot "runtime\fast_ssd_models"
$ReceiptDir = Join-Path $ProjectRoot "reports\ct_sync"
$Stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$ResolvedKeyPath = [System.IO.Path]::GetFullPath($KeyPath)

if (-not (Test-Path -LiteralPath $ResolvedKeyPath -PathType Leaf)) {
    throw "Engel CT SSH key missing: $ResolvedKeyPath"
}
$OfflineCt245Mount = "/mnt/" + "engel-vault"
if (-not $AllowVaultUse -and $VaultRoot.TrimEnd("/") -eq $OfflineCt245Mount) {
    throw "CT245 offline-vault storage is disabled. Use CT246 SSD /opt/engel or Dell HDD /mnt/engel-hdd-vault."
}
New-Item -ItemType Directory -Force -Path $RuntimeDir, $ReceiptDir | Out-Null

function Write-Utf8NoBom {
    param([string]$Path, [string]$Text)
    $encoding = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $Text, $encoding)
}

$RemoteScriptPath = "$RuntimeRoot/cache/install_engel_active_models_fast_ssd_$Stamp.sh"
$LocalScriptPath = Join-Path $RuntimeDir "install_engel_active_models_fast_ssd_$Stamp.sh"

$Script = @"
#!/usr/bin/env bash
set -euo pipefail

RUNTIME_ROOT="$RuntimeRoot"
VAULT_ROOT="$VaultRoot"
SSD_ROOT="`$RUNTIME_ROOT/models-active"
LLM_ROOT="`$SSD_ROOT/llm"
LORA_NAME="engel_standalone_lora_adapter_vipybdo0pgm6fl_20260704T233142Z"
LORA_SRC="`$VAULT_ROOT/training-outputs/runpod/standalone_chat_llm/`$LORA_NAME"
LORA_DST="`$SSD_ROOT/lora/`$LORA_NAME"
MANIFEST="`$RUNTIME_ROOT/runtime/engel_standalone_chat_llm/trained_lora_adapter_manifest.json"
LARGE_MANIFEST="`$RUNTIME_ROOT/memory/models/ENGEL_LARGE_CHAT_LLM_MANIFEST.json"
REPORT="`$RUNTIME_ROOT/reports/ENGEL_FAST_SSD_MODEL_ACTIVATION_$Stamp.json"

mkdir -p "`$LLM_ROOT" "`$LORA_DST" "`$RUNTIME_ROOT/cache" "`$RUNTIME_ROOT/runtime/engel_standalone_chat_llm" "`$RUNTIME_ROOT/memory/models" "`$RUNTIME_ROOT/reports"

copy_model() {
  local src="`$1"
  local rel="`$2"
  local dst="`$LLM_ROOT/`$rel"
  # (20260711 fix) check the DESTINATION first: if the model is already resident on
  # the SSD it is present regardless of whether the vault source still exists. The
  # old source-first check exited 3 on the first model whenever the archive source
  # was absent (which it now is — vault holds cosmos3-originals only), aborting the
  # whole deploy even though every target was already in place.
  mkdir -p "`$(dirname "`$dst")"
  if [ -f "`$dst" ] && [ -s "`$dst" ]; then
    echo "already-present `$dst"
    return 0
  fi
  if [ ! -f "`$src" ]; then
    echo "Missing model on SSD and no vault source to copy from: `$dst (src `$src)" >&2
    exit 3
  fi
  echo "copy `$src -> `$dst"
  cp -f "`$src" "`$dst"
  sync -f "`$dst" || true
}

copy_model "`$VAULT_ROOT/models-archive/llm/qwen2.5-7b-instruct/qwen2.5-7b-instruct-q5_k_m.gguf" "qwen2.5-7b-instruct/qwen2.5-7b-instruct-q5_k_m.gguf"
copy_model "`$VAULT_ROOT/models-archive/llm/qwen2.5-7b-instruct/qwen2.5-7b-instruct-q5_k_m-00001-of-00002.gguf" "qwen2.5-7b-instruct/qwen2.5-7b-instruct-q5_k_m-00001-of-00002.gguf"
copy_model "`$VAULT_ROOT/models-archive/llm/qwen2.5-7b-instruct/qwen2.5-7b-instruct-q5_k_m-00002-of-00002.gguf" "qwen2.5-7b-instruct/qwen2.5-7b-instruct-q5_k_m-00002-of-00002.gguf"
copy_model "`$VAULT_ROOT/models-archive/llm/qwen2.5-coder-3b-instruct/qwen2.5-coder-3b-instruct-q5_k_m.gguf" "qwen2.5-coder-3b-instruct/qwen2.5-coder-3b-instruct-q5_k_m.gguf"
copy_model "`$VAULT_ROOT/models-archive/llm/qwen2.5-3b-instruct/qwen2.5-3b-instruct-q5_k_m.gguf" "qwen2.5-3b-instruct/qwen2.5-3b-instruct-q5_k_m.gguf"
copy_model "`$VAULT_ROOT/models-archive/llm/qwen2.5-0.5b-instruct/qwen2.5-0.5b-instruct-q5_k_m.gguf" "qwen2.5-0.5b-instruct/qwen2.5-0.5b-instruct-q5_k_m.gguf"
copy_model "`$VAULT_ROOT/models-archive/llm/mistral-7b-instruct-v0.3/Mistral-7B-Instruct-v0.3-Q4_K_M.gguf" "mistral-7b-instruct-v0.3/Mistral-7B-Instruct-v0.3-Q4_K_M.gguf"

if [ ! -d "`$LORA_SRC" ]; then
  echo "Missing required LoRA artifact directory: `$LORA_SRC" >&2
  exit 4
fi
cp -a "`$LORA_SRC/." "`$LORA_DST/"

BASE_MODEL="`$LLM_ROOT/qwen2.5-7b-instruct/qwen2.5-7b-instruct-q5_k_m.gguf"
CODER_MODEL="`$LLM_ROOT/qwen2.5-coder-3b-instruct/qwen2.5-coder-3b-instruct-q5_k_m.gguf"
ADAPTER_MODEL="`$LORA_DST/adapter_model.gguf"

python3 - <<PY
import json
from pathlib import Path

manifest_path = Path("`$MANIFEST")
manifest = {}
if manifest_path.is_file():
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
manifest.update({
    "local_artifact_dir": "`$LORA_DST",
    "external_artifact_dir": "`$LORA_DST",
    "serving_base_gguf_model_path": "`$BASE_MODEL",
    "ct_fast_ssd_models_active": True,
    "ct_fast_ssd_model_root": "`$LLM_ROOT",
    "ct_fast_ssd_registered_at_utc": "$Stamp",
})
adapter = manifest.get("adapter_model_gguf")
if not isinstance(adapter, dict):
    adapter = {}
adapter["path"] = "adapter_model.gguf"
adapter["absolute_path"] = "`$ADAPTER_MODEL"
manifest["adapter_model_gguf"] = adapter
manifest_path.parent.mkdir(parents=True, exist_ok=True)
manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

large_path = Path("`$LARGE_MANIFEST")
large = {}
if large_path.is_file():
    large = json.loads(large_path.read_text(encoding="utf-8-sig"))
large.update({
    "model_store_root": "`$LLM_ROOT",
    "active_model_path": "`$BASE_MODEL",
    "selected_model_path": "`$BASE_MODEL",
    "selected_model_present": True,
    "enabled_for_local_chat_when_present": True,
    "minimum_model_store_gib": 0,
    "minimum_model_bytes": 0,
    "active_runtime_storage": "engel-fast-ssd",
    "vault_used_for_active_models": False,
    "ct_fast_ssd_registered_at_utc": "$Stamp",
    "extra_model_roots": ["`$LLM_ROOT"],
})
large_path.parent.mkdir(parents=True, exist_ok=True)
large_path.write_text(json.dumps(large, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

mkdir -p /etc/systemd/system/engel-main-chat.service.d
cat > /etc/systemd/system/engel-main-chat.service.d/20-fast-ssd-models.conf <<EOF
[Service]
Environment=ENGEL_ACTIVE_MODEL_STORAGE=engel-fast-ssd
Environment=ENGEL_MODELS_ACTIVE_ROOT=`$SSD_ROOT
Environment=ENGEL_TRAINED_LORA_MANIFEST=`$MANIFEST
Environment=ENGEL_TRAINED_LORA_ARTIFACT_DIR=`$LORA_DST
Environment=ENGEL_TRAINED_LORA_ADAPTER_GGUF=`$ADAPTER_MODEL
Environment=ENGEL_TRAINED_LORA_BASE_GGUF_MODEL=`$BASE_MODEL
Environment=ENGEL_LOCAL_GGUF_MODEL=`$CODER_MODEL
Environment=ENGEL_LARGE_CHAT_LLM_ROOTS=`$LLM_ROOT
Environment=ENGEL_STANDALONE_CHAT_PROVIDER=local
EOF

systemctl daemon-reload
systemctl restart engel-main-chat.service
sleep 2

python3 - <<PY
import json, os, subprocess
from pathlib import Path
files = [p for p in Path("`$SSD_ROOT").rglob("*") if p.is_file()]
ggufs = [p for p in files if p.suffix.lower() == ".gguf"]
report = {
    "schema": "engel_fast_ssd_model_activation_v1",
    "ok": True,
    "updated_at_utc": "$Stamp",
    "runtime_root": "`$RUNTIME_ROOT",
    "active_model_root": "`$SSD_ROOT",
    "active_model_storage": "engel-fast-ssd",
    "vault_used_for_active_models": False,
    "gguf_count": len(ggufs),
    "total_model_bytes": sum(p.stat().st_size for p in files),
    "ggufs": [{"bytes": p.stat().st_size, "path": str(p)} for p in sorted(ggufs)],
    "base_model": "`$BASE_MODEL",
    "coder_model": "`$CODER_MODEL",
    "adapter_model": "`$ADAPTER_MODEL",
    "df_root": subprocess.check_output(["df", "-h", "/"], text=True).strip(),
}
Path("`$REPORT").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps(report, indent=2, sort_keys=True))
PY

curl -fsS http://127.0.0.1:8765/health >/tmp/engel-fast-ssd-chat-health.json
cat /tmp/engel-fast-ssd-chat-health.json
echo
"@

Write-Utf8NoBom $LocalScriptPath $Script

& ssh -i $ResolvedKeyPath -p $CtPort -o BatchMode=yes -o StrictHostKeyChecking=accept-new "${CtUser}@${CtHost}" "mkdir -p '$RuntimeRoot/cache'"
if ($LASTEXITCODE -ne 0) {
    throw "Failed to prepare CT cache directory."
}

& scp -i $ResolvedKeyPath -P $CtPort -o BatchMode=yes -o StrictHostKeyChecking=accept-new $LocalScriptPath "${CtUser}@${CtHost}:$RemoteScriptPath"
if ($LASTEXITCODE -ne 0) {
    throw "Failed to copy fast SSD model activation script to CT."
}

& ssh -i $ResolvedKeyPath -p $CtPort -o BatchMode=yes -o StrictHostKeyChecking=accept-new "${CtUser}@${CtHost}" "chmod +x '$RemoteScriptPath' && '$RemoteScriptPath'"
if ($LASTEXITCODE -ne 0) {
    throw "Fast SSD model activation failed on CT."
}

$RemoteReport = & ssh -i $ResolvedKeyPath -p $CtPort -o BatchMode=yes -o StrictHostKeyChecking=accept-new "${CtUser}@${CtHost}" "cat '$RuntimeRoot/reports/ENGEL_FAST_SSD_MODEL_ACTIVATION_$Stamp.json'"
if ($LASTEXITCODE -ne 0) {
    throw "Failed to read CT fast SSD model activation report."
}

$ReceiptPath = Join-Path $ReceiptDir "ENGEL_FAST_SSD_MODEL_ACTIVATION_$Stamp.json"
Write-Utf8NoBom $ReceiptPath $RemoteReport
Write-Host "Fast SSD model activation receipt: $ReceiptPath"
