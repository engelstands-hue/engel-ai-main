from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
GUI_HOST = PROJECT_ROOT / "engel_companion.py"
MAX_READ_CHARS = 80_000
MAX_HASH_BYTES = 64 * 1024 * 1024
MAX_SHALLOW_COUNT = 25

MODEL_PLAN = PROJECT_ROOT / "memory" / "ENGEL_MODEL_LIBRARY_PLAN_V1.json"
NON_MODEL_PLAN = PROJECT_ROOT / "memory" / "ENGEL_NON_MODEL_LIBRARY_PLAN_V1.json"
OFFLINE_RUNTIME_CONTRACT = PROJECT_ROOT / "memory" / "ENGEL_OFFLINE_MODEL_RUNTIME_CONTRACT_V1.json"
OFFLINE_SEED_CONTRACT = PROJECT_ROOT / "memory" / "OFFLINE_SEED_LLM_CONTRACT_V1.json"
MODEL_INTAKE_MANIFEST = PROJECT_ROOT / "reports" / "ai_model_intake" / "manifests" / "ENGEL_AI_MODEL_INTAKE_MANIFEST_V1.json"
MODEL_REVIEW_APPROVAL_MANIFEST = PROJECT_ROOT / "reports" / "ai_model_review_approvals" / "manifests" / "engel_ai_model_review_approval_manifest.json"
RUNTIME_DRY_RUN_MANIFEST = PROJECT_ROOT / "reports" / "ai_runtime_dry_runs" / "configs" / "engel_ai_runtime_dry_run_manifest.json"
RUNTIME_PATH_CONFIG_MANIFEST = PROJECT_ROOT / "reports" / "ai_runtime_path_config" / "manifests" / "engel_ai_local_runtime_path_config_manifest.json"
NO_GENERATION_LOAD_CHECK_RECEIPTS = PROJECT_ROOT / "reports" / "ai_no_generation_load_checks" / "receipts"
LLAMA_CPP_COMPATIBILITY_RECEIPTS = PROJECT_ROOT / "reports" / "ai_llama_cpp_compatibility" / "receipts"
LLAMA_CPP_COMPATIBILITY_MATRICES = PROJECT_ROOT / "reports" / "ai_llama_cpp_compatibility" / "matrices"
LLAMA_CPP_RUNTIME_SWAP_MANIFESTS = PROJECT_ROOT / "reports" / "ai_llama_cpp_runtime_swap_plan" / "manifests"
LLAMA_CPP_RUNTIME_SWAP_RECEIPTS = PROJECT_ROOT / "reports" / "ai_llama_cpp_runtime_swap_plan" / "receipts"
LLAMA_CPP_RUNTIME_CANDIDATE_VALIDATION_RECEIPTS = PROJECT_ROOT / "reports" / "ai_llama_cpp_runtime_candidate_validation" / "receipts"
RUNTIME_CANDIDATE_FAILURE_DIAGNOSIS_RECEIPTS = PROJECT_ROOT / "reports" / "ai_runtime_candidate_failure_diagnosis" / "receipts"
RUNTIME_CANDIDATE_VALIDATION_REPLAY_RECEIPTS = PROJECT_ROOT / "reports" / "ai_runtime_candidate_validation_replay" / "receipts"
RUNTIME_CANDIDATE_ALT_COMMAND_STYLE_RECEIPTS = PROJECT_ROOT / "reports" / "ai_runtime_candidate_alt_command_style" / "receipts"
LLAMA_CPP_RUNTIME_SWAP_APPROVAL_RECEIPTS = PROJECT_ROOT / "reports" / "ai_llama_cpp_runtime_swap_approval" / "receipts"
FIRST_LOCAL_RESPONSE_SMOKE_RECEIPTS = PROJECT_ROOT / "reports" / "ai_first_local_response_smoke" / "receipts"
FIRST_LOCAL_RESPONSE_SMOKE_EXIT_FIX_RECEIPTS = PROJECT_ROOT / "reports" / "ai_first_local_response_smoke_exit_fix" / "receipts"
FIRST_RESPONSE_OUTPUT_FILTER_TUNING_RECEIPTS = PROJECT_ROOT / "reports" / "ai_first_response_output_filter_tuning" / "receipts"
BOUNDED_LOCAL_CHAT_SMOKE_RECEIPTS = PROJECT_ROOT / "reports" / "ai_bounded_local_chat_smoke" / "receipts"
LOCAL_CHAT_PROMPT_DRAFT_RECEIPTS = PROJECT_ROOT / "reports" / "ai_local_chat_prompt_draft" / "receipts"
LOCAL_CHAT_SESSION_DRAFT_RECEIPTS = PROJECT_ROOT / "reports" / "ai_local_chat_session_draft" / "receipts"
LOCAL_CHAT_SESSION_REVIEW_RECEIPTS = PROJECT_ROOT / "reports" / "ai_local_chat_session_review" / "receipts"
LOCAL_CHAT_SESSION_REVIEW_CANDIDATES = PROJECT_ROOT / "reports" / "ai_local_chat_session_review" / "memory_candidate_drafts"
LOCAL_CHAT_MEMORY_CANDIDATE_REVIEW_WRITE_RECEIPTS = PROJECT_ROOT / "reports" / "ai_local_chat_session_memory_candidate_review_and_approved_write" / "receipts"
LOCAL_CHAT_APPROVED_MEMORY_RECORDS = PROJECT_ROOT / "reports" / "ai_local_chat_session_memory_candidate_review_and_approved_write" / "approved_memory_records"
LOCAL_CHAT_APPROVED_MEMORY_READBACK_RECEIPTS = PROJECT_ROOT / "reports" / "ai_local_approved_memory_readback" / "receipts"
LOCAL_CHAT_APPROVED_MEMORY_CONTEXT_PREVIEW_RECEIPTS = PROJECT_ROOT / "reports" / "ai_local_approved_memory_context_preview" / "receipts"
LOCAL_OPEN_CHAT_SUPERVISED_RUN_RECEIPTS = PROJECT_ROOT / "reports" / "ai_local_open_chat_supervised_run" / "receipts"
PERSISTENT_CHAT_SUPERVISED_RUNTIME_PLAN_RECEIPTS = PROJECT_ROOT / "reports" / "ai_persistent_chat_supervised_runtime_plan" / "receipts"
PERSISTENT_CHAT_SUPERVISED_RUNTIME_PLAN_JSON = PROJECT_ROOT / "memory" / "ENGEL_AI_PERSISTENT_CHAT_SUPERVISED_RUNTIME_PLAN_V1.json"
LOCAL_CHAT_PANEL_ENABLE_REPORT = PROJECT_ROOT / "reports" / "codex_bridge" / "ENGEL_AI_LOCAL_CHAT_PANEL_ENABLE_BOUNDED_RUN_V1.md"
LOCAL_CHAT_PROMPT_DRAFT_REPORT = PROJECT_ROOT / "reports" / "codex_bridge" / "ENGEL_AI_LOCAL_CHAT_PANEL_HUMAN_PROMPT_DRAFT_V1.md"
LOCAL_CHAT_SESSION_DRAFT_REPORT = PROJECT_ROOT / "reports" / "codex_bridge" / "ENGEL_AI_LOCAL_CHAT_PANEL_SESSION_DRAFT_V1.md"
LOCAL_CHAT_SESSION_REVIEW_REPORT = PROJECT_ROOT / "reports" / "codex_bridge" / "ENGEL_AI_LOCAL_CHAT_PANEL_SESSION_REVIEW_V1.md"
LOCAL_CHAT_MEMORY_CANDIDATE_REVIEW_WRITE_REPORT = PROJECT_ROOT / "reports" / "codex_bridge" / "ENGEL_AI_LOCAL_CHAT_SESSION_MEMORY_CANDIDATE_REVIEW_AND_APPROVED_WRITE_V1.md"
LOCAL_CHAT_APPROVED_MEMORY_READBACK_REPORT = PROJECT_ROOT / "reports" / "codex_bridge" / "ENGEL_AI_LOCAL_APPROVED_MEMORY_READBACK_V1.md"
LOCAL_CHAT_APPROVED_MEMORY_CONTEXT_PREVIEW_REPORT = PROJECT_ROOT / "reports" / "codex_bridge" / "ENGEL_AI_LOCAL_APPROVED_MEMORY_CONTEXT_PREVIEW_V1.md"
LOCAL_OPEN_CHAT_SUPERVISED_RUN_REPORT = PROJECT_ROOT / "reports" / "codex_bridge" / "ENGEL_AI_LOCAL_OPEN_CHAT_SUPERVISED_RUN_V1.md"
PERSISTENT_CHAT_SUPERVISED_RUNTIME_PLAN_REPORT = PROJECT_ROOT / "reports" / "codex_bridge" / "ENGEL_AI_PERSISTENT_CHAT_SUPERVISED_RUNTIME_PLAN_V1.md"
# Legacy marker kept for the bounded-run panel verifier while prompt draft becomes the next safe action.
LOCAL_CHAT_PANEL_BOUNDED_RUN_READY_MARKER = "ENGEL_AI_LOCAL_CHAT_PANEL_BOUNDED_RUN_READY"
COMMANDS = PROJECT_ROOT / "memory" / "ENGEL_COMMANDS.md"
CODEX_VERIFY = PROJECT_ROOT / "scripts" / "codex_verify.ps1"
APPROVED_ENGEL_ROOTS = [
    ("/opt/engel", "ct246_active_runtime_memory_and_models"),
    ("/opt/engel/models-active", "ct246_active_model_store"),
    ("/mnt/engel-hdd-vault", "dell_poweredge_hdd_archive_when_mounted"),
]
PREFERRED_RUNTIME_ROOT = "/opt/engel/runtime"
ALTERNATE_RUNTIME_ROOT = "D:\\b.WorkSpace\\Engel App\\runtime"
EXPANSION_LIBRARY_ROOT = "/mnt/engel-hdd-vault/libraries"

EXPECTED_MODEL_TIERS = [
    ("Tiny Seed Mode", "Qwen2.5-0.5B-Instruct GGUF"),
    ("Daily Local Mode", "Qwen2.5-3B-Instruct GGUF"),
    ("Research Worker Mode", "Qwen2.5-7B-Instruct GGUF"),
    ("Alternative Research Worker", "Mistral-7B-Instruct v0.3 GGUF"),
]

KNOWN_DATA_SOURCES = [
    "memory\\ENGEL_MODEL_LIBRARY_PLAN_V1.json",
    "memory\\ENGEL_MODEL_LIBRARY_PLAN_V1.md",
    "memory\\ENGEL_NON_MODEL_LIBRARY_PLAN_V1.json",
    "memory\\ENGEL_NON_MODEL_LIBRARY_PLAN_V1.md",
    "memory\\ENGEL_COMMANDS.md",
    "memory\\ENGEL_SYSTEM_INTEGRATION_STATUS_V1.md",
    "memory\\ENGEL_CORE_CONTINUITY_MAP_V1.json",
    "memory\\ENGEL_CORE_CONTINUITY_MAP_V1.md",
    "memory\\ENGEL_OFFLINE_MODEL_RUNTIME_CONTRACT_V1.json",
    "memory\\OFFLINE_SEED_LLM_CONTRACT_V1.json",
    "memory\\ENGEL_MEMORY_ROOTS_STORAGE_LAYOUT_V1.json",
    "memory\\ENGEL_MEMORY_ROOTS_STORAGE_LAYOUT_V1.md",
    "reports\\ai_runtime_path_config\\manifests\\engel_ai_local_runtime_path_config_manifest.json",
    "reports\\codex_bridge\\ENGEL_MEMORY_ROOTS_STORAGE_LAYOUT_V1.md",
    "reports\\codex_bridge\\ENGEL_AI_NO_GENERATION_LOAD_CHECK_V1.md",
    "reports\\codex_bridge\\ENGEL_AI_NO_GENERATION_LOAD_CHECK_V2.md",
    "reports\\codex_bridge\\ENGEL_AI_NO_GENERATION_LOAD_CHECK_V3.md",
    "reports\\codex_bridge\\ENGEL_AI_NO_GENERATION_LOAD_CHECK_V4.md",
    "reports\\ai_no_generation_load_checks\\receipts",
    "reports\\codex_bridge\\ENGEL_AI_LLAMA_CPP_COMPATIBILITY_MATRIX_V1.md",
    "reports\\ai_llama_cpp_compatibility\\matrices",
    "reports\\ai_llama_cpp_compatibility\\receipts",
    "reports\\codex_bridge\\ENGEL_AI_LLAMA_CPP_RUNTIME_SWAP_PLAN_V1.md",
    "reports\\ai_llama_cpp_runtime_swap_plan\\manifests",
    "reports\\ai_llama_cpp_runtime_swap_plan\\receipts",
    "reports\\codex_bridge\\ENGEL_AI_LLAMA_CPP_RUNTIME_CANDIDATE_VALIDATION_V1.md",
    "reports\\ai_llama_cpp_runtime_candidate_validation\\receipts",
    "reports\\codex_bridge\\ENGEL_AI_RUNTIME_CANDIDATE_FAILURE_DIAGNOSIS_V1.md",
    "reports\\ai_runtime_candidate_failure_diagnosis\\receipts",
    "reports\\codex_bridge\\ENGEL_AI_RUNTIME_CANDIDATE_VALIDATION_REPLAY_V1.md",
    "reports\\ai_runtime_candidate_validation_replay\\receipts",
    "reports\\codex_bridge\\ENGEL_AI_RUNTIME_CANDIDATE_ALT_COMMAND_STYLE_V1.md",
    "reports\\ai_runtime_candidate_alt_command_style\\receipts",
    "reports\\codex_bridge\\ENGEL_AI_LLAMA_CPP_RUNTIME_SWAP_APPROVAL_V1.md",
    "reports\\ai_llama_cpp_runtime_swap_approval\\receipts",
    "reports\\codex_bridge\\ENGEL_AI_FIRST_LOCAL_RESPONSE_SMOKE_V1.md",
    "reports\\ai_first_local_response_smoke\\receipts",
    "reports\\codex_bridge\\ENGEL_AI_FIRST_LOCAL_RESPONSE_SMOKE_EXIT_FIX_V1.md",
    "reports\\ai_first_local_response_smoke_exit_fix\\receipts",
    "reports\\codex_bridge\\ENGEL_AI_FIRST_RESPONSE_OUTPUT_FILTER_TUNING_V1.md",
    "reports\\ai_first_response_output_filter_tuning\\receipts",
    "reports\\codex_bridge\\ENGEL_AI_BOUNDED_LOCAL_CHAT_ENABLE_V1.md",
    "reports\\ai_bounded_local_chat_smoke\\receipts",
    "reports\\codex_bridge\\ENGEL_AI_LOCAL_CHAT_PANEL_ENABLE_BOUNDED_RUN_V1.md",
    "reports\\codex_bridge\\ENGEL_AI_LOCAL_CHAT_PANEL_HUMAN_PROMPT_DRAFT_V1.md",
    "reports\\ai_local_chat_prompt_draft\\receipts",
    "reports\\codex_bridge\\ENGEL_AI_LOCAL_CHAT_PANEL_SESSION_DRAFT_V1.md",
    "reports\\ai_local_chat_session_draft\\receipts",
    "reports\\codex_bridge\\ENGEL_AI_LOCAL_CHAT_PANEL_SESSION_REVIEW_V1.md",
    "reports\\ai_local_chat_session_review\\receipts",
    "reports\\ai_local_chat_session_review\\memory_candidate_drafts",
    "reports\\codex_bridge\\ENGEL_AI_LOCAL_CHAT_SESSION_MEMORY_CANDIDATE_REVIEW_AND_APPROVED_WRITE_V1.md",
    "reports\\ai_local_chat_session_memory_candidate_review_and_approved_write\\receipts",
    "reports\\ai_local_chat_session_memory_candidate_review_and_approved_write\\approved_memory_records",
    "reports\\codex_bridge\\ENGEL_AI_LOCAL_APPROVED_MEMORY_READBACK_V1.md",
    "reports\\ai_local_approved_memory_readback\\receipts",
    "reports\\codex_bridge\\ENGEL_AI_LOCAL_APPROVED_MEMORY_CONTEXT_PREVIEW_V1.md",
    "reports\\ai_local_approved_memory_context_preview\\receipts",
    "reports\\codex_bridge\\ENGEL_AI_LOCAL_OPEN_CHAT_SUPERVISED_RUN_V1.md",
    "reports\\ai_local_open_chat_supervised_run\\receipts",
    "memory\\ENGEL_AI_PERSISTENT_CHAT_SUPERVISED_RUNTIME_PLAN_V1.json",
    "memory\\ENGEL_AI_PERSISTENT_CHAT_SUPERVISED_RUNTIME_PLAN_V1.md",
    "reports\\codex_bridge\\ENGEL_AI_PERSISTENT_CHAT_SUPERVISED_RUNTIME_PLAN_V1.md",
    "reports\\ai_persistent_chat_supervised_runtime_plan\\receipts",
    "reports\\codex_bridge\\OFFLINE_SEED_LLM_CONTRACT_AND_SCAFFOLD.md",
    "reports\\codex_bridge\\ENGEL_OFFLINE_MODEL_RUNTIME_CONTRACT_V1.md",
    "reports\\codex_bridge\\ENGEL_OUTSIDE_AI_BOUNDARY_RULE_V1.md",
    "reports\\codex_bridge\\ENGEL_REMOTE_WORKER_PHASE_12_ENGEL_CONTROLLED_PHONE_LINK_MANAGER.md",
    "reports\\codex_bridge\\ENGEL_CODE_COMPANION_PATCH_CLASS_ALLOWLIST_V1.md",
    "reports\\codex_bridge\\ENGEL_CODE_COMPANION_PROTECTED_APPLY_PASSWORD_GATE_INTEGRATION_SMOKE.md",
    "reports\\codex_bridge\\ENGEL_WHOLE_SYSTEM_INCOMPLETE_ITEMS_AUDIT.md",
    "scripts\\codex_verify.ps1",
]

CODE_COMPANION_PHASES = [
    ("Phase 1 Fix Candidate Intake", "engel_code_companion_fix_candidate_intake.py", "reports\\codex_bridge\\ENGEL_CODE_COMPANION_FIX_CANDIDATE_INTAKE_V1.md", "tools\\verify_engel_code_companion_fix_candidate_intake.py"),
    ("Phase 2 Patch Plan Preview", "engel_code_companion_patch_plan_preview.py", "reports\\codex_bridge\\ENGEL_CODE_COMPANION_PATCH_PLAN_PREVIEW_V1.md", "tools\\verify_engel_code_companion_patch_plan_preview.py"),
    ("Phase 3 Patch Bundle Draft", "engel_code_companion_patch_bundle_draft.py", "reports\\codex_bridge\\ENGEL_CODE_COMPANION_PATCH_BUNDLE_DRAFT_V1.md", "tools\\verify_engel_code_companion_patch_bundle_draft.py"),
    ("Phase 4 Protected Application Gate", "engel_code_companion_patch_application_gate.py", "reports\\codex_bridge\\ENGEL_CODE_COMPANION_PROTECTED_PATCH_APPLICATION_GATE_V1.md", "tools\\verify_engel_code_companion_patch_application_gate.py"),
    ("Phase 5 Apply Dry-Run Simulator", "engel_code_companion_patch_apply_dry_run.py", "reports\\codex_bridge\\ENGEL_CODE_COMPANION_PATCH_APPLY_DRY_RUN_V1.md", "tools\\verify_engel_code_companion_patch_apply_dry_run.py"),
    ("Phase 6 Approval Receipt", "engel_code_companion_patch_apply_approval_receipt.py", "reports\\codex_bridge\\ENGEL_CODE_COMPANION_PATCH_APPLY_APPROVAL_RECEIPT_V1.md", "tools\\verify_engel_code_companion_patch_apply_approval_receipt.py"),
    ("Phase 7 Protected Patch Apply MVP", "engel_code_companion_protected_patch_apply.py", "reports\\codex_bridge\\ENGEL_CODE_COMPANION_PROTECTED_PATCH_APPLY_MVP_V1.md", "tools\\verify_engel_code_companion_protected_patch_apply.py"),
    ("Phase 8 Tiny Documentation Patch Smoke", "", "reports\\codex_bridge\\ENGEL_CODE_COMPANION_TINY_DOCUMENTATION_PATCH_APPLY_SMOKE.md", "tools\\verify_engel_code_companion_tiny_doc_patch_smoke.py"),
    ("Phase 9 Protected Rollback MVP", "engel_code_companion_protected_rollback.py", "reports\\codex_bridge\\ENGEL_CODE_COMPANION_PROTECTED_ROLLBACK_MVP_V1.md", "tools\\verify_engel_code_companion_protected_rollback.py"),
    ("Phase 10 Review Surface", "tools\\engel_code_companion_review_surface.py", "reports\\codex_bridge\\ENGEL_CODE_COMPANION_PATCH_APPLY_UI_REVIEW_SURFACE_V1.md", "tools\\verify_engel_code_companion_review_surface.py"),
    ("Phase 11 Patch Class Allowlist", "engel_code_companion_patch_class_allowlist.py", "reports\\codex_bridge\\ENGEL_CODE_COMPANION_PATCH_CLASS_ALLOWLIST_V1.md", "tools\\verify_engel_code_companion_patch_class_allowlist.py"),
    ("Phase 12 Password Gate Integration Smoke", "engel_code_companion_password_gate_integration.py", "reports\\codex_bridge\\ENGEL_CODE_COMPANION_PROTECTED_APPLY_PASSWORD_GATE_INTEGRATION_SMOKE.md", "tools\\verify_engel_code_companion_password_gate_integration.py"),
]


def rel(path: Path) -> str:
    try:
        return str(path.resolve(strict=False).relative_to(PROJECT_ROOT.resolve(strict=False))).replace("/", "\\")
    except ValueError:
        return str(path)


def path_from_repo(path_text: str) -> Path:
    return PROJECT_ROOT / path_text


def exists(path_text: str) -> bool:
    return path_from_repo(path_text).exists()


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace")[:MAX_READ_CHARS])
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def read_bounded(path_text: str) -> str:
    path = path_from_repo(path_text)
    if not path.exists() or not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:MAX_READ_CHARS]
    except OSError:
        return ""


def gui_marker_state() -> dict[str, bool]:
    source = read_bounded("engel_companion.py")

    def has_all(*needles: str) -> bool:
        return bool(source) and all(needle in source for needle in needles)

    return {
        "local_ai_bounded_run_section_present": has_all("Bounded Run", "run_local_ai_bounded_smoke_from_panel"),
        "local_ai_human_prompt_draft_section_present": has_all("Human Prompt Draft", "APPROVE_LOCAL_CHAT_PROMPT_DRAFT"),
        "local_ai_session_draft_section_present": has_all("Session Draft", "APPROVE_LOCAL_CHAT_SESSION_DRAFT_TURN"),
        "local_ai_supervised_open_chat_section_present": has_all("Supervised Open Chat", "send_supervised_message(prompt)"),
        "local_ai_persistent_chat_plan_section_present": has_all("Persistent Chat Runtime Plan"),
    }


def shallow_count(path_text: str, suffixes: set[str] | None = None) -> dict[str, Any]:
    path = Path(path_text)
    result = {"path": path_text, "exists": path.exists(), "is_dir": path.is_dir(), "bounded_count": 0, "sample_names": []}
    if not path.exists() or not path.is_dir():
        return result
    names: list[str] = []
    try:
        for child in path.iterdir():
            if suffixes is not None and child.suffix.lower() not in suffixes:
                continue
            names.append(child.name)
            if len(names) >= MAX_SHALLOW_COUNT:
                break
    except OSError as exc:
        result["error"] = str(exc)
    result["bounded_count"] = len(names)
    result["sample_names"] = sorted(names)
    return result


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def model_entries() -> list[dict[str, Any]]:
    plan = read_json(MODEL_PLAN)
    models = plan.get("models")
    if not isinstance(models, list):
        return []
    return [item for item in models if isinstance(item, dict)]


def model_expected_path(model: dict[str, Any]) -> str:
    folder = str(model.get("expected_local_folder", "") or "")
    expected_files = model.get("expected_files")
    if isinstance(expected_files, list) and expected_files and isinstance(expected_files[0], str):
        return str(Path(folder) / Path(expected_files[0]).name)
    return "unknown"


def model_intake_entries_by_source() -> dict[str, dict[str, Any]]:
    data = read_json(MODEL_INTAKE_MANIFEST)
    entries = data.get("entries")
    if not isinstance(entries, list):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if isinstance(entry, dict) and isinstance(entry.get("source_path"), str):
            result[str(Path(entry["source_path"]).resolve(strict=False))] = entry
    return result


def model_review_approval_entries_by_source() -> dict[str, dict[str, Any]]:
    data = read_json(MODEL_REVIEW_APPROVAL_MANIFEST)
    entries = data.get("entries")
    if not isinstance(entries, list):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if isinstance(entry, dict) and isinstance(entry.get("model_file_path"), str):
            result[str(Path(entry["model_file_path"]).resolve(strict=False))] = entry
    return result


def runtime_dry_run_entries_by_model_key() -> dict[str, dict[str, Any]]:
    data = read_json(RUNTIME_DRY_RUN_MANIFEST)
    entries = data.get("entries")
    if not isinstance(entries, list):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if isinstance(entry, dict) and isinstance(entry.get("model_key"), str):
            result[entry["model_key"]] = entry
    return result


def no_generation_load_check_entries() -> list[dict[str, Any]]:
    if not NO_GENERATION_LOAD_CHECK_RECEIPTS.exists():
        return []
    rows: list[dict[str, Any]] = []
    for receipt in sorted(NO_GENERATION_LOAD_CHECK_RECEIPTS.glob("*.json")):
        data = read_json(receipt)
        if data.get("no_generation_load_check_version") in {"1", "2", "3", "4"}:
            data["receipt_path"] = rel(receipt)
            rows.append(data)
    return rows


def latest_no_generation_load_check() -> dict[str, Any] | None:
    rows = no_generation_load_check_entries()
    return rows[-1] if rows else None


def llama_cpp_compatibility_probe_entries() -> list[dict[str, Any]]:
    if not LLAMA_CPP_COMPATIBILITY_RECEIPTS.exists():
        return []
    rows: list[dict[str, Any]] = []
    for receipt in sorted(LLAMA_CPP_COMPATIBILITY_RECEIPTS.glob("*.json")):
        data = read_json(receipt)
        if data.get("compatibility_probe_version") == "1":
            data["receipt_path"] = rel(receipt)
            rows.append(data)
    return rows


def latest_llama_cpp_compatibility_probe() -> dict[str, Any] | None:
    rows = llama_cpp_compatibility_probe_entries()
    return rows[-1] if rows else None


def llama_cpp_compatibility_matrix_entries() -> list[dict[str, Any]]:
    if not LLAMA_CPP_COMPATIBILITY_MATRICES.exists():
        return []
    rows: list[dict[str, Any]] = []
    for matrix in sorted(LLAMA_CPP_COMPATIBILITY_MATRICES.glob("LLAMA_CPP_COMPATIBILITY_MATRIX_*.json")):
        data = read_json(matrix)
        if data.get("compatibility_matrix_version") == "1":
            data["matrix_path"] = rel(matrix)
            rows.append(data)
    return rows


def latest_llama_cpp_compatibility_matrix() -> dict[str, Any] | None:
    rows = llama_cpp_compatibility_matrix_entries()
    return rows[-1] if rows else None


def llama_cpp_runtime_swap_plan_entries() -> list[dict[str, Any]]:
    if not LLAMA_CPP_RUNTIME_SWAP_MANIFESTS.exists():
        return []
    rows: list[dict[str, Any]] = []
    for manifest in sorted(LLAMA_CPP_RUNTIME_SWAP_MANIFESTS.glob("LLAMA_CPP_RUNTIME_SWAP_PLAN_*.json")):
        data = read_json(manifest)
        if data.get("runtime_swap_plan_version") == "1":
            data["manifest_path"] = rel(manifest)
            rows.append(data)
    return rows


def latest_llama_cpp_runtime_swap_plan() -> dict[str, Any] | None:
    rows = llama_cpp_runtime_swap_plan_entries()
    return rows[-1] if rows else None


def llama_cpp_runtime_swap_receipt_entries() -> list[dict[str, Any]]:
    if not LLAMA_CPP_RUNTIME_SWAP_RECEIPTS.exists():
        return []
    rows: list[dict[str, Any]] = []
    for receipt in sorted(LLAMA_CPP_RUNTIME_SWAP_RECEIPTS.glob("LLAMA_CPP_RUNTIME_SWAP_PLAN_RECEIPT_*.json")):
        data = read_json(receipt)
        if data.get("runtime_swap_plan_receipt_version") == "1":
            data["receipt_path"] = rel(receipt)
            rows.append(data)
    return rows


def latest_llama_cpp_runtime_swap_receipt() -> dict[str, Any] | None:
    rows = llama_cpp_runtime_swap_receipt_entries()
    return rows[-1] if rows else None


def llama_cpp_runtime_candidate_validation_entries() -> list[dict[str, Any]]:
    if not LLAMA_CPP_RUNTIME_CANDIDATE_VALIDATION_RECEIPTS.exists():
        return []
    rows: list[dict[str, Any]] = []
    for receipt in sorted(LLAMA_CPP_RUNTIME_CANDIDATE_VALIDATION_RECEIPTS.glob("RUNTIME_CANDIDATE_VALIDATION_*.json")):
        data = read_json(receipt)
        if data.get("runtime_candidate_validation_version") == "1":
            data["receipt_path"] = rel(receipt)
            rows.append(data)
    return rows


def latest_llama_cpp_runtime_candidate_validation() -> dict[str, Any] | None:
    rows = llama_cpp_runtime_candidate_validation_entries()
    return rows[-1] if rows else None


def runtime_candidate_failure_diagnosis_entries() -> list[dict[str, Any]]:
    if not RUNTIME_CANDIDATE_FAILURE_DIAGNOSIS_RECEIPTS.exists():
        return []
    rows: list[dict[str, Any]] = []
    for receipt in sorted(RUNTIME_CANDIDATE_FAILURE_DIAGNOSIS_RECEIPTS.glob("RUNTIME_CANDIDATE_FAILURE_DIAGNOSIS_*.json")):
        data = read_json(receipt)
        if data.get("runtime_candidate_failure_diagnosis_version") == "1":
            data["receipt_path"] = rel(receipt)
            rows.append(data)
    return rows


def latest_runtime_candidate_failure_diagnosis() -> dict[str, Any] | None:
    rows = runtime_candidate_failure_diagnosis_entries()
    return rows[-1] if rows else None


def runtime_candidate_validation_replay_entries() -> list[dict[str, Any]]:
    if not RUNTIME_CANDIDATE_VALIDATION_REPLAY_RECEIPTS.exists():
        return []
    rows: list[dict[str, Any]] = []
    for receipt in sorted(RUNTIME_CANDIDATE_VALIDATION_REPLAY_RECEIPTS.glob("RUNTIME_CANDIDATE_VALIDATION_REPLAY_*.json")):
        data = read_json(receipt)
        if data.get("runtime_candidate_validation_replay_version") == "1":
            data["receipt_path"] = rel(receipt)
            rows.append(data)
    return rows


def latest_runtime_candidate_validation_replay() -> dict[str, Any] | None:
    rows = runtime_candidate_validation_replay_entries()
    return rows[-1] if rows else None


def runtime_candidate_alt_command_style_entries() -> list[dict[str, Any]]:
    if not RUNTIME_CANDIDATE_ALT_COMMAND_STYLE_RECEIPTS.exists():
        return []
    rows: list[dict[str, Any]] = []
    for receipt in sorted(RUNTIME_CANDIDATE_ALT_COMMAND_STYLE_RECEIPTS.glob("RUNTIME_CANDIDATE_ALT_COMMAND_STYLE_*.json")):
        data = read_json(receipt)
        if data.get("runtime_candidate_alt_command_style_version") == "1":
            data["receipt_path"] = rel(receipt)
            rows.append(data)
    return rows


def latest_runtime_candidate_alt_command_style() -> dict[str, Any] | None:
    rows = runtime_candidate_alt_command_style_entries()
    return rows[-1] if rows else None


def llama_cpp_runtime_swap_approval_entries() -> list[dict[str, Any]]:
    if not LLAMA_CPP_RUNTIME_SWAP_APPROVAL_RECEIPTS.exists():
        return []
    rows: list[dict[str, Any]] = []
    for receipt in sorted(LLAMA_CPP_RUNTIME_SWAP_APPROVAL_RECEIPTS.glob("RUNTIME_SWAP_APPROVAL_*.json")):
        data = read_json(receipt)
        if data.get("runtime_swap_approval_version") == "1":
            data["receipt_path"] = rel(receipt)
            rows.append(data)
    return rows


def latest_llama_cpp_runtime_swap_approval() -> dict[str, Any] | None:
    rows = llama_cpp_runtime_swap_approval_entries()
    return rows[-1] if rows else None


def first_local_response_smoke_entries() -> list[dict[str, Any]]:
    if not FIRST_LOCAL_RESPONSE_SMOKE_RECEIPTS.exists():
        return []
    rows: list[dict[str, Any]] = []
    for receipt in sorted(FIRST_LOCAL_RESPONSE_SMOKE_RECEIPTS.glob("FIRST_LOCAL_RESPONSE_SMOKE_*.json")):
        data = read_json(receipt)
        if data.get("first_local_response_smoke_version") == "1":
            data["receipt_path"] = rel(receipt)
            rows.append(data)
    return rows


def latest_first_local_response_smoke() -> dict[str, Any] | None:
    rows = first_local_response_smoke_entries()
    return rows[-1] if rows else None


def first_local_response_smoke_exit_fix_entries() -> list[dict[str, Any]]:
    if not FIRST_LOCAL_RESPONSE_SMOKE_EXIT_FIX_RECEIPTS.exists():
        return []
    rows: list[dict[str, Any]] = []
    for receipt in sorted(FIRST_LOCAL_RESPONSE_SMOKE_EXIT_FIX_RECEIPTS.glob("FIRST_LOCAL_RESPONSE_SMOKE_EXIT_FIX_*.json")):
        data = read_json(receipt)
        if data.get("first_local_response_smoke_exit_fix_version") == "1":
            data["receipt_path"] = rel(receipt)
            rows.append(data)
    return rows


def latest_first_local_response_smoke_exit_fix() -> dict[str, Any] | None:
    rows = first_local_response_smoke_exit_fix_entries()
    return rows[-1] if rows else None


def first_response_output_filter_tuning_entries() -> list[dict[str, Any]]:
    if not FIRST_RESPONSE_OUTPUT_FILTER_TUNING_RECEIPTS.exists():
        return []
    rows: list[dict[str, Any]] = []
    for receipt in sorted(FIRST_RESPONSE_OUTPUT_FILTER_TUNING_RECEIPTS.glob("FIRST_RESPONSE_OUTPUT_FILTER_TUNING_*.json")):
        data = read_json(receipt)
        if data.get("first_response_output_filter_tuning_version") == "1":
            data["receipt_path"] = rel(receipt)
            rows.append(data)
    return rows


def latest_first_response_output_filter_tuning() -> dict[str, Any] | None:
    rows = first_response_output_filter_tuning_entries()
    return rows[-1] if rows else None


def bounded_local_chat_smoke_entries() -> list[dict[str, Any]]:
    if not BOUNDED_LOCAL_CHAT_SMOKE_RECEIPTS.exists():
        return []
    rows: list[dict[str, Any]] = []
    for receipt in sorted(BOUNDED_LOCAL_CHAT_SMOKE_RECEIPTS.glob("BOUNDED_LOCAL_CHAT_SMOKE_*.json")):
        data = read_json(receipt)
        if data.get("bounded_local_chat_smoke_version") == "1":
            data["receipt_path"] = rel(receipt)
            rows.append(data)
    return rows


def latest_bounded_local_chat_smoke() -> dict[str, Any] | None:
    rows = bounded_local_chat_smoke_entries()
    return rows[-1] if rows else None


def local_chat_prompt_draft_entries() -> list[dict[str, Any]]:
    if not LOCAL_CHAT_PROMPT_DRAFT_RECEIPTS.exists():
        return []
    rows: list[dict[str, Any]] = []
    for receipt in sorted(LOCAL_CHAT_PROMPT_DRAFT_RECEIPTS.glob("LOCAL_CHAT_PROMPT_DRAFT_*.json")):
        data = read_json(receipt)
        if data.get("local_chat_prompt_draft_version") == "1":
            data["receipt_path"] = rel(receipt)
            rows.append(data)
    return rows


def latest_local_chat_prompt_draft() -> dict[str, Any] | None:
    rows = local_chat_prompt_draft_entries()
    return rows[-1] if rows else None


def local_chat_session_draft_entries() -> list[dict[str, Any]]:
    if not LOCAL_CHAT_SESSION_DRAFT_RECEIPTS.exists():
        return []
    rows: list[dict[str, Any]] = []
    for receipt in sorted(LOCAL_CHAT_SESSION_DRAFT_RECEIPTS.glob("LOCAL_CHAT_SESSION_DRAFT_*.json")):
        data = read_json(receipt)
        if data.get("local_chat_session_draft_version") == "1":
            data["receipt_path"] = rel(receipt)
            rows.append(data)
    return rows


def latest_local_chat_session_draft() -> dict[str, Any] | None:
    rows = local_chat_session_draft_entries()
    return rows[-1] if rows else None


def local_chat_session_review_entries() -> list[dict[str, Any]]:
    if not LOCAL_CHAT_SESSION_REVIEW_RECEIPTS.exists():
        return []
    rows: list[dict[str, Any]] = []
    for receipt in sorted(LOCAL_CHAT_SESSION_REVIEW_RECEIPTS.glob("LOCAL_CHAT_SESSION_REVIEW_*.json")):
        data = read_json(receipt)
        if data.get("local_chat_session_review_version") == "1":
            data["receipt_path"] = rel(receipt)
            rows.append(data)
    return rows


def latest_local_chat_session_review() -> dict[str, Any] | None:
    rows = local_chat_session_review_entries()
    return rows[-1] if rows else None


def local_chat_session_memory_candidate_draft_entries() -> list[dict[str, Any]]:
    if not LOCAL_CHAT_SESSION_REVIEW_CANDIDATES.exists():
        return []
    rows: list[dict[str, Any]] = []
    for receipt in sorted(LOCAL_CHAT_SESSION_REVIEW_CANDIDATES.glob("LOCAL_CHAT_SESSION_MEMORY_CANDIDATE_*.json")):
        data = read_json(receipt)
        if data.get("local_chat_session_review_memory_candidate_draft_version") == "1":
            data["draft_path"] = rel(receipt)
            rows.append(data)
    return rows


def latest_local_chat_session_memory_candidate_draft() -> dict[str, Any] | None:
    rows = local_chat_session_memory_candidate_draft_entries()
    return rows[-1] if rows else None


def local_chat_session_memory_candidate_review_entries() -> list[dict[str, Any]]:
    if not LOCAL_CHAT_MEMORY_CANDIDATE_REVIEW_WRITE_RECEIPTS.exists():
        return []
    rows: list[dict[str, Any]] = []
    for receipt in sorted(LOCAL_CHAT_MEMORY_CANDIDATE_REVIEW_WRITE_RECEIPTS.glob("LOCAL_CHAT_MEMORY_CANDIDATE_REVIEW_*.json")):
        data = read_json(receipt)
        if data.get("local_chat_session_memory_candidate_review_and_approved_write_version") == "1":
            data["receipt_path"] = rel(receipt)
            rows.append(data)
    return rows


def latest_local_chat_session_memory_candidate_review() -> dict[str, Any] | None:
    rows = local_chat_session_memory_candidate_review_entries()
    return rows[-1] if rows else None


def local_chat_session_approved_memory_write_entries() -> list[dict[str, Any]]:
    if not LOCAL_CHAT_MEMORY_CANDIDATE_REVIEW_WRITE_RECEIPTS.exists():
        return []
    rows: list[dict[str, Any]] = []
    for receipt in sorted(LOCAL_CHAT_MEMORY_CANDIDATE_REVIEW_WRITE_RECEIPTS.glob("APPROVED_LOCAL_CHAT_MEMORY_WRITE_*.json")):
        data = read_json(receipt)
        if data.get("local_chat_session_memory_candidate_approved_write_version") == "1":
            data["receipt_path"] = rel(receipt)
            rows.append(data)
    return rows


def latest_local_chat_session_approved_memory_write() -> dict[str, Any] | None:
    rows = local_chat_session_approved_memory_write_entries()
    return rows[-1] if rows else None


def approved_local_chat_memory_records() -> list[dict[str, Any]]:
    if not LOCAL_CHAT_APPROVED_MEMORY_RECORDS.exists():
        return []
    rows: list[dict[str, Any]] = []
    for record in sorted(LOCAL_CHAT_APPROVED_MEMORY_RECORDS.glob("APPROVED_LOCAL_CHAT_MEMORY_RECORD_*.json")):
        data = read_json(record)
        if data.get("approved_local_chat_memory_record_version") == "1":
            data["approved_memory_record_path"] = rel(record)
            rows.append(data)
    return rows


def local_approved_memory_readback_entries() -> list[dict[str, Any]]:
    if not LOCAL_CHAT_APPROVED_MEMORY_READBACK_RECEIPTS.exists():
        return []
    rows: list[dict[str, Any]] = []
    for receipt in sorted(LOCAL_CHAT_APPROVED_MEMORY_READBACK_RECEIPTS.glob("LOCAL_APPROVED_MEMORY_READBACK_*.json")):
        data = read_json(receipt)
        if data.get("local_approved_memory_readback_version") == "1":
            data["receipt_path"] = rel(receipt)
            rows.append(data)
    return rows


def latest_local_approved_memory_readback() -> dict[str, Any] | None:
    rows = local_approved_memory_readback_entries()
    return rows[-1] if rows else None


def local_approved_memory_context_preview_entries() -> list[dict[str, Any]]:
    if not LOCAL_CHAT_APPROVED_MEMORY_CONTEXT_PREVIEW_RECEIPTS.exists():
        return []
    rows: list[dict[str, Any]] = []
    for receipt in sorted(LOCAL_CHAT_APPROVED_MEMORY_CONTEXT_PREVIEW_RECEIPTS.glob("LOCAL_APPROVED_MEMORY_CONTEXT_PREVIEW_*.json")):
        data = read_json(receipt)
        if data.get("local_approved_memory_context_preview_version") == "1":
            data["receipt_path"] = rel(receipt)
            rows.append(data)
    return rows


def latest_local_approved_memory_context_preview() -> dict[str, Any] | None:
    rows = local_approved_memory_context_preview_entries()
    return rows[-1] if rows else None


def local_approved_memory_context_run_entries() -> list[dict[str, Any]]:
    if not LOCAL_CHAT_APPROVED_MEMORY_CONTEXT_PREVIEW_RECEIPTS.exists():
        return []
    rows: list[dict[str, Any]] = []
    for receipt in sorted(LOCAL_CHAT_APPROVED_MEMORY_CONTEXT_PREVIEW_RECEIPTS.glob("LOCAL_APPROVED_MEMORY_CONTEXT_RUN_*.json")):
        data = read_json(receipt)
        if data.get("local_approved_memory_context_run_version") == "1":
            data["receipt_path"] = rel(receipt)
            rows.append(data)
    return rows


def latest_local_approved_memory_context_run() -> dict[str, Any] | None:
    rows = local_approved_memory_context_run_entries()
    return rows[-1] if rows else None


def local_open_chat_supervised_run_entries() -> list[dict[str, Any]]:
    if not LOCAL_OPEN_CHAT_SUPERVISED_RUN_RECEIPTS.exists():
        return []
    rows: list[dict[str, Any]] = []
    for receipt in sorted(LOCAL_OPEN_CHAT_SUPERVISED_RUN_RECEIPTS.glob("LOCAL_OPEN_CHAT_SUPERVISED_TURN_*.json")):
        data = read_json(receipt)
        if data.get("local_open_chat_supervised_run_version") == "1":
            data["receipt_path"] = rel(receipt)
            rows.append(data)
    return rows


def latest_local_open_chat_supervised_run() -> dict[str, Any] | None:
    rows = local_open_chat_supervised_run_entries()
    return rows[-1] if rows else None


def persistent_chat_supervised_runtime_plan_entries() -> list[dict[str, Any]]:
    if not PERSISTENT_CHAT_SUPERVISED_RUNTIME_PLAN_RECEIPTS.exists():
        return []
    rows: list[dict[str, Any]] = []
    for receipt in sorted(PERSISTENT_CHAT_SUPERVISED_RUNTIME_PLAN_RECEIPTS.glob("PERSISTENT_CHAT_SUPERVISED_RUNTIME_PLAN_*.json")):
        data = read_json(receipt)
        if data.get("persistent_chat_supervised_runtime_plan_version") == "1":
            data["receipt_path"] = rel(receipt)
            rows.append(data)
    return rows


def latest_persistent_chat_supervised_runtime_plan() -> dict[str, Any] | None:
    rows = persistent_chat_supervised_runtime_plan_entries()
    if rows:
        return rows[-1]
    plan = read_json(PERSISTENT_CHAT_SUPERVISED_RUNTIME_PLAN_JSON)
    if plan.get("persistent_chat_supervised_runtime_plan_version") == "1":
        plan["receipt_path"] = None
        return plan
    return None


def runtime_path_config() -> dict[str, Any]:
    return read_json(RUNTIME_PATH_CONFIG_MANIFEST)


def approved_engel_root_statuses() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path_text, role in APPROVED_ENGEL_ROOTS:
        path = Path(path_text)
        row = {
            "path": path_text,
            "role": role,
            "present": path.exists() and path.is_dir(),
            "recursive_scan_enabled": False,
        }
        if path_text.startswith("F:"):
            expected_folders = [
                path / "models",
                path / "runtimes",
                path / "libraries",
                path / "chat_exports",
                path / "remote_worker",
                path / "code_companion",
                path / "backups",
                path / "receipts",
                path / "reports",
                path / "manifests",
                path / "quarantine",
            ]
            row["scaffold_created"] = path.exists() and all(folder.exists() and folder.is_dir() for folder in expected_folders)
        rows.append(row)
    return rows


def model_key_for_tier(tier: str) -> str:
    mapping = {
        "Tiny Seed Mode": "tiny_seed",
        "Daily Local Mode": "daily_local",
        "Research Worker Mode": "research_worker",
        "Alternative Research Worker": "alternative_research_worker",
    }
    return mapping.get(tier, "unknown")


def model_file_status(expected_path: str) -> dict[str, Any]:
    if expected_path == "unknown":
        return {
            "status": "unknown",
            "file_size_bytes": None,
            "sha256": None,
            "hash_status": "no_clear_expected_path",
        }
    path = Path(expected_path)
    if not path.exists() or not path.is_file():
        return {
            "status": "missing",
            "file_size_bytes": None,
            "sha256": None,
            "hash_status": "missing",
        }
    try:
        size = path.stat().st_size
    except OSError:
        return {
            "status": "unknown",
            "file_size_bytes": None,
            "sha256": None,
            "hash_status": "stat_failed",
        }
    if size > MAX_HASH_BYTES:
        return {
            "status": "present_unreviewed",
            "file_size_bytes": size,
            "sha256": None,
            "hash_status": "skipped_large_file",
        }
    try:
        file_hash = sha256_file(path)
    except OSError:
        file_hash = None
        hash_status = "hash_failed"
    else:
        hash_status = "hashed_bounded_file"
    return {
        "status": "present_unreviewed",
        "file_size_bytes": size,
        "sha256": file_hash,
        "hash_status": hash_status,
    }


def collect_models() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    entries = model_entries()
    by_tier = {str(entry.get("tier")): entry for entry in entries}
    intake_by_source = model_intake_entries_by_source()
    approval_by_source = model_review_approval_entries_by_source()
    dry_run_by_key = runtime_dry_run_entries_by_model_key()
    for tier, model_name in EXPECTED_MODEL_TIERS:
        model_key = model_key_for_tier(tier)
        entry = by_tier.get(tier, {})
        expected_path = model_expected_path(entry) if entry else "unknown"
        file_state = model_file_status(expected_path)
        intake_entry = intake_by_source.get(str(Path(expected_path).resolve(strict=False))) if expected_path != "unknown" else None
        approval_entry = approval_by_source.get(str(Path(expected_path).resolve(strict=False))) if expected_path != "unknown" else None
        dry_run_entry = dry_run_by_key.get(model_key)
        rows.append(
            {
                "model_key": model_key,
                "tier": tier,
                "model_name": model_name,
                "expected_path": expected_path,
                "status": file_state["status"],
                "file_size_bytes": file_state["file_size_bytes"],
                "sha256": file_state["sha256"],
                "hash_status": file_state["hash_status"],
                "manual_approval_required": True,
                "auto_load_enabled": False,
                "inference_enabled": False,
                "download_enabled": False,
                "plan_local_file_status": entry.get("local_file_status") if entry else "unknown",
                "plan_manual_presence_status": entry.get("manual_presence_status") if entry else "unknown",
                "model_intake_receipt_present": intake_entry is not None,
                "model_intake_review_status": intake_entry.get("review_status", "not_intaken") if intake_entry else "not_intaken",
                "model_review_approval_present": approval_entry is not None,
                "model_review_approval_status": approval_entry.get("review_status", "not_approved_for_dry_run") if approval_entry else "not_approved_for_dry_run",
                "approved_for_runtime_dry_run": bool(approval_entry and approval_entry.get("approved_for_runtime_dry_run") is True),
                "runtime_dry_run_eligible": bool(approval_entry and approval_entry.get("runtime_dry_run_eligible") is True),
                "runtime_dry_run_receipt_present": dry_run_entry is not None,
                "runtime_dry_run_completed": bool(dry_run_entry and dry_run_entry.get("runtime_dry_run_completed") is True),
                "runtime_dry_run_ready": bool(dry_run_entry and dry_run_entry.get("runtime_dry_run_ready") is True),
                "runtime_dry_run_final_decision": dry_run_entry.get("final_decision", "not_run") if dry_run_entry else "not_run",
                "runtime_backend": dry_run_entry.get("runtime_backend", "unknown") if dry_run_entry else "unknown",
                "runtime_binary_present": bool(dry_run_entry and dry_run_entry.get("runtime_binary_present") is True),
                "approved_for_runtime": False,
                "runtime_ready": False,
                "trust_level": "untrusted_until_human_review",
            }
        )
    return {
        "section": "Model Inventory",
        "status": "MANUAL_REQUIRED",
        "plan_present": MODEL_PLAN.exists(),
        "expected_tiers": rows,
        "auto_load_enabled": False,
        "inference_enabled": False,
        "download_enabled": False,
        "manual_approval_required": True,
        "manual_model_file_intake_present": (PROJECT_ROOT / "engel_ai_manual_model_file_intake.py").exists(),
        "model_intake_manifest_present": MODEL_INTAKE_MANIFEST.exists(),
        "model_review_approval_present": (PROJECT_ROOT / "engel_ai_model_review_approval.py").exists(),
        "model_review_approval_manifest_present": MODEL_REVIEW_APPROVAL_MANIFEST.exists(),
        "offline_runtime_dry_run_present": (PROJECT_ROOT / "engel_ai_offline_runtime_dry_run.py").exists(),
        "runtime_dry_run_manifest_present": RUNTIME_DRY_RUN_MANIFEST.exists(),
        "notes": [
            "Model file presence does not enable runtime.",
            "Model review approval enables dry-run eligibility only.",
            "Runtime dry-run receipts do not enable inference.",
            "Large model files are not hashed by this readiness dashboard.",
            "No model is loaded and no inference is run.",
        ],
    }


def collect_runtime_boundaries() -> dict[str, Any]:
    runtime = read_json(OFFLINE_RUNTIME_CONTRACT)
    seed = read_json(OFFLINE_SEED_CONTRACT)
    dry_run_entries = runtime_dry_run_entries_by_model_key()
    no_generation_entries = no_generation_load_check_entries()
    latest_no_generation = latest_no_generation_load_check()
    compatibility_probe_entries = llama_cpp_compatibility_probe_entries()
    latest_compatibility_probe = latest_llama_cpp_compatibility_probe()
    compatibility_matrix_entries = llama_cpp_compatibility_matrix_entries()
    latest_compatibility_matrix = latest_llama_cpp_compatibility_matrix()
    runtime_swap_plan_entries = llama_cpp_runtime_swap_plan_entries()
    latest_runtime_swap_plan = latest_llama_cpp_runtime_swap_plan()
    runtime_swap_receipt_entries = llama_cpp_runtime_swap_receipt_entries()
    latest_runtime_swap_receipt = latest_llama_cpp_runtime_swap_receipt()
    candidate_validation_entries = llama_cpp_runtime_candidate_validation_entries()
    latest_candidate_validation = latest_llama_cpp_runtime_candidate_validation()
    failure_diagnosis_entries = runtime_candidate_failure_diagnosis_entries()
    latest_failure_diagnosis = latest_runtime_candidate_failure_diagnosis()
    replay_entries = runtime_candidate_validation_replay_entries()
    latest_replay = latest_runtime_candidate_validation_replay()
    alt_style_entries = runtime_candidate_alt_command_style_entries()
    latest_alt_style = latest_runtime_candidate_alt_command_style()
    swap_approval_entries = llama_cpp_runtime_swap_approval_entries()
    latest_swap_approval = latest_llama_cpp_runtime_swap_approval()
    first_smoke_entries = first_local_response_smoke_entries()
    latest_first_smoke = latest_first_local_response_smoke()
    exit_fix_entries = first_local_response_smoke_exit_fix_entries()
    latest_exit_fix = latest_first_local_response_smoke_exit_fix()
    filter_tuning_entries = first_response_output_filter_tuning_entries()
    latest_filter_tuning = latest_first_response_output_filter_tuning()
    bounded_chat_entries = bounded_local_chat_smoke_entries()
    latest_bounded_chat = latest_bounded_local_chat_smoke()
    prompt_draft_entries = local_chat_prompt_draft_entries()
    latest_prompt_draft = latest_local_chat_prompt_draft()
    session_draft_entries = local_chat_session_draft_entries()
    latest_session_draft = latest_local_chat_session_draft()
    session_review_entries = local_chat_session_review_entries()
    latest_session_review = latest_local_chat_session_review()
    session_candidate_entries = local_chat_session_memory_candidate_draft_entries()
    latest_session_candidate = latest_local_chat_session_memory_candidate_draft()
    session_memory_candidate_review_entries = local_chat_session_memory_candidate_review_entries()
    latest_session_memory_candidate_review = latest_local_chat_session_memory_candidate_review()
    session_approved_memory_write_entries = local_chat_session_approved_memory_write_entries()
    latest_session_approved_memory_write = latest_local_chat_session_approved_memory_write()
    approved_local_chat_memory_record_entries = approved_local_chat_memory_records()
    local_approved_memory_readback_receipt_entries = local_approved_memory_readback_entries()
    latest_local_approved_readback = latest_local_approved_memory_readback()
    local_approved_memory_context_preview_receipt_entries = local_approved_memory_context_preview_entries()
    latest_local_memory_context_preview = latest_local_approved_memory_context_preview()
    local_approved_memory_context_run_receipt_entries = local_approved_memory_context_run_entries()
    latest_local_memory_context_run = latest_local_approved_memory_context_run()
    local_open_chat_supervised_receipt_entries = local_open_chat_supervised_run_entries()
    latest_open_chat_supervised = latest_local_open_chat_supervised_run()
    persistent_chat_plan_entries = persistent_chat_supervised_runtime_plan_entries()
    latest_persistent_chat_plan = latest_persistent_chat_supervised_runtime_plan()
    gui_state = gui_marker_state()
    candidate_ready_for_swap_review = bool(
        (latest_candidate_validation and latest_candidate_validation.get("candidate_runtime_ready_for_swap_review") is True)
        or (latest_replay and latest_replay.get("candidate_runtime_ready_for_swap_review") is True)
        or (latest_alt_style and latest_alt_style.get("candidate_runtime_ready_for_swap_review") is True)
    )
    first_local_response_smoke_allowed_next = bool(
        latest_swap_approval
        and latest_swap_approval.get("runtime_swap_approval_recorded") is True
        and latest_swap_approval.get("first_local_response_smoke_allowed_next") is True
    )
    first_local_response_smoke_passed = bool(
        (latest_first_smoke and latest_first_smoke.get("first_response_smoke_passed") is True)
        or (latest_exit_fix and latest_exit_fix.get("first_response_smoke_exit_fix_passed") is True)
        or (
            latest_filter_tuning
            and latest_filter_tuning.get("diagnosis_classification") == "clean_single_turn_exit_but_filter_too_strict"
            and latest_filter_tuning.get("first_response_smoke_passed_after_tuning_preview") is True
        )
    )
    first_local_response_smoke_exit_fix_passed = bool(
        latest_exit_fix
        and latest_exit_fix.get("first_response_smoke_exit_fix_passed") is True
    )
    first_response_output_filter_tuning_passed = bool(
        latest_filter_tuning
        and latest_filter_tuning.get("diagnosis_classification") == "clean_single_turn_exit_but_filter_too_strict"
        and latest_filter_tuning.get("first_response_smoke_passed_after_tuning_preview") is True
    )
    bounded_local_chat_smoke_passed = bool(
        latest_bounded_chat
        and latest_bounded_chat.get("bounded_local_chat_smoke_passed") is True
        and latest_bounded_chat.get("output_marked_untrusted") is True
        and latest_bounded_chat.get("model_output_trusted") is False
        and latest_bounded_chat.get("runtime_ready_for_inference") is False
        and latest_bounded_chat.get("open_chat_enabled") is False
    )
    local_chat_panel_bounded_run_enabled = bool(
        LOCAL_CHAT_PANEL_ENABLE_REPORT.exists()
        and exists("tools\\verify_engel_ai_local_chat_panel_enable_bounded_run.py")
        and gui_state["local_ai_bounded_run_section_present"]
    )
    local_chat_prompt_draft_passed = bool(
        latest_prompt_draft
        and latest_prompt_draft.get("local_chat_prompt_draft_passed") is True
        and latest_prompt_draft.get("output_marked_untrusted") is True
        and latest_prompt_draft.get("model_output_trusted") is False
        and latest_prompt_draft.get("runtime_ready_for_inference") is False
        and latest_prompt_draft.get("open_chat_enabled") is False
    )
    bounded_human_prompt_enabled = bool(
        LOCAL_CHAT_PROMPT_DRAFT_REPORT.exists()
        and exists("engel_ai_local_chat_prompt_draft.py")
        and exists("tools\\verify_engel_ai_local_chat_prompt_draft.py")
        and local_chat_prompt_draft_passed
        and gui_state["local_ai_human_prompt_draft_section_present"]
    )
    local_chat_session_draft_passed = bool(
        latest_session_draft
        and latest_session_draft.get("local_chat_session_draft_turn_passed") is True
        and latest_session_draft.get("output_marked_untrusted") is True
        and latest_session_draft.get("model_output_trusted") is False
        and latest_session_draft.get("session_transcript_trusted") is False
        and latest_session_draft.get("automatic_next_turn_enabled") is False
        and latest_session_draft.get("runtime_ready_for_inference") is False
        and latest_session_draft.get("open_chat_enabled") is False
    )
    bounded_session_draft_enabled = bool(
        LOCAL_CHAT_SESSION_DRAFT_REPORT.exists()
        and exists("engel_ai_local_chat_session_draft.py")
        and exists("tools\\verify_engel_ai_local_chat_session_draft.py")
        and local_chat_session_draft_passed
        and gui_state["local_ai_session_draft_section_present"]
    )
    local_chat_session_review_passed = bool(
        latest_session_review
        and latest_session_review.get("local_chat_session_review_version") == "1"
        and latest_session_review.get("review_output_trusted") is False
        and latest_session_review.get("trusted_memory_write_enabled") is False
        and latest_session_review.get("approved_memory_write_enabled") is False
        and latest_session_review.get("runtime_process_started") is False
        and latest_session_review.get("model_process_started") is False
        and latest_session_review.get("runtime_ready_for_inference") is False
        and latest_session_review.get("open_chat_enabled") is False
    )
    local_chat_session_review_available = bool(
        LOCAL_CHAT_SESSION_REVIEW_REPORT.exists()
        and exists("engel_ai_local_chat_session_review.py")
        and exists("tools\\verify_engel_ai_local_chat_session_review.py")
        and local_chat_session_review_passed
    )
    local_chat_session_memory_candidate_draft_available = bool(
        latest_session_candidate
        and latest_session_candidate.get("trust_state") == "untrusted"
        and latest_session_candidate.get("human_review_required") is True
        and latest_session_candidate.get("promoted_to_trusted_memory") is False
        and latest_session_candidate.get("trusted_memory_write_enabled") is False
        and latest_session_candidate.get("approved_memory_write_enabled") is False
    )
    local_chat_session_memory_candidate_review_available = bool(
        latest_session_memory_candidate_review
        and latest_session_memory_candidate_review.get("local_chat_session_memory_candidate_review_and_approved_write_version") == "1"
        and latest_session_memory_candidate_review.get("human_approval_required") is False
        and latest_session_memory_candidate_review.get("approval_token_required") is False
        and latest_session_memory_candidate_review.get("review_output_trusted") is False
        and latest_session_memory_candidate_review.get("candidate_content_obeyed") is False
        and latest_session_memory_candidate_review.get("runtime_process_started") is False
        and latest_session_memory_candidate_review.get("model_process_started") is False
        and latest_session_memory_candidate_review.get("runtime_ready_for_inference") is False
        and latest_session_memory_candidate_review.get("open_chat_enabled") is False
    )
    local_chat_session_approved_memory_records_available = bool(approved_local_chat_memory_record_entries)
    local_approved_memory_readback_available = bool(
        latest_local_approved_readback
        and latest_local_approved_readback.get("local_approved_memory_readback_version") == "1"
        and latest_local_approved_readback.get("approval_required_for_readback") is False
        and latest_local_approved_readback.get("memory_write_performed") is False
        and latest_local_approved_readback.get("global_trusted_memory") is False
        and latest_local_approved_readback.get("used_as_hidden_prompt_context") is False
        and latest_local_approved_readback.get("automatic_context_injection_enabled") is False
        and latest_local_approved_readback.get("runtime_process_started") is False
        and latest_local_approved_readback.get("model_process_started") is False
        and latest_local_approved_readback.get("runtime_ready_for_inference") is False
        and latest_local_approved_readback.get("open_chat_enabled") is False
    )
    local_approved_memory_context_preview_available = bool(
        latest_local_memory_context_preview
        and latest_local_memory_context_preview.get("local_approved_memory_context_preview_version") == "1"
        and latest_local_memory_context_preview.get("visible_context_only") is True
        and latest_local_memory_context_preview.get("hidden_prompt_context") is False
        and latest_local_memory_context_preview.get("automatic_context_injection_enabled") is False
        and latest_local_memory_context_preview.get("global_trusted_memory") is False
        and latest_local_memory_context_preview.get("memory_write_performed") is False
        and latest_local_memory_context_preview.get("runtime_process_started") is False
        and latest_local_memory_context_preview.get("model_process_started") is False
        and latest_local_memory_context_preview.get("runtime_ready_for_inference") is False
        and latest_local_memory_context_preview.get("open_chat_enabled") is False
    )
    local_approved_memory_context_run_passed = bool(
        latest_local_memory_context_run
        and latest_local_memory_context_run.get("local_approved_memory_context_run_passed") is True
        and latest_local_memory_context_run.get("output_marked_untrusted") is True
        and latest_local_memory_context_run.get("model_output_trusted") is False
        and latest_local_memory_context_run.get("hidden_prompt_context") is False
        and latest_local_memory_context_run.get("automatic_context_injection_enabled") is False
        and latest_local_memory_context_run.get("memory_write_performed") is False
        and latest_local_memory_context_run.get("runtime_ready_for_inference") is False
        and latest_local_memory_context_run.get("open_chat_enabled") is False
    )
    local_open_chat_supervised_run_available = bool(
        latest_open_chat_supervised
        and gui_state["local_ai_supervised_open_chat_section_present"]
        and latest_open_chat_supervised.get("local_open_chat_supervised_turn_passed") is True
        and latest_open_chat_supervised.get("mode") == "supervised_local_open_chat"
        and latest_open_chat_supervised.get("open_chat_enabled") is True
        and latest_open_chat_supervised.get("open_chat_scope") == "supervised_local_gui_session_only"
        and latest_open_chat_supervised.get("chat_enabled") is True
        and latest_open_chat_supervised.get("chat_scope") == "supervised_local_gui_session_only"
        and latest_open_chat_supervised.get("persistent_chat_loop_enabled") is False
        and latest_open_chat_supervised.get("server_enabled") is False
        and latest_open_chat_supervised.get("provider_api_enabled") is False
        and latest_open_chat_supervised.get("trusted_memory_write_enabled") is False
        and latest_open_chat_supervised.get("memory_write_performed") is False
        and latest_open_chat_supervised.get("runtime_ready_for_inference") is False
    )
    persistent_chat_plan_available = bool(
        latest_persistent_chat_plan
        and latest_persistent_chat_plan.get("persistent_chat_supervised_runtime_plan_version") == "1"
        and latest_persistent_chat_plan.get("persistent_chat_enabled") is False
        and latest_persistent_chat_plan.get("persistent_runtime_enabled") is False
        and latest_persistent_chat_plan.get("true_long_lived_model_process_enabled") is False
        and latest_persistent_chat_plan.get("recommended_next_mode") == "supervised_persistent_gui_session_repeated_bounded_calls"
        and latest_persistent_chat_plan.get("server_enabled") is False
        and latest_persistent_chat_plan.get("provider_api_enabled") is False
        and latest_persistent_chat_plan.get("trusted_memory_write_enabled") is False
    )
    compatibility_probe_passed = bool(latest_compatibility_probe and latest_compatibility_probe.get("candidate_probe_passed") is True)
    no_generation_ready = bool((latest_no_generation and latest_no_generation.get("no_generation_load_check_passed") is True) or compatibility_probe_passed)
    path_config = runtime_path_config()
    configured_runtime_path = path_config.get("runtime_binary_path") if isinstance(path_config.get("runtime_binary_path"), str) else None
    configured_runtime_present = bool(configured_runtime_path and Path(configured_runtime_path).exists() and Path(configured_runtime_path).is_file())
    return {
        "section": "Runtime Boundaries",
        "status": "DISABLED_BY_SAFETY",
        "offline_model_runtime_contract_present": OFFLINE_RUNTIME_CONTRACT.exists(),
        "offline_seed_llm_contract_present": OFFLINE_SEED_CONTRACT.exists(),
        "local_runtime_path_config_module_present": exists("engel_ai_local_runtime_path_config.py"),
        "runtime_path_config_manifest_present": RUNTIME_PATH_CONFIG_MANIFEST.exists(),
        "approved_engel_roots": approved_engel_root_statuses(),
        "preferred_runtime_root": PREFERRED_RUNTIME_ROOT,
        "alternate_runtime_root": ALTERNATE_RUNTIME_ROOT,
        "expansion_library_root": EXPANSION_LIBRARY_ROOT,
        "memory_roots_storage_layout_present": exists("engel_memory_roots_storage_layout.py"),
        "memory_roots_storage_layout_manifest_present": exists("memory\\ENGEL_MEMORY_ROOTS_STORAGE_LAYOUT_V1.json"),
        "runtime_path_config_status": {
            "runtime_backend": path_config.get("runtime_backend", "not_configured"),
            "runtime_binary_path": configured_runtime_path,
            "runtime_binary_present": configured_runtime_present,
            "runtime_path_approved": bool(path_config.get("runtime_path_approved") is True),
            "runtime_execution_enabled": False,
            "model_load_enabled": False,
            "inference_enabled": False,
        },
        "runtime_enabled": bool(runtime.get("runtime_enabled") is True or seed.get("model_runtime_enabled") is True),
        "inference_enabled": False,
        "model_auto_load_enabled": False,
        "provider_api_enabled": False,
        "local_server_enabled": False,
        "background_worker_enabled": False,
        "download_enabled": False,
        "install_package_enabled": False,
        "model_output_trust": "untrusted_generated_text",
        "future_runtime_requires_approval": True,
        "offline_runtime_dry_run_module_present": exists("engel_ai_offline_runtime_dry_run.py"),
        "runtime_dry_run_manifest_present": RUNTIME_DRY_RUN_MANIFEST.exists(),
        "runtime_dry_run_entry_count": len(dry_run_entries),
        "runtime_dry_run_ready_count": len([entry for entry in dry_run_entries.values() if entry.get("runtime_dry_run_ready") is True]),
        "no_generation_load_check_module_present": exists("engel_ai_no_generation_load_check.py"),
        "no_generation_load_check_receipt_count": len(no_generation_entries),
        "latest_no_generation_load_check": {
            "receipt_path": latest_no_generation.get("receipt_path"),
            "no_generation_load_check_version": latest_no_generation.get("no_generation_load_check_version"),
            "model_key": latest_no_generation.get("model_key"),
            "command_style": latest_no_generation.get("command_style"),
            "exit_code": latest_no_generation.get("exit_code"),
            "timed_out": latest_no_generation.get("timed_out"),
            "interrupted": latest_no_generation.get("interrupted"),
            "orphan_process_detected": latest_no_generation.get("orphan_process_detected"),
            "no_generation_load_check_passed": latest_no_generation.get("no_generation_load_check_passed"),
            "final_decision": latest_no_generation.get("final_decision"),
        } if latest_no_generation else None,
        "llama_cpp_compatibility_matrix_module_present": exists("engel_ai_llama_cpp_compatibility_matrix.py"),
        "llama_cpp_compatibility_matrix_count": len(compatibility_matrix_entries),
        "latest_llama_cpp_compatibility_matrix": {
            "matrix_path": latest_compatibility_matrix.get("matrix_path"),
            "recommended_candidate_id": latest_compatibility_matrix.get("recommended_candidate_id"),
            "final_decision": latest_compatibility_matrix.get("final_decision"),
        } if latest_compatibility_matrix else None,
        "llama_cpp_compatibility_probe_receipt_count": len(compatibility_probe_entries),
        "latest_llama_cpp_compatibility_probe": {
            "receipt_path": latest_compatibility_probe.get("receipt_path"),
            "candidate_id": latest_compatibility_probe.get("candidate_id"),
            "exit_code": latest_compatibility_probe.get("exit_code"),
            "timed_out": latest_compatibility_probe.get("timed_out"),
            "interrupted": latest_compatibility_probe.get("interrupted"),
            "orphan_process_detected": latest_compatibility_probe.get("orphan_process_detected"),
            "candidate_probe_passed": latest_compatibility_probe.get("candidate_probe_passed"),
            "final_decision": latest_compatibility_probe.get("final_decision"),
        } if latest_compatibility_probe else None,
        "llama_cpp_runtime_swap_plan_module_present": exists("engel_ai_llama_cpp_runtime_swap_plan.py"),
        "llama_cpp_runtime_swap_plan_count": len(runtime_swap_plan_entries),
        "latest_llama_cpp_runtime_swap_plan": {
            "manifest_path": latest_runtime_swap_plan.get("manifest_path"),
            "latest_recommended_candidate_id": latest_runtime_swap_plan.get("latest_recommended_candidate_id"),
            "latest_candidate_probe_succeeded": latest_runtime_swap_plan.get("latest_candidate_probe_succeeded"),
            "manual_download_required": latest_runtime_swap_plan.get("manual_download_required"),
            "engel_download_enabled": latest_runtime_swap_plan.get("engel_download_enabled"),
            "engel_install_enabled": latest_runtime_swap_plan.get("engel_install_enabled"),
            "runtime_execution_enabled_in_this_phase": latest_runtime_swap_plan.get("runtime_execution_enabled_in_this_phase"),
            "model_load_enabled_in_this_phase": latest_runtime_swap_plan.get("model_load_enabled_in_this_phase"),
            "next_validation_phase": latest_runtime_swap_plan.get("next_validation_phase"),
            "final_decision": latest_runtime_swap_plan.get("final_decision"),
        } if latest_runtime_swap_plan else None,
        "llama_cpp_runtime_swap_receipt_count": len(runtime_swap_receipt_entries),
        "latest_llama_cpp_runtime_swap_receipt": {
            "receipt_path": latest_runtime_swap_receipt.get("receipt_path"),
            "manifest_path": latest_runtime_swap_receipt.get("manifest_path"),
            "manual_download_required": latest_runtime_swap_receipt.get("manual_download_required"),
            "runtime_execution_enabled_in_this_phase": latest_runtime_swap_receipt.get("runtime_execution_enabled_in_this_phase"),
            "model_load_enabled_in_this_phase": latest_runtime_swap_receipt.get("model_load_enabled_in_this_phase"),
            "next_validation_phase": latest_runtime_swap_receipt.get("next_validation_phase"),
            "final_decision": latest_runtime_swap_receipt.get("final_decision"),
        } if latest_runtime_swap_receipt else None,
        "llama_cpp_runtime_candidate_validation_module_present": exists("engel_ai_llama_cpp_runtime_candidate_validation.py"),
        "llama_cpp_runtime_candidate_validation_receipt_count": len(candidate_validation_entries),
        "latest_llama_cpp_runtime_candidate_validation": {
            "receipt_path": latest_candidate_validation.get("receipt_path"),
            "candidate_folder": latest_candidate_validation.get("candidate_folder"),
            "selected_command_style": latest_candidate_validation.get("selected_command_style"),
            "exit_code": latest_candidate_validation.get("exit_code"),
            "timed_out": latest_candidate_validation.get("timed_out"),
            "interrupted": latest_candidate_validation.get("interrupted"),
            "orphan_process_detected": latest_candidate_validation.get("orphan_process_detected"),
            "candidate_validation_passed": latest_candidate_validation.get("candidate_validation_passed"),
            "candidate_runtime_ready_for_swap_review": latest_candidate_validation.get("candidate_runtime_ready_for_swap_review"),
            "registered_runtime_changed": latest_candidate_validation.get("registered_runtime_changed"),
            "runtime_ready_for_inference": latest_candidate_validation.get("runtime_ready_for_inference"),
            "final_decision": latest_candidate_validation.get("final_decision"),
        } if latest_candidate_validation else None,
        "runtime_candidate_failure_diagnosis_module_present": exists("engel_ai_runtime_candidate_failure_diagnosis.py"),
        "runtime_candidate_failure_diagnosis_receipt_count": len(failure_diagnosis_entries),
        "latest_runtime_candidate_failure_diagnosis": {
            "receipt_path": latest_failure_diagnosis.get("receipt_path"),
            "source_receipt_path": latest_failure_diagnosis.get("source_receipt_path"),
            "diagnosis_classification": latest_failure_diagnosis.get("diagnosis_classification"),
            "historical_receipt_modified": latest_failure_diagnosis.get("historical_receipt_modified"),
            "registered_runtime_changed": latest_failure_diagnosis.get("registered_runtime_changed"),
            "runtime_ready_for_inference": latest_failure_diagnosis.get("runtime_ready_for_inference"),
            "recommended_next_action": latest_failure_diagnosis.get("recommended_next_action"),
            "final_decision": latest_failure_diagnosis.get("final_decision"),
        } if latest_failure_diagnosis else None,
        "runtime_candidate_validation_replay_module_present": exists("engel_ai_runtime_candidate_validation_replay.py"),
        "runtime_candidate_validation_replay_receipt_count": len(replay_entries),
        "latest_runtime_candidate_validation_replay": {
            "receipt_path": latest_replay.get("receipt_path"),
            "candidate_folder": latest_replay.get("candidate_folder"),
            "command_style": latest_replay.get("command_style"),
            "exit_code": latest_replay.get("exit_code"),
            "timed_out": latest_replay.get("timed_out"),
            "interrupted": latest_replay.get("interrupted"),
            "post_process_interruption": latest_replay.get("post_process_interruption"),
            "orphan_process_detected": latest_replay.get("orphan_process_detected"),
            "disqualifying_interactive_markers_found": latest_replay.get("disqualifying_interactive_markers_found"),
            "disqualifying_generation_markers_found": latest_replay.get("disqualifying_generation_markers_found"),
            "generated_text_detected": latest_replay.get("generated_text_detected"),
            "candidate_validation_replay_passed": latest_replay.get("candidate_validation_replay_passed"),
            "candidate_runtime_ready_for_swap_review": latest_replay.get("candidate_runtime_ready_for_swap_review"),
            "registered_runtime_changed": latest_replay.get("registered_runtime_changed"),
            "runtime_ready_for_inference": latest_replay.get("runtime_ready_for_inference"),
            "final_decision": latest_replay.get("final_decision"),
        } if latest_replay else None,
        "runtime_candidate_alt_command_style_module_present": exists("engel_ai_runtime_candidate_alt_command_style.py"),
        "runtime_candidate_alt_command_style_receipt_count": len(alt_style_entries),
        "latest_runtime_candidate_alt_command_style": {
            "receipt_path": latest_alt_style.get("receipt_path"),
            "candidate_folder": latest_alt_style.get("candidate_folder"),
            "selected_command_style": latest_alt_style.get("selected_command_style"),
            "exit_code": latest_alt_style.get("exit_code"),
            "timed_out": latest_alt_style.get("timed_out"),
            "interrupted": latest_alt_style.get("interrupted"),
            "orphan_process_detected": latest_alt_style.get("orphan_process_detected"),
            "disqualifying_interactive_markers_found": latest_alt_style.get("disqualifying_interactive_markers_found"),
            "disqualifying_generation_markers_found": latest_alt_style.get("disqualifying_generation_markers_found"),
            "generated_text_detected": latest_alt_style.get("generated_text_detected"),
            "tokenization_output_classified_non_generation": latest_alt_style.get("tokenization_output_classified_non_generation"),
            "alt_command_style_validation_passed": latest_alt_style.get("alt_command_style_validation_passed"),
            "candidate_runtime_ready_for_swap_review": latest_alt_style.get("candidate_runtime_ready_for_swap_review"),
            "registered_runtime_changed": latest_alt_style.get("registered_runtime_changed"),
            "runtime_ready_for_inference": latest_alt_style.get("runtime_ready_for_inference"),
            "runtime_no_generation_check_ready": latest_alt_style.get("runtime_no_generation_check_ready"),
            "final_decision": latest_alt_style.get("final_decision"),
        } if latest_alt_style else None,
        "llama_cpp_runtime_swap_approval_module_present": exists("engel_ai_llama_cpp_runtime_swap_approval.py"),
        "llama_cpp_runtime_swap_approval_receipt_count": len(swap_approval_entries),
        "latest_llama_cpp_runtime_swap_approval": {
            "receipt_path": latest_swap_approval.get("receipt_path"),
            "source_alt_command_style_receipt": latest_swap_approval.get("source_alt_command_style_receipt"),
            "source_validation_style": latest_swap_approval.get("source_validation_style"),
            "source_validation_passed": latest_swap_approval.get("source_validation_passed"),
            "candidate_folder": latest_swap_approval.get("candidate_folder"),
            "candidate_runtime_binary_path": latest_swap_approval.get("candidate_runtime_binary_path"),
            "candidate_tokenize_binary_path": latest_swap_approval.get("candidate_tokenize_binary_path"),
            "previous_registered_runtime_path": latest_swap_approval.get("previous_registered_runtime_path"),
            "registered_runtime_changed": latest_swap_approval.get("registered_runtime_changed"),
            "registration_mode": latest_swap_approval.get("registration_mode"),
            "runtime_path_config_updated": latest_swap_approval.get("runtime_path_config_updated"),
            "rollback_metadata_path": latest_swap_approval.get("rollback_metadata_path"),
            "rollback_previous_runtime_path_recorded": latest_swap_approval.get("rollback_previous_runtime_path_recorded"),
            "first_local_response_smoke_allowed_next": latest_swap_approval.get("first_local_response_smoke_allowed_next"),
            "runtime_ready_for_inference": latest_swap_approval.get("runtime_ready_for_inference"),
            "inference_enabled": latest_swap_approval.get("inference_enabled"),
            "chat_enabled": latest_swap_approval.get("chat_enabled"),
            "server_enabled": latest_swap_approval.get("server_enabled"),
            "trusted_memory_write_enabled": latest_swap_approval.get("trusted_memory_write_enabled"),
            "next_safe_action": latest_swap_approval.get("next_safe_action"),
            "final_decision": latest_swap_approval.get("final_decision"),
        } if latest_swap_approval else None,
        "first_local_response_smoke_module_present": exists("engel_ai_first_local_response_smoke.py"),
        "first_local_response_smoke_receipt_count": len(first_smoke_entries),
        "latest_first_local_response_smoke": {
            "receipt_path": latest_first_smoke.get("receipt_path"),
            "source_runtime_swap_approval_receipt": latest_first_smoke.get("source_runtime_swap_approval_receipt"),
            "model_key": latest_first_smoke.get("model_key"),
            "registered_runtime_path": latest_first_smoke.get("registered_runtime_path"),
            "model_file_path": latest_first_smoke.get("model_file_path"),
            "prompt_is_fixed_inert": latest_first_smoke.get("prompt_is_fixed_inert"),
            "user_content_used_as_prompt": latest_first_smoke.get("user_content_used_as_prompt"),
            "n_predict": latest_first_smoke.get("n_predict"),
            "command_executed": latest_first_smoke.get("command_executed"),
            "runtime_process_started": latest_first_smoke.get("runtime_process_started"),
            "runtime_process_exited": latest_first_smoke.get("runtime_process_exited"),
            "exit_code": latest_first_smoke.get("exit_code"),
            "timed_out": latest_first_smoke.get("timed_out"),
            "interrupted": latest_first_smoke.get("interrupted"),
            "orphan_process_detected": latest_first_smoke.get("orphan_process_detected"),
            "output_captured": latest_first_smoke.get("output_captured"),
            "expected_token_seen": latest_first_smoke.get("expected_token_seen"),
            "output_marked_untrusted": latest_first_smoke.get("output_marked_untrusted"),
            "model_output_trusted": latest_first_smoke.get("model_output_trusted"),
            "first_response_smoke_passed": latest_first_smoke.get("first_response_smoke_passed"),
            "first_local_response_smoke_ready": latest_first_smoke.get("first_local_response_smoke_ready"),
            "runtime_ready_for_inference": latest_first_smoke.get("runtime_ready_for_inference"),
            "chat_enabled": latest_first_smoke.get("chat_enabled"),
            "server_enabled": latest_first_smoke.get("server_enabled"),
            "trusted_memory_write_enabled": latest_first_smoke.get("trusted_memory_write_enabled"),
            "next_safe_action": latest_first_smoke.get("next_safe_action"),
            "final_decision": latest_first_smoke.get("final_decision"),
        } if latest_first_smoke else None,
        "first_local_response_smoke_exit_fix_module_present": exists("engel_ai_first_local_response_smoke_exit_fix.py"),
        "first_local_response_smoke_exit_fix_receipt_count": len(exit_fix_entries),
        "latest_first_local_response_smoke_exit_fix": {
            "receipt_path": latest_exit_fix.get("receipt_path"),
            "source_first_local_response_smoke_receipt": latest_exit_fix.get("source_first_local_response_smoke_receipt"),
            "source_failure_reason": latest_exit_fix.get("source_failure_reason"),
            "source_exit_code": latest_exit_fix.get("source_exit_code"),
            "selected_command_style": latest_exit_fix.get("selected_command_style"),
            "selected_command_style_supported": latest_exit_fix.get("selected_command_style_supported"),
            "exit_control_flags": latest_exit_fix.get("exit_control_flags"),
            "model_key": latest_exit_fix.get("model_key"),
            "registered_runtime_path": latest_exit_fix.get("registered_runtime_path"),
            "model_file_path": latest_exit_fix.get("model_file_path"),
            "prompt_is_fixed_inert": latest_exit_fix.get("prompt_is_fixed_inert"),
            "user_content_used_as_prompt": latest_exit_fix.get("user_content_used_as_prompt"),
            "n_predict": latest_exit_fix.get("n_predict"),
            "command_executed": latest_exit_fix.get("command_executed"),
            "runtime_process_started": latest_exit_fix.get("runtime_process_started"),
            "runtime_process_exited": latest_exit_fix.get("runtime_process_exited"),
            "exit_code": latest_exit_fix.get("exit_code"),
            "timed_out": latest_exit_fix.get("timed_out"),
            "interrupted": latest_exit_fix.get("interrupted"),
            "orphan_process_detected": latest_exit_fix.get("orphan_process_detected"),
            "output_captured": latest_exit_fix.get("output_captured"),
            "expected_token_seen": latest_exit_fix.get("expected_token_seen"),
            "disqualifying_interactive_markers_found": latest_exit_fix.get("disqualifying_interactive_markers_found"),
            "output_marked_untrusted": latest_exit_fix.get("output_marked_untrusted"),
            "model_output_trusted": latest_exit_fix.get("model_output_trusted"),
            "first_response_smoke_exit_fix_passed": latest_exit_fix.get("first_response_smoke_exit_fix_passed"),
            "first_response_smoke_passed": latest_exit_fix.get("first_response_smoke_passed"),
            "runtime_ready_for_inference": latest_exit_fix.get("runtime_ready_for_inference"),
            "chat_enabled": latest_exit_fix.get("chat_enabled"),
            "server_enabled": latest_exit_fix.get("server_enabled"),
            "trusted_memory_write_enabled": latest_exit_fix.get("trusted_memory_write_enabled"),
            "next_safe_action": latest_exit_fix.get("next_safe_action"),
            "final_decision": latest_exit_fix.get("final_decision"),
        } if latest_exit_fix else None,
        "first_response_output_filter_tuning_module_present": exists("engel_ai_first_response_output_filter_tuning.py"),
        "first_response_output_filter_tuning_receipt_count": len(filter_tuning_entries),
        "latest_first_response_output_filter_tuning": {
            "receipt_path": latest_filter_tuning.get("receipt_path"),
            "source_exit_fix_receipt": latest_filter_tuning.get("source_exit_fix_receipt"),
            "source_exit_code": latest_filter_tuning.get("source_exit_code"),
            "source_timed_out": latest_filter_tuning.get("source_timed_out"),
            "source_interrupted": latest_filter_tuning.get("source_interrupted"),
            "source_orphan_process_detected": latest_filter_tuning.get("source_orphan_process_detected"),
            "source_expected_token_seen": latest_filter_tuning.get("source_expected_token_seen"),
            "source_output_marked_untrusted": latest_filter_tuning.get("source_output_marked_untrusted"),
            "historical_receipt_modified": latest_filter_tuning.get("historical_receipt_modified"),
            "fatal_marker_types": latest_filter_tuning.get("fatal_marker_types"),
            "suspicious_marker_types": latest_filter_tuning.get("suspicious_marker_types"),
            "benign_marker_types": latest_filter_tuning.get("benign_marker_types"),
            "diagnosis_classification": latest_filter_tuning.get("diagnosis_classification"),
            "filter_tuning_applied": latest_filter_tuning.get("filter_tuning_applied"),
            "historical_first_response_smoke_reclassified_as_passed": latest_filter_tuning.get("historical_first_response_smoke_reclassified_as_passed"),
            "first_response_smoke_passed_after_tuning_preview": latest_filter_tuning.get("first_response_smoke_passed_after_tuning_preview"),
            "runtime_ready_for_inference": latest_filter_tuning.get("runtime_ready_for_inference"),
            "chat_enabled": latest_filter_tuning.get("chat_enabled"),
            "server_enabled": latest_filter_tuning.get("server_enabled"),
            "trusted_memory_write_enabled": latest_filter_tuning.get("trusted_memory_write_enabled"),
            "recommended_next_action": latest_filter_tuning.get("recommended_next_action"),
            "final_decision": latest_filter_tuning.get("final_decision"),
        } if latest_filter_tuning else None,
        "bounded_local_chat_smoke_module_present": exists("engel_ai_bounded_local_chat_smoke.py"),
        "local_chat_panel_bounded_run_enabled": local_chat_panel_bounded_run_enabled,
        "bounded_local_chat_smoke_receipt_count": len(bounded_chat_entries),
        "latest_bounded_local_chat_smoke": {
            "receipt_path": latest_bounded_chat.get("receipt_path"),
            "prior_first_response_smoke_passed": latest_bounded_chat.get("prior_first_response_smoke_passed"),
            "model_key": latest_bounded_chat.get("model_key"),
            "registered_runtime_path": latest_bounded_chat.get("registered_runtime_path"),
            "model_file_path": latest_bounded_chat.get("model_file_path"),
            "prompt_is_fixed_test_prompt": latest_bounded_chat.get("prompt_is_fixed_test_prompt"),
            "user_content_used_as_prompt": latest_bounded_chat.get("user_content_used_as_prompt"),
            "n_predict": latest_bounded_chat.get("n_predict"),
            "command_executed": latest_bounded_chat.get("command_executed"),
            "runtime_process_started": latest_bounded_chat.get("runtime_process_started"),
            "runtime_process_exited": latest_bounded_chat.get("runtime_process_exited"),
            "exit_code": latest_bounded_chat.get("exit_code"),
            "timed_out": latest_bounded_chat.get("timed_out"),
            "interrupted": latest_bounded_chat.get("interrupted"),
            "orphan_process_detected": latest_bounded_chat.get("orphan_process_detected"),
            "output_captured": latest_bounded_chat.get("output_captured"),
            "expected_phrase_seen": latest_bounded_chat.get("expected_phrase_seen"),
            "output_marked_untrusted": latest_bounded_chat.get("output_marked_untrusted"),
            "model_output_trusted": latest_bounded_chat.get("model_output_trusted"),
            "persistent_chat_loop_enabled": latest_bounded_chat.get("persistent_chat_loop_enabled"),
            "server_enabled": latest_bounded_chat.get("server_enabled"),
            "trusted_memory_write_enabled": latest_bounded_chat.get("trusted_memory_write_enabled"),
            "runtime_ready_for_inference": latest_bounded_chat.get("runtime_ready_for_inference"),
            "open_chat_enabled": latest_bounded_chat.get("open_chat_enabled"),
            "bounded_local_chat_smoke_passed": latest_bounded_chat.get("bounded_local_chat_smoke_passed"),
            "next_safe_action": latest_bounded_chat.get("next_safe_action"),
            "final_decision": latest_bounded_chat.get("final_decision"),
        } if latest_bounded_chat else None,
        "local_chat_prompt_draft_module_present": exists("engel_ai_local_chat_prompt_draft.py"),
        "local_chat_prompt_draft_receipt_count": len(prompt_draft_entries),
        "latest_local_chat_prompt_draft": {
            "receipt_path": latest_prompt_draft.get("receipt_path"),
            "prior_bounded_local_chat_smoke_passed": latest_prompt_draft.get("prior_bounded_local_chat_smoke_passed"),
            "model_key": latest_prompt_draft.get("model_key"),
            "registered_runtime_path": latest_prompt_draft.get("registered_runtime_path"),
            "model_file_path": latest_prompt_draft.get("model_file_path"),
            "prompt_length": latest_prompt_draft.get("prompt_length"),
            "prompt_max_length": latest_prompt_draft.get("prompt_max_length"),
            "prompt_source": latest_prompt_draft.get("prompt_source"),
            "prompt_from_file": latest_prompt_draft.get("prompt_from_file"),
            "prompt_from_memory": latest_prompt_draft.get("prompt_from_memory"),
            "prompt_from_model_output": latest_prompt_draft.get("prompt_from_model_output"),
            "hidden_context_added": latest_prompt_draft.get("hidden_context_added"),
            "n_predict": latest_prompt_draft.get("n_predict"),
            "command_executed": latest_prompt_draft.get("command_executed"),
            "runtime_process_started": latest_prompt_draft.get("runtime_process_started"),
            "runtime_process_exited": latest_prompt_draft.get("runtime_process_exited"),
            "exit_code": latest_prompt_draft.get("exit_code"),
            "timed_out": latest_prompt_draft.get("timed_out"),
            "interrupted": latest_prompt_draft.get("interrupted"),
            "orphan_process_detected": latest_prompt_draft.get("orphan_process_detected"),
            "output_captured": latest_prompt_draft.get("output_captured"),
            "output_marked_untrusted": latest_prompt_draft.get("output_marked_untrusted"),
            "model_output_trusted": latest_prompt_draft.get("model_output_trusted"),
            "persistent_chat_loop_enabled": latest_prompt_draft.get("persistent_chat_loop_enabled"),
            "server_enabled": latest_prompt_draft.get("server_enabled"),
            "trusted_memory_write_enabled": latest_prompt_draft.get("trusted_memory_write_enabled"),
            "runtime_ready_for_inference": latest_prompt_draft.get("runtime_ready_for_inference"),
            "open_chat_enabled": latest_prompt_draft.get("open_chat_enabled"),
            "local_chat_prompt_draft_passed": latest_prompt_draft.get("local_chat_prompt_draft_passed"),
            "next_safe_action": latest_prompt_draft.get("next_safe_action"),
            "final_decision": latest_prompt_draft.get("final_decision"),
        } if latest_prompt_draft else None,
        "local_chat_session_draft_module_present": exists("engel_ai_local_chat_session_draft.py"),
        "local_chat_session_draft_receipt_count": len(session_draft_entries),
        "latest_local_chat_session_draft": {
            "receipt_path": latest_session_draft.get("receipt_path"),
            "prior_bounded_local_chat_smoke_passed": latest_session_draft.get("prior_bounded_local_chat_smoke_passed"),
            "prior_local_chat_prompt_draft_passed": latest_session_draft.get("prior_local_chat_prompt_draft_passed"),
            "model_key": latest_session_draft.get("model_key"),
            "registered_runtime_path": latest_session_draft.get("registered_runtime_path"),
            "model_file_path": latest_session_draft.get("model_file_path"),
            "turn_number": latest_session_draft.get("turn_number"),
            "turn_max": latest_session_draft.get("turn_max"),
            "prompt_length": latest_session_draft.get("prompt_length"),
            "prompt_max_length": latest_session_draft.get("prompt_max_length"),
            "prompt_source": latest_session_draft.get("prompt_source"),
            "prompt_from_file": latest_session_draft.get("prompt_from_file"),
            "prompt_from_memory": latest_session_draft.get("prompt_from_memory"),
            "prompt_from_model_output": latest_session_draft.get("prompt_from_model_output"),
            "hidden_context_added": latest_session_draft.get("hidden_context_added"),
            "prior_turns_included_as_prompt_context": latest_session_draft.get("prior_turns_included_as_prompt_context"),
            "n_predict": latest_session_draft.get("n_predict"),
            "command_executed": latest_session_draft.get("command_executed"),
            "runtime_process_started": latest_session_draft.get("runtime_process_started"),
            "runtime_process_exited": latest_session_draft.get("runtime_process_exited"),
            "exit_code": latest_session_draft.get("exit_code"),
            "timed_out": latest_session_draft.get("timed_out"),
            "interrupted": latest_session_draft.get("interrupted"),
            "orphan_process_detected": latest_session_draft.get("orphan_process_detected"),
            "output_captured": latest_session_draft.get("output_captured"),
            "output_marked_untrusted": latest_session_draft.get("output_marked_untrusted"),
            "model_output_trusted": latest_session_draft.get("model_output_trusted"),
            "session_transcript_trusted": latest_session_draft.get("session_transcript_trusted"),
            "automatic_next_turn_enabled": latest_session_draft.get("automatic_next_turn_enabled"),
            "persistent_chat_loop_enabled": latest_session_draft.get("persistent_chat_loop_enabled"),
            "server_enabled": latest_session_draft.get("server_enabled"),
            "trusted_memory_write_enabled": latest_session_draft.get("trusted_memory_write_enabled"),
            "runtime_ready_for_inference": latest_session_draft.get("runtime_ready_for_inference"),
            "open_chat_enabled": latest_session_draft.get("open_chat_enabled"),
            "local_chat_session_draft_turn_passed": latest_session_draft.get("local_chat_session_draft_turn_passed"),
            "next_safe_action": latest_session_draft.get("next_safe_action"),
            "final_decision": latest_session_draft.get("final_decision"),
        } if latest_session_draft else None,
        "local_chat_session_review_module_present": exists("engel_ai_local_chat_session_review.py"),
        "local_chat_session_review_receipt_count": len(session_review_entries),
        "latest_local_chat_session_review": {
            "receipt_path": latest_session_review.get("receipt_path"),
            "source_session_draft_receipt": latest_session_review.get("source_session_draft_receipt"),
            "session_id": latest_session_review.get("session_id"),
            "turn_count_reviewed": latest_session_review.get("turn_count_reviewed"),
            "output_marked_untrusted": latest_session_review.get("output_marked_untrusted"),
            "model_output_trusted": latest_session_review.get("model_output_trusted"),
            "session_transcript_trusted": latest_session_review.get("session_transcript_trusted"),
            "review_output_trusted": latest_session_review.get("review_output_trusted"),
            "trusted_memory_write_enabled": latest_session_review.get("trusted_memory_write_enabled"),
            "approved_memory_write_enabled": latest_session_review.get("approved_memory_write_enabled"),
            "automatic_learning_enabled": latest_session_review.get("automatic_learning_enabled"),
            "runtime_process_started": latest_session_review.get("runtime_process_started"),
            "model_process_started": latest_session_review.get("model_process_started"),
            "eligible_for_memory_candidate_draft": latest_session_review.get("eligible_for_memory_candidate_draft"),
            "next_safe_action": latest_session_review.get("next_safe_action"),
            "final_decision": latest_session_review.get("final_decision"),
        } if latest_session_review else None,
        "local_chat_session_memory_candidate_draft_count": len(session_candidate_entries),
        "latest_local_chat_session_memory_candidate_draft": {
            "draft_path": latest_session_candidate.get("draft_path"),
            "source_session_review_receipt": latest_session_candidate.get("source_session_review_receipt"),
            "source_session_draft_receipt": latest_session_candidate.get("source_session_draft_receipt"),
            "candidate_type": latest_session_candidate.get("candidate_type"),
            "trust_state": latest_session_candidate.get("trust_state"),
            "human_review_required": latest_session_candidate.get("human_review_required"),
            "promoted_to_trusted_memory": latest_session_candidate.get("promoted_to_trusted_memory"),
            "trusted_memory_write_enabled": latest_session_candidate.get("trusted_memory_write_enabled"),
            "approved_memory_write_enabled": latest_session_candidate.get("approved_memory_write_enabled"),
            "model_output_trusted": latest_session_candidate.get("model_output_trusted"),
            "automatic_learning_enabled": latest_session_candidate.get("automatic_learning_enabled"),
            "next_safe_action": latest_session_candidate.get("next_safe_action"),
            "final_decision": latest_session_candidate.get("final_decision"),
        } if latest_session_candidate else None,
        "local_chat_session_memory_candidate_review_write_module_present": exists("engel_ai_local_chat_session_memory_candidate_review_and_approved_write.py"),
        "local_chat_session_memory_candidate_review_receipt_count": len(session_memory_candidate_review_entries),
        "latest_local_chat_session_memory_candidate_review": {
            "receipt_path": latest_session_memory_candidate_review.get("receipt_path"),
            "source_candidate_path": latest_session_memory_candidate_review.get("source_candidate_path"),
            "schema_valid": latest_session_memory_candidate_review.get("schema_valid"),
            "deterministic_guardian_gates_passed": latest_session_memory_candidate_review.get("deterministic_guardian_gates_passed"),
            "approved_memory_write_eligible": latest_session_memory_candidate_review.get("approved_memory_write_eligible"),
            "recommendation": latest_session_memory_candidate_review.get("recommendation"),
            "risk_flags": latest_session_memory_candidate_review.get("risk_flags"),
            "human_approval_required": latest_session_memory_candidate_review.get("human_approval_required"),
            "approval_token_required": latest_session_memory_candidate_review.get("approval_token_required"),
            "candidate_content_obeyed": latest_session_memory_candidate_review.get("candidate_content_obeyed"),
            "review_output_trusted": latest_session_memory_candidate_review.get("review_output_trusted"),
            "runtime_process_started": latest_session_memory_candidate_review.get("runtime_process_started"),
            "model_process_started": latest_session_memory_candidate_review.get("model_process_started"),
            "runtime_ready_for_inference": latest_session_memory_candidate_review.get("runtime_ready_for_inference"),
            "open_chat_enabled": latest_session_memory_candidate_review.get("open_chat_enabled"),
            "final_decision": latest_session_memory_candidate_review.get("final_decision"),
        } if latest_session_memory_candidate_review else None,
        "local_chat_session_approved_memory_write_receipt_count": len(session_approved_memory_write_entries),
        "latest_local_chat_session_approved_memory_write": {
            "receipt_path": latest_session_approved_memory_write.get("receipt_path"),
            "source_candidate_path": latest_session_approved_memory_write.get("source_candidate_path"),
            "source_review_receipt": latest_session_approved_memory_write.get("source_review_receipt"),
            "approved_memory_record_path": latest_session_approved_memory_write.get("approved_memory_record_path"),
            "rollback_metadata_path": latest_session_approved_memory_write.get("rollback_metadata_path"),
            "deterministic_guardian_gates_passed": latest_session_approved_memory_write.get("deterministic_guardian_gates_passed"),
            "approved_memory_write_performed": latest_session_approved_memory_write.get("approved_memory_write_performed"),
            "trusted_memory_write_scope": latest_session_approved_memory_write.get("trusted_memory_write_scope"),
            "trusted_memory_write_enabled_global": latest_session_approved_memory_write.get("trusted_memory_write_enabled_global"),
            "runtime_process_started": latest_session_approved_memory_write.get("runtime_process_started"),
            "model_process_started": latest_session_approved_memory_write.get("model_process_started"),
            "runtime_ready_for_inference": latest_session_approved_memory_write.get("runtime_ready_for_inference"),
            "open_chat_enabled": latest_session_approved_memory_write.get("open_chat_enabled"),
            "final_decision": latest_session_approved_memory_write.get("final_decision"),
        } if latest_session_approved_memory_write else None,
        "approved_local_chat_memory_record_count": len(approved_local_chat_memory_record_entries),
        "latest_approved_local_chat_memory_record": {
            "approved_memory_record_path": approved_local_chat_memory_record_entries[-1].get("approved_memory_record_path"),
            "source_candidate_path": approved_local_chat_memory_record_entries[-1].get("source_candidate_path"),
            "source_review_receipt": approved_local_chat_memory_record_entries[-1].get("source_review_receipt"),
            "approval_basis": approved_local_chat_memory_record_entries[-1].get("approval_basis"),
            "source_model_output_trusted": approved_local_chat_memory_record_entries[-1].get("source_model_output_trusted"),
            "candidate_content_obeyed": approved_local_chat_memory_record_entries[-1].get("candidate_content_obeyed"),
        } if approved_local_chat_memory_record_entries else None,
        "local_approved_memory_readback_module_present": exists("engel_ai_local_approved_memory_readback.py"),
        "local_approved_memory_readback_receipt_count": len(local_approved_memory_readback_receipt_entries),
        "latest_local_approved_memory_readback": {
            "receipt_path": latest_local_approved_readback.get("receipt_path"),
            "approved_record_path": latest_local_approved_readback.get("approved_record_path"),
            "approved_record_schema_valid": latest_local_approved_readback.get("approved_record_schema_valid"),
            "rollback_metadata_present": latest_local_approved_readback.get("rollback_metadata_present"),
            "source_write_receipt_present": latest_local_approved_readback.get("source_write_receipt_present"),
            "global_trusted_memory": latest_local_approved_readback.get("global_trusted_memory"),
            "used_as_hidden_prompt_context": latest_local_approved_readback.get("used_as_hidden_prompt_context"),
            "automatic_context_injection_enabled": latest_local_approved_readback.get("automatic_context_injection_enabled"),
            "memory_write_performed": latest_local_approved_readback.get("memory_write_performed"),
            "runtime_process_started": latest_local_approved_readback.get("runtime_process_started"),
            "model_process_started": latest_local_approved_readback.get("model_process_started"),
            "runtime_ready_for_inference": latest_local_approved_readback.get("runtime_ready_for_inference"),
            "open_chat_enabled": latest_local_approved_readback.get("open_chat_enabled"),
            "final_decision": latest_local_approved_readback.get("final_decision"),
        } if latest_local_approved_readback else None,
        "local_approved_memory_readback_available": local_approved_memory_readback_available,
        "local_approved_memory_context_preview_module_present": exists("engel_ai_local_approved_memory_context_preview.py"),
        "local_approved_memory_context_preview_receipt_count": len(local_approved_memory_context_preview_receipt_entries),
        "latest_local_approved_memory_context_preview": {
            "receipt_path": latest_local_memory_context_preview.get("receipt_path"),
            "context_preview_path": latest_local_memory_context_preview.get("context_preview_path"),
            "approved_record_count_included": latest_local_memory_context_preview.get("approved_record_count_included"),
            "visible_context_only": latest_local_memory_context_preview.get("visible_context_only"),
            "hidden_prompt_context": latest_local_memory_context_preview.get("hidden_prompt_context"),
            "automatic_context_injection_enabled": latest_local_memory_context_preview.get("automatic_context_injection_enabled"),
            "global_trusted_memory": latest_local_memory_context_preview.get("global_trusted_memory"),
            "memory_write_performed": latest_local_memory_context_preview.get("memory_write_performed"),
            "runtime_process_started": latest_local_memory_context_preview.get("runtime_process_started"),
            "model_process_started": latest_local_memory_context_preview.get("model_process_started"),
            "runtime_ready_for_inference": latest_local_memory_context_preview.get("runtime_ready_for_inference"),
            "open_chat_enabled": latest_local_memory_context_preview.get("open_chat_enabled"),
            "final_decision": latest_local_memory_context_preview.get("final_decision"),
        } if latest_local_memory_context_preview else None,
        "local_approved_memory_context_run_receipt_count": len(local_approved_memory_context_run_receipt_entries),
        "latest_local_approved_memory_context_run": {
            "receipt_path": latest_local_memory_context_run.get("receipt_path"),
            "context_preview_path": latest_local_memory_context_run.get("context_preview_path"),
            "constructed_prompt_path": latest_local_memory_context_run.get("constructed_prompt_path"),
            "exit_code": latest_local_memory_context_run.get("exit_code"),
            "timed_out": latest_local_memory_context_run.get("timed_out"),
            "interrupted": latest_local_memory_context_run.get("interrupted"),
            "orphan_process_detected": latest_local_memory_context_run.get("orphan_process_detected"),
            "output_captured": latest_local_memory_context_run.get("output_captured"),
            "output_marked_untrusted": latest_local_memory_context_run.get("output_marked_untrusted"),
            "model_output_trusted": latest_local_memory_context_run.get("model_output_trusted"),
            "memory_write_performed": latest_local_memory_context_run.get("memory_write_performed"),
            "runtime_ready_for_inference": latest_local_memory_context_run.get("runtime_ready_for_inference"),
            "open_chat_enabled": latest_local_memory_context_run.get("open_chat_enabled"),
            "local_approved_memory_context_run_passed": latest_local_memory_context_run.get("local_approved_memory_context_run_passed"),
            "final_decision": latest_local_memory_context_run.get("final_decision"),
        } if latest_local_memory_context_run else None,
        "local_approved_memory_context_preview_available": local_approved_memory_context_preview_available,
        "local_approved_memory_context_run_passed": local_approved_memory_context_run_passed,
        "approved_local_memory_visible_context_run_available": local_approved_memory_context_run_passed,
        "local_open_chat_supervised_run_module_present": exists("engel_ai_local_open_chat_supervised_run.py"),
        "local_open_chat_supervised_run_receipt_count": len(local_open_chat_supervised_receipt_entries),
        "latest_local_open_chat_supervised_run": {
            "receipt_path": latest_open_chat_supervised.get("receipt_path"),
            "session_turn_number": latest_open_chat_supervised.get("session_turn_number"),
            "exit_code": latest_open_chat_supervised.get("exit_code"),
            "timed_out": latest_open_chat_supervised.get("timed_out"),
            "interrupted": latest_open_chat_supervised.get("interrupted"),
            "orphan_process_detected": latest_open_chat_supervised.get("orphan_process_detected"),
            "output_captured": latest_open_chat_supervised.get("output_captured"),
            "output_marked_untrusted": latest_open_chat_supervised.get("output_marked_untrusted"),
            "model_output_trusted": latest_open_chat_supervised.get("model_output_trusted"),
            "open_chat_enabled": latest_open_chat_supervised.get("open_chat_enabled"),
            "open_chat_scope": latest_open_chat_supervised.get("open_chat_scope"),
            "chat_enabled": latest_open_chat_supervised.get("chat_enabled"),
            "chat_scope": latest_open_chat_supervised.get("chat_scope"),
            "persistent_chat_loop_enabled": latest_open_chat_supervised.get("persistent_chat_loop_enabled"),
            "server_enabled": latest_open_chat_supervised.get("server_enabled"),
            "provider_api_enabled": latest_open_chat_supervised.get("provider_api_enabled"),
            "trusted_memory_write_enabled": latest_open_chat_supervised.get("trusted_memory_write_enabled"),
            "runtime_ready_for_inference": latest_open_chat_supervised.get("runtime_ready_for_inference"),
            "local_open_chat_supervised_turn_passed": latest_open_chat_supervised.get("local_open_chat_supervised_turn_passed"),
            "final_decision": latest_open_chat_supervised.get("final_decision"),
        } if latest_open_chat_supervised else None,
        "local_open_chat_supervised_run_available": local_open_chat_supervised_run_available,
        "persistent_chat_supervised_runtime_plan_module_present": exists("engel_ai_persistent_chat_supervised_runtime_plan.py"),
        "persistent_chat_supervised_runtime_plan_receipt_count": len(persistent_chat_plan_entries),
        "latest_persistent_chat_supervised_runtime_plan": {
            "receipt_path": latest_persistent_chat_plan.get("receipt_path"),
            "persistent_chat_enabled": latest_persistent_chat_plan.get("persistent_chat_enabled"),
            "persistent_runtime_enabled": latest_persistent_chat_plan.get("persistent_runtime_enabled"),
            "true_long_lived_model_process_enabled": latest_persistent_chat_plan.get("true_long_lived_model_process_enabled"),
            "recommended_next_mode": latest_persistent_chat_plan.get("recommended_next_mode"),
            "recommended_next_phase": latest_persistent_chat_plan.get("recommended_next_phase"),
            "server_enabled": latest_persistent_chat_plan.get("server_enabled"),
            "provider_api_enabled": latest_persistent_chat_plan.get("provider_api_enabled"),
            "startup_auto_load_enabled": latest_persistent_chat_plan.get("startup_auto_load_enabled"),
            "background_daemon_enabled": latest_persistent_chat_plan.get("background_daemon_enabled"),
            "trusted_memory_write_enabled": latest_persistent_chat_plan.get("trusted_memory_write_enabled"),
            "approved_memory_write_enabled": latest_persistent_chat_plan.get("approved_memory_write_enabled"),
            "runtime_ready_for_inference": latest_persistent_chat_plan.get("runtime_ready_for_inference"),
            "final_decision": latest_persistent_chat_plan.get("final_decision"),
        } if latest_persistent_chat_plan else None,
        "persistent_chat_requested": bool(latest_persistent_chat_plan and latest_persistent_chat_plan.get("user_requested_persistent_chat") is True),
        "persistent_chat_enabled": False,
        "persistent_runtime_enabled": False,
        "persistent_chat_plan_available": persistent_chat_plan_available,
        "recommended_persistent_next_mode": "supervised_persistent_gui_session_repeated_bounded_calls" if persistent_chat_plan_available else None,
        "gui_local_ai_bounded_run_section_present": gui_state["local_ai_bounded_run_section_present"],
        "gui_local_ai_human_prompt_draft_section_present": gui_state["local_ai_human_prompt_draft_section_present"],
        "gui_local_ai_session_draft_section_present": gui_state["local_ai_session_draft_section_present"],
        "gui_local_ai_supervised_open_chat_section_present": gui_state["local_ai_supervised_open_chat_section_present"],
        "gui_local_ai_persistent_chat_plan_section_present": gui_state["local_ai_persistent_chat_plan_section_present"],
        "open_chat_scope": "supervised_local_gui_session_only" if local_open_chat_supervised_run_available else None,
        "chat_scope": "supervised_local_gui_session_only" if local_open_chat_supervised_run_available else None,
        "hidden_prompt_context_enabled": False,
        "global_trusted_memory_enabled": False,
        "automatic_context_injection_enabled": False,
        "candidate_runtime_ready_for_swap_review": candidate_ready_for_swap_review,
        "first_local_response_smoke_allowed_next": first_local_response_smoke_allowed_next,
        "first_local_response_smoke_passed": first_local_response_smoke_passed,
        "first_local_response_smoke_ready": first_local_response_smoke_passed,
        "first_local_response_smoke_exit_fix_passed": first_local_response_smoke_exit_fix_passed,
        "first_response_output_filter_tuning_passed": first_response_output_filter_tuning_passed,
        "bounded_local_chat_smoke_passed": bounded_local_chat_smoke_passed,
        "local_chat_panel_bounded_run_enabled": local_chat_panel_bounded_run_enabled,
        "local_chat_prompt_draft_passed": local_chat_prompt_draft_passed,
        "bounded_human_prompt_enabled": bounded_human_prompt_enabled,
        "local_chat_session_draft_passed": local_chat_session_draft_passed,
        "bounded_session_draft_enabled": bounded_session_draft_enabled,
        "local_chat_session_review_available": local_chat_session_review_available,
        "local_chat_session_review_passed": local_chat_session_review_passed,
        "local_chat_session_memory_candidate_draft_available": local_chat_session_memory_candidate_draft_available,
        "local_chat_session_memory_candidate_review_available": local_chat_session_memory_candidate_review_available,
        "local_chat_session_approved_memory_records_available": local_chat_session_approved_memory_records_available,
        "runtime_no_generation_check_ready": no_generation_ready,
        "runtime_ready_for_inference": False,
        "normal_inference_enabled": False,
        "chat_enabled": local_open_chat_supervised_run_available,
        "open_chat_enabled": local_open_chat_supervised_run_available,
        "persistent_chat_loop_enabled": False,
        "server_enabled": False,
        "trusted_memory_write_enabled": False,
    }


def collect_libraries() -> dict[str, Any]:
    plan = read_json(NON_MODEL_PLAN)
    folder_layout = plan.get("folder_layout") if isinstance(plan.get("folder_layout"), dict) else {}
    categories = plan.get("categories") if isinstance(plan.get("categories"), list) else []
    category_rows: list[dict[str, Any]] = []
    for category in categories:
        if not isinstance(category, dict):
            continue
        quarantine = str(category.get("expected_quarantine_folder", "") or "")
        approved = str(category.get("expected_approved_folder", "") or "")
        category_rows.append(
            {
                "category_name": category.get("category_name", "unknown"),
                "category_slug": category.get("category_slug", "unknown"),
                "import_status": category.get("import_status", "unknown"),
                "trust_status": category.get("trust_status", "untrusted_until_human_review"),
                "quarantine_folder": shallow_count(quarantine, None),
                "approved_folder": shallow_count(approved, None),
                "human_approval_required": True,
                "auto_index_allowed": False,
                "recursive_scan_enabled": False,
            }
        )
    return {
        "section": "Library Readiness",
        "status": "READY_FOR_LIBRARY_REVIEW",
        "non_model_library_plan_present": NON_MODEL_PLAN.exists(),
        "chat_export_intake_available": exists("engel_chat_export_intake.py"),
        "manual_model_intake_evaluator_available": exists("engel_manual_model_intake_evaluator.py") or exists("tools\\verify_engel_manual_model_intake_evaluator.py"),
        "library_root": folder_layout.get("library_root", "unknown"),
        "quarantine_root": folder_layout.get("quarantine_imports_root", "unknown"),
        "approved_root": folder_layout.get("approved_library_root", "unknown"),
        "categories": category_rows,
        "auto_indexing_enabled": False,
        "recursive_scan_enabled": False,
        "download_enabled": False,
        "execute_document_content_enabled": False,
        "trusted_memory_write_enabled": False,
        "manual_approval_required": True,
    }


def collect_remote_worker() -> dict[str, Any]:
    link_report = "reports\\codex_bridge\\ENGEL_REMOTE_WORKER_PHASE_12_ENGEL_CONTROLLED_PHONE_LINK_MANAGER.md"
    link_report_text = read_bounded(link_report).lower()
    phase8_report = "reports\\codex_bridge\\ENGEL_REMOTE_WORKER_PHASE_8_REAL_ANDROID_LAN_SMOKE.md"
    post_manager_live_smoke_done = "live phone smoke after link manager: passed" in link_report_text
    return {
        "section": "Remote Worker Status",
        "status": "READY_FOR_REMOTE_WORKER_SMOKE",
        "link_manager_present": exists("engel_remote_worker_link_manager.py"),
        "link_manager_report_present": exists(link_report),
        "lan_pairing_present": exists("engel_remote_worker_lan_pairing.py"),
        "communication_queen_assignment_producer_present": exists("engel_communication_queen_assignment_producer.py"),
        "result_intake_present": exists("engel_remote_worker_result_intake.py"),
        "claim_lock_verifier_present": exists("tools\\verify_engel_remote_worker_claim_lock.py"),
        "latest_phone_smoke_report_present": exists(phase8_report),
        "latest_phone_smoke_report": phase8_report,
        "live_phone_smoke_after_link_manager": post_manager_live_smoke_done,
        "live_phone_smoke_after_link_manager_pending": not post_manager_live_smoke_done,
        "phone_output_trust": "untrusted_review_required",
        "auto_apply": False,
        "lan_receiver_auto_start": False,
        "auto_worker_auto_start": False,
        "notes": [
            "Engel may manage the dedicated phone link visibly.",
            "Phone output remains untrusted and review-required.",
            "No LAN receiver or Auto Worker mode starts from this readiness command.",
        ],
    }


def phase_status(name: str, module_path: str, report_path: str, verifier_path: str) -> dict[str, Any]:
    module_present = True if not module_path else exists(module_path)
    report_present = exists(report_path)
    verifier_present = exists(verifier_path)
    if module_present and report_present and verifier_present:
        status = "READY"
    elif "Rollback" in name:
        status = "BLOCKED"
    else:
        status = "MISSING"
    return {
        "phase": name,
        "status": status,
        "module_present": module_present,
        "report_present": report_present,
        "verifier_present": verifier_present,
        "module_path": module_path or None,
        "report_path": report_path,
        "verifier_path": verifier_path,
    }


def collect_code_companion() -> dict[str, Any]:
    try:
        import engel_global_password_gate

        password_status = engel_global_password_gate.global_password_gate_status()
    except Exception:
        password_status = {"configured": False, "config_valid": False}
    phase_rows = [phase_status(*phase) for phase in CODE_COMPANION_PHASES]
    return {
        "section": "Code Companion Status",
        "status": "BLOCKED_ITEMS_PRESENT",
        "phases": phase_rows,
        "protected_apply_fail_closed": True,
        "protected_apply_blocks_ai_setup": False,
        "password_gate_config_valid": bool(password_status.get("config_valid") is True),
        "password_gate_configured": bool(password_status.get("configured") is True),
        "review_surface_present": exists("tools\\engel_code_companion_review_surface.py"),
        "patch_class_allowlist_present": exists("engel_code_companion_patch_class_allowlist.py"),
        "rollback_blocked_until_real_apply_backup_exists": not exists("engel_code_companion_protected_rollback.py"),
        "auto_apply": False,
        "trusted_memory_write": False,
    }


def collect_safety() -> dict[str, Any]:
    companion = collect_code_companion()
    return {
        "section": "Safety / Blocked Items",
        "status": "BLOCKED_ITEMS_PRESENT",
        "hermes_rejected": True,
        "wsl_disabled": True,
        "docker_linux_disabled": True,
        "provider_cloud_disabled": True,
        "trusted_memory_writes_disabled": True,
        "source_mutation_disabled": True,
        "route_mutation_disabled": True,
        "queue_mutation_disabled": True,
        "model_download_install_disabled": True,
        "inference_disabled": True,
        "outside_ai_boundary_active": exists("tools\\verify_engel_outside_ai_boundary.py"),
        "password_gate_config_valid": companion["password_gate_config_valid"],
        "password_gate_configured_for_protected_apply": companion["password_gate_configured"],
        "protected_patch_apply_fail_closed": True,
        "protected_patch_apply_blocks_ai_setup": False,
        "model_auto_load_enabled": False,
        "provider_api_enabled": False,
        "background_workers_enabled": False,
        "auto_apply_enabled": False,
    }


def next_actions() -> list[dict[str, Any]]:
    dry_run_entries = runtime_dry_run_entries_by_model_key()
    latest_no_generation = latest_no_generation_load_check()
    latest_compatibility_probe = latest_llama_cpp_compatibility_probe()
    latest_compatibility_matrix = latest_llama_cpp_compatibility_matrix()
    latest_runtime_swap_plan = latest_llama_cpp_runtime_swap_plan()
    latest_candidate_validation = latest_llama_cpp_runtime_candidate_validation()
    latest_failure_diagnosis = latest_runtime_candidate_failure_diagnosis()
    latest_replay = latest_runtime_candidate_validation_replay()
    latest_alt_style = latest_runtime_candidate_alt_command_style()
    latest_swap_approval = latest_llama_cpp_runtime_swap_approval()
    latest_first_smoke = latest_first_local_response_smoke()
    latest_exit_fix = latest_first_local_response_smoke_exit_fix()
    latest_filter_tuning = latest_first_response_output_filter_tuning()
    latest_bounded_chat = latest_bounded_local_chat_smoke()
    latest_prompt_draft = latest_local_chat_prompt_draft()
    latest_session_draft = latest_local_chat_session_draft()
    latest_session_review = latest_local_chat_session_review()
    latest_session_candidate = latest_local_chat_session_memory_candidate_draft()
    latest_session_memory_candidate_review = latest_local_chat_session_memory_candidate_review()
    approved_local_chat_memory_record_entries = approved_local_chat_memory_records()
    latest_local_approved_readback = latest_local_approved_memory_readback()
    latest_local_memory_context_preview = latest_local_approved_memory_context_preview()
    latest_local_memory_context_run = latest_local_approved_memory_context_run()
    latest_open_chat_supervised = latest_local_open_chat_supervised_run()
    latest_persistent_chat_plan = latest_persistent_chat_supervised_runtime_plan()
    gui_state = gui_marker_state()
    local_chat_panel_bounded_run_enabled = bool(
        LOCAL_CHAT_PANEL_ENABLE_REPORT.exists()
        and exists("tools\\verify_engel_ai_local_chat_panel_enable_bounded_run.py")
        and gui_state["local_ai_bounded_run_section_present"]
    )
    compatibility_probe_passed = bool(latest_compatibility_probe and latest_compatibility_probe.get("candidate_probe_passed") is True)
    path_config = runtime_path_config()
    runtime_path = path_config.get("runtime_binary_path") if isinstance(path_config.get("runtime_binary_path"), str) else None
    runtime_binary_present = bool(runtime_path and Path(runtime_path).exists() and Path(runtime_path).is_file())
    if latest_persistent_chat_plan and latest_persistent_chat_plan.get("persistent_chat_supervised_runtime_plan_version") == "1":
        first_title = "ENGEL_AI_PERSISTENT_CHAT_SUPERVISED_SESSION_V1"
        first_reason = "Persistent chat has a deterministic supervised runtime plan. The next safe step is a supervised persistent GUI session using repeated bounded calls; no long-lived model process, server/provider behavior, startup auto-load, background daemon, or memory write is enabled."
    elif (
        latest_open_chat_supervised
        and gui_state["local_ai_supervised_open_chat_section_present"]
        and latest_open_chat_supervised.get("local_open_chat_supervised_turn_passed") is True
    ):
        first_title = "ENGEL_AI_PERSISTENT_CHAT_SUPERVISED_RUNTIME_PLAN_V1"
        first_reason = "Supervised local GUI chat has completed one bounded turn with output marked untrusted. Persistent chat, server/provider behavior, startup auto-load, and memory writes remain disabled."
    elif latest_local_memory_context_run and latest_local_memory_context_run.get("local_approved_memory_context_run_passed") is True:
        first_title = "ENGEL_AI_LOCAL_MEMORY_AWARE_CHAT_DRAFT_V1"
        first_reason = "One approval-gated visible approved-memory context run passed with output marked untrusted. Hidden context, automatic injection, open chat, and memory writes remain disabled."
    elif latest_local_memory_context_preview and latest_local_memory_context_preview.get("local_approved_memory_context_preview_version") == "1":
        first_title = "Run one approved context prompt or continue local approved memory review"
        first_reason = "A visible approved local memory context preview exists. It is bounded, not hidden prompt context, not automatically injected, and not global trusted memory."
    elif latest_local_approved_readback and latest_local_approved_readback.get("local_approved_memory_readback_version") == "1":
        first_title = "ENGEL_AI_LOCAL_APPROVED_MEMORY_CONTEXT_PREVIEW_V1"
        first_reason = "Approved local chat memory readback exists as bounded status/evidence only. Records are not global trusted memory and are not injected into hidden prompts."
    elif approved_local_chat_memory_record_entries:
        first_title = "ENGEL_AI_LOCAL_APPROVED_MEMORY_READBACK_V1"
        first_reason = "An approved local chat memory record exists under the bounded phase folder. Source model output remains untrusted, trusted memory targets are untouched, and the next safe step is readback verification."
    elif latest_session_memory_candidate_review and latest_session_memory_candidate_review.get("approved_memory_write_eligible") is True:
        first_title = "write approved local chat memory record if deterministic gates pass"
        first_reason = "A deterministic review found an eligible untrusted local chat memory candidate. No human approval token is required, but deterministic Guardian gates and rollback metadata remain mandatory."
    elif latest_session_candidate and latest_session_candidate.get("trust_state") == "untrusted":
        first_title = "ENGEL_AI_LOCAL_CHAT_SESSION_MEMORY_CANDIDATE_REVIEW_AND_APPROVED_WRITE_V1"
        first_reason = "An untrusted memory-candidate draft exists from local session review. The next safe step is deterministic Guardian review and approved local chat memory record write if eligible; no trusted-memory target is touched."
    elif latest_session_review and latest_session_review.get("local_chat_session_review_version") == "1":
        first_title = "ENGEL_AI_LOCAL_CHAT_SESSION_MEMORY_CANDIDATE_REVIEW_V1"
        first_reason = "A bounded local session review exists as untrusted evidence. The next safe step is human review of the candidate draft path or continuing bounded session draft; no memory has been promoted."
    elif latest_session_draft and latest_session_draft.get("local_chat_session_draft_turn_passed") is True:
        first_title = "ENGEL_AI_LOCAL_CHAT_PANEL_SESSION_REVIEW_V1"
        first_reason = "One approval-gated bounded session draft turn passed with output and transcript marked untrusted. Open chat, automatic continuation, persistent chat, runtime_ready_for_inference, server mode, and trusted-memory writes remain disabled."
    elif latest_prompt_draft and latest_prompt_draft.get("local_chat_prompt_draft_passed") is True:
        first_title = "ENGEL_AI_LOCAL_CHAT_PANEL_SESSION_DRAFT_V1"
        first_reason = "One approval-gated bounded human prompt draft passed with output marked untrusted. Open chat, persistent chat, runtime_ready_for_inference, server mode, and trusted-memory writes remain disabled."
    elif local_chat_panel_bounded_run_enabled and latest_bounded_chat and latest_bounded_chat.get("bounded_local_chat_smoke_passed") is True:
        first_title = "ENGEL_AI_LOCAL_CHAT_PANEL_HUMAN_PROMPT_DRAFT_V1"
        first_reason = "The Companion Local AI panel can run one approval-gated bounded tiny_seed smoke and is ready for one short human prompt draft/review gate. Output remains untrusted and open chat, runtime_ready_for_inference, server mode, and trusted-memory writes remain disabled."
    elif latest_bounded_chat and latest_bounded_chat.get("bounded_local_chat_smoke_passed") is True:
        first_title = "ENGEL_AI_LOCAL_CHAT_PANEL_ENABLE_BOUNDED_RUN_V1"
        first_reason = "The bounded tiny_seed local chat-style smoke passed with output marked untrusted. The Companion Local AI panel may show the bounded evidence, while open chat, runtime_ready_for_inference, server mode, and trusted-memory writes remain disabled."
    elif latest_bounded_chat:
        first_title = "Review bounded local chat smoke logs or adjust bounded command style"
        first_reason = "A bounded local chat smoke receipt exists, but it did not pass cleanly; keep the GUI run path fail-closed and review the bounded untrusted logs."
    elif (
        latest_filter_tuning
        and latest_filter_tuning.get("diagnosis_classification") == "clean_single_turn_exit_but_filter_too_strict"
        and latest_filter_tuning.get("first_response_smoke_passed_after_tuning_preview") is True
    ):
        first_title = "ENGEL_AI_BOUNDED_LOCAL_CHAT_SMOKE_V1"
        first_reason = "The output filter tuning receipt reclassified the clean single-turn exit-fix evidence as a valid first-response smoke while preserving output distrust and keeping inference, chat, server mode, and trusted-memory writes disabled."
    elif latest_filter_tuning and latest_filter_tuning.get("diagnosis_classification") == "ambiguous_needs_replay":
        first_title = "ENGEL_AI_FIRST_RESPONSE_FILTER_TUNED_REPLAY_V1"
        first_reason = "Output filter tuning found ambiguous historical evidence; an explicit future replay is required before considering the first-response smoke passed."
    elif latest_filter_tuning:
        first_title = "Adjust bounded command style or choose another runtime candidate"
        first_reason = "Output filter tuning confirmed unsafe or failed first-response evidence; keep local response smoke fail-closed."
    elif latest_exit_fix and latest_exit_fix.get("first_response_smoke_exit_fix_passed") is True:
        first_title = "ENGEL_AI_BOUNDED_LOCAL_CHAT_SMOKE_V1"
        first_reason = "A bounded tiny_seed exit-fix smoke completed cleanly with output marked untrusted; broader inference, chat, server mode, and trusted-memory writes remain disabled."
    elif latest_exit_fix:
        first_title = "ENGEL_AI_FIRST_RESPONSE_OUTPUT_FILTER_TUNING_V1"
        first_reason = "The exit-fix smoke completed cleanly but was failed by the older interactive marker classifier; tune output classification before any replay or chat step."
    elif latest_first_smoke and latest_first_smoke.get("first_response_smoke_passed") is True:
        first_title = "ENGEL_AI_BOUNDED_LOCAL_CHAT_SMOKE_V1"
        first_reason = "One bounded tiny_seed first-response smoke passed; its output remains untrusted and broader inference, chat, server mode, and trusted-memory writes remain disabled."
    elif latest_first_smoke:
        if latest_first_smoke.get("interrupted") is True or latest_first_smoke.get("exit_code") == 130:
            first_title = "ENGEL_AI_FIRST_LOCAL_RESPONSE_SMOKE_EXIT_FIX_V1"
            first_reason = "The first-response smoke produced bounded untrusted output but required interruption; run the explicit exit-fix phase to select a stricter non-interactive command style."
        else:
            first_title = "Review first local response smoke logs or adjust bounded command style"
            first_reason = "A first local response smoke receipt exists, but it did not pass cleanly; review the bounded receipt/logs without promoting output or enabling chat."
    elif latest_swap_approval and latest_swap_approval.get("first_local_response_smoke_allowed_next") is True:
        first_title = "ENGEL_AI_FIRST_LOCAL_RESPONSE_SMOKE_V1"
        first_reason = "A protected llama.cpp runtime swap approval recorded the validated candidate path for future smoke review; inference, chat, server mode, and trusted-memory writes remain disabled."
    elif latest_swap_approval:
        first_title = "Fix runtime swap approval blocker or choose another candidate"
        first_reason = "A runtime swap approval receipt exists, but it did not approve first local response smoke as the next action."
    elif (latest_no_generation and latest_no_generation.get("no_generation_load_check_passed") is True) or compatibility_probe_passed:
        first_title = "ENGEL_AI_FIRST_LOCAL_RESPONSE_SMOKE_V1"
        first_reason = "A no-generation-compatible local runtime candidate exited cleanly; the next explicit phase may request one bounded local response while normal inference remains disabled by default."
    elif latest_alt_style and latest_alt_style.get("candidate_runtime_ready_for_swap_review") is True:
        first_title = "ENGEL_AI_LLAMA_CPP_RUNTIME_SWAP_APPROVAL_V1"
        first_reason = "A tokenizer-only alternate command-style validation passed; the registered runtime is still unchanged and requires a separate swap approval phase before any future chat or inference work."
    elif latest_replay and latest_replay.get("candidate_runtime_ready_for_swap_review") is True:
        first_title = "ENGEL_AI_LLAMA_CPP_RUNTIME_SWAP_APPROVAL_V1"
        first_reason = "A bounded replay with corrected interpretation logic passed; the registered runtime is still unchanged and requires a separate swap approval phase."
    elif latest_alt_style:
        first_title = "Try another alternate command style or runtime candidate; do not swap"
        first_reason = "An alternate command-style receipt exists, but the candidate is not ready for swap review under strict no-generation output rules."
    elif latest_replay:
        first_title = "Try alternate command style or different runtime candidate; do not swap"
        first_reason = "A bounded replay exists, but the candidate is not ready for swap review under strict no-generation output rules."
    elif latest_candidate_validation and latest_candidate_validation.get("candidate_runtime_ready_for_swap_review") is True:
        first_title = "ENGEL_AI_LLAMA_CPP_RUNTIME_SWAP_APPROVAL_V1"
        first_reason = "A manually placed runtime candidate passed bounded tiny_seed no-generation validation; the registered runtime is still unchanged and requires a separate swap approval phase."
    elif latest_failure_diagnosis and latest_failure_diagnosis.get("diagnosis_classification") == "contradictory_receipt_state":
        first_title = "ENGEL_AI_RUNTIME_CANDIDATE_VALIDATION_REPLAY_V1"
        first_reason = "A diagnosis found a contradictory candidate validation receipt; future validation logic is corrected, but a separate approved replay is required before swap review."
    elif latest_failure_diagnosis:
        first_title = "Try another runtime candidate or alternate safe model-info/tokenize path"
        first_reason = "A candidate failure diagnosis exists and keeps runtime readiness fail-closed."
    elif latest_candidate_validation:
        first_title = "Try another manually placed runtime candidate or inspect validation logs"
        first_reason = "A runtime candidate validation receipt exists, but no candidate is ready for swap review."
    elif latest_runtime_swap_plan:
        first_title = "Manually place alternate llama.cpp Windows runtime candidate, then run ENGEL_AI_LLAMA_CPP_RUNTIME_CANDIDATE_VALIDATION_V1"
        first_reason = "A runtime swap plan exists because the current llama.cpp build has no clean tiny_seed no-generation model-load exit; manual placement under approved E/F candidate roots is required before validation."
    elif latest_compatibility_probe or latest_compatibility_matrix:
        first_title = "Use compatibility matrix to choose alternate llama.cpp build or safe model-info/tokenize-only mode"
        first_reason = "A llama.cpp compatibility matrix exists, but no tiny_seed no-generation candidate probe has passed cleanly."
    elif latest_no_generation:
        latest_version = latest_no_generation.get("no_generation_load_check_version", "unknown")
        if str(latest_version) == "4":
            first_title = "Review V4 minimal exit probe diagnosis; consider llama.cpp binary compatibility or alternate runtime build"
        elif str(latest_version) == "3":
            first_title = "Review V3 diagnosis logs and runtime/model compatibility"
        else:
            first_title = f"Fix runtime/model compatibility from no-generation V{latest_version} receipt/log"
        first_reason = "A no-generation load check receipt exists but did not pass; use the bounded receipt/logs to repair local runtime compatibility."
    elif dry_run_entries and all(entry.get("runtime_dry_run_ready") is True for entry in dry_run_entries.values()):
        first_title = "Offline no-generation load check phase"
        first_reason = "Runtime dry-run wiring is ready; the next explicit phase may check loading without generation while keeping inference disabled."
    elif runtime_binary_present:
        first_title = "Rerun ENGEL_AI_OFFLINE_RUNTIME_DRY_RUN_V1"
        first_reason = "A local runtime binary path is configured; rerun runtime dry-run previews so receipts reflect the local path without executing it."
    elif path_config.get("runtime_path_approved") is True:
        first_title = "Restore or replace configured local runtime binary"
        first_reason = "A runtime path was recorded, but the binary is no longer present; place the local runtime binary back under the approved Engel runtime root."
    elif dry_run_entries:
        first_title = "Place llama.cpp binary under an approved runtime root"
        first_reason = "Runtime dry-run receipts exist, but no configured local runtime binary is present; E: is preferred and F: is an approved alternate runtime root."
    else:
        first_title = "ENGEL_AI_OFFLINE_RUNTIME_DRY_RUN_V1"
        first_reason = "Approved model folders can proceed to a future explicit offline runtime dry-run phase; inference and auto-load remain disabled."
    return [
        {
            "rank": 1,
            "title": first_title,
            "status": "MANUAL_REQUIRED",
            "reason": first_reason,
        },
        {
            "rank": 2,
            "title": "Manual model folder placement/check",
            "status": "MANUAL_REQUIRED",
            "reason": "Use bounded presence checks only; do not load or infer from model files.",
        },
        {
            "rank": 3,
            "title": "Non-model library approved-material intake",
            "status": "READY_FOR_LIBRARY_REVIEW",
            "reason": "Approved library material remains manual, untrusted until reviewed, and not auto-indexed.",
        },
        {
            "rank": 4,
            "title": "Remote Worker Link Manager live phone smoke",
            "status": "READY_FOR_REMOTE_WORKER_SMOKE",
            "reason": "The link manager exists; a visible start/pair/status/check/stop smoke is the safe next phone step.",
        },
        {
            "rank": 5,
            "title": "Package live EXEs after stable readiness work",
            "status": "MANUAL_REQUIRED",
            "reason": "Packaging has been intentionally skipped and should happen after this readiness layer stabilizes.",
        },
        {
            "rank": 6,
            "title": "Optional main-GUI integration for readiness dashboard",
            "status": "MANUAL_REQUIRED",
            "reason": "The standalone dashboard can be promoted to the main GUI later without changing runtime safety.",
        },
        {
            "rank": 7,
            "title": "Configure password/protected-action gate only when ready for real protected apply",
            "status": "BLOCKED",
            "reason": "This does not block AI setup; it only blocks real protected patch application.",
        },
    ]


def collect_core_ai_setup() -> dict[str, Any]:
    runtime = collect_runtime_boundaries()
    return {
        "section": "Core AI Setup",
        "status": "NOT_READY_FOR_INFERENCE",
        "ready_for_manual_model_intake": True,
        "ready_for_library_review": True,
        "ready_for_remote_worker_smoke": True,
        "blocked_items_present": True,
        "inference_enabled": False,
        "model_auto_load_enabled": False,
        "provider_api_enabled": False,
        "runtime_contract_present": runtime["offline_model_runtime_contract_present"],
        "seed_llm_contract_present": runtime["offline_seed_llm_contract_present"],
        "conclusion": "Engel is ready for read-only/manual AI setup steps, not model inference.",
    }


def readiness_payload() -> dict[str, Any]:
    core = collect_core_ai_setup()
    models = collect_models()
    runtime = collect_runtime_boundaries()
    libraries = collect_libraries()
    remote_worker = collect_remote_worker()
    code_companion = collect_code_companion()
    safety = collect_safety()
    data_sources = [
        {"path": path, "present": exists(path)}
        for path in KNOWN_DATA_SOURCES
    ]
    return {
        "dashboard_version": "1",
        "created_by": "Engel AI Runtime Readiness",
        "mode": "read_only_readiness_reporting",
        "overall_readiness": [
            "NOT_READY_FOR_INFERENCE",
            "READY_FOR_MANUAL_MODEL_INTAKE",
            "READY_FOR_LIBRARY_REVIEW",
            "READY_FOR_REMOTE_WORKER_SMOKE",
            "BLOCKED_ITEMS_PRESENT",
        ],
        "safety_flags": {
            "inference_enabled": False,
            "model_auto_load_enabled": False,
            "provider_api_enabled": False,
            "download_enabled": False,
            "package_install_enabled": False,
            "trusted_memory_write_enabled": False,
            "source_mutation_enabled": False,
            "route_mutation_enabled": False,
            "queue_mutation_enabled": False,
            "background_workers_enabled": False,
            "auto_apply_enabled": False,
        },
        "core_ai_setup": core,
        "model_inventory": models,
        "runtime_boundaries": runtime,
        "library_readiness": libraries,
        "remote_worker_status": remote_worker,
        "code_companion_status": code_companion,
        "safety_blocked_items": safety,
        "next_safe_actions": next_actions(),
        "data_sources_inspected": data_sources,
    }


def render_status(payload: dict[str, Any] | None = None) -> str:
    data = payload or readiness_payload()
    core = data["core_ai_setup"]
    runtime_config = data["runtime_boundaries"]["runtime_path_config_status"]
    lines = [
        "Engel AI Runtime Readiness Dashboard V1",
        "Mode: read-only readiness reporting",
        "",
        "Overall readiness:",
    ]
    lines.extend(f"- {state}" for state in data["overall_readiness"])
    lines.extend(
        [
            "",
            f"Conclusion: {core['conclusion']}",
            f"inference_enabled: {data['safety_flags']['inference_enabled']}",
            f"model_auto_load_enabled: {data['safety_flags']['model_auto_load_enabled']}",
            f"provider_api_enabled: {data['safety_flags']['provider_api_enabled']}",
            f"download_enabled: {data['safety_flags']['download_enabled']}",
            f"trusted_memory_write_enabled: {data['safety_flags']['trusted_memory_write_enabled']}",
            f"preferred_runtime_root: {data['runtime_boundaries']['preferred_runtime_root']}",
            f"alternate_runtime_root: {data['runtime_boundaries']['alternate_runtime_root']}",
            f"expansion_library_root: {data['runtime_boundaries']['expansion_library_root']}",
            f"configured_runtime_binary_path: {runtime_config['runtime_binary_path']}",
            f"runtime_binary_present: {runtime_config['runtime_binary_present']}",
            f"runtime_no_generation_check_ready: {data['runtime_boundaries']['runtime_no_generation_check_ready']}",
            f"runtime_ready_for_inference: {data['runtime_boundaries']['runtime_ready_for_inference']}",
            f"chat_enabled: {data['runtime_boundaries']['chat_enabled']}",
            f"first_local_response_smoke_allowed_next: {data['runtime_boundaries']['first_local_response_smoke_allowed_next']}",
            f"first_local_response_smoke_passed: {data['runtime_boundaries']['first_local_response_smoke_passed']}",
            f"first_local_response_smoke_ready: {data['runtime_boundaries']['first_local_response_smoke_ready']}",
            f"first_local_response_smoke_exit_fix_passed: {data['runtime_boundaries']['first_local_response_smoke_exit_fix_passed']}",
            f"first_response_output_filter_tuning_passed: {data['runtime_boundaries']['first_response_output_filter_tuning_passed']}",
            f"bounded_local_chat_smoke_passed: {data['runtime_boundaries']['bounded_local_chat_smoke_passed']}",
            f"local_chat_panel_bounded_run_enabled: {data['runtime_boundaries']['local_chat_panel_bounded_run_enabled']}",
            f"local_chat_prompt_draft_passed: {data['runtime_boundaries']['local_chat_prompt_draft_passed']}",
            f"bounded_human_prompt_enabled: {data['runtime_boundaries']['bounded_human_prompt_enabled']}",
            f"local_chat_session_draft_passed: {data['runtime_boundaries']['local_chat_session_draft_passed']}",
            f"bounded_session_draft_enabled: {data['runtime_boundaries']['bounded_session_draft_enabled']}",
            f"local_chat_session_review_passed: {data['runtime_boundaries']['local_chat_session_review_passed']}",
            f"local_chat_session_review_available: {data['runtime_boundaries']['local_chat_session_review_available']}",
            f"local_chat_session_memory_candidate_draft_available: {data['runtime_boundaries']['local_chat_session_memory_candidate_draft_available']}",
            f"local_chat_session_memory_candidate_review_available: {data['runtime_boundaries']['local_chat_session_memory_candidate_review_available']}",
            f"local_chat_session_approved_memory_records_available: {data['runtime_boundaries']['local_chat_session_approved_memory_records_available']}",
            f"approved_local_chat_memory_record_count: {data['runtime_boundaries']['approved_local_chat_memory_record_count']}",
            f"local_approved_memory_readback_available: {data['runtime_boundaries']['local_approved_memory_readback_available']}",
            f"local_approved_memory_context_preview_available: {data['runtime_boundaries']['local_approved_memory_context_preview_available']}",
            f"local_approved_memory_context_run_passed: {data['runtime_boundaries']['local_approved_memory_context_run_passed']}",
            f"local_open_chat_supervised_run_available: {data['runtime_boundaries']['local_open_chat_supervised_run_available']}",
            f"persistent_chat_plan_available: {data['runtime_boundaries']['persistent_chat_plan_available']}",
            f"recommended_persistent_next_mode: {data['runtime_boundaries']['recommended_persistent_next_mode']}",
            f"gui_local_ai_bounded_run_section_present: {data['runtime_boundaries']['gui_local_ai_bounded_run_section_present']}",
            f"gui_local_ai_supervised_open_chat_section_present: {data['runtime_boundaries']['gui_local_ai_supervised_open_chat_section_present']}",
            f"gui_local_ai_persistent_chat_plan_section_present: {data['runtime_boundaries']['gui_local_ai_persistent_chat_plan_section_present']}",
            f"open_chat_scope: {data['runtime_boundaries']['open_chat_scope']}",
            f"chat_scope: {data['runtime_boundaries']['chat_scope']}",
            f"global_trusted_memory_enabled: {data['runtime_boundaries']['global_trusted_memory_enabled']}",
            f"hidden_prompt_context_enabled: {data['runtime_boundaries']['hidden_prompt_context_enabled']}",
            f"automatic_context_injection_enabled: {data['runtime_boundaries']['automatic_context_injection_enabled']}",
            "",
            "Next safe action: " + data["next_safe_actions"][0]["title"],
        ]
    )
    return "\n".join(lines) + "\n"


def render_model_summary(payload: dict[str, Any] | None = None) -> str:
    data = payload or readiness_payload()
    lines = ["Engel AI Model Readiness", ""]
    for model in data["model_inventory"]["expected_tiers"]:
        lines.append(
            f"- {model['tier']}: {model['model_name']} / {model['status']} / path: {model['expected_path']} / "
            f"intake={model['model_intake_receipt_present']} / dry_run_eligible={model['approved_for_runtime_dry_run']} / "
            f"runtime_dry_run_ready={model['runtime_dry_run_ready']} / runtime_ready={model['runtime_ready']} / auto_load={model['auto_load_enabled']} / "
            f"inference={model['inference_enabled']} / download={model['download_enabled']}"
        )
    return "\n".join(lines) + "\n"


def render_library_summary(payload: dict[str, Any] | None = None) -> str:
    data = payload or readiness_payload()
    libraries = data["library_readiness"]
    lines = [
        "Engel Library Readiness",
        "",
        f"status: {libraries['status']}",
        f"auto_indexing_enabled: {libraries['auto_indexing_enabled']}",
        f"recursive_scan_enabled: {libraries['recursive_scan_enabled']}",
        f"download_enabled: {libraries['download_enabled']}",
        f"trusted_memory_write_enabled: {libraries['trusted_memory_write_enabled']}",
        "",
        "Categories:",
    ]
    for category in libraries["categories"]:
        lines.append(
            f"- {category['category_name']}: import_status={category['import_status']} / "
            f"quarantine_exists={category['quarantine_folder']['exists']} / approved_exists={category['approved_folder']['exists']}"
        )
    return "\n".join(lines) + "\n"


def render_safety_summary(payload: dict[str, Any] | None = None) -> str:
    data = payload or readiness_payload()
    safety = data["safety_blocked_items"]
    lines = ["Engel AI Runtime Safety", ""]
    for key in [
        "hermes_rejected",
        "wsl_disabled",
        "docker_linux_disabled",
        "provider_cloud_disabled",
        "trusted_memory_writes_disabled",
        "source_mutation_disabled",
        "route_mutation_disabled",
        "queue_mutation_disabled",
        "model_download_install_disabled",
        "inference_disabled",
        "outside_ai_boundary_active",
        "password_gate_configured_for_protected_apply",
        "protected_patch_apply_fail_closed",
    ]:
        lines.append(f"- {key}: {safety[key]}")
    return "\n".join(lines) + "\n"


def render_remote_worker_summary(payload: dict[str, Any] | None = None) -> str:
    data = payload or readiness_payload()
    remote = data["remote_worker_status"]
    lines = ["Engel Remote Worker Readiness", ""]
    for key in [
        "link_manager_present",
        "lan_pairing_present",
        "communication_queen_assignment_producer_present",
        "result_intake_present",
        "claim_lock_verifier_present",
        "latest_phone_smoke_report_present",
        "live_phone_smoke_after_link_manager_pending",
        "phone_output_trust",
        "auto_apply",
    ]:
        lines.append(f"- {key}: {remote[key]}")
    return "\n".join(lines) + "\n"


def render_code_companion_summary(payload: dict[str, Any] | None = None) -> str:
    data = payload or readiness_payload()
    companion = data["code_companion_status"]
    lines = [
        "Engel Code Companion Readiness",
        "",
        f"protected_apply_fail_closed: {companion['protected_apply_fail_closed']}",
        f"protected_apply_blocks_ai_setup: {companion['protected_apply_blocks_ai_setup']}",
        f"password_gate_config_valid: {companion['password_gate_config_valid']}",
        f"password_gate_configured: {companion['password_gate_configured']}",
        f"auto_apply: {companion['auto_apply']}",
        "",
        "Phases:",
    ]
    for phase in companion["phases"]:
        lines.append(f"- {phase['phase']}: {phase['status']}")
    return "\n".join(lines) + "\n"


def render_next_summary(payload: dict[str, Any] | None = None) -> str:
    data = payload or readiness_payload()
    lines = ["Engel AI Next Safe Actions", ""]
    for action in data["next_safe_actions"]:
        lines.append(f"{action['rank']}. {action['title']} [{action['status']}]")
        lines.append(f"   {action['reason']}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Engel AI Runtime Readiness Dashboard V1")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ["status", "json", "models", "libraries", "safety", "remote-worker", "code-companion", "next"]:
        subparsers.add_parser(command)
    args = parser.parse_args(argv)
    payload = readiness_payload()
    if args.command == "status":
        print(render_status(payload), end="")
    elif args.command == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif args.command == "models":
        print(render_model_summary(payload), end="")
    elif args.command == "libraries":
        print(render_library_summary(payload), end="")
    elif args.command == "safety":
        print(render_safety_summary(payload), end="")
    elif args.command == "remote-worker":
        print(render_remote_worker_summary(payload), end="")
    elif args.command == "code-companion":
        print(render_code_companion_summary(payload), end="")
    elif args.command == "next":
        print(render_next_summary(payload), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
