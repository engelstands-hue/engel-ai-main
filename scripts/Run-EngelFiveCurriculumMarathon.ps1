<#
.SYNOPSIS
  Run all five Engel prompt-training curricula back to back (5 x 8h/80 prompts).

.DESCRIPTION
  Sequentially launches the sanctioned per-curriculum training wrapper for each of
  the five canonical curricula. Each run is synchronous (the wrapper returns when
  its run finishes); the OS prompt-run claim inside the runner guarantees only one
  run exists at a time. A failed run does not stop the marathon - the remaining
  curricula still train, and the summary reports every outcome honestly.

  Preconditions per run: EngelAIMain.exe running (the runner auto-starts it),
  unlocked interactive desktop, CT246 chat healthy (the runner's grounding gate
  refuses to start otherwise).

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\Run-EngelFiveCurriculumMarathon.ps1
#>
param(
    [string]$TrainingLevel = "fellow",
    [string]$TrainingTargets = "slm,llm",
    [int]$PerPromptTimeout = 760
)

$root = "D:\b.WorkSpace\Engel App"
$launcher = Join-Path $root "memory\training\engel_main\run_hour_prompt_training.ps1"
$templates = @(
    "ENGEL_TEMPLATE_CONSTRUCTION.json",
    "ENGEL_TEMPLATE_CHAT_COMMUNICATION.json",
    "ENGEL_TEMPLATE_CAPABILITIES.json",
    "ENGEL_TEMPLATE_MATH_SCHOOL.json",
    "ENGEL_TEMPLATE_SELF_BUILD.json"
)
$log = Join-Path $root "memory\training\engel_main\runs\ui_prompt\marathon_$(Get-Date -Format yyyyMMddTHHmmss).log"
$results = @()

foreach ($template in $templates) {
    $templatePath = Join-Path $root "memory\training\engel_main\templates\$template"
    if (-not (Test-Path -LiteralPath $templatePath)) {
        "$(Get-Date -Format s) SKIP $template (template missing)" | Add-Content -LiteralPath $log
        $results += "$template = SKIPPED (missing)"
        continue
    }
    "$(Get-Date -Format s) START $template" | Add-Content -LiteralPath $log
    & powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File $launcher `
        -Hours 8 -TrainingLevel $TrainingLevel -TrainingTargets $TrainingTargets `
        -TrainingsPerHour 10 -TemplateCycle 1 -StartIndex 1 `
        -PerPromptTimeout $PerPromptTimeout -Template $templatePath
    $exit = $LASTEXITCODE
    $status = "unknown"
    $sentinel = Join-Path $root "runtime\one_hour_local_only_chat_training\active.json"
    if (Test-Path -LiteralPath $sentinel) {
        try {
            $status = (Get-Content -LiteralPath $sentinel -Raw | ConvertFrom-Json).status
        } catch {}
    }
    "$(Get-Date -Format s) END $template exit=$exit status=$status" | Add-Content -LiteralPath $log
    $results += "$template = exit $exit / $status"
    Start-Sleep -Seconds 90  # settle window between runs (claim release, receipts)
}

"$(Get-Date -Format s) MARATHON COMPLETE" | Add-Content -LiteralPath $log
$results | Add-Content -LiteralPath $log
$results
