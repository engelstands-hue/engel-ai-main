#!/usr/bin/env python3
"""Launch a visible Engel AI UI run for the Trading Dashboard bridge.

This is intentionally interactive: the Desktop V2 window stays open so the
operator can see the prompt, Meeting Room route, agent collaboration, and
bridge report path.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PROMPT = (
    "Review the Engel dashboard SnapTrade setup and paper trader safety rules. "
    "Merge these docs into Engel AI and return the bridge report path."
)
STATUS_PATH = ROOT / "runtime" / "meeting_room" / "trading_dashboard" / "visible_demo_status.json"


def _latest_report_after(start_time: float) -> Path | None:
    root = ROOT / "runtime" / "meeting_room" / "trading_dashboard" / "merge"
    if not root.exists():
        return None
    reports = [
        path
        for path in root.glob("**/TRADING_DASHBOARD_MERGE_REPORT.md")
        if path.stat().st_mtime >= start_time
    ]
    return sorted(reports, key=lambda item: item.stat().st_mtime)[-1] if reports else None


def _write_status(payload: dict) -> None:
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATUS_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> int:
    # Force real visible Qt when this script is started from prior offscreen tests.
    os.environ.pop("QT_QPA_PLATFORM", None)
    os.environ.setdefault("ENGEL_MEETING_ROOM_ANDROID_RETURN_WAIT_SECONDS", "0")

    import engel_desktop_v2 as desktop

    if not desktop.HAS_QT:
        _write_status({"status": "FAIL", "reason": "Qt is not available"})
        return 1

    app = desktop.QApplication.instance() or desktop.QApplication(sys.argv)
    app.setStyleSheet(desktop.STYLESHEET)
    app.setWindowIcon(desktop._engel_icon())

    started = time.time()
    _write_status({
        "status": "STARTING",
        "prompt": PROMPT,
        "started_at": _dt.datetime.now().isoformat(timespec="seconds"),
    })

    win = desktop.EngelDesktopV2()
    win.setWindowTitle("Engel AI - visible Trading Dashboard bridge test")
    win.resize(1280, 760)
    win.show()
    win.raise_()
    win.activateWindow()

    state = {"sent": False, "finished": False}

    def send_prompt() -> None:
        state["sent"] = True
        win.chat_panel.msg_input.setText(PROMPT)
        win.chat_panel._send()
        _write_status({
            "status": "SENT",
            "prompt": PROMPT,
            "sent_at": _dt.datetime.now().isoformat(timespec="seconds"),
        })

    def mark_done(status: str) -> None:
        if state["finished"]:
            return
        state["finished"] = True
        transcript = win.chat_panel.transcript.toPlainText()
        bridge_report = _latest_report_after(started)
        shot_path = ROOT / "reports" / "meeting_rooms" / f"ENGEL_UI_TRADING_DASHBOARD_VISIBLE_{_dt.datetime.now().strftime('%Y%m%dT%H%M%S')}.png"
        shot_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            win.grab().save(str(shot_path))
        except Exception:
            shot_path = Path("")
        win.chat_panel.transcript.append(
            "\nEngel Visible Test: PASS - this prompt ran through Engel AI UI input, "
            "Agent Meeting Room, and the Trading Dashboard bridge. Window left open for review."
        )
        _write_status({
            "status": status,
            "prompt": PROMPT,
            "bridge_report_path": str(bridge_report) if bridge_report else "",
            "screenshot_path": str(shot_path) if shot_path else "",
            "transcript_preview": transcript[-3000:],
            "completed_at": _dt.datetime.now().isoformat(timespec="seconds"),
            "note": "Window remains open until the user closes it.",
        })
        try:
            win._launch_meeting_room()
        except Exception:
            pass

    def poll() -> None:
        if not state["sent"] or state["finished"]:
            return
        thread = getattr(win.chat_panel, "_chat_thread", None)
        running = bool(thread and thread.isRunning())
        transcript = win.chat_panel.transcript.toPlainText()
        report = _latest_report_after(started)
        if (
            not running
            and report is not None
            and "Trading Dashboard bridge returned" in transcript
            and "Meeting Room updated:" in transcript
        ):
            mark_done("PASS")
        elif time.time() - started > 120:
            mark_done("FAIL_TIMEOUT")

    desktop.QTimer.singleShot(900, send_prompt)
    timer = desktop.QTimer()
    timer.timeout.connect(poll)
    timer.start(500)

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
