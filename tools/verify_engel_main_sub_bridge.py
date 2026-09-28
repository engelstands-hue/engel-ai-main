#!/usr/bin/env python3
"""Verify the receive-only Engel Main bridge contract for the Dell Sub node."""
from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "tools" / "windows_sub_engel_wired_bootstrap_server.py"
STARTER = ROOT / "scripts" / "Start-EngelMainSubBridge.ps1"
FIREWALL = ROOT / "scripts" / "Install-EngelMainSubBridgeFirewall.ps1"
CONNECT_ALL = ROOT / "scripts" / "Connect-EngelAllDevices.ps1"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    server = SERVER.read_text(encoding="utf-8")
    starter = STARTER.read_text(encoding="utf-8")
    firewall = FIREWALL.read_text(encoding="utf-8")
    connect_all = CONNECT_ALL.read_text(encoding="utf-8")
    watcher = (ROOT / "tools" / "watch_windows_sub_engel_pairing.py").read_text(encoding="utf-8")
    ast.parse(server)
    ast.parse(watcher)

    require('"--ready-only"' in server, "server ready-only flag is missing")
    require('"--allowed-node-ip"' in server, "server source allowlist flag is missing")
    require("node source is not allowlisted" in server, "source-IP rejection is missing")
    require("length > 256 * 1024" in server, "node-ready request bound is missing")
    require("temp_path.replace(LATEST_READY)" in server, "atomic ready receipt write is missing")
    require('latest.pop("pairing_code", None)' in server, "latest-ready endpoint exposes pairing code")
    require('"sensitive_pairing_material_exposed"] = False' in server, "latest-ready redaction proof missing")
    require('"--host", "0.0.0.0"' in starter, "starter does not bind all Main interfaces")
    require('"--ready-only"' in starter, "starter can expose stale bootstrap payloads")
    require('"--allowed-node-ip", $AllowedNodeIp' in starter, "starter does not pass exact Sub allowlist")
    require("watch_windows_sub_engel_pairing.py" in starter, "fresh callback watcher is not started")
    require('"--server-only"' in starter, "pairing watcher is not pinned to server-only mode")
    require("authenticated_direct_http" in watcher, "pair proof is not direct authenticated HTTP")
    require("run_pair_on_ct246" in watcher, "fresh pairing is not delegated to CT246")
    require('CT_ID = "246"' in watcher, "fresh pairing is not pinned to the real Engel CT")
    require("PROOF_HELPER" not in watcher, "Drive-backed proof helper remains active")
    require('RemoteAddress $AllowedNodeIp' in firewall, "firewall is not scoped to the Sub IP")
    require('LocalPort $Port' in firewall, "firewall is not scoped to the Main bridge port")
    require("Start-EngelMainSubBridge.ps1" in connect_all, "Main restart flow does not restore the bridge")
    require("198.51.100.227" in connect_all, "new Dell Sub address is not pinned in restart flow")

    forbidden = ("192.0.2.44", "DESKTOP-FIB17O7", "/mnt/engel-vault", "engel-vault-main")
    active_text = "\n".join((starter, firewall, connect_all, watcher))
    for value in forbidden:
        require(value not in active_text, f"stale/forbidden active reference found: {value}")

    print("PASS: Engel Main Sub bridge is receive-only, IP-scoped, restart-wired, and stale-node free")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
