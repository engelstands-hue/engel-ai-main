#!/usr/bin/env python3
"""
Engel Phone Auto Repair
Windows-friendly one-button Android reconnect / re-pair helper.

What can be fully automated:
- Restart adb cleanly.
- Reconnect previously saved wireless phones.
- Detect USB-attached authorized phones.
- Switch USB phones into adb-over-Wi-Fi mode with `adb tcpip 5555`.
- Discover their Wi-Fi IP from the phone and connect automatically.
- Save successful wireless records for future one-click reconnect.
- Create a desktop launcher.

Android security limit:
- A brand-new Wireless Debugging pairing from an untrusted computer cannot be
  completed without the pairing code shown on the phone. This script automates
  every command around that, but Android still requires the user-visible code.

Recommended fully automated path:
1. Plug phone in by USB once and accept the USB debugging prompt on the phone.
2. Click "FULL AUTO REPAIR".
3. Future reconnects should work without USB using saved IP:port records.
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
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable, Optional

try:
    import tkinter as tk
    from tkinter import messagebox, simpledialog
except Exception as exc:  # pragma: no cover
    print("Tkinter is required for the GUI:", exc)
    sys.exit(1)

APP_NAME = "Engel Phone Auto Repair"
DEFAULT_CONNECT_PORT = 5555


def default_state_dir() -> Path:
    """Prefer D: Engel workspace so Engel-owned state does not live on C:."""
    if platform.system().lower().startswith("win"):
        preferred = Path(r"D:\b.WorkSpace\Engel App\memory\phone_repair")
        try:
            preferred.mkdir(parents=True, exist_ok=True)
            return preferred
        except Exception:
            pass
    fallback = Path(__file__).resolve().parent / "phone_repair_state"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


STATE_DIR = default_state_dir()
PHONES_FILE = STATE_DIR / "saved_phones.json"
LOG_FILE = STATE_DIR / "phone_auto_repair.log"


@dataclass
class PhoneRecord:
    name: str
    ip: str
    port: int = DEFAULT_CONNECT_PORT
    serial_hint: str = ""

    @property
    def target(self) -> str:
        return f"{self.ip}:{self.port}"


def append_log(text: str) -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(text.rstrip() + "\n")


def find_adb() -> Optional[str]:
    """Find adb.exe/adb without requiring PATH if platform-tools is nearby."""
    candidates: list[Path] = []
    here = Path(__file__).resolve().parent
    exe = "adb.exe" if platform.system().lower().startswith("win") else "adb"

    path_hit = shutil.which("adb")
    if path_hit:
        return path_hit

    candidates.extend([
        here / exe,
        here / "platform-tools" / exe,
        Path.cwd() / exe,
        Path.cwd() / "platform-tools" / exe,
    ])

    if platform.system().lower().startswith("win"):
        local = os.environ.get("LOCALAPPDATA", "")
        program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
        candidates.extend([
            Path(local) / "Android" / "Sdk" / "platform-tools" / "adb.exe",
            Path(program_files) / "Android" / "android-sdk" / "platform-tools" / "adb.exe",
            Path(r"D:\platform-tools\adb.exe"),
            Path(r"D:\Android\platform-tools\adb.exe"),
            Path(r"D:\b.WorkSpace\platform-tools\adb.exe"),
        ])

    for c in candidates:
        if c.exists():
            return str(c)
    return None


def run_cmd(args: list[str], timeout: int = 25) -> tuple[int, str]:
    adb = find_adb()
    if not adb:
        return 127, "adb was not found. Install Android platform-tools or put adb beside this script."

    cmd = [adb] + args
    try:
        completed = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW if platform.system().lower().startswith("win") else 0,
        )
        out = completed.stdout.strip()
        append_log(f"$ {' '.join(cmd)}\n{out}\nexit={completed.returncode}\n")
        return completed.returncode, out
    except subprocess.TimeoutExpired:
        msg = f"Timed out running: {' '.join(cmd)}"
        append_log(msg)
        return 124, msg
    except Exception as exc:
        msg = f"Failed running {' '.join(cmd)}: {exc}"
        append_log(msg)
        return 1, msg


def load_records() -> list[PhoneRecord]:
    if not PHONES_FILE.exists():
        return []
    try:
        raw = json.loads(PHONES_FILE.read_text(encoding="utf-8"))
        return [PhoneRecord(**item) for item in raw if item.get("ip")]
    except Exception:
        return []


def save_records(records: Iterable[PhoneRecord]) -> None:
    unique: dict[str, PhoneRecord] = {}
    for r in records:
        if r.ip:
            unique[r.target] = r
    PHONES_FILE.parent.mkdir(parents=True, exist_ok=True)
    PHONES_FILE.write_text(json.dumps([asdict(r) for r in unique.values()], indent=2), encoding="utf-8")


def parse_devices(output: str) -> list[tuple[str, str]]:
    devices: list[tuple[str, str]] = []
    for line in output.splitlines():
        line = line.strip()
        if not line or line.startswith("List of devices"):
            continue
        parts = line.split()
        if len(parts) >= 2:
            devices.append((parts[0], parts[1]))
    return devices


def adb_devices() -> list[tuple[str, str]]:
    _, out = run_cmd(["devices", "-l"])
    return parse_devices(out)


def is_ip_serial(serial: str) -> bool:
    return bool(re.match(r"^\d{1,3}(?:\.\d{1,3}){3}:\d+$", serial))


def shell(serial: str, command: str, timeout: int = 20) -> tuple[int, str]:
    return run_cmd(["-s", serial, "shell", command], timeout=timeout)


def get_phone_ip(serial: str) -> Optional[str]:
    """Ask an authorized USB phone for its Wi-Fi IP."""
    commands = [
        "ip -f inet addr show wlan0",
        "ip addr show wlan0",
        "ifconfig wlan0",
    ]
    for command in commands:
        code, out = shell(serial, command)
        if code == 0 and out:
            match = re.search(r"inet\s+(\d+\.\d+\.\d+\.\d+)", out)
            if match and not match.group(1).startswith("127."):
                return match.group(1)
            match = re.search(r"addr:(\d+\.\d+\.\d+\.\d+)", out)
            if match and not match.group(1).startswith("127."):
                return match.group(1)
    return None


def start_clean_adb() -> str:
    lines = []
    for args in (["kill-server"], ["start-server"]):
        _, out = run_cmd(args)
        lines.append(out)
    return "\n".join(x for x in lines if x)


def reconnect_saved() -> str:
    records = load_records()
    if not records:
        return "No saved wireless phones yet."

    lines = ["Reconnect saved phones:"]
    for r in records:
        code, out = run_cmd(["connect", r.target], timeout=15)
        status = "OK" if code == 0 and ("connected" in out.lower() or "already" in out.lower()) else "CHECK"
        lines.append(f"- {r.name} {r.target}: {status} - {out}")
    return "\n".join(lines)


def usb_bootstrap() -> str:
    """Fully automate wireless adb setup for authorized USB phones."""
    devices = adb_devices()
    usb_devices = [(s, st) for s, st in devices if not is_ip_serial(s)]
    if not usb_devices:
        return "No USB-attached phones detected. Plug in USB and accept the debugging prompt for full automation."

    records = load_records()
    lines = ["USB bootstrap:"]

    for serial, status in usb_devices:
        if status != "device":
            lines.append(f"- {serial}: not authorized yet ({status}). Accept USB debugging on the phone, then run again.")
            continue

        ip = get_phone_ip(serial)
        if not ip:
            lines.append(f"- {serial}: could not read Wi-Fi IP. Make sure phone Wi-Fi is on.")
            continue

        code, tcpip_out = run_cmd(["-s", serial, "tcpip", str(DEFAULT_CONNECT_PORT)], timeout=20)
        if code != 0:
            lines.append(f"- {serial}: failed adb tcpip: {tcpip_out}")
            continue

        target = f"{ip}:{DEFAULT_CONNECT_PORT}"
        code, connect_out = run_cmd(["connect", target], timeout=20)
        ok = code == 0 and ("connected" in connect_out.lower() or "already" in connect_out.lower())
        if ok:
            existing_targets = {r.target for r in records}
            if target not in existing_targets:
                records.append(PhoneRecord(name=f"Phone {ip}", ip=ip, port=DEFAULT_CONNECT_PORT, serial_hint=serial))
                save_records(records)
            lines.append(f"- {serial} -> {target}: connected and saved.")
        else:
            lines.append(f"- {serial} -> {target}: connect check needed: {connect_out}")

    return "\n".join(lines)


def manual_wireless_pair(parent: tk.Tk, log: tk.Text) -> None:
    """Guided fallback for Android Wireless Debugging pairing code."""
    ip = simpledialog.askstring("Phone IP", "Phone IP address shown in Wireless debugging:", parent=parent)
    if not ip:
        return
    pair_port = simpledialog.askinteger("Pairing Port", "Pairing port shown under Pair device with pairing code:", parent=parent)
    if not pair_port:
        return
    code = simpledialog.askstring("Pairing Code", "6-digit pairing code shown on the phone:", parent=parent)
    if not code:
        return
    connect_port = simpledialog.askinteger("Connect Port", "Wireless debugging main connect port:", initialvalue=DEFAULT_CONNECT_PORT, parent=parent)
    if not connect_port:
        connect_port = DEFAULT_CONNECT_PORT

    add_log(log, f"Pairing {ip}:{pair_port} ...")
    pair_code, pair_out = run_cmd(["pair", f"{ip}:{pair_port}", code], timeout=25)
    add_log(log, pair_out)
    if pair_code != 0 and "success" not in pair_out.lower():
        add_log(log, "Pairing did not report success. Check the code and pairing port.")
        return

    target = f"{ip}:{connect_port}"
    code2, out2 = run_cmd(["connect", target], timeout=20)
    add_log(log, out2)
    if code2 == 0 and ("connected" in out2.lower() or "already" in out2.lower()):
        records = load_records()
        records.append(PhoneRecord(name=f"Phone {ip}", ip=ip, port=int(connect_port)))
        save_records(records)
        add_log(log, f"Saved {target} for future one-click reconnect.")


def add_log(widget: tk.Text, text: str) -> None:
    widget.configure(state="normal")
    widget.insert("end", text.rstrip() + "\n")
    widget.see("end")
    widget.configure(state="disabled")
    append_log(text)


def run_threaded(button: tk.Button, log: tk.Text, func) -> None:
    def worker() -> None:
        try:
            button.configure(state="disabled")
            result = func()
            log.after(0, lambda: add_log(log, result))
            log.after(0, lambda: add_log(log, "Done."))
        finally:
            log.after(0, lambda: button.configure(state="normal"))

    threading.Thread(target=worker, daemon=True).start()


def full_auto_repair() -> str:
    parts = [
        f"State folder: {STATE_DIR}",
        start_clean_adb(),
        reconnect_saved(),
        usb_bootstrap(),
        "Current adb devices:",
        run_cmd(["devices", "-l"])[1],
    ]
    return "\n\n".join(p for p in parts if p)


def create_desktop_launcher() -> str:
    if not platform.system().lower().startswith("win"):
        return "Desktop launcher creation is Windows-only in this script."

    desktop = Path.home() / "Desktop"
    if not desktop.exists():
        desktop = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Desktop"
    target = desktop / "Engel Phone Auto Repair.cmd"
    script = Path(__file__).resolve()
    content = f'''@echo off
setlocal
cd /d "{script.parent}"
py -3 "{script}" || python "{script}"
pause
'''
    target.write_text(content, encoding="utf-8")
    return f"Created desktop launcher: {target}"


def show_saved() -> str:
    records = load_records()
    if not records:
        return f"No saved phones. State folder: {STATE_DIR}"
    return "Saved phones:\n" + "\n".join(f"- {r.name}: {r.target}" for r in records)


def forget_saved() -> str:
    save_records([])
    return "Cleared saved phone records."


def open_state_folder() -> str:
    try:
        if platform.system().lower().startswith("win"):
            os.startfile(str(STATE_DIR))  # type: ignore[attr-defined]
            return f"Opened {STATE_DIR}"
        return f"State folder: {STATE_DIR}"
    except Exception as exc:
        return f"Could not open folder: {exc}\nState folder: {STATE_DIR}"


def build_gui() -> tk.Tk:
    root = tk.Tk()
    root.title(APP_NAME)
    root.geometry("820x620")

    title = tk.Label(root, text="Engel Phone Auto Repair", font=("Segoe UI", 18, "bold"))
    title.pack(pady=(12, 4))

    note = tk.Label(
        root,
        text=(
            "FULL AUTO REPAIR reconnects saved phones and bootstraps authorized USB phones into Wi-Fi adb. "
            "Brand-new wireless pairing still needs the Android pairing code shown on the phone."
        ),
        wraplength=760,
        justify="center",
    )
    note.pack(pady=(0, 10))

    button_frame = tk.Frame(root)
    button_frame.pack(pady=4)

    log = tk.Text(root, height=24, width=100, state="disabled")
    log.pack(fill="both", expand=True, padx=12, pady=10)

    full_btn = tk.Button(button_frame, text="FULL AUTO REPAIR", width=24, height=2)
    full_btn.grid(row=0, column=0, padx=5, pady=5)
    full_btn.configure(command=lambda: run_threaded(full_btn, log, full_auto_repair))

    reconnect_btn = tk.Button(button_frame, text="Reconnect Saved", width=18)
    reconnect_btn.grid(row=0, column=1, padx=5, pady=5)
    reconnect_btn.configure(command=lambda: run_threaded(reconnect_btn, log, reconnect_saved))

    usb_btn = tk.Button(button_frame, text="USB Auto Bootstrap", width=18)
    usb_btn.grid(row=0, column=2, padx=5, pady=5)
    usb_btn.configure(command=lambda: run_threaded(usb_btn, log, usb_bootstrap))

    pair_btn = tk.Button(button_frame, text="Guided Pair Fallback", width=18)
    pair_btn.grid(row=0, column=3, padx=5, pady=5)
    pair_btn.configure(command=lambda: manual_wireless_pair(root, log))

    devices_btn = tk.Button(button_frame, text="Check Devices", width=18)
    devices_btn.grid(row=1, column=0, padx=5, pady=5)
    devices_btn.configure(command=lambda: run_threaded(devices_btn, log, lambda: run_cmd(["devices", "-l"])[1]))

    saved_btn = tk.Button(button_frame, text="Show Saved", width=18)
    saved_btn.grid(row=1, column=1, padx=5, pady=5)
    saved_btn.configure(command=lambda: add_log(log, show_saved()))

    launcher_btn = tk.Button(button_frame, text="Create Desktop Link", width=18)
    launcher_btn.grid(row=1, column=2, padx=5, pady=5)
    launcher_btn.configure(command=lambda: add_log(log, create_desktop_launcher()))

    folder_btn = tk.Button(button_frame, text="Open State Folder", width=18)
    folder_btn.grid(row=1, column=3, padx=5, pady=5)
    folder_btn.configure(command=lambda: add_log(log, open_state_folder()))

    clear_btn = tk.Button(button_frame, text="Forget Saved Phones", width=18)
    clear_btn.grid(row=2, column=0, padx=5, pady=5)
    clear_btn.configure(command=lambda: add_log(log, forget_saved()))

    add_log(log, f"Ready. State folder: {STATE_DIR}")
    add_log(log, "Best full-auto path: connect phone by USB once, accept USB debugging, click FULL AUTO REPAIR.")
    return root


def cli(argv: list[str]) -> int:
    if "--auto" in argv:
        print(full_auto_repair())
        return 0
    if "--launcher" in argv:
        print(create_desktop_launcher())
        return 0
    if "--saved" in argv:
        print(show_saved())
        return 0
    if "--reconnect" in argv:
        print(start_clean_adb())
        print(reconnect_saved())
        return 0
    return 2


def main() -> None:
    if len(sys.argv) > 1:
        raise SystemExit(cli(sys.argv[1:]))
    root = build_gui()
    root.mainloop()


if __name__ == "__main__":
    main()
