# =====================================================================
# Reconnect Engel Remote Workers (Android Alpha + Beta) - desktop side
# ---------------------------------------------------------------------
# One-click recovery for phone pairing after a reboot or token drift.
# It is idempotent and safe to run any time. It:
#   1. Ensures the dedicated shared-secret file exists (5M787FII).
#   2. Re-pins the rotating pairing_session.json to the agreed code so
#      an expired/rotated token can never lock the phones out again.
#   3. Ensures the receiver is listening on 0.0.0.0:8765
#      (LAN endpoint 192.0.2.40 plus loopback for ADB reverse).
#   4. Verifies both workers have fresh phone-origin heartbeats.
#   5. Refreshes the D-only paired-state file from live receiver state.
#   6. Prints LAN/receipt diagnostics when a phone is present but not paired.
#
# Everything stays under D:\b.WorkSpace\Engel App. Nothing writes to C:.
# Target package: com.example.engel_remote_worker
# =====================================================================

$ErrorActionPreference = 'Continue'

$Root          = 'D:\b.WorkSpace\Engel App'
$env:ENGEL_APP_ROOT     = $Root
$env:ENGEL_PROJECT_ROOT = $Root
$Exe           = Join-Path $Root 'rust\engel-core-rs\target\debug\engel-ai-rs.exe'
$Hostip        = '192.0.2.40'
$BindHost      = '0.0.0.0'
$Port          = 8765
$Code          = '5M787FII'
$Approval      = 'APPROVE_REMOTE_WORKER_LINK_PROCESS_CONTROL'
$FreshSeconds  = 300
$AdbPathCandidates = @(
  (Join-Path $Root 'tools\platform-tools\adb.exe'),
  (Join-Path $Root 'runtime\platform-tools\adb.exe')
)
$AdbPath = $AdbPathCandidates | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
if (-not $AdbPath) {
  # Never fall back to C:\ Android SDK — Engel refuses C:-rooted ADB.
  $AdbPath = Join-Path $Root 'tools\platform-tools\adb.exe'
}

$PairDir       = Join-Path $Root 'remote_workers\lan_pairing'
$SessionFile   = Join-Path $PairDir 'pairing_session.json'
$DedicatedFile = Join-Path $PairDir 'dedicated_pairing_code.json'
$StateFile     = Join-Path $Root 'remote_workers\lan_link_manager\session_state.json'
$PairedFile    = Join-Path $Root 'memory\phone_bridge\ENGEL_REMOTE_WORKERS_PAIRED.json'
$LogDir        = Join-Path $Root 'reports\codex_bridge'
$PairReceiptDir = Join-Path $Root 'reports\remote_worker_lan_pairing'

New-Item -ItemType Directory -Force -Path $LogDir, $PairDir, (Split-Path $PairedFile) | Out-Null
$LogFile = Join-Path $LogDir ('reconnect_' + ([DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')) + '.log')

# Static worker metadata. Phones may DHCP onto 192.168.7.x (current WiFi) while
# the historical 192.0.2.x values remain accepted LAN targets.
$Meta = @{
  'android_worker_alpha' = @{ name='Android Worker Alpha'; model='Moto G Power 2025 (8GB)'; ip='192.0.2.78'; alt_ips=@('192.168.7.196'); serial='ANDROID_WORKER_ALPHA'; transport='lan' }
  'android_worker_beta'  = @{ name='Android Worker Beta';  model='Moto G Fast (3GB)';      ip='192.0.2.83'; alt_ips=@('192.168.7.195'); serial='ANDROID_WORKER_BETA'; transport='adb_reverse_usb' }
  'android_worker_gamma' = @{ name='Android Worker Gamma'; model='Samsung Galaxy A14 5G';  ip='198.51.100.236'; alt_ips=@('192.168.7.190'); serial='ANDROID_WORKER_GAMMA'; transport='lan' }
}
$AllWorkers = @('android_worker_alpha','android_worker_beta','android_worker_gamma')

function Log([string]$m){
  $line = ([DateTime]::UtcNow.ToString('s') + 'Z  ' + $m)
  Write-Host $line
  Add-Content -LiteralPath $LogFile -Value $line
}

function WriteJsonNoBom($path,$obj){
  $json = ($obj | ConvertTo-Json -Depth 8)
  [System.IO.File]::WriteAllText($path, $json + "`n", (New-Object System.Text.UTF8Encoding($false)))
}

function Test-Health {
  try {
    $h = Invoke-RestMethod -Uri ("http://{0}:{1}/health" -f $Hostip,$Port) -TimeoutSec 4
    return ($h.status -eq 'engel_lan_pairing_receiver_ready')
  } catch { return $false }
}

function Parse-UtcDate($value) {
  if (-not $value) { return $null }
  try {
    return ([DateTimeOffset]::Parse([string]$value)).UtcDateTime
  } catch {
    return $null
  }
}

function Test-IcmpReachable([string]$ip) {
  try {
    return [bool](Test-Connection -ComputerName $ip -Count 1 -Quiet -ErrorAction SilentlyContinue)
  } catch {
    return $false
  }
}

function Test-ArpPresent([string]$ip) {
  try {
    $pattern = [regex]::Escape($ip)
    return [bool](arp -a | Select-String -Pattern $pattern -Quiet)
  } catch {
    return $false
  }
}

function Test-AdbDeviceOnline([string]$serial) {
  if (-not $serial) { return $false }
  if (-not (Test-Path -LiteralPath $AdbPath -PathType Leaf)) { return $false }
  try {
    $escaped = [regex]::Escape($serial)
    $devices = & $AdbPath devices 2>$null
    return [bool]($devices | Select-String -Pattern ("^$escaped\s+device\b") -Quiet)
  } catch {
    return $false
  }
}

function Test-AdbReverseActive([string]$serial) {
  if (-not $serial) { return $false }
  if (-not (Test-Path -LiteralPath $AdbPath -PathType Leaf)) { return $false }
  try {
    $reverseList = & $AdbPath -s $serial reverse --list 2>$null
    return [bool]($reverseList | Select-String -Pattern 'tcp:8765\s+tcp:8765' -Quiet)
  } catch {
    return $false
  }
}

function Ensure-AdbReverse([string]$serial) {
  if (-not $serial) { return $false }
  if (-not (Test-AdbDeviceOnline $serial)) { return $false }
  try {
    & $AdbPath -s $serial reverse tcp:$Port tcp:$Port 2>$null | Out-Null
    return (Test-AdbReverseActive $serial)
  } catch {
    return $false
  }
}

function Get-LatestPairReceipt([string]$ip) {
  $empty = [ordered]@{ path = ''; last_write_utc = '' }
  if (-not (Test-Path -LiteralPath $PairReceiptDir)) { return $empty }
  try {
    $pattern = [regex]::Escape($ip)
    $latest = Get-ChildItem -LiteralPath $PairReceiptDir -Filter '*.md' -File -ErrorAction SilentlyContinue |
      Where-Object { Select-String -LiteralPath $_.FullName -Pattern $pattern -Quiet -ErrorAction SilentlyContinue } |
      Sort-Object LastWriteTimeUtc -Descending |
      Select-Object -First 1
    if (-not $latest) { return $empty }
    return [ordered]@{
      path = $latest.FullName
      last_write_utc = $latest.LastWriteTimeUtc.ToString('yyyy-MM-ddTHH:mm:ssZ')
    }
  } catch {
    return $empty
  }
}

Write-Host ''
Log '=== Engel Remote Worker reconnect starting ==='

# 1) Dedicated shared-secret file (durable; honored by the patched receiver) ----
if (-not (Test-Path -LiteralPath $DedicatedFile)) {
  $ded = [ordered]@{
    pairing_code   = $Code
    source_package = 'com.example.engel_remote_worker'
    worker_device  = 'engel_remote_worker_flutter'
    client_mode    = 'local_draft_mode'
    workers        = @('android_worker_alpha','android_worker_beta','android_worker_gamma')
    grants_control = $false
    mode           = 'status_only'
  }
  WriteJsonNoBom $DedicatedFile $ded
  Log 'created dedicated_pairing_code.json'
} else {
  Log 'dedicated_pairing_code.json present'
}

# 2) Re-pin the rotating session token to the agreed shared code ----------------
$session = [ordered]@{
  pairing_code   = $Code
  created_at_utc = ([DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ssZ'))
  expires_at_utc = '2099-01-01T00:00:00Z'
}
WriteJsonNoBom $SessionFile $session
Log 'pinned pairing_session.json to the agreed shared code (5M787FII)'

# 3) Ensure the receiver is listening -------------------------------------------
$existingState = $null
if (Test-Path -LiteralPath $StateFile) { try { $existingState = Get-Content -Raw -LiteralPath $StateFile | ConvertFrom-Json } catch {} }
$bindAlreadyOk = [bool]($existingState -and ([string]$existingState.host -eq $BindHost))
if ((Test-Health) -and $bindAlreadyOk) {
  Log ("receiver already healthy on {0}:{1}; bind={2}" -f $Hostip,$Port,$BindHost)
} else {
  $action = if (Test-Health) { 'restarting' } else { 'starting' }
  Log ("receiver bind/health requires {0} via link manager; endpoint={1}:{2}; bind={3}" -f $action,$Hostip,$Port,$BindHost)
  if (-not (Test-Path -LiteralPath $Exe)) {
    Log ("ERROR: engel-ai-rs.exe not found at $Exe")
  } else {
    $receiverArgs = @(
      'lan-link', $action.Replace('ing', ''),
      '--host', $BindHost,
      '--port', [string]$Port,
      '--allow-lan',
      '--approve', $Approval
    )
    Start-Process -FilePath $Exe -ArgumentList $receiverArgs -WindowStyle Hidden -WorkingDirectory $Root | Out-Null
    $ok = $false
    for ($i=0; $i -lt 12; $i++) { if (Test-Health) { $ok = $true; break }; Start-Sleep -Seconds 1 }
    if ($ok) { Log ("receiver {0} and healthy" -f $action) } else { Log ("WARN: receiver still not healthy after {0} attempt" -f $action) }
  }
}

foreach ($w in $AllWorkers) {
  if (Test-AdbDeviceOnline $Meta[$w].serial) {
    $reverseOk = Ensure-AdbReverse $Meta[$w].serial
    Log ("adb reverse ensure {0}: serial={1}; reverse={2}" -f $w,$Meta[$w].serial,$reverseOk)
  }
}

# 4) Verify real phone-origin heartbeats ----------------------------------------
# Do not POST /pair from this PC and call that a phone connection. A phone is
# live only when the receiver state has a fresh last_seen from the expected
# phone IP, written by the actual Android app calling /pair or /worker/status.
$state = $null
if (Test-Path -LiteralPath $StateFile) { try { $state = Get-Content -Raw -LiteralPath $StateFile | ConvertFrom-Json } catch {} }

$phoneResult = @{}
$nowUtc = [DateTime]::UtcNow
foreach ($w in $AllWorkers) {
  $workerState = $null
  if ($state -and $state.workers -and $state.workers.$w) { $workerState = $state.workers.$w }
  $identity = $null
  if ($workerState -and $workerState.identity) { $identity = $workerState.identity }
  $remoteAddress = if ($identity) { [string]$identity.remote_address } else { '' }
  $lastSeenText = if ($workerState) { [string]$workerState.last_seen_utc } else { '' }
  $lastSeenUtc = Parse-UtcDate $lastSeenText
  $ageSeconds = $null
  if ($lastSeenUtc) { $ageSeconds = [math]::Round(($nowUtc - $lastSeenUtc).TotalSeconds, 1) }
  $adbDeviceOnline = Test-AdbDeviceOnline $Meta[$w].serial
  $adbReverseActive = Test-AdbReverseActive $Meta[$w].serial
  $altIps = @($Meta[$w].alt_ips)
  $lanIpMatch = ($remoteAddress -eq $Meta[$w].ip) -or ($altIps -contains $remoteAddress)
  $transport = if ($lanIpMatch) {
    'lan'
  } elseif ($remoteAddress -eq '127.0.0.1' -and $adbDeviceOnline -and $adbReverseActive) {
    'adb_reverse_usb'
  } else {
    'unknown'
  }
  $remoteMatches = ($transport -eq 'lan' -or $transport -eq 'adb_reverse_usb')
  $fresh = ($ageSeconds -ne $null -and $ageSeconds -ge 0 -and $ageSeconds -le $FreshSeconds)
  $live = [bool]($remoteMatches -and $fresh)
  $icmpReachable = Test-IcmpReachable $Meta[$w].ip
  $arpPresent = Test-ArpPresent $Meta[$w].ip
  $latestReceipt = Get-LatestPairReceipt $Meta[$w].ip
  $reason = if ($live) {
    if ($transport -eq 'adb_reverse_usb') { 'fresh phone-origin heartbeat over adb_reverse_usb' } else { 'fresh phone-origin heartbeat over lan' }
  } elseif (-not $workerState) {
    'no worker state from phone'
  } elseif (-not $remoteMatches) {
    "last heartbeat was not from an accepted phone transport (saw '$remoteAddress')"
  } elseif (-not $fresh) {
    "last heartbeat is stale or missing ($lastSeenText)"
  } else {
    'not live'
  }
  $phoneResult[$w] = [ordered]@{
    live_phone_connected = $live
    expected_phone_ip = $Meta[$w].ip
    observed_remote_address = $remoteAddress
    transport = $transport
    adb_serial = $Meta[$w].serial
    adb_device_online = $adbDeviceOnline
    adb_reverse_active = $adbReverseActive
    last_seen = $lastSeenText
    last_seen_age_seconds = $ageSeconds
    freshness_limit_seconds = $FreshSeconds
    icmp_reachable = $icmpReachable
    arp_present = $arpPresent
    latest_pair_receipt_path = $latestReceipt.path
    latest_pair_receipt_utc = $latestReceipt.last_write_utc
    reason = $reason
  }
  Log ("live phone check {0}: live={1}; transport={2}; expected={3}; observed={4}; last_seen={5}; icmp={6}; arp={7}; adb={8}; reverse={9}; last_receipt={10}; reason={11}" -f $w,$live,$transport,$Meta[$w].ip,$remoteAddress,$lastSeenText,$icmpReachable,$arpPresent,$adbDeviceOnline,$adbReverseActive,$latestReceipt.last_write_utc,$reason)
}

# 5) Refresh the D-only paired-state file from live receiver state ---------------
$workersOut = @()
foreach ($w in $AllWorkers) {
  $live = [bool]$phoneResult[$w].live_phone_connected
  $workersOut += [ordered]@{
    worker_id      = $w
    worker_name    = $Meta[$w].name
    phone_model    = $Meta[$w].model
    phone_ip       = $Meta[$w].ip
    host           = $Hostip
    port           = $Port
    paired         = $live
    live_phone_connected = $live
    expected_phone_ip = $phoneResult[$w].expected_phone_ip
    observed_remote_address = $phoneResult[$w].observed_remote_address
    transport = $phoneResult[$w].transport
    adb_serial = $phoneResult[$w].adb_serial
    adb_device_online = $phoneResult[$w].adb_device_online
    adb_reverse_active = $phoneResult[$w].adb_reverse_active
    last_seen      = $phoneResult[$w].last_seen
    last_seen_age_seconds = $phoneResult[$w].last_seen_age_seconds
    freshness_limit_seconds = $FreshSeconds
    icmp_reachable = $phoneResult[$w].icmp_reachable
    arp_present = $phoneResult[$w].arp_present
    latest_pair_receipt_path = $phoneResult[$w].latest_pair_receipt_path
    latest_pair_receipt_utc = $phoneResult[$w].latest_pair_receipt_utc
    connection_reason = $phoneResult[$w].reason
    desktop_self_pair_check = $false
    source_package = 'com.example.engel_remote_worker'
    control_direction = 'Engel controls phone'
    phone_does_not_control_engel = $true
    mode           = 'status_only'
  }
}

$paired = [ordered]@{
  schema           = 'engel_remote_workers_paired_v1'
  generated_at_utc = ([DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ssZ'))
  source_package   = 'com.example.engel_remote_worker'
  worker_device    = 'engel_remote_worker_flutter'
  client_mode      = 'local_draft_mode'
  refreshed_by     = 'reconnect_engel_remote_workers.ps1'
  pairing_endpoint = [ordered]@{
    host = $Hostip; bind_host = $BindHost; port = $Port; transport = 'http/1.1'
    receiver_runtime = 'engel-ai-rs'
    pairing_code_source = 'dedicated_pairing_code.json + pinned pairing_session.json (shared secret 5M787FII)'
  }
  live_phone_required = $true
  freshness_limit_seconds = $FreshSeconds
  desktop_self_pair_check_removed = $true
  workers          = $workersOut
}
WriteJsonNoBom $PairedFile $paired
Log ("refreshed paired-state file: " + $PairedFile)

# 6) Summary --------------------------------------------------------------------
$listener = netstat -ano | Select-String 'LISTENING' | Select-String (':' + $Port)
$allLive = $true
foreach ($w in $AllWorkers) { if (-not $phoneResult[$w].live_phone_connected) { $allLive = $false } }

Write-Host ''
Write-Host '--------------------------------------------------------------'
if ($allLive) {
  Write-Host '  RESULT: PASS  - all Engel remote workers have fresh phone-origin heartbeats' -ForegroundColor Green
} else {
  Write-Host '  RESULT: CHECK - receiver is ready, but one or more physical phones are not live' -ForegroundColor Yellow
}
Write-Host ('  Alpha (192.0.2.78): live=' + $phoneResult['android_worker_alpha'].live_phone_connected + '; reason=' + $phoneResult['android_worker_alpha'].reason)
Write-Host ('  Beta  (192.0.2.83): live=' + $phoneResult['android_worker_beta'].live_phone_connected + '; reason=' + $phoneResult['android_worker_beta'].reason)
Write-Host ('  Gamma (198.51.100.236): live=' + $phoneResult['android_worker_gamma'].live_phone_connected + '; reason=' + $phoneResult['android_worker_gamma'].reason)
Write-Host ('  Alpha LAN: icmp=' + $phoneResult['android_worker_alpha'].icmp_reachable + '; arp=' + $phoneResult['android_worker_alpha'].arp_present + '; last_pair_receipt_utc=' + $phoneResult['android_worker_alpha'].latest_pair_receipt_utc)
Write-Host ('  Beta  LAN: icmp=' + $phoneResult['android_worker_beta'].icmp_reachable + '; arp=' + $phoneResult['android_worker_beta'].arp_present + '; last_pair_receipt_utc=' + $phoneResult['android_worker_beta'].latest_pair_receipt_utc)
Write-Host ('  Beta  USB: adb_online=' + $phoneResult['android_worker_beta'].adb_device_online + '; reverse=' + $phoneResult['android_worker_beta'].adb_reverse_active + '; transport=' + $phoneResult['android_worker_beta'].transport)
if (-not $phoneResult['android_worker_beta'].live_phone_connected) {
  Write-Host '  Beta required phone settings: host=127.0.0.1; port=8765 over adb reverse tcp:8765 tcp:8765; worker_id=android_worker_beta; worker_device=engel_remote_worker_flutter; client_mode=local_draft_mode'
}
if ($listener) { Write-Host ('  Listener: ' + $listener.ToString().Trim()) } else { Write-Host '  Listener: (none found on 8765)' }
Write-Host ('  Log:    ' + $LogFile)
Write-Host ('  State:  ' + $PairedFile)
Write-Host '--------------------------------------------------------------'
Log ('=== reconnect finished: all_live=' + $allLive + ' ===')
