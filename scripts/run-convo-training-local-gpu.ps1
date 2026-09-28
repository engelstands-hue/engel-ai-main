# Run conversational LoRA training on this Windows machine (the one with 8GB RTX 2070 CUDA)
# This machine is one of the GPU nodes connected to the 730xd server (central storage/orchestrator, no GPU)

$ErrorActionPreference = 'Stop'

$baseDir = "D:\b.WorkSpace\Engel App\runtime\training-convo-gpu"
$packageDir = "D:\b.WorkSpace\Engel App\runtime\engel_lora_training_package"
$dataset = "$packageDir\dataset\engel_standalone_sft.jsonl"

New-Item -ItemType Directory -Force -Path $baseDir | Out-Null

Write-Host "=== Setting up training venv on local 8GB GPU machine ==="

$venv = "$baseDir\venv"
if (-not (Test-Path "$venv\Scripts\python.exe")) {
    Write-Host "Creating venv..."
    & 'D:\b.WorkSpace\Engel App\runtime\python310\python.exe' -m venv $venv
}

$py = "$venv\Scripts\python.exe"
$pip = "$venv\Scripts\pip.exe"

Write-Host "Upgrading pip..."
& $pip install --upgrade pip wheel

Write-Host "Installing torch with CUDA 12.1 (for RTX 2070) + requirements..."
& $pip install torch==2.1.0+cu121 torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
& $pip install -r "$packageDir\requirements.txt" 2>&1 | Select -Last 5

Write-Host "Verifying GPU..."
& $py -c "
import torch
print('torch:', torch.__version__)
print('cuda available:', torch.cuda.is_available())
if torch.cuda.is_available():
    print('gpu:', torch.cuda.get_device_name(0))
    print('total mem:', round(torch.cuda.get_device_properties(0).total_memory / 1024**3, 1), 'GB')
"

$outputDir = "$baseDir\output-convo-$(Get-Date -Format yyyyMMdd-HHmmss)"
New-Item -ItemType Directory -Force -Path $outputDir | Out-Null

Write-Host "=== Launching training (Qwen 7B conversational on 8GB) ==="
Write-Host "This will take hours. Monitor the log."

$log = "$baseDir\train.log"

# Use nohup equivalent: Start-Process with output redirect
$args = @(
    "$packageDir\train_engel_lora.py",
    "--base_model", "Qwen/Qwen2.5-7B-Instruct",
    "--dataset", $dataset,
    "--output_dir", $outputDir,
    "--max_steps", "1500",
    "--batch_size", "1",
    "--gradient_accumulation_steps", "8",
    "--lora_r", "8",
    "--lora_alpha", "16",
    "--learning_rate", "1e-4",
    "--max_length", "512",
    "--load_in_4bit"
)

Start-Process -FilePath $py -ArgumentList $args -RedirectStandardOutput $log -RedirectStandardError "$baseDir\train.err.log" -WorkingDirectory $packageDir -WindowStyle Hidden

Write-Host "Training started in background."
Write-Host "Log: $log"
Write-Host "Output adapter dir will be: $outputDir"
Write-Host "To watch: Get-Content $log -Wait -Tail 20"
Write-Host ""
Write-Host "Once complete, the adapter can be converted and used for the SSD Chat LLM on the 730xd setup."