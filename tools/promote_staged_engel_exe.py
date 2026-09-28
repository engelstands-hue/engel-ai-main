#!/usr/bin/env python3
"""
Promote staged fourth-pass Engel.exe into live\\app safely.

Default project root:
    D:\\b.WorkSpace\\Engel App

What this script does:
- Refuses to overwrite live\\app\\Engel.exe if it appears locked/running.
- Finds a staged Engel.exe automatically, or accepts --staged-exe.
- Backs up the current live Engel.exe.
- Copies the staged Engel.exe into live\\app\\Engel.exe.
- Computes SHA-256 hashes for live Engel.exe and EngelSuperSwarmHive3D.exe.
- Appends a packaging note to:
    reports\\codex_bridge\\ALL_TABS_EXE_GUI_POLISH_FOURTH_PASS.md

What this script does NOT do:
- It does not stop Engel processes.
- It does not launch provider/API/network behavior.
- It does not modify source code.
- It does not mutate queues, trusted memory, ALIVE_STATE, routes, or autonomy state.

Recommended use:
    cd "D:\\b.WorkSpace\\Engel App"
    python .\\tools\\promote_staged_engel_exe.py

If auto-detection is ambiguous:
    python .\\tools\\promote_staged_engel_exe.py --staged-exe "D:\\b.WorkSpace\\Engel App\\path\\to\\staged\\Engel.exe"
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import os
import shutil
import sys
from pathlib import Path


DEFAULT_ROOT = Path(r"D:\b.WorkSpace\Engel App")
REPORT_REL = Path(r"reports\codex_bridge\ALL_TABS_EXE_GUI_POLISH_FOURTH_PASS.md")
LIVE_REL = Path(r"live\app\Engel.exe")
LIVE_3D_REL = Path(r"live\app\EngelSuperSwarmHive3D.exe")

EXCLUDE_DIR_NAMES = {
    ".git",
    "__pycache__",
    "backups",
    "models",
    "venv",
    ".venv",
    "node_modules",
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def is_same_path(a: Path, b: Path) -> bool:
    try:
        return a.resolve().samefile(b.resolve())
    except FileNotFoundError:
        return a.resolve() == b.resolve()
    except OSError:
        return a.resolve() == b.resolve()


def live_exe_appears_locked(path: Path) -> bool:
    """
    Windows does not allow renaming/replacing an EXE while it is running.
    This probes with a reversible rename. If it fails, assume the file is locked.
    """
    if not path.exists():
        return False

    probe = path.with_name(path.name + ".lock_probe")
    if probe.exists():
        # Avoid interfering with a leftover probe.
        return True

    try:
        path.rename(probe)
        probe.rename(path)
        return False
    except PermissionError:
        return True
    except OSError:
        return True


def iter_candidate_exes(root: Path, live_exe: Path):
    for current_root, dirs, files in os.walk(root):
        current_path = Path(current_root)

        # Prune excluded directories in-place.
        dirs[:] = [
            d for d in dirs
            if d not in EXCLUDE_DIR_NAMES and not d.lower().startswith("v2app-")
        ]

        if "Engel.exe" not in files:
            continue

        candidate = current_path / "Engel.exe"

        # Skip live exe itself.
        if is_same_path(candidate, live_exe):
            continue

        # Skip obvious backup/archive paths.
        lower_parts = [p.lower() for p in candidate.parts]
        if any(part in {"backup", "backups", "archive", "archives"} for part in lower_parts):
            continue

        yield candidate


def find_staged_exe(root: Path, live_exe: Path) -> Path:
    candidates = []
    for p in iter_candidate_exes(root, live_exe):
        try:
            stat = p.stat()
        except OSError:
            continue
        candidates.append((stat.st_mtime, stat.st_size, p))

    if not candidates:
        raise RuntimeError(
            "No staged Engel.exe candidate found. "
            "Pass --staged-exe with the rebuilt EXE path."
        )

    candidates.sort(reverse=True, key=lambda item: item[0])
    newest_time = candidates[0][0]
    newest = [item for item in candidates if item[0] == newest_time]

    # If multiple have the exact same timestamp, require explicit choice.
    if len(newest) > 1:
        msg = ["Multiple staged Engel.exe candidates are tied for newest:"]
        for _, size, p in newest:
            msg.append(f"  - {p} ({size} bytes)")
        msg.append("Pass --staged-exe explicitly.")
        raise RuntimeError("\n".join(msg))

    return candidates[0][2]


def backup_live_exe(live_exe: Path, backup_dir: Path) -> Path | None:
    if not live_exe.exists():
        return None

    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"Engel_live_before_promote_{stamp}.exe"
    shutil.copy2(live_exe, backup_path)
    return backup_path


def append_report(report_path: Path, text: str) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("a", encoding="utf-8") as f:
        f.write("\n\n")
        f.write(text.rstrip())
        f.write("\n")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Promote staged Engel.exe into live\\app safely.")
    parser.add_argument("--project-root", default=str(DEFAULT_ROOT), help="Engel project root.")
    parser.add_argument("--staged-exe", default="", help="Explicit staged Engel.exe path.")
    parser.add_argument("--no-backup", action="store_true", help="Do not back up existing live Engel.exe.")
    parser.add_argument("--dry-run", action="store_true", help="Show what would happen without copying.")
    args = parser.parse_args(argv)

    root = Path(args.project_root).resolve()
    live_exe = root / LIVE_REL
    live_3d_exe = root / LIVE_3D_REL
    report_path = root / REPORT_REL

    if not root.exists():
        print(f"ERROR: project root not found: {root}", file=sys.stderr)
        return 2

    if args.staged_exe:
        staged_exe = Path(args.staged_exe).resolve()
        if not staged_exe.exists():
            print(f"ERROR: staged EXE not found: {staged_exe}", file=sys.stderr)
            return 2
    else:
        try:
            staged_exe = find_staged_exe(root, live_exe)
        except RuntimeError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 2

    if is_same_path(staged_exe, live_exe):
        print("ERROR: staged EXE resolves to the live EXE. Refusing to promote.", file=sys.stderr)
        return 2

    if live_exe_appears_locked(live_exe):
        print("ERROR: live Engel.exe appears locked/running.", file=sys.stderr)
        print("Close Engel.exe first, then rerun this script.", file=sys.stderr)
        return 3

    staged_hash = sha256_file(staged_exe)
    staged_size = staged_exe.stat().st_size

    print("Promotion plan")
    print(f"- Project root: {root}")
    print(f"- Staged EXE:  {staged_exe}")
    print(f"- Staged SHA:  {staged_hash}")
    print(f"- Staged size: {staged_size} bytes")
    print(f"- Live target: {live_exe}")
    print(f"- Report:      {report_path}")

    if args.dry_run:
        print("DRY RUN: no files copied.")
        return 0

    backup_path = None
    if not args.no_backup:
        backup_path = backup_live_exe(live_exe, root / "backups" / "exe_promotions")
        if backup_path:
            print(f"- Backup:      {backup_path}")

    live_exe.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(staged_exe, live_exe)

    live_hash = sha256_file(live_exe)
    live_size = live_exe.stat().st_size
    live_mtime = _dt.datetime.fromtimestamp(live_exe.stat().st_mtime).isoformat(timespec="seconds")

    live_3d_hash = "MISSING"
    live_3d_size = "MISSING"
    if live_3d_exe.exists():
        live_3d_hash = sha256_file(live_3d_exe)
        live_3d_size = str(live_3d_exe.stat().st_size)

    stamp = _dt.datetime.now().isoformat(timespec="seconds")
    report_text = f"""## Final live Engel.exe promotion

Status: COMPLETE

Timestamp: {stamp}

Promotion:
- Staged EXE: `{staged_exe}`
- Live EXE: `{live_exe}`
- Live EXE modified time: `{live_mtime}`
- Live EXE size: `{live_size}` bytes
- Live EXE SHA-256: `{live_hash}`
- Backup created: `{backup_path if backup_path else "not requested / not applicable"}`

3D companion EXE:
- Path: `{live_3d_exe}`
- Size: `{live_3d_size}` bytes
- SHA-256: `{live_3d_hash}`

Safety statement:
- Packaging promotion only.
- No source feature changes.
- No provider/API/network/background/autonomy/queue/trusted-memory/source-edit behavior was added by this promotion script.
- This script did not stop processes, launch Engel, mutate routes, mutate queues, write trusted memory, write ALIVE_STATE, or enable runtime powers.
"""

    append_report(report_path, report_text)

    print("\nPromotion complete")
    print(f"- Live EXE SHA-256: {live_hash}")
    print(f"- Live EXE modified: {live_mtime}")
    print(f"- 3D EXE SHA-256: {live_3d_hash}")
    print(f"- Report updated: {report_path}")
    print("\nNext smoke command:")
    print(r'  Start-Process "D:\b.WorkSpace\Engel App\live\app\Engel.exe"')
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
