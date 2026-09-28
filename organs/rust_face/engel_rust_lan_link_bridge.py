#!/usr/bin/env python3
"""Narrow Python bridge to Rust LAN link state-control commands."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
from typing import Any

from engel_project_paths import resolve_engel_app_root


ENGEL_APP_ROOT = resolve_engel_app_root(__file__)
BRIDGE_ENV = "ENGEL_REMOTE_WORKER_LINK_MANAGER_RUST_BRIDGE"
STRICT_ENV = "ENGEL_REMOTE_WORKER_LINK_MANAGER_RUST_STRICT"
ROOT_ENV = "ENGEL_REMOTE_WORKER_LINK_MANAGER_RUST_ROOT"
ALLOWED_ACTIONS = {
    "enable-auto-worker",
    "disable-auto-worker",
    "check-now",
}
PROCESS_CONTROL_APPROVAL = "APPROVE_REMOTE_WORKER_LINK_PROCESS_CONTROL"
PROCESS_ACTIONS = {
    "start",
    "stop",
    "restart",
}


def _truthy_value(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _truthy(name: str) -> bool:
    return _truthy_value(os.environ.get(name, ""))


def bridge_enabled(*, force: bool = False) -> bool:
    return force or _truthy(BRIDGE_ENV)


def strict_enabled(override: bool | None = None) -> bool:
    if override is not None:
        return bool(override)
    return _truthy(STRICT_ENV)


def _bridge_root(override: str | os.PathLike[str] | None = None) -> Path:
    if override is not None:
        return Path(override)
    configured = os.environ.get(ROOT_ENV, "").strip()
    return Path(configured) if configured else ENGEL_APP_ROOT


def _rust_executable(override: str | os.PathLike[str] | None = None) -> Path | None:
    configured = str(override or os.environ.get("ENGEL_AI_RS_EXE", "")).strip()
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


def _failure(status: int, reason: str, *, strict: bool | None = None, **extra: Any) -> dict[str, Any] | None:
    if not strict_enabled(strict):
        return None
    payload: dict[str, Any] = {
        "ok": False,
        "status": "rust_link_bridge_unavailable",
        "status_code": status,
        "runtime": "engel-ai-rs",
        "bridge": "python-link-manager-rust-lan-link",
        "reason": reason,
        "phone_does_not_control_engel": True,
        "direct_control": False,
        "trusted_memory_write": False,
        "auto_apply": False,
        "safe_to_auto_apply": False,
    }
    payload.update(extra)
    return payload


def run_link_control(
    action: str,
    *,
    force: bool = False,
    bridge_root: str | os.PathLike[str] | None = None,
    strict: bool | None = None,
    rust_executable: str | os.PathLike[str] | None = None,
) -> dict[str, Any] | None:
    if not bridge_enabled(force=force):
        return None
    if action not in ALLOWED_ACTIONS:
        return _failure(400, "unsupported Rust LAN link bridge action", strict=strict)
    exe = _rust_executable(rust_executable)
    if exe is None:
        return _failure(503, "engel-ai-rs executable not built", strict=strict)

    root = _bridge_root(bridge_root)
    env = os.environ.copy()
    env["ENGEL_APP_ROOT"] = str(root)
    try:
        run = subprocess.run(
            [str(exe), "lan-link", action],
            cwd=str(ENGEL_APP_ROOT),
            env=env,
            text=True,
            capture_output=True,
            timeout=45,
            check=False,
            shell=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return _failure(503, f"engel-ai-rs bridge failed to start: {exc}", strict=strict)

    if run.returncode != 0:
        return _failure(
            502,
            f"engel-ai-rs failed with exit code {run.returncode}",
            strict=strict,
            stderr=run.stderr.strip(),
        )
    try:
        payload = json.loads(run.stdout)
    except json.JSONDecodeError as exc:
        return _failure(
            502,
            f"engel-ai-rs returned invalid JSON: {exc}",
            strict=strict,
            stdout=run.stdout.strip(),
        )
    if not isinstance(payload, dict):
        return _failure(502, "engel-ai-rs returned a non-object JSON payload", strict=strict)

    payload.setdefault("ok", True)
    payload.setdefault("runtime", "engel-ai-rs")
    payload.setdefault("bridge", "python-link-manager-rust-lan-link")
    payload.setdefault("status_code", 200)
    payload.setdefault("phone_does_not_control_engel", True)
    payload.setdefault("trusted_memory_write", False)
    payload.setdefault("auto_apply", False)
    payload.setdefault("safe_to_auto_apply", False)
    return payload


def run_link_process_control(
    action: str,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
    allow_lan: bool = False,
    force: bool = False,
    bridge_root: str | os.PathLike[str] | None = None,
    strict: bool | None = None,
    rust_executable: str | os.PathLike[str] | None = None,
) -> dict[str, Any] | None:
    if not bridge_enabled(force=force):
        return None
    if action not in PROCESS_ACTIONS:
        return _failure(400, "unsupported Rust LAN link process-control action", strict=strict)
    exe = _rust_executable(rust_executable)
    if exe is None:
        return _failure(503, "engel-ai-rs executable not built", strict=strict)

    root = _bridge_root(bridge_root)
    env = os.environ.copy()
    env["ENGEL_APP_ROOT"] = str(root)
    command = [str(exe), "lan-link", action, "--approve", PROCESS_CONTROL_APPROVAL]
    if action in {"start", "restart"}:
        command.extend(["--host", str(host), "--port", str(int(port))])
        if allow_lan:
            command.append("--allow-lan")
    try:
        capture_dir = root / "remote_workers" / "lan_link_manager" / "bridge_capture"
        capture_dir.mkdir(parents=True, exist_ok=True)
        suffix = f"{os.getpid()}_{action}"
        stdout_path = capture_dir / f"rust_process_control_{suffix}_stdout.json"
        stderr_path = capture_dir / f"rust_process_control_{suffix}_stderr.txt"
        with stdout_path.open("w", encoding="utf-8") as stdout_handle, stderr_path.open(
            "w", encoding="utf-8"
        ) as stderr_handle:
            run = subprocess.run(
                command,
                cwd=str(ENGEL_APP_ROOT),
                env=env,
                text=True,
                stdout=stdout_handle,
                stderr=stderr_handle,
                timeout=60,
                check=False,
                shell=False,
            )
        stdout_text = stdout_path.read_text(encoding="utf-8", errors="replace")
        stderr_text = stderr_path.read_text(encoding="utf-8", errors="replace")
    except (OSError, subprocess.SubprocessError) as exc:
        return _failure(503, f"engel-ai-rs process-control bridge failed to start: {exc}", strict=strict)

    if run.returncode != 0:
        return _failure(
            502,
            f"engel-ai-rs process-control failed with exit code {run.returncode}",
            strict=strict,
            stderr=stderr_text.strip(),
        )
    try:
        payload = json.loads(stdout_text)
    except json.JSONDecodeError as exc:
        return _failure(
            502,
            f"engel-ai-rs returned invalid process-control JSON: {exc}",
            strict=strict,
            stdout=stdout_text.strip(),
        )
    if not isinstance(payload, dict):
        return _failure(502, "engel-ai-rs returned a non-object process-control JSON payload", strict=strict)

    payload.setdefault("ok", True)
    payload.setdefault("runtime", "engel-ai-rs")
    payload.setdefault("bridge", "python-link-manager-rust-lan-link")
    payload.setdefault("bridge_process_control", True)
    payload.setdefault("status_code", 200)
    payload.setdefault("phone_does_not_control_engel", True)
    payload.setdefault("trusted_memory_write", False)
    payload.setdefault("auto_apply", False)
    payload.setdefault("safe_to_auto_apply", False)
    return payload
