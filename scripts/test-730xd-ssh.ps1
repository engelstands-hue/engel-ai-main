$ErrorActionPreference = 'Stop'
$key = "$env:USERPROFILE\.ssh\engel_ai_main_ct246_ed25519"
if (Test-Path $key) {
    Write-Host "Key found at $key"
    $result = ssh -i $key -o BatchMode=yes -o StrictHostKeyChecking=no -p 24622 root@192.0.2.50 'echo "SSH_CONNECTION_OK" ; hostname ; uptime ; echo "GPU check:" ; (nvidia-smi -L 2>/dev/null || echo "no nvidia-smi or no GPUs visible") ; df -h / | tail -1'
    Write-Host $result
} else {
    Write-Host "Key not found at expected path: $key"
    if (Test-Path 'D:\pod\id_ed25519') {
        Write-Host "Alternative D:\pod key exists (may be for RunPod)"
    }
    Get-ChildItem "$env:USERPROFILE\.ssh" -ErrorAction SilentlyContinue | Select-Object Name, FullName
}