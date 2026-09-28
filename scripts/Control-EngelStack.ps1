<#
  Control-EngelStack.ps1  (2026-07-09)

  Lifecycle controller: the Engel ROG service stack runs ONLY while EngelAIMain.exe
  (the desktop app) is running, and tears down to free resources when it's closed.
  Everything runs HIDDEN (pythonw for services, -WindowStyle Hidden for the tunnels).

  Registered as EngelStackController (runs every minute). This is the ONLY thing that
  starts/stops the stack — the service tasks themselves have no trigger. Because it
  re-checks each minute, it also gives crash recovery WHILE Engel is up.

  Idempotent + quiet: only acts on a state change (start a dead service when Engel is
  up, stop a live one when Engel is down). One log line per action.
#>
[CmdletBinding()]
param([string]$Root = "D:\b.WorkSpace\Engel App")

$log = Join-Path $Root "runtime\logs\engel_stack_controller.log"
New-Item -ItemType Directory -Force -Path (Split-Path $log) | Out-Null

# order matters on start: tunnels + model first, then the bridges/broker on top.
$services = @(
    "EngelRogGpuModelServer",
    "EngelRogGpuTunnel",
    "EngelMainServerPersistentLink",
    "EngelGeminiApiBridge",
    # EngelClaudeCliBridge removed — operator disconnected Claude from Engel
    "EngelCodexCliBridge",
    "EngelChatGptBrowserBridge",
    "EngelGrokImagineService",
    "EngelGrokHeadlessBroker"
)

$engel = Get-Process -Name "EngelAIMain" -ErrorAction SilentlyContinue

if ($engel) {
    # Engel app is UP -> ensure every service is running (start any that died).
    foreach ($s in $services) {
        $t = Get-ScheduledTask -TaskName $s -ErrorAction SilentlyContinue
        if ($t -and $t.State -ne "Running") {
            try {
                Start-ScheduledTask -TaskName $s -ErrorAction Stop
                Add-Content -LiteralPath $log -Value ("[{0}] Engel up  -> started {1}" -f (Get-Date -Format s), $s)
            } catch {
                Add-Content -LiteralPath $log -Value ("[{0}] Engel up  -> FAILED start {1}: {2}" -f (Get-Date -Format s), $s, $_.Exception.Message)
            }
        }
    }
} else {
    # Engel app is CLOSED -> stop the stack to free RAM/VRAM (reverse order).
    foreach ($s in ($services[($services.Count - 1)..0])) {
        $t = Get-ScheduledTask -TaskName $s -ErrorAction SilentlyContinue
        if ($t -and $t.State -eq "Running") {
            try {
                Stop-ScheduledTask -TaskName $s -ErrorAction Stop
                Add-Content -LiteralPath $log -Value ("[{0}] Engel down -> stopped {1}" -f (Get-Date -Format s), $s)
            } catch {
                Add-Content -LiteralPath $log -Value ("[{0}] Engel down -> FAILED stop {1}: {2}" -f (Get-Date -Format s), $s, $_.Exception.Message)
            }
        }
    }
}
