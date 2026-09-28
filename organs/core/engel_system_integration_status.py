from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
CORE_MAP_JSON = ROOT / "memory" / "ENGEL_CORE_CONTINUITY_MAP_V1.json"

STATUS_LABELS = [
    "SYSTEM_INTEGRATION_RECONCILIATION",
    "CONTINUITY_RECONCILIATION",
    "COMPLEXITY_REDUCTION_PASS",
    "STATUS_SURFACES_CONNECTED",
    "CORE_CONTINUITY_COVERAGE_CHECKED",
    "GUI_STATUS_COVERAGE_CHECKED",
    "VERIFIER_COVERAGE_CHECKED",
    "PROTECTED_ACTIONS_ALIGNED",
    "PASSWORD_GATE_ALIGNMENT_CHECKED",
    "CODE_COMPANION_ALIGNMENT_CHECKED",
    "AI_GROWTH_ALIGNMENT_CHECKED",
    "BACKGROUND_WORKER_ALIGNMENT_CHECKED",
    "RESEARCH_TOGGLE_ALIGNMENT_CHECKED",
    "TRUTHFULNESS_GUARD_ALIGNMENT_CHECKED",
    "NO_NEW_RUNTIME_BEHAVIOR",
    "NO_PROVIDER_CALLS",
    "NO_NETWORK",
    "NO_BROWSER",
    "NO_MODEL_RUNTIME",
    "NO_TRUSTED_MEMORY_WRITE",
    "NO_SOURCE_MUTATION_BEYOND_REFACTOR",
    "NO_PACKAGE_REFRESH",
    "NO_BACKGROUND_WORKER_STARTED",
    "NO_STARTUP_AUTORUN_ENABLED",
]

DISPLAY_LABELS = [
    "CONNECTED",
    "AVAILABLE",
    "MISSING_OPTIONAL",
    "MISSING_REQUIRED",
    "NEEDS_CORE_CONTINUITY_LINK",
    "NEEDS_GUI_LINK",
    "NEEDS_VERIFIER_LINK",
    "READ_ONLY_STATUS",
    "SAFE_TO_VIEW",
    "ACTION_REQUIRES_PASSWORD",
    "ACTION_REQUIRES_CONTRACT",
    "ACTION_REQUIRES_VERIFIER",
]

SECTION_ORDER = [
    "AI Growth systems",
    "Self-Learning systems",
    "Daily Cycle systems",
    "Candidate Review systems",
    "Memory Promotion systems",
    "Research-to-Fix systems",
    "Code Companion systems",
    "Code Companion Patch systems",
    "Global Password / Protected Actions",
    "Background Worker / Startup",
    "Research Toggle Worker",
    "Remote Worker / Mobile",
    "Truthfulness Guard",
    "Core Continuity",
    "GUI Status Surfaces",
    "Verifier Coverage",
    "Runtime / Environment Dependencies",
    "Model Library / Offline Model Readiness",
    "Manual Downloads",
    "Manual Downloads / Non-Model Materials",
    "Optional Local Tooling Environment",
    "Approved Library / Intake",
    "Safety Boundaries",
    "Package Visibility Records",
    "Active Build Plan",
    "Missing or Optional Systems",
    "Next Safe Integration Steps",
]

SYSTEMS = [
    {
        "section": "AI Growth systems",
        "system_id": "ai_growth_dashboard",
        "display_name": "Engel AI Growth Dashboard",
        "primary_files": ["engel_ai_growth_dashboard.py"],
        "verifier_files": ["tools\\verify_engel_ai_growth_dashboard.py"],
        "reports": ["reports\\codex_bridge\\ENGEL_AI_GROWTH_DASHBOARD_V1.md"],
        "core_continuity_node_expected": "packaged_engel_ai_growth_visibility_v1",
        "gui_surface_expected": "AI Growth",
        "safety_boundary": "READ_ONLY_STATUS / SAFE_TO_VIEW / NO_ACTION_EXECUTION",
    },
    {
        "section": "Self-Learning systems",
        "system_id": "self_learning_mini_runner",
        "display_name": "Self-Learning Mini Runner",
        "primary_files": ["engel_self_learning_mini_runner.py", "engel_self_learning_status_surface.py"],
        "verifier_files": ["tools\\verify_engel_self_learning_mini_runner.py", "tools\\verify_engel_self_learning_status_surface.py"],
        "reports": ["reports\\codex_bridge\\ENGEL_SELF_LEARNING_MINI_RUNNER_V1.md", "reports\\codex_bridge\\ENGEL_SELF_LEARNING_STATUS_SURFACE_V1.md"],
        "core_continuity_node_expected": "engel_self_learning_mini_runner_v1",
        "gui_surface_expected": "Self-Learning",
        "safety_boundary": "CANDIDATE_ONLY / READ_ONLY_STATUS / writes only through existing explicit runner modes",
    },
    {
        "section": "Self-Learning systems",
        "system_id": "bounded_self_learning_scheduler",
        "display_name": "Bounded Self-Learning Scheduler",
        "primary_files": ["engel_bounded_self_learning_scheduler.py"],
        "verifier_files": ["tools\\verify_engel_bounded_self_learning_scheduler.py"],
        "reports": ["reports\\codex_bridge\\ENGEL_BOUNDED_SELF_LEARNING_SCHEDULER_V1.md"],
        "core_continuity_node_expected": "engel_bounded_self_learning_scheduler_v1",
        "gui_surface_expected": "Self-Learning",
        "safety_boundary": "bounded foreground scheduler / no startup autorun / no hidden background loop",
    },
    {
        "section": "Self-Learning systems",
        "system_id": "learning_job_queue",
        "display_name": "Engel Learning Job Queue V1",
        "primary_files": [
            "engel_learning_job_queue.py",
            "memory\\ENGEL_LEARNING_JOB_QUEUE_CONTRACT_V1.json",
            "memory\\ENGEL_LEARNING_JOB_QUEUE_CONTRACT_V1.md",
        ],
        "verifier_files": ["tools\\verify_engel_learning_job_queue.py"],
        "reports": ["reports\\codex_bridge\\ENGEL_LEARNING_JOB_QUEUE_V1.md"],
        "core_continuity_node_expected": "engel_learning_job_queue_v1",
        "gui_surface_expected": "System Integration",
        "queue_folder": "reports\\learning_job_queue\\",
        "receipt_folder": "reports\\learning_job_queue_receipts\\",
        "current_state": "Learning Job Queue V1 available; draft/queued counts are visible through python engel_learning_job_queue.py --status; real source required; no fake queue records; next step: Self-Learning Run Controller V1",
        "safety_boundary": "LEARNING_JOB_QUEUE / CANDIDATE_LEARNING_ONLY / EXPLICIT_JOBS_ONLY / APPROVED_LOCAL_SOURCES_ONLY / REAL_SOURCE_REQUIRED / SOURCE_FILE_MUST_EXIST / NO_FAKE_QUEUE_RECORDS / NO_FAKE_APPROVALS / UNTRUSTED_OUTPUTS_ONLY / NOT_TRUSTED_MEMORY / PASSWORD_GATE_REQUIRED_FOR_WRITE_RUN / RECEIPTS_REQUIRED / no learning jobs run by queue / no trusted-memory write / no source mutation / no patch apply / no provider/network/browser/model runtime / no WSL/Hermes/Android runtime",
    },
    {
        "section": "Self-Learning systems",
        "system_id": "self_learning_run_controller",
        "display_name": "Engel Self-Learning Run Controller V1",
        "primary_files": [
            "engel_self_learning_run_controller.py",
            "memory\\ENGEL_SELF_LEARNING_RUN_CONTROLLER_CONTRACT_V1.json",
            "memory\\ENGEL_SELF_LEARNING_RUN_CONTROLLER_CONTRACT_V1.md",
        ],
        "verifier_files": ["tools\\verify_engel_self_learning_run_controller.py"],
        "reports": ["reports\\codex_bridge\\ENGEL_SELF_LEARNING_RUN_CONTROLLER_V1.md"],
        "core_continuity_node_expected": "engel_self_learning_run_controller_v1",
        "gui_surface_expected": "System Integration",
        "receipt_folder": "reports\\self_learning_run_receipts\\",
        "summary_folder": "reports\\self_learning_run_summaries\\",
        "current_state": "Self-Learning Run Controller V1 available; one explicit queue job per run; real source required; outputs remain untrusted/candidate-only; next step: Fix Candidate Queue V1",
        "safety_boundary": "SELF_LEARNING_RUN_CONTROLLER / BOUNDED_LEARNING_RUNNER / REAL_QUEUE_JOBS_ONLY / REAL_SOURCE_REQUIRED / CANDIDATE_LEARNING_ONLY / UNTRUSTED_OUTPUTS_ONLY / NOT_TRUSTED_MEMORY / PASSWORD_GATE_REQUIRED_FOR_RUN / RECEIPTS_REQUIRED / HUMAN_REVIEW_REQUIRED / no trusted-memory write / no source mutation / no patch apply / no model loading / no inference / no training / no WSL/Hermes/Android runtime / no provider/network/browser / no background worker / no startup autorun",
    },
    {
        "section": "Self-Learning systems",
        "system_id": "candidate_learning_output_review",
        "display_name": "Engel Candidate Learning Output Review V1",
        "primary_files": [
            "engel_candidate_learning_output_review.py",
            "memory\\ENGEL_CANDIDATE_LEARNING_OUTPUT_REVIEW_CONTRACT_V1.json",
            "memory\\ENGEL_CANDIDATE_LEARNING_OUTPUT_REVIEW_CONTRACT_V1.md",
        ],
        "verifier_files": ["tools\\verify_engel_candidate_learning_output_review.py"],
        "reports": ["reports\\codex_bridge\\ENGEL_CANDIDATE_LEARNING_OUTPUT_REVIEW_V1.md"],
        "core_continuity_node_expected": "engel_candidate_learning_output_review_v1",
        "gui_surface_expected": "System Integration",
        "current_state": "Candidate Learning Output Review V1 available; read-only review window for self-learning receipts, summaries, research notes, lesson candidates, memory candidate proposals, learning queue records, and failed/rejected candidate outputs; honest empty state when no real outputs exist",
        "safety_boundary": "CANDIDATE_LEARNING_OUTPUT_REVIEW / READ_ONLY_REVIEW_LAYER / EXISTING_OUTPUTS_ONLY / HONEST_EMPTY_STATE / UNTRUSTED_OUTPUTS_ONLY / NOT_TRUSTED_MEMORY / HUMAN_REVIEW_REQUIRED / NO_APPROVAL / NO_PROMOTION / NO_APPLY / NO_RUN_JOBS / no trusted-memory write / no source mutation / no route mutation / no model loading / no inference / no training / no WSL/Hermes/Android runtime / no provider/network/browser / no background worker / no startup autorun / no fake approvals",
    },
    {
        "section": "Daily Cycle systems",
        "system_id": "daily_cycle",
        "display_name": "Daily Cycle Runner and Status Surface",
        "primary_files": ["engel_daily_cycle_runner.py", "engel_daily_cycle_status_surface.py"],
        "verifier_files": ["tools\\verify_engel_daily_cycle_runner.py", "tools\\verify_engel_daily_cycle_status_surface.py"],
        "reports": ["reports\\codex_bridge\\ENGEL_DAILY_CYCLE_RUNNER_V1.md", "reports\\codex_bridge\\ENGEL_DAILY_CYCLE_STATUS_SURFACE_V1.md"],
        "core_continuity_node_expected": "engel_system_integration_continuity_reconciliation_v1",
        "gui_surface_expected": "AI Growth",
        "safety_boundary": "dry-run/status visibility / protected run actions require password and contract gates",
    },
    {
        "section": "Candidate Review systems",
        "system_id": "candidate_review_dashboard",
        "display_name": "Candidate Review Dashboard",
        "primary_files": ["engel_candidate_review_dashboard.py"],
        "verifier_files": ["tools\\verify_engel_candidate_review_dashboard.py"],
        "reports": ["reports\\codex_bridge\\ENGEL_CANDIDATE_REVIEW_DASHBOARD_V1.md"],
        "core_continuity_node_expected": "engel_candidate_review_dashboard_v1",
        "gui_surface_expected": "Candidate Review",
        "safety_boundary": "READ_ONLY_STATUS / candidates remain untrusted until separate review",
    },
    {
        "section": "Candidate Review systems",
        "system_id": "fix_candidate_queue",
        "display_name": "Engel Fix Candidate Queue V1",
        "primary_files": [
            "engel_fix_candidate_queue.py",
            "memory\\ENGEL_FIX_CANDIDATE_QUEUE_CONTRACT_V1.json",
            "memory\\ENGEL_FIX_CANDIDATE_QUEUE_CONTRACT_V1.md",
        ],
        "verifier_files": ["tools\\verify_engel_fix_candidate_queue.py"],
        "reports": ["reports\\codex_bridge\\ENGEL_FIX_CANDIDATE_QUEUE_V1.md"],
        "core_continuity_node_expected": "engel_fix_candidate_queue_v1",
        "gui_surface_expected": "System Integration",
        "current_state": "Fix Candidate Queue V1 available; stores inert fix candidate records only; next step is future protected Code Companion / bounded patch review flow.",
        "safety_boundary": "FIX_CANDIDATE_QUEUE / INERT_RECORDS_ONLY / NOT_PATCHES / NOT_APPLIED_CHANGES / HUMAN_REVIEW_REQUIRED / VERIFIER_REQUIRED / NO_PATCH_APPLY / NO_SOURCE_MUTATION / NO_ROUTE_MUTATION / NO_TRUSTED_MEMORY_WRITE / NO_PROVIDER_CALLS / NO_NETWORK / NO_BROWSER / NO_MODEL_LOADING / NO_INFERENCE / NO_WSL_EXECUTION / NO_HERMES_EXECUTION",
    },
    {
        "section": "Memory Promotion systems",
        "system_id": "memory_promotion",
        "display_name": "Memory Promotion Contract and Writer",
        "primary_files": ["engel_memory_promotion_writer.py", "memory\\ENGEL_APPROVED_MEMORY_PROMOTION_CONTRACT_V1.md"],
        "verifier_files": ["tools\\verify_engel_memory_promotion_writer.py", "tools\\verify_engel_approved_memory_promotion_contract.py"],
        "reports": ["reports\\codex_bridge\\ENGEL_MEMORY_PROMOTION_WRITER_V1.md", "reports\\codex_bridge\\ENGEL_APPROVED_MEMORY_PROMOTION_CONTRACT_V1.md"],
        "core_continuity_node_expected": "engel_memory_promotion_writer_v1",
        "gui_surface_expected": "Memory Promotion",
        "safety_boundary": "ACTION_REQUIRES_PASSWORD / ACTION_REQUIRES_CONTRACT / ACTION_REQUIRES_VERIFIER",
    },
    {
        "section": "Memory Promotion systems",
        "system_id": "trusted_memory_target_contract",
        "display_name": "Engel Trusted Memory Target Contract V1",
        "primary_files": [
            "engel_trusted_memory_target.py",
            "memory\\ENGEL_TRUSTED_MEMORY_TARGET_CONTRACT_V1.json",
            "memory\\ENGEL_TRUSTED_MEMORY_TARGET_CONTRACT_V1.md",
        ],
        "verifier_files": ["tools\\verify_engel_trusted_memory_target.py"],
        "reports": ["reports\\codex_bridge\\ENGEL_TRUSTED_MEMORY_TARGET_CONTRACT_V1.md"],
        "core_continuity_node_expected": "engel_trusted_memory_target_contract_v1",
        "gui_surface_expected": "System Integration",
        "current_state": "Trusted memory target is explicit as memory\\ENGEL_TRUSTED_MEMORY_V1.jsonl but disabled_until_human_target_approval; Approved Memory Promotion must block while disabled.",
        "safety_boundary": "TRUSTED_MEMORY_TARGET_CONTRACT / TARGET_EXPLICIT / DISABLED_UNTIL_HUMAN_TARGET_APPROVAL / APPEND_ONLY_JSONL / HUMAN_APPROVAL_REQUIRED / PASSWORD_GATE_REQUIRED / RECEIPT_REQUIRED / VERIFIER_REQUIRED / PROMOTION_BLOCKED_WHILE_DISABLED / NO_AUTO_PROMOTION / NO_FAKE_TRUSTED_MEMORY_ENTRIES",
    },
    {
        "section": "Memory Promotion systems",
        "system_id": "approved_memory_promotion",
        "display_name": "Approved Memory Promotion V1",
        "primary_files": [
            "engel_approved_memory_promotion.py",
            "memory\\ENGEL_APPROVED_MEMORY_PROMOTION_CONTRACT_V1.json",
            "memory\\ENGEL_APPROVED_MEMORY_PROMOTION_CONTRACT_V1.md",
        ],
        "verifier_files": ["tools\\verify_engel_approved_memory_promotion.py"],
        "reports": ["reports\\codex_bridge\\ENGEL_APPROVED_MEMORY_PROMOTION_V1.md"],
        "core_continuity_node_expected": "engel_approved_memory_promotion_v1",
        "gui_surface_expected": "Memory Promotion",
        "current_state": "Discovers memory candidates as untrusted proposals and consults Trusted Memory Target Contract V1; promotion remains blocked while the target is disabled or unclear.",
        "safety_boundary": "MEMORY_CANDIDATES_ARE_NOT_MEMORY / HUMAN_APPROVAL_REQUIRED / APPROVAL_TOKEN_REQUIRED / PASSWORD_GATE_REQUIRED / RECEIPTS_REQUIRED / NO_AUTO_PROMOTION / NO_BULK_PROMOTION / NO_SOURCE_MUTATION / NO_ROUTE_MUTATION / NO_MODEL_LOADING / NO_INFERENCE / NO_HERMES_EXECUTION",
    },
    {
        "section": "Research-to-Fix systems",
        "system_id": "research_to_fix_loop",
        "display_name": "Research-to-Fix Loop",
        "primary_files": ["engel_research_to_fix_loop.py"],
        "verifier_files": ["tools\\verify_engel_research_to_fix_loop.py"],
        "reports": ["reports\\codex_bridge\\ENGEL_RESEARCH_TO_FIX_LOOP_V1.md"],
        "core_continuity_node_expected": "engel_research_to_fix_loop_v1",
        "gui_surface_expected": "Research-to-Fix",
        "safety_boundary": "candidate chain only / no verifier update / no patch apply",
    },
    {
        "section": "Code Companion systems",
        "system_id": "code_companion_intelligence_loop",
        "display_name": "Code Companion Intelligence Loop",
        "primary_files": [
            "engel_code_companion_candidate_finder.py",
            "engel_code_companion_patch_candidate.py",
            "engel_code_companion_verifier_plan.py",
            "engel_code_companion_candidate_review_status.py",
        ],
        "verifier_files": [
            "tools\\verify_engel_code_companion_candidate_finder.py",
            "tools\\verify_engel_code_companion_patch_candidate.py",
            "tools\\verify_engel_code_companion_verifier_plan.py",
            "tools\\verify_engel_code_companion_candidate_review_gui.py",
        ],
        "reports": [
            "reports\\codex_bridge\\ENGEL_CODE_COMPANION_INTELLIGENCE_LOOP_V1.md",
            "reports\\codex_bridge\\ENGEL_CODE_COMPANION_CANDIDATE_REVIEW_GUI_V1.md",
        ],
        "core_continuity_node_expected": "engel_code_companion_intelligence_loop_v1",
        "gui_surface_expected": "Code Companion Review",
        "safety_boundary": "candidate/planning/read-only / no source mutation / no patch apply",
    },
    {
        "section": "Code Companion Patch systems",
        "system_id": "code_companion_patch_stack",
        "display_name": "Code Companion Low-Risk Patch Stack",
        "primary_files": [
            "engel_code_companion_low_risk_patch_runner.py",
            "engel_code_companion_patch_receipt_viewer.py",
            "engel_code_companion_patch_status_surface.py",
            "memory\\ENGEL_CODE_COMPANION_LOW_RISK_PATCH_APPLY_CONTRACT_V1.md",
        ],
        "verifier_files": [
            "tools\\verify_engel_code_companion_low_risk_patch_apply_contract.py",
            "tools\\verify_engel_code_companion_low_risk_patch_runner.py",
            "tools\\verify_engel_code_companion_patch_receipt_viewer.py",
            "tools\\verify_engel_code_companion_patch_status_surface.py",
        ],
        "reports": [
            "reports\\codex_bridge\\ENGEL_CODE_COMPANION_LOW_RISK_PATCH_APPLY_CONTRACT_V1.md",
            "reports\\codex_bridge\\ENGEL_CODE_COMPANION_LOW_RISK_PATCH_RUNNER_V1.md",
            "reports\\codex_bridge\\ENGEL_CODE_COMPANION_PATCH_RECEIPT_VIEWER_V1.md",
            "reports\\codex_bridge\\ENGEL_CODE_COMPANION_LOW_RISK_PATCH_GUI_STATUS_V1.md",
        ],
        "core_continuity_node_expected": "code_companion_low_risk_patch_runner_v1",
        "gui_surface_expected": "Code Companion Review",
        "safety_boundary": "narrow low-risk runner / receipts / no commit automation",
    },
    {
        "section": "Global Password / Protected Actions",
        "system_id": "global_password_protected_actions",
        "display_name": "Global Password Gate and Protected Action Registry",
        "primary_files": ["engel_global_password_gate.py", "engel_protected_action_registry.py"],
        "verifier_files": ["tools\\verify_engel_global_password_gate.py", "tools\\verify_engel_protected_action_registry.py"],
        "reports": ["reports\\codex_bridge\\ENGEL_GLOBAL_PASSWORD_GATED_ACTION_LAYER_V1.md"],
        "core_continuity_node_expected": "engel_global_password_gated_action_layer_v1",
        "gui_surface_expected": "Global Safety",
        "safety_boundary": "ACTION_REQUIRES_PASSWORD / blocked actions remain blocked",
    },
    {
        "section": "Global Password / Protected Actions",
        "system_id": "hive_safety_password_gate",
        "display_name": "Hive Safety Password Gate",
        "primary_files": ["engel_hive_safety_password_gate.py"],
        "verifier_files": ["tools\\verify_engel_hive_safety_password_gate.py"],
        "reports": ["reports\\codex_bridge\\ENGEL_HIVE_SAFETY_PASSWORD_GATE_V1.md"],
        "core_continuity_node_expected": "engel_hive_safety_password_gate_v1",
        "gui_surface_expected": "Permissions",
        "required": False,
        "safety_boundary": "MISSING_OPTIONAL if absent; Global Password Gate is the active newer gate",
    },
    {
        "section": "Background Worker / Startup",
        "system_id": "background_worker_startup_contract",
        "display_name": "Background Worker and Startup Autorun Contract",
        "primary_files": ["memory\\ENGEL_BACKGROUND_WORKER_STARTUP_AUTORUN_CONTRACT_V1.md"],
        "verifier_files": ["tools\\verify_engel_background_worker_startup_autorun_contract.py"],
        "reports": ["reports\\codex_bridge\\ENGEL_BACKGROUND_WORKER_STARTUP_AUTORUN_CONTRACT_V1.md"],
        "core_continuity_node_expected": "engel_background_worker_startup_autorun_contract_v1",
        "gui_surface_expected": "Global Safety",
        "safety_boundary": "disabled by default / no startup autorun install / no hidden autonomy",
    },
    {
        "section": "Background Worker / Startup",
        "system_id": "background_worker_registry",
        "display_name": "Background Worker Registry",
        "primary_files": ["engel_background_worker_registry.py"],
        "verifier_files": ["tools\\verify_engel_background_worker_registry.py"],
        "reports": [],
        "core_continuity_node_expected": "engel_background_worker_registry_v1",
        "gui_surface_expected": "Global Safety",
        "required": False,
        "safety_boundary": "MISSING_OPTIONAL if absent; contract node governs current worker safety",
    },
    {
        "section": "Research Toggle Worker",
        "system_id": "research_toggle_worker",
        "display_name": "Research Toggle Overnight Worker",
        "primary_files": ["engel_research_toggle_worker.py", "engel_research_toggle_status.py", "memory\\ENGEL_RESEARCH_TOGGLE_OVERNIGHT_WORKER_CONTRACT_V1.md"],
        "verifier_files": ["tools\\verify_engel_research_toggle_overnight_worker.py"],
        "reports": ["reports\\codex_bridge\\ENGEL_RESEARCH_TOGGLE_OVERNIGHT_WORKER_V1.md"],
        "core_continuity_node_expected": "engel_research_toggle_overnight_worker_v1",
        "gui_surface_expected": "Global Safety",
        "safety_boundary": "disabled by default / explicit job list / candidate-only / no startup autorun",
    },
    {
        "section": "Remote Worker / Mobile",
        "system_id": "multi_android_remote_workers_protocol",
        "display_name": "Engel Multi Android Remote Workers Protocol V1",
        "primary_files": [
            "engel_multi_android_remote_workers.py",
            "engel_android_remote_worker_protocol.py",
            "engel_remote_worker_app_scaffold.py",
            "memory\\ENGEL_MULTI_ANDROID_REMOTE_WORKERS_PROTOCOL_V1.json",
            "memory\\ENGEL_MULTI_ANDROID_REMOTE_WORKERS_PROTOCOL_V1.md",
            "memory\\ENGEL_ANDROID_REMOTE_WORKER_REGISTRY_V1.json",
            "remote_workers\\android_worker_alpha",
            "remote_workers\\android_worker_beta",
            "remote_workers\\android_worker_gamma",
        ],
        "verifier_files": ["tools\\verify_engel_multi_android_remote_workers.py"],
        "reports": ["reports\\codex_bridge\\ENGEL_MULTI_ANDROID_REMOTE_WORKERS_PROTOCOL_V1.md"],
        "core_continuity_node_expected": "engel_multi_android_remote_workers_protocol_v1",
        "gui_surface_expected": "System Integration",
        "current_state": "Multi Android Remote Workers Protocol V1 available; manual_transfer_v1; real data only; first real Alpha job packet prepared / awaiting manual worker status; Alpha/Beta/Gamma packages are uploadable manual-transfer packages and are not proof of phone connection; Communication Queen routes real job packets; Remote Workers are not Queens; old single-worker scaffold is superseded by this multi-worker protocol.",
        "safety_boundary": "MULTI_ANDROID_REMOTE_WORKERS_PROTOCOL / REAL_DATA_ONLY / MANUAL_TRANSFER_MODE_ONLY / ON_DEVICE_AUTONOMY_ALLOWED / AUTONOMY_SCOPE_ASSIGNED_JOB_SANDBOX_ONLY / COMMUNICATION_QUEEN_ROUTING_REQUIRED / REMOTE_WORKER_NOT_QUEEN / CANDIDATE_OUTPUTS_ONLY / no phone connection / no Android runtime execution from Engel / no ADB/SSH/socket/cloud sync / no fake worker progress / no fake jobs / no fake results / no trusted-memory write / no patch apply / no provider/network/browser / no model runtime / no Hermes/Ollama/llama.cpp / no background worker / no startup autorun",
    },
    {
        "section": "Remote Worker / Mobile",
        "system_id": "remote_worker_job_assignment",
        "display_name": "Communication Queen Remote Worker Job Assignment V1",
        "primary_files": [
            "engel_remote_worker_job_assignment.py",
            "memory\\ENGEL_REMOTE_WORKER_JOB_ASSIGNMENT_CONTRACT_V1.json",
            "memory\\ENGEL_REMOTE_WORKER_JOB_ASSIGNMENT_CONTRACT_V1.md",
            "memory\\ENGEL_ANDROID_REMOTE_WORKER_REGISTRY_V1.json",
            "remote_workers\\android_worker_alpha",
            "remote_workers\\android_worker_beta",
            "remote_workers\\android_worker_gamma",
        ],
        "verifier_files": ["tools\\verify_engel_remote_worker_job_assignment.py"],
        "reports": ["reports\\codex_bridge\\ENGEL_REMOTE_WORKER_JOB_ASSIGNMENT_V1.md"],
        "core_continuity_node_expected": "communication_queen_remote_worker_job_assignment_v1",
        "gui_surface_expected": "System Integration",
        "current_state": "Communication Queen Remote Worker Job Assignment V1 available; validates Alpha/Beta/Gamma job eligibility; creates only real prepared_for_manual_transfer job packets from real local input files; first real Alpha summarize_text packet is prepared for manual transfer; returned worker outputs remain candidate-only.",
        "safety_boundary": "COMMUNICATION_QUEEN_REMOTE_WORKER_JOB_ASSIGNMENT / REAL_JOB_PACKETS_ONLY / REAL_INPUT_FILE_REQUIRED / SAFE_LOCAL_INPUTS_ONLY / MANUAL_TRANSFER_ONLY / COMMUNICATION_QUEEN_ROUTING_REQUIRED / REMOTE_WORKER_NOT_QUEEN / PREPARED_FOR_MANUAL_TRANSFER_ONLY / CANDIDATE_OUTPUTS_ONLY / no phone connection / no Android runtime execution from Engel / no worker job execution from Engel / no ADB/SSH/live connection server/cloud sync / no fake returned status/result/progress / no completion without returned packet / no trusted-memory write / no memory promotion / no patch apply / no source mutation / no route mutation / no provider/network/browser / no model runtime / no package install / no download / no background worker / no startup autorun / Hermes remains rejected / do not install on this computer / no Ollama / no llama.cpp",
    },
    {
        "section": "Remote Worker / Mobile",
        "system_id": "android_studio_remote_worker_setup",
        "display_name": "Android Studio Setup for First Real Android Remote Worker V1",
        "primary_files": [
            "tools\\setup_android_worker_alpha_adb.py",
            "memory\\ENGEL_ANDROID_STUDIO_REMOTE_WORKER_SETUP_V1.json",
            "memory\\ENGEL_ANDROID_STUDIO_REMOTE_WORKER_SETUP_V1.md",
            "memory\\ENGEL_ANDROID_WORKER_ALPHA_PHONE_BUTTON_UI_V1.json",
            "memory\\ENGEL_ANDROID_WORKER_ALPHA_PHONE_BUTTON_UI_V1.md",
            "remote_workers\\android_worker_alpha\\finish_alpha_job.py",
            "remote_workers\\android_worker_alpha\\start_remote_worker_ui.py",
            "remote_workers\\android_worker_alpha\\remote_worker_phone_ui.py",
            "remote_workers\\android_worker_alpha\\termux_widget_shortcuts\\EngelWorkerAlphaUI",
            "remote_workers\\android_worker_alpha\\communication_queen_choices.py",
            "remote_workers\\android_worker_alpha\\queen_choice_bridge.py",
            "remote_workers\\android_worker_alpha",
            "remote_workers\\android_worker_alpha\\jobs\\20260516T201324Z_android_worker_alpha_summarize_text_summarize_engel_remote_worke.json",
            "reports\\codex_bridge\\ENGEL_MULTI_ANDROID_REMOTE_WORKERS_PROTOCOL_V1.md",
        ],
        "verifier_files": [
            "tools\\verify_android_worker_alpha_adb_setup.py",
            "tools\\verify_android_worker_alpha_phone_button_ui.py",
            "tools\\verify_android_worker_alpha_finish_setup.py",
        ],
        "reports": [
            "reports\\codex_bridge\\ENGEL_ANDROID_STUDIO_REMOTE_WORKER_SETUP_V1.md",
            "reports\\codex_bridge\\ENGEL_ANDROID_STUDIO_ADB_PATH_FIX_V1.md",
            "reports\\codex_bridge\\ENGEL_ANDROID_WORKER_ALPHA_ON_DEVICE_RUN_EXTENSION_V1.md",
            "reports\\codex_bridge\\ENGEL_ANDROID_WORKER_ALPHA_PHONE_BUTTON_UI_V1.md",
            "reports\\codex_bridge\\ENGEL_ANDROID_WORKER_ALPHA_FINISH_SETUP_V1.md",
        ],
        "core_continuity_node_expected": "android_studio_remote_worker_setup_v1",
        "gui_surface_expected": "System Integration",
        "current_state": "Android Studio / ADB setup helper available as a bounded ADB file-transfer bridge for Android Worker Alpha; status, check-python, check-termux, prepare-commands, prepare-run-command, prepare-phone-button-commands, check-phone-ui, and prepare-one-line-termux-finish are non-mutating; push, push-phone-button-ui, and push-finish-runner require --i-understand-this-uses-adb; finish-alpha-worker requires --i-approve-finish-alpha-worker and either pulls real returned files or stops honestly with one exact Termux fallback; optional on-device run requires --i-approve-run-worker-on-phone and does not trust completion until returned files are pulled and validated; phone button UI uses real local files and bounded Communication Queen choices only; no second ADB/Termux hook; no fake status/result/progress/log/receipt; no phone control loop.",
        "safety_boundary": "ANDROID_STUDIO_REMOTE_WORKER_SETUP / ANDROID_WORKER_ALPHA_PHONE_BUTTON_UI / ANDROID_WORKER_ALPHA_FINISH_SETUP / ADB_FILE_TRANSFER_ONLY / HUMAN_APPROVED_TRANSPORT_ONLY / MANUAL_TRANSFER_BRIDGE / COMMUNICATION_QUEEN_ROUTING_REQUIRED / REMOTE_WORKER_NOT_QUEEN / TERMUX_WIDGET_SHORTCUT_TEMPLATE / REAL_FILES_ONLY / REAL_JOB_PACKET_ONLY / REAL_INPUT_FILE_ONLY / QUEEN_CHOICES_BOUNDED / PYTHON_TERMUX_STATUS_CHECK_ONLY / RUN_WORKER_REQUIRES_EXPLICIT_APPROVAL / FINISH_WORKER_REQUIRES_EXPLICIT_APPROVAL / RUN_WORKER_ON_PHONE_ONLY / COMPLETION_NOT_TRUSTED_UNTIL_PULL_VALIDATION / ONE_LINE_TERMUX_FALLBACK_ONLY / NO_SECOND_ADB_HOOK / no worker execution during push / no UI execution during push / no fake choices/jobs/status/result/progress/log/receipt / no job completion marking / no Termux/app/package/model install automation / no Hermes/Ollama/llama.cpp / no model runtime / no provider/network/browser / no network server / no SSH / no cloud sync / no ADB wireless / no phone control loop / no background worker / no startup autorun / no trusted-memory write / no patch apply",
    },
    {
        "section": "Remote Worker / Mobile",
        "system_id": "android_remote_worker_plan",
        "display_name": "Engel Android Remote Worker Plan V1",
        "primary_files": [
            "memory\\ENGEL_ANDROID_REMOTE_WORKER_PLAN_V1.json",
            "memory\\ENGEL_ANDROID_REMOTE_WORKER_PLAN_V1.md",
            "engel_android_remote_worker_contract.py",
        ],
        "verifier_files": ["tools\\verify_android_remote_worker_contract.py"],
        "reports": ["reports\\codex_bridge\\ENGEL_ANDROID_REMOTE_WORKER_PLAN_V1.md"],
        "core_continuity_node_expected": "engel_android_remote_worker_plan_v1",
        "gui_surface_expected": "System Integration",
        "current_state": "scaffold-only; controlled by Communication Queen; not a Queen; no runtime phone connection; future Phase 2 manual JSON handoff",
        "safety_boundary": "REMOTE_WORKER / MOBILE_WORKER / CONTROLLED_BY_COMMUNICATION_QUEEN / ROUTED_THROUGH_COMMUNICATION_QUEEN / NOT_A_QUEEN / no network runtime / no background worker / no trusted-memory, queue, route, or source mutation",
    },
    {
        "section": "Truthfulness Guard",
        "system_id": "truthfulness_anti_flattery_guard",
        "display_name": "Truthfulness and Anti-Flattery Guard",
        "primary_files": ["engel_truthfulness_anti_flattery_guard.py", "memory\\ENGEL_TRUTHFULNESS_ANTI_FLATTERY_GUARD_V1.md"],
        "verifier_files": ["tools\\verify_engel_truthfulness_anti_flattery_guard.py"],
        "reports": ["reports\\codex_bridge\\ENGEL_TRUTHFULNESS_ANTI_FLATTERY_GUARD_V1.md"],
        "core_continuity_node_expected": "engel_truthfulness_anti_flattery_guard_v1",
        "gui_surface_expected": "AI Growth",
        "safety_boundary": "verification-first / no-flattery / heuristic only / no provider calls",
    },
    {
        "section": "Core Continuity",
        "system_id": "core_continuity",
        "display_name": "Core Continuity Map",
        "primary_files": ["memory\\ENGEL_CORE_CONTINUITY_MAP_V1.md", "memory\\ENGEL_CORE_CONTINUITY_MAP_V1.json", "tools\\build_engel_core_continuity_map.py"],
        "verifier_files": ["tools\\verify_engel_core_continuity_map.py"],
        "reports": ["reports\\codex_bridge\\ENGEL_CORE_CONTINUITY_MAP.md"],
        "core_continuity_node_expected": "engel_system_integration_continuity_reconciliation_v1",
        "gui_surface_expected": "System Integration",
        "safety_boundary": "read-only index / not trusted-memory write / not runtime authority",
    },
    {
        "section": "Core Continuity",
        "system_id": "engel_ai_update_routes",
        "display_name": "Engel AI Update Routes V1",
        "primary_files": [
            "engel_ai_update_routes.py",
            "engel_communication_router.py",
            "engel_progress_dashboard.py",
            "engel_memory_candidate_inventory.py",
            "engel_archive_shelf_manager.py",
        ],
        "verifier_files": ["tools\\verify_engel_ai_update_routes.py"],
        "reports": ["reports\\codex_bridge\\ENGEL_AI_UPDATE_ROUTE_CONNECTIONS_V1.md"],
        "core_continuity_node_expected": "engel_ai_update_routes_v1",
        "current_state": "Feature-expansion status modules are accessible through Engel AI command routing while remaining local, offline, read-only, status-only, and invisible as new UI.",
        "safety_boundary": "command understanding only / no visible UI change / no memory promotion / no trusted-memory write / no fix apply / no archive migration-copy-sync-delete / no provider-model-network-browser / no background worker / no packaging",
    },
    {
        "section": "GUI Status Surfaces",
        "system_id": "gui_status_surfaces",
        "display_name": "Companion and Research Office Status Tabs",
        "primary_files": ["engel_companion.py", "engel_research_office.py"],
        "verifier_files": ["tools\\verify_engel_ai_growth_gui_tabs.py"],
        "reports": ["reports\\codex_bridge\\ENGEL_AI_GROWTH_GUI_TABS_V1.md"],
        "core_continuity_node_expected": "engel_system_integration_continuity_reconciliation_v1",
        "gui_surface_expected": "System Integration",
        "safety_boundary": "read-only status tabs / no action execution from reconciliation surface",
    },
    {
        "section": "Verifier Coverage",
        "system_id": "verifier_coverage",
        "display_name": "Verifier Coverage",
        "primary_files": ["tools\\verify_engel_core_continuity_map.py"],
        "verifier_files": ["tools\\verify_engel_system_integration_status.py"],
        "reports": ["reports\\codex_bridge\\ENGEL_SYSTEM_INTEGRATION_AND_CONTINUITY_RECONCILIATION_V1.md"],
        "core_continuity_node_expected": "engel_system_integration_continuity_reconciliation_v1",
        "gui_surface_expected": "System Integration",
        "safety_boundary": "verifier coverage checked / optional missing verifiers reported honestly",
    },
    {
        "section": "Runtime / Environment Dependencies",
        "system_id": "wsl_ubuntu_runtime_dependency",
        "display_name": "WSL Ubuntu Runtime Dependency",
        "primary_files": [
            "memory\\ENGEL_WSL_UBUNTU_RUNTIME_DEPENDENCY_V1.md",
            "memory\\ENGEL_WSL_UBUNTU_RUNTIME_DEPENDENCY_V1.json",
        ],
        "verifier_files": ["tools\\verify_engel_wsl_ubuntu_runtime_dependency.py"],
        "reports": ["reports\\codex_bridge\\ENGEL_WSL_UBUNTU_RUNTIME_DEPENDENCY_V1.md"],
        "core_continuity_node_expected": "engel_wsl_ubuntu_runtime_dependency_v1",
        "gui_surface_expected": "System Integration",
        "manual_downloads_root": "/mnt/engel-hdd-vault/wsl",
        "current_state": "WSL Ubuntu runtime dependency recorded / NOT_TRUSTED_MEMORY / STAGE_2_AUTONOMY / STAGE_3_AUTONOMY",
        "safety_boundary": "environment/runtime dependency / stored under Dell HDD archive when mounted / not trusted memory / STAGE_2_AUTONOMY (auto-run authorized) / STAGE_3_AUTONOMY (auto-install authorized, model loading authorized, inference authorized, training authorized, package-manager-and-model-registry network authorized) / browser-provider-arbitrary-outbound-network-source-mutation still gated",
    },
    {
        "section": "Runtime / Environment Dependencies",
        "system_id": "wsl_bridge",
        "display_name": "Engel WSL Bridge V1",
        "primary_files": [
            "engel_wsl_bridge.py",
            "engel_ai_update_routes.py",
            "engel_ai.py",
        ],
        "verifier_files": ["tools\\verify_engel_wsl_bridge.py"],
        "reports": [
            "reports\\codex_bridge\\ENGEL_WSL_BRIDGE_V1.md",
            "reports\\codex_bridge\\ENGEL_PHASE_B_NATIVE_INVOKE_ROUTES_V1.md",
        ],
        "core_continuity_node_expected": "engel_wsl_bridge_v1",
        "gui_surface_expected": "none",
        "manual_downloads_root": "D:\\WSL\\Ubuntu",
        "current_state": "local WSL bridge with read-only status routes plus fixed Phase B Stage 3 action command IDs",
        "safety_boundary": "local WSL bridge / status routes read-only-status-only / Phase B Stage 3 action routes fixed allowlist IDs only / allowlisted WSL commands only / timeout-bounded / no free-form shell / no WSL install / no Ubuntu import-unregister / package-manager words contracted to fixed Stage 3 actions / no sudo / no hidden background worker / no browser spawn / no provider calls / no arbitrary outbound network / no Engel source mutation from WSL / no trusted-memory write",
    },
    {
        "section": "Model Library / Offline Model Readiness",
        "system_id": "manual_model_intake_evaluator",
        "display_name": "Manual Model Intake Evaluator",
        "primary_files": ["engel_manual_model_intake_evaluator.py"],
        "verifier_files": ["tools\\verify_engel_manual_model_intake_evaluator.py"],
        "reports": [
            "reports\\codex_bridge\\ENGEL_MANUAL_MODEL_INTAKE_EVALUATION_V1.md",
            "reports\\codex_bridge\\ENGEL_MODEL_INTAKE_INTEGRATION_UPDATE.md",
        ],
        "core_continuity_node_expected": "engel_manual_model_intake_evaluator_v1",
        "gui_surface_expected": "System Integration",
        "review_output_folder": "reports\\model_intake_reviews\\",
        "manual_downloads_root": "/opt/engel/models-active",
        "current_state": "no real model evaluated yet unless review files exist",
        "safety_boundary": "MODEL_INTAKE_REVIEW_ONLY / EXPLICIT_CANDIDATE_PATH_REQUIRED / MANUAL_DOWNLOADS_ONLY / NO_MODEL_LOADING / NO_INFERENCE / NO_AUTO_MOVE / NO_AUTO_DELETE / WSL_UBUNTU_CLASSIFIED_NOT_MODEL",
    },
    {
        "section": "Manual Downloads",
        "system_id": "manual_model_downloads_root",
        "display_name": "Manual Model Downloads Root",
        "primary_files": ["memory\\ENGEL_MODEL_LIBRARY_PLAN_V1.md", "memory\\ENGEL_MODEL_LIBRARY_PLAN_V1.json"],
        "verifier_files": ["tools\\verify_engel_model_library_plan.py"],
        "reports": [
            "reports\\codex_bridge\\ENGEL_MODEL_LIBRARY_PLAN_V1.md",
            "reports\\codex_bridge\\ENGEL_MANUAL_MODEL_INTAKE_EVALUATION_V1.md",
            "reports\\codex_bridge\\ENGEL_MODEL_INTAKE_INTEGRATION_UPDATE.md",
        ],
        "core_continuity_node_expected": "engel_manual_model_intake_evaluator_v1",
        "gui_surface_expected": "System Integration",
        "manual_downloads_root": "/opt/engel/models-active",
        "current_state": "manual shelf only / model runtime disabled",
        "safety_boundary": "manual downloads are untrusted until human approval / no loading/inference/move/delete/download",
    },
    {
        "section": "Manual Downloads / Non-Model Materials",
        "system_id": "wsl_ubuntu_non_model_material",
        "display_name": "WSL Ubuntu Non-Model Material",
        "primary_files": ["memory\\ENGEL_WSL_UBUNTU_RUNTIME_DEPENDENCY_V1.md"],
        "verifier_files": ["tools\\verify_engel_wsl_ubuntu_runtime_dependency.py"],
        "reports": ["reports\\codex_bridge\\ENGEL_WSL_UBUNTU_RUNTIME_DEPENDENCY_V1.md"],
        "core_continuity_node_expected": "engel_wsl_ubuntu_runtime_dependency_v1",
        "gui_surface_expected": "System Integration",
        "manual_downloads_root": "/mnt/engel-hdd-vault/wsl",
        "current_state": "Ubuntu WSL2 distro archived under Dell HDD by human-completed migration",
        "safety_boundary": "NOT_AI_MODEL / NOT_MODEL_LIBRARY_MATERIAL / not loaded as model / not imported into trusted memory",
    },
    {
        "section": "Optional Local Tooling Environment",
        "system_id": "wsl_ubuntu_optional_local_tooling",
        "display_name": "WSL Ubuntu Optional Local Tooling Environment",
        "primary_files": ["memory\\ENGEL_WSL_UBUNTU_RUNTIME_DEPENDENCY_V1.md"],
        "verifier_files": ["tools\\verify_engel_wsl_ubuntu_runtime_dependency.py"],
        "reports": ["reports\\codex_bridge\\ENGEL_WSL_UBUNTU_RUNTIME_DEPENDENCY_V1.md"],
        "core_continuity_node_expected": "engel_wsl_ubuntu_runtime_dependency_v1",
        "gui_surface_expected": "System Integration",
        "manual_downloads_root": "/opt/engel/models-active/wsl/Ubuntu",
        "current_state": "live local AI development environment under Stage 3 autonomy (auto-run, auto-install, model loading, inference, training authorized)",
        "safety_boundary": "STAGE_3_AUTONOMY: auto-install authorized, model loading authorized, inference authorized, training authorized, package-manager-and-model-registry network authorized / still gated: NO_BROWSER, NO_PROVIDER_CALLS, NO_ARBITRARY_OUTBOUND_NETWORK, NO_SOURCE_MUTATION",
    },
    {
        "section": "Approved Library / Intake",
        "system_id": "llm_python_library_intake_plan",
        "display_name": "Engel LLM and Python Library Intake Plan V1",
        "primary_files": [
            "memory\\ENGEL_LLM_AND_PYTHON_LIBRARY_INTAKE_PLAN_V1.json",
            "memory\\ENGEL_LLM_AND_PYTHON_LIBRARY_INTAKE_PLAN_V1.md",
        ],
        "verifier_files": ["tools\\verify_engel_llm_and_python_library_intake_plan.py"],
        "reports": ["reports\\codex_bridge\\ENGEL_LLM_AND_PYTHON_LIBRARY_INTAKE_PLAN_V1.md"],
        "core_continuity_node_expected": "engel_llm_and_python_library_intake_plan_v1",
        "gui_surface_expected": "System Integration",
        "current_state": "Model Library / Non-Model Library readiness path; model candidate intake path and Python docs/reference intake path are plan-only; Android Remote Worker non-model reference boundary is plan-only; next step: Manual LLM Candidate Review Batch V1; next step: Python Library Approved Materials Intake V1",
        "manual_downloads_root": "/opt/engel/models-active",
        "safety_boundary": "LLM_AND_PYTHON_LIBRARY_INTAKE_PLAN / PLAN_ONLY / no model loading/inference/package install / WSL runtime dependency remains NOT_AI_MODEL / Android Remote Worker references are non-model/scaffold-only / approved references remain untrusted until reviewed",
    },
    {
        "section": "Approved Library / Intake",
        "system_id": "manual_model_intake_approved_library_boundary",
        "display_name": "Manual Model Intake Approved Library Boundary",
        "primary_files": ["memory\\ENGEL_STORAGE_LOCATION_REGISTRY_V1.md", "memory\\ENGEL_APPROVED_LIBRARY_IMPORT_INTAKE_CONTRACT_V1.md"],
        "verifier_files": ["tools\\verify_engel_storage_location_registry.py"],
        "reports": [
            "reports\\codex_bridge\\ENGEL_MANUAL_MODEL_INTAKE_EVALUATION_V1.md",
            "reports\\codex_bridge\\ENGEL_MODEL_INTAKE_INTEGRATION_UPDATE.md",
        ],
        "core_continuity_node_expected": "engel_manual_model_intake_evaluator_v1",
        "gui_surface_expected": "System Integration",
        "safety_boundary": "candidate reviews do not approve, import, move, delete, load, infer, or write trusted memory",
    },
    {
        "section": "Safety Boundaries",
        "system_id": "outside_ai_boundary_rule",
        "display_name": "Engel Outside-AI Boundary Rule V1",
        "primary_files": [
            "engel_outside_ai_boundary.py",
            "memory\\ENGEL_OUTSIDE_AI_BOUNDARY_RULE_V1.json",
            "memory\\ENGEL_OUTSIDE_AI_BOUNDARY_RULE_V1.md",
        ],
        "verifier_files": ["tools\\verify_engel_outside_ai_boundary.py"],
        "reports": ["reports\\codex_bridge\\ENGEL_OUTSIDE_AI_BOUNDARY_RULE_V1.md"],
        "core_continuity_node_expected": "engel_outside_ai_boundary_rule_v1",
        "gui_surface_expected": "System Integration",
        "current_state": "Outside-AI Boundary V1 available; Engel uses Tools/AI; Tools/AI do not use Engel; Hermes/Hermes-style agentic runtimes rejected for this computer",
        "safety_boundary": "OUTSIDE_AI_BOUNDARY_RULE / OUTSIDE_AI_UNTRUSTED_INPUT / ENGEL_CONTROLLED_BOUNDARY / NO_OUTSIDE_AI_CONTROL / NO_BYPASS / NO_SELF_APPROVAL / NO_DIRECT_TOOL_EXECUTION / NO_TRUSTED_MEMORY_WRITE / NO_ROUTE_MUTATION / NO_SOURCE_MUTATION / NO_REMOTE_QUEEN_CONTROL / NO_PROVIDER_CALLS / NO_NETWORK / NO_BROWSER / NO_PACKAGE_INSTALL / NO_MODEL_DOWNLOAD / NO_STARTUP_AUTOLOAD / NO_BACKGROUND_WORKER / HUMAN_APPROVAL_REQUIRED / VERIFIER_REQUIRED / RECEIPTS_REQUIRED / HERMES_APPROVED_FOR_LOCAL_TESTING_HUMAN_DRIVEN_ONLY",
    },
    {
        "section": "Safety Boundaries",
        "system_id": "manual_model_intake_safety_boundary",
        "display_name": "Manual Model Intake Safety Boundary",
        "primary_files": ["engel_manual_model_intake_evaluator.py"],
        "verifier_files": ["tools\\verify_engel_manual_model_intake_evaluator.py"],
        "reports": [
            "reports\\codex_bridge\\ENGEL_MANUAL_MODEL_INTAKE_EVALUATION_V1.md",
            "reports\\codex_bridge\\ENGEL_MODEL_INTAKE_INTEGRATION_UPDATE.md",
        ],
        "core_continuity_node_expected": "engel_manual_model_intake_evaluator_v1",
        "gui_surface_expected": "System Integration",
        "safety_boundary": "no model loading / no inference / no training / no auto move / no auto delete / no download / no network/browser/provider / no trusted-memory write / WSL/Ubuntu tar is not a model",
    },
    {
        "section": "Package Visibility Records",
        "system_id": "package_visibility_records",
        "display_name": "AI Growth and Code Companion Package Visibility Records",
        "primary_files": [
            "reports\\codex_bridge\\ENGEL_AI_GROWTH_VISIBILITY_PACKAGE_REFRESH.md",
            "reports\\codex_bridge\\ENGEL_CODE_COMPANION_CANDIDATE_REVIEW_PACKAGE_REFRESH.md",
        ],
        "verifier_files": ["tools\\verify_engel_core_continuity_map.py"],
        "reports": [
            "reports\\codex_bridge\\ENGEL_CORE_CONTINUITY_MAP_AI_GROWTH_VISIBILITY_REFRESH_UPDATE.md",
            "reports\\codex_bridge\\ENGEL_CORE_CONTINUITY_MAP_PACKAGED_CODE_COMPANION_REVIEW_VISIBILITY_UPDATE.md",
        ],
        "core_continuity_node_expected": "latest_engel_ai_growth_visibility_package_refresh_v1",
        "gui_surface_expected": "System Integration",
        "safety_boundary": "records only / no package refresh in reconciliation pass",
    },
    {
        "section": "Active Build Plan",
        "system_id": "active_build_plan_learning_and_fixing",
        "display_name": "Engel Active Build Plan: Learning and Fixing V1",
        "primary_files": [
            "memory\\ENGEL_ACTIVE_BUILD_PLAN_LEARNING_AND_FIXING_V1.json",
            "memory\\ENGEL_ACTIVE_BUILD_PLAN_LEARNING_AND_FIXING_V1.md",
        ],
        "verifier_files": ["tools\\verify_engel_active_build_plan_learning_and_fixing.py"],
        "reports": ["reports\\codex_bridge\\ENGEL_ACTIVE_BUILD_PLAN_LEARNING_AND_FIXING_V1.md"],
        "core_continuity_node_expected": "engel_active_build_plan_learning_and_fixing_v1",
        "gui_surface_expected": "System Integration",
        "current_state": "current immediate step: Integrated Status + WSL Runtime Package Refresh; next major path: LLM Library and Python Library Intake; next functional path: Learning Job Queue / Self-Learning Run Controller / Fix Candidate Queue",
        "safety_boundary": "LEARNING_AND_FIXING_PATH / PASSWORD_GATE_REQUIRED_FOR_WRITE_APPLY_RUN / PROTECTED_ACTION_REGISTRY_REQUIRED / RECEIPTS_REQUIRED / VERIFIERS_REQUIRED / no provider/network/browser/model/trusted-memory/source-mutation/background-worker/startup behavior enabled",
    },
]


def rel_path(path_text: str) -> Path:
    return ROOT / path_text


def exists(path_text: str) -> bool:
    return rel_path(path_text).exists()


def load_core_map() -> dict[str, object]:
    try:
        return json.loads(CORE_MAP_JSON.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def gui_text() -> str:
    parts = []
    for path_text in ["engel_companion.py", "engel_research_office.py"]:
        path = rel_path(path_text)
        try:
            parts.append(path.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            parts.append("")
    return "\n".join(parts)


def evaluate_systems() -> list[dict[str, object]]:
    core = load_core_map()
    gui = gui_text()
    evaluated = []
    for raw in SYSTEMS:
        system = dict(raw)
        required = bool(system.get("required", True))
        primary_files = list(system.get("primary_files", []))
        verifier_files = list(system.get("verifier_files", []))
        reports = list(system.get("reports", []))
        core_node = str(system.get("core_continuity_node_expected", ""))
        gui_surface = str(system.get("gui_surface_expected", ""))
        missing_primary = [path for path in primary_files if not exists(path)]
        missing_verifiers = [path for path in verifier_files if not exists(path)]
        missing_reports = [path for path in reports if not exists(path)]
        core_missing = bool(core_node and core_node not in core)
        gui_missing = bool(gui_surface and gui_surface not in gui)
        missing_items = missing_primary + missing_verifiers + missing_reports
        labels = ["READ_ONLY_STATUS", "SAFE_TO_VIEW"]
        if not missing_items and not core_missing and not gui_missing:
            labels.extend(["AVAILABLE", "CONNECTED"])
        elif not required:
            labels.append("MISSING_OPTIONAL")
        else:
            if missing_primary or missing_reports:
                labels.append("MISSING_REQUIRED")
            if missing_verifiers:
                labels.append("NEEDS_VERIFIER_LINK")
            if core_missing:
                labels.append("NEEDS_CORE_CONTINUITY_LINK")
            if gui_missing:
                labels.append("NEEDS_GUI_LINK")
        boundary = str(system.get("safety_boundary", ""))
        if "password" in boundary.lower():
            labels.append("ACTION_REQUIRES_PASSWORD")
        if "contract" in boundary.lower():
            labels.append("ACTION_REQUIRES_CONTRACT")
        if "verifier" in boundary.lower():
            labels.append("ACTION_REQUIRES_VERIFIER")
        system["status"] = " / ".join(labels)
        system["missing_items"] = missing_items
        system["missing_primary_files"] = missing_primary
        system["missing_verifier_files"] = missing_verifiers
        system["missing_reports"] = missing_reports
        system["core_continuity_node_present"] = not core_missing
        system["gui_surface_present"] = not gui_missing
        if "review_output_folder" in system:
            folder = str(system["review_output_folder"])
            system["review_output_folder"] = folder
            system["review_output_folder_present"] = exists(folder.rstrip("\\/"))
        if "manual_downloads_root" in system:
            system["manual_downloads_root"] = str(system["manual_downloads_root"])
        if "current_state" in system:
            system["current_state"] = str(system["current_state"])
        evaluated.append(system)
    return evaluated


def integration_summary() -> dict[str, object]:
    systems = evaluate_systems()
    missing_optional = [system for system in systems if "MISSING_OPTIONAL" in str(system["status"])]
    missing_required = [system for system in systems if "MISSING_REQUIRED" in str(system["status"])]
    needs_core = [system for system in systems if "NEEDS_CORE_CONTINUITY_LINK" in str(system["status"])]
    needs_gui = [system for system in systems if "NEEDS_GUI_LINK" in str(system["status"])]
    needs_verifier = [system for system in systems if "NEEDS_VERIFIER_LINK" in str(system["status"])]
    return {
        "schema_version": "1.0",
        "status_labels": list(STATUS_LABELS),
        "display_labels": list(DISPLAY_LABELS),
        "sections": list(SECTION_ORDER),
        "systems": systems,
        "summary": {
            "systems_total": len(systems),
            "connected_count": sum(1 for system in systems if "CONNECTED" in str(system["status"])),
            "missing_optional_count": len(missing_optional),
            "missing_required_count": len(missing_required),
            "needs_core_continuity_link_count": len(needs_core),
            "needs_gui_link_count": len(needs_gui),
            "needs_verifier_link_count": len(needs_verifier),
        },
        "missing_optional_systems": [str(system["system_id"]) for system in missing_optional],
        "missing_required_systems": [str(system["system_id"]) for system in missing_required],
        "next_safe_integration_steps": [
            "Active Build Plan: Learning and Fixing V1 is the current plan.",
            "Immediate official step: Integrated Status + WSL Runtime Package Refresh.",
            "Next major path: LLM Library and Python Library Intake.",
            "Next functional path: Learning Job Queue / Self-Learning Run Controller / Fix Candidate Queue / Learning-to-Fix Cycle.",
            "Next work should enable bounded candidate learning and safe fix queues, not just visibility.",
            "Keep this reconciliation surface read-only.",
            "Run targeted verifiers before claiming a system is connected.",
            "Add future GUI controls only after separate action contracts exist.",
            "Keep package refresh and live promotion outside this pass.",
            "Treat optional missing systems as honest inventory, not failure.",
        ],
        "safety_boundary": [
            "No new runtime behavior.",
            "No provider calls.",
            "No network.",
            "No browser.",
            "No model runtime.",
            "No trusted-memory write.",
            "No source mutation beyond this reconciliation refactor.",
            "No package refresh.",
            "No background worker started.",
            "No startup autorun enabled.",
        ],
    }


def systems_by_section(systems: list[dict[str, object]]) -> dict[str, list[dict[str, object]]]:
    grouped = {section: [] for section in SECTION_ORDER}
    for system in systems:
        grouped.setdefault(str(system["section"]), []).append(system)
    return grouped


def render_status() -> str:
    payload = integration_summary()
    grouped = systems_by_section(list(payload["systems"]))
    lines = [
        "Engel System Integration and Continuity Reconciliation V1",
        "",
        "Status:",
        *[f"- {label}" for label in STATUS_LABELS],
        "",
        "Display labels:",
        *[f"- {label}" for label in DISPLAY_LABELS],
        "",
        "Read-only behavior:",
        "- This module checks explicit known local paths only.",
        "- It does not run workers.",
        "- It does not run patch apply.",
        "- It does not run package refresh.",
        "- It does not call providers/network/browser/model runtime, write trusted memory, or start background workers.",
    ]
    for section in SECTION_ORDER:
        lines.extend(["", "## " + section])
        if section == "Next Safe Integration Steps":
            lines.extend(f"- {step}" for step in payload["next_safe_integration_steps"])
            continue
        entries = grouped.get(section, [])
        if not entries:
            lines.append("- no entries")
            continue
        for system in entries:
            lines.extend(
                [
                    f"- system_id: {system['system_id']}",
                    f"  display_name: {system['display_name']}",
                    f"  status: {system['status']}",
                    f"  primary_files: {', '.join(system.get('primary_files', [])) or 'none'}",
                    f"  verifier_files: {', '.join(system.get('verifier_files', [])) or 'none'}",
                    f"  reports: {', '.join(system.get('reports', [])) or 'none'}",
                    f"  core_continuity_node_expected: {system.get('core_continuity_node_expected', '')}",
                    f"  gui_surface_expected: {system.get('gui_surface_expected', '')}",
                    f"  review_output_folder: {system.get('review_output_folder', 'none')}",
                    f"  manual_downloads_root: {system.get('manual_downloads_root', 'none')}",
                    f"  current_state: {system.get('current_state', 'n/a')}",
                    f"  missing_items: {', '.join(system.get('missing_items', [])) or 'none'}",
                    f"  safety_boundary: {system.get('safety_boundary', '')}",
                ]
            )
    lines.extend(
        [
            "",
            "Summary:",
            *[f"- {key}: {value}" for key, value in payload["summary"].items()],
            "",
            "Safety boundary:",
            *[f"- {item}" for item in payload["safety_boundary"]],
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def render_check_links() -> str:
    payload = integration_summary()
    lines = [
        "Engel System Integration Link Check",
        "",
        "Missing optional systems:",
    ]
    optional = payload["missing_optional_systems"]
    lines.extend(f"- {item}" for item in optional) if optional else lines.append("- none")
    lines.append("")
    lines.append("Missing required systems:")
    required = payload["missing_required_systems"]
    lines.extend(f"- {item}" for item in required) if required else lines.append("- none")
    lines.append("")
    lines.append("Detailed missing items:")
    missing_any = False
    for system in payload["systems"]:
        missing = list(system.get("missing_items", []))
        if not missing:
            continue
        missing_any = True
        lines.append(f"- {system['system_id']}: {', '.join(missing)}")
    if not missing_any:
        lines.append("- none")
    lines.extend(["", "This check is read-only and reports optional absences honestly."])
    return "\n".join(lines).rstrip() + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only Engel system integration reconciliation status.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--status", action="store_true", help="Print readable integration status.")
    mode.add_argument("--json", action="store_true", help="Print structured integration status JSON.")
    mode.add_argument("--check-links", action="store_true", help="Check explicit known system links.")
    return parser


def main(argv: list[str] | None = None, stdout=None, stderr=None) -> int:
    out = stdout if stdout is not None else sys.stdout
    args = build_parser().parse_args(argv)
    if args.json:
        out.write(json.dumps(integration_summary(), indent=2, sort_keys=True) + "\n")
        return 0
    if args.check_links:
        out.write(render_check_links())
        return 0
    out.write(render_status())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
