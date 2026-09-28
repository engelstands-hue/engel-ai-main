# Fix C: no-write homes. NEVER use $Home (PowerShell reserved = C:\Users\ziese).
$ErrorActionPreference = "Continue"
$ToolHome = "D:\b.WorkSpace\tool-homes"
$Stage = "D:\b.WorkSpace\archive\c-drive-20260819"
$Log = Join-Path $Stage "move-log.txt"
$Key = Join-Path $env:USERPROFILE ".ssh\engel_ai_main_ct246_ed25519"
$VaultRel = "/mnt/engel-hdd-vault/datasets-archive/laptop-c-drive-20260819"

function Log([string]$msg) {
    $line = "$(Get-Date -Format o)  $msg"
    Write-Output $line
    Add-Content -LiteralPath $Log -Value $line
}

function Robo([string]$src, [string]$dst) {
    if (-not (Test-Path -LiteralPath $src)) { Log "SKIP missing $src"; return 99 }
    New-Item -ItemType Directory -Force -Path $dst | Out-Null
    Log "ROBOCOPY $src -> $dst"
    cmd /c "robocopy `"$src`" `"$dst`" /E /COPY:DAT /R:2 /W:1 /XJ /NFL /NDL /NP /NJH"
    $code = $LASTEXITCODE
    Log "ROBOCOPY exit $code"
    return $code
}

function DropJunction([string]$path) {
    if (-not (Test-Path -LiteralPath $path)) { Log "SKIP drop missing $path"; return }
    $item = Get-Item -LiteralPath $path -Force
    if ($item.Attributes.ToString() -notmatch "ReparsePoint") {
        Log "FAIL $path is not a junction, not dropping"
        return
    }
    Log "RMDIR junction $path"
    cmd /c "rmdir `"$path`""
}

New-Item -ItemType Directory -Force -Path $ToolHome, $Stage, (Join-Path $ToolHome "codex"), (Join-Path $ToolHome "android"), (Join-Path $ToolHome "wsl") | Out-Null
Log "==== retarget homes onto D: tool-homes ===="
Log "C free $((Get-PSDrive C).Free) D free $((Get-PSDrive D).Free)"

# Codex real data currently at C:\Users\ziese\codex, .codex is a C: junction to it
$code = Robo "C:\Users\ziese\codex" (Join-Path $ToolHome "codex")
if ($code -le 7) {
    DropJunction "C:\Users\ziese\.codex"
    cmd /c "mklink /J `"C:\Users\ziese\.codex`" `"$ToolHome\codex`""
    Log "mklink .codex exit $LASTEXITCODE"
    if ((Get-Item "C:\Users\ziese\.codex" -Force).Attributes.ToString() -match "ReparsePoint") {
        Log "DELETE C:\Users\ziese\codex after D: copy"
        Remove-Item -LiteralPath "C:\Users\ziese\codex" -Recurse -Force
    }
} else { Log "FAIL codex copy" }

$code = Robo "C:\Users\ziese\android" (Join-Path $ToolHome "android")
if ($code -le 7) {
    DropJunction "C:\Users\ziese\AppData\Local\Android"
    cmd /c "mklink /J `"C:\Users\ziese\AppData\Local\Android`" `"$ToolHome\android`""
    Log "mklink Android exit $LASTEXITCODE"
    if ((Get-Item "C:\Users\ziese\AppData\Local\Android" -Force).Attributes.ToString() -match "ReparsePoint") {
        Log "DELETE C:\Users\ziese\android after D: copy"
        Remove-Item -LiteralPath "C:\Users\ziese\android" -Recurse -Force
    }
} else { Log "FAIL android copy" }

foreach ($name in @("Ubuntu-22.04", "Ubuntu", "Debian")) {
    $dest = Join-Path $ToolHome "wsl\$name"
    New-Item -ItemType Directory -Force -Path $dest | Out-Null
    Log "WSL move $name -> $dest"
    wsl --manage $name --move $dest
    Log "WSL move $name exit $LASTEXITCODE"
}

$caches = @(
    "C:\Users\ziese\AppData\Local\pip\cache",
    "C:\Users\ziese\AppData\Local\npm-cache",
    "C:\Users\ziese\AppData\Local\pnpm",
    "C:\Users\ziese\AppData\Local\pnpm-cache",
    "C:\Users\ziese\AppData\Local\ms-playwright",
    "C:\Users\ziese\AppData\Local\NVIDIA\DXCache",
    "C:\Users\ziese\AppData\Local\uv"
)
foreach ($c in $caches) {
    if (Test-Path -LiteralPath $c) {
        Log "DELETE cache $c"
        Remove-Item -LiteralPath $c -Recurse -Force
    }
}

if (Test-Path "C:\Users\ziese\AppData\Local\Temp\43y5yj2s") {
    $t = Join-Path $Stage "Temp-43y5yj2s"
    Robo "C:\Users\ziese\AppData\Local\Temp\43y5yj2s" $t | Out-Null
    Remove-Item "C:\Users\ziese\AppData\Local\Temp\43y5yj2s" -Recurse -Force
    Log "archived then deleted Temp-43y5yj2s"
}

if (Test-Path "C:\Program Files\WindowsApps.tmp") {
    $t = Join-Path $Stage "WindowsApps.tmp"
    Robo "C:\Program Files\WindowsApps.tmp" $t | Out-Null
}

Log "C free $((Get-PSDrive C).Free) D free $((Get-PSDrive D).Free)"
Log "==== D: retarget phase done ===="
