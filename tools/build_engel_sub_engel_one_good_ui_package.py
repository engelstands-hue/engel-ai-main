#!/usr/bin/env python3
"""Build the one-good-UI Engel AI Sub-Engel package."""

from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / "workflows" / "sub_engel_nodes"
STANDALONE = WORKFLOW / "standalone"
DIST = ROOT / "dist"
BUILD_ROOT = ROOT / "runtime" / "package_build" / "EngelAI-SubEngel-OneGoodUI"
SUPPORT_DIR = BUILD_ROOT / ".engel_support"
ZIP_PATH = DIST / "EngelAI-SubEngel-OneGoodUI-20260621.zip"
LOCAL_MODEL_SOURCE = (
    Path("/opt/engel/models-active")
    / "qwen2.5-0.5b-instruct"
    / "qwen2.5-0.5b-instruct-q5_k_m.gguf"
)
LOCAL_MODEL_TARGET = (
    SUPPORT_DIR
    / "models"
    / "qwen2.5-0.5b-instruct"
    / "qwen2.5-0.5b-instruct-q5_k_m.gguf"
)


def utc_stamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def copy_file(src: Path, dst: Path) -> None:
    if not src.exists():
        raise FileNotFoundError(src)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def write_launcher() -> Path:
    launcher = BUILD_ROOT / "START_ENGEL_AI_SUB_ENGEL.cmd"
    launcher.write_text(
        "\n".join(
            [
                "@echo off",
                "setlocal",
                "cd /d \"%~dp0\"",
                "set \"PY=%~dp0.engel_support\\bin\\python\\python.exe\"",
                "if not exist \"%PY%\" set \"PY=python\"",
                "\"%PY%\" \"%~dp0.engel_support\\app\\engel_sub_engel_gui.py\"",
                "endlocal",
            ]
        )
        + "\n",
        encoding="ascii",
    )
    return launcher


def main() -> int:
    if BUILD_ROOT.exists():
        shutil.rmtree(BUILD_ROOT)
    SUPPORT_DIR.mkdir(parents=True)
    DIST.mkdir(parents=True, exist_ok=True)

    launcher = write_launcher()
    copy_file(STANDALONE / "engel_sub_engel_gui.py", SUPPORT_DIR / "app" / "engel_sub_engel_gui.py")
    copy_file(ROOT / "engel_windows_sub_node_agent.py", SUPPORT_DIR / "agent" / "engel_windows_sub_node_agent.py")
    copy_file(STANDALONE / "models" / "sub_engel_local_helper_model.json", SUPPORT_DIR / "models" / "sub_engel_local_helper_model.json")
    copy_file(LOCAL_MODEL_SOURCE, LOCAL_MODEL_TARGET)

    manifest = {
        "name": "Engel AI Sub-Engel One Good UI",
        "version": "2026.06.21",
        "branding": "Engel AI",
        "visible_entrypoint": launcher.name,
        "gui": ".engel_support/app/engel_sub_engel_gui.py",
        "agent": ".engel_support/agent/engel_windows_sub_node_agent.py",
        "local_helper_model_manifest": ".engel_support/models/sub_engel_local_helper_model.json",
        "top_level_user_actions": [launcher.name],
        "removed_from_top_level": [
            "Run-EngelAISubEngelSelfTest.cmd",
            "Run-EngelAISubEngelLifecycleDemo.cmd",
            "installer scripts",
            "extra README pages",
        ],
        "main_compatible": True,
        "pairing_required": True,
        "google_drive_shared_room": {
            "enabled": True,
            "room_name": "ENGEL_SHARED_NODE_ROOM",
            "active_work_request_file": "SUB_ENGEL_ACTIVE_WORK_REQUEST.json",
            "work_order_folder": "SUB_ENGEL_WORK_ORDERS",
            "sent_work_folder": "SUB_ENGEL_SENT_WORK",
            "shows_active_main_request": True,
            "shows_selected_sub_engel_detail": True,
            "shows_matching_returned_proof_files": True,
        },
        "safety": {
            "raw_shell": False,
            "ssh": False,
            "remote_disk_install": False,
            "service_install": False,
            "provider_runtime": False,
            "background_worker_default": False,
        },
        "included_model": {
            "path": str(LOCAL_MODEL_TARGET.relative_to(BUILD_ROOT)).replace("\\", "/"),
            "source": str(LOCAL_MODEL_SOURCE),
            "sha256": sha256_file(LOCAL_MODEL_TARGET),
            "size_bytes": LOCAL_MODEL_TARGET.stat().st_size,
        },
    }
    (SUPPORT_DIR / "package_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    receipt = {
        "built_at_utc": utc_stamp(),
        "zip_path": str(ZIP_PATH),
        "build_root": str(BUILD_ROOT),
        "visible_top_level_files": [launcher.name],
        "support_root": ".engel_support",
        "manifest": ".engel_support/package_manifest.json",
        "gui_sha256": sha256_file(SUPPORT_DIR / "app" / "engel_sub_engel_gui.py"),
        "agent_sha256": sha256_file(SUPPORT_DIR / "agent" / "engel_windows_sub_node_agent.py"),
        "model_sha256": sha256_file(LOCAL_MODEL_TARGET),
    }
    (SUPPORT_DIR / "BUILD_RECEIPT.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")

    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(BUILD_ROOT.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(BUILD_ROOT).as_posix())

    out = {
        "ok": True,
        "zip_path": str(ZIP_PATH),
        "zip_sha256": sha256_file(ZIP_PATH),
        "file_count": sum(1 for path in BUILD_ROOT.rglob("*") if path.is_file()),
        "top_level_files": sorted(path.name for path in BUILD_ROOT.iterdir() if path.is_file()),
        "support_dir": str(SUPPORT_DIR),
    }
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
