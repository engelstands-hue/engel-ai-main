from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
MAX_READ_CHARS = 80_000
MAX_SUMMARY_CHARS = 600

CANDIDATE_VALIDATION_RECEIPTS = PROJECT_ROOT / "reports" / "ai_llama_cpp_runtime_candidate_validation" / "receipts"
REPORT_ROOT = PROJECT_ROOT / "reports" / "ai_runtime_candidate_failure_diagnosis"
DIAGNOSTIC_DIR = REPORT_ROOT / "diagnostics"
RECEIPT_DIR = REPORT_ROOT / "receipts"
PLAN_REPORT_DIR = REPORT_ROOT / "reports"
EXAMPLE_DIR = REPORT_ROOT / "examples"
CODEX_REPORT = PROJECT_ROOT / "reports" / "codex_bridge" / "ENGEL_AI_RUNTIME_CANDIDATE_FAILURE_DIAGNOSIS_V1.md"

FINAL_DECISION = "RUNTIME CANDIDATE FAILURE DIAGNOSIS RECORDED \u2014 HISTORICAL RECEIPT UNCHANGED \u2014 NO CHAT \u2014 NO TRUSTED MEMORY WRITE"


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def stamp(value: str) -> str:
    return value.replace(":", "").replace("-", "").replace("+00:00", "Z")


def safe_slug(value: str, max_length: int = 96) -> str:
    chars: list[str] = []
    for char in value.lower():
        if char.isascii() and char.isalnum():
            chars.append(char)
        elif char in {"-", "_", "."}:
            chars.append(char)
        else:
            chars.append("_")
    slug = "_".join(part for part in "".join(chars).strip("._-").split("_") if part)
    return (slug or "runtime_candidate_failure")[:max_length]


def ensure_folders() -> None:
    for folder in [REPORT_ROOT, DIAGNOSTIC_DIR, RECEIPT_DIR, PLAN_REPORT_DIR, EXAMPLE_DIR, CODEX_REPORT.parent]:
        folder.mkdir(parents=True, exist_ok=True)


def write_lf_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def project_relative(path: Path) -> str:
    try:
        return str(path.resolve(strict=False).relative_to(PROJECT_ROOT.resolve(strict=False))).replace("/", "\\")
    except ValueError:
        return str(path.resolve(strict=False))


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace")[:MAX_READ_CHARS])
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def read_text_bounded(path_text: str | None) -> str:
    if not path_text:
        return ""
    path = PROJECT_ROOT / path_text
    if not path.exists() or not path.is_file():
        path = Path(path_text)
    if not path.exists() or not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:MAX_READ_CHARS]
    except OSError:
        return ""


def sha256_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError:
        return None
    return digest.hexdigest()


def latest_candidate_validation_receipt_path() -> Path | None:
    if not CANDIDATE_VALIDATION_RECEIPTS.exists():
        return None
    rows = sorted(CANDIDATE_VALIDATION_RECEIPTS.glob("RUNTIME_CANDIDATE_VALIDATION_*.json"))
    return rows[-1] if rows else None


def latest_diagnosis_receipt() -> dict[str, Any] | None:
    if not RECEIPT_DIR.exists():
        return None
    rows: list[dict[str, Any]] = []
    for path in sorted(RECEIPT_DIR.glob("RUNTIME_CANDIDATE_FAILURE_DIAGNOSIS_*.json")):
        data = read_json(path)
        if data.get("runtime_candidate_failure_diagnosis_version") == "1":
            data["receipt_path"] = project_relative(path)
            rows.append(data)
    return rows[-1] if rows else None


def runtime_output_flags(stdout_text: str, stderr_text: str) -> dict[str, bool]:
    combined = (stdout_text + "\n" + stderr_text).lower()
    return {
        "model_loading_observed": "loading model" in combined or "model      :" in combined,
        "interactive_command_menu_observed": "available commands:" in combined,
        "prompt_marker_observed": "\n> " in combined,
        "generation_stats_observed": "generation:" in combined,
        "runtime_reported_exit": "exiting..." in combined,
        "stderr_nonempty": bool(stderr_text.strip()),
    }


def summarize_log(kind: str, text: str) -> str:
    if not text.strip():
        return kind + " log is empty."
    flags = runtime_output_flags(text if kind == "stdout" else "", text if kind == "stderr" else "")
    observations: list[str] = []
    if flags["model_loading_observed"]:
        observations.append("model loading/banner text observed")
    if flags["interactive_command_menu_observed"]:
        observations.append("interactive command menu observed")
    if flags["prompt_marker_observed"]:
        observations.append("prompt marker observed")
    if flags["generation_stats_observed"]:
        observations.append("generation statistics observed")
    if flags["runtime_reported_exit"]:
        observations.append("runtime reported exiting")
    if not observations:
        compact = " ".join(line.strip() for line in text.splitlines() if line.strip())
        return (kind + " summary: " + compact[:MAX_SUMMARY_CHARS]) if compact else kind + " log has only whitespace."
    return kind + " summary: " + "; ".join(observations) + "."


def classify_receipt(receipt: dict[str, Any], stdout_text: str, stderr_text: str) -> tuple[str, str, str]:
    exit_code = receipt.get("exit_code")
    process_started = receipt.get("runtime_process_started") is True
    process_exited = receipt.get("runtime_process_exited") is True
    timed_out = receipt.get("timed_out") is True
    interrupted = receipt.get("interrupted") is True
    orphan = receipt.get("orphan_process_detected") is True
    command_executed = receipt.get("command_executed") is True
    flags = runtime_output_flags(stdout_text, stderr_text)

    if timed_out:
        return "timeout", "The child process timed out; the historical failure should remain failed.", "Try another runtime candidate or alternate safe model-info/tokenize path."
    if orphan:
        return "orphan_detected", "The receipt says an orphan process was detected; keep the runtime fail-closed.", "Inspect process cleanup before any future replay."
    if not command_executed:
        return "blocked", "The validation did not execute a candidate command.", "Inspect the blocked reason and candidate folder shape."
    if interrupted and not process_exited:
        return "true_keyboard_interrupt", "The child process had not exited when the interruption was recorded.", "Rerun only after confirming the process cleanup path."
    if exit_code not in (0, None) and process_started:
        return "child_process_failed", "The candidate process returned a nonzero exit code.", "Try another runtime candidate or inspect stderr summary."
    if exit_code == 0 and process_exited and not timed_out and not orphan and interrupted:
        if flags["interactive_command_menu_observed"] or flags["generation_stats_observed"]:
            return (
                "contradictory_receipt_state",
                "The process appears to have exited with code 0, but the receipt marked interrupted. The validator interruption handler was too broad. The stdout also shows an interactive prompt/menu or generation statistics, so this historical run must not be promoted as a no-generation pass.",
                "Fix validator interpretation and avoid this command style unless a bounded replay proves no prompt loop or generation output.",
            )
        return (
            "contradictory_receipt_state",
            "The process appears to have exited with code 0, but the receipt marked interrupted. This likely reflects a post-process KeyboardInterrupt or stale interruption flag.",
            "Fix validator interpretation and rerun one bounded diagnostic validation if needed.",
        )
    if exit_code == 0 and process_exited and not timed_out and not orphan:
        if flags["interactive_command_menu_observed"] or flags["generation_stats_observed"]:
            return "child_process_failed", "The process exited but stdout indicates prompt-loop or generation behavior, which violates the no-generation contract.", "Try another runtime candidate or a safer tokenize/model-info path."
        return "possible_clean_no_generation_exit_needs_replay", "The child process appears to have exited cleanly without the contradictory interruption flag.", "Use a future approved replay phase before any swap approval."
    return "ambiguous", "The receipt state does not map cleanly to a known failure class.", "Inspect diagnosis logs and consider one bounded diagnostic replay."


def build_diagnosis(source_receipt_path: Path, write_receipt: bool) -> dict[str, Any]:
    ensure_folders()
    before_hash = sha256_file(source_receipt_path)
    receipt = read_json(source_receipt_path)
    stdout_text = read_text_bounded(receipt.get("stdout_log_path") if isinstance(receipt.get("stdout_log_path"), str) else None)
    stderr_text = read_text_bounded(receipt.get("stderr_log_path") if isinstance(receipt.get("stderr_log_path"), str) else None)
    classification, likely_explanation, recommended = classify_receipt(receipt, stdout_text, stderr_text)
    created_at = now_utc()
    flags = runtime_output_flags(stdout_text, stderr_text)
    diagnosis = {
        "runtime_candidate_failure_diagnosis_version": "1",
        "created_at": created_at,
        "source_receipt_path": project_relative(source_receipt_path),
        "source_receipt_sha256_before": before_hash,
        "source_receipt_sha256_after": sha256_file(source_receipt_path),
        "candidate_folder": receipt.get("candidate_folder"),
        "selected_command_style": receipt.get("selected_command_style"),
        "exit_code": receipt.get("exit_code"),
        "runtime_process_started": receipt.get("runtime_process_started"),
        "runtime_process_exited": receipt.get("runtime_process_exited"),
        "timed_out": receipt.get("timed_out"),
        "interrupted": receipt.get("interrupted"),
        "orphan_process_detected": receipt.get("orphan_process_detected"),
        "candidate_validation_passed": receipt.get("candidate_validation_passed"),
        "diagnosis_classification": classification,
        "likely_explanation": likely_explanation,
        "stdout_log_path": receipt.get("stdout_log_path"),
        "stderr_log_path": receipt.get("stderr_log_path"),
        "stdout_summary": summarize_log("stdout", stdout_text),
        "stderr_summary": summarize_log("stderr", stderr_text),
        "runtime_output_flags": flags,
        "historical_receipt_modified": False,
        "registered_runtime_changed": False,
        "runtime_ready_for_inference": False,
        "inference_enabled": False,
        "chat_enabled": False,
        "server_enabled": False,
        "trusted_memory_write_enabled": False,
        "provider_api_enabled": False,
        "source_route_queue_mutation": False,
        "recommended_next_action": recommended,
        "final_decision": FINAL_DECISION,
    }
    if write_receipt:
        slug = safe_slug(Path(str(source_receipt_path)).stem)
        path = RECEIPT_DIR / f"RUNTIME_CANDIDATE_FAILURE_DIAGNOSIS_{stamp(created_at)}_{slug}.json"
        report_path = PLAN_REPORT_DIR / f"RUNTIME_CANDIDATE_FAILURE_DIAGNOSIS_{stamp(created_at)}_{slug}.md"
        diagnosis["diagnosis_receipt_path"] = project_relative(path)
        diagnosis["diagnosis_report_path"] = project_relative(report_path)
        write_lf_text(path, json.dumps(diagnosis, indent=2, sort_keys=True) + "\n")
        report = render_report(diagnosis)
        write_lf_text(report_path, report)
        write_lf_text(CODEX_REPORT, report)
    return diagnosis


def render_report(diagnosis: dict[str, Any] | None = None) -> str:
    d = diagnosis or latest_diagnosis_receipt() or {}
    return f"""# ENGEL_AI_RUNTIME_CANDIDATE_FAILURE_DIAGNOSIS_V1

## Summary
Engel diagnoses the latest runtime candidate validation evidence without rerunning model validation. The historical receipt remains immutable evidence.

## Why This Phase Exists
The candidate validation receipt reported `exit_code: 0`, `runtime_process_exited: true`, `timed_out: false`, and `orphan_process_detected: false`, while also reporting `interrupted: true` and `candidate_validation_passed: false`.

## Candidate Validation Context
- Candidate folder: `{d.get("candidate_folder")}`
- Selected command style: `{d.get("selected_command_style")}`
- Source receipt path: `{d.get("source_receipt_path")}`

## Contradiction observed
- exit_code: `{d.get("exit_code")}`
- runtime_process_exited: `{d.get("runtime_process_exited")}`
- timed_out: `{d.get("timed_out")}`
- interrupted: `{d.get("interrupted")}`
- orphan_process_detected: `{d.get("orphan_process_detected")}`
- candidate_validation_passed: `{d.get("candidate_validation_passed")}`

## Log Summary
- stdout: {d.get("stdout_summary")}
- stderr: {d.get("stderr_summary")}
- runtime output flags: `{d.get("runtime_output_flags")}`

## Diagnosis
- classification: `{d.get("diagnosis_classification")}`
- likely explanation: {d.get("likely_explanation")}
- recommended next action: {d.get("recommended_next_action")}

## Code Logic
The future candidate validator distinguishes a real child-process interruption from a `post_process_interruption` after the child process has already exited. It also records output-contract flags so prompt-loop or generation-output behavior cannot be silently treated as a clean no-generation validation.

## Historical Evidence
- Historical receipt modified: false
- Registered runtime changed: false
- Runtime ready for inference: false

## Safety Boundaries
- No model validation replay was run in this phase.
- No runtime binary was executed by the diagnosis module.
- No download or install behavior occurred.
- No provider, API, cloud, browser, or email behavior occurred.
- No WSL, Docker, or Linux runtime was used; Hermes remains rejected / do not install on this computer.
- No chat/server mode was started.
- No trusted memory was written.
- No source, route, or queue mutation occurred beyond intended source/docs/verifier/report updates.

## Verification
- Runtime candidate failure diagnosis verifier: pending run.
- Full Codex verifier: pending run.
- Packaging skipped.

This phase diagnoses candidate validation evidence only. It does not download, install, change the registered runtime, enable inference, start chat/server mode, write trusted memory, mutate source/routes/queues, or trust model output.
"""


def status() -> dict[str, Any]:
    latest_source = latest_candidate_validation_receipt_path()
    latest_diag = latest_diagnosis_receipt()
    return {
        "runtime_candidate_failure_diagnosis_version": "1",
        "latest_candidate_validation_receipt": project_relative(latest_source) if latest_source else None,
        "latest_diagnosis_receipt": latest_diag.get("receipt_path") if latest_diag else None,
        "latest_diagnosis_classification": latest_diag.get("diagnosis_classification") if latest_diag else None,
        "registered_runtime_changed": False,
        "runtime_ready_for_inference": False,
        "inference_enabled": False,
        "chat_enabled": False,
        "server_enabled": False,
        "trusted_memory_write_enabled": False,
    }


def print_json(data: Any) -> None:
    print(json.dumps(data, indent=2, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Engel runtime candidate failure diagnosis")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    sub.add_parser("diagnose-latest")
    diagnose = sub.add_parser("diagnose-receipt")
    diagnose.add_argument("receipt_path")
    preview = sub.add_parser("reclassify-receipt-preview")
    preview.add_argument("receipt_path")
    sub.add_parser("json")
    args = parser.parse_args(argv)

    if args.command == "status":
        print_json(status())
        return 0
    if args.command == "diagnose-latest":
        latest = latest_candidate_validation_receipt_path()
        if latest is None:
            print_json({"ok": False, "error": "no_candidate_validation_receipt", "runtime_ready_for_inference": False})
            return 1
        print_json(build_diagnosis(latest, write_receipt=True))
        return 0
    if args.command == "diagnose-receipt":
        path = PROJECT_ROOT / args.receipt_path
        if not path.exists():
            path = Path(args.receipt_path)
        if not path.exists() or not path.is_file():
            print_json({"ok": False, "error": "receipt_not_found", "runtime_ready_for_inference": False})
            return 1
        print_json(build_diagnosis(path, write_receipt=True))
        return 0
    if args.command == "reclassify-receipt-preview":
        path = PROJECT_ROOT / args.receipt_path
        if not path.exists():
            path = Path(args.receipt_path)
        if not path.exists() or not path.is_file():
            print_json({"ok": False, "error": "receipt_not_found", "runtime_ready_for_inference": False})
            return 1
        data = build_diagnosis(path, write_receipt=False)
        data["preview_only"] = True
        print_json(data)
        return 0
    if args.command == "json":
        print_json({"status": status(), "latest_diagnosis": latest_diagnosis_receipt()})
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
