# Reset the Engel chat worker: kill all worker processes so the app respawns a fresh
# one from the current (action-lane) file. Fixes a wedged/stale worker.
$log = "D:\b.WorkSpace\Engel App\runtime\logs\reset_chat_worker.log"
$killed = 0
$workerPattern = [regex]::Escape((Join-Path (Split-Path $PSScriptRoot -Parent) 'tools\engel_main_local_model_worker.py'))
Get-CimInstance Win32_Process | Where-Object {
    $_.Name -in @('python.exe', 'pythonw.exe') -and $_.CommandLine -match $workerPattern
} | ForEach-Object {
    try { Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop; $killed++ } catch {}
}
"[$(Get-Date -Format s)] killed $killed worker process(es)" | Out-File $log -Encoding utf8
Start-Sleep -Seconds 1
$remain = (Get-CimInstance Win32_Process | Where-Object {
    $_.Name -in @('python.exe', 'pythonw.exe') -and $_.CommandLine -match $workerPattern
} | Measure-Object).Count
"remaining workers: $remain" | Out-File $log -Append -Encoding utf8
"killed=$killed remaining=$remain"
