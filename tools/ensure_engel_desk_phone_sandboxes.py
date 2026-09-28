#!/usr/bin/env python3
"""Create each Discord desk sandbox on its assigned phone.

Uses the D: platform-tools adb. Does not start a worker, enqueue a job,
or install Discord. The Download folder is the phone's working room.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADB = ROOT / "tools" / "platform-tools" / "adb.exe"
STAGE = ROOT / "reports" / "codex_bridge" / "_phone_sandbox_stage"
PHONE_ROOT = "/storage/emulated/0/Download/EngelRemoteWorker/desks"
WORKERS = {
    "android_worker_alpha": "ANDROID_WORKER_ALPHA",
    "android_worker_beta": "ANDROID_WORKER_BETA",
    "android_worker_gamma": "ANDROID_WORKER_GAMMA",
}
DESKS = {
    "android_worker_alpha": ("research", "product", "architect", "training"),
    "android_worker_beta": ("support", "ops", "builder"),
    "android_worker_gamma": ("community", "sales", "memory", "proof"),
}


def _adb(serial: str, *args: str) -> subprocess.CompletedProcess[str]:
    if not ADB.is_file() or str(ADB).lower().startswith("c:"):
        raise SystemExit("D: adb is required")
    return subprocess.run(
        [str(ADB), "-s", serial, *args],
        capture_output=True,
        text=True,
        check=False,
    )


def _seed(desk: str, worker: str) -> Path:
    base = STAGE / worker / desk
    for rel in ("wiki", "sandbox/inbox", "sandbox/work", "sandbox/journal", "sandbox/collab"):
        (base / rel).mkdir(parents=True, exist_ok=True)
    (base / "sandbox" / "README.md").write_text(
        f"# {desk} sandbox\n\n"
        "This working room is on the phone. It is not Wiki One for Engel AI Main.\n"
        "Discord is not installed on this phone.\n"
        "Read wiki/ONE.md, inbox, work, and journal before you draft.\n"
        "Append journal/turns.jsonl after a draft.\n"
        "You cannot approve protected actions, start a training run, or apply a patch.\n",
        encoding="utf-8",
    )
    (base / "sandbox" / "work" / "OPEN.md").write_text(
        f"# Open work for {desk}\n\n"
        "No filed ask yet. New asks land in inbox/LAST_ASK.md.\n",
        encoding="utf-8",
    )
    (base / "wiki" / "ONE.md").write_text(
        f"# Engel {desk} second brain\n\n"
        f"This file lives on the phone sandbox for {desk}.\n"
        f"Worker: {worker}\n"
        "Authority: Josh > Guardian > Engel/runtime\n"
        "Speak as this desk. Do not speak as Engel AI Main.\n",
        encoding="utf-8",
    )
    (base / "sandbox" / "CHARTER.json").write_text(
        json.dumps({"desk": desk, "worker_id": worker, "discord_on_phone": False}, indent=2)
        + "\n",
        encoding="utf-8",
    )
    (base / "sandbox" / "journal" / "turns.jsonl").touch()
    return base


def main() -> int:
    listed = subprocess.run([str(ADB), "devices"], capture_output=True, text=True, check=False)
    online = set()
    for line in (listed.stdout or "").splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device":
            online.add(parts[0])
    if not online:
        print("NO_PHONES")
        return 2
    pushed = 0
    for worker, serial in WORKERS.items():
        if serial not in online:
            print(f"{worker} offline")
            continue
        for desk in DESKS[worker]:
            local = _seed(desk, worker)
            made = _adb(serial, "shell", "mkdir", "-p", PHONE_ROOT)
            if made.returncode != 0:
                print(f"{desk} mkdir_fail")
                continue
            copied = _adb(serial, "push", str(local), f"{PHONE_ROOT}/")
            if copied.returncode != 0:
                print(f"{desk} push_fail")
                continue
            check = _adb(serial, "shell", "test", "-f", f"{PHONE_ROOT}/{desk}/wiki/ONE.md")
            print(f"{desk} phone_sandbox={'yes' if check.returncode == 0 else 'no'}")
            pushed += 1
    print(f"PUSHED {pushed}")
    return 0 if pushed else 2


if __name__ == "__main__":
    raise SystemExit(main())
