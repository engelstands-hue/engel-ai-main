from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports" / "codex_bridge" / "ENGEL_LOCAL_LLM_ADAPTER_REVIEW_V1.md"
RUN_ROOT = ROOT / "data" / "local_llm_training" / "runs"

FINAL_STATUS_LABELS = {
    "ADAPTER_REVIEW_COMPLETE_PROMOTION_NOT_APPROVED",
    "ADAPTER_REVIEW_COMPLETE_NOT_READY",
    "ADAPTER_REVIEW_PREFLIGHT_BLOCKED",
    "NO_TRAINING_RUN_FOUND_FOR_REVIEW",
}

FORBIDDEN_REPORT_CLAIMS = [
    "Engel is trained and ready",
    "production model updated",
    "adapter deployed",
    "trusted memory updated",
    "production-ready adapter",
]


class VerifyFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise VerifyFailure(message)


def _read(path: Path) -> str:
    require(path.is_file(), f"missing file: {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8")


def _review_status(report_text: str) -> str:
    found = [label for label in FINAL_STATUS_LABELS if label in report_text]
    require(found, "review report missing required final status label")
    require(len(found) == 1, "review report must contain exactly one final status label")
    return found[0]


def _latest_run_folder() -> Path | None:
    if not RUN_ROOT.is_dir():
        return None
    v2 = sorted(RUN_ROOT.glob("ENGEL_LORA_RUN_V2_*"), key=lambda path: path.stat().st_mtime, reverse=True)
    if v2:
        return v2[0]
    v1 = sorted(RUN_ROOT.glob("ENGEL_LORA_RUN_V1_*"), key=lambda path: path.stat().st_mtime, reverse=True)
    return v1[0] if v1 else None


def _check_common_report_safety(report_text: str) -> None:
    for claim in FORBIDDEN_REPORT_CLAIMS:
        require(claim.lower() not in report_text.lower(), f"review report contains forbidden claim: {claim}")
    for needle in [
        "no production deployment occurred",
        "no trusted memory was written",
        "adapter remains untrusted",
    ]:
        require(needle in report_text.lower(), f"review report missing safety wording: {needle}")


def _check_no_run_report(report_text: str) -> None:
    require(_latest_run_folder() is None, "report says no run exists, but a run folder is present")
    for needle in [
        "NO_TRAINING_RUN_FOUND_FOR_REVIEW",
        "Reviewed run folder: none",
        "Adapter path: none",
        "Review result: no adapter run exists to review",
    ]:
        require(needle in report_text, "no-run review report missing: " + needle)


def _check_run_report(report_text: str) -> None:
    run_folder = _latest_run_folder()
    require(run_folder is not None, "review report expects a run folder but none exists")
    config_path = run_folder / "RUN_CONFIG.json"
    safety_path = run_folder / "TRAINING_SAFETY_RECEIPT.md"
    require(config_path.is_file(), "RUN_CONFIG.json missing from reviewed run folder")
    require(safety_path.is_file(), "TRAINING_SAFETY_RECEIPT.md missing from reviewed run folder")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    require(config.get("auto_merge") is False, "RUN_CONFIG auto_merge must be false")
    require(config.get("auto_deploy") is False, "RUN_CONFIG auto_deploy must be false")
    require(config.get("trusted_memory_write") is False, "RUN_CONFIG trusted_memory_write must be false")
    require(config.get("provider_calls") is False, "RUN_CONFIG provider_calls must be false")
    require(config.get("network_enabled") is False, "RUN_CONFIG network_enabled must be false")
    require(config.get("package_install_enabled") is False, "RUN_CONFIG package_install_enabled must be false")
    require(config.get("source_mutation_from_model_output") is False, "RUN_CONFIG source mutation must be false")
    require(config.get("queue_route_mutation") is False, "RUN_CONFIG queue/route mutation must be false")
    require(str(run_folder) in report_text, "review report does not identify reviewed run folder")
    require("UNTRUSTED_TRAINED_ADAPTER_PENDING_REVIEW" in report_text, "adapter must remain untrusted pending review/promotion")


def verify() -> None:
    report_text = _read(REPORT)
    status = _review_status(report_text)
    _check_common_report_safety(report_text)
    if status == "NO_TRAINING_RUN_FOUND_FOR_REVIEW":
        _check_no_run_report(report_text)
    else:
        _check_run_report(report_text)


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Engel local LLM adapter review report.")
    parser.parse_args()
    try:
        verify()
    except (VerifyFailure, json.JSONDecodeError) as exc:
        print("[FAIL]", exc)
        return 1
    print("[PASS] Engel local LLM adapter review verifier passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
