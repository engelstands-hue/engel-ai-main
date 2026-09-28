# CODEX_JOB.md - Engel App Standing Codex Guidance

Status: CURRENT / STANDING_GUIDANCE / DOCS_CONFIG_ONLY

Date: 2026-05-12

## Active Workspace

Codex work for this project must use:

```text
D:\b.WorkSpace\Engel App
```

Historical reports may still mention `D:\Engel App`; current active workspace root is `D:\b.WorkSpace\Engel App`.

Do not follow older handoff text that points to another drive or an already-completed route implementation task.

## CT246 Server-First Runtime And Storage

Engel AI Main is one system centered on CT 246 `engel-ai-main` on the Dell PowerEdge server. The ROG laptop is the face/controller and may act as an explicitly requested GPU helper lane, but it is not the default storage or long-lived runtime home.

Use this storage split for new work unless Josh gives a newer explicit instruction:

```text
CT246 SSD /opt/engel:
- active chat/model services
- active local LLMs and adapters
- persistent memory
- Agent Meeting Room state
- current receipts, logs, and service state
- source-of-truth runtime files

Dell server HDD/ZFS engel-hdd-vault:
- model archives
- datasets
- old checkpoints
- large training outputs
- snapshots and transfer staging

CT245, the retired external storage array, `/mnt/engel-vault`, laptop external drives, and Windows-only model paths are permanently outside Engel AI Main's topology. Do not probe, mount, start, copy to, or create a re-enable path for them.
```

## Governing Safety Document

Before any future Engel growth task, read:

```text
memory\ENGEL_CORE_DIRECTION_AND_SAFETY_CONSTITUTION_V1.md
```

The EY constitution is the governing safety document for colony, swarm, mycelium, memory, research, proposal, autonomy, source-edit, provider/network, and trusted-memory work.

Core rule:

```text
Engel may observe, organize, compare, research, summarize, propose, verify, and report.
Engel may not trust, write, mutate, execute, enable, self-edit, or apply changes without verifier checks and explicit human approval.
```

Important execution clarification:

```text
When Josh explicitly asks in the active conversation to build, fix, wire, install, train, update, run, or proceed with a named task, that is explicit human approval for that bounded task. Do not convert the request into a read-only plan when the requested action is discoverable, scoped, and verifier-covered. Execute the approved safe parts, verify them, write the receipt, and only stage the pieces that remain unclear, destructive, secret-bearing, or outside the active approval.
```

## Standing Work Rules

- Read `wiki/ONE.md` before landing CODE. Update `wiki/ONE.md` and `wiki/organs.json` when organs, talks-to, sources, or duties change. Stamp Wiki Journal after CODE with `tools/stamp_wiki_one_journal.py --wiki-read`.
- Work one Codex task at a time.
- Use the active user packet as the job source of truth.
- Keep changes inside the task's allowed files.
- Do not broaden the job into runtime behavior, route behavior, provider/API/network behavior, background workers, autonomous loops, trusted-memory writes, source-edit behavior, queue mutation, digest/history writes, or `ALIVE_STATE` writes.
- Do not use the approval model as a blanket read-only block. If the active packet explicitly approves a bounded source edit, route/runtime change, service action, model-training pass, or device action, perform that approved work with receipts and verifiers while preserving hard safety boundaries.
- All .grok (Grok harness/skills/config/state) must live under and write only to D:\b.WorkSpace\Engel App\.grok (C: location is junction only). No code, scripts, or env may target or write C:\Users\...\ .grok paths. Enforce in launchers and verifiers.
- Do not perform a broad refactor unless a separate refactor safety contract explicitly approves scope, files, verification, rollback, and stop conditions.
- Do not add autonomy, provider/network behavior, background behavior, trusted-write behavior, source-edit behavior, queue mutation, digest/history writes, or `ALIVE_STATE` writes unless the active packet explicitly approves it and verifier coverage exists.
- Every major step needs a report, checkpoint, verification results, changed-files summary, warnings, and next safe step.

## Important Approval-Token Boundary

The user may provide `APPROVE_PROMOTE_MEMORY_CANDIDATE` for the approved memory candidate path. This token may only be recognized by the existing Approved Memory Promotion flow.

Research-to-Fix Loop V1, Fix Candidate Queue V1, Code Companion patch review, and any future patch/apply flow must not treat `APPROVE_PROMOTE_MEMORY_CANDIDATE` as permission to apply fixes, edit source, mutate routes, promote fix candidates, mark fix candidates approved, or mark any fix candidate as applied.

The Research-to-Fix / Fix Candidate chain remains separate:

```text
Research / candidate learning output
-> Candidate Learning Output Review
-> Research-to-Fix Loop V1
-> Fix Candidate Queue
-> human review
-> APPROVE_FIX_CANDIDATE
-> future patch/apply flow
```

The memory promotion chain remains separate:

```text
Memory Candidate Proposal
-> Approved Memory Promotion
-> APPROVE_PROMOTE_MEMORY_CANDIDATE
-> trusted memory write, only if all gates pass
```

`APPROVE_PROMOTE_MEMORY_CANDIDATE` is not `APPROVE_FIX_CANDIDATE`. A future fix candidate approval must require the separate `APPROVE_FIX_CANDIDATE` token and its own verifier-covered protected apply flow.

## Current Safety Order

Current project order:

1. EY Engel Core Direction and Safety Constitution - complete.
2. EZ Codex Job and Next Baton Alignment Cleanup - complete.
3. EW-A Launch Safety Guard Tool/Status Hardening - complete.
4. EX Refactor Safety Contract - complete.
5. EY2 Route and Command Metadata Inventory - complete.
6. EY3 Route and Command Metadata Documentation Normalization - complete.
7. EY4 Route Metadata Verifier Contract - complete.
8. EY5 Implement Static Route Metadata Contract Verifier - complete.
9. EY6 Route Metadata Reference Map - complete.
10. First tiny refactor slice only if Josh explicitly chooses refactor next and uses the static verifier before/after.
11. FK Research Source Fixture Contract, only after safety alignment remains clean and still approved as contract-only/no live research.

FK remains queued, but launch-safety hardening, Codex alignment, the refactor safety contract, route metadata inventory, metadata documentation normalization, route metadata verifier, and EY6 route metadata reference map are higher-priority safety prerequisites.

Before route handler movement or metadata-driven dispatcher refactor, preserve the EY3 side-effect classes:

- pure read-only status
- status-like with known report/log side effects
- preview-only
- report-only
- `APPROVE_REPORT`
- `APPROVE` / approval-required
- proposal-only
- trusted-write
- source-edit
- disabled/future
- unknown / needs review

`health`, `router status`, and `tool registry status` are status-like but not pure read-only when they write reports/logs. Future smoke checks should prefer pure read-only routes unless the active task explicitly allows known report/log side effects.

Before implementing any route metadata verifier, read:

```text
memory\ROUTE_METADATA_VERIFIER_CONTRACT_V1.md
```

Route metadata must never make a command look safer than it actually is. EY5 implements `tools\verify_route_metadata_contract.py` as a direct/optional static verifier, not part of the eight-verifier standard sequence unless a later promotion task approves it.

EY6 adds `memory\ROUTE_METADATA_REFERENCE_MAP_V1.md` as a reference map only. It does not move handlers, change route behavior, change write behavior, execute side-effecting routes, or perform a refactor. Future route metadata/refactor slices must run `python .\tools\verify_route_metadata_contract.py` before and after the change.

Before any broad cleanup, restructuring, route reorganization, or module extraction, read:

```text
memory\ENGEL_REFACTOR_SAFETY_CONTRACT_V1.md
```

## Default Verification

For docs/config/report-only work, run the verification requested by the active packet. At minimum:

```powershell
python -m json.tool memory\<checkpoint>.json
python .\tools\verify_living_systems_documentation_drift.py
powershell -ExecutionPolicy Bypass -File scripts\codex_verify.ps1
```

Run the full standard verifier sequence only when appropriate for the scope and allowed outputs. Some standard verifiers intentionally create report-only artifacts, so do not run them when a task's allowed-file list excludes those artifacts unless the active packet explicitly permits it.

Run `py_compile` only when Python files are touched or the active packet requires it.

## Definition of Done

A Codex task is complete only when:

- the assigned scope is handled
- stale guidance is removed or clearly superseded
- verification has run or a scoped reason for skipping a broader verifier is recorded
- report and checkpoint exist when requested
- no forbidden behavior was added
- the final response lists status, files changed, verification commands, results, warnings, and next safe step
