$ErrorActionPreference = 'Continue'
$key = "$env:USERPROFILE\.ssh\engel_ai_main_ct246_ed25519"
$zip = 'D:\b.WorkSpace\Engel App\runtime\engel_lora_training_package\engel_standalone_lora_training_package.zip'
$remoteDir = '/mnt/ssd-ai/training/packages/engel-training-convo-20260701'
$archiveDir = '/mnt/engel-hdd-vault/training-outputs'

Write-Host "=== Transferring conversational training package to 730xd server ==="

if (-not (Test-Path $key)) {
    Write-Error "SSH key not found at $key"
    exit 1
}

Write-Host "Creating remote dir..."
ssh -i $key -o BatchMode=yes -o StrictHostKeyChecking=no -p 24622 root@192.0.2.50 "set -e; test -d /mnt/engel-hdd-vault; mkdir -p $remoteDir $archiveDir/receipts"

Write-Host "Copying zip..."
scp -i $key -o BatchMode=yes -o StrictHostKeyChecking=no -P 24622 $zip "root@192.0.2.50:$remoteDir/"

Write-Host "Verifying on server..."
ssh -i $key -o BatchMode=yes -o StrictHostKeyChecking=no -p 24622 root@192.0.2.50 "ls -lh $remoteDir && echo '--- disk ---' && df -hT /mnt/ssd-ai /mnt/engel-hdd-vault && echo '--- nvidia ---' && (nvidia-smi -L 2>/dev/null || echo 'nvidia-smi not visible in this shell')"

Write-Host "Done. Package is on the 730xd."
