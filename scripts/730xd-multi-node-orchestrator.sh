#!/usr/bin/env bash
# Run this on the 730xd server.
# It prepares the shared dir and can launch the distributed training.
#
# Assumptions:
# - You have mounted/exported the fast SSD so both GPU Windows machines see it as Z:\ or equivalent.
# - The two GPU machines have SSH or you will manually start the node scripts on them.
# - Package has been copied to the shared dir or each machine has a local copy of the code.

set -euo pipefail

SHARED_BASE="/mnt/fast-ssd/engel-distributed-training"   # adjust to your actual mount on 730xd
PACKAGE_DIR="$SHARED_BASE/package"                       # or wherever you put the source

mkdir -p "$SHARED_BASE/dataset" "$SHARED_BASE/outputs" "$SHARED_BASE/logs"

echo "=== Preparing shared training dir on 730xd SSD ==="
echo "SHARED_BASE=$SHARED_BASE"

# Copy dataset if not present
if [[ ! -f "$SHARED_BASE/dataset/engel_standalone_sft.jsonl" ]]; then
  cp -v runtime/engel_lora_training_package/dataset/engel_standalone_sft.jsonl "$SHARED_BASE/dataset/" || echo "Please copy the dataset manually to $SHARED_BASE/dataset/"
fi

# Copy the training package source (so nodes can run the .py)
mkdir -p "$PACKAGE_DIR"
rsync -a --delete runtime/engel_lora_training_package/ "$PACKAGE_DIR/" || echo "rsync the package to $PACKAGE_DIR"

echo
echo "=== Multi-node setup ready ==="
echo "1. On GPU node 0 (Windows): run multi-node-launch-node0.ps1 (pointing SHARED_BASE to the mounted drive)"
echo "2. On GPU node 1 (Windows): run multi-node-launch-node1.ps1"
echo
echo "Master address for torchrun: this machine's IP (192.0.2.50)"
echo
echo "Optional: launch a CPU-only job on 730xd in parallel:"
echo "  nohup python3 $PACKAGE_DIR/train_engel_lora.py --base-model Qwen/Qwen2.5-7B-Instruct --dataset $SHARED_BASE/dataset/engel_standalone_sft.jsonl --output-dir $SHARED_BASE/outputs/730xd-cpu --max-steps 500 --max-length 256 > $SHARED_BASE/logs/730xd-cpu.log 2>&1 &"
echo
echo "Monitor from anywhere:"
echo "  tail -f $SHARED_BASE/logs/*.log"
echo "  ls $SHARED_BASE/outputs/"