# ============================================================
# Engel Startup Review + Memory Optimizer (Delayed Memory Scan)
# Keeps Explorer and SoftLanding intact
# Disables only GoogleDriveFS, OneDrive, Autodesk Services
# Tracks memory over first 60 seconds after login
# ============================================================

Set-StrictMode -Version Latest
$ErrorActionPreference = "Continue"

# --- Folders & reports ---
$TimeStamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$ToolFolder = "D:\EngelTools\EngelStartupReview"
$ReportsFolder = Join-Path $ToolFolder "Reports"
$BackupsFolder = Join-Path $ToolFolder "Backups"
$Report = Join-Path $ReportsFolder "EngelStartupReview_Report_$TimeStamp.txt"
$BackupJson = Join-Path $BackupsFolder "EngelStartupReview_Backup_$TimeStamp.json"

New-Item -ItemType Directory -Path $ReportsFolder -Force | Out-Null
New-Item -ItemType Directory -Path $BackupsFolder -Force | Out-Null

# --- Essential processes to keep ---
$EssentialProcesses = @("explorer", "dwm", "ChatGPT")  

# --- Startup entries to disable ---
$DisableEntries = @(
    "GoogleDriveFS",
    "OneDriveSetup",
    "Autodesk Access Service",
    "Autodesk Genuine Service"
)

# --- Helper functions ---
function Test-IsAdmin {
    try {
        $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
        $principal = New-Object Security.Principal.WindowsPrincipal($identity)
        return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    } catch { return $false }
}

function Add-Report { param([string]$Text) Add-Content -Path $Report -Value $Text }

function Write-Section { param([string]$Title)
    $line = "=" * 76
    Write-Host "`n$line" -ForegroundColor DarkCyan
    Write-Host $Title -ForegroundColor Cyan
    Write-Host "$line" -ForegroundColor DarkCyan
    Add-Report "`n$line"
    Add-Report $Title
    Add-Report $line
}

function Invoke-ReportBlock { param([string]$Title, [scriptblock]$Block)
    Write-Section $Title
    try {
        $output = & $Block 2>&1 | Out-String -Width 4096
        if ([string]::IsNullOrWhiteSpace($output)) { $output = "No results returned." }
        Add-Report $output
        Write-Host "Status: complete" -ForegroundColor Green
    } catch {
        Add-Report "ERROR: $($_.Exception.Message)"
        Write-Host "Status: error" -ForegroundColor Red
    }
}

function Get-RunKeyEntries {
    $runKeys = @(
        "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run",
        "HKCU:\Software\Microsoft\Windows\CurrentVersion\RunOnce",
        "HKLM:\Software\Microsoft\Windows\CurrentVersion\Run",
        "HKLM:\Software\Microsoft\Windows\CurrentVersion\RunOnce",
        "HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Run"
    )

    foreach ($key in $runKeys) {
        if (Test-Path $key) {
            $props = Get-ItemProperty -Path $key
            $props.PSObject.Properties |
                Where-Object { $_.Name -notin @("PSPath","PSParentPath","PSChildName","PSDrive","PSProvider") } |
                ForEach-Object {
                    [PSCustomObject]@{
                        KeyPath = $key
                        Name = $_.Name
                        Command = [string]$_.Value
                    }
                }
        }
    }
}

function Disable-RunEntry {
    param([string]$KeyPath,[string]$Name,[string]$Command)
    $disabledKey = Join-Path $KeyPath "EngelDisabledStartup"
    if (-not (Test-Path $disabledKey)) { New-Item -Path $disabledKey -Force | Out-Null }
    New-ItemProperty -Path $disabledKey -Name $Name -Value $Command -PropertyType String -Force | Out-Null
    Remove-ItemProperty -Path $KeyPath -Name $Name -ErrorAction Stop
}

function Stop-NonEssentialProcess {
    param([string]$Name)
    if ($EssentialProcesses -notcontains $Name) {
        $proc = Get-Process -Name $Name -ErrorAction SilentlyContinue
        if ($proc) {
            Write-Host "Stopping process: $Name | Memory: $([math]::Round($proc.WorkingSet64/1MB,2)) MB"
            Stop-Process -Name $Name -Force -ErrorAction SilentlyContinue
        }
    }
}

# --- Main ---
Clear-Host
Write-Host "============================================================" -ForegroundColor DarkCyan
Write-Host " ENGEL STARTUP REVIEW + MEMORY OPTIMIZER (Delayed Scan)" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor DarkCyan
Write-Host ""

Write-Host "Report path: $Report"
Write-Host "Backup path: $BackupJson"

"Engel Startup Review Report" | Out-File -FilePath $Report -Encoding UTF8
Add-Report "Generated: $(Get-Date)"
Add-Report "Computer: $env:COMPUTERNAME"
Add-Report "User: $env:USERNAME"
Add-Report "Running as admin: $(Test-IsAdmin)"

if (-not (Test-IsAdmin)) {
    Write-Host "WARNING: Not running as Administrator. HKLM cleanup may be incomplete." -ForegroundColor Yellow
    Add-Report "WARNING: Not running as Administrator. HKLM cleanup may be incomplete."
}

# --- User mode selection ---
Write-Host "Choose mode:" -ForegroundColor Cyan
Write-Host "1 = Audit only"
Write-Host "2 = Disable GoogleDriveFS, OneDrive, Autodesk + stop their processes"
Write-Host "3 = Restore latest disabled startup backup"
$choice = Read-Host "Enter 1, 2, or 3"

# --- Capture startup commands ---
Invoke-ReportBlock "1. Current startup commands" {
    Get-CimInstance Win32_StartupCommand | ForEach-Object {
        $proc = Get-Process -Name $_.Name -ErrorAction SilentlyContinue
        $memMB = if ($proc) { [math]::Round($proc.WorkingSet64/1MB,2) } else { 0 }
        [PSCustomObject]@{
            Name = $_.Name
            Command = $_.Command
            Location = $_.Location
            User = $_.User
            MemoryMB = $memMB
        }
    } | Sort-Object Location, Name | Format-List
}

# --- Disable selected entries ---
if ($choice -eq "2") {
    Write-Section "2. Disabling GoogleDriveFS, OneDrive, Autodesk services"
    $entries = Get-RunKeyEntries | Where-Object { $DisableEntries -contains $_.Name }
    if (-not $entries) {
        Write-Host "No matching entries found." -ForegroundColor Yellow
        Add-Report "No matching entries found."
    } else {
        $entries | ConvertTo-Json -Depth 5 | Out-File -FilePath $BackupJson -Encoding UTF8
        Write-Host "Backup saved: $BackupJson" -ForegroundColor Cyan
        Add-Report "Backup saved: $BackupJson"

        foreach ($entry in $entries) {
            try {
                Disable-RunEntry -KeyPath $entry.KeyPath -Name $entry.Name -Command $entry.Command
                Stop-NonEssentialProcess -Name $entry.Name
                Write-Host "Disabled and stopped: $($entry.Name)" -ForegroundColor Green
                Add-Report "Disabled and stopped: $($entry.Name)"
            } catch {
                Write-Host "FAILED: $($entry.Name)" -ForegroundColor Red
                Add-Report "FAILED: $($entry.Name) -- $($_.Exception.Message)"
            }
        }
    }
}

# --- Restore backup ---
elseif ($choice -eq "3") {
    Write-Section "2. Restore latest disabled startup backup"
    $latest = Get-ChildItem -Path $BackupsFolder -Filter "EngelStartupReview_Backup_*.json" -File | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($latest) {
        $items = Get-Content $latest.FullName -Raw | ConvertFrom-Json
        foreach ($item in $items) {
            try {
                if (-not (Test-Path $item.KeyPath)) { New-Item -Path $item.KeyPath -Force | Out-Null }
                New-ItemProperty -Path $item.KeyPath -Name $item.Name -Value $item.Command -PropertyType String -Force | Out-Null
                Write-Host "Restored: $($item.Name)" -ForegroundColor Green
                Add-Report "Restored: $($item.Name)"
            } catch {
                Write-Host "FAILED restore: $($item.Name)" -ForegroundColor Red
                Add-Report "FAILED restore: $($item.Name) -- $($_.Exception.Message)"
            }
        }
    } else {
        Write-Host "No backup found." -ForegroundColor Yellow
        Add-Report "No backup found."
    }
}

# --- Delayed Memory Scan ---
Write-Section "3. Delayed Memory Scan (0-60 seconds)"
$DelaySeconds = 60
$Interval = 5
for ($i=0; $i -le $DelaySeconds; $i+=$Interval) {
    Write-Host "Memory snapshot at +$i seconds..."
    $procSnapshot = Get-Process -IncludeUserName | Sort-Object WS -Descending |
        Select-Object -First 20 Name, Id, UserName, @{Name="MemoryMB";Expression={[math]::Round($_.WS/1MB,2)}}
    Add-Report "Snapshot +$i sec:`n$($procSnapshot | Format-Table | Out-String)"
    Start-Sleep -Seconds $Interval
}

# --- Top memory consumers final ---
Invoke-ReportBlock "4. Top memory consumers after cleanup" {
    Get-Process -IncludeUserName | Sort-Object WS -Descending |
        Select-Object -First 10 Name, Id, UserName, @{Name="MemoryMB";Expression={[math]::Round($_.WS/1MB,2)}} | Format-Table -AutoSize
}

Add-Report "`nSTARTUP REVIEW COMPLETE: $(Get-Date)"
Add-Report "Report saved: $Report"

Write-Host "`nENGEL STARTUP REVIEW COMPLETE" -ForegroundColor Green
Write-Host "Report saved to: $Report" -ForegroundColor Cyan
Start-Process notepad.exe $Report
Read-Host "Press Enter to close this window"