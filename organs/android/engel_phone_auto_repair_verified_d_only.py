#!/usr/bin/env python3
"""
Engel Phone Auto Repair + Verify - D: drive only

Purpose:
- Reconnect previously approved Android phones over adb.
- Bootstrap wireless adb from an authorized USB connection when possible.
- Verify the phone is actually usable, not merely visible in `adb devices`.
- Write all Engel bridge state under D:\b.WorkSpace\Engel App by default.

Important:
- This script intentionally avoids writing to C:.
- New Android wireless pairing still requires Android's user-approved pairing code once.
- After a phone is trusted/authorized, reconnect can be mostly automatic.
"""

from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from tkinter import Tk, StringVar, Text, END, BOTH, LEFT, RIGHT, X, Y, DISABLED, NORMAL
from tkinter import ttk, messagebox

# -----------------------------
# D-ONLY CONFIGURATION
# -----------------------------

DEFAULT_ENGEL_ROOT = Path(r"D:\b.WorkSpace\Engel App")
DEFAULT_BRIDGE_DIR = DEFAULT_ENGEL_ROOT / "memory" / "phone_bridge"
DEFAULT_STATUS_FILE = DEFAULT_BRIDGE_DIR / "ENGEL_PHONE_BRIDGE_STATUS.json"
DEFAULT_SAVED_PHONES_FILE = DEFAULT_BRIDGE_DIR / "saved_phones.json"
DEFAULT_LOG_FILE = DEFAULT_BRIDGE_DIR / "phone_bridge_repair.log"
DEFAULT_LAUNCHERS_DIR = DEFAULT_ENGEL_ROOT / "launchers"
DEFAULT_CMD_LAUNCHER = DEFAULT_LAUNCHERS_DIR / "Engel Phone Auto Repair.cmd"

ADB_PORT = 5555


@dataclass
class PhoneRecord:
    serial: str
    ip: str | None = None
    port: int = ADB_PORT
    model: str | None = None
    product: str | None = None
    last_seen: str | None = None
    connection_kind: str | None = None
    verified: bool = False


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def ensure_d_only_path(path: Path) -> Path:
    resolved = path.expanduser()
    drive = resolved.drive.upper()
    if platform.system().lower().startswith("win") and drive and drive != "D:":
        raise RuntimeError(f"Refusing to use non-D drive path: {resolved}")
    return resolved


def ensure_dirs() -> None:
    for path in (DEFAULT_BRIDGE_DIR, DEFAULT_LAUNCHERS_DIR):
        ensure_d_only_path(path)
        path.mkdir(parents=True, exist_ok=True)


def append_log(message: str) -> None:
    ensure_dirs()
    line = f"[{now_iso()}] {message}\n"
    with DEFAULT_LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(line)


def run_cmd(args: list[str], timeout: int = 20) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
        )
        return proc.returncode, proc.stdout.strip()
    except FileNotFoundError:
        return 127, f"Command not found: {args[0]}"
    except subprocess.TimeoutExpired:
        return 124, f"Timed out: {' '.join(args)}"


def find_adb() -> str | None:
    candidates: list[Path] = []

    # Prefer D: locations. Do not search C:.
    candidates.extend([
        DEFAULT_ENGEL_ROOT / "tools" / "platform-tools" / "adb.exe",
        Path(r"D:\platform-tools\adb.exe"),
        Path(r"D:\Android\platform-tools\adb.exe"),
        Path.cwd() / "platform-tools" / "adb.exe",
        Path.cwd() / "adb.exe",
    ])

    for candidate in candidates:
        if candidate.exists():
            return str(candidate)

    # PATH lookup may resolve anywhere. Allow it only if the resolved path is not on C:.
    found = shutil.which("adb")
    if found:
        p = Path(found)
        if platform.system().lower().startswith("win") and p.drive.upper() == "C:":
            return None
        return found

    return None


def parse_adb_devices(output: str) -> list[dict[str, str]]:
    devices: list[dict[str, str]] = []
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line or line.lower().startswith("list of devices"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        serial, state = parts[0], parts[1]
        props = {"serial": serial, "state": state, "raw": line}
        for part in parts[2:]:
            if ":" in part:
                k, v = part.split(":", 1)
                props[k] = v
        devices.append(props)
    return devices


def adb(adb_path: str, *args: str, timeout: int = 20) -> tuple[int, str]:
    return run_cmd([adb_path, *args], timeout=timeout)


def adb_serial(adb_path: str, serial: str, *args: str, timeout: int = 20) -> tuple[int, str]:
    return run_cmd([adb_path, "-s", serial, *args], timeout=timeout)


def load_saved_phones() -> list[PhoneRecord]:
    ensure_dirs()
    if not DEFAULT_SAVED_PHONES_FILE.exists():
        return []
    try:
        data = json.loads(DEFAULT_SAVED_PHONES_FILE.read_text(encoding="utf-8"))
        return [PhoneRecord(**item) for item in data.get("phones", [])]
    except Exception as exc:
        append_log(f"Could not load saved phones: {exc}")
        return []


def save_phones(records: list[PhoneRecord]) -> None:
    ensure_dirs()
    unique: dict[str, PhoneRecord] = {}
    for rec in records:
        if rec.ip:
            key = f"{rec.ip}:{rec.port}"
        else:
            key = rec.serial
        unique[key] = rec
    payload = {
        "updated_at": now_iso(),
        "storage_root": str(DEFAULT_BRIDGE_DIR),
        "phones": [asdict(r) for r in unique.values()],
    }
    DEFAULT_SAVED_PHONES_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_status(status: dict) -> None:
    ensure_dirs()
    status["updated_at"] = now_iso()
    status["storage_root"] = str(DEFAULT_BRIDGE_DIR)
    status["d_drive_only"] = True
    DEFAULT_STATUS_FILE.write_text(json.dumps(status, indent=2), encoding="utf-8")


def get_prop(adb_path: str, serial: str, prop: str) -> str | None:
    code, out = adb_serial(adb_path, serial, "shell", "getprop", prop, timeout=10)
    if code == 0 and out.strip():
        return out.strip().splitlines()[-1].strip()
    return None


def get_phone_ip(adb_path: str, serial: str) -> str | None:
    # Try modern ip command first.
    code, out = adb_serial(adb_path, serial, "shell", "ip", "-f", "inet", "addr", "show", "wlan0", timeout=10)
    if code == 0:
        m = re.search(r"inet\s+(\d+\.\d+\.\d+\.\d+)/", out)
        if m and not m.group(1).startswith("127."):
            return m.group(1)

    # Fallback: parse all IPv4s from `ip addr` and avoid loopback/link-local.
    code, out = adb_serial(adb_path, serial, "shell", "ip", "addr", timeout=10)
    if code == 0:
        for ip in re.findall(r"inet\s+(\d+\.\d+\.\d+\.\d+)/", out):
            if not ip.startswith(("127.", "169.254.")):
                return ip
    return None


def verify_device(adb_path: str, serial: str) -> dict:
    result = {
        "serial": serial,
        "state": "unknown",
        "verified": False,
        "model": None,
        "product": None,
        "android_release": None,
        "ip": None,
        "checks": [],
    }

    checks = [
        ("get_state", ["get-state"]),
        ("echo", ["shell", "echo", "ENGEL_PHONE_BRIDGE_OK"]),
        ("sdk", ["shell", "getprop", "ro.build.version.sdk"]),
    ]

    for name, args in checks:
        code, out = adb_serial(adb_path, serial, *args, timeout=12)
        ok = code == 0 and (name != "echo" or "ENGEL_PHONE_BRIDGE_OK" in out)
        result["checks"].append({"name": name, "ok": ok, "code": code, "output": out[-500:]})
        if name == "get_state" and code == 0:
            result["state"] = out.strip()

    result["model"] = get_prop(adb_path, serial, "ro.product.model")
    result["product"] = get_prop(adb_path, serial, "ro.product.name")
    result["android_release"] = get_prop(adb_path, serial, "ro.build.version.release")
    result["ip"] = get_phone_ip(adb_path, serial)
    result["verified"] = all(c["ok"] for c in result["checks"][:2])
    return result


def connect_saved(adb_path: str, log) -> list[PhoneRecord]:
    saved = load_saved_phones()
    updated: list[PhoneRecord] = []
    for rec in saved:
        if not rec.ip:
            updated.append(rec)
            continue
        target = f"{rec.ip}:{rec.port}"
        log(f"Connecting saved phone {target} ...")
        code, out = adb(adb_path, "connect", target, timeout=20)
        log(out or f"adb connect exit {code}")
        rec.last_seen = now_iso()
        rec.connection_kind = "wireless_saved"
        updated.append(rec)
    save_phones(updated)
    return updated


def full_auto_repair(adb_path: str, package_name: str | None, log) -> dict:
    append_log("Starting full auto repair D-only")
    status = {
        "ok": False,
        "message": "Started",
        "adb_path": adb_path,
        "phones": [],
        "errors": [],
    }

    code, out = adb(adb_path, "start-server", timeout=20)
    log(out or "adb server started")

    connect_saved(adb_path, log)

    code, out = adb(adb_path, "devices", "-l", timeout=20)
    log(out)
    devices = parse_adb_devices(out)

    records = load_saved_phones()

    for dev in devices:
        serial = dev["serial"]
        state = dev.get("state", "unknown")
        if state == "unauthorized":
            msg = f"{serial} is unauthorized. Unlock phone and approve USB debugging prompt."
            log(msg)
            status["errors"].append(msg)
            status["phones"].append({**dev, "verified": False, "reason": "unauthorized"})
            continue
        if state == "offline":
            msg = f"{serial} is offline. Replug USB or toggle Wireless debugging, then retry."
            log(msg)
            status["errors"].append(msg)
            status["phones"].append({**dev, "verified": False, "reason": "offline"})
            continue
        if state != "device":
            status["phones"].append({**dev, "verified": False, "reason": state})
            continue

        log(f"Verifying {serial} ...")
        verified = verify_device(adb_path, serial)
        log(f"Verified={verified['verified']} model={verified.get('model')} ip={verified.get('ip')}")

        # If USB serial and IP exists, enable tcpip and connect wirelessly.
        is_wireless = ":" in serial
        if not is_wireless and verified.get("ip"):
            ip = verified["ip"]
            log(f"USB phone found. Enabling tcpip {ADB_PORT} for {ip} ...")
            code, tcp_out = adb_serial(adb_path, serial, "tcpip", str(ADB_PORT), timeout=20)
            log(tcp_out or f"tcpip exit {code}")
            time.sleep(2)
            target = f"{ip}:{ADB_PORT}"
            code, con_out = adb(adb_path, "connect", target, timeout=20)
            log(con_out or f"connect exit {code}")
            # Reverify wireless target if possible.
            code, state_out = adb_serial(adb_path, target, "get-state", timeout=10)
            if code == 0 and "device" in state_out:
                verified_wireless = verify_device(adb_path, target)
                status["phones"].append(verified_wireless)
                records.append(PhoneRecord(
                    serial=target,
                    ip=ip,
                    port=ADB_PORT,
                    model=verified_wireless.get("model"),
                    product=verified_wireless.get("product"),
                    last_seen=now_iso(),
                    connection_kind="wireless_bootstrapped_from_usb",
                    verified=bool(verified_wireless.get("verified")),
                ))
            else:
                status["errors"].append(f"Could not verify wireless target {target}: {state_out}")

        status["phones"].append(verified)
        records.append(PhoneRecord(
            serial=serial,
            ip=verified.get("ip"),
            port=ADB_PORT,
            model=verified.get("model"),
            product=verified.get("product"),
            last_seen=now_iso(),
            connection_kind="wireless" if is_wireless else "usb",
            verified=bool(verified.get("verified")),
        ))

        if package_name and verified.get("verified"):
            log(f"Launching package {package_name} on {serial} ...")
            code, launch_out = adb_serial(adb_path, serial, "shell", "monkey", "-p", package_name, "1", timeout=15)
            log(launch_out or f"launch exit {code}")

    save_phones(records)
    status["ok"] = any(p.get("verified") for p in status["phones"] if isinstance(p, dict))
    status["message"] = "At least one phone verified" if status["ok"] else "No phone fully verified"
    write_status(status)
    append_log(status["message"])
    return status


def create_d_launcher(script_path: Path, log) -> None:
    ensure_dirs()
    script_path = ensure_d_only_path(script_path)
    launcher = ensure_d_only_path(DEFAULT_CMD_LAUNCHER)
    launcher.write_text(
        "@echo off\n"
        "setlocal\n"
        f"cd /d \"{script_path.parent}\"\n"
        f"python \"{script_path}\"\n"
        "pause\n",
        encoding="utf-8",
    )
    log(f"Created D: launcher: {launcher}")


class App:
    def __init__(self, root: Tk):
        self.root = root
        self.root.title("Engel Phone Auto Repair + Verify - D Only")
        self.adb_path = find_adb()
        self.package_var = StringVar(value="")
        self.status_var = StringVar(value="Ready. Storage is D-only.")

        frame = ttk.Frame(root, padding=10)
        frame.pack(fill=BOTH, expand=True)

        ttk.Label(frame, text="Engel Phone Bridge - D: Drive Only", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        ttk.Label(frame, text=f"Storage: {DEFAULT_BRIDGE_DIR}").pack(anchor="w")
        ttk.Label(frame, text=f"Status JSON: {DEFAULT_STATUS_FILE}").pack(anchor="w")
        ttk.Label(frame, text=f"adb: {self.adb_path or 'NOT FOUND on D: or non-C PATH'}").pack(anchor="w")

        pkg_frame = ttk.Frame(frame)
        pkg_frame.pack(fill=X, pady=(10, 5))
        ttk.Label(pkg_frame, text="Optional Android package to launch:").pack(side=LEFT)
        ttk.Entry(pkg_frame, textvariable=self.package_var, width=45).pack(side=LEFT, padx=5, fill=X, expand=True)

        btns = ttk.Frame(frame)
        btns.pack(fill=X, pady=5)
        ttk.Button(btns, text="FULL AUTO REPAIR + VERIFY", command=self.on_repair).pack(side=LEFT, padx=3)
        ttk.Button(btns, text="Check adb Devices", command=self.on_devices).pack(side=LEFT, padx=3)
        ttk.Button(btns, text="Create D: Launcher", command=self.on_launcher).pack(side=LEFT, padx=3)
        ttk.Button(btns, text="Open D: Bridge Folder", command=self.on_open_folder).pack(side=LEFT, padx=3)

        ttk.Label(frame, textvariable=self.status_var).pack(anchor="w", pady=(5, 0))

        self.text = Text(frame, height=22, width=100)
        self.text.pack(fill=BOTH, expand=True, pady=(5, 0))
        self.log("Ready. This version refuses C: storage.")
        if not self.adb_path:
            self.log("ADB not found. Put platform-tools on D:, for example D:\\platform-tools\\adb.exe")

    def log(self, msg: str) -> None:
        self.text.configure(state=NORMAL)
        self.text.insert(END, f"[{now_iso()}] {msg}\n")
        self.text.see(END)
        self.text.configure(state=DISABLED)
        append_log(msg)

    def require_adb(self) -> bool:
        if self.adb_path:
            return True
        messagebox.showerror("adb not found", "adb.exe was not found on D: or a non-C PATH. Put platform-tools on D:, then retry.")
        return False

    def on_repair(self) -> None:
        if not self.require_adb():
            return
        self.status_var.set("Running repair...")
        package = self.package_var.get().strip() or None

        def worker():
            try:
                status = full_auto_repair(self.adb_path, package, self.log)
                self.status_var.set(status["message"])
                self.log(f"Wrote status JSON: {DEFAULT_STATUS_FILE}")
            except Exception as exc:
                self.status_var.set("Repair failed")
                self.log(f"ERROR: {exc}")
                write_status({"ok": False, "message": str(exc), "phones": [], "errors": [str(exc)]})

        threading.Thread(target=worker, daemon=True).start()

    def on_devices(self) -> None:
        if not self.require_adb():
            return
        code, out = adb(self.adb_path, "devices", "-l", timeout=20)
        self.log(out or f"adb devices exit {code}")

    def on_launcher(self) -> None:
        try:
            create_d_launcher(Path(__file__).resolve(), self.log)
            messagebox.showinfo("Launcher created", f"Created:\n{DEFAULT_CMD_LAUNCHER}")
        except Exception as exc:
            self.log(f"ERROR creating launcher: {exc}")
            messagebox.showerror("Launcher error", str(exc))

    def on_open_folder(self) -> None:
        ensure_dirs()
        if platform.system().lower().startswith("win"):
            os.startfile(str(DEFAULT_BRIDGE_DIR))  # type: ignore[attr-defined]
        else:
            self.log(str(DEFAULT_BRIDGE_DIR))


def main() -> int:
    ensure_dirs()
    root = Tk()
    App(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
