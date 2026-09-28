#!/usr/bin/env python3
"""Run fresh Engel AI UI prompts through Meeting Room to device results."""
from __future__ import annotations

import datetime
import json
import os
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RETURNED_DIR = ROOT / "remote_workers" / "communication_queen_assignments" / "returned"
ARTIFACT_ROOT = ROOT / "artifacts" / "engel_ui_results"
REPORT_DIR = ROOT / "reports" / "meeting_rooms"


PROMPTS = [
    {
        "label": "PDF",
        "prompt": (
            "ENGELNEWPDF make me a PDF field guide for Engel AI job flow: user input, "
            "Meeting Room routing, phone worker selection, review gate, and artifact return."
        ),
    },
    {
        "label": "GAME",
        "prompt": (
            "ENGELNEWGAME create a video game called Engel Node Courier where a phone worker "
            "moves packets across a compact neon dashboard and avoids broken routes."
        ),
    },
    {
        "label": "LANGUAGE",
        "prompt": (
            "ENGELNEWLANG lets work on the language for this app: write clean labels for "
            "device-first agents, WiFi returns, review-required results, and finished artifacts."
        ),
    },
    {
        "label": "RESEARCH",
        "prompt": (
            "ENGELNEWRESEARCH search internet for useful local-first multi-device agent "
            "dashboard patterns and summarize ideas Engel AI could adapt later."
        ),
    },
    {
        "label": "CODE",
        "prompt": (
            "ENGELNEWCODE write code for a small Engel job receipt formatter that turns "
            "worker, transport, artifact kind, and review status into a readable status line."
        ),
    },
    {
        "label": "FILE",
        "prompt": (
            "ENGELNEWFILE make this file and put it here: a compact test note proving new "
            "Engel AI UI inputs can create fresh artifacts through the Meeting Room."
        ),
    },
]


def _paths_since(folder: Path, since: float, pattern: str) -> list[Path]:
    if not folder.exists():
        return []
    return sorted(
        [path for path in folder.glob(pattern) if path.stat().st_mtime >= since],
        key=lambda item: item.stat().st_mtime,
    )


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _summarize_returns(paths: list[Path]) -> list[dict]:
    rows: list[dict] = []
    for path in paths:
        payload = _load_json(path)
        caps = payload.get("device_capabilities") if isinstance(payload, dict) else {}
        caps = caps if isinstance(caps, dict) else {}
        conn = caps.get("connectivity") if isinstance(caps, dict) else {}
        conn = conn if isinstance(conn, dict) else {}
        rows.append(
            {
                "file": str(path),
                "worker_id": payload.get("worker_id"),
                "result_type": payload.get("result_type"),
                "packet_id": payload.get("packet_id"),
                "requires_review": payload.get("requires_review"),
                "safe_to_auto_apply": payload.get("safe_to_auto_apply"),
                "transports": conn.get("transports"),
                "preview": str(payload.get("draft_text") or "")[:260],
            }
        )
    return rows


def _artifact_manifest(folder: Path) -> dict:
    payload = _load_json(folder / "manifest.json")
    return {
        "artifact_dir": str(folder),
        "kind": payload.get("kind"),
        "files": payload.get("files", []),
        "safety": payload.get("safety", {}),
    }


def main() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("ENGEL_MEETING_ROOM_ANDROID_RETURN_WAIT_SECONDS", "45")
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    run_stamp = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
    run_started = time.time()

    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    from PySide6.QtCore import QObject, Signal
    import engel_desktop_v2 as desktop

    class BoundedChatWorker(QObject):
        finished = Signal(str)

        def __init__(self, text: str, mode: str):
            super().__init__()
            self.text = text
            self.mode = mode

        def isRunning(self) -> bool:
            return False

        def start(self) -> None:
            self.finished.emit(
                "Engel AI accepted the UI input and returned a bounded test reply for Meeting Room dispatch."
            )

    desktop._ChatWorker = BoundedChatWorker

    app = desktop.QApplication.instance() or desktop.QApplication([])
    panel = desktop.AgentChatPanel()

    records: list[dict] = []
    for item in PROMPTS:
        label = item["label"]
        prompt = item["prompt"]
        before_returns = {path.name for path in _paths_since(RETURNED_DIR, run_started - 2, "*.json")}
        before_artifacts = {str(path) for path in ARTIFACT_ROOT.glob("*")} if ARTIFACT_ROOT.exists() else set()
        before_result_count = panel.transcript.toPlainText().count("Engel Result:")

        panel.msg_input.setText(prompt)
        panel.send_btn.click()
        deadline = time.time() + 180
        finished = False
        while time.time() < deadline:
            app.processEvents()
            if panel.transcript.toPlainText().count("Engel Result:") > before_result_count:
                finished = True
                break
            time.sleep(0.2)

        app.processEvents()
        after_returns = _paths_since(RETURNED_DIR, run_started - 2, "*.json")
        new_returns = [path for path in after_returns if path.name not in before_returns]
        after_artifacts = sorted(ARTIFACT_ROOT.glob("*"), key=lambda item: item.stat().st_mtime) if ARTIFACT_ROOT.exists() else []
        new_artifacts = [path for path in after_artifacts if str(path) not in before_artifacts and path.is_dir()]

        records.append(
            {
                "label": label,
                "prompt": prompt,
                "ui_finished": finished,
                "new_returns": _summarize_returns(new_returns),
                "new_artifacts": [_artifact_manifest(path) for path in new_artifacts],
            }
        )

    transcript_path = REPORT_DIR / f"ENGEL_NEW_UI_INPUT_JOBS_{run_stamp}_transcript.txt"
    transcript_path.write_text(panel.transcript.toPlainText(), encoding="utf-8")
    receipt_path = REPORT_DIR / f"ENGEL_NEW_UI_INPUT_JOBS_{run_stamp}.json"
    receipt = {
        "run_started": datetime.datetime.fromtimestamp(run_started).isoformat(timespec="seconds"),
        "run_finished": datetime.datetime.now().isoformat(timespec="seconds"),
        "route": "Engel AI UI input -> Meeting Room -> device workers -> executable artifacts",
        "android_return_wait_seconds": os.environ.get("ENGEL_MEETING_ROOM_ANDROID_RETURN_WAIT_SECONDS"),
        "transcript": str(transcript_path),
        "records": records,
    }
    receipt_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")

    workers = sorted(
        {
            str(row.get("worker_id"))
            for record in records
            for row in record.get("new_returns", [])
            if row.get("worker_id")
        }
    )
    kinds = [artifact.get("kind") for record in records for artifact in record.get("new_artifacts", [])]
    print(
        json.dumps(
            {
                "receipt": str(receipt_path),
                "transcript": str(transcript_path),
                "jobs": len(records),
                "workers_returned": workers,
                "artifact_kinds": kinds,
                "all_ui_finished": all(record["ui_finished"] for record in records),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
