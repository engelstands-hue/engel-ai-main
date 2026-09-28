#!/usr/bin/env bash
set -euo pipefail

SSD_TRAINING_ROOT="${ENGEL_TRAINING_WORK_ROOT:-/mnt/ssd-ai/training}"
HDD_TRAINING_ARCHIVE="${ENGEL_TRAINING_ARCHIVE_ROOT:-/mnt/engel-hdd-vault/training-outputs}"
TRAIN_DIR="${ENGEL_TRAINING_PACKAGE_ROOT:-$SSD_TRAINING_ROOT/packages/engel-training-convo-20260701}"
VENV_DIR="$SSD_TRAINING_ROOT/venvs/engel-train-venv"
RUN_ID="engel-fix-launch-$(date -u +%Y%m%dT%H%M%SZ)"
LOG_DIR="$SSD_TRAINING_ROOT/logs"
OUTPUT_DIR="$SSD_TRAINING_ROOT/runs/$RUN_ID"
RECEIPT_DIR="$HDD_TRAINING_ARCHIVE/receipts"

case "$SSD_TRAINING_ROOT $HDD_TRAINING_ARCHIVE $TRAIN_DIR" in
  *"/mnt/engel-vault"*) echo "Retired external-array path /mnt/engel-vault is permanently forbidden; refusing training launch." >&2; exit 2 ;;
esac

mkdir -p "$SSD_TRAINING_ROOT/venvs" "$LOG_DIR" "$OUTPUT_DIR" "$RECEIPT_DIR"
cd "$TRAIN_DIR/extracted"

echo "Creating venv for training (avoids externally-managed issues)..."
python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

echo "Installing requirements in venv..."
pip install --upgrade pip wheel
pip install -r requirements.txt

echo "Checking torch/cuda in venv..."
python -c '
import torch
print("torch:", torch.__version__)
print("cuda:", torch.cuda.is_available())
if torch.cuda.is_available():
    print("gpu:", torch.cuda.get_device_name(0))
'

echo "Starting training (background, logs to $LOG_DIR/$RUN_ID.log)..."
nohup python train_engel_lora.py \
  --base_model "Qwen/Qwen2.5-7B-Instruct" \
  --dataset dataset/engel_standalone_sft.jsonl \
  --output_dir "$OUTPUT_DIR" \
  --max_steps 500 \
  --batch_size 1 \
  --gradient_accumulation_steps 4 \
  --lora_r 8 \
  --learning_rate 1e-4 \
  --max_length 384 \
  > "$LOG_DIR/$RUN_ID.log" 2>&1 &
PID="$!"

cat > "$RECEIPT_DIR/${RUN_ID}_launch.json" <<EOF
{
  "schema": "engel_training_launch_receipt_v1",
  "ok": true,
  "started_at_utc": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "run_id": "$RUN_ID",
  "pid": $PID,
  "package_dir": "$TRAIN_DIR/extracted",
  "venv_dir": "$VENV_DIR",
  "output_dir": "$OUTPUT_DIR",
  "log": "$LOG_DIR/$RUN_ID.log",
  "active_training_root": "$SSD_TRAINING_ROOT",
  "archive_root": "$HDD_TRAINING_ARCHIVE",
  "retired_external_array_forbidden": "/mnt/engel-vault"
}
EOF

echo "Training launched in background."
echo "Monitor with: tail -f $LOG_DIR/$RUN_ID.log"
echo "Deactivate venv when done: deactivate"
