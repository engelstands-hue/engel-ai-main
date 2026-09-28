$key = "$env:USERPROFILE\.ssh\engel_ai_main_ct246_ed25519"
ssh -i $key -o BatchMode=yes -p 24622 root@192.0.2.50 '
set -e
cd /mnt/ssd-ai/training/distributed/package
mkdir -p /mnt/ssd-ai/training/venvs
python3 -m venv /mnt/ssd-ai/training/venvs/engel-train-venv
source /mnt/ssd-ai/training/venvs/engel-train-venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
echo "Venv and requirements installed on 730xd for CPU training."
'
