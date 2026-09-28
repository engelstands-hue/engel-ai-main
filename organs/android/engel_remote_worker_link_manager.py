"""Engel-controlled local link manager for the dedicated Android Remote Worker.

Phase 12 gives Engel a visible, user-controlled way to start and stop the
existing LAN receiver. The control direction is Engel PC -> dedicated phone.
The phone still cannot control Engel, apply changes, write trusted memory, or
mutate source/routes/queues.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from typing import Any

import engel_remote_worker_lan_pairing as lan_pairing
from engel_project_paths import resolve_engel_app_root


def _resolve_engel_python_executable(caller_file: str | os.PathLike[str] | None = None) -> Path:
    try:
        from engel_project_paths import resolve_engel_python_executable

        return resolve_engel_python_executable(caller_file)
    except ImportError:
        root = resolve_engel_app_root(caller_file)
        bundled = root / "runtime" / "python310" / "python.exe"
        if bundled.is_file():
            return bundled
        return Path(sys.executable)


PROJECT_ROOT = resolve_engel_app_root(__file__)
ENGEL_PYTHON = _resolve_engel_python_executable(__file__)
RUNTIME_ROOT = PROJECT_ROOT / "remote_workers" / "lan_link_manager"
STATE_PATH = RUNTIME_ROOT / "session_state.json"
LOG_PATH = RUNTIME_ROOT / "link_manager.log"
REPORT_DIR = PROJECT_ROOT / "reports" / "remote_worker_lan_link_manager"
LAN_RECEIVER_SCRIPT = PROJECT_ROOT / "engel_remote_worker_lan_pairing.py"
CLAIM_LOCK_VERIFIER = PROJECT_ROOT / "tools" / "verify_engel_remote_worker_claim_lock.py"

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
EXPECTED_WORKER_ID = "android_worker_alpha"
EXPECTED_WORKER_DEVICE = "engel_remote_worker_flutter"
RUST_LINK_MANAGER_BRIDGE_ENV = "ENGEL_REMOTE_WORKER_LINK_MANAGER_RUST_BRIDGE"
RUST_LINK_MANAGER_STRICT_ENV = "ENGEL_REMOTE_WORKER_LINK_MANAGER_RUST_STRICT"
RUST_LINK_MANAGER_ROOT_ENV = "ENGEL_REMOTE_WORKER_LINK_MANAGER_RUST_ROOT"
RUST_LAN_ENDPOINT_BRIDGE_ENV = "ENGEL_REMOTE_WORKER_LAN_RUST_BRIDGE"
RUST_LAN_ENDPOINT_STRICT_ENV = "ENGEL_REMOTE_WORKER_LAN_RUST_STRICT"
RUST_LAN_ENDPOINT_ROOT_ENV = "ENGEL_REMOTE_WORKER_LAN_RUST_ROOT"
RUST_EXE_ENV = "ENGEL_AI_RS_EXE"

ALLOWED_PHONE_CONTROLS = [
    "status_request",
    "check_now",
    "enable_auto_worker",
    "disable_auto_worker",
    "pause_worker",
    "rotate_session_notice",
    "assignment_available",
]

BLOCKED_PHONE_CONTROLS = [
    "execute_command",
    "run_route",
    "apply_patch",
    "write_memory",
    "mutate_source",
    "mutate_routes",
    "mutate_queue",
    "provider_call",
    "browser_task",
    "install_package",
    "download",
    "trust_result",
]


class LinkManagerError(ValueError):
    pass


def _truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _env_truthy(name: str) -> bool:
    return _truthy(os.environ.get(name))


def rust_lan_link_bridge_env_enabled() -> bool:
    return _env_truthy(RUST_LINK_MANAGER_BRIDGE_ENV)


def rust_lan_link_bridge_enabled(state: dict[str, Any] | None = None) -> bool:
    if rust_lan_link_bridge_env_enabled():
        return True
    state = state or load_state()
    return _truthy(state.get("rust_link_manager_bridge_enabled"))


def rust_lan_link_bridge_strict_enabled(state: dict[str, Any] | None = None) -> bool:
    if _env_truthy(RUST_LINK_MANAGER_STRICT_ENV):
        return True
    state = state or load_state()
    return _truthy(state.get("rust_link_manager_bridge_strict"))


def rust_link_control(action: str) -> dict[str, Any] | None:
    state = load_state()
    if not rust_lan_link_bridge_enabled(state):
        return None
    strict = rust_lan_link_bridge_strict_enabled(state)
    try:
        from engel_rust_lan_link_bridge import run_link_control

        bridge_root = Path(os.environ.get(RUST_LINK_MANAGER_ROOT_ENV, "").strip() or PROJECT_ROOT)
        payload = run_link_control(action, force=True, bridge_root=bridge_root, strict=strict)
        if payload is not None:
            payload.setdefault("bridge", "python-link-manager-rust-lan-link")
            payload.setdefault(
                "bridge_source",
                "environment" if rust_lan_link_bridge_env_enabled() else "persistent_state",
            )
        return payload
    except Exception as exc:  # pragma: no cover - strict verifier covers the happy path.
        if strict:
            return {
                "ok": False,
                "status": "rust_link_bridge_unavailable",
                "status_code": 503,
                "runtime": "engel-ai-rs",
                "bridge": "python-link-manager-rust-lan-link",
                "reason": f"Rust LAN link bridge failed: {exc}",
                "phone_does_not_control_engel": True,
                "direct_control": False,
                "trusted_memory_write": False,
                "auto_apply": False,
                "safe_to_auto_apply": False,
            }
        return None


def rust_link_process_control(action: str, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, allow_lan: bool = False) -> dict[str, Any] | None:
    state = load_state()
    if not rust_lan_link_bridge_enabled(state):
        return None
    strict = rust_lan_link_bridge_strict_enabled(state)
    try:
        from engel_rust_lan_link_bridge import run_link_process_control

        bridge_root = Path(os.environ.get(RUST_LINK_MANAGER_ROOT_ENV, "").strip() or PROJECT_ROOT)
        payload = run_link_process_control(
            action,
            host=host,
            port=port,
            allow_lan=allow_lan,
            force=True,
            bridge_root=bridge_root,
            strict=strict,
        )
        if payload is not None:
            payload.setdefault("bridge", "python-link-manager-rust-lan-link")
            payload.setdefault("bridge_process_control", True)
            payload.setdefault(
                "bridge_source",
                "environment" if rust_lan_link_bridge_env_enabled() else "persistent_state",
            )
        return payload
    except Exception as exc:  # pragma: no cover - verifier covers the happy path.
        if strict:
            return {
                "ok": False,
                "status": "rust_link_process_control_bridge_unavailable",
                "status_code": 503,
                "runtime": "engel-ai-rs",
                "bridge": "python-link-manager-rust-lan-link",
                "bridge_process_control": True,
                "reason": f"Rust LAN link process-control bridge failed: {exc}",
                "phone_does_not_control_engel": True,
                "direct_control": False,
                "trusted_memory_write": False,
                "auto_apply": False,
                "safe_to_auto_apply": False,
            }
        return None


def _rust_executable() -> Path | None:
    configured = os.environ.get(RUST_EXE_ENV, "").strip()
    if configured:
        candidate = Path(configured)
        if candidate.is_file():
            return candidate
    candidates = [
        PROJECT_ROOT / "rust" / "engel-core-rs" / "target" / "debug" / "engel-ai-rs.exe",
        PROJECT_ROOT / "rust" / "engel-core-rs" / "target" / "release" / "engel-ai-rs.exe",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def receiver_bridge_env_overrides(state: dict[str, Any] | None = None) -> dict[str, str]:
    state = state or load_state()
    if not _truthy(state.get("rust_lan_endpoint_bridge_soak_enabled")):
        return {}
    env = {
        RUST_LAN_ENDPOINT_BRIDGE_ENV: "1",
        RUST_LAN_ENDPOINT_STRICT_ENV: "1" if _truthy(state.get("rust_lan_endpoint_bridge_strict", True)) else "0",
        RUST_LAN_ENDPOINT_ROOT_ENV: str(PROJECT_ROOT),
    }
    exe = _rust_executable()
    if exe is not None:
        env[RUST_EXE_ENV] = str(exe)
    return env


def receiver_environment(state: dict[str, Any] | None = None) -> dict[str, str]:
    env = os.environ.copy()
    env.update(receiver_bridge_env_overrides(state))
    return env


def _receiver_bridge_restart_required(state: dict[str, Any], running: bool) -> bool:
    if not running:
        return False
    desired = _truthy(state.get("rust_lan_endpoint_bridge_soak_enabled"))
    active = _truthy(state.get("receiver_rust_lan_endpoint_bridge_enabled"))
    return desired != active


def _apply_link_manager_bridge_status_fields(state: dict[str, Any]) -> None:
    saved_enabled = _truthy(state.get("rust_link_manager_bridge_enabled"))
    env_enabled = rust_lan_link_bridge_env_enabled()
    strict = _env_truthy(RUST_LINK_MANAGER_STRICT_ENV) or (
        saved_enabled and _truthy(state.get("rust_link_manager_bridge_strict"))
    )
    env_keys = [
        key
        for key in [RUST_LINK_MANAGER_BRIDGE_ENV, RUST_LINK_MANAGER_STRICT_ENV, RUST_LINK_MANAGER_ROOT_ENV, RUST_EXE_ENV]
        if os.environ.get(key) is not None
    ]
    state["rust_link_manager_bridge_enabled"] = saved_enabled
    state["rust_link_manager_bridge_strict"] = bool(strict)
    bridge_root = os.environ.get(RUST_LINK_MANAGER_ROOT_ENV, "").strip() or str(PROJECT_ROOT)
    state["rust_link_manager_bridge_root"] = bridge_root
    state["rust_link_manager_bridge_env_enabled"] = env_enabled
    state["rust_link_manager_bridge_effective_enabled"] = saved_enabled or env_enabled
    state["rust_link_manager_bridge_source"] = (
        "environment" if env_enabled else "persistent_state" if saved_enabled else "disabled"
    )
    state["rust_link_manager_bridge_env_keys"] = sorted(env_keys)
    state["rust_link_manager_bridge_available"] = _rust_executable() is not None
    state["rust_link_manager_bridge_actions"] = [
        "enable-auto-worker",
        "disable-auto-worker",
        "check-now",
        "start",
        "stop",
        "restart",
    ]


def _apply_bridge_status_fields(state: dict[str, Any], *, running: bool) -> None:
    enabled = _truthy(state.get("rust_lan_endpoint_bridge_soak_enabled"))
    state["rust_lan_endpoint_bridge_soak_enabled"] = enabled
    state["rust_lan_endpoint_bridge_strict"] = True if enabled else _truthy(
        state.get("rust_lan_endpoint_bridge_strict")
    )
    state["rust_lan_endpoint_bridge_root"] = str(PROJECT_ROOT)
    state["rust_lan_endpoint_bridge_env_keys"] = sorted(receiver_bridge_env_overrides(state).keys())
    state["rust_lan_endpoint_bridge_requires_receiver_restart"] = _receiver_bridge_restart_required(state, running)


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def timestamp_file(value: str | None = None) -> str:
    stamp = value or now_utc()
    return stamp.replace("-", "").replace(":", "").replace("+00:00", "Z")


def ensure_scaffold() -> None:
    RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)


def redacted_code(code: str | None) -> str | None:
    if not code:
        return None
    if len(code) <= 2:
        return "**"
    return "*" * (len(code) - 2) + code[-2:]


def safe_relative(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def default_state() -> dict[str, Any]:
    return {
        "manager": "Engel Remote Worker Link Manager",
        "phone_role": "Dedicated Engel Remote Worker",
        "control_direction": "Engel controls phone",
        "phone_does_not_control_engel": True,
        "link_status": "stopped",
        "host": DEFAULT_HOST,
        "port": DEFAULT_PORT,
        "allow_lan": False,
        "receiver_pid": None,
        "started_by_link_manager": False,
        "started_at_utc": None,
        "stopped_at_utc": None,
        "pairing_token_hint": None,
        "pairing_token_expires_at_utc": None,
        "paired_phone_identity": None,
        "last_seen_utc": None,
        "last_phone_status": None,
        "auto_worker_enabled": False,
        "auto_worker_paused": False,
        "check_now_requested": False,
        "claim_lock_status": claim_lock_status(),
        "lan_only": True,
        "auto_apply": False,
        "safe_to_auto_apply": False,
        "trusted_memory_write": False,
        "source_mutation": False,
        "route_mutation": False,
        "queue_mutation_from_phone": False,
        "provider_calls": False,
        "allowed_phone_controls": list(ALLOWED_PHONE_CONTROLS),
        "blocked_phone_controls": list(BLOCKED_PHONE_CONTROLS),
        "rust_link_manager_bridge_enabled": False,
        "rust_link_manager_bridge_strict": False,
        "rust_link_manager_bridge_root": str(PROJECT_ROOT),
        "rust_lan_endpoint_bridge_soak_enabled": False,
        "rust_lan_endpoint_bridge_strict": False,
        "rust_lan_endpoint_bridge_root": str(PROJECT_ROOT),
        "rust_lan_endpoint_bridge_env_keys": [],
        "rust_lan_endpoint_bridge_requires_receiver_restart": False,
        "receiver_rust_lan_endpoint_bridge_enabled": False,
    }


def load_state(path: Path | None = None) -> dict[str, Any]:
    path = path or STATE_PATH
    if not path.exists():
        return default_state()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default_state()
    if not isinstance(payload, dict):
        return default_state()
    state = default_state()
    state.update(payload)
    state["claim_lock_status"] = claim_lock_status()
    state["phone_does_not_control_engel"] = True
    state["auto_apply"] = False
    state["safe_to_auto_apply"] = False
    state["trusted_memory_write"] = False
    state["source_mutation"] = False
    state["route_mutation"] = False
    state["queue_mutation_from_phone"] = False
    state["provider_calls"] = False
    state["allowed_phone_controls"] = list(ALLOWED_PHONE_CONTROLS)
    state["blocked_phone_controls"] = list(BLOCKED_PHONE_CONTROLS)
    state["rust_link_manager_bridge_enabled"] = _truthy(state.get("rust_link_manager_bridge_enabled"))
    state["rust_link_manager_bridge_strict"] = _truthy(state.get("rust_link_manager_bridge_strict"))
    state["rust_link_manager_bridge_root"] = str(PROJECT_ROOT)
    state["rust_lan_endpoint_bridge_soak_enabled"] = _truthy(state.get("rust_lan_endpoint_bridge_soak_enabled"))
    state["rust_lan_endpoint_bridge_strict"] = _truthy(state.get("rust_lan_endpoint_bridge_strict"))
    state["rust_lan_endpoint_bridge_root"] = str(PROJECT_ROOT)
    state["rust_lan_endpoint_bridge_env_keys"] = sorted(receiver_bridge_env_overrides(state).keys())
    state["receiver_rust_lan_endpoint_bridge_enabled"] = _truthy(
        state.get("receiver_rust_lan_endpoint_bridge_enabled")
    )
    return state


def write_state(state: dict[str, Any], path: Path | None = None) -> None:
    path = path or STATE_PATH
    ensure_scaffold()
    safe_state = dict(state)
    safe_state.pop("pairing_code", None)
    safe_state.pop("receiver_running", None)
    safe_state.pop("receiver_health_ok", None)
    safe_state.pop("receiver_environment", None)
    safe_state.pop("rust_lan_endpoint_bridge_env", None)
    safe_state.pop("rust_link_manager_bridge_effective_enabled", None)
    safe_state.pop("rust_link_manager_bridge_env_enabled", None)
    safe_state.pop("rust_link_manager_bridge_env_keys", None)
    safe_state.pop("rust_link_manager_bridge_source", None)
    safe_state.pop("rust_link_manager_bridge_available", None)
    safe_state["phone_does_not_control_engel"] = True
    safe_state["auto_apply"] = False
    safe_state["safe_to_auto_apply"] = False
    safe_state["trusted_memory_write"] = False
    safe_state["source_mutation"] = False
    safe_state["route_mutation"] = False
    safe_state["queue_mutation_from_phone"] = False
    safe_state["provider_calls"] = False
    safe_state["allowed_phone_controls"] = list(ALLOWED_PHONE_CONTROLS)
    safe_state["blocked_phone_controls"] = list(BLOCKED_PHONE_CONTROLS)
    safe_state["rust_link_manager_bridge_enabled"] = _truthy(safe_state.get("rust_link_manager_bridge_enabled"))
    safe_state["rust_link_manager_bridge_strict"] = _truthy(safe_state.get("rust_link_manager_bridge_strict"))
    safe_state["rust_link_manager_bridge_root"] = str(PROJECT_ROOT)
    safe_state["rust_lan_endpoint_bridge_soak_enabled"] = _truthy(
        safe_state.get("rust_lan_endpoint_bridge_soak_enabled")
    )
    safe_state["rust_lan_endpoint_bridge_strict"] = _truthy(safe_state.get("rust_lan_endpoint_bridge_strict"))
    safe_state["rust_lan_endpoint_bridge_root"] = str(PROJECT_ROOT)
    safe_state["rust_lan_endpoint_bridge_env_keys"] = sorted(receiver_bridge_env_overrides(safe_state).keys())
    safe_state["receiver_rust_lan_endpoint_bridge_enabled"] = _truthy(
        safe_state.get("receiver_rust_lan_endpoint_bridge_enabled")
    )
    path.write_text(json.dumps(safe_state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def claim_lock_status() -> str:
    return "present" if CLAIM_LOCK_VERIFIER.exists() else "missing"


def process_running(pid: Any) -> bool:
    try:
        number = int(pid)
    except (TypeError, ValueError):
        return False
    if number <= 0:
        return False
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        open_process = kernel32.OpenProcess
        open_process.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        open_process.restype = wintypes.HANDLE
        get_exit_code_process = kernel32.GetExitCodeProcess
        get_exit_code_process.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        get_exit_code_process.restype = wintypes.BOOL
        close_handle = kernel32.CloseHandle
        close_handle.argtypes = [wintypes.HANDLE]
        close_handle.restype = wintypes.BOOL

        process_query_limited_information = 0x1000
        still_active = 259
        handle = open_process(process_query_limited_information, False, number)
        if not handle:
            return False
        try:
            exit_code = wintypes.DWORD()
            if not get_exit_code_process(handle, ctypes.byref(exit_code)):
                return False
            return exit_code.value == still_active
        finally:
            close_handle(handle)
    try:
        os.kill(number, 0)  # windows-footgun: ok - POSIX-only branch after os.name != "nt"
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except (OSError, SystemError):
        return False
    return True


def receiver_command(host: str, port: int, allow_lan: bool) -> list[str]:
    command = [
        str(ENGEL_PYTHON),
        "-u",
        str(LAN_RECEIVER_SCRIPT),
        "serve",
        "--host",
        host,
        "--port",
        str(port),
    ]
    if allow_lan:
        command.append("--allow-lan")
    return command


def validate_start(host: str, port: int, allow_lan: bool) -> None:
    ok, reason = lan_pairing.validate_bind(host, allow_lan)
    if not ok:
        if "--allow-lan" not in reason:
            reason = "LAN bind requires --allow-lan"
        raise LinkManagerError(reason)
    if port < 1 or port > 65535:
        raise LinkManagerError("port must be between 1 and 65535")


def write_receipt(action: str, details: dict[str, Any]) -> Path:
    ensure_scaffold()
    stamp = now_utc()
    safe_action = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in action)[:60]
    path = REPORT_DIR / f"REMOTE_WORKER_LINK_MANAGER_{timestamp_file(stamp)}_{safe_action}.md"
    details = dict(details)
    details.pop("pairing_code", None)
    text = [
        f"# Remote Worker Link Manager {action}",
        "",
        f"- timestamp_utc: `{stamp}`",
        f"- action: `{action}`",
        f"- phone_role: `Dedicated Engel Remote Worker`",
        f"- control_direction: `Engel controls phone`",
        f"- phone_does_not_control_engel: `true`",
        f"- auto_apply: `false`",
        f"- trusted_memory_write: `false`",
        f"- source_route_queue_mutation_from_phone: `false`",
        "",
        "Details:",
        "```json",
        json.dumps(details, indent=2, sort_keys=True),
        "```",
        "",
        "This receipt does not contain a full pairing token or session secret.",
    ]
    path.write_text("\n".join(text) + "\n", encoding="utf-8")
    return path


def _sync_external_receiver(host: str, port: int, allow_lan: bool) -> dict[str, Any]:
    """Mark the link running when /health is up but this manager does not own the PID."""
    state = load_state()
    state.update(
        {
            "link_status": "running",
            "host": host,
            "port": int(port),
            "allow_lan": bool(allow_lan),
            "started_by_link_manager": False,
            "stopped_at_utc": None,
            "receiver_rust_lan_endpoint_bridge_enabled": False,
        }
    )
    if not process_running(state.get("receiver_pid")):
        state["receiver_pid"] = None
    write_state(state)
    return link_status()


def _wait_for_receiver_health(host: str, port: int, *, attempts: int = 30, delay: float = 0.1) -> bool:
    for _ in range(attempts):
        if lan_pairing.probe_receiver_health(host, port):
            return True
        time.sleep(delay)
    return False


def _receiver_health_ok(host: str, port: int) -> bool:
    """Probe /health with a short retry so a busy receiver is not marked dead."""
    return _wait_for_receiver_health(host, port, attempts=3, delay=0.2)


def link_status() -> dict[str, Any]:
    ensure_scaffold()
    state = load_state()
    pid_running = process_running(state.get("receiver_pid"))
    host = str(state.get("host") or DEFAULT_HOST)
    port = int(state.get("port") or DEFAULT_PORT)
    health_ok = _receiver_health_ok(host, port)
    running = pid_running or health_ok
    if health_ok and state.get("link_status") != "running":
        state["link_status"] = "running"
        state["host"] = host
        state["port"] = port
        state["stopped_at_utc"] = None
        if not process_running(state.get("receiver_pid")):
            state["receiver_pid"] = None
            state["started_by_link_manager"] = False
        write_state(state)
    elif not running and state.get("link_status") == "running":
        state["link_status"] = "stopped"
        state["stopped_at_utc"] = now_utc()
        state["receiver_pid"] = None
        state["started_by_link_manager"] = False
        write_state(state)
    state["receiver_running"] = running
    state["receiver_health_ok"] = health_ok
    _apply_link_manager_bridge_status_fields(state)
    _apply_bridge_status_fields(state, running=running)
    state["runtime_state_path"] = safe_relative(STATE_PATH)
    state["runtime_log_path"] = safe_relative(LOG_PATH)
    state["report_dir"] = safe_relative(REPORT_DIR)
    state["background_autostart"] = False
    state["windows_service"] = False
    state["scheduled_task"] = False
    state["firewall_automation"] = False
    state["cloud_relay"] = False
    return state


def start_link(host: str, port: int, allow_lan: bool) -> dict[str, Any]:
    bridged = rust_link_process_control("start", host, port, allow_lan)
    if bridged is not None:
        return bridged
    ensure_scaffold()
    validate_start(host, port, allow_lan)
    if _receiver_health_ok(host, port):
        return _sync_external_receiver(host, port, allow_lan)
    state = link_status()
    if state.get("receiver_running"):
        if state.get("receiver_health_ok"):
            raise LinkManagerError("link is already running; stop or restart it first")
        if not _wait_for_receiver_health(host, port, attempts=10, delay=0.2):
            stop_link()

    command = receiver_command(host, port, allow_lan)
    bridge_env = receiver_bridge_env_overrides(state)
    receiver_env = receiver_environment(state)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    log_handle = LOG_PATH.open("a", encoding="utf-8")
    log_handle.write(f"\n[{now_utc()}] starting managed receiver: {json.dumps(command)}\n")
    if bridge_env:
        log_handle.write(f"[{now_utc()}] managed receiver Rust bridge env keys: {json.dumps(sorted(bridge_env.keys()))}\n")
    log_handle.flush()
    creationflags = 0
    if os.name == "nt" and hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP"):
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
    process = subprocess.Popen(
        command,
        cwd=str(PROJECT_ROOT),
        stdin=subprocess.DEVNULL,
        stdout=log_handle,
        stderr=log_handle,
        env=receiver_env,
        shell=False,
        creationflags=creationflags,
    )
    if _wait_for_receiver_health(host, port):
        if process.poll() is not None:
            return _sync_external_receiver(host, port, allow_lan)
    elif process.poll() is not None:
        raise LinkManagerError("managed LAN receiver exited immediately; see link_manager.log")
    state.update(
        {
            "link_status": "running",
            "host": host,
            "port": port,
            "allow_lan": bool(allow_lan),
            "receiver_pid": process.pid,
            "receiver_command": command,
            "receiver_rust_lan_endpoint_bridge_enabled": bool(bridge_env),
            "rust_lan_endpoint_bridge_env_keys": sorted(bridge_env.keys()),
            "rust_lan_endpoint_bridge_requires_receiver_restart": False,
            "started_by_link_manager": True,
            "started_at_utc": now_utc(),
            "stopped_at_utc": None,
        }
    )
    write_state(state)
    receipt = write_receipt(
        "start",
        {
            "host": host,
            "port": port,
            "allow_lan": allow_lan,
            "receiver_pid": process.pid,
            "rust_lan_endpoint_bridge_soak_enabled": bool(bridge_env),
            "rust_lan_endpoint_bridge_env_keys": sorted(bridge_env.keys()),
        },
    )
    state["receipt_path"] = safe_relative(receipt)
    return link_status()


def stop_link() -> dict[str, Any]:
    bridged = rust_link_process_control("stop")
    if bridged is not None:
        return bridged
    ensure_scaffold()
    state = load_state()
    pid = state.get("receiver_pid")
    if state.get("started_by_link_manager") is not True:
        state["link_status"] = "stopped"
        state["receiver_pid"] = None
        state["receiver_rust_lan_endpoint_bridge_enabled"] = False
        write_state(state)
        return link_status()
    if process_running(pid):
        os.kill(int(pid), signal.SIGTERM)
        for _ in range(20):
            if not process_running(pid):
                break
            time.sleep(0.1)
    state["link_status"] = "stopped"
    state["receiver_pid"] = None
    state["stopped_at_utc"] = now_utc()
    state["started_by_link_manager"] = False
    state["receiver_rust_lan_endpoint_bridge_enabled"] = False
    write_state(state)
    write_receipt("stop", {"stopped_pid": pid})
    return link_status()


def restart_link(host: str, port: int, allow_lan: bool) -> dict[str, Any]:
    bridged = rust_link_process_control("restart", host, port, allow_lan)
    if bridged is not None:
        return bridged
    stop_link()
    return start_link(host, port, allow_lan)


def ensure_receiver_running(host: str, port: int, allow_lan: bool = True) -> dict[str, Any]:
    """Start or restart the LAN receiver until /health responds on host:port."""
    if _receiver_health_ok(host, port):
        state = link_status()
        if str(state.get("host") or "") == host and int(state.get("port") or 0) == int(port):
            if state.get("receiver_health_ok"):
                return state
        return _sync_external_receiver(host, port, allow_lan)
    state = link_status()
    if state.get("receiver_running") and state.get("receiver_health_ok"):
        if str(state.get("host") or "") == host and int(state.get("port") or 0) == int(port):
            return state
    if state.get("receiver_running") and not _wait_for_receiver_health(host, port, attempts=10, delay=0.2):
        stop_link()
    try:
        return start_link(host, port, allow_lan)
    except LinkManagerError:
        if _receiver_health_ok(host, port):
            return _sync_external_receiver(host, port, allow_lan)
        raise


def rotate_token() -> dict[str, Any]:
    """Force-rotate to a fresh pairing token. Invalidates any current
    pairing on a phone. Use this only for deliberate re-pair flows
    (e.g. "connect android workers usb", explicit "rotate code")."""
    ensure_scaffold()
    session = lan_pairing.create_pairing_session()
    return _record_token(session, rotated=True)


def ensure_session_token() -> dict[str, Any]:
    """Return the active pairing token, reusing the current session until it
    actually expires. Use on "show pairing code", "connect android workers",
    and provisioning so phones stay paired for multi-hour runs (6h+)."""
    ensure_scaffold()
    existing = lan_pairing.load_pairing_session()
    reused = existing is not None and not existing.is_expired()
    session = existing if reused else lan_pairing.get_or_create_session()
    return _record_token(session, rotated=not reused)


def _record_token(session: "lan_pairing.PairingSession", *, rotated: bool) -> dict[str, Any]:
    state = load_state()
    state["pairing_token_hint"] = redacted_code(session.pairing_code)
    state["pairing_token_expires_at_utc"] = session.expires_at_utc
    if rotated:
        state["last_token_rotated_at_utc"] = now_utc()
    state["last_token_observed_at_utc"] = now_utc()
    write_state(state)
    write_receipt(
        "token",
        {
            "pairing_token_hint": redacted_code(session.pairing_code),
            "pairing_token_expires_at_utc": session.expires_at_utc,
            "rotated": rotated,
        },
    )
    return {
        "pairing_code": session.pairing_code,
        "pairing_token_hint": redacted_code(session.pairing_code),
        "expires_at_utc": session.expires_at_utc,
        "rotated": rotated,
        "phone_role": "Dedicated Engel Remote Worker",
        "control_direction": "Engel controls phone",
        "phone_does_not_control_engel": True,
    }


def update_control_state(**updates: Any) -> dict[str, Any]:
    state = load_state()
    state.update(updates)
    state["updated_at_utc"] = now_utc()
    write_state(state)
    return link_status()


def rust_control_bridge_status() -> dict[str, Any]:
    state = link_status()
    return {
        "ok": True,
        "runtime": "python-link-manager",
        "bridge_target_runtime": "engel-ai-rs",
        "mode": "rust_link_manager_control_bridge_status",
        "rust_link_manager_bridge_enabled": state.get("rust_link_manager_bridge_enabled"),
        "rust_link_manager_bridge_effective_enabled": state.get("rust_link_manager_bridge_effective_enabled"),
        "rust_link_manager_bridge_strict": state.get("rust_link_manager_bridge_strict"),
        "rust_link_manager_bridge_source": state.get("rust_link_manager_bridge_source"),
        "rust_link_manager_bridge_root": state.get("rust_link_manager_bridge_root"),
        "rust_link_manager_bridge_env_enabled": state.get("rust_link_manager_bridge_env_enabled"),
        "rust_link_manager_bridge_env_keys": state.get("rust_link_manager_bridge_env_keys"),
        "rust_link_manager_bridge_available": state.get("rust_link_manager_bridge_available"),
        "rust_link_manager_bridge_actions": state.get("rust_link_manager_bridge_actions"),
        "phone_does_not_control_engel": True,
        "auto_apply": False,
        "trusted_memory_write": False,
        "safe_to_auto_apply": False,
    }


def enable_rust_control_bridge() -> dict[str, Any]:
    state = load_state()
    state["rust_link_manager_bridge_enabled"] = True
    state["rust_link_manager_bridge_strict"] = True
    state["rust_link_manager_bridge_root"] = str(PROJECT_ROOT)
    state["updated_at_utc"] = now_utc()
    write_state(state)
    status = rust_control_bridge_status()
    write_receipt(
        "enable-rust-control-bridge",
        {
            "rust_link_manager_bridge_enabled": True,
            "rust_link_manager_bridge_effective_enabled": status.get(
                "rust_link_manager_bridge_effective_enabled"
            ),
            "rust_link_manager_bridge_strict": status.get("rust_link_manager_bridge_strict"),
            "rust_link_manager_bridge_available": status.get("rust_link_manager_bridge_available"),
            "rust_link_manager_bridge_actions": status.get("rust_link_manager_bridge_actions"),
        },
    )
    return status


def disable_rust_control_bridge() -> dict[str, Any]:
    state = load_state()
    state["rust_link_manager_bridge_enabled"] = False
    state["rust_link_manager_bridge_strict"] = False
    state["updated_at_utc"] = now_utc()
    write_state(state)
    status = rust_control_bridge_status()
    write_receipt(
        "disable-rust-control-bridge",
        {
            "rust_link_manager_bridge_enabled": False,
            "rust_link_manager_bridge_effective_enabled": status.get(
                "rust_link_manager_bridge_effective_enabled"
            ),
            "rust_link_manager_bridge_env_enabled": status.get("rust_link_manager_bridge_env_enabled"),
        },
    )
    return status


def rust_bridge_soak_status() -> dict[str, Any]:
    state = link_status()
    return {
        "ok": True,
        "runtime": "python-link-manager",
        "bridge_target_runtime": "engel-ai-rs",
        "mode": "rust_lan_endpoint_bridge_soak_status",
        "rust_lan_endpoint_bridge_soak_enabled": state.get("rust_lan_endpoint_bridge_soak_enabled"),
        "rust_lan_endpoint_bridge_strict": state.get("rust_lan_endpoint_bridge_strict"),
        "rust_lan_endpoint_bridge_root": state.get("rust_lan_endpoint_bridge_root"),
        "rust_lan_endpoint_bridge_env_keys": state.get("rust_lan_endpoint_bridge_env_keys"),
        "rust_lan_endpoint_bridge_requires_receiver_restart": state.get(
            "rust_lan_endpoint_bridge_requires_receiver_restart"
        ),
        "receiver_running": state.get("receiver_running"),
        "receiver_health_ok": state.get("receiver_health_ok"),
        "receiver_rust_lan_endpoint_bridge_enabled": state.get("receiver_rust_lan_endpoint_bridge_enabled"),
        "phone_does_not_control_engel": True,
        "auto_apply": False,
        "trusted_memory_write": False,
        "safe_to_auto_apply": False,
    }


def enable_rust_bridge_soak() -> dict[str, Any]:
    state = load_state()
    state["rust_lan_endpoint_bridge_soak_enabled"] = True
    state["rust_lan_endpoint_bridge_strict"] = True
    state["rust_lan_endpoint_bridge_root"] = str(PROJECT_ROOT)
    state["rust_lan_endpoint_bridge_env_keys"] = sorted(receiver_bridge_env_overrides(state).keys())
    state["updated_at_utc"] = now_utc()
    write_state(state)
    status = rust_bridge_soak_status()
    write_receipt(
        "enable-rust-bridge-soak",
        {
            "rust_lan_endpoint_bridge_soak_enabled": True,
            "rust_lan_endpoint_bridge_env_keys": status.get("rust_lan_endpoint_bridge_env_keys"),
            "rust_lan_endpoint_bridge_requires_receiver_restart": status.get(
                "rust_lan_endpoint_bridge_requires_receiver_restart"
            ),
        },
    )
    return status


def disable_rust_bridge_soak() -> dict[str, Any]:
    state = load_state()
    state["rust_lan_endpoint_bridge_soak_enabled"] = False
    state["rust_lan_endpoint_bridge_strict"] = False
    state["rust_lan_endpoint_bridge_env_keys"] = []
    state["updated_at_utc"] = now_utc()
    write_state(state)
    status = rust_bridge_soak_status()
    write_receipt(
        "disable-rust-bridge-soak",
        {
            "rust_lan_endpoint_bridge_soak_enabled": False,
            "rust_lan_endpoint_bridge_env_keys": [],
            "rust_lan_endpoint_bridge_requires_receiver_restart": status.get(
                "rust_lan_endpoint_bridge_requires_receiver_restart"
            ),
        },
    )
    return status


def enable_auto_worker() -> dict[str, Any]:
    bridged = rust_link_control("enable-auto-worker")
    if bridged is not None:
        return bridged
    if claim_lock_status() != "present":
        raise LinkManagerError("claim-lock verifier is missing; unattended Auto Worker remains disabled")
    return update_control_state(auto_worker_enabled=True, auto_worker_paused=False, check_now_requested=True)


def disable_auto_worker() -> dict[str, Any]:
    bridged = rust_link_control("disable-auto-worker")
    if bridged is not None:
        return bridged
    return update_control_state(auto_worker_enabled=False, auto_worker_paused=True, check_now_requested=False)


def check_now() -> dict[str, Any]:
    bridged = rust_link_control("check-now")
    if bridged is not None:
        return bridged
    return update_control_state(check_now_requested=True, last_check_now_requested_at_utc=now_utc())


def record_phone_seen(payload: dict[str, Any] | None = None, remote_address: str = "local") -> dict[str, Any]:
    state = load_state()
    identity = {
        "worker_id": EXPECTED_WORKER_ID,
        "worker_device": EXPECTED_WORKER_DEVICE,
        "remote_address": remote_address,
    }
    if isinstance(payload, dict):
        identity["worker_device"] = str(payload.get("worker_device") or EXPECTED_WORKER_DEVICE)
        if payload.get("worker_id"):
            identity["worker_id"] = str(payload.get("worker_id"))
        for optional in ["app_version", "platform", "battery_level", "current_mode"]:
            if payload.get(optional) is not None:
                identity[optional] = payload.get(optional)
    state["paired_phone_identity"] = identity
    state["last_seen_utc"] = now_utc()
    state["last_phone_status"] = {
        "requires_review": True,
        "safe_to_auto_apply": False,
        "trust_level": "untrusted_until_engel_review",
        "phone_does_not_control_engel": True,
    }
    write_state(state)
    return state


def phone_control_payload() -> dict[str, Any]:
    state = load_state()
    return {
        "link_manager": "Engel Dedicated Phone Link",
        "phone_role": "Dedicated Engel Remote Worker",
        "control_direction": "Engel controls phone",
        "phone_does_not_control_engel": True,
        "lan_only": True,
        "auto_worker_enabled": bool(state.get("auto_worker_enabled")),
        "auto_worker_paused": bool(state.get("auto_worker_paused")),
        "check_now_requested": bool(state.get("check_now_requested")),
        "claim_lock_status": claim_lock_status(),
        "allowed_control_messages": list(ALLOWED_PHONE_CONTROLS),
        "blocked_control_messages": list(BLOCKED_PHONE_CONTROLS),
        "requires_review": True,
        "safe_to_auto_apply": False,
        "auto_apply": False,
        "trusted_memory_write": False,
    }


def render_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True)


def status_text() -> str:
    return render_json(link_status())


def pair_status_text() -> str:
    payload = lan_pairing.status_payload()
    payload["link_manager"] = phone_control_payload()
    return render_json(payload)


def phone_status_text() -> str:
    state = link_status()
    return render_json(
        {
            "phone_role": "Dedicated Engel Remote Worker",
            "control_direction": "Engel controls phone",
            "phone_does_not_control_engel": True,
            "paired_phone_identity": state.get("paired_phone_identity"),
            "last_seen_utc": state.get("last_seen_utc"),
            "last_phone_status": state.get("last_phone_status"),
            "auto_worker_enabled": state.get("auto_worker_enabled"),
            "claim_lock_status": state.get("claim_lock_status"),
            "status_truth": "unknown_until_phone_foreground_request" if not state.get("last_seen_utc") else "last_seen_recorded",
            "safe_to_auto_apply": False,
            "auto_apply": False,
        }
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Engel-controlled dedicated phone Link Manager.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    start = sub.add_parser("start")
    start.add_argument("--host", default=DEFAULT_HOST)
    start.add_argument("--port", type=int, default=DEFAULT_PORT)
    start.add_argument("--allow-lan", action="store_true")
    sub.add_parser("stop")
    restart = sub.add_parser("restart")
    restart.add_argument("--host", default=DEFAULT_HOST)
    restart.add_argument("--port", type=int, default=DEFAULT_PORT)
    restart.add_argument("--allow-lan", action="store_true")
    sub.add_parser("token")
    sub.add_parser("pair-status")
    sub.add_parser("phone-status")
    sub.add_parser("enable-auto-worker")
    sub.add_parser("disable-auto-worker")
    sub.add_parser("check-now")
    sub.add_parser("rust-control-bridge-status")
    sub.add_parser("enable-rust-control-bridge")
    sub.add_parser("disable-rust-control-bridge")
    sub.add_parser("rust-bridge-soak-status")
    sub.add_parser("enable-rust-bridge-soak")
    sub.add_parser("disable-rust-bridge-soak")

    args = parser.parse_args(argv)
    try:
        if args.command == "status":
            print(status_text())
            return 0
        if args.command == "start":
            print(render_json(start_link(args.host, args.port, args.allow_lan)))
            return 0
        if args.command == "stop":
            print(render_json(stop_link()))
            return 0
        if args.command == "restart":
            print(render_json(restart_link(args.host, args.port, args.allow_lan)))
            return 0
        if args.command == "token":
            print(render_json(rotate_token()))
            return 0
        if args.command == "pair-status":
            print(pair_status_text())
            return 0
        if args.command == "phone-status":
            print(phone_status_text())
            return 0
        if args.command == "enable-auto-worker":
            print(render_json(enable_auto_worker()))
            return 0
        if args.command == "disable-auto-worker":
            print(render_json(disable_auto_worker()))
            return 0
        if args.command == "check-now":
            print(render_json(check_now()))
            return 0
        if args.command == "rust-control-bridge-status":
            print(render_json(rust_control_bridge_status()))
            return 0
        if args.command == "enable-rust-control-bridge":
            print(render_json(enable_rust_control_bridge()))
            return 0
        if args.command == "disable-rust-control-bridge":
            print(render_json(disable_rust_control_bridge()))
            return 0
        if args.command == "rust-bridge-soak-status":
            print(render_json(rust_bridge_soak_status()))
            return 0
        if args.command == "enable-rust-bridge-soak":
            print(render_json(enable_rust_bridge_soak()))
            return 0
        if args.command == "disable-rust-bridge-soak":
            print(render_json(disable_rust_bridge_soak()))
            return 0
    except LinkManagerError as exc:
        print(render_json({"ok": False, "error": str(exc), "auto_apply": False, "phone_does_not_control_engel": True}))
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
