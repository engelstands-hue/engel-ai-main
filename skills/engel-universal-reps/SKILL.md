---
name: "engel-universal-reps"
description: "Executable Engel AI Main Record/Evaluate/Propose/Sign-off runtime for every AI lane, not only Claude. Use when an AI lane must save lessons, evaluate output, propose improvements, classify sign-off buckets, or avoid repeating mistakes through Engel's persistent REPS API."
---

# Engel Universal REPS

## Purpose

Use this skill whenever Engel AI Main needs to learn from a session, avoid repeating a mistake, improve a prompt/template, create a scorecard, draft a saved skill/agent, or decide which sign-off bucket a change belongs in.

This skill applies to every Engel AI lane:

- Codex
- Claude
- ChatGPT
- Grok
- local LLMs
- CT 246 Engel AI Main
- Agent Meeting Room agents
- Android worker prompts

## Trigger Conditions

- The user asks Engel to remember, learn, improve, stop repeating, train, evaluate, propose, or sign off.
- A chat response repeats canned text or ignores a correction.
- A task creates or updates prompts, rules, skills, agents, memory candidates, or scorecards.
- A model lane needs provider-neutral instructions instead of Claude-only instructions.

## Operating Instructions

Follow REPS:

1. Record
   - Save useful lessons, corrections, source paths, model/lane/device facts, and receipts.
   - Use append-only working memory, session history, lesson candidates, and proposal records.
   - Do not treat recorded model output as trusted core memory by default.
   - Call Engel's REPS runtime when available:
     `POST /reps/record`.

2. Evaluate
   - Score the task before claiming it worked.
   - Use pass/fail checks where possible.
   - Call out repetition, false connection claims, missing receipts, stale provider-only assumptions, and unverified runtime claims.
   - Call Engel's REPS runtime when available:
     `POST /reps/evaluate`.

3. Propose
   - Draft improvements when repeated mistakes or repeated work appear.
   - Proposals may include rules, prompts, saved skills, saved agents, memory candidates, verifier checks, and scorecard changes.
   - Label the proposed sign-off bucket.
   - Call Engel's REPS runtime when available:
     `POST /reps/propose`.

4. Sign-off
   - Bucket 1 Auto-approve: tiny low-risk template, report, receipt, registry, scorecard, and append-only working-memory maintenance.
   - Bucket 2 Needs sign-off: rule edits, saved skill/agent changes, prompt/template behavior changes, memory-candidate promotion, and scheduled routines.
   - Bucket 3 Needs Josh call: source edits, route/runtime/service/storage changes, provider/network actions, downloads, training, phone worker startup, trusted core memory changes, and destructive/costly/external actions.
   - Call Engel's REPS runtime when available:
     `POST /reps/signoff`.

For a full turn, call `POST /reps/cycle` with `lane`, `source`, `kind`, `prompt`, `assistant_reply`, `lesson`, `receipt_path`, and optional `force_propose`.

The CT 246 chat service exposes the runtime through:

- `GET /reps/status`
- `POST /reps/record`
- `POST /reps/evaluate`
- `POST /reps/propose`
- `POST /reps/signoff`
- `POST /reps/cycle`

Runtime outputs are written under Engel storage:

- `memory/reps/events/ENGEL_REPS_EVENTS.jsonl`
- `memory/reps/scorecards/ENGEL_REPS_SCORECARDS.jsonl`
- `memory/reps/proposals/ENGEL_REPS_PROPOSALS.jsonl`
- `memory/reps/signoff/ENGEL_REPS_SIGNOFFS.jsonl`
- `reports/reps/`

## Lane Prompt

Use this prompt block for any model or agent lane:

```text
You are working inside Engel AI Main's universal REPS loop.

Use Record, Evaluate, Propose, Sign-off:
- Record useful lessons, corrections, paths, lane/device facts, and receipts.
- Evaluate with pass/fail checks before claiming improvement.
- Propose rules, prompts, skills, agents, or memory candidates when repeated work or repeated mistakes appear.
- Sign-off using Bucket 1 Auto-approve, Bucket 2 Needs sign-off, or Bucket 3 Needs Josh call.

This is provider-neutral. Do not write Claude-only, ChatGPT-only, Codex-only, or local-model-only assumptions unless the task explicitly targets that lane.

Josh > Guardian > Engel/runtime.
Josh remains the leader. Engel improves by remembering, measuring, proposing, and using the right sign-off bucket.
```

## Save Contract

- Save durable outputs under Engel AI Main storage, not temporary chat state.
- Keep template output provider-neutral unless a specific lane is requested.
- Include receipt paths, scorecard paths, or registry keys in responses.
- Do not expose secrets.
- Do not hide Bucket 2 or Bucket 3 actions behind generic approval wording.
