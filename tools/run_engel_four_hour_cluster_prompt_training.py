#!/usr/bin/env python3
"""Run four-hour Engel prompt training with cluster/device proof snapshots.

This is a wrapper around the existing real UI prompt trainer. The child runner
drives Engel Desktop V2 chat and Agent Meeting Room. This wrapper only adds
read-only status evidence for Android workers, Windows Sub-Engel nodes, and the
shared Drive room before, during, and after the training.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TRAINER = ROOT / "tools" / "run_engel_four_hour_prompt_training.py"
REPORT_DIR = ROOT / "reports" / "codex_bridge"
RUNTIME_DIR = ROOT / "runtime" / "four_hour_cluster_prompt_training"
LOOP_REPORT_DIR = ROOT / "reports" / "meeting_rooms"
WINDOWS_NODE_IDS = ["DESKTOP-UE5A6GG"]
WINDOWS_ACTIONS = ["node.status", "shared_room.status", "ui.visible_status"]


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def local_stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%dT%H%M%S")


def clip(value: Any, limit: int = 4000) -> str:
    text = str(value or "")
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def write_jsonl(path: Path, event: str, **payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {"time_utc": utc_now(), "event": event, **payload}
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    print(json.dumps(row, ensure_ascii=False, sort_keys=True), flush=True)


def safe_call(label: str, fn: Any) -> dict[str, Any]:
    started = time.time()
    try:
        result = fn()
        return {"ok": True, "elapsed_seconds": round(time.time() - started, 3), "result": result}
    except Exception as exc:  # pragma: no cover - evidence path
        return {
            "ok": False,
            "elapsed_seconds": round(time.time() - started, 3),
            "error": f"{label}: {type(exc).__name__}: {exc}",
        }


def append_shared_room(channel: str, message: str) -> dict[str, Any]:
    def _append() -> dict[str, Any]:
        from engel_shared_drive_room import append_message

        return append_message(sender="Engel Main Four Hour Trainer", channel=channel, message=message)

    return safe_call("shared_room.append", _append)


def compact_node_response(response: dict[str, Any]) -> dict[str, Any]:
    result = response.get("result") if isinstance(response, dict) else {}
    stdout = result.get("stdout") if isinstance(result, dict) else ""
    parsed: Any = ""
    if isinstance(stdout, str) and stdout.strip():
        try:
            parsed = json.loads(stdout)
        except json.JSONDecodeError:
            parsed = clip(stdout, 1200)
    elif stdout:
        parsed = stdout
    compact = {
        "ok": bool(response.get("ok")) if isinstance(response, dict) else False,
        "return_code": result.get("return_code") if isinstance(result, dict) else None,
    }
    if isinstance(parsed, dict):
        for key in ("hostname", "platform", "local_ips", "remote_control", "ok", "room_exists", "message_count"):
            if key in parsed:
                compact[key] = parsed[key]
        compact["parsed_preview"] = clip(json.dumps(parsed, sort_keys=True), 1600)
    else:
        compact["stdout_preview"] = clip(parsed, 1600)
    if isinstance(response, dict) and response.get("error"):
        compact["error"] = response.get("error")
    return compact


def collect_snapshot(phase: str) -> dict[str, Any]:
    snapshot: dict[str, Any] = {"phase": phase, "timestamp_utc": utc_now()}

    snapshot["shared_drive_room"] = safe_call(
        "shared_room.status",
        lambda: __import__("engel_shared_drive_room").status(),
    )
    snapshot["android_link_manager"] = safe_call(
        "engel_remote_worker_link_manager.link_status",
        lambda: __import__("engel_remote_worker_link_manager").link_status(),
    )
    snapshot["android_adb_workers"] = safe_call(
        "engel_adb_worker_manager.render_adb_workers_status",
        lambda: clip(__import__("engel_adb_worker_manager").render_adb_workers_status(), 5000),
    )

    def _windows() -> list[dict[str, Any]]:
        from engel_sub_node_remote_control import run_action

        rows: list[dict[str, Any]] = []
        for node_id in WINDOWS_NODE_IDS:
            for action in WINDOWS_ACTIONS:
                started = time.time()
                response = run_action(action, node_kind="windows", node_id=node_id)
                row = compact_node_response(response)
                row.update(
                    {
                        "node_id": node_id,
                        "action": action,
                        "elapsed_seconds": round(time.time() - started, 3),
                    }
                )
                rows.append(row)
        return rows

    snapshot["windows_sub_engel"] = safe_call("windows_sub_engel.probes", _windows)
    return snapshot


def list_loop_receipts_since(start_epoch: float) -> list[Path]:
    if not LOOP_REPORT_DIR.exists():
        return []
    return sorted(
        [
            path
            for path in LOOP_REPORT_DIR.glob("ENGEL_UI_INPUT_CREATION_TRAINING_LOOP_*.json")
            if path.stat().st_mtime >= start_epoch - 2
        ],
        key=lambda item: item.stat().st_mtime,
    )


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def render_report(
    report_path: Path,
    run_stamp: str,
    started_utc: str,
    ended_utc: str,
    duration_seconds: float,
    command: list[str],
    exit_code: int,
    event_log: Path,
    child_log: Path,
    snapshots: list[dict[str, Any]],
    loop_receipts: list[Path],
) -> None:
    latest_loop = loop_receipts[-1] if loop_receipts else None
    latest_payload = load_json(latest_loop) if latest_loop else {}
    final_snapshot = snapshots[-1] if snapshots else {}
    link_result = final_snapshot.get("android_link_manager", {}).get("result", {})
    windows_rows = final_snapshot.get("windows_sub_engel", {}).get("result", [])
    windows_ok = [
        row.get("node_id")
        for row in windows_rows
        if row.get("action") == "node.status" and row.get("ok")
    ] if isinstance(windows_rows, list) else []
    lines = [
        "# Engel Four-Hour Cluster Prompt Training",
        "",
        f"- Run stamp: `{run_stamp}`",
        f"- Started UTC: `{started_utc}`",
        f"- Ended UTC: `{ended_utc}`",
        f"- Duration seconds: `{duration_seconds:.1f}`",
        f"- Trainer exit code: `{exit_code}`",
        f"- Trainer complete: `{exit_code == 0}`",
        f"- Device snapshots: `{len(snapshots)}`",
        f"- Android receiver running at final snapshot: `{bool(link_result.get('receiver_running')) if isinstance(link_result, dict) else False}`",
        f"- Android last seen UTC: `{link_result.get('last_seen_utc') if isinstance(link_result, dict) else ''}`",
        f"- Windows direct nodes live at final snapshot: `{sorted(set(windows_ok))}`",
        f"- Loop all_ok: `{latest_payload.get('all_ok') if latest_payload else ''}`",
        f"- Loop cycles completed: `{latest_payload.get('cycles_completed') if latest_payload else ''}`",
        "",
        "## Proof Files",
        "",
        f"- Event log: `{event_log}`",
        f"- Trainer log: `{child_log}`",
    ]
    for path in loop_receipts:
        lines.append(f"- Training loop receipt: `{path}`")
        report = path.with_suffix(".md")
        if report.exists():
            lines.append(f"- Training loop report: `{report}`")
    lines += [
        "",
        "## Command",
        "",
        "```powershell",
        " ".join(command),
        "```",
        "",
        "## Safety Boundary",
        "",
        "- Engel Desktop V2 chat and Agent Meeting Room are driven by the child trainer.",
        "- Android worker results remain review-only and are finalized locally by Engel.",
        "- Windows probes are pair-gated allowlisted diagnostics only.",
        "- Shared Drive room writes are append-only status messages.",
    ]
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cycles", type=int, default=4)
    parser.add_argument("--minutes", type=float, default=60.0)
    parser.add_argument("--target-jobs", type=int, default=60)
    parser.add_argument("--per-job-timeout", type=float, default=240.0)
    parser.add_argument("--prompt-start-index", type=int, default=0)
    parser.add_argument("--monitor-interval-seconds", type=int, default=300)
    parser.add_argument("--skip-final-wait", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    os.environ.setdefault("PYTHONPATH", str(ROOT))
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    run_stamp = local_stamp()
    started_utc = utc_now()
    started_epoch = time.time()
    run_dir = RUNTIME_DIR / run_stamp
    event_log = run_dir / "events.jsonl"
    child_log = run_dir / "trainer_stdout.log"
    snapshots: list[dict[str, Any]] = []

    command = [
        sys.executable,
        str(TRAINER),
        "--cycles",
        str(args.cycles),
        "--minutes",
        str(args.minutes),
        "--target-jobs",
        str(args.target_jobs),
        "--per-job-timeout",
        str(args.per_job_timeout),
        "--prompt-start-index",
        str(args.prompt_start_index),
    ]
    if args.skip_final_wait:
        command.append("--skip-final-wait")

    write_jsonl(event_log, "wrapper_started", run_stamp=run_stamp, command=command)
    append_shared_room(
        "TRAINING_START",
        (
            f"Four-hour prompt training wrapper started at {started_utc}. "
            f"cycles={args.cycles}, minutes={args.minutes}, target_jobs={args.target_jobs}."
        ),
    )

    first_snapshot = collect_snapshot("start")
    snapshots.append(first_snapshot)
    write_jsonl(event_log, "device_snapshot", snapshot=first_snapshot)

    env = os.environ.copy()
    env.setdefault("PYTHONPATH", str(ROOT))
    env.setdefault("QT_QPA_PLATFORM", "offscreen")
    proc = subprocess.Popen(
        command,
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))

    def pump_output() -> None:
        assert proc.stdout is not None
        child_log.parent.mkdir(parents=True, exist_ok=True)
        with child_log.open("w", encoding="utf-8") as handle:
            for line in proc.stdout:
                handle.write(line)
                handle.flush()
                print(line, end="", flush=True)

    thread = threading.Thread(target=pump_output, daemon=True)
    thread.start()

    next_snapshot = time.time() + max(60, args.monitor_interval_seconds)
    while proc.poll() is None:
        if time.time() >= next_snapshot:
            phase = f"monitor_{len(snapshots):03d}"
            snapshot = collect_snapshot(phase)
            snapshots.append(snapshot)
            write_jsonl(event_log, "device_snapshot", snapshot=snapshot)
            next_snapshot = time.time() + max(60, args.monitor_interval_seconds)
        time.sleep(5)

    exit_code = int(proc.wait())
    thread.join(timeout=10)
    final_snapshot = collect_snapshot("final")
    snapshots.append(final_snapshot)
    write_jsonl(event_log, "device_snapshot", snapshot=final_snapshot)

    ended_utc = utc_now()
    loop_receipts = list_loop_receipts_since(started_epoch)
    report_path = REPORT_DIR / f"ENGEL_FOUR_HOUR_CLUSTER_PROMPT_TRAINING_{run_stamp}.md"
    render_report(
        report_path=report_path,
        run_stamp=run_stamp,
        started_utc=started_utc,
        ended_utc=ended_utc,
        duration_seconds=time.time() - started_epoch,
        command=command,
        exit_code=exit_code,
        event_log=event_log,
        child_log=child_log,
        snapshots=snapshots,
        loop_receipts=loop_receipts,
    )
    write_jsonl(event_log, "wrapper_finished", exit_code=exit_code, report=str(report_path))
    append_shared_room(
        "TRAINING_RESULT",
        (
            f"Four-hour prompt training finished at {ended_utc}. "
            f"exit_code={exit_code}. Report: {report_path}"
        ),
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
