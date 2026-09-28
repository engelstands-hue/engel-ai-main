param(
    [string]$EnvName = "ENGEL_OPENAI_API_KEY"
)

$ErrorActionPreference = "Stop"

$clipboard = Get-Clipboard -Raw -ErrorAction SilentlyContinue
$match = [regex]::Match([string]$clipboard, "sk-[A-Za-z0-9_-]{20,}")
if (-not $match.Success) {
    Write-Host "Paste the NEW OpenAI API key for Engel, then press Enter:"
    $typed = Read-Host
    $match = [regex]::Match([string]$typed, "sk-[A-Za-z0-9_-]{20,}")
    if (-not $match.Success) {
        throw "Input does not contain an OpenAI-shaped API key."
    }
}

$key = $match.Value.Trim()
[Environment]::SetEnvironmentVariable($EnvName, $key, "User")
[Environment]::SetEnvironmentVariable($EnvName, $key, "Process")

[pscustomobject]@{
    ok = $true
    env_name = $EnvName
    scope = "User and current installer process"
    key_present = $true
    key_length = $key.Length
    key_value_visible = $false
    note = "Engel reads this from Windows user environment; the key was not printed."
} | ConvertTo-Json -Depth 3

Write-Host ""
Write-Host "Installed. Tell Codex: done" -ForegroundColor Green
