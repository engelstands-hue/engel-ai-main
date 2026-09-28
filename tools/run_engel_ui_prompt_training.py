#!/usr/bin/env python3
"""Run bounded Engel UI prompt training through a visible chat UI."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
os.chdir(ROOT)
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from engel_ui_prompt_training_support import (  # noqa: E402
    build_agent_proposals,
    build_device_selection,
    ensure_dirs,
    iso_now,
    prompt_bank,
    redact,
    stamp,
    write_plan,
    write_reports,
)


ORDER_DIR = ROOT / "runtime" / "meeting_room" / "main_ui_orders"
LLM_RECEIPT_DIR = ROOT / "reports" / "engel_standalone_chat_llm" / "chat_receipts"


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None


def _paths_since(root: Path, since_epoch: float, pattern: str) -> list[Path]:
    if not root.exists():
        return []
    return sorted(
        [path for path in root.glob(pattern) if path.is_file() and path.stat().st_mtime >= since_epoch],
        key=lambda item: item.stat().st_mtime,
    )


def _path_has_c_drive(paths: list[str]) -> bool:
    return any(Path(path).drive.lower() == "c:" for path in paths if path)


def _new_ip_literals_in_scripts() -> list[str]:
    script_paths = [
        ROOT / "tools" / "run_engel_ui_prompt_training.py",
        ROOT / "tools" / "run_engel_ui_chat_meeting_room_llm.py",
        ROOT / "tools" / "engel_ui_prompt_training_support.py",
        ROOT / "engel_flutter_main" / "lib" / "main.dart",
    ]
    hits: list[str] = []
    pattern = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
    ignored = {"127.0.0.1", "0.0.0.0"}
    for path in script_paths:
        if not path.exists():
            continue
        for index, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
            matches = set(pattern.findall(line))
            if matches - ignored:
                hits.append(f"{path}:{index}:{line.strip()}")
    return hits


def _summarize_order(path: Path) -> dict[str, Any]:
    payload = _load_json(path)
    payload = payload if isinstance(payload, dict) else {}
    return {
        "path": str(path),
        "order_id": payload.get("order_id"),
        "source": payload.get("source"),
        "job_type": payload.get("job_type"),
        "station_routes": payload.get("station_routes"),
        "station_details": payload.get("station_details"),
        "station_results": payload.get("station_results"),
        "returned_previews": payload.get("returned_previews"),
        "collaboration_dialogue_count": len(payload.get("collaboration_dialogue") or []),
    }


def _latest_llm_receipt_path(since_epoch: float) -> str:
    paths = _paths_since(LLM_RECEIPT_DIR, since_epoch - 2, "ENGEL_STANDALONE_CHAT_LLM_*.json")
    return str(paths[-1]) if paths else ""


def _receipt_local_only(path: str) -> bool:
    payload = _load_json(Path(path)) if path else {}
    if not isinstance(payload, dict):
        return False
    return bool(
        payload.get("requested_provider") == "local"
        and payload.get("provider_api_enabled") is False
        and payload.get("network_enabled") is False
        and payload.get("runtime_provider") == "local-rust-llama-cpp-cuda"
    )


def _make_local_chat_worker(timeout: int, max_tokens: int):
    import engel_desktop_v2 as desktop

    class StandaloneLocalChatWorker(desktop.QThread):
        finished = desktop.pyqtSignal(str)
        receipts: list[dict[str, Any]] = []

        def __init__(self, text: str, mode: str):
            super().__init__()
            self._text = text
            self._mode = mode

        def run(self) -> None:
            try:
                from run_engel_standalone_chat_llm import run_chat

                receipt = run_chat(
                    prompt=self._text,
                    timeout=timeout,
                    max_tokens=max_tokens,
                    temperature=0.15,
                )
                self.receipts.append(receipt)
                reply = str(receipt.get("assistant_reply") or receipt.get("assistant_output_text") or "").strip()
                if not reply:
                    reply = str(receipt.get("status") or "local LLM returned no readable reply")
                self.finished.emit(reply)
            except Exception as exc:
                self.finished.emit(f"local LLM error: {type(exc).__name__}: {exc}")

    return StandaloneLocalChatWorker


def run_training(mode: str, minutes: float, per_prompt_timeout: int, max_tokens: int, final_wait: bool) -> dict[str, Any]:
    ensure_dirs()
    write_plan()
    import engel_desktop_v2 as desktop
    import engel_agent_meeting_room as room

    desktop._ChatWorker = _make_local_chat_worker(per_prompt_timeout, max_tokens)

    app = desktop.QApplication.instance() or desktop.QApplication(sys.argv)
    try:
        app.setStyleSheet(desktop.STYLESHEET)
    except Exception:
        pass

    win = desktop.EngelDesktopV2()
    win.setWindowTitle(f"Engel AI UI Prompt Training - {mode}")
    win.resize(1240, 780)
    win.move(20, 40)
    meeting = room.AgentMeetingRoomWindow()
    meeting.resize(1120, 720)
    meeting.move(520, 80)
    win.show()
    meeting.show()
    win.raise_()
    win.activateWindow()
    try:
        win.chat_panel._set_mode("local")
    except Exception:
        pass
    app.processEvents()

    prompts = prompt_bank(mode)
    requested = len(prompts)
    run_id = f"engel_ui_prompt_training_{mode}_{stamp()}"
    started_epoch = time.time()
    started_mono = time.monotonic()
    deadline = started_mono + max(1.0, minutes * 60.0)
    interval = (minutes * 60.0 / max(1, requested)) if mode == "one-hour" else 0.0
    prompt_results: list[dict[str, Any]] = []
    blockers: list[str] = []

    for index, prompt in enumerate(prompts, start=1):
        if mode == "one-hour" and time.monotonic() >= deadline:
            blockers.append("one-hour deadline reached before all prompts were sent")
            break
        before_orders = {path.name for path in _paths_since(ORDER_DIR, started_epoch - 2, "MAIN-*.json")}
        prompt_started = time.time()
        before_transcript_len = len(win.chat_panel.transcript.toPlainText())
        win.chat_panel.msg_input.setText(prompt)
        win.chat_panel.send_btn.click()
        app.processEvents()
        timeout_at = time.monotonic() + per_prompt_timeout + 90
        status = "TIMEOUT"
        while time.monotonic() < timeout_at:
            app.processEvents()
            thread = getattr(win.chat_panel, "_chat_thread", None)
            running = bool(thread and thread.isRunning())
            if not running and bool(win.chat_panel.send_btn.isEnabled()):
                transcript = win.chat_panel.transcript.toPlainText()
                if len(transcript) > before_transcript_len and "Meeting Room:" in transcript[before_transcript_len:]:
                    status = "DONE"
                    break
            time.sleep(0.2)
        app.processEvents()
        after_orders = _paths_since(ORDER_DIR, started_epoch - 2, "MAIN-*.json")
        new_orders = [path for path in after_orders if path.name not in before_orders]
        order_summary = [_summarize_order(path) for path in new_orders]
        latest_receipt = _latest_llm_receipt_path(prompt_started)
        if status != "DONE":
            blockers.append(f"prompt {index} timed out or did not return through Meeting Room")
        if not latest_receipt:
            blockers.append(f"prompt {index} did not create a local LLM receipt")
        prompt_results.append(
            {
                "prompt_index": index,
                "prompt": prompt,
                "status": status,
                "duration_seconds": round(time.time() - prompt_started, 3),
                "order_id": order_summary[-1].get("order_id") if order_summary else "",
                "orders": order_summary,
                "local_llm_receipt_path": latest_receipt,
                "local_llm_only": _receipt_local_only(latest_receipt),
            }
        )
        print(
            json.dumps(
                {
                    "event": "prompt_complete",
                    "run_id": run_id,
                    "mode": mode,
                    "index": index,
                    "requested": requested,
                    "status": status,
                    "order_id": prompt_results[-1]["order_id"],
                    "local_llm_receipt": latest_receipt,
                    "seconds_to_deadline": int(max(0, deadline - time.monotonic())),
                },
                sort_keys=True,
            ),
            flush=True,
        )
        if mode == "one-hour":
            scheduled_next = started_mono + interval * index
            while time.monotonic() < scheduled_next and time.monotonic() < deadline:
                app.processEvents()
                remaining = min(scheduled_next, deadline) - time.monotonic()
                if remaining > 20:
                    print(
                        json.dumps(
                            {
                                "event": "paced_wait",
                                "run_id": run_id,
                                "completed_prompts": index,
                                "seconds_to_next_prompt": int(remaining),
                                "seconds_to_deadline": int(max(0, deadline - time.monotonic())),
                            },
                            sort_keys=True,
                        ),
                        flush=True,
                    )
                time.sleep(min(10.0, max(0.5, remaining)))

    if mode == "one-hour" and final_wait:
        while time.monotonic() < deadline:
            app.processEvents()
            remaining = deadline - time.monotonic()
            print(
                json.dumps(
                    {
                        "event": "final_wait",
                        "run_id": run_id,
                        "completed_prompts": len(prompt_results),
                        "seconds_to_deadline": int(remaining),
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
            time.sleep(min(30.0, max(0.5, remaining)))

    try:
        meeting._reload_state_from_disk()
    except Exception:
        pass
    app.processEvents()
    transcript_path = ROOT / "reports" / "codex_bridge" / f"ENGEL_UI_PROMPT_TRAINING_{mode}_{stamp()}_transcript.txt"
    transcript_path.parent.mkdir(parents=True, exist_ok=True)
    transcript_path.write_text(win.chat_panel.transcript.toPlainText(), encoding="utf-8")
    try:
        win.close()
        meeting.close()
        app.processEvents()
    except Exception:
        pass

    order_ids = [str(item.get("order_id") or "") for item in prompt_results if item.get("order_id")]
    selection = build_device_selection(run_id, order_ids)
    proposals = build_agent_proposals(selection)
    output_files = [
        str(ROOT / "reports" / "codex_bridge" / "ENGEL_UI_PROMPT_TRAINING_PLAN.md"),
        str(transcript_path),
        str(ROOT / "memory" / "training" / "ENGEL_UI_PROMPT_TRAINING_SESSION.json"),
        str(ROOT / "memory" / "training" / "ENGEL_AGENT_MEETING_ROOM_DEVICE_SELECTION.json"),
        str(ROOT / "memory" / "training" / "ENGEL_AGENT_MEETING_ROOM_AGENT_PROPOSALS.json"),
    ]
    ip_hits = _new_ip_literals_in_scripts()
    summary = {
        "prompts_requested": requested,
        "prompts_completed": sum(1 for item in prompt_results if item.get("status") == "DONE"),
        "meeting_room_order_count": len(order_ids),
        "local_llm_only": all(item.get("local_llm_only") for item in prompt_results) if prompt_results else False,
        "no_provider_api": all(item.get("local_llm_only") for item in prompt_results) if prompt_results else False,
        "device_count": len(selection.get("devices") or []),
        "no_c_drive_output_paths": not _path_has_c_drive(output_files),
        "no_hard_coded_ips": not ip_hits,
        "hard_coded_ip_hits": ip_hits,
        "hidden_persistent_worker_started": False,
    }
    if ip_hits:
        blockers.append("new training scripts contain IP literals")
    if summary["prompts_completed"] != len(prompt_results) or not prompt_results:
        blockers.append("not every sent prompt completed through the visible chat path")
    if not summary["local_llm_only"]:
        blockers.append("one or more local LLM receipts did not prove local-only mode")
    if summary["meeting_room_order_count"] < len(prompt_results):
        blockers.append("one or more prompts did not create Meeting Room orders")
    status = "PASS" if not blockers else "FAIL"
    receipt = {
        "schema": "engel_ui_prompt_training_session_v1",
        "run_id": run_id,
        "mode": mode,
        "status": status,
        "started_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(started_epoch)),
        "finished_at_utc": iso_now(),
        "requested_minutes": minutes,
        "actual_duration_seconds": round(time.monotonic() - started_mono, 3),
        "ui_path_used": "visible engel_desktop_v2.AgentChatPanel send button; Flutter main chat is wired to the same local LLM + Meeting Room wrapper",
        "local_llm_runner": str(ROOT / "tools" / "run_engel_standalone_chat_llm.py"),
        "meeting_room_route": "submit_order_from_engel_main_ui -> complete_order_from_engel_main_ui",
        "device_selection": selection,
        "agent_proposals": proposals,
        "prompt_results": prompt_results,
        "summary": summary,
        "blockers": blockers,
        "output_files": output_files,
    }
    paths = write_reports(receipt)
    print(json.dumps({"event": "training_complete", "receipt_status": status, "report": paths.get("report"), "summary": summary}, indent=2), flush=True)
    return receipt


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["smoke", "one-hour"], required=True)
    parser.add_argument("--minutes", type=float, default=None)
    parser.add_argument("--per-prompt-timeout", type=int, default=650)
    parser.add_argument("--max-tokens", type=int, default=420)
    parser.add_argument("--skip-final-wait", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    minutes = args.minutes
    if minutes is None:
        minutes = 60.0 if args.mode == "one-hour" else 10.0
    final_wait = args.mode == "one-hour" and not args.skip_final_wait
    receipt = run_training(
        mode=args.mode,
        minutes=minutes,
        per_prompt_timeout=max(30, args.per_prompt_timeout),
        max_tokens=max(80, args.max_tokens),
        final_wait=final_wait,
    )
    print(json.dumps(redact(receipt), indent=2), flush=True)
    return 0 if receipt.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
