# One-shot: retire the broken conhost tunnels, start the new wait-wrapper tunnels clean.
$log = "D:\b.WorkSpace\Engel App\runtime\logs\reset_tunnels.log"
"[$(Get-Date -Format s)] reset start" | Out-File $log -Encoding utf8

# stop old + new tunnel tasks
foreach ($t in 'EngelRogGpuTunnel','EngelMainServerPersistentLink','EngelGpuTunnelSvc','EngelChatLinkSvc') {
    try { Stop-ScheduledTask -TaskName $t -ErrorAction SilentlyContinue } catch {}
}
Start-Sleep -Seconds 1

# kill every tunnel loop + its ssh
$killed = 0
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'TunnelPersistent' } | ForEach-Object {
    try { Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop; $killed++ } catch {}
}
Get-CimInstance Win32_Process -Filter "Name='ssh.exe'" | Where-Object {
    $_.CommandLine -match 'engel_ai_main_ct246' -and $_.CommandLine -match ' -N'
} | ForEach-Object { try { Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop; $killed++ } catch {} }
"killed $killed tunnel/ssh procs" | Out-File $log -Append -Encoding utf8
Start-Sleep -Seconds 2

$remain = (Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'TunnelPersistent' } | Measure-Object).Count
"TunnelPersistent remaining after kill: $remain" | Out-File $log -Append -Encoding utf8

# start the two new wait-wrapper tunnels
foreach ($t in 'EngelGpuTunnelSvc','EngelChatLinkSvc') {
    try { Start-ScheduledTask -TaskName $t -ErrorAction Stop; "started $t" | Out-File $log -Append -Encoding utf8 }
    catch { "FAILED start $t : $($_.Exception.Message)" | Out-File $log -Append -Encoding utf8 }
}
"[$(Get-Date -Format s)] reset done" | Out-File $log -Append -Encoding utf8
