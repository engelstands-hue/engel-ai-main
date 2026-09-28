#!/usr/bin/env python3
"""
Engel Remote Worker Pairing Host - D-only

Purpose:
- Direct local fix, no Claude/Codex.
- Uses the real worker app package only:
    com.example.engel_remote_worker
- Avoids old/deleted monitor app:
    com.engel.engel_monitor
- Checks whether this PC is actually the host the phones expect.
- If the PC LAN IP changed, updates worker_connection.json on the phones.
- Starts a minimal Engel pairing/heartbeat host on port 8765.
- Writes all files under D:\b.WorkSpace\Engel App only.

Run:
  D:
  cd "D:\\b.WorkSpace\\Engel App"
  python engel_remote_worker_pairing_host_d_only.py

What it found from your phone logs:
- Android Worker Alpha and Beta both have:
  auto_pair: true
  host: 192.0.2.40
  port: 8765

Meaning:
- The phones are trying to reach Engel desktop at 192.0.2.40:8765.
- If this computer is not 192.0.2.40 anymore, the phone app will say not paired.
- If nothing is listening on port 8765, the phone app will say not paired.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import selectors
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

ENGEL_ROOT = Path(r"D:\b.WorkSpace\Engel App")
BRIDGE_DIR = ENGEL_ROOT / "memory" / "phone_bridge"
REPORT_DIR = ENGEL_ROOT / "reports" / "codex_bridge"

TARGET_PACKAGE = "com.example.engel_remote_worker"
PORT_DEFAULT = 8765

STATE_FILE = BRIDGE_DIR / "ENGEL_REMOTE_WORKER_HOST_STATE.json"
REPORT_FILE = REPORT_DIR / "ENGEL_REMOTE_WORKER_HOST_REPORT.md"
LOG_FILE = BRIDGE_DIR / "engel_remote_worker_pairing_host.log"

ADB_CANDIDATES = [
    ENGEL_ROOT / "tools" / "platform-tools" / "adb.exe",
    Path(r"D:\platform-tools\adb.exe"),
    ENGEL_ROOT / "platform-tools" / "adb.exe",
    Path.cwd() / "tools" / "platform-tools" / "adb.exe",
    Path.cwd() / "platform-tools" / "adb.exe",
    Path.cwd() / "adb.exe",
]


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
    for candidate in ADB_CANDIDATES:
        if candidate.exists() and not str(candidate).lower().startswith("c:\\"):
            return str(candidate)

    try:
        result = subprocess.run(["where", "adb"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                line = line.strip()
                if line and not line.lower().startswith("c:\\"):
                    return line
    except Exception:
        pass

    return None


def run(cmd: list[str], timeout: int = 30, input_text: str | None = None) -> tuple[int, str, str]:
    log("RUN: " + " ".join(cmd))
    try:
        proc = subprocess.run(
            cmd,
            input=input_text,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        out = proc.stdout.strip()
        err = proc.stderr.strip()
        if out:
            log("STDOUT: " + out[:3000])
        if err:
            log("STDERR: " + err[:3000])
        return proc.returncode, out, err
    except subprocess.TimeoutExpired:
        return 998, "", f"Timed out after {timeout}s"
    except Exception as exc:
        return 997, "", str(exc)


def adb(adb_path: str, *args: str, timeout: int = 30, input_text: str | None = None) -> tuple[int, str, str]:
    return run([adb_path, *args], timeout=timeout, input_text=input_text)


def adb_s(adb_path: str, serial: str, *args: str, timeout: int = 30, input_text: str | None = None) -> tuple[int, str, str]:
    return adb(adb_path, "-s", serial, *args, timeout=timeout, input_text=input_text)


def parse_devices(adb_path: str) -> list[dict[str, Any]]:
    code, out, _ = adb(adb_path, "devices", "-l", timeout=15)
    devices: list[dict[str, Any]] = []
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
                "detail": " ".join(parts[2:]),
                "is_wifi": bool(re.match(r"^\d+\.\d+\.\d+\.\d+:\d+$", serial)),
            })
    return devices


def shell(adb_path: str, serial: str, *args: str, timeout: int = 20) -> str:
    code, out, _ = adb_s(adb_path, serial, "shell", *args, timeout=timeout)
    return out.strip() if code == 0 else ""


def get_wifi_ip(adb_path: str, serial: str) -> str:
    out = shell(adb_path, serial, "ip", "-f", "inet", "addr", "show", "wlan0", timeout=10)
    match = re.search(r"inet\s+(\d+\.\d+\.\d+\.\d+)", out)
    if match:
        return match.group(1)
    return ""


def enrich_device(adb_path: str, dev: dict[str, Any]) -> dict[str, Any]:
    out = dict(dev)
    if dev["state"] != "device":
        out["usable"] = False
        return out

    serial = dev["serial"]
    out["usable"] = True
    out["model"] = shell(adb_path, serial, "getprop", "ro.product.model", timeout=10)
    out["android_version"] = shell(adb_path, serial, "getprop", "ro.build.version.release", timeout=10)
    out["android_id"] = shell(adb_path, serial, "settings", "get", "secure", "android_id", timeout=10)
    out["wifi_ip"] = get_wifi_ip(adb_path, serial)
    return out


def canonicalize(devices: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for dev in devices:
        key = dev.get("android_id") or dev.get("serial")
        grouped.setdefault(key, []).append(dev)

    result = []
    for _, group in grouped.items():
        usable = [x for x in group if x.get("usable")]
        wifi = [x for x in usable if x.get("is_wifi")]
        chosen = wifi[0] if wifi else (usable[0] if usable else group[0])
        chosen = dict(chosen)
        chosen["duplicate_transports"] = [
            {"serial": x.get("serial"), "state": x.get("state"), "is_wifi": x.get("is_wifi")}
            for x in group
        ]
        result.append(chosen)
    return result


def package_exists(adb_path: str, serial: str) -> bool:
    code, out, _ = adb_s(adb_path, serial, "shell", "pm", "path", TARGET_PACKAGE, timeout=15)
    return code == 0 and "package:" in out


def run_as_cat_json(adb_path: str, serial: str, rel_path: str) -> dict[str, Any] | None:
    code, out, err = adb_s(
        adb_path,
        serial,
        "shell",
        "run-as",
        TARGET_PACKAGE,
        "cat",
        rel_path,
        timeout=15,
    )
    if code != 0:
        log(f"Could not read {rel_path} from {serial}: {err or out}")
        return None
    try:
        return json.loads(out)
    except Exception:
        log(f"Could not parse JSON from {rel_path} on {serial}")
        return None


def run_as_write_json(adb_path: str, serial: str, rel_path: str, data: dict[str, Any]) -> bool:
    # Use base64 to avoid shell quote problems.
    text = json.dumps(data, indent=2)
    payload = base64.b64encode(text.encode("utf-8")).decode("ascii")
    cmd = f"printf %s {payload} | base64 -d > {rel_path}"

    code, out, err = adb_s(
        adb_path,
        serial,
        "shell",
        "run-as",
        TARGET_PACKAGE,
        "sh",
        "-c",
        cmd,
        timeout=15,
    )
    if code == 0:
        return True

    log(f"Write failed for {serial} {rel_path}: {err or out}")
    return False


def get_desktop_lan_ips() -> list[str]:
    ips = set()

    # Best route trick: does not need internet success, only local routing.
    probes = [("8.8.8.8", 80), ("192.0.2.1", 80), ("1.1.1.1", 80)]
    for host, port in probes:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect((host, port))
            ip = s.getsockname()[0]
            if ip and not ip.startswith("127."):
                ips.add(ip)
        except Exception:
            pass
        finally:
            s.close()

    try:
        name = socket.gethostname()
        for item in socket.getaddrinfo(name, None, socket.AF_INET):
            ip = item[4][0]
            if ip and not ip.startswith("127."):
                ips.add(ip)
    except Exception:
        pass

    return sorted(ips)


def choose_desktop_ip(expected_hosts: list[str]) -> str:
    ips = get_desktop_lan_ips()
    for host in expected_hosts:
        if host in ips:
            return host
    # Prefer same subnet 192.0.2.x if present.
    for ip in ips:
        if ip.startswith("192.0.2."):
            return ip
    return ips[0] if ips else "0.0.0.0"


def port_is_free(port: int) -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("0.0.0.0", port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def websocket_accept_key(client_key: str) -> str:
    magic = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
    raw = hashlib.sha1((client_key + magic).encode("utf-8")).digest()
    return base64.b64encode(raw).decode("ascii")


def ws_send_text(conn: socket.socket, text: str) -> None:
    data = text.encode("utf-8")
    header = bytearray()
    header.append(0x81)
    length = len(data)
    if length < 126:
        header.append(length)
    elif length < 65536:
        header.append(126)
        header += length.to_bytes(2, "big")
    else:
        header.append(127)
        header += length.to_bytes(8, "big")
    conn.sendall(bytes(header) + data)


def handle_plain_or_ws_client(conn: socket.socket, addr: tuple[str, int], pairing_state: dict[str, Any]) -> None:
    log(f"Client connected from {addr[0]}:{addr[1]}")
    conn.settimeout(10)

    try:
        first = conn.recv(4096)
        if not first:
            log("Client sent no data.")
            return

        text = first.decode("utf-8", errors="replace")
        log("CLIENT FIRST DATA: " + text[:1000].replace("\r", "\\r").replace("\n", "\\n"))

        hello = {
            "type": "engel_pairing_host",
            "status": "ready",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "pairing": {
                "auto_pair": True,
                "accepted_worker_ids": [w.get("worker_id") for w in pairing_state.get("workers", [])],
                "port": pairing_state.get("port"),
                "host": pairing_state.get("desktop_ip"),
            },
            "message": "Engel desktop pairing host is listening.",
        }

        if text.startswith("GET ") and "Upgrade: websocket" in text:
            key_match = re.search(r"Sec-WebSocket-Key:\s*(.+)", text, flags=re.IGNORECASE)
            if not key_match:
                log("WebSocket request missing Sec-WebSocket-Key.")
                return

            accept = websocket_accept_key(key_match.group(1).strip())
            response = (
                "HTTP/1.1 101 Switching Protocols\r\n"
                "Upgrade: websocket\r\n"
                "Connection: Upgrade\r\n"
                f"Sec-WebSocket-Accept: {accept}\r\n"
                "\r\n"
            )
            conn.sendall(response.encode("utf-8"))
            ws_send_text(conn, json.dumps(hello))
            log("Sent WebSocket hello.")
            time.sleep(2)
            return

        # Plain TCP/HTTP fallback.
        if text.startswith("GET ") or text.startswith("POST "):
            body = json.dumps(hello, indent=2)
            response = (
                "HTTP/1.1 200 OK\r\n"
                "Content-Type: application/json\r\n"
                f"Content-Length: {len(body.encode('utf-8'))}\r\n"
                "Connection: close\r\n"
                "\r\n"
                + body
            )
            conn.sendall(response.encode("utf-8"))
            log("Sent HTTP JSON hello.")
        else:
            conn.sendall((json.dumps(hello) + "\n").encode("utf-8"))
            log("Sent plain TCP JSON hello.")

    except Exception as exc:
        log(f"Client handler error: {exc}")
    finally:
        try:
            conn.close()
        except Exception:
            pass


def start_pairing_host(port: int, pairing_state: dict[str, Any]) -> None:
    if not port_is_free(port):
        log(f"Port {port} is already in use. If Engel is already running, this may be OK.")
        return

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("0.0.0.0", port))
    server.listen(20)

    log(f"Engel pairing host listening on 0.0.0.0:{port}")
    log("Keep this window open while testing the phone app.")

    while True:
        try:
            conn, addr = server.accept()
            t = threading.Thread(target=handle_plain_or_ws_client, args=(conn, addr, pairing_state), daemon=True)
            t.start()
        except KeyboardInterrupt:
            log("Stopped by user.")
            break
        except Exception as exc:
            log(f"Server accept error: {exc}")


def make_report(state: dict[str, Any]) -> str:
    lines = [
        "# Engel Remote Worker Host Report",
        "",
        f"- Time: `{state.get('timestamp')}`",
        f"- Desktop IP selected: `{state.get('desktop_ip')}`",
        f"- Port: `{state.get('port')}`",
        f"- Target package: `{TARGET_PACKAGE}`",
        f"- Overall: `{state.get('overall')}`",
        "",
        "## Meaning",
        "",
        "Both phones were configured to auto-pair to a desktop host and port. If that host IP is not this computer, the phone app will say not paired.",
        "",
        "## Workers",
        "",
    ]

    for worker in state.get("workers", []):
        lines += [
            f"### {worker.get('worker_name')} / {worker.get('model')}",
            "",
            f"- ADB serial: `{worker.get('serial')}`",
            f"- Phone IP: `{worker.get('phone_ip')}`",
            f"- Worker ID: `{worker.get('worker_id')}`",
            f"- Old host: `{worker.get('old_connection', {}).get('host')}`",
            f"- New host: `{worker.get('new_connection', {}).get('host')}`",
            f"- Port: `{worker.get('new_connection', {}).get('port')}`",
            f"- Updated phone file: `{worker.get('phone_file_updated')}`",
            "",
        ]

    lines += [
        "## Test",
        "",
        "Keep the Python window open, then open the Engel Remote Worker app on each phone.",
        "If the app connects, the terminal should print `Client connected from ...`.",
        "",
        "If no client connects, check Windows Firewall for Python on private networks and confirm the PC IP is reachable from the phones.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    ensure_dirs()
    log("Starting Engel Remote Worker Pairing Host.")

    adb_path = find_adb()
    if not adb_path:
        log("ADB not found under D-safe paths.")
        return

    adb(adb_path, "start-server", timeout=15)

    raw_devices = parse_devices(adb_path)
    enriched = [enrich_device(adb_path, d) for d in raw_devices]
    canonical = canonicalize(enriched)

    workers = []
    expected_hosts = []
    expected_ports = []

    for dev in canonical:
        if not dev.get("usable"):
            continue

        serial = dev["serial"]
        if not package_exists(adb_path, serial):
            continue

        identity = run_as_cat_json(adb_path, serial, "./files/worker_identity.json") or {}
        connection = run_as_cat_json(adb_path, serial, "./files/worker_connection.json") or {}

        host = connection.get("host")
        port = int(connection.get("port") or PORT_DEFAULT)
        if host:
            expected_hosts.append(host)
        expected_ports.append(port)

        workers.append({
            "serial": serial,
            "model": dev.get("model"),
            "android_id": dev.get("android_id"),
            "phone_ip": dev.get("wifi_ip"),
            "worker_id": identity.get("worker_id"),
            "worker_name": identity.get("worker_name"),
            "old_connection": connection,
            "new_connection": dict(connection),
            "phone_file_updated": False,
        })

    desktop_ip = choose_desktop_ip(expected_hosts)
    port = expected_ports[0] if expected_ports else PORT_DEFAULT

    for worker in workers:
        new_conn = dict(worker["old_connection"])
        new_conn["auto_pair"] = True
        new_conn["host"] = desktop_ip
        new_conn["port"] = port
        worker["new_connection"] = new_conn

        if new_conn != worker["old_connection"]:
            ok = run_as_write_json(adb_path, worker["serial"], "./files/worker_connection.json", new_conn)
            worker["phone_file_updated"] = ok
        else:
            worker["phone_file_updated"] = False

    state = {
        "overall": "HOST_READY",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "engel_root": str(ENGEL_ROOT),
        "adb_path": adb_path,
        "target_package": TARGET_PACKAGE,
        "desktop_ip": desktop_ip,
        "all_desktop_ips": get_desktop_lan_ips(),
        "port": port,
        "workers": workers,
        "notes": [
            "Keep this script running while testing the app.",
            "If Windows Firewall asks, allow Python on Private networks.",
            "This script avoids com.engel.engel_monitor.",
            "No files are written to C: by this script.",
        ],
    }

    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    REPORT_FILE.write_text(make_report(state), encoding="utf-8")

    log(f"Wrote state: {STATE_FILE}")
    log(f"Wrote report: {REPORT_FILE}")
    log(f"Desktop IP selected: {desktop_ip}")
    log(f"Port selected: {port}")

    print("")
    print("READY")
    print(f"Desktop IP: {desktop_ip}")
    print(f"Port: {port}")
    print("Keep this window open, then open the Engel Remote Worker app on the phones.")
    print("Watch for: Client connected from ...")
    print("Press Ctrl+C to stop.")
    print("")

    start_pairing_host(port, state)


if __name__ == "__main__":
    main()
