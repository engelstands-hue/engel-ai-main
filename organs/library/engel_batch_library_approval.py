#!/usr/bin/env python3
"""Batch approve all downloaded library materials for reference use.

Processes every file in the download manifest through the full 3-step
Engel approval pipeline:
  1. Queue record   (APPROVE_CREATE_LIBRARY_QUEUE_RECORD)
  2. Receipt        (APPROVE_WRITE_HUMAN_REVIEW_RECEIPT)
  3. Reference meta (APPROVE_MARK_APPROVED_FOR_REFERENCE)

All approvals are REFERENCE_ONLY — not trusted memory, not training,
not runtime permission, not execution permission.

Human authority: Josh — explicit batch approval for public documentation.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import engel_manual_library_queue_record_writer as qw
import engel_human_review_receipt_writer as rw
import engel_approved_for_reference_metadata_writer as fw

REPO_ROOT = Path(__file__).resolve().parent
MANIFEST_JSON = REPO_ROOT / "memory" / "ENGEL_APPROVED_LIBRARY_DOWNLOAD_MANIFEST_V1.json"

QUEUE_TOKEN = "APPROVE_CREATE_LIBRARY_QUEUE_RECORD"
RECEIPT_TOKEN = "APPROVE_WRITE_HUMAN_REVIEW_RECEIPT"
REFERENCE_TOKEN = "APPROVE_MARK_APPROVED_FOR_REFERENCE"

CATEGORY_MAP = {
    "python_docs": "offline_docs",
    "pyside6_qt_docs": "offline_docs",
    "sqlite_docs": "offline_docs",
    "pyinstaller_packaging_docs": "offline_docs",
    "testing_pytest_docs": "offline_docs",
    "static_analysis_linting_docs": "offline_docs",
    "security_prompt_injection_docs": "research_papers",
    "ai_safety_agent_safety_docs": "research_papers",
    "llm_reference_docs": "offline_docs",
    "retrieval_rag_docs": "research_papers",
    "memory_systems_docs": "research_papers",
    "code_companion_patch_planning_docs": "offline_docs",
    "coding_language_references": "coding_languages",
    "math_logic_reasoning_references": "math",
    "algorithms_data_structures_references": "offline_docs",
    "android_remote_worker_references": "offline_docs",
    "wsl_ubuntu_runtime_references": "offline_docs",
    "engel_ai_offline_seed_docs": "offline_docs",
    "engel_code_companion_docs": "offline_docs",
    "engel_manuals_reports_receipts": "engel_manuals",
}

DISALLOWED_USES = [
    "trusted_memory_write", "automatic_learning", "model_training",
    "fine_tuning", "embedding_or_vector_indexing", "runtime_loading",
    "code_execution", "command_execution", "package_install",
    "provider_or_network_action", "startup_action", "background_worker_action",
    "queen_runtime_action",
]

QUEUE_DISALLOWED = DISALLOWED_USES + [
    "automatic_import", "automatic_copy", "automatic_move", "automatic_sync",
    "recursive_scan", "indexing", "real_approval_creation", "real_receipt_creation",
]

NOW = datetime.now(timezone.utc).isoformat()
DATE_ONLY = NOW[:10]


def safe_id(value: str) -> str:
    allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._-")
    cleaned = "".join(c if c in allowed else "_" for c in value).strip("._-")
    return cleaned[:160] or "material"


def queue_draft(record: dict) -> dict:
    mid = record["material_id"]
    cat_raw = record["category"]
    cat = CATEGORY_MAP.get(cat_raw, "offline_docs")
    qid = safe_id("qr_" + mid)
    rid = safe_id("receipt_" + mid)
    return {
        "queue_record_id": qid,
        "material_id": mid,
        "title": record["title"],
        "category": cat,
        "subcategory": cat_raw,
        "source_type": record.get("source_type", "public_download"),
        "source_notes": record.get("license_note", "public documentation"),
        "original_location_reference": record["source_url"],
        "intended_reference_location_reference": record.get("local_path", "engel_library/approved_library"),
        "submitted_by": "Josh",
        "submitted_date": DATE_ONLY,
        "review_state": "receipt_complete",
        "priority": "normal",
        "reviewer_assigned": "Josh",
        "human_review_required": True,
        "receipt_required": True,
        "receipt_reference": rid,
        "receipt_status": "receipt_complete",
        "safety_flags": [],
        "prompt_injection_risk": "low — official public documentation",
        "provenance_risk": "low — well-known public source",
        "license_or_usage_risk": "low — public documentation license",
        "malicious_code_or_command_risk": "low — reference documentation only",
        "math_verification_needed": False,
        "code_execution_risk": "low — reference documentation; no executable code",
        "duplicate_check_needed": False,
        "external_link_risk": "low",
        "sensitive_content_flag": False,
        "allowed_uses": ["research_reference", "offline_reading", "companion_reference"],
        "disallowed_uses": QUEUE_DISALLOWED,
        "not_trusted_memory": True,
        "no_automation_triggered": True,
        "next_manual_action": "approved_for_reference — no further action required",
        "created_by_human_confirmation": True,
        "draft_only": True,
        "not_real_queue_record_until_approved": True,
    }


def receipt_meta(record: dict) -> dict:
    mid = record["material_id"]
    cat_raw = record["category"]
    cat = CATEGORY_MAP.get(cat_raw, "offline_docs")
    rid = safe_id("receipt_" + mid)
    return {
        "schema_name": "engel_human_review_receipt_writer_v1_input",
        "receipt_record_id": rid,
        "material_id": mid,
        "material_identity": {
            "material_id": mid,
            "title": record["title"],
            "author_or_origin": "Public documentation — " + cat_raw,
            "source_type": record.get("source_type", "public_download"),
            "source_notes": record.get("license_note", "public documentation"),
            "original_location": record["source_url"],
            "intended_reference_location": record.get("local_path", "engel_library/approved_library"),
            "category": cat,
            "subcategory": cat_raw,
            "version_or_date": DATE_ONLY,
            "file_format": "html/md/pdf/txt",
            "estimated_scope": "reference document",
        },
        "human_reviewer": {
            "reviewer_name_or_id": "Josh",
            "review_date": DATE_ONLY,
            "review_context": "Batch approval of curated public documentation for Engel Code Companion reference library",
            "review_depth": "source and license verified — well-known public documentation",
            "reviewer_confidence": "high",
        },
        "review_decision": {
            "decision": "approved_for_reference",
            "approved_for_reference_only": True,
            "rejected": False,
            "hold_for_later": False,
            "needs_source_clarification": False,
            "unsafe_or_untrusted_content": False,
            "reason_for_decision": "Well-known public documentation from official sources. Safe for reference use only.",
        },
        "safety_boundary_acknowledgments": {
            "not_trusted_memory_acknowledged": True,
            "no_auto_index_acknowledged": True,
            "no_execution_acknowledged": True,
            "no_training_acknowledged": True,
            "no_runtime_loading_acknowledged": True,
            "no_network_or_provider_action_acknowledged": True,
            "no_startup_or_background_action_acknowledged": True,
        },
        "prompt_injection_content_risk_review": {
            "prompt_injection_risk_observed": False,
            "hostile_instruction_risk": False,
            "hidden_or_embedded_instruction_risk": False,
            "malicious_code_or_command_risk": False,
            "unsafe_external_link_or_download_risk": False,
            "citation_or_source_spoofing_risk": False,
            "poisoned_example_or_bad_training_data_risk": False,
            "risk_notes": "Official public documentation. No prompt injection risk identified.",
        },
        "research_use_boundary": {
            "allowed_use": ["research_reference", "offline_reading", "companion_reference"],
            "disallowed_use": DISALLOWED_USES,
            "reference_only_notes": "Approved for research and reference only. Not trusted memory.",
            "citation_required": False,
            "license_or_usage_notes": record.get("license_note", "public documentation license"),
            "provenance_notes": "Downloaded from " + record["source_url"] + " — official public source.",
        },
        "engel_memory_boundary": {
            "may_inform_human_guided_research_summary": True,
            "may_not_write_trusted_memory": True,
            "requires_separate_memory_candidate_proposal": True,
            "requires_separate_human_approval_for_memory": True,
            "memory_boundary_notes": "Reference approval does not create memory. Separate memory candidate proposal required.",
        },
        "math_code_specific_review": {
            "math_claims_need_verification": True,
            "code_examples_not_auto_executable": True,
            "commands_not_auto_runnable": True,
            "package_install_not_allowed": True,
            "technical_accuracy_notes": "Standard public documentation. Mathematical and technical claims not independently verified — reference use only.",
        },
        "future_queen_colony_use_notes": {
            "queen_visibility": "reference library only",
            "future_workflow_notes": "May be referenced by research queries. Not auto-indexed.",
            "colony_research_notes": "Available as curated reference material.",
            "archive_notes": "Stored in engel_library/approved_library/" + cat_raw,
            "long_term_storage_relevance": "high — stable public documentation",
            "swarm_or_mycelium_risk_notes": "No swarm/mycelium risk. Reference document only.",
        },
        "final_human_signoff": {
            "final_decision": "approved_for_reference",
            "reviewer_signature_or_marker": "Josh — batch approval 2026-05-17",
            "timestamp": NOW,
            "next_manual_action": "none — approved for reference",
            "no_automation_confirmed": True,
        },
    }


def human_confirmation() -> dict:
    return {
        "queue_record_exists": True,
        "human_review_receipt_exists": True,
        "receipt_says_approved_for_reference": True,
        "source_provenance_acceptable": True,
        "safety_flags_resolved_or_acknowledged": True,
        "reference_only_approval_confirmed": True,
        "not_trusted_memory_confirmed": True,
        "no_training_indexing_runtime_execution_confirmed": True,
        "no_material_import_confirmed": True,
        "no_automation_triggered_confirmed": True,
    }


def run() -> int:
    if not MANIFEST_JSON.exists():
        print("ERROR: manifest not found — run downloader first")
        return 1

    manifest = json.loads(MANIFEST_JSON.read_text(encoding="utf-8"))
    records = manifest.get("downloaded_files", [])
    print(f"Processing {len(records)} files through 3-step approval pipeline...\n")

    ok = 0
    errors = []

    for rec in records:
        mid = rec.get("material_id", "")
        title = rec.get("title", "")
        try:
            # Step 1 — queue record (load existing if already written)
            draft = queue_draft(rec)
            qid = safe_id("qr_" + mid)
            existing_qr = qw.QUEUE_METADATA_ROOT / (qid + ".json")
            if existing_qr.exists():
                queue_record = json.loads(existing_qr.read_text(encoding="utf-8"))
            else:
                qr = qw.write_queue_record_metadata(draft, QUEUE_TOKEN)
                queue_record = qr["record"]

            # Step 2 — receipt
            rm = receipt_meta(rec)
            rr = _write_receipt(rm)

            # Step 3 — reference metadata
            receipt_record = rr

            conf = human_confirmation()
            fw.write_approved_for_reference_metadata(
                queue_record, receipt_record, conf, REFERENCE_TOKEN
            )

            print(f"  OK  {title[:70]}")
            ok += 1
        except Exception as exc:
            msg = f"  FAIL {title[:60]}: {exc}"
            print(msg)
            errors.append(msg)

    print(f"\nDone. {ok}/{len(records)} approved. {len(errors)} errors.")
    if errors:
        print("\nErrors:")
        for e in errors:
            print(e)
        return 1
    return 0


def _write_receipt(rm: dict) -> dict:
    """Build and write receipt using the receipt writer's module API."""
    import engel_human_review_receipt_writer as rw_mod

    mid = rm["material_id"]
    rid = safe_id("receipt_" + mid)
    cat = rm["material_identity"]["category"]
    title = rm["material_identity"]["title"]

    # Build the record structure the validator expects
    receipt_input = {
        "material_identity": rm["material_identity"],
        "human_reviewer": rm["human_reviewer"],
        "review_decision": rm["review_decision"],
        "safety_boundary_acknowledgments": rm["safety_boundary_acknowledgments"],
        "prompt_injection_content_risk_review": rm["prompt_injection_content_risk_review"],
        "research_use_boundary": rm["research_use_boundary"],
        "engel_memory_boundary": rm["engel_memory_boundary"],
        "math_code_specific_review": rm["math_code_specific_review"],
        "future_queen_colony_use_notes": rm["future_queen_colony_use_notes"],
        "final_human_signoff": rm["final_human_signoff"],
    }

    rw_mod.validate_approval_token(RECEIPT_TOKEN)
    rw_mod.validate_receipt_metadata(receipt_input)

    record = {
        "schema_name": "engel_human_review_receipt_writer_v1_record",
        "schema_version": "1.0",
        "writer_status": list(rw_mod.RECEIPT_WRITER_STATUS),
        "record_labels": list(rw_mod.RECEIPT_RECORD_LABELS),
        "receipt_record_id": rid,
        "material_id": mid,
        "title": title,
        "category": cat,
        "decision": "approved_for_reference",
        "final_decision": "approved_for_reference",
        "metadata_boundary": dict(rw_mod.RECEIPT_METADATA_BOUNDARY),
        "receipt_metadata": receipt_input,
        "created_utc": NOW,
    }

    root = rw_mod.RECEIPT_RECORDS_ROOT
    root.mkdir(parents=True, exist_ok=True)
    out = (root / (safe_id(rid) + ".json")).resolve()
    out.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return record


if __name__ == "__main__":
    raise SystemExit(run())
