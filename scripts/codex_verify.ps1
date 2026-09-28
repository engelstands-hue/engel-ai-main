$ErrorActionPreference = "Continue"

$RepoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $RepoRoot

# Prefer Engel-owned D: Python; only fall back to PATH 'python' if the D: copy
# is missing. NEVER hard-code a C: python path here.
$EngelPy = Join-Path $RepoRoot "runtime\python310\python.exe"
if (-not (Test-Path -LiteralPath $EngelPy)) { $EngelPy = "python" }

$script:RunCount = 0
$script:PassCount = 0
$script:SkipCount = 0
$script:FailCount = 0
$script:Failures = New-Object System.Collections.Generic.List[string]

function Invoke-PythonVerifier {
    param(
        [Parameter(Mandatory = $true)][string]$Group,
        [Parameter(Mandatory = $true)][string]$Path,
        [bool]$Required = $true
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        if ($Required) {
            Write-Host "[FAIL][$Group] missing required verifier: $Path"
            $script:FailCount += 1
            $script:Failures.Add("$Group :: missing $Path") | Out-Null
        } else {
            Write-Host "[SKIP][$Group] optional verifier unavailable: $Path"
            $script:SkipCount += 1
        }
        return
    }

    $script:RunCount += 1
    Write-Host "[RUN ][$Group] $EngelPy $Path"
    & $EngelPy $Path
    $exitCode = $LASTEXITCODE
    if ($exitCode -eq 0) {
        Write-Host "[PASS][$Group] $Path"
        $script:PassCount += 1
    } else {
        Write-Host "[FAIL][$Group] $Path exited $exitCode"
        $script:FailCount += 1
        $script:Failures.Add("$Group :: $Path exited $exitCode") | Out-Null
    }
}

function Invoke-Group {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][array]$Verifiers
    )

    Write-Host ""
    Write-Host "== $Name =="
    foreach ($verifier in $Verifiers) {
        if ($verifier -is [string]) {
            Invoke-PythonVerifier -Group $Name -Path $verifier -Required $true
        } else {
            Invoke-PythonVerifier -Group $Name -Path $verifier.Path -Required $verifier.Required
        }
    }
}

# (2026-07-28, issue engel_issue_dec7c33267bccab7) External-memory shelf,
# F:-era llama.cpp runtime, and WSL verifiers are ENVIRONMENT-DEPENDENT
# surfaces declared optional in memory\ENGEL_COMMANDS.md ("when present").
# When the environment is absent they SKIP with the reason; when it is
# present they run at full strictness. This is presence-gating, not
# retirement - the verifier files and their checks are unchanged.
$ExternalShelfRoots = @('E', 'F', 'G', 'I') | ForEach-Object { "${_}:\ENGEL_APP_MEMORY" } | Where-Object { Test-Path $_ }
$ExternalShelfPresent = @($ExternalShelfRoots).Count -gt 0
$WslPresent = $false
try {
    $null = & wsl.exe --status 2>$null
    $WslPresent = ($LASTEXITCODE -eq 0)
} catch { $WslPresent = $false }

function Invoke-EnvironmentGroup {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][array]$Verifiers,
        [Parameter(Mandatory = $true)][bool]$Present,
        [Parameter(Mandatory = $true)][string]$AbsentReason
    )
    Write-Host ""
    Write-Host "== $Name =="
    if (-not $Present) {
        foreach ($verifier in $Verifiers) {
            Write-Host "[SKIP][$Name] $verifier - $AbsentReason"
            $script:SkipCount += 1
        }
        return
    }
    foreach ($verifier in $Verifiers) {
        Invoke-PythonVerifier -Group $Name -Path $verifier -Required $true
    }
}

Write-Host "Engel Codex Verification"
Write-Host "Repository: $RepoRoot"
Write-Host "Mode: local verifier groups; no provider/network/browser/package/model runtime"
Write-Host ("External memory shelf: " + $(if ($ExternalShelfPresent) { "present ($($ExternalShelfRoots -join ', '))" } else { "absent (E/F/G/I ENGEL_APP_MEMORY roots not mounted)" }))
Write-Host ("WSL runtime: " + $(if ($WslPresent) { "present" } else { "absent" }))

Invoke-Group -Name "Core Safety Guards" -Verifiers @(
    "tools\verify_authority_hierarchy.py",
    "tools\verify_prompt_injection_guard.py",
    "tools\verify_untrusted_content_guard.py",
    @{ Path = "tools\verify_local_only_boundary_checker.py"; Required = $false }
)

Invoke-Group -Name "Documentation And Route Drift" -Verifiers @(
    "tools\verify_living_systems_documentation_drift.py",
    "tools\verify_route_metadata_contract.py",
    "tools\verify_engel_complete_name_path_reference_refactor.py",
    "tools\verify_engel_progress_dashboard.py",
    "tools\verify_engel_route_explorer_superswarm.py",
    "tools\verify_engel_ai_update_routes.py",
    "tools\verify_engel_ai_run_entry.py"
)

Invoke-EnvironmentGroup -Name "External Memory Shelf (optional surface)" -Present $ExternalShelfPresent `
    -AbsentReason "no ENGEL_APP_MEMORY shelf mounted; optional per ENGEL_COMMANDS.md" -Verifiers @(
    "tools\verify_engel_memory_archive_status.py",
    "tools\verify_engel_archive_shelf_manager.py",
    "tools\verify_engel_ai_connector_hub.py",
    "tools\verify_engel_account_connector.py",
    "tools\verify_engel_chat_export_intake.py",
    "tools\verify_engel_manual_model_intake_evaluator.py",
    "tools\verify_engel_memory_roots_storage_layout.py"
)

Invoke-Group -Name "Report-Only True Data Analytics" -Verifiers @(
    "tools\verify_engel_true_data_score_chart.py"
)

Invoke-Group -Name "System Integration And Continuity" -Verifiers @(
    "tools\verify_engel_system_integration_status.py",
    # CT246 server/controller merge records and launcher contract are release
    # surfaces; keep the static verifier in the normal local sweep.
    "tools\verify_engel_main_server_merge.py",
    "tools\verify_engel_ai_main_cluster_build_state.py",
    "tools\verify_engel_core_continuity_map.py",
    # Engel Graph & Loop Studio is a separate product with its own checkout
    # and release verifier.  Do not treat its companion verifier files as
    # Engel AI Main files (they intentionally are not present in this tree).
    "tools\verify_super_swarm_graphify_map.py",
    "tools\verify_super_swarm_antimalware_friendly_packaging.py"
)

Invoke-Group -Name "Learning, Fixing, And Memory Candidate Flow" -Verifiers @(
    "tools\verify_engel_learning_job_queue.py",
    "tools\verify_engel_self_learning_run_controller.py",
    "tools\verify_engel_candidate_learning_output_review.py",
    "tools\verify_engel_memory_candidate_inventory.py",
    "tools\verify_engel_candidate_set_approval.py",
    "tools\verify_engel_trusted_memory_target.py",
    "tools\verify_engel_approved_memory_promotion.py",
    "tools\verify_engel_code_companion.py",
    "tools\verify_engel_fix_candidate_queue.py",
    "tools\verify_engel_code_companion_fix_candidate_intake.py",
    "tools\verify_engel_code_companion_patch_plan_preview.py",
    "tools\verify_engel_code_companion_patch_bundle_draft.py",
    "tools\verify_engel_code_companion_patch_application_gate.py",
    "tools\verify_engel_code_companion_patch_apply_dry_run.py",
    "tools\verify_engel_code_companion_patch_apply_approval_receipt.py",
    "tools\verify_engel_code_companion_protected_patch_apply.py",
    "tools\verify_engel_code_companion_tiny_doc_patch_smoke.py",
    "tools\verify_engel_code_companion_review_surface.py",
    "tools\verify_engel_code_companion_patch_class_allowlist.py",
    "tools\verify_engel_code_companion_password_gate_integration.py",
    "tools\verify_engel_discord_identity_guard.py",
    "tools\verify_engel_discord_desktop_route_parity.py",
    # (2026-09-10) Chat OOM + Discord desk peer-storm hardening
    "tools\verify_engel_chat_memory_discipline.py",
    "tools\verify_engel_discord_peer_storm_guard.py",
    # (2026-08-01) Discord GIF choices must match the ask and captions must not assert
    # a match nobody checked -- the "dental orthodontics"/"happy august" incident
    "tools\verify_engel_discord_gif_relevance.py",
    # (2026-08-14) Chat needs a comparison point: the compare tool's payload must stay
    # chat_only/training-opt-out and its llama-cli transcript parsing must stay honest.
    "tools\verify_engel_chat_compare.py",
    "tools\verify_engel_training_capture_filter.py",
    "tools\verify_engel_model_promotion_gate.py",
    "tools\verify_engel_self_upgrade_system.py",
    "tools\verify_engel_runtime_path_normalizer.py",
    "tools\verify_engel_codebase_inventory.py",
    "tools\verify_engel_source_sync_rosetta.py",
    "tools\verify_engel_patch_permission_matrix.py",
    "tools\verify_engel_self_model_runtime.py",
    "tools\verify_engel_shell_bridge_registry.py",
    "tools\verify_engel_provider_capability_map.py",
    "tools\verify_engel_provider_routing_capability_gate.py",
    "tools\verify_engel_local_llm_fast_fail.py",
    "tools\verify_engel_chat_failure_corpus_builder.py",
    "tools\verify_engel_codex_workbench_ingest.py",
    "tools\verify_engel_whole_system_incomplete_audit.py"
)

# (2026-07-28) Chat/build/self-upgrade surfaces added in the 20260727-28
# sessions; registered here so the sweep keeps covering them.
Invoke-Group -Name "Chat Build Lane And Backlog Driver" -Verifiers @(
    "tools\verify_engel_build_lane_usable_gate.py",
    "tools\verify_engel_semantic_repair_scope.py",
    "tools\verify_engel_backlog_driver.py",
    "tools\verify_engel_provider_picker.py",
    "tools\verify_engel_incomplete_input_gate_scope.py",
    "tools\verify_engel_ui_surface_integrity.py",
    # (2026-08-03) was never registered, so nobody saw it go red: it pinned the old
    # `_run_fleet_dispatch(prompt, ...)` literal and failed once that argument was
    # correctly narrowed to operator_prompt. Assertion now matches the call by name.
    "tools\verify_engel_conical_build_orchestration.py",
    "tools\verify_engel_underspecified_app_build_gates.py",
    "tools\verify_engel_sub_engel_false_disconnect.py",
    "tools\verify_engel_ui_retry_not_backend.py",
    "tools\verify_engel_chat_completion_communication.py",
    "tools\verify_engel_local_llm_build_first.py",
    # Graph & Loop Studio is a separately installed companion application. Run
    # this integration check when its checkout is present, but do not make a
    # Main-only release fail because the companion is absent.
    @{ Path = "tools\verify_engel_graph_studio_single_window.py"; Required = $false }
)

# (2026-08-26) Engel AI Main release lanes.  These are deliberately explicit:
# the standard sweep must catch a stale/broken CLI package or API contract
# instead of silently treating those new verifiers as an unregistered audit.
Invoke-Group -Name "Engel AI Main CLI/API Release" -Verifiers @(
    "tools\verify_engel_ai_main_api.py",
    "tools\verify_engel_ai_main_cli_api_share.py"
)

# The Flutter bundle verifier is kept separate from the CLI/API checks because
# it validates a different artifact (the canonical Windows Release ZIP).
Invoke-Group -Name "Engel AI Main Flutter Release Package" -Verifiers @(
    "tools\verify_engel_ai_main_flutter_release.py"
)

# (2026-07-31) Governor decision plane, lane routing, and memory hygiene
# (docs/ENGEL_GOVERNOR_DESIGN.md). These verifiers are listed explicitly because the
# sweep does not auto-discover new files -- an unregistered verifier is a gate that
# silently never runs.
Invoke-Group -Name "Governor Decision Plane" -Verifiers @(
    "tools\verify_engel_governor.py",
    # HIPL/MIPL semantic bridge and native Agent Kernel: compact packet
    # integrity, non-authorizing handoff, result return, and dispatch proof.
    "tools\verify_engel_mipl.py",
    # (2026-08-08) AGENT/SKILL/TASK/ASSIGN work packets bridge the Meeting Room
    # skill roster to authored agents without granting or running them.
    "tools\verify_engel_mipl_agent_work.py",
    "tools\verify_engel_lifted_intent.py",
    "tools\verify_engel_agent_kernel.py",
    "tools\verify_engel_grok_bot.py",
    "tools\verify_engel_icm_architect.py",
    "tools\verify_wiki_one.py",
    # conceptual math must reach a reasoning lane, not the default 7B, and Engel-ops
    # phrasing must not be hijacked onto a CPU reasoner
    "tools\verify_engel_reasoning_routing.py",
    # training turns stay persisted (the corpus + the DONE gate need them) but are
    # never re-injected as chat context -- this is the echo loop
    "tools\verify_engel_training_turn_context_exclusion.py",
    # the WRITE side of the same contract: persister stamps training_turn/echo/
    # context_eligible and substitutes the base ask for the wrapper + contract
    "tools\verify_engel_memory_hygiene.py",
    # SLM serving runtime: roster artifacts serve ONLY behind their training
    # gates, never block a turn, fail open; service wire-in asserted
    "tools\verify_engel_local_encoder.py",
    "tools\verify_engel_slm_runtime.py",
    # Canonical six-head roster: producer/runtime/UI parity, bounded authority,
    # non-leaking Governor and Code Forge datasets, safe artifact mirroring
    "tools\verify_engel_slm_roster.py",
    # (2026-08-05) the two MANDATORY roster gates themselves -- beats-majority-baseline
    # and not-leaking -- plus artifact/receipt integrity. It was never registered, so
    # nobody saw it go red: it pinned the CT-shaped models-active/slm path that does not
    # exist on ROG, where the roster lives in runtime/slm_models. Card 8 of the
    # capabilities curriculum cites this file as the proof of those gates.
    "tools\verify_engel_slm.py",
    # Candidate selection is a separate release boundary from artifact serving: canonical
    # prompt groups may not cross the holdout, incumbents use their own vectorizers, and a
    # below-gate or incomparable candidate may never overwrite a valid serving head.
    "tools\verify_engel_slm_selection.py",
    # Training writes only to a run-specific candidate. The exact hash-bound roster is
    # verified there, downloaded to a sibling directory, and promoted atomically with a
    # unique rollback backup; partial or stale reports never touch the live mirror.
    "tools\verify_engel_slm_promotion_lifecycle.py",
    # per-discipline prompts/contracts/eligibility for the training curricula
    "tools\verify_engel_training_domain_discipline.py",
    # (2026-08-01) prompt training actually trains: the pack contract and the four
    # independent readers of it (runner, SFT builder, SLM builder, cycle orchestrator)
    "tools\verify_engel_real_training.py",
    # Every newly written pack must carry a no-overwrite, read-only receipt binding exact
    # pack/session bytes, schedule, canonical curriculum, run id, and writer source.
    "tools\verify_engel_prompt_pack_writer_receipt.py",
    # The desktop watchdog and remote orchestrator must share one bounded runtime
    # contract; otherwise a healthy selected trainer is killed by an arbitrary UI timer.
    "tools\verify_engel_training_cycle_runtime_contract.py",
    # Prompt scheduling is a separate causal gate: exact displayed topic consent,
    # resume cadence, lifecycle/guard ownership, and generated-asset identity must
    # remain intact before the broader cross-product window matrix runs.
    "tools\verify_engel_training_schedule.py",
    # Scheduled practice must be genuinely new across immutable pack history. Replays
    # are refused before UI, GPU, guard, or prompt-delivery side effects, and Prepare
    # Files may select only whole reviewed cards whose ten prompts are all unused.
    "tools\verify_engel_prompt_novelty.py",
    "tools\verify_engel_prompt_pack_history_migration.py",
    # The five canonical picker entries must each resolve to eight substantive,
    # artifact/evidence-bound cycles: 400 prompts total, mutually distinct and unused
    # across immutable pack/reservation history. Math also binds 80 exact decidable
    # questions instead of allowing the model to invent the problem it will be graded on.
    "tools\verify_engel_curriculum_renewal.py",
    # Generated Construction/Communication cards enter canonical slots only through an
    # explicit digest confirmation and an immutable receipt binding the adopted bytes.
    "tools\verify_engel_curriculum_adoption.py",
    "tools\verify_engel_generated_aec_sync_integrity.py",
    # Release readiness is one exact-five contract: current canonical templates, immutable
    # novelty history, bound source bytes, verified construction evidence, and five
    # executable 8-hour launcher controls must all agree.
    "tools\verify_engel_all_five_training_readiness.py",
    # Model training may consume only one current immutable 80-row pack from each of those
    # five exact curricula, with every operator-selected model lane represented in all five.
    "tools\verify_engel_five_curriculum_model_handoff.py",
    # Hash-verified transfer is insufficient if a stale CT builder reads only part of the
    # roster. Both model lanes must echo the exact physical/logical and per-target counts;
    # a 1-of-400 receipt is a hard refusal before either trainer starts.
    "tools\verify_engel_exact_remote_consumption.py",
    # A pack is immutable evidence, not admission authority. Both downstream builders
    # must independently reject action lanes, malformed schemas, unsupported AEC claims,
    # duplicate-label conflicts, and the old longest-reply-wins quality regression.
    "tools\verify_engel_training_pack_downstream_safety.py",
    # CT246 must receive the reviewed, offline, negative-aware trainer from this repo;
    # an untracked scratchpad copy is not an auditable training source of truth.
    "tools\verify_engel_ct246_canonical_lora_trainer.py",
    # A canary authorizes nothing unless immutable proof/model hashes survive the run;
    # deployment must consume the exact minted contract, conversion receipt, and GGUF.
    "tools\verify_engel_lora_promotion_provenance.py",
    # The converter is the missing producer between canary and deploy: it must preserve
    # the canaried tree and emit the fully bound immutable v2 conversion receipt.
    "tools\verify_engel_ct246_gguf_conversion.py",
    # (2026-08-06) the training loop's missing half. Until now the system trained but
    # never measured CAPABILITY (LoRA val_loss is in-distribution likelihood; SLM
    # macro_f1 is scored on a split of its own corpus), and never fed its FAILURES back
    # into the syllabus. These two gate the held-out capability suite and the
    # weakness->curriculum drafter -- the drafter writes training material, which makes
    # it the easiest place in the system to reintroduce a fabricated citation.
    # (2026-08-06) Math is the ONE discipline here where correctness is decidable, and the
    # gate was grading form only: it admitted x=4 for 2x+1=7, d/dx x^2 = 3x, and
    # integral 2x dx = x^3, because each carried an internally-consistent Check. This gates
    # the CAS correctness check that now rejects them -- in both directions, since a false
    # refutation deletes good training data and teaches against a correct method.
    "tools\verify_engel_math_answer_verifier.py",
    # (2026-08-06) Math problems that carry their own ground truth, so admission is a
    # DECISION rather than an inference. Gated in both directions: a wrong answer must lose
    # its training row, and a correct answer written in any reasonable form must survive --
    # throwing away correct mathematics trains the model against its own correct method.
    # Also gates the honesty property: a proof has no decidable answer and must be recorded
    # as form-graded, never stamped "exactly verified".
    "tools\verify_engel_math_problems.py",
    # (2026-08-07) The training gate refuses to LEARN from refuted maths; the serving path
    # now records the same CAS verdict on every chat receipt (advisory, fail-open,
    # kill-switched via ENGEL_MATH_SERVING_VERDICT_ENABLED, ct_math_lane skipped). Gates
    # both the service wiring order and the verdict behavior incl. LaTeX and latency caps.
    "tools\verify_engel_math_serving_verdict.py",
    "tools\verify_engel_grover_lane.py",
    "tools\verify_engel_next_stage_merge.py",
    "tools\verify_engel_hermes_root_catalog.py",
    "tools\verify_engel_sub_engel_catalog_addon.py",
    "tools\verify_engel_models_brains_catalog.py",
    "tools\verify_engel_live_status_before_provider.py",
    # (2026-08-07) Code is EXECUTED, not admired: programming answers are verified by
    # running their own assertions through the Forge-gated sandbox (refute only what
    # execution proves broken), wired into the engineering admission gate and a held-out
    # code_executes capability skill. Includes the canary that caught this gate's own
    # first execution hole (advisory-vs-fatal misread).
    "tools\verify_engel_code_answer_verifier.py",
    # (2026-08-08) The aec discipline's ground truth: operator-supplied building-code
    # PDFs -> page corpus + section index; explicitly cited sections are checked and a
    # provably fabricated citation loses its training row. Synthetic-PDF fixtures prove
    # both directions without the real volumes.
    "tools\verify_engel_construction_corpus.py",
    # The verified construction corpus is transported as one exact, run-scoped bundle.
    # Partial copies, stale shared roots, extra remote files, and builder fallback to a
    # different corpus must all fail before dataset or model work begins.
    "tools\verify_engel_real_training_corpus_transport.py",
    "tools\verify_engel_capability_eval.py",
    "tools\verify_engel_weakness_curriculum.py",
    # (2026-08-06) Engel can now AUTHOR an agent and give it standing direction. The
    # risky part is what the record allows, so the gate is written against the refusals:
    # no self-granted authority to act, no undeclared capability, no silent rewrite of a
    # direction (a run is diagnosed by what it was told at the time).
    "tools\verify_engel_agent_author.py",
    # (2026-08-06) multi-turn agents that iterate toward a goal. The whole safety of the
    # loop is one property -- the agent's claim of completion must never end the run --
    # so the central fixture is an agent that announces success every turn while the
    # state never moves. It must stall out, not succeed.
    "tools\verify_engel_agent_goal_loop.py",
    # (2026-08-06) the ONLY component on the agent surface that can change the workspace.
    # Written against the refusals: the realistic failure is not an agent wrecking the
    # repo, it is an agent writing to memory/agents to set its own allow_actions, or to
    # tools/ to blunt the gate that would have caught it. Both are denied even for a
    # fully granted agent.
    "tools\verify_engel_agent_action_executor.py",
    # (2026-08-03) a turn that declares interactive=false has nobody to answer a
    # confirm gate: the action planner must not strand training runs on a pending
    # plan (one such prompt burned 781s and failed a 5-hour run at 38/50)
    "tools\verify_engel_non_interactive_action_gate.py",
    # (2026-08-05) the PID liveness probe is the single source of truth for "is this
    # worker alive"; it had NO verifier, and the training card that honestly said so
    # was answered by the model INVENTING this file's name in 5 of 10 replies. It now
    # exists and is gated: live/dead/access-denied/garbage, and the probe's code must
    # stay free of child-process calls (a tasklist child raises a real console window).
    "tools\verify_engel_process_liveness.py",
    # (2026-08-05) the two curriculum cards that reproducibly INVENTED a verifier now have
    # real ones. Recon: the authorized-use contract on the dual-use nmap surface (8 NSE
    # cards, 7 evasion flags, own-LAN scoping, D:-only binary). Verb intent gate: proves a
    # real training order still routes while discussion of training never routes and never
    # LAUNCHES a runner -- writing it caught a live defect where six plain questions
    # ("how do I read the training report") passed the launch gate on a proximity window.
    "tools\verify_engel_nmap_recon_surface.py",
    "tools\verify_engel_verb_intent_gate.py",
    # CT246 RAG is executable, not a decorative lab: all ten strategies and
    # the loopback-only HTTP bridge must preserve their local/read-only gates.
    "tools\verify_engel_rag_runtime.py",
    "tools\verify_engel_rag_http_bridge.py",
    "tools\verify_engel_ai_systems_runtime.py",
    # Training window matrix: every curriculum x 1-8 hours x level x hourly count x
    # SLM/LLM target selection builds a valid schedule and reaches the guarded trainer.
    "tools\verify_engel_training_window_matrix.py",
    # UI navigation: `_sectionIndexById` silently selects Home for an unknown route id,
    # so a mistyped navigation target is invisible at runtime and untestable by tapping.
    # Two "Models" buttons pointed at 'models' -- a label, never an id -- and quietly
    # opened Home. This proves every navigation literal resolves to a page that renders.
    "tools\verify_engel_ui_navigation_targets.py",
    # EngelScript: Engel's own plan language -- strict grammar, hard caps,
    # registry-flag safety before execution, receipts, router wire-in
    "tools\verify_engel_script.py",
    # Capability index: Engel finding its own 517 routes from intent --
    # recall on real goals, determinism, optional rerank, safe phrasebook
    "tools\verify_engel_capability_index.py"
)

Invoke-Group -Name "Library, Model, And Runtime Boundaries" -Verifiers @(
    @{ Path = "tools\verify_engel_llm_and_python_library_intake_plan.py"; Required = $false },
    "tools\verify_engel_model_library_plan.py",
    "tools\verify_engel_non_model_library_plan.py",
    "tools\verify_engel_storage_location_registry.py",
    "tools\verify_engel_trusted_vault_storage.py",
    "tools\verify_engel_memory_storage_exclusion.py",
    "tools\verify_engel_ai_runtime_readiness.py",
    "tools\verify_engel_ai_manual_model_file_intake.py",
    "tools\verify_engel_ai_model_review_approval.py",
    "tools\verify_engel_ai_offline_runtime_dry_run.py",
    "tools\verify_engel_ai_llama_cpp_compatibility_matrix.py",
     "tools\verify_engel_ai_llama_cpp_runtime_swap_plan.py",
     "tools\verify_engel_ai_llama_cpp_runtime_candidate_validation.py",
     "tools\verify_engel_ai_runtime_candidate_failure_diagnosis.py",
     "tools\verify_engel_ai_runtime_candidate_validation_replay.py",
     "tools\verify_engel_main_rust_local_chat_bridge.py",
     "tools\verify_engel_main_rust_connectors_bridge.py",
     "tools\verify_engel_main_rust_research_bridge.py",
     "tools\verify_engel_main_rust_ui_shell_bridge.py",
    "tools\verify_engel_phase_b_native_invokes.py"
)

Invoke-EnvironmentGroup -Name "External Fast-Shelf Local Runtime (optional surface)" -Present $ExternalShelfPresent `
    -AbsentReason "F:-era llama.cpp candidate runtimes live on the external fast shelf, which is not mounted" -Verifiers @(
    "tools\verify_engel_ai_local_runtime_path_config.py",
    "tools\verify_engel_ai_no_generation_load_check.py",
    "tools\verify_engel_ai_runtime_candidate_alt_command_style.py",
    "tools\verify_engel_ai_llama_cpp_runtime_swap_approval.py",
    "tools\verify_engel_ai_first_local_response_smoke.py",
    "tools\verify_engel_ai_first_local_response_smoke_exit_fix.py",
    "tools\verify_engel_ai_first_response_output_filter_tuning.py"
)

Invoke-EnvironmentGroup -Name "WSL Runtime (optional surface)" -Present $WslPresent `
    -AbsentReason "WSL is not installed on this host" -Verifiers @(
    "tools\verify_engel_wsl_ubuntu_runtime_dependency.py",
    "tools\verify_engel_wsl_bridge.py"
)

Invoke-Group -Name "Password, Protected Actions, And Remote Boundaries" -Verifiers @(
    @{ Path = "tools\verify_engel_global_password_gate.py"; Required = $false },
    @{ Path = "tools\verify_engel_protected_action_registry.py"; Required = $false },
    @{ Path = "tools\verify_communication_queen_contract.py"; Required = $false },
    @{ Path = "tools\verify_trusted_remote_queen_protocol.py"; Required = $false },
    @{ Path = "tools\verify_engel_outside_ai_boundary.py"; Required = $false },
    # verify_engel_hermes_rejection.py was retired from the active suite on
    # 2026-05-20 per Josh's explicit authority decision: Hermes is no longer
    # blocked. The verifier file stays in tools/ as audit history; see
    # memory/ENGEL_HERMES_POLICY_CHANGE_V1.{json,md} and
    # reports/codex_bridge/ENGEL_HERMES_POLICY_CHANGE_V1.md for the record.
    # "tools\verify_engel_hermes_rejection.py",
    "tools\verify_android_remote_worker_contract.py",
    "tools\verify_engel_multi_android_remote_workers.py",
    "tools\verify_engel_remote_worker_job_assignment.py",
    "tools\verify_engel_remote_worker_result_intake.py",
    "tools\verify_engel_remote_worker_lan_pairing.py",
    "tools\verify_engel_remote_worker_auto_assignment.py",
    "tools\verify_engel_communication_queen_assignment_producer.py",
    "tools\verify_engel_remote_worker_link_manager.py",
    "tools\verify_engel_ui_system_actions.py",
    "tools\verify_engel_android_worker_prompt_signals.py",
    "tools\verify_engel_remote_worker_phase7_smoke.py",
    "tools\verify_engel_remote_worker_phase8_android_lan_smoke.py",
    "tools\verify_engel_remote_worker_claim_lock.py",
    "tools\verify_engel_ct_assignment_queue_consumer.py",
    "tools\verify_sub_engel_controller_client.py",
    "tools\verify_engel_sub_engel_training_safe_task_executor.py",
    "tools\verify_engel_sub_engel_session_renewal.py",
    "tools\verify_engel_meeting_room_live_device_overlay.py",
    "tools\verify_engel_flutter_ui_submission_retry.py",
    "tools\verify_engel_first_real_android_worker_job_packet.py",
    "tools\verify_android_worker_alpha_adb_setup.py",
    "tools\verify_android_worker_alpha_phone_button_ui.py",
    "tools\verify_android_worker_alpha_finish_setup.py",
    # verify_android_worker_alpha_rejected_result_diagnosis.py was a one-time
    # diagnostic for the older rejected smoke run. Alpha now completes cleanly
    # on ANDROID_WORKER_ALPHA (see memory/ENGEL_PHONE_DEVICE_MAP_V1), so the rejected
    # status no longer exists. The verifier file stays in the repo as audit
    # trail but is no longer in the active suite.
    "tools\verify_android_worker_beta_package_parity.py",
    "tools\verify_android_worker_beta_finish_setup.py"
)

Write-Host ""
Write-Host "== Engel Codex Verification Summary =="
Write-Host "Run: $script:RunCount"
Write-Host "Passed: $script:PassCount"
Write-Host "Skipped optional: $script:SkipCount"
Write-Host "Failed: $script:FailCount"

if ($script:FailCount -gt 0) {
    Write-Host ""
    Write-Host "Failures:"
    foreach ($failure in $script:Failures) {
        Write-Host "- $failure"
    }
    exit 1
}

Write-Host "ENGEL_CODEX_VERIFY_PASS"
exit 0
