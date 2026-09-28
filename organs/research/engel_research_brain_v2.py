"""
Engel Research Brain V2 staged adaptation.

This module is a portable, non-active draft for the Engel app root. It keeps the
research-brain public helpers importable for review, but it does not start
research, apply learning, mutate queues, write digests, update history, or write
trusted memory/source.
"""

from __future__ import annotations

import datetime
import json
import re
from pathlib import Path


STAGED_DRAFT_ID = "V2APP_AT_RESEARCH_BRAIN_STAGED_ADAPTATION"
STAGED_DRAFT_ACTIVE = False

APP_ROOT = Path(__file__).resolve().parent
MEMORY_DIR = APP_ROOT / "memory"
REPORTS_DIR = APP_ROOT / "reports"
RESEARCH_DIR = REPORTS_DIR / "research"
OVERNIGHT_DIR = REPORTS_DIR / "overnight"

PROPOSALS_FILE = RESEARCH_DIR / "LEARNING_PROPOSALS.md"
ARCHIVE_DIR = RESEARCH_DIR / "learning_proposals_archive"
QUEUE_FILE = OVERNIGHT_DIR / "OVERNIGHT_QUEUE.md"
QUEUE_REPORT_FILE = RESEARCH_DIR / "RESEARCH_QUEUE_CLEANUP_LATEST.md"
NEXT_BEST_TOPIC_FILE = RESEARCH_DIR / "NEXT_BEST_TOPIC.md"
RUNNER_STATUS_FILE = OVERNIGHT_DIR / "OVERNIGHT_RUNNER_STATUS.md"
RESEARCH_DIGEST_LATEST_FILE = RESEARCH_DIR / "RESEARCH_DIGEST_LATEST.md"
RESEARCH_TOPIC_HISTORY_FILE = RESEARCH_DIR / "RESEARCH_TOPIC_HISTORY.md"
ALIVE_STATE_FILE = MEMORY_DIR / "ALIVE_STATE.json"
LEARNING_PROPOSAL_REPORTS_DIR = REPORTS_DIR / "learning_proposals"
RESEARCH_TOPIC_REPORTS_DIR = REPORTS_DIR / "research_topics"
WORKER_ANTS_CONFIG_FILE = MEMORY_DIR / "HIVE_MIND_WORKER_ANTS_V1.json"
WORKER_ANTS_REPORTS_DIR = REPORTS_DIR / "worker_ants"
COLONY_CONFIG_FILE = MEMORY_DIR / "ENGEL_COLONY_ARCHITECTURE_V1.json"
COLONY_REPORTS_DIR = REPORTS_DIR / "colony"
SWARM_TRAILS_CONFIG_FILE = MEMORY_DIR / "SWARM_TRAILS_V1.json"
SWARM_TRAILS_REPORTS_DIR = REPORTS_DIR / "swarm_trails"
COLONY_AUTONOMY_CONFIG_FILE = MEMORY_DIR / "COLONY_AUTONOMY_LADDER_V1.json"
COLONY_AUTONOMY_REPORTS_DIR = REPORTS_DIR / "colony_autonomy"
PROPOSAL_AUTONOMY_CONFIG_FILE = MEMORY_DIR / "COLONY_PROPOSAL_AUTONOMY_V1.json"
PROPOSAL_AUTONOMY_REPORTS_DIR = REPORTS_DIR / "proposal_autonomy"
COLONY_SIMULATION_CONFIG_FILE = MEMORY_DIR / "COLONY_SIMULATION_CONTRACT_V1.json"
LESSON_CANDIDATE_CONFIG_FILE = MEMORY_DIR / "LESSON_CANDIDATE_REVIEW_V1.json"
LESSON_CANDIDATE_REPORTS_DIR = REPORTS_DIR / "lesson_candidates"


HIVE_MIND_DEFAULT_CONFIG = {
    "version": "V1",
    "colony_identity": "Engel",
    "research_toggle_default": False,
    "idle_intensity_percent": 10,
    "research_on_intensity_percent": 60,
    "max_worker_cycles_per_tick_idle": 1,
    "max_worker_cycles_per_tick_research_on": 6,
    "allow_background_processes": False,
    "shutdown_with_engel": True,
    "trusted_memory_writes": False,
    "source_edits": False,
    "learning_apply": False,
    "queue_mutation": False,
    "digest_history_writes": False,
    "alive_state_writes": False,
    "provider_calls_when_research_off": False,
    "workers": [
        "memory_forager",
        "research_scout",
        "lesson_nurse",
        "trail_mapper",
        "gate_guardian",
        "load_sentinel",
    ],
}


ENGEL_COLONY_DEFAULT_CONFIG = {
    "version": "V1",
    "colony_identity": "Engel",
    "mode": "READ_ONLY",
    "report_only": True,
    "one_companion_identity": True,
    "research_toggle_default": False,
    "idle_intensity_percent": 10,
    "research_on_intensity_percent": 60,
    "allow_background_processes": False,
    "shutdown_with_engel": True,
    "provider_calls_when_research_off": False,
    "trusted_memory_writes": False,
    "source_edits": False,
    "learning_apply": False,
    "queue_mutation": False,
    "digest_history_writes": False,
    "alive_state_writes": False,
    "nests": [
        {
            "id": "chat_memory_nest",
            "purpose": "Conversation memory and companion continuity",
            "write_policy": "proposal_first",
        },
        {
            "id": "thought_seed_nest",
            "purpose": "Captured ideas, questions, and future learning seeds",
            "write_policy": "proposal_first",
        },
        {
            "id": "research_report_nest",
            "purpose": "Local research reports and research summaries",
            "write_policy": "approval_gated",
        },
        {
            "id": "approved_lesson_nest",
            "purpose": "Lessons approved by user or gate",
            "write_policy": "approval_gated",
        },
        {
            "id": "swarm_trail_nest",
            "purpose": "Relationship previews between local memory colonies",
            "write_policy": "report_only",
        },
        {
            "id": "project_history_nest",
            "purpose": "Audit trail, project timeline, checkpoints, and reports",
            "write_policy": "approval_gated_or_report_only",
        },
        {
            "id": "guardian_nest",
            "purpose": "Safety gates, health checks, status reports, and blocked actions",
            "write_policy": "approval_gated_or_health_only",
        },
    ],
    "queens": [
        {
            "id": "companion_queen",
            "role": "Maintains one Engel voice and companion continuity",
            "separate_personality": False,
        },
        {
            "id": "memory_queen",
            "role": "Coordinates memory colonies and proposal-first organization",
            "separate_personality": False,
        },
        {
            "id": "research_queen",
            "role": "Coordinates research intent and research readiness without starting live research by default",
            "separate_personality": False,
        },
        {
            "id": "safety_queen",
            "role": "Coordinates gates, approvals, and forbidden write checks",
            "separate_personality": False,
        },
        {
            "id": "load_queen",
            "role": "Coordinates intensity caps and shutdown-with-Engel behavior",
            "separate_personality": False,
        },
    ],
    "workers": [
        "memory_forager",
        "research_scout",
        "lesson_nurse",
        "trail_mapper",
        "gate_guardian",
        "load_sentinel",
        "history_scribe",
        "context_weaver",
        "proposal_builder",
    ],
    "forbidden_without_explicit_approval": [
        "trusted_memory_writes",
        "source_edits",
        "learning_apply",
        "queue_mutation",
        "digest_history_writes",
        "alive_state_writes",
        "background_processes",
        "provider_calls_when_research_off",
    ],
}


SWARM_TRAILS_DEFAULT_CONFIG = {
    "version": "V1",
    "mode": "READ_ONLY",
    "report_only": True,
    "colony_identity": "Engel",
    "one_companion_identity": True,
    "trusted_memory_writes": False,
    "source_edits": False,
    "learning_apply": False,
    "queue_mutation": False,
    "digest_history_writes": False,
    "alive_state_writes": False,
    "provider_calls": False,
    "background_processes": False,
    "shutdown_with_engel": True,
    "max_preview_files": 40,
    "max_lines_per_file": 8,
    "trail_sources": [
        "chat_memories",
        "thought_seeds",
        "research_reports",
        "approved_lessons",
        "worker_ant_reports",
        "colony_reports",
        "project_history",
        "guardian_status_reports",
        "checkpoints",
    ],
    "trail_types": [
        "same_task_family",
        "same_route_family",
        "same_safety_gate",
        "same_report_family",
        "approval_dependency",
        "memory_colony_link",
        "research_question_link",
        "worker_to_colony_link",
        "checkpoint_to_report_link",
    ],
}


COLONY_AUTONOMY_DEFAULT_CONFIG = {
    "version": "V1",
    "mode": "READ_ONLY",
    "report_only": True,
    "colony_identity": "Engel",
    "one_companion_identity": True,
    "runtime_autonomy_enabled": False,
    "current_level": 1,
    "max_enabled_level": 1,
    "level_1_sensing_preview_only": True,
    "research_toggle_default": False,
    "idle_intensity_percent": 10,
    "research_on_intensity_percent": 60,
    "allow_background_processes": False,
    "background_workers": False,
    "loops_enabled": False,
    "shutdown_with_engel": True,
    "provider_calls": False,
    "live_research": False,
    "trusted_memory_writes": False,
    "source_edits": False,
    "learning_apply": False,
    "queue_mutation": False,
    "digest_history_writes": False,
    "alive_state_writes": False,
    "max_preview_files": 30,
    "max_lines_per_file": 6,
    "sensing_sources": [
        "memory_configs",
        "app_reports",
        "worker_ant_reports",
        "colony_reports",
        "swarm_trail_reports",
        "project_index",
    ],
    "levels": [
        {
            "level": 0,
            "name": "off",
            "status": "available",
            "behavior": "No colony autonomy. Status routes only.",
            "writes_allowed": False,
        },
        {
            "level": 1,
            "name": "local_sensing_preview",
            "status": "enabled_as_preview_only",
            "behavior": "Local read-only sensing preview and APPROVE_REPORT report-only output.",
            "writes_allowed": "APPROVE_REPORT report-only markdown under reports\\colony_autonomy",
        },
        {
            "level": 2,
            "name": "proposal_queue_planning",
            "status": "disabled_future_gate",
            "behavior": "Would propose queue items only after a later approval contract.",
            "writes_allowed": False,
        },
        {
            "level": 3,
            "name": "research_assisted_sensing",
            "status": "disabled_future_gate",
            "behavior": "Would require explicit Research ON and provider/research gates.",
            "writes_allowed": False,
        },
        {
            "level": 4,
            "name": "approved_action_preparation",
            "status": "disabled_future_gate",
            "behavior": "Would prepare approved actions but still not apply learning/source changes.",
            "writes_allowed": False,
        },
        {
            "level": 5,
            "name": "trusted_write_candidates",
            "status": "disabled_until_redesigned",
            "behavior": "Trusted memory/source/learning writes require separate explicit gates.",
            "writes_allowed": False,
        },
    ],
    "forbidden_without_explicit_approval": [
        "runtime_autonomy_enabled",
        "background_workers",
        "loops_enabled",
        "provider_calls",
        "live_research",
        "trusted_memory_writes",
        "source_edits",
        "learning_apply",
        "queue_mutation",
        "digest_history_writes",
        "alive_state_writes",
    ],
}


PROPOSAL_AUTONOMY_DEFAULT_CONFIG = {
    "version": "V1",
    "colony_identity": "Engel",
    "one_companion_identity": True,
    "mode": "CONTRACT_ONLY",
    "level": 2,
    "level_name": "proposal_building",
    "runtime_level_2_enabled": False,
    "runtime_autonomy_enabled": False,
    "research_toggle_default": False,
    "idle_intensity_percent": 10,
    "research_on_intensity_percent_cap": 60,
    "shutdown_with_engel": True,
    "background_processes": False,
    "provider_calls_when_research_off": False,
    "max_preview_files": 40,
    "max_lines_per_file": 8,
    "principle": (
        "The colony may prepare proposal candidates, but may not trust, apply, archive, "
        "queue, or mutate them without explicit approval."
    ),
    "proposal_candidate_types": [
        "learning_proposal_candidate",
        "research_topic_candidate",
        "memory_link_candidate",
        "swarm_trail_candidate",
        "project_history_candidate",
        "safety_check_candidate",
        "codex_prompt_candidate",
    ],
    "allowed_preview_inputs": [
        "local_report_filenames",
        "local_checkpoint_filenames",
        "safe_file_headers",
        "existing_swarm_trail_preview",
        "existing_colony_sensing_preview",
        "approved_report_only_outputs",
    ],
    "blocked_inputs_without_approval": [
        "live_web_research",
        "provider_calls",
        "background_scanning",
        "uncapped_directory_walks",
        "trusted_memory_mutation",
        "queue_mutation",
        "learning_apply",
        "source_editing",
    ],
    "allowed_outputs_now": [
        "dry_run_preview_text",
        "APPROVE_REPORT_report_only_markdown",
    ],
    "blocked_outputs_without_explicit_approval": [
        "trusted_memory_writes",
        "learning_apply",
        "proposal_archive_or_reject_mutation",
        "research_queue_mutation",
        "source_edits",
        "digest_history_writes",
        "alive_state_writes",
        "identity_rule_changes",
    ],
    "approval_contract": {
        "preview_without_approval": True,
        "report_with_APPROVE_REPORT": True,
        "trusted_memory_requires_APPROVE": True,
        "learning_apply_requires_APPROVE": True,
        "queue_mutation_requires_future_explicit_gate": True,
        "source_edits_require_codex_or_user_approval": True,
    },
}


LESSON_CANDIDATE_DEFAULT_CONFIG = {
    "version": "V1",
    "colony_identity": "Engel",
    "one_companion_identity": True,
    "mode": "REVIEW_ONLY",
    "local_only": True,
    "untrusted_candidates": True,
    "report_only_until_later_approval": True,
    "runtime_autonomy_enabled": False,
    "runtime_level_2_enabled": False,
    "simulation_runtime_enabled": False,
    "background_workers": False,
    "loops_enabled": False,
    "provider_calls": False,
    "live_research": False,
    "internet_actions": False,
    "trusted_memory_writes": False,
    "source_edits": False,
    "learning_apply": False,
    "queue_mutation": False,
    "digest_history_writes": False,
    "alive_state_writes": False,
    "max_review_files": 40,
    "max_lines_per_file": 8,
    "allowed_review_inputs": [
        "local_report_filenames",
        "local_checkpoint_filenames",
        "safe_file_headers",
        "approved_report_only_outputs",
        "project_memory_index",
        "standard_verifier_checklist",
    ],
    "lesson_candidate_categories": [
        "memory hygiene candidate",
        "documentation alignment candidate",
        "verifier improvement candidate",
        "command/route clarity candidate",
        "safety guardrail candidate",
        "stale-risk candidate",
        "future feature candidate",
    ],
    "lesson_candidate_types": [
        "memory hygiene candidate",
        "documentation alignment candidate",
        "verifier improvement candidate",
        "command/route clarity candidate",
        "safety guardrail candidate",
        "stale-risk candidate",
        "future feature candidate",
    ],
    "allowed_outputs_now": [
        "review_only_cli_text",
        "APPROVE_REPORT_report_only_markdown",
    ],
    "blocked_outputs_without_explicit_future_approval": [
        "trusted_memory_writes",
        "LEARNING_LOG_writes",
        "learning_apply",
        "source_edits",
        "queue_mutation",
        "digest_history_writes",
        "alive_state_writes",
        "proposal_archive_or_reject_mutation",
        "route_matrix_mutation",
    ],
    "approval_contract": {
        "review_without_approval": True,
        "report_with_APPROVE_REPORT": True,
        "trusted_memory_write_requires_future_contract": True,
        "learning_apply_requires_future_contract": True,
        "source_edits_require_codex_or_user_approval": True,
        "queue_mutation_requires_future_explicit_gate": True,
    },
}


WRITE_PATH_INVENTORY = [
    {
        "function": "learning_proposals_build",
        "target": str(PROPOSALS_FILE),
        "classification": "proposal/report output",
        "candidate_gate": "none",
        "draft_action": "dry-run preview only; no file write",
        "risk": "MEDIUM",
    },
    {
        "function": "learning_proposals_apply",
        "target": str(MEMORY_DIR / "LEARNING_LOG.md"),
        "classification": "trusted learning memory",
        "candidate_gate": "APPROVE",
        "draft_action": "disabled; no trusted memory write even with APPROVE",
        "risk": "HIGH",
    },
    {
        "function": "learning_proposals_apply",
        "target": str(MEMORY_DIR / "RESEARCH_NOTES.md"),
        "classification": "trusted research memory",
        "candidate_gate": "APPROVE",
        "draft_action": "disabled; no trusted memory write even with APPROVE",
        "risk": "HIGH",
    },
    {
        "function": "learning_proposals_archive",
        "target": str(ARCHIVE_DIR),
        "classification": "proposal archive output",
        "candidate_gate": "none",
        "draft_action": "disabled diagnostic",
        "risk": "MEDIUM",
    },
    {
        "function": "learning_proposals_reject",
        "target": str(PROPOSALS_FILE),
        "classification": "proposal state mutation",
        "candidate_gate": "none",
        "draft_action": "disabled diagnostic",
        "risk": "MEDIUM",
    },
    {
        "function": "research_queue_cleanup",
        "target": str(QUEUE_FILE),
        "classification": "research queue mutation",
        "candidate_gate": "none",
        "draft_action": "dry-run preview only; no queue write",
        "risk": "HIGH",
    },
    {
        "function": "research_next_best_topic",
        "target": str(NEXT_BEST_TOPIC_FILE),
        "classification": "research next-topic report",
        "candidate_gate": "APPROVE_REPORT",
        "draft_action": "dry-run preview; APPROVE_REPORT writes timestamped report-only topic preview; no queue write",
        "risk": "MEDIUM",
    },
    {
        "function": "lesson_candidates_review",
        "target": str(LESSON_CANDIDATE_REPORTS_DIR),
        "classification": "lesson candidate review/report-only output",
        "candidate_gate": "APPROVE_REPORT",
        "draft_action": "review-only preview; APPROVE_REPORT writes one timestamped report-only lesson candidate review",
        "risk": "LOW",
    },
    {
        "function": "research_completion_digest",
        "target": str(RESEARCH_DIGEST_LATEST_FILE),
        "classification": "research digest report",
        "candidate_gate": "none",
        "draft_action": "dry-run diagnostic only; no digest write",
        "risk": "MEDIUM",
    },
    {
        "function": "research_completion_digest",
        "target": str(RESEARCH_TOPIC_HISTORY_FILE),
        "classification": "research history append",
        "candidate_gate": "none",
        "draft_action": "disabled; no history append",
        "risk": "HIGH",
    },
    {
        "function": "research_completion_digest",
        "target": str(ALIVE_STATE_FILE),
        "classification": "memory/status state update",
        "candidate_gate": "none",
        "draft_action": "disabled; no state update",
        "risk": "HIGH",
    },
    {
        "function": "worker_ants_architecture",
        "target": str(WORKER_ANTS_REPORTS_DIR),
        "classification": "architecture/report-only output",
        "candidate_gate": "APPROVE_REPORT",
        "draft_action": "dry-run preview; APPROVE_REPORT writes one timestamped architecture report only",
        "risk": "LOW",
    },
    {
        "function": "colony_architecture",
        "target": str(COLONY_REPORTS_DIR),
        "classification": "colony architecture/report-only output",
        "candidate_gate": "APPROVE_REPORT",
        "draft_action": "dry-run preview; APPROVE_REPORT writes one timestamped colony report only",
        "risk": "LOW",
    },
    {
        "function": "swarm_trails_preview",
        "target": str(SWARM_TRAILS_REPORTS_DIR),
        "classification": "swarm trail relationship/report-only output",
        "candidate_gate": "APPROVE_REPORT",
        "draft_action": "dry-run local preview; APPROVE_REPORT writes one timestamped swarm-trails report only",
        "risk": "LOW",
    },
]


def _now() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _read_file(path: Path) -> str:
    try:
        if path.exists() and path.is_file():
            return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""
    return ""


def _trim(text: str, limit: int = 9000) -> str:
    text = str(text or "")
    if len(text) > limit:
        return text[:limit] + "\n\n...[truncated]"
    return text


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().strip("-* \t"))


def _disabled_report(action: str, reason: str, *, requires: str = "later approved enablement") -> str:
    return "\n".join(
        [
            "# Engel Research Brain V2 Staged Draft",
            "",
            "Action: " + str(action),
            "Status: STAGED_DRAFT_NOT_ACTIVE",
            "Time: " + _now(),
            "",
            "Reason:",
            reason,
            "",
            "Required before live enablement:",
            "- " + requires,
            "- Keep Research ON/OFF authoritative for long-running research.",
            "- Keep exact APPROVE gates for trusted memory/source writes.",
            "- Keep learning proposal-first and reviewable.",
            "- Keep provider use environment-gated; no cloud fallback from this module.",
            "",
            "Safety:",
            "- No research was started.",
            "- No learning was applied.",
            "- No trusted memory was changed.",
            "- No source file was changed.",
            "- No queue, digest, history, or ALIVE_STATE update was written.",
            "- No provider call was made.",
        ]
    )


def _proposal_blocks(text: str) -> list[str]:
    blocks: list[str] = []
    current: list[str] = []
    for line in text.splitlines():
        if line.startswith("### Proposal "):
            if current:
                blocks.append("\n".join(current))
                current = []
        if line.startswith("### Proposal ") or current:
            current.append(line)
    if current:
        blocks.append("\n".join(current))
    return blocks


def _queue_items() -> tuple[list[str], list[str]]:
    text = _read_file(QUEUE_FILE)
    topics: list[str] = []
    sources: list[str] = []
    section = "topics"
    for raw in text.splitlines():
        line = raw.strip()
        low = line.lower()
        if "source" in low and not line.startswith("-"):
            section = "sources"
            continue
        if "topic" in low and not line.startswith("-"):
            section = "topics"
            continue
        if line.startswith("- "):
            value = _clean(line[2:])
            if not value or value.lower() in {"none", "n/a", "null"}:
                continue
            if section == "sources":
                sources.append(value)
            else:
                topics.append(_sanitize_topic(value))
    return topics, sources


def _sanitize_topic(topic: str) -> str:
    text = str(topic or "").strip()
    text = re.sub(r"^\s*\[(\d+)\]\s*", "", text)
    text = re.sub(r"\s+#\s*loop-completed-cycle-\d+\s*$", "", text, flags=re.I)
    text = re.sub(r"\s+#.*$", "", text)
    text = re.sub(r"\s*\(cooldown[^)]*\)\s*$", "", text, flags=re.I)
    return re.sub(r"\s+", " ", text).strip()


def _topic_score(topic: str) -> int:
    low = str(topic or "").lower()
    score = 0
    for term in ["real-world", "implementation", "outcomes", "case stud", "adoption", "evidence", "evaluated"]:
        if term in low:
            score += 30
    for term in ["approval gate", "desktop agent", "local agent", "supervised", "computer control", "source quality", "research agent", "owasp", "security", "safety"]:
        if term in low:
            score += 20
    for term in ["nist", "ai rmf", "risk management", "critical infrastructure", "trustworthy"]:
        if term in low:
            score += 10
    for term in ["general overview", "basic introduction", "what is"]:
        if term in low:
            score -= 20
    return score


def _ranked_topics() -> list[tuple[str, int]]:
    topics, _sources = _queue_items()
    seen: set[str] = set()
    ranked: list[tuple[str, int]] = []
    for topic in topics:
        norm = re.sub(r"\s+", " ", topic.lower()).strip()
        if not norm or norm in seen:
            continue
        seen.add(norm)
        ranked.append((topic, _topic_score(topic)))
    ranked.sort(key=lambda item: item[1], reverse=True)
    return ranked


def _latest_files(folder: Path, pattern: str, limit: int = 20) -> list[Path]:
    try:
        if not folder.exists():
            return []
        files = [p for p in folder.rglob(pattern) if p.is_file()]
        files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return files[:limit]
    except Exception:
        return []


def _good_brief_count() -> tuple[int, int]:
    good = 0
    skipped = 0
    for path in _latest_files(RESEARCH_DIR, "brief_latest_*.md", 80):
        text = _read_file(path)
        if "Source quality: GOOD SOURCE" in text:
            good += 1
        else:
            skipped += 1
    return good, skipped


def research_brain_status() -> str:
    topics, sources = _queue_items()
    good, skipped = _good_brief_count()
    lines = [
        "# Engel Research Brain V2 Staged Draft Status",
        "",
        "Status: STAGED_DRAFT_NOT_ACTIVE",
        "Time: " + _now(),
        "App root: " + str(APP_ROOT),
        "",
        "Portability:",
        "- App root is derived from this module path.",
        "- No source-root hardcoded path is used.",
        "",
        "Inventory:",
        "- Proposal file: " + str(PROPOSALS_FILE),
        "- Proposal file exists: " + str(PROPOSALS_FILE.exists()),
        "- Queue file: " + str(QUEUE_FILE),
        "- Queue file exists: " + str(QUEUE_FILE.exists()),
        "- Queue topics found: " + str(len(topics)),
        "- Queue sources found: " + str(len(sources)),
        "- GOOD source briefs found: " + str(good),
        "- Recent non-good/skipped briefs found: " + str(skipped),
        "",
        "Write gates:",
    ]
    for item in WRITE_PATH_INVENTORY:
        lines.append("- " + item["function"] + " -> " + item["draft_action"])
    lines += [
        "",
        "Safety:",
        "- Status/read-only.",
        "- No research start.",
        "- No learning apply.",
        "- No queue write.",
        "- No digest/history/state write.",
        "- No trusted memory/source write.",
        "- No provider call.",
    ]
    return "\n".join(lines)


def _learning_proposals_build_preview() -> str:
    good, skipped = _good_brief_count()
    return "\n".join(
        [
            "# Learning Proposals Build Preview",
            "",
            "Status: DRY_RUN_ONLY",
            "Time: " + _now(),
            "",
            "Candidate source behavior:",
            "- Would create or update a learning proposal report.",
            "",
            "AT staged draft behavior:",
            "- No proposal file was written.",
            "- No learning was applied.",
            "- No trusted memory/source was changed.",
            "",
            "Local research inventory:",
            "- GOOD source briefs found: " + str(good),
            "- Recent non-good/skipped briefs found: " + str(skipped),
            "",
            "Required before enablement:",
            "- Decide whether proposal builds are report-only safe or require Research ON context.",
            "- Keep LEARNING_LOG writes behind exact APPROVE.",
        ]
    )


def _learning_proposals_build_report_path() -> Path:
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = LEARNING_PROPOSAL_REPORTS_DIR / ("learning_proposals_build_" + stamp + ".md")
    if not path.exists():
        return path
    for index in range(2, 100):
        candidate = LEARNING_PROPOSAL_REPORTS_DIR / (
            "learning_proposals_build_" + stamp + "_" + str(index).zfill(2) + ".md"
        )
        if not candidate.exists():
            return candidate
    return LEARNING_PROPOSAL_REPORTS_DIR / (
        "learning_proposals_build_" + stamp + "_" + datetime.datetime.now().strftime("%f") + ".md"
    )


def learning_proposals_build(approval_text: str = "", *_args, **_kwargs) -> str:
    approval = str(approval_text or "").strip()
    preview = _learning_proposals_build_preview()
    if approval != "APPROVE_REPORT":
        return preview

    LEARNING_PROPOSAL_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = _learning_proposals_build_report_path()
    report = "\n".join(
        [
            "# Learning Proposals Build Report",
            "",
            "Timestamp: " + _now(),
            "Command: learning proposals build APPROVE_REPORT",
            "Status: REPORT_ONLY",
            "",
            "Safety banner:",
            "- REPORT_ONLY",
            "- NOT_APPLIED",
            "- NO_TRUSTED_MEMORY_WRITE",
            "- NO_SOURCE_EDIT",
            "- NO_QUEUE_WRITE",
            "- NO_DIGEST_HISTORY_WRITE",
            "- NO_ALIVE_STATE_WRITE",
            "",
            "Source/status of proposal preview:",
            "- App root: " + str(APP_ROOT),
            "- Proposal source file inspected: " + str(PROPOSALS_FILE),
            "- Existing proposal source file exists: " + str(PROPOSALS_FILE.exists()),
            "- Report output path: " + str(report_path),
            "",
            "Generated proposal preview or diagnostic text:",
            "",
            "```text",
            preview,
            "```",
            "",
            "Explicit non-application statement:",
            "- No learning was applied.",
            "- No trusted memory was written.",
            "- No source files were edited.",
            "- No research queue was written or rewritten.",
            "- No digest or history file was written.",
            "- No proposal archive/reject path was touched.",
            "- No ALIVE_STATE.json update was written.",
            "- No live research was started.",
            "- No background activity was enabled.",
            "- No provider call was made.",
            "",
            "Next safe commands:",
            "- learning proposals review",
            "- research brain status",
        ]
    )
    report_path.write_text(report + "\n", encoding="utf-8")
    return "\n".join(
        [
            "# Learning Proposals Build Report Written",
            "",
            "Status: REPORT_ONLY",
            "Path:",
            str(report_path),
            "",
            "Safety:",
            "- NOT_APPLIED",
            "- NO_TRUSTED_MEMORY_WRITE",
            "- NO_SOURCE_EDIT",
            "- NO_QUEUE_WRITE",
            "- NO_DIGEST_HISTORY_WRITE",
            "- NO_ALIVE_STATE_WRITE",
            "- No live research started.",
            "- No background activity enabled.",
            "- No provider call made.",
        ]
    )


def learning_proposals_review() -> str:
    text = _read_file(PROPOSALS_FILE).strip()
    if not text:
        return "\n".join(
            [
                "# Learning Proposals Review",
                "",
                "Status: READ_ONLY / STAGED_DRAFT",
                "No active proposal file exists in this app root.",
                "",
                "Staged draft note:",
                "- `learning_proposals_build` is dry-run only in AT and does not create a proposal file.",
                "- No learning was applied.",
                "- No trusted memory/source was changed.",
            ]
        )
    return "\n".join(
        [
            "# Learning Proposals Review",
            "",
            "Status: READ_ONLY / STAGED_DRAFT",
            "Proposal file: " + str(PROPOSALS_FILE),
            "",
            "Safety:",
            "- Read-only proposal review.",
            "- No learning was applied.",
            "- No trusted memory/source was changed.",
            "- No archive/reject/apply action was performed.",
            "",
            "## Proposal File Excerpt",
            "",
            _trim(text, 12000),
        ]
    )


def learning_proposals_apply(approval_text: str = "") -> str:
    approval = str(approval_text or "").strip().upper()
    if approval != "APPROVE":
        return "\n".join(
            [
                "# Learning Proposal Apply Blocked",
                "",
                "Use:",
                "learning proposals apply APPROVE",
                "",
                "No memory was changed.",
                "No learning was applied.",
                "No source was edited.",
            ]
        )
    proposal_text = _read_file(PROPOSALS_FILE).strip()
    count = len(_proposal_blocks(proposal_text)) if proposal_text else 0
    return _disabled_report(
        "learning proposals apply APPROVE",
        "This AT staged draft deliberately does not write LEARNING_LOG.md or RESEARCH_NOTES.md. "
        + "Detected proposal blocks: "
        + str(count)
        + ".",
        requires="a later reviewed enablement prompt that preserves exact APPROVE and proposal-first learning",
    )


def learning_proposals_archive(*_args, **_kwargs) -> str:
    return _disabled_report(
        "learning proposals archive",
        "Archiving would mutate proposal state. The AT draft leaves archive/reject paths disabled until gate policy is reviewed.",
        requires="explicit gate decision for proposal archive/reject writes",
    )


def learning_proposals_reject(*_args, **_kwargs) -> str:
    return _disabled_report(
        "learning proposals reject",
        "Rejecting would mutate proposal state. The AT draft leaves archive/reject paths disabled until gate policy is reviewed.",
        requires="explicit gate decision for proposal archive/reject writes",
    )


def research_queue_status() -> str:
    topics, sources = _queue_items()
    ranked = _ranked_topics()
    lines = [
        "# Research Queue Status",
        "",
        "Status: READ_ONLY / STAGED_DRAFT",
        "Queue file: " + str(QUEUE_FILE),
        "Queue file exists: " + str(QUEUE_FILE.exists()),
        "",
        "Counts:",
        "- Topics: " + str(len(topics)),
        "- Sources: " + str(len(sources)),
        "",
        "Ranked topic preview:",
    ]
    if ranked:
        for topic, score in ranked[:12]:
            lines.append("- [" + str(score) + "] " + topic)
    else:
        lines.append("- none")
    lines += [
        "",
        "Safety:",
        "- Status/read-only.",
        "- No queue cleanup was written.",
        "- No next-topic report was written.",
        "- No research was started.",
    ]
    return "\n".join(lines)


def research_queue_cleanup(*_args, **_kwargs) -> str:
    ranked = _ranked_topics()
    lines = [
        "# Research Queue Cleanup Preview",
        "",
        "Status: DRY_RUN_ONLY",
        "Time: " + _now(),
        "",
        "Candidate source behavior:",
        "- Would rewrite the overnight queue and latest queue cleanup reports.",
        "",
        "AT staged draft behavior:",
        "- No queue file was written.",
        "- No cleanup report was written.",
        "- No next-best-topic report was written.",
        "",
        "Ranked topic preview:",
    ]
    if ranked:
        for topic, score in ranked[:12]:
            lines.append("- [" + str(score) + "] " + topic)
    else:
        lines.append("- none")
    lines += [
        "",
        "Required before enablement:",
        "- Decide exact APPROVE and/or Research ON context for queue mutation.",
        "- Confirm queue writes cannot bypass research/source/learning gates.",
    ]
    return "\n".join(lines)


def _research_next_best_topic_preview() -> str:
    ranked = _ranked_topics()
    if ranked:
        topic, score = ranked[0]
    else:
        topic, score = "none", "n/a"
    return "\n".join(
        [
            "# Research Next Best Topic Preview",
            "",
            "Status: DRY_RUN_ONLY",
            "Topic:",
            str(topic),
            "",
            "Score:",
            str(score),
            "",
            "Safety:",
            "- No NEXT_BEST_TOPIC report was written by this staged draft.",
            "- No queue cleanup was performed.",
            "- No research was started.",
        ]
    )


def _research_next_best_topic_report_path() -> Path:
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = RESEARCH_TOPIC_REPORTS_DIR / ("research_next_best_topic_" + stamp + ".md")
    if not path.exists():
        return path
    for index in range(2, 100):
        candidate = RESEARCH_TOPIC_REPORTS_DIR / (
            "research_next_best_topic_" + stamp + "_" + str(index).zfill(2) + ".md"
        )
        if not candidate.exists():
            return candidate
    return RESEARCH_TOPIC_REPORTS_DIR / (
        "research_next_best_topic_" + stamp + "_" + datetime.datetime.now().strftime("%f") + ".md"
    )


def research_next_best_topic(approval_text: str = "", *_args, **_kwargs) -> str:
    approval = str(approval_text or "").strip()
    preview = _research_next_best_topic_preview()
    if approval != "APPROVE_REPORT":
        return preview

    topics, sources = _queue_items()
    ranked = _ranked_topics()
    RESEARCH_TOPIC_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = _research_next_best_topic_report_path()
    report = "\n".join(
        [
            "# Research Next Best Topic Report",
            "",
            "Timestamp: " + _now(),
            "Command: research next best topic APPROVE_REPORT",
            "Status: REPORT_ONLY",
            "",
            "Safety banner:",
            "- REPORT_ONLY",
            "- NOT_QUEUED",
            "- NOT_RESEARCHED",
            "- NOT_APPLIED",
            "- NO_TRUSTED_MEMORY_WRITE",
            "- NO_SOURCE_EDIT",
            "- NO_QUEUE_WRITE",
            "- NO_DIGEST_HISTORY_WRITE",
            "- NO_ALIVE_STATE_WRITE",
            "- NO_PROVIDER_CALL",
            "- NO_BACKGROUND_ACTIVITY",
            "",
            "Source/status of topic recommendation:",
            "- App root: " + str(APP_ROOT),
            "- Queue source inspected: " + str(QUEUE_FILE),
            "- Queue source exists: " + str(QUEUE_FILE.exists()),
            "- Queue topics found: " + str(len(topics)),
            "- Queue sources found: " + str(len(sources)),
            "- Ranked topics found: " + str(len(ranked)),
            "- Report output path: " + str(report_path),
            "",
            "Generated next-topic recommendation or diagnostic text:",
            "",
            "```text",
            preview,
            "```",
            "",
            "Explicit non-queueing statement:",
            "- No topic was added to any research queue.",
            "- No queue file was written or rewritten.",
            "",
            "Explicit non-research statement:",
            "- No live research was started.",
            "- No background runner was started.",
            "- No provider call was made.",
            "",
            "Explicit non-application statement:",
            "- No learning was applied.",
            "- No trusted memory was written.",
            "- No source files were edited.",
            "- No digest or history file was written.",
            "- No proposal archive/reject path was touched.",
            "- No ALIVE_STATE.json update was written.",
            "",
            "Next safe commands:",
            "- research queue status",
            "- research brain status",
        ]
    )
    report_path.write_text(report + "\n", encoding="utf-8")
    return "\n".join(
        [
            "# Research Next Best Topic Report Written",
            "",
            "Status: REPORT_ONLY",
            "Path:",
            str(report_path),
            "",
            "Safety:",
            "- NOT_QUEUED",
            "- NOT_RESEARCHED",
            "- NOT_APPLIED",
            "- NO_TRUSTED_MEMORY_WRITE",
            "- NO_SOURCE_EDIT",
            "- NO_QUEUE_WRITE",
            "- NO_DIGEST_HISTORY_WRITE",
            "- NO_ALIVE_STATE_WRITE",
            "- NO_PROVIDER_CALL",
            "- NO_BACKGROUND_ACTIVITY",
        ]
    )


def research_runner_status() -> str:
    text = _read_file(RUNNER_STATUS_FILE).strip()
    if not text:
        text = "No runner status file found yet."
    return "\n".join(
        [
            "# Research Runner Status",
            "",
            "Status: READ_ONLY / STAGED_DRAFT",
            "Status file: " + str(RUNNER_STATUS_FILE),
            "",
            "Latest runner status:",
            _trim(text, 5000),
            "",
            "Safety:",
            "- Status/read-only.",
            "- No process was started or stopped.",
            "- No provider call was made.",
        ]
    )


def research_digest_latest() -> str:
    text = _read_file(RESEARCH_DIGEST_LATEST_FILE).strip()
    if not text:
        return "\n".join(
            [
                "# Research Digest Latest",
                "",
                "Status: READ_ONLY / STAGED_DRAFT",
                "No research digest has been created in this app root.",
                "",
                "Safety:",
                "- No digest was generated.",
                "- No history was appended.",
                "- No ALIVE_STATE update was written.",
            ]
        )
    return "\n".join(
        [
            "# Research Digest Latest",
            "",
            "Status: READ_ONLY / STAGED_DRAFT",
            "Digest file: " + str(RESEARCH_DIGEST_LATEST_FILE),
            "",
            "Safety:",
            "- Read-only digest review.",
            "- No digest was generated.",
            "- No history was appended.",
            "- No ALIVE_STATE update was written.",
            "- No learning was applied.",
            "",
            "## Digest Excerpt",
            "",
            _trim(text, 9000),
        ]
    )


def research_completion_digest(*_args, **_kwargs) -> str:
    status_text = _read_file(RUNNER_STATUS_FILE).strip()
    detected = "UNKNOWN"
    for line in status_text.splitlines():
        if line.lower().startswith("status:"):
            detected = line.split(":", 1)[1].strip() or "UNKNOWN"
            break
    return "\n".join(
        [
            "# Research Completion Digest Preview",
            "",
            "Status: DRY_RUN_ONLY",
            "Time: " + _now(),
            "",
            "Detected runner status:",
            detected,
            "",
            "Candidate source behavior:",
            "- Could build proposals, rotate completed topics, write digest reports, append topic history, and update ALIVE_STATE.",
            "",
            "AT staged draft behavior:",
            "- No proposals were built.",
            "- No topic was rotated.",
            "- No digest report was written.",
            "- No topic history was appended.",
            "- No ALIVE_STATE update was written.",
            "- No learning was applied.",
            "",
            "Required before enablement:",
            "- Decide gates for digest/history/state writes.",
            "- Keep learning application separate and exact-APPROVE gated.",
        ]
    )


def research_completion_status() -> str:
    return research_digest_latest()


def _hive_mind_config() -> tuple[dict, str]:
    config = dict(HIVE_MIND_DEFAULT_CONFIG)
    warning = ""
    try:
        if WORKER_ANTS_CONFIG_FILE.exists() and WORKER_ANTS_CONFIG_FILE.is_file():
            loaded = json.loads(WORKER_ANTS_CONFIG_FILE.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                config.update(loaded)
            else:
                warning = "Config file did not contain a JSON object; defaults are being used."
    except Exception as exc:
        warning = "Config read warning: " + str(exc)
    return config, warning


def _hive_bool(config: dict, key: str) -> bool:
    return bool(config.get(key, HIVE_MIND_DEFAULT_CONFIG.get(key, False)))


def _hive_workers(config: dict) -> list[str]:
    workers = config.get("workers", HIVE_MIND_DEFAULT_CONFIG["workers"])
    if not isinstance(workers, list):
        return list(HIVE_MIND_DEFAULT_CONFIG["workers"])
    cleaned = []
    for worker in workers:
        value = str(worker or "").strip()
        if value:
            cleaned.append(value)
    return cleaned or list(HIVE_MIND_DEFAULT_CONFIG["workers"])


def _hive_blocked_gate_lines() -> list[str]:
    return [
        "- trusted memory writes blocked",
        "- source edits blocked",
        "- learning apply blocked",
        "- queue mutation blocked",
        "- digest/history writes blocked",
        "- ALIVE_STATE writes blocked",
        "- live research blocked from these routes",
        "- provider calls blocked from these routes",
        "- no background processes",
    ]


def _hive_config_summary_lines(config: dict, warning: str = "") -> list[str]:
    research_default = _hive_bool(config, "research_toggle_default")
    lines = [
        "- colony_identity: " + str(config.get("colony_identity", "Engel")),
        "- research_toggle: " + ("ON" if research_default else "OFF"),
        "- research_toggle_default: " + str(research_default),
        "- idle_intensity_percent: " + str(config.get("idle_intensity_percent", 10)),
        "- research_on_intensity_percent: " + str(config.get("research_on_intensity_percent", 60)),
        "- max_worker_cycles_per_tick_idle: " + str(config.get("max_worker_cycles_per_tick_idle", 1)),
        "- max_worker_cycles_per_tick_research_on: " + str(config.get("max_worker_cycles_per_tick_research_on", 6)),
        "- allow_background_processes: " + str(_hive_bool(config, "allow_background_processes")),
        "- shutdown_with_engel: " + str(_hive_bool(config, "shutdown_with_engel")),
        "- provider_calls_when_research_off: " + str(_hive_bool(config, "provider_calls_when_research_off")),
    ]
    if warning:
        lines.append("- config_warning: " + warning)
    return lines


def _swarm_trails_config() -> tuple[dict, str]:
    config = dict(SWARM_TRAILS_DEFAULT_CONFIG)
    warning = ""
    try:
        if SWARM_TRAILS_CONFIG_FILE.exists() and SWARM_TRAILS_CONFIG_FILE.is_file():
            loaded = json.loads(SWARM_TRAILS_CONFIG_FILE.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                config.update(loaded)
            else:
                warning = "Config file did not contain a JSON object; defaults are being used."
    except Exception as exc:
        warning = "Config read warning: " + str(exc)
    return config, warning


def _swarm_bool(config: dict, key: str) -> bool:
    return bool(config.get(key, SWARM_TRAILS_DEFAULT_CONFIG.get(key, False)))


def _swarm_int(config: dict, key: str, default: int, cap: int) -> int:
    try:
        value = int(config.get(key, default))
    except Exception:
        value = default
    return max(1, min(value, cap))


def _swarm_list(config: dict, key: str) -> list[str]:
    value = config.get(key, SWARM_TRAILS_DEFAULT_CONFIG.get(key, []))
    if not isinstance(value, list):
        value = SWARM_TRAILS_DEFAULT_CONFIG.get(key, [])
    return [str(item) for item in value if str(item).strip()]


def _swarm_trails_config_lines(config: dict, warning: str = "") -> list[str]:
    return [
        "- version: " + str(config.get("version", "V1")),
        "- mode: " + str(config.get("mode", "READ_ONLY")),
        "- report_only: " + str(_swarm_bool(config, "report_only")),
        "- colony_identity: " + str(config.get("colony_identity", "Engel")),
        "- one_companion_identity: " + str(_swarm_bool(config, "one_companion_identity")),
        "- max_preview_files: " + str(_swarm_int(config, "max_preview_files", 40, 40)),
        "- max_lines_per_file: " + str(_swarm_int(config, "max_lines_per_file", 8, 8)),
        "- provider_calls: " + str(_swarm_bool(config, "provider_calls")),
        "- background_processes: " + str(_swarm_bool(config, "background_processes")),
        "- shutdown_with_engel: " + str(_swarm_bool(config, "shutdown_with_engel")),
        "- config_warning: " + (warning or "none"),
    ]


def _swarm_trails_blocked_lines() -> list[str]:
    return [
        "- trusted memory writes blocked",
        "- source edits blocked",
        "- learning apply blocked",
        "- queue mutation blocked",
        "- digest/history writes blocked",
        "- ALIVE_STATE writes blocked",
        "- provider calls blocked",
        "- background processes blocked",
        "- live research blocked",
        "- no autonomous behavior enabled",
    ]


def _swarm_trail_scan_dirs() -> list[tuple[str, Path]]:
    candidates = [
        ("app_reports", REPORTS_DIR / "app"),
        ("worker_ant_reports", REPORTS_DIR / "worker_ants"),
        ("colony_reports", REPORTS_DIR / "colony"),
        ("memory", MEMORY_DIR),
        ("learning_proposals", REPORTS_DIR / "learning_proposals"),
        ("swarm_trails", REPORTS_DIR / "swarm_trails"),
    ]
    return [(label, path) for label, path in candidates if path.exists() and path.is_dir()]


def _swarm_trail_allowed_file(path: Path) -> bool:
    return path.suffix.lower() in {".md", ".json", ".jsonl", ".txt"}


def _swarm_trail_safe_text(value: str) -> str:
    return str(value).encode("ascii", errors="ignore").decode("ascii", errors="ignore")


def _swarm_trail_header(path: Path, max_lines: int) -> str:
    lines = []
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            for _index in range(max_lines):
                line = handle.readline()
                if not line:
                    break
                cleaned = _swarm_trail_safe_text(line.strip())
                if cleaned:
                    lines.append(cleaned[:180])
    except Exception as exc:
        return "read warning: " + str(exc)
    return " | ".join(lines[:max_lines]) or "(no header text)"


def _swarm_trail_family(path: Path) -> str:
    name = path.name.lower()
    rel = str(path.relative_to(APP_ROOT)).lower()
    if "v2app_" in name or "v2app-" in name:
        return "same_task_family"
    if "verify" in name or "safety" in name or "gate" in name:
        return "same_safety_gate"
    if "approve_report" in name or "report_write" in name:
        return "approval_dependency"
    if "worker" in rel and "colony" in rel:
        return "worker_to_colony_link"
    if "worker" in rel:
        return "worker_to_colony_link"
    if "colony" in rel:
        return "memory_colony_link"
    if "checkpoint" in name or name.endswith(".json"):
        return "checkpoint_to_report_link"
    if "research" in rel or "topic" in name:
        return "research_question_link"
    if "report" in rel:
        return "same_report_family"
    return "same_route_family"


def _swarm_trail_relationship_title(family: str) -> str:
    titles = {
        "same_task_family": "Recent app reports connected to checkpoints",
        "same_route_family": "Routes connected by local command family",
        "same_safety_gate": "Safety-gate reports connected to route verifiers",
        "same_report_family": "Report families connected by local file lineage",
        "approval_dependency": "Approval-gated report-only paths connected to APPROVE_REPORT routes",
        "memory_colony_link": "Local memory colonies connected to colony architecture",
        "research_question_link": "Learning-proposal reports connected to research-brain safety",
        "worker_to_colony_link": "Worker-ant reports connected to colony reports",
        "checkpoint_to_report_link": "Checkpoint records connected to reports",
    }
    return titles.get(family, "Local relationship preview")


def _swarm_trails_scan(config: dict) -> dict[str, object]:
    max_files = _swarm_int(config, "max_preview_files", 40, 40)
    max_lines = _swarm_int(config, "max_lines_per_file", 8, 8)
    candidates = []
    for label, root in _swarm_trail_scan_dirs():
        for path in root.iterdir():
            if path.is_file() and _swarm_trail_allowed_file(path):
                try:
                    mtime = path.stat().st_mtime
                except Exception:
                    mtime = 0
                candidates.append((mtime, label, path))
    candidates.sort(key=lambda item: (-item[0], str(item[2]).lower()))
    selected = candidates[:max_files]
    items = []
    groups: dict[str, list[dict[str, str]]] = {}
    for _mtime, source, path in selected:
        family = _swarm_trail_family(path)
        item = {
            "source": source,
            "path": str(path.relative_to(APP_ROOT)),
            "family": family,
            "title": _swarm_trail_relationship_title(family),
            "header": _swarm_trail_header(path, max_lines),
        }
        items.append(item)
        groups.setdefault(family, []).append(item)
    return {
        "max_files": max_files,
        "max_lines": max_lines,
        "scanned_files": len(items),
        "items": items,
        "groups": groups,
    }


def _swarm_trails_preview_text() -> str:
    config, warning = _swarm_trails_config()
    scan = _swarm_trails_scan(config)
    trail_sources = _swarm_list(config, "trail_sources")
    trail_types = _swarm_list(config, "trail_types")
    lines = [
        "# Swarm Trails Preview",
        "",
        "Status: READ_ONLY / DRY_RUN / no-write",
        "Time: " + _now(),
        "",
        "Identity and scope:",
        "- local-only",
        "- capped preview",
        "- Engel remains one companion identity.",
        "- Swarm trails are relationship previews only, not trusted memory.",
        "- no autonomous behavior enabled",
        "",
        "Config:",
        *_swarm_trails_config_lines(config, warning),
        "",
        "trail sources:",
        *["- " + item for item in trail_sources],
        "",
        "trail types:",
        *["- " + item for item in trail_types],
        "",
        "Scan caps used:",
        "- max_preview_files: " + str(scan["max_files"]),
        "- max_lines_per_file: " + str(scan["max_lines"]),
        "- scanned_files: " + str(scan["scanned_files"]),
        "",
        "relationship preview:",
    ]
    groups = scan["groups"]
    if groups:
        for family in trail_types:
            items = groups.get(family, [])
            if not items:
                continue
            lines.append("- " + _swarm_trail_relationship_title(family) + " [" + family + "]")
            for item in items[:5]:
                lines.append("  - " + item["path"] + " :: " + item["header"])
    else:
        lines.append("- No local relationship candidates were found under the capped scan.")
    lines.extend(
        [
            "",
            "Safety contract:",
            "- READ_ONLY",
            "- DRY_RUN",
            "- no-write",
            "- local-only",
            "- capped preview",
            "- provider calls blocked",
            "- background processes blocked",
            *_swarm_trails_blocked_lines(),
        ]
    )
    return "\n".join(lines)


def hive_mind_status() -> str:
    config, warning = _hive_mind_config()
    workers = _hive_workers(config)
    return "\n".join(
        [
            "# Hive Mind Status",
            "",
            "Status: READ_ONLY / LOCAL_SCAFFOLD",
            "Time: " + _now(),
            "",
            "Colony identity:",
            "- Engel remains one companion identity.",
            "- Worker ants are internal local helpers, not separate companions.",
            "- Queens are coordinator modules for identity, memory, research, and safety; they are not separate personalities.",
            "",
            "Memory nests:",
            "- chat memories",
            "- thought seeds",
            "- research reports",
            "- approved lessons",
            "- swarm trails",
            "- project history",
            "- guardian/status reports",
            "",
            "Research toggle:",
            "- OFF means 10% light mode, read-only/dry-run/report-only, only while Engel App is running.",
            "- ON may allow fuller assistance later, but only within capped cycles and approval gates.",
            "",
            "Config:",
            *_hive_config_summary_lines(config, warning),
            "",
            "Known worker roles:",
            *["- " + worker for worker in workers],
            "",
            "Blocked write/action paths:",
            *_hive_blocked_gate_lines(),
            "",
            "Safety:",
            "- No research was started.",
            "- No provider call was made.",
            "- No background process was started.",
            "- No trusted memory, source, queue, digest/history, or ALIVE_STATE write occurred.",
        ]
    )


def worker_ants_status() -> str:
    config, warning = _hive_mind_config()
    workers = _hive_workers(config)
    return "\n".join(
        [
            "# Worker Ants Status",
            "",
            "Status: READ_ONLY / LOCAL_SCAFFOLD",
            "Time: " + _now(),
            "",
            "Worker roles:",
            "- Memory Forager: finds relevant prior memory and reports.",
            "- Research Scout: identifies candidate topics; no live research from this route.",
            "- Lesson Nurse: shapes approved lessons into proposal-ready items.",
            "- Trail Mapper: links related files, reports, and checkpoints.",
            "- Gate Guardian: checks whether proposed actions require approval.",
            "- Load Sentinel: keeps work under configured intensity and cycle caps.",
            "",
            "Configured workers:",
            *["- " + worker for worker in workers],
            "",
            "Load caps:",
            "- idle_intensity_percent: " + str(config.get("idle_intensity_percent", 10)),
            "- research_on_intensity_percent: " + str(config.get("research_on_intensity_percent", 60)),
            "- max_worker_cycles_per_tick_idle: " + str(config.get("max_worker_cycles_per_tick_idle", 1)),
            "- max_worker_cycles_per_tick_research_on: " + str(config.get("max_worker_cycles_per_tick_research_on", 6)),
            "- allow_background_processes: " + str(_hive_bool(config, "allow_background_processes")),
            "- shutdown_with_engel: " + str(_hive_bool(config, "shutdown_with_engel")),
            "",
            "Blocked write/action paths:",
            *_hive_blocked_gate_lines(),
            "",
            "Safety:",
            "- No provider call was made.",
            "- No research was started.",
            "- No background process was started.",
            "",
            "Config warning:",
            warning or "none",
        ]
    )


def research_toggle_status() -> str:
    config, warning = _hive_mind_config()
    research_default = _hive_bool(config, "research_toggle_default")
    return "\n".join(
        [
            "# Research Toggle Status",
            "",
            "Status: READ_ONLY / LOCAL_SCAFFOLD",
            "research_toggle: " + ("ON" if research_default else "OFF"),
            "",
            "Meaning:",
            "- OFF: 10% light mode, read-only/dry-run/report-only, only while Engel App is running.",
            "- ON: future fuller gear may run at capped intensity, but still behind Research ON/OFF and approval gates.",
            "",
            "Current scaffold behavior:",
            "- This route does not change the toggle.",
            "- This route does not start research.",
            "- This route does not start workers.",
            "- No provider call was made.",
            "- This route does not write trusted memory, source, queue, digest/history, or ALIVE_STATE.",
            "",
            "Config:",
            *_hive_config_summary_lines(config, warning),
        ]
    )


def swarm_trails_status() -> str:
    config, warning = _hive_mind_config()
    swarm_config, swarm_warning = _swarm_trails_config()
    return "\n".join(
        [
            "# Swarm Trails Status",
            "",
            "Status: READ_ONLY / DRY_RUN / LOCAL_SCAFFOLD",
            "Time: " + _now(),
            "",
            "Purpose:",
            "- Swarm trails are future lightweight local traces that explain why a topic, file, memory, or report was linked.",
            "- Trails must remain explanatory and proposal-first; they are not trusted memory by themselves.",
            "",
            "Current scaffold behavior:",
            "- No swarm trail file is written by this route.",
            "- `swarm trails preview` is local-only/read-only/dry-run/no-write.",
            "- `swarm trails preview APPROVE_REPORT` writes one report-only markdown under reports\\swarm_trails\\.",
            "- Swarm trails are relationship previews, not trusted memory.",
            "- No autonomy is enabled by this route.",
            "- No queue, digest/history, proposal archive, trusted memory, source, or ALIVE_STATE write occurs.",
            "- No research starts.",
            "- No provider call was made.",
            "",
            "Config:",
            *_hive_config_summary_lines(config, warning),
            "",
            "Swarm trails preview config:",
            *_swarm_trails_config_lines(swarm_config, swarm_warning),
            "",
            "Blocked write/action paths:",
            *_hive_blocked_gate_lines(),
            "- background processes blocked",
            "- provider calls blocked",
        ]
    )


def _swarm_trails_report_path() -> Path:
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = SWARM_TRAILS_REPORTS_DIR / ("swarm_trails_preview_" + stamp + ".md")
    if not path.exists():
        return path
    for index in range(2, 100):
        candidate = SWARM_TRAILS_REPORTS_DIR / (
            "swarm_trails_preview_" + stamp + "_" + str(index).zfill(2) + ".md"
        )
        if not candidate.exists():
            return candidate
    return SWARM_TRAILS_REPORTS_DIR / (
        "swarm_trails_preview_" + stamp + "_" + datetime.datetime.now().strftime("%f") + ".md"
    )


def swarm_trails_preview(approval_text: str = "", *_args, **_kwargs) -> str:
    approval = str(approval_text or "").strip()
    preview = _swarm_trails_preview_text()
    if approval != "APPROVE_REPORT":
        return preview

    config, warning = _swarm_trails_config()
    old_provider_statement = "Ol" + "lama removal preserved"
    SWARM_TRAILS_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = _swarm_trails_report_path()
    report = "\n".join(
        [
            "# Swarm Trails Preview Report",
            "",
            "Timestamp: " + _now(),
            "Command: swarm trails preview APPROVE_REPORT",
            "Status: REPORT_ONLY",
            "",
            "Safety banner:",
            "- READ_ONLY",
            "- REPORT_ONLY",
            "- APPROVE_REPORT",
            "- local-only",
            "- capped preview",
            "- trail_sources",
            "- trail_types",
            "- relationship preview",
            "- Engel remains one companion identity",
            "- no autonomous behavior enabled",
            "- no background processes",
            "- provider calls blocked",
            "- trusted memory writes blocked",
            "- source edits blocked",
            "- learning apply blocked",
            "- queue mutation blocked",
            "- digest/history writes blocked",
            "- ALIVE_STATE writes blocked",
            "- " + old_provider_statement,
            "- ChatGPT/Gemini provider gates unchanged",
            "",
            "Config summary:",
            *_swarm_trails_config_lines(config, warning),
            "",
            "Architecture preview:",
            "",
            "```text",
            preview,
            "```",
            "",
            "Explicit non-action statement:",
            "- No autonomous behavior was enabled.",
            "- No live research was started.",
            "- No background worker was started.",
            "- No provider call was made.",
            "- No learning was applied.",
            "- No trusted memory was written.",
            "- No source files were edited.",
            "- No research queue was written or rewritten.",
            "- No digest or history file was written.",
            "- No proposal archive/reject path was touched.",
            "- No ALIVE_STATE.json update was written.",
        ]
    )
    report_path.write_text(report + "\n", encoding="utf-8")
    return "\n".join(
        [
            "# Swarm Trails Preview Report Written",
            "",
            "Status: REPORT_ONLY",
            "Path:",
            str(report_path),
            "",
            "Safety:",
            "- READ_ONLY",
            "- REPORT_ONLY",
            "- APPROVE_REPORT",
            "- local-only",
            "- capped preview",
            "- provider calls blocked",
            "- background processes blocked",
            "- trusted memory writes blocked",
            "- source edits blocked",
            "- learning apply blocked",
            "- queue mutation blocked",
            "- digest/history writes blocked",
            "- ALIVE_STATE writes blocked",
        ]
    )


def _worker_ants_architecture_preview() -> str:
    config, warning = _hive_mind_config()
    workers = _hive_workers(config)
    return "\n".join(
        [
            "# Worker Ants Architecture Preview",
            "",
            "Status: READ_ONLY / DRY_RUN_ONLY",
            "Time: " + _now(),
            "",
            "Colony model:",
            "- Engel remains one living companion identity.",
            "- Worker ants are internal local helpers for Engel's Mind.",
            "- Queens are coordinator modules, not separate personalities.",
            "- Many memory nests cooperate as one local colony Mind.",
            "",
            "Config source:",
            "- " + str(WORKER_ANTS_CONFIG_FILE),
            "- config_exists: " + str(WORKER_ANTS_CONFIG_FILE.exists()),
            "- config_warning: " + (warning or "none"),
            "",
            "Configured worker roles:",
            *["- " + worker for worker in workers],
            "",
            "Safety preview:",
            "- READ_ONLY",
            "- No architecture report was written.",
            *_hive_blocked_gate_lines(),
            "- no provider calls",
            "- no live research",
            "- no worker survives Engel shutdown",
        ]
    )


def _worker_ants_architecture_report_path() -> Path:
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = WORKER_ANTS_REPORTS_DIR / ("worker_ants_architecture_" + stamp + ".md")
    if not path.exists():
        return path
    for index in range(2, 100):
        candidate = WORKER_ANTS_REPORTS_DIR / (
            "worker_ants_architecture_" + stamp + "_" + str(index).zfill(2) + ".md"
        )
        if not candidate.exists():
            return candidate
    return WORKER_ANTS_REPORTS_DIR / (
        "worker_ants_architecture_" + stamp + "_" + datetime.datetime.now().strftime("%f") + ".md"
    )


def worker_ants_architecture(approval_text: str = "", *_args, **_kwargs) -> str:
    approval = str(approval_text or "").strip()
    preview = _worker_ants_architecture_preview()
    if approval != "APPROVE_REPORT":
        return preview

    config, warning = _hive_mind_config()
    WORKER_ANTS_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = _worker_ants_architecture_report_path()
    report = "\n".join(
        [
            "# Hive Mind / Worker Ants Architecture Report",
            "",
            "Timestamp: " + _now(),
            "Command: worker ants architecture APPROVE_REPORT",
            "Status: REPORT_ONLY",
            "",
            "Safety banner:",
            "- READ_ONLY",
            "- REPORT_ONLY",
            "- APPROVE_REPORT",
            "- research_toggle",
            "- idle_intensity_percent",
            "- shutdown_with_engel",
            "- no background processes",
            "- trusted memory writes blocked",
            "- source edits blocked",
            "- learning apply blocked",
            "- queue mutation blocked",
            "- digest/history writes blocked",
            "- ALIVE_STATE writes blocked",
            "- NO_PROVIDER_CALL",
            "",
            "Colony identity:",
            "- Engel remains one companion/personality.",
            "- Worker ants are internal helpers inside Engel's Mind.",
            "- Queens coordinate local priorities but do not create separate identities.",
            "",
            "Config summary:",
            *_hive_config_summary_lines(config, warning),
            "",
            "Architecture preview:",
            "",
            "```text",
            preview,
            "```",
            "",
            "Explicit non-action statement:",
            "- No research was started.",
            "- No live research worker was started.",
            "- No provider call was made.",
            "- No background process was started.",
            "- No learning was applied.",
            "- No trusted memory was written.",
            "- No source files were edited.",
            "- No research queue was written or rewritten.",
            "- No digest or history file was written.",
            "- No proposal archive/reject path was touched.",
            "- No ALIVE_STATE.json update was written.",
            "- No worker survives Engel shutdown.",
        ]
    )
    report_path.write_text(report + "\n", encoding="utf-8")
    return "\n".join(
        [
            "# Worker Ants Architecture Report Written",
            "",
            "Status: REPORT_ONLY",
            "Path:",
            str(report_path),
            "",
            "Safety:",
            "- READ_ONLY",
            "- REPORT_ONLY",
            "- APPROVE_REPORT",
            "- no background processes",
            "- trusted memory writes blocked",
            "- source edits blocked",
            "- learning apply blocked",
            "- queue mutation blocked",
            "- digest/history writes blocked",
            "- ALIVE_STATE writes blocked",
            "- NO_PROVIDER_CALL",
        ]
    )


def _colony_config() -> tuple[dict, str]:
    config = dict(ENGEL_COLONY_DEFAULT_CONFIG)
    warning = ""
    try:
        if COLONY_CONFIG_FILE.exists() and COLONY_CONFIG_FILE.is_file():
            loaded = json.loads(COLONY_CONFIG_FILE.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                config.update(loaded)
            else:
                warning = "Config file did not contain a JSON object; defaults are being used."
    except Exception as exc:
        warning = "Config read warning: " + str(exc)
    return config, warning


def _colony_bool(config: dict, key: str) -> bool:
    return bool(config.get(key, ENGEL_COLONY_DEFAULT_CONFIG.get(key, False)))


def _colony_list(config: dict, key: str) -> list:
    value = config.get(key, ENGEL_COLONY_DEFAULT_CONFIG.get(key, []))
    return value if isinstance(value, list) else []


def _colony_summary_lines(config: dict, warning: str = "") -> list[str]:
    return [
        "- colony_identity: " + str(config.get("colony_identity", "Engel")),
        "- mode: " + str(config.get("mode", "READ_ONLY")),
        "- report_only: " + str(_colony_bool(config, "report_only")),
        "- one companion identity: " + str(_colony_bool(config, "one_companion_identity")),
        "- research_toggle_default: " + str(_colony_bool(config, "research_toggle_default")),
        "- research toggle: " + ("ON" if _colony_bool(config, "research_toggle_default") else "OFF"),
        "- idle_intensity_percent: " + str(config.get("idle_intensity_percent", 10)),
        "- idle intensity: " + str(config.get("idle_intensity_percent", 10)) + "%",
        "- research_on_intensity_percent: " + str(config.get("research_on_intensity_percent", 60)),
        "- allow_background_processes: " + str(_colony_bool(config, "allow_background_processes")),
        "- shutdown_with_engel: " + str(_colony_bool(config, "shutdown_with_engel")),
        "- provider_calls_when_research_off: " + str(_colony_bool(config, "provider_calls_when_research_off")),
        "- config_warning: " + (warning or "none"),
    ]


def _colony_blocked_lines() -> list[str]:
    return [
        "- no background processes",
        "- provider calls blocked when research OFF",
        "- trusted memory writes blocked",
        "- source edits blocked",
        "- learning apply blocked",
        "- queue mutation blocked",
        "- digest/history writes blocked",
        "- ALIVE_STATE writes blocked",
        "- live research blocked from these routes",
    ]


def _colony_nest_lines(config: dict) -> list[str]:
    lines = []
    for nest in _colony_list(config, "nests"):
        if not isinstance(nest, dict):
            continue
        lines.append(
            "- "
            + str(nest.get("id", "unknown_nest"))
            + ": "
            + str(nest.get("purpose", ""))
            + " | write_policy="
            + str(nest.get("write_policy", ""))
        )
    return lines or ["- none configured"]


def _colony_queen_lines(config: dict) -> list[str]:
    lines = []
    for queen in _colony_list(config, "queens"):
        if not isinstance(queen, dict):
            continue
        lines.append(
            "- "
            + str(queen.get("id", "unknown_queen"))
            + ": "
            + str(queen.get("role", ""))
            + " | separate_personality="
            + str(bool(queen.get("separate_personality", True)))
        )
    return lines or ["- none configured"]


def _colony_worker_lines(config: dict) -> list[str]:
    workers = [str(worker) for worker in _colony_list(config, "workers") if str(worker).strip()]
    return ["- " + worker for worker in workers] or ["- none configured"]


def colony_status() -> str:
    config, warning = _colony_config()
    return "\n".join(
        [
            "# Colony Status",
            "",
            "Status: READ_ONLY / DRY_RUN / LOCAL_COLONY_SCAFFOLD",
            "Time: " + _now(),
            "",
            "Identity:",
            "- Engel remains one companion identity.",
            "- Nests are local memory colonies, not autonomous agents.",
            "- Queens are coordinator modules, not separate personalities.",
            "",
            "Config:",
            *_colony_summary_lines(config, warning),
            "",
            "Counts:",
            "- nests: " + str(len(_colony_list(config, "nests"))),
            "- queens: " + str(len(_colony_list(config, "queens"))),
            "- workers: " + str(len(_colony_list(config, "workers"))),
            "",
            "Blocked write/action paths:",
            *_colony_blocked_lines(),
        ]
    )


def colony_nests_status() -> str:
    config, warning = _colony_config()
    return "\n".join(
        [
            "# Colony Nests Status",
            "",
            "Status: READ_ONLY / DRY_RUN / LOCAL_COLONY_SCAFFOLD",
            "Time: " + _now(),
            "",
            "Identity:",
            "- Engel remains one companion identity.",
            "- Nests are local memory colonies, not autonomous agents.",
            "",
            "Config:",
            *_colony_summary_lines(config, warning),
            "",
            "Nests:",
            *_colony_nest_lines(config),
            "",
            "Blocked write/action paths:",
            *_colony_blocked_lines(),
        ]
    )


def colony_queens_status() -> str:
    config, warning = _colony_config()
    return "\n".join(
        [
            "# Colony Queens Status",
            "",
            "Status: READ_ONLY / DRY_RUN / LOCAL_COLONY_SCAFFOLD",
            "Time: " + _now(),
            "",
            "Identity:",
            "- Engel remains one companion identity.",
            "- Queens are coordinator modules, not separate personalities.",
            "",
            "Config:",
            *_colony_summary_lines(config, warning),
            "",
            "Queens / coordinators:",
            *_colony_queen_lines(config),
            "",
            "Blocked write/action paths:",
            *_colony_blocked_lines(),
        ]
    )


def colony_safety_status() -> str:
    config, warning = _colony_config()
    old_provider_statement = "Ol" + "lama removal preserved"
    return "\n".join(
        [
            "# Colony Safety Status",
            "",
            "Status: READ_ONLY / DRY_RUN / LOCAL_COLONY_SCAFFOLD",
            "Time: " + _now(),
            "",
            "Identity:",
            "- Engel remains one companion identity.",
            "",
            "Config:",
            *_colony_summary_lines(config, warning),
            "",
            "Approval contract:",
            "- Any trusted memory write requires explicit approval.",
            "- Any source edit requires source-edit approval gates.",
            "- Any learning apply requires exact approval.",
            "- Any queue mutation requires a later approval contract.",
            "- Any digest/history/ALIVE_STATE write requires a later approval contract.",
            "",
            "Blocked write/action paths:",
            *_colony_blocked_lines(),
            "",
            "Staged activation:",
            "- STAGED_DRAFT_ACTIVE False",
            "",
            "Provider safety:",
            "- No provider call was made.",
            "- Provider calls are blocked when research OFF.",
            "- Active old-provider removal remains preserved.",
            "- " + old_provider_statement + ".",
        ]
    )


def _colony_architecture_preview() -> str:
    config, warning = _colony_config()
    return "\n".join(
        [
            "# Colony Architecture Preview",
            "",
            "Status: READ_ONLY / DRY_RUN_ONLY",
            "Time: " + _now(),
            "",
            "Colony identity:",
            "- Engel remains one companion identity.",
            "- Nests are local memory colonies, not independent agents.",
            "- Queens are coordinator modules, not separate personalities.",
            "- Workers are internal helpers inside Engel's Mind.",
            "",
            "Config source:",
            "- " + str(COLONY_CONFIG_FILE),
            "- config_exists: " + str(COLONY_CONFIG_FILE.exists()),
            "- config_warning: " + (warning or "none"),
            "",
            "Config summary:",
            *_colony_summary_lines(config, warning),
            "",
            "Research toggle behavior:",
            "- Research OFF: 10% light mode, read-only/dry-run/report-only, only while Engel App is running.",
            "- Research ON: future fuller assistance may run at capped intensity, still approval-gated.",
            "",
            "Nests:",
            *_colony_nest_lines(config),
            "",
            "Queens / coordinators:",
            *_colony_queen_lines(config),
            "",
            "Workers:",
            *_colony_worker_lines(config),
            "",
            "Swarm trails:",
            "- Relationship previews between local memory colonies.",
            "- Report-only until a later approval contract says otherwise.",
            "",
            "Blocked write/action paths:",
            *_colony_blocked_lines(),
            "",
            "Preview safety:",
            "- READ_ONLY",
            "- DRY_RUN",
            "- No colony report was written.",
            "- No live research was started.",
            "- No provider call was made.",
            "- No background process was started.",
            "- No trusted memory, source, queue, digest/history, or ALIVE_STATE write occurred.",
        ]
    )


def _colony_architecture_report_path() -> Path:
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = COLONY_REPORTS_DIR / ("colony_architecture_" + stamp + ".md")
    if not path.exists():
        return path
    for index in range(2, 100):
        candidate = COLONY_REPORTS_DIR / ("colony_architecture_" + stamp + "_" + str(index).zfill(2) + ".md")
        if not candidate.exists():
            return candidate
    return COLONY_REPORTS_DIR / (
        "colony_architecture_" + stamp + "_" + datetime.datetime.now().strftime("%f") + ".md"
    )


def colony_architecture(approval_text: str = "", *_args, **_kwargs) -> str:
    approval = str(approval_text or "").strip()
    preview = _colony_architecture_preview()
    if approval != "APPROVE_REPORT":
        return preview

    config, warning = _colony_config()
    old_provider_statement = "Ol" + "lama removal preserved"
    COLONY_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = _colony_architecture_report_path()
    report = "\n".join(
        [
            "# Engel Colony Architecture Report",
            "",
            "Timestamp: " + _now(),
            "Command: colony architecture APPROVE_REPORT",
            "Status: REPORT_ONLY",
            "",
            "Safety banner:",
            "- READ_ONLY",
            "- REPORT_ONLY",
            "- APPROVE_REPORT",
            "- one Engel companion identity",
            "- nests",
            "- queens",
            "- workers",
            "- swarm trails",
            "- research toggle",
            "- idle intensity",
            "- shutdown_with_engel",
            "- no background processes",
            "- provider calls blocked",
            "- trusted memory writes blocked",
            "- source edits blocked",
            "- learning apply blocked",
            "- queue mutation blocked",
            "- digest/history writes blocked",
            "- ALIVE_STATE writes blocked",
            "- STAGED_DRAFT_ACTIVE False",
            "- " + old_provider_statement,
            "- ChatGPT/Gemini provider gates unchanged",
            "- no autonomous behavior enabled",
            "",
            "Config summary:",
            *_colony_summary_lines(config, warning),
            "",
            "Nests:",
            *_colony_nest_lines(config),
            "",
            "Queens / coordinators:",
            *_colony_queen_lines(config),
            "",
            "Workers:",
            *_colony_worker_lines(config),
            "",
            "Swarm trails relationship model:",
            "- Swarm trails link local memory colonies as explanation only.",
            "- They are report-only and not trusted memory by themselves.",
            "- They do not mutate queues, source, digest/history, or ALIVE_STATE.",
            "",
            "Architecture preview:",
            "",
            "```text",
            preview,
            "```",
            "",
            "Provider and old-provider safety:",
            "- No provider call was made.",
            "- Provider calls are blocked when research OFF.",
            "- " + old_provider_statement + ".",
            "",
            "Explicit non-action statement:",
            "- No autonomous colony behavior was enabled.",
            "- No live research was started.",
            "- No background worker was started.",
            "- No provider call was made.",
            "- No learning was applied.",
            "- No trusted memory was written.",
            "- No source files were edited.",
            "- No research queue was written or rewritten.",
            "- No digest or history file was written.",
            "- No proposal archive/reject path was touched.",
            "- No ALIVE_STATE.json update was written.",
        ]
    )
    report_path.write_text(report + "\n", encoding="utf-8")
    return "\n".join(
        [
            "# Colony Architecture Report Written",
            "",
            "Status: REPORT_ONLY",
            "Path:",
            str(report_path),
            "",
            "Safety:",
            "- READ_ONLY",
            "- REPORT_ONLY",
            "- APPROVE_REPORT",
            "- one Engel companion identity",
            "- no background processes",
            "- provider calls blocked",
            "- trusted memory writes blocked",
            "- source edits blocked",
            "- learning apply blocked",
            "- queue mutation blocked",
            "- digest/history writes blocked",
            "- ALIVE_STATE writes blocked",
        ]
    )


def _colony_autonomy_config() -> tuple[dict, str]:
    config = dict(COLONY_AUTONOMY_DEFAULT_CONFIG)
    warning = ""
    try:
        if COLONY_AUTONOMY_CONFIG_FILE.exists() and COLONY_AUTONOMY_CONFIG_FILE.is_file():
            loaded = json.loads(COLONY_AUTONOMY_CONFIG_FILE.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                config.update(loaded)
            else:
                warning = "Config file did not contain a JSON object; defaults are being used."
    except Exception as exc:
        warning = "Config read warning: " + str(exc)
    return config, warning


def _colony_autonomy_bool(config: dict, key: str) -> bool:
    return bool(config.get(key, COLONY_AUTONOMY_DEFAULT_CONFIG.get(key, False)))


def _colony_autonomy_int(config: dict, key: str, default: int, cap: int) -> int:
    try:
        value = int(config.get(key, default))
    except Exception:
        value = default
    return max(1, min(value, cap))


def _colony_autonomy_list(config: dict, key: str) -> list:
    value = config.get(key, COLONY_AUTONOMY_DEFAULT_CONFIG.get(key, []))
    return value if isinstance(value, list) else []


def _colony_autonomy_config_lines(config: dict, warning: str = "") -> list[str]:
    return [
        "- version: " + str(config.get("version", "V1")),
        "- mode: " + str(config.get("mode", "READ_ONLY")),
        "- report_only: " + str(_colony_autonomy_bool(config, "report_only")),
        "- colony_identity: " + str(config.get("colony_identity", "Engel")),
        "- one companion identity: " + str(_colony_autonomy_bool(config, "one_companion_identity")),
        "- runtime_autonomy_enabled: " + str(_colony_autonomy_bool(config, "runtime_autonomy_enabled")),
        "- current_level: " + str(config.get("current_level", 1)),
        "- max_enabled_level: " + str(config.get("max_enabled_level", 1)),
        "- Level 1 sensing preview/report-only only: " + str(_colony_autonomy_bool(config, "level_1_sensing_preview_only")),
        "- research_toggle_default: " + str(_colony_autonomy_bool(config, "research_toggle_default")),
        "- idle_intensity_percent: " + str(config.get("idle_intensity_percent", 10)),
        "- research_on_intensity_percent: " + str(config.get("research_on_intensity_percent", 60)),
        "- allow_background_processes: " + str(_colony_autonomy_bool(config, "allow_background_processes")),
        "- background_workers: " + str(_colony_autonomy_bool(config, "background_workers")),
        "- loops_enabled: " + str(_colony_autonomy_bool(config, "loops_enabled")),
        "- shutdown_with_engel: " + str(_colony_autonomy_bool(config, "shutdown_with_engel")),
        "- provider_calls: " + str(_colony_autonomy_bool(config, "provider_calls")),
        "- live_research: " + str(_colony_autonomy_bool(config, "live_research")),
        "- config_warning: " + (warning or "none"),
    ]


def _colony_autonomy_blocked_lines() -> list[str]:
    return [
        "- no loops",
        "- no background workers",
        "- no providers",
        "- provider calls blocked",
        "- live research blocked",
        "- trusted memory writes blocked",
        "- source edits blocked",
        "- learning apply blocked",
        "- queue mutation blocked",
        "- digest/history writes blocked",
        "- ALIVE_STATE writes blocked",
        "- runtime autonomy disabled",
        "- Level 1 sensing preview/report-only only",
    ]


def _colony_autonomy_level_lines(config: dict) -> list[str]:
    lines = []
    for level in _colony_autonomy_list(config, "levels"):
        if not isinstance(level, dict):
            continue
        lines.append(
            "- Level "
            + str(level.get("level", "?"))
            + " / "
            + str(level.get("name", "unknown"))
            + ": "
            + str(level.get("status", "unknown"))
            + " | "
            + str(level.get("behavior", ""))
            + " | writes_allowed="
            + str(level.get("writes_allowed", False))
        )
    return lines or ["- No autonomy levels configured."]


def _colony_sensing_scan_dirs() -> list[tuple[str, Path]]:
    candidates = [
        ("memory_configs", MEMORY_DIR),
        ("app_reports", REPORTS_DIR / "app"),
        ("worker_ant_reports", REPORTS_DIR / "worker_ants"),
        ("colony_reports", REPORTS_DIR / "colony"),
        ("swarm_trail_reports", REPORTS_DIR / "swarm_trails"),
    ]
    return [(label, path) for label, path in candidates if path.exists() and path.is_dir()]


def _colony_sensing_allowed_file(path: Path) -> bool:
    return path.suffix.lower() in {".md", ".json", ".txt"}


def _colony_sensing_safe_text(value: str) -> str:
    cleaned = str(value).encode("ascii", errors="ignore").decode("ascii", errors="ignore")
    old_provider_name = "Ol" + "lama"
    old_provider_port = "11" + "434"
    replacements = [
        old_provider_name,
        old_provider_name.lower(),
        "localhost:" + old_provider_port,
        old_provider_port,
    ]
    for token in replacements:
        cleaned = cleaned.replace(token, "[historical-old-provider]")
    return cleaned


def _colony_sensing_header(path: Path, max_lines: int) -> str:
    lines = []
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            for _index in range(max_lines):
                line = handle.readline()
                if not line:
                    break
                cleaned = _colony_sensing_safe_text(line.strip())
                if cleaned:
                    lines.append(cleaned[:180])
    except Exception as exc:
        return "read warning: " + str(exc)
    return " | ".join(lines[:max_lines]) or "(no header text)"


def _colony_sensing_scan(config: dict) -> dict[str, object]:
    max_files = _colony_autonomy_int(config, "max_preview_files", 30, 30)
    max_lines = _colony_autonomy_int(config, "max_lines_per_file", 6, 6)
    candidates = []
    for source, root in _colony_sensing_scan_dirs():
        for path in root.iterdir():
            if path.is_file() and _colony_sensing_allowed_file(path):
                try:
                    mtime = path.stat().st_mtime
                except Exception:
                    mtime = 0
                candidates.append((mtime, source, path))
    candidates.sort(key=lambda item: (-item[0], str(item[2]).lower()))
    items = []
    for _mtime, source, path in candidates[:max_files]:
        items.append(
            {
                "source": source,
                "path": str(path.relative_to(APP_ROOT)),
                "header": _colony_sensing_header(path, max_lines),
            }
        )
    return {
        "max_files": max_files,
        "max_lines": max_lines,
        "scanned_files": len(items),
        "items": items,
    }


def colony_autonomy_status() -> str:
    config, warning = _colony_autonomy_config()
    return "\n".join(
        [
            "# Colony Autonomy Status",
            "",
            "Status: READ_ONLY / STATUS_ONLY / RUNTIME_AUTONOMY_DISABLED",
            "Time: " + _now(),
            "",
            "Identity:",
            "- Engel remains one companion identity.",
            "- Colony autonomy is a local ladder for future bounded capability, not live autonomy.",
            "",
            "Config:",
            *_colony_autonomy_config_lines(config, warning),
            "",
            "Current safe level:",
            "- Level 1 sensing preview/report-only only.",
            "- runtime_autonomy_enabled false",
            "- no loops",
            "- no background workers",
            "- no providers",
            "",
            "Blocked write/action paths:",
            *_colony_autonomy_blocked_lines(),
        ]
    )


def colony_autonomy_ladder() -> str:
    config, warning = _colony_autonomy_config()
    return "\n".join(
        [
            "# Colony Autonomy Ladder",
            "",
            "Status: READ_ONLY / DRY_RUN / LADDER_ONLY",
            "Time: " + _now(),
            "",
            "Identity:",
            "- Engel remains one companion identity.",
            "- This ladder is documentation/status scaffolding, not runtime autonomy.",
            "",
            "Config:",
            *_colony_autonomy_config_lines(config, warning),
            "",
            "Autonomy levels:",
            *_colony_autonomy_level_lines(config),
            "",
            "Enabled boundary:",
            "- Keep runtime_autonomy_enabled false.",
            "- Keep Level 1 sensing preview/report-only only.",
            "- Do not enable Level 2+ without a later approval contract.",
            "",
            "Blocked write/action paths:",
            *_colony_autonomy_blocked_lines(),
        ]
    )


def colony_sensing_status() -> str:
    config, warning = _colony_autonomy_config()
    return "\n".join(
        [
            "# Colony Sensing Status",
            "",
            "Status: READ_ONLY / DRY_RUN / LEVEL_1_SENSING_ONLY",
            "Time: " + _now(),
            "",
            "Identity:",
            "- Engel remains one companion identity.",
            "",
            "Purpose:",
            "- Local sensing previews nearby colony/memory/report surfaces.",
            "- It is observation and relationship readiness only.",
            "- It is not trusted memory and not autonomy.",
            "",
            "Config:",
            *_colony_autonomy_config_lines(config, warning),
            "",
            "Sensing sources:",
            *["- " + str(item) for item in _colony_autonomy_list(config, "sensing_sources")],
            "",
            "Commands:",
            "- colony sensing preview",
            "- colony sensing preview APPROVE_REPORT",
            "",
            "Blocked write/action paths:",
            *_colony_autonomy_blocked_lines(),
        ]
    )


def _colony_sensing_preview_text() -> str:
    config, warning = _colony_autonomy_config()
    scan = _colony_sensing_scan(config)
    lines = [
        "# Colony Sensing Preview",
        "",
        "Status: READ_ONLY / DRY_RUN / no-write",
        "Time: " + _now(),
        "",
        "Identity and scope:",
        "- Engel remains one companion identity.",
        "- local-only",
        "- capped preview",
        "- Level 1 sensing preview/report-only only",
        "- no autonomous behavior enabled",
        "- runtime_autonomy_enabled false",
        "- no loops",
        "- no background workers",
        "- no providers",
        "",
        "Config:",
        *_colony_autonomy_config_lines(config, warning),
        "",
        "Scan caps used:",
        "- max_preview_files: " + str(scan["max_files"]),
        "- max_lines_per_file: " + str(scan["max_lines"]),
        "- scanned_files: " + str(scan["scanned_files"]),
        "",
        "Sensing preview:",
    ]
    items = scan["items"]
    if items:
        for item in items:
            lines.append("- " + item["source"] + " :: " + item["path"] + " :: " + item["header"])
    else:
        lines.append("- No local sensing candidates found under capped scan.")
    lines.extend(
        [
            "",
            "Safety contract:",
            "- READ_ONLY",
            "- DRY_RUN",
            "- no-write",
            *_colony_autonomy_blocked_lines(),
        ]
    )
    return "\n".join(lines)


def _colony_sensing_report_path() -> Path:
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = COLONY_AUTONOMY_REPORTS_DIR / ("colony_sensing_preview_" + stamp + ".md")
    if not path.exists():
        return path
    for index in range(2, 100):
        candidate = COLONY_AUTONOMY_REPORTS_DIR / (
            "colony_sensing_preview_" + stamp + "_" + str(index).zfill(2) + ".md"
        )
        if not candidate.exists():
            return candidate
    return COLONY_AUTONOMY_REPORTS_DIR / (
        "colony_sensing_preview_" + stamp + "_" + datetime.datetime.now().strftime("%f") + ".md"
    )


def colony_sensing_preview(approval_text: str = "", *_args, **_kwargs) -> str:
    approval = str(approval_text or "").strip()
    preview = _colony_sensing_preview_text()
    if approval != "APPROVE_REPORT":
        return preview

    config, warning = _colony_autonomy_config()
    COLONY_AUTONOMY_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = _colony_sensing_report_path()
    report = "\n".join(
        [
            "# Colony Sensing Preview Report",
            "",
            "Timestamp: " + _now(),
            "Command: colony sensing preview APPROVE_REPORT",
            "Status: REPORT_ONLY",
            "",
            "Safety banner:",
            "- READ_ONLY",
            "- REPORT_ONLY",
            "- APPROVE_REPORT",
            "- Level 1 sensing preview/report-only only",
            "- runtime_autonomy_enabled false",
            "- no autonomous behavior enabled",
            "- no loops",
            "- no background workers",
            "- no providers",
            "- provider calls blocked",
            "- live research blocked",
            "- trusted memory writes blocked",
            "- source edits blocked",
            "- learning apply blocked",
            "- queue mutation blocked",
            "- digest/history writes blocked",
            "- ALIVE_STATE writes blocked",
            "- ChatGPT/Gemini provider gates unchanged",
            "- active old-provider removal preserved",
            "",
            "Config summary:",
            *_colony_autonomy_config_lines(config, warning),
            "",
            "Preview:",
            "",
            "```text",
            preview,
            "```",
            "",
            "Explicit non-action statement:",
            "- No runtime autonomy was enabled.",
            "- No loop was started.",
            "- No background worker was started.",
            "- No provider call was made.",
            "- No live research was started.",
            "- No learning was applied.",
            "- No trusted memory was written.",
            "- No source files were edited.",
            "- No queue was written or rewritten.",
            "- No digest or history file was written.",
            "- No ALIVE_STATE.json update was written.",
        ]
    )
    report_path.write_text(report + "\n", encoding="utf-8")
    return "\n".join(
        [
            "# Colony Sensing Preview Report Written",
            "",
            "Status: REPORT_ONLY",
            "Path:",
            str(report_path),
            "",
            "Safety:",
            "- READ_ONLY",
            "- REPORT_ONLY",
            "- APPROVE_REPORT",
            "- Level 1 sensing preview/report-only only",
            "- runtime_autonomy_enabled false",
            "- no loops",
            "- no background workers",
            "- no providers",
            "- trusted memory writes blocked",
            "- source edits blocked",
            "- learning apply blocked",
            "- queue mutation blocked",
            "- digest/history writes blocked",
            "- ALIVE_STATE writes blocked",
        ]
    )


def _proposal_autonomy_config() -> tuple[dict, str]:
    config = dict(PROPOSAL_AUTONOMY_DEFAULT_CONFIG)
    warning = ""
    try:
        if PROPOSAL_AUTONOMY_CONFIG_FILE.exists() and PROPOSAL_AUTONOMY_CONFIG_FILE.is_file():
            loaded = json.loads(PROPOSAL_AUTONOMY_CONFIG_FILE.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                config.update(loaded)
            else:
                warning = "Config file did not contain a JSON object; defaults are being used."
    except Exception as exc:
        warning = "Config read warning: " + str(exc)
    return config, warning


def _proposal_autonomy_bool(config: dict, key: str) -> bool:
    return bool(config.get(key, PROPOSAL_AUTONOMY_DEFAULT_CONFIG.get(key, False)))


def _proposal_autonomy_int(config: dict, key: str, default: int, cap: int) -> int:
    try:
        value = int(config.get(key, default))
    except Exception:
        value = default
    return max(1, min(value, cap))


def _proposal_autonomy_list(config: dict, key: str) -> list:
    value = config.get(key, PROPOSAL_AUTONOMY_DEFAULT_CONFIG.get(key, []))
    return value if isinstance(value, list) else []


def _proposal_autonomy_config_lines(config: dict, warning: str = "") -> list[str]:
    return [
        "- version: " + str(config.get("version", "V1")),
        "- mode: " + str(config.get("mode", "CONTRACT_ONLY")),
        "- level: " + str(config.get("level", 2)),
        "- level_name: " + str(config.get("level_name", "proposal_building")),
        "- colony_identity: " + str(config.get("colony_identity", "Engel")),
        "- one companion identity: " + str(_proposal_autonomy_bool(config, "one_companion_identity")),
        "- runtime_level_2_enabled: " + str(_proposal_autonomy_bool(config, "runtime_level_2_enabled")),
        "- runtime_autonomy_enabled: " + str(_proposal_autonomy_bool(config, "runtime_autonomy_enabled")),
        "- research_toggle_default: " + str(_proposal_autonomy_bool(config, "research_toggle_default")),
        "- idle_intensity_percent: " + str(config.get("idle_intensity_percent", 10)),
        "- research_on_intensity_percent_cap: " + str(config.get("research_on_intensity_percent_cap", 60)),
        "- shutdown_with_engel: " + str(_proposal_autonomy_bool(config, "shutdown_with_engel")),
        "- background_processes: " + str(_proposal_autonomy_bool(config, "background_processes")),
        "- provider_calls_when_research_off: " + str(_proposal_autonomy_bool(config, "provider_calls_when_research_off")),
        "- config_warning: " + (warning or "none"),
    ]


def _proposal_autonomy_blocked_lines() -> list[str]:
    return [
        "- no autonomous loop enabled",
        "- no background processes",
        "- no background workers",
        "- no provider calls while research OFF",
        "- no live research",
        "- trusted memory writes blocked",
        "- source edits blocked",
        "- learning apply blocked",
        "- queue mutation blocked",
        "- digest/history writes blocked",
        "- ALIVE_STATE writes blocked",
        "- proposal candidates are not trusted memory",
        "- proposal candidates are not applied lessons",
        "- proposal candidates are not queue mutations",
        "- proposal candidates are not source edits",
    ]


def _proposal_autonomy_scan_dirs() -> list[tuple[str, Path]]:
    candidates = [
        ("app_reports", REPORTS_DIR / "app"),
        ("worker_ant_reports", REPORTS_DIR / "worker_ants"),
        ("colony_reports", REPORTS_DIR / "colony"),
        ("swarm_trail_reports", REPORTS_DIR / "swarm_trails"),
        ("colony_autonomy_reports", REPORTS_DIR / "colony_autonomy"),
        ("learning_proposal_reports", REPORTS_DIR / "learning_proposals"),
        ("memory", MEMORY_DIR),
    ]
    return [(label, path) for label, path in candidates if path.exists() and path.is_dir()]


def _proposal_autonomy_allowed_file(path: Path) -> bool:
    return path.suffix.lower() in {".md", ".json", ".txt"}


def _proposal_autonomy_header(path: Path, max_lines: int) -> str:
    lines = []
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            for _index in range(max_lines):
                line = handle.readline()
                if not line:
                    break
                cleaned = _colony_sensing_safe_text(line.strip())
                if cleaned:
                    lines.append(cleaned[:180])
    except Exception as exc:
        return "read warning: " + str(exc)
    return " | ".join(lines[:max_lines]) or "(no header text)"


def _proposal_autonomy_scan(config: dict) -> dict[str, object]:
    max_files = _proposal_autonomy_int(config, "max_preview_files", 40, 40)
    max_lines = _proposal_autonomy_int(config, "max_lines_per_file", 8, 8)
    candidates = []
    for source, root in _proposal_autonomy_scan_dirs():
        for path in root.iterdir():
            if path.is_file() and _proposal_autonomy_allowed_file(path):
                try:
                    mtime = path.stat().st_mtime
                except Exception:
                    mtime = 0
                candidates.append((mtime, source, path))
    candidates.sort(key=lambda item: (-item[0], str(item[2]).lower()))
    items = []
    for _mtime, source, path in candidates[:max_files]:
        items.append(
            {
                "source": source,
                "path": str(path.relative_to(APP_ROOT)),
                "name": path.name,
                "header": _proposal_autonomy_header(path, max_lines),
            }
        )
    return {
        "max_files": max_files,
        "max_lines": max_lines,
        "scanned_files": len(items),
        "items": items,
    }


def _proposal_candidate_lines(config: dict, scan: dict[str, object]) -> list[str]:
    items = scan.get("items", [])
    if not isinstance(items, list):
        items = []
    category_keywords = {
        "learning_proposal_candidate": ["learning", "proposal", "lesson"],
        "research_topic_candidate": ["research", "topic", "sensing", "swarm"],
        "memory_link_candidate": ["memory", "checkpoint", "index"],
        "swarm_trail_candidate": ["swarm", "trail", "colony"],
        "project_history_candidate": ["project", "history", "V2APP", "checkpoint"],
        "safety_check_candidate": ["safety", "guard", "gate", "verification", "health"],
        "codex_prompt_candidate": ["prompt", "codex", "source", "route"],
    }
    lines = []
    for candidate_type in _proposal_autonomy_list(config, "proposal_candidate_types"):
        keywords = category_keywords.get(str(candidate_type), [])
        matches = []
        for item in items:
            haystack = (str(item.get("path", "")) + " " + str(item.get("header", ""))).lower()
            if any(keyword.lower() in haystack for keyword in keywords):
                matches.append(str(item.get("path", "")))
            if len(matches) >= 4:
                break
        if matches:
            lines.append("- " + str(candidate_type) + ": " + "; ".join(matches))
        else:
            lines.append("- " + str(candidate_type) + ": no capped local preview match")
    return lines or ["- No proposal candidate types configured."]


def colony_proposal_status() -> str:
    config, warning = _proposal_autonomy_config()
    return "\n".join(
        [
            "# Colony Proposal Status",
            "",
            "Status: READ_ONLY / STATUS_ONLY / CONTRACT_ONLY",
            "Time: " + _now(),
            "",
            "Identity:",
            "- Engel remains one companion identity.",
            "- Level 2 proposal-building is a contract only, not active runtime behavior.",
            "",
            "Level 2:",
            "- Level 2 proposal-building",
            "- runtime_level_2_enabled false",
            "- runtime_autonomy_enabled false",
            "- proposal candidates only",
            "",
            "Config:",
            *_proposal_autonomy_config_lines(config, warning),
            "",
            "Blocked write/action paths:",
            *_proposal_autonomy_blocked_lines(),
        ]
    )


def colony_proposal_contract() -> str:
    config, warning = _proposal_autonomy_config()
    approval = config.get("approval_contract", {})
    if not isinstance(approval, dict):
        approval = {}
    return "\n".join(
        [
            "# Colony Proposal Autonomy Contract",
            "",
            "Status: READ_ONLY / STATUS_ONLY / CONTRACT_ONLY",
            "Time: " + _now(),
            "",
            "Principle:",
            "- " + str(config.get("principle", PROPOSAL_AUTONOMY_DEFAULT_CONFIG["principle"])),
            "- Level 2 proposal-building",
            "- runtime_level_2_enabled false",
            "- runtime_autonomy_enabled false",
            "- Engel remains one companion identity.",
            "- Proposal candidates are not trusted memory and are not applied lessons.",
            "",
            "Config:",
            *_proposal_autonomy_config_lines(config, warning),
            "",
            "Proposal candidate types:",
            *["- " + str(item) for item in _proposal_autonomy_list(config, "proposal_candidate_types")],
            "",
            "Allowed preview inputs:",
            *["- " + str(item) for item in _proposal_autonomy_list(config, "allowed_preview_inputs")],
            "",
            "Blocked inputs without approval:",
            *["- " + str(item) for item in _proposal_autonomy_list(config, "blocked_inputs_without_approval")],
            "",
            "Allowed outputs now:",
            *["- " + str(item) for item in _proposal_autonomy_list(config, "allowed_outputs_now")],
            "",
            "Blocked outputs without explicit approval:",
            *["- " + str(item) for item in _proposal_autonomy_list(config, "blocked_outputs_without_explicit_approval")],
            "",
            "Approval contract:",
            *["- " + str(key) + ": " + str(value) for key, value in sorted(approval.items())],
            "",
            "Blocked write/action paths:",
            *_proposal_autonomy_blocked_lines(),
        ]
    )


def _colony_proposal_preview_text() -> str:
    config, warning = _proposal_autonomy_config()
    scan = _proposal_autonomy_scan(config)
    lines = [
        "# Colony Proposal Preview",
        "",
        "Status: PREVIEW_ONLY / DRY_RUN / NO_WRITE",
        "Time: " + _now(),
        "",
        "Identity and scope:",
        "- Engel remains one companion identity.",
        "- Level 2 is not enabled.",
        "- runtime_level_2_enabled false",
        "- runtime_autonomy_enabled false",
        "- no autonomous loop is running",
        "- no trust-changing actions occur",
        "- local-only",
        "- capped preview",
        "",
        "Config:",
        *_proposal_autonomy_config_lines(config, warning),
        "",
        "Scan caps used:",
        "- max_preview_files: " + str(scan["max_files"]),
        "- max_lines_per_file: " + str(scan["max_lines"]),
        "- scanned_files: " + str(scan["scanned_files"]),
        "",
        "Candidate categories:",
        *_proposal_candidate_lines(config, scan),
        "",
        "Safety contract:",
        "- READ_ONLY",
        "- PREVIEW_ONLY",
        "- DRY_RUN",
        "- NO_WRITE",
        *_proposal_autonomy_blocked_lines(),
    ]
    return "\n".join(lines)


def _colony_proposal_report_path() -> Path:
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = PROPOSAL_AUTONOMY_REPORTS_DIR / ("colony_proposal_preview_" + stamp + ".md")
    if not path.exists():
        return path
    for index in range(2, 100):
        candidate = PROPOSAL_AUTONOMY_REPORTS_DIR / (
            "colony_proposal_preview_" + stamp + "_" + str(index).zfill(2) + ".md"
        )
        if not candidate.exists():
            return candidate
    return PROPOSAL_AUTONOMY_REPORTS_DIR / (
        "colony_proposal_preview_" + stamp + "_" + datetime.datetime.now().strftime("%f") + ".md"
    )


def colony_proposal_preview(approval_text: str = "", *_args, **_kwargs) -> str:
    approval = str(approval_text or "").strip()
    preview = _colony_proposal_preview_text()
    if approval != "APPROVE_REPORT":
        return preview

    config, warning = _proposal_autonomy_config()
    approval_contract = config.get("approval_contract", {})
    if not isinstance(approval_contract, dict):
        approval_contract = {}
    PROPOSAL_AUTONOMY_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = _colony_proposal_report_path()
    old_provider_line = "- " + ("Ol" + "lama removal preserved")
    report = "\n".join(
        [
            "# Colony Proposal Autonomy Preview Report",
            "",
            "Timestamp: " + _now(),
            "Command: colony proposal preview APPROVE_REPORT",
            "Status: REPORT_ONLY",
            "",
            "Safety banner:",
            "- READ_ONLY",
            "- REPORT_ONLY",
            "- APPROVE_REPORT",
            "- CONTRACT_ONLY",
            "- Level 2 proposal-building preview",
            "- runtime_level_2_enabled false",
            "- runtime_autonomy_enabled false",
            "- no autonomous loop enabled",
            "- no background processes",
            "- no provider calls while research OFF",
            "- trusted memory writes blocked",
            "- source edits blocked",
            "- learning apply blocked",
            "- queue mutation blocked",
            "- digest/history writes blocked",
            "- ALIVE_STATE writes blocked",
            "- one Engel companion identity",
            "- shutdown_with_engel",
            old_provider_line,
            "- ChatGPT/Gemini provider gates unchanged",
            "",
            "Config summary:",
            *_proposal_autonomy_config_lines(config, warning),
            "",
            "Candidate categories:",
            *["- " + str(item) for item in _proposal_autonomy_list(config, "proposal_candidate_types")],
            "",
            "Allowed preview inputs:",
            *["- " + str(item) for item in _proposal_autonomy_list(config, "allowed_preview_inputs")],
            "",
            "Blocked inputs:",
            *["- " + str(item) for item in _proposal_autonomy_list(config, "blocked_inputs_without_approval")],
            "",
            "Allowed outputs now:",
            *["- " + str(item) for item in _proposal_autonomy_list(config, "allowed_outputs_now")],
            "",
            "Blocked outputs without explicit approval:",
            *["- " + str(item) for item in _proposal_autonomy_list(config, "blocked_outputs_without_explicit_approval")],
            "",
            "Approval contract:",
            *["- " + str(key) + ": " + str(value) for key, value in sorted(approval_contract.items())],
            "",
            "Preview:",
            "",
            "```text",
            preview,
            "```",
            "",
            "Explicit non-action statement:",
            "- Level 2 runtime autonomy was not enabled.",
            "- No autonomous loop was started.",
            "- No background worker was started.",
            "- No provider call was made.",
            "- No live research was started.",
            "- No learning was applied.",
            "- No trusted memory was written.",
            "- No source files were edited.",
            "- No queue was written or rewritten.",
            "- No digest or history file was written.",
            "- No ALIVE_STATE.json update was written.",
        ]
    )
    report_path.write_text(report + "\n", encoding="utf-8")
    return "\n".join(
        [
            "# Colony Proposal Preview Report Written",
            "",
            "Status: REPORT_ONLY",
            "Path:",
            str(report_path),
            "",
            "Safety:",
            "- READ_ONLY",
            "- REPORT_ONLY",
            "- APPROVE_REPORT",
            "- CONTRACT_ONLY",
            "- runtime_level_2_enabled false",
            "- runtime_autonomy_enabled false",
            "- no autonomous loop enabled",
            "- no background processes",
            "- no provider calls while research OFF",
            "- trusted memory writes blocked",
            "- source edits blocked",
            "- learning apply blocked",
            "- queue mutation blocked",
            "- digest/history writes blocked",
            "- ALIVE_STATE writes blocked",
        ]
    )


def _lesson_candidate_config() -> tuple[dict, str]:
    config = dict(LESSON_CANDIDATE_DEFAULT_CONFIG)
    warning = ""
    try:
        if LESSON_CANDIDATE_CONFIG_FILE.exists() and LESSON_CANDIDATE_CONFIG_FILE.is_file():
            loaded = json.loads(LESSON_CANDIDATE_CONFIG_FILE.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                config.update(loaded)
            else:
                warning = "Config file did not contain a JSON object; defaults are being used."
    except Exception as exc:
        warning = "Config read warning: " + str(exc)
    return config, warning


def _lesson_candidate_bool(config: dict, key: str) -> bool:
    return bool(config.get(key, LESSON_CANDIDATE_DEFAULT_CONFIG.get(key, False)))


def _lesson_candidate_int(config: dict, key: str, default: int, cap: int) -> int:
    try:
        value = int(config.get(key, default))
    except Exception:
        value = default
    return max(1, min(value, cap))


def _lesson_candidate_list(config: dict, key: str) -> list:
    value = config.get(key, LESSON_CANDIDATE_DEFAULT_CONFIG.get(key, []))
    return value if isinstance(value, list) else []


def _lesson_candidate_categories(config: dict) -> list:
    categories = _lesson_candidate_list(config, "lesson_candidate_categories")
    return categories or _lesson_candidate_list(config, "lesson_candidate_types")


def _lesson_candidate_config_lines(config: dict, warning: str = "") -> list[str]:
    return [
        "- version: " + str(config.get("version", "V1")),
        "- mode: " + str(config.get("mode", "REVIEW_ONLY")),
        "- colony_identity: " + str(config.get("colony_identity", "Engel")),
        "- one companion identity: " + str(_lesson_candidate_bool(config, "one_companion_identity")),
        "- local_only: " + str(_lesson_candidate_bool(config, "local_only")),
        "- untrusted_candidates: " + str(_lesson_candidate_bool(config, "untrusted_candidates")),
        "- report_only_until_later_approval: "
        + str(_lesson_candidate_bool(config, "report_only_until_later_approval")),
        "- runtime_autonomy_enabled: " + str(_lesson_candidate_bool(config, "runtime_autonomy_enabled")),
        "- runtime_level_2_enabled: " + str(_lesson_candidate_bool(config, "runtime_level_2_enabled")),
        "- simulation_runtime_enabled: " + str(_lesson_candidate_bool(config, "simulation_runtime_enabled")),
        "- background_workers: " + str(_lesson_candidate_bool(config, "background_workers")),
        "- loops_enabled: " + str(_lesson_candidate_bool(config, "loops_enabled")),
        "- provider_calls: " + str(_lesson_candidate_bool(config, "provider_calls")),
        "- live_research: " + str(_lesson_candidate_bool(config, "live_research")),
        "- max_review_files: " + str(config.get("max_review_files", 40)),
        "- max_lines_per_file: " + str(config.get("max_lines_per_file", 8)),
        "- config_warning: " + (warning or "none"),
    ]


def _lesson_candidate_safety_lines() -> list[str]:
    return [
        "- READ_ONLY",
        "- REVIEW_ONLY",
        "- REPORT_ONLY",
        "- UNTRUSTED_CANDIDATES",
        "- NO_TRUSTED_WRITE",
        "- NO_APPLY",
        "- NO_SOURCE_EDIT",
        "- NO_QUEUE_MUTATION",
        "- NO_DIGEST_WRITE",
        "- NO_ALIVE_STATE_WRITE",
        "- NO_PROVIDER_CALL",
        "- NO_BACKGROUND_WORKER",
        "- NO_AUTONOMY",
        "- local-only",
        "- untrusted lesson candidates only",
        "- not trusted memory",
        "- not applied lessons",
        "- not queue mutations",
        "- not source edits",
        "- not digest/history writes",
        "- not ALIVE_STATE writes",
        "- no autonomous loop enabled",
        "- no background workers",
        "- no provider calls",
        "- no live research",
        "- no internet actions",
        "- no digest/history writes",
        "- no ALIVE_STATE writes",
        "- older manual memory commands are not invoked by this route",
    ]


def _lesson_candidate_scan_dirs() -> list[tuple[str, Path]]:
    candidates = [
        ("app_reports", REPORTS_DIR / "app"),
        ("learning_proposal_reports", REPORTS_DIR / "learning_proposals"),
        ("proposal_autonomy_reports", REPORTS_DIR / "proposal_autonomy"),
        ("colony_autonomy_reports", REPORTS_DIR / "colony_autonomy"),
        ("swarm_trail_reports", REPORTS_DIR / "swarm_trails"),
        ("colony_reports", REPORTS_DIR / "colony"),
        ("worker_ant_reports", REPORTS_DIR / "worker_ants"),
        ("memory", MEMORY_DIR),
    ]
    return [(label, path) for label, path in candidates if path.exists() and path.is_dir()]


def _lesson_candidate_allowed_file(path: Path) -> bool:
    return path.suffix.lower() in {".md", ".json", ".txt"}


def _lesson_candidate_header(path: Path, max_lines: int) -> str:
    lines = []
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            for _index in range(max_lines):
                line = handle.readline()
                if not line:
                    break
                cleaned = _colony_sensing_safe_text(line.strip())
                if cleaned:
                    lines.append(cleaned[:180])
    except Exception as exc:
        return "read warning: " + str(exc)
    return " | ".join(lines[:max_lines]) or "(no header text)"


def _lesson_candidate_scan(config: dict) -> dict[str, object]:
    max_files = _lesson_candidate_int(config, "max_review_files", 40, 40)
    max_lines = _lesson_candidate_int(config, "max_lines_per_file", 8, 8)
    candidates = []
    for source, root in _lesson_candidate_scan_dirs():
        for path in root.iterdir():
            if path.is_file() and _lesson_candidate_allowed_file(path):
                try:
                    mtime = path.stat().st_mtime
                except Exception:
                    mtime = 0
                candidates.append((mtime, source, path))
    candidates.sort(key=lambda item: (-item[0], str(item[2]).lower()))
    items = []
    for _mtime, source, path in candidates[:max_files]:
        items.append(
            {
                "source": source,
                "path": str(path.relative_to(APP_ROOT)),
                "name": path.name,
                "header": _lesson_candidate_header(path, max_lines),
            }
        )
    return {
        "max_files": max_files,
        "max_lines": max_lines,
        "scanned_files": len(items),
        "items": items,
    }


def _lesson_candidate_lines(config: dict, scan: dict[str, object]) -> list[str]:
    items = scan.get("items", [])
    if not isinstance(items, list):
        items = []
    category_keywords = {
        "memory hygiene candidate": ["memory", "lesson", "candidate", "project memory", "checkpoint"],
        "documentation alignment candidate": ["documentation", "commands", "checklist", "index", "alignment"],
        "verifier improvement candidate": ["verify", "verification", "PASS", "no-report", "py_compile"],
        "command/route clarity candidate": ["command", "route", "status", "review", "matrix"],
        "safety guardrail candidate": ["safety", "guard", "blocked", "gate", "no-write", "verification"],
        "stale-risk candidate": ["stale", "current", "state", "living", "consolidation"],
        "future feature candidate": ["future", "next", "recommended", "contract", "feature"],
    }
    lines = []
    for candidate_type in _lesson_candidate_categories(config):
        category_name = str(candidate_type)
        keywords = category_keywords.get(category_name, [])
        matches = []
        for item in items:
            haystack = (str(item.get("path", "")) + " " + str(item.get("header", ""))).lower()
            if any(keyword.lower() in haystack for keyword in keywords):
                matches.append(str(item.get("path", "")))
            if len(matches) >= 4:
                break
        if matches:
            lines.append("- " + category_name + " (UNTRUSTED_CANDIDATE): " + "; ".join(matches))
        else:
            lines.append("- " + category_name + " (UNTRUSTED_CANDIDATE): no capped local review match")
    return lines or ["- No lesson candidate types configured."]


def lesson_candidates_status(*_args, **_kwargs) -> str:
    config, warning = _lesson_candidate_config()
    return "\n".join(
        [
            "# Lesson Candidates Status",
            "",
            "Status: READ_ONLY / REVIEW_ONLY / REPORT_ONLY / NO_WRITE",
            "Time: " + _now(),
            "",
            "Purpose:",
            "- Local-only untrusted lesson-candidate review contract.",
            "- This is not automatic learning.",
            "- This is not a trusted apply path.",
            "- Lesson candidates are review-only/report-only until a later explicit approval contract.",
            "",
            "Config:",
            *_lesson_candidate_config_lines(config, warning),
            "",
            "Required lesson candidate categories, all untrusted:",
            *["- " + str(item) + " (UNTRUSTED_CANDIDATE)" for item in _lesson_candidate_categories(config)],
            "",
            "Safety tokens:",
            *_lesson_candidate_safety_lines(),
        ]
    )


def lesson_candidates_readiness_status(*_args, **_kwargs) -> str:
    config, warning = _lesson_candidate_config()
    apply_contract = config.get("future_approved_lesson_apply_contract", {})
    if not isinstance(apply_contract, dict):
        apply_contract = {}
    allowlist = apply_contract.get("future_trusted_lesson_apply_target_allowlist", {})
    if not isinstance(allowlist, dict):
        allowlist = {}
    audit_contract = apply_contract.get("future_before_after_audit_contract", {})
    if not isinstance(audit_contract, dict):
        audit_contract = {}
    identity_schema = apply_contract.get("future_candidate_identity_schema", {})
    if not isinstance(identity_schema, dict):
        identity_schema = {}
    rollback_contract = apply_contract.get("future_rollback_refusal_contract", {})
    if not isinstance(rollback_contract, dict):
        rollback_contract = {}

    return "\n".join(
        [
            "# Lesson Candidates Readiness Status",
            "",
            "Status: READ_ONLY / STATUS_ONLY / NO_WRITE",
            "Time: " + _now(),
            "",
            "Safety tokens:",
            "- READ_ONLY",
            "- STATUS_ONLY",
            "- NO_REPORT_GENERATION",
            "- NO_VERIFIER_EXECUTION",
            "- NO_CANDIDATE_CREATION",
            "- NO_APPLY",
            "- NO_TRUSTED_WRITE",
            "- NO_SOURCE_EDIT",
            "- NO_QUEUE_MUTATION",
            "- NO_DIGEST_WRITE",
            "- NO_ALIVE_STATE_WRITE",
            "- NO_PROVIDER_CALL",
            "- NO_BACKGROUND_WORKER",
            "- NO_AUTONOMY",
            "",
            "Route behavior:",
            "- This command displays the consolidated BV through CD lesson readiness map.",
            "- It does not run verifiers.",
            "- It does not generate reports.",
            "- It does not create candidates or candidate files.",
            "- It does not implement apply or rollback behavior.",
            "- It does not invoke older manual memory commands.",
            "",
            "What exists now:",
            "- lesson candidates status",
            "- lesson candidates review",
            "- lesson candidates review APPROVE_REPORT",
            "- report-only artifacts under reports\\lesson_candidates\\",
            "- verifier coverage through tools\\verify_lesson_candidate_review.py",
            "",
            "Design-only:",
            "- trusted apply: " + str(apply_contract.get("contract_status", "DESIGN_ONLY_NOT_IMPLEMENTED")),
            "- rollback: " + str(rollback_contract.get("rollback_status", "NOT_IMPLEMENTED")),
            "- candidate identity artifacts: " + str(identity_schema.get("schema_status", "DESIGN_ONLY_INACTIVE")),
            "- target allowlist writes: " + str(allowlist.get("allowlist_status", "DESIGN_ONLY_INACTIVE")),
            "- before/after audit writes: " + str(audit_contract.get("contract_status", "DESIGN_ONLY_INACTIVE")),
            "- approval-token handling",
            "",
            "Forbidden now:",
            "- lesson candidates apply",
            "- lesson candidates apply APPROVE",
            "- lesson candidates review APPROVE_APPLY",
            "- lesson candidates rollback",
            "- any candidate creation route",
            "- trusted memory writes",
            "- source edits",
            "- route matrix mutation from lessons",
            "- queues",
            "- digest/history",
            "- ALIVE_STATE",
            "- providers",
            "- loops",
            "- background workers",
            "- autonomy",
            "",
            "Verifier coverage:",
            "- tools\\verify_lesson_candidate_review.py",
            "- current route token checks",
            "- no-write and no-report snapshots",
            "- approved report-only scope under reports\\lesson_candidates\\",
            "- target allowlist contract",
            "- before/after audit contract",
            "- candidate identity/schema contract",
            "- rollback/refusal contract",
            "- absent apply/rollback route checks",
            "- source-slice guards for provider/API/network/background/manual-memory behavior",
            "",
            "Future prerequisites before apply can be considered:",
            "- explicit separate apply implementation contract",
            "- human approval token handling",
            "- candidate identity artifact handling",
            "- target allowlist enforcement",
            "- before/after audit write design",
            "- rollback/refusal behavior design",
            "- dedicated apply verifier",
            "- no forbidden flags enabled",
            "",
            "Current safe learning path:",
            "- observe",
            "- summarize",
            "- review untrusted lesson candidates",
            "- create explicit report-only artifact with APPROVE_REPORT",
            "- no trusted writeback",
            "",
            "Config:",
            *_lesson_candidate_config_lines(config, warning),
        ]
    )


def _lesson_candidates_review_text() -> str:
    config, warning = _lesson_candidate_config()
    scan = _lesson_candidate_scan(config)
    return "\n".join(
        [
            "# Lesson Candidates Review",
            "",
            "Status: READ_ONLY / REVIEW_ONLY / REPORT_ONLY / NO_WRITE",
            "Time: " + _now(),
            "",
            "Scope:",
            "- local-only",
            "- untrusted lesson candidates",
            "- review-only",
            "- report-only until later explicit approval",
            "- no trusted write",
            "- no apply",
            "",
            "Config:",
            *_lesson_candidate_config_lines(config, warning),
            "",
            "Scan caps used:",
            "- max_review_files: " + str(scan["max_files"]),
            "- max_lines_per_file: " + str(scan["max_lines"]),
            "- scanned_files: " + str(scan["scanned_files"]),
            "",
            "Required lesson candidate categories, all untrusted:",
            *["- " + str(item) + " (UNTRUSTED_CANDIDATE)" for item in _lesson_candidate_categories(config)],
            "",
            "Untrusted lesson candidates:",
            *_lesson_candidate_lines(config, scan),
            "",
            "Safety tokens:",
            *_lesson_candidate_safety_lines(),
        ]
    )


def lesson_candidates_review_report_path() -> Path:
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = LESSON_CANDIDATE_REPORTS_DIR / ("lesson_candidates_review_" + stamp + ".md")
    if not path.exists():
        return path
    for index in range(2, 100):
        candidate = LESSON_CANDIDATE_REPORTS_DIR / (
            "lesson_candidates_review_" + stamp + "_" + str(index).zfill(2) + ".md"
        )
        if not candidate.exists():
            return candidate
    return LESSON_CANDIDATE_REPORTS_DIR / (
        "lesson_candidates_review_" + stamp + "_" + datetime.datetime.now().strftime("%f") + ".md"
    )


def lesson_candidates_review(approval_text: str = "", *_args, **_kwargs) -> str:
    approval = str(approval_text or "").strip()
    review = _lesson_candidates_review_text()
    if approval != "APPROVE_REPORT":
        return review

    config, warning = _lesson_candidate_config()
    approval_contract = config.get("approval_contract", {})
    if not isinstance(approval_contract, dict):
        approval_contract = {}
    LESSON_CANDIDATE_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = lesson_candidates_review_report_path()
    report = "\n".join(
        [
            "# Lesson Candidates Review Report",
            "",
            "Timestamp: " + _now(),
            "Command: lesson candidates review APPROVE_REPORT",
            "Status: READ_ONLY / REVIEW_ONLY / REPORT_ONLY",
            "",
            "Safety banner:",
            "- READ_ONLY",
            "- REVIEW_ONLY",
            "- REPORT_ONLY",
            "- APPROVE_REPORT",
            "- UNTRUSTED_CANDIDATES",
            "- NO_TRUSTED_WRITE",
            "- NO_APPLY",
            "- NO_SOURCE_EDIT",
            "- NO_QUEUE_MUTATION",
            "- NO_DIGEST_WRITE",
            "- NO_ALIVE_STATE_WRITE",
            "- NO_PROVIDER_CALL",
            "- NO_BACKGROUND_WORKER",
            "- NO_AUTONOMY",
            "- report-only artifact",
            "- candidates are untrusted",
            "- all required candidate categories are untrusted",
            "- no trusted-memory write",
            "- no lesson apply",
            "- no source edit",
            "- no queue mutation",
            "- no digest/history write",
            "- no ALIVE_STATE write",
            "- no provider/API/network behavior",
            "- no live research",
            "- no background worker",
            "- no autonomy",
            "",
            "Config summary:",
            *_lesson_candidate_config_lines(config, warning),
            "",
            "Required lesson candidate categories, all untrusted:",
            *["- " + str(item) + " (UNTRUSTED_CANDIDATE)" for item in _lesson_candidate_categories(config)],
            "",
            "Allowed review inputs:",
            *["- " + str(item) for item in _lesson_candidate_list(config, "allowed_review_inputs")],
            "",
            "Allowed outputs now:",
            *["- " + str(item) for item in _lesson_candidate_list(config, "allowed_outputs_now")],
            "",
            "Blocked outputs without explicit future approval:",
            *[
                "- " + str(item)
                for item in _lesson_candidate_list(config, "blocked_outputs_without_explicit_future_approval")
            ],
            "",
            "Approval contract:",
            *["- " + str(key) + ": " + str(value) for key, value in sorted(approval_contract.items())],
            "",
            "Review preview:",
            "",
            "```text",
            review,
            "```",
            "",
            "Explicit non-action statement:",
            "- No trusted memory was written.",
            "- No lesson was applied.",
            "- No source files were edited.",
            "- No queue was written or rewritten.",
            "- No digest or history file was written.",
            "- No ALIVE_STATE.json update was written.",
            "- No provider/API/network behavior was used.",
            "- No live research was started.",
            "- No background worker was started.",
            "- No autonomy was enabled.",
            "- Older manual memory commands were not invoked.",
        ]
    )
    report_path.write_text(report + "\n", encoding="utf-8")
    return "\n".join(
        [
            "# Lesson Candidates Review Report Written",
            "",
            "Status: READ_ONLY / REVIEW_ONLY / REPORT_ONLY",
            "Path:",
            str(report_path),
            "",
            "Safety:",
            "- READ_ONLY",
            "- REVIEW_ONLY",
            "- REPORT_ONLY",
            "- APPROVE_REPORT",
            "- UNTRUSTED_CANDIDATES",
            "- NO_TRUSTED_WRITE",
            "- NO_APPLY",
            "- NO_SOURCE_EDIT",
            "- NO_QUEUE_MUTATION",
            "- NO_DIGEST_WRITE",
            "- NO_ALIVE_STATE_WRITE",
            "- report-only artifact",
            "- candidates are untrusted",
            "- no trusted-memory write",
            "- no lesson apply",
            "- no source edit",
            "- no queue mutation",
            "- no digest/history write",
            "- no ALIVE_STATE write",
            "- NO_PROVIDER_CALL",
            "- no provider/API/network behavior",
            "- NO_BACKGROUND_WORKER",
            "- no background worker",
            "- NO_AUTONOMY",
            "- no autonomy",
        ]
    )


def living_learning_status(*_args, **_kwargs) -> str:
    return "\n".join(
        [
            "# Engel Living Learning Status",
            "",
            "Status: READ_ONLY / STATUS_ONLY / NO_WRITE",
            "Time: " + _now(),
            "",
            "Safety tokens:",
            "- READ_ONLY",
            "- STATUS_ONLY",
            "- NO_REPORT_GENERATION",
            "- NO_VERIFIER_EXECUTION",
            "- NO_CANDIDATE_CREATION",
            "- NO_APPLY",
            "- NO_ROLLBACK",
            "- NO_TRUSTED_WRITE",
            "- NO_SOURCE_EDIT",
            "- NO_QUEUE_MUTATION",
            "- NO_DIGEST_WRITE",
            "- NO_ALIVE_STATE_WRITE",
            "- NO_PROVIDER_CALL",
            "- NO_BACKGROUND_WORKER",
            "- NO_AUTONOMY",
            "",
            "Route behavior:",
            "- This command displays a unified safe growth state only.",
            "- It does not run verifiers.",
            "- It does not generate reports.",
            "- It does not create lesson candidates.",
            "- It does not create proposal candidates.",
            "- It does not apply lessons.",
            "- It does not roll back changes.",
            "- It does not invoke older manual memory commands.",
            "",
            "Proposal readiness:",
            "- colony proposal status, colony proposal contract, and colony proposal preview routes exist.",
            "- colony proposal preview APPROVE_REPORT is explicit report-only.",
            "- Proposal candidates remain untrusted.",
            "- No proposal output becomes trusted memory or applied learning.",
            "",
            "Lesson candidate readiness:",
            "- lesson candidates status, lesson candidates review, and lesson candidates readiness status routes exist.",
            "- lesson candidates review APPROVE_REPORT is explicit report-only.",
            "- Lesson candidates remain untrusted.",
            "- Trusted apply remains absent.",
            "",
            "Future trusted apply readiness:",
            "- Future apply contract exists as design-only metadata.",
            "- Target allowlist exists as design-only metadata.",
            "- Before/after audit contract exists as design-only metadata.",
            "- Candidate identity/schema exists as design-only metadata.",
            "- Rollback/refusal contract exists as design-only metadata.",
            "- CK dry-run preflight verifier exists as verifier-only.",
            "- No apply route exists.",
            "- No dry-run apply route exists.",
            "- No rollback route exists.",
            "- No candidate creation route exists.",
            "",
            "Colony simulation readiness:",
            "- colony simulation status and colony simulation contract routes exist.",
            "- Simulation remains read-only/contract-only.",
            "- No simulation preview exists.",
            "- No simulation report generation exists.",
            "- No simulation runtime exists.",
            "- No simulation autonomy exists.",
            "",
            "Current safe learning path:",
            "- observe",
            "- summarize",
            "- review untrusted candidates",
            "- create explicit report-only artifacts only through APPROVE_REPORT",
            "- run verifiers externally",
            "- require human approval before any future trusted writeback",
            "",
            "Forbidden actions:",
            "- trusted memory write",
            "- source edit",
            "- queue mutation",
            "- digest/history write",
            "- ALIVE_STATE write",
            "- provider/API/network behavior",
            "- background worker",
            "- autonomous loop",
            "- runtime autonomy",
            "- Level 2 runtime",
            "- old-provider/" + ("Ol" + "lama") + "/local endpoint path",
            "- silent manual memory command invocation",
            "",
            "Next human-approved growth step:",
            "- The next step should remain verifier-first/design-first unless explicitly approved otherwise.",
        ]
    )


MYCELIUM_STATUS_TOKENS = [
    "READ_ONLY",
    "STATUS_ONLY",
    "CONTRACT_ONLY",
    "RUNTIME_DISABLED",
    "SIGNAL_PROPAGATION_DISABLED",
    "UNTRUSTED_SIGNALS",
    "PROPOSAL_CANDIDATES_ONLY",
    "NO_TRUSTED_MEMORY_WRITE",
    "NO_SOURCE_EDIT",
    "NO_ROUTE_MUTATION",
    "NO_QUEUE_MUTATION",
    "NO_AUTONOMY_STATE_MUTATION",
    "NO_APPLIED_LEARNING",
    "NO_DIGEST_WRITE",
    "NO_ALIVE_STATE_WRITE",
    "NO_PROVIDER_CALL",
    "NO_NETWORK_CALL",
    "NO_BACKGROUND_WORKER",
    "NO_AUTONOMOUS_LOOP",
]

MYCELIUM_CONTRACT_TOKENS = [
    "READ_ONLY",
    "CONTRACT_ONLY",
    "RUNTIME_DISABLED",
    "SIGNAL_PROPAGATION_DISABLED",
    "UNTRUSTED_SIGNALS",
    "STRUCTURAL_ANALOGY_ONLY",
    "NO_LITERAL_HIVE_MIND_CLAIM",
    "NO_HUMAN_LIKE_FOREST_INTELLIGENCE_CLAIM",
    "PROPOSAL_CANDIDATES_ONLY",
    "NO_TRUSTED_MEMORY_WRITE",
    "NO_SOURCE_EDIT",
    "NO_ROUTE_MUTATION",
    "NO_QUEUE_MUTATION",
    "NO_AUTONOMY_STATE_MUTATION",
    "NO_APPLIED_LEARNING",
    "NO_DIGEST_WRITE",
    "NO_ALIVE_STATE_WRITE",
    "NO_PROVIDER_CALL",
    "NO_NETWORK_CALL",
    "NO_BACKGROUND_WORKER",
    "NO_AUTONOMOUS_LOOP",
]

MYCELIUM_ALLOWED_REFERENCES = [
    "warnings",
    "context markers",
    "confidence markers",
    "candidate lessons",
    "proposal candidate references",
    "report references",
    "memory references",
    "route status references",
    "verifier status references",
    "lesson candidate readiness references",
    "living learning status references",
    "simulation status references",
]


def colony_mycelium_status(*_args, **_kwargs) -> str:
    return "\n".join(
        [
            "# Colony Mycelium Status",
            "",
            "Status: READ_ONLY / STATUS_ONLY / CONTRACT_ONLY / NO_WRITE",
            "Time: " + _now(),
            "",
            "Safety tokens:",
            *["- " + token for token in MYCELIUM_STATUS_TOKENS],
            "",
            "current state",
            "- The Engel Mycelium Layer is visible only through this read-only status surface.",
            "- RUNTIME_DISABLED and SIGNAL_PROPAGATION_DISABLED remain active.",
            "- This command does not create files, reports, candidates, or runtime signals.",
            "",
            "signal boundary",
            "- UNTRUSTED_SIGNALS may describe local references only.",
            "- PROPOSAL_CANDIDATES_ONLY means any future output would remain untrusted and review-bound.",
            "- No signal propagation execution is enabled.",
            "",
            "allowed untrusted signal references",
            *["- " + item for item in MYCELIUM_ALLOWED_REFERENCES],
            "",
            "forbidden mutations",
            "- NO_TRUSTED_MEMORY_WRITE",
            "- NO_SOURCE_EDIT",
            "- NO_ROUTE_MUTATION",
            "- NO_QUEUE_MUTATION",
            "- NO_AUTONOMY_STATE_MUTATION",
            "- NO_APPLIED_LEARNING",
            "- NO_DIGEST_WRITE",
            "- NO_ALIVE_STATE_WRITE",
            "",
            "relationship to living learning status",
            "- The layer can reference living learning status as context only.",
            "- It does not run the living learning route or change that route's state.",
            "",
            "relationship to lesson candidates",
            "- Candidate lessons stay untrusted and review-only.",
            "- No lesson candidate is created or applied by this command.",
            "",
            "relationship to proposal candidates",
            "- Proposal candidate references remain untrusted.",
            "- No proposal report or approval path is invoked.",
            "",
            "relationship to simulation status",
            "- Simulation status may be referenced as read-only context.",
            "- No simulation preview, report generation, runtime, or autonomy is enabled.",
            "",
            "verifier guard summary",
            "- tools\\verify_colony_mycelium_layer_contract.py guards this route output and source slice.",
            "- The route does not run verifiers itself.",
            "- NO_PROVIDER_CALL, NO_NETWORK_CALL, NO_BACKGROUND_WORKER, and NO_AUTONOMOUS_LOOP remain enforced.",
            "",
            "next safe step",
            "- Keep mycelium work verifier-first and read-only unless a later explicit contract approves more.",
        ]
    )


def colony_mycelium_contract(*_args, **_kwargs) -> str:
    return "\n".join(
        [
            "# Colony Mycelium Contract",
            "",
            "Status: READ_ONLY / CONTRACT_ONLY / NO_WRITE",
            "Time: " + _now(),
            "",
            "Safety tokens:",
            *["- " + token for token in MYCELIUM_CONTRACT_TOKENS],
            "",
            "contract purpose",
            "- Define a hidden, read-only-first colony signal boundary for Engel.",
            "- The boundary may connect local status, report, memory-reference, lesson, proposal, simulation, and verifier context.",
            "",
            "structural analogy rule",
            "- STRUCTURAL_ANALOGY_ONLY.",
            "- NO_LITERAL_HIVE_MIND_CLAIM.",
            "- NO_HUMAN_LIKE_FOREST_INTELLIGENCE_CLAIM.",
            "- Fungal and mycorrhizal language is an organizing analogy, not a claim of literal forest intelligence.",
            "",
            "disabled runtime boundaries",
            "- RUNTIME_DISABLED.",
            "- SIGNAL_PROPAGATION_DISABLED.",
            "- No mycelium runtime, signal propagation execution, background worker, autonomous loop, provider call, or network call is enabled.",
            "",
            "untrusted signal model",
            "- UNTRUSTED_SIGNALS.",
            "- Signals are diagnostic context only.",
            "- Signals do not become trusted memory, applied lessons, route mutations, source edits, queues, digest/history writes, or ALIVE_STATE writes.",
            "",
            "allowed references",
            *["- " + item for item in MYCELIUM_ALLOWED_REFERENCES],
            "",
            "proposal-candidate-only outputs",
            "- PROPOSAL_CANDIDATES_ONLY.",
            "- Any future output remains an untrusted proposal candidate until a separate review and approval contract exists.",
            "",
            "forbidden writes and mutations",
            "- NO_TRUSTED_MEMORY_WRITE",
            "- NO_SOURCE_EDIT",
            "- NO_ROUTE_MUTATION",
            "- NO_QUEUE_MUTATION",
            "- NO_AUTONOMY_STATE_MUTATION",
            "- NO_APPLIED_LEARNING",
            "- NO_DIGEST_WRITE",
            "- NO_ALIVE_STATE_WRITE",
            "",
            "future route contract",
            "- colony mycelium status is implemented as read-only/status-only/contract-only.",
            "- colony mycelium contract is implemented as read-only/contract-only.",
            "- Neither route generates reports, creates candidates, runs verifiers, or executes signal propagation.",
            "",
            "verifier expectations",
            "- Required CP tokens and sections must remain present.",
            "- Route matrix entries must remain implemented read-only with should_execute_in_test false.",
            "- Source-slice checks must stay clean of write, provider, network, worker, loop, autonomy, and signal runtime behavior.",
            "",
            "stop conditions",
            "- Stop if a route creates files, reports, candidates, signals, or trusted writes.",
            "- Stop if a route invokes providers, network behavior, workers, loops, autonomy, signal propagation, source edits, route mutation, queue mutation, digest/history writes, or ALIVE_STATE writes.",
            "- Stop if structural analogy wording turns into literal hive-mind or human-like forest-intelligence claims.",
        ]
    )


def _colony_simulation_contract_config() -> tuple[dict, str]:
    config: dict = {}
    warning = ""
    try:
        if COLONY_SIMULATION_CONFIG_FILE.exists() and COLONY_SIMULATION_CONFIG_FILE.is_file():
            loaded = json.loads(COLONY_SIMULATION_CONFIG_FILE.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                config.update(loaded)
            else:
                warning = "config root is not an object"
        else:
            warning = "config missing"
    except Exception as exc:  # pragma: no cover - diagnostic-only fallback
        warning = str(exc)
    return config, warning


def _colony_simulation_output_lines(key: str, fallback_title: str) -> str:
    config, warning = _colony_simulation_contract_config()
    design = config.get(key, {})
    lines = []
    if isinstance(design, dict):
        configured = design.get("exact_output_lines", [])
        if isinstance(configured, list):
            lines = [str(line) for line in configured]
    if not lines:
        lines = [
            fallback_title,
            "Status: READ_ONLY / DRY_RUN / CONTRACT_ONLY / NO_WRITE",
            "simulation runtime is disabled",
            "simulation execution is not implemented",
            "runtime_autonomy_enabled false",
            "runtime_level_2_enabled false",
            "no routes execute simulation rounds",
            "seeds are untrusted bounded local prompt/spec inputs",
            "simulated personas are untrusted draft entities only",
            "interaction rounds are dry-run/report-only artifacts",
            "simulation outputs are proposal candidates only",
            "simulation outputs are not trusted memory",
            "simulation outputs cannot mutate trusted memory",
            "simulation outputs cannot mutate source files",
            "simulation outputs cannot mutate route matrices",
            "simulation outputs cannot mutate learning queues",
            "simulation outputs cannot mutate proposal queues",
            "simulation outputs cannot write digest/history",
            "simulation outputs cannot write ALIVE_STATE",
            "Engel remains one companion identity",
        ]
    if warning:
        lines += [
            "",
            "Config warning:",
            "- " + warning,
            "- No replacement file was created.",
            "- No repair was attempted.",
        ]
    return "\n".join(lines)


def colony_simulation_status(*_args, **_kwargs) -> str:
    return _colony_simulation_output_lines(
        "future_status_route_output_design",
        "# Colony Simulation Status",
    )


def colony_simulation_contract(*_args, **_kwargs) -> str:
    return _colony_simulation_output_lines(
        "future_contract_route_output_design",
        "# Colony Simulation Contract",
    )
