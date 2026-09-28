# Quick stack status snapshot -> stdout.
$tp = @(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'TunnelPersistent' })
"TunnelPersistent procs: $($tp.Count)  (4 = healthy: 2 wrappers + 2 loops)"
$tp | ForEach-Object {
    $w = if ($_.CommandLine -match 'RogGpuTunnel') { 'GPU ' } elseif ($_.CommandLine -match 'ChatTunnel') { 'CHAT' } else { '?' }
    "   $w [$($_.Name)] pid $($_.ProcessId)"
}
$win = @(Get-Process powershell,pythonw,conhost,WindowsTerminal,ssh,python -EA SilentlyContinue | Where-Object { $_.MainWindowHandle -ne 0 })
"visible windows: $($win.Count)"
foreach ($t in 'EngelGpuTunnelSvc','EngelChatLinkSvc') {
    "$t = $((Get-ScheduledTask -TaskName $t -EA SilentlyContinue).State)"
}
