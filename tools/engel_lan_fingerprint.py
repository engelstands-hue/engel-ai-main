#!/usr/bin/env python3
"""Complete LAN device fingerprint engine for Engel AI Main.

Goal (operator, 2026-07-30): identify EVERY device on the home LAN completely, so
nothing sits as an "Unassigned LAN device". The old audit knew 5 MAC vendors, did
passive ARP only, and hard-probed just Vizio/Roku/eero. This engine fuses every
practical fingerprint signal per host into one identity record.

Where it runs and why: the ROG laptop (192.0.2.40) is the ONLY vantage on the
192.168.4/5.x home LAN — CT246 is a NAT'd container on 10.246.0.2 and cannot see
it. So every probe here is ROG-Windows-native or pure-Python; nothing depends on
CT. Bundled nmap 7.92 and its OUI table live under runtime\\nmap; nbtstat is a
Windows built-in. No npcap and no admin, so raw scans (-O, -sU) are out — but
-Pn -sT -sV -sC and every pure-socket probe run fine unprivileged.

Signals fused per device:
  * MAC + OUI vendor        nmap-mac-prefixes (30k) + curated overlay + LA-bit
  * reverse DNS (PTR)       socket.gethostbyaddr (in-process, window-free)
  * NetBIOS name            nbtstat -A (CREATE_NO_WINDOW)
  * mDNS / Bonjour          raw UDP 5353 query (no zeroconf needed)
  * SSDP / UPnP             M-SEARCH + fetch the LOCATION device-description XML
  * open TCP ports          pure-socket connect scan of a curated port list
  * HTTP banner + <title>   urllib on open web ports
  * TLS certificate CN/SAN  ssl on 443
  * vendor self-report      Chromecast eureka_info, Roku ECP, Vizio SmartCast

Honest-unknown is a hard rule (this codebase forbids invented facts): every
asserted field carries an evidence entry, an OUI is never promoted to a product
model, and a device with no discriminating signal stays device_type='unknown' /
identification_level='UNKNOWN' rather than getting a plausible guess.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
import socket
import ssl
import struct
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
NMAP_EXE = ROOT / "runtime" / "nmap" / "portable" / "nmap-7.92" / "nmap.exe"
OUI_DB = ROOT / "runtime" / "nmap" / "portable" / "nmap-7.92" / "nmap-mac-prefixes"
REPORT_DIR = ROOT / "reports" / "device_audits"
LATEST = ROOT / "runtime" / "device_swarm" / "device_lan_fingerprint_latest.json"

# The nmap OUI table predates some recent registrations; a tiny curated overlay
# covers vendors we have positively confirmed on this LAN that the 7.92 DB misses.
OUI_OVERLAY = {
    "94CDFD": "eero inc.",
    "E4C767": "Intel Corporate",  # real MA-L the bundled 2021 nmap DB omits
}

# Curated deep-probe port list — services that actually identify home devices.
PROBE_PORTS = [
    21, 22, 23, 53, 80, 139, 443, 445, 515, 631, 1400, 1883, 2049, 3074, 3260,
    3389, 5000, 5001, 7000, 7345, 7680, 8008, 8009, 8060, 8080, 8443, 9000, 9100,
]
WEB_PORTS = [80, 443, 8008, 8060, 8080, 8443, 5000, 631]

_MAC_RE = re.compile(r"[0-9A-Fa-f]{2}([-:]?)(?:[0-9A-Fa-f]{2}\1){4}[0-9A-Fa-f]{2}")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _run(cmd: list[str], timeout: int = 12) -> str:
    try:
        completed = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout, check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return completed.stdout or ""
    except Exception:
        return ""


# --------------------------------------------------------------------------- #
# OUI resolution
# --------------------------------------------------------------------------- #
_OUI_CACHE: dict[str, str] = {}


def _load_oui() -> dict[str, str]:
    if _OUI_CACHE:
        return _OUI_CACHE
    _OUI_CACHE.update(OUI_OVERLAY)
    try:
        for line in OUI_DB.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(None, 1)
            if len(parts) == 2 and len(parts[0]) >= 6:
                _OUI_CACHE.setdefault(parts[0].upper(), parts[1].strip())
    except OSError:
        pass
    return _OUI_CACHE


def _norm_mac(mac: str) -> str:
    return re.sub(r"[^0-9A-Fa-f]", "", str(mac or "")).upper()


def mac_vendor(mac: str) -> tuple[str, bool]:
    """Return (vendor, randomized). Honest: randomized MACs and unknown OUIs say so."""
    hexmac = _norm_mac(mac)
    if len(hexmac) < 6:
        return ("", False)
    first_octet = int(hexmac[:2], 16)
    if first_octet & 0b10:  # locally-administered bit -> randomized/private MAC
        return ("Private/randomized MAC", True)
    db = _load_oui()
    # Prefer longer sub-registry prefixes (MA-S /36, MA-M /28) before MA-L /24.
    for width in (9, 7, 6):
        hit = db.get(hexmac[:width])
        if hit:
            return (hit, False)
    aa, bb, cc = hexmac[0:2], hexmac[2:4], hexmac[4:6]
    return (f"Unknown OUI ({aa}:{bb}:{cc})", False)


# --------------------------------------------------------------------------- #
# discovery
# --------------------------------------------------------------------------- #
_BROADCAST_MACS = {"FFFFFFFFFFFF", "000000000000"}


def prime_and_read_neighbors(cidr24: str) -> list[dict[str, str]]:
    """Prime the ARP cache across a /24, then read Get-NetNeighbor. Returns
    [{ip, mac, state}] for real LAN hosts (broadcast/multicast filtered out)."""
    # Prime with nmap's ping sweep when available — seconds vs. ~4 min for 254
    # serial-ish PowerShell pings. Unprivileged -sn does TCP/ICMP host discovery.
    if NMAP_EXE.is_file():
        _run([str(NMAP_EXE), "-sn", "-T4", "--host-timeout", "3s", f"{cidr24}0/24"], timeout=120)
    script = (
        "Get-NetNeighbor -AddressFamily IPv4 | "
        "Where-Object { $_.IPAddress -match '^192\\.168\\.[4-7]\\.' -and $_.LinkLayerAddress "
        "-and $_.LinkLayerAddress -ne '00-00-00-00-00-00' } | "
        "Sort-Object IPAddress -Unique | "
        "ForEach-Object { [pscustomobject]@{ip=$_.IPAddress; mac=$_.LinkLayerAddress; "
        "state=$_.State.ToString()} } | ConvertTo-Json -Depth 3 -Compress"
    )
    raw = _run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script], timeout=30
    ).strip()
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return []
    rows = parsed if isinstance(parsed, list) else [parsed]
    devices: list[dict[str, str]] = []
    for r in rows:
        if not isinstance(r, dict) or not r.get("ip"):
            continue
        ip = str(r["ip"])
        # Drop L2/L3 broadcast + IPv4 multicast (224-239.x) — not devices.
        if ip.endswith(".255") or _norm_mac(r.get("mac", "")) in _BROADCAST_MACS:
            continue
        first = int(ip.split(".", 1)[0]) if ip.split(".")[0].isdigit() else 0
        if 224 <= first <= 239:
            continue
        devices.append(r)
    return devices


# --------------------------------------------------------------------------- #
# per-host signals (all window-free / pure-socket)
# --------------------------------------------------------------------------- #
def reverse_dns(ip: str) -> str:
    try:
        return socket.gethostbyaddr(ip)[0]
    except (OSError, socket.herror):
        return ""


def netbios_name(ip: str) -> dict[str, str]:
    out = _run(["nbtstat", "-A", ip], timeout=5)
    result: dict[str, str] = {}
    for line in out.splitlines():
        m = re.match(r"\s*(\S+)\s+<00>\s+UNIQUE", line)
        if m and "name" not in result:
            result["name"] = m.group(1).strip()
        g = re.match(r"\s*(\S+)\s+<00>\s+GROUP", line)
        if g:
            result["workgroup"] = g.group(1).strip()
    return result


def scan_ports(ip: str, ports: list[int], timeout: float = 0.6) -> list[int]:
    open_ports: list[int] = []

    def probe(port: int) -> int | None:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        try:
            if s.connect_ex((ip, port)) == 0:
                return port
        except OSError:
            return None
        finally:
            s.close()
        return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=32) as pool:
        for result in pool.map(probe, ports):
            if result is not None:
                open_ports.append(result)
    return sorted(open_ports)


def http_banner(ip: str, port: int) -> dict[str, str]:
    scheme = "https" if port in (443, 8443, 8009) else "http"
    url = f"{scheme}://{ip}:{port}/"
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Engel-LAN-Fingerprint"})
        with urllib.request.urlopen(req, timeout=4, context=ctx) as resp:
            server = resp.headers.get("Server", "")
            body = resp.read(4096).decode("utf-8", "replace")
    except Exception as exc:
        server, body = "", ""
        if "401" in str(exc) or "403" in str(exc):
            server = "auth-required"
    out: dict[str, str] = {}
    if server:
        out["server"] = server[:120]
    title = re.search(r"<title[^>]*>(.*?)</title>", body, re.I | re.S)
    if title:
        out["title"] = re.sub(r"\s+", " ", title.group(1)).strip()[:120]
    return out


def tls_cert(ip: str, port: int = 443) -> dict[str, str]:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        with socket.create_connection((ip, port), timeout=4) as raw:
            with ctx.wrap_socket(raw, server_hostname=ip) as tls:
                cert = tls.getpeercert()
    except Exception:
        return {}
    out: dict[str, str] = {}
    if not cert:
        return out
    for tup in cert.get("subject", ()):
        for k, v in tup:
            if k == "commonName":
                out["cert_cn"] = str(v)[:120]
    sans = [v for typ, v in cert.get("subjectAltName", ()) if typ == "DNS"]
    if sans:
        out["cert_san"] = ", ".join(sans[:5])[:160]
    return out


def _udp_query(ip: str, port: int, payload: bytes, timeout: float = 2.5) -> bytes:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(timeout)
    try:
        s.sendto(payload, (ip, port))
        data, _ = s.recvfrom(65535)
        return data
    except OSError:
        return b""
    finally:
        s.close()


def mdns_names(ip: str) -> list[str]:
    """Unicast mDNS query for the host's own name + common service pointers."""
    queries = [
        b"\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00"
        b"\x09_services\x07_dns-sd\x04_udp\x05local\x00\x00\x0c\x00\x01",
    ]
    names: list[str] = []
    for q in queries:
        data = _udp_query(ip, 5353, q, timeout=2.0)
        for m in re.finditer(rb"([\x01-\x3f][\x20-\x7e]{2,62})", data):
            token = m.group(1)[1:].decode("ascii", "replace")
            if token.startswith("_") or token in ("local", "udp", "tcp"):
                continue
            if token not in names and len(token) > 2:
                names.append(token)
    return names[:8]


def ssdp_description(ip: str) -> dict[str, str]:
    msg = (
        "M-SEARCH * HTTP/1.1\r\nHOST: 239.255.255.250:1900\r\n"
        'MAN: "ssdp:discover"\r\nMX: 1\r\nST: ssdp:all\r\n\r\n'
    ).encode()
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(2.5)
    location = ""
    try:
        s.sendto(msg, (ip, 1900))
        data, _ = s.recvfrom(65535)
        for line in data.decode("utf-8", "replace").splitlines():
            if line.lower().startswith("location:"):
                location = line.split(":", 1)[1].strip()
                break
    except OSError:
        return {}
    finally:
        s.close()
    if not location:
        return {}
    out: dict[str, str] = {"upnp_location": location}
    try:
        with urllib.request.urlopen(location, timeout=4) as resp:
            xml = resp.read(8192).decode("utf-8", "replace")
    except Exception:
        return out
    for tag in ("friendlyName", "manufacturer", "modelName", "modelNumber", "deviceType"):
        m = re.search(rf"<{tag}>(.*?)</{tag}>", xml, re.I | re.S)
        if m:
            out[tag] = re.sub(r"\s+", " ", m.group(1)).strip()[:120]
    return out


def vendor_endpoints(ip: str, open_ports: list[int]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if 8008 in open_ports:
        try:
            with urllib.request.urlopen(
                f"http://{ip}:8008/setup/eureka_info?options=detail", timeout=4
            ) as resp:
                info = json.loads(resp.read().decode("utf-8", "replace"))
            cast = {}
            if isinstance(info, dict):
                if info.get("name"):
                    cast["friendly_name"] = str(info["name"])[:80]
                md = info.get("detail", {}) if isinstance(info.get("detail"), dict) else {}
                if md.get("model_name"):
                    cast["model"] = str(md["model_name"])[:80]
                if info.get("cast_build_revision"):
                    cast["build"] = str(info["cast_build_revision"])[:40]
            if cast:
                out["google_cast"] = cast
        except Exception:
            pass
    if 8060 in open_ports:
        try:
            with urllib.request.urlopen(f"http://{ip}:8060/query/device-info", timeout=4) as resp:
                xml = resp.read().decode("utf-8", "replace")
            roku = {}
            for tag in ("user-device-name", "model-name", "model-number", "serial-number"):
                m = re.search(rf"<{tag}>(.*?)</{tag}>", xml, re.I | re.S)
                if m:
                    roku[tag] = m.group(1).strip()[:80]
            if roku:
                out["roku"] = roku
        except Exception:
            pass
    return out


def nmap_services(ip: str, ports: list[int], timeout: int = 90) -> dict[int, dict[str, str]]:
    """Bounded nmap -sV -sC on the already-open ports for product/version banners."""
    if not NMAP_EXE.is_file() or not ports:
        return {}
    port_arg = ",".join(str(p) for p in ports)
    xml = _run(
        [str(NMAP_EXE), "-Pn", "-sT", "-sV", "-sC", "--version-light",
         "--host-timeout", f"{timeout}s", "-p", port_arg, "-oX", "-", ip],
        timeout=timeout + 20,
    )
    services: dict[int, dict[str, str]] = {}
    for block in re.finditer(r'<port protocol="tcp" portid="(\d+)">(.*?)</port>', xml, re.S):
        port = int(block.group(1))
        body = block.group(2)
        svc = re.search(
            r'<service name="([^"]*)"(?:[^>]*?product="([^"]*)")?(?:[^>]*?version="([^"]*)")?',
            body,
        )
        if svc:
            services[port] = {
                "name": svc.group(1) or "",
                "product": (svc.group(2) or "")[:80],
                "version": (svc.group(3) or "")[:40],
            }
    return services


# --------------------------------------------------------------------------- #
# fusion + classification
# --------------------------------------------------------------------------- #
def classify(record: dict[str, Any]) -> tuple[str, str]:
    """Return (device_type, confidence). Only fires on discriminating signals."""
    ports = set(record.get("open_ports") or [])
    services = record.get("services") or {}
    vendor = (record.get("oui_vendor") or "").lower()
    text = " ".join(
        [json.dumps(record.get("vendor_report") or {}), json.dumps(record.get("upnp") or {}),
         " ".join(record.get("mdns_names") or []), str(record.get("hostnames") or [])]
    ).lower()

    if record.get("is_gateway"):
        return ("router/gateway", "high")
    if record.get("vendor_report", {}).get("roku") or {7345, 9000} & ports or \
            record.get("vendor_report", {}).get("google_cast") or {8008, 8009, 8060} & ports:
        return ("TV/streaming", "high")
    if 631 in ports or 9100 in ports or 515 in ports or "_ipp" in text or "printer" in text:
        return ("printer", "high")
    if {445, 139} & ports and ({5000, 5001, 2049, 548} & ports or "synology" in text or "qnap" in text):
        return ("NAS", "medium")
    if 3074 in ports or (9295 <= min(ports, default=0) <= 9309) or "xbox" in text or "playstation" in text:
        return ("game-console", "medium")
    if record.get("adb_serial") or "_companion-link" in text or "android" in text or \
            "_airplay" in text:
        return ("phone", "medium")
    # Randomized MAC with no open ports is the signature of a modern phone/tablet
    # with MAC privacy and a locked-down firewall. Report the CLASS honestly as a
    # low-confidence hint; never assert a vendor or model we could not observe.
    if record.get("mac_randomized") and not ports:
        return ("mobile/personal (randomized MAC)", "low")
    if 7680 in ports or 3389 in ports or record.get("netbios_name") or \
            "windows" in text or "microsoft" in text:
        return ("laptop/PC", "medium")
    if ports and ports <= {80, 443, 1883, 8883, 5683} and \
            any(v in vendor for v in ("espressif", "tuya", "amazon", "nest", "philips")):
        return ("IoT/smart-home", "medium")
    return ("unknown", "low")


def identification_level(record: dict[str, Any]) -> str:
    vendor = record.get("oui_vendor") or ""
    vendor_known = vendor and not vendor.startswith("Unknown OUI") and vendor != "Private/randomized MAC"
    has_model = bool((record.get("model_guess") or {}).get("value"))
    corroborating = sum(
        1 for x in (
            record.get("hostnames"), record.get("netbios_name"), record.get("mdns_names"),
            record.get("open_ports"), record.get("services"), record.get("vendor_report"),
            record.get("upnp"),
        ) if x
    )
    dtype = record.get("device_type", "unknown")
    if (vendor_known or has_model) and dtype != "unknown" and (has_model or corroborating >= 2):
        return "FULLY_IDENTIFIED"
    if vendor_known or dtype != "unknown" or corroborating >= 1:
        return "PARTIAL"
    return "UNKNOWN"


def fingerprint_host(ip: str, mac: str, gateway_ip: str) -> dict[str, Any]:
    vendor, randomized = mac_vendor(mac)
    evidence: list[dict[str, str]] = []

    def note(signal: str, source: str) -> None:
        evidence.append({"signal": signal, "source": source, "observed_at": _now()})

    record: dict[str, Any] = {
        "ip": ip,
        "mac_address": mac,
        "oui_vendor": vendor,
        "mac_randomized": randomized,
        "is_gateway": ip == gateway_ip,
        "hostnames": [],
        "mdns_names": [],
        "netbios_name": "",
        "open_ports": [],
        "services": {},
        "vendor_report": {},
        "upnp": {},
        "model_guess": {"value": None, "basis": "", "verified": False},
    }
    if vendor and not vendor.startswith("Unknown"):
        note("oui", "nmap-mac-prefixes" if not randomized else "la-bit")

    ptr = reverse_dns(ip)
    if ptr:
        record["hostnames"].append(ptr)
        note("reverse_dns", "gethostbyaddr")

    nb = netbios_name(ip)
    if nb.get("name"):
        record["netbios_name"] = nb["name"]
        note("netbios", "nbtstat")
    if nb.get("workgroup"):
        record["workgroup"] = nb["workgroup"]

    mdns = mdns_names(ip)
    if mdns:
        record["mdns_names"] = mdns
        note("mdns", "udp-5353")

    upnp = ssdp_description(ip)
    if upnp:
        record["upnp"] = upnp
        note("ssdp", "upnp-desc")
        if upnp.get("modelName"):
            record["model_guess"] = {
                "value": (upnp.get("manufacturer", "") + " " + upnp["modelName"]).strip(),
                "basis": "UPnP device description", "verified": True,
            }
            note("model", "upnp-desc")

    ports = scan_ports(ip, PROBE_PORTS)
    if ports:
        record["open_ports"] = ports
        note("port_scan", "tcp-connect")

    for wp in [p for p in WEB_PORTS if p in ports]:
        banner = http_banner(ip, wp)
        if banner:
            record.setdefault("web", {})[str(wp)] = banner
            note("http_banner", f"http:{wp}")
    if 443 in ports:
        cert = tls_cert(ip)
        if cert:
            record["tls"] = cert
            note("tls_cert", "tls:443")

    vend = vendor_endpoints(ip, ports)
    if vend:
        record["vendor_report"] = vend
        note("vendor_endpoint", "self-report")
        roku = vend.get("roku") or {}
        cast = vend.get("google_cast") or {}
        if roku.get("model-name"):
            record["model_guess"] = {
                "value": f"Roku {roku['model-name']}", "basis": "Roku ECP device-info", "verified": True,
            }
            note("model", "roku-ecp")
        elif cast.get("model"):
            record["model_guess"] = {
                "value": cast["model"], "basis": "Google Cast eureka_info", "verified": True,
            }
            note("model", "cast-eureka")

    dtype, dconf = classify(record)
    record["device_type"] = dtype
    record["device_type_confidence"] = dconf
    record["identification_level"] = identification_level(record)
    record["evidence"] = evidence
    record["last_seen_utc"] = _now()
    return record


def _deep_enrich(record: dict[str, Any]) -> None:
    services = nmap_services(record["ip"], record.get("open_ports") or [])
    if services:
        record["services"] = {
            str(p): v for p, v in services.items() if v.get("name") or v.get("product")
        }
        record["evidence"].append(
            {"signal": "nmap_sv", "source": "nmap-7.92 -sV -sC", "observed_at": _now()}
        )
        record["identification_level"] = identification_level(record)


def build(cidr24: str, deep: bool) -> dict[str, Any]:
    _load_oui()
    gateway = cidr24 + "1"
    neighbors = prime_and_read_neighbors(cidr24)
    devices: list[dict[str, Any]] = []
    for n in neighbors:
        rec = fingerprint_host(n["ip"], n.get("mac", ""), gateway)
        rec["arp_state"] = n.get("state", "")
        devices.append(rec)
    if deep:
        for rec in devices:
            if rec.get("open_ports"):
                _deep_enrich(rec)
    levels: dict[str, int] = {}
    types: dict[str, int] = {}
    for d in devices:
        levels[d["identification_level"]] = levels.get(d["identification_level"], 0) + 1
        types[d["device_type"]] = types.get(d["device_type"], 0) + 1
    return {
        "schema": "engel_lan_fingerprint_v1",
        "generated_at_utc": _now(),
        "vantage": "ROG 192.0.2.40 (only host on the home LAN; CT246 is off-subnet)",
        "oui_db_entries": len(_load_oui()),
        "cidr_scanned": cidr24 + "0/24",
        "deep_nmap": deep,
        "device_count": len(devices),
        "identification_levels": levels,
        "device_types": types,
        "fully_identified": [
            d["ip"] for d in devices if d["identification_level"] == "FULLY_IDENTIFIED"
        ],
        "still_unknown": [
            d["ip"] for d in devices if d["identification_level"] == "UNKNOWN"
        ],
        "devices": devices,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Engel complete LAN device fingerprint")
    parser.add_argument("--cidr24", default="192.0.2.", help="/24 prefix ending in a dot")
    parser.add_argument("--deep", action="store_true", help="add nmap -sV -sC per host (slower)")
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--ip", default="", help="fingerprint a single IP (skips the sweep)")
    args = parser.parse_args()

    if args.ip:
        _load_oui()
        cidr = args.ip.rsplit(".", 1)[0] + "."
        rec = fingerprint_host(args.ip, "", cidr + "1")
        if args.deep and rec.get("open_ports"):
            _deep_enrich(rec)
        print(json.dumps(rec, indent=2, sort_keys=True, default=str))
        return 0

    payload = build(args.cidr24, args.deep)
    if not args.no_write:
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        LATEST.parent.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        encoded = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        (REPORT_DIR / f"ENGEL_LAN_FINGERPRINT_{stamp}.json").write_text(encoded, encoding="utf-8")
        LATEST.write_text(encoded, encoding="utf-8")
        payload["saved"] = str(LATEST)
    print(json.dumps(
        {k: v for k, v in payload.items() if k != "devices"}, indent=2, sort_keys=True, default=str,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
