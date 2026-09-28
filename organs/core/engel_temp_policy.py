"""Keep Engel-owned scratch files on the project drive."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

from engel_project_paths import resolve_engel_app_root

ROOT = resolve_engel_app_root(__file__)


def apply_engel_temp_policy() -> Path:
    runtime = ROOT / "runtime"
    home_root = runtime / "home"
    engel_home = home_root / ".engel"
    engelcode_home = home_root / ".engelcode"
    openengel_home = home_root / ".openengel"
    temp_root = runtime / "tmp"
    config_root = runtime / "config"
    cache_root = runtime / "cache"
    data_root = runtime / "data"
    pyinstaller_config = runtime / "pyinstaller_config"
    pyinstaller_extract = runtime / "pyinstaller_tmp"

    for folder in (
        home_root,
        engel_home,
        engelcode_home,
        openengel_home,
        temp_root,
        config_root,
        cache_root,
        data_root,
        pyinstaller_config,
        pyinstaller_extract,
    ):
        folder.mkdir(parents=True, exist_ok=True)

    temp_text = str(temp_root)
    os.environ["HOME"] = str(home_root)
    os.environ["ENGEL_HOME"] = str(engel_home)
    os.environ["ENGELCODE_HOME"] = str(engelcode_home)
    os.environ["OPENENGEL_HOME"] = str(openengel_home)
    os.environ["XDG_CONFIG_HOME"] = str(config_root)
    os.environ["XDG_CACHE_HOME"] = str(cache_root)
    os.environ["XDG_DATA_HOME"] = str(data_root)
    os.environ["TEMP"] = temp_text
    os.environ["TMP"] = temp_text
    os.environ["TMPDIR"] = temp_text
    os.environ["PYINSTALLER_CONFIG_DIR"] = str(pyinstaller_config)
    tempfile.tempdir = temp_text
    return temp_root


if os.environ.get("ENGEL_ALLOW_OS_TEMP", "").strip().lower() not in {"1", "true", "yes"}:
    apply_engel_temp_policy()
