# Engel HIPL/MIPL Intent Bridge and MIPL/2 Language

Design and implementation — 2026-08-03; authored-agent packet extension — 2026-08-08.

Status: MIPL v2 is shipped in `engel_mipl.py`. It is wired into
`engel_lifted_intent.py`, the Engel Main chat worker, Agent Kernel, route
registry, receipts, and System → Intent UI.

The 2026-08-08 extension adds a bounded `AGENT_TASK` stream and the
`engel_mipl_agent_work.py` bridge. Engel Main can now prepare one authored
agent, bind explicit skills, assign one task, and carry the exact binding into
the existing authored-agent runner. Creation, activation, action grants, and
execution remain separate audited steps.

## Purpose

Engel has strong executors and gates. MIPL supplies the small deterministic
semantic package that tells those existing parts what the human intended and
what proof must return. It is not a model, agent, scheduler, or executor.

```text
HIPL expression
    ↓
lifted intent (objective, effect, targets, constraints, proof criteria)
    ↓
MIPL/2 request packets (resolve → gate → dispatch → verify → return)
    ↓
existing Engel Governor / Agent Kernel / routes / sandboxes
    ↓
MIPL/2 outcome packets (result + proof/error → return)
    ↓
HIPL comprehension
```

HIPL is the human-facing language and surface. MIPL is the compact
machine-intended packet language. The lifted intent is their shared semantic
object.

## Why MIPL uses less hardware

MIPL compilation and validation are deterministic standard-library work. They
require no language model, provider, network call, vector database, package
install, route-catalog import, autonomous loop, or background worker.

The `mipl2-low-resource` profile has fixed ceilings:

- at most 32 packets per stream;
- at most 32,768 encoded wire bytes;
- at most 24,576 decoded payload bytes;
- at most 800 result-summary characters;
- at most 12 targets, proof paths, and verification criteria;
- at most 8 skills and 2,000 task characters per authored-agent assignment;
- numeric one-byte opcodes;
- compact canonical JSON with DEFLATE used only when it makes the stream
  smaller;
- SHA-256 integrity over the uncompressed canonical payload.

These are honest bounds, not a claim that MIPL replaces the hardware needed by
an LLM or executor. MIPL avoids using those heavy components for intent
transport, routing metadata, validation, and receipts.

## Packet set

| Opcode | Packet | Purpose |
|---:|---|---|
| `0x01` | `BEGIN` | Declares request/outcome mode and failure behavior. |
| `0x02` | `INTENT` | Carries expression and lifted-intent hashes plus effect. |
| `0x03` | `BUDGET` | Declares packet, wire-byte, and result-character ceilings. |
| `0x04` | `RESOLVE` | Names bounded capability targets. |
| `0x05` | `GATE` | Requires the existing approval/Governor policy. |
| `0x06` | `DISPATCH` | Names an existing Engel engine; external gate is mandatory. |
| `0x07` | `VERIFY` | Carries bounded acceptance criteria. |
| `0x08` | `RETURN` | Returns result and failures to HIPL comprehension. |
| `0x09` | `RESULT` | Carries success, status, and result hash. |
| `0x0A` | `PROOF` | Carries bounded receipt or verifier paths. |
| `0x0B` | `ERROR` | Carries a bounded failure code and summary. |
| `0x10` | `AGENT` | Pins the authored agent id, name, purpose, and lifecycle. |
| `0x11` | `SKILL` | Pins one catalogued skill, its real tool names, and whether an operator grant is required. |
| `0x12` | `TASK` | Pins one objective, turn ceiling, and completion evidence list. |
| `0x13` | `ASSIGN` | Binds the declared agent, task, and ordered skill ids. |
| `0xFF` | `END` | Terminates the stream. |

The request grammar is fixed:

```text
BEGIN INTENT BUDGET RESOLVE GATE DISPATCH VERIFY RETURN END
```

The outcome grammar is fixed:

```text
BEGIN RESULT [PROOF] [ERROR] RETURN END
```

The authored-agent assignment grammar is fixed except for one to eight
contiguous `SKILL` packets:

```text
BEGIN INTENT BUDGET RESOLVE AGENT SKILL... TASK ASSIGN
GATE DISPATCH VERIFY RETURN END
```

For this stream, `DISPATCH` names the existing
`engel_authored_agent_runner`, still with `external_gate_required`.

An unsuccessful `RESULT` must include `ERROR`; a successful result must not.
Both paths must return failures honestly to HIPL.

## Writing MIPL/2

The human-readable assembler format starts with a stream declaration. Each
following instruction takes one JSON argument object. Example:

```mipl
MIPL/2 REQUEST
BEGIN {"kind":"request","failure":"closed"}
INTENT {"expression_hash":"<64 hex>","lifted_intent_hash":"<64 hex>","effect":"create"}
BUDGET {"max_packets":32,"max_wire_bytes":32768,"max_result_chars":800}
RESOLVE {"targets":["engel-ai-main"]}
GATE {"policy":"approval_and_governor","failure":"closed"}
DISPATCH {"engine":"existing_engel_engine","authorization":"external_gate_required"}
VERIFY {"criteria":["Return a verifier receipt."]}
RETURN {"channel":"hipl_comprehension","include_failures":true}
END
```

`engel_mipl.assemble()` converts this format to the bounded wire IR.
`engel_mipl.disassemble()` returns editable source. Assembly does not execute
the stream.

## Non-authorizing MIPL

Every MIPL IR has `execution_authorized: false`. Intent classification is not approval.
An intended or attempted action is never completion proof.

The `DISPATCH` packet may name `existing_engel_engine` for a normal request or
`engel_authored_agent_runner` for an agent-task assignment, and it must state
`external_gate_required`. Side-effecting effects fail closed and require the
current approval and Governor path. Guardian, Governor, approval tokens/files,
route metadata, Agent Kernel, authored-agent lifecycle, and sandbox rules
remain authoritative.

## Authored-agent work flow

`engel_mipl_agent_work.py` is the persistent bridge. Its catalog maps the large
Meeting Room label roster onto a smaller set of capabilities backed by tool
names that `engel_agent_author.py` already enforces. All current Meeting Room
skill labels resolve through this bridge. An unknown label is refused; it is
never treated as arbitrary authority.

State transitions are deliberately separate:

1. `preview` compiles the complete packet in memory and writes nothing.
2. `create` atomically writes a draft agent and an `assigned_draft` task into
   `memory/agents/ENGEL_AGENT_REGISTRY.json`. It does not activate or run.
3. `activate` requires a named operator and permits a bounded run. A skill's
   privileged tools remain locked.
4. `grant` requires a named operator and a reason, and enables only the pending
   privileged tools already named by the bound skills.
5. `run` performs one bounded session through the existing local authored-agent
   runner. A successful reply becomes `review_required`, never `completed`.

Revoking the action grant removes privileged tools from the usable tool list
and returns them to the pending list. Every transition produces a local
receipt; the stored task retains its MIPL hash and full packet so reference
drift or tampering is detectable before a run.

## Wire envelope and validation

The binary envelope contains:

```text
magic | version | flags | packet count | reserved
decoded length | body length | SHA-256 | body
```

Validation rejects:

- wrong magic, schema, version, profile, or stream kind;
- unknown or out-of-order opcodes;
- non-contiguous sequence numbers;
- missing or oversized arguments;
- invalid expression, intent, request, or result hashes;
- resource budgets above the profile ceiling;
- compressed payloads that expand past the payload ceiling;
- trailing compressed data, truncated payloads, or metadata mismatches;
- dispatch that does not defer to an existing engine and external gate;
- side-effecting requests that do not fail closed;
- result/error combinations that contradict each other;
- return packets that hide failures or bypass HIPL comprehension;
- any IR that claims execution authority.

## Audit chain

Completed receipts recompute and link:

```text
expression_hash → lifted_intent_hash → MIPL request hash → contract_hash
contract_hash + result_hash + MIPL outcome hash → audit_head
```

Receipts are written atomically under `reports/engel_lifted_intent/`; the UI
reads `LATEST.json`. Common password, token, secret, bearer-token, and API-key
forms are redacted before local persistence. Raw model output is not embedded
in MIPL; only bounded status, hashes, and proof references return.

## Engel Main integration

- Every Engel Main chat response is annotated with the lifted-intent summary,
  receipt path, and audit-complete state.
- Every Agent Kernel goal receives its MIPL request before engine selection and
  a MIPL outcome after the lane result.
- `lift intent <request>` and `compile mipl <request>` compile safe previews and
  execute nothing.
- `mipl docs`, `mipl status`, and `latest lifted intent` expose the language and
  current receipts.
- `mipl agent docs|skills|status|list` expose the authored-agent packet layer.
  JSON-bearing `mipl agent preview|create|activate|grant|run` commands use the
  same bounded API from Chat.
- Agents → **Create a task agent** provides the easy draft creator; Skills →
  **Task-agent skill catalog** shows exact capabilities and gated tools.
- System → Intent displays the MIPL version, packet count, encoded bytes,
  resource profile, result, and proof without requiring the operator to read
  JSON.

## Explicit limits

- MIPL does not replace EngelScript or create a general-purpose executor.
- MIPL does not decide which model is correct or grant permission.
- MIPL creates no listener, port, schedule, provider call, autonomous loop, or
  background service.
- MIPL cannot make an LLM inference itself cheaper; it keeps deterministic
  intent handling and verification off the model path.
