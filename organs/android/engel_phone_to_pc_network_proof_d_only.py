#!/usr/bin/env python3
"""
Engel Phone-to-PC Network Proof - D-only

Purpose:
- Prove whether each Android phone can reach this PC on port 8765.
- This does NOT depend on the Engel Remote Worker app.
- If this passes, the app itself is not attempting connection/pairing.
- If this fails, fix Windows Firewall / network / IP first.

Run:
  D:
  cd "D:\\b.WorkSpace\\Engel App"
  python engel_phone_to_pc_network_proof_d_only.py

Writes only under:
  D:\\b.WorkSpace\\Engel App\\memory\\phone_bridge\\
  D:\\b.WorkSpace\\Engel App\\reports\\codex_bridge\\
"""

from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

ENGEL_ROOT = Path(r"D:\b.WorkSpace\Engel App")
BRIDGE_DIR = ENGEL_ROOT / "memory" / "phone_bridge"
REPORT_DIR = ENGEL_ROOT / "reports" / "codex_bridge"

PORT = 8765
STATE_FILE = BRIDGE_DIR / "ENGEL_PHONE_TO_PC_NETWORK_PROOF.json"
REPORT_FILE = REPORT_DIR / "ENGEL_PHONE_TO_PC_NETWORK_PROOF.md"
LOG_FILE = BRIDGE_DIR / "engel_phone_to_pc_network_proof.log"

ADB_CANDIDATES = [
    ENGEL_ROOT / "tools" / "platform-tools" / "adb.exe",
    Path(r"D:\platform-tools\adb.exe"),
    ENGEL_ROOT / "platform-tools" / "adb.exe",
    Path.cwd() / "tools" / "platform-tools" / "adb.exe",
    Path.cwd() / "platform-tools" / "adb.exe",
    Path.cwd() / "adb.exe",
]

CAPTURES: list[dict[str, Any]] = []
STOP = False


def assert_d_only(path: Path) -> None:
    if not str(path).lower().startswith("d:\\"):
        raise RuntimeError(f"Blocked non-D path: {path}")


def ensure_dirs() -> None:
    for path in [ENGEL_ROOT, BRIDGE_DIR, REPORT_DIR]:
        assert_d_only(path)
        path.mkdir(parents=True, exist_ok=True)


def log(msg: str) -> None:
    ensure_dirs()
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def find_adb() -> str | None:
    for p in ADB_CANDIDATES:
        if p.exists() and not str(p).lower().startswith("c:\\"):
            return str(p)

    try:
        r = subprocess.run(["where", "adb"], capture_output=True, text=True, timeout=5)
        if r.returncode == 0:
            for line in r.stdout.splitlines():
                line = line.strip()
                if line and not line.lower().startswith("c:\\"):
                    return line
    except Exception:
        pass
    return None


def run(cmd: list[str], timeout: int = 30) -> tuple[int, str, str]:
    log("RUN: " + " ".join(cmd))
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        out = p.stdout.strip()
        err = p.stderr.strip()
        if out:
            log("STDOUT: " + out[:2500])
        if err:
            log("STDERR: " + err[:2500])
        return p.returncode, out, err
    except subprocess.TimeoutExpired:
        return 998, "", f"Timed out after {timeout}s"
    except Exception as exc:
        return 997, "", str(exc)


def adb(adb_path: str, *args: str, timeout: int = 30) -> tuple[int, str, str]:
    return run([adb_path, *args], timeout=timeout)


def adb_s(adb_path: str, serial: str, *args: str, timeout: int = 30) -> tuple[int, str, str]:
    return adb(adb_path, "-s", serial, *args, timeout=timeout)


def parse_devices(adb_path: str) -> list[dict[str, Any]]:
    code, out, _ = adb(adb_path, "devices", "-l", timeout=15)
    devices = []
    if code != 0:
        return devices
    for line in out.splitlines():
        line = line.strip()
        if not line or line.startswith("List of devices"):
            continue
        parts = line.split()
        if len(parts) >= 2:
            serial = parts[0]
            devices.append({
                "serial": serial,
                "state": parts[1],
                "is_wifi": bool(re.match(r"^\d+\.\d+\.\d+\.\d+:\d+$", serial)),
                "detail": " ".join(parts[2:]),
            })
    return devices


def shell(adb_path: str, serial: str, *args: str, timeout: int = 20) -> str:
    code, out, _ = adb_s(adb_path, serial, "shell", *args, timeout=timeout)
    return out.strip() if code == 0 else ""


def enrich(adb_path: str, dev: dict[str, Any]) -> dict[str, Any]:
    out = dict(dev)
    if dev["state"] != "device":
        out["usable"] = False
        return out
    serial = dev["serial"]
    out["usable"] = True
    out["model"] = shell(adb_path, serial, "getprop", "ro.product.model")
    out["android_id"] = shell(adb_path, serial, "settings", "get", "secure", "android_id")
    return out


def canonicalize(devices: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for d in devices:
        groups.setdefault(d.get("android_id") or d["serial"], []).append(d)
    result = []
    for _, group in groups.items():
        usable = [x for x in group if x.get("usable")]
        wifi = [x for x in usable if x.get("is_wifi")]
        chosen = wifi[0] if wifi else (usable[0] if usable else group[0])
        chosen = dict(chosen)
        chosen["duplicate_transports"] = [{"serial": x["serial"], "is_wifi": x.get("is_wifi")} for x in group]
        result.append(chosen)
    return result


def get_desktop_ips() -> list[str]:
    ips = set()
    for host in ["192.0.2.1", "8.8.8.8", "1.1.1.1"]:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect((host, 80))
            ip = s.getsockname()[0]
            if ip and not ip.startswith("127."):
                ips.add(ip)
        except Exception:
            pass
        finally:
            s.close()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if ip and not ip.startswith("127."):
                ips.add(ip)
    except Exception:
        pass
    return sorted(ips)


def choose_ip() -> str:
    ips = get_desktop_ips()
    for ip in ips:
        if ip.startswith("192.0.2."):
            return ip
    return ips[0] if ips else "0.0.0.0"


def server(port: int) -> None:
    global STOP
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", port))
    srv.listen(20)
    srv.settimeout(1)
    log(f"NETWORK PROOF SERVER LISTENING on 0.0.0.0:{port}")

    while not STOP:
        try:
            conn, addr = srv.accept()
            log(f"PHONE REACHED PC from {addr[0]}:{addr[1]}")
            try:
                conn.settimeout(2)
                data = conn.recv(2048)
            except Exception:
                data = b""
            try:
                conn.sendall(b"ENGEL_PC_REACHED\n")
            except Exception:
                pass
            CAPTURES.append({
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "remote_ip": addr[0],
                "remote_port": addr[1],
                "data_hex": data.hex(),
                "data_text": data.decode("utf-8", errors="replace"),
            })
            try:
                conn.close()
            except Exception:
                pass
        except socket.timeout:
            continue
        except Exception as exc:
            log(f"server error: {exc}")
            break

    try:
        srv.close()
    except Exception:
        pass


def phone_connect_tests(adb_path: str, serial: str, desktop_ip: str) -> list[dict[str, Any]]:
    tests = []

    commands = [
        ["toybox", "nc", "-w", "3", desktop_ip, str(PORT)],
        ["nc", "-w", "3", desktop_ip, str(PORT)],
        ["sh", "-c", f"echo ENGEL_FROM_PHONE | toybox nc -w 3 {desktop_ip} {PORT}"],
        ["sh", "-c", f"echo ENGEL_FROM_PHONE | nc -w 3 {desktop_ip} {PORT}"],
    ]

    for cmd in commands:
        code, out, err = adb_s(adb_path, serial, "shell", *cmd, timeout=8)
        tests.append({
            "cmd": " ".join(cmd),
            "returncode": code,
            "stdout": out[-1000:],
            "stderr": err[-1000:],
        })
        time.sleep(1)
        if CAPTURES:
            break

    return tests


def make_report(state: dict[str, Any]) -> str:
    lines = [
        "# Engel Phone-to-PC Network Proof",
        "",
        f"- Time: `{state.get('timestamp')}`",
        f"- Desktop IP: `{state.get('desktop_ip')}`",
        f"- Port: `{state.get('port')}`",
        f"- Overall: `{state.get('overall')}`",
        "",
        "## Meaning",
        "",
    ]

    if state.get("overall") == "PHONE_CAN_REACH_PC":
        lines.append("The phones can reach the PC on the pairing port. Windows network/firewall is not the main blocker. The Android app is not attempting the connection, or its pairing code path is not active.")
    else:
        lines.append("The phones did not reach the PC on the pairing port. Fix Windows Firewall, network profile, router/client isolation, or desktop IP before changing the app.")

    lines += ["", "## Devices", ""]
    for dev in state.get("devices", []):
        lines += [
            f"### {dev.get('model')} / {dev.get('serial')}",
            "",
            f"- Android ID: `{dev.get('android_id')}`",
            f"- Tests:",
        ]
        for t in dev.get("connect_tests", []):
            lines.append(f"  - `{t.get('cmd')}` rc=`{t.get('returncode')}` stdout=`{t.get('stdout')}` stderr=`{t.get('stderr')}`")
        lines.append("")

    lines += ["## Captures", "", "```json", json.dumps(state.get("captures", []), indent=2), "```", ""]
    return "\n".join(lines)


def main() -> None:
    global STOP

    ensure_dirs()
    log("Starting phone-to-PC network proof.")

    adb_path = find_adb()
    if not adb_path:
        log("ADB not found.")
        return

    desktop_ip = choose_ip()
    adb(adb_path, "start-server", timeout=15)

    raw = parse_devices(adb_path)
    enriched = [enrich(adb_path, d) for d in raw]
    canonical = canonicalize(enriched)

    t = threading.Thread(target=server, args=(PORT,), daemon=True)
    t.start()
    time.sleep(1)

    for dev in canonical:
        if not dev.get("usable"):
            continue
        dev["connect_tests"] = phone_connect_tests(adb_path, dev["serial"], desktop_ip)

    time.sleep(2)
    STOP = True
    time.sleep(1)

    overall = "PHONE_CAN_REACH_PC" if CAPTURES else "PHONE_CANNOT_REACH_PC"

    state = {
        "overall": overall,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "desktop_ip": desktop_ip,
        "all_desktop_ips": get_desktop_ips(),
        "port": PORT,
        "devices": canonical,
        "captures": CAPTURES,
        "notes": [
            "No C: writes.",
            "This test does not depend on the Engel Android app.",
            "If this passes but the app sniffer had no captures, the app is not initiating network pairing.",
        ],
    }

    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    REPORT_FILE.write_text(make_report(state), encoding="utf-8")

    log(f"Wrote state: {STATE_FILE}")
    log(f"Wrote report: {REPORT_FILE}")
    log(f"Finished. Overall: {overall}")

    print("")
    print("DONE")
    print(f"Overall: {overall}")
    print(f"Desktop IP: {desktop_ip}")
    print(f"Report: {REPORT_FILE}")
    print(f"State:  {STATE_FILE}")


if __name__ == "__main__":
    main()
