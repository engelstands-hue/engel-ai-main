#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
JSON_PATH = ROOT / "memory" / "ENGEL_APPROVED_LIBRARY_IMPORT_INTAKE_CONTRACT_V1.json"
MD_PATH = ROOT / "memory" / "ENGEL_APPROVED_LIBRARY_IMPORT_INTAKE_CONTRACT_V1.md"
REPORT_PATH = ROOT / "reports" / "codex_bridge" / "ENGEL_APPROVED_LIBRARY_IMPORT_INTAKE_CONTRACT_V1.md"

REQUIRED_STATUSES = [
    "CONTRACT_ONLY",
    "INTAKE_PLAN_ONLY",
    "HUMAN_REVIEW_REQUIRED",
    "NO_AUTOMATIC_IMPORT",
    "NOT_TRUSTED_MEMORY",
]

REQUIRED_TERMS = [
    "quarantine_imports",
    "approved_library",
    "rejected_or_hold",
    "source_notes",
    "human_review_receipt",
    "approved_for_reference_only",
]

REQUIRED_CATEGORIES = [
    "research_papers",
    "architecture_references",
    "engel_manuals",
    "offline_docs",
    "math",
    "coding_languages",
]

REQUIRED_REVIEW_STATES = [
    "candidate_material_recorded",
    "human_review_pending",
    "approved_for_reference",
    "rejected",
    "hold_for_later",
    "needs_source_clarification",
    "unsafe_or_untrusted_content",
]

REQUIRED_RECEIPT_FIELDS = [
    "material_id",
    "title",
    "category",
    "source_type",
    "original_location",
    "intended_reference_location",
    "reviewer",
    "review_date",
    "decision",
    "reason",
    "safety_notes",
    "not_trusted_memory_acknowledged",
    "no_auto_index_acknowledged",
    "no_execution_acknowledged",
]

ACTIVE_FORBIDDEN_PHRASES = [
    "automatic import enabled",
    "auto import enabled",
    "auto-index enabled",
    "recursive scan enabled",
    "copy files automatically",
    "move files automatically",
    "sync automatically",
    "trusted memory write enabled",
    "startup load enabled",
    "execute material enabled",
    "run material enabled",
    "download material enabled",
    "browser import enabled",
    "provider import enabled",
    "api import enabled",
    "train model enabled",
    "model fine tune enabled",
    "runtime load enabled",
]

SAFETY_FALSE_FLAGS = [
    "importing_enabled",
    "copying_enabled",
    "moving_enabled",
    "syncing_enabled",
    "indexing_enabled",
    "recursive_scans_enabled",
    "trusted_memory_writes_enabled",
    "learning_enabled",
    "model_training_enabled",
    "runtime_loading_enabled",
    "network_enabled",
    "browser_enabled",
    "provider_api_enabled",
    "package_manager_enabled",
    "execution_enabled",
    "background_workers_enabled",
    "route_mutation_enabled",
    "queue_mutation_enabled",
    "source_mutation_enabled",
    "startup_behavior_enabled",
]

REQUIRED_BOUNDARY_PHRASES = [
    "approved_library is research/reference only",
    "approved_library is not trusted memory",
    "quarantine_imports is untrusted",
    "Human review is required",
]


class CheckFailure(Exception):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def _read(path: Path) -> str:
    _require(path.exists() and path.is_file(), "required file missing: " + str(path))
    return path.read_text(encoding="utf-8", errors="replace")


def _load_json() -> dict:
    try:
        data = json.loads(_read(JSON_PATH))
    except json.JSONDecodeError as exc:
        raise CheckFailure("contract JSON is invalid: " + str(exc)) from exc
    _require(isinstance(data, dict), "contract JSON must be an object")
    return data


def _assert_terms(text: str, label: str) -> None:
    normalized = text.replace("\\\\", "\\")
    for term in REQUIRED_STATUSES + REQUIRED_TERMS + REQUIRED_CATEGORIES:
        _require(term in normalized, label + " missing required term: " + term)
    for phrase in REQUIRED_BOUNDARY_PHRASES:
        _require(phrase.lower() in normalized.lower(), label + " missing boundary phrase: " + phrase)


def _assert_no_active_forbidden(text: str, label: str) -> None:
    lowered = text.lower()
    for phrase in ACTIVE_FORBIDDEN_PHRASES:
        _require(phrase not in lowered, label + " contains active forbidden wording: " + phrase)


def _assert_json(data: dict) -> None:
    _require(data.get("schema") == "ENGEL_APPROVED_LIBRARY_IMPORT_INTAKE_CONTRACT_V1", "schema mismatch")
    status = str(data.get("status", ""))
    for required_status in REQUIRED_STATUSES:
        _require(required_status in status, "status missing: " + required_status)
    _require(data.get("contract_scope") == "documentation_manifest_verifier_only", "contract scope mismatch")
    _require(data.get("runtime_effect") == "NONE", "runtime effect must be NONE")
    _require(data.get("intake_areas") == REQUIRED_TERMS, "intake areas mismatch")
    _require(data.get("categories") == REQUIRED_CATEGORIES, "categories mismatch")
    _require(data.get("review_states") == REQUIRED_REVIEW_STATES, "review states mismatch")
    _require(data.get("approval_receipt_fields") == REQUIRED_RECEIPT_FIELDS, "approval receipt fields mismatch")

    boundaries = data.get("boundaries")
    _require(isinstance(boundaries, dict), "boundaries object missing")
    for phrase in [
        "External materials are manually obtained only.",
        "quarantine_imports is untrusted.",
        "approved_library is research/reference only.",
        "approved_library is not trusted memory.",
        "Import approval does not trigger learning.",
        "Import approval does not trigger indexing.",
        "Import approval does not trigger model training.",
        "Import approval does not trigger runtime loading.",
        "No automatic copy/move/sync behavior is enabled.",
        "No recursive scans are enabled.",
        "No network/browser/provider/API behavior is enabled.",
        "No package-manager behavior is enabled.",
        "No execution of imported materials is enabled.",
        "No trusted-memory writes are enabled.",
    ]:
        _require(phrase in boundaries.values(), "boundary missing: " + phrase)

    safety_flags = data.get("safety_flags")
    _require(isinstance(safety_flags, dict), "safety flags missing")
    for flag in SAFETY_FALSE_FLAGS:
        _require(safety_flags.get(flag) is False, "safety flag must be false: " + flag)

    _require("not trusted memory" in str(data.get("approved_library_meaning", "")).lower(), "approved library meaning missing trusted-memory boundary")
    _require("human review is required" in str(data.get("human_review_policy", "")).lower(), "human review policy missing")
    _require("cannot write trusted memory" in str(data.get("memory_policy", "")).lower(), "memory policy missing trusted-memory boundary")


def main() -> int:
    try:
        data = _load_json()
        md_text = _read(MD_PATH)
        report_text = _read(REPORT_PATH) if REPORT_PATH.exists() else ""
        json_text = json.dumps(data, indent=2, sort_keys=True)
        _assert_json(data)
        for text, label in [
            (json_text, "JSON"),
            (md_text, "Markdown"),
        ]:
            _assert_terms(text, label)
            _assert_no_active_forbidden(text, label)
        if report_text:
            _assert_terms(report_text, "report")
            _assert_no_active_forbidden(report_text, "report")
    except CheckFailure as exc:
        print("[FAIL]", exc)
        return 1

    print("PASS: Engel Approved Library Import Intake Contract V1 verifier")
    print("- contract JSON and Markdown exist and parse")
    print("- required statuses, intake areas, categories, review states, and receipt fields are documented")
    print("- approved_library remains research/reference only and not trusted memory")
    print("- no import automation, indexing, execution, training, runtime loading, or trusted-memory write is enabled")
    return 0


if __name__ == "__main__":
    sys.exit(main())
