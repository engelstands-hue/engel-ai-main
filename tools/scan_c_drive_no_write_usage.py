#!/usr/bin/env python3
"""Read-only C: usage scan. Never writes to C:. Does not follow junctions."""
from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "reports" / "c_drive_cleanup"
OUT_JSON = OUT_DIR / "C_DRIVE_USAGE_SCAN.json"
REPARSE = 0x400
MAX_ERRORS = 4000

KNOWN = [
    r"C:\Users\ziese\.grok",
    r"C:\Users\ziese\.claude",
    r"C:\Users\ziese\.cursor",
    r"C:\Users\ziese\.codex",
    r"C:\Users\ziese\.npm",
    r"C:\Users\ziese\.cache",
    r"C:\Users\ziese\Downloads",
    r"C:\Users\ziese\Desktop",
    r"C:\Users\ziese\Documents",
    r"C:\Users\ziese\Videos",
    r"C:\Users\ziese\Pictures",
    r"C:\Users\ziese\Music",
    r"C:\Users\ziese\AppData\Local\Temp",
    r"C:\Users\ziese\AppData\Local\Packages",
    r"C:\Users\ziese\AppData\Local\Docker",
    r"C:\Users\ziese\AppData\Local\npm-cache",
    r"C:\Users\ziese\AppData\Local\pip",
    r"C:\Users\ziese\AppData\Local\pnpm",
    r"C:\Users\ziese\AppData\Local\Yarn",
    r"C:\Users\ziese\AppData\Local\Pub",
    r"C:\Users\ziese\AppData\Local\Android",
    r"C:\Users\ziese\AppData\Local\Google",
    r"C:\Users\ziese\AppData\Local\Microsoft",
    r"C:\Users\ziese\AppData\Local\Programs",
    r"C:\Users\ziese\AppData\Local\Temp\_MEI",
    r"C:\Users\ziese\AppData\Roaming",
    r"C:\Users\ziese\AppData\Local",
    r"C:\Users\ziese\AppData",
    r"C:\ProgramData",
    r"C:\Windows\WinSxS",
    r"C:\Windows\Installer",
    r"C:\Windows\SoftwareDistribution",
    r"C:\Windows\Temp",
    r"C:\pagefile.sys",
    r"C:\hiberfil.sys",
    r"C:\swapfile.sys",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def gb(n: int) -> str:
    return f"{n / (1024 ** 3):.2f} GB"


def is_reparse(entry: os.DirEntry) -> bool:
    try:
        st = entry.stat(follow_symlinks=False)
    except OSError:
        return True
    return bool(getattr(st, "st_file_attributes", 0) & REPARSE)


def walk_size(path: str, errors: list[str]) -> tuple[int, int, bool]:
    """Return (bytes, file_count, is_reparse_root). Never follows reparse points."""
    p = Path(path)
    try:
        if p.is_symlink() or bool(p.lstat().st_file_attributes & REPARSE):  # type: ignore[attr-defined]
            return 0, 0, True
    except OSError as exc:
        errors.append(f"{path}: {exc}")
        return 0, 0, False
    if p.is_file():
        try:
            return p.lstat().st_size, 1, False
        except OSError as exc:
            errors.append(f"{path}: {exc}")
            return 0, 0, False
    total = 0
    files = 0
    stack = [path]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as it:
                for entry in it:
                    try:
                        if is_reparse(entry):
                            continue
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(entry.path)
                        else:
                            total += entry.stat(follow_symlinks=False).st_size
                            files += 1
                    except OSError as exc:
                        if len(errors) < MAX_ERRORS:
                            errors.append(f"{entry.path}: {exc}")
                    except FileNotFoundError:
                        continue
        except OSError as exc:
            if len(errors) < MAX_ERRORS:
                errors.append(f"{current}: {exc}")
    return total, files, False


def children_sizes(path: str, errors: list[str]) -> list[dict]:
    rows = []
    try:
        with os.scandir(path) as it:
            kids = list(it)
    except OSError as exc:
        errors.append(f"{path}: {exc}")
        return rows
    for entry in kids:
        try:
            if is_reparse(entry):
                rows.append(
                    {
                        "path": entry.path,
                        "bytes": 0,
                        "files": 0,
                        "reparse": True,
                        "kind": "junction-or-symlink",
                    }
                )
                continue
            if entry.is_dir(follow_symlinks=False):
                size, files, reparse = walk_size(entry.path, errors)
                rows.append(
                    {
                        "path": entry.path,
                        "bytes": size,
                        "files": files,
                        "reparse": reparse,
                        "kind": "dir",
                    }
                )
            else:
                st = entry.stat(follow_symlinks=False)
                rows.append(
                    {
                        "path": entry.path,
                        "bytes": st.st_size,
                        "files": 1,
                        "reparse": False,
                        "kind": "file",
                    }
                )
        except OSError as exc:
            errors.append(f"{entry.path}: {exc}")
    rows.sort(key=lambda r: r["bytes"], reverse=True)
    return rows


def disk_free(letter: str) -> dict:
    usage = os.statvfs(letter) if hasattr(os, "statvfs") else None
    if usage:
        return {
            "total": usage.f_frsize * usage.f_blocks,
            "free": usage.f_frsize * usage.f_bavail,
        }
    import ctypes

    avail = ctypes.c_ulonglong(0)
    total_bytes = ctypes.c_ulonglong(0)
    free_bytes = ctypes.c_ulonglong(0)
    ctypes.windll.kernel32.GetDiskFreeSpaceExW(
        ctypes.c_wchar_p(letter),
        ctypes.byref(avail),
        ctypes.byref(total_bytes),
        ctypes.byref(free_bytes),
    )
    return {"total": int(total_bytes.value), "free": int(avail.value)}


def main() -> int:
    errors: list[str] = []
    c_info = disk_free("C:\\")
    payload: dict = {
        "schema": "engel_c_drive_usage_scan_v1",
        "ok": True,
        "scanned_at_utc": utc_now(),
        "note": "Read-only. Did not follow junctions. Did not write to C:.",
        "disk": {
            "letter": "C:",
            "total_bytes": c_info["total"],
            "free_bytes": c_info["free"],
            "used_bytes": c_info["total"] - c_info["free"],
        },
        "top_level": [],
        "user_home": [],
        "appdata_local": [],
        "appdata_roaming": [],
        "known_paths": [],
        "error_count": 0,
        "errors_head": [],
    }
    payload["top_level"] = children_sizes(r"C:\\", errors)
    home = r"C:\Users\ziese"
    if Path(home).is_dir():
        payload["user_home"] = children_sizes(home, errors)
    local = r"C:\Users\ziese\AppData\Local"
    if Path(local).is_dir():
        payload["appdata_local"] = children_sizes(local, errors)
    roaming = r"C:\Users\ziese\AppData\Roaming"
    if Path(roaming).is_dir():
        payload["appdata_roaming"] = children_sizes(roaming, errors)
    for raw in KNOWN:
        size, files, reparse = walk_size(raw, errors)
        payload["known_paths"].append(
            {
                "path": raw,
                "bytes": size,
                "files": files,
                "reparse": reparse,
                "exists": Path(raw).exists(),
            }
        )
    payload["error_count"] = len(errors)
    payload["errors_head"] = errors[:40]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    used = payload["disk"]["used_bytes"]
    free = payload["disk"]["free_bytes"]
    total = payload["disk"]["total_bytes"]
    print(f"C: used={gb(used)} free={gb(free)} total={gb(total)}")
    print("TOP C:\\")
    for row in payload["top_level"][:15]:
        mark = " [junction]" if row.get("reparse") else ""
        print(f"  {gb(row['bytes']):>10}  {row['path']}{mark}")
    print("USER HOME")
    for row in payload["user_home"][:15]:
        mark = " [junction]" if row.get("reparse") else ""
        print(f"  {gb(row['bytes']):>10}  {row['path']}{mark}")
    print("APPDATA LOCAL")
    for row in payload["appdata_local"][:20]:
        print(f"  {gb(row['bytes']):>10}  {row['path']}")
    print(f"wrote {OUT_JSON}")
    print(f"errors={len(errors)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
