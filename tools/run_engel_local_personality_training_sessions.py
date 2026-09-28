from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))


def _load_personality() -> str:
    path = ROOT / "memory" / "personality" / "ENGEL_AI_MERGED_PERSONALITY.md"
    try:
        text = path.read_text(encoding="utf-8-sig").strip()
    except Exception:
        text = ""
    if not text:
        text = (
            "You are Engel AI Main, Joshua's local AI system. Speak plainly, "
            "answer the current request directly, and only claim work that receipts prove."
        )
    return text[:2400]


ENGEL_CHAT_PERSONALITY = _load_personality()
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

RUST_EXE = ROOT / "runtime" / "temp" / "engel-rust-rewrite" / "cargo-target" / "debug" / "engel-ai-rs.exe"


def _is_ct_runtime() -> bool:
    return ROOT.as_posix() == "/opt/engel"


def _default_chat_url() -> str:
    return "http://127.0.0.1:8765/chat" if _is_ct_runtime() else "http://127.0.0.1:24680/chat"


CHAT_SERVICE_URL = os.environ.get("ENGEL_LOCAL_PERSONALITY_CHAT_URL", _default_chat_url()).strip()


def _default_model_path() -> Path:
    candidates = [
        ROOT / "models-active" / "llm" / "mistral-7b-instruct-v0.3" / "Mistral-7B-Instruct-v0.3-Q4_K_M.gguf",
        ROOT / "models-active" / "mistral-7b-instruct-v0.3" / "Mistral-7B-Instruct-v0.3-Q4_K_M.gguf",
        ROOT / "models-active" / "llm" / "engel-qwen2.5-1.5b-deepreason" / "engel-qwen2.5-1.5b-deepreason-q5_k_m.gguf",
        ROOT / "models-active" / "llm" / "ornith-1.0-9b" / "ornith-1.0-9b-Q4_K_M.gguf",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


MODEL_PATH = Path(os.environ.get("ENGEL_LOCAL_PERSONALITY_MODEL_PATH", str(_default_model_path())))
SESSION_ROOT = Path(
    os.environ.get(
        "ENGEL_LOCAL_PERSONALITY_TRAINING_SESSION_ROOT",
        str(ROOT / "runtime" / "local_personality_training_sessions"),
    )
)
WORKSPACE_RECEIPT_DIR = ROOT / "reports" / "engel_local_personality_training" / "receipts"
LATEST_RECEIPT = ROOT / "runtime" / "engel_local_personality_training_latest.json"
LATEST_REPORT = ROOT / "reports" / "engel_local_personality_training" / "ENGEL_LOCAL_PERSONALITY_TRAINING_LATEST.md"


class LocalTrainingError(RuntimeError):
    pass


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def is_c_drive(path: Path) -> bool:
    text = str(path).replace("/", "\\").lower()
    return text.startswith("c:\\") or text.startswith("\\\\?\\c:\\")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    if is_c_drive(path):
        raise LocalTrainingError(f"refusing to write receipt on C: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _runtime_provider() -> str:
    forced = os.environ.get("ENGEL_LOCAL_PERSONALITY_RUNTIME", "").strip().lower()
    if forced in {"chat-service", "service", "ct-chat"}:
        return "ct246-local-chat-service"
    if forced in {"rust", "local-rust"}:
        return "local-rust-mistral-gguf"
    if RUST_EXE.exists():
        return "local-rust-mistral-gguf"
    return "ct246-local-chat-service"


def run_service_turn(exercise: dict[str, Any], timeout: int) -> dict[str, Any]:
    prompt = str(exercise["prompt"])
    started = time.perf_counter()
    turn: dict[str, Any] = {
        "name": exercise["name"],
        "prompt": prompt,
        "ok": False,
        "response_text": "",
        "latency_ms": 0,
        "chat_service_url": CHAT_SERVICE_URL,
        "model_key": "ct246-local-chat-service",
        "model_file_path": str(MODEL_PATH),
    }
    try:
        payload = json.dumps(
            {
                "prompt": prompt,
                "source": "engel_local_personality_training",
                "max_tokens": 180,
                "training_probe": True,
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            CHAT_SERVICE_URL,
            data=payload,
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8", errors="replace"))
        reply = str(data.get("assistant_reply") or data.get("assistant_output_text") or "").strip()
        turn.update(
            {
                "response_text": reply,
                "service_ok": data.get("ok") is not False,
                "provider": data.get("provider") or data.get("selected_provider") or "ct246-local-chat-service",
                "receipt_path": data.get("receipt_path") or "",
            }
        )
        score = score_response(reply, list(exercise.get("must_include") or []))
        turn["score"] = score
        turn["ok"] = bool(reply and turn["service_ok"] and score["ok"])
    except urllib.error.HTTPError as exc:
        turn["error"] = f"chat service HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')[:1000]}"
    except Exception as exc:
        turn["error"] = str(exc)
    finally:
        turn["latency_ms"] = int((time.perf_counter() - started) * 1000)
    return turn


def run_local_turn(exercise: dict[str, Any], timeout: int) -> dict[str, Any]:
    prompt = str(exercise["prompt"])
    command = [
        str(RUST_EXE),
        "local-chat",
        "bounded-run-execute",
        "--approve",
        "APPROVE_LOCAL_CHAT_BOUNDED_RUN_EXECUTION",
        "--",
        prompt,
    ]
    started = time.perf_counter()
    turn: dict[str, Any] = {
        "name": exercise["name"],
        "prompt": prompt,
        "ok": False,
        "response_text": "",
        "latency_ms": 0,
        "command": command,
    }
    try:
        completed = subprocess.run(
            command,
            cwd=str(ROOT),
            text=True,
            capture_output=True,
            timeout=timeout,
            shell=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        turn["returncode"] = completed.returncode
        turn["stderr_preview"] = completed.stderr[:2000]
        if completed.returncode != 0:
            turn["error"] = completed.stderr[:2000] or completed.stdout[:2000] or f"returncode={completed.returncode}"
            return turn
        data = json.loads(completed.stdout)
        reply = str(data.get("assistant_reply") or data.get("assistant_output_text") or "").strip()
        turn.update(
            {
                "response_text": reply,
                "rust_ok": data.get("ok") is True,
                "readable_output_captured": data.get("readable_output_captured") is True,
                "receipt_path": str(ROOT / str(data.get("receipt_path") or "")),
                "constructed_prompt_path": str(ROOT / str(data.get("constructed_prompt_path") or "")),
                "model_key": (data.get("receipt") or {}).get("model_key"),
                "model_file_path": (data.get("receipt") or {}).get("model_file_path"),
            }
        )
        score = score_response(reply, list(exercise.get("must_include") or []))
        turn["score"] = score
        turn["ok"] = bool(turn["rust_ok"] and turn["readable_output_captured"] and score["ok"])
    except Exception as exc:
        turn["error"] = str(exc)
    finally:
        turn["latency_ms"] = int((time.perf_counter() - started) * 1000)
    return turn


def run_one_session(*, session_index: int, duration_seconds: int, turn_interval_seconds: int, max_turns: int, timeout: int) -> dict[str, Any]:
    start_perf = time.perf_counter()
    deadline = start_perf + duration_seconds
    provider = _runtime_provider()
    session: dict[str, Any] = {
        "ok": False,
        "schema": "engel_local_personality_training_session_v1",
        "session_index": session_index,
        "started_at_utc": iso_now(),
        "finished_at_utc": "",
        "requested_duration_seconds": duration_seconds,
        "turn_interval_seconds": turn_interval_seconds,
        "max_turns": max_turns,
        "provider": provider,
        "model": MODEL_PATH.name,
        "model_path": str(MODEL_PATH),
        "chat_service_url": CHAT_SERVICE_URL if provider == "ct246-local-chat-service" else "",
        "personality": ENGEL_CHAT_PERSONALITY,
        "api_key_present": False,
        "api_key_value_visible": False,
        "network_enabled": False,
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
        turn = run_service_turn(exercise, timeout) if provider == "ct246-local-chat-service" else run_local_turn(exercise, timeout)
        turn["turn_index"] = turn_index
        session["turns"].append(turn)
        if not turn.get("ok"):
            session["errors"].append({"turn_index": turn_index, "error": turn.get("error") or turn.get("score")})
            break
        now = time.perf_counter()
        if now >= deadline:
            break
        remaining_seconds = max(0, int(deadline - now))
        if remaining_seconds <= 0:
            break
        sleep_for = min(turn_interval_seconds, remaining_seconds)
        if sleep_for > 0:
            time.sleep(sleep_for)

    elapsed = int(time.perf_counter() - start_perf)
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
    duration_seconds = args.session_seconds if args.session_seconds is not None else args.minutes_per_session * 60
    if args.require_five_one_hour and (args.session_count < 5 or duration_seconds < 3600):
        raise LocalTrainingError("five one-hour training requires session-count >= 5 and duration >= 3600 seconds")
    provider = _runtime_provider()
    if provider == "local-rust-mistral-gguf" and not RUST_EXE.exists():
        raise LocalTrainingError(f"missing Rust executable: {RUST_EXE}")
    if not MODEL_PATH.exists():
        raise LocalTrainingError(f"missing Mistral model: {MODEL_PATH}")

    stamp = utc_stamp()
    workspace_summary_path = WORKSPACE_RECEIPT_DIR / f"ENGEL_LOCAL_PERSONALITY_TRAINING_{stamp}.json"
    external_summary_path = SESSION_ROOT / f"ENGEL_LOCAL_PERSONALITY_TRAINING_{stamp}.json"
    summary: dict[str, Any] = {
        "ok": False,
        "schema": "engel_local_personality_training_summary_v1",
        "updated_at_utc": iso_now(),
        "training_kind": "Local Engel chat personality training/evaluation, not weight fine-tune",
        "provider": provider,
        "model": MODEL_PATH.name,
        "model_path": str(MODEL_PATH),
        "rust_executable": str(RUST_EXE),
        "chat_service_url": CHAT_SERVICE_URL if provider == "ct246-local-chat-service" else "",
        "personality": ENGEL_CHAT_PERSONALITY,
        "api_key_present": False,
        "api_key_value_visible": False,
        "network_enabled": False,
        "c_drive_used": False,
        "session_count_requested": args.session_count,
        "requested_duration_seconds_per_session": duration_seconds,
        "five_one_hour_requirement_requested": bool(args.require_five_one_hour),
        "five_one_hour_requirement_met": False,
        "workspace_receipt_path": str(workspace_summary_path),
        "external_receipt_path": str(external_summary_path),
        "sessions": [],
        "errors": [],
    }
    for index in range(1, args.session_count + 1):
        session = run_one_session(
            session_index=index,
            duration_seconds=duration_seconds,
            turn_interval_seconds=args.turn_interval_seconds,
            max_turns=args.max_turns_per_session,
            timeout=args.timeout,
        )
        session_path = SESSION_ROOT / f"ENGEL_LOCAL_PERSONALITY_TRAINING_SESSION_{stamp}_{index:02d}.json"
        write_json(session_path, session)
        session["external_session_receipt_path"] = str(session_path)
        session["external_session_receipt_sha256"] = sha256_file(session_path)
        summary["sessions"].append(session)
        write_json(workspace_summary_path, summary)
        write_json(external_summary_path, summary)
        write_json(LATEST_RECEIPT, summary)
        write_report(summary)
        if not session.get("ok"):
            summary["errors"].append(f"session {index} failed or did not complete requested duration")
            if args.stop_on_failure:
                break

    completed = [session for session in summary["sessions"] if session.get("ok") is True]
    summary["session_count_completed"] = len(completed)
    summary["all_sessions_ok"] = len(completed) == args.session_count
    summary["five_one_hour_requirement_met"] = (
        args.session_count >= 5
        and duration_seconds >= 3600
        and len(completed) >= 5
        and all(session.get("one_hour_requirement_met") is True for session in completed[:5])
    )
    summary["ok"] = bool(summary["all_sessions_ok"] and (not args.require_five_one_hour or summary["five_one_hour_requirement_met"]))
    summary["updated_at_utc"] = iso_now()
    write_json(workspace_summary_path, summary)
    write_json(external_summary_path, summary)
    write_json(LATEST_RECEIPT, summary)
    write_report(summary)
    return summary


def write_report(summary: dict[str, Any]) -> None:
    lines = [
        "# Engel Local Personality Training Latest",
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
    parser = argparse.ArgumentParser(description="Run receipt-based local Mistral Engel personality training sessions.")
    parser.add_argument("--session-count", type=int, default=5)
    parser.add_argument("--minutes-per-session", type=int, default=60)
    parser.add_argument("--session-seconds", type=int, default=None)
    parser.add_argument("--turn-interval-seconds", type=int, default=900)
    parser.add_argument("--max-turns-per-session", type=int, default=0)
    parser.add_argument("--timeout", type=int, default=240)
    parser.add_argument("--stop-on-failure", action="store_true", default=True)
    parser.add_argument("--require-five-one-hour", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        summary = run_training(args)
    except LocalTrainingError as exc:
        print(json.dumps({"ok": False, "error": str(exc), "api_key_value_visible": False}, indent=2))
        return 1
    print(json.dumps(summary, indent=2))
    return 0 if summary.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
