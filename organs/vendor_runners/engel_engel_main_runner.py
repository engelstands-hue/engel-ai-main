"""Engel AI ↔ bundled engel_main (Tauri desktop AI companion) integration.

Backs the ``engel.engel_main.*`` routes registered in
``engel_ai_update_routes``. The vendored tree at
``D:\\b.WorkSpace\\Engel App\\engel_main`` is a fork of OpenHuman
(tinyhumansai/openhuman), case-preservingly rebranded
``openhuman → engel`` across all case variants (1,258 files
touched, 9,820 substitutions, 10 path renames).

Engel Main is a Tauri 2 desktop AI companion (Rust core +
pnpm/Vite/React frontend) with a desktop mascot, meeting
integration, and background thinking. The Rust crate name is
``engel`` (binary: ``engel-core``); the JS workspace package is
``engel-app``.

Runtime requirements:
  - Node.js >= 24 (already present)
  - pnpm 10+ from a non-C drive or ENGEL_PNPM_EXE
  - Rust toolchain (install via https://rustup.rs/) — only needed
    for ``tauri_build``; ``dev`` and ``build`` run the web layer
    only and can work without cargo.

Public surface:

    render_engel_main_status()      — toolchain + deps + dev server PID
    render_engel_main_version()     — app/package.json version
    render_engel_main_binaries()    — declared [[bin]] targets
    render_engel_main_install()     — pnpm install
    render_engel_main_dev_start()   — pnpm dev (detached Vite)
    render_engel_main_dev_stop()    — terminate dev server
    render_engel_main_build()       — pnpm build (web bundle)
    render_engel_main_tauri_build() — cargo tauri build (full desktop)
    render_engel_main_bring_up()    — toolchain install walkthrough
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

APP_ROOT: Path = Path(__file__).resolve().parent / "engel_main"
APP_PACKAGE: Path = APP_ROOT / "app"
PID_FILE: Path = APP_ROOT / ".engel_main_server.pid"
DEV_LOG: Path = APP_ROOT / ".engel_main_server.log"
DEFAULT_DEV_PORT = 5173  # Vite default
APPROVED_TEMP_ROOT = Path(r"D:\b.WorkSpace\Engel App\runtime\temp\engel-main")
APPROVED_CARGO_HOME = Path(r"D:\b.WorkSpace\Engel App\runtime\cargo-home")
APPROVED_ENGEL_HOME = Path(r"D:\b.WorkSpace\Engel App\runtime\engel-home")


def _path_on_os_drive(path: Path | str | None) -> bool:
    if path is None:
        return False
    text = str(path).replace("/", "\\").lower()
    return text.startswith("c:\\") or text.startswith("\\\\?\\c:\\")


def _approved_path(path: Path | str | None) -> Optional[str]:
    if not path:
        return None
    candidate = Path(path)
    if _path_on_os_drive(candidate):
        return None
    try:
        if candidate.is_file():
            return str(candidate)
    except OSError:
        return None
    return None


def _approved_env_exe(name: str) -> Optional[str]:
    return _approved_path(os.environ.get(name, "").strip())


def _join_approved_env_path(name: str, *parts: str) -> Optional[Path]:
    value = os.environ.get(name, "").strip()
    if not value:
        return None
    root = Path(value)
    if _path_on_os_drive(root):
        return None
    return root.joinpath(*parts)


def _which_approved(*names: str) -> Optional[str]:
    for name in names:
        approved = _approved_path(shutil.which(name))
        if approved:
            return approved
    return None


def _path_without_os_drive_entries() -> str:
    parts = []
    for item in os.environ.get("PATH", "").split(os.pathsep):
        if item and not _path_on_os_drive(item):
            parts.append(item)
    return os.pathsep.join(parts)


def _ensure_runtime_dirs() -> None:
    for path in (APPROVED_TEMP_ROOT, APPROVED_CARGO_HOME, APPROVED_ENGEL_HOME):
        path.mkdir(parents=True, exist_ok=True)


def _subprocess_env() -> dict[str, str]:
    _ensure_runtime_dirs()
    env = os.environ.copy()
    env.update(
        {
            "TEMP": str(APPROVED_TEMP_ROOT),
            "TMP": str(APPROVED_TEMP_ROOT),
            "TMPDIR": str(APPROVED_TEMP_ROOT),
            "CARGO_HOME": str(APPROVED_CARGO_HOME),
            "ENGEL_HOME": str(APPROVED_ENGEL_HOME),
            "HOME": str(APPROVED_ENGEL_HOME),
        }
    )
    env["PATH"] = _path_without_os_drive_entries()
    return env


def _node_path() -> Optional[str]:
    return _which_approved("node", "node.exe")


_PNPM_FALLBACKS = (
    _approved_env_exe("ENGEL_PNPM_EXE"),
)
_CARGO_FALLBACKS = (
    _approved_env_exe("ENGEL_CARGO_EXE"),
    _join_approved_env_path("CARGO_HOME", "bin", "cargo.exe"),
    APPROVED_CARGO_HOME / "bin" / "cargo.exe",
)


def _pnpm_path() -> Optional[str]:
    found = _which_approved("pnpm", "pnpm.cmd")
    if found:
        return found
    for p in _PNPM_FALLBACKS:
        approved = _approved_path(p)
        if approved:
            return approved
    return None


def _cargo_path() -> Optional[str]:
    found = _which_approved("cargo", "cargo.exe")
    if found:
        return found
    for p in _CARGO_FALLBACKS:
        approved = _approved_path(p)
        if approved:
            return approved
    return None


def _node_modules_present() -> bool:
    return (APP_ROOT / "node_modules").is_dir()


def _read_app_version() -> str:
    pkg = APP_PACKAGE / "package.json"
    if not pkg.is_file():
        return "(app/package.json missing)"
    try:
        data = json.loads(pkg.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return f"(read failed: {exc})"
    return str(data.get("version", "(no version field)"))


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
                capture_output=True, text=True, check=False,
                encoding="utf-8", errors="replace",
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
        import signal as _sig
        os.kill(pid, _sig.SIGTERM)
        return True, f"sent SIGTERM to {pid}"
    except (OSError, ProcessLookupError) as exc:
        return False, str(exc)


def _wrap(title: str, body: str, *, configured: bool = True) -> str:
    safety = [
        "Safety:",
        f"- Engel Main tree: {APP_ROOT}",
        "- Tauri desktop companion subprocess lifecycle managed via PID file.",
        "- C drive is OS-only; Engel Main toolchains and subprocess temp/cache/home use approved non-C roots.",
        "- Autonomy and background work permitted (2026-05-19 ruling).",
    ]
    if not configured:
        safety.append("- Ask 'engel main bring up' for full toolchain install steps.")
    return f"{title}\n\n{body}\n\n" + "\n".join(safety)


def _ensure_tree() -> Optional[str]:
    if not APP_ROOT.is_dir():
        return _wrap("Engel Main — tree missing", f"Vendored tree not found at {APP_ROOT}.", configured=False)
    return None


def render_engel_main_status(_payload: str = "") -> str:
    missing = _ensure_tree()
    if missing:
        return missing
    lines = [
        f"Tree root          : {APP_ROOT}",
        f"App package.json   : {APP_PACKAGE / 'package.json'} (version={_read_app_version()})",
        f"node executable    : {_node_path()  or 'NOT FOUND'}",
        f"pnpm executable    : {_pnpm_path()  or 'NOT FOUND (non-C pnpm required; C-side pnpm ignored)'}",
        f"cargo executable   : {_cargo_path() or 'NOT FOUND — only needed for tauri_build'}",
        f"node_modules       : {'yes' if _node_modules_present() else 'no (run engel main install)'}",
    ]
    pid = _read_pid()
    if pid is None:
        lines.append("Dev server         : not running (no PID file)")
    elif _pid_alive(pid):
        lines.append(f"Dev server         : running (pid={pid}, log={DEV_LOG})")
    else:
        lines.append(f"Dev server         : stale PID file (pid={pid} not alive)")
    lines.append(f"Default Vite port  : http://localhost:{DEFAULT_DEV_PORT}/")
    return _wrap("Engel Main — status", "\n".join(lines))


def render_engel_main_version(_payload: str = "") -> str:
    missing = _ensure_tree()
    if missing:
        return missing
    return _wrap("Engel Main — version", f"engel-app {_read_app_version()} (from app/package.json)")


def render_engel_main_binaries(_payload: str = "") -> str:
    missing = _ensure_tree()
    if missing:
        return missing
    cargo_toml = APP_ROOT / "Cargo.toml"
    if not cargo_toml.is_file():
        return _wrap("Engel Main — binaries", "Root Cargo.toml missing.")
    text = cargo_toml.read_text(encoding="utf-8", errors="replace")
    bins = re.findall(r"\[\[bin\]\][^\[]*?name\s*=\s*\"([^\"]+)\"", text, re.DOTALL)
    body = (
        "Declared [[bin]] targets:\n"
        + ("\n".join(f"  - {b}" for b in bins) if bins else "  (none)")
    )
    return _wrap("Engel Main — Rust binaries", body)


def _run_pnpm(action: str, argv: list[str], *, timeout: int = 600) -> str:
    missing = _ensure_tree()
    if missing:
        return missing
    pnpm = _pnpm_path()
    if not pnpm:
        return _wrap(
            f"Engel Main — {action} unavailable (pnpm missing)",
            (
                "pnpm is not on approved non-C PATH. Install or copy pnpm to a non-C drive,\n"
                "add that directory to PATH, or set ENGEL_PNPM_EXE to the non-C executable.\n"
                "C-side pnpm paths are ignored for Engel."
            ),
            configured=False,
        )
    proc = subprocess.run(
        [pnpm, *argv],
        cwd=str(APP_ROOT),
        capture_output=True, text=True, check=False,
        encoding="utf-8", errors="replace",
        env=_subprocess_env(),
        timeout=timeout,
    )
    if proc.returncode != 0:
        return _wrap(
            f"Engel Main — {action} failed (exit {proc.returncode})",
            ((proc.stderr or proc.stdout) or "(no output)")[-8000:],
        )
    body = (proc.stdout.rstrip() or proc.stderr.rstrip() or "(no output)")
    return _wrap(f"Engel Main — {action} complete", body[-8000:])


def render_engel_main_install(_payload: str = "") -> str:
    return _run_pnpm("pnpm install", ["install"], timeout=900)


def render_engel_main_build(_payload: str = "") -> str:
    if not _node_modules_present():
        return _wrap(
            "Engel Main — build prerequisite missing",
            "node_modules/ not present. Run 'engel main install' first.",
            configured=False,
        )
    return _run_pnpm("pnpm build (web bundle)", ["build"], timeout=900)


def render_engel_main_dev_start(_payload: str = "") -> str:
    missing = _ensure_tree()
    if missing:
        return missing
    pnpm = _pnpm_path()
    if not pnpm:
        return _wrap(
            "Engel Main — dev unavailable (pnpm missing)",
            "Install or point Engel to a non-C pnpm executable first; ask 'engel main bring up'.",
            configured=False,
        )
    if not _node_modules_present():
        return _wrap(
            "Engel Main — dev prerequisite missing",
            "node_modules/ not present. Run 'engel main install' first.",
            configured=False,
        )
    pid = _read_pid()
    if pid is not None and _pid_alive(pid):
        return _wrap(
            "Engel Main — already running",
            f"Existing dev server pid={pid}. Use 'engel main dev stop' first.",
        )
    if sys.platform == "win32":
        creationflags = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
        pnpm_cmd = _which_approved("pnpm.cmd") or pnpm
    else:
        creationflags = 0
        pnpm_cmd = pnpm
    try:
        with open(DEV_LOG, "wb") as logf:
            proc = subprocess.Popen(
                [pnpm_cmd, "dev"],
                cwd=str(APP_ROOT),
                stdout=logf, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                env=_subprocess_env(),
                creationflags=creationflags if sys.platform == "win32" else 0,
                close_fds=True, shell=False,
            )
    except OSError as exc:
        return _wrap("Engel Main — dev start failed", f"Could not spawn pnpm dev: {exc}")
    PID_FILE.write_text(str(proc.pid), encoding="utf-8")
    return _wrap(
        "Engel Main — dev start initiated",
        (
            f"Launched pnpm dev in background (pid={proc.pid}).\n"
            f"Working dir : {APP_ROOT}\n"
            f"Log file    : {DEV_LOG}\n"
            f"Open in browser once compiled: http://localhost:{DEFAULT_DEV_PORT}/\n"
            "Use 'engel main status' / 'engel main dev stop'."
        ),
    )


def render_engel_main_dev_stop(_payload: str = "") -> str:
    pid = _read_pid()
    if pid is None:
        return _wrap("Engel Main — nothing to stop", "No PID file present.")
    if not _pid_alive(pid):
        try: PID_FILE.unlink()
        except OSError: pass
        return _wrap("Engel Main — already stopped", f"Stale PID file removed (pid={pid}).")
    ok, detail = _kill_pid(pid)
    if ok:
        try: PID_FILE.unlink()
        except OSError: pass
        return _wrap("Engel Main — stopped", f"Terminated pid={pid}. {detail}")
    return _wrap("Engel Main — stop failed", f"Could not terminate pid={pid}: {detail}")


def render_engel_main_tauri_build(_payload: str = "") -> str:
    missing = _ensure_tree()
    if missing:
        return missing
    if not _cargo_path():
        return _wrap(
            "Engel Main — tauri build unavailable (Rust toolchain missing)",
            (
                "cargo is not on approved non-C PATH. Install Rust to a non-C toolchain root, "
                "set CARGO_HOME under F:, and ask 'engel main bring up'. C-side Rust is ignored."
            ),
            configured=False,
        )
    if not _pnpm_path():
        return _wrap(
            "Engel Main — tauri build unavailable (pnpm missing)",
            "Install or point Engel to a non-C pnpm executable first.",
            configured=False,
        )
    if not _node_modules_present():
        return _wrap(
            "Engel Main — tauri build prerequisite missing",
            "node_modules/ not present. Run 'engel main install' first.",
            configured=False,
        )
    proc = subprocess.run(
        [_pnpm_path(), "tauri", "build"],
        cwd=str(APP_ROOT),
        capture_output=True, text=True, check=False,
        encoding="utf-8", errors="replace",
        env=_subprocess_env(),
        timeout=1800,
    )
    if proc.returncode != 0:
        return _wrap(
            "Engel Main — tauri build failed",
            ((proc.stderr or proc.stdout) or "(no output)")[-8000:],
        )
    return _wrap(
        "Engel Main — tauri build complete",
        (
            "Full Tauri desktop bundle built.\n"
            f"Artifacts under {APP_ROOT}/target/release/bundle/."
        ),
    )


def render_engel_main_bring_up(_payload: str = "") -> str:
    body = (
        "Engel Main is a Tauri 2 desktop AI companion (Rust + pnpm + Vite).\n"
        "Bring-up steps:\n"
        "\n"
        f"  1) Node.js (currently {'present' if _node_path() else 'MISSING — install Node >= 24'}) at {_node_path() or 'NOT FOUND'}\n"
        "\n"
        "  2) pnpm:\n"
        "       install or copy pnpm to a non-C drive and add it to PATH\n"
        "       or set ENGEL_PNPM_EXE to that non-C executable.\n"
        "\n"
        "  3) Rust (only required for the full Tauri build):\n"
        "       install Rust to a non-C toolchain root, set CARGO_HOME under F:,\n"
        "       then ensure non-C cargo/rustc are on PATH.\n"
        "\n"
        "  4) Install JS deps via Engel AI:\n"
        "       engel main install\n"
        "     (Or: cd engel_main && pnpm install)\n"
        "\n"
        "  5) Web-only dev (no Rust required, fastest path):\n"
        "       engel main dev start   # detached Vite server on :5173\n"
        "       engel main status      # check pid\n"
        "       engel main dev stop    # terminate\n"
        "\n"
        "  6) Full desktop build (Rust + Tauri):\n"
        "       engel main tauri build\n"
        "     Output: app/target/release/bundle/\n"
    )
    return _wrap("Engel Main — bring-up guide", body, configured=False)
