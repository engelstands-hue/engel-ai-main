"""Engel AI ↔ bundled engel3d (3D virtual office) integration runner.

Backs the ``engel.engel3d.{status,start,stop,build}`` routes registered
in ``engel_ai_update_routes``. The vendored Next.js + React + Three.js
tree at ``D:\\b.WorkSpace\\Engel App\\engel3d_office_main`` is a fork of
Claw3D, case-preservingly renamed (claw3d→engel3d, OpenClaw→OpenEngel,
Hermes→Engel). It is the visualisation layer that pairs naturally with
the bundled engel_agent_main runtime (originally hermes-agent).

Per the 2026-05-19 ruling change, autonomy and background work are
permitted; the ``start`` route launches the Node.js dev server as a
detached background process and records its PID for ``stop`` to find.

Public surface (all return human-readable strings):

    render_engel3d_status()  — Node availability, deps state, server PID
    render_engel3d_start()   — npm run dev (detached background)
    render_engel3d_stop()    — terminate the recorded PID
    render_engel3d_build()   — npm install + next build (blocking)
"""
from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

OFFICE_ROOT: Path = Path(__file__).resolve().parent / "engel3d_office_main"
PID_FILE: Path = OFFICE_ROOT / ".engel3d_server.pid"
SERVER_LOG: Path = OFFICE_ROOT / ".engel3d_server.log"
DEFAULT_DEV_PORT = 3000


def _node_path() -> Optional[str]:
    return shutil.which("node")


def _npm_path() -> Optional[str]:
    return shutil.which("npm") or shutil.which("npm.cmd") or shutil.which("npm.ps1")


def _node_modules_present() -> bool:
    return (OFFICE_ROOT / "node_modules").is_dir()


def _read_pid() -> Optional[int]:
    if not PID_FILE.is_file():
        return None
    try:
        return int(PID_FILE.read_text(encoding="utf-8").strip())
    except (ValueError, OSError):
        return None


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform == "win32":
        try:
            out = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                capture_output=True, text=True, check=False, encoding="utf-8",
                errors="replace",
            )
            return str(pid) in (out.stdout or "")
        except OSError:
            return False
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def _kill_pid(pid: int) -> tuple[bool, str]:
    try:
        if sys.platform == "win32":
            proc = subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                capture_output=True, text=True, check=False,
                encoding="utf-8", errors="replace",
            )
            return proc.returncode == 0, (proc.stdout or proc.stderr or "").strip()
        os.kill(pid, signal.SIGTERM)
        time.sleep(0.5)
        if _pid_alive(pid):
            os.kill(pid, signal.SIGKILL)
        return True, f"sent SIGTERM to {pid}"
    except (OSError, ProcessLookupError) as exc:
        return False, str(exc)


def _wrap(title: str, body: str) -> str:
    return f"{title}\n\n{body}\n\nSafety:\n- engel3d office subprocess lifecycle managed via PID file.\n- Autonomy and background work permitted (2026-05-19 ruling).\n- No mutation of Engel App router state."


def _ensure_office_exists() -> Optional[str]:
    if not OFFICE_ROOT.is_dir():
        return _wrap(
            "Engel3D Office — not installed",
            f"Vendored tree missing at {OFFICE_ROOT}. Restore it and retry.",
        )
    return None


def render_engel3d_status(_payload: str = "") -> str:
    missing = _ensure_office_exists()
    if missing:
        return missing

    lines = [
        f"Office root            : {OFFICE_ROOT}",
        f"Node executable        : {_node_path() or 'NOT FOUND'}",
        f"npm executable         : {_npm_path()  or 'NOT FOUND'}",
        f"node_modules installed : {'yes' if _node_modules_present() else 'no (run engel3d build)'}",
    ]
    pid = _read_pid()
    if pid is None:
        lines.append("Dev server             : not running (no PID file)")
    elif _pid_alive(pid):
        lines.append(f"Dev server             : running (pid={pid}, log={SERVER_LOG})")
    else:
        lines.append(f"Dev server             : stale PID file (pid={pid} not alive)")
    lines.append(f"Default dev URL        : http://localhost:{DEFAULT_DEV_PORT}/")
    return _wrap("Engel3D Office — status", "\n".join(lines))


def render_engel3d_start(_payload: str = "") -> str:
    missing = _ensure_office_exists()
    if missing:
        return missing

    npm = _npm_path()
    if not npm:
        return _wrap(
            "Engel3D Office — start failed",
            "npm not found on PATH. Install Node.js / npm first.",
        )

    pid = _read_pid()
    if pid is not None and _pid_alive(pid):
        return _wrap(
            "Engel3D Office — already running",
            f"Existing dev server pid={pid}. Use 'engel3d stop' first to relaunch.",
        )

    if not _node_modules_present():
        return _wrap(
            "Engel3D Office — dependencies missing",
            "node_modules/ not present. Run 'engel3d build' first to install dependencies, then 'engel3d start'.",
        )

    # Detached background spawn. We use npm.cmd on Windows because PowerShell
    # cannot be detached cleanly via Popen, and npm.ps1 requires a PS host.
    if sys.platform == "win32":
        creationflags = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
        npm_cmd = shutil.which("npm.cmd") or npm
        cmd = [npm_cmd, "run", "dev"]
    else:
        creationflags = 0
        cmd = [npm, "run", "dev"]

    try:
        with open(SERVER_LOG, "wb") as logf:
            proc = subprocess.Popen(
                cmd,
                cwd=str(OFFICE_ROOT),
                stdout=logf,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                creationflags=creationflags if sys.platform == "win32" else 0,
                close_fds=True,
                shell=False,
            )
    except OSError as exc:
        return _wrap(
            "Engel3D Office — start failed",
            f"Could not spawn '{' '.join(cmd)}': {exc}",
        )

    PID_FILE.write_text(str(proc.pid), encoding="utf-8")
    return _wrap(
        "Engel3D Office — start initiated",
        (
            f"Launched dev server in background (pid={proc.pid}).\n"
            f"Working dir : {OFFICE_ROOT}\n"
            f"Log file    : {SERVER_LOG}\n"
            f"Open in browser once compiled: http://localhost:{DEFAULT_DEV_PORT}/\n"
            "Use 'engel3d status' to confirm the process is up; "
            "'engel3d stop' to terminate."
        ),
    )


def render_engel3d_stop(_payload: str = "") -> str:
    pid = _read_pid()
    if pid is None:
        return _wrap("Engel3D Office — nothing to stop", "No PID file present.")
    if not _pid_alive(pid):
        try:
            PID_FILE.unlink()
        except OSError:
            pass
        return _wrap(
            "Engel3D Office — already stopped",
            f"Stale PID file removed (pid={pid} was not alive).",
        )
    ok, detail = _kill_pid(pid)
    if ok:
        try:
            PID_FILE.unlink()
        except OSError:
            pass
        return _wrap("Engel3D Office — stopped", f"Terminated pid={pid}. {detail}")
    return _wrap("Engel3D Office — stop failed", f"Could not terminate pid={pid}: {detail}")


def render_engel3d_build(_payload: str = "") -> str:
    missing = _ensure_office_exists()
    if missing:
        return missing

    npm = _npm_path()
    if not npm:
        return _wrap(
            "Engel3D Office — build failed",
            "npm not found on PATH. Install Node.js / npm first.",
        )

    # Long-running blocking command. Capture combined output but cap at 8k.
    npm_cmd = shutil.which("npm.cmd") if sys.platform == "win32" else npm
    npm_cmd = npm_cmd or npm

    install = subprocess.run(
        [npm_cmd, "install"],
        cwd=str(OFFICE_ROOT),
        capture_output=True, text=True, check=False,
        encoding="utf-8", errors="replace",
    )
    if install.returncode != 0:
        return _wrap(
            "Engel3D Office — npm install failed",
            (install.stderr or install.stdout or "(no output)")[:8000],
        )

    build = subprocess.run(
        [npm_cmd, "run", "build"],
        cwd=str(OFFICE_ROOT),
        capture_output=True, text=True, check=False,
        encoding="utf-8", errors="replace",
    )
    if build.returncode != 0:
        return _wrap(
            "Engel3D Office — next build failed",
            (build.stderr or build.stdout or "(no output)")[:8000],
        )

    return _wrap(
        "Engel3D Office — build complete",
        (
            "npm install + next build finished cleanly.\n"
            "You can now run 'engel3d start' to launch the dev server."
        ),
    )
