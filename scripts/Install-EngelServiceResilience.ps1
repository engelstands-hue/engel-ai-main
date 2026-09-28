<#
  Install-EngelServiceResilience.ps1  (2026-07-09)

  Makes every always-on Engel ROG service SELF-HEAL across sleep / wake / shutdown /
  crash. The GPU lane died on 2026-07-09 04:35 (sleep) and never came back because its
  tasks had only a LogOn trigger and nothing fires on wake.

  Two layers, both registrable by a NON-ELEVATED user (the existing GPU/link tasks were
  created elevated and cannot be modified without elevation, but Start-ScheduledTask on
  them IS allowed):

    1. New Limited resilient tasks for the services that had NO task at all — the 4
       provider bridges (grok/24880 EXCLUDED — it drives grok.exe, stays off), the Grok
       Imagine service, and the Grok Headless broker. Each gets:
         triggers : AtLogOn + AtStartup + a 3-min repeating tick (indefinite)
         settings : battery-safe, RestartCount 999 / 1-min, ExecutionTimeLimit 0,
                    MultipleInstances=IgnoreNew, StartWhenAvailable
       Long-running services run python DIRECTLY (the wrapper .ps1 Start-Process+exit
       and orphan the child, which a task can't monitor/restart).

    2. A Limited WATCHDOG task (EngelGpuLaneWatchdog) that runs Watch-EngelGpuLaneHealth
       on the same schedule and Start-ScheduledTask's the ELEVATED GPU / tunnel / chat-
       link tasks whenever their endpoint is down — the wake-recovery those tasks lack.

  Idempotent + re-runnable. Run elevated only if you also want the GPU/link tasks
  themselves given repeat triggers; not required for the self-heal to work.
#>
[CmdletBinding()]
param(
    [string]$Root = "D:\b.WorkSpace\Engel App",
    [switch]$StartNow
)

$ErrorActionPreference = "Stop"
$Py        = Join-Path $Root "runtime\python310\python.exe"
$BrowserPy = Join-Path $Root "runtime\browser_ai_venv\Scripts\python.exe"
$Tools     = Join-Path $Root "tools"
$Scripts   = Join-Path $Root "scripts"
$User      = "$env:USERNAME"

function Register-EngelResilientTask {
    param(
        [Parameter(Mandatory)] [string]$Name,
        [Parameter(Mandatory)] [string]$Execute,
        [string]$Argument = "",
        [string]$Note     = ""
    )
    # NOTE: -AtStartup (boot) AND -AtLogOn triggers both require elevation to register.
    # A repeating -Once trigger does NOT, and with StartWhenAvailable it covers every
    # case anyway: boot/logon (a missed run fires when available), wake, and crash
    # (the 3-min tick relaunches a dead service; a live one is left alone via IgnoreNew).
    $action  = New-ScheduledTaskAction -Execute $Execute -Argument $Argument -WorkingDirectory $Root
    $tRepeat = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) `
                 -RepetitionInterval (New-TimeSpan -Minutes 3) `
                 -RepetitionDuration (New-TimeSpan -Days 3650)
    $settings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
        -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) `
        -MultipleInstances IgnoreNew -StartWhenAvailable `
        -ExecutionTimeLimit ([TimeSpan]::Zero)
    $principal = New-ScheduledTaskPrincipal -UserId $User -LogonType Interactive -RunLevel Limited

    if (Get-ScheduledTask -TaskName $Name -ErrorAction SilentlyContinue) {
        try { Unregister-ScheduledTask -TaskName $Name -Confirm:$false } catch {}
    }
    try {
        Register-ScheduledTask -TaskName $Name -Action $action `
            -Trigger $tRepeat -Settings $settings `
            -Principal $principal -Description $Note | Out-Null
        Write-Host ("  registered {0,-28} {1}" -f $Name, $Note)
    } catch {
        Write-Host ("  FAILED    {0,-28} {1}" -f $Name, $_.Exception.Message)
    }
}

Write-Host "== Engel service resilience install (non-elevated) =="

# --- provider bridges (python DIRECTLY; grok/24880 deliberately EXCLUDED) -----
Register-EngelResilientTask -Name "EngelGeminiApiBridge" -Execute $Py `
    -Argument ('"{0}\engel_gemini_api_bridge_http_service.py" --port 24886' -f $Tools) `
    -Note "Gemini API bridge :24886"
# EngelClaudeCliBridge removed — operator disconnected Claude from Engel (do not re-register)
if (Get-ScheduledTask -TaskName "EngelClaudeCliBridge" -ErrorAction SilentlyContinue) {
    Stop-ScheduledTask -TaskName "EngelClaudeCliBridge" -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName "EngelClaudeCliBridge" -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "  removed EngelClaudeCliBridge (Claude disconnected)"
}
Register-EngelResilientTask -Name "EngelCodexCliBridge" -Execute $Py `
    -Argument ('"{0}\engel_codex_cli_bridge_http_service.py" --port 24888' -f $Tools) `
    -Note "Codex CLI bridge :24888 (usable when codex CLI is authed)"
Register-EngelResilientTask -Name "EngelChatGptBrowserBridge" -Execute $BrowserPy `
    -Argument ('"{0}\engel_chatgpt_browser_bridge_http_service.py" --port 24884' -f $Tools) `
    -Note "ChatGPT browser bridge :24884 (needs a logged-in browser)"

# --- Grok creative lane (headless, NOT the CLI) ------------------------------
Register-EngelResilientTask -Name "EngelGrokImagineService" -Execute $Py `
    -Argument ('"{0}\engel_grok_imagine_http_service.py"' -f $Tools) `
    -Note "Grok Imagine headless image service :24890"
Register-EngelResilientTask -Name "EngelGrokHeadlessBroker" -Execute $Py `
    -Argument ('"{0}\engel_grok_headless_http_service.py"' -f $Tools) `
    -Note "Grok Headless Worker broker :24892"

# --- watchdog for the ELEVATED GPU / tunnel / chat-link tasks -----------------
Register-EngelResilientTask -Name "EngelGpuLaneWatchdog" -Execute "powershell.exe" `
    -Argument ('-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "{0}\Watch-EngelGpuLaneHealth.ps1"' -f $Scripts) `
    -Note "Restarts GPU/tunnel/link tasks after sleep/wake (they can't self-repeat)"

Write-Host ""
Write-Host "Registered 7 resilient tasks (grok CLI bridge 24880 intentionally omitted)."

if ($StartNow) {
    Write-Host "Starting new tasks now..."
    foreach ($n in "EngelGeminiApiBridge","EngelCodexCliBridge",
                    "EngelChatGptBrowserBridge","EngelGrokImagineService",
                    "EngelGrokHeadlessBroker","EngelGpuLaneWatchdog") {
        try { Start-ScheduledTask -TaskName $n; Write-Host "  started $n" }
        catch { Write-Host "  FAILED to start $n : $($_.Exception.Message)" }
    }
}
Write-Host "== done =="
