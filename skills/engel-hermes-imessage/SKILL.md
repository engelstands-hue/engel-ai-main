---
name: "engel-hermes-imessage"
description: "Send and receive iMessages/SMS via the imsg CLI on macOS."
version: "1.0.0"
source: "engel-ai-main-server"
created_at_utc: "2026-08-26T00:45:19Z"
updated_at_utc: "2026-08-26T00:45:19Z"
---

# Engel Hermes imessage

## Purpose

Send and receive iMessages/SMS via the imsg CLI on macOS.

## Trigger Conditions

- imessage
- hermes imessage
- engel hermes imessage

## Operating Instructions

Operate as Engel AI Main. Authority order is Josh > Guardian > Engel/runtime. Use local Engel storage, routes, and receipts. Do not add provider/API/network calls, live trading keys, trusted-memory writes, queue mutation, ALIVE_STATE writes, autonomous loops, Level 2 runtime, or C: project writes. Do not print secrets, tokens, or private keys. Source remains on disk; this saved card does not enable the upstream tool by itself.

Source card: engel_agent_main/skills/apple/imessage/SKILL.md

Send and receive iMessages/SMS via the imsg CLI on macOS.

# iMessage

Use `imsg` to read and send iMessage/SMS via macOS Messages.app.

## Prerequisites

- **macOS** with Messages.app signed in
- Install: `brew install steipete/tap/imsg`
- Grant Full Disk Access for terminal (System Settings → Privacy → Full Disk Access)
- Grant Automation permission for Messages.app when prompted

## When to Use

- User asks to send an iMessage or text message
- Reading iMessage conversation history
- Checking recent Messages.app chats
- Sending to phone numbers or Apple IDs

## When NOT to Use

- Telegram/Discord/Slack/WhatsApp messages → use the appropriate gateway channel
- Group chat management (adding/removing members) → not supported
- Bulk/mass messaging → always confirm with user first

## Quick Reference

### List Chats

```bash
imsg chats --limit 10 --json
```

### View History

```bash
# By chat ID
imsg history --chat-id 1 --limit 20 --json

# With attachments info
imsg history --chat-id 1 --limit 20 --attachments --json
```

### Send Messages

```bash
# Text only
imsg send --to "+14155551212" --text "Hello!"

# With attachment
imsg send --to "+14155551212" --text "Check this out" --file /path/to/image.jpg

# Force iMessage or SMS
imsg send --to "+14155551212" --text "Hi" --service imessage
imsg send --to "+14155551212" --text "Hi" --service sms
```

### Watch for New Messages

```bash
imsg watch --chat-id 1 --attachments
```

## Service Options

- `--service imessage` — Force iMessage (requires recipient has iMessage)
- `--service sms` — Force SMS (green bubble)
- `--service auto` — Let Messages.app decide (default)

## Rules

1. **Always confirm recipient and message content** before sending
2. **Never send to unknown numbers** without explicit user approval
3. **Verify file paths** exist before attaching
4. **Don't spam** — rate-limit yourself

## Example Workflow

User: "Text mom that I'll be late"

```bash
# 1. Find mom's chat
imsg chats --limit 20 --json | jq '.[] | select(.displayName | contains("Mom"))'

# 2. Confirm with user: "Found Mom at +1555123456. Send 'I'll be late' via iMessage?"

# 3. Send after confirmation
imsg send --to "+1555123456" --text "I'll be late"
```

## Save Contract

- Save durable outputs under Engel AI Main storage, not temporary chat state.
- Update the Engel skill registry after changes.
- Include a receipt path or registry key in the response when this skill creates or changes files.
- Do not expose secrets in skill files, receipts, chat replies, or logs.
