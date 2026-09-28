"""Engel AI ↔ bundled engel_lan (LAN file-sharing) integration.

Backs the ``engel.engel_lan.*`` routes registered in
``engel_ai_update_routes``. The vendored tree at
``D:\\b.WorkSpace\\Engel App\\engel_lan_main`` is a fork of
LocalSend, case-preservingly rebranded with Dart-aware mappings:
  LOCALSEND → ENGEL_LAN     (constants)
  LocalSend → EngelLan      (PascalCase classes, no underscore)
  localSend → engelLan      (camelCase)
  localsend → engel_lan     (snake_case files/identifiers)
407 files touched, 3,833 substitutions, 6 path renames.

Engel LAN is a Flutter app + Dart CLI for cross-platform LAN
file/message sharing. The CLI entry is ``cli/bin/cli.dart`` and
runs via the Dart toolchain (shipped with the Flutter SDK).

Detected Flutter SDK location (auto-discovered each call):
  D:\\b.WorkSpace\\flutter_windows_3.41.9-stable\\flutter\\bin\\
or the system PATH if available.

Public surface:

    render_engel_lan_status()         — Flutter SDK + deps presence
    render_engel_lan_version()        — pubspec versions
    render_engel_lan_cli_help()       — dart bin/cli.dart --help
    render_engel_lan_cli_scan()       — dart bin/cli.dart scan
    render_engel_lan_app_dev_start()  — flutter run (detached)
    render_engel_lan_app_dev_stop()   — terminate dev server
    render_engel_lan_bring_up()       — toolchain bring-up guide
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

ENGEL_LAN_ROOT: Path = Path(__file__).resolve().parent / "engel_lan_main"
CLI_DIR: Path = ENGEL_LAN_ROOT / "cli"
CLI_ENTRY: Path = CLI_DIR / "bin" / "cli.dart"
APP_DIR: Path = ENGEL_LAN_ROOT / "app"
PID_FILE: Path = ENGEL_LAN_ROOT / ".engel_lan_app.pid"
DEV_LOG: Path = ENGEL_LAN_ROOT / ".engel_lan_app.log"

# Common Flutter SDK locations on this host
_FLUTTER_CANDIDATES = (
    Path(r"D:\b.WorkSpace\flutter_windows_3.41.9-stable\flutter\bin"),
    Path(r"D:\flutter_windows_3.41.9-stable\flutter\bin"),
)


def _find_flutter_bin() -> Optional[Path]:
    for candidate in _FLUTTER_CANDIDATES:
        if (candidate / "flutter.bat").is_file() or (candidate / "flutter").is_file():
            return candidate
    return None


def _flutter_path() -> Optional[str]:
    bindir = _find_flutter_bin()
    if bindir:
        for n in ("flutter.bat", "flutter"):
            p = bindir / n
            if p.is_file():
                return str(p)
    return shutil.which("flutter") or shutil.which("flutter.bat")


def _dart_path() -> Optional[str]:
    bindir = _find_flutter_bin()
    if bindir:
        for n in ("dart.bat", "dart"):
            p = bindir / n
            if p.is_file():
                return str(p)
    return shutil.which("dart") or shutil.which("dart.bat")


def _read_pubspec_version(pubspec: Path) -> str:
    if not pubspec.is_file():
        return "(missing)"
    try:
        for line in pubspec.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if line.startswith("version:"):
                return line.split(":", 1)[1].strip().strip("\"'")
    except OSError as exc:
        return f"(read failed: {exc})"
    return "(no version line)"


def _cli_pub_get_done() -> bool:
    return (CLI_DIR / ".dart_tool" / "package_config.json").is_file()


def _app_pub_get_done() -> bool:
    return (APP_DIR / ".dart_tool" / "package_config.json").is_file()


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
        f"- Engel LAN tree: {ENGEL_LAN_ROOT}",
        "- CLI and app subprocesses run inside the vendored tree only.",
        "- Network: LAN-only (Engel LAN does not call the internet).",
        "- Autonomy and background work permitted (2026-05-19 ruling).",
    ]
    if not configured:
        safety.append("- Ask 'engel lan bring up' for the toolchain install walkthrough.")
    return f"{title}\n\n{body}\n\n" + "\n".join(safety)


def _ensure_tree() -> Optional[str]:
    if not ENGEL_LAN_ROOT.is_dir():
        return _wrap("Engel LAN — tree missing", f"Vendored tree not found at {ENGEL_LAN_ROOT}.", configured=False)
    return None


def render_engel_lan_status(_payload: str = "") -> str:
    missing = _ensure_tree()
    if missing:
        return missing
    lines = [
        f"Tree root         : {ENGEL_LAN_ROOT}",
        f"CLI entry         : {CLI_ENTRY} ({'present' if CLI_ENTRY.is_file() else 'MISSING'})",
        f"App dir           : {APP_DIR} ({'present' if APP_DIR.is_dir() else 'MISSING'})",
        f"flutter executable: {_flutter_path() or 'NOT FOUND'}",
        f"dart executable   : {_dart_path()    or 'NOT FOUND'}",
        f"CLI .dart_tool    : {'pub get done' if _cli_pub_get_done() else 'not yet run (dart pub get inside cli/)'}",
        f"App .dart_tool    : {'pub get done' if _app_pub_get_done() else 'not yet run (flutter pub get inside app/)'}",
        f"CLI pubspec ver   : {_read_pubspec_version(CLI_DIR / 'pubspec.yaml')}",
        f"App pubspec ver   : {_read_pubspec_version(APP_DIR / 'pubspec.yaml')}",
    ]
    pid = _read_pid()
    if pid is None:
        lines.append("App dev server    : not running (no PID file)")
    elif _pid_alive(pid):
        lines.append(f"App dev server    : running (pid={pid}, log={DEV_LOG})")
    else:
        lines.append(f"App dev server    : stale PID file (pid={pid} not alive)")
    return _wrap("Engel LAN — status", "\n".join(lines))


def render_engel_lan_version(_payload: str = "") -> str:
    missing = _ensure_tree()
    if missing:
        return missing
    cli_ver = _read_pubspec_version(CLI_DIR / "pubspec.yaml")
    app_ver = _read_pubspec_version(APP_DIR / "pubspec.yaml")
    return _wrap(
        "Engel LAN — version",
        f"engel_lan CLI: {cli_ver}\nengel_lan App: {app_ver}",
    )


def _run_dart_cli(action: str, extra_argv: list[str], *, timeout: int = 60) -> str:
    missing = _ensure_tree()
    if missing:
        return missing
    if not CLI_ENTRY.is_file():
        return _wrap("Engel LAN — CLI entry missing", f"Expected {CLI_ENTRY}", configured=False)
    dart = _dart_path()
    if not dart:
        return _wrap(
            f"Engel LAN — {action} unavailable (dart not found)",
            "Install Flutter SDK (which ships dart). Ask 'engel lan bring up' for steps.",
            configured=False,
        )
    if not _cli_pub_get_done():
        # Auto-run pub get inside the CLI package (cheap, ~seconds).
        pubget = subprocess.run(
            [dart, "pub", "get"],
            cwd=str(CLI_DIR),
            capture_output=True, text=True, check=False,
            encoding="utf-8", errors="replace",
            timeout=120,
        )
        if pubget.returncode != 0:
            return _wrap(
                "Engel LAN — dart pub get failed",
                ((pubget.stderr or pubget.stdout) or "(no output)")[-4000:],
            )
    proc = subprocess.run(
        [dart, "run", "bin/cli.dart", *extra_argv],
        cwd=str(CLI_DIR),
        capture_output=True, text=True, check=False,
        encoding="utf-8", errors="replace",
        timeout=timeout,
    )
    body = (proc.stdout.rstrip() or proc.stderr.rstrip() or "(no output)")
    title = f"Engel LAN — {action}" + (f" (exit {proc.returncode})" if proc.returncode != 0 else "")
    return _wrap(title, body[-8000:])


def render_engel_lan_cli_help(_payload: str = "") -> str:
    return _run_dart_cli("cli --help", ["--help"], timeout=60)


def render_engel_lan_cli_receive_start(_payload: str = "") -> str:
    """Spawn ``dart run bin/cli.dart --receive`` in the background so the
    receiving server stays up while the host Engel AI session continues.
    PID is recorded under ``.engel_lan_receive.pid``.
    """
    missing = _ensure_tree()
    if missing:
        return missing
    dart = _dart_path()
    if not dart:
        return _wrap(
            "Engel LAN — cli receive unavailable (dart not found)",
            "Install Flutter SDK. Ask 'engel lan bring up'.",
            configured=False,
        )
    recv_pid_file = ENGEL_LAN_ROOT / ".engel_lan_receive.pid"
    recv_log = ENGEL_LAN_ROOT / ".engel_lan_receive.log"
    if recv_pid_file.is_file():
        try:
            existing = int(recv_pid_file.read_text(encoding="utf-8").strip())
            if _pid_alive(existing):
                return _wrap(
                    "Engel LAN — receive already running",
                    f"Existing receive pid={existing}. Use 'engel lan receive stop' first.",
                )
        except (ValueError, OSError):
            pass
    creationflags = 0
    if sys.platform == "win32":
        creationflags = 0x00000008 | 0x00000200
    try:
        with open(recv_log, "wb") as logf:
            proc = subprocess.Popen(
                [dart, "run", "bin/cli.dart", "--receive"],
                cwd=str(CLI_DIR),
                stdout=logf, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                creationflags=creationflags if sys.platform == "win32" else 0,
                close_fds=True, shell=False,
            )
    except OSError as exc:
        return _wrap("Engel LAN — receive start failed", f"Could not spawn dart receive: {exc}")
    recv_pid_file.write_text(str(proc.pid), encoding="utf-8")
    return _wrap(
        "Engel LAN — receive server started",
        (
            f"Launched 'dart run bin/cli.dart --receive' in background (pid={proc.pid}).\n"
            f"Working dir : {CLI_DIR}\n"
            f"Log file    : {recv_log}\n"
            "The receive server listens on the LAN for inbound file transfers.\n"
            "Use 'engel lan receive stop' to terminate."
        ),
    )


def render_engel_lan_cli_receive_stop(_payload: str = "") -> str:
    recv_pid_file = ENGEL_LAN_ROOT / ".engel_lan_receive.pid"
    if not recv_pid_file.is_file():
        return _wrap("Engel LAN — receive: nothing to stop", "No receive PID file present.")
    try:
        pid = int(recv_pid_file.read_text(encoding="utf-8").strip())
    except (ValueError, OSError):
        return _wrap("Engel LAN — receive: PID file unreadable", "Manual cleanup may be needed.")
    if not _pid_alive(pid):
        try: recv_pid_file.unlink()
        except OSError: pass
        return _wrap("Engel LAN — receive: already stopped", f"Stale PID file removed (pid={pid}).")
    ok, detail = _kill_pid(pid)
    if ok:
        try: recv_pid_file.unlink()
        except OSError: pass
        return _wrap("Engel LAN — receive stopped", f"Terminated pid={pid}. {detail}")
    return _wrap("Engel LAN — receive stop failed", f"Could not terminate pid={pid}: {detail}")


def render_engel_lan_app_dev_start(_payload: str = "") -> str:
    missing = _ensure_tree()
    if missing:
        return missing
    flutter = _flutter_path()
    if not flutter:
        return _wrap(
            "Engel LAN — app dev unavailable (flutter not found)",
            "Install / locate the Flutter SDK. Ask 'engel lan bring up' for steps.",
            configured=False,
        )
    pid = _read_pid()
    if pid is not None and _pid_alive(pid):
        return _wrap(
            "Engel LAN — already running",
            f"Existing app dev pid={pid}. Use 'engel lan stop' first.",
        )
    creationflags = 0
    if sys.platform == "win32":
        creationflags = 0x00000008 | 0x00000200
    try:
        with open(DEV_LOG, "wb") as logf:
            proc = subprocess.Popen(
                [flutter, "run", "-d", "windows"],
                cwd=str(APP_DIR),
                stdout=logf, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                creationflags=creationflags if sys.platform == "win32" else 0,
                close_fds=True, shell=False,
            )
    except OSError as exc:
        return _wrap("Engel LAN — app dev start failed", f"Could not spawn flutter run: {exc}")
    PID_FILE.write_text(str(proc.pid), encoding="utf-8")
    return _wrap(
        "Engel LAN — app dev start initiated",
        (
            f"Launched 'flutter run -d windows' in background (pid={proc.pid}).\n"
            f"Working dir : {APP_DIR}\n"
            f"Log file    : {DEV_LOG}\n"
            "Use 'engel lan status' / 'engel lan stop'."
        ),
    )


def render_engel_lan_app_dev_stop(_payload: str = "") -> str:
    pid = _read_pid()
    if pid is None:
        return _wrap("Engel LAN — nothing to stop", "No PID file present.")
    if not _pid_alive(pid):
        try: PID_FILE.unlink()
        except OSError: pass
        return _wrap("Engel LAN — already stopped", f"Stale PID file removed (pid={pid}).")
    ok, detail = _kill_pid(pid)
    if ok:
        try: PID_FILE.unlink()
        except OSError: pass
        return _wrap("Engel LAN — stopped", f"Terminated pid={pid}. {detail}")
    return _wrap("Engel LAN — stop failed", f"Could not terminate pid={pid}: {detail}")


def render_engel_lan_bring_up(_payload: str = "") -> str:
    flutter = _flutter_path()
    dart = _dart_path()
    body = (
        "Engel LAN is a Flutter app + Dart CLI for LAN file sharing.\n"
        "\n"
        f"  1) Flutter SDK (currently: {flutter or 'NOT FOUND'})\n"
        "     Detected SDK candidates checked:\n"
        + "\n".join(f"       - {c}" for c in _FLUTTER_CANDIDATES)
        + "\n"
        "     If missing, download the bundled archive at\n"
        "     D:\\b.WorkSpace\\flutter_windows_3.41.9-stable\\ (if extracted),\n"
        "     or grab a fresh SDK from https://docs.flutter.dev/get-started/install\n"
        "\n"
        f"  2) Dart executable (currently: {dart or 'NOT FOUND'}) — ships with Flutter.\n"
        "\n"
        "  3) Add flutter\\bin to your PATH so 'flutter' and 'dart' are reachable.\n"
        "\n"
        "  4) CLI usage:\n"
        "       engel lan cli help    # discover subcommands\n"
        "       engel lan cli scan    # find LAN peers\n"
        "\n"
        "  5) App (Flutter desktop):\n"
        "       engel lan dev start   # detached 'flutter run -d windows'\n"
        "       engel lan status      # check pid\n"
        "       engel lan dev stop    # terminate\n"
        "\n"
        "  6) Network behaviour: LAN-only discovery via multicast/Bonjour-style.\n"
        "     No internet calls. Safe to run on isolated/offline networks.\n"
    )
    return _wrap("Engel LAN — bring-up guide", body, configured=False)
