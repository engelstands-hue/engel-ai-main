# CODEX_HANDOFF.md - Engel App Current Handoff

Status: CURRENT / MEETING_ROOM_V1_BUILT / ANDROID_DISPATCH_LIVE / SMOKE_CLEAN

Date: 2026-05-25

## Active Workspace

```text
D:\b.WorkSpace\Engel App
```

Historical reports may mention old workspace roots; the active workspace root is `D:\b.WorkSpace\Engel App`. Do not follow stale handoff packets pointing to another root or a completed task.

## Wiki One (whole Engel AI Main)

Read `wiki/ONE.md` before landing CODE. Update `wiki/ONE.md` and `wiki/organs.json` in the same job when an organ, talks-to, source, or duty changes. Stamp Journal after CODE. Contract: `wiki/CONTRACT.md`. Phrases: `wiki one`, `wiki journal`, `update wiki one`.

---

## Current Route State

**Route count: 490** (Architect Agent + Wave 4)

Smoke test result (full 490-route run, 2026-05-25): **445 tested / 45 skipped (slow build routes) / 0 failures / 149s total**

Architect routes (31): all resolve clean. Meeting Room routes (8 `engel.meeting_room.*` + new Qt window): all resolve clean.

Run smoke test:

```powershell
cd "D:\b.WorkSpace\Engel App"
python _route_smoke.py
```

Route progression: 231 → 289 → 298 → 355 → 373 → 379 → 408 → 434 → 459 → 490

---

## Agent Meeting Room V1 (2026-05-25) — `engel_agent_meeting_room.py`

A Qt window for assembling agents + skills, attaching them to equipment,
selecting per-agent bridges, and dispatching jobs.

**Launch:** Desktop V2 button `⌬ Meeting Room`, chat phrase `meeting room` / `open meeting room` / `where is the meeting room`, or direct: `python engel_agent_meeting_room.py`

**Surfaces:**

- 10 agent types, 9 skill types, 4 equipment targets
- 11 per-agent bridges: None / Codex / Claude / Hermes-Agent / Cursor / GStack / Jarvis / HermesAgent (Nous) / AirLLM / LFM2 / Custom
- Chat panel with HTML rendering, auto-scroll, color-coded roles
- Send Job dispatcher:
  - **Local Engel AI** → chat record only
  - **Android App Worker** → REAL dispatch via `engel_adb_worker_manager.render_adb_create_job(payload)` (same function the `create android job` router phrase invokes)
  - **Sub-Engel OS Worker** → PREVIEW ONLY via `engel_remote_worker_job_assignment.preview_assignment()` — stages input under `runtime/meeting_room/sub_engel_inputs/`, no remote control
- Bottom-bar status probes real ADB device count via `engel_adb_worker_manager.render_adb_workers_status`
- Banner-style UX feedback for "select participant first" / "type name first"
- State persists to `runtime/meeting_room/room_state.json`; exports to `reports/meeting_rooms/ROOM-YYYYMMDD-HHMMSS.md`

**Files created:**

- `engel_agent_meeting_room.py` — Qt window
- `tools/verify_engel_agent_meeting_room.py` — 8-check AST-aware verifier
- `memory/ENGEL_AGENT_MEETING_ROOM_CONTRACT_V1.md` — safety contract
- `reports/codex_bridge/ENGEL_AGENT_MEETING_ROOM_BUILD.md` — build report
- `runtime/meeting_room/`, `runtime/agent_bridge/`, `reports/meeting_rooms/`

**Files modified:**

- `engel_desktop_v2.py` — `⌬ Meeting Room` button, chat-phrase intercept (`meeting room` / `where is the meeting room` etc. open the window locally without touching the provider bridge)
- `engel_agent_bridge.py` — no longer raises `RuntimeError` at import. `AGENT_ROOT: Path | None` is resolved from candidate paths (sibling file, sibling exe, `runtime/agent_bridge/engel_agent_main`, hard-coded install). Exposes `bridge_available()` + `bridge_missing_reason()`. Fixes the `C:\Users\…\Temp\_MEI*\engel_agent_main missing` chat error.

**Verifiers run:**

- `verify_engel_agent_meeting_room.py` — **PASS 8/8**
- `verify_engel_outside_ai_boundary.py` — PASS
- `verify_prompt_injection_guard.py` — PASS
- `verify_authority_hierarchy.py` — PASS
- `scripts/codex_verify.ps1` — **PASS 90/90** (`ENGEL_CODEX_VERIFY_PASS`)
- Full route smoke — **0 failures**, 445/445 tested

---

## Android Worker Status (live ADB devices, 2026-05-25)

**Each worker is a separate, independent process — even when the role name
is the same across phones.** Dispatching to "alpha" without scoping the
serial dispatches to *both* alpha workers (one per phone). The Meeting
Room's Send Job currently does not pick a device serial; it relies on
the worker name. A device-serial picker is on the queue.

| Slot | Model | Serial | Workers (each independent) |
|---|---|---|---|
| 1 | **Moto G Power 2025 (8GB)** | `ANDROID_WORKER_ALPHA` | `android_worker_alpha` ← own queue · `android_worker_beta` ← own queue |
| 2 | **Moto G Fast (3GB)** | `ANDROID_WORKER_BETA` | `android_worker_alpha` ← own queue (different from phone 1's alpha) |

ADB path: `C:\Users\ziese\AppData\Local\Android\Sdk\platform-tools\adb.exe`

**Routes for ADB worker control** (all approved, gated by `engel_adb_worker_manager`):

- `engel.android_workers.status` — list devices + queues (alias: `android workers status`)
- `engel.android_workers.jobs` — full job dashboard
- `engel.android_workers.create_job` — create a pending job (payload: `worker_id|job_type|title|instructions`)
- `engel.android_workers.push_jobs` — push pending jobs from PC to phones
- `engel.android_workers.pull_results` — pull completed results back from phones
- `engel.android_workers.latest_result` — read latest result content
- `engel.android_workers.provision` — provision a new worker on a device

**Pending WiFi work:** ADB-over-WiFi (`adb tcpip 5555` + `adb connect <ip>:5555`) is not yet wired. The LAN pairing server (`engel_remote_worker_lan_pairing.py`, port 8765) exists as a separate path for the standalone Android worker app. User asked to enable WiFi connectivity — proposed approach is to add a small `render_adb_wifi_connect(payload)` to `engel_adb_worker_manager.py` plus a "Connect via WiFi" button in the Meeting Room. Not yet implemented.

---

## Integrated Module Waves

### Wave 1 — 12 original modules (pre-2026-05-24)

| Folder | Upstream | Route prefix |
|---|---|---|
| `engel_agent_main/` | hermes-agent | `engel.engel_agent.*` |
| `engel3d_office_main/` | Claw3D | `engel.engel3d.*` |
| `engelsandbox_main/` | CubeSandbox | `engel.engel_sandbox.*` |
| `engelcode_main/` | jcode | `engel.engelcode.*` |
| `engel_main/` | openhuman | `engel.engel_main.*` |
| `engel_lan_main/` | localsend | `engel.engel_lan.*` |
| `engel_humanizer_main/` | humanizer | `engel.engel_humanizer.*` |
| `engel_native_agent_main/` | CodexAgent | `engel.native_agent.*` |
| `engel_ide_companion_main/` | AI-ASSISTANT-CURSOR | `engel.ide.*` |
| `engel_evolution_lab_main/` | darwinian_evolver | `engel.evolution_lab.*` |
| `engel_knowledge_graph_main/` | graphify-7 | `engel.knowledge_graph.*` |
| `engel_evolution_engine_main/` | evolver | `engel.evolution_engine.*` |

### Wave 2 — 10 modules (2026-05-24)

| Folder | Upstream | Route prefix |
|---|---|---|
| `engel_cli_anything_main/` | CLI-Anything | `engel.cli_anything.*` |
| `engel_git_nexus_main/` | GitNexus | `engel.git_nexus.*` |
| `engel_octogent_main/` | octogent | `engel.octogent.*` |
| `engel_open_agents_main/` | open-agents | `engel.open_agents.*` |
| `engel_airllm_main/` | AirLLM | `engel.airllm.*` |
| `engel_jarvis_main/` | OpenJarvis | `engel.jarvis.*` |
| `engel_chat_ui_main/` | agent-chat-ui | `engel.chat_ui.*` |
| `engel_ai_gallery_main/` | ai-dev-gallery | `engel.ai_gallery.*` |
| `engel_cluster_main/` | cluster | `engel.cluster.*` |
| `engel_knowledge_graph_v2_main/` | graphify-8 | `engel.kg_v2.*` |

Also added: ADB Android worker routes, LAN pairing routes, Agent Meeting Room (8 routes: `engel.meeting_room.*`), Desktop V2 GUI (`engel_desktop_v2.py`).

Runner: `engel_new_tools_runner.py`

### Wave 3 — 5 modules (2026-05-25)

| Folder | Upstream | Route prefix |
|---|---|---|
| `engel_gstack_main/` | gstack | `engel.gstack.*` |
| `engel_lfm2_main/` | LFM2 | `engel.lfm2.*` |
| `engel_lfm2_code_review_main/` | LFM2-CodeReview | `engel.lfm2_code_review.*` |
| `engel_lfm2_mobile_main/` | LFM2.5-Mobile | `engel.lfm2_mobile.*` |
| `engel_lfm2_vision_main/` | LFM2-Vision | `engel.lfm2_vision.*` |

Runner: `engel_wave3_runner.py`

### Wave 4 — 5 modules (2026-05-25)

| Folder | Upstream | Route prefix | Capability |
|---|---|---|---|
| `engel_claw3d_main/` | Claw3D | `engel.claw3d.*` (5) | 3D virtual office for AI agent teams |
| `engel_cubesandbox_main/` | CubeSandbox | `engel.cubesandbox.*` (4) | E2B-compatible AI agent sandbox |
| `engel_darwinian_evolver_main/` | DarwinEvolver | `engel.darwinian_evolver.*` (5) | Evolutionary code/prompt optimizer |
| `engel_hermes_agent_main/` | HermesAgent (Nous Research) | `engel.hermes_agent.*` (6) | Self-improving agent, skill creation, Telegram/Discord |
| `engel_localsend_main/` | LocalSend | `engel.localsend.*` (4) | Cross-platform LAN file sharing |

Runner: `engel_wave4_runner.py`

---

## Router Alias Fixes Applied (2026-05-25)

13 routes were failing the smoke test due to stale hardcoded entries overriding UPDATE_ROUTES. All fixed:

**Removed from `KNOWN_COMMANDS` in `engel_communication_router.py`:**
- `colony hive status/map/permissions/queen links` (were pointing to old-style `colony_hive_*` targets)
- `research office status/map/queen links` (were aliased to colony hive targets)
- `future upgrades status` / `future upgrade status` (were pointing to `human_command_mode`)

**Removed from `COMPLEX_HUMAN_COMMAND_MODE_COMMANDS`:**
- `research office permissions`
- `colony simulation status`

**Removed duplicate first-aliases from UPDATE_ROUTES:**
- `engel.octogent.swarm_status` — removed duplicate `"octogent status"`
- `engel.llama_cli.explain` — removed duplicate `"explain module"`
- `engel.growth.dashboard` — removed duplicate `"candidate learning status"`
- `engel.hive_mind.status` — removed duplicate `"colony hive status"`
- `engel.research.toggle_status` — removed duplicate `"research toggle status"`

---

## Key Files

| File | Purpose |
|---|---|
| `engel_ai_update_routes.py` | Single source of truth for all 459 routes |
| `engel_communication_router.py` | Main router — resolves phrases to routes |
| `engel_route_explorer.py` | Route catalog + group map |
| `engel_architect_agent.py` | Architect Agent — 13-section pipeline + planner phase (new) |
| `memory/architect_state/` | Architect state dir (sections/, briefs/, planner/, outputs/) |
| `engel_wave4_runner.py` | Wave 4 render functions |
| `engel_wave3_runner.py` | Wave 3 render functions |
| `engel_new_tools_runner.py` | Wave 2 render functions |
| `ENGEL_MODULE_MANIFEST.md` | Full module index (all waves) |
| `_route_smoke.py` | Smoke test runner (all routes) |
| `_route_smoke.log` | Latest smoke test results |
| `engel_desktop_v2.py` | V2 desktop GUI (TEL-style 4-panel) |
| `launch_engel_desktop_v2.bat` | Launch V2 GUI |

---

## Current Project State

EY Engel Core Direction and Safety Constitution remains the governing document:

```text
memory\ENGEL_CORE_DIRECTION_AND_SAFETY_CONSTITUTION_V1.md
```

Safe growth rhythm:

```text
observe -> propose -> verify -> report -> approve -> apply
```

Apply steps require verifier checks and explicit human approval.

---

## Current Safety State

The following remain disabled unless a later explicit, verifier-covered, human-approved task enables a bounded path:

- runtime autonomy
- Level 2 runtime execution
- autonomous proposal application
- simulation runtime
- colony/swarm/mycelium runtime
- provider/API/network calls
- live internet research
- background workers
- autonomous loops
- file sensing/watchers
- trusted-memory writes
- source-edit behavior
- queue mutation
- .grok writes or references on C: (must always use D:\b.WorkSpace\Engel App\.grok )
- learning apply behavior
- digest/history writes
- `ALIVE_STATE` writes

`STAGED_DRAFT_ACTIVE` must remain false.

---

## Current Safety Order

All prior orders complete. Current queue:

1. EY — Engel Core Direction and Safety Constitution — **complete**
2. EZ — Codex Job and Next Baton Alignment Cleanup — **complete**
3. EW-A — Launch Safety Guard Tool/Status Hardening — **complete**
4. EX — Refactor Safety Contract — **complete**
5. EY2 — Route and Command Metadata Inventory — **complete**
6. EY3 — Route and Command Metadata Documentation Normalization — **complete**
7. EY4 — Route Metadata Verifier Contract — **complete**
8. EY5 — Implement Static Route Metadata Contract Verifier — **complete**
9. EY6 — Route Metadata Reference Map — **complete**
10. Wave 2 integration (10 modules, ADB, Meeting Room, Desktop V2) — **complete**
11. Wave 3 integration (gstack, LFM2 family) — **complete**
12. Wave 4 integration (Claw3D, CubeSandbox, DarwinEvolver, HermesAgent, LocalSend) — **complete**
13. Router alias deduplication (13 routes fixed, smoke clean) — **complete**
14. Route Visual Map rebuild — 131-route "Other" bucket eliminated, 66→67 logical groups — **complete**
15. Agent Meeting Room verified — 8 routes, state files, lifecycle clean — **complete**
16. Architect Agent setup (31 routes, 5 zones, planner phase A-J) — **complete**
17. **Next:** First tiny refactor slice — only if Josh explicitly chooses refactor next and uses the static verifier before/after.
15. **Queued:** FK Research Source Fixture Contract — only after safety alignment remains clean and still approved as contract-only/no live research.

EY3 metadata guidance still applies:

- Preserve each route's existing side-effect class during future refactor work.
- Treat `health`, `router status`, and `tool registry status` as status-like with known report/log side effects, not pure read-only/no-write status routes.
- Do not reclassify a side-effecting status-like route as pure read-only unless a separate approved implementation task changes code behavior and verifier coverage.
- Read `memory\ROUTE_METADATA_VERIFIER_CONTRACT_V1.md` before implementing any static route metadata verifier.
- Future route metadata/refactor slices must run `python .\tools\verify_route_metadata_contract.py` before and after the change.

Before any broad cleanup, restructuring, route reorganization, or module extraction, read:

```text
memory\ENGEL_REFACTOR_SAFETY_CONTRACT_V1.md
```

---

## Codex Work Pattern

For each task:

1. Read `AGENTS.md`.
2. Read this handoff.
3. Read `CODEX_JOB.md`.
4. Read the EY constitution.
5. Inspect only files relevant to the active packet.
6. Make the huge-safe per the rules change.
7. Run scoped verification.
8. Write the requested report and checkpoint.
9. Include changed files, verification results, warnings, and next safe step in the final response.

---

## Verification Baseline

For docs/config/report-only work:

```powershell
python -m json.tool memory\<checkpoint>.json
python .\tools\verify_living_systems_documentation_drift.py
powershell -ExecutionPolicy Bypass -File scripts\codex_verify.ps1
```

For route changes:

```powershell
python _route_smoke.py
```

Run `py_compile` only when Python files are touched or explicitly required.

Run the full standard verifier sequence only when the scope and allowed output files make it appropriate.
