<#
Launch real multi-node distributed LoRA training for Engel Chat LLM
All launched from the Engel AI Main laptop (one of the 8GB GPU nodes).

Uses direct python on local GPU + shared-room dispatch (DESKTOP-UE5A6GG) + SSH (730xd CPU).

CONNECTION RULE (you run launcher; make the tunnel "once"):
- The 18777 forward (DESKTOP-UE5A6GG via CT) is set up ONE TIME only.
- Run scripts\Install-EngelMainPersistentAgenticSystem.ps1 once.
  It does one-time key auth (may prompt CT password once) + creates scheduled task "EngelMainServerPersistentLink".
- The task auto-starts the tunnel hidden at every logon (reconnecting, mutex single-instance).
- Daily use: scripts\Start-EngelMainOneSystem.ps1 or the "Engel AI Main - One System.lnk" shortcut.
- This launcher script does NOT create/start/manage any tunnel or SSH to the desktop.
- Desktop dispatch is via drop of work order JSON into D:\b.WorkSpace\Engel App\run\sub_engel_transport\SUB_ENGEL_WORK_ORDERS.
- The optional 127.0.0.1:18777 trigger here only works on the machine that sees the forward; it fails soft and is not required.
- To test forward once manually: ...Start-EngelMainServerChatTunnelPersistent.ps1 -Once

Assumptions:
- CT246 `/mnt/ssd-ai/training` is the fast SSD home for active training.
- CT246 `/mnt/engel-hdd-vault/training-outputs` is the Dell PowerEdge HDD archive.
- Do not use the CT245 offline-vault mount; active training stays on CT246 SSD and archive output goes to Dell HDD.
- Google Drive shared room is how this desktop communicates for jobs.
- Persistent tunnel (install once) for any direct commands/bridges when needed.
#>

$ErrorActionPreference = "Stop"

$ErrorActionPreference = "Stop"

# ====================== CONFIG - EDIT THESE ======================
$SHARED_BASE = "D:\b.WorkSpace\Engel App\shared-730xd-training"   # Local laptop staging. Server-side active training is /mnt/ssd-ai/training/distributed.
$SERVER_SHARED = "/mnt/ssd-ai/training/distributed"  # Linux path on CT246 fast SSD.
$SERVER_ARCHIVE = "/mnt/engel-hdd-vault/training-outputs"  # Dell PowerEdge HDD archive.
$LOCAL_PACKAGE = "D:\b.WorkSpace\Engel App\runtime\engel_lora_training_package"
$TRAIN_VENV_PY = "D:\b.WorkSpace\Engel App\runtime\training-convo-gpu\venv\Scripts\python.exe"

# Other GPU machine (the second 8GB node). Use hostname or IP that this laptop can SSH to.
$OTHER_GPU_HOST = "127.0.0.1"   # DESKTOP-UE5A6GG through CT port 18777
$OTHER_GPU_PORT = 18777
$OTHER_GPU_USER = "root"        # adjust if different user on the desktop
$OTHER_GPU_KEY = "$env:USERPROFILE\.ssh\engel_ai_main_ct246_ed25519"  # use the known key, or the one for sub-engel

# 730xd details (for syncing and optional CPU job)
$SERVER = "192.0.2.50"
$SERVER_PORT = 24622
$SERVER_USER = "root"
$SERVER_KEY = "$env:USERPROFILE\.ssh\engel_ai_main_ct246_ed25519"

# Training params
$BASE_MODEL = "Qwen/Qwen2.5-7B-Instruct"
$MAX_STEPS = 2000
$MAX_LENGTH = 384
$LR = "1.5e-4"

# ================================================================

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$OUTPUT_DIR = "$SHARED_BASE\outputs\multi-node-$timestamp"
$DATASET = "$SHARED_BASE\dataset\engel_standalone_sft.jsonl"
$LOG_DIR = "$SHARED_BASE\logs"
$PACKAGE_ON_SHARED = "$SHARED_BASE\package"

# Server-side paths (Linux)
$SERVER_OUTPUT_DIR = "$SERVER_SHARED/outputs/multi-node-$timestamp"
$SERVER_LOG_DIR = "$SERVER_SHARED/logs"
$SERVER_PACKAGE = "$SERVER_SHARED/package"
$SERVER_CPU_LOG = "$SERVER_LOG_DIR/730xd-cpu-$timestamp.log"

Write-Host "=== Engel Multi-Node Distributed Training Launch (from Laptop) ===" -ForegroundColor Cyan
Write-Host "Shared storage : $SHARED_BASE"
Write-Host "Output dir     : $OUTPUT_DIR"
Write-Host "Master (730xd) : $SERVER"
Write-Host ""

# 1. Ensure directories on 730xd SSD (use Linux paths on the server)
Write-Host "Preparing shared directories on 730xd..."
ssh -i $SERVER_KEY -o BatchMode=yes -p $SERVER_PORT "$SERVER_USER@$SERVER" "
  OFFLINE_CT245_MOUNT='/mnt/'engel-vault
  case '$SERVER_SHARED $SERVER_ARCHIVE' in *"`$OFFLINE_CT245_MOUNT"*) echo 'CT245 offline-vault storage is disabled; refusing training.' >&2; exit 2 ;; esac
  mkdir -p '$SERVER_SHARED/dataset' '$SERVER_OUTPUT_DIR' '$SERVER_LOG_DIR' '$SERVER_PACKAGE' '$SERVER_ARCHIVE/receipts'
"

# 2. Sync the latest training package and dataset to the shared 730xd location
Write-Host "Syncing package and dataset to 730xd SSD..."
New-Item -ItemType Directory -Force -Path "$SHARED_BASE\package", "$SHARED_BASE\dataset", "$LOG_DIR" | Out-Null
# Copy package (code)
robocopy $LOCAL_PACKAGE "$SHARED_BASE\package" /MIR /NFL /NDL /NJH /NJS | Out-Null
# Ensure dataset is there (we updated it earlier)
Copy-Item "$LOCAL_PACKAGE\dataset\engel_standalone_sft.jsonl" -Destination "$SHARED_BASE\dataset\" -Force

# Also rsync via 730xd SSH for Linux side consistency
scp -i $SERVER_KEY -P $SERVER_PORT -r "$LOCAL_PACKAGE" "${SERVER_USER}@${SERVER}:${SERVER_SHARED}/package/" 2>$null | Out-Null

# 3. Dispatch to the OTHER GPU machine (DESKTOP-UE5A6GG) via local Sub-Engel transport.
# The node monitors run\sub_engel_transport and processes work orders in SUB_ENGEL_WORK_ORDERS
Write-Host "Dispatching training work order to DESKTOP-UE5A6GG via local transport..."

$sharedRoom = if ($env:ENGEL_SUB_ENGEL_TRANSPORT_ROOT) { $env:ENGEL_SUB_ENGEL_TRANSPORT_ROOT } else { "D:\b.WorkSpace\Engel App\run\sub_engel_transport" }
$ordersDir = Join-Path $sharedRoom "SUB_ENGEL_WORK_ORDERS"
New-Item -ItemType Directory -Force -Path $ordersDir | Out-Null

# Ensure fresh package is available at the location referenced by the work order (desktop reads directly from its G: view)
$desktopPackageDir = Join-Path $sharedRoom "training-packages\convo-lora-20260701"
New-Item -ItemType Directory -Force -Path $desktopPackageDir | Out-Null
Write-Host "Syncing current training package to shared room for desktop: $desktopPackageDir"
robocopy $LOCAL_PACKAGE $desktopPackageDir /MIR /NFL /NDL /NJH /NJS /R:1 /W:1 | Out-Null
# Also ensure dataset subdir is explicit
Copy-Item "$LOCAL_PACKAGE\dataset\engel_standalone_sft.jsonl" -Destination (Join-Path $desktopPackageDir "dataset") -Force -ErrorAction SilentlyContinue

$woId = "TRAIN-CONVO-LORA-DESKTOP-UE5A6GG-$(Get-Date -Format 'yyyyMMddTHHmmssZ')"
$workOrder = @{
    schema = "engel_sub_engel_work_order_v1"
    id = $woId
    created_at_utc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    created_by = "Engel AI Main / Laptop Launcher"
    target = "windows_sub_engel"
    target_node = @{ node_id = "DESKTOP-UE5A6GG"; hostname = "DESKTOP-UE5A6GG"; label = "Windows Sub-Engel Node - 8GB GPU for LoRA training" }
    job_type = "run_lora_training"
    order_text = @"
Run the conversational (real-feel) LoRA training on your local 8GB CUDA GPU.

Package is ready in the shared room at: training-packages/convo-lora-20260701

EASIEST: Double-click or run:
  .\run_training_on_this_desktop.ps1

Or manually (from inside the package dir):
  python train_engel_lora.py --base-model Qwen/Qwen2.5-7B-Instruct --dataset dataset/engel_standalone_sft.jsonl --output-dir [path on 730xd SSD or G:\...outputs] --max-steps $MAX_STEPS --max-length $MAX_LENGTH --lr $LR

The runner script sets up logging and tries to save adapters + receipt back toward SUB_ENGEL_SENT_WORK.

Use your local GPU (CUDA). Provide proof (log + adapter files + GPU stats if possible).
Proof required.
"@
    shared_room = $sharedRoom
    expected_return_folder = (Join-Path $sharedRoom "SUB_ENGEL_SENT_WORK")
    proof_required = $true
    package_path = $desktopPackageDir
    status = "ready_for_sub_engel_import"
    lane = "Google Drive shared room"
} | ConvertTo-Json -Depth 5

$woPath = Join-Path $ordersDir "$woId.json"
$workOrder | Set-Content -LiteralPath $woPath -Encoding UTF8
Write-Output "Work order dropped for DESKTOP-UE5A6GG: $woPath"

# Optional: trigger processing via the node's HTTP relay (only useful if 127.0.0.1:18777 is forwarded to you locally)
# This launcher does not start the tunnel. If not available, desktop will pick up from polling the shared folder on its own schedule.
try {
  $cmdBody = @{ action = "shared_room.process_pending_work_orders"; limit = 5 } | ConvertTo-Json
  $resp = Invoke-WebRequest -Uri "http://127.0.0.1:18777/node/command" -Method POST -Body $cmdBody -ContentType "application/json" -TimeoutSec 5 -UseBasicParsing -ErrorAction Stop
  Write-Output "Triggered process_pending on desktop via relay: $($resp.Content)"
} catch {
  Write-Output "Could not auto-trigger via 127.0.0.1:18777 (expected if tunnel not listening on this host; desktop polls shared room directly): $($_.Exception.Message)"
}

# 4. Launch locally on this laptop (node 0) + 730xd CPU in parallel (desktop is async via shared room)
$localLog = "$LOG_DIR\node0-$timestamp.log"
$cpuLog   = "$LOG_DIR\730xd-cpu-$timestamp.log"
New-Item -ItemType Directory -Force -Path $LOG_DIR | Out-Null

Write-Host "Starting local GPU training (node 0) as background job on this laptop..."
$localJob = Start-Job -ScriptBlock {
    param($py, $script, $base, $ds, $out, $steps, $len, $lr, $log)
    & $py $script --base-model $base --dataset $ds --output-dir $out --max-steps $steps --max-length $len --lr $lr *>&1 | Tee-Object -FilePath $log
} -ArgumentList $TRAIN_VENV_PY, "$SHARED_BASE\package\train_engel_lora.py", $BASE_MODEL, $DATASET, $OUTPUT_DIR, $MAX_STEPS, $MAX_LENGTH, $LR, $localLog

Write-Host "Also starting CPU-only job on 730xd (parallel, lower steps)..."
ssh -i $SERVER_KEY -o BatchMode=yes -p $SERVER_PORT "$SERVER_USER@$SERVER" "
  nohup python3 $SERVER_SHARED/package/train_engel_lora.py \
    --base-model '$BASE_MODEL' \
    --dataset '$SERVER_SHARED/package/dataset/engel_standalone_sft.jsonl' \
    --output-dir '$SERVER_SHARED/outputs/730xd-cpu' \
    --max-steps 500 \
    --max-length 256 \
    --lr '$LR' \
    > '$SERVER_CPU_LOG' 2>&1 &
  echo '730xd CPU job started. Log on 730xd: $SERVER_CPU_LOG'
" 2>$null | Out-Null

Write-Host ""
Write-Host "=== Dispatched (local GPU job + desktop via shared room + 730xd CPU) ===" -ForegroundColor Green
Write-Host "Local job (this laptop GPU): Job Id $($localJob.Id)  Log: $localLog"
Write-Host "Desktop (8GB): work order $woId  (polls G: shared room; results -> SUB_ENGEL_SENT_WORK)"
Write-Host "730xd CPU: launched via SSH nohup. Log path on server: $SERVER_CPU_LOG"
Write-Host ""
Write-Host "Monitor:"
Write-Host "  Receive-Job $($localJob.Id) -Keep -Wait"
Write-Host "  Get-Content $localLog -Wait -Tail 20"
Write-Host "  Get-Content (Join-Path '$LOG_DIR' '730xd-cpu-$timestamp.log') -Wait -Tail 10"
Write-Host ""
Write-Host "When all done, copy best adapter(s) to the 730xd SSD location used by the Chat LLM."
Write-Host "Desktop results will appear as *.done.json under D:\b.WorkSpace\Engel App\run\sub_engel_transport\SUB_ENGEL_SENT_WORK"
