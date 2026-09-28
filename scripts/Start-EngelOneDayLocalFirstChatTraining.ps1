[CmdletBinding()]
param(
    [double]$Hours = 24,
    [double]$EpochMinutes = 60
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root 'runtime\python310\python.exe'
$runner = Join-Path $root 'tools\run_engel_one_day_local_first_chat_training.py'
$logRoot = Join-Path $root 'runtime\one_day_local_first_chat_training\launch'

New-Item -ItemType Directory -Force -Path $logRoot | Out-Null
$stdout = Join-Path $logRoot 'scheduled-supervisor.stdout.log'
$stderr = Join-Path $logRoot 'scheduled-supervisor.stderr.log'

Push-Location $root
try {
    & $python $runner --hours $Hours --epoch-minutes $EpochMinutes 1>> $stdout 2>> $stderr
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
