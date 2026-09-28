<#
  Set-EngelGifSearchKeys.ps1  (2026-07-11)

  Securely add Tenor and/or Giphy GIF-search API keys so Engel's Discord GIF lane
  returns GOOD matches (today it only has the narrow local library + keyless
  DuckDuckGo, so uncommon asks come back off-topic).

  Security: keys are typed into masked boxes, held only in memory, and pushed to
  CT246 over the SSH tunnel (encrypted transit) straight into the root-only secret
  file /opt/engel/run/secrets/discord.env (0600). They are passed via SSH STDIN,
  never as command arguments, so they never appear on disk or in any process list.

  Get free keys instantly:
    Tenor  (best, Google):  https://developers.google.com/tenor/guides/quickstart
    Giphy  (also free):     https://developers.giphy.com/dashboard/
  You can fill only one - Tenor alone is plenty.
#>
param(
    [string]$CtHost = "192.0.2.50",
    [int]$CtPort = 24622,
    [string]$CtUser = "root",
    [string]$KeyPath = (Join-Path $env:USERPROFILE ".ssh\engel_ai_main_ct246_ed25519")
)

Add-Type -AssemblyName PresentationFramework

$xaml = @"
<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
        xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
        Title="Engel GIF Search Keys" Height="290" Width="440"
        WindowStartupLocation="CenterScreen" ResizeMode="NoResize" Background="#1e1e2e">
  <StackPanel Margin="18">
    <TextBlock Text="Engel GIF search keys" Foreground="#cdd6f4" FontSize="16" FontWeight="Bold"/>
    <TextBlock Text="Better Discord GIF matches. Fill either or both; Tenor alone is plenty." Foreground="#a6adc8" TextWrapping="Wrap" Margin="0,4,0,10"/>
    <TextBlock Text="Tenor API key" Foreground="#cdd6f4" Margin="0,4,0,2"/>
    <PasswordBox x:Name="Tenor" Height="26" Background="#313244" Foreground="#cdd6f4"/>
    <TextBlock Text="Giphy API key (optional)" Foreground="#cdd6f4" Margin="0,10,0,2"/>
    <PasswordBox x:Name="Giphy" Height="26" Background="#313244" Foreground="#cdd6f4"/>
    <TextBlock x:Name="Status" Text="" Foreground="#f9e2af" TextWrapping="Wrap" Margin="0,10,0,0"/>
    <StackPanel Orientation="Horizontal" HorizontalAlignment="Right" Margin="0,12,0,0">
      <Button x:Name="Cancel" Content="Cancel" Width="80" Height="28" Margin="0,0,8,0"/>
      <Button x:Name="Save" Content="Save to CT246" Width="120" Height="28" Background="#89b4fa"/>
    </StackPanel>
  </StackPanel>
</Window>
"@

# (20260711 fix) the first version omitted xmlns:x, so XamlReader threw on x:Name
# and the window silently never opened. Load inside try/catch so ANY future load
# failure is shown instead of vanishing.
try {
    $reader = New-Object System.Xml.XmlNodeReader ([xml]$xaml)
    $win = [Windows.Markup.XamlReader]::Load($reader)
} catch {
    [System.Windows.MessageBox]::Show("Window failed to load:`n$($_.Exception.Message)", "Engel GIF Keys", "OK", "Error") | Out-Null
    exit 1
}
$tenor = $win.FindName("Tenor"); $giphy = $win.FindName("Giphy")
$status = $win.FindName("Status"); $save = $win.FindName("Save"); $cancel = $win.FindName("Cancel")

$cancel.Add_Click({ $win.Close() })
$save.Add_Click({
    $t = $tenor.Password; $g = $giphy.Password
    if (-not $t -and -not $g) { $status.Text = "Enter at least one key."; return }
    $status.Text = "Pushing to CT246 (encrypted)..."
    $win.Dispatcher.Invoke([action]{}, "Render")
    # Build the env content; pipe via STDIN so the keys never appear in argv.
    $lines = @()
    if ($t) { $lines += "ENGEL_TENOR_API_KEY=$t" }
    if ($g) { $lines += "ENGEL_GIPHY_API_KEY=$g" }
    $payload = ($lines -join "`n") + "`n"
    # (20260711 fix) the old design piped the key to ssh STDIN from inside this WPF
    # handler - it reported success but the bytes never reached CT246. Robust path:
    # write to a temp file, scp it, merge remotely, then READ BACK + run a live GIF
    # search so "success" means search actually works - not just "a command ran".
    $tmpFile = [IO.Path]::GetTempFileName()
    $applyScript = Join-Path $PSScriptRoot "engel_apply_gif_keys.sh"
    try {
        # UTF8 no-BOM so the env file stays clean; strip CR so bash never sees \r
        [IO.File]::WriteAllText($tmpFile, ($payload -replace "`r", ""), (New-Object System.Text.UTF8Encoding($false)))
        $scpErr = & scp -i $KeyPath -P $CtPort -o BatchMode=yes -o StrictHostKeyChecking=accept-new $tmpFile "${CtUser}@${CtHost}:/tmp/engel_gifkeys.env" 2>&1
        if ($LASTEXITCODE -ne 0) { $status.Foreground = "#f38ba8"; $status.Text = "scp (key) failed: $scpErr"; return }
        # LF-normalize the apply script before shipping so a CRLF checkout can't make bash choke on \r
        $shLF = [IO.Path]::GetTempFileName()
        [IO.File]::WriteAllText($shLF, ([IO.File]::ReadAllText($applyScript) -replace "`r", ""), (New-Object System.Text.UTF8Encoding($false)))
        $scpErr2 = & scp -i $KeyPath -P $CtPort -o BatchMode=yes -o StrictHostKeyChecking=accept-new $shLF "${CtUser}@${CtHost}:/tmp/engel_apply_gif_keys.sh" 2>&1
        Remove-Item $shLF -Force -ErrorAction SilentlyContinue
        if ($LASTEXITCODE -ne 0) { $status.Foreground = "#f38ba8"; $status.Text = "scp (script) failed: $scpErr2"; return }
        # committed remote script does the merge + restart + LIVE-SEARCH verify -> RESULT:<n>:<source>
        $runCmd = 'bash /tmp/engel_apply_gif_keys.sh'
        $out = & ssh -i $KeyPath -p $CtPort -o BatchMode=yes -o StrictHostKeyChecking=accept-new "${CtUser}@${CtHost}" $runCmd
        $line = ($out | Where-Object { $_ -match '^RESULT:' } | Select-Object -First 1)
        if ($line -match '^RESULT:(\d+):(\S+)') {
            $n = [int]$Matches[1]; $srcName = $Matches[2]
            if ($n -ge 1 -and $srcName -ne 'none') {
                $status.Foreground = "#a6e3a1"
                $status.Text = "Done - $n key(s) saved, Discord bridge restarted, and a live search returned a GIF via '$srcName'. GIF search now works."
                $tenor.Password = ""; $giphy.Password = ""
            } elseif ($n -ge 1) {
                $status.Foreground = "#f9e2af"
                $status.Text = "$n key saved, but a live test search returned nothing - the key may be wrong or not active yet. Double-check it and re-save."
            } else {
                $status.Foreground = "#f38ba8"; $status.Text = "The key did not save (0 lines written). Try again."
            }
        } else {
            $status.Foreground = "#f38ba8"; $status.Text = "Unexpected result from CT246: $out"
        }
    } catch {
        $status.Foreground = "#f38ba8"; $status.Text = "Failed: $($_.Exception.Message)"
    } finally {
        # wipe the local temp key immediately (overwrite then delete)
        try {
            if (Test-Path $tmpFile) {
                [IO.File]::WriteAllText($tmpFile, ("0" * 256))
                Remove-Item $tmpFile -Force -ErrorAction SilentlyContinue
            }
        } catch {}
    }
})

$win.ShowDialog() | Out-Null
