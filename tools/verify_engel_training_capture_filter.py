#!/usr/bin/env python3
"""Verify Engel training capture cannot absorb identity-confused chat data."""

from __future__ import annotations

from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
REPORT_DIR = ROOT / "reports" / "llm_training"


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    require(spec is not None and spec.loader is not None, f"cannot load module spec: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def verify_filter_behavior() -> dict[str, Any]:
    module = load_module("engel_training_capture_filter_verify", TOOLS / "engel_training_capture_filter.py")
    result = module.self_test()
    require(result.get("ok") is True, "training capture filter self-test failed")

    chase = {
        "discord_identity_lock": module.IDENTITY_LOCK,
        "discord_author_id": "189914577100603392",
        "discord_resolved_actor": "chase_lokal",
        "discord_authority_level": "guest",
    }
    good = module.classify_training_pair(
        source="discord",
        user="who am i",
        assistant="You are Chase/Lokal in this lane, not Joshua.",
        record=chase,
    )
    bad = module.classify_training_pair(
        source="discord",
        user="who am i",
        assistant="You are Joshua, the owner of Engel AI Main.",
        record=chase,
    )
    missing = module.classify_training_pair(
        source="discord",
        user="who am i",
        assistant="You are Joshua, the owner of Engel AI Main.",
        record={},
    )

    require(good.accept is True, "Chase/Lokal correct identity answer should be positive")
    require(bad.bucket == "negative_eval", "Chase/Lokal answered as Joshua must become negative eval")
    require(missing.accept is False, "Discord rows without identity metadata must not be positive")
    return {
        "self_test": result,
        "chase_good": module.decision_dict(good),
        "chase_bad": module.decision_dict(bad),
        "missing_metadata": module.decision_dict(missing),
    }


def verify_builder_wiring() -> dict[str, Any]:
    dataset_builder = (TOOLS / "engel_build_training_dataset.py").read_text(encoding="utf-8")
    package_builder = (TOOLS / "build_engel_lora_training_package.py").read_text(encoding="utf-8")

    required_dataset_markers = [
        "from engel_training_capture_filter import classify_training_pair, decision_dict",
        "capture_row(",
        "negative_eval.jsonl",
        "rejected_training_captures",
        "ENGEL_TRAINING_CAPTURE_DECISION_V1",
    ]
    required_package_markers = [
        "from engel_training_capture_filter import classify_training_pair, decision_dict",
        "CT_PUBLISH_DATASET_DIR",
        "identity_guard_examples",
        "load_ct_publish_examples",
        "ct_publish_plus_identity_guard",
        "ENGEL_TRAINING_CAPTURE_DECISION_V1",
    ]

    for marker in required_dataset_markers:
        require(marker in dataset_builder, f"dataset builder missing marker: {marker}")
    for marker in required_package_markers:
        require(marker in package_builder, f"package builder missing marker: {marker}")

    summary: dict[str, Any] = {
        "dataset_builder_markers": required_dataset_markers,
        "package_builder_markers": required_package_markers,
        "ct_publish_cache_present": False,
    }

    ct_manifest = ROOT / "runtime" / "runpod" / "ct_publish" / "dataset_manifest.json"
    if ct_manifest.is_file():
        package_module = load_module("build_engel_lora_training_package_verify", TOOLS / "build_engel_lora_training_package.py")
        rows, ct_summary = package_module.load_ct_publish_examples()
        require(len(rows) >= 60, "CT publish dataset cache exists but loads fewer than 60 positive rows")
        summary["ct_publish_cache_present"] = True
        summary["ct_publish_rows_loaded"] = len(rows)
        summary["ct_publish_rows_rejected"] = ct_summary.get("rows_rejected")
        summary["ct_publish_manifest"] = ct_summary.get("manifest")
    return summary


def verify_runpod_artifact_state() -> dict[str, Any]:
    latest = ROOT / "runtime" / "engel_lora_training_artifact_verifier_latest.json"
    active_manifest = ROOT / "runtime" / "engel_standalone_chat_llm" / "trained_lora_adapter_manifest.json"
    result: dict[str, Any] = {
        "latest_verifier_present": latest.is_file(),
        "active_manifest_present": active_manifest.is_file(),
        "latest_artifact_ok": False,
        "active_manifest_runtime_loaded": False,
        "latest_artifact_sha256": "",
        "active_manifest_sha256": "",
        "latest_artifact_is_active": False,
    }
    if latest.is_file():
        latest_obj = read_json(latest)
        result["latest_artifact_ok"] = latest_obj.get("ok") is True and latest_obj.get("training_receipt_ok") is True
        for item in latest_obj.get("files", []):
            if item.get("path") == "adapter_model.safetensors":
                result["latest_artifact_sha256"] = item.get("sha256", "")
    if active_manifest.is_file():
        active_obj = read_json(active_manifest)
        result["active_manifest_runtime_loaded"] = active_obj.get("runtime_loaded_by_current_chat_endpoint") is True
        result["active_manifest_sha256"] = active_obj.get("adapter_model", {}).get("sha256", "")
    result["latest_artifact_is_active"] = bool(
        result["latest_artifact_sha256"]
        and result["active_manifest_sha256"]
        and str(result["latest_artifact_sha256"]).casefold() == str(result["active_manifest_sha256"]).casefold()
    )
    return result


def main() -> int:
    report: dict[str, Any] = {
        "schema": "ENGEL_TRAINING_CAPTURE_FILTER_VERIFY_V1",
        "verified_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "ok": False,
        "checks": {},
    }
    try:
        report["checks"]["filter_behavior"] = verify_filter_behavior()
        report["checks"]["builder_wiring"] = verify_builder_wiring()
        report["checks"]["runpod_artifact_state"] = verify_runpod_artifact_state()
        report["ok"] = True
    except Exception as exc:
        report["error"] = str(exc)
        report["ok"] = False

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / f"ENGEL_TRAINING_CAPTURE_FILTER_VERIFY_{utc_stamp()}.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"ok": report["ok"], "report": str(path), "runpod_artifact_state": report.get("checks", {}).get("runpod_artifact_state", {})}, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
