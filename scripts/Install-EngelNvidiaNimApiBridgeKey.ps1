param(
    [string]$EnvName = "NVIDIA_API_KEY",
    [switch]$SkipCt246
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$ProfilePath = Join-Path $ProjectRoot "runtime\connector_profiles\providers\nvidia.json"
$NvidiaEnvFile = Join-Path $ProjectRoot "run\secrets\nvidia.env"
$SshKey = Join-Path $env:USERPROFILE ".ssh\engel_ai_main_ct246_ed25519"

$acceptedNames = @(
    "NVIDIA_API_KEY",
    "ENGEL_NVIDIA_API_KEY",
    "NGC_API_KEY",
    "NIM_API_KEY"
)

if ($acceptedNames -notcontains $EnvName) {
    throw "Unsupported NVIDIA env name '$EnvName'."
}

function ConvertFrom-SecureStringPlainText {
    param([securestring]$Secure)
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Secure)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    } finally {
        if ($bstr -ne [IntPtr]::Zero) {
            [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
        }
    }
}

Write-Host "Paste the NVIDIA NIM API key. Input is hidden and will not be printed."
$secureKey = Read-Host -Prompt "NVIDIA NIM API key" -AsSecureString
$plainKey = ConvertFrom-SecureStringPlainText -Secure $secureKey

try {
    if ([string]::IsNullOrWhiteSpace($plainKey) -or $plainKey.Trim().Length -lt 20) {
        throw "NVIDIA key was empty or too short; no changes made."
    }
    $plainKey = $plainKey.Trim()

    [Environment]::SetEnvironmentVariable($EnvName, $plainKey, "User")
    Set-Item -Path "Env:$EnvName" -Value $plainKey
    $dir = Split-Path -Parent $NvidiaEnvFile
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    $utf8NoBom = [System.Text.UTF8Encoding]::new($false)
    $body = "{0}={1}`n" -f $EnvName, $plainKey
    [System.IO.File]::WriteAllText($NvidiaEnvFile, $body, $utf8NoBom)
    icacls $NvidiaEnvFile /inheritance:r /grant:r "$env:USERNAME:(R)" | Out-Null

    $profileDir = Split-Path -Parent $ProfilePath
    New-Item -ItemType Directory -Force -Path $profileDir | Out-Null
    $profile = [ordered]@{
        schema = "engel_connector_profile_v1"
        created_at_utc = (Get-Date).ToUniversalTime().ToString("o")
        created_by = "Engel AI Main"
        connector_kind = "provider"
        connector_id = "nvidia"
        connector_name = "NVIDIA NIM"
        category = "AI Providers"
        status = "key saved - secret not verified live"
        env_name = $EnvName
        live_verified = $false
        secret_backed = $true
        diagnostic = "NVIDIA NIM key is stored in the Windows user environment and run/secrets/nvidia.env. Secret value is not stored in this JSON profile."
    }
    $profile | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $ProfilePath -Encoding UTF8

    $ct246 = $false
    if (-not $SkipCt246 -and (Test-Path -LiteralPath $SshKey)) {
        & scp -i $SshKey -P 24622 -o BatchMode=yes $NvidiaEnvFile "root@192.0.2.50:/opt/engel/run/secrets/nvidia.env"
        if ($LASTEXITCODE -eq 0) {
            & ssh -i $SshKey -p 24622 -o BatchMode=yes root@192.0.2.50 "chmod 600 /opt/engel/run/secrets/nvidia.env; chown root:root /opt/engel/run/secrets/nvidia.env; systemctl daemon-reload; systemctl restart engel-main-chat.service; systemctl is-active engel-main-chat.service"
            $ct246 = $true
        }
    }

    [pscustomobject]@{
        ok = $true
        secret_present = $true
        secret_name = $EnvName
        env_file = $NvidiaEnvFile
        profile = $ProfilePath
        ct246_copied = $ct246
        api_verified = $false
    } | ConvertTo-Json -Depth 6
} finally {
    if ($plainKey) {
        $plainKey = $null
    }
}
