---
name: claw-ecosystem
description: This skill should be used when the user asks to "start all claws", "start claw gateways", "run all gateways", "start openclaw nanobot picoclaw zeroclaw nanoclaw", "launch claw ecosystem", "stop all claws", "stop gateways", "claw status", "check gateway status", or "open claws". Manages all five Claw ecosystem gateways (OpenClaw, ZeroClaw, NanoBot, PicoClaw, NanoClaw) as a unified fleet.
version: 2.0.0
---

# Claw Ecosystem Gateway Manager

Manage all five Claw/NanoBot gateways as one fleet. Supports start, stop, status, and restart
across OpenClaw (TypeScript), ZeroClaw (Rust), NanoBot (Python), PicoClaw (Go), and NanoClaw (Node.js).

## Project Overview

| Project   | Language   | Binary/Entrypoint              | Runtime Workspace          | Port    |
|-----------|------------|--------------------------------|----------------------------|---------|
| OpenClaw  | TypeScript | `openclaw` (npm global)        | `~/.openclaw`              | 18789   |
| ZeroClaw  | Rust       | `zeroclaw` (brew)              | `~/.zeroclaw`              | 42617   |
| NanoBot   | Python     | `nanobot` (pip)                | `~/.nanobot`               | 18790   |
| PicoClaw  | Go         | `picoclaw` (binary)            | `~/.picoclaw`              | dynamic |
| NanoClaw  | Node.js    | `node dist/index.js` (source)  | `~/Open-Universe/NanoClaw` | —       |

## Quick Commands

```bash
# Start all (skips already-running ones)
~/.Codex/skills/claw-ecosystem/scripts/claw-gateway.sh start

# Status of all
~/.Codex/skills/claw-ecosystem/scripts/claw-gateway.sh status

# Stop all
~/.Codex/skills/claw-ecosystem/scripts/claw-gateway.sh stop

# Full restart
~/.Codex/skills/claw-ecosystem/scripts/claw-gateway.sh restart

# Single project operations
~/.Codex/skills/claw-ecosystem/scripts/claw-gateway.sh start zeroclaw
~/.Codex/skills/claw-ecosystem/scripts/claw-gateway.sh restart nanoclaw
~/.Codex/skills/claw-ecosystem/scripts/claw-gateway.sh stop nanobot
```

Logs: `/tmp/claw-gateways/<project>.log`

## Project Details

### OpenClaw (TypeScript)
- **Start:** `openclaw gateway start`  — managed via **launchd** (`ai.openclaw.gateway`)
- **Stop:** `openclaw gateway stop`
- **Status:** `openclaw gateway status`
- **Port:** 18789
- **Config:** `~/.openclaw/openclaw.json`
- **Detection:** `launchctl list ai.openclaw.gateway` (NOT pgrep — it's a LaunchAgent)
- **Important:** Do NOT `pkill -f openclaw` — always use `openclaw gateway stop`

### ZeroClaw (Rust)
- **Start:** `zeroclaw daemon`  ← **must use `daemon`, not `gateway`**
  - `daemon` = gateway + channels + heartbeat + scheduler (all components)
  - `gateway` = HTTP only — no channels, no scheduler, no heartbeat
- **Stop:** `pkill -f "zeroclaw daemon"`
- **Status:** `zeroclaw status`
- **Config:** `~/.zeroclaw/config.toml`
- **Port:** 42617
- **Default provider:** `custom:http://localhost:20128/v1` (model: `glm/glm-4.7`)
- **Provider note:** Only recognises 37 built-in IDs + `custom:<URL>`. For local proxy use:
  ```toml
  default_provider = "custom:http://localhost:20128/v1"
  [[model_routes]]
  hint = "glm-4.7"
  provider = "custom:http://localhost:20128/v1"
  model = "glm/glm-4.7"
  api_key = "REDACTED_LOCAL_PROXY_KEY"
  ```
- **TOML pitfall:** Never mix `model_routes = []` and `[[model_routes]]` — causes duplicate key parse error

### NanoBot (Python)
- **Start:** `nanobot gateway`
- **Stop:** `pkill -f "nanobot gateway"`
- **Status:** `nanobot status`
- **Config:** `~/.nanobot/config.json`
- **Port:** 18790
- **Channels:** Telegram (`@MetaSocialDataBot`), Discord, Email (IMAP polling)
- **Default provider:** `zai` (model: `glm-4.7`)
- **Critical:** Provider MUST be `zai`, NOT `local` or `custom`.
  GLM models return 422 errors for tool-calling (rejects `tool` role + `tool_choice: auto`).
  The key `"custom"` in providers is NanoBot's built-in name for custom OpenAI-compatible endpoints.
- **Fallbacks:** `kimi/kimi-k2-thinking-turbo`, `google/gemini-2.5-flash`, `openrouter/meta-llama/llama-3.3-70b-instruct:free`

### PicoClaw (Go)
- **Start:** `picoclaw gateway`
- **Stop:** `pkill -f "picoclaw gateway"`
- **Status:** `picoclaw status`
- **Config:** `~/.picoclaw/config.json`
- **Health endpoint:** `http://127.0.0.1:<port>/health`
- **Memory files:** Auto-created at `~/.picoclaw/workspace/memory/YYYYMM/YYYYMMDD.md`

### NanoClaw (Node.js — run from source)
- **Start:** `cd ~/Open-Universe/NanoClaw && node dist/index.js`
- **Stop:** `pkill -f "Open-Universe/NanoClaw"`
- **Source dir:** `~/Open-Universe/NanoClaw/`
- **Config:** `~/Open-Universe/NanoClaw/.env`
- **Channels:** Telegram (`@NanoClaw97_bot`), Discord (`NanoClaw#2256`)
- **Trigger phrase:** `@Andy`
- **Database:** `~/Open-Universe/NanoClaw/store/messages.db` (SQLite)
- **Two prerequisites (auto-handled by script):**
  1. Apple container system running: `container system status` → `apiserver is running`
     - Fix: `container system start` (downloads kernel on first run, ~2 min)
  2. `nanoclaw-agent:latest` image built: `container image list` → shows `nanoclaw-agent`
     - Build: `cd ~/Open-Universe/NanoClaw/container && bash build.sh` (~3 min, first time only)
- **Architecture:** Each conversation runs in an isolated Linux VM via Apple's native `container` CLI.
  The image contains Codex, Chromium (agent-browser), and the TypeScript agent-runner.
- **Rebuild dist:** `cd ~/Open-Universe/NanoClaw && npm run build`
- **Rebuild image:** `cd ~/Open-Universe/NanoClaw/container && bash build.sh`

## Local LLM Proxy

Shared proxy at `http://localhost:20128/v1`, key: `REDACTED_LOCAL_PROXY_KEY`

| Model ID               | Used by         |
|------------------------|-----------------|
| `glm/glm-4.7`          | ZeroClaw        |
| `qwen/qwen3-coder-plus`| ZeroClaw        |
| `gh/Codex-sonnet-4.5` | ZeroClaw        |

NanoBot uses `zai` (not the local proxy) because GLM lacks tool-calling support.

## Troubleshooting

**OpenClaw port conflict:**
```bash
openclaw gateway stop && openclaw gateway start
# or: openclaw gateway run --force
```

**ZeroClaw "API key not set" for all providers:**
Named providers need `zeroclaw onboard`. Use `custom:http://...` instead — no onboarding needed.

**ZeroClaw TOML "duplicate key: model_routes":**
Remove `model_routes = []` line; keep only `[[model_routes]]` sections.

**NanoBot "No API key configured" on start:**
Provider `local` is not recognised. Fix:
```bash
python3 -c "
import json; f='$HOME/.nanobot/config.json'
d=json.load(open(f))
d['agents']['defaults']['provider']='zai'
d['agents']['defaults']['model']='glm-4.7'
json.dump(d,open(f,'w'),indent=2)"
nanobot gateway &
```

**NanoBot "422 tool role" error:**
GLM doesn't support tool-calling via the local proxy. Switch provider to `zai` or use
`kimi/kimi-k2-thinking-turbo`.

**NanoClaw "XPC connection error: Connection invalid":**
```bash
container system start   # first run downloads kata kernel (~2 min)
```

**NanoClaw container exits immediately (code 1):**
```bash
cd ~/Open-Universe/NanoClaw/container && bash build.sh
```

**NanoClaw flooding health-check alerts (runaway scheduled tasks):**
```bash
sqlite3 ~/Open-Universe/NanoClaw/store/messages.db "
UPDATE scheduled_tasks SET status='paused'
WHERE prompt LIKE '%health check%' OR prompt LIKE '%monitoring/%'
   OR prompt LIKE '%code-reviewer agent%' OR prompt LIKE '%health summary%';"
```

**ZeroClaw stale heartbeat/scheduler/telegram errors:**
You're running `zeroclaw gateway` instead of `zeroclaw daemon`. Restart with daemon:
```bash
pkill -f "zeroclaw gateway" && zeroclaw daemon &
```

## Scripts

- **`scripts/claw-gateway.sh`** — Fleet management script (start/stop/status/restart [project])
