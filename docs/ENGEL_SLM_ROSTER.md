# Engel AI Main — canonical SLM roster

Engineering review — 2026-08-02. Status: six-head registry shipped; two heads are
still collecting real evidence and may not influence decisions.

## Purpose

Engel uses small, local classifiers for narrow predictions that are faster and more
auditable than asking a generative model. The source of truth is
`tools/engel_slm_roster.py`. The dataset builder, trainer, runtime, real-training
cycle, desktop roster, and verifiers must all preserve its order and contracts.

Every head is **advisory only**. Deterministic code remains authoritative for action
permission, safety, training admission, trusted-memory promotion, provider health,
model deployment, retry bounds, and persistence.

## The six heads

| Head | What it predicts | Lifecycle | Runtime consumer |
|---|---|---|---|
| `intent_router` | chat, build, training, or Meeting Room intent | active | Governor features and chat receipt |
| `route_governor` | best local lane from bounded route features | collecting data | Governor shadow receipt only |
| `style_checks` | which proven reply-style checks may fail | active | chat advisory receipt |
| `reply_grader` | clean reply or repair likely needed | active | chat advisory receipt |
| `train_admit` | shadow opinion on reviewed training material | shadow candidate | prompt-training telemetry only |
| `failure_triage` | whether one bounded Forge repair is likely to work | collecting data | Code Forge telemetry only |

The ordinary training default is `intent_router,style_checks,reply_grader,train_admit`.
The two collecting-data heads are deliberately excluded until they have enough real,
balanced observations. `--slm-tasks all` is available for an explicit review run; a
below-gate requested head makes that run partial and cannot be mirrored as eligible.

## Current evidence

The local mirror's 2026-08-01 report records:

- `intent_router`: gate passed, macro-F1 0.9076, lift 0.0661;
- `style_checks`: gate passed for 4 of 6 trained check heads, aggregate macro-F1 0.8584;
- `reply_grader`: gate passed, macro-F1 0.7498, lift 0.0399;
- `train_admit`: below the data floor with 15 admit and 5 reject examples;
- `route_governor`: no eligible training result yet;
- `failure_triage`: no eligible training result yet.

These are historical evidence, not a claim that a retrain ran during this review.
Legacy v1 artifacts remain readable behind their recorded gates. The next training
run emits v2 reports and artifacts pinned by task contract version, dataset SHA-256,
and artifact SHA-256.

## Data contracts

`route_governor` learns only the allowlisted route features in the registry. The
label, rule ID, approval state, gate outcomes, and free-form metadata are removed.
Normal chat receipts now retain the T0 route feature/verdict pair so a real corpus can
accumulate while T0 continues to decide.

`failure_triage` no longer derives labels from the same status/error text given to the
classifier. It uses Code Forge's observed `fixed_by_next` outcome:
`repair_succeeded` or `repair_failed`. Missing outcomes, successful `error_class=none`
rounds, and exact duplicates do not enter this dataset.

## Serving and promotion

The runtime loads only a task that is canonical and marked `ok=true` in the latest
report. V2 loading additionally requires artifact schema, task name, contract version,
and file hash to match that report. Loading and prediction fail open: absence or model
failure removes the advisory, never blocks chat or weakens a deterministic gate.

The real-training cycle mirrors only files named in `trained_ok`; it does not wildcard
copy stale or rejected `.joblib` files. A candidate may move from collecting data to
shadow only after class balance, leakage, macro-F1, and lift gates pass. Moving a shadow
head into any decision path requires a separate reviewed change and disagreement data.

## Verification

- `tools/verify_engel_slm_roster.py`: registry completeness, authority boundary,
  data leakage boundaries, producer/UI parity, and safe mirroring.
- `tools/verify_engel_slm_runtime.py`: gate-aware artifact loading, v2 pinning,
  fail-open prediction, and consumer wiring.
- `tools/verify_engel_slm.py`: training metrics, leakage, report, and artifact gate.
- `tools/verify_engel_real_training.py`: prompt-pack-to-training and orchestrator joins.

All are registered in `scripts/codex_verify.ps1`; a new head is incomplete until the
registry, its real label source, runtime method, consumer, UI row, and these gates agree.
