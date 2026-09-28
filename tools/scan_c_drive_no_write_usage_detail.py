#!/usr/bin/env python3
"""Second-level C: detail. Read-only. No C: writes. No junction follow."""
from __future__ import annotations

import json
from pathlib import Path

from scan_c_drive_no_write_usage import children_sizes, gb, utc_now, walk_size

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "c_drive_cleanup" / "C_DRIVE_USAGE_DETAIL.json"

TARGETS = [
    r"C:\Program Files",
    r"C:\Program Files (x86)",
    r"C:\ProgramData",
    r"C:\Users\ziese\AppData\Roaming",
    r"C:\Users\ziese\.codex",
    r"C:\Users\ziese\.claude",
    r"C:\Users\ziese\.vscode",
    r"C:\Users\ziese\AppData\Local\Google",
    r"C:\Users\ziese\AppData\Local\wsl",
    r"C:\Users\ziese\AppData\Local\Packages",
    r"C:\Users\ziese\AppData\Local\pip",
    r"C:\Users\ziese\AppData\Local\Android",
    r"C:\Users\ziese\AppData\Local\Programs",
    r"C:\Users\ziese\AppData\Local\Microsoft",
    r"C:\Users\ziese\AppData\Local\NVIDIA",
    r"C:\Users\ziese\AppData\Local\Temp",
    r"C:\Windows\WinSxS",
    r"C:\Windows\Installer",
    r"C:\Windows\SoftwareDistribution",
]

LEAF = [
    r"C:\Users\ziese\.grok",
    r"C:\Users\ziese\.claude",
    r"C:\Users\ziese\.codex",
    r"C:\Users\ziese\.cursor",
    r"C:\Users\ziese\agent-tools",
]


def main() -> int:
    errors: list[str] = []
    payload = {"schema": "engel_c_drive_usage_detail_v1", "ok": True, "scanned_at_utc": utc_now(), "folders": {}, "leaves": []}
    for target in TARGETS:
        rows = children_sizes(target, errors)[:20]
        payload["folders"][target] = rows
        print(f"\n{target}")
        for row in rows[:12]:
            mark = " [junction]" if row.get("reparse") else ""
            print(f"  {gb(row['bytes']):>10}  {row['path']}{mark}")
    for raw in LEAF:
        size, files, reparse = walk_size(raw, errors)
        payload["leaves"].append({"path": raw, "bytes": size, "files": files, "reparse": reparse, "exists": Path(raw).exists()})
        print(f"LEAF {gb(size):>10}  {raw}  reparse={reparse} files={files}")
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"\nwrote {OUT} errors={len(errors)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
