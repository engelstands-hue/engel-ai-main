#!/usr/bin/env python3
"""Serve a one-command wired bootstrap for a Windows Sub-Engel node."""
from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
AGENT_PATH = ROOT / "engel_windows_sub_node_agent.py"
INSTALL_SCRIPT_PATH = ROOT / "workflows" / "sub_engel_nodes" / "install_windows_sub_engel_node.ps1"
FILE_STRUCTURE_PATH = ROOT / "workflows" / "sub_engel_nodes" / "windows_sub_engel_file_structure.json"
PACKAGE_ZIP_PATH = ROOT / "dist" / "EngelAI-SubEngel-Windows-App-20260621.zip"
READY_DIR = ROOT / "runtime" / "windows_sub_engel_bootstrap"
LATEST_READY = READY_DIR / "latest_node_ready.json"


def ps_script(controller_url: str, controller_ip: str) -> str:
    return f"""$ErrorActionPreference = 'Stop'
$ControllerUrl = '{controller_url.rstrip("/")}'
$ControllerIp = '{controller_ip}'
$Drive = Get-PSDrive -PSProvider FileSystem | Where-Object Name -ne 'C' | Sort-Object Name | Select-Object -First 1
if (-not $Drive) {{
    throw 'No non-C drive found for Engel Windows Sub-Engel setup. C: is OS-only.'
}}
$NodeRoot = Join-Path $Drive.Root 'EngelWindowsSubNode'
$TempRoot = Join-Path $NodeRoot 'temp'
New-Item -ItemType Directory -Force -Path $TempRoot | Out-Null
$env:TEMP = $TempRoot
$env:TMP = $TempRoot
$env:TMPDIR = $TempRoot
$InstallerPath = Join-Path $TempRoot 'engel-windows-subnode-install.ps1'
Write-Host 'Downloading Engel Windows Sub-Engel installer from controller...'
Invoke-WebRequest -UseBasicParsing -Uri ($ControllerUrl + '/install_windows_sub_engel_node.ps1') -OutFile $InstallerPath
Write-Host 'Launching installer and foreground node server.'
powershell -NoProfile -ExecutionPolicy Bypass -File $InstallerPath -ControllerUrl $ControllerUrl -ControllerIp $ControllerIp -NodeRoot $NodeRoot -StartServer
"""


def package_install_script(controller_url: str) -> str:
    return f"""$ErrorActionPreference = 'Stop'
$ControllerUrl = '{controller_url.rstrip("/")}'
$Drive = Get-PSDrive -PSProvider FileSystem | Where-Object Name -ne 'C' | Sort-Object Name | Select-Object -First 1
if (-not $Drive) {{
    throw 'No non-C drive found for Engel AI Sub-Engel package install. C: is OS-only.'
}}
$NodeRoot = Join-Path $Drive.Root 'EngelWindowsSubNode'
$TempRoot = Join-Path $NodeRoot 'temp'
$Downloads = Join-Path $NodeRoot 'downloads'
$ExtractRoot = Join-Path $NodeRoot 'package_extract\\EngelAI-SubEngel-Windows-App-20260621'
New-Item -ItemType Directory -Force -Path $TempRoot,$Downloads | Out-Null
$env:TEMP = $TempRoot
$env:TMP = $TempRoot
$env:TMPDIR = $TempRoot
$ZipPath = Join-Path $Downloads 'EngelAI-SubEngel-Windows-App-20260621.zip'
Write-Host 'Downloading full Engel AI Sub-Engel Windows app package from Main...'
Invoke-WebRequest -UseBasicParsing -Uri ($ControllerUrl + '/sub-engel-package.zip') -OutFile $ZipPath
if (Test-Path -LiteralPath $ExtractRoot) {{
    Remove-Item -LiteralPath $ExtractRoot -Recurse -Force
}}
New-Item -ItemType Directory -Force -Path $ExtractRoot | Out-Null
Write-Host 'Extracting Engel AI Sub-Engel package...'
Expand-Archive -LiteralPath $ZipPath -DestinationPath $ExtractRoot -Force
$Installer = Join-Path $ExtractRoot 'Install_EngelAI_SubEngel.cmd'
if (-not (Test-Path -LiteralPath $Installer)) {{
    throw 'Package installer missing after extract: ' + $Installer
}}
Write-Host 'Running Engel AI Sub-Engel app installer...'
Start-Process -FilePath $Installer -WorkingDirectory $ExtractRoot -Wait
Write-Host 'Engel AI Sub-Engel package install complete.'
"""


class Handler(BaseHTTPRequestHandler):
    controller_url = "http://192.0.2.40:8788"
    controller_ip = "192.0.2.40"
    ready_only = False
    allowed_node_ips: frozenset[str] = frozenset()

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"{self.client_address[0]} - {fmt % args}")

    def send_bytes(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, path: Path, content_type: str) -> None:
        if not path.is_file():
            self.send_json(404, {"ok": False, "error": f"missing file: {path.name}"})
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(path.stat().st_size))
        self.end_headers()
        with path.open("rb") as fh:
            while True:
                chunk = fh.read(1024 * 1024)
                if not chunk:
                    break
                self.wfile.write(chunk)

    def send_json(self, status: int, payload: dict[str, Any]) -> None:
        self.send_bytes(status, json.dumps(payload, indent=2, sort_keys=True).encode("utf-8"), "application/json")

    def do_GET(self) -> None:
        if self.path in {"/", "/health"}:
            self.send_json(
                200,
                {
                    "ok": True,
                    "service": "windows-sub-engel-wired-bootstrap",
                    "mode": "node-ready-receiver" if self.ready_only else "bootstrap",
                    "bind": f"{self.server.server_address[0]}:{self.server.server_address[1]}",
                    "allowed_node_ips": sorted(self.allowed_node_ips),
                    "agent": str(AGENT_PATH),
                    "installer": str(INSTALL_SCRIPT_PATH),
                    "file_structure": str(FILE_STRUCTURE_PATH),
                    "package_zip": str(PACKAGE_ZIP_PATH),
                    "package_zip_exists": PACKAGE_ZIP_PATH.is_file(),
                },
            )
            return
        if self.path == "/ready/latest":
            if LATEST_READY.exists():
                try:
                    latest = json.loads(LATEST_READY.read_text(encoding="utf-8-sig"))
                except (OSError, json.JSONDecodeError):
                    latest = {}
                if isinstance(latest, dict):
                    latest.pop("pairing_code", None)
                    latest.pop("session_token", None)
                    latest["sensitive_pairing_material_exposed"] = False
                    self.send_json(200, latest)
                else:
                    self.send_json(500, {"ok": False, "error": "latest node-ready receipt is invalid"})
            else:
                self.send_json(404, {"ok": False, "error": "no node-ready callback received yet"})
            return
        if self.ready_only:
            self.send_json(404, {"ok": False, "error": "node-ready receiver mode"})
            return
        if self.path == "/engel_windows_sub_node_agent.py":
            self.send_bytes(200, AGENT_PATH.read_bytes(), "text/x-python; charset=utf-8")
            return
        if self.path == "/install_windows_sub_engel_node.ps1":
            self.send_bytes(200, INSTALL_SCRIPT_PATH.read_bytes(), "text/plain; charset=utf-8")
            return
        if self.path in {"/windows_sub_engel_file_structure.json", "/file-structure.json"}:
            self.send_bytes(200, FILE_STRUCTURE_PATH.read_bytes(), "application/json")
            return
        if self.path == "/start.ps1":
            body = ps_script(self.controller_url, self.controller_ip).encode("utf-8")
            self.send_bytes(200, body, "text/plain; charset=utf-8")
            return
        if self.path == "/install-sub-engel-package.ps1":
            body = package_install_script(self.controller_url).encode("utf-8")
            self.send_bytes(200, body, "text/plain; charset=utf-8")
            return
        if self.path in {"/sub-engel-package.zip", "/EngelAI-SubEngel-Windows-App-20260621.zip"}:
            self.send_file(PACKAGE_ZIP_PATH, "application/zip")
            return
        self.send_json(404, {"ok": False, "error": "not found"})

    def do_POST(self) -> None:
        if self.path != "/node-ready":
            self.send_json(404, {"ok": False, "error": "not found"})
            return
        remote_ip = self.client_address[0]
        if self.allowed_node_ips and remote_ip not in self.allowed_node_ips:
            self.send_json(403, {"ok": False, "error": "node source is not allowlisted"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.send_json(400, {"ok": False, "error": "bad content length"})
            return
        if length < 1 or length > 256 * 1024:
            self.send_json(413, {"ok": False, "error": "node-ready body must be 1..262144 bytes"})
            return
        raw = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(raw.decode("utf-8"))
        except Exception as exc:
            self.send_json(400, {"ok": False, "error": str(exc)})
            return
        READY_DIR.mkdir(parents=True, exist_ok=True)
        payload = {"ok": True, "remote_addr": remote_ip, **data}
        temp_path = LATEST_READY.with_suffix(".json.tmp")
        temp_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temp_path.replace(LATEST_READY)
        self.send_json(200, {"ok": True, "stored": str(LATEST_READY)})


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve Windows Sub-Engel wired bootstrap")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8788)
    parser.add_argument("--controller-ip", default="192.0.2.40")
    parser.add_argument(
        "--ready-only",
        action="store_true",
        help="Expose only health, ready/latest, and the node-ready callback receiver.",
    )
    parser.add_argument(
        "--allowed-node-ip",
        action="append",
        default=[],
        help="Accept node-ready callbacks only from this exact source IP; may be repeated.",
    )
    args = parser.parse_args()
    Handler.controller_ip = args.controller_ip
    Handler.controller_url = f"http://{args.controller_ip}:{args.port}"
    Handler.ready_only = bool(args.ready_only)
    Handler.allowed_node_ips = frozenset(str(value).strip() for value in args.allowed_node_ip if str(value).strip())
    READY_DIR.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Windows Sub-Engel wired bootstrap server listening on {args.host}:{args.port}")
    print(f"Mode: {'node-ready-receiver' if args.ready_only else 'bootstrap'}")
    print(f"Target bootstrap URL: http://{args.controller_ip}:{args.port}/start.ps1")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
