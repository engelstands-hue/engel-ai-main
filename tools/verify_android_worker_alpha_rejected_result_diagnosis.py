from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
ALPHA = ROOT / "remote_workers" / "android_worker_alpha"
JOB_ID = "20260516T201324Z_android_worker_alpha_summarize_text_summarize_engel_remote_worke"
STATUS = ALPHA / "status" / (JOB_ID + "_status.json")
RESULT = ALPHA / "outbox" / (JOB_ID + "_result.json")
LOG = ALPHA / "logs" / (JOB_ID + ".log")
RECEIPT = ALPHA / "receipts" / (JOB_ID + "_receipt.json")
LOCAL_EXECUTOR = ALPHA / "remote_worker_local_executor.py"
JOB_PACKET = ALPHA / "jobs" / (JOB_ID + ".json")
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_ANDROID_WORKER_ALPHA_REJECTED_RESULT_DIAGNOSIS_V1.md"
CODEX_VERIFY = ROOT / "scripts" / "codex_verify.ps1"


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def load_json(path: Path) -> dict[str, object]:
    data = json.loads(read(path))
    require(isinstance(data, dict), "JSON root is not object: " + str(path.relative_to(ROOT)))
    return data


def load_local_executor():
    if str(ALPHA) not in sys.path:
        sys.path.insert(0, str(ALPHA))
    spec = importlib.util.spec_from_file_location("remote_worker_local_executor", LOCAL_EXECUTOR)
    require(spec is not None and spec.loader is not None, "could not load local executor")
    module = importlib.util.module_from_spec(spec)
    sys.modules["remote_worker_local_executor"] = module
    spec.loader.exec_module(module)
    return module


def check_real_returned_files() -> None:
    for path in [STATUS, RESULT, LOG, RECEIPT]:
        require(path.exists(), "real returned file missing: " + str(path.relative_to(ROOT)))
    status = load_json(STATUS)
    result = load_json(RESULT)
    receipt = load_json(RECEIPT)
    require(status.get("real_status") is True, "status must be marked real_status")
    require(status.get("source") == "android_worker_returned_status", "status source mismatch")
    require(status.get("job_status") == "rejected_by_worker", "status must record rejected_by_worker")
    require(result.get("real_result") is True, "result must be marked real_result")
    require(result.get("source") == "android_worker_returned_result", "result source mismatch")
    require(result.get("job_status") == "rejected_by_worker", "result must record rejected_by_worker")
    require(result.get("candidate_outputs") == [], "rejected result must not claim candidate outputs")
    require(receipt.get("final_status") == "rejected_by_worker", "receipt must record rejected_by_worker")
    require(receipt.get("outputs") == [], "rejected receipt must not claim outputs")


def check_exact_rejection_reason() -> None:
    result = load_json(RESULT)
    warnings = result.get("warnings", [])
    require(isinstance(warnings, list), "result warnings must be a list")
    for required in [
        "flagged_adb",
        "flagged_install_package",
        "flagged_download_model",
        "flagged_network",
        "flagged_ssh",
        "flagged_startup",
        "input file missing or outside worker folder: inbox\\assigned_inputs\\" + JOB_ID + "\\engel_multi_android_remote_worke.md",
    ]:
        require(required in warnings, "diagnostic source result missing expected rejection detail: " + required)
    require("Job rejected by worker validation." in read(LOG), "log must record validation rejection")


def check_minimal_fix() -> None:
    source = read(LOCAL_EXECUTOR)
    for phrase in [
        "JOB_RISK_SCAN_FIELDS",
        "requested_job_text",
        "Safety-denial fields such as blocked_actions",
        "warning_flags(requested_job_text(job))",
    ]:
        require(phrase in source, "local executor missing requested-field scan fix: " + phrase)
    module = load_local_executor()
    job = module.load_json(JOB_PACKET)
    errors = module.validate_job(job)
    for forbidden_false_positive in [
        "flagged_adb",
        "flagged_install_package",
        "flagged_download_model",
        "flagged_network",
        "flagged_ssh",
        "flagged_startup",
        "flagged_ollama",
    ]:
        require(forbidden_false_positive not in errors, "blocked_actions false positive remains: " + forbidden_false_positive)
    unsafe_job = dict(job)
    unsafe_job["instructions"] = "run this command"
    require("flagged_run_this_command" in module.validate_job(unsafe_job), "requested forbidden instruction must still be rejected")


def check_report_and_codex_verify() -> None:
    require(REPORT.exists(), "diagnosis report missing")
    report = read(REPORT)
    for phrase in [
        "Engel Android Worker Alpha Rejected Result Diagnosis V1",
        "rejected_by_worker",
        "blocked_actions false positive",
        "missing input file in Termux home",
        "path mismatch",
        "minimal fix",
        "no fake success",
        "no trusted-memory write",
        "no patch apply",
        "verifier results",
        "packaging skipped",
    ]:
        require(phrase.lower() in report.lower(), "diagnosis report missing: " + phrase)
    require("tools\\verify_android_worker_alpha_rejected_result_diagnosis.py" in read(CODEX_VERIFY), "codex verifier script missing diagnosis verifier")


def main() -> int:
    checks = [
        ("real_returned_files", check_real_returned_files),
        ("exact_rejection_reason", check_exact_rejection_reason),
        ("minimal_fix", check_minimal_fix),
        ("report_and_codex_verify", check_report_and_codex_verify),
    ]
    failures: list[str] = []
    for name, fn in checks:
        try:
            fn()
            print("PASS " + name)
        except CheckFailure as exc:
            failures.append(f"{name}: {exc}")
            print("FAIL " + name + ": " + str(exc))
        except Exception as exc:
            failures.append(f"{name}: unexpected error: {exc}")
            print("FAIL " + name + ": unexpected error: " + str(exc))
    if failures:
        print("\nAndroid Worker Alpha rejected result diagnosis verifier FAILED")
        for failure in failures:
            print("- " + failure)
        return 1
    print("\nAndroid Worker Alpha rejected result diagnosis verifier PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
