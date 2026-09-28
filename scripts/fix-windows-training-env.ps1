$ErrorActionPreference = 'Continue'

$base = "D:\b.WorkSpace\Engel App\runtime\training-convo-gpu"
$venv = "$base\venv"
$venvPy = "$venv\Scripts\python.exe"
$venvPip = "$venv\Scripts\pip.exe"
$pkgDir = "D:\b.WorkSpace\Engel App\runtime\engel_lora_training_package"
$req = "$pkgDir\requirements.txt"

Write-Host "=== Fixing Windows 8GB GPU training environment ==="

if (-not (Test-Path $venvPy)) {
    Write-Error "Venv not found. Run the launcher again or create manually."
    exit 1
}

Write-Host "Current torch in venv:"
& $venvPy -c "import torch; print('torch:', torch.__version__); print('cuda:', torch.cuda.is_available()); print('gpu:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'none')" 2>&1

Write-Host ""
Write-Host "Installing core training packages (bitsandbytes is the tricky one on Windows)..."

# Install the non-torch parts from the project's requirements, but with compatible versions for Windows + cu121
& $venvPip install --upgrade pip wheel 2>&1 | Select -Last 3

# Critical packages for the training script
& $venvPip install "transformers==4.44.2" "peft==0.12.0" "datasets==2.20.0" "accelerate==0.34.2" "safetensors==0.4.5" 2>&1 | Select -Last 5

# bitsandbytes on Windows - use a community wheel that works better
Write-Host "Attempting bitsandbytes (Windows build)..."
& $venvPip install bitsandbytes --extra-index-url https://jllllll.github.io/bitsandbytes-windows-webui 2>&1 | Select -Last 8

Write-Host ""
Write-Host "Verifying imports needed by train_engel_lora.py:"
& $venvPy -c "
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, TrainingArguments, Trainer
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from datasets import Dataset
print('All core imports successful!')
print('torch cuda available:', torch.cuda.is_available())
if torch.cuda.is_available():
    print('GPU:', torch.cuda.get_device_name(0))
" 2>&1

Write-Host ""
Write-Host "Environment check complete. If imports succeeded, we can launch training."