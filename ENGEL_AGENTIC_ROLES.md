# Engel Agentic Roles

## Role Definitions

| Role | Meaning | Existing assignment examples |
|---|---|---|
| Controller | Final decision authority | Josh |
| Orchestrator | Routes requests and coordinates system | ROG Strix G15, `scripts/Start-EngelMainOneSystem.ps1`, desktop shortcut |
| Body | Main runtime execution system | CT 246 `engel-ai-main`, `/opt/engel` |
| Spine | Infrastructure backbone | Proxmox host `engel-spine-01` |
| Vault | Long-term storage/memory/model archive | PowerVault, `/mnt/engel-vault` |
| Worker | Delegated task/device executor | `remote_workers/`, `mobile/`, `engel_adb_worker_manager.py`, connected phones |
| Verifier | Checks health, contracts, safety | `tools/verify_*`, `scripts/codex_verify.ps1`, `_route_smoke.py` |
| Builder | Packaging/build surfaces | `build_*.ps1`, `Engel.spec`, `dist/`, `pyinstaller_runtime_hooks/` |
| Monitor | Status/watchdog/health surfaces | `engel_guardian_watchdog.py`, `engel_system_monitor.py`, health scripts |
| Logger | Receipts, reports, logs | `reports/`, `build_*.log`, `runtime/` reports |
| Memory Curator | Memory review/archive/promotion | `memory/`, `engel_memory_*`, `engel_approved_memory_promotion.py` |
| Model Manager | Model intake, review, runtime selection | `models/`, `engel_local_model_manager.py`, `engel_large_chat_llm.py`, F-drive transferred archive |
| App Backend Worker | Python/Rust backend modules | root `engel_*.py`, `engelcode_main/src`, backend scripts |
| Mini-game Worker | Game/runtime demo components | `assets/engel_game_runtime`, game factory bridge, game-related assets |

## Module Role Assignments

| Path pattern | Assigned role |
|---|---|
| `agents/`, `.agents/` | Agent |
| `skills/` | Agent skill/tool role |
| `scripts/` | Orchestrator/tool/verifier depending on filename |
| `tools/` | Tool/verifier/worker support |
| `memory/` | Memory Curator and system memory |
| `models/` | Model Manager |
| `remote_workers/`, `remote_nodes/`, `mobile/` | Worker |
| `engel3d_office_main/` | Agent meeting room/3D office body-part visualization |
| `engel_flutter_main/`, `engel_chat_ui_main/`, `engel_main/` | UI/app frontend |
| `engelcode_main/` | Coding tool/backend worker |
| `engelsandbox_main/`, `engel_cubesandbox_main/` | Sandbox worker/tool |
| `archive/`, `backups/`, `dist/` | Vault candidate, backup, or build artifact |
| `browser_profile/`, caches, `__pycache__` | Cache/pending review |

## Assignment Rule

If a file does not clearly match a role, it stays `unknown / pending review` in the manifest. Unknown is a documented state, not permission to delete.

