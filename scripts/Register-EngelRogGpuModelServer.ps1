<#
.SYNOPSIS
  Register (and start) the ROG GPU model server as a logon scheduled task so it
  survives reboots and session ends. Runs the venv python directly via cmd (the
  hidden-PowerShell launcher failed on stream redirection), keeping the 7B warm
  on the RTX 2070 as an OpenAI endpoint on 127.0.0.1:8899.

  Remove:  Unregister-ScheduledTask -TaskName EngelRogGpuModelServer -Confirm:$false
#>
param(
    [string]$TaskName = "EngelRogGpuModelServer",
    [int]$Port = 8899,
    [switch]$NoStartNow
)
$ErrorActionPreference = "Stop"
$venvpy = "D:\b.WorkSpace\Engel App\runtime\gpu_llm_venv\Scripts\python.exe"
$model = "D:\b.WorkSpace\Engel App\runtime\gpu_models\Mistral-7B-Instruct-v0.3-Q4_K_M.gguf"
$log = Join-Path $env:LOCALAPPDATA "Engel AI Main\logs\rog-gpu-model-server.log"
New-Item -ItemType Directory -Force -Path (Split-Path $log) | Out-Null

# Run python.exe DIRECTLY (a cmd wrapper mangles the space-filled paths and the
# task never starts). Output isn't captured to a file, but the server is the
# point; startup can be checked by the port + nvidia-smi VRAM.
$argstr = "-m llama_cpp.server --model `"$model`" --n_gpu_layers -1 --n_ctx 8192 --host 127.0.0.1 --port $Port"
$action = New-ScheduledTaskAction -Execute $venvpy -Argument $argstr -WorkingDirectory (Split-Path $venvpy -Parent)
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew `
    -RestartCount 5 -RestartInterval (New-TimeSpan -Minutes 1) -StartWhenAvailable
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Principal $principal -Settings $settings -Force | Out-Null
Write-Host "Registered scheduled task '$TaskName' (runs at logon)."
if (-not $NoStartNow) { Start-ScheduledTask -TaskName $TaskName; Write-Host "Started task now." }
Write-Host "Remove with: Unregister-ScheduledTask -TaskName $TaskName -Confirm:`$false"
