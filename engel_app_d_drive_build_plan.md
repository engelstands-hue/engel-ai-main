# Engel App Build Plan — B Workspace Active Workspace

**Active workspace:** `D:\b.WorkSpace\Engel App`

**Standing rule:** From now on, this Engel App project stays on `D:\b.WorkSpace\Engel App`.

Do not use old paths:

```text
E:\Engel App
E:\EngelStandalone
D:\b.WorkSpace\Engel App
S:\Engel App
```

Older notes that mention old E-drive or S-drive locations are historical only. When reused, they must be translated into the current active workspace:

```text
D:\b.WorkSpace\Engel App
```

---

## Core Direction

Engel is a local/offline living learning companion system.

Engel Core:

```text
Self-researching
Self-teaching
Self-improving
Self-updating
Self-protecting
```

Engel may notice, learn, propose, and improve.

Engel may not trust, write, mutate, execute, enable, or update until the Immune System, verifiers, and human approval path allow it.

---

## Engel Immune System

The Engel Immune System is the Guardian/self-protection membrane around Engel's living learning architecture.

It protects:

```text
Engel Core
Colony / hive-mind layer
Swarm layer
Mycelium layer
Engel Mind memory nests
Trusted-memory write paths
Route/source mutation paths
Provider/network/autonomy gates
Computer stability / launch safety
```

The Immune System should not block Engel's growth. It protects growth from corrupted research, prompt injection, unsafe autonomy, poisoned memory candidates, unsafe route mutation, provider/network reactivation, unapproved source/write changes, and computer overload at launch.

---

## Computer Stability Comes First

Before adding more layers, Engel must protect the laptop.

Engel startup must be:

```text
lightweight
staged
bounded
human-controlled
read-only by default
```

On startup, Engel should not automatically start:

```text
heavy scans
Android builds
recursive indexing
provider/API/network calls
background workers
autonomous loops
swarm/colony/mycelium runtime
bulk memory writes
long-running research tasks
```

Safe startup flow:

```text
Engel opens
  ↓
Launch Safety Guard checks computer stability
  ↓
Engel stays lightweight
  ↓
Heavy work requires explicit user approval
```

---

## Architecture Inspiration

Use Argentine ant supercolonies as design inspiration only.

Design metaphor:

```text
many nests
many workers
many queens
one cooperative colony identity
```

Engel's Mind should feel like one living companion built from many local memory colonies:

```text
thought seeds
chat memories
work history
project history
research reports
approved lessons
swarm trails
companion reflections
```

The goal is not uncontrolled autonomy.

The goal is coordinated offline intelligence:

```text
Engel remembers.
Engel compares.
Engel reinforces.
Engel cools down.
Engel researches.
Engel proposes.
Authority order stays fixed: Josh first, Guardian second, Engel/runtime below both.
```

This is a structural metaphor, not a claim of biological consciousness.

---

## Master Build Track

### EW — Launch Safety Guard Integration

**Purpose:** Make Engel safe to turn on before adding more layers.

Add an official Python launch preflight under:

```text
D:\b.WorkSpace\Engel App\tools\engel_launch_safety_guard.py
```

Add read-only route:

```text
launch safety status
```

The route should summarize:

```text
Engel Launch Safety: READ_ONLY / PREFLIGHT
Startup mode: lightweight
Background workers: disabled
Autonomous loops: disabled
Heavy scans: disabled until approved
Provider/network calls: disabled
Swarm/colony/mycelium runtime: disabled
Build tasks: manual only
Status: SAFE / CAUTION / BLOCKED
```

Must not add internet behavior, provider/API calls, background workers, autonomous loops, startup scans, automatic Android builds, recursive indexing, colony/swarm/mycelium runtime, trusted-memory writes, queue mutation, ALIVE_STATE writes, automatic remediation, process killing, or OS setting changes.

---

### EX — Refactor Safety Contract

**Purpose:** Prepare `D:\b.WorkSpace\Engel App` for staged refactoring without behavior changes.

This is a contract/documentation milestone only.

Rules:

```text
No big refactor yet.
No source movement yet.
No route behavior change yet.
No provider reactivation.
No autonomy enablement.
No background workers.
No trusted-memory mutation.
No queue mutation.
No ALIVE_STATE writes.
No large rename/move pass without verifier coverage.
```

Define backup rules, safe slice order, forbidden changes, verification requirements, and rollback expectations.

---

### EY — Colony Autonomy Ladder Contract

**Purpose:** Define Engel's staged colony autonomy model.

Use the Argentine ant supercolony metaphor:

```text
one Engel Mind
many local memory nests
many worker-style checks
many proposal paths
one cooperative companion identity
```

Define levels:

```text
Level 0 — Status only
Read-only routes. No writes. No autonomy.

Level 1 — Local sensing autonomy
Light local inspection while Engel is running.
No background daemon.
No provider calls.
No trusted writes.
No work after Engel exits.

Level 2 — Proposal autonomy
Can prepare approved proposal/report artifacts.
No trusted-memory writes.
No learning apply.

Level 3 — Research ON bounded autonomy
Only after explicit Research ON toggle.
Strict caps.
Approval still required before trusted changes.

Level 4 — Approved learning integration
Approved lessons may enter trusted memory only after explicit approval and verifier checks.

Level 5 — Source/code proposal support
Can prepare source-change proposals or Codex prompts.
Cannot edit source without approval.
```

Implement only documentation/contract at this stage. Do not implement sensing runtime yet.

---

### EZ — Colony Autonomy Status Routes

**Purpose:** Add read-only visibility into the autonomy ladder.

Routes:

```text
colony autonomy status
colony autonomy ladder
```

Behavior:

```text
read-only
no writes
no sensing
no provider calls
no background worker
no autonomy enablement
```

---

### FA — Level 1 Local Sensing Preview

**Purpose:** Add a safe preview of what Engel would notice locally.

Routes:

```text
colony sensing status
colony sensing preview
```

Behavior:

```text
light local inspection only
read-only
bounded
no report write
no trusted-memory write
no source edit
no queue mutation
no provider call
no work after Engel exits
```

The preview may show recent reports, known memory files, current project state signals, possible next safe build step, and warnings requiring Josh review.

---

### FB — Sensing Preview APPROVE_REPORT

**Purpose:** Allow a human-approved sensing preview report.

Route:

```text
colony sensing preview APPROVE_REPORT
```

Allowed behavior:

```text
write exactly one report-only markdown
no trusted-memory write
no queue mutation
no learning apply
no source edit
no background work
no provider call
```

---

### FC — Engel Mind Supercolony Architecture Contract

**Purpose:** Document Engel Mind before implementation.

Engel Mind should be one local/offline companion built from many memory nests:

```text
thought seeds
conversation memory
work history
project history
research reports
approved lessons
swarm trails
companion reflections
```

This milestone is documentation/contract only.

Do not add thought intake, memory archive, runtime autonomy, research start, learning apply, source edits, provider calls, or background workers.

---

### FD — V2MIND-A Companion Thought Intake Contract

**Purpose:** Define the first safe thought-seed intake feature before implementation.

V2MIND-A lets Josh speak naturally to Engel and have Engel hold explicit ideas locally as offline brain thought seeds.

Natural inputs:

```text
think about <idea>
Engel, think about <idea>
remember this idea: <idea>
research idea <idea>
```

Engel response should feel warm:

```text
I hear you.
I'll hold this in my offline brain as something to think about.
```

This is not all-chat memory, automatic research, autonomous action, learning apply, or source apply.

Allowed write targets when implemented:

```text
memory\COMPANION_THOUGHT_INBOX_V2MIND_A.json
reports\mind\COMPANION_THOUGHT_INBOX_V2MIND_A.md
memory\COMPANION_THOUGHT_PROMOTED_RESEARCH_TOPICS_V2MIND_A.md
```

Promotion must require exact approval.

---

### FE — V2MIND-A Companion Thought Intake Implementation

**Purpose:** Implement explicit thought seed capture.

Commands:

```text
think about <idea>
Engel, think about <idea>
remember this idea: <idea>
research idea <idea>
idea queue status
idea queue review
idea queue promote preview
idea queue promote APPROVE
```

Thought schema:

```text
id
timestamp
raw_text
idea_text
source_command
classification list
status: HELD
target: OFFLINE_BRAIN_RESEARCH_SEED
promoted: false
safety_notes
```

Simple classification categories:

```text
Body
Mind
Safety
App
Mobile
Process
Research
Income
Memory
Swarm
Hive
Offline
Unknown
```

If idea mentions ants, hive, colony, swarm, pheromone, supercolony, or Argentine ants, classify as Mind, Swarm, Hive, Research, and Offline if relevant.

Safety rules:

```text
No source edited.
No learning applied.
No research started.
No cloud fallback.
No LEARNING_LOG write.
No automatic promotion.
```

`idea queue promote APPROVE` may write only proposed research-topic entries to:

```text
memory\COMPANION_THOUGHT_PROMOTED_RESEARCH_TOPICS_V2MIND_A.md
```

It must not start research.

---

### FF — V2MIND-B Offline Conversation Memory Archive Contract

**Purpose:** Define archive-only offline conversation/work memory.

V2MIND-B creates the next memory nest after thought seeds.

It may archive explicit user-provided memory text and safe local Engel-accessible work/session memory.

It must not access external ChatGPT history, use internet/cloud, distill memories into lessons, write `LEARNING_LOG.md`, start research, change behavior based on memory, or recall archived memory into active context.

Allowed future write targets:

```text
memory\OFFLINE_CONVERSATION_ARCHIVE_V2MIND_B.jsonl
memory\OFFLINE_CONVERSATION_INDEX_V2MIND_B.json
reports\mind\OFFLINE_CONVERSATION_ARCHIVE_V2MIND_B.md
reports\mind\V2MIND_B_OFFLINE_CONVERSATION_ARCHIVE_DIAGNOSE.md
```

---

### FG — V2MIND-B Offline Conversation Memory Archive Implementation

**Purpose:** Implement explicit local memory archive.

Commands:

```text
offline memory status
offline memory review
offline memory archive latest APPROVE
offline memory archive note: <text>
offline memory export report
```

Optional aliases if narrow and safe:

```text
archive this memory: <text>
remember this conversation: <text>
```

Archive schema:

```text
id
timestamp
source_type
source_path
raw_text_or_summary
title
tags
safety_classification
archived_by_command
distillation_status: NOT_DISTILLED
recall_status: NOT_ACTIVE
approved_for_learning: false
approved_for_research: false
notes
```

Safety:

```text
archive-only
no LEARNING_LOG write
no RESEARCH_GOALS_QUEUE write
no research start
no source edit
no cloud fallback
no launcher/shortcut/EXE changes
```

---

### FH — V2MIND-C Memory Distillation / Self-Teaching Proposals Contract

**Purpose:** Define how archived thought seeds and conversation memories can later become self-teaching proposal candidates.

This is contract only.

It should define what may be distilled, what remains untrusted, how proposal candidates are labeled, how Guardian reviews them, how Josh approves them, and what verifiers must check.

No implementation yet. No trusted learning write yet.

---

### FI — V2MIND-D Offline Recall into Engel Active Mind Contract

**Purpose:** Define how archived local memory may later be recalled into Engel's active context.

This is contract only.

It must answer:

```text
what memory can be recalled
how much can be recalled
when recall is allowed
how stale/corrupt memory is avoided
how prompt-injection is blocked
how Josh can disable recall
```

No implementation yet. No automatic behavior change yet.

---

### FJ — V2SWARM-C Supercolony Hive-Mind Strategy Contract

**Purpose:** Define later swarm reinforcement/decay strategy.

This is where pheromone-style reinforcement/decay belongs, not V2MIND-A.

It should cover signal reinforcement, signal decay, cool-down, competing proposals, worker scoring, colony identity consistency, Guardian review, and Josh approval.

No implementation yet. No autonomous action yet.

---

### FK — Engel Bible Companion Architecture Cleanup Note

**Purpose:** Keep the Engel Bible Companion architecture cleanly separated.

Architecture:

```text
Engel Bible Companion
├─ Mobile App Shell
│  ├─ Android UI
│  ├─ orb / chat input / mic direction
│  ├─ splash / launcher branding
│  └─ future iOS shell
│
├─ Engel Companion / LLM Layer
│  ├─ persona prompt
│  ├─ humanized companion voice
│  ├─ Bible-study behavior
│  ├─ safe humility / no false divine claims
│  └─ future chat connection
│
└─ Bible Engine / Research Library
   ├─ inventory report
   ├─ approval review plan
   ├─ approved resource registry
   ├─ future local search/index
   ├─ source labels / quote limits
   └─ future Engel Mind deep-search connection
```

This should be separate from colony autonomy and Engel Mind implementation.

---

### FL — Engel App / Bible Companion Alignment Contract

**Purpose:** Align main Engel Mind with Engel Bible Companion safely.

Goal:

```text
Engel Bible Companion remains Scripture-first.
Engel App remains the broader living learning system.
The two can align through safe local/offline memory, approved resources, and guarded companion behavior.
```

Must preserve Scripture first, no false divine claims, no cloud fallback unless explicitly approved later, no unsafe provider/network behavior, no unapproved Bible resource ingestion, and no unapproved memory/trusted learning writes.

---

## Codex Usage Rule

Even with Pro, keep Codex jobs narrow.

```text
One milestone.
One Codex task.
One report.
One checkpoint.
Run verifiers.
Stop before broad refactor.
```

Do not send Codex a giant “do everything” task.

Each task should include:

```text
project path: D:\b.WorkSpace\Engel App
goal
files allowed
forbidden changes
implementation steps
verification commands
definition of done
```

---

## Standard Safety Rules for Every Milestone

Unless a milestone explicitly allows it, do not add:

```text
internet behavior
provider/API calls
background workers
autonomous loops
startup scans
automatic Android builds
recursive indexing
trusted-memory writes
learning apply
source apply
queue mutation
route mutation beyond explicit route work
digest/history writes
ALIVE_STATE writes
process killing
OS setting changes
launcher/shortcut changes
EXE build/launch
mobile bridge changes
cloud fallback
```

---

## Standard Verification Expectations

For each milestone, run relevant checks such as:

```powershell
cd /d "D:\b.WorkSpace\Engel App"
python -m py_compile engel_app.py engel_research_brain_v2.py
```

If a new Python tool is added:

```powershell
python -m py_compile tools\<new_tool>.py
python tools\<new_tool>.py
```

Run existing standard verifiers sequentially when available.

Run targeted CLI smoke checks for affected routes.

Confirm status routes do not create reports unless explicitly approved.

Search for forbidden additions:

```text
provider calls
internet/network calls
background workers
autonomous loops
STAGED_DRAFT_ACTIVE=True
runtime_autonomy_enabled true
runtime_level_2_enabled true
ALIVE_STATE writes
```

---

## Immediate Next Step

Finish:

```text
EW — Launch Safety Guard Integration
```

Then paste back:

```text
Files changed:
Verification commands:
Results:
Errors or warnings:
```

Only after EW passes should Engel move to:

```text
EX — Refactor Safety Contract
```
