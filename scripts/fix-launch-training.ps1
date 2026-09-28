$key = "$env:USERPROFILE\.ssh\engel_ai_main_ct246_ed25519"
$fix = 'D:\b.WorkSpace\Engel App\scripts\fix-and-launch-training.sh'
$remoteDir = '/mnt/ssd-ai/training/packages/engel-training-convo-20260701'
$archiveDir = '/mnt/engel-hdd-vault/training-outputs'

Write-Host "Copying fix launcher..."
scp -i $key -o BatchMode=yes -o StrictHostKeyChecking=no -P 24622 $fix "root@192.0.2.50:$remoteDir/"

Write-Host "Running fix and launch..."
ssh -i $key -o BatchMode=yes -o StrictHostKeyChecking=no -p 24622 root@192.0.2.50 "
mkdir -p $remoteDir $archiveDir/receipts /mnt/ssd-ai/training/logs
cd $remoteDir
chmod +x fix-and-launch-training.sh
ENGEL_TRAINING_PACKAGE_ROOT=$remoteDir ENGEL_TRAINING_ARCHIVE_ROOT=$archiveDir nohup ./fix-and-launch-training.sh > /mnt/ssd-ai/training/logs/fix-launch.out 2>&1 &
sleep 15
cat /mnt/ssd-ai/training/logs/fix-launch.out || true
echo '=== recent train log ==='
ls -t /mnt/ssd-ai/training/logs/*.log 2>/dev/null | head -1 | xargs -r tail -30 || echo 'no train log yet (installing may take time)'
echo '=== processes ==='
ps aux | grep -E 'python|train' | grep -v grep | head -5 || true
"
