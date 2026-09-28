#!/usr/bin/env python3
"""
Engel Phone Auto Repair - Verified App Bridge Version

Purpose
- One-button repair for Android ADB USB/Wi-Fi phone connections.
- Verifies the phone is actually usable, not merely listed as connected.
- Saves known wireless targets.
- Writes a machine-readable status JSON that Engel/Claude/other apps can read.
- Optionally starts an Android app package on the phone after connection.

Best path
1. Plug phone in by USB once.
2. Enable Developer Options -> USB debugging.
3. Accept the phone's USB debugging trust prompt.
4. Run this script and click FULL AUTO REPAIR + VERIFY.

Important Android limit
- A brand-new wireless debugging pair still requires the phone-generated pairing code once.
- After a device is trusted, reconnect can be automated.
"""

from __future__ import annotations

import json
import os
import platform
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional, Tuple

try:
    import tkinter as tk
    from tkinter import messagebox, simpledialog
except Exception as exc:
    raise SystemExit(f"Tkinter is required for this GUI: {exc}")

APP_TITLE = "Engel Phone Auto Repair - Verified"
DEFAULT_ADB_PORT = 5555

STATE_DIR = Path.home() / ".engel_phone_bridge"
STATE_DIR.mkdir(parents=True, exist_ok=True)
SAVED_TARGETS_FILE = STATE_DIR / "saved_wireless_targets.json"
STATUS_FILE = STATE_DIR / "phone_bridge_status.json"
LOG_FILE = STATE_DIR / "phone_bridge.log"

# Also try to write a copy in likely Engel workspace locations when they exist.
POSSIBLE_ENGEL_STATUS_DIRS = [
    Path("D:/b.WorkSpace/Engel App/memory"),
    Path("D:/b.WorkSpace/memory"),
    Path("D:/Engel App/memory"),
]


@dataclass
class DeviceInfo:
    serial: str
    state: str
    transport: str
    model: str = ""
    product: str = ""
    device: str = ""


@dataclass
class BridgeStatus:
    timestamp: float
    ok: bool
    devices: List[DeviceInfo]
    saved_targets: List[str]
    selected_app_package: str
    notes: List[str]


class AdbError(RuntimeError):
    pass


def log_line(text: str) -> None:
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{stamp}] {text}"
    try:
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def find_adb() -> str:
    candidates = []
    env_adb = os.environ.get("ADB")
    if env_adb:
        candidates.append(env_adb)
    candidates.extend([
        "adb.exe" if os.name == "nt" else "adb",
        str(Path.cwd() / "adb.exe"),
        str(Path.cwd() / "platform-tools" / "adb.exe"),
        str(Path.home() / "AppData" / "Local" / "Android" / "Sdk" / "platform-tools" / "adb.exe"),
        "C:/Android/platform-tools/adb.exe",
        "C:/platform-tools/adb.exe",
        "D:/platform-tools/adb.exe",
    ])
    for c in candidates:
        found = shutil.which(c) if not Path(c).exists() else c
        if found:
            return str(found)
    raise AdbError("adb was not found. Install Android platform-tools or place this script beside adb.exe.")


def run_cmd(args: List[str], timeout: int = 20) -> Tuple[int, str, str]:
    log_line("RUN: " + " ".join(args))
    try:
        p = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
            shell=False,
        )
        out = p.stdout.strip()
        err = p.stderr.strip()
        if out:
            log_line("OUT: " + out.replace("\n", " | "))
        if err:
            log_line("ERR: " + err.replace("\n", " | "))
        return p.returncode, out, err
    except subprocess.TimeoutExpired:
        log_line("TIMEOUT: " + " ".join(args))
        return 124, "", "Timed out"


def adb(args: List[str], timeout: int = 20, serial: Optional[str] = None) -> Tuple[int, str, str]:
    exe = find_adb()
    cmd = [exe]
    if serial:
        cmd += ["-s", serial]
    cmd += args
    return run_cmd(cmd, timeout=timeout)


def adb_ok(args: List[str], timeout: int = 20, serial: Optional[str] = None) -> str:
    code, out, err = adb(args, timeout=timeout, serial=serial)
    if code != 0:
        raise AdbError(err or out or f"adb command failed: {' '.join(args)}")
    return out


def parse_devices(output: str) -> List[DeviceInfo]:
    devices: List[DeviceInfo] = []
    for line in output.splitlines():
        line = line.strip()
        if not line or line.lower().startswith("list of devices"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        serial = parts[0]
        state = parts[1]
        kv = {}
        for item in parts[2:]:
            if ":" in item:
                k, v = item.split(":", 1)
                kv[k] = v
        transport = "wireless" if ":" in serial else "usb"
        devices.append(DeviceInfo(
            serial=serial,
            state=state,
            transport=transport,
            model=kv.get("model", ""),
            product=kv.get("product", ""),
            device=kv.get("device", ""),
        ))
    return devices


def list_devices() -> List[DeviceInfo]:
    out = adb_ok(["devices", "-l"], timeout=15)
    return parse_devices(out)


def verify_device(serial: str) -> Tuple[bool, str]:
    # A real usable device should answer shell commands. Merely "connected" is not enough.
    tests = [
        (["shell", "getprop", "ro.product.model"], "model"),
        (["shell", "id"], "shell id"),
        (["shell", "echo", "ENGEL_ADB_OK"], "echo"),
    ]
    notes = []
    for cmd, label in tests:
        code, out, err = adb(cmd, timeout=12, serial=serial)
        if code != 0:
            return False, f"{serial}: failed {label}: {err or out}"
        notes.append(f"{label}={out.strip()[:80]}")
    return True, f"{serial}: verified usable ({'; '.join(notes)})"


def load_saved_targets() -> List[str]:
    if not SAVED_TARGETS_FILE.exists():
        return []
    try:
        data = json.loads(SAVED_TARGETS_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [str(x) for x in data]
    except Exception:
        pass
    return []


def save_targets(targets: List[str]) -> None:
    unique = []
    for t in targets:
        t = t.strip()
        if t and t not in unique:
            unique.append(t)
    SAVED_TARGETS_FILE.write_text(json.dumps(unique, indent=2), encoding="utf-8")


def write_status(status: BridgeStatus) -> None:
    raw = asdict(status)
    text = json.dumps(raw, indent=2, sort_keys=True)
    STATUS_FILE.write_text(text, encoding="utf-8")
    for d in POSSIBLE_ENGEL_STATUS_DIRS:
        try:
            if d.exists():
                (d / "ENGEL_PHONE_BRIDGE_STATUS.json").write_text(text, encoding="utf-8")
        except Exception as exc:
            log_line(f"Could not write Engel status copy to {d}: {exc}")


def get_phone_ip(serial: str) -> Optional[str]:
    # Prefer wlan0 IPv4. Some devices use rmnet/mobile data, which is not useful for local adb connect.
    commands = [
        ["shell", "ip", "-f", "inet", "addr", "show", "wlan0"],
        ["shell", "ifconfig", "wlan0"],
    ]
    for cmd in commands:
        code, out, _ = adb(cmd, timeout=10, serial=serial)
        if code == 0 and out:
            match = re.search(r"inet(?: addr:)?\s*(\d+\.\d+\.\d+\.\d+)", out)
            if match and not match.group(1).startswith("127."):
                return match.group(1)
    return None


def enable_tcpip_and_connect_usb(serial: str) -> Tuple[bool, str, Optional[str]]:
    code, out, err = adb(["tcpip", str(DEFAULT_ADB_PORT)], timeout=20, serial=serial)
    if code != 0:
        return False, f"{serial}: could not enable adb tcpip: {err or out}", None
    time.sleep(2)
    ip = get_phone_ip(serial)
    if not ip:
        return False, f"{serial}: USB is authorized, but Wi-Fi IP was not found. Make sure phone is on Wi-Fi.", None
    target = f"{ip}:{DEFAULT_ADB_PORT}"
    code, out, err = adb(["connect", target], timeout=20)
    msg = out or err
    if code == 0 and ("connected" in msg.lower() or "already connected" in msg.lower()):
        return True, f"{serial}: wireless target connected as {target}", target
    return False, f"{serial}: adb connect {target} failed: {msg}", target


def reconnect_saved_targets(targets: List[str]) -> List[str]:
    notes = []
    for target in targets:
        code, out, err = adb(["connect", target], timeout=15)
        notes.append(f"{target}: {out or err or 'no output'}")
    return notes


def start_android_package(serial: str, package: str) -> str:
    package = package.strip()
    if not package:
        return "No Android app package selected. Skipped app start."
    # monkey starts launcher activity without needing activity name.
    code, out, err = adb(["shell", "monkey", "-p", package, "-c", "android.intent.category.LAUNCHER", "1"], timeout=15, serial=serial)
    if code == 0:
        return f"Started Android package on {serial}: {package}"
    return f"Could not start package {package} on {serial}: {err or out}"


def create_desktop_launcher(script_path: Path) -> Path:
    desktop = Path.home() / "Desktop"
    desktop.mkdir(exist_ok=True)
    launcher = desktop / "Engel Phone Auto Repair Verified.cmd"
    py = sys.executable or "python"
    launcher.write_text(f'@echo off\n"{py}" "{script_path}"\npause\n', encoding="utf-8")
    return launcher


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("900x620")
        self.q: queue.Queue[str] = queue.Queue()
        self.app_package = tk.StringVar(value="")

        top = tk.Frame(root)
        top.pack(fill="x", padx=10, pady=8)

        tk.Label(top, text="Optional Android app package to start after repair:").pack(side="left")
        tk.Entry(top, textvariable=self.app_package, width=42).pack(side="left", padx=6)
        tk.Button(top, text="Set Package", command=self.ask_package).pack(side="left", padx=4)

        buttons = tk.Frame(root)
        buttons.pack(fill="x", padx=10, pady=4)

        tk.Button(buttons, text="FULL AUTO REPAIR + VERIFY", height=2, command=self.full_auto).pack(side="left", padx=4)
        tk.Button(buttons, text="Check adb Devices", command=self.check_devices).pack(side="left", padx=4)
        tk.Button(buttons, text="Reconnect Saved", command=self.reconnect_saved).pack(side="left", padx=4)
        tk.Button(buttons, text="Create Desktop Launcher", command=self.make_launcher).pack(side="left", padx=4)
        tk.Button(buttons, text="Open Status Folder", command=self.open_status_folder).pack(side="left", padx=4)

        info = tk.Label(
            root,
            justify="left",
            text=(
                "If adb says connected but your app does not: this tool now verifies adb shell works, writes "
                "phone_bridge_status.json, and can start the Android app package.\n"
                "Status file: " + str(STATUS_FILE)
            ),
        )
        info.pack(fill="x", padx=10, pady=4)

        self.text = tk.Text(root, wrap="word")
        self.text.pack(fill="both", expand=True, padx=10, pady=8)
        self.log("Ready. Click FULL AUTO REPAIR + VERIFY.")
        self.root.after(100, self.drain_queue)

    def log(self, msg: str) -> None:
        self.text.insert("end", msg + "\n")
        self.text.see("end")
        log_line(msg)

    def post(self, msg: str) -> None:
        self.q.put(msg)

    def drain_queue(self) -> None:
        while True:
            try:
                self.log(self.q.get_nowait())
            except queue.Empty:
                break
        self.root.after(100, self.drain_queue)

    def run_thread(self, fn) -> None:
        threading.Thread(target=fn, daemon=True).start()

    def ask_package(self) -> None:
        val = simpledialog.askstring(
            "Android package",
            "Enter Android package name to launch, or leave blank.\nExample: com.example.app",
            initialvalue=self.app_package.get(),
        )
        if val is not None:
            self.app_package.set(val.strip())

    def check_devices(self) -> None:
        def work():
            try:
                devices = list_devices()
                if not devices:
                    self.post("No devices visible to adb.")
                for d in devices:
                    self.post(f"{d.serial} | {d.state} | {d.transport} | model={d.model}")
            except Exception as exc:
                self.post(f"ERROR: {exc}")
        self.run_thread(work)

    def reconnect_saved(self) -> None:
        def work():
            try:
                targets = load_saved_targets()
                if not targets:
                    self.post("No saved wireless targets yet.")
                    return
                for note in reconnect_saved_targets(targets):
                    self.post(note)
                self.post("Reconnect saved complete. Now checking devices...")
                for d in list_devices():
                    self.post(f"{d.serial} | {d.state} | {d.transport} | model={d.model}")
            except Exception as exc:
                self.post(f"ERROR: {exc}")
        self.run_thread(work)

    def full_auto(self) -> None:
        def work():
            notes: List[str] = []
            saved = load_saved_targets()
            try:
                self.post("Starting adb server repair...")
                adb(["kill-server"], timeout=10)
                adb(["start-server"], timeout=15)

                if saved:
                    self.post("Reconnecting saved wireless phones...")
                    for note in reconnect_saved_targets(saved):
                        notes.append(note)
                        self.post(note)

                devices = list_devices()
                if not devices:
                    notes.append("No adb devices found. Plug phone in by USB and accept the debugging prompt.")
                    self.post(notes[-1])

                # Fix unauthorized/offline messaging first.
                for d in devices:
                    if d.state == "unauthorized":
                        msg = f"{d.serial}: unauthorized. Unlock phone and tap Allow USB debugging. Then run again."
                        notes.append(msg)
                        self.post(msg)
                    elif d.state == "offline":
                        msg = f"{d.serial}: offline. Toggle USB/Wireless debugging or reconnect cable."
                        notes.append(msg)
                        self.post(msg)

                # For authorized USB devices, bootstrap wireless.
                new_targets = list(saved)
                for d in devices:
                    if d.state == "device" and d.transport == "usb":
                        self.post(f"USB authorized phone found: {d.serial}. Enabling wireless adb...")
                        ok, msg, target = enable_tcpip_and_connect_usb(d.serial)
                        notes.append(msg)
                        self.post(msg)
                        if ok and target and target not in new_targets:
                            new_targets.append(target)

                save_targets(new_targets)
                time.sleep(2)
                final_devices = list_devices()

                verified_count = 0
                for d in final_devices:
                    if d.state != "device":
                        continue
                    ok, msg = verify_device(d.serial)
                    notes.append(msg)
                    self.post(msg)
                    if ok:
                        verified_count += 1
                        pkg_note = start_android_package(d.serial, self.app_package.get())
                        notes.append(pkg_note)
                        self.post(pkg_note)

                ok = verified_count > 0
                status = BridgeStatus(
                    timestamp=time.time(),
                    ok=ok,
                    devices=final_devices,
                    saved_targets=new_targets,
                    selected_app_package=self.app_package.get().strip(),
                    notes=notes,
                )
                write_status(status)
                self.post(f"Wrote status: {STATUS_FILE}")
                if ok:
                    self.post("DONE: At least one phone is verified usable by adb shell. If Engel still does not see it, point Engel to the status JSON or set the Android package above.")
                else:
                    self.post("NOT DONE: adb can see something, but no phone passed shell verification.")
            except Exception as exc:
                notes.append(f"ERROR: {exc}")
                self.post(f"ERROR: {exc}")
                try:
                    write_status(BridgeStatus(time.time(), False, [], saved, self.app_package.get().strip(), notes))
                except Exception:
                    pass
        self.run_thread(work)

    def make_launcher(self) -> None:
        try:
            launcher = create_desktop_launcher(Path(__file__).resolve())
            messagebox.showinfo(APP_TITLE, f"Created launcher:\n{launcher}")
            self.log(f"Created launcher: {launcher}")
        except Exception as exc:
            messagebox.showerror(APP_TITLE, str(exc))

    def open_status_folder(self) -> None:
        try:
            if platform.system().lower().startswith("win"):
                os.startfile(str(STATE_DIR))  # type: ignore[attr-defined]
            elif platform.system().lower() == "darwin":
                subprocess.Popen(["open", str(STATE_DIR)])
            else:
                subprocess.Popen(["xdg-open", str(STATE_DIR)])
        except Exception as exc:
            self.log(f"Could not open folder: {exc}")


def main() -> None:
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
