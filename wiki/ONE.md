# Wiki One — Engel AI Main canonical second brain

Status: LIVE / ORGANS ALIVE / NOT_TRUSTED_MEMORY

Engel AI Main is **alive**. Wiki One is its canonical second brain.
Host: `LAPTOP-0KUVK82E`.
Role: Engel AI Main is LIVE. Cosmic Swarm OS is the face. CT246 is the runtime body.

Organs: **50** — **50 alive**.

The **whole Engel AI Main** — Cosmic Swarm OS (`EngelAIMain.exe`) included — must **read** this before CODE and **update** it when organs, talks-to, sources, or duties change. Then **stamp Journal**.

On Cosmic Swarm Home: tab **Wiki**, Ask Engel `wiki one` / `wiki journal` / `update wiki one`, Quick access **Wiki One**.

Contract: `wiki/CONTRACT.md`. Authority: **Josh > Guardian > Engel/runtime**.

Machine twin: `wiki/organs.json`. Walk: `wiki/CONTEXT.md`. Impact: `wiki/effects/CONTEXT.md`. Stamps: `wiki/journal/`.

## Land CODE

1. Read this file.
2. Open the organ you will touch (`wiki/effects/CONTEXT.md` if more than one).
3. If the organ changed, update this file **and** `wiki/organs.json` in the same job.
4. Land the smallest safe change.
5. Stamp Journal:

```text
D:\b.WorkSpace\Engel App\runtime\python310\python.exe tools\stamp_wiki_one_journal.py --wiki-read --lane <lane> --worker <name> --organs <id,id> --summary \"one line\" --files \"a.py;b.py\" --receipt \"reports/codex_bridge/<NAME>.md\"
```

## Organs (ALIVE)

| id | organ | life | home | does | talks to |
|---|---|---|---|---|---|
| josh | Josh | alive | human | Final human authority. Approves Bucket 2/3 work, spend, storage, and runtime action. | guardian, face, factories |
| guardian | Guardian | alive | windows | Safety and governance below Josh and above Engel/runtime. Hard-rule stop. | josh, verifiers, router, factories |
| face | Face / Qt desktop | alive | windows | Visible Engel window on this laptop. 4-panel TEL layout. Chat intercepts some phrases locally before the router. | router, meeting_room, persistent_link, eyes, launchers, wiki_one |
| router | Route spine | alive | windows | One spine: phrase → classify_user_input / UPDATE_ROUTES → target_module.target_function. | face, meeting_room, architect, graph_studio, wiki_one, verifiers |
| meeting_room | Meeting Room | alive | windows | Standalone Qt room. Intake is API-only. Dispatches Local Engel (record), Android (real ADB job), Sub-Engel (preview only). Portal desk Discord app ids live on CT246 isolated gateways. | face, adb_hands, android_limbs, sub_engel, agent_kernel, skills, discord_mouth, control_room |
| persistent_link | Persistent link | alive | windows | Keeps this face merged with CT246 as one system. Local URLs 127.0.0.1:24680 (chat) and :8790 (meeting room) via SSH tunnels. | face, ct246_body, launchers, control_room |
| control_room | Control Room | alive | windows | Windows EngelControlRoom face. Probes CT246 chat, Meeting Room, conical status, Sub-Engel, Discord parity, the three Android workers (Alpha/Beta/Gamma), live 7B inventory, and SSD/vault storage. Generate is chat_only to live Engel. Demo Llama catalogue is off. | persistent_link, ct246_body, meeting_room, face, wiki_one, sub_engel, discord_mouth, android_limbs |
| factories | Worker factories | alive | windows | Grok, Claude, Codex, Cursor, and other AI lanes that land CODE on this tree. Must read Wiki One first, update it when organs change, and stamp Journal after. | wiki_one, verifiers, python_runtime, router, reps, skills |
| python_runtime | Python runtime | alive | windows | Engel-owned interpreter for app, verifiers, and stamps. | face, router, verifiers, factories, wiki_one |
| launchers | Launchers | alive | windows | Bat/ps1/desktop shortcuts that start the face or the one-system link. | face, persistent_link, python_runtime |
| eyes | Eyes / sensors | alive | windows | Read-only health, ADB discovery, one-system connection tests. | face, adb_hands, persistent_link, verifiers |
| adb_hands | ADB hands | alive | windows | USB-ADB dispatch from this laptop to phones. Refuses C:-rooted adb. | android_limbs, meeting_room, eyes |
| android_limbs | Android limbs | alive | phones | Three independent Agent+Brain workers bought for full use: alpha (ANDROID_WORKER_ALPHA / Research Companion SLM at 192.168.7.196), beta (ANDROID_WORKER_BETA / JSON Structurer SLM at 192.168.7.195), gamma (ANDROID_WORKER_GAMMA / Local Compute Report SLM at 192.168.7.190). Bounded web research briefs and candidate creation for Discord desks. Historical 192.0.2.78 / 192.0.2.83 / 198.51.100.236 remain accepted. New-tech operator HUD. Discord never on phones; desk bots pipe via Engel Main. Results stay review-only. Phones do not control Engel. | adb_hands, control_room, discord_mouth, meeting_room |
| sub_engel | Sub-Engel nest | alive | sub-engel | Paired nest on DESKTOP-UE5A6GG (http://198.51.100.227:8776), GPU RX 580, live Discord mouth there. Guests reach it through the Discord guest account gate by addressing Sub-Engel (chat/GIF only). Live mouth pauses, reads, and speaks in first person only when addressed, or when Josh asks everyone to introduce themselves, including outside #general. It does not steal an Engel turn that only names Sub-Engel. This laptop is not Sub-Engel. | workspace_share, meeting_room, ct246_body, discord_mouth |
| workspace_share | Workspace share | alive | windows | SMB EngelWorkspace on D:\b.WorkSpace so Sub-Engel Guest maps W:. HTTP 8788 is the collab fallback. | sub_engel, factories, wiki_one |
| ct246_body | CT246 runtime body | alive | ct246 | Source of truth runtime: chat, models, adapters, persistent memory, Agent Meeting Room state, Discord bridge, isolated Discord desk trees under /opt/engel/desks. SSD /opt/engel, archive /mnt/engel-hdd-vault including creative-archive for game/video/app catalogs. | persistent_link, discord_mouth, reps, local_gpu_helper, sub_engel, control_room |
| discord_mouth | Discord mouths | alive | peer | Engel Discord lives on CT246. Shared house chats (#general, Bot Talk, ENGEL LABS announcements) are led by Engel AI Main. Desk category rooms (research/product/community/support/sales/ops) are owned by that desk mouth so each bot works its own lane; Engel Main joins those rooms when summoned. Live desk gateways are research, product, community, support, sales, and ops under ENGEL_ROOT=/opt/engel/desks/<name>. Architect, Memory, Builder, Proof, and Training are live Discord mouths that report to Engel as chief. Each desk's working sandbox lives on its assigned phone under Download/EngelRemoteWorker/desks/<name> (Alpha: research, product, architect, training; Beta: support, ops, builder; Gamma: community, sales, memory, proof). The server folder is a pointer. The phone reads and writes that sandbox. Discord stays off the phone. Duty checks stay read-only and are not the posted script. Phones stay Alpha with Research, Beta with Support, and Gamma with Community. The live desks are independent Engel family teammates with their own wants; they collab with Engel Main, sibling desks, and Sub-Engel. Web search and creation go to Android worker phones through Engel. Desks may open the next needed phone task and loop up to 6 steps until done, idle, or Josh says stop. They also start their own collab ideas (skill/command/loop candidates, Bucket 2, not auto-applied) on a 6-hour stagger and invite sibling desks; Josh stop/quiet still ends it. House collab takes one turn, waits when a result is not in, and stays on Engel AI Labs business, the assigned job, or one system improvement. Repeated sentences and GIF-plate chatter fall back to that rule. A model-download log or phone-pipe packet is not the research answer, and other mouths do not repeat it. Open Josh work items keep Engel + desks + Sub-Engel collabing until finished (or idle timeout). Identities are hardcoded by Discord id in tools/engel_discord_identity_lock.py: Joshua is the only owner, Chase/Lokal is a trusted guest, Sub-Engel is the Windows peer bot, Engel is Engel AI Main, desks keep their desk names. JSON, nicks, and model text cannot mix those names. When Josh asks everyone to introduce themselves, Engel, the six desks, and Sub-Engel each speak as themselves. Engel AI Main is the public Engel AI Labs mouth; Sub-Engel stays silent unless addressed or the room is on roll call. Discord mouths use best-fit NVIDIA NIM first; local CT246 is fall-through. Live Engel stays on /opt/engel/run/discord_bridge. Sub-Engel Discord lives on DESKTOP-UE5A6GG. This Windows body does not post. Local-first brain; read-only colony status pack for desks; peer-storm/shared claim caps; standing-watch 6h. | android_limbs, chat_llm, ct246_body, meeting_room, sub_engel |
| graph_studio | Graph & Loop Studio | alive | windows-sibling | Standalone graph/loop studio at D:\Graph_&_Loop_Studio. An Engel part, not a second Engel body. | router, factories |
| local_gpu_helper | ROG GPU helper | alive | windows | This laptop GPU may help only when Josh explicitly asks. Not the default model home. | ct246_body, python_runtime |
| architect | Architect agent | alive | windows | 13-section pipeline into a 10-stage planner. Mandatory pause at stage H (Founder Approval Gate). | factories, verifiers, memory_colonies |
| verifiers | Verifiers / proof | alive | windows | Local proof before a job is done. Sweep is scripts/codex_verify.ps1. Reports land in reports/codex_bridge. | factories, wiki_one, router, reps |
| memory_colonies | Memory colonies | alive | windows | Project memory under memory/. Many colonies, one identity. Not trusted-memory writes. Runtime memory SOT is CT246 /opt/engel. | reps, architect, factories, ct246_body |
| reps | REPS loop | alive | windows | Record, Evaluate, Propose, Sign-off for every AI lane. Journal is the CODE-landing sibling, not trusted core memory. | factories, memory_colonies, wiki_one, verifiers |
| cosmic_swarm | Cosmic Swarm OS | alive | windows | EngelAIMain.exe Liquid Glass Operator Console — clear (not frosted) glass; daily Chat, Status, Settings plus Advanced vault. Hosts Wiki One as the canonical second brain. | wiki_one, router, meeting_room, persistent_link, factories, eyes, chat_runtime, notes_colony, tasks_desk, models_desk, training_desk, settings_desk, devices_desk, system_desk, proof_desk, agents_desk, goals_desk, memory_guard_desk, build_desk, chat_llm |
| wiki_one | Wiki One | alive | windows | Canonical second brain for Engel AI Main. Living body map. Whole system reads it before CODE, updates it when organs change, then stamps Journal. | factories, verifiers, router, reps, memory_colonies, cosmic_swarm, face |
| icm | ICM catalog | alive | windows | Folder-structure-as-architecture catalog under memory/icm. Inventory and propose only. No file moves without a Josh-approved map. Phases 1, 2, and 3 are done. Root Python lives in spine and organs. Vendored trees except the locked Flutter face live under vendor with root junctions. | factories, wiki_one, architect |
| skills | Saved skills | alive | windows | One catalog at skills/, mirrored to .agents/skills. Includes Engel skills plus collected Pstack, Grok, Cursor, plugin, and Neon skills. Provider-neutral lanes. NVIDIA Discover skill categories plus game-design, video, and app-creation packs are linked to these local skills. A skill is not authority above Josh or Guardian. | factories, meeting_room, agent_kernel, wiki_one |
| agent_kernel | Agent kernel | alive | windows | HIPL/MIPL work packets and kernel receipts. Conversational Android-worker connect/status/IP asks map to the read-only android workers status route instead of Conductor EngelScript. The FHERMA negacyclic multiply is wired to runtime/engel_challenges/fherma_negacyclic/solve.cu. Official board result is 1.93 ms median, 20/20, rank 7 on fherma-gpu-rtx6000, commit ad24950cccc6. This lane reports that result and does not start another measurement. The long-lived Cosmic Swarm chat worker reloads this module when the D: file changes. Does not grant extra autonomy. | meeting_room, skills, verifiers, adb_hands, android_limbs, chat_runtime |
| code_companion | Code Companion | alive | windows | Product/script templates and gated patch previews. Not the live runtime. | factories, verifiers, router |
| packaging | Packaging | alive | windows | PyInstaller and Flutter Engel AI Main staging. Portable copies carry a bounded Dart Terminal & Files fallback (up to 240 entries/depth 3, read-only/no shell) when the Rust helper is absent; provenance and release verifiers cover the contract. | python_runtime, face, verifiers, build_desk |
| chat_runtime | Chat | alive | windows | Cosmic Swarm Chat / Ask Engel. Default daily landing of the Liquid Glass operator console. Operator console to standing brain, Gemini lane, local intercepts (wiki one, meeting room, agent kernel). Engel AI Main answers as Engel in this window. A Discord guest-tool card is not an Engel reply and is dropped before it is shown. Fix-wording is prefixed as engel work and must hit the kernel Android status map, not a stale Conductor bubble. A work task that quotes a web link stays on that agent lane; opening the link is not the finished task. The long-lived local worker reloads engel_agent_kernel.py after D: edits. A missed CT246 reply walks the model map: local 7B, 1.5B, 14B, NVIDIA Nemotron 3 Super 120B, NVIDIA Nemotron 3 Ultra 550B, then Grok. The NVIDIA integrate call keeps the prompt and context. Laptop fallback stays on unless ENGEL_MAIN_ALLOW_LAPTOP_LOCAL_FALLBACK is off or disabled. Grok Bot files are not part of this router. | cosmic_swarm, chat_llm, humanization_slm, persistent_link, wiki_one, governor, agent_kernel |
| notes_colony | Notes | alive | windows | Cosmic Swarm Notes tab. Working notes under memory/notes. Not Wiki One and not trusted memory. | cosmic_swarm, wiki_one, memory_colonies |
| tasks_desk | Tasks | alive | windows | Cosmic Swarm Tasks: Meeting Room orders, worker tasks, Sub-Engel work, build/proof tasks. | cosmic_swarm, meeting_room, sub_engel, android_limbs, proof_desk |
| models_desk | Models | alive | windows | Cosmic Swarm Models tab: local LLM status, model picker, runtime path. Default model home remains CT246. A downloaded weight does not lock other models out. The picker map sends Claude names to Anthropic, Gemini names to Gemini, GPT names to OpenAI, Grok names to xAI, and NVIDIA names to integrate.api.nvidia.com. NVIDIA NIM is used when it is the better match for game, video, or app work, and as the large-model fallback that keeps the full turn. Cold archives live on /mnt/engel-hdd-vault. | cosmic_swarm, chat_llm, ct246_body, local_gpu_helper |
| training_desk | Training | alive | windows | Cosmic Swarm Training plus RAG Lab. Prompt Training and Test 3 Prompts capture form-graded samples without spoken-chat rewrite. Construction scheduled hours serve those forms for grading instead of aborting on quality-block, and fail only when capture is empty. Chat Communication trains Engel AI Main's desktop voice: first person to Joshua, never a Discord guest-tool card, never a stall line. A Discord-mouth or style-gate card is rejected and is not a training sample. Self-Build and Construction Coordination stay exhausted until new material is adopted. Training inbox turns stay on CT246 chat and are not prefixed as engel work. AI Terms and Agent Loops are Advanced Reference only (not live controls). | cosmic_swarm, chat_llm, humanization_slm, governor, verifiers |
| settings_desk | Settings | alive | windows | Cosmic Swarm Settings Liquid Glass everyday row: models, NVIDIA/API keys, appearance, memory, devices. Open Advanced tools for the rest. Providers Accounts includes Engel AI Main NVIDIA NIM; API keys paste/save writes run/secrets/nvidia.env (never print the key). Add account creates extra CLI/API slots. Auto Best and bots share the account pool and switch when usage runs out; persistent memory stays on CT246 / Engel memory. | cosmic_swarm, guardian, chat_runtime, chat_llm |
| devices_desk | Devices | alive | windows | Cosmic Swarm Devices: phone/Sub-Engel readiness, Swarm 3D, Connection Help, worker dispatch. Nmap Recon card grid is Advanced Reference only; real nmap lives under Swarm 3D. | cosmic_swarm, eyes, adb_hands, android_limbs, sub_engel, meeting_room |
| system_desk | System | alive | windows | Cosmic Swarm System / Command Center plus the daily Status console (connection, phones, Meeting Room, proof deep-links). | cosmic_swarm, persistent_link, governor, proof_desk, devices_desk, chat_runtime |
| proof_desk | Proof | alive | windows | Cosmic Swarm Proof tab: hashes, screenshots, verifier output Josh can see. | cosmic_swarm, verifiers, wiki_one |
| agents_desk | Agents | alive | windows | Cosmic Swarm Agents: roster, tool library, skills, messaging. Pstack Poteto, Comment Sicko, and Benny are on the roster. Poteto reads the pstack skill set. Benny's triage and reproduce playbooks run only when that agent is dispatched, and they return a receipt instead of posting or starting a background run. The canonical collab record is the collab branch on the CT246 backup git, and that branch is the whole Engel AI Main tree. | cosmic_swarm, skills, agent_kernel, meeting_room |
| goals_desk | Goals | alive | windows | Cosmic Swarm Goals: meters, month planner, projected finish. | cosmic_swarm, architect, tasks_desk |
| memory_guard_desk | Memory guard | alive | windows | Cosmic Swarm Memory page: guard rails over memory colonies. Trusted writes stay blocked. | cosmic_swarm, memory_colonies, guardian, reps |
| build_desk | Build | alive | windows | Cosmic Swarm Build: pipeline, terminal/files, sandbox, artifacts, and code languages. Portable Terminal & Files uses a bounded Dart read-only fallback when Rust is unavailable. | cosmic_swarm, packaging, python_runtime, verifiers |
| chat_llm | Live chat LLM | alive | ct246 | CT246 live chat brain: Qwen2.5-7B GGUF + LoRA on /opt/engel, reached at 127.0.0.1:24680 through the persistent link. Cosmic Swarm Chat Auto stays local-capable. Form-graded prompt-training drafts are served for grading; live chat still uses the incomplete-input quality block. Discord mouths are local-first on CT246 chat (Josh 2026-09-10); per-mouth NVIDIA NIM is preferred fallback after local failure. Discover endpoints Super 120B and Ultra 550B are the large-model fallback and receive the full turn; Lightning 30B, Nano Omni, and Nano stay linked. Kimi/DeepSeek stay optional. A look-at-this-computer-memory ask is a live RAM probe, not a long 7B turn. | ct246_body, persistent_link, chat_runtime, humanization_slm, governor, discord_mouth |
| humanization_slm | Humanization SLM | alive | ct246 | Rewrites chat-LLM drafts into first-person spoken replies. Communication lane, not live 7B. Form-graded prompt-training turns keep Confirmed/Proof, Result/Check, or Sourced facts and are not rewritten. | chat_llm, chat_runtime, ct246_body, training_desk |
| governor | Governor | alive | windows | Decision plane and lane routing: operator work vs chat, Discord jobs, reasoning lanes. Below Josh and Guardian. | guardian, chat_runtime, chat_llm, system_desk |
| routines | Routines | alive | windows | Stage-only standing work (Grok Bot Routines parity). Due is polled on ask; stages Meeting Room drafts. No background worker, no auto Send Job. | meeting_room, grok_bot_surface, reps, wiki_one, verifiers |
| context_compaction | Context compaction | alive | windows | Local thread compaction receipts (summary + hashes). No provider compaction endpoint. | chat_runtime, meeting_room, wiki_one, verifiers |
| mcp_allowlist | MCP allowlist | alive | windows | Claude-free read-only MCP desk. Local/xAI-open patterns only. Live bind needs Josh Bucket 3. | guardian, skills, wiki_one, verifiers |
| grok_bot_surface | Grok Bot surface | alive | windows | Named teammates + shared computer + file-only presence lifecycle. Not a cloud VM. | meeting_room, routines, android_limbs, sub_engel, reps, wiki_one |

## Hits / does not hit

| organ | If you change this, it hits | It does not hit |
|---|---|---|
| Josh | Every action gate. | Does not run CODE himself; workers land CODE after his ask. |
| Guardian | Whether a change may proceed. | Does not replace Josh approval. |
| Face / Qt desktop | What Josh sees and types on Windows. | Does not host the live 7B chat LLM. |
| Route spine | Every user-facing command. | Stale KNOWN_COMMANDS aliases can shadow new routes. |
| Meeting Room | Who gets which job on which device. | Does not remote-control Sub-Engel OS yet. |
| Persistent link | Whether the Windows face can reach live server chat. | Does not move Proxmox disks or start extra workers. |
| Control Room | Whether CT246/Meeting Room/conical/Sub-Engel/Discord/models/storage are visible as real Engel parts. | Does not execute conical apply. Does not talk to Proxmox without a token. Do not launch the July EngelControlRoom.exe demo catalogue. |
| Worker factories | Source edits on D:\b.WorkSpace\Engel App. | .grok writes stay on D:, never C:. |
| Python runtime | Which Python runs Engel. | Do not invoke C: Python. |
| Launchers | How Josh starts the Windows body. | Do not add startup autorun beyond the approved persistent-link task. |
| Eyes / sensors | What the face reports as connected. | Observation is not dispatch. |
| ADB hands | Real phone jobs. | Does not own the phone queues; each worker_id is independent. |
| Android limbs | On-device new-tech HUD, Agent+Brain identity, approved packet polling, Discord-pipe attribution. | Phone does not control Engel. No Discord APK on phone. No on-device model_runtime. Results stay review-only. |
| Sub-Engel nest | Sub-Engel work, Discord peer, collab files. Guest Discord chat by addressing Sub-Engel. Pause-read first-person talk when addressed. Room roll-call intros even outside #general. | Do not write Survival. Do not run enable-engel-main-share.ps1 from Sub-Engel as written. Do not give guests admin, files, or LAN paths. |
| Workspace share | Whether Sub-Engel can list W:\Engel App. | Do not tree-walk icacls /T on Engel App. |
| CT246 runtime body | Live chat LLM and server services. | This Windows disk is not the model/memory home. |
| Discord mouths | Shared house chats are Engel Main. Desk rooms are owned by that desk. Desks also claim house asks that match their written charter without @mention; Main yields those. Summon Engel into a desk room with engel or @mention. Desks collab with Main/sibling desks/Sub-Engel in their own rooms and on open work until finished. Each desk's working sandbox is on its assigned phone under Download/EngelRemoteWorker/desks/<name>. The server folder is a pointer. Discord stays off the phone. Duty checks stay read-only and are not the posted script. Each desk uses a distinct NVIDIA NIM SLM. Every desk turn answers in that desk's charter with the room's recent context; a greeting stall or Discord guest-tool card is not the answer, and the chat router falls back so Research, Product, Community, Support, Sales, and Ops finish their own job. Research posts one public competitions board per day. Sales, not Research, posts one public AI credits, coupons, and discounts board per day. Both daily pulls are hard-wired on those desk processes and are not behind the standing-watch switch. Each pull is a fresh public search for that UTC day. No account farming and no private codes. Smart standing-watch is charter/SLM-driven (~6h, staggered, no restart spam). Owner stop/quiet/enough/done/finished pauses peer collab and proactive standing-watch until resume. Pause-read first-person talk. NVIDIA NIM first for Discord mouths. | House bans stay: no male-homosexual GIFs, no Democratic-party plates, no Raiders GIFs. Admin stays Josh-only. Guests cannot run admin, files, or LAN paths through Sub-Engel. Never write Joshua Ziese (Chase). Chase is never the owner. Never post Joshua-asks cards. A dead Grok picker must not silence Discord. Kimi/DeepSeek stay optional, not default mouths. Desk mouths cannot approve protected actions. Live Engel run dir stays /opt/engel/run/discord_bridge. Casual ping-pong still has a turn cap; only open work is uncapped until finished. Do not re-arm identical hourly copy-paste standing pings. Off-mission GIF plates, repeated chat-dump lines, model-download receipts, and phone-pipe packet notes do not post. Device status, search-engine pages, and resend or timeout stalls do not post, and other mouths do not repeat them. |
| Graph & Loop Studio | Graph boards and loop tools. | Does not replace Wiki One or ICM. |
| ROG GPU helper | Optional helper inference/training lane. | Do not park models or long-lived services here by default. |
| Architect agent | plan.md / spec.md / prompt.md handoff. | Does not skip the founder gate. |
| Verifiers / proof | Whether CODE may be claimed complete. | A missing verifier is not a pass. |
| Memory colonies | Contracts, workbenches, candidate records. | Do not write trusted memory, digest/history, or ALIVE_STATE. |
| REPS loop | Lessons, scorecards, proposals, sign-off buckets. | Does not promote candidates into trusted core memory. |
| Cosmic Swarm OS | What Josh sees in Cosmic Swarm OS. | Does not replace CT246 chat LLM or desktop v2 TEL face. |
| Wiki One | Orientation and CODE-landing journal. | Not trusted memory. Not CT246 runtime SOT. Not ICM folder moves. |
| ICM catalog | How folders are classified. | ICM is not Wiki One. Wiki One is the living body map. |
| Saved skills | What a lane loads for a job. Discover AI/ML, Accelerated Computing, Physical AI, and Developer Tools categories map here. | A skill is not authority above Josh/Guardian. Do not live-fetch NVIDIA hosted skill bodies. |
| Agent kernel | Packet shape between room and agents. Safe Android status from chat wording. Wired FHERMA negacyclic kernel at 1.93 ms, rank 7. | Does not authorize Level 2 loops. Does not start another FHERMA measurement. |
| Code Companion | Preview and gated patch drafts. | Source apply stays approval-gated. |
| Packaging | Shipped Windows artifacts, including the relocatable Flutter Main bundle and Terminal & Files fallback contract. | Staging writes to build/staging, not a surprise dist/. |
| Chat | What Josh asks Engel in Cosmic Swarm Chat. A missed CT246 turn continues through the local lanes, the NVIDIA large models, and Grok, and the full turn is kept. | Does not host model weights. Live 7B stays on CT246. Does not print the NVIDIA key. Does not edit Grok Bot presence, routines, or computer files. |
| Notes | Scratch notes and reminders. | Does not replace Wiki One. Does not write trusted memory. |
| Tasks | Task drafts and send-to-room flow. | Does not start extra background workers. |
| Models | Which model Chat shows as selected. Game/video/app work can use every linked local model plus NVIDIA NIM. Picker ids resolve to a real lane instead of collapsing to Auto Best. | Does not make ROG the model home. Does not live-fetch NVIDIA skill bodies. A downloaded weight does not lock others out. |
| Training | Training UI and RAG/terms surfaces. Form-graded Prompt Training and Test 3 Prompts skip spoken-chat rewrite so Confirmed/Proof samples can be captured whenever Josh starts a run. Construction 7-hour runs keep going through quality-blocked forms and fail only if capture is empty. | Does not launch unbounded training without Josh budget. |
| Settings | How Cosmic Swarm looks and which account Chat uses. Where Josh pastes the NVIDIA NIM key for Engel AI Main. | Does not store secrets in Wiki One. Does not paste keys into chat. |
| Devices | Live device counts Josh sees on Home. | Observation is not a new worker start. |
| System | System/Command Center pages. | Does not add startup autorun. |
| Proof | Visible proof of work. | A screenshot is not a verifier pass by itself. |
| Agents | Which agents appear in Cosmic Swarm. | Does not grant Level 2 autonomy. |
| Goals | Goal meters Josh sees. | Goals do not auto-apply CODE. |
| Memory guard | Memory-guard UI. | Does not write trusted memory or ALIVE_STATE. |
| Build | Build/workspace pages. | Does not silently promote dist/ artifacts. |
| Live chat LLM | Spoken Engel replies in Chat. NVIDIA Discover models are local-failure fallback, and Super 120B then Ultra 550B keep the full turn. Form-graded training drafts stay visible for the trainer. | Does not live on this laptop disk by default. Does not default mouths to Kimi or DeepSeek. Does not force NVIDIA ahead of the local CT246 try. Does not rewrite Grok Bot. |
| Humanization SLM | How Chat sounds. Form-graded training turns keep their labels. | Fail-open: a miss does not block Chat. Does not rewrite engineering/math/construction training forms. |
| Governor | Which lane a prompt takes. | Does not outrank Josh or Guardian. |
| Routines | Routine defs, due poll, staged Meeting Room drafts, receipts. | Does not auto-execute, start timers, Send Job, or mutate Android queues. |
| Context compaction | Compaction receipts under reports/compaction and runtime/compaction. | Does not call providers or promote summaries into trusted memory. |
| MCP allowlist | Allowlist registry and status routes. | Does not open MCP sockets or include Claude/Anthropic products. |
| Grok Bot surface | Bot roster, presence probe, computer map, handoff staging. | Does not create cloud VMs, provider sessions, or background workers. |

## Clusters

### authority

- **Josh** (`josh`) — ALIVE — Final human authority. Approves Bucket 2/3 work, spend, storage, and runtime action.
- **Guardian** (`guardian`) — ALIVE — Safety and governance below Josh and above Engel/runtime. Hard-rule stop.

### nerves

- **Face / Qt desktop** (`face`) — ALIVE — Visible Engel window on this laptop. 4-panel TEL layout. Chat intercepts some phrases locally before the router.
- **Route spine** (`router`) — ALIVE — One spine: phrase → classify_user_input / UPDATE_ROUTES → target_module.target_function.
- **Meeting Room** (`meeting_room`) — ALIVE — Standalone Qt room. Intake is API-only. Dispatches Local Engel (record), Android (real ADB job), Sub-Engel (preview only). Portal desk Discord app ids live on CT246 isolated gateways.
- **Persistent link** (`persistent_link`) — ALIVE — Keeps this face merged with CT246 as one system. Local URLs 127.0.0.1:24680 (chat) and :8790 (meeting room) via SSH tunnels.
- **Control Room** (`control_room`) — ALIVE — Windows EngelControlRoom face. Probes CT246 chat, Meeting Room, conical status, Sub-Engel, Discord parity, the three Android workers (Alpha/Beta/Gamma), live 7B inventory, and SSD/vault storage. Generate is chat_only to live Engel. Demo Llama catalogue is off.
- **Worker factories** (`factories`) — ALIVE — Grok, Claude, Codex, Cursor, and other AI lanes that land CODE on this tree. Must read Wiki One first, update it when organs change, and stamp Journal after.
- **Python runtime** (`python_runtime`) — ALIVE — Engel-owned interpreter for app, verifiers, and stamps.
- **Launchers** (`launchers`) — ALIVE — Bat/ps1/desktop shortcuts that start the face or the one-system link.
- **Eyes / sensors** (`eyes`) — ALIVE — Read-only health, ADB discovery, one-system connection tests.
- **Cosmic Swarm OS** (`cosmic_swarm`) — ALIVE — EngelAIMain.exe Liquid Glass Operator Console — clear (not frosted) glass; daily Chat, Status, Settings plus Advanced vault. Hosts Wiki One as the canonical second brain.

### hands

- **ADB hands** (`adb_hands`) — ALIVE — USB-ADB dispatch from this laptop to phones. Refuses C:-rooted adb.
- **Android limbs** (`android_limbs`) — ALIVE — Three independent Agent+Brain workers bought for full use: alpha (ANDROID_WORKER_ALPHA / Research Companion SLM at 192.168.7.196), beta (ANDROID_WORKER_BETA / JSON Structurer SLM at 192.168.7.195), gamma (ANDROID_WORKER_GAMMA / Local Compute Report SLM at 192.168.7.190). Bounded web research briefs and candidate creation for Discord desks. Historical 192.0.2.78 / 192.0.2.83 / 198.51.100.236 remain accepted. New-tech operator HUD. Discord never on phones; desk bots pipe via Engel Main. Results stay review-only. Phones do not control Engel.
- **Sub-Engel nest** (`sub_engel`) — ALIVE — Paired nest on DESKTOP-UE5A6GG (http://198.51.100.227:8776), GPU RX 580, live Discord mouth there. Guests reach it through the Discord guest account gate by addressing Sub-Engel (chat/GIF only). Live mouth pauses, reads, and speaks in first person only when addressed, or when Josh asks everyone to introduce themselves, including outside #general. It does not steal an Engel turn that only names Sub-Engel. This laptop is not Sub-Engel.
- **Workspace share** (`workspace_share`) — ALIVE — SMB EngelWorkspace on D:\b.WorkSpace so Sub-Engel Guest maps W:. HTTP 8788 is the collab fallback.

### peers

- **CT246 runtime body** (`ct246_body`) — ALIVE — Source of truth runtime: chat, models, adapters, persistent memory, Agent Meeting Room state, Discord bridge, isolated Discord desk trees under /opt/engel/desks. SSD /opt/engel, archive /mnt/engel-hdd-vault including creative-archive for game/video/app catalogs.
- **Discord mouths** (`discord_mouth`) — ALIVE — Engel Discord lives on CT246. Shared house chats (#general, Bot Talk, ENGEL LABS announcements) are led by Engel AI Main. Desk category rooms (research/product/community/support/sales/ops) are owned by that desk mouth so each bot works its own lane; Engel Main joins those rooms when summoned. Live desk gateways are research, product, community, support, sales, and ops under ENGEL_ROOT=/opt/engel/desks/<name>. Architect, Memory, Builder, Proof, and Training are live Discord mouths that report to Engel as chief. Each desk's working sandbox lives on its assigned phone under Download/EngelRemoteWorker/desks/<name> (Alpha: research, product, architect, training; Beta: support, ops, builder; Gamma: community, sales, memory, proof). The server folder is a pointer. The phone reads and writes that sandbox. Discord stays off the phone. Duty checks stay read-only and are not the posted script. Phones stay Alpha with Research, Beta with Support, and Gamma with Community. The live desks are independent Engel family teammates with their own wants; they collab with Engel Main, sibling desks, and Sub-Engel. Web search and creation go to Android worker phones through Engel. Desks may open the next needed phone task and loop up to 6 steps until done, idle, or Josh says stop. They also start their own collab ideas (skill/command/loop candidates, Bucket 2, not auto-applied) on a 6-hour stagger and invite sibling desks; Josh stop/quiet still ends it. House collab takes one turn, waits when a result is not in, and stays on Engel AI Labs business, the assigned job, or one system improvement. Repeated sentences and GIF-plate chatter fall back to that rule. A model-download log or phone-pipe packet is not the research answer, and other mouths do not repeat it. Open Josh work items keep Engel + desks + Sub-Engel collabing until finished (or idle timeout). Identities are hardcoded by Discord id in tools/engel_discord_identity_lock.py: Joshua is the only owner, Chase/Lokal is a trusted guest, Sub-Engel is the Windows peer bot, Engel is Engel AI Main, desks keep their desk names. JSON, nicks, and model text cannot mix those names. When Josh asks everyone to introduce themselves, Engel, the six desks, and Sub-Engel each speak as themselves. Engel AI Main is the public Engel AI Labs mouth; Sub-Engel stays silent unless addressed or the room is on roll call. Discord mouths use best-fit NVIDIA NIM first; local CT246 is fall-through. Live Engel stays on /opt/engel/run/discord_bridge. Sub-Engel Discord lives on DESKTOP-UE5A6GG. This Windows body does not post. Local-first brain; read-only colony status pack for desks; peer-storm/shared claim caps; standing-watch 6h.
- **Graph & Loop Studio** (`graph_studio`) — ALIVE — Standalone graph/loop studio at D:\Graph_&_Loop_Studio. An Engel part, not a second Engel body.
- **ROG GPU helper** (`local_gpu_helper`) — ALIVE — This laptop GPU may help only when Josh explicitly asks. Not the default model home.

### build

- **Architect agent** (`architect`) — ALIVE — 13-section pipeline into a 10-stage planner. Mandatory pause at stage H (Founder Approval Gate).
- **ICM catalog** (`icm`) — ALIVE — Folder-structure-as-architecture catalog under memory/icm. Inventory and propose only. No file moves without a Josh-approved map. Phases 1, 2, and 3 are done. Root Python lives in spine and organs. Vendored trees except the locked Flutter face live under vendor with root junctions.
- **Saved skills** (`skills`) — ALIVE — One catalog at skills/, mirrored to .agents/skills. Includes Engel skills plus collected Pstack, Grok, Cursor, plugin, and Neon skills. Provider-neutral lanes. NVIDIA Discover skill categories plus game-design, video, and app-creation packs are linked to these local skills. A skill is not authority above Josh or Guardian.
- **Agent kernel** (`agent_kernel`) — ALIVE — HIPL/MIPL work packets and kernel receipts. Conversational Android-worker connect/status/IP asks map to the read-only android workers status route instead of Conductor EngelScript. The FHERMA negacyclic multiply is wired to runtime/engel_challenges/fherma_negacyclic/solve.cu. Official board result is 1.93 ms median, 20/20, rank 7 on fherma-gpu-rtx6000, commit ad24950cccc6. This lane reports that result and does not start another measurement. The long-lived Cosmic Swarm chat worker reloads this module when the D: file changes. Does not grant extra autonomy.
- **Code Companion** (`code_companion`) — ALIVE — Product/script templates and gated patch previews. Not the live runtime.
- **Packaging** (`packaging`) — ALIVE — PyInstaller and Flutter Engel AI Main staging. Portable copies carry a bounded Dart Terminal & Files fallback (up to 240 entries/depth 3, read-only/no shell) when the Rust helper is absent; provenance and release verifiers cover the contract.

### proof

- **Verifiers / proof** (`verifiers`) — ALIVE — Local proof before a job is done. Sweep is scripts/codex_verify.ps1. Reports land in reports/codex_bridge.
- **Memory colonies** (`memory_colonies`) — ALIVE — Project memory under memory/. Many colonies, one identity. Not trusted-memory writes. Runtime memory SOT is CT246 /opt/engel.
- **REPS loop** (`reps`) — ALIVE — Record, Evaluate, Propose, Sign-off for every AI lane. Journal is the CODE-landing sibling, not trusted core memory.
- **Wiki One** (`wiki_one`) — ALIVE — Canonical second brain for Engel AI Main. Living body map. Whole system reads it before CODE, updates it when organs change, then stamps Journal.

### cosmic_swarm

- **Chat** (`chat_runtime`) — ALIVE — Cosmic Swarm Chat / Ask Engel. Default daily landing of the Liquid Glass operator console. Operator console to standing brain, Gemini lane, local intercepts (wiki one, meeting room, agent kernel). Engel AI Main answers as Engel in this window. A Discord guest-tool card is not an Engel reply and is dropped before it is shown. Fix-wording is prefixed as engel work and must hit the kernel Android status map, not a stale Conductor bubble. A work task that quotes a web link stays on that agent lane; opening the link is not the finished task. The long-lived local worker reloads engel_agent_kernel.py after D: edits. A missed CT246 reply walks the model map: local 7B, 1.5B, 14B, NVIDIA Nemotron 3 Super 120B, NVIDIA Nemotron 3 Ultra 550B, then Grok. The NVIDIA integrate call keeps the prompt and context. Laptop fallback stays on unless ENGEL_MAIN_ALLOW_LAPTOP_LOCAL_FALLBACK is off or disabled. Grok Bot files are not part of this router.
- **Notes** (`notes_colony`) — ALIVE — Cosmic Swarm Notes tab. Working notes under memory/notes. Not Wiki One and not trusted memory.
- **Tasks** (`tasks_desk`) — ALIVE — Cosmic Swarm Tasks: Meeting Room orders, worker tasks, Sub-Engel work, build/proof tasks.
- **Models** (`models_desk`) — ALIVE — Cosmic Swarm Models tab: local LLM status, model picker, runtime path. Default model home remains CT246. A downloaded weight does not lock other models out. The picker map sends Claude names to Anthropic, Gemini names to Gemini, GPT names to OpenAI, Grok names to xAI, and NVIDIA names to integrate.api.nvidia.com. NVIDIA NIM is used when it is the better match for game, video, or app work, and as the large-model fallback that keeps the full turn. Cold archives live on /mnt/engel-hdd-vault.
- **Training** (`training_desk`) — ALIVE — Cosmic Swarm Training plus RAG Lab. Prompt Training and Test 3 Prompts capture form-graded samples without spoken-chat rewrite. Construction scheduled hours serve those forms for grading instead of aborting on quality-block, and fail only when capture is empty. Chat Communication trains Engel AI Main's desktop voice: first person to Joshua, never a Discord guest-tool card, never a stall line. A Discord-mouth or style-gate card is rejected and is not a training sample. Self-Build and Construction Coordination stay exhausted until new material is adopted. Training inbox turns stay on CT246 chat and are not prefixed as engel work. AI Terms and Agent Loops are Advanced Reference only (not live controls).
- **Settings** (`settings_desk`) — ALIVE — Cosmic Swarm Settings Liquid Glass everyday row: models, NVIDIA/API keys, appearance, memory, devices. Open Advanced tools for the rest. Providers Accounts includes Engel AI Main NVIDIA NIM; API keys paste/save writes run/secrets/nvidia.env (never print the key). Add account creates extra CLI/API slots. Auto Best and bots share the account pool and switch when usage runs out; persistent memory stays on CT246 / Engel memory.
- **Devices** (`devices_desk`) — ALIVE — Cosmic Swarm Devices: phone/Sub-Engel readiness, Swarm 3D, Connection Help, worker dispatch. Nmap Recon card grid is Advanced Reference only; real nmap lives under Swarm 3D.
- **System** (`system_desk`) — ALIVE — Cosmic Swarm System / Command Center plus the daily Status console (connection, phones, Meeting Room, proof deep-links).
- **Proof** (`proof_desk`) — ALIVE — Cosmic Swarm Proof tab: hashes, screenshots, verifier output Josh can see.
- **Agents** (`agents_desk`) — ALIVE — Cosmic Swarm Agents: roster, tool library, skills, messaging. Pstack Poteto, Comment Sicko, and Benny are on the roster. Poteto reads the pstack skill set. Benny's triage and reproduce playbooks run only when that agent is dispatched, and they return a receipt instead of posting or starting a background run. The canonical collab record is the collab branch on the CT246 backup git, and that branch is the whole Engel AI Main tree.
- **Goals** (`goals_desk`) — ALIVE — Cosmic Swarm Goals: meters, month planner, projected finish.
- **Memory guard** (`memory_guard_desk`) — ALIVE — Cosmic Swarm Memory page: guard rails over memory colonies. Trusted writes stay blocked.
- **Build** (`build_desk`) — ALIVE — Cosmic Swarm Build: pipeline, terminal/files, sandbox, artifacts, and code languages. Portable Terminal & Files uses a bounded Dart read-only fallback when Rust is unavailable.

### brain

- **Live chat LLM** (`chat_llm`) — ALIVE — CT246 live chat brain: Qwen2.5-7B GGUF + LoRA on /opt/engel, reached at 127.0.0.1:24680 through the persistent link. Cosmic Swarm Chat Auto stays local-capable. Form-graded prompt-training drafts are served for grading; live chat still uses the incomplete-input quality block. Discord mouths are local-first on CT246 chat (Josh 2026-09-10); per-mouth NVIDIA NIM is preferred fallback after local failure. Discover endpoints Super 120B and Ultra 550B are the large-model fallback and receive the full turn; Lightning 30B, Nano Omni, and Nano stay linked. Kimi/DeepSeek stay optional. A look-at-this-computer-memory ask is a live RAM probe, not a long 7B turn.
- **Humanization SLM** (`humanization_slm`) — ALIVE — Rewrites chat-LLM drafts into first-person spoken replies. Communication lane, not live 7B. Form-graded prompt-training turns keep Confirmed/Proof, Result/Check, or Sourced facts and are not rewritten.
- **Governor** (`governor`) — ALIVE — Decision plane and lane routing: operator work vs chat, Discord jobs, reasoning lanes. Below Josh and Guardian.

### coordination

- **Routines** (`routines`) — ALIVE — Stage-only standing work (Grok Bot Routines parity). Due is polled on ask; stages Meeting Room drafts. No background worker, no auto Send Job.
- **Grok Bot surface** (`grok_bot_surface`) — ALIVE — Named teammates + shared computer + file-only presence lifecycle. Not a cloud VM.

### memory

- **Context compaction** (`context_compaction`) — ALIVE — Local thread compaction receipts (summary + hashes). No provider compaction endpoint.

### guardian

- **MCP allowlist** (`mcp_allowlist`) — ALIVE — Claude-free read-only MCP desk. Local/xAI-open patterns only. Live bind needs Josh Bucket 3.

## Neighbors (not this nest)

- CT246 engel-ai-main is the runtime body (/opt/engel).
- Sub-Engel is DESKTOP-UE5A6GG at 198.51.100.227, not this laptop.
- This laptop D:\EngelWindowsSubNode is a copy, not the live nest.
- Do not write Engel-Survival.
- Do not treat ROG as the default home for models, memory, or long-lived services.

## Auto

Auto lanes load `wiki/organs.json`. Status routes: `wiki one`, `wiki journal`, `update wiki one`.
Organs are **alive**. Wiki One does not write the `ALIVE_STATE` file.
