#!/usr/bin/env python3
"""Renew near-expiry paired Sub-Engel sessions on their authoritative host."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import engel_sub_node_remote_control as remote  # noqa: E402


REPORT_PATH = (
    ROOT
    / "reports"
    / "sub_engel_remote_control"
    / "ENGEL_SUB_SESSION_RENEWAL_LATEST.json"
)
DEFAULT_RENEW_BEFORE_SECONDS = 3 * 24 * 60 * 60


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_utc(value: Any) -> float:
    raw = str(value or "").strip()
    if not raw:
        return 0.0
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def renew_sessions(*, dry_run: bool, renew_before_seconds: int) -> dict[str, Any]:
    nodes: list[dict[str, Any]] = []
    ok = True
    now = time.time()
    for item in remote.list_node_sessions("windows"):
        node_id = str(item.get("node_id") or "").strip()
        session = item.get("session") if isinstance(item.get("session"), dict) else {}
        expires_at = parse_utc(session.get("expires_at_utc"))
        remaining = expires_at - now if expires_at else 0.0
        record: dict[str, Any] = {
            "node_id": node_id,
            "expires_at_utc": str(session.get("expires_at_utc") or ""),
            "remaining_seconds": round(remaining, 1),
            "renewal_due": bool(expires_at and remaining <= renew_before_seconds),
            "renewed": False,
            "dry_run": dry_run,
        }
        if not expires_at:
            record["status"] = "missing_expiry"
            ok = False
        elif remaining <= 0:
            record["status"] = "expired_requires_pairing"
            ok = False
        elif remaining > renew_before_seconds:
            record["status"] = "healthy_not_due"
        elif dry_run:
            record["status"] = "renewal_due_dry_run"
        else:
            response = remote.run_action(
                "session.renew",
                node_kind="windows",
                node_id=node_id,
            )
            result = remote.decode_action_stdout(response)
            renewed = bool(
                response.get("ok") is True
                and result.get("ok") is True
                and result.get("expires_at_utc")
            )
            record.update(
                {
                    "renewed": renewed,
                    "status": "renewed" if renewed else "renewal_failed",
                    "new_expires_at_utc": str(result.get("expires_at_utc") or ""),
                    "error": str(response.get("error") or result.get("error") or ""),
                }
            )
            ok = ok and renewed
        nodes.append(record)
    if not nodes:
        ok = False
    payload = {
        "schema": "engel_sub_session_renewal_v1",
        "ok": ok,
        "checked_at_utc": utc_now(),
        "authority_root": str(ROOT),
        "dry_run": dry_run,
        "renew_before_seconds": renew_before_seconds,
        "node_count": len(nodes),
        "renewed_count": sum(1 for item in nodes if item.get("renewed") is True),
        "nodes": nodes,
        "secret_material_reported": False,
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--renew-before-seconds",
        type=int,
        default=DEFAULT_RENEW_BEFORE_SECONDS,
    )
    args = parser.parse_args()
    payload = renew_sessions(
        dry_run=args.dry_run,
        renew_before_seconds=max(3600, int(args.renew_before_seconds)),
    )
    print(json.dumps(payload, indent=2))
    return 0 if payload.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
