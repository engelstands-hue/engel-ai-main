$key = "$env:USERPROFILE\.ssh\engel_ai_main_ct246_ed25519"
ssh -i $key -o BatchMode=yes -o StrictHostKeyChecking=no -p 24622 root@192.0.2.50 '
echo "=== Package location ==="
ls -l /mnt/ssd-ai/training/packages/engel-training-convo-20260701/ 2>/dev/null || echo missing package
echo
echo "=== Launcher output (last lines) ==="
tail -30 /mnt/ssd-ai/training/logs/launcher.out 2>/dev/null || echo no launcher.out yet
echo
echo "=== Latest training log ==="
ls -t /mnt/ssd-ai/training/logs/*.log 2>/dev/null | head -1 | xargs -r tail -30 || echo no training log yet
echo
echo "=== Processes ==="
ps aux | grep -E "(python|pip|train)" | grep -v grep || echo none
echo
echo "=== Training storage ==="
df -hT /mnt/ssd-ai /mnt/engel-hdd-vault
findmnt -T /mnt/engel-hdd-vault || true
echo
echo "=== Python and torch status ==="
python3 --version 2>/dev/null || echo no python3
python3 -c "import torch; print(torch.__version__, \"cuda:\", torch.cuda.is_available())" 2>/dev/null || echo "no torch in system python"
' 
