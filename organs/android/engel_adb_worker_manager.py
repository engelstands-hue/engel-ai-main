"""Engel ADB Worker Manager — manage Android remote workers via USB ADB.

Uses the Android Debug Bridge (adb.exe) to push job packets, pull results,
and check status on connected phones without requiring a running server.

Worker directory on phones: /sdcard/EngelRemoteWorker/<worker_id>/
ADB path: D:/b.WorkSpace/Engel App/tools/platform-tools/adb.exe
  (relocated from C:\\Users\\...\\Android\\Sdk on 2026-05-25; never reintroduce
   a C: drive ADB path — Engel-owned tool binaries live on D:)

Safety: ADB USB transport only. No WiFi ADB. No arbitrary shell execution.
File push/pull only. Read status files. No trusted-memory writes from results.
Results are candidate-only and require human review before applying.
"""
from __future__ import annotations

import engel_temp_policy  # noqa: F401
import json
import hashlib
import re
import shutil
import subprocess
import time
from pathlib import Path

from engel_project_paths import resolve_engel_app_root

_APP_ROOT = resolve_engel_app_root(__file__)


def _resolve_adb() -> Path:
    """Find adb.exe on D: first; never fall back to a C: install.

    Search order:
      1. D:\\b.WorkSpace\\Engel App\\tools\\platform-tools\\adb.exe (Engel-owned)
      2. Any adb on PATH that does NOT live under C:\\
      3. Final fallback returns the canonical D: path (will surface as
         "adb not found" via the subsequent subprocess call rather than
         silently invoking a C: copy)
    """
    engel_adb = _APP_ROOT / "tools" / "platform-tools" / "adb.exe"
    if engel_adb.is_file():
        return engel_adb
    on_path = shutil.which("adb")
    if on_path:
        candidate = Path(on_path)
        # Hard rule: refuse C:-rooted tool binaries for Engel work.
        try:
            anchor = candidate.resolve().anchor.lower()
        except Exception:
            anchor = ""
        if not anchor.startswith("c:"):
            return candidate
    return engel_adb


_ADB = _resolve_adb()
_SDCARD_ROOT = "/sdcard/EngelRemoteWorker"
_WORKERS_PC_ROOT = _APP_ROOT / "remote_workers"
_REMOTE_WORKER_APP_ID = "com.example.engel_remote_worker"
_REMOTE_WORKER_APP_FILES = "/data/user/0/com.example.engel_remote_worker/files"
_REMOTE_WORKER_EXTERNAL_FILES = "/storage/emulated/0/Android/data/com.example.engel_remote_worker/files"

# Known device serial → worker assignment.
# Each phone runs ONE distinct worker_id (see [[project-engel-android-workers]]
# memory): alpha on Moto G Power 2025, beta on Moto G Fast, gamma on Samsung
# A14. Same role name on two phones would create two independent queues which
# is confusing; Meeting Room + Flutter treat each phone as one Agent+Brain.
_DEVICE_WORKERS = {
    "ANDROID_WORKER_ALPHA": ["android_worker_alpha"],
    "ANDROID_WORKER_BETA": ["android_worker_beta"],
    "ANDROID_WORKER_GAMMA": ["android_worker_gamma"],
}
_DEVICE_LABELS = {
    "ANDROID_WORKER_ALPHA": "Moto G Power 2025 (8GB)",
    "ANDROID_WORKER_BETA": "Moto G Fast (3GB)",
    "ANDROID_WORKER_GAMMA": "Samsung Galaxy A14 5G",
}


def _adb(*args: str, serial: str | None = None, timeout: int = 10) -> subprocess.CompletedProcess:
    cmd = [str(_ADB)]
    if serial:
        cmd += ["-s", serial]
    cmd += list(args)
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def _connected_serials() -> list[str]:
    r = _adb("devices")
    serials = []
    for line in r.stdout.splitlines()[1:]:
        parts = line.strip().split()
        if len(parts) >= 2 and parts[1] == "device":
            serials.append(parts[0])
    return serials


def _safe_job_slug(title: str, limit: int = 40) -> str:
    """Return a Windows-safe slug for worker job IDs and folders."""
    slug = re.sub(r"[^a-z0-9_-]+", "_", str(title or "").lower())
    slug = re.sub(r"_+", "_", slug).strip("_-")
    return (slug[:limit].rstrip("_-") or "job")


def _worker_on_device(serial: str) -> list[str]:
    """List which workers exist on this device's sdcard."""
    r = _adb("shell", f"ls {_SDCARD_ROOT}/ 2>/dev/null", serial=serial)
    return [w.strip() for w in r.stdout.splitlines() if w.strip().startswith("android_worker_")]


def _pc_lan_ip() -> str:
    import socket

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
        sock.close()
        return ip
    except Exception:
        return "127.0.0.1"


def _write_temp_json(name: str, payload: dict) -> Path:
    temp_dir = _APP_ROOT / "runtime" / "meeting_room" / "lan_auto_pair"
    temp_dir.mkdir(parents=True, exist_ok=True)
    path = temp_dir / name
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def provision_lan_auto_pair(
    *,
    host: str,
    pairing_code: str,
    port: int = 8765,
    launch: bool = True,
) -> list[dict]:
    """Provision connected worker phones for LAN auto-pairing.

    This is setup/provisioning only. Job packets and results still move over
    the bounded LAN HTTP worker protocol; no WiFi ADB and no shell job
    execution are enabled.
    """
    results: list[dict] = []
    serials = _connected_serials() if _ADB.exists() and not str(_ADB).lower().startswith("c:") else []
    connection = {
        "host": host,
        "port": int(port),
        "pairing_code": pairing_code,
        "auto_pair": True,
    }
    connection_path = _write_temp_json("worker_connection.json", connection)
    temp_paths = [connection_path]

    try:
        for serial in serials:
            for worker_id in _DEVICE_WORKERS.get(serial, []):
                label = _DEVICE_LABELS.get(serial, serial)
                identity = {
                    "worker_id": worker_id,
                    "worker_name": "Android Worker " + worker_id.rsplit("_", 1)[-1].title(),
                    "phone_model": label,
                    "controls_engel": False,
                    "discord_on_phone": False,
                    "model_runtime": False,
                }
                try:
                    from engel_android_worker_agent_brain import identity_overlay

                    identity.update({k: v for k, v in identity_overlay(worker_id).items() if v is not None})
                except Exception:
                    pass
                identity_path = _write_temp_json(f"{worker_id}_identity.json", identity)
                temp_paths.append(identity_path)
                record = {
                    "serial": serial,
                    "worker_id": worker_id,
                    "label": label,
                    "host": host,
                    "port": int(port),
                    "launched": False,
                    "config_ok": False,
                    "internal_config_ok": False,
                    "ok": False,
                    "steps": [],
                }

                for local, remote_name in (
                    (identity_path, "worker_identity.json"),
                    (connection_path, "worker_connection.json"),
                ):
                    push = _adb("push", str(local), f"/data/local/tmp/{remote_name}", serial=serial, timeout=20)
                    record["steps"].append({"push_tmp": remote_name, "rc": push.returncode})
                    mkdir = _adb("shell", f"run-as {_REMOTE_WORKER_APP_ID} mkdir -p files", serial=serial, timeout=10)
                    record["steps"].append({"mkdir_internal": remote_name, "rc": mkdir.returncode})
                    copy = _adb("shell", f"run-as {_REMOTE_WORKER_APP_ID} cp /data/local/tmp/{remote_name} files/{remote_name}", serial=serial, timeout=10)
                    record["steps"].append({"copy_internal": remote_name, "rc": copy.returncode})
                    _adb("shell", f"mkdir -p {_REMOTE_WORKER_EXTERNAL_FILES}", serial=serial, timeout=10)
                    ext = _adb("push", str(local), f"{_REMOTE_WORKER_EXTERNAL_FILES}/{remote_name}", serial=serial, timeout=20)
                    record["steps"].append({"push_external": remote_name, "rc": ext.returncode})

                _adb("shell", f"am force-stop {_REMOTE_WORKER_APP_ID}", serial=serial, timeout=10)
                if launch:
                    start = _adb("shell", f"am start -n {_REMOTE_WORKER_APP_ID}/.MainActivity", serial=serial, timeout=10)
                    record["launched"] = start.returncode == 0
                    record["steps"].append({"launch": "MainActivity", "rc": start.returncode})
                external_names = {
                    step.get("push_external"): step.get("rc")
                    for step in record["steps"]
                    if "push_external" in step
                }
                internal_names = {
                    step.get("copy_internal"): step.get("rc")
                    for step in record["steps"]
                    if "copy_internal" in step
                }
                record["config_ok"] = (
                    external_names.get("worker_identity.json") == 0
                    and external_names.get("worker_connection.json") == 0
                )
                record["internal_config_ok"] = (
                    internal_names.get("worker_identity.json") == 0
                    and internal_names.get("worker_connection.json") == 0
                )
                # Release Android apps are not debuggable, so `run-as` is
                # expected to fail. The Flutter worker reads the external
                # app-scoped files first, so those pushes are the real gate.
                record["ok"] = record["config_ok"] and (record["launched"] if launch else True)
                results.append(record)
    finally:
        for path in temp_paths:
            try:
                path.unlink()
            except FileNotFoundError:
                pass
    return results


def render_adb_workers_lan_auto_pair(payload: str = "") -> str:
    parts = [part.strip() for part in str(payload or "").split("|")]
    host = parts[0] if parts and parts[0] else _pc_lan_ip()
    code = parts[1] if len(parts) > 1 else ""
    port = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 8765
    if not code:
        try:
            import engel_remote_worker_lan_pairing as _lan
            session = _lan.create_pairing_session()
            code = session.pairing_code
        except Exception as exc:
            return "# Engel ADB LAN Auto Pair\n\nCould not create pairing token: " + str(exc)
    rows = provision_lan_auto_pair(host=host, pairing_code=code, port=port, launch=True)
    lines = [
        "# Engel ADB LAN Auto Pair",
        "",
        f"Host: `{host}`",
        f"Port: `{port}`",
        "Pairing code: generated/pushed to app storage",
        "",
    ]
    if not rows:
        lines.append("No connected known worker phones found.")
    for row in rows:
        mark = "PASS" if row.get("ok") else "FAIL"
        lines.append(f"- {mark} {row.get('label')} `{row.get('worker_id')}` launched={row.get('launched')}")
    lines += [
        "",
        "Transport: WiFi/LAN worker HTTP polling.",
        "ADB is used only to provision app-scoped identity/connection files and launch the worker app.",
    ]
    return "\n".join(lines)


def _read_remote_json(serial: str, remote_path: str) -> dict:
    r = _adb("shell", f"cat {remote_path} 2>/dev/null", serial=serial)
    if r.returncode != 0 or not r.stdout.strip():
        return {}
    try:
        return json.loads(r.stdout)
    except Exception:
        return {}


def _list_remote_dir(serial: str, remote_path: str) -> list[str]:
    r = _adb("shell", f"ls {remote_path}/ 2>/dev/null", serial=serial)
    return [f.strip() for f in r.stdout.splitlines() if f.strip()]


def render_adb_workers_status() -> str:
    """Show all ADB-connected devices and their worker status."""
    if not _ADB.exists():
        return f"# ADB Worker Manager\n\nadb not found: {_ADB}"

    serials = _connected_serials()
    lines = [
        "# Engel ADB Worker Manager — Status",
        "",
        f"ADB:      {_ADB}",
        f"Devices:  {len(serials)} connected via USB",
        "Mode:     each phone = dedicated Agent + Brain (phone does not control Engel)",
        "Discord:  desk bots pipe through Engel; Discord APK never on phones",
        "",
    ]
    try:
        from engel_android_worker_agent_brain import binding_for_serial, binding_for_worker
    except Exception:
        binding_for_serial = None  # type: ignore[assignment]
        binding_for_worker = None  # type: ignore[assignment]
    try:
        from engel_discord_android_worker_pipe import pipe_colony_snapshot

        snap = pipe_colony_snapshot()
        lines += [
            f"Discord pipe waiting assignments: {snap.get('approved_discord_assignments', 0)}",
            f"Discord pipe pending replies:     {snap.get('pending_discord_replies', 0)}",
            "",
        ]
    except Exception:
        pass

    if not serials:
        lines += [
            "No ADB devices connected.",
            "Connect phones via USB and enable USB debugging.",
        ]
        return "\n".join(lines)

    for serial in serials:
        label = _DEVICE_LABELS.get(serial, serial)
        mapped = list(_DEVICE_WORKERS.get(serial, []))
        workers = _worker_on_device(serial) or mapped
        lines += [f"## {label}  [{serial}]", f"  Workers: {', '.join(workers) or 'none'}"]
        if binding_for_serial is not None:
            bind = binding_for_serial(serial) or (
                binding_for_worker(mapped[0]) if mapped and binding_for_worker else {}
            )
            if bind:
                lines += [
                    f"  Agent:   {bind.get('agent_name') or '(unbound)'}",
                    f"  Brain:   {bind.get('brain_label') or '(unbound)'} [{bind.get('brain_id') or '?'}]",
                    f"  Lane:    {bind.get('brain_lane') or '(unbound)'}",
                ]

        for wid in workers:
            base = f"{_SDCARD_ROOT}/{wid}"
            jobs = _list_remote_dir(serial, f"{base}/jobs")
            real_jobs = [j for j in jobs if j.endswith(".json") and not j.endswith(".gitkeep")]
            outbox = _list_remote_dir(serial, f"{base}/outbox")
            real_results = [r for r in outbox if r.endswith(".json")]
            status_files = _list_remote_dir(serial, f"{base}/status")
            lines += [
                f"",
                f"  [{wid}]",
                f"    Jobs pending:   {len(real_jobs)}",
                f"    Results ready:  {len(real_results)}",
                f"    Status files:   {len(status_files)}",
            ]
            if real_jobs:
                for j in real_jobs[:2]:
                    lines.append(f"    - job: {j[:60]}")
            if real_results:
                for r in real_results[:2]:
                    lines.append(f"    - result: {r[:60]}")
        lines.append("")

    lines += [
        "Commands:",
        "  engel adb workers pull results    -- pull all results to remote_workers/",
        "  engel adb workers push job        -- push pending PC jobs to phones",
        "  engel adb workers result          -- read latest result content",
        "  engel discord android pipe status -- Discord desk <-> phone pipe (no Discord on phone)",
    ]
    return "\n".join(lines)


def render_adb_workers_pull_results() -> str:
    """Pull all worker results from connected phones to remote_workers/ on PC."""
    serials = _connected_serials()
    if not serials:
        return "# ADB Pull Results\n\nNo devices connected."

    lines = ["# Engel ADB — Pull Results", ""]
    pulled_total = 0

    for serial in serials:
        label = _DEVICE_LABELS.get(serial, serial)
        workers = _worker_on_device(serial)
        lines.append(f"## {label}")

        for wid in workers:
            base = f"{_SDCARD_ROOT}/{wid}"
            # Pull outbox, status, receipts, logs
            for folder in ("outbox", "status", "receipts", "logs"):
                remote = f"{base}/{folder}/"
                local = _WORKERS_PC_ROOT / wid / folder
                local.mkdir(parents=True, exist_ok=True)
                # Check what's there
                files = [f for f in _list_remote_dir(serial, f"{base}/{folder}") if f.endswith(".json") or f.endswith(".txt") or f.endswith(".md")]
                if not files:
                    continue
                for fname in files:
                    remote_file = f"{base}/{folder}/{fname}"
                    local_file = local / fname
                    if local_file.exists():
                        lines.append(f"  SKIP (exists): {wid}/{folder}/{fname}")
                        continue
                    r = _adb("pull", remote_file, str(local_file), serial=serial, timeout=30)
                    if r.returncode == 0:
                        lines.append(f"  PULLED: {wid}/{folder}/{fname}")
                        pulled_total += 1
                    else:
                        lines.append(f"  FAIL: {wid}/{folder}/{fname}  — {r.stderr.strip()[:60]}")

    lines += [
        "",
        f"Total files pulled: {pulled_total}",
        "",
        "Results are candidate-only. Review before applying.",
        "View: engel adb workers result",
    ]
    return "\n".join(lines)


def render_adb_workers_push_jobs() -> str:
    """Push pending PC-side job packets to the appropriate phone workers via ADB."""
    serials = _connected_serials()
    if not serials:
        return "# ADB Push Jobs\n\nNo devices connected."

    lines = ["# Engel ADB — Push Jobs", ""]
    pushed_total = 0

    for serial in serials:
        label = _DEVICE_LABELS.get(serial, serial)
        workers = _worker_on_device(serial)
        lines.append(f"## {label}")

        for wid in workers:
            pc_jobs_dir = _WORKERS_PC_ROOT / wid / "jobs"
            if not pc_jobs_dir.exists():
                continue
            job_files = [f for f in pc_jobs_dir.iterdir() if f.suffix == ".json" and f.name != ".gitkeep"]
            if not job_files:
                lines.append(f"  [{wid}] No pending jobs on PC.")
                continue

            base = f"{_SDCARD_ROOT}/{wid}"
            # Check what's already on device
            existing = set(_list_remote_dir(serial, f"{base}/jobs"))

            for job_file in sorted(job_files):
                if job_file.name in existing:
                    lines.append(f"  SKIP (exists): {wid}/jobs/{job_file.name}")
                    continue
                # Validate it's a real job (not template)
                try:
                    data = json.loads(job_file.read_text(encoding="utf-8"))
                    if data.get("job_template") is True:
                        lines.append(f"  SKIP (template): {job_file.name}")
                        continue
                    if data.get("real_job") is not True:
                        lines.append(f"  SKIP (not real_job): {job_file.name}")
                        continue
                except Exception:
                    lines.append(f"  SKIP (invalid JSON): {job_file.name}")
                    continue

                # Push job file
                remote = f"{base}/jobs/{job_file.name}"
                r = _adb("push", str(job_file), remote, serial=serial, timeout=30)
                if r.returncode == 0:
                    lines.append(f"  PUSHED: {wid}/jobs/{job_file.name}")
                    pushed_total += 1

                    # Also push input files if they exist
                    input_files = data.get("input_files", [])
                    for inp in input_files:
                        local_inp = _WORKERS_PC_ROOT / wid / inp.replace("\\", "/")
                        if local_inp.exists():
                            remote_inp = f"{base}/{inp.replace(chr(92), '/')}"
                            # Ensure remote directory exists
                            remote_dir = remote_inp.rsplit("/", 1)[0]
                            _adb("shell", f"mkdir -p {remote_dir}", serial=serial)
                            ri = _adb("push", str(local_inp), remote_inp, serial=serial, timeout=30)
                            if ri.returncode == 0:
                                lines.append(f"  PUSHED input: {inp}")
                else:
                    lines.append(f"  FAIL: {job_file.name} — {r.stderr.strip()[:60]}")

    lines += [
        "",
        f"Total files pushed: {pushed_total}",
        "",
        "Now open the Engel Remote Worker app on the phone to process the job.",
        "Then pull results: engel adb workers pull results",
    ]
    return "\n".join(lines)


def render_adb_workers_latest_result() -> str:
    """Read and display the latest pulled worker result."""
    lines = ["# Engel ADB — Latest Result", ""]

    all_results: list[tuple[float, Path]] = []
    for wid_dir in _WORKERS_PC_ROOT.iterdir():
        if not wid_dir.is_dir() or not wid_dir.name.startswith("android_worker_"):
            continue
        outbox = wid_dir / "outbox"
        if not outbox.exists():
            continue
        for f in outbox.iterdir():
            if f.suffix == ".json":
                all_results.append((f.stat().st_mtime, f))

    if not all_results:
        lines += [
            "No results pulled yet.",
            "Run: engel adb workers pull results",
        ]
        return "\n".join(lines)

    all_results.sort(reverse=True)
    _, latest = all_results[0]
    lines += [
        f"File: {latest.relative_to(_WORKERS_PC_ROOT)}",
        f"Time: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(latest.stat().st_mtime))}",
        "",
    ]
    try:
        data = json.loads(latest.read_text(encoding="utf-8"))
        summary = data.get("summary") or data.get("result_summary") or data.get("output")
        if summary:
            lines += ["Summary:", str(summary)[:1000], ""]
        # Show key fields
        for key in ("job_id", "job_status", "worker_id", "completed_at"):
            if key in data:
                lines.append(f"{key}: {data[key]}")
    except Exception as exc:
        lines.append(f"Read error: {exc}")

    lines += ["", f"Full file: {latest}"]
    return "\n".join(lines)


def render_adb_provision_worker(payload: str = "") -> str:
    """Create worker directory structure on a connected phone.

    payload: optional 'serial' or 'serial worker_id' — defaults to all
    unprovisioned workers in _DEVICE_WORKERS.
    """
    serials = _connected_serials()
    if not serials:
        return "# ADB Provision Worker\n\nNo devices connected."

    parts = (payload or "").strip().split()
    target_serial = parts[0] if parts else None
    target_wid = parts[1] if len(parts) > 1 else None

    if target_serial and target_serial not in serials:
        return f"# ADB Provision Worker\n\nDevice {target_serial} not connected.\nConnected: {', '.join(serials)}"

    _SUBDIRS = ("jobs", "inbox", "outbox", "status", "receipts", "logs")

    lines = ["# Engel ADB -- Provision Worker", ""]
    created_total = 0

    for serial in serials:
        if target_serial and serial != target_serial:
            continue
        label = _DEVICE_LABELS.get(serial, serial)
        assigned = _DEVICE_WORKERS.get(serial, [])
        lines.append(f"## {label}  [{serial}]")

        for wid in assigned:
            if target_wid and wid != target_wid:
                continue
            base = f"{_SDCARD_ROOT}/{wid}"
            # Check if already provisioned
            existing = _list_remote_dir(serial, _SDCARD_ROOT)
            if wid in existing:
                lines.append(f"  [{wid}] Already exists -- skipping top-level mkdir")
            else:
                r = _adb("shell", f"mkdir -p {base}", serial=serial)
                if r.returncode != 0:
                    lines.append(f"  [{wid}] FAIL mkdir base: {r.stderr.strip()[:60]}")
                    continue
                lines.append(f"  [{wid}] Created base: {base}")

            for sub in _SUBDIRS:
                remote_sub = f"{base}/{sub}"
                r = _adb("shell", f"mkdir -p {remote_sub}", serial=serial)
                if r.returncode == 0:
                    lines.append(f"    + {sub}/")
                    created_total += 1
                else:
                    lines.append(f"    FAIL {sub}/: {r.stderr.strip()[:40]}")

            # Write a .gitkeep marker so ls shows the dirs as non-empty
            for sub in ("jobs", "outbox"):
                _adb("shell", f"touch {base}/{sub}/.gitkeep", serial=serial)

            # Write worker identity file
            identity = json.dumps({
                "worker_id": wid,
                "device_serial": serial,
                "device_label": _DEVICE_LABELS.get(serial, serial),
                "provisioned_by": "engel_adb_worker_manager",
                "protocol": "manual_transfer_v1",
            }, indent=2)
            _adb("shell", f"echo '{identity}' > {base}/worker_identity.json", serial=serial)
            lines.append(f"    + worker_identity.json")

            # Also create local PC mirror dirs
            for sub in _SUBDIRS:
                local = _WORKERS_PC_ROOT / wid / sub
                local.mkdir(parents=True, exist_ok=True)

            lines.append(f"  [{wid}] Provisioned OK")

    lines += [
        "",
        f"Directories created: {created_total}",
        "",
        "Next: push a job with:  engel adb workers push jobs",
        "Then open Engel Remote Worker app on the phone to execute.",
    ]
    return "\n".join(lines)


# ── Standard safety block (shared across all job types) ──────────────────────
_SAFETY_BLOCK = {
    "android_remote_worker_not_queen": True,
    "approval_required_for_any_write": True,
    "assignment_mode": "manual_transfer_v1",
    "assignment_route": "communication_queen_only",
    "assignment_safety": {
        "Hermes remains rejected / do not install on this computer": True,
        "candidate_outputs_only": True,
        "no_android_runtime_execution_from_engel": True,
        "no_completion_without_returned_packet": True,
        "no_fake_progress": True,
        "no_fake_returned_result": True,
        "no_fake_returned_status": True,
        "no_phone_connection": True,
        "no_worker_job_execution_from_engel": True,
    },
    "assignment_status": "prepared_for_manual_transfer",
    "autonomy_scope": "assigned_job_sandbox_only",
    "blocked_actions": [
        "access paths outside worker folder unless listed in input_files",
        "adb", "android_runtime_execution", "cloud_sync",
        "delete logs", "delete receipts", "download files", "download models",
        "execute arbitrary shell from job packet", "expose SSH",
        "fake_progress", "fake_returned_result", "fake_returned_status",
        "hermes_runtime_rejected_do_not_install", "impersonate approval",
        "install packages", "live_connection_server", "llama_cpp_runtime_blocked",
        "mark memory promoted", "mark output trusted", "mark patch applied",
        "mark_completed_without_returned_packet", "model_runtime",
        "mutate job packet after receipt except status/result fields",
        "ollama_runtime_blocked", "patch_apply", "phone_connection",
        "provider_network", "route_mutation", "run background daemon",
        "schedule boot startup", "source_mutation", "ssh",
        "start network server", "trusted_memory_write",
        "worker_job_execution_from_engel",
    ],
    "created_by": "engel",
    "job_template": False,
    "log_required": True,
    "manual_transfer_required": True,
    "max_input_size": 200000,
    "max_output_size": 200000,
    "max_runtime_hint": 900,
    "model_runtime": False,
    "offline_only": True,
    "on_device_autonomy_allowed": True,
    "patch_apply": False,
    "provider_network": False,
    "real_job": True,
    "receipt_required": True,
    "requires_human_review": True,
    "route_mutation": False,
    "routed_by": "communication_queen",
    "source_mutation": False,
    "trusted_memory_write": False,
}

_JOB_TYPE_TEMPLATES: dict[str, dict] = {
    "summarize_text": {
        "allowed_actions": [
            "create bullet summary",
            "create research note draft",
            "flag risky instructions",
            "read assigned input file",
            "save candidate markdown",
            "save receipt",
            "save validation notes",
        ],
        "expected_outputs": [
            "candidate markdown summary",
            "worker status packet",
            "worker result packet",
            "worker log",
            "worker receipt",
        ],
    },
    "draft_candidate_json": {
        "allowed_actions": [
            "extract bounded fields",
            "read assigned local note listed in the job packet",
            "reject unknown or unsafe fields",
            "save candidate JSON",
            "save receipt",
            "save validation notes",
            "validate simple JSON structure",
        ],
        "expected_outputs": [
            "candidate JSON file",
            "validation notes (text)",
            "worker status packet",
            "worker result packet",
            "worker log",
            "worker receipt",
        ],
    },
    "classify_text": {
        "allowed_actions": [
            "apply provided label set only",
            "read assigned input file",
            "save candidate classification",
            "save receipt",
            "save validation notes",
        ],
        "expected_outputs": [
            "candidate classification result",
            "worker status packet",
            "worker result packet",
            "worker log",
            "worker receipt",
        ],
    },
    "extract_fields": {
        "allowed_actions": [
            "extract listed fields only",
            "read assigned input file",
            "reject unlisted fields",
            "save candidate extraction",
            "save receipt",
        ],
        "expected_outputs": [
            "candidate field extraction",
            "worker status packet",
            "worker result packet",
            "worker log",
            "worker receipt",
        ],
    },
}

_WORKER_NAMES = {
    "android_worker_alpha": "Android Worker Alpha",
    "android_worker_beta": "Android Worker Beta",
    "android_worker_gamma": "Android Worker Gamma",
}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def render_adb_workers_jobs() -> str:
    """Show all PC-side job packets and their status across all workers."""
    lines = ["# Engel ADB -- Worker Job Dashboard", ""]

    any_found = False
    for wid_dir in sorted(_WORKERS_PC_ROOT.iterdir()):
        if not wid_dir.is_dir() or not wid_dir.name.startswith("android_worker_"):
            continue
        any_found = True

        jobs_dir = wid_dir / "jobs"
        outbox_dir = wid_dir / "outbox"
        completed_ids: set[str] = set()
        if outbox_dir.exists():
            for f in outbox_dir.iterdir():
                if f.suffix == ".json":
                    # Extract job_id from result filename prefix
                    completed_ids.add(f.stem.rsplit("_result", 1)[0])

        lines.append(f"## {wid_dir.name}")
        job_count = 0
        if jobs_dir.exists():
            for job_file in sorted(jobs_dir.iterdir()):
                if job_file.suffix != ".json" or job_file.name == ".gitkeep":
                    continue
                job_count += 1
                try:
                    data = json.loads(job_file.read_text(encoding="utf-8"))
                    jid = data.get("job_id", job_file.stem)
                    jtype = data.get("job_type", "?")
                    jtitle = data.get("job_title", jid[-40:])
                    done = jid in completed_ids or data.get("job_status") == "completed"
                    state = "DONE" if done else "PENDING"
                    lines.append(f"  [{state}] {jtitle[:60]}")
                    lines.append(f"         type={jtype}  id={jid[-40:]}")
                except Exception:
                    lines.append(f"  [?] {job_file.name}")
        if job_count == 0:
            lines.append("  (no jobs)")
        lines.append("")

    if not any_found:
        lines.append("No worker directories found in remote_workers/")

    lines += [
        "Create a job:   engel adb workers create job <worker_id>|<job_type>|<title>|<instructions>",
        "Push jobs:      engel adb workers push jobs",
        "Pull results:   engel adb workers pull results",
    ]
    return "\n".join(lines)


def render_adb_wifi_connect(payload: str = "") -> str:
    """Enable ADB over WiFi for a phone (tcpip 5555 + adb connect IP:5555).
    Payload: IP or SERIAL|IP:port   (e.g. 192.168.1.42 or ANDROID_WORKER_ALPHA|192.168.1.42:5555)
    Safe: only uses resolved adb, no C: paths.
    """
    try:
        adb = _resolve_adb()
        parts = [p.strip() for p in str(payload or "").split("|") if p.strip()]
        if not parts:
            return "Usage: adb wifi connect <IP> or <SERIAL|IP:5555>\nExample: 192.168.1.105 or ANDROID_WORKER_ALPHA|192.168.1.105:5555"
        target = parts[0]
        if len(parts) > 1:
            serial = target
            ipport = parts[1]
            # first tcpip on serial
            _run_adb([adb, "-s", serial, "tcpip", "5555"], timeout=10)
            res = _run_adb([adb, "connect", ipport], timeout=15)
        else:
            ipport = target if ":" in target else target + ":5555"
            # assume already paired or use first device
            _run_adb([adb, "tcpip", "5555"], timeout=10)
            res = _run_adb([adb, "connect", ipport], timeout=15)
        return f"ADB WiFi connect result for {ipport}:\n{res}"
    except Exception as exc:
        return "ADB WiFi connect (safe): " + str(exc)


def render_adb_create_job(payload: str = "") -> str:
    """Create a job packet for a phone worker.

    payload format: worker_id|job_type|title|instructions
    Supported job_types: summarize_text, draft_candidate_json, classify_text, extract_fields
    """
    if not payload.strip():
        types = ", ".join(_JOB_TYPE_TEMPLATES.keys())
        return (
            "# Engel ADB -- Create Job\n\n"
            "Usage: engel adb workers create job <worker_id>|<job_type>|<title>|<instructions>\n\n"
            f"Job types: {types}\n\n"
            "Example:\n"
            "  android_worker_alpha|summarize_text|Summarize system report|"
            "Read the assigned file and produce a bullet-point summary of key findings."
        )

    parts = payload.split("|", 3)
    if len(parts) < 4:
        return (
            "# Engel ADB -- Create Job\n\n"
            f"Error: need 4 pipe-separated fields, got {len(parts)}.\n"
            "Format: worker_id|job_type|title|instructions"
        )

    worker_id, job_type, title, instructions = [p.strip() for p in parts]

    if job_type not in _JOB_TYPE_TEMPLATES:
        types = ", ".join(_JOB_TYPE_TEMPLATES.keys())
        return f"# Engel ADB -- Create Job\n\nUnknown job_type '{job_type}'.\nSupported: {types}"

    # Generate job_id
    ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    slug = _safe_job_slug(title)
    base_job_id = f"{ts}_{worker_id}_{job_type}_{slug}"
    job_id = base_job_id
    jobs_dir = _WORKERS_PC_ROOT / worker_id / "jobs"
    suffix = 2
    while (
        (jobs_dir / f"{job_id}.json").exists()
        or (_WORKERS_PC_ROOT / worker_id / "inbox" / "assigned_inputs" / job_id).exists()
    ):
        job_id = f"{base_job_id}_{suffix}"
        suffix += 1

    template = _JOB_TYPE_TEMPLATES[job_type]
    input_rel = Path("inbox") / "assigned_inputs" / job_id / "instructions.txt"
    input_path = _WORKERS_PC_ROOT / worker_id / input_rel
    input_path.parent.mkdir(parents=True, exist_ok=True)
    input_path.write_text(
        "\n".join([
            f"# {title}",
            "",
            f"Worker: {worker_id}",
            f"Job type: {job_type}",
            "",
            "Instructions:",
            instructions,
            "",
        ]),
        encoding="utf-8",
    )
    source_rel = Path("remote_workers") / worker_id / input_rel
    packet = {
        **_SAFETY_BLOCK,
        **template,
        "input_files": [str(input_rel)],
        "source_input": {
            "copied_for_manual_transfer": True,
            "project_path": str(source_rel),
            "sha256": _sha256_file(input_path),
            "size_bytes": input_path.stat().st_size,
            "staged_worker_path": str(source_rel),
        },
        "assigned_worker_id": worker_id,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "instructions": instructions,
        "job_id": job_id,
        "job_title": title,
        "job_type": job_type,
        "priority": "normal",
        "status": "prepared_for_manual_transfer",
        "worker_name": _WORKER_NAMES.get(worker_id, worker_id),
    }

    # Write to PC jobs dir
    jobs_dir.mkdir(parents=True, exist_ok=True)
    fname = f"{job_id}.json"
    out_path = jobs_dir / fname
    out_path.write_text(json.dumps(packet, indent=2), encoding="utf-8")

    return "\n".join([
        "# Engel ADB -- Create Job",
        "",
        f"Created: {fname}",
        f"Worker:  {worker_id}",
        f"Type:    {job_type}",
        f"Title:   {title}",
        f"Path:    {out_path}",
        "",
        "Next: push to phone with:  engel adb workers push jobs",
        "Then open Engel Remote Worker app on the phone to execute.",
    ])
