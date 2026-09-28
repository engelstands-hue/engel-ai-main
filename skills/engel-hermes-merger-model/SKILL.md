---
name: "engel-hermes-merger-model"
description: "Build accretion/dilution (merger) models in Excel — pro-forma P&L, synergies, financing mix, EPS impact. Pairs with excel-author. Use for M&A pitches, board materials, or deal evaluation."
version: "1.0.0"
source: "engel-ai-main-server"
created_at_utc: "2026-08-26T00:56:15Z"
updated_at_utc: "2026-08-26T00:56:15Z"
---

# Engel Merger Model

## Purpose

Build accretion/dilution (merger) models in Excel — pro-forma P&L, synergies, financing mix, EPS impact. Pairs with excel-author. Use for M&A pitches, board materials, or deal evaluation.

## Trigger Conditions

- merger model
- optional hermes merger model
- engel hermes merger model

## Operating Instructions

Operate as Engel AI Main. Authority order is Josh > Guardian > Engel/runtime. This is a recreated Engel skill, not a live Hermes optional plugin. Use local Engel storage, routes, and receipts. Do not add provider/API/network calls, live trading keys, trusted-memory writes, queue mutation, ALIVE_STATE writes, autonomous loops, Level 2 runtime, or C: project writes. Do not print secrets, tokens, or private keys. Source remains on disk; this saved card does not enable the upstream tool by itself.

Source card: engel_agent_main/optional-skills/finance/merger-model/SKILL.md

Build accretion/dilution (merger) models in Excel — pro-forma P&L, synergies, financing mix, EPS impact. Pairs with excel-author. Use for M&A pitches, board materials, or deal evaluation.

## Environment

This skill assumes **headless openpyxl** — you are producing an .xlsx file on disk.
Follow the `excel-author` skill's conventions for cell coloring, formulas, named ranges, and sensitivity tables.
Recalculate before delivery: `python /path/to/excel-author/scripts/recalc.py ./out/model.xlsx`.

# Merger Model

Build accretion/dilution analysis for M&A transactions. Models pro forma EPS impact, synergy sensitivities, and purchase price allocation. Use when evaluating a potential acquisition, preparing merger consequences analysis for a pitch, or advising on deal terms.

## Workflow

### Step 1: Gather Inputs

**Acquirer:**
- Company name, current share price, shares outstanding
- LTM and NTM EPS (GAAP and adjusted)
- P/E multiple
- Pre-tax cost of debt, tax rate
- Cash on balance sheet, existing debt

**Target:**
- Company name, current share price, shares outstanding (if public)
- LTM and NTM EPS or net income
- Enterprise value or equity value

**Deal Terms:**
- Offer price per share (or premium to current)
- Consideration mix: % cash vs. % stock
- New debt raised to fund cash portion
- Expected synergies (revenue and cost) and phase-in timeline
- Transaction fees and financing costs
- Expected close date

### Step 2: Purchase Price Analysis

| Item | Value |
|------|-------|
| Offer price per share | |
| Premium to current | |
| Equity value | |
| Plus: net debt assumed | |
| Enterprise value | |
| EV / EBITDA implied | |
| P/E implied | |

### Step 3: Sources & Uses

| Sources | $ | Uses | $ |
|---------|---|------|---|
| New debt | | Equity purchase price | |
| Cash on hand | | Refinance target debt | |
| New equity issued | | Transaction fees | |
| | | Financing fees | |
| **Total** | | **Total** | |

### Step 4: Pro Forma EPS (Accretion / Dilution)

Calculate year-by-year (Year 1-3):

| | Standalone | Pro Forma | Accretion/(Dilution) |
|---|-----------|-----------|---------------------|
| Acquirer net income | | | |
| Target net income | | | |
| Synergies (after tax) | | | |
| Foregone interest on cash (after tax) | | | |
| New debt interest (after tax) | | | |
| Intangible amortization (after tax) | | | |
| Pro forma net income | | | |
| Pro forma shares | | | |
| **Pro forma EPS** | | | |
| **Accretion / (Dilution) %** | | | |

### Step 5: Sensitivity Analysis

**Accretion/Dilution vs. Synergies and Offer Premium:**

| | $0M syn | $25M syn | $50M syn | $75M syn | $100M syn |
|---|---------|----------|----------|----------|-----------|
| 15% premium | | | | | |
| 20% premium | | | | | |
| 25% premium | | | | | |
| 30% premium | | | | | |

**Accretion/Dilution vs. Cash/Stock Mix:**

| | 100% cash | 75/25 | 50/50 | 25/75 | 100% stock |
|---|-----------|-------|-------|-------|------------|
| Year 1 | | | | | |
| Year 2 | | | | | |

### Step 6: Breakeven Synergies

Calculate the minimum synergies needed for the deal to be EPS-neutral in Year 1.

### Step 7: Output

- Excel workbook with:
  - Assumptions tab
  - Sources & uses
  - Pro forma income statement
  - Accretion/dilution summary
  - Sensitivity tables
  - Breakeven analysis
- One-page merger consequences summary for pitch book

## Important Notes

- Always show both GAAP and adjusted (cash) EPS where relevant
- Stock deals: use acquirer's current price for exchange ratio, note dilution from new shares
- Include purchase price allocation — goodwill and intangible amortization matter for GAAP EPS
- Synergy phase-in is critical — Year 1 is often only 25-50% of run-rate synergies
- Don't forget foregone interest income on cash used and new interest expense on debt raised
- Tax rate on synergies and interest adjustments should match the acquirer's marginal rate


## Data sources — MCP first, web fallback

Many passages below say "use the S&P Kensho MCP / Daloopa MCP / FactSet MCP". Those are commercial financial-data MCPs from the original Cowork plugin context. In Engel:

- **If you have any structured financial-data MCP configured** (Engel supports MCP — see `native-mcp` skill), prefer it for point-in-time comps, precedent transactions, and filings.
- **Otherwise**, fall back to:
  - `web_search` / `web_extract` against SEC EDGAR (`https://www.sec.gov/cgi-bin/browse-edgar`) for US filings
  - Company IR pages for press releases, earnings decks
  - `browser_navigate` for interactive data portals
  - User-provided data (explicitly ask when the context doesn't have it)
- **Never fabricate**. If a multiple, precedent, or filing number can't be sourced, flag the cell as `[UNSOURCED]` and surface it to the user.

## Attribution

This skill is adapted from Anthropic's Claude for Financial Services plugin suite (Apache-2.0). The Office-JS / Cowork live-Excel paths have been removed; this version targets headless openpyxl via the `excel-author` skill's conventions. Original: https://github.com/anthropics/financial-services

## Save Contract

- Save durable outputs under Engel AI Main storage, not temporary chat state.
- Update the Engel skill registry after changes.
- Include a receipt path or registry key in the response when this skill creates or changes files.
- Do not expose secrets in skill files, receipts, chat replies, or logs.
