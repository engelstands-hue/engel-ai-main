param()

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$standalone = Join-Path $root "tools\run_engel_standalone_chat_llm.py"
$uiWrapper = Join-Path $root "tools\run_engel_ui_chat_meeting_room_llm.py"
$personality = Join-Path $root "memory\personality\ENGEL_AI_MERGED_PERSONALITY.md"
$latestReceipt = Join-Path $root "memory\receipts\engel_local_chat_turn_latest.json"
$releaseProof = Join-Path $root "reports\codex_bridge\ENGEL_RELEASE_BUILD_LOCATION_CONNECTION_20260623.md"

$checks = [ordered]@{}

function Add-Check {
  param([string]$Name, [bool]$Ok, [string]$Detail)
  $script:checks[$Name] = [ordered]@{
    ok = $Ok
    detail = $Detail
  }
}

function Require-Text {
  param([string]$Text, [string]$Needle, [string]$Name)
  Add-Check $Name ($Text.Contains($Needle)) $Needle
}

if (-not (Test-Path -LiteralPath $standalone)) {
  throw "missing standalone chat runner: $standalone"
}
if (-not (Test-Path -LiteralPath $uiWrapper)) {
  throw "missing UI chat wrapper: $uiWrapper"
}

$standaloneText = Get-Content -LiteralPath $standalone -Raw
$uiText = Get-Content -LiteralPath $uiWrapper -Raw

Add-Check "personality_source_exists" (Test-Path -LiteralPath $personality) $personality
Require-Text $standaloneText "DEAD_FALLBACK_TERMS" "standalone_has_dead_fallback_terms"
Require-Text $standaloneText "no_dead_fallback_reply" "standalone_scores_dead_fallbacks"
Require-Text $standaloneText "reply_is_stale_build_status" "standalone_blocks_stale_build_status"
Require-Text $standaloneText "apply_failed_style_fallback" "standalone_applies_guard_fallback"
Require-Text $standaloneText "write_local_chat_turn_receipt" "standalone_writes_turn_receipt"
Require-Text $standaloneText "LOCAL_CHAT_TURN_LATEST_RECEIPT_PATH" "standalone_latest_receipt_path"
Require-Text $standaloneText "fallback_guard_triggered" "standalone_receipts_guard_trigger"
Require-Text $uiText "WEAK_VISIBLE_REPLY_TERMS" "ui_has_weak_reply_terms"
Require-Text $uiText "_weak_visible_reply" "ui_blocks_weak_visible_reply"
Require-Text $uiText "visible_reply_source" "ui_records_visible_reply_source"
Require-Text $uiText "standalone_guard_triggered" "ui_records_standalone_guard"
Add-Check "release_build_proof_report_exists" (Test-Path -LiteralPath $releaseProof) $releaseProof

if (Test-Path -LiteralPath $latestReceipt) {
  try {
    $receipt = Get-Content -LiteralPath $latestReceipt -Raw | ConvertFrom-Json
    Add-Check "latest_receipt_json_valid" $true $latestReceipt
    Add-Check "latest_receipt_not_on_c" (-not ($latestReceipt.ToLowerInvariant().StartsWith("c:\"))) $latestReceipt
    Add-Check "latest_receipt_identity_engel" ($receipt.identity -eq "Engel AI Main") "identity=$($receipt.identity)"
  } catch {
    Add-Check "latest_receipt_json_valid" $false $_.Exception.Message
  }
} else {
  Add-Check "latest_receipt_exists_after_chat_run" $false $latestReceipt
}

$failed = @()
foreach ($key in $checks.Keys) {
  if (-not $checks[$key].ok) {
    $failed += $key
  }
}

$result = [ordered]@{
  ok = ($failed.Count -eq 0)
  schema = "engel_local_runtime_personality_router_verifier_v1"
  checked_at_utc = (Get-Date).ToUniversalTime().ToString("o")
  root = $root
  failed = $failed
  checks = $checks
}

$result | ConvertTo-Json -Depth 6
if ($failed.Count -gt 0) {
  exit 1
}
exit 0
