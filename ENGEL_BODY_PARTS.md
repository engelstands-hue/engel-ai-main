# Engel Body Parts

## Body-Part Model

Engel is one system with distinct body parts. Each part has a role, health boundary, safe failure behavior, and allowed work-sharing behavior.

| Body part | Component | Allowed work-sharing behavior | Safe failure behavior |
|---|---|---|---|
| Brain/authority | Josh | Approves direction and high-risk actions | Pause until Josh decides |
| Queen nervous system | ROG Strix G15 | Routes commands, keeps UI/control, fallback access | Continue local docs/control; do not assume server state |
| Spine | engel-spine-01 | Hosts CT and storage plumbing | Pause CT/storage-dependent work |
| Body | engel-ai-main CT 246 | Runs chat, meeting room, model service, memory runtime | ROG fallback; no blind restart loops |
| Memory/vault | PowerVault / engel-vault-main | Stores long-lived models, memory, datasets, backups | Do not write vault-dependent data until healthy |
| Hands/tools | `scripts/`, `tools/`, launchers, verifiers | Execute approved bounded operations | Stop on error, write report, ask approval for risky actions |
| Voice/chat | Engel UI/chat service | User communication and response generation | Fall back to ROG docs/local route if CT is unavailable |
| Meeting room | `engel3d_office_main`, meeting room services | Visualize agents, roles, devices, work assignments | Preserve state, do not dispatch unknown workers |
| Eyes/sensors | device status, health checks, LAN/ADB discovery | Read-only observation unless approved | Mark unknown/pending review |
| Limbs/workers | phones, desktops, laptops, GPU nodes | Device-scoped work after registration | Mark unavailable; do not reassign blindly |
| Memory curator | `memory/`, vault memory archive | Organize and propose memory updates | No trusted-memory writes without approval |
| Model manager | active models and vault model archive | Select/promote model payloads by policy | Do not activate unknown models |
| Wiki One | `wiki/ONE.md` + `wiki/organs.json` | Living body map: every organ, what it does, who it talks to. Whole Engel AI Main reads it before CODE and updates it when organs change. Stamp `wiki/journal` after CODE. | Keep map in sync with code; not trusted memory |

## Delegation Rules

- Worker delegation must name the device or worker identity.
- A shared role name such as alpha/beta is not enough when more than one device may use it.
- Heavy tasks need approved budget, stop condition, and receipt path.
- Failure of one body part must not cascade into destructive recovery.
- Unknown workers are not used until registered.

## Meeting Room Rule

The virtual agent meeting room must show which agents exist, which device/body part they are using, what work they are assigned, and whether that device is healthy, pending, or unavailable.

