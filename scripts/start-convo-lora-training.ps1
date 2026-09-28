# Final launch of conversational LoRA training on the 8GB RTX 2070 GPU machine
# (part of the 730xd-centered setup: server handles storage/coordination, this machine does the compute)

$venvPy = "D:\b.WorkSpace\Engel App\runtime\training-convo-gpu\venv\Scripts\python.exe"
$pkgDir = "D:\b.WorkSpace\Engel App\runtime\engel_lora_training_package"
$dataset = "$pkgDir\dataset\engel_standalone_sft.jsonl"   # the version with real-conversation examples
$baseDir = "D:\b.WorkSpace\Engel App\runtime\training-convo-gpu"
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$outputDir = "$baseDir\adapter-convo-$timestamp"

New-Item -ItemType Directory -Force -Path $outputDir | Out-Null

Write-Host "=== Starting LoRA training for real conversation feel ==="
Write-Host "Base model : Qwen/Qwen2.5-7B-Instruct"
Write-Host "Dataset    : $dataset (743 rows, conversation-focused)"
Write-Host "Output     : $outputDir"
Write-Host "VRAM target: 8GB (using 4-bit + small batch)"
Write-Host ""

$log = "$baseDir\train-$timestamp.log"

# Training args tuned for 8GB VRAM on RTX 2070
$trainArgs = @(
    "$pkgDir\train_engel_lora.py",
    "--base_model", "Qwen/Qwen2.5-7B-Instruct",
    "--dataset", $dataset,
    "--output_dir", $outputDir,
    "--max_steps", "1200",
    "--batch_size", "1",
    "--gradient_accumulation_steps", "8",
    "--lora_r", "8",
    "--lora_alpha", "16",
    "--learning_rate", "1.5e-4",
    "--max_length", "384",
    "--load_in_4bit"
)

Write-Host "Command: $venvPy $($trainArgs -join ' ')"
Write-Host "Logging to: $log"
Write-Host ""

# Launch in background so we can continue chatting
Start-Process -FilePath $venvPy `
    -ArgumentList $trainArgs `
    -RedirectStandardOutput $log `
    -RedirectStandardError "$baseDir\train-$timestamp.err.log" `
    -WorkingDirectory $pkgDir `
    -WindowStyle Hidden

Write-Host "Training process started (background)."
Write-Host "Monitor with:"
Write-Host "  Get-Content $log -Wait -Tail 20"
Write-Host ""
Write-Host "When finished, copy the adapter to the 730xd fast-ssd and update the Chat LLM profile."