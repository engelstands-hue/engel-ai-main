# Engel Conductor — the loop that closes (v1)

Design spec — 2026-07-31. Senior AI design-engineering pass.
Status: SHIPPED v1 (`engel_conductor.py`, routes `engel.conductor.*`,
verifier `tools/verify_engel_conductor.py`).

---

## 0. The gap this fills

Engel has every organ of an agent and no circulatory system. Measured against the
live tree on 2026-07-31:

- **Plan** exists — `engel_script.draft_prompt` retrieves real routes and a 7B emits
  a valid plan (proven live) — but the draft flow ends by printing *"Drafts never run
  automatically."* and waiting for a human to type the run phrase as a second turn.
- **Act** exists — `execute_engel_script` — but v1 blocks every non-read-only route
  unconditionally; `allow_actions` is recorded and ignored, waiting (per its own
  docstring) for "the Governor's allow class to gate a real grant later."
- **Decide** exists — `engel_governor.govern` — but `govern("allow", ...)` had zero
  production callers; the decision plane was dark for the one decision class built
  fail-closed for exactly this.
- **Observe** exists — every step outcome lands in the run receipt — but nothing in
  the codebase reads a receipt and produces a next step. A blocked step assigns
  `[blocked: …]` to a variable and the run marches on.
- **Remember** does not exist — the only cross-turn state in the chat path is one
  module-level `_PENDING_ACTION` that is dropped the moment the operator says
  anything but yes or no. "Work on X until it's done" has nowhere to live.

`docs/ENGEL_SCRIPT_LANGUAGE.md` §5 names the missing piece explicitly: *"something
outside the language decides to run a script."* The Conductor is that something.

## 1. What the Conductor is

A **bounded, deterministic goal loop**: goal → retrieve → plan → validate → run →
observe → repair → ledger. One module, `engel_conductor.py`, same contract culture
as the Governor and EngelScript:

- **The module itself never calls a model.** The draft/repair LLM call is injected
  (`draft_fn`) by the caller that owns the model lane (the chat worker, which already
  drafts with `chat_only=True` and the long-generation escape hatch). With no
  `draft_fn` the Conductor still works from saved plans — degraded, never broken.
- **Bounded by construction.** At most `MAX_ROUNDS` (2) plan-run rounds per conduct
  call: the initial round plus one repair. Repair is granted through
  `govern("escalate", …)` — one escalation, already-spent thereafter. All script
  caps (64 statements / 16 KiB / 120 s) are inherited unchanged.
- **Receipted.** Every conduct writes `reports/engel_conductor/CONDUCT_*.json` with
  the goal, every round's plan sha256, run receipt path, observation, Governor
  verdicts, and the outcome. Receipts are the training corpus; a conduct that ran
  is a document.
- **Persistent.** Every conduct upserts `memory/engel_goals/<slug>.json` — goal
  text, status (`open` / `done` / `needs_attention` / `failed`), rounds spent,
  receipt paths. `continue engel goal <slug>` re-enters a goal in a later turn with
  its history folded into the repair prompt. Goals survive the process.

## 2. The loop, precisely

```
conduct(goal, draft_fn=None, allow_actions=False)
  1. RETRIEVE  capability index: top routes + the safe phrasebook for the goal
  2. PLAN      goal names a saved plan?  load it
               else draft_fn?            draft_prompt(goal) → draft_fn → extract
               else                      honest no-planner receipt + suggestions
  3. VALIDATE  parse_engel_script; invalid + rounds left → repair round
               (validator errors folded into the repair prompt verbatim)
  4. DECIDE    govern("allow", {gate, gate_result}) — deterministic gate:
               read-only run: plan validated ∧ allow_actions=False
               granted run:  operator grants file ∧ confirmed ∧ every action
                             step's route id individually granted
               deny → the run does not happen; receipt says why
  5. RUN       execute_engel_script(source, allow_actions=…)
  6. OBSERVE   read the run receipt: blocked steps, failed routes, cap aborts
  7. REPAIR    problems ∧ rounds left ∧ draft_fn ∧ govern("escalate") grants →
               fold observation + alternative phrases into repair_prompt → step 3
  8. LEDGER    upsert the goal file; write the conduct receipt; render the story
```

Determinism note: with the same goal, saved plans, registry, and injected
functions, the loop structure is a pure function of its inputs. Only route outputs
vary — same rule EngelScript already lives by.

## 3. Action grants — the Governor's allow class, finally lit

v1 of EngelScript shipped strictly read-only with the grant flow specified from
both ends and never joined. The Conductor joins it, **default-off, triple-gated**:

1. **Operator grants file** — `memory/engel_conductor_action_grants.json`,
   operator-authored, absent by default. Absent/empty/malformed ⇒ zero grants;
   behaviour is byte-identical to before this feature existed.
2. **Governor allow verdict** — every granted step calls
   `govern("allow", {"gate": "engel_script_action_grant", "gate_result": …})`,
   fail-closed: a Governor import failure denies the grant. The verdict is embedded
   in the step receipt — the first production caller of the allow class.
3. **The belts stay on.** Slow-lane suffixes, the script-engine self-reference
   ban, non-registry phrases, and the prompt-injection guard are all still refused
   for granted steps. A grant widens exactly one check: the read-only flag test,
   for route ids the operator listed by hand.

Every phrase-reachable surface still passes `allow_actions=False`. The only path
to a granted run is a Python caller that sets the flag — and the chat worker only
does so after the operator has seen the validated plan and confirmed.

## 4. Runtime surfaces

| Route | Phrase examples | What it does |
|---|---|---|
| `engel.conductor.docs` | "engel conductor docs", "what is the engel conductor" | This reference, rendered. |
| `engel.conductor.goal` | "engel goal <text>", "conduct engel goal <text>" | Run the loop for a goal (route surface: saved plans only, read-only; the drafting loop lives in the chat worker where the model lane is). |
| `engel.conductor.status` | "engel goal status", "list engel goals" | The goal ledger, rendered: open/done/failed, rounds, receipts. |

Chat surface (ROG worker, before the fleet/build detectors): `engel goal <text>`
runs the full loop with `draft_fn` wired to the local model lane (`chat_only=True`,
long-generation budget — the draft instruction text must never trip the build
detector, same lesson as the script draft flow). `continue engel goal <slug>`
re-enters. Receipts and the ledger are shared across both surfaces.

## 5. Explicit non-goals (v1)

- **No autonomous scheduling.** The Conductor closes the loop *within* an invocation
  and persists state *between* invocations; it never wakes itself. Something outside
  it (an operator, a cron the operator installs) decides to conduct.
- **No parallel fan-out.** Steps run serially under the existing in-flight limit of
  one local model; the conical build lane and `engel_subagents.fan_out` remain the
  parallel vehicles. Wiring them into conducted plans is a v2 candidate, after the
  loop itself has receipts behind it. *(Shipped 2026-07-31 as the Engel Orchestra —
  `engel_orchestra.py`, docs/ENGEL_ORCHESTRA_DESIGN.md: bounded parallel read-only
  Conductor lanes with one merged receipt; actions remain serial-Conductor-only.)*
- **No learned gating.** Action gating stays deterministic forever (Governor design
  §2.4). The grants file is written by a human, the gate is a set-membership test,
  and T1/T2 never touch `allow`.
- **No new language surface.** The Conductor emits and consumes EngelScript v1
  unchanged; a goal that needs loops in the *plan* still means Python reviewed by a
  human.
