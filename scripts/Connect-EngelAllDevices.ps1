<#
.SYNOPSIS
  Connect every Engel device/surface in one pass: the ROG<->CT server link, the
  three Android phone workers, and the Windows Sub-Engel node.

.DESCRIPTION
  Each surface is attempted independently. A surface that fails is FLAGGED and
  the routine CONTINUES to the rest - one dead phone never blocks the others.
  Writes a receipt to reports\connect_all\ and always exits 0 (so it never
  blocks the restart trigger that calls it). Read the receipt for what failed.

  Idempotent and safe to run any time. Composes the existing per-surface tools
  (reconnect_engel_remote_workers.ps1, engel_connection_loop_doctor, the
  sub-engel pair tool) rather than duplicating them.
#>
param(
    [switch]$Quiet
)

$ErrorActionPreference = "Continue"   # flag-and-continue, never abort the pass
$ProjectRoot   = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$PythonExe     = Join-Path $ProjectRoot "runtime\python310\python.exe"
if (-not (Test-Path -LiteralPath $PythonExe)) { $PythonExe = "python" }
$ReconnectPs1  = Join-Path $ProjectRoot "tools\reconnect_engel_remote_workers.ps1"
$TunnelLauncher= Join-Path $ProjectRoot "scripts\Start-EngelMainServerChatTunnelPersistent.ps1"
$SubEngelPair  = Join-Path $ProjectRoot "tools\pair_latest_windows_sub_engel_node.py"
$SubEngelCheck = Join-Path $ProjectRoot "tools\check_windows_sub_engel_link.py"
$SubBridgeStart= Join-Path $ProjectRoot "scripts\Start-EngelMainSubBridge.ps1"
$PairedFile    = Join-Path $ProjectRoot "memory\phone_bridge\ENGEL_REMOTE_WORKERS_PAIRED.json"
$ChatHealthUrl = "http://127.0.0.1:24680/health"
$SubBridgeHealthUrl = "http://127.0.0.1:8788/health"
$Stamp         = [DateTime]::UtcNow.ToString("yyyyMMddTHHmmssZ")
$ReceiptDir    = Join-Path $ProjectRoot "reports\connect_all"
New-Item -ItemType Directory -Force -Path $ReceiptDir | Out-Null

$results = [System.Collections.Generic.List[object]]::new()
function Add-Result {
    param([string]$Surface, [string]$Device, [bool]$Connected, [string]$Reason)
    $results.Add([ordered]@{
        surface = $Surface; device = $Device
        connected = $Connected; flagged = (-not $Connected); reason = $Reason
    })
    if (-not $Quiet) {
        $tag = if ($Connected) { "OK  " } else { "FLAG" }
        Write-Host ("  {0} [{1}] {2}: {3}" -f $tag, $Surface, $Device, $Reason)
    }
}
function Test-Url {
    param([string]$Url, [int]$TimeoutSec = 5)
    try { $null = Invoke-WebRequest -Uri $Url -TimeoutSec $TimeoutSec -UseBasicParsing; return $true }
    catch { return $false }
}
# Run a child process with a HARD timeout so a hung tool (e.g. a network call
# with no timeout) can never freeze the whole connect-all pass. Returns a
# hashtable: timedout, exit, output.
function Invoke-Bounded {
    param([string]$FilePath, [string[]]$ArgList, [int]$TimeoutSec, [string]$OutFile)
    try {
        if (Test-Path -LiteralPath $OutFile) { Remove-Item -LiteralPath $OutFile -Force -ErrorAction SilentlyContinue }
        $errFile = "$OutFile.err"
        if (Test-Path -LiteralPath $errFile) { Remove-Item -LiteralPath $errFile -Force -ErrorAction SilentlyContinue }
        # Start-Process joins ArgList with spaces WITHOUT quoting, so any arg
        # containing a space (e.g. a path under "Engel App") must be quoted
        # here or the child sees it split into two arguments.
        $quoted = $ArgList | ForEach-Object { if ($_ -match '\s' -and $_ -notmatch '^".*"$') { '"' + $_ + '"' } else { $_ } }
        $p = Start-Process -FilePath $FilePath -ArgumentList $quoted -WindowStyle Hidden -PassThru -RedirectStandardOutput $OutFile -RedirectStandardError $errFile
        if (-not $p.WaitForExit($TimeoutSec * 1000)) {
            try { $p.Kill() } catch {}
            return @{ timedout = $true; exit = $null; output = ""; stderr = "" }
        }
        # The timed WaitForExit(ms) overload does not flush async state; the
        # parameterless call after it does, and without it ExitCode can read
        # as $null and the redirect files as empty even for a clean exit.
        $p.WaitForExit()
        $out = ""
        for ($r = 0; $r -lt 5; $r++) {
            $out = if (Test-Path -LiteralPath $OutFile) { [string](Get-Content -Raw -LiteralPath $OutFile -ErrorAction SilentlyContinue) } else { "" }
            if (-not [string]::IsNullOrWhiteSpace($out)) { break }
            Start-Sleep -Milliseconds 200
        }
        $err = if (Test-Path -LiteralPath $errFile) { [string](Get-Content -Raw -LiteralPath $errFile -ErrorAction SilentlyContinue) } else { "" }
        return @{ timedout = $false; exit = $p.ExitCode; output = $out; stderr = $err }
    } catch {
        return @{ timedout = $false; exit = -1; output = ""; stderr = "invoke error: $($_.Exception.Message)" }
    }
}

if (-not $Quiet) { Write-Host "== Engel Connect-All ($Stamp) ==" }

# ---- Surface 1: ROG <-> CT server link (phones/chat depend on it) -----------
try {
    if (Test-Url $ChatHealthUrl 5) {
        Add-Result "server_link" "rog_ct_tunnel" $true "chat health ok on 24680"
    } else {
        # link down: start the mutex-guarded self-healing persistent launcher
        if (Test-Path -LiteralPath $TunnelLauncher) {
            Start-Process -FilePath "powershell" -ArgumentList @(
                "-NoProfile","-ExecutionPolicy","Bypass","-WindowStyle","Hidden","-File",('"' + $TunnelLauncher + '"')
            ) -WindowStyle Hidden | Out-Null
            $ok = $false
            for ($i = 0; $i -lt 12; $i++) { Start-Sleep -Seconds 2; if (Test-Url $ChatHealthUrl 4) { $ok = $true; break } }
            Add-Result "server_link" "rog_ct_tunnel" $ok ($(if ($ok) { "relaunched persistent link, health ok" } else { "launcher started but health not ok after 24s" }))
        } else {
            Add-Result "server_link" "rog_ct_tunnel" $false "tunnel launcher missing: $TunnelLauncher"
        }
    }
} catch { Add-Result "server_link" "rog_ct_tunnel" $false "exception: $($_.Exception.Message)" }

# ---- Surface 1b: ROG Main node-ready receiver for the new Dell Sub ----------
try {
    $bridgeHealthy = $false
    if (Test-Url $SubBridgeHealthUrl 3) {
        try {
            $bridgeState = Invoke-RestMethod -Uri $SubBridgeHealthUrl -TimeoutSec 3
            $bridgeHealthy = (
                $bridgeState.ok -eq $true -and
                $bridgeState.mode -eq "node-ready-receiver" -and
                @($bridgeState.allowed_node_ips) -contains "198.51.100.227"
            )
        } catch {}
    }
    if (-not $bridgeHealthy -and (Test-Path -LiteralPath $SubBridgeStart)) {
        $br = Invoke-Bounded "powershell" @(
            "-NoProfile","-ExecutionPolicy","Bypass","-File",$SubBridgeStart,
            "-ControllerIp","192.0.2.40","-Port","8788","-AllowedNodeIp","198.51.100.227"
        ) 30 (Join-Path $env:TEMP "engel_connect_sub_bridge.out")
        if (-not $br.timedout) {
            $bridgeHealthy = Test-Url $SubBridgeHealthUrl 4
        }
    }
    $bridgeReason = if ($bridgeHealthy) {
        "Main node-ready receiver healthy on 0.0.0.0:8788; source restricted to 198.51.100.227"
    } else {
        "Main node-ready receiver failed to start on 8788"
    }
    Add-Result "main_sub_bridge" "DESKTOP-UE5A6GG" $bridgeHealthy $bridgeReason
} catch {
    Add-Result "main_sub_bridge" "DESKTOP-UE5A6GG" $false "exception: $($_.Exception.Message)"
}

# ---- Surface 2: Android phone workers (per-phone flag) ----------------------
try {
    if (Test-Path -LiteralPath $ReconnectPs1) {
        $rc = Invoke-Bounded "powershell" @("-NoProfile","-ExecutionPolicy","Bypass","-File",$ReconnectPs1) 75 (Join-Path $env:TEMP "engel_connect_reconnect.out")
        if ($rc.timedout) { Add-Result "phone_workers" "reconnect_receiver" $false "reconnect script timed out (>75s)" }
    }
    $paired = $null
    if (Test-Path -LiteralPath $PairedFile) {
        try { $paired = Get-Content -Raw -LiteralPath $PairedFile | ConvertFrom-Json } catch {}
    }
    $expected = @("android_worker_alpha","android_worker_beta","android_worker_gamma")
    $byId = @{}
    if ($paired -and $paired.workers) { foreach ($w in $paired.workers) { $byId[$w.worker_id] = $w } }
    foreach ($id in $expected) {
        $w = $byId[$id]
        if ($null -eq $w) { Add-Result "phone_workers" $id $false "no entry in paired-state file"; continue }
        $live = [bool]$w.live_phone_connected
        Add-Result "phone_workers" $id $live ([string]$w.connection_reason)
    }
} catch { Add-Result "phone_workers" "reconnect" $false "exception: $($_.Exception.Message)" }

# ---- Surface 3: Windows Sub-Engel node --------------------------------------
# Primary probe: does the STORED pair session still control the node? That is
# the actual work path. Fresh pairing (the fallback below) needs a
# pairing_code from a new node-ready callback, which only a node-side service
# restart produces - so requiring it every pass would flag a healthy link.
$subEngelDone = $false
try {
    if (Test-Path -LiteralPath $SubEngelCheck) {
        # 45s bound: the stored-session action takes ~21s when stdout is a
        # redirected file instead of a console - a 20s bound killed it 1s short.
        $sc = Invoke-Bounded $PythonExe @($SubEngelCheck) 45 (Join-Path $env:TEMP "engel_connect_subengel_check.out")
        if (-not $sc.timedout -and -not [string]::IsNullOrWhiteSpace([string]$sc.output)) {
            try {
                $cj = [string]$sc.output | ConvertFrom-Json
                if ($null -ne $cj -and $cj.connected -eq $true) {
                    Add-Result "sub_engel_node" "DESKTOP-UE5A6GG" $true ([string]$cj.reason)
                    $subEngelDone = $true
                }
            } catch {}
        }
    }
} catch {}
try {
    if ($subEngelDone) {
        # already verified via stored session
    } elseif (Test-Path -LiteralPath $SubEngelPair) {
        $sr = Invoke-Bounded $PythonExe @($SubEngelPair) 25 (Join-Path $env:TEMP "engel_connect_subengel.out")
        if ($sr.timedout) {
            Add-Result "sub_engel_node" "DESKTOP-UE5A6GG" $false "sub-engel pair tool timed out (>25s)"
        } else {
        $out = [string]$sr.output
        # Empty output is a FLAG, never a pass: an earlier version defaulted
        # to "paired" when parsing produced $null, which reported connected
        # without any proof the pair tool even ran. A nonzero exit with JSON
        # is legitimate (the tool exits 1 when pair_ok is false) - parse it.
        if ([string]::IsNullOrWhiteSpace($out)) {
            $errHint = ([string]$sr.stderr).Trim()
            if ($errHint.Length -gt 160) { $errHint = $errHint.Substring(0, 160) }
            Add-Result "sub_engel_node" "DESKTOP-UE5A6GG" $false "pair tool gave no output (exit $($sr.exit)) $errHint"
        } else {
        $connected = $false; $reason = "pair result unparseable / refused"
        try {
            $j = $out | ConvertFrom-Json
            if ($null -ne $j) {
                $connected = ($j.pair_ok -eq $true)
                $reason = if ($connected) { "paired (pair_ok)" }
                          elseif ($j.required_fix) { [string]$j.required_fix }
                          elseif ($j.status) { [string]$j.status }
                          else { "pair_ok false" }
            }
        } catch {
            $connected = ($out -match '"pair_ok"\s*:\s*true')
            if ($connected) { $reason = "paired (text parse)" }
        }
        Add-Result "sub_engel_node" "DESKTOP-UE5A6GG" $connected $reason
        }
        }
    } else {
        Add-Result "sub_engel_node" "DESKTOP-UE5A6GG" $false "pair tool missing: $SubEngelPair"
    }
} catch { Add-Result "sub_engel_node" "DESKTOP-UE5A6GG" $false "exception: $($_.Exception.Message)" }

# ---- Receipt (UTF-8 no BOM) + summary ---------------------------------------
$connectedCount = @($results | Where-Object { $_.connected }).Count
$flagged        = @($results | Where-Object { -not $_.connected })
$receipt = [ordered]@{
    schema = "engel_connect_all_devices_v1"
    generated_at_utc = $Stamp
    trigger = $env:ENGEL_CONNECT_ALL_TRIGGER
    engel_main_running = [bool](Get-Process EngelAIMain -ErrorAction SilentlyContinue)
    total = $results.Count
    connected = $connectedCount
    flagged_count = $flagged.Count
    all_connected = ($flagged.Count -eq 0)
    devices = $results
    flagged = @($flagged | ForEach-Object { "$($_.device): $($_.reason)" })
}
$json = $receipt | ConvertTo-Json -Depth 6
$enc = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText((Join-Path $ReceiptDir "ENGEL_CONNECT_ALL_$Stamp.json"), $json, $enc)
[System.IO.File]::WriteAllText((Join-Path $ReceiptDir "ENGEL_CONNECT_ALL_LATEST.json"), $json, $enc)

if (-not $Quiet) {
    Write-Host ("-- connected {0}/{1}; flagged {2} --" -f $connectedCount, $results.Count, $flagged.Count)
    if ($flagged.Count -gt 0) { $flagged | ForEach-Object { Write-Host ("   FLAGGED {0}: {1}" -f $_.device, $_.reason) -ForegroundColor Yellow } }
    Write-Host ("receipt: " + (Join-Path $ReceiptDir "ENGEL_CONNECT_ALL_LATEST.json"))
}
exit 0   # never block the restart trigger
