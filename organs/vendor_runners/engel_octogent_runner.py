"""Engel Octogent Runner - install, start, and stop the Octogent swarm UI.

Octogent: multi-agent orchestration web UI (TypeScript/Node, pnpm workspace).
API listens on http://localhost:8787 by default.

Safety: subprocess execution is human-initiated only; no auto-start on import.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

from engel_project_paths import resolve_engel_app_root

_APP_ROOT = resolve_engel_app_root(__file__)
_OCTOGENT_DIR = _APP_ROOT / "engel_octogent_main"
_PORT = int(os.environ.get("OCTOGENT_API_PORT", "8787"))
_WEB_PORT = int(os.environ.get("OCTOGENT_WEB_PORT", "5173"))
_PID_FILE = _APP_ROOT / "memory" / "octogent_server.pid"
_LOG_FILE = _APP_ROOT / "reports" / "octogent" / "octogent_dev.log"

_REQUIRED_NODE = 22
_REQUIRED_PNPM = 10


def _node_version() -> str:
    try:
        r = subprocess.run(["node", "--version"], capture_output=True, text=True, timeout=5)
        return r.stdout.strip()
    except Exception:
        return "not found"


def _pnpm_version() -> str:
    try:
        r = subprocess.run(["pnpm", "--version"], capture_output=True, text=True, timeout=5)
        return r.stdout.strip()
    except Exception:
        return "not found"


def _node_modules_ok() -> bool:
    return (_OCTOGENT_DIR / "node_modules").exists()


def _server_pid() -> int | None:
    try:
        pid_str = _PID_FILE.read_text(encoding="utf-8").strip()
        pid = int(pid_str)
        os.kill(pid, 0)
        return pid
    except Exception:
        return None


def _port_open(port: int) -> bool:
    import socket

    for host in ("127.0.0.1", "::1"):
        try:
            with socket.create_connection((host, int(port)), timeout=0.5):
                return True
        except OSError:
            pass
    return False


def _wait_for_port(port: int, timeout: float = 12.0) -> bool:
    deadline = time.time() + max(0.0, timeout)
    while time.time() < deadline:
        if _port_open(port):
            return True
        time.sleep(0.35)
    return _port_open(port)


def _api_url() -> str:
    return f"http://localhost:{_PORT}"


def _web_url() -> str:
    return f"http://localhost:{_WEB_PORT}"


def _ps_quote(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _listening_pids_for_ports(ports: list[int]) -> list[int]:
    if sys.platform != "win32":
        return []
    port_args = ",".join(str(int(port)) for port in ports)
    ps_script = (
        f"$ports=@({port_args}); "
        "Get-NetTCPConnection -State Listen -LocalPort $ports -ErrorAction SilentlyContinue "
        "| Select-Object -ExpandProperty OwningProcess -Unique"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        return []
    pids: list[int] = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            pid = int(line)
        except ValueError:
            continue
        if pid not in pids:
            pids.append(pid)
    return pids


def render_octogent_status() -> str:
    node_ver = _node_version()
    pnpm_ver = _pnpm_version()
    installed = _node_modules_ok()
    pid = _server_pid()
    web_up = _port_open(_WEB_PORT)
    api_up = _port_open(_PORT)
    port_pids = _listening_pids_for_ports([_WEB_PORT, _PORT]) if (web_up or api_up) else []
    if pid:
        pid_label = str(pid)
    elif port_pids:
        pid_label = "ports owned by " + ", ".join(str(item) for item in port_pids)
    else:
        pid_label = "not running"

    lines = [
        "# Engel Octogent - Status",
        "",
        f"Octogent dir:    {_OCTOGENT_DIR}",
        f"Dir present:     {'YES' if _OCTOGENT_DIR.exists() else 'NO'}",
        f"node_modules:    {'installed' if installed else 'NOT installed - run: engel.octogent.install'}",
        "",
        f"Node.js version: {node_ver}",
        f"pnpm version:    {pnpm_ver}",
        "",
        f"Server PID:      {pid_label}",
        f"Web dashboard:   {_web_url()}" + (" (UP)" if web_up else " (down)"),
        f"API backend:     {_api_url()}" + (" (UP; backend only)" if api_up else " (down)"),
        f"Log file:        {_LOG_FILE}",
        "",
        "Use: Octogent is Engel's multi-agent swarm dashboard. Open the web dashboard URL.",
        "Note: the API backend root can return {\"error\":\"Not found\"}; that is not the UI.",
        "",
        "Commands:",
        "  python engel_ai.py ask 'octogent install'  - pnpm install",
        "  python engel_ai.py ask 'octogent start'    - launch dev server",
        "  python engel_ai.py ask 'octogent stop'     - stop server",
    ]
    return "\n".join(lines)


def render_octogent_install() -> str:
    if not _OCTOGENT_DIR.exists():
        return f"Octogent dir not found: {_OCTOGENT_DIR}"

    lines = [
        "# Engel Octogent - Install",
        "",
        f"Running: pnpm install  (cwd: {_OCTOGENT_DIR})",
        "",
    ]
    try:
        result = subprocess.run(
            ["pnpm", "install", "--frozen-lockfile"],
            cwd=str(_OCTOGENT_DIR),
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            lines += [
                "Status: OK",
                "",
                "stdout:",
                result.stdout.strip() or "(empty)",
                "",
                "Ready to start: python engel_ai.py ask 'octogent start'",
            ]
        else:
            lines += [
                f"Status: ERROR (exit {result.returncode})",
                "",
                "stdout:", result.stdout.strip() or "(empty)",
                "stderr:", result.stderr.strip() or "(empty)",
                "",
                "Tip: try without --frozen-lockfile if lockfile is stale.",
            ]
    except subprocess.TimeoutExpired:
        lines.append("ERROR: pnpm install timed out after 120 seconds.")
    except FileNotFoundError:
        lines.append("ERROR: pnpm not found. Install pnpm: npm install -g pnpm")
    except Exception as exc:
        lines.append(f"ERROR: {exc}")

    return "\n".join(lines)


def render_octogent_start() -> str:
    if not _OCTOGENT_DIR.exists():
        return f"Octogent dir not found: {_OCTOGENT_DIR}"

    if not _node_modules_ok():
        return "\n".join([
            "Octogent: node_modules not installed.",
            "Run first: python engel_ai.py ask 'octogent install'",
        ])

    existing_pid = _server_pid()
    already_reachable = _port_open(_WEB_PORT) or _port_open(_PORT)
    if existing_pid or already_reachable:
        return "\n".join([
            "# Engel Octogent - Start",
            "",
            f"Server is already reachable (PID {existing_pid if existing_pid else 'managed by dev server child process'}).",
            f"Open web dashboard: {_web_url()}",
            f"API backend: {_api_url()} (backend only)",
        ])

    env = {
        **os.environ,
        "OCTOGENT_API_PORT": str(_PORT),
        "OCTOGENT_DEV_START_PORT": str(_PORT),
        "OCTOGENT_WORKSPACE_CWD": str(_OCTOGENT_DIR),
    }
    _LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    try:
        if sys.platform == "win32":
            _LOG_FILE.touch(exist_ok=True)
            cmd_line = f'pnpm dev >> "{_LOG_FILE}" 2>&1'
            ps_script = (
                "$ErrorActionPreference='Stop'; "
                "$p = Start-Process -FilePath $env:ComSpec "
                f"-ArgumentList @('/d','/c',{_ps_quote(cmd_line)}) "
                f"-WorkingDirectory {_ps_quote(str(_OCTOGENT_DIR))} "
                "-WindowStyle Hidden -PassThru; "
                "Write-Output $p.Id"
            )
            started = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
                cwd=str(_OCTOGENT_DIR),
                env=env,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if started.returncode != 0:
                return "\n".join([
                    "ERROR starting octogent with Windows background launcher.",
                    started.stdout.strip() or "(empty stdout)",
                    started.stderr.strip() or "(empty stderr)",
                ])
            pid_text = (started.stdout.strip().splitlines() or [""])[-1].strip()
            proc_pid = int(pid_text)
        else:
            log_handle = _LOG_FILE.open("a", encoding="utf-8")
            proc = subprocess.Popen(
                ["pnpm", "dev"],
                cwd=str(_OCTOGENT_DIR),
                env=env,
                stdout=log_handle,
                stderr=log_handle,
                start_new_session=True,
            )
            proc_pid = proc.pid

        _PID_FILE.parent.mkdir(parents=True, exist_ok=True)
        _PID_FILE.write_text(str(proc_pid), encoding="utf-8")
        web_ready = _wait_for_port(_WEB_PORT, timeout=12.0)
        api_ready = _wait_for_port(_PORT, timeout=2.0)

        return "\n".join([
            "# Engel Octogent - Start",
            "",
            f"Server launched (PID {proc_pid}).",
            f"Web dashboard: {_web_url()}" + (" (ready)" if web_ready else " (starting)"),
            f"API backend: {_api_url()}" + (" (ready; backend only)" if api_ready else " (starting; backend only)"),
            f"Log: {_LOG_FILE}",
            "",
            "Use: Octogent is Engel's multi-agent swarm dashboard. Open the web dashboard URL.",
            "Note: do not open the API backend root as the UI.",
            f"Open in browser: {_web_url()}",
            "",
            "To stop: python engel_ai.py ask 'octogent stop'",
        ])
    except FileNotFoundError:
        return "ERROR: pnpm not found. Install with: npm install -g pnpm"
    except Exception as exc:
        return f"ERROR starting octogent: {exc}"


def render_octogent_stop() -> str:
    pid = _server_pid()
    pids = [pid] if pid is not None else _listening_pids_for_ports([_WEB_PORT, _PORT])
    if not pids:
        return "Octogent: no server running (or PID file stale)."

    try:
        if sys.platform == "win32":
            for target_pid in pids:
                subprocess.run(["taskkill", "/PID", str(target_pid), "/T", "/F"],
                               capture_output=True, timeout=10)
        else:
            import signal
            for target_pid in pids:
                os.kill(target_pid, signal.SIGTERM)

        try:
            _PID_FILE.unlink()
        except Exception:
            pass

        return "Octogent: stopped server (" + ", ".join(f"PID {item}" for item in pids) + ")."
    except Exception as exc:
        return f"Octogent stop error: {exc}"
