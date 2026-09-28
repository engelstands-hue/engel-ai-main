#!/usr/bin/env python3
"""
Engel Remote Worker Pairing Sniffer - D-only

Use this when the Engel Remote Worker app still says "not paired".

Purpose:
- Do not guess the phone protocol.
- Do not use Claude/Codex.
- Do not write to C:.
- Target ONLY: com.example.engel_remote_worker
- Keep a listener open on the host/port the app expects.
- Update the worker app connection file to this PC IP if needed.
- Launch the real worker app.
- Capture:
  1. whether the phone connects to the PC,
  2. the first bytes/request the phone sends,
  3. matching Android logcat lines,
  4. current worker_identity.json and worker_connection.json.

If no connection appears, the problem is network/firewall/app not trying.
If a connection appears, the captured first request tells us the actual protocol to implement next.
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
PORT_DEFAULT = 8765

STATE_FILE = BRIDGE_DIR / "ENGEL_REMOTE_WORKER_SNIFFER_STATE.json"
CAPTURE_FILE = BRIDGE_DIR / "ENGEL_REMOTE_WORKER_SNIFFER_CAPTURE.json"
REPORT_FILE = REPORT_DIR / "ENGEL_REMOTE_WORKER_SNIFFER_REPORT.md"
LOG_FILE = BRIDGE_DIR / "engel_remote_worker_pairing_sniffer.log"

ADB_CANDIDATES = [
    ENGEL_ROOT / "tools" / "platform-tools" / "adb.exe",
    Path(r"D:\platform-tools\adb.exe"),
    ENGEL_ROOT / "platform-tools" / "adb.exe",
    Path.cwd() / "tools" / "platform-tools" / "adb.exe",
    Path.cwd() / "platform-tools" / "adb.exe",
    Path.cwd() / "adb.exe",
]

PAIRING_LOG_WORDS = [
    "engel", "worker", "remote", "pair", "paired", "pairing", "not paired",
    "connect", "connected", "connection", "socket", "websocket", "ws://",
    "http", "host", "port", "token", "code", "8765", "192.168"
]

CAPTURES: list[dict[str, Any]] = []
STOP_SERVER = False


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
            log("STDOUT: " + out[:3000])
        if err:
            log("STDERR: " + err[:3000])
        return p.returncode, out, err
    except subprocess.TimeoutExpired:
        return 998, "", f"Timed out after {timeout}s"
    except Exception as exc:
        return 997, "", str(exc)


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
                "detail": " ".join(parts[2:]),
                "is_wifi": bool(re.match(r"^\d+\.\d+\.\d+\.\d+:\d+$", serial)),
            })
    return devices


def get_wifi_ip(adb_path: str, serial: str) -> str:
    out = shell(adb_path, serial, "ip", "-f", "inet", "addr", "show", "wlan0", timeout=10)
    m = re.search(r"inet\s+(\d+\.\d+\.\d+\.\d+)", out)
    return m.group(1) if m else ""


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
    code, out, err = adb_s(adb_path, serial, "shell", "run-as", TARGET_PACKAGE, "cat", rel_path, timeout=15)
    if code != 0:
        log(f"read failed {serial} {rel_path}: {err or out}")
        return None
    try:
        return json.loads(out)
    except Exception:
        log(f"json parse failed {serial} {rel_path}: {out[:500]}")
        return None


def run_as_write_json(adb_path: str, serial: str, rel_path: str, data: dict[str, Any]) -> bool:
    text = json.dumps(data, indent=2)
    payload = base64.b64encode(text.encode("utf-8")).decode("ascii")
    cmd = f"printf %s {payload} | base64 -d > {rel_path}"
    code, out, err = adb_s(adb_path, serial, "shell", "run-as", TARGET_PACKAGE, "sh", "-c", cmd, timeout=15)
    if code == 0:
        return True
    log(f"write failed {serial} {rel_path}: {err or out}")
    return False


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


def choose_desktop_ip(expected_hosts: list[str]) -> str:
    ips = get_desktop_ips()
    for expected in expected_hosts:
        if expected in ips:
            return expected
    for ip in ips:
        if ip.startswith("192.0.2."):
            return ip
    return ips[0] if ips else "0.0.0.0"


def handle_client(conn: socket.socket, addr: tuple[str, int]) -> None:
    entry: dict[str, Any] = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "remote_ip": addr[0],
        "remote_port": addr[1],
        "first_bytes_hex": "",
        "first_text": "",
        "response_sent": "",
    }

    log(f"CLIENT CONNECTED from {addr[0]}:{addr[1]}")

    try:
        conn.settimeout(8)
        data = b""
        try:
            data = conn.recv(8192)
        except socket.timeout:
            log("Client connected but sent no data before timeout.")

        entry["first_bytes_hex"] = data[:512].hex()
        entry["first_text"] = data[:4096].decode("utf-8", errors="replace")

        if entry["first_text"]:
            log("CLIENT FIRST TEXT: " + entry["first_text"][:1000].replace("\r", "\\r").replace("\n", "\\n"))

        # Send multiple friendly protocol hints without pretending full pairing.
        text = entry["first_text"]
        body = json.dumps({
            "type": "engel_remote_pairing_probe",
            "status": "host_reached",
            "paired": False,
            "message": "Desktop host reached. Protocol capture is active.",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }, indent=2)

        if text.startswith("GET ") or text.startswith("POST "):
            response = (
                "HTTP/1.1 200 OK\r\n"
                "Content-Type: application/json\r\n"
                f"Content-Length: {len(body.encode('utf-8'))}\r\n"
                "Connection: close\r\n"
                "\r\n"
                + body
            )
            conn.sendall(response.encode("utf-8"))
            entry["response_sent"] = "http_json_host_reached"
        else:
            conn.sendall((body + "\n").encode("utf-8"))
            entry["response_sent"] = "plain_json_host_reached"

    except Exception as exc:
        entry["error"] = str(exc)
        log(f"client handler error: {exc}")
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


def sniffer_server(port: int) -> None:
    global STOP_SERVER

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", port))
    srv.listen(50)
    srv.settimeout(1.0)
    log(f"SNIFFER LISTENING on 0.0.0.0:{port}")

    while not STOP_SERVER:
        try:
            conn, addr = srv.accept()
            threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()
        except socket.timeout:
            continue
        except Exception as exc:
            log(f"server error: {exc}")
            break

    try:
        srv.close()
    except Exception:
        pass


def launch_worker(adb_path: str, serial: str) -> None:
    # Force-stop then launch only the real worker app.
    adb_s(adb_path, serial, "shell", "am", "force-stop", TARGET_PACKAGE, timeout=10)
    adb_s(adb_path, serial, "shell", "am", "start", "-n", TARGET_ACTIVITY, timeout=15)


def clear_logcat(adb_path: str, serial: str) -> None:
    adb_s(adb_path, serial, "logcat", "-c", timeout=10)


def get_filtered_logcat(adb_path: str, serial: str) -> list[str]:
    code, out, _ = adb_s(adb_path, serial, "logcat", "-d", "-v", "time", timeout=30)
    if code != 0:
        return []
    lines = []
    for line in out.splitlines():
        low = line.lower()
        if any(word in low for word in PAIRING_LOG_WORDS):
            lines.append(line[-1000:])
    return lines[-200:]


def make_report(state: dict[str, Any]) -> str:
    lines = [
        "# Engel Remote Worker Pairing Sniffer Report",
        "",
        f"- Time: `{state.get('timestamp')}`",
        f"- Target package: `{TARGET_PACKAGE}`",
        f"- Desktop IP: `{state.get('desktop_ip')}`",
        f"- Port: `{state.get('port')}`",
        f"- Overall: `{state.get('overall')}`",
        "",
        "## What this means",
        "",
    ]

    if state.get("capture_count", 0) > 0:
        lines.append("At least one phone reached the desktop host. The issue is protocol mismatch, not network reachability.")
    else:
        lines.append("No phone reached the desktop host during the capture window. The likely causes are Windows Firewall, wrong host IP, wrong port, or the app is not attempting network pairing.")

    lines += [
        "",
        "## Workers",
        "",
    ]

    for worker in state.get("workers", []):
        lines += [
            f"### {worker.get('worker_name')} / {worker.get('model')}",
            "",
            f"- Serial: `{worker.get('serial')}`",
            f"- Phone IP: `{worker.get('phone_ip')}`",
            f"- Worker ID: `{worker.get('worker_id')}`",
            f"- Connection host now: `{worker.get('connection_after', {}).get('host')}`",
            f"- Connection port now: `{worker.get('connection_after', {}).get('port')}`",
            f"- App launched: `{worker.get('launched')}`",
            "",
        ]
        if worker.get("logcat_filtered"):
            lines.append("Filtered logcat:")
            for item in worker.get("logcat_filtered", [])[:30]:
                lines.append(f"- `{item}`")
            lines.append("")

    lines += [
        "## Captures",
        "",
    ]

    for cap in state.get("captures", []):
        lines += [
            f"### Connection from {cap.get('remote_ip')}:{cap.get('remote_port')}",
            "",
            f"- Response sent: `{cap.get('response_sent')}`",
            "",
            "First text:",
            "```text",
            cap.get("first_text", "")[:2000],
            "```",
            "",
            "First bytes hex:",
            "```text",
            cap.get("first_bytes_hex", "")[:1000],
            "```",
            "",
        ]

    lines += [
        "## Next fix",
        "",
        "If captures are empty, fix firewall/IP/port first.",
        "If captures show HTTP/WebSocket/plain JSON, build the real server response that the app expects.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    global STOP_SERVER

    ensure_dirs()
    log("Starting Engel Remote Worker Pairing Sniffer.")

    adb_path = find_adb()
    if not adb_path:
        log("ADB not found under D-only paths.")
        return

    adb(adb_path, "start-server", timeout=15)

    raw = parse_devices(adb_path)
    enriched = [enrich_device(adb_path, d) for d in raw]
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

        if connection.get("host"):
            expected_hosts.append(str(connection.get("host")))
        expected_ports.append(int(connection.get("port") or PORT_DEFAULT))

        workers.append({
            "serial": serial,
            "model": dev.get("model"),
            "android_id": dev.get("android_id"),
            "phone_ip": dev.get("wifi_ip"),
            "worker_id": identity.get("worker_id"),
            "worker_name": identity.get("worker_name"),
            "connection_before": connection,
        })

    desktop_ip = choose_desktop_ip(expected_hosts)
    port = expected_ports[0] if expected_ports else PORT_DEFAULT

    # Update worker connection files to actual desktop IP.
    for worker in workers:
        conn = dict(worker.get("connection_before") or {})
        conn["auto_pair"] = True
        conn["host"] = desktop_ip
        conn["port"] = port
        ok = run_as_write_json(adb_path, worker["serial"], "./files/worker_connection.json", conn)
        worker["connection_after"] = run_as_cat_json(adb_path, worker["serial"], "./files/worker_connection.json") or conn
        worker["connection_update_ok"] = ok

    CAPTURE_FILE.write_text("[]", encoding="utf-8")
    server_thread = threading.Thread(target=sniffer_server, args=(port,), daemon=True)
    server_thread.start()

    print("")
    print("SNIFFER READY")
    print(f"Desktop IP: {desktop_ip}")
    print(f"Port: {port}")
    print("The script will launch the worker app on the phones and listen for 60 seconds.")
    print("If Windows Firewall asks, allow Python on PRIVATE networks.")
    print("Do not close this window.")
    print("")

    # Clear logcat and launch app.
    for worker in workers:
        clear_logcat(adb_path, worker["serial"])
        launch_worker(adb_path, worker["serial"])
        worker["launched"] = True

    # Wait for app attempts.
    for remaining in range(60, 0, -5):
        log(f"Capture window active... {remaining}s remaining. Captures so far: {len(CAPTURES)}")
        time.sleep(5)

    # Collect logcat.
    for worker in workers:
        worker["logcat_filtered"] = get_filtered_logcat(adb_path, worker["serial"])

    STOP_SERVER = True
    time.sleep(1)

    overall = "PHONE_REACHED_HOST_PROTOCOL_CAPTURED" if CAPTURES else "NO_PHONE_CONNECTION_TO_HOST"

    state = {
        "overall": overall,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "engel_root": str(ENGEL_ROOT),
        "adb_path": adb_path,
        "target_package": TARGET_PACKAGE,
        "desktop_ip": desktop_ip,
        "all_desktop_ips": get_desktop_ips(),
        "port": port,
        "workers": workers,
        "capture_count": len(CAPTURES),
        "captures": CAPTURES,
        "notes": [
            "No C: writes.",
            "Only com.example.engel_remote_worker was targeted.",
            "com.engel.engel_monitor is intentionally ignored.",
        ],
    }

    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    CAPTURE_FILE.write_text(json.dumps(CAPTURES, indent=2), encoding="utf-8")
    REPORT_FILE.write_text(make_report(state), encoding="utf-8")

    log(f"Wrote state: {STATE_FILE}")
    log(f"Wrote capture: {CAPTURE_FILE}")
    log(f"Wrote report: {REPORT_FILE}")
    log(f"Finished. Overall: {overall}")

    print("")
    print("DONE")
    print(f"Overall: {overall}")
    print(f"Captures: {len(CAPTURES)}")
    print(f"Open report: {REPORT_FILE}")
    print(f"Open capture: {CAPTURE_FILE}")


if __name__ == "__main__":
    main()
