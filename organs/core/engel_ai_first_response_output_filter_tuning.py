from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
MAX_READ_CHARS = 120_000
MAX_OUTPUT_SUMMARY_CHARS = 4_000

SOURCE_EXIT_FIX_COMMIT = "9c2b90f9b6963c9429722b0dc6e572e840862359"
MODEL_KEY = "tiny_seed"
EXPECTED_TOKEN = "Engel"

EXIT_FIX_RECEIPT_DIR = PROJECT_ROOT / "reports" / "ai_first_local_response_smoke_exit_fix" / "receipts"
REPORT_ROOT = PROJECT_ROOT / "reports" / "ai_first_response_output_filter_tuning"
DIAGNOSTIC_DIR = REPORT_ROOT / "diagnostics"
RECEIPT_DIR = REPORT_ROOT / "receipts"
PLAN_REPORT_DIR = REPORT_ROOT / "reports"
EXAMPLE_DIR = REPORT_ROOT / "examples"
CODEX_REPORT = PROJECT_ROOT / "reports" / "codex_bridge" / "ENGEL_AI_FIRST_RESPONSE_OUTPUT_FILTER_TUNING_V1.md"

FINAL_DECISION_PASSED = "FIRST RESPONSE OUTPUT FILTER TUNING PASSED - HISTORICAL EVIDENCE CLEAN FOR SINGLE-TURN SMOKE - OUTPUT STILL UNTRUSTED - NO CHAT LOOP - NO TRUSTED MEMORY WRITE"
FINAL_DECISION_REPLAY = "FIRST RESPONSE OUTPUT FILTER TUNING NEEDS REPLAY - HISTORICAL EVIDENCE AMBIGUOUS - OUTPUT STILL UNTRUSTED - NO CHAT LOOP - NO TRUSTED MEMORY WRITE"
FINAL_DECISION_FAILED = "FIRST RESPONSE OUTPUT FILTER TUNING CONFIRMED FAILURE - OUTPUT STILL UNTRUSTED - NO CHAT LOOP - NO TRUSTED MEMORY WRITE"

NEXT_SUCCESS_ACTION = "ENGEL_AI_BOUNDED_LOCAL_CHAT_SMOKE_V1"
NEXT_REPLAY_ACTION = "ENGEL_AI_FIRST_RESPONSE_FILTER_TUNED_REPLAY_V1"
NEXT_FAILURE_ACTION = "adjust bounded command style or choose another runtime candidate"


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def stamp(value: str) -> str:
    return value.replace(":", "").replace("-", "").replace("+00:00", "Z")


def write_lf_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def ensure_folders() -> None:
    for folder in [REPORT_ROOT, DIAGNOSTIC_DIR, RECEIPT_DIR, PLAN_REPORT_DIR, EXAMPLE_DIR, CODEX_REPORT.parent]:
        folder.mkdir(parents=True, exist_ok=True)
    example = EXAMPLE_DIR / "FIRST_RESPONSE_OUTPUT_FILTER_TUNING_EXAMPLE.json"
    if not example.exists():
        write_lf_text(
            example,
            json.dumps(
                {
                    "first_response_output_filter_tuning_version": "1",
                    "example_only": True,
                    "diagnosis_classification": "clean_single_turn_exit_but_filter_too_strict",
                    "historical_receipt_modified": False,
                    "output_remains_untrusted": True,
                    "runtime_ready_for_inference": False,
                    "chat_enabled": False,
                    "server_enabled": False,
                    "trusted_memory_write_enabled": False,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
        )


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace")[:MAX_READ_CHARS])
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def read_text(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:MAX_READ_CHARS]
    except OSError:
        return ""


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


def bounded_summary(text: str) -> tuple[str, bool]:
    if len(text) <= MAX_OUTPUT_SUMMARY_CHARS:
        return text, False
    return text[:MAX_OUTPUT_SUMMARY_CHARS] + "\n[TRUNCATED]\n", True


def safety_fields() -> dict[str, bool]:
    return {
        "runtime_ready_for_inference": False,
        "inference_enabled": False,
        "chat_enabled": False,
        "server_enabled": False,
        "persistent_chat_loop_enabled": False,
        "trusted_memory_write_enabled": False,
        "model_output_trusted": False,
        "provider_api_enabled": False,
        "source_route_queue_mutation": False,
    }


def future_filter_policy() -> dict[str, bool]:
    return {
        "fatal_markers_fail_always": True,
        "suspicious_markers_require_context": True,
        "benign_markers_do_not_fail_alone": True,
        "clean_exit_required": True,
        "orphan_process_must_be_false": True,
        "output_remains_untrusted": True,
    }


def latest_exit_fix_receipt() -> dict[str, Any] | None:
    if not EXIT_FIX_RECEIPT_DIR.exists():
        return None
    rows: list[dict[str, Any]] = []
    for path in sorted(EXIT_FIX_RECEIPT_DIR.glob("FIRST_LOCAL_RESPONSE_SMOKE_EXIT_FIX_*.json")):
        data = read_json(path)
        if data.get("first_local_response_smoke_exit_fix_version") == "1":
            data["receipt_path"] = project_relative(path)
            data["_absolute_receipt_path"] = str(path)
            rows.append(data)
    return rows[-1] if rows else None


def latest_tuning_receipt() -> dict[str, Any] | None:
    if not RECEIPT_DIR.exists():
        return None
    rows: list[dict[str, Any]] = []
    for path in sorted(RECEIPT_DIR.glob("FIRST_RESPONSE_OUTPUT_FILTER_TUNING_*.json")):
        data = read_json(path)
        if data.get("first_response_output_filter_tuning_version") == "1":
            data["receipt_path"] = project_relative(path)
            rows.append(data)
    return rows[-1] if rows else None


def load_exit_fix_logs(receipt: dict[str, Any] | None) -> tuple[str, str]:
    if not receipt:
        return "", ""
    return (
        read_text(repo_path(receipt.get("stdout_log_path"))),
        read_text(repo_path(receipt.get("stderr_log_path"))),
    )


def line_prompt_only_count_after_token(text: str, token: str = EXPECTED_TOKEN) -> int:
    token_index = text.find(token)
    if token_index < 0:
        return 0
    tail = text[token_index + len(token):]
    count = 0
    for line in tail.splitlines():
        if line.strip() in {">", ">>>", "..."}:
            count += 1
    return count


def line_prompt_echo_count(text: str) -> int:
    return sum(1 for line in text.splitlines() if line.strip().startswith("> Reply with exactly: Engel"))


def classify_markers(stdout_text: str, stderr_text: str) -> dict[str, Any]:
    combined = (stdout_text or "") + "\n" + (stderr_text or "")
    lower = combined.lower()
    fatal: list[dict[str, str]] = []
    suspicious: list[dict[str, str]] = []
    benign: list[dict[str, str]] = []

    def add(bucket: list[dict[str, str]], marker_type: str, evidence: str) -> None:
        if not any(item["type"] == marker_type and item["evidence"] == evidence for item in bucket):
            bucket.append({"type": marker_type, "evidence": evidence})

    server_patterns = [
        "server listening",
        "listening on",
        "listening at",
        "llama server",
        "http server",
        "bind address",
        "server started",
    ]
    for pattern in server_patterns:
        if pattern in lower:
            add(fatal, "fatal_server_startup", pattern)

    wait_patterns = [
        "waiting for input",
        "press enter",
        "enter prompt",
        "input prompt",
        "stdin open",
        "readline",
    ]
    for pattern in wait_patterns:
        if pattern in lower:
            add(fatal, "fatal_interactive_wait", pattern)

    if "interactive mode" in lower and "exiting" not in lower:
        add(fatal, "fatal_persistent_chat", "interactive mode without clean exit marker")
    if "persistent chat" in lower or "chat loop" in lower:
        add(fatal, "fatal_persistent_chat", "persistent/chat loop marker")

    prompt_after_token = line_prompt_only_count_after_token(combined)
    if prompt_after_token >= 2:
        add(fatal, "fatal_prompt_loop", "repeated prompt marker after expected token")
    elif prompt_after_token == 1:
        add(suspicious, "suspicious_prompt_marker", "single prompt marker after expected token")

    if "available commands:" in lower:
        add(suspicious, "suspicious_command_menu_banner", "available commands:")
    slash_markers = ["/exit", "/regen", "/clear", "/read <file>", "/glob <pattern>", "/help"]
    for marker in slash_markers:
        if marker in lower:
            add(suspicious, "suspicious_command_menu_banner", marker)
    if "ctrl+c" in lower:
        add(suspicious, "suspicious_command_menu_banner", "Ctrl+C mention")
    if re.search(r"(?m)^\s*>\s*$", combined):
        add(suspicious, "suspicious_prompt_marker", "standalone prompt marker")

    if "loading model" in lower or "build      :" in lower or "modalities :" in lower:
        add(benign, "benign_llama_banner", "llama.cpp banner/model load scaffold")
    if "available commands:" in lower and "exiting" in lower:
        add(benign, "benign_help_scaffolding", "static command scaffold followed by exit")
    if line_prompt_echo_count(combined):
        add(benign, "benign_prompt_echo", "fixed prompt echo")
    if "[ prompt:" in lower or "generation:" in lower:
        add(benign, "benign_generation_stats_after_exit", "timing summary")
    if EXPECTED_TOKEN in combined:
        add(benign, "clean_expected_token", EXPECTED_TOKEN)
    if "exiting" in lower:
        add(benign, "benign_llama_banner", "clean exit banner")

    return {
        "marker_classes": {
            "fatal": fatal,
            "suspicious": suspicious,
            "benign": benign,
        },
        "fatal_marker_types": sorted({item["type"] for item in fatal}),
        "suspicious_marker_types": sorted({item["type"] for item in suspicious}),
        "benign_marker_types": sorted({item["type"] for item in benign}),
        "prompt_markers_after_expected_token": prompt_after_token,
        "prompt_echo_markers": line_prompt_echo_count(combined),
    }


def classify_evidence(receipt: dict[str, Any], stdout_text: str, stderr_text: str) -> dict[str, Any]:
    markers = classify_markers(stdout_text, stderr_text)
    fatal_types = set(markers["fatal_marker_types"])
    source_exit_code = receipt.get("exit_code")
    source_timed_out = receipt.get("timed_out") is True
    source_interrupted = receipt.get("interrupted") is True
    source_orphan = receipt.get("orphan_process_detected") is True
    source_exited = receipt.get("runtime_process_exited") is True
    expected_seen = receipt.get("expected_token_seen") is True
    output_marked_untrusted = receipt.get("output_marked_untrusted") is True
    output_captured = receipt.get("output_captured") is True
    server_enabled = receipt.get("server_enabled") is True
    persistent_chat_loop_enabled = receipt.get("persistent_chat_loop_enabled") is True
    trusted_memory_write_enabled = receipt.get("trusted_memory_write_enabled") is True

    if server_enabled or "fatal_server_startup" in fatal_types:
        classification = "server_or_persistent_mode_detected"
    elif persistent_chat_loop_enabled or "fatal_persistent_chat" in fatal_types:
        classification = "server_or_persistent_mode_detected"
    elif "fatal_prompt_loop" in fatal_types:
        classification = "unsafe_prompt_loop_confirmed"
    elif "fatal_interactive_wait" in fatal_types or "fatal_open_stdin_wait" in fatal_types:
        classification = "unsafe_interactive_wait_confirmed"
    elif source_exit_code != 0 or source_timed_out or source_interrupted or source_orphan or not source_exited:
        classification = "real_failure"
    elif not expected_seen or not output_marked_untrusted or not output_captured or trusted_memory_write_enabled:
        classification = "ambiguous_needs_replay"
    elif not markers["marker_classes"]["fatal"]:
        classification = "clean_single_turn_exit_but_filter_too_strict"
    else:
        classification = "ambiguous_needs_replay"

    passed_after_tuning = classification == "clean_single_turn_exit_but_filter_too_strict"
    if passed_after_tuning:
        final_decision = FINAL_DECISION_PASSED
        recommended_next_action = NEXT_SUCCESS_ACTION
        filter_tuning_applied = True
    elif classification == "ambiguous_needs_replay":
        final_decision = FINAL_DECISION_REPLAY
        recommended_next_action = NEXT_REPLAY_ACTION
        filter_tuning_applied = False
    else:
        final_decision = FINAL_DECISION_FAILED
        recommended_next_action = NEXT_FAILURE_ACTION
        filter_tuning_applied = False

    return {
        **markers,
        "diagnosis_classification": classification,
        "filter_tuning_applied": filter_tuning_applied,
        "historical_first_response_smoke_reclassified_as_passed": passed_after_tuning,
        "first_response_smoke_passed_after_tuning_preview": passed_after_tuning,
        "output_marked_untrusted": True,
        "recommended_next_action": recommended_next_action,
        "final_decision": final_decision,
        **safety_fields(),
    }


def tuning_payload(write_receipt: bool = False) -> dict[str, Any]:
    receipt = latest_exit_fix_receipt() or {}
    stdout_text, stderr_text = load_exit_fix_logs(receipt)
    combined_summary, truncated = bounded_summary((stdout_text + "\n" + stderr_text).strip())
    evidence = classify_evidence(receipt, stdout_text, stderr_text) if receipt else {
        "marker_classes": {"fatal": [], "suspicious": [], "benign": []},
        "fatal_marker_types": [],
        "suspicious_marker_types": [],
        "benign_marker_types": [],
        "diagnosis_classification": "real_failure",
        "filter_tuning_applied": False,
        "historical_first_response_smoke_reclassified_as_passed": False,
        "first_response_smoke_passed_after_tuning_preview": False,
        "recommended_next_action": NEXT_FAILURE_ACTION,
        "final_decision": FINAL_DECISION_FAILED,
    }
    created_at = now_utc()
    payload = {
        "first_response_output_filter_tuning_version": "1",
        "created_at": created_at,
        "created_by": "Engel AI First Response Output Filter Tuning",
        "source_exit_fix_commit": SOURCE_EXIT_FIX_COMMIT,
        "source_exit_fix_receipt": receipt.get("receipt_path"),
        "source_exit_code": receipt.get("exit_code"),
        "source_timed_out": receipt.get("timed_out"),
        "source_interrupted": receipt.get("interrupted"),
        "source_orphan_process_detected": receipt.get("orphan_process_detected"),
        "source_runtime_process_exited": receipt.get("runtime_process_exited"),
        "source_expected_token_seen": receipt.get("expected_token_seen"),
        "source_output_marked_untrusted": receipt.get("output_marked_untrusted"),
        "source_output_captured": receipt.get("output_captured"),
        "historical_receipt_modified": False,
        "source_selected_command_style": receipt.get("selected_command_style"),
        "source_command_args": receipt.get("command_args"),
        "source_final_decision": receipt.get("final_decision"),
        "bounded_output_summary": combined_summary,
        "bounded_output_truncated": truncated,
        "future_filter_policy": future_filter_policy(),
        **evidence,
        **safety_fields(),
    }
    if write_receipt:
        return persist_receipt(payload)
    return payload


def persist_receipt(payload: dict[str, Any]) -> dict[str, Any]:
    ensure_folders()
    created_at = str(payload.get("created_at") or now_utc())
    prefix = f"FIRST_RESPONSE_OUTPUT_FILTER_TUNING_{stamp(created_at)}_tiny_seed"
    receipt_path = RECEIPT_DIR / f"{prefix}.json"
    report_path = PLAN_REPORT_DIR / f"{prefix}.md"
    diagnostic_path = DIAGNOSTIC_DIR / f"{prefix}_diagnosis.json"
    payload["receipt_path"] = project_relative(receipt_path)
    payload["report_path"] = project_relative(report_path)
    payload["diagnostic_path"] = project_relative(diagnostic_path)
    write_lf_text(receipt_path, json.dumps(payload, indent=2, sort_keys=True) + "\n")
    write_lf_text(diagnostic_path, json.dumps(payload, indent=2, sort_keys=True) + "\n")
    report = render_report(payload)
    write_lf_text(report_path, report)
    write_lf_text(CODEX_REPORT, report)
    return payload


def status_payload() -> dict[str, Any]:
    source = latest_exit_fix_receipt()
    latest = latest_tuning_receipt()
    return {
        "first_response_output_filter_tuning_version": "1",
        "source_exit_fix_receipt": source.get("receipt_path") if source else None,
        "source_exit_code": source.get("exit_code") if source else None,
        "source_timed_out": source.get("timed_out") if source else None,
        "source_interrupted": source.get("interrupted") if source else None,
        "source_orphan_process_detected": source.get("orphan_process_detected") if source else None,
        "source_expected_token_seen": source.get("expected_token_seen") if source else None,
        "source_output_marked_untrusted": source.get("output_marked_untrusted") if source else None,
        "latest_tuning_receipt": latest.get("receipt_path") if latest else None,
        "latest_diagnosis_classification": latest.get("diagnosis_classification") if latest else None,
        "first_response_output_filter_tuning_passed": latest.get("diagnosis_classification") == "clean_single_turn_exit_but_filter_too_strict" if latest else False,
        **safety_fields(),
    }


def render_marker_table(marker_classes: dict[str, Any]) -> str:
    lines = ["| Severity | Type | Evidence |", "| --- | --- | --- |"]
    for severity in ["fatal", "suspicious", "benign"]:
        items = marker_classes.get(severity) if isinstance(marker_classes, dict) else []
        if not items:
            lines.append(f"| {severity} | none | none |")
            continue
        for item in items:
            lines.append(f"| {severity} | {item.get('type')} | `{item.get('evidence')}` |")
    return "\n".join(lines)


def render_report(payload: dict[str, Any] | None = None) -> str:
    data = payload or latest_tuning_receipt() or tuning_payload(False)
    marker_classes = data.get("marker_classes") if isinstance(data.get("marker_classes"), dict) else {"fatal": [], "suspicious": [], "benign": []}
    return f"""# ENGEL_AI_FIRST_RESPONSE_OUTPUT_FILTER_TUNING_V1

## Summary
This phase tunes the first-response output classifier by separating fatal, suspicious, and benign llama.cpp output markers.

## Why This Phase Exists
The exit-fix smoke exited cleanly and produced bounded untrusted output, but the earlier classifier treated banner/menu scaffolding as fatal. This phase reclassifies historical evidence without editing old receipts or running another model process.

## Source Exit-Fix Receipt
- source commit: `{data.get("source_exit_fix_commit", SOURCE_EXIT_FIX_COMMIT)}`
- source receipt: `{data.get("source_exit_fix_receipt")}`

## Exit-Fix Result Recap
- exit code: `{data.get("source_exit_code")}`
- timed out: `{data.get("source_timed_out")}`
- interrupted: `{data.get("source_interrupted")}`
- orphan process detected: `{data.get("source_orphan_process_detected")}`
- expected token seen: `{data.get("source_expected_token_seen")}`
- output marked untrusted: `{data.get("source_output_marked_untrusted")}`

## Marker Classification Table
{render_marker_table(marker_classes)}

## Marker Summary
- Fatal markers found: `{data.get("fatal_marker_types", [])}`
- Suspicious markers found: `{data.get("suspicious_marker_types", [])}`
- Benign markers found: `{data.get("benign_marker_types", [])}`

## Diagnosis
- Diagnosis classification: `{data.get("diagnosis_classification")}`
- Filter tuning applied: `{data.get("filter_tuning_applied")}`
- Historical receipt unchanged: `{data.get("historical_receipt_modified") is False}`
- Historical evidence considered valid single-turn first response smoke: `{data.get("historical_first_response_smoke_reclassified_as_passed")}`
- First response smoke passed after tuning preview: `{data.get("first_response_smoke_passed_after_tuning_preview")}`

## Readiness Result
- runtime ready for inference: `{data.get("runtime_ready_for_inference", False)}`
- inference enabled: `{data.get("inference_enabled", False)}`
- chat enabled: `{data.get("chat_enabled", False)}`
- server enabled: `{data.get("server_enabled", False)}`
- persistent chat loop enabled: `{data.get("persistent_chat_loop_enabled", False)}`
- trusted memory write enabled: `{data.get("trusted_memory_write_enabled", False)}`
- model output trusted: `{data.get("model_output_trusted", False)}`
- recommended next action: `{data.get("recommended_next_action")}`

## Safety Boundaries
- New model process run in this phase: `False`
- Historical exit-fix receipt modified: `{data.get("historical_receipt_modified")}`
- Provider API enabled: `{data.get("provider_api_enabled", False)}`
- Source/route/queue mutation: `{data.get("source_route_queue_mutation", False)}`

## Verification Results
- Output filter tuning verifier: pending run.
- Exit-fix verifier: pending run.
- Runtime readiness verifier: pending run.
- Full Codex verifier result: pending run.
- Packaging skipped.

This phase tunes output classification only. It does not run a new model process, enable persistent chat, enable server mode, write trusted memory, enable startup auto-load, call providers, run larger models, or trust model output.
"""


def write_initial_report() -> None:
    ensure_folders()
    if not CODEX_REPORT.exists():
        write_lf_text(CODEX_REPORT, render_report(None))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Engel AI first response output filter tuning")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    sub.add_parser("diagnose-latest")
    sub.add_parser("reclassify-latest-preview")
    sub.add_parser("json")
    args = parser.parse_args(argv)

    ensure_folders()
    write_initial_report()
    if args.command == "status":
        print(json.dumps(status_payload(), indent=2, sort_keys=True))
        return 0
    if args.command == "diagnose-latest":
        print(json.dumps(tuning_payload(False), indent=2, sort_keys=True))
        return 0
    if args.command == "reclassify-latest-preview":
        print(json.dumps(tuning_payload(True), indent=2, sort_keys=True))
        return 0
    if args.command == "json":
        payload = {
            "status": status_payload(),
            "diagnosis": tuning_payload(False),
            "latest_tuning_receipt": latest_tuning_receipt(),
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
