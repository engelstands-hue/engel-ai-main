$ErrorActionPreference = "Stop"

$ZipPath = "D:\Claw3D-main.zip"
$EngelRoot = "D:\b.WorkSpace\Engel App"
$StageRoot = "D:\EngelTools\claw3d_to_engel_stage"
$SourceRoot = Join-Path $StageRoot "source"
$SanitizedRoot = Join-Path $StageRoot "sanitized"
$ReportRoot = Join-Path $EngelRoot "reports\codex_bridge"
$ReportPath = Join-Path $ReportRoot "CLAW3D_TO_ENGEL_STAGE_REPORT.md"

if (!(Test-Path $ZipPath)) { throw "Missing source zip: $ZipPath" }
if (!(Test-Path $EngelRoot)) { throw "Missing Engel root: $EngelRoot" }

New-Item -ItemType Directory -Force -Path $StageRoot, $ReportRoot | Out-Null
Remove-Item -Recurse -Force $SourceRoot, $SanitizedRoot -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $SourceRoot, $SanitizedRoot | Out-Null

Expand-Archive -LiteralPath $ZipPath -DestinationPath $SourceRoot -Force
Copy-Item -Path (Join-Path $SourceRoot "*") -Destination $SanitizedRoot -Recurse -Force

$textExtensions = @(
  ".py", ".pyw", ".txt", ".md", ".json", ".jsonc", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".xml",
  ".html", ".htm", ".css", ".scss", ".js", ".jsx", ".ts", ".tsx", ".vue", ".svelte",
  ".cs", ".csproj", ".sln", ".props", ".targets", ".xaml", ".resx",
  ".kt", ".kts", ".java", ".gradle", ".properties", ".bat", ".ps1", ".sh", ".env.example"
)

$brandPatterns = @("Claw3D", "Claw 3D", "CLAW3D", "claw3d", "claw_3d", "claw-3d")
$riskyPatterns = @(
  "openai", "anthropic", "gemini", "ollama", "localhost:11434", "api_key", "apikey", "Authorization:",
  "requests.get", "requests.post", "httpx", "aiohttp", "fetch(", "axios", "WebSocket", "socket.io",
  "schedule.", "while True", "BackgroundService", "Thread(", "Task.Run", "cron", "celery", "autonomous"
)

$sourceBrandHits = @()
foreach ($pattern in $brandPatterns) {
  $hits = Get-ChildItem -Path $SourceRoot -Recurse -File -ErrorAction SilentlyContinue |
    Select-String -Pattern $pattern -SimpleMatch -ErrorAction SilentlyContinue
  $sourceBrandHits += $hits
}

$riskyHits = @()
foreach ($pattern in $riskyPatterns) {
  $hits = Get-ChildItem -Path $SourceRoot -Recurse -File -ErrorAction SilentlyContinue |
    Select-String -Pattern $pattern -SimpleMatch -ErrorAction SilentlyContinue
  $riskyHits += $hits
}

Get-ChildItem -Path $SanitizedRoot -Recurse -File | ForEach-Object {
  $file = $_.FullName
  $ext = $_.Extension.ToLowerInvariant()
  if ($textExtensions -contains $ext) {
    $content = Get-Content -LiteralPath $file -Raw -ErrorAction SilentlyContinue
    if ($null -ne $content) {
      $updated = $content
      $updated = $updated -replace "Claw 3D", "Engel"
      $updated = $updated -replace "Claw3D", "Engel"
      $updated = $updated -replace "CLAW3D", "ENGEL"
      $updated = $updated -replace "claw3d", "engel"
      $updated = $updated -replace "claw_3d", "engel"
      $updated = $updated -replace "claw-3d", "engel"
      if ($updated -ne $content) {
        Set-Content -LiteralPath $file -Value $updated -Encoding UTF8
      }
    }
  }
}

Get-ChildItem -Path $SanitizedRoot -Recurse -Force | Sort-Object FullName -Descending | ForEach-Object {
  $name = $_.Name
  $newName = $name
  $newName = $newName -replace "Claw 3D", "Engel"
  $newName = $newName -replace "Claw3D", "Engel"
  $newName = $newName -replace "CLAW3D", "ENGEL"
  $newName = $newName -replace "claw3d", "engel"
  $newName = $newName -replace "claw_3d", "engel"
  $newName = $newName -replace "claw-3d", "engel"
  if ($newName -ne $name) {
    Rename-Item -LiteralPath $_.FullName -NewName $newName -ErrorAction Stop
  }
}

$remainingStageBrandHits = @()
foreach ($pattern in $brandPatterns) {
  $hits = Get-ChildItem -Path $SanitizedRoot -Recurse -File -ErrorAction SilentlyContinue |
    Select-String -Pattern $pattern -SimpleMatch -ErrorAction SilentlyContinue
  $remainingStageBrandHits += $hits
}

$projectFiles = Get-ChildItem -Path $SanitizedRoot -Recurse -File -Include *.sln,*.csproj,*.vcxproj,*.fsproj,*.vbproj,package.json,pyproject.toml,requirements.txt,*.gradle,*.kts,CMakeLists.txt -ErrorAction SilentlyContinue
$uiCandidates = Get-ChildItem -Path $SanitizedRoot -Recurse -File -ErrorAction SilentlyContinue |
  Where-Object { $_.FullName -match "(?i)(ui|gui|view|component|window|dashboard|office|agent|worker|desk|task|research)" }

$report = @()
$report += "# Claw3D to Engel staging report"
$report += ""
$report += "Status: STAGED_ONLY"
$report += "Source zip: $ZipPath"
$report += "Engel root: $EngelRoot"
$report += "Sanitized staging root: $SanitizedRoot"
$report += ""
$report += "## Source branding hits"
$report += "Count: $($sourceBrandHits.Count)"
$report += $sourceBrandHits | Select-Object -First 200 | ForEach-Object { "- $($_.Path):$($_.LineNumber): $($_.Line.Trim())" }
$report += ""
$report += "## Remaining branding hits in sanitized staging"
$report += "Count: $($remainingStageBrandHits.Count)"
$report += $remainingStageBrandHits | Select-Object -First 200 | ForEach-Object { "- $($_.Path):$($_.LineNumber): $($_.Line.Trim())" }
$report += ""
$report += "## Risky source patterns to review before merge"
$report += "Count: $($riskyHits.Count)"
$report += $riskyHits | Select-Object -First 300 | ForEach-Object { "- $($_.Path):$($_.LineNumber): $($_.Line.Trim())" }
$report += ""
$report += "## Project/build files found"
$report += $projectFiles | ForEach-Object { "- $($_.FullName)" }
$report += ""
$report += "## UI/office/agent/worker/research candidates"
$report += $uiCandidates | Select-Object -First 300 | ForEach-Object { "- $($_.FullName)" }
$report += ""
$report += "## Next step"
$report += "Review candidates, then copy only selected sanitized files into Engel App using Engel names. Do not copy risky provider/network/autonomy code."

Set-Content -LiteralPath $ReportPath -Value ($report -join "`r`n") -Encoding UTF8
Write-Host "Staging complete: $SanitizedRoot"
Write-Host "Report: $ReportPath"
