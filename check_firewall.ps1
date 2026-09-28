$rules = Get-NetFirewallRule -DisplayGroup 'File and Printer Sharing'
$rules | Where-Object { $_.Enabled -eq 'True' } | Select-Object DisplayName, Direction, Action, Profile