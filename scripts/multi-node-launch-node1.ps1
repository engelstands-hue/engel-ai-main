<#
Multi-node distributed LoRA training - NODE 1 (SECOND 8GB GPU machine)

Run this on the second GPU machine AFTER node 0 has started.
#>

$ErrorActionPreference = 'Stop'

# === CONFIG - EDIT THESE (same as node 0) ===
$SHARED_BASE = "Z:\engel-distributed-training"   # Mount of 730xd SSD (must be identical)
$PACKAGE_DIR = "D:\b.WorkSpace\Engel App\runtime\engel_lora_training_package"
$VENV_PYTHON = "D:\b.WorkSpace\Engel App\runtime\training-convo-gpu\venv\Scripts\python.exe"  # adjust per machine

$MASTER_ADDR = "192.0.2.50"
$MASTER_PORT = 29500
$NNODES = 2
$NPROC_PER_NODE = 1
$NODE_RANK = 1

$DATASET = "$SHARED_BASE\dataset\engel_standalone_sft.jsonl"
$OUTPUT_DIR = "$SHARED_BASE\outputs\multi-node-run-$(Get-Date -Format yyyyMMdd-HHmmss)"

New-Item -ItemType Directory -Force -Path $OUTPUT_DIR | Out-Null

Write-Host "=== Multi-node Node 1 (this GPU) ==="
Write-Host "Connecting to master $MASTER_ADDR:$MASTER_PORT"

$env:MASTER_ADDR = $MASTER_ADDR
$env:MASTER_PORT = $MASTER_PORT

& $VENV_PYTHON -m torch.distributed.run `
    --nnodes=$NNODES `
    --nproc_per_node=$NPROC_PER_NODE `
    --node_rank=$NODE_RANK `
    --master_addr=$MASTER_ADDR `
    --master_port=$MASTER_PORT `
    "$PACKAGE_DIR\train_engel_lora.py" `
    --base-model "Qwen/Qwen2.5-7B-Instruct" `
    --dataset $DATASET `
    --output-dir $OUTPUT_DIR `
    --max-steps 2000 `
    --max-length 384 `
    --lr 1.5e-4

Write-Host "Node 1 finished."