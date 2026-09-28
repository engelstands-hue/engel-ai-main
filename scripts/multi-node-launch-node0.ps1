<#
Multi-node distributed LoRA training - NODE 0 (first 8GB GPU machine)

Run this on the first GPU machine.
All dataset, cache, and outputs go to the 730xd SSD (great network + fast storage).

Prerequisites on BOTH GPU machines:
- Same Python venv with torch+cu121, transformers, peft, bitsandbytes, etc.
- The training package extracted to same local path, OR use full paths on the 730xd share.
- Shared mount of 730xd SSD. Example:
    Windows:  net use Z: \\192.0.2.50\fast-ssd
    Then use Z:\engel-distributed-training as base.

Launch order:
1. On 730xd (or any machine), start this on node 0 first.
2. Then on the second GPU machine, run multi-node-launch-node1.ps1

Master is the 730xd for rendezvous.
#>

$ErrorActionPreference = 'Stop'

# === CONFIG - EDIT THESE ===
$SHARED_BASE = "Z:\engel-distributed-training"   # <-- Mount of 730xd SSD
$PACKAGE_DIR = "D:\b.WorkSpace\Engel App\runtime\engel_lora_training_package"  # local copy of package, or point inside $SHARED_BASE
$VENV_PYTHON = "D:\b.WorkSpace\Engel App\runtime\training-convo-gpu\venv\Scripts\python.exe"

$MASTER_ADDR = "192.0.2.50"   # 730xd IP
$MASTER_PORT = 29500
$NNODES = 2
$NPROC_PER_NODE = 1
$NODE_RANK = 0

# Shared paths (create these on 730xd)
$DATASET = "$SHARED_BASE\dataset\engel_standalone_sft.jsonl"
$OUTPUT_DIR = "$SHARED_BASE\outputs\multi-node-run-$(Get-Date -Format yyyyMMdd-HHmmss)"

# Ensure dirs
New-Item -ItemType Directory -Force -Path $OUTPUT_DIR | Out-Null

Write-Host "=== Multi-node Node 0 (this GPU) ==="
Write-Host "Master: $MASTER_ADDR:$MASTER_PORT"
Write-Host "Output (on 730xd SSD): $OUTPUT_DIR"

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

Write-Host "Node 0 finished (or crashed). Check $OUTPUT_DIR"