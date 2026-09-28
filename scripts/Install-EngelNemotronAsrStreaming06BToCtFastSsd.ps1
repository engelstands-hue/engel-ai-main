[CmdletBinding()]
param(
    [string]$CtHost = "192.0.2.50",
    [int]$CtPort = 24622,
    [string]$CtUser = "root",
    [string]$RuntimeRoot = "/opt/engel",
    [string]$KeyPath = (Join-Path $env:USERPROFILE ".ssh\engel_ai_main_ct246_ed25519"),
    [switch]$SkipRuntimeDeps
)

$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$ReceiptDir = Join-Path $ProjectRoot "reports\ct_sync"
$RuntimeDir = Join-Path $ProjectRoot "runtime\ct_fast_ssd_model_sync"
$Stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$ResolvedKeyPath = [System.IO.Path]::GetFullPath($KeyPath)
$SshExe = "C:\Windows\System32\OpenSSH\ssh.exe"
$ScpExe = "C:\Windows\System32\OpenSSH\scp.exe"
$RemoteInstallerPath = "$RuntimeRoot/cache/install_nemotron_asr_streaming_06b_$Stamp.py"
$LocalInstallerPath = Join-Path $RuntimeDir "install_nemotron_asr_streaming_06b_$Stamp.py"
$ReceiptPath = Join-Path $ReceiptDir "ENGEL_NEMOTRON_ASR_STREAMING_06B_INSTALL_$Stamp.json"

if (-not (Test-Path -LiteralPath $ResolvedKeyPath -PathType Leaf)) {
    throw "Engel CT SSH key missing: $ResolvedKeyPath"
}
if (-not (Test-Path -LiteralPath $SshExe -PathType Leaf)) {
    throw "OpenSSH ssh.exe missing: $SshExe"
}
if (-not (Test-Path -LiteralPath $ScpExe -PathType Leaf)) {
    throw "OpenSSH scp.exe missing: $ScpExe"
}

New-Item -ItemType Directory -Force -Path $ReceiptDir, $RuntimeDir | Out-Null

function Write-Utf8NoBom {
    param([string]$Path, [string]$Text)
    [System.IO.File]::WriteAllText($Path, $Text, [System.Text.UTF8Encoding]::new($false))
}

$installRuntimeDeps = if ($SkipRuntimeDeps) { "0" } else { "1" }

$remoteInstaller = @'
#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO_ID = "nvidia/nemotron-3.5-asr-streaming-0.6b"
MODEL_ID = "nemotron-3.5-asr-streaming-0.6b"
RUNTIME_ROOT = Path("__RUNTIME_ROOT__")
STAMP = "__STAMP__"
INSTALL_RUNTIME_DEPS = "__INSTALL_RUNTIME_DEPS__" == "1"

MODELS_ACTIVE = RUNTIME_ROOT / "models-active"
MODEL_DIR = MODELS_ACTIVE / "asr" / MODEL_ID
MEMORY_MODELS = RUNTIME_ROOT / "memory" / "models"
REPORTS = RUNTIME_ROOT / "reports"
CACHE = RUNTIME_ROOT / "cache"
SERVICE_DROPIN_DIR = Path("/etc/systemd/system/engel-main-chat.service.d")
SERVICE_DROPIN = SERVICE_DROPIN_DIR / "50-nemotron-asr-streaming.conf"
INVENTORY = MEMORY_MODELS / "ENGEL_CT_FAST_SSD_MODEL_INVENTORY.json"
ASR_MANIFEST = MEMORY_MODELS / "ENGEL_ASR_MODEL_MANIFEST.json"
MODEL_MANIFEST = MEMORY_MODELS / "ENGEL_NEMOTRON_ASR_STREAMING_06B_MANIFEST.json"
STATUS_TOOL = RUNTIME_ROOT / "tools" / "engel_nemotron_asr_status.py"
REPORT = REPORTS / f"ENGEL_NEMOTRON_ASR_STREAMING_06B_INSTALL_{STAMP}.json"
REQUIRED_FILES = [
    "README.md",
    "config.json",
    "generation_config.json",
    "processor_config.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "model.safetensors",
    "nemotron-3.5-asr-streaming-0.6b.nemo",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def fail(message: str) -> None:
    raise RuntimeError(message)


def run(command: list[str], *, check: bool = True, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    merged_env = dict(os.environ)
    if env:
        merged_env.update(env)
    return subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=check, env=merged_env)


def read_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def path_is_vault(path: Path) -> bool:
    text = str(path.resolve(strict=False)).replace("\\", "/").lower()
    offline_ct245_mount = "/mnt/" + "engel-vault"
    return text.startswith(offline_ct245_mount) or (offline_ct245_mount + "/") in text


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def install_download_deps() -> tuple[bool, str]:
    packages = ["huggingface_hub[hf_xet]>=0.33.0"]
    env = {"PIP_DISABLE_PIP_VERSION_CHECK": "1"}
    try:
        result = run([sys.executable, "-m", "pip", "install", "--upgrade", "--prefer-binary", *packages], env=env)
        return True, result.stdout[-4000:]
    except subprocess.CalledProcessError as exc:
        return False, exc.stdout[-4000:] if exc.stdout else str(exc)


def install_runtime_deps() -> dict:
    status: dict[str, object] = {"requested": INSTALL_RUNTIME_DEPS, "ok": False, "steps": []}
    if not INSTALL_RUNTIME_DEPS:
        status["ok"] = None
        status["message"] = "runtime dependency install skipped"
        return status

    apt_packages = ["ffmpeg", "libsndfile1"]
    try:
        apt_update = run(["apt-get", "update"], check=False)
        status["steps"].append({"command": "apt-get update", "returncode": apt_update.returncode, "tail": apt_update.stdout[-2000:]})
        apt_install = run(["apt-get", "install", "-y", "--no-install-recommends", *apt_packages], check=False)
        status["steps"].append({"command": "apt-get install ffmpeg libsndfile1", "returncode": apt_install.returncode, "tail": apt_install.stdout[-2000:]})
    except Exception as exc:
        status["steps"].append({"command": "apt runtime deps", "error": str(exc)})

    pip_env = {"PIP_DISABLE_PIP_VERSION_CHECK": "1"}
    try:
        torch = run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--upgrade",
                "--prefer-binary",
                "--index-url",
                "https://download.pytorch.org/whl/cpu",
                "torch",
            ],
            check=False,
            env=pip_env,
        )
        status["steps"].append({"command": "pip install torch cpu", "returncode": torch.returncode, "tail": torch.stdout[-3000:]})
        rest = run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--upgrade",
                "--prefer-binary",
                "transformers",
                "accelerate",
                "soundfile",
                "librosa",
                "sentencepiece",
            ],
            check=False,
            env=pip_env,
        )
        status["steps"].append({"command": "pip install transformers audio stack", "returncode": rest.returncode, "tail": rest.stdout[-3000:]})
    except Exception as exc:
        status["steps"].append({"command": "pip runtime deps", "error": str(exc)})

    module_state = module_status()
    status["modules"] = module_state
    status["ok"] = bool(module_state.get("transformers") and module_state.get("torch"))
    return status


def module_status() -> dict[str, bool]:
    names = ["huggingface_hub", "torch", "transformers", "accelerate", "soundfile", "librosa", "nemo", "nemo.collections.asr"]
    status: dict[str, bool] = {}
    for name in names:
        try:
            status[name] = importlib.util.find_spec(name) is not None
        except ModuleNotFoundError:
            status[name] = False
    return status


def fetch_model_info() -> dict:
    url = f"https://huggingface.co/api/models/{REPO_ID}"
    with urllib.request.urlopen(url, timeout=60) as response:
        info = json.load(response)
    return {
        "id": info.get("id"),
        "sha": info.get("sha"),
        "pipeline_tag": info.get("pipeline_tag"),
        "library_name": info.get("library_name"),
        "gated": info.get("gated"),
        "private": info.get("private"),
        "tags": info.get("tags") or [],
        "sibling_count": len(info.get("siblings") or []),
        "siblings": [item.get("rfilename") for item in (info.get("siblings") or [])],
    }


def download_snapshot() -> dict:
    dep_ok, dep_tail = install_download_deps()
    if not dep_ok:
        fail("huggingface_hub install failed: " + dep_tail)

    import importlib

    huggingface_hub = importlib.import_module("huggingface_hub")
    snapshot_download = huggingface_hub.snapshot_download

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    kwargs = {
        "repo_id": REPO_ID,
        "local_dir": str(MODEL_DIR),
        "resume_download": True,
    }
    try:
        path = snapshot_download(**kwargs, local_dir_use_symlinks=False)
    except TypeError:
        path = snapshot_download(**kwargs)
    return {"dependency_install_tail": dep_tail, "snapshot_path": path}


def file_summary() -> tuple[list[dict], int, int]:
    rows: list[dict] = []
    total = 0
    count = 0
    for path in sorted(MODEL_DIR.rglob("*"), key=lambda item: str(item).lower()):
        if not path.is_file():
            continue
        size = path.stat().st_size
        count += 1
        total += size
        rel = path.relative_to(MODEL_DIR).as_posix()
        rows.append({"relative_path": rel, "bytes": size})
    return rows, count, total


def validate_snapshot() -> dict:
    missing = [name for name in REQUIRED_FILES if not (MODEL_DIR / name).is_file()]
    if missing:
        fail("Nemotron ASR snapshot missing required files: " + ", ".join(missing))
    rows, count, total = file_summary()
    return {
        "required_files": REQUIRED_FILES,
        "missing_required_files": missing,
        "file_count": count,
        "total_bytes": total,
        "total_gib": round(total / (1024 ** 3), 3),
        "largest_files": sorted(rows, key=lambda item: item["bytes"], reverse=True)[:12],
    }


def write_service_dropin() -> None:
    SERVICE_DROPIN_DIR.mkdir(parents=True, exist_ok=True)
    text = f"""[Service]
Environment=ENGEL_ASR_MODEL_ID={REPO_ID}
Environment=ENGEL_ASR_MODEL_NAME=Nemotron-3.5-ASR-Streaming-0.6B
Environment=ENGEL_ASR_MODEL_ROOT={MODEL_DIR}
Environment=ENGEL_ASR_MODEL_STORAGE=engel-fast-ssd
Environment=ENGEL_ASR_MODEL_LIBRARY=nemo
Environment=ENGEL_ASR_MODEL_TASK=automatic-speech-recognition
Environment=ENGEL_ASR_STREAMING_ENABLED=1
Environment=ENGEL_VOICE_ASR_BACKEND=nemotron-transformers
Environment=ENGEL_VOICE_ASR_MODEL_ROOT={MODEL_DIR}
Environment=ENGEL_VOICE_ASR_MODEL_ID={REPO_ID}
"""
    SERVICE_DROPIN.write_text(text, encoding="utf-8")


def write_status_tool() -> None:
    STATUS_TOOL.parent.mkdir(parents=True, exist_ok=True)
    STATUS_TOOL.write_text(
        f"""#!/usr/bin/env python3
from __future__ import annotations
import importlib.util
import json
from pathlib import Path

model_dir = Path({str(MODEL_DIR)!r})
required = {REQUIRED_FILES!r}
modules = {{}}
for name in ["huggingface_hub", "torch", "transformers", "accelerate", "soundfile", "librosa", "nemo", "nemo.collections.asr"]:
    try:
        modules[name] = importlib.util.find_spec(name) is not None
    except ModuleNotFoundError:
        modules[name] = False
missing = [name for name in required if not (model_dir / name).is_file()]
payload = {{
    "ok": model_dir.is_dir() and not missing,
    "model_id": {REPO_ID!r},
    "model_root": str(model_dir),
    "missing_required_files": missing,
    "modules": modules,
}}
print(json.dumps(payload, indent=2, sort_keys=True))
raise SystemExit(0 if payload["ok"] else 1)
""",
        encoding="utf-8",
    )
    STATUS_TOOL.chmod(0o755)


def write_manifests(model_info: dict, validation: dict, runtime_deps: dict, download: dict) -> dict:
    now = utc_now()
    model_record = {
        "id": MODEL_ID,
        "repo": REPO_ID,
        "name": "Nemotron 3.5 ASR Streaming 0.6B",
        "task": "automatic-speech-recognition",
        "role": "streaming_asr",
        "library_name": model_info.get("library_name") or "nemo",
        "pipeline_tag": model_info.get("pipeline_tag") or "automatic-speech-recognition",
        "runtime_storage": "engel-fast-ssd",
        "path": str(MODEL_DIR),
        "source_url": f"https://huggingface.co/{REPO_ID}",
        "snapshot_sha": model_info.get("sha"),
        "gated": model_info.get("gated"),
        "private": model_info.get("private"),
        "file_count": validation["file_count"],
        "total_bytes": validation["total_bytes"],
        "total_gib": validation["total_gib"],
        "required_files": validation["required_files"],
        "runtime_dependency_status": runtime_deps,
        "installed_at_utc": now,
    }

    model_manifest = {
        "schema": "engel_nemotron_asr_streaming_06b_manifest_v1",
        "ok": True,
        "updated_at_utc": now,
        "model": model_record,
        "download": download,
        "notes": [
            "Installed on CT 246 fast SSD under /opt/engel/models-active/asr.",
            "Vault storage is not used by this ASR registration.",
            "Transformers runtime is installed when dependency installation succeeds; NeMo remains optional.",
        ],
    }
    write_json(MODEL_MANIFEST, model_manifest)

    asr_manifest = read_json(ASR_MANIFEST)
    asr_manifest.update(
        {
            "schema": "engel_asr_model_manifest_v1",
            "ok": True,
            "updated_at_utc": now,
            "active_asr_model": model_record,
            "active_streaming_asr_model_id": REPO_ID,
            "active_streaming_asr_model_root": str(MODEL_DIR),
            "active_streaming_asr_storage": "engel-fast-ssd",
            "vault_required": False,
            "service_environment_dropin": str(SERVICE_DROPIN),
        }
    )
    write_json(ASR_MANIFEST, asr_manifest)

    inventory = read_json(INVENTORY)
    installed = inventory.get("installed_models") if isinstance(inventory.get("installed_models"), dict) else {}
    installed[MODEL_ID] = model_record
    inventory.update(
        {
            "schema": inventory.get("schema") or "engel_ct_fast_ssd_model_inventory_v1",
            "ok": True,
            "updated_at_utc": now,
            "active_model_root": str(MODELS_ACTIVE),
            "active_runtime_storage": "engel-fast-ssd",
            "nemotron_3_5_asr_streaming_06b_installed": True,
            "active_streaming_asr_model_root": str(MODEL_DIR),
            "installed_models": installed,
        }
    )
    write_json(INVENTORY, inventory)
    return model_record


def main() -> int:
    if not RUNTIME_ROOT.exists():
        fail(f"runtime root missing: {RUNTIME_ROOT}")
    if path_is_vault(RUNTIME_ROOT) or path_is_vault(MODEL_DIR):
        fail(f"refusing to install ASR model under vault path: {MODEL_DIR}")

    for directory in [MODELS_ACTIVE, MODEL_DIR, MEMORY_MODELS, REPORTS, CACHE]:
        directory.mkdir(parents=True, exist_ok=True)

    started = time.time()
    model_info = fetch_model_info()
    if model_info.get("gated") or model_info.get("private"):
        fail(f"model repo is gated/private and cannot be installed without explicit Hugging Face access: {REPO_ID}")

    download = download_snapshot()
    validation = validate_snapshot()
    runtime_deps = install_runtime_deps()
    write_service_dropin()
    write_status_tool()
    model_record = write_manifests(model_info, validation, runtime_deps, download)

    df = run(["df", "-h", str(RUNTIME_ROOT)], check=False).stdout.strip()
    report = {
        "schema": "engel_nemotron_asr_streaming_06b_install_v1",
        "ok": True,
        "updated_at_utc": utc_now(),
        "elapsed_seconds": round(time.time() - started, 2),
        "model": model_record,
        "model_info": model_info,
        "validation": validation,
        "runtime_deps": runtime_deps,
        "manifest_path": str(MODEL_MANIFEST),
        "asr_manifest_path": str(ASR_MANIFEST),
        "inventory_path": str(INVENTORY),
        "status_tool": str(STATUS_TOOL),
        "service_dropin": str(SERVICE_DROPIN),
        "df_opt_engel": df,
        "guard": {
            "vault_used": False,
            "runtime_root": str(RUNTIME_ROOT),
            "storage": "engel-fast-ssd",
            "model_root": str(MODEL_DIR),
        },
        "report_content_sha256": sha256_text(json.dumps(model_record, sort_keys=True)),
    }
    write_json(REPORT, report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        error_report = {
            "schema": "engel_nemotron_asr_streaming_06b_install_v1",
            "ok": False,
            "updated_at_utc": utc_now(),
            "error": str(exc),
            "model_id": REPO_ID,
            "model_root": str(MODEL_DIR),
            "guard": {"vault_used": path_is_vault(MODEL_DIR)},
        }
        try:
            write_json(REPORT, error_report)
        except Exception:
            pass
        print(json.dumps(error_report, indent=2, sort_keys=True), file=sys.stderr)
        raise SystemExit(1)
'@

$remoteInstaller = $remoteInstaller.Replace("__RUNTIME_ROOT__", $RuntimeRoot)
$remoteInstaller = $remoteInstaller.Replace("__STAMP__", $Stamp)
$remoteInstaller = $remoteInstaller.Replace("__INSTALL_RUNTIME_DEPS__", $installRuntimeDeps)
Write-Utf8NoBom $LocalInstallerPath $remoteInstaller

$remoteTarget = "${CtUser}@${CtHost}"
& $SshExe -i $ResolvedKeyPath -p $CtPort -o BatchMode=yes -o StrictHostKeyChecking=accept-new $remoteTarget "mkdir -p '$RuntimeRoot/cache' '$RuntimeRoot/reports' '$RuntimeRoot/memory/models'"
if ($LASTEXITCODE -ne 0) { throw "Failed to prepare CT install directories." }

& $ScpExe -i $ResolvedKeyPath -P $CtPort -o BatchMode=yes -o StrictHostKeyChecking=accept-new $LocalInstallerPath "${remoteTarget}:$RemoteInstallerPath"
if ($LASTEXITCODE -ne 0) { throw "Failed to copy Nemotron ASR installer to CT." }

& $SshExe -i $ResolvedKeyPath -p $CtPort -o BatchMode=yes -o StrictHostKeyChecking=accept-new $remoteTarget "'$RuntimeRoot/.venv/bin/python' '$RemoteInstallerPath'"
if ($LASTEXITCODE -ne 0) { throw "Nemotron ASR install failed on CT." }

& $SshExe -i $ResolvedKeyPath -p $CtPort -o BatchMode=yes -o StrictHostKeyChecking=accept-new $remoteTarget "systemctl daemon-reload && systemctl restart engel-main-chat.service && sleep 2 && systemctl is-active engel-main-chat.service && '$RuntimeRoot/.venv/bin/python' '$RuntimeRoot/tools/engel_nemotron_asr_status.py' && curl -fsS http://127.0.0.1:8765/health"
if ($LASTEXITCODE -ne 0) { throw "Nemotron ASR post-install verification failed on CT." }

$remoteReport = & $SshExe -i $ResolvedKeyPath -p $CtPort -o BatchMode=yes -o StrictHostKeyChecking=accept-new $remoteTarget "cat '$RuntimeRoot/reports/ENGEL_NEMOTRON_ASR_STREAMING_06B_INSTALL_$Stamp.json'"
if ($LASTEXITCODE -ne 0) { throw "Failed to read CT Nemotron ASR install report." }
Write-Utf8NoBom $ReceiptPath ($remoteReport -join "`n")
Write-Host "Nemotron ASR fast SSD install receipt: $ReceiptPath"
