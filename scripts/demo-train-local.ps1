$venvPy = 'D:\b.WorkSpace\Engel App\runtime\training-convo-gpu\venv\Scripts\python.exe'
$pkg = 'D:\b.WorkSpace\Engel App\runtime\engel_lora_training_package'
$out = 'D:\b.WorkSpace\Engel App\runtime\outputs\chat-llm-convo-demo'
New-Item -ItemType Directory -Force -Path $out | Out-Null

Write-Output '=== Demo training start on local 8GB GPU (as part of multi-node setup) ==='
$logFile = "$out\train.log"
$job = Start-Job -ScriptBlock {
    param($venvPy, $pkg, $out)
    & $venvPy $pkg\train_engel_lora.py --base-model Qwen/Qwen2.5-7B-Instruct --dataset $pkg\dataset\engel_standalone_sft.jsonl --output-dir $out --max-steps 50 --max-length 128 --lr 2e-4 *>&1 | Out-File -FilePath $using:logFile -Append
} -ArgumentList $venvPy, $pkg, $out

Write-Output "Training started as job. Job Id: $($job.Id)"
Write-Output "Log: $logFile"
Start-Sleep -Seconds 10
Receive-Job $job -Keep | Select -First 10
Get-Job $job | Select Id, State, HasMoreData | Format-Table
if (Test-Path $logFile) { Get-Content $logFile -Tail 10 } else { Write-Output "No log file yet" }