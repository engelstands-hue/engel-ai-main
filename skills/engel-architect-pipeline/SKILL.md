---
name: "engel-architect-pipeline"
description: "Drive the Engel Architect Agent: 13-section discovery-to-engineering pipeline feeding a 10-stage planner with a mandatory Founder Approval Gate at stage H. Use whenever a request mentions the architect, planning a build, plan/spec/prompt outputs, sections, planner stages, or the founder gate."
version: "1.0.0"
source: "claude-skill-creator"
created_at_utc: "2026-08-04T14:56:01Z"
updated_at_utc: "2026-08-04T14:56:01Z"
---

# Engel Architect Pipeline

## Purpose

Turn an idea into an executor-ready plan through `engel_architect_agent.py`: 13 sections (Discovery → Commercial → Quality → Engineering) feeding a 10-stage planner (A through J), pausing hard at stage H for founder approval.

## Trigger Conditions

- The user asks the architect to start, continue, or review a plan.
- A request involves sections, briefs, planner stages, or `plan.md` / `spec.md` / `prompt.md` outputs.
- Someone asks to approve, skip, or retry part of the pipeline.

## Structure

- **Sections (13):** run in order through Discovery, Commercial, Quality, and Engineering phases. Drive with `engel.architect.run_section`, `complete_section`, `retry_section`, `skip_section`, `section_detail`, `sections`.
- **Planner (10 stages, A–J):** track with `engel.architect.planner_status` and `planner_list`.
- **Stage H — Founder Approval Gate:** the pipeline pauses here by design. Surface it with `engel.architect.approval_gate`; only an explicit human decision moves it via `approve_gate` (or `redirect_gate`). Never auto-approve, never bypass, never treat a timeout as consent.
- **Outputs:** `plan.md`, `spec.md`, `prompt.md` → cold Executor handoff (`engel.architect.executor_handoff`).

## State

Everything persists under `memory/architect_state/{sections,briefs,planner,outputs}/`. The pipeline is resumable — check `engel.architect.status` and `engel.architect.overview` before starting new work, and use `engel.architect.continue` rather than restarting.

## Operating Instructions

- All 31 routes live under `engel.architect.*`; run them via `python engel_ai.py ask "<phrase>"` with the D: interpreter.
- Useful supporting routes: `briefs`, `issue_log`, `open_issues`, `tracker_log`, `failure_recovery`, `integration_check`, `legal_scan`, `change_management`, `founder_voice`, `principles`, `modes`.
- Start fresh only when asked: `engel.architect.start_new`; close out with `engel.architect.close`.

## Save Contract

- Stage H requires explicit human approval — report and wait; that is the contract, not a bug.
- Architect outputs stay in `memory/architect_state/outputs/`; hand off to the Executor cold (plan + spec + prompt), not via shared conversational state.
- Report pipeline work under `reports/codex_bridge/<NAME>.md` with section/stage reached and blockers.
