$key = "$env:USERPROFILE\.ssh\engel_ai_main_ct246_ed25519"
ssh -i $key -o BatchMode=yes -o StrictHostKeyChecking=no -p 24622 root@192.0.2.50 '
cd /mnt/ssd-ai/training/packages/engel-training-convo-20260701/extracted
echo "=== train_engel_lora.py --help ==="
python3 train_engel_lora.py --help 2>&1 || true
echo
echo "=== Checking torch / cuda availability ==="
python3 -c "
import torch
print(\"torch:\", torch.__version__)
print(\"cuda available:\", torch.cuda.is_available())
if torch.cuda.is_available():
    print(\"device:\", torch.cuda.get_device_name(0))
print(\"cuda version:\", torch.version.cuda if hasattr(torch.version, \"cuda\") else \"n/a\")
" 2>&1 || echo "python torch check failed"
' 
