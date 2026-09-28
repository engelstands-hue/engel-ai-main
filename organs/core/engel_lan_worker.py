"""Engel LAN Worker — discover and dispatch inference tasks to LAN workers.

Android phones/tablets running llama-server (llama.cpp), Ollama, or
LocalSend are auto-discovered on the local subnet. Inference tasks are
dispatched via HTTP to the best available worker (highest-priority,
lowest queue depth).

Worker ports scanned:
  53317  — LocalSend/Engel LAN device presence
   8080  — llama-server (llama.cpp HTTP API, default port)
  11434  — Ollama (openai-compatible API)

Safety: LAN-only (192.168.x.x / 10.x.x.x / 172.16-31.x.x).
NO_PROVIDER_CALLS, NO_INTERNET, NO_AUTO_DOWNLOAD.
"""
from __future__ import annotations

import json
import socket
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

_APP_ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
_MEMORY_DIR = _APP_ROOT / "memory"
_REGISTRY_FILE = _MEMORY_DIR / "lan_workers.json"

_LLAMA_SERVER_PORT = 8080
_OLLAMA_PORT = 11434
_LOCALSEND_PORT = 53317

_SCAN_TIMEOUT_S = 0.4
_DISPATCH_TIMEOUT_S = 120


def _arp_devices() -> list[dict]:
    """Read the OS ARP cache to find all devices on the local subnet."""
    import subprocess
    import re
    devices: list[dict] = []
    try:
        r = subprocess.run(["arp", "-a"], capture_output=True, text=True, timeout=5)
        # Parse lines like: '  192.0.2.20   3c-9b-d6-4d-c0-d8   dynamic'
        for line in r.stdout.splitlines():
            m = re.match(r"\s+([\d.]+)\s+([\da-fA-F:-]+)\s+(\w+)", line)
            if not m:
                continue
            ip, mac, arp_type = m.group(1), m.group(2), m.group(3)
            if arp_type == "static" or ip.endswith(".255") or ip.startswith("224.") or ip.startswith("239."):
                continue
            # Locally-administered MAC bit set = randomized (Android/iOS privacy)
            first_octet = int(mac.replace("-", ":").split(":")[0], 16)
            is_randomized = bool(first_octet & 0x02)
            devices.append({"ip": ip, "mac": mac, "randomized": is_randomized})
    except Exception:
        pass
    return devices


def _local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def _subnet_prefix(ip: str) -> str:
    """Return '192.168.4' from '192.0.2.40'."""
    return ".".join(ip.split(".")[:3])


def _is_lan_ip(ip: str) -> bool:
    parts = ip.split(".")
    if not parts or not parts[0].isdigit():
        return False
    first = int(parts[0])
    return first in (10, 172, 192)


def _port_open(ip: str, port: int, timeout: float = _SCAN_TIMEOUT_S) -> bool:
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except Exception:
        return False


def _probe_localsend(ip: str) -> dict | None:
    """Try to get device info from LocalSend/Engel LAN v2 info endpoint."""
    import urllib.request
    import urllib.error
    try:
        url = f"http://{ip}:{_LOCALSEND_PORT}/api/engel_lan/v2/info"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=_SCAN_TIMEOUT_S) as resp:
            data = json.loads(resp.read())
            return {"type": "localsend", "alias": data.get("alias", ip), "data": data}
    except Exception:
        pass
    # Try HTTPS
    try:
        import ssl
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        url = f"https://{ip}:{_LOCALSEND_PORT}/api/engel_lan/v2/info"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=_SCAN_TIMEOUT_S, context=ctx) as resp:
            data = json.loads(resp.read())
            return {"type": "localsend", "alias": data.get("alias", ip), "data": data}
    except Exception:
        return None


def _probe_llama_server(ip: str, port: int) -> dict | None:
    """Check if llama-server is running and return model info."""
    import urllib.request
    try:
        url = f"http://{ip}:{port}/health"
        with urllib.request.urlopen(url, timeout=_SCAN_TIMEOUT_S) as resp:
            health = json.loads(resp.read())
            status = health.get("status", "unknown")
            if status not in ("ok", "no slot available"):
                return None
        # Get model info
        model_name = "unknown"
        try:
            with urllib.request.urlopen(f"http://{ip}:{port}/props", timeout=_SCAN_TIMEOUT_S) as r2:
                props = json.loads(r2.read())
                model_name = props.get("default_generation_settings", {}).get("model", "unknown")
        except Exception:
            pass
        return {"type": "llama_server", "alias": f"{ip}:{port}", "model": model_name, "status": status}
    except Exception:
        return None


def _probe_ollama(ip: str) -> dict | None:
    """Check if Ollama is running and list models."""
    import urllib.request
    try:
        with urllib.request.urlopen(f"http://{ip}:{_OLLAMA_PORT}/api/tags", timeout=_SCAN_TIMEOUT_S) as resp:
            data = json.loads(resp.read())
            models = [m.get("name", "?") for m in data.get("models", [])]
            return {"type": "ollama", "alias": f"{ip}:{_OLLAMA_PORT}", "models": models}
    except Exception:
        return None


def _scan_host(ip: str) -> list[dict]:
    """Probe a single host for all known inference/LAN services."""
    found: list[dict] = []
    # LocalSend
    if _port_open(ip, _LOCALSEND_PORT):
        info = _probe_localsend(ip)
        if info:
            info["ip"] = ip
            info["port"] = _LOCALSEND_PORT
            found.append(info)
    # llama-server on 8080
    if _port_open(ip, _LLAMA_SERVER_PORT):
        info = _probe_llama_server(ip, _LLAMA_SERVER_PORT)
        if info:
            info["ip"] = ip
            info["port"] = _LLAMA_SERVER_PORT
            found.append(info)
    # Ollama
    if _port_open(ip, _OLLAMA_PORT):
        info = _probe_ollama(ip)
        if info:
            info["ip"] = ip
            info["port"] = _OLLAMA_PORT
            found.append(info)
    return found


def _full_subnet_scan(prefix: str, max_workers: int = 64) -> list[dict]:
    ips = [f"{prefix}.{i}" for i in range(1, 255)]
    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_scan_host, ip): ip for ip in ips}
        for f in as_completed(futures):
            found = f.result()
            results.extend(found)
    return results


def _load_registry() -> list[dict]:
    if not _REGISTRY_FILE.exists():
        return []
    try:
        return json.loads(_REGISTRY_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save_registry(workers: list[dict]) -> None:
    _MEMORY_DIR.mkdir(exist_ok=True)
    _REGISTRY_FILE.write_text(json.dumps(workers, indent=2), encoding="utf-8")


def render_lan_workers_scan() -> str:
    """Scan the local subnet for inference workers and LocalSend peers.

    Uses ARP cache for instant device discovery, then probes only known
    hosts for inference ports — much faster than a blind subnet sweep.
    Falls back to full subnet scan if ARP table is empty.
    """
    my_ip = _local_ip()
    prefix = _subnet_prefix(my_ip)
    arp_devices = _arp_devices()
    known_ips = [d["ip"] for d in arp_devices if _subnet_prefix(d["ip"]) == prefix]

    lines = [
        "# Engel LAN Worker Scan",
        "",
        f"Local IP:  {my_ip}",
        f"Devices visible on ARP table: {len(known_ips)}",
        f"Probing ports: {_LOCALSEND_PORT} (LocalSend)  {_LLAMA_SERVER_PORT} (llama-server)  {_OLLAMA_PORT} (Ollama)",
        "",
    ]
    if known_ips:
        lines.append(f"Known IPs: {', '.join(sorted(known_ips))}")
        lines.append("")

    t0 = time.time()
    if known_ips:
        # Probe only ARP-known hosts — fast path
        found = []
        with ThreadPoolExecutor(max_workers=len(known_ips)) as pool:
            futures = {pool.submit(_scan_host, ip): ip for ip in known_ips}
            for f in as_completed(futures):
                found.extend(f.result())
    else:
        lines.append(f"ARP table empty — full sweep of {prefix}.1–254")
        found = _full_subnet_scan(prefix)
    elapsed = round(time.time() - t0, 1)

    # Update registry with discovered workers
    registry = _load_registry()
    seen_keys = {f"{w['ip']}:{w['port']}" for w in registry}
    added = 0
    for node in found:
        key = f"{node['ip']}:{node['port']}"
        if key not in seen_keys:
            registry.append({
                "ip": node["ip"],
                "port": node["port"],
                "type": node["type"],
                "alias": node.get("alias", node["ip"]),
                "model": node.get("model") or (node.get("models") or ["?"])[0],
                "last_seen": time.strftime("%Y-%m-%d %H:%M:%S"),
                "enabled": True,
            })
            added += 1
        else:
            # Update last_seen
            for w in registry:
                if f"{w['ip']}:{w['port']}" == key:
                    w["last_seen"] = time.strftime("%Y-%m-%d %H:%M:%S")
    if found:
        _save_registry(registry)

    lines += [
        "",
        f"Scan complete in {elapsed}s.  Found {len(found)} service(s), {added} new.",
        "",
    ]

    if not found:
        lines += [
            "No inference servers found on the network.",
            "",
        ]
        if known_ips:
            lines += [
                f"  {len(known_ips)} device(s) ARE visible on the network but have no",
                "  inference server running yet.",
                "",
                "  On each Android device, choose ONE of these options:",
                "",
                "  Option A — PocketPal AI app (no setup, easiest):",
                "    Install from Play Store: search 'PocketPal AI'",
                "    Load a GGUF model → Settings → Enable API server",
                "    Server runs on port 8080 by default",
                "",
                "  Option B — Termux + pre-built llama-server:",
                "    Install Termux from F-Droid (not Play Store)",
                "    In Termux:",
                "      pkg update && pkg install wget",
                "      # Download pre-built arm64 binary from llama.cpp releases",
                "      wget https://github.com/ggml-org/llama.cpp/releases/latest/download/llama-<ver>-bin-android-arm64.zip",
                "      unzip llama-*.zip",
                "      ./llama-server -m <model.gguf> --host 0.0.0.0 --port 8080 -ngl 0",
                "",
                "  Option C — LocalSend (file transfer, not inference):",
                "    Install LocalSend from Play Store",
                "    Allows file-based task dispatch on port 53317",
                "",
                "  Then run: engel lan workers scan",
            ]
        else:
            lines += [
                "To add a worker manually:",
                "  engel lan workers add 192.0.2.x:8080 AndroidPhone",
            ]
    else:
        lines.append(f"  {'IP:Port':<22} {'Type':<14} {'Alias / Model'}")
        lines.append("  " + "-" * 70)
        for node in sorted(found, key=lambda x: x["ip"]):
            ip_port = f"{node['ip']}:{node['port']}"
            ntype = node["type"]
            if ntype == "llama_server":
                detail = node.get("model", "?")
            elif ntype == "ollama":
                models = node.get("models", [])
                detail = ", ".join(models[:2]) or "no models"
            else:
                detail = node.get("alias", node["ip"])
            lines.append(f"  {ip_port:<22} {ntype:<14} {detail}")

    lines += [
        "",
        "View registry:     engel lan workers status",
        "Dispatch task:     engel lan worker dispatch <prompt>",
    ]
    return "\n".join(lines)


def render_lan_workers_status() -> str:
    """Show registered LAN workers from memory/lan_workers.json."""
    registry = _load_registry()
    my_ip = _local_ip()
    lines = [
        "# Engel LAN Worker Status",
        "",
        f"Local IP: {my_ip}",
        f"Registry: {_REGISTRY_FILE}",
        f"Workers:  {len(registry)}",
        "",
    ]
    if not registry:
        lines += [
            "No workers registered.",
            "",
            "Scan for workers:  engel lan workers scan",
            "Add manually:      engel lan workers add 192.0.2.x:8080 AndroidPhone",
        ]
        return "\n".join(lines)

    lines.append(f"  {'IP:Port':<22} {'Type':<14} {'Model':<28} {'Last Seen':<20} Enabled")
    lines.append("  " + "-" * 95)
    for w in sorted(registry, key=lambda x: x.get("ip", "")):
        ip_port = f"{w['ip']}:{w['port']}"
        wtype = w.get("type", "?")
        model = str(w.get("model", "?"))[:27]
        last_seen = w.get("last_seen", "never")[:19]
        enabled = "YES" if w.get("enabled", True) else "no"
        lines.append(f"  {ip_port:<22} {wtype:<14} {model:<28} {last_seen:<20} {enabled}")

    inference_workers = [w for w in registry if w.get("type") in ("llama_server", "ollama") and w.get("enabled", True)]
    lines += [
        "",
        f"Inference-capable workers: {len(inference_workers)}",
        "",
        "Commands:",
        "  engel lan workers scan              — re-scan subnet",
        "  engel lan workers add <ip:port> <alias>",
        "  engel lan workers remove <ip:port>",
        "  engel lan worker dispatch <prompt>  — send to best available",
    ]
    return "\n".join(lines)


def render_lan_workers_add(payload: str = "") -> str:
    """Manually register a LAN worker. Payload: '<ip:port> <alias> [type]'"""
    parts = payload.strip().split(None, 2)
    if not parts:
        return (
            "# Engel LAN Workers — Add\n\n"
            "Usage: engel lan workers add <ip:port> <alias> [llama_server|ollama]\n"
            "Example: engel lan workers add 192.0.2.55:8080 AndroidPhone llama_server"
        )
    ip_port = parts[0]
    alias = parts[1] if len(parts) > 1 else ip_port
    worker_type = parts[2] if len(parts) > 2 else "llama_server"

    if ":" not in ip_port:
        ip_port = f"{ip_port}:{_LLAMA_SERVER_PORT}"

    ip, port_str = ip_port.rsplit(":", 1)
    try:
        port = int(port_str)
    except ValueError:
        return f"# Engel LAN Workers — Add\n\nInvalid port in: {ip_port}"

    if not _is_lan_ip(ip):
        return f"# Engel LAN Workers — Add\n\nRefused: {ip} is not a private LAN address."

    registry = _load_registry()
    key = f"{ip}:{port}"
    for w in registry:
        if f"{w['ip']}:{w['port']}" == key:
            w["alias"] = alias
            w["type"] = worker_type
            w["last_seen"] = time.strftime("%Y-%m-%d %H:%M:%S")
            w["enabled"] = True
            _save_registry(registry)
            return f"# Engel LAN Workers — Add\n\nUpdated existing worker: {key} ({alias})"

    registry.append({
        "ip": ip, "port": port, "type": worker_type, "alias": alias,
        "model": "unknown", "last_seen": time.strftime("%Y-%m-%d %H:%M:%S"), "enabled": True,
    })
    _save_registry(registry)
    return f"# Engel LAN Workers — Add\n\nRegistered: {key} ({alias}, {worker_type})\n\nTest with: engel lan worker dispatch hello"


def render_lan_workers_remove(payload: str = "") -> str:
    """Remove a worker from the registry. Payload: 'ip:port'"""
    target = payload.strip()
    if not target:
        return "Usage: engel lan workers remove <ip:port>"
    registry = _load_registry()
    before = len(registry)
    registry = [w for w in registry if f"{w['ip']}:{w['port']}" != target]
    if len(registry) == before:
        return f"Worker not found: {target}"
    _save_registry(registry)
    return f"Removed: {target}. Registry now has {len(registry)} worker(s)."


def _dispatch_to_llama_server(ip: str, port: int, prompt: str, max_tokens: int = 128) -> str:
    """Send a completion request to llama-server (/completion endpoint)."""
    import urllib.request
    payload_bytes = json.dumps({
        "prompt": prompt,
        "n_predict": max_tokens,
        "temperature": 0.7,
        "stop": ["\n\n"],
    }).encode()
    req = urllib.request.Request(
        f"http://{ip}:{port}/completion",
        data=payload_bytes,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=_DISPATCH_TIMEOUT_S) as resp:
        data = json.loads(resp.read())
        return data.get("content", "").strip()


def _dispatch_to_ollama(ip: str, prompt: str, model: str = "llama3") -> str:
    """Send a completion request to Ollama (/api/generate endpoint)."""
    import urllib.request
    payload_bytes = json.dumps({
        "model": model, "prompt": prompt, "stream": False,
    }).encode()
    req = urllib.request.Request(
        f"http://{ip}:{_OLLAMA_PORT}/api/generate",
        data=payload_bytes,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=_DISPATCH_TIMEOUT_S) as resp:
        data = json.loads(resp.read())
        return data.get("response", "").strip()


def render_lan_worker_dispatch(payload: str = "") -> str:
    """Dispatch an inference prompt to the best available LAN worker.

    Payload: the prompt to run.
    Selects the first enabled inference worker (llama_server or ollama).
    """
    prompt = payload.strip()
    if not prompt:
        return (
            "# Engel LAN Worker Dispatch\n\n"
            "Usage: engel lan worker dispatch <prompt>\n"
            "Example: engel lan worker dispatch 'what is the capital of France?'"
        )

    registry = _load_registry()
    workers = [w for w in registry if w.get("type") in ("llama_server", "ollama") and w.get("enabled", True)]

    if not workers:
        return (
            "# Engel LAN Worker Dispatch\n\n"
            "No inference workers registered.\n\n"
            "Scan first:  engel lan workers scan\n"
            "Add one:     engel lan workers add 192.0.2.x:8080 AndroidPhone"
        )

    lines = ["# Engel LAN Worker Dispatch", ""]
    t0 = time.time()

    for w in workers:
        ip, port, wtype = w["ip"], w["port"], w["type"]
        alias = w.get("alias", ip)
        lines += [f"Worker: {alias}  ({ip}:{port}  {wtype})", f"Prompt: {prompt[:80]}", ""]
        try:
            if wtype == "llama_server":
                result = _dispatch_to_llama_server(ip, port, prompt)
            else:
                model = w.get("model", "llama3")
                result = _dispatch_to_ollama(ip, prompt, model=model)
            elapsed = round(time.time() - t0, 1)
            lines += [
                f"Response ({elapsed}s):",
                result,
                "",
                "Dispatch successful.",
            ]
            # Update last_seen in registry
            for reg_w in registry:
                if reg_w["ip"] == ip and reg_w["port"] == port:
                    reg_w["last_seen"] = time.strftime("%Y-%m-%d %H:%M:%S")
            _save_registry(registry)
            return "\n".join(lines)
        except Exception as exc:
            lines += [f"Failed ({wtype}): {exc}", "Trying next worker...", ""]

    lines += ["All workers failed. Re-scan: engel lan workers scan"]
    return "\n".join(lines)


def render_lan_network_devices() -> str:
    """List all devices currently visible on the local network (ARP table).

    Shows IP, MAC, whether MAC is randomized (phone/tablet), and open
    inference ports if any. Does not require any server to be installed.
    """
    my_ip = _local_ip()
    devices = _arp_devices()
    prefix = _subnet_prefix(my_ip)
    local_devices = [d for d in devices if _subnet_prefix(d["ip"]) == prefix]

    lines = [
        "# Engel LAN — Network Devices",
        "",
        f"Local IP:   {my_ip}",
        f"Subnet:     {prefix}.x",
        f"Devices:    {len(local_devices)} visible in ARP table",
        "",
    ]

    if not local_devices:
        lines += ["No devices found in ARP table. They may not have communicated recently."]
        return "\n".join(lines)

    # Quick port check on inference ports only
    inference_ports = [_LLAMA_SERVER_PORT, _OLLAMA_PORT, _LOCALSEND_PORT]

    def check_ports(ip: str) -> tuple[str, list[int]]:
        open_p = []
        for p in inference_ports:
            if _port_open(ip, p, timeout=0.3):
                open_p.append(p)
        return ip, open_p

    with ThreadPoolExecutor(max_workers=len(local_devices)) as pool:
        port_results = dict(pool.map(lambda d: check_ports(d["ip"]), local_devices))

    lines += [
        f"  {'IP':<18} {'MAC':<20} {'Type':<12} {'Open Inference Ports'}",
        "  " + "-" * 75,
    ]
    for d in sorted(local_devices, key=lambda x: [int(p) for p in x["ip"].split(".")]):
        ip = d["ip"]
        mac = d["mac"]
        device_type = "phone/tablet" if d["randomized"] else "fixed device"
        open_ports = port_results.get(ip, [])
        port_str = ", ".join(
            f"{p}({'llama' if p == _LLAMA_SERVER_PORT else 'ollama' if p == _OLLAMA_PORT else 'localsend'})"
            for p in open_ports
        ) if open_ports else "none"
        lines.append(f"  {ip:<18} {mac:<20} {device_type:<12} {port_str}")

    # Summary
    inference_ready = [ip for ip, ports in port_results.items() if ports]
    phone_count = sum(1 for d in local_devices if d["randomized"])
    lines += [
        "",
        f"Phones/tablets (randomized MAC): {phone_count}",
        f"Inference-ready:                 {len(inference_ready)}",
        "",
    ]
    if inference_ready:
        lines += [
            "Ready to register:",
            *[f"  engel lan workers add {ip}:8080 Device_{ip.split('.')[-1]}" for ip in inference_ready],
        ]
    else:
        lines += [
            "No inference servers running yet.",
            "Install PocketPal AI or llama-server on Android, enable API, then re-scan.",
        ]
    return "\n".join(lines)
