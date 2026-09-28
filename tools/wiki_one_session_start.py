#!/usr/bin/env python3
"""Grok SessionStart helper: remind the lane to read Wiki One before CODE."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engel_wiki_one import session_start_text  # noqa: E402


def main() -> int:
    print(session_start_text())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
