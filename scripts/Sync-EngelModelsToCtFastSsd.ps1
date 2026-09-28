[CmdletBinding()]
param(
    [string]$CtHost = "192.0.2.50",
    [int]$CtPort = 24622,
    [string]$CtUser = "root",
    [string]$RuntimeRoot = "/opt/engel",
    [string]$VaultRoot = "/mnt/engel-hdd-vault",
    [string]$KeyPath = (Join-Path $env:USERPROFILE ".ssh\engel_ai_main_ct246_ed25519"),
    [switch]$SkipCosmosSuper,
    [switch]$AllowVaultUse
)

$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$RuntimeDir = Join-Path $ProjectRoot "runtime\ct_fast_ssd_model_sync"
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

$RemoteScriptPath = "$RuntimeRoot/cache/sync_engel_models_fast_ssd_$Stamp.sh"
$LocalScriptPath = Join-Path $RuntimeDir "sync_engel_models_fast_ssd_$Stamp.sh"
$SkipSuperValue = if ($SkipCosmosSuper) { "1" } else { "0" }

$Script = @"
#!/usr/bin/env bash
set -euo pipefail

RUNTIME_ROOT="$RuntimeRoot"
VAULT_ROOT="$VaultRoot"
SSD_ROOT="`$RUNTIME_ROOT/models-active"
REPORT_DIR="`$RUNTIME_ROOT/reports"
STAMP="$Stamp"
REPORT="`$REPORT_DIR/ENGEL_CT_FAST_SSD_MODEL_SYNC_`$STAMP.json"
LOG="`$REPORT_DIR/ENGEL_CT_FAST_SSD_MODEL_SYNC_`$STAMP.log"
SKIP_COSMOS_SUPER="$SkipSuperValue"

mkdir -p "`$SSD_ROOT" "`$REPORT_DIR" "`$RUNTIME_ROOT/cache"
: > "`$LOG"

log() {
  printf '%s\n' "`$*" | tee -a "`$LOG"
}

copy_tree() {
  local src="`$1"
  local dst="`$2"
  if [ ! -d "`$src" ]; then
    log "skip missing source `$src"
    return 0
  fi
  mkdir -p "`$dst"
  log "sync `$src -> `$dst"
  if command -v rsync >/dev/null 2>&1; then
    rsync -a --human-readable --info=stats2,progress2 --exclude='.cache/huggingface/download/*.lock' "`$src/" "`$dst/" 2>&1 | tee -a "`$LOG"
  else
    cp -an "`$src/." "`$dst/"
  fi
}

copy_tree "`$VAULT_ROOT/models-archive/llm" "`$SSD_ROOT/llm"
copy_tree "`$VAULT_ROOT/training-outputs/runpod/standalone_chat_llm" "`$SSD_ROOT/lora"
copy_tree "`$VAULT_ROOT/training-outputs/runpod/standalone_llm_training/artifacts" "`$SSD_ROOT/runpod/standalone_llm_training/artifacts"
copy_tree "`$VAULT_ROOT/training-outputs/runpod/standalone_chat_llm" "`$SSD_ROOT/runpod/standalone_chat_llm"
copy_tree "`$VAULT_ROOT/training-outputs/runpod/local_standalone_chat_llm" "`$SSD_ROOT/runpod/local_standalone_chat_llm"

if [ -d "`$VAULT_ROOT/models-archive/cosmos3" ]; then
  if [ "`$SKIP_COSMOS_SUPER" = "1" ]; then
    mkdir -p "`$SSD_ROOT/hf/cosmos3"
    for model_dir in "`$VAULT_ROOT"/models-archive/cosmos3/*; do
      [ -d "`$model_dir" ] || continue
      case "`$(basename "`$model_dir")" in
        Cosmos3-Super|Cosmos3-Super-Text2Image|Cosmos3-Super-Image2Video)
          log "skip Cosmos3 super-size model `$model_dir"
          ;;
        *)
          copy_tree "`$model_dir" "`$SSD_ROOT/hf/cosmos3/`$(basename "`$model_dir")"
          ;;
      esac
    done
  else
    copy_tree "`$VAULT_ROOT/models-archive/cosmos3" "`$SSD_ROOT/hf/cosmos3"
  fi
fi

python3 - <<'PY'
import json
import os
import subprocess
from pathlib import Path
from datetime import datetime, timezone

ssd_root = Path(os.environ.get("SSD_ROOT", "/opt/engel/models-active"))
report = Path(os.environ.get("REPORT", "/opt/engel/reports/ENGEL_CT_FAST_SSD_MODEL_SYNC_UNKNOWN.json"))
log_path = Path(os.environ.get("LOG", ""))
memory_inventory = Path(os.environ.get("MEMORY_INVENTORY", "/opt/engel/memory/models/ENGEL_CT_FAST_SSD_MODEL_INVENTORY.json"))
model_exts = {".gguf", ".safetensors", ".bin", ".pt", ".pth"}
config_names = {"config.json", "tokenizer.json", "tokenizer_config.json", "special_tokens_map.json", "adapter_config.json"}

files = []
for path in ssd_root.rglob("*"):
    if not path.is_file():
        continue
    if path.suffix.lower() in model_exts or path.name in config_names:
        try:
            size = path.stat().st_size
        except OSError:
            size = 0
        files.append((size, path))

by_ext = {}
for size, path in files:
    ext = path.suffix.lower() or path.name.lower()
    by_ext.setdefault(ext, {"count": 0, "bytes": 0})
    by_ext[ext]["count"] += 1
    by_ext[ext]["bytes"] += size

def sh(command):
    try:
        return subprocess.check_output(command, text=True, stderr=subprocess.STDOUT).strip()
    except Exception as exc:
        return str(exc)

payload = {
    "schema": "engel_ct_fast_ssd_model_sync_v1",
    "ok": True,
    "updated_at_utc": datetime.now(timezone.utc).isoformat(),
    "active_runtime_storage": "engel-fast-ssd",
    "active_model_root": str(ssd_root),
    "vault_used_for_active_runtime": False,
    "vault_used_as_copy_source": True,
    "model_file_count": len(files),
    "model_total_bytes": sum(size for size, _ in files),
    "model_total_gib": round(sum(size for size, _ in files) / (1024**3), 2),
    "by_extension": by_ext,
    "largest_files": [{"bytes": size, "gib": round(size / (1024**3), 2), "path": str(path)} for size, path in sorted(files, reverse=True)[:80]],
    "df_opt_engel": sh(["df", "-h", "/opt/engel"]),
    "du_models_active": sh(["du", "-sh", str(ssd_root)]),
    "log_path": str(log_path),
    "memory_inventory_path": str(memory_inventory),
}
memory_inventory.parent.mkdir(parents=True, exist_ok=True)
memory_inventory.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
report.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps(payload, indent=2, sort_keys=True))
PY
"@

Write-Utf8NoBom $LocalScriptPath $Script

& ssh -i $ResolvedKeyPath -p $CtPort -o BatchMode=yes -o StrictHostKeyChecking=accept-new "${CtUser}@${CtHost}" "mkdir -p '$RuntimeRoot/cache' '$RuntimeRoot/reports'"
if ($LASTEXITCODE -ne 0) {
    throw "Failed to prepare CT cache/report directories."
}

& scp -i $ResolvedKeyPath -P $CtPort -o BatchMode=yes -o StrictHostKeyChecking=accept-new $LocalScriptPath "${CtUser}@${CtHost}:$RemoteScriptPath"
if ($LASTEXITCODE -ne 0) {
    throw "Failed to copy CT fast SSD model sync script."
}

$envText = "SSD_ROOT='$RuntimeRoot/models-active' REPORT='$RuntimeRoot/reports/ENGEL_CT_FAST_SSD_MODEL_SYNC_$Stamp.json' LOG='$RuntimeRoot/reports/ENGEL_CT_FAST_SSD_MODEL_SYNC_$Stamp.log' MEMORY_INVENTORY='$RuntimeRoot/memory/models/ENGEL_CT_FAST_SSD_MODEL_INVENTORY.json'"
& ssh -i $ResolvedKeyPath -p $CtPort -o BatchMode=yes -o StrictHostKeyChecking=accept-new "${CtUser}@${CtHost}" "chmod +x '$RemoteScriptPath' && $envText '$RemoteScriptPath'"
if ($LASTEXITCODE -ne 0) {
    throw "CT fast SSD model sync failed."
}

$RemoteReportPath = "$RuntimeRoot/reports/ENGEL_CT_FAST_SSD_MODEL_SYNC_$Stamp.json"
$RemoteReport = & ssh -i $ResolvedKeyPath -p $CtPort -o BatchMode=yes -o StrictHostKeyChecking=accept-new "${CtUser}@${CtHost}" "cat '$RemoteReportPath'"
if ($LASTEXITCODE -ne 0) {
    throw "Failed to read CT fast SSD model sync report."
}

$ReceiptPath = Join-Path $ReceiptDir "ENGEL_CT_FAST_SSD_MODEL_SYNC_$Stamp.json"
Write-Utf8NoBom $ReceiptPath $RemoteReport
Write-Host "CT fast SSD model sync receipt: $ReceiptPath"
