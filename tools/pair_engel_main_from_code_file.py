#!/usr/bin/env python3
"""Pair Engel AI Main to Sub-Engel using pairing_code.txt. Never prints the code."""
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
CODE_FILE = ROOT / "runtime" / "windows_sub_engel_bootstrap" / "pairing_code.txt"
URL = "http://198.51.100.227:8776"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def read_code() -> str:
    if not CODE_FILE.is_file():
        return ""
    for line in CODE_FILE.read_text(encoding="utf-8-sig").splitlines():
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        if text.upper() in {"CODE", "THE_CODE", "PASTE_CODE_HERE"}:
            continue
        return text
    return ""


def main() -> int:
    code = read_code()
    if not code:
        print("No pairing code in")
        print(str(CODE_FILE))
        print("Put the one-time code from Sub-Engel token on the first line, then run this again.")
        return 2
    from engel_sub_node_remote_control import pair_node

    result = pair_node(
        URL,
        code,
        controller_name="Engel AI Controller",
        store=True,
        node_kind="windows",
    )
    safe = {k: v for k, v in result.items() if "token" not in k.lower() and "code" not in k.lower()}
    print(json.dumps({"pair_ok": bool(result.get("ok")), "url": URL, **safe}, indent=2, sort_keys=True))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
