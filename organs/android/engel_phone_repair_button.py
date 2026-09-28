#!/usr/bin/env python3
"""
Engel Phone Reconnect / Re-Pair Button

Purpose:
- Give a simple button GUI for reconnecting saved Android phones over ADB.
- Pair a new phone using Android Wireless Debugging pairing code.
- Create a desktop launcher .cmd file so you can double-click it later.

Requirements:
- Python 3 on Windows.
- Android platform-tools installed, with adb.exe available in PATH,
  OR place this script near platform-tools/adb.exe.

Phone setup:
1. On Android: Developer options -> Wireless debugging -> ON.
2. For first pairing: Wireless debugging -> Pair device with pairing code.
3. Enter the IP, pairing port, and pairing code in this tool.
4. For later reconnects: keep Wireless debugging on and use Reconnect Saved Phones.

Notes:
- Pairing port is usually temporary and shown beside the pairing code.
- Connect port is usually 5555, but some phones show another port under Wireless debugging.
- Saved phone records are stored in ~/.engel_phone_repair/phones.json.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from tkinter import Tk, StringVar, END, BOTH, LEFT, RIGHT, X, Y, Text, messagebox, simpledialog
from tkinter import ttk

APP_NAME = "Engel Phone Reconnect"
CONFIG_DIR = Path.home() / ".engel_phone_repair"
CONFIG_FILE = CONFIG_DIR / "phones.json"
DEFAULT_CONNECT_PORT = "5555"


@dataclass
class PhoneRecord:
    name: str
    ip: str
    connect_port: str = DEFAULT_CONNECT_PORT

    @property
    def address(self) -> str:
        return f"{self.ip}:{self.connect_port}"


def load_phones() -> list[PhoneRecord]:
    if not CONFIG_FILE.exists():
        return []
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        phones = []
        for item in data.get("phones", []):
            if item.get("ip"):
                phones.append(
                    PhoneRecord(
                        name=item.get("name") or item.get("ip"),
                        ip=item["ip"],
                        connect_port=str(item.get("connect_port") or DEFAULT_CONNECT_PORT),
                    )
                )
        return phones
    except Exception:
        return []


def save_phones(phones: list[PhoneRecord]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    data = {"phones": [asdict(phone) for phone in phones]}
    CONFIG_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def add_or_update_phone(new_phone: PhoneRecord) -> None:
    phones = load_phones()
    kept = [p for p in phones if not (p.ip == new_phone.ip and p.connect_port == new_phone.connect_port)]
    kept.append(new_phone)
    save_phones(kept)


def find_adb() -> str | None:
    # 1) Normal PATH lookup.
    found = shutil.which("adb") or shutil.which("adb.exe")
    if found:
        return found

    # 2) Common locations beside this script.
    script_dir = Path(__file__).resolve().parent
    candidates = [
        script_dir / "adb.exe",
        script_dir / "platform-tools" / "adb.exe",
        Path.cwd() / "adb.exe",
        Path.cwd() / "platform-tools" / "adb.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Android" / "Sdk" / "platform-tools" / "adb.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None


def run_adb(args: list[str], timeout: int = 25) -> tuple[int, str]:
    adb = find_adb()
    if not adb:
        return 127, (
            "adb was not found. Install Android platform-tools, then add adb.exe to PATH, "
            "or put this script next to platform-tools\\adb.exe."
        )

    try:
        proc = subprocess.run(
            [adb, *args],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            shell=False,
        )
        return proc.returncode, proc.stdout.strip()
    except subprocess.TimeoutExpired:
        return 124, "Command timed out. Check that the phone and computer are on the same network."
    except Exception as exc:
        return 1, f"Failed to run adb: {exc}"


def reconnect_saved_phones() -> str:
    phones = load_phones()
    lines: list[str] = []
    if not phones:
        return "No saved phones yet. Use Pair New Phone first."

    code, out = run_adb(["start-server"])
    lines.append(f"adb start-server -> {code}\n{out}".strip())

    for phone in phones:
        code, out = run_adb(["connect", phone.address])
        lines.append(f"\nReconnect {phone.name} ({phone.address}) -> {code}\n{out}".strip())

    code, out = run_adb(["devices", "-l"])
    lines.append(f"\nDevices now visible -> {code}\n{out}".strip())
    return "\n".join(lines)


def pair_phone(name: str, ip: str, pairing_port: str, pairing_code: str, connect_port: str) -> str:
    ip = ip.strip()
    pairing_port = pairing_port.strip()
    pairing_code = pairing_code.strip()
    connect_port = (connect_port or DEFAULT_CONNECT_PORT).strip()
    name = (name or ip).strip()

    if not ip or not pairing_port or not pairing_code:
        return "Missing IP, pairing port, or pairing code. Open Wireless debugging -> Pair device with pairing code."

    lines: list[str] = []
    code, out = run_adb(["start-server"])
    lines.append(f"adb start-server -> {code}\n{out}".strip())

    code, out = run_adb(["pair", f"{ip}:{pairing_port}", pairing_code], timeout=30)
    lines.append(f"\nPair {ip}:{pairing_port} -> {code}\n{out}".strip())

    # Even if pairing text is not perfectly consistent, try connect afterward.
    code2, out2 = run_adb(["connect", f"{ip}:{connect_port}"], timeout=30)
    lines.append(f"\nConnect {ip}:{connect_port} -> {code2}\n{out2}".strip())

    if code2 == 0 or "connected" in out2.lower() or "already connected" in out2.lower():
        add_or_update_phone(PhoneRecord(name=name, ip=ip, connect_port=connect_port))
        lines.append(f"\nSaved phone as: {name} ({ip}:{connect_port})")

    code3, out3 = run_adb(["devices", "-l"])
    lines.append(f"\nDevices now visible -> {code3}\n{out3}".strip())
    return "\n".join(lines)


def create_desktop_launcher() -> Path:
    desktop = Path.home() / "Desktop"
    desktop.mkdir(parents=True, exist_ok=True)
    script_path = Path(__file__).resolve()
    launcher = desktop / "Engel Phone Reconnect.cmd"

    # Use pythonw for GUI when available, otherwise python.
    py_exe = Path(sys.executable)
    pythonw = py_exe.with_name("pythonw.exe")
    exe = pythonw if pythonw.exists() else py_exe

    launcher.write_text(
        "@echo off\n"
        f'"{exe}" "{script_path}"\n'
        "exit /b %errorlevel%\n",
        encoding="utf-8",
    )
    return launcher


class PhoneRepairApp:
    def __init__(self) -> None:
        self.root = Tk()
        self.root.title(APP_NAME)
        self.root.geometry("780x560")

        self.status = StringVar(value="Ready. Make sure adb is installed and your phone has Wireless debugging turned on.")

        outer = ttk.Frame(self.root, padding=12)
        outer.pack(fill=BOTH, expand=True)

        title = ttk.Label(outer, text="Engel Phone Reconnect / Re-Pair", font=("Segoe UI", 16, "bold"))
        title.pack(anchor="w")

        hint = ttk.Label(
            outer,
            text=(
                "Use Reconnect for saved phones. Use Pair New Phone when Android shows a new pairing code. "
                "Both devices must be on the same Wi-Fi/network."
            ),
            wraplength=730,
        )
        hint.pack(anchor="w", pady=(4, 10))

        button_row = ttk.Frame(outer)
        button_row.pack(fill=X, pady=(0, 10))

        ttk.Button(button_row, text="Reconnect Saved Phones", command=self.on_reconnect).pack(side=LEFT, padx=(0, 8))
        ttk.Button(button_row, text="Pair New Phone", command=self.on_pair).pack(side=LEFT, padx=(0, 8))
        ttk.Button(button_row, text="Show Saved Phones", command=self.on_show_saved).pack(side=LEFT, padx=(0, 8))
        ttk.Button(button_row, text="Create Desktop Launcher", command=self.on_create_launcher).pack(side=LEFT, padx=(0, 8))
        ttk.Button(button_row, text="Check adb Devices", command=self.on_devices).pack(side=LEFT)

        self.output = Text(outer, height=24, wrap="word")
        self.output.pack(fill=BOTH, expand=True)

        bottom = ttk.Frame(outer)
        bottom.pack(fill=X, pady=(8, 0))
        ttk.Label(bottom, textvariable=self.status, wraplength=680).pack(side=LEFT, fill=X, expand=True)
        ttk.Button(bottom, text="Clear", command=self.clear).pack(side=RIGHT)

        self.log("Ready.\n\nFirst-time pair steps:\n1. Phone: Developer options -> Wireless debugging -> Pair device with pairing code.\n2. Click Pair New Phone.\n3. Enter IP, pairing port, pairing code, and connect port.\n")

    def log(self, text: str) -> None:
        self.output.insert(END, text + "\n")
        self.output.see(END)
        self.status.set("Done.")

    def clear(self) -> None:
        self.output.delete("1.0", END)
        self.status.set("Cleared.")

    def on_reconnect(self) -> None:
        self.status.set("Reconnecting saved phones...")
        self.log(reconnect_saved_phones())

    def on_devices(self) -> None:
        self.status.set("Checking adb devices...")
        code, out = run_adb(["devices", "-l"])
        self.log(f"adb devices -l -> {code}\n{out}")

    def on_show_saved(self) -> None:
        phones = load_phones()
        if not phones:
            self.log("No saved phones yet.")
            return
        self.log("Saved phones:\n" + "\n".join(f"- {p.name}: {p.address}" for p in phones))

    def on_create_launcher(self) -> None:
        try:
            launcher = create_desktop_launcher()
            self.log(f"Created desktop launcher:\n{launcher}")
            messagebox.showinfo(APP_NAME, f"Created desktop launcher:\n{launcher}")
        except Exception as exc:
            self.log(f"Could not create desktop launcher: {exc}")
            messagebox.showerror(APP_NAME, f"Could not create desktop launcher:\n{exc}")

    def on_pair(self) -> None:
        name = simpledialog.askstring(APP_NAME, "Phone name, example: Pixel Main", parent=self.root) or "Android Phone"
        ip = simpledialog.askstring(APP_NAME, "Phone IP address, example: 192.168.1.25", parent=self.root)
        if not ip:
            self.log("Pair cancelled: no IP entered.")
            return
        pairing_port = simpledialog.askstring(APP_NAME, "Pairing port shown with pairing code, example: 37123", parent=self.root)
        if not pairing_port:
            self.log("Pair cancelled: no pairing port entered.")
            return
        pairing_code = simpledialog.askstring(APP_NAME, "Pairing code shown on phone", parent=self.root)
        if not pairing_code:
            self.log("Pair cancelled: no pairing code entered.")
            return
        connect_port = simpledialog.askstring(
            APP_NAME,
            "Connect port. Usually 5555, or use the port shown under Wireless debugging.",
            initialvalue=DEFAULT_CONNECT_PORT,
            parent=self.root,
        ) or DEFAULT_CONNECT_PORT

        self.status.set("Pairing phone...")
        self.log(pair_phone(name, ip, pairing_port, pairing_code, connect_port))

    def run(self) -> None:
        self.root.mainloop()


def main() -> int:
    parser = argparse.ArgumentParser(description="Engel Phone Reconnect / Re-Pair Button")
    parser.add_argument("--reconnect", action="store_true", help="Reconnect all saved phones and print output.")
    parser.add_argument("--devices", action="store_true", help="Show adb devices and print output.")
    parser.add_argument("--create-launcher", action="store_true", help="Create a desktop launcher and print its path.")
    args = parser.parse_args()

    if args.reconnect:
        print(reconnect_saved_phones())
        return 0
    if args.devices:
        code, out = run_adb(["devices", "-l"])
        print(out)
        return code
    if args.create_launcher:
        print(create_desktop_launcher())
        return 0

    app = PhoneRepairApp()
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
