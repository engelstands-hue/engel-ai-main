param(
    [string[]]$ScanTarget = @(),
    [switch]$KeepZipEvidence,
    [switch]$NoOpenReport,
    [switch]$NoPrompt,
    [int]$MaxZipEntries = 1000,
    [long]$MaxZipArchiveBytes = 536870912,
    [long]$MaxZipUncompressedBytes = 1073741824,
    [int]$ApprovedNestedArchiveDepth = 0,
    [int]$MaxZipEntryPathDepth = 20,
    [long]$MaxZipTextFileBytes = 5242880,
    [long]$MaxAiTextFileBytes = 5242880,
    [switch]$TriageSummary,
    [int]$TriageTopFiles = 20,
    [int]$TriageMaxExamplesPerGroup = 5,
    [switch]$TriageIncludeRawFindings,
    [switch]$TriageSuppressRawFindings,
    [int]$TriageAutoThreshold = 100
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Continue"

$ZipSupportedTextExtensions = @(
    ".bat", ".cmd", ".conf", ".config", ".cpp", ".cs", ".csproj", ".css",
    ".csv", ".fsproj", ".go", ".gradle", ".h", ".hpp", ".htm", ".html",
    ".ini", ".java", ".js", ".json", ".jsx", ".kt", ".lock", ".log",
    ".md", ".php", ".properties", ".ps1", ".psd1", ".psm1", ".py", ".rb",
    ".rs", ".sh", ".sln", ".sql", ".swift", ".toml", ".ts", ".tsx",
    ".txt", ".vb", ".vbproj", ".xml", ".yaml", ".yml"
)
$ZipSupportedTextNames = @(
    ".editorconfig", ".env", ".gitattributes", ".gitignore", "dockerfile",
    "gemfile", "makefile", "podfile", "rakefile"
)
$ZipArchiveExtensions = @(
    ".zip", ".7z", ".rar", ".tar", ".tgz", ".gz", ".bz2", ".xz"
)
$ZipSuspiciousTextPatterns = @(
    "Invoke-Expression", "\bIEX\b", "DownloadString", "DownloadFile",
    "FromBase64String", "Start-Process", "New-Object\s+Net\.WebClient",
    "System\.Net\.WebClient", "\bcurl\b", "\bwget\b", "\bbitsadmin\b",
    "\bcertutil\b", "\bregsvr32\b", "\brundll32\b", "\bmshta\b",
    "powershell\s+-", "cmd\s+/c", "chmod\s+\+x", "\bnc\s+-e\b",
    "/bin/bash", "\beval\s*\(", "child_process", "ProcessBuilder"
)
$AiSourceMaterialExtensions = @(".pdf", ".doc", ".docx", ".ppt", ".pptx", ".rtf")
$AiAgentSecurityRules = @(
    [PSCustomObject]@{
        Id = "AI001_PROMPT_INJECTION"
        Severity = "High"
        Description = "Prompt injection or instruction override content"
        Pattern = '(?i)\b(ignore|disregard|override|forget)\b.{0,80}\b(previous|prior|system|developer|instructions?)\b|reveal.{0,40}\b(system prompt|developer message|hidden instructions)\b|jailbreak|DAN mode'
    },
    [PSCustomObject]@{
        Id = "AI002_SECRET_EXPOSURE"
        Severity = "High"
        Description = "Secrets, API keys, bearer tokens, or credential handling"
        Pattern = '(?i)\b(api[_-]?key|secret[_-]?key|access[_-]?token|bearer\s+[A-Za-z0-9._-]{10,}|OPENAI_API_KEY|ANTHROPIC_API_KEY|AZURE_OPENAI|sk-[A-Za-z0-9_-]{10,})\b'
    },
    [PSCustomObject]@{
        Id = "AI003_TOOL_OR_PROCESS_EXECUTION"
        Severity = "High"
        Description = "Agent/tool code may execute commands, scripts, or processes"
        Pattern = '(?i)\b(Start-Process|Invoke-Expression|IEX|subprocess\.|os\.system|child_process|exec\s*\(|spawn\s*\(|ProcessBuilder|cmd\s*/c|powershell\s+-|bash\s+-c|sh\s+-c)\b'
    },
    [PSCustomObject]@{
        Id = "AI004_PROVIDER_OR_NETWORK_BEHAVIOR"
        Severity = "Medium"
        Description = "Provider/API/network behavior or outbound link/reference"
        Pattern = '(?i)\b(Invoke-WebRequest|Invoke-RestMethod|curl|wget|fetch\s*\(|requests\.|WebClient|http://|https://|OpenAI|Anthropic|Gemini|AzureOpenAI)\b'
    },
    [PSCustomObject]@{
        Id = "AI005_AUTONOMOUS_OR_PERSISTENT_BEHAVIOR"
        Severity = "High"
        Description = "Autonomous loop, background worker, scheduled task, service, or persistence behavior"
        Pattern = '(?i)\b(Start-Job|Register-ScheduledTask|New-Service|sc\.exe\s+create|while\s*\(\s*\$?true\s*\)|while\s+true|for\s*\(\s*;\s*;\s*\)|setInterval\s*\(|cron|daemon|background worker|persistent service|autonomous loop)\b'
    },
    [PSCustomObject]@{
        Id = "AI006_UNSAFE_REMEDIATION_OR_FILE_DESTRUCTIVE"
        Severity = "High"
        Description = "Destructive remediation or broad filesystem mutation"
        Pattern = '(?i)\b(Remove-Item\b.{0,80}-Recurse|rm\s+-rf|del\s+/s|format\s+[A-Z]:|delete all|wipe|remediate automatically|auto-remediate|quarantine automatically)\b'
    },
    [PSCustomObject]@{
        Id = "AI007_UNTRUSTED_CONTENT_BOUNDARY"
        Severity = "Medium"
        Description = "Untrusted content, tool output, archive, or source material boundary concern"
        Pattern = '(?i)\b(untrusted|tool output|source material|uploaded file|zip content|archive content|prompt from file|readme instructions|follow links|browser\.open|open url)\b'
    }
)

$TimeStamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$ScannerRoot = if ($PSScriptRoot) { $PSScriptRoot } else { (Get-Location).Path }
$ReportFolder = "D:\EngelTools\EngelSecurityScanner\Reports"
$Report = Join-Path $ReportFolder "EngelSecurityScan_Report_$TimeStamp.txt"

$DefaultScanTargets = @(
    "D:\b.WorkSpace\Engel App",
    "D:\Engel App Bible",
    "D:\EngelBible",
    "D:\EngelStandalone"
)

if ($ScanTarget.Count -gt 0) {
    $ScanTargets = @($ScanTarget | Where-Object { Test-Path -LiteralPath $_ })
}
else {
    $ScanTargets = @($DefaultScanTargets | Where-Object { Test-Path -LiteralPath $_ })
}

New-Item -ItemType Directory -Path $ReportFolder -Force | Out-Null

function Test-IsAdmin {
    try {
        $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
        $principal = New-Object Security.Principal.WindowsPrincipal($identity)
        return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    }
    catch {
        return $false
    }
}

function Add-Report {
    param([string]$Text)
    Add-Content -Path $Report -Value $Text
}

function Write-Header {
    param([string]$Title)

    $line = "=" * 72
    Write-Host ""
    Write-Host $line -ForegroundColor DarkCyan
    Write-Host $Title -ForegroundColor Cyan
    Write-Host $line -ForegroundColor DarkCyan

    Add-Report ""
    Add-Report $line
    Add-Report $Title
    Add-Report $line
}

function Invoke-ReportBlock {
    param(
        [string]$Title,
        [scriptblock]$Block
    )

    Write-Header $Title

    try {
        $output = & $Block 2>&1 | Out-String -Width 4096

        if ([string]::IsNullOrWhiteSpace($output)) {
            $output = "No results returned."
        }

        Add-Report $output
        Write-Host "Status: complete" -ForegroundColor Green
    }
    catch {
        Add-Report "ERROR: $($_.Exception.Message)"
        Write-Host "Status: error" -ForegroundColor Red
        Write-Host $_.Exception.Message -ForegroundColor Red
    }
}

function Format-ByteCount {
    param([long]$Bytes)

    if ($Bytes -ge 1GB) {
        return "{0:N2} GB" -f ($Bytes / 1GB)
    }
    if ($Bytes -ge 1MB) {
        return "{0:N2} MB" -f ($Bytes / 1MB)
    }
    if ($Bytes -ge 1KB) {
        return "{0:N2} KB" -f ($Bytes / 1KB)
    }

    return "$Bytes bytes"
}

function Add-LimitedListItem {
    param(
        [System.Collections.Generic.List[string]]$List,
        [string]$Item,
        [int]$Limit = 50
    )

    if ($List.Count -lt $Limit) {
        [void]$List.Add($Item)
    }
}

function Test-ZipEntryIsDirectory {
    param($Entry)

    return (
        $Entry.FullName.EndsWith("/") -or
        $Entry.FullName.EndsWith("\") -or
        [string]::IsNullOrEmpty($Entry.Name)
    )
}

function Get-ZipEntryPathIssue {
    param([string]$EntryName)

    if ([string]::IsNullOrWhiteSpace($EntryName)) {
        return "blank entry name"
    }

    $normalized = $EntryName.Replace("\", "/")

    if ($normalized.StartsWith("/") -or $normalized -match "^[A-Za-z]:") {
        return "absolute path"
    }
    if ($normalized -match "//") {
        return "empty path segment"
    }

    $segments = @($normalized -split "/" | Where-Object { $_ -ne "" })
    if ($segments.Count -eq 0) {
        return "empty entry path"
    }
    if ($segments.Count -gt $MaxZipEntryPathDepth) {
        return "path depth $($segments.Count) exceeds limit $MaxZipEntryPathDepth"
    }

    foreach ($segment in $segments) {
        if ($segment -eq "..") {
            return "path traversal segment '..'"
        }
        if ($segment -eq ".") {
            return "relative path segment '.'"
        }
        if ($segment -like "*:*") {
            return "colon in path segment"
        }
    }

    return $null
}

function Get-NormalizedZipEntryPath {
    param([string]$EntryName)

    $segments = @($EntryName.Replace("\", "/") -split "/" | Where-Object { $_ -ne "" })
    return ($segments -join [string][System.IO.Path]::DirectorySeparatorChar)
}

function Get-ScannerFileClassification {
    param([string]$Path)

    $leafName = [System.IO.Path]::GetFileName($Path).ToLowerInvariant()
    $extension = [System.IO.Path]::GetExtension($leafName).ToLowerInvariant()

    if ($extension -eq ".zip") {
        return "NestedZip"
    }
    if ($ZipArchiveExtensions -contains $extension) {
        return "NestedArchive"
    }
    if (($ZipSupportedTextExtensions -contains $extension) -or ($ZipSupportedTextNames -contains $leafName)) {
        return "Text"
    }

    return "ManualReview"
}

function Get-ZipEntryClassification {
    param([string]$EntryName)

    $relativePath = Get-NormalizedZipEntryPath -EntryName $EntryName
    return Get-ScannerFileClassification -Path $relativePath
}

function Get-ZipEntryDestinationPath {
    param(
        [string]$TempRoot,
        [string]$EntryName
    )

    $relativePath = Get-NormalizedZipEntryPath -EntryName $EntryName
    return [System.IO.Path]::GetFullPath((Join-Path $TempRoot $relativePath))
}

function Invoke-ZipPolicyScan {
    param(
        [string]$ZipPath,
        [int]$Depth = 0
    )

    $indent = "  " * $Depth
    $archive = $null
    $tempRoot = $null

    Write-Output "${indent}Archive: $ZipPath"

    try {
        Add-Type -AssemblyName System.IO.Compression.FileSystem -ErrorAction Stop

        $zipItem = Get-Item -LiteralPath $ZipPath -ErrorAction Stop
        if ($zipItem.Length -gt $MaxZipArchiveBytes) {
            Write-Output "${indent}Result: REJECTED"
            Write-Output "$indent- Archive size $(Format-ByteCount $zipItem.Length) exceeds limit $(Format-ByteCount $MaxZipArchiveBytes)."
            return
        }

        $archive = [System.IO.Compression.ZipFile]::OpenRead($zipItem.FullName)
        $entries = @($archive.Entries)
        $totalUncompressed = [long]0

        foreach ($entry in $entries) {
            $totalUncompressed += [long]$entry.Length
        }

        Write-Output "${indent}Manifest entries read before extraction: $($entries.Count)"
        Write-Output "${indent}Archive size: $(Format-ByteCount $zipItem.Length)"
        Write-Output "${indent}Total uncompressed size: $(Format-ByteCount $totalUncompressed)"
        Write-Output "${indent}Manifest inventory:"

        $manifestLimit = 200
        foreach ($entry in ($entries | Select-Object -First $manifestLimit)) {
            if (Test-ZipEntryIsDirectory -Entry $entry) {
                Write-Output "${indent}- $($entry.FullName) [Directory]"
            }
            else {
                $classification = Get-ZipEntryClassification -EntryName $entry.FullName
                Write-Output "${indent}- $($entry.FullName) [$classification, $(Format-ByteCount $entry.Length)]"
            }
        }
        if ($entries.Count -gt $manifestLimit) {
            Write-Output "${indent}- Manifest inventory truncated after $manifestLimit entries."
        }

        $rejections = New-Object "System.Collections.Generic.List[string]"
        if ($entries.Count -gt $MaxZipEntries) {
            [void]$rejections.Add("entry count $($entries.Count) exceeds limit $MaxZipEntries")
        }
        if ($totalUncompressed -gt $MaxZipUncompressedBytes) {
            [void]$rejections.Add("uncompressed size $(Format-ByteCount $totalUncompressed) exceeds limit $(Format-ByteCount $MaxZipUncompressedBytes)")
        }

        $seenPaths = @{}
        foreach ($entry in $entries) {
            $pathIssue = Get-ZipEntryPathIssue -EntryName $entry.FullName
            if ($pathIssue) {
                [void]$rejections.Add("$($entry.FullName): $pathIssue")
                continue
            }

            if (-not (Test-ZipEntryIsDirectory -Entry $entry)) {
                $normalizedPath = Get-NormalizedZipEntryPath -EntryName $entry.FullName
                $normalizedKey = $normalizedPath.ToLowerInvariant()

                if ($seenPaths.ContainsKey($normalizedKey)) {
                    [void]$rejections.Add("$($entry.FullName): duplicate normalized path '$normalizedPath'")
                }
                else {
                    $seenPaths[$normalizedKey] = $true
                }

                $classification = Get-ZipEntryClassification -EntryName $entry.FullName
                if (($classification -eq "NestedZip") -or ($classification -eq "NestedArchive")) {
                    $nestedDepth = $Depth + 1
                    if ($nestedDepth -gt $ApprovedNestedArchiveDepth) {
                        [void]$rejections.Add("$($entry.FullName): nested archive depth $nestedDepth exceeds approved depth $ApprovedNestedArchiveDepth")
                    }
                }
            }
        }

        if ($rejections.Count -gt 0) {
            Write-Output "${indent}Result: REJECTED"
            foreach ($reason in $rejections) {
                Write-Output "$indent- $reason"
            }
            return
        }

        Write-Output "${indent}Result: accepted for scanner-controlled temporary extraction"

        $tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("EngelSecurityScannerZip_{0}" -f ([System.Guid]::NewGuid().ToString("N")))
        New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null

        $rootFullPath = [System.IO.Path]::GetFullPath($tempRoot)
        $directorySeparator = [string][System.IO.Path]::DirectorySeparatorChar
        if (-not $rootFullPath.EndsWith($directorySeparator)) {
            $rootFullPath = $rootFullPath + $directorySeparator
        }

        $extractedCount = 0
        foreach ($entry in $entries) {
            if (Test-ZipEntryIsDirectory -Entry $entry) {
                continue
            }

            $destinationPath = Get-ZipEntryDestinationPath -TempRoot $tempRoot -EntryName $entry.FullName
            if (-not $destinationPath.StartsWith($rootFullPath, [System.StringComparison]::OrdinalIgnoreCase)) {
                throw "Blocked extraction outside scanner temp folder: $($entry.FullName)"
            }

            $destinationFolder = Split-Path -Path $destinationPath -Parent
            New-Item -ItemType Directory -Path $destinationFolder -Force | Out-Null
            [System.IO.Compression.ZipFileExtensions]::ExtractToFile($entry, $destinationPath, $false)
            $extractedCount++
        }

        Write-Output "${indent}Extracted entries to temp folder: $extractedCount"
        Write-Output "${indent}Execution policy: archive scripts, installers, macros, binaries, and build files were not run."

        $textFilesScanned = 0
        $textFileExamples = New-Object "System.Collections.Generic.List[string]"
        $manualReviewCount = 0
        $manualReviewExamples = New-Object "System.Collections.Generic.List[string]"
        $suspiciousFindingCount = 0
        $suspiciousExamples = New-Object "System.Collections.Generic.List[string]"

        foreach ($entry in $entries) {
            if (Test-ZipEntryIsDirectory -Entry $entry) {
                continue
            }

            $destinationPath = Get-ZipEntryDestinationPath -TempRoot $tempRoot -EntryName $entry.FullName
            $classification = Get-ZipEntryClassification -EntryName $entry.FullName

            if ($classification -eq "Text") {
                if ($entry.Length -gt $MaxZipTextFileBytes) {
                    $manualReviewCount++
                    Add-LimitedListItem -List $manualReviewExamples -Item "$($entry.FullName) (text/code file exceeds text scan limit $(Format-ByteCount $MaxZipTextFileBytes))"
                    continue
                }

                try {
                    $lineNumber = 0
                    foreach ($line in [System.IO.File]::ReadLines($destinationPath)) {
                        $lineNumber++
                        foreach ($pattern in $ZipSuspiciousTextPatterns) {
                            if ($line -match $pattern) {
                                $suspiciousFindingCount++
                                Add-LimitedListItem -List $suspiciousExamples -Item "$($entry.FullName):$lineNumber matched '$pattern'"
                                break
                            }
                        }
                    }
                    $textFilesScanned++
                    Add-LimitedListItem -List $textFileExamples -Item $entry.FullName
                }
                catch {
                    $manualReviewCount++
                    Add-LimitedListItem -List $manualReviewExamples -Item "$($entry.FullName) (could not read as text: $($_.Exception.Message))"
                }
                continue
            }

            if ($classification -eq "NestedZip") {
                Write-Output "${indent}Nested ZIP approved for recursive manifest scan: $($entry.FullName)"
                Invoke-ZipPolicyScan -ZipPath $destinationPath -Depth ($Depth + 1)
                continue
            }

            $manualReviewCount++
            if ($classification -eq "NestedArchive") {
                Add-LimitedListItem -List $manualReviewExamples -Item "$($entry.FullName) (unsupported nested archive format, $(Format-ByteCount $entry.Length))"
            }
            else {
                Add-LimitedListItem -List $manualReviewExamples -Item "$($entry.FullName) (unsupported binary or non-text file, $(Format-ByteCount $entry.Length))"
            }
        }

        Write-Output "${indent}Text/code files statically scanned: $textFilesScanned"
        foreach ($item in $textFileExamples) {
            Write-Output "$indent- Scanned text/code: $item"
        }

        Write-Output "${indent}Unsupported binaries/non-text files flagged for manual review: $manualReviewCount"
        foreach ($item in $manualReviewExamples) {
            Write-Output "$indent- Manual review: $item"
        }

        Write-Output "${indent}Suspicious text/code pattern matches: $suspiciousFindingCount"
        foreach ($item in $suspiciousExamples) {
            Write-Output "$indent- Finding: $item"
        }
    }
    catch {
        Write-Output "${indent}Result: ERROR"
        Write-Output "$indent- $($_.Exception.Message)"
    }
    finally {
        if ($archive -ne $null) {
            $archive.Dispose()
        }

        if ($tempRoot -and (Test-Path -LiteralPath $tempRoot)) {
            if ($KeepZipEvidence) {
                Write-Output "${indent}Evidence retained: $tempRoot"
            }
            else {
                Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
                Write-Output "${indent}Temp cleanup: deleted extracted files"
            }
        }
    }
}

function New-AiAgentScanState {
    return [PSCustomObject]@{
        TextFilesScanned = 0
        SourceMaterialsInventoried = 0
        UnsupportedFilesFlagged = 0
        FindingCount = 0
        ScannedTextFiles = New-Object "System.Collections.Generic.List[string]"
        SourceMaterialExamples = New-Object "System.Collections.Generic.List[string]"
        UnsupportedExamples = New-Object "System.Collections.Generic.List[string]"
        Findings = New-Object "System.Collections.Generic.List[string]"
        FindingRecords = New-Object "System.Collections.Generic.List[object]"
        UnsupportedRecords = New-Object "System.Collections.Generic.List[object]"
        ZipResults = New-Object "System.Collections.Generic.List[string]"
    }
}

function Format-TriageSnippet {
    param([string]$Text)

    if ($null -eq $Text) {
        return ""
    }

    $snippet = ($Text -replace "\s+", " ").Trim()
    if ($snippet.Length -gt 160) {
        return $snippet.Substring(0, 157) + "..."
    }

    return $snippet
}

function Get-TriageLogicalPath {
    param([string]$Path)

    if ($Path -like "*!*") {
        return ($Path -split "!", 2)[1]
    }

    return $Path
}

function Get-TriageFileName {
    param([string]$Path)

    $logicalPath = (Get-TriageLogicalPath -Path $Path).Replace("/", "\")
    return [System.IO.Path]::GetFileName($logicalPath)
}

function Get-TriagePathExtension {
    param([string]$Path)

    $fileName = Get-TriageFileName -Path $Path
    return [System.IO.Path]::GetExtension($fileName).ToLowerInvariant()
}

function Get-TriageProjectArea {
    param([string]$Path)

    $normalizedPath = $Path.Replace("/", "\").ToLowerInvariant()
    $logicalPath = (Get-TriageLogicalPath -Path $Path).Replace("/", "\").ToLowerInvariant()
    $fileName = Get-TriageFileName -Path $Path
    $fileNameLower = $fileName.ToLowerInvariant()
    $extension = Get-TriagePathExtension -Path $Path

    if (
        ($normalizedPath -match "\\reports?\\") -or
        ($normalizedPath -match "\\backups?\\") -or
        ($normalizedPath -match "\\checkpoint") -or
        ($normalizedPath -match "\\history\\") -or
        ($fileNameLower -like "*old*report*")
    ) {
        return "REPORT_OR_HISTORY"
    }

    if (
        ($normalizedPath -match "\\memory\\") -or
        ($normalizedPath -match "\\logs?\\") -or
        ($extension -in @(".log", ".jsonl")) -or
        ($fileNameLower -eq "main_agent_log.md") -or
        ($fileNameLower -like "project_memory_index*")
    ) {
        return "MEMORY_OR_LOG"
    }

    if (
        ($extension -in @(".ps1", ".py", ".kt", ".java", ".cs", ".js", ".ts", ".bat", ".cmd", ".vbs")) -or
        ($normalizedPath -match "\\live\\app\\") -or
        ($normalizedPath -match "\\tools?\\") -or
        ($normalizedPath -match "\\scripts?\\")
    ) {
        return "ACTIVE_CODE"
    }

    if ($extension -in @(".json", ".yml", ".yaml", ".toml", ".ini", ".cfg", ".config", ".properties", ".status")) {
        return "CONFIG"
    }

    if ($extension -in @(".exe", ".dll", ".bin", ".dat", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".wav", ".mp3", ".mp4", ".pdf", ".doc", ".docx", ".ppt", ".pptx", ".zip", ".7z", ".rar")) {
        return "ASSET_OR_BINARY"
    }

    return "UNKNOWN"
}

function Add-AiAgentUnsupportedFile {
    param(
        $State,
        [string]$Path,
        [string]$Reason,
        [long]$Size = 0
    )

    $State.UnsupportedFilesFlagged++
    $sizeText = if ($Size -gt 0) { ", $(Format-ByteCount $Size)" } else { "" }
    Add-LimitedListItem -List $State.UnsupportedExamples -Item "$Path ($Reason$sizeText)" -Limit 200
    [void]$State.UnsupportedRecords.Add([PSCustomObject]@{
        Source = $Path
        Reason = $Reason
        Size = $Size
        ProjectArea = Get-TriageProjectArea -Path $Path
        Extension = Get-TriagePathExtension -Path $Path
    })
}

function Add-AiAgentRuleMatch {
    param(
        $State,
        [string]$Source,
        [int]$LineNumber,
        $Rule,
        [string]$Line
    )

    $State.FindingCount++
    $snippet = Format-TriageSnippet -Text $Line
    $rawFinding = "[$($Rule.Severity) $($Rule.Id)] ${Source}:$LineNumber - $($Rule.Description)"
    if (-not [string]::IsNullOrWhiteSpace($snippet)) {
        $rawFinding = "$rawFinding | $snippet"
    }

    [void]$State.Findings.Add($rawFinding)
    [void]$State.FindingRecords.Add([PSCustomObject]@{
        Severity = $Rule.Severity
        RuleId = $Rule.Id
        RuleDescription = $Rule.Description
        Source = $Source
        LineNumber = $LineNumber
        Snippet = $snippet
        ProjectArea = Get-TriageProjectArea -Path $Source
    })
}

function Invoke-AiAgentTextLineScan {
    param(
        $State,
        [string]$Source,
        [int]$LineNumber,
        [string]$Line
    )

    foreach ($rule in $AiAgentSecurityRules) {
        if ($Line -match $rule.Pattern) {
            Add-AiAgentRuleMatch -State $State -Source $Source -LineNumber $LineNumber -Rule $rule -Line $Line
        }
    }
}

function Invoke-AiAgentTextFileScan {
    param(
        $State,
        [string]$Path,
        [string]$DisplayPath
    )

    try {
        $file = Get-Item -LiteralPath $Path -ErrorAction Stop
        if ($file.Length -gt $MaxAiTextFileBytes) {
            Add-AiAgentUnsupportedFile -State $State -Path $DisplayPath -Reason "text/code file exceeds AI scan limit $(Format-ByteCount $MaxAiTextFileBytes)" -Size $file.Length
            return
        }

        $lineNumber = 0
        foreach ($line in [System.IO.File]::ReadLines($file.FullName)) {
            $lineNumber++
            Invoke-AiAgentTextLineScan -State $State -Source $DisplayPath -LineNumber $lineNumber -Line $line
        }

        $State.TextFilesScanned++
        Add-LimitedListItem -List $State.ScannedTextFiles -Item $DisplayPath -Limit 200
    }
    catch {
        Add-AiAgentUnsupportedFile -State $State -Path $DisplayPath -Reason "could not read as text: $($_.Exception.Message)"
    }
}

function Add-AiAgentSourceMaterialInventory {
    param(
        $State,
        [string]$Path,
        [string]$Scope
    )

    try {
        $file = Get-Item -LiteralPath $Path -ErrorAction Stop
        $State.SourceMaterialsInventoried++
        Add-LimitedListItem -List $State.SourceMaterialExamples -Item "$($file.FullName) [$Scope, $(Format-ByteCount $file.Length), inventory only; links not followed]" -Limit 200
    }
    catch {
        Add-AiAgentUnsupportedFile -State $State -Path $Path -Reason "source material inventory failed: $($_.Exception.Message)"
    }
}

function Invoke-AiAgentSourceMaterialInventory {
    param(
        $State,
        [string[]]$Targets
    )

    $seen = @{}
    $rootMaterials = @()
    if (Test-Path -LiteralPath $ScannerRoot) {
        $rootMaterials = Get-ChildItem -LiteralPath $ScannerRoot -File -ErrorAction SilentlyContinue |
            Where-Object { $AiSourceMaterialExtensions -contains [System.IO.Path]::GetExtension($_.Name).ToLowerInvariant() }
    }

    foreach ($item in $rootMaterials) {
        $key = $item.FullName.ToLowerInvariant()
        if (-not $seen.ContainsKey($key)) {
            $seen[$key] = $true
            Add-AiAgentSourceMaterialInventory -State $State -Path $item.FullName -Scope "scanner-root source material"
        }
    }

    foreach ($target in $Targets) {
        if (-not (Test-Path -LiteralPath $target)) {
            continue
        }

        $targetMaterials = Get-ChildItem -LiteralPath $target -Recurse -File -ErrorAction SilentlyContinue |
            Where-Object { $AiSourceMaterialExtensions -contains [System.IO.Path]::GetExtension($_.Name).ToLowerInvariant() }

        foreach ($item in $targetMaterials) {
            $key = $item.FullName.ToLowerInvariant()
            if (-not $seen.ContainsKey($key)) {
                $seen[$key] = $true
                Add-AiAgentSourceMaterialInventory -State $State -Path $item.FullName -Scope "scan-target source material"
            }
        }
    }
}

function Invoke-AiAgentLooseFileScan {
    param(
        $State,
        [string[]]$Targets
    )

    foreach ($target in $Targets) {
        if (-not (Test-Path -LiteralPath $target)) {
            continue
        }

        $files = Get-ChildItem -LiteralPath $target -Recurse -File -ErrorAction SilentlyContinue |
            Sort-Object FullName

        foreach ($file in $files) {
            $extension = [System.IO.Path]::GetExtension($file.Name).ToLowerInvariant()
            if ($extension -eq ".zip") {
                continue
            }
            if ($AiSourceMaterialExtensions -contains $extension) {
                continue
            }

            $classification = Get-ScannerFileClassification -Path $file.FullName
            if ($classification -eq "Text") {
                Invoke-AiAgentTextFileScan -State $State -Path $file.FullName -DisplayPath $file.FullName
            }
            else {
                Add-AiAgentUnsupportedFile -State $State -Path $file.FullName -Reason "unsupported non-text file" -Size $file.Length
            }
        }
    }
}

function Invoke-AiAgentZipScan {
    param(
        $State,
        [string]$ZipPath,
        [int]$Depth = 0
    )

    $indent = "  " * $Depth
    $archive = $null
    $tempRoot = $null
    Add-LimitedListItem -List $State.ZipResults -Item "${indent}Archive: $ZipPath" -Limit 300

    try {
        Add-Type -AssemblyName System.IO.Compression.FileSystem -ErrorAction Stop

        $zipItem = Get-Item -LiteralPath $ZipPath -ErrorAction Stop
        if ($zipItem.Length -gt $MaxZipArchiveBytes) {
            Add-LimitedListItem -List $State.ZipResults -Item "${indent}Result: REJECTED - archive size $(Format-ByteCount $zipItem.Length) exceeds limit $(Format-ByteCount $MaxZipArchiveBytes)" -Limit 300
            return
        }

        $archive = [System.IO.Compression.ZipFile]::OpenRead($zipItem.FullName)
        $entries = @($archive.Entries)
        $totalUncompressed = [long]0
        foreach ($entry in $entries) {
            $totalUncompressed += [long]$entry.Length
        }

        Add-LimitedListItem -List $State.ZipResults -Item "${indent}Manifest entries read before extraction: $($entries.Count)" -Limit 300

        $rejections = New-Object "System.Collections.Generic.List[string]"
        if ($entries.Count -gt $MaxZipEntries) {
            [void]$rejections.Add("entry count $($entries.Count) exceeds limit $MaxZipEntries")
        }
        if ($totalUncompressed -gt $MaxZipUncompressedBytes) {
            [void]$rejections.Add("uncompressed size $(Format-ByteCount $totalUncompressed) exceeds limit $(Format-ByteCount $MaxZipUncompressedBytes)")
        }

        foreach ($entry in $entries) {
            $pathIssue = Get-ZipEntryPathIssue -EntryName $entry.FullName
            if ($pathIssue) {
                [void]$rejections.Add("$($entry.FullName): $pathIssue")
                continue
            }

            if (-not (Test-ZipEntryIsDirectory -Entry $entry)) {
                $classification = Get-ZipEntryClassification -EntryName $entry.FullName
                Add-LimitedListItem -List $State.ZipResults -Item "${indent}- $($entry.FullName) [$classification, $(Format-ByteCount $entry.Length)]" -Limit 300

                if (($classification -eq "NestedZip") -or ($classification -eq "NestedArchive")) {
                    $nestedDepth = $Depth + 1
                    if ($nestedDepth -gt $ApprovedNestedArchiveDepth) {
                        [void]$rejections.Add("$($entry.FullName): nested archive depth $nestedDepth exceeds approved depth $ApprovedNestedArchiveDepth")
                    }
                }
            }
        }

        if ($rejections.Count -gt 0) {
            Add-LimitedListItem -List $State.ZipResults -Item "${indent}Result: REJECTED" -Limit 300
            foreach ($reason in $rejections) {
                Add-LimitedListItem -List $State.ZipResults -Item "${indent}- $reason" -Limit 300
            }
            return
        }

        Add-LimitedListItem -List $State.ZipResults -Item "${indent}Result: accepted for static AI rule scan" -Limit 300

        $tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("EngelSecurityScannerAiZip_{0}" -f ([System.Guid]::NewGuid().ToString("N")))
        New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null

        $rootFullPath = [System.IO.Path]::GetFullPath($tempRoot)
        $directorySeparator = [string][System.IO.Path]::DirectorySeparatorChar
        if (-not $rootFullPath.EndsWith($directorySeparator)) {
            $rootFullPath = $rootFullPath + $directorySeparator
        }

        foreach ($entry in $entries) {
            if (Test-ZipEntryIsDirectory -Entry $entry) {
                continue
            }

            $destinationPath = Get-ZipEntryDestinationPath -TempRoot $tempRoot -EntryName $entry.FullName
            if (-not $destinationPath.StartsWith($rootFullPath, [System.StringComparison]::OrdinalIgnoreCase)) {
                throw "Blocked AI ZIP extraction outside scanner temp folder: $($entry.FullName)"
            }

            $destinationFolder = Split-Path -Path $destinationPath -Parent
            New-Item -ItemType Directory -Path $destinationFolder -Force | Out-Null
            [System.IO.Compression.ZipFileExtensions]::ExtractToFile($entry, $destinationPath, $false)

            $classification = Get-ZipEntryClassification -EntryName $entry.FullName
            if ($classification -eq "Text") {
                Invoke-AiAgentTextFileScan -State $State -Path $destinationPath -DisplayPath "$ZipPath!$($entry.FullName)"
            }
            elseif ($classification -eq "NestedZip") {
                Invoke-AiAgentZipScan -State $State -ZipPath $destinationPath -Depth ($Depth + 1)
            }
            elseif ($classification -eq "NestedArchive") {
                Add-AiAgentUnsupportedFile -State $State -Path "$ZipPath!$($entry.FullName)" -Reason "unsupported nested archive format" -Size $entry.Length
            }
            else {
                Add-AiAgentUnsupportedFile -State $State -Path "$ZipPath!$($entry.FullName)" -Reason "unsupported non-text ZIP entry" -Size $entry.Length
            }
        }
    }
    catch {
        Add-LimitedListItem -List $State.ZipResults -Item "${indent}Result: ERROR - $($_.Exception.Message)" -Limit 300
    }
    finally {
        if ($archive -ne $null) {
            $archive.Dispose()
        }

        if ($tempRoot -and (Test-Path -LiteralPath $tempRoot)) {
            Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
            Add-LimitedListItem -List $State.ZipResults -Item "${indent}Temp cleanup: deleted AI ZIP extracted files" -Limit 300
        }
    }
}

function Get-AiTriagePriority {
    param($Item)

    if ($Item.Kind -eq "Unsupported") {
        if (($Item.ProjectArea -eq "ACTIVE_CODE") -and ($Item.Extension -eq ".exe")) {
            return "P0 Immediate review"
        }
        if ($Item.ProjectArea -eq "ACTIVE_CODE") {
            return "P1 Review next"
        }
        return "P3 Low context"
    }

    if (($Item.Severity -eq "Critical") -and ($Item.ProjectArea -eq "ACTIVE_CODE")) {
        return "P0 Immediate review"
    }

    if (
        ($Item.Severity -eq "High") -and
        ($Item.ProjectArea -eq "ACTIVE_CODE") -and
        (
            ($Item.RuleId -in @("AI003_TOOL_OR_PROCESS_EXECUTION", "AI005_AUTONOMOUS_OR_PERSISTENT_BEHAVIOR", "AI006_UNSAFE_REMEDIATION_OR_FILE_DESTRUCTIVE")) -or
            ($Item.Snippet -match "(?i)\b(exec|spawn|subprocess|Start-Process|cmd\s*/c|powershell\s+-|shell|process|startup|persistence|write|delete|remove|tool)\b")
        )
    ) {
        return "P0 Immediate review"
    }

    if (
        ($Item.Severity -eq "High") -and
        (
            ($Item.ProjectArea -in @("CONFIG", "MEMORY_OR_LOG")) -or
            ($Item.RuleId -in @("AI005_AUTONOMOUS_OR_PERSISTENT_BEHAVIOR", "AI006_UNSAFE_REMEDIATION_OR_FILE_DESTRUCTIVE"))
        )
    ) {
        return "P1 Review next"
    }

    if (
        ($Item.Severity -eq "Medium") -and
        (
            ($Item.ProjectArea -in @("REPORT_OR_HISTORY", "MEMORY_OR_LOG")) -or
            ($Item.RuleId -in @("AI004_PROVIDER_OR_NETWORK_BEHAVIOR", "AI007_UNTRUSTED_CONTENT_BOUNDARY"))
        )
    ) {
        return "P2 Historical/noisy review"
    }

    if (
        ($Item.RuleId -eq "AI001_PROMPT_INJECTION") -and
        ($Item.Source -match "(?i)\\(reports?|backups?|test_inputs|docs?|notes?|history)\\")
    ) {
        return "P2 Historical/noisy review"
    }

    if ($Item.Severity -eq "Low") {
        return "P3 Low context"
    }

    if ($Item.ProjectArea -eq "ASSET_OR_BINARY") {
        return "P3 Low context"
    }

    return "P1 Review next"
}

function ConvertTo-AiTriageItems {
    param($State)

    $items = New-Object "System.Collections.Generic.List[object]"

    foreach ($finding in $State.FindingRecords) {
        $item = [PSCustomObject]@{
            Kind = "Finding"
            Severity = $finding.Severity
            RuleId = $finding.RuleId
            RuleDescription = $finding.RuleDescription
            Source = $finding.Source
            LineNumber = $finding.LineNumber
            Snippet = $finding.Snippet
            ProjectArea = $finding.ProjectArea
            Extension = Get-TriagePathExtension -Path $finding.Source
            Priority = ""
        }
        $item.Priority = Get-AiTriagePriority -Item $item
        [void]$items.Add($item)
    }

    foreach ($unsupported in $State.UnsupportedRecords) {
        $item = [PSCustomObject]@{
            Kind = "Unsupported"
            Severity = "ManualReview"
            RuleId = "UNSUPPORTED_FILE"
            RuleDescription = $unsupported.Reason
            Source = $unsupported.Source
            LineNumber = 0
            Snippet = "$($unsupported.Reason)"
            ProjectArea = $unsupported.ProjectArea
            Extension = $unsupported.Extension
            Priority = ""
        }
        $item.Priority = Get-AiTriagePriority -Item $item
        [void]$items.Add($item)
    }

    return @($items.ToArray())
}

function Write-TriageTopGroups {
    param(
        [string]$Title,
        [object[]]$Groups,
        [int]$Limit = $TriageTopFiles
    )

    Write-Output $Title
    $topGroups = @($Groups | Sort-Object Count -Descending | Select-Object -First $Limit)
    if ($topGroups.Count -eq 0) {
        Write-Output "- None"
        return
    }

    foreach ($group in $topGroups) {
        Write-Output "- $($group.Name): $($group.Count)"
    }
}

function Write-TriagePriorityGroups {
    param(
        [object[]]$Items,
        [string]$Priority
    )

    Write-Output "$Priority"
    $priorityItems = @($Items | Where-Object { $_.Priority -eq $Priority })
    if ($priorityItems.Count -eq 0) {
        Write-Output "- None"
        return
    }

    $groups = @($priorityItems | Group-Object { "$($_.RuleId)|$($_.ProjectArea)|$($_.Source)" } | Sort-Object Count -Descending | Select-Object -First $TriageTopFiles)
    foreach ($group in $groups) {
        $first = $group.Group | Select-Object -First 1
        $lines = @(
            $group.Group |
                Where-Object { $_.LineNumber -gt 0 } |
                Select-Object -ExpandProperty LineNumber -First $TriageMaxExamplesPerGroup
        )
        $lineText = if ($lines.Count -gt 0) { " lines " + ($lines -join ", ") } else { "" }
        Write-Output "- [$($first.ProjectArea)] $($first.RuleId) :: $($first.Source) :: count $($group.Count)$lineText"

        $examples = @($group.Group | Where-Object { -not [string]::IsNullOrWhiteSpace($_.Snippet) } | Select-Object -First $TriageMaxExamplesPerGroup)
        foreach ($example in $examples) {
            Write-Output "  example: $($example.Snippet)"
        }
    }
}

function Write-AiAgentTriageSummary {
    param($State)

    $findings = @($State.FindingRecords.ToArray())
    $triageItems = @(ConvertTo-AiTriageItems -State $State)

    Write-Output "AI_AGENT_TRIAGE_SUMMARY_V1"
    Write-Output "Triage thresholds: explicit=$TriageSummary; auto threshold=$TriageAutoThreshold; top files=$TriageTopFiles; examples per group=$TriageMaxExamplesPerGroup"
    Write-Output "Total AI findings: $($State.FindingCount)"
    Write-Output "Total critical findings: $(@($findings | Where-Object { $_.Severity -eq 'Critical' }).Count)"
    Write-Output "Total high findings: $(@($findings | Where-Object { $_.Severity -eq 'High' }).Count)"
    Write-Output "Total medium findings: $(@($findings | Where-Object { $_.Severity -eq 'Medium' }).Count)"
    Write-Output "Total low findings: $(@($findings | Where-Object { $_.Severity -eq 'Low' }).Count)"
    Write-Output "Unsupported manual-review files included in triage: $($State.UnsupportedFilesFlagged)"
    Write-Output ""

    Write-TriageTopGroups -Title "Top rules by count:" -Groups @($findings | Group-Object RuleId)
    Write-Output ""

    Write-TriageTopGroups -Title "Top files by count:" -Groups @($findings | Group-Object Source)
    Write-Output ""

    Write-TriageTopGroups -Title "Top high/critical files:" -Groups @($findings | Where-Object { $_.Severity -in @("Critical", "High") } | Group-Object Source)
    Write-Output ""

    Write-TriageTopGroups -Title "Findings grouped by project area:" -Groups @($findings | Group-Object ProjectArea) -Limit 20
    Write-Output ""

    Write-Output "Repeated historical/noisy files:"
    $noisyGroups = @(
        $findings |
            Where-Object { $_.ProjectArea -in @("MEMORY_OR_LOG", "REPORT_OR_HISTORY") } |
            Group-Object Source |
            Where-Object { $_.Count -ge 10 } |
            Sort-Object Count -Descending |
            Select-Object -First $TriageTopFiles
    )
    if ($noisyGroups.Count -eq 0) {
        Write-Output "- None above repeated-noise threshold."
    }
    else {
        foreach ($group in $noisyGroups) {
            $first = $group.Group | Select-Object -First 1
            $ruleSummary = ($group.Group | Group-Object RuleId | Sort-Object Count -Descending | Select-Object -First 3 | ForEach-Object { "$($_.Name)=$($_.Count)" }) -join "; "
            Write-Output "- [$($first.ProjectArea)] $($group.Name): $($group.Count) findings ($ruleSummary)"
        }
    }
    Write-Output ""

    Write-Output "Recommended manual review order:"
    foreach ($priority in @("P0 Immediate review", "P1 Review next", "P2 Historical/noisy review", "P3 Low context")) {
        Write-TriagePriorityGroups -Items $triageItems -Priority $priority
    }
}

function Invoke-AiAgentSecurityRulePackForTargets {
    param([string[]]$Targets)

    $state = New-AiAgentScanState

    Write-Output "Rule pack: AI_AGENT_SECURITY_RULE_PACK_V1"
    Write-Output "Handling: static scanning only; scanned files and ZIP contents are not executed; source materials are inventoried only; links are not followed."
    Write-Output "Rules loaded: $($AiAgentSecurityRules.Count)"
    Write-Output "Max AI text file bytes: $(Format-ByteCount $MaxAiTextFileBytes)"
    Write-Output ""

    if (-not $Targets -or $Targets.Count -eq 0) {
        Write-Output "No scan targets available for AI agent rule pack scan."
    }
    else {
        Invoke-AiAgentSourceMaterialInventory -State $state -Targets $Targets
        Invoke-AiAgentLooseFileScan -State $state -Targets $Targets

        $zipFiles = @()
        foreach ($target in $Targets) {
            if (Test-Path -LiteralPath $target) {
                $zipFiles += Get-ChildItem -LiteralPath $target -Recurse -File -Filter "*.zip" -ErrorAction SilentlyContinue
            }
        }

        foreach ($zipFile in ($zipFiles | Sort-Object FullName)) {
            Invoke-AiAgentZipScan -State $state -ZipPath $zipFile.FullName -Depth 0
        }
    }

    Write-Output "Source materials inventoried: $($state.SourceMaterialsInventoried)"
    foreach ($item in $state.SourceMaterialExamples) {
        Write-Output "- Source material: $item"
    }
    Write-Output ""

    Write-Output "Text/code files statically scanned by AI rule pack: $($state.TextFilesScanned)"
    foreach ($item in $state.ScannedTextFiles) {
        Write-Output "- Scanned text/code: $item"
    }
    Write-Output ""

    Write-Output "Unsupported AI rule pack files flagged for manual review: $($state.UnsupportedFilesFlagged)"
    foreach ($item in $state.UnsupportedExamples) {
        Write-Output "- Manual review: $item"
    }
    Write-Output ""

    Write-Output "AI agent security findings: $($state.FindingCount)"
    $showTriageSummary = [bool]$TriageSummary -or ($state.FindingCount -gt $TriageAutoThreshold)
    if ($showTriageSummary) {
        Write-AiAgentTriageSummary -State $state
    }
    else {
        Write-Output "AI_AGENT_TRIAGE_SUMMARY_V1: not emitted because finding count $($state.FindingCount) did not exceed auto threshold $TriageAutoThreshold and -TriageSummary was not selected."
    }
    Write-Output ""

    $includeRawFindings = (-not [bool]$TriageSuppressRawFindings) -or [bool]$TriageIncludeRawFindings
    if ($includeRawFindings) {
        Write-Output "AI agent raw findings appendix:"
        Write-Output "Raw findings preserved: $($state.Findings.Count)"
        foreach ($item in $state.Findings) {
            Write-Output "- Finding: $item"
        }
    }
    else {
        Write-Output "AI agent raw findings appendix suppressed by -TriageSuppressRawFindings."
    }
    Write-Output ""

    Write-Output "AI ZIP static scan results:"
    if ($state.ZipResults.Count -eq 0) {
        Write-Output "No ZIP archives found for AI rule pack scan."
    }
    else {
        foreach ($item in $state.ZipResults) {
            Write-Output $item
        }
    }
}

function Invoke-LooseTargetPolicyScanForTargets {
    param([string[]]$Targets)

    Write-Output "Loose target file static scan:"

    if (-not $Targets -or $Targets.Count -eq 0) {
        Write-Output "No scan targets available for loose file static scan."
        Write-Output ""
        return
    }

    $files = @()
    foreach ($target in $Targets) {
        if (Test-Path -LiteralPath $target) {
            $files += Get-ChildItem -LiteralPath $target -Recurse -File -ErrorAction SilentlyContinue |
                Where-Object { [System.IO.Path]::GetExtension($_.Name).ToLowerInvariant() -ne ".zip" }
        }
    }

    if (-not $files -or $files.Count -eq 0) {
        Write-Output "No loose non-ZIP files found in scan targets."
        Write-Output ""
        return
    }

    $textFilesScanned = 0
    $textFileExamples = New-Object "System.Collections.Generic.List[string]"
    $manualReviewCount = 0
    $manualReviewExamples = New-Object "System.Collections.Generic.List[string]"
    $suspiciousFindingCount = 0
    $suspiciousExamples = New-Object "System.Collections.Generic.List[string]"

    foreach ($file in ($files | Sort-Object FullName)) {
        $classification = Get-ScannerFileClassification -Path $file.FullName

        if ($classification -eq "Text") {
            if ($file.Length -gt $MaxZipTextFileBytes) {
                $manualReviewCount++
                Add-LimitedListItem -List $manualReviewExamples -Item "$($file.FullName) (text/code file exceeds text scan limit $(Format-ByteCount $MaxZipTextFileBytes))"
                continue
            }

            try {
                $lineNumber = 0
                foreach ($line in [System.IO.File]::ReadLines($file.FullName)) {
                    $lineNumber++
                    foreach ($pattern in $ZipSuspiciousTextPatterns) {
                        if ($line -match $pattern) {
                            $suspiciousFindingCount++
                            Add-LimitedListItem -List $suspiciousExamples -Item "$($file.FullName):$lineNumber matched '$pattern'"
                            break
                        }
                    }
                }

                $textFilesScanned++
                Add-LimitedListItem -List $textFileExamples -Item $file.FullName
            }
            catch {
                $manualReviewCount++
                Add-LimitedListItem -List $manualReviewExamples -Item "$($file.FullName) (could not read as text: $($_.Exception.Message))"
            }
            continue
        }

        $manualReviewCount++
        if ($classification -eq "NestedArchive") {
            Add-LimitedListItem -List $manualReviewExamples -Item "$($file.FullName) (unsupported archive format, $(Format-ByteCount $file.Length))"
        }
        else {
            Add-LimitedListItem -List $manualReviewExamples -Item "$($file.FullName) (unsupported binary or non-text file, $(Format-ByteCount $file.Length))"
        }
    }

    Write-Output "Text/code loose files statically scanned: $textFilesScanned"
    foreach ($item in $textFileExamples) {
        Write-Output "- Scanned text/code: $item"
    }

    Write-Output "Unsupported loose binaries/non-text files flagged for manual review: $manualReviewCount"
    foreach ($item in $manualReviewExamples) {
        Write-Output "- Manual review: $item"
    }

    Write-Output "Suspicious loose text/code pattern matches: $suspiciousFindingCount"
    foreach ($item in $suspiciousExamples) {
        Write-Output "- Finding: $item"
    }

    Write-Output ""
}

function Invoke-ZipPolicyScanForTargets {
    param([string[]]$Targets)

    Write-Output "Policy: ZIP_SCAN_POLICY_V1"
    Write-Output "Handling: every ZIP is untrusted; manifests are read before extraction; extraction is temp-only; archive contents are never executed."
    Write-Output "Limits: MaxZipEntries=$MaxZipEntries; MaxZipArchiveBytes=$(Format-ByteCount $MaxZipArchiveBytes); MaxZipUncompressedBytes=$(Format-ByteCount $MaxZipUncompressedBytes); ApprovedNestedArchiveDepth=$ApprovedNestedArchiveDepth; MaxZipEntryPathDepth=$MaxZipEntryPathDepth; MaxZipTextFileBytes=$(Format-ByteCount $MaxZipTextFileBytes)"
    Write-Output "Keep evidence copy: $KeepZipEvidence"
    Write-Output ""

    Invoke-LooseTargetPolicyScanForTargets -Targets $Targets

    if (-not $Targets -or $Targets.Count -eq 0) {
        Write-Output "No scan targets available for ZIP policy scan."
        return
    }

    $zipFiles = @()
    foreach ($target in $Targets) {
        if (Test-Path -LiteralPath $target) {
            $zipFiles += Get-ChildItem -LiteralPath $target -Recurse -File -Filter "*.zip" -ErrorAction SilentlyContinue
        }
    }

    if (-not $zipFiles -or $zipFiles.Count -eq 0) {
        Write-Output "No ZIP archives found in scan targets."
        return
    }

    Write-Output "ZIP archives found: $($zipFiles.Count)"
    Write-Output ""

    foreach ($zipFile in ($zipFiles | Sort-Object FullName)) {
        Invoke-ZipPolicyScan -ZipPath $zipFile.FullName -Depth 0
        Write-Output ""
    }
}

function Wait-JobWithSpinner {
    param(
        [System.Management.Automation.Job]$Job,
        [string]$Target
    )

    $spinner = @("|","/","-","\")
    $i = 0
    $start = Get-Date

    while ($Job.State -eq "Running") {
        $elapsed = New-TimeSpan -Start $start -End (Get-Date)
        $spin = $spinner[$i % $spinner.Count]

        Write-Host "`r$spin Scanning: $Target | elapsed $($elapsed.ToString('hh\:mm\:ss'))   " -NoNewline -ForegroundColor Cyan

        Write-Progress `
            -Activity "Engel Security Scan" `
            -Status "Scanning $Target | elapsed $($elapsed.ToString('hh\:mm\:ss'))" `
            -PercentComplete -1

        Start-Sleep -Milliseconds 500
        $i++
    }

    Write-Progress -Activity "Engel Security Scan" -Completed
    Write-Host ""

    $result = Receive-Job -Job $Job -ErrorAction SilentlyContinue 2>&1 | Out-String -Width 4096
    $state = $Job.State
    Remove-Job -Job $Job -Force -ErrorAction SilentlyContinue

    return [PSCustomObject]@{
        State = $state
        Output = $result
        Elapsed = (New-TimeSpan -Start $start -End (Get-Date))
    }
}

Clear-Host
Write-Host ""
Write-Host "============================================================" -ForegroundColor DarkCyan
Write-Host " ENGEL SECURITY SCAN" -ForegroundColor Cyan
Write-Host " Defender custom scan + startup/network/security report" -ForegroundColor Gray
Write-Host "============================================================" -ForegroundColor DarkCyan
Write-Host ""
Write-Host "Mode:      D: Engel project folders only" -ForegroundColor White
Write-Host "No delete: This script only scans and reports" -ForegroundColor White
Write-Host "Report:    $Report" -ForegroundColor White
Write-Host ""

"Engel Security Scan Report" | Out-File -FilePath $Report -Encoding UTF8
Add-Report "Generated: $(Get-Date)"
Add-Report "Computer: $env:COMPUTERNAME"
Add-Report "User: $env:USERNAME"
Add-Report "Running as admin: $(Test-IsAdmin)"
Add-Report "Report path: $Report"
Add-Report ""
Add-Report "Scan targets:"

Write-Host "Scan targets:" -ForegroundColor Cyan
foreach ($target in $ScanTargets) {
    Add-Report $target
    Write-Host "  [OK] $target" -ForegroundColor Green
}

if (-not (Test-IsAdmin)) {
    Write-Host "WARNING: Not running as Administrator. Some checks may be incomplete." -ForegroundColor Yellow
    Add-Report "WARNING: Not running as Administrator. Some checks may be incomplete."
}

Invoke-ReportBlock "1. Defender status" {
    Get-Service WinDefend, SecurityHealthService |
        Select-Object Name, Status, StartType |
        Format-Table -AutoSize

    ""
    Get-MpComputerStatus |
        Select-Object AntivirusEnabled, RealTimeProtectionEnabled, BehaviorMonitorEnabled, IoavProtectionEnabled, IsTamperProtected, AntivirusSignatureLastUpdated, QuickScanAge, FullScanAge |
        Format-List
}

Invoke-ReportBlock "2. Defender exclusions" {
    Get-MpPreference |
        Select-Object -ExpandProperty ExclusionPath |
        Sort-Object
}

Invoke-ReportBlock "3. Update Defender signatures" {
    Update-MpSignature
    "Signature update completed or was already current."
}

Invoke-ReportBlock "4. ZIP_SCAN_POLICY_V1 archive scan" {
    Invoke-ZipPolicyScanForTargets -Targets $ScanTargets
}

Invoke-ReportBlock "5. AI_AGENT_SECURITY_RULE_PACK_V1 static scan" {
    Invoke-AiAgentSecurityRulePackForTargets -Targets $ScanTargets
}

Write-Header "6. Custom Defender scan of D: Engel folders"

if (-not $ScanTargets -or $ScanTargets.Count -eq 0) {
    Write-Host "No D: Engel scan targets found." -ForegroundColor Yellow
    Add-Report "No D: Engel scan targets found."
}
else {
    $scanIndex = 0

    foreach ($target in $ScanTargets) {
        $scanIndex++

        Write-Host ""
        Write-Host "[$scanIndex/$($ScanTargets.Count)] Preparing scan target:" -ForegroundColor Cyan
        Write-Host $target -ForegroundColor White

        Add-Report ""
        Add-Report "Scanning target [$scanIndex/$($ScanTargets.Count)]: $target"

        $job = Start-Job -ArgumentList $target -ScriptBlock {
            param($path)
            Start-MpScan -ScanType CustomScan -ScanPath $path
        }

        $scanResult = Wait-JobWithSpinner -Job $job -Target $target

        Add-Report "Scan job state: $($scanResult.State)"
        Add-Report "Elapsed: $($scanResult.Elapsed.ToString('hh\:mm\:ss'))"

        if (-not [string]::IsNullOrWhiteSpace($scanResult.Output)) {
            Add-Report $scanResult.Output
        }

        if ($scanResult.State -eq "Completed") {
            Write-Host "Finished: $target in $($scanResult.Elapsed.ToString('hh\:mm\:ss'))" -ForegroundColor Green
        }
        else {
            Write-Host "Scan ended with state: $($scanResult.State)" -ForegroundColor Yellow
        }
    }
}

Invoke-ReportBlock "7. Defender threat detections" {
    $detections = Get-MpThreatDetection -ErrorAction SilentlyContinue

    if ($detections) {
        $detections |
            Select-Object InitialDetectionTime, LastThreatStatusChangeTime, ThreatID, ThreatStatusID, ActionSuccess, Resources |
            Sort-Object InitialDetectionTime -Descending |
            Format-List
    }
    else {
        "No Defender threat detections returned."
    }
}

Invoke-ReportBlock "8. Startup commands" {
    Get-CimInstance Win32_StartupCommand |
        Select-Object Name, Command, Location, User |
        Sort-Object Location, Name |
        Format-List
}

Invoke-ReportBlock "9. User-writable running process locations" {
    $patterns = "\\Users\\|\\AppData\\|\\Temp\\|\\Downloads\\|\\ProgramData\\|\\Public\\|\\Windows\\Tasks\\"

    Get-Process |
        ForEach-Object {
            $p = $_
            $path = ""
            $company = ""

            try { $path = $p.Path } catch {}
            try {
                if ($p.FileVersionInfo) {
                    $company = $p.FileVersionInfo.CompanyName
                }
            } catch {}

            if ($path -and ($path -match $patterns)) {
                [PSCustomObject]@{
                    Process = $p.ProcessName
                    Id = $p.Id
                    Company = $company
                    Path = $path
                }
            }
        } |
        Sort-Object Path |
        Format-List
}

Invoke-ReportBlock "10. Non-Microsoft scheduled tasks" {
    Get-ScheduledTask |
        Where-Object { $_.TaskPath -notlike "\Microsoft\Windows\*" } |
        Select-Object TaskName, TaskPath, State, Author |
        Sort-Object TaskPath, TaskName |
        Format-Table -AutoSize
}

Invoke-ReportBlock "11. Listening TCP ports" {
    Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
        ForEach-Object {
            $conn = $_
            $proc = Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue

            [PSCustomObject]@{
                LocalAddress = $conn.LocalAddress
                LocalPort = $conn.LocalPort
                ProcessId = $conn.OwningProcess
                ProcessName = if ($proc) { $proc.ProcessName } else { "" }
                ProcessPath = if ($proc) { try { $proc.Path } catch { "" } } else { "" }
            }
        } |
        Sort-Object LocalPort |
        Format-Table -AutoSize
}

Invoke-ReportBlock "12. Recent System warnings/errors, last 7 days" {
    Get-WinEvent -FilterHashtable @{
        LogName = "System"
        StartTime = (Get-Date).AddDays(-7)
    } -ErrorAction SilentlyContinue |
        Where-Object { $_.LevelDisplayName -in "Critical","Error","Warning" } |
        Select-Object TimeCreated, ProviderName, Id, LevelDisplayName, Message -First 80 |
        Format-List
}

Invoke-ReportBlock "13. Final Defender status" {
    Get-MpComputerStatus |
        Select-Object AntivirusEnabled, RealTimeProtectionEnabled, QuickScanAge, FullScanAge, QuickScanEndTime, FullScanEndTime, AntivirusSignatureLastUpdated |
        Format-List
}

Add-Report ""
Add-Report "SCAN COMPLETE: $(Get-Date)"
Add-Report "Report saved to: $Report"

Write-Host ""
Write-Host "============================================================" -ForegroundColor DarkCyan
Write-Host " ENGEL SECURITY SCAN COMPLETE" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor DarkCyan
Write-Host ""
Write-Host "Report saved to:" -ForegroundColor Cyan
Write-Host $Report -ForegroundColor White
Write-Host ""

if (-not $NoOpenReport) {
    Start-Process notepad.exe $Report
}

if (-not $NoPrompt) {
    Read-Host "Press Enter to close this window"
}
