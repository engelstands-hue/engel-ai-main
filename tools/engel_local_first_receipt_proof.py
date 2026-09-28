#!/usr/bin/env python3
"""Portable local-first and verified-escalation receipt classifier."""

from __future__ import annotations

from typing import Any


REMOTE_PROVIDER_TERMS = (
    "openai",
    "anthropic",
    "chatgpt",
    "claude",
    "gemini",
    "grok",
    "xai",
    "codex",
)


def evaluate_local_first_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    provider = str(evidence.get("provider") or evidence.get("runtime_provider") or "").strip()
    selected = str(evidence.get("selected_provider") or evidence.get("selected_chat_provider") or "").strip()
    remote_name = (provider + " " + selected).casefold()
    remote_provider = any(term in remote_name for term in REMOTE_PROVIDER_TERMS)
    model = str(
        evidence.get("model")
        or evidence.get("quick_model_path")
        or evidence.get("quick_casual_model_path")
        or ""
    )
    model_backed = bool(model) and (model.casefold().endswith(".gguf") or "llama" in provider.casefold())
    status = str(evidence.get("status") or "").casefold()
    semantic_quality = evidence.get("local_semantic_quality")
    if not isinstance(semantic_quality, dict):
        semantic_quality = evidence.get("local_ct_lora_first_semantic_quality")
    semantic_quality_ok = not isinstance(semantic_quality, dict) or semantic_quality.get("ok") is True
    quality_verified = bool(
        evidence.get("quality_gate_degraded") is not True
        and "quality warning" not in status
        and "quality check failed" not in status
        and "style check failed" not in status
        and semantic_quality_ok
    )
    training_sample_eligible = evidence.get("training_sample_eligible") is True
    verified = bool(
        evidence.get("provider_api_enabled") is False
        and not remote_provider
        and model_backed
        and quality_verified
        and training_sample_eligible
    )
    provider_pipeline_used = evidence.get("provider_api_enabled") is True or remote_provider
    escalated_from = evidence.get("escalated_from")
    if escalated_from is None:
        escalated_from = evidence.get("_engel_escalated_from")
    verified_local_first_escalation = bool(
        provider_pipeline_used
        and evidence.get("local_ct_lora_first_attempted") is True
        and evidence.get("local_ct_lora_first_failed") is True
        and str(escalated_from or "") == "2"
        and evidence.get("provider_reply_quality_gate_passed") is True
        and isinstance(evidence.get("provider_final_semantic_quality"), dict)
        and evidence.get("provider_final_semantic_quality", {}).get("ok") is True
        and training_sample_eligible
    )
    return {
        "verified": verified,
        "local_only_verified": verified,
        "provider_pipeline_used": provider_pipeline_used,
        "verified_local_first_escalation": verified_local_first_escalation,
        "routing_policy_verified": verified or verified_local_first_escalation,
        "quality_verified": quality_verified,
        "quality_gate_degraded": evidence.get("quality_gate_degraded") is True,
        "training_sample_eligible": training_sample_eligible,
        "local_semantic_quality": semantic_quality,
        "provider_reply_quality_gate_passed": evidence.get("provider_reply_quality_gate_passed"),
        "provider_final_semantic_quality": evidence.get("provider_final_semantic_quality"),
        "escalated_from": escalated_from,
        "local_ct_lora_first_status": evidence.get("local_ct_lora_first_status"),
        "local_ct_lora_first_error": evidence.get("local_ct_lora_first_error"),
        "provider": provider,
        "selected_provider": selected,
        "provider_api_enabled": evidence.get("provider_api_enabled"),
        "network_enabled": evidence.get("network_enabled"),
        "model": model,
    }
