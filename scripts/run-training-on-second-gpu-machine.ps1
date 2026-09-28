<#
Run this on the SECOND 8GB GPU machine (the other desktop or laptop connected to the 730xd).

Prerequisites:
1. Copy the training package from the 730xd or from the first GPU machine:
  From CT246 (if you have access): scp root@192.0.2.50:/mnt/ssd-ai/training/packages/engel-training-convo-20260701/engel_standalone_lora_training_package.zip .
   Or from this machine if network share.

2. Extract it to e.g. C:\engel-training

3. Have Python 3.10+ and run this script (or paste the commands).

This will run in parallel with the job on the first GPU and the CPU job on the 730xd.
#>

$ErrorActionPreference = 'Stop'

$packageRoot = "C:\engel-training"   # CHANGE if you extracted elsewhere
if (-not (Test-Path $packageRoot)) {
    Write-Error "Extract the package first to $packageRoot (or edit this script)"
    exit 1
}

$dataset = "$packageRoot\dataset\engel_standalone_sft.jsonl"
if (-not (Test-Path $dataset)) {
    Write-Error "Dataset not found at $dataset"
    exit 1
}

$baseDir = "C:\engel-convo-training-gpu2"
New-Item -ItemType Directory -Force -Path $baseDir | Out-Null

$venv = "$baseDir\venv"
if (-not (Test-Path "$venv\Scripts\python.exe")) {
    Write-Host "Creating venv..."
    python -m venv $venv   # or py -3.10 -m venv ...
}

$py = "$venv\Scripts\python.exe"
$pip = "$venv\Scripts\pip.exe"

Write-Host "Installing torch CUDA + deps for this 8GB GPU machine..."
& $pip install --upgrade pip wheel
& $pip install torch==2.1.0+cu121 torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
& $pip install transformers==4.44.2 peft==0.12.0 datasets==2.20.0 accelerate==0.34.2 bitsandbytes safetensors

Write-Host "Verifying GPU..."
& $py -c "import torch; print('CUDA available:', torch.cuda.is_available()); print('GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'NONE')"

$timestamp = Get-Date -Format yyyyMMdd-HHmmss
$outDir = "$baseDir\adapter-gpu2-$timestamp"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

$log = "$baseDir\train-gpu2-$timestamp.log"

Write-Host "=== Launching training on GPU2 (parallel with GPU1 + 730xd) ==="

$args = @(
    "$packageRoot\train_engel_lora.py",
    "--base_model", "Qwen/Qwen2.5-7B-Instruct",
    "--dataset", $dataset,
    "--output_dir", $outDir,
    "--max-steps", "1200",
    "--max-length", "384",
    "--lr", "1.5e-4"
)

Start-Process -FilePath $py -ArgumentList $args -RedirectStandardOutput $log -WindowStyle Hidden -WorkingDirectory $packageRoot

Write-Host "Training started on this machine (GPU2)."
Write-Host "Log: $log"
Write-Host "Monitor: Get-Content $log -Wait -Tail 20"
Write-Host ""
Write-Host "When done on all three machines, bring the adapters back to the 730xd fast-ssd and pick the best one for the Chat LLM."
