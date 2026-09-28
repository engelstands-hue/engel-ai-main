<#
  Add-EngelGifKey.ps1  (2026-07-11)  - console, no window.

  Bulletproof alternative to the WPF window: prompts (masked) for a Tenor and/or
  Giphy GIF-search key, pushes it to CT246's root-only Discord secret over SSH, and
  VERIFIES with a live search so you KNOW it worked. No WPF, no event handlers.

  Free keys:  Giphy  https://developers.giphy.com/dashboard/
              Tenor  https://developers.google.com/tenor/guides/quickstart

  Run:  powershell -ExecutionPolicy Bypass -File "D:\b.WorkSpace\Engel App\scripts\Add-EngelGifKey.ps1"
#>
param(
    [string]$CtHost = "192.0.2.50",
    [int]$CtPort = 24622,
    [string]$CtUser = "root",
    [string]$KeyPath = (Join-Path $env:USERPROFILE ".ssh\engel_ai_main_ct246_ed25519")
)

function Read-Plain([string]$label) {
    $sec = Read-Host "$label (blank to skip)" -AsSecureString
    if (-not $sec -or $sec.Length -eq 0) { return "" }
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec)
    try { return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
}

Write-Host "`nEngel GIF search key setup" -ForegroundColor Cyan
Write-Host "Paste your key(s). Input is hidden. Tenor alone is plenty; Giphy alone is fine too.`n"
$tenor = Read-Plain "Tenor API key"
$giphy = Read-Plain "Giphy API key"
if (-not $tenor -and -not $giphy) { Write-Host "No key entered - nothing to do." -ForegroundColor Yellow; exit 0 }

$lines = @()
if ($tenor) { $lines += "ENGEL_TENOR_API_KEY=$tenor" }
if ($giphy) { $lines += "ENGEL_GIPHY_API_KEY=$giphy" }
$payload = ($lines -join "`n") + "`n"

$applyScript = Join-Path $PSScriptRoot "engel_apply_gif_keys.sh"
$tmpKey = [IO.Path]::GetTempFileName()
$tmpSh  = [IO.Path]::GetTempFileName()
try {
    [IO.File]::WriteAllText($tmpKey, ($payload -replace "`r", ""), (New-Object System.Text.UTF8Encoding($false)))
    [IO.File]::WriteAllText($tmpSh,  ([IO.File]::ReadAllText($applyScript) -replace "`r", ""), (New-Object System.Text.UTF8Encoding($false)))

    Write-Host "`nPushing to CT246 (encrypted) ..." -ForegroundColor Gray
    & scp -i $KeyPath -P $CtPort -o BatchMode=yes -o StrictHostKeyChecking=accept-new $tmpKey "${CtUser}@${CtHost}:/tmp/engel_gifkeys.env" | Out-Null
    if ($LASTEXITCODE -ne 0) { Write-Host "scp of key failed (SSH/key issue). Check $KeyPath." -ForegroundColor Red; exit 1 }
    & scp -i $KeyPath -P $CtPort -o BatchMode=yes -o StrictHostKeyChecking=accept-new $tmpSh "${CtUser}@${CtHost}:/tmp/engel_apply_gif_keys.sh" | Out-Null
    if ($LASTEXITCODE -ne 0) { Write-Host "scp of apply script failed." -ForegroundColor Red; exit 1 }

    $out = & ssh -i $KeyPath -p $CtPort -o BatchMode=yes -o StrictHostKeyChecking=accept-new "${CtUser}@${CtHost}" 'bash /tmp/engel_apply_gif_keys.sh'
    $line = ($out | Where-Object { $_ -match '^RESULT:' } | Select-Object -First 1)
    if ($line -match '^RESULT:(\d+):(\S+)') {
        $n = [int]$Matches[1]
        $srcName = $Matches[2]
        Write-Host ""
        if ($n -ge 1 -and $srcName -ne 'none') {
            Write-Host ("Done - {0} key saved, Discord bridge restarted, live search returned a GIF via '{1}'." -f $n, $srcName) -ForegroundColor Green
            Write-Host "GIF search now works. Try it in Discord." -ForegroundColor Green
        } elseif ($n -ge 1) {
            Write-Host ("{0} key saved, but a live test search returned nothing." -f $n) -ForegroundColor Yellow
            Write-Host "The key may be wrong or not active yet. On Giphy: a fresh app is a Beta key that IS valid for search - if it still returns nothing, regenerate it and re-run." -ForegroundColor Yellow
        } else {
            Write-Host "The key did not save. Try again." -ForegroundColor Red
        }
    } else {
        Write-Host ""
        Write-Host "Unexpected result from CT246:" -ForegroundColor Red
        Write-Host $out -ForegroundColor Red
    }
} finally {
    foreach ($t in @($tmpKey, $tmpSh)) {
        try { if (Test-Path $t) { [IO.File]::WriteAllText($t, ("0" * 256)); Remove-Item $t -Force -EA SilentlyContinue } } catch {}
    }
}
