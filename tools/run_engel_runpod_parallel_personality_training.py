from __future__ import annotations

import argparse
import concurrent.futures
import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

from run_engel_personality_training_sessions import (  # noqa: E402
    ENGEL_CHAT_PERSONALITY,
    LATEST_RECEIPT,
    SESSION_ROOT,
    WORKSPACE_RECEIPT_DIR,
    TrainingError,
    ensure_runtime_env,
    iso_now,
    load_engel_runtime,
    openai_get_models,
    run_one_session,
    sha256_file,
    utc_stamp,
    write_json,
    write_report,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run parallel receipt-based RunPod Engel personality training/evaluation sessions."
    )
    parser.add_argument("--session-count", type=int, default=5)
    parser.add_argument("--minutes-per-session", type=int, default=60)
    parser.add_argument("--session-seconds", type=int, default=None)
    parser.add_argument("--turn-interval-seconds", type=int, default=900)
    parser.add_argument("--max-turns-per-session", type=int, default=0)
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--require-five-one-hour", action="store_true")
    parser.add_argument("--max-workers", type=int, default=0)
    return parser


def run_parallel_training(args: argparse.Namespace) -> dict[str, Any]:
    if args.session_count < 1:
        raise TrainingError("session-count must be at least 1")
    duration_seconds = args.session_seconds if args.session_seconds is not None else args.minutes_per_session * 60
    if duration_seconds < 1:
        raise TrainingError("session duration must be at least 1 second")
    if args.turn_interval_seconds < 0:
        raise TrainingError("turn interval cannot be negative")
    if args.require_five_one_hour and (args.session_count < 5 or duration_seconds < 3600):
        raise TrainingError("five one-hour training requires session-count >= 5 and duration >= 3600 seconds")

    engel_home = ensure_runtime_env()
    runtime = load_engel_runtime()
    receipt_stamp = utc_stamp()
    summary_path = WORKSPACE_RECEIPT_DIR / f"ENGEL_PERSONALITY_TRAINING_PARALLEL_{receipt_stamp}.json"
    f_summary_path = SESSION_ROOT / f"ENGEL_PERSONALITY_TRAINING_PARALLEL_{receipt_stamp}.json"
    max_workers = args.max_workers if args.max_workers > 0 else args.session_count

    summary: dict[str, Any] = {
        "ok": False,
        "schema": "engel_personality_training_summary_v1",
        "updated_at_utc": iso_now(),
        "training_kind": "Parallel RunPod chat personality training/evaluation, not weight fine-tune",
        "parallel_sessions": True,
        "parallel_worker_count": max_workers,
        "engel_home": str(engel_home),
        "provider": "runpod-engel",
        "runtime_provider": runtime.get("provider"),
        "requested_provider": runtime.get("requested_provider"),
        "api_mode": runtime.get("api_mode"),
        "base_url": runtime.get("base_url"),
        "model": runtime.get("model"),
        "personality": ENGEL_CHAT_PERSONALITY,
        "api_key_present": bool(runtime.get("api_key")),
        "api_key_value_visible": False,
        "session_count_requested": args.session_count,
        "requested_duration_seconds_per_session": duration_seconds,
        "five_one_hour_requirement_requested": bool(args.require_five_one_hour),
        "five_one_hour_requirement_met": False,
        "workspace_receipt_path": str(summary_path),
        "external_receipt_path": str(f_summary_path),
        "c_drive_used": False,
        "models_probe": {},
        "sessions": [],
        "errors": [],
    }

    try:
        started = time.perf_counter()
        models = openai_get_models(str(runtime.get("base_url") or ""), str(runtime.get("api_key") or ""), args.timeout)
        model_ids = [item.get("id") for item in models.get("data", []) if isinstance(item, dict) and item.get("id")]
        summary["models_probe"] = {
            "ok": True,
            "model_count": len(model_ids),
            "model_ids": model_ids[:20],
            "latency_ms": int((time.perf_counter() - started) * 1000),
        }
    except Exception as exc:
        summary["models_probe"] = {"ok": False, "error": str(exc)}
        summary["errors"].append("models probe failed: " + str(exc))

    if summary["models_probe"].get("ok") is True:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(
                    run_one_session,
                    session_index=index,
                    duration_seconds=duration_seconds,
                    turn_interval_seconds=args.turn_interval_seconds,
                    max_turns=args.max_turns_per_session,
                    timeout=args.timeout,
                    runtime=runtime,
                ): index
                for index in range(1, args.session_count + 1)
            }
            for future in concurrent.futures.as_completed(futures):
                index = futures[future]
                try:
                    session = future.result()
                except Exception as exc:
                    session = {
                        "ok": False,
                        "schema": "engel_personality_training_session_v1",
                        "session_index": index,
                        "started_at_utc": "",
                        "finished_at_utc": iso_now(),
                        "requested_duration_seconds": duration_seconds,
                        "turn_interval_seconds": args.turn_interval_seconds,
                        "max_turns": args.max_turns_per_session,
                        "provider": "runpod-engel",
                        "model": runtime.get("model"),
                        "api_key_present": bool(runtime.get("api_key")),
                        "api_key_value_visible": False,
                        "c_drive_used": False,
                        "turns": [],
                        "errors": [{"error": str(exc)}],
                        "elapsed_seconds": 0,
                        "turn_count": 0,
                        "passed_turn_count": 0,
                        "one_hour_requirement_met": False,
                    }
                session_path = SESSION_ROOT / f"ENGEL_PERSONALITY_TRAINING_PARALLEL_SESSION_{receipt_stamp}_{index:02d}.json"
                write_json(session_path, session)
                session["external_session_receipt_path"] = str(session_path)
                session["external_session_receipt_sha256"] = sha256_file(session_path)
                summary["sessions"].append(session)
                if not session.get("ok"):
                    summary["errors"].append(f"session {index} failed or did not complete requested duration")
                summary["sessions"] = sorted(summary["sessions"], key=lambda item: int(item.get("session_index") or 0))
                summary["updated_at_utc"] = iso_now()
                write_json(summary_path, summary)
                write_json(f_summary_path, summary)
                write_json(LATEST_RECEIPT, summary)
                write_report(summary)

    completed_sessions = [session for session in summary["sessions"] if session.get("ok") is True]
    summary["session_count_completed"] = len(completed_sessions)
    summary["all_sessions_ok"] = len(completed_sessions) == args.session_count
    summary["five_one_hour_requirement_met"] = (
        args.session_count >= 5
        and duration_seconds >= 3600
        and len(completed_sessions) >= 5
        and all(session.get("one_hour_requirement_met") is True for session in completed_sessions[:5])
    )
    summary["ok"] = bool(summary["all_sessions_ok"] and (not args.require_five_one_hour or summary["five_one_hour_requirement_met"]))
    summary["updated_at_utc"] = iso_now()
    write_json(summary_path, summary)
    write_json(f_summary_path, summary)
    write_json(LATEST_RECEIPT, summary)
    write_report(summary)
    return summary


def main() -> int:
    args = build_parser().parse_args()
    try:
        summary = run_parallel_training(args)
    except TrainingError as exc:
        print(json.dumps({"ok": False, "error": str(exc), "api_key_value_visible": False}, indent=2))
        return 1
    print(json.dumps(summary, indent=2))
    return 0 if summary.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
