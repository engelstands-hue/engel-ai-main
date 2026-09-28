#!/usr/bin/env python3
"""Safe Python bridge to Rust-native Engel Meeting Room order flow."""
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


def _rust_root_env() -> dict[str, str]:
    env = os.environ.copy()
    root_override = os.environ.get("ENGEL_MEETING_ROOM_RUST_ROOT", "").strip()
    if root_override:
        env["ENGEL_APP_ROOT"] = root_override
    return env


def _env_true(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _run_rust_meeting_room(args: list[str], timeout: float = 120.0) -> dict[str, Any]:
    exe = _rust_executable()
    if exe is None:
        return {
            "accepted": False,
            "ok": False,
            "reason": "engel-ai-rs executable not built",
            "runtime": "engel-ai-rs",
        }
    run = subprocess.run(
        [str(exe), "meeting-room", *args],
        cwd=str(ENGEL_APP_ROOT),
        env=_rust_root_env(),
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    if run.returncode != 0:
        return {
            "accepted": False,
            "ok": False,
            "reason": f"engel-ai-rs failed with exit code {run.returncode}",
            "runtime": "engel-ai-rs",
            "stderr": run.stderr.strip(),
        }
    try:
        payload = json.loads(run.stdout)
    except json.JSONDecodeError as exc:
        return {
            "accepted": False,
            "ok": False,
            "reason": f"engel-ai-rs returned invalid JSON: {exc}",
            "runtime": "engel-ai-rs",
            "stdout": run.stdout.strip(),
        }
    if isinstance(payload, dict):
        payload.setdefault("runtime", "engel-ai-rs")
        return payload
    return {
        "accepted": False,
        "ok": False,
        "reason": "engel-ai-rs returned non-object JSON",
        "runtime": "engel-ai-rs",
        "stdout": run.stdout.strip(),
    }


def submit_order_via_rust(order_text: str, source: str = "Engel AI Main UI") -> dict[str, Any]:
    return _run_rust_meeting_room(
        [
            "native-submit",
            "--source",
            str(source or "Engel AI Main UI"),
            str(order_text or ""),
        ]
    )


def complete_order_via_rust(
    order_id: str,
    main_reply: str,
    source: str = "Engel AI Main UI",
) -> dict[str, Any]:
    args = [
        "native-complete",
        "--order-id",
        str(order_id or ""),
        "--source",
        str(source or "Engel AI Main UI"),
        "--reply",
        str(main_reply or ""),
    ]
    if _env_true("ENGEL_MEETING_ROOM_RUST_WRITE_DISPATCH"):
        args.append("--write-dispatch-packets")
        dispatch_root = os.environ.get("ENGEL_MEETING_ROOM_RUST_DISPATCH_ROOT", "").strip()
        if dispatch_root:
            args.extend(["--dispatch-root", dispatch_root])
        else:
            args.append("--live-dispatch")
        if _env_true("ENGEL_MEETING_ROOM_RUST_ALLOW_LIVE_DISPATCH"):
            args.append("--allow-live-dispatch")
    return _run_rust_meeting_room(
        args
    )


def return_intake_via_rust(
    order_id: str,
    source: str = "Engel AI Main UI",
) -> dict[str, Any]:
    return _run_rust_meeting_room(
        [
            "native-return-intake",
            "--order-id",
            str(order_id or ""),
            "--source",
            str(source or "Engel AI Main UI"),
        ]
    )
