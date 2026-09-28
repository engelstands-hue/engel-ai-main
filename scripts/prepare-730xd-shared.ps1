$key = "$env:USERPROFILE\.ssh\engel_ai_main_ct246_ed25519"
ssh -i $key -o BatchMode=yes -p 24622 root@192.0.2.50 '
set -e
mkdir -p /mnt/ssd-ai/training/distributed/{dataset,outputs,logs,package} /mnt/engel-hdd-vault/training-outputs/receipts
echo "Directories prepared on 730xd SSD at /mnt/ssd-ai/training/distributed"
ls -d /mnt/ssd-ai/training/distributed/*
'
