$key = "$env:USERPROFILE\.ssh\engel_ai_main_ct246_ed25519"
$script = 'D:\b.WorkSpace\Engel App\scripts\launch-on-730xd-cpu.sh'

Write-Host "Copying CPU launcher to 730xd..."
scp -i $key -o BatchMode=yes -o StrictHostKeyChecking=no -P 24622 $script root@192.0.2.50:/root/

Write-Host "Launching CPU training on 730xd in parallel..."
ssh -i $key -o BatchMode=yes -o StrictHostKeyChecking=no -p 24622 root@192.0.2.50 '
mkdir -p /mnt/ssd-ai/training/logs
chmod +x /root/launch-on-730xd-cpu.sh
ENGEL_TRAINING_PACKAGE_ROOT=/mnt/ssd-ai/training/packages/engel-training-convo-20260701 ENGEL_TRAINING_ARCHIVE_ROOT=/mnt/engel-hdd-vault/training-outputs nohup /root/launch-on-730xd-cpu.sh > /mnt/ssd-ai/training/logs/730xd-launch.log 2>&1 &
sleep 4
cat /mnt/ssd-ai/training/logs/730xd-launch.log
echo "=== Active training logs on 730xd ==="
ls -lt /mnt/ssd-ai/training/logs/*cpu*.log /mnt/ssd-ai/training/runs/* 2>/dev/null | head -5
' 
