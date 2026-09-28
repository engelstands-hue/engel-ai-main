#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
from engel_local_first_receipt_proof import evaluate_local_first_evidence

REPORT_DIR = ROOT / "reports" / "engel_discord_local_first_proof"


def main() -> int:
    failures: list[str] = []
    prompt = "fresh proof prompt"
    stamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def evaluate(evidence: dict) -> dict:
        return evaluate_local_first_evidence(evidence)

    good_local = evaluate(
            {
                "ok": True,
                "status": "large local chat replied",
                "provider": "local-llama-cpp-large-chat-gguf",
                "provider_api_enabled": False,
                "model": "/opt/engel/models-active/test.gguf",
                "quality_gate_degraded": False,
                "local_semantic_quality": {"ok": True},
                "training_sample_eligible": True,
            }
    )
    if good_local.get("verified") is not True:
        failures.append("good local model receipt was not verified")

    degraded_local = evaluate(
            {
                "ok": True,
                "status": "local model replied with quality warning",
                "provider": "local-llama-cpp-large-chat-gguf",
                "provider_api_enabled": False,
                "model": "/opt/engel/models-active/test.gguf",
                "quality_gate_degraded": True,
                "local_semantic_quality": {"ok": False},
                "training_sample_eligible": True,
            }
    )
    if degraded_local.get("verified") is True or degraded_local.get("quality_verified") is True:
        failures.append("degraded local model receipt was accepted")

    provider_after_local = evaluate(
            {
                "ok": True,
                "status": "provider bridge replied",
                "provider": "Claude/Anthropic",
                "provider_api_enabled": True,
                "escalated_from": 2,
                "local_ct_lora_first_attempted": True,
                "local_ct_lora_first_failed": True,
                "provider_reply_quality_gate_passed": True,
                "provider_final_semantic_quality": {"ok": True},
                "training_sample_eligible": True,
            }
    )
    if provider_after_local.get("verified_local_first_escalation") is not True:
        failures.append("provider receipt with local-first depth-2 proof was not verified")

    ok = not failures
    receipt = {
        "schema": "engel_discord_local_first_proof_verifier_v1",
        "ok": ok,
        "status": "PASS" if ok else "FAIL",
        "created_at_utc": stamp,
        "failures": failures,
        "model_runtime_loaded": False,
        "provider_calls_made": False,
    }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / f"ENGEL_DISCORD_LOCAL_FIRST_PROOF_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}.json"
    path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({**receipt, "receipt_path": str(path)}, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
