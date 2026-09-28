#!/usr/bin/env python3
"""Train/test Engel UI input recognition for one hour with real artifacts.

This runner sends plain user-style prompts through the real Engel Desktop V2
AgentChatPanel send path. The provider reply worker is replaced with a bounded
local reply so the run isolates:

Engel UI input -> Agent Meeting Room auto-select -> phone worker return -> local
artifact finalization.

The generated outputs are reviewable local artifacts. Phone worker returns stay
untrusted and are never auto-applied to source.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RETURNED_DIR = ROOT / "remote_workers" / "communication_queen_assignments" / "returned"
ARTIFACT_ROOT = ROOT / "artifacts" / "engel_ui_results"
ORDER_DIR = ROOT / "runtime" / "meeting_room" / "main_ui_orders"
REPORT_DIR = ROOT / "reports" / "meeting_rooms"
MEMORY_CANDIDATE_DIR = ROOT / "reports" / "memory_candidates"
LINK_STATE_PATH = ROOT / "remote_workers" / "lan_link_manager" / "session_state.json"


@dataclass(frozen=True)
class PromptItem:
    label: str
    kind: str
    expected_job_type: str
    expected_worker: str
    prompt: str


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0)


def utc_stamp() -> str:
    return utc_now().isoformat().replace("+00:00", "Z")


def local_stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%dT%H%M%S")


def safe_slug(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "_" for ch in value)
    return "_".join(part for part in cleaned.split("_") if part) or "engel_ui_creation_training"


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _paths_since(folder: Path, since: float, pattern: str) -> list[Path]:
    if not folder.exists():
        return []
    return sorted(
        [path for path in folder.glob(pattern) if path.stat().st_mtime >= since],
        key=lambda item: item.stat().st_mtime,
    )


def _artifact_manifest(folder: Path) -> dict[str, Any]:
    payload = _load_json(folder / "manifest.json")
    payload = payload if isinstance(payload, dict) else {}
    return {
        "artifact_dir": str(folder),
        "kind": payload.get("kind"),
        "files": payload.get("files", []),
        "safety": payload.get("safety", {}),
    }


def _summarize_returns(paths: list[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in paths:
        payload = _load_json(path)
        payload = payload if isinstance(payload, dict) else {}
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
                "preview": str(payload.get("draft_text") or "")[:360],
            }
        )
    return rows


def _summarize_orders(paths: list[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in paths:
        payload = _load_json(path)
        payload = payload if isinstance(payload, dict) else {}
        rows.append(
            {
                "file": str(path),
                "order_id": payload.get("order_id"),
                "order_text": payload.get("order_text"),
                "job_type": payload.get("job_type"),
                "station_labels": payload.get("station_labels"),
                "station_routes": payload.get("station_routes"),
                "station_details": payload.get("station_details"),
                "station_results": payload.get("station_results"),
                "returned_previews": payload.get("returned_previews"),
            }
        )
    return rows


def _link_state_snapshot() -> dict[str, Any]:
    state = _load_json(LINK_STATE_PATH)
    if not isinstance(state, dict):
        return {}
    workers = state.get("workers") if isinstance(state.get("workers"), dict) else {}
    clean_workers: dict[str, Any] = {}
    for worker_id, record in workers.items():
        if not isinstance(record, dict):
            continue
        identity = record.get("identity") if isinstance(record.get("identity"), dict) else {}
        clean_workers[str(worker_id)] = {
            "last_seen_utc": record.get("last_seen_utc"),
            "remote_address": identity.get("remote_address"),
            "current_mode": identity.get("current_mode"),
            "safe_to_auto_apply": record.get("safe_to_auto_apply"),
            "source_mutation": record.get("source_mutation"),
            "trusted_memory_write": record.get("trusted_memory_write"),
        }
    return {
        "last_seen_utc": state.get("last_seen_utc"),
        "workers": clean_workers,
        "safe_to_auto_apply": state.get("safe_to_auto_apply"),
        "source_mutation": state.get("source_mutation"),
        "trusted_memory_write": state.get("trusted_memory_write"),
        "phone_does_not_control_engel": state.get("phone_does_not_control_engel"),
    }


def build_prompt_bank(target_jobs: int) -> list[PromptItem]:
    pdf_topics = [
        "a field guide for how phone agents save main computer resources",
        "a checklist for safe review-only artifact creation",
        "a one-page map of Engel UI input to Meeting Room routing",
        "a quick guide for choosing Alpha or Beta for a job",
        "a status report on WiFi worker reliability",
        "a simple operator handoff for artifact review",
        "a compact guide to safe PDF and report requests",
        "a comparison of phone-worker tasks and main-PC tasks",
        "a quick start sheet for new Engel phone devices",
        "a recap of how executable results stay bounded",
        "a second-pass report on what the first UI training hour proved",
        "a follow-up checklist for prompts that imply games without saying game",
        "a before-and-after note on the fixed meeting-room maze routing bug",
        "a phone-first routing scorecard for Alpha and Beta",
        "a compact guide to checking real artifacts after each UI prompt",
        "a post-training handoff for improving simple user input recognition",
        "a safe operator guide for rerunning failed prompt cases",
        "a summary of which prompts should go to phone workers first",
        "a practical guide to testing artifact variety without duplicates",
        "a final readiness sheet for Engel UI creation requests",
    ]
    game_topics = [
        "a tiny route game where a green packet reaches the right phone",
        "a browser game where Alpha catches code packets and Beta catches reports",
        "a small dashboard game about avoiding unsafe auto-apply blocks",
        "a route puzzle game where jobs choose the best worker",
        "a neon courier game about carrying results back to Engel",
        "a worker selection game with phone battery and WiFi meters",
        "a compact game where agents unlock artifact rooms",
        "a packet sorting game with PDF, code, file, and research lanes",
        "a meeting-room maze where the verifier guards the final door",
        "a phone-agent timing game about returning before the job expires",
        "an upgraded meeting-room maze with device gates and verifier keys",
        "a playable prompt classifier game with PDF, code, and research doors",
        "a second-pass worker routing puzzle where Alpha and Beta trade lanes",
        "a timing runner where stale WiFi heartbeats slow the route",
        "a review gate arcade game where unsafe auto-apply blocks lose points",
        "a capability card puzzle where each phone unlocks matching jobs",
        "a local-first artifact courier game with receipt checkpoints",
        "a verifier maze where every result needs a manifest before exit",
        "a phone-first resource saver game with main-PC battery protection",
        "a creation-intent sorting game for simple Engel UI prompts",
    ]
    language_topics = [
        "offline phone warnings and not-paired messages",
        "the Meeting Room ready, waiting, assigned, and returned states",
        "main Engel UI result messages after an artifact is created",
        "phone wake and WiFi pairing labels",
        "short labels for device capability cards",
        "friendly text for review-required results",
        "plain words for code, PDF, file, game, language, and research jobs",
        "compact status copy for stale worker heartbeats",
        "button labels for opening artifacts and maps",
        "short descriptions for Alpha and Beta agent skills",
        "second-pass messages after a failed prompt is fixed and rerun",
        "friendly labels for corrected classifier behavior",
        "plain text that tells the user which phone handled the job",
        "short success messages for PDF, game, code, file, language, and research artifacts",
        "copy that explains why a phone return is review-only",
        "compact wording for artifact variety checks",
        "simple UI text for a corrected prompt rerun",
        "status labels for prompt recognized, routed, returned, and finalized",
        "operator notes when one prompt in a long run needs a fix",
        "clear user-facing wording for phone-first resource saving",
    ]
    research_topics = [
        "local-first multi-device agent dashboards",
        "Android app WiFi heartbeat reliability patterns",
        "safe review-only worker result designs",
        "phone-based code drafting tools for agents",
        "LAN pairing user experience patterns",
        "offline-first mobile worker queues",
        "bounded web research result formatting",
        "mobile artifact creation workflows",
        "agent task routing dashboards",
        "simple device capability scoring ideas",
        "prompt classifier design for artifact creation systems",
        "local-first workflow receipts for multi-device AI agents",
        "mobile worker reliability checks after long training runs",
        "human-readable artifact manifest patterns",
        "testing prompt intent recognition with varied user language",
        "bounded agent collaboration reports",
        "phone-first work distribution for desktop assistant apps",
        "review-only result handling in local automation tools",
        "UI patterns for showing which device did the work",
        "safe rerun workflows after a classifier bug is fixed",
    ]
    code_topics = [
        "a tiny Python function that scores phone workers by capability",
        "a Python receipt formatter for Engel artifact results",
        "a helper that groups jobs by artifact kind",
        "a status normalizer for worker heartbeat age",
        "a safe slug function for artifact folder names",
        "a small validator for review-required result manifests",
        "a table printer for device, agent, skill, and result",
        "a sorter that prioritizes WiFi phone workers before main PC",
        "a compact JSON summary writer for Meeting Room runs",
        "a route counter that counts PDF, code, game, file, language, and research jobs",
        "a classifier helper that detects maze and puzzle creation prompts",
        "a verifier that checks every training receipt has matching artifacts",
        "a tiny diff reporter for before-and-after prompt routing",
        "a worker score function that includes last_seen heartbeat freshness",
        "a manifest linter for Engel UI result folders",
        "a summary merger for first-run and correction-run receipts",
        "a prompt variety checker that flags duplicate artifact requests",
        "a route matrix printer for prompt kind, job type, worker, and artifact",
        "a safe artifact path checker for Engel UI outputs",
        "a training regression picker that reruns only failed prompt styles",
    ]
    file_topics = [
        "a short note explaining why Engel sends routine work to phones first",
        "a mini index of today's training artifacts",
        "safe result rules for phone agents",
        "a checklist for adding a new device to the worker tree",
        "a short Meeting Room operator note",
        "a device capability cheat sheet",
        "an artifact review checklist",
        "a phone-worker maintenance note",
        "a simple map legend for device-agent-skill choices",
        "a local-first safety reminder for Engel outputs",
        "a second-run artifact index that links first-hour lessons to new checks",
        "a fixed-prompt rerun note for the meeting-room maze case",
        "a prompt-writing cheat sheet for asking Engel to create things",
        "a phone-first routing note for future devices",
        "a review checklist for corrected classifier runs",
        "a small glossary of job type, artifact kind, worker, and station",
        "a safe rerun playbook for when one job fails in a long test",
        "a device assignment note that explains Alpha versus Beta choices",
        "a real-results inventory format for Engel UI training",
        "a memory note template for future training runs",
    ]

    groups = [
        ("pdf", "PDF", "format_report_draft", "android_worker_beta", "Make me a PDF about {topic}.", pdf_topics),
        ("game", "GAME", "draft_code_artifact", "android_worker_alpha", "Create {topic}.", game_topics),
        ("language", "LANG", "summarize_text", "android_worker_alpha", "Help me write clearer app wording for {topic}.", language_topics),
        ("research", "RESEARCH", "web_research_brief", "android_worker_alpha", "Search online for {topic} and make a short brief.", research_topics),
        ("code", "CODE", "draft_code_artifact", "android_worker_alpha", "Write code for {topic}.", code_topics),
        ("file", "FILE", "summarize_text", "android_worker_alpha", "Make this file and put it here: {topic}.", file_topics),
    ]
    prompts: list[PromptItem] = []
    round_idx = 0

    build_on_layers = [
        "third-wave build-on check using the first two classifier fixes",
        "fourth-wave stress check with clearer wording and artifact uniqueness",
        "fifth-wave phone-first routing check with device capability awareness",
        "sixth-wave regression guard using prior receipt lessons",
        "seventh-wave cleanup-safe run that proves D-drive artifact handling",
        "eighth-wave operator-ready run with simple user phrasing",
        "ninth-wave future-device run that keeps Alpha and Beta behavior clear",
        "tenth-wave finalizer check that honors explicit output format first",
    ]

    def build_on_topic(base_topic: str, round_number: int) -> str:
        # Each one-hour run uses ten rounds. The first two hours are the
        # original prompt bank; later hours add a lesson layer so prompt
        # indexes 121+ build on prior receipts instead of replaying old text.
        hour_wave = (round_number // 10) + 1
        if hour_wave <= 2:
            return base_topic
        layer = build_on_layers[(hour_wave - 3) % len(build_on_layers)]
        return f"{layer}: {base_topic}"

    while len(prompts) < target_jobs:
        for kind, label_prefix, expected_job_type, expected_worker, template, topics in groups:
            topic = build_on_topic(topics[round_idx % len(topics)], round_idx)
            number = len(prompts) + 1
            prompt = template.format(topic=topic)
            prompts.append(PromptItem(f"{label_prefix}_{number:03d}", kind, expected_job_type, expected_worker, prompt))
            if len(prompts) >= target_jobs:
                break
        round_idx += 1
    return prompts


def _record_ok(record: dict[str, Any]) -> bool:
    return bool(record.get("ui_finished") and record.get("new_orders") and record.get("new_returns") and record.get("new_artifacts"))


def _training_id(started_at: str) -> str:
    return "ui_creation_training_" + hashlib.sha256(started_at.encode("utf-8")).hexdigest()[:14]


def _render_summary(receipt: dict[str, Any]) -> str:
    summary = receipt.get("summary") if isinstance(receipt.get("summary"), dict) else {}
    lines = [
        "# Engel UI Input Creation Training Hour",
        "",
        f"run_id: {receipt.get('run_id')}",
        f"started_at: {receipt.get('run_started')}",
        f"finished_at: {receipt.get('run_finished')}",
        f"requested_minutes: {receipt.get('requested_minutes')}",
        f"actual_duration_seconds: {receipt.get('actual_duration_seconds')}",
        f"jobs: {summary.get('jobs')}",
        f"all_ui_finished: {summary.get('all_ui_finished')}",
        f"all_jobs_have_orders: {summary.get('all_jobs_have_orders')}",
        f"all_jobs_have_returns: {summary.get('all_jobs_have_returns')}",
        f"all_jobs_have_artifacts: {summary.get('all_jobs_have_artifacts')}",
        f"expected_artifact_kind_matches: {summary.get('expected_artifact_kind_matches')}",
        f"expected_job_type_matches: {summary.get('expected_job_type_matches')}",
        f"expected_worker_matches: {summary.get('expected_worker_matches')}",
        f"all_expected_job_types_matched: {summary.get('all_expected_job_types_matched')}",
        f"all_expected_workers_matched: {summary.get('all_expected_workers_matched')}",
        "",
        "Route:",
        f"- {receipt.get('route')}",
        "",
        "Workers:",
        *[f"- {key}: {value}" for key, value in sorted((summary.get("workers") or {}).items())],
        "",
        "Artifacts:",
        *[f"- {key}: {value}" for key, value in sorted((summary.get("artifacts") or {}).items())],
        "",
        "Job types:",
        *[f"- {key}: {value}" for key, value in sorted((summary.get("job_types") or {}).items())],
        "",
        "Training lessons:",
        "- Engel should recognize simple creation prompts without special tags.",
        "- Prompt wording should route to a matching job type before the device is selected.",
        "- Device-first routing should prefer phone workers for bounded creation jobs.",
        "- Phone returns remain untrusted context; final local artifacts are produced by Engel's bounded finalizer.",
        "- Every prompt must produce a new artifact folder, not just a renamed duplicate request record.",
        "",
        "Safety boundary:",
        "- No phone result was auto-applied.",
        "- No trusted memory was written.",
        "- No source mutation was requested from a phone worker.",
        "- Provider chat was bounded locally so the run measured UI/Meeting Room/device/artifact behavior.",
        "",
        "Output files:",
        f"- receipt: {receipt.get('receipt_path')}",
        f"- transcript: {receipt.get('transcript')}",
        f"- summary: {receipt.get('summary_path')}",
        f"- candidate memory: {receipt.get('memory_candidate')}",
    ]
    return "\n".join(str(line) for line in lines).rstrip() + "\n"


def _render_memory_candidate(receipt: dict[str, Any]) -> str:
    summary = receipt.get("summary") if isinstance(receipt.get("summary"), dict) else {}
    lines = [
        "# Engel UI Input Creation Training Candidate Memory",
        "",
        "Not trusted memory: true",
        "Human review required: true",
        "",
        f"source_run_id: {receipt.get('run_id')}",
        f"source_receipt: {receipt.get('receipt_path')}",
        f"jobs_completed: {summary.get('jobs')}",
        "",
        "Candidate learning:",
        "Engel should map plain user creation requests into artifact intents: PDF/report, browser game, app language, web research brief, reviewable code, or requested file. The Meeting Room should choose the device, agent, and skill automatically, prefer phone workers for bounded work, and return context to Engel's finalizer for real local artifacts.",
        "",
        "Observed routing counts:",
        f"- workers: {summary.get('workers')}",
        f"- artifacts: {summary.get('artifacts')}",
        f"- job_types: {summary.get('job_types')}",
        "",
        "Do not promote automatically. Review the receipt, artifacts, and choice map first.",
    ]
    return "\n".join(lines).rstrip() + "\n"


def run_training(
    minutes: float,
    target_jobs: int,
    per_job_timeout: float,
    final_wait: bool,
    prompt_start_index: int = 1,
) -> dict[str, Any]:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("ENGEL_MEETING_ROOM_ANDROID_RETURN_WAIT_SECONDS", "45")
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    MEMORY_CANDIDATE_DIR.mkdir(parents=True, exist_ok=True)
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)

    run_started_monotonic = time.monotonic()
    run_started_epoch = time.time()
    run_started = dt.datetime.fromtimestamp(run_started_epoch).isoformat(timespec="seconds")
    run_stamp = local_stamp()
    run_id = _training_id(run_started)
    prompt_start_index = max(1, prompt_start_index)
    prompt_bank = build_prompt_bank(target_jobs + prompt_start_index - 1)
    prompts = prompt_bank[prompt_start_index - 1: prompt_start_index - 1 + target_jobs]
    interval = max(0.0, (minutes * 60.0) / max(1, target_jobs))
    deadline = run_started_monotonic + max(0.0, minutes * 60.0)

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
                "Engel recognized the creation request, routed it through the Agent Meeting Room, "
                "and is waiting for the selected agent/device result before creating the local artifact."
            )

    desktop._ChatWorker = BoundedChatWorker
    app = desktop.QApplication.instance() or desktop.QApplication([])
    panel = desktop.AgentChatPanel()

    records: list[dict[str, Any]] = []
    print(
        json.dumps(
            {
                "event": "training_start",
                "run_id": run_id,
                "minutes": minutes,
                "target_jobs": target_jobs,
                "prompt_start_index": prompt_start_index,
                "interval_seconds": round(interval, 3),
                "link_state": _link_state_snapshot(),
            },
            indent=2,
        ),
        flush=True,
    )

    for index, item in enumerate(prompts, start=1):
        before_returns = {path.name for path in _paths_since(RETURNED_DIR, run_started_epoch - 2, "*.json")}
        before_orders = {path.name for path in _paths_since(ORDER_DIR, run_started_epoch - 2, "*.json")}
        before_artifacts = {str(path) for path in ARTIFACT_ROOT.glob("*")} if ARTIFACT_ROOT.exists() else set()
        before_result_count = panel.transcript.toPlainText().count("Engel Result:")
        job_started = time.time()

        panel.msg_input.setText(item.prompt)
        panel.send_btn.click()
        timeout_at = time.monotonic() + per_job_timeout
        return_grace = float(os.environ.get("ENGEL_TRAINING_RETURN_GRACE_SECONDS", "60"))
        finished = False
        result_seen = False
        while time.monotonic() < timeout_at:
            app.processEvents()
            if panel.transcript.toPlainText().count("Engel Result:") > before_result_count:
                result_seen = True
            current_returns = {
                path.name for path in _paths_since(RETURNED_DIR, run_started_epoch - 2, "*.json")
            }
            if result_seen and (current_returns - before_returns):
                finished = True
                break
            time.sleep(0.2)
        if result_seen and not finished:
            grace_end = min(timeout_at, time.monotonic() + return_grace)
            while time.monotonic() < grace_end:
                app.processEvents()
                current_returns = {
                    path.name for path in _paths_since(RETURNED_DIR, run_started_epoch - 2, "*.json")
                }
                if current_returns - before_returns:
                    finished = True
                    break
                time.sleep(0.5)

        app.processEvents()
        after_returns = _paths_since(RETURNED_DIR, run_started_epoch - 2, "*.json")
        after_orders = _paths_since(ORDER_DIR, run_started_epoch - 2, "*.json")
        after_artifacts = sorted(ARTIFACT_ROOT.glob("*"), key=lambda item_path: item_path.stat().st_mtime) if ARTIFACT_ROOT.exists() else []
        record = {
            "index": index,
            "label": item.label,
            "expected_kind": item.kind,
            "expected_job_type": item.expected_job_type,
            "expected_worker": item.expected_worker,
            "prompt": item.prompt,
            "ui_finished": result_seen and finished,
            "duration_seconds": round(time.time() - job_started, 3),
            "new_orders": _summarize_orders([path for path in after_orders if path.name not in before_orders]),
            "new_returns": _summarize_returns([path for path in after_returns if path.name not in before_returns]),
            "new_artifacts": [
                _artifact_manifest(path)
                for path in after_artifacts
                if str(path) not in before_artifacts and path.is_dir()
            ],
        }
        records.append(record)

        artifacts = [row.get("kind") for row in record["new_artifacts"]]
        workers = [row.get("worker_id") for row in record["new_returns"]]
        job_types = [row.get("job_type") for row in record["new_orders"]]
        print(
            json.dumps(
                {
                    "event": "job_complete",
                    "run_id": run_id,
                    "index": index,
                    "target_jobs": target_jobs,
                    "ok": _record_ok(record),
                    "label": item.label,
                    "expected_kind": item.kind,
                    "expected_job_type": item.expected_job_type,
                    "expected_worker": item.expected_worker,
                    "artifacts": artifacts,
                    "workers": workers,
                    "job_types": job_types,
                    "duration_seconds": record["duration_seconds"],
                    "prompt": item.prompt,
                },
                sort_keys=True,
            ),
            flush=True,
        )

        scheduled_next = run_started_monotonic + interval * index
        while time.monotonic() < scheduled_next:
            remaining = scheduled_next - time.monotonic()
            if remaining > 20:
                print(
                    json.dumps(
                        {
                            "event": "paced_wait",
                            "run_id": run_id,
                            "completed_jobs": index,
                            "target_jobs": target_jobs,
                            "seconds_to_next_job": int(remaining),
                            "seconds_to_hour_end": max(0, int(deadline - time.monotonic())),
                        },
                        sort_keys=True,
                    ),
                    flush=True,
                )
            time.sleep(min(15.0, max(0.5, remaining)))

    if final_wait:
        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            print(
                json.dumps(
                    {
                        "event": "final_hour_wait",
                        "run_id": run_id,
                        "completed_jobs": len(records),
                        "seconds_to_hour_end": int(remaining),
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
            time.sleep(min(30.0, max(0.5, remaining)))

    transcript_path = REPORT_DIR / f"ENGEL_UI_INPUT_CREATION_TRAINING_HOUR_{run_stamp}_transcript.txt"
    transcript_path.write_text(panel.transcript.toPlainText(), encoding="utf-8")

    worker_counts = Counter(
        str(row.get("worker_id"))
        for record in records
        for row in record.get("new_returns", [])
        if row.get("worker_id")
    )
    artifact_counts = Counter(
        str(row.get("kind"))
        for record in records
        for row in record.get("new_artifacts", [])
        if row.get("kind")
    )
    job_type_counts = Counter(
        str(order.get("job_type"))
        for record in records
        for order in record.get("new_orders", [])
        if order.get("job_type")
    )
    kind_match_count = sum(
        1
        for record in records
        if any(artifact.get("kind") == record.get("expected_kind") for artifact in record.get("new_artifacts", []))
    )
    job_type_match_count = sum(
        1
        for record in records
        if any(order.get("job_type") == record.get("expected_job_type") for order in record.get("new_orders", []))
    )
    worker_match_count = sum(
        1
        for record in records
        if any(ret.get("worker_id") == record.get("expected_worker") for ret in record.get("new_returns", []))
    )
    summary = {
        "jobs": len(records),
        "workers": dict(sorted(worker_counts.items())),
        "artifacts": dict(sorted(artifact_counts.items())),
        "job_types": dict(sorted(job_type_counts.items())),
        "expected_artifact_kind_matches": kind_match_count,
        "expected_job_type_matches": job_type_match_count,
        "expected_worker_matches": worker_match_count,
        "all_ui_finished": all(record["ui_finished"] for record in records),
        "all_jobs_have_orders": all(bool(record["new_orders"]) for record in records),
        "all_jobs_have_returns": all(bool(record["new_returns"]) for record in records),
        "all_jobs_have_artifacts": all(bool(record["new_artifacts"]) for record in records),
        "all_expected_kinds_matched": kind_match_count == len(records),
        "all_expected_job_types_matched": job_type_match_count == len(records),
        "all_expected_workers_matched": worker_match_count == len(records),
    }
    receipt_path = REPORT_DIR / f"ENGEL_UI_INPUT_CREATION_TRAINING_HOUR_{run_stamp}.json"
    summary_path = REPORT_DIR / f"ENGEL_UI_INPUT_CREATION_TRAINING_HOUR_{run_stamp}_summary.md"
    memory_path = MEMORY_CANDIDATE_DIR / f"ENGEL_UI_INPUT_CREATION_TRAINING_HOUR_{run_stamp}_candidate_memory.md"
    receipt = {
        "run_id": run_id,
        "run_started": run_started,
        "run_finished": dt.datetime.now().isoformat(timespec="seconds"),
        "requested_minutes": minutes,
        "actual_duration_seconds": round(time.monotonic() - run_started_monotonic, 3),
        "target_jobs": target_jobs,
        "prompt_start_index": prompt_start_index,
        "route": "plain Engel AI UI input -> Meeting Room auto-select -> WiFi phone workers -> executable local artifacts",
        "provider_mode": "bounded deterministic reply harness; real UI input, Meeting Room, device routing, and artifact finalizer",
        "android_return_wait_seconds": os.environ.get("ENGEL_MEETING_ROOM_ANDROID_RETURN_WAIT_SECONDS"),
        "link_state_start": _link_state_snapshot(),
        "transcript": str(transcript_path),
        "receipt_path": str(receipt_path),
        "summary_path": str(summary_path),
        "memory_candidate": str(memory_path),
        "summary": summary,
        "records": records,
    }
    receipt_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    summary_path.write_text(_render_summary(receipt), encoding="utf-8")
    memory_path.write_text(_render_memory_candidate(receipt), encoding="utf-8")

    print(
        json.dumps(
            {
                "event": "training_complete",
                "run_id": run_id,
                "receipt": str(receipt_path),
                "summary": str(summary_path),
                "transcript": str(transcript_path),
                "memory_candidate": str(memory_path),
                "summary_counts": summary,
            },
            indent=2,
        ),
        flush=True,
    )
    return receipt


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--minutes", type=float, default=60.0)
    parser.add_argument("--target-jobs", type=int, default=60)
    parser.add_argument("--per-job-timeout", type=float, default=180.0)
    parser.add_argument("--prompt-start-index", type=int, default=1)
    parser.add_argument("--skip-final-wait", action="store_true")
    parser.add_argument("--no-strict", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    receipt = run_training(
        minutes=args.minutes,
        target_jobs=max(1, args.target_jobs),
        per_job_timeout=max(5.0, args.per_job_timeout),
        final_wait=not args.skip_final_wait,
        prompt_start_index=max(1, args.prompt_start_index),
    )
    summary = receipt.get("summary") if isinstance(receipt.get("summary"), dict) else {}
    strict_ok = all(
        bool(summary.get(key))
        for key in [
            "all_ui_finished",
            "all_jobs_have_orders",
            "all_jobs_have_returns",
            "all_jobs_have_artifacts",
            "all_expected_kinds_matched",
            "all_expected_job_types_matched",
            "all_expected_workers_matched",
        ]
    )
    if not args.no_strict and not strict_ok:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
