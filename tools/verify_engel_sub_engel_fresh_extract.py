#!/usr/bin/env python3
"""Verify a fresh unzip of the Engel AI Sub-Engel package can run."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import socket
import subprocess
import time
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ZIP_PATH = ROOT / "dist" / "EngelAI-SubEngel-Standalone-20260607.zip"
RUNTIME_ROOT = ROOT / "runtime" / "sub_engel_fresh_extract_verifier"
PROOF_PATH = ROOT / "runtime" / "sub_engel_fresh_extract_verifier_latest.json"
SHARED_ROOM = Path(
    os.environ.get(
        "ENGEL_SUB_ENGEL_TRANSPORT_ROOT",
        str(ROOT / "run" / "sub_engel_transport"),
    )
)
WORK_ORDERS = SHARED_ROOM / "SUB_ENGEL_WORK_ORDERS"
SENT_WORK = SHARED_ROOM / "SUB_ENGEL_SENT_WORK"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def run_script(package_root: Path, script_name: str, node_root: Path) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
    env = os.environ.copy()
    env["ENGEL_SHARED_ROOM_ROOT"] = str(SHARED_ROOM)
    env["ENGEL_WINDOWS_SUB_NODE_ROOT"] = str(node_root)
    env["TEMP"] = str(node_root / "temp")
    env["TMP"] = str(node_root / "temp")
    env["TMPDIR"] = str(node_root / "temp")
    completed = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(package_root / script_name),
            str(node_root),
        ],
        cwd=str(package_root),
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=120,
        check=False,
    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    payload = json.loads(completed.stdout[completed.stdout.find("{") :])
    return completed, payload


def main() -> int:
    require(ZIP_PATH.exists(), f"missing zip: {ZIP_PATH}")
    require(SHARED_ROOM.exists(), f"missing shared room: {SHARED_ROOM}")
    require(WORK_ORDERS.exists(), f"missing work orders folder: {WORK_ORDERS}")
    SENT_WORK.mkdir(parents=True, exist_ok=True)

    run_id = f"{int(time.time())}-{os.getpid()}"
    package_root = RUNTIME_ROOT / f"package-{run_id}"
    node_root = RUNTIME_ROOT / f"node-{run_id}"
    package_root.parent.mkdir(parents=True, exist_ok=True)
    node_root.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(ZIP_PATH, "r") as zf:
        zf.extractall(package_root)

    required = [
        package_root / "Start-EngelAISubEngel.cmd",
        package_root / "Run-EngelAISubEngelSelfTest.ps1",
        package_root / "Run-EngelAISubEngelLifecycleDemo.ps1",
        package_root / "app" / "engel_sub_engel_gui.py",
        package_root / "models" / "qwen2.5-0.5b-instruct" / "qwen2.5-0.5b-instruct-q5_k_m.gguf",
    ]
    for path in required:
        require(path.exists(), f"fresh extract missing required file: {path}")

    self_test_completed, self_test = run_script(
        package_root,
        "Run-EngelAISubEngelSelfTest.ps1",
        node_root,
    )
    require(self_test_completed.returncode == 0, f"self-test failed: {self_test_completed.stderr}")
    require(self_test.get("overall_ok") is True, "fresh-extract self-test overall_ok false")
    require(self_test.get("shared_room") == str(SHARED_ROOM), "fresh-extract shared room mismatch")
    require(
        (self_test.get("local_helper_model") or {}).get("ok") is True,
        "fresh-extract local helper model check failed",
    )

    lifecycle_completed, lifecycle = run_script(
        package_root,
        "Run-EngelAISubEngelLifecycleDemo.ps1",
        node_root,
    )
    require(lifecycle_completed.returncode == 0, f"lifecycle demo failed: {lifecycle_completed.stderr}")
    require(lifecycle.get("overall_ok") is True, "fresh-extract lifecycle overall_ok false")
    exported = Path(str(lifecycle["exported_file"]))
    require(exported.exists(), f"fresh-extract exported result missing: {exported}")
    require(str(exported).startswith(str(SENT_WORK)), "fresh-extract export was not sent-work folder")

    proof = {
        "ok": True,
        "event": "sub_engel_fresh_extract_verifier",
        "hostname": socket.gethostname(),
        "zip": str(ZIP_PATH),
        "zip_sha256": sha256_file(ZIP_PATH),
        "package_root": str(package_root),
        "node_root": str(node_root),
        "shared_room": str(SHARED_ROOM),
        "self_test_receipt": self_test.get("receipt_path"),
        "self_test_overall_ok": self_test.get("overall_ok"),
        "lifecycle_receipt": lifecycle.get("receipt_path"),
        "lifecycle_overall_ok": lifecycle.get("overall_ok"),
        "lifecycle_exported_file": str(exported),
        "lifecycle_exported_file_sha256": sha256_file(exported),
        "included_model_sha256": sha256_file(required[-1]),
        "included_model_bytes": required[-1].stat().st_size,
    }
    PROOF_PATH.write_text(json.dumps(proof, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(proof, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        raise SystemExit(1)
