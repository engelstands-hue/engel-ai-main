---
name: "engel-verify-and-report"
description: "The required Engel work pattern: read handoffs, make small safe changes, run verifiers, write a codex_bridge report. Use for every job — and especially whenever a request mentions verifying, the sweep, smoke tests, finishing a job, reports, or whether a change is safe to apply."
version: "1.0.0"
source: "claude-skill-creator"
created_at_utc: "2026-08-04T14:56:01Z"
updated_at_utc: "2026-08-04T14:56:01Z"
---

# Engel Verify and Report

## Purpose

Make every change land the same way: scoped, verified, reported, and approved before apply. This is the safe growth rhythm from the Core Direction and Safety Constitution:

```
observe → propose → verify → report → approve → apply
```

## Trigger Conditions

- Any job is starting (read the handoffs) or finishing (verify + report).
- The user asks to verify, run the sweep, smoke-test, or check whether something broke.
- A change looks like it needs one of the forbidden capabilities — then the answer is stop and report.

## The required work pattern (AGENTS.md)

1. Read `AGENTS.md`, `CODEX_HANDOFF.md`, `CODEX_JOB.md`.
2. Read `wiki/ONE.md` before landing CODE. Update `wiki/ONE.md` and `wiki/organs.json` when organs, talks-to, sources, or duties change.
3. Inspect only the files relevant to the job.
4. Make the small, safe-per-the-rules change.
5. Verify (see below).
6. Stamp Wiki Journal: `runtime\python310\python.exe tools\stamp_wiki_one_journal.py --wiki-read ...`
7. Write a short report under `reports/codex_bridge/<NAME>.md` listing files changed, verifiers run, blockers, and the next recommended packet.

## Verification commands

- Full sweep (90+ verifiers, ~3-5 min): `powershell -ExecutionPolicy Bypass -File scripts/codex_verify.ps1`
- Route smoke (~2-3 min): `python _route_smoke.py`
- One verifier: `python tools/verify_<name>.py`
- Narrow changes: route smoke + the touched module's specific verifier is acceptable; refactors and route changes get the full sweep.
- Always the D: interpreter: `D:\b.WorkSpace\Engel App\runtime\python310\python.exe`.

## Hard safety rules — stop and report instead of implementing

Never add or enable: provider/API/network calls or live research; autonomous loops, background workers, Level 2 autonomy; trusted-memory writes, queue mutation, learning-apply; digest/history or `ALIVE_STATE` writes; source edits outside the job's allowed files; Ollama/localhost-provider/old-provider paths. Apply steps require verifier checks **and** explicit human approval — authority order is Josh > Guardian > Engel/runtime.

## Read-first map

| Before changing | Read first |
|---|---|
| Any CODE landing on this Windows body | `wiki/ONE.md` (Wiki One — also update it when organs change) |
| Routes / `UPDATE_ROUTES` | `memory/ROUTE_METADATA_REFERENCE_MAP_V1.md`, `memory/ROUTE_METADATA_VERIFIER_CONTRACT_V1.md` |
| Multi-module refactor | `memory/ENGEL_REFACTOR_SAFETY_CONTRACT_V1.md` |
| Bridge / runtime / autonomy | `memory/ENGEL_CORE_DIRECTION_AND_SAFETY_CONSTITUTION_V1.md` |
| Meeting Room dispatcher | `memory/ENGEL_AGENT_MEETING_ROOM_CONTRACT_V1.md` |
| Android workers | `engel_android_remote_worker_contract.py` + the mobile contract V1 |

## Save Contract

- No job is done without its `reports/codex_bridge/<NAME>.md` report.
- Reports name the verifiers actually run, not just "verified".
- Recent reports are the orientation pass for the next worker — write them to be read.
