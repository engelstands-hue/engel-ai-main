from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

from run_engel_runpod_stretch import (  # noqa: E402
    ENGEL_CHAT_PERSONALITY,
    StretchError,
    ensure_runtime_env,
    is_os_drive,
    load_engel_runtime,
    openai_get_models,
    openai_post,
)

SESSION_ROOT = Path(
    os.environ.get(
        "ENGEL_PERSONALITY_TRAINING_SESSION_ROOT",
        str(ROOT / "runtime" / "runpod" / "personality_training_sessions"),
    )
)
WORKSPACE_RECEIPT_DIR = ROOT / "reports" / "engel_personality_training" / "receipts"
LATEST_RECEIPT = ROOT / "runtime" / "engel_personality_training_latest.json"
LATEST_REPORT = ROOT / "reports" / "engel_personality_training" / "ENGEL_PERSONALITY_TRAINING_LATEST.md"

BANNED_TERMS = [
    "hermes",
    "composio",
    "alibaba",
    "qwen",
    "i am runpod",
    "as runpod",
    "completed five training sessions",
    "completed 5 training sessions",
    "i already trained",
    "email verification",
    "installation receipt",
    "check your email",
    "system logs",
]

EXERCISES: list[dict[str, Any]] = [
    {
        "name": "identity_and_scope",
        "prompt": "Answer as Engel AI in two short sentences. Say what you are for without naming other assistants, providers, vendors, or model families.",
        "must_include": ["engel"],
    },
    {
        "name": "receipt_honesty",
        "prompt": "Explain in one short paragraph how you report proof: only claim work that receipts show really ran.",
        "must_include": ["receipt"],
    },
    {
        "name": "agentic_workflow",
        "prompt": "Reply in exactly one sentence starting with Engel AI next step: Ask for the specific task to run, and say a receipt will be created after real work runs.",
        "must_include": ["engel", "receipt"],
    },
    {
        "name": "sub_engel_language",
        "prompt": "Describe how Engel AI uses Sub-Engels without sounding like a separate product.",
        "must_include": ["sub-engel", "engel"],
    },
    {
        "name": "plain_chat_style",
        "prompt": "Reply to: this UI is confusing and not easy to chat with. Keep it plain and useful.",
        "must_include": [],
    },
]


class TrainingError(RuntimeError):
    pass


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    if is_os_drive(path):
        raise TrainingError(f"refusing to write receipt on C: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def score_response(text: str, must_include: list[str]) -> dict[str, Any]:
    stripped = text.strip()
    lowered = stripped.lower()
    banned_hits = [term for term in BANNED_TERMS if term in lowered]
    missing = []
    for term in must_include:
        term_lower = term.lower()
        if term_lower == "receipt":
            if "receipt" not in lowered and "proof" not in lowered:
                missing.append(term)
        elif term_lower not in lowered:
            missing.append(term)
    checks = {
        "nonempty": bool(stripped),
        "not_ready_loop": stripped != "Ready.",
        "no_banned_terms": not banned_hits,
        "must_include_present": not missing,
        "bounded_length": len(stripped) <= 900,
    }
    return {
        "ok": all(checks.values()),
        "checks": checks,
        "banned_hits": banned_hits,
        "missing_required_terms": missing,
    }


def run_turn(*, base_url: str, api_key: str, model: str, exercise: dict[str, Any], timeout: int) -> dict[str, Any]:
    prompt = str(exercise["prompt"])
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    ENGEL_CHAT_PERSONALITY
                    + " This is a personality training and evaluation turn. "
                    + "Shape the answer style, but do not claim model weights changed."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 180,
    }
    started = time.perf_counter()
    turn: dict[str, Any] = {
        "name": exercise["name"],
        "prompt": prompt,
        "ok": False,
        "response_text": "",
        "latency_ms": 0,
    }
    try:
        data = openai_post(base_url, api_key, payload, timeout)
        text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        turn["response_text"] = str(text).strip()
        turn["latency_ms"] = int((time.perf_counter() - started) * 1000)
        score = score_response(turn["response_text"], list(exercise.get("must_include") or []))
        turn["score"] = score
        turn["ok"] = bool(score["ok"])
        usage = data.get("usage")
        if isinstance(usage, dict):
            turn["usage"] = {
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
                "total_tokens": usage.get("total_tokens"),
            }
    except Exception as exc:
        turn["latency_ms"] = int((time.perf_counter() - started) * 1000)
        turn["error"] = str(exc)
    return turn


def run_one_session(
    *,
    session_index: int,
    duration_seconds: int,
    turn_interval_seconds: int,
    max_turns: int,
    timeout: int,
    runtime: dict[str, Any],
) -> dict[str, Any]:
    base_url = str(runtime.get("base_url") or "").strip().rstrip("/")
    model = str(runtime.get("model") or "").strip()
    api_key = str(runtime.get("api_key") or "").strip()
    session_started_perf = time.perf_counter()
    session_started_wall = iso_now()
    deadline = session_started_perf + duration_seconds
    session: dict[str, Any] = {
        "ok": False,
        "schema": "engel_personality_training_session_v1",
        "session_index": session_index,
        "started_at_utc": session_started_wall,
        "finished_at_utc": "",
        "requested_duration_seconds": duration_seconds,
        "turn_interval_seconds": turn_interval_seconds,
        "max_turns": max_turns,
        "provider": "runpod-engel",
        "base_url": base_url,
        "model": model,
        "personality": ENGEL_CHAT_PERSONALITY,
        "api_key_present": bool(api_key),
        "api_key_value_visible": False,
        "c_drive_used": False,
        "turns": [],
        "errors": [],
    }
    turn_index = 0
    while True:
        if max_turns and turn_index >= max_turns:
            break
        now = time.perf_counter()
        if turn_index > 0 and now >= deadline:
            break
        exercise = EXERCISES[turn_index % len(EXERCISES)]
        turn_index += 1
        turn = run_turn(base_url=base_url, api_key=api_key, model=model, exercise=exercise, timeout=timeout)
        turn["turn_index"] = turn_index
        session["turns"].append(turn)
        if not turn.get("ok"):
            session["errors"].append({"turn_index": turn_index, "error": turn.get("error") or turn.get("score")})
            break
        now = time.perf_counter()
        if now >= deadline:
            break
        sleep_for = min(turn_interval_seconds, max(0, int(deadline - now)))
        if sleep_for <= 0:
            break
        time.sleep(sleep_for)

    elapsed = int(time.perf_counter() - session_started_perf)
    passed_turns = sum(1 for turn in session["turns"] if turn.get("ok") is True)
    session.update(
        {
            "finished_at_utc": iso_now(),
            "elapsed_seconds": elapsed,
            "turn_count": len(session["turns"]),
            "passed_turn_count": passed_turns,
            "one_hour_requirement_met": elapsed >= 3600 and duration_seconds >= 3600,
        }
    )
    completed_requested_turns = bool(max_turns) and len(session["turns"]) >= max_turns
    completed_requested_duration = elapsed >= duration_seconds
    session["ok"] = (
        bool(session["turns"])
        and passed_turns == len(session["turns"])
        and not session["errors"]
        and (completed_requested_duration or completed_requested_turns)
    )
    return session


def run_training(args: argparse.Namespace) -> dict[str, Any]:
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
    summary_path = WORKSPACE_RECEIPT_DIR / f"ENGEL_PERSONALITY_TRAINING_{receipt_stamp}.json"
    f_summary_path = SESSION_ROOT / f"ENGEL_PERSONALITY_TRAINING_{receipt_stamp}.json"

    summary: dict[str, Any] = {
        "ok": False,
        "schema": "engel_personality_training_summary_v1",
        "updated_at_utc": iso_now(),
        "training_kind": "RunPod chat personality training/evaluation, not weight fine-tune",
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

    if summary["models_probe"].get("ok") is True or args.continue_without_models_probe:
        for index in range(1, args.session_count + 1):
            session = run_one_session(
                session_index=index,
                duration_seconds=duration_seconds,
                turn_interval_seconds=args.turn_interval_seconds,
                max_turns=args.max_turns_per_session,
                timeout=args.timeout,
                runtime=runtime,
            )
            session_path = SESSION_ROOT / f"ENGEL_PERSONALITY_TRAINING_SESSION_{receipt_stamp}_{index:02d}.json"
            write_json(session_path, session)
            session["external_session_receipt_path"] = str(session_path)
            session["external_session_receipt_sha256"] = sha256_file(session_path)
            summary["sessions"].append(session)
            if not session.get("ok"):
                summary["errors"].append(f"session {index} failed or did not complete requested duration")
                if args.stop_on_failure:
                    break

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


def write_report(summary: dict[str, Any]) -> None:
    lines = [
        "# Engel Personality Training Latest",
        "",
        f"- ok: `{summary.get('ok')}`",
        f"- training_kind: `{summary.get('training_kind')}`",
        f"- provider: `{summary.get('provider')}`",
        f"- model: `{summary.get('model')}`",
        f"- session_count_requested: `{summary.get('session_count_requested')}`",
        f"- session_count_completed: `{summary.get('session_count_completed')}`",
        f"- requested_duration_seconds_per_session: `{summary.get('requested_duration_seconds_per_session')}`",
        f"- five_one_hour_requirement_met: `{summary.get('five_one_hour_requirement_met')}`",
        f"- workspace_receipt_path: `{summary.get('workspace_receipt_path')}`",
        f"- external_receipt_path: `{summary.get('external_receipt_path')}`",
        "",
        "## Errors",
    ]
    errors = summary.get("errors") or []
    if errors:
        lines.extend(f"- {error}" for error in errors)
    else:
        lines.append("- none")
    LATEST_REPORT.parent.mkdir(parents=True, exist_ok=True)
    LATEST_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run receipt-based Engel AI RunPod personality training sessions.")
    parser.add_argument("--session-count", type=int, default=5)
    parser.add_argument("--minutes-per-session", type=int, default=60)
    parser.add_argument("--session-seconds", type=int, default=None)
    parser.add_argument("--turn-interval-seconds", type=int, default=300)
    parser.add_argument("--max-turns-per-session", type=int, default=0, help="0 means no explicit turn cap")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--stop-on-failure", action="store_true", default=True)
    parser.add_argument("--continue-without-models-probe", action="store_true")
    parser.add_argument("--require-five-one-hour", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        summary = run_training(args)
    except (TrainingError, StretchError) as exc:
        print(json.dumps({"ok": False, "error": str(exc), "api_key_value_visible": False}, indent=2))
        return 1
    print(json.dumps(summary, indent=2))
    return 0 if summary.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())

