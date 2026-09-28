# Engel GitHub export v1

Status: rules for the public source snapshot. Josh said to push on 2026-09-28. The public repository is https://github.com/engelstands-hue/engel-ai-main. It is not the live body.

Authority: Josh > Guardian > Engel/runtime.

Josh named the GitHub account `engelstands-hue` on 2026-09-28 and then said to push. The public repository is `engelstands-hue/engel-ai-main`.

## What GitHub is

GitHub receives one new orphan snapshot of the authored Engel AI Main source. Live Engel stays `/opt/engel` on CT246. The history remote stays `/opt/engel/backups/engel-app.git`. A merge or push on GitHub does not deploy and does not restart services.

The 30 GiB pack at `D:\b.WorkSpace\engel-app-git-backup` is not the upload. Old commits can still hold a secret or a giant blob. The snapshot git directory is `D:\b.WorkSpace\engel-app-github-snapshot`. The workspace folder `D:\b.WorkSpace\Engel App\.git` stays empty.

## Include

- Root app modules and launchers: `*.py`, `*.md`, `*.bat`, `*.cmd`, `*.ps1`, `*.vbs`, `*.spec`, `*.toml`, `.gitignore`, `.cursorrules`, `config.toml`, `.env.template` when the scan finds no real secret.
- `wiki/`, `organs/`, `spine/`, `tools/`, `skills/`, `agents/`, `scripts/`, `docs/`.
- `mobile/engel_remote_worker/` source.
- `public/engelailabs-site/`.
- `engel_flutter_main/` source.
- `memory/ENGEL_PR_REVIEW_CONTRACT_V1.md` and this file.
- `LICENSE` (MIT, below).

`.agents/skills/` is a local mirror of `skills/`. The snapshot keeps the canonical `skills/` tree only.

## Secret denylist

Leave these out. Record the path only. Do not print the value.

- `.env`, `.env.local`, `.env.*.local`, and `run/secrets/*.env`. `*.env.example` and `.env.template` stay only when they contain placeholders.
- SSH private keys, `*.pem`, `*.key`, `id_rsa`, `id_ed25519`.
- Discord tokens, API keys, pairing codes, OAuth client files, `credentials.json`, `client_secret*.json`, `token.json`.
- `codex_usage_coffee.b64` and any file whose text matches a private-key block or a live token pattern.
- Local-only state: `.grok/`, `browser_profile/`, phone job queues under `remote_workers/`, chat receipts, `reports/`, `active_sessions.json`.

## Bulk denylist

Leave these out even though they sit on D:.

- `runtime/`, `archives/`, `archive/`, `dist/`, `models/`, `models-active/`, `hf-cache/`, `backups/`, `hold/`, `rust/`, `artifacts/`.
- `*.gguf`, `*.safetensors`, `*.onnx`, `*.iso`, `*.7z`, `*.tar`, `*.tar.gz`, `*.apk`, `*.exe`, `*.dll`.
- `node_modules/`, `.gradle/`, `.gradle-user/`, `.dart_tool/`, Flutter `build/`, Tauri `target/`, `__pycache__/`.
- The root `engel_main/` tree and every `vendor/*_main` tree. Measured 2026-09-28: `runtime` 89.09 GiB, `vendor` 64.75 GiB, root `engel_main` 63.77 GiB, `archive` 59.99 GiB.

## Vendor manifest

These third-party trees stay off the first upload. A later pass can add one tree after its own size and secret check.

`engel3d_office_main`, `engel_agent_main`, `engel_ai_gallery_main`, `engel_airllm_main`, `engel_chat_ui_main`, `engel_claw3d_main`, `engel_cli_anything_main`, `engel_cubesandbox_main`, `engel_evolution_engine_main`, `engel_evolution_lab_main`, `engel_git_nexus_main`, `engel_gstack_main`, `engel_hermes_agent_main`, `engel_humanizer_main`, `engel_jarvis_main`, `engel_knowledge_graph_v2_main`, `engel_lan_main`, `engel_lfm2_code_review_main`, `engel_lfm2_mobile_main`, `engel_lfm2_vision_main`, `engel_localsend_main`, `engel_main`, `engel_native_agent_main`, `engel_octogent_main`, `engel_open_agents_main`, `engelcode_main`, `engelsandbox_main`.

`engel_flutter_main` is Engel's Cosmic Swarm face. Its source is in this snapshot. Its build output is not. The vendored copy under `vendor/` stays off with the rest of that folder.

## MIT license

The public snapshot is released under the MIT License so other people may have the authored Engel source. The grant is the `LICENSE` file. Vendored files that a later pass ships keep their own upstream license notices. This license does not cover secrets, model weights, or the CT246 runtime.

## Push gate

Josh said to push on 2026-09-28. The account is `engelstands-hue`. The public repository is `engel-ai-main`.

The published tree uses placeholders for phone serials, the Discord owner id, personal Gmail addresses, and the house LAN ranges. The live Engel body is unchanged. `.env.template` is not in this history. The local receipt is `reports/codex_bridge/ENGEL_GITHUB_EXPORT_20260928.md`.
