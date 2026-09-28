from __future__ import annotations

import json
import os
from pathlib import Path
import socket
from typing import Any


ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
PROFILE = ROOT / "memory" / "ENGEL_MAIN_SERVER_MERGE_V1.json"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def merge_profile() -> dict[str, Any]:
    return _read_json(PROFILE)


def _server_field(profile: dict[str, Any], key: str, default: str = "") -> str:
    server = profile.get("server_runtime")
    if not isinstance(server, dict):
        server = {}
    return str(server.get(key) or default).strip()


def _server_port(profile: dict[str, Any]) -> int:
    env_value = os.environ.get("ENGEL_MAIN_SERVER_SSH_PORT", "").strip()
    value = env_value or _server_field(profile, "ssh_port", "24622")
    try:
        port = int(value)
    except ValueError:
        return 24622
    return port if 1 <= port <= 65535 else 24622


def tcp_reachable(host: str, port: int, timeout: float = 0.6) -> bool:
    if not host or port < 1 or port > 65535:
        return False
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def server_merge_status_payload(live_probe: bool = False) -> dict[str, Any]:
    profile = merge_profile()
    host = os.environ.get("ENGEL_MAIN_SERVER_HOST", "").strip() or _server_field(
        profile, "ssh_host", "192.0.2.50"
    )
    port = _server_port(profile)
    user = os.environ.get("ENGEL_MAIN_SERVER_SSH_USER", "").strip() or _server_field(
        profile, "ssh_user", "root"
    )
    runtime_root = os.environ.get("ENGEL_MAIN_SERVER_RUNTIME_ROOT", "").strip() or _server_field(
        profile, "runtime_root", "/opt/engel"
    )
    enabled_env = os.environ.get("ENGEL_MAIN_SERVER_ENABLED", "").strip().lower()
    enabled = enabled_env in {"1", "true", "yes", "on"} or bool(profile)
    reachable = tcp_reachable(host, port) if live_probe else None
    return {
        "schema": "engel_main_server_merge_status_v1",
        "ok": bool(enabled and host and port),
        "profile_present": PROFILE.exists(),
        "profile_path": str(PROFILE),
        "merge_status": str(profile.get("status") or ""),
        "enabled": enabled,
        "windows_controller_ui": str(
            (profile.get("windows_controller_app") or {}).get("current_release_exe")
            if isinstance(profile.get("windows_controller_app"), dict)
            else ""
        ),
        "server_peer": "engel-ai-main CT 246",
        "ct_id": 246,
        "ct_hostname": os.environ.get("ENGEL_MAIN_SERVER_CT_HOSTNAME", "").strip()
        or _server_field(profile, "ct_hostname", "engel-ai-main"),
        "ssh_host": host,
        "ssh_port": port,
        "ssh_user": user,
        "ssh_route": f"ssh {user}@{host} -p {port}",
        "runtime_root": runtime_root,
        "memory_path": _server_field(profile, "memory_path", "/opt/engel/memory"),
        "reports_path": _server_field(profile, "reports_path", "/opt/engel/reports/codex_bridge"),
        "tcp_probe_performed": live_probe,
        "tcp_reachable": reachable,
        "remote_readback_requires_ssh_auth": True,
        "storage_mutation_performed": False,
        "vault_mount_created": False,
        "background_worker_started": False,
    }


def render_server_merge_status(live_probe: bool = False) -> str:
    status = server_merge_status_payload(live_probe=live_probe)
    probe = status["tcp_reachable"]
    if probe is None:
        probe_text = "not probed"
    else:
        probe_text = "reachable" if probe else "not reachable"
    lines = [
        "# Engel Main Server Merge",
        "",
        "Status: " + (status["merge_status"] or "not registered"),
        "Enabled: " + ("YES" if status["enabled"] else "NO"),
        "Controller UI: " + (status["windows_controller_ui"] or "not recorded"),
        "Server peer: " + status["server_peer"],
        "SSH route: " + status["ssh_route"],
        "Runtime root: " + status["runtime_root"],
        "Memory path: " + status["memory_path"],
        "TCP probe: " + probe_text,
        "",
        "Safety:",
        "- No storage mutation.",
        "- No vault mount creation.",
        "- No background worker start.",
        "- Remote readback still requires SSH authentication.",
    ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    print(render_server_merge_status(live_probe=True))
