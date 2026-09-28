---
name: "engel-android-worker-fleet"
description: "Dispatch, monitor, and provision the USB/LAN Android worker phone fleet (alpha + beta). Use whenever a request mentions android workers, phone jobs, ADB dispatch, worker queues, LAN pairing, or installing the Engel remote worker APK."
version: "1.0.1"
source: "claude-skill-creator"
created_at_utc: "2026-08-04T14:56:01Z"
updated_at_utc: "2026-08-04T16:19:54Z"
---

# Engel Android Worker Fleet

## Purpose

Run real jobs on the two USB-connected Android worker phones through `engel_adb_worker_manager.py`, keep their queues independent, and pair them over LAN when needed.

## The fleet

| Serial | Model | Worker ID |
|---|---|---|
| `ANDROID_WORKER_ALPHA` | Moto G Power 2025 | `android_worker_alpha` |
| `ANDROID_WORKER_BETA` | Moto G Fast | `android_worker_beta` |

Each phone runs an independent worker. The same role name on two phones means two separate queues — never assume a shared queue (see `memory/project_engel_android_workers.md`).

## Trigger Conditions

- The user asks about android workers, phone status, or worker queues.
- A job must be created, pushed, or its results pulled.
- A phone needs provisioning, LAN pairing, or an APK reinstall.

## Operating Instructions

- ADB lives at `D:\b.WorkSpace\Engel App\tools\platform-tools\adb.exe` (v37.0.0). `_resolve_adb()` refuses C:-rooted ADB from PATH — never point at a C: install.
- Status: `python engel_ai.py ask "android workers status"` (`render_adb_workers_status`).
- Create a job: `python engel_ai.py ask "create android job <worker_id>|<job_type>|<title>|<instructions>"` — payload is 4 pipe-separated fields. Supported job types: `summarize_text`, `draft_candidate_json`, `classify_text`, `extract_fields`.
- Push queued jobs to phones: `render_adb_workers_push_jobs`; pull finished results: `render_adb_workers_pull_results`; latest result: `render_adb_workers_latest_result`.
- Target a specific phone with `adb.exe -s <SERIAL>`.
- Git Bash mangles `/storage/...` device paths into `E:/Git/storage/...` — prefix any `adb push|shell` with `export MSYS_NO_PATHCONV=1`.

## LAN side

Start the server with `python engel_remote_worker_lan_pairing.py serve --lan` (default port 8765; omit `--lan` for localhost-only). `ALLOWED_WORKER_IDS = {alpha, beta, gamma}` — keep in sync with `_allowedWorkerIds` in `mobile/engel_remote_worker/lib/lan_pairing_client.dart`. Auto-pair via `render_adb_workers_lan_auto_pair`. The LAN server's contract is pairing/status only: `PAIRING STATUS ONLY - NO CONTROL GRANTED`, and worker returns are untrusted review only — never applied automatically.

## APK

- Rebuild: `cd mobile/engel_remote_worker && "D:\b.WorkSpace\flutter_windows_3.41.9-stable\flutter\bin\flutter.bat" build apk --release`
- Install: `tools\platform-tools\adb.exe -s <SERIAL> install -r mobile\engel_remote_worker\build\app\outputs\flutter-apk\app-release.apk`
- The Flutter app (`lib/main.dart`) is intentionally minimal: identity badge, assigned agent chip, transcript, pair row, status footer. Keep it that way.

## Save Contract

- Before behavior changes, read `engel_android_remote_worker_contract.py` and `mobile/engel_remote_worker/ENGEL_REMOTE_WORKER_ANDROID_CONTRACT_V1.md`.
- Job packets and results live under the worker's PC-side folders; include job IDs or receipt paths when reporting.
- No autonomous loops or background workers — jobs are created, pushed, and pulled on explicit request only.
