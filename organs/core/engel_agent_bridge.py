"""engel_agent_bridge — internal bridge for the bundled engel-agent.

The bundled subtree at ``D:\\b.WorkSpace\\Engel App\\engel_agent_main`` is a
fork of hermes-agent that has been case-preservingly renamed so every
``hermes`` token reads ``engel``. This module is the *plumbing* that lets
the bundled tree be invoked from inside Engel AI; user-facing
integration is exposed through the deterministic router (handled by
``engel_engel_agent_runner``). Direct callers should generally not
import this module — talk to Engel AI's router instead
(e.g. ``engel_ai.py ask "engel agent status"``).

Stage 4 (Phase D, 2026-05-20): the bridge now appends ``engel_agent_main``
to ``sys.path`` at module-import time, making hermes-agent Python modules
(``engel_cli``, ``engel_bootstrap``, ``agent``, ``cron``, ``acp_adapter``,
``gateway``, etc.) importable in-process from Engel AI without any
sys.path swap. The historical ``engel_agent_session`` context manager
remains for the legacy ``runpy``-style ``run_cli`` invocation path, but
new code paths should prefer ``import_hermes_module`` / direct
``import engel_cli...`` for in-process calls.

Empirical verification (2026-05-20):
  - hermes-agent has NO ``from engel import X`` statements; the original
    purge dance was over-defensive.
  - Engel App's own ``engel/`` package and hermes-agent's ``engel_cli/``
    coexist cleanly in the same Python process.
  - Engel App's ``tools/`` and ``scripts/`` directories are not Python
    packages (no ``__init__.py``), so appending hermes-agent at the END
    of sys.path causes no real conflict.

Public surface (internal):

    AGENT_ROOT                 — Path to the bundled tree
    in_process_available()     — True if hermes-agent modules are importable
    import_hermes_module(name) — Direct in-process import helper (Phase D)
    engel_agent_session        — Legacy context manager (kept for runpy path)
    run_cli                    — Invoke the bundled CLI in-process via runpy
    spawn_cli                  — Invoke the bundled CLI in a subprocess
"""
from __future__ import annotations

import contextlib
import importlib
import os
import runpy
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Iterator, Sequence

def _candidate_agent_roots() -> list[Path]:
    """Return ordered candidate paths for the bundled engel_agent_main tree.

    Priority:
      1. Sibling of this file (dev mode + PyInstaller MEIPASS extraction).
      2. Sibling of sys.executable (next-to-exe install layout).
      3. Engel-owned runtime relocation under Engel App root.
      4. Hard-coded D:\\b.WorkSpace\\Engel App fallback (matches install policy).
    """
    here = Path(__file__).resolve().parent
    candidates: list[Path] = [here / "engel_agent_main"]
    try:
        exe_dir = Path(sys.executable).resolve().parent
        candidates.append(exe_dir / "engel_agent_main")
    except Exception:
        pass
    # Engel-owned relocation target — agents may be staged here by approved flows.
    candidates.append(here / "runtime" / "agent_bridge" / "engel_agent_main")
    # Hard-coded install policy fallback.
    candidates.append(Path("D:/b.WorkSpace/Engel App/engel_agent_main"))
    return candidates


def _resolve_agent_root() -> Path | None:
    for p in _candidate_agent_roots():
        try:
            if p.is_dir():
                return p
        except Exception:
            continue
    return None


# Resolved at import time — None when the subtree is unavailable (e.g. the
# Engel App is running from a packaged exe that did not bundle the tree).
# Callers MUST check ``in_process_available()`` or ``bridge_available()``
# before using ``run_cli`` / ``import_hermes_module``; importing this module
# never crashes the host process.
AGENT_ROOT: Path | None = _resolve_agent_root()

if AGENT_ROOT is not None:
    _AGENT_ROOT_STR = str(AGENT_ROOT)
    if _AGENT_ROOT_STR not in sys.path:
        sys.path.append(_AGENT_ROOT_STR)


def bridge_available() -> bool:
    """Return True if the engel-agent subtree was found and is usable."""
    return AGENT_ROOT is not None and AGENT_ROOT.is_dir()


def bridge_missing_reason() -> str:
    """Human-readable explanation when the bridge is unavailable."""
    if bridge_available():
        return ""
    tried = "\n  ".join(str(p) for p in _candidate_agent_roots())
    return (
        "engel_agent_main subtree missing — Engel-Hermes integration not wired.\n"
        f"  Looked in:\n  {tried}\n"
        "  Place a copy under D:\\b.WorkSpace\\Engel App\\engel_agent_main\\ "
        "or D:\\b.WorkSpace\\Engel App\\runtime\\agent_bridge\\engel_agent_main\\ "
        "to enable the bridge."
    )


def in_process_available() -> bool:
    """Return True if hermes-agent modules can be imported in-process.

    Phase D proof: tries to import ``engel_cli`` and ``engel_bootstrap``;
    success means the source-level absorption is wired up correctly.
    Failure is silently swallowed and returns False so callers can
    degrade gracefully.
    """
    try:
        importlib.import_module("engel_cli")
        importlib.import_module("engel_bootstrap")
        return True
    except Exception:
        return False


def import_hermes_module(name: str) -> ModuleType | None:
    """Import a hermes-agent module in-process and return it.

    Returns None if the import fails for any reason (missing dependency,
    syntax error in the bundled module, etc.). Callers should treat None
    as 'not available — fall back to subprocess or describe-only'.
    """
    try:
        return importlib.import_module(name)
    except Exception:
        return None


def import_hermes_module_diagnostic(name: str) -> tuple[ModuleType | None, str | None]:
    """Same as import_hermes_module but also returns a short diagnostic
    string on failure (e.g. ``"ModuleNotFoundError: No module named 'rich'"``).

    Returns ``(module, None)`` on success, ``(None, error_str)`` on failure.
    Used by the engel.native_runtime proof route so missing-dependency
    failures are visible to the user instead of silently dropping to a
    bare ``✗ import failed`` line.
    """
    try:
        return importlib.import_module(name), None
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"


def _purge_engel_modules() -> dict[str, object]:
    """Remove any cached engel.* / engel_cli.* modules so the bundled
    package can be imported cleanly. Returns the removed entries so they
    can be restored on context exit.
    """
    removed: dict[str, object] = {}
    prefixes = (
        "engel", "engel.",
        "engel_cli", "engel_cli.",
        "engel_bootstrap",
        "engel_constants",
        "engel_logging",
        "engel_state",
        "engel_time",
        "agent", "agent.",
        "cron", "cron.",
        "acp_adapter", "acp_adapter.",
    )
    for name in list(sys.modules.keys()):
        if name == "engel" or name.startswith("engel."):
            removed[name] = sys.modules.pop(name)
            continue
        for p in prefixes:
            if name == p.rstrip(".") or (p.endswith(".") and name.startswith(p)):
                removed[name] = sys.modules.pop(name)
                break
    return removed


@contextlib.contextmanager
def engel_agent_session() -> Iterator[Path]:
    """Run a block of code with ``engel_agent_main`` at the front of
    ``sys.path`` and the host ``engel`` package temporarily unloaded.

    On exit the original ``sys.path`` and any previously imported
    ``engel*`` modules are restored.
    """
    if not bridge_available():
        raise RuntimeError(bridge_missing_reason())
    original_path = list(sys.path)
    swapped_out = _purge_engel_modules()
    sys.path.insert(0, str(AGENT_ROOT))
    try:
        yield AGENT_ROOT
    finally:
        sys.path[:] = original_path
        # Drop anything the bundled tree imported, then re-publish the
        # originally cached host modules.
        for name in list(sys.modules.keys()):
            if (
                name == "engel"
                or name.startswith("engel.")
                or name == "engel_cli"
                or name.startswith("engel_cli.")
            ):
                sys.modules.pop(name, None)
        for name, mod in swapped_out.items():
            sys.modules[name] = mod  # type: ignore[assignment]


def run_cli(argv: Sequence[str] | None = None) -> None:
    """Invoke the bundled cli.py in-process within an engel_agent_session.

    ``argv`` (without program name) is forwarded as ``sys.argv[1:]``.
    """
    saved_argv = sys.argv[:]
    sys.argv = ["cli.py", *(argv or [])]
    try:
        with engel_agent_session() as root:
            runpy.run_path(str(root / "cli.py"), run_name="__main__")
    finally:
        sys.argv = saved_argv


def _is_packaged_engel_executable(value: str | None = None) -> bool:
    """True when ``value`` points at a frozen Engel app executable.

    PyInstaller sets ``sys.frozen`` and makes ``sys.executable`` the app
    launcher. Running that launcher with ``cli.py`` relaunches the GUI, so
    subprocess agent routes must avoid it.
    """
    exe = Path(value or sys.executable)
    name = exe.name.lower()
    if name in {"engel.exe", "engelsuperswarmhive3d.exe"}:
        return True
    return value is None and bool(getattr(sys, "frozen", False)) and name.endswith(".exe")


def _command_from_python_setting(value: str | None) -> list[str] | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    unquoted = raw.strip("\"'")
    if Path(unquoted).exists():
        return [unquoted]
    try:
        parts = shlex.split(raw)
    except ValueError:
        parts = [raw]
    return parts or None


def _dedupe_commands(commands: list[list[str]]) -> list[list[str]]:
    seen: set[tuple[str, ...]] = set()
    unique: list[list[str]] = []
    for command in commands:
        if not command:
            continue
        key = tuple(command)
        if key in seen:
            continue
        seen.add(key)
        unique.append(command)
    return unique


def _python_command_candidates(python: str | None = None) -> list[list[str]]:
    """Return safe Python command candidates for bundled agent scripts.

    Source runs keep using ``sys.executable``. Frozen/live app runs skip the
    Engel GUI executable and try the explicit/env Python override first,
    then normal Windows Python launchers.
    """
    candidates: list[list[str]] = []
    explicit = _command_from_python_setting(python)
    if explicit:
        return [explicit]

    env_python = _command_from_python_setting(os.environ.get("ENGEL_AGENT_PYTHON"))
    if env_python:
        candidates.append(env_python)

    if not _is_packaged_engel_executable(sys.executable):
        candidates.append([sys.executable])
    else:
        path_python = shutil.which("python")
        if path_python and not _is_packaged_engel_executable(path_python):
            candidates.append([path_python])
        launcher = shutil.which("py")
        if launcher and not _is_packaged_engel_executable(launcher):
            candidates.append([launcher, "-3.10"])
            candidates.append([launcher, "-3"])
        for folder in (
            Path.home() / "AppData" / "Local" / "Programs" / "Python" / "Python310",
            Path.home() / "AppData" / "Local" / "Programs" / "Python" / "Python312",
        ):
            exe = folder / "python.exe"
            if exe.exists():
                candidates.append([str(exe)])

    if not candidates:
        candidates.append([sys.executable])
    return _dedupe_commands(candidates)


def _synthetic_completed_process(
    args: list[str],
    returncode: int,
    stderr: str,
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=args, returncode=returncode, stdout="", stderr=stderr)


def _run_agent_python_script(
    script_name: str,
    argv: Sequence[str] | None = None,
    *,
    python: str | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    if not bridge_available():
        return _synthetic_completed_process(
            [script_name, *(argv or [])],
            127,
            bridge_missing_reason(),
        )
    run_env = os.environ.copy()
    if env:
        run_env.update(env)

    last_error: subprocess.CompletedProcess[str] | None = None
    for python_cmd in _python_command_candidates(python):
        cmd = [*python_cmd, script_name, *(argv or [])]
        if _is_packaged_engel_executable(python_cmd[0]):
            last_error = _synthetic_completed_process(
                cmd,
                126,
                (
                    "Refused to run bundled Engel agent script through the "
                    f"packaged app executable: {python_cmd[0]}"
                ),
            )
            continue
        try:
            return subprocess.run(
                cmd,
                cwd=str(AGENT_ROOT),
                env=run_env,
                capture_output=True,
                text=True,
                check=False,
                encoding="utf-8",
                errors="replace",
            )
        except OSError as exc:
            last_error = _synthetic_completed_process(
                cmd,
                127,
                f"Could not start Python for Engel Agent: {exc}",
            )

    return last_error or _synthetic_completed_process(
        ["python", script_name, *(argv or [])],
        127,
        "Could not find a usable Python interpreter for Engel Agent.",
    )


def spawn_cli(
    argv: Sequence[str] | None = None,
    *,
    python: str | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run the bundled CLI in a subprocess so it cannot pollute the host
    Python session. Returns the completed process result.

    Phase D follow-up (2026-05-20): when Engel AI is launched from a frozen
    PyInstaller bundle (Engel.exe / EngelSuperSwarmHive3D.exe),
    ``sys.executable`` points at the app launcher. Running that launcher as
    ``Engel.exe cli.py ...`` relaunches a second GUI and yields empty agent
    output. Frozen runs therefore skip the app executable and use a real
    Python command instead.

    Resolution order: explicit ``python=`` arg > ``ENGEL_AGENT_PYTHON`` env
    var > source ``sys.executable`` > PATH ``python`` / Windows ``py``.
    """
    return _run_agent_python_script("cli.py", argv, python=python, env=env)


def spawn_engel_launcher(
    argv: Sequence[str] | None = None,
    *,
    python: str | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run the bundled ``engel`` launcher through a real Python command."""
    return _run_agent_python_script("engel", argv, python=python, env=env)


if __name__ == "__main__":
    proc = spawn_cli(sys.argv[1:])
    sys.stdout.write(proc.stdout)
    sys.stderr.write(proc.stderr)
    sys.exit(proc.returncode)
