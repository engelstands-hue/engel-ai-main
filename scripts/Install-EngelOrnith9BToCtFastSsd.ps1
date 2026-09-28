[CmdletBinding()]
param(
    [string]$CtHost = "192.0.2.50",
    [int]$CtPort = 24622,
    [string]$CtUser = "root",
    [string]$RuntimeRoot = "/opt/engel",
    [string]$ModelRepo = "deepreinforce-ai/Ornith-1.0-9B-GGUF",
    [string]$ModelFile = "ornith-1.0-9b-Q4_K_M.gguf",
    [Int64]$ExpectedBytes = 5629108704,
    [string]$KeyPath = (Join-Path $env:USERPROFILE ".ssh\engel_ai_main_ct246_ed25519")
)

$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$ReceiptDir = Join-Path $ProjectRoot "reports\ct_sync"
$RuntimeDir = Join-Path $ProjectRoot "runtime\ct_fast_ssd_model_sync"
$Stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$ResolvedKeyPath = [System.IO.Path]::GetFullPath($KeyPath)
$SshExe = "C:\Windows\System32\OpenSSH\ssh.exe"
$ScpExe = "C:\Windows\System32\OpenSSH\scp.exe"

if (-not (Test-Path -LiteralPath $ResolvedKeyPath -PathType Leaf)) {
    throw "Engel CT SSH key missing: $ResolvedKeyPath"
}
if (-not (Test-Path -LiteralPath $SshExe -PathType Leaf)) {
    throw "OpenSSH ssh.exe missing: $SshExe"
}
if (-not (Test-Path -LiteralPath $ScpExe -PathType Leaf)) {
    throw "OpenSSH scp.exe missing: $ScpExe"
}

New-Item -ItemType Directory -Force -Path $ReceiptDir, $RuntimeDir | Out-Null

function Write-Utf8NoBom {
    param([string]$Path, [string]$Text)
    [System.IO.File]::WriteAllText($Path, $Text, [System.Text.UTF8Encoding]::new($false))
}

$RemoteScriptPath = "$RuntimeRoot/cache/install_ornith_9b_fast_ssd_$Stamp.sh"
$LocalScriptPath = Join-Path $RuntimeDir "install_ornith_9b_fast_ssd_$Stamp.sh"
$ReceiptPath = Join-Path $ReceiptDir "ENGEL_ORNITH_9B_FAST_SSD_INSTALL_$Stamp.json"
$ModelUrl = "https://huggingface.co/$ModelRepo/resolve/main/$ModelFile"

$remoteScript = @"
#!/usr/bin/env bash
set -euo pipefail

RUNTIME_ROOT="$RuntimeRoot"
SSD_ROOT="`$RUNTIME_ROOT/models-active"
MODEL_DIR="`$SSD_ROOT/llm/ornith-1.0-9b"
MODEL_FILE="$ModelFile"
MODEL_PATH="`$MODEL_DIR/`$MODEL_FILE"
PART_PATH="`$MODEL_PATH.part"
MODEL_URL="$ModelUrl"
EXPECTED_BYTES="$ExpectedBytes"
STAMP="$Stamp"
MODEL_REPO="$ModelRepo"
REPORT="`$RUNTIME_ROOT/reports/ENGEL_ORNITH_9B_FAST_SSD_INSTALL_$Stamp.json"
INVENTORY="`$RUNTIME_ROOT/memory/models/ENGEL_CT_FAST_SSD_MODEL_INVENTORY.json"
ACTIVE_CHAT_MANIFEST="`$RUNTIME_ROOT/memory/models/ENGEL_ACTIVE_CHAT_MODEL_MANIFEST.json"
LARGE_MANIFEST="`$RUNTIME_ROOT/memory/models/ENGEL_LARGE_CHAT_LLM_MANIFEST.json"
SERVICE_OVERRIDE_DIR="/etc/systemd/system/engel-main-chat.service.d"
SERVICE_OVERRIDE="`$SERVICE_OVERRIDE_DIR/30-ornith-9b-fast-ssd.conf"

mkdir -p "`$MODEL_DIR" "`$RUNTIME_ROOT/reports" "`$RUNTIME_ROOT/memory/models" "`$RUNTIME_ROOT/cache" "`$SERVICE_OVERRIDE_DIR"

if [ -f "`$MODEL_PATH" ]; then
  actual="`$(stat -c%s "`$MODEL_PATH")"
else
  actual="0"
fi

if [ "`$actual" != "`$EXPECTED_BYTES" ]; then
  rm -f "`$MODEL_PATH"
  echo "Downloading Ornith-1.0-9B GGUF to CT fast SSD: `$MODEL_PATH"
  if command -v curl >/dev/null 2>&1; then
    curl -L --fail --retry 5 --retry-delay 5 --connect-timeout 30 -C - -o "`$PART_PATH" "`$MODEL_URL"
  else
    python3 - <<PY
import urllib.request
url = "$ModelUrl"
out = "`$PART_PATH"
with urllib.request.urlopen(url, timeout=60) as response, open(out, "ab") as handle:
    while True:
        chunk = response.read(1024 * 1024)
        if not chunk:
            break
        handle.write(chunk)
PY
  fi
  downloaded="`$(stat -c%s "`$PART_PATH")"
  if [ "`$downloaded" != "`$EXPECTED_BYTES" ]; then
    echo "Downloaded size mismatch: expected `$EXPECTED_BYTES got `$downloaded" >&2
    exit 12
  fi
  mv -f "`$PART_PATH" "`$MODEL_PATH"
fi

final_bytes="`$(stat -c%s "`$MODEL_PATH")"
if [ "`$final_bytes" != "`$EXPECTED_BYTES" ]; then
  echo "Final model size mismatch: expected `$EXPECTED_BYTES got `$final_bytes" >&2
  exit 13
fi

sha256="`$(sha256sum "`$MODEL_PATH" | awk '{print `$1}')"

cat > "`$SERVICE_OVERRIDE" <<EOF
[Service]
Environment=ENGEL_ACTIVE_MODEL_STORAGE=engel-fast-ssd
Environment=ENGEL_MODELS_ACTIVE_ROOT=`$SSD_ROOT
Environment=ENGEL_LOCAL_GGUF_MODEL=`$MODEL_PATH
Environment=ENGEL_LARGE_CHAT_LLM_ROOTS=`$SSD_ROOT/llm
Environment=ENGEL_LARGE_CHAT_LLM_MODEL=`$MODEL_PATH
Environment=ENGEL_STANDALONE_CHAT_PROVIDER=local
EOF

python3 - <<PY
import json
import os
import subprocess
from pathlib import Path

runtime_root = Path("$RuntimeRoot")
model_path = Path("$RuntimeRoot/models-active/llm/ornith-1.0-9b/$ModelFile")
report_path = Path("$RuntimeRoot/reports/ENGEL_ORNITH_9B_FAST_SSD_INSTALL_$Stamp.json")
inventory_path = Path("$RuntimeRoot/memory/models/ENGEL_CT_FAST_SSD_MODEL_INVENTORY.json")
active_chat_manifest_path = Path("$RuntimeRoot/memory/models/ENGEL_ACTIVE_CHAT_MODEL_MANIFEST.json")
large_manifest_path = Path("$RuntimeRoot/memory/models/ENGEL_LARGE_CHAT_LLM_MANIFEST.json")

model_record = {
    "id": "ornith-1.0-9b-q4_k_m",
    "name": "Ornith-1.0-9B Q4_K_M GGUF",
    "repo": "$ModelRepo",
    "source_url": "$ModelUrl",
    "path": str(model_path),
    "bytes": int("$ExpectedBytes"),
    "gib": round(int("$ExpectedBytes") / (1024 ** 3), 2),
    "sha256": "`$sha256",
    "format": "gguf",
    "quantization": "Q4_K_M",
    "runtime_storage": "engel-fast-ssd",
    "active_for_plain_local_chat": True,
    "lora_attached": False,
    "installed_at_utc": "$Stamp",
}

active = {
    "schema": "engel_active_chat_model_manifest_v1",
    "ok": True,
    "updated_at_utc": "$Stamp",
    "active_plain_local_model": model_record,
    "trained_lora_lane_preserved": True,
    "notes": [
        "Ornith is registered as the plain local GGUF model on CT fast SSD.",
        "The existing Qwen LoRA lane is not attached to Ornith because the adapter was trained for Qwen/Qwen2.5-7B-Instruct.",
    ],
}
active_chat_manifest_path.parent.mkdir(parents=True, exist_ok=True)
active_chat_manifest_path.write_text(json.dumps(active, indent=2, sort_keys=True) + "\n", encoding="utf-8")

if large_manifest_path.is_file():
    try:
        large = json.loads(large_manifest_path.read_text(encoding="utf-8-sig"))
    except Exception:
        large = {}
else:
    large = {}
large.update({
    "schema": "engel_large_chat_llm_manifest_v1",
    "enabled_for_local_chat_when_present": True,
    "model_store_root": str(model_path.parent),
    "active_model_path": str(model_path),
    "selected_model_path": str(model_path),
    "selected_model_present": True,
    "active_model_size_rule": "no_fixed_minimum",
    "active_runtime_storage": "engel-fast-ssd",
    "active_model_registered_name": "Ornith-1.0-9B Q4_K_M GGUF",
    "minimum_model_store_gib": 0,
    "minimum_model_bytes": 0,
    "extra_model_roots": [str(runtime_root / "models-active" / "llm")],
    "runpod_handoff_root": str(runtime_root / "run" / "runpod" / "large_chat_llm"),
    "download_enabled": False,
    "provider_calls_enabled": False,
    "runpod_api_enabled": False,
    "updated_at_utc": "$Stamp",
})
large_manifest_path.parent.mkdir(parents=True, exist_ok=True)
large_manifest_path.write_text(json.dumps(large, indent=2, sort_keys=True) + "\n", encoding="utf-8")

if inventory_path.is_file():
    try:
        inventory = json.loads(inventory_path.read_text(encoding="utf-8-sig"))
    except Exception:
        inventory = {}
else:
    inventory = {"schema": "engel_ct_fast_ssd_model_inventory_v1"}
installed = inventory.get("installed_models") if isinstance(inventory.get("installed_models"), dict) else {}
installed[model_record["id"]] = model_record
inventory.update({
    "ok": True,
    "active_model_root": str(runtime_root / "models-active"),
    "active_runtime_storage": "engel-fast-ssd",
    "updated_at_utc": "$Stamp",
    "ornith_1_0_9b_installed": True,
    "active_plain_local_model_path": str(model_path),
    "installed_models": installed,
})
inventory_path.parent.mkdir(parents=True, exist_ok=True)
inventory_path.write_text(json.dumps(inventory, indent=2, sort_keys=True) + "\n", encoding="utf-8")

files = [p for p in (runtime_root / "models-active").rglob("*") if p.is_file()]
ggufs = [p for p in files if p.suffix.lower() == ".gguf"]
report = {
    "schema": "engel_ornith_9b_fast_ssd_install_v1",
    "ok": True,
    "updated_at_utc": "$Stamp",
    "model": model_record,
    "active_chat_manifest_path": str(active_chat_manifest_path),
    "large_chat_manifest_path": str(large_manifest_path),
    "inventory_path": str(inventory_path),
    "service_override": "/etc/systemd/system/engel-main-chat.service.d/30-ornith-9b-fast-ssd.conf",
    "models_active_total_gib": round(sum(p.stat().st_size for p in files) / (1024 ** 3), 2),
    "models_active_file_count": len(files),
    "models_active_gguf_count": len(ggufs),
    "df_opt_engel": subprocess.check_output(["df", "-h", str(runtime_root)], text=True).strip(),
}
report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps(report, indent=2, sort_keys=True))
PY

systemctl daemon-reload
systemctl restart engel-main-chat.service
sleep 2
systemctl is-active engel-main-chat.service
curl -fsS http://127.0.0.1:8765/health >/tmp/engel_ornith_health.json
cat /tmp/engel_ornith_health.json
"@

Write-Utf8NoBom $LocalScriptPath $remoteScript

$remoteTarget = "${CtUser}@${CtHost}"
& $SshExe -i $ResolvedKeyPath -p $CtPort -o BatchMode=yes -o StrictHostKeyChecking=accept-new $remoteTarget "mkdir -p '$RuntimeRoot/cache'"
if ($LASTEXITCODE -ne 0) { throw "Failed to prepare CT cache directory." }

& $ScpExe -i $ResolvedKeyPath -P $CtPort -o BatchMode=yes -o StrictHostKeyChecking=accept-new $LocalScriptPath "${remoteTarget}:$RemoteScriptPath"
if ($LASTEXITCODE -ne 0) { throw "Failed to copy Ornith installer to CT." }

& $ScpExe -i $ResolvedKeyPath -P $CtPort -o BatchMode=yes -o StrictHostKeyChecking=accept-new (Join-Path $ProjectRoot "engel_large_chat_llm.py") "${remoteTarget}:$RuntimeRoot/engel_large_chat_llm.py"
if ($LASTEXITCODE -ne 0) { throw "Failed to copy updated large chat selector to CT." }

& $SshExe -i $ResolvedKeyPath -p $CtPort -o BatchMode=yes -o StrictHostKeyChecking=accept-new $remoteTarget "python3 -m py_compile '$RuntimeRoot/engel_large_chat_llm.py' && chmod +x '$RemoteScriptPath' && '$RemoteScriptPath'"
if ($LASTEXITCODE -ne 0) { throw "Ornith install failed on CT." }

$remoteReport = & $SshExe -i $ResolvedKeyPath -p $CtPort -o BatchMode=yes -o StrictHostKeyChecking=accept-new $remoteTarget "cat '$RuntimeRoot/reports/ENGEL_ORNITH_9B_FAST_SSD_INSTALL_$Stamp.json'"
if ($LASTEXITCODE -ne 0) { throw "Failed to read CT Ornith install report." }
Write-Utf8NoBom $ReceiptPath ($remoteReport -join "`n")
Write-Host "Ornith fast SSD install receipt: $ReceiptPath"
