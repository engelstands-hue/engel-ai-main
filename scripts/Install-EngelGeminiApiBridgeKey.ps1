param(
    [string]$EnvName = "ENGEL_GEMINI_API_KEY",
    [switch]$Verify
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$ProfilePath = Join-Path $ProjectRoot "runtime\connector_profiles\providers\gemini.json"
$ProviderBridgeEnvFile = Join-Path $ProjectRoot "run\secrets\provider_bridges.env"
$StartBridge = Join-Path $PSScriptRoot "Start-EngelGeminiApiBridge.ps1"
$HealthUrl = "http://127.0.0.1:24886/health"
$ChatUrl = "http://127.0.0.1:24886/chat"

$acceptedNames = @(
    "ENGEL_GEMINI_API_KEY",
    "GEMINI_API_KEY",
    "ENGEL_GOOGLE_API_KEY",
    "GOOGLE_API_KEY",
    "GOOGLE_GENAI_API_KEY",
    "GENAI_API_KEY",
    "GOOGLE_GENERATIVE_AI_API_KEY",
    "ENGEL_GOOGLE_GENAI_API_KEY",
    "ENGEL_GOOGLE_GENERATIVE_AI_API_KEY",
    "GOOGLE_AI_API_KEY",
    "ENGEL_GOOGLE_AI_API_KEY"
)

if ($acceptedNames -notcontains $EnvName) {
    throw "Unsupported Gemini env name '$EnvName'. Use one of: $($acceptedNames -join ', ')"
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

Write-Host "Paste the Gemini / Google AI Studio API key. Input is hidden and will not be printed."
$secureKey = Read-Host -Prompt "Gemini API key" -AsSecureString
$plainKey = ConvertFrom-SecureStringPlainText -Secure $secureKey

try {
    if ([string]::IsNullOrWhiteSpace($plainKey) -or $plainKey.Trim().Length -lt 20) {
        throw "Gemini key was empty or too short; no changes made."
    }
    $plainKey = $plainKey.Trim()

    [Environment]::SetEnvironmentVariable($EnvName, $plainKey, "User")
    Set-Item -Path "Env:$EnvName" -Value $plainKey
    $providerBridgeEnvDir = Split-Path -Parent $ProviderBridgeEnvFile
    New-Item -ItemType Directory -Force -Path $providerBridgeEnvDir | Out-Null
    $lines = New-Object "System.Collections.Generic.List[string]"
    if (Test-Path -LiteralPath $ProviderBridgeEnvFile) {
        foreach ($line in [System.IO.File]::ReadAllLines($ProviderBridgeEnvFile)) {
            if ($line -notmatch ("^" + [regex]::Escape($EnvName) + "\s*=")) {
                [void]$lines.Add($line)
            }
        }
    }
    [void]$lines.Add(("{0}={1}" -f $EnvName, $plainKey))
    $utf8NoBom = [System.Text.UTF8Encoding]::new($false)
    [System.IO.File]::WriteAllLines($ProviderBridgeEnvFile, [string[]]$lines, $utf8NoBom)

    if (-not (Test-Path -LiteralPath (Split-Path -Parent $ProfilePath))) {
        New-Item -ItemType Directory -Path (Split-Path -Parent $ProfilePath) -Force | Out-Null
    }

    $profile = [ordered]@{
        schema = "engel_connector_profile_v1"
        created_at_utc = (Get-Date).ToUniversalTime().ToString("o")
        created_by = "Engel AI Main"
        connector_kind = "provider"
        connector_id = "gemini"
        connector_name = "Gemini"
        category = "AI Providers"
        status = "key saved - bridge secret reachable"
        env_name = $EnvName
        live_verified = $false
        live_verify_state = "secret_present_not_api_verified"
        live_verify_code = 0
        live_verified_at_utc = ""
        secret_backed = $true
        diagnostic = "Gemini key is stored in the Windows user environment and run/secrets/provider_bridges.env. Secret value is not stored in this JSON profile."
    }
    $profile | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $ProfilePath -Encoding UTF8

    $listener = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object { $_.LocalPort -eq 24886 }
    foreach ($item in $listener) {
        Stop-Process -Id $item.OwningProcess -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Seconds 1

    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $StartBridge | Out-Host
    $health = Invoke-RestMethod -Uri $HealthUrl -TimeoutSec 20

    $verified = $false
    $verifyCode = 0
    if ($Verify) {
        try {
            $payload = @{
                prompt = "Reply with one short sentence: Gemini bridge verified."
                max_tokens = 64
                temperature = 0.1
                timeout_seconds = 30
            } | ConvertTo-Json -Depth 8
            $reply = Invoke-RestMethod -Uri $ChatUrl -Method Post -ContentType "application/json" -Body $payload -TimeoutSec 45
            $verified = [bool]$reply.ok
            $verifyCode = if ($verified) { 200 } else { 502 }
        } catch {
            $verified = $false
            $verifyCode = 502
        }
    }

    if ($health.secret_present -eq $true) {
        $profile.status = if ($verified) { "connected - live verified" } else { "key saved - bridge secret reachable" }
        $profile.live_verified = [bool]$verified
        $profile.live_verify_state = if ($verified) { "verified" } else { "secret_present_not_api_verified" }
        $profile.live_verify_code = $verifyCode
        $profile.live_verified_at_utc = if ($verified) { (Get-Date).ToUniversalTime().ToString("o") } else { "" }
        $profile.secret_backed = $true
        $profile | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $ProfilePath -Encoding UTF8
    }

    [pscustomobject]@{
        ok = [bool]$health.ok
        bridge_usable = [bool]$health.usable
        secret_present = [bool]$health.secret_present
        secret_source_type = [string]$health.secret_source.source_type
        secret_name = [string]$health.secret_source.name
        api_verified = [bool]$verified
        profile = $ProfilePath
        bridge_env_file = $ProviderBridgeEnvFile
    } | ConvertTo-Json -Depth 6
} finally {
    if ($plainKey) {
        $plainKey = $null
    }
}
