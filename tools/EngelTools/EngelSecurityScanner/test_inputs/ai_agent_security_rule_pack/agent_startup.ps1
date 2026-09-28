Start-Job -ScriptBlock { "static sample only" }
Register-ScheduledTask -TaskName StaticSample
