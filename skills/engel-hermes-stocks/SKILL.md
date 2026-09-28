---
name: "engel-hermes-stocks"
description: "Stock quotes, history, search, compare, crypto via Yahoo."
version: "1.0.0"
source: "engel-ai-main-server"
created_at_utc: "2026-08-26T00:56:15Z"
updated_at_utc: "2026-08-26T00:56:15Z"
---

# Engel Stocks

## Purpose

Stock quotes, history, search, compare, crypto via Yahoo.

## Trigger Conditions

- stocks
- optional hermes stocks
- engel hermes stocks

## Operating Instructions

Operate as Engel AI Main. Authority order is Josh > Guardian > Engel/runtime. This is a recreated Engel skill, not a live Hermes optional plugin. Use local Engel storage, routes, and receipts. Do not add provider/API/network calls, live trading keys, trusted-memory writes, queue mutation, ALIVE_STATE writes, autonomous loops, Level 2 runtime, or C: project writes. Do not print secrets, tokens, or private keys. Source remains on disk; this saved card does not enable the upstream tool by itself.

Paper/research only. No live brokerage keys.

Source card: engel_agent_main/optional-skills/finance/stocks/SKILL.md

Stock quotes, history, search, compare, crypto via Yahoo.

# Stocks Skill

Read-only market data via Yahoo Finance. Five commands: `quote`, `search`,
`history`, `compare`, `crypto`. Python stdlib only — no API key, no pip
installs. Yahoo's endpoint is unofficial and may rate-limit or change.

## When to Use

- User asks for a current stock price (AAPL, TSLA, MSFT, ...)
- User wants to look up a ticker by company name
- User wants OHLCV history or performance over a date range
- User wants to compare several tickers side by side
- User asks for a crypto price (BTC, ETH, SOL, ...)

## Prerequisites

Python 3.8+ stdlib only. Optional: set `ALPHA_VANTAGE_KEY` to enrich
`market_cap`, `pe_ratio`, and 52-week levels when Yahoo's crumb-protected
fields come back null. Free key: https://www.alphavantage.co/support/#api-key

## How to Run

Invoke through the `terminal` tool. Once installed:

```
SCRIPT=~/.engel/skills/finance/stocks/scripts/stocks_client.py
python3 $SCRIPT quote AAPL
```

All output is JSON on stdout — pipe through `jq` if you want to slice it.

## Quick Reference

```
python3 $SCRIPT quote AAPL
python3 $SCRIPT quote AAPL MSFT GOOGL TSLA
python3 $SCRIPT search "Tesla"
python3 $SCRIPT history NVDA --range 6mo
python3 $SCRIPT compare AAPL MSFT GOOGL
python3 $SCRIPT crypto BTC ETH SOL
```

## Commands

### `quote SYMBOL [SYMBOL2 ...]`

Current price, change, change%, volume, 52-week high/low.

### `search QUERY`

Find tickers by company name. Returns top 5: symbol, name, exchange, type.

### `history SYMBOL [--range RANGE]`

Daily OHLCV plus stats (min, max, avg, total return %). Ranges: `1mo`,
`3mo`, `6mo`, `1y`, `5y`. Default: `1mo`.

### `compare SYMBOL1 SYMBOL2 [...]`

Side-by-side: price, change%, 52-week performance.

### `crypto SYMBOL [SYMBOL2 ...]`

Crypto prices. Pass `BTC` (the script appends `-USD` automatically).

## Pitfalls

- Yahoo Finance's API is unofficial. Endpoints can change or rate-limit
  without notice — if requests start failing, that's why.
- `market_cap` and `pe_ratio` may return null on `quote` when Yahoo's
  crumb session isn't established. Set `ALPHA_VANTAGE_KEY` to backfill.
- Add a small delay between bulk requests to avoid rate-limiting.
- This is read-only — no order placement, no account integration.

## Verification

```
python3 ~/.engel/skills/finance/stocks/scripts/stocks_client.py quote AAPL
```

Returns a JSON object with `symbol: "AAPL"` and a numeric `price` field.

## Save Contract

- Save durable outputs under Engel AI Main storage, not temporary chat state.
- Update the Engel skill registry after changes.
- Include a receipt path or registry key in the response when this skill creates or changes files.
- Do not expose secrets in skill files, receipts, chat replies, or logs.
