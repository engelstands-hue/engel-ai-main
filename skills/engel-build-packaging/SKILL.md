---
name: "engel-build-packaging"
description: "Build and package Engel deliverables: Engel.exe, the SuperSwarm exe, approved staged artifacts, and the Android worker APK. Use whenever a request mentions building an exe, PyInstaller, packaging, staging artifacts, rebuilding the APK, or why a folder shows as MISSING inside a packaged exe."
version: "1.0.0"
source: "claude-skill-creator"
created_at_utc: "2026-08-04T14:56:01Z"
updated_at_utc: "2026-08-04T14:56:01Z"
---

# Engel Build and Packaging

## Purpose

Produce the packaged Engel artifacts reproducibly, with the right things bundled and the right things intentionally left out.

## Trigger Conditions

- The user asks to build, rebuild, or package any exe or the APK.
- A packaged exe reports a "MISSING folder" and someone asks if that's a bug.
- A new vendored module needs a bundling decision.

## Build commands (repo root, D: tools only)

| Artifact | Command | Notes |
|---|---|---|
| `Engel.exe` | `powershell -ExecutionPolicy Bypass -File scripts/build_engel_main_exe.ps1` | PyInstaller, ~5-10 min |
| `EngelSuperSwarmHive3D.exe` | `scripts/build_engel_super_swarm_exe.ps1` | |
| Both approved packaged exes | `scripts/build_approved_packaged_artifacts.ps1` | Writes to **`build/staging/`, not `dist/`** |
| Android worker APK | `cd mobile/engel_remote_worker && "D:\b.WorkSpace\flutter_windows_3.41.9-stable\flutter\bin\flutter.bat" build apk --release` | Install with `tools\platform-tools\adb.exe -s <SERIAL> install -r mobile\engel_remote_worker\build\app\outputs\flutter-apk\app-release.apk` |

## Bundling rules for vendored modules

- Vendored `engel_*_main/` folders under ~50MB get bundled into the PyInstaller specs.
- `jarvis`, `octogent`, `engelcode`, and `engel_main` are too big and are **not** bundled — inside a packaged exe they surface as "MISSING folder", which is expected and fine for status routes. Don't "fix" it by bundling them.
- The Engel-Hermes bridge (`engel_agent_bridge.py`) never raises on a missing subtree; callers check `bridge_available()` / `bridge_missing_reason()`. That's why the Meeting Room launches from an exe without the agent subtree.
- New vendored project: drop the folder, write an `engel_<name>_runner.py` modeled on `engel_wave4_runner.py`, add routes, then decide bundling by size.

## Operating Instructions

- Everything runs from D: — Python at `D:\b.WorkSpace\Engel App\runtime\python310\python.exe`, Flutter at the `D:\b.WorkSpace\flutter_windows_...` SDK, ADB at `tools\platform-tools\adb.exe`. Hard-coded C: paths fail `tools/verify_engel_c_drive_cleanup.py`.
- After a build, smoke the exe's status routes before calling it good.
- Approved-artifact builds land in `build/staging/` for review; promotion out of staging is a human decision.

## Save Contract

- Record build outputs, durations, and any bundling decisions in `reports/codex_bridge/<NAME>.md`.
- Never change what gets bundled without noting it in the report and running the standard sweep.
- APK installs name the target serial explicitly (`-s ANDROID_WORKER_ALPHA` alpha / `-s ANDROID_WORKER_BETA` beta).
