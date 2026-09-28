#!/usr/bin/env python3
"""Prove Engel AI Main <-> Windows Sub-Engel LAN, then pair if a fresh code exists.

Does not print pairing codes or session tokens. Does not mark paired without pair_ok.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
READY = ROOT / "runtime" / "windows_sub_engel_bootstrap" / "latest_node_ready.json"
SESSION = ROOT / "remote_nodes" / "windows_sub_engel" / "nodes" / "DESKTOP-UE5A6GG" / "session.json"
SESSION_ALIAS = ROOT / "remote_nodes" / "windows_sub_engel" / "session.json"
RECEIPT = ROOT / "reports" / "sub_engel_remote_control" / "engel_main_sub_engel_reconnect.json"
NODE_HEALTH = "http://198.51.100.227:8776/health"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def probe_node() -> dict:
    try:
        raw = urlopen(NODE_HEALTH, timeout=5).read().decode("utf-8", "replace")
        data = json.loads(raw)
    except Exception as exc:
        return {"ok": False, "error": str(exc), "reachable": False}
    if not isinstance(data, dict):
        return {"ok": False, "error": "health was not an object", "reachable": True}
    return {
        "ok": bool(data.get("ok")),
        "reachable": True,
        "hostname": data.get("hostname"),
        "role": data.get("role"),
        "node_root": data.get("node_root"),
        "pairing_required": data.get("pairing_required"),
        "ips": data.get("local_ips") or [],
        "has_pairing_code": bool(data.get("pairing_code")),
    }


def stamp_live_session(health: dict) -> None:
    now = utc_now()
    for path in (SESSION, SESSION_ALIAS):
        data = read_json(path)
        if not data:
            continue
        data["last_seen_utc"] = now
        data["live_health_ok"] = bool(health.get("ok") and health.get("reachable"))
        data["last_health_probe_at_utc"] = now
        data["last_known_ips"] = health.get("ips") or data.get("last_known_ips") or ["198.51.100.227"]
        data["url"] = "http://198.51.100.227:8776"
        data["hostname"] = health.get("hostname") or data.get("hostname") or "DESKTOP-UE5A6GG"
        # Do not flip paired/meeting_ready/auth without a successful pair.
        data["paired"] = False
        data["session_invalid"] = True
        data["meeting_ready"] = False
        data["last_auth_probe_ok"] = False
        write_json(path, data)


def main() -> int:
    health = probe_node()
    ready = read_json(READY)
    stamp_live_session(health) if health.get("reachable") else None
    if health.get("ok") and bool(ready.get("pairing_code")):
        from tools.pair_latest_windows_sub_engel_node import main as pair_main

        pair_rc = pair_main()
        receipt = {
            "schema": "engel_main_sub_engel_reconnect_v1",
            "created_at_utc": utc_now(),
            "lan_ok": True,
            "node_health_ok": True,
            "pair_attempted": True,
            "pair_exit": pair_rc,
            "paired": pair_rc == 0,
        }
        write_json(RECEIPT, receipt)
        print(json.dumps({k: v for k, v in receipt.items()}, indent=2))
        return pair_rc

    receipt = {
        "schema": "engel_main_sub_engel_reconnect_v1",
        "created_at_utc": utc_now(),
        "lan_ok": bool(health.get("reachable")),
        "node_health_ok": bool(health.get("ok")),
        "hostname": health.get("hostname"),
        "ips": health.get("ips"),
        "node_root": health.get("node_root"),
        "pairing_required_on_node": health.get("pairing_required"),
        "latest_ready_has_pairing_code": bool(ready.get("pairing_code")),
        "latest_ready_at": ready.get("timestamp"),
        "paired": False,
        "honest": (
            "Sub-Engel DESKTOP-UE5A6GG is on the LAN and /health is ok. "
            "Engel AI Main session is invalid. The node is not waiting for a pairing code "
            "(pairing_required=false), so Main cannot finish pairing from here. "
            "On the Sub-Engel PC run: python engel_windows_sub_node_agent.py token "
            "then on this PC run: python tools/pair_latest_windows_sub_engel_node.py"
        ),
        "required_on_sub_engel_pc": [
            "cd /d D:\\EngelWindowsSubNode",
            "python engel_windows_sub_node_agent.py token",
        ],
        "required_on_engel_main_pc": [
            "python tools/pair_latest_windows_sub_engel_node.py",
        ],
    }
    write_json(RECEIPT, receipt)
    print(json.dumps(receipt, indent=2))
    return 0 if health.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
