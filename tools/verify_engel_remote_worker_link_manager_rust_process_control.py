#!/usr/bin/env python3
"""Verify Python/Engel Main link-manager process control delegates to Rust."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import socket
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
VERIFY_ROOT = ROOT / "runtime" / "rust_link_manager_process_control_verifier"
RUST_EXE = ROOT / "rust" / "engel-core-rs" / "target" / "debug" / "engel-ai-rs.exe"
APPROVAL_TOKEN = "APPROVE_REMOTE_WORKER_LINK_PROCESS_CONTROL"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def free_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def prepare_root(root: Path) -> None:
    if root.exists():
        shutil.rmtree(root)
    (root / "remote_workers" / "lan_link_manager").mkdir(parents=True, exist_ok=True)
    (root / "reports" / "remote_worker_lan_link_manager").mkdir(parents=True, exist_ok=True)
    (root / "tools").mkdir(parents=True, exist_ok=True)
    (root / "engel_ai.py").write_text("# verifier marker\n", encoding="utf-8")
    (root / "engel_agent_meeting_room.py").write_text("# verifier marker\n", encoding="utf-8")
    (root / "engel_remote_worker_lan_pairing.py").write_text("# verifier marker\n", encoding="utf-8")
    (root / "tools" / "verify_engel_remote_worker_claim_lock.py").write_text(
        "# verifier marker\n",
        encoding="utf-8",
    )


def receipt_text(root: Path) -> str:
    report_dir = root / "reports" / "remote_worker_lan_link_manager"
    return "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in sorted(report_dir.glob("REMOTE_WORKER_LINK_MANAGER_*.md"))
    )


def main() -> int:
    sys.path.insert(0, str(ROOT))
    require(RUST_EXE.is_file(), f"missing Rust executable: {RUST_EXE}")
    prepare_root(VERIFY_ROOT)
    port = free_local_port()

    old_env = {
        "ENGEL_REMOTE_WORKER_LINK_MANAGER_RUST_BRIDGE": os.environ.get(
            "ENGEL_REMOTE_WORKER_LINK_MANAGER_RUST_BRIDGE"
        ),
        "ENGEL_REMOTE_WORKER_LINK_MANAGER_RUST_STRICT": os.environ.get(
            "ENGEL_REMOTE_WORKER_LINK_MANAGER_RUST_STRICT"
        ),
        "ENGEL_REMOTE_WORKER_LINK_MANAGER_RUST_ROOT": os.environ.get(
            "ENGEL_REMOTE_WORKER_LINK_MANAGER_RUST_ROOT"
        ),
        "ENGEL_AI_RS_EXE": os.environ.get("ENGEL_AI_RS_EXE"),
    }
    os.environ["ENGEL_REMOTE_WORKER_LINK_MANAGER_RUST_BRIDGE"] = "1"
    os.environ["ENGEL_REMOTE_WORKER_LINK_MANAGER_RUST_STRICT"] = "1"
    os.environ["ENGEL_REMOTE_WORKER_LINK_MANAGER_RUST_ROOT"] = str(VERIFY_ROOT)
    os.environ["ENGEL_AI_RS_EXE"] = str(RUST_EXE)
    try:
        import engel_remote_worker_link_manager as manager

        lan_refused = manager.start_link("192.0.2.40", port, False)
        require(lan_refused.get("ok") is False, f"LAN bind without allow-lan was not refused: {lan_refused}")
        require(
            lan_refused.get("runtime") == "engel-ai-rs",
            f"LAN refusal did not come from Rust bridge: {lan_refused}",
        )

        started = manager.start_link("127.0.0.1", port, False)
        require(started.get("runtime") == "engel-ai-rs", f"start not Rust-backed: {started}")
        require(started.get("bridge_process_control") is True, f"start missing process bridge: {started}")
        require(started.get("process_started") is True, f"Rust process was not started: {started}")
        require(started.get("receiver_runtime") == "engel-ai-rs", f"wrong receiver runtime: {started}")
        require(started.get("receiver_health_ok") is True, f"receiver health failed: {started}")
        require(started.get("started_by_link_manager") is True, f"start ownership missing: {started}")
        first_pid = int(started.get("receiver_pid") or 0)
        require(first_pid > 0, f"missing started pid: {started}")

        restarted = manager.restart_link("127.0.0.1", port, False)
        require(restarted.get("runtime") == "engel-ai-rs", f"restart not Rust-backed: {restarted}")
        require(restarted.get("bridge_process_control") is True, f"restart missing process bridge: {restarted}")
        require(restarted.get("process_started") is True, f"restart did not start receiver: {restarted}")
        require(restarted.get("receiver_health_ok") is True, f"restart health failed: {restarted}")
        second_pid = int(restarted.get("receiver_pid") or 0)
        require(second_pid > 0, f"missing restarted pid: {restarted}")

        stopped = manager.stop_link()
        require(stopped.get("runtime") == "engel-ai-rs", f"stop not Rust-backed: {stopped}")
        require(stopped.get("bridge_process_control") is True, f"stop missing process bridge: {stopped}")
        require(stopped.get("process_stopped") is True, f"Rust process was not stopped: {stopped}")
        require(stopped.get("receiver_running") is False, f"receiver still running: {stopped}")
        require(stopped.get("receiver_pid") is None, f"receiver pid not cleared: {stopped}")

        receipts = receipt_text(VERIFY_ROOT)
        require(APPROVAL_TOKEN not in receipts, "approval token leaked into process-control receipts")

        payload: dict[str, Any] = {
            "ok": True,
            "runtime": "engel-ai-rs",
            "verification": "Python/Engel Main link-manager Rust process-control bridge",
            "bridge": "python-link-manager-rust-lan-link",
            "bridge_process_control": True,
            "lan_without_allow_refused": lan_refused.get("ok") is False,
            "started_by_rust": started.get("process_started") is True,
            "restarted_by_rust": restarted.get("process_started") is True,
            "stopped_by_rust": stopped.get("process_stopped") is True,
            "receiver_runtime": "engel-ai-rs",
            "first_pid": first_pid,
            "second_pid": second_pid,
            "receipt_approval_token_stripped": APPROVAL_TOKEN not in receipts,
            "python_receiver_started": False,
            "mutates_live_link_state": False,
            "mutates_live_pairing_token": False,
            "mutates_live_assignment_root": False,
        }
        return 0 if print_json_after_cleanup(payload) else 1
    finally:
        for key, value in old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        if VERIFY_ROOT.exists():
            shutil.rmtree(VERIFY_ROOT)


def print_json_after_cleanup(payload: dict[str, Any]) -> bool:
    if VERIFY_ROOT.exists():
        shutil.rmtree(VERIFY_ROOT)
    payload["temp_root"] = str(VERIFY_ROOT)
    payload["temp_root_removed"] = not VERIFY_ROOT.exists()
    payload["ok"] = bool(payload.get("ok")) and payload["temp_root_removed"]
    print(json.dumps(payload, indent=2, sort_keys=True))
    return bool(payload["ok"])


if __name__ == "__main__":
    raise SystemExit(main())
