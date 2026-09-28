#!/usr/bin/env python3
"""Supervise the Engel Android LAN receiver during long-running tests."""
from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path
import subprocess
import sys
import threading
import time


ROOT = Path(__file__).resolve().parents[1]
RECEIVER = ROOT / "engel_remote_worker_lan_pairing.py"
RUNTIME_PYTHON = ROOT / "runtime" / "python310" / "python.exe"
LOG_DIR = ROOT / "runtime" / "android_link_watchdog"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%dT%H%M%S")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duration-seconds", type=int, default=15300)
    parser.add_argument("--host", default="192.0.2.40")
    parser.add_argument("--port", default="8765")
    parser.add_argument("--restart-delay-seconds", type=float, default=1.0)
    parser.add_argument("--verbose-receiver", action="store_true")
    args = parser.parse_args()

    python = str(RUNTIME_PYTHON if RUNTIME_PYTHON.is_file() else Path(sys.executable))
    log_path = LOG_DIR / f"lan_receiver_supervisor_{stamp()}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.time() + max(1, args.duration_seconds)

    def log(line: str, *, echo: bool = True) -> None:
        text = f"{utc_now()} {line}"
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(text.rstrip() + "\n")
        if echo:
            print(text.rstrip(), flush=True)

    log(f"supervisor_started host={args.host} port={args.port} log={log_path}")
    launches = 0
    while time.time() < deadline:
        launches += 1
        command = [
            python,
            "-u",
            str(RECEIVER),
            "serve",
            "--host",
            args.host,
            "--port",
            str(args.port),
            "--allow-lan",
        ]
        log(f"receiver_launch index={launches} command={' '.join(command)}")
        proc = subprocess.Popen(
            command,
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))

        def pump() -> None:
            assert proc.stdout is not None
            for child_line in proc.stdout:
                log("receiver: " + child_line.rstrip(), echo=args.verbose_receiver)

        thread = threading.Thread(target=pump, daemon=True)
        thread.start()
        return_code = proc.wait()
        thread.join(timeout=3)
        log(f"receiver_exit index={launches} return_code={return_code}")
        if time.time() < deadline:
            time.sleep(max(0.2, args.restart_delay_seconds))

    log(f"supervisor_finished launches={launches}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
