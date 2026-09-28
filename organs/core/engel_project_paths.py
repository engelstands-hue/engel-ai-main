"""Shared project-root resolver for Engel App.

PyInstaller one-file builds run imported modules from a temporary ``_MEI``
folder. Engel state, artifacts, and tool workspaces must resolve back to the
real project folder on the work drive instead of that extraction directory.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


_KNOWN_WINDOWS_ROOT = Path(r"D:\b.WorkSpace\Engel App")
_ROOT_MARKERS = (
    "engel_desktop_v2.py",
    "engel_agent_meeting_room.py",
    "engel_ai.py",
)


def _parts_upper(path: Path) -> tuple[str, ...]:
    try:
        return tuple(part.upper() for part in path.resolve(strict=False).parts)
    except OSError:
        return tuple(part.upper() for part in path.parts)


def is_pyinstaller_temp_path(path: Path) -> bool:
    text = str(path).casefold()
    if "pyinstaller_tmp" in text:
        return True
    parts = _parts_upper(path)
    return any(part.startswith("_MEI") for part in parts)


def _looks_like_engel_root(path: Path) -> bool:
    try:
        if not path.is_dir():
            return False
    except OSError:
        return False
    marker_hits = sum(1 for marker in _ROOT_MARKERS if (path / marker).is_file())
    return marker_hits >= 2 or (path / "engel_octogent_main").is_dir()


def _walk_parents(start: Path) -> list[Path]:
    try:
        start = start.resolve(strict=False)
    except OSError:
        pass
    roots = [start]
    roots.extend(start.parents)
    return roots


def _candidate_roots(caller_file: str | os.PathLike[str] | None = None) -> list[Path]:
    candidates: list[Path] = []

    for env_name in ("ENGEL_APP_ROOT", "ENGEL_PROJECT_ROOT", "ENGEL_WORKSPACE_ROOT"):
        raw = os.environ.get(env_name, "").strip()
        if raw:
            candidates.append(Path(raw))

    try:
        candidates.extend(_walk_parents(Path.cwd()))
    except OSError:
        pass

    if getattr(sys, "frozen", False):
        candidates.extend(_walk_parents(Path(sys.executable).parent))

    if caller_file:
        candidates.extend(_walk_parents(Path(caller_file).parent))
    candidates.extend(_walk_parents(Path(__file__).parent))

    if _KNOWN_WINDOWS_ROOT.exists():
        candidates.append(_KNOWN_WINDOWS_ROOT)

    seen: set[str] = set()
    unique: list[Path] = []
    for candidate in candidates:
        try:
            key = str(candidate.resolve(strict=False)).casefold()
        except OSError:
            key = str(candidate).casefold()
        if key not in seen:
            unique.append(candidate)
            seen.add(key)
    return unique


def workspace_module_path(root: Path, name: str) -> Path | None:
    """Find a top-level Engel module at the root or in an organ folder."""
    direct = root / f"{name}.py"
    if direct.is_file():
        return direct
    try:
        import engel_organ_paths
    except Exception:
        return None
    for rel in engel_organ_paths.RELATIVE_DIRS:
        candidate = root / rel / f"{name}.py"
        if candidate.is_file():
            return candidate
    return None


def prefer_workspace_modules(*names: str, caller_file: str | os.PathLike[str] | None = None) -> None:
    """Reload listed top-level modules from the real workspace when a bundled copy is active."""
    import importlib.util

    root = resolve_engel_app_root(caller_file)
    root_text = str(root)
    if sys.path and sys.path[0] != root_text:
        if root_text in sys.path:
            sys.path.remove(root_text)
        sys.path.insert(0, root_text)
    for name in names:
        module_path = workspace_module_path(root, name)
        if module_path is None:
            continue
        existing = sys.modules.get(name)
        existing_file = str(getattr(existing, "__file__", "") or "") if existing is not None else ""
        if existing is not None and existing_file and not is_pyinstaller_temp_path(Path(existing_file)):
            continue
        spec = importlib.util.spec_from_file_location(name, module_path)
        if spec is None or spec.loader is None:
            continue
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)


def resolve_engel_python_executable(caller_file: str | os.PathLike[str] | None = None) -> Path:
    """Prefer the bundled D: workspace interpreter over whatever launched the GUI."""
    root = resolve_engel_app_root(caller_file)
    bundled = root / "runtime" / "python310" / "python.exe"
    if bundled.is_file():
        return bundled
    return Path(sys.executable)


def resolve_engel_app_root(caller_file: str | os.PathLike[str] | None = None) -> Path:
    """Return the real Engel App root, preferring non-temp workspace paths."""
    candidates = _candidate_roots(caller_file)
    for candidate in candidates:
        if _looks_like_engel_root(candidate) and not is_pyinstaller_temp_path(candidate):
            root = candidate.resolve(strict=False)
            os.environ["ENGEL_APP_ROOT"] = str(root)
            return root

    for candidate in candidates:
        if _looks_like_engel_root(candidate):
            root = candidate.resolve(strict=False)
            os.environ["ENGEL_APP_ROOT"] = str(root)
            return root

    fallback = _KNOWN_WINDOWS_ROOT if _KNOWN_WINDOWS_ROOT.exists() else Path(caller_file or __file__).resolve().parent
    os.environ["ENGEL_APP_ROOT"] = str(fallback)
    return fallback

