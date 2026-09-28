#!/usr/bin/env bash
set -euo pipefail

SSD_TRAINING_ROOT="${ENGEL_TRAINING_WORK_ROOT:-/mnt/ssd-ai/training}"
HDD_TRAINING_ARCHIVE="${ENGEL_TRAINING_ARCHIVE_ROOT:-/mnt/engel-hdd-vault/training-outputs}"
PACKAGE_ROOT="${ENGEL_TRAINING_PACKAGE_ROOT:-$SSD_TRAINING_ROOT/packages/engel-training-convo-20260701}"
PACKAGE_DIR="$PACKAGE_ROOT/extracted"
RUN_ID="engel-convo-lora-$(date -u +%Y%m%dT%H%M%SZ)"
OUTPUT_DIR="$SSD_TRAINING_ROOT/runs/$RUN_ID"
LOG_DIR="$SSD_TRAINING_ROOT/logs"
LOG="$LOG_DIR/$RUN_ID.log"
RECEIPT_DIR="$HDD_TRAINING_ARCHIVE/receipts"

case "$SSD_TRAINING_ROOT $HDD_TRAINING_ARCHIVE $PACKAGE_ROOT" in
  *"/mnt/engel-vault"*) echo "Retired external-array path /mnt/engel-vault is permanently forbidden; refusing training launch." >&2; exit 2 ;;
esac

if ! findmnt -T /mnt/engel-hdd-vault >/dev/null 2>&1; then
  echo "Dell PowerEdge HDD vault /mnt/engel-hdd-vault is not mounted; refusing archive receipt write." >&2
  exit 2
fi

mkdir -p "$SSD_TRAINING_ROOT/runs" "$LOG_DIR" "$RECEIPT_DIR"

cd "$PACKAGE_DIR"

echo "=== Installing requirements (this may take time) ==="
python3 -m pip install --upgrade pip wheel
python3 -m pip install -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cu121 2>&1 | tail -5 || python3 -m pip install -r requirements.txt 2>&1 | tail -10

echo
echo "=== Environment check ==="
python3 -c '
import torch
print("torch:", torch.__version__)
print("cuda available:", torch.cuda.is_available())
if torch.cuda.is_available():
    print("gpu:", torch.cuda.get_device_name(0))
    print("mem:", round(torch.cuda.get_device_properties(0).total_memory / 1e9, 1), "GB")
' || echo "torch check failed (may be CPU only)"

echo
echo "=== Launching LoRA training for conversational Chat LLM ==="
echo "Using updated dataset with real conversation examples."
echo "This is long-running. Output will be logged."

nohup python3 train_engel_lora.py \
  --base_model "Qwen/Qwen2.5-7B-Instruct" \
  --dataset "dataset/engel_standalone_sft.jsonl" \
  --output_dir "$OUTPUT_DIR" \
  --max_steps 2000 \
  --batch_size 1 \
  --gradient_accumulation 8 \
  --lora_r 16 \
  --lora_alpha 32 \
  --lora_dropout 0.05 \
  --learning_rate 2e-4 \
  --max_length 512 \
  > "$LOG" 2>&1 &
PID="$!"

cat > "$RECEIPT_DIR/${RUN_ID}_launch.json" <<EOF
{
  "schema": "engel_training_launch_receipt_v1",
  "ok": true,
  "started_at_utc": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "run_id": "$RUN_ID",
  "pid": $PID,
  "package_dir": "$PACKAGE_DIR",
  "output_dir": "$OUTPUT_DIR",
  "log": "$LOG",
  "active_training_root": "$SSD_TRAINING_ROOT",
  "archive_root": "$HDD_TRAINING_ARCHIVE",
  "retired_external_array_forbidden": "/mnt/engel-vault"
}
EOF

echo "Training started in background."
echo "Log: $LOG"
echo "Output: $OUTPUT_DIR"
echo "Receipt: $RECEIPT_DIR/${RUN_ID}_launch.json"
echo "To watch: tail -f $LOG"
echo "To check if running: ps aux | grep train_engel_lora"
echo
echo "When done, the adapter will be in the output_dir. Then convert to GGUF for SSD Chat LLM use."
