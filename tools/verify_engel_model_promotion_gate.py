#!/usr/bin/env python3
"""Verify Engel model promotion cannot silently switch chat adapters."""

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
GATE = TOOLS / "engel_model_promotion_gate.py"


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def load_module():
    spec = importlib.util.spec_from_file_location("engel_model_promotion_gate_verify", GATE)
    require(spec is not None and spec.loader is not None, f"cannot load module spec: {GATE}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["engel_model_promotion_gate_verify"] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def main() -> int:
    report: dict[str, Any] = {
        "schema": "ENGEL_MODEL_PROMOTION_GATE_VERIFY_V1",
        "verified_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "ok": False,
        "ok_meaning": (
            "ok = the gate MECHANISM is fail-closed and self-consistent. "
            "Promotion readiness is checks.state.ready_for_promotion; a "
            "passing verify with ready_for_promotion=false is normal, not a "
            "contradiction."
        ),
        "checks": {},
    }
    try:
        source = GATE.read_text(encoding="utf-8")
        for marker in [
            "APPROVE_ENGEL_MODEL_PROMOTION_V1",
            "latest_is_active",
            "ready_for_promotion",
            "rollback_manifest_path",
            "model_promotion_conversion_manifest",
            "runtime_loaded_by_current_chat_endpoint",
            "ENGEL_MODEL_PROMOTION_RECEIPT_V1",
        ]:
            require(marker in source, f"promotion gate missing marker: {marker}")

        gate = load_module()
        normalized_forbidden = {
            str(marker).replace("\\", "/").casefold()
            for marker in gate.FORBIDDEN_PATH_MARKERS
        }
        require(
            "/mnt/engel-vault" in normalized_forbidden,
            "promotion gate does not reject the retired CT245 mount",
        )
        require(
            "engel-vault-main" in normalized_forbidden,
            "promotion gate does not reject the retired storage ID",
        )
        report["checks"]["retired_storage_rejected"] = True
        state = gate.latest_state()
        report["checks"]["state"] = state
        require(state.get("latest_adapter_sha256") or not state.get("latest_verifier_path"), "latest adapter sha unavailable despite verifier path")
        require(state.get("active_adapter_sha256") or not Path(state.get("active_manifest_path", "")).is_file(), "active manifest present but adapter sha unavailable")
        require(state.get("latest_is_active") is False or state.get("latest_adapter_sha256") == state.get("active_adapter_sha256"), "latest_is_active inconsistent")
        if state.get("ready_for_promotion"):
            candidate = gate.build_candidate_manifest(state)
            report["checks"]["candidate"] = {
                "training_base_model": candidate.get("training_base_model"),
                "adapter_sha256": candidate.get("adapter_model", {}).get("sha256"),
                "adapter_gguf_sha256": candidate.get("adapter_model_gguf", {}).get("sha256"),
                "runtime_loaded_by_current_chat_endpoint": candidate.get("runtime_loaded_by_current_chat_endpoint"),
            }
            require(candidate.get("adapter_model", {}).get("sha256") == state.get("latest_adapter_sha256"), "candidate adapter sha mismatch")
            require(candidate.get("adapter_model_gguf", {}).get("sha256") == state.get("adapter_gguf_sha256"), "candidate GGUF sha mismatch")
            require(candidate.get("runtime_loaded_by_current_chat_endpoint") is False, "candidate must not claim live runtime")
        else:
            errors = state.get("errors") or []
            require(isinstance(errors, list), "not-ready state must include errors list")
        report["ok"] = True
    except Exception as exc:
        report["error"] = str(exc)
        report["ok"] = False

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / f"ENGEL_MODEL_PROMOTION_GATE_VERIFY_{utc_stamp()}.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"ok": report["ok"], "report": str(path), "ready_for_promotion": report.get("checks", {}).get("state", {}).get("ready_for_promotion")}, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
