---
name: "engel-hermes-nano-pdf"
description: "Edit PDF text/typos/titles via nano-pdf CLI (NL prompts)."
version: "1.0.0"
source: "engel-ai-main-server"
created_at_utc: "2026-08-26T00:45:20Z"
updated_at_utc: "2026-08-26T00:45:20Z"
---

# Engel Hermes nano-pdf

## Purpose

Edit PDF text/typos/titles via nano-pdf CLI (NL prompts).

## Trigger Conditions

- nano pdf
- hermes nano pdf
- engel hermes nano pdf

## Operating Instructions

Operate as Engel AI Main. Authority order is Josh > Guardian > Engel/runtime. Use local Engel storage, routes, and receipts. Do not add provider/API/network calls, live trading keys, trusted-memory writes, queue mutation, ALIVE_STATE writes, autonomous loops, Level 2 runtime, or C: project writes. Do not print secrets, tokens, or private keys. Source remains on disk; this saved card does not enable the upstream tool by itself.

Source card: engel_agent_main/skills/productivity/nano-pdf/SKILL.md

Edit PDF text/typos/titles via nano-pdf CLI (NL prompts).

# nano-pdf

Edit PDFs using natural-language instructions. Point it at a page and describe what to change.

## Prerequisites

```bash
# Install with uv (recommended — already available in Engel)
uv pip install nano-pdf

# Or with pip
pip install nano-pdf
```

## Usage

```bash
nano-pdf edit <file.pdf> <page_number> "<instruction>"
```

## Examples

```bash
# Change a title on page 1
nano-pdf edit deck.pdf 1 "Change the title to 'Q3 Results' and fix the typo in the subtitle"

# Update a date on a specific page
nano-pdf edit report.pdf 3 "Update the date from January to February 2026"

# Fix content
nano-pdf edit contract.pdf 2 "Change the client name from 'Acme Corp' to 'Acme Industries'"
```

## Notes

- Page numbers may be 0-based or 1-based depending on version — if the edit hits the wrong page, retry with ±1
- Always verify the output PDF after editing (use `read_file` to check file size, or open it)
- The tool uses an LLM under the hood — requires an API key (check `nano-pdf --help` for config)
- Works well for text changes; complex layout modifications may need a different approach

## Save Contract

- Save durable outputs under Engel AI Main storage, not temporary chat state.
- Update the Engel skill registry after changes.
- Include a receipt path or registry key in the response when this skill creates or changes files.
- Do not expose secrets in skill files, receipts, chat replies, or logs.
