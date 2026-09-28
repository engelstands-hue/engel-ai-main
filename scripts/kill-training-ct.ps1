$key = "$env:USERPROFILE\.ssh\engel_ai_main_ct246_ed25519"
ssh -i $key -o BatchMode=yes -o StrictHostKeyChecking=no -p 24622 root@192.0.2.50 '
pkill -9 -f "engel-train-venv" || true
pkill -9 -f "train_engel_lora" || true
pkill -9 -f "fix-and-launch-training" || true
echo "Cleaned any training related processes on the CT"
ps aux | grep -E "python|pip" | grep -v grep | head -5 || echo "no matching processes"
'