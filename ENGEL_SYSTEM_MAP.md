# Engel AI Main Conical Agentic System Map

Workspace: `D:\b.WorkSpace\Engel App`

## System Identity

Engel AI Main is one Conical Agentic System. The workspace is not a loose pile of folders. Every inspected file, folder, script, prompt, model reference, cache, UI surface, backend module, worker module, log, report, and document is treated as part of Engel until it is classified or marked `unknown / pending review`.

## Authority Cone

```text
Josh
-> ROG Queen Orchestrator
-> engel-spine-01 Spine
-> engel-ai-main Body
-> connected worker parts/devices
-> PowerVault Memory/Vault
```

## Roles In The Cone

| Layer | Node | Role | Authority |
|---|---|---|---|
| Human | Josh | Human controller and final authority | Final approval, emergency stop, destructive-action approval |
| Queen | ROG Strix G15 laptop | Orchestrator, command system, fallback access | Starts/uses Engel UI, routes commands, opens CT access |
| Spine | engel-spine-01 | Proxmox host and local infrastructure backbone | Hosts CT 246 and storage paths; no destructive changes without Josh |
| Body | engel-ai-main | Main runtime container | Runs Engel server runtime, chat body, meeting room body, model services |
| Limbs | Connected devices | Worker body parts | Phones, desktops, laptops, GPUs, tools, storage workers when approved |
| Memory | PowerVault / engel-vault-main | Long-term vault | Memory archive, models archive, datasets, backups, transfers |

## Command Flow

1. Josh enters intent through the ROG Engel AI Main app, terminal, or approved control surface.
2. ROG acts as Queen Orchestrator and routes the request to local UI, local tools, or the server body.
3. Server body `engel-ai-main` handles runtime work inside CT 246 through `/opt/engel` and approved services.
4. Worker limbs may be selected for load, app work, phone work, GPU work, testing, or specialized tasks only when approved and safe.
5. PowerVault stores long-lived memory, model archives, datasets, backups, and transfer records.

## Approval Flow

```text
Josh approval
-> ROG command gate
-> Guardian/safety checks
-> Engel runtime or worker action
-> verifier/report
-> memory/report registration
```

Josh remains highest authority. ROG remains the emergency fallback and Queen controller. Engel runtime may observe, summarize, compare, plan, verify, and report. Engel does not autonomously execute destructive actions, migrations, storage mutation, or uncontrolled worker loops.

## Fallback Flow

| Failure | Safe fallback |
|---|---|
| CT runtime unavailable | ROG local app remains controller and can SSH to Proxmox/CT when approved |
| Server body slow or down | ROG can use local docs, manifests, and fallback workflows |
| PowerVault unavailable | Runtime stays on fast SSD; vault-dependent tasks pause until storage is healthy |
| Worker limb disconnected | Worker is marked pending/unavailable; job is not silently reassigned to risky actions |
| Unknown file/component | Mark unknown / pending review in the manifest; do not delete or move |

## Request Routing

| Request type | Primary route | Storage target | Notes |
|---|---|---|---|
| Chat/user communication | ROG UI -> CT chat service -> Engel body | `/opt/engel/memory` and approved memory surfaces | Must stay fast and persistent |
| Agent meeting room | ROG UI -> CT meeting room -> agent roster/tools | `/opt/engel/run`, `/opt/engel/memory`, vault archive for history | Worker selection must be visible |
| Model inference | ROG request -> CT model service | `/opt/engel/models-active` for fast active models; vault for archives | Long-lived model service is the intended path |
| File/model archives | ROG/CT documentation and approved copy workflows | `/mnt/engel-vault` | Migration requires approval |
| Device/phone work | ROG -> server body -> worker limb | worker queues and reports | Device identity must be explicit |
| Documentation | Local workspace docs | `D:\b.WorkSpace\Engel App` and CT report/memory when approved | This task is documentation-only |

## Completed Documentation Position

The current workspace is mapped as the ROG-side Engel App source body. The server-side body target is `engel-ai-main:/opt/engel/app`. Large model and archive payloads map to `engel-ai-main:/mnt/engel-vault`. This document does not execute migration or activation.

