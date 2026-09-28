\# AGENTS.md — Engel App Coding Agent Rules



\## Project



This repository is Engel App / Engel Bible Companion related work.



Agents may help inspect, edit, test, and document the project, but must preserve the safety model.



\## Hard Safety Rules



Do not add or enable:



\- provider calls

\- live internet research

\- autonomous loops

\- background workers

\- Level 2 runtime autonomy

\- trusted-memory writes

\- queue mutation

\- learning apply behavior

\- digest/history writes

\- ALIVE\_STATE writes

\- source edits outside the assigned job

\- Ollama, localhost provider, or old-provider paths

\- Any .grok data (skills, docs, config, state) living on or writing to C: (must be at D:\b.WorkSpace\Engel App\.grok with C: junction only for legacy compat; all references and writes must use the D: location)



Bounded RunPod LLM exception:

- A RunPod provider/API/network action is allowed only when Josh explicitly requests RunPod LLM creation, training, inference verification, or adapter registration in the current conversation and states a spend budget or confirms a prior budget.
- The action must be limited to Engel AI Main LLM work using the existing RunPod scripts, receipts, and config under `F:\ENGEL_APP_MEMORY\runpod` and this repo's `tools\run_engel_lora_training_on_runpod.py`, `tools\create_engel_runpod_training_pod.py`, and `tools\register_engel_trained_lora_adapter.py`.
- The agent must not print, copy, summarize, or store API keys, SSH private keys, tokens, or other secrets in chat, reports, receipts, logs, or source files.
- The agent must respect the stated dollar budget, pass the budget to the RunPod runner when supported, stop or scale down paid resources when the job finishes or fails, and write receipts under `F:\ENGEL_APP_MEMORY\runpod\receipts` plus a Codex bridge report under `reports\codex_bridge`.
- This exception does not allow general provider calls, live internet research, autonomous loops, background workers, startup autorun, trusted-memory writes, queue mutation, learning apply behavior, digest/history writes, `ALIVE_STATE` writes, Ollama, localhost provider, or old-provider paths.
- If the action is not explicitly RunPod LLM work with a bounded budget and receipt coverage, stop and report instead of implementing.

Bounded Proxmox Engel Main persistent-link exception:

- A startup/background service action is allowed only when Josh explicitly asks to keep the ROG Engel AI Main app merged with the Proxmox `engel-ai-main` CT runtime as one persistent system.
- The allowed persistent pieces are limited to CT 246 systemd services `engel-main-chat.service` and `engel-agent-meeting-room.service`, plus the Windows logon task `EngelMainServerPersistentLink` that opens SSH tunnels for local app URLs `http://127.0.0.1:24680` and `http://127.0.0.1:8790`.
- The setup must use key-based SSH after a one-time password entry. Do not store SSH passwords, private keys, tokens, API keys, or secrets in the repo, reports, receipts, chat, or logs.
- This exception does not allow Proxmox storage mutation, `pct set`, VM/container migration, disk formatting, LVM recreation, multipath changes, device-worker startup, trusted-memory writes, queue mutation, or provider calls.
- The canonical one-time setup script is `scripts\Install-EngelMainPersistentAgenticSystem.ps1`; the tunnel worker is `scripts\Start-EngelMainServerChatTunnelPersistent.ps1`.
- Normal user activation should go through `scripts\Start-EngelMainOneSystem.ps1` or the Desktop shortcut `Engel AI Main - One System.lnk`; connection debugging should use `scripts\Test-EngelMainOneSystemConnections.ps1`.

CT246 server-first storage rule:

- Engel AI Main's source of truth is the Dell PowerEdge Proxmox CT 246 `engel-ai-main` server runtime, not the ROG laptop.
- The ROG laptop is Engel AI Main's face/controller and may provide its GPU only as an explicitly requested helper lane; it must not become the default home for models, memory, training outputs, receipts, worker state, or long-lived services.
- Active runtime work goes on CT 246 SSD storage under `/opt/engel`: chat service, model service, active local LLMs, active adapters, persistent memory, Agent Meeting Room state, current receipts, and service logs.
- Bulk/cold work goes on the Dell server HDD/ZFS `engel-hdd-vault` storage when mounted: model archives, datasets, old checkpoints, large training outputs, snapshots, and transfer staging.
- External storage arrays, retired storage containers, laptop external drives, and Windows-only model paths are permanently outside Engel AI Main's topology. There is no re-enable path in this build.
- The complete CT246 storage allowlist is `/opt/engel` for active runtime and `/mnt/engel-hdd-vault` for archive writes only after exact mount proof. Reject every other storage root.
- If an action cannot confirm the CT 246 SSD/HDD target path, stage the storage move and continue only with safe local planning or verification.

Bounded Josh landscape-research exception:

- A live internet / vendor-docs research action is allowed only when Josh explicitly asks in the current conversation to research online, a named vendor (including xAI), or the wider AI landscape and to compare the findings against Engel AI / this repo.
- Allowed work is read-only: public web search, public vendor pages, public model/docs pages, and a comparison report under `reports/codex_bridge` (plus optional REPS Record/Evaluate/Propose notes). No secrets may be fetched, printed, stored, or summarized.
- Allowed outputs are gap lists, proposals, curriculum/topic candidates, and AGENTS.md / report edits needed to keep this exception accurate. Applying a proposed feature into Engel runtime, routes, providers, models, packages, or services still requires a separate Josh sign-off for that named build task.
- This exception does not allow wiring Engel to xAI/Grok/OpenAI/Anthropic or any other live provider API, downloading models/packages, autonomous loops, background workers, trusted-memory writes, queue mutation, learning-apply behavior, digest/history writes outside the requested report/REPS records, `ALIVE_STATE` writes, Ollama/localhost/old-provider paths, Proxmox storage mutation, or device-worker startup.
- If Josh did not explicitly request landscape/online/vendor research in the current conversation, stop and report instead of browsing.

Bounded Engel Universal REPS runtime exception:

- When Josh explicitly asks Engel AI Main to use the REPS/self-improvement template pattern shown in the provided images, the task is allowed to create and update universal Engel AI Main REPS runtime assets for all AI lanes, not only Claude.
- REPS means: Record, Evaluate, Propose, Sign-off. It is the active Engel improvement loop from the templates: memory fills automatically, scoreboards measure drift, proposals upgrade the system, and sign-off keeps Josh in charge.
- Allowed outputs include documentation, prompt/template files, saved Engel skill definitions, saved Engel agent definitions, append-only session memory, working-memory notes, untrusted lesson records, memory-candidate records, proposal records, evaluation scorecards, sign-off request templates, receipts, reports, read-only registry exposure, and bounded REPS runtime/API code needed to make `/reps/status`, `/reps/record`, `/reps/evaluate`, `/reps/propose`, `/reps/signoff`, and `/reps/cycle` actually write persistent Engel records.
- Allowed AI lanes are Codex, Claude, ChatGPT, Grok, local LLMs, CT 246 Engel AI Main, Agent Meeting Room agents, and Android worker prompts, as long as the same Josh > Guardian > Engel/runtime authority order is preserved.
- The templates must be provider-neutral. Do not hard-code the system as Claude-only. Use "AI lane", "assistant", "model", or named lane fields where a specific lane is required.
- Record is on by default for REPS work: save the useful lesson, correction, source pointer, lane, score, and receipt under Engel-controlled storage so the same mistake is not repeated across AI lanes.
- Evaluate is on by default for REPS work: run or create pass/fail scoreboards for the task, compare before and after, and mark keep/throw-away/rework status.
- Propose is on by default for REPS work: draft rules, prompts, skills, agents, memory candidates, and improvement candidates when repeated mistakes or useful workflows appear.
- Sign-off follows the template buckets instead of a blanket block:
  - Bucket 1 Auto-approve: tiny low-risk template, report, receipt, registry, scorecard, and append-only working-memory maintenance that stays inside Engel storage, has no secrets, and does not change runtime behavior.
  - Bucket 2 Needs sign-off: rule edits, saved skill/agent changes, prompt/template changes that alter future behavior, and promotion from candidate/working memory into active Engel guidance.
  - Bucket 3 Needs Josh call: source edits, route/runtime/service changes, storage changes, provider/network/mobile actions, package/model downloads, training, trusted core memory changes, and any action with real-world or destructive impact.
- This exception does not allow provider calls, live internet research, model downloads, package installs, autonomous loops, unbounded background workers, trusted-memory writes, queue mutation, source edits outside the assigned REPS runtime job, Proxmox storage mutation, device-worker startup, digest/history writes outside the requested Engel REPS records, or `ALIVE_STATE` writes.
- Explicit current-turn approval is a real gate, not a read-only downgrade. When Josh explicitly asks to build, fix, wire, install, train, update, or proceed with a named Bucket 2 or Bucket 3 task in the current conversation, treat that as matching sign-off for that bounded task and execute the approved work instead of stopping at a proposal.
- Approved execution must stay inside the named scope, preserve the hard safety rules, avoid secrets in output, run the relevant verifier(s), write a receipt/report, and record the lesson through REPS. If the approval is broad but the target files, systems, budget, credentials, or destructive risk are unclear, stage only the unclear part and continue with the safe parts.
- Stage instead of executing only when the task would cross an unapproved hard boundary: destructive storage changes, unbounded paid resources, secret disclosure, Proxmox disk/LVM mutation, unapproved provider/network/mobile action, autonomous background behavior, or trusted core-memory promotion without the matching verifier-covered approval.

If a task appears to require any forbidden behavior outside the bounded RunPod LLM exception, bounded Proxmox Engel Main persistent-link exception, bounded Josh landscape-research exception, or bounded Engel Universal REPS runtime exception, stop and report instead of implementing.



## Authority Hierarchy

Josh > Guardian > Engel/runtime

Josh is the final human authority.

Guardian is the safety/governance layer below Josh and above Engel/runtime.

Engel/runtime remains below the fixed Josh-first, Guardian-second gates. Engel may observe, summarize, compare, cool down, research locally, and propose, but may not cross action gates without Josh approval and Guardian safety checks.



\## Required Work Pattern



For every job:



1\. Read this file.

2\. Read `CODEX\_HANDOFF.md`.

3\. Read `CODEX\_JOB.md`.

4\. Read `wiki/ONE.md` before landing CODE. Update `wiki/ONE.md` and `wiki/organs.json` in the same job when an organ, talks-to, source, or duty changes.

5\. Inspect only the files relevant to the job.

6\. Make the smallest complete safe change.

7\. Run verification.

8\. Stamp Wiki Journal with `tools/stamp_wiki_one_journal.py --wiki-read`.

9\. Write a report under `reports/codex\_bridge/`.



\## Verification



Before reporting completion, run:



```powershell

powershell -ExecutionPolicy Bypass -File scripts/codex\_verify.ps1

Core Engel Mind Architecture Principle:

Use Argentine ant supercolonies as inspiration for Engel’s local hive-mind architecture:
many nests, many workers, many queens, one cooperative colony identity.

Engel’s Mind should feel like one living companion built from many local memory colonies:
- chat memories
- thought seeds
- research reports
- approved lessons
- swarm trails
- project history
- local Bible/search resources
- verification reports
- proposal drafts

The goal is not uncontrolled autonomy.

The goal is coordinated offline intelligence:
Engel remembers, compares, reinforces, cools down, researches, and proposes while authority stays explicit: Josh is highest approval authority, Guardian is the safety review layer below Josh, and Engel/runtime systems remain below both.

Design rules:
- Many local subsystems may contribute.
- No subsystem acts as an uncontrolled autonomous authority.
- Memory colonies should reinforce useful patterns and cool down weak/noisy ones.
- Research/proposal systems may suggest, not execute, unless explicitly approved.
- Authority order is fixed: Josh first, Guardian second, Engel/runtime below both for activation, mutation, permission, registry, and runtime action gates.
- Engel should feel unified to the user, even when many local colonies are contributing beneath the surface.
