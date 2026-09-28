param(
    [string]$CtHost = "192.0.2.50",
    [int]$CtPort = 24622,
    [string]$CtUser = "root",
    [string]$KeyPath = (Join-Path $env:USERPROFILE ".ssh\engel_ai_main_ct246_ed25519"),
    [string]$RemoteRoot = "/opt/engel",
    [string]$QueueImportUrl = "http://127.0.0.1:18765/queue/import-assignment",
    [int]$MaxPerRun = 25,
    [switch]$SkipRunOnce
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$ResolvedKeyPath = [System.IO.Path]::GetFullPath($KeyPath)
if (-not (Test-Path -LiteralPath $ResolvedKeyPath -PathType Leaf)) {
    throw "CT SSH key not found: $ResolvedKeyPath"
}

$consumer = Join-Path $RepoRoot "tools\engel_ct_assignment_queue_consumer.py"
$producer = Join-Path $RepoRoot "engel_communication_queen_assignment_producer.py"
$branding = Join-Path $RepoRoot "engel_branding.py"
foreach ($path in @($consumer, $producer, $branding)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Required local file missing: $path"
    }
}

function Invoke-Ct {
    param([Parameter(Mandatory = $true)][string]$Command)
    & ssh -i $ResolvedKeyPath -p $CtPort -o BatchMode=yes -o StrictHostKeyChecking=accept-new "${CtUser}@${CtHost}" $Command
    if ($LASTEXITCODE -ne 0) {
        throw "CT command failed with exit code $LASTEXITCODE`: $Command"
    }
}

Write-Host "Preparing CT assignment queue consumer paths on ${CtUser}@${CtHost}:${CtPort}"
Invoke-Ct "mkdir -p '$RemoteRoot/tools' '$RemoteRoot/reports/ct_assignment_queue_consumer' '$RemoteRoot/remote_workers/communication_queen_assignments/approved' '$RemoteRoot/remote_workers/communication_queen_assignments/shipped_to_rog' '$RemoteRoot/remote_workers/communication_queen_assignments/invalid'"

Write-Host "Copying consumer and validation dependencies to CT246 /opt/engel"
& scp -i $ResolvedKeyPath -P $CtPort -o BatchMode=yes -o StrictHostKeyChecking=accept-new $consumer "${CtUser}@${CtHost}:/tmp/engel_ct_assignment_queue_consumer.py"
if ($LASTEXITCODE -ne 0) { throw "scp failed for consumer" }
& scp -i $ResolvedKeyPath -P $CtPort -o BatchMode=yes -o StrictHostKeyChecking=accept-new $producer "${CtUser}@${CtHost}:/tmp/engel_communication_queen_assignment_producer.py"
if ($LASTEXITCODE -ne 0) { throw "scp failed for assignment producer" }
& scp -i $ResolvedKeyPath -P $CtPort -o BatchMode=yes -o StrictHostKeyChecking=accept-new $branding "${CtUser}@${CtHost}:/tmp/engel_branding.py"
if ($LASTEXITCODE -ne 0) { throw "scp failed for engel_branding.py" }
Invoke-Ct "mv /tmp/engel_ct_assignment_queue_consumer.py '$RemoteRoot/tools/engel_ct_assignment_queue_consumer.py' && mv /tmp/engel_communication_queen_assignment_producer.py '$RemoteRoot/engel_communication_queen_assignment_producer.py' && mv /tmp/engel_branding.py '$RemoteRoot/engel_branding.py' && chmod 0755 '$RemoteRoot/tools/engel_ct_assignment_queue_consumer.py'"

$serviceName = "engel-ct-assignment-queue-consumer"
# Installs engel-ct-assignment-queue-consumer.service and
# engel-ct-assignment-queue-consumer.timer.
$remoteScript = @"
set -euo pipefail
cat >/etc/systemd/system/${serviceName}.service <<'UNIT'
[Unit]
Description=Engel CT assignment queue consumer to ROG candidate intake
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory=$RemoteRoot
Environment=ENGEL_APP_ROOT=$RemoteRoot
Environment=ENGEL_ROG_ASSIGNMENT_IMPORT_URL=$QueueImportUrl
ExecStart=/usr/bin/python3 $RemoteRoot/tools/engel_ct_assignment_queue_consumer.py --once --max $MaxPerRun
Nice=5
IOSchedulingClass=best-effort
IOSchedulingPriority=6
UNIT

cat >/etc/systemd/system/${serviceName}.timer <<'UNIT'
[Unit]
Description=Run Engel CT assignment queue consumer every minute

[Timer]
OnBootSec=30s
OnUnitActiveSec=60s
AccuracySec=10s
Persistent=true
Unit=engel-ct-assignment-queue-consumer.service

[Install]
WantedBy=timers.target
UNIT

systemctl daemon-reload
systemctl enable --now ${serviceName}.timer
"@
$remoteScript = $remoteScript -replace "`r`n", "`n"

Write-Host "Installing systemd service and timer on CT246"
$tempInstallScript = Join-Path $env:TEMP ("engel_ct_assignment_queue_consumer_install_" + [guid]::NewGuid().ToString("N") + ".sh")
[System.IO.File]::WriteAllText($tempInstallScript, $remoteScript, (New-Object System.Text.UTF8Encoding($false)))
try {
    & scp -i $ResolvedKeyPath -P $CtPort -o BatchMode=yes -o StrictHostKeyChecking=accept-new $tempInstallScript "${CtUser}@${CtHost}:/tmp/engel_ct_assignment_queue_consumer_install.sh"
    if ($LASTEXITCODE -ne 0) { throw "scp failed for remote install script" }
    Invoke-Ct "bash /tmp/engel_ct_assignment_queue_consumer_install.sh && rm -f /tmp/engel_ct_assignment_queue_consumer_install.sh"
} finally {
    Remove-Item -LiteralPath $tempInstallScript -Force -ErrorAction SilentlyContinue
}

if (-not $SkipRunOnce) {
    Write-Host "Running CT assignment queue consumer once now"
    & ssh -i $ResolvedKeyPath -p $CtPort -o BatchMode=yes -o StrictHostKeyChecking=accept-new "${CtUser}@${CtHost}" "systemctl start ${serviceName}.service || journalctl -u ${serviceName}.service -n 80 --no-pager"
    if ($LASTEXITCODE -ne 0) { throw "initial service run failed" }
}

Write-Host "CT assignment queue consumer status"
& ssh -i $ResolvedKeyPath -p $CtPort -o BatchMode=yes -o StrictHostKeyChecking=accept-new "${CtUser}@${CtHost}" "systemctl is-enabled ${serviceName}.timer; systemctl is-active ${serviceName}.timer; systemctl --no-pager --full status ${serviceName}.service | sed -n '1,40p'; find '$RemoteRoot/remote_workers/communication_queen_assignments' -maxdepth 1 -type d -printf '%f\n' | sort"
if ($LASTEXITCODE -ne 0) { throw "status check failed" }
