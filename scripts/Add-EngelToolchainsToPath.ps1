# Add the Engel-installed portable toolchains (Go, MinGW gcc/g++) to the USER PATH so
# they're runnable from any terminal and inherited by the app-spawned worker.
$dirs = @('D:\toolchains\go\bin', 'D:\toolchains\mingw64\bin')
$cur = [Environment]::GetEnvironmentVariable('Path', 'User')
if ($null -eq $cur) { $cur = '' }
$parts = $cur.Split(';') | Where-Object { $_ -ne '' }
$added = @()
foreach ($d in $dirs) {
    if ($parts -notcontains $d) { $parts += $d; $added += $d }
}
if ($added.Count -gt 0) {
    [Environment]::SetEnvironmentVariable('Path', ($parts -join ';'), 'User')
    "added to user PATH: $($added -join ', ')"
} else {
    "already on user PATH (no change)"
}
