#!/usr/bin/env python3
"""Run a real Engel Desktop V2 UI input test for Code Factory.

This opens the actual Desktop V2 window, writes a prompt into the chat input,
uses the panel's send path, waits for the Agent Meeting Room handoff to return,
and records the resulting Code Factory Scout spec.
"""
from __future__ import annotations

import datetime as _dt
import json
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PROMPT = (
    "Use main PC Code Factory Scout: make a builder-ready spec for adding "
    "a --version flag to code-factory factory.py. Return the spec path."
)


def _latest_spec_after(start_time: float) -> Path | None:
    specs_dir = ROOT / "runtime" / "meeting_room" / "code_factory" / "runtime" / "specs"
    if not specs_dir.exists():
        return None
    specs = [
        path for path in specs_dir.glob("engel-code-factory-*.json")
        if path.stat().st_mtime >= start_time
    ]
    return sorted(specs, key=lambda path: path.stat().st_mtime)[-1] if specs else None


def _write_report(record: dict) -> Path:
    reports_dir = ROOT / "reports" / "meeting_rooms"
    reports_dir.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().strftime("%Y%m%dT%H%M%S")
    path = reports_dir / f"ENGEL_UI_CODE_FACTORY_REAL_TEST_{stamp}.json"
    path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    md_path = path.with_suffix(".md")
    lines = [
        "# Engel UI Code Factory Real Test",
        "",
        f"- Prompt: {record.get('prompt')}",
        f"- Status: {record.get('status')}",
        f"- Spec: {record.get('spec_path')}",
        f"- Screenshot: {record.get('screenshot_path')}",
        "",
        "## Transcript",
        "",
        "```text",
        str(record.get("transcript") or ""),
        "```",
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    record["markdown_report_path"] = str(md_path)
    path.write_text(json.dumps(record, indent=2), encoding="utf-8")
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
    win = desktop.EngelDesktopV2()
    win.show()
    win.raise_()
    win.activateWindow()

    state = {"sent": False, "done": False, "report_path": ""}

    def send_prompt() -> None:
        state["sent"] = True
        win.chat_panel.msg_input.setText(PROMPT)
        win.chat_panel._send()

    def finish(status: str) -> None:
        transcript = win.chat_panel.transcript.toPlainText()
        spec_path = _latest_spec_after(started)
        if "don't have a live AI connected right now" in transcript.lower():
            status = "FAIL_STALE_PROVIDER_MESSAGE"
        screenshot_path = ""
        reports_dir = ROOT / "reports" / "meeting_rooms"
        reports_dir.mkdir(parents=True, exist_ok=True)
        try:
            stamp = _dt.datetime.now().strftime("%Y%m%dT%H%M%S")
            shot = reports_dir / f"ENGEL_UI_CODE_FACTORY_REAL_TEST_{stamp}.png"
            win.grab().save(str(shot))
            screenshot_path = str(shot)
        except Exception as exc:
            screenshot_path = f"screenshot failed: {type(exc).__name__}: {exc}"
        record = {
            "prompt": PROMPT,
            "status": status,
            "spec_path": str(spec_path) if spec_path else "",
            "screenshot_path": screenshot_path,
            "transcript": transcript,
            "started_at": _dt.datetime.fromtimestamp(started).isoformat(timespec="seconds"),
            "completed_at": _dt.datetime.now().isoformat(timespec="seconds"),
        }
        report_path = _write_report(record)
        state["report_path"] = str(report_path)
        state["done"] = True
        desktop.QTimer.singleShot(1500, app.quit)

    def poll() -> None:
        if not state["sent"]:
            return
        thread = getattr(win.chat_panel, "_chat_thread", None)
        running = bool(thread and thread.isRunning())
        transcript = win.chat_panel.transcript.toPlainText()
        spec_path = _latest_spec_after(started)
        if not running and spec_path and "Meeting Room updated:" in transcript:
            finish("PASS")
            return
        if time.time() - started > 90:
            finish("FAIL_TIMEOUT")

    desktop.QTimer.singleShot(700, send_prompt)
    poll_timer = desktop.QTimer()
    poll_timer.timeout.connect(poll)
    poll_timer.start(500)

    app.exec()
    if not state["done"]:
        finish("FAIL_APP_EXITED_EARLY")
    print(state["report_path"])
    return 0 if "PASS" in Path(state["report_path"]).read_text(encoding="utf-8") else 1


if __name__ == "__main__":
    raise SystemExit(main())
