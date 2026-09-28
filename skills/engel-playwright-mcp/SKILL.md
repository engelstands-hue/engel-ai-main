---
name: "engel-playwright-mcp"
description: "Local Playwright browser MCP staged from storage-pull for Engel AI Main. Default allowlist is localhost/file only."
version: "1.0.0"
source: "engel-ai-main-server"
created_at_utc: "2026-08-25T21:48:52Z"
updated_at_utc: "2026-08-25T21:48:52Z"
---

# Engel Playwright MCP

## Purpose

Local Playwright browser MCP staged from storage-pull for Engel AI Main. Default allowlist is localhost/file only.

## Trigger Conditions

- playwright mcp
- browser mcp
- local browser tools

## Operating Instructions

Use the staged Playwright MCP under runtime/next_stage/playwright_mcp. Do not enable unrestricted web crawling. Allowed origins stay localhost and file workspace roots unless Josh expands them. Linux Chrome/Edge apt installers live beside the MCP for CT246 only. This is local browser automation, not a cloud provider.

## Save Contract

- Save durable outputs under Engel AI Main storage, not temporary chat state.
- Update the Engel skill registry after changes.
- Include a receipt path or registry key in the response when this skill creates or changes files.
- Do not expose secrets in skill files, receipts, chat replies, or logs.
