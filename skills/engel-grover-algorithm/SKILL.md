---
name: "engel-grover-algorithm"
description: "Verified Grover quadratic-search logic for Engel AI Main: explain, simulate, and AES-bit heuristic with Shor/PQC caveats. Local only."
version: "1.0.0"
source: "engel-ai-main-server"
created_at_utc: "2026-08-20T16:39:06Z"
updated_at_utc: "2026-08-20T16:39:06Z"
---

# Engel Grover Algorithm

## Purpose

Verified Grover quadratic-search logic for Engel AI Main: explain, simulate, and AES-bit heuristic with Shor/PQC caveats. Local only.

## Trigger Conditions

- grover algorithm
- explain grover
- grover search
- quantum unstructured search
- grover aes

## Operating Instructions

When Josh or chat asks about Grover, quantum unstructured search, Grover vs Shor, or AES Grover security, use Engel's grover lane instead of guessing. Call engel_grover_lane.answer_grover_prompt or the routes engel.grover.explain, engel.grover.search, engel.grover.crypto, engel.grover.status. State: classical O(N), Grover O(sqrt(N)) with about pi/4 sqrt(N) queries; oracle plus diffusion; success is sin^2((2k+1)theta) and overshooting hurts; quadratic not exponential; Shor breaks RSA; AES-128 ~64-bit Grover heuristic but iterations are sequential and public-key still needs PQC. Simulate only for N<=1024. No provider, no trusted-memory write, no quantum hardware.

## Save Contract

- Save durable outputs under Engel AI Main storage, not temporary chat state.
- Update the Engel skill registry after changes.
- Include a receipt path or registry key in the response when this skill creates or changes files.
- Do not expose secrets in skill files, receipts, chat replies, or logs.
