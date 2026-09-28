# Engel AI Main — Handoff Brief (2026-07-12)

Supersedes ENGEL_HANDOFF_20260711.md (still valid for architecture/access; this doc adds what the
7/11 evening Claude soak, the 7/11-12 overnight Codex session, and the 7/12 Claude service work changed).
Owner: Joshua Ziese. Everything below is LIVE and verified unless marked otherwise.

## 0. ACTIVATED — no pending steps

The `EngelSubEngelAutoReturn` stack service is LIVE as a controller-managed scheduled task
(operator re-ran the elevated `Setup-EngelStackLifecycle-RunAsAdmin.cmd` 2026-07-12 ~12:44Z; the setup's
port sweep retired the session stand-in and the controller tick started the managed task — task state
Running, mutex :8777 held, hidden log clean). The Sub-Engel meeting-room lane now runs whenever
EngelAIMain.exe is open, like the rest of the stack (11 managed services + controller).

## 1. What changed since the 7/11 morning handoff

### Claude soak session (7/11 ~16:30-18:30Z) — build lane + Sub-Engel round-trip
- **Build lane (CT246 :8765)**: slug-truncation collisions fixed (hash-suffix disambiguation via README
  title compare); "…, overwrite" now genuinely rebuilds (was a dead promise); existing builds short-circuit
  BEFORE the bridge call; workspace-setup lane added to the CT service (was ROG-worker-only; fast-chat ate
  those orders); NT-1 activation-depth 0→3 fix for self-appending lanes; `_BUILD_TARGETS` widened
  (demo/parser/formatter/printer/checker/tracker/analyzer); TypeScript runs via Node native type stripping
  (ts-node dropped — it self-installed then crashed); **Go installed on CT246** (tarball 1.23.4,
  /usr/local/go) + two exec-env fixes (Windows GOPATH leak; no-$HOME GOCACHE). Live matrix on CT246:
  python/js/ts/web/c/cpp/bash/go build AND run; ruby/java/rust give honest install caveats.
  Offline gate: `tools/test_engel_build_overwrite.py` (15/15).
- **Sub-Engel round-trip (dead 7/8→7/11)**: two root causes fixed — (a) the shared-room agent's target
  gate stringified the meeting room's descriptor-dict `target_node` into a fake identity (EVERY node
  refused EVERY order); (b) rust `node_kind_for_station` defaulted generic stations to `linux_sub_engel`,
  a worker class with no consumer anywhere (60 orders orphaned since 6/21 — archived 7/12 to
  `SUB_ENGEL_WORK_ORDERS\archived_linux_orphans_20260712\` with receipt). Also fixed in the agent: the
  one-shot LLM executor read a pre-refactor status shape (unreachable → structured fallback forever) and
  passed no `-c` (32k KV cache = 4GB alloc crash next to the :8899 server). Verified: real Mistral prose
  returns via `local_llm_one_shot` with GPU_LAYERS=14 + CTX=4096.
- Discord/Tel channel: Chase granted perms; a real GIF war ran 7/11 08:57Z. Fully live.

### Codex overnight session (7/11 18:00Z - 7/12 05:00Z) — policy + verifiers + UI
- New verifiers: `verify_engel_worker_ct_build_policy.py` (ROG build requests must reach CT246 before any
  local helper), `verify_engel_sub_direct_fallback.py` (paired direct Sub-Engel fallback, offline proof),
  `verify_engel_ui_web_build_receipt.py`; device-routing-intent updates; bash generation guardrails +
  language-aware `_project_is_interactive` in the build lane (fixes the bash `read -r` false-interactive);
  main.dart work proven through `run_engel_flutter_main_ui_prompt_training.py` (drives the visible app).
- Closed properly: rebuild → relaunch (PID 25196) → manifest re-pin → **GREEN 2026-07-12T04:59:49Z**.

### Claude service session (7/12 ~12:00Z) — durable Sub-Engel worker (THIS doc's §0)
- **NEW `tools/engel_sub_engel_auto_return_service.py`** — controller-managed wrapper that runs the
  shared-room agent's auto-return loop in-process on the ROG: env contract pinned in code (task lane
  passes none), loopback :8777 bind as single-instance mutex, crash-restart with backoff + fresh agent
  re-import, clean-return = intentional stop, EADDRINUSE vs transient-bind distinction, finite-cycle
  smoke mode (`ENGEL_SUB_AUTO_RETURN_CYCLES`).
- **`tools/engel_stack_controller.py`**: `EngelSubEngelAutoReturn` appended to SERVICES; 8777 in
  STACK_PORTS; **pre-existing teardown bug fixed** — the force-kill sweep PowerShell matched its own
  command line and killed itself mid-phase-1 (phase 2 never ran; empirically confirmed); now excludes
  `$PID` and also reaps a mid-flight packaged llama-cli by 'EngelAI-SubEngel' cmdline signature.
- **`scripts/Setup-EngelStackLifecycle.ps1`**: registers the new task; 8777 added to the elevated
  port-cleanup sweep.
- **`engel_sub_node_meeting_bridge.py` (ROG) — dead-node pinning fix**: orders are pinned to a specific
  node ONLY when its live health probe passes. Previously the best-scoring node was pinned even with a
  FAILED probe (score -120), and the agent identity gate then made every other worker skip the order —
  review verified 110 unreturned orders were all unclaimable. Unpinned orders keep the generic
  `windows_sub_engel` target any live worker may claim; the offline probe result is recorded under
  `best_candidate_when_written`. Offline proof: 6/6 both directions against the agent's real gate.
  (Worker mtime bumped so the running app respawned with the fix.)

## 2. Sub-Engel worker operations (ROG stand-in)

- Managed lane (after §0 activation): task `EngelSubEngelAutoReturn` runs
  `pythonw engel_hidden_launch.py script tools\engel_sub_engel_auto_return_service.py`; log at
  `runtime\logs\hidden_engel_sub_engel_auto_return_service.log`; scans every 30s, limit 5.
- Env knobs (operator env beats pinned defaults): `ENGEL_SUB_AUTO_RETURN_INTERVAL/_LIMIT/_CYCLES`,
  `ENGEL_SUB_ENGEL_LLM_GPU_LAYERS` (14), `ENGEL_SUB_ENGEL_LLM_CTX` (4096).
- Room semantics: generic (unpinned) orders may be answered by EVERY live windows_sub_engel worker —
  intentional (matches "every worker report status"). Identity-pinned orders are single-owner.
- When DESKTOP-UE5A6GG returns: it refreshes the agent from the shared room (both 7/11 agent fixes +
  nothing else needed); newly-dispatched orders will pin to it whenever its health probe passes, so the
  ROG stand-in naturally stops receiving pinned work.

## 3. Verification quick refs

- Health: `python tools\engel_health_check.py` (GREEN stamp needs `--full`). Doctor: `tools\engel_doctor.py`.
- Build lane smoke: probe script pattern in reports/receipts; offline gate `tools\test_engel_build_overwrite.py`.
- Sub-Engel drain (manual, session-scoped): run the wrapper directly with
  `ENGEL_SUB_AUTO_RETURN_CYCLES=2` for a bounded smoke; mutex :8777 enforces single instance.
- GREEN as of this writing: 2026-07-12T04:59:49Z (PID 25196, Codex). Nothing manifest-pinned changed in
  the 7/12 session (verified: wrapper/controller/setup/bridge are all unpinned).

## 4. Memory (Claude Code sessions)

`D:\ClaudeHome\projects\d--b-WorkSpace\memory\` — new/updated: engel-sub-engel-work-orders.md (round-trip
fixes + drain recipe + meeting-room architecture note: Sub-Engel and phone workers are both stations of
the ONE Agent Meeting Room), engel-chat-action-lane.md (soak fix log), engel-discord-multiserver.md.

## 5. Afternoon session (7/12 ~13:00-14:00Z) — personalization + real-user UI stretch

- **Engel knows Joshua now**: 8 durable facts taught via the real "remember that..." lane (JZ Drafting &
  Design owner/services/motto, Senior Draftsman at Global Modular, career path, links) — recalled verbatim,
  used in generated bios AND in build-lane sample data. THREE fixes made facts actually reach the models:
  facts-first composition + `_facts_clipped` newest-priority (both lanes were tail-slicing the newest facts
  out), big-lane memory budget 2600->4000, identity questions routed off the 1.5B quick model.
- **Themed build stretch**: 4 waves, 23 domain builds (beam/scale/takeoff/panel/stud/board-feet/schedule/
  BIM/tracker/invoice/proposal/timesheet/portfolio...) — all built, zero errors, engineering math verified
  exact, idempotence + overwrite proven, UI-built and script-built projects share one workspace store.
- **Real-user UI pass (computer-use)**: chat round-trip proven on screen (verbose panel, Send->Stop, reply
  bubble with real CT246 build output). TWO app bugs fixed + shipped (77/77 tests, GREEN 13:50:43Z,
  PID 45144): main.dart's 21 hardcoded H:\My Drive shared-room refs -> G:\ (Home tile showed "0 returned"
  vs 185 real), and the blank empty-state chat bubble removed.
- Managed Sub-Engel worker survived the rebuild bounce (mutex PID unchanged, scans continuous).

## 6. UI build marathon (7/12 ~13:11-15:01Z) — 33 detailed builds through the app, 4 defects fixed live

Drove build orders through the real Engel AI Main chat UI (computer-use) small->big, drafting/engineering
themed. All ran with correct output unless genuinely interactive. Four real defects found + fixed + deployed
mid-marathon (all offline-gated, then re-proven live in the UI):
- **Package-layout relative imports crashed at run** ("no known parent package"): `_execute_project` now
  runs a nested entry with `from .` imports as `python -m pkg.main`; gen prompt steers python multi-file
  builds to a ROOT entry + absolute imports.
- **Media lane stole a build order**: `_prompt_requests_media_artifact` matched 'visual' as a bare
  substring (caught 'visualizer'); now word-boundary + explicit-build-order precedence.
- **Facts starvation / identity routing** (afternoon): facts-first memory composition + identity Qs to big lane.
- **More build-target nouns**: exporter/writer/viewer/editor/manager/scheduler/estimator/configurator/
  visualizer/validator/monitor/organizer/counter/summarizer added to `_BUILD_TARGETS` (prose-risky words
  like report/log/plan/schedule deliberately excluded). "csv exporter" now builds + wrote a real CSV live.
Coverage incl.: kickoff checklist, ft-in->mm, roof pitch, concrete cu yd, door/window schedule, estimate
generator, unit configurator, mini-CRM, intake-form page, sheet index, block-char Gantt+critical path,
permit checklist, framing takeoff, material PO, C++ beam section props, payment schedule, revision log, site
report, punch list, occupancy load, stud SVG, cost/SF, egress width, 4-module PM suite, HVAC, parking count,
JZ services brochure (branded), rust trim (honest caveat), csv exporter. GREEN 2026-07-12T15:01:13Z PID 45144;
doctor 26/0/0; 96 workspaces; 0 service exceptions. No manifest-pinned files changed (tools-only deploys).

## 7. Fleet round-trip through the UI (7/12 ~15:06Z) — phones + Sub-Engel

Operator flagged the marathon incomplete without fleet visibility. Through the real chat UI:
- "send an order to the meeting room for all devices: ..." -> alpha+beta+gamma queued/returned (~6s,
  receipts on disk) AND shared-room order MAIN-MEETING-20260712T150644068624Z pinned to DESKTOP-UE5A6GG.
- **DESKTOP-UE5A6GG IS BACK ONLINE** and answers its own orders (fixed agent refreshed from shared room);
  the ROG EngelSubEngelAutoReturn worker skips pinned work as designed and remains the offline stand-in.
- Targeted dispatch ("have alpha summarize ...") round-trips from the UI.
- Gotcha: the Tasks page "Send Order" SUBMITS but does not complete/dispatch; the chat action lane does both.

## 8. Meeting-room panel dispatch wired (7/12 ~15:36Z)

Tasks-page "Send Order" (`_submitMeetingOrder`) was SUBMIT-ONLY (rust native-submit) — recorded the order,
never fanned out. Rewired to route through the worker chat dispatch lane (proven fleet fan-out), switching
to the chat view so returns show. The fleet detector is phrase-sensitive: the literal prefix
"send an order to the meeting room for all devices: " works; "Engel Meeting Room" broke it (placeholder).
Fixed to the exact form. VERIFIED LIVE via the panel button: 3 phones + Sub-Engel round-tripped. Widget
test updated (localChatRunner stub asserts the order reaches chat). GREEN 15:36:22Z PID 15156. 77/77.
