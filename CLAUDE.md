# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## What this repo is

Engel App is a local-first AI companion that absorbs 28+ upstream open-source agent/runtime projects under one roof and surfaces them through a unified route system. There is no remote backend by default — everything runs against the user's local files, local model weights, USB-connected Android phones, and a local LAN.

Active workspace root: `D:\b.WorkSpace\Engel App`. Authority order is fixed: **Josh > Guardian > Engel/runtime** (see `AGENTS.md`).

---

## D: drive only — non-negotiable

Per project memory `feedback-no-c-drive`: nothing project-related lives on or is invoked from `C:\`. The Engel-owned tool binaries have been relocated:

- **Python interpreter:** `D:\b.WorkSpace\Engel App\runtime\python310\python.exe` (3.10.11, PySide6 6.11.0 + psutil + pip pre-installed)
- **Android Debug Bridge:** `D:\b.WorkSpace\Engel App\tools\platform-tools\adb.exe` (v37.0.0)
- **Flutter SDK:** `D:\b.WorkSpace\flutter_windows_3.41.9-stable\flutter\bin\flutter.bat`
- **Grok harness (.grok):** `D:\b.WorkSpace\Engel App\.grok` (C:\Users\ziese\.grok is a junction only; zero writes/data on C:)

When invoking python or adb in scripts, always prefer the D: paths above. .grok (skills, config, state) must always resolve to the D: location. Launch scripts use this pattern:

```batch
set ENGEL_PY=%~dp0runtime\python310\python.exe
if not exist "%ENGEL_PY%" set ENGEL_PY=python
"%ENGEL_PY%" engel_desktop_v2.py
```

`engel_adb_worker_manager._resolve_adb()` actively *refuses* C:-rooted ADB candidates from PATH. New code that hard-codes a C: path will fail the `tools/verify_engel_c_drive_cleanup.py` verifier in the standard sweep.

---

## Common commands

All run from the repo root unless stated otherwise.

| Task | Command |
|---|---|
| Smoke-test every registered route (~2-3 min, 445 of 490 routes; 45 slow `.build`/`.install` skipped) | `python _route_smoke.py` |
| Run a single phrase through the router | `python engel_ai.py ask "engel status"` |
| Full verifier sweep (90+ verifiers, ~3-5 min) | `powershell -ExecutionPolicy Bypass -File scripts/codex_verify.ps1` |
| One specific verifier | `python tools/verify_<name>.py` |
| Launch the main Qt GUI | `python engel_desktop_v2.py` (or `launch_engel_desktop_v2.bat`) |
| Launch the Meeting Room Qt window | `python engel_agent_meeting_room.py` (or `launch_engel_meeting_room.bat`) |
| Build `Engel.exe` (PyInstaller, ~5-10 min) | `powershell -ExecutionPolicy Bypass -File scripts/build_engel_main_exe.ps1` |
| Build SuperSwarm `EngelSuperSwarmHive3D.exe` | `scripts/build_engel_super_swarm_exe.ps1` |
| Build both packaged exes | `scripts/build_approved_packaged_artifacts.ps1` (writes to `build/staging/`, not `dist/`) |
| Rebuild Android worker APK | `cd mobile/engel_remote_worker && "D:\b.WorkSpace\flutter_windows_3.41.9-stable\flutter\bin\flutter.bat" build apk --release` |
| Install Android APK on a specific phone | `tools\platform-tools\adb.exe -s <SERIAL> install -r mobile\engel_remote_worker\build\app\outputs\flutter-apk\app-release.apk` |
| Show connected Android workers + queues | `python engel_ai.py ask "android workers status"` |
| Create a worker job | `python engel_ai.py ask "create android job <worker_id>\|<job_type>\|<title>\|<instructions>"` |

ADB on Windows + Git Bash mangles `/storage/...` device paths into `E:/Git/storage/...`. Prefix any `adb push|shell` calls with `export MSYS_NO_PATHCONV=1`.

---

## Big-picture architecture

### Route system (the spine)

Every user-facing action goes through one path:

1. User says a phrase to `engel_ai.py` (CLI) or `engel_desktop_v2.py`'s chat panel.
2. `engel_communication_router.classify_user_input(phrase)` matches the phrase against alias tables and falls back to `resolve_update_route` in `engel_ai_update_routes.py`.
3. The matched `EngelAIUpdateRoute` declares `target_module` + `target_function` + safety flags (`read_only`, `status_only`, `no_provider_model_network`, etc.).
4. The dispatcher imports the module and calls the function with the remaining payload.
5. The string return is surfaced to the UI.

`UPDATE_ROUTES` (in `engel_ai_update_routes.py`) is the **single source of truth** for the 490-route registry. To add a feature, you typically (a) write `render_<name>()` in a `engel_<feature>.py` module, (b) add a `ROUTE_ID` constant + `EngelAIUpdateRoute(...)` entry to `UPDATE_ROUTES`, (c) extend `_group_for_route()` in `engel_route_explorer.py` if it deserves a new group. The route-explorer verifier (`tools/verify_engel_route_explorer_superswarm.py`) requires the catalog to exactly cover `UPDATE_ROUTES`.

Stale hardcoded aliases in `engel_communication_router.KNOWN_COMMANDS` and `COMPLEX_HUMAN_COMMAND_MODE_COMMANDS` can shadow new routes — when a smoke-test mismatch shows `route_target != expected`, look there first.

### Three coexisting GUI surfaces

- `engel_desktop_v2.py` — main Qt window (PyQt6 preferred, PySide6 fallback). 4-panel TEL-style layout: System Monitor / Agent Chat / Goals|Models|Routes tabs / status bar. Chat panel intercepts certain phrases (`meeting room`, `where is the meeting room`, etc.) locally before routing them, so the provider bridge never sees them.
- `engel_agent_meeting_room.py` — standalone Qt Meeting Room. **Intake is API-only** — no prompt input lives in the window. Orders arrive via `submit_order_from_engel_main_ui(order_text)` from the main UI; replies come back via `complete_order_from_engel_main_ui(order_id, reply)`. Per-equipment dispatch: Local Engel AI = chat record, Android worker = real packet via `engel_adb_worker_manager.render_adb_create_job`, Sub-Engel = preview-only staged file (no remote control yet).
- `engel_agent_meetingroom.py` (note the missing underscore) — the text-only `engel.meeting_room.*` routes for the chat router. Separate from the Qt window.

### Vendored upstream modules

28 `engel_*_main/` folders are full source trees of upstream OSS projects (hermes-agent, Claw3D, CubeSandbox, gstack, LFM2 family, etc.) renamed to live under one root. Each gets a `engel_<name>_runner.py` (or shares a wave runner like `engel_new_tools_runner.py`, `engel_wave3_runner.py`, `engel_wave4_runner.py`) that exposes `render_<name>_status/features/docs/install/...` functions reachable via `engel.<name>.*` routes.

When adding a new vendored project: drop the source folder, write a `engel_<name>_runner.py` modeled on `engel_wave4_runner.py`, add routes, decide whether to bundle the folder in the PyInstaller specs (the small ones — under ~50MB — are bundled; jarvis/octogent/engelcode/engel_main are too big and surface as "MISSING folder" inside the packaged exe, which is fine for status routes).

### Architect Agent (`engel_architect_agent.py`)

13-section pipeline (Discovery → Commercial → Quality → Engineering) feeding a 10-stage planner (A through J) with a **mandatory pause at stage H (Founder Approval Gate)**. State persists under `memory/architect_state/{sections,briefs,planner,outputs}/`. Outputs land as `plan.md` / `spec.md` / `prompt.md` → cold Executor handoff. 31 routes under `engel.architect.*`.

### Android worker fleet

Two phones, each runs an **independent** worker (same role name on two phones = two separate queues — see `project_engel_android_workers.md`):

| Serial | Model | Worker ID |
|---|---|---|
| `ANDROID_WORKER_ALPHA` | Moto G Power 2025 | `android_worker_alpha` |
| `ANDROID_WORKER_BETA` | Moto G Fast | `android_worker_beta` |

PC-side dispatch goes through `engel_adb_worker_manager.py` (USB-ADB). The phone runs a Flutter app at `mobile/engel_remote_worker/` whose `lib/main.dart` is intentionally a minimal tool: identity badge → assigned agent chip → message transcript → pair row → status footer. The LAN side is `engel_remote_worker_lan_pairing.py` (port 8765, `--lan` for non-localhost). The LAN server accepts `ALLOWED_WORKER_IDS = {alpha, beta, gamma}`.

### Engel-Hermes bridge

`engel_agent_bridge.py` exposes the bundled `engel_agent_main/` (hermes-agent fork) for in-process import. It searches multiple roots in priority order (sibling file → sibling exe → `runtime/agent_bridge/engel_agent_main` → install root). **Never raises on import** when the subtree is missing; callers check `bridge_available()` / `bridge_missing_reason()` instead. This is why the Meeting Room can launch even from a packaged exe that didn't bundle the agent subtree.

### Long-term storage layout (E: / F: / G: external memory drives)

Engel uses three external memory drives in addition to the D: workspace. **Any code that scans for GGUF model weights, archived chat exports, or long-term receipts MUST check all three** (in F → G → E order per `project_engel_external_memory.md`; F is the fastest). `engel_local_model_manager._SCAN_ROOTS` already reflects this. Never add a new external-memory call site that hits only one drive.

| Drive | Role | Trusted writes | Folder structure | Notable contents |
|---|---|---|---|---|
| **E:\ENGEL_APP_MEMORY** | Primary long-term archive shelf — `long_term_engel_archive_shelf`, `NO_BROAD_SCAN`, **trusted_memory_write=BLOCKED** | blocked | `00_README_FIRST/`, `01_PROJECT_MEMORY/`, `02_BACKUPS/`, `03_REPORTS/`, `04_CHECKPOINTS/`, `05_VERIFIERS/`, `06_SECURITY_AUDITS/`, `07_CODE_SNAPSHOTS/`, `08_BATONS/`, `09_ARCHIVE_OLD/`, `archives/`, `exports/`, `inbox/` | No GGUF models currently |
| **F:\ENGEL_APP_MEMORY** | `FAST_EXTERNAL_MEMORY` — Seagate FireCuda Gaming 1TB; the **fast** drive | (see `engel_account_connector.py`) | `backups/`, `chat_exports/`, `code_companion/`, `libraries/`, `manifests/`, `models/`, `quarantine/`, `receipts/`, `remote_worker/`, `reports/`, `runtimes/` | **llama.cpp builds** live here: `runtimes/llama.cpp/candidates/llama-b9198-bin-win-cpu-x64/llama-cli.exe` (CPU) and `…/llama-b9198-bin-win-cuda-12.4-x64/` (CUDA 12.4, DLLs only). No GGUF models. |
| **G:\ENGEL_APP_MEMORY** | Secondary / overflow archive shelf — same `long_term_engel_archive_shelf` role | per shelf rules | Same as E: structure | **6 GGUF models live here:** Mistral-7B-Instruct-v0.3-Q4_K_M (4.07 GB), qwen2.5-0.5b Q5_K_M, qwen2.5-3b Q5_K_M, qwen2.5-7b Q5_K_M (split 00001+00002 and full 5.07 GB) |

Short rules:

- **Models go on G:** (with F: as fast cache when working on them). `runtime/python310/` and `tools/platform-tools/` stay on D: — that's app runtime, not long-term storage.
- **F: holds llama.cpp**, not models. Models stay on G: even when invoked through F: runtimes.
- **E: is the cold archive.** Trusted-memory writes to E: are blocked at the policy layer — don't try to bypass it.
- **The D: `memory/` folder is the *project* mirror of Claude harness memory** (synced from `C:\Users\ziese\.claude\projects\d--b-WorkSpace\memory\`). It is not the same as the external long-term archive shelves on E:/G:. Don't conflate them.
- If a user prompt is vague about "where should X go," default to: code/runtime → D:, model weights → G: (or F: for working set), chat exports → F:, hard archive snapshots → E:.

---

## Required work pattern (from AGENTS.md)

For every job:

1. Read `AGENTS.md`, `CODEX_HANDOFF.md`, `CODEX_JOB.md`.
2. Read `wiki/ONE.md` before landing CODE. Update `wiki/ONE.md` and `wiki/organs.json` in the same job when an organ, talks-to, source, or duty changes.
3. Inspect only the files relevant to the job.
4. Make the huge-safe per the rules change.
5. Run verification (`scripts/codex_verify.ps1` for the full sweep, or the route smoke + the specific module's verifier for narrower changes).
6. Stamp Wiki Journal: `runtime\python310\python.exe tools\stamp_wiki_one_journal.py --wiki-read ...`
7. Write a short report under `reports/codex_bridge/<NAME>.md` listing files changed, verifiers run, blockers, and the next recommended packet.

---

## Hard safety rules (`AGENTS.md`)

Do **not** add or enable:

- provider/API/network calls, live internet research
- autonomous loops, background workers, Level 2 runtime autonomy
- trusted-memory writes, queue mutation, learning-apply behavior
- digest/history writes, `ALIVE_STATE` writes
- source edits outside the assigned job's allowed files
- Ollama, localhost provider, or old-provider paths

If a task appears to require any of those, **stop and report** instead of implementing.

The safe growth rhythm (`memory/ENGEL_CORE_DIRECTION_AND_SAFETY_CONSTITUTION_V1.md`):

```
observe → propose → verify → report → approve → apply
```

Apply steps require verifier checks and explicit human approval.

---

## Project memory

Two synced copies of the project's auto-memory:

- `C:\Users\ziese\.claude\projects\d--b-WorkSpace\memory\` — where Claude Code's harness writes
- `D:\b.WorkSpace\Engel App\memory\` — D:-side mirror checked into the project

Important entries:

- `feedback_no_c_drive.md` — the D:-only rule + audit log of every relocation
- `project_engel_wave2_integration.md` — full integration history (Wave 2 through Wave 4 + Architect + Meeting Room V1)
- `project_engel_meeting_room.md` — Meeting Room dispatch model
- `project_engel_android_workers.md` — phone fleet, worker independence rule
- `project_engel_external_memory.md` — E:/F:/G: drive roles (GGUF models, llama.cpp builds)

`tools/verify_engel_c_drive_cleanup.py` enforces that the D: copies stay in hash-sync with the C: harness copies.

---

## Files to read before non-trivial changes

| Before changing | Read first |
|---|---|
| Any CODE landing on this Windows body | `wiki/ONE.md` (Wiki One) |
| Any route or `UPDATE_ROUTES` entry | `memory/ROUTE_METADATA_REFERENCE_MAP_V1.md`, `memory/ROUTE_METADATA_VERIFIER_CONTRACT_V1.md` |
| Anything that touches multiple modules ("refactor") | `memory/ENGEL_REFACTOR_SAFETY_CONTRACT_V1.md` |
| Bridge / runtime / autonomy behavior | `memory/ENGEL_CORE_DIRECTION_AND_SAFETY_CONSTITUTION_V1.md` |
| Meeting Room dispatcher | `memory/ENGEL_AGENT_MEETING_ROOM_CONTRACT_V1.md` |
| Android worker behavior | `engel_android_remote_worker_contract.py`, `mobile/engel_remote_worker/ENGEL_REMOTE_WORKER_ANDROID_CONTRACT_V1.md` |

The most recent build/run reports live under `reports/codex_bridge/`; the most recent one (`ENGEL_D_DRIVE_RELOCATION_V1.md`) is a good orientation pass on the current state.
