# Engel AI Main — Governor, Lane Routing, and Memory Hygiene

Design spec — 2026-07-31. Senior design engineer pass.
Status: T0 SHIPPED; T1 DATA COLLECTION ACTIVE (implementation phased below).
Supersedes nothing; extends the chat lane, SLM roster, and prompt-training pipeline.

---

## 0. Why this exists

Three defects share one root cause: **Engel has no single place that decides.** Routing,
policy gating, quality admission, and memory retention are each decided by ad-hoc code
scattered across the chat service, the trainer, and the lanes. Consequences observed live:

1. **Routing is content-guessed, not intent-known.** Two independent exclusions send
   teaching-math to the weak lane:
   - **The digit gate (the deterministic one).** `detect_math_reasoning_request`
     (`tools/engel_math_lane.py:155-172`) — the *only* non-explicit path to a real
     reasoning model — requires a **digit** in the prompt. "Explain the chain rule",
     "derive why this holds", and every conceptual/teaching math prompt therefore fail
     it structurally, regardless of difficulty.
   - **The scoring threshold.** `_sparse_moe_route_decision`
     (`tools/engel_main_server_chat_http_service.py:7157`) needs `score >= 3`; short hard
     technical questions rarely reach it.

   Result: the turn falls to the default aligned 7B on the RTX 2070, which echoes the
   answer contract instead of solving. The system already *has* a capable lane —
   sparse-MoE Qwen3-30B produced a correct, CAS-consistent `Result/Work/Check` on the
   same prompt. It simply was never asked.
2. **Training turns poison their own context.** Training prompts persist into
   `ENGEL_AI_MAIN_LLM_CHAT_MEMORY.jsonl`, including the injected answer contract.
   `_recent_chat_records_uncached` (`:~1505`) filters ok/quality/rejected/scope but has
   **no training-turn skip**, so a training turn is reloaded verbatim into "RECENT ENGEL
   CHAT CONTEXT" and the 7B parrots it. The pipeline manufactures its own echo bait.
   Compounding it: **there are two physical stores** sharing that filename — the ROG `D:`
   copy and the CT `/opt/engel` copy — and the ROG records carry **neither** discriminator
   field today (0 of 875 live records). Patching one side leaves the loop open on the other.
3. **No governance identity.** There is no component that can answer "why was this turn
   routed here, admitted as a sample, or persisted?" with a receipt.

The fix is a **Governor**: a decision plane Engel owns, consulted by the lanes, that
emits an auditable verdict per decision. It decides; it never executes.

---

## 1. Governor — what it is (and is not)

**Is:** a policy/decision plane. Pure functions plus a small learned classifier, returning
`GovernorVerdict` records that callers enforce and that land in receipts.

**Is not:** a chat model, a proxy in front of the model, a new network service, or a
component that performs side effects. The Governor never writes files, never calls a
provider, never kills a process. It answers questions.

### 1.1 Three tiers, deliberately

| Tier | Mechanism | Latency budget | Availability | Role |
|---|---|---|---|---|
| **T0** | Deterministic rules (Python, in-process) | < 1 ms | always | Source of truth. Every decision has a T0 answer. |
| **T1** | Governor **SLM** — embedding + linear head, receipt-trained | < 50 ms | best-effort | Sharpens T0 on ambiguous inputs. Advisory → shadow → in-path. |
| **T2** | Governor **LLM** escalation — existing sparse-MoE 30B / deepseek-r1 | seconds | rare | Only for T0-`uncertain` + high-stakes. Never per-turn. |

**Why not "just an LLM governor":** a Governor consulted on every turn sits in the
latency path of all chat. deepseek-r1 on CT246 CPU measures **3.69 tok/s at 12 threads** —
using it per-turn would add seconds to every reply. The RTX 2070 (8 GB) is already held by
the aligned chat 7B plus the image lane and cannot co-resident a second 7B. Therefore the
per-turn governor **must** be a T0 rule set with an optional tiny T1 head, and LLM
judgement is reserved for the rare hard call. This is a hardware fact, not a preference.

### 1.2 Fail-safety is asymmetric — the most important rule

A single fail-open or fail-closed policy would be wrong. The Governor's failure behaviour
is **per decision class**:

| Decision class | On Governor error/timeout | Rationale |
|---|---|---|
| `route` | **fail-open** → current default lane | A routing outage must never break chat. Degrade to today's behaviour. |
| `allow` (action gating) | **fail-closed** → deny | Never launch a build/train/fleet action on an unresolved verdict. |
| `admit` (training sample) | **fail-closed** → do not capture | An uncaptured good sample costs nothing; a captured bad one poisons the corpus. |
| `persist` | **fail-closed on context-visibility** → persist but mark `context_eligible: false` | Keep the receipt (corpus value), withhold it from context until judged. |
| `escalate` | **fail-open** → do not escalate | Escalation is an optimisation, not a safety control. |

Encoded as `_FAILSAFE = {"route": "open", "allow": "closed", "admit": "closed",
"persist": "closed_context", "escalate": "open"}` and asserted by the verifier.

### 1.3 Verdict contract

```python
GovernorVerdict = {
  "decision":      "route" | "allow" | "admit" | "persist" | "escalate",
  "outcome":       str,     # lane id, "allow"/"deny", True/False — class-specific
  "confidence":    float,   # 0.0-1.0; T0 rules emit 1.0 or a calibrated band
  "reason":        str,      # human-readable, names the rule that fired
  "rule_id":       str,      # stable id, e.g. "route.discipline.math"
  "tier":          "T0" | "T1" | "T2",
  "model_id":      str,      # "" for T0
  "fallback_used": bool,
  "latency_ms":    float,
  "inputs_hash":   str,      # sha256 of the feature dict — makes T0 replayable
}
```

Two invariants the verifier enforces:
- **Replayability.** T0 is a pure function of the feature dict: same `inputs_hash` ⇒ same
  `outcome`. No clock, no randomness, no network. This is what makes a routing decision
  auditable months later.
- **No silent tier drift.** If T1 overrides T0, both verdicts are recorded and the
  disagreement is logged. A promotion can never be inferred from a quiet win rate.

### 1.4 Deployment: no new network service

T0 and T1 run **in-process** inside the chat service (and are importable by the trainer).
T2 reuses lanes that already exist. **No new port, no new listener, nothing new to
firewall.** This is deliberate: the 2026-07-10 attack-surface audit found unauthenticated
LAN RCE on bridge ports that had been added casually. The Governor adds zero surface.

---

## 2. Decision classes in detail

### 2.1 `route` — lane selection

**Precedence (highest wins).** Ambiguity here is what produced the current mess, so the
order is explicit and tested:

1. **Operator explicit** — `request.model_mode / local_model / model / lane` ∈
   `{moe, sparse_moe, 30b-a3b, …}`, or explicit prose ("use the 30B lane"). Already
   honoured at `:7187`. The Governor must never override an explicit human choice.
2. **Reserved-lane guard** — code-artifact/build requests stay on the coder + conical
   build path (`prompt_requests_code_artifact`, `:7211`). Routing is not a build bypass.
3. **Deterministic math lane** — computable asks are CAS-verified and served or refused
   (`engel_math_lane.compute`, gated on `verified=True`). Unchanged.
4. **Discipline hint** (NEW) — a training turn declares `training_discipline`
   (`math`/`engineering`/`aec`) via trusted local metadata.
5. **Governor T0/T1 verdict** (NEW) — features below.
6. **Existing automatic heuristics** — `_sparse_moe_route_decision` scoring, unchanged as
   the fallback.
7. **Default** — aligned 7B on the 2070.

**Lane capability matrix.** The missing artefact; routing was never written against one.

| Lane | Host | Strengths | Latency | Route when |
|---|---|---|---|---|
| `engel_math_lane` (sympy) | CT CPU | exact, verified-or-refuse | ms | computable math |
| `ct_sparse_moe_specialist` (Qwen3-30B-A3B) | CT CPU | multi-step reasoning, math work-through | slow-ish | math/engineering **non-interactive**; hard reasoning |
| `deepseek-r1` reasoner | CT CPU (3.69 tok/s) | word problems, proofs | very slow | math the CAS declined, **non-interactive only** |
| `main_server_deep_local_specialist` (14B) | CT | long context, grounded engineering | medium | engineering with large context |
| `local-cuda-qwen-coder` | ROG GPU | code artifacts | fast | code/build lane |
| aligned 7B + vipy LoRA | ROG GPU (2070) | persona, voice, interactive chat | fast (~35 tok/s) | default, all interactive chat, `aec` |

**Interactivity is a first-class routing feature.** This is the detail that makes the fix
safe. Heavy CT lanes are *slower* than the 2070 7B. Blanket-routing math to the 30B would
make interactive chat feel broken. So the Governor keys on `(discipline, interactive)`:

- `interactive=True` (a human is waiting in the composer) → latency-bounded lanes; escalate
  only when the content genuinely warrants it (today's heuristics).
- `interactive=False` (training turns, scheduled work, background jobs) → **quality over
  latency**; math/engineering go straight to the capable lane.

Training turns are inherently non-interactive — cadence is minutes per prompt. Spending 40 s
on a correct, capturable answer is strictly better than 3 s on an echo. This single feature
resolves the yield problem without degrading chat.

**T0 route features:** `discipline`, `interactive`, `intent` (from the shipped
`intent_router` SLM, macro-F1 0.918), `prompt_len`, `math_token_density`,
`explicit_lane_request`, `is_code_artifact`, `context_bytes`, `caller` (`chat_ui` /
`trainer` / `cron`), `lane_health` (is the lane loaded/reachable).

**Kill switch:** `ENGEL_GOVERNOR_ROUTING_ENABLED` (default on), matching the existing
`ENGEL_MOE_REASON_AUTO_ROUTE` convention. Off ⇒ byte-identical legacy behaviour.

#### 2.1.1 Two traps that dictate the implementation

**(a) Never route by setting `_escalate_past_quick`.** The specialist lanes are guarded by
`not request.get("_escalate_past_quick")` (MoE `:12256`, 14B `:12282`), while the reflex /
large-reasoning heuristics (`:11884-11891`, `:5459`) set that flag with the **7B big lane**
as the target. So the intuitive "escalate this turn" move **skips the exact lane we want**.
A reasoning route must **dispatch the specialist receipt directly**
(`_sparse_moe_local_model_receipt` / `_math_reasoning_receipt`) *before* anything sets that
flag. This is the single easiest way to build a fix that silently does nothing.

**(b) One resident heavy model.** `ENGEL_LOCAL_MODEL_CACHE_MAX_MODELS=1` on CT246 —
deepseek-r1, MoE-30B and the 14B are mutually exclusive loads. The Governor must select
**exactly one** heavy lane per turn; a fan-out or a "try both" would thrash the cache.

Also: never set `force_provider` as a routing signal — it jumps Auto chat onto an external
bridge (warned at `:2240-2244`), violating local-only.

### 2.2 `admit` — training-sample admission

Already built this session (discipline eligibility): local-only provenance + domain check
(math: `Result`/`Work`/`Check` + independent method + concrete relation + **CAS
refutation** + not a contract echo; engineering: `Proof:` + a cited `.py` that **exists on
disk**). The Governor **absorbs these as `admit` rules** so admission is one auditable
call rather than logic embedded in the runner. Behaviour is unchanged; provenance moves.

### 2.3 `persist` — memory admission and context visibility

See §4. Two independent booleans, which the current code conflates:
`persist` (does it enter the store) and `context_eligible` (may it be loaded into a later
turn's prompt).

### 2.4 `allow` — action gating

The existing governing-verb intent gates (`_prompt_requests_training_job`,
`_prompt_starts_local_training`) and the sandbox denylist keep their implementations and
register as `allow` rules. Unified reporting, unchanged semantics. **Explicitly out of
scope for T1/T2:** a learned model must never be the thing that authorises a real action.
Action gating stays deterministic, forever.

### 2.5 `escalate` — stronger model or human

Escalate when T0 is `uncertain` **and** stakes are high (irreversible action, a claim about
Engel's own state, math the CAS refused). Bounded: one escalation per turn, hard timeout,
deterministic fallback, and the escalation itself is receipted.

---

## 3. Signal plumbing — the enabler

Routing and memory hygiene both need to know "this is a training turn of discipline X."
Today that signal dies in transit.

**Chain, with all three breaks marked** (verified — it is not one drop, it is three):

```
trainer  _deliver_prompt()        :852   writes {schema, request_id, prompt, created_at_utc}
                                         ← ★ DROP 1: discipline is known and discarded
         ↓ runtime/ui_chat_inbox/requests/<id>.json
Flutter  _drainUiChatInbox()      :14908 reads decoded['prompt'] ONLY
         ↓ _submitChatDraft :15713 → _runLocalChatReply :15952 → LocalModelService.runChat :383
                                         ← ★ DROP 2: no metadata field in the wire payload
worker   engel_main_local_model_worker.py :1767  rebuilds its OWN hardcoded metadata dict
           _main_server_fast_chat  :1203  and  _stream_server_chat :1475
                                         ← ★ DROP 3: both POST lanes drop it
         ↓
service  request  :13594/:13798   _request_local_only_training :893 ALREADY dual-reads
                                  top-level + metadata → no receive-plumbing needed
```

**Change (four edits, all additive):**
1. `_deliver_prompt(prompt, metadata=None)` → emit `metadata`
   `{discipline, route_hint, training_turn, local_only_training, do_not_persist}`.
   Keep the atomic `.tmp` → `replace`.
2. Flutter `_drainUiChatInbox` → read `decoded['metadata']` **before the file delete**,
   thread an optional `metadata` param through `_submitChatDraft` → `_runLocalChatReply`
   → `runChat`, and add `if (metadata != null && metadata.isNotEmpty) 'metadata': metadata`
   to the payload. Send-button path (no metadata) stays byte-identical.
3. Worker → read `payload.get('metadata')` and **merge into both POST lanes** — fast *and*
   stream. **Normal chat is streamed**, so patching only the fast lane misses live chat.
   Merge must not overwrite `worker_source` / `worker_contract` / `conversation_id`
   (the `rog_ui_to_ct246_chat_v1` contract checks depend on them).
4. Service → **no new receive code**; consume the carried keys at the existing points.

**Per-turn vs the global sentinel:** today `local_only_training` comes from a wall-clock
sentinel (`_enforce_local_only_training :162-172`). Per-turn metadata **ORs** with it —
either source marks the turn training. Never AND: that would silently un-mark turns.

**Trusted fields (whitelist, clamped):** `training_discipline` ∈ {math, engineering, aec},
`training_run_id` (opaque str, ≤ 128 chars), `interactive` (bool), `routing_hint` (lane id
from the known set), `persist_policy` ∈ {normal, training}, `base_prompt` (str, ≤ 8 000
chars — **persist-only**: consumed solely by the §4.2 substitution; never read by routing,
admission, or action gating. Without this field the persister cannot substitute the base
ask, so §4.2 would be unimplementable — the trainer already carries `base_prompt` on every
schedule entry, it just has to travel with the turn).

**Trust boundary — stated explicitly.** Inbox metadata is local and same-host, but it is
still *input*. It may only ever **narrow** capability. Hard rules, asserted by the
verifier:
- Metadata can never enable an external provider, disable a safety/quality gate, mark a
  turn admissible, or grant an action.
- Unknown keys are dropped; out-of-range values fall back to the default.
- `routing_hint` selects only among lanes the caller could already reach; it is a *hint*,
  outranked by the reserved-lane guard.
- **Consumed exactly once.** Flutter attaches the metadata to the single chat request the
  drained prompt produces and clears it in a `finally` (and whenever the operator edits
  the composer). `_drainUiChatInbox` funnels into the same `_submitChatDraft()` the human
  uses — without an explicit clear, a stale training context could ride on a human turn.

Rationale: this is the one new path into the decision plane. Constrain it now.

---

## 4. Memory hygiene

### 4.1 ISOLATE, do not SKIP — and why

The naive fix — "don't persist training turns" — is **wrong twice over**:

1. Receipts *are* the training corpus (4,120 receipts → 4 datasets). Deleting them
   destroys the asset.
2. **It would break the training gates.** The runner's DONE gate
   (`run_engel_flutter_main_ui_prompt_training.py:2107/2181`) and the SSH cross-check
   `_check_ct_persistent_chat_memory (:1089)` both *require*
   `persistent_chat_memory_appended == True`. A hard skip turns every training turn red.

The real problem is not persistence, it is **context re-injection**. Split the concepts:

| Field | Meaning | Training turn |
| --- | --- | --- |
| `persist` | record enters the store (corpus, audit, gates) | **yes** — keep it |
| `context_eligible` | record may be loaded into a later turn's prompt | **no** — this is the echo |

Implemented as two cooperating mechanisms so neither is a single point of failure:

- **Read-side marker filter** — `_recent_chat_records_uncached (:~1505)` skips
  `local_only_training is True`. One line; immediately effective; real turns lack the flag
  so grounding is untouched. Mirror in `_big_lane_memory`, and add the existing
  `_semantic_text_matches_rejected_sample (:1432)` quarantine to `_recent_chat_context
  (:1362)` so the recent-context path filters echo bait the way the semantic path already
  does.
- **Scope isolation** — `_chat_context_scope (:1332)` returns
  `engel_training:{conversation_id}` for training turns, so unscoped loaders
  (`context_scope == ''`) cannot pull them. The scope filter *alone* is insufficient (it
  only bites when scope is non-empty, `:1506`), which is why the marker filter leads.

**Both physical stores must be patched.** The ROG-side record dict
(`run_engel_standalone_chat_llm.py:4695-4745`) carries **neither** `local_only_training`
nor `chat_context_scope` today, so a read filter is *inert* there until the fields are
added; then `persistent_chat_record_usable (:773)` gains the same skip. CT owns
persistence — do **not** re-enable the standalone append at the CT call sites
(`persist_chat_history=False` at `:12518/:12652`).

**`do_not_persist` must kill eligibility too.** Suppressing only the append leaves
`training_sample_eligible` set elsewhere (`:12716-12723`), and the daily dataset builder
re-ingests the echo bait. Control lanes (`_training_request_turn :12051`, mission-control,
self-upgrade-review) pass the existing `persist_memory=False` kwarg (`:9850`).

### 4.2 Strip the scaffolding before persisting

Root-cause the echo rather than filtering it downstream. Persist the **base ask**
(`base_prompt` — already carried on every schedule entry) plus the answer, **not** the
level-wrapper + answer contract. The contract text then never enters memory, so no future
turn can parrot it — including turns that legitimately load context.

### 4.3 Echo guard at ingest

Reuse `_CONTRACT_ECHO_MARKERS` plus a similarity check against the injected contract. On a
hit: tag `echo: true`, force `context_eligible: false`, refuse admission. Prevents the
feedback loop from ever closing, even if a contract is reworded later.

**Single source:** the markers currently live only in the trainer
(`run_engel_flutter_main_ui_prompt_training.py:605`), and the ingest guard runs service-side
— two copies would drift. The markers move to `tools/engel_governor.py` as the one
definition; the trainer imports them from there.

### 4.4 Retention and compaction

- Cap context-window records; prefer operator turns over machine turns.
- Near-duplicate collapse (the 7B's repeated identity paragraph is a known space hog).
- Respect the existing facts-first budget (4 000 chars, `_facts_clipped`) — facts and
  identity must never be evicted by chat history. Regression risk noted in memory.

### 4.5 Verifier

`verify_engel_memory_hygiene.py` asserts: a training turn is persisted; it is **not** in
the next turn's assembled context; contract text never appears in a persisted record;
echo replies are tagged and refused; a normal operator turn is still context-eligible
(no grounding regression).

---

## 5. Governor SLM — the honest bootstrap

The corpus needed to train a router is now being collected, and inventing labels would produce the
`failure_triage` failure again (F1 = 1.00 from 18 distinct inputs — a lookup table wearing
a model's coat, correctly rejected).

| Phase | Action | Exit gate |
|---|---|---|
| **A. Instrument** | T0 rules emit `governor_decision` receipts: features + verdict + **outcome** (status DONE?, admitted?, style pass?, latency, lane) | Receipts accumulating; routing verifier green |
| **B. Corpus** | Build a routing dataset from A (≈2 k+ decisions, matching the 4 120-receipt precedent) | Class balance documented; per-class counts published |
| **C. Train** | `tools/engel_slm_trainer.py`, same pipeline as `intent_router` | **Both mandatory gates**: beats majority baseline by the gated lift **and** leakage report clean |
| **D. Shadow** | T1 predicts, T0 decides; log every disagreement | Agreement + lift stable over a real window |
| **E. Promote** | T1 in-path for `route`/`escalate` only, T0 fallback always | Rollback = one env flag |

`allow` never leaves T0. `admit` may use T1 only to *tighten*, never to loosen.

Honest statement as of 2026-08-02: **A is shipped.** Normal chat receipts retain the
bounded T0 route features and authoritative verdict, `build_route_governor` turns only
real `decision=route` outcomes into the canonical dataset, and the runtime records an
SLM prediction in shadow telemetry when an eligible artifact exists. **B–E remain gated
on real, balanced data and reviewed promotion.**
Shipping a "Governor SLM" before C would be the exact self-deception the capability
curriculum warns about — a number that cannot go down is not evidence.

---

## 6. Build order (independently verifiable)

Ordered smallest-change-first so each step *earns* the next. Steps 1–3 fix both reported
problems **without the SLM**; the Governor then supersedes them as the single owner.

1. **Echo filter (CT read side)** — the marker skip in `_recent_chat_records_uncached`
   (`:~1505`) + the rejected-sample quarantine in `_recent_chat_context` (`:1362`).
   → `verify_engel_training_turn_context_exclusion.py` (seeded records; asserts exclusion
   **and** that a normal turn still loads, so grounding is not starved).
   *Smallest change, highest immediate value — kills echo for every turn already stamped
   by the global sentinel.*
2. **Persist isolation + ROG parity** — `engel_training:*` scope branch (`:1332`); ensure
   `local_only_training`/`do_not_persist` reach the persisted record (`:13005`, `:9659`);
   `persist_memory=False` for control lanes; add both discriminator fields to the ROG
   record dict (`run_engel_standalone_chat_llm.py:4695-4745`) and the skip in
   `persistent_chat_record_usable (:773)`. → extend the verifier to both stores; confirm
   the training DONE gate and SSH cross-check stay green (isolate, not skip).
   **Deploy caveat:** this file has historically-diverged ROG/CT246 copies; identify the
   host that actually executes the persister and hash-sync that copy deliberately.
3. **Deterministic routing fix (no Governor yet)** — `detect_engineering_reasoning_request`
   + a teaching-math branch keyed on `_MATH_NOUN_RE` + a teach/derive/prove verb **instead
   of a digit**, preserving `_FIGURATIVE_RE`/`_SOFTWARE_NOUNS`; wire into `:12083-12105`
   dispatching the specialist receipt **directly** (trap §2.1.1a); discipline-conditioned
   MoE threshold (`>=2` when discipline is known, `>=3` otherwise). Flag
   `ENGEL_ENG_REASON_LANE_ENABLED`. → verifier: a teaching/eng prompt reaches a reasoning
   receipt not the 7B; figurative false-positives still blocked; fail-open.
   *This wins the routing goal without waiting on the SLM.*
4. **Per-turn signal plumbing** — the metadata map through all three drop points (§3).
   → verifier: metadata round-trips into `request`; absent metadata ⇒ Send-button and
   existing training paths byte-identical.
5. **`tools/engel_governor.py`** — T0 rules, verdict contract, fail-safe table, receipts.
   Pure, no side effects. Consulted pre-cascade at the top of `_run_chat_turn_inner`
   (~`:11962`, **after** deterministic-arithmetic `:11995` and safety/blocked `:12009` so
   verified/safety behaviour is never bypassed), writing only the route keys the existing
   gates already read, non-destructively. `ENGEL_GOVERNOR_ENABLED`, off ⇒ byte-identical.
   → `verify_engel_governor.py`.
6. **Governor SLM (Phase A→C)** — `build_route_governor` in the dataset builder; train on
   CPU; **both mandatory gates** before it ships.
7. **Live proof** — Math School run: capable lane selected, samples admitted, no echo;
   captured-sample yield measured before/after.
8. **GREEN loop** — rebuild → restart → re-pin hashes/PID → `engel_health_check.py --full`.

Each step is shippable alone and reverts by one flag.

**Sweep registration:** `scripts/codex_verify.ps1` runs an explicit verifier list — new
verifier files do **not** auto-run. Both `verify_engel_governor.py` and
`verify_engel_memory_hygiene.py` must be added to a group or the gate is theatre.

**Flutter rebuild:** step 2's Dart change (metadata forward in `_drainUiChatInbox` /
`_submitChatDraft`) requires `flutter build windows` and an app restart before steps 5–7
can observe it; until then the running build silently drops metadata, which looks exactly
like the plumbing bug this fixes.

---

## 7. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Heavy lanes slow interactive chat | `interactive` is a first-class routing feature; heavy lanes are non-interactive by default; latency asserted by verifier |
| Governor becomes a choke point | In-process, pure, `route` fails **open** to today's default |
| T1 leakage repeats `failure_triage` | Both mandatory gates before promotion; shadow mode; `allow` never learned |
| Inbox metadata as an escalation path | Whitelist + clamp + narrow-only invariant, verifier-asserted |
| Context filter breaks grounding | Facts-first budget preserved; verifier asserts operator turns stay eligible |
| Second GPU model | Not planned — 2070/8 GB cannot co-fit; T1 is a tiny head, T2 reuses CT lanes |
| Hidden console windows | All subprocesses keep `CREATE_NO_WINDOW` (known regression class) |
| Silent lane unavailability | `lane_health` feature; unreachable lane ⇒ documented fallback, receipted |

---

## 8. Operator decisions

1. **T1 scope on promotion** — `route` + `escalate` only (recommended), or also tighten
   `admit`?
2. **Interactive escalation appetite** — may an *interactive* math turn spend ~40 s on the
   30B when the CAS declines, or always stay fast and answer "unverified"? (Recommend:
   stay fast, offer the deep answer.)
3. **T2 model of record** — sparse-MoE 30B (faster, strong) vs deepseek-r1 (stronger at
   word problems, 3.69 tok/s). Recommend 30B, r1 for declined-CAS word problems only.

Defaults above are safe; none blocks steps 1–6.
