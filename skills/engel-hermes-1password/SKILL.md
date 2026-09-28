---
name: "engel-hermes-1password"
description: "Set up and use 1Password CLI (op). Use when installing the CLI, enabling desktop app integration, signing in, and reading/injecting secrets for commands."
version: "1.0.0"
source: "engel-ai-main-server"
created_at_utc: "2026-08-26T00:56:16Z"
updated_at_utc: "2026-08-26T00:56:16Z"
---

# Engel 1Password

## Purpose

Set up and use 1Password CLI (op). Use when installing the CLI, enabling desktop app integration, signing in, and reading/injecting secrets for commands.

## Trigger Conditions

- 1password
- optional hermes 1password
- engel hermes 1password

## Operating Instructions

Operate as Engel AI Main. Authority order is Josh > Guardian > Engel/runtime. This is a recreated Engel skill, not a live Hermes optional plugin. Use local Engel storage, routes, and receipts. Do not add provider/API/network calls, live trading keys, trusted-memory writes, queue mutation, ALIVE_STATE writes, autonomous loops, Level 2 runtime, or C: project writes. Do not print secrets, tokens, or private keys. Source remains on disk; this saved card does not enable the upstream tool by itself.

Do not print, copy, or store 1Password secrets.

Source card: engel_agent_main/optional-skills/security/1password/SKILL.md

Set up and use 1Password CLI (op). Use when installing the CLI, enabling desktop app integration, signing in, and reading/injecting secrets for commands.

# 1Password CLI

Use this skill when the user wants secrets managed through 1Password instead of plaintext env vars or files.

## Requirements

- 1Password account
- 1Password CLI (`op`) installed
- One of: desktop app integration, service account token (`OP_SERVICE_ACCOUNT_TOKEN`), or Connect server
- `tmux` available for stable authenticated sessions during Engel terminal calls (desktop app flow only)

## When to Use

- Install or configure 1Password CLI
- Sign in with `op signin`
- Read secret references like `op://Vault/Item/field`
- Inject secrets into config/templates using `op inject`
- Run commands with secret env vars via `op run`

## Authentication Methods

### Service Account (recommended for Engel)

Set `OP_SERVICE_ACCOUNT_TOKEN` in `~/.engel/.env` (the skill will prompt for this on first load).
No desktop app needed. Supports `op read`, `op inject`, `op run`.

```bash
export OP_SERVICE_ACCOUNT_TOKEN=[redacted]
op whoami  # verify — should show Type: SERVICE_ACCOUNT
```

### Desktop App Integration (interactive)

1. Enable in 1Password desktop app: Settings → Developer → Integrate with 1Password CLI
2. Ensure app is unlocked
3. Run `op signin` and approve the biometric prompt

### Connect Server (self-hosted)

```bash
export OP_CONNECT_HOST="http://localhost:8080"
export OP_CONNECT_TOKEN=[redacted]
```

## Setup

1. Install CLI:

```bash
# macOS
brew install 1password-cli

# Linux (official package/install docs)
# See references/get-started.md for distro-specific links.

# Windows (winget)
winget install AgileBits.1Password.CLI
```

2. Verify:

```bash
op --version
```

3. Choose an auth method above and configure it.

## Engel Execution Pattern (desktop app flow)

Engel terminal commands are non-interactive by default and can lose auth context between calls.
For reliable `op` use with desktop app integration, run sign-in and secret operations inside a dedicated tmux session.

Note: This is NOT needed when using `OP_SERVICE_ACCOUNT_TOKEN` — the token persists across terminal calls automatically.

```bash
SOCKET_DIR="${TMPDIR:-/tmp}/engel-tmux-sockets"
mkdir -p "$SOCKET_DIR"
SOCKET="$SOCKET_DIR/engel-op.sock"
SESSION="op-auth-$(date +%Y%m%d-%H%M%S)"

tmux -S "$SOCKET" new -d -s "$SESSION" -n shell

# Sign in (approve in desktop app when prompted)
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- "eval \"\$(op signin --account my.1password.com)\"" Enter

# Verify auth
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- "op whoami" Enter

# Example read
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- "op read 'op://Private/Npmjs/one-time password?attribute=otp'" Enter

# Capture output when needed
tmux -S "$SOCKET" capture-pane -p -J -t "$SESSION":0.0 -S -200

# Cleanup
tmux -S "$SOCKET" kill-session -t "$SESSION"
```

## Common Operations

### Read a secret

```bash
op read "op://app-prod/db/password"
```

### Get OTP

```bash
op read "op://app-prod/npm/one-time password?attribute=otp"
```

### Inject into template

```bash
echo "db_password: {{ op://app-prod/db/password }}" | op inject
```

### Run a command with secret env var

```bash
export DB_PASSWORD="op://app-prod/db/password"
op run -- sh -c '[ -n "$DB_PASSWORD" ] && echo "DB_PASSWORD is set" || echo "DB_PASSWORD missing"'
```

## Guardrails

- Never print raw secrets back to user unless they explicitly request the value.
- Prefer `op run` / `op inject` instead of writing secrets into files.
- If command fails with "account is not signed in", run `op signin` again in the same tmux session.
- If desktop app integration is unavailable (headless/CI), use service account token flow.

## CI / Headless note

For non-interactive use, authenticate with `OP_SERVICE_ACCOUNT_TOKEN` and avoid interactive `op signin`.
Service accounts require CLI v2.18.0+.

## References

- `references/get-started.md`
- `references/cli-examples.md`
- https://developer.1password.com/docs/cli/
- https://developer.1password.com/docs/service-accounts/

## Save Contract

- Save durable outputs under Engel AI Main storage, not temporary chat state.
- Update the Engel skill registry after changes.
- Include a receipt path or registry key in the response when this skill creates or changes files.
- Do not expose secrets in skill files, receipts, chat replies, or logs.
