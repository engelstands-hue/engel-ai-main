"""Put organ folders on sys.path so `import engel_*` still finds moved modules."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

RELATIVE_DIRS = (
    "spine/routes",
    "spine/kernel",
    "organs/discord",
    "organs/android",
    "organs/meeting_room",
    "organs/face",
    "organs/chat",
    "organs/code_companion",
    "organs/models",
    "organs/memory",
    "organs/research",
    "organs/library",
    "organs/architect",
    "organs/guardian",
    "organs/learning",
    "organs/grok",
    "organs/rust_face",
    "organs/vendor_runners",
    "organs/bridges",
    "organs/browser_queen",
    "organs/fherma",
    "organs/core",
)


def install() -> None:
    for rel in RELATIVE_DIRS:
        folder = ROOT / rel
        if not folder.is_dir():
            continue
        text = str(folder)
        if text not in sys.path:
            sys.path.append(text)
