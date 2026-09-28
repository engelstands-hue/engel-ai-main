#!/usr/bin/env python3
"""Package Engel AI Sub-Engel as a Windows app install zip."""

from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
PYINSTALLER_APP = ROOT / "runtime" / "package_build" / "sub_engel_app_exe_dist" / "EngelAI-SubEngel"
BUILD_ROOT = ROOT / "runtime" / "package_build" / "EngelAI-SubEngel-Windows-App"
APP_DIR = BUILD_ROOT / "EngelAI-SubEngel"
ZIP_PATH = DIST / "EngelAI-SubEngel-Windows-App-20260621.zip"

MAIN_MISTRAL_MODEL = Path("/opt/engel/models-active/mistral-7b-instruct-v0.3/Mistral-7B-Instruct-v0.3-Q4_K_M.gguf")
MAIN_MISTRAL_MODEL_REL = Path("models/mistral-7b-instruct-v0.3/Mistral-7B-Instruct-v0.3-Q4_K_M.gguf")
CUDA_LLAMA_DIR = ROOT / "runtime" / "llama.cpp" / "candidates" / "llama-b9198-bin-win-cuda-12.4-x64"
CUDA_DLL_DIR = ROOT / "runtime" / "llama.cpp" / "candidates" / "cudart-llama-bin-win-cuda-12.4-x64"
TRAINED_LORA_DIR = Path("/opt/engel/models-active/lora/engel_standalone_lora_adapter_3wdwt9jjwf2cox_20260620T214117Z")
COSMOS3_ROOT = Path("/opt/engel/models-active/cosmos3")
LOCAL_HELPER_MANIFEST_NAME = "sub_engel_local_helper_model.json"


def utc_stamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def require_file(path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError(path)


def require_dir(path: Path) -> None:
    if not path.is_dir():
        raise FileNotFoundError(path)


def copytree_clean(source: Path, target: Path) -> None:
    require_dir(source)
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)


def dir_count_size(path: Path) -> dict[str, int]:
    count = 0
    size = 0
    for item in path.rglob("*"):
        if item.is_file():
            count += 1
            size += item.stat().st_size
    return {"file_count": count, "size_bytes": size}


def posix_rel(path: Path) -> str:
    return path.as_posix()


def write_local_llm_payload() -> dict[str, object]:
    require_file(MAIN_MISTRAL_MODEL)
    require_file(CUDA_LLAMA_DIR / "llama-cli.exe")
    require_dir(CUDA_DLL_DIR)
    require_file(TRAINED_LORA_DIR / "adapter_model.safetensors")

    internal = APP_DIR / "_internal"
    models_dir = internal / "models"
    runtimes_dir = internal / "runtimes" / "llama.cpp"
    lora_dir = internal / "lora" / TRAINED_LORA_DIR.name

    if models_dir.exists():
        shutil.rmtree(models_dir)
    models_dir.mkdir(parents=True, exist_ok=True)

    model_target = internal / MAIN_MISTRAL_MODEL_REL
    model_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(MAIN_MISTRAL_MODEL, model_target)

    copytree_clean(CUDA_LLAMA_DIR, runtimes_dir / "cuda")
    copytree_clean(CUDA_DLL_DIR, runtimes_dir / "cuda_dlls")
    copytree_clean(TRAINED_LORA_DIR, lora_dir)

    model_sha = sha256_file(model_target)
    cli_target = runtimes_dir / "cuda" / "llama-cli.exe"
    adapter_model = lora_dir / "adapter_model.safetensors"
    adapter_config = lora_dir / "adapter_config.json"
    training_receipt = lora_dir / "ENGEL_LORA_TRAINING_RECEIPT.json"
    cuda_stats = dir_count_size(runtimes_dir / "cuda")
    cuda_dll_stats = dir_count_size(runtimes_dir / "cuda_dlls")
    lora_stats = dir_count_size(lora_dir)

    manifest = {
        "schema": "engel_sub_engel_local_helper_model_v2",
        "name": "Engel AI Main local LLM packaged for Sub-Engel",
        "created_at_utc": utc_stamp(),
        "source": "Engel AI Main standalone chat profile",
        "included_model": {
            "family": "Mistral-7B-Instruct-v0.3",
            "format": "gguf",
            "quantization": "Q4_K_M",
            "file": posix_rel(MAIN_MISTRAL_MODEL_REL),
            "source_on_main": str(MAIN_MISTRAL_MODEL),
            "size_bytes": model_target.stat().st_size,
            "sha256": model_sha,
        },
        "runtime": {
            "provider": "llama.cpp",
            "backend": "cuda",
            "cli": "runtimes/llama.cpp/cuda/llama-cli.exe",
            "cli_sha256": sha256_file(cli_target),
            "cuda_dll_dir": "runtimes/llama.cpp/cuda_dlls",
            "gpu_layers_default": 99,
            "source_cli_dir_on_main": str(CUDA_LLAMA_DIR),
            "source_cuda_dll_dir_on_main": str(CUDA_DLL_DIR),
            "cuda_runtime_file_count": cuda_stats["file_count"],
            "cuda_runtime_size_bytes": cuda_stats["size_bytes"],
            "cuda_dll_file_count": cuda_dll_stats["file_count"],
            "cuda_dll_size_bytes": cuda_dll_stats["size_bytes"],
        },
        "trained_lora_adapter": {
            "schema": "engel_trained_lora_adapter_manifest_v1",
            "format": "peft_safetensors",
            "packaged_dir": f"lora/{TRAINED_LORA_DIR.name}",
            "source_on_main": str(TRAINED_LORA_DIR),
            "adapter_model": "adapter_model.safetensors",
            "adapter_model_size_bytes": adapter_model.stat().st_size,
            "adapter_model_sha256": sha256_file(adapter_model),
            "adapter_config": "adapter_config.json",
            "adapter_config_size_bytes": adapter_config.stat().st_size if adapter_config.is_file() else 0,
            "adapter_config_sha256": sha256_file(adapter_config) if adapter_config.is_file() else "",
            "training_receipt": "ENGEL_LORA_TRAINING_RECEIPT.json",
            "training_receipt_size_bytes": training_receipt.stat().st_size if training_receipt.is_file() else 0,
            "training_receipt_sha256": sha256_file(training_receipt) if training_receipt.is_file() else "",
            "artifact_file_count": lora_stats["file_count"],
            "artifact_size_bytes": lora_stats["size_bytes"],
            "runtime_loaded_by_current_gguf_cli": False,
            "runtime_note": "Packaged as the real trained LoRA artifact. The verified Sub-Engel CUDA GGUF runtime uses the base Mistral GGUF unless a converted llama.cpp adapter is added and verified.",
        },
        "cosmos3_reference": {
            "source_on_main": str(COSMOS3_ROOT),
            "packaged": False,
            "catalog_reference_only": True,
            "reason": "Cosmos3 remains on F: as the shared Engel model catalog; it is not copied into this Sub-Engel installer.",
        },
        "model_output_trusted": False,
        "command_execution_from_model": False,
    }
    manifest_path = models_dir / LOCAL_HELPER_MANIFEST_NAME
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    return {
        "manifest_path": str(manifest_path),
        "model_target": str(model_target),
        "model_size_bytes": model_target.stat().st_size,
        "model_sha256": model_sha,
        "cuda_cli": str(cli_target),
        "cuda_cli_sha256": manifest["runtime"]["cli_sha256"],
        "cuda_runtime_size_bytes": cuda_stats["size_bytes"] + cuda_dll_stats["size_bytes"],
        "lora_dir": str(lora_dir),
        "lora_adapter_model_sha256": manifest["trained_lora_adapter"]["adapter_model_sha256"],
        "cosmos3_reference": str(COSMOS3_ROOT),
    }


def zip_compress_type(path: Path) -> int:
    if path.suffix.lower() in {".gguf", ".safetensors", ".dll", ".exe", ".bin", ".zip"}:
        return zipfile.ZIP_STORED
    return zipfile.ZIP_DEFLATED


def write_installer() -> Path:
    installer = BUILD_ROOT / "Install_EngelAI_SubEngel.cmd"
    installer.write_text(
        "\n".join(
            [
                "@echo off",
                "setlocal",
                "set \"SRC=%~dp0EngelAI-SubEngel\"",
                "set \"TARGET=D:\\EngelAI\\SubEngel\"",
                "if not exist D:\\ set \"TARGET=%~dp0Installed\\EngelAI-SubEngel\"",
                "if not exist \"%SRC%\\EngelAI-SubEngel.exe\" (",
                "  echo Missing source app: %SRC%\\EngelAI-SubEngel.exe",
                "  exit /b 2",
                ")",
                "echo Stopping stale local Sub-Engel listener on TCP 8776 if present",
                "powershell -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -Command \"Get-NetTCPConnection -LocalPort 8776 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique | Where-Object { $_ } | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }\"",
                "echo Installing Engel AI Sub-Engel to %TARGET%",
                "robocopy \"%SRC%\" \"%TARGET%\" /MIR /NFL /NDL /NJH /NJS /NP >nul",
                "if %ERRORLEVEL% GEQ 8 exit /b %ERRORLEVEL%",
                "powershell -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -Command \"$shell=New-Object -ComObject WScript.Shell; $shortcut=$shell.CreateShortcut((Join-Path '%TARGET%' 'Engel AI Sub-Engel.lnk')); $shortcut.TargetPath='%TARGET%\\EngelAI-SubEngel.exe'; $shortcut.WorkingDirectory='%TARGET%'; $shortcut.Description='Engel AI Sub-Engel'; $shortcut.Save()\"",
                "echo Installed Engel AI Sub-Engel.",
                "echo Install-folder shortcut: %TARGET%\\Engel AI Sub-Engel.lnk",
                "start \"\" \"%TARGET%\\EngelAI-SubEngel.exe\"",
                "endlocal",
            ]
        )
        + "\n",
        encoding="ascii",
    )
    return installer


def main() -> int:
    if not (PYINSTALLER_APP / "EngelAI-SubEngel.exe").exists():
        raise FileNotFoundError(PYINSTALLER_APP / "EngelAI-SubEngel.exe")
    if BUILD_ROOT.exists():
        shutil.rmtree(BUILD_ROOT)
    BUILD_ROOT.mkdir(parents=True)
    DIST.mkdir(parents=True, exist_ok=True)

    shutil.copytree(PYINSTALLER_APP, APP_DIR)
    local_llm_payload = write_local_llm_payload()
    installer = write_installer()
    manifest = {
        "name": "Engel AI Sub-Engel Windows App",
        "version": "2026.06.21",
        "branding": "Engel AI",
        "installer": installer.name,
        "installed_app_exe": "EngelAI-SubEngel/EngelAI-SubEngel.exe",
        "default_install_dir": "D:/EngelAI/SubEngel",
        "desktop_shortcut": False,
        "install_folder_shortcut": "D:/EngelAI/SubEngel/Engel AI Sub-Engel.lnk",
        "python_script_user_entrypoint": False,
        "visible_user_entrypoints": [
            "Install_EngelAI_SubEngel.cmd",
            "EngelAI-SubEngel/EngelAI-SubEngel.exe",
        ],
        "support_agent_exe": "EngelAI-SubEngel/_internal/agent/engel_windows_sub_node_agent.exe",
        "local_llm": {
            "included": True,
            "manifest": f"EngelAI-SubEngel/_internal/models/{LOCAL_HELPER_MANIFEST_NAME}",
            "model": "EngelAI-SubEngel/_internal/models/mistral-7b-instruct-v0.3/Mistral-7B-Instruct-v0.3-Q4_K_M.gguf",
            "runtime_cli": "EngelAI-SubEngel/_internal/runtimes/llama.cpp/cuda/llama-cli.exe",
            "cuda_dll_dir": "EngelAI-SubEngel/_internal/runtimes/llama.cpp/cuda_dlls",
            "trained_lora_adapter": f"EngelAI-SubEngel/_internal/lora/{TRAINED_LORA_DIR.name}",
            "cosmos3_reference_only": str(COSMOS3_ROOT),
        },
        "safety": {
            "raw_shell": False,
            "ssh": False,
            "remote_disk_install": False,
            "service_install": False,
            "provider_runtime": False,
            "writes_c_drive": False,
            "shared_room_auto_return_default": True,
            "destructive_background_worker_default": False,
            "auto_apply": False,
            "requires_review_before_apply": True,
        },
    }
    (BUILD_ROOT / "ENGEL_SUB_ENGEL_APP_MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    receipt = {
        "built_at_utc": utc_stamp(),
        "zip_path": str(ZIP_PATH),
        "build_root": str(BUILD_ROOT),
        "app_exe_sha256": sha256_file(APP_DIR / "EngelAI-SubEngel.exe"),
        "agent_exe_sha256": sha256_file(APP_DIR / "_internal" / "agent" / "engel_windows_sub_node_agent.exe"),
        "local_llm": local_llm_payload,
        "file_count": sum(1 for path in BUILD_ROOT.rglob("*") if path.is_file()),
    }
    (BUILD_ROOT / "BUILD_RECEIPT.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")

    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(BUILD_ROOT.rglob("*")):
            if path.is_file():
                archive.write(
                    path,
                    path.relative_to(BUILD_ROOT).as_posix(),
                    compress_type=zip_compress_type(path),
                )

    out = {
        "ok": True,
        "zip_path": str(ZIP_PATH),
        "zip_sha256": sha256_file(ZIP_PATH),
        "file_count": receipt["file_count"],
        "installer": installer.name,
        "app_exe": str(APP_DIR / "EngelAI-SubEngel.exe"),
        "local_llm": local_llm_payload,
    }
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
