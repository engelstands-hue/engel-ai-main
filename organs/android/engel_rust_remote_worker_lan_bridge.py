#!/usr/bin/env python3
"""Narrow Python bridge to Rust remote-worker LAN state-machine helpers."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
from typing import Any

from engel_project_paths import resolve_engel_app_root


ENGEL_APP_ROOT = resolve_engel_app_root(__file__)
BRIDGE_ENV = "ENGEL_REMOTE_WORKER_LAN_RUST_BRIDGE"
STRICT_ENV = "ENGEL_REMOTE_WORKER_LAN_RUST_STRICT"
ROOT_ENV = "ENGEL_REMOTE_WORKER_LAN_RUST_ROOT"


def _truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def bridge_enabled() -> bool:
    return _truthy(BRIDGE_ENV)


def strict_enabled() -> bool:
    return _truthy(STRICT_ENV)


def _bridge_root() -> Path:
    configured = os.environ.get(ROOT_ENV, "").strip()
    return Path(configured) if configured else ENGEL_APP_ROOT


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


def _failure(status: int, reason: str, **extra: Any) -> tuple[int, dict[str, Any]] | None:
    if not strict_enabled():
        return None
    payload: dict[str, Any] = {
        "accepted": False,
        "status": "rust_bridge_unavailable",
        "status_code": status,
        "runtime": "engel-ai-rs",
        "bridge": "python-lan-endpoint-rust-state-machine",
        "reason": reason,
        "direct_control": False,
        "trusted_memory_write": False,
        "auto_apply": False,
        "safe_to_auto_apply": False,
    }
    payload.update(extra)
    return status, payload


def _run_rust(args: list[str], *, input_payload: Any | None = None) -> tuple[int, dict[str, Any]] | None:
    if not bridge_enabled():
        return None
    exe = _rust_executable()
    if exe is None:
        return _failure(503, "engel-ai-rs executable not built")

    root = _bridge_root()
    env = os.environ.copy()
    env["ENGEL_APP_ROOT"] = str(root)
    command = [str(exe), *args]
    input_text = None if input_payload is None else json.dumps(input_payload)
    try:
        run = subprocess.run(
            command,
            cwd=str(ENGEL_APP_ROOT),
            env=env,
            input=input_text,
            text=True,
            capture_output=True,
            timeout=45,
            check=False,
            shell=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return _failure(503, f"engel-ai-rs bridge failed to start: {exc}")

    if run.returncode != 0:
        return _failure(
            502,
            f"engel-ai-rs failed with exit code {run.returncode}",
            stderr=run.stderr.strip(),
        )
    try:
        payload = json.loads(run.stdout)
    except json.JSONDecodeError as exc:
        return _failure(
            502,
            f"engel-ai-rs returned invalid JSON: {exc}",
            stdout=run.stdout.strip(),
        )
    if not isinstance(payload, dict):
        return _failure(502, "engel-ai-rs returned a non-object JSON payload")

    payload.setdefault("runtime", "engel-ai-rs")
    payload.setdefault("bridge", "python-lan-endpoint-rust-state-machine")
    payload.setdefault("direct_control", False)
    payload.setdefault("trusted_memory_write", False)
    payload.setdefault("auto_apply", False)
    payload.setdefault("safe_to_auto_apply", False)
    status = int(payload.get("status_code") or 200)
    return status, payload


def claim_next_assignment(worker_id: str, worker_device: str) -> tuple[int, dict[str, Any]] | None:
    root = _bridge_root()
    return _run_rust(
        [
            "remote-workers",
            "claim-next",
            "--root",
            str(root),
            "--worker-id",
            str(worker_id),
            "--worker-device",
            str(worker_device),
        ]
    )


def return_result(payload: Any, remote_address: str) -> tuple[int, dict[str, Any]] | None:
    safe_payload = dict(payload) if isinstance(payload, dict) else payload
    if isinstance(safe_payload, dict):
        safe_payload.pop("pairing_code", None)
    root = _bridge_root()
    return _run_rust(
        [
            "remote-workers",
            "return-result",
            "--root",
            str(root),
            "--remote-address",
            str(remote_address),
        ],
        input_payload=safe_payload,
    )
