---
name: "engel-route-dispatch"
description: "Operate and extend the Engel AI Main 490-route command system. Use whenever a request involves running a route, asking Engel a phrase, the route explorer, route smoke tests, adding a new route, or debugging why a phrase hit the wrong route."
version: "1.0.0"
source: "claude-skill-creator"
created_at_utc: "2026-08-04T14:56:01Z"
updated_at_utc: "2026-08-04T14:56:01Z"
---

# Engel Route Dispatch

## Purpose

Every user-facing Engel action flows through one spine: phrase in, route matched, module function called, string out. This skill explains how to drive that spine, extend it safely, and debug it when a phrase lands on the wrong route.

## Trigger Conditions

- The user asks to run, test, list, or explore Engel routes.
- The user wants a new feature reachable by phrase ("add a route for X").
- A phrase returns the wrong output and the route match must be debugged.
- Route smoke tests or the route explorer catalog are mentioned.

## How dispatch works

1. Phrase enters via `engel_ai.py` CLI (`python engel_ai.py ask "<phrase>"`) or the `engel_desktop_v2.py` chat panel.
2. `engel_communication_router.classify_user_input(phrase)` checks alias tables, then falls back to `resolve_update_route` in `engel_ai_update_routes.py`.
3. The matched `EngelAIUpdateRoute` declares `target_module` + `target_function` + safety flags (`read_only`, `status_only`, `no_provider_model_network`).
4. The dispatcher imports the module, calls the function with the remaining payload, and surfaces the string return.

`UPDATE_ROUTES` in `engel_ai_update_routes.py` is the single source of truth for the registry (~490 routes).

## Operating Instructions

- Run one phrase: `python engel_ai.py ask "engel status"` (always the D: interpreter: `D:\b.WorkSpace\Engel App\runtime\python310\python.exe`).
- Smoke-test the registry: `python _route_smoke.py` (~2-3 min; 445 routes run, 45 slow `.build`/`.install` skipped).
- Add a feature: (a) write `render_<name>()` in an `engel_<feature>.py` module, (b) add a `ROUTE_ID` constant + `EngelAIUpdateRoute(...)` entry to `UPDATE_ROUTES`, (c) extend `_group_for_route()` in `engel_route_explorer.py` if it needs a new group.
- Before touching any route, read `memory/ROUTE_METADATA_REFERENCE_MAP_V1.md` and `memory/ROUTE_METADATA_VERIFIER_CONTRACT_V1.md`.
- After route changes, run `python tools/verify_engel_route_explorer_superswarm.py` — the explorer catalog must exactly cover `UPDATE_ROUTES`.

## Debugging wrong matches

Stale hardcoded aliases in `engel_communication_router.KNOWN_COMMANDS` and `COMPLEX_HUMAN_COMMAND_MODE_COMMANDS` can shadow new routes. When a smoke mismatch shows `route_target != expected`, look there first. Also note `engel_desktop_v2.py` intercepts some phrases (`meeting room`, `where is the meeting room`) locally before routing.

## Save Contract

- New routes ship with their `render_*` function, registry entry, and explorer group in the same change.
- Run the route smoke plus the route-explorer verifier before reporting done.
- Report changes under `reports/codex_bridge/<NAME>.md`.
- Do not add provider/network calls, autonomous loops, or trusted-memory writes to route handlers.
