#!/usr/bin/env python3
"""Run a 20-job Engel AI UI input matrix through Meeting Room devices.

The prompts are user-style UI inputs. The runner uses the real
AgentChatPanel send path, while replacing the provider chat worker with a
bounded deterministic reply so the test isolates UI -> Meeting Room ->
device worker -> artifact behavior from provider/network chat latency.
"""
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
    {
        "label": "PDF_DEVICE_FLOW",
        "prompt": (
            "ENGELTRAIN01 make me a PDF field report showing Engel UI input, Meeting Room "
            "routing, Alpha and Beta phone worker returns, and the human review gate."
        ),
    },
    {
        "label": "PDF_SAFETY",
        "prompt": (
            "ENGELTRAIN02 make me a PDF safety checklist for device-first agents, WiFi "
            "jobs, no source mutation, no trusted-memory writes, and review-only returns."
        ),
    },
    {
        "label": "GAME_NODE_COURIER",
        "prompt": (
            "ENGELTRAIN03 create a video game called Engel Node Courier where phone agents "
            "carry neon packets across a compact dashboard without dropping routes."
        ),
    },
    {
        "label": "GAME_REVIEW_GATE",
        "prompt": (
            "ENGELTRAIN04 create a video game called Review Gate Runner where an Engel "
            "worker collects approved artifacts and avoids unsafe auto-apply blocks."
        ),
    },
    {
        "label": "LANG_MAIN_UI",
        "prompt": (
            "ENGELTRAIN05 lets work on the language for this app: write clean labels for "
            "the main Engel AI input, Meeting Room status, WiFi device returns, and results."
        ),
    },
    {
        "label": "LANG_ERRORS",
        "prompt": (
            "ENGELTRAIN06 lets work on the app language for error states: not paired, "
            "offline worker, stale phone, waiting for result, and review required."
        ),
    },
    {
        "label": "RESEARCH_DASHBOARDS",
        "prompt": (
            "ENGELTRAIN07 search internet for local-first multi-device agent dashboard "
            "patterns and summarize what Engel AI should consider later."
        ),
    },
    {
        "label": "RESEARCH_ANDROID",
        "prompt": (
            "ENGELTRAIN08 search online for Android background worker reliability ideas "
            "for a local WiFi agent app and summarize practical patterns."
        ),
    },
    {
        "label": "CODE_RECEIPT",
        "prompt": (
            "ENGELTRAIN09 write code for a small Engel job receipt formatter that prints "
            "worker, transport, artifact kind, file count, and review status."
        ),
    },
    {
        "label": "CODE_SCORE",
        "prompt": (
            "ENGELTRAIN10 write code for a device capability score helper that picks a "
            "phone worker based on allowed jobs, freshness, and preferred task type."
        ),
    },
    {
        "label": "FILE_HANDOFF",
        "prompt": (
            "ENGELTRAIN11 make this file and put it here: a Meeting Room handoff note for "
            "agents that explains user input, auto-selection, and review-only output."
        ),
    },
    {
        "label": "FILE_INDEX",
        "prompt": (
            "ENGELTRAIN12 create file for a compact artifact index that lists PDF, game, "
            "language, research, code, and file outputs from a 20-job test."
        ),
    },
    {
        "label": "PDF_GRAPH",
        "prompt": (
            "ENGELTRAIN13 make me a PDF graph summary for device-to-agent routing, showing "
            "which phone should handle code, report formatting, research, and labels."
        ),
    },
    {
        "label": "LANG_WAKE",
        "prompt": (
            "ENGELTRAIN14 app language pass for phone wake and pairing states: ready, "
            "stale, waking, paired over WiFi, returned result, and needs review."
        ),
    },
    {
        "label": "RESEARCH_PAIRING",
        "prompt": (
            "ENGELTRAIN15 search internet for mobile LAN pairing and heartbeat design "
            "patterns that could help Engel phone workers stay connected."
        ),
    },
    {
        "label": "CODE_HEALTH",
        "prompt": (
            "ENGELTRAIN16 write code for a Python helper that normalizes worker health rows "
            "from heartbeat age, transport list, battery label, and status."
        ),
    },
    {
        "label": "GAME_ROUTER",
        "prompt": (
            "ENGELTRAIN17 create a video game called Router Lab where Engel chooses the "
            "best phone worker for each packet before the timer runs out."
        ),
    },
    {
        "label": "FILE_SAFE_RESULTS",
        "prompt": (
            "ENGELTRAIN18 make this file and put it here: safe executable results rules "
            "for agents, including local artifacts only and no auto-apply."
        ),
    },
    {
        "label": "PDF_OFFLOAD",
        "prompt": (
            "ENGELTRAIN19 make me a PDF about keeping main computer usage down by sending "
            "routine research, code drafts, report formatting, and labels to phone agents."
        ),
    },
    {
        "label": "RESEARCH_PHONE_CREATION",
        "prompt": (
            "ENGELTRAIN20 search online for phone-based creation tools and plugins that "
            "could help agents draft code, documents, and compact research briefs."
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
                "Engel AI accepted the user UI input and returned a bounded training reply for Meeting Room dispatch."
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
        new_returns = [path for path in after_returns if path.name not in before_returns]
        after_orders = _paths_since(ORDER_DIR, run_started - 2, "*.json")
        new_orders = [path for path in after_orders if path.name not in before_orders]
        after_artifacts = sorted(ARTIFACT_ROOT.glob("*"), key=lambda item: item.stat().st_mtime) if ARTIFACT_ROOT.exists() else []
        new_artifacts = [path for path in after_artifacts if str(path) not in before_artifacts and path.is_dir()]

        records.append(
            {
                "index": index,
                "label": label,
                "prompt": prompt,
                "ui_finished": finished,
                "new_orders": _summarize_orders(new_orders),
                "new_returns": _summarize_returns(new_returns),
                "new_artifacts": [_artifact_manifest(path) for path in new_artifacts],
            }
        )

    transcript_path = REPORT_DIR / f"ENGEL_UI_INPUT_20_JOB_MATRIX_{run_stamp}_transcript.txt"
    transcript_path.write_text(panel.transcript.toPlainText(), encoding="utf-8")
    receipt_path = REPORT_DIR / f"ENGEL_UI_INPUT_20_JOB_MATRIX_{run_stamp}.json"
    receipt = {
        "run_started": datetime.datetime.fromtimestamp(run_started).isoformat(timespec="seconds"),
        "run_finished": datetime.datetime.now().isoformat(timespec="seconds"),
        "route": "Engel AI UI input -> Meeting Room auto-select -> device workers -> executable artifacts",
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
