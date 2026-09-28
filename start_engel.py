import subprocess
import sys
import os
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
ENTRY = PROJECT_DIR / "engel_app.py"
DEFAULT_MEMORY_ROOT = PROJECT_DIR / "runtime" / "engel_memory"


def _memory_root() -> Path:
    configured = os.environ.get("ENGEL_MEMORY_ROOT", "").strip() or os.environ.get("ENGEL_" + "APP_MEMORY_ROOT", "").strip()
    if configured:
        return Path(configured)
    return DEFAULT_MEMORY_ROOT


def _launch_env() -> dict[str, str]:
    env = os.environ.copy()
    memory_root = _memory_root()
    engel_home = memory_root / "engel-home"
    runpod_root = memory_root / "runpod"
    secret_path = memory_root / "secrets" / "runpod_api_key.txt"
    for path in [engel_home, runpod_root, secret_path.parent]:
        path.mkdir(parents=True, exist_ok=True)
    env.setdefault("ENGEL_HOME", str(engel_home))
    env.setdefault("ENGEL_RUNPOD_ROOT", str(runpod_root))
    env.setdefault("ENGEL_RUNPOD_API_KEY_FILE", str(secret_path))
    return env

if not ENTRY.exists():
    raise FileNotFoundError(f"Missing Engel entry file: {ENTRY}")

subprocess.run(
    [sys.executable, str(ENTRY)],
    cwd=str(PROJECT_DIR),
    env=_launch_env(),
    check=False,
)
