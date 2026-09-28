#!/usr/bin/env python3
"""Run visible Engel UI prompt-training test through the real chat input path."""
from __future__ import annotations

import datetime as _dt
import json
import os
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


PROMPTS = [
    "Make me a PDF about Engel prompt routes with one simple example.",
    "Create a yellow happy face image and save it for Engel.",
    "Write code for a tiny prompt route checker.",
    "Create a video game about routing signals.",
    "Create file with a short note about agent collaboration and put it here.",
    "Search internet for prompt engineering tips for Engel and save a research brief.",
]


def _paths_after(root: Path, pattern: str, started: float) -> list[Path]:
    if not root.exists():
        return []
    return sorted(
        [path for path in root.glob(pattern) if path.is_file() and path.stat().st_mtime >= started],
        key=lambda path: path.stat().st_mtime,
    )


def _dirs_after(root: Path, started: float) -> list[Path]:
    if not root.exists():
        return []
    return sorted(
        [path for path in root.iterdir() if path.is_dir() and path.stat().st_mtime >= started],
        key=lambda path: path.stat().st_mtime,
    )


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _artifact_files(path: Path) -> list[str]:
    try:
        return [str(item) for item in sorted(path.rglob("*")) if item.is_file()]
    except Exception:
        return []


def _write_report(record: dict[str, Any]) -> Path:
    reports_dir = ROOT / "reports" / "meeting_rooms"
    reports_dir.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().strftime("%Y%m%dT%H%M%S")
    path = reports_dir / f"ENGEL_VISIBLE_SIMPLE_PROMPT_TRAINING_{stamp}.json"
    md_path = path.with_suffix(".md")
    lines = [
        "# Engel Visible Simple Prompt Training",
        "",
        f"- Status: {record.get('status')}",
        f"- Started: {record.get('started_at')}",
        f"- Completed: {record.get('completed_at')}",
        f"- Desktop screenshot: {record.get('desktop_screenshot')}",
        f"- Meeting Room screenshot: {record.get('meeting_room_screenshot')}",
        "",
        "## Prompts",
    ]
    for item in record.get("prompt_results", []):
        lines.append(f"- {item.get('status')}: {item.get('prompt')}")
    lines += ["", "## Devices And Agents"]
    for usage in record.get("device_agent_usage", []):
        lines.append(
            f"- {usage.get('device')} -> {usage.get('agent')} / "
            f"{usage.get('skill')} [{usage.get('status')}]"
        )
    lines += ["", "## Artifacts"]
    for artifact in record.get("artifacts", []):
        lines.append(f"- {artifact.get('dir')}")
        for file_path in artifact.get("files", [])[:8]:
            lines.append(f"  - {file_path}")
    lines += ["", "## Collaboration Dialogue"]
    for turn in record.get("collaboration_dialogue", []):
        lines.append(f"- {turn.get('name')}: {turn.get('text')}")
    lines += ["", "## Transcript", "", "```text", str(record.get("transcript") or ""), "```"]
    path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    record["markdown_report_path"] = str(md_path)
    path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return path


def main() -> int:
    os.environ.setdefault("ENGEL_MEETING_ROOM_ANDROID_RETURN_WAIT_SECONDS", "12")
    os.environ.setdefault("ENGEL_EXECUTABLE_RESULTS_DIR", str(ROOT / "artifacts" / "engel_ui_results"))

    import engel_desktop_v2 as desktop
    import engel_agent_meeting_room as room

    if not desktop.HAS_QT or not room.HAS_QT:
        print("FAIL: Qt is not available for visible Engel UI training")
        return 1

    app = desktop.QApplication.instance() or desktop.QApplication(sys.argv)
    app.setStyleSheet(desktop.STYLESHEET)
    app.setWindowIcon(desktop._engel_icon())

    started = time.time()
    started_iso = _dt.datetime.fromtimestamp(started).isoformat(timespec="seconds")
    artifact_root = Path(os.environ["ENGEL_EXECUTABLE_RESULTS_DIR"])
    orders_root = ROOT / "runtime" / "meeting_room" / "main_ui_orders"

    win = desktop.EngelDesktopV2()
    win.resize(1220, 760)
    win.move(30, 40)
    meeting = room.AgentMeetingRoomWindow()
    meeting.resize(1260, 760)
    meeting.move(520, 70)
    win.show()
    meeting.show()
    win.raise_()
    win.activateWindow()

    state: dict[str, Any] = {
        "index": -1,
        "current_started": 0.0,
        "current_prompt": "",
        "prompt_results": [],
        "awaiting_completion": False,
        "done": False,
        "report_path": "",
    }

    def send_next() -> None:
        state["index"] += 1
        if state["index"] >= len(PROMPTS):
            finish("PASS")
            return
        prompt = PROMPTS[state["index"]]
        state["current_prompt"] = prompt
        state["current_started"] = time.time()
        state["awaiting_completion"] = True
        win.chat_panel.msg_input.setText(prompt)
        win.chat_panel.send_btn.click()

    def capture_prompt(status: str) -> None:
        if not state.get("awaiting_completion"):
            return
        state["awaiting_completion"] = False
        state["prompt_results"].append({
            "prompt": state.get("current_prompt"),
            "status": status,
            "elapsed_seconds": round(time.time() - float(state.get("current_started") or time.time()), 2),
        })

    def poll() -> None:
        if state["done"] or state["index"] < 0 or not state.get("awaiting_completion"):
            return
        thread = getattr(win.chat_panel, "_chat_thread", None)
        running = bool(thread and thread.isRunning())
        elapsed = time.time() - float(state.get("current_started") or time.time())
        if running:
            return
        if elapsed > 90:
            capture_prompt("TIMEOUT")
            desktop.QTimer.singleShot(500, send_next)
            return
        if elapsed < 1.5:
            return
        transcript = win.chat_panel.transcript.toPlainText()
        if str(state.get("current_prompt") or "") in transcript and win.chat_panel.send_btn.isEnabled():
            capture_prompt("DONE")
            desktop.QTimer.singleShot(800, send_next)

    def finish(status: str) -> None:
        if state["done"]:
            return
        state["done"] = True
        try:
            meeting._reload_state_from_disk()
        except Exception:
            pass
        app.processEvents()

        reports_dir = ROOT / "reports" / "meeting_rooms"
        reports_dir.mkdir(parents=True, exist_ok=True)
        stamp = _dt.datetime.now().strftime("%Y%m%dT%H%M%S")
        desktop_shot = reports_dir / f"ENGEL_VISIBLE_SIMPLE_PROMPT_TRAINING_DESKTOP_{stamp}.png"
        room_shot = reports_dir / f"ENGEL_VISIBLE_SIMPLE_PROMPT_TRAINING_ROOM_{stamp}.png"
        win.grab().save(str(desktop_shot))
        meeting.grab().save(str(room_shot))

        order_paths = _paths_after(orders_root, "*.json", started)
        orders = [_read_json(path) | {"path": str(path)} for path in order_paths]
        artifacts = [
            {"dir": str(path), "files": _artifact_files(path)}
            for path in _dirs_after(artifact_root, started)
        ]
        usage: list[dict[str, str]] = []
        dialogue: list[dict[str, Any]] = []
        for order in orders:
            details = order.get("station_details") if isinstance(order, dict) else []
            results = order.get("station_results") if isinstance(order, dict) else []
            results = results if isinstance(results, list) else []
            for index, detail in enumerate(details if isinstance(details, list) else []):
                if not isinstance(detail, dict):
                    continue
                usage.append({
                    "device": str(detail.get("device") or ""),
                    "agent": str(detail.get("agent") or ""),
                    "skill": str(detail.get("skill") or ""),
                    "status": str(results[index] if index < len(results) else ""),
                    "order_id": str(order.get("order_id") or ""),
                })
            turns = order.get("collaboration_dialogue")
            if isinstance(turns, list):
                dialogue.extend([turn for turn in turns if isinstance(turn, dict)])

        record = {
            "status": status,
            "started_at": started_iso,
            "completed_at": _dt.datetime.now().isoformat(timespec="seconds"),
            "prompts": PROMPTS,
            "prompt_results": state["prompt_results"],
            "desktop_screenshot": str(desktop_shot),
            "meeting_room_screenshot": str(room_shot),
            "orders": orders,
            "artifacts": artifacts,
            "device_agent_usage": usage,
            "collaboration_dialogue": dialogue,
            "transcript": win.chat_panel.transcript.toPlainText(),
        }
        if not artifacts:
            record["status"] = "FAIL_NO_ARTIFACTS"
        if not dialogue:
            record["status"] = "FAIL_NO_COLLABORATION_DIALOGUE"
        report = _write_report(record)
        state["report_path"] = str(report)
        desktop.QTimer.singleShot(1500, app.quit)

    desktop.QTimer.singleShot(900, send_next)
    timer = desktop.QTimer()
    timer.timeout.connect(poll)
    timer.start(500)
    desktop.QTimer.singleShot(8 * 60 * 1000, lambda: finish("FAIL_GLOBAL_TIMEOUT"))

    app.exec()
    if not state["done"]:
        finish("FAIL_APP_EXITED_EARLY")
    print(state["report_path"])
    report_text = Path(state["report_path"]).read_text(encoding="utf-8") if state["report_path"] else ""
    return 0 if '"status": "PASS"' in report_text else 1


if __name__ == "__main__":
    raise SystemExit(main())
