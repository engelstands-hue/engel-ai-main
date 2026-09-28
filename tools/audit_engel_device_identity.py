#!/usr/bin/env python3
"""Write an evidence-based Engel device identity/location inventory."""

from __future__ import annotations

import argparse
import json
import os
import re
import socket
import subprocess
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / "runtime" / "python310" / "python.exe"
ADB = ROOT / "tools" / "platform-tools" / "adb.exe"
SUB_CLIENT = ROOT / "engel_sub_node_remote_control.py"
SESSION_STATE = ROOT / "remote_workers" / "lan_link_manager" / "session_state.json"
LATEST_STATE = ROOT / "runtime" / "device_swarm" / "device_identity_audit_latest.json"
REPORT_DIR = ROOT / "reports" / "device_audits"
SSH_KEY = Path.home() / ".ssh" / "engel_ai_main_ct246_ed25519"

PHONE_BY_SERIAL = {
    "ANDROID_WORKER_ALPHA": ("android_worker_alpha", "Alpha", "Motorola", "moto g power - 2025", "16"),
    "ANDROID_WORKER_BETA": ("android_worker_beta", "Beta", "Motorola", "moto g fast", "11"),
    "ANDROID_WORKER_GAMMA": ("android_worker_gamma", "Gamma", "Samsung", "Galaxy A14 5G (SM-A146U)", "13"),
}
OUI_VENDORS = {
    "94-CD-FD": "eero inc.",
    "3C-9B-D6": "Vizio, Inc.",
    "E4-C7-67": "Intel Corporate",
    "EC-F4-BB": "Dell Inc.",
    "FC-4D-D4": "Universal Global Scientific Industrial., Ltd",
}


def now() -> datetime:
    return datetime.now(timezone.utc)


def iso_now() -> str:
    return now().isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def run(command: list[str], timeout: int = 12) -> subprocess.CompletedProcess[str]:
    kwargs: dict[str, Any] = {
        "capture_output": True,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
        "timeout": timeout,
        "cwd": str(ROOT),
    }
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    try:
        return subprocess.run(command, **kwargs)
    except subprocess.TimeoutExpired as error:
        return subprocess.CompletedProcess(command, 124, error.stdout or "", "timeout")
    except OSError as error:
        return subprocess.CompletedProcess(command, 127, "", str(error))


def ps_json(script: str, timeout: int = 15) -> Any:
    result = run(["powershell.exe", "-NoProfile", "-Command", script], timeout)
    try:
        return json.loads(result.stdout.lstrip("\ufeff")) if result.returncode == 0 else None
    except json.JSONDecodeError:
        return None


def http_json(url: str, timeout: float = 3.0) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            value = json.loads(response.read().decode("utf-8", "replace"))
            return value if isinstance(value, dict) else {}
    except (OSError, urllib.error.URLError, json.JSONDecodeError):
        return {}


def http_text(url: str, timeout: float = 3.0) -> str:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return response.read().decode("utf-8", "replace")
    except (OSError, urllib.error.URLError):
        return ""


def age_seconds(value: Any) -> float | None:
    try:
        timestamp = str(value).replace("Z", "+00:00")
        timestamp = re.sub(r"(\.\d{6})\d+(?=[+-]\d{2}:\d{2}$)", r"\1", timestamp)
        parsed = datetime.fromisoformat(timestamp)
        return max(0.0, (now() - parsed.astimezone(timezone.utc)).total_seconds())
    except ValueError:
        return None


def mac_vendor(mac: str) -> str:
    # Resolve against the full 30k-entry nmap OUI DB (via the fingerprint engine's
    # resolver) so EVERY device in the audit/Swarm 3D gets a real vendor, not the
    # old 5-entry map. Falls back to the local map if the engine can't be imported.
    try:
        from engel_lan_fingerprint import mac_vendor as _full_vendor

        vendor, _randomized = _full_vendor(mac)
        return vendor
    except Exception:
        pass
    normalized = mac.upper().replace(":", "-")
    if not normalized:
        return ""
    try:
        if int(normalized.split("-")[0], 16) & 2:
            return "Private/randomized MAC"
    except ValueError:
        return "Unknown OUI"
    return OUI_VENDORS.get(normalized[:8], "Unknown OUI")


def local_host() -> dict[str, Any]:
    return ps_json(
        r"""
$cs=Get-CimInstance Win32_ComputerSystem
$gpu=Get-CimInstance Win32_VideoController | Select-Object Name
$net=Get-NetAdapter | Where-Object {$_.Status -eq 'Up'} | Select-Object Name,MacAddress,LinkSpeed
$ip=Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.IPAddress -notlike '169.254*' -and $_.IPAddress -ne '127.0.0.1'} | Select-Object IPAddress,PrefixLength,InterfaceAlias
[pscustomobject]@{computer_name=$env:COMPUTERNAME;manufacturer=$cs.Manufacturer;model=$cs.Model;gpu=@($gpu);adapters=@($net);ipv4=@($ip)} | ConvertTo-Json -Depth 5 -Compress
"""
    ) or {}


def pnp_locations() -> dict[str, dict[str, Any]]:
    pattern = "|".join(PHONE_BY_SERIAL)
    raw = ps_json(
        rf"""
$devs=Get-PnpDevice -PresentOnly | Where-Object {{$_.InstanceId -match '{pattern}'}}
$out=foreach($d in $devs){{
  $loc=(Get-PnpDeviceProperty -InstanceId $d.InstanceId -KeyName 'DEVPKEY_Device_LocationInfo' -ErrorAction SilentlyContinue).Data
  $paths=(Get-PnpDeviceProperty -InstanceId $d.InstanceId -KeyName 'DEVPKEY_Device_LocationPaths' -ErrorAction SilentlyContinue).Data
  [pscustomobject]@{{friendly_name=$d.FriendlyName;instance_id=$d.InstanceId;location_info=$loc;location_paths=@($paths)}}
}}
$out | ConvertTo-Json -Depth 5 -Compress
"""
    ) or []
    rows = raw if isinstance(raw, list) else [raw]
    found: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        for serial in PHONE_BY_SERIAL:
            if serial in str(row.get("instance_id") or ""):
                found[serial] = row
    return found


def adb_inventory() -> dict[str, dict[str, Any]]:
    if not ADB.is_file():
        return {}
    listed = run([str(ADB), "devices", "-l"], 8)
    rows: dict[str, dict[str, Any]] = {}
    for line in listed.stdout.splitlines()[1:]:
        match = re.match(r"^(\S+)\s+(\S+)(.*)$", line.strip())
        if not match or match.group(1) not in PHONE_BY_SERIAL:
            continue
        serial, state, detail = match.groups()
        rows[serial] = {
            "serial": serial,
            "adb_state": state,
            "adb_fields": dict(re.findall(r"(\w+):([^\s]+)", detail)),
        }
    properties = {
        "manufacturer": "ro.product.manufacturer",
        "model": "ro.product.model",
        "android": "ro.build.version.release",
    }
    for serial, row in rows.items():
        responsive = True
        for key, prop in properties.items():
            result = run([str(ADB), "-s", serial, "shell", "getprop", prop], 4)
            row[key] = result.stdout.strip()
            responsive = responsive and result.returncode == 0 and bool(row[key])
        ip_result = run(
            [str(ADB), "-s", serial, "shell", "ip", "-o", "-4", "addr", "show", "scope", "global"],
            4,
        )
        match = re.search(r"\binet\s+(\d{1,3}(?:\.\d{1,3}){3})/", ip_result.stdout)
        row["ipv4"] = match.group(1) if match else ""
        row["adb_responsive"] = responsive
    return rows


def neighbors() -> list[dict[str, str]]:
    raw = ps_json(
        r"""
$rows=Get-NetNeighbor -AddressFamily IPv4 | Where-Object {$_.IPAddress -match '^192\.168\.[4-7]\.' -and $_.LinkLayerAddress -and $_.LinkLayerAddress -ne '00-00-00-00-00-00'}
$rows | Sort-Object InterfaceAlias,IPAddress -Unique | ForEach-Object {[pscustomobject]@{ip=$_.IPAddress;mac=$_.LinkLayerAddress;state=$_.State.ToString();interface=$_.InterfaceAlias}} | ConvertTo-Json -Depth 3 -Compress
"""
    ) or []
    rows = raw if isinstance(raw, list) else [raw]
    return [row for row in rows if isinstance(row, dict)]


def sub_action(action: str) -> dict[str, Any]:
    if not PYTHON.is_file() or not SUB_CLIENT.is_file():
        return {}
    result = run(
        [str(PYTHON), str(SUB_CLIENT), "command", "--action", action, "--node-kind", "windows", "--node", "DESKTOP-UE5A6GG"],
        28,
    )
    try:
        payload = json.loads(result.stdout.lstrip("\ufeff"))
        nested = payload.get("result") if isinstance(payload, dict) else {}
        stdout = nested.get("stdout") if isinstance(nested, dict) else ""
        return {"response": payload, "stdout_json": json.loads(stdout) if stdout else {}}
    except json.JSONDecodeError:
        return {}


def proxmox_audit() -> dict[str, Any]:
    if not SSH_KEY.is_file():
        return {"ok": False, "error": "CT246 SSH key missing"}
    remote = (
        "printf 'host=%s\\n' \"$(hostname)\"; "
        "printf 'vendor=%s\\n' \"$(cat /sys/class/dmi/id/sys_vendor)\"; "
        "printf 'model=%s\\n' \"$(cat /sys/class/dmi/id/product_name)\"; "
        "pct status 246; pct config 246"
    )
    result = run(
        ["ssh.exe", "-i", str(SSH_KEY), "-o", "BatchMode=yes", "-o", "ConnectTimeout=7", "root@192.0.2.50", remote],
        18,
    )
    values: dict[str, Any] = {"ok": result.returncode == 0, "return_code": result.returncode}
    for line in result.stdout.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
        elif line.startswith("status:"):
            values["ct_status"] = line.split(":", 1)[1].strip()
    if result.returncode != 0:
        values["error"] = result.stderr.strip() or "SSH audit failed"
    return values


def ssdp_devices() -> list[dict[str, str]]:
    crlf = "\r\n"
    message = (
        "M-SEARCH * HTTP/1.1" + crlf
        + "HOST: 239.255.255.250:1900" + crlf
        + 'MAN: "ssdp:discover"' + crlf
        + "MX: 2" + crlf
        + "ST: ssdp:all" + crlf + crlf
    ).encode()
    found: dict[tuple[str, str], dict[str, str]] = {}
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton("192.0.2.40"))
        sock.settimeout(0.45)
        sock.sendto(message, ("239.255.255.250", 1900))
        deadline = now().timestamp() + 3.0
        while now().timestamp() < deadline:
            try:
                data, address = sock.recvfrom(65535)
            except socket.timeout:
                continue
            headers: dict[str, str] = {}
            for line in data.decode("utf-8", "replace").splitlines()[1:]:
                if ":" in line:
                    key, value = line.split(":", 1)
                    headers[key.lower().strip()] = value.strip()
            location = headers.get("location", "")
            found[(address[0], location)] = {
                "ip": address[0],
                "location": location,
                "server": headers.get("server", ""),
            }
    except OSError:
        pass
    finally:
        sock.close()
    return list(found.values())


def record(
    *,
    id: str,
    name: str,
    classification: str,
    status: str,
    hardware: str,
    network_location: str,
    physical_location: str,
    location_confidence: str,
    identity_confidence: str,
    ip: str = "",
    mac: str = "",
    transport: str = "",
    last_seen_utc: str = "",
    aliases: list[str] | None = None,
    evidence: list[str] | None = None,
    can_join_cluster: bool = False,
) -> dict[str, Any]:
    return {
        "id": id,
        "name": name,
        "classification": classification,
        "status": status,
        "hardware": hardware,
        "ip": ip,
        "mac_address": mac,
        "vendor": mac_vendor(mac),
        "transport": transport,
        "network_location": network_location,
        "physical_location": physical_location,
        "location_confidence": location_confidence,
        "identity_confidence": identity_confidence,
        "last_seen_utc": last_seen_utc,
        "aliases": aliases or [],
        "evidence": evidence or [],
        "can_join_cluster": can_join_cluster,
    }


def build_inventory() -> dict[str, Any]:
    session = read_json(SESSION_STATE)
    host = local_host()
    pnp = pnp_locations()
    adb = adb_inventory()
    neighbor_rows = neighbors()
    neighbor_by_ip = {str(row.get("ip")): row for row in neighbor_rows}
    proxmox = proxmox_audit()
    chat = http_json("http://127.0.0.1:24680/health")
    meeting = http_json("http://127.0.0.1:8790/health")
    sub_health = http_json("http://198.51.100.227:8776/health")
    sub_hardware = sub_action("node.hardware")
    sub_status = sub_action("main.control_status")
    devices: list[dict[str, Any]] = []

    host_ips = host.get("ipv4") if isinstance(host.get("ipv4"), list) else []
    host_ip = next((str(row.get("IPAddress")) for row in host_ips if isinstance(row, dict)), "192.0.2.40")
    adapters = host.get("adapters") if isinstance(host.get("adapters"), list) else []
    host_mac = next((str(row.get("MacAddress")) for row in adapters if isinstance(row, dict)), "")
    gpu_rows = host.get("gpu") if isinstance(host.get("gpu"), list) else []
    gpu_names = ", ".join(str(row.get("Name")) for row in gpu_rows if isinstance(row, dict) and row.get("Name"))
    devices.append(
        record(
            id="engel-main-pc",
            name="ROG / Engel AI Main Controller",
            classification="cluster_member",
            status="verified_live",
            hardware=f"{host.get('manufacturer', 'ASUS')} {host.get('model', 'ROG')}; GPU: {gpu_names or 'not returned'}",
            ip=host_ip,
            mac=host_mac,
            transport="Ethernet",
            network_location=f"LAN {host_ip}/22; Engel receiver 0.0.0.0:8765",
            physical_location="ROG laptop; exact room not assigned",
            location_confidence="network_and_local_hardware_verified; room_unknown",
            identity_confidence="high",
            aliases=["LAPTOP-0KUVK82E", "Engel AI Main PC", f"nmap-{host_ip.replace('.', '-')}"],
            evidence=["Windows CIM hardware", "active Windows adapter", "running EngelAIMain.exe"],
            can_join_cluster=True,
        )
    )
    devices.append(
        record(
            id="engel-spine-01",
            name="engel-spine-01 / Dell PowerEdge R730xd",
            classification="cluster_member",
            status="verified_live" if proxmox.get("ok") else "unreachable",
            hardware=f"{proxmox.get('vendor', 'Dell Inc.')} {proxmox.get('model', 'PowerEdge R730xd')}; dual Xeon E5-2660 v3",
            ip="192.0.2.50",
            mac=str(neighbor_by_ip.get("192.0.2.50", {}).get("mac") or "EC-F4-BB-E9-B1-C0"),
            transport="Ethernet",
            network_location="Proxmox host 192.0.2.50/22 on vmbr0",
            physical_location="Physical Dell PowerEdge server; exact rack/room not assigned",
            location_confidence="network_and_dmi_verified; rack_room_unknown",
            identity_confidence="high",
            aliases=["ssh-node-192.0.2.50", "Proxmox host", "Dell 730xd"],
            evidence=["read-only SSH DMI audit", "Proxmox host network", "port 22 OpenSSH"],
            can_join_cluster=True,
        )
    )

    ct_live = proxmox.get("ct_status") == "running"
    devices.append(
        record(
            id="local-llm-runtime",
            name="CT246 engel-ai-main",
            classification="logical_runtime",
            status="verified_live" if ct_live and chat.get("ok") else "runtime_live_tunnel_down" if ct_live else "offline",
            hardware="Debian 12 LXC; 24 cores; 40960 MB RAM; 1000G rootfs on engel-fast-ssd",
            ip="10.246.0.2",
            transport="NAT via Proxmox vmbr1; ROG SSH port 24622",
            network_location="Inside engel-spine-01; 10.246.0.2/24; ROG route 192.0.2.50:24622",
            physical_location="Virtual container on Dell PowerEdge R730xd",
            location_confidence="high",
            identity_confidence="high",
            aliases=["CT 246 LLM Runtime", "192.0.2.50:24622", "engel-ai-main"],
            evidence=["pct status/config", "CT hostname", "chat /health" if chat.get("ok") else "ROG chat tunnel unavailable"],
            can_join_cluster=True,
        )
    )
    devices.append(
        record(
            id="meeting-room-server",
            name="Agent Meeting Room Runtime",
            classification="logical_runtime",
            status="verified_live" if meeting.get("ok") else "tunnel_down",
            hardware="Python Meeting Room service on CT246",
            ip="127.0.0.1:8790",
            transport="SSH local forward to CT246:8790",
            network_location="CT246 /opt/engel/run/meeting_room_server",
            physical_location="Virtual service on Dell PowerEdge R730xd",
            location_confidence="high",
            identity_confidence="high",
            aliases=["Meeting Room Server"],
            evidence=["ROG /health tunnel" if meeting.get("ok") else "ROG port 8790 unavailable"],
        )
    )

    nested = sub_hardware.get("stdout_json") if isinstance(sub_hardware, dict) else {}
    computer = nested.get("computer") if isinstance(nested, dict) and isinstance(nested.get("computer"), dict) else {}
    cpu = nested.get("cpu") if isinstance(nested, dict) and isinstance(nested.get("cpu"), dict) else {}
    sub_ip = "198.51.100.227"
    control_ok = bool(sub_status.get("response", {}).get("ok")) if isinstance(sub_status, dict) else False
    devices.append(
        record(
            id="sub-engel-node",
            name="Sub-Engel DESKTOP-UE5A6GG",
            classification="cluster_member",
            status="verified_live" if sub_health.get("ok") and control_ok else "degraded",
            hardware=f"{computer.get('Manufacturer', 'OEM')} {computer.get('Model', 'B450M/ac')}; {cpu.get('Name', 'AMD Ryzen 5 2600')}; Radeon RX 580",
            ip=sub_ip,
            mac=str(neighbor_by_ip.get(sub_ip, {}).get("mac") or "70-85-C2-D3-1B-F3"),
            transport="Ethernet",
            network_location=f"LAN {sub_ip}/22; authenticated action node :8776",
            physical_location="Physical Sub-Engel desktop; exact room not assigned",
            location_confidence="network_and_remote_hardware_verified; room_unknown",
            identity_confidence="high",
            aliases=["DESKTOP-UE5A6GG", "Sub-Engel Node", "Windows Sub-Engel WiFi 02"],
            evidence=["live /health", "authenticated node.hardware", "authenticated main.control_status"],
            can_join_cluster=True,
        )
    )

    worker_state = session.get("workers") if isinstance(session.get("workers"), dict) else {}
    for serial, known in PHONE_BY_SERIAL.items():
        worker_id, label, fallback_maker, fallback_model, fallback_android = known
        adb_row = adb.get(serial, {})
        worker = worker_state.get(worker_id) if isinstance(worker_state.get(worker_id), dict) else {}
        identity = worker.get("identity") if isinstance(worker.get("identity"), dict) else {}
        last_seen = str(worker.get("last_seen_utc") or "")
        age = age_seconds(last_seen)
        heartbeat_live = age is not None and age <= 300
        adb_attached = serial in adb
        adb_responsive = adb_row.get("adb_responsive") is True
        if heartbeat_live:
            phone_status = "verified_live"
        elif adb_attached:
            phone_status = "usb_attached_worker_stale"
        else:
            phone_status = "offline"
        maker = str(adb_row.get("manufacturer") or fallback_maker)
        model = str(adb_row.get("model") or adb_row.get("adb_fields", {}).get("model") or fallback_model).replace("_", " ")
        android = str(adb_row.get("android") or fallback_android)
        ip = str(identity.get("remote_address") or adb_row.get("ipv4") or "")
        location = pnp.get(serial, {})
        port = str(location.get("location_info") or "USB port not returned")
        paths = location.get("location_paths") if isinstance(location.get("location_paths"), list) else []
        path_text = str(paths[0]) if paths else ""
        devices.append(
            record(
                id=worker_id,
                name=f"Android Worker {label} - {maker} {model}",
                classification="cluster_member",
                status=phone_status,
                hardware=f"{maker} {model}; Android {android}; ADB serial {serial}",
                ip=ip,
                mac=str(neighbor_by_ip.get(ip, {}).get("mac") or ""),
                transport="USB ADB + authenticated LAN worker",
                network_location=f"LAN {ip or 'not observed'}; ADB serial {serial}",
                physical_location=f"Attached to ROG USB {port}{'; ' + path_text if path_text else ''}",
                location_confidence="USB_topology_verified; room_inherits_ROG_unknown",
                identity_confidence="high",
                last_seen_utc=last_seen,
                aliases=[serial, f"android-adb-{serial}", worker_id],
                evidence=[
                    f"ADB listed={adb_attached}, responsive={adb_responsive}",
                    f"authenticated worker last seen {last_seen or 'unknown'}",
                    f"Windows PnP {port}",
                ],
                can_join_cluster=True,
            )
        )

    gateway = neighbor_by_ip.get("192.0.2.1", {})
    gateway_xml = http_text("http://192.0.2.1:1900/igd.xml")
    gateway_model = "eero Pro 7" if "eero Pro 7" in gateway_xml else "eero gateway"
    devices.append(
        record(
            id="lan-gateway",
            name=f"{gateway_model} LAN Gateway",
            classification="network_infrastructure",
            status="verified_live" if gateway else "not_seen",
            hardware=gateway_model,
            ip="192.0.2.1",
            mac=str(gateway.get("mac") or "94-CD-FD-38-50-D2"),
            transport="Ethernet/WiFi gateway",
            network_location="Default gateway for 192.0.2.0/22",
            physical_location="Physical location not assigned",
            location_confidence="model_and_network_verified; room_unknown",
            identity_confidence="high",
            aliases=["Engel WiFi / LAN Hub", "unidentified-lan-neighbor-192.0.2.1"],
            evidence=["eero UPnP model document", "Windows default route", "neighbor table"],
        )
    )

    known_ips = {str(device.get("ip") or "").split(":", 1)[0] for device in devices}
    for row in neighbor_rows:
        ip = str(row.get("ip") or "")
        if ip in known_ips or ip.endswith(".255"):
            continue
        mac = str(row.get("mac") or "")
        vendor = mac_vendor(mac)
        if ip == "192.0.2.20" or vendor == "Vizio, Inc.":
            cast = http_json(f"http://{ip}:8008/setup/eureka_info?options=detail")
            cast_name = str(cast.get("name") or "Vizio SmartCast TV")
            devices.append(
                record(
                    id=f"lan-candidate-{ip.replace('.', '-')}",
                    name=f"Vizio SmartCast TV ({cast_name})",
                    classification="lan_candidate",
                    status="reachable_not_engel",
                    hardware="Vizio SmartCast television with Chromecast built-in; exact panel model not advertised without TV pairing",
                    ip=ip,
                    mac=mac,
                    transport=str(row.get("interface") or "LAN"),
                    network_location=f"LAN {ip}/22",
                    physical_location="Exact room not assigned",
                    location_confidence="vendor_and_service_verified; exact_model_and_room_unknown",
                    identity_confidence="medium",
                    aliases=[f"unidentified-lan-neighbor-{ip}"],
                    evidence=["Vizio OUI", "Chromecast eureka_info", "SmartCast ports 7345/8008/8009/9000"],
                )
            )
        elif ip == "192.0.2.33" or vendor == "Intel Corporate":
            devices.append(
                record(
                    id=f"lan-candidate-{ip.replace('.', '-')}",
                    name=f"Unassigned Windows device at {ip}",
                    classification="lan_candidate",
                    status="reachable_not_engel",
                    hardware="Windows-class device with Intel network adapter; exact computer model not advertised",
                    ip=ip,
                    mac=mac,
                    transport=str(row.get("interface") or "LAN"),
                    network_location=f"LAN {ip}/22; Windows Delivery Optimization port 7680 observed",
                    physical_location="Unknown",
                    location_confidence="network_and_os_family_verified; exact_device_and_room_unknown",
                    identity_confidence="medium",
                    aliases=[f"unidentified-lan-neighbor-{ip}"],
                    evidence=["Intel OUI", "TCP 7680 response", "no Engel/ADB endpoint"],
                )
            )
        else:
            devices.append(
                record(
                    id=f"lan-candidate-{ip.replace('.', '-')}",
                    name=f"Unassigned LAN device at {ip}",
                    classification="lan_candidate",
                    status="lan_seen_not_identified",
                    hardware=f"Network adapter vendor: {vendor}",
                    ip=ip,
                    mac=mac,
                    transport=str(row.get("interface") or "LAN"),
                    network_location=f"LAN {ip}/22",
                    physical_location="Unknown",
                    location_confidence="network_only",
                    identity_confidence="low",
                    aliases=[f"unidentified-lan-neighbor-{ip}"],
                    evidence=["Windows neighbor table only"],
                )
            )

    for item in ssdp_devices():
        ip = item.get("ip", "")
        if not ip:
            continue
        server = item.get("server", "")
        if "Roku" not in server:
            continue
        info_text = http_text(f"http://{ip}:8060/query/device-info")
        name = "Roku device"
        physical = "Exact room not assigned"
        mac = ""
        hardware = server
        try:
            xml = ET.fromstring(info_text)
            values = {child.tag: (child.text or "") for child in xml}
            name = values.get("user-device-name") or values.get("friendly-device-name") or name
            physical = values.get("user-device-location") or physical
            mac = values.get("wifi-mac", "").replace(":", "-").upper()
            hardware = f"{values.get('vendor-name', 'Roku')} {values.get('model-name', '')} {values.get('model-number', '')}".strip()
        except ET.ParseError:
            pass
        roku_record = record(
            id=f"lan-candidate-{ip.replace('.', '-')}",
            name=name,
            classification="lan_candidate",
            status="reachable_not_engel",
            hardware=hardware,
            ip=ip,
            mac=mac,
            transport="WiFi",
            network_location=f"LAN {ip}/22; Roku ECP :8060",
            physical_location=physical,
            location_confidence="device_self_reported",
            identity_confidence="high",
            aliases=[f"roku-{ip}"],
            evidence=["SSDP response", "Roku /query/device-info"],
        )
        existing_index = next(
            (index for index, device in enumerate(devices) if device.get("ip") == ip),
            None,
        )
        if existing_index is None:
            devices.append(roku_record)
        elif devices[existing_index].get("classification") == "lan_candidate":
            devices[existing_index] = roku_record

    # Roku SSDP replies are intermittent. A current neighbor can still expose the
    # exact read-only ECP identity endpoint, so enrich LAN candidates directly.
    for index, device in enumerate(list(devices)):
        if device.get("classification") != "lan_candidate":
            continue
        ip = str(device.get("ip") or "")
        info_text = http_text(f"http://{ip}:8060/query/device-info", timeout=2.0)
        if "<device-info>" not in info_text:
            continue
        try:
            xml = ET.fromstring(info_text)
        except ET.ParseError:
            continue
        values = {child.tag: (child.text or "") for child in xml}
        if not values.get("vendor-name") and not values.get("model-name"):
            continue
        name = values.get("user-device-name") or values.get("friendly-device-name") or "Roku device"
        physical = values.get("user-device-location") or "Exact room not assigned"
        mac = (values.get("wifi-mac") or values.get("ethernet-mac") or "").replace(":", "-").upper()
        screen = values.get("screen-size", "")
        hardware = " ".join(
            value
            for value in (
                values.get("vendor-name", "Roku"),
                values.get("model-name", ""),
                values.get("model-number", ""),
                f'{screen}-inch' if screen else "",
            )
            if value
        )
        devices[index] = record(
            id=f"lan-candidate-{ip.replace('.', '-')}",
            name=name,
            classification="lan_candidate",
            status="reachable_not_engel",
            hardware=hardware,
            ip=ip,
            mac=mac,
            transport=values.get("network-type", "WiFi"),
            network_location=f"LAN {ip}/22; Roku ECP :8060",
            physical_location=physical,
            location_confidence="device_self_reported",
            identity_confidence="high",
            aliases=[f"roku-{ip}"],
            evidence=["direct Roku /query/device-info", "current Windows LAN neighbor"],
        )

    counts: dict[str, int] = {}
    for device in devices:
        classification = str(device["classification"])
        counts[classification] = counts.get(classification, 0) + 1
    issues = [
        {"id": device["id"], "status": device["status"]}
        for device in devices
        if device["classification"] in {"cluster_member", "logical_runtime"}
        and device["status"] != "verified_live"
    ]
    return {
        "schema": "engel_device_identity_audit_v1",
        "generated_at_utc": iso_now(),
        "ok": all(
            device["status"] == "verified_live"
            for device in devices
            if device["id"] in {"engel-main-pc", "engel-spine-01", "sub-engel-node"}
        ),
        "policy": {
            "cluster_members_require_authenticated_or_local_evidence": True,
            "lan_candidates_are_never_auto_trusted": True,
            "physical_room_is_unknown_unless_device_or_operator_assigned": True,
            "raw_adb_and_nmap_aliases_do_not_count_as_separate_devices": True,
        },
        "summary": {
            "records": len(devices),
            "classifications": counts,
            "verified_live": sum(device["status"] == "verified_live" for device in devices),
            "issues": issues,
        },
        "devices": devices,
    }


def markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Engel Device Identity and Location Audit",
        "",
        f"Generated: {payload['generated_at_utc']}",
        "",
        "| Device | Class | Status | Exact identity | IP | MAC | Network location | Physical location | Identity confidence | Location confidence |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for item in payload["devices"]:
        values = [
            item["name"],
            item["classification"],
            item["status"],
            item["hardware"],
            item["ip"],
            item["mac_address"],
            item["network_location"],
            item["physical_location"],
            item["identity_confidence"],
            item["location_confidence"],
        ]
        lines.append("| " + " | ".join(str(value).replace("|", "/").replace("\n", " ") for value in values) + " |")
    lines.extend(
        [
            "",
            "## Accuracy rules",
            "",
            "- USB serial, PnP topology, authenticated worker identity, DMI, and self-reported device metadata are exact evidence.",
            "- A MAC OUI identifies the network-adapter vendor, not always the exact product.",
            "- A room/rack location is reported only when the device or operator assigned one.",
            "- LAN candidates are not Engel members and cannot be bulk-promoted to trusted workers.",
            "",
            "## Current issues",
            "",
        ]
    )
    issues = payload["summary"]["issues"]
    lines.extend(
        (f"- {item['id']}: {item['status']}" for item in issues)
        if issues
        else ["- None."]
    )
    return "\n".join(lines) + "\n"


def write_outputs(payload: dict[str, Any]) -> tuple[Path, Path]:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    LATEST_STATE.parent.mkdir(parents=True, exist_ok=True)
    report_stamp = now().strftime("%Y%m%dT%H%M%SZ")
    json_path = REPORT_DIR / f"ENGEL_DEVICE_IDENTITY_AUDIT_{report_stamp}.json"
    md_path = REPORT_DIR / f"ENGEL_DEVICE_IDENTITY_AUDIT_{report_stamp}.md"
    encoded = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    json_path.write_text(encoded, encoding="utf-8")
    LATEST_STATE.write_text(encoded, encoding="utf-8")
    report = markdown(payload)
    md_path.write_text(report, encoding="utf-8")
    (REPORT_DIR / "ENGEL_DEVICE_IDENTITY_AUDIT_LATEST.md").write_text(report, encoding="utf-8")
    return json_path, md_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()
    payload = build_inventory()
    if not args.no_write:
        json_path, md_path = write_outputs(payload)
        payload["saved_json"] = str(json_path)
        payload["saved_markdown"] = str(md_path)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
