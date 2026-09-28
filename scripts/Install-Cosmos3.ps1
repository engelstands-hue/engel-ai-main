param(
    [ValidateSet("Models", "DatasetMetadata", "Datasets", "All")]
    [string]$Mode = "Models",
    [string]$ModelRoot = "/opt/engel/models-active/cosmos3",
    [string]$DatasetRoot = "/mnt/engel-hdd-vault/datasets/cosmos3",
    [string]$PythonExe = "",
    [string]$HfExe = "",
    [string]$HfHome = "/opt/engel/cache/hf-cache",
    [string]$PipCache = "/opt/engel/cache/pip-cache",
    [int]$MaxWorkers = 4,
    [switch]$AllowHugeDatasets,
    [switch]$InstallPythonHelpers
)

$ErrorActionPreference = "Stop"

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

function Resolve-EngelPath {
    param(
        [string]$Path,
        [string]$Label
    )
    if ([string]::IsNullOrWhiteSpace($Path)) {
        throw "$Label cannot be empty"
    }
    $full = [System.IO.Path]::GetFullPath($Path)
    if ($full.StartsWith("C:\", [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "$Label resolved to C:, which is reserved for OS only: $full"
    }
    return $full
}

if ([string]::IsNullOrWhiteSpace($PythonExe)) {
    $PythonExe = Join-Path (Split-Path -Parent $ScriptRoot) "runtime\python310\python.exe"
}
if ([string]::IsNullOrWhiteSpace($HfExe)) {
    $HfExe = Join-Path (Split-Path -Parent $ScriptRoot) "runtime\python310\Scripts\hf.exe"
}

$PythonExe = Resolve-EngelPath $PythonExe "PythonExe"
$HfExe = Resolve-EngelPath $HfExe "HfExe"
$ModelRoot = Resolve-EngelPath $ModelRoot "ModelRoot"
$DatasetRoot = Resolve-EngelPath $DatasetRoot "DatasetRoot"
$HfHome = Resolve-EngelPath $HfHome "HfHome"
$PipCache = Resolve-EngelPath $PipCache "PipCache"

$Models = @(
    @{ Repo = "nvidia/Cosmos3-Nano"; Gb = 32.50 },
    @{ Repo = "nvidia/Cosmos3-Super"; Gb = 125.36 },
    @{ Repo = "nvidia/Cosmos3-Super-Image2Video"; Gb = 121.67 },
    @{ Repo = "nvidia/Cosmos3-Super-Text2Image"; Gb = 123.43 },
    @{ Repo = "nvidia/Cosmos3-Nano-Policy-DROID"; Gb = 30.68 }
)

$Datasets = @(
    @{ Repo = "nvidia/PhysicalAI-WorldModel-Synthetic-Digital-Human-Scenes"; Gb = 159384.04 },
    @{ Repo = "nvidia/PhysicalAI-WorldModel-Synthetic-Physical-Interaction-Scenes"; Gb = 15308.74 },
    @{ Repo = "nvidia/PhysicalAI-WorldModel-Synthetic-Embodied-Robot-Scenes"; Gb = 1942.04 },
    @{ Repo = "nvidia/PhysicalAI-WorldModel-Synthetic-Warehouse-Operations-Scenes"; Gb = 22421.41 },
    @{ Repo = "nvidia/PhysicalAI-WorldModel-Synthetic-Autonomous-Driving-Scenarios"; Gb = 2334.41 },
    @{ Repo = "nvidia/LIBERO_LeRobot_v3"; Gb = 4.15 },
    @{ Repo = "nvidia/BridgeData2_LeRobot_v3"; Gb = 84.26 },
    @{ Repo = "nvidia/Cosmos-HumanEval-v1"; Gb = 0.00 },
    @{ Repo = "nvidia/BridgeData2-Subset-Synthetic-Captions"; Gb = 0.61 }
)

function Require-Command {
    param([string]$Name)
    $cmd = Get-Command $Name -ErrorAction SilentlyContinue
    if (-not $cmd) {
        throw "Required command not found: $Name"
    }
}

function Repo-Leaf {
    param([string]$Repo)
    return (($Repo -split "/")[-1])
}

function Invoke-HfDownload {
    param(
        [string]$Repo,
        [ValidateSet("model", "dataset", "space")]
        [string]$RepoType,
        [string]$Root,
        [switch]$MetadataOnly
    )
    $target = Join-Path $Root (Repo-Leaf $Repo)
    New-Item -ItemType Directory -Force -Path $target | Out-Null

    $args = @(
        "download",
        $Repo,
        "--repo-type", $RepoType,
        "--local-dir", $target,
        "--max-workers", "$MaxWorkers"
    )

    if ($MetadataOnly) {
        $args += @(
            "--include", "*.json",
            "--include", "*.md",
            "--include", "*.txt",
            "--include", "*.py",
            "--include", "*.yaml",
            "--include", "*.yml",
            "--include", "*.csv",
            "--include", "*.jsonl",
            "--include", "*.jsonld",
            "--include", "*.parquet.metadata",
            "--exclude", "*.safetensors",
            "--exclude", "*.bin",
            "--exclude", "*.parquet",
            "--exclude", "*.tar",
            "--exclude", "*.tar.gz",
            "--exclude", "*.mp4",
            "--exclude", "*.webm",
            "--exclude", "*.jpg",
            "--exclude", "*.jpeg",
            "--exclude", "*.png"
        )
    }

    Write-Host ""
    Write-Host "== hf $RepoType download: $Repo =="
    Write-Host "Target: $target"
    & $HfExe @args
    if ($LASTEXITCODE -ne 0) {
        throw "hf download failed for $Repo with exit code $LASTEXITCODE"
    }
}

function Save-HfRepoMetadata {
    param(
        [string]$Repo,
        [ValidateSet("model", "dataset", "space")]
        [string]$RepoType,
        [string]$Root
    )
    $target = Join-Path $Root (Repo-Leaf $Repo)
    New-Item -ItemType Directory -Force -Path $target | Out-Null
    $kind = if ($RepoType -eq "dataset") { "datasets" } elseif ($RepoType -eq "space") { "spaces" } else { "models" }
    $url = "https://huggingface.co/api/$kind/$Repo" + "?blobs=true"
    $outFile = Join-Path $target "huggingface_repo_api.json"

    Write-Host ""
    Write-Host "== hf $RepoType metadata: $Repo =="
    Write-Host "Target: $outFile"
    $data = Invoke-RestMethod -Uri $url -Method Get -TimeoutSec 120
    $data | ConvertTo-Json -Depth 100 | Set-Content -LiteralPath $outFile -Encoding UTF8
}

if (-not (Test-Path -LiteralPath $PythonExe)) {
    throw "Engel-local Python not found: $PythonExe"
}
if (-not (Test-Path -LiteralPath $HfExe) -and -not $InstallPythonHelpers) {
    throw "Engel-local Hugging Face CLI not found: $HfExe. Run with -InstallPythonHelpers first."
}

New-Item -ItemType Directory -Force -Path $HfHome | Out-Null
New-Item -ItemType Directory -Force -Path $PipCache | Out-Null

$env:PYTHONNOUSERSITE = "1"
$env:PYTHONUSERBASE = (Resolve-EngelPath (Join-Path (Split-Path -Parent $HfHome) "python-userbase") "PYTHONUSERBASE")
$env:PIP_CACHE_DIR = $PipCache
$env:HF_HOME = $HfHome
$env:HF_HUB_CACHE = Join-Path $HfHome "hub"
$env:HF_XET_CACHE = Join-Path $HfHome "xet"
$env:HF_ASSETS_CACHE = Join-Path $HfHome "assets"
$env:HF_DATASETS_CACHE = Join-Path $DatasetRoot ".cache\huggingface\datasets"
$env:TRANSFORMERS_CACHE = Join-Path $HfHome "transformers"
$env:HF_XET_HIGH_PERFORMANCE = "1"

Write-Host "Engel-local Python: $PythonExe"
Write-Host "Engel-local hf CLI: $HfExe"
Write-Host "HF_HOME:            $env:HF_HOME"
Write-Host "PIP_CACHE_DIR:      $env:PIP_CACHE_DIR"

& $PythonExe --version | Out-Host

if ($InstallPythonHelpers) {
    Write-Host "Installing/updating Cosmos3 Python download/runtime helper packages into Engel-local Python..."
    & $PythonExe -m pip install --upgrade huggingface_hub hf_transfer safetensors diffusers transformers accelerate sentencepiece
    if ($LASTEXITCODE -ne 0) {
        throw "pip install helper packages failed with exit code $LASTEXITCODE"
    }
    if (-not (Test-Path -LiteralPath $HfExe)) {
        throw "Engel-local Hugging Face CLI not found after helper install: $HfExe"
    }
}

New-Item -ItemType Directory -Force -Path $ModelRoot | Out-Null
New-Item -ItemType Directory -Force -Path $DatasetRoot | Out-Null

$modelGb = ($Models | ForEach-Object { [double]$_.Gb } | Measure-Object -Sum).Sum
$datasetGb = ($Datasets | ForEach-Object { [double]$_.Gb } | Measure-Object -Sum).Sum
Write-Host "Cosmos3 model total:   $([math]::Round($modelGb, 2)) GB"
Write-Host "Cosmos3 dataset total: $([math]::Round($datasetGb, 2)) GB"

if ($Mode -eq "Models" -or $Mode -eq "All") {
    foreach ($row in $Models) {
        Invoke-HfDownload -Repo $row.Repo -RepoType model -Root $ModelRoot
    }
}

if ($Mode -eq "DatasetMetadata" -or ($Mode -eq "All" -and -not $AllowHugeDatasets)) {
    foreach ($row in $Datasets) {
        Save-HfRepoMetadata -Repo $row.Repo -RepoType dataset -Root $DatasetRoot
    }
}

if ($Mode -eq "Datasets" -or ($Mode -eq "All" -and $AllowHugeDatasets)) {
    if (-not $AllowHugeDatasets) {
        throw "Full Cosmos3 datasets are over 200 TB. Re-run with -AllowHugeDatasets only if the target storage is intentionally prepared."
    }
    foreach ($row in $Datasets) {
        Invoke-HfDownload -Repo $row.Repo -RepoType dataset -Root $DatasetRoot
    }
}

Write-Host ""
Write-Host "Cosmos3 install/download step complete for mode: $Mode"
