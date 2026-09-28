from __future__ import annotations

import hashlib
import importlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


_file = globals().get("__file__")
if not _file or not isinstance(_file, str) or _file.startswith("<"):
    APP_ROOT = Path.cwd()
else:
    try:
        APP_ROOT = Path(_file).resolve().parents[1]
    except (OSError, ValueError, IndexError):
        APP_ROOT = Path.cwd()
ENGEL_APP = APP_ROOT / "engel_app.py"
CONFIG_PATH = APP_ROOT / "memory" / "LESSON_CANDIDATE_REVIEW_V1.json"
MANIFEST_PATH = APP_ROOT / "memory" / "ROUTE_VERIFICATION_SET_V1.json"
COMMANDS_PATH = APP_ROOT / "memory" / "ENGEL_COMMANDS.md"
CHECKLIST_PATH = APP_ROOT / "memory" / "STANDARD_VERIFIER_CHECKLIST_V1.md"
PROJECT_MEMORY_INDEX_PATH = APP_ROOT / "memory" / "PROJECT_MEMORY_INDEX_V2V.md"
REPORT_DIR = APP_ROOT / "reports" / "lesson_candidates"
REPORT_GLOB = "lesson_candidates_review_*.md"

STANDARD_VERIFIER = "tools\\verify_lesson_candidate_review.py"
STANDARD_VERIFIERS = [
    "tools\\verify_hive_mind_worker_ants.py",
    "tools\\verify_colony_routes.py",
    "tools\\verify_swarm_trails_preview.py",
    "tools\\verify_colony_autonomy_ladder.py",
    "tools\\verify_colony_proposal_autonomy.py",
    "tools\\verify_lesson_candidate_review.py",
    "tools\\verify_colony_simulation_contract.py",
    "tools\\verify_colony_mycelium_layer_contract.py",
]
MATRIX_ENTRIES = {
    "lesson candidates status": "READ_ONLY_REVIEW_ONLY_STATUS",
    "lesson candidates readiness status": "READ_ONLY_STATUS_ONLY_NO_WRITE",
    "lesson candidates review": "READ_ONLY_REVIEW_ONLY_LOCAL_ONLY_NO_WRITE",
    "lesson candidates review APPROVE_REPORT": "APPROVE_REPORT_REPORT_ONLY_LOCAL_ONLY",
    "living learning status": "READ_ONLY_STATUS_ONLY_NO_WRITE",
    "lesson candidates apply": "FUTURE_APPROVAL_GATED_LESSON_APPLY_NOT_IMPLEMENTED",
    "lesson candidates apply APPROVE": "FUTURE_APPROVAL_GATED_LESSON_APPLY_NOT_IMPLEMENTED",
    "lesson candidates review APPROVE_APPLY": "FUTURE_APPROVAL_GATED_LESSON_APPLY_NOT_IMPLEMENTED",
    "lesson candidates rollback": "FUTURE_ROLLBACK_NOT_IMPLEMENTED",
}
ROUTES = {
    "lesson candidates status": "# Lesson Candidates Status",
    "lesson candidates review": "# Lesson Candidates Review",
}
READINESS_ROUTE = "lesson candidates readiness status"
LIVING_ROUTE = "living learning status"
CF_SNAPSHOT_ROUTES = [
    READINESS_ROUTE,
    "lesson candidates status",
    "lesson candidates review",
    "route regression status",
    "verification set status",
]
CL_SNAPSHOT_ROUTES = [
    LIVING_ROUTE,
    READINESS_ROUTE,
    "lesson candidates status",
    "lesson candidates review",
    "route regression status",
    "verification set status",
    "colony simulation status",
    "colony simulation contract",
]
EXPECTED_CG_ROUTE_CLASSIFICATIONS = {
    "lesson candidates status": "read-only/no-write",
    "lesson candidates review": "read-only/no-write",
    READINESS_ROUTE: "read-only/status-only/no-write",
    "lesson candidates review APPROVE_REPORT": "explicit report-only markdown under reports\\lesson_candidates\\",
}
EXPECTED_FUTURE_ABSENT_ROUTES = [
    "lesson candidates apply",
    "lesson candidates apply APPROVE",
    "lesson candidates review APPROVE_APPLY",
    "lesson candidates rollback",
    "candidate creation route",
]
ABSENT_APPLY_ROUTES = [
    "lesson candidates apply",
    "lesson candidates apply APPROVE",
    "lesson candidates review APPROVE_APPLY",
    "lesson candidates rollback",
]
REQUIRED_OUTPUT_TOKENS = [
    "READ_ONLY",
    "REVIEW_ONLY",
    "REPORT_ONLY",
    "UNTRUSTED_CANDIDATES",
    "NO_TRUSTED_WRITE",
    "NO_APPLY",
    "NO_SOURCE_EDIT",
    "NO_QUEUE_MUTATION",
    "NO_DIGEST_WRITE",
    "NO_ALIVE_STATE_WRITE",
    "NO_PROVIDER_CALL",
    "NO_BACKGROUND_WORKER",
    "NO_AUTONOMY",
]
REQUIRED_READINESS_TOKENS = [
    "READ_ONLY",
    "STATUS_ONLY",
    "NO_REPORT_GENERATION",
    "NO_VERIFIER_EXECUTION",
    "NO_CANDIDATE_CREATION",
    "NO_APPLY",
    "NO_TRUSTED_WRITE",
    "NO_SOURCE_EDIT",
    "NO_QUEUE_MUTATION",
    "NO_DIGEST_WRITE",
    "NO_ALIVE_STATE_WRITE",
    "NO_PROVIDER_CALL",
    "NO_BACKGROUND_WORKER",
    "NO_AUTONOMY",
]
REQUIRED_LIVING_TOKENS = [
    "READ_ONLY",
    "STATUS_ONLY",
    "NO_REPORT_GENERATION",
    "NO_VERIFIER_EXECUTION",
    "NO_CANDIDATE_CREATION",
    "NO_APPLY",
    "NO_ROLLBACK",
    "NO_TRUSTED_WRITE",
    "NO_SOURCE_EDIT",
    "NO_QUEUE_MUTATION",
    "NO_DIGEST_WRITE",
    "NO_ALIVE_STATE_WRITE",
    "NO_PROVIDER_CALL",
    "NO_BACKGROUND_WORKER",
    "NO_AUTONOMY",
]
CW_CONSOLIDATION_CHECKPOINT = "V2APP_CW_ENGEL_LIVING_SYSTEMS_CONSOLIDATION_AUDIT"
CX_DRIFT_GUARD_CHECKPOINT = "V2APP_CX_ENGEL_LIVING_SYSTEMS_DRIFT_GUARD"
CW_SURFACE_ROUTES = {
    "proposal_autonomy": [
        "colony proposal status",
        "colony proposal contract",
        "colony proposal preview",
        "colony proposal preview APPROVE_REPORT",
    ],
    "lesson_candidate_learning": [
        "lesson candidates status",
        "lesson candidates review",
        "lesson candidates readiness status",
        "lesson candidates review APPROVE_REPORT",
    ],
    "colony_simulation": [
        "colony simulation status",
        "colony simulation contract",
    ],
    "living_learning": [
        "living learning status",
    ],
    "mycelium_layer": [
        "colony mycelium status",
        "colony mycelium contract",
    ],
}
CW_SAFE_PATH_PHRASES = [
    "observe",
    "summarize",
    "review untrusted candidates",
    "create explicit report-only artifacts only through APPROVE_REPORT",
    "run verifiers externally",
    "require human approval before any future trusted writeback",
    "no autonomous mutation path",
]
CW_FORBIDDEN_ACTIONS = [
    "trusted-memory writes",
    "source edits",
    "route mutations",
    "queue mutations",
    "digest/history writes",
    "ALIVE_STATE writes",
    "provider/API/network calls",
    "live research or internet behavior",
    "background workers",
    "autonomous loops",
    "runtime autonomy",
    "Level 2 runtime",
    "old-provider/local endpoint paths",
]
CW_DOC_PHRASES = [
    "proposal autonomy",
    "lesson candidate learning",
    "colony simulation",
    "living-learning status",
    "mycelium readiness",
    "colony proposal status",
    "colony proposal contract",
    "colony proposal preview",
    "colony proposal preview APPROVE_REPORT",
    "proposal candidates remain untrusted",
    "lesson candidates status",
    "lesson candidates review",
    "lesson candidates readiness status",
    "lesson candidates review APPROVE_REPORT",
    "trusted apply remains absent",
    "rollback remains absent",
    "candidate creation remains absent",
    "future apply metadata remains design/verifier-only",
    "colony simulation status",
    "colony simulation contract",
    "simulation preview remains absent",
    "simulation report remains absent",
    "simulation runtime remains absent",
    "simulation autonomy remains absent",
    "living learning status",
    "read-only/status-only/no-write",
    "no report generation",
    "no verifier execution",
    "no candidate creation",
    "no apply/rollback",
    "colony mycelium status",
    "colony mycelium contract",
    "no signal propagation runtime",
    "no mycelium preview/report/APPROVE_REPORT/candidate routes",
    "structural analogy rule remains enforced",
]
REPORT_TOKENS = REQUIRED_OUTPUT_TOKENS + [
    "APPROVE_REPORT",
    "report-only artifact",
    "candidates are untrusted",
    "all required candidate categories are untrusted",
    "no trusted-memory write",
    "no lesson apply",
    "no source edit",
    "no queue mutation",
    "no digest/history write",
    "no ALIVE_STATE write",
    "no provider/API/network behavior",
    "Older manual memory commands were not invoked",
]
EXPECTED_CANDIDATE_CATEGORIES = {
    "memory hygiene candidate",
    "documentation alignment candidate",
    "verifier improvement candidate",
    "command/route clarity candidate",
    "safety guardrail candidate",
    "stale-risk candidate",
    "future feature candidate",
}
EXPECTED_ALLOWED_OUTPUTS = {
    "review_only_cli_text",
    "APPROVE_REPORT_report_only_markdown",
}
REQUIRED_BLOCKED_OUTPUTS = {
    "trusted_memory_writes",
    "LEARNING_LOG_writes",
    "learning_apply",
    "source_edits",
    "queue_mutation",
    "digest_history_writes",
    "alive_state_writes",
    "proposal_archive_or_reject_mutation",
    "route_matrix_mutation",
}
REQUIRED_APPROVAL_CONTRACT_KEYS = {
    "review_without_approval",
    "report_with_APPROVE_REPORT",
    "trusted_memory_write_requires_future_contract",
    "learning_apply_requires_future_contract",
    "source_edits_require_codex_or_user_approval",
    "queue_mutation_requires_future_explicit_gate",
}
REQUIRED_FUTURE_APPLY_TOKENS = {
    "APPROVE_LESSON_APPLY",
    "HUMAN_APPROVED",
    "VERIFIER_PASSED",
    "TRUSTED_WRITE_ALLOWED",
}
EXPECTED_FUTURE_CANDIDATE_SOURCES = {
    "reports\\lesson_candidates\\lesson_candidates_review_*.md",
}
EXPECTED_FUTURE_ALLOWLISTED_TARGET_TYPES = {
    "project_memory_index_entry",
    "documentation_note",
    "verifier_checklist_note",
    "command_help_text_note",
}
EXPECTED_FUTURE_TARGET_ALLOWLIST = {
    "project_memory_index_entry": {
        "allowed_paths": {"memory\\PROJECT_MEMORY_INDEX_V2V.md"},
        "maximum_write_scope": "single bounded project memory index entry only; no rewrite of unrelated sections",
    },
    "documentation_note": {
        "allowed_paths": {"memory\\ENGEL_COMMANDS.md"},
        "maximum_write_scope": "single bounded documentation note only; no broad command documentation rewrite",
    },
    "verifier_checklist_note": {
        "allowed_paths": {"memory\\STANDARD_VERIFIER_CHECKLIST_V1.md"},
        "maximum_write_scope": "single bounded verifier checklist note only; no verifier behavior change",
    },
    "command_help_text_note": {
        "allowed_paths": {"memory\\ENGEL_COMMANDS.md"},
        "maximum_write_scope": "single bounded command help text note only; no route behavior change",
    },
}
REQUIRED_FUTURE_REFUSAL_CONDITIONS = {
    "verifier_fails",
    "candidate_source_missing",
    "candidate_not_from_approved_report_only_artifact",
    "candidate_not_human_approved",
    "candidate_category_unknown",
    "approval_tokens_missing",
    "target_type_unknown",
    "target_write_path_not_allowlisted",
    "target_would_edit_source_code",
    "target_would_mutate_route_matrix_without_separate_route_contract",
    "target_would_mutate_queues",
    "target_would_write_digest_history",
    "target_would_write_ALIVE_STATE",
    "target_would_modify_provider_config",
    "target_would_modify_autonomy_flags",
    "target_would_modify_simulation_runtime_config",
    "runtime_autonomy_enabled",
    "runtime_autonomy_enabled_true",
    "runtime_level_2_enabled_without_later_explicit_contract",
    "runtime_level_2_enabled_true_without_later_explicit_contract",
    "STAGED_DRAFT_ACTIVE_true",
}
REQUIRED_TARGET_ALLOWLIST_REFUSAL_CONDITIONS = REQUIRED_FUTURE_REFUSAL_CONDITIONS - {
    "runtime_autonomy_enabled",
    "runtime_level_2_enabled_without_later_explicit_contract",
}
EXPECTED_FUTURE_AUDIT_LOCATION = "reports\\lesson_apply_audits"
REQUIRED_FUTURE_AUDIT_FIELDS = {
    "audit_id",
    "timestamp",
    "candidate_report_source",
    "candidate_id",
    "candidate_category",
    "human_approval_token",
    "verifier_status",
    "target_type",
    "target_path",
    "before_snapshot",
    "proposed_change_summary",
    "after_snapshot",
    "diff_summary",
    "refusal_conditions_checked",
    "allowed_target_confirmed",
    "forbidden_target_confirmed_absent",
    "manual_memory_command_not_used",
    "trusted_write_scope",
    "rollback_note",
    "final_status",
}
REQUIRED_FUTURE_AUDIT_TOKENS = {
    "BEFORE_SNAPSHOT_RECORDED",
    "AFTER_SNAPSHOT_RECORDED",
    "DIFF_SUMMARY_RECORDED",
    "ALLOWLIST_TARGET_CONFIRMED",
    "FORBIDDEN_TARGETS_REJECTED",
    "MANUAL_MEMORY_COMMAND_NOT_USED",
    "HUMAN_APPROVED",
    "VERIFIER_PASSED",
    "TRUSTED_WRITE_ALLOWED",
}
REQUIRED_FUTURE_AUDIT_REFUSAL_CONDITIONS = {
    "missing_before_snapshot",
    "missing_after_snapshot",
    "missing_diff_summary",
    "missing_candidate_report_source",
    "missing_candidate_id",
    "missing_human_approval_token",
    "verifier_did_not_pass",
    "target_type_not_allowlisted",
    "target_path_not_allowlisted",
    "target_touches_forbidden_target",
    "manual_memory_command_detected",
    "runtime_autonomy_enabled",
    "runtime_level_2_enabled_without_later_explicit_contract",
    "STAGED_DRAFT_ACTIVE_true",
}
REQUIRED_FUTURE_CANDIDATE_FIELDS = {
    "candidate_id",
    "candidate_schema_version",
    "candidate_category",
    "candidate_source_report",
    "candidate_created_at",
    "candidate_summary",
    "candidate_rationale",
    "proposed_target_type",
    "proposed_target_path",
    "proposed_change_type",
    "proposed_change_summary",
    "risk_level",
    "refusal_conditions",
    "required_approval_tokens",
    "verifier_requirements",
    "trust_status",
}
REQUIRED_FUTURE_TRUST_STATUS = {
    "UNTRUSTED_CANDIDATE",
    "REVIEW_ONLY",
    "NOT_APPLIED",
    "NOT_TRUSTED_MEMORY",
}
REQUIRED_FUTURE_CANDIDATE_IDENTITY_TOKENS = {
    "CANDIDATE_ID_REQUIRED",
    "CANDIDATE_SCHEMA_VERSION_REQUIRED",
    "SOURCE_REPORT_REQUIRED",
    "CATEGORY_ALLOWLIST_REQUIRED",
    "TARGET_ALLOWLIST_REQUIRED",
    "TRUST_STATUS_UNTRUSTED",
    "NOT_APPLIED",
    "NOT_TRUSTED_MEMORY",
}
REQUIRED_FUTURE_CANDIDATE_REFUSAL_CONDITIONS = {
    "missing_candidate_id",
    "duplicate_candidate_id",
    "missing_source_report",
    "source_report_not_under_reports_lesson_candidates",
    "unknown_category",
    "missing_proposed_target_type",
    "proposed_target_type_not_allowlisted",
    "missing_proposed_target_path",
    "proposed_target_path_not_allowlisted",
    "missing_trust_status",
    "trust_status_is_not_untrusted",
    "missing_approval_tokens",
    "missing_verifier_requirements",
    "proposed_change_touches_forbidden_target",
    "proposed_change_requires_source_edit",
    "proposed_change_requires_queue_mutation",
    "proposed_change_requires_digest_history_write",
    "proposed_change_requires_ALIVE_STATE_write",
    "proposed_change_invokes_older_manual_memory_commands",
}
REQUIRED_FUTURE_ROLLBACK_REQUIREMENTS = {
    "rollback_plan_required",
    "rollback_scope",
    "rollback_target_path",
    "rollback_snapshot_source",
    "rollback_human_approval_required",
    "rollback_verifier_required",
    "rollback_audit_required",
    "rollback_status",
    "rollback_must_not_touch_forbidden_targets",
}
REQUIRED_FUTURE_ROLLBACK_TOKENS = {
    "ROLLBACK_PLAN_REQUIRED",
    "ROLLBACK_SCOPE_RECORDED",
    "ROLLBACK_SNAPSHOT_REQUIRED",
    "ROLLBACK_HUMAN_APPROVAL_REQUIRED",
    "ROLLBACK_VERIFIER_REQUIRED",
    "ROLLBACK_AUDIT_REQUIRED",
    "ROLLBACK_FORBIDDEN_TARGETS_REJECTED",
}
REQUIRED_FUTURE_REFUSAL_CATEGORIES = {
    "identity_schema_refusal",
    "source_report_refusal",
    "approval_token_refusal",
    "verifier_status_refusal",
    "target_allowlist_refusal",
    "forbidden_target_refusal",
    "manual_memory_command_refusal",
    "autonomy_flag_refusal",
    "staged_draft_refusal",
    "provider_network_refusal",
    "source_edit_refusal",
    "queue_digest_ALIVE_STATE_refusal",
    "simulation_runtime_refusal",
}
REQUIRED_FUTURE_REFUSAL_TOKENS = {
    "REFUSE_MISSING_CANDIDATE_ID",
    "REFUSE_MISSING_SOURCE_REPORT",
    "REFUSE_UNAPPROVED_CANDIDATE",
    "REFUSE_VERIFIER_NOT_PASSED",
    "REFUSE_TARGET_NOT_ALLOWLISTED",
    "REFUSE_FORBIDDEN_TARGET",
    "REFUSE_MANUAL_MEMORY_COMMAND",
    "REFUSE_AUTONOMY_ENABLED",
    "REFUSE_STAGED_DRAFT_ACTIVE",
    "REFUSE_PROVIDER_OR_NETWORK",
    "REFUSE_SOURCE_EDIT",
    "REFUSE_QUEUE_DIGEST_ALIVE_WRITE",
    "REFUSE_SIMULATION_RUNTIME",
}
REQUIRED_FORBIDDEN_FUTURE_APPLY_TARGETS = {
    "source_code",
    "route_matrix_mutation_without_separate_route_contract",
    "queues",
    "digest_history",
    "ALIVE_STATE",
    "provider_config",
    "autonomy_flags",
    "simulation_runtime_config",
}
REQUIRED_FUTURE_VERIFIER_EXPECTATIONS = {
    "apply_route_absent_until_separate_contract",
    "approval_tokens_required_exactly",
    "candidate_source_report_only_artifact_required",
    "candidate_category_must_be_known",
    "target_path_must_be_allowlisted",
    "before_after_audit_report_required",
    "manual_memory_commands_not_invoked",
    "no_source_code_write",
    "no_queue_write",
    "no_digest_history_write",
    "no_ALIVE_STATE_write",
    "runtime_autonomy_disabled",
    "runtime_level_2_disabled_unless_later_contract",
    "STAGED_DRAFT_ACTIVE_false",
}
CK_PREFLIGHT_CHECKPOINT = "V2APP_CK_FUTURE_LESSON_APPLY_DRY_RUN_PREFLIGHT_VERIFIER"
CK_PREFLIGHT_REQUIRED_CHECKS = {
    "candidate_identity_schema_metadata",
    "report_only_candidate_source_requirements",
    "target_allowlist_metadata",
    "before_after_audit_contract_metadata",
    "rollback_refusal_contract_metadata",
    "future_approval_token_requirements",
    "absent_apply_rollback_candidate_creation_and_dry_run_routes",
    "active_lesson_route_source_slice_guards",
}
CK_PREFLIGHT_MUST_NOT = {
    "apply",
    "write_trusted_memory",
    "create_candidates",
    "mutate_queues",
    "edit_source",
    "write_digest_history",
    "write_ALIVE_STATE",
    "run_providers",
    "call_manual_memory_commands",
    "enable_autonomy",
}
CK_PREFLIGHT_SOURCE_REQUIREMENTS = {
    "source_must_be_report_only": True,
    "source_root": "reports\\lesson_candidates",
    "source_glob": "reports\\lesson_candidates\\lesson_candidates_review_*.md",
    "source_must_not_be_trusted_memory": True,
    "source_must_not_be_generated_by_apply": True,
    "source_must_not_be_generated_by_rollback": True,
}
CK_ABSENT_DRY_RUN_ROUTES = [
    "lesson candidates apply dry-run",
    "lesson candidates apply dry run",
    "lesson candidates dry-run apply",
    "lesson candidates dry run apply",
    "lesson candidates apply preflight",
    "lesson candidates preflight apply",
    "dry-run apply route",
]
CK_DOC_PHRASES = [
    "CK dry-run preflight",
    "verifier-only",
    "no dry-run route exists",
    "trusted apply remains unimplemented",
    "rollback remains unimplemented",
    "candidate creation remains unimplemented",
    "no write behavior is enabled",
]
CM_LIVING_CLASSIFICATION_PHRASES = [
    "read-only",
    "status-only",
    "no-write",
    "no report generation",
    "no verifier execution",
    "no candidate creation",
    "no apply",
    "no rollback",
]
CM_LIVING_SUMMARY_PHRASES = [
    "proposal readiness",
    "lesson candidate readiness",
    "future trusted apply readiness",
    "colony simulation readiness",
    "current safe learning path",
    "forbidden actions",
    "next human-approved growth step",
]
CM_FORBIDDEN_AVAILABILITY_PHRASES = [
    "trusted apply remains absent",
    "no dry-run route exists",
    "rollback remains unimplemented",
    "candidate creation remains unimplemented",
    "no trusted",
    "no source",
    "no queue",
    "no digest/history",
    "no ALIVE",
    "no provider",
    "no background",
    "no autonomy",
]

SENSITIVE_ROOTS = [
    APP_ROOT / "memory",
    APP_ROOT / "reports",
]
NORMAL_CLI_LOG_WRITES = {
    "memory\\MAIN_AGENT_LOG.md",
}
THOUGHT_INBOX_FILES = [
    APP_ROOT / "memory" / "COMPANION_THOUGHT_INBOX_V2MIND_A.json",
    APP_ROOT / "reports" / "mind" / "COMPANION_THOUGHT_INBOX_V2MIND_A.md",
]
FORBIDDEN_TARGETS = [
    APP_ROOT / "memory" / "ALIVE_STATE.json",
    APP_ROOT / "memory" / "LEARNING_LOG.md",
    APP_ROOT / "memory" / "RESEARCH_NOTES.md",
    APP_ROOT / "memory" / "RESEARCH_GOALS_QUEUE_V1.md",
    APP_ROOT / "memory" / "PROJECT_HISTORY.md",
    *THOUGHT_INBOX_FILES,
    APP_ROOT / "memory" / "OVERNIGHT_TOPIC_ROTATION.json",
    APP_ROOT / "prompts" / "ENGEL_SYSTEM.md",
    APP_ROOT / "engel_app.py",
    APP_ROOT / "engel_research_brain_v2.py",
    APP_ROOT / "reports" / "overnight" / "OVERNIGHT_QUEUE.md",
    APP_ROOT / "reports" / "research" / "RESEARCH_QUEUE.md",
    APP_ROOT / "reports" / "research" / "LEARNING_PROPOSALS.md",
    APP_ROOT / "reports" / "research" / "RESEARCH_QUEUE_CLEANUP_LATEST.md",
    APP_ROOT / "reports" / "research" / "NEXT_BEST_TOPIC.md",
    APP_ROOT / "reports" / "research" / "RESEARCH_DIGEST_LATEST.md",
    APP_ROOT / "reports" / "research" / "RESEARCH_TOPIC_HISTORY.md",
    APP_ROOT / "reports" / "research" / "learning_proposals_archive",
    APP_ROOT / "reports" / "OVERNIGHT_RESEARCH_LOOP_HISTORY.jsonl",
    APP_ROOT / "reports" / "overnight" / "proposal_harvest",
]
WATCHED_REPORT_DIRS = [
    APP_ROOT / "reports" / "lesson_candidates",
    APP_ROOT / "reports" / "proposal_autonomy",
    APP_ROOT / "reports" / "learning_proposals",
    APP_ROOT / "reports" / "colony_autonomy",
    APP_ROOT / "reports" / "swarm_trails",
    APP_ROOT / "reports" / "colony",
    APP_ROOT / "reports" / "worker_ants",
    APP_ROOT / "reports" / "colony_simulation",
]
ACTIVE_OLD_PROVIDER_FILES = [
    APP_ROOT / "engel_app.py",
    APP_ROOT / "engel_companion.py",
    APP_ROOT / "engel_research_brain_v2.py",
    APP_ROOT / "memory" / "ENGEL_COMMANDS.md",
    APP_ROOT / "memory" / "ROUTE_VERIFICATION_SET_V1.json",
    APP_ROOT / "memory" / "LESSON_CANDIDATE_REVIEW_V1.json",
    APP_ROOT / "memory" / "COLONY_PROPOSAL_AUTONOMY_V1.json",
    APP_ROOT / "memory" / "COLONY_SIMULATION_CONTRACT_V1.json",
    APP_ROOT / "memory" / "BRAIN_BACKENDS.json",
    APP_ROOT / "memory" / "BRAIN_BACKEND_LAYER_V1.md",
    APP_ROOT / "memory" / "OFFLINE_BRAIN_GUARD_V1.md",
    APP_ROOT / "memory" / "ENGEL_BRAIN_RULES.md",
    APP_ROOT / "prompts" / "ENGEL_SYSTEM.md",
]
OLD_PROVIDER_PATTERNS = [
    "Ol" + "lama",
    "ol" + "lama",
    "local" + "host:" + "11" + "434",
    "11" + "434",
]
ACTIVATION_FILES = [
    APP_ROOT / "engel_app.py",
    APP_ROOT / "engel_research_brain_v2.py",
    CONFIG_PATH,
    MANIFEST_PATH,
]

PROVIDER_CALL_PATTERNS = [
    "requests.",
    "urllib.",
    "OPENAI_API_KEY",
    "GEMINI_API_KEY",
    "_chatgpt_",
    "_gemini_",
    "_brain_text_result",
    "ask_brain_provider",
    "research_search",
    "source_search",
    "research_completion_digest(",
    "completion_digest(",
    "live_completion",
    "digest_latest(",
    "research_runner",
    "research_goals_hook_select",
]
BACKGROUND_PATTERNS = [
    "subprocess.Popen",
    "threading.Thread",
    "multiprocessing",
    "schedule.",
    "while True",
    "daemon=True",
    "start_new_session",
    "DETACHED_PROCESS",
]
FORBIDDEN_DIRECT_WRITE_PATTERNS = [
    r"ALIVE_STATE_FILE\.(write_text|open|unlink|replace)",
    r"QUEUE_FILE\.(write_text|open|unlink|replace)",
    r"RESEARCH_DIGEST_LATEST_FILE\.(write_text|open|unlink|replace)",
    r"RESEARCH_TOPIC_HISTORY_FILE\.(write_text|open|unlink|replace)",
    r"PROPOSALS_FILE\.(write_text|open|unlink|replace)",
    r"ARCHIVE_DIR\.(mkdir|write_text|open|unlink|replace)",
    r"LEARNING_LOG\.(write_text|open)",
    r"RESEARCH_NOTES\.(write_text|open)",
    r"write_file\(",
    r"json\.dump\(",
]
MANUAL_MEMORY_PATTERNS = [
    "append_file(",
    "add_memory_note(",
    "LEARNING_LOG",
    "remember <lesson>",
    "Lesson saved",
    "notes ",
]


class CheckFailure(Exception):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_signature(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False}
    if path.is_file():
        stat = path.stat()
        return {
            "exists": True,
            "type": "file",
            "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
            "sha256": sha256(path),
        }
    if path.is_dir():
        stat = path.stat()
        return {
            "exists": True,
            "type": "dir",
            "mtime_ns": stat.st_mtime_ns,
            "file_count": len([p for p in path.rglob("*") if p.is_file()]),
        }
    return {"exists": True, "type": "other"}


def snapshot_roots(roots: list[Path]) -> dict[str, dict[str, Any]]:
    snapshot: dict[str, dict[str, Any]] = {}
    for root in roots:
        if not root.exists():
            snapshot[str(root.relative_to(APP_ROOT))] = {"exists": False}
            continue
        snapshot[str(root.relative_to(APP_ROOT))] = file_signature(root)
        for path in sorted(root.rglob("*")):
            if path.is_file() or path.is_dir():
                snapshot[str(path.relative_to(APP_ROOT))] = file_signature(path)
    return snapshot


def snapshot_sensitive_tree() -> dict[str, dict[str, Any]]:
    return snapshot_roots(SENSITIVE_ROOTS)


def snapshot_forbidden() -> dict[str, dict[str, Any]]:
    return {str(path.relative_to(APP_ROOT)): file_signature(path) for path in FORBIDDEN_TARGETS}


def snapshot_watched_reports() -> dict[str, dict[str, Any]]:
    return snapshot_roots(WATCHED_REPORT_DIRS)


def diff_snapshot(before: dict[str, dict[str, Any]], after: dict[str, dict[str, Any]]) -> dict[str, list[str]]:
    before_keys = set(before)
    after_keys = set(after)
    return {
        "new": sorted(after_keys - before_keys),
        "removed": sorted(before_keys - after_keys),
        "modified": sorted(key for key in before_keys & after_keys if before[key] != after[key]),
    }


def format_diff(diff: dict[str, list[str]]) -> str:
    parts = []
    for key in ["new", "removed", "modified"]:
        if diff[key]:
            parts.append(key + ": " + ", ".join(diff[key][:20]))
    return "; ".join(parts) or "no changes"


def assert_no_tree_change(before: dict[str, dict[str, Any]], after: dict[str, dict[str, Any]], label: str) -> None:
    diff = diff_snapshot(before, after)
    unexpected_modified = [path for path in diff["modified"] if path not in NORMAL_CLI_LOG_WRITES]
    if diff["new"] or diff["removed"] or unexpected_modified:
        scoped = {**diff, "modified": unexpected_modified}
        raise CheckFailure(label + " changed sensitive tree: " + format_diff(scoped))


def assert_only_allowed_lesson_report(
    before: dict[str, dict[str, Any]], after: dict[str, dict[str, Any]], report: Path
) -> None:
    rel = str(report.relative_to(APP_ROOT))
    report_dir_rel = str(REPORT_DIR.relative_to(APP_ROOT))
    reports_rel = str((APP_ROOT / "reports").relative_to(APP_ROOT))
    diff = diff_snapshot(before, after)
    allowed_new = {rel, report_dir_rel}
    allowed_modified = {reports_rel, report_dir_rel}
    unexpected_new = [path for path in diff["new"] if path not in allowed_new]
    unexpected_modified = [
        path for path in diff["modified"] if path not in NORMAL_CLI_LOG_WRITES and path not in allowed_modified
    ]
    if unexpected_new or diff["removed"] or unexpected_modified:
        scoped = {**diff, "new": unexpected_new, "modified": unexpected_modified}
        raise CheckFailure("approved lesson report changed unexpected entries: " + format_diff(scoped))


def report_files() -> set[Path]:
    if not REPORT_DIR.exists():
        return set()
    return {path.resolve() for path in REPORT_DIR.glob(REPORT_GLOB) if path.is_file()}


def thought_inbox_count() -> int:
    path = APP_ROOT / "memory" / "COMPANION_THOUGHT_INBOX_V2MIND_A.json"
    if not path.exists():
        return 0
    data = json.loads(path.read_text(encoding="utf-8"))
    thoughts = data.get("thoughts", [])
    if not isinstance(thoughts, list):
        raise CheckFailure("thought inbox JSON has non-list thoughts")
    return len(thoughts)


def snapshot_thought_inbox() -> dict[str, dict[str, Any]]:
    return {str(path.relative_to(APP_ROOT)): file_signature(path) for path in THOUGHT_INBOX_FILES}


def assert_thought_inbox_unchanged(before_count: int, before_files: dict[str, dict[str, Any]], label: str) -> None:
    after_count = thought_inbox_count()
    after_files = snapshot_thought_inbox()
    if before_count != after_count:
        raise CheckFailure(f"{label} changed thought inbox count {before_count} -> {after_count}")
    diff = diff_snapshot(before_files, after_files)
    if diff["new"] or diff["removed"] or diff["modified"]:
        raise CheckFailure(label + " changed thought inbox files: " + format_diff(diff))


def run_engel(command: str) -> str:
    proc = subprocess.run(
        [sys.executable, str(ENGEL_APP)],
        input=command + "\nexit\n",
        cwd=str(APP_ROOT),
        capture_output=True,
        text=True,
        timeout=90,
    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    output = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode != 0:
        raise CheckFailure(f"{command}: Engel exited with {proc.returncode}\n{output}")
    return output


def assert_contains_ci(text: str, needle: str, label: str) -> None:
    if needle.lower() not in text.lower():
        raise CheckFailure(f"{label}: missing {needle!r}")


def check_py_compile() -> None:
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "py_compile",
            str(APP_ROOT / "engel_app.py"),
            str(APP_ROOT / "engel_companion.py"),
            str(APP_ROOT / "engel_research_brain_v2.py"),
            str(APP_ROOT / "tools" / "verify_lesson_candidate_review.py"),
        ],
        cwd=str(APP_ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if proc.returncode != 0:
        raise CheckFailure("py_compile failed\n" + (proc.stdout or "") + (proc.stderr or ""))


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        raise CheckFailure("missing lesson candidate config: " + str(CONFIG_PATH))
    data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise CheckFailure("lesson candidate config root must be an object")
    return data


def require_false(data: dict[str, Any], key: str) -> None:
    if data.get(key) is not False:
        raise CheckFailure("config must keep " + key + "=false")


def require_true(data: dict[str, Any], key: str) -> None:
    if data.get(key) is not True:
        raise CheckFailure("config must keep " + key + "=true")


def check_config_schema() -> None:
    data = load_config()
    required_values = {
        "version": "V1",
        "colony_identity": "Engel",
        "one_companion_identity": True,
        "mode": "REVIEW_ONLY",
        "local_only": True,
        "untrusted_candidates": True,
        "report_only_until_later_approval": True,
    }
    for key, expected in required_values.items():
        if data.get(key) != expected:
            raise CheckFailure(f"config {key} expected {expected!r}, got {data.get(key)!r}")
    for key in [
        "runtime_autonomy_enabled",
        "runtime_level_2_enabled",
        "simulation_runtime_enabled",
        "background_workers",
        "loops_enabled",
        "provider_calls",
        "live_research",
        "internet_actions",
        "trusted_memory_writes",
        "source_edits",
        "learning_apply",
        "queue_mutation",
        "digest_history_writes",
        "alive_state_writes",
    ]:
        require_false(data, key)
    if int(data.get("max_review_files", 999)) > 40:
        raise CheckFailure("max_review_files must remain <= 40")
    if int(data.get("max_lines_per_file", 999)) > 8:
        raise CheckFailure("max_lines_per_file must remain <= 8")
    if not EXPECTED_CANDIDATE_CATEGORIES.issubset(set(data.get("lesson_candidate_categories", []))):
        raise CheckFailure("missing expected lesson_candidate_categories")
    if not EXPECTED_CANDIDATE_CATEGORIES.issubset(set(data.get("lesson_candidate_types", []))):
        raise CheckFailure("lesson_candidate_types must mirror the hardened candidate categories")
    if not set(data.get("required_output_tokens", [])) >= set(REQUIRED_OUTPUT_TOKENS):
        raise CheckFailure("required_output_tokens missing hardened BW tokens")
    if set(data.get("allowed_outputs_now", [])) != EXPECTED_ALLOWED_OUTPUTS:
        raise CheckFailure("allowed_outputs_now must remain review/report-only")
    if not REQUIRED_BLOCKED_OUTPUTS.issubset(set(data.get("blocked_outputs_without_explicit_future_approval", []))):
        raise CheckFailure("missing blocked outputs")
    approval = data.get("approval_contract")
    if not isinstance(approval, dict):
        raise CheckFailure("approval_contract must be an object")
    for key in REQUIRED_APPROVAL_CONTRACT_KEYS:
        if approval.get(key) is not True:
            raise CheckFailure("approval_contract must keep " + key + "=true")
    manual = data.get("manual_memory_command_boundary")
    if not isinstance(manual, dict):
        raise CheckFailure("manual_memory_command_boundary must be an object")
    require_false(manual, "lesson_candidate_routes_may_invoke_manual_memory_commands")
    require_true(manual, "candidate_outputs_are_not_trusted_memory")
    check_future_apply_contract_object(data.get("future_approved_lesson_apply_contract"), "config")


def check_future_apply_contract_object(value: Any, label: str) -> None:
    if not isinstance(value, dict):
        raise CheckFailure(label + " missing future approved lesson apply contract")
    if value.get("contract_status") != "DESIGN_ONLY_NOT_IMPLEMENTED":
        raise CheckFailure(label + " future apply contract must remain design-only/not implemented")
    if value.get("future_path_must_be_separate_explicit_approval_gated") is not True:
        raise CheckFailure(label + " future apply must be separate explicit approval-gated path")
    for key in [
        "trusted_apply_route_exists_now",
        "automatic_learning_apply_enabled",
        "trusted_memory_writes_enabled_now",
    ]:
        if value.get(key) is not False:
            raise CheckFailure(label + " future apply contract must keep " + key + "=false")
    if value.get("rollback_refusal_checkpoint") != "V2APP_CC_FUTURE_LESSON_APPLY_ROLLBACK_REFUSAL_CONTRACT":
        raise CheckFailure(label + " future apply contract missing CC rollback/refusal checkpoint")
    absent_routes = set(value.get("absent_routes_verified", []))
    if not set(ABSENT_APPLY_ROUTES).issubset(absent_routes):
        raise CheckFailure(label + " future apply contract missing absent apply/rollback route checks")
    if set(value.get("candidate_sources_allowed_future", [])) != EXPECTED_FUTURE_CANDIDATE_SOURCES:
        raise CheckFailure(label + " future apply must only consider report-only lesson candidate artifacts")
    if value.get("candidate_sources_allowed_now", []) != []:
        raise CheckFailure(label + " future apply must have no currently allowed candidate sources")
    if value.get("candidates_remain_untrusted_until_explicit_approval") is not True:
        raise CheckFailure(label + " candidates must remain untrusted until explicit approval")
    if set(value.get("required_future_approval_tokens", [])) != REQUIRED_FUTURE_APPLY_TOKENS:
        raise CheckFailure(label + " required future approval tokens mismatch")
    for key in [
        "future_apply_must_be_narrow_and_file_scoped",
        "future_apply_must_produce_before_after_audit_report",
        "future_apply_must_never_invoke_manual_memory_commands",
    ]:
        if value.get(key) is not True:
            raise CheckFailure(label + " must require " + key)
    if not REQUIRED_FUTURE_REFUSAL_CONDITIONS.issubset(set(value.get("future_refusal_conditions", []))):
        raise CheckFailure(label + " missing future refusal conditions")
    if set(value.get("future_allowlisted_target_types_not_enabled", [])) != EXPECTED_FUTURE_ALLOWLISTED_TARGET_TYPES:
        raise CheckFailure(label + " future allowlisted target types must be design-only and exact")
    if not REQUIRED_FORBIDDEN_FUTURE_APPLY_TARGETS.issubset(set(value.get("forbidden_future_apply_targets", []))):
        raise CheckFailure(label + " missing forbidden future apply targets")
    if not REQUIRED_FUTURE_VERIFIER_EXPECTATIONS.issubset(set(value.get("future_verifier_expectations", []))):
        raise CheckFailure(label + " missing future verifier expectations")
    check_future_target_allowlist(value.get("future_trusted_lesson_apply_target_allowlist"), label)
    check_future_before_after_audit_contract(value.get("future_before_after_audit_contract"), label)
    check_future_candidate_identity_schema(value.get("future_candidate_identity_schema"), label)
    check_future_rollback_refusal_contract(value.get("future_rollback_refusal_contract"), label)
    check_ck_dry_run_apply_preflight_contract(value.get("future_dry_run_apply_preflight_verifier"), value, label)


def check_future_target_allowlist(value: Any, label: str) -> None:
    if not isinstance(value, dict):
        raise CheckFailure(label + " missing future trusted lesson apply target allowlist")
    if value.get("allowlist_status") != "DESIGN_ONLY_INACTIVE":
        raise CheckFailure(label + " target allowlist must remain DESIGN_ONLY_INACTIVE")
    for key in [
        "trusted_lesson_apply_implemented_now",
        "trusted_write_behavior_enabled_now",
        "route_enabled_now",
        "route_matrix_mutation_enabled_now",
    ]:
        if value.get(key) is not False:
            raise CheckFailure(label + " target allowlist must keep " + key + "=false")
    if value.get("required_candidate_source") not in EXPECTED_FUTURE_CANDIDATE_SOURCES:
        raise CheckFailure(label + " target allowlist must require report-only lesson candidate source")
    if set(value.get("required_approval_tokens", [])) != REQUIRED_FUTURE_APPLY_TOKENS:
        raise CheckFailure(label + " target allowlist approval tokens mismatch")
    if set(value.get("allowed_future_target_types", [])) != EXPECTED_FUTURE_ALLOWLISTED_TARGET_TYPES:
        raise CheckFailure(label + " target allowlist target type set mismatch")
    if value.get("currently_enabled_target_types", []) != []:
        raise CheckFailure(label + " target allowlist must have no currently enabled target types")
    if not REQUIRED_TARGET_ALLOWLIST_REFUSAL_CONDITIONS.issubset(set(value.get("refusal_conditions", []))):
        raise CheckFailure(label + " target allowlist missing refusal conditions")
    if not REQUIRED_FORBIDDEN_FUTURE_APPLY_TARGETS.issubset(set(value.get("forbidden_future_targets", []))):
        raise CheckFailure(label + " target allowlist missing forbidden future targets")
    targets = value.get("targets")
    if not isinstance(targets, list):
        raise CheckFailure(label + " target allowlist targets must be a list")
    by_type = {str(item.get("target_type", "")): item for item in targets if isinstance(item, dict)}
    if set(by_type) != EXPECTED_FUTURE_ALLOWLISTED_TARGET_TYPES:
        raise CheckFailure(label + " target allowlist must define exactly the expected target types")
    for target_type, expected in EXPECTED_FUTURE_TARGET_ALLOWLIST.items():
        item = by_type[target_type]
        for key in ["design_only", "active_now", "trusted_write_enabled_now"]:
            expected_value = False if key in {"active_now", "trusted_write_enabled_now"} else True
            if item.get(key) is not expected_value:
                raise CheckFailure(label + " target " + target_type + " must keep " + key + "=" + str(expected_value))
        if set(item.get("allowed_paths", [])) != expected["allowed_paths"]:
            raise CheckFailure(label + " target " + target_type + " allowed_paths mismatch")
        if set(item.get("required_approval_tokens", [])) != REQUIRED_FUTURE_APPLY_TOKENS:
            raise CheckFailure(label + " target " + target_type + " approval tokens mismatch")
        if item.get("required_candidate_source") not in EXPECTED_FUTURE_CANDIDATE_SOURCES:
            raise CheckFailure(label + " target " + target_type + " candidate source mismatch")
        if item.get("required_verifier_state") != STANDARD_VERIFIER + " passed":
            raise CheckFailure(label + " target " + target_type + " verifier state mismatch")
        if item.get("before_after_audit_required") is not True:
            raise CheckFailure(label + " target " + target_type + " must require before/after audit")
        if item.get("maximum_write_scope") != expected["maximum_write_scope"]:
            raise CheckFailure(label + " target " + target_type + " maximum_write_scope mismatch")
        if not REQUIRED_TARGET_ALLOWLIST_REFUSAL_CONDITIONS.issubset(set(item.get("refusal_conditions", []))):
            raise CheckFailure(label + " target " + target_type + " missing refusal conditions")


def check_future_before_after_audit_contract(value: Any, label: str) -> None:
    if not isinstance(value, dict):
        raise CheckFailure(label + " missing future before/after audit contract")
    if value.get("contract_status") != "DESIGN_ONLY_INACTIVE":
        raise CheckFailure(label + " future audit contract must remain DESIGN_ONLY_INACTIVE")
    if value.get("audit_artifact_location") != EXPECTED_FUTURE_AUDIT_LOCATION:
        raise CheckFailure(label + " future audit artifact location mismatch")
    for key in [
        "audit_artifact_location_design_only",
        "audit_artifact_required_before_apply_complete",
        "before_snapshot_required",
        "after_snapshot_required",
        "diff_summary_required",
        "allowed_target_confirmed_required",
        "forbidden_target_confirmed_absent_required",
        "manual_memory_command_not_used_required",
    ]:
        if value.get(key) is not True:
            raise CheckFailure(label + " future audit contract must require " + key)
    for key in [
        "audit_artifact_write_enabled_now",
        "trusted_apply_route_enabled_now",
        "trusted_write_behavior_enabled_now",
    ]:
        if value.get(key) is not False:
            raise CheckFailure(label + " future audit contract must keep " + key + "=false")
    if set(value.get("required_future_audit_fields", [])) != REQUIRED_FUTURE_AUDIT_FIELDS:
        raise CheckFailure(label + " future audit fields mismatch")
    if set(value.get("required_future_audit_tokens", [])) != REQUIRED_FUTURE_AUDIT_TOKENS:
        raise CheckFailure(label + " future audit tokens mismatch")
    if not REQUIRED_FUTURE_AUDIT_REFUSAL_CONDITIONS.issubset(set(value.get("refusal_conditions", []))):
        raise CheckFailure(label + " future audit contract missing refusal conditions")


def check_future_candidate_identity_schema(value: Any, label: str) -> None:
    if not isinstance(value, dict):
        raise CheckFailure(label + " missing future candidate identity/schema contract")
    if value.get("schema_status") != "DESIGN_ONLY_INACTIVE":
        raise CheckFailure(label + " future candidate identity schema must remain DESIGN_ONLY_INACTIVE")
    if value.get("candidate_schema_version") != "V1":
        raise CheckFailure(label + " future candidate schema version mismatch")
    for key in [
        "candidate_schema_enforced_by_verifier",
        "candidate_source_report_required",
        "category_allowlist_required",
        "target_allowlist_required",
    ]:
        if value.get(key) is not True:
            raise CheckFailure(label + " future candidate schema must require " + key)
    for key in [
        "candidate_apply_enabled_now",
        "trusted_write_behavior_enabled_now",
        "candidate_files_created_now",
    ]:
        if value.get(key) is not False:
            raise CheckFailure(label + " future candidate schema must keep " + key + "=false")
    if value.get("required_candidate_source_root") != "reports\\lesson_candidates":
        raise CheckFailure(label + " future candidate source root mismatch")
    if set(value.get("required_candidate_fields", [])) != REQUIRED_FUTURE_CANDIDATE_FIELDS:
        raise CheckFailure(label + " future candidate fields mismatch")
    if set(value.get("allowed_candidate_categories", [])) != EXPECTED_CANDIDATE_CATEGORIES:
        raise CheckFailure(label + " future candidate categories must match BW categories")
    if set(value.get("required_trust_status", [])) != REQUIRED_FUTURE_TRUST_STATUS:
        raise CheckFailure(label + " future candidate trust status mismatch")
    if set(value.get("required_identity_tokens", [])) != REQUIRED_FUTURE_CANDIDATE_IDENTITY_TOKENS:
        raise CheckFailure(label + " future candidate identity tokens mismatch")
    if set(value.get("required_approval_tokens", [])) != REQUIRED_FUTURE_APPLY_TOKENS:
        raise CheckFailure(label + " future candidate approval tokens mismatch")
    verifier_requirements = set(value.get("verifier_requirements", []))
    expected_requirements = {
        STANDARD_VERIFIER + " passed",
        "future_apply_route_absent",
        "target_allowlist_verified",
        "before_after_audit_contract_verified",
    }
    if not expected_requirements.issubset(verifier_requirements):
        raise CheckFailure(label + " future candidate verifier requirements mismatch")
    if not REQUIRED_FUTURE_CANDIDATE_REFUSAL_CONDITIONS.issubset(set(value.get("refusal_conditions", []))):
        raise CheckFailure(label + " future candidate refusal conditions missing")


def check_future_rollback_refusal_contract(value: Any, label: str) -> None:
    if not isinstance(value, dict):
        raise CheckFailure(label + " missing future rollback/refusal contract")
    if value.get("contract_status") != "DESIGN_ONLY_INACTIVE":
        raise CheckFailure(label + " future rollback/refusal contract must remain DESIGN_ONLY_INACTIVE")
    if value.get("rollback_status") != "NOT_IMPLEMENTED":
        raise CheckFailure(label + " future rollback status must remain NOT_IMPLEMENTED")
    for key in [
        "rollback_design_only",
        "refusal_design_only",
        "rollback_plan_required",
        "rollback_human_approval_required",
        "rollback_verifier_required",
        "rollback_audit_required",
        "rollback_must_not_touch_forbidden_targets",
    ]:
        if value.get(key) is not True:
            raise CheckFailure(label + " future rollback/refusal contract must require " + key)
    for key in [
        "rollback_route_exists_now",
        "rollback_route_enabled_now",
        "rollback_behavior_enabled_now",
        "trusted_apply_route_enabled_now",
        "trusted_write_behavior_enabled_now",
    ]:
        if value.get(key) is not False:
            raise CheckFailure(label + " future rollback/refusal contract must keep " + key + "=false")
    for key in ["rollback_scope", "rollback_target_path", "rollback_snapshot_source"]:
        text = str(value.get(key, ""))
        if "design-only" not in text.lower() or "inactive" not in text.lower():
            raise CheckFailure(label + " future rollback field must remain design-only/inactive: " + key)
    if set(value.get("required_rollback_requirements", [])) != REQUIRED_FUTURE_ROLLBACK_REQUIREMENTS:
        raise CheckFailure(label + " future rollback requirements mismatch")
    if set(value.get("required_rollback_tokens", [])) != REQUIRED_FUTURE_ROLLBACK_TOKENS:
        raise CheckFailure(label + " future rollback tokens mismatch")
    if set(value.get("future_refusal_categories", [])) != REQUIRED_FUTURE_REFUSAL_CATEGORIES:
        raise CheckFailure(label + " future refusal categories mismatch")
    if set(value.get("future_refusal_tokens", [])) != REQUIRED_FUTURE_REFUSAL_TOKENS:
        raise CheckFailure(label + " future refusal tokens mismatch")


def check_future_apply_manifest_expectation(value: Any) -> None:
    if not isinstance(value, dict):
        raise CheckFailure("missing lesson_apply_contract_audit_expectations")
    if value.get("contract_status") != "DESIGN_ONLY_NOT_IMPLEMENTED":
        raise CheckFailure("manifest future apply contract must remain design-only/not implemented")
    if value.get("rollback_refusal_checkpoint") != "V2APP_CC_FUTURE_LESSON_APPLY_ROLLBACK_REFUSAL_CONTRACT":
        raise CheckFailure("manifest future apply contract missing CC rollback/refusal checkpoint")
    for key in [
        "future_apply_route_implemented_now",
        "automatic_learning_apply_enabled",
        "trusted_memory_writes_enabled_now",
    ]:
        if value.get(key) is not False:
            raise CheckFailure("manifest future apply contract must keep " + key + "=false")
    if set(value.get("required_future_approval_tokens", [])) != REQUIRED_FUTURE_APPLY_TOKENS:
        raise CheckFailure("manifest future approval tokens mismatch")
    if set(value.get("candidate_sources_allowed_future", [])) != EXPECTED_FUTURE_CANDIDATE_SOURCES:
        raise CheckFailure("manifest future apply must only consider report-only lesson artifacts")
    if value.get("candidate_sources_allowed_now", []) != []:
        raise CheckFailure("manifest future apply must have no currently allowed candidate sources")
    if value.get("candidates_remain_untrusted_until_explicit_approval") is not True:
        raise CheckFailure("manifest future apply must keep candidates untrusted")
    for key in [
        "future_apply_must_be_narrow_and_file_scoped",
        "future_apply_must_produce_before_after_audit_report",
        "future_apply_must_never_invoke_manual_memory_commands",
    ]:
        if value.get(key) is not True:
            raise CheckFailure("manifest future apply contract must require " + key)
    if not REQUIRED_FUTURE_REFUSAL_CONDITIONS.issubset(set(value.get("future_refusal_conditions", []))):
        raise CheckFailure("manifest missing future apply refusal conditions")
    if set(value.get("future_allowlisted_target_types_not_enabled", [])) != EXPECTED_FUTURE_ALLOWLISTED_TARGET_TYPES:
        raise CheckFailure("manifest future allowlisted target types must remain exact/design-only")
    if not REQUIRED_FORBIDDEN_FUTURE_APPLY_TARGETS.issubset(set(value.get("forbidden_future_apply_targets", []))):
        raise CheckFailure("manifest missing forbidden future apply targets")
    if not REQUIRED_FUTURE_VERIFIER_EXPECTATIONS.issubset(set(value.get("future_verifier_expectations", []))):
        raise CheckFailure("manifest missing future apply verifier expectations")
    if value.get("verifier_path", STANDARD_VERIFIER) != STANDARD_VERIFIER:
        raise CheckFailure("manifest future apply verifier_path must point to " + STANDARD_VERIFIER)
    absent_routes = set(value.get("absent_routes_verified", []))
    if not set(ABSENT_APPLY_ROUTES).issubset(absent_routes):
        raise CheckFailure("manifest future apply expectation missing absent route checks")
    if value.get("trusted_apply_route_remains_absent", True) is not True:
        raise CheckFailure("manifest must record trusted apply route remains absent")
    check_future_target_allowlist(value.get("future_trusted_lesson_apply_target_allowlist"), "manifest")
    check_future_before_after_audit_contract(value.get("future_before_after_audit_contract"), "manifest")
    check_future_candidate_identity_schema(value.get("future_candidate_identity_schema"), "manifest")
    check_future_rollback_refusal_contract(value.get("future_rollback_refusal_contract"), "manifest")
    check_ck_dry_run_apply_preflight_contract(value.get("future_dry_run_apply_preflight_verifier"), value, "manifest")


def check_ck_dry_run_apply_preflight_contract(value: Any, future_apply: dict[str, Any], label: str) -> None:
    if not isinstance(value, dict):
        raise CheckFailure(label + " missing CK dry-run apply preflight verifier metadata")
    expected_text = {
        "checkpoint": CK_PREFLIGHT_CHECKPOINT,
        "status": "VERIFIER_ONLY_DESIGN_ONLY",
        "verifier_path": STANDARD_VERIFIER,
    }
    for key, expected in expected_text.items():
        if value.get(key) != expected:
            raise CheckFailure(label + " CK preflight " + key + " mismatch")
    for key in [
        "verifier_only",
        "design_only",
        "metadata_contract_checks_only",
        "apply_remains_absent",
        "rollback_remains_absent",
        "candidate_creation_remains_absent",
    ]:
        if value.get(key) is not True:
            raise CheckFailure(label + " CK preflight must keep " + key + "=true")
    for key in [
        "implemented_now",
        "route_enabled_now",
        "dry_run_apply_route_exists_now",
        "trusted_apply_route_exists_now",
        "rollback_route_exists_now",
        "candidate_creation_route_exists_now",
        "trusted_write_behavior_enabled_now",
        "writes_enabled_now",
    ]:
        if value.get(key) is not False:
            raise CheckFailure(label + " CK preflight must keep " + key + "=false")
    if not CK_PREFLIGHT_REQUIRED_CHECKS.issubset(set(value.get("preflight_checks_only", []))):
        raise CheckFailure(label + " CK preflight missing required metadata check list")
    if not CK_PREFLIGHT_MUST_NOT.issubset(set(value.get("must_not", []))):
        raise CheckFailure(label + " CK preflight missing must_not boundary")
    source_requirements = value.get("candidate_source_requirements")
    if not isinstance(source_requirements, dict):
        raise CheckFailure(label + " CK preflight missing candidate source requirements")
    for key, expected in CK_PREFLIGHT_SOURCE_REQUIREMENTS.items():
        if source_requirements.get(key) != expected:
            raise CheckFailure(label + " CK preflight source requirement mismatch: " + key)
    if set(value.get("required_future_approval_tokens", [])) != REQUIRED_FUTURE_APPLY_TOKENS:
        raise CheckFailure(label + " CK preflight approval token mismatch")
    if set(value.get("target_allowlist_types_verified", [])) != EXPECTED_FUTURE_ALLOWLISTED_TARGET_TYPES:
        raise CheckFailure(label + " CK preflight target allowlist mismatch")
    if set(value.get("required_candidate_fields_verified", [])) != REQUIRED_FUTURE_CANDIDATE_FIELDS:
        raise CheckFailure(label + " CK preflight candidate field mismatch")
    expected_absent = set(ABSENT_APPLY_ROUTES) | set(CK_ABSENT_DRY_RUN_ROUTES)
    if not expected_absent.issubset(set(value.get("absent_routes_verified", []))):
        raise CheckFailure(label + " CK preflight missing absent route checks")
    if value.get("candidate_source_requirements", {}).get("source_glob") not in future_apply.get("candidate_sources_allowed_future", []):
        raise CheckFailure(label + " CK preflight source glob must match future apply report-only source")


def check_staged_inactive() -> None:
    sys.path.insert(0, str(APP_ROOT))
    module = importlib.import_module("engel_research_brain_v2")
    if getattr(module, "STAGED_DRAFT_ACTIVE", None) is not False:
        raise CheckFailure("STAGED_DRAFT_ACTIVE must remain False")


def check_no_activation_literals() -> None:
    patterns = [
        re.compile(r"STAGED_DRAFT_ACTIVE\s*=\s*True"),
        re.compile(r"runtime_autonomy_enabled\s+true", re.IGNORECASE),
        re.compile(r"runtime_level_2_enabled\s+true", re.IGNORECASE),
    ]
    matches: list[str] = []
    for path in ACTIVATION_FILES:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if any(pattern.search(line) for pattern in patterns):
                matches.append(f"{path.relative_to(APP_ROOT)}:{lineno}:{line.strip()}")
    if matches:
        raise CheckFailure("unsafe activation literal found:\n" + "\n".join(matches[:30]))


def check_no_active_old_provider() -> None:
    regex = re.compile("|".join(re.escape(item) for item in OLD_PROVIDER_PATTERNS), re.IGNORECASE)
    matches: list[str] = []
    for path in ACTIVE_OLD_PROVIDER_FILES:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if regex.search(line):
                matches.append(f"{path.relative_to(APP_ROOT)}:{lineno}:{line.strip()}")
    if matches:
        raise CheckFailure("active old-provider matches found:\n" + "\n".join(matches[:20]))


def check_manifest_alignment() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if manifest.get("mode") != "DOCUMENTATION_ONLY":
        raise CheckFailure("manifest mode must remain DOCUMENTATION_ONLY")
    if manifest.get("runtime_feature_enabled") is not False:
        raise CheckFailure("manifest runtime_feature_enabled must remain false")
    if manifest.get("runs_automatically") is not False:
        raise CheckFailure("manifest runs_automatically must remain false")
    verifiers = manifest.get("standard_verifiers")
    if not isinstance(verifiers, list):
        raise CheckFailure("standard_verifiers must be a list")
    for verifier in STANDARD_VERIFIERS:
        if verifier not in verifiers:
            raise CheckFailure("standard verifier missing from manifest: " + verifier)
    entries = manifest.get("route_regression_matrix_entries")
    if not isinstance(entries, list):
        raise CheckFailure("route_regression_matrix_entries must be a list")
    by_command = {str(entry.get("command", "")): entry for entry in entries if isinstance(entry, dict)}
    for command, expected_behavior in MATRIX_ENTRIES.items():
        entry = by_command.get(command)
        if not entry:
            raise CheckFailure("missing lesson candidate matrix entry: " + command)
        if entry.get("expected_behavior") != expected_behavior:
            raise CheckFailure(command + " expected_behavior mismatch")
        if entry.get("should_execute_in_test") is not False:
            raise CheckFailure(command + " should_execute_in_test must remain false")
        if command in ABSENT_APPLY_ROUTES:
            if entry.get("implemented_now") is not False:
                raise CheckFailure(command + " implemented_now must remain false")
            if entry.get("content_contract_ref") != "lesson_apply_contract_audit_expectations":
                raise CheckFailure(command + " must reference lesson_apply_contract_audit_expectations")
    expectation = manifest.get("lesson_candidate_review_expectations")
    if not isinstance(expectation, dict):
        raise CheckFailure("missing lesson_candidate_review_expectations")
    for key in [
        "trusted_memory_writes",
        "source_edits",
        "learning_apply",
        "queue_mutation",
        "digest_history_writes",
        "alive_state_writes",
        "provider_calls",
        "background_workers",
        "loops_enabled",
    ]:
        if expectation.get(key) is not False:
            raise CheckFailure("lesson expectation must keep " + key + "=false")
    if expectation.get("approve_report_output_folder") != "reports\\lesson_candidates":
        raise CheckFailure("lesson candidate approve_report_output_folder mismatch")
    if not EXPECTED_CANDIDATE_CATEGORIES.issubset(set(expectation.get("candidate_categories", []))):
        raise CheckFailure("manifest lesson expectation missing hardened candidate categories")
    if not set(expectation.get("required_output_tokens", [])) >= set(REQUIRED_OUTPUT_TOKENS):
        raise CheckFailure("manifest lesson expectation missing hardened output tokens")
    readiness = manifest.get("lesson_candidate_readiness_expectations")
    if not isinstance(readiness, dict):
        raise CheckFailure("missing lesson_candidate_readiness_expectations")
    if readiness.get("route") != READINESS_ROUTE:
        raise CheckFailure("lesson readiness route expectation mismatch")
    if readiness.get("expected_behavior") != MATRIX_ENTRIES[READINESS_ROUTE]:
        raise CheckFailure("lesson readiness expected_behavior mismatch")
    if readiness.get("should_execute_in_test") is not False:
        raise CheckFailure("lesson readiness should_execute_in_test must remain false")
    if not set(readiness.get("required_output_tokens", [])) >= set(REQUIRED_READINESS_TOKENS):
        raise CheckFailure("lesson readiness expectation missing required output tokens")
    for phrase in [
        "run verifiers",
        "generate reports",
        "create lesson candidates",
        "create candidate files",
        "implement apply",
        "implement rollback",
        "modify trusted memory",
        "modify source",
        "mutate queues",
        "write digest/history",
        "write ALIVE_STATE",
        "call providers",
        "start loops or background workers",
    ]:
        if phrase not in set(readiness.get("must_not", [])):
            raise CheckFailure("lesson readiness expectation missing must_not phrase: " + phrase)
    cf_safety = readiness.get("cf_safety_test_pass")
    if not isinstance(cf_safety, dict):
        raise CheckFailure("lesson readiness expectation missing CF safety test pass metadata")
    if cf_safety.get("source_checkpoint") != "V2APP_CF_LESSON_CANDIDATE_READINESS_STATUS_SAFETY_TEST_PASS":
        raise CheckFailure("lesson readiness CF safety checkpoint mismatch")
    if cf_safety.get("snapshot_routes") != CF_SNAPSHOT_ROUTES:
        raise CheckFailure("lesson readiness CF snapshot routes mismatch")
    if not set(cf_safety.get("snapshot_roots", [])) >= {"memory\\", "reports\\"}:
        raise CheckFailure("lesson readiness CF snapshot roots must include memory and reports")
    for watched_dir in [
        "reports\\lesson_candidates\\",
        "reports\\proposal_autonomy\\",
        "reports\\learning_proposals\\",
        "reports\\colony_autonomy\\",
        "reports\\swarm_trails\\",
        "reports\\colony\\",
        "reports\\worker_ants\\",
        "reports\\colony_simulation\\",
    ]:
        if watched_dir not in set(cf_safety.get("watched_report_dirs", [])):
            raise CheckFailure("lesson readiness CF watched report dir missing: " + watched_dir)
    for target in [
        "memory\\ALIVE_STATE.json",
        "memory\\LEARNING_LOG.md",
        "memory\\RESEARCH_GOALS_QUEUE_V1.md",
        "memory\\PROJECT_HISTORY.md",
        "memory\\COMPANION_THOUGHT_INBOX_V2MIND_A.json",
        "reports\\mind\\COMPANION_THOUGHT_INBOX_V2MIND_A.md",
        "reports\\overnight\\OVERNIGHT_QUEUE.md",
        "reports\\research\\RESEARCH_QUEUE.md",
        "reports\\research\\RESEARCH_DIGEST_LATEST.md",
        "reports\\research\\RESEARCH_TOPIC_HISTORY.md",
        "reports\\OVERNIGHT_RESEARCH_LOOP_HISTORY.jsonl",
    ]:
        if target not in set(cf_safety.get("watched_forbidden_targets", [])):
            raise CheckFailure("lesson readiness CF watched forbidden target missing: " + target)
    for action in [
        "verifier execution",
        "report generation",
        "candidate creation",
        "apply logic",
        "rollback logic",
        "older manual memory commands",
        "provider/API/network calls",
        "background worker logic",
        "trusted memory writes",
        "source edits",
        "queue mutations",
        "digest/history writes",
        "ALIVE_STATE writes",
        "autonomy",
    ]:
        if action not in set(cf_safety.get("runtime_actions_blocked", [])):
            raise CheckFailure("lesson readiness CF blocked runtime action missing: " + action)
    living = manifest.get("living_learning_status_expectations")
    if not isinstance(living, dict):
        raise CheckFailure("missing living_learning_status_expectations")
    if living.get("route") != LIVING_ROUTE:
        raise CheckFailure("living learning route expectation mismatch")
    if living.get("expected_behavior") != MATRIX_ENTRIES[LIVING_ROUTE]:
        raise CheckFailure("living learning expected_behavior mismatch")
    if living.get("should_execute_in_test") is not False:
        raise CheckFailure("living learning should_execute_in_test must remain false")
    if living.get("source_checkpoint") != "V2APP_CL_ENGEL_LIVING_LEARNING_UNIFIED_STATUS":
        raise CheckFailure("living learning checkpoint mismatch")
    if not set(living.get("required_output_tokens", [])) >= set(REQUIRED_LIVING_TOKENS):
        raise CheckFailure("living learning expectation missing required tokens")
    for phrase in [
        "proposal readiness",
        "lesson candidate readiness",
        "future trusted apply readiness",
        "colony simulation readiness",
        "current safe learning path",
        "forbidden actions",
        "next human-approved growth step",
    ]:
        if phrase not in set(living.get("must_summarize", [])):
            raise CheckFailure("living learning expectation missing summary phrase: " + phrase)
    for phrase in [
        "run verifiers",
        "generate reports",
        "create candidates",
        "apply lessons",
        "rollback changes",
        "write trusted memory",
        "edit source",
        "mutate queues",
        "write digest/history",
        "write ALIVE_STATE",
        "call providers",
        "start loops or background workers",
        "enable autonomy",
    ]:
        if phrase not in set(living.get("must_not", [])):
            raise CheckFailure("living learning expectation missing must_not phrase: " + phrase)
    check_future_apply_manifest_expectation(manifest.get("lesson_apply_contract_audit_expectations"))


def normalized_doc_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore").replace("`", "").replace("/", "\\").lower()


def require_doc_phrase(text: str, phrase: str, label: str) -> None:
    if phrase.replace("/", "\\").lower() not in text:
        raise CheckFailure(label + " missing drift guard phrase: " + phrase)


def check_cg_documentation_drift_guard() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    readiness = manifest.get("lesson_candidate_readiness_expectations")
    if not isinstance(readiness, dict):
        raise CheckFailure("missing lesson_candidate_readiness_expectations for CG drift guard")
    if readiness.get("documentation_alignment_checkpoint") != "V2APP_CG_LESSON_CANDIDATE_READINESS_DOCUMENTATION_ALIGNMENT":
        raise CheckFailure("lesson readiness CG documentation alignment checkpoint missing")

    structured_classifications = {
        str(entry.get("command", "")): entry
        for entry in readiness.get("current_lesson_route_classifications", [])
        if isinstance(entry, dict)
    }
    for command, classification in EXPECTED_CG_ROUTE_CLASSIFICATIONS.items():
        entry = structured_classifications.get(command)
        if not entry:
            raise CheckFailure("CG route classification missing from manifest: " + command)
        if entry.get("classification") != classification:
            raise CheckFailure("CG route classification mismatch for " + command)
        if entry.get("should_execute_in_test") is not False:
            raise CheckFailure("CG route classification should_execute_in_test must remain false for " + command)

    manifest_absent = set(readiness.get("future_routes_remain_absent", []))
    for route in EXPECTED_FUTURE_ABSENT_ROUTES:
        if route not in manifest_absent:
            raise CheckFailure("CG future absent route missing from manifest: " + route)

    if not set(readiness.get("required_output_tokens", [])) >= set(REQUIRED_READINESS_TOKENS):
        raise CheckFailure("CG manifest readiness tokens drifted")
    cf_safety = readiness.get("cf_safety_test_pass")
    if not isinstance(cf_safety, dict):
        raise CheckFailure("CG manifest missing CF safety test pass")
    for command in CF_SNAPSHOT_ROUTES:
        if command not in cf_safety.get("snapshot_routes", []):
            raise CheckFailure("CG manifest missing CF snapshot route: " + command)
    for phrase in [
        "memory\\",
        "reports\\",
        "memory\\ALIVE_STATE.json",
        "reports\\research\\RESEARCH_DIGEST_LATEST.md",
        "reports\\research\\RESEARCH_TOPIC_HISTORY.md",
    ]:
        joined_targets = "\n".join(str(item) for item in cf_safety.get("snapshot_roots", []) + cf_safety.get("watched_forbidden_targets", []))
        if phrase not in joined_targets:
            raise CheckFailure("CG manifest CF snapshot target missing: " + phrase)
    for action in [
        "verifier execution",
        "report generation",
        "candidate creation",
        "apply logic",
        "rollback logic",
        "older manual memory commands",
        "provider/API/network calls",
        "background worker logic",
    ]:
        if action not in set(cf_safety.get("runtime_actions_blocked", [])):
            raise CheckFailure("CG manifest CF blocked action missing: " + action)

    doc_paths = {
        "ENGEL_COMMANDS.md": COMMANDS_PATH,
        "STANDARD_VERIFIER_CHECKLIST_V1.md": CHECKLIST_PATH,
        "PROJECT_MEMORY_INDEX_V2V.md": PROJECT_MEMORY_INDEX_PATH,
    }
    for label, path in doc_paths.items():
        text = normalized_doc_text(path)
        require_doc_phrase(text, "lesson candidates readiness status", label)
        for command, classification in EXPECTED_CG_ROUTE_CLASSIFICATIONS.items():
            require_doc_phrase(text, command, label)
            require_doc_phrase(text, classification, label)
        for route in EXPECTED_FUTURE_ABSENT_ROUTES:
            require_doc_phrase(text, route, label)
        if not any(word in text for word in ["absent", "unimplemented", "non-executing"]):
            raise CheckFailure(label + " must document future apply/rollback/candidate routes as absent or non-executing")
        for phrase in [
            "snapshot",
            "before",
            "after",
            "memory",
            "reports",
            "queue",
            "digest/history",
            "alive_state",
            "verifier",
            "report generation",
            "candidate creation",
            "apply",
            "rollback",
        ]:
            require_doc_phrase(text, phrase, label)

    for label, path in {
        "ENGEL_COMMANDS.md": COMMANDS_PATH,
        "STANDARD_VERIFIER_CHECKLIST_V1.md": CHECKLIST_PATH,
    }.items():
        text = normalized_doc_text(path)
        for token in REQUIRED_READINESS_TOKENS:
            require_doc_phrase(text, token, label)


def check_ck_dry_run_preflight_documentation_alignment() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    apply_expectations = manifest.get("lesson_apply_contract_audit_expectations")
    if not isinstance(apply_expectations, dict):
        raise CheckFailure("missing lesson apply expectations for CK preflight")
    if apply_expectations.get("dry_run_apply_preflight_checkpoint") != CK_PREFLIGHT_CHECKPOINT:
        raise CheckFailure("manifest missing CK dry-run preflight checkpoint")
    for key in [
        "dry_run_apply_preflight_verifier_only",
        "trusted_apply_remains_unimplemented",
        "rollback_remains_unimplemented",
        "candidate_creation_remains_unimplemented",
        "no_write_behavior_enabled",
    ]:
        if apply_expectations.get(key) is not True:
            raise CheckFailure("manifest CK preflight must keep " + key + "=true")
    for key in [
        "dry_run_apply_route_exists_now",
        "dry_run_apply_route_should_execute_in_test",
    ]:
        if apply_expectations.get(key) is not False:
            raise CheckFailure("manifest CK preflight must keep " + key + "=false")

    for label, path in {
        "ENGEL_COMMANDS.md": COMMANDS_PATH,
        "STANDARD_VERIFIER_CHECKLIST_V1.md": CHECKLIST_PATH,
        "PROJECT_MEMORY_INDEX_V2V.md": PROJECT_MEMORY_INDEX_PATH,
    }.items():
        text = normalized_doc_text(path)
        for phrase in CK_DOC_PHRASES:
            require_doc_phrase(text, phrase, label)
        for route in CK_ABSENT_DRY_RUN_ROUTES:
            require_doc_phrase(text, route, label)


def check_cl_living_learning_documentation_alignment() -> None:
    for label, path in {
        "ENGEL_COMMANDS.md": COMMANDS_PATH,
        "STANDARD_VERIFIER_CHECKLIST_V1.md": CHECKLIST_PATH,
        "PROJECT_MEMORY_INDEX_V2V.md": PROJECT_MEMORY_INDEX_PATH,
    }.items():
        text = normalized_doc_text(path)
        for phrase in [
            "living learning status",
            "read-only/status-only",
            "proposal readiness",
            "lesson candidate readiness",
            "future trusted apply readiness",
            "colony simulation readiness",
            "current safe learning path",
            "forbidden actions",
            "next human-approved growth step",
            "no verifier execution",
            "no report generation",
            "no candidate creation",
            "no apply",
            "no rollback",
        ]:
            require_doc_phrase(text, phrase, label)
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    living = manifest.get("living_learning_status_expectations")
    if not isinstance(living, dict):
        raise CheckFailure("manifest missing CL living learning status expectations")
    if living.get("route") != LIVING_ROUTE:
        raise CheckFailure("manifest CL living learning route mismatch")


def check_cm_living_learning_drift_guard() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    entries = manifest.get("route_regression_matrix_entries")
    if not isinstance(entries, list):
        raise CheckFailure("CM drift guard missing route matrix entries")
    by_command = {str(entry.get("command", "")): entry for entry in entries if isinstance(entry, dict)}
    living_entry = by_command.get(LIVING_ROUTE)
    if not isinstance(living_entry, dict):
        raise CheckFailure("CM drift guard missing living learning matrix entry")
    if living_entry.get("expected_behavior") != "READ_ONLY_STATUS_ONLY_NO_WRITE":
        raise CheckFailure("CM living learning matrix expected behavior drifted")
    if living_entry.get("should_execute_in_test") is not False:
        raise CheckFailure("CM living learning matrix must keep should_execute_in_test false")
    if living_entry.get("content_contract_ref") != "living_learning_status_expectations":
        raise CheckFailure("CM living learning matrix content contract ref drifted")

    living = manifest.get("living_learning_status_expectations")
    if not isinstance(living, dict):
        raise CheckFailure("CM drift guard missing living learning expectations")
    if set(living.get("required_output_tokens", [])) != set(REQUIRED_LIVING_TOKENS):
        raise CheckFailure("CM living learning required output token set drifted")
    if not set(CM_LIVING_SUMMARY_PHRASES).issubset(set(living.get("must_summarize", []))):
        raise CheckFailure("CM living learning summary expectations drifted")
    if not {
        "run verifiers",
        "generate reports",
        "create candidates",
        "apply lessons",
        "rollback changes",
        "write trusted memory",
        "edit source",
        "mutate queues",
        "write digest/history",
        "write ALIVE_STATE",
        "call providers",
        "start loops or background workers",
        "enable autonomy",
    }.issubset(set(living.get("must_not", []))):
        raise CheckFailure("CM living learning forbidden-action expectations drifted")

    for label, path in {
        "ENGEL_COMMANDS.md": COMMANDS_PATH,
        "STANDARD_VERIFIER_CHECKLIST_V1.md": CHECKLIST_PATH,
        "PROJECT_MEMORY_INDEX_V2V.md": PROJECT_MEMORY_INDEX_PATH,
    }.items():
        text = normalized_doc_text(path)
        require_doc_phrase(text, LIVING_ROUTE, label)
        for phrase in CM_LIVING_CLASSIFICATION_PHRASES:
            require_doc_phrase(text, phrase, label)
        for phrase in CM_LIVING_SUMMARY_PHRASES:
            require_doc_phrase(text, phrase, label)
        for phrase in CM_FORBIDDEN_AVAILABILITY_PHRASES:
            require_doc_phrase(text, phrase, label)

    research_text = (APP_ROOT / "engel_research_brain_v2.py").read_text(encoding="utf-8", errors="ignore")
    app_text = (APP_ROOT / "engel_app.py").read_text(encoding="utf-8", errors="ignore")
    living_source = function_slice(research_text, "living_learning_status")
    living_wrapper = function_slice(app_text, "living_learning_status")
    living_dispatch = source_between(app_text, 'if lower_msg == "living learning status"', 'if lower_msg == "colony simulation status"')
    combined = living_source + "\n" + living_wrapper + "\n" + living_dispatch

    provider_hits = [pattern for pattern in PROVIDER_CALL_PATTERNS if pattern in combined]
    if provider_hits:
        raise CheckFailure("CM living route provider/API/network pattern found: " + ", ".join(provider_hits))
    background_hits = [pattern for pattern in BACKGROUND_PATTERNS if pattern in combined]
    if background_hits:
        raise CheckFailure("CM living route background pattern found: " + ", ".join(background_hits))
    manual_hits = [pattern for pattern in MANUAL_MEMORY_PATTERNS if pattern in combined]
    if manual_hits:
        raise CheckFailure("CM living route manual-memory pattern found: " + ", ".join(manual_hits))
    forbidden_source_patterns = [
        "write_text",
        ".mkdir(",
        "write_file(",
        "append_file(",
        "json.dump(",
        "subprocess.run",
        "subprocess.Popen",
        "run_engel(",
        "verify_lesson_candidate_review",
        "LESSON_CANDIDATE_REVIEW_VERIFICATION_PASS",
        "lesson_candidates_review(",
        "colony_proposal_preview(",
    ]
    hits = [pattern for pattern in forbidden_source_patterns if pattern in combined]
    if hits:
        raise CheckFailure("CM living route source slice contains forbidden behavior marker: " + ", ".join(hits))


def check_cx_living_systems_map_drift_guard() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    entries = manifest.get("route_regression_matrix_entries")
    if not isinstance(entries, list):
        raise CheckFailure("CX living systems guard missing route matrix entries")
    by_command = {str(entry.get("command", "")): entry for entry in entries if isinstance(entry, dict)}

    living_systems = manifest.get("living_systems_consolidation_expectations")
    if not isinstance(living_systems, dict):
        raise CheckFailure("missing living_systems_consolidation_expectations")
    if living_systems.get("consolidation_checkpoint") != CW_CONSOLIDATION_CHECKPOINT:
        raise CheckFailure("CW consolidation checkpoint missing from living systems expectations")
    if living_systems.get("drift_guard_checkpoint") != CX_DRIFT_GUARD_CHECKPOINT:
        raise CheckFailure("CX drift guard checkpoint missing from living systems expectations")
    if living_systems.get("drift_guard_verifier") != STANDARD_VERIFIER:
        raise CheckFailure("CX living systems drift guard must stay in lesson candidate verifier")

    for verifier in STANDARD_VERIFIERS:
        if verifier not in set(living_systems.get("standard_verifiers", [])):
            raise CheckFailure("CX living systems verifier map missing standard verifier: " + verifier)

    surface_map = living_systems.get("current_safe_surfaces")
    if not isinstance(surface_map, dict):
        raise CheckFailure("CX living systems current_safe_surfaces must be an object")
    for surface, routes in CW_SURFACE_ROUTES.items():
        surface_info = surface_map.get(surface)
        if not isinstance(surface_info, dict):
            raise CheckFailure("CX living systems missing surface: " + surface)
        if not set(routes).issubset(set(surface_info.get("routes", []))):
            raise CheckFailure("CX living systems surface route drift: " + surface)

    expected_route_behaviors = {
        "colony proposal status": "READ_ONLY_STATUS_ONLY_CONTRACT_ONLY",
        "colony proposal contract": "READ_ONLY_STATUS_ONLY_CONTRACT_ONLY",
        "colony proposal preview": "READ_ONLY_DRY_RUN_LOCAL_ONLY_NO_WRITE",
        "colony proposal preview APPROVE_REPORT": "APPROVE_REPORT_REPORT_ONLY_LOCAL_ONLY",
        "lesson candidates status": "READ_ONLY_REVIEW_ONLY_STATUS",
        "lesson candidates review": "READ_ONLY_REVIEW_ONLY_LOCAL_ONLY_NO_WRITE",
        "lesson candidates readiness status": "READ_ONLY_STATUS_ONLY_NO_WRITE",
        "lesson candidates review APPROVE_REPORT": "APPROVE_REPORT_REPORT_ONLY_LOCAL_ONLY",
        "colony simulation status": "READ_ONLY_STATUS_ONLY_CONTRACT_ONLY",
        "colony simulation contract": "READ_ONLY_STATUS_ONLY_CONTRACT_ONLY",
        "living learning status": "READ_ONLY_STATUS_ONLY_NO_WRITE",
        "colony mycelium status": "READ_ONLY_STATUS_ONLY_CONTRACT_ONLY_NO_RUNTIME_NO_WRITE",
        "colony mycelium contract": "READ_ONLY_CONTRACT_ONLY_NO_RUNTIME_NO_WRITE",
    }
    for command, expected_behavior in expected_route_behaviors.items():
        entry = by_command.get(command)
        if not isinstance(entry, dict):
            raise CheckFailure("CX living systems missing route matrix entry: " + command)
        if entry.get("expected_behavior") != expected_behavior:
            raise CheckFailure("CX living systems route expected behavior drifted: " + command)
        if entry.get("should_execute_in_test") is not False:
            raise CheckFailure("CX living systems route should_execute_in_test must remain false: " + command)

    proposal = manifest.get("proposal_autonomy_content_expectations")
    if not isinstance(proposal, dict):
        raise CheckFailure("CX missing proposal autonomy expectations")
    if proposal.get("approve_report_output_folder") != "reports\\proposal_autonomy":
        raise CheckFailure("CX proposal APPROVE_REPORT output folder drifted")
    for phrase in [
        "proposal candidates are not trusted memory",
        "proposal candidates are not applied lessons",
        "proposal candidates are not queue mutations",
        "proposal candidates are not source edits",
    ]:
        if phrase not in set(proposal.get("preview_must_state", [])):
            raise CheckFailure("CX proposal untrusted/no-mutation phrase missing: " + phrase)

    lesson = manifest.get("lesson_candidate_review_expectations")
    if not isinstance(lesson, dict):
        raise CheckFailure("CX missing lesson candidate expectations")
    if lesson.get("untrusted_candidates") is not True:
        raise CheckFailure("CX lesson candidates must remain untrusted")
    if lesson.get("approve_report_output_folder") != "reports\\lesson_candidates":
        raise CheckFailure("CX lesson APPROVE_REPORT output folder drifted")
    for key in ["trusted_memory_writes", "source_edits", "learning_apply", "queue_mutation"]:
        if lesson.get(key) is not False:
            raise CheckFailure("CX lesson expectation must keep " + key + "=false")

    apply_expectations = manifest.get("lesson_apply_contract_audit_expectations")
    check_future_apply_manifest_expectation(apply_expectations)
    if not isinstance(apply_expectations, dict):
        raise CheckFailure("CX missing future apply expectations")
    for key in [
        "trusted_apply_remains_unimplemented",
        "rollback_remains_unimplemented",
        "candidate_creation_remains_unimplemented",
        "dry_run_apply_preflight_verifier_only",
    ]:
        if apply_expectations.get(key) is not True:
            raise CheckFailure("CX future apply metadata drifted: " + key)
    for route in [
        "lesson candidates apply",
        "lesson candidates apply APPROVE",
        "lesson candidates review APPROVE_APPLY",
        "lesson candidates rollback",
        "dry-run apply route",
    ]:
        if route not in set(apply_expectations.get("absent_routes_verified", [])):
            raise CheckFailure("CX future apply absent route missing: " + route)

    simulation = manifest.get("colony_simulation_contract_expectations")
    if not isinstance(simulation, dict):
        raise CheckFailure("CX missing colony simulation expectations")
    if set(simulation.get("current_implemented_routes", [])) != {"colony simulation status", "colony simulation contract"}:
        raise CheckFailure("CX simulation implemented routes drifted")
    if simulation.get("simulation_runtime_enabled") is not False:
        raise CheckFailure("CX simulation runtime must remain disabled")
    for route in ["colony simulation preview", "colony simulation preview APPROVE_REPORT"]:
        if route not in set(simulation.get("disabled_routes", [])):
            raise CheckFailure("CX simulation disabled route missing: " + route)

    living = manifest.get("living_learning_status_expectations")
    if not isinstance(living, dict):
        raise CheckFailure("CX missing living learning expectations")
    if living.get("expected_behavior") != "READ_ONLY_STATUS_ONLY_NO_WRITE":
        raise CheckFailure("CX living learning expected behavior drifted")
    for phrase in ["run verifiers", "generate reports", "create candidates", "apply lessons", "rollback changes"]:
        if phrase not in set(living.get("must_not", [])):
            raise CheckFailure("CX living learning forbidden behavior missing: " + phrase)

    mycelium = manifest.get("colony_mycelium_layer_contract_expectations")
    if not isinstance(mycelium, dict):
        raise CheckFailure("CX missing mycelium expectations")
    if mycelium.get("mycelium_runtime_enabled") is not False:
        raise CheckFailure("CX mycelium runtime must remain disabled")
    if mycelium.get("signal_propagation_runtime_enabled") is not False:
        raise CheckFailure("CX mycelium signal propagation runtime must remain disabled")
    if mycelium.get("structural_analogy_only") is not True:
        raise CheckFailure("CX mycelium structural analogy rule drifted")
    mycelium_guard_text = " ".join(str(item) for item in mycelium.get("read_only_route_drift_guard_checks", []))
    for phrase in [
        "mycelium preview",
        "preview/report",
        "APPROVE_REPORT",
        "candidate routes",
    ]:
        if phrase.lower() not in mycelium_guard_text.lower():
            raise CheckFailure("CX mycelium absent route guard phrase missing: " + phrase)

    if not set(CW_SAFE_PATH_PHRASES).issubset(set(living_systems.get("unified_safe_learning_path", []))):
        raise CheckFailure("CX unified safe learning path drifted")
    if not set(CW_FORBIDDEN_ACTIONS).issubset(set(living_systems.get("forbidden_actions", []))):
        raise CheckFailure("CX forbidden action summary drifted")

    for label, path in {
        "STANDARD_VERIFIER_CHECKLIST_V1.md": CHECKLIST_PATH,
        "PROJECT_MEMORY_INDEX_V2V.md": PROJECT_MEMORY_INDEX_PATH,
    }.items():
        text = normalized_doc_text(path)
        for phrase in [CW_CONSOLIDATION_CHECKPOINT, CX_DRIFT_GUARD_CHECKPOINT]:
            require_doc_phrase(text, phrase, label)
        for phrase in CW_DOC_PHRASES + CW_SAFE_PATH_PHRASES + CW_FORBIDDEN_ACTIONS:
            require_doc_phrase(text, phrase, label)


def check_status_routes_no_reports() -> None:
    for route_command in ["verification set status", "route regression status"]:
        before_tree = snapshot_sensitive_tree()
        before_watched_reports = snapshot_watched_reports()
        before_reports = report_files()
        before_thought_files = snapshot_thought_inbox()
        before_thought_count = thought_inbox_count()
        output = run_engel(route_command)
        after_tree = snapshot_sensitive_tree()
        after_watched_reports = snapshot_watched_reports()
        assert_no_tree_change(before_tree, after_tree, route_command)
        assert_no_tree_change(before_watched_reports, after_watched_reports, route_command + " watched reports")
        assert_thought_inbox_unchanged(before_thought_count, before_thought_files, route_command)
        if report_files() != before_reports:
            raise CheckFailure(route_command + " generated a lesson candidate report")
        assert_contains_ci(output, STANDARD_VERIFIER, route_command)
        for command in MATRIX_ENTRIES:
            assert_contains_ci(output, command, route_command)
        assert_contains_ci(output, "should_execute_in_test: false", route_command)
        assert_contains_ci(output, "does not generate reports", route_command)
        if "# Lesson Candidates Review Report Written" in output:
            raise CheckFailure(route_command + " appears to have executed approved lesson report route")


def check_future_apply_routes_absent_from_source() -> None:
    app_text = (APP_ROOT / "engel_app.py").read_text(encoding="utf-8", errors="ignore")
    research_text = (APP_ROOT / "engel_research_brain_v2.py").read_text(encoding="utf-8", errors="ignore")
    app_wrapper_source = source_between(app_text, "def lesson_candidates_status", "def colony_simulation_status")
    route_dispatch_source = source_between(
        app_text, 'if lower_msg == "lesson candidates status"', 'if lower_msg == "colony simulation status"'
    )
    forbidden_exact_dispatch = [
        'if lower_msg == "lesson candidates apply"',
        'if lower_msg == "lesson candidates apply approve"',
        'if lower_msg == "lesson candidates apply dry-run"',
        'if lower_msg == "lesson candidates apply dry run"',
        'if lower_msg == "lesson candidates dry-run apply"',
        'if lower_msg == "lesson candidates dry run apply"',
        'if lower_msg == "lesson candidates apply preflight"',
        'if lower_msg == "lesson candidates preflight apply"',
        'if lower_msg == "lesson candidates review approve_apply"',
        'if lower_msg == "lesson candidates rollback"',
        'if lower_msg == "lesson candidates create"',
        'if lower_msg == "lesson candidates create approve"',
    ]
    lowered_dispatch = route_dispatch_source.lower()
    dispatch_hits = [literal for literal in forbidden_exact_dispatch if literal in lowered_dispatch]
    if dispatch_hits:
        raise CheckFailure("future lesson apply/rollback route appears in CLI dispatch: " + ", ".join(dispatch_hits))

    forbidden_route_symbols = [
        r"def\s+lesson_candidates_apply\s*\(",
        r"def\s+lesson_candidates_apply_dry_run\s*\(",
        r"def\s+lesson_candidates_dry_run_apply\s*\(",
        r"def\s+lesson_candidates_apply_preflight\s*\(",
        r"def\s+lesson_candidates_preflight_apply\s*\(",
        r"def\s+lesson_candidates_rollback\s*\(",
        r"def\s+lesson_candidates_create\s*\(",
        r"def\s+lesson_candidates_review_approve_apply\s*\(",
    ]
    combined = app_text + "\n" + research_text
    hits = [pattern for pattern in forbidden_route_symbols if re.search(pattern, combined, re.IGNORECASE)]
    if hits:
        raise CheckFailure("future lesson apply route/path appears in active route source slice: " + ", ".join(hits))


def check_unapproved_routes_no_write() -> None:
    for command, title in ROUTES.items():
        before_tree = snapshot_sensitive_tree()
        before_forbidden = snapshot_forbidden()
        before_watched_reports = snapshot_watched_reports()
        before_reports = report_files()
        before_thought_files = snapshot_thought_inbox()
        before_thought_count = thought_inbox_count()
        output = run_engel(command)
        after_tree = snapshot_sensitive_tree()
        after_forbidden = snapshot_forbidden()
        after_watched_reports = snapshot_watched_reports()
        assert_no_tree_change(before_tree, after_tree, command)
        assert_no_tree_change(before_forbidden, after_forbidden, command + " forbidden targets")
        assert_no_tree_change(before_watched_reports, after_watched_reports, command + " watched reports")
        assert_thought_inbox_unchanged(before_thought_count, before_thought_files, command)
        if report_files() != before_reports:
            raise CheckFailure(command + " generated a report")
        assert_contains_ci(output, title, command)
        for token in REQUIRED_OUTPUT_TOKENS:
            assert_contains_ci(output, token, command)
        for category in EXPECTED_CANDIDATE_CATEGORIES:
            assert_contains_ci(output, category, command)
            assert_contains_ci(output, category + " (UNTRUSTED_CANDIDATE)", command)
        assert_contains_ci(output, "untrusted", command)
        assert_contains_ci(output, "local-only", command)
        assert_contains_ci(output, "older manual memory commands are not invoked", command)


def assert_readiness_output_contract(output: str) -> None:
    assert_contains_ci(output, "# Lesson Candidates Readiness Status", READINESS_ROUTE)
    for token in REQUIRED_READINESS_TOKENS:
        assert_contains_ci(output, token, READINESS_ROUTE)
    for phrase in [
        "What exists now",
        "Design-only",
        "Forbidden now",
        "Verifier coverage",
        "Future prerequisites before apply can be considered",
        "Current safe learning path",
        "lesson candidates status",
        "lesson candidates review",
        "lesson candidates review APPROVE_REPORT",
        "reports\\lesson_candidates\\",
        STANDARD_VERIFIER,
        "trusted apply",
        "rollback",
        "candidate identity artifacts",
        "target allowlist writes",
        "before/after audit writes",
        "approval-token handling",
        "lesson candidates apply",
        "lesson candidates apply APPROVE",
        "lesson candidates review APPROVE_APPLY",
        "lesson candidates rollback",
        "any candidate creation route",
        "trusted memory writes",
        "source edits",
        "route matrix mutation from lessons",
        "queues",
        "digest/history",
        "ALIVE_STATE",
        "providers",
        "loops",
        "background workers",
        "autonomy",
        "explicit separate apply implementation contract",
        "human approval token handling",
        "candidate identity artifact handling",
        "target allowlist enforcement",
        "before/after audit write design",
        "rollback/refusal behavior design",
        "dedicated apply verifier",
        "no forbidden flags enabled",
        "observe",
        "summarize",
        "review untrusted lesson candidates",
        "create explicit report-only artifact with APPROVE_REPORT",
        "no trusted writeback",
    ]:
        assert_contains_ci(output, phrase, READINESS_ROUTE)
    for forbidden_output in [
        "# Lesson Candidates Review Report Written",
        "LESSON_CANDIDATE_REVIEW_VERIFICATION_PASS",
        "generated_lesson_candidate_report=",
    ]:
        if forbidden_output in output:
            raise CheckFailure(READINESS_ROUTE + " appears to run a verifier or generate a report")


def assert_living_output_contract(output: str) -> None:
    assert_contains_ci(output, "# Engel Living Learning Status", LIVING_ROUTE)
    for token in REQUIRED_LIVING_TOKENS:
        assert_contains_ci(output, token, LIVING_ROUTE)
    for phrase in [
        "Proposal readiness",
        "colony proposal status",
        "colony proposal contract",
        "colony proposal preview",
        "colony proposal preview APPROVE_REPORT is explicit report-only",
        "Proposal candidates remain untrusted",
        "No proposal output becomes trusted memory or applied learning",
        "Lesson candidate readiness",
        "lesson candidates status",
        "lesson candidates review",
        "lesson candidates readiness status",
        "lesson candidates review APPROVE_REPORT is explicit report-only",
        "Lesson candidates remain untrusted",
        "Trusted apply remains absent",
        "Future trusted apply readiness",
        "Future apply contract exists as design-only metadata",
        "Target allowlist exists as design-only metadata",
        "Before/after audit contract exists as design-only metadata",
        "Candidate identity/schema exists as design-only metadata",
        "Rollback/refusal contract exists as design-only metadata",
        "CK dry-run preflight verifier exists as verifier-only",
        "No apply route exists",
        "No dry-run apply route exists",
        "No rollback route exists",
        "No candidate creation route exists",
        "Colony simulation readiness",
        "colony simulation status",
        "colony simulation contract",
        "Simulation remains read-only/contract-only",
        "No simulation preview exists",
        "No simulation report generation exists",
        "No simulation runtime exists",
        "No simulation autonomy exists",
        "Current safe learning path",
        "observe",
        "summarize",
        "review untrusted candidates",
        "create explicit report-only artifacts only through APPROVE_REPORT",
        "run verifiers externally",
        "require human approval before any future trusted writeback",
        "Forbidden actions",
        "trusted memory write",
        "source edit",
        "queue mutation",
        "digest/history write",
        "ALIVE_STATE write",
        "provider/API/network behavior",
        "background worker",
        "autonomous loop",
        "runtime autonomy",
        "Level 2 runtime",
        "old-provider/Ollama/local endpoint path",
        "silent manual memory command invocation",
        "Next human-approved growth step",
        "verifier-first/design-first",
    ]:
        assert_contains_ci(output, phrase, LIVING_ROUTE)
    for forbidden_output in [
        "# Lesson Candidates Review Report Written",
        "# Colony Proposal Preview Report Written",
        "LESSON_CANDIDATE_REVIEW_VERIFICATION_PASS",
        "generated_lesson_candidate_report=",
    ]:
        if forbidden_output in output:
            raise CheckFailure(LIVING_ROUTE + " appears to run a verifier or generate a report")


def assert_command_no_sensitive_file_change(command: str) -> str:
    before_tree = snapshot_sensitive_tree()
    before_forbidden = snapshot_forbidden()
    before_watched_reports = snapshot_watched_reports()
    before_reports = report_files()
    before_thought_files = snapshot_thought_inbox()
    before_thought_count = thought_inbox_count()
    output = run_engel(command)
    after_tree = snapshot_sensitive_tree()
    after_forbidden = snapshot_forbidden()
    after_watched_reports = snapshot_watched_reports()
    assert_no_tree_change(before_tree, after_tree, command)
    assert_no_tree_change(before_forbidden, after_forbidden, command + " forbidden targets")
    assert_no_tree_change(before_watched_reports, after_watched_reports, command + " watched reports")
    assert_thought_inbox_unchanged(before_thought_count, before_thought_files, command)
    if report_files() != before_reports:
        raise CheckFailure(command + " generated a lesson candidate report")
    return output


def check_readiness_status_no_write() -> None:
    output = assert_command_no_sensitive_file_change(READINESS_ROUTE)
    assert_readiness_output_contract(output)


def check_living_learning_status_no_write() -> None:
    output = assert_command_no_sensitive_file_change(LIVING_ROUTE)
    assert_living_output_contract(output)


def check_cf_readiness_safety_snapshot_routes() -> None:
    for command in CF_SNAPSHOT_ROUTES:
        output = assert_command_no_sensitive_file_change(command)
        if command == READINESS_ROUTE:
            assert_readiness_output_contract(output)
        if command in {"route regression status", "verification set status"}:
            assert_contains_ci(output, "does not generate reports", command)
            if "LESSON_CANDIDATE_REVIEW_VERIFICATION_PASS" in output:
                raise CheckFailure(command + " appears to run the lesson candidate verifier")
        if "# Lesson Candidates Review Report Written" in output:
            raise CheckFailure(command + " generated the approved lesson candidate report")


def check_cl_living_learning_safety_snapshot_routes() -> None:
    for command in CL_SNAPSHOT_ROUTES:
        output = assert_command_no_sensitive_file_change(command)
        if command == LIVING_ROUTE:
            assert_living_output_contract(output)
        if command == READINESS_ROUTE:
            assert_readiness_output_contract(output)
        if command in {"route regression status", "verification set status"}:
            assert_contains_ci(output, "does not generate reports", command)
            if "LESSON_CANDIDATE_REVIEW_VERIFICATION_PASS" in output:
                raise CheckFailure(command + " appears to run the lesson candidate verifier")
        for forbidden_output in [
            "# Lesson Candidates Review Report Written",
            "# Colony Proposal Preview Report Written",
            "generated_lesson_candidate_report=",
        ]:
            if forbidden_output in output:
                raise CheckFailure(command + " generated or surfaced report/verifier output")


def check_approved_report_only_route() -> Path:
    before_tree = snapshot_sensitive_tree()
    before_forbidden = snapshot_forbidden()
    before_reports = report_files()
    before_thought_files = snapshot_thought_inbox()
    before_thought_count = thought_inbox_count()
    output = run_engel("lesson candidates review APPROVE_REPORT")
    after_tree = snapshot_sensitive_tree()
    after_forbidden = snapshot_forbidden()
    after_reports = report_files()
    assert_thought_inbox_unchanged(before_thought_count, before_thought_files, "lesson candidates review APPROVE_REPORT")
    assert_no_tree_change(before_forbidden, after_forbidden, "lesson candidates review APPROVE_REPORT forbidden targets")
    new_reports = sorted(after_reports - before_reports)
    if len(new_reports) != 1:
        raise CheckFailure("APPROVE_REPORT should create exactly one lesson report, got " + str(len(new_reports)))
    report = new_reports[0]
    try:
        report.relative_to(REPORT_DIR)
    except ValueError as exc:
        raise CheckFailure("lesson report created outside reports\\lesson_candidates: " + str(report)) from exc
    assert_only_allowed_lesson_report(before_tree, after_tree, report)
    assert_contains_ci(output, "# Lesson Candidates Review Report Written", "APPROVE_REPORT output")
    assert_contains_ci(output, str(report), "APPROVE_REPORT output path")
    for token in REPORT_TOKENS:
        assert_contains_ci(output + "\n" + report.read_text(encoding="utf-8"), token, "APPROVE_REPORT report")
    report_text = report.read_text(encoding="utf-8")
    for category in EXPECTED_CANDIDATE_CATEGORIES:
        assert_contains_ci(report_text, category, "APPROVE_REPORT report category")
        assert_contains_ci(report_text, category + " (UNTRUSTED_CANDIDATE)", "APPROVE_REPORT report category trust label")
    for phrase in [
        "not trusted memory",
        "not applied lessons",
        "not source edits",
        "not queue mutations",
        "not digest/history writes",
        "not ALIVE_STATE writes",
        "no autonomy",
    ]:
        assert_contains_ci(report_text, phrase, "APPROVE_REPORT report strengthened disclaimer")
    return report


def function_slice(text: str, name: str) -> str:
    match = re.search(r"(?m)^def " + re.escape(name) + r"\(", text)
    if not match:
        raise CheckFailure("function not found: " + name)
    next_match = re.search(r"(?m)^def \w+\(", text[match.end() :])
    if not next_match:
        return text[match.start() :]
    return text[match.start() : match.end() + next_match.start()]


def source_between(text: str, start_marker: str, end_marker: str) -> str:
    start = text.find(start_marker)
    if start < 0:
        raise CheckFailure("source marker not found: " + start_marker)
    end = text.find(end_marker, start)
    if end < 0:
        return text[start:]
    return text[start:end]


def check_source_slice_guards() -> None:
    research_text = (APP_ROOT / "engel_research_brain_v2.py").read_text(encoding="utf-8", errors="ignore")
    app_text = (APP_ROOT / "engel_app.py").read_text(encoding="utf-8", errors="ignore")
    route_functions = [
        "_lesson_candidate_config",
        "_lesson_candidate_bool",
        "_lesson_candidate_int",
        "_lesson_candidate_list",
        "_lesson_candidate_config_lines",
        "_lesson_candidate_safety_lines",
        "_lesson_candidate_scan_dirs",
        "_lesson_candidate_allowed_file",
        "_lesson_candidate_header",
        "_lesson_candidate_scan",
        "_lesson_candidate_lines",
        "lesson_candidates_status",
        "lesson_candidates_readiness_status",
        "_lesson_candidates_review_text",
        "lesson_candidates_review_report_path",
        "lesson_candidates_review",
        "living_learning_status",
    ]
    route_source = "\n".join(function_slice(research_text, name) for name in route_functions)
    app_wrapper_source = source_between(app_text, "def lesson_candidates_status", "def colony_simulation_status")
    route_dispatch_source = source_between(app_text, 'if lower_msg == "lesson candidates status"', 'if lower_msg == "colony simulation status"')
    combined = route_source + "\n" + app_wrapper_source + "\n" + route_dispatch_source

    provider_hits = [pattern for pattern in PROVIDER_CALL_PATTERNS if pattern in combined]
    if provider_hits:
        raise CheckFailure("provider/live-research pattern found in lesson candidate source slice: " + ", ".join(provider_hits))
    background_hits = [pattern for pattern in BACKGROUND_PATTERNS if pattern in combined]
    if background_hits:
        raise CheckFailure("background pattern found in lesson candidate source slice: " + ", ".join(background_hits))
    for pattern in FORBIDDEN_DIRECT_WRITE_PATTERNS:
        if re.search(pattern, route_source):
            raise CheckFailure("forbidden direct write pattern found in lesson candidate source slice: " + pattern)
    manual_hits = [pattern for pattern in MANUAL_MEMORY_PATTERNS if pattern in route_source]
    if manual_hits:
        raise CheckFailure("manual memory pattern found in lesson candidate route source: " + ", ".join(manual_hits))

    write_text_occurrences = combined.count("write_text")
    if write_text_occurrences != combined.count("report_path.write_text"):
        raise CheckFailure("unexpected write_text occurrence in lesson candidate source slice")
    mkdir_occurrences = combined.count(".mkdir(")
    if mkdir_occurrences != combined.count("LESSON_CANDIDATE_REPORTS_DIR.mkdir("):
        raise CheckFailure("unexpected mkdir occurrence in lesson candidate source slice")
    for status_name in [
        "lesson_candidates_status",
        "lesson_candidates_readiness_status",
        "_lesson_candidates_review_text",
        "living_learning_status",
    ]:
        source = function_slice(research_text, status_name)
        if "write_text" in source or ".mkdir(" in source:
            raise CheckFailure(status_name + " must remain no-write")


def pass_check(name: str) -> None:
    print("PASS " + name)


def main() -> int:
    try:
        check_py_compile()
        pass_check("py_compile_lesson_candidate_targets")
        check_config_schema()
        pass_check("lesson_candidate_config_schema")
        check_staged_inactive()
        pass_check("STAGED_DRAFT_ACTIVE_false")
        check_no_activation_literals()
        pass_check("no_runtime_or_staged_activation_literal")
        check_no_active_old_provider()
        pass_check("no_active_old_provider_matches")
        check_manifest_alignment()
        pass_check("route_verification_manifest_includes_lesson_candidates")
        check_cg_documentation_drift_guard()
        pass_check("CG_lesson_candidate_readiness_documentation_drift_guard")
        check_ck_dry_run_preflight_documentation_alignment()
        pass_check("CK_dry_run_apply_preflight_documentation_alignment")
        check_cl_living_learning_documentation_alignment()
        pass_check("CL_living_learning_status_documentation_alignment")
        check_cm_living_learning_drift_guard()
        pass_check("CM_living_learning_status_drift_guard")
        check_cx_living_systems_map_drift_guard()
        pass_check("CX_living_systems_map_drift_guard")
        check_status_routes_no_reports()
        pass_check("verification_and_route_regression_status_no_lesson_reports")
        check_future_apply_routes_absent_from_source()
        pass_check("future_lesson_apply_routes_absent_from_source")
        check_source_slice_guards()
        pass_check("lesson_candidate_source_slice_guards")
        check_unapproved_routes_no_write()
        pass_check("lesson_candidate_unapproved_routes_no_write")
        check_readiness_status_no_write()
        pass_check("lesson_candidate_readiness_status_no_write")
        check_living_learning_status_no_write()
        pass_check("living_learning_status_no_write")
        check_cf_readiness_safety_snapshot_routes()
        pass_check("CF_readiness_related_routes_no_sensitive_file_changes")
        check_cl_living_learning_safety_snapshot_routes()
        pass_check("CL_living_learning_related_routes_no_sensitive_file_changes")
        report = check_approved_report_only_route()
        pass_check("lesson_candidate_approved_report_only_route")
    except CheckFailure as exc:
        print("FAIL " + str(exc), file=sys.stderr)
        return 1

    print("\nLESSON_CANDIDATE_REVIEW_VERIFICATION_PASS")
    print("generated_lesson_candidate_report=" + str(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

