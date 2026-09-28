from __future__ import annotations

from pathlib import Path


_file = globals().get("__file__")
if not _file or not isinstance(_file, str) or _file.startswith("<"):
    ROOT = Path.cwd()
else:
    try:
        ROOT = Path(_file).resolve().parents[1]
    except (OSError, ValueError, IndexError):
        ROOT = Path.cwd()
OUTPUT_PATH = ROOT / "reports" / "next_work" / "NEXT_WORK_BATON_DX.md"

LAST_COMPLETED_STEP = "DW Living Systems + Security Unified Guardrail Review"
NEXT_RECOMMENDED_STEP = "DY Direct Security Verifier Batch Runbook Contract"
SOURCE_OF_NEXT_STEP_TRUTH = (
    "V2APP-DW guardrail review and the human-approved DX baton refresh task"
)
LATEST_CHECKPOINT_KNOWN_TO_DOCS = "V2APP-DW"
GENERATED_AFTER_LATEST_CHECKPOINT_KNOWN_TO_DOCS = "YES"


BATON_TEXT = f"""# Engel Next Work Baton DX

Status: LOCAL_PACKET_ONLY / HUMAN_INVOKED / GENERATE_PACKET_ONLY / NO_AUTONOMY

## Current Completed Step

{LAST_COMPLETED_STEP}

## Next Recommended Step

{NEXT_RECOMMENDED_STEP}

## Target Freshness

- Last completed step: {LAST_COMPLETED_STEP}
- Next recommended step: {NEXT_RECOMMENDED_STEP}
- Source of next-step truth: {SOURCE_OF_NEXT_STEP_TRUTH}
- Latest checkpoint known to docs: {LATEST_CHECKPOINT_KNOWN_TO_DOCS}
- Generated after latest checkpoint known to docs: {GENERATED_AFTER_LATEST_CHECKPOINT_KNOWN_TO_DOCS}
- Stale packets are informational only. They must not auto-run, auto-refresh, self-advance, execute routes, run verifiers, mutate queues, or change the next step by themselves.

## Safe Posture

docs/config/verifier-first

## Allowed Scope

- docs
- memory indexes
- command docs
- reports
- checkpoint JSON
- direct verifier runbook/decision files

## Forbidden

- trusted apply
- rollback
- lesson candidate creation route
- simulation runtime
- mycelium signal propagation
- provider/API/network behavior
- live research
- background worker
- autonomous loop
- queue mutation
- trusted-memory write
- digest/history write
- ALIVE_STATE write
- route implementation changes
- remediation code changes unless Josh explicitly approves one specific item
- verifier weakening
- self-advancing baton behavior

## Required Verification

- JSON validation
- py_compile
- direct lesson verifier
- direct mycelium verifier
- all eight standard verifiers
- CLI read-only/status route smoke checks
- no-file/no-report route snapshots
- forbidden flag search
- active old-provider/local-endpoint search

## Next Safe Candidate Queue

1. DY Direct Security Verifier Batch Runbook Contract [docs/config only]
2. DZ Security Regression Packaging/Manifest Inventory Decision [read-only decision/report only]
3. EA Security Regression Result Archive Index [docs/report index only]
4. EB First approved low-risk security hardening patch [only if Josh explicitly selects one remediation item]
5. EC Security verifier promotion or separate security sequence revisit [decision/report only]

## Completion Response Template

Files changed:

What changed:

Verification passed:

Notes:

Recommended next:

## Safety Boundary

This packet is a local handoff note only. It does not execute the next task, run verifiers, start a background worker, call providers or network paths, perform live research, mutate queues, write trusted memory, write digest/history, write ALIVE_STATE, apply lessons, roll back changes, create candidates, enable simulation runtime, enable mycelium signal propagation, or enable autonomy.

The baton tool does not auto-detect next steps by executing project routes. It does not run builds, run tests, run verifiers, watch files, schedule work, call external services, or advance the task queue by itself.
"""


def main() -> int:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(BATON_TEXT, encoding="utf-8")
    print(f"NEXT_WORK_BATON_CREATED={OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
