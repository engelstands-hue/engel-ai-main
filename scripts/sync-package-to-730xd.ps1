$key = "$env:USERPROFILE\.ssh\engel_ai_main_ct246_ed25519"
$localPkg = 'D:\b.WorkSpace\Engel App\runtime\engel_lora_training_package'
$remotePackage = '/mnt/ssd-ai/training/distributed/package'

ssh -i $key -o BatchMode=yes -p 24622 root@192.0.2.50 "mkdir -p $remotePackage"

scp -i $key -o BatchMode=yes -P 24622 -r "$localPkg/*" "root@192.0.2.50:$remotePackage/"

Write-Host "Package synced to 730xd."

ssh -i $key -o BatchMode=yes -p 24622 root@192.0.2.50 "ls $remotePackage/ | head -5"
