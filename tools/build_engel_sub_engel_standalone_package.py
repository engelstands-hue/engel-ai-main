#!/usr/bin/env python3
"""Build the Engel AI Sub-Engel standalone zip."""

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
BUILD_ROOT = ROOT / "runtime" / "package_build" / "EngelAI-SubEngel-Standalone"
ZIP_PATH = DIST / "EngelAI-SubEngel-Standalone-20260607.zip"
LOCAL_MODEL_SOURCE = (
    Path("/opt/engel/models-active")
    / "qwen2.5-0.5b-instruct"
    / "qwen2.5-0.5b-instruct-q5_k_m.gguf"
)
LOCAL_MODEL_TARGET = (
    BUILD_ROOT
    / "models"
    / "qwen2.5-0.5b-instruct"
    / "qwen2.5-0.5b-instruct-q5_k_m.gguf"
)


def utc_stamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def copy_file(src: Path, dst: Path) -> None:
    if not src.exists():
        raise FileNotFoundError(src)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def main() -> int:
    if BUILD_ROOT.exists():
        shutil.rmtree(BUILD_ROOT)
    BUILD_ROOT.mkdir(parents=True)
    DIST.mkdir(parents=True, exist_ok=True)

    copy_file(STANDALONE / "Start-EngelAISubEngel.cmd", BUILD_ROOT / "Start-EngelAISubEngel.cmd")
    copy_file(STANDALONE / "Start-EngelAISubEngel.ps1", BUILD_ROOT / "Start-EngelAISubEngel.ps1")
    copy_file(STANDALONE / "Run-EngelAISubEngelSelfTest.cmd", BUILD_ROOT / "Run-EngelAISubEngelSelfTest.cmd")
    copy_file(STANDALONE / "Run-EngelAISubEngelSelfTest.ps1", BUILD_ROOT / "Run-EngelAISubEngelSelfTest.ps1")
    copy_file(STANDALONE / "Run-EngelAISubEngelLifecycleDemo.cmd", BUILD_ROOT / "Run-EngelAISubEngelLifecycleDemo.cmd")
    copy_file(STANDALONE / "Run-EngelAISubEngelLifecycleDemo.ps1", BUILD_ROOT / "Run-EngelAISubEngelLifecycleDemo.ps1")
    copy_file(STANDALONE / "README_STANDALONE.md", BUILD_ROOT / "README_STANDALONE.md")
    copy_file(STANDALONE / "package_manifest.json", BUILD_ROOT / "package_manifest.json")
    copy_file(STANDALONE / "engel_sub_engel_gui.py", BUILD_ROOT / "app" / "engel_sub_engel_gui.py")
    copy_file(STANDALONE / "engel_sub_engel_self_test.py", BUILD_ROOT / "app" / "engel_sub_engel_self_test.py")
    copy_file(STANDALONE / "engel_sub_engel_lifecycle_demo.py", BUILD_ROOT / "app" / "engel_sub_engel_lifecycle_demo.py")
    copy_file(ROOT / "engel_windows_sub_node_agent.py", BUILD_ROOT / "agent" / "engel_windows_sub_node_agent.py")
    copy_file(WORKFLOW / "install_windows_sub_engel_node.ps1", BUILD_ROOT / "workflows" / "install_windows_sub_engel_node.ps1")
    copy_file(WORKFLOW / "windows_sub_engel_file_structure.json", BUILD_ROOT / "config" / "windows_sub_engel_file_structure.json")
    copy_file(STANDALONE / "models" / "sub_engel_local_helper_model.json", BUILD_ROOT / "models" / "sub_engel_local_helper_model.json")
    copy_file(LOCAL_MODEL_SOURCE, LOCAL_MODEL_TARGET)

    (BUILD_ROOT / "bin").mkdir(parents=True, exist_ok=True)
    (BUILD_ROOT / "bin" / "README_PYTHON.txt").write_text(
        "\n".join(
            [
                "Engel AI Sub-Engel uses Python 3.",
                "If a portable Python is placed at bin\\python\\python.exe, the launcher will use it.",
                "Otherwise the launcher uses the system python command.",
                "The included installer can download portable Python into the node root when needed.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    receipt = {
        "built_at_utc": utc_stamp(),
        "name": "Engel AI Sub-Engel Standalone",
        "zip_path": str(ZIP_PATH),
        "build_root": str(BUILD_ROOT),
        "entrypoints": ["Start-EngelAISubEngel.cmd", "Start-EngelAISubEngel.ps1"],
        "self_test_entrypoints": [
            "Run-EngelAISubEngelSelfTest.cmd",
            "Run-EngelAISubEngelSelfTest.ps1",
        ],
        "lifecycle_demo_entrypoints": [
            "Run-EngelAISubEngelLifecycleDemo.cmd",
            "Run-EngelAISubEngelLifecycleDemo.ps1",
        ],
        "gui": "app/engel_sub_engel_gui.py",
        "cli_self_test": "app/engel_sub_engel_self_test.py",
        "cli_lifecycle_demo": "app/engel_sub_engel_lifecycle_demo.py",
        "agent": "agent/engel_windows_sub_node_agent.py",
        "local_helper_model_manifest": "models/sub_engel_local_helper_model.json",
        "included_model": {
            "path": str(LOCAL_MODEL_TARGET.relative_to(BUILD_ROOT)).replace("\\", "/"),
            "source": str(LOCAL_MODEL_SOURCE),
            "sha256": sha256_file(LOCAL_MODEL_TARGET),
            "size_bytes": LOCAL_MODEL_TARGET.stat().st_size,
        },
    }
    (BUILD_ROOT / "BUILD_RECEIPT.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")

    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in sorted(BUILD_ROOT.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(BUILD_ROOT).as_posix())

    out = {
        "ok": True,
        "zip_path": str(ZIP_PATH),
        "zip_sha256": sha256_file(ZIP_PATH),
        "file_count": sum(1 for p in BUILD_ROOT.rglob("*") if p.is_file()),
        "build_root": str(BUILD_ROOT),
    }
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
