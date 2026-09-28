[CmdletBinding()]
param(
    [decimal]$BudgetUsd = 25.00,
    [string]$GpuTypeId = "NVIDIA H100 80GB HBM3",
    [int]$ContainerDiskGb = 80,
    [int]$VolumeGb = 40,
    [string]$BaseModel = "mistralai/Mistral-7B-Instruct-v0.3",
    [int]$MaxSteps = 100000,
    [int]$MaxLength = 768,
    [double]$LearningRate = 0.0002,
    [int]$StopMarginSeconds = 120,
    [string]$CtHost = "192.0.2.50",
    [int]$CtPort = 24622,
    [string]$CtUser = "root",
    [string]$CtRuntimeRoot = "/opt/engel",
    [string]$CtKeyPath = (Join-Path $env:USERPROFILE ".ssh\engel_ai_main_ct246_ed25519"),
    [string]$Python = "D:\b.WorkSpace\venv\Scripts\python.exe",
    [switch]$SkipCtPublish
)

$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$RunPodRoot = Join-Path $ProjectRoot "runtime\runpod"
$SecretDir = Join-Path $RunPodRoot "secrets"
$SecretPath = Join-Path $SecretDir "runpod_api_key.txt"
$ReceiptDir = Join-Path $RunPodRoot "receipts"
$PublishDir = Join-Path $ProjectRoot "runtime\runpod\ct_publish"
$Stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")

New-Item -ItemType Directory -Force -Path $SecretDir, $ReceiptDir, $PublishDir | Out-Null

function Write-Utf8NoBom {
    param([Parameter(Mandatory)][string]$Path, [Parameter(Mandatory)][string]$Text)
    $encoding = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $Text, $encoding)
}

function Write-JsonReceipt {
    param([Parameter(Mandatory)][string]$Name, [Parameter(Mandatory)]$Payload)
    $path = Join-Path $ReceiptDir "$Name`_$Stamp.json"
    $Payload | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $path -Encoding UTF8
    return $path
}

function Invoke-Checked {
    param(
        [Parameter(Mandatory)][string[]]$Command,
        [Parameter(Mandatory)][string]$Stage
    )
    Write-Host ""
    Write-Host "== $Stage =="
    Write-Host (($Command | ForEach-Object { if ($_ -match "Bearer ") { "[REDACTED]" } else { $_ } }) -join " ")
    & $Command[0] @($Command | Select-Object -Skip 1)
    if ($LASTEXITCODE -ne 0) {
        throw "$Stage failed with exit code $LASTEXITCODE"
    }
}

if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    $Python = "python"
}

if (-not (Test-Path -LiteralPath $SecretPath -PathType Leaf) -or ((Get-Item -LiteralPath $SecretPath).Length -lt 20)) {
    Write-Host "Paste the RunPod API key. It will be stored locally at:"
    Write-Host "  $SecretPath"
    Write-Host "The key will not be printed in receipts or output."
    $secure = Read-Host "RunPod API key" -AsSecureString
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try {
        $plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr).Trim()
    }
    finally {
        if ($bstr -ne [IntPtr]::Zero) {
            [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
        }
    }
    if (-not $plain -or $plain.Length -lt 20) {
        throw "RunPod API key was not provided or is too short."
    }
    Write-Utf8NoBom -Path $SecretPath -Text ($plain + "`n")
    $plain = $null
}

$env:ENGEL_RUNPOD_MEMORY_ROOT = $RunPodRoot
$env:ENGEL_RUNPOD_KEY_PATH = $SecretPath

$package = Join-Path $ProjectRoot "runtime\engel_lora_training_package\engel_standalone_lora_training_package.zip"
if (-not (Test-Path -LiteralPath $package -PathType Leaf)) {
    Invoke-Checked -Stage "Build LoRA training package" -Command @($Python, (Join-Path $ProjectRoot "tools\build_engel_lora_training_package.py"))
}

$podName = "engel-lora-budget-$($BudgetUsd.ToString('0').Replace('.', '-'))-$Stamp"
$createArgs = @(
    $Python,
    (Join-Path $ProjectRoot "tools\create_engel_runpod_training_pod.py"),
    "--name", $podName,
    "--gpu-type-id", $GpuTypeId,
    "--container-disk-gb", [string]$ContainerDiskGb,
    "--volume-gb", [string]$VolumeGb
)

Write-Host ""
Write-Host "== Create bounded RunPod pod =="
$createOutput = & $createArgs[0] @($createArgs | Select-Object -Skip 1) 2>&1
$createOutput | ForEach-Object { Write-Host $_ }
if ($LASTEXITCODE -ne 0) {
    throw "RunPod pod creation failed."
}

$podId = ""
$jsonText = ($createOutput -join "`n")
try {
    $jsonStart = $jsonText.IndexOf("{")
    $jsonEnd = $jsonText.LastIndexOf("}")
    if ($jsonStart -ge 0 -and $jsonEnd -gt $jsonStart) {
        $created = $jsonText.Substring($jsonStart, $jsonEnd - $jsonStart + 1) | ConvertFrom-Json
        $podId = [string]$created.pod_id
    }
}
catch {
    $podId = ""
}
if (-not $podId) {
    throw "RunPod pod id was not returned."
}

$runArgs = @(
    $Python,
    (Join-Path $ProjectRoot "tools\run_engel_lora_training_on_runpod.py"),
    "--pod-id", $podId,
    "--base-model", $BaseModel,
    "--max-steps", [string]$MaxSteps,
    "--max-length", [string]$MaxLength,
    "--lr", [string]$LearningRate,
    "--budget-usd", [string]$BudgetUsd,
    "--stop-margin-seconds", [string]$StopMarginSeconds,
    "run-all"
)
Invoke-Checked -Stage "Run bounded RunPod LoRA training" -Command $runArgs

Invoke-Checked -Stage "Register trained LoRA adapter locally" -Command @($Python, (Join-Path $ProjectRoot "tools\register_engel_trained_lora_adapter.py"))

if (-not $SkipCtPublish) {
    $ctKey = [IO.Path]::GetFullPath($CtKeyPath)
    if (-not (Test-Path -LiteralPath $ctKey -PathType Leaf)) {
        throw "CT SSH key missing: $ctKey"
    }

    $verifierPath = Join-Path $ProjectRoot "runtime\engel_lora_training_artifact_verifier_latest.json"
    $manifestPath = Join-Path $ProjectRoot "runtime\engel_standalone_chat_llm\trained_lora_adapter_manifest.json"
    $verifier = Get-Content -LiteralPath $verifierPath -Raw | ConvertFrom-Json
    $artifactDir = [string]$verifier.local_artifact_dir
    if (-not (Test-Path -LiteralPath $artifactDir -PathType Container)) {
        throw "Local artifact directory missing: $artifactDir"
    }
    if ($artifactDir -match "(?i)mnt[/\\]engel-vault") {
        throw "Refusing to publish CT245 offline-vault path: $artifactDir"
    }

    $artifactName = Split-Path -Leaf $artifactDir
    $remoteArtifactDir = "$CtRuntimeRoot/models-active/lora/$artifactName"
    $remoteManifest = "$CtRuntimeRoot/runtime/engel_standalone_chat_llm/trained_lora_adapter_manifest.json"
    $remoteReceiptDir = "$CtRuntimeRoot/reports/runpod"
    $tarPath = Join-Path $PublishDir "$artifactName.tar"

    if (Test-Path -LiteralPath $tarPath) {
        Remove-Item -LiteralPath $tarPath -Force
    }
    tar -C $artifactDir -cf $tarPath .
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to package LoRA artifact for CT publish."
    }

    $sshTarget = "$CtUser@$CtHost"
    $sshBase = @("ssh", "-i", $ctKey, "-p", [string]$CtPort, "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=accept-new", $sshTarget)
    $scpBase = @("scp", "-i", $ctKey, "-P", [string]$CtPort, "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=accept-new")

    Invoke-Checked -Stage "Prepare CT SSD LoRA directory" -Command ($sshBase + @("mkdir -p '$remoteArtifactDir' '$CtRuntimeRoot/runtime/engel_standalone_chat_llm' '$remoteReceiptDir'"))
    Invoke-Checked -Stage "Upload LoRA artifact tar to CT" -Command ($scpBase + @($tarPath, "$sshTarget`:$CtRuntimeRoot/cache/$artifactName.tar"))
    Invoke-Checked -Stage "Extract LoRA artifact on CT SSD" -Command ($sshBase + @("tar -C '$remoteArtifactDir' -xf '$CtRuntimeRoot/cache/$artifactName.tar' && rm -f '$CtRuntimeRoot/cache/$artifactName.tar'"))
    Invoke-Checked -Stage "Upload LoRA manifest to CT" -Command ($scpBase + @($manifestPath, "$sshTarget`:$remoteManifest"))

    $remotePatch = @"
python3 - <<'PY'
import json
from datetime import datetime, timezone
from pathlib import Path
manifest_path = Path("$remoteManifest")
manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
artifact_dir = Path("$remoteArtifactDir")
manifest.update({
    "local_artifact_dir": str(artifact_dir),
    "external_artifact_dir": str(artifact_dir),
    "ct_runtime_root": "$CtRuntimeRoot",
    "ct_fast_ssd_registered_at_utc": datetime.now(timezone.utc).isoformat(),
    "ct_fast_ssd_models_active": True,
    "runtime_loaded_by_current_chat_endpoint": False,
})
adapter = manifest.get("adapter_model_gguf")
if not isinstance(adapter, dict):
    adapter = {}
gguf = artifact_dir / "adapter_model.gguf"
adapter["path"] = "adapter_model.gguf"
adapter["absolute_path"] = str(gguf)
adapter["present"] = gguf.is_file()
manifest["adapter_model_gguf"] = adapter
receipt = artifact_dir / "ENGEL_LORA_GGUF_CONVERSION_RECEIPT.json"
manifest["conversion_receipt_path"] = str(receipt)
base_model = Path("$CtRuntimeRoot/models-active/llm/qwen2.5-7b-instruct/qwen2.5-7b-instruct-q5_k_m.gguf")
if base_model.is_file():
    manifest["serving_base_gguf_model_path"] = str(base_model)
manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps({
    "ok": True,
    "manifest": str(manifest_path),
    "artifact_dir": str(artifact_dir),
    "adapter_gguf_present": gguf.is_file(),
    "base_model_present": base_model.is_file(),
}, indent=2, sort_keys=True))
PY
systemctl restart engel-main-chat.service
systemctl restart engel-discord-bridge.service || true
systemctl is-active engel-main-chat.service
"@
    Invoke-Checked -Stage "Patch CT manifest and restart Engel chat" -Command ($sshBase + @($remotePatch))

    $publishReceipt = [ordered]@{
        ok = $true
        schema = "engel_runpod_lora_ct_publish_v1"
        updated_at_utc = (Get-Date).ToUniversalTime().ToString("o")
        pod_id = $podId
        budget_usd = [decimal]$BudgetUsd
        local_artifact_dir = $artifactDir
        ct_artifact_dir = $remoteArtifactDir
        ct_manifest_path = $remoteManifest
        ct_runtime_root = $CtRuntimeRoot
        power_vault_used = $false
        api_key_value_visible = $false
    }
    $receiptPath = Write-JsonReceipt -Name "RUNPOD_ENGEL_LORA_CT_PUBLISH" -Payload $publishReceipt
    Write-Host "CT publish receipt: $receiptPath"
}

Write-Host ""
Write-Host "Engel RunPod budget LoRA training flow completed."
