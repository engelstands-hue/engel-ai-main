#!/usr/bin/env python3
"""Pair Main Engel AI with the latest Windows Sub-Engel node-ready callback."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
READY_PATH = ROOT / "runtime" / "windows_sub_engel_bootstrap" / "latest_node_ready.json"
REPORT_PATH = ROOT / "reports" / "sub_engel_remote_control" / "latest_windows_pair_result.json"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def utc_stamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def decode_action_stdout(response: dict[str, Any]) -> dict[str, Any]:
    result = response.get("result") if isinstance(response.get("result"), dict) else {}
    stdout = result.get("stdout") if isinstance(result, dict) else ""
    if not isinstance(stdout, str) or not stdout.strip():
        return {}
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        return {"raw_stdout": stdout[:4000]}
    return payload if isinstance(payload, dict) else {"raw_stdout": stdout[:4000]}


def is_drive_backed_node_root(value: Any) -> bool:
    text = str(value or "").replace("/", "\\").lower()
    return "\\my drive\\" in text or text.startswith("g:\\my drive\\") or text.startswith("h:\\my drive\\")


def ready_node_url(ready: dict[str, Any]) -> tuple[str, str]:
    for key in ("url", "remote_addr", "node_ip"):
        raw = str(ready.get(key) or "").strip().rstrip("/")
        if not raw:
            continue
        if "://" in raw:
            parsed = urlparse(raw)
            if parsed.hostname:
                return f"{parsed.scheme or 'http'}://{parsed.hostname}:{parsed.port or 8776}", parsed.hostname
            continue
        if ":" in raw and raw.count(":") == 1:
            host, port = raw.rsplit(":", 1)
            if host.strip() and port.strip().isdigit():
                return f"http://{host.strip()}:{port.strip()}", host.strip()
        return f"http://{raw}:8776", raw
    return "", ""


def main() -> int:
    ready = read_json(READY_PATH)
    if not ready:
        print(f"No node-ready callback found at {READY_PATH}")
        return 1
    url, node_ip = ready_node_url(ready)
    pairing_code = str(ready.get("pairing_code") or "").strip()
    if not node_ip or not pairing_code:
        report = {
            "created_at_utc": utc_stamp(),
            "ready_path": str(READY_PATH),
            "pair_ok": False,
            "missing_node_url": not bool(node_ip),
            "missing_pairing_code": not bool(pairing_code),
            "computer_name": ready.get("computer_name") or ready.get("hostname", ""),
            "node_ip": node_ip,
            "url": url,
            "required_fix": "Generate a fresh Sub-Engel pairing code on the Windows node or restart the node service so it posts a fresh node-ready callback containing pairing_code.",
        }
        write_json(REPORT_PATH, report)
        print(json.dumps(report, indent=2, sort_keys=True))
        return 1
    node_root = ready.get("node_root") or ready.get("file_structure_root") or ""
    if is_drive_backed_node_root(node_root):
        report = {
            "created_at_utc": utc_stamp(),
            "ready_path": str(READY_PATH),
            "pair_ok": False,
            "refused": True,
            "reason": "latest Windows Sub-Engel callback uses a Google Drive-backed node root",
            "node_root": str(node_root),
            "computer_name": ready.get("computer_name", ""),
            "node_ip": node_ip,
            "required_fix": "Start the installed Sub-Engel from a local non-C root such as D:/EngelWindowsSubNode or D:/EngelAI/SubEngel.",
        }
        write_json(REPORT_PATH, report)
        print(json.dumps(report, indent=2, sort_keys=True))
        return 2

    from engel_sub_node_remote_control import pair_node, run_action
    from engel_sub_node_meeting_bridge import record_windows_sub_node_checkin

    pair_result = pair_node(
        url,
        pairing_code,
        controller_name="Engel AI Controller",
        store=True,
        node_kind="windows",
    )
    status_result: dict[str, Any] = {}
    net_result: dict[str, Any] = {}
    checkin_result: dict[str, Any] = {}

    if pair_result.get("ok"):
        status_result = run_action("node.status", node_kind="windows")
        net_result = run_action("net.status", node_kind="windows")
        checkin_payload = {
            "checkin_utc": utc_stamp(),
            "node": decode_action_stdout(status_result),
            "network": {
                "node_ip": node_ip,
                "node_ips": ready.get("node_ips", []),
                "net_status": decode_action_stdout(net_result),
            },
            "bootstrap": {
                "agent_path": ready.get("agent_path", ""),
                "node_root": ready.get("node_root", ""),
                "state_dir": ready.get("state_dir", ""),
                "file_structure_root": ready.get("file_structure_root", ""),
                "file_structure_version": ready.get("file_structure_version", ""),
            },
            "source": "latest windows_sub_engel node-ready callback",
        }
        checkin_result = record_windows_sub_node_checkin(checkin_payload, pair_result.get("session_token_hint", ""))

    report = {
        "created_at_utc": utc_stamp(),
        "ready_path": str(READY_PATH),
        "url": url,
        "node_ip": node_ip,
        "computer_name": ready.get("computer_name", ""),
        "pair_ok": bool(pair_result.get("ok")),
        "pair_result": {k: v for k, v in pair_result.items() if k != "session_token"},
        "status_ok": bool(status_result.get("ok")),
        "net_ok": bool(net_result.get("ok")),
        "checkin_result": checkin_result,
    }
    write_json(REPORT_PATH, report)

    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if pair_result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
