<#
.SYNOPSIS
  Compare the live Engel chat lane against Nemotron 3.5 Lightning for one prompt.

.DESCRIPTION
  Runs tools/engel_chat_compare.py ON CT246 (where both the chat service and the
  reference model live) and streams the side-by-side result back. The receipt JSON
  stays on CT246 under /opt/engel/reports/chat_compare/.

  Why: "Chat needs a comparison point for Chat" (operator, 2026-08-14). A weak live
  reply is only visibly weak next to what another model does with the identical ask.

.EXAMPLE
  .\Run-EngelChatCompare.ps1 -Prompt "Lets make a pdf with hello world then a 3d one spinning"
#>
param(
    [Parameter(Mandatory = $true)][string]$Prompt,
    [int]$MaxTokens = 800,
    # Drops the chat_only guard so the live lane may route to the build/scaffold
    # lanes and REALLY build+run (app behavior, real side effects on CT246).
    [switch]$WithActions
)

$key = Join-Path $env:USERPROFILE ".ssh\engel_ai_main_ct246_ed25519"
if (-not (Test-Path -LiteralPath $key)) {
    Write-Error "CT246 SSH key not found at $key"
    exit 1
}

# Base64 the prompt so quoting survives PowerShell -> ssh -> bash intact.
$b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($Prompt))
$actions = ""
if ($WithActions) { $actions = "--with-actions " }
$remote = "python3 /opt/engel/tools/engel_chat_compare.py $actions--max-tokens $MaxTokens --prompt `"`$(echo $b64 | base64 -d)`""
ssh -i $key -o BatchMode=yes -o ConnectTimeout=10 -p 24622 root@192.0.2.50 $remote
exit $LASTEXITCODE
