$key = "$env:USERPROFILE\.ssh\engel_ai_main_ct246_ed25519"
ssh -i $key -o BatchMode=yes -p 24622 root@192.0.2.50 '
source /mnt/ssd-ai/training/venvs/engel-train-venv/bin/activate 2>/dev/null || true
cd /mnt/ssd-ai/training/distributed/package
mkdir -p /mnt/ssd-ai/training/distributed/outputs /mnt/ssd-ai/training/distributed/logs
nohup python train_engel_lora.py --base-model Qwen/Qwen2.5-7B-Instruct --dataset dataset/engel_standalone_sft.jsonl --output-dir /mnt/ssd-ai/training/distributed/outputs/730xd-cpu-convo --max-steps 200 --max-length 256 --lr 2e-4 > /mnt/ssd-ai/training/distributed/logs/730xd-cpu-convo.log 2>&1 &
echo "730xd CPU convo training started."
sleep 3
tail -5 /mnt/ssd-ai/training/distributed/logs/730xd-cpu-convo.log || true
'
