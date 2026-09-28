<#
.SYNOPSIS
  After the five-curriculum marathon completes, resume the two legs it lost.

.DESCRIPTION
  Waits for the marathon's completion marker, then sequentially resumes:
    - Construction at prompt 51 (positions 1-50 consumed by the 2026-08-14 22:53Z
      leg that died on the chat-service cold-start after a deploy restart)
    - Chat Communication at prompt 3 (positions 1-2 consumed by the 2026-08-15
      03:53Z leg killed by the receipt-belt defect, since fixed and proven)
  StartIndexes were computed from the write-ahead reservation ledger; the novelty
  preflight refuses any replay, so a wrong index fails safe.
#>
$root = "D:\b.WorkSpace\Engel App"
$launcher = Join-Path $root "memory\training\engel_main\run_hour_prompt_training.ps1"
$marathonLog = Get-ChildItem (Join-Path $root "memory\training\engel_main\runs\ui_prompt") -Filter "marathon_*.log" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
$sentinel = Join-Path $root "runtime\one_hour_local_only_chat_training\active.json"
$log = Join-Path $root "memory\training\engel_main\runs\ui_prompt\tail_resumes_$(Get-Date -Format yyyyMMddTHHmmss).log"

"$(Get-Date -Format s) waiting for marathon completion ($($marathonLog.Name))" | Set-Content -Encoding utf8 $log
while ($true) {
    $content = Get-Content $marathonLog.FullName -Raw -ErrorAction SilentlyContinue
    $running = $false
    if (Test-Path $sentinel) {
        try { $running = ((Get-Content $sentinel -Raw | ConvertFrom-Json).status -eq "RUNNING") } catch {}
    }
    if ($content -match "MARATHON COMPLETE" -and -not $running) { break }
    Start-Sleep -Seconds 600
}
"$(Get-Date -Format s) marathon complete; starting tail resumes" | Add-Content -Encoding utf8 $log

$tails = @(
    @{ Template = "ENGEL_TEMPLATE_CONSTRUCTION.json"; StartIndex = 51 },
    @{ Template = "ENGEL_TEMPLATE_CHAT_COMMUNICATION.json"; StartIndex = 3 }
)
foreach ($tail in $tails) {
    $tpl = Join-Path $root "memory\training\engel_main\templates\$($tail.Template)"
    "$(Get-Date -Format s) RESUME $($tail.Template) at $($tail.StartIndex)" | Add-Content -Encoding utf8 $log
    & powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File $launcher `
        -Hours 8 -TrainingLevel fellow -TrainingTargets "slm,llm" -TrainingsPerHour 10 `
        -TemplateCycle 1 -StartIndex $tail.StartIndex -PerPromptTimeout 760 -Template $tpl
    $exit = $LASTEXITCODE
    $status = "unknown"
    if (Test-Path $sentinel) {
        try { $status = (Get-Content $sentinel -Raw | ConvertFrom-Json).status } catch {}
    }
    "$(Get-Date -Format s) END $($tail.Template) exit=$exit status=$status" | Add-Content -Encoding utf8 $log
    Start-Sleep -Seconds 90
}
"$(Get-Date -Format s) TAIL RESUMES COMPLETE" | Add-Content -Encoding utf8 $log
