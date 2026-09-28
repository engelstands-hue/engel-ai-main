#!/usr/bin/env python3
"""Evidence-backed operational status for Engel's twelve AI systems.

The Flutter page uses familiar AI terms, but a term is not automatically a
training method.  This module reports the real role of each system and proves
it from live local services, datasets, training/evaluation receipts, and
artifact hashes.  The probe is read-only and never starts training or promotes
weights.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any, Callable


ROOT = Path(os.environ.get("ENGEL_APP_ROOT", "/opt/engel"))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def _is_sha256(value: Any) -> bool:
    text = str(value or "").strip()
    return len(text) == 64 and all(char in "0123456789abcdefABCDEF" for char in text)


def _phase(receipt: dict[str, Any], name: str) -> dict[str, Any]:
    phases = receipt.get("phases") if isinstance(receipt.get("phases"), list) else []
    for item in phases:
        if isinstance(item, dict) and str(item.get("phase") or item.get("name") or "").casefold() == name.casefold():
            return item
    return {}


def _system(
    number: str,
    title: str,
    system_type: str,
    ready: bool,
    summary: str,
    evidence: list[str],
    receipt_path: str,
    *,
    changes_weights: bool = False,
    approval_required: bool = False,
) -> dict[str, Any]:
    return {
        "id": number,
        "title": title,
        "system_type": system_type,
        "ready": bool(ready),
        "state": "ready" if ready else "needs_attention",
        "summary": summary,
        "evidence": [str(item)[:500] for item in evidence if str(item).strip()],
        "receipt_path": receipt_path,
        "changes_weights": changes_weights,
        "approval_required": approval_required,
    }


def status_snapshot(
    root: Path | None = None,
    rag_status_provider: Callable[[], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    root = Path(root or ROOT)
    if rag_status_provider is None:
        from engel_rag_runtime import status_snapshot as rag_status_provider

    try:
        rag = rag_status_provider()
    except Exception as exc:
        rag = {"ok": False, "status": "RAG status failed", "errors": [str(exc)[:240]]}

    dataset_path = root / "reports" / "llm_training" / "ENGEL_TRAINING_DATASET_LATEST.json"
    dataset = _read_json(dataset_path)
    dataset_manifest_path = root / "llm_training" / "datasets" / "latest" / "dataset_manifest.json"
    dataset_manifest = _read_json(dataset_manifest_path)
    weekly_path = root / "reports" / "llm_training" / "ENGEL_WEEKLY_RETRAIN_LATEST.json"
    weekly = _read_json(weekly_path)
    train_phase = _phase(weekly, "train")
    complete_phase = _phase(weekly, "complete")
    lora_path = root / "reports" / "llm_training" / "ENGEL_CT246_LORA_PROOF_LATEST.json"
    lora = _read_json(lora_path)
    adapter_path = root / "runtime" / "engel_standalone_chat_llm" / "trained_lora_adapter_manifest.json"
    adapter = _read_json(adapter_path)
    preference_path = root / "reports" / "llm_training" / "ENGEL_PREFERENCE_DATASET_LATEST.json"
    preference = _read_json(preference_path)
    rag_receipt_path = root / "reports" / "rag_runtime" / "latest.json"
    rag_receipt = _read_json(rag_receipt_path)

    raw_counts = dataset.get("raw_counts") if isinstance(dataset.get("raw_counts"), dict) else {}
    train_rows = int(dataset.get("train") or 0)
    val_rows = int(dataset.get("val") or 0)
    teacher_rows = int(raw_counts.get("teacher") or 0)
    prompt_training_rows = int(raw_counts.get("prompt_training") or 0)
    local_model_id = str(rag.get("local_model_id") or "")
    rag_ready = rag.get("ok") is True and int(rag.get("production_route_count") or 0) == 10
    runtime_loaded = adapter.get("runtime_loaded_by_current_chat_endpoint") is True
    adapter_hash = (
        adapter.get("adapter_model_gguf", {}).get("sha256")
        if isinstance(adapter.get("adapter_model_gguf"), dict)
        else ""
    )
    base_hash = adapter.get("serving_base_gguf_model_sha256")
    tokenizer_hash = ""
    adapter_files = lora.get("adapter_files") if isinstance(lora.get("adapter_files"), list) else []
    for item in adapter_files:
        if isinstance(item, dict) and str(item.get("relative_path") or "") == "tokenizer.json":
            tokenizer_hash = str(item.get("sha256") or "")
            break
    weekly_complete = bool(complete_phase) and int(complete_phase.get("at_s") or 0) > 0
    preference_pairs = int(preference.get("matched_pair_count") or 0)
    val_before = train_phase.get("val_loss_before")
    val_after = train_phase.get("val_loss")
    try:
        val_improved = float(val_after) < float(val_before)
    except (TypeError, ValueError):
        val_improved = False
    system_prompt = str(dataset_manifest.get("system_prompt") or "")
    private_reasoning_guard = (
        "Do not reveal scratch work" in system_prompt
        and "Never output a Thinking Process section" in system_prompt
    )
    build_lane = root / "tools" / "engel_build_lane.py"
    workspace_scaffold = root / "tools" / "engel_workspace_scaffold.py"

    systems = [
        _system(
            "01", "LLM", "inference_runtime",
            bool(rag.get("local_model_ready") is True and local_model_id),
            "The selected local model completed a live generation readiness probe.",
            [f"Local model: {local_model_id}", "Provider call: false"],
            str(rag_receipt_path),
        ),
        _system(
            "02", "HALLUCINATION", "grounding_evaluation",
            rag_ready and rag_receipt.get("ok") is True,
            "Grounding is checked with retrieved source evidence and a redacted route receipt.",
            [f"RAG routes ready: {int(rag.get('production_route_count') or 0)}/10", f"Latest grounded result count: {int(rag_receipt.get('result_count') or 0)}"],
            str(rag_receipt_path),
        ),
        _system(
            "03", "TOKEN", "training_instrumentation",
            _is_sha256(tokenizer_hash) and train_rows > 0 and val_rows > 0,
            "A pinned tokenizer artifact and bounded train/validation datasets provide real token accounting inputs.",
            [f"Tokenizer SHA-256: {tokenizer_hash}", f"Dataset rows: {train_rows} train / {val_rows} validation"],
            str(lora_path),
        ),
        _system(
            "04", "TRAIN vs INFER", "model_lifecycle_boundary",
            train_rows > 0 and runtime_loaded,
            "Candidate dataset/training paths remain separate from the explicitly promoted inference artifact.",
            [f"Candidate rows: {train_rows + val_rows}", f"Promoted runtime loaded: {str(runtime_loaded).lower()}"],
            str(adapter_path),
        ),
        _system(
            "05", "FINE-TUNING", "weight_training",
            lora.get("ok") is True and lora.get("new_adapter_trained") is True and weekly_complete,
            "Approval-gated LoRA training produced evaluated candidate adapters; promotion remains separate.",
            [f"Latest weekly candidate: {complete_phase.get('adapter') or 'missing'}", f"Prompt-training rows admitted: {prompt_training_rows}", "Auto-deploy: false"],
            str(weekly_path), changes_weights=True, approval_required=True,
        ),
        _system(
            "06", "RLHF", "alignment_training_data",
            preference.get("ok") is True and preference_pairs > 0 and preference.get("weight_training_started") is False,
            "Owner-rejected replies are paired with successful answers to the exact same prompt for a DPO-compatible, approval-gated alignment dataset.",
            [f"Matched owner preference pairs: {preference_pairs}", f"Train/validation: {int(preference.get('train_pair_count') or 0)} / {int(preference.get('validation_pair_count') or 0)}", "Weight training started by status probe: false"],
            str(preference_path), changes_weights=True, approval_required=True,
        ),
        _system(
            "07", "DISTILLATION", "distillation_training",
            teacher_rows > 0 and weekly_complete,
            "Provenance-tagged teacher examples are admitted into the same held-out weekly training/evaluation cycle.",
            [f"Teacher examples in latest dataset: {teacher_rows}", f"Evaluated candidate: {complete_phase.get('adapter') or 'missing'}"],
            str(dataset_path), changes_weights=True, approval_required=True,
        ),
        _system(
            "08", "RAG", "retrieval_runtime",
            rag_ready,
            "Ten local retrieval strategies execute through the five verified ingest/embed/retrieve/rerank/generate moves.",
            [f"Indexed items: {int(rag.get('indexed_items') or 0)}", f"Production routes: {int(rag.get('production_route_count') or 0)}", "Index mutation by query: false"],
            str(rag_receipt_path),
        ),
        _system(
            "09", "CHAIN OF THOUGHT", "reasoning_safety_runtime",
            private_reasoning_guard and train_rows > 0,
            "Engel trains and serves a concise rationale boundary while keeping hidden scratch reasoning out of datasets and UI output.",
            ["Private scratch-work guard is present in the served training prompt", f"Guarded dataset rows: {train_rows + val_rows}"],
            str(dataset_manifest_path),
        ),
        _system(
            "10", "WEIGHTS", "artifact_governance",
            runtime_loaded and _is_sha256(adapter_hash) and _is_sha256(base_hash),
            "The live base and adapter are pinned by SHA-256 with promotion and rollback receipts.",
            [f"Base SHA-256: {base_hash}", f"Adapter SHA-256: {adapter_hash}", f"Runtime loaded: {str(runtime_loaded).lower()}"],
            str(adapter_path),
        ),
        _system(
            "11", "VALIDATION LOSS", "training_evaluation",
            weekly_complete and val_improved,
            "The newest weekly candidate records held-out loss before and after training and keeps the candidate unpromoted for review.",
            [f"Validation loss: {val_before} -> {val_after}", f"Delta: {train_phase.get('val_loss_delta')}", f"Validation rows: {val_rows}"],
            str(weekly_path),
        ),
        _system(
            "12", "CODING AGENT", "agent_runtime",
            build_lane.is_file() and workspace_scaffold.is_file(),
            "The coding agent has a real scoped build lane and workspace scaffold; tests and receipts remain completion authority.",
            [f"Build lane: {build_lane}", f"Workspace scaffold: {workspace_scaffold}", "Intent alone is not completion proof"],
            str(build_lane),
        ),
    ]
    ready_count = sum(1 for item in systems if item["ready"])
    return {
        "schema": "ENGEL_AI_SYSTEMS_STATUS_V1",
        "ok": ready_count == len(systems),
        "status": f"{ready_count} of {len(systems)} operational AI systems verified",
        "ready_count": ready_count,
        "system_count": len(systems),
        "weight_training_system_count": sum(1 for item in systems if item["changes_weights"]),
        "non_weight_system_count": sum(1 for item in systems if not item["changes_weights"]),
        "systems": systems,
        "boundaries": {
            "status_probe_is_read_only": True,
            "weight_training_started": False,
            "model_promoted": False,
            "provider_called": False,
            "trusted_memory_write": False,
            "hidden_reasoning_stored": False,
        },
        "updated_at_utc": _now(),
    }


def main() -> int:
    payload = status_snapshot()
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
