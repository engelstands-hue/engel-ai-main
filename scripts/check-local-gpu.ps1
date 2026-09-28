Write-Output '=== Local Windows GPU / CUDA check (for training target) ==='

if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
    nvidia-smi --query-gpu=name,memory.total,memory.free,driver_version --format=csv
} else {
    Write-Output 'nvidia-smi not found on this machine PATH'
}

Write-Output ''
Write-Output 'Project Python torch check:'
& 'D:\b.WorkSpace\Engel App\runtime\python310\python.exe' -c "
import sys
print('python:', sys.executable)
try:
    import torch
    print('torch version:', torch.__version__)
    print('cuda available:', torch.cuda.is_available())
    if torch.cuda.is_available():
        print('gpu count:', torch.cuda.device_count())
        for i in range(torch.cuda.device_count()):
            print('  gpu', i, torch.cuda.get_device_name(i), round(torch.cuda.get_device_properties(i).total_memory/1024**3,1), 'GB')
except Exception as e:
    print('torch error:', e)
" 2>&1 | Out-String

Write-Output ''
Write-Output 'Checking if this machine looks like one of the 8GB GPU machines.'