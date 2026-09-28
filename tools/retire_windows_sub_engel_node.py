#!/usr/bin/env python3
"""Retire one Windows Sub-Engel node without deleting its audit history."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "remote_nodes" / "windows_sub_engel"


def utc_stamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--node-id", required=True)
    args = parser.parse_args()
    node_id = str(args.node_id).strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,90}", node_id):
        raise SystemExit("invalid node id")

    session_path = REGISTRY / "nodes" / node_id / "session.json"
    session = read_json(session_path)
    session.pop("session_token", None)
    session.update({
        "hostname": node_id,
        "selected_for_engel_main": False,
        "disabled_for_engel_main": True,
        "do_not_use_for_engel_ai_main": True,
        "agent_meeting_status": "retired",
        "retired_at_utc": session.get("retired_at_utc") or utc_stamp(),
        "retired_reason": "Owner removed this desktop from Engel AI Main worker routing.",
    })
    write_json(session_path, session)

    manifest_path = REGISTRY / "fleet_manifest.json"
    manifest = read_json(manifest_path)
    nodes = manifest.get("nodes") if isinstance(manifest.get("nodes"), list) else []
    manifest["nodes"] = [
        item for item in nodes
        if not isinstance(item, dict)
        or str(item.get("node_id") or item.get("hostname") or "").strip().lower() != node_id.lower()
    ]
    manifest["last_updated_utc"] = utc_stamp()
    manifest.setdefault("retired_node_ids", [])
    if node_id not in manifest["retired_node_ids"]:
        manifest["retired_node_ids"].append(node_id)
    write_json(manifest_path, manifest)

    print(json.dumps({
        "ok": True,
        "node_id": node_id,
        "session_path": str(session_path),
        "fleet_manifest_path": str(manifest_path),
        "session_token_removed": True,
        "audit_history_deleted": False,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
