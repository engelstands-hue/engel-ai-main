<#
.SYNOPSIS
  Start the ROG GPU-accelerated local LLM server (llama.cpp on the RTX 2070),
  OpenAI-compatible, keeping the model warm in VRAM.

.DESCRIPTION
  In the Engel controller/server topology the CT246 server has no GPU, so heavy
  local inference crawls on CPU (~35s/answer). The ROG laptop has an RTX 2070
  (8GB). This serves Engel's large local chat model on that GPU (~0.6-0.9s/answer,
  32-52 tok/s) as an OpenAI /v1/chat/completions endpoint on 127.0.0.1:PORT.
  A reverse SSH tunnel exposes it to CT246, which routes its large-chat lane here
  with a CPU fallback if the ROG is offline. Single-instance via a port check.
#>
param(
    [int]$Port = 8899,
    [string]$Model = "D:\b.WorkSpace\Engel App\runtime\gpu_models\Mistral-7B-Instruct-v0.3-Q4_K_M.gguf",
    [int]$CtxSize = 8192
)
$ErrorActionPreference = "Stop"
$venvpy = "D:\b.WorkSpace\Engel App\runtime\gpu_llm_venv\Scripts\python.exe"
if (-not (Test-Path $venvpy)) { throw "GPU venv python missing: $venvpy" }
if (-not (Test-Path $Model)) { throw "Model missing: $Model" }

# single-instance: bail if the port is already serving
$busy = (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) | Select-Object -First 1
if ($busy) { Write-Host "GPU model server already listening on $Port (PID $($busy.OwningProcess))."; return }

$log = Join-Path $env:LOCALAPPDATA "Engel AI Main\logs\rog-gpu-model-server.log"
New-Item -ItemType Directory -Force -Path (Split-Path $log) | Out-Null
"[$(Get-Date -Format s)] starting ROG GPU model server on 127.0.0.1:$Port model=$Model" | Add-Content -LiteralPath $log
& $venvpy -m llama_cpp.server --model "$Model" --n_gpu_layers -1 --n_ctx $CtxSize --host 127.0.0.1 --port $Port *>> $log
