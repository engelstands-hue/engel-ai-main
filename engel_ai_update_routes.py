from __future__ import annotations

from dataclasses import dataclass


PROGRESS_ROUTE_ID = "engel.progress_dashboard.status"
MEMORY_CANDIDATE_ROUTE_ID = "engel.memory_candidate_inventory.status"
ARCHIVE_SHELF_ROUTE_ID = "engel.archive_shelf_manager.status"
ENGEL_AGENT_STATUS_ROUTE_ID = "engel.engel_agent.status"
ENGEL_AGENT_INVOKE_ROUTE_ID = "engel.engel_agent.invoke"
ENGEL_AGENT_DOCTOR_ROUTE_ID = "engel.engel_agent.doctor"
ENGEL_AGENT_VERSION_ROUTE_ID = "engel.engel_agent.version"
ENGEL_AGENT_TOOLSETS_ROUTE_ID = "engel.engel_agent.toolsets"
ENGEL_AGENT_GATEWAY_STATUS_ROUTE_ID = "engel.engel_agent.gateway_status"
ENGEL_AGENT_GATEWAY_START_ROUTE_ID = "engel.engel_agent.gateway_start"
ENGEL_AGENT_GATEWAY_STOP_ROUTE_ID = "engel.engel_agent.gateway_stop"
ENGEL_AGENT_CRON_STATUS_ROUTE_ID = "engel.engel_agent.cron_status"
ENGEL_AGENT_CRON_LIST_ROUTE_ID = "engel.engel_agent.cron_list"
ENGEL_AGENT_MEMORY_STATUS_ROUTE_ID = "engel.engel_agent.memory_status"
ENGEL_AGENT_SKILLS_LIST_ROUTE_ID = "engel.engel_agent.skills_list"
ENGEL_AGENT_SESSIONS_LIST_ROUTE_ID = "engel.engel_agent.sessions_list"
ENGEL_AGENT_SESSIONS_STATS_ROUTE_ID = "engel.engel_agent.sessions_stats"
ENGEL_AGENT_PLUGINS_LIST_ROUTE_ID = "engel.engel_agent.plugins_list"
ENGEL_AGENT_TOP_STATUS_ROUTE_ID = "engel.engel_agent.top_status"
ENGEL3D_STATUS_ROUTE_ID = "engel.engel3d.status"
ENGEL3D_START_ROUTE_ID = "engel.engel3d.start"
ENGEL3D_STOP_ROUTE_ID = "engel.engel3d.stop"
ENGEL3D_BUILD_ROUTE_ID = "engel.engel3d.build"
ENGEL_SANDBOX_STATUS_ROUTE_ID = "engel.engel_sandbox.status"
ENGEL_SANDBOX_NODES_ROUTE_ID = "engel.engel_sandbox.nodes"
ENGEL_SANDBOX_LIST_ROUTE_ID = "engel.engel_sandbox.list"
ENGEL_SANDBOX_CREATE_ROUTE_ID = "engel.engel_sandbox.create"
ENGEL_SANDBOX_DELETE_ROUTE_ID = "engel.engel_sandbox.delete"
ENGEL_SANDBOX_BRING_UP_ROUTE_ID = "engel.engel_sandbox.bring_up"
ENGEL_WSL_STATUS_ROUTE_ID = "engel.wsl.status"
ENGEL_WSL_DISTROS_ROUTE_ID = "engel.wsl.distros"
ENGEL_WSL_TOOLS_ROUTE_ID = "engel.wsl.tools"
ENGEL_WSL_PATHS_ROUTE_ID = "engel.wsl.paths"
ENGEL_WSL_SELF_TEST_ROUTE_ID = "engel.wsl.self_test"
ENGEL_WSL_UBUNTU_RUNTIME_STATUS_ROUTE_ID = "engel.wsl_ubuntu.runtime_status"
ENGEL_WSL_UBUNTU_RUNTIME_FACTS_ROUTE_ID = "engel.wsl_ubuntu.runtime_facts"
ENGEL_WSL_UBUNTU_RUNTIME_SAFETY_ROUTE_ID = "engel.wsl_ubuntu.runtime_safety"
ENGEL_WSL_UBUNTU_RUNTIME_STAGE_2_ROUTE_ID = "engel.wsl_ubuntu.stage_2"
ENGEL_WSL_UBUNTU_RUNTIME_STAGE_3_ROUTE_ID = "engel.wsl_ubuntu.stage_3"
ENGELCODE_STATUS_ROUTE_ID = "engel.engelcode.status"
ENGELCODE_VERSION_ROUTE_ID = "engel.engelcode.version"
ENGELCODE_CRATES_ROUTE_ID = "engel.engelcode.crates"
ENGELCODE_BUILD_ROUTE_ID = "engel.engelcode.build"
ENGELCODE_INVOKE_ROUTE_ID = "engel.engelcode.invoke"
ENGELCODE_BRING_UP_ROUTE_ID = "engel.engelcode.bring_up"
ENGEL_MAIN_STATUS_ROUTE_ID = "engel.engel_main.status"
ENGEL_MAIN_VERSION_ROUTE_ID = "engel.engel_main.version"
ENGEL_MAIN_BINARIES_ROUTE_ID = "engel.engel_main.binaries"
ENGEL_MAIN_INSTALL_ROUTE_ID = "engel.engel_main.install"
ENGEL_MAIN_BUILD_ROUTE_ID = "engel.engel_main.build"
ENGEL_MAIN_DEV_START_ROUTE_ID = "engel.engel_main.dev_start"
ENGEL_MAIN_DEV_STOP_ROUTE_ID = "engel.engel_main.dev_stop"
ENGEL_MAIN_TAURI_BUILD_ROUTE_ID = "engel.engel_main.tauri_build"
ENGEL_MAIN_BRING_UP_ROUTE_ID = "engel.engel_main.bring_up"
ENGEL_LAN_STATUS_ROUTE_ID = "engel.engel_lan.status"
ENGEL_LAN_VERSION_ROUTE_ID = "engel.engel_lan.version"
ENGEL_LAN_CLI_HELP_ROUTE_ID = "engel.engel_lan.cli_help"
ENGEL_LAN_CLI_RECEIVE_START_ROUTE_ID = "engel.engel_lan.cli_receive_start"
ENGEL_LAN_CLI_RECEIVE_STOP_ROUTE_ID = "engel.engel_lan.cli_receive_stop"
ENGEL_LAN_APP_DEV_START_ROUTE_ID = "engel.engel_lan.app_dev_start"
ENGEL_LAN_APP_DEV_STOP_ROUTE_ID = "engel.engel_lan.app_dev_stop"
ENGEL_LAN_BRING_UP_ROUTE_ID = "engel.engel_lan.bring_up"
ENGEL_LAN_WORKERS_SCAN_ROUTE_ID = "engel.engel_lan.workers_scan"
ENGEL_LAN_WORKERS_STATUS_ROUTE_ID = "engel.engel_lan.workers_status"
ENGEL_LAN_WORKERS_ADD_ROUTE_ID = "engel.engel_lan.workers_add"
ENGEL_LAN_WORKERS_REMOVE_ROUTE_ID = "engel.engel_lan.workers_remove"
ENGEL_LAN_WORKER_DISPATCH_ROUTE_ID = "engel.engel_lan.worker_dispatch"
ENGEL_LAN_NETWORK_DEVICES_ROUTE_ID = "engel.engel_lan.network_devices"
ENGEL_ADB_WORKERS_STATUS_ROUTE_ID = "engel.android_workers.status"
ENGEL_ADB_WORKERS_PULL_ROUTE_ID = "engel.android_workers.pull_results"
ENGEL_ADB_WORKERS_PUSH_ROUTE_ID = "engel.android_workers.push_jobs"
ENGEL_ADB_WORKERS_RESULT_ROUTE_ID = "engel.android_workers.latest_result"
ENGEL_ADB_WORKERS_PROVISION_ROUTE_ID = "engel.android_workers.provision"
ENGEL_ADB_WORKERS_JOBS_ROUTE_ID = "engel.android_workers.jobs"
ENGEL_ADB_WORKERS_CREATE_JOB_ROUTE_ID = "engel.android_workers.create_job"
ENGEL_LAN_PAIRING_STATUS_ROUTE_ID = "engel.lan_pairing.status"
ENGEL_LAN_PAIRING_TOKEN_ROUTE_ID = "engel.lan_pairing.token"
ENGEL_MULTI_ANDROID_STATUS_ROUTE_ID = "engel.multi_android.status"
ENGEL_MULTI_ANDROID_LINKS_ROUTE_ID = "engel.multi_android.check_links"
ENGEL_WORKER_ASSIGNMENT_STATUS_ROUTE_ID = "engel.worker_assignment.status"
ENGEL_WORKER_ASSIGNMENT_JOBS_ROUTE_ID = "engel.worker_assignment.prepared_jobs"
ENGEL_RESULT_INTAKE_STATUS_ROUTE_ID = "engel.result_intake.status"
ENGEL_RESULT_INTAKE_LIST_ROUTE_ID = "engel.result_intake.list"
ENGEL_RUNTIME_READINESS_ROUTE_ID = "engel.runtime_readiness.status"
ENGEL_SYSTEM_INTEGRATION_STATUS_ROUTE_ID = "engel.system_integration.status"
ENGEL_CORE_V1_DASHBOARD_ROUTE_ID = "engel.core_v1.dashboard"
ENGEL_DAILY_CYCLE_STATUS_ROUTE_ID = "engel.daily_cycle.status"
ENGEL_CANDIDATE_REVIEW_DASHBOARD_ROUTE_ID = "engel.candidate_review.dashboard"
ENGEL_APPROVED_MEMORY_STATUS_ROUTE_ID = "engel.approved_memory.status"
ENGEL_APPROVED_MEMORY_CANDIDATES_ROUTE_ID = "engel.approved_memory.candidates"
ENGEL_BROWSER_QUEEN_STATUS_ROUTE_ID = "engel.browser_queen.status"
ENGEL_BROWSER_QUEEN_PHASE2_ROUTE_ID = "engel.browser_queen.phase2"
ENGEL_BROWSER_QUEEN_WORKBENCH_ROUTE_ID = "engel.browser_queen.workbench"
ENGEL_BROWSER_QUEEN_MVP_ROUTE_ID = "engel.browser_queen.mvp"
ENGEL_RESEARCH_OFFICE_STATUS_ROUTE_ID = "engel.research_office.status"
ENGEL_RESEARCH_OFFICE_MAP_ROUTE_ID = "engel.research_office.map"
ENGEL_RESEARCH_TOGGLE_STATUS_ROUTE_ID = "engel.research_toggle.status"
ENGEL_RESEARCH_TOGGLE_EXPLAIN_ROUTE_ID = "engel.research_toggle.explain"
ENGEL_SELF_LEARNING_STATUS_ROUTE_ID = "engel.self_learning.status"
ENGEL_PRODUCT_WORKBENCH_STATUS_ROUTE_ID = "engel.product_workbench.status"
ENGEL_PRODUCT_CYCLE_DASHBOARD_ROUTE_ID = "engel.product_cycle.dashboard"
ENGEL_CORE_CONTINUITY_STATUS_ROUTE_ID = "engel.core_continuity.status"
ENGEL_MEMORY_ARCHIVE_STATUS_ROUTE_ID = "engel.memory_archive.status"
ENGEL_MEMORY_CANDIDATE_REVIEW_ROUTE_ID = "engel.memory_candidate.review"
ENGEL_OFFLINE_MODEL_CONTRACT_ROUTE_ID = "engel.offline_model.contract"
ENGEL_PROGRESS_REPORT_ROUTE_ID = "engel.progress.report"
ENGEL_WHOLE_SYSTEM_AUDIT_ROUTE_ID = "engel.whole_system.audit"
ENGEL_COLONY_SIMULATION_ROUTE_ID = "engel.research.colony_simulation"
ENGEL_AI_BODY_STATUS_ROUTE_ID = "engel.ai_body.status"
ENGEL_WSL_BRIDGE_STATUS_ROUTE_ID = "engel.wsl_bridge.status"
ENGEL_PROTECTED_ACTIONS_LIST_ROUTE_ID = "engel.protected_actions.list"
ENGEL_PATCH_RECEIPTS_LIST_ROUTE_ID = "engel.patch_receipts.list"
ENGEL_LOWRISK_SELFFIX_STATUS_ROUTE_ID = "engel.lowrisk_selffix.status"
ENGEL_MEMORY_INVENTORY_ROUTE_ID = "engel.memory_inventory.status"
ENGEL_RUNTIME_PATH_CONFIG_ROUTE_ID = "engel.runtime_path.config"
ENGEL_LLAMA_COMPAT_MATRIX_ROUTE_ID = "engel.llama_cpp.compat_matrix"
ENGEL_RESEARCH_TO_FIX_SUMMARY_ROUTE_ID = "engel.research_to_fix.summary"
ENGEL_OFFLINE_SEED_LLM_ROUTE_ID = "engel.offline_seed_llm.status"
ENGEL_ARCHIVE_SHELF_REPORT_ROUTE_ID = "engel.archive_shelf.report"
ENGEL_TRUTHFULNESS_GUARD_ROUTE_ID = "engel.truthfulness_guard.status"
ENGEL_OUTSIDE_AI_BOUNDARY_ROUTE_ID = "engel.outside_ai_boundary.status"
ENGEL_PASSWORD_GATE_ROUTE_ID = "engel.password_gate.status"
ENGEL_COLONY_HIVE_MAP_ROUTE_ID = "engel.colony_hive.map"
ENGEL_COLONY_HIVE_STATUS_ROUTE_ID = "engel.colony_hive.status"
ENGEL_COLONY_HIVE_PERMISSIONS_ROUTE_ID = "engel.colony_hive.permissions"
ENGEL_COLONY_HIVE_QUEEN_LINKS_ROUTE_ID = "engel.colony_hive.queen_links"
ENGEL_COMMUNICATION_QUEEN_STATUS_ROUTE_ID = "engel.communication_queen.status"
ENGEL_ENGEL_MIND_CONNECTIONS_ROUTE_ID = "engel.engel_mind.connections"
ENGEL_FUTURE_UPGRADES_STATUS_ROUTE_ID = "engel.future_upgrades.status"
ENGEL_LONG_TERM_MEMORY_DRIVE_ROUTE_ID = "engel.long_term_memory.drive_status"
ENGEL_PRODUCT_CONTEXT_PACK_ROUTE_ID = "engel.product_context.pack"
ENGEL_GUIDED_LIBRARY_REVIEW_ROUTE_ID = "engel.guided_library_review.status"
ENGEL_HUMAN_REVIEW_DRAFT_SURFACE_ROUTE_ID = "engel.human_review_draft.status"
ENGEL_TRUSTED_MEMORY_TARGET_ROUTE_ID = "engel.trusted_memory_target.status"
ENGEL_SELF_FIX_RECEIPT_LIST_ROUTE_ID = "engel.self_fix.receipt_list"
ENGEL_INTENT_PLANNER_STATUS_ROUTE_ID = "engel.intent_planner.status"
ENGEL_INTENT_PLANNER_HELP_ROUTE_ID = "engel.intent_planner.help"
ENGEL_INTENT_BRIDGE_DOCS_ROUTE_ID = "engel.intent_bridge.docs"
ENGEL_INTENT_BRIDGE_STATUS_ROUTE_ID = "engel.intent_bridge.status"
ENGEL_INTENT_BRIDGE_LATEST_ROUTE_ID = "engel.intent_bridge.latest"
ENGEL_INTENT_BRIDGE_LIFT_ROUTE_ID = "engel.intent_bridge.lift"
ENGEL_SPEECH_SPC_DOCS_ROUTE_ID = "engel.speech_spc.docs"
ENGEL_SPEECH_SPC_STATUS_ROUTE_ID = "engel.speech_spc.status"
ENGEL_SPEECH_SPC_LATEST_ROUTE_ID = "engel.speech_spc.latest"
ENGEL_SPEECH_SPC_COMPILE_ROUTE_ID = "engel.speech_spc.compile"
ENGEL_MIPL_AGENT_DOCS_ROUTE_ID = "engel.mipl_agent.docs"
ENGEL_MIPL_AGENT_SKILLS_ROUTE_ID = "engel.mipl_agent.skills"
ENGEL_MIPL_AGENT_STATUS_ROUTE_ID = "engel.mipl_agent.status"
ENGEL_MIPL_AGENT_LIST_ROUTE_ID = "engel.mipl_agent.list"
ENGEL_MODEL_INTAKE_LIST_ROUTE_ID = "engel.model_intake.list"
ENGEL_MODEL_INTAKE_STATUS_ROUTE_ID = "engel.model_intake.status"
ENGEL_MODEL_REVIEW_APPROVAL_STATUS_ROUTE_ID = "engel.model_review_approval.status"
ENGEL_MODEL_REVIEW_APPROVAL_LIST_ROUTE_ID = "engel.model_review_approval.list"
ENGEL_NO_GENERATION_LOAD_CHECK_ROUTE_ID = "engel.no_generation_load_check.status"
ENGEL_OFFLINE_RUNTIME_DRY_RUN_STATUS_ROUTE_ID = "engel.offline_runtime_dry_run.status"
ENGEL_OFFLINE_RUNTIME_DRY_RUN_MODELS_ROUTE_ID = "engel.offline_runtime_dry_run.list_models"
ENGEL_LOCAL_RUNTIME_PATH_ROOTS_ROUTE_ID = "engel.local_runtime_path.roots"
ENGEL_BQ_PHASE4_CONTRACT_ROUTE_ID = "engel.browser_queen_phase4.contract"
ENGEL_BQ_PHASE5_CONTRACT_ROUTE_ID = "engel.browser_queen_phase5.contract"
ENGEL_CANDIDATE_LEARNING_STATUS_ROUTE_ID = "engel.candidate_learning.status"
ENGEL_CANDIDATE_REVIEW_DASHBOARD2_ROUTE_ID = "engel.candidate_review.dashboard2"
ENGEL_CANDIDATE_SET_APPROVAL_STATUS_ROUTE_ID = "engel.candidate_set_approval.status"
ENGEL_CHAT_EXPORT_INTAKE_STATUS_ROUTE_ID = "engel.chat_export_intake.status"
ENGEL_CHAT_EXPORT_INTAKE_LIST_ROUTE_ID = "engel.chat_export_intake.list"
ENGEL_CC_CANDIDATE_REVIEW_STATUS_ROUTE_ID = "engel.cc_candidate_review.status"
ENGEL_CC_FIX_CANDIDATE_INTAKE_STATUS_ROUTE_ID = "engel.cc_fix_candidate_intake.status"
ENGEL_CC_FIX_CANDIDATE_INTAKE_LIST_ROUTE_ID = "engel.cc_fix_candidate_intake.list"
ENGEL_CC_LOW_RISK_PATCH_RUNNER_ROUTE_ID = "engel.cc_low_risk_patch_runner.status"
ENGEL_CC_PASSWORD_GATE_INTEGRATION_ROUTE_ID = "engel.cc_password_gate_integration.status"
ENGEL_CC_PATCH_APPLICATION_GATE_STATUS_ROUTE_ID = "engel.cc_patch_application_gate.status"
ENGEL_CC_PATCH_APPLICATION_GATE_LIST_ROUTE_ID = "engel.cc_patch_application_gate.list"
ENGEL_CC_PATCH_APPLY_RECEIPT_STATUS_ROUTE_ID = "engel.cc_patch_apply_receipt.status"
ENGEL_CC_PATCH_APPLY_RECEIPT_LIST_ROUTE_ID = "engel.cc_patch_apply_receipt.list"
ENGEL_CC_PATCH_APPLY_DRY_RUN_STATUS_ROUTE_ID = "engel.cc_patch_apply_dry_run.status"
ENGEL_CC_PATCH_APPLY_DRY_RUN_LIST_ROUTE_ID = "engel.cc_patch_apply_dry_run.list"
ENGEL_CC_PATCH_BUNDLE_DRAFT_STATUS_ROUTE_ID = "engel.cc_patch_bundle_draft.status"
ENGEL_CC_PATCH_BUNDLE_DRAFT_LIST_ROUTE_ID = "engel.cc_patch_bundle_draft.list"
ENGEL_CC_PATCH_CLASS_ALLOWLIST_STATUS_ROUTE_ID = "engel.cc_patch_class_allowlist.status"
ENGEL_CC_PATCH_CLASS_ALLOWLIST_CLASSES_ROUTE_ID = "engel.cc_patch_class_allowlist.classes"
ENGEL_CC_PATCH_PLAN_PREVIEW_STATUS_ROUTE_ID = "engel.cc_patch_plan_preview.status"
ENGEL_CC_PATCH_PLAN_PREVIEW_LIST_ROUTE_ID = "engel.cc_patch_plan_preview.list"
ENGEL_CC_PATCH_STATUS_SURFACE_ROUTE_ID = "engel.cc_patch_status_surface.status"
ENGEL_CC_PROTECTED_PATCH_APPLY_ROUTE_ID = "engel.cc_protected_patch_apply.status"
ENGEL_CC_PROTECTED_PATCH_APPLY_COMMAND_ROUTE_ID = "engel.cc_protected_patch_apply.apply"
ENGEL_DAILY_CYCLE_RECEIPT_LIST_ROUTE_ID = "engel.daily_cycle.receipt_list"
ENGEL_EXTERNAL_MEMORY_ROOTS_ROUTE_ID = "engel.external_memory_roots.status"
ENGEL_FIX_CANDIDATE_QUEUE_STATUS_ROUTE_ID = "engel.fix_candidate_queue.status"
ENGEL_FIX_CANDIDATE_QUEUE_LIST_ROUTE_ID = "engel.fix_candidate_queue.list"
ENGEL_GUIDED_LIBRARY_DRAFT_REPORT_ROUTE_ID = "engel.guided_library_draft.report"
ENGEL_HUMAN_REVIEW_DRAFT_PREVIEW_ROUTE_ID = "engel.human_review_draft.preview"
ENGEL_LEARNING_JOB_QUEUE_STATUS_ROUTE_ID = "engel.learning_job_queue.status"
ENGEL_LEARNING_JOB_QUEUE_LIST_ROUTE_ID = "engel.learning_job_queue.list"
ENGEL_MEMORY_ROOTS_STORAGE_STATUS_ROUTE_ID = "engel.memory_roots_storage.status"
ENGEL_MEMORY_ROOTS_STORAGE_ROOTS_ROUTE_ID = "engel.memory_roots_storage.roots"
ENGEL_REMOTE_WORKER_APP_SCAFFOLD_ROUTE_ID = "engel.remote_worker_app_scaffold.status"
ENGEL_RESEARCH_TO_FIX_LOOP_ROUTE_ID = "engel.research_to_fix_loop.status"
ENGEL_RESEARCH_TOGGLE_WORKER_ROUTE_ID = "engel.research_toggle_worker.status"
ENGEL_SELF_LEARNING_CONTROLLER_ROUTE_ID = "engel.self_learning_controller.status"
ENGEL_SYSTEM_INTEGRATION_CHECK_LINKS_ROUTE_ID = "engel.system_integration.check_links"
ENGEL_TRAINING_TRUSTED_MEMORY_STATUS_ROUTE_ID = "engel.training_trusted_memory.status"
ENGEL_TRAINING_TRUSTED_MEMORY_PREVIEW_ROUTE_ID = "engel.training_trusted_memory.preview"
ENGEL_WHOLE_SYSTEM_AUDIT_STATUS_ROUTE_ID = "engel.whole_system_audit.status"
ENGEL_AI_GROWTH_FOLDER_STATUS_ROUTE_ID = "engel.ai_growth_dashboard.folder_status"
ENGEL_RUNTIME_READINESS_MODEL_ROUTE_ID = "engel.runtime_readiness.model_summary"
ENGEL_RUNTIME_READINESS_LIBRARY_ROUTE_ID = "engel.runtime_readiness.library_summary"
ENGEL_RUNTIME_READINESS_SAFETY_ROUTE_ID = "engel.runtime_readiness.safety_summary"
ENGEL_RUNTIME_READINESS_REMOTE_WORKER_ROUTE_ID = "engel.runtime_readiness.remote_worker_summary"
ENGEL_RUNTIME_READINESS_CODE_COMPANION_ROUTE_ID = "engel.runtime_readiness.code_companion_summary"
ENGEL_RUNTIME_READINESS_NEXT_ROUTE_ID = "engel.runtime_readiness.next_summary"
ENGEL_BOUNDED_LOCAL_CHAT_SMOKE_ROUTE_ID = "engel.bounded_local_chat_smoke.report"
ENGEL_SUB_ENGEL_STATUS_ROUTE_ID = "engel.sub_engel.status"
ENGEL_SUB_ENGEL_CREATE_JOB_ROUTE_ID = "engel.sub_engel.create_job"
ENGEL_SUB_ENGEL_RESULTS_ROUTE_ID = "engel.sub_engel.results"
ENGEL_CODE_LIST_LANGUAGES_ROUTE_ID = "engel.code.list_languages"
ENGEL_CODE_LIST_LOCAL_MODELS_ROUTE_ID = "engel.code.list_local_models"
ENGEL_CODE_GENERATE_MULTI_MODEL_ROUTE_ID = "engel.code.generate"
ENGEL_CODE_REFINE_ROUTE_ID = "engel.code.refine"
ENGEL_CODE_BATCH_GENERATE_ROUTE_ID = "engel.code.batch_generate"
ENGEL_CODE_WITH_COMPANION_ROUTE_ID = "engel.code.with_companion"
ENGEL_CODE_TRANSLATE_ROUTE_ID = "engel.code.translate"
ENGEL_CODE_BEST_AUTO_ROUTE_ID = "engel.code.best"
ENGEL_CODE_LIST_MODELS_FOR_LANG_ROUTE_ID = "engel.code.models_for_lang"
ENGEL_CODE_MULTI_CANDIDATES_ROUTE_ID = "engel.code.multi_candidates"
ENGEL_CODE_STAGE_SUB_ENGEL_ROUTE_ID = "engel.code.stage_sub_engel"
ENGEL_FIRST_LOCAL_RESPONSE_SMOKE_ROUTE_ID = "engel.first_local_response_smoke.report"
ENGEL_FIRST_LOCAL_RESPONSE_SMOKE_FIX_ROUTE_ID = "engel.first_local_response_smoke_fix.report"
ENGEL_OUTPUT_FILTER_TUNING_ROUTE_ID = "engel.output_filter_tuning.report"
ENGEL_LLAMA_SWAP_APPROVAL_ROUTE_ID = "engel.llama_swap_approval.report"
ENGEL_APPROVED_MEMORY_CONTEXT_BRIDGE_ROUTE_ID = "engel.approved_memory_context.bridge_report"
ENGEL_APPROVED_MEMORY_READBACK_BRIDGE_ROUTE_ID = "engel.approved_memory_readback.bridge_report"
ENGEL_LOCAL_CHAT_PROMPT_DRAFT_ROUTE_ID = "engel.local_chat_prompt_draft.report"
ENGEL_LOCAL_CHAT_SESSION_DRAFT_ROUTE_ID = "engel.local_chat_session_draft.report"
ENGEL_LOCAL_CHAT_MEMORY_REVIEW_BRIDGE_ROUTE_ID = "engel.local_chat_memory_review.bridge_report"
ENGEL_LOCAL_CHAT_SESSION_REVIEW_BRIDGE_ROUTE_ID = "engel.local_chat_session_review.bridge_report"
ENGEL_LOCAL_OPEN_CHAT_BRIDGE_ROUTE_ID = "engel.local_open_chat.bridge_report"
ENGEL_LOCAL_OPEN_CHAT_BOUNDED_RUN_REQUEST_ROUTE_ID = "engel.local_open_chat.bounded_run_request"
ENGEL_LOCAL_OPEN_CHAT_BOUNDED_RUN_EXECUTION_ROUTE_ID = "engel.local_open_chat.bounded_run_execution"
ENGEL_PERSISTENT_CHAT_PLAN_BRIDGE_ROUTE_ID = "engel.persistent_chat_plan.bridge_report"
ENGEL_PERSISTENT_CHAT_SESSION_STATUS_ROUTE_ID = "engel.persistent_chat_session.status"
ENGEL_PERSISTENT_CHAT_SESSION_START_ROUTE_ID = "engel.persistent_chat_session.start"
ENGEL_PERSISTENT_CHAT_SESSION_STOP_ROUTE_ID = "engel.persistent_chat_session.stop"
ENGEL_RUNTIME_CANDIDATE_ALT_ROUTE_ID = "engel.runtime_candidate_alt.report"
ENGEL_RUNTIME_CANDIDATE_FAILURE_ROUTE_ID = "engel.runtime_candidate_failure.report"
ENGEL_RUNTIME_CANDIDATE_VALIDATION_ROUTE_ID = "engel.runtime_candidate_validation.report"
ENGEL_LAN_PAIRING_STATUS2_ROUTE_ID = "engel.lan_pairing.status2"
ENGEL_LAN_PAIRING_TOKEN2_ROUTE_ID = "engel.lan_pairing.token2"
ENGEL_RESEARCH_OFFICE_QUEEN_LINKS_ROUTE_ID = "engel.research_office.queen_links"
ENGEL_RESEARCH_OFFICE_PERMISSIONS_ROUTE_ID = "engel.research_office.permissions"
ENGEL_CC_PRODUCT_CONTEXT_VIEW_ROUTE_ID = "engel.code_companion.product_context_view"
ENGEL_CC_CONTEXTUAL_TALK_ROUTE_ID = "engel.code_companion.contextual_talk"
ENGEL_EXTERNAL_MEMORY_ARCHIVE_SHELF_ROUTE_ID = "engel.external_memory.archive_shelf"
ENGEL_ROUTE_EXPLORER_DETAILS_ROUTE_ID = "engel.route_explorer.details"
MINOR_TOOLS_LIST_ROUTE_ID = "engel.minor_tools.list"
ENGEL_HUMANIZER_STATUS_ROUTE_ID = "engel.engel_humanizer.status"
ENGEL_HUMANIZER_FEATURES_ROUTE_ID = "engel.engel_humanizer.features"
ENGEL_HUMANIZER_DOCS_ROUTE_ID = "engel.engel_humanizer.docs"
ENGEL_NATIVE_AGENT_STATUS_ROUTE_ID = "engel.native_agent.status"
ENGEL_NATIVE_AGENT_FEATURES_ROUTE_ID = "engel.native_agent.features"
ENGEL_NATIVE_AGENT_DOCS_ROUTE_ID = "engel.native_agent.docs"
ENGEL_IDE_STATUS_ROUTE_ID = "engel.ide.status"
ENGEL_IDE_FEATURES_ROUTE_ID = "engel.ide.features"
ENGEL_IDE_DOCS_ROUTE_ID = "engel.ide.docs"
ENGEL_EVOLUTION_LAB_STATUS_ROUTE_ID = "engel.evolution_lab.status"
ENGEL_EVOLUTION_LAB_FEATURES_ROUTE_ID = "engel.evolution_lab.features"
ENGEL_EVOLUTION_LAB_DOCS_ROUTE_ID = "engel.evolution_lab.docs"
ENGEL_KNOWLEDGE_GRAPH_STATUS_ROUTE_ID = "engel.knowledge_graph.status"
ENGEL_KNOWLEDGE_GRAPH_FEATURES_ROUTE_ID = "engel.knowledge_graph.features"
ENGEL_KNOWLEDGE_GRAPH_DOCS_ROUTE_ID = "engel.knowledge_graph.docs"
ENGEL_EVOLUTION_ENGINE_STATUS_ROUTE_ID = "engel.evolution_engine.status"
ENGEL_EVOLUTION_ENGINE_FEATURES_ROUTE_ID = "engel.evolution_engine.features"
ENGEL_EVOLUTION_ENGINE_DOCS_ROUTE_ID = "engel.evolution_engine.docs"
ENGEL_AI_CONNECTORS_STATUS_ROUTE_ID = "engel.ai_connectors.status"
ENGEL_AI_CONNECTORS_ADAPTERS_ROUTE_ID = "engel.ai_connectors.adapters"
ENGEL_AI_CONNECTORS_BLUEPRINT_ROUTE_ID = "engel.ai_connectors.blueprint"
ENGEL_AI_CONNECTORS_RULES_ROUTE_ID = "engel.ai_connectors.rules"
ENGEL_AI_CONNECTORS_ZIP_AUDIT_ROUTE_ID = "engel.ai_connectors.zip_audit"
ENGEL_ACCOUNT_CONNECTOR_STATUS_ROUTE_ID = "engel.accounts.status"
ENGEL_ACCOUNT_CONNECTOR_PROVIDERS_ROUTE_ID = "engel.accounts.providers"
ENGEL_ACCOUNT_CONNECTOR_SETUP_ROUTE_ID = "engel.accounts.setup"
ENGEL_ACCOUNT_CONNECTOR_SAFETY_ROUTE_ID = "engel.accounts.safety"
ENGEL_ROUTE_EXPLORER_ROUTE_ID = "engel.routes.explorer"
ENGEL_ROUTE_SEARCH_ROUTE_ID = "engel.routes.search"
ENGEL_CAPABILITIES_LIST_ROUTE_ID = "engel.capabilities.list"
ENGEL_IDENTITY_ROUTE_ID = "engel.identity"
ENGEL_NATIVE_GATEWAY_START_ROUTE_ID = "engel.gateway.start"
ENGEL_NATIVE_GATEWAY_STOP_ROUTE_ID = "engel.gateway.stop"
ENGEL_NATIVE_GATEWAY_STATUS_ROUTE_ID = "engel.gateway.status"
ENGEL_NATIVE_CRON_LIST_ROUTE_ID = "engel.cron.list"
ENGEL_NATIVE_CRON_STATUS_ROUTE_ID = "engel.cron.status"
ENGEL_NATIVE_MEMORY_STATUS_ROUTE_ID = "engel.memory.status"
ENGEL_NATIVE_SKILLS_LIST_ROUTE_ID = "engel.skills.list"
ENGEL_SAVED_SKILLS_LIST_ROUTE_ID = "engel.skills.saved_list"
ENGEL_FEATURE_MAP_ROUTE_ID = "engel.feature_map.show"
ENGEL_FEATURE_MAP_DRAFT_PR_ROUTE_ID = "engel.feature_map.draft_pr"
ENGEL_NATIVE_SESSIONS_LIST_ROUTE_ID = "engel.sessions.list"
ENGEL_NATIVE_SESSIONS_STATS_ROUTE_ID = "engel.sessions.stats"
ENGEL_NATIVE_PLUGINS_LIST_ROUTE_ID = "engel.plugins.list"
ENGEL_NATIVE_TOOLSETS_ROUTE_ID = "engel.toolsets"
ENGEL_NATIVE_DOCTOR_ROUTE_ID = "engel.doctor"
ENGEL_NATIVE_TOP_STATUS_ROUTE_ID = "engel.top.status"
ENGEL_NATIVE_VERSION_ROUTE_ID = "engel.version"
ENGEL_NATIVE_INVOKE_ROUTE_ID = "engel.invoke"
ENGEL_NATIVE_RUNTIME_ROUTE_ID = "engel.native_runtime"
ENGEL_HUMANIZER_INVOKE_ROUTE_ID = "engel.engel_humanizer.invoke"
ENGEL_NATIVE_AGENT_LAUNCH_DASHBOARD_ROUTE_ID = "engel.native_agent.launch_dashboard"
ENGEL_NATIVE_AGENT_LAUNCH_AGENT_ROUTE_ID = "engel.native_agent.launch_agent"
ENGEL_IDE_INSTALL_TO_PROJECT_ROUTE_ID = "engel.ide.install_to_project"
ENGEL_EVOLUTION_LAB_HELP_ROUTE_ID = "engel.evolution_lab.help"
ENGEL_EVOLUTION_LAB_RUN_EXAMPLE_ROUTE_ID = "engel.evolution_lab.run_example"
ENGEL_KNOWLEDGE_GRAPH_HELP_ROUTE_ID = "engel.knowledge_graph.help"
ENGEL_KNOWLEDGE_GRAPH_BUILD_ROUTE_ID = "engel.knowledge_graph.build"
ENGEL_EVOLUTION_ENGINE_HELP_ROUTE_ID = "engel.evolution_engine.help"
ENGEL_EVOLUTION_ENGINE_RUN_ROUTE_ID = "engel.evolution_engine.run"

# Wave 2 — 10 new vendored modules (2026-05-24)
ENGEL_NEW_TOOLS_LIST_ROUTE_ID = "engel.new_tools.list"
ENGEL_CLI_ANYTHING_STATUS_ROUTE_ID = "engel.cli_anything.status"
ENGEL_CLI_ANYTHING_FEATURES_ROUTE_ID = "engel.cli_anything.features"
ENGEL_CLI_ANYTHING_DOCS_ROUTE_ID = "engel.cli_anything.docs"
ENGEL_GIT_NEXUS_STATUS_ROUTE_ID = "engel.git_nexus.status"
ENGEL_GIT_NEXUS_FEATURES_ROUTE_ID = "engel.git_nexus.features"
ENGEL_GIT_NEXUS_DOCS_ROUTE_ID = "engel.git_nexus.docs"
ENGEL_OCTOGENT_STATUS_ROUTE_ID = "engel.octogent.status"
ENGEL_OCTOGENT_FEATURES_ROUTE_ID = "engel.octogent.features"
ENGEL_OCTOGENT_DOCS_ROUTE_ID = "engel.octogent.docs"
ENGEL_OPEN_AGENTS_STATUS_ROUTE_ID = "engel.open_agents.status"
ENGEL_OPEN_AGENTS_FEATURES_ROUTE_ID = "engel.open_agents.features"
ENGEL_OPEN_AGENTS_DOCS_ROUTE_ID = "engel.open_agents.docs"
ENGEL_AIRLLM_STATUS_ROUTE_ID = "engel.airllm.status"
ENGEL_AIRLLM_FEATURES_ROUTE_ID = "engel.airllm.features"
ENGEL_AIRLLM_DOCS_ROUTE_ID = "engel.airllm.docs"
ENGEL_JARVIS_STATUS_ROUTE_ID = "engel.jarvis.status"
ENGEL_JARVIS_FEATURES_ROUTE_ID = "engel.jarvis.features"
ENGEL_JARVIS_DOCS_ROUTE_ID = "engel.jarvis.docs"
ENGEL_CHAT_UI_STATUS_ROUTE_ID = "engel.chat_ui.status"
ENGEL_CHAT_UI_FEATURES_ROUTE_ID = "engel.chat_ui.features"
ENGEL_CHAT_UI_DOCS_ROUTE_ID = "engel.chat_ui.docs"
ENGEL_AI_GALLERY_STATUS_ROUTE_ID = "engel.ai_gallery.status"
ENGEL_AI_GALLERY_FEATURES_ROUTE_ID = "engel.ai_gallery.features"
ENGEL_AI_GALLERY_DOCS_ROUTE_ID = "engel.ai_gallery.docs"
ENGEL_CLUSTER_STATUS_ROUTE_ID = "engel.cluster.status"
ENGEL_CLUSTER_FEATURES_ROUTE_ID = "engel.cluster.features"
ENGEL_CLUSTER_DOCS_ROUTE_ID = "engel.cluster.docs"
ENGEL_KNOWLEDGE_GRAPH_V2_STATUS_ROUTE_ID = "engel.knowledge_graph_v2.graphify8_status"
ENGEL_KNOWLEDGE_GRAPH_V2_FEATURES_ROUTE_ID = "engel.knowledge_graph_v2.features"
ENGEL_KNOWLEDGE_GRAPH_V2_DOCS_ROUTE_ID = "engel.knowledge_graph_v2.docs"
# Wave 2 extended routes — per-module install / list / action surfaces
ENGEL_GIT_NEXUS_PLUGINS_ROUTE_ID = "engel.git_nexus.plugins"
ENGEL_GIT_NEXUS_INSTALL_ROUTE_ID = "engel.git_nexus.install"
ENGEL_GIT_NEXUS_ANALYZE_ROUTE_ID = "engel.git_nexus.analyze"
ENGEL_CLI_ANYTHING_PLUGINS_ROUTE_ID = "engel.cli_anything.plugins"
ENGEL_CLI_ANYTHING_SEARCH_ROUTE_ID = "engel.cli_anything.search"
ENGEL_CLI_ANYTHING_INSTALL_ROUTE_ID = "engel.cli_anything.install"
ENGEL_OPEN_AGENTS_PACKAGES_ROUTE_ID = "engel.open_agents.packages"
ENGEL_OPEN_AGENTS_SKILLS_ROUTE_ID = "engel.open_agents.skills"
ENGEL_OPEN_AGENTS_INSTALL_ROUTE_ID = "engel.open_agents.install"
ENGEL_JARVIS_INSTALL_ROUTE_ID = "engel.jarvis.install"
ENGEL_JARVIS_START_ROUTE_ID = "engel.jarvis.start"
ENGEL_JARVIS_SKILLS_ROUTE_ID = "engel.jarvis.skills"
ENGEL_CHAT_UI_INSTALL_ROUTE_ID = "engel.chat_ui.install"
ENGEL_CHAT_UI_START_ROUTE_ID = "engel.chat_ui.start"
ENGEL_CHAT_UI_CONFIG_ROUTE_ID = "engel.chat_ui.config"
ENGEL_AI_GALLERY_DEMOS_ROUTE_ID = "engel.ai_gallery.demos"
ENGEL_AI_GALLERY_INSTALL_ROUTE_ID = "engel.ai_gallery.install"
ENGEL_AI_GALLERY_REQUIREMENTS_ROUTE_ID = "engel.ai_gallery.requirements"
ENGEL_CLUSTER_NODES_ROUTE_ID = "engel.cluster.nodes"
ENGEL_CLUSTER_INSTALL_ROUTE_ID = "engel.cluster.install"
ENGEL_CLUSTER_EXAMPLES_ROUTE_ID = "engel.cluster.examples"
# Agent Meeting Room — multi-agent collaboration space
ENGEL_MEETING_ROOM_STATUS_ROUTE_ID = "engel.meeting_room.status"
ENGEL_MEETING_ROOM_AGENDA_ROUTE_ID = "engel.meeting_room.agenda"
ENGEL_MEETING_ROOM_TRANSCRIPT_ROUTE_ID = "engel.meeting_room.transcript"
ENGEL_MEETING_ROOM_WHITEBOARD_ROUTE_ID = "engel.meeting_room.whiteboard"
ENGEL_MEETING_ROOM_AGENTS_ROUTE_ID = "engel.meeting_room.agents"
ENGEL_MEETING_ROOM_OPEN_ROUTE_ID = "engel.meeting_room.open"
ENGEL_MEETING_ROOM_CLOSE_ROUTE_ID = "engel.meeting_room.close"
ENGEL_MEETING_ROOM_ADD_NOTE_ROUTE_ID = "engel.meeting_room.add_note"
# Wave 3 — gstack + LFM2 family (2026-05-25)
ENGEL_WAVE3_LIST_ROUTE_ID = "engel.wave3.list"
ENGEL_GSTACK_STATUS_ROUTE_ID = "engel.gstack.status"
ENGEL_GSTACK_FEATURES_ROUTE_ID = "engel.gstack.features"
ENGEL_GSTACK_DOCS_ROUTE_ID = "engel.gstack.docs"
ENGEL_GSTACK_INSTALL_ROUTE_ID = "engel.gstack.install"
ENGEL_GSTACK_SKILLS_ROUTE_ID = "engel.gstack.skills"
ENGEL_LFM2_STATUS_ROUTE_ID = "engel.lfm2.status"
ENGEL_LFM2_FEATURES_ROUTE_ID = "engel.lfm2.features"
ENGEL_LFM2_DOCS_ROUTE_ID = "engel.lfm2.docs"
ENGEL_LFM2_INSTALL_ROUTE_ID = "engel.lfm2.install"
ENGEL_LFM2_EXAMPLE_ROUTE_ID = "engel.lfm2.example"
ENGEL_LFM2_CODE_REVIEW_STATUS_ROUTE_ID = "engel.lfm2_code_review.status"
ENGEL_LFM2_CODE_REVIEW_FEATURES_ROUTE_ID = "engel.lfm2_code_review.features"
ENGEL_LFM2_CODE_REVIEW_DOCS_ROUTE_ID = "engel.lfm2_code_review.docs"
ENGEL_LFM2_CODE_REVIEW_INSTALL_ROUTE_ID = "engel.lfm2_code_review.install"
ENGEL_LFM2_CODE_REVIEW_APPS_ROUTE_ID = "engel.lfm2_code_review.apps"
ENGEL_LFM2_MOBILE_STATUS_ROUTE_ID = "engel.lfm2_mobile.status"
ENGEL_LFM2_MOBILE_FEATURES_ROUTE_ID = "engel.lfm2_mobile.features"
ENGEL_LFM2_MOBILE_DOCS_ROUTE_ID = "engel.lfm2_mobile.docs"
ENGEL_LFM2_MOBILE_INSTALL_ROUTE_ID = "engel.lfm2_mobile.install"
ENGEL_LFM2_MOBILE_INFERENCE_ROUTE_ID = "engel.lfm2_mobile.inference"
ENGEL_LFM2_VISION_STATUS_ROUTE_ID = "engel.lfm2_vision.status"
ENGEL_LFM2_VISION_FEATURES_ROUTE_ID = "engel.lfm2_vision.features"
ENGEL_LFM2_VISION_DOCS_ROUTE_ID = "engel.lfm2_vision.docs"
ENGEL_LFM2_VISION_INSTALL_ROUTE_ID = "engel.lfm2_vision.install"
ENGEL_LFM2_VISION_START_ROUTE_ID = "engel.lfm2_vision.start"
# Wave 4 — Claw3D, CubeSandbox, DarwinEvolver, HermesAgent, LocalSend (2026-05-25)
ENGEL_WAVE4_LIST_ROUTE_ID = "engel.wave4.list"
ENGEL_CLAW3D_STATUS_ROUTE_ID = "engel.claw3d.status"
ENGEL_CLAW3D_FEATURES_ROUTE_ID = "engel.claw3d.features"
ENGEL_CLAW3D_DOCS_ROUTE_ID = "engel.claw3d.docs"
ENGEL_CLAW3D_INSTALL_ROUTE_ID = "engel.claw3d.install"
ENGEL_CLAW3D_START_ROUTE_ID = "engel.claw3d.start"
ENGEL_CUBESANDBOX_STATUS_ROUTE_ID = "engel.cubesandbox.status"
ENGEL_CUBESANDBOX_FEATURES_ROUTE_ID = "engel.cubesandbox.features"
ENGEL_CUBESANDBOX_DOCS_ROUTE_ID = "engel.cubesandbox.docs"
ENGEL_CUBESANDBOX_INSTALL_ROUTE_ID = "engel.cubesandbox.install"
ENGEL_DARWINIAN_EVOLVER_STATUS_ROUTE_ID = "engel.darwinian_evolver.status"
ENGEL_DARWINIAN_EVOLVER_FEATURES_ROUTE_ID = "engel.darwinian_evolver.features"
ENGEL_DARWINIAN_EVOLVER_DOCS_ROUTE_ID = "engel.darwinian_evolver.docs"
ENGEL_DARWINIAN_EVOLVER_INSTALL_ROUTE_ID = "engel.darwinian_evolver.install"
ENGEL_DARWINIAN_EVOLVER_RUN_ROUTE_ID = "engel.darwinian_evolver.run"
ENGEL_HERMES_AGENT_STATUS_ROUTE_ID = "engel.hermes_agent.status"
ENGEL_HERMES_AGENT_FEATURES_ROUTE_ID = "engel.hermes_agent.features"
ENGEL_HERMES_AGENT_DOCS_ROUTE_ID = "engel.hermes_agent.docs"
ENGEL_HERMES_AGENT_INSTALL_ROUTE_ID = "engel.hermes_agent.install"
ENGEL_HERMES_AGENT_START_ROUTE_ID = "engel.hermes_agent.start"
ENGEL_HERMES_AGENT_SKILLS_ROUTE_ID = "engel.hermes_agent.skills"
ENGEL_LOCALSEND_STATUS_ROUTE_ID = "engel.localsend.status"
ENGEL_LOCALSEND_FEATURES_ROUTE_ID = "engel.localsend.features"
ENGEL_LOCALSEND_DOCS_ROUTE_ID = "engel.localsend.docs"
ENGEL_LOCALSEND_INSTALL_ROUTE_ID = "engel.localsend.install"
# Architect Agent — Zones 1-5 (2026-05-25)
ENGEL_ARCHITECT_OVERVIEW_ROUTE_ID = "engel.architect.overview"
ENGEL_ARCHITECT_STATUS_ROUTE_ID = "engel.architect.status"
ENGEL_ARCHITECT_SECTIONS_ROUTE_ID = "engel.architect.sections"
ENGEL_ARCHITECT_SECTION_DETAIL_ROUTE_ID = "engel.architect.section_detail"
ENGEL_ARCHITECT_MODES_ROUTE_ID = "engel.architect.modes"
ENGEL_ARCHITECT_PRINCIPLES_ROUTE_ID = "engel.architect.principles"
ENGEL_ARCHITECT_FOUNDER_VOICE_ROUTE_ID = "engel.architect.founder_voice"
ENGEL_ARCHITECT_TRACKER_ROUTE_ID = "engel.architect.tracker_log"
ENGEL_ARCHITECT_BRIEFS_ROUTE_ID = "engel.architect.briefs"
ENGEL_ARCHITECT_ISSUE_LOG_ROUTE_ID = "engel.architect.issue_log"
ENGEL_ARCHITECT_CHANGE_MGMT_ROUTE_ID = "engel.architect.change_management"
ENGEL_ARCHITECT_FAILURE_RECOVERY_ROUTE_ID = "engel.architect.failure_recovery"
ENGEL_ARCHITECT_PLANNER_LIST_ROUTE_ID = "engel.architect.planner_list"
ENGEL_ARCHITECT_PLANNER_STATUS_ROUTE_ID = "engel.architect.planner_status"
ENGEL_ARCHITECT_APPROVAL_GATE_ROUTE_ID = "engel.architect.approval_gate"
ENGEL_ARCHITECT_LEGAL_SCAN_ROUTE_ID = "engel.architect.legal_scan"
ENGEL_ARCHITECT_PLAN_ROUTE_ID = "engel.architect.plan"
ENGEL_ARCHITECT_SPEC_ROUTE_ID = "engel.architect.spec"
ENGEL_ARCHITECT_PROMPT_ROUTE_ID = "engel.architect.prompt"
ENGEL_ARCHITECT_EXECUTOR_HANDOFF_ROUTE_ID = "engel.architect.executor_handoff"
ENGEL_ARCHITECT_OPEN_ISSUES_ROUTE_ID = "engel.architect.open_issues"
ENGEL_ARCHITECT_INTEGRATION_CHECK_ROUTE_ID = "engel.architect.integration_check"
ENGEL_ARCHITECT_START_NEW_ROUTE_ID = "engel.architect.start_new"
ENGEL_ARCHITECT_CONTINUE_ROUTE_ID = "engel.architect.continue"
ENGEL_ARCHITECT_CLOSE_ROUTE_ID = "engel.architect.close"
ENGEL_ARCHITECT_RUN_SECTION_ROUTE_ID = "engel.architect.run_section"
ENGEL_ARCHITECT_COMPLETE_SECTION_ROUTE_ID = "engel.architect.complete_section"
ENGEL_ARCHITECT_SKIP_SECTION_ROUTE_ID = "engel.architect.skip_section"
ENGEL_ARCHITECT_RETRY_SECTION_ROUTE_ID = "engel.architect.retry_section"
ENGEL_ARCHITECT_APPROVE_GATE_ROUTE_ID = "engel.architect.approve_gate"
ENGEL_ARCHITECT_REDIRECT_GATE_ROUTE_ID = "engel.architect.redirect_gate"
# AirLLM local inference bridge
ENGEL_AIRLLM_BRIDGE_STATUS_ROUTE_ID = "engel.airllm.bridge_status"
ENGEL_AIRLLM_LOAD_ROUTE_ID = "engel.airllm.load"
ENGEL_AIRLLM_GENERATE_ROUTE_ID = "engel.airllm.generate"
ENGEL_AIRLLM_UNLOAD_ROUTE_ID = "engel.airllm.unload"
# Overnight research runner — read-only status view
ENGEL_OVERNIGHT_STATUS_ROUTE_ID = "engel.overnight.status"
# Talk-to-Code — Engel explains its own source modules
ENGEL_TALK_TO_CODE_LIST_ROUTE_ID = "engel.talk_to_code.list"
ENGEL_TALK_TO_CODE_EXPLAIN_ROUTE_ID = "engel.talk_to_code.explain"
# Local Model Manager — list/load/unload larger GGUF models
ENGEL_MODELS_LIST_ROUTE_ID = "engel.models.list"
ENGEL_MODELS_STATUS_ROUTE_ID = "engel.models.status"
ENGEL_MODELS_LOAD_ROUTE_ID = "engel.models.load"
ENGEL_MODELS_UNLOAD_ROUTE_ID = "engel.models.unload"
ENGEL_MODELS_INFO_ROUTE_ID = "engel.models.info"
# Octogent swarm UI — install / start / stop
ENGEL_OCTOGENT_SWARM_STATUS_ROUTE_ID = "engel.octogent.swarm_status"
ENGEL_OCTOGENT_INSTALL_ROUTE_ID = "engel.octogent.install"
ENGEL_OCTOGENT_START_ROUTE_ID = "engel.octogent.start"
ENGEL_OCTOGENT_STOP_ROUTE_ID = "engel.octogent.stop"
# Research brain + overnight loop status
ENGEL_RESEARCH_OVERVIEW_ROUTE_ID = "engel.research.overview"
ENGEL_RESEARCH_BRAIN_STATUS_ROUTE_ID = "engel.research.brain_status"
ENGEL_RESEARCH_QUEUE_ROUTE_ID = "engel.research.queue"
ENGEL_RESEARCH_NEXT_TOPIC_ROUTE_ID = "engel.research.next_topic"
ENGEL_RESEARCH_DIGEST_ROUTE_ID = "engel.research.digest"
ENGEL_RESEARCH_TOGGLE_ROUTE_ID = "engel.research.toggle_status"
ENGEL_HIVE_MIND_STATUS_ROUTE_ID = "engel.hive_mind.status"
ENGEL_WORKER_ANTS_STATUS_ROUTE_ID = "engel.worker_ants.status"
ENGEL_COLONY_STATUS_ROUTE_ID = "engel.colony.status"
ENGEL_COLONY_SAFETY_ROUTE_ID = "engel.colony.safety"
ENGEL_SWARM_TRAILS_ROUTE_ID = "engel.swarm_trails.status"
ENGEL_LEARNING_PROPOSALS_ROUTE_ID = "engel.learning.proposals"
ENGEL_LESSON_CANDIDATES_ROUTE_ID = "engel.learning.lesson_candidates"
ENGEL_OVERNIGHT_LOOP_STATUS_ROUTE_ID = "engel.overnight.loop_status"
ENGEL_OVERNIGHT_LOOP_CLEANUP_ROUTE_ID = "engel.overnight.loop_cleanup"
# Growth dashboard
ENGEL_GROWTH_DASHBOARD_ROUTE_ID = "engel.growth.dashboard"
# Knowledge Graph V2 (engel_graphify)
ENGEL_KG_V2_STATUS_ROUTE_ID = "engel.knowledge_graph_v2.status"
ENGEL_KG_V2_GLOBAL_ROUTE_ID = "engel.knowledge_graph_v2.global_graph"
ENGEL_KG_V2_SCAN_ROUTE_ID = "engel.knowledge_graph_v2.scan"
ENGEL_KG_V2_HELP_ROUTE_ID = "engel.knowledge_graph_v2.help"
ENGEL_KG_V2_INSTALL_ROUTE_ID = "engel.knowledge_graph_v2.install"
ENGEL_KG_V2_BUILD_CORE_ROUTE_ID = "engel.knowledge_graph_v2.build_core"
ENGEL_KG_V2_ANALYZE_CORE_ROUTE_ID = "engel.knowledge_graph_v2.analyze_core"
ENGEL_KG_V2_SEARCH_ROUTE_ID = "engel.knowledge_graph_v2.search"
ENGEL_KG_V2_NEIGHBORS_ROUTE_ID = "engel.knowledge_graph_v2.neighbors"
ENGEL_KG_V2_COMMUNITIES_ROUTE_ID = "engel.knowledge_graph_v2.communities"
# Workspace verifiers (static checks, no mutations)
ENGEL_VERIFY_LOCAL_LLM_GROWTH_ROUTE_ID = "engel.verify.local_llm_growth"
ENGEL_VERIFY_PROMOTION_ROUTE_ID = "engel.verify.promotion"
ENGEL_VERIFY_BRAIN_PROVIDER_ROUTE_ID = "engel.verify.brain_provider"
ENGEL_VERIFY_LLM_TEACHING_ROUTE_ID = "engel.verify.llm_teaching"
ENGEL_VERIFY_STYLE_GUIDE_ROUTE_ID = "engel.verify.style_guide"
ENGEL_VERIFY_ALL_ROUTE_ID = "engel.verify.all"
# External memory drives E/F/G
ENGEL_EXT_MEM_STATUS_ROUTE_ID = "engel.external_memory.status"
ENGEL_EXT_MEM_MODELS_ROUTE_ID = "engel.external_memory.models"
ENGEL_EXT_MEM_RUNTIMES_ROUTE_ID = "engel.external_memory.runtimes"
ENGEL_EXT_MEM_E_DRIVE_ROUTE_ID = "engel.external_memory.e_drive"
ENGEL_EXT_MEM_F_DRIVE_ROUTE_ID = "engel.external_memory.f_drive"
ENGEL_EXT_MEM_G_DRIVE_ROUTE_ID = "engel.external_memory.g_drive"
ENGEL_VAULT_MIGRATION_STATUS_ROUTE_ID = "engel.vault_migration.status"
ENGEL_VAULT_MIGRATION_PLAN_ROUTE_ID = "engel.vault_migration.plan"
ENGEL_MAIN_SERVER_MERGE_STATUS_ROUTE_ID = "engel.main_server_merge.status"
# llama-cli subprocess inference backend (F: drive CPU/CUDA builds)
ENGEL_LLAMA_CLI_STATUS_ROUTE_ID = "engel.llama_cli.status"
ENGEL_LLAMA_CLI_PREFLIGHT_ROUTE_ID = "engel.llama_cli.preflight"
ENGEL_LLAMA_CLI_RUN_ROUTE_ID = "engel.llama_cli.run"
ENGEL_LLAMA_CLI_BENCHMARK_ROUTE_ID = "engel.llama_cli.benchmark"
ENGEL_LLAMA_CLI_RUN_SLUG_ROUTE_ID = "engel.llama_cli.run_slug"
ENGEL_LLAMA_CLI_GPU_BENCHMARK_ROUTE_ID = "engel.llama_cli.gpu_benchmark"
ENGEL_LLAMA_CLI_GPU_INFO_ROUTE_ID = "engel.llama_cli.gpu_info"
ENGEL_LLAMA_CLI_COMPARE_ROUTE_ID = "engel.llama_cli.compare"
ENGEL_LLAMA_CLI_EXPLAIN_ROUTE_ID = "engel.llama_cli.explain"
ENGEL_LOCAL_LLM_DASHBOARD_ROUTE_ID = "engel.llama_cli.dashboard"
ENGEL_LOCAL_LLM_DOCTOR_ROUTE_ID = "engel.llama_cli.doctor"
# Darwin evolution lab framework status
ENGEL_DARWIN_STATUS_ROUTE_ID = "engel.evolution_lab.darwin_status"
ENGEL_DARWIN_PROBLEMS_ROUTE_ID = "engel.evolution_lab.darwin_problems"
ENGEL_DARWIN_FRAMEWORK_ROUTE_ID = "engel.evolution_lab.darwin_framework"
ENGEL_DARWIN_LOG_ROUTE_ID = "engel.evolution_lab.darwin_learning_log"
ENGEL_DARWIN_LOCAL_STATUS_ROUTE_ID = "engel.evolution_lab.darwin_local_status"
ENGEL_DARWIN_LOCAL_PARROT_RUN_ROUTE_ID = "engel.evolution_lab.darwin_local_parrot_run"


@dataclass(frozen=True)
class EngelAIUpdateRoute:
    route_id: str
    label: str
    target_module: str
    target_function: str
    aliases: tuple[str, ...]
    read_only: bool = True
    status_only: bool = True
    safe_for_ai_route: bool = True
    no_memory_promotion: bool = True
    no_trusted_memory_write: bool = True
    no_fix_apply: bool = True
    no_queue_route_mutation: bool = True
    no_archive_mutation: bool = True
    no_provider_model_network: bool = True
    no_background_worker: bool = True
    no_visible_ui_change: bool = True


ENGEL_CAPABILITY_SEARCH_ROUTE_ID = "engel.capability.search"
ENGEL_SCRIPT_DOCS_ROUTE_ID = "engel.script.docs"
ENGEL_SCRIPT_EXAMPLES_ROUTE_ID = "engel.script.examples"
ENGEL_SCRIPT_VALIDATE_ROUTE_ID = "engel.script.validate"
ENGEL_SCRIPT_RUN_ROUTE_ID = "engel.script.run"
ENGEL_FORGE_DOCS_ROUTE_ID = "engel.forge.docs"
ENGEL_FORGE_CODE_ROUTE_ID = "engel.forge.code"
ENGEL_FORGE_STATUS_ROUTE_ID = "engel.forge.status"
ENGEL_CONDUCTOR_DOCS_ROUTE_ID = "engel.conductor.docs"
ENGEL_CONDUCTOR_GOAL_ROUTE_ID = "engel.conductor.goal"
ENGEL_CONDUCTOR_STATUS_ROUTE_ID = "engel.conductor.status"
ENGEL_ORCHESTRA_DOCS_ROUTE_ID = "engel.orchestra.docs"
ENGEL_ORCHESTRA_RUN_ROUTE_ID = "engel.orchestra.run"
ENGEL_ORCHESTRA_STATUS_ROUTE_ID = "engel.orchestra.status"
ENGEL_AGENT_KERNEL_DOCS_ROUTE_ID = "engel.agent_kernel.docs"
ENGEL_AGENT_KERNEL_RUN_ROUTE_ID = "engel.agent_kernel.run"
ENGEL_AGENT_KERNEL_STATUS_ROUTE_ID = "engel.agent_kernel.status"
ENGEL_GROK_BOT_DOCS_ROUTE_ID = "engel.grok_bot.docs"
ENGEL_GROK_BOT_STATUS_ROUTE_ID = "engel.grok_bot.status"
ENGEL_GROK_BOT_LIST_ROUTE_ID = "engel.grok_bot.list"
ENGEL_GROK_BOT_COMPUTER_ROUTE_ID = "engel.grok_bot.computer"
ENGEL_GROK_BOT_APPROVALS_ROUTE_ID = "engel.grok_bot.approvals"
ENGEL_GROK_BOT_CREATE_ROUTE_ID = "engel.grok_bot.create"
ENGEL_GROK_BOT_MESSAGE_ROUTE_ID = "engel.grok_bot.message"
ENGEL_GROK_BOT_HANDOFF_ROUTE_ID = "engel.grok_bot.handoff"

ENGEL_GROK_BOT_PRESENCE_ROUTE_ID = "engel.grok_bot.presence"
ENGEL_ROUTINES_DOCS_ROUTE_ID = "engel.routines.docs"
ENGEL_ROUTINES_STATUS_ROUTE_ID = "engel.routines.status"
ENGEL_ROUTINES_LIST_ROUTE_ID = "engel.routines.list"
ENGEL_ROUTINES_CREATE_ROUTE_ID = "engel.routines.create"
ENGEL_ROUTINES_DUE_ROUTE_ID = "engel.routines.due"
ENGEL_ROUTINES_STAGE_ROUTE_ID = "engel.routines.stage"
ENGEL_ROUTINES_PAUSE_ROUTE_ID = "engel.routines.pause"
ENGEL_COMPACTION_DOCS_ROUTE_ID = "engel.compaction.docs"
ENGEL_COMPACTION_STATUS_ROUTE_ID = "engel.compaction.status"
ENGEL_COMPACTION_COMPACT_ROUTE_ID = "engel.compaction.compact"
ENGEL_MCP_ALLOWLIST_DOCS_ROUTE_ID = "engel.mcp_allowlist.docs"
ENGEL_MCP_ALLOWLIST_STATUS_ROUTE_ID = "engel.mcp_allowlist.status"
ENGEL_MCP_ALLOWLIST_LIST_ROUTE_ID = "engel.mcp_allowlist.list"
ENGEL_ICM_DOCS_ROUTE_ID = "engel.icm.docs"
ENGEL_ICM_STATUS_ROUTE_ID = "engel.icm.status"
ENGEL_ICM_AUDIT_ROUTE_ID = "engel.icm.audit"
ENGEL_ICM_WORKSPACE_ROUTE_ID = "engel.icm.workspace"
ENGEL_ICM_OUTPUTS_ROUTE_ID = "engel.icm.outputs"
ENGEL_ICM_ROUTING_ROUTE_ID = "engel.icm.routing"
ENGEL_GRAPH_STUDIO_STATUS_ROUTE_ID = "engel.graph_studio.status"
ENGEL_GRAPH_STUDIO_OPEN_ROUTE_ID = "engel.graph_studio.open"
ENGEL_GRAPH_STUDIO_NEW_ROUTE_ID = "engel.graph_studio.new"
ENGEL_GRAPH_STUDIO_LIST_ROUTE_ID = "engel.graph_studio.list"
ENGEL_GROVER_STATUS_ROUTE_ID = "engel.grover.status"
ENGEL_GROVER_EXPLAIN_ROUTE_ID = "engel.grover.explain"
ENGEL_GROVER_SEARCH_ROUTE_ID = "engel.grover.search"
ENGEL_GROVER_CRYPTO_ROUTE_ID = "engel.grover.crypto"
ENGEL_NEXT_STAGE_STATUS_ROUTE_ID = "engel.next_stage.status"
ENGEL_NEXT_STAGE_INVENTORY_ROUTE_ID = "engel.next_stage.inventory"
ENGEL_NEXT_STAGE_COMPANION_ROUTE_ID = "engel.next_stage.companion"
ENGEL_NEXT_STAGE_SAFETY_ROUTE_ID = "engel.next_stage.safety"
ENGEL_WIKI_ONE_STATUS_ROUTE_ID = "engel.wiki_one.status"
ENGEL_WIKI_ONE_JOURNAL_ROUTE_ID = "engel.wiki_one.journal"
ENGEL_WIKI_ONE_UPDATE_ROUTE_ID = "engel.wiki_one.update"


UPDATE_ROUTES: tuple[EngelAIUpdateRoute, ...] = (
    EngelAIUpdateRoute(
        route_id=PROGRESS_ROUTE_ID,
        label="Engel progress dashboard status",
        target_module="engel_progress_dashboard",
        target_function="render_progress_status",
        aliases=(
            "what is engel status",
            "show engel status",
            "engel status",
            "show progress dashboard",
            "progress dashboard",
            "show current blockers",
            "current blockers",
            "what is blocking engel",
            "feature expansion status",
            "update status",
            "progress update",
            "what changed recently",
            "what is the current baseline",
            "is engel clean",
            "is the verifier clean",
            "verifier status",
            "show verifier status",
            "codex status",
            "show codex status",
            "full verifier status",
            "what passed",
            "what failed",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=MEMORY_CANDIDATE_ROUTE_ID,
        label="Engel memory candidate inventory status",
        target_module="engel_memory_candidate_inventory",
        target_function="render_inventory_status",
        aliases=(
            "check memory candidates",
            "memory candidate inventory",
            "show memory candidate inventory",
            "memory candidates status",
            "compare memory candidates",
            "memory candidate count",
            "are memory candidates clean",
            "check candidate mismatch",
            "candidate mismatch status",
            "show candidate approval status",
            "memory candidate approval status",
            "why did candidate count fail",
            "check the 24/24 memory candidates",
            "candidate set approval status",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ARCHIVE_SHELF_ROUTE_ID,
        label="Engel archive shelf manager status",
        target_module="engel_archive_shelf_manager",
        target_function="render_archive_shelf_status",
        aliases=(
            "check archive shelves",
            "archive shelf status",
            "external memory status",
            "external memory roots",
            "where is engel memory",
            "where are engel archives",
            "what archive drives are available",
            "show memory shelves",
            "check external memory roots",
            "is i drive required",
            "is i:\\engel_app_memory required",
            "is i:\\engel_app_memory still needed",
            "show e f g archive shelves",
            "show project local memory fallback",
            "long term archive status",
            "cold archive status",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_AGENT_STATUS_ROUTE_ID,
        label="Engel Agent toolset and skill inventory",
        target_module="engel_engel_agent_runner",
        target_function="render_engel_agent_status",
        aliases=(
            "engel agent status",
            "engel agent tools",
            "engel agent toolset",
            "engel agent toolsets",
            "list engel agent tools",
            "list engel agent toolsets",
            "show engel agent",
            "show engel agent status",
            "show engel agent tools",
            "show engel agent toolsets",
            "engel agent help",
            "engel agent inventory",
            "what can engel agent do",
            "what tools does engel agent have",
            "agent tools",
            "agent status",
            "agent toolset",
            "agent toolsets",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_AGENT_INVOKE_ROUTE_ID,
        label="Engel Agent task invocation (autonomous, may run background work)",
        target_module="engel_engel_agent_runner",
        target_function="render_engel_agent_invocation",
        aliases=(
            # Empty payloads — the trigger PREFIXES that carry the actual task
            # text are recognised by ``engel_communication_router``; these exact
            # aliases just print usage if invoked alone.
            "engel agent run",
            "engel agent do",
            "engel agent task",
            "agent run",
            "agent do",
            "agent task",
            "ask engel agent",
            "tell engel agent",
            "run engel agent",
        ),
        read_only=False,
        status_only=False,
        no_memory_promotion=False,
        no_trusted_memory_write=False,
        no_fix_apply=False,
        no_archive_mutation=False,
        no_provider_model_network=False,
        no_background_worker=False,
        no_visible_ui_change=False,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_AGENT_DOCTOR_ROUTE_ID,
        label="Engel Agent doctor (config + dependency health check)",
        target_module="engel_engel_agent_runner",
        target_function="render_engel_agent_doctor",
        aliases=(
            "engel agent doctor",
            "agent doctor",
            "engel doctor",
            "doctor engel agent",
            "engel agent health",
            "engel agent diagnostics",
            "check engel agent config",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_AGENT_VERSION_ROUTE_ID,
        label="Engel Agent version",
        target_module="engel_engel_agent_runner",
        target_function="render_engel_agent_version",
        aliases=(
            "engel agent version",
            "agent version",
            "engel version",
            "what version is engel agent",
            "show engel agent version",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_AGENT_TOOLSETS_ROUTE_ID,
        label="Engel Agent toolset enumeration",
        target_module="engel_engel_agent_runner",
        target_function="render_engel_agent_toolsets",
        aliases=(
            "engel agent toolsets list",
            "engel agent list toolsets",
            "list engel agent toolsets",
            "agent toolsets list",
            "engel agent show toolsets",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_AGENT_GATEWAY_STATUS_ROUTE_ID,
        label="Engel Agent gateway status (messaging + cron service)",
        target_module="engel_engel_agent_runner",
        target_function="render_engel_agent_gateway_status",
        aliases=(
            "engel agent gateway status",
            "engel gateway status",
            "agent gateway status",
            "is engel gateway running",
            "show engel agent gateway",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_AGENT_GATEWAY_START_ROUTE_ID,
        label="Engel Agent gateway start (messaging + cron service)",
        target_module="engel_engel_agent_runner",
        target_function="render_engel_agent_gateway_start",
        aliases=(
            "engel agent gateway start",
            "engel gateway start",
            "agent gateway start",
            "start engel gateway",
            "start engel agent gateway",
        ),
        read_only=False,
        status_only=False,
        no_background_worker=False,
        no_provider_model_network=False,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_AGENT_GATEWAY_STOP_ROUTE_ID,
        label="Engel Agent gateway stop",
        target_module="engel_engel_agent_runner",
        target_function="render_engel_agent_gateway_stop",
        aliases=(
            "engel agent gateway stop",
            "engel gateway stop",
            "agent gateway stop",
            "stop engel gateway",
            "stop engel agent gateway",
        ),
        read_only=False,
        status_only=False,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_AGENT_CRON_STATUS_ROUTE_ID,
        label="Engel Agent cron scheduler status",
        target_module="engel_engel_agent_runner",
        target_function="render_engel_agent_cron_status",
        aliases=(
            "engel agent cron status",
            "engel cron status",
            "agent cron status",
            "is engel cron running",
            "show engel agent cron",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_AGENT_CRON_LIST_ROUTE_ID,
        label="Engel Agent cron job listing",
        target_module="engel_engel_agent_runner",
        target_function="render_engel_agent_cron_list",
        aliases=(
            "engel agent cron list",
            "engel cron list",
            "agent cron list",
            "list engel cron jobs",
            "show engel agent cron jobs",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_AGENT_MEMORY_STATUS_ROUTE_ID,
        label="Engel Agent memory provider status",
        target_module="engel_engel_agent_runner",
        target_function="render_engel_agent_memory_status",
        aliases=(
            "engel agent memory status",
            "engel memory status",
            "agent memory status",
            "show engel agent memory",
            "memory provider status",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_AGENT_SKILLS_LIST_ROUTE_ID,
        label="Engel Agent installed skills list",
        target_module="engel_engel_agent_runner",
        target_function="render_engel_agent_skills_list",
        aliases=(
            "engel agent skills list",
            "engel agent skills",
            "engel skills list",
            "list engel agent skills",
            "show engel agent skills",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_AGENT_SESSIONS_LIST_ROUTE_ID,
        label="Engel Agent session listing",
        target_module="engel_engel_agent_runner",
        target_function="render_engel_agent_sessions_list",
        aliases=(
            "engel agent sessions list",
            "engel agent sessions",
            "engel sessions list",
            "list engel agent sessions",
            "show engel agent sessions",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_AGENT_SESSIONS_STATS_ROUTE_ID,
        label="Engel Agent session statistics",
        target_module="engel_engel_agent_runner",
        target_function="render_engel_agent_sessions_stats",
        aliases=(
            "engel agent sessions stats",
            "engel sessions stats",
            "engel agent session stats",
            "show engel agent session stats",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_AGENT_PLUGINS_LIST_ROUTE_ID,
        label="Engel Agent installed plugins list",
        target_module="engel_engel_agent_runner",
        target_function="render_engel_agent_plugins_list",
        aliases=(
            "engel agent plugins list",
            "engel agent plugins",
            "engel plugins list",
            "list engel agent plugins",
            "show engel agent plugins",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_AGENT_TOP_STATUS_ROUTE_ID,
        label="Engel Agent top-level component status",
        target_module="engel_engel_agent_runner",
        target_function="render_engel_agent_top_status",
        aliases=(
            "engel agent top status",
            "engel agent components",
            "agent components status",
            "engel agent component health",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL3D_STATUS_ROUTE_ID,
        label="Engel3D office runtime status",
        target_module="engel_engel3d_runner",
        target_function="render_engel3d_status",
        aliases=(
            "engel3d status",
            "engel3d office status",
            "engel 3d status",
            "engel 3d office status",
            "show engel3d office",
            "show engel 3d office",
            "engel3d office",
            "engel 3d office",
            "engel3d health",
            "engel 3d health",
            "engel3d office health",
            "is engel3d running",
            "is engel 3d running",
            "engel3d server status",
            "where is engel3d",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL3D_START_ROUTE_ID,
        label="Engel3D office dev server start (detached background)",
        target_module="engel_engel3d_runner",
        target_function="render_engel3d_start",
        aliases=(
            "engel3d start",
            "engel3d office start",
            "engel 3d start",
            "engel 3d office start",
            "start engel3d",
            "start engel 3d",
            "start engel3d office",
            "start engel 3d office",
            "launch engel3d",
            "launch engel 3d",
            "launch engel3d office",
            "open engel3d office",
            "open engel 3d office",
            "run engel3d office",
        ),
        read_only=False,
        status_only=False,
        no_memory_promotion=False,
        no_trusted_memory_write=False,
        no_fix_apply=False,
        no_archive_mutation=False,
        no_provider_model_network=False,
        no_background_worker=False,
        no_visible_ui_change=False,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL3D_STOP_ROUTE_ID,
        label="Engel3D office dev server stop",
        target_module="engel_engel3d_runner",
        target_function="render_engel3d_stop",
        aliases=(
            "engel3d stop",
            "engel3d office stop",
            "engel 3d stop",
            "engel 3d office stop",
            "stop engel3d",
            "stop engel 3d",
            "stop engel3d office",
            "stop engel 3d office",
            "close engel3d office",
            "shutdown engel3d",
            "kill engel3d",
        ),
        read_only=False,
        status_only=False,
        no_visible_ui_change=False,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL3D_BUILD_ROUTE_ID,
        label="Engel3D office production build (npm install + next build)",
        target_module="engel_engel3d_runner",
        target_function="render_engel3d_build",
        aliases=(
            "engel3d build",
            "engel3d office build",
            "engel 3d build",
            "engel 3d office build",
            "build engel3d",
            "build engel 3d",
            "build engel3d office",
            "build engel 3d office",
            "rebuild engel3d",
            "rebuild engel 3d",
            "install engel3d",
            "install engel 3d",
            "install engel3d deps",
        ),
        read_only=False,
        status_only=False,
        no_memory_promotion=False,
        no_trusted_memory_write=False,
        no_fix_apply=False,
        no_archive_mutation=False,
        no_provider_model_network=False,
        no_background_worker=False,
        no_visible_ui_change=False,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_SANDBOX_STATUS_ROUTE_ID,
        label="Engel Sandbox server health + cluster overview",
        target_module="engel_engel_sandbox_runner",
        target_function="render_engel_sandbox_status",
        aliases=(
            "engel sandbox status",
            "engel sandbox health",
            "is engel sandbox running",
            "engel sandbox server status",
            "engelsandbox status",
            "engel hypervisor status",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_SANDBOX_NODES_ROUTE_ID,
        label="Engel Sandbox cluster node listing",
        target_module="engel_engel_sandbox_runner",
        target_function="render_engel_sandbox_nodes",
        aliases=(
            "engel sandbox nodes",
            "engel sandbox cluster nodes",
            "list engel sandbox nodes",
            "show engel sandbox nodes",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_SANDBOX_LIST_ROUTE_ID,
        label="Engel Sandbox active sandboxes (E2B-compatible API)",
        target_module="engel_engel_sandbox_runner",
        target_function="render_engel_sandbox_list",
        aliases=(
            "engel sandbox list",
            "list engel sandboxes",
            "show engel sandboxes",
            "engel sandbox list active",
            "engel active sandboxes",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_SANDBOX_CREATE_ROUTE_ID,
        label="Engel Sandbox create new sandbox (E2B-compatible)",
        target_module="engel_engel_sandbox_runner",
        target_function="render_engel_sandbox_create",
        aliases=(
            "engel sandbox create",
            "create engel sandbox",
            "new engel sandbox",
            "spawn engel sandbox",
        ),
        read_only=False,
        status_only=False,
        no_visible_ui_change=False,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_SANDBOX_DELETE_ROUTE_ID,
        label="Engel Sandbox delete sandbox by id",
        target_module="engel_engel_sandbox_runner",
        target_function="render_engel_sandbox_delete",
        aliases=(
            "engel sandbox delete",
            "delete engel sandbox",
            "kill engel sandbox",
            "destroy engel sandbox",
        ),
        read_only=False,
        status_only=False,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_SANDBOX_BRING_UP_ROUTE_ID,
        label="Engel Sandbox WSL2 bring-up guide",
        target_module="engel_engel_sandbox_runner",
        target_function="render_engel_sandbox_bring_up",
        aliases=(
            "engel sandbox bring up",
            "bring up engel sandbox",
            "engel sandbox setup",
            "install engel sandbox",
            "how to start engel sandbox",
            "engel sandbox how to",
            "engel sandbox guide",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_WSL_STATUS_ROUTE_ID,
        label="Engel WSL Bridge status",
        target_module="engel_wsl_bridge",
        target_function="render_wsl_status",
        aliases=(
            "check wsl status",
            "wsl status",
            "ubuntu status",
            "check ubuntu",
            "is ubuntu installed",
            "is wsl installed",
            "wsl version",
            "ubuntu version",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_WSL_DISTROS_ROUTE_ID,
        label="Engel WSL Bridge distro list",
        target_module="engel_wsl_bridge",
        target_function="render_wsl_distros",
        aliases=(
            "show wsl distros",
            "list wsl distros",
            "wsl distros",
            "wsl distro list",
            "show ubuntu distros",
            "list ubuntu distros",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_WSL_TOOLS_ROUTE_ID,
        label="Engel WSL Bridge Linux tool readiness",
        target_module="engel_wsl_bridge",
        target_function="render_wsl_tools",
        aliases=(
            "show linux tools",
            "check linux tools",
            "check python in ubuntu",
            "check node in ubuntu",
            "check git in ubuntu",
            "linux tool status",
            "ubuntu tool status",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_WSL_PATHS_ROUTE_ID,
        label="Engel WSL Bridge path status",
        target_module="engel_wsl_bridge",
        target_function="render_wsl_paths",
        aliases=(
            "where is ubuntu installed",
            "where should ubuntu live",
            "where is engel in ubuntu",
            "show wsl engel path",
            "check engel path in ubuntu",
            "can ubuntu see engel",
            "check /mnt/d engel path",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_WSL_SELF_TEST_ROUTE_ID,
        label="Engel WSL Bridge self-test",
        target_module="engel_wsl_bridge",
        target_function="render_wsl_self_test",
        aliases=(
            "run wsl self test",
            "wsl self test",
            "ubuntu self test",
            "test wsl bridge",
            "check wsl bridge",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_WSL_UBUNTU_RUNTIME_STATUS_ROUTE_ID,
        label="Engel WSL Ubuntu Runtime Dependency status (Stage 2 contract)",
        target_module="engel_wsl_ubuntu_runner",
        target_function="render_wsl_ubuntu_runtime_status",
        aliases=(
            "wsl ubuntu runtime status",
            "wsl ubuntu contract",
            "wsl ubuntu contract status",
            "show wsl ubuntu contract",
            "engel wsl ubuntu status",
            "is engel allowed to auto run wsl",
            "is engel allowed in wsl",
            "what can engel do in wsl",
            "stage 2 autonomy status",
            "wsl ubuntu stage status",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_WSL_UBUNTU_RUNTIME_FACTS_ROUTE_ID,
        label="Engel WSL Ubuntu Runtime Dependency recorded facts",
        target_module="engel_wsl_ubuntu_runner",
        target_function="render_wsl_ubuntu_runtime_facts",
        aliases=(
            "wsl ubuntu facts",
            "wsl ubuntu distro facts",
            "wsl ubuntu paths",
            "where is the engel ubuntu distro",
            "show wsl ubuntu facts",
            "engel wsl ubuntu paths",
            "engel ubuntu distro info",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_WSL_UBUNTU_RUNTIME_SAFETY_ROUTE_ID,
        label="Engel WSL Ubuntu Runtime Dependency safety boundaries",
        target_module="engel_wsl_ubuntu_runner",
        target_function="render_wsl_ubuntu_runtime_safety",
        aliases=(
            "wsl ubuntu safety",
            "wsl ubuntu boundaries",
            "wsl ubuntu what is allowed",
            "wsl ubuntu what is gated",
            "what can engel do in wsl ubuntu",
            "engel wsl ubuntu safety",
            "wsl ubuntu safety boundaries",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_WSL_UBUNTU_RUNTIME_STAGE_2_ROUTE_ID,
        label="Engel WSL Ubuntu Runtime Dependency Stage 2 amendment",
        target_module="engel_wsl_ubuntu_runner",
        target_function="render_wsl_ubuntu_runtime_stage_2",
        aliases=(
            "wsl ubuntu stage 2",
            "wsl ubuntu stage two",
            "engel stage 2",
            "engel stage two",
            "stage 2 autonomy",
            "stage 2 amendment",
            "show stage 2",
            "what changed in wsl ubuntu",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_WSL_UBUNTU_RUNTIME_STAGE_3_ROUTE_ID,
        label="Engel WSL Ubuntu Runtime Dependency Stage 3 amendment (full local AI dev environment)",
        target_module="engel_wsl_ubuntu_runner",
        target_function="render_wsl_ubuntu_runtime_stage_3",
        aliases=(
            "wsl ubuntu stage 3",
            "wsl ubuntu stage three",
            "engel stage 3",
            "engel stage three",
            "stage 3 autonomy",
            "stage 3 amendment",
            "show stage 3",
            "can engel install packages",
            "can engel load models",
            "can engel train",
            "can engel run inference",
            "full local ai environment",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGELCODE_STATUS_ROUTE_ID,
        label="Engelcode (Rust TUI coding agent) status",
        target_module="engel_engelcode_runner",
        target_function="render_engelcode_status",
        aliases=(
            "engelcode status",
            "engel code status",
            "show engelcode",
            "show engelcode status",
            "is engelcode built",
            "engelcode health",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGELCODE_VERSION_ROUTE_ID,
        label="Engelcode Cargo.toml version",
        target_module="engel_engelcode_runner",
        target_function="render_engelcode_version",
        aliases=(
            "engelcode version",
            "engel code version",
            "show engelcode version",
            "what version is engelcode",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGELCODE_CRATES_ROUTE_ID,
        label="Engelcode Rust workspace crate inventory",
        target_module="engel_engelcode_runner",
        target_function="render_engelcode_crates",
        aliases=(
            "engelcode crates",
            "engel code crates",
            "list engelcode crates",
            "show engelcode crates",
            "engelcode workspace",
            "engelcode workspace members",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGELCODE_BUILD_ROUTE_ID,
        label="Engelcode cargo build --release (blocking, may take 10-30 min)",
        target_module="engel_engelcode_runner",
        target_function="render_engelcode_build",
        aliases=(
            "engelcode build",
            "engel code build",
            "build engelcode",
            "compile engelcode",
            "cargo build engelcode",
            "rebuild engelcode",
        ),
        read_only=False,
        status_only=False,
        no_background_worker=False,
        no_visible_ui_change=False,
    ),
    EngelAIUpdateRoute(
        route_id=ENGELCODE_INVOKE_ROUTE_ID,
        label="Engelcode invoke built binary (autonomous coding agent)",
        target_module="engel_engelcode_runner",
        target_function="render_engelcode_invoke",
        aliases=(
            "engelcode invoke",
            "engelcode run",
            "engel code invoke",
            "engel code run",
            "run engelcode",
            "exec engelcode",
        ),
        read_only=False,
        status_only=False,
        no_memory_promotion=False,
        no_trusted_memory_write=False,
        no_fix_apply=False,
        no_archive_mutation=False,
        no_provider_model_network=False,
        no_background_worker=False,
        no_visible_ui_change=False,
    ),
    EngelAIUpdateRoute(
        route_id=ENGELCODE_BRING_UP_ROUTE_ID,
        label="Engelcode Rust toolchain bring-up guide",
        target_module="engel_engelcode_runner",
        target_function="render_engelcode_bring_up",
        aliases=(
            "engelcode bring up",
            "bring up engelcode",
            "engelcode setup",
            "install engelcode",
            "engelcode guide",
            "how to build engelcode",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_MAIN_STATUS_ROUTE_ID,
        label="Engel Main (Tauri desktop companion) status",
        target_module="engel_ai_main_rust_ui_shell_bridge",
        target_function="render_engel_main_status",
        aliases=(
            "engel main status",
            "engel desktop status",
            "engel companion status",
            "show engel main",
            "is engel main running",
            "engel main health",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_MAIN_VERSION_ROUTE_ID,
        label="Engel Main app/package.json version",
        target_module="engel_ai_main_rust_ui_shell_bridge",
        target_function="render_engel_main_version",
        aliases=(
            "engel main version",
            "engel companion version",
            "show engel main version",
            "what version is engel main",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_MAIN_BINARIES_ROUTE_ID,
        label="Engel Main declared Rust [[bin]] targets",
        target_module="engel_ai_main_rust_ui_shell_bridge",
        target_function="render_engel_main_binaries",
        aliases=(
            "engel main binaries",
            "engel main bins",
            "list engel main binaries",
            "show engel main bins",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_MAIN_INSTALL_ROUTE_ID,
        label="Engel Main pnpm install (JS deps)",
        target_module="engel_ai_main_rust_ui_shell_bridge",
        target_function="render_engel_main_install",
        aliases=(
            "engel main install",
            "install engel main",
            "engel main deps install",
            "pnpm install engel main",
        ),
        read_only=False,
        status_only=False,
        no_visible_ui_change=False,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_MAIN_BUILD_ROUTE_ID,
        label="Engel Main pnpm build (web bundle, no Rust needed)",
        target_module="engel_ai_main_rust_ui_shell_bridge",
        target_function="render_engel_main_build",
        aliases=(
            "engel main build",
            "engel companion build",
            "build engel main",
            "compile engel main",
            "engel main web build",
        ),
        read_only=False,
        status_only=False,
        no_visible_ui_change=False,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_MAIN_DEV_START_ROUTE_ID,
        label="Engel Main pnpm dev start (detached Vite, no Rust needed)",
        target_module="engel_ai_main_rust_ui_shell_bridge",
        target_function="render_engel_main_dev_start",
        aliases=(
            "engel main dev start",
            "engel main start",
            "start engel main",
            "launch engel main",
            "engel main dev",
            "open engel companion",
        ),
        read_only=False,
        status_only=False,
        no_background_worker=False,
        no_visible_ui_change=False,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_MAIN_DEV_STOP_ROUTE_ID,
        label="Engel Main dev server stop",
        target_module="engel_ai_main_rust_ui_shell_bridge",
        target_function="render_engel_main_dev_stop",
        aliases=(
            "engel main dev stop",
            "engel main stop",
            "stop engel main",
            "kill engel main",
            "close engel companion",
        ),
        read_only=False,
        status_only=False,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_MAIN_TAURI_BUILD_ROUTE_ID,
        label="Engel Main full Tauri desktop build (requires Rust + pnpm)",
        target_module="engel_ai_main_rust_ui_shell_bridge",
        target_function="render_engel_main_tauri_build",
        aliases=(
            "engel main tauri build",
            "engel companion tauri build",
            "build engel main desktop",
            "engel main full build",
            "engel main desktop build",
        ),
        read_only=False,
        status_only=False,
        no_background_worker=False,
        no_visible_ui_change=False,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_MAIN_BRING_UP_ROUTE_ID,
        label="Engel Main bring-up guide (Node + pnpm + Rust)",
        target_module="engel_ai_main_rust_ui_shell_bridge",
        target_function="render_engel_main_bring_up",
        aliases=(
            "engel main bring up",
            "engel companion bring up",
            "bring up engel main",
            "engel main setup",
            "engel main guide",
            "how to start engel main",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_LAN_STATUS_ROUTE_ID,
        label="Engel LAN (file sharing) status",
        target_module="engel_engel_lan_runner",
        target_function="render_engel_lan_status",
        aliases=(
            "engel lan status",
            "engel lan health",
            "show engel lan",
            "show engel lan status",
            "is engel lan running",
            "engel lan",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_LAN_VERSION_ROUTE_ID,
        label="Engel LAN pubspec versions (CLI + App)",
        target_module="engel_engel_lan_runner",
        target_function="render_engel_lan_version",
        aliases=(
            "engel lan version",
            "engel lan versions",
            "show engel lan version",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_LAN_CLI_HELP_ROUTE_ID,
        label="Engel LAN CLI --help (Dart subprocess)",
        target_module="engel_engel_lan_runner",
        target_function="render_engel_lan_cli_help",
        aliases=(
            "engel lan cli help",
            "engel lan help",
            "engel lan cli usage",
            "show engel lan cli help",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_LAN_CLI_RECEIVE_START_ROUTE_ID,
        label="Engel LAN CLI receive server start (detached, listens for LAN file transfers)",
        target_module="engel_engel_lan_runner",
        target_function="render_engel_lan_cli_receive_start",
        aliases=(
            "engel lan receive start",
            "engel lan cli receive",
            "engel lan receive",
            "start engel lan receive",
            "engel lan listen",
        ),
        read_only=False,
        status_only=False,
        no_background_worker=False,
        no_provider_model_network=False,
        no_visible_ui_change=False,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_LAN_CLI_RECEIVE_STOP_ROUTE_ID,
        label="Engel LAN CLI receive server stop",
        target_module="engel_engel_lan_runner",
        target_function="render_engel_lan_cli_receive_stop",
        aliases=(
            "engel lan receive stop",
            "stop engel lan receive",
            "engel lan stop receive",
            "kill engel lan receive",
        ),
        read_only=False,
        status_only=False,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_LAN_APP_DEV_START_ROUTE_ID,
        label="Engel LAN app dev start (detached flutter run)",
        target_module="engel_engel_lan_runner",
        target_function="render_engel_lan_app_dev_start",
        aliases=(
            "engel lan app dev start",
            "engel lan dev start",
            "engel lan app start",
            "engel lan start",
            "launch engel lan",
            "open engel lan",
        ),
        read_only=False,
        status_only=False,
        no_background_worker=False,
        no_provider_model_network=False,
        no_visible_ui_change=False,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_LAN_APP_DEV_STOP_ROUTE_ID,
        label="Engel LAN app dev stop",
        target_module="engel_engel_lan_runner",
        target_function="render_engel_lan_app_dev_stop",
        aliases=(
            "engel lan app dev stop",
            "engel lan dev stop",
            "engel lan stop",
            "stop engel lan",
            "kill engel lan",
        ),
        read_only=False,
        status_only=False,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_LAN_BRING_UP_ROUTE_ID,
        label="Engel LAN bring-up guide (Flutter SDK)",
        target_module="engel_engel_lan_runner",
        target_function="render_engel_lan_bring_up",
        aliases=(
            "engel lan bring up",
            "bring up engel lan",
            "engel lan setup",
            "engel lan guide",
            "how to start engel lan",
            "install engel lan",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_LAN_WORKERS_SCAN_ROUTE_ID,
        label="LAN worker scan — discover inference workers on local subnet",
        target_module="engel_lan_worker",
        target_function="render_lan_workers_scan",
        aliases=(
            "lan workers scan",
            "scan lan workers",
            "find android workers",
            "discover inference workers",
            "scan for workers",
            "find workers on lan",
        ),
        read_only=False,
        status_only=False,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_LAN_WORKERS_STATUS_ROUTE_ID,
        label="LAN worker status — show registered inference workers",
        target_module="engel_lan_worker",
        target_function="render_lan_workers_status",
        aliases=(
            "lan workers",
            "lan worker status",
            "show lan workers",
            "android workers",
            "remote workers",
        ),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_LAN_WORKERS_ADD_ROUTE_ID,
        label="LAN workers add — register a worker by IP:port",
        target_module="engel_lan_worker",
        target_function="render_lan_workers_add",
        aliases=(
            "lan workers add",
            "add lan worker",
            "register worker",
            "add android worker",
        ),
        read_only=False,
        status_only=False,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_LAN_WORKERS_REMOVE_ROUTE_ID,
        label="LAN workers remove — deregister a worker by IP:port",
        target_module="engel_lan_worker",
        target_function="render_lan_workers_remove",
        aliases=(
            "lan workers remove",
            "remove lan worker",
            "deregister worker",
        ),
        read_only=False,
        status_only=False,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_LAN_WORKER_DISPATCH_ROUTE_ID,
        label="LAN worker dispatch — send inference prompt to best available worker",
        target_module="engel_lan_worker",
        target_function="render_lan_worker_dispatch",
        aliases=(
            "lan worker dispatch",
            "dispatch to worker",
            "send to android worker",
            "worker inference",
            "remote inference",
            "offload inference",
        ),
        read_only=False,
        status_only=False,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_LAN_NETWORK_DEVICES_ROUTE_ID,
        label="LAN network devices — list all devices on local subnet",
        target_module="engel_lan_worker",
        target_function="render_lan_network_devices",
        aliases=(
            "lan devices",
            "network devices",
            "show network devices",
            "who is on my network",
            "lan scan devices",
            "android devices on network",
        ),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_ADB_WORKERS_STATUS_ROUTE_ID,
        label="Android workers status (ADB USB) — connected phones and job queue",
        target_module="engel_adb_worker_manager",
        target_function="render_adb_workers_status",
        aliases=(
            "android workers status",
            "adb workers",
            "phone workers",
            "connected workers",
            "usb workers status",
            "engel phone status",
            "android worker not connected",
            "android workers not connected",
            "one of the android workers is not connected",
            "android workers disconnected",
            "fix android worker connection",
            "fix android workers",
            "check android workers",
            "android worker offline",
        ),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_ADB_WORKERS_PULL_ROUTE_ID,
        label="Android workers pull results (ADB) — pull job results from phones",
        target_module="engel_adb_worker_manager",
        target_function="render_adb_workers_pull_results",
        aliases=(
            "adb workers pull",
            "pull worker results",
            "pull android results",
            "get phone results",
            "collect worker output",
        ),
        read_only=False,
        status_only=False,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_ADB_WORKERS_PUSH_ROUTE_ID,
        label="Android workers push jobs (ADB) — push PC job packets to phones",
        target_module="engel_adb_worker_manager",
        target_function="render_adb_workers_push_jobs",
        aliases=(
            "adb workers push",
            "push jobs to phone",
            "send jobs to android",
            "assign android job",
        ),
        read_only=False,
        status_only=False,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_ADB_WORKERS_RESULT_ROUTE_ID,
        label="Android workers latest result — show most recent pulled result",
        target_module="engel_adb_worker_manager",
        target_function="render_adb_workers_latest_result",
        aliases=(
            "adb workers result",
            "latest worker result",
            "android result",
            "phone job result",
        ),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_ADB_WORKERS_PROVISION_ROUTE_ID,
        label="Android workers provision — create worker dirs on phone via ADB",
        target_module="engel_adb_worker_manager",
        target_function="render_adb_provision_worker",
        aliases=(
            "adb provision worker",
            "provision phone worker",
            "setup android worker",
            "create worker dirs",
            "init android worker",
        ),
        read_only=False,
        status_only=False,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_ADB_WORKERS_JOBS_ROUTE_ID,
        label="Android workers job dashboard — PC-side job status for all workers",
        target_module="engel_adb_worker_manager",
        target_function="render_adb_workers_jobs",
        aliases=(
            "adb workers jobs",
            "android worker jobs",
            "phone jobs",
            "worker job list",
            "android jobs dashboard",
        ),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_ADB_WORKERS_CREATE_JOB_ROUTE_ID,
        label="Android workers create job — create a new job packet for a phone worker",
        target_module="engel_adb_worker_manager",
        target_function="render_adb_create_job",
        aliases=(
            "adb workers create job",
            "create android job",
            "new phone job",
            "create worker job",
            "assign job to android",
        ),
        read_only=False,
        status_only=False,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_LAN_PAIRING_STATUS_ROUTE_ID,
        label="LAN pairing server status — show pairing session state",
        target_module="engel_remote_worker_lan_pairing",
        target_function="render_lan_pairing_status",
        aliases=(
            "lan pairing status",
            "remote worker pairing",
            "phone pairing status",
            "lan pairing server",
            "pairing token status",
        ),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_LAN_PAIRING_TOKEN_ROUTE_ID,
        label="LAN pairing generate token — create new pairing code for phone",
        target_module="engel_remote_worker_lan_pairing",
        target_function="render_lan_pairing_token",
        aliases=(
            "lan pairing token",
            "generate pairing token",
            "new pairing code",
            "create pairing token",
        ),
        read_only=False,
        status_only=False,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_MULTI_ANDROID_STATUS_ROUTE_ID,
        label="Multi-Android workers protocol status — all 3 workers overview",
        target_module="engel_multi_android_remote_workers",
        target_function="render_status",
        aliases=(
            "multi android status",
            "android workers overview",
            "remote worker protocol status",
            "all workers status",
        ),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_MULTI_ANDROID_LINKS_ROUTE_ID,
        label="Multi-Android workers check links — verify all worker files present",
        target_module="engel_multi_android_remote_workers",
        target_function="render_check_links",
        aliases=(
            "android worker check links",
            "check android worker files",
            "verify worker packages",
        ),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_WORKER_ASSIGNMENT_STATUS_ROUTE_ID,
        label="Worker assignment status — job assignment registry and contract",
        target_module="engel_remote_worker_job_assignment",
        target_function="render_status",
        aliases=(
            "worker assignment status",
            "job assignment registry",
            "android assignment protocol",
            "remote worker assignment",
        ),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_WORKER_ASSIGNMENT_JOBS_ROUTE_ID,
        label="Worker assignment prepared jobs — list all job packets ready to assign",
        target_module="engel_remote_worker_job_assignment",
        target_function="render_prepared_jobs",
        aliases=(
            "worker prepared jobs",
            "prepared job packets",
            "jobs ready to assign",
            "worker job packets list",
        ),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_RESULT_INTAKE_STATUS_ROUTE_ID,
        label="Remote worker result intake status — incoming result folder state",
        target_module="engel_remote_worker_result_intake",
        target_function="render_status",
        aliases=(
            "result intake status",
            "remote worker result intake",
            "incoming results status",
            "worker result folder",
        ),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_RESULT_INTAKE_LIST_ROUTE_ID,
        label="Remote worker result intake list — list incoming result files",
        target_module="engel_remote_worker_result_intake",
        target_function="render_list",
        aliases=(
            "result intake list",
            "incoming result files",
            "list worker results",
        ),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_RUNTIME_READINESS_ROUTE_ID,
        label="AI runtime readiness dashboard — local inference readiness check",
        target_module="engel_ai_runtime_readiness",
        target_function="render_status",
        aliases=(
            "runtime readiness",
            "ai runtime readiness",
            "inference readiness",
            "engel readiness check",
        ),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_SYSTEM_INTEGRATION_STATUS_ROUTE_ID,
        label="System integration status — full system reconciliation check",
        target_module="engel_system_integration_status",
        target_function="render_status",
        aliases=(
            "system integration status",
            "engel system check",
            "full system status",
            "integration reconciliation",
        ),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_CORE_V1_DASHBOARD_ROUTE_ID,
        label="Engel Core V1 command center dashboard",
        target_module="engel_core_v1_dashboard_status",
        target_function="render_core_v1_dashboard_status",
        aliases=(
            "core dashboard",
            "engel core v1",
            "command center",
            "core command center",
            "engel core status",
        ),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_DAILY_CYCLE_STATUS_ROUTE_ID,
        label="Daily cycle status surface — receipts and cycle run history",
        target_module="engel_daily_cycle_status_surface",
        target_function="render_status_surface",
        aliases=(
            "daily cycle status",
            "engel daily cycle",
            "cycle run history",
            "daily receipts",
        ),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_CANDIDATE_REVIEW_DASHBOARD_ROUTE_ID,
        label="Candidate review dashboard — counts of all candidate queues",
        target_module="engel_candidate_review_dashboard",
        target_function="render_candidate_counts",
        aliases=(
            "candidate review dashboard",
            "candidate counts",
            "review queue counts",
            "lesson candidate counts",
            "candidate pipeline",
        ),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_APPROVED_MEMORY_STATUS_ROUTE_ID,
        label="Approved memory promotion status — pending approvals and gate state",
        target_module="engel_approved_memory_promotion",
        target_function="render_status",
        aliases=(
            "approved memory status",
            "memory promotion status",
            "memory approval gate",
            "memory candidates status",
        ),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_APPROVED_MEMORY_CANDIDATES_ROUTE_ID,
        label="Approved memory candidates — list memory candidate proposals",
        target_module="engel_approved_memory_promotion",
        target_function="render_candidates",
        aliases=(
            "memory candidate proposals",
            "list memory candidates",
            "approved memory candidates",
            "memory proposals",
        ),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_BROWSER_QUEEN_STATUS_ROUTE_ID,
        label="Browser Queen phase 3 contract status",
        target_module="engel_browser_queen_phase3_contract",
        target_function="render_browser_queen_phase3_contract_status",
        aliases=(
            "browser queen status",
            "browser queen phase 3",
            "browser queen contract",
        ),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_BROWSER_QUEEN_PHASE2_ROUTE_ID,
        label="Browser Queen phase 2 status",
        target_module="engel_browser_queen_phase2_status",
        target_function="render_browser_queen_phase2_status",
        aliases=(
            "browser queen phase 2",
            "browser status panel",
        ),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_BROWSER_QUEEN_WORKBENCH_ROUTE_ID,
        label="Browser Queen workbench phase status — all phases overview",
        target_module="engel_browser_queen_workbench",
        target_function="render_browser_queen_phase_status",
        aliases=(
            "browser queen workbench",
            "browser queen phases",
            "all browser phases",
        ),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_BROWSER_QUEEN_MVP_ROUTE_ID,
        label="Browser Queen MVP runtime status — open URL and manual intake",
        target_module="engel_browser_queen_runtime_mvp",
        target_function="render_browser_queen_mvp_status",
        aliases=(
            "browser queen mvp",
            "browser mvp status",
            "open url status",
        ),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_RESEARCH_OFFICE_STATUS_ROUTE_ID,
        label="Research office status — colony and office health check",
        target_module="engel_research_office_data",
        target_function="render_research_office_status",
        aliases=(
            "research office status",
            "research office health",
            "colony office status",
        ),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_RESEARCH_OFFICE_MAP_ROUTE_ID,
        label="Research office map — structure and connection map",
        target_module="engel_research_office_data",
        target_function="render_research_office_map",
        aliases=(
            "research office map",
            "office structure map",
            "research map",
        ),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_RESEARCH_TOGGLE_STATUS_ROUTE_ID,
        label="Research toggle status — overnight worker enable/disable state",
        target_module="engel_research_toggle_status",
        target_function="render_status",
        aliases=(
            "research toggle status",
            "overnight worker status",
            "research toggle",
            "research worker enabled",
        ),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_RESEARCH_TOGGLE_EXPLAIN_ROUTE_ID,
        label="Research toggle explain — how the research toggle works",
        target_module="engel_research_toggle_status",
        target_function="render_explain",
        aliases=(
            "research toggle explain",
            "explain research toggle",
            "how research toggle works",
        ),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_SELF_LEARNING_STATUS_ROUTE_ID,
        label="Self-learning status surface — learning pipeline and candidate chain",
        target_module="engel_self_learning_status_surface",
        target_function="render_status_surface",
        aliases=(
            "self learning status",
            "learning pipeline status",
            "self learning surface",
            "engel learning status",
        ),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_PRODUCT_WORKBENCH_STATUS_ROUTE_ID,
        label="Product workbench status — code companion product development view",
        target_module="engel_code_companion_product_workbench",
        target_function="render_selected_product_workbench",
        aliases=(
            "product workbench",
            "code companion workbench",
            "product workbench status",
            "selected product workbench",
        ),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_PRODUCT_CYCLE_DASHBOARD_ROUTE_ID,
        label="Product cycle dashboard — plan, patch, review cycle overview",
        target_module="engel_code_companion_product_cycle_dashboard",
        target_function="render_selected_product_cycle_dashboard",
        aliases=(
            "product cycle dashboard",
            "product development cycle",
            "product cycle status",
            "code companion cycle",
        ),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_CORE_CONTINUITY_STATUS_ROUTE_ID,
        label="Core continuity status — controlled library chain and continuity surface",
        target_module="engel_core_continuity_status_surface",
        target_function="render_controlled_library_chain_status",
        aliases=(
            "core continuity status",
            "library chain status",
            "continuity dashboard",
            "controlled library chain",
        ),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_MEMORY_ARCHIVE_STATUS_ROUTE_ID,
        label="Memory archive status — archive shelf and backup state",
        target_module="engel_memory_archive_status",
        target_function="render_memory_archive_status",
        aliases=(
            "memory archive status",
            "archive shelf status",
            "memory backup status",
        ),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_MEMORY_CANDIDATE_REVIEW_ROUTE_ID,
        label="Memory candidate review dashboard — trusted memory candidate queue",
        target_module="engel_memory_candidate_review_dashboard",
        target_function="render_memory_candidate_review_dashboard",
        aliases=(
            "memory candidate review",
            "memory review dashboard",
            "trusted memory candidates",
        ),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_OFFLINE_MODEL_CONTRACT_ROUTE_ID,
        label="Offline model runtime contract — local inference contract status",
        target_module="engel_offline_model_runtime_contract",
        target_function="render_offline_model_runtime_status",
        aliases=(
            "offline model contract",
            "local inference contract",
            "offline runtime status",
        ),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_PROGRESS_REPORT_ROUTE_ID,
        label="Progress report — detailed Engel feature expansion progress",
        target_module="engel_progress_dashboard",
        target_function="render_progress_report",
        aliases=(
            "progress report",
            "engel progress report",
            "feature progress",
            "expansion progress",
        ),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_WHOLE_SYSTEM_AUDIT_ROUTE_ID,
        label="Whole-system incomplete audit — outstanding items across all subsystems",
        target_module="engel_whole_system_incomplete_audit",
        target_function="render_report",
        aliases=(
            "whole system audit",
            "incomplete items audit",
            "system audit report",
            "outstanding items",
        ),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_COLONY_SIMULATION_ROUTE_ID,
        label="Colony simulation status — research colony dry-run and simulation state",
        target_module="engel_research_status",
        target_function="render_colony_simulation_status",
        aliases=(
            "colony simulation status",
            "research colony status",
            "colony sim status",
        ),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_AI_BODY_STATUS_ROUTE_ID,
        label="Engel AI body status — local AI organs and authority mapping",
        target_module="engel_ai_body_status",
        target_function="render_ai_body_status_text",
        aliases=(
            "ai body status",
            "engel ai body",
            "local ai organs",
            "ai authority map",
        ),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_WSL_BRIDGE_STATUS_ROUTE_ID,
        label="WSL bridge status — allowed WSL commands and tool allowlist",
        target_module="engel_wsl_bridge",
        target_function="render_json_status",
        aliases=(
            "wsl bridge status",
            "wsl allowlist",
            "wsl tool allowlist",
        ),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_PROTECTED_ACTIONS_LIST_ROUTE_ID,
        label="Protected action registry — list of all protected actions and their gates",
        target_module="engel_protected_action_registry",
        target_function="render_action_list",
        aliases=(
            "protected actions list",
            "protected action registry",
            "action gates",
            "engel protected actions",
        ),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_PATCH_RECEIPTS_LIST_ROUTE_ID,
        label="Code companion patch receipts — list of applied patch receipts",
        target_module="engel_code_companion_patch_receipt_viewer",
        target_function="render_receipt_list",
        aliases=("patch receipts list", "applied patch receipts", "patch receipt viewer"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_LOWRISK_SELFFIX_STATUS_ROUTE_ID,
        label="Low-risk self-fix status surface — bounded self-fix pipeline state",
        target_module="engel_low_risk_self_fix_status_surface",
        target_function="render_status",
        aliases=("low risk self fix status", "self fix surface", "bounded self fix"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_MEMORY_INVENTORY_ROUTE_ID,
        label="Memory candidate inventory — all memory candidates and proposal counts",
        target_module="engel_memory_candidate_inventory",
        target_function="render_inventory_report",
        aliases=("memory inventory", "memory candidate inventory", "memory proposals inventory"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_RUNTIME_PATH_CONFIG_ROUTE_ID,
        label="AI local runtime path config — configured runtime roots and drive paths",
        target_module="engel_ai_local_runtime_path_config",
        target_function="render_status",
        aliases=("runtime path config", "ai runtime paths", "local runtime config"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_LLAMA_COMPAT_MATRIX_ROUTE_ID,
        label="llama.cpp compatibility matrix — build vs. GPU compatibility check",
        target_module="engel_ai_llama_cpp_compatibility_matrix",
        target_function="render_status",
        aliases=("llama compat matrix", "llama cpp compatibility", "build compatibility matrix"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_RESEARCH_TO_FIX_SUMMARY_ROUTE_ID,
        label="Research-to-fix loop summary — research findings to fix pipeline state",
        target_module="engel_research_to_fix_loop",
        target_function="render_summary",
        aliases=("research to fix summary", "research fix loop", "fix loop status"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_OFFLINE_SEED_LLM_ROUTE_ID,
        label="Offline seed LLM status — local Qwen2.5-0.5B seed model state",
        target_module="engel_offline_seed_llm",
        target_function="render_offline_seed_llm_status",
        aliases=("offline seed llm", "seed llm status", "local seed model"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_ARCHIVE_SHELF_REPORT_ROUTE_ID,
        label="Archive shelf report — E-drive archive shelf status",
        target_module="engel_archive_shelf_manager",
        target_function="render_archive_shelf_report",
        aliases=("archive shelf report", "archive shelf status", "engel archive"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_TRUTHFULNESS_GUARD_ROUTE_ID,
        label="Truthfulness anti-flattery guard status — honesty constraint state",
        target_module="engel_truthfulness_anti_flattery_guard",
        target_function="render_status",
        aliases=("truthfulness guard status", "anti flattery guard", "honesty guard"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_OUTSIDE_AI_BOUNDARY_ROUTE_ID,
        label="Outside-AI boundary rule — AI/tool boundary constraints",
        target_module="engel_outside_ai_boundary",
        target_function="render_status",
        aliases=("outside ai boundary", "ai boundary rule", "engel boundary"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_PASSWORD_GATE_ROUTE_ID,
        label="Password gate status — global password-gated action layer state",
        target_module="engel_global_password_gate",
        target_function="render_status",
        aliases=("password gate status", "global password gate", "action password gate"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_COLONY_HIVE_MAP_ROUTE_ID,
        label="Colony hive map — Engel colony chamber visual map",
        target_module="engel_research_office_data",
        target_function="render_colony_hive_map",
        aliases=("colony hive map", "engel colony map", "hive chamber map"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_COLONY_HIVE_STATUS_ROUTE_ID,
        label="Colony hive status — full colony hive state with chambers",
        target_module="engel_research_office_data",
        target_function="render_colony_hive_status",
        aliases=("colony hive status", "colony status", "hive status"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_COLONY_HIVE_PERMISSIONS_ROUTE_ID,
        label="Colony hive permissions — safety permissions panel",
        target_module="engel_research_office_data",
        target_function="render_colony_hive_permissions",
        aliases=("colony hive permissions", "hive permissions", "colony permissions"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_COLONY_HIVE_QUEEN_LINKS_ROUTE_ID,
        label="Colony hive queen links — research queen connection map",
        target_module="engel_research_office_data",
        target_function="render_colony_hive_queen_links",
        aliases=("colony queen links", "hive queen links", "queen research links"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_COMMUNICATION_QUEEN_STATUS_ROUTE_ID,
        label="Communication Queen status — remote queen and communication routing",
        target_module="engel_research_office_data",
        target_function="render_communication_queen_status",
        aliases=("communication queen status", "remote queen status", "queen communication"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_ENGEL_MIND_CONNECTIONS_ROUTE_ID,
        label="Engel mind connections — mind/hive upgrade connection map",
        target_module="engel_research_office_data",
        target_function="render_engel_mind_connections_status",
        aliases=("engel mind connections", "mind hive connections", "upgrade connections"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_FUTURE_UPGRADES_STATUS_ROUTE_ID,
        label="Future upgrades status — planned upgrade pipeline and readiness",
        target_module="engel_research_office_data",
        target_function="render_future_upgrades_status",
        aliases=("future upgrades status", "planned upgrades", "upgrade pipeline"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_LONG_TERM_MEMORY_DRIVE_ROUTE_ID,
        label="Long-term memory drive status — E/F/G drive memory archive state",
        target_module="engel_research_office_data",
        target_function="render_long_term_memory_drive_status",
        aliases=("long term memory drive", "memory drive status", "archive drives status"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_PRODUCT_CONTEXT_PACK_ROUTE_ID,
        label="Product context pack -- current code companion product context bundle",
        target_module="engel_code_companion_product_context",
        target_function="render_selected_product_context_pack",
        aliases=("product context pack", "context pack", "code companion context"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_GUIDED_LIBRARY_REVIEW_ROUTE_ID,
        label="Guided library review surface -- manual review queue UI surface",
        target_module="engel_guided_library_review_surface",
        target_function="render_surface_text",
        aliases=("guided library review", "library review surface", "guided review status"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_HUMAN_REVIEW_DRAFT_SURFACE_ROUTE_ID,
        label="Human review draft surface -- pending human-review draft surface",
        target_module="engel_human_review_receipt_draft_surface",
        target_function="render_surface_text",
        aliases=("human review draft", "review draft surface", "draft surface status"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_TRUSTED_MEMORY_TARGET_ROUTE_ID,
        label="Trusted memory target status -- trusted write target state",
        target_module="engel_trusted_memory_target",
        target_function="render_status",
        aliases=("trusted memory target", "memory target status", "trusted target"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_SELF_FIX_RECEIPT_LIST_ROUTE_ID,
        label="Self-fix receipt list -- completed self-fix receipts",
        target_module="engel_self_fix_receipt_viewer",
        target_function="render_receipt_list",
        aliases=("self fix receipts", "fix receipt list", "self fix log"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_INTENT_PLANNER_STATUS_ROUTE_ID,
        label="Intent planner status -- AI intent planner current state",
        target_module="engel_ai_intent_planner",
        target_function="render_status",
        aliases=("intent planner status", "intent planner", "ai intent status"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_INTENT_PLANNER_HELP_ROUTE_ID,
        label="Intent planner help -- AI intent planner usage guide",
        target_module="engel_ai_intent_planner",
        target_function="render_help",
        aliases=("intent planner help", "intent help", "planner help"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_INTENT_BRIDGE_DOCS_ROUTE_ID,
        label="HIPL/MIPL Intent Bridge reference -- human expression to auditable machine comprehension",
        target_module="engel_lifted_intent",
        target_function="render_docs",
        aliases=(
            "intent bridge docs",
            "hipl docs",
            "mipl docs",
            "what is the intent bridge",
            "lifted intent help",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_INTENT_BRIDGE_STATUS_ROUTE_ID,
        label="HIPL/MIPL Intent Bridge status and receipt count",
        target_module="engel_lifted_intent",
        target_function="render_status",
        aliases=(
            "intent bridge status",
            "hipl status",
            "mipl status",
            "lifted intent status",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_INTENT_BRIDGE_LATEST_ROUTE_ID,
        label="Latest lifted intent and machine comprehension receipt",
        target_module="engel_lifted_intent",
        target_function="render_latest",
        aliases=(
            "latest lifted intent",
            "show latest intent",
            "intent bridge latest",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_INTENT_BRIDGE_LIFT_ROUTE_ID,
        label="Preview a HIPL expression as non-executing lifted intent and MIPL IR",
        target_module="engel_lifted_intent",
        target_function="render_lift",
        aliases=(
            "lift intent",
            "lifted intent",
            "intent bridge lift",
            "compile mipl",
            "write mipl",
            "assemble mipl",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_SPEECH_SPC_DOCS_ROUTE_ID,
        label="Speech Packet Compiler reference -- hear/speak packets without playback",
        target_module="engel_speech_spc",
        target_function="render_docs",
        aliases=(
            "speech spc docs",
            "spc docs",
            "speech packet compiler help",
            "what is speech spc",
        ),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_SPEECH_SPC_STATUS_ROUTE_ID,
        label="Speech Packet Compiler status and lane inventory",
        target_module="engel_speech_spc",
        target_function="render_status",
        aliases=(
            "speech spc status",
            "spc status",
            "speech packet compiler status",
        ),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_SPEECH_SPC_LATEST_ROUTE_ID,
        label="Latest Speech Packet Compiler receipt",
        target_module="engel_speech_spc",
        target_function="render_latest",
        aliases=(
            "speech spc latest",
            "spc latest",
            "latest speech packet",
        ),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_SPEECH_SPC_COMPILE_ROUTE_ID,
        label="Preview a non-playing speech packet from text",
        target_module="engel_speech_spc",
        target_function="render_compile",
        aliases=(
            "compile speech",
            "speech spc compile",
            "spc compile",
        ),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_MIPL_AGENT_DOCS_ROUTE_ID,
        label="MIPL authored-agent work packet reference",
        target_module="engel_mipl_agent_work",
        target_function="render_docs",
        aliases=("mipl agent docs", "mipl agent help", "mipl agents help"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_MIPL_AGENT_SKILLS_ROUTE_ID,
        label="MIPL authored-agent skill catalog",
        target_module="engel_mipl_agent_work",
        target_function="render_skills",
        aliases=("mipl agent skills", "mipl agents skills"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_MIPL_AGENT_STATUS_ROUTE_ID,
        label="MIPL authored-agent registry and binding status",
        target_module="engel_mipl_agent_work",
        target_function="render_status",
        aliases=("mipl agent status", "mipl agents status"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_MIPL_AGENT_LIST_ROUTE_ID,
        label="MIPL authored-agent assigned task list",
        target_module="engel_mipl_agent_work",
        target_function="render_list",
        aliases=("mipl agent list", "mipl agents list"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_MODEL_INTAKE_LIST_ROUTE_ID,
        label="Model intake list -- manually ingested model files",
        target_module="engel_ai_manual_model_file_intake",
        target_function="render_list",
        aliases=("model intake list", "model file list", "intake list"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_MODEL_INTAKE_STATUS_ROUTE_ID,
        label="Model intake status -- model file intake system state",
        target_module="engel_ai_manual_model_file_intake",
        target_function="render_status",
        aliases=("model intake status", "model intake", "model file intake"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_MODEL_REVIEW_APPROVAL_STATUS_ROUTE_ID,
        label="Model review approval status -- AI model review approval state",
        target_module="engel_ai_model_review_approval",
        target_function="render_status",
        aliases=("model review approval status", "model approval status"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_MODEL_REVIEW_APPROVAL_LIST_ROUTE_ID,
        label="Model review approval list -- approved model list",
        target_module="engel_ai_model_review_approval",
        target_function="render_list",
        aliases=("model review approval list", "model approval list"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_NO_GENERATION_LOAD_CHECK_ROUTE_ID,
        label="No-generation load check status -- model load without generation check",
        target_module="engel_ai_no_generation_load_check",
        target_function="render_status",
        aliases=("no generation load check", "load check status"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_OFFLINE_RUNTIME_DRY_RUN_STATUS_ROUTE_ID,
        label="Offline runtime dry run status -- offline AI runtime dry run state",
        target_module="engel_ai_offline_runtime_dry_run",
        target_function="render_status",
        aliases=("offline runtime dry run status", "dry run status"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_OFFLINE_RUNTIME_DRY_RUN_MODELS_ROUTE_ID,
        label="Offline runtime dry run models -- available models for dry run",
        target_module="engel_ai_offline_runtime_dry_run",
        target_function="render_list_models",
        aliases=("offline runtime models", "dry run models list"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_LOCAL_RUNTIME_PATH_ROOTS_ROUTE_ID,
        label="Local runtime path roots -- configured path roots for local AI runtime",
        target_module="engel_ai_local_runtime_path_config",
        target_function="render_roots",
        aliases=("local runtime path roots", "runtime path roots"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_BQ_PHASE4_CONTRACT_ROUTE_ID,
        label="Browser Queen phase 4 contract -- phase 4 contract status",
        target_module="engel_browser_queen_phase4_contract",
        target_function="render_browser_queen_phase4_contract_status",
        aliases=("browser queen phase 4 contract", "bq phase 4", "phase 4 contract"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_BQ_PHASE5_CONTRACT_ROUTE_ID,
        label="Browser Queen phase 5 contract -- phase 5 contract status",
        target_module="engel_browser_queen_phase5_contract",
        target_function="render_browser_queen_phase5_contract_status",
        aliases=("browser queen phase 5 contract", "bq phase 5", "phase 5 contract"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_CANDIDATE_LEARNING_STATUS_ROUTE_ID,
        label="Candidate learning output review status",
        target_module="engel_candidate_learning_output_review",
        target_function="render_status",
        aliases=("candidate learning status", "learning output review status"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_CANDIDATE_REVIEW_DASHBOARD2_ROUTE_ID,
        label="Candidate review dashboard -- full candidate review view",
        target_module="engel_candidate_review_dashboard",
        target_function="render_dashboard",
        aliases=("candidate review dashboard full", "candidate dashboard"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_CANDIDATE_SET_APPROVAL_STATUS_ROUTE_ID,
        label="Candidate set approval status -- candidate set approval state",
        target_module="engel_candidate_set_approval",
        target_function="render_status",
        aliases=("set approval status", "candidate set approval state", "candidate set approval status"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_CHAT_EXPORT_INTAKE_STATUS_ROUTE_ID,
        label="Chat export intake status -- chat export intake system state",
        target_module="engel_chat_export_intake",
        target_function="render_status",
        aliases=("chat export intake status", "chat export status"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_CHAT_EXPORT_INTAKE_LIST_ROUTE_ID,
        label="Chat export intake list -- ingested chat export files",
        target_module="engel_chat_export_intake",
        target_function="render_list",
        aliases=("chat export intake list", "chat export list"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_CC_CANDIDATE_REVIEW_STATUS_ROUTE_ID,
        label="Code companion candidate review status",
        target_module="engel_code_companion_candidate_review_status",
        target_function="render_status",
        aliases=("code companion candidate review", "cc candidate review status"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_CC_FIX_CANDIDATE_INTAKE_STATUS_ROUTE_ID,
        label="Code companion fix candidate intake status",
        target_module="engel_code_companion_fix_candidate_intake",
        target_function="render_status",
        aliases=("cc fix candidate intake status", "fix candidate intake status"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_CC_FIX_CANDIDATE_INTAKE_LIST_ROUTE_ID,
        label="Code companion fix candidate intake list",
        target_module="engel_code_companion_fix_candidate_intake",
        target_function="render_list",
        aliases=("cc fix candidate intake list", "fix candidate intake list"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_CC_LOW_RISK_PATCH_RUNNER_ROUTE_ID,
        label="Code companion low risk patch runner status",
        target_module="engel_code_companion_low_risk_patch_runner",
        target_function="render_status",
        aliases=("low risk patch runner status", "cc low risk patch runner"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_CC_PASSWORD_GATE_INTEGRATION_ROUTE_ID,
        label="Code companion password gate integration status",
        target_module="engel_code_companion_password_gate_integration",
        target_function="render_status",
        aliases=("cc password gate integration", "password gate integration status"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_CC_PATCH_APPLICATION_GATE_STATUS_ROUTE_ID,
        label="Code companion patch application gate status",
        target_module="engel_code_companion_patch_application_gate",
        target_function="render_status",
        aliases=("patch application gate status", "cc patch gate status"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_CC_PATCH_APPLICATION_GATE_LIST_ROUTE_ID,
        label="Code companion patch application gate list",
        target_module="engel_code_companion_patch_application_gate",
        target_function="render_list",
        aliases=("patch application gate list", "cc patch gate list"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_CC_PATCH_APPLY_RECEIPT_STATUS_ROUTE_ID,
        label="Code companion patch apply approval receipt status",
        target_module="engel_code_companion_patch_apply_approval_receipt",
        target_function="render_status",
        aliases=("patch apply receipt status", "cc patch receipt status"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_CC_PATCH_APPLY_RECEIPT_LIST_ROUTE_ID,
        label="Code companion patch apply approval receipt list",
        target_module="engel_code_companion_patch_apply_approval_receipt",
        target_function="render_list",
        aliases=("patch apply receipt list", "cc patch receipt list"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_CC_PATCH_APPLY_DRY_RUN_STATUS_ROUTE_ID,
        label="Code companion patch apply dry run status",
        target_module="engel_code_companion_patch_apply_dry_run",
        target_function="render_status",
        aliases=("patch apply dry run status", "cc dry run status"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_CC_PATCH_APPLY_DRY_RUN_LIST_ROUTE_ID,
        label="Code companion patch apply dry run list",
        target_module="engel_code_companion_patch_apply_dry_run",
        target_function="render_list",
        aliases=("patch apply dry run list", "cc dry run list"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_CC_PATCH_BUNDLE_DRAFT_STATUS_ROUTE_ID,
        label="Code companion patch bundle draft status",
        target_module="engel_code_companion_patch_bundle_draft",
        target_function="render_status",
        aliases=("patch bundle draft status", "cc patch bundle status"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_CC_PATCH_BUNDLE_DRAFT_LIST_ROUTE_ID,
        label="Code companion patch bundle draft list",
        target_module="engel_code_companion_patch_bundle_draft",
        target_function="render_list",
        aliases=("patch bundle draft list", "cc patch bundle list"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_CC_PATCH_CLASS_ALLOWLIST_STATUS_ROUTE_ID,
        label="Code companion patch class allowlist status",
        target_module="engel_code_companion_patch_class_allowlist",
        target_function="render_status",
        aliases=("patch class allowlist status", "cc patch allowlist status"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_CC_PATCH_CLASS_ALLOWLIST_CLASSES_ROUTE_ID,
        label="Code companion patch class allowlist -- allowed patch classes",
        target_module="engel_code_companion_patch_class_allowlist",
        target_function="render_classes",
        aliases=("patch class allowlist classes", "cc patch classes"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_CC_PATCH_PLAN_PREVIEW_STATUS_ROUTE_ID,
        label="Code companion patch plan preview status",
        target_module="engel_code_companion_patch_plan_preview",
        target_function="render_status",
        aliases=("patch plan preview status", "cc patch plan status"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_CC_PATCH_PLAN_PREVIEW_LIST_ROUTE_ID,
        label="Code companion patch plan preview list",
        target_module="engel_code_companion_patch_plan_preview",
        target_function="render_list",
        aliases=("patch plan preview list", "cc patch plan list"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_CC_PATCH_STATUS_SURFACE_ROUTE_ID,
        label="Code companion patch status surface -- full patch pipeline view",
        target_module="engel_code_companion_patch_status_surface",
        target_function="render_status",
        aliases=("patch status surface", "cc patch status surface"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_CC_PROTECTED_PATCH_APPLY_ROUTE_ID,
        label="Code companion protected patch apply status",
        target_module="engel_code_companion_protected_patch_apply",
        target_function="render_status",
        aliases=("protected patch apply status", "cc protected patch status"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_DAILY_CYCLE_RECEIPT_LIST_ROUTE_ID,
        label="Daily cycle receipt list -- completed daily cycle receipts",
        target_module="engel_daily_cycle_status_surface",
        target_function="render_receipt_list",
        aliases=("daily cycle receipt list", "daily cycle receipts"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_EXTERNAL_MEMORY_ROOTS_ROUTE_ID,
        label="External memory roots status -- E/F/G external drive memory roots",
        target_module="engel_external_memory_roots",
        target_function="render_external_memory_status",
        aliases=("external memory roots status", "external memory roots", "external memory status"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_FIX_CANDIDATE_QUEUE_STATUS_ROUTE_ID,
        label="Fix candidate queue status -- self-fix candidate queue state",
        target_module="engel_fix_candidate_queue",
        target_function="render_status",
        aliases=("fix candidate queue status", "fix queue status"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_FIX_CANDIDATE_QUEUE_LIST_ROUTE_ID,
        label="Fix candidate queue list -- queued self-fix candidates",
        target_module="engel_fix_candidate_queue",
        target_function="render_list",
        aliases=("fix candidate queue list", "fix queue list"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_GUIDED_LIBRARY_DRAFT_REPORT_ROUTE_ID,
        label="Guided library draft report -- library review draft report",
        target_module="engel_guided_library_review_draft_report",
        target_function="render_draft_report",
        aliases=("guided library draft report", "library draft report"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_HUMAN_REVIEW_DRAFT_PREVIEW_ROUTE_ID,
        label="Human review draft preview -- draft receipt preview surface",
        target_module="engel_human_review_receipt_draft_surface",
        target_function="render_receipt_draft_preview",
        aliases=("human review draft preview", "review draft preview"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_LEARNING_JOB_QUEUE_STATUS_ROUTE_ID,
        label="Learning job queue status -- self-learning job queue state",
        target_module="engel_learning_job_queue",
        target_function="render_status",
        aliases=("learning job queue status", "learning queue status"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_LEARNING_JOB_QUEUE_LIST_ROUTE_ID,
        label="Learning job queue list -- queued learning jobs",
        target_module="engel_learning_job_queue",
        target_function="render_list",
        aliases=("learning job queue list", "learning queue list"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_MEMORY_ROOTS_STORAGE_STATUS_ROUTE_ID,
        label="Memory roots storage layout status",
        target_module="engel_memory_roots_storage_layout",
        target_function="render_status",
        aliases=("memory roots storage status", "memory roots status"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_MEMORY_ROOTS_STORAGE_ROOTS_ROUTE_ID,
        label="Memory roots storage layout roots -- configured memory root paths",
        target_module="engel_memory_roots_storage_layout",
        target_function="render_roots",
        aliases=("memory roots storage roots", "memory roots layout"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_REMOTE_WORKER_APP_SCAFFOLD_ROUTE_ID,
        label="Remote worker app scaffold status -- Android remote worker app scaffold",
        target_module="engel_remote_worker_app_scaffold",
        target_function="render_status",
        aliases=("remote worker app scaffold", "worker app scaffold status"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_RESEARCH_TO_FIX_LOOP_ROUTE_ID,
        label="Research to fix loop status -- research-to-fix pipeline state",
        target_module="engel_research_to_fix_loop",
        target_function="render_status",
        aliases=("research to fix loop status", "research fix loop"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_RESEARCH_TOGGLE_WORKER_ROUTE_ID,
        label="Research toggle worker status -- research toggle worker state",
        target_module="engel_research_toggle_worker",
        target_function="render_status",
        aliases=("research toggle worker status", "toggle worker status"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_SELF_LEARNING_CONTROLLER_ROUTE_ID,
        label="Self-learning run controller status",
        target_module="engel_self_learning_run_controller",
        target_function="render_status",
        aliases=("self learning run controller status", "self learning controller"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_SYSTEM_INTEGRATION_CHECK_LINKS_ROUTE_ID,
        label="System integration check links -- integration link verification",
        target_module="engel_system_integration_status",
        target_function="render_check_links",
        aliases=("system integration check links", "integration check links"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_TRAINING_TRUSTED_MEMORY_STATUS_ROUTE_ID,
        label="Training trusted memory status",
        target_module="engel_training_trusted_memory",
        target_function="render_status",
        aliases=("training trusted memory status", "training memory status"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_TRAINING_TRUSTED_MEMORY_PREVIEW_ROUTE_ID,
        label="Training trusted memory preview -- trusted memory content preview",
        target_module="engel_training_trusted_memory",
        target_function="render_preview",
        aliases=("training trusted memory preview", "training memory preview"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_WHOLE_SYSTEM_AUDIT_STATUS_ROUTE_ID,
        label="Whole system incomplete audit status",
        target_module="engel_whole_system_incomplete_audit",
        target_function="render_status",
        aliases=("whole system audit status", "incomplete audit status"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_AI_GROWTH_FOLDER_STATUS_ROUTE_ID,
        label="AI growth dashboard folder status",
        target_module="engel_ai_growth_dashboard",
        target_function="render_folder_status",
        aliases=("ai growth folder status", "growth dashboard folder"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_RUNTIME_READINESS_MODEL_ROUTE_ID,
        label="Runtime readiness model summary -- AI model readiness check",
        target_module="engel_ai_runtime_readiness",
        target_function="render_model_summary",
        aliases=("runtime readiness model summary", "readiness model summary"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_RUNTIME_READINESS_LIBRARY_ROUTE_ID,
        label="Runtime readiness library summary -- library readiness check",
        target_module="engel_ai_runtime_readiness",
        target_function="render_library_summary",
        aliases=("runtime readiness library summary", "readiness library summary"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_RUNTIME_READINESS_SAFETY_ROUTE_ID,
        label="Runtime readiness safety summary -- safety readiness check",
        target_module="engel_ai_runtime_readiness",
        target_function="render_safety_summary",
        aliases=("runtime readiness safety summary", "readiness safety summary"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_RUNTIME_READINESS_REMOTE_WORKER_ROUTE_ID,
        label="Runtime readiness remote worker summary",
        target_module="engel_ai_runtime_readiness",
        target_function="render_remote_worker_summary",
        aliases=("runtime readiness remote worker", "readiness remote worker"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_RUNTIME_READINESS_CODE_COMPANION_ROUTE_ID,
        label="Runtime readiness code companion summary",
        target_module="engel_ai_runtime_readiness",
        target_function="render_code_companion_summary",
        aliases=("runtime readiness code companion", "readiness code companion"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_RUNTIME_READINESS_NEXT_ROUTE_ID,
        label="Runtime readiness next summary -- next steps for readiness",
        target_module="engel_ai_runtime_readiness",
        target_function="render_next_summary",
        aliases=("runtime readiness next steps", "readiness next summary"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_BOUNDED_LOCAL_CHAT_SMOKE_ROUTE_ID,
        label="Bounded local chat smoke test report",
        target_module="engel_ai_bounded_local_chat_smoke",
        target_function="render_report",
        aliases=("bounded local chat smoke", "local chat smoke report"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_FIRST_LOCAL_RESPONSE_SMOKE_ROUTE_ID,
        label="First local response smoke test report",
        target_module="engel_ai_first_local_response_smoke",
        target_function="render_report",
        aliases=("first local response smoke", "first response smoke report"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_FIRST_LOCAL_RESPONSE_SMOKE_FIX_ROUTE_ID,
        label="First local response smoke exit-fix report",
        target_module="engel_ai_first_local_response_smoke_exit_fix",
        target_function="render_report",
        aliases=("first local response smoke fix", "smoke exit fix report"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_OUTPUT_FILTER_TUNING_ROUTE_ID,
        label="Output filter tuning report -- first response output filter state",
        target_module="engel_ai_first_response_output_filter_tuning",
        target_function="render_report",
        aliases=("output filter tuning report", "response filter tuning"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_LLAMA_SWAP_APPROVAL_ROUTE_ID,
        label="llama.cpp runtime swap approval report",
        target_module="engel_ai_llama_cpp_runtime_swap_approval",
        target_function="render_report",
        aliases=("llama swap approval report", "runtime swap approval"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_APPROVED_MEMORY_CONTEXT_BRIDGE_ROUTE_ID,
        label="Approved memory context preview bridge report",
        target_module="engel_ai_local_approved_memory_context_preview",
        target_function="render_bridge_report",
        aliases=("approved memory context bridge", "memory context bridge report"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_APPROVED_MEMORY_READBACK_BRIDGE_ROUTE_ID,
        label="Approved memory readback bridge report",
        target_module="engel_ai_local_approved_memory_readback",
        target_function="render_bridge_report",
        aliases=("approved memory readback bridge", "memory readback bridge report"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_LOCAL_CHAT_PROMPT_DRAFT_ROUTE_ID,
        label="Local chat prompt draft report",
        target_module="engel_ai_local_chat_prompt_draft",
        target_function="render_report",
        aliases=("local chat prompt draft report", "chat prompt draft"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_LOCAL_CHAT_SESSION_DRAFT_ROUTE_ID,
        label="Local chat session draft report",
        target_module="engel_ai_local_chat_session_draft",
        target_function="render_report",
        aliases=("local chat session draft report", "chat session draft"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_LOCAL_CHAT_MEMORY_REVIEW_BRIDGE_ROUTE_ID,
        label="Local chat session memory review bridge report",
        target_module="engel_ai_local_chat_session_memory_candidate_review_and_approved_write",
        target_function="render_bridge_report",
        aliases=("local chat memory review bridge", "chat memory review bridge"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_LOCAL_CHAT_SESSION_REVIEW_BRIDGE_ROUTE_ID,
        label="Local chat session review bridge report",
        target_module="engel_ai_local_chat_session_review",
        target_function="render_bridge_report",
        aliases=("local chat session review bridge", "chat session review bridge"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_LOCAL_OPEN_CHAT_BRIDGE_ROUTE_ID,
        label="Local open chat supervised run bridge report",
        target_module="engel_ai_local_open_chat_supervised_run",
        target_function="render_bridge_report",
        aliases=("local open chat bridge", "open chat bridge report"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_LOCAL_OPEN_CHAT_BOUNDED_RUN_REQUEST_ROUTE_ID,
        label="Rust local open chat bounded run request route report",
        target_module="engel_ai_main_rust_local_chat_bridge",
        target_function="render_bounded_run_request_route_report",
        aliases=("local chat bounded run request route", "bounded local chat request route"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_LOCAL_OPEN_CHAT_BOUNDED_RUN_EXECUTION_ROUTE_ID,
        label="Rust local open chat bounded run execution route report",
        target_module="engel_ai_main_rust_local_chat_bridge",
        target_function="render_bounded_run_execution_route_report",
        aliases=("local chat bounded run execution route", "bounded local chat execution route"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_PERSISTENT_CHAT_PLAN_BRIDGE_ROUTE_ID,
        label="Persistent chat supervised runtime plan bridge report",
        target_module="engel_ai_persistent_chat_supervised_runtime_plan",
        target_function="render_bridge_report",
        aliases=("persistent chat plan bridge", "chat plan bridge report"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_PERSISTENT_CHAT_SESSION_STATUS_ROUTE_ID,
        label="Rust persistent chat supervised session status route report",
        target_module="engel_ai_main_rust_local_chat_bridge",
        target_function="render_persistent_session_status_route_report",
        aliases=("persistent chat session status route", "local chat persistent session status route"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_PERSISTENT_CHAT_SESSION_START_ROUTE_ID,
        label="Rust persistent chat supervised session start route report",
        target_module="engel_ai_main_rust_local_chat_bridge",
        target_function="render_persistent_session_start_route_report",
        aliases=("persistent chat session start route", "local chat persistent session start route"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_PERSISTENT_CHAT_SESSION_STOP_ROUTE_ID,
        label="Rust persistent chat supervised session stop route report",
        target_module="engel_ai_main_rust_local_chat_bridge",
        target_function="render_persistent_session_stop_route_report",
        aliases=("persistent chat session stop route", "local chat persistent session stop route"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_RUNTIME_CANDIDATE_ALT_ROUTE_ID,
        label="Runtime candidate alt command style report",
        target_module="engel_ai_runtime_candidate_alt_command_style",
        target_function="render_report",
        aliases=("runtime candidate alt style", "candidate alt command report"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_RUNTIME_CANDIDATE_FAILURE_ROUTE_ID,
        label="Runtime candidate failure diagnosis report",
        target_module="engel_ai_runtime_candidate_failure_diagnosis",
        target_function="render_report",
        aliases=("runtime candidate failure diagnosis", "candidate failure report"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_RUNTIME_CANDIDATE_VALIDATION_ROUTE_ID,
        label="Runtime candidate validation replay report",
        target_module="engel_ai_runtime_candidate_validation_replay",
        target_function="render_report",
        aliases=("runtime candidate validation replay", "candidate validation report"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_LAN_PAIRING_STATUS2_ROUTE_ID,
        label="LAN pairing worker status -- raw LAN pairing status endpoint",
        target_module="engel_remote_worker_lan_pairing",
        target_function="render_status",
        aliases=("lan pairing worker status", "lan pairing raw status"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_LAN_PAIRING_TOKEN2_ROUTE_ID,
        label="LAN pairing worker token -- raw LAN pairing token endpoint",
        target_module="engel_remote_worker_lan_pairing",
        target_function="render_token",
        aliases=("lan pairing worker token", "lan pairing raw token"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_RESEARCH_OFFICE_QUEEN_LINKS_ROUTE_ID,
        label="Research office queen links -- research office queen link map",
        target_module="engel_research_office_data",
        target_function="render_research_office_queen_links",
        aliases=("research office queen links", "office queen links"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_RESEARCH_OFFICE_PERMISSIONS_ROUTE_ID,
        label="Research office permissions -- research office permission table",
        target_module="engel_research_office_data",
        target_function="render_research_office_permissions",
        aliases=("research office permissions", "office permissions"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_CC_PRODUCT_CONTEXT_VIEW_ROUTE_ID,
        label="Code companion product context view -- selected product context",
        target_module="engel_code_companion",
        target_function="render_product_context_view",
        aliases=("code companion product context view", "cc product context view"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_CC_CONTEXTUAL_TALK_ROUTE_ID,
        label="Code companion contextual talk -- contextual chat for selected product",
        target_module="engel_code_companion_contextual_talk",
        target_function="render_context_for_selected_product",
        aliases=("code companion contextual talk", "cc contextual talk"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_EXTERNAL_MEMORY_ARCHIVE_SHELF_ROUTE_ID,
        label="External memory archive shelf -- drive-specific archive shelf view",
        target_module="engel_external_memory_status",
        target_function="render_external_memory_archive_shelf",
        aliases=("external memory archive shelf", "memory archive shelf"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_ROUTE_EXPLORER_DETAILS_ROUTE_ID,
        label="Route explorer details -- details for a specific route ID",
        target_module="engel_route_explorer",
        target_function="render_route_details",
        aliases=("route explorer details", "route details"),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=MINOR_TOOLS_LIST_ROUTE_ID,
        label="Engel App vendored minor-tools inventory",
        target_module="engel_minor_tools_runner",
        target_function="render_minor_tools_list",
        aliases=(
            "engel minor tools",
            "engel minor tools list",
            "list engel minor tools",
            "show engel minor tools",
            "engel tools list",
            "engel vendored tools",
            "what minor tools does engel have",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_HUMANIZER_STATUS_ROUTE_ID,
        label="Engel Humanizer (de-AI-ify writing skill) status",
        target_module="engel_minor_tools_runner",
        target_function="render_humanizer_status",
        aliases=(
            "engel humanizer status",
            "engel humanizer",
            "show engel humanizer",
            "humanizer status",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_NATIVE_AGENT_STATUS_ROUTE_ID,
        label="Engel Native Agent status",
        target_module="engel_minor_tools_runner",
        target_function="render_native_agent_status",
        aliases=(
            "engel native agent status",
            "engel native agent",
            "show engel native agent",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_IDE_STATUS_ROUTE_ID,
        label="Engel IDE Companion status",
        target_module="engel_minor_tools_runner",
        target_function="render_ide_status",
        aliases=(
            "engel ide status",
            "engel ide",
            "show engel ide",
            "engel ide companion",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_EVOLUTION_LAB_STATUS_ROUTE_ID,
        label="Engel Evolution Lab status",
        target_module="engel_minor_tools_runner",
        target_function="render_evolution_lab_status",
        aliases=(
            "engel evolution lab status",
            "engel evolution lab",
            "show engel evolution lab",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_KNOWLEDGE_GRAPH_STATUS_ROUTE_ID,
        label="Engel Knowledge Graph status",
        target_module="engel_minor_tools_runner",
        target_function="render_knowledge_graph_status",
        aliases=(
            "engel knowledge graph status",
            "engel knowledge graph",
            "show engel knowledge graph",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_EVOLUTION_ENGINE_STATUS_ROUTE_ID,
        label="Engel Evolution Engine status",
        target_module="engel_minor_tools_runner",
        target_function="render_evolution_engine_status",
        aliases=(
            "engel evolution engine status",
            "engel evolution engine",
            "show engel evolution engine",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_HUMANIZER_FEATURES_ROUTE_ID,
        label="Engel Humanizer features and abilities",
        target_module="engel_minor_tools_runner",
        target_function="render_humanizer_features",
        aliases=(
            "engel humanizer features",
            "what can engel humanizer do",
            "humanizer abilities",
            "humanizer skill features",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_HUMANIZER_DOCS_ROUTE_ID,
        label="Engel Humanizer documentation index",
        target_module="engel_minor_tools_runner",
        target_function="render_humanizer_docs",
        aliases=(
            "engel humanizer docs",
            "humanizer documentation",
            "show humanizer readme",
            "humanizer readme",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_NATIVE_AGENT_FEATURES_ROUTE_ID,
        label="Engel Native Agent features and abilities",
        target_module="engel_minor_tools_runner",
        target_function="render_native_agent_features",
        aliases=(
            "engel native agent features",
            "what can engel native agent do",
            "engel native agent abilities",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_NATIVE_AGENT_DOCS_ROUTE_ID,
        label="Engel Native Agent documentation index",
        target_module="engel_minor_tools_runner",
        target_function="render_native_agent_docs",
        aliases=(
            "engel native agent docs",
            "native agent documentation",
            "show native agent readme",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_IDE_FEATURES_ROUTE_ID,
        label="Engel IDE Companion features and abilities",
        target_module="engel_minor_tools_runner",
        target_function="render_ide_features",
        aliases=(
            "engel ide features",
            "what can engel ide do",
            "engel ide abilities",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_IDE_DOCS_ROUTE_ID,
        label="Engel IDE Companion documentation index",
        target_module="engel_minor_tools_runner",
        target_function="render_ide_docs",
        aliases=(
            "engel ide docs",
            "ide companion documentation",
            "show ide companion readme",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_EVOLUTION_LAB_FEATURES_ROUTE_ID,
        label="Engel Evolution Lab features and abilities",
        target_module="engel_minor_tools_runner",
        target_function="render_evolution_lab_features",
        aliases=(
            "engel evolution lab features",
            "what can engel evolution lab do",
            "engel evolution lab abilities",
            "engel ga features",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_EVOLUTION_LAB_DOCS_ROUTE_ID,
        label="Engel Evolution Lab documentation index",
        target_module="engel_minor_tools_runner",
        target_function="render_evolution_lab_docs",
        aliases=(
            "engel evolution lab docs",
            "evolution lab documentation",
            "show evolution lab readme",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_KNOWLEDGE_GRAPH_FEATURES_ROUTE_ID,
        label="Engel Knowledge Graph features and abilities",
        target_module="engel_minor_tools_runner",
        target_function="render_knowledge_graph_features",
        aliases=(
            "engel knowledge graph features",
            "what can engel knowledge graph do",
            "engel knowledge graph abilities",
            "knowledge graph features",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_KNOWLEDGE_GRAPH_DOCS_ROUTE_ID,
        label="Engel Knowledge Graph documentation index",
        target_module="engel_minor_tools_runner",
        target_function="render_knowledge_graph_docs",
        aliases=(
            "engel knowledge graph docs",
            "knowledge graph documentation",
            "show knowledge graph readme",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_EVOLUTION_ENGINE_FEATURES_ROUTE_ID,
        label="Engel Evolution Engine features and abilities",
        target_module="engel_minor_tools_runner",
        target_function="render_evolution_engine_features",
        aliases=(
            "engel evolution engine features",
            "what can engel evolution engine do",
            "engel evolution engine abilities",
            "gep evolution features",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_EVOLUTION_ENGINE_DOCS_ROUTE_ID,
        label="Engel Evolution Engine documentation index",
        target_module="engel_minor_tools_runner",
        target_function="render_evolution_engine_docs",
        aliases=(
            "engel evolution engine docs",
            "evolution engine documentation",
            "show evolution engine readme",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_HUMANIZER_INVOKE_ROUTE_ID,
        label="Engel Humanizer invoke (skill prompt ready to apply)",
        target_module="engel_minor_tools_runner",
        target_function="render_humanizer_invoke",
        aliases=(
            "engel humanizer invoke",
            "humanize text",
            "apply engel humanizer",
            "engel humanizer apply",
            "engel humanizer skill",
            "use humanizer",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_NATIVE_AGENT_LAUNCH_DASHBOARD_ROUTE_ID,
        label="Engel Native Agent launch dashboard (bounded host subprocess)",
        target_module="engel_minor_tools_runner",
        target_function="render_native_agent_launch_dashboard",
        aliases=(
            "engel native agent launch dashboard",
            "launch engel native agent dashboard",
            "engel native agent dashboard",
            "open engel native agent",
            "start engel native agent dashboard",
        ),
        read_only=False,
        status_only=False,
        no_background_worker=False,
        no_visible_ui_change=False,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_NATIVE_AGENT_LAUNCH_AGENT_ROUTE_ID,
        label="Engel Native Agent launch background agent (bounded host subprocess)",
        target_module="engel_minor_tools_runner",
        target_function="render_native_agent_launch_agent",
        aliases=(
            "engel native agent launch agent",
            "start engel native agent",
            "engel native agent run",
            "run engel native agent",
            "engel native background agent",
        ),
        read_only=False,
        status_only=False,
        no_background_worker=False,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_IDE_INSTALL_TO_PROJECT_ROUTE_ID,
        label="Engel IDE Companion install rules/agents/skills/workflows to active Engel project",
        target_module="engel_minor_tools_runner",
        target_function="render_ide_install_to_project",
        aliases=(
            "engel ide install",
            "engel ide install to project",
            "install engel ide rules",
            "copy engel ide rules",
            "apply engel ide",
            "engel ide activate",
        ),
        read_only=False,
        status_only=False,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_EVOLUTION_LAB_HELP_ROUTE_ID,
        label="Engel Evolution Lab help (uv run engel_darwin --help inside WSL Ubuntu)",
        target_module="engel_minor_tools_runner",
        target_function="render_evolution_lab_help",
        aliases=(
            "engel evolution lab help",
            "engel evolution lab --help",
            "run engel evolution lab help",
            "engel ga help",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_EVOLUTION_LAB_RUN_EXAMPLE_ROUTE_ID,
        label="Engel Evolution Lab run example (bounded WSL Stage 3 action)",
        target_module="engel_minor_tools_runner",
        target_function="render_evolution_lab_run_example",
        aliases=(
            "engel evolution lab run example",
            "engel evolution lab parrot",
            "run engel evolution lab parrot",
            "engel evolution lab demo",
            "engel ga example",
        ),
        read_only=False,
        status_only=False,
        no_provider_model_network=False,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_KNOWLEDGE_GRAPH_HELP_ROUTE_ID,
        label="Engel Knowledge Graph help (engel_graphify --help inside WSL Ubuntu)",
        target_module="engel_minor_tools_runner",
        target_function="render_knowledge_graph_help",
        aliases=(
            "engel knowledge graph help",
            "engel knowledge graph --help",
            "run engel knowledge graph help",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_KNOWLEDGE_GRAPH_BUILD_ROUTE_ID,
        label="Engel Knowledge Graph build (bounded WSL Stage 3 action)",
        target_module="engel_minor_tools_runner",
        target_function="render_knowledge_graph_build",
        aliases=(
            "engel knowledge graph build",
            "engel knowledge graph run",
            "engel knowledge graph a folder",
            "engel knowledge graph index",
            "build knowledge graph",
        ),
        read_only=False,
        status_only=False,
        no_provider_model_network=False,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_EVOLUTION_ENGINE_HELP_ROUTE_ID,
        label="Engel Evolution Engine help (engel_evolver --help inside WSL Ubuntu)",
        target_module="engel_minor_tools_runner",
        target_function="render_evolution_engine_help",
        aliases=(
            "engel evolution engine help",
            "engel evolution engine --help",
            "run engel evolution engine help",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_EVOLUTION_ENGINE_RUN_ROUTE_ID,
        label="Engel Evolution Engine run once (bounded WSL Stage 3 action)",
        target_module="engel_minor_tools_runner",
        target_function="render_evolution_engine_run",
        aliases=(
            "engel evolution engine run",
            "run engel evolution engine",
            "engel evolution engine invoke",
            "engel evolution engine in repo",
            "engel gep evolve",
        ),
        read_only=False,
        status_only=False,
        no_provider_model_network=False,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_AI_CONNECTORS_STATUS_ROUTE_ID,
        label="Engel AI Connector Hub status",
        target_module="engel_ai_connector_hub",
        target_function="render_ai_connector_status",
        aliases=(
            "engel ai connector status",
            "ai connector status",
            "show ai connectors",
            "other ai connectors",
            "connect other ai",
            "connect other ais",
            "how can engel connect other ai",
            "how can engel connect other ais",
            "engel connector hub",
            "engel ai connectors",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_AI_CONNECTORS_ADAPTERS_ROUTE_ID,
        label="Engel AI Connector Hub adapter inventory",
        target_module="engel_ai_connector_hub",
        target_function="render_ai_connector_adapters",
        aliases=(
            "show hermes ai adapters",
            "show engel ai adapters",
            "ai connector adapters",
            "engel connector adapters",
            "other ai adapter inventory",
            "show connector inventory",
            "show provider plugins",
            "show acp adapter",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_AI_CONNECTORS_BLUEPRINT_ROUTE_ID,
        label="Engel AI Connector Hub blueprint",
        target_module="engel_ai_connector_hub",
        target_function="render_ai_connector_blueprint",
        aliases=(
            "ai connector blueprint",
            "engel connector blueprint",
            "copy hermes connector pattern",
            "copy hermes ai pattern",
            "how to add another ai to engel",
            "how to connect another ai to engel",
            "make other ai part of engel",
            "engel ai connector pattern",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_AI_CONNECTORS_RULES_ROUTE_ID,
        label="Engel AI Connector Hub rules",
        target_module="engel_ai_connector_hub",
        target_function="render_ai_connector_rules",
        aliases=(
            "ai connector rules",
            "engel connector rules",
            "outside ai connector rules",
            "rules for connecting other ai",
            "ai connector blockers",
            "engel ai connector safety",
            "new phase connector rules",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_AI_CONNECTORS_ZIP_AUDIT_ROUTE_ID,
        label="Engel AI Connector Hub Hermes zip audit",
        target_module="engel_ai_connector_hub",
        target_function="render_ai_connector_zip_audit",
        aliases=(
            "hermes zip audit",
            "audit hermes zip",
            "hermes source audit",
            "show hermes connector source",
            "show hermes provider docs",
            "compare hermes source to engel",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_ACCOUNT_CONNECTOR_STATUS_ROUTE_ID,
        label="Engel Account Connector status",
        target_module="engel_account_connector",
        target_function="render_account_connector_status",
        aliases=(
            "connect my account",
            "connect account",
            "connect account to engel",
            "connect my account to engel",
            "connect my ai account",
            "connect provider account",
            "engel account connector",
            "account connector",
            "engel account status",
            "account connection status",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_ACCOUNT_CONNECTOR_PROVIDERS_ROUTE_ID,
        label="Engel Account Connector provider choices",
        target_module="engel_account_connector",
        target_function="render_account_connector_providers",
        aliases=(
            "show account providers",
            "account providers",
            "show provider accounts",
            "which accounts can engel connect",
            "what accounts can engel connect",
            "show login providers",
            "show ai account providers",
            "provider account list",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_ACCOUNT_CONNECTOR_SETUP_ROUTE_ID,
        label="Engel Account Connector setup path",
        target_module="engel_account_connector",
        target_function="render_account_connector_setup",
        aliases=(
            "account setup in engel",
            "engel account setup",
            "setup account connection",
            "setup my account in engel",
            "how do i connect my account in engel",
            "how to connect account in engel",
            "how to login to engel",
            "engel login setup",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_ACCOUNT_CONNECTOR_SAFETY_ROUTE_ID,
        label="Engel Account Connector safety",
        target_module="engel_account_connector",
        target_function="render_account_connector_safety",
        aliases=(
            "account connection safety",
            "account secrets safety",
            "where does engel store accounts",
            "where does engel store secrets",
            "should i paste my api key",
            "should i paste my token",
            "api key safety",
            "oauth token safety",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_ROUTE_EXPLORER_ROUTE_ID,
        label="Engel Route Explorer and Super Swarm route catalog",
        target_module="engel_route_explorer",
        target_function="render_route_explorer",
        aliases=(
            "route explorer",
            "engel route explorer",
            "show engel routes",
            "show all routes",
            "show all engel routes",
            "show route menu",
            "show command menu",
            "easy commands",
            "help me use engel",
            "what can i do",
            "what commands can engel run",
            "what can i ask engel",
            "show super swarm routes",
            "super swarm routes",
            "superswarm routes",
            "show routes in super swarm",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_ROUTE_SEARCH_ROUTE_ID,
        label="Route search — find routes by keyword",
        target_module="engel_route_explorer",
        target_function="render_route_search",
        aliases=(
            "route search",
            "engel route search",
            "find route",
            "search routes",
            "find command",
            "search commands",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_CAPABILITIES_LIST_ROUTE_ID,
        label="Engel AI full vendored capabilities inventory (all 12 projects)",
        target_module="engel_minor_tools_runner",
        target_function="render_capabilities_list",
        aliases=(
            "engel capabilities",
            "engel capabilities list",
            "what can engel do",
            "engel features",
            "engel abilities",
            "list engel projects",
            "engel inventory",
            "show all engel features",
            "all engel routes",
            "engel project inventory",
        ),
    ),
    # ---- Stage 4: Engel AI = hermes-agent native (top-level capability surface) ----
    EngelAIUpdateRoute(
        route_id=ENGEL_IDENTITY_ROUTE_ID,
        label="Engel AI identity (Stage 4 hermes-agent native)",
        target_module="engel_engel_agent_runner",
        target_function="render_engel_identity",
        aliases=(
            "engel identity",
            "what is engel",
            "what is engel ai",
            "engel ai identity",
            "engel architecture",
            "engel ai architecture",
            "engel hermes",
            "is engel hermes",
            "stage 4 identity",
            "stage 4 amendment",
            "stage 4 autonomy",
            "stage four",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_NATIVE_GATEWAY_START_ROUTE_ID,
        label="Engel native gateway start (hermes-agent gateway)",
        target_module="engel_engel_agent_runner",
        target_function="render_engel_agent_gateway_start",
        aliases=(
            "native gateway start",
            "engel gateway start",
            "start engel gateway",
            "engel start gateway",
            "engel ai gateway start",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_NATIVE_GATEWAY_STOP_ROUTE_ID,
        label="Engel native gateway stop",
        target_module="engel_engel_agent_runner",
        target_function="render_engel_agent_gateway_stop",
        aliases=(
            "native gateway stop",
            "engel gateway stop",
            "stop engel gateway",
            "engel stop gateway",
            "engel ai gateway stop",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_NATIVE_GATEWAY_STATUS_ROUTE_ID,
        label="Engel native gateway status",
        target_module="engel_engel_agent_runner",
        target_function="render_engel_agent_gateway_status",
        aliases=(
            "native gateway status",
            "engel gateway status",
            "engel gateway",
            "is engel gateway running",
            "engel ai gateway status",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_NATIVE_CRON_LIST_ROUTE_ID,
        label="Engel native cron list (hermes-agent cron)",
        target_module="engel_engel_agent_runner",
        target_function="render_engel_agent_cron_list",
        aliases=(
            "native cron list",
            "engel cron list",
            "list engel cron",
            "show engel cron jobs",
            "engel cron jobs",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_NATIVE_CRON_STATUS_ROUTE_ID,
        label="Engel native cron status",
        target_module="engel_engel_agent_runner",
        target_function="render_engel_agent_cron_status",
        aliases=(
            "native cron status",
            "engel cron status",
            "engel cron",
            "is engel cron running",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_NATIVE_MEMORY_STATUS_ROUTE_ID,
        label="Engel native memory status (hermes-agent memory)",
        target_module="engel_engel_agent_runner",
        target_function="render_engel_agent_memory_status",
        aliases=(
            "native memory status",
            "engel memory status",
            "engel memory",
            "show engel memory",
            "engel ai memory status",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_NATIVE_SKILLS_LIST_ROUTE_ID,
        label="Engel native skills list (hermes-agent skills)",
        target_module="engel_engel_agent_runner",
        target_function="render_engel_agent_skills_list",
        aliases=(
            "native skills list",
            "engel skills list",
            "engel skills",
            "list engel skills",
            "show engel skills",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_SAVED_SKILLS_LIST_ROUTE_ID,
        label="Engel saved skills list (saved-skill registry status)",
        target_module="engel_saved_skills_list",
        target_function="render_saved_skills_list",
        aliases=(
            "saved skills list",
            "engel saved skills",
            "list saved skills",
            "show saved skills",
            "saved skills",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_FEATURE_MAP_ROUTE_ID,
        label="Engel feature map (user-facing map of Engel AI Main and its parts)",
        target_module="engel_feature_map",
        target_function="render_feature_map",
        aliases=(
            "feature map",
            "engel feature map",
            "pstack feature map",
            "show feature map",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_FEATURE_MAP_DRAFT_PR_ROUTE_ID,
        label="Open a draft pull request on the public Engel source",
        target_module="engel_feature_map",
        target_function="render_open_draft_pr",
        aliases=(
            "open draft pr",
            "open draft pull request",
            "create draft pr",
            "create draft pull request",
        ),
        read_only=False,
        status_only=False,
        no_provider_model_network=False,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_NATIVE_SESSIONS_LIST_ROUTE_ID,
        label="Engel native sessions list (hermes-agent sessions)",
        target_module="engel_engel_agent_runner",
        target_function="render_engel_agent_sessions_list",
        aliases=(
            "native sessions list",
            "engel sessions list",
            "engel sessions",
            "list engel sessions",
            "show engel sessions",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_NATIVE_SESSIONS_STATS_ROUTE_ID,
        label="Engel native sessions stats (hermes-agent session stats)",
        target_module="engel_engel_agent_runner",
        target_function="render_engel_agent_sessions_stats",
        aliases=(
            "native sessions stats",
            "engel sessions stats",
            "engel session stats",
            "show engel session stats",
            "engel ai sessions stats",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_NATIVE_PLUGINS_LIST_ROUTE_ID,
        label="Engel native plugins list (hermes-agent plugins)",
        target_module="engel_engel_agent_runner",
        target_function="render_engel_agent_plugins_list",
        aliases=(
            "native plugins list",
            "engel plugins list",
            "engel plugins",
            "list engel plugins",
            "show engel plugins",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_NATIVE_TOOLSETS_ROUTE_ID,
        label="Engel native toolsets (hermes-agent toolsets)",
        target_module="engel_engel_agent_runner",
        target_function="render_engel_agent_toolsets",
        aliases=(
            "engel toolsets",
            "engel toolsets list",
            "list engel toolsets",
            "show engel toolsets",
            "engel tools",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_NATIVE_DOCTOR_ROUTE_ID,
        label="Engel native doctor (hermes-agent doctor)",
        target_module="engel_engel_agent_runner",
        target_function="render_engel_agent_doctor",
        aliases=(
            "native doctor",
            "engel doctor",
            "engel ai doctor",
            "check engel",
            "engel health",
            "engel health check",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_NATIVE_TOP_STATUS_ROUTE_ID,
        label="Engel native top status (hermes-agent top)",
        target_module="engel_engel_agent_runner",
        target_function="render_engel_agent_top_status",
        aliases=(
            "engel top",
            "engel top status",
            "engel ai top",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_NATIVE_VERSION_ROUTE_ID,
        label="Engel native version (hermes-agent version)",
        target_module="engel_engel_agent_runner",
        target_function="render_engel_agent_version",
        aliases=(
            "native version",
            "engel version",
            "engel ai version",
            "what version is engel",
            "show engel version",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_NATIVE_INVOKE_ROUTE_ID,
        label="Engel native invoke (single-shot hermes-agent task)",
        target_module="engel_engel_agent_runner",
        target_function="render_engel_agent_invocation",
        aliases=(
            "engel invoke",
            "engel ai invoke",
            "engel run task",
            "engel do task",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_NATIVE_RUNTIME_ROUTE_ID,
        label="Engel native runtime (Phase D in-process import proof)",
        target_module="engel_engel_agent_runner",
        target_function="render_engel_native_runtime",
        aliases=(
            "engel native runtime",
            "engel in process",
            "engel in-process",
            "phase d status",
            "phase d proof",
            "is hermes in process",
            "is engel hermes in process",
            "engel runtime proof",
        ),
    ),
    # ── Wave 2 tools (2026-05-24) ───────────────────────────────────────────
    EngelAIUpdateRoute(
        route_id=ENGEL_NEW_TOOLS_LIST_ROUTE_ID,
        label="Engel Wave 2 new tools list",
        target_module="engel_new_tools_runner",
        target_function="render_new_tools_list",
        aliases=("new tools list", "wave 2 tools", "engel new tools", "show new tools", "list new modules"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_CLI_ANYTHING_STATUS_ROUTE_ID,
        label="CLI-Anything hub status",
        target_module="engel_new_tools_runner",
        target_function="render_cli_anything_status",
        aliases=("cli anything status", "cli hub status", "engel cli anything", "cli-anything status"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_CLI_ANYTHING_FEATURES_ROUTE_ID,
        label="CLI-Anything hub features",
        target_module="engel_new_tools_runner",
        target_function="render_cli_anything_features",
        aliases=("cli anything features", "what can cli anything do", "cli hub features"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_CLI_ANYTHING_DOCS_ROUTE_ID,
        label="CLI-Anything hub docs",
        target_module="engel_new_tools_runner",
        target_function="render_cli_anything_docs",
        aliases=("cli anything docs", "cli hub docs", "cli anything readme"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_GIT_NEXUS_STATUS_ROUTE_ID,
        label="GitNexus status",
        target_module="engel_new_tools_runner",
        target_function="render_git_nexus_status",
        aliases=("git nexus status", "engel git nexus", "gitnexus status"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_GIT_NEXUS_FEATURES_ROUTE_ID,
        label="GitNexus features",
        target_module="engel_new_tools_runner",
        target_function="render_git_nexus_features",
        aliases=("git nexus features", "what can git nexus do"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_GIT_NEXUS_DOCS_ROUTE_ID,
        label="GitNexus docs",
        target_module="engel_new_tools_runner",
        target_function="render_git_nexus_docs",
        aliases=("git nexus docs", "gitnexus readme"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_OCTOGENT_STATUS_ROUTE_ID,
        label="Octogent swarm status",
        target_module="engel_new_tools_runner",
        target_function="render_octogent_status",
        aliases=("octogent status", "engel octogent", "8 agent status", "swarm status"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_OCTOGENT_FEATURES_ROUTE_ID,
        label="Octogent swarm features",
        target_module="engel_new_tools_runner",
        target_function="render_octogent_features",
        aliases=("octogent features", "what can octogent do", "8 agent features"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_OCTOGENT_DOCS_ROUTE_ID,
        label="Octogent swarm docs",
        target_module="engel_new_tools_runner",
        target_function="render_octogent_docs",
        aliases=("octogent docs", "octogent readme"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_OPEN_AGENTS_STATUS_ROUTE_ID,
        label="Open Agents framework status",
        target_module="engel_new_tools_runner",
        target_function="render_open_agents_status",
        aliases=("open agents status", "engel open agents", "open-agents status"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_OPEN_AGENTS_FEATURES_ROUTE_ID,
        label="Open Agents features",
        target_module="engel_new_tools_runner",
        target_function="render_open_agents_features",
        aliases=("open agents features", "what can open agents do"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_OPEN_AGENTS_DOCS_ROUTE_ID,
        label="Open Agents docs",
        target_module="engel_new_tools_runner",
        target_function="render_open_agents_docs",
        aliases=("open agents docs", "open agents readme"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_AIRLLM_STATUS_ROUTE_ID,
        label="AirLLM local inference status",
        target_module="engel_new_tools_runner",
        target_function="render_airllm_status",
        aliases=("airllm status", "engel airllm", "air llm status", "local inference status"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_AIRLLM_FEATURES_ROUTE_ID,
        label="AirLLM features",
        target_module="engel_new_tools_runner",
        target_function="render_airllm_features",
        aliases=("airllm features", "what can airllm do", "air llm features"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_AIRLLM_DOCS_ROUTE_ID,
        label="AirLLM docs",
        target_module="engel_new_tools_runner",
        target_function="render_airllm_docs",
        aliases=("airllm docs", "airllm readme"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_JARVIS_STATUS_ROUTE_ID,
        label="Jarvis assistant status",
        target_module="engel_new_tools_runner",
        target_function="render_jarvis_status",
        aliases=("jarvis status", "engel jarvis", "openjarvis status"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_JARVIS_FEATURES_ROUTE_ID,
        label="Jarvis features",
        target_module="engel_new_tools_runner",
        target_function="render_jarvis_features",
        aliases=("jarvis features", "what can jarvis do"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_JARVIS_DOCS_ROUTE_ID,
        label="Jarvis docs",
        target_module="engel_new_tools_runner",
        target_function="render_jarvis_docs",
        aliases=("jarvis docs", "jarvis readme"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_CHAT_UI_STATUS_ROUTE_ID,
        label="Agent Chat UI status",
        target_module="engel_new_tools_runner",
        target_function="render_chat_ui_status",
        aliases=("chat ui status", "engel chat ui", "agent chat ui status"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_CHAT_UI_FEATURES_ROUTE_ID,
        label="Agent Chat UI features",
        target_module="engel_new_tools_runner",
        target_function="render_chat_ui_features",
        aliases=("chat ui features", "what can chat ui do"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_CHAT_UI_DOCS_ROUTE_ID,
        label="Agent Chat UI docs",
        target_module="engel_new_tools_runner",
        target_function="render_chat_ui_docs",
        aliases=("chat ui docs", "chat ui readme"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_AI_GALLERY_STATUS_ROUTE_ID,
        label="AI Dev Gallery status",
        target_module="engel_new_tools_runner",
        target_function="render_ai_gallery_status",
        aliases=("ai gallery status", "engel ai gallery", "ai dev gallery status"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_AI_GALLERY_FEATURES_ROUTE_ID,
        label="AI Dev Gallery features",
        target_module="engel_new_tools_runner",
        target_function="render_ai_gallery_features",
        aliases=("ai gallery features", "what can ai gallery do"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_AI_GALLERY_DOCS_ROUTE_ID,
        label="AI Dev Gallery docs",
        target_module="engel_new_tools_runner",
        target_function="render_ai_gallery_docs",
        aliases=("ai gallery docs", "ai gallery readme"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_CLUSTER_STATUS_ROUTE_ID,
        label="Cluster manager status",
        target_module="engel_new_tools_runner",
        target_function="render_cluster_status",
        aliases=("cluster status", "engel cluster", "cluster manager status"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_CLUSTER_FEATURES_ROUTE_ID,
        label="Cluster manager features",
        target_module="engel_new_tools_runner",
        target_function="render_cluster_features",
        aliases=("cluster features", "what can cluster do"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_CLUSTER_DOCS_ROUTE_ID,
        label="Cluster manager docs",
        target_module="engel_new_tools_runner",
        target_function="render_cluster_docs",
        aliases=("cluster docs", "cluster readme"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_KNOWLEDGE_GRAPH_V2_STATUS_ROUTE_ID,
        label="Knowledge Graph V2 graphify8 vendor status",
        target_module="engel_new_tools_runner",
        target_function="render_knowledge_graph_v2_status",
        aliases=("graphify 8 status", "kg vendor status", "graphify vendor"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_KNOWLEDGE_GRAPH_V2_FEATURES_ROUTE_ID,
        label="Knowledge Graph V2 features",
        target_module="engel_new_tools_runner",
        target_function="render_knowledge_graph_v2_features",
        aliases=("knowledge graph v2 features", "graphify 8 features"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_KNOWLEDGE_GRAPH_V2_DOCS_ROUTE_ID,
        label="Knowledge Graph V2 docs",
        target_module="engel_new_tools_runner",
        target_function="render_knowledge_graph_v2_docs",
        aliases=("knowledge graph v2 docs", "graphify 8 docs", "knowledge graph v2 readme"),
    ),
    # ── Wave 2 extended routes ───────────────────────────────────────────────
    EngelAIUpdateRoute(
        route_id=ENGEL_GIT_NEXUS_PLUGINS_ROUTE_ID,
        label="GitNexus plugin integrations",
        target_module="engel_new_tools_runner",
        target_function="render_git_nexus_plugins",
        aliases=("git nexus plugins", "gitnexus integrations", "git nexus claude plugin", "git nexus cursor plugin"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_GIT_NEXUS_INSTALL_ROUTE_ID,
        label="GitNexus install commands",
        target_module="engel_new_tools_runner",
        target_function="render_git_nexus_install",
        aliases=("git nexus install", "install gitnexus", "git nexus setup", "set up gitnexus"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_GIT_NEXUS_ANALYZE_ROUTE_ID,
        label="GitNexus git repo analysis",
        target_module="engel_new_tools_runner",
        target_function="render_git_nexus_analyze",
        aliases=("git nexus analyze", "gitnexus analyze repo", "analyze git with nexus", "git history analysis"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_CLI_ANYTHING_PLUGINS_ROUTE_ID,
        label="CLI-Anything plugin list",
        target_module="engel_new_tools_runner",
        target_function="render_cli_anything_plugins",
        aliases=("cli anything plugins", "list cli plugins", "cli hub plugins", "show cli tools"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_CLI_ANYTHING_SEARCH_ROUTE_ID,
        label="CLI-Anything plugin search",
        target_module="engel_new_tools_runner",
        target_function="render_cli_anything_search",
        aliases=("cli anything search", "search cli plugins", "find cli tool", "cli hub search"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_CLI_ANYTHING_INSTALL_ROUTE_ID,
        label="CLI-Anything install",
        target_module="engel_new_tools_runner",
        target_function="render_cli_anything_install",
        aliases=("cli anything install", "install cli anything", "install cli hub", "set up cli anything"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_OPEN_AGENTS_PACKAGES_ROUTE_ID,
        label="open-agents monorepo packages",
        target_module="engel_new_tools_runner",
        target_function="render_open_agents_packages",
        aliases=("open agents packages", "open agents monorepo", "list open agents packages", "open agents modules"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_OPEN_AGENTS_SKILLS_ROUTE_ID,
        label="open-agents skills inventory",
        target_module="engel_new_tools_runner",
        target_function="render_open_agents_skills",
        aliases=("open agents skills", "list open agents skills", "open agents skill lock", "open agent skills list"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_OPEN_AGENTS_INSTALL_ROUTE_ID,
        label="open-agents install commands",
        target_module="engel_new_tools_runner",
        target_function="render_open_agents_install",
        aliases=("open agents install", "install open agents", "set up open agents", "open agents setup"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_JARVIS_INSTALL_ROUTE_ID,
        label="Jarvis install commands",
        target_module="engel_new_tools_runner",
        target_function="render_jarvis_install",
        aliases=("jarvis install", "install jarvis", "set up jarvis", "openjarvis install"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_JARVIS_START_ROUTE_ID,
        label="Jarvis start command",
        target_module="engel_new_tools_runner",
        target_function="render_jarvis_start",
        aliases=("start jarvis", "launch jarvis", "jarvis start", "run openjarvis"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_JARVIS_SKILLS_ROUTE_ID,
        label="Jarvis skills list",
        target_module="engel_new_tools_runner",
        target_function="render_jarvis_skills",
        aliases=("jarvis skills", "list jarvis skills", "openjarvis skills", "what can jarvis do"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_CHAT_UI_INSTALL_ROUTE_ID,
        label="agent-chat-ui install commands",
        target_module="engel_new_tools_runner",
        target_function="render_chat_ui_install",
        aliases=("chat ui install", "install chat ui", "agent chat ui install", "set up chat ui"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_CHAT_UI_START_ROUTE_ID,
        label="agent-chat-ui start dev server",
        target_module="engel_new_tools_runner",
        target_function="render_chat_ui_start",
        aliases=("start chat ui", "launch chat ui", "chat ui dev server", "run chat ui", "chat ui start"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_CHAT_UI_CONFIG_ROUTE_ID,
        label="agent-chat-ui env config",
        target_module="engel_new_tools_runner",
        target_function="render_chat_ui_config",
        aliases=("chat ui config", "chat ui env", "configure chat ui", "chat ui environment"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_AI_GALLERY_DEMOS_ROUTE_ID,
        label="AI Dev Gallery demos list",
        target_module="engel_new_tools_runner",
        target_function="render_ai_gallery_demos",
        aliases=("ai gallery demos", "list ai demos", "ai dev gallery demos", "show gallery demos"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_AI_GALLERY_INSTALL_ROUTE_ID,
        label="AI Dev Gallery build instructions",
        target_module="engel_new_tools_runner",
        target_function="render_ai_gallery_install",
        aliases=("ai gallery install", "install ai gallery", "build ai gallery", "ai dev gallery build"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_AI_GALLERY_REQUIREMENTS_ROUTE_ID,
        label="AI Dev Gallery system requirements",
        target_module="engel_new_tools_runner",
        target_function="render_ai_gallery_requirements",
        aliases=("ai gallery requirements", "ai dev gallery requirements", "ai gallery system requirements", "what does ai gallery need"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_CLUSTER_NODES_ROUTE_ID,
        label="cluster node list",
        target_module="engel_new_tools_runner",
        target_function="render_cluster_nodes",
        aliases=("cluster nodes", "list cluster nodes", "cluster workers", "show cluster nodes"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_CLUSTER_INSTALL_ROUTE_ID,
        label="cluster install commands",
        target_module="engel_new_tools_runner",
        target_function="render_cluster_install",
        aliases=("cluster install", "install cluster", "set up cluster", "cluster setup"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_CLUSTER_EXAMPLES_ROUTE_ID,
        label="cluster examples list",
        target_module="engel_new_tools_runner",
        target_function="render_cluster_examples",
        aliases=("cluster examples", "list cluster examples", "show cluster examples", "cluster sample apps"),
    ),
    # ── Agent Meeting Room ───────────────────────────────────────────────────
    EngelAIUpdateRoute(
        route_id=ENGEL_MEETING_ROOM_STATUS_ROUTE_ID,
        label="Agent Meeting Room status",
        target_module="engel_agent_meetingroom",
        target_function="render_meeting_room_status",
        aliases=("meeting room status", "agent meeting room", "meeting room", "show meeting room", "meeting status"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_MEETING_ROOM_AGENDA_ROUTE_ID,
        label="Agent Meeting Room agenda",
        target_module="engel_agent_meetingroom",
        target_function="render_meeting_room_agenda",
        aliases=("meeting room agenda", "meeting agenda", "show meeting agenda", "meeting items", "agenda items"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_MEETING_ROOM_TRANSCRIPT_ROUTE_ID,
        label="Agent Meeting Room transcript",
        target_module="engel_agent_meetingroom",
        target_function="render_meeting_room_transcript",
        aliases=("meeting room transcript", "meeting transcript", "show meeting transcript", "meeting log", "agent discussion log"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_MEETING_ROOM_WHITEBOARD_ROUTE_ID,
        label="Agent Meeting Room whiteboard",
        target_module="engel_agent_meetingroom",
        target_function="render_meeting_room_whiteboard",
        aliases=("meeting room whiteboard", "agent whiteboard", "shared whiteboard", "meeting notes", "show whiteboard"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_MEETING_ROOM_AGENTS_ROUTE_ID,
        label="Agent Meeting Room — invited agents",
        target_module="engel_agent_meetingroom",
        target_function="render_meeting_room_agents",
        aliases=("meeting room agents", "meeting agents", "who is in the meeting", "invited agents", "meeting participants"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_MEETING_ROOM_OPEN_ROUTE_ID,
        label="Open agent meeting room",
        target_module="engel_agent_meetingroom",
        target_function="render_meeting_room_open",
        aliases=("open meeting room", "start meeting room", "start meeting", "open meeting", "begin meeting", "launch meeting room"),
        read_only=False,
        status_only=False,
        no_visible_ui_change=False,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_MEETING_ROOM_CLOSE_ROUTE_ID,
        label="Close agent meeting room",
        target_module="engel_agent_meetingroom",
        target_function="render_meeting_room_close",
        aliases=("close meeting room", "end meeting", "close meeting", "finish meeting", "shut down meeting room"),
        read_only=False,
        status_only=False,
        no_visible_ui_change=False,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_MEETING_ROOM_ADD_NOTE_ROUTE_ID,
        label="Add note to meeting room whiteboard",
        target_module="engel_agent_meetingroom",
        target_function="render_meeting_room_add_note",
        aliases=("meeting add note", "add meeting note", "whiteboard add", "add to whiteboard", "meeting room note"),
        read_only=False,
        status_only=False,
    ),
    # ── Wave 3 — gstack + LFM2 family ───────────────────────────────────────
    EngelAIUpdateRoute(
        route_id=ENGEL_WAVE3_LIST_ROUTE_ID,
        label="Wave 3 modules list",
        target_module="engel_wave3_runner",
        target_function="render_wave3_list",
        aliases=("wave 3 tools", "wave 3 list", "new wave 3 modules", "show wave 3"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_GSTACK_STATUS_ROUTE_ID,
        label="GStack agent framework status",
        target_module="engel_wave3_runner",
        target_function="render_gstack_status",
        aliases=("gstack status", "gstack agent status", "show gstack", "gstack framework status"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_GSTACK_FEATURES_ROUTE_ID,
        label="GStack features",
        target_module="engel_wave3_runner",
        target_function="render_gstack_features",
        aliases=("gstack features", "what can gstack do", "gstack capabilities"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_GSTACK_DOCS_ROUTE_ID,
        label="GStack docs",
        target_module="engel_wave3_runner",
        target_function="render_gstack_docs",
        aliases=("gstack docs", "gstack readme", "gstack documentation"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_GSTACK_INSTALL_ROUTE_ID,
        label="GStack install",
        target_module="engel_wave3_runner",
        target_function="render_gstack_install",
        aliases=("gstack install", "install gstack", "set up gstack", "gstack setup"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_GSTACK_SKILLS_ROUTE_ID,
        label="GStack skills list",
        target_module="engel_wave3_runner",
        target_function="render_gstack_skills",
        aliases=("gstack skills", "list gstack skills", "gstack skill list", "what skills does gstack have"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_LFM2_STATUS_ROUTE_ID,
        label="LFM2 SDK status",
        target_module="engel_wave3_runner",
        target_function="render_lfm2_status",
        aliases=("lfm2 status", "lfm2 sdk status", "liquid model status", "show lfm2"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_LFM2_FEATURES_ROUTE_ID,
        label="LFM2 features",
        target_module="engel_wave3_runner",
        target_function="render_lfm2_features",
        aliases=("lfm2 features", "what can lfm2 do", "lfm2 capabilities", "liquid model features"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_LFM2_DOCS_ROUTE_ID,
        label="LFM2 docs",
        target_module="engel_wave3_runner",
        target_function="render_lfm2_docs",
        aliases=("lfm2 docs", "lfm2 readme", "liquid model docs"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_LFM2_INSTALL_ROUTE_ID,
        label="LFM2 install",
        target_module="engel_wave3_runner",
        target_function="render_lfm2_install",
        aliases=("lfm2 install", "install lfm2", "set up lfm2", "lfm2 sdk install"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_LFM2_EXAMPLE_ROUTE_ID,
        label="LFM2 example script",
        target_module="engel_wave3_runner",
        target_function="render_lfm2_example",
        aliases=("lfm2 example", "lfm2 example script", "show lfm2 example", "run lfm2 example"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_LFM2_CODE_REVIEW_STATUS_ROUTE_ID,
        label="LFM2 Code Review Agent status",
        target_module="engel_wave3_runner",
        target_function="render_lfm2_code_review_status",
        aliases=("lfm2 code review status", "code review agent status", "lfm2 review status"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_LFM2_CODE_REVIEW_FEATURES_ROUTE_ID,
        label="LFM2 Code Review features",
        target_module="engel_wave3_runner",
        target_function="render_lfm2_code_review_features",
        aliases=("lfm2 code review features", "code review agent features", "lfm2 review capabilities"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_LFM2_CODE_REVIEW_DOCS_ROUTE_ID,
        label="LFM2 Code Review docs",
        target_module="engel_wave3_runner",
        target_function="render_lfm2_code_review_docs",
        aliases=("lfm2 code review docs", "code review agent docs", "lfm2 review readme"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_LFM2_CODE_REVIEW_INSTALL_ROUTE_ID,
        label="LFM2 Code Review install",
        target_module="engel_wave3_runner",
        target_function="render_lfm2_code_review_install",
        aliases=("lfm2 code review install", "install lfm2 code review", "set up lfm2 review"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_LFM2_CODE_REVIEW_APPS_ROUTE_ID,
        label="LFM2 Code Review apps",
        target_module="engel_wave3_runner",
        target_function="render_lfm2_code_review_apps",
        aliases=("lfm2 code review apps", "code review apps", "lfm2 review app list"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_LFM2_MOBILE_STATUS_ROUTE_ID,
        label="LFM2.5 Mobile status",
        target_module="engel_wave3_runner",
        target_function="render_lfm2_mobile_status",
        aliases=("lfm2 mobile status", "lfm2.5 mobile status", "mobile model status", "lfm2 mobile"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_LFM2_MOBILE_FEATURES_ROUTE_ID,
        label="LFM2.5 Mobile features",
        target_module="engel_wave3_runner",
        target_function="render_lfm2_mobile_features",
        aliases=("lfm2 mobile features", "lfm2.5 features", "mobile model features"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_LFM2_MOBILE_DOCS_ROUTE_ID,
        label="LFM2.5 Mobile docs",
        target_module="engel_wave3_runner",
        target_function="render_lfm2_mobile_docs",
        aliases=("lfm2 mobile docs", "lfm2.5 docs", "mobile model readme"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_LFM2_MOBILE_INSTALL_ROUTE_ID,
        label="LFM2.5 Mobile install",
        target_module="engel_wave3_runner",
        target_function="render_lfm2_mobile_install",
        aliases=("lfm2 mobile install", "install lfm2 mobile", "lfm2.5 install"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_LFM2_MOBILE_INFERENCE_ROUTE_ID,
        label="LFM2.5 Mobile inference script",
        target_module="engel_wave3_runner",
        target_function="render_lfm2_mobile_inference",
        aliases=("lfm2 mobile inference", "lfm2.5 inference", "run lfm2 mobile", "mobile model inference"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_LFM2_VISION_STATUS_ROUTE_ID,
        label="LFM2 Vision server status",
        target_module="engel_wave3_runner",
        target_function="render_lfm2_vision_status",
        aliases=("lfm2 vision status", "vision model status", "lfm2 vision server", "show lfm2 vision"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_LFM2_VISION_FEATURES_ROUTE_ID,
        label="LFM2 Vision features",
        target_module="engel_wave3_runner",
        target_function="render_lfm2_vision_features",
        aliases=("lfm2 vision features", "vision model features", "lfm2 vision capabilities"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_LFM2_VISION_DOCS_ROUTE_ID,
        label="LFM2 Vision docs",
        target_module="engel_wave3_runner",
        target_function="render_lfm2_vision_docs",
        aliases=("lfm2 vision docs", "vision model docs", "lfm2 vision readme"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_LFM2_VISION_INSTALL_ROUTE_ID,
        label="LFM2 Vision install",
        target_module="engel_wave3_runner",
        target_function="render_lfm2_vision_install",
        aliases=("lfm2 vision install", "install lfm2 vision", "set up lfm2 vision"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_LFM2_VISION_START_ROUTE_ID,
        label="LFM2 Vision start server",
        target_module="engel_wave3_runner",
        target_function="render_lfm2_vision_start",
        aliases=("lfm2 vision start", "start lfm2 vision", "run lfm2 vision server", "launch vision server"),
    ),
    # ── Wave 4 — Claw3D, CubeSandbox, DarwinEvolver, HermesAgent, LocalSend ──
    EngelAIUpdateRoute(
        route_id=ENGEL_WAVE4_LIST_ROUTE_ID,
        label="Wave 4 modules list",
        target_module="engel_wave4_runner",
        target_function="render_wave4_list",
        aliases=("wave 4 tools", "wave 4 list", "new wave 4 modules", "show wave 4"),
    ),
    # Claw3D
    EngelAIUpdateRoute(
        route_id=ENGEL_CLAW3D_STATUS_ROUTE_ID,
        label="Claw3D 3D agent office status",
        target_module="engel_wave4_runner",
        target_function="render_claw3d_status",
        aliases=("claw3d status", "3d agent office status", "show claw3d", "claw 3d status"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_CLAW3D_FEATURES_ROUTE_ID,
        label="Claw3D features",
        target_module="engel_wave4_runner",
        target_function="render_claw3d_features",
        aliases=("claw3d features", "3d office features", "what can claw3d do", "claw3d capabilities"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_CLAW3D_DOCS_ROUTE_ID,
        label="Claw3D docs",
        target_module="engel_wave4_runner",
        target_function="render_claw3d_docs",
        aliases=("claw3d docs", "claw3d readme", "3d office docs"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_CLAW3D_INSTALL_ROUTE_ID,
        label="Claw3D install",
        target_module="engel_wave4_runner",
        target_function="render_claw3d_install",
        aliases=("claw3d install", "install claw3d", "set up claw3d", "claw3d setup"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_CLAW3D_START_ROUTE_ID,
        label="Claw3D start",
        target_module="engel_wave4_runner",
        target_function="render_claw3d_start",
        aliases=("claw3d start", "start claw3d", "launch claw3d", "run claw3d"),
        read_only=False,
        status_only=False,
    ),
    # CubeSandbox
    EngelAIUpdateRoute(
        route_id=ENGEL_CUBESANDBOX_STATUS_ROUTE_ID,
        label="CubeSandbox agent sandbox status",
        target_module="engel_wave4_runner",
        target_function="render_cubesandbox_status",
        aliases=("cubesandbox status", "cube sandbox status", "ai sandbox status", "show cubesandbox"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_CUBESANDBOX_FEATURES_ROUTE_ID,
        label="CubeSandbox features",
        target_module="engel_wave4_runner",
        target_function="render_cubesandbox_features",
        aliases=("cubesandbox features", "cube sandbox features", "ai sandbox features", "what can cubesandbox do"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_CUBESANDBOX_DOCS_ROUTE_ID,
        label="CubeSandbox docs",
        target_module="engel_wave4_runner",
        target_function="render_cubesandbox_docs",
        aliases=("cubesandbox docs", "cube sandbox readme", "ai sandbox docs"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_CUBESANDBOX_INSTALL_ROUTE_ID,
        label="CubeSandbox install",
        target_module="engel_wave4_runner",
        target_function="render_cubesandbox_install",
        aliases=("cubesandbox install", "install cubesandbox", "set up cube sandbox", "ai sandbox install"),
    ),
    # Darwinian Evolver
    EngelAIUpdateRoute(
        route_id=ENGEL_DARWINIAN_EVOLVER_STATUS_ROUTE_ID,
        label="Darwinian Evolver status",
        target_module="engel_wave4_runner",
        target_function="render_darwinian_evolver_status",
        aliases=("darwinian evolver status", "darwin evolver status", "evolution optimizer status", "show darwinian evolver"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_DARWINIAN_EVOLVER_FEATURES_ROUTE_ID,
        label="Darwinian Evolver features",
        target_module="engel_wave4_runner",
        target_function="render_darwinian_evolver_features",
        aliases=("darwinian evolver features", "darwin evolver features", "evolution optimizer features", "what can darwinian evolver do"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_DARWINIAN_EVOLVER_DOCS_ROUTE_ID,
        label="Darwinian Evolver docs",
        target_module="engel_wave4_runner",
        target_function="render_darwinian_evolver_docs",
        aliases=("darwinian evolver docs", "darwin evolver readme", "evolutionary optimizer docs"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_DARWINIAN_EVOLVER_INSTALL_ROUTE_ID,
        label="Darwinian Evolver install",
        target_module="engel_wave4_runner",
        target_function="render_darwinian_evolver_install",
        aliases=("darwinian evolver install", "install darwin evolver", "set up evolutionary optimizer"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_DARWINIAN_EVOLVER_RUN_ROUTE_ID,
        label="Darwinian Evolver run command",
        target_module="engel_wave4_runner",
        target_function="render_darwinian_evolver_run",
        aliases=("darwinian evolver run", "run darwin evolver", "evolutionary optimizer run", "how to run darwinian evolver"),
    ),
    # Hermes Agent
    EngelAIUpdateRoute(
        route_id=ENGEL_HERMES_AGENT_STATUS_ROUTE_ID,
        label="Hermes Agent (Nous Research) status",
        target_module="engel_wave4_runner",
        target_function="render_hermes_agent_status",
        aliases=("hermes agent status", "nous hermes status", "hermes nous status", "show hermes agent"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_HERMES_AGENT_FEATURES_ROUTE_ID,
        label="Hermes Agent features",
        target_module="engel_wave4_runner",
        target_function="render_hermes_agent_features",
        aliases=("hermes agent features", "nous hermes features", "hermes agent capabilities", "what can hermes agent do"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_HERMES_AGENT_DOCS_ROUTE_ID,
        label="Hermes Agent docs",
        target_module="engel_wave4_runner",
        target_function="render_hermes_agent_docs",
        aliases=("hermes agent docs", "nous hermes readme", "hermes agent documentation"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_HERMES_AGENT_INSTALL_ROUTE_ID,
        label="Hermes Agent install",
        target_module="engel_wave4_runner",
        target_function="render_hermes_agent_install",
        aliases=("hermes agent install", "install hermes agent", "set up hermes", "hermes nous install"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_HERMES_AGENT_START_ROUTE_ID,
        label="Hermes Agent start",
        target_module="engel_wave4_runner",
        target_function="render_hermes_agent_start",
        aliases=("hermes agent start", "start hermes", "launch hermes agent", "run hermes"),
        read_only=False,
        status_only=False,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_HERMES_AGENT_SKILLS_ROUTE_ID,
        label="Hermes Agent skills",
        target_module="engel_wave4_runner",
        target_function="render_hermes_agent_skills",
        aliases=("hermes agent skills", "hermes skills", "hermes skill list", "nous hermes skills"),
    ),
    # LocalSend
    EngelAIUpdateRoute(
        route_id=ENGEL_LOCALSEND_STATUS_ROUTE_ID,
        label="LocalSend LAN file sharing status",
        target_module="engel_wave4_runner",
        target_function="render_localsend_status",
        aliases=("localsend status", "local send status", "lan share status", "show localsend"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_LOCALSEND_FEATURES_ROUTE_ID,
        label="LocalSend features",
        target_module="engel_wave4_runner",
        target_function="render_localsend_features",
        aliases=("localsend features", "local send features", "lan share features", "what can localsend do"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_LOCALSEND_DOCS_ROUTE_ID,
        label="LocalSend docs",
        target_module="engel_wave4_runner",
        target_function="render_localsend_docs",
        aliases=("localsend docs", "local send readme", "lan share docs"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_LOCALSEND_INSTALL_ROUTE_ID,
        label="LocalSend install",
        target_module="engel_wave4_runner",
        target_function="render_localsend_install",
        aliases=("localsend install", "install localsend", "set up local send", "lan share install"),
    ),
    # ── Architect Agent (Zones 1-5) ──────────────────────────────────────────
    EngelAIUpdateRoute(
        route_id=ENGEL_ARCHITECT_OVERVIEW_ROUTE_ID,
        label="Architect Agent overview",
        target_module="engel_architect_agent",
        target_function="render_architect_overview",
        aliases=("architect", "architect agent", "architect overview", "what is the architect agent", "show architect"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_ARCHITECT_STATUS_ROUTE_ID,
        label="Architect Agent status",
        target_module="engel_architect_agent",
        target_function="render_architect_status",
        aliases=("architect status", "architect run status", "architect state", "engel architect status"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_ARCHITECT_SECTIONS_ROUTE_ID,
        label="Architect 13 sections pipeline",
        target_module="engel_architect_agent",
        target_function="render_architect_sections",
        aliases=("architect sections", "architect 13 sections", "show architect sections", "architect pipeline"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_ARCHITECT_SECTION_DETAIL_ROUTE_ID,
        label="Architect current section detail",
        target_module="engel_architect_agent",
        target_function="render_architect_section_detail",
        aliases=("architect section detail", "architect current section", "architect section", "show current architect section"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_ARCHITECT_MODES_ROUTE_ID,
        label="Architect entry & execution modes",
        target_module="engel_architect_agent",
        target_function="render_architect_modes",
        aliases=("architect modes", "architect entry modes", "architect mode list", "show architect modes"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_ARCHITECT_PRINCIPLES_ROUTE_ID,
        label="Architect principles",
        target_module="engel_architect_agent",
        target_function="render_architect_principles",
        aliases=("architect principles", "architect ask vs derive", "architect output standard", "show architect principles"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_ARCHITECT_FOUNDER_VOICE_ROUTE_ID,
        label="Architect founder voice thread",
        target_module="engel_architect_agent",
        target_function="render_architect_founder_voice",
        aliases=("architect founder voice", "founder voice thread", "architect voice", "show founder voice"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_ARCHITECT_TRACKER_ROUTE_ID,
        label="Architect tracker log",
        target_module="engel_architect_agent",
        target_function="render_architect_tracker_log",
        aliases=("architect tracker", "architect tracker log", "architect activity log", "show architect tracker"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_ARCHITECT_BRIEFS_ROUTE_ID,
        label="Architect brief writer outputs",
        target_module="engel_architect_agent",
        target_function="render_architect_briefs",
        aliases=("architect briefs", "architect brief writer", "architect brief list", "show architect briefs"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_ARCHITECT_ISSUE_LOG_ROUTE_ID,
        label="Architect issue log",
        target_module="engel_architect_agent",
        target_function="render_architect_issue_log",
        aliases=("architect issue log", "architect issues", "architect open issues log", "show architect issues"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_ARCHITECT_CHANGE_MGMT_ROUTE_ID,
        label="Architect change management",
        target_module="engel_architect_agent",
        target_function="render_architect_change_management",
        aliases=("architect change management", "architect pivot flow", "architect change mgmt", "show architect change management"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_ARCHITECT_FAILURE_RECOVERY_ROUTE_ID,
        label="Architect failure recovery protocol",
        target_module="engel_architect_agent",
        target_function="render_architect_failure_recovery",
        aliases=("architect failure recovery", "architect recovery", "architect retry skip manual", "show architect recovery"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_ARCHITECT_PLANNER_LIST_ROUTE_ID,
        label="Architect planner stages list",
        target_module="engel_architect_agent",
        target_function="render_architect_planner_list",
        aliases=("architect planner", "architect planner stages", "architect planner list", "show architect planner"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_ARCHITECT_PLANNER_STATUS_ROUTE_ID,
        label="Architect planner status",
        target_module="engel_architect_agent",
        target_function="render_architect_planner_status",
        aliases=("architect planner status", "architect plan phase status", "architect planner state"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_ARCHITECT_APPROVAL_GATE_ROUTE_ID,
        label="Architect founder approval gate",
        target_module="engel_architect_agent",
        target_function="render_architect_approval_gate",
        aliases=("architect approval gate", "architect founder approval", "architect gate h", "show approval gate"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_ARCHITECT_LEGAL_SCAN_ROUTE_ID,
        label="Architect 6-category legal scan",
        target_module="engel_architect_agent",
        target_function="render_architect_legal_scan",
        aliases=("architect legal scan", "architect b legal", "architect 6 category legal", "show architect legal scan"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_ARCHITECT_PLAN_ROUTE_ID,
        label="Architect plan.md",
        target_module="engel_architect_agent",
        target_function="render_architect_plan",
        aliases=("architect plan", "architect plan.md", "show architect plan"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_ARCHITECT_SPEC_ROUTE_ID,
        label="Architect spec.md",
        target_module="engel_architect_agent",
        target_function="render_architect_spec",
        aliases=("architect spec", "architect spec.md", "show architect spec"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_ARCHITECT_PROMPT_ROUTE_ID,
        label="Architect prompt.md",
        target_module="engel_architect_agent",
        target_function="render_architect_prompt",
        aliases=("architect prompt", "architect prompt.md", "architect executor prompt", "show architect prompt"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_ARCHITECT_EXECUTOR_HANDOFF_ROUTE_ID,
        label="Architect executor handoff",
        target_module="engel_architect_agent",
        target_function="render_architect_executor_handoff",
        aliases=("architect executor handoff", "architect handoff", "architect ready for executor", "show executor handoff"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_ARCHITECT_OPEN_ISSUES_ROUTE_ID,
        label="Architect open issues check",
        target_module="engel_architect_agent",
        target_function="render_architect_open_issues",
        aliases=("architect open issues", "architect issues check", "architect critical issues", "show architect open issues"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_ARCHITECT_INTEGRATION_CHECK_ROUTE_ID,
        label="Architect gsd-integration-checker",
        target_module="engel_architect_agent",
        target_function="render_architect_integration_check",
        aliases=("architect integration check", "architect gsd integration", "architect cross section check", "gsd integration checker"),
    ),
    # ── Architect action routes (state mutations) ────────────────────────────
    EngelAIUpdateRoute(
        route_id=ENGEL_ARCHITECT_START_NEW_ROUTE_ID,
        label="Architect — start NEW run",
        target_module="engel_architect_agent",
        target_function="render_architect_start_new",
        aliases=("architect start new", "start architect new project", "architect new project", "architect begin new"),
        read_only=False,
        status_only=False,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_ARCHITECT_CONTINUE_ROUTE_ID,
        label="Architect — continue existing run",
        target_module="engel_architect_agent",
        target_function="render_architect_continue",
        aliases=("architect continue", "architect resume", "continue architect run", "resume architect"),
        read_only=False,
        status_only=False,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_ARCHITECT_CLOSE_ROUTE_ID,
        label="Architect — close current run",
        target_module="engel_architect_agent",
        target_function="render_architect_close",
        aliases=("architect close", "close architect run", "architect end run", "architect shut down"),
        read_only=False,
        status_only=False,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_ARCHITECT_RUN_SECTION_ROUTE_ID,
        label="Architect — run current section",
        target_module="engel_architect_agent",
        target_function="render_architect_run_section",
        aliases=("architect run section", "run architect section", "architect run current section", "architect start section"),
        read_only=False,
        status_only=False,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_ARCHITECT_COMPLETE_SECTION_ROUTE_ID,
        label="Architect — complete current section",
        target_module="engel_architect_agent",
        target_function="render_architect_complete_section",
        aliases=("architect complete section", "complete architect section", "architect finish section", "architect next section"),
        read_only=False,
        status_only=False,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_ARCHITECT_SKIP_SECTION_ROUTE_ID,
        label="Architect — skip current section (stub + issue)",
        target_module="engel_architect_agent",
        target_function="render_architect_skip_section",
        aliases=("architect skip section", "skip architect section", "architect skip current section", "stub architect section"),
        read_only=False,
        status_only=False,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_ARCHITECT_RETRY_SECTION_ROUTE_ID,
        label="Architect — retry current section",
        target_module="engel_architect_agent",
        target_function="render_architect_retry_section",
        aliases=("architect retry section", "retry architect section", "architect retry current section", "architect try again"),
        read_only=False,
        status_only=False,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_ARCHITECT_APPROVE_GATE_ROUTE_ID,
        label="Architect — APPROVE founder gate (H)",
        target_module="engel_architect_agent",
        target_function="render_architect_approve_gate",
        aliases=("architect approve gate", "approve architect gate", "architect founder approve", "architect approve h"),
        read_only=False,
        status_only=False,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_ARCHITECT_REDIRECT_GATE_ROUTE_ID,
        label="Architect — REDIRECT founder gate (H) to change mgmt",
        target_module="engel_architect_agent",
        target_function="render_architect_redirect_gate",
        aliases=("architect redirect gate", "redirect architect gate", "architect founder redirect", "architect change at gate"),
        read_only=False,
        status_only=False,
    ),
    # ── AirLLM local inference ───────────────────────────────────────────────
    EngelAIUpdateRoute(
        route_id=ENGEL_AIRLLM_BRIDGE_STATUS_ROUTE_ID,
        label="AirLLM bridge status",
        target_module="engel_airllm_bridge",
        target_function="render_airllm_bridge_status",
        aliases=("airllm bridge status", "airllm bridge", "local llm bridge status"),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_AIRLLM_LOAD_ROUTE_ID,
        label="AirLLM load model",
        target_module="engel_airllm_bridge",
        target_function="render_airllm_load",
        aliases=("airllm load", "load local model", "load llm", "airllm load model"),
        read_only=False,
        status_only=False,
        no_provider_model_network=False,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_AIRLLM_GENERATE_ROUTE_ID,
        label="AirLLM generate (local inference)",
        target_module="engel_airllm_bridge",
        target_function="render_airllm_generate",
        aliases=("airllm generate", "run local model", "local inference", "airllm run"),
        read_only=False,
        status_only=False,
        no_provider_model_network=False,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_AIRLLM_UNLOAD_ROUTE_ID,
        label="AirLLM unload model",
        target_module="engel_airllm_bridge",
        target_function="render_airllm_unload",
        aliases=("airllm unload", "unload model", "free model memory"),
        read_only=False,
        status_only=False,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_OVERNIGHT_STATUS_ROUTE_ID,
        label="Overnight research runner status (read-only view)",
        target_module="engel_overnight_status",
        target_function="render_overnight_status",
        aliases=(
            "overnight status",
            "overnight runner status",
            "show overnight runner",
            "research runner status",
            "overnight research status",
            "did overnight run",
            "overnight cycle status",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_TALK_TO_CODE_LIST_ROUTE_ID,
        label="Talk-to-Code: list talkable modules",
        target_module="engel_talk_to_code",
        target_function="list_talkable_modules",
        aliases=(
            "talk to code",
            "list talkable modules",
            "what modules can engel explain",
            "engel explain source",
            "talk to code list",
            "code modules",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_TALK_TO_CODE_EXPLAIN_ROUTE_ID,
        label="Talk-to-Code: explain a source module",
        target_module="engel_talk_to_code",
        target_function="explain_module",
        aliases=(
            "explain module",
            "explain engel code",
            "explain source",
            "describe module",
        ),
        status_only=False,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_MODELS_LIST_ROUTE_ID,
        label="Local Model Manager: list available GGUF models",
        target_module="engel_local_model_manager",
        target_function="render_models_list",
        aliases=(
            "models list",
            "list models",
            "show models",
            "available models",
            "local models",
            "what models are available",
            "list local models",
            "show local models",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_MODELS_STATUS_ROUTE_ID,
        label="Local Model Manager: active model status",
        target_module="engel_local_model_manager",
        target_function="render_models_status",
        aliases=(
            "models status",
            "active model",
            "which model is loaded",
            "model manager status",
            "current model",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_MODELS_LOAD_ROUTE_ID,
        label="Local Model Manager: load a GGUF model",
        target_module="engel_local_model_manager",
        target_function="render_models_load",
        aliases=(
            "models load",
            "load model",
            "switch model",
            "use model",
        ),
        read_only=False,
        status_only=False,
        no_provider_model_network=False,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_MODELS_UNLOAD_ROUTE_ID,
        label="Local Model Manager: unload active model",
        target_module="engel_local_model_manager",
        target_function="render_models_unload",
        aliases=(
            "models unload",
            "unload model",
            "free model",
            "release model",
        ),
        read_only=False,
        status_only=False,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_MODELS_INFO_ROUTE_ID,
        label="Local Model Manager: model info (quant, VRAM estimate)",
        target_module="engel_local_model_manager",
        target_function="render_models_info",
        aliases=(
            "model info",
            "models info",
            "show model info",
            "model vram",
            "model quantization",
        ),
        no_provider_model_network=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_OCTOGENT_SWARM_STATUS_ROUTE_ID,
        label="Octogent swarm UI status",
        target_module="engel_octogent_runner",
        target_function="render_octogent_status",
        aliases=(
            "octogent swarm status",
            "swarm status",
            "is octogent running",
            "octogent server status",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_OCTOGENT_INSTALL_ROUTE_ID,
        label="Octogent pnpm install",
        target_module="engel_octogent_runner",
        target_function="render_octogent_install",
        aliases=(
            "octogent install",
            "install octogent",
            "octogent pnpm install",
        ),
        read_only=False,
        status_only=False,
        no_background_worker=False,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_OCTOGENT_START_ROUTE_ID,
        label="Octogent start dev server (detached, port 8787)",
        target_module="engel_octogent_runner",
        target_function="render_octogent_start",
        aliases=(
            "octogent start",
            "start octogent",
            "launch octogent",
            "start swarm",
            "launch swarm",
            "octogent dev",
        ),
        read_only=False,
        status_only=False,
        no_background_worker=False,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_OCTOGENT_STOP_ROUTE_ID,
        label="Octogent stop dev server",
        target_module="engel_octogent_runner",
        target_function="render_octogent_stop",
        aliases=(
            "octogent stop",
            "stop octogent",
            "kill octogent",
            "stop swarm",
        ),
        read_only=False,
        status_only=False,
    ),
    # ── Research Brain ──────────────────────────────────────────────────────
    EngelAIUpdateRoute(
        route_id=ENGEL_RESEARCH_OVERVIEW_ROUTE_ID,
        label="Research overview — brain + queue + loop in one view",
        target_module="engel_research_status",
        target_function="render_research_overview",
        aliases=(
            "research overview",
            "research status",
            "show research",
            "what is engel researching",
            "research brain overview",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_RESEARCH_BRAIN_STATUS_ROUTE_ID,
        label="Research brain status",
        target_module="engel_research_status",
        target_function="render_research_brain_status",
        aliases=(
            "research brain status",
            "brain status",
            "research brain",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_RESEARCH_QUEUE_ROUTE_ID,
        label="Research queue status",
        target_module="engel_research_status",
        target_function="render_research_queue_status",
        aliases=(
            "research queue",
            "research queue status",
            "what is in the research queue",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_RESEARCH_NEXT_TOPIC_ROUTE_ID,
        label="Research next best topic",
        target_module="engel_research_status",
        target_function="render_research_next_best_topic",
        aliases=(
            "next research topic",
            "research next topic",
            "best topic to research",
            "what should engel research next",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_RESEARCH_DIGEST_ROUTE_ID,
        label="Latest research digest",
        target_module="engel_research_status",
        target_function="render_research_digest_latest",
        aliases=(
            "research digest",
            "latest research digest",
            "research summary",
            "what did engel research",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_RESEARCH_TOGGLE_ROUTE_ID,
        label="Research toggle status (on/off)",
        target_module="engel_research_status",
        target_function="render_research_toggle_status",
        aliases=(
            "research system toggle",
            "research toggle",
            "is research on",
            "research on or off",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_HIVE_MIND_STATUS_ROUTE_ID,
        label="Hive mind status",
        target_module="engel_research_status",
        target_function="render_hive_mind_status",
        aliases=(
            "hive mind status",
            "hive mind",
            "show hive mind",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_WORKER_ANTS_STATUS_ROUTE_ID,
        label="Worker ants status",
        target_module="engel_research_status",
        target_function="render_worker_ants_status",
        aliases=(
            "worker ants",
            "worker ants status",
            "show worker ants",
            "ants status",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_COLONY_STATUS_ROUTE_ID,
        label="Colony status",
        target_module="engel_research_status",
        target_function="render_colony_status",
        aliases=(
            "research colony overview",
            "colony status",
            "show colony",
            "engel colony",
            "colony overview",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_COLONY_SAFETY_ROUTE_ID,
        label="Colony safety gates status",
        target_module="engel_research_status",
        target_function="render_colony_safety_status",
        aliases=(
            "colony safety",
            "colony gates",
            "colony safety status",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_SWARM_TRAILS_ROUTE_ID,
        label="Swarm trails status",
        target_module="engel_research_status",
        target_function="render_swarm_trails_status",
        aliases=(
            "swarm trails",
            "swarm trails status",
            "show swarm trails",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_LEARNING_PROPOSALS_ROUTE_ID,
        label="Learning proposals review",
        target_module="engel_research_status",
        target_function="render_learning_proposals_status",
        aliases=(
            "learning proposals",
            "show learning proposals",
            "what are the learning proposals",
            "proposals review",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_LESSON_CANDIDATES_ROUTE_ID,
        label="Lesson candidates status",
        target_module="engel_research_status",
        target_function="render_lesson_candidates_status",
        aliases=(
            "lesson candidates",
            "show lesson candidates",
            "lesson candidates status",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_OVERNIGHT_LOOP_STATUS_ROUTE_ID,
        label="Overnight research loop status (is the loop running?)",
        target_module="engel_research_status",
        target_function="render_overnight_loop_status",
        aliases=(
            "overnight loop status",
            "is overnight loop running",
            "overnight loop",
            "loop status",
            "research loop status",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_GROWTH_DASHBOARD_ROUTE_ID,
        label="Engel AI growth dashboard",
        target_module="engel_ai_growth_dashboard",
        target_function="render_dashboard",
        aliases=(
            "growth dashboard",
            "engel growth dashboard",
            "ai growth",
            "show growth dashboard",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_OVERNIGHT_LOOP_CLEANUP_ROUTE_ID,
        label="Overnight loop stale-state cleanup",
        target_module="engel_research_status",
        target_function="render_overnight_loop_cleanup",
        aliases=(
            "overnight loop cleanup",
            "clean overnight loop",
            "remove overnight stale files",
            "clear loop lock file",
            "overnight cleanup",
        ),
        read_only=False,
        status_only=False,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_KG_V2_STATUS_ROUTE_ID,
        label="Knowledge Graph V2 status",
        target_module="engel_knowledge_graph_v2_status",
        target_function="render_kg_status",
        aliases=(
            "knowledge graph v2 status",
            "engel graphify status",
            "kg v2 status",
            "show knowledge graph status",
            "graphify status",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_KG_V2_GLOBAL_ROUTE_ID,
        label="Knowledge Graph V2 global graph",
        target_module="engel_knowledge_graph_v2_status",
        target_function="render_kg_global_graph",
        aliases=(
            "knowledge graph global",
            "engel graphify global graph",
            "kg global graph",
            "global code graph",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_KG_V2_SCAN_ROUTE_ID,
        label="Knowledge Graph V2 scan workspace",
        target_module="engel_knowledge_graph_v2_status",
        target_function="render_kg_scan_workspace",
        aliases=(
            "scan workspace for graphs",
            "find knowledge graphs",
            "kg scan workspace",
            "engel graphify scan",
            "list graph outputs",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_KG_V2_HELP_ROUTE_ID,
        label="Knowledge Graph V2 help",
        target_module="engel_knowledge_graph_v2_status",
        target_function="render_kg_help",
        aliases=(
            "knowledge graph help",
            "engel graphify help",
            "how to use knowledge graph",
            "kg v2 usage",
            "graphify commands",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_KG_V2_INSTALL_ROUTE_ID,
        label="Knowledge Graph V2 install",
        target_module="engel_knowledge_graph_v2_status",
        target_function="render_kg_install",
        aliases=(
            "install knowledge graph",
            "engel graphify install",
            "install graphify",
            "kg v2 install",
            "install engel graphify",
        ),
        read_only=False,
        status_only=False,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_KG_V2_BUILD_CORE_ROUTE_ID,
        label="Knowledge Graph V2 build Engel App core",
        target_module="engel_knowledge_graph_v2_status",
        target_function="render_kg_build_core",
        aliases=(
            "engel graphify build engel app core",
            "build knowledge graph",
            "build engel app graph",
            "kg build core",
            "graphify build engel",
        ),
        read_only=False,
        status_only=False,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_KG_V2_ANALYZE_CORE_ROUTE_ID,
        label="Knowledge Graph V2 analyze Engel App graph",
        target_module="engel_knowledge_graph_v2_status",
        target_function="render_kg_analyze_core",
        aliases=(
            "analyze knowledge graph",
            "engel graphify analyze",
            "kg analyze",
            "find god nodes",
            "engel graph analysis",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_KG_V2_SEARCH_ROUTE_ID,
        label="Knowledge Graph V2 search nodes by keyword",
        target_module="engel_knowledge_graph_v2_status",
        target_function="render_kg_search",
        aliases=(
            "kg search",
            "search graph",
            "find node",
            "graph search",
            "engel graphify search",
            "knowledge graph search",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_KG_V2_NEIGHBORS_ROUTE_ID,
        label="Knowledge Graph V2 show neighbors of a node",
        target_module="engel_knowledge_graph_v2_status",
        target_function="render_kg_neighbors",
        aliases=(
            "kg neighbors",
            "graph neighbors",
            "node neighbors",
            "engel graphify neighbors",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_KG_V2_COMMUNITIES_ROUTE_ID,
        label="Knowledge Graph V2 community clusters",
        target_module="engel_knowledge_graph_v2_status",
        target_function="render_kg_communities",
        aliases=(
            "kg communities",
            "graph communities",
            "cluster communities",
            "engel graphify communities",
            "knowledge graph clusters",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_VERIFY_LOCAL_LLM_GROWTH_ROUTE_ID,
        label="Verify customer-ready local LLM growth",
        target_module="engel_verify_status",
        target_function="render_verify_local_llm_growth",
        aliases=(
            "verify local llm growth",
            "check local llm growth",
            "customer ready local llm",
            "llm growth verifier",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_VERIFY_PROMOTION_ROUTE_ID,
        label="Verify customer-ready promotion",
        target_module="engel_verify_status",
        target_function="render_verify_promotion",
        aliases=(
            "verify promotion",
            "check promotion",
            "customer ready promotion",
            "promotion verifier",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_VERIFY_BRAIN_PROVIDER_ROUTE_ID,
        label="Verify brain provider trusted context",
        target_module="engel_verify_status",
        target_function="render_verify_brain_provider",
        aliases=(
            "verify brain provider",
            "check brain provider",
            "brain provider trusted context",
            "brain provider verifier",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_VERIFY_LLM_TEACHING_ROUTE_ID,
        label="Verify local LLM teaching session",
        target_module="engel_verify_status",
        target_function="render_verify_llm_teaching",
        aliases=(
            "verify llm teaching",
            "check teaching session",
            "llm one hour teaching",
            "teaching session verifier",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_VERIFY_STYLE_GUIDE_ROUTE_ID,
        label="Verify local LLM style guide proposal",
        target_module="engel_verify_status",
        target_function="render_verify_style_guide",
        aliases=(
            "verify style guide",
            "check style guide proposal",
            "style guide verifier",
            "llm style guide",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_VERIFY_ALL_ROUTE_ID,
        label="Run all workspace verifiers",
        target_module="engel_verify_status",
        target_function="render_verify_all",
        aliases=(
            "verify all",
            "run all verifiers",
            "check all workspace",
            "full verifier suite",
            "workspace health check",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_EXT_MEM_STATUS_ROUTE_ID,
        label="External memory drive status (E/F/G)",
        target_module="engel_external_memory_status",
        target_function="render_external_memory_status",
        aliases=(
            "external memory drive status",
            "external memory status",
            "check external drives",
            "engel memory drives",
            "e f g drive status",
            "external memory health",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_EXT_MEM_MODELS_ROUTE_ID,
        label="External memory GGUF models (E/F/G)",
        target_module="engel_external_memory_status",
        target_function="render_external_memory_models",
        aliases=(
            "external memory models",
            "gguf models on drives",
            "models on external drives",
            "list external gguf",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_EXT_MEM_RUNTIMES_ROUTE_ID,
        label="External memory runtime candidates (F: llama.cpp)",
        target_module="engel_external_memory_status",
        target_function="render_external_memory_runtimes",
        aliases=(
            "external memory runtimes",
            "llama cpp runtimes",
            "f drive runtimes",
            "llama cli candidates",
            "local inference runtimes",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_VAULT_MIGRATION_STATUS_ROUTE_ID,
        label="Storage migration status -- CT246 SSD plus Dell HDD policy",
        target_module="engel_vault_paths",
        target_function="render_vault_migration_status",
        aliases=(
            "vault migration status",
            "engel vault migration status",
            "move engel storage to ct246",
            "retired drive migration status",
            "disconnect external storage status",
            "engel storage transfer status",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_VAULT_MIGRATION_PLAN_ROUTE_ID,
        label="Storage migration plan -- CT246 SSD plus Dell HDD archive",
        target_module="engel_vault_paths",
        target_function="render_vault_migration_plan",
        aliases=(
            "vault migration plan",
            "engel vault migration plan",
            "dell hdd copy plan",
            "copy retired drives to server storage",
            "setup engel storage on proxmox",
            "disconnect external storage plan",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_MAIN_SERVER_MERGE_STATUS_ROUTE_ID,
        label="Engel Main server merge status -- Windows app to CT 246",
        target_module="engel_main_server_merge",
        target_function="render_server_merge_status",
        aliases=(
            "engel main server merge status",
            "server engel ai main merge status",
            "is engel main merged with server",
            "windows app server merge",
            "ct 246 merge status",
            "engel-ai-main server status",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_EXT_MEM_E_DRIVE_ROUTE_ID,
        label="E: drive archive shelf status",
        target_module="engel_external_memory_status",
        target_function="render_e_drive_status",
        aliases=(
            "e drive status",
            "e engel memory status",
            "check e drive",
            "e archive shelf",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_EXT_MEM_F_DRIVE_ROUTE_ID,
        label="F: drive fast shelf status",
        target_module="engel_external_memory_status",
        target_function="render_f_drive_status",
        aliases=(
            "f drive status",
            "f engel memory status",
            "check f drive",
            "fast memory shelf",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_EXT_MEM_G_DRIVE_ROUTE_ID,
        label="G: drive archive shelf status",
        target_module="engel_external_memory_status",
        target_function="render_g_drive_status",
        aliases=(
            "g drive status",
            "g engel memory status",
            "check g drive",
            "g archive shelf",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_LLAMA_CLI_STATUS_ROUTE_ID,
        label="llama-cli runtime status",
        target_module="engel_llama_cli_runner",
        target_function="render_llama_cli_status",
        aliases=(
            "llama cli status",
            "llama runtime status",
            "check llama cli",
            "f drive llama status",
            "llama cpp cli status",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_LLAMA_CLI_PREFLIGHT_ROUTE_ID,
        label="llama-cli preflight check",
        target_module="engel_llama_cli_runner",
        target_function="render_llama_cli_preflight",
        aliases=(
            "llama cli preflight",
            "preflight llama",
            "check llama binary",
            "llama cli ready check",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_LLAMA_CLI_RUN_ROUTE_ID,
        label="llama-cli run inference",
        target_module="engel_llama_cli_runner",
        target_function="render_llama_cli_run",
        aliases=(
            "llama cli run",
            "run llama cli",
            "llama inference",
            "run local inference cli",
            "llama cpp run",
        ),
        read_only=False,
        status_only=False,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_LLAMA_CLI_BENCHMARK_ROUTE_ID,
        label="llama-cli quick benchmark",
        target_module="engel_llama_cli_runner",
        target_function="render_llama_cli_benchmark",
        aliases=(
            "llama cli benchmark",
            "benchmark llama cli",
            "llama speed test",
            "llama cpp benchmark",
        ),
        read_only=False,
        status_only=False,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_LLAMA_CLI_RUN_SLUG_ROUTE_ID,
        label="llama-cli run by model slug",
        target_module="engel_llama_cli_runner",
        target_function="render_llama_cli_run_slug",
        aliases=(
            "llama cli run model",
            "llama run slug",
            "run model slug",
            "llama cli model run",
        ),
        read_only=False,
        status_only=False,
        no_provider_model_network=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_LLAMA_CLI_GPU_BENCHMARK_ROUTE_ID,
        label="llama-cli GPU benchmark (7B)",
        target_module="engel_llama_cli_runner",
        target_function="render_llama_cli_gpu_benchmark",
        aliases=(
            "llama gpu benchmark",
            "llama cuda benchmark",
            "gpu inference benchmark",
            "7b benchmark",
        ),
        read_only=False,
        status_only=False,
        no_provider_model_network=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_LLAMA_CLI_GPU_INFO_ROUTE_ID,
        label="GPU info (VRAM, temperature, utilization)",
        target_module="engel_llama_cli_runner",
        target_function="render_llama_cli_gpu_info",
        aliases=(
            "gpu info",
            "show gpu",
            "vram usage",
            "gpu memory",
            "nvidia smi",
        ),
        no_provider_model_network=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_LLAMA_CLI_COMPARE_ROUTE_ID,
        label="Compare models on same prompt",
        target_module="engel_llama_cli_runner",
        target_function="render_llama_cli_compare",
        aliases=(
            "compare models",
            "model comparison",
            "run all models",
            "compare llm",
            "benchmark comparison",
        ),
        no_provider_model_network=True,
        read_only=False,
        status_only=False,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_LLAMA_CLI_EXPLAIN_ROUTE_ID,
        label="Explain Python module with local LLM",
        target_module="engel_llama_cli_runner",
        target_function="render_llama_cli_explain",
        aliases=(
            "llm explain",
            "explain code",
            "local explain",
            "ai explain module",
        ),
        no_provider_model_network=True,
        read_only=False,
        status_only=False,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_LOCAL_LLM_DASHBOARD_ROUTE_ID,
        label="Local LLM dashboard — GPU, models, backend, VRAM fit",
        target_module="engel_local_llm_dashboard",
        target_function="render_local_llm_dashboard",
        aliases=(
            "local llm dashboard",
            "llm dashboard",
            "llm status dashboard",
            "gpu model dashboard",
            "local inference dashboard",
            "ai dashboard",
        ),
        no_provider_model_network=True,
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_LOCAL_LLM_DOCTOR_ROUTE_ID,
        label="Local LLM doctor — full-chain preflight healthcheck (read-only)",
        target_module="engel_local_llm_doctor",
        target_function="render_local_llm_doctor",
        aliases=(
            "local llm doctor",
            "llm doctor",
            "local llm healthcheck",
            "local llm health check",
            "local llm preflight",
            "diagnose local llm",
            "check local llm",
            "why is local llm broken",
            "local model doctor",
        ),
        no_provider_model_network=True,
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_DARWIN_STATUS_ROUTE_ID,
        label="Darwin evolution lab status",
        target_module="engel_darwin_status",
        target_function="render_darwin_status",
        aliases=(
            "darwin status",
            "evolution lab darwin status",
            "engel darwin status",
            "darwin framework status",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_DARWIN_PROBLEMS_ROUTE_ID,
        label="Darwin available problems",
        target_module="engel_darwin_status",
        target_function="render_darwin_problems",
        aliases=(
            "darwin problems",
            "evolution problems",
            "list darwin problems",
            "engel darwin problem list",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_DARWIN_FRAMEWORK_ROUTE_ID,
        label="Darwin framework architecture",
        target_module="engel_darwin_status",
        target_function="render_darwin_framework_info",
        aliases=(
            "darwin framework",
            "how does darwin work",
            "evolution lab architecture",
            "darwin organism mutator evaluator",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_DARWIN_LOG_ROUTE_ID,
        label="Darwin learning log",
        target_module="engel_darwin_status",
        target_function="render_darwin_learning_log",
        aliases=(
            "darwin learning log",
            "evolution lab log",
            "darwin run history",
            "darwin logs",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_DARWIN_LOCAL_STATUS_ROUTE_ID,
        label="Darwin local runner status",
        target_module="engel_darwin_local_runner",
        target_function="render_darwin_local_parrot_status",
        aliases=(
            "darwin local status",
            "darwin local runner",
            "local evolution status",
            "darwin llama status",
            "evolution lab local status",
        ),
        no_provider_model_network=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_DARWIN_LOCAL_PARROT_RUN_ROUTE_ID,
        label="Darwin local parrot run",
        target_module="engel_darwin_local_runner",
        target_function="render_darwin_local_parrot_run",
        aliases=(
            "darwin local parrot run",
            "run local evolution",
            "evolve parrot locally",
            "darwin local run",
            "local parrot evolution",
        ),
        no_provider_model_network=True,
    ),
    # Sub-Engel (additional computers) support for more AI usage
    EngelAIUpdateRoute(
        route_id=ENGEL_SUB_ENGEL_STATUS_ROUTE_ID,
        label="Sub-Engel (additional computers) status and registered workers",
        target_module="engel_remote_worker_job_assignment",
        target_function="render_sub_engel_status",
        aliases=(
            "sub engel status",
            "sub-engel status",
            "additional computers status",
            "sub engel workers",
            "linux sub engel status",
            "windows sub engel status",
        ),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_SUB_ENGEL_CREATE_JOB_ROUTE_ID,
        label="Create bounded job for Sub-Engel additional computer",
        target_module="engel_remote_worker_job_assignment",
        target_function="render_sub_engel_create_job",
        aliases=(
            "sub engel create job",
            "sub-engel job",
            "create sub engel job",
            "send to additional computer",
            "dispatch to sub engel",
        ),
        read_only=False,
        status_only=False,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_SUB_ENGEL_RESULTS_ROUTE_ID,
        label="Sub-Engel results from additional computers (more computer usage for AI)",
        target_module="engel_remote_worker_job_assignment",
        target_function="render_sub_engel_results",
        aliases=(
            "sub engel results",
            "sub-engel results",
            "additional computers results",
            "fleet results",
            "sub engel output",
        ),
        read_only=True,
        status_only=True,
    ),
    # Multi-model local code generation across all supported languages (local GGUF only, grounded in library)
    EngelAIUpdateRoute(
        route_id=ENGEL_CODE_LIST_LANGUAGES_ROUTE_ID,
        label="List all supported code languages from approved library",
        target_module="engel_local_multi_model_code",
        target_function="render_code_list_languages",
        aliases=(
            "code languages",
            "list code languages",
            "supported languages for code",
            "polyglot languages",
            "what languages can engel code in",
        ),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_CODE_LIST_LOCAL_MODELS_ROUTE_ID,
        label="List available local GGUF models for code generation",
        target_module="engel_local_multi_model_code",
        target_function="render_code_list_local_models",
        aliases=(
            "local code models",
            "gguf models for code",
            "list local models code",
            "available ai models for code",
        ),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_CODE_GENERATE_MULTI_MODEL_ROUTE_ID,
        label="Generate code using chosen local AI model in any supported language",
        target_module="engel_local_multi_model_code",
        target_function="render_code_generate",
        aliases=(
            "generate code",
            "code generate",
            "write code",
            "create code",
            "polyglot generate",
            "use model for code",
            "generate code with",
        ),
        read_only=False,
        status_only=False,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_CODE_REFINE_ROUTE_ID,
        label="Refine/iterate on code using local AI model and feedback",
        target_module="engel_local_multi_model_code",
        target_function="render_code_refine",
        aliases=(
            "refine code",
            "iterate code",
            "improve code",
            "fix code with model",
            "code refine",
        ),
        read_only=False,
        status_only=False,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_CODE_BATCH_GENERATE_ROUTE_ID,
        label="Batch generate code for multiple languages using local models (auto suggested per lang)",
        target_module="engel_local_multi_model_code",
        target_function="render_code_batch_generate",
        aliases=(
            "batch code generate",
            "multi language code",
            "generate in many languages",
            "batch polyglot code",
        ),
        read_only=False,
        status_only=False,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_CODE_WITH_COMPANION_ROUTE_ID,
        label="Generate code then hand off to Code Companion for further analysis/patching",
        target_module="engel_local_multi_model_code",
        target_function="render_code_with_companion",
        aliases=(
            "code to companion",
            "generate and companion",
            "code gen + companion",
        ),
        read_only=False,
        status_only=False,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_CODE_TRANSLATE_ROUTE_ID,
        label="Translate/port code between languages using local models (auto-suggest per target)",
        target_module="engel_local_multi_model_code",
        target_function="render_code_translate",
        aliases=(
            "translate code",
            "port code to",
            "convert code to",
            "code translate",
        ),
        read_only=False,
        status_only=False,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_CODE_BEST_AUTO_ROUTE_ID,
        label="Auto best model + generate code for a language (smart suggestion + execution)",
        target_module="engel_local_multi_model_code",
        target_function="render_code_best_for_language",
        aliases=(
            "best code",
            "auto code for language",
            "smart code gen",
            "best model for lang",
        ),
        read_only=False,
        status_only=False,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_CODE_LIST_MODELS_FOR_LANG_ROUTE_ID,
        label="List suggested/available models for a specific language",
        target_module="engel_local_multi_model_code",
        target_function="render_code_list_models_for_language",
        aliases=(
            "models for language",
            "best models for",
            "which model for python",
        ),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_CODE_MULTI_CANDIDATES_ROUTE_ID,
        label="Generate multiple code candidates using top models for a language",
        target_module="engel_local_multi_model_code",
        target_function="render_code_multi_model_candidates",
        aliases=(
            "multi model code",
            "candidates for",
            "try several models",
            "all models for lang",
        ),
        read_only=False,
        status_only=False,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_CODE_STAGE_SUB_ENGEL_ROUTE_ID,
        label="Stage code generation job for a Sub-Engel node (fleet dispatch for specific model)",
        target_module="engel_local_multi_model_code",
        target_function="stage_code_gen_for_sub_engel",
        aliases=(
            "stage code sub engel",
            "code gen to fleet",
            "dispatch code to sub",
        ),
        read_only=False,
        status_only=False,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_CAPABILITY_SEARCH_ROUTE_ID,
        label="Engel capability search — find the route that serves an intention",
        target_module="engel_capability_index",
        target_function="render_capability_search",
        aliases=(
            "what can you do about",
            "what can engel do about",
            "engel capabilities for",
            "capability search",
            "find engel route for",
            "which route",
        ),
    ),
    # ---- EngelScript: Engel's own plan language (docs/ENGEL_SCRIPT_LANGUAGE.md) ----
    EngelAIUpdateRoute(
        route_id=ENGEL_SCRIPT_DOCS_ROUTE_ID,
        label="EngelScript language reference (Engel's own plan language)",
        target_module="engel_script",
        target_function="render_engel_script_docs",
        aliases=(
            "engel script docs",
            "engel script help",
            "engel script language",
            "engelscript docs",
            "what is engelscript",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_SCRIPT_EXAMPLES_ROUTE_ID,
        label="EngelScript example plans and where receipts land",
        target_module="engel_script",
        target_function="render_engel_script_examples",
        aliases=(
            "engel script examples",
            "engel script plans",
            "list engel scripts",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_SCRIPT_VALIDATE_ROUTE_ID,
        label="Validate an EngelScript plan (parse + safety-resolve; runs nothing)",
        target_module="engel_script",
        target_function="render_engel_script_validate",
        aliases=(
            "validate engel script",
            "engel script validate",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_SCRIPT_RUN_ROUTE_ID,
        label="Run an EngelScript plan by name (read-only mode; action routes blocked; receipted)",
        target_module="engel_script",
        target_function="render_engel_script_run",
        aliases=(
            "run engel script",
            "engel script run",
        ),
        status_only=False,
    ),
    # ---- Engel Conductor: the goal loop (docs/ENGEL_CONDUCTOR_DESIGN.md) ----
    EngelAIUpdateRoute(
        route_id=ENGEL_CONDUCTOR_DOCS_ROUTE_ID,
        label="Engel Conductor reference (the goal loop that closes plan-run-observe-repair)",
        target_module="engel_conductor",
        target_function="render_conductor_docs",
        aliases=(
            "engel conductor docs",
            "engel conductor help",
            "what is the engel conductor",
            "engel conductor",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_CONDUCTOR_GOAL_ROUTE_ID,
        label="Conduct a goal (plan, validate, run, observe, repair; bounded and receipted)",
        target_module="engel_conductor",
        target_function="render_conduct",
        aliases=(
            "engel goal",
            "conduct engel goal",
            "continue engel goal",
        ),
        status_only=False,
    ),
    # ---- Engel Code Forge: proven code (docs/ENGEL_CODE_FORGE_DESIGN.md) ----
    EngelAIUpdateRoute(
        route_id=ENGEL_FORGE_DOCS_ROUTE_ID,
        label="Engel Code Forge reference (generate, gate, run, observe, repair)",
        target_module="engel_code_forge",
        target_function="render_forge_docs",
        aliases=(
            "engel forge docs",
            "engel forge help",
            "what is the engel forge",
            "engel code forge",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_FORGE_STATUS_ROUTE_ID,
        label="Engel forge ledger (recent forges: rounds, outcome, proven artifacts)",
        target_module="engel_code_forge",
        target_function="render_forge_status",
        aliases=(
            "engel forge status",
            "list forges",
            "forge status",
            "engel forges",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_FORGE_CODE_ROUTE_ID,
        label="Forge code for a task (sandboxed generate/run/repair loop; chat surface forges)",
        target_module="engel_code_forge",
        target_function="render_forge",
        aliases=(
            "forge code",
            "engel forge code",
            "engel forge",
        ),
        status_only=False,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_CONDUCTOR_STATUS_ROUTE_ID,
        label="Engel goal ledger (open, done, needs-attention goals with their receipts)",
        target_module="engel_conductor",
        target_function="render_goal_status",
        aliases=(
            "engel goal status",
            "engel goals status",
            "list engel goals",
            "engel goals",
            "engel goal ledger",
        ),
    ),
    # ---- Engel Orchestra: parallel lanes (docs/ENGEL_ORCHESTRA_DESIGN.md) ----
    EngelAIUpdateRoute(
        route_id=ENGEL_ORCHESTRA_DOCS_ROUTE_ID,
        label="Engel Orchestra reference (the Conductor's parallel section)",
        target_module="engel_orchestra",
        target_function="render_orchestra_docs",
        aliases=(
            "engel orchestra docs",
            "engel orchestra help",
            "what is the engel orchestra",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_ORCHESTRA_RUN_ROUTE_ID,
        label="Orchestrate a multi-part goal (bounded parallel read-only Conductor lanes)",
        target_module="engel_orchestra",
        target_function="render_orchestrate",
        aliases=(
            "engel orchestra",
            "engel orchestrate",
            "orchestrate engel goal",
        ),
        status_only=False,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_ORCHESTRA_STATUS_ROUTE_ID,
        label="Engel Orchestra ledger (recent orchestrations: lanes, outcomes, receipts)",
        target_module="engel_orchestra",
        target_function="render_orchestra_status",
        aliases=(
            "engel orchestra status",
            "engel orchestra runs",
            "list engel orchestra runs",
            "engel orchestra ledger",
        ),
    ),
    # ---- Engel Agent Kernel: one goal -> the smallest proven engine ----
    EngelAIUpdateRoute(
        route_id=ENGEL_AGENT_KERNEL_DOCS_ROUTE_ID,
        label="Engel Agent Kernel reference (automatic native dispatch spine)",
        target_module="engel_agent_kernel",
        target_function="render_agent_docs",
        aliases=(
            "engel agent kernel",
            "engel agent kernel docs",
            "engel work help",
            "what is the engel agent kernel",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_AGENT_KERNEL_RUN_ROUTE_ID,
        label="Run one goal through Engel's native Agent Kernel",
        target_module="engel_agent_kernel",
        target_function="render_agent_work",
        aliases=(
            "engel work",
            "engel solve",
            "engel agent work",
        ),
        read_only=False,
        status_only=False,
        safe_for_ai_route=False,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_AGENT_KERNEL_STATUS_ROUTE_ID,
        label="Engel Agent Kernel receipt ledger",
        target_module="engel_agent_kernel",
        target_function="render_agent_status",
        aliases=(
            "engel work status",
            "engel agent kernel status",
            "engel agent kernel runs",
        ),
    ),
    # ---- Engel Grok Bot: named teammates on the shared cluster computer ----
    EngelAIUpdateRoute(
        route_id=ENGEL_GROK_BOT_DOCS_ROUTE_ID,
        label="Engel Grok Bot reference (named cluster teammates, not a cloud VM)",
        target_module="engel_grok_bot",
        target_function="render_grok_bot_docs",
        aliases=(
            "what is grok bot",
            "grok bot docs",
            "grok bot help",
            "explain grok bot",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_GROK_BOT_STATUS_ROUTE_ID,
        label="Engel Grok Bot status (named bots plus shared-computer map)",
        target_module="engel_grok_bot",
        target_function="render_grok_bot_status",
        aliases=(
            "grok bot status",
            "grok bot",
            "show grok bot",
            "engel grok bot status",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_GROK_BOT_LIST_ROUTE_ID,
        label="List named Engel Grok Bots",
        target_module="engel_grok_bot",
        target_function="render_grok_bot_list",
        aliases=(
            "list grok bots",
            "grok bots",
            "show grok bots",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_GROK_BOT_COMPUTER_ROUTE_ID,
        label="Shared Engel computer used by every Grok Bot",
        target_module="engel_grok_bot",
        target_function="render_grok_bot_computer",
        aliases=(
            "grok bot computer",
            "shared grok bot computer",
            "where does grok bot run",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_GROK_BOT_APPROVALS_ROUTE_ID,
        label="Grok Bot approval buckets (Josh / Guardian / runtime)",
        target_module="engel_grok_bot",
        target_function="render_grok_bot_approvals",
        aliases=(
            "grok bot approvals",
            "grok bot approval",
            "grok bot gates",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_GROK_BOT_CREATE_ROUTE_ID,
        label="Create a named Engel Grok Bot teammate",
        target_module="engel_grok_bot",
        target_function="render_grok_bot_create",
        aliases=(
            "create grok bot",
            "new grok bot",
            "add grok bot",
        ),
        read_only=False,
        status_only=False,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_GROK_BOT_MESSAGE_ROUTE_ID,
        label="Message a named Engel Grok Bot like a teammate",
        target_module="engel_grok_bot",
        target_function="render_grok_bot_message",
        aliases=(
            "message grok bot",
            "ask grok bot",
            "tell grok bot",
        ),
        read_only=False,
        status_only=False,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_GROK_BOT_HANDOFF_ROUTE_ID,
        label="Stage a Grok Bot task into the Agent Meeting Room",
        target_module="engel_grok_bot",
        target_function="render_grok_bot_handoff",
        aliases=(
            "handoff grok bot",
            "grok bot handoff",
            "send grok bot",
        ),
        read_only=False,
        status_only=False,
    ),

    EngelAIUpdateRoute(
        route_id=ENGEL_GROK_BOT_PRESENCE_ROUTE_ID,
        label="Engel Grok Bot presence lifecycle (file-only)",
        target_module="engel_grok_bot",
        target_function="render_grok_bot_presence",
        aliases=(
            "grok bot presence",
            "engel grok bot presence",
            "show grok bot presence",
        ),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_ROUTINES_DOCS_ROUTE_ID,
        label="Engel Routines V1 docs (stage-only standing work)",
        target_module="engel_routines",
        target_function="render_routines_docs",
        aliases=(
            "what is engel routine",
            "engel routines docs",
            "engel routine help",
        ),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_ROUTINES_STATUS_ROUTE_ID,
        label="Engel Routines status",
        target_module="engel_routines",
        target_function="render_routines_status",
        aliases=(
            "engel routines status",
            "engel routine status",
            "routines status",
        ),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_ROUTINES_LIST_ROUTE_ID,
        label="List Engel Routines",
        target_module="engel_routines",
        target_function="render_routines_list",
        aliases=(
            "list engel routines",
            "engel routines",
            "show engel routines",
        ),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_ROUTINES_CREATE_ROUTE_ID,
        label="Create an Engel Routine (no auto-execute)",
        target_module="engel_routines",
        target_function="render_routines_create",
        aliases=(
            "create engel routine",
            "new engel routine",
            "add engel routine",
        ),
        read_only=False,
        status_only=False,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_ROUTINES_DUE_ROUTE_ID,
        label="Poll which Engel Routines are due (no background timer)",
        target_module="engel_routines",
        target_function="render_routines_due",
        aliases=(
            "engel routines due",
            "due engel routines",
            "which routines are due",
        ),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_ROUTINES_STAGE_ROUTE_ID,
        label="Stage a due Engel Routine as Meeting Room draft only",
        target_module="engel_routines",
        target_function="render_routines_stage",
        aliases=(
            "stage engel routine",
            "stage due routine",
            "stage routine",
        ),
        read_only=False,
        status_only=False,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_ROUTINES_PAUSE_ROUTE_ID,
        label="Pause an Engel Routine",
        target_module="engel_routines",
        target_function="render_routines_pause",
        aliases=(
            "pause engel routine",
            "pause routine",
        ),
        read_only=False,
        status_only=False,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_COMPACTION_DOCS_ROUTE_ID,
        label="Engel local context compaction docs",
        target_module="engel_context_compaction",
        target_function="render_compaction_docs",
        aliases=(
            "engel compaction docs",
            "what is engel compaction",
            "context compaction docs",
        ),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_COMPACTION_STATUS_ROUTE_ID,
        label="Engel local context compaction status",
        target_module="engel_context_compaction",
        target_function="render_compaction_status",
        aliases=(
            "engel compaction status",
            "compaction status",
            "context compaction status",
        ),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_COMPACTION_COMPACT_ROUTE_ID,
        label="Compact a local thread into a receipt",
        target_module="engel_context_compaction",
        target_function="render_compaction_compact",
        aliases=(
            "compact engel thread",
            "engel compact thread",
            "compact thread",
        ),
        read_only=False,
        status_only=False,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_MCP_ALLOWLIST_DOCS_ROUTE_ID,
        label="Engel MCP allowlist docs (Claude-free)",
        target_module="engel_mcp_allowlist",
        target_function="render_mcp_allowlist_docs",
        aliases=(
            "engel mcp allowlist docs",
            "what is engel mcp allowlist",
            "mcp allowlist docs",
        ),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_MCP_ALLOWLIST_STATUS_ROUTE_ID,
        label="Engel MCP allowlist status (Claude-free)",
        target_module="engel_mcp_allowlist",
        target_function="render_mcp_allowlist_status",
        aliases=(
            "engel mcp allowlist status",
            "engel mcp allowlist",
            "mcp allowlist status",
        ),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_MCP_ALLOWLIST_LIST_ROUTE_ID,
        label="List Engel MCP allowlist entries",
        target_module="engel_mcp_allowlist",
        target_function="render_mcp_allowlist_list",
        aliases=(
            "list engel mcp allowlist",
            "show engel mcp allowlist",
            "mcp allowlist",
        ),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_ICM_DOCS_ROUTE_ID,
        label="ICM Architect method applied to Engel AI Main",
        target_module="engel_icm_architect",
        target_function="render_icm_docs",
        aliases=(
            "what is icm architect",
            "icm architect",
            "icm docs",
            "icm help",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_ICM_STATUS_ROUTE_ID,
        label="ICM-on-Engel workspace status",
        target_module="engel_icm_architect",
        target_function="render_icm_status",
        aliases=(
            "icm status",
            "icm architect status",
            "engel icm status",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_ICM_AUDIT_ROUTE_ID,
        label="ICM inventory of the current Engel AI Main app (no file moves)",
        target_module="engel_icm_architect",
        target_function="render_icm_audit",
        aliases=(
            "icm audit",
            "icm this",
            "icm inventory",
            "audit engel with icm",
        ),
        status_only=False,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_ICM_WORKSPACE_ROUTE_ID,
        label="ICM propose map and walk-test for Engel AI Main (no file moves)",
        target_module="engel_icm_architect",
        target_function="render_icm_workspace",
        aliases=(
            "icm workspace",
            "icm propose",
            "icm walk test",
        ),
        status_only=False,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_ICM_OUTPUTS_ROUTE_ID,
        label="List Engel AI Main outputs filed in the ICM workspace",
        target_module="engel_icm_output_router",
        target_function="render_icm_outputs",
        aliases=(
            "icm outputs",
            "where are icm outputs",
            "engel icm outputs",
            "list icm jobs",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_ICM_ROUTING_ROUTE_ID,
        label="Engel AI Main ICM output routing map",
        target_module="engel_icm_output_router",
        target_function="render_icm_routing",
        aliases=(
            "icm routing",
            "where does engel file outputs",
            "engel output routing",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_GRAPH_STUDIO_STATUS_ROUTE_ID,
        label="Engel Graph & Loop Studio status",
        target_module="engel_graph_loop_studio",
        target_function="render_graph_studio_status",
        aliases=(
            "graph studio status",
            "graph and loop studio",
            "graph studio",
            "engel graph studio",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_GRAPH_STUDIO_OPEN_ROUTE_ID,
        label="Open Engel Graph & Loop Studio",
        target_module="engel_graph_loop_studio",
        target_function="render_graph_studio_open",
        aliases=(
            "open graph studio",
            "open graph and loop studio",
            "launch graph studio",
            "show graph studio",
        ),
        read_only=False,
        status_only=False,
        no_visible_ui_change=False,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_GRAPH_STUDIO_NEW_ROUTE_ID,
        label="Create a new Engel engineering graph",
        target_module="engel_graph_loop_studio",
        target_function="render_graph_studio_new",
        aliases=(
            "new engel graph",
            "new graph studio graph",
            "create engel graph",
            "make a new graph",
        ),
        read_only=False,
        status_only=False,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_GRAPH_STUDIO_LIST_ROUTE_ID,
        label="List saved Engel engineering graphs",
        target_module="engel_graph_loop_studio",
        target_function="render_graph_studio_list",
        aliases=(
            "list engel graphs",
            "saved engel graphs",
            "graph studio list",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_GROVER_STATUS_ROUTE_ID,
        label="Engel Grover lane status",
        target_module="engel_grover_lane",
        target_function="render_grover_status",
        aliases=(
            "grover status",
            "grover lane",
            "engel grover",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_GROVER_EXPLAIN_ROUTE_ID,
        label="Explain Grover's algorithm",
        target_module="engel_grover_lane",
        target_function="render_grover_explain",
        aliases=(
            "explain grover",
            "explain grover's algorithm",
            "explain grovers algorithm",
            "what is grover's algorithm",
            "what is grovers algorithm",
            "grover speedup",
            "grover's algorithm",
            "grovers algorithm",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_GROVER_SEARCH_ROUTE_ID,
        label="Simulate Grover search",
        target_module="engel_grover_lane",
        target_function="render_grover_search",
        aliases=(
            "grover search",
            "simulate grover",
            "run grover",
            "grover demo",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_GROVER_CRYPTO_ROUTE_ID,
        label="Grover AES security heuristic",
        target_module="engel_grover_lane",
        target_function="render_grover_crypto",
        aliases=(
            "grover aes",
            "grover aes-128",
            "grover aes-256",
            "grover crypto",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_NEXT_STAGE_STATUS_ROUTE_ID,
        label="Engel next-stage merge status",
        target_module="engel_next_stage_runner",
        target_function="render_next_stage_status",
        aliases=(
            "next stage status",
            "next-stage status",
            "engel next stage",
            "storage pull merge status",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_NEXT_STAGE_INVENTORY_ROUTE_ID,
        label="Engel next-stage inventory",
        target_module="engel_next_stage_runner",
        target_function="render_next_stage_inventory",
        aliases=(
            "next stage inventory",
            "next-stage inventory",
            "storage pull inventory",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_NEXT_STAGE_COMPANION_ROUTE_ID,
        label="Engel companion 3B lane status",
        target_module="engel_next_stage_runner",
        target_function="render_next_stage_companion",
        aliases=(
            "companion 3b status",
            "engel companion 3b",
            "daily local companion",
            "next stage companion",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_NEXT_STAGE_SAFETY_ROUTE_ID,
        label="Engel next-stage safety gates",
        target_module="engel_next_stage_runner",
        target_function="render_next_stage_safety",
        aliases=(
            "next stage safety",
            "trading desk disarmed",
            "next-stage safety",
        ),
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_WIKI_ONE_STATUS_ROUTE_ID,
        label="Wiki One — Windows body map (read before landing CODE)",
        target_module="engel_wiki_one",
        target_function="render_wiki_one_status",
        aliases=(
            "wiki one",
            "wiki one map",
            "wiki one status",
            "windows body map",
            "engel wiki one",
            "engel wiki",
        ),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_WIKI_ONE_JOURNAL_ROUTE_ID,
        label="Wiki One Journal — CODE-landing stamps",
        target_module="engel_wiki_one",
        target_function="render_wiki_one_journal",
        aliases=(
            "wiki journal",
            "wiki one journal",
            "windows body journal",
            "engel wiki journal",
        ),
        read_only=True,
        status_only=True,
    ),
    EngelAIUpdateRoute(
        route_id=ENGEL_WIKI_ONE_UPDATE_ROUTE_ID,
        label="Wiki One update duty — whole Engel AI Main must keep the map current",
        target_module="engel_wiki_one",
        target_function="render_wiki_one_update",
        aliases=(
            "update wiki one",
            "wiki one update",
            "update the wiki",
            "wiki one contract",
        ),
        read_only=True,
        status_only=True,
    ),
)


def normalize_update_route_text(text: str) -> str:
    raw = str(text or "").strip().lower()
    replacements = {
        "\t": " ",
        "\r": " ",
        "\n": " ",
        "\\": " ",
        "/": " ",
        ".": "",
        ",": "",
        "!": "",
        "?": "",
        ":": "",
        ";": "",
        "\"": "",
        "'": "",
        "`": "",
    }
    for old, new in replacements.items():
        raw = raw.replace(old, new)
    return " ".join(raw.split())


def _alias_index() -> dict[str, str]:
    index: dict[str, str] = {}
    for route in UPDATE_ROUTES:
        for alias in route.aliases:
            index.setdefault(normalize_update_route_text(alias), route.route_id)
    return index


ALIASES_BY_NORMALIZED_TEXT = _alias_index()
ROUTE_BY_ID = {route.route_id: route for route in UPDATE_ROUTES}


def resolve_update_route(text: str) -> str:
    return ALIASES_BY_NORMALIZED_TEXT.get(normalize_update_route_text(text), "")


def is_update_route(route_id: str) -> bool:
    return str(route_id or "") in ROUTE_BY_ID


def route_metadata(route_id: str) -> dict[str, object]:
    route = ROUTE_BY_ID.get(str(route_id or ""))
    if route is None:
        return {}
    return {
        "route_id": route.route_id,
        "label": route.label,
        "target_module": route.target_module,
        "target_function": route.target_function,
        "aliases": list(route.aliases),
        "read_only": route.read_only,
        "status_only": route.status_only,
        "safe_for_ai_route": route.safe_for_ai_route,
        "no_memory_promotion": route.no_memory_promotion,
        "no_trusted_memory_write": route.no_trusted_memory_write,
        "no_fix_apply": route.no_fix_apply,
        "no_queue_route_mutation": route.no_queue_route_mutation,
        "no_archive_mutation": route.no_archive_mutation,
        "no_provider_model_network": route.no_provider_model_network,
        "no_background_worker": route.no_background_worker,
        "no_visible_ui_change": route.no_visible_ui_change,
    }


def describe_update_route(route_id: str) -> str:
    meta = route_metadata(route_id)
    if not meta:
        return "Unknown Engel AI update route."
    read_only = bool(meta.get("read_only"))
    status_only = bool(meta.get("status_only"))
    if read_only and status_only:
        mode = "local, read-only, status-only"
    else:
        mode = "local, explicit-user-action"
    boundaries: list[str] = []
    if bool(meta.get("no_memory_promotion")):
        boundaries.append("no memory promotion")
    if bool(meta.get("no_trusted_memory_write")):
        boundaries.append("no trusted-memory write")
    if bool(meta.get("no_fix_apply")):
        boundaries.append("no fix application")
    if bool(meta.get("no_queue_route_mutation")):
        boundaries.append("no host queue/route runtime mutation")
    if bool(meta.get("no_archive_mutation")):
        boundaries.append("no archive migration/copy/sync/delete")
    if bool(meta.get("no_provider_model_network")):
        boundaries.append("no provider/model/network behavior")
    else:
        boundaries.append("provider/model/network behavior possible only inside the explicit target route")
    if bool(meta.get("no_background_worker")):
        boundaries.append("no background worker")
    else:
        boundaries.append("background work possible only inside the explicit target route")
    return (
        "Known Engel AI route: "
        + str(meta["label"])
        + ". Mode: "
        + mode
        + ". Boundaries: "
        + "; ".join(boundaries)
        + "."
    )


def render_update_route(route_id: str, payload: str = "") -> str:
    route_id = str(route_id or "")
    try:
        if route_id == PROGRESS_ROUTE_ID:
            import engel_progress_dashboard

            return engel_progress_dashboard.render_progress_status()
        if route_id == MEMORY_CANDIDATE_ROUTE_ID:
            import engel_memory_candidate_inventory

            return engel_memory_candidate_inventory.render_inventory_status()
        if route_id == ARCHIVE_SHELF_ROUTE_ID:
            import engel_archive_shelf_manager

            return engel_archive_shelf_manager.render_archive_shelf_status()
        if route_id == ENGEL_AGENT_STATUS_ROUTE_ID:
            import engel_engel_agent_runner

            return engel_engel_agent_runner.render_engel_agent_status()
        if route_id == ENGEL_AGENT_INVOKE_ROUTE_ID:
            import engel_engel_agent_runner

            return engel_engel_agent_runner.render_engel_agent_invocation(payload)
        if route_id == ENGEL_AGENT_DOCTOR_ROUTE_ID:
            import engel_engel_agent_runner

            return engel_engel_agent_runner.render_engel_agent_doctor()
        if route_id == ENGEL_AGENT_VERSION_ROUTE_ID:
            import engel_engel_agent_runner

            return engel_engel_agent_runner.render_engel_agent_version()
        if route_id == ENGEL_AGENT_TOOLSETS_ROUTE_ID:
            import engel_engel_agent_runner

            return engel_engel_agent_runner.render_engel_agent_toolsets()
        if route_id == ENGEL_AGENT_GATEWAY_STATUS_ROUTE_ID:
            import engel_engel_agent_runner

            return engel_engel_agent_runner.render_engel_agent_gateway_status()
        if route_id == ENGEL_AGENT_GATEWAY_START_ROUTE_ID:
            import engel_engel_agent_runner

            return engel_engel_agent_runner.render_engel_agent_gateway_start()
        if route_id == ENGEL_AGENT_GATEWAY_STOP_ROUTE_ID:
            import engel_engel_agent_runner

            return engel_engel_agent_runner.render_engel_agent_gateway_stop()
        if route_id == ENGEL_AGENT_CRON_STATUS_ROUTE_ID:
            import engel_engel_agent_runner

            return engel_engel_agent_runner.render_engel_agent_cron_status()
        if route_id == ENGEL_AGENT_CRON_LIST_ROUTE_ID:
            import engel_engel_agent_runner

            return engel_engel_agent_runner.render_engel_agent_cron_list()
        if route_id == ENGEL_AGENT_MEMORY_STATUS_ROUTE_ID:
            import engel_engel_agent_runner

            return engel_engel_agent_runner.render_engel_agent_memory_status()
        if route_id == ENGEL_AGENT_SKILLS_LIST_ROUTE_ID:
            import engel_engel_agent_runner

            return engel_engel_agent_runner.render_engel_agent_skills_list()
        if route_id == ENGEL_AGENT_SESSIONS_LIST_ROUTE_ID:
            import engel_engel_agent_runner

            return engel_engel_agent_runner.render_engel_agent_sessions_list()
        if route_id == ENGEL_AGENT_SESSIONS_STATS_ROUTE_ID:
            import engel_engel_agent_runner

            return engel_engel_agent_runner.render_engel_agent_sessions_stats()
        if route_id == ENGEL_AGENT_PLUGINS_LIST_ROUTE_ID:
            import engel_engel_agent_runner

            return engel_engel_agent_runner.render_engel_agent_plugins_list()
        if route_id == ENGEL_AGENT_TOP_STATUS_ROUTE_ID:
            import engel_engel_agent_runner

            return engel_engel_agent_runner.render_engel_agent_top_status()
        if route_id == ENGEL3D_STATUS_ROUTE_ID:
            import engel_engel3d_runner

            return engel_engel3d_runner.render_engel3d_status(payload)
        if route_id == ENGEL3D_START_ROUTE_ID:
            import engel_engel3d_runner

            return engel_engel3d_runner.render_engel3d_start(payload)
        if route_id == ENGEL3D_STOP_ROUTE_ID:
            import engel_engel3d_runner

            return engel_engel3d_runner.render_engel3d_stop(payload)
        if route_id == ENGEL3D_BUILD_ROUTE_ID:
            import engel_engel3d_runner

            return engel_engel3d_runner.render_engel3d_build(payload)
        if route_id == ENGEL_SANDBOX_STATUS_ROUTE_ID:
            import engel_engel_sandbox_runner

            return engel_engel_sandbox_runner.render_engel_sandbox_status()
        if route_id == ENGEL_SANDBOX_NODES_ROUTE_ID:
            import engel_engel_sandbox_runner

            return engel_engel_sandbox_runner.render_engel_sandbox_nodes()
        if route_id == ENGEL_SANDBOX_LIST_ROUTE_ID:
            import engel_engel_sandbox_runner

            return engel_engel_sandbox_runner.render_engel_sandbox_list()
        if route_id == ENGEL_SANDBOX_CREATE_ROUTE_ID:
            import engel_engel_sandbox_runner

            return engel_engel_sandbox_runner.render_engel_sandbox_create()
        if route_id == ENGEL_SANDBOX_DELETE_ROUTE_ID:
            import engel_engel_sandbox_runner

            return engel_engel_sandbox_runner.render_engel_sandbox_delete(payload)
        if route_id == ENGEL_SANDBOX_BRING_UP_ROUTE_ID:
            import engel_engel_sandbox_runner

            return engel_engel_sandbox_runner.render_engel_sandbox_bring_up()
        if route_id == ENGEL_WSL_STATUS_ROUTE_ID:
            import engel_wsl_bridge

            return engel_wsl_bridge.render_wsl_status(payload)
        if route_id == ENGEL_WSL_DISTROS_ROUTE_ID:
            import engel_wsl_bridge

            return engel_wsl_bridge.render_wsl_distros(payload)
        if route_id == ENGEL_WSL_TOOLS_ROUTE_ID:
            import engel_wsl_bridge

            return engel_wsl_bridge.render_wsl_tools(payload)
        if route_id == ENGEL_WSL_PATHS_ROUTE_ID:
            import engel_wsl_bridge

            return engel_wsl_bridge.render_wsl_paths(payload)
        if route_id == ENGEL_WSL_SELF_TEST_ROUTE_ID:
            import engel_wsl_bridge

            return engel_wsl_bridge.render_wsl_self_test(payload)
        if route_id == ENGEL_WSL_UBUNTU_RUNTIME_STATUS_ROUTE_ID:
            import engel_wsl_ubuntu_runner

            return engel_wsl_ubuntu_runner.render_wsl_ubuntu_runtime_status()
        if route_id == ENGEL_WSL_UBUNTU_RUNTIME_FACTS_ROUTE_ID:
            import engel_wsl_ubuntu_runner

            return engel_wsl_ubuntu_runner.render_wsl_ubuntu_runtime_facts()
        if route_id == ENGEL_WSL_UBUNTU_RUNTIME_SAFETY_ROUTE_ID:
            import engel_wsl_ubuntu_runner

            return engel_wsl_ubuntu_runner.render_wsl_ubuntu_runtime_safety()
        if route_id == ENGEL_WSL_UBUNTU_RUNTIME_STAGE_2_ROUTE_ID:
            import engel_wsl_ubuntu_runner

            return engel_wsl_ubuntu_runner.render_wsl_ubuntu_runtime_stage_2()
        if route_id == ENGEL_WSL_UBUNTU_RUNTIME_STAGE_3_ROUTE_ID:
            import engel_wsl_ubuntu_runner

            return engel_wsl_ubuntu_runner.render_wsl_ubuntu_runtime_stage_3()
        if route_id == ENGELCODE_STATUS_ROUTE_ID:
            import engel_engelcode_runner

            return engel_engelcode_runner.render_engelcode_status()
        if route_id == ENGELCODE_VERSION_ROUTE_ID:
            import engel_engelcode_runner

            return engel_engelcode_runner.render_engelcode_version()
        if route_id == ENGELCODE_CRATES_ROUTE_ID:
            import engel_engelcode_runner

            return engel_engelcode_runner.render_engelcode_crates()
        if route_id == ENGELCODE_BUILD_ROUTE_ID:
            import engel_engelcode_runner

            return engel_engelcode_runner.render_engelcode_build()
        if route_id == ENGELCODE_INVOKE_ROUTE_ID:
            import engel_engelcode_runner

            return engel_engelcode_runner.render_engelcode_invoke(payload)
        if route_id == ENGELCODE_BRING_UP_ROUTE_ID:
            import engel_engelcode_runner

            return engel_engelcode_runner.render_engelcode_bring_up()
        if route_id == ENGEL_MAIN_STATUS_ROUTE_ID:
            import engel_ai_main_rust_ui_shell_bridge

            return engel_ai_main_rust_ui_shell_bridge.render_engel_main_status()
        if route_id == ENGEL_MAIN_VERSION_ROUTE_ID:
            import engel_ai_main_rust_ui_shell_bridge

            return engel_ai_main_rust_ui_shell_bridge.render_engel_main_version()
        if route_id == ENGEL_MAIN_BINARIES_ROUTE_ID:
            import engel_ai_main_rust_ui_shell_bridge

            return engel_ai_main_rust_ui_shell_bridge.render_engel_main_binaries()
        if route_id == ENGEL_MAIN_INSTALL_ROUTE_ID:
            import engel_ai_main_rust_ui_shell_bridge

            return engel_ai_main_rust_ui_shell_bridge.render_engel_main_install()
        if route_id == ENGEL_MAIN_BUILD_ROUTE_ID:
            import engel_ai_main_rust_ui_shell_bridge

            return engel_ai_main_rust_ui_shell_bridge.render_engel_main_build()
        if route_id == ENGEL_MAIN_DEV_START_ROUTE_ID:
            import engel_ai_main_rust_ui_shell_bridge

            return engel_ai_main_rust_ui_shell_bridge.render_engel_main_dev_start()
        if route_id == ENGEL_MAIN_DEV_STOP_ROUTE_ID:
            import engel_ai_main_rust_ui_shell_bridge

            return engel_ai_main_rust_ui_shell_bridge.render_engel_main_dev_stop()
        if route_id == ENGEL_MAIN_TAURI_BUILD_ROUTE_ID:
            import engel_ai_main_rust_ui_shell_bridge

            return engel_ai_main_rust_ui_shell_bridge.render_engel_main_tauri_build()
        if route_id == ENGEL_MAIN_BRING_UP_ROUTE_ID:
            import engel_ai_main_rust_ui_shell_bridge

            return engel_ai_main_rust_ui_shell_bridge.render_engel_main_bring_up()
        if route_id == ENGEL_LAN_STATUS_ROUTE_ID:
            import engel_engel_lan_runner

            return engel_engel_lan_runner.render_engel_lan_status()
        if route_id == ENGEL_LAN_VERSION_ROUTE_ID:
            import engel_engel_lan_runner

            return engel_engel_lan_runner.render_engel_lan_version()
        if route_id == ENGEL_LAN_CLI_HELP_ROUTE_ID:
            import engel_engel_lan_runner

            return engel_engel_lan_runner.render_engel_lan_cli_help()
        if route_id == ENGEL_LAN_CLI_RECEIVE_START_ROUTE_ID:
            import engel_engel_lan_runner

            return engel_engel_lan_runner.render_engel_lan_cli_receive_start()
        if route_id == ENGEL_LAN_CLI_RECEIVE_STOP_ROUTE_ID:
            import engel_engel_lan_runner

            return engel_engel_lan_runner.render_engel_lan_cli_receive_stop()
        if route_id == ENGEL_LAN_APP_DEV_START_ROUTE_ID:
            import engel_engel_lan_runner

            return engel_engel_lan_runner.render_engel_lan_app_dev_start()
        if route_id == ENGEL_LAN_APP_DEV_STOP_ROUTE_ID:
            import engel_engel_lan_runner

            return engel_engel_lan_runner.render_engel_lan_app_dev_stop()
        if route_id == ENGEL_LAN_BRING_UP_ROUTE_ID:
            import engel_engel_lan_runner

            return engel_engel_lan_runner.render_engel_lan_bring_up()
        if route_id == ENGEL_LAN_WORKERS_SCAN_ROUTE_ID:
            import engel_lan_worker
            return engel_lan_worker.render_lan_workers_scan()
        if route_id == ENGEL_LAN_WORKERS_STATUS_ROUTE_ID:
            import engel_lan_worker
            return engel_lan_worker.render_lan_workers_status()
        if route_id == ENGEL_LAN_WORKERS_ADD_ROUTE_ID:
            import engel_lan_worker
            return engel_lan_worker.render_lan_workers_add(str(payload or ""))
        if route_id == ENGEL_LAN_WORKERS_REMOVE_ROUTE_ID:
            import engel_lan_worker
            return engel_lan_worker.render_lan_workers_remove(str(payload or ""))
        if route_id == ENGEL_LAN_WORKER_DISPATCH_ROUTE_ID:
            import engel_lan_worker
            return engel_lan_worker.render_lan_worker_dispatch(str(payload or ""))
        if route_id == ENGEL_LAN_NETWORK_DEVICES_ROUTE_ID:
            import engel_lan_worker
            return engel_lan_worker.render_lan_network_devices()
        if route_id == ENGEL_ADB_WORKERS_STATUS_ROUTE_ID:
            import engel_adb_worker_manager
            return engel_adb_worker_manager.render_adb_workers_status()
        if route_id == ENGEL_ADB_WORKERS_PULL_ROUTE_ID:
            import engel_adb_worker_manager
            return engel_adb_worker_manager.render_adb_workers_pull_results()
        if route_id == ENGEL_ADB_WORKERS_PUSH_ROUTE_ID:
            import engel_adb_worker_manager
            return engel_adb_worker_manager.render_adb_workers_push_jobs()
        if route_id == ENGEL_ADB_WORKERS_RESULT_ROUTE_ID:
            import engel_adb_worker_manager
            return engel_adb_worker_manager.render_adb_workers_latest_result()
        if route_id == ENGEL_ADB_WORKERS_PROVISION_ROUTE_ID:
            import engel_adb_worker_manager
            return engel_adb_worker_manager.render_adb_provision_worker(str(payload or ""))
        if route_id == ENGEL_ADB_WORKERS_JOBS_ROUTE_ID:
            import engel_adb_worker_manager
            return engel_adb_worker_manager.render_adb_workers_jobs()
        if route_id == ENGEL_ADB_WORKERS_CREATE_JOB_ROUTE_ID:
            import engel_adb_worker_manager
            return engel_adb_worker_manager.render_adb_create_job(str(payload or ""))
        if route_id == ENGEL_LAN_PAIRING_STATUS_ROUTE_ID:
            import engel_remote_worker_lan_pairing
            return engel_remote_worker_lan_pairing.render_lan_pairing_status()
        if route_id == ENGEL_LAN_PAIRING_TOKEN_ROUTE_ID:
            import engel_remote_worker_lan_pairing
            return engel_remote_worker_lan_pairing.render_lan_pairing_token()
        if route_id == ENGEL_MULTI_ANDROID_STATUS_ROUTE_ID:
            import engel_multi_android_remote_workers
            return engel_multi_android_remote_workers.render_status()
        if route_id == ENGEL_MULTI_ANDROID_LINKS_ROUTE_ID:
            import engel_multi_android_remote_workers
            return engel_multi_android_remote_workers.render_check_links()
        if route_id == ENGEL_WORKER_ASSIGNMENT_STATUS_ROUTE_ID:
            import engel_remote_worker_job_assignment
            return engel_remote_worker_job_assignment.render_status()
        if route_id == ENGEL_WORKER_ASSIGNMENT_JOBS_ROUTE_ID:
            import engel_remote_worker_job_assignment
            return engel_remote_worker_job_assignment.render_prepared_jobs()
        if route_id == ENGEL_RESULT_INTAKE_STATUS_ROUTE_ID:
            import engel_remote_worker_result_intake
            return engel_remote_worker_result_intake.render_status()
        if route_id == ENGEL_RESULT_INTAKE_LIST_ROUTE_ID:
            import engel_remote_worker_result_intake
            return engel_remote_worker_result_intake.render_list()
        if route_id == ENGEL_RUNTIME_READINESS_ROUTE_ID:
            import engel_ai_runtime_readiness
            return engel_ai_runtime_readiness.render_status()
        if route_id == ENGEL_SYSTEM_INTEGRATION_STATUS_ROUTE_ID:
            import engel_system_integration_status
            return engel_system_integration_status.render_status()
        if route_id == ENGEL_CORE_V1_DASHBOARD_ROUTE_ID:
            import engel_core_v1_dashboard_status
            return engel_core_v1_dashboard_status.render_core_v1_dashboard_status()
        if route_id == ENGEL_DAILY_CYCLE_STATUS_ROUTE_ID:
            import engel_daily_cycle_status_surface
            return engel_daily_cycle_status_surface.render_status_surface()
        if route_id == ENGEL_CANDIDATE_REVIEW_DASHBOARD_ROUTE_ID:
            import engel_candidate_review_dashboard
            return "\n".join(engel_candidate_review_dashboard.render_candidate_counts())
        if route_id == ENGEL_APPROVED_MEMORY_STATUS_ROUTE_ID:
            import engel_approved_memory_promotion
            return engel_approved_memory_promotion.render_status()
        if route_id == ENGEL_APPROVED_MEMORY_CANDIDATES_ROUTE_ID:
            import engel_approved_memory_promotion
            return engel_approved_memory_promotion.render_candidates()
        if route_id == ENGEL_BROWSER_QUEEN_STATUS_ROUTE_ID:
            import engel_browser_queen_phase3_contract
            return engel_browser_queen_phase3_contract.render_browser_queen_phase3_contract_status()
        if route_id == ENGEL_BROWSER_QUEEN_PHASE2_ROUTE_ID:
            import engel_browser_queen_phase2_status
            return engel_browser_queen_phase2_status.render_browser_queen_phase2_status()
        if route_id == ENGEL_BROWSER_QUEEN_WORKBENCH_ROUTE_ID:
            import engel_browser_queen_workbench
            return engel_browser_queen_workbench.render_browser_queen_phase_status()
        if route_id == ENGEL_BROWSER_QUEEN_MVP_ROUTE_ID:
            import engel_browser_queen_runtime_mvp
            return engel_browser_queen_runtime_mvp.render_browser_queen_mvp_status()
        if route_id == ENGEL_RESEARCH_OFFICE_STATUS_ROUTE_ID:
            import engel_research_office_data
            from pathlib import Path as _Path
            return engel_research_office_data.render_research_office_status(str(_Path(__file__).resolve().parent))
        if route_id == ENGEL_RESEARCH_OFFICE_MAP_ROUTE_ID:
            import engel_research_office_data
            from pathlib import Path as _Path
            return engel_research_office_data.render_research_office_map(str(_Path(__file__).resolve().parent))
        if route_id == ENGEL_RESEARCH_TOGGLE_STATUS_ROUTE_ID:
            import engel_research_toggle_status
            return engel_research_toggle_status.render_status()
        if route_id == ENGEL_RESEARCH_TOGGLE_EXPLAIN_ROUTE_ID:
            import engel_research_toggle_status
            return engel_research_toggle_status.render_explain()
        if route_id == ENGEL_SELF_LEARNING_STATUS_ROUTE_ID:
            import engel_self_learning_status_surface
            return engel_self_learning_status_surface.render_status_surface()
        if route_id == ENGEL_PRODUCT_WORKBENCH_STATUS_ROUTE_ID:
            import engel_code_companion_product_workbench
            return engel_code_companion_product_workbench.render_selected_product_workbench(str(payload or "") or None)
        if route_id == ENGEL_PRODUCT_CYCLE_DASHBOARD_ROUTE_ID:
            import engel_code_companion_product_cycle_dashboard
            return engel_code_companion_product_cycle_dashboard.render_selected_product_cycle_dashboard(str(payload or ""))
        if route_id == ENGEL_CORE_CONTINUITY_STATUS_ROUTE_ID:
            import engel_core_continuity_status_surface
            return engel_core_continuity_status_surface.render_controlled_library_chain_status()
        if route_id == ENGEL_MEMORY_ARCHIVE_STATUS_ROUTE_ID:
            import engel_memory_archive_status
            return engel_memory_archive_status.render_memory_archive_status()
        if route_id == ENGEL_MEMORY_CANDIDATE_REVIEW_ROUTE_ID:
            import engel_memory_candidate_review_dashboard
            return engel_memory_candidate_review_dashboard.render_memory_candidate_review_dashboard()
        if route_id == ENGEL_OFFLINE_MODEL_CONTRACT_ROUTE_ID:
            import engel_offline_model_runtime_contract
            return engel_offline_model_runtime_contract.render_offline_model_runtime_status()
        if route_id == ENGEL_PROGRESS_REPORT_ROUTE_ID:
            import engel_progress_dashboard
            return engel_progress_dashboard.render_progress_report()
        if route_id == ENGEL_WHOLE_SYSTEM_AUDIT_ROUTE_ID:
            import engel_whole_system_incomplete_audit
            return engel_whole_system_incomplete_audit.render_report()
        if route_id == ENGEL_COLONY_SIMULATION_ROUTE_ID:
            import engel_research_status
            return engel_research_status.render_colony_simulation_status()
        if route_id == ENGEL_AI_BODY_STATUS_ROUTE_ID:
            import engel_ai_body_status
            return engel_ai_body_status.render_ai_body_status_text()
        if route_id == ENGEL_WSL_BRIDGE_STATUS_ROUTE_ID:
            import engel_wsl_bridge
            return engel_wsl_bridge.render_json_status()
        if route_id == ENGEL_PROTECTED_ACTIONS_LIST_ROUTE_ID:
            import engel_protected_action_registry
            return engel_protected_action_registry.render_action_list()
        if route_id == ENGEL_PATCH_RECEIPTS_LIST_ROUTE_ID:
            import engel_code_companion_patch_receipt_viewer
            return engel_code_companion_patch_receipt_viewer.render_receipt_list()
        if route_id == ENGEL_LOWRISK_SELFFIX_STATUS_ROUTE_ID:
            import engel_low_risk_self_fix_status_surface
            return engel_low_risk_self_fix_status_surface.render_status()
        if route_id == ENGEL_MEMORY_INVENTORY_ROUTE_ID:
            import engel_memory_candidate_inventory
            return engel_memory_candidate_inventory.render_inventory_report()
        if route_id == ENGEL_RUNTIME_PATH_CONFIG_ROUTE_ID:
            import engel_ai_local_runtime_path_config
            return engel_ai_local_runtime_path_config.render_status()
        if route_id == ENGEL_LLAMA_COMPAT_MATRIX_ROUTE_ID:
            import engel_ai_llama_cpp_compatibility_matrix
            return engel_ai_llama_cpp_compatibility_matrix.render_status()
        if route_id == ENGEL_RESEARCH_TO_FIX_SUMMARY_ROUTE_ID:
            import engel_research_to_fix_loop
            return engel_research_to_fix_loop.render_summary()
        if route_id == ENGEL_OFFLINE_SEED_LLM_ROUTE_ID:
            import engel_offline_seed_llm
            return engel_offline_seed_llm.render_offline_seed_llm_status()
        if route_id == ENGEL_ARCHIVE_SHELF_REPORT_ROUTE_ID:
            import engel_archive_shelf_manager
            return engel_archive_shelf_manager.render_archive_shelf_report()
        if route_id == ENGEL_TRUTHFULNESS_GUARD_ROUTE_ID:
            import engel_truthfulness_anti_flattery_guard
            return engel_truthfulness_anti_flattery_guard.render_status()
        if route_id == ENGEL_OUTSIDE_AI_BOUNDARY_ROUTE_ID:
            import engel_outside_ai_boundary
            return engel_outside_ai_boundary.render_status()
        if route_id == ENGEL_PASSWORD_GATE_ROUTE_ID:
            import engel_global_password_gate
            return engel_global_password_gate.render_status()
        if route_id == ENGEL_COLONY_HIVE_MAP_ROUTE_ID:
            import engel_research_office_data
            from pathlib import Path as _Path
            return engel_research_office_data.render_colony_hive_map(str(_Path(__file__).resolve().parent))
        if route_id == ENGEL_COLONY_HIVE_STATUS_ROUTE_ID:
            import engel_research_office_data
            from pathlib import Path as _Path
            return engel_research_office_data.render_colony_hive_status(str(_Path(__file__).resolve().parent))
        if route_id == ENGEL_COLONY_HIVE_PERMISSIONS_ROUTE_ID:
            import engel_research_office_data
            from pathlib import Path as _Path
            return engel_research_office_data.render_colony_hive_permissions(str(_Path(__file__).resolve().parent))
        if route_id == ENGEL_COLONY_HIVE_QUEEN_LINKS_ROUTE_ID:
            import engel_research_office_data
            from pathlib import Path as _Path
            return engel_research_office_data.render_colony_hive_queen_links(str(_Path(__file__).resolve().parent))
        if route_id == ENGEL_COMMUNICATION_QUEEN_STATUS_ROUTE_ID:
            import engel_research_office_data
            from pathlib import Path as _Path
            return engel_research_office_data.render_communication_queen_status(str(_Path(__file__).resolve().parent))
        if route_id == ENGEL_ENGEL_MIND_CONNECTIONS_ROUTE_ID:
            import engel_research_office_data
            from pathlib import Path as _Path
            return engel_research_office_data.render_engel_mind_connections_status(str(_Path(__file__).resolve().parent))
        if route_id == ENGEL_FUTURE_UPGRADES_STATUS_ROUTE_ID:
            import engel_research_office_data
            from pathlib import Path as _Path
            return engel_research_office_data.render_future_upgrades_status(str(_Path(__file__).resolve().parent))
        if route_id == ENGEL_LONG_TERM_MEMORY_DRIVE_ROUTE_ID:
            import engel_research_office_data
            return engel_research_office_data.render_long_term_memory_drive_status()
        if route_id == ENGEL_PRODUCT_CONTEXT_PACK_ROUTE_ID:
            import engel_code_companion_product_context
            return engel_code_companion_product_context.render_selected_product_context_pack("")
        if route_id == ENGEL_GUIDED_LIBRARY_REVIEW_ROUTE_ID:
            import engel_guided_library_review_surface
            return engel_guided_library_review_surface.render_surface_text()
        if route_id == ENGEL_HUMAN_REVIEW_DRAFT_SURFACE_ROUTE_ID:
            import engel_human_review_receipt_draft_surface
            return engel_human_review_receipt_draft_surface.render_surface_text()
        if route_id == ENGEL_TRUSTED_MEMORY_TARGET_ROUTE_ID:
            import engel_trusted_memory_target
            return engel_trusted_memory_target.render_status()
        if route_id == ENGEL_SELF_FIX_RECEIPT_LIST_ROUTE_ID:
            import engel_self_fix_receipt_viewer
            return engel_self_fix_receipt_viewer.render_receipt_list()
        if route_id == ENGEL_INTENT_PLANNER_STATUS_ROUTE_ID:
            import engel_ai_intent_planner
            return engel_ai_intent_planner.render_status()
        if route_id == ENGEL_INTENT_PLANNER_HELP_ROUTE_ID:
            import engel_ai_intent_planner
            return engel_ai_intent_planner.render_help()
        if route_id == ENGEL_INTENT_BRIDGE_DOCS_ROUTE_ID:
            import engel_lifted_intent
            return engel_lifted_intent.render_docs(payload)
        if route_id == ENGEL_INTENT_BRIDGE_STATUS_ROUTE_ID:
            import engel_lifted_intent
            return engel_lifted_intent.render_status(payload)
        if route_id == ENGEL_INTENT_BRIDGE_LATEST_ROUTE_ID:
            import engel_lifted_intent
            return engel_lifted_intent.render_latest(payload)
        if route_id == ENGEL_INTENT_BRIDGE_LIFT_ROUTE_ID:
            import engel_lifted_intent
            return engel_lifted_intent.render_lift(payload)
        if route_id == ENGEL_SPEECH_SPC_DOCS_ROUTE_ID:
            import engel_speech_spc
            return engel_speech_spc.render_docs(payload)
        if route_id == ENGEL_SPEECH_SPC_STATUS_ROUTE_ID:
            import engel_speech_spc
            return engel_speech_spc.render_status(payload)
        if route_id == ENGEL_SPEECH_SPC_LATEST_ROUTE_ID:
            import engel_speech_spc
            return engel_speech_spc.render_latest(payload)
        if route_id == ENGEL_SPEECH_SPC_COMPILE_ROUTE_ID:
            import engel_speech_spc
            return engel_speech_spc.render_compile(payload)
        if route_id == ENGEL_MIPL_AGENT_DOCS_ROUTE_ID:
            import engel_mipl_agent_work

            return engel_mipl_agent_work.render_docs(payload)
        if route_id == ENGEL_MIPL_AGENT_SKILLS_ROUTE_ID:
            import engel_mipl_agent_work

            return engel_mipl_agent_work.render_skills(payload)
        if route_id == ENGEL_MIPL_AGENT_STATUS_ROUTE_ID:
            import engel_mipl_agent_work

            return engel_mipl_agent_work.render_status(payload)
        if route_id == ENGEL_MIPL_AGENT_LIST_ROUTE_ID:
            import engel_mipl_agent_work

            return engel_mipl_agent_work.render_list(payload)
        if route_id == ENGEL_MODEL_INTAKE_LIST_ROUTE_ID:
            import engel_ai_manual_model_file_intake
            return engel_ai_manual_model_file_intake.render_list()
        if route_id == ENGEL_MODEL_INTAKE_STATUS_ROUTE_ID:
            import engel_ai_manual_model_file_intake
            return engel_ai_manual_model_file_intake.render_status()
        if route_id == ENGEL_MODEL_REVIEW_APPROVAL_STATUS_ROUTE_ID:
            import engel_ai_model_review_approval
            return engel_ai_model_review_approval.render_status()
        if route_id == ENGEL_MODEL_REVIEW_APPROVAL_LIST_ROUTE_ID:
            import engel_ai_model_review_approval
            return engel_ai_model_review_approval.render_list()
        if route_id == ENGEL_NO_GENERATION_LOAD_CHECK_ROUTE_ID:
            import engel_ai_no_generation_load_check
            return engel_ai_no_generation_load_check.render_status()
        if route_id == ENGEL_OFFLINE_RUNTIME_DRY_RUN_STATUS_ROUTE_ID:
            import engel_ai_offline_runtime_dry_run
            return engel_ai_offline_runtime_dry_run.render_status()
        if route_id == ENGEL_OFFLINE_RUNTIME_DRY_RUN_MODELS_ROUTE_ID:
            import engel_ai_offline_runtime_dry_run
            return engel_ai_offline_runtime_dry_run.render_list_models()
        if route_id == ENGEL_LOCAL_RUNTIME_PATH_ROOTS_ROUTE_ID:
            import engel_ai_local_runtime_path_config
            return engel_ai_local_runtime_path_config.render_roots()
        if route_id == ENGEL_BQ_PHASE4_CONTRACT_ROUTE_ID:
            import engel_browser_queen_phase4_contract
            return engel_browser_queen_phase4_contract.render_browser_queen_phase4_contract_status()
        if route_id == ENGEL_BQ_PHASE5_CONTRACT_ROUTE_ID:
            import engel_browser_queen_phase5_contract
            return engel_browser_queen_phase5_contract.render_browser_queen_phase5_contract_status()
        if route_id == ENGEL_CANDIDATE_LEARNING_STATUS_ROUTE_ID:
            import engel_candidate_learning_output_review
            return engel_candidate_learning_output_review.render_status()
        if route_id == ENGEL_CANDIDATE_REVIEW_DASHBOARD2_ROUTE_ID:
            import engel_candidate_review_dashboard
            return engel_candidate_review_dashboard.render_dashboard()
        if route_id == ENGEL_CANDIDATE_SET_APPROVAL_STATUS_ROUTE_ID:
            import engel_candidate_set_approval
            return engel_candidate_set_approval.render_status()
        if route_id == ENGEL_CHAT_EXPORT_INTAKE_STATUS_ROUTE_ID:
            import engel_chat_export_intake
            return engel_chat_export_intake.render_status()
        if route_id == ENGEL_CHAT_EXPORT_INTAKE_LIST_ROUTE_ID:
            import engel_chat_export_intake
            return engel_chat_export_intake.render_list()
        if route_id == ENGEL_CC_CANDIDATE_REVIEW_STATUS_ROUTE_ID:
            import engel_code_companion_candidate_review_status
            return engel_code_companion_candidate_review_status.render_status()
        if route_id == ENGEL_CC_FIX_CANDIDATE_INTAKE_STATUS_ROUTE_ID:
            import engel_code_companion_fix_candidate_intake
            return engel_code_companion_fix_candidate_intake.render_status()
        if route_id == ENGEL_CC_FIX_CANDIDATE_INTAKE_LIST_ROUTE_ID:
            import engel_code_companion_fix_candidate_intake
            return engel_code_companion_fix_candidate_intake.render_list()
        if route_id == ENGEL_CC_LOW_RISK_PATCH_RUNNER_ROUTE_ID:
            import engel_code_companion_low_risk_patch_runner
            return engel_code_companion_low_risk_patch_runner.render_status()
        if route_id == ENGEL_CC_PASSWORD_GATE_INTEGRATION_ROUTE_ID:
            import engel_code_companion_password_gate_integration
            return engel_code_companion_password_gate_integration.render_status()
        if route_id == ENGEL_CC_PATCH_APPLICATION_GATE_STATUS_ROUTE_ID:
            import engel_code_companion_patch_application_gate
            return engel_code_companion_patch_application_gate.render_status()
        if route_id == ENGEL_CC_PATCH_APPLICATION_GATE_LIST_ROUTE_ID:
            import engel_code_companion_patch_application_gate
            return engel_code_companion_patch_application_gate.render_list()
        if route_id == ENGEL_CC_PATCH_APPLY_RECEIPT_STATUS_ROUTE_ID:
            import engel_code_companion_patch_apply_approval_receipt
            return engel_code_companion_patch_apply_approval_receipt.render_status()
        if route_id == ENGEL_CC_PATCH_APPLY_RECEIPT_LIST_ROUTE_ID:
            import engel_code_companion_patch_apply_approval_receipt
            return engel_code_companion_patch_apply_approval_receipt.render_list()
        if route_id == ENGEL_CC_PATCH_APPLY_DRY_RUN_STATUS_ROUTE_ID:
            import engel_code_companion_patch_apply_dry_run
            return engel_code_companion_patch_apply_dry_run.render_status()
        if route_id == ENGEL_CC_PATCH_APPLY_DRY_RUN_LIST_ROUTE_ID:
            import engel_code_companion_patch_apply_dry_run
            return engel_code_companion_patch_apply_dry_run.render_list()
        if route_id == ENGEL_CC_PATCH_BUNDLE_DRAFT_STATUS_ROUTE_ID:
            import engel_code_companion_patch_bundle_draft
            return engel_code_companion_patch_bundle_draft.render_status()
        if route_id == ENGEL_CC_PATCH_BUNDLE_DRAFT_LIST_ROUTE_ID:
            import engel_code_companion_patch_bundle_draft
            return engel_code_companion_patch_bundle_draft.render_list()
        if route_id == ENGEL_CC_PATCH_CLASS_ALLOWLIST_STATUS_ROUTE_ID:
            import engel_code_companion_patch_class_allowlist
            return engel_code_companion_patch_class_allowlist.render_status()
        if route_id == ENGEL_CC_PATCH_CLASS_ALLOWLIST_CLASSES_ROUTE_ID:
            import engel_code_companion_patch_class_allowlist
            return engel_code_companion_patch_class_allowlist.render_classes()
        if route_id == ENGEL_CC_PATCH_PLAN_PREVIEW_STATUS_ROUTE_ID:
            import engel_code_companion_patch_plan_preview
            return engel_code_companion_patch_plan_preview.render_status()
        if route_id == ENGEL_CC_PATCH_PLAN_PREVIEW_LIST_ROUTE_ID:
            import engel_code_companion_patch_plan_preview
            return engel_code_companion_patch_plan_preview.render_list()
        if route_id == ENGEL_CC_PATCH_STATUS_SURFACE_ROUTE_ID:
            import engel_code_companion_patch_status_surface
            return engel_code_companion_patch_status_surface.render_status()
        if route_id == ENGEL_CC_PROTECTED_PATCH_APPLY_ROUTE_ID:
            import engel_code_companion_protected_patch_apply
            return engel_code_companion_protected_patch_apply.render_status()
        if route_id == ENGEL_DAILY_CYCLE_RECEIPT_LIST_ROUTE_ID:
            import engel_daily_cycle_status_surface
            return engel_daily_cycle_status_surface.render_receipt_list()
        if route_id == ENGEL_EXTERNAL_MEMORY_ROOTS_ROUTE_ID:
            import engel_external_memory_roots
            return engel_external_memory_roots.render_external_memory_status()
        if route_id == ENGEL_FIX_CANDIDATE_QUEUE_STATUS_ROUTE_ID:
            import engel_fix_candidate_queue
            return engel_fix_candidate_queue.render_status()
        if route_id == ENGEL_FIX_CANDIDATE_QUEUE_LIST_ROUTE_ID:
            import engel_fix_candidate_queue
            return engel_fix_candidate_queue.render_list()
        if route_id == ENGEL_GUIDED_LIBRARY_DRAFT_REPORT_ROUTE_ID:
            import engel_guided_library_review_draft_report
            return engel_guided_library_review_draft_report.render_draft_report()
        if route_id == ENGEL_HUMAN_REVIEW_DRAFT_PREVIEW_ROUTE_ID:
            import engel_human_review_receipt_draft_surface
            return engel_human_review_receipt_draft_surface.render_receipt_draft_preview()
        if route_id == ENGEL_LEARNING_JOB_QUEUE_STATUS_ROUTE_ID:
            import engel_learning_job_queue
            return engel_learning_job_queue.render_status()
        if route_id == ENGEL_LEARNING_JOB_QUEUE_LIST_ROUTE_ID:
            import engel_learning_job_queue
            return engel_learning_job_queue.render_list()
        if route_id == ENGEL_MEMORY_ROOTS_STORAGE_STATUS_ROUTE_ID:
            import engel_memory_roots_storage_layout
            return engel_memory_roots_storage_layout.render_status()
        if route_id == ENGEL_MEMORY_ROOTS_STORAGE_ROOTS_ROUTE_ID:
            import engel_memory_roots_storage_layout
            return engel_memory_roots_storage_layout.render_roots()
        if route_id == ENGEL_REMOTE_WORKER_APP_SCAFFOLD_ROUTE_ID:
            import engel_remote_worker_app_scaffold
            return engel_remote_worker_app_scaffold.render_status()
        if route_id == ENGEL_RESEARCH_TO_FIX_LOOP_ROUTE_ID:
            import engel_research_to_fix_loop
            return engel_research_to_fix_loop.render_status()
        if route_id == ENGEL_RESEARCH_TOGGLE_WORKER_ROUTE_ID:
            import engel_research_toggle_worker
            return engel_research_toggle_worker.render_status()
        if route_id == ENGEL_SELF_LEARNING_CONTROLLER_ROUTE_ID:
            import engel_self_learning_run_controller
            return engel_self_learning_run_controller.render_status()
        if route_id == ENGEL_SYSTEM_INTEGRATION_CHECK_LINKS_ROUTE_ID:
            import engel_system_integration_status
            return engel_system_integration_status.render_check_links()
        if route_id == ENGEL_TRAINING_TRUSTED_MEMORY_STATUS_ROUTE_ID:
            import engel_training_trusted_memory
            return engel_training_trusted_memory.render_status()
        if route_id == ENGEL_TRAINING_TRUSTED_MEMORY_PREVIEW_ROUTE_ID:
            import engel_training_trusted_memory
            return engel_training_trusted_memory.render_preview()
        if route_id == ENGEL_WHOLE_SYSTEM_AUDIT_STATUS_ROUTE_ID:
            import engel_whole_system_incomplete_audit
            return engel_whole_system_incomplete_audit.render_status()
        if route_id == ENGEL_AI_GROWTH_FOLDER_STATUS_ROUTE_ID:
            import engel_ai_growth_dashboard
            result = engel_ai_growth_dashboard.render_folder_status()
            return "\n".join(result) if isinstance(result, list) else result
        if route_id == ENGEL_RUNTIME_READINESS_MODEL_ROUTE_ID:
            import engel_ai_runtime_readiness
            return engel_ai_runtime_readiness.render_model_summary()
        if route_id == ENGEL_RUNTIME_READINESS_LIBRARY_ROUTE_ID:
            import engel_ai_runtime_readiness
            return engel_ai_runtime_readiness.render_library_summary()
        if route_id == ENGEL_RUNTIME_READINESS_SAFETY_ROUTE_ID:
            import engel_ai_runtime_readiness
            return engel_ai_runtime_readiness.render_safety_summary()
        if route_id == ENGEL_RUNTIME_READINESS_REMOTE_WORKER_ROUTE_ID:
            import engel_ai_runtime_readiness
            return engel_ai_runtime_readiness.render_remote_worker_summary()
        if route_id == ENGEL_RUNTIME_READINESS_CODE_COMPANION_ROUTE_ID:
            import engel_ai_runtime_readiness
            return engel_ai_runtime_readiness.render_code_companion_summary()
        if route_id == ENGEL_RUNTIME_READINESS_NEXT_ROUTE_ID:
            import engel_ai_runtime_readiness
            return engel_ai_runtime_readiness.render_next_summary()
        if route_id == ENGEL_BOUNDED_LOCAL_CHAT_SMOKE_ROUTE_ID:
            import engel_ai_bounded_local_chat_smoke
            return engel_ai_bounded_local_chat_smoke.render_report()
        if route_id == ENGEL_FIRST_LOCAL_RESPONSE_SMOKE_ROUTE_ID:
            import engel_ai_first_local_response_smoke
            return engel_ai_first_local_response_smoke.render_report()
        if route_id == ENGEL_FIRST_LOCAL_RESPONSE_SMOKE_FIX_ROUTE_ID:
            import engel_ai_first_local_response_smoke_exit_fix
            return engel_ai_first_local_response_smoke_exit_fix.render_report()
        if route_id == ENGEL_OUTPUT_FILTER_TUNING_ROUTE_ID:
            import engel_ai_first_response_output_filter_tuning
            return engel_ai_first_response_output_filter_tuning.render_report()
        if route_id == ENGEL_LLAMA_SWAP_APPROVAL_ROUTE_ID:
            import engel_ai_llama_cpp_runtime_swap_approval
            return engel_ai_llama_cpp_runtime_swap_approval.render_report()
        if route_id == ENGEL_APPROVED_MEMORY_CONTEXT_BRIDGE_ROUTE_ID:
            import engel_ai_local_approved_memory_context_preview
            return engel_ai_local_approved_memory_context_preview.render_bridge_report()
        if route_id == ENGEL_APPROVED_MEMORY_READBACK_BRIDGE_ROUTE_ID:
            import engel_ai_local_approved_memory_readback
            return engel_ai_local_approved_memory_readback.render_bridge_report()
        if route_id == ENGEL_LOCAL_CHAT_PROMPT_DRAFT_ROUTE_ID:
            import engel_ai_local_chat_prompt_draft
            return engel_ai_local_chat_prompt_draft.render_report()
        if route_id == ENGEL_LOCAL_CHAT_SESSION_DRAFT_ROUTE_ID:
            import engel_ai_local_chat_session_draft
            return engel_ai_local_chat_session_draft.render_report()
        if route_id == ENGEL_LOCAL_CHAT_MEMORY_REVIEW_BRIDGE_ROUTE_ID:
            import engel_ai_local_chat_session_memory_candidate_review_and_approved_write
            return engel_ai_local_chat_session_memory_candidate_review_and_approved_write.render_bridge_report()
        if route_id == ENGEL_LOCAL_CHAT_SESSION_REVIEW_BRIDGE_ROUTE_ID:
            import engel_ai_local_chat_session_review
            return engel_ai_local_chat_session_review.render_bridge_report()
        if route_id == ENGEL_LOCAL_OPEN_CHAT_BRIDGE_ROUTE_ID:
            import engel_ai_local_open_chat_supervised_run
            return engel_ai_local_open_chat_supervised_run.render_bridge_report()
        if route_id == ENGEL_LOCAL_OPEN_CHAT_BOUNDED_RUN_REQUEST_ROUTE_ID:
            import engel_ai_main_rust_local_chat_bridge
            return engel_ai_main_rust_local_chat_bridge.render_bounded_run_request_route_report()
        if route_id == ENGEL_LOCAL_OPEN_CHAT_BOUNDED_RUN_EXECUTION_ROUTE_ID:
            import engel_ai_main_rust_local_chat_bridge
            return engel_ai_main_rust_local_chat_bridge.render_bounded_run_execution_route_report()
        if route_id == ENGEL_PERSISTENT_CHAT_PLAN_BRIDGE_ROUTE_ID:
            import engel_ai_persistent_chat_supervised_runtime_plan
            return engel_ai_persistent_chat_supervised_runtime_plan.render_bridge_report()
        if route_id == ENGEL_PERSISTENT_CHAT_SESSION_STATUS_ROUTE_ID:
            import engel_ai_main_rust_local_chat_bridge
            return engel_ai_main_rust_local_chat_bridge.render_persistent_session_status_route_report()
        if route_id == ENGEL_PERSISTENT_CHAT_SESSION_START_ROUTE_ID:
            import engel_ai_main_rust_local_chat_bridge
            return engel_ai_main_rust_local_chat_bridge.render_persistent_session_start_route_report()
        if route_id == ENGEL_PERSISTENT_CHAT_SESSION_STOP_ROUTE_ID:
            import engel_ai_main_rust_local_chat_bridge
            return engel_ai_main_rust_local_chat_bridge.render_persistent_session_stop_route_report()
        if route_id == ENGEL_RUNTIME_CANDIDATE_ALT_ROUTE_ID:
            import engel_ai_runtime_candidate_alt_command_style
            return engel_ai_runtime_candidate_alt_command_style.render_report()
        if route_id == ENGEL_RUNTIME_CANDIDATE_FAILURE_ROUTE_ID:
            import engel_ai_runtime_candidate_failure_diagnosis
            return engel_ai_runtime_candidate_failure_diagnosis.render_report()
        if route_id == ENGEL_RUNTIME_CANDIDATE_VALIDATION_ROUTE_ID:
            import engel_ai_runtime_candidate_validation_replay
            return engel_ai_runtime_candidate_validation_replay.render_report()
        if route_id == ENGEL_LAN_PAIRING_STATUS2_ROUTE_ID:
            import engel_remote_worker_lan_pairing
            return engel_remote_worker_lan_pairing.render_status()
        if route_id == ENGEL_LAN_PAIRING_TOKEN2_ROUTE_ID:
            import engel_remote_worker_lan_pairing
            return engel_remote_worker_lan_pairing.render_token()
        if route_id == ENGEL_RESEARCH_OFFICE_QUEEN_LINKS_ROUTE_ID:
            import engel_research_office_data
            from pathlib import Path as _Path
            return engel_research_office_data.render_research_office_queen_links(str(_Path(__file__).resolve().parent))
        if route_id == ENGEL_RESEARCH_OFFICE_PERMISSIONS_ROUTE_ID:
            import engel_research_office_data
            from pathlib import Path as _Path
            return engel_research_office_data.render_research_office_permissions(str(_Path(__file__).resolve().parent))
        if route_id == ENGEL_CC_PRODUCT_CONTEXT_VIEW_ROUTE_ID:
            import engel_code_companion
            return engel_code_companion.render_product_context_view(payload or None)
        if route_id == ENGEL_CC_CONTEXTUAL_TALK_ROUTE_ID:
            import engel_code_companion_contextual_talk
            return engel_code_companion_contextual_talk.render_context_for_selected_product(payload or None)
        if route_id == ENGEL_EXTERNAL_MEMORY_ARCHIVE_SHELF_ROUTE_ID:
            import engel_external_memory_status
            return engel_external_memory_status.render_external_memory_archive_shelf(payload or "E")
        if route_id == ENGEL_ROUTE_EXPLORER_DETAILS_ROUTE_ID:
            import engel_route_explorer
            return engel_route_explorer.render_route_details(payload or "")
        if route_id == MINOR_TOOLS_LIST_ROUTE_ID:
            import engel_minor_tools_runner

            return engel_minor_tools_runner.render_minor_tools_list()
        if route_id == ENGEL_HUMANIZER_STATUS_ROUTE_ID:
            import engel_minor_tools_runner

            return engel_minor_tools_runner.render_humanizer_status()
        if route_id == ENGEL_NATIVE_AGENT_STATUS_ROUTE_ID:
            import engel_minor_tools_runner

            return engel_minor_tools_runner.render_native_agent_status()
        if route_id == ENGEL_IDE_STATUS_ROUTE_ID:
            import engel_minor_tools_runner

            return engel_minor_tools_runner.render_ide_status()
        if route_id == ENGEL_EVOLUTION_LAB_STATUS_ROUTE_ID:
            import engel_minor_tools_runner

            return engel_minor_tools_runner.render_evolution_lab_status()
        if route_id == ENGEL_KNOWLEDGE_GRAPH_STATUS_ROUTE_ID:
            import engel_minor_tools_runner

            return engel_minor_tools_runner.render_knowledge_graph_status()
        if route_id == ENGEL_EVOLUTION_ENGINE_STATUS_ROUTE_ID:
            import engel_minor_tools_runner

            return engel_minor_tools_runner.render_evolution_engine_status()
        if route_id == ENGEL_HUMANIZER_FEATURES_ROUTE_ID:
            import engel_minor_tools_runner

            return engel_minor_tools_runner.render_humanizer_features()
        if route_id == ENGEL_HUMANIZER_DOCS_ROUTE_ID:
            import engel_minor_tools_runner

            return engel_minor_tools_runner.render_humanizer_docs()
        if route_id == ENGEL_NATIVE_AGENT_FEATURES_ROUTE_ID:
            import engel_minor_tools_runner

            return engel_minor_tools_runner.render_native_agent_features()
        if route_id == ENGEL_NATIVE_AGENT_DOCS_ROUTE_ID:
            import engel_minor_tools_runner

            return engel_minor_tools_runner.render_native_agent_docs()
        if route_id == ENGEL_IDE_FEATURES_ROUTE_ID:
            import engel_minor_tools_runner

            return engel_minor_tools_runner.render_ide_features()
        if route_id == ENGEL_IDE_DOCS_ROUTE_ID:
            import engel_minor_tools_runner

            return engel_minor_tools_runner.render_ide_docs()
        if route_id == ENGEL_EVOLUTION_LAB_FEATURES_ROUTE_ID:
            import engel_minor_tools_runner

            return engel_minor_tools_runner.render_evolution_lab_features()
        if route_id == ENGEL_EVOLUTION_LAB_DOCS_ROUTE_ID:
            import engel_minor_tools_runner

            return engel_minor_tools_runner.render_evolution_lab_docs()
        if route_id == ENGEL_KNOWLEDGE_GRAPH_FEATURES_ROUTE_ID:
            import engel_minor_tools_runner

            return engel_minor_tools_runner.render_knowledge_graph_features()
        if route_id == ENGEL_KNOWLEDGE_GRAPH_DOCS_ROUTE_ID:
            import engel_minor_tools_runner

            return engel_minor_tools_runner.render_knowledge_graph_docs()
        if route_id == ENGEL_EVOLUTION_ENGINE_FEATURES_ROUTE_ID:
            import engel_minor_tools_runner

            return engel_minor_tools_runner.render_evolution_engine_features()
        if route_id == ENGEL_EVOLUTION_ENGINE_DOCS_ROUTE_ID:
            import engel_minor_tools_runner

            return engel_minor_tools_runner.render_evolution_engine_docs()
        if route_id == ENGEL_HUMANIZER_INVOKE_ROUTE_ID:
            import engel_minor_tools_runner

            return engel_minor_tools_runner.render_humanizer_invoke()
        if route_id == ENGEL_NATIVE_AGENT_LAUNCH_DASHBOARD_ROUTE_ID:
            import engel_minor_tools_runner

            return engel_minor_tools_runner.render_native_agent_launch_dashboard()
        if route_id == ENGEL_NATIVE_AGENT_LAUNCH_AGENT_ROUTE_ID:
            import engel_minor_tools_runner

            return engel_minor_tools_runner.render_native_agent_launch_agent()
        if route_id == ENGEL_IDE_INSTALL_TO_PROJECT_ROUTE_ID:
            import engel_minor_tools_runner

            return engel_minor_tools_runner.render_ide_install_to_project()
        if route_id == ENGEL_EVOLUTION_LAB_HELP_ROUTE_ID:
            import engel_minor_tools_runner

            return engel_minor_tools_runner.render_evolution_lab_help()
        if route_id == ENGEL_EVOLUTION_LAB_RUN_EXAMPLE_ROUTE_ID:
            import engel_minor_tools_runner

            return engel_minor_tools_runner.render_evolution_lab_run_example()
        if route_id == ENGEL_KNOWLEDGE_GRAPH_HELP_ROUTE_ID:
            import engel_minor_tools_runner

            return engel_minor_tools_runner.render_knowledge_graph_help()
        if route_id == ENGEL_KNOWLEDGE_GRAPH_BUILD_ROUTE_ID:
            import engel_minor_tools_runner

            return engel_minor_tools_runner.render_knowledge_graph_build()
        if route_id == ENGEL_EVOLUTION_ENGINE_HELP_ROUTE_ID:
            import engel_minor_tools_runner

            return engel_minor_tools_runner.render_evolution_engine_help()
        if route_id == ENGEL_EVOLUTION_ENGINE_RUN_ROUTE_ID:
            import engel_minor_tools_runner

            return engel_minor_tools_runner.render_evolution_engine_run()
        if route_id == ENGEL_AI_CONNECTORS_STATUS_ROUTE_ID:
            import engel_ai_connector_hub

            return engel_ai_connector_hub.render_ai_connector_status(payload)
        if route_id == ENGEL_AI_CONNECTORS_ADAPTERS_ROUTE_ID:
            import engel_ai_connector_hub

            return engel_ai_connector_hub.render_ai_connector_adapters(payload)
        if route_id == ENGEL_AI_CONNECTORS_BLUEPRINT_ROUTE_ID:
            import engel_ai_connector_hub

            return engel_ai_connector_hub.render_ai_connector_blueprint(payload)
        if route_id == ENGEL_AI_CONNECTORS_RULES_ROUTE_ID:
            import engel_ai_connector_hub

            return engel_ai_connector_hub.render_ai_connector_rules(payload)
        if route_id == ENGEL_AI_CONNECTORS_ZIP_AUDIT_ROUTE_ID:
            import engel_ai_connector_hub

            return engel_ai_connector_hub.render_ai_connector_zip_audit(payload)
        if route_id == ENGEL_ACCOUNT_CONNECTOR_STATUS_ROUTE_ID:
            import engel_account_connector

            return engel_account_connector.render_account_connector_status(payload)
        if route_id == ENGEL_ACCOUNT_CONNECTOR_PROVIDERS_ROUTE_ID:
            import engel_account_connector

            return engel_account_connector.render_account_connector_providers(payload)
        if route_id == ENGEL_ACCOUNT_CONNECTOR_SETUP_ROUTE_ID:
            import engel_account_connector

            return engel_account_connector.render_account_connector_setup(payload)
        if route_id == ENGEL_ACCOUNT_CONNECTOR_SAFETY_ROUTE_ID:
            import engel_account_connector

            return engel_account_connector.render_account_connector_safety(payload)
        if route_id == ENGEL_ROUTE_EXPLORER_ROUTE_ID:
            import engel_route_explorer

            return engel_route_explorer.render_route_explorer(payload)
        if route_id == ENGEL_ROUTE_SEARCH_ROUTE_ID:
            import engel_route_explorer
            return engel_route_explorer.render_route_search(str(payload or ""))
        if route_id == ENGEL_CAPABILITIES_LIST_ROUTE_ID:
            import engel_minor_tools_runner

            return engel_minor_tools_runner.render_capabilities_list()
        # ---- Stage 4: native top-level Engel = hermes-agent dispatch ----
        if route_id == ENGEL_IDENTITY_ROUTE_ID:
            import engel_engel_agent_runner

            return engel_engel_agent_runner.render_engel_identity()
        if route_id == ENGEL_NATIVE_GATEWAY_START_ROUTE_ID:
            import engel_engel_agent_runner

            return engel_engel_agent_runner.render_engel_agent_gateway_start()
        if route_id == ENGEL_NATIVE_GATEWAY_STOP_ROUTE_ID:
            import engel_engel_agent_runner

            return engel_engel_agent_runner.render_engel_agent_gateway_stop()
        if route_id == ENGEL_NATIVE_GATEWAY_STATUS_ROUTE_ID:
            import engel_engel_agent_runner

            return engel_engel_agent_runner.render_engel_agent_gateway_status()
        if route_id == ENGEL_NATIVE_CRON_LIST_ROUTE_ID:
            import engel_engel_agent_runner

            return engel_engel_agent_runner.render_engel_agent_cron_list()
        if route_id == ENGEL_NATIVE_CRON_STATUS_ROUTE_ID:
            import engel_engel_agent_runner

            return engel_engel_agent_runner.render_engel_agent_cron_status()
        if route_id == ENGEL_NATIVE_MEMORY_STATUS_ROUTE_ID:
            import engel_engel_agent_runner

            return engel_engel_agent_runner.render_engel_agent_memory_status()
        if route_id == ENGEL_NATIVE_SKILLS_LIST_ROUTE_ID:
            import engel_engel_agent_runner

            return engel_engel_agent_runner.render_engel_agent_skills_list()
        if route_id == ENGEL_SAVED_SKILLS_LIST_ROUTE_ID:
            import engel_saved_skills_list

            return engel_saved_skills_list.render_saved_skills_list()
        if route_id == ENGEL_FEATURE_MAP_ROUTE_ID:
            import engel_feature_map

            return engel_feature_map.render_feature_map(payload)
        if route_id == ENGEL_FEATURE_MAP_DRAFT_PR_ROUTE_ID:
            import engel_feature_map

            return engel_feature_map.render_open_draft_pr(payload)
        if route_id == ENGEL_NATIVE_SESSIONS_LIST_ROUTE_ID:
            import engel_engel_agent_runner

            return engel_engel_agent_runner.render_engel_agent_sessions_list()
        if route_id == ENGEL_NATIVE_SESSIONS_STATS_ROUTE_ID:
            import engel_engel_agent_runner

            return engel_engel_agent_runner.render_engel_agent_sessions_stats()
        if route_id == ENGEL_NATIVE_PLUGINS_LIST_ROUTE_ID:
            import engel_engel_agent_runner

            return engel_engel_agent_runner.render_engel_agent_plugins_list()
        if route_id == ENGEL_NATIVE_TOOLSETS_ROUTE_ID:
            import engel_engel_agent_runner

            return engel_engel_agent_runner.render_engel_agent_toolsets()
        if route_id == ENGEL_NATIVE_DOCTOR_ROUTE_ID:
            import engel_engel_agent_runner

            return engel_engel_agent_runner.render_engel_agent_doctor()
        if route_id == ENGEL_NATIVE_TOP_STATUS_ROUTE_ID:
            import engel_engel_agent_runner

            return engel_engel_agent_runner.render_engel_agent_top_status()
        if route_id == ENGEL_NATIVE_VERSION_ROUTE_ID:
            import engel_engel_agent_runner

            return engel_engel_agent_runner.render_engel_agent_version()
        if route_id == ENGEL_NATIVE_INVOKE_ROUTE_ID:
            import engel_engel_agent_runner

            return engel_engel_agent_runner.render_engel_agent_invocation(payload)
        if route_id == ENGEL_NATIVE_RUNTIME_ROUTE_ID:
            import engel_engel_agent_runner

            return engel_engel_agent_runner.render_engel_native_runtime()
        # ── Wave 2 new tools ────────────────────────────────────────────────
        if route_id == ENGEL_NEW_TOOLS_LIST_ROUTE_ID:
            import engel_new_tools_runner
            return engel_new_tools_runner.render_new_tools_list()
        if route_id == ENGEL_CLI_ANYTHING_STATUS_ROUTE_ID:
            import engel_new_tools_runner
            return engel_new_tools_runner.render_cli_anything_status()
        if route_id == ENGEL_CLI_ANYTHING_FEATURES_ROUTE_ID:
            import engel_new_tools_runner
            return engel_new_tools_runner.render_cli_anything_features()
        if route_id == ENGEL_CLI_ANYTHING_DOCS_ROUTE_ID:
            import engel_new_tools_runner
            return engel_new_tools_runner.render_cli_anything_docs()
        if route_id == ENGEL_GIT_NEXUS_STATUS_ROUTE_ID:
            import engel_new_tools_runner
            return engel_new_tools_runner.render_git_nexus_status()
        if route_id == ENGEL_GIT_NEXUS_FEATURES_ROUTE_ID:
            import engel_new_tools_runner
            return engel_new_tools_runner.render_git_nexus_features()
        if route_id == ENGEL_GIT_NEXUS_DOCS_ROUTE_ID:
            import engel_new_tools_runner
            return engel_new_tools_runner.render_git_nexus_docs()
        if route_id == ENGEL_OCTOGENT_STATUS_ROUTE_ID:
            import engel_new_tools_runner
            return engel_new_tools_runner.render_octogent_status()
        if route_id == ENGEL_OCTOGENT_FEATURES_ROUTE_ID:
            import engel_new_tools_runner
            return engel_new_tools_runner.render_octogent_features()
        if route_id == ENGEL_OCTOGENT_DOCS_ROUTE_ID:
            import engel_new_tools_runner
            return engel_new_tools_runner.render_octogent_docs()
        if route_id == ENGEL_OPEN_AGENTS_STATUS_ROUTE_ID:
            import engel_new_tools_runner
            return engel_new_tools_runner.render_open_agents_status()
        if route_id == ENGEL_OPEN_AGENTS_FEATURES_ROUTE_ID:
            import engel_new_tools_runner
            return engel_new_tools_runner.render_open_agents_features()
        if route_id == ENGEL_OPEN_AGENTS_DOCS_ROUTE_ID:
            import engel_new_tools_runner
            return engel_new_tools_runner.render_open_agents_docs()
        if route_id == ENGEL_AIRLLM_STATUS_ROUTE_ID:
            import engel_new_tools_runner
            return engel_new_tools_runner.render_airllm_status()
        if route_id == ENGEL_AIRLLM_FEATURES_ROUTE_ID:
            import engel_new_tools_runner
            return engel_new_tools_runner.render_airllm_features()
        if route_id == ENGEL_AIRLLM_DOCS_ROUTE_ID:
            import engel_new_tools_runner
            return engel_new_tools_runner.render_airllm_docs()
        if route_id == ENGEL_JARVIS_STATUS_ROUTE_ID:
            import engel_new_tools_runner
            return engel_new_tools_runner.render_jarvis_status()
        if route_id == ENGEL_JARVIS_FEATURES_ROUTE_ID:
            import engel_new_tools_runner
            return engel_new_tools_runner.render_jarvis_features()
        if route_id == ENGEL_JARVIS_DOCS_ROUTE_ID:
            import engel_new_tools_runner
            return engel_new_tools_runner.render_jarvis_docs()
        if route_id == ENGEL_CHAT_UI_STATUS_ROUTE_ID:
            import engel_new_tools_runner
            return engel_new_tools_runner.render_chat_ui_status()
        if route_id == ENGEL_CHAT_UI_FEATURES_ROUTE_ID:
            import engel_new_tools_runner
            return engel_new_tools_runner.render_chat_ui_features()
        if route_id == ENGEL_CHAT_UI_DOCS_ROUTE_ID:
            import engel_new_tools_runner
            return engel_new_tools_runner.render_chat_ui_docs()
        if route_id == ENGEL_AI_GALLERY_STATUS_ROUTE_ID:
            import engel_new_tools_runner
            return engel_new_tools_runner.render_ai_gallery_status()
        if route_id == ENGEL_AI_GALLERY_FEATURES_ROUTE_ID:
            import engel_new_tools_runner
            return engel_new_tools_runner.render_ai_gallery_features()
        if route_id == ENGEL_AI_GALLERY_DOCS_ROUTE_ID:
            import engel_new_tools_runner
            return engel_new_tools_runner.render_ai_gallery_docs()
        if route_id == ENGEL_CLUSTER_STATUS_ROUTE_ID:
            import engel_new_tools_runner
            return engel_new_tools_runner.render_cluster_status()
        if route_id == ENGEL_CLUSTER_FEATURES_ROUTE_ID:
            import engel_new_tools_runner
            return engel_new_tools_runner.render_cluster_features()
        if route_id == ENGEL_CLUSTER_DOCS_ROUTE_ID:
            import engel_new_tools_runner
            return engel_new_tools_runner.render_cluster_docs()
        if route_id == ENGEL_KNOWLEDGE_GRAPH_V2_STATUS_ROUTE_ID:
            import engel_new_tools_runner
            return engel_new_tools_runner.render_knowledge_graph_v2_status()
        if route_id == ENGEL_KNOWLEDGE_GRAPH_V2_FEATURES_ROUTE_ID:
            import engel_new_tools_runner
            return engel_new_tools_runner.render_knowledge_graph_v2_features()
        if route_id == ENGEL_KNOWLEDGE_GRAPH_V2_DOCS_ROUTE_ID:
            import engel_new_tools_runner
            return engel_new_tools_runner.render_knowledge_graph_v2_docs()
        # ── Wave 2 extended ──────────────────────────────────────────────────
        if route_id == ENGEL_GIT_NEXUS_PLUGINS_ROUTE_ID:
            import engel_new_tools_runner
            return engel_new_tools_runner.render_git_nexus_plugins()
        if route_id == ENGEL_GIT_NEXUS_INSTALL_ROUTE_ID:
            import engel_new_tools_runner
            return engel_new_tools_runner.render_git_nexus_install()
        if route_id == ENGEL_GIT_NEXUS_ANALYZE_ROUTE_ID:
            import engel_new_tools_runner
            return engel_new_tools_runner.render_git_nexus_analyze()
        if route_id == ENGEL_CLI_ANYTHING_PLUGINS_ROUTE_ID:
            import engel_new_tools_runner
            return engel_new_tools_runner.render_cli_anything_plugins()
        if route_id == ENGEL_CLI_ANYTHING_SEARCH_ROUTE_ID:
            import engel_new_tools_runner
            return engel_new_tools_runner.render_cli_anything_search()
        if route_id == ENGEL_CLI_ANYTHING_INSTALL_ROUTE_ID:
            import engel_new_tools_runner
            return engel_new_tools_runner.render_cli_anything_install()
        if route_id == ENGEL_OPEN_AGENTS_PACKAGES_ROUTE_ID:
            import engel_new_tools_runner
            return engel_new_tools_runner.render_open_agents_packages()
        if route_id == ENGEL_OPEN_AGENTS_SKILLS_ROUTE_ID:
            import engel_new_tools_runner
            return engel_new_tools_runner.render_open_agents_skills()
        if route_id == ENGEL_OPEN_AGENTS_INSTALL_ROUTE_ID:
            import engel_new_tools_runner
            return engel_new_tools_runner.render_open_agents_install()
        if route_id == ENGEL_JARVIS_INSTALL_ROUTE_ID:
            import engel_new_tools_runner
            return engel_new_tools_runner.render_jarvis_install()
        if route_id == ENGEL_JARVIS_START_ROUTE_ID:
            import engel_new_tools_runner
            return engel_new_tools_runner.render_jarvis_start()
        if route_id == ENGEL_JARVIS_SKILLS_ROUTE_ID:
            import engel_new_tools_runner
            return engel_new_tools_runner.render_jarvis_skills()
        if route_id == ENGEL_CHAT_UI_INSTALL_ROUTE_ID:
            import engel_new_tools_runner
            return engel_new_tools_runner.render_chat_ui_install()
        if route_id == ENGEL_CHAT_UI_START_ROUTE_ID:
            import engel_new_tools_runner
            return engel_new_tools_runner.render_chat_ui_start()
        if route_id == ENGEL_CHAT_UI_CONFIG_ROUTE_ID:
            import engel_new_tools_runner
            return engel_new_tools_runner.render_chat_ui_config()
        if route_id == ENGEL_AI_GALLERY_DEMOS_ROUTE_ID:
            import engel_new_tools_runner
            return engel_new_tools_runner.render_ai_gallery_demos()
        if route_id == ENGEL_AI_GALLERY_INSTALL_ROUTE_ID:
            import engel_new_tools_runner
            return engel_new_tools_runner.render_ai_gallery_install()
        if route_id == ENGEL_AI_GALLERY_REQUIREMENTS_ROUTE_ID:
            import engel_new_tools_runner
            return engel_new_tools_runner.render_ai_gallery_requirements()
        if route_id == ENGEL_CLUSTER_NODES_ROUTE_ID:
            import engel_new_tools_runner
            return engel_new_tools_runner.render_cluster_nodes()
        if route_id == ENGEL_CLUSTER_INSTALL_ROUTE_ID:
            import engel_new_tools_runner
            return engel_new_tools_runner.render_cluster_install()
        if route_id == ENGEL_CLUSTER_EXAMPLES_ROUTE_ID:
            import engel_new_tools_runner
            return engel_new_tools_runner.render_cluster_examples()
        # ── Agent Meeting Room ───────────────────────────────────────────────
        if route_id == ENGEL_MEETING_ROOM_STATUS_ROUTE_ID:
            import engel_agent_meetingroom
            return engel_agent_meetingroom.render_meeting_room_status()
        if route_id == ENGEL_MEETING_ROOM_AGENDA_ROUTE_ID:
            import engel_agent_meetingroom
            return engel_agent_meetingroom.render_meeting_room_agenda()
        if route_id == ENGEL_MEETING_ROOM_TRANSCRIPT_ROUTE_ID:
            import engel_agent_meetingroom
            return engel_agent_meetingroom.render_meeting_room_transcript()
        if route_id == ENGEL_MEETING_ROOM_WHITEBOARD_ROUTE_ID:
            import engel_agent_meetingroom
            return engel_agent_meetingroom.render_meeting_room_whiteboard()
        if route_id == ENGEL_MEETING_ROOM_AGENTS_ROUTE_ID:
            import engel_agent_meetingroom
            return engel_agent_meetingroom.render_meeting_room_agents()
        if route_id == ENGEL_MEETING_ROOM_OPEN_ROUTE_ID:
            import engel_agent_meetingroom
            return engel_agent_meetingroom.render_meeting_room_open(payload or "")
        if route_id == ENGEL_MEETING_ROOM_CLOSE_ROUTE_ID:
            import engel_agent_meetingroom
            return engel_agent_meetingroom.render_meeting_room_close()
        if route_id == ENGEL_MEETING_ROOM_ADD_NOTE_ROUTE_ID:
            import engel_agent_meetingroom
            return engel_agent_meetingroom.render_meeting_room_add_note(payload or "")
        # ── Wave 3 — gstack + LFM2 ──────────────────────────────────────────
        if route_id == ENGEL_WAVE3_LIST_ROUTE_ID:
            import engel_wave3_runner
            return engel_wave3_runner.render_wave3_list()
        if route_id == ENGEL_GSTACK_STATUS_ROUTE_ID:
            import engel_wave3_runner
            return engel_wave3_runner.render_gstack_status()
        if route_id == ENGEL_GSTACK_FEATURES_ROUTE_ID:
            import engel_wave3_runner
            return engel_wave3_runner.render_gstack_features()
        if route_id == ENGEL_GSTACK_DOCS_ROUTE_ID:
            import engel_wave3_runner
            return engel_wave3_runner.render_gstack_docs()
        if route_id == ENGEL_GSTACK_INSTALL_ROUTE_ID:
            import engel_wave3_runner
            return engel_wave3_runner.render_gstack_install()
        if route_id == ENGEL_GSTACK_SKILLS_ROUTE_ID:
            import engel_wave3_runner
            return engel_wave3_runner.render_gstack_skills()
        if route_id == ENGEL_LFM2_STATUS_ROUTE_ID:
            import engel_wave3_runner
            return engel_wave3_runner.render_lfm2_status()
        if route_id == ENGEL_LFM2_FEATURES_ROUTE_ID:
            import engel_wave3_runner
            return engel_wave3_runner.render_lfm2_features()
        if route_id == ENGEL_LFM2_DOCS_ROUTE_ID:
            import engel_wave3_runner
            return engel_wave3_runner.render_lfm2_docs()
        if route_id == ENGEL_LFM2_INSTALL_ROUTE_ID:
            import engel_wave3_runner
            return engel_wave3_runner.render_lfm2_install()
        if route_id == ENGEL_LFM2_EXAMPLE_ROUTE_ID:
            import engel_wave3_runner
            return engel_wave3_runner.render_lfm2_example()
        if route_id == ENGEL_LFM2_CODE_REVIEW_STATUS_ROUTE_ID:
            import engel_wave3_runner
            return engel_wave3_runner.render_lfm2_code_review_status()
        if route_id == ENGEL_LFM2_CODE_REVIEW_FEATURES_ROUTE_ID:
            import engel_wave3_runner
            return engel_wave3_runner.render_lfm2_code_review_features()
        if route_id == ENGEL_LFM2_CODE_REVIEW_DOCS_ROUTE_ID:
            import engel_wave3_runner
            return engel_wave3_runner.render_lfm2_code_review_docs()
        if route_id == ENGEL_LFM2_CODE_REVIEW_INSTALL_ROUTE_ID:
            import engel_wave3_runner
            return engel_wave3_runner.render_lfm2_code_review_install()
        if route_id == ENGEL_LFM2_CODE_REVIEW_APPS_ROUTE_ID:
            import engel_wave3_runner
            return engel_wave3_runner.render_lfm2_code_review_apps()
        if route_id == ENGEL_LFM2_MOBILE_STATUS_ROUTE_ID:
            import engel_wave3_runner
            return engel_wave3_runner.render_lfm2_mobile_status()
        if route_id == ENGEL_LFM2_MOBILE_FEATURES_ROUTE_ID:
            import engel_wave3_runner
            return engel_wave3_runner.render_lfm2_mobile_features()
        if route_id == ENGEL_LFM2_MOBILE_DOCS_ROUTE_ID:
            import engel_wave3_runner
            return engel_wave3_runner.render_lfm2_mobile_docs()
        if route_id == ENGEL_LFM2_MOBILE_INSTALL_ROUTE_ID:
            import engel_wave3_runner
            return engel_wave3_runner.render_lfm2_mobile_install()
        if route_id == ENGEL_LFM2_MOBILE_INFERENCE_ROUTE_ID:
            import engel_wave3_runner
            return engel_wave3_runner.render_lfm2_mobile_inference()
        if route_id == ENGEL_LFM2_VISION_STATUS_ROUTE_ID:
            import engel_wave3_runner
            return engel_wave3_runner.render_lfm2_vision_status()
        if route_id == ENGEL_LFM2_VISION_FEATURES_ROUTE_ID:
            import engel_wave3_runner
            return engel_wave3_runner.render_lfm2_vision_features()
        if route_id == ENGEL_LFM2_VISION_DOCS_ROUTE_ID:
            import engel_wave3_runner
            return engel_wave3_runner.render_lfm2_vision_docs()
        if route_id == ENGEL_LFM2_VISION_INSTALL_ROUTE_ID:
            import engel_wave3_runner
            return engel_wave3_runner.render_lfm2_vision_install()
        if route_id == ENGEL_LFM2_VISION_START_ROUTE_ID:
            import engel_wave3_runner
            return engel_wave3_runner.render_lfm2_vision_start()
        # ── AirLLM local inference ───────────────────────────────────────────
        if route_id == ENGEL_AIRLLM_BRIDGE_STATUS_ROUTE_ID:
            import engel_airllm_bridge
            return engel_airllm_bridge.render_airllm_bridge_status()
        if route_id == ENGEL_AIRLLM_LOAD_ROUTE_ID:
            import engel_airllm_bridge
            return engel_airllm_bridge.render_airllm_load(str(payload or ""))
        if route_id == ENGEL_AIRLLM_GENERATE_ROUTE_ID:
            import engel_airllm_bridge
            return engel_airllm_bridge.render_airllm_generate(str(payload or ""))
        if route_id == ENGEL_AIRLLM_UNLOAD_ROUTE_ID:
            import engel_airllm_bridge
            return engel_airllm_bridge.render_airllm_unload()
        # ── Overnight runner ─────────────────────────────────────────────────
        if route_id == ENGEL_OVERNIGHT_STATUS_ROUTE_ID:
            import engel_overnight_status
            return engel_overnight_status.render_overnight_status()
        # ── Talk-to-Code ─────────────────────────────────────────────────────
        if route_id == ENGEL_TALK_TO_CODE_LIST_ROUTE_ID:
            import engel_talk_to_code
            return engel_talk_to_code.list_talkable_modules()
        if route_id == ENGEL_TALK_TO_CODE_EXPLAIN_ROUTE_ID:
            import engel_talk_to_code
            return engel_talk_to_code.explain_module(str(payload or ""))
        # ── Local Model Manager ──────────────────────────────────────────────
        if route_id == ENGEL_MODELS_LIST_ROUTE_ID:
            import engel_local_model_manager
            return engel_local_model_manager.render_models_list()
        if route_id == ENGEL_MODELS_STATUS_ROUTE_ID:
            import engel_local_model_manager
            return engel_local_model_manager.render_models_status()
        if route_id == ENGEL_MODELS_LOAD_ROUTE_ID:
            import engel_local_model_manager
            return engel_local_model_manager.render_models_load(str(payload or ""))
        if route_id == ENGEL_MODELS_UNLOAD_ROUTE_ID:
            import engel_local_model_manager
            return engel_local_model_manager.render_models_unload()
        if route_id == ENGEL_MODELS_INFO_ROUTE_ID:
            import engel_local_model_manager
            return engel_local_model_manager.render_models_info(str(payload or ""))
        # ── Octogent swarm UI ────────────────────────────────────────────────
        if route_id == ENGEL_OCTOGENT_SWARM_STATUS_ROUTE_ID:
            import engel_octogent_runner
            return engel_octogent_runner.render_octogent_status()
        if route_id == ENGEL_OCTOGENT_INSTALL_ROUTE_ID:
            import engel_octogent_runner
            return engel_octogent_runner.render_octogent_install()
        if route_id == ENGEL_OCTOGENT_START_ROUTE_ID:
            import engel_octogent_runner
            return engel_octogent_runner.render_octogent_start()
        if route_id == ENGEL_OCTOGENT_STOP_ROUTE_ID:
            import engel_octogent_runner
            return engel_octogent_runner.render_octogent_stop()
        # ── Research Brain + Overnight Loop ──────────────────────────────────
        if route_id == ENGEL_RESEARCH_OVERVIEW_ROUTE_ID:
            import engel_research_status
            return engel_research_status.render_research_overview()
        if route_id == ENGEL_RESEARCH_BRAIN_STATUS_ROUTE_ID:
            import engel_research_status
            return engel_research_status.render_research_brain_status()
        if route_id == ENGEL_RESEARCH_QUEUE_ROUTE_ID:
            import engel_research_status
            return engel_research_status.render_research_queue_status()
        if route_id == ENGEL_RESEARCH_NEXT_TOPIC_ROUTE_ID:
            import engel_research_status
            return engel_research_status.render_research_next_best_topic()
        if route_id == ENGEL_RESEARCH_DIGEST_ROUTE_ID:
            import engel_research_status
            return engel_research_status.render_research_digest_latest()
        if route_id == ENGEL_RESEARCH_TOGGLE_ROUTE_ID:
            import engel_research_status
            return engel_research_status.render_research_toggle_status()
        if route_id == ENGEL_HIVE_MIND_STATUS_ROUTE_ID:
            import engel_research_status
            return engel_research_status.render_hive_mind_status()
        if route_id == ENGEL_WORKER_ANTS_STATUS_ROUTE_ID:
            import engel_research_status
            return engel_research_status.render_worker_ants_status()
        if route_id == ENGEL_COLONY_STATUS_ROUTE_ID:
            import engel_research_status
            return engel_research_status.render_colony_status()
        if route_id == ENGEL_COLONY_SAFETY_ROUTE_ID:
            import engel_research_status
            return engel_research_status.render_colony_safety_status()
        if route_id == ENGEL_SWARM_TRAILS_ROUTE_ID:
            import engel_research_status
            return engel_research_status.render_swarm_trails_status()
        if route_id == ENGEL_LEARNING_PROPOSALS_ROUTE_ID:
            import engel_research_status
            return engel_research_status.render_learning_proposals_status()
        if route_id == ENGEL_LESSON_CANDIDATES_ROUTE_ID:
            import engel_research_status
            return engel_research_status.render_lesson_candidates_status()
        if route_id == ENGEL_OVERNIGHT_LOOP_STATUS_ROUTE_ID:
            import engel_research_status
            return engel_research_status.render_overnight_loop_status()
        if route_id == ENGEL_GROWTH_DASHBOARD_ROUTE_ID:
            import engel_ai_growth_dashboard
            return engel_ai_growth_dashboard.render_dashboard()
        if route_id == ENGEL_OVERNIGHT_LOOP_CLEANUP_ROUTE_ID:
            import engel_research_status
            return engel_research_status.render_overnight_loop_cleanup()
        if route_id == ENGEL_KG_V2_STATUS_ROUTE_ID:
            import engel_knowledge_graph_v2_status
            return engel_knowledge_graph_v2_status.render_kg_status()
        if route_id == ENGEL_KG_V2_GLOBAL_ROUTE_ID:
            import engel_knowledge_graph_v2_status
            return engel_knowledge_graph_v2_status.render_kg_global_graph()
        if route_id == ENGEL_KG_V2_SCAN_ROUTE_ID:
            import engel_knowledge_graph_v2_status
            return engel_knowledge_graph_v2_status.render_kg_scan_workspace()
        if route_id == ENGEL_KG_V2_HELP_ROUTE_ID:
            import engel_knowledge_graph_v2_status
            return engel_knowledge_graph_v2_status.render_kg_help()
        if route_id == ENGEL_KG_V2_INSTALL_ROUTE_ID:
            import engel_knowledge_graph_v2_status
            return engel_knowledge_graph_v2_status.render_kg_install()
        if route_id == ENGEL_KG_V2_BUILD_CORE_ROUTE_ID:
            import engel_knowledge_graph_v2_status
            return engel_knowledge_graph_v2_status.render_kg_build_core()
        if route_id == ENGEL_KG_V2_ANALYZE_CORE_ROUTE_ID:
            import engel_knowledge_graph_v2_status
            return engel_knowledge_graph_v2_status.render_kg_analyze_core()
        if route_id == ENGEL_KG_V2_SEARCH_ROUTE_ID:
            import engel_knowledge_graph_v2_status
            return engel_knowledge_graph_v2_status.render_kg_search(str(payload or ""))
        if route_id == ENGEL_KG_V2_NEIGHBORS_ROUTE_ID:
            import engel_knowledge_graph_v2_status
            return engel_knowledge_graph_v2_status.render_kg_neighbors(str(payload or ""))
        if route_id == ENGEL_KG_V2_COMMUNITIES_ROUTE_ID:
            import engel_knowledge_graph_v2_status
            return engel_knowledge_graph_v2_status.render_kg_communities(str(payload or ""))
        if route_id == ENGEL_VERIFY_LOCAL_LLM_GROWTH_ROUTE_ID:
            import engel_verify_status
            return engel_verify_status.render_verify_local_llm_growth()
        if route_id == ENGEL_VERIFY_PROMOTION_ROUTE_ID:
            import engel_verify_status
            return engel_verify_status.render_verify_promotion()
        if route_id == ENGEL_VERIFY_BRAIN_PROVIDER_ROUTE_ID:
            import engel_verify_status
            return engel_verify_status.render_verify_brain_provider()
        if route_id == ENGEL_VERIFY_LLM_TEACHING_ROUTE_ID:
            import engel_verify_status
            return engel_verify_status.render_verify_llm_teaching()
        if route_id == ENGEL_VERIFY_STYLE_GUIDE_ROUTE_ID:
            import engel_verify_status
            return engel_verify_status.render_verify_style_guide()
        if route_id == ENGEL_VERIFY_ALL_ROUTE_ID:
            import engel_verify_status
            return engel_verify_status.render_verify_all()
        if route_id == ENGEL_EXT_MEM_STATUS_ROUTE_ID:
            import engel_external_memory_status
            return engel_external_memory_status.render_external_memory_status()
        if route_id == ENGEL_EXT_MEM_MODELS_ROUTE_ID:
            import engel_external_memory_status
            return engel_external_memory_status.render_external_memory_models()
        if route_id == ENGEL_EXT_MEM_RUNTIMES_ROUTE_ID:
            import engel_external_memory_status
            return engel_external_memory_status.render_external_memory_runtimes()
        if route_id == ENGEL_VAULT_MIGRATION_STATUS_ROUTE_ID:
            import engel_vault_paths
            return engel_vault_paths.render_vault_migration_status()
        if route_id == ENGEL_VAULT_MIGRATION_PLAN_ROUTE_ID:
            import engel_vault_paths
            return engel_vault_paths.render_vault_migration_plan()
        if route_id == ENGEL_MAIN_SERVER_MERGE_STATUS_ROUTE_ID:
            import engel_main_server_merge
            return engel_main_server_merge.render_server_merge_status()
        if route_id == ENGEL_EXT_MEM_E_DRIVE_ROUTE_ID:
            import engel_external_memory_status
            return engel_external_memory_status.render_e_drive_status()
        if route_id == ENGEL_EXT_MEM_F_DRIVE_ROUTE_ID:
            import engel_external_memory_status
            return engel_external_memory_status.render_f_drive_status()
        if route_id == ENGEL_EXT_MEM_G_DRIVE_ROUTE_ID:
            import engel_external_memory_status
            return engel_external_memory_status.render_g_drive_status()
        if route_id == ENGEL_LLAMA_CLI_STATUS_ROUTE_ID:
            import engel_llama_cli_runner
            return engel_llama_cli_runner.render_llama_cli_status()
        if route_id == ENGEL_LLAMA_CLI_PREFLIGHT_ROUTE_ID:
            import engel_llama_cli_runner
            return engel_llama_cli_runner.render_llama_cli_preflight()
        if route_id == ENGEL_LLAMA_CLI_RUN_ROUTE_ID:
            import engel_llama_cli_runner
            return engel_llama_cli_runner.render_llama_cli_run(payload)
        if route_id == ENGEL_LLAMA_CLI_BENCHMARK_ROUTE_ID:
            import engel_llama_cli_runner
            return engel_llama_cli_runner.render_llama_cli_benchmark()
        if route_id == ENGEL_LLAMA_CLI_RUN_SLUG_ROUTE_ID:
            import engel_llama_cli_runner
            return engel_llama_cli_runner.render_llama_cli_run_slug(payload)
        if route_id == ENGEL_LLAMA_CLI_GPU_BENCHMARK_ROUTE_ID:
            import engel_llama_cli_runner
            return engel_llama_cli_runner.render_llama_cli_gpu_benchmark()
        if route_id == ENGEL_LLAMA_CLI_GPU_INFO_ROUTE_ID:
            import engel_llama_cli_runner
            return engel_llama_cli_runner.render_llama_cli_gpu_info()
        if route_id == ENGEL_LLAMA_CLI_COMPARE_ROUTE_ID:
            import engel_llama_cli_runner
            return engel_llama_cli_runner.render_llama_cli_compare(payload)
        if route_id == ENGEL_LLAMA_CLI_EXPLAIN_ROUTE_ID:
            import engel_llama_cli_runner
            return engel_llama_cli_runner.render_llama_cli_explain(payload)
        if route_id == ENGEL_LOCAL_LLM_DASHBOARD_ROUTE_ID:
            import engel_local_llm_dashboard
            return engel_local_llm_dashboard.render_local_llm_dashboard()
        if route_id == ENGEL_LOCAL_LLM_DOCTOR_ROUTE_ID:
            import engel_local_llm_doctor
            return engel_local_llm_doctor.render_local_llm_doctor(payload)
        if route_id == ENGEL_DARWIN_STATUS_ROUTE_ID:
            import engel_darwin_status
            return engel_darwin_status.render_darwin_status()
        if route_id == ENGEL_DARWIN_PROBLEMS_ROUTE_ID:
            import engel_darwin_status
            return engel_darwin_status.render_darwin_problems()
        if route_id == ENGEL_DARWIN_FRAMEWORK_ROUTE_ID:
            import engel_darwin_status
            return engel_darwin_status.render_darwin_framework_info()
        if route_id == ENGEL_DARWIN_LOG_ROUTE_ID:
            import engel_darwin_status
            return engel_darwin_status.render_darwin_learning_log()
        if route_id == ENGEL_DARWIN_LOCAL_STATUS_ROUTE_ID:
            import engel_darwin_local_runner
            return engel_darwin_local_runner.render_darwin_local_parrot_status()
        if route_id == ENGEL_DARWIN_LOCAL_PARROT_RUN_ROUTE_ID:
            import engel_darwin_local_runner
            return engel_darwin_local_runner.render_darwin_local_parrot_run(payload)
        if route_id == ENGEL_CODE_LIST_LANGUAGES_ROUTE_ID:
            import engel_local_multi_model_code
            return engel_local_multi_model_code.render_code_list_languages(payload)
        if route_id == ENGEL_CODE_LIST_LOCAL_MODELS_ROUTE_ID:
            import engel_local_multi_model_code
            return engel_local_multi_model_code.render_code_list_local_models(payload)
        if route_id == ENGEL_CODE_GENERATE_MULTI_MODEL_ROUTE_ID:
            import engel_local_multi_model_code
            return engel_local_multi_model_code.render_code_generate(payload)
        if route_id == ENGEL_CODE_REFINE_ROUTE_ID:
            import engel_local_multi_model_code
            return engel_local_multi_model_code.render_code_refine(payload)
        if route_id == ENGEL_CODE_BATCH_GENERATE_ROUTE_ID:
            import engel_local_multi_model_code
            return engel_local_multi_model_code.render_code_batch_generate(payload)
        if route_id == ENGEL_CODE_WITH_COMPANION_ROUTE_ID:
            import engel_local_multi_model_code
            return engel_local_multi_model_code.render_code_with_companion(payload)
        if route_id == ENGEL_CODE_TRANSLATE_ROUTE_ID:
            import engel_local_multi_model_code
            return engel_local_multi_model_code.render_code_translate(payload)
        if route_id == ENGEL_CODE_BEST_AUTO_ROUTE_ID:
            import engel_local_multi_model_code
            return engel_local_multi_model_code.render_code_best_for_language(payload)
        if route_id == ENGEL_CODE_LIST_MODELS_FOR_LANG_ROUTE_ID:
            import engel_local_multi_model_code
            return engel_local_multi_model_code.render_code_list_models_for_language(payload)
        if route_id == ENGEL_CODE_MULTI_CANDIDATES_ROUTE_ID:
            import engel_local_multi_model_code
            return engel_local_multi_model_code.render_code_multi_model_candidates(payload)
        if route_id == ENGEL_CODE_STAGE_SUB_ENGEL_ROUTE_ID:
            import engel_local_multi_model_code
            return engel_local_multi_model_code.stage_code_gen_for_sub_engel(payload)
        if route_id == ENGEL_CAPABILITY_SEARCH_ROUTE_ID:
            import engel_capability_index
            return engel_capability_index.render_capability_search(payload)
        if route_id == ENGEL_SCRIPT_DOCS_ROUTE_ID:
            import engel_script
            return engel_script.render_engel_script_docs(payload)
        if route_id == ENGEL_SCRIPT_EXAMPLES_ROUTE_ID:
            import engel_script
            return engel_script.render_engel_script_examples(payload)
        if route_id == ENGEL_SCRIPT_VALIDATE_ROUTE_ID:
            import engel_script
            return engel_script.render_engel_script_validate(payload)
        if route_id == ENGEL_SCRIPT_RUN_ROUTE_ID:
            import engel_script
            return engel_script.render_engel_script_run(payload)
        if route_id == ENGEL_FORGE_DOCS_ROUTE_ID:
            import engel_code_forge
            return engel_code_forge.render_forge_docs(payload)
        if route_id == ENGEL_FORGE_STATUS_ROUTE_ID:
            import engel_code_forge
            return engel_code_forge.render_forge_status(payload)
        if route_id == ENGEL_FORGE_CODE_ROUTE_ID:
            import engel_code_forge
            return engel_code_forge.render_forge(payload)
        if route_id == ENGEL_CONDUCTOR_DOCS_ROUTE_ID:
            import engel_conductor
            return engel_conductor.render_conductor_docs(payload)
        if route_id == ENGEL_CONDUCTOR_GOAL_ROUTE_ID:
            import engel_conductor
            return engel_conductor.render_conduct(payload)
        if route_id == ENGEL_CONDUCTOR_STATUS_ROUTE_ID:
            import engel_conductor
            return engel_conductor.render_goal_status(payload)
        if route_id == ENGEL_ORCHESTRA_DOCS_ROUTE_ID:
            import engel_orchestra
            return engel_orchestra.render_orchestra_docs(payload)
        if route_id == ENGEL_ORCHESTRA_RUN_ROUTE_ID:
            import engel_orchestra
            return engel_orchestra.render_orchestrate(payload)
        if route_id == ENGEL_ORCHESTRA_STATUS_ROUTE_ID:
            import engel_orchestra
            return engel_orchestra.render_orchestra_status(payload)
        if route_id == ENGEL_AGENT_KERNEL_DOCS_ROUTE_ID:
            import engel_agent_kernel
            return engel_agent_kernel.render_agent_docs(payload)
        if route_id == ENGEL_AGENT_KERNEL_RUN_ROUTE_ID:
            import engel_agent_kernel
            return engel_agent_kernel.render_agent_work(payload)
        if route_id == ENGEL_AGENT_KERNEL_STATUS_ROUTE_ID:
            import engel_agent_kernel
            return engel_agent_kernel.render_agent_status(payload)
        if route_id == ENGEL_GROK_BOT_DOCS_ROUTE_ID:
            import engel_grok_bot
            return engel_grok_bot.render_grok_bot_docs(payload)
        if route_id == ENGEL_GROK_BOT_STATUS_ROUTE_ID:
            import engel_grok_bot
            return engel_grok_bot.render_grok_bot_status(payload)
        if route_id == ENGEL_GROK_BOT_LIST_ROUTE_ID:
            import engel_grok_bot
            return engel_grok_bot.render_grok_bot_list(payload)
        if route_id == ENGEL_GROK_BOT_COMPUTER_ROUTE_ID:
            import engel_grok_bot
            return engel_grok_bot.render_grok_bot_computer(payload)
        if route_id == ENGEL_GROK_BOT_APPROVALS_ROUTE_ID:
            import engel_grok_bot
            return engel_grok_bot.render_grok_bot_approvals(payload)
        if route_id == ENGEL_GROK_BOT_CREATE_ROUTE_ID:
            import engel_grok_bot
            return engel_grok_bot.render_grok_bot_create(payload)
        if route_id == ENGEL_GROK_BOT_MESSAGE_ROUTE_ID:
            import engel_grok_bot
            return engel_grok_bot.render_grok_bot_message(payload)
        if route_id == ENGEL_GROK_BOT_HANDOFF_ROUTE_ID:
            import engel_grok_bot
            return engel_grok_bot.render_grok_bot_handoff(payload)

        if route_id == ENGEL_GROK_BOT_PRESENCE_ROUTE_ID:
            import engel_grok_bot
            return engel_grok_bot.render_grok_bot_presence(payload)
        if route_id == ENGEL_ROUTINES_DOCS_ROUTE_ID:
            import engel_routines
            return engel_routines.render_routines_docs(payload)
        if route_id == ENGEL_ROUTINES_STATUS_ROUTE_ID:
            import engel_routines
            return engel_routines.render_routines_status(payload)
        if route_id == ENGEL_ROUTINES_LIST_ROUTE_ID:
            import engel_routines
            return engel_routines.render_routines_list(payload)
        if route_id == ENGEL_ROUTINES_CREATE_ROUTE_ID:
            import engel_routines
            return engel_routines.render_routines_create(payload)
        if route_id == ENGEL_ROUTINES_DUE_ROUTE_ID:
            import engel_routines
            return engel_routines.render_routines_due(payload)
        if route_id == ENGEL_ROUTINES_STAGE_ROUTE_ID:
            import engel_routines
            return engel_routines.render_routines_stage(payload)
        if route_id == ENGEL_ROUTINES_PAUSE_ROUTE_ID:
            import engel_routines
            return engel_routines.render_routines_pause(payload)
        if route_id == ENGEL_COMPACTION_DOCS_ROUTE_ID:
            import engel_context_compaction
            return engel_context_compaction.render_compaction_docs(payload)
        if route_id == ENGEL_COMPACTION_STATUS_ROUTE_ID:
            import engel_context_compaction
            return engel_context_compaction.render_compaction_status(payload)
        if route_id == ENGEL_COMPACTION_COMPACT_ROUTE_ID:
            import engel_context_compaction
            return engel_context_compaction.render_compaction_compact(payload)
        if route_id == ENGEL_MCP_ALLOWLIST_DOCS_ROUTE_ID:
            import engel_mcp_allowlist
            return engel_mcp_allowlist.render_mcp_allowlist_docs(payload)
        if route_id == ENGEL_MCP_ALLOWLIST_STATUS_ROUTE_ID:
            import engel_mcp_allowlist
            return engel_mcp_allowlist.render_mcp_allowlist_status(payload)
        if route_id == ENGEL_MCP_ALLOWLIST_LIST_ROUTE_ID:
            import engel_mcp_allowlist
            return engel_mcp_allowlist.render_mcp_allowlist_list(payload)
        if route_id == ENGEL_ICM_DOCS_ROUTE_ID:
            import engel_icm_architect
            return engel_icm_architect.render_icm_docs(payload)
        if route_id == ENGEL_ICM_STATUS_ROUTE_ID:
            import engel_icm_architect
            return engel_icm_architect.render_icm_status(payload)
        if route_id == ENGEL_ICM_AUDIT_ROUTE_ID:
            import engel_icm_architect
            return engel_icm_architect.render_icm_audit(payload)
        if route_id == ENGEL_ICM_WORKSPACE_ROUTE_ID:
            import engel_icm_architect
            return engel_icm_architect.render_icm_workspace(payload)
        if route_id == ENGEL_ICM_OUTPUTS_ROUTE_ID:
            import engel_icm_output_router
            return engel_icm_output_router.render_icm_outputs(payload)
        if route_id == ENGEL_ICM_ROUTING_ROUTE_ID:
            import engel_icm_output_router
            return engel_icm_output_router.render_icm_routing(payload)
        if route_id == ENGEL_GRAPH_STUDIO_STATUS_ROUTE_ID:
            import engel_graph_loop_studio
            return engel_graph_loop_studio.render_graph_studio_status(payload)
        if route_id == ENGEL_GRAPH_STUDIO_OPEN_ROUTE_ID:
            import engel_graph_loop_studio
            return engel_graph_loop_studio.render_graph_studio_open(payload)
        if route_id == ENGEL_GRAPH_STUDIO_NEW_ROUTE_ID:
            import engel_graph_loop_studio
            return engel_graph_loop_studio.render_graph_studio_new(payload)
        if route_id == ENGEL_GRAPH_STUDIO_LIST_ROUTE_ID:
            import engel_graph_loop_studio
            return engel_graph_loop_studio.render_graph_studio_list(payload)
        if route_id == ENGEL_GROVER_STATUS_ROUTE_ID:
            import engel_grover_lane
            return engel_grover_lane.render_grover_status(payload)
        if route_id == ENGEL_GROVER_EXPLAIN_ROUTE_ID:
            import engel_grover_lane
            return engel_grover_lane.render_grover_explain(payload)
        if route_id == ENGEL_GROVER_SEARCH_ROUTE_ID:
            import engel_grover_lane
            return engel_grover_lane.render_grover_search(payload)
        if route_id == ENGEL_GROVER_CRYPTO_ROUTE_ID:
            import engel_grover_lane
            return engel_grover_lane.render_grover_crypto(payload)
        if route_id == ENGEL_NEXT_STAGE_STATUS_ROUTE_ID:
            import engel_next_stage_runner
            return engel_next_stage_runner.render_next_stage_status(payload)
        if route_id == ENGEL_NEXT_STAGE_INVENTORY_ROUTE_ID:
            import engel_next_stage_runner
            return engel_next_stage_runner.render_next_stage_inventory(payload)
        if route_id == ENGEL_NEXT_STAGE_COMPANION_ROUTE_ID:
            import engel_next_stage_runner
            return engel_next_stage_runner.render_next_stage_companion(payload)
        if route_id == ENGEL_NEXT_STAGE_SAFETY_ROUTE_ID:
            import engel_next_stage_runner
            return engel_next_stage_runner.render_next_stage_safety(payload)
        if route_id == ENGEL_WIKI_ONE_STATUS_ROUTE_ID:
            import engel_wiki_one
            return engel_wiki_one.render_wiki_one_status(payload)
        if route_id == ENGEL_WIKI_ONE_JOURNAL_ROUTE_ID:
            import engel_wiki_one
            return engel_wiki_one.render_wiki_one_journal(payload)
        if route_id == ENGEL_WIKI_ONE_UPDATE_ROUTE_ID:
            import engel_wiki_one
            return engel_wiki_one.render_wiki_one_update(payload)
    except Exception as exc:
        return "\n".join(
            [
                "Engel AI Update Route",
                "",
                "Status renderer unavailable.",
                "Route: " + route_id,
                "Error: " + str(exc),
                "",
                "Safety:",
                "- READ_ONLY_STATUS_ONLY",
                "- NO_MEMORY_PROMOTION",
                "- NO_TRUSTED_MEMORY_WRITE",
                "- NO_FIX_APPLY",
                "- NO_ARCHIVE_MUTATION",
                "- NO_PROVIDER_MODEL_NETWORK",
                "- NO_BACKGROUND_WORKER",
                "- NO_VISIBLE_UI_CHANGE",
            ]
        )
    return "Unknown Engel AI update route: " + route_id
