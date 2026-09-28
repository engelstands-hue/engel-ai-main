from __future__ import annotations

import datetime
import hashlib
import hmac
import os
from pathlib import Path
from typing import Any

import engel_global_password_gate as global_password_gate
from engel_memory_archive_status import build_memory_archive_snapshot, render_memory_archive_status

ENGEL_LONG_TERM_MEMORY_DRIVE = "/mnt/engel-hdd-vault"

ENGEL_LONG_TERM_MEMORY_FOLDER_ROLES = {
    "00_README_FIRST": "orientation and drive instructions",
    "01_PROJECT_MEMORY": "long-term project memory archive shelf",
    "02_BACKUPS": "backup archive shelf",
    "03_REPORTS": "report archive shelf",
    "04_CHECKPOINTS": "checkpoint archive shelf",
    "05_VERIFIERS": "verifier result/archive shelf",
    "06_SECURITY_AUDITS": "security audit archive shelf",
    "07_CODE_SNAPSHOTS": "code snapshot archive shelf",
    "08_BATONS": "handoff and baton archive shelf",
    "09_ARCHIVE_OLD": "older archive shelf",
}

COLONY_HIVE_CELLS: list[dict[str, Any]] = [
    {
        "id": "colony-heart",
        "role": "heart",
        "colony_id": "engel-core",
        "nest_name": "Unified Companion Identity",
        "cell_name": "Colony Heart",
        "actor": "Engel Mind",
        "current_task": "Hold the one-companion identity while many local memory colonies contribute.",
        "linked_local_artifact": "memory/ENGEL_CORE_DIRECTION_AND_SAFETY_CONSTITUTION_V1.md",
        "command": "living learning status",
        "signal_type": "identity rhythm",
        "confidence_marker": "steady",
        "safety_state": "guardian gated",
        "proposal_only": True,
        "accent": "#9ee7d0",
    },
    {
        "id": "queen-memory-map",
        "role": "queen",
        "colony_id": "memory-map",
        "nest_name": "Project Memory Colony",
        "cell_name": "Memory Queen",
        "actor": "Project Memory Coordinator",
        "current_task": "Coordinate the local project-memory map without promoting notes into trusted memory.",
        "linked_local_artifact": "memory/PROJECT_MEMORY_INDEX_V2V.md",
        "command": "project memory index",
        "signal_type": "orientation signal",
        "confidence_marker": "high",
        "safety_state": "read-only map",
        "proposal_only": True,
        "accent": "#6ec6ff",
    },
    {
        "id": "queen-proposal-lane",
        "role": "queen",
        "colony_id": "proposal-colony",
        "nest_name": "Proposal Colony",
        "cell_name": "Proposal Queen",
        "actor": "Proposal Coordinator",
        "current_task": "Keep proposal candidates visible as untrusted candidates until human approval.",
        "linked_local_artifact": "memory/COLONY_PROPOSAL_AUTONOMY_V1.json",
        "command": "colony proposal status",
        "signal_type": "candidate routing",
        "confidence_marker": "review required",
        "safety_state": "proposal-only",
        "proposal_only": True,
        "accent": "#f0c36a",
    },
    {
        "id": "queen-research-map",
        "role": "queen",
        "colony_id": "research-reports",
        "nest_name": "Research Reports Colony",
        "cell_name": "Research Queen",
        "actor": "Research Coordinator",
        "current_task": "Prioritize local research reports and safe next questions without starting live research.",
        "linked_local_artifact": "reports/research",
        "command": "research status",
        "signal_type": "local report orientation",
        "confidence_marker": "local-only",
        "safety_state": "no live research start",
        "proposal_only": True,
        "accent": "#5eead4",
    },
    {
        "id": "queen-guardian-posture",
        "role": "queen",
        "colony_id": "guardian-layer",
        "nest_name": "Guardian Safety Colony",
        "cell_name": "Guardian Queen",
        "actor": "Guardian Coordinator",
        "current_task": "Keep unsafe actions marked blocked and proposal-only until Josh approves a separate contract.",
        "linked_local_artifact": "memory/STANDARD_VERIFIER_CHECKLIST_V1.md",
        "command": "launch safety status",
        "signal_type": "safety membrane posture",
        "confidence_marker": "guardian watching",
        "safety_state": "blocks unsafe runtime power",
        "proposal_only": False,
        "accent": "#c084fc",
    },
    {
        "id": "queen-verifier-posture",
        "role": "queen",
        "colony_id": "verifier-colony",
        "nest_name": "Verifier Results Colony",
        "cell_name": "Verifier Queen",
        "actor": "Verifier Coordinator",
        "current_task": "Surface verifier posture and keep future growth behind explicit verifier checks.",
        "linked_local_artifact": "memory/ROUTE_VERIFICATION_SET_V1.json",
        "command": "verification set status",
        "signal_type": "verification posture",
        "confidence_marker": "external checks required",
        "safety_state": "read-only status",
        "proposal_only": False,
        "accent": "#a78bfa",
    },
    {
        "id": "worker-queue-curator",
        "role": "worker",
        "colony_id": "research-nests",
        "nest_name": "Research Queue Nest",
        "cell_name": "Queue Worker Cell",
        "actor": "Queue Curator",
        "current_task": "Review local research queue topics without changing the queue.",
        "linked_local_artifact": "reports/overnight/OVERNIGHT_QUEUE.md",
        "command": "research queue status",
        "signal_type": "priority marker",
        "confidence_marker": "local artifact dependent",
        "safety_state": "no queue mutation",
        "proposal_only": True,
        "accent": "#9ad48f",
    },
    {
        "id": "worker-topic-scout",
        "role": "worker",
        "colony_id": "research-nests",
        "nest_name": "Next Topic Nest",
        "cell_name": "Topic Worker Cell",
        "actor": "Topic Scout",
        "current_task": "Watch the local next-topic preview and keep it proposal-stage only.",
        "linked_local_artifact": "reports/research/NEXT_BEST_TOPIC.md",
        "command": "research next best topic",
        "signal_type": "next-topic marker",
        "confidence_marker": "candidate",
        "safety_state": "report-only gate required",
        "proposal_only": True,
        "accent": "#ffd166",
    },
    {
        "id": "worker-digest-reader",
        "role": "worker",
        "colony_id": "research-nests",
        "nest_name": "Digest Nest",
        "cell_name": "Digest Worker Cell",
        "actor": "Digest Archivist",
        "current_task": "Read the latest local research digest if one exists, without writing history.",
        "linked_local_artifact": "reports/research/RESEARCH_DIGEST_LATEST.md",
        "command": "research digest latest",
        "signal_type": "digest marker",
        "confidence_marker": "local snapshot",
        "safety_state": "no digest write",
        "proposal_only": True,
        "accent": "#b99cff",
    },
    {
        "id": "worker-chat-memory",
        "role": "worker",
        "colony_id": "chat-memories",
        "nest_name": "Chat Memories Nest",
        "cell_name": "Chat Memory Worker",
        "actor": "Chat Memory Worker",
        "current_task": "Observe local chat memory archive signals without distilling or trusting them automatically.",
        "linked_local_artifact": "memory/OFFLINE_CONVERSATION_ARCHIVE_V2MIND_B.jsonl",
        "command": "offline memory status",
        "signal_type": "conversation memory marker",
        "confidence_marker": "untrusted context",
        "safety_state": "read-only archive reference",
        "proposal_only": True,
        "accent": "#38bdf8",
    },
    {
        "id": "worker-thought-seed",
        "role": "worker",
        "colony_id": "thought-seeds",
        "nest_name": "Thought Seeds Nest",
        "cell_name": "Thought Seed Worker",
        "actor": "Thought Seed Worker",
        "current_task": "Organize local thought-seed candidates as context markers only.",
        "linked_local_artifact": "memory/COMPANION_THOUGHT_INBOX_V2MIND_A.json",
        "command": "thought inbox status",
        "signal_type": "seed context marker",
        "confidence_marker": "candidate only",
        "safety_state": "no trusted-memory write",
        "proposal_only": True,
        "accent": "#34d399",
    },
    {
        "id": "worker-report-review",
        "role": "worker",
        "colony_id": "research-reports",
        "nest_name": "Research Reports Nest",
        "cell_name": "Report Review Worker",
        "actor": "Report Review Worker",
        "current_task": "Map existing local reports into proposal context without creating new reports.",
        "linked_local_artifact": "reports/research",
        "command": "research status",
        "signal_type": "report context marker",
        "confidence_marker": "local artifact dependent",
        "safety_state": "read-only report reference",
        "proposal_only": True,
        "accent": "#22d3ee",
    },
    {
        "id": "worker-lesson-candidate",
        "role": "worker",
        "colony_id": "lesson-candidates",
        "nest_name": "Lesson Candidate Nest",
        "cell_name": "Lesson Candidate Worker",
        "actor": "Lesson Candidate Worker",
        "current_task": "Route candidate lessons to the proposal lane without applying them.",
        "linked_local_artifact": "memory/LESSON_CANDIDATE_REVIEW_V1.json",
        "command": "lesson candidates status",
        "signal_type": "candidate lesson routing",
        "confidence_marker": "human approval required",
        "safety_state": "no applied learning",
        "proposal_only": True,
        "accent": "#fb7185",
    },
    {
        "id": "worker-swarm-trail",
        "role": "worker",
        "colony_id": "swarm-trails",
        "nest_name": "Swarm Trails Nest",
        "cell_name": "Swarm Trail Worker",
        "actor": "Swarm Trail Worker",
        "current_task": "Show local swarm trail previews as mapped trails only.",
        "linked_local_artifact": "memory/SWARM_TRAILS_V1.json",
        "command": "swarm trails preview",
        "signal_type": "trail map marker",
        "confidence_marker": "preview only",
        "safety_state": "no swarm runtime",
        "proposal_only": True,
        "accent": "#f59e0b",
    },
    {
        "id": "worker-project-history",
        "role": "worker",
        "colony_id": "project-history",
        "nest_name": "Project History Nest",
        "cell_name": "Project History Worker",
        "actor": "Project History Worker",
        "current_task": "Map project history into present context without writing new history.",
        "linked_local_artifact": "memory/PROJECT_HISTORY.md",
        "command": "project memory index",
        "signal_type": "history context marker",
        "confidence_marker": "local record",
        "safety_state": "no digest/history write",
        "proposal_only": True,
        "accent": "#fbbf24",
    },
    {
        "id": "worker-verifier",
        "role": "worker",
        "colony_id": "verifier-results",
        "nest_name": "Verifier Results Nest",
        "cell_name": "Verifier Worker",
        "actor": "Verifier Worker",
        "current_task": "Keep verifier expectations visible without running verifiers from this screen.",
        "linked_local_artifact": "memory/STANDARD_VERIFIER_CHECKLIST_V1.md",
        "command": "verification set status",
        "signal_type": "verifier expectation marker",
        "confidence_marker": "must be run externally",
        "safety_state": "display only",
        "proposal_only": False,
        "accent": "#93c5fd",
    },
    {
        "id": "nest-lesson-candidates",
        "role": "nest",
        "colony_id": "lesson-colony",
        "nest_name": "Lesson Candidate Colony",
        "cell_name": "Candidate Nest",
        "actor": "Lesson Reviewer",
        "current_task": "Keep untrusted lesson candidates visible without applying them.",
        "linked_local_artifact": "memory/LESSON_CANDIDATE_REVIEW_V1.json",
        "command": "lesson candidates status",
        "signal_type": "candidate lesson trail",
        "confidence_marker": "untrusted",
        "safety_state": "no apply",
        "proposal_only": True,
        "accent": "#ff9aa2",
    },
    {
        "id": "nest-project-memory",
        "role": "nest",
        "colony_id": "memory-map",
        "nest_name": "Project Memory Colony",
        "cell_name": "Memory Nest",
        "actor": "Project Memory Index",
        "current_task": "Anchor the hive map to existing local project memory.",
        "linked_local_artifact": "memory/PROJECT_MEMORY_INDEX_V2V.md",
        "command": "project memory index",
        "signal_type": "local path trail",
        "confidence_marker": "high",
        "safety_state": "read-only",
        "proposal_only": False,
        "accent": "#7bdff2",
    },
    {
        "id": "nest-chat-memories",
        "role": "nest",
        "colony_id": "chat-memories",
        "nest_name": "Chat Memories Nest",
        "cell_name": "Chat Memories Nest",
        "actor": "Offline Conversation Archive",
        "current_task": "Represent local chat memories as untrusted context until separately reviewed.",
        "linked_local_artifact": "memory/OFFLINE_CONVERSATION_INDEX_V2MIND_B.json",
        "command": "offline memory status",
        "signal_type": "chat memory colony",
        "confidence_marker": "local index",
        "safety_state": "read-only",
        "proposal_only": True,
        "accent": "#60a5fa",
    },
    {
        "id": "nest-thought-seeds",
        "role": "nest",
        "colony_id": "thought-seeds",
        "nest_name": "Thought Seeds Nest",
        "cell_name": "Thought Seeds Nest",
        "actor": "Thought Seed Index",
        "current_task": "Hold local thought seeds as candidate context, not applied memory.",
        "linked_local_artifact": "memory/COMPANION_THOUGHT_INBOX_V2MIND_A.json",
        "command": "thought inbox status",
        "signal_type": "thought seed colony",
        "confidence_marker": "candidate only",
        "safety_state": "untrusted input boundary",
        "proposal_only": True,
        "accent": "#4ade80",
    },
    {
        "id": "nest-research-reports",
        "role": "nest",
        "colony_id": "research-reports",
        "nest_name": "Research Reports Nest",
        "cell_name": "Research Reports Nest",
        "actor": "Research Report Archive",
        "current_task": "Expose existing local research report folders as local reference colonies.",
        "linked_local_artifact": "reports/research",
        "command": "research status",
        "signal_type": "research report colony",
        "confidence_marker": "local artifact dependent",
        "safety_state": "read-only",
        "proposal_only": True,
        "accent": "#2dd4bf",
    },
    {
        "id": "nest-approved-lessons",
        "role": "nest",
        "colony_id": "approved-lessons",
        "nest_name": "Approved Lessons Nest",
        "cell_name": "Approved Lessons Nest",
        "actor": "Lesson Review Contract",
        "current_task": "Separate reviewed lesson contracts from untrusted lesson candidates.",
        "linked_local_artifact": "memory/V2APP_CJ_FUTURE_TRUSTED_LESSON_APPLY_BOUNDARY_READINESS_DECISION.json",
        "command": "lesson candidates readiness status",
        "signal_type": "approved lesson boundary",
        "confidence_marker": "contract guarded",
        "safety_state": "no apply from hive",
        "proposal_only": False,
        "accent": "#fde68a",
    },
    {
        "id": "nest-swarm-trails",
        "role": "nest",
        "colony_id": "swarm-trails",
        "nest_name": "Swarm Trails Nest",
        "cell_name": "Swarm Trails Nest",
        "actor": "Swarm Trail Map",
        "current_task": "Show route/trail ideas as local preview structure only.",
        "linked_local_artifact": "memory/SWARM_TRAILS_V1.json",
        "command": "swarm trails preview",
        "signal_type": "swarm trail colony",
        "confidence_marker": "preview only",
        "safety_state": "no runtime swarm",
        "proposal_only": True,
        "accent": "#f97316",
    },
    {
        "id": "nest-project-history",
        "role": "nest",
        "colony_id": "project-history",
        "nest_name": "Project History Nest",
        "cell_name": "Project History Nest",
        "actor": "Project History",
        "current_task": "Hold local project history as orientation context.",
        "linked_local_artifact": "memory/PROJECT_HISTORY.md",
        "command": "project memory index",
        "signal_type": "project history colony",
        "confidence_marker": "local record",
        "safety_state": "read-only",
        "proposal_only": False,
        "accent": "#facc15",
    },
    {
        "id": "nest-safety-contracts",
        "role": "nest",
        "colony_id": "safety-contracts",
        "nest_name": "Safety Contracts Nest",
        "cell_name": "Safety Contracts Nest",
        "actor": "Safety Contract Shelf",
        "current_task": "Keep safety contracts above any future growth action.",
        "linked_local_artifact": "memory/ENGEL_CORE_DIRECTION_AND_SAFETY_CONSTITUTION_V1.md",
        "command": "living systems status",
        "signal_type": "safety contract colony",
        "confidence_marker": "governing contract",
        "safety_state": "Josh first; Guardian second; Engel/runtime below both",
        "proposal_only": False,
        "accent": "#c084fc",
    },
    {
        "id": "nest-proposal-candidates",
        "role": "nest",
        "colony_id": "proposal-candidates",
        "nest_name": "Proposal Candidates Nest",
        "cell_name": "Proposal Candidates Nest",
        "actor": "Proposal Candidate Shelf",
        "current_task": "Hold candidate ideas as untrusted, proposal-only material.",
        "linked_local_artifact": "reports/proposal_autonomy",
        "command": "colony proposal preview",
        "signal_type": "proposal candidate colony",
        "confidence_marker": "human approval required",
        "safety_state": "proposal-only",
        "proposal_only": True,
        "accent": "#fb923c",
    },
    {
        "id": "nest-route-status",
        "role": "nest",
        "colony_id": "route-status",
        "nest_name": "Route Status Nest",
        "cell_name": "Route Status Nest",
        "actor": "Route Verification Set",
        "current_task": "Show command/route expectations without mutating routes.",
        "linked_local_artifact": "memory/ROUTE_VERIFICATION_SET_V1.json",
        "command": "verification set status",
        "signal_type": "route status colony",
        "confidence_marker": "metadata guarded",
        "safety_state": "no route mutation",
        "proposal_only": False,
        "accent": "#67e8f9",
    },
    {
        "id": "guardian-layer",
        "role": "guardian",
        "colony_id": "guardian-layer",
        "nest_name": "Safety Membrane",
        "cell_name": "Guardian Layer",
        "actor": "Guardian Layer",
        "current_task": "Monitor unsafe signals, provider/network state, autonomy posture, and verifier readiness.",
        "linked_local_artifact": "memory/STANDARD_VERIFIER_CHECKLIST_V1.md",
        "command": "launch safety status",
        "signal_type": "safety membrane",
        "confidence_marker": "must verify",
        "safety_state": "blocks unsafe mutation",
        "proposal_only": False,
        "accent": "#82e0c2",
    },
    {
        "id": "guardian-permission-membrane",
        "role": "guardian",
        "colony_id": "guardian-layer",
        "nest_name": "Engel Permissions",
        "cell_name": "Safety Membrane",
        "actor": "Permission Guardian",
        "current_task": "Display blocked dangerous permissions and password-gated request state.",
        "linked_local_artifact": "memory/ROUTE_VERIFICATION_SET_V1.json",
        "command": "colony hive permissions",
        "signal_type": "permission membrane",
        "confidence_marker": "password gate is intent only",
        "safety_state": "no runtime power granted",
        "proposal_only": False,
        "accent": "#86efac",
    },
    {
        "id": "verifier-lane",
        "role": "verifier",
        "colony_id": "verifier-colony",
        "nest_name": "Verifier Colony",
        "cell_name": "Verifier Lane",
        "actor": "Verifier Clerk",
        "current_task": "Keep the standard verifier ritual visible before any future growth step.",
        "linked_local_artifact": "memory/STANDARD_VERIFIER_CHECKLIST_V1.md",
        "command": "verification set status",
        "signal_type": "verifier posture",
        "confidence_marker": "external run required",
        "safety_state": "status-only",
        "proposal_only": False,
        "accent": "#8ecae6",
    },
    {
        "id": "mycelium-memory-signal",
        "role": "mycelium_signal",
        "colony_id": "mycelium-layer",
        "nest_name": "Engel Mycelium Layer",
        "cell_name": "Memory Signal Path",
        "actor": "Read-only Signal Path",
        "current_task": "Show the relationship between memory references, reports, candidates, and verifier state.",
        "linked_local_artifact": "memory/COLONY_MYCELIUM_LAYER_CONTRACT_V1.json",
        "command": "colony mycelium status",
        "signal_type": "read-only-first signal",
        "confidence_marker": "untrusted signal",
        "safety_state": "signal propagation disabled",
        "proposal_only": True,
        "accent": "#cdb4db",
    },
    {
        "id": "mycelium-report-route-signal",
        "role": "mycelium_signal",
        "colony_id": "mycelium-layer",
        "nest_name": "Engel Mycelium Layer",
        "cell_name": "Report Route Signal",
        "actor": "Report-to-Route Signal",
        "current_task": "Display how reports, route status, and verifier markers relate without mutating routes.",
        "linked_local_artifact": "memory/COLONY_MYCELIUM_LAYER_CONTRACT_V1.json",
        "command": "colony mycelium status",
        "signal_type": "read-only route context",
        "confidence_marker": "status marker",
        "safety_state": "no route mutation",
        "proposal_only": True,
        "accent": "#c4b5fd",
    },
    {
        "id": "mycelium-warning-confidence-signal",
        "role": "mycelium_signal",
        "colony_id": "mycelium-layer",
        "nest_name": "Engel Mycelium Layer",
        "cell_name": "Warning Confidence Signal",
        "actor": "Warning Marker Path",
        "current_task": "Connect warnings, confidence markers, and proposal candidates as display-only signals.",
        "linked_local_artifact": "memory/COLONY_MYCELIUM_LAYER_CONTRACT_V1.json",
        "command": "colony mycelium status",
        "signal_type": "warning/confidence marker",
        "confidence_marker": "read-only-first",
        "safety_state": "no applied learning",
        "proposal_only": True,
        "accent": "#f0abfc",
    },
    {
        "id": "proposal-candidate-lane",
        "role": "proposal",
        "colony_id": "proposal-colony",
        "nest_name": "Proposal Candidate Lane",
        "cell_name": "Candidate Lane",
        "actor": "Candidate Router",
        "current_task": "Keep proposed research, lessons, and warnings as candidates until approved.",
        "linked_local_artifact": "reports/proposal_autonomy",
        "command": "colony proposal preview",
        "signal_type": "proposal candidate",
        "confidence_marker": "human review needed",
        "safety_state": "proposal-only",
        "proposal_only": True,
        "accent": "#f4a261",
    },
    {
        "id": "proposal-growth-lane",
        "role": "proposal",
        "colony_id": "proposal-growth",
        "nest_name": "Proposal Growth Lane",
        "cell_name": "Growth Candidate Lane",
        "actor": "Growth Candidate Router",
        "current_task": "Display improvement proposals, future tasks, and safe next steps as untrusted candidates.",
        "linked_local_artifact": "memory/PROJECT_NEXT_STEPS_V2W.md",
        "command": "project next steps",
        "signal_type": "safe next-step candidate",
        "confidence_marker": "human approval required",
        "safety_state": "proposal-only",
        "proposal_only": True,
        "accent": "#fdba74",
    },
    {
        "id": "proposal-untrusted-lane",
        "role": "proposal",
        "colony_id": "proposal-growth",
        "nest_name": "Proposal Growth Lane",
        "cell_name": "Untrusted Candidate Lane",
        "actor": "Untrusted Candidate Marker",
        "current_task": "Keep candidate lessons and copied context visibly untrusted until review.",
        "linked_local_artifact": "memory/LESSON_CANDIDATE_REVIEW_V1.json",
        "command": "lesson candidates review",
        "signal_type": "untrusted candidate marker",
        "confidence_marker": "approval required",
        "safety_state": "no apply",
        "proposal_only": True,
        "accent": "#fca5a5",
    },
]


ROLE_ORDER = ["heart", "queen", "worker", "nest", "guardian", "mycelium_signal", "proposal", "verifier"]

ROLE_TITLES = {
    "heart": "Colony Heart",
    "queen": "Queens / Coordinators",
    "worker": "Colony Workers",
    "nest": "Memory Colonies / Local Nests",
    "guardian": "Guardian Layer",
    "mycelium_signal": "Engel Mycelium Layer",
    "proposal": "Proposal / Candidate Lane",
    "verifier": "Verifier / Status Lane",
}

HIVE_MAP_LANES: list[dict[str, str]] = [
    {
        "number": "1",
        "title": "Queens",
        "role": "queen",
        "summary": "Coordination / prioritization / proposal only",
        "badge": "PROPOSAL ONLY",
        "accent": "#facc15",
    },
    {
        "number": "2",
        "title": "Colony Workers",
        "role": "worker",
        "summary": "Observation / organization / mapping / proposal-building only",
        "badge": "LOCAL TASK CARDS",
        "accent": "#22d3ee",
    },
    {
        "number": "3",
        "title": "Memory Colonies / Nests",
        "role": "nest",
        "summary": "Chat memories, thought seeds, reports, lessons, trails, history, routes, verifiers",
        "badge": "LOCAL ONLY",
        "accent": "#84cc16",
    },
    {
        "number": "4",
        "title": "Mycelium Signal Paths",
        "role": "mycelium_signal",
        "summary": "Read-only-first signal paths for warnings, context, confidence, and candidates",
        "badge": "READ-ONLY-FIRST",
        "accent": "#38bdf8",
    },
    {
        "number": "5",
        "title": "Guardian Layer",
        "role": "guardian",
        "summary": "Safety membrane, blocked capabilities, verifier posture, proposal warnings",
        "badge": "GUARDIAN WATCHING",
        "accent": "#c084fc",
    },
    {
        "number": "6",
        "title": "Verifier Posture",
        "role": "verifier",
        "summary": "Observe / verify / no execution from the Hive screen",
        "badge": "NO EXECUTION",
        "accent": "#a78bfa",
    },
    {
        "number": "7",
        "title": "Proposal Growth Lane",
        "role": "proposal",
        "summary": "Untrusted candidate lessons, improvement proposals, and safe next steps",
        "badge": "HUMAN APPROVAL REQUIRED",
        "accent": "#f59e0b",
    },
]

SAFETY_LINES = [
    "Local hive map only.",
    "Local visual hive only.",
    "No browsing.",
    "No provider call.",
    "No network call.",
    "No background worker service.",
    "No autonomous loop.",
    "No queue mutation.",
    "No trusted-memory write.",
    "No source edit.",
    "Mycelium signals are read-only-first.",
    "Colony outputs are proposal candidates until human-approved.",
    "Password unlock changes only session request/proposal state and grants no runtime power.",
]

SAFETY_TOKENS = [
    "READ_ONLY_FIRST",
    "LOCAL_LINKS_ONLY",
    "STRUCTURAL_ANALOGY_ONLY",
    "PROPOSAL_CANDIDATES_ONLY",
    "RUNTIME_AUTONOMY_DISABLED",
    "SIGNAL_PROPAGATION_DISABLED",
    "NO_PROVIDER_CALL",
    "NO_NETWORK_CALL",
    "NO_BACKGROUND_WORKER",
    "NO_AUTONOMOUS_LOOP",
    "NO_QUEUE_MUTATION",
    "NO_TRUSTED_MEMORY_WRITE",
    "NO_SOURCE_EDIT",
    "NO_ROUTE_MUTATION",
    "NO_APPLIED_LEARNING",
    "NO_DIGEST_WRITE",
    "NO_ALIVE_STATE_WRITE",
]

HIVE_PERMISSION_GATES: list[dict[str, Any]] = [
    {
        "permission_id": "browsing",
        "name": "Browsing",
        "label": "No browsing",
        "default_state": "OFF",
        "current_state": "OFF",
        "status_badge": "OFF / BLOCKED",
        "safety_mode": "BLOCKED",
        "description": "Hive cannot browse or fetch web content from this screen.",
        "requires_approval": True,
        "can_execute_from_hive": False,
    },
    {
        "permission_id": "provider_calls",
        "name": "Provider calls",
        "label": "No provider call",
        "default_state": "OFF",
        "current_state": "OFF",
        "status_badge": "OFF / BLOCKED",
        "safety_mode": "BLOCKED",
        "description": "Hive cannot call configured online model providers, local model endpoints, or any provider from this screen.",
        "requires_approval": True,
        "can_execute_from_hive": False,
    },
    {
        "permission_id": "network_calls",
        "name": "Network calls",
        "label": "No network call",
        "default_state": "OFF",
        "current_state": "OFF",
        "status_badge": "OFF / BLOCKED",
        "safety_mode": "BLOCKED",
        "description": "Hive cannot use network transport behavior from this screen.",
        "requires_approval": True,
        "can_execute_from_hive": False,
    },
    {
        "permission_id": "background_worker_service",
        "name": "Background worker service",
        "label": "No background worker service",
        "default_state": "OFF",
        "current_state": "OFF",
        "status_badge": "OFF / BLOCKED",
        "safety_mode": "BLOCKED",
        "description": "Hive cannot create persistent background services.",
        "requires_approval": True,
        "can_execute_from_hive": False,
    },
    {
        "permission_id": "autonomous_loop",
        "name": "Autonomous loop",
        "label": "No autonomous loop",
        "default_state": "OFF",
        "current_state": "OFF",
        "status_badge": "OFF / BLOCKED",
        "safety_mode": "BLOCKED",
        "description": "Hive cannot run recursive/autonomous loops.",
        "requires_approval": True,
        "can_execute_from_hive": False,
    },
    {
        "permission_id": "queue_mutation",
        "name": "Queue mutation",
        "label": "No queue mutation",
        "default_state": "OFF",
        "current_state": "OFF",
        "status_badge": "OFF / BLOCKED",
        "safety_mode": "BLOCKED",
        "description": "Hive cannot mutate queues.",
        "requires_approval": True,
        "can_execute_from_hive": False,
    },
    {
        "permission_id": "trusted_memory_write",
        "name": "Trusted-memory write",
        "label": "No trusted-memory write",
        "default_state": "OFF",
        "current_state": "OFF",
        "status_badge": "OFF / BLOCKED",
        "safety_mode": "BLOCKED",
        "description": "Hive cannot write trusted memory.",
        "requires_approval": True,
        "can_execute_from_hive": False,
    },
    {
        "permission_id": "source_edit",
        "name": "Source edit",
        "label": "No source edit",
        "default_state": "OFF",
        "current_state": "OFF",
        "status_badge": "OFF / BLOCKED",
        "safety_mode": "BLOCKED",
        "description": "Hive cannot edit source code.",
        "requires_approval": True,
        "can_execute_from_hive": False,
    },
    {
        "permission_id": "mycelium_signals",
        "name": "Mycelium signals",
        "label": "Mycelium signals are read-only-first",
        "default_state": "ON_READ_ONLY_FIRST",
        "current_state": "READ_ONLY_FIRST",
        "status_badge": "READ-ONLY-FIRST",
        "safety_mode": "LOCAL ONLY / READ-ONLY",
        "description": (
            "Mycelium may display/read local signal paths, warnings, confidence markers, "
            "context, and proposal candidates, but cannot directly mutate trusted memory, "
            "source, queues, routes, autonomy state, or applied learning."
        ),
        "requires_approval": False,
        "can_execute_from_hive": False,
    },
]

ENGEL_MIND_MEMORY_COLONIES: list[dict[str, Any]] = [
    {
        "name": "Chat Memories",
        "states": ["LOCAL ONLY", "READ ONLY"],
        "surface": "memory/OFFLINE_CONVERSATION_INDEX_V2MIND_B.json",
        "command": "offline memory status",
        "role": "conversation context colony",
        "guardrail": "untrusted context only; no trusted-memory write from status",
    },
    {
        "name": "Thought Seeds",
        "states": ["LOCAL ONLY", "READ ONLY"],
        "surface": "memory/COMPANION_THOUGHT_INBOX_V2MIND_A.json",
        "command": "thought inbox status",
        "role": "idea seed colony",
        "guardrail": "candidate ideas only until reviewed and approved",
    },
    {
        "name": "Research Reports",
        "states": ["CONNECTED", "READ ONLY"],
        "surface": "reports/research",
        "command": "research status",
        "role": "local research report colony",
        "guardrail": "existing local reports are references, not command authority",
    },
    {
        "name": "Approved Lessons",
        "states": ["NEEDS REVIEW", "HUMAN APPROVAL REQUIRED"],
        "surface": "memory/V2APP_CJ_FUTURE_TRUSTED_LESSON_APPLY_BOUNDARY_READINESS_DECISION.json",
        "command": "lesson candidates readiness status",
        "role": "lesson boundary colony",
        "guardrail": "trusted lesson apply remains absent unless separately approved",
    },
    {
        "name": "Swarm Trails",
        "states": ["READ ONLY", "SCAFFOLD ONLY"],
        "surface": "memory/SWARM_TRAILS_V1.json",
        "command": "swarm trails preview",
        "role": "trail preview colony",
        "guardrail": "trail previews do not start a swarm runtime",
    },
    {
        "name": "Project History",
        "states": ["CONNECTED", "READ ONLY"],
        "surface": "memory/PROJECT_HISTORY.md",
        "command": "project memory index",
        "role": "project history colony",
        "guardrail": "no digest/history write from this surface",
    },
    {
        "name": "Long-Term Memory Drive",
        "states": ["CONNECTED", "LOCAL ONLY", "READ ONLY"],
        "surface": ENGEL_LONG_TERM_MEMORY_DRIVE,
        "command": "long term memory drive status",
        "role": "external Engel memory-drive shelf",
        "guardrail": "explicit read-only status root; no trusted-memory writes or automatic sync",
    },
    {
        "name": "Queen Links",
        "states": ["CONNECTED", "LOCAL ONLY"],
        "surface": "memory/COMMUNICATION_QUEEN_REMOTE_QUEEN_CONTRACT_V1.json",
        "command": "colony hive queen links",
        "role": "session-local queen handoff surface",
        "guardrail": "folder links are session-only context and do not assign jobs",
    },
    {
        "name": "Hive Status",
        "states": ["CONNECTED", "LOCAL ONLY"],
        "surface": "engel_research_office.py",
        "command": "colony hive status",
        "role": "local supercolony GUI/status surface",
        "guardrail": "visual/status only; no worker service or loop",
    },
    {
        "name": "Mycelium Signals",
        "states": ["READ ONLY", "DISABLED"],
        "surface": "memory/COLONY_MYCELIUM_LAYER_CONTRACT_V1.json",
        "command": "colony mycelium status",
        "role": "read-only signal analogy layer",
        "guardrail": "signal propagation runtime remains disabled",
    },
    {
        "name": "Guardian Safety Checks",
        "states": ["CONNECTED", "READ ONLY"],
        "surface": "tools/engel_launch_safety_guard.py",
        "command": "launch safety status",
        "role": "safety membrane colony",
        "guardrail": "blocks unsafe runtime paths and keeps checks visible",
    },
    {
        "name": "Offline Seed LLM Scaffold",
        "states": ["SCAFFOLD ONLY", "DISABLED"],
        "surface": "engel_offline_seed_llm.py",
        "command": "offline seed llm status",
        "role": "default-off companion model scaffold",
        "guardrail": "env-gated, untrusted text only; no provider fallback or command execution",
    },
    {
        "name": "Research Brain",
        "states": ["CONNECTED", "REPORT ONLY"],
        "surface": "engel_research_brain_v2.py",
        "command": "research brain status",
        "role": "local research-brain status/report foundation",
        "guardrail": "status/report paths do not start live internet research",
    },
    {
        "name": "Research Thinking Screen",
        "states": ["LOCAL ONLY", "READ ONLY"],
        "surface": "engel_research_thinking_screen.py",
        "command": "research thinking screen",
        "role": "observer screen",
        "guardrail": "optional local observer screen only",
    },
    {
        "name": "Proposal Lane",
        "states": ["REPORT ONLY", "HUMAN APPROVAL REQUIRED"],
        "surface": "reports/proposal_autonomy",
        "command": "colony proposal status",
        "role": "proposal candidate colony",
        "guardrail": "proposing is not acting; candidates remain untrusted",
    },
]

ENGEL_MIND_SAFE_CAPABILITIES: list[dict[str, str]] = [
    {
        "capability": "remember",
        "state": "LOCAL CONTEXT ONLY",
        "meaning": "surface existing memory colonies and candidate notes without trusting or writing them",
    },
    {
        "capability": "compare",
        "state": "READ ONLY",
        "meaning": "compare local reports, routes, signals, and indexes without mutation",
    },
    {
        "capability": "reinforce",
        "state": "PROPOSAL ONLY",
        "meaning": "mark useful patterns as candidates for later review; no automatic apply",
    },
    {
        "capability": "cool down",
        "state": "GUARDIAN MEDIATED",
        "meaning": "slow or block noisy, unsafe, stale, or unapproved paths",
    },
    {
        "capability": "research locally",
        "state": "LOCAL ONLY",
        "meaning": "use existing local reports/status surfaces; no live internet or provider calls",
    },
    {
        "capability": "summarize",
        "state": "READ ONLY",
        "meaning": "summarize visible local state and command outputs",
    },
    {
        "capability": "propose",
        "state": "HUMAN APPROVAL REQUIRED",
        "meaning": "draft candidates and reports; proposing is not acting",
    },
    {
        "capability": "report",
        "state": "REPORT ONLY",
        "meaning": "write only explicit approved report artifacts when a route requires approval",
    },
    {
        "capability": "await approval",
        "state": "ACTION GATED",
        "meaning": "hold before crossing trusted-memory, source, queue, route, provider, or runtime gates",
    },
]

ENGEL_MIND_GUARDIAN_BOUNDARIES = [
    "no provider calls",
    "no live internet",
    "no uncontrolled autonomy",
    "no background workers",
    "no trusted-memory writes without approval",
    "no queue mutation",
    "no ALIVE_STATE writes",
    "no source edits unless explicitly assigned",
    "no fake live data",
    "no hidden schedulers",
    "no automatic research",
]

ENGEL_MIND_ACTION_GATES = [
    {
        "level": "Josh",
        "state": "highest approval authority",
        "gate": "only exact, task-scoped Josh approval may cross a documented action gate",
    },
    {
        "level": "Guardian",
        "state": "safety review and blocking layer below Josh",
        "gate": "provider, network, autonomy, queue, trusted-memory, source, and runtime gates stay closed unless Josh approves and verifiers pass",
    },
    {
        "level": "Verifier",
        "state": "checks before apply",
        "gate": "verifiers run externally, not from status routes",
    },
    {
        "level": "Engel",
        "state": "may observe, summarize, compare, and propose",
        "gate": "cannot execute, mutate, trust, or apply by itself",
    },
]

ENGEL_MIND_COMMAND_SURFACES: list[dict[str, str]] = [
    {
        "label": "Upgrade Connections",
        "command": "upgrade connections status",
        "state": "READ ONLY",
        "opens": "Companion chat output / Engel Mind tab status text",
        "note": "connection map and package/resource presence",
    },
    {
        "label": "Future Upgrade Readiness",
        "command": "future upgrades status",
        "state": "CONNECTED FOR REVIEW",
        "opens": "Companion chat output / Engel Mind tab status text",
        "note": "next-step readiness map; no future system is activated automatically",
    },
    {
        "label": "Long-Term Memory Drive",
        "command": "long term memory drive status",
        "state": "READ ONLY",
        "opens": "status output / Engel Mind tab",
        "note": "CT246 SSD and Dell HDD archive status with project-local fallback",
    },
    {
        "label": "Colony Hive",
        "command": "colony hive status",
        "state": "LOCAL ONLY",
        "opens": "Hive GUI",
        "note": "local supercolony map and screen PID status",
    },
    {
        "label": "Queen Links",
        "command": "colony hive queen links",
        "state": "READ ONLY",
        "opens": "Queen Links tab",
        "note": "session-only local folder handoff posture",
    },
    {
        "label": "Super Swarm Hive",
        "command": "super swarm hive status",
        "state": "SCAFFOLD ONLY",
        "opens": "Swarm tab / optional 3D visual scaffold",
        "note": "visual/local scaffold; no runtime power",
    },
    {
        "label": "Research Thinking",
        "command": "research thinking status",
        "state": "READ ONLY",
        "opens": "observer status",
        "note": "dependent surface must fail clearly if unavailable",
    },
    {
        "label": "Offline Seed LLM",
        "command": "offline seed llm status",
        "state": "DISABLED",
        "opens": "status output",
        "note": "default-off, env-gated, no provider fallback",
    },
    {
        "label": "Living Learning",
        "command": "living learning status",
        "state": "READ ONLY",
        "opens": "heartbeat route",
        "note": "safe growth status, no verifier execution",
    },
    {
        "label": "Mycelium",
        "command": "colony mycelium status",
        "state": "CONTRACT ONLY",
        "opens": "status/contract output",
        "note": "signal propagation disabled",
    },
    {
        "label": "Simulation",
        "command": "colony simulation status",
        "state": "CONTRACT ONLY",
        "opens": "status/contract output",
        "note": "simulation runtime disabled",
    },
    {
        "label": "Proposal Lane",
        "command": "colony proposal status",
        "state": "HUMAN APPROVAL REQUIRED",
        "opens": "proposal status output",
        "note": "proposal candidates only",
    },
]

ENGEL_FUTURE_UPGRADE_READINESS: list[dict[str, str]] = [
    {
        "name": "Trusted Lesson Apply Boundary",
        "states": "CONNECTED FOR REVIEW, HUMAN APPROVAL REQUIRED",
        "surface": "lesson candidates readiness status",
        "readiness": "ready for a separate verifier-covered trusted-write task packet",
        "next_step": "Josh chooses an exact approved lesson-apply contract; Guardian and verifiers check before any write",
        "guardrail": "trusted lesson apply remains absent and cannot self-enable",
    },
    {
        "name": "Colony Simulation Preview / Report",
        "states": "SCAFFOLD ONLY, DISABLED UNTIL APPROVED",
        "surface": "colony simulation status",
        "readiness": "contract visible; preview/report runtime remains unimplemented",
        "next_step": "Josh approves a bounded simulation-preview contract with no runtime autonomy",
        "guardrail": "no simulation runtime, workers, providers, reports, or loops are started",
    },
    {
        "name": "Mycelium Signal Propagation",
        "states": "CONTRACT ONLY, DISABLED",
        "surface": "colony mycelium status",
        "readiness": "read-only signal model is documented and visible",
        "next_step": "Josh approves a bounded signal-preview task before any propagation behavior exists",
        "guardrail": "signals stay untrusted and proposal-only; no propagation runtime is enabled",
    },
    {
        "name": "Remote Queens / Communication Queen Runtime",
        "states": "SCAFFOLD ONLY, NEEDS REVIEW",
        "surface": "colony hive remote queens",
        "readiness": "GUI/docs/status shape is visible; network runtime remains off",
        "next_step": "Josh approves a separate remote-queen contract if any device/network behavior is ever needed",
        "guardrail": "no WiFi discovery, sockets, remote execution, provider calls, or background workers",
    },
    {
        "name": "Offline Seed LLM Runtime",
        "states": "SCAFFOLD ONLY, DISABLED BY DEFAULT",
        "surface": "offline seed llm status",
        "readiness": "status route and packaged module are visible; runtime remains env-gated",
        "next_step": "Josh explicitly enables the local env gate for companion-only testing if desired",
        "guardrail": "no provider fallback, no command execution from model output, model text remains untrusted",
    },
    {
        "name": "Bounded Local Research Upgrade",
        "states": "READY FOR CONTRACT, HUMAN APPROVAL REQUIRED",
        "surface": "research search status",
        "readiness": "local/offline research surfaces are visible; live internet remains disabled",
        "next_step": "Josh approves a bounded research contract before any live source or provider path exists",
        "guardrail": "no live internet, browser automation, provider/API call, or automatic research",
    },
    {
        "name": "Approved Learning Integration",
        "states": "FUTURE ONLY, HUMAN APPROVAL REQUIRED",
        "surface": "living learning status",
        "readiness": "safe growth heartbeat shows the observe/propose/verify/report/approve/apply boundary",
        "next_step": "Josh approves a narrow integration task after verifier coverage is defined",
        "guardrail": "no learning apply, trusted-memory write, queue mutation, or digest/history write",
    },
    {
        "name": "Source Proposal Support",
        "states": "FUTURE ONLY, SOURCE-EDIT CONTRACT REQUIRED",
        "surface": "complex routes status",
        "readiness": "route visibility and reports can inform future proposals",
        "next_step": "Josh provides an explicit source-edit task with backup, rollback, and verification",
        "guardrail": "no self-directed source edits or command execution from model output",
    },
    {
        "name": "Long-Term Memory Drive Integration",
        "states": "CONNECTED, READ ONLY, NEEDS REVIEW FOR ANY WRITE",
        "surface": "long term memory drive status",
        "readiness": "/opt/engel is active CT246 SSD; /mnt/engel-hdd-vault is Dell HDD archive; CT245 offline-vault storage remains disabled and not required",
        "next_step": "Josh approves any future import/sync/write contract separately",
        "guardrail": "no recursive scan, automatic sync, trusted-memory promotion, queue mutation, or drive write",
    },
]

PERMISSION_GUARD_TEXT = (
    "These toggles do not grant runtime power by themselves. Unsafe actions require "
    "separate human approval, contract updates, and verifier checks."
)

PASSWORD_GATE_COPY = (
    "Global password gate protects actions; it does not bypass safety. "
    "Password does not approve high-risk actions by itself. "
    "Contracts, verifiers, receipts, and authority hierarchy still apply. "
    "Blocked actions remain blocked even with password. "
    "Action IDs use strict allowlists and canonicalization. "
    "SQL-injection-style, Unicode, encoding, whitespace, and prompt-injection bypass attempts are rejected. "
    "If not configured, run: python engel_global_password_gate.py --setup"
)

HIVE_PERMISSION_HASH_ENV = "ENGEL_HIVE_PERMISSION_PASSWORD_HASH"

SUPER_SWARM_LIVE_COPY = (
    "Hive Live is visual + local read-only signal refresh only. Growth reflects gathered local "
    "research artifacts. Proposals remain untrusted until human-approved."
)

SUPER_SWARM_LIVE_MEANING = (
    "Animate and refresh local read-only hive signals for this GUI session. This does not start "
    "autonomous agents, write memory, apply lessons, edit source, mutate queues, call providers, "
    "browse, or run background services."
)

LOCAL_SIGNAL_SOURCE_DIRS = [
    "memory",
    "reports",
    "reports/codex_bridge",
    "reports/app",
    "reports/security",
    "reports/proposal_autonomy",
    "reports/colony",
]

MAX_LOCAL_SIGNAL_FILES = 700
MAX_LOCAL_SIGNAL_BYTES = 4096
MAX_QUEEN_FOLDER_SUMMARY_FILES = 200

SAFE_QUEEN_RESEARCH_LINK_DIRS = [
    "memory",
    "reports",
    "reports/codex_bridge",
    "reports/app",
    "reports/security",
    "reports/colony",
    "reports/proposal_autonomy",
    "assets",
]

QUEEN_RESEARCH_LINK_TEMPLATES: list[dict[str, Any]] = [
    {
        "queen_id": "memory_queen",
        "queen_label": "Memory Queen",
        "role": "Coordinates chat memory, thought seed, and project history context.",
        "assigned_worker_groups": ["Chat Memory Workers", "Thought Seed Workers", "Project History Workers"],
    },
    {
        "queen_id": "research_queen",
        "queen_label": "Research Queen",
        "role": "Coordinates local research reports and source-summary context.",
        "assigned_worker_groups": ["Research Report Workers", "Source Summary Workers"],
    },
    {
        "queen_id": "guardian_queen",
        "queen_label": "Guardian Queen",
        "role": "Coordinates safety, permission, and verifier warning context.",
        "assigned_worker_groups": ["Security Workers", "Permission Workers", "Verifier Workers"],
    },
    {
        "queen_id": "proposal_queen",
        "queen_label": "Proposal Queen",
        "role": "Coordinates untrusted proposal and lesson-candidate context.",
        "assigned_worker_groups": ["Proposal Candidate Workers", "Lesson Candidate Workers"],
    },
    {
        "queen_id": "verifier_queen",
        "queen_label": "Verifier Queen",
        "role": "Coordinates verifier result and route-status context.",
        "assigned_worker_groups": ["Verifier Workers", "Route Status Workers"],
    },
]

COMMUNICATION_QUEEN_STATUS: dict[str, Any] = {
    "enabled": False,
    "runtime_wifi_enabled": False,
    "trusted_wifi_runtime_enabled": False,
    "runtime_remote_queen_network_enabled": False,
    "remote_queen_runtime_enabled": False,
    "network_discovery_enabled": False,
    "device_pairing_enabled": False,
    "background_service_enabled": False,
    "background_worker_enabled": False,
    "autonomous_remote_work_enabled": False,
    "remote_execution_enabled": False,
    "remote_file_transfer_enabled": False,
    "trusted_memory_write_enabled": False,
    "remote_memory_write_enabled": False,
    "queue_mutation_enabled": False,
    "remote_source_edit_enabled": False,
    "source_edit_enabled": False,
    "remote_queue_mutation_enabled": False,
    "applied_learning_enabled": False,
    "provider_network_enabled": False,
    "provider_or_api_calls_enabled": False,
    "internet_behavior_enabled": False,
    "status_label": "Scaffold only / offline / no network",
    "safety_badge": "OFFLINE SCAFFOLD - NO NETWORK ACTIVE",
}

COMMUNICATION_QUEEN_RUNTIME_CARDS: list[dict[str, str]] = [
    {"label": "Trusted WiFi Runtime", "key": "trusted_wifi_runtime_enabled"},
    {"label": "Remote Queen Runtime", "key": "remote_queen_runtime_enabled"},
    {"label": "Network Discovery", "key": "network_discovery_enabled"},
    {"label": "Remote Execution", "key": "remote_execution_enabled"},
    {"label": "Remote Memory Writes", "key": "remote_memory_write_enabled"},
    {"label": "Remote Source Edits", "key": "remote_source_edit_enabled"},
    {"label": "Background Workers", "key": "background_worker_enabled"},
]

COMMUNICATION_QUEEN_ARCHITECTURE_COPY = (
    "The Communication Queen is the future coordinator for trusted local Remote Queens. "
    "Remote Queens may eventually host small, slow, low-priority project hives so the main "
    "Engel computer can stay lighter and safer.\n\n"
    "For now this panel is only an architecture scaffold. It does not scan WiFi, connect to "
    "devices, send tasks, receive remote outputs, or run background workers. Remote Queen "
    "outputs are untrusted until reviewed, scanned, verified, and human-approved.\n\n"
    "If Communication Queen later gains chat or status input, that text must pass through "
    "the shared deterministic communication membrane before any adapter, route, or model boundary."
)

REMOTE_QUEEN_CANDIDATES: list[dict[str, Any]] = [
    {
        "display_name": "Remote Queen Alpha",
        "role": "Future low-priority research hive host",
        "trust_state": "Placeholder only",
        "connection_state": "Not connected / placeholder only",
        "allowed_future_work": [
            "Report-only proposal drafting",
            "Slow document summarization candidates",
        ],
        "forbidden_actions": [
            "No memory writes",
            "No source edits",
            "No queue mutation",
        ],
        "last_seen": "Never - placeholder only",
        "notes": [
            "No device discovery has run.",
            "No remote device is connected.",
            "No remote task can be assigned.",
        ],
    },
    {
        "display_name": "Remote Queen Beta",
        "role": "Future slow project indexing hive",
        "trust_state": "Placeholder only",
        "connection_state": "Not connected / placeholder only",
        "allowed_future_work": [
            "Local summarization candidates",
            "Non-urgent project index preparation",
        ],
        "forbidden_actions": [
            "No network calls",
            "No autonomous dispatch",
            "No trusted writes",
        ],
        "last_seen": "Never - placeholder only",
        "notes": [
            "No device discovery has run.",
            "No remote device is connected.",
            "No remote task can be assigned.",
        ],
    },
    {
        "display_name": "Remote Queen Garden",
        "role": "Future project-specific helper hive for quiet background planning",
        "trust_state": "Placeholder only",
        "connection_state": "Not connected / placeholder only",
        "allowed_future_work": [
            "Low-priority planning summaries",
            "Project-specific scout hive notes",
        ],
        "forbidden_actions": [
            "No provider calls",
            "No remote execution",
            "No background loops",
        ],
        "last_seen": "Never - placeholder only",
        "notes": [
            "No device discovery has run.",
            "No remote device is connected.",
            "No remote task can be assigned.",
        ],
    },
]

COMMUNICATION_QUEEN_FUTURE_WORKFLOW = [
    "Human approves a trusted Remote Queen device.",
    "Engel verifies the local trust contract.",
    "Communication Queen records the device as a candidate.",
    "Human chooses a low-priority project hive assignment.",
    "Remote Queen returns report-only outputs.",
    "Engel scans outputs as untrusted content.",
    "Verifiers run before anything is promoted.",
    "Human approval is required before trusted memory, source, queue, or project state changes.",
]

COMMUNICATION_QUEEN_FUTURE_ROUTES: list[dict[str, Any]] = [
    {
        "route": "communication queen status",
        "implemented_now": False,
        "should_execute_in_test": False,
        "status": "Future / not implemented / should not execute in route regression yet",
    },
    {
        "route": "communication queen contract",
        "implemented_now": False,
        "should_execute_in_test": False,
        "status": "Future / not implemented / should not execute in route regression yet",
    },
    {
        "route": "remote queens status",
        "implemented_now": False,
        "should_execute_in_test": False,
        "status": "Future / not implemented / should not execute in route regression yet",
    },
    {
        "route": "remote queens candidates",
        "implemented_now": False,
        "should_execute_in_test": False,
        "status": "Future / not implemented / should not execute in route regression yet",
    },
    {
        "route": "remote queen assignment preview",
        "implemented_now": False,
        "should_execute_in_test": False,
        "status": "Future / not implemented / should not execute in route regression yet",
    },
]

EMPTY_FOLDER_SUMMARY = {
    "file_count": 0,
    "markdown_count": 0,
    "json_count": 0,
    "python_count": 0,
    "report_count": 0,
    "proposal_count": 0,
    "verifier_count": 0,
    "warning_count": 0,
    "bounded_scan_note": "No folder linked for this local GUI session.",
    "partial": False,
}

MEMORY_COLONY_SIGNAL_RULES = [
    {
        "colony_id": "chat-memories",
        "label": "Chat Memories Nest",
        "needles": ["conversation", "chat", "offline_memory"],
        "signal_type": "context signal",
        "safety_state": "read-only local memory reference",
    },
    {
        "colony_id": "thought-seeds",
        "label": "Thought Seeds Nest",
        "needles": ["thought", "inbox", "seed"],
        "signal_type": "context signal",
        "safety_state": "candidate context only",
    },
    {
        "colony_id": "research-reports",
        "label": "Research Reports Nest",
        "needles": ["reports/research", "research", "report"],
        "signal_type": "context signal",
        "safety_state": "read-only report reference",
    },
    {
        "colony_id": "approved-lessons",
        "label": "Approved Lessons Nest",
        "needles": ["approved", "lesson"],
        "signal_type": "confidence signal",
        "safety_state": "no lesson apply from hive",
    },
    {
        "colony_id": "swarm-trails",
        "label": "Swarm Trails Nest",
        "needles": ["swarm", "trail"],
        "signal_type": "context signal",
        "safety_state": "no swarm runtime",
    },
    {
        "colony_id": "project-history",
        "label": "Project History Nest",
        "needles": ["project_history", "project-memory", "checkpoint", "session_snapshot"],
        "signal_type": "context signal",
        "safety_state": "no digest/history write",
    },
    {
        "colony_id": "route-status",
        "label": "Route Status Nest",
        "needles": ["route", "verification_set", "metadata"],
        "signal_type": "verifier signal",
        "safety_state": "no route mutation",
    },
    {
        "colony_id": "verifier-results",
        "label": "Verifier Results Nest",
        "needles": ["verifier", "verification", "verify_"],
        "signal_type": "verifier signal",
        "safety_state": "external verifier posture only",
    },
    {
        "colony_id": "proposal-candidates",
        "label": "Proposal Candidates Nest",
        "needles": ["proposal", "candidate", "next_steps"],
        "signal_type": "proposal signal",
        "safety_state": "proposal-only",
    },
    {
        "colony_id": "safety-contracts",
        "label": "Safety Contracts Nest",
        "needles": ["safety", "guardian", "contract", "permission", "boundary"],
        "signal_type": "warning signal",
        "safety_state": "Josh first; Guardian second; Engel/runtime below both",
    },
]


def _root_path(root: str | Path) -> Path:
    return Path(root).resolve()


def _safe_local_path(root: Path, relative_path: str) -> Path | None:
    candidate = (root / relative_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return candidate


def _path_state(app_root: Path, relative_path: str) -> str:
    if str(relative_path).strip().lower() == ENGEL_LONG_TERM_MEMORY_DRIVE.lower():
        drive_path = Path(ENGEL_LONG_TERM_MEMORY_DRIVE)
        return "present" if drive_path.exists() else "missing"
    local_path = _safe_local_path(app_root, relative_path)
    if not local_path:
        return "blocked"
    return "present" if local_path.exists() else "missing"


def build_long_term_memory_drive_snapshot() -> dict[str, Any]:
    return build_memory_archive_snapshot()


def render_long_term_memory_drive_status() -> str:
    return render_memory_archive_status().replace(
        "# Engel Memory Archive Status",
        "# Engel Long-Term Memory Drive Status",
        1,
    )


def _hidden_import_state(app_root: Path) -> str:
    spec_path = _safe_local_path(app_root, "staging/app/build_work/spec/Engel.spec")
    if not spec_path or not spec_path.exists():
        return "spec missing"
    try:
        text = spec_path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return "read error: " + str(exc)
    return "included" if "engel_research_brain_v2" in text else "missing"


def build_engel_mind_connections_snapshot(root: str | Path) -> dict[str, Any]:
    app_root = _root_path(root)
    long_term_memory_snapshot = build_long_term_memory_drive_snapshot()
    colonies = []
    for colony in ENGEL_MIND_MEMORY_COLONIES:
        enriched = dict(colony)
        enriched["path_state"] = _path_state(app_root, str(colony.get("surface", "")))
        colonies.append(enriched)

    return {
        "title": "Engel Mind / Hive Connections",
        "mode": "read-only/status-only connection map",
        "generated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "root": str(app_root),
        "identity": {
            "name": "Engel Mind",
            "frame": "Local Supercolony",
            "one_identity": "One Companion Identity",
            "many_colonies": "Many Safe Local Memory Colonies",
            "gate_hierarchy": "Josh First / Guardian Safety / Engel Gated",
            "analogy": (
                "Argentine ant supercolonies inspire the information architecture: many nests, "
                "many workers, many queens, one cooperative colony identity. This is a structural "
                "software metaphor only, not literal biological intelligence."
            ),
        },
        "colonies": colonies,
        "safe_capabilities": list(ENGEL_MIND_SAFE_CAPABILITIES),
        "guardian_boundaries": list(ENGEL_MIND_GUARDIAN_BOUNDARIES),
        "action_gates": list(ENGEL_MIND_ACTION_GATES),
        "command_surfaces": list(ENGEL_MIND_COMMAND_SURFACES),
        "future_upgrades": list(ENGEL_FUTURE_UPGRADE_READINESS),
        "long_term_memory_drive": long_term_memory_snapshot,
        "package_state": {
            "live_app": _path_state(app_root, "live/app/Engel.exe"),
            "super_swarm_hive_3d": _path_state(app_root, "live/app/EngelSuperSwarmHive3D.exe"),
            "operator_manual": _path_state(app_root, "Engel_Operator_Manual.pdf"),
            "research_brain_module": _path_state(app_root, "engel_research_brain_v2.py"),
            "research_office": _path_state(app_root, "engel_research_office.py"),
            "research_thinking_screen": _path_state(app_root, "engel_research_thinking_screen.py"),
            "offline_seed_llm": _path_state(app_root, "engel_offline_seed_llm.py"),
            "long_term_memory_archive": long_term_memory_snapshot["archive_status"],
            "hidden_import_engel_research_brain_v2": _hidden_import_state(app_root),
        },
    }


def render_engel_mind_connections_status(
    root: str | Path,
    title: str = "# Engel Mind / Hive Connections / Upgrade Connections",
) -> str:
    snapshot = build_engel_mind_connections_snapshot(root)
    identity = snapshot["identity"]
    lines = [
        title,
        "",
        "Mode: " + snapshot["mode"],
        "Behavior: shallow local presence checks plus known deterministic route inventory.",
        "Time: " + snapshot["generated_at"],
        "",
        "## Colony Identity Panel",
        "- " + identity["name"],
        "- " + identity["frame"],
        "- " + identity["one_identity"],
        "- " + identity["many_colonies"],
        "- " + identity["gate_hierarchy"],
        "- Structural analogy only: " + identity["analogy"],
        "",
        "## Local Memory Colonies Panel",
    ]
    for colony in snapshot["colonies"]:
        lines.extend(
            [
                "- "
                + colony["name"]
                + " | "
                + ", ".join(colony["states"])
                + " | path="
                + colony["path_state"],
                "  command: " + colony["command"],
                "  role: " + colony["role"],
                "  guardrail: " + colony["guardrail"],
            ]
        )

    lines.extend(["", "## Cooperative Intelligence Panel"])
    for item in snapshot["safe_capabilities"]:
        lines.append(
            "- "
            + item["capability"]
            + " | "
            + item["state"]
            + " | "
            + item["meaning"]
        )

    lines.extend(["", "## Guardian Safety Panel"])
    for boundary in snapshot["guardian_boundaries"]:
        lines.append("- " + boundary)

    lines.extend(["", "## Action Gate Panel"])
    for gate in snapshot["action_gates"]:
        lines.append("- " + gate["level"] + ": " + gate["state"] + " | " + gate["gate"])

    lines.extend(["", "## Launchable Local Screens / Commands"])
    for surface in snapshot["command_surfaces"]:
        lines.append(
            "- "
            + surface["label"]
            + " | "
            + surface["state"]
            + " | `"
            + surface["command"]
            + "` | "
            + surface["note"]
        )

    lines.extend(["", "## Future Upgrade Readiness Panel"])
    for upgrade in snapshot["future_upgrades"]:
        lines.extend(
            [
                "- " + upgrade["name"] + " | " + upgrade["states"],
                "  surface: " + upgrade["surface"],
                "  readiness: " + upgrade["readiness"],
                "  next step: " + upgrade["next_step"],
                "  guardrail: " + upgrade["guardrail"],
            ]
        )
    lines.extend(
        [
            "",
            "Future upgrade rule:",
            "- All future upgrades may be connected for visibility and next-step review.",
            "- No future upgrade is enabled, activated, trusted, or executed automatically.",
            "- Authority order stays fixed for every future upgrade: Josh first, Guardian second, Engel/runtime below both.",
        ]
    )

    package = snapshot["package_state"]
    long_term = snapshot["long_term_memory_drive"]
    lines.extend(
        [
            "",
            "## Package / Resource Connections",
            "- live\\app\\Engel.exe: " + package["live_app"],
            "- live\\app\\EngelSuperSwarmHive3D.exe: " + package["super_swarm_hive_3d"],
            "- Engel_Operator_Manual.pdf: " + package["operator_manual"],
            "- engel_research_brain_v2.py: " + package["research_brain_module"],
            "- PyInstaller hidden import engel_research_brain_v2: " + package["hidden_import_engel_research_brain_v2"],
            "- engel_research_office.py: " + package["research_office"],
            "- engel_research_thinking_screen.py: " + package["research_thinking_screen"],
            "- engel_offline_seed_llm.py: " + package["offline_seed_llm"],
            "- External archive status: " + package["long_term_memory_archive"],
            "- External archive available roots: " + (", ".join(long_term["available_archive_roots"]) if long_term["available_archive_roots"] else "none"),
            "- External archive marker present: " + str(long_term["marker_present"]),
            "- External archive top-level folders/files: "
            + str(long_term["top_level_folder_count"])
            + "/"
            + str(long_term["top_level_file_count"]),
            "- Deprecated external-drive archive paths are not required on the ROG controller",
            "- Active work root: D:\\b.WorkSpace\\Engel App",
            "- Controller-local archive fallback: D:\\b.WorkSpace\\Engel App\\runtime\\engel_memory_archive",
            "",
            "## Safety Boundaries Still Enforced",
            "- No provider/API/network call.",
            "- No live internet research.",
            "- No autonomous loop or background worker.",
            "- No model-command execution.",
            "- No trusted-memory write.",
            "- No queue mutation, digest/history write, or ALIVE_STATE write.",
            "- No source edits from this status surface.",
            "- No fake live colony activity.",
            "- Reports are audit artifacts only and are not command authority.",
            "- Authority order: Josh first, Guardian second, Engel/runtime below both for activation, mutation, permission, registry, runtime action, trusted-memory, provider/network, and source-edit gates.",
        ]
    )
    return "\n".join(lines)


def render_future_upgrades_status(root: str | Path) -> str:
    snapshot = build_engel_mind_connections_snapshot(root)
    lines = [
        "# Future Upgrades Status",
        "",
        "Mode: read-only/status-only readiness map",
        "Rule: future upgrades are connected for visibility and next-step planning, not automatically enabled.",
        "Root: " + snapshot["root"],
        "Time: " + snapshot["generated_at"],
        "",
        "Connected future-upgrade readiness items:",
    ]
    for upgrade in snapshot["future_upgrades"]:
        lines.extend(
            [
                "- " + upgrade["name"] + " | " + upgrade["states"],
                "  surface: " + upgrade["surface"],
                "  readiness: " + upgrade["readiness"],
                "  next step: " + upgrade["next_step"],
                "  guardrail: " + upgrade["guardrail"],
            ]
        )
    lines.extend(
        [
            "",
            "Next-step gate:",
            "- Engel may observe, summarize, compare, and propose next steps.",
            "- Guardian reviews and blocks unsafe paths under Josh's approval authority.",
            "- Josh approves exact task-scoped upgrades.",
            "- Verifiers run externally before apply.",
            "- Only explicit approved actions may cross gates.",
            "",
            "Safety:",
            "- READ_ONLY",
            "- STATUS_ONLY",
            "- NO_AUTOMATIC_ENABLEMENT",
            "- NO_PROVIDER_CALL",
            "- NO_NETWORK_CALL",
            "- NO_LIVE_INTERNET",
            "- NO_BACKGROUND_WORKER",
            "- NO_AUTONOMOUS_LOOP",
            "- NO_TRUSTED_MEMORY_WRITE",
            "- NO_QUEUE_MUTATION",
            "- NO_SOURCE_EDIT",
            "- NO_ALIVE_STATE_WRITE",
            "- NO_FAKE_LIVE_ACTIVITY",
            "- Authority order: Josh first, Guardian second, Engel/runtime below both.",
        ]
    )
    return "\n".join(lines)


def _path_is_inside(path: Path, base: Path) -> bool:
    try:
        path.relative_to(base)
        return True
    except ValueError:
        return False


def _safe_queen_roots(app_root: Path) -> list[Path]:
    roots: list[Path] = []
    for relative_dir in SAFE_QUEEN_RESEARCH_LINK_DIRS:
        candidate = _safe_local_path(app_root, relative_dir)
        if candidate:
            roots.append(candidate)
    return roots


def _format_timestamp(value: float | None) -> str:
    if value is None:
        return "missing"
    return datetime.datetime.fromtimestamp(value).strftime("%Y-%m-%d %H:%M:%S")


def _read_preview(path: Path, limit: int = 520) -> str:
    if not path.exists():
        return "No local artifact is present yet."
    if path.is_dir():
        try:
            names = sorted(item.name for item in path.iterdir())[:8]
        except Exception as exc:
            return "Folder read warning: " + str(exc)
        if not names:
            return "Local folder is present but currently empty."
        return "Folder entries: " + ", ".join(names)
    if not path.is_file():
        return "Local artifact is present but is not a regular file."
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            text = handle.read(limit + 1)
    except Exception as exc:
        return "Read warning: " + str(exc)
    cleaned = " ".join(text.replace("\ufeff", "").replace("\r", "\n").split())
    if not cleaned:
        return "Local file is present but has no preview text."
    if len(cleaned) > limit:
        cleaned = cleaned[:limit].rstrip() + "..."
    return cleaned


def _iter_signal_files(app_root: Path) -> list[Path]:
    files: list[Path] = []
    seen: set[Path] = set()
    for relative_dir in LOCAL_SIGNAL_SOURCE_DIRS:
        base = _safe_local_path(app_root, relative_dir)
        if not base or not base.exists():
            continue
        if base.is_file():
            candidates = [base]
        else:
            try:
                candidates = [item for item in base.rglob("*") if item.is_file()]
            except Exception:
                candidates = []
        for candidate in sorted(candidates):
            resolved = candidate.resolve()
            if resolved in seen:
                continue
            try:
                resolved.relative_to(app_root)
            except ValueError:
                continue
            seen.add(resolved)
            files.append(resolved)
            if len(files) >= MAX_LOCAL_SIGNAL_FILES:
                return files
    return files


def _read_signal_text(path: Path) -> str:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            return handle.read(MAX_LOCAL_SIGNAL_BYTES).replace("\ufeff", "").lower()
    except Exception:
        return ""


def _empty_folder_summary(note: str | None = None) -> dict[str, Any]:
    summary = dict(EMPTY_FOLDER_SUMMARY)
    if note:
        summary["bounded_scan_note"] = note
    return summary


def validate_queen_research_folder(root: str | Path, folder: str | Path) -> dict[str, Any]:
    app_root = _root_path(root)
    raw_value = str(folder).strip()
    if not raw_value:
        return {
            "ok": False,
            "folder_status": "NO_FOLDER_SELECTED",
            "safety_state": "NO_SESSION_LINK",
            "message": "No folder was selected.",
            "path": "",
            "can_link": False,
        }
    lowered = raw_value.lower()
    if lowered.startswith(("http:", "https:", "ftp:", "file:")):
        return {
            "ok": False,
            "folder_status": "BLOCKED_URL_OR_REMOTE_PATH",
            "safety_state": "BLOCKED",
            "message": "Remote or URL-style paths are blocked for Queen research links.",
            "path": raw_value,
            "can_link": False,
        }
    if raw_value.startswith("\\\\"):
        return {
            "ok": False,
            "folder_status": "BLOCKED_UNC_PATH",
            "safety_state": "BLOCKED",
            "message": "UNC or network-style paths are blocked by default.",
            "path": raw_value,
            "can_link": False,
        }
    try:
        candidate = Path(raw_value)
        if not candidate.is_absolute():
            candidate = app_root / candidate
        resolved = candidate.resolve()
    except Exception as exc:
        return {
            "ok": False,
            "folder_status": "INVALID_PATH",
            "safety_state": "BLOCKED",
            "message": "Path could not be resolved: " + str(exc),
            "path": raw_value,
            "can_link": False,
        }
    if not _path_is_inside(resolved, app_root):
        return {
            "ok": False,
            "folder_status": "REQUIRES_APPROVAL_OUTSIDE_ENGEL_ROOT",
            "safety_state": "REQUIRES_APPROVAL",
            "message": "Folder is outside the Engel App root and was not linked.",
            "path": str(resolved),
            "can_link": False,
        }
    if not resolved.exists():
        return {
            "ok": False,
            "folder_status": "MISSING_FOLDER",
            "safety_state": "BLOCKED",
            "message": "Folder does not exist.",
            "path": str(resolved),
            "can_link": False,
        }
    if not resolved.is_dir():
        return {
            "ok": False,
            "folder_status": "NOT_A_DIRECTORY",
            "safety_state": "BLOCKED",
            "message": "Selected path is not a directory.",
            "path": str(resolved),
            "can_link": False,
        }
    if resolved.is_symlink():
        return {
            "ok": False,
            "folder_status": "BLOCKED_SYMLINK",
            "safety_state": "BLOCKED",
            "message": "Symlink folders are blocked for Queen research links.",
            "path": str(resolved),
            "can_link": False,
        }
    safe_roots = _safe_queen_roots(app_root)
    if not any(resolved == safe_root or _path_is_inside(resolved, safe_root) for safe_root in safe_roots):
        return {
            "ok": False,
            "folder_status": "REQUIRES_APPROVAL_OUTSIDE_SAFE_SCOPE",
            "safety_state": "REQUIRES_APPROVAL",
            "message": "Folder is inside Engel App but outside the configured Queen link safe scopes.",
            "path": str(resolved),
            "can_link": False,
        }
    return {
        "ok": True,
        "folder_status": "LOCAL_FOLDER_READY",
        "safety_state": "LOCAL SESSION / READ-ONLY / PROPOSAL CONTEXT",
        "message": "Folder linked for this local GUI session only.",
        "path": str(resolved),
        "can_link": True,
    }


def summarize_queen_research_folder(root: str | Path, folder: str | Path) -> dict[str, Any]:
    validation = validate_queen_research_folder(root, folder)
    if not validation.get("ok"):
        return _empty_folder_summary(str(validation.get("message", "Folder was not linked.")))
    app_root = _root_path(root)
    folder_path = Path(str(validation["path"]))
    summary = _empty_folder_summary()
    summary["bounded_scan_note"] = "Inspected filenames and metadata only; no full-file parsing; max files=" + str(MAX_QUEEN_FOLDER_SUMMARY_FILES) + "."
    stack = [folder_path]
    inspected = 0
    while stack and inspected < MAX_QUEEN_FOLDER_SUMMARY_FILES:
        current = stack.pop()
        try:
            entries = sorted(current.iterdir(), key=lambda item: item.name.lower())
        except Exception:
            continue
        for item in entries:
            if inspected >= MAX_QUEEN_FOLDER_SUMMARY_FILES:
                break
            try:
                resolved = item.resolve()
            except Exception:
                continue
            if not _path_is_inside(resolved, app_root):
                continue
            if item.is_symlink():
                continue
            if item.is_dir():
                stack.append(item)
                continue
            if not item.is_file():
                continue
            inspected += 1
            summary["file_count"] += 1
            name = item.name.lower()
            suffix = item.suffix.lower()
            if suffix in [".md", ".markdown"]:
                summary["markdown_count"] += 1
            if suffix == ".json" or suffix == ".jsonl":
                summary["json_count"] += 1
            if suffix == ".py":
                summary["python_count"] += 1
            if "report" in name:
                summary["report_count"] += 1
            if "proposal" in name or "candidate" in name:
                summary["proposal_count"] += 1
            if "verifier" in name or "verify" in name or "verification" in name:
                summary["verifier_count"] += 1
            if "warning" in name or "safety" in name or "guardian" in name or "blocked" in name:
                summary["warning_count"] += 1
    summary["partial"] = inspected >= MAX_QUEEN_FOLDER_SUMMARY_FILES
    if summary["partial"]:
        summary["bounded_scan_note"] += " Summary is partial due to the file cap."
    return summary


def build_queen_research_link_templates(root: str | Path) -> list[dict[str, Any]]:
    _root_path(root)
    links: list[dict[str, Any]] = []
    for template in QUEEN_RESEARCH_LINK_TEMPLATES:
        links.append(
            {
                **template,
                "linked_folder": "",
                "folder_status": "NO_SESSION_LINK",
                "safety_state": "LOCAL SESSION ONLY / NO FOLDER LINKED",
                "last_refresh_time": "not refreshed",
                "summary_counts": _empty_folder_summary(),
                "proposal_only": True,
                "session_only": True,
                "sent_to_workers": False,
                "handoff_status": "NOT_SENT",
            }
        )
    return links


def build_queen_research_links_snapshot(root: str | Path, session_links: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    app_root = _root_path(root)
    links = session_links if session_links is not None else build_queen_research_link_templates(app_root)
    return {
        "title": "Queen Research Links",
        "mode": "SESSION_LOCAL_READ_ONLY_VISUAL_ASSIGNMENTS",
        "generated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "root": str(app_root),
        "queen_links": links,
        "safe_scopes": [str(path) for path in _safe_queen_roots(app_root)],
        "max_summary_files": MAX_QUEEN_FOLDER_SUMMARY_FILES,
        "safety": [
            "Queen research folder links are session-only.",
            "Queen-to-worker handoffs are visual/read-only context.",
            "Workers do not start background jobs.",
            "No mutation or provider/network behavior.",
            "External folders are blocked or require a separate approved workflow.",
        ],
    }


def build_communication_queen_snapshot(root: str | Path) -> dict[str, Any]:
    app_root = _root_path(root)
    status = dict(COMMUNICATION_QUEEN_STATUS)
    runtime_cards: list[dict[str, Any]] = []
    for card in COMMUNICATION_QUEEN_RUNTIME_CARDS:
        enabled = bool(status.get(card["key"], False))
        runtime_cards.append(
            {
                "label": card["label"],
                "key": card["key"],
                "enabled": enabled,
                "value": "Enabled" if enabled else "Disabled",
            }
        )
    candidates: list[dict[str, Any]] = []
    for candidate in REMOTE_QUEEN_CANDIDATES:
        candidates.append(
            {
                **candidate,
                "device_discovery_state": "No device discovery has run.",
                "can_assign_tasks_now": False,
                "assignment_state": "No remote task can be assigned.",
                "output_trust": "Untrusted until reviewed, scanned, verified, and human-approved.",
            }
        )
    return {
        "title": "Communication Queen",
        "subtitle": "Future trusted-WiFi coordinator for Remote Queens and small project hives.",
        "mode": "READ_ONLY_ARCHITECTURE_SCAFFOLD",
        "generated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "root": str(app_root),
        "status": status,
        "runtime_safety_cards": runtime_cards,
        "architecture_copy": COMMUNICATION_QUEEN_ARCHITECTURE_COPY,
        "remote_queen_candidates": candidates,
        "future_workflow": list(COMMUNICATION_QUEEN_FUTURE_WORKFLOW),
        "future_routes": [dict(route) for route in COMMUNICATION_QUEEN_FUTURE_ROUTES],
        "safety": [
            "Trusted WiFi communication is not active yet.",
            "Remote Queens are not connected yet.",
            "No network scanning is performed.",
            "No background worker is running.",
            "No remote task execution is enabled.",
            "All remote assignment ideas are proposal candidates only.",
            "All Remote Queen outputs are untrusted until reviewed, verified, and human-approved.",
            "Future Communication Queen chat/status text must pass through engel_communication_router first.",
        ],
    }


def _signal_growth_level(count: int) -> int:
    if count <= 0:
        return 0
    if count < 3:
        return 1
    if count < 8:
        return 2
    if count < 18:
        return 3
    if count < 38:
        return 4
    return 5


def _matches_any(text: str, needles: list[str]) -> bool:
    return any(needle.lower() in text for needle in needles)


def build_local_hive_signal_snapshot(root: str | Path) -> dict[str, Any]:
    app_root = _root_path(root)
    files = _iter_signal_files(app_root)
    category_counts: dict[str, int] = {
        str(rule["colony_id"]): 0 for rule in MEMORY_COLONY_SIGNAL_RULES
    }
    report_count = 0
    proposal_candidate_count = 0
    verifier_signal_count = 0
    guardian_warning_count = 0
    recent_project_history_markers = 0
    inspected_bytes = 0
    recent_paths: list[str] = []

    for path in files:
        try:
            relative = path.relative_to(app_root).as_posix()
        except ValueError:
            continue
        lowered = relative.lower()
        text = _read_signal_text(path)
        inspected_bytes += min(MAX_LOCAL_SIGNAL_BYTES, len(text))
        combined = lowered + "\n" + text

        if lowered.startswith("reports/"):
            report_count += 1
        if _matches_any(combined, ["proposal", "candidate", "next step", "next_steps"]):
            proposal_candidate_count += 1
        if _matches_any(combined, ["verifier", "verification", "verify_", "verification_pass"]):
            verifier_signal_count += 1
        if _matches_any(combined, ["guardian", "safety", "warning", "blocked", "forbidden", "boundary"]):
            guardian_warning_count += 1
        if _matches_any(combined, ["project_history", "project memory", "checkpoint", "session snapshot"]):
            recent_project_history_markers += 1

        for rule in MEMORY_COLONY_SIGNAL_RULES:
            if _matches_any(combined, list(rule["needles"])):
                category_counts[str(rule["colony_id"])] += 1

    for path in sorted(files, key=lambda item: item.stat().st_mtime if item.exists() else 0, reverse=True)[:8]:
        try:
            recent_paths.append(path.relative_to(app_root).as_posix())
        except ValueError:
            continue

    memory_colony_signals = []
    for rule in MEMORY_COLONY_SIGNAL_RULES:
        count = category_counts[str(rule["colony_id"])]
        memory_colony_signals.append(
            {
                "colony_id": rule["colony_id"],
                "label": rule["label"],
                "count": count,
                "growth_level": _signal_growth_level(count),
                "signal_type": rule["signal_type"],
                "safety_state": rule["safety_state"],
            }
        )

    total_signal_strength = sum(item["count"] for item in memory_colony_signals)
    return {
        "live_enabled": False,
        "motion_paused": False,
        "reduced_motion": False,
        "last_local_refresh_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "files_inspected": len(files),
        "max_files": MAX_LOCAL_SIGNAL_FILES,
        "inspected_bytes": inspected_bytes,
        "local_signal_counts": category_counts,
        "memory_colony_signals": memory_colony_signals,
        "total_signal_strength": total_signal_strength,
        "report_count": report_count,
        "guardian_warning_count": guardian_warning_count,
        "proposal_candidate_count": proposal_candidate_count,
        "verifier_signal_count": verifier_signal_count,
        "recent_project_history_markers": recent_project_history_markers,
        "recent_local_paths": recent_paths,
        "mode_meaning": SUPER_SWARM_LIVE_MEANING,
        "ui_copy": SUPER_SWARM_LIVE_COPY,
        "safety_state": "VISUAL_ANIMATION_AND_BOUNDED_READ_ONLY_REFRESH_ONLY",
        "can_execute_from_hive": False,
    }


def _enrich_cell(app_root: Path, cell: dict[str, Any]) -> dict[str, Any]:
    local_path = _safe_local_path(app_root, str(cell["linked_local_artifact"]))
    exists = bool(local_path and local_path.exists())
    is_file = bool(local_path and local_path.is_file())
    is_dir = bool(local_path and local_path.is_dir())
    stat = None
    if local_path and exists:
        try:
            stat = local_path.stat()
        except Exception:
            stat = None
    kind = "file" if is_file else "folder" if is_dir else "missing"
    status = "LOCAL_PATH_READY" if exists else "WAITING_FOR_LOCAL_ARTIFACT"
    return {
        **cell,
        "station": cell["cell_name"],
        "worker": cell["actor"],
        "task": cell["current_task"],
        "local_link": cell["linked_local_artifact"],
        "absolute_path": str(local_path) if local_path else "",
        "exists": exists,
        "kind": kind,
        "last_updated": _format_timestamp(stat.st_mtime if stat else None),
        "size_bytes": stat.st_size if stat and is_file else 0,
        "status": status,
        "preview": _read_preview(local_path) if local_path else "Invalid local link.",
        "badges": _badges_for(cell, status),
    }


def _badges_for(cell: dict[str, Any], status: str) -> list[str]:
    badges = ["LOCAL_ONLY", status]
    if cell.get("proposal_only"):
        badges.append("PROPOSAL_ONLY")
    if cell.get("role") == "mycelium_signal":
        badges.append("READ_ONLY_FIRST_SIGNAL")
    if cell.get("role") == "guardian":
        badges.append("GUARDIAN_LAYER")
    return badges


def _group_cells(cells: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {role: [] for role in ROLE_ORDER}
    for cell in cells:
        grouped.setdefault(str(cell.get("role", "worker")), []).append(cell)
    return grouped


def _configured_hive_permission_hash() -> str:
    raw_value = os.environ.get(HIVE_PERMISSION_HASH_ENV, "").strip()
    if raw_value.lower().startswith("sha256:"):
        raw_value = raw_value.split(":", 1)[1].strip()
    return raw_value


def is_hive_permission_password_configured() -> bool:
    return global_password_gate.is_global_password_gate_configured()


def verify_hive_permission_password(candidate: str) -> bool:
    return global_password_gate.verify_global_password(candidate)


def _permission_by_id(permission_id: str) -> dict[str, Any] | None:
    for permission in HIVE_PERMISSION_GATES:
        if permission.get("permission_id") == permission_id:
            return permission
    return None


def request_permission_unlock(permission_id: str, supplied_value: str | None = None) -> dict[str, Any]:
    permission = _permission_by_id(permission_id)
    if not permission:
        return {
            "ok": False,
            "reason": "UNKNOWN_PERMISSION",
            "requested_state": "UNCHANGED",
            "can_execute_from_hive": False,
        }
    if not bool(permission.get("requires_approval")):
        return {
            "ok": True,
            "reason": "READ_ONLY_PERMISSION",
            "requested_state": permission.get("current_state", "READ_ONLY_FIRST"),
            "can_execute_from_hive": False,
        }
    if not is_hive_permission_password_configured():
        return {
            "ok": False,
            "reason": "PASSWORD_GATE_NOT_CONFIGURED",
            "message": "Global password gate is not configured. Run: python engel_global_password_gate.py --setup",
            "requested_state": "UNCHANGED",
            "can_execute_from_hive": False,
        }
    if supplied_value is None:
        return {
            "ok": False,
            "reason": "PASSWORD_REQUIRED",
            "requested_state": "UNCHANGED",
            "can_execute_from_hive": False,
        }
    if verify_hive_permission_password(supplied_value):
        return {
            "ok": True,
            "reason": "REQUESTED_THIS_SESSION",
            "requested_state": "PROPOSAL_ONLY",
            "can_execute_from_hive": False,
            "message": PASSWORD_GATE_COPY,
        }
    return {
        "ok": False,
        "reason": "PASSWORD_REJECTED",
        "requested_state": "UNCHANGED",
        "can_execute_from_hive": False,
    }


def _enrich_permission(permission: dict[str, Any]) -> dict[str, Any]:
    guarded = bool(permission.get("requires_approval"))
    enriched = dict(permission)
    enriched["locked"] = guarded
    enriched["requires_password"] = guarded
    enriched["unlocked_this_session"] = False
    enriched["requested_this_session"] = False
    enriched["can_execute_from_hive"] = False
    enriched["password_gate_configured"] = is_hive_permission_password_configured() if guarded else False
    if guarded and not enriched["password_gate_configured"]:
        enriched["gate_status"] = "LOCKED / PASSWORD GATE NOT CONFIGURED"
    elif guarded:
        enriched["gate_status"] = "LOCKED / PASSWORD REQUIRED"
    else:
        enriched["gate_status"] = "READ-ONLY DEFAULT"
    return enriched


def build_colony_hive_snapshot(root: str | Path) -> dict[str, Any]:
    app_root = _root_path(root)
    cells = [_enrich_cell(app_root, cell) for cell in COLONY_HIVE_CELLS]
    grouped = _group_cells(cells)
    local_signals = build_local_hive_signal_snapshot(app_root)
    queen_links = build_queen_research_links_snapshot(app_root)
    communication_queen = build_communication_queen_snapshot(app_root)
    return {
        "title": "Engel Colony Hive",
        "status": "LOCAL_VISUAL_HIVE / READ_ONLY_FIRST / PROPOSAL_CANDIDATES_ONLY",
        "generated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "root": str(app_root),
        "cell_count": len(cells),
        "desk_count": len(cells),
        "artwork_path": str((app_root / "Engel art work.png").resolve()),
        "icon_path": str((app_root / "assets" / "branding" / "engel_colony_hive_icon.ico").resolve()),
        "mind_summary": {
            "identity": "One cooperative Engel Mind",
            "companion_identity": "one cooperative local companion identity",
            "posture": "Local-only, Guardian-gated, proposal-first",
            "safe_mode": "ON",
            "brain_provider_state": "No provider call from Colony Hive",
            "guardian_posture": "Guardian Layer watching blocked capabilities",
        },
        "hive_map_lanes": HIVE_MAP_LANES,
        "super_swarm_hive_live": local_signals,
        "queen_research_links": queen_links,
        "communication_queen": communication_queen,
        "cells": cells,
        "desks": cells,
        "grouped_cells": grouped,
        "queens": grouped.get("queen", []),
        "workers": grouped.get("worker", []),
        "memory_nests": grouped.get("nest", []),
        "guardian_cards": grouped.get("guardian", []),
        "proposal_lanes": grouped.get("proposal", []),
        "role_titles": ROLE_TITLES,
        "safety": SAFETY_LINES,
        "safety_tokens": SAFETY_TOKENS,
        "permissions_title": "Engel Permissions",
        "permissions_panel": "Hive Safety Permissions",
        "permissions_guard_text": PERMISSION_GUARD_TEXT,
        "password_gate_copy": PASSWORD_GATE_COPY,
        "password_gate_configured": is_hive_permission_password_configured(),
        "permissions": [_enrich_permission(permission) for permission in HIVE_PERMISSION_GATES],
        "mycelium_signals": [
            {
                "from": "memory colonies",
                "to": "proposal candidates",
                "signal_type": "context markers",
                "runtime": "read-only display",
            },
            {
                "from": "proposal candidates",
                "to": "Guardian Layer",
                "signal_type": "warning and confidence markers",
                "runtime": "read-only display",
            },
            {
                "from": "verifiers",
                "to": "Colony Heart",
                "signal_type": "status posture",
                "runtime": "read-only display",
            },
            {
                "from": "route status",
                "to": "Guardian Layer",
                "signal_type": "route warning markers",
                "runtime": "read-only display",
            },
            {
                "from": "candidate lessons",
                "to": "Proposal Growth Lane",
                "signal_type": "candidate routing markers",
                "runtime": "read-only display",
            },
            {
                "from": "safety contracts",
                "to": "Engel Permissions",
                "signal_type": "blocked capability markers",
                "runtime": "read-only display",
            },
        ],
        "guardian_layer": {
            "visible": True,
            "monitors": [
                "provider/network status",
                "autonomy posture",
                "untrusted candidate content",
                "verifier state",
                "proposal-only boundaries",
            ],
            "blocks": [
                "trusted-memory writes",
                "source edits",
                "route mutations",
                "queue mutations",
                "applied learning",
                "provider/network activation",
                "background services",
                "autonomous loops",
            ],
        },
        "structural_analogy": (
            "Hive, colony, queen, worker, trail, and mycelium wording is a local software "
            "structure metaphor only. Engel remains one local software companion."
        ),
    }


def build_research_office_snapshot(root: str | Path) -> dict[str, Any]:
    return build_colony_hive_snapshot(root)


def _cell_lines(cell: dict[str, Any]) -> list[str]:
    return [
        "- " + cell["actor"] + " [" + ROLE_TITLES.get(cell["role"], cell["role"]) + "]",
        "  role: " + cell["role"],
        "  colony_id: " + cell["colony_id"],
        "  nest_name: " + cell["nest_name"],
        "  current_task: " + cell["current_task"],
        "  command: " + cell["command"],
        "  trail: " + cell["linked_local_artifact"],
        "  signal_type: " + cell["signal_type"],
        "  confidence_marker: " + cell["confidence_marker"],
        "  safety_state: " + cell["safety_state"],
        "  proposal_only: " + str(bool(cell["proposal_only"])),
        "  status: " + cell["status"],
        "  kind: " + cell["kind"],
        "  last_updated: " + cell["last_updated"],
    ]


def _permission_lines(permission: dict[str, Any]) -> list[str]:
    return [
        "- " + permission["name"] + ": " + permission["status_badge"],
        "  gate_status: " + permission.get("gate_status", "UNKNOWN"),
        "  label: " + permission["label"],
        "  default_state: " + permission["default_state"],
        "  current_state: " + permission["current_state"],
        "  safety_mode: " + permission["safety_mode"],
        "  locked: " + str(bool(permission.get("locked"))),
        "  password_required: " + str(bool(permission.get("requires_password"))),
        "  requested_this_session: " + str(bool(permission.get("requested_this_session"))),
        "  unlocked_this_session: " + str(bool(permission.get("unlocked_this_session"))),
        "  requires_approval: " + str(bool(permission["requires_approval"])),
        "  can_execute_from_hive: NO",
        "  meaning: " + permission["description"],
    ]


def _queen_link_lines(link: dict[str, Any]) -> list[str]:
    summary = link.get("summary_counts", {})
    return [
        "- " + str(link.get("queen_label", "Queen")),
        "  role: " + str(link.get("role", "")),
        "  linked_folder: " + (str(link.get("linked_folder", "")) or "none"),
        "  folder_status: " + str(link.get("folder_status", "UNKNOWN")),
        "  safety_state: " + str(link.get("safety_state", "UNKNOWN")),
        "  assigned_worker_groups: " + ", ".join(link.get("assigned_worker_groups", [])),
        "  handoff_status: " + str(link.get("handoff_status", "NOT_SENT")),
        "  last_refresh_time: " + str(link.get("last_refresh_time", "not refreshed")),
        "  session_only: " + str(bool(link.get("session_only", True))),
        "  proposal_only: " + str(bool(link.get("proposal_only", True))),
        "  summary_file_count: " + str(summary.get("file_count", 0)),
        "  markdown_count: " + str(summary.get("markdown_count", 0)),
        "  json_count: " + str(summary.get("json_count", 0)),
        "  python_count: " + str(summary.get("python_count", 0)),
        "  report_count: " + str(summary.get("report_count", 0)),
        "  proposal_count: " + str(summary.get("proposal_count", 0)),
        "  verifier_count: " + str(summary.get("verifier_count", 0)),
        "  warning_count: " + str(summary.get("warning_count", 0)),
        "  bounded_scan_note: " + str(summary.get("bounded_scan_note", "")),
    ]


def render_colony_hive_queen_links(root: str | Path) -> str:
    snapshot = build_queen_research_links_snapshot(root)
    lines = [
        "# Engel Colony Hive Queen Research Links",
        "",
        "Mode: " + snapshot["mode"],
        "Time: " + snapshot["generated_at"],
        "",
        "This CLI view is status-only. GUI Queen links are session-local and are not persisted here.",
        "",
        "Safety:",
        *["- " + item for item in snapshot["safety"]],
        "",
        "Safe folder scopes:",
        *["- " + item for item in snapshot["safe_scopes"]],
        "",
        "Queens:",
    ]
    for link in snapshot["queen_links"]:
        lines.extend(_queen_link_lines(link))
    return "\n".join(lines)


def _enabled_label(value: bool) -> str:
    return "ENABLED" if value else "DISABLED"


def render_communication_queen_status(root: str | Path) -> str:
    snapshot = build_communication_queen_snapshot(root)
    status = snapshot["status"]
    routes = snapshot["future_routes"]
    candidates = snapshot["remote_queen_candidates"]
    flag_rows = [
        ("Trusted WiFi", "runtime_wifi_enabled"),
        ("Remote Queen network", "runtime_remote_queen_network_enabled"),
        ("Device pairing", "device_pairing_enabled"),
        ("Background service", "background_service_enabled"),
        ("Autonomous remote work", "autonomous_remote_work_enabled"),
        ("Remote file transfer", "remote_file_transfer_enabled"),
        ("Trusted-memory write", "trusted_memory_write_enabled"),
        ("Queue mutation", "queue_mutation_enabled"),
        ("Source edit", "source_edit_enabled"),
        ("Applied learning", "applied_learning_enabled"),
        ("Provider/network", "provider_network_enabled"),
    ]
    lines = [
        "# Communication Queen / Remote Queens",
        "",
        "Communication Queen: SCAFFOLD ONLY / READ_ONLY_STATUS",
        "Mode: " + snapshot["mode"],
        "Time: " + snapshot["generated_at"],
        "",
        "Purpose:",
        "- Future trusted-WiFi coordinator for Remote Queens and small project hives.",
        "- This CLI view is read-only status only.",
        "- No WiFi/device runtime is enabled here.",
        "",
        "Runtime/device capability status:",
    ]
    for label, key in flag_rows:
        lines.append("- " + label + ": " + _enabled_label(bool(status.get(key, False))))
    lines.extend(
        [
            "",
            "Remote Queen records:",
            "- untrusted/session-local/scaffold-only",
            "- placeholder candidates only",
            "- no device discovery has run",
            "- no remote device is connected",
            "- no remote task can be assigned",
            "- outputs remain untrusted until reviewed, scanned, verified, and human-approved",
            "",
            "Remote Queen candidates:",
        ]
    )
    for candidate in candidates:
        allowed = "; ".join(str(item) for item in candidate.get("allowed_future_work", []))
        forbidden = "; ".join(str(item) for item in candidate.get("forbidden_actions", []))
        lines.extend(
            [
                "- " + str(candidate.get("display_name", "Remote Queen")),
                "  role: " + str(candidate.get("role", "")),
                "  trust_state: untrusted/session-local/scaffold-only",
                "  candidate_trust_label: " + str(candidate.get("trust_state", "Placeholder only")),
                "  connection_state: " + str(candidate.get("connection_state", "")),
                "  allowed_future_work: " + allowed,
                "  forbidden_actions: " + forbidden,
                "  assignment_state: " + str(candidate.get("assignment_state", "No remote task can be assigned.")),
            ]
        )
    lines.extend(
        [
            "",
            "Future route preview:",
        ]
    )
    for route in routes:
        lines.append(
            "- "
            + str(route.get("route", ""))
            + ": implemented_now="
            + str(bool(route.get("implemented_now", True)))
            + " | should_execute_in_test="
            + str(bool(route.get("should_execute_in_test", True)))
            + " | "
            + str(route.get("status", "Future / not implemented"))
        )
    lines.extend(
        [
            "",
            "Safety:",
            *["- " + item for item in snapshot["safety"]],
            "- No device communication runtime, remote execution, background worker, autonomous loop, provider/API/network call, trusted-memory write, queue mutation, source edit, applied learning, or persistent pairing is enabled.",
            "",
            "Next safe step:",
            "- Bundled GUI smoke, then trusted-device protocol design.",
        ]
    )
    return "\n".join(lines)


def render_colony_hive_permissions(root: str | Path) -> str:
    snapshot = build_colony_hive_snapshot(root)
    live = snapshot["super_swarm_hive_live"]
    lines = [
        "# Engel Permissions",
        "",
        "Panel: Hive Safety Permissions",
        "Status: LOCAL_ONLY / INDICATOR_ONLY / NO_RUNTIME_POWER",
        "",
        snapshot["permissions_guard_text"],
        snapshot["password_gate_copy"],
        "",
    ]
    for permission in snapshot["permissions"]:
        lines.extend(_permission_lines(permission))
    lines.extend(
        [
            "",
            "Super Swarm Hive Live:",
            "- State: OFF by default unless toggled ON inside the visible GUI session.",
            "- Meaning: " + live["mode_meaning"],
            "- Can execute from Hive: NO",
            "- Password gate status: existing dangerous permission gates remain unchanged.",
        ]
    )
    return "\n".join(lines)


def render_colony_hive_status(root: str | Path) -> str:
    snapshot = build_colony_hive_snapshot(root)
    live = snapshot["super_swarm_hive_live"]
    queen_links = snapshot["queen_research_links"]
    lines = [
        "# Engel Colony Hive Status",
        "",
        "Status: " + snapshot["status"],
        "Time: " + snapshot["generated_at"],
        "",
        "Purpose:",
        "- Engel Mind: one cooperative local companion identity.",
        "- Show a local hive chamber / colony map for Engel's memory colonies and proposal-stage work.",
        "- Keep queens, workers, nests, mycelium signals, and Guardian Layer as visual/status structure.",
        "- Keep the metaphor structural only: Engel remains one local software companion.",
        "",
        "Engel Mind / Colony Heart:",
        "- identity: " + snapshot["mind_summary"]["identity"],
        "- posture: " + snapshot["mind_summary"]["posture"],
        "- local_only: True",
        "- safe_mode: " + snapshot["mind_summary"]["safe_mode"],
        "- brain_provider_state: " + snapshot["mind_summary"]["brain_provider_state"],
        "- guardian_posture: " + snapshot["mind_summary"]["guardian_posture"],
        "",
        "Super Swarm Hive Live:",
        "- state: OFF by default unless a visible GUI session toggles it ON",
        "- live mode means visual animation + bounded local read-only signal refresh only",
        "- meaning: " + live["mode_meaning"],
        "- local_refresh: bounded read-only metadata/signal snapshot",
        "- last_local_refresh_time: " + live["last_local_refresh_time"],
        "- files_inspected: " + str(live["files_inspected"]) + " / " + str(live["max_files"]),
        "- total_signal_strength: " + str(live["total_signal_strength"]),
        "- proposal_candidate_count: " + str(live["proposal_candidate_count"]),
        "- verifier_signal_count: " + str(live["verifier_signal_count"]),
        "- guardian_warning_count: " + str(live["guardian_warning_count"]),
        "- No runtime power granted.",
        "- no background service",
        "- no autonomous loop",
        "- no mutation",
        "- no provider/network/browsing",
        "",
        "Queen Research Links:",
        "- Queen research folder links are session-only.",
        "- Queen-to-worker handoffs are visual/read-only context.",
        "- Workers do not start background jobs.",
        "- No mutation or provider/network behavior.",
        "- link_count: " + str(len(queen_links["queen_links"])),
        "",
        "Colony Heart:",
    ]
    for cell in snapshot["grouped_cells"].get("heart", []):
        lines.extend(_cell_lines(cell))

    lines.extend(["", "Queens / Coordinators:"])
    for cell in snapshot["grouped_cells"].get("queen", []):
        lines.extend(_cell_lines(cell))

    lines.extend(["", "Colony Workers:"])
    for cell in snapshot["grouped_cells"].get("worker", []):
        lines.extend(_cell_lines(cell))

    lines.extend(["", "Memory Colonies / Local Nests:"])
    lines.append("- chat memories, thought seeds, research reports, approved lessons, swarm trails, project history, route status, verifier results, proposal candidates, safety contracts")
    for signal in live["memory_colony_signals"]:
        lines.append(
            "- "
            + signal["label"]
            + ": count="
            + str(signal["count"])
            + " | growth_level="
            + str(signal["growth_level"])
            + " | "
            + signal["signal_type"]
            + " | "
            + signal["safety_state"]
        )
    for cell in snapshot["grouped_cells"].get("nest", []):
        lines.extend(_cell_lines(cell))

    lines.extend(["", "Guardian Layer:"])
    for cell in snapshot["grouped_cells"].get("guardian", []):
        lines.extend(_cell_lines(cell))
    lines.extend(["  blocks: " + ", ".join(snapshot["guardian_layer"]["blocks"])])

    lines.extend(["", "Mycelium Layer Signals:"])
    for signal in snapshot["mycelium_signals"]:
        lines.append(
            "- "
            + signal["from"]
            + " -> "
            + signal["to"]
            + " | "
            + signal["signal_type"]
            + " | "
            + signal["runtime"]
        )

    lines.extend(["", "Proposal Growth Lane:"])
    for cell in snapshot["grouped_cells"].get("proposal", []):
        lines.extend(_cell_lines(cell))

    lines.extend(
        [
            "",
            "Engel Permissions:",
            "- " + snapshot["permissions_guard_text"],
        ]
    )
    for permission in snapshot["permissions"]:
        lines.append(
            "- "
            + permission["name"]
            + ": "
            + permission["status_badge"]
            + " | "
            + permission.get("gate_status", "UNKNOWN")
            + " | REQUESTED THIS SESSION: "
            + str(bool(permission.get("requested_this_session")))
            + " | CAN EXECUTE FROM HIVE: NO"
        )

    lines.extend(
        [
            "",
            "Safety:",
            *["- " + item for item in snapshot["safety"]],
            "",
            "Tokens:",
            *["- " + item for item in snapshot["safety_tokens"]],
        ]
    )
    return "\n".join(lines)


def render_colony_hive_snapshot(root: str | Path) -> str:
    snapshot = build_colony_hive_snapshot(root)
    live = snapshot["super_swarm_hive_live"]
    lines = [
        "# Engel Colony Hive Snapshot",
        "",
        "Status: " + snapshot["status"],
        "Time: " + snapshot["generated_at"],
        "Root: " + snapshot["root"],
        "Cell count: " + str(snapshot["cell_count"]),
        "",
        "Structural analogy:",
        "- " + snapshot["structural_analogy"],
        "",
        "## Engel Mind / Colony Heart",
        "- " + snapshot["mind_summary"]["identity"],
        "- " + snapshot["mind_summary"]["companion_identity"],
        "- Posture: " + snapshot["mind_summary"]["posture"],
        "- Safe mode: " + snapshot["mind_summary"]["safe_mode"],
        "- Brain provider state: " + snapshot["mind_summary"]["brain_provider_state"],
        "- Guardian posture: " + snapshot["mind_summary"]["guardian_posture"],
        "",
        "## Super Swarm Hive Live",
        "- State: OFF by default unless a visible GUI session toggles it ON",
        "- " + live["ui_copy"],
        "- Meaning: " + live["mode_meaning"],
        "- Last local refresh: " + live["last_local_refresh_time"],
        "- Files inspected: " + str(live["files_inspected"]) + " / " + str(live["max_files"]),
        "- Total signal strength: " + str(live["total_signal_strength"]),
        "- Guardian warning count: " + str(live["guardian_warning_count"]),
        "- Proposal candidate count: " + str(live["proposal_candidate_count"]),
        "- Verifier signal count: " + str(live["verifier_signal_count"]),
        "- No runtime power granted.",
        "",
        "## Queen Research Links",
        "- Queen research folder links are session-only.",
        "- Queen-to-worker handoffs are visual/read-only context.",
        "- Workers do not start background jobs.",
        "- No mutation or provider/network behavior.",
        "",
    ]
    for role in ROLE_ORDER:
        cells = snapshot["grouped_cells"].get(role, [])
        if not cells:
            continue
        lines.append("## " + ROLE_TITLES.get(role, role))
        for cell in cells:
            lines.extend(_cell_lines(cell))
            lines.append("  preview: " + cell["preview"])
        lines.append("")

    lines.extend(
        [
            "## Guardian Layer Safety Membrane",
            "- Monitors: " + ", ".join(snapshot["guardian_layer"]["monitors"]),
            "- Blocks: " + ", ".join(snapshot["guardian_layer"]["blocks"]),
            "",
            "## Mycelium Layer Read-only Signals",
        ]
    )
    for signal in snapshot["mycelium_signals"]:
        lines.append(
            "- "
            + signal["from"]
            + " -> "
            + signal["to"]
            + " | "
            + signal["signal_type"]
            + " | "
            + signal["runtime"]
        )

    lines.extend(
        [
            "",
            "## Engel Permissions",
            "- Panel: Hive Safety Permissions",
            "- " + snapshot["permissions_guard_text"],
            "- " + snapshot["password_gate_copy"],
        ]
    )
    for permission in snapshot["permissions"]:
        lines.extend(_permission_lines(permission))

    lines.extend(
        [
            "",
            "## Safety",
            *["- " + item for item in snapshot["safety"]],
            "",
            "## Tokens",
            *["- " + item for item in snapshot["safety_tokens"]],
        ]
    )
    return "\n".join(lines).rstrip()


def render_colony_hive_map(root: str | Path) -> str:
    snapshot = build_colony_hive_snapshot(root)
    mind = snapshot["mind_summary"]
    live = snapshot["super_swarm_hive_live"]
    lines = [
        "# Engel Colony Hive Map",
        "",
        "Mode: READ_ONLY_LOCAL_HIVE_MAP",
        "Status: " + snapshot["status"],
        "Time: " + snapshot["generated_at"],
        "",
        "Engel Mind:",
        "- " + mind["identity"],
        "- " + mind["companion_identity"],
        "- posture: " + mind["posture"],
        "- brain_provider_state: " + mind["brain_provider_state"],
        "- guardian_posture: " + mind["guardian_posture"],
        "",
        "Super Swarm Hive Live:",
        "- state: OFF by default unless toggled ON inside the visible GUI session",
        "- live mode means visual animation + bounded local read-only signal refresh only",
        "- No runtime power granted.",
        "- total_signal_strength: " + str(live["total_signal_strength"]),
        "- proposal_candidate_count: " + str(live["proposal_candidate_count"]),
        "- verifier_signal_count: " + str(live["verifier_signal_count"]),
        "- guardian_warning_count: " + str(live["guardian_warning_count"]),
        "",
        "Queen Research Links:",
        "- Queen research folder links are session-only.",
        "- Queen-to-worker handoffs are visual/read-only context.",
        "- Workers do not start background jobs.",
        "- No mutation or provider/network behavior.",
        "",
        "Read-only map:",
        "                  [1] QUEENS",
        "                       Coordination / prioritization / proposal only",
        "                         |      |      |",
        "[2] COLONY WORKERS ---- ONE COOPERATIVE ENGEL MIND ---- [3] MEMORY COLONIES / NESTS",
        " Observation / organization / mapping / proposal-only        Local memory / project references only",
        "                         |      |      |",
        "                  [5] GUARDIAN LAYER",
        "                       Safety membrane / blocked unsafe runtime power",
        "            [4] MYCELIUM SIGNAL PATHS ---- [6] VERIFIER POSTURE ---- [7] PROPOSAL GROWTH LANE",
        "                 Read-only-first               Observe / verify / no execution       Untrusted candidates",
        "",
        "Hive lanes:",
    ]
    for lane in snapshot["hive_map_lanes"]:
        count = len(snapshot["grouped_cells"].get(lane["role"], []))
        lines.append(
            "- "
            + lane["number"]
            + " "
            + lane["title"]
            + ": "
            + lane["summary"]
            + " | "
            + lane["badge"]
            + " | cards="
            + str(count)
        )

    lines.extend(["", "Queens: coordination/prioritization/proposal only"])
    for cell in snapshot["queens"]:
        lines.append("- " + cell["actor"] + " -> " + cell["current_task"])

    lines.extend(["", "Workers: observation/organization/mapping/proposal only"])
    for cell in snapshot["workers"]:
        lines.append("- " + cell["actor"] + " -> " + cell["nest_name"] + " | " + cell["safety_state"])

    lines.extend(
        [
            "",
            "Memory colonies:",
            "- Chat memories",
            "- Thought seeds",
            "- Research reports",
            "- Approved lessons",
            "- Swarm trails",
            "- Project history",
            "- Route status",
            "- Verifier results",
            "- Proposal candidates",
            "- Safety contracts",
        ]
    )
    lines.extend(["", "Nest growth signals:"])
    for signal in live["memory_colony_signals"]:
        lines.append(
            "- "
            + signal["label"]
            + ": count="
            + str(signal["count"])
            + " | growth="
            + str(signal["growth_level"])
            + " | "
            + signal["signal_type"]
        )

    lines.extend(["", "Mycelium: read-only-first signal network"])
    for signal in snapshot["mycelium_signals"]:
        lines.append("- " + signal["from"] + " -> " + signal["to"] + " | " + signal["signal_type"])

    lines.extend(
        [
            "",
            "Guardian: safety membrane",
            "- blocks: " + ", ".join(snapshot["guardian_layer"]["blocks"]),
            "",
            "Permissions: password-gated proposal-only dangerous toggles",
        ]
    )
    for permission in snapshot["permissions"]:
        lines.append(
            "- "
            + permission["name"]
            + ": "
            + permission["status_badge"]
            + " | "
            + permission.get("gate_status", "UNKNOWN")
            + " | can_execute_from_hive=NO"
        )

    lines.extend(
        [
            "",
            "Safety: no runtime power granted",
            *["- " + item for item in snapshot["safety"]],
        ]
    )
    return "\n".join(lines).rstrip()


def render_research_office_status(root: str | Path) -> str:
    return render_colony_hive_status(root)


def render_research_office_snapshot(root: str | Path) -> str:
    return render_colony_hive_snapshot(root)


def render_research_office_map(root: str | Path) -> str:
    return render_colony_hive_map(root)


def render_research_office_queen_links(root: str | Path) -> str:
    return render_colony_hive_queen_links(root)


def render_research_office_permissions(root: str | Path) -> str:
    return render_colony_hive_permissions(root)
