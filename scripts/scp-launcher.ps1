$key = "$env:USERPROFILE\.ssh\engel_ai_main_ct246_ed25519"
$launcher = 'D:\b.WorkSpace\Engel App\scripts\launch-convo-training-on-730xd.sh'
$remoteDir = '/mnt/ssd-ai/training/packages/engel-training-convo-20260701'
ssh -i $key -o BatchMode=yes -o StrictHostKeyChecking=no -p 24622 root@192.0.2.50 "mkdir -p $remoteDir"
scp -i $key -o BatchMode=yes -o StrictHostKeyChecking=no -P 24622 $launcher "root@192.0.2.50:$remoteDir/"
Write-Host "Launcher script copied to server."
