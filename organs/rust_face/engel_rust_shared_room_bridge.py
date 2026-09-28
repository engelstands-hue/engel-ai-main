#!/usr/bin/env python3
"""Safe Python bridge to Rust-native Engel shared Drive room operations."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
from typing import Any

from engel_project_paths import resolve_engel_app_root


ENGEL_APP_ROOT = resolve_engel_app_root(__file__)


def _rust_executable() -> Path | None:
    configured = os.environ.get("ENGEL_AI_RS_EXE", "").strip()
    candidates: list[Path] = []
    if configured:
        candidates.append(Path(configured))
    candidates.extend(
        [
            ENGEL_APP_ROOT / "rust" / "engel-core-rs" / "target" / "debug" / "engel-ai-rs.exe",
            ENGEL_APP_ROOT / "rust" / "engel-core-rs" / "target" / "release" / "engel-ai-rs.exe",
        ]
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def _run_shared_room(args: list[str], timeout: float = 60.0) -> dict[str, Any]:
    exe = _rust_executable()
    if exe is None:
        return {
            "ok": False,
            "error": "engel-ai-rs executable not built",
            "runtime": "engel-ai-rs",
        }
    run = subprocess.run(
        [str(exe), "shared-room", *args],
        cwd=str(ENGEL_APP_ROOT),
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    if run.returncode != 0:
        return {
            "ok": False,
            "error": f"engel-ai-rs failed with exit code {run.returncode}",
            "runtime": "engel-ai-rs",
            "stderr": run.stderr.strip(),
        }
    try:
        payload = json.loads(run.stdout)
    except json.JSONDecodeError as exc:
        return {
            "ok": False,
            "error": f"engel-ai-rs returned invalid JSON: {exc}",
            "runtime": "engel-ai-rs",
            "stdout": run.stdout.strip(),
        }
    if isinstance(payload, dict):
        payload.setdefault("runtime", "engel-ai-rs")
        payload.setdefault("google_doc_url", "")
        payload.setdefault("connector_status", "")
        return payload
    return {
        "ok": False,
        "error": "engel-ai-rs returned non-object JSON",
        "runtime": "engel-ai-rs",
        "stdout": run.stdout.strip(),
    }


def init_room_via_rust(
    root: str | Path | None = None,
    google_doc_url: str = "",
    connector_status: str = "",
) -> dict[str, Any]:
    args = ["init"]
    if root:
        args.extend(["--root", str(root)])
    if google_doc_url:
        args.extend(["--google-doc-url", str(google_doc_url)])
    if connector_status:
        args.extend(["--connector-status", str(connector_status)])
    return _run_shared_room(args)


def append_message_via_rust(
    sender: str,
    message: str,
    channel: str = "input",
    root: str | Path | None = None,
) -> dict[str, Any]:
    args = [
        "append",
        "--sender",
        str(sender or "engel-ai-rs"),
        "--channel",
        str(channel or "input"),
        "--message",
        str(message or ""),
    ]
    if root:
        args.extend(["--root", str(root)])
    return _run_shared_room(args)


def status_via_rust(root: str | Path | None = None) -> dict[str, Any]:
    args = ["status"]
    if root:
        args.extend(["--root", str(root)])
    return _run_shared_room(args)


def tail_via_rust(
    root: str | Path | None = None,
    limit: int = 20,
    channel: str | None = None,
) -> dict[str, Any]:
    args = ["tail", "--limit", str(max(1, int(limit or 1)))]
    if root:
        args.extend(["--root", str(root)])
    if channel:
        args.extend(["--channel", str(channel)])
    return _run_shared_room(args)
