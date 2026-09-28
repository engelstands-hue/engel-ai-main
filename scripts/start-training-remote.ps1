$key = "$env:USERPROFILE\.ssh\engel_ai_main_ct246_ed25519"
Write-Host "Making script executable and starting training on 730xd..."
ssh -i $key -o BatchMode=yes -o StrictHostKeyChecking=no -p 24622 root@192.0.2.50 '
cd /mnt/ssd-ai/training/packages/engel-training-convo-20260701
chmod +x launch-convo-training-on-730xd.sh
ENGEL_TRAINING_PACKAGE_ROOT=/mnt/ssd-ai/training/packages/engel-training-convo-20260701 ENGEL_TRAINING_ARCHIVE_ROOT=/mnt/engel-hdd-vault/training-outputs nohup ./launch-convo-training-on-730xd.sh > /mnt/ssd-ai/training/logs/launcher.out 2>&1 &
sleep 3
echo "Background training launch initiated."
cat /mnt/ssd-ai/training/logs/launcher.out || true
echo "---- current processes ----"
ps aux | grep -E "(python|train|pip)" | grep -v grep || echo "no matching processes yet"
'
