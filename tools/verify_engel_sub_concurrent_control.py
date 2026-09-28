#!/usr/bin/env python3
"""Prove Sub-Engel keeps shell and disk control responsive during long work."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
for value in (str(ROOT), str(ROOT / "tools")):
    if value not in sys.path:
        sys.path.insert(0, value)

from engel_sub_node_remote_control import decode_action_stdout, run_action


REPORT_DIR = ROOT / "reports" / "sub_engel_remote_control"
NODE_ID = "DESKTOP-UE5A6GG"


def _action_ok(response: dict[str, Any]) -> bool:
    result = response.get("result") if isinstance(response.get("result"), dict) else {}
    return bool(response.get("ok") is True and int(result.get("return_code") or 0) == 0)


def main() -> int:
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=2) as pool:
        shell_future = pool.submit(
            run_action,
            "main.shell",
            node_kind="windows",
            node_id=NODE_ID,
            payload={
                "command": "Start-Sleep -Seconds 6; Write-Output ENGEL_SHELL_DONE",
                "cwd": r"D:\EngelWindowsSubNode",
                "timeout_seconds": 10,
            },
        )
        time.sleep(0.75)
        disk_started = time.perf_counter()
        disk_response = run_action(
            "disk.control",
            node_kind="windows",
            node_id=NODE_ID,
            payload={
                "operation": "path_status",
                "path": r"D:\EngelWindowsSubNode\models",
            },
        )
        disk_elapsed = time.perf_counter() - disk_started
        shell_response = shell_future.result(timeout=15)
    total_elapsed = time.perf_counter() - started

    disk_payload = decode_action_stdout(disk_response)
    shell_result = (
        shell_response.get("result")
        if isinstance(shell_response.get("result"), dict)
        else {}
    )
    shell_transport = str(shell_response.get("control_transport") or "")
    disk_transport = str(disk_response.get("control_transport") or "")
    ct246_authoritative_relay = bool(
        shell_transport == "rog_ssh_to_ct246_authenticated_sub_control"
        and disk_transport == "rog_ssh_to_ct246_authenticated_sub_control"
    )
    ok = bool(
        _action_ok(shell_response)
        and "ENGEL_SHELL_DONE" in str(shell_result.get("stdout") or "")
        and _action_ok(disk_response)
        and disk_payload.get("ok") is True
        and disk_payload.get("exists") is True
        and ct246_authoritative_relay
        and disk_elapsed < 3.5
        and total_elapsed >= 5.5
    )
    payload = {
        "schema": "engel_sub_concurrent_control_verifier_v1",
        "ok": ok,
        "checked_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "node_id": NODE_ID,
        "shell_ok": _action_ok(shell_response),
        "disk_ok": _action_ok(disk_response) and disk_payload.get("ok") is True,
        "disk_path_exists": disk_payload.get("exists") is True,
        "ct246_authoritative_relay": ct246_authoritative_relay,
        "shell_control_transport": shell_transport,
        "disk_control_transport": disk_transport,
        "disk_response_seconds": round(disk_elapsed, 3),
        "shell_and_disk_total_seconds": round(total_elapsed, 3),
        "concurrency_rule": "disk response under 3.5 seconds while shell sleeps for 6 seconds",
        "destructive_action_used": False,
    }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORT_DIR / "ENGEL_SUB_CONCURRENT_CONTROL_LATEST.json"
    report_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    payload["receipt_path"] = str(report_path)
    print(json.dumps(payload, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
