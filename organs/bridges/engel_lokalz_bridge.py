from __future__ import annotations

import json
import os
import socket
import threading
import time
import uuid
from pathlib import Path

try:
    import requests
except ImportError:
    requests = None

ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
# Path to the LocalSend protocol source tree (external folder name kept as-is).
LOKALZ_SRC = ROOT / "external" / "localsend-main"

# LocalSend protocol defaults — these are the wire-protocol constants and
# must match the published LocalSend spec.
MULTICAST_GROUP = "224.0.0.167"
DEFAULT_PORT = 53317
DEVICE_FINGERPRINT = str(uuid.uuid4())[:16]

_LOCK = threading.Lock()
_DEVICES: dict[str, dict] = {}  # ip -> info


def _src_present() -> bool:
    return (LOKALZ_SRC / "README.md").exists()


def _self_info() -> dict:
    return {
        "alias": "Engel",
        "version": "2.1",
        "deviceModel": "PC",
        "deviceType": "desktop",
        "fingerprint": DEVICE_FINGERPRINT,
        "port": DEFAULT_PORT,
        "protocol": "http",
        "download": False,
        "announce": True,
    }


def lokalz_status() -> str:
    lines = ["# Lokalz Bridge Status", ""]
    lines.append(f"Source: {'PRESENT' if _src_present() else 'NOT FOUND'}  [{LOKALZ_SRC}]")
    lines.append(f"requests lib: {'OK' if requests else 'MISSING (pip install requests)'}")
    lines.append(f"Engel device fingerprint: {DEVICE_FINGERPRINT}")
    lines.append("")
    with _LOCK:
        if _DEVICES:
            lines.append(f"Known devices ({len(_DEVICES)}):")
            for ip, info in list(_DEVICES.items())[:10]:
                alias = info.get("alias", "?")
                port = info.get("port", DEFAULT_PORT)
                model = info.get("deviceModel", "?")
                lines.append(f"  {ip}:{port}  {alias} ({model})")
        else:
            lines.append("No devices known yet. Run 'lokalz scan'.")
    lines += [
        "",
        "Commands:",
        "  lokalz status              — this page",
        "  lokalz scan [seconds]      — UDP multicast scan (default 5s)",
        "  lokalz list                — list discovered devices",
        "  lokalz info <ip[:port]>    — fetch device info",
        "  lokalz send <ip[:port]> <file>  — send a file",
        "  lokalz forget              — clear device list",
    ]
    return "\n".join(lines)


def _parse_target(target: str) -> tuple[str, int]:
    target = target.strip()
    if ":" in target:
        host, _, port_str = target.partition(":")
        try:
            return host, int(port_str)
        except ValueError:
            return target, DEFAULT_PORT
    return target, DEFAULT_PORT


def lokalz_scan(seconds: int = 5) -> str:
    """Listen for LocalSend UDP multicast announcements on 224.0.0.167:53317."""
    found: dict[str, dict] = {}
    sock = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("", DEFAULT_PORT))
        mreq = socket.inet_aton(MULTICAST_GROUP) + socket.inet_aton("0.0.0.0")
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        sock.settimeout(1.0)

        # Announce ourselves once so passive devices respond.
        try:
            announce_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            announce_sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
            announce_sock.sendto(
                json.dumps(_self_info()).encode("utf-8"),
                (MULTICAST_GROUP, DEFAULT_PORT),
            )
            announce_sock.close()
        except Exception:
            pass

        deadline = time.time() + max(1, seconds)
        while time.time() < deadline:
            try:
                data, addr = sock.recvfrom(2048)
            except socket.timeout:
                continue
            try:
                msg = json.loads(data.decode("utf-8"))
            except Exception:
                continue
            ip = addr[0]
            if msg.get("fingerprint") == DEVICE_FINGERPRINT:
                continue
            found[ip] = msg
    except Exception as exc:
        return f"Scan failed: {exc}"
    finally:
        if sock:
            try:
                sock.close()
            except Exception:
                pass

    with _LOCK:
        _DEVICES.update(found)

    if not found:
        return f"Scanned {seconds}s. No LocalSend devices announced themselves."
    out = [f"Found {len(found)} device(s):"]
    for ip, info in found.items():
        port = info.get("port", DEFAULT_PORT)
        alias = info.get("alias", "?")
        out.append(f"  {ip}:{port}  {alias}")
    return "\n".join(out)


def lokalz_list() -> str:
    with _LOCK:
        if not _DEVICES:
            return "No devices known. Run 'lokalz scan'."
        out = [f"# Known devices ({len(_DEVICES)})"]
        for ip, info in _DEVICES.items():
            port = info.get("port", DEFAULT_PORT)
            alias = info.get("alias", "?")
            model = info.get("deviceModel", "?")
            out.append(f"  {ip}:{port}  {alias} ({model})")
    return "\n".join(out)


def lokalz_info(target: str) -> str:
    if requests is None:
        return "requests not installed. Run: pip install requests"
    if not target.strip():
        return "Usage: lokalz info <ip[:port]>"
    host, port = _parse_target(target)
    # /api/localsend/v2/info is the published LocalSend protocol endpoint;
    # the path string is part of the wire protocol and stays as-is.
    url = f"http://{host}:{port}/api/localsend/v2/info"
    try:
        r = requests.get(url, timeout=5)
    except Exception as exc:
        return f"Failed: {exc}"
    if r.status_code != 200:
        return f"HTTP {r.status_code}: {r.text[:200]}"
    try:
        return json.dumps(r.json(), indent=2)
    except Exception:
        return r.text[:600]


def lokalz_send(target: str, file_path: str) -> str:
    if requests is None:
        return "requests not installed. Run: pip install requests"
    target = target.strip()
    file_path = file_path.strip().strip('"').strip("'")
    if not target or not file_path:
        return "Usage: lokalz send <ip[:port]> <file>"
    fp = Path(file_path)
    if not fp.exists() or not fp.is_file():
        return f"File not found: {fp}"
    host, port = _parse_target(target)

    file_id = uuid.uuid4().hex
    prepare_body = {
        "info": _self_info(),
        "files": {
            file_id: {
                "id": file_id,
                "fileName": fp.name,
                "size": fp.stat().st_size,
                "fileType": "application/octet-stream",
                "preview": None,
            }
        },
    }
    try:
        # /api/localsend/v2/* are protocol-defined endpoints; do not rename.
        r = requests.post(
            f"http://{host}:{port}/api/localsend/v2/prepare-upload",
            json=prepare_body,
            timeout=10,
        )
    except Exception as exc:
        return f"prepare-upload failed: {exc}"
    if r.status_code != 200:
        return f"prepare-upload HTTP {r.status_code}: {r.text[:300]}"
    try:
        prepared = r.json()
    except Exception:
        return f"prepare-upload non-JSON: {r.text[:300]}"

    session_id = prepared.get("sessionId")
    files_map = prepared.get("files", {})
    token = files_map.get(file_id, {}).get("token") if isinstance(files_map, dict) else None
    if not (session_id and token):
        return f"Receiver rejected the file or wrong response: {prepared}"

    try:
        with fp.open("rb") as f:
            r2 = requests.post(
                f"http://{host}:{port}/api/localsend/v2/upload",
                params={"sessionId": session_id, "fileId": file_id, "token": token},
                data=f,
                timeout=300,
            )
    except Exception as exc:
        return f"upload failed: {exc}"
    if r2.status_code in (200, 204):
        return f"Sent {fp.name} ({fp.stat().st_size} bytes) to {host}:{port}"
    return f"upload HTTP {r2.status_code}: {r2.text[:300]}"


def lokalz_forget() -> str:
    with _LOCK:
        n = len(_DEVICES)
        _DEVICES.clear()
    return f"Cleared {n} device(s)."


def handle_lokalz_command(args: str) -> str:
    text = (args or "").strip()
    if not text or text == "status":
        return lokalz_status()
    if text.startswith("scan"):
        rest = text[4:].strip()
        try:
            secs = int(rest) if rest else 5
        except ValueError:
            secs = 5
        return lokalz_scan(secs)
    if text == "list":
        return lokalz_list()
    if text == "forget":
        return lokalz_forget()
    if text.startswith("info"):
        return lokalz_info(text[4:].strip())
    if text.startswith("send"):
        rest = text[4:].strip().split(maxsplit=1)
        if len(rest) < 2:
            return "Usage: lokalz send <ip[:port]> <file>"
        return lokalz_send(rest[0], rest[1])
    return f"Unknown lokalz subcommand: '{text}'. Try 'lokalz status'."
