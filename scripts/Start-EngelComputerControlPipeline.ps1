param(
    [string]$Goal = "Observe the current screen and report structured UI state.",
    [int]$Cycles = 1,
    [double]$Delay = 1.0,
    [switch]$Json,
    [switch]$NoLlm,
    [switch]$AllowActions,
    [switch]$FullAccess,
    [string]$ApprovalToken = "",
    [string]$LlmUrl = "",
    [switch]$SelfTest
)

$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$RuntimePython = Join-Path $ProjectRoot "runtime\python310\python.exe"
$PythonExe = if (Test-Path -LiteralPath $RuntimePython -PathType Leaf) { $RuntimePython } else { "python" }
$Pipeline = Join-Path $ProjectRoot "tools\engel_computer_control_pipeline.py"

$argsList = @(
    $Pipeline,
    "--goal", $Goal,
    "--cycles", [string]$Cycles,
    "--delay", [string]$Delay
)

if ($Json) { $argsList += "--json" }
if ($NoLlm) { $argsList += "--no-llm" }
if ($SelfTest) { $argsList += "--self-test" }
if ($AllowActions) { $argsList += "--allow-actions" }
if ($FullAccess) { $argsList += "--full-access" }
if ($ApprovalToken) { $argsList += @("--approval-token", $ApprovalToken) }
if ($LlmUrl) { $argsList += @("--llm-url", $LlmUrl) }

& $PythonExe @argsList
exit $LASTEXITCODE
