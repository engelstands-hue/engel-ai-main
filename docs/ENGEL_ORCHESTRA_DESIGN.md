# Engel Orchestra — the Conductor's parallel section (v1)

Design spec — 2026-07-31. Senior AI design-engineering pass.
Status: SHIPPED v1 (`engel_orchestra.py`, routes `engel.orchestra.*`,
verifier `tools/verify_engel_orchestra.py`).

---

## 0. The gap this fills

The Conductor (docs/ENGEL_CONDUCTOR_DESIGN.md) closed Engel's agent loop — goal →
plan → run → observe → repair → ledger — and its own §5 named what it left out:

> **No parallel fan-out.** Steps run serially under the existing in-flight limit of
> one local model; the conical build lane and `engel_subagents.fan_out` remain the
> parallel vehicles. Wiring them into conducted plans is a v2 candidate, after the
> loop itself has receipts behind it.

Measured against the live tree on 2026-07-31, the loop has receipts behind it
(`reports/engel_conductor/`), and the parallel vehicles are still islands:

- `engel_subagents.fan_out` / `spawn_subagent` have **zero production callers**
  outside `engel_agent_harness` (itself unwired) and the doctor's self-check. The
  fan-out pattern exists but only ever reached *provider text lanes* — never
  Engel's own 490-route library.
- A multi-part operator goal ("check the fleet AND the bridges AND storage") either
  becomes one long serial plan under one 120 s script cap, or three separate chat
  turns the operator sequences by hand. Engel's parts are used one at a time.

The Orchestra is the join: **the fan-out pattern, aimed at the Conductor.** A
multi-part goal splits into bounded parallel lanes, each lane a full conduct
(retrieve → plan → validate → run read-only → observe → repair once), and the lane
observations merge into one receipted, ledgered outcome. This is what lets Engel
use all of its parts *fluidly* (one goal in, one combined answer out) and *fast*
(independent read-only lanes overlap their route I/O instead of queueing).

## 1. What the Orchestra is

One module, `engel_orchestra.py`, same contract culture as Governor / EngelScript /
Conductor:

- **The module itself never calls a model.** The decomposition and synthesis
  prompts are deterministic string builders; the LLM call is injected (`draft_fn`)
  by the caller that owns the model lane (the chat worker). With no `draft_fn` the
  Orchestra still orchestrates explicit `|`-separated parts and saved plans —
  degraded, never broken.
- **Bounded by construction.** At most `MAX_LANES` (4) lanes per orchestration.
  Each lane is one `engel_conductor.conduct` call and inherits every Conductor
  bound unchanged (MAX_ROUNDS=2, script caps 64 statements / 16 KiB / 120 s, one
  Governor-gated repair). Decomposition is one injected call; synthesis is one.
- **One model in flight.** Every lane's `draft_fn` is wrapped in a single shared
  lock before fan-out: route I/O runs in parallel, model calls serialize. This is
  the constraint that made fan-out a v1 non-goal, honored rather than removed.
- **Read-only by construction.** `orchestrate()` has **no `allow_actions`
  parameter**. Two lanes mutating state concurrently is an explicit non-goal;
  granted-action runs stay with the serial Conductor where the operator grants
  file + Governor allow class already gate them.
- **Receipted + persistent.** Every orchestration writes
  `reports/engel_orchestra/ORCHESTRA_*.json` linking each lane's conduct receipt,
  and upserts a parent record in `memory/engel_goals/` (kind `orchestra`) next to
  the per-lane goal records the Conductor already writes. A failed lane's slug is
  printed so `continue engel goal <slug>` re-enters exactly the part that failed.

## 2. The loop, precisely

```
orchestrate(goal, draft_fn=None, router=None, intent_fn=None, synthesize=True)
  1. SPLIT      "a | b | c" → operator's own decomposition (2..MAX_LANES parts;
                more is an honest refusal, never a silent clip)
                else draft_fn → ONE decomposition call (capability phrasebook
                folded in so the split follows Engel's real parts); <2 usable
                lines → single lane
                else → single lane (delegates to the Conductor unchanged)
  2. GATE       govern("allow", {gate: "orchestra_fan_out", gate_result, lanes,
                read_only: True}) — verdict recorded in the receipt; read-only
                orchestration proceeds when the Governor is unavailable (same
                route-class asymmetry as the Conductor)
  3. FAN OUT    ThreadPoolExecutor(≤4): each lane = conduct(subgoal,
                draft_fn=locked, allow_actions=False) — full retrieve/plan/
                validate/run/observe/repair per lane, own conduct receipt
  4. MERGE      per-lane: status, ok, rounds, executed/blocked routes, problems
                parent ok = every lane ok; status "done" or "k/n lanes done --
                needs attention"; problems prefixed "lane i (slug):"
  5. SYNTHESIZE optional, one injected call: lane outputs → one combined answer
                (recorded in the receipt; failure degrades to the merge story)
  6. LEDGER     write ORCHESTRA_*.json; upsert the parent goal record; the story
                names each failed lane's continue-slug
```

## 3. Safety belts

- `engel_script.route_step_safety` and `_action_grant_for` refuse
  `engel.orchestra.*` exactly as they refuse `engel.script` / `engel.conductor` /
  `engel.forge`: a plan invoking the orchestrator is unbounded recursion wearing a
  phrase's coat, and the orchestrator is never grantable.
- Lanes conduct with `allow_actions=False` — hardcoded, not defaulted.
- The route surface (`engel.orchestra.run`) orchestrates without a drafter
  (explicit splits and saved plans only); the drafting orchestration lives in the
  chat worker where the model lane is, `chat_only=True` with the long budget
  (build-detector lesson inherited from the script/conductor draft flows).

## 4. Runtime surfaces

| Route | Phrase examples | What it does |
|---|---|---|
| `engel.orchestra.docs` | "engel orchestra docs", "what is the engel orchestra" | This reference, rendered. |
| `engel.orchestra.run` | "engel orchestra <a> \| <b> \| <c>", "engel orchestrate <goal>" | Fan out and merge (route surface: explicit splits + saved plans, read-only). |
| `engel.orchestra.status` | "engel orchestra status", "engel orchestra runs" | Recent orchestrations: goal, lanes, outcome, receipts. |

Chat surface (ROG worker, before the fleet/build detectors, after the Conductor
intercept): `engel orchestra <goal>` runs the full loop with `draft_fn` wired to
the local model lane — decomposition, per-lane drafting/repair, and synthesis.
Status/docs answer locally without a model. The status branch is checked BEFORE
the run branch and tolerates trailing filler (the Conductor's phantom-goal lesson,
2026-08-01).

`engel_agent_harness` registers `orchestrate_goal` as a tool, so the harness's
plugin/hook runtime reaches the same loop — the harness island's first
Engel-native production wiring.

## 5. Explicit non-goals (v1)

- **No parallel actions.** Granted-action runs are serial-Conductor-only. If two
  lanes ever need to mutate state, that is a design change with its own receipt
  culture, not a flag.
- **No nested orchestration.** A lane is a conduct, never another orchestration;
  the script-engine prefix ban makes the recursive phrase unreachable too.
- **No autonomous scheduling.** Same as the Conductor: something outside decides
  to orchestrate.
- **No learned lane routing.** Which lane runs where stays deterministic; the SLM
  roster stays advisory.

Shipped above v1 on 2026-08-01: the Agent Kernel
(`docs/ENGEL_AGENT_KERNEL_DESIGN.md`) adds heterogeneous top-level lanes. A
compound `engel work` goal can run direct route, Conductor, and sandboxed
Forge lanes together while preserving this module's original read-only
Conductor-only contract.
