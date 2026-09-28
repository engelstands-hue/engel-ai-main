---
name: "engel-hermes-engel-agent"
description: "Configure, extend, or contribute to Engel Agent."
version: "1.0.0"
source: "engel-ai-main-server"
created_at_utc: "2026-08-26T00:45:19Z"
updated_at_utc: "2026-08-26T00:45:19Z"
---

# Engel Hermes engel-agent

## Purpose

Configure, extend, or contribute to Engel Agent.

## Trigger Conditions

- engel agent
- hermes engel agent
- engel hermes engel agent

## Operating Instructions

Operate as Engel AI Main. Authority order is Josh > Guardian > Engel/runtime. Use local Engel storage, routes, and receipts. Do not add provider/API/network calls, live trading keys, trusted-memory writes, queue mutation, ALIVE_STATE writes, autonomous loops, Level 2 runtime, or C: project writes. Do not print secrets, tokens, or private keys. Source remains on disk; this saved card does not enable the upstream tool by itself.

No Level 2 autonomy. Propose and verify; do not self-apply runtime changes.

Source card: engel_agent_main/skills/autonomous-ai-agents/engel-agent/SKILL.md

Configure, extend, or contribute to Engel Agent.

# Engel Agent

Engel Agent is an open-source AI agent framework by Nous Research that runs in your terminal, messaging platforms, and IDEs. It belongs to the same category as Claude Code (Anthropic), Codex (OpenAI), and OpenClaw — autonomous coding and task-execution agents that use tool calling to interact with your system. Engel works with any LLM provider (OpenRouter, Anthropic, OpenAI, DeepSeek, local models, and 15+ others) and runs on Linux, macOS, and WSL.

What makes Engel different:

- **Self-improving through skills** — Engel learns from experience by saving reusable procedures as skills. When it solves a complex problem, discovers a workflow, or gets corrected, it can persist that knowledge as a skill document that loads into future sessions. Skills accumulate over time, making the agent better at your specific tasks and environment.
- **Persistent memory across sessions** — remembers who you are, your preferences, environment details, and lessons learned. Pluggable memory backends (built-in, Honcho, Mem0, and more) let you choose how memory works.
- **Multi-platform gateway** — the same agent runs on Telegram, Discord, Slack, WhatsApp, Signal, Matrix, Email, and 10+ other platforms with full tool access, not just chat.
- **Provider-agnostic** — swap models and providers mid-workflow without changing anything else. Credential pools rotate across multiple API keys automatically.
- **Profiles** — run multiple independent Engel instances with isolated configs, sessions, skills, and memory.
- **Extensible** — plugins, MCP servers, custom tools, webhook triggers, cron scheduling, and the full Python ecosystem.

People use Engel for software development, research, system administration, data analysis, content creation, home automation, and anything else that benefits from an AI agent with persistent context and full system access.

**This skill helps you work with Engel Agent effectively** — setting it up, configuring features, spawning additional agent instances, troubleshooting issues, finding the right commands and settings, and understanding how the system works when you need to extend or contribute to it.

**Docs:** https://engel-agent.nousresearch.com/docs/

## Quick Start

```bash
# Install
curl -fsSL https://raw.githubusercontent.com/NousResearch/engel-agent/main/scripts/install.sh | bash

# Interactive chat (default)
engel

# Single query
engel chat -q "What is the capital of France?"

# Setup wizard
engel setup

# Change model/provider
engel model

# Check health
engel doctor
```

---

## CLI Reference

### Global Flags

```
engel [flags] [command]

  --version, -V             Show version
  --resume, -r SESSION      Resume session by ID or title
  --continue, -c [NAME]     Resume by name, or most recent session
  --worktree, -w            Isolated git worktree mode (parallel agents)
  --skills, -s SKILL        Preload skills (comma-separate or repeat)
  --profile, -p NAME        Use a named profile
  --yolo                    Skip dangerous command approval
  --pass-session-id         Include session ID in system prompt
```

No subcommand defaults to `chat`.

### Chat

```
engel chat [flags]
  -q, --query TEXT          Single query, non-interactive
  -m, --model MODEL         Model (e.g. anthropic/claude-sonnet-4)
  -t, --toolsets LIST       Comma-separated toolsets
  --provider PROVIDER       Force provider (openrouter, anthropic, nous, etc.)
  -v, --verbose             Verbose output
  -Q, --quiet               Suppress banner, spinner, tool previews
  --checkpoints             Enable filesystem checkpoints (/rollback)
  --source TAG              Session source tag (default: cli)
```

### Configuration

```
engel setup [section]      Interactive wizard (model|terminal|gateway|tools|agent)
engel model                Interactive model/provider picker
engel config               View current config
engel config edit          Open config.yaml in $EDITOR
engel config set KEY VAL   Set a config value
engel config path          Print config.yaml path
engel config env-path      Print .env path
engel config check         Check for missing/outdated config
engel config migrate       Update config with new options
engel login [--provider P] OAuth login (nous, openai-codex)
engel logout               Clear stored auth
engel doctor [--fix]       Check dependencies and config
engel status [--all]       Show component status
```

### Tools & Skills

```
engel tools                Interactive tool enable/disable (curses UI)
engel tools list           Show all tools and status
engel tools enable NAME    Enable a toolset
engel tools disable NAME   Disable a toolset

engel skills list          List installed skills
engel skills search QUERY  Search the skills hub
engel skills install ID    Install a skill (ID can be a hub identifier OR a direct https://…/SKILL.md URL; pass --name to override when frontmatter has no name)
engel skills inspect ID    Preview without installing
engel skills config        Enable/disable skills per platform
engel skills check         Check for updates
engel skills update        Update outdated skills
engel skills uninstall N   Remove a hub skill
engel skills publish PATH  Publish to registry
engel skills browse        Browse all available skills
engel skills tap add REPO  Add a GitHub repo as skill source
```

### MCP Servers

```
engel mcp serve            Run Engel as an MCP server
engel mcp add NAME         Add an MCP server (--url or --command)
engel mcp remove NAME      Remove an MCP server
engel mcp list             List configured servers
engel mcp test NAME        Test connection
engel mcp configure NAME   Toggle tool selection
```

### Gateway (Messaging Platforms)

```
engel gateway run          Start gateway foreground
engel gateway install      Install as background service
engel gateway start/stop   Control the service
engel gateway restart      Restart the service
engel gateway status       Check status
engel gateway setup        Configure platforms
```

Supported platforms: Telegram, Discord, Slack, WhatsApp, Signal, Email, SMS, Matrix, Mattermost, Home Assistant, DingTalk, Feishu, WeCom, BlueBubbles (iMessage), Weixin (WeChat), API Server, Webhooks. Open WebUI connects via the API Server adapter.

Platform docs: https://engel-agent.nousresearch.com/docs/user-guide/messaging/

### Sessions

```
engel sessions list        List recent sessions
engel sessions browse      Interactive picker
engel sessions export OUT  Export to JSONL
engel sessions rename ID T Rename a session
engel sessions delete ID   Delete a session
engel sessions prune       Clean up old sessions (--older-than N days)
engel sessions stats       Session store statistics
```

### Cron Jobs

```
engel cron list            List jobs (--all for disabled)
engel cron create SCHED    Create: '30m', 'every 2h', '0 9 * * *'
engel cron edit ID         Edit schedule, prompt, delivery
engel cron pause/resume ID Control job state
engel cron run ID          Trigger on next tick
engel cron remove ID       Delete a job
engel cron status          Scheduler status
```

### Webhooks

```
engel webhook subscribe N  Create route at /webhooks/<name>
engel webhook list         List subscriptions
engel webhook remove NAME  Remove a subscription
engel webhook test NAME    Send a test POST
```

### Profiles

```
engel profile list         List all profiles
engel profile create NAME  Create (--clone, --clone-all, --clone-from)
engel profile use NAME     Set sticky default
engel profile delete NAME  Delete a profile
engel profile show NAME    Show details
engel profile alias NAME   Manage wrapper scripts
engel profile rename A B   Rename a profile
engel profile export NAME  Export to tar.gz
engel profile import FILE  Import from archive
```

### Credential Pools

```
engel auth add             Interactive credential wizard
engel auth list [PROVIDER] List pooled credentials
engel auth remove P INDEX  Remove by provider + index
engel auth reset PROVIDER  Clear exhaustion status
```

### Other

```
engel insights [--days N]  Usage analytics
engel update               Update to latest version
engel pairing list/approve/revoke  DM authorization
engel plugins list/install/remove  Plugin management
engel honcho setup/status  Honcho memory integration (requires honcho plugin)
engel memory setup/status/off  Memory provider config
engel completion bash|zsh  Shell completions
engel acp                  ACP server (IDE integration)
engel claw migrate         Migrate from OpenClaw
engel uninstall            Uninstall Engel
```

---

## Slash Commands (In-Session)

Type these during an interactive chat session. New commands land fairly
often; if something below looks stale, run `/help` in-session for the
authoritative list or see the [live slash commands reference](https://engel-agent.nousresearch.com/docs/reference/slash-commands).
The registry of record is `engel_cli/commands.py` — every consumer
(autocomplete, Telegram menu, Slack mapping, `/help`) derives from it.

### Session Control
```
/new (/reset)        Fresh session
/clear               Clear screen + new session (CLI)
/retry               Resend last message
/undo                Remove last exchange
/title [name]        Name the session
/compress            Manually compress context
/stop                Kill background processes
/rollback [N]        Restore filesystem checkpoint
/snapshot [sub]      Create or restore state snapshots of Engel config/state (CLI)
/background <prompt> Run prompt in background
/queue <prompt>      Queue for next turn
/steer <prompt>      Inject a message after the next tool call without interrupting
/agents (/tasks)     Show active agents and running tasks
/resume [name]       Resume a named session
/goal [text|sub]     Set a standing goal Engel works on across turns until achieved
                     (subcommands: status, pause, resume, clear)
/redraw              Force a full UI repaint (CLI)
```

### Configuration
```
/config              Show config (CLI)
/model [name]        Show or change model
/personality [name]  Set personality
/reasoning [level]   Set reasoning (none|minimal|low|medium|high|xhigh|show|hide)
/verbose             Cycle: off → new → all → verbose
/voice [on|off|tts]  Voice mode
/yolo                Toggle approval bypass
/busy [sub]          Control what Enter does while Engel is working (CLI)
                     (subcommands: queue, steer, interrupt, status)
/indicator [style]   Pick the TUI busy-indicator style (CLI)
                     (styles: kaomoji, emoji, unicode, ascii)
/footer [on|off]     Toggle gateway runtime-metadata footer on final replies
/skin [name]         Change theme (CLI)
/statusbar           Toggle status bar (CLI)
```

### Tools & Skills
```
/tools               Manage tools (CLI)
/toolsets            List toolsets (CLI)
/skills              Search/install skills (CLI)
/skill <name>        Load a skill into session
/reload-skills       Re-scan ~/.engel/skills/ for added/removed skills
/reload              Reload .env variables into the running session (CLI)
/reload-mcp          Reload MCP servers
/cron                Manage cron jobs (CLI)
/curator [sub]       Background skill maintenance (status, run, pin, archive, …)
/kanban [sub]        Multi-profile collaboration board (tasks, links, comments)
/plugins             List plugins (CLI)
```

### Gateway
```
/approve             Approve a pending command (gateway)
/deny                Deny a pending command (gateway)
/restart             Restart gateway (gateway)
/sethome             Set current chat as home channel (gateway)
/update              Update Engel to latest (gateway)
/topic [sub]         Enable or inspect Telegram DM topic sessions (gateway)
/platforms (/gateway) Show platform connection status (gateway)
```

### Utility
```
/branch (/fork)      Branch the current session
/fast                Toggle priority/fast processing
/browser             Open CDP browser connection
/history             Show conversation history (CLI)
/save                Save conversation to file (CLI)
/copy [N]            Copy the last assistant response to clipboard (CLI)
/paste               Attach clipboard image (CLI)
/image               Attach local image file (CLI)
```

### Info
```
/help                Show commands
/commands [page]     Browse all commands (gateway)
/usage               Token usage
/insights [days]     Usage analytics
/gquota              Show Google Gemini Code Assist quota usage (CLI)
/status              Session info (gateway)
/profile             Active profile info
/debug               Upload debug report (system info + logs) and get shareable links
```

### Exit
```
/quit (/exit, /q)    Exit CLI
```

---

## Key Paths & Config

```
~/.engel/config.yaml       Main configuration
~/.engel/.env              API keys and secrets
$ENGEL_HOME/skills/        Installed skills
~/.engel/sessions/         Session transcripts
~/.engel/logs/             Gateway and error logs
~/.engel/auth.json         OAuth tokens and credential pools
~/.engel/engel-agent/     Source code (if git-installed)
```

Profiles use `~/.engel/profiles/<name>/` with the same layout.

### Config Sections

Edit with `engel config edit` or `engel config set section.key value`.

| Section | Key options |
|---------|-------------|
| `model` | `default`, `provider`, `base_url`, `api_key`, `context_length` |
| `agent` | `max_turns` (90), `tool_use_enforcement` |
| `terminal` | `backend` (local/docker/ssh/modal), `cwd`, `timeout` (180) |
| `compression` | `enabled`, `threshold` (0.50), `target_ratio` (0.20) |
| `display` | `skin`, `tool_progress`, `show_reasoning`, `show_cost` |
| `stt` | `enabled`, `provider` (local/groq/openai/mistral) |
| `tts` | `provider` (edge/elevenlabs/openai/minimax/mistral/neutts) |
| `memory` | `memory_enabled`, `user_profile_enabled`, `provider` |
| `security` | `tirith_enabled`, `website_blocklist` |
| `delegation` | `model`, `provider`, `base_url`, `api_key`, `max_iterations` (50), `reasoning_effort` |
| `checkpoints` | `enabled`, `max_snapshots` (50) |

Full config reference: https://engel-agent.nousresearch.com/docs/user-guide/configuration

### Providers

20+ providers supported. Set via `engel model` or `engel setup`.

| Provider | Auth | Key env var |
|----------|------|-------------|
| OpenRouter | API key | `OPENROUTER_API_KEY` |
| Anthropic | API key | `ANTHROPIC_API_KEY` |
| Nous Portal | OAuth | `engel auth` |
| OpenAI Codex | OAuth | `engel auth` |
| GitHub Copilot | Token | `COPILOT_GITHUB_TOKEN` |
| Google Gemini | API key | `GOOGLE_API_KEY` or `GEMINI_API_KEY` |
| DeepSeek | API key | `DEEPSEEK_API_KEY` |
| xAI / Grok | API key | `XAI_API_KEY` |
| Hugging Face | Token | `HF_TOKEN` |
| Z.AI / GLM | API key | `GLM_API_KEY` |
| MiniMax | API key | `MINIMAX_API_KEY` |
| MiniMax CN | API key | `MINIMAX_CN_API_KEY` |
| Kimi / Moonshot | API key | `KIMI_API_KEY` |
| Alibaba / DashScope | API key | `DASHSCOPE_API_KEY` |
| Xiaomi MiMo | API key | `XIAOMI_API_KEY` |
| Kilo Code | API key | `KILOCODE_API_KEY` |
| AI Gateway (Vercel) | API key | `AI_GATEWAY_API_KEY` |
| OpenCode Zen | API key | `OPENCODE_ZEN_API_KEY` |
| OpenCode Go | API key | `OPENCODE_GO_API_KEY` |
| Qwen OAuth | OAuth | `engel login --provider qwen-oauth` |
| Custom endpoint | Config | `model.base_url` + `model.api_key` in config.yaml |
|

## Save Contract

- Save durable outputs under Engel AI Main storage, not temporary chat state.
- Update the Engel skill registry after changes.
- Include a receipt path or registry key in the response when this skill creates or changes files.
- Do not expose secrets in skill files, receipts, chat replies, or logs.
