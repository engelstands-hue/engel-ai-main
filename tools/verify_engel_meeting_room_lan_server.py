#!/usr/bin/env python3
"""Verify the Engel Meeting Room LAN server with real HTTP calls."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time
from typing import Any
import urllib.error
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "reports" / "meeting_room_server"


def iso_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def stamp() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def request_json(method: str, url: str, payload: dict[str, Any] | None = None, timeout: float = 20.0) -> dict[str, Any]:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8")
    parsed = json.loads(body)
    if not isinstance(parsed, dict):
        raise ValueError(f"{url} returned non-object JSON")
    return parsed


def run(url: str, submit_test_order: bool) -> dict[str, Any]:
    base = url.rstrip("/")
    started = time.perf_counter()
    checks: list[dict[str, Any]] = []

    def check(name: str, fn) -> dict[str, Any]:
        try:
            value = fn()
            ok = bool(value.get("ok") is True)
            item = {"name": name, "ok": ok, "result": value}
        except Exception as exc:
            item = {"name": name, "ok": False, "error": str(exc)}
        checks.append(item)
        return item

    health = check("health", lambda: request_json("GET", f"{base}/health"))
    check("api_health", lambda: request_json("GET", f"{base}/api/health"))
    check(
        "main_checkin",
        lambda: request_json(
            "POST",
            f"{base}/room/checkin",
            {
                "participant_id": "engel_ai_main_verifier",
                "name": "Engel AI Main Verifier",
                "kind": "engel_ai_main",
                "role": "meeting_room_server_verifier",
                "status": "online",
                "source": "tools/verify_engel_meeting_room_lan_server.py",
                "capabilities": ["room_state", "order_submit", "order_complete", "event_tail"],
            },
        ),
    )
    state = check("room_state", lambda: request_json("GET", f"{base}/room/state"))
    participants = check("participants", lambda: request_json("GET", f"{base}/room/participants"))
    events = check("events", lambda: request_json("GET", f"{base}/room/events?since=0&limit=25"))
    latest_before = check("latest_order_before", lambda: request_json("GET", f"{base}/room/orders/latest"))

    order_result: dict[str, Any] = {}
    complete_result: dict[str, Any] = {}
    if submit_test_order:
        order = check(
            "submit_test_order",
            lambda: request_json(
                "POST",
                f"{base}/room/order",
                {
                    "source": "Engel Meeting Room LAN Server Verifier",
                    "order_text": (
                        "Verify the new LAN Meeting Room server by creating a visible proof order "
                        "for Engel AI Main, Android workers, and Sub-Engels."
                    ),
                },
                timeout=60,
            ),
        )
        order_result = order.get("result") if isinstance(order.get("result"), dict) else {}
        order_id = str(order_result.get("order_id") or "")
        if order_id:
            complete = check(
                "complete_test_order",
                lambda: request_json(
                    "POST",
                    f"{base}/room/complete",
                    {
                        "source": "Engel Meeting Room LAN Server Verifier",
                        "order_id": order_id,
                        "reply": (
                            "Verifier completed this through the LAN server. "
                            "The server accepted order submit/complete and recorded an event trail."
                        ),
                    },
                    timeout=90,
                ),
            )
            complete_result = complete.get("result") if isinstance(complete.get("result"), dict) else {}
        check("latest_order_after", lambda: request_json("GET", f"{base}/room/orders/latest"))

    all_required_ok = all(item.get("ok") is True for item in checks)
    health_result = health.get("result") if isinstance(health.get("result"), dict) else {}
    state_result = state.get("result") if isinstance(state.get("result"), dict) else {}
    participants_result = participants.get("result") if isinstance(participants.get("result"), dict) else {}
    events_result = events.get("result") if isinstance(events.get("result"), dict) else {}
    receipt = {
        "ok": all_required_ok,
        "schema": "engel_meeting_room_lan_server_verify_v1",
        "status": "LAN Meeting Room server verified" if all_required_ok else "LAN Meeting Room server verification failed",
        "updated_at_utc": iso_now(),
        "url": base,
        "latency_ms": int((time.perf_counter() - started) * 1000),
        "server_root": health_result.get("server_root", ""),
        "app_root": health_result.get("app_root", ""),
        "c_drive_used": bool(health_result.get("c_drive_used") is True),
        "storage_policy": health_result.get("storage_policy", ""),
        "google_drive_policy": health_result.get("google_drive_policy", ""),
        "participant_counts": participants_result.get("participant_counts", {}),
        "room_participant_count": (state_result.get("room") or {}).get("participant_count", 0)
        if isinstance(state_result.get("room"), dict)
        else 0,
        "event_count": events_result.get("event_count", 0),
        "submit_test_order": submit_test_order,
        "test_order_id": order_result.get("order_id", ""),
        "test_order_accepted": bool(order_result.get("accepted") is True),
        "test_complete_accepted": bool(complete_result.get("accepted") is True) if submit_test_order else False,
        "checks": checks,
    }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    receipt_path = REPORT_DIR / f"ENGEL_MEETING_ROOM_LAN_SERVER_VERIFY_{stamp()}.json"
    receipt["receipt_path"] = str(receipt_path)
    write_json(receipt_path, receipt)
    latest_path = REPORT_DIR / "ENGEL_MEETING_ROOM_LAN_SERVER_VERIFY_LATEST.json"
    write_json(latest_path, receipt)
    return receipt


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8790")
    parser.add_argument("--submit-test-order", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    receipt = run(args.url, args.submit_test_order)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if receipt.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
