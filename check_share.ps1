$shares = Get-WmiObject -Class Win32_Share
$shares | Where-Object { $_.Name -eq 'EngelWorkspace' } | Format-List