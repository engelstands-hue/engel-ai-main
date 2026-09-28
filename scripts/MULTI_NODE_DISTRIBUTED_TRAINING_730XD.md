# Real Multi-Node Distributed Training on 730xd + 2x 8GB GPUs

**Launch everything from the Engel AI Main laptop** using the new `launch_distributed_training_from_laptop.ps1` (which uses Hugging Face Accelerate under the hood).

This is the recommended "accelerate launch version". It also optionally starts a CPU job on the 730xd so all three participate at the same time.

All I/O (dataset, checkpoints, final adapters) goes to the 730xd fast SSD.

All heavy compute runs on the two 8GB GPU machines in data-parallel.
All dataset, model cache, checkpoints and final adapters live on the 730xd fast SSD (great network).

The 730xd acts as:
- Master for torch.distributed rendezvous
- Central storage (via SMB/NFS mount on the Windows GPU machines)
- Optional CPU-only training node running in parallel

## Prerequisites
1. On the 730xd, export a directory on the fast SSD so both GPU machines can mount it with the **same path** (example):
   - Windows GPU machines: `net use Z: \\192.0.2.50\fast-ssd`
   - Then use `Z:\engel-distributed-training` everywhere.

2. On **both** GPU machines:
   - Same Python 3.10+ venv with CUDA torch + the packages (see previous setup).
   - The updated `train_engel_lora.py` (distributed support added 2026-07-01).

3. Dataset and package source placed on the shared 730xd path.

## Step-by-step

### 1. On 730xd (prepare shared area)
```bash
mkdir -p /mnt/fast-ssd/engel-distributed-training/{dataset,outputs,logs,package}
# Copy or rsync the training package + the updated conversation dataset here
```

### 2. On GPU Node 0 (first 8GB machine)
Run:
```powershell
.\multi-node-launch-node0.ps1
```
( Edit the SHARED_BASE, VENV_PYTHON and PACKAGE_DIR at the top first )

This becomes node_rank=0 and starts the master.

### 3. On GPU Node 1 (second 8GB machine)
Run:
```powershell
.\multi-node-launch-node1.ps1
```

### 4. (Optional) Extra CPU job on 730xd
```bash
nohup python3 /path/to/package/train_engel_lora.py \
  --base-model Qwen/Qwen2.5-7B-Instruct \
  --dataset /mnt/fast-ssd/.../dataset/engel_standalone_sft.jsonl \
  --output-dir /mnt/fast-ssd/.../outputs/730xd-cpu \
  --max-steps 500 \
  > /mnt/fast-ssd/.../logs/730xd-cpu.log 2>&1 &
```

Now you have real distributed training on the two GPUs + work happening on the 730xd at the same time.

## Monitoring
From anywhere that can reach the share:
```bash
tail -f /mnt/fast-ssd/engel-distributed-training/logs/*.log
# or on Windows
Get-Content Z:\engel-distributed-training\logs\*.log -Wait -Tail 30
```

## After training
- All three (or two) adapters will be under the shared `outputs/` directory on the 730xd SSD.
- Pick the best one, convert to GGUF, update the SSD Chat LLM profile.

## Tips for 8GB cards + 7B QLoRA
- The launchers use conservative batch=1 + grad_accum.
- If OOM, reduce max_length or grad_accum.
- Use the same random seed across nodes if you want reproducible sharding.

## Recommended: Launch Everything from the Laptop (Accelerate version)

1. On the laptop (Engel AI Main):
   ```powershell
   cd D:\b.WorkSpace\Engel App\scripts
   # Edit paths at the top of the script if needed (SHARED_BASE, OTHER_GPU_HOST, keys, etc.)
   .\launch_distributed_training_from_laptop.ps1
   ```

   The script will:
   - Sync the latest package + dataset to the 730xd SSD.
   - SSH to the second GPU machine and start `accelerate launch` (node 1).
   - Run `accelerate launch` locally (node 0).
   - Also start a CPU job on the 730xd for full participation.

2. The accelerate config is in the package: `accelerate_multi_node.yaml` (machine_rank is overridden on CLI).

3. Monitor from the laptop:
   ```powershell
   Get-Content "$SHARED_BASE\logs\*.log" -Wait -Tail 30
   ```

All saves land on the 730xd SSD under the `outputs\` folder.

## Alternative: Pure torchrun (if you prefer no accelerate)

Use the older `multi-node-launch-node0.ps1` / `node1.ps1` with `torchrun` directly (still supported).

## After Training

- Adapters from all runs are in `$SHARED_BASE\outputs\...`
- Pick the best one → convert to GGUF → update the SSD Chat LLM profile on the 730xd.
- This should make the local conversation feel significantly more natural.

## Tips
- Make sure the SSD is mounted at the **exact same path** on both Windows GPU machines.
- Have passwordless SSH from laptop → other GPU machine and laptop → 730xd.
- For the second machine's venv path, edit the remote command in the launcher script.
- If you hit NCCL issues on Windows, the accelerate config + gloo fallback can be tuned.

Run the launcher from your Engel AI Main laptop and all three will be working together.