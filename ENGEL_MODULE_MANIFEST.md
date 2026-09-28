# Engel AI — Module Manifest
**Updated:** 2026-05-25  
**Route count:** 490 (Wave 4 + Architect Agent complete)  
**Active workspace:** `D:\b.WorkSpace\Engel App\`

---

## Overview

Engel AI is a unified local-first AI companion system. All upstream projects are vendored under this single Engel App root, renamed to semantic `engel_*_main/` folders, and surfaced through a unified route system at `engel_ai.py ask "<phrase>"`.

---

## Wave 1 — Original Vendored Modules (12 projects)

| Engel Folder | Upstream | Route Prefix | Capability |
|---|---|---|---|
| `engel_agent_main/` | hermes-agent | `engel.engel_agent.*` (16) | Hermes CLI agent + gateway/cron/memory/skills |
| `engel3d_office_main/` | Claw3D | `engel.engel3d.*` (4) | 3D office viewer/scene builder |
| `engelsandbox_main/` | CubeSandbox | `engel.engel_sandbox.*` (6) | E2B-compat Linux/KVM microVM sandbox |
| `engelcode_main/` | jcode | `engel.engelcode.*` (6) | Rust TUI coding agent |
| `engel_main/` | openhuman | `engel.engel_main.*` (9) | Tauri desktop companion |
| `engel_lan_main/` | localsend | `engel.engel_lan.*` (8) | LAN file sharing (Flutter + CLI) |
| `engel_humanizer_main/` | humanizer | `engel.engel_humanizer.*` (4) | Claude Code skill: de-AI text |
| `engel_native_agent_main/` | CodexAgent | `engel.native_agent.*` (5) | Background notify agent + GUI dashboards |
| `engel_ide_companion_main/` | AI-ASSISTANT-CURSOR | `engel.ide.*` (4) | Cursor IDE config/rules |
| `engel_evolution_lab_main/` | darwinian_evolver | `engel.evolution_lab.*` (5) | Darwin-Goedel GA framework |
| `engel_knowledge_graph_main/` | graphify-7 | `engel.knowledge_graph.*` (5) | Project knowledge graph builder |
| `engel_evolution_engine_main/` | evolver | `engel.evolution_engine.*` (5) | GEP self-evolution engine (Node.js) |

---

## Architect Agent (2026-05-25)

Implements the Architect Agent blueprint — Zones 1-5:
- Zone 1: Entry & mode selection (NEW/CONTINUE/ADD; Full/Lite/Custom)
- Zone 2: 13-section pipeline (Discovery, Commercial, Quality, Engineering)
- Zone 3: Support agents (Injector, Brief Writer, Tracker, Change Mgmt, Principles)
- Zone 4: Planner phase (10 stages A-J, mandatory pause at H)
- Zone 5: Outputs & handoff (plan.md / spec.md / prompt.md → Executor)

Module: `engel_architect_agent.py`  
State directory: `memory/architect_state/`  
Routes: 31 (`engel.architect.*`) — 22 status, 9 action

---

## Wave 4 — New Integrated Modules (5 projects, 2026-05-25)

| Engel Folder | Upstream | Route Prefix | Capability |
|---|---|---|---|
| `engel_claw3d_main/` | Claw3D | `engel.claw3d.*` (5) | 3D virtual office for AI agent teams |
| `engel_cubesandbox_main/` | CubeSandbox | `engel.cubesandbox.*` (4) | Instant E2B-compatible AI agent sandbox service |
| `engel_darwinian_evolver_main/` | DarwinEvolver | `engel.darwinian_evolver.*` (5) | LLM-based evolutionary optimizer for code/prompts |
| `engel_hermes_agent_main/` | HermesAgent (Nous Research) | `engel.hermes_agent.*` (6) | Self-improving agent — skill creation, learning loop, Telegram/Discord |
| `engel_localsend_main/` | LocalSend | `engel.localsend.*` (4) | Cross-platform LAN file sharing, no cloud required |

---

## Wave 3 — New Integrated Modules (5 projects, 2026-05-25)

| Engel Folder | Upstream | Route Prefix | Capability |
|---|---|---|---|
| `engel_gstack_main/` | gstack | `engel.gstack.*` (6) | Multi-agent CLI orchestration + gbrain context graph |
| `engel_lfm2_main/` | LFM2 | `engel.lfm2.*` (5) | Liquid Foundation Model 2 Python SDK |
| `engel_lfm2_code_review_main/` | LFM2-CodeReview | `engel.lfm2_code_review.*` (5) | LFM2-24B code review agent |
| `engel_lfm2_mobile_main/` | LFM2.5-Mobile | `engel.lfm2_mobile.*` (5) | LFM2.5-1.2B mobile inference + training |
| `engel_lfm2_vision_main/` | LFM2-Vision | `engel.lfm2_vision.*` (5) | Private vision model server |

**Also absorbed from workspace:**
- `TEL_APP_FULL_BONES_BUILDER_KIT_JOSH_V4.zip` → `docs/TEL_APP_FULL_BONES_BUILDER_KIT_JOSH_V4/`
- `claude.md/` (12-file workspace guide) → `docs/workspace_guide/`
- `docs/` workflow templates → `docs/workflow_templates/`
- `scripts/` verify scripts → `tools/`

---

## Agent Meeting Room (2026-05-25)

A structured multi-agent collaboration space combining debate, task handoff, and shared whiteboard.

| Route | Purpose |
|---|---|
| `engel.meeting_room.status` | Current meeting state + agent roster |
| `engel.meeting_room.agenda` | 6-item agenda (pending → in_progress → done) |
| `engel.meeting_room.transcript` | Running agent discussion log |
| `engel.meeting_room.whiteboard` | Shared Markdown scratchpad |
| `engel.meeting_room.agents` | Invited agents + roles |
| `engel.meeting_room.open` | Open meeting, initialise agenda + whiteboard |
| `engel.meeting_room.close` | Close meeting, save transcript |
| `engel.meeting_room.add_note` | Add note to shared whiteboard |

Agents: HermesAgent (executor), JarvisAgent (researcher), OctogentSwarm (planner), OpenAgents (reviewer), GitNexus (facilitator)  
Storage: `memory/ENGEL_MEETING_ROOM.json`, `memory/ENGEL_MEETING_WHITEBOARD.md`, `memory/meeting_transcripts/`

---

## Wave 2 — New Integrated Modules (10 projects, 2026-05-24)

| Engel Folder | Upstream | Route Prefix | Capability |
|---|---|---|---|
| `engel_cli_anything_main/` | CLI-Anything | `engel.cli_anything.*` (3) | 300+ CLI tool plugin hub |
| `engel_git_nexus_main/` | GitNexus | `engel.git_nexus.*` (3) | AI-powered git workflow |
| `engel_octogent_main/` | octogent | `engel.octogent.*` (3) | 8-agent orchestration swarm |
| `engel_open_agents_main/` | open-agents | `engel.open_agents.*` (3) | Open-source multi-agent framework |
| `engel_airllm_main/` | AirLLM | `engel.airllm.*` (3) | Memory-efficient local LLM inference |
| `engel_jarvis_main/` | OpenJarvis | `engel.jarvis.*` (3) | Jarvis-style AI assistant |
| `engel_chat_ui_main/` | agent-chat-ui | `engel.chat_ui.*` (3) | Streaming chat frontend |
| `engel_ai_gallery_main/` | ai-dev-gallery | `engel.ai_gallery.*` (3) | AI capability demos |
| `engel_cluster_main/` | cluster | `engel.cluster.*` (3) | Multi-node cluster manager |
| `engel_knowledge_graph_v2_main/` | graphify-8 | `engel.knowledge_graph_v2.*` (3) | Knowledge graph v2 |

---

## Native Surface (Stage 4 — Engel = hermes-agent native)

| Route | Capability |
|---|---|
| `engel.identity` | Engel identity + architecture announcement |
| `engel.native_runtime` | Phase D in-process import proof (14/14 OK) |
| `engel.gateway.*` | Gateway start/stop/status |
| `engel.cron.*` | Cron list/status |
| `engel.memory.*` | Memory status |
| `engel.skills.*` | Skills list |
| `engel.sessions.*` | Sessions list/stats |
| `engel.plugins.*` | Plugins list |
| `engel.toolsets` | Toolsets |
| `engel.doctor` | System health check |
| `engel.top.status` | Top-level status |
| `engel.version` | Version |
| `engel.invoke` | Single-shot invocation |

---

## Core Engel Modules

| Module | Purpose |
|---|---|
| `engel_ai.py` | Main entry point — `python engel_ai.py ask "<phrase>"` |
| `engel_ai_update_routes.py` | Route registry (490 routes) + dispatch |
| `engel_communication_router.py` | NLP phrase → route_id classifier |
| `engel_app.py` | App body (conversation, file ops, memory) |
| `engel_ai_intent_planner.py` | Intent planning |
| `engel_guardian_watchdog.py` | Watchdog / self-protection |
| `engel_prompt_injection_guard.py` | Prompt injection defense |
| `engel_leak_guard.py` | Data leak prevention |
| `engel_global_password_gate.py` | Human approval gate |
| `engel_ui_theme.py` | Shared Qt stylesheet |

---

## Desktop GUIs

| File | Purpose | Launch |
|---|---|---|
| `engel_desktop_v2.py` | **New** simplified TEL-style desktop (V2) | `launch_engel_desktop_v2.bat` |
| `start_engel.py` | Original Engel desktop launcher | `launch_engel_ai.bat` |
| `live/app/Engel.exe` | Built Windows executable | Direct launch |
| `live/app/EngelSuperSwarmHive3D.exe` | 3D hive GUI | Direct launch |
| `tools/capture_engel_screens.py` | Screenshot QA for Desktop V2 + passive thinking screen | `python tools/capture_engel_screens.py` |

---

## Integrated Files from Workspace Root

| File / Folder | Integrated To | Purpose |
|---|---|---|
| `engel_de_bruijn_memory_loader.py` | Engel App root | De Bruijn memory loader |
| `memory/engel_memory_de_bruijn_quantum_expanded.json` | `memory/` | De Bruijn quantum memory data |
| `tools/EngelTools/` | `tools/EngelTools/` | Security scanner, startup review, codex viewer |
| `assets/goal_queue_module_v1/` | `assets/` | React Goal Queue component (TEL-style) |
| `docs/TEL_APP_BLUEPRINT_FOR_JOSH_V3/` | `docs/` | TEL app build blueprint V3 |
| `docs/TEL_APP_BONES_FULL_PACKET_FOR_JOSH/` | `docs/` | TEL app bones/schemas |
| `docs/ENGEL_GUARDIAN_WATCHDOG_RECOVERY_SPINE_V1.md` | `docs/` | Guardian watchdog design |
| `docs/VANTAMOTH_GOAL_QUEUE.md` | `docs/` | VantaMoth goal queue spec |
| `docs/ENGEL_AI_CODE_COMPANION_FUTURE_GOALS.md` | `docs/` | Future goals doc |
| `docs/ENGEL_INDIVIDUAL_MARKDOWN_SECTION_SHEETS/` | `docs/` | Individual markdown sheets |
| `docs/De Bruijn Sequences and Quantum De Bruijn Graphs/` | `docs/` | Teaching reference |
| `memory/ENGEL_CUSTOMER_READY_*.md/.json` | `memory/` | 23 customer-ready LLM memory files |

---

## Route Summary by Namespace

This section is a high-level route map. For the exact current catalog, run
`python engel_ai.py ask "route explorer"` or `python _route_smoke.py`.

| Namespace | Count | Surface |
|---|---|---|
| `engel.architect.*` | 31 | Architect Agent pipeline, planner, outputs |
| `engel.<native>` | 17 | Stage 4 hermes-agent native surface |
| `engel.engel_agent.*` | 16 | hermes-agent runner (legacy form) |
| `engel.engel_lan.*` | 14 | LocalSend LAN |
| `engel.knowledge_graph_v2.*` | 13 | graphify-8 knowledge graph v2 |
| `engel.evolution_lab.*` | 11 | darwinian_evolver |
| `engel.llama_cli.*` | 10 | llama-cli local runtime |
| `engel.engel_main.*` | 9 | OpenHuman/Tauri desktop |
| `engel.meeting_room.*` | 8 | Agent Meeting Room debate + handoff + whiteboard |
| `engel.android_workers.*` | 7 | Android worker job/control surfaces |
| `engel.runtime_readiness.*` | 7 | Local AI runtime readiness |
| `engel.research.*` | 7 | Research queue/status surfaces |
| `engel.external_memory.*` | 7 | External memory status and intake |
| `engel.octogent.*` | 7 | Octogent swarm integration |
| `engel.airllm.*` | 7 | AirLLM local inference integration |
| `engel.engelcode.*` | 6 | jcode Rust TUI |
| `engel.engel_sandbox.*` | 6 | CubeSandbox microVM |
| Wave 2 base modules | 6 each | CLI-Anything, GitNexus, open-agents, Jarvis, chat-ui, ai-gallery, cluster |
| `engel.verify.*` | 6 | Workspace verifier bridge |
| `engel.wsl_ubuntu.*` | 5 | WSL Ubuntu Stage 2/3/4 |
| `engel.wsl.*` | 5 | WSL bridge |
| `engel.native_agent.*` | 5 | CodexAgent |
| `engel.knowledge_graph.*` | 5 | graphify-7 |
| `engel.evolution_engine.*` | 5 | evolver |
| `engel.ai_connectors.*` | 5 | AI connector hub |
| Wave 3 modules | 5 each | gstack, LFM2, LFM2 code review, LFM2 mobile, LFM2 vision |
| Wave 4 5-route modules | 5 each | Claw3D, Darwinian Evolver |
| `engel.ide.*` | 4 | Cursor IDE rules |
| `engel.engel_humanizer.*` | 4 | humanizer skill |
| `engel.engel3d.*` | 4 | Claw3D 3D office |
| `engel.accounts.*` | 4 | Account setup + safety |
| Wave 4 4-route modules | 4 each | CubeSandbox, LocalSend |
| Other status/action surfaces | 154 | Safety, memory, research, code companion, route explorer, WSL, worker, model, learning, and report surfaces |
| **Total** | **490** | Current source of truth: `engel_ai_update_routes.UPDATE_ROUTES` |

---

## Quick Commands

```powershell
cd "D:\b.WorkSpace\Engel App"
$env:PYTHONIOENCODING = "utf-8"

# All routes
python engel_ai.py routes

# Wave 2 new tools
python engel_ai.py ask "new tools list"
python engel_ai.py ask "cli anything plugins"       # lists 69+ plugin folders
python engel_ai.py ask "cli anything install"
python engel_ai.py ask "git nexus plugins"
python engel_ai.py ask "git nexus install"
python engel_ai.py ask "open agents packages"
python engel_ai.py ask "jarvis skills"
python engel_ai.py ask "start chat ui"
python engel_ai.py ask "ai gallery demos"
python engel_ai.py ask "cluster examples"

# Agent Meeting Room
python engel_ai.py ask "meeting room status"
python engel_ai.py ask "open meeting room"
python engel_ai.py ask "meeting room agenda"
python engel_ai.py ask "meeting room whiteboard"
python engel_ai.py ask "close meeting room"

# Desktop V2 GUI
python engel_desktop_v2.py

# Screen QA
python tools/capture_engel_screens.py

# Smoke test
python _route_smoke.py
```

---

## Safety Model

Engel follows an **Immune System** model:

- **READ_ONLY_STATUS_ONLY** — most routes just report, never mutate
- **NO_PROVIDER_CALLS** — no live API calls unless explicitly authorized
- **NO_BACKGROUND_WORKER** — no autonomous background loops by default
- **NO_TRUSTED_MEMORY_WRITE** — human approval required for memory promotion
- **NO_SOURCE_MUTATION** — Engel cannot rewrite its own source
- **HUMAN_APPROVAL_GATED** — all risky actions pass through the approval gate

The `engel_guardian_watchdog.py` + `engel_global_password_gate.py` enforce these boundaries at runtime.
