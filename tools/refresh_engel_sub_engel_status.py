#!/usr/bin/env python3
"""Refresh Sub-Engel last-seen from a live probe. Never prints tokens.

Does not flip paired/meeting_ready. Auth stamp only after node.status ok.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SESSION = ROOT / "remote_nodes" / "windows_sub_engel" / "nodes" / "DESKTOP-UE5A6GG" / "session.json"
SESSION_ALIAS = ROOT / "remote_nodes" / "windows_sub_engel" / "session.json"
NODE_URL = "http://198.51.100.227:8776"
NODE_HEALTH = NODE_URL + "/health"


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


def probe_health() -> dict:
    try:
        raw = urlopen(NODE_HEALTH, timeout=5).read().decode("utf-8", "replace")
        data = json.loads(raw)
    except Exception as exc:
        return {"ok": False, "reachable": False, "error": type(exc).__name__}
    if not isinstance(data, dict):
        return {"ok": False, "reachable": True, "error": "health was not an object"}
    return {
        "ok": bool(data.get("ok")),
        "reachable": True,
        "hostname": data.get("hostname"),
        "pairing_required": data.get("pairing_required"),
        "ips": data.get("local_ips") or [],
    }


def stamp(paths: list[Path], **fields) -> None:
    now = utc_now()
    for path in paths:
        data = read_json(path)
        if not data:
            continue
        data["last_seen_utc"] = now
        data["last_health_probe_at_utc"] = now
        data.update(fields)
        write_json(path, data)


def main() -> int:
    health = probe_health()
    paths = [SESSION, SESSION_ALIAS]
    if not health.get("reachable"):
        stamp(paths, live_health_ok=False)
        print(json.dumps({"ok": False, "reachable": False, "error": health.get("error")}, indent=2))
        return 1
    stamp(
        paths,
        live_health_ok=bool(health.get("ok")),
        hostname=health.get("hostname") or "DESKTOP-UE5A6GG",
        url=NODE_URL,
        last_known_ips=health.get("ips") or ["198.51.100.227"],
    )
    auth_ok = False
    try:
        from engel_sub_node_remote_control import decode_action_stdout, run_action

        resp = run_action(
            "node.status",
            node_kind="windows",
            node_id="DESKTOP-UE5A6GG",
            url=NODE_URL,
        )
        decoded = decode_action_stdout(resp) if resp.get("ok") else {}
        auth_ok = bool(resp.get("ok")) and bool(decoded)
        if not isinstance(decoded, dict):
            decoded = {}
        hostname = decoded.get("hostname") or health.get("hostname")
    except Exception:
        hostname = health.get("hostname")
        auth_ok = False
    now = utc_now()
    stamp(
        paths,
        last_auth_probe_at_utc=now,
        last_auth_probe_ok=auth_ok,
        last_auth_error="" if auth_ok else "node.status failed",
        live_health_ok=True,
        hostname=hostname or "DESKTOP-UE5A6GG",
    )
    print(
        json.dumps(
            {
                "ok": bool(health.get("ok") and auth_ok),
                "reachable": True,
                "health_ok": bool(health.get("ok")),
                "auth_ok": auth_ok,
                "hostname": hostname or "DESKTOP-UE5A6GG",
                "url": NODE_URL,
                "paired_left_unchanged": True,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if health.get("ok") and auth_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
