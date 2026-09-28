# Engel AI Main — Handoff Brief (2026-07-11)

Self-contained continuation document for any Claude session (app or Code) picking up this system.
Owner: Joshua Ziese (redacted@example.com). Everything below is LIVE and verified unless marked otherwise.

---

## 1. The system in one paragraph

**Engel AI Main** is Joshua's personal multi-device agentic AI cluster. The whole repo at
`D:\b.WorkSpace\Engel App` (Python + Rust + Flutter) IS the product. A ROG Windows laptop
(192.0.2.40, RTX 2070 8GB) is the controller: it runs the Flutter desktop app, five provider
bridges (Claude/Grok/Codex/ChatGPT/Gemini), a llama.cpp GPU chat server (:8899), and an
sdxl-turbo image server (:8931). The brain is **CT246** — a Debian 12 LXC (192.0.2.50, CPU-only
24-core Xeon, 40GB RAM) on a Proxmox Dell PowerEdge — running the chat service (:8765), Discord
bridge, CPU image engine (:8930), and semantic memory search (:8940). ROG services reach CT246
via persistent SSH reverse tunnels. Three Android phones + a Windows Sub-Engel form a task fleet.

## 2. Access + hard rules

- **CT246 SSH**: `ssh -i C:\Users\ziese\.ssh\engel_ai_main_ct246_ed25519 -p 24622 root@192.0.2.50`
- Deploy pattern: scp changed `tools/*.py` → `/opt/engel/tools/` then `systemctl restart engel-main-chat.service`
  (or `engel-discord-bridge.service`). App-root modules (`engel_large_chat_llm.py`, `engel_llama_cli_runner.py`)
  go to `/opt/engel/`.
- **NEVER**: use C: for temp/cache; run `scripts\Start-EngelMainServerChatService.ps1`; touch
  CT245/PowerVault/engel-vault (offline); enable grok.exe CLI (24880 stays off); print secrets.
- **DIVERGED FILE WARNING**: `engel_llama_cli_runner.py` has DIFFERENT copies on ROG (F:/D: paths)
  and CT246 (/opt/engel paths). Never scp one over the other — port edits to each.
- PowerShell 5.1 quirks: no `&&`, no ternary; complex remote commands → write a `.sh`, scp, run
  (inline quoting through ssh breaks constantly). Strip CR before shipping shell scripts.
- Windows PS scripts must be pure ASCII (em-dashes break PS 5.1 parsing under cp1252).

## 3. Chat routing (CT246 :8765) — the lanes in fire order

1. **BUILD lane** (`_build_lane_receipt`) — "build me a <thing>" → bridges (Codex→Claude→Grok)
   generate multi-file code → `engel_build_lane.py` scaffolds to `/opt/engel/workspaces/` → runs
   non-interactive programs → real output in the reply. **Discord EXCLUDED** (source startswith
   "discord" → falls through; Joshua's call). Kill: `ENGEL_BUILD_LANE_ENABLED=0`. Depth 3.
2. **CODE lane** (`_code_lane_model_receipt`) — explicit code asks → qwen2.5-coder-3b in-process.
   Requires a CLOSED fence (even ``` count ≥2) else falls through. Skips prompts that route to the
   provider-bridge `code_or_review` matrix (stronger reviewers win). Kill: `ENGEL_CODE_LANE_ENABLED=0`. Depth 1.
3. **QUICK lane** — engel-qwen2.5-1.5b-deepreason GGUF in-process (persona-LoRA-tuned, train/serve
   aligned, retrained 2026-07-10 on RunPod loss 1.81→0.19). Persona + facts + semantic recall ride
   extra_system. NT-2 escalation ON (tau 0.62): weak replies escalate to the big lane.
4. **BIG lane** — primary: ROG GPU :8899 via tunnel (Mistral-7B). CPU fallback: qwen2.5-7b +
   vipy LoRA (aligned persona) via `engel_large_chat_llm.py` — guard applies the adapter ONLY when
   base == `ENGEL_TRAINED_LORA_BASE_GGUF_MODEL`. Depth 2.
5. **Provider bridges** (depth 3) — ROG-local, reverse-tunneled to CT246 loopback:
   grok 24881, claude 24883, chatgpt 24885, gemini 24887, codex 24889, **imagine 24890** (added
   2026-07-11 — was missing, memes silently failed).

NT-1 stamps `activation_depth` (0 router / 1 quick+code / 2 big / 3 bridge) on every memory record.
Chat memory: `/opt/engel/memory/persistent_chat/ENGEL_AI_MAIN_LLM_CHAT_MEMORY.jsonl`.
The chat brain is SPLIT: `engel_main_server_chat_http_service.py` (routing/receipts) +
`run_engel_standalone_chat_llm.py` (big-lane run + its OWN memory writer). Touch both for lane work.

## 4. Image/media stack

- **sdxl-turbo GPU lane** — ROG :8931 (gpu_image_venv, torch 2.6 cu124, sequential offload so it
  coexists with :8899 in <1GB VRAM), tunneled to CT246 :8931. ~12s/512px photoreal.
- **sd-turbo CPU fallback** — CT246 :8930.
- **Discord failover** — GPU first (3s health preflight, 120s budget) → CPU (600s). Remote outputs
  fetched via `/file` (GPU-lane paths don't exist on CT246); collision-proof filenames.
- **GIF search FIXED at root (2026-07-11)**: `_download_gif` used `resp.content.read(N)` which
  returns ONE ~16KB buffered chunk, truncating every real GIF → rejected by the 30KB min-size
  check → ALL keyed search silently empty forever. Now `iter_chunked` reads the full body.
  Giphy key is set (`/opt/engel/run/secrets/discord.env`, 0600) and verified: every query returns
  real 1–2MB GIFs. Local GIF library (1195 assets, mostly starwars/vader) serves only on curated
  trigger hits (or 3+ token match) — generic asks go to real search.
- Grok Imagine :24890 (Joshua has Grok MAX plan) + Gemini cover cloud image/video.

## 5. Discord (engel-discord-bridge.service on CT246)

- Bot **application id 1506157762785312808**. Invite URL (needs Manage Server on target):
  `https://discord.com/oauth2/authorize?client_id=1506157762785312808&permissions=379968&scope=bot`
- **Home channel** 1148755186752430163: `REPLY_MODE=all` (answers everything).
- **Any other server**: summon-only (@mention or "engel …" prefix). Toggle off:
  `ENGEL_DISCORD_OPEN_TO_MENTIONS=0`.
- **Bounded AI-to-AI mode (LIVE)**: Engel converses with Chase's AI **"Tel"**
  (bot id 1483970038804385952) in channel 1489749597365600390 (guild 1489749596463693854),
  capped at 6 consecutive exchanges, 8s cooldown, ANY human message resets the counter.
  Config lines in discord.env: `ENGEL_DISCORD_PEER_BOT_IDS / PEER_CHANNEL_IDS / PEER_MAX_TURNS /
  PEER_COOLDOWN_SECONDS`. Verified 7/7 in simulation.
- Build lane is blocked for Discord; GIFs/media/chat/code-as-text all work.

## 6. Cosmos3 world models (all four usable)

NF4-quantized on RunPod 2026-07-10/11 (~$6.30 total), artifacts on CT246
`/opt/engel/models-active/hf/cosmos3/`: Nano-NF4 (12G, also on ROG `runtime\gpu_models\`),
Super-NF4 (37G), Super-Text2Image-NF4 (37G), Super-Image2Video-NF4 (36G). Native diffusers
pipeline: `Cosmos3OmniPipeline` (num_frames=1→image, >1→video, image=→i2v, enable_sound).
bf16 originals (~436G incl. un-quantized Nano-Policy-DROID) archived per-file-verified to
`/mnt/engel-hdd-vault/models-archive/cosmos3-originals/`. SSD now 37% used (589G free).
- **Local**: Nano runs on the 2070 — 56.5 min/image (spills past 8GB VRAM). Batch lane only.
  Interactive local needs a 24GB GPU (used RTX 3090 ~$700 in the PowerEdge → est 1-2 min/image).
- **RunPod is OFF by policy** (0 pods, ~$27 balance idle). `tools/engel_cosmos3_generate.py`
  (run/create-pod/generate/stop) is break-glass tooling only. Sanctioned RunPod use: LoRA retrains.
- Pod-env gauntlet, if ever re-quantizing: torch==2.6.0 + torchvision==0.21.0 lockstep, purge
  torchaudio/xformers/flash-attn, `enable_safety_checker=False` (guardrail repo is HF-gated),
  output field is `result.video`.

## 7. Other model lanes

- **14B offline gguf**: `/opt/engel/models-active/llm/qwen2.5-14b-instruct/` (8.4G Q4_K_M) — built,
  sanity-verified, NOT routed (~2 tok/s on this CPU). WARNING: the large-chat selector falls back
  to the LARGEST gguf — keep the env pin (drop-in `zzzzz-large-chat-aligned-lora.conf`).
- **Speculative draft (D-lane)**: built (`engel_speculative_draft.py`), benchmarked 0.54× = SLOWER
  on CPU, ships OFF (env-gated `ENGEL_LOCAL_MODEL_DRAFT_GGUF/_TARGET_GGUF`). Don't enable without
  a native llama.cpp speculative runtime.
- Quick-lane retrain flow: `engel_build_training_dataset.py` SYSTEM_PROMPT == served prompt
  (base+guards+style card); canary gate imports the same. RunPod key via DPAPI
  (`Set-EngelRunpodApiKey.ps1` → runtime/runpod/secrets/runpod_api_key.dpapi).

## 8. Stack lifecycle (ROG)

Everything runs ONLY while EngelAIMain.exe is open, hidden. `EngelStackController` task ticks
every minute → starts/stops 10 services incl. `EngelRogGpuModelServer` (:8899),
`EngelRogGpuImageServer` (:8931), `EngelGpuTunnelSvc` (forwards 8899+8931), `EngelChatLinkSvc`
(chat+meeting+office forwards + 5 bridge -R forwards + imagine 24890). Repair/re-register:
`scripts\Setup-EngelStackLifecycle-RunAsAdmin.cmd` (elevated). Controller is TRI-STATE on
process-table reads (unknown ≠ app-closed → never false-teardown). Tunnel gotcha: killing tunnel
parents ORPHANS the ssh (holds the sshd-side forward; ExitOnForwardFailure kills new attempts) —
kill the ssh too; a running PowerShell loop keeps its OLD parsed script, so restart the task to
pick up script edits.

## 9. Secrets

- All keys live in `/opt/engel/run/secrets/*.env` (0600 root) on CT246 or DPAPI blobs on ROG.
- GIF keys: `Add-EngelGifKey.ps1` (console, bulletproof) or `Set-EngelGifSearchKeys.ps1` (window);
  both scp + run `engel_apply_gif_keys.sh` remotely, then LIVE-search verify (RESULT:<n>:<source> —
  only trust green when source != none).
- Vault gotcha: CT246 is an unprivileged LXC — root CANNOT mkdir at the vault ROOT
  (`/mnt/engel-hdd-vault`); use existing writable dirs (models-archive/, training-outputs/, …).
- Cross-fs verify gotcha: `du -sb` false-mismatches ext4→ZFS (dir-entry overhead); verify per-file
  (rsync --dry-run --itemize-changes + summed file bytes).

## 10. Known-good verification commands

```bash
# on CT246 — chat lanes smoke
curl -s -X POST http://127.0.0.1:8765/chat -H 'Content-Type: application/json' \
  -d '{"message":"you good engel","prompt":"you good engel","source":"engel_flutter_main"}'
# build lane (app source builds; discord source must NOT)
# ... same with "build me a python script that prints ..." and source engel_flutter_main
# image lanes: curl :8931/health (GPU via tunnel) and :8930/health (CPU)
# bridges: curl :24883/health (claude) etc.; imagine :24890/health
# NT-1 depths: tail /opt/engel/memory/persistent_chat/ENGEL_AI_MAIN_LLM_CHAT_MEMORY.jsonl
```
Health: `python tools\engel_health_check.py` (run FIRST after any handoff — receipts in
`reports\health_checks\`). Doctor: `tools\engel_doctor.py`.

## 11. Open threads / next candidates

- **Hardware**: used RTX 3090 24GB for the PowerEdge = interactive local Cosmos3-Nano (~1-2 min/img)
  + headroom for every GGUF lane. Measured need: 11.15GB peak.
- Deploy scripts (`Sync-EngelLlmRuntimeToMainCt.ps1`, `Install-EngelActiveModelsToFastSsd.ps1`)
  had criticals fixed (paths, dest-first copy) but two deferred items: drop-in shadowing readback
  (they write low-priority drop-ins that later files override) and adapter-name-from-manifest
  (still hardcodes vipy; next retrain re-introduces staleness).
- Voice: nemotron-0.6b ASR endpoint designed but unbuilt (no voice UI consumer yet).
- Streaming path is not code/build-gated (v1 scope; non-streamed turns handle those lanes).
- Discord peer mode: tune PEER_MAX_TURNS / COOLDOWN to taste; add more peer bots by appending IDs.

## 12. Memory (for Claude Code sessions)

Persistent memory lives at `D:\ClaudeHome\projects\d--b-WorkSpace\memory\` (MEMORY.md = index).
Key files: engel-model-activation-20260710.md (the big activation session + all gotchas),
engel-chat-action-lane.md (build lane + GIF root-cause), engel-discord-multiserver.md (this
Discord work), engel-persona-voice-layer.md, engel-neuron-transfers.md. The Claude *app* doesn't
read these — this handoff replicates the essentials.
