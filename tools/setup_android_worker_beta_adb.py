"""Bounded Android Studio / ADB setup helper for Android Worker Beta.

Mirrors tools/setup_android_worker_alpha_adb.py with beta paths, beta job
id, and beta-specific Termux shortcut name. Modes:

  --status            Local readiness + ADB device list, no transfer.
  --prepare-commands  Print exact ADB commands without executing them.
  --push              Run the prepared push commands. Requires
                      --i-understand-this-uses-adb.
  --check-on-device   Read-only ls of the beta folders on the phone.
  --prepare-one-line-termux-finish-beta
                      Print app-scoped ADB push + one-line Termux finish
                      commands without executing them.

Safety: this script only pushes/lists files. It does NOT install Termux
or any package, does NOT load models, does NOT run the worker job on
the phone, does NOT touch network/SSH/cloud sync/ADB wireless, does NOT
write trusted memory, and does NOT apply patches.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKER_ID = "android_worker_beta"
WORKER_NAME = "Android Worker Beta"
# Beta phone is the moto g fast (serial ANDROID_WORKER_BETA). See
# memory/ENGEL_PHONE_DEVICE_MAP_V1.md for the authoritative phone-to-worker map.
TARGET_DEVICE_HINT = "moto_g_fast"

JOB_ID = "20260519T120000Z_android_worker_beta_draft_candidate_json_extract_beta_package_fields"
INPUT_BASENAME = "beta_package_readme.md"

BETA_PACKAGE = ROOT / "remote_workers" / WORKER_ID
JOB_PACKET = BETA_PACKAGE / "jobs" / (JOB_ID + ".json")
STAGED_INPUT = BETA_PACKAGE / "inbox" / "assigned_inputs" / JOB_ID / INPUT_BASENAME

PHONE_PARENT = "/sdcard/EngelRemoteWorker"
PHONE_ROOT = PHONE_PARENT + "/" + WORKER_ID
TERMUX_APP_SCOPED_PARENT = "/sdcard/Android/data/com.termux/files/EngelRemoteWorker"
TERMUX_APP_SCOPED_ROOT = TERMUX_APP_SCOPED_PARENT + "/" + WORKER_ID
TERMUX_APP_SCOPED_SHELL_ROOT = "~/storage/external-1/EngelRemoteWorker/" + WORKER_ID
REMOTE_JOB_PACKET_DIR = PHONE_ROOT + "/jobs"
REMOTE_INPUT_DIR = PHONE_ROOT + "/inbox/assigned_inputs/" + JOB_ID

PHONE_DIRS = [
    PHONE_ROOT + "/config",
    PHONE_ROOT + "/inbox",
    PHONE_ROOT + "/inbox/queen_choices",
    PHONE_ROOT + "/inbox/assigned_inputs",
    PHONE_ROOT + "/inbox/assigned_inputs/" + JOB_ID,
    PHONE_ROOT + "/jobs",
    PHONE_ROOT + "/outbox",
    PHONE_ROOT + "/logs",
    PHONE_ROOT + "/receipts",
    PHONE_ROOT + "/status",
]

# Files we always push: full package (config, scripts, README, UI).
# We push the package wholesale via `adb push`, then push the specific
# job packet + staged input individually to be sure they land in place.
KNOWN_USER_ADB = Path(r"C:\Users\ziese\AppData\Local\Android\Sdk\platform-tools\adb.exe")


def resolve_adb(explicit: str | None) -> str | None:
    if explicit:
        path = Path(explicit)
        if path.exists():
            return str(path)
    if KNOWN_USER_ADB.exists():
        return str(KNOWN_USER_ADB)
    found = shutil.which("adb")
    return found


def adb_base(adb: str, device_id: str | None) -> list[str]:
    parts = [adb]
    if device_id:
        parts.extend(["-s", device_id])
    return parts


def command_text(parts: list[str]) -> str:
    quoted = []
    for p in parts:
        if " " in p or ":" in p:
            quoted.append('"' + p + '"')
        else:
            quoted.append(p)
    return " ".join(quoted)


def run_adb(parts: list[str], timeout: int = 90) -> tuple[int, str, str]:
    try:
        completed = subprocess.run(
            parts,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except subprocess.TimeoutExpired as exc:
        return 124, exc.stdout or "", exc.stderr or "timeout"
    except FileNotFoundError as exc:
        return 127, "", str(exc)
    return completed.returncode, completed.stdout or "", completed.stderr or ""


def list_devices(adb: str) -> list[tuple[str, str]]:
    rc, out, _ = run_adb([adb, "devices", "-l"], timeout=30)
    if rc != 0:
        return []
    devices: list[tuple[str, str]] = []
    for line in out.splitlines():
        stripped = line.strip()
        if not stripped or stripped.lower().startswith("list of devices"):
            continue
        parts = stripped.split()
        if len(parts) >= 2 and parts[1] == "device":
            devices.append((parts[0], " ".join(parts[2:])))
    return devices


def auto_target_device(adb: str) -> tuple[str | None, list[tuple[str, str]]]:
    devices = list_devices(adb)
    matches = [device for device in devices if TARGET_DEVICE_HINT in device[1].lower()]
    if len(matches) == 1:
        return matches[0][0], devices
    return None, devices


def status(adb: str | None, device_id: str | None) -> int:
    print("Android Studio Setup for Android Worker Beta")
    print()
    print("Worker: " + WORKER_NAME + " (" + WORKER_ID + ")")
    print("Phone target folder: " + PHONE_ROOT)
    print("Worker package: " + str(BETA_PACKAGE.relative_to(ROOT)))
    print("Job packet: " + str(JOB_PACKET.relative_to(ROOT)))
    print("Staged input: " + str(STAGED_INPUT.relative_to(ROOT)))
    print("Local job packet exists: " + str(JOB_PACKET.is_file()))
    print("Local staged input exists: " + str(STAGED_INPUT.is_file()))
    print("ADB path: " + (adb or "(not found)"))
    if not adb:
        print("ADB not found on PATH or Android Studio SDK. Install Android Studio's platform-tools and retry.")
        return 1
    devices = list_devices(adb)
    print("Devices visible: " + str(len(devices)))
    for d_id, info in devices:
        print("  - " + d_id + "  " + info)
    chosen = device_id
    if not chosen:
        chosen, _ = auto_target_device(adb)
    print("Selected device for beta push: " + (chosen or "(none — pass --device-id explicitly if more than one device is connected and none match '" + TARGET_DEVICE_HINT + "')"))
    print()
    print("Safety:")
    print("- This helper only pushes/lists files. No install, no run, no model load.")
    print("- --push requires --i-understand-this-uses-adb.")
    print("- No Termux/app/package/model install automation, Hermes/Ollama/llama.cpp path,")
    print("  network server, SSH, cloud sync, ADB wireless, background worker, startup autorun,")
    print("  trusted-memory write, or patch apply is enabled. Hermes remains rejected.")
    return 0


def prepared_command_groups(adb: str, device_id: str) -> list[tuple[str, list[str]]]:
    base = adb_base(adb, device_id)
    groups: list[tuple[str, list[str]]] = [
        ("create phone folders", base + ["shell", "mkdir", "-p", *PHONE_DIRS]),
        ("push beta worker package", base + ["push", str(BETA_PACKAGE), PHONE_PARENT + "/"]),
        ("push beta job packet (explicit, in case the package push skipped it)", base + ["push", str(JOB_PACKET), REMOTE_JOB_PACKET_DIR + "/"]),
        ("push beta staged input file", base + ["push", str(STAGED_INPUT), REMOTE_INPUT_DIR + "/"]),
    ]
    return groups


def app_scoped_review_command_groups(adb: str | None = None, device_id: str | None = None) -> list[tuple[str, list[str]]]:
    base = adb_base(adb or "adb", device_id)
    return [
        ("create Termux app-scoped beta folder", base + ["shell", "mkdir", "-p", TERMUX_APP_SCOPED_ROOT]),
        ("push beta worker package to Termux app-scoped storage", base + ["push", str(BETA_PACKAGE), TERMUX_APP_SCOPED_PARENT + "/"]),
        (
            "push beta job packet to Termux app-scoped storage",
            base + ["push", str(JOB_PACKET), TERMUX_APP_SCOPED_ROOT + "/jobs/"],
        ),
        (
            "push beta staged input to Termux app-scoped storage",
            base + ["push", str(STAGED_INPUT), TERMUX_APP_SCOPED_ROOT + "/inbox/assigned_inputs/" + JOB_ID + "/"],
        ),
    ]


def one_line_termux_finish_beta_command() -> str:
    return "cd " + TERMUX_APP_SCOPED_SHELL_ROOT + " && python finish_beta_job.py"


def prepare_one_line_termux_finish_beta(adb: str | None, device_id: str | None) -> int:
    display_adb = adb or "adb"
    print("# Android Worker Beta app-scoped Termux finish commands (review only - nothing is executed)")
    print("# Use these if Android scoped storage blocks Termux from /sdcard/EngelRemoteWorker.")
    print("# ADB copy target:")
    print("#   " + TERMUX_APP_SCOPED_ROOT)
    print("# Termux path:")
    print("#   " + TERMUX_APP_SCOPED_SHELL_ROOT)
    print("# If more than one Android device is connected, add --device-id or insert adb -s <device-id>.")
    print("")
    print("# ADB commands to review/run from Windows:")
    print(command_text(adb_base(display_adb, device_id) + ["devices"]))
    for label, parts in app_scoped_review_command_groups(display_adb, device_id):
        print("")
        print("# " + label)
        print(command_text(parts))
    print("")
    print("# Paste this exact line into Termux after the app-scoped push:")
    print(one_line_termux_finish_beta_command())
    print("")
    print("# Optional ADB pull commands after the Termux command creates real returned files:")
    for folder in ["status", "outbox", "logs", "receipts"]:
        print(command_text(adb_base(display_adb, device_id) + ["pull", TERMUX_APP_SCOPED_ROOT + "/" + folder, str(BETA_PACKAGE / folder)]))
    print("")
    print("Safety:")
    print("- No ADB command is executed by this prepare mode.")
    print("- The Termux line runs finish_beta_job.py once only after the human pastes it.")
    print("- No install, package download, model runtime, provider/network, trusted-memory write, or patch apply is enabled.")
    return 0


def prepare_commands(adb: str | None, device_id: str | None) -> int:
    if not adb:
        print("ADB not found.")
        return 1
    chosen = device_id
    if not chosen:
        chosen, _ = auto_target_device(adb)
    if not chosen:
        print("No device matched '" + TARGET_DEVICE_HINT + "'. Pass --device-id explicitly.")
        return 1
    print("# Android Worker Beta ADB push commands (review only — nothing is executed)")
    print("# Target device: " + chosen)
    print(command_text([adb, "devices"]))
    for label, parts in prepared_command_groups(adb, chosen):
        print("")
        print("# " + label)
        print(command_text(parts))
    print("")
    print("# After push, optionally verify what landed on the phone:")
    base = adb_base(adb, chosen)
    print(command_text(base + ["shell", "ls", "-1", PHONE_ROOT]))
    print(command_text(base + ["shell", "ls", "-1", REMOTE_JOB_PACKET_DIR]))
    print(command_text(base + ["shell", "ls", "-1", REMOTE_INPUT_DIR]))
    return 0


def push(adb: str | None, device_id: str | None, ack: bool) -> int:
    if not adb:
        print("ADB not found.")
        return 1
    if not ack:
        print("Refusing to push without --i-understand-this-uses-adb.")
        return 2
    if not JOB_PACKET.is_file():
        print("Local job packet missing: " + str(JOB_PACKET))
        return 1
    if not STAGED_INPUT.is_file():
        print("Local staged input missing: " + str(STAGED_INPUT))
        return 1
    chosen = device_id
    if not chosen:
        chosen, _ = auto_target_device(adb)
    if not chosen:
        print("No device matched '" + TARGET_DEVICE_HINT + "'. Pass --device-id explicitly.")
        return 1
    print("Pushing Android Worker Beta package to device: " + chosen)
    fail = 0
    for label, parts in prepared_command_groups(adb, chosen):
        print("")
        print("[CMD] " + label)
        print("  " + command_text(parts))
        rc, out, err = run_adb(parts, timeout=180)
        if out:
            for line in out.splitlines():
                print("  > " + line)
        if err:
            for line in err.splitlines():
                print("  ! " + line)
        if rc != 0:
            print("  exit code: " + str(rc))
            fail += 1
    if fail:
        print("")
        print("[FAIL] " + str(fail) + " push command(s) failed.")
        return 1
    print("")
    print("[OK] Beta package pushed to " + PHONE_ROOT + " on device " + chosen + ".")
    print("Next: open Termux on the second phone and run:")
    print("    cd /sdcard/EngelRemoteWorker/" + WORKER_ID)
    print("    python start_remote_worker_ui.py")
    return 0


def check_on_device(adb: str | None, device_id: str | None) -> int:
    if not adb:
        print("ADB not found.")
        return 1
    chosen = device_id
    if not chosen:
        chosen, _ = auto_target_device(adb)
    if not chosen:
        print("No device matched '" + TARGET_DEVICE_HINT + "'. Pass --device-id explicitly.")
        return 1
    base = adb_base(adb, chosen)
    print("Reading on-device state of " + PHONE_ROOT + " on " + chosen + " (read-only)")
    for label, parts in [
        ("phone root", base + ["shell", "ls", "-1", PHONE_ROOT]),
        ("config",     base + ["shell", "ls", "-1", PHONE_ROOT + "/config"]),
        ("jobs",       base + ["shell", "ls", "-1", REMOTE_JOB_PACKET_DIR]),
        ("staged input", base + ["shell", "ls", "-1", REMOTE_INPUT_DIR]),
        ("ui files",   base + ["shell", "ls", "-1", PHONE_ROOT + "/remote_worker_phone_ui.py", PHONE_ROOT + "/start_remote_worker_ui.py"]),
    ]:
        print("")
        print("# " + label)
        rc, out, err = run_adb(parts, timeout=30)
        for line in (out or "").splitlines():
            print("  " + line)
        for line in (err or "").splitlines():
            print("  ! " + line)
        if rc != 0:
            print("  (exit " + str(rc) + ")")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bounded ADB setup helper for Android Worker Beta.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--status", action="store_true", help="Local readiness + ADB device list. No transfer.")
    mode.add_argument("--prepare-commands", action="store_true", help="Print exact ADB commands without executing them.")
    mode.add_argument("--push", action="store_true", help="Push beta package to the phone. Requires --i-understand-this-uses-adb.")
    mode.add_argument("--check-on-device", action="store_true", help="Read-only ls of beta folders on the phone.")
    mode.add_argument("--prepare-one-line-termux-finish-beta", action="store_true", help="Print app-scoped ADB push + one-line Termux finish commands without executing them.")
    parser.add_argument("--device-id", default=None, help="ADB device id to target. If omitted, auto-targets the '" + TARGET_DEVICE_HINT + "' phone.")
    parser.add_argument("--adb-path", default=None, help="Explicit path to adb.exe (overrides Android SDK auto-detect).")
    parser.add_argument("--i-understand-this-uses-adb", action="store_true", help="Explicit acknowledgment required by --push.")
    args = parser.parse_args(argv)

    adb = resolve_adb(args.adb_path)
    if args.status:
        return status(adb, args.device_id)
    if args.prepare_commands:
        return prepare_commands(adb, args.device_id)
    if args.push:
        return push(adb, args.device_id, args.i_understand_this_uses_adb)
    if args.check_on_device:
        return check_on_device(adb, args.device_id)
    if args.prepare_one_line_termux_finish_beta:
        return prepare_one_line_termux_finish_beta(adb, args.device_id)
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
