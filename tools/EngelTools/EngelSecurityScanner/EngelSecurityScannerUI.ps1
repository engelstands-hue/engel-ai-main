param(
    [string]$ScanTarget = "",
    [switch]$RunOnce,
    [switch]$NoOpenReport,
    [switch]$NoTriageSummary
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ScriptRoot = if ($PSScriptRoot) { $PSScriptRoot } else { (Get-Location).Path }
$ScannerPath = Join-Path $ScriptRoot "EngelSecurityScan.ps1"
$ReportsPath = Join-Path $ScriptRoot "Reports"

function ConvertTo-CommandLineArgument {
    param([string]$Value)

    if ($Value -notmatch '[\s"]') {
        return $Value
    }

    return '"' + ($Value -replace '"', '\"') + '"'
}

function Get-LatestScannerReport {
    if (-not (Test-Path -LiteralPath $ReportsPath)) {
        return $null
    }

    return Get-ChildItem -LiteralPath $ReportsPath -Filter "EngelSecurityScan_Report_*.txt" -File -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
}

function New-ScannerArgumentList {
    param(
        [string]$Target,
        [bool]$SuppressReportOpen,
        [bool]$UseTriageSummary
    )

    $arguments = @(
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        $ScannerPath,
        "-NoPrompt"
    )

    if ($SuppressReportOpen) {
        $arguments += "-NoOpenReport"
    }

    if ($UseTriageSummary) {
        $arguments += "-TriageSummary"
    }

    if (-not [string]::IsNullOrWhiteSpace($Target)) {
        $arguments += "-ScanTarget"
        $arguments += $Target
    }

    return $arguments
}

function Get-ScannerCommandText {
    param(
        [string]$Target,
        [bool]$SuppressReportOpen,
        [bool]$UseTriageSummary
    )

    $arguments = New-ScannerArgumentList -Target $Target -SuppressReportOpen $SuppressReportOpen -UseTriageSummary $UseTriageSummary
    return "powershell.exe " + (($arguments | ForEach-Object { ConvertTo-CommandLineArgument $_ }) -join " ")
}

function Invoke-ScannerFromUi {
    param(
        [string]$Target,
        [bool]$SuppressReportOpen,
        [bool]$UseTriageSummary
    )

    if (-not (Test-Path -LiteralPath $ScannerPath)) {
        throw "Scanner script not found: $ScannerPath"
    }

    if (-not [string]::IsNullOrWhiteSpace($Target)) {
        if (-not (Test-Path -LiteralPath $Target)) {
            throw "Selected scan target does not exist: $Target"
        }
    }

    $arguments = New-ScannerArgumentList -Target $Target -SuppressReportOpen $SuppressReportOpen -UseTriageSummary $UseTriageSummary

    $process = New-Object System.Diagnostics.Process
    $process.StartInfo.FileName = "powershell.exe"
    $process.StartInfo.Arguments = ($arguments | ForEach-Object { ConvertTo-CommandLineArgument $_ }) -join " "
    $process.StartInfo.WorkingDirectory = $ScriptRoot
    $process.StartInfo.UseShellExecute = $false
    $process.StartInfo.RedirectStandardOutput = $true
    $process.StartInfo.RedirectStandardError = $true
    $process.StartInfo.CreateNoWindow = $true

    [void]$process.Start()
    $standardOutput = $process.StandardOutput.ReadToEnd()
    $standardError = $process.StandardError.ReadToEnd()
    $process.WaitForExit()

    $latestReport = Get-LatestScannerReport

    return [PSCustomObject]@{
        ExitCode = $process.ExitCode
        Command = Get-ScannerCommandText -Target $Target -SuppressReportOpen $SuppressReportOpen -UseTriageSummary $UseTriageSummary
        Output = $standardOutput
        Error = $standardError
        ReportPath = if ($latestReport) { $latestReport.FullName } else { "" }
    }
}

if ($RunOnce) {
    $result = Invoke-ScannerFromUi -Target $ScanTarget -SuppressReportOpen ([bool]$NoOpenReport) -UseTriageSummary (-not [bool]$NoTriageSummary)
    "UI launcher command: $($result.Command)"
    "Exit code: $($result.ExitCode)"
    if (-not [string]::IsNullOrWhiteSpace($result.ReportPath)) {
        "Report path: $($result.ReportPath)"
    }
    if (-not [string]::IsNullOrWhiteSpace($result.Error)) {
        "Scanner stderr:"
        $result.Error
    }
    if (-not [string]::IsNullOrWhiteSpace($result.Output)) {
        "Scanner stdout:"
        $result.Output
    }
    exit $result.ExitCode
}

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

[System.Windows.Forms.Application]::EnableVisualStyles()

$form = New-Object System.Windows.Forms.Form
$form.Text = "Engel Security Scanner"
$form.StartPosition = "CenterScreen"
$form.Size = New-Object System.Drawing.Size(720, 560)
$form.MinimumSize = New-Object System.Drawing.Size(680, 460)

$title = New-Object System.Windows.Forms.Label
$title.Text = "Engel Security Scanner"
$title.Font = New-Object System.Drawing.Font("Segoe UI", 14, [System.Drawing.FontStyle]::Bold)
$title.AutoSize = $true
$title.Location = New-Object System.Drawing.Point(16, 14)
$form.Controls.Add($title)

$status = New-Object System.Windows.Forms.Label
$status.Text = "Included checks: ZIP_SCAN_POLICY_V1, AI_AGENT_SECURITY_RULE_PACK_V1, AI triage summary, Defender custom scan when available."
$status.AutoSize = $true
$status.Location = New-Object System.Drawing.Point(18, 50)
$form.Controls.Add($status)

$targetLabel = New-Object System.Windows.Forms.Label
$targetLabel.Text = "Scan target"
$targetLabel.AutoSize = $true
$targetLabel.Location = New-Object System.Drawing.Point(18, 86)
$form.Controls.Add($targetLabel)

$targetBox = New-Object System.Windows.Forms.TextBox
$targetBox.Location = New-Object System.Drawing.Point(20, 108)
$targetBox.Size = New-Object System.Drawing.Size(560, 24)
$targetBox.Text = $ScanTarget
$form.Controls.Add($targetBox)

$browseButton = New-Object System.Windows.Forms.Button
$browseButton.Text = "Browse..."
$browseButton.Location = New-Object System.Drawing.Point(590, 106)
$browseButton.Size = New-Object System.Drawing.Size(92, 28)
$browseButton.Add_Click({
    $dialog = New-Object System.Windows.Forms.FolderBrowserDialog
    $dialog.Description = "Select a folder to scan"
    $dialog.ShowNewFolderButton = $false
    if (-not [string]::IsNullOrWhiteSpace($targetBox.Text) -and (Test-Path -LiteralPath $targetBox.Text)) {
        $dialog.SelectedPath = $targetBox.Text
    }
    if ($dialog.ShowDialog($form) -eq [System.Windows.Forms.DialogResult]::OK) {
        $targetBox.Text = $dialog.SelectedPath
    }
})
$form.Controls.Add($browseButton)

$openReportCheck = New-Object System.Windows.Forms.CheckBox
$openReportCheck.Text = "Open report after scan"
$openReportCheck.Checked = $true
$openReportCheck.AutoSize = $true
$openReportCheck.Location = New-Object System.Drawing.Point(20, 148)
$form.Controls.Add($openReportCheck)

$triageCheck = New-Object System.Windows.Forms.CheckBox
$triageCheck.Text = "Include AI triage summary; full raw findings are preserved"
$triageCheck.Checked = -not [bool]$NoTriageSummary
$triageCheck.AutoSize = $true
$triageCheck.Location = New-Object System.Drawing.Point(20, 172)
$form.Controls.Add($triageCheck)

$runButton = New-Object System.Windows.Forms.Button
$runButton.Text = "Run Scan"
$runButton.Location = New-Object System.Drawing.Point(20, 210)
$runButton.Size = New-Object System.Drawing.Size(120, 34)
$form.Controls.Add($runButton)

$latestButton = New-Object System.Windows.Forms.Button
$latestButton.Text = "Open Latest Report"
$latestButton.Location = New-Object System.Drawing.Point(150, 210)
$latestButton.Size = New-Object System.Drawing.Size(150, 34)
$latestButton.Add_Click({
    $latest = Get-LatestScannerReport
    if ($latest) {
        Start-Process notepad.exe $latest.FullName
    }
    else {
        [System.Windows.Forms.MessageBox]::Show($form, "No scanner report found.", "Engel Security Scanner", "OK", "Information") | Out-Null
    }
})
$form.Controls.Add($latestButton)

$reportLabel = New-Object System.Windows.Forms.Label
$reportLabel.Text = "Report path"
$reportLabel.AutoSize = $true
$reportLabel.Location = New-Object System.Drawing.Point(18, 270)
$form.Controls.Add($reportLabel)

$reportBox = New-Object System.Windows.Forms.TextBox
$reportBox.Location = New-Object System.Drawing.Point(20, 292)
$reportBox.Size = New-Object System.Drawing.Size(662, 24)
$reportBox.ReadOnly = $true
$form.Controls.Add($reportBox)

$logBox = New-Object System.Windows.Forms.TextBox
$logBox.Location = New-Object System.Drawing.Point(20, 332)
$logBox.Size = New-Object System.Drawing.Size(662, 150)
$logBox.Multiline = $true
$logBox.ScrollBars = "Vertical"
$logBox.ReadOnly = $true
$form.Controls.Add($logBox)

$runButton.Add_Click({
    try {
        $runButton.Enabled = $false
        $browseButton.Enabled = $false
        $logBox.Text = "Running scanner..."
        $form.Refresh()

        $suppressReportOpen = -not $openReportCheck.Checked
        $result = Invoke-ScannerFromUi -Target $targetBox.Text -SuppressReportOpen $suppressReportOpen -UseTriageSummary ([bool]$triageCheck.Checked)
        $reportBox.Text = $result.ReportPath
        $logBox.Text = "Command:`r`n$($result.Command)`r`n`r`nExit code: $($result.ExitCode)`r`n`r`n$($result.Output)$($result.Error)"

        if (($result.ExitCode -eq 0) -and $openReportCheck.Checked -and -not [string]::IsNullOrWhiteSpace($result.ReportPath)) {
            Start-Process notepad.exe $result.ReportPath
        }
    }
    catch {
        $logBox.Text = $_.Exception.Message
        [System.Windows.Forms.MessageBox]::Show($form, $_.Exception.Message, "Engel Security Scanner", "OK", "Error") | Out-Null
    }
    finally {
        $runButton.Enabled = $true
        $browseButton.Enabled = $true
    }
})

$latest = Get-LatestScannerReport
if ($latest) {
    $reportBox.Text = $latest.FullName
}

[void]$form.ShowDialog()
