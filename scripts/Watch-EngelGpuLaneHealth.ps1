<#
  Watch-EngelGpuLaneHealth.ps1  (2026-07-09)

  Wake/crash self-healer for the ELEVATED Engel tasks that a non-elevated session
  cannot give a repeating trigger to (EngelRogGpuModelServer / EngelRogGpuTunnel /
  EngelMainServerPersistentLink). Runs every few minutes from EngelGpuLaneWatchdog:
  if a service's endpoint is DOWN, it Start-ScheduledTask's the owning task (Start is
  permitted non-elevated even though modify/register is not). This is what brings the
  GPU lane back after a sleep/wake — the exact failure from 2026-07-09 04:35.

  Idempotent + quiet: a healthy endpoint is left alone (MultipleInstances=IgnoreNew on
  the tasks prevents duplicates). One log line per action under runtime\logs.
#>
[CmdletBinding()]
param([string]$Root = "D:\b.WorkSpace\Engel App")

$log = Join-Path $Root "runtime\logs\engel_gpu_lane_watchdog.log"
New-Item -ItemType Directory -Force -Path (Split-Path $log) | Out-Null

function Test-Port([int]$Port) {
    try {
        $c = New-Object Net.Sockets.TcpClient
        $iar = $c.BeginConnect("127.0.0.1", $Port, $null, $null)
        $ok = $iar.AsyncWaitHandle.WaitOne(1500)
        if ($ok -and $c.Connected) { $c.Close(); return $true }
        $c.Close(); return $false
    } catch { return $false }
}

function Test-SshForward([string]$Marker) {
    # True if an ssh process is carrying a forward whose command line contains $Marker.
    $procs = Get-CimInstance Win32_Process -Filter "Name='ssh.exe'" -ErrorAction SilentlyContinue
    foreach ($p in $procs) { if ($p.CommandLine -and $p.CommandLine -match [regex]::Escape($Marker)) { return $true } }
    return $false
}

function Ensure([string]$TaskName, [scriptblock]$Healthy, [string]$What) {
    if (& $Healthy) { return }
    try {
        Start-ScheduledTask -TaskName $TaskName -ErrorAction Stop
        $line = "[{0}] {1} down -> started {2}" -f (Get-Date -Format s), $What, $TaskName
    } catch {
        $line = "[{0}] {1} down -> FAILED to start {2}: {3}" -f (Get-Date -Format s), $What, $TaskName, $_.Exception.Message
    }
    Add-Content -LiteralPath $log -Value $line
}

# GPU model server (llama.cpp) — the sleep casualty: up == local 8899 answers.
Ensure -TaskName "EngelRogGpuModelServer"        -What "GPU model server"    -Healthy { Test-Port 8899 }
# GPU reverse tunnel: 8899 can be up LOCALLY while the reverse forward to CT246 is
# dead, so verify the ssh forward itself, not just the local port.
Ensure -TaskName "EngelRogGpuTunnel"             -What "GPU reverse tunnel"  -Healthy { Test-SshForward "8899:127.0.0.1:8899" }
# Chat + bridge link: local 24680 bound == the chat -L forward is alive.
Ensure -TaskName "EngelMainServerPersistentLink" -What "chat + bridge tunnel" -Healthy { Test-Port 24680 }
