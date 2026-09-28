#!/usr/bin/env python3
"""Run plain user-style Engel AI UI prompts through Meeting Room devices."""
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
ORDER_DIR = ROOT / "runtime" / "meeting_room" / "main_ui_orders"
REPORT_DIR = ROOT / "reports" / "meeting_rooms"


PROMPTS = [
    {"label": "PDF_FLOW", "prompt": "Make me a PDF that explains how Engel sends work to phone agents."},
    {"label": "PDF_SAFETY", "prompt": "Make a PDF checklist for keeping phone worker jobs safe."},
    {"label": "GAME_PACKET", "prompt": "Create a simple video game where I move a green packet through routes."},
    {"label": "GAME_WORKER", "prompt": "Create a video game about choosing the best worker for a task."},
    {"label": "LANG_ROOM", "prompt": "Help me improve the wording for the Meeting Room screen."},
    {"label": "LANG_OFFLINE", "prompt": "Write clearer error messages for when a phone is offline or not paired."},
    {"label": "RESEARCH_DASHBOARD", "prompt": "Search online for ideas for local-first agent dashboards."},
    {"label": "RESEARCH_ANDROID", "prompt": "Search internet for ways Android apps can stay reliable on WiFi."},
    {"label": "CODE_RECEIPT", "prompt": "Write Python code for a tiny receipt formatter."},
    {"label": "CODE_SCORE", "prompt": "Write code for scoring which phone should get a job."},
    {"label": "FILE_FLOW", "prompt": "Make this file and put it here: a short note about how jobs move through Engel."},
    {"label": "FILE_INDEX", "prompt": "Create file with an index of today's Engel UI test outputs."},
    {"label": "PDF_DEVICE_GRAPH", "prompt": "Make me a PDF graph summary of which device handles which kind of task."},
    {"label": "LANG_WAKE", "prompt": "Help with app wording for waking phones and pairing them."},
    {"label": "RESEARCH_PAIRING", "prompt": "Search online for LAN pairing heartbeat ideas for mobile workers."},
    {"label": "CODE_HEALTH", "prompt": "Write code for normalizing worker health status."},
    {"label": "GAME_ALPHA_BETA", "prompt": "Create a video game about routing packets to Alpha and Beta."},
    {"label": "FILE_RULES", "prompt": "Make this file and put it here: safe results rules for phone agents."},
    {"label": "PDF_OFFLOAD", "prompt": "Make me a PDF about saving main computer resources by using phone workers."},
    {"label": "RESEARCH_CREATION", "prompt": "Search online for phone tools that help create code and documents."},
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


def _summarize_orders(paths: list[Path]) -> list[dict]:
    rows: list[dict] = []
    for path in paths:
        payload = _load_json(path)
        rows.append(
            {
                "file": str(path),
                "order_id": payload.get("order_id"),
                "job_type": payload.get("job_type"),
                "station_labels": payload.get("station_labels"),
                "station_routes": payload.get("station_routes"),
                "station_details": payload.get("station_details"),
                "station_results": payload.get("station_results"),
                "returned_previews": payload.get("returned_previews"),
            }
        )
    return rows


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
                "Engel AI accepted the plain user prompt and returned a bounded reply for Meeting Room dispatch."
            )

    desktop._ChatWorker = BoundedChatWorker

    app = desktop.QApplication.instance() or desktop.QApplication([])
    panel = desktop.AgentChatPanel()

    records: list[dict] = []
    for index, item in enumerate(PROMPTS, start=1):
        label = item["label"]
        prompt = item["prompt"]
        before_returns = {path.name for path in _paths_since(RETURNED_DIR, run_started - 2, "*.json")}
        before_orders = {path.name for path in _paths_since(ORDER_DIR, run_started - 2, "*.json")}
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
        after_orders = _paths_since(ORDER_DIR, run_started - 2, "*.json")
        after_artifacts = sorted(ARTIFACT_ROOT.glob("*"), key=lambda item: item.stat().st_mtime) if ARTIFACT_ROOT.exists() else []

        records.append(
            {
                "index": index,
                "label": label,
                "prompt": prompt,
                "ui_finished": finished,
                "new_orders": _summarize_orders([path for path in after_orders if path.name not in before_orders]),
                "new_returns": _summarize_returns([path for path in after_returns if path.name not in before_returns]),
                "new_artifacts": [
                    _artifact_manifest(path)
                    for path in after_artifacts
                    if str(path) not in before_artifacts and path.is_dir()
                ],
            }
        )

    transcript_path = REPORT_DIR / f"ENGEL_SIMPLE_USER_UI_INPUT_JOBS_{run_stamp}_transcript.txt"
    transcript_path.write_text(panel.transcript.toPlainText(), encoding="utf-8")
    receipt_path = REPORT_DIR / f"ENGEL_SIMPLE_USER_UI_INPUT_JOBS_{run_stamp}.json"
    receipt = {
        "run_started": datetime.datetime.fromtimestamp(run_started).isoformat(timespec="seconds"),
        "run_finished": datetime.datetime.now().isoformat(timespec="seconds"),
        "route": "plain Engel AI UI input -> Meeting Room auto-select -> device workers -> executable artifacts",
        "provider_mode": "bounded deterministic reply harness; real UI input and Meeting Room/device routing",
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
    job_types = sorted(
        {
            str(order.get("job_type"))
            for record in records
            for order in record.get("new_orders", [])
            if order.get("job_type")
        }
    )
    print(
        json.dumps(
            {
                "receipt": str(receipt_path),
                "transcript": str(transcript_path),
                "jobs": len(records),
                "workers_returned": workers,
                "artifact_kinds": kinds,
                "job_types": job_types,
                "all_ui_finished": all(record["ui_finished"] for record in records),
                "all_jobs_have_returns": all(bool(record["new_returns"]) for record in records),
                "all_jobs_have_artifacts": all(bool(record["new_artifacts"]) for record in records),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
