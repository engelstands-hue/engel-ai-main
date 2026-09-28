#!/usr/bin/env python3
"""Run a real Engel Desktop V2 UI-input test for the Trading Dashboard bridge."""
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


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


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


def _latest_order_after(start_time: float) -> Path | None:
    root = ROOT / "runtime" / "meeting_room" / "main_ui_orders"
    if not root.exists():
        return None
    orders = [
        path
        for path in root.glob("MAIN-*.json")
        if path.stat().st_mtime >= start_time
    ]
    return sorted(orders, key=lambda item: item.stat().st_mtime)[-1] if orders else None


def _read_json(path: Path | None) -> dict:
    if not path or not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _assert_no_secret_or_temp(value: object) -> None:
    text = json.dumps(value, indent=2) if not isinstance(value, str) else value
    forbidden = (
        "SNAPTRADE_CONSUMER_KEY=",
        "SNAPTRADE_CLIENT_ID=",
        "Authorization: Bearer",
        "session token:",
        "C:\\Users\\ziese\\AppData\\Local\\Temp",
        "AppData\\Local\\Temp",
    )
    require(not any(item in text for item in forbidden), "secret/temp text leaked into UI test output")


def _write_report(record: dict) -> Path:
    reports_dir = ROOT / "reports" / "meeting_rooms"
    reports_dir.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().strftime("%Y%m%dT%H%M%S")
    path = reports_dir / f"ENGEL_UI_TRADING_DASHBOARD_REAL_TEST_{stamp}.json"
    md_path = path.with_suffix(".md")
    lines = [
        "# Engel UI Trading Dashboard Real Test",
        "",
        f"- Prompt: {record.get('prompt')}",
        f"- Status: {record.get('status')}",
        f"- Bridge report: {record.get('bridge_report_path')}",
        f"- Order record: {record.get('order_path')}",
        f"- Screenshot: {record.get('screenshot_path')}",
        "",
        "## Route",
        "",
        f"- Task type: {record.get('prompt_route', {}).get('task_type')}",
        f"- Bridge key: {record.get('prompt_route', {}).get('bridge_key')}",
        f"- Meeting bridge: {record.get('prompt_route', {}).get('meeting_bridge')}",
        "",
        "## Stations",
        "",
    ]
    for station in record.get("station_details", []):
        lines.append(
            "- {equipment} -> {agent} -> {skill} via {bridge}".format(
                equipment=station.get("device", ""),
                agent=station.get("agent", ""),
                skill=station.get("skill", ""),
                bridge=station.get("bridge", ""),
            )
        )
    lines += [
        "",
        "## Transcript",
        "",
        "```text",
        str(record.get("transcript") or ""),
        "```",
        "",
    ]
    path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    record["markdown_report_path"] = str(md_path)
    path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return path


def main() -> int:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("ENGEL_MEETING_ROOM_ANDROID_RETURN_WAIT_SECONDS", "0")

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
        bridge_report = _latest_report_after(started)
        order_path = _latest_order_after(started)
        order_payload = _read_json(order_path)
        screenshot_path = ""
        try:
            stamp = _dt.datetime.now().strftime("%Y%m%dT%H%M%S")
            shot = ROOT / "reports" / "meeting_rooms" / f"ENGEL_UI_TRADING_DASHBOARD_REAL_TEST_{stamp}.png"
            shot.parent.mkdir(parents=True, exist_ok=True)
            win.grab().save(str(shot))
            screenshot_path = str(shot)
        except Exception as exc:
            screenshot_path = f"screenshot failed: {type(exc).__name__}: {exc}"

        record = {
            "prompt": PROMPT,
            "status": status,
            "bridge_report_path": str(bridge_report) if bridge_report else "",
            "order_path": str(order_path) if order_path else "",
            "screenshot_path": screenshot_path,
            "prompt_route": order_payload.get("prompt_route") or {},
            "station_details": order_payload.get("station_details") or [],
            "station_results": order_payload.get("station_results") or [],
            "returned_previews": order_payload.get("returned_previews") or [],
            "collaboration_dialogue": order_payload.get("collaboration_dialogue") or [],
            "transcript": transcript,
            "started_at": _dt.datetime.fromtimestamp(started).isoformat(timespec="seconds"),
            "completed_at": _dt.datetime.now().isoformat(timespec="seconds"),
        }
        if bridge_report and bridge_report.exists():
            bridge_text = bridge_report.read_text(encoding="utf-8", errors="replace")
            record["bridge_report_preview"] = bridge_text[:2500]
            _assert_no_secret_or_temp(bridge_text)
        _assert_no_secret_or_temp(record)
        report_path = _write_report(record)
        state["report_path"] = str(report_path)
        state["done"] = True
        desktop.QTimer.singleShot(500, app.quit)

    def poll() -> None:
        if not state["sent"]:
            return
        thread = getattr(win.chat_panel, "_chat_thread", None)
        running = bool(thread and thread.isRunning())
        transcript = win.chat_panel.transcript.toPlainText()
        bridge_report = _latest_report_after(started)
        if (
            not running
            and bridge_report
            and "Trading Dashboard bridge returned" in transcript
            and "Meeting Room updated:" in transcript
        ):
            finish("PASS")
            return
        if time.time() - started > 120:
            finish("FAIL_TIMEOUT")

    desktop.QTimer.singleShot(700, send_prompt)
    poll_timer = desktop.QTimer()
    poll_timer.timeout.connect(poll)
    poll_timer.start(500)

    app.exec()
    if not state["done"]:
        finish("FAIL_APP_EXITED_EARLY")

    report_payload = _read_json(Path(state["report_path"]))
    transcript = str(report_payload.get("transcript") or "")
    route = report_payload.get("prompt_route") or {}
    stations = report_payload.get("station_details") or []
    require(report_payload.get("status") == "PASS", f"real UI test did not pass: {report_payload.get('status')}")
    require(route.get("task_type") == "trading-dashboard", f"wrong task type: {route}")
    require(route.get("bridge_key") == "trading_dashboard", f"wrong bridge key: {route}")
    require(any(station.get("skill") == "Trading Dashboard Bridge Skill" for station in stations), "Trading Dashboard station missing")
    require("You: " + PROMPT in transcript, "transcript missing user prompt")
    require("Meeting Room selected:" in transcript, "transcript missing Meeting Room selection")
    require("Trading Dashboard bridge returned" in transcript, "transcript missing bridge return")
    require(report_payload.get("bridge_report_path"), "bridge report missing")
    print(state["report_path"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
