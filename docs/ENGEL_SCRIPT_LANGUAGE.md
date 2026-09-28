# EngelScript — Engel AI Main's own code language (v1)

Design spec — 2026-07-31. Senior AI code-language design pass.
Status: SHIPPED v1 (`engel_script.py`, routes `engel.script.*`,
verifier `tools/verify_engel_script.py`).

---

## 0. Why a language, and why this one

Engel has a 490-route library, six model lanes, a served SLM roster, and a Governor —
and **no way to compose them**. A phrase invokes exactly one route; anything multi-step
means writing Python. The missing agentic piece is the composition layer: a way to say
"check this, then that, and if the first said OFFLINE, run the doctor" as a first-class,
auditable artifact.

EngelScript is deliberately NOT a general-purpose language. It is a **plan notation**:

- **Small enough for Engel's own models to emit and for a human to read at a glance.**
  Eight statement forms, one expression form, no nesting, no loops. A 7B that can write
  a sentence can write a valid script; the validator catches the ones it gets wrong.
- **Deterministic and bounded.** No loops, no recursion, ≤ 64 statements, ≤ 16 KiB
  source, ≤ 120 s wall clock. A script's step *structure* is a pure function of its
  source; only route outputs vary.
- **Safe by construction, not by review.** Every `route` step resolves through the real
  router (prompt-injection guard included) and is safety-checked against the route
  registry's own flags BEFORE it runs. Non-read-only routes are blocked and receipted —
  running a script can never do more than the phrases it contains were already allowed
  to do, and by default strictly less.
- **Receipted like everything else in Engel.** Every run writes a JSON receipt with the
  script's sha256, every step's route id / outcome / latency, and the final variables.
  A plan that ran is a document you can audit months later.

## 1. Language reference

Line-oriented. `#` starts a comment. Blank lines ignored. One statement per line.

| Statement | Meaning |
|---|---|
| `plan "<title>"` | Optional header, once, first statement. Names the run in receipts. |
| `let $name = <expr>` | Bind a string variable. |
| `ask $name = route <expr>` | Run the phrase through Engel's router, capture the reply text. |
| `route <expr>` | Run a phrase, discard the capture (still receipted). |
| `ask $name = intent <expr>` | Ask the served SLM roster for the route intent label (advisory; `unavailable` when the runtime is not ready — ROG-side, for example). |
| `if $name contains "<literal>" then <statement>` | Guard exactly one statement (no nesting: the guarded statement may not be another `if`). |
| `if $name misses "<literal>" then <statement>` | Negated guard. |
| `say <expr>` | Append a line to the run's visible output. |

**Expressions** are string literals and variables joined with `+`:

```
let $worker = "android_worker_alpha"
ask $jobs = route "android workers status"
if $jobs contains "OFFLINE" then route "connection doctor"
say "fleet: " + $jobs
```

Variables hold strings only (max 32 per run, values clipped at 16 KiB). Reading an
unset variable is a validation error, not an empty string — a typo must fail loudly.

## 2. Safety model (the part that makes it shippable)

1. **Registry flags decide, per step, before execution.** A `route` step's phrase is
   classified first; it executes only when it resolves to an `UPDATE_ROUTES` entry whose
   own metadata says `read_only`, `safe_for_ai_route`, and `no_provider_model_network`.
   Everything else — action routes, legacy known-commands, companion chat, unsafe
   phrasing, unknown phrases — is **blocked**: the step is receipted with the reason,
   the variable (if any) gets `[blocked: …]`, and the script continues.
2. **Slow-lane denylist as a belt:** route ids ending in `.build`, `.install`,
   `.dev_start`, `.tauri_build`, `.bring_up`, etc. are refused in script mode even if
   their flags read safe — a script step must return in seconds, not spawn cargo.
3. **The prompt-injection guard is inherited per step**, because classification runs
   inside the real router. A script cannot smuggle a phrase past the guard that chat
   would have caught.
4. **`allow_actions` exists only as an explicit Python-caller flag** for a future
   approval flow, is `False` from every phrase-reachable surface, and when it is ever
   set, the Governor's `allow` decision class records the grant. v1 ships with the
   route surface strictly read-only.
5. **Caps are hard.** Statement, size, variable, and wall-clock limits abort with an
   honest partial receipt.

## 3. Runtime surfaces

| Route | Phrase examples | What it does |
|---|---|---|
| `engel.script.docs` | "engel script docs", "engel script language" | This reference, rendered. |
| `engel.script.examples` | "engel script examples" | The bundled example plans + where receipts land. |
| `engel.script.validate` | "validate engel script `<plan_name or source>`" | Parse + safety-resolve every step; report errors and which steps would be blocked. Runs nothing. |
| `engel.script.run` | "run engel script `<plan_name>`" | Execute in read-only mode; returns the `say` output + step summary; writes the receipt. |

The router's normalization layer strips newlines, quotes, dots, and semicolons, so the
phrase surface runs plans **by name**: `run engel script morning_health_sweep` loads
`memory/engel_scripts/morning_health_sweep.engel` (names are `[a-z0-9_-]+` only —
containment by construction). Inline source works from Python
(`execute_engel_script`) with `;` as a statement separator. Example plans live in
`memory/engel_scripts/*.engel`; receipts land in `reports/engel_script/`.

## 4. How the models use it

The intended loop, matching the SLM roster's advisory ladder: a model **drafts** a
script from a goal, the **validator** proves it parses and shows exactly which steps
would execute vs be blocked, and only then does anything run — with a receipt. The
language is the contract between "what the model wants to do" and "what Engel actually
does"; the validator is the referee. Because scripts are text, they are also training
data: admitted plans + their receipts are a future corpus for a plan-drafting lane.

Shipped 2026-08-01: the Agent Kernel (`docs/ENGEL_AGENT_KERNEL_DESIGN.md`)
is now the single operator-facing dispatcher above this flow. Exact safe
phrases take an immediate EngelScript fast path; larger goals reach this
language through the Conductor. The kernel route family is self-reference
blocked like Script/Conductor/Orchestra/Forge.

## 5. Explicit non-goals (v1)

- No loops, no functions, no arithmetic, no nesting — a plan that needs them should be
  Python reviewed by a human, not a longer script.
- No file or network primitives: the ONLY effect a script can have is invoking routes
  that already exist, under their own flags.
- No autonomous scheduling: something outside the language decides to run a script.
