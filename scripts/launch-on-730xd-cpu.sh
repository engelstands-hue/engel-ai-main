#!/usr/bin/env bash
set -euo pipefail

SSD_TRAINING_ROOT="${ENGEL_TRAINING_WORK_ROOT:-/mnt/ssd-ai/training}"
HDD_TRAINING_ARCHIVE="${ENGEL_TRAINING_ARCHIVE_ROOT:-/mnt/engel-hdd-vault/training-outputs}"
PACKAGE_ROOT="${ENGEL_TRAINING_PACKAGE_ROOT:-$SSD_TRAINING_ROOT/packages/engel-training-convo-20260701}"
PACKAGE_DIR="$PACKAGE_ROOT/extracted"
RUN_ID="engel-730xd-cpu-$(date -u +%Y%m%dT%H%M%SZ)"
LOG_DIR="$SSD_TRAINING_ROOT/logs"
OUTDIR="$SSD_TRAINING_ROOT/runs/$RUN_ID"
LOG="$LOG_DIR/$RUN_ID.log"
RECEIPT_DIR="$HDD_TRAINING_ARCHIVE/receipts"

case "$SSD_TRAINING_ROOT $HDD_TRAINING_ARCHIVE $PACKAGE_ROOT" in
  *"/mnt/engel-vault"*) echo "Retired external-array path /mnt/engel-vault is permanently forbidden; refusing CPU training launch." >&2; exit 2 ;;
esac

mkdir -p "$LOG_DIR" "$OUTDIR" "$RECEIPT_DIR"
cd "$PACKAGE_DIR" 2>/dev/null || cd "$PACKAGE_ROOT"

echo "=== Launching CPU training on 730xd (no GPU) ==="
echo "This will be slow but runs in parallel with the GPU jobs."

export CUDA_VISIBLE_DEVICES=""
export OMP_NUM_THREADS=4

nohup python3 train_engel_lora.py \
  --base_model "Qwen/Qwen2.5-7B-Instruct" \
  --dataset "dataset/engel_standalone_sft.jsonl" \
  --output_dir "$OUTDIR" \
  --max-steps 400 \
  --max-length 256 \
  --lr 2e-4 \
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
  "output_dir": "$OUTDIR",
  "log": "$LOG",
  "active_training_root": "$SSD_TRAINING_ROOT",
  "archive_root": "$HDD_TRAINING_ARCHIVE",
  "retired_external_array_forbidden": "/mnt/engel-vault"
}
EOF

echo "Training launched on 730xd."
echo "Log: $LOG"
echo "Output: $OUTDIR"
echo "Receipt: $RECEIPT_DIR/${RUN_ID}_launch.json"
echo "To monitor: tail -f $LOG"
