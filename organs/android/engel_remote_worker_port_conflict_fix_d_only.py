#!/usr/bin/env python3
"""
Engel Remote Worker Port Conflict Fix - D-only

Why this exists:
- Your phone-to-PC proof showed HTTP/1.1 400 responses from 192.0.2.40:8765.
- That means the phones can reach the PC, but port 8765 is already answered by another service/proxy.
- The earlier proof/sniffer did not receive captures because it was not the service actually answering the phones.

What this script does:
1. Uses only D:\b.WorkSpace\Engel App paths.
2. Targets only com.example.engel_remote_worker.
3. Avoids com.engel.engel_monitor.
4. Checks who owns/listens on port 8765.
5. Chooses a free replacement port, default 8766.
6. Correctly updates worker_connection.json on both phones using run-as.
7. Starts a raw capture server on the replacement port.
8. Force-stops and launches the worker app.
9. Captures whether the app connects to the replacement port.

Run:
  D:
  cd "D:\\b.WorkSpace\\Engel App"
  python engel_remote_worker_port_conflict_fix_d_only.py
"""

from __future__ import annotations

import base64
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

TARGET_PACKAGE = "com.example.engel_remote_worker"
TARGET_ACTIVITY = "com.example.engel_remote_worker/.MainActivity"

OLD_PORT = 8765
PREFERRED_NEW_PORT = 8766

STATE_FILE = BRIDGE_DIR / "ENGEL_REMOTE_WORKER_PORT_CONFLICT_FIX_STATE.json"
CAPTURE_FILE = BRIDGE_DIR / "ENGEL_REMOTE_WORKER_PORT_CONFLICT_FIX_CAPTURE.json"
REPORT_FILE = REPORT_DIR / "ENGEL_REMOTE_WORKER_PORT_CONFLICT_FIX_REPORT.md"
LOG_FILE = BRIDGE_DIR / "engel_remote_worker_port_conflict_fix.log"

ADB_CANDIDATES = [
    ENGEL_ROOT / "tools" / "platform-tools" / "adb.exe",
    Path(r"D:\platform-tools\adb.exe"),
    ENGEL_ROOT / "platform-tools" / "adb.exe",
    Path.cwd() / "tools" / "platform-tools" / "adb.exe",
    Path.cwd() / "platform-tools" / "adb.exe",
    Path.cwd() / "adb.exe",
]

CAPTURES: list[dict[str, Any]] = []
STOP_SERVER = False


def assert_d_only(path: Path) -> None:
    if not str(path).lower().startswith("d:\\"):
        raise RuntimeError(f"Blocked non-D path: {path}")


def ensure_dirs() -> None:
    for p in [ENGEL_ROOT, BRIDGE_DIR, REPORT_DIR]:
        assert_d_only(p)
        p.mkdir(parents=True, exist_ok=True)


def log(msg: str) -> None:
    ensure_dirs()
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def run(cmd: list[str], timeout: int = 30) -> tuple[int, str, str]:
    log("RUN: " + " ".join(cmd))
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        out = p.stdout.strip()
        err = p.stderr.strip()
        if out:
            log("STDOUT: " + out[:3000])
        if err:
            log("STDERR: " + err[:3000])
        return p.returncode, out, err
    except subprocess.TimeoutExpired:
        return 998, "", f"Timed out after {timeout}s"
    except Exception as e:
        return 997, "", str(e)


def find_adb() -> str | None:
    for p in ADB_CANDIDATES:
        if p.exists() and not str(p).lower().startswith("c:\\"):
            return str(p)

    try:
        code, out, _ = run(["where", "adb"], timeout=5)
        if code == 0:
            for line in out.splitlines():
                line = line.strip()
                if line and not line.lower().startswith("c:\\"):
                    return line
    except Exception:
        pass

    return None


def adb(adb_path: str, *args: str, timeout: int = 30) -> tuple[int, str, str]:
    return run([adb_path, *args], timeout=timeout)


def adb_s(adb_path: str, serial: str, *args: str, timeout: int = 30) -> tuple[int, str, str]:
    return adb(adb_path, "-s", serial, *args, timeout=timeout)


def shell(adb_path: str, serial: str, *args: str, timeout: int = 20) -> str:
    code, out, _ = adb_s(adb_path, serial, "shell", *args, timeout=timeout)
    return out.strip() if code == 0 else ""


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


def enrich_device(adb_path: str, dev: dict[str, Any]) -> dict[str, Any]:
    out = dict(dev)
    if out["state"] != "device":
        out["usable"] = False
        return out

    serial = out["serial"]
    out["usable"] = True
    out["model"] = shell(adb_path, serial, "getprop", "ro.product.model")
    out["android_id"] = shell(adb_path, serial, "settings", "get", "secure", "android_id")
    out["wifi_ip"] = get_wifi_ip(adb_path, serial)
    return out


def get_wifi_ip(adb_path: str, serial: str) -> str:
    out = shell(adb_path, serial, "ip", "-f", "inet", "addr", "show", "wlan0")
    m = re.search(r"inet\s+(\d+\.\d+\.\d+\.\d+)", out)
    return m.group(1) if m else ""


def canonicalize(devices: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for dev in devices:
        groups.setdefault(dev.get("android_id") or dev["serial"], []).append(dev)

    result = []
    for _, group in groups.items():
        usable = [x for x in group if x.get("usable")]
        wifi = [x for x in usable if x.get("is_wifi")]
        chosen = wifi[0] if wifi else (usable[0] if usable else group[0])
        chosen = dict(chosen)
        chosen["duplicate_transports"] = [
            {"serial": x.get("serial"), "is_wifi": x.get("is_wifi"), "state": x.get("state")}
            for x in group
        ]
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


def choose_desktop_ip() -> str:
    ips = get_desktop_ips()
    for ip in ips:
        if ip.startswith("192.0.2."):
            return ip
    return ips[0] if ips else "0.0.0.0"


def is_port_free(port: int) -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("0.0.0.0", port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def choose_free_port() -> int:
    if is_port_free(PREFERRED_NEW_PORT):
        return PREFERRED_NEW_PORT
    for port in range(8767, 8799):
        if is_port_free(port):
            return port
    raise RuntimeError("No free port found in 8766-8798")


def port_owner_report(port: int) -> dict[str, Any]:
    report: dict[str, Any] = {"port": port, "netstat_lines": [], "pids": [], "tasks": []}
    code, out, _ = run(["netstat", "-ano", "-p", "tcp"], timeout=15)
    if code == 0:
        for line in out.splitlines():
            if f":{port} " in line or f":{port}\r" in line or f":{port}\t" in line:
                report["netstat_lines"].append(line)
                parts = line.split()
                if parts:
                    pid = parts[-1]
                    if pid.isdigit() and pid not in report["pids"]:
                        report["pids"].append(pid)

    for pid in report["pids"]:
        code, out, _ = run(["tasklist", "/FI", f"PID eq {pid}"], timeout=10)
        if code == 0:
            report["tasks"].append({"pid": pid, "tasklist": out})

    return report


def package_exists(adb_path: str, serial: str) -> bool:
    code, out, _ = adb_s(adb_path, serial, "shell", "pm", "path", TARGET_PACKAGE, timeout=15)
    return code == 0 and "package:" in out


def run_as_cat_json(adb_path: str, serial: str, rel_path: str) -> dict[str, Any] | None:
    code, out, err = adb_s(adb_path, serial, "shell", "run-as", TARGET_PACKAGE, "cat", rel_path, timeout=15)
    if code != 0:
        log(f"read failed {serial} {rel_path}: {err or out}")
        return None
    try:
        return json.loads(out)
    except Exception:
        log(f"json parse failed {serial} {rel_path}: {out[:500]}")
        return None


def run_as_write_json_fixed(adb_path: str, serial: str, rel_path: str, data: dict[str, Any]) -> bool:
    """
    Correct write method:
    - cd into app data dir first, because run-as sh starts somewhere inconsistent.
    - quote the whole sh -c script as one adb argument.
    - use echo instead of printf to avoid Android toybox printf argument issue.
    """
    text = json.dumps(data, indent=2)
    payload = base64.b64encode(text.encode("utf-8")).decode("ascii")
    script = (
        "cd /data/user/0/com.example.engel_remote_worker && "
        "mkdir -p files && "
        f"echo {payload} | base64 -d > {rel_path}"
    )
    code, out, err = adb_s(adb_path, serial, "shell", "run-as", TARGET_PACKAGE, "sh", "-c", script, timeout=20)
    if code != 0:
        log(f"write failed {serial}: {err or out}")
        return False

    check = run_as_cat_json(adb_path, serial, rel_path)
    return check == data


def handle_client(conn: socket.socket, addr: tuple[str, int]) -> None:
    entry: dict[str, Any] = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "remote_ip": addr[0],
        "remote_port": addr[1],
        "first_text": "",
        "first_hex": "",
        "response_sent": "",
    }
    log(f"CLIENT CONNECTED from {addr[0]}:{addr[1]}")

    try:
        conn.settimeout(8)
        data = b""
        try:
            data = conn.recv(8192)
        except socket.timeout:
            pass

        entry["first_hex"] = data[:512].hex()
        entry["first_text"] = data[:4096].decode("utf-8", errors="replace")
        if entry["first_text"]:
            log("CLIENT FIRST TEXT: " + entry["first_text"][:1000].replace("\r", "\\r").replace("\n", "\\n"))

        body = json.dumps({
            "type": "engel_remote_worker_port_conflict_fix",
            "status": "desktop_reached",
            "paired": False,
            "message": "Phone reached corrected port. Capture active.",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }, indent=2)

        if entry["first_text"].startswith("GET ") or entry["first_text"].startswith("POST "):
            response = (
                "HTTP/1.1 200 OK\r\n"
                "Content-Type: application/json\r\n"
                f"Content-Length: {len(body.encode('utf-8'))}\r\n"
                "Connection: close\r\n"
                "\r\n" + body
            )
            conn.sendall(response.encode("utf-8"))
            entry["response_sent"] = "http_json"
        else:
            conn.sendall((body + "\n").encode("utf-8"))
            entry["response_sent"] = "plain_json"

    except Exception as e:
        entry["error"] = str(e)
        log(f"client handler error: {e}")
    finally:
        CAPTURES.append(entry)
        try:
            CAPTURE_FILE.write_text(json.dumps(CAPTURES, indent=2), encoding="utf-8")
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass


def server(port: int) -> None:
    global STOP_SERVER
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", port))
    srv.listen(50)
    srv.settimeout(1)
    log(f"FIX SERVER LISTENING on 0.0.0.0:{port}")

    while not STOP_SERVER:
        try:
            conn, addr = srv.accept()
            threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()
        except socket.timeout:
            continue
        except Exception as e:
            log(f"server error: {e}")
            break

    try:
        srv.close()
    except Exception:
        pass


def launch_worker(adb_path: str, serial: str) -> None:
    adb_s(adb_path, serial, "shell", "am", "force-stop", TARGET_PACKAGE, timeout=10)
    adb_s(adb_path, serial, "shell", "am", "start", "-n", TARGET_ACTIVITY, timeout=15)


def make_report(state: dict[str, Any]) -> str:
    lines = [
        "# Engel Remote Worker Port Conflict Fix Report",
        "",
        f"- Time: `{state.get('timestamp')}`",
        f"- Desktop IP: `{state.get('desktop_ip')}`",
        f"- Old port: `{OLD_PORT}`",
        f"- New port: `{state.get('new_port')}`",
        f"- Overall: `{state.get('overall')}`",
        "",
        "## Port 8765 owner",
        "",
        "```text",
        json.dumps(state.get("old_port_owner"), indent=2),
        "```",
        "",
        "## Meaning",
        "",
    ]

    if state.get("old_port_free"):
        lines.append("Port 8765 was free at check time, so the HTTP 400 response likely came from a transient or different listener.")
    else:
        lines.append("Port 8765 was not free. The worker app was aimed at a port already owned by another process/service.")

    if state.get("capture_count", 0) > 0:
        lines.append("The phone reached the replacement port. Next step is implement the exact protocol from the capture.")
    else:
        lines.append("No phone reached the replacement port. The app may not re-read worker_connection.json at launch, or pairing code path is inactive.")

    lines += ["", "## Workers", ""]
    for w in state.get("workers", []):
        lines += [
            f"### {w.get('worker_name')} / {w.get('model')}",
            "",
            f"- Serial: `{w.get('serial')}`",
            f"- Phone IP: `{w.get('phone_ip')}`",
            f"- Worker ID: `{w.get('worker_id')}`",
            f"- Old connection: `{w.get('old_connection')}`",
            f"- New connection: `{w.get('new_connection')}`",
            f"- Write verified: `{w.get('write_verified')}`",
            "",
        ]

    lines += ["## Captures", "", "```json", json.dumps(state.get("captures", []), indent=2), "```", ""]
    return "\n".join(lines)


def main() -> None:
    global STOP_SERVER

    ensure_dirs()
    log("Starting Engel Remote Worker Port Conflict Fix.")

    adb_path = find_adb()
    if not adb_path:
        log("ADB not found.")
        return

    old_port_free = is_port_free(OLD_PORT)
    old_owner = port_owner_report(OLD_PORT)
    new_port = choose_free_port()
    desktop_ip = choose_desktop_ip()

    adb(adb_path, "start-server", timeout=15)

    devices = canonicalize([enrich_device(adb_path, d) for d in parse_devices(adb_path)])
    workers = []

    for dev in devices:
        if not dev.get("usable"):
            continue

        serial = dev["serial"]
        if not package_exists(adb_path, serial):
            continue

        identity = run_as_cat_json(adb_path, serial, "./files/worker_identity.json") or {}
        old_conn = run_as_cat_json(adb_path, serial, "./files/worker_connection.json") or {}

        new_conn = dict(old_conn)
        new_conn["auto_pair"] = True
        new_conn["host"] = desktop_ip
        new_conn["port"] = new_port

        ok = run_as_write_json_fixed(adb_path, serial, "./files/worker_connection.json", new_conn)
        after = run_as_cat_json(adb_path, serial, "./files/worker_connection.json") or {}

        workers.append({
            "serial": serial,
            "model": dev.get("model"),
            "android_id": dev.get("android_id"),
            "phone_ip": dev.get("wifi_ip"),
            "worker_id": identity.get("worker_id"),
            "worker_name": identity.get("worker_name"),
            "old_connection": old_conn,
            "new_connection": after,
            "write_verified": ok,
        })

    CAPTURE_FILE.write_text("[]", encoding="utf-8")
    thread = threading.Thread(target=server, args=(new_port,), daemon=True)
    thread.start()
    time.sleep(1)

    print("")
    print("PORT CONFLICT FIX READY")
    print(f"Desktop IP: {desktop_ip}")
    print(f"Old port: {OLD_PORT}")
    print(f"Replacement port: {new_port}")
    print("Keep this window open. The app will be launched and captured for 60 seconds.")
    print("If Windows Firewall asks, allow Python on PRIVATE networks.")
    print("")

    for w in workers:
        launch_worker(adb_path, w["serial"])

    for remaining in range(60, 0, -5):
        log(f"Capture active... {remaining}s remaining. Captures: {len(CAPTURES)}")
        time.sleep(5)

    STOP_SERVER = True
    time.sleep(1)

    overall = "PHONE_REACHED_REPLACEMENT_PORT" if CAPTURES else "NO_PHONE_CONNECTION_TO_REPLACEMENT_PORT"

    state = {
        "overall": overall,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "engel_root": str(ENGEL_ROOT),
        "adb_path": adb_path,
        "target_package": TARGET_PACKAGE,
        "desktop_ip": desktop_ip,
        "all_desktop_ips": get_desktop_ips(),
        "old_port": OLD_PORT,
        "old_port_free": old_port_free,
        "old_port_owner": old_owner,
        "new_port": new_port,
        "workers": workers,
        "capture_count": len(CAPTURES),
        "captures": CAPTURES,
        "notes": [
            "No C: writes.",
            "Only com.example.engel_remote_worker was targeted.",
            "worker_connection.json write command was fixed in this script.",
        ],
    }

    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    REPORT_FILE.write_text(make_report(state), encoding="utf-8")
    CAPTURE_FILE.write_text(json.dumps(CAPTURES, indent=2), encoding="utf-8")

    log(f"Wrote state: {STATE_FILE}")
    log(f"Wrote capture: {CAPTURE_FILE}")
    log(f"Wrote report: {REPORT_FILE}")
    log(f"Finished. Overall: {overall}")

    print("")
    print("DONE")
    print(f"Overall: {overall}")
    print(f"Old port 8765 free: {old_port_free}")
    print(f"Replacement port: {new_port}")
    print(f"Captures: {len(CAPTURES)}")
    print(f"Report: {REPORT_FILE}")
    print(f"State:  {STATE_FILE}")


if __name__ == "__main__":
    main()
