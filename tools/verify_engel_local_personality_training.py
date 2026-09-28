from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LATEST_RECEIPT = ROOT / "runtime" / "engel_local_personality_training_latest.json"
SUMMARY_RECEIPT_DIR = ROOT / "reports" / "engel_local_personality_training" / "receipts"
BAD_TERMS = ["hermes", "composio", "alibaba", "qwen"]
LOCAL_PROVIDERS = {"local-rust-mistral-gguf", "ct246-local-chat-service"}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def turn_bad_terms(turn: dict[str, Any]) -> list[str]:
    response = str(turn.get("response_text") or "")
    return [term for term in BAD_TERMS if term in response.lower()]


def session_is_clean_one_hour(session: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if session.get("ok") is not True:
        reasons.append("session ok is not true")
    if session.get("one_hour_requirement_met") is not True:
        reasons.append("one-hour requirement not met")
    provider = str(session.get("provider") or "")
    if provider not in LOCAL_PROVIDERS:
        reasons.append("provider mismatch")
    if "mistral" not in str(session.get("model") or "").lower():
        reasons.append("model is not Mistral")
    if session.get("network_enabled") is not False:
        reasons.append("network not disabled")
    if session.get("c_drive_used") is not False:
        reasons.append("C drive marked used")
    turns = session.get("turns") if isinstance(session.get("turns"), list) else []
    if not turns:
        reasons.append("no turns")
    for turn in turns:
        if turn.get("ok") is not True:
            reasons.append(f"turn {turn.get('turn_index')} not ok")
        model_key = str(turn.get("model_key") or "")
        if provider == "local-rust-mistral-gguf" and model_key != "mistral_7b_instruct_v0_3":
            reasons.append(f"turn {turn.get('turn_index')} model key mismatch")
        if provider == "ct246-local-chat-service" and model_key != "ct246-local-chat-service":
            reasons.append(f"turn {turn.get('turn_index')} model key mismatch")
        if "mistral" not in str(turn.get("model_file_path") or "").lower():
            reasons.append(f"turn {turn.get('turn_index')} model path mismatch")
        banned = turn_bad_terms(turn)
        if banned:
            reasons.append(f"turn {turn.get('turn_index')} banned terms: {', '.join(banned)}")
    return not reasons, reasons


def iter_summary_receipts() -> list[Path]:
    paths: list[Path] = []
    if LATEST_RECEIPT.exists():
        paths.append(LATEST_RECEIPT)
    if SUMMARY_RECEIPT_DIR.exists():
        paths.extend(sorted(SUMMARY_RECEIPT_DIR.glob("ENGEL_LOCAL_PERSONALITY_TRAINING_*.json")))
    unique: dict[str, Path] = {}
    for path in paths:
        unique[str(path.resolve()).lower()] = path
    return list(unique.values())


def collect_completed_one_hour_sessions() -> list[dict[str, Any]]:
    completed: dict[str, dict[str, Any]] = {}
    for summary_path in iter_summary_receipts():
        try:
            data = read_json(summary_path)
        except Exception:
            continue
        sessions = data.get("sessions") if isinstance(data.get("sessions"), list) else []
        for session in sessions:
            ok, reasons = session_is_clean_one_hour(session)
            if not ok:
                continue
            key = str(session.get("external_session_receipt_path") or "")
            if not key:
                key = f"{session.get('started_at_utc')}::{session.get('finished_at_utc')}::{summary_path}"
            completed[key] = {
                "summary_path": str(summary_path),
                "session_index": session.get("session_index"),
                "started_at_utc": session.get("started_at_utc"),
                "finished_at_utc": session.get("finished_at_utc"),
                "elapsed_seconds": session.get("elapsed_seconds"),
                "turn_count": session.get("turn_count"),
                "external_session_receipt_path": session.get("external_session_receipt_path"),
                "external_session_receipt_sha256": session.get("external_session_receipt_sha256"),
            }
    return sorted(completed.values(), key=lambda item: str(item.get("started_at_utc") or ""))


def check_receipt(data: dict[str, Any], *, require_five_hours: bool) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: str = "") -> None:
        item = {"name": name, "ok": bool(ok)}
        if detail:
            item["detail"] = detail
        checks.append(item)

    add("schema", data.get("schema") == "engel_local_personality_training_summary_v1", str(data.get("schema")))
    provider = str(data.get("provider") or "")
    add("provider_local", provider in LOCAL_PROVIDERS, provider)
    add("model_mistral", "mistral" in str(data.get("model") or "").lower(), str(data.get("model")))
    add("network_disabled", data.get("network_enabled") is False)
    add("api_key_not_used", data.get("api_key_present") is False and data.get("api_key_value_visible") is False)
    add("c_drive_not_used", data.get("c_drive_used") is False)
    add("personality_present", "Engel AI Main" in str(data.get("personality") or ""))
    sessions = data.get("sessions") if isinstance(data.get("sessions"), list) else []
    add("sessions_list_present", isinstance(sessions, list))
    for index, session in enumerate(sessions, start=1):
        add(f"session_{index}_provider", str(session.get("provider") or "") in LOCAL_PROVIDERS)
        add(f"session_{index}_network_disabled", session.get("network_enabled") is False)
        add(f"session_{index}_c_drive_not_used", session.get("c_drive_used") is False)
        for turn in session.get("turns") or []:
            banned = turn_bad_terms(turn)
            add(f"session_{index}_turn_{turn.get('turn_index')}_ok", turn.get("ok") is True, str(turn.get("error") or turn.get("score") or ""))
            add(f"session_{index}_turn_{turn.get('turn_index')}_no_bad_terms", not banned, ", ".join(banned))

    completed_one_hour_sessions = collect_completed_one_hour_sessions()
    if require_five_hours:
        add("aggregate_five_one_hour_sessions", len(completed_one_hour_sessions) >= 5, str(len(completed_one_hour_sessions)))
        add("aggregate_sessions_have_receipts", all(item.get("external_session_receipt_path") for item in completed_one_hour_sessions[:5]))
    return {
        "ok": all(item["ok"] for item in checks),
        "checks": checks,
        "receipt_path": str(LATEST_RECEIPT),
        "completed_one_hour_session_count": len(completed_one_hour_sessions),
        "completed_one_hour_sessions": completed_one_hour_sessions,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify latest and aggregate local Engel personality training receipts.")
    parser.add_argument("--require-five-hours", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if not LATEST_RECEIPT.exists():
        print(json.dumps({"ok": False, "error": f"missing latest receipt: {LATEST_RECEIPT}"}, indent=2))
        return 1
    result = check_receipt(read_json(LATEST_RECEIPT), require_five_hours=args.require_five_hours)
    print(json.dumps(result, indent=2))
    return 0 if result.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
