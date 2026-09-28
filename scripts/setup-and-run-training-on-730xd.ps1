$ErrorActionPreference = 'Continue'
$key = "$env:USERPROFILE\.ssh\engel_ai_main_ct246_ed25519"
$remoteDir = '/mnt/ssd-ai/training/packages/engel-training-convo-20260701'
$archiveDir = '/mnt/engel-hdd-vault/training-outputs'
Write-Host "=== Setup training on 730xd ==="

$remoteCmd = @'
set -euo pipefail
REMOTE_DIR="${ENGEL_TRAINING_PACKAGE_ROOT:-/mnt/ssd-ai/training/packages/engel-training-convo-20260701}"
ARCHIVE_DIR="${ENGEL_TRAINING_ARCHIVE_ROOT:-/mnt/engel-hdd-vault/training-outputs}"
OFFLINE_CT245_MOUNT="/mnt/"engel-vault
case "$REMOTE_DIR $ARCHIVE_DIR" in *"$OFFLINE_CT245_MOUNT"*) echo "CT245 offline-vault storage is disabled; refusing setup." >&2; exit 2 ;; esac
mkdir -p "$REMOTE_DIR" "$ARCHIVE_DIR/receipts" /mnt/ssd-ai/training/{runs,logs,datasets,venvs}
cd "$REMOTE_DIR"
echo "Extracting package..."
if ! command -v unzip >/dev/null; then
  apt-get update -qq && apt-get install -y -qq unzip
fi
rm -rf extracted
unzip -q engel_standalone_lora_training_package.zip -d extracted
ls -l extracted/
echo
echo "=== Dataset info ==="
ls -l extracted/dataset/ || true
wc -l extracted/dataset/engel_standalone_sft.jsonl || true
echo
echo "=== Training launch info ==="
cat extracted/run_training.sh || true
echo
head -c 500 extracted/train_engel_lora.py || true
echo
echo "=== Ready. To run (example, adjust for your env):"
echo "cd $REMOTE_DIR/extracted"
echo "python3 -m pip install -r requirements.txt"
echo "python3 train_engel_lora.py --base_model Qwen/Qwen2.5-7B-Instruct --dataset dataset/engel_standalone_sft.jsonl --output_dir /mnt/ssd-ai/training/runs/engel-lora-output --max_steps 1000 --lora_r 16"
echo
echo "For full conversational training on this hardware, use your GPU-enabled env or container."
'@

ssh -i $key -o BatchMode=yes -o StrictHostKeyChecking=no -p 24622 root@192.0.2.50 "ENGEL_TRAINING_PACKAGE_ROOT='$remoteDir' ENGEL_TRAINING_ARCHIVE_ROOT='$archiveDir' bash -lc '$remoteCmd'"

Write-Host "Setup commands executed on 730xd."
