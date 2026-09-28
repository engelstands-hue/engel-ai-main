#!/usr/bin/env python3
"""Real Engel UI test for the Code Factory duration loop.

The prompt is entered through Desktop V2's chat input, then the Agent Meeting
Room starts the Code Factory loop worker. This harness keeps the Engel window
open, records progress into the transcript, and waits until the factory worker
finishes the requested target duration plus any in-flight Builder cycle.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BRIDGE_RUNTIME = ROOT / "runtime" / "meeting_room" / "code_factory"
HOUR_LOOP_ROOT = BRIDGE_RUNTIME / "hour_loop"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _duration_target() -> int:
    raw = os.environ.get("ENGEL_CODE_FACTORY_HOUR_LOOP_SECONDS", "").strip()
    if raw:
        try:
            return max(1, int(float(raw)))
        except ValueError:
            pass
    return 3600


def _duration_label(seconds: int) -> str:
    if seconds % 3600 == 0:
        hours = seconds // 3600
        return f"{hours} hour" if hours == 1 else f"{hours} hours"
    if seconds % 60 == 0:
        minutes = seconds // 60
        return f"{minutes} minute"
    return f"{seconds} second"


def _prompt_for_duration(seconds: int) -> str:
    label = _duration_label(seconds)
    seed_set = os.environ.get("ENGEL_CODE_FACTORY_SEED_SET", "").strip()
    item_text = ""
    if seed_set and seed_set.lower() not in {"default", "standard"}:
        item_text = " Use all new Code Factory items for this run; do not replay the previous seeded item set."
    return (
        f"Run Code Factory for {label} as a loop to fix varied issues in Code Factory. "
        "If a factory problem is still running after the target duration, let it finish. "
        "Use Engel AI input, Agent Meeting Room, Code Factory stations, and share the load across "
        "Alpha and Beta phone devices before falling back to the main PC."
        f"{item_text} Save the process to Engel AI."
    )


def _latest_status_after(started: float) -> Path | None:
    if not HOUR_LOOP_ROOT.exists():
        return None
    statuses = [
        path for path in HOUR_LOOP_ROOT.glob("*/status.json")
        if path.stat().st_mtime >= started
    ]
    return sorted(statuses, key=lambda path: path.stat().st_mtime)[-1] if statuses else None


def _load_status(path: Path | None) -> dict[str, Any]:
    if not path or not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_report(record: dict[str, Any]) -> Path:
    reports_dir = ROOT / "reports" / "meeting_rooms"
    reports_dir.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%dT%H%M%S")
    path = reports_dir / f"ENGEL_UI_CODE_FACTORY_HOUR_LOOP_{stamp}.json"
    path.write_text(json.dumps(record, indent=2, default=str), encoding="utf-8")
    md_path = path.with_suffix(".md")
    lines = [
        "# Engel UI Code Factory Hour Loop",
        "",
        f"- Prompt: {record.get('prompt')}",
        f"- Status: {record.get('status')}",
        f"- Worker state: {record.get('worker_state')}",
        f"- Status path: {record.get('status_path')}",
        f"- Worker report: {record.get('worker_report_path')}",
        f"- Screenshot: {record.get('screenshot_path')}",
        "",
        "## Worker Summary",
        "",
        "```json",
        json.dumps(record.get("worker_status") or {}, indent=2, default=str),
        "```",
        "",
        "## Transcript",
        "",
        "```text",
        str(record.get("transcript") or ""),
        "```",
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    record["markdown_report_path"] = str(md_path)
    path.write_text(json.dumps(record, indent=2, default=str), encoding="utf-8")
    return path


def main() -> int:
    import engel_desktop_v2 as desktop

    if not desktop.HAS_QT:
        print("FAIL: Qt is not available for Desktop V2")
        return 1

    app = desktop.QApplication.instance() or desktop.QApplication(sys.argv)
    app.setStyleSheet(desktop.STYLESHEET)
    app.setWindowIcon(desktop._engel_icon())

    started = time.time()
    duration = _duration_target()
    prompt = _prompt_for_duration(duration)
    max_wait = int(os.environ.get("ENGEL_CODE_FACTORY_HOUR_LOOP_MAX_WAIT_SECONDS", duration + 7200))
    win = desktop.EngelDesktopV2()
    win.show()
    win.raise_()
    win.activateWindow()

    state: dict[str, Any] = {
        "sent": False,
        "done": False,
        "status_path": "",
        "last_progress_at": 0.0,
        "report_path": "",
    }

    def send_prompt() -> None:
        state["sent"] = True
        win.chat_panel.msg_input.setText(prompt)
        win.chat_panel._send()

    def append_progress(status: dict[str, Any]) -> None:
        now = time.time()
        if now - float(state.get("last_progress_at") or 0) < 60:
            return
        state["last_progress_at"] = now
        line = (
            "Factory progress: "
            f"state={status.get('state')} cycle={status.get('cycle')} "
            f"elapsed={status.get('elapsed_sec')}s "
            f"specs={status.get('specs')} builds={status.get('builds')} "
            f"reviews={status.get('reviews')} bundles={status.get('pull_request_bundles')} "
            f"device_returns={(status.get('device_load_share') or {}).get('returned_count')}"
        )
        win.chat_panel.transcript.append("\nEngel Process: " + line)

    def finish(status_text: str, worker_status: dict[str, Any]) -> None:
        transcript = win.chat_panel.transcript.toPlainText()
        screenshot_path = ""
        reports_dir = ROOT / "reports" / "meeting_rooms"
        reports_dir.mkdir(parents=True, exist_ok=True)
        try:
            stamp = dt.datetime.now().strftime("%Y%m%dT%H%M%S")
            shot = reports_dir / f"ENGEL_UI_CODE_FACTORY_HOUR_LOOP_{stamp}.png"
            win.grab().save(str(shot))
            screenshot_path = str(shot)
        except Exception as exc:
            screenshot_path = f"screenshot failed: {type(exc).__name__}: {exc}"
        record = {
            "prompt": prompt,
            "status": status_text,
            "worker_state": worker_status.get("state"),
            "status_path": state.get("status_path") or "",
            "worker_report_path": worker_status.get("report_path") or "",
            "screenshot_path": screenshot_path,
            "worker_status": worker_status,
            "transcript": transcript,
            "started_at": dt.datetime.fromtimestamp(started).isoformat(timespec="seconds"),
            "completed_at": dt.datetime.now().isoformat(timespec="seconds"),
        }
        report = _write_report(record)
        state["report_path"] = str(report)
        state["done"] = True
        desktop.QTimer.singleShot(1500, app.quit)

    def poll() -> None:
        if not state["sent"]:
            return
        status_path = Path(str(state.get("status_path") or "")) if state.get("status_path") else _latest_status_after(started)
        if status_path and status_path.exists():
            state["status_path"] = str(status_path)
        worker_status = _load_status(status_path)
        if worker_status:
            append_progress(worker_status)
            worker_state = str(worker_status.get("state") or "")
            if worker_state == "finished":
                finish("PASS", worker_status)
                return
            if worker_state == "failed":
                finish("FAIL_WORKER_FAILED", worker_status)
                return
        if time.time() - started > max_wait:
            finish("FAIL_TIMEOUT", worker_status)

    desktop.QTimer.singleShot(700, send_prompt)
    timer = desktop.QTimer()
    timer.timeout.connect(poll)
    timer.start(5000)

    app.exec()
    if not state["done"]:
        finish("FAIL_APP_EXITED_EARLY", _load_status(Path(str(state.get("status_path") or ""))))
    print(state["report_path"])
    return 0 if "PASS" in Path(state["report_path"]).read_text(encoding="utf-8") else 1


if __name__ == "__main__":
    raise SystemExit(main())
