# Engel quick merge packet: Claw3D zip -> Engel App

## Job
Deep-search `D:\Claw3D-main.zip` for every occurrence of `Claw3D`, `Claw 3D`, `claw3d`, and related project identifiers, replace public-facing/internal references with `Engel`, and selectively merge any useful autonomous-agent office/worker/GUI structure into `D:\b.WorkSpace\Engel App` without importing the Claw3D name, external API/provider dependencies, persistent background autonomy, or unsafe write behavior.

## Hard guardrails
- Do not transfer the Claw3D name into Engel App.
- No outsourced API/provider behavior.
- No new network calls, cloud API clients, paid providers, telemetry, browser automation, or remote model hooks.
- No persistent background autonomous loops.
- No trusted-memory writes or source edits by autonomous workers unless already approved by Engel’s verifier path.
- Treat imported autonomous agents as local UI/structural concepts only.
- Research workers should be visible local worker/desk entities linked to a research project/task, not live external agents.
- Preserve Engel App identity and existing safety contracts.
- Stage first, review diffs, then copy only selected assets/code.

## Target assumptions
- Source zip: `D:\Claw3D-main.zip`
- Engel target repo: `D:\b.WorkSpace\Engel App`
- Staging folder: `D:\EngelTools\claw3d_to_engel_stage`
- Report folder: `D:\b.WorkSpace\Engel App\reports\codex_bridge`

## One-shot Codex / Visual Studio prompt

```text
You are working locally on the Engel App repository at D:\b.WorkSpace\Engel App.

Job:
Import useful visual and structural ideas from D:\Claw3D-main.zip into Engel App while fully sanitizing Claw3D branding. Deep-search the zip contents, project files, Python files, configs, docs, and assets for Claw3D / Claw 3D / claw3d identifiers and replace with Engel or remove when not appropriate. Merge only pieces that enhance Engel visually and structurally: autonomous agent office, worker desks, research-worker/task linkage, local dashboard concepts, and UI layout ideas.

Hard constraints:
1. Do not leave any Claw3D / Claw 3D / claw3d branding in Engel App.
2. Do not add outsourced APIs, provider calls, cloud model hooks, telemetry, browser automation, or network behavior.
3. Do not enable background autonomous loops, persistent workers, auto-run schedulers, trusted-memory writes, source mutation, queue mutation, or ALIVE_STATE writes.
4. Imported autonomous agents must be represented as local, bounded UI/structure only.
5. Research workers' desks must link to their local research project/task status.
6. Use staging and reports. Do not overwrite unrelated Engel code blindly.

Implementation plan:
1. Expand D:\Claw3D-main.zip into D:\EngelTools\claw3d_to_engel_stage\source.
2. Inventory source structure, language/framework, project files, and UI assets.
3. Run a deep text scan for Claw3D variants and risky API/network/autonomy patterns.
4. Produce a sanitized staging copy under D:\EngelTools\claw3d_to_engel_stage\sanitized.
5. Rename paths/files containing Claw3D/claw3d to Engel/engel where safe.
6. Replace text occurrences in text-like files only; do not corrupt binaries.
7. Identify merge candidates:
   - autonomous office layout
   - worker/agent desk model
   - research project/task linking structure
   - local dashboard/view components
   - reusable visual assets without branding
8. Integrate only selected pieces into Engel App using Engel naming and safety patterns.
9. Add a local UI model if needed, for example:
   - `ResearchWorkerDesk`
   - `ResearchOfficeState`
   - `ResearchProjectLink`
   - `WorkerTaskStatus`
   These must be local data/view models, not live autonomous workers.
10. Add/adjust Engel routes or UI panels only as read-only/status-only unless existing Engel architecture already allows more.
11. Run verification:
   - Python compile checks for touched Python files
   - existing Engel verifier scripts if present
   - search target repo for forbidden Claw3D names
   - search target repo for new provider/network/API/autonomy patterns
   - run app smoke command available in repo
12. Write `D:\b.WorkSpace\Engel App\reports\codex_bridge\CLAW3D_TO_ENGEL_MERGE_REPORT.md`.

Definition of done:
- Useful office/agent/worker visual structure is merged or staged with clear next steps.
- Worker desks link to research project/task state locally.
- No Claw3D branding remains in Engel App except in the merge report audit section if necessary.
- No outsourced API/provider/network behavior is added.
- No unsafe autonomy/background worker behavior is added.
- Build/verifier checks pass or failures are clearly reported with exact next fix.

Report format:
Status: COMPLETE / PARTIAL / BLOCKED
Source zip inspected:
Files copied/changed:
Branding replacements made:
Visual/structural enhancements merged:
Research worker desk/task linkage added:
Verification commands:
Results:
Forbidden-pattern scan results:
Risks:
Next safe step:
```

## Recommended PowerShell staging script

Save as `D:\EngelTools\merge_claw3d_to_engel_stage.ps1` and run from PowerShell. It stages and sanitizes only; it does not blindly overwrite Engel App.

```powershell
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

# Replace branding in text-like files in sanitized staging copy.
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

# Rename files/directories in sanitized copy after content replacement.
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
```

## Visual/structural merge target

Suggested Engel-side structure if the app is Python-based:

```text
engel_app.py
engel_research_brain_v2.py
ui/
  research_office/
    __init__.py
    office_state.py
    worker_desk.py
    research_project_link.py
    office_view.py
reports/codex_bridge/
  CLAW3D_TO_ENGEL_MERGE_REPORT.md
```

Suggested local model shape:

```python
from dataclasses import dataclass
from typing import Literal

WorkerStatus = Literal["idle", "reviewing", "searching_local", "summarizing", "blocked", "complete"]

@dataclass(frozen=True)
class ResearchProjectLink:
    project_id: str
    title: str
    local_report_path: str | None = None
    task_summary: str = ""

@dataclass(frozen=True)
class ResearchWorkerDesk:
    worker_id: str
    display_name: str
    role: str
    status: WorkerStatus
    project: ResearchProjectLink | None
    last_note: str = ""
```

Keep this display-only unless a later approved Engel task explicitly wires it into real research execution.

## Final scan commands after merge

```powershell
cd "D:\b.WorkSpace\Engel App"

# Must return no matches except the merge report audit section, if you decide to keep it.
Get-ChildItem -Recurse -File | Select-String -Pattern "Claw3D","Claw 3D","claw3d","claw_3d","claw-3d" -SimpleMatch

# Review any new network/provider/autonomy patterns.
Get-ChildItem -Recurse -File -Include *.py,*.js,*.ts,*.tsx,*.cs,*.json,*.md,*.ps1,*.bat | Select-String -Pattern "openai","anthropic","gemini","ollama","localhost:11434","api_key","requests.post","requests.get","fetch(","axios","while True","BackgroundService","cron","celery" -SimpleMatch

# Compile Python if applicable.
python -m py_compile engel_app.py engel_research_brain_v2.py

# Run existing Engel verifiers if present.
Get-ChildItem .\tools\verify_*.py | ForEach-Object { python $_.FullName }
```
