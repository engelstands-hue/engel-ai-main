param(
  [ValidateSet('status', 'install')]
  [string]$Mode = 'status',
  [string]$Approve = ''
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$ApprovalToken = 'APPROVE_XAI_GROK_CLI_INSTALL'
$Root = Split-Path -Parent $PSScriptRoot
$RuntimeDir = Join-Path $Root 'runtime\xai_grok_cli'
$InstallerDir = Join-Path $Root 'runtime\xai_cli_install'
$ReportDir = Join-Path $Root 'reports\xai_grok_cli'
$BinDir = Join-Path $RuntimeDir 'bin'
$EngelUserProfile = Join-Path $RuntimeDir 'user_profile'
$InstallerUrl = 'https://x.ai/cli/install.ps1'
$InstallerPath = Join-Path $InstallerDir 'install.ps1'
$LatestReceiptPath = Join-Path $RuntimeDir 'latest_receipt.json'

function Is-CDrivePath([string]$PathText) {
  try {
    $full = [System.IO.Path]::GetFullPath($PathText)
    return $full.StartsWith('C:\', [System.StringComparison]::OrdinalIgnoreCase)
  } catch {
    return $false
  }
}

function Ensure-EngelPath([string]$PathText) {
  if (Is-CDrivePath $PathText) {
    throw "Refusing to write Engel-owned xAI/Grok artifact on C: $PathText"
  }
  New-Item -ItemType Directory -Force -Path $PathText | Out-Null
}

function Get-ExeInfo([string]$PathText) {
  $exists = Test-Path -LiteralPath $PathText -PathType Leaf
  $version = ''
  if ($exists) {
    try {
      $raw = & $PathText --version 2>&1
      $version = ($raw | Out-String).Trim()
    } catch {
      $version = $_.Exception.Message
    }
  }
  [ordered]@{
    path = $PathText
    exists = $exists
    version = $version
  }
}

function Write-Receipt([hashtable]$Payload) {
  Ensure-EngelPath $ReportDir
  Ensure-EngelPath $RuntimeDir
  $stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssfffffffZ')
  $path = Join-Path $ReportDir "XAI_GROK_CLI_$($Payload.mode.ToUpperInvariant())_$stamp.json"
  $Payload.updated_at_utc = (Get-Date).ToUniversalTime().ToString('o')
  $Payload.receipt_path = $path
  $json = $Payload | ConvertTo-Json -Depth 10
  Set-Content -LiteralPath $path -Value $json -Encoding UTF8
  Set-Content -LiteralPath $LatestReceiptPath -Value $json -Encoding UTF8
  $json
}

Ensure-EngelPath $RuntimeDir
Ensure-EngelPath $InstallerDir
Ensure-EngelPath $BinDir
Ensure-EngelPath $EngelUserProfile

$downloaded = $false
if (-not (Test-Path -LiteralPath $InstallerPath -PathType Leaf)) {
  Invoke-WebRequest -Uri $InstallerUrl -OutFile $InstallerPath
  $downloaded = $true
}
$hash = (Get-FileHash -LiteralPath $InstallerPath -Algorithm SHA256).Hash

$receipt = [ordered]@{
  schema = 'engel_xai_grok_cli_install_v1'
  ok = $false
  mode = $Mode
  status = ''
  installer_url = $InstallerUrl
  requested_source_command = 'irm https://x.ai/cli/install.ps1 | iex'
  execution_method = 'local downloaded installer script with Engel-controlled environment'
  installer_path = $InstallerPath
  installer_downloaded_this_run = $downloaded
  installer_sha256 = $hash
  root = $Root
  runtime_dir = $RuntimeDir
  bin_dir = $BinDir
  engel_user_profile_for_install = $EngelUserProfile
  c_drive_artifact_write_allowed = $false
  provider = 'xAI / Grok'
  provider_key = 'xai'
  secrets_visible = $false
  grok = Get-ExeInfo (Join-Path $BinDir 'grok.exe')
  agent = Get-ExeInfo (Join-Path $BinDir 'agent.exe')
  path_added_by_installer = $false
  stdout = ''
  stderr = ''
  exit_code = $null
}

if ($Mode -eq 'status') {
  $receipt.ok = [bool]($receipt.grok.exists -and $receipt.agent.exists)
  $receipt.status = if ($receipt.ok) { 'xAI Grok CLI installed in Engel runtime' } else { 'xAI Grok CLI not installed in Engel runtime' }
  Write-Receipt $receipt
  exit ($(if ($receipt.ok) { 0 } else { 1 }))
}

if ($Approve -ne $ApprovalToken) {
  $receipt.status = "install blocked; missing approval token $ApprovalToken"
  Write-Receipt $receipt
  exit 2
}

$oldGrokBinDir = $env:GROK_BIN_DIR
$oldUserProfile = $env:USERPROFILE
try {
  $env:GROK_BIN_DIR = $BinDir
  $env:USERPROFILE = $EngelUserProfile
  $raw = & $InstallerPath 2>&1
  $receipt.exit_code = $LASTEXITCODE
  $receipt.stdout = ($raw | Out-String).Trim()
  $receipt.stderr = ''
} catch {
  $receipt.exit_code = -1
  $receipt.stderr = $_.Exception.Message
} finally {
  $env:GROK_BIN_DIR = $oldGrokBinDir
  $env:USERPROFILE = $oldUserProfile
}

$receipt.grok = Get-ExeInfo (Join-Path $BinDir 'grok.exe')
$receipt.agent = Get-ExeInfo (Join-Path $BinDir 'agent.exe')
$receipt.path_added_by_installer = (([Environment]::GetEnvironmentVariable('Path', 'User') -split ';') -contains $BinDir)
$receipt.ok = [bool]($receipt.grok.exists -and $receipt.agent.exists -and ($receipt.exit_code -eq 0 -or $null -eq $receipt.exit_code))
$receipt.status = if ($receipt.ok) { 'xAI Grok CLI installed in Engel runtime' } else { 'xAI Grok CLI install failed or incomplete' }
Write-Receipt $receipt
exit ($(if ($receipt.ok) { 0 } else { 1 }))
