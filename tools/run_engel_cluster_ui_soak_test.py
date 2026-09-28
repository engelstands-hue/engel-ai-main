#!/usr/bin/env python3
"""Run a real Engel UI + Windows Sub-Engel cluster soak test.

This harness drives the native Qt Desktop V2 chat UI and Meeting Room window
with UI events, while separately probing the paired Windows Sub-Engel nodes
through the approved pair-gated controller client.

The safety boundary is intentional:
- UI widgets and Meeting Room order flow are real.
- Provider/model/browser/internet calls are not used.
- Android/queue/device dispatch is replaced with a local preview inside this
  test process so the all-agent coverage pass cannot mutate worker queues.
- Windows Sub-Engel node proof is real allowlisted HTTP diagnostics.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import shutil
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


NODE_IDS = ["DESKTOP-UE5A6GG"]
FULL_NODE_ACTIONS = [
    "node.status",
    "node.hardware",
    "node.safety",
    "node.controller",
    "net.status",
    "net.diagnose",
    "install.status",
    "install.preflight",
    "install.list_disks",
    "ui.dashboard",
    "ui.visible_status",
    "shared_room.status",
    "remote.status",
]
HEARTBEAT_ACTIONS = ["node.status", "net.status", "ui.visible_status", "shared_room.status", "remote.status"]


def utc_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def stamp() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def clip(text: Any, limit: int = 900) -> str:
    value = str(text or "").strip()
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 3)].rstrip() + "..."


class EventLog:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, event: str, **payload: Any) -> None:
        row = {"time_utc": utc_now(), "event": event, **payload}
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        print(json.dumps(row, ensure_ascii=False, sort_keys=True), flush=True)


def parse_node_stdout(response: dict[str, Any]) -> Any:
    result = response.get("result") if isinstance(response, dict) else {}
    stdout = result.get("stdout") if isinstance(result, dict) else ""
    if not isinstance(stdout, str):
        return stdout
    raw = stdout.strip()
    if not raw:
        return ""
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return clip(raw, 1200)


def compact_node_response(node_id: str, action: str, response: dict[str, Any]) -> dict[str, Any]:
    result = response.get("result") if isinstance(response, dict) else {}
    parsed = parse_node_stdout(response)
    summary: dict[str, Any] = {
        "node_id": node_id,
        "action": action,
        "ok": bool(response.get("ok")) if isinstance(response, dict) else False,
        "return_code": result.get("return_code") if isinstance(result, dict) else None,
    }
    if isinstance(parsed, dict):
        for key in ("hostname", "platform", "python", "role", "node_os", "remote_control"):
            if key in parsed:
                summary[key] = parsed[key]
        if "local_ips" in parsed:
            summary["local_ips"] = parsed["local_ips"]
        if action == "node.safety":
            summary["safety"] = parsed
        elif action.startswith("install."):
            summary["install"] = parsed
        elif action.startswith("net."):
            summary["network"] = clip(json.dumps(parsed, sort_keys=True), 1200)
        else:
            summary["parsed"] = parsed
    else:
        summary["stdout"] = parsed
    if not summary["ok"]:
        summary["error"] = response.get("error") if isinstance(response, dict) else "unknown response"
    return summary


def run_node_probe(actions: list[str], event_log: EventLog, phase: str) -> list[dict[str, Any]]:
    from engel_sub_node_remote_control import run_action

    out: list[dict[str, Any]] = []
    for node_id in NODE_IDS:
        for action in actions:
            started = time.time()
            response = run_action(action, node_kind="windows", node_id=node_id)
            elapsed = round(time.time() - started, 3)
            compact = compact_node_response(node_id, action, response)
            compact["elapsed_seconds"] = elapsed
            compact["phase"] = phase
            out.append(compact)
            event_log.write("node_probe", **compact)
    return out


def import_qtest_for_desktop(desktop: Any) -> Any:
    module = str(desktop.QApplication.__module__)
    if module.startswith("PyQt6"):
        from PyQt6.QtTest import QTest  # type: ignore
    else:
        from PySide6.QtTest import QTest  # type: ignore
    return QTest


def app_process_events(app: Any, seconds: float = 0.05) -> None:
    deadline = time.time() + max(0.0, seconds)
    while time.time() < deadline:
        app.processEvents()
        time.sleep(0.01)


def wait_for_chat_idle(app: Any, panel: Any, timeout_seconds: float, event_log: EventLog, label: str) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        app.processEvents()
        thread = getattr(panel, "_chat_thread", None)
        running = bool(thread and hasattr(thread, "isRunning") and thread.isRunning())
        if panel.send_btn.isEnabled() and not running:
            return True
        time.sleep(0.05)
    event_log.write("chat_timeout", label=label, timeout_seconds=timeout_seconds)
    return False


def safe_patch_meeting_room_dispatch(meeting_room: Any, event_log: EventLog) -> Any:
    original = meeting_room.dispatch_station_work

    def safe_dispatch(station: dict[str, Any], job_type: str, prompt: str) -> tuple[str, str]:
        equipment = str(station.get("equipment") or "")
        bridge = str(station.get("bridge") or "")
        skill = str(station.get("skill_label") or "")
        if "Windows Sub-Engel Node" in equipment or "Windows Sub-Engel Check-in Preview" in bridge:
            return original(station, job_type, prompt)
        event_log.write(
            "safe_station_preview",
            agent=str(station.get("type_label") or station.get("name") or "Agent"),
            skill=skill,
            equipment=equipment,
            bridge=bridge,
            job_type=job_type,
        )
        return (
            "Assigned",
            "Soak-test preview only: station received the order through the real Meeting Room UI path. "
            "Provider calls, worker queue mutation, source edits, and external browsing are disabled for this coverage pass.",
        )

    meeting_room.dispatch_station_work = safe_dispatch
    return original


def safe_patch_chat_worker(desktop: Any) -> Any:
    original = desktop._ChatWorker

    class SafeChatWorker(desktop.QThread):  # type: ignore[misc]
        finished = desktop.pyqtSignal(str)

        def __init__(self, text: str, mode: str):
            super().__init__()
            self._text = text
            self._mode = mode

        def run(self) -> None:
            self.finished.emit(
                "Engel local bridge is connected for the cluster UI soak test. "
                "I routed the user request through the Agent Meeting Room, kept the pass local, "
                "and returned a deterministic UI-visible result for verification."
            )

    desktop._ChatWorker = SafeChatWorker
    return original


def load_prompts(prompt_limit: int | None = None) -> list[tuple[str, str, str]]:
    import _meeting_room_agent_routing_test as routing

    prompts: list[tuple[str, str, str]] = []
    for agent, (skill, prompt) in routing.PROMPTS.items():
        safe_prompt = (
            f"UI coverage pass for {agent} using {skill}. "
            "Safety boundary: local Engel AI Main transcript and Meeting Room collaboration record only. "
            f"Task keywords: {prompt}"
        )
        prompts.append((agent, skill, safe_prompt))
    if prompt_limit is not None and prompt_limit >= 0:
        return prompts[:prompt_limit]
    return prompts


def reset_room_state_for_soak(meeting_room: Any, run_id: str, event_log: EventLog) -> Path | None:
    state_path = meeting_room.ROOM_STATE_FILE
    backup: Path | None = None
    if state_path.exists():
        backup = state_path.with_name(f"{state_path.stem}.{run_id}.backup.json")
        shutil.copy2(state_path, backup)
    fresh = meeting_room.RoomState(
        room_name="Cluster UI Soak Test Room",
        created_at=utc_now(),
        goal="Exercise every Meeting Room agent/skill and the two Windows Sub-Engel nodes through the UI.",
        project="Engel Windows Sub-Engel cluster",
        open_task="Two-hour UI-visible collaboration and diagnostics soak",
        safety_state="LOCAL UI + allowlisted Windows Sub-Engel diagnostics only",
        participants=[
            meeting_room.Participant(
                name="DESKTOP-UE5A6GG / Safety Review Skill",
                kind="agent",
                type_label="Safety Agent",
                skill_label="Safety Review Skill",
                equipment="Windows Sub-Engel Node - service / outbound",
                status="Waiting",
                bridge="Windows Sub-Engel Check-in Preview",
            ),
        ],
        messages=[],
    )
    meeting_room._save_state(fresh)
    event_log.write("room_state_reset", state_path=str(state_path), backup_path=str(backup or ""))
    return backup


def screenshot_window(window: Any, path: Path, event_log: EventLog, label: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok = bool(window.grab().save(str(path)))
    event_log.write("screenshot", label=label, path=str(path), ok=ok)


def click_meeting_room_button(app: Any, desktop: Any, QTest: Any, win: Any, event_log: EventLog) -> Any:
    button = None
    for candidate in win.findChildren(desktop.QPushButton):
        if str(candidate.text()).strip().lower() == "meeting room":
            button = candidate
            break
    if button is None:
        raise RuntimeError("Meeting Room button not found in Desktop V2")
    QTest.mouseClick(button, desktop.Qt.MouseButton.LeftButton)
    deadline = time.time() + 10
    while time.time() < deadline:
        app.processEvents()
        room_win = getattr(win, "_meeting_room_win", None)
        if room_win is not None and room_win.isVisible():
            event_log.write("meeting_room_opened_via_button")
            return room_win
        time.sleep(0.05)
    raise RuntimeError("Meeting Room window did not open after button click")


def send_chat_prompt(app: Any, desktop: Any, QTest: Any, panel: Any, prompt: str, label: str, event_log: EventLog) -> dict[str, Any]:
    before = panel.transcript.toPlainText()
    before_len = len(before)
    panel.msg_input.setFocus()
    panel.msg_input.clear()
    panel.msg_input.setText(prompt)
    app.processEvents()
    QTest.mouseClick(panel.send_btn, desktop.Qt.MouseButton.LeftButton)
    idle = wait_for_chat_idle(app, panel, timeout_seconds=90, event_log=event_log, label=label)
    transcript = panel.transcript.toPlainText()
    tail = transcript[before_len:]
    event = {
        "label": label,
        "idle": idle,
        "prompt_chars": len(prompt),
        "transcript_tail": clip(tail, 1800),
    }
    event_log.write("ui_chat_prompt", **event)
    return event


def latest_order_record() -> dict[str, Any]:
    import engel_agent_meeting_room as meeting_room

    order_dir = meeting_room.ORDER_DIR
    candidates = sorted(order_dir.glob("MAIN-*.json"), key=lambda p: p.stat().st_mtime)
    if not candidates:
        return {}
    try:
        data = json.loads(candidates[-1].read_text(encoding="utf-8"))
    except Exception:
        return {"path": str(candidates[-1]), "error": "unreadable"}
    data["path"] = str(candidates[-1])
    return data


def coverage_from_orders(order_paths: set[str]) -> dict[str, Any]:
    agents: set[str] = set()
    skills: set[str] = set()
    labels: set[str] = set()
    for raw_path in order_paths:
        path = Path(raw_path)
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for label in record.get("station_labels") or []:
            text = str(label)
            labels.add(text)
            if " / " in text:
                agent, skill = text.split(" / ", 1)
                agents.add(agent)
                skills.add(skill)
    return {
        "agent_count": len(agents),
        "skill_count": len(skills),
        "label_count": len(labels),
        "agents": sorted(agents),
        "skills": sorted(skills),
        "labels": sorted(labels),
    }


def write_report(
    report_path: Path,
    run_id: str,
    started_utc: str,
    ended_utc: str,
    duration_seconds: float,
    prompt_count: int,
    coverage: dict[str, Any],
    node_results: list[dict[str, Any]],
    event_log_path: Path,
    screenshot_paths: list[Path],
    transcript_paths: list[Path],
    room_state_path: Path,
    order_paths: set[str],
    pass_fail: dict[str, Any],
) -> None:
    node_ok = [r for r in node_results if r.get("ok")]
    node_fail = [r for r in node_results if not r.get("ok")]
    lines = [
        "# Engel Cluster UI Soak Test",
        "",
        f"- Run ID: `{run_id}`",
        f"- Started UTC: `{started_utc}`",
        f"- Ended UTC: `{ended_utc}`",
        f"- Duration seconds: `{duration_seconds:.1f}`",
        f"- UI prompts submitted: `{prompt_count}`",
        f"- Agent coverage: `{coverage.get('agent_count')}`",
        f"- Skill coverage: `{coverage.get('skill_count')}`",
        f"- Meeting Room station labels observed: `{coverage.get('label_count')}`",
        f"- Windows node probe passes: `{len(node_ok)}`",
        f"- Windows node probe failures: `{len(node_fail)}`",
        "",
        "## Verdict",
        "",
        f"- Duration requirement met: `{pass_fail.get('duration_met')}`",
        f"- All requested Windows nodes live at final probe: `{pass_fail.get('nodes_live_final')}`",
        f"- UI produced Meeting Room chat/order evidence: `{pass_fail.get('ui_evidence')}`",
        f"- Agent/skill coverage threshold met: `{pass_fail.get('coverage_met')}`",
        f"- Overall complete: `{pass_fail.get('complete')}`",
        "",
        "## Proof Files",
        "",
        f"- Event log: `{event_log_path}`",
        f"- Room state: `{room_state_path}`",
        f"- Order files observed: `{len(order_paths)}` under `runtime/meeting_room/main_ui_orders`",
    ]
    for screenshot in screenshot_paths:
        lines.append(f"- Screenshot: `{screenshot}`")
    for transcript in transcript_paths:
        lines.append(f"- Transcript: `{transcript}`")
    lines += [
        "",
        "## Windows Node Results",
        "",
    ]
    for node_id in NODE_IDS:
        latest = [r for r in node_results if r.get("node_id") == node_id and r.get("phase") == "final"]
        ok_count = sum(1 for r in node_results if r.get("node_id") == node_id and r.get("ok"))
        fail_count = sum(1 for r in node_results if r.get("node_id") == node_id and not r.get("ok"))
        lines.append(f"### {node_id}")
        lines.append("")
        lines.append(f"- Total ok: `{ok_count}`")
        lines.append(f"- Total fail: `{fail_count}`")
        for row in latest:
            bits = [f"`{row.get('action')}` ok=`{row.get('ok')}`"]
            if row.get("hostname"):
                bits.append(f"hostname=`{row.get('hostname')}`")
            if row.get("platform"):
                bits.append(f"platform=`{row.get('platform')}`")
            if row.get("local_ips"):
                bits.append(f"ips=`{row.get('local_ips')}`")
            lines.append("- " + " ".join(bits))
        lines.append("")
    lines += [
        "## Agent Coverage",
        "",
        "Agents observed:",
        "",
    ]
    for agent in coverage.get("agents") or []:
        lines.append(f"- {agent}")
    lines += ["", "Skills observed:", ""]
    for skill in coverage.get("skills") or []:
        lines.append(f"- {skill}")
    lines += [
        "",
        "## Safety Boundary",
        "",
        "- UI widgets and Meeting Room order flow were exercised live.",
        "- Windows node diagnostics used only the existing pair-gated allowlist.",
        "- Provider calls, live web browsing, Android worker queue mutation, source edits, and autonomous loops were not used.",
        "- Meeting Room Windows station dispatch remains preview/staging only; real Windows proof is the repeated allowlisted node diagnostics in this report.",
        "",
    ]
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Engel UI cluster soak test")
    parser.add_argument("--duration-seconds", type=int, default=7200)
    parser.add_argument("--heartbeat-seconds", type=int, default=300)
    parser.add_argument("--prompt-limit", type=int, default=-1, help="debug only; -1 means all prompts")
    parser.add_argument("--chat-timeout-seconds", type=int, default=90)
    args = parser.parse_args(argv)

    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    os.environ["ENGEL_MEETING_ROOM_ANDROID_RETURN_WAIT_SECONDS"] = "0"

    run_id = stamp()
    run_dir = ROOT / "reports" / "cluster_ui_soak" / run_id
    runtime_dir = ROOT / "runtime" / "cluster_ui_soak" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    runtime_dir.mkdir(parents=True, exist_ok=True)
    event_log = EventLog(runtime_dir / "events.jsonl")
    started_utc = utc_now()
    started = time.time()
    event_log.write("soak_started", run_id=run_id, duration_seconds=args.duration_seconds)

    import engel_agent_meeting_room as meeting_room
    import engel_desktop_v2 as desktop

    original_dispatch = safe_patch_meeting_room_dispatch(meeting_room, event_log)
    original_worker = safe_patch_chat_worker(desktop)
    reset_room_state_for_soak(meeting_room, run_id, event_log)

    app = desktop.QApplication.instance() or desktop.QApplication([])
    app.setStyleSheet(desktop.STYLESHEET)
    QTest = import_qtest_for_desktop(desktop)

    win = desktop.EngelDesktopV2()
    win.setWindowTitle("Engel AI - Cluster UI Soak Test")
    win.show()
    win.raise_()
    win.activateWindow()
    app_process_events(app, 0.5)
    screenshots: list[Path] = []
    first_shot = run_dir / "desktop_start.png"
    screenshot_window(win, first_shot, event_log, "desktop_start")
    screenshots.append(first_shot)

    room_win = click_meeting_room_button(app, desktop, QTest, win, event_log)
    app_process_events(app, 0.5)
    room_start = run_dir / "meeting_room_start.png"
    screenshot_window(room_win, room_start, event_log, "meeting_room_start")
    screenshots.append(room_start)

    panel = win.chat_panel
    prompts = load_prompts(None if args.prompt_limit < 0 else args.prompt_limit)
    order_paths: set[str] = set()
    node_results: list[dict[str, Any]] = []

    node_results.extend(run_node_probe(FULL_NODE_ACTIONS, event_log, phase="initial"))

    # A UI-visible cluster message before the coverage pass.
    cluster_intro = (
        "Run a real Windows Sub-Engel collaboration test using DESKTOP-UE5A6GG. "
        "Show the Agent Meeting Room communication, keep actions allowlisted, "
        "and compare what this live node can safely do."
    )
    send_chat_prompt(app, desktop, QTest, panel, cluster_intro, "cluster_intro", event_log)
    latest = latest_order_record()
    if latest.get("path"):
        order_paths.add(str(latest["path"]))

    for index, (agent, skill, prompt) in enumerate(prompts, 1):
        label = f"coverage_{index:03d}_{agent}_{skill}"
        event_log.write("coverage_prompt_start", index=index, total=len(prompts), agent=agent, skill=skill)
        send_chat_prompt(app, desktop, QTest, panel, prompt, label, event_log)
        latest = latest_order_record()
        if latest.get("path"):
            order_paths.add(str(latest["path"]))
        if index in {1, len(prompts)} or index % 10 == 0:
            shot = run_dir / f"desktop_coverage_{index:03d}.png"
            screenshot_window(win, shot, event_log, f"desktop_coverage_{index:03d}")
            screenshots.append(shot)
            if getattr(win, "_meeting_room_win", None) is not None:
                room_shot = run_dir / f"meeting_room_coverage_{index:03d}.png"
                screenshot_window(win._meeting_room_win, room_shot, event_log, f"meeting_room_coverage_{index:03d}")
                screenshots.append(room_shot)

    coverage = coverage_from_orders(order_paths)
    event_log.write(
        "coverage_complete",
        prompt_count=len(prompts),
        agent_count=coverage["agent_count"],
        skill_count=coverage["skill_count"],
        label_count=coverage["label_count"],
    )

    next_heartbeat = time.time()
    heartbeat_index = 0
    while time.time() - started < args.duration_seconds:
        app.processEvents()
        now = time.time()
        if now >= next_heartbeat:
            heartbeat_index += 1
            phase = f"heartbeat_{heartbeat_index:03d}"
            event_log.write(
                "heartbeat_start",
                heartbeat=heartbeat_index,
                elapsed_seconds=round(now - started, 1),
                remaining_seconds=max(0, round(args.duration_seconds - (now - started), 1)),
            )
            node_results.extend(run_node_probe(HEARTBEAT_ACTIONS, event_log, phase=phase))
            heartbeat_prompt = (
                f"Cluster heartbeat {heartbeat_index}: record current Windows Sub-Engel status for "
                "DESKTOP-UE5A6GG in the Agent Meeting Room. "
                "Keep this as communication/proof only; do not start runtime workers."
            )
            send_chat_prompt(app, desktop, QTest, panel, heartbeat_prompt, phase, event_log)
            latest = latest_order_record()
            if latest.get("path"):
                order_paths.add(str(latest["path"]))
            if getattr(win, "_meeting_room_win", None) is not None:
                win._meeting_room_win._reload_state_from_disk()
            if heartbeat_index == 1 or heartbeat_index % 3 == 0:
                shot = run_dir / f"desktop_{phase}.png"
                screenshot_window(win, shot, event_log, f"desktop_{phase}")
                screenshots.append(shot)
                if getattr(win, "_meeting_room_win", None) is not None:
                    room_shot = run_dir / f"meeting_room_{phase}.png"
                    screenshot_window(win._meeting_room_win, room_shot, event_log, f"meeting_room_{phase}")
                    screenshots.append(room_shot)
            next_heartbeat = now + max(30, args.heartbeat_seconds)
        time.sleep(0.2)

    node_results.extend(run_node_probe(FULL_NODE_ACTIONS, event_log, phase="final"))
    final_prompt = (
        "Final cluster soak summary: show that the two Windows Sub-Engel devices stayed reachable, "
        "the Meeting Room routed every agent/skill coverage prompt, and the collaboration remained "
        "inside the approved safety boundary."
    )
    send_chat_prompt(app, desktop, QTest, panel, final_prompt, "final_summary", event_log)
    latest = latest_order_record()
    if latest.get("path"):
        order_paths.add(str(latest["path"]))

    final_desktop = run_dir / "desktop_final.png"
    screenshot_window(win, final_desktop, event_log, "desktop_final")
    screenshots.append(final_desktop)
    transcript_paths: list[Path] = []
    main_transcript = panel.transcript.toPlainText()
    main_transcript_path = run_dir / "engel_ai_main_chat_transcript.txt"
    main_transcript_path.write_text(main_transcript, encoding="utf-8", newline="\n")
    transcript_paths.append(main_transcript_path)
    event_log.write("main_chat_transcript_saved", path=str(main_transcript_path), chars=len(main_transcript))
    if getattr(win, "_meeting_room_win", None) is not None:
        win._meeting_room_win._reload_state_from_disk()
        final_room = run_dir / "meeting_room_final.png"
        screenshot_window(win._meeting_room_win, final_room, event_log, "meeting_room_final")
        screenshots.append(final_room)
        room_transcript = win._meeting_room_win.center_panel.transcript.toPlainText()
        room_transcript_path = run_dir / "meeting_room_order_flow_transcript.txt"
        room_transcript_path.write_text(room_transcript, encoding="utf-8", newline="\n")
        transcript_paths.append(room_transcript_path)
        event_log.write("meeting_room_transcript_saved", path=str(room_transcript_path), chars=len(room_transcript))
        export_path = meeting_room.export_room_summary(win._meeting_room_win.state)
        event_log.write("meeting_room_export", path=str(export_path))

    ended_utc = utc_now()
    duration = time.time() - started
    coverage = coverage_from_orders(order_paths)
    final_live = {
        node_id: any(
            r.get("node_id") == node_id
            and r.get("phase") == "final"
            and r.get("action") == "node.status"
            and r.get("ok")
            for r in node_results
        )
        for node_id in NODE_IDS
    }
    pass_fail = {
        "duration_met": duration >= args.duration_seconds,
        "nodes_live_final": all(final_live.values()),
        "ui_evidence": (
            bool(order_paths)
            and main_transcript.count("You:") >= len(prompts)
            and "Engel:" in main_transcript
            and "Meeting Room:" in main_transcript
        ),
        "coverage_met": coverage.get("agent_count", 0) >= 50 and coverage.get("skill_count", 0) >= 50,
    }
    pass_fail["complete"] = all(pass_fail.values())

    report_path = ROOT / "reports" / "codex_bridge" / f"ENGEL_CLUSTER_UI_SOAK_TEST_{run_id}.md"
    write_report(
        report_path=report_path,
        run_id=run_id,
        started_utc=started_utc,
        ended_utc=ended_utc,
        duration_seconds=duration,
        prompt_count=len(prompts),
        coverage=coverage,
        node_results=node_results,
        event_log_path=event_log.path,
        screenshot_paths=screenshots,
        transcript_paths=transcript_paths,
        room_state_path=meeting_room.ROOM_STATE_FILE,
        order_paths=order_paths,
        pass_fail=pass_fail,
    )
    event_log.write("soak_finished", report_path=str(report_path), **pass_fail)

    desktop._ChatWorker = original_worker
    meeting_room.dispatch_station_work = original_dispatch
    app.processEvents()
    return 0 if pass_fail["complete"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
