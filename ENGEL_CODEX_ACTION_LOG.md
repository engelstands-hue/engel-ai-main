# Engel Codex Action Log

## Documentation Files Created Or Updated

- `ENGEL_SYSTEM_MAP.md`
- `ENGEL_CLUSTER_TOPOLOGY.md`
- `ENGEL_DEVICE_REGISTRY.md`
- `ENGEL_STORAGE_MAP.md`
- `ENGEL_MIGRATION_PLAN.md`
- `ENGEL_HEALTH_CHECKS.md`
- `ENGEL_STARTUP_POLICY.md`
- `ENGEL_SAFETY_RULES.md`
- `ENGEL_OPEN_TASKS.md`
- `ENGEL_AGENTIC_ROLES.md`
- `ENGEL_BODY_PARTS.md`
- `ENGEL_CODEX_ACTION_LOG.md`
- `ENGEL_FILE_MANIFEST.md`

## Read-Only Inspection Performed

- Read user-provided documentation packet.
- Read `AGENTS.md`.
- Read `CODEX_HANDOFF.md`.
- Read `CODEX_JOB.md`.
- Read `ENGEL_MODULE_MANIFEST.md`.
- Listed top-level workspace folders/files.
- Generated a path/name-based file manifest under `D:\b.WorkSpace\Engel App`.
- Secret-like folders were not expanded or content-inspected.

## Assumptions

- `D:\b.WorkSpace\Engel App` is the active ROG-side source workspace.
- `engel-spine-01` and CT 246 infrastructure values are accepted as confirmed from Josh's packet.
- The system is documented as one conical agentic system with Josh as final authority and ROG as Queen orchestrator.
- Unknown does not mean unused; it means pending review.

## Unknowns / Pending Review

- Exact current connected-device list beyond known/pending phones and future workers.
- Current beta phone pairing state.
- Exact active model set to promote into `/opt/engel/models-active`.
- Which build/cache/vendor folders should migrate versus regenerate on CT.
- Second iSCSI path / multipath.
- Final approved migration window from ROG workspace to CT app path.

## Not Done

- No migration executed.
- No service startup executed.
- No Proxmox commands executed.
- No PowerVault/iSCSI/multipath commands executed.
- No storage configuration changed.
- No files moved, renamed, deleted, or reorganized.
- No deployment commands executed.
- No autonomous worker swarm, recursive loop, or heavy background task started.
- No secret contents inspected.

## Safety Result

This action was documentation-only. It created local documentation and a local manifest. It did not change server infrastructure or runtime state.

## Manifest Note

- `ENGEL_FILE_MANIFEST.md` was finalized as a compact operational manifest.
- A literal every-file manifest was not retained because the workspace contains more than 195,000 files and recursive backup/cache/vendor/build/runtime trees would produce an unusable multi-hundred-MB document.
- Nested files inherit the closest container classification unless a more specific rule applies.
- Full per-file export should be generated only if Josh explicitly requests it and should be written to a vault transfer/report location, not treated as active runtime state.

## 2026-07-27 CT246 And Sub-Engel Repair

- Confirmed Sub-Engel already authorized `main.shell` and `disk.control`.
- Replaced the Sub node's blocking `HTTPServer` with `ThreadingHTTPServer`.
- Removed stale duplicate Sub node-agent processes without stopping the
  watchdog-managed listener.
- Proved concurrent shell and disk control through CT246 while a six-second
  shell request was active.
- Added long-request UI heartbeats, local build retries, structured JSON
  project parsing, path-collision normalization, atomic workspace writes,
  strict local-only route enforcement, and failed-candidate rollback.
- Ran two real requests through the visible Flutter Engel AI Main chat.
- Proved fresh Alpha, Beta, Gamma, and Sub-Engel returns at `4/4`.
- Restored the newest verified Conical Proof Viewer workspace after a local
  candidate failed; all four restored tests pass.
- Recorded the verified guardrails in CT246 R.E.P.S. event
  `reps_event_8f504a08f6682ebb`.
- Deployed with rollback root
  `/opt/engel/run/self_update/rollback/server_only_transport_20260727T221832Z`.
- Detailed report:
  `reports/codex_bridge/ENGEL_SUB_CONTROL_AND_VISIBLE_LOCAL_BUILD_REPAIR_20260727.md`.
- PowerVault, Google Drive, and external laptop drives were not used.
- Reproduced a later Sub control failure as `401 invalid bearer token`.
- Found two concurrent ROG auto-pair watchers and a stale ROG session while
  CT246 retained the valid authoritative paired session.
- Routed ROG `main.shell` and `disk.control` calls through CT246's authenticated
  Sub session without exposing or copying the bearer to ROG.
- Added a single-instance watcher lock; a duplicate launch exited and the live
  watcher count remained one.
- Re-proved concurrent control through the CT246 relay: six-second shell
  request passed and disk status returned in `0.289` seconds.
- Completed the visible strict-local Flutter build proof with all four workers,
  eight passing tests, CT persistent memory, and package SHA-256
  `6c523fe8a7589d2d72204be54a0dc78f5d5f317a72953e003bf39abb5611060f`.
- Fixed the UI proof race so PASS now requires Flutter's own fresh
  `worker_result_received` event before completion capture.
- Deployed the CT246 control artifacts with rollback root
  `/opt/engel/run/self_update/rollback/rog_sub_control_relay_20260727T224200Z`.
- Recorded CT246 R.E.P.S. event `reps_event_44e6f560a4e2c771`.
- Disabled obsolete ROG-side session renewal and installed CT246
  `engel-sub-session-renewal.timer`; its first check passed with one healthy
  Sub session and no secret material in the report.

## 2026-07-27 Prompt/Patch Provenance And UI Review

- Added the append-locked, hash-chained prompt-to-patch provenance ledger and
  immutable per-entry receipts.
- Wired provenance into the governed cycle before quorum.
- Added a desktop-only, review-without-apply chat route; Discord cannot invoke
  this owner review lane.
- Ran the lane through the open Flutter Engel AI Main chat using CT246's local
  Qwen3 sparse-MoE model, all three phones, and `DESKTOP-UE5A6GG`.
- Proved `4/4` worker returns, CT persistent chat memory, R.E.P.S. recording,
  no provider call, and no source mutation.
- Fixed the review-only quorum boundary while preserving execute-mode approval
  enforcement.
- Preserved 37 historical verifier-fixture entries in the append-only ledger,
  isolated future fixtures, and retained strict evidence checks for the two
  production entries.
- Re-ran the CT cycle verifier and proved the production ledger remained at
  39 lines before and after.
- Re-proved Sub shell and disk control through CT246: disk returned in `0.291`
  seconds while a six-second shell command was active.
- Latest rollback root:
  `/opt/engel/run/self_update/rollback/provenance_fixture_isolation_20260727T232530Z`.
- Detailed report:
  `reports/codex_bridge/ENGEL_PROMPT_PATCH_PROVENANCE_AND_UI_REVIEW_PROOF_20260727.md`.
- PowerVault, Google Drive, external E/F/G drives, and `DESKTOP-FIB17O7` were
  not used.
