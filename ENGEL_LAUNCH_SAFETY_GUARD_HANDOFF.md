# Engel Launch Safety Guard — Python Handoff

## Goal

Create a Python-based **Engel Launch Safety / Computer Stability Guard** before adding more Engel layers.

This guard should help ensure that when Engel is turned on, it does not overload or crash the laptop.

## Core Principle

Engel startup must be:

```text
staged
bounded
lightweight
human-controlled
read-only by default
```

## What This Adds

A Python preflight script:

```text
tools/engel_launch_safety_guard.py
```

The script checks:

- AC power / battery state when available
- available RAM when available
- free disk space on configured Engel project drives
- whether heavy development processes are already running
- startup safety policy status

It returns one of:

```text
SAFE
CAUTION
BLOCKED
```

## What This Must Not Add

This must not enable:

- provider/API/network calls
- background workers
- autonomous loops
- heavy startup scans
- automatic Android builds
- recursive project indexing
- colony/swarm/mycelium runtime
- trusted-memory writes
- route mutation
- queue mutation
- source edits outside the explicit implementation
- `ALIVE_STATE` writes
- automatic remediation
- killing processes

## Suggested File Placement

Copy the Python script to:

```text
D:\b.WorkSpace\Engel App\tools\engel_launch_safety_guard.py
```

Optional reports should go to:

```text
D:\b.WorkSpace\Engel App\reports\launch_safety\
```

## Suggested Commands

From `D:\b.WorkSpace\Engel App`:

```powershell
python .\tools\engel_launch_safety_guard.py
```

Strict mode:

```powershell
python .\tools\engel_launch_safety_guard.py --block-on-heavy-processes
```

JSON output:

```powershell
python .\tools\engel_launch_safety_guard.py --json
```

Explicit report write:

```powershell
python .\tools\engel_launch_safety_guard.py --write-report
```

## Future Engel Route Shape

Later, Engel App can expose this as a read-only route:

```text
launch safety status
```

Expected behavior:

```text
Engel Launch Safety: ACTIVE
Startup mode: lightweight
Background workers: disabled
Autonomous loops: disabled
Heavy scans: disabled until approved
Provider/network calls: disabled
Swarm/colony/mycelium runtime: disabled
Build tasks: manual only
Status: SAFE / CAUTION / BLOCKED
```

## Definition of Done

- Python script exists under `tools/`.
- Script runs with `python .\tools\engel_launch_safety_guard.py`.
- Default mode does not write files.
- `--write-report` is the only report-writing path.
- Script performs no network/provider/API behavior.
- Script starts no background workers.
- Script does not kill or modify processes.
- Script does not mutate Engel memory, routes, queues, or autonomy state.
- A short completion report is created after local verification.
