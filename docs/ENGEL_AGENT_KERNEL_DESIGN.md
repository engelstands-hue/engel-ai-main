# Engel Agent Kernel - the missing dispatch spine (v1)

Design and implementation - 2026-08-01.
Status: SHIPPED v1 (`engel_agent_kernel.py`, routes `engel.agent_kernel.*`,
Main-chat surface `engel work <goal>`, verifier
`tools/verify_engel_agent_kernel.py`).

## 0. What was missing

Engel already had the parts of an agentic system, but they were separate
operator-selected islands:

- the Governor could decide and receipt policy;
- the capability index could find routes;
- EngelScript could safely compose routes;
- the Conductor could plan, run, observe, repair, and remember one goal;
- the Orchestra could overlap several read-only Conductor lanes;
- the Code Forge could generate, gate, test, observe, and repair Python.

The operator still had to know which mechanism to name. `engel goal`,
`engel orchestra`, and `forge code` were three different doors. The older
`engel_agent_harness` registered tools, but `run_agent()` only called the
failover model and never consumed the registry; the bundled agent invocation
ran in a separate provider-driven subprocess and did not use Engel Main's new
Governor/Script/Conductor/Orchestra/Forge stack.

The missing release piece was therefore not another model or tool. It was a
small, deterministic **dispatch spine** over the proven loops.

## 1. Contract

`run_goal(goal, draft_fn=None, generate_fn=None, ...)` chooses the smallest
engine that can prove the work:

1. **Direct fast path** - an exact phrase that passes
   `engel_script.route_step_safety` becomes a three-line EngelScript receipt.
   No model call is spent.
2. **Code Forge** - a pure-computation Python creation task goes through the
   Forge's generate/gate/run/observe/repair loop. App, service, deployment,
   GUI, cluster, and package work is excluded because the Forge v1 contract
   cannot honestly build those artifacts.
3. **Heterogeneous Orchestra** - a clear compound goal is split into at most
   four lanes. Each lane selects its own fast route, Conductor, or Forge.
   Route I/O and sandbox work overlap; all calls to the one resident heavy
   model share one lock.
4. **Conductor** - a remaining single operational goal uses the existing
   plan/run/observe/repair/ledger loop with actions disabled.

Selection is deterministic and recorded. A model may decompose and synthesize,
but a model never chooses the safety boundary or grants an action.

## 2. One receipt tree

Every run writes `reports/engel_agent_kernel/AGENT_*.json` with:

- prompt-injection preflight;
- selected engine and reason;
- Governor `allow.gate.agent_kernel_dispatch` verdict;
- each lane's engine, output, problems, artifact paths, and child receipt;
- final status, optional synthesis, and the engines actually used.

Child receipts remain authoritative. The kernel does not copy their internals
or invent a second definition of success.

## 3. Safety and failure behavior

- The real prompt-injection guard runs before any injected model callback.
- Direct work must be a registry route marked read-only, AI-safe, and
  provider-network-free.
- Conducted work always passes `allow_actions=False`.
- Code execution stays inside the Forge's AST gate and restricted sandbox;
  artifacts are candidates and are never installed or deployed.
- Forge dispatch is fail-closed if the Governor is unavailable. Read-only
  direct/Conductor work retains the Governor design's availability behavior.
- The kernel, Conductor, Orchestra, Script, and Forge route families are all
  refused from EngelScript, preventing recursive self-invocation.
- Four lanes maximum. No autonomous scheduling. No background mutation.
- The module never contacts a model or provider itself. Main chat injects the
  existing local CT model callback.

## 4. Runtime surfaces

| Route | Phrase | Behavior |
|---|---|---|
| `engel.agent_kernel.docs` | `engel agent kernel`, `engel work help` | Reference and boundaries. |
| `engel.agent_kernel.run` | `engel work <goal>`, `engel solve <goal>` | Automatic native dispatch. |
| `engel.agent_kernel.status` | `engel work status` | Recent kernel receipts. |

In Engel AI Main chat, the existing friendly phrases `engel agent do <goal>`,
`engel agent run <goal>`, and `agent task <goal>` also enter the native kernel.
The explicit lower-level surfaces remain available for operators who want to
force a particular mechanism.

## 5. Release invariants

The verifier proves all four engine choices, mixed direct+Forge lanes, model
serialization, prompt-guard refusal, Governor receipts, route registration,
EngelScript recursion refusal, Main-chat interception, harness registration,
and receipt persistence. A green syntax check alone is not a release proof.

