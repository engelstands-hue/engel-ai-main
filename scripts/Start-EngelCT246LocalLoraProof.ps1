[CmdletBinding()]
param(
    [string]$ProxmoxHost = "192.0.2.50",
    [int]$SshPort = 24622,
    [string]$SshUser = "root",
    [string]$SshKey = "$env:USERPROFILE\.ssh\engel_ai_main_ct246_ed25519",
    [switch]$PreflightOnly,
    [string]$Approval = "",
    [int]$TrainingBudgetSeconds = 3600,
    [int]$EvalTimeoutSeconds = 7200
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$localTool = Join-Path $repoRoot "tools\run_engel_ct246_local_lora_proof.py"
$remoteTool = "/opt/engel/tools/run_engel_ct246_local_lora_proof.py"

if (-not (Test-Path -LiteralPath $localTool)) {
    throw "Missing local tool: $localTool"
}
if (-not (Test-Path -LiteralPath $SshKey)) {
    throw "Missing CT246 SSH key: $SshKey"
}

$target = "$SshUser@$ProxmoxHost"
Write-Host "Syncing CT246 LoRA proof tool to ${target}:$remoteTool"
scp -i $SshKey -P $SshPort -o StrictHostKeyChecking=no -o UserKnownHostsFile=NUL $localTool "${target}:$remoteTool"
if ($LASTEXITCODE -ne 0) {
    throw "scp failed."
}

$remoteArgs = @(
    "python3",
    $remoteTool,
    "--training-budget-seconds",
    "$TrainingBudgetSeconds",
    "--eval-timeout-seconds",
    "$EvalTimeoutSeconds"
)

if ($PreflightOnly) {
    $remoteArgs += "--preflight-only"
} else {
    $remoteArgs += @("--approval", $Approval)
}

$escaped = ($remoteArgs | ForEach-Object { "'" + ($_ -replace "'", "'\''") + "'" }) -join " "
Write-Host "Running CT246 LoRA proof command..."
ssh -i $SshKey -p $SshPort -o StrictHostKeyChecking=no -o UserKnownHostsFile=NUL $target $escaped
exit $LASTEXITCODE
