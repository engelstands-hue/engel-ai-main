param(
  [ValidateSet('claude', 'codex', 'grok')]
  [string]$Provider = 'claude',
  [ValidateSet('status', 'install', 'login', 'add_account')]
  [string]$Mode = 'status',
  [string]$Approve = '',
  [string]$AccountId = 'primary'
)

# Engel AI Main — CLI account login helper.
# Installs a provider CLI into Engel's D: runtime (never C:) and launches the
# CLI's own subscription/OAuth sign-in flow in a visible terminal so the
# operator can complete it. Secret values are never read or printed here.

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$ApprovalToken = 'APPROVE_ENGEL_CLI_ACCOUNT_LOGIN'
$Root = Split-Path -Parent $PSScriptRoot
$CliRoot = Join-Path $Root 'runtime\cli_accounts'
$ReportDir = Join-Path $Root 'reports\cli_accounts'

function Test-CDrivePath([string]$PathText) {
  try {
    return ([System.IO.Path]::GetFullPath($PathText)).StartsWith('C:\', [System.StringComparison]::OrdinalIgnoreCase)
  } catch {
    return $false
  }
}

function Ensure-EngelPath([string]$PathText) {
  if (Test-CDrivePath $PathText) { throw "Refusing to write Engel CLI artifact on C: $PathText" }
  New-Item -ItemType Directory -Force -Path $PathText | Out-Null
}

switch ($Provider) {
  'claude' {
    $Name = 'Claude (Anthropic)'; $Pkg = '@anthropic-ai/claude-code'; $Bin = 'claude'
    $HomeEnv = 'CLAUDE_CONFIG_DIR'; $LoginArgs = @()
    $LoginDisplay = 'claude (Pro/Max subscription OAuth on first run)'
    $CredNames = @('.credentials.json', '.claude.json', 'credentials.json')
  }
  'codex' {
    $Name = 'ChatGPT (OpenAI Codex)'; $Pkg = '@openai/codex'; $Bin = 'codex'
    $HomeEnv = 'CODEX_HOME'; $LoginArgs = @('login')
    $LoginDisplay = 'codex login (ChatGPT account OAuth)'
    $CredNames = @('auth.json')
  }
  'grok' {
    $Name = 'xAI Grok'; $Pkg = ''; $Bin = 'grok'
    $HomeEnv = 'USERPROFILE'; $LoginArgs = @()
    $LoginDisplay = 'grok (xAI sign-in on first run)'
    $CredNames = @('.grok\auth.json', '.grok\user-settings.json', 'auth.json', 'user-settings.json')
  }
}

$ProviderDir = Join-Path $CliRoot $Provider
$AccountKey = if ([string]::IsNullOrWhiteSpace($AccountId)) { 'primary' } else { $AccountId.Trim() }
if ($Provider -eq 'grok') {
  if ($AccountKey -in @('primary', 'default', 'super')) {
    $HomeDir = $Root
  } else {
    $HomeDir = Join-Path $Root ("runtime\xai_grok_cli\accounts\" + $AccountKey)
  }
} elseif ($AccountKey -in @('primary', 'default')) {
  $HomeDir = Join-Path $ProviderDir 'home'
} else {
  $HomeDir = Join-Path $ProviderDir ("accounts\" + $AccountKey + "\home")
}

function Resolve-Bin {
  if ($Provider -eq 'grok') {
    $g = Join-Path $Root 'runtime\xai_grok_cli\bin\grok.exe'
    if (Test-Path -LiteralPath $g) { return $g }
  }
  foreach ($cand in @(
      (Join-Path $ProviderDir ($Bin + '.cmd')),
      (Join-Path $ProviderDir ($Bin + '.exe')),
      (Join-Path $ProviderDir ('bin\' + $Bin + '.cmd')),
      (Join-Path $ProviderDir ('node_modules\.bin\' + $Bin + '.cmd')))) {
    if (Test-Path -LiteralPath $cand) { return $cand }
  }
  $c = Get-Command $Bin -ErrorAction SilentlyContinue
  if ($c -and -not (Test-CDrivePath $c.Source)) { return $c.Source }
  return ''
}

function Test-LoggedIn([string]$HomePath) {
  if ([string]::IsNullOrWhiteSpace($HomePath) -or -not (Test-Path -LiteralPath $HomePath)) { return $false }
  foreach ($n in $CredNames) {
    $cp = Join-Path $HomePath $n
    if (Test-Path -LiteralPath $cp -PathType Leaf) {
      try {
        if ((Get-Item -LiteralPath $cp).Length -gt 20) { return $true }
      } catch {
        return $true
      }
    }
  }
  return $false
}

$binPath = Resolve-Bin
$installed = [bool]($binPath -ne '')
$loggedIn = Test-LoggedIn $HomeDir

$receipt = [ordered]@{
  schema = 'engel_cli_account_login_v1'
  ok = $false
  provider = $Provider
  provider_name = $Name
  mode = $Mode
  bin = $binPath
  installed = $installed
  home_dir = $HomeDir
  home_env = $HomeEnv
  account_id = $AccountKey
  logged_in = $loggedIn
  login_command = $LoginDisplay
  c_drive_artifact_write_allowed = $false
  secrets_visible = $false
  status = ''
  stdout = ''
  exit_code = $null
}

function Append-ActionLog($Payload, $ReceiptPath) {
  # Mirror the shared engel_action_log_v1 line into Engel AI Main's own memory
  # so every CLI account action shows up on the same post-handoff tape.
  try {
    $logDir = Join-Path $Root 'memory'
    if (Test-CDrivePath $logDir) { return }
    New-Item -ItemType Directory -Force -Path $logDir | Out-Null
    $log = Join-Path $logDir 'engel_action_log.jsonl'
    $line = [ordered]@{
      schema       = 'engel_action_log_v1'
      ts_utc       = (Get-Date).ToUniversalTime().ToString('o')
      category     = 'cli_account'
      action       = [string]$Payload.mode
      ok           = [bool]$Payload.ok
      status       = [string]$Payload.status
      summary      = "$($Payload.provider): $($Payload.status)"
      receipt_path = [string]$ReceiptPath
      artifacts    = @()
      pid          = $PID
    }
    $json = ($line | ConvertTo-Json -Compress -Depth 6)
    $enc = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::AppendAllText($log, ($json + "`n"), $enc)
  } catch { }
}

function Write-Receipt($Payload) {
  Ensure-EngelPath $ReportDir
  $stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssfffffffZ')
  $path = Join-Path $ReportDir ("CLI_$($Provider.ToUpper())_$($Payload.mode.ToUpper())_$stamp.json")
  $Payload.updated_at_utc = (Get-Date).ToUniversalTime().ToString('o')
  $Payload.receipt_path = $path
  $json = $Payload | ConvertTo-Json -Depth 8
  Set-Content -LiteralPath $path -Value $json -Encoding UTF8
  Append-ActionLog $Payload $path
  return $json
}

if ($Mode -eq 'status') {
  $receipt.ok = $installed
  $receipt.status = if ($installed) {
    if ($loggedIn) { "$Name CLI installed and signed in" } else { "$Name CLI installed; not signed in yet" }
  } else { "$Name CLI not installed" }
  Write-Receipt $receipt
  exit ($(if ($installed) { 0 } else { 1 }))
}

if ($Approve -ne $ApprovalToken) {
  $receipt.status = "action blocked; missing approval token $ApprovalToken"
  Write-Receipt $receipt
  exit 2
}

if ($Mode -eq 'install') {
  Ensure-EngelPath $ProviderDir
  if ($Provider -eq 'grok') {
    $grokScript = Join-Path $PSScriptRoot 'install_xai_grok_cli_for_engel.ps1'
    $raw = & powershell -NoProfile -ExecutionPolicy Bypass -File $grokScript -Mode install -Approve 'APPROVE_XAI_GROK_CLI_INSTALL' 2>&1
    $receipt.exit_code = $LASTEXITCODE
  } else {
    $npm = Join-Path $env:ProgramFiles 'nodejs\npm.cmd'
    if (-not (Test-Path -LiteralPath $npm)) { $npm = 'npm.cmd' }
    $raw = & $npm install -g --prefix "$ProviderDir" $Pkg 2>&1
    $receipt.exit_code = $LASTEXITCODE
  }
  $receipt.stdout = ($raw | Out-String).Trim()
  $receipt.bin = Resolve-Bin
  $receipt.installed = [bool]($receipt.bin -ne '')
  $receipt.ok = $receipt.installed
  $receipt.status = if ($receipt.ok) { "$Name CLI installed in Engel runtime" } else { "$Name CLI install failed or incomplete" }
  Write-Receipt $receipt
  exit ($(if ($receipt.ok) { 0 } else { 1 }))
}

if ($Mode -eq 'add_account') {
  if ($Approve -ne $ApprovalToken) {
    $receipt.status = "action blocked; missing approval token $ApprovalToken"
    Write-Receipt $receipt
    exit 2
  }
  $py = Join-Path $Root 'runtime\python310\python.exe'
  if (-not (Test-Path -LiteralPath $py)) { $py = 'python' }
  $raw = & $py (Join-Path $PSScriptRoot 'engel_provider_account_pool.py') --add $Provider 2>&1
  $receipt.stdout = ($raw | Out-String).Trim()
  $receipt.ok = $true
  $receipt.status = "$Name extra account slot created; run Login on the new account id"
  Write-Receipt $receipt
  exit 0
}

if ($Mode -eq 'login') {
  if (-not $installed) {
    $receipt.status = "$Name CLI not installed; run Install first"
    Write-Receipt $receipt
    exit 1
  }
  Ensure-EngelPath $HomeDir
  $binDirForPath = Split-Path -Parent $binPath
  $argLine = ($LoginArgs -join ' ')
  $inner = "`$env:$HomeEnv='$HomeDir'; `$env:PATH='$binDirForPath;'+`$env:PATH; Write-Host 'Engel CLI account login: $Name'; Write-Host 'Running: $LoginDisplay'; Write-Host 'A browser sign-in should open. Complete it, then return here.'; Write-Host ''; & '$binPath' $argLine; Write-Host ''; Read-Host 'When sign-in is finished, press Enter to close'"
  Start-Process powershell -ArgumentList '-NoExit', '-NoProfile', '-Command', $inner | Out-Null
  $receipt.ok = $true
  $receipt.status = "$Name sign-in window launched; complete the browser OAuth there, then re-check status"
  Write-Receipt $receipt
  exit 0
}
