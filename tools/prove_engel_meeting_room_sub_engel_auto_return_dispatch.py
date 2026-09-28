#!/usr/bin/env python3
"""Prove Main Meeting Room -> Sub-Engel auto-return dispatch.

This proof sends a real station job through engel_agent_meeting_room and marks
success only when Main returns after seeing a SUB_ENGEL_SENT_WORK result packet
from the selected physical Sub-Engel identity. A local package worker can still
be enabled explicitly for package-only regression testing.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "reports" / "sub_engel_auto_return"
DEFAULT_AGENT = (
    ROOT
    / "runtime"
    / "package_build"
    / "EngelAI-SubEngel-Windows-App"
    / "EngelAI-SubEngel"
    / "_internal"
    / "agent"
    / "engel_windows_sub_node_agent.exe"
)
def _default_shared_room() -> Path:
    override = os.environ.get("ENGEL_SUB_ENGEL_TRANSPORT_ROOT") or os.environ.get(
        "ENGEL_SHARED_ROOM_ROOT"
    )
    if override:
        return Path(override)
    return ROOT / "run" / "sub_engel_transport"


DEFAULT_SHARED_ROOM = _default_shared_room()
DEFAULT_NODE_ROOT = ROOT / "runtime" / "sub_engel_meeting_dispatch_auto_return_node"


def utc_stamp() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def start_auto_worker(agent: Path, env: dict[str, str], out_log: Path, err_log: Path) -> subprocess.Popen:
    out_log.parent.mkdir(parents=True, exist_ok=True)
    out_fh = out_log.open("w", encoding="utf-8")
    err_fh = err_log.open("w", encoding="utf-8")
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return subprocess.Popen(
        [
            str(agent),
            "auto-process-work-orders",
            "--cycles",
            "12",
            "--interval",
            "2",
            "--limit",
            "50",
        ],
        cwd=str(agent.parent.parent),
        env=env,
        stdout=out_fh,
        stderr=err_fh,
        text=True,
        creationflags=flags,
    )


def run_proof(args: argparse.Namespace) -> dict[str, Any]:
    agent = Path(args.agent)
    shared_room = Path(args.shared_room)
    node_root = Path(args.node_root)
    if args.use_local_package_worker and not agent.is_file():
        raise FileNotFoundError(agent)
    if not shared_room.is_dir():
        raise FileNotFoundError(shared_room)

    stamp = utc_stamp()
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    out_log = REPORT_DIR / f"meeting_dispatch_auto_worker_{stamp}.out.log"
    err_log = REPORT_DIR / f"meeting_dispatch_auto_worker_{stamp}.err.log"

    env = os.environ.copy()
    env.update(
        {
            "ENGEL_SHARED_ROOM_ROOT": str(shared_room),
            "ENGEL_MEETING_ROOM_SUB_PASSIVE_WAIT_SECONDS": str(args.passive_wait),
            "ENGEL_MEETING_ROOM_SUB_RETURN_WAIT_SECONDS": str(args.return_wait),
            "ENGEL_MEETING_ROOM_SUB_AUTO_RETURN_ATTEMPTS": str(args.attempts),
            "ENGEL_SUB_ENGEL_LLM_TIMEOUT_SECONDS": str(args.llm_timeout),
            "ENGEL_SUB_ENGEL_LLM_MAX_TOKENS": "160",
        }
    )
    if args.use_local_package_worker:
        env.update(
            {
                "ENGEL_WINDOWS_SUB_NODE_ROOT": str(node_root),
                "ENGEL_WINDOWS_SUB_NODE_STATE": str(node_root / "state"),
                "COMPUTERNAME": str(args.node_id),
            }
        )

    previous_env = os.environ.copy()
    os.environ.update(env)
    worker: subprocess.Popen | None = None
    if args.use_local_package_worker:
        worker = start_auto_worker(agent, env, out_log, err_log)
    try:
        if worker is not None:
            time.sleep(1.0)
        sys.path.insert(0, str(ROOT))
        from engel_agent_meeting_room import dispatch_station_work

        station = {
            "name": "Windows Sub-Engel Auto Return Proof Station",
            "type_label": "Worker Agent",
            "skill_label": "Windows Sub-Engel Worker Skill",
            "equipment": "Windows Sub-Engel Node - LAN check-in",
            "bridge": "Windows Sub-Engel Check-in Preview",
        }
        status, reply = dispatch_station_work(
            station,
            "sub_engel_auto_return_dispatch_proof",
            (
                "MEETING ROOM AUTO RETURN PROOF: create a Windows Sub-Engel "
                "work order, let the Sub-Engel auto-return loop pick it up "
                "from the shared Agent Meeting Room, and mark Returned only "
                "after the SUB_ENGEL_SENT_WORK .done.json exists. Do not "
                "require a human Mark Done or Send Done click."
            ),
        )
        time.sleep(2.0)
    finally:
        os.environ.clear()
        os.environ.update(previous_env)
        if worker is not None and worker.poll() is None:
            worker.terminate()
            try:
                worker.wait(timeout=5)
            except subprocess.TimeoutExpired:
                worker.kill()
                worker.wait(timeout=5)

    receipt = {
        "ok": status == "Returned",
        "schema": "engel_meeting_room_sub_engel_auto_return_dispatch_proof_v1",
        "created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
        "dispatch": {
            "status": status,
            "reply": reply,
        },
        "physical_node_required": not args.use_local_package_worker,
        "selected_node_id_for_proof": str(args.node_id),
        "identity_enforced_by_main": True,
        "worker_pid": worker.pid if worker is not None else None,
        "auto_worker_stdout_log": str(out_log),
        "auto_worker_stderr_log": str(err_log),
        "auto_worker_stdout": read_text(out_log) if worker is not None else "",
        "auto_worker_stderr": read_text(err_log) if worker is not None else "",
        "shared_room": str(shared_room),
        "node_root": str(node_root) if args.use_local_package_worker else "",
        "package_agent": str(agent) if args.use_local_package_worker else "",
    }
    out = REPORT_DIR / f"ENGEL_MEETING_ROOM_SUB_ENGEL_AUTO_RETURN_DISPATCH_PROOF_{stamp}.json"
    latest = REPORT_DIR / "ENGEL_MEETING_ROOM_SUB_ENGEL_AUTO_RETURN_DISPATCH_PROOF_LATEST.json"
    receipt["proof_path"] = str(out)
    receipt["latest_path"] = str(latest)
    write_json(out, receipt)
    write_json(latest, receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description="Prove meeting-room Sub-Engel auto-return dispatch")
    parser.add_argument("--agent", default=str(DEFAULT_AGENT))
    parser.add_argument("--shared-room", default=str(DEFAULT_SHARED_ROOM))
    parser.add_argument("--node-root", default=str(DEFAULT_NODE_ROOT))
    parser.add_argument("--node-id", default="DESKTOP-UE5A6GG")
    parser.add_argument("--attempts", type=int, default=2)
    parser.add_argument("--passive-wait", type=float, default=75.0)
    parser.add_argument("--return-wait", type=float, default=75.0)
    parser.add_argument("--llm-timeout", type=float, default=45.0)
    parser.add_argument("--use-local-package-worker", action="store_true")
    args = parser.parse_args()
    receipt = run_proof(args)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if receipt.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
