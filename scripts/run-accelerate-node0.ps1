$venvPy = 'D:\b.WorkSpace\Engel App\runtime\training-convo-gpu\venv\Scripts\python.exe'
$pkg = 'D:\b.WorkSpace\Engel App\runtime\engel_lora_training_package'
$out = 'D:\b.WorkSpace\Engel App\runtime\outputs\multi-node-demo'
New-Item -ItemType Directory -Force -Path $out | Out-Null

Write-Output 'Starting accelerate launch for node 0 (laptop GPU) ...'

& $venvPy -m accelerate.commands.launch `
  --config_file "$pkg\accelerate_multi_node.yaml" `
  --machine_rank 0 `
  --main_process_ip 192.0.2.50 `
  --main_process_port 29500 `
  --num_machines 2 `
  --num_processes 2 `
  "$pkg\train_engel_lora.py" `
    --base-model "Qwen/Qwen2.5-7B-Instruct" `
    --dataset "$pkg\dataset\engel_standalone_sft.jsonl" `
    --output-dir $out `
    --max-steps 30 `
    --max-length 128 `
    --lr "2e-4" 2>&1 | Select-Object -First 40

Write-Output 'Accelerate node 0 launch attempted (see output above for any errors or training start).'