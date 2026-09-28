<#
  Setup-EngelStackLifecycle.ps1  (2026-07-09)  ** RUN ELEVATED **

  One-time (re-runnable) elevated setup that converts the Engel ROG stack from
  "always-on, visible consoles" to "runs only while EngelAIMain.exe is open, fully
  hidden." It:
    1. Kills the orphan chat tunnel + any stray/duplicate stack processes (needs admin).
    2. Re-registers the stack services HIDDEN (pythonw for python, -WindowStyle Hidden
       for the two ssh tunnels) with NO trigger — the controller starts/stops them.
    3. Registers EngelStackController (AtLogon + every minute) which brings the stack up
       when the app is running and tears it down when it's closed.
    4. Removes the obsolete always-on watchdog and starts the controller.

  Grok CLI bridge (24880 / grok.exe) is deliberately NOT included — it stays off.
#>
[CmdletBinding()]
param([string]$Root = "D:\b.WorkSpace\Engel App")

$ErrorActionPreference = "Continue"

$transcript = Join-Path $Root "runtime\logs\setup_elevated.log"
New-Item -ItemType Directory -Force -Path (Split-Path $transcript) | Out-Null
try { Start-Transcript -Path $transcript -Force | Out-Null } catch {}

# --- must be elevated ---
$id = [Security.Principal.WindowsIdentity]::GetCurrent()
if (-not (New-Object Security.Principal.WindowsPrincipal($id)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "ERROR: must run elevated (admin)." ; try { Stop-Transcript | Out-Null } catch {}; exit 1
}
Write-Host "== Engel stack lifecycle setup (elevated) =="

$Py        = Join-Path $Root "runtime\python310\pythonw.exe"
$BrowserPy = Join-Path $Root "runtime\browser_ai_venv\Scripts\pythonw.exe"
$GpuPy     = Join-Path $Root "runtime\gpu_llm_venv\Scripts\pythonw.exe"
$Tools     = Join-Path $Root "tools"
$Scripts   = Join-Path $Root "scripts"
$Key       = "C:\Users\ziese\.ssh\engel_ai_main_ct246_ed25519"
$User      = "$env:USERNAME"

# ---------------------------------------------------------------- 1. clean up
Write-Host "-- clearing orphan/stray stack processes --"
# stale elevated setup windows from previous runs (they used to end in 'pause').
# Skip our own ancestry so we don't kill the window this very run lives in.
$self = $PID
$ancestors = @()
$cur = Get-CimInstance Win32_Process -Filter "ProcessId=$self" -ErrorAction SilentlyContinue
while ($cur) {
    $ancestors += [int]$cur.ProcessId
    $cur = Get-CimInstance Win32_Process -Filter "ProcessId=$($cur.ParentProcessId)" -ErrorAction SilentlyContinue
    if ($ancestors.Count -gt 12) { break }
}
Get-Process cmd -ErrorAction SilentlyContinue | Where-Object {
    $_.MainWindowTitle -match "Engel Stack Lifecycle Setup" -and $ancestors -notcontains $_.Id
} | ForEach-Object { Write-Host "  closed stale setup window (pid $($_.Id))"; Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue }
# Kill by STACK-PORT OWNERSHIP (elevated, so it gets even higher-integrity orphans
# like the ancient pid-8600 chat tunnel whose null cmdline evaded name/host matching).
# 24680 MUST be in this list — its omission is why 8600 survived every earlier run.
foreach ($p in 8899,8931,24680,24882,24884,24886,24888,24890,24892,24894,8790,8777) {
    Get-NetTCPConnection -State Listen -LocalPort $p -ErrorAction SilentlyContinue | ForEach-Object {
        taskkill /F /PID $_.OwningProcess 2>&1 | Out-Null; Write-Host "  freed port $p (pid $($_.OwningProcess))"
    }
}
# any remaining persistent ssh tunnels to CT246 (the -N sessions), by signature.
Get-CimInstance Win32_Process -Filter "Name='ssh.exe'" | Where-Object {
    $_.CommandLine -and $_.CommandLine -match "engel_ai_main_ct246" -and $_.CommandLine -match " -N"
} | ForEach-Object { taskkill /F /PID $_.ProcessId 2>&1 | Out-Null; Write-Host "  killed ssh tunnel $($_.ProcessId)" }
# orphaned tunnel-loop hosts from the old conhost approach (task went Ready -> the
# controller restarted them every minute, piling up powershell/conhost/pythonw loops).
Get-CimInstance Win32_Process | Where-Object {
    $_.CommandLine -and $_.CommandLine -match "TunnelPersistent"
} | ForEach-Object { taskkill /F /PID $_.ProcessId 2>&1 | Out-Null; Write-Host "  killed orphan tunnel host $($_.ProcessId)" }

# ---------------------------------------------------------------- 2. (re)register services
function Register-Hidden {
    param([string]$Name, [string]$Execute, [string]$Argument, [string]$Note)
    $action  = New-ScheduledTaskAction -Execute $Execute -Argument $Argument -WorkingDirectory $Root
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
        -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -MultipleInstances IgnoreNew `
        -StartWhenAvailable -ExecutionTimeLimit ([TimeSpan]::Zero) -Hidden
    $principal = New-ScheduledTaskPrincipal -UserId $User -LogonType Interactive -RunLevel Limited
    if (Get-ScheduledTask -TaskName $Name -ErrorAction SilentlyContinue) {
        Stop-ScheduledTask -TaskName $Name -ErrorAction SilentlyContinue
        Unregister-ScheduledTask -TaskName $Name -Confirm:$false -ErrorAction SilentlyContinue
    }
    # NO trigger: the controller starts/stops these on the app lifecycle.
    Register-ScheduledTask -TaskName $Name -Action $action -Settings $settings -Principal $principal -Description $Note | Out-Null
    Write-Host "  registered (hidden, controller-managed) $Name"
}

# The two ssh tunnels are powershell reconnect-loops. They must be windowless AND keep
# the task RUNNING. `powershell -WindowStyle Hidden` shows a window under Windows
# Terminal; `conhost --headless` hides it but EXITS right after spawning powershell, so
# the task flips to Ready and the controller restarts it every minute (orphan pile-up).
# So run them under pythonw via engel_run_hidden.py, which spawns the powershell with
# CREATE_NO_WINDOW and BLOCKS on it: no window, and pythonw stays alive as the task
# process (task stays Running). Job-object stop still kills the powershell + ssh tree.
$tunWrap = ('"{0}\engel_run_hidden.py" powershell.exe -NoProfile -ExecutionPolicy Bypass -File' -f $Tools)

# python services run under pythonw (no window) THROUGH engel_hidden_launch.py, which
# gives them a real stdout sink so their startup prints (uvicorn / "listening on ...")
# don't crash on pythonw's null streams. The launcher runs the target in-process, so
# it stays in the task tree and Stop-ScheduledTask still kills it.
$L = ('"{0}\engel_hidden_launch.py"' -f $Tools)
$ImgPy = Join-Path $Root "runtime\gpu_image_venv\Scripts\pythonw.exe"
# 2026-07-30 (operator-approved placement upgrade): the GPU tenant is the
# persona-ALIGNED qwen2.5-7b + vipy LoRA (canary-gated adapter B4DD1B93...,
# promoted 2026-07-05) instead of raw Mistral. n_ctx 6144: Qwen's 4-KV-head GQA
# keeps the cache small, service prompts are bounded ~2k tokens, and the Q5 base
# (5.44 GB) + LoRA + KV must fit 8 GB first try. Rollback = restore the Mistral
# line (file kept in runtime\gpu_models) and re-run this setup elevated.
Register-Hidden "EngelRogGpuModelServer" $GpuPy `
    ('{0} module llama_cpp.server --model "{1}\runtime\gpu_models\qwen2.5-7b-instruct-q5_k_m.gguf" --lora_path "{1}\runtime\gpu_models\engel_vipy_lora_qwen7b.gguf" --n_gpu_layers -1 --n_ctx 6144 --host 127.0.0.1 --port 8899' -f $L, $Root) "GPU big-lane model server (aligned qwen7b+vipy)"
Register-Hidden "EngelRogGpuImageServer" $ImgPy `
    ('{0} script "{1}\engel_rog_gpu_image_server.py"' -f $L, $Tools) "sdxl-turbo GPU image lane :8931"
Register-Hidden "EngelGpuTunnelSvc" $Py `
    ('{0} "{1}\Start-EngelRogGpuTunnelPersistent.ps1"' -f $tunWrap, $Scripts) "GPU reverse tunnel to CT246 (wait-wrapper)"
Register-Hidden "EngelChatLinkSvc" $Py `
    ('{0} "{1}\Start-EngelMainServerChatTunnelPersistent.ps1" -CtHost "192.0.2.50" -CtPort 24622 -CtUser "root" -KeyPath "{2}"' -f $tunWrap, $Scripts, $Key) "Chat + 5 bridge reverse-forwards (wait-wrapper)"
Register-Hidden "EngelGeminiApiBridge"      $Py        ('{0} script "{1}\engel_gemini_api_bridge_http_service.py" --port 24886' -f $L, $Tools) "Gemini API bridge :24886"
# EngelClaudeCliBridge removed — operator disconnected Claude from Engel (do not re-register)
if (Get-ScheduledTask -TaskName "EngelClaudeCliBridge" -ErrorAction SilentlyContinue) {
    Stop-ScheduledTask -TaskName "EngelClaudeCliBridge" -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName "EngelClaudeCliBridge" -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "  removed EngelClaudeCliBridge (Claude disconnected)"
}
Register-Hidden "EngelCodexCliBridge"       $Py        ('{0} script "{1}\engel_codex_cli_bridge_http_service.py" --port 24888' -f $L, $Tools) "Codex CLI bridge :24888"
Register-Hidden "EngelChatGptBrowserBridge" $BrowserPy ('{0} script "{1}\engel_chatgpt_browser_bridge_http_service.py" --port 24884' -f $L, $Tools) "ChatGPT browser bridge :24884"
Register-Hidden "EngelGrokImagineService"   $Py        ('{0} script "{1}\engel_grok_imagine_http_service.py"' -f $L, $Tools) "Grok Imagine service :24890"
Register-Hidden "EngelGrokHeadlessBroker"   $Py        ('{0} script "{1}\engel_grok_headless_http_service.py"' -f $L, $Tools) "Grok Headless broker :24892"
Register-Hidden "EngelSubEngelAutoReturn"   $Py        ('{0} script "{1}\engel_sub_engel_auto_return_service.py"' -f $L, $Tools) "Sub-Engel meeting-room auto-return worker (mutex :8777)"
Register-Hidden "EngelModelExpressServer"   $Py        ('{0} script "{1}\engel_model_express_server.py"' -f $L, $Tools) "ModelExpress weight-location broker :24894 (loopback only)"

# ---------------------------------------------------------------- 3. obsolete task
foreach ($old in "EngelGpuLaneWatchdog","EngelRogGpuTunnel","EngelMainServerPersistentLink") {
    if (Get-ScheduledTask -TaskName $old -ErrorAction SilentlyContinue) {
        Stop-ScheduledTask -TaskName $old -ErrorAction SilentlyContinue
        Unregister-ScheduledTask -TaskName $old -Confirm:$false -ErrorAction SilentlyContinue
        Write-Host "  removed obsolete $old"
    }
}

# EngelSubEngelAutoReturn is DELIBERATELY disabled (DESKTOP-UE5A6GG serves its own
# orders); re-registration above reverts that to Ready every run, which twice
# needed a second elevated pass to undo. Heal it here while we are already admin.
Stop-ScheduledTask -TaskName "EngelSubEngelAutoReturn" -ErrorAction SilentlyContinue
Disable-ScheduledTask -TaskName "EngelSubEngelAutoReturn" -ErrorAction SilentlyContinue | Out-Null
Write-Host "  re-disabled EngelSubEngelAutoReturn (deliberate operator state)"

# ---------------------------------------------------------------- 4. controller
# The controller runs under PYTHONW (GUI subsystem) — powershell.exe is a console
# app and Task Scheduler flashed its window every minute even with -WindowStyle
# Hidden. pythonw cannot create a console at all, so the tick is truly invisible.
$cAction = New-ScheduledTaskAction -Execute $Py `
    -Argument ('{0} script "{1}\engel_stack_controller.py"' -f $L, $Tools) -WorkingDirectory $Root
$cTrigLogon = New-ScheduledTaskTrigger -AtLogOn
$cTrigTick  = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) `
                -RepetitionInterval (New-TimeSpan -Minutes 1) -RepetitionDuration (New-TimeSpan -Days 3650)
$cSettings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -MultipleInstances IgnoreNew -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 5) -Hidden
$cPrincipal = New-ScheduledTaskPrincipal -UserId $User -LogonType Interactive -RunLevel Limited
if (Get-ScheduledTask -TaskName "EngelStackController" -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName "EngelStackController" -Confirm:$false -ErrorAction SilentlyContinue
}
Register-ScheduledTask -TaskName "EngelStackController" -Action $cAction `
    -Trigger @($cTrigLogon, $cTrigTick) -Settings $cSettings -Principal $cPrincipal `
    -Description "Runs the Engel stack only while EngelAIMain.exe is open (hidden)" | Out-Null
Write-Host "  registered EngelStackController (AtLogon + every minute)"

# ---------------------------------------------------------------- 5. go
Start-ScheduledTask -TaskName "EngelStackController"
Write-Host ""
Write-Host "Done. The stack now runs hidden, only while EngelAIMain.exe is open."
Write-Host "(Grok CLI bridge 24880 intentionally omitted.)"
try { Stop-Transcript | Out-Null } catch {}
