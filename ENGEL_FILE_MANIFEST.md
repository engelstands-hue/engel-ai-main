# Engel File Manifest

Scope: `D:\b.WorkSpace\Engel App`

This manifest is documentation-only. It is based on read-only path, name, and type inspection from the local workspace. Secret-like folders and `.git` internals are not expanded here.

A literal row for every file in this workspace is not operationally useful because the tree contains very large backup, cache, vendor, build, and runtime areas. Nested items inherit the classification of the nearest listed container unless a more specific rule below applies.

## Classification Categories

| Category | Meaning | Default migration target |
|---|---|---|
| Core runtime | Main Engel execution code and local app entrypoints | `/opt/engel/app` after approval |
| Orchestrator/controller | ROG controller, cluster coordination, routing, startup, and dispatch logic | `/opt/engel/app` or ROG-only depending owner |
| Agent/worker | Agent roles, worker scripts, device helpers, Android/remote workers | `/opt/engel/app` and `/opt/engel/core` |
| Model | Local model files, active model references, adapters, and model metadata | `/opt/engel/models-active` or `/mnt/engel-vault/models-archive` |
| Memory | Persistent memories, notes, task stores, chat state, and knowledge records | `/opt/engel/memory` and mirrored backups on vault |
| UI/frontend | Desktop, Electron/Tauri/web UI, 3D office, gallery, and chat surfaces | `/opt/engel/app` with ROG launcher bridge |
| Tool/script | Installers, setup helpers, diagnostics, and operator utilities | `/opt/engel/scripts` after review |
| Documentation | Markdown, handoff, manifests, records, maps, and planning docs | `/opt/engel/docs` and vault backup |
| Runtime/cache/log | Generated logs, caches, temp files, profiles, and runtime state | Regenerate or vault/log target; do not treat as source |
| Backup/archive | Historical snapshots, duplicate working trees, old generated outputs | `/mnt/engel-vault/backups` if retained |
| Build/vendor | Distribution bundles, package caches, dependencies, build outputs | Rebuild or migrate only when explicitly needed |
| Unknown/pending review | Path cannot be safely assigned from name/type alone | Hold for Josh review before migration or activation |

## Migration Rules

| Rule | Action |
|---|---|
| Active app/runtime code | Copy to CT 246 under `/opt/engel/app` only after Josh approves a staged migration. |
| Active memory | Copy to `/opt/engel/memory`; mirror backups to `/mnt/engel-vault/backups`; preserve timestamps. |
| Large models and archives | Put active fast models in `/opt/engel/models-active`; put bulk model archives in `/mnt/engel-vault/models-archive`. |
| Backups, old exports, and duplicate trees | Stage on `/mnt/engel-vault/backups`; do not activate automatically. |
| Cache, temp, dist, build, browser profile, and logs | Recreate on the server unless Josh requests preserving the specific artifact. |
| Secret-bearing files | Do not print contents; migrate only through an approved secret handling step. |
| Unknown files | Do not delete or auto-run; keep for review. |

## Top-Level Manifest

| Path | Type | Likely role | Migration target | Notes |
|---|---|---|---|---|
| `.\.agents` | Directory | Agent/worker | `/opt/engel/app and /opt/engel/core` | Worker/device material; activate only through reviewed startup policy. |
| `.\.claude` | Directory | Tool/config | `ROG controller or /opt/engel/docs by approval` | Assistant/tool state; inspect for secrets before any migration. |
| `.\.codex` | Directory | Tool/config | `ROG controller or /opt/engel/docs by approval` | Assistant/tool state; inspect for secrets before any migration. |
| `.\.cursor` | Directory | Tool/config | `ROG controller or /opt/engel/docs by approval` | Assistant/tool state; inspect for secrets before any migration. |
| `.\.git` | Directory | Runtime/cache/log or build/vendor | `Regenerate or vault only if needed` | Generated or tool-managed container; not authoritative source. |
| `.\.grok` | Directory | Tool/config | `ROG controller or /opt/engel/docs by approval` | Assistant/tool state; inspect for secrets before any migration. |
| `.\.pytest_cache` | Directory | Runtime/cache/log or build/vendor | `Regenerate or vault only if needed` | Generated or tool-managed container; not authoritative source. |
| `.\__pycache__` | Directory | Runtime/cache/log or build/vendor | `Regenerate or vault only if needed` | Generated or tool-managed container; not authoritative source. |
| `.\agents` | Directory | Agent/worker | `/opt/engel/app and /opt/engel/core` | Worker/device material; activate only through reviewed startup policy. |
| `.\archive` | Directory | Backup/archive | `/mnt/engel-vault/backups` | Historical or duplicate data; do not activate automatically. |
| `.\assets` | Directory | UI/frontend | `/opt/engel/app` | User-facing UI or asset container. |
| `.\backups` | Directory | Backup/archive | `/mnt/engel-vault/backups` | Historical or duplicate data; do not activate automatically. |
| `.\browser_profile` | Directory | Runtime/cache/log or build/vendor | `Regenerate or vault only if needed` | Generated or tool-managed container; not authoritative source. |
| `.\dist` | Directory | Runtime/cache/log or build/vendor | `Regenerate or vault only if needed` | Generated or tool-managed container; not authoritative source. |
| `.\engel_agent_main` | Directory | Core runtime / module | `/opt/engel/app` | Engel module container; migrate by module owner and test path. |
| `.\engel_ai_gallery_main` | Directory | UI/frontend | `/opt/engel/app` | User-facing UI or asset container. |
| `.\engel_airllm_main` | Directory | Model | `/opt/engel/models-active or /mnt/engel-vault/models-archive` | Model-related container; active/bulk split required. |
| `.\engel_chat_ui_main` | Directory | UI/frontend | `/opt/engel/app` | User-facing UI or asset container. |
| `.\engel_claw3d_main` | Directory | Core runtime / module | `/opt/engel/app` | Engel module container; migrate by module owner and test path. |
| `.\engel_cli_anything_main` | Directory | Core runtime / module | `/opt/engel/app` | Engel module container; migrate by module owner and test path. |
| `.\engel_cubesandbox_main` | Directory | Core runtime / module | `/opt/engel/app` | Engel module container; migrate by module owner and test path. |
| `.\engel_evolution_engine_main` | Directory | Core runtime / module | `/opt/engel/app` | Engel module container; migrate by module owner and test path. |
| `.\engel_evolution_lab_main` | Directory | Core runtime / module | `/opt/engel/app` | Engel module container; migrate by module owner and test path. |
| `.\engel_flutter_main` | Directory | UI/frontend | `/opt/engel/app` | User-facing UI or asset container. |
| `.\engel_git_nexus_main` | Directory | Core runtime / module | `/opt/engel/app` | Engel module container; migrate by module owner and test path. |
| `.\engel_gstack_main` | Directory | Core runtime / module | `/opt/engel/app` | Engel module container; migrate by module owner and test path. |
| `.\engel_hermes_agent_main` | Directory | Core runtime / module | `/opt/engel/app` | Engel module container; migrate by module owner and test path. |
| `.\engel_humanizer_main` | Directory | Core runtime / module | `/opt/engel/app` | Engel module container; migrate by module owner and test path. |
| `.\engel_jarvis_main` | Directory | Core runtime / module | `/opt/engel/app` | Engel module container; migrate by module owner and test path. |
| `.\engel_knowledge_graph_v2_main` | Directory | Core runtime / module | `/opt/engel/app` | Engel module container; migrate by module owner and test path. |
| `.\engel_lan_main` | Directory | Core runtime / module | `/opt/engel/app` | Engel module container; migrate by module owner and test path. |
| `.\engel_lfm2_code_review_main` | Directory | Core runtime / module | `/opt/engel/app` | Engel module container; migrate by module owner and test path. |
| `.\engel_lfm2_mobile_main` | Directory | Core runtime / module | `/opt/engel/app` | Engel module container; migrate by module owner and test path. |
| `.\engel_lfm2_vision_main` | Directory | Core runtime / module | `/opt/engel/app` | Engel module container; migrate by module owner and test path. |
| `.\engel_library` | Directory | Core runtime / module | `/opt/engel/app` | Engel module container; migrate by module owner and test path. |
| `.\engel_localsend_main` | Directory | Core runtime / module | `/opt/engel/app` | Engel module container; migrate by module owner and test path. |
| `.\engel_main` | Directory | Core runtime / module | `/opt/engel/app` | Engel module container; migrate by module owner and test path. |
| `.\engel_native_agent_main` | Directory | Core runtime / module | `/opt/engel/app` | Engel module container; migrate by module owner and test path. |
| `.\engel_octogent_main` | Directory | Core runtime / module | `/opt/engel/app` | Engel module container; migrate by module owner and test path. |
| `.\engel_open_agents_main` | Directory | Core runtime / module | `/opt/engel/app` | Engel module container; migrate by module owner and test path. |
| `.\engel3d_office_main` | Directory | UI/frontend | `/opt/engel/app` | User-facing UI or asset container. |
| `.\engelcode_main` | Directory | Core runtime / module | `/opt/engel/app` | Engel module container; migrate by module owner and test path. |
| `.\engelsandbox_main` | Directory | Core runtime / module | `/opt/engel/app` | Engel module container; migrate by module owner and test path. |
| `.\examples` | Directory | Tool/script | `/opt/engel/scripts or /opt/engel/app` | Review before running on CT. |
| `.\lessons` | Directory | Memory/documentation | `/opt/engel/memory and /mnt/engel-vault/backups` | Persistent records; preserve timestamps. |
| `.\memory` | Directory | Memory/documentation | `/opt/engel/memory and /mnt/engel-vault/backups` | Persistent records; preserve timestamps. |
| `.\mobile` | Directory | Agent/worker | `/opt/engel/app and /opt/engel/core` | Worker/device material; activate only through reviewed startup policy. |
| `.\models` | Directory | Model | `/opt/engel/models-active or /mnt/engel-vault/models-archive` | Model-related container; active/bulk split required. |
| `.\products` | Directory | UI/frontend | `/opt/engel/app` | User-facing UI or asset container. |
| `.\pyinstaller_runtime_hooks` | Directory | Tool/script | `/opt/engel/scripts or /opt/engel/app` | Review before running on CT. |
| `.\remote_nodes` | Directory | Agent/worker | `/opt/engel/app and /opt/engel/core` | Worker/device material; activate only through reviewed startup policy. |
| `.\remote_workers` | Directory | Agent/worker | `/opt/engel/app and /opt/engel/core` | Worker/device material; activate only through reviewed startup policy. |
| `.\reports` | Directory | Memory/documentation | `/opt/engel/memory and /mnt/engel-vault/backups` | Persistent records; preserve timestamps. |
| `.\runtime` | Directory | Runtime/cache/log or build/vendor | `Regenerate or vault only if needed` | Generated or tool-managed container; not authoritative source. |
| `.\rust` | Directory | Core runtime / module | `/opt/engel/app` | Engel module container; migrate by module owner and test path. |
| `.\scripts` | Directory | Tool/script | `/opt/engel/scripts or /opt/engel/app` | Review before running on CT. |
| `.\skills` | Directory | Tool/script | `/opt/engel/scripts or /opt/engel/app` | Review before running on CT. |
| `.\tools` | Directory | Tool/script | `/opt/engel/scripts or /opt/engel/app` | Review before running on CT. |
| `.\.cursorrules` | File | Unknown/pending review | `Hold for Josh review` | Classify from name/type before migration. |
| `.\.env` | File | Config/secret-sensitive | `Approved secret handling only` | Contents not inspected or printed. |
| `.\.env.template` | File | Config/secret-sensitive | `Approved secret handling only` | Contents not inspected or printed. |
| `.\.gitignore` | File | Unknown/pending review | `Hold for Josh review` | Classify from name/type before migration. |
| `.\_e2e_meeting_room_test.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\_meeting_room_agent_routing_test.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\_route_smoke.log` | File | Runtime/cache/log | `Regenerate or /mnt/engel-vault/logs` | Generated runtime artifact. |
| `.\_route_smoke.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\AGENTS.md` | File | Documentation | `/opt/engel/docs and vault backup` | Cluster records, handoff, manifest, or notes. |
| `.\build_engel.log` | File | Runtime/cache/log | `Regenerate or /mnt/engel-vault/logs` | Generated runtime artifact. |
| `.\build_hive.log` | File | Runtime/cache/log | `Regenerate or /mnt/engel-vault/logs` | Generated runtime artifact. |
| `.\ChatGPT Image May 9, 2026, 07_22_02 AM.png` | File | Asset/UI | `/opt/engel/app/assets` | Visual asset. |
| `.\ChatGPT Image May 9, 2026, 07_52_50 AM.png` | File | Asset/UI | `/opt/engel/app/assets` | Visual asset. |
| `.\ChatGPT Image May 9, 2026, 08_10_20 .png` | File | Asset/UI | `/opt/engel/app/assets` | Visual asset. |
| `.\CHECK_ENGEL_RUST.cmd` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\check_firewall.ps1` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\check_ntfs.ps1` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\check_share.ps1` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\CLAUDE.md` | File | Documentation | `/opt/engel/docs and vault backup` | Cluster records, handoff, manifest, or notes. |
| `.\CODEX_HANDOFF.md` | File | Documentation | `/opt/engel/docs and vault backup` | Cluster records, handoff, manifest, or notes. |
| `.\CODEX_JOB.md` | File | Documentation | `/opt/engel/docs and vault backup` | Cluster records, handoff, manifest, or notes. |
| `.\codex_usage_coffee.b64` | File | Unknown/pending review | `Hold for Josh review` | Classify from name/type before migration. |
| `.\decode_codex_usage_coffee.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\Engel AI Rust UI.lnk` | File | ROG launcher | `ROG controller only` | Windows shortcut; recreate if needed. |
| `.\Engel Health Check.cmd` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\Engel Terminal.lnk` | File | ROG launcher | `ROG controller only` | Windows shortcut; recreate if needed. |
| `.\Engel.spec` | File | Core runtime / Engel module | `/opt/engel/app` | Named Engel entry or module file. |
| `.\engel_account_connector.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_adb_worker_manager.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_agent_bridge.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_agent_meeting_room.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_agent_meetingroom.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_agent_skill_candidate_scaffold.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\ENGEL_AGENTIC_ROLES.md` | File | Documentation | `/opt/engel/docs and vault backup` | Cluster records, handoff, manifest, or notes. |
| `.\engel_ai.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_ai_body_status.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_ai_bounded_local_chat_smoke.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_ai_connector_hub.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_ai_first_local_response_smoke.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_ai_first_local_response_smoke_exit_fix.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_ai_first_response_output_filter_tuning.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_ai_growth_dashboard.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_ai_intent_planner.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_ai_llama_cpp_compatibility_matrix.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_ai_llama_cpp_runtime_candidate_validation.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_ai_llama_cpp_runtime_swap_approval.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_ai_llama_cpp_runtime_swap_plan.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_ai_local_approved_memory_context_preview.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_ai_local_approved_memory_readback.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_ai_local_chat_prompt_draft.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_ai_local_chat_session_draft.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_ai_local_chat_session_memory_candidate_review_and_approved_write.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_ai_local_chat_session_review.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_ai_local_open_chat_supervised_run.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_ai_local_runtime_path_config.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_ai_main_rust_connectors_bridge.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_ai_main_rust_local_chat_bridge.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_ai_main_rust_research_bridge.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_ai_main_rust_ui_shell_bridge.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_ai_manual_model_file_intake.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_ai_model_review_approval.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_ai_no_generation_load_check.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_ai_offline_runtime_dry_run.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_ai_persistent_chat_supervised_runtime_plan.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_ai_proceed_receipts.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_ai_receipt_viewer.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_ai_runtime_candidate_alt_command_style.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_ai_runtime_candidate_failure_diagnosis.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_ai_runtime_candidate_validation_replay.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_ai_runtime_readiness.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_ai_update_routes.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_airllm_bridge.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_android_remote_worker_contract.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_android_remote_worker_protocol.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_android_worker_prompt_signals.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_app.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_app_d_drive_build_plan.md` | File | Documentation | `/opt/engel/docs and vault backup` | Cluster records, handoff, manifest, or notes. |
| `.\engel_approved_for_reference_metadata_writer.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_approved_library_downloader.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_approved_memory_promotion.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_architect_agent.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_archive_shelf_manager.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_batch_library_approval.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\ENGEL_BODY_PARTS.md` | File | Documentation | `/opt/engel/docs and vault backup` | Cluster records, handoff, manifest, or notes. |
| `.\engel_bounded_file_presence_checker.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_bounded_self_learning_scheduler.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_brain_provider_prompt_context.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_branding.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_browser_ai_bridge.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_browser_queen_phase2_status.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_browser_queen_phase3_contract.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_browser_queen_phase4_contract.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_browser_queen_phase5_contract.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_browser_queen_runtime_mvp.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_browser_queen_status.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_browser_queen_workbench.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_candidate_learning_output_review.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_candidate_review_dashboard.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_candidate_set_approval.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_chat_export_intake.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\ENGEL_CLUSTER_TOPOLOGY.md` | File | Documentation | `/opt/engel/docs and vault backup` | Cluster records, handoff, manifest, or notes. |
| `.\engel_code_companion.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_code_companion_candidate_finder.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_code_companion_candidate_review_status.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_code_companion_contextual_talk.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_code_companion_continue_product.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_code_companion_conversation_commands.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_code_companion_examples.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_code_companion_fix_candidate_intake.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_code_companion_health_delta.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_code_companion_lesson_review.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_code_companion_lessons.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_code_companion_low_risk_patch_runner.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_code_companion_memory_handoff.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_code_companion_password_gate_integration.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_code_companion_patch_application_gate.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_code_companion_patch_apply.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_code_companion_patch_apply_approval_receipt.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_code_companion_patch_apply_dry_run.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_code_companion_patch_bundle_draft.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_code_companion_patch_candidate.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_code_companion_patch_class_allowlist.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_code_companion_patch_lesson_bridge.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_code_companion_patch_lesson_review.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_code_companion_patch_plan_preview.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_code_companion_patch_proposals.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_code_companion_patch_receipt_viewer.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_code_companion_patch_status_surface.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_code_companion_product_context.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_code_companion_product_cycle_dashboard.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_code_companion_product_session.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_code_companion_product_workbench.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_code_companion_products.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_code_companion_project_builder.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_code_companion_protected_patch_apply.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_code_companion_readme_manifest_proposals.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_code_companion_talk_to_code.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_code_companion_verifier_plan.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_code_factory_bridge.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_code_workshop.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\ENGEL_CODEX_ACTION_LOG.md` | File | Documentation | `/opt/engel/docs and vault backup` | Cluster records, handoff, manifest, or notes. |
| `.\engel_communication_queen_assignment_producer.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_communication_router.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_companion.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_core_continuity_status_surface.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_core_immune_system_architecture.md` | File | Documentation | `/opt/engel/docs and vault backup` | Cluster records, handoff, manifest, or notes. |
| `.\engel_core_v1_daily_check.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_core_v1_dashboard_status.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_daily_cycle_runner.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_daily_cycle_status_surface.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_darwin_local_runner.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_darwin_status.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_de_bruijn_memory_loader.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_debruijn_lane_traversal_classifier.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_debruijn_quantum_apply.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_debruijn_quantum_automation_file_structure.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_debruijn_quantum_build_promote.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_debruijn_quantum_runtime.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_debruijn_quantum_structure_status.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_desktop_v2.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_desktop_v2_part1.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_desktop_v2_part2.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_device_capability_registry.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\ENGEL_DEVICE_REGISTRY.md` | File | Documentation | `/opt/engel/docs and vault backup` | Cluster records, handoff, manifest, or notes. |
| `.\Engel_Device_Visible_Proof_Status_GoogleDocs.docx` | File | Core runtime / Engel module | `/opt/engel/app` | Named Engel entry or module file. |
| `.\engel_discord_bridge.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_ehuman_bridge.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_eng3d_bridge.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_engel_agent_runner.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_engel_lan_runner.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_engel_main_runner.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_engel_sandbox_runner.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_engel3d_runner.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_engelcode_runner.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_engize_bridge.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_ensor_bridge.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_ephify_bridge.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_evolver_bridge.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_external_memory_intake_bridge.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_external_memory_roots.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_external_memory_scaffold.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_external_memory_status.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\ENGEL_FILE_MANIFEST.md` | File | Documentation | `/opt/engel/docs and vault backup` | Cluster records, handoff, manifest, or notes. |
| `.\engel_fix_candidate_queue.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_game_factory_bridge.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_global_password_gate.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_guardian_watchdog.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_guardian_watchdog_receipts.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_guided_library_review_draft_report.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_guided_library_review_surface.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\ENGEL_HEALTH_CHECKS.md` | File | Documentation | `/opt/engel/docs and vault backup` | Cluster records, handoff, manifest, or notes. |
| `.\engel_hive_data_services.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_human_command_mode.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_human_command_shared.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_human_review_receipt_draft_surface.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_human_review_receipt_writer.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_jcode_bridge.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_knowledge_graph_v2_status.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_lan_worker.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_large_chat_llm.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\ENGEL_LAUNCH_SAFETY_GUARD_HANDOFF.md` | File | Documentation | `/opt/engel/docs and vault backup` | Cluster records, handoff, manifest, or notes. |
| `.\engel_leak_guard.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_learning_job_queue.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_lesson_candidate_extractor.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_llama_cli_runner.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_local_llm_bridge.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_local_llm_dashboard.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_local_llm_doctor.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_local_model_manager.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_local_model_service.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_local_multi_model_code.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_lokalz_bridge.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_lorenz_attractor_lane_classifier.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_low_risk_self_fix_runner.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_low_risk_self_fix_status_surface.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_main_server_merge.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_manual_library_queue_record_viewer.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_manual_library_queue_record_writer.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_manual_model_intake_evaluator.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_memory_archive_status.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_memory_candidate_inventory.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_memory_candidate_proposals.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_memory_candidate_review_dashboard.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_memory_promotion_writer.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_memory_roots_storage_layout.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\ENGEL_MIGRATION_PLAN.md` | File | Documentation | `/opt/engel/docs and vault backup` | Cluster records, handoff, manifest, or notes. |
| `.\engel_minor_tools_runner.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\ENGEL_MODULE_MANIFEST.md` | File | Documentation | `/opt/engel/docs and vault backup` | Cluster records, handoff, manifest, or notes. |
| `.\engel_multi_android_remote_workers.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_new_tools_runner.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_next_step_human_command_smoke.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_octogent_runner.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_offline_model_runtime_contract.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_offline_seed_llm.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\ENGEL_OPEN_TASKS.md` | File | Documentation | `/opt/engel/docs and vault backup` | Cluster records, handoff, manifest, or notes. |
| `.\Engel_Operator_Manual.pdf` | File | Core runtime / Engel module | `/opt/engel/app` | Named Engel entry or module file. |
| `.\engel_os_bridge.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_outside_ai_boundary.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_overnight_loop.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_overnight_runner.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_overnight_status.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_overnight_support.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_phone_auto_repair.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_phone_auto_repair_verified.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_phone_auto_repair_verified_d_only.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_phone_repair_button.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_phone_to_pc_network_proof_d_only.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_phone_wake_manager.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_progress_dashboard.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_project_paths.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_prompt_bridge_selection.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_prompt_injection_guard.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_protected_action_registry.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_python_teaching_mode.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_remote_direct_pairing_fix_d_only.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_remote_pairing_probe_d_only.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_remote_worker_app_scaffold.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_remote_worker_job_assignment.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_remote_worker_lan_pairing.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_remote_worker_link_manager.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_remote_worker_pairing_host_d_only.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_remote_worker_pairing_reader_d_only.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_remote_worker_pairing_sniffer_d_only.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_remote_worker_port_conflict_fix_d_only.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_remote_worker_result_intake.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_research_brain_v2.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_research_conversation_commands.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_research_intake_queue.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_research_lesson_bridge.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_research_lesson_review.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_research_memory_candidate_proposal.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_research_note_viewer.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_research_office.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_research_office_data.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_research_status.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_research_summary_proposals.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_research_thinking_screen.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_research_to_fix_loop.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_research_toggle_status.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_research_toggle_worker.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_research_understanding_library.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_route_explorer.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\ENGEL_RUST_BUILD_ENV.ps1` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_rust_executable_results_bridge.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_rust_lan_link_bridge.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_rust_meeting_room_bridge.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_rust_remote_worker_lan_bridge.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_rust_shared_room_bridge.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\ENGEL_SAFETY_RULES.md` | File | Documentation | `/opt/engel/docs and vault backup` | Cluster records, handoff, manifest, or notes. |
| `.\engel_sandbox_bridge.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_self_fix_improvement_candidate.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_self_fix_receipt_viewer.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_self_learning_mini_runner.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_self_learning_run_controller.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_self_learning_status_surface.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_shared_drive_room.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_skill_agent_creator.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_speech_bridge.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\ENGEL_STARTUP_POLICY.md` | File | Documentation | `/opt/engel/docs and vault backup` | Cluster records, handoff, manifest, or notes. |
| `.\ENGEL_STORAGE_MAP.md` | File | Documentation | `/opt/engel/docs and vault backup` | Cluster records, handoff, manifest, or notes. |
| `.\engel_sub_node_meeting_bridge.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_sub_node_remote_control.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_system_integration_status.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\ENGEL_SYSTEM_MAP.md` | File | Documentation | `/opt/engel/docs and vault backup` | Cluster records, handoff, manifest, or notes. |
| `.\engel_system_monitor.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_talk_to_code.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_temp_policy.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_trading_dashboard_bridge.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_training_trusted_memory.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_trusted_memory_target.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_trusted_memory_target_enable.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_trusted_vault_storage.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_truthfulness_anti_flattery_guard.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_ui_executable_results.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_ui_system_actions.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_ui_theme.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_unified_conversation_router.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_untrusted_content_guard.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_untrusted_research_note_generator.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_vault_paths.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_verifier_improvement_candidate.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_verify_status.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_wave3_runner.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_wave4_runner.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_whole_system_incomplete_audit.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_windows_sub_node_agent.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_wsl_bridge.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\engel_wsl_ubuntu_runner.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\EngelDesktopV2.spec` | File | Core runtime / Engel module | `/opt/engel/app` | Named Engel entry or module file. |
| `.\EngelSuperSwarmHive3D.spec` | File | Core runtime / Engel module | `/opt/engel/app` | Named Engel entry or module file. |
| `.\files.zip` | File | Backup/archive | `/mnt/engel-vault/backups or transfers` | Compressed artifact; do not unpack automatically. |
| `.\Grok Build.lnk` | File | ROG launcher | `ROG controller only` | Windows shortcut; recreate if needed. |
| `.\HANDOFF_MEETING_ROOM_LAN_FLOW_20260526.md` | File | Documentation | `/opt/engel/docs and vault backup` | Cluster records, handoff, manifest, or notes. |
| `.\INSTALL_ENGEL_RUST_BUILD_ENV.cmd` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\launch_engel_desktop_v2.bat` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\launch_engel_meeting_room.bat` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\PACKAGE_ENGEL_AI_STANDALONE.cmd` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\PACKAGE_ENGEL_AI_STANDALONE.ps1` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\personality.md` | File | Documentation | `/opt/engel/docs and vault backup` | Cluster records, handoff, manifest, or notes. |
| `.\Reconnect Engel Phones.cmd` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\Reconnect Engel Phones.lnk` | File | ROG launcher | `ROG controller only` | Windows shortcut; recreate if needed. |
| `.\rescue_diff.patch` | File | Unknown/pending review | `Hold for Josh review` | Classify from name/type before migration. |
| `.\rescue_status.txt` | File | Documentation | `/opt/engel/docs and vault backup` | Cluster records, handoff, manifest, or notes. |
| `.\RUN_ENGEL_RUST_UI.cmd` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\secconfig.inf` | File | Unknown/pending review | `Hold for Josh review` | Classify from name/type before migration. |
| `.\set_acl.bat` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\set_acl.ps1` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\set_acl2.ps1` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\set_everyone.bat` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\ShareEngelWorkspace.cmd` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\sitecustomize.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\skill.zip` | File | Backup/archive | `/mnt/engel-vault/backups or transfers` | Compressed artifact; do not unpack automatically. |
| `.\soul.md` | File | Documentation | `/opt/engel/docs and vault backup` | Cluster records, handoff, manifest, or notes. |
| `.\Start Engel App.vbs` | File | Unknown/pending review | `Hold for Josh review` | Classify from name/type before migration. |
| `.\Start Engel Rust UI.vbs` | File | Unknown/pending review | `Hold for Josh review` | Classify from name/type before migration. |
| `.\start_discord_bridge.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\start_engel.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\test_browser_bridge.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |
| `.\trigger_codex_event.py` | File | Core runtime or tool/script | `/opt/engel/app or /opt/engel/scripts` | Review before activation on CT. |

## Recursive Container Rules

| Path pattern | Type | Likely role | Migration target | Notes |
|---|---|---|---|---|
| `.\engel_*\**` | Directory tree | Engel module source | `/opt/engel/app` | Module trees should move as named units with tests and owner notes. |
| `.\memory\**` | Directory tree | Persistent memory | `/opt/engel/memory` | Preserve timestamps; mirror to vault backups. |
| `.\models\**` | Directory tree | Model store | `/opt/engel/models-active or /mnt/engel-vault/models-archive` | Separate active fast models from bulk archives. |
| `.\backups\**` | Directory tree | Backup/archive | `/mnt/engel-vault/backups` | Do not activate or overwrite active files automatically. |
| `.\archive\**` | Directory tree | Archive | `/mnt/engel-vault/backups/archive` | Historical data; keep read-only until reviewed. |
| `.\runtime\**` | Directory tree | Runtime state | `/opt/engel/run or regenerate` | Only migrate specific state that Engel needs persistently. |
| `.\dist\**` | Directory tree | Build output | `Rebuild preferred` | Generated distribution output; not source of truth. |
| `.\.git\**` | Directory tree | Git metadata | `Do not migrate as app data` | Repository metadata; not expanded. |
| `.\.codex\**` | Directory tree | Codex/tool state | `ROG controller only unless approved` | May contain session data; not expanded. |
| `.\.claude\**` | Directory tree | Assistant/tool state | `ROG controller only unless approved` | May contain local tool state. |
| `.\browser_profile\**` | Directory tree | Browser profile/cache | `Regenerate` | Do not move cookies/session material without approval. |
| `.\scripts\**` | Directory tree | Operator scripts | `/opt/engel/scripts` | Review each before execution on Proxmox/CT. |
| `.\tools\**` | Directory tree | Tools | `/opt/engel/scripts or /opt/engel/app/tools` | Execution requires review. |
| `.\agents\**` | Directory tree | Agents | `/opt/engel/core or /opt/engel/app/agents` | Start only under approved startup policy. |
| `.\remote_workers\**` | Directory tree | Remote workers | `/opt/engel/app/workers` | Do not auto-launch autonomous workers. |
| `.\mobile\**` | Directory tree | Mobile/Android device support | `/opt/engel/app/mobile` | Phone pairing state must be verified live. |
| `.\reports\**` | Directory tree | Reports/documentation | `/opt/engel/docs/reports` | Useful for audit history. |
| `.\assets\**` | Directory tree | Assets/UI media | `/opt/engel/app/assets` | Retain only referenced assets in active app path. |
| `.\products\**` | Directory tree | Product/app outputs | `/mnt/engel-vault/transfers or /opt/engel/app` | Review whether source or generated output. |
| `.\*.log` | File pattern | Log | `/mnt/engel-vault/logs if retained` | Generated; usually not active source. |
| `.\*.sqlite; .\*.db` | File pattern | Database/memory | `/opt/engel/memory or /mnt/engel-vault/datasets` | Requires schema and ownership review. |
| `.\*.gguf; .\*.safetensors; .\*.bin` | File pattern | Model weight | `/opt/engel/models-active or /mnt/engel-vault/models-archive` | Large files require active/archive split. |
| `.\*.env; .\*secret*; .\*key*` | File pattern | Secret-sensitive config | `Approved secret handling only` | Do not print contents. |

## Unknowns And Pending Review

- Any nested file not covered by a specific rule inherits its parent container classification.
- Any executable, service definition, scheduler item, worker loop, migration helper, or storage helper requires Josh approval before running on the ROG laptop, Proxmox host, or CT 246.
- Any file that may contain credentials, tokens, keys, session cookies, private logs, or provider credentials must be handled through an approved secret migration step.
- This manifest does not authorize deletes, moves, service starts, Proxmox commands, PowerVault changes, iSCSI changes, or multipath changes.

## Source Inventory Note

A read-only count found more than 195,000 workspace files when excluding `.git` and obvious secret paths. The compact manifest above is the operational source for migration classification; full per-file export should be generated into `/mnt/engel-vault/transfers` only if Josh explicitly requests it.
