from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LATEST_RECEIPT = ROOT / "runtime" / "engel_personality_training_latest.json"

BAD_TERMS = ["hermes", "composio", "alibaba", "qwen"]


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def check_receipt(data: dict[str, Any], *, require_five_hours: bool) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: str = "") -> None:
        item = {"name": name, "ok": bool(ok)}
        if detail:
            item["detail"] = detail
        checks.append(item)

    add("schema", data.get("schema") == "engel_personality_training_summary_v1", str(data.get("schema")))
    add("api_key_redacted", data.get("api_key_value_visible") is False)
    add("c_drive_not_used", data.get("c_drive_used") is False)
    add("provider_runpod", data.get("provider") == "runpod-engel", str(data.get("provider")))
    model = str(data.get("model") or "")
    add("model_configured", bool(model), model)
    add("model_not_qwen", "qwen" not in model.lower(), model)
    personality = str(data.get("personality") or "")
    add("personality_present", "Engel AI Main" in personality)
    add("personality_no_forbidden_identity", not any(term in personality.lower() for term in ["you are hermes", "you are composio", "you are qwen"]))
    sessions = data.get("sessions") if isinstance(data.get("sessions"), list) else []
    add("sessions_list_present", isinstance(sessions, list))
    add("models_probe_recorded", isinstance(data.get("models_probe"), dict))
    if require_five_hours:
        add("five_one_hour_requirement_met", data.get("five_one_hour_requirement_met") is True, str(data.get("five_one_hour_requirement_met")))
        add("five_sessions_completed", int(data.get("session_count_completed") or 0) >= 5, str(data.get("session_count_completed")))
    for index, session in enumerate(sessions, start=1):
        add(f"session_{index}_api_key_redacted", session.get("api_key_value_visible") is False)
        add(f"session_{index}_c_drive_not_used", session.get("c_drive_used") is False)
        for turn in session.get("turns") or []:
            response = str(turn.get("response_text") or "")
            banned = [term for term in BAD_TERMS if term in response.lower()]
            add(f"session_{index}_turn_{turn.get('turn_index')}_no_bad_terms", not banned, ", ".join(banned))
    ok = all(item["ok"] for item in checks)
    return {"ok": ok, "checks": checks, "receipt_path": str(LATEST_RECEIPT)}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify latest Engel personality training receipt.")
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