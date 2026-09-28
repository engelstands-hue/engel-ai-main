# Engel Code Forge — real code, proven by running it (v1)

Design spec — 2026-07-31. Senior AI design-engineering pass.
Status: SHIPPED v1 (`engel_code_forge.py`, routes `engel.forge.*`,
verifier `tools/verify_engel_code_forge.py`).

---

## 0. The gap this fills

Engel's local models can *emit* code in several places, and none of those
places ever finds out whether the code works:

- `engel_local_multi_model_code` generates candidates into
  `reports/generated_code/` — the newest artifacts (2026-06-23) contain the
  PROMPT text and were never executed by anything.
- The chat build lane extracts files and scaffolds apps; a failed step stops
  the run ("Stops at the first failure") and the error text never reaches a
  model again.
- The Code Companion has a sandboxed run button — pressed by a human — and its
  patch lanes gate Engel's OWN code behind human approval, by design.
- The Conductor (2026-07-31) closes the loop for *plans*, but a plan step is a
  route invocation; there is no route whose output is "this code ran green."

So "Engel writes code" has meant "Engel writes text that looks like code."
The missing piece is the loop that makes it real: **generate → gate → run →
observe → repair**, with the run's own stderr as the teacher.

## 1. What the Forge is

One module, `engel_code_forge.py`, same contract culture as the Conductor:

- **No model calls in the module.** `generate_fn` is injected by the caller
  that owns a model lane (the chat worker). The module builds prompts,
  extracts files, gates, runs, observes, repairs, receipts.
- **Bounded.** At most `MAX_ROUNDS` (3) generate/run rounds. `max_rounds` is
  the **sole** bound: a `govern("escalate", …)` verdict is recorded on each
  repair for the audit trail, carrying the *true* `already_escalated` value,
  but it is **advisory only** and does not gate the loop. (An earlier draft
  claimed it gated repairs while passing `already_escalated=False` every time —
  a receipt feature that contradicted reality and broke `inputs_hash` replay.)
  Per-run sandbox timeout, file-count and file-size caps also apply.
- **Proven, not claimed.** A forge is `forged` only when every emitted
  `test_*.py` ran green in the sandbox. Three independent guards enforce that,
  each added after a live run defeated the previous one:
  1. **exit code** — the process must exit 0;
  2. **output scan** — a suite ending `unittest.main(exit=False)` swallows its
     exit code, so failure markers in the real output also fail the round;
  3. **static reachability** — a file that merely *defines* `def test_x():`
     and never calls it exits 0 having asserted nothing, so at least one
     assertion must be reachable when the file runs (loops and `__main__`
     guards included).
  No tests emitted is its own error class (`no_tests`), never a pass. Advisory
  extraction notes (a dropped README) are recorded as `warnings` and may
  **not** veto a run whose tests actually passed.
- **Receipted + a dataset flywheel.** Every forge writes
  `reports/engel_forge/FORGE_*.json`, and every round appends one line to
  `reports/engel_forge/forge_outcomes.jsonl` — goal, error class
  (`gate` / `compile` / `assert` / `runtime` / `timeout` / `none`), error
  tail, and whether the next round fixed it. This is exactly the labeled
  corpus the SLM roster's `failure_triage` lane was missing: real (goal,
  deterministic error class, diagnostic, next-round outcome) tuples, produced
  as a by-product of use. The roster builder now consumes `fixed_by_next` as
  `repair_succeeded` / `repair_failed`; the head remains data-collecting until
  class balance and model gates pass. `reply_grader` uses chat repair receipts
  and passed its separate gate on 2026-08-01.

## 2. The loop, precisely

```text
forge(goal, generate_fn)
  1. PROMPT    forge_prompt(goal): a CONCRETE two-file example, not a
               description — small local models copy a shape far more
               reliably than they follow prose
  2. EXTRACT   FILE: markers (fenced-block fallback); path safety: relative,
               shallow, [a-z0-9_.-], caps on count and bytes; a file name
               that shadows a stdlib name is refused
  3. COMPILE   compile() every file FIRST — a file that will not parse cannot
               be meaningfully gated, and "syntax error line 3" repairs better
               than a policy refusal. Nothing executes here.
  4. GATE      structural (AST) gate: every import alias against the
               allowlist, no bare escape-hatch builtins, no dunder access
               -> govern("allow", {gate: "forge_code_gate", gate_result})
               fail-closed: violation = nothing runs, and the violation text
               becomes a repair problem
  5. REACH     every test file must be able to EXECUTE an assertion
  6. RUN       each test_*.py via engel_sandbox tier "restricted"
               (secrets stripped, denylist, timeout, isolated workspace under
               runtime/forge_workspaces/SLUG/round_N/)
  7. OBSERVE   exit code + output failure markers per test -> problems
  8. REPAIR    problems and rounds left and generate_fn ->
               repair_forge_prompt folds the exact stderr back in -> step 2
  9. RECEIPT   forge receipt + one outcomes line per round + (on success)
               artifact paths; artifacts never leave the workspace by
               themselves — candidate outputs, never auto-deployed
```

## 3. Safety model (why this may run model code at all)

v1 forges the **pure-computation kernel** of Python: functions, classes,
algorithms, data transforms, tested with plain asserts. That kernel needs no
I/O, no network, no processes — so the gate can be an allowlist, and the
allowlist can be honest:

The gate is **structural, not textual** — it parses each file and judges AST
nodes. Text scanning was tried first and failed in both directions; the
2026-08-01 adversarial review proved two escapes end-to-end (each wrote a file
*outside* the workspace while the run still returned `forged`) and two
false refusals:

| Payload | Old text gate | Now |
|---|---|---|
| `import math, os` then `os.system(...)` | passed — the regex read only the first name | refused: every import alias is checked |
| `getattr(__builtins__, '__imp'+'ort__')('os')` | passed — no import, and the split string beat the token scan | refused: `getattr` and `__builtins__` are denied names |
| `().__class__.__bases__[0].__subclasses__()` | passed | refused: dunder attribute access |
| `re.compile(r'x')` with `re` allowlisted | **refused** — `compile(` matched as a substring | allowed: an attribute of an allowlisted module |
| `def retrieval(...)`, `def reopen(...)` | **refused** — `eval(`, `open(` matched | allowed |

1. **Import allowlist** (math, json, re, itertools, functools, collections,
   dataclasses, typing, datetime, heapq, bisect, statistics, string, enum,
   abc, copy, operator, decimal, fractions, random, textwrap, unittest),
   applied to every alias of every import statement. Anything else — `os`,
   `sys`, `subprocess`, `socket`, `pathlib`, `shutil` — is a violation,
   reported and repairable. Relative imports are refused.
2. **No stdlib shadowing.** A generated file may not be *named* after a
   stdlib module, and a local file never grants its own name as an import if
   the stdlib owns it. (Without this, emitting a trivial `os.py` put `os`
   into the local-module set and `import os` passed — while the child
   process resolved the *real* `os`, already in `sys.modules` at startup.)
3. **Denied names and dunders**: bare `eval`/`exec`/`compile`/`open`/`input`/
   `getattr`/`setattr`/`vars`/`globals`/`locals`/`__import__`/`__builtins__`,
   and any dunder name or attribute outside a small benign set (`__name__`,
   `__init__`, `__repr__`, the operator protocol). This closes the
   `__class__`→`__bases__`→`__subclasses__` family with one rule.
4. **The sandbox stays on underneath**: secrets-stripped env, isolated cwd,
   argv denylist, hard timeout — defense in depth, not the primary gate.
5. **The Governor allow class receipts every run decision** with the gate
   result, same fail-closed contract as EngelScript's action grants.
6. Over-blocking a benign import is the SAFE failure for model-generated
   code (same philosophy the sandbox denylist documents). Widening the
   allowlist is a deliberate future step, not a default.

**Honest limit.** This is a static gate over source plus a process sandbox; it
is not a syscall boundary. It is sound against the escape classes enumerated
above and against imports, but a determined novel bypass of a source-level
gate cannot be ruled out by construction. Running genuinely untrusted code
would need real containment (a restricted interpreter or a container), which
v1 deliberately does not claim to provide — which is also why the forged
kernel is pure computation with no I/O, and why artifacts are never
auto-deployed.

## 4. Runtime surfaces

| Route | Phrase examples | What it does |
|---|---|---|
| `engel.forge.docs` | "engel forge docs", "what is the engel forge" | This reference, rendered. |
| `engel.forge.code` | "forge code <goal>", "engel forge <goal>" | The loop (route surface has no model lane attached: renders usage + recent forges; the forging chat surface lives in the worker). |
| `engel.forge.status` | "engel forge status", "list forges" | Recent forge receipts: goal, rounds, outcome, artifacts. |

Chat surface (ROG worker, before the build detectors — forge wording like
"write/create code" must never trip `_requested_app_build`): `forge code
<goal>` runs the full loop with `generate_fn` wired to the local model lane
(`chat_only=True`, long generation budget). The reply shows each round's
outcome, the final artifact paths, and where the receipt landed.

## 5. Explicit non-goals (v1)

- **No auto-deploy, no auto-install.** Artifacts live in the forge workspace;
  moving one into a project is a human act (or a future granted action).
- **Python only, pure-computation only.** Other languages and I/O-needing
  code wait until there is a container boundary worth trusting.
- **No pytest dependency.** Tests are plain-assert scripts run with the venv
  interpreter; green means exit 0.
- **No learned gating.** The gate is an allowlist + token scan, deterministic
  forever; the SLM corpus the Forge feeds trains *advisory* triage, never the
  gate.
- **No recursive Forge step inside EngelScript.** Shipped 2026-08-01 through
  the Agent Kernel (`docs/ENGEL_AGENT_KERNEL_DESIGN.md`): a top-level mixed
  goal can select Forge and Conductor lanes and link both child receipts. The
  Forge remains unavailable as an EngelScript route step, which prevents an
  unbounded plan -> Forge -> plan recursion.
