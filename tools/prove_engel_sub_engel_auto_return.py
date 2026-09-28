#!/usr/bin/env python3
"""Prove Sub-Engel can auto-return a shared-room work order.

This is a Main-side compatibility proof for live Sub-Engel nodes that still run
the older one-shot action. It writes a normal Agent Meeting Room work order,
keeps the active marker fresh for Drive sync, calls the pair-gated allowlisted
return action, and verifies that a real SUB_ENGEL_SENT_WORK packet appears.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engel_sub_node_meeting_bridge import (
    stage_meeting_packet_for_node,
    write_shared_room_work_order_for_node,
)
from engel_sub_node_remote_control import run_action


REPORT_DIR = ROOT / "reports" / "sub_engel_remote_control"


def utc_stamp() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def decode_remote_stdout(response: dict[str, Any]) -> dict[str, Any]:
    result = response.get("result") if isinstance(response.get("result"), dict) else {}
    stdout = result.get("stdout") if isinstance(result, dict) else ""
    if not isinstance(stdout, str) or not stdout.strip():
        return {}
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def refresh_active_request(work_order: dict[str, Any]) -> bool:
    active_path = Path(str(work_order.get("active_request_path") or ""))
    order_path = Path(str(work_order.get("path") or ""))
    if not active_path:
        return False
    try:
        active_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema": "engel_sub_engel_active_work_request_v1",
            "created_at_utc": utc_stamp(),
            "created_by": "Engel AI Main / auto-return proof",
            "order_id": str(work_order.get("id") or order_path.stem),
            "work_order_name": order_path.name,
            "work_order_path": str(order_path),
            "expected_return_folder": str(work_order.get("expected_return_folder") or ""),
            "target": str(work_order.get("target") or ""),
            "selected_node": work_order.get("selected_node") if isinstance(work_order.get("selected_node"), dict) else {},
            "proof_required": True,
            "auto_return_retry": True,
            "auto_apply": False,
        }
        active_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return True
    except Exception:
        return False


def load_json_file(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def return_matches_node(path: Path, payload: dict[str, Any], node_id: str) -> bool:
    target = str(node_id or "").strip().lower()
    if not target:
        return True
    values = {
        payload.get("hostname", ""),
        payload.get("node_id", ""),
        payload.get("computer_name", ""),
        path.name.split("__", 1)[0] if "__" in path.name else "",
    }
    return target in {str(value).strip().lower() for value in values if str(value or "").strip()}


def wait_for_sub_engel_return(
    order_id: str,
    sent_folder: str,
    timeout_seconds: float,
    node_id: str,
) -> tuple[Path, dict[str, Any]] | None:
    target = str(order_id or "")
    folder = Path(str(sent_folder or ""))
    if not target or not folder.exists():
        return None
    deadline = time.time() + max(0.0, timeout_seconds)
    while True:
        matches: list[tuple[Path, dict[str, Any]]] = []
        try:
            candidates = list(folder.glob(f"*{target}*.json"))
        except OSError:
            candidates = []
        for path in candidates:
            payload = load_json_file(path)
            if (
                isinstance(payload, dict)
                and str(payload.get("order_id") or "") == target
                and return_matches_node(path, payload, node_id)
            ):
                matches.append((path, payload))
        if matches:
            return sorted(matches, key=lambda item: item[0].stat().st_mtime if item[0].exists() else 0)[-1]
        if time.time() >= deadline:
            return None
        time.sleep(1.0)


def run_proof(node_id: str, attempts: int, wait_seconds: float) -> dict[str, Any]:
    station = {
        "name": "Windows Sub-Engel Auto Return Proof",
        "type_label": "Verifier Agent",
        "skill_label": "Verification Skill",
        "equipment": f"Windows Sub-Engel Node {node_id}",
        "bridge": "Windows Sub-Engel Check-in Preview",
    }
    prompt = (
        "AUTO RETURN PROOF: receive this Agent Meeting Room work order, use the "
        "Sub-Engel local helper path or structured fallback, and return a real "
        "SUB_ENGEL_SENT_WORK .done.json packet. Do not apply code or mutate files."
    )
    packet = stage_meeting_packet_for_node(station, "sub_engel_auto_return_proof", prompt)
    work_order = write_shared_room_work_order_for_node(
        station,
        "sub_engel_auto_return_proof",
        prompt,
        meeting_packet_path=str(packet.get("path") or ""),
    )

    attempts_log: list[dict[str, Any]] = []
    returned: tuple[Path, dict[str, Any]] | None = None
    for index in range(1, max(1, attempts) + 1):
        refreshed = refresh_active_request(work_order)
        returned = wait_for_sub_engel_return(
            str(work_order.get("id") or ""),
            str(work_order.get("expected_return_folder") or ""),
            wait_seconds,
            node_id,
        )
        attempt_log: dict[str, Any] = {
            "attempt": index,
            "active_marker_refreshed": refreshed,
            "passive_auto_return_seen": returned is not None,
            "returned_file": str(returned[0]) if returned else "",
            "remote_wakeups": [],
        }
        if returned:
            attempts_log.append(attempt_log)
            break
        for action in ("shared_room.process_pending_work_orders", "shared_room.process_latest_work_order"):
            remote = run_action(
                action,
                node_kind="windows",
                node_id=node_id,
            )
            payload = decode_remote_stdout(remote)
            attempt_log["remote_wakeups"].append({
                "action": action,
                "remote_ok": bool(remote.get("ok")),
                "remote_return_code": remote.get("result", {}).get("return_code") if isinstance(remote.get("result"), dict) else None,
                "remote_error": remote.get("error", ""),
                "remote_payload_overall_ok": payload.get("overall_ok"),
                "remote_payload_source_work_order": payload.get("source_work_order", ""),
                "remote_payload_exported_file": payload.get("exported_file", ""),
            })
            returned = wait_for_sub_engel_return(
                str(work_order.get("id") or ""),
                str(work_order.get("expected_return_folder") or ""),
                wait_seconds,
                node_id,
            )
            attempt_log["returned_file"] = str(returned[0]) if returned else ""
            if returned:
                break
        attempts_log.append(attempt_log)
        if returned:
            break
        time.sleep(min(10.0, 2.0 * index))

    receipt = {
        "schema": "engel_sub_engel_auto_return_proof_v1",
        "created_at_utc": utc_stamp(),
        "ok": returned is not None,
        "node_id": node_id,
        "work_order": work_order,
        "meeting_packet": packet,
        "attempts": attempts_log,
        "returned_file": str(returned[0]) if returned else "",
        "returned_payload": returned[1] if returned else {},
        "auto_return": True,
        "auto_apply": False,
        "requires_review_before_apply": True,
        "google_drive_use": "communication_only",
    }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    out = REPORT_DIR / f"ENGEL_SUB_ENGEL_AUTO_RETURN_PROOF_{_dt.datetime.now(_dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    latest = REPORT_DIR / "ENGEL_SUB_ENGEL_AUTO_RETURN_PROOF_LATEST.json"
    latest.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    receipt["proof_path"] = str(out)
    receipt["latest_path"] = str(latest)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description="Prove live Windows Sub-Engel auto-return path")
    parser.add_argument("--node", default="DESKTOP-UE5A6GG", help="registered Windows Sub-Engel node id")
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--wait-seconds", type=float, default=45.0)
    args = parser.parse_args()
    receipt = run_proof(args.node, args.attempts, args.wait_seconds)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if receipt.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
