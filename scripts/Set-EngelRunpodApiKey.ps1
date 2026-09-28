<#
    Set-EngelRunpodApiKey.ps1  (2026-07-10)

    Secure input WINDOW for the RunPod API key. You paste the key into a masked
    PasswordBox; it is stored DPAPI-encrypted (Windows CurrentUser scope) as a
    ciphertext blob -- NEVER as plaintext, never in a .txt. Only your Windows
    account on THIS machine can decrypt it. The launch wrapper decrypts it
    just-in-time into the process env for one run; plaintext never hits disk.

    RUN IT IN YOUR OWN interactive session (not from an automated tool):
        Right-click this file  ->  "Run with PowerShell"
      or:
        powershell -ExecutionPolicy Bypass -File Set-EngelRunpodApiKey.ps1

    To replace/rotate the key later: just run it again.
#>
Add-Type -AssemblyName PresentationFramework

$secretsDir = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\runtime\runpod\secrets'))
$blobPath   = Join-Path $secretsDir 'runpod_api_key.dpapi'
New-Item -ItemType Directory -Force -Path $secretsDir | Out-Null

# ---- build the window ----
$win = New-Object System.Windows.Window
$win.Title = 'Engel - RunPod API Key (encrypted at rest)'
$win.Width = 500; $win.Height = 250
$win.WindowStartupLocation = 'CenterScreen'
$win.ResizeMode = 'NoResize'
$win.Topmost = $true

$stack = New-Object System.Windows.Controls.StackPanel
$stack.Margin = '18'

$lbl = New-Object System.Windows.Controls.TextBlock
$lbl.Text = "Paste your RunPod API key. It is encrypted with your Windows account (DPAPI) and stored as ciphertext only - no plaintext file, and it is never displayed."
$lbl.TextWrapping = 'Wrap'
$lbl.Margin = '0,0,0,12'
$stack.AddChild($lbl)

$pb = New-Object System.Windows.Controls.PasswordBox
$pb.FontSize = 14
$pb.Padding = '4'
$pb.Margin = '0,0,0,6'
$stack.AddChild($pb)

$hint = New-Object System.Windows.Controls.TextBlock
$hint.Text = "Stored at: $blobPath"
$hint.FontSize = 10
$hint.Foreground = 'Gray'
$hint.TextWrapping = 'Wrap'
$hint.Margin = '0,0,0,14'
$stack.AddChild($hint)

$row = New-Object System.Windows.Controls.StackPanel
$row.Orientation = 'Horizontal'
$row.HorizontalAlignment = 'Right'

$save = New-Object System.Windows.Controls.Button
$save.Content = 'Save (encrypted)'
$save.Width = 130; $save.Height = 30; $save.Margin = '0,0,8,0'; $save.IsDefault = $true

$cancel = New-Object System.Windows.Controls.Button
$cancel.Content = 'Cancel'
$cancel.Width = 80; $cancel.Height = 30; $cancel.IsCancel = $true

$row.AddChild($save); $row.AddChild($cancel)
$stack.AddChild($row)
$win.Content = $stack

$script:saved = $false
$save.Add_Click({
    $sec = $pb.SecurePassword
    if ($sec.Length -lt 8) {
        [System.Windows.MessageBox]::Show('That key looks too short. Paste the full RunPod API key.', 'Engel', 'OK', 'Warning') | Out-Null
        return
    }
    # ConvertFrom-SecureString (no -Key) = DPAPI, CurrentUser scope -> ciphertext hex string
    $enc = ConvertFrom-SecureString -SecureString $sec
    Set-Content -Path $blobPath -Value $enc -Encoding ASCII -NoNewline
    $script:saved = $true
    $win.DialogResult = $true
    $win.Close()
})

$null = $win.ShowDialog()

if ($script:saved -and (Test-Path $blobPath)) {
    # lock the ciphertext blob to just this user + SYSTEM + Admins (matches Engel secret hardening)
    icacls $blobPath /inheritance:r /grant:r "$($env:USERNAME):F" "SYSTEM:F" "Administrators:F" 2>&1 | Out-Null
    $bytes = (Get-Item $blobPath).Length
    Write-Host ""
    Write-Host "Saved. RunPod key is DPAPI-encrypted at:" -ForegroundColor Green
    Write-Host "  $blobPath  ($bytes bytes, ciphertext)"
    Write-Host "  No plaintext was written. Only $($env:USERNAME) on this machine can decrypt it."
    Write-Host ""
    Write-Host "Tell Claude 'the RunPod key is set' and it will launch the training run."
} else {
    Write-Host "Cancelled - no key saved." -ForegroundColor Yellow
}
