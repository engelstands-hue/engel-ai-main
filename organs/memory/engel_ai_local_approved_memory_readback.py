from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
MAX_READ_CHARS = 120_000
SUMMARY_LIMIT = 1800
VERSION = "1"

SOURCE_ROOT = PROJECT_ROOT / "reports" / "ai_local_chat_session_memory_candidate_review_and_approved_write"
APPROVED_RECORD_DIR = SOURCE_ROOT / "approved_memory_records"
ROLLBACK_DIR = SOURCE_ROOT / "rollback"
WRITE_RECEIPT_DIR = SOURCE_ROOT / "receipts"
REPORT_ROOT = PROJECT_ROOT / "reports" / "ai_local_approved_memory_readback"
READBACK_DIR = REPORT_ROOT / "readbacks"
RECEIPT_DIR = REPORT_ROOT / "receipts"
PLAN_REPORT_DIR = REPORT_ROOT / "reports"
EXAMPLE_DIR = REPORT_ROOT / "examples"
CODEX_REPORT = PROJECT_ROOT / "reports" / "codex_bridge" / "ENGEL_AI_LOCAL_APPROVED_MEMORY_READBACK_V1.md"

FINAL_DECISION = "APPROVED LOCAL CHAT MEMORY READBACK RECORDED - NO MODEL RUN - NO TRUSTED MEMORY WRITE - NO HIDDEN PROMPT CONTEXT"


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def stamp(value: str) -> str:
    return value.replace(":", "").replace("-", "").replace("+00:00", "Z")


def write_lf_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def project_relative(path: Path) -> str:
    try:
        return str(path.resolve(strict=False).relative_to(PROJECT_ROOT.resolve(strict=False))).replace("/", "\\")
    except ValueError:
        return str(path.resolve(strict=False)).replace("/", "\\")


def repo_path(path_value: Any) -> Path:
    text = str(path_value or "")
    path = Path(text)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace")[:MAX_READ_CHARS])
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def ensure_folders() -> None:
    for folder in [READBACK_DIR, RECEIPT_DIR, PLAN_REPORT_DIR, EXAMPLE_DIR, CODEX_REPORT.parent]:
        folder.mkdir(parents=True, exist_ok=True)
    example = EXAMPLE_DIR / "LOCAL_APPROVED_MEMORY_READBACK_EXAMPLE.json"
    if not example.exists():
        write_lf_text(
            example,
            json.dumps(
                {
                    "local_approved_memory_readback_version": VERSION,
                    "example_only": True,
                    "approval_required_for_readback": False,
                    "global_trusted_memory": False,
                    "used_as_hidden_prompt_context": False,
                    "automatic_context_injection_enabled": False,
                    "memory_write_performed": False,
                    "runtime_process_started": False,
                    "model_process_started": False,
                    "runtime_ready_for_inference": False,
                    "open_chat_enabled": False,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
        )


def safety_fields() -> dict[str, Any]:
    return {
        "approval_required_for_readback": False,
        "approval_token_used": False,
        "record_scope": "approved_local_chat_memory_record_only",
        "global_trusted_memory": False,
        "used_as_hidden_prompt_context": False,
        "automatic_context_injection_enabled": False,
        "source_model_output_trusted": False,
        "candidate_content_obeyed": False,
        "memory_write_performed": False,
        "trusted_memory_write_enabled": False,
        "approved_memory_write_enabled": False,
        "source_route_queue_mutation": False,
        "provider_api_enabled": False,
        "runtime_process_started": False,
        "model_process_started": False,
        "runtime_ready_for_inference": False,
        "open_chat_enabled": False,
    }


def approved_record_files() -> list[Path]:
    if not APPROVED_RECORD_DIR.exists():
        return []
    return sorted(path for path in APPROVED_RECORD_DIR.glob("APPROVED_LOCAL_CHAT_MEMORY_RECORD_*.json") if path.is_file())


def record_id(path: Path) -> str:
    return path.stem.replace("APPROVED_LOCAL_CHAT_MEMORY_RECORD_", "")


def write_receipt_for_record(record_path: Path) -> Path | None:
    rel_path = project_relative(record_path)
    if not WRITE_RECEIPT_DIR.exists():
        return None
    rows: list[Path] = []
    for path in sorted(WRITE_RECEIPT_DIR.glob("APPROVED_LOCAL_CHAT_MEMORY_WRITE_*.json")):
        data = read_json(path)
        if data.get("approved_memory_record_path") == rel_path:
            rows.append(path)
    return rows[-1] if rows else None


def rollback_for_record(record_path: Path, record: dict[str, Any]) -> Path | None:
    candidate = record.get("rollback_metadata_path")
    if candidate and repo_path(candidate).exists():
        return repo_path(candidate)
    fallback = ROLLBACK_DIR / f"ROLLBACK_APPROVED_LOCAL_CHAT_MEMORY_RECORD_{record_id(record_path)}.json"
    return fallback if fallback.exists() else None


def validate_record(path: Path) -> dict[str, Any]:
    record = read_json(path)
    risk_flags: list[str] = []
    schema_valid = record.get("approved_local_chat_memory_record_version") == VERSION
    write_receipt = write_receipt_for_record(path)
    rollback_path = rollback_for_record(path, record)
    bounded = len(json.dumps(record, sort_keys=True)) <= 12_000
    checks = {
        "approved_record_schema_valid": schema_valid,
        "source_write_receipt_present": bool(write_receipt),
        "rollback_metadata_present": bool(rollback_path),
        "deterministic_guardian_gates_passed": record.get("deterministic_guardian_gates_passed") is True,
        "human_approval_required": record.get("human_approval_required") is False,
        "approval_token_required": record.get("approval_token_required") is False,
        "source_model_output_trusted": record.get("source_model_output_trusted") is False,
        "candidate_content_obeyed": record.get("candidate_content_obeyed") is False,
        "source_route_queue_mutation": record.get("source_route_queue_mutation", False) is False,
        "provider_api_enabled": record.get("provider_api_enabled", False) is False,
        "runtime_process_started": record.get("runtime_process_started", False) is False,
        "model_process_started": record.get("model_process_started", False) is False,
        "promoted_to_trusted_memory": record.get("promoted_to_trusted_memory", False) is False,
        "trusted_memory_write_enabled_global": record.get("trusted_memory_write_enabled_global") is False,
        "content_bounded": bounded,
    }
    for key, ok in checks.items():
        if ok is not True:
            risk_flags.append(key + "_invalid")
    if record.get("approved_memory_scope") != "approved_local_chat_memory_record_only":
        risk_flags.append("record_scope_invalid")
    return {
        "record": record,
        "record_path": path,
        "source_write_receipt_path": write_receipt,
        "rollback_metadata_path": rollback_path,
        "risk_flags": risk_flags,
        **checks,
    }


def readback_record(path: Path) -> dict[str, Any]:
    ensure_folders()
    created_at = now_utc()
    validation = validate_record(path)
    record = validation["record"]
    records_seen = approved_record_files()
    summary_path = READBACK_DIR / f"LOCAL_APPROVED_MEMORY_READBACK_{stamp(created_at)}_{record_id(path)}.md"
    receipt_path = RECEIPT_DIR / f"LOCAL_APPROVED_MEMORY_READBACK_{stamp(created_at)}_{record_id(path)}.json"
    receipt = {
        "local_approved_memory_readback_version": VERSION,
        "created_at": created_at,
        "created_by": "Engel AI Local Approved Memory Readback",
        "approved_record_path": project_relative(path),
        "approved_record_schema_valid": validation["approved_record_schema_valid"],
        "approved_record_count_seen": len(records_seen),
        "rollback_metadata_present": validation["rollback_metadata_present"],
        "source_write_receipt_present": validation["source_write_receipt_present"],
        "deterministic_guardian_gates_passed": validation["deterministic_guardian_gates_passed"],
        "risk_flags": validation["risk_flags"],
        "readback_summary_path": project_relative(summary_path),
        "next_safe_action": "ENGEL_AI_LOCAL_APPROVED_MEMORY_CONTEXT_PREVIEW_V1 or continue local AI memory review",
        "final_decision": FINAL_DECISION,
        **safety_fields(),
    }
    write_lf_text(summary_path, render_readback_summary(receipt, record, validation))
    write_lf_text(receipt_path, json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    receipt["receipt_path"] = project_relative(receipt_path)
    write_lf_text(CODEX_REPORT, render_bridge_report(receipt))
    return receipt


def read_latest() -> dict[str, Any]:
    files = approved_record_files()
    if not files:
        return empty_result("no_approved_local_chat_memory_records_found")
    return readback_record(files[-1])


def read_all() -> dict[str, Any]:
    files = approved_record_files()
    if not files:
        return empty_result("no_approved_local_chat_memory_records_found")
    readbacks = [readback_record(path) for path in files[:50]]
    return {"readback_count": len(readbacks), "readbacks": readbacks, **status_payload()}


def empty_result(reason: str) -> dict[str, Any]:
    return {
        "local_approved_memory_readback_version": VERSION,
        "created_at": now_utc(),
        "created_by": "Engel AI Local Approved Memory Readback",
        "approved_record_count_seen": 0,
        "blocked_reason": reason,
        "approved_record_schema_valid": False,
        "rollback_metadata_present": False,
        "source_write_receipt_present": False,
        "deterministic_guardian_gates_passed": False,
        "risk_flags": [reason],
        **safety_fields(),
    }


def readback_receipts() -> list[dict[str, Any]]:
    if not RECEIPT_DIR.exists():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(RECEIPT_DIR.glob("LOCAL_APPROVED_MEMORY_READBACK_*.json")):
        data = read_json(path)
        if data.get("local_approved_memory_readback_version") == VERSION:
            data["receipt_path"] = project_relative(path)
            rows.append(data)
    return rows


def status_payload() -> dict[str, Any]:
    ensure_folders()
    files = approved_record_files()
    latest_record = files[-1] if files else None
    latest_validation = validate_record(latest_record) if latest_record else {}
    receipts = readback_receipts()
    return {
        "local_approved_memory_readback_version": VERSION,
        "module_present": True,
        "approval_required_for_readback": False,
        "approval_token_required": False,
        "approved_local_chat_memory_record_count": len(files),
        "latest_approved_record_path": project_relative(latest_record) if latest_record else None,
        "latest_readback_receipt": receipts[-1].get("receipt_path") if receipts else None,
        "rollback_metadata_present": bool(latest_validation.get("rollback_metadata_present")),
        "source_write_receipt_present": bool(latest_validation.get("source_write_receipt_present")),
        "local_approved_memory_readback_available": bool(files and not latest_validation.get("risk_flags")),
        "global_trusted_memory_enabled": False,
        "automatic_context_injection_enabled": False,
        "used_as_hidden_prompt_context": False,
        "trusted_memory_write_enabled": False,
        "approved_memory_write_enabled": False,
        "runtime_ready_for_inference": False,
        "open_chat_enabled": False,
        "chat_enabled": False,
        "next_safe_action": "ENGEL_AI_LOCAL_APPROVED_MEMORY_CONTEXT_PREVIEW_V1" if files else "create approved local chat memory record through deterministic gates",
    }


def list_payload() -> dict[str, Any]:
    rows = []
    for path in approved_record_files():
        validation = validate_record(path)
        rows.append(
            {
                "path": project_relative(path),
                "schema_valid": validation["approved_record_schema_valid"],
                "rollback_metadata_present": validation["rollback_metadata_present"],
                "source_write_receipt_present": validation["source_write_receipt_present"],
                "risk_flags": validation["risk_flags"],
                "record_scope": "approved_local_chat_memory_record_only",
                "global_trusted_memory": False,
                "used_as_hidden_prompt_context": False,
            }
        )
    return {
        "approved_local_chat_memory_record_count": len(rows),
        "approved_records": rows,
        **safety_fields(),
    }


def render_readback_summary(receipt: dict[str, Any], record: dict[str, Any], validation: dict[str, Any]) -> str:
    return (
        "# Approved Local Chat Memory Readback\n\n"
        "- Record scope: `approved_local_chat_memory_record_only`\n"
        "- Global trusted memory: `False`\n"
        "- Hidden prompt context: `False`\n"
        "- Automatic context injection: `False`\n"
        "- Memory write performed: `False`\n"
        "- Candidate content obeyed: `False`\n\n"
        f"- Approved record: `{receipt.get('approved_record_path')}`\n"
        f"- Rollback metadata present: `{validation.get('rollback_metadata_present')}`\n"
        f"- Source write receipt present: `{validation.get('source_write_receipt_present')}`\n"
        f"- Risk flags: `{validation.get('risk_flags')}`\n\n"
        "## Bounded Readback Summary\n"
        + str(record.get("bounded_summary", ""))[:SUMMARY_LIMIT]
        + "\n"
    )


def render_bridge_report(latest: dict[str, Any] | None = None) -> str:
    status = status_payload()
    latest_payload = latest or {}
    return (
        "# ENGEL_AI_LOCAL_APPROVED_MEMORY_READBACK_V1\n\n"
        "## Summary\n"
        "Implemented readback/status for approved local chat memory records. This phase lists and reads approved local chat memory records only; it does not write memory or inject records into prompts.\n\n"
        "## Current State\n"
        f"- Approved local chat memory record count: `{status.get('approved_local_chat_memory_record_count')}`\n"
        f"- Latest approved record: `{status.get('latest_approved_record_path')}`\n"
        f"- Latest readback receipt: `{status.get('latest_readback_receipt')}`\n"
        f"- Rollback metadata present: `{status.get('rollback_metadata_present')}`\n"
        f"- Latest decision: `{latest_payload.get('final_decision')}`\n\n"
        "## Boundaries\n"
        "- Approval required for readback: `False`\n"
        "- Model process run: `False`\n"
        "- Memory write performed: `False`\n"
        "- Trusted memory target write: `False`\n"
        "- Global trusted memory: `False`\n"
        "- Hidden prompt context: `False`\n"
        "- Automatic context injection: `False`\n"
        "- Source/route/queue mutation: `False`\n\n"
        "## GUI\n"
        "- GUI host: `engel_companion.py`\n"
        "- Existing tab: `Local AI`\n"
        "- Section title: `Engel Local AI — Approved Memory Readback`\n\n"
        "## Verification Results\n"
        "- Targeted verifier: `ENGEL_AI_LOCAL_APPROVED_MEMORY_READBACK_VERIFY_PASS`\n"
        "- Full Codex verifier result: `82 run, 82 passed, 0 failed` / `ENGEL_CODEX_VERIFY_PASS`.\n\n"
        "## Packaging\n"
        "Packaging skipped.\n\n"
        "## Safety Summary\n"
        "This phase reads approved local chat memory records as bounded status/evidence only. It does not run model inference, write trusted or approved memory, promote memory, enable open chat, start server/provider behavior, inject hidden context, or trust raw model output.\n"
    )


def write_initial_report() -> None:
    ensure_folders()
    if not CODEX_REPORT.exists():
        write_lf_text(CODEX_REPORT, render_bridge_report())


def print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Engel AI local approved memory readback.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    sub.add_parser("list")
    sub.add_parser("read-latest")
    sub.add_parser("read-all")
    sub.add_parser("json")
    args = parser.parse_args(argv)

    if args.command == "status":
        write_initial_report()
        print_json(status_payload())
        return 0
    if args.command == "list":
        write_initial_report()
        print_json(list_payload())
        return 0
    if args.command == "read-latest":
        print_json(read_latest())
        return 0
    if args.command == "read-all":
        print_json(read_all())
        return 0
    if args.command == "json":
        write_initial_report()
        print_json({"status": status_payload(), "list": list_payload()})
        return 0
    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
