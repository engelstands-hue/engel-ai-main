param(
    [string]$CtHost = "192.0.2.50",
    [int]$CtPort = 24622,
    [string]$CtUser = "root",
    [string]$KeyPath = (Join-Path $env:USERPROFILE ".ssh\engel_ai_main_ct246_ed25519"),
    [string]$RuntimeRoot = "/opt/engel",
    [int]$OfficePort = 3000
)

# Installs the Engel-native virtual office (operator directive 2026-08-10: all third
# party removed and rewritten to Engel AI Main).
#
# (2026-08-11) This script used to package the third-party `engel3d_office_main` Node
# app -- rsync the tree, install Node 22, `npm ci`, `npm run build`, and write a unit
# with `ExecStart=/usr/bin/npm run start`. The CT was migrated to the Python rewrite by
# hand on 2026-08-10 but this installer was never repointed, so re-running it would have
# silently restored the third-party server and overwritten the live unit. It now deploys
# the same stdlib-only server the CT is actually running, and verifies it afterwards.
#
# The rewrite is deliberately dependency-free: one file, Python standard library only,
# bound to loopback. There is nothing to build and no package manager to install.

$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$ServerSource = Join-Path $ProjectRoot "tools\engel_virtual_office_server.py"
$VerifierSource = Join-Path $ProjectRoot "tools\verify_engel_virtual_office.py"
$ResolvedKeyPath = [System.IO.Path]::GetFullPath($KeyPath)
$Stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")

foreach ($required in @($ServerSource, $VerifierSource, $ResolvedKeyPath)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        throw "required file missing: $required"
    }
}

$SshTarget = "$CtUser@$CtHost"
$SshArgs = @("-i", $ResolvedKeyPath, "-p", "$CtPort", $SshTarget)
$ScpBase = @("-i", $ResolvedKeyPath, "-P", "$CtPort")

Write-Host "Deploying the Engel-native virtual office to $SshTarget ..."

# 1. Ship the server and its verifier.
& scp.exe @ScpBase $ServerSource "${SshTarget}:$RuntimeRoot/tools/engel_virtual_office_server.py"
if ($LASTEXITCODE -ne 0) { throw "failed to copy the virtual office server" }
& scp.exe @ScpBase $VerifierSource "${SshTarget}:$RuntimeRoot/tools/verify_engel_virtual_office.py"
if ($LASTEXITCODE -ne 0) { throw "failed to copy the virtual office verifier" }

# 2. Write the unit, keeping any previous one as a dated backup.
$unit = @"
[Unit]
Description=Engel AI Main server virtual office (Engel-native rewrite v1, stdlib only)
After=network-online.target

[Service]
Type=simple
Environment=ENGEL_VIRTUAL_OFFICE_PORT=$OfficePort
ExecStart=$RuntimeRoot/.venv/bin/python $RuntimeRoot/tools/engel_virtual_office_server.py
Restart=always
RestartSec=5
WorkingDirectory=$RuntimeRoot

[Install]
WantedBy=multi-user.target
"@

$remoteScript = @"
set -e
UNIT=/etc/systemd/system/engel-virtual-office.service
if [ -f "`$UNIT" ]; then cp "`$UNIT" "`$UNIT.bak_$Stamp"; fi
cat > "`$UNIT" <<'UNIT_EOF'
$unit
UNIT_EOF
python3 -m py_compile $RuntimeRoot/tools/engel_virtual_office_server.py
systemctl daemon-reload
systemctl enable engel-virtual-office.service >/dev/null 2>&1 || true
systemctl restart engel-virtual-office.service
sleep 3
systemctl is-active engel-virtual-office.service
"@

$remoteScript = $remoteScript.Replace("`r`n", "`n")
$remoteScript | & ssh.exe @SshArgs "bash -s"
if ($LASTEXITCODE -ne 0) { throw "remote install failed" }

# 3. Prove it: the verifier checks stdlib-only imports, loopback bind, no external
#    URLs, and live health -- the same gate that guards the rewrite in the repo.
Write-Host "Verifying ..."
& ssh.exe @SshArgs "cd $RuntimeRoot && python3 tools/verify_engel_virtual_office.py"
if ($LASTEXITCODE -ne 0) { throw "virtual office verifier failed after install" }

Write-Host "Engel-native virtual office installed and verified on port $OfficePort."
