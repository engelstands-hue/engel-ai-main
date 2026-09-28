#!/usr/bin/env python3
"""Watch node-ready callbacks and auto-pair new Windows Sub-Engel nodes."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Any
from urllib import request

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import engel_sub_node_remote_control as remote  # noqa: E402


READY_PATH = ROOT / "runtime" / "windows_sub_engel_bootstrap" / "latest_node_ready.json"
STATE_PATH = ROOT / "runtime" / "windows_sub_engel_bootstrap" / "auto_pair_watcher_state.json"
LOG_PATH = ROOT / "reports" / "sub_engel_remote_control" / "windows_auto_pair_watcher.jsonl"
PAIR_HELPER = ROOT / "tools" / "pair_latest_windows_sub_engel_node.py"
PYTHON = ROOT / "runtime" / "python310" / "python.exe"
WINDOWS_NODE_DIR = ROOT / "remote_nodes" / "windows_sub_engel"
DEFAULT_HEALTH_PROBES = ("http://198.51.100.227:8776",)
SERVER_ONLY = "--server-only" in sys.argv
CT_PAIR_HELPER = "/opt/engel/tools/engel_pair_windows_sub_from_stdin.py"
PROXMOX_HOST = "root@192.0.2.50"
CT_ID = "246"
DISABLED_AGENT_MEETING_STATUSES = {
    "not_selectable",
    "not_selectable_external_jobs",
    "reserved_external_jobs",
    "disabled",
    "retired",
}
SESSION_RENEW_BEFORE_SECONDS = 3 * 24 * 60 * 60
SESSION_RENEW_CHECK_SECONDS = 5 * 60
WATCHER_LOCK_PATH = (
    ROOT
    / "runtime"
    / "windows_sub_engel_bootstrap"
    / "auto_pair_watcher.lock"
)
_WATCHER_LOCK_HANDLE = None


def utc_stamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def append_log(event: dict[str, Any]) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"timestamp_utc": utc_stamp(), **event}, sort_keys=True) + "\n")


def acquire_single_instance_lock():
    global _WATCHER_LOCK_HANDLE
    WATCHER_LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    handle = WATCHER_LOCK_PATH.open("a+b")
    handle.seek(0)
    if handle.tell() == 0 and WATCHER_LOCK_PATH.stat().st_size == 0:
        handle.write(b"0")
        handle.flush()
    handle.seek(0)
    try:
        if sys.platform == "win32":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (OSError, BlockingIOError):
        handle.close()
        return None
    _WATCHER_LOCK_HANDLE = handle
    return handle


def ready_key(data: dict[str, Any]) -> str:
    return "|".join([
        str(data.get("computer_name") or ""),
        str(data.get("node_ip") or data.get("remote_addr") or ""),
        str(data.get("pairing_code") or ""),
        str(data.get("timestamp") or ""),
    ])


def is_drive_backed_node_root(value: Any) -> bool:
    text = str(value or "").replace("/", "\\").lower()
    return "\\my drive\\" in text or text.startswith("g:\\my drive\\") or text.startswith("h:\\my drive\\")


def session_is_disabled(session: dict[str, Any]) -> bool:
    if not isinstance(session, dict):
        return False
    if session.get("disabled_for_engel_main") is True or session.get("do_not_use_for_engel_ai_main") is True:
        return True
    status = str(session.get("agent_meeting_status") or "").strip().lower()
    return status in DISABLED_AGENT_MEETING_STATUSES


def parse_utc(value: Any) -> float:
    raw = str(value or "").strip()
    if not raw:
        return 0.0
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return 0.0
    return parsed.timestamp()


def health_probe_urls() -> list[str]:
    values: list[str] = []
    raw = str(sys.argv[sys.argv.index("--probe-url") + 1]) if "--probe-url" in sys.argv and sys.argv.index("--probe-url") + 1 < len(sys.argv) else ""
    if raw:
        values.extend(part.strip() for part in raw.split(";") if part.strip())
    for path in (WINDOWS_NODE_DIR / "session.json",):
        session = read_json(path)
        if session.get("url") and not session_is_disabled(session):
            values.append(str(session["url"]))
    nodes_dir = WINDOWS_NODE_DIR / "nodes"
    if nodes_dir.is_dir():
        for session_path in nodes_dir.glob("*/session.json"):
            session = read_json(session_path)
            if session.get("url") and not session_is_disabled(session):
                values.append(str(session["url"]))
    values.extend(DEFAULT_HEALTH_PROBES)
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        clean = str(value or "").strip().rstrip("/")
        if not clean:
            continue
        if "://" not in clean:
            clean = "http://" + clean
        key = clean.lower()
        if key not in seen:
            seen.add(key)
            out.append(clean)
    return out


def fetch_health(url: str) -> dict[str, Any]:
    try:
        req = request.Request(url.rstrip("/") + "/health", headers={"Accept": "application/json"})
        with request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data if isinstance(data, dict) else {"ok": False, "error": "invalid_health"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def should_run_health_proof(state: dict[str, Any], key: str, minimum_seconds: float = 120.0) -> bool:
    if state.get("last_health_probe_proof_key") != key:
        return True
    if state.get("last_health_probe_proof_ok") is True:
        return False
    last_attempt = parse_utc(state.get("last_health_probe_proof_at_utc"))
    return (time.time() - last_attempt) >= minimum_seconds


def authenticated_session_ready(node_id: str) -> tuple[bool, str]:
    session = remote.load_session("windows", node_id)
    if not session.get("session_token"):
        return False, "session_token_missing"
    expires_at = parse_utc(session.get("expires_at_utc"))
    if not expires_at or expires_at <= time.time():
        return False, "session_expired_requires_pair"
    return True, "ready"


def run_pair_on_ct246(ready: dict[str, Any]) -> dict[str, Any]:
    node_ip = str(ready.get("node_ip") or ready.get("remote_addr") or "").strip()
    payload = {
        "computer_name": str(ready.get("computer_name") or "").strip(),
        "url": f"http://{node_ip}:8776",
        "pairing_code": str(ready.get("pairing_code") or "").strip(),
    }
    try:
        proc = subprocess.run(
            [
                "ssh",
                "-o",
                "BatchMode=yes",
                "-o",
                "ConnectTimeout=8",
                PROXMOX_HOST,
                "pct",
                "exec",
                CT_ID,
                "--",
                "python3",
                CT_PAIR_HELPER,
            ],
            cwd=str(ROOT),
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=45,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except subprocess.TimeoutExpired as exc:
        return {
            "returncode": 124,
            "timed_out": True,
            "stdout_tail": str(exc.stdout or "")[-4000:],
            "stderr_tail": str(exc.stderr or "")[-4000:],
        }
    result: dict[str, Any] = {
        "returncode": proc.returncode,
        "transport": "ct246_direct_http",
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
    }
    try:
        parsed = json.loads(proc.stdout)
        if isinstance(parsed, dict):
            parsed.pop("session_token", None)
            result["parsed"] = parsed
    except json.JSONDecodeError:
        pass
    return result


def run_pair(ready: dict[str, Any]) -> dict[str, Any]:
    if SERVER_ONLY:
        return run_pair_on_ct246(ready)
    try:
        proc = subprocess.run(
            [str(PYTHON), str(PAIR_HELPER)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=45,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except subprocess.TimeoutExpired as exc:
        return {
            "returncode": 124,
            "timed_out": True,
            "stdout_tail": str(exc.stdout or "")[-4000:],
            "stderr_tail": str(exc.stderr or "")[-4000:],
        }
    payload: dict[str, Any] = {
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
    }
    try:
        parsed = json.loads(proc.stdout)
        if isinstance(parsed, dict):
            parsed.pop("session_token", None)
            payload["parsed"] = parsed
    except json.JSONDecodeError:
        pass
    return payload


def run_live_proof(node_id: str) -> dict[str, Any]:
    response = remote.run_action("node.status", node_kind="windows", node_id=node_id)
    parsed = remote.decode_action_stdout(response)
    return {
        "returncode": 0 if response.get("ok") and parsed.get("ok") else 1,
        "transport": "authenticated_direct_http",
        "parsed": parsed,
        "error": response.get("error", ""),
    }


def renew_expiring_sessions(state: dict[str, Any]) -> dict[str, Any]:
    last_check = parse_utc(state.get("last_session_renew_check_at_utc"))
    if last_check and (time.time() - last_check) < SESSION_RENEW_CHECK_SECONDS:
        return state

    checked = 0
    renewed = 0
    expired: list[str] = []
    errors: list[dict[str, str]] = []
    for item in remote.list_node_sessions("windows"):
        node_id = str(item.get("node_id") or "").strip()
        session = item.get("session") if isinstance(item.get("session"), dict) else {}
        expires_at = parse_utc(session.get("expires_at_utc"))
        if not node_id or not expires_at:
            continue
        remaining = expires_at - time.time()
        checked += 1
        if remaining <= 0:
            expired.append(node_id)
            continue
        if remaining > SESSION_RENEW_BEFORE_SECONDS:
            continue

        url = str(session.get("url") or "").rstrip("/")
        health = fetch_health(url) if url else {"ok": False, "error": "missing_url"}
        actions = health.get("allowed_actions") if isinstance(health.get("allowed_actions"), list) else []
        if "session.renew" not in actions:
            errors.append({"node_id": node_id, "error": "session_renew_not_available"})
            continue
        response = remote.run_action("session.renew", node_kind="windows", node_id=node_id)
        result = remote.decode_action_stdout(response)
        if response.get("ok") and result.get("ok") and result.get("expires_at_utc"):
            renewed += 1
            append_log({
                "event": "session_renewed",
                "node_id": node_id,
                "expires_at_utc": result.get("expires_at_utc"),
            })
        else:
            errors.append({"node_id": node_id, "error": str(response.get("error") or result.get("error") or "renew_failed")})

    state.update({
        "last_session_renew_check_at_utc": utc_stamp(),
        "last_session_renew_checked": checked,
        "last_session_renewed": renewed,
        "expired_sessions_requiring_pair": expired,
        "session_renew_errors": errors,
    })
    return state


def probe_known_nodes_for_auto_return(state: dict[str, Any]) -> dict[str, Any]:
    for url in health_probe_urls():
        health = fetch_health(url)
        if not health.get("ok"):
            continue
        actions = health.get("allowed_actions") if isinstance(health.get("allowed_actions"), list) else []
        node_root = str(health.get("node_root") or "")
        hostname = str(health.get("hostname") or "").strip()
        health_key = "|".join([
            hostname,
            url,
            node_root,
            "direct" if "direct_work.execute" in actions else "legacy",
        ])
        if is_drive_backed_node_root(node_root):
            continue
        if "direct_work.execute" not in actions:
            state.update({
                "last_health_probe_at_utc": utc_stamp(),
                "last_health_probe_key": health_key,
                "last_health_probe_status": "legacy_action_list",
                "last_health_probe_url": url,
            })
            continue
        if not hostname:
            continue
        session_ready, session_status = authenticated_session_ready(hostname)
        if not session_ready:
            state.update({
                "last_health_probe_at_utc": utc_stamp(),
                "last_health_probe_key": health_key,
                "last_health_probe_status": session_status,
                "last_health_probe_url": url,
                "last_health_probe_node": hostname,
            })
            continue
        if not should_run_health_proof(state, health_key):
            continue
        append_log({
            "event": "health_probe_new_direct_work_node",
            "url": url,
            "hostname": hostname,
            "node_root": node_root,
        })
        proof = run_live_proof(hostname)
        parsed = proof.get("parsed") if isinstance(proof.get("parsed"), dict) else {}
        proof_ok = bool(parsed.get("ok")) or proof.get("returncode") == 0
        state.update({
            "last_health_probe_at_utc": utc_stamp(),
            "last_health_probe_key": health_key,
            "last_health_probe_status": "direct_work_action_available",
            "last_health_probe_url": url,
            "last_health_probe_node": hostname,
            "last_health_probe_proof_key": health_key,
            "last_health_probe_proof_at_utc": utc_stamp(),
            "last_health_probe_proof_ok": proof_ok,
        })
        append_log({
            "event": "health_probe_live_proof_complete",
            "ok": proof_ok,
            "url": url,
            "hostname": hostname,
            "proof": proof,
        })
        return state
    return state


def main() -> int:
    if acquire_single_instance_lock() is None:
        append_log({
            "event": "duplicate_watcher_exited",
            "server_only": SERVER_ONLY,
        })
        return 0
    interval = 4.0
    skip_existing = "--pair-existing" not in sys.argv
    state = read_json(STATE_PATH)
    if skip_existing and not state.get("initialized"):
        existing = read_json(READY_PATH)
        if existing:
            state["last_seen_key"] = ready_key(existing)
            state["initialized"] = True
            state["initialized_at_utc"] = utc_stamp()
            write_json(STATE_PATH, state)
            append_log({"event": "initialized_skip_existing", "ready_key": state["last_seen_key"]})

    append_log({
        "event": "watcher_started",
        "ready_path": str(READY_PATH),
        "pair_helper": str(PAIR_HELPER),
        "server_only": SERVER_ONLY,
    })
    while True:
        state = read_json(STATE_PATH)
        ready = read_json(READY_PATH)
        key = ready_key(ready) if ready else ""
        if ready and key and key != state.get("last_seen_key"):
            node_root = ready.get("node_root") or ready.get("file_structure_root") or ""
            append_log({
                "event": "new_node_ready",
                "computer_name": ready.get("computer_name", ""),
                "node_ip": ready.get("node_ip") or ready.get("remote_addr") or "",
                "node_root": str(node_root),
            })
            if is_drive_backed_node_root(node_root):
                state.update({
                    "last_seen_key": key,
                    "last_pair_attempt_utc": utc_stamp(),
                    "last_pair_ok": False,
                    "last_pair_returncode": 2,
                    "last_node_ip": ready.get("node_ip") or ready.get("remote_addr") or "",
                    "last_computer_name": ready.get("computer_name", ""),
                    "last_refusal": "drive_backed_node_root",
                    "last_refused_node_root": str(node_root),
                })
                write_json(STATE_PATH, state)
                append_log({
                    "event": "pair_refused",
                    "reason": "drive_backed_node_root",
                    "node_root": str(node_root),
                })
                time.sleep(interval)
                continue
            if not str(ready.get("pairing_code") or "").strip():
                state.update({
                    "last_seen_key": key,
                    "last_node_ready_utc": utc_stamp(),
                    "last_node_ip": ready.get("node_ip") or ready.get("remote_addr") or "",
                    "last_computer_name": ready.get("computer_name", ""),
                    "last_pair_skipped": "session_preserving_node_ready",
                })
                write_json(STATE_PATH, state)
                append_log({
                    "event": "session_preserving_node_ready",
                    "computer_name": ready.get("computer_name", ""),
                    "node_ip": ready.get("node_ip") or ready.get("remote_addr") or "",
                    "pair_attempted": False,
                })
                time.sleep(interval)
                continue
            result = run_pair(ready)
            ok = bool(result.get("parsed", {}).get("pair_ok")) if isinstance(result.get("parsed"), dict) else result["returncode"] == 0
            proof_result: dict[str, Any] = {}
            proof_ok = bool(result.get("parsed", {}).get("proof_ok")) if isinstance(result.get("parsed"), dict) else False
            if ok and not SERVER_ONLY:
                node_id = str(ready.get("computer_name") or result.get("parsed", {}).get("computer_name") or "").strip()
                if node_id:
                    proof_result = run_live_proof(node_id)
                    parsed_proof = proof_result.get("parsed") if isinstance(proof_result.get("parsed"), dict) else {}
                    proof_ok = bool(parsed_proof.get("ok")) or proof_result.get("returncode") == 0
            state.update({
                "last_seen_key": key,
                "last_pair_attempt_utc": utc_stamp(),
                "last_pair_ok": ok,
                "last_pair_returncode": result["returncode"],
                "last_live_proof_ok": proof_ok,
                "last_node_ip": ready.get("node_ip") or ready.get("remote_addr") or "",
                "last_computer_name": ready.get("computer_name", ""),
            })
            write_json(STATE_PATH, state)
            append_log({"event": "pair_attempt_complete", "ok": ok, "result": result, "proof": proof_result})
        if not SERVER_ONLY:
            state = renew_expiring_sessions(read_json(STATE_PATH))
            state = probe_known_nodes_for_auto_return(state)
        else:
            state = read_json(STATE_PATH)
            state["shared_drive_disabled"] = True
            state["control_transport"] = "authenticated_direct_http"
            state["session_renewal_owner"] = "ct246"
            state["rog_local_session_renewal_disabled"] = True
        write_json(STATE_PATH, state)
        time.sleep(interval)


if __name__ == "__main__":
    raise SystemExit(main())
