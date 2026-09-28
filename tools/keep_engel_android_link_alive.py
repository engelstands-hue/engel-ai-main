#!/usr/bin/env python3
"""Keep the Engel Android LAN worker receiver alive during long UI runs."""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
LINK_MANAGER = ROOT / "engel_remote_worker_link_manager.py"
LOG_DIR = ROOT / "runtime" / "android_link_watchdog"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%dT%H%M%S")


def run_json(args: list[str], timeout: int = 45) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, str(LINK_MANAGER), *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        payload = {"stdout": proc.stdout[-2000:]}
    payload["return_code"] = proc.returncode
    if proc.stderr.strip():
        payload["stderr"] = proc.stderr.strip()[-2000:]
    return payload


def write_row(log_path: Path, row: dict[str, Any]) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")
    print(json.dumps(row, sort_keys=True), flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duration-seconds", type=int, default=15000, help="Run duration. Use 0 for no fixed deadline.")
    parser.add_argument("--interval-seconds", type=int, default=60)
    parser.add_argument("--host", default="192.0.2.40")
    parser.add_argument("--port", default="8765")
    args = parser.parse_args(argv)

    log_path = LOG_DIR / f"android_link_watchdog_{stamp()}.jsonl"
    deadline = None if args.duration_seconds == 0 else time.time() + max(1, args.duration_seconds)
    write_row(log_path, {"time_utc": utc_now(), "event": "watchdog_started", "log": str(log_path)})

    while deadline is None or time.time() < deadline:
        status = run_json(["status"])
        receiver_running = bool(status.get("receiver_running"))
        auto_enabled = bool(status.get("auto_worker_enabled"))
        row = {
            "time_utc": utc_now(),
            "event": "status",
            "receiver_running": receiver_running,
            "receiver_health_ok": bool(status.get("receiver_health_ok")),
            "auto_worker_enabled": auto_enabled,
            "last_seen_utc": status.get("last_seen_utc"),
            "host": status.get("host"),
            "port": status.get("port"),
        }
        write_row(log_path, row)

        if not receiver_running or not status.get("receiver_health_ok"):
            restarted = run_json(["restart", "--host", args.host, "--port", str(args.port), "--allow-lan"], timeout=90)
            write_row(
                log_path,
                {
                    "time_utc": utc_now(),
                    "event": "receiver_restarted",
                    "receiver_running": bool(restarted.get("receiver_running")),
                    "receiver_health_ok": bool(restarted.get("receiver_health_ok")),
                    "last_seen_utc": restarted.get("last_seen_utc"),
                },
            )
            status = restarted
        if not status.get("auto_worker_enabled"):
            enabled = run_json(["enable-auto-worker"])
            write_row(
                log_path,
                {
                    "time_utc": utc_now(),
                    "event": "auto_worker_enabled",
                    "auto_worker_enabled": bool(enabled.get("auto_worker_enabled")),
                    "check_now_requested": bool(enabled.get("check_now_requested")),
                },
            )
        checked = run_json(["check-now"])
        write_row(
            log_path,
            {
                "time_utc": utc_now(),
                "event": "check_now",
                "receiver_running": bool(checked.get("receiver_running")),
                "last_seen_utc": checked.get("last_seen_utc"),
                "check_now_requested": bool(checked.get("check_now_requested")),
            },
        )
        time.sleep(max(10, args.interval_seconds))

    write_row(log_path, {"time_utc": utc_now(), "event": "watchdog_finished"})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
