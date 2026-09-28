#!/usr/bin/env python3
"""Run Engel Main backend auto-fix agents.

The agents in this file perform bounded local repairs for Engel-owned backend
lanes. They do not delete operator work, do not write to C:, and record every
action in reports and persistent memory.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.error
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime"
REPORT_DIR = ROOT / "reports" / "backend_autofix_agents"
MEMORY_DIR = ROOT / "memory"
LATEST_RECEIPT = RUNTIME / "backend_autofix_agents_latest.json"
LATEST_MEMORY = MEMORY_DIR / "ENGEL_BACKEND_AUTOFIX_AGENTS_20260623.md"
MEETING_HEALTH_URL = "http://127.0.0.1:8790/health"
HASH_FIELDS = {"receipt_sha256", "receipt_payload_sha256"}


def utc_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat()


def stamp() -> str:
    return _dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def assert_safe_write_path(path: Path) -> None:
    resolved = str(path.resolve())
    if resolved.upper().startswith("C:\\"):
        raise RuntimeError(f"Refusing C: drive write: {resolved}")
    root = str(ROOT.resolve()).upper()
    if not resolved.upper().startswith(root):
        raise RuntimeError(f"Refusing write outside Engel App root: {resolved}")


def ensure_dir(path: Path, files_changed: list[str]) -> None:
    assert_safe_write_path(path)
    path.mkdir(parents=True, exist_ok=True)
    marker = path / ".keep"
    if not marker.exists():
        marker.write_text("Engel backend auto-fix managed directory.\n", encoding="utf-8")
        files_changed.append(str(marker))


def write_json(path: Path, payload: dict) -> None:
    assert_safe_write_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def canonical_payload_sha256(payload: dict) -> str:
    cleaned = json.loads(json.dumps(payload, sort_keys=True))
    for key in HASH_FIELDS:
        cleaned.pop(key, None)
    encoded = json.dumps(cleaned, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest().upper()


def command_result(
    executable: str,
    args: list[str],
    timeout: int = 45,
    extra_env: dict[str, str] | None = None,
) -> dict:
    env = os.environ.copy()
    env.update(
        {
            "ENGEL_APP_ROOT": str(ROOT),
            "TEMP": str(RUNTIME / "temp"),
            "TMP": str(RUNTIME / "tmp"),
            "TMPDIR": str(RUNTIME / "tmp"),
            "CARGO_HOME": str(RUNTIME / "cargo-home"),
        }
    )
    if extra_env:
        env.update(extra_env)
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    started = time.monotonic()
    try:
        result = subprocess.run(
            [executable, *args],
            cwd=str(ROOT),
            env=env,
            text=True,
            capture_output=True,
            timeout=timeout,
            creationflags=flags,
        )
        return {
            "command": " ".join([executable, *args]),
            "exit_code": result.returncode,
            "elapsed_ms": int((time.monotonic() - started) * 1000),
            "stdout_tail": result.stdout[-4000:],
            "stderr_tail": result.stderr[-4000:],
        }
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        return {
            "command": " ".join([executable, *args]),
            "exit_code": None,
            "elapsed_ms": int((time.monotonic() - started) * 1000),
            "timeout": timeout,
            "stdout_tail": stdout[-4000:],
            "stderr_tail": stderr[-4000:],
        }
    except Exception as exc:
        return {
            "command": " ".join([executable, *args]),
            "exit_code": None,
            "elapsed_ms": int((time.monotonic() - started) * 1000),
            "error": repr(exc),
        }


def health_check() -> tuple[bool, dict]:
    try:
        with urllib.request.urlopen(MEETING_HEALTH_URL, timeout=3) as response:
            body = response.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            payload = {"body": body[-1000:]}
        ok = bool(payload.get("ok") is True or payload.get("status") in {"running", "ok"})
        return ok, payload
    except (OSError, urllib.error.URLError) as exc:
        return False, {"error": repr(exc)}


def meeting_room_server_agent(files_changed: list[str]) -> dict:
    actions: list[dict] = []
    before_ok, before = health_check()
    repaired = False
    if before_ok:
        actions.append({"type": "health_check", "result": "already_running"})
    else:
        script = ROOT / "tools" / "start_engel_meeting_room_lan_server.ps1"
        if script.exists():
            result = command_result(
                "powershell.exe",
                [
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(script),
                ],
                timeout=35,
            )
            actions.append({"type": "start_meeting_room_server", "result": result})
            repaired = result.get("exit_code") == 0
            time.sleep(2)
        else:
            actions.append(
                {
                    "type": "missing_start_script",
                    "path": str(script),
                    "severity": "error",
                }
            )
    after_ok, after = health_check()
    return {
        "id": "meeting_room_server_agent",
        "name": "Meeting Room Server Agent",
        "goal": "Keep Engel Meeting Room HTTP server reachable on 127.0.0.1:8790.",
        "status": "ok" if after_ok else "needs_attention",
        "repaired": repaired and after_ok,
        "before": before,
        "after": after,
        "actions": actions,
    }


def connector_profile_agent(files_changed: list[str]) -> dict:
    dirs = [
        RUNTIME / "connector_profiles" / "channels",
        RUNTIME / "connector_profiles" / "integrations",
        RUNTIME / "browser_control" / "channels",
        RUNTIME / "browser_control" / "integrations",
        RUNTIME / "standalone_connection_requests" / "channels",
        RUNTIME / "standalone_connection_requests" / "integrations",
    ]
    for directory in dirs:
        ensure_dir(directory, files_changed)

    malformed: list[dict] = []
    json_roots = [RUNTIME / "connector_profiles", RUNTIME / "browser_control"]
    for root in json_roots:
        if not root.exists():
            continue
        for path in root.rglob("*.json"):
            try:
                json.loads(path.read_text(encoding="utf-8"))
            except Exception as exc:
                malformed.append({"path": str(path), "error": repr(exc)})

    report_path = RUNTIME / "connector_profiles" / "autofix_scan.json"
    write_json(
        report_path,
        {
            "schema": "engel_connector_profile_scan_v1",
            "created_at_utc": utc_now(),
            "malformed_count": len(malformed),
            "malformed": malformed,
            "managed_roots": [str(p) for p in dirs],
        },
    )
    files_changed.append(str(report_path))
    return {
        "id": "connector_profile_agent",
        "name": "Connector Profile Agent",
        "goal": "Make connector/browser-control lanes writable and JSON-safe.",
        "status": "ok" if not malformed else "needs_attention",
        "directories_ready": [str(p) for p in dirs],
        "malformed_json": malformed,
        "actions": [{"type": "write_scan", "path": str(report_path)}],
    }


def runtime_cleanup_agent(files_changed: list[str]) -> dict:
    dirs = [
        RUNTIME / "temp",
        RUNTIME / "tmp",
        RUNTIME / "backend_autofix_agents",
        REPORT_DIR,
        MEMORY_DIR,
        MEMORY_DIR / "notes",
        MEMORY_DIR / "personality",
    ]
    for directory in dirs:
        ensure_dir(directory, files_changed)
    state_path = RUNTIME / "backend_autofix_agents" / "runtime_state.json"
    state = {
        "schema": "engel_backend_runtime_state_v1",
        "created_at_utc": utc_now(),
        "temp": str(RUNTIME / "temp"),
        "tmp": str(RUNTIME / "tmp"),
        "report_dir": str(REPORT_DIR),
        "memory_dir": str(MEMORY_DIR),
        "c_drive_write_allowed": False,
    }
    write_json(state_path, state)
    files_changed.append(str(state_path))
    return {
        "id": "runtime_cleanup_agent",
        "name": "Runtime Cleanup Agent",
        "goal": "Create missing local runtime/report/memory roots without deleting user work.",
        "status": "ok",
        "directories_ready": [str(p) for p in dirs],
        "actions": [{"type": "write_runtime_state", "path": str(state_path)}],
    }


def rust_backend_agent(files_changed: list[str]) -> dict:
    candidates = [
        RUNTIME / "temp" / "engel-rust-rewrite" / "cargo-target" / "release" / "engel-ai-rs.exe",
        RUNTIME / "temp" / "engel-rust-rewrite" / "cargo-target" / "debug" / "engel-ai-rs.exe",
        ROOT / "rust" / "engel-core-rs" / "target" / "release" / "engel-ai-rs.exe",
    ]
    exe = next((path for path in candidates if path.exists()), None)
    actions: list[dict] = []
    status = "ok"
    if exe is None:
        return {
            "id": "rust_backend_agent",
            "name": "Rust Backend Agent",
            "goal": "Verify Engel Rust backend command surface is available.",
            "status": "needs_attention",
            "candidates": [str(path) for path in candidates],
            "actions": [{"type": "missing_rust_exe"}],
        }

    safe_routes = (
        ["workspace-inventory", "short"],
        ["workspace-verifiers", "verify"],
        ["connectors", "verify"],
    )
    for args in safe_routes:
        result = command_result(str(exe), args, timeout=35)
        actions.append({"type": "rust_verify", "args": args, "result": result})
        if result.get("exit_code") != 0:
            status = "needs_attention"
    return {
        "id": "rust_backend_agent",
        "name": "Rust Backend Agent",
        "goal": "Run safe Rust health routes for workspace, verifiers, and connectors.",
        "status": status,
        "exe": str(exe),
        "actions": actions,
    }


def chat_bridge_agent(files_changed: list[str]) -> dict:
    paths = {
        "chatgpt_browser_worker": ROOT / "tools" / "engel_chatgpt_browser_worker.py",
        "bridge_root": RUNTIME / "browser_ai_chatgpt_bridge",
        "provider_config": MEMORY_DIR / "personality" / "ENGEL_CHAT_PROVIDER_CONFIG.json",
        "notes_memory": MEMORY_DIR / "notes",
    }
    ensure_dir(paths["bridge_root"], files_changed)
    ensure_dir(paths["notes_memory"], files_changed)
    status_report = {
        key: {"path": str(path), "exists": path.exists()} for key, path in paths.items()
    }
    missing = [key for key, data in status_report.items() if not data["exists"]]
    report_path = RUNTIME / "browser_ai_chatgpt_bridge" / "autofix_status.json"
    write_json(
        report_path,
        {
            "schema": "engel_chat_bridge_autofix_status_v1",
            "created_at_utc": utc_now(),
            "status": "ok" if not missing else "needs_attention",
            "paths": status_report,
        },
    )
    files_changed.append(str(report_path))
    return {
        "id": "chat_bridge_agent",
        "name": "Chat Bridge Agent",
        "goal": "Keep Engel natural-chat bridge files and memory paths ready.",
        "status": "ok" if not missing else "needs_attention",
        "missing": missing,
        "paths": status_report,
        "actions": [{"type": "write_chat_bridge_status", "path": str(report_path)}],
    }


def write_memory(receipt_path: Path, receipt: dict, files_changed: list[str]) -> None:
    assert_safe_write_path(LATEST_MEMORY)
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    created = not LATEST_MEMORY.exists()
    with LATEST_MEMORY.open("a", encoding="utf-8") as fh:
        if created:
            fh.write("# Engel Backend Auto-Fix Agents Receipt\n")
        fh.write(f"\n\n## {receipt['created_at_utc']} - Backend Auto-Fix Agents\n")
        fh.write(f"- Overall OK: {receipt['overall_ok']}\n")
        fh.write(f"- JSON receipt: {receipt_path}\n")
        fh.write(f"- Latest receipt: {LATEST_RECEIPT}\n")
        fh.write(f"- Agents: {len(receipt['agents'])}\n")
        for agent in receipt["agents"]:
            fh.write(f"- {agent['name']}: {agent['status']} - {agent['goal']}\n")
        fh.write("- Policy: no C: writes, no user work deletion, localhost health checks only.\n")
    files_changed.append(str(LATEST_MEMORY))

    log_path = MEMORY_DIR / "MAIN_AGENT_LOG.md"
    assert_safe_write_path(log_path)
    entry = (
        f"\n\n## {receipt['created_at_utc']} - Backend Auto-Fix Agents\n"
        f"- overall_ok: {receipt['overall_ok']}\n"
        f"- receipt: {receipt_path}\n"
        f"- agents: {', '.join(agent['id'] + '=' + agent['status'] for agent in receipt['agents'])}\n"
    )
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(entry)
    files_changed.append(str(log_path))


def build_summary(receipt: dict) -> dict:
    return {
        "schema": "engel_backend_autofix_agents_summary_v1",
        "created_at_utc": receipt["created_at_utc"],
        "overall_ok": receipt["overall_ok"],
        "receipt_path": receipt["receipt_path"],
        "receipt_payload_sha256": receipt["receipt_payload_sha256"],
        "receipt_file_sha256_sidecar": receipt["receipt_file_sha256_sidecar"],
        "files_changed_count": len(receipt["files_changed"]),
        "agents": [
            {
                "id": agent["id"],
                "status": agent["status"],
                "actions": len(agent.get("actions", [])),
            }
            for agent in receipt["agents"]
        ],
    }


def run_agents() -> dict:
    files_changed: list[str] = []
    ensure_dir(REPORT_DIR, files_changed)
    ensure_dir(RUNTIME / "backend_autofix_agents", files_changed)
    agents = [
        runtime_cleanup_agent(files_changed),
        connector_profile_agent(files_changed),
        meeting_room_server_agent(files_changed),
        rust_backend_agent(files_changed),
        chat_bridge_agent(files_changed),
    ]
    overall_ok = all(agent["status"] == "ok" for agent in agents)
    receipt_path = REPORT_DIR / f"backend_autofix_{stamp()}.json"
    sidecar_path = receipt_path.with_suffix(receipt_path.suffix + ".sha256")
    receipt = {
        "schema": "engel_backend_autofix_agents_v1",
        "created_at_utc": utc_now(),
        "root": str(ROOT),
        "overall_ok": overall_ok,
        "agents": agents,
        "receipt_path": str(receipt_path),
        "receipt_file_sha256_sidecar": str(sidecar_path),
        "receipt_hash_scope": "canonical JSON excluding receipt_sha256 and receipt_payload_sha256 fields",
        "safety": {
            "c_drive_write_allowed": False,
            "delete_user_work": False,
            "network_scope": "localhost health checks only",
        },
    }
    write_memory(receipt_path, receipt, files_changed)
    final_files = sorted(
        set(files_changed + [str(receipt_path), str(LATEST_RECEIPT), str(sidecar_path)])
    )
    receipt["files_changed"] = final_files
    payload_hash = canonical_payload_sha256(receipt)
    receipt["receipt_payload_sha256"] = payload_hash
    receipt["receipt_sha256"] = payload_hash
    write_json(receipt_path, receipt)
    write_json(LATEST_RECEIPT, receipt)
    sidecar_path.write_text(f"{sha256(receipt_path)}  {receipt_path.name}\n", encoding="utf-8")
    return receipt


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Print compact UI summary while still writing full receipts.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    receipt = run_agents()
    payload = build_summary(receipt) if args.summary else receipt
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if receipt["overall_ok"] else 2


if __name__ == "__main__":
    sys.exit(main())