#!/usr/bin/env python3
"""Flutter/Engel chat wrapper: local LLM plus Agent Meeting Room handoff.

This keeps the Flutter chat JSON contract while making the main-chat route
explicit:

UI chat -> local standalone LLM -> Agent Meeting Room submit/complete.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import time
from typing import Any
import urllib.error
import urllib.parse
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
os.chdir(ROOT)

from tools.engel_phone_presence import phone_presence_snapshot  # noqa: E402

from engel_ui_prompt_training_support import (  # noqa: E402
    build_agent_proposals,
    build_device_selection,
    iso_now,
    redact,
    stamp,
    write_json,
)

try:  # noqa: E402
    from engel_chat_humanizer import improve_visible_reply
except Exception:  # pragma: no cover - fallback keeps chat alive if helper is missing
    def improve_visible_reply(prompt: str, reply: str, *, source: str = "") -> tuple[str, dict[str, Any]]:
        text = str(reply or "").strip()
        return text, {
            "schema": "engel_chat_humanizer_result_v1",
            "source": source,
            "humanizer_reference_loaded": False,
            "workspace_registry_loaded": False,
            "reply_was_weak_or_repeated": False,
            "reply_changed": False,
            "reason": "humanizer_unavailable",
        }


TRAINING_TEMPLATE_SCRIPT = TOOLS / "run_engel_local_llm_prompt_training_template.py"
APP_ARTIFACT_ROOT = ROOT / "artifacts" / "engel_ui_results" / "app_creation"
DEFAULT_MEETING_ROOM_SERVER_URL = "http://127.0.0.1:8790"
CHAT_SAFE_MEETING_ROOM_DEFAULTS = {
    "ENGEL_MEETING_ROOM_SUB_RETURN_WAIT_SECONDS": "18",
    "ENGEL_MEETING_ROOM_SUB_PASSIVE_WAIT_SECONDS": "4",
    "ENGEL_MEETING_ROOM_SUB_AUTO_RETURN_ATTEMPTS": "1",
}
PHONE_ASSIGNMENT_ROOT = ROOT / "remote_workers" / "communication_queen_assignments"
PHONE_APPROVED_DIR = PHONE_ASSIGNMENT_ROOT / "approved"
PHONE_CLAIMED_DIR = PHONE_ASSIGNMENT_ROOT / "claimed"
PHONE_RETURNED_DIR = PHONE_ASSIGNMENT_ROOT / "returned"
PHONE_BRIDGE_STATE_PATH = ROOT / "memory" / "phone_bridge" / "ENGEL_REMOTE_WORKERS_PAIRED.json"
PHONE_RETURN_RELAY_URL = os.environ.get(
    "ENGEL_PHONE_RETURN_RELAY_URL",
    "http://127.0.0.1:18765/queue/returned-result",
).strip()
SUB_ENGEL_DEFAULT_WAIT_SECONDS = 30
CONICAL_PHONE_RETURN_WAIT_SECONDS = 45
CONICAL_REPORT_ROOT = ROOT / "reports" / "conical_jobs"
CONICAL_PHONE_TASKS = (
    {
        "worker_id": "android_worker_alpha",
        "role": "requirements analyst",
        "task_type": "conical_requirements_analysis",
        "objective": (
            "Extract the functional requirements, user-visible behavior, data inputs, "
            "outputs, and acceptance criteria. Return a compact implementation brief."
        ),
    },
    {
        "worker_id": "android_worker_beta",
        "role": "verification planner",
        "task_type": "conical_verification_plan",
        "objective": (
            "Draft the test matrix, edge cases, failure states, and proof steps that "
            "must pass before the result can be called finished."
        ),
    },
    {
        "worker_id": "android_worker_gamma",
        "role": "dependency and risk checker",
        "task_type": "conical_dependency_risk_check",
        "objective": (
            "Identify dependencies, integration risks, offline constraints, and the "
            "smallest deterministic checks needed to catch regressions."
        ),
    },
)


def _sanitize_prompt_text(prompt: str) -> str:
    text = str(prompt or "").replace("\x00", "")
    return "".join(ch for ch in text if ch in "\r\n\t" or ord(ch) >= 32).strip()


def _read_prompt_file(path_text: str) -> str:
    if not path_text:
        return ""
    path = Path(path_text)
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists() or not path.is_file():
        raise ValueError(f"prompt file not found: {path}")
    if str(path.resolve()).lower().startswith("c:\\"):
        raise ValueError(f"prompt file is on C drive, refusing Engel prompt handoff: {path}")
    return path.read_text(encoding="utf-8", errors="replace")


def _apply_chat_safe_meeting_room_defaults() -> None:
    for key, value in CHAT_SAFE_MEETING_ROOM_DEFAULTS.items():
        os.environ.setdefault(key, value)


def _meeting_room_server_url() -> str:
    if os.environ.get("ENGEL_MEETING_ROOM_SERVER_DISABLED", "").strip().lower() in {"1", "true", "yes", "on"}:
        return ""
    return os.environ.get("ENGEL_MEETING_ROOM_SERVER_URL", DEFAULT_MEETING_ROOM_SERVER_URL).strip().rstrip("/")


def _server_merge_snapshot() -> dict[str, Any]:
    try:
        from engel_main_server_merge import server_merge_status_payload

        return server_merge_status_payload(live_probe=False)
    except Exception as exc:
        return {
            "schema": "engel_main_server_merge_status_v1",
            "ok": False,
            "status": "server merge status unavailable",
            "error": str(exc),
            "storage_mutation_performed": False,
            "background_worker_started": False,
        }


def _server_merge_live_snapshot() -> dict[str, Any]:
    try:
        from engel_main_server_merge import server_merge_status_payload

        return server_merge_status_payload(live_probe=True)
    except Exception as exc:
        return {
            "schema": "engel_main_server_merge_status_v1",
            "ok": False,
            "status": "server merge live status unavailable",
            "error": str(exc),
            "tcp_probe_performed": True,
            "tcp_reachable": False,
            "storage_mutation_performed": False,
            "background_worker_started": False,
        }


def _persistent_chat_memory_status() -> dict[str, Any]:
    path = ROOT / "memory" / "persistent_chat" / "ENGEL_AI_MAIN_LLM_CHAT_MEMORY.jsonl"
    parent = path.parent
    return {
        "schema": "engel_persistent_chat_memory_status_v1",
        "path": str(path),
        "parent": str(parent),
        "parent_exists": parent.exists(),
        "file_exists": path.exists(),
        "writable": parent.exists() and os.access(parent, os.W_OK),
        "append_only_context_history": True,
        "approved_trusted_memory": False,
    }


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name, "").strip().lower()
    if not value:
        return default
    return value in {"1", "true", "yes", "on"}


def _main_server_chat_url(server_merge: dict[str, Any]) -> str:
    explicit = os.environ.get("ENGEL_MAIN_SERVER_CHAT_URL", "").strip().rstrip("/")
    if explicit:
        return explicit
    if bool(server_merge.get("enabled")):
        return "http://127.0.0.1:24680"
    return ""


def _main_server_chat_required(server_merge: dict[str, Any]) -> bool:
    if os.environ.get("ENGEL_MAIN_SERVER_CHAT_REQUIRED", "").strip():
        return _env_bool("ENGEL_MAIN_SERVER_CHAT_REQUIRED")
    return bool(server_merge.get("enabled"))


def _main_server_chat_payload(
    prompt: str,
    timeout: int,
    max_tokens: int,
    temperature: float,
    server_merge: dict[str, Any],
    conical_orchestration: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "schema": "engel_main_server_chat_request_v1",
        "prompt": prompt,
        "timeout": max(1, timeout),
        "max_tokens": max(1, max_tokens),
        "temperature": temperature,
        "source": "ROG Engel AI Main Chat UI",
        "controller": os.environ.get("COMPUTERNAME", "rog-controller"),
        "server_peer": server_merge.get("server_peer", "engel-ai-main CT 246"),
        "ssh_route": server_merge.get("ssh_route", "ssh root@192.0.2.50 -p 24622"),
    }
    if conical_orchestration:
        payload["conical_orchestration"] = conical_orchestration
    return payload


def _post_json(url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8", errors="replace")
    parsed = json.loads(body)
    if not isinstance(parsed, dict):
        raise ValueError("server returned non-object JSON")
    return parsed


def _write_ui_chat_receipt(receipt: dict[str, Any], prompt: str) -> dict[str, Any]:
    receipt_path = ROOT / "reports" / "engel_standalone_chat_llm" / "chat_receipts" / f"ENGEL_UI_CHAT_MEETING_ROOM_{stamp()}.json"
    write_json(receipt_path, receipt)
    receipt["ui_meeting_room_receipt_path"] = str(receipt_path)
    receipt = _append_trusted_ui_memory(receipt, prompt)
    if "persistent_chat_history_appended" not in receipt:
        receipt["persistent_chat_history_appended"] = bool(receipt.get("persistent_chat_memory_appended"))
    write_json(receipt_path, receipt)
    return receipt


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        if not path.is_file():
            return {}
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _parse_utc(text: Any) -> datetime | None:
    raw = str(text or "").strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    if "." in raw:
        head, tail = raw.split(".", 1)
        frac = tail
        suffix = ""
        if "+" in tail:
            frac, suffix = tail.split("+", 1)
            suffix = "+" + suffix
        elif "-" in tail:
            frac, suffix = tail.split("-", 1)
            suffix = "-" + suffix
        raw = head + "." + frac[:6] + suffix
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _phone_bridge_workers() -> dict[str, dict[str, Any]]:
    snapshot = phone_presence_snapshot(root=ROOT)
    workers = snapshot.get("workers")
    return workers if isinstance(workers, dict) else {}


_FORBIDDEN_DEVICE_IDS_FALLBACK = {"desktop-fib17o7"}


def _broker_forbidden_ids() -> set[str]:
    try:
        from engel_device_broker import FORBIDDEN_DEVICE_IDS

        return {str(x).lower() for x in FORBIDDEN_DEVICE_IDS} | _FORBIDDEN_DEVICE_IDS_FALLBACK
    except Exception:
        return set(_FORBIDDEN_DEVICE_IDS_FALLBACK)


def _sub_engel_forbidden_block(selected: dict[str, Any]) -> str:
    """Returns a refusal reason when the selected Sub-Engel node is forbidden
    by the goal contract; empty string when dispatch may proceed."""
    selected_id = str(selected.get("node_id") or selected.get("hostname") or "").strip().lower()
    if selected_id and selected_id in _broker_forbidden_ids():
        return f"selected node {selected_id} is forbidden by the goal contract; dispatch refused"
    return ""


def _broker_dispatch_gate(worker_ids: list[str], job_kind: "str | None" = None) -> dict[str, Any]:
    """Evidence-backed pre-dispatch eligibility gate (goal criterion: only
    reachable and capable devices receive assignments).

    - FORBIDDEN devices are hard-blocked even when the broker cannot run.
    - When the broker runs, a worker must be broker-eligible to pass; a worker
      with no broker evidence is blocked (fail-closed).
    - If the broker itself errors, the existing fresh-heartbeat gate remains
      the reachability check and only the forbidden hard-block is added, so a
      broker outage narrows dispatch and never widens it.
    """
    forbidden = _broker_forbidden_ids()
    gate: dict[str, Any] = {
        "schema": "engel_dispatch_broker_gate_v1",
        "consulted": False,
        "eligible": [],
        "blocked": {},
        "broker_error": "",
    }
    remaining: list[str] = []
    for worker_id in worker_ids:
        if str(worker_id).strip().lower() in forbidden:
            gate["blocked"][worker_id] = "forbidden device (goal contract)"
        else:
            remaining.append(worker_id)
    try:
        from engel_device_broker import broker_decision

        decision = broker_decision(job_kind=job_kind)
        devices = decision.get("candidates") if isinstance(decision.get("candidates"), list) \
            else (decision.get("devices") if isinstance(decision.get("devices"), list) else [])
        by_id = {str(d.get("device_id") or "").lower(): d for d in devices if isinstance(d, dict)}
        gate["consulted"] = True
        for worker_id in remaining:
            entry = by_id.get(str(worker_id).lower())
            if entry is None:
                gate["blocked"][worker_id] = "no broker evidence for this device"
            elif entry.get("eligible") is True:
                gate["eligible"].append(worker_id)
            else:
                gate["blocked"][worker_id] = str(entry.get("reason") or "not eligible")
    except Exception as exc:
        gate["broker_error"] = str(exc)[:200]
        gate["eligible"] = remaining
    return gate


def _prompt_requests_device_work(prompt: str) -> bool:
    text = " ".join(str(prompt or "").casefold().split())
    if not text:
        return False
    device_terms = (
        "all devices",
        "all workers",
        "whole room",
        "full room",
        "meeting room",
        "agent room",
        "sub-engel",
        "sub engel",
        "windows sub-engel",
        "windows sub engel",
        "desktop node",
        "phone",
        "phones",
        "android",
    )
    work_terms = (
        "work",
        "send",
        "give",
        "assign",
        "dispatch",
        "route",
        "run",
        "test",
        "check",
        "verify",
        "proof",
        "report",
        "split",
        "use",
        "stretch",
    )
    return any(term in text for term in device_terms) and any(term in text for term in work_terms)


def _prompt_requests_phone_work(prompt: str) -> bool:
    text = " ".join(str(prompt or "").casefold().split())
    if not text:
        return False
    phone_terms = (
        "phone",
        "phones",
        "android",
        "worker alpha",
        "worker beta",
        "worker gamma",
        "android worker",
        "alpha",
        "beta",
        "gamma",
        "all devices",
        "all workers",
    )
    work_terms = (
        "work",
        "send",
        "give",
        "assign",
        "dispatch",
        "route",
        "run",
        "test",
        "verify",
        "proof",
        "status",
        "check result",
        "report",
        "classify",
        "classification",
        "summarize",
        "draft",
        "stretch",
        "use",
        "use the phones",
        "use phones",
        "get any work",
    )
    return any(term in text for term in phone_terms) and any(term in text for term in work_terms)


def _prompt_requests_sub_engel_work(prompt: str) -> bool:
    text = " ".join(str(prompt or "").casefold().split())
    if not text:
        return False
    sub_terms = (
        "sub-engel",
        "sub engel",
        "windows sub-engel",
        "windows sub engel",
        "desktop node",
        "all devices",
        "all workers",
        "whole room",
        "full room",
        "meeting room",
        "agent room",
    )
    work_terms = (
        "work",
        "send",
        "give",
        "assign",
        "dispatch",
        "route",
        "run",
        "test",
        "check",
        "verify",
        "proof",
        "report",
        "split",
        "use",
        "stretch",
    )
    return any(term in text for term in sub_terms) and any(term in text for term in work_terms)


def _requested_phone_workers(prompt: str, workers: dict[str, dict[str, Any]]) -> list[str]:
    text = " ".join(str(prompt or "").casefold().split())
    explicit: list[str] = []
    if "alpha" in text:
        explicit.append("android_worker_alpha")
    if "beta" in text:
        explicit.append("android_worker_beta")
    if "gamma" in text:
        explicit.append("android_worker_gamma")
    if explicit:
        return [worker_id for worker_id in explicit if worker_id in workers]
    if any(term in text for term in ("all devices", "all workers", "all phones", "phones", "phone workers", "android workers")):
        return sorted(workers)
    preferred = ["android_worker_alpha", "android_worker_beta", "android_worker_gamma"]
    listed = [worker_id for worker_id in preferred if worker_id in workers]
    return listed or sorted(workers)


def _sub_engel_order_result(order_id: str, folder: str) -> dict[str, Any] | None:
    target = str(order_id or "").strip()
    root = Path(str(folder or ""))
    if not target or not root.exists():
        return None
    matches: list[tuple[float, Path, dict[str, Any]]] = []
    try:
        candidates = list(root.glob(f"*{target}*.json"))
    except OSError:
        candidates = []
    for path in candidates:
        payload = _load_json_object(path)
        if str(payload.get("order_id") or "") == target:
            try:
                mtime = path.stat().st_mtime
            except OSError:
                mtime = 0.0
            matches.append((mtime, path, payload))
    if not matches:
        return None
    _mtime, path, payload = sorted(matches, key=lambda item: item[0])[-1]
    return {"path": str(path), "payload": payload}


def _sub_engel_wait_for_result(order_id: str, folder: str, timeout_seconds: float) -> dict[str, Any] | None:
    deadline = time.time() + max(0.0, timeout_seconds)
    while True:
        found = _sub_engel_order_result(order_id, folder)
        if found is not None:
            return found
        if time.time() >= deadline:
            return None
        time.sleep(1.0)


def _sub_engel_url_candidates(selected_node: dict[str, Any]) -> list[str]:
    candidates: list[str] = []
    seen: set[str] = set()

    def add(raw: Any) -> None:
        text = str(raw or "").strip().rstrip("/")
        if not text:
            return
        if "://" not in text:
            text = "http://" + text
        if text not in seen:
            seen.add(text)
            candidates.append(text)

    add(selected_node.get("url"))
    ips = selected_node.get("ips") or selected_node.get("last_known_ips") or []
    if isinstance(ips, str):
        ips = [ips]
    if isinstance(ips, list):
        for ip in ips:
            add(f"http://{ip}:8776")
    return candidates


def _sub_engel_tcp_open(url: str, timeout: float = 0.8) -> bool:
    try:
        parsed = urllib.parse.urlsplit(url if "://" in url else "http://" + url)
        host = parsed.hostname or ""
        port = parsed.port or 8776
        if not host:
            return False
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


_SUB_ENGEL_TRANSIENT_PIPE_MARKERS = (
    "remote end closed",
    "connection reset",
    "connection aborted",
    "broken pipe",
    "timed out",
    "timeout",
    "temporarily unavailable",
    "eof occurred",
    "winerror 10054",
    "winerror 10053",
    "winerror 10060",
    "connection refused",
)


def _sub_engel_pipe_error_is_transient(error: str) -> bool:
    low = str(error or "").casefold()
    return any(marker in low for marker in _SUB_ENGEL_TRANSIENT_PIPE_MARKERS)


def _sub_engel_node_url(selected: dict[str, Any] | None = None) -> str:
    selected = selected if isinstance(selected, dict) else {}
    return str(selected.get("url") or "http://198.51.100.227:8776").strip()


def _sub_engel_node_reachable(selected: dict[str, Any] | None = None, timeout: float = 1.5) -> dict[str, Any]:
    """Live proof that Sub-Engel is on the LAN — not the CT246 chat pipe."""
    url = _sub_engel_node_url(selected)
    tcp_open = _sub_engel_tcp_open(url, timeout=timeout)
    health_ok = False
    health_error = ""
    if tcp_open:
        try:
            with urllib.request.urlopen(url.rstrip("/") + "/health", timeout=timeout) as response:
                payload = json.loads(response.read().decode("utf-8", errors="replace"))
            health_ok = isinstance(payload, dict) and payload.get("ok") is True
        except Exception as exc:
            health_error = str(exc)[:200]
    return {
        "url": url,
        "tcp_open": tcp_open,
        "health_ok": health_ok,
        "reachable": bool(tcp_open),
        "error": health_error,
    }


def _honest_sub_engel_dispatch_error(
    error: str,
    selected: dict[str, Any] | None = None,
    probe: dict[str, Any] | None = None,
) -> str:
    """Never report a paired reachable node as disconnected."""
    probe = probe if isinstance(probe, dict) else _sub_engel_node_reachable(selected)
    url = str(probe.get("url") or _sub_engel_node_url(selected))
    detail = str(error or "work pipe failed").strip()
    if probe.get("health_ok") is True or probe.get("tcp_open") is True:
        return (
            f"Sub-Engel is paired and reachable at {url}; "
            f"the CT246 work pipe failed ({detail}). This is not an unpaired node."
        )
    return (
        f"Sub-Engel pair target {url} is not accepting connections ({detail}). "
        "Check the Sub-Engel desktop agent, not just the CT246 chat tunnel."
    )


def _expected_sub_engel_return_path(work_order: dict[str, Any]) -> Path:
    folder = Path(str(work_order.get("expected_return_folder") or ""))
    order_id = str(work_order.get("id") or "")
    node_id = str(
        (work_order.get("selected_node") or {}).get("node_id")
        or "DESKTOP-UE5A6GG"
    )
    safe_node = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in node_id)
    return folder / f"{safe_node}__{order_id}.done.json"


def _wait_for_sub_engel_done_file(path: Path, timeout_seconds: float) -> dict[str, Any] | None:
    deadline = time.time() + max(0.0, timeout_seconds)
    while time.time() <= deadline:
        payload = _load_json_object(path)
        if payload.get("ok") is True and payload.get("order_id"):
            return payload
        time.sleep(1.5)
    return None


def _ct246_authenticated_run_action() -> Any | None:
    """Return CT246's direct paired-node action runner when executing on CT246.

    The CT chat listener is intentionally single-threaded. Posting a Sub-Engel
    request back into that same listener deadlocks until the loopback request
    times out, so CT246 must call its authenticated node client in-process.
    """
    if os.name == "nt":
        return None
    configured_root = Path(os.environ.get("ENGEL_APP_ROOT", str(ROOT))).resolve()
    if configured_root != Path("/opt/engel") or ROOT.resolve() != configured_root:
        return None
    try:
        from engel_sub_node_remote_control import run_action
    except Exception as exc:
        raise RuntimeError(
            f"CT246 authenticated Sub-Engel action client is unavailable: {exc}"
        ) from exc
    return run_action


def _action_stdout_payload(remote: dict[str, Any]) -> dict[str, Any]:
    result = remote.get("result") if isinstance(remote.get("result"), dict) else {}
    stdout = str(result.get("stdout") or "").strip()
    if not stdout:
        return {}
    candidates = [stdout]
    candidates.extend(
        line.strip() for line in reversed(stdout.splitlines()) if line.strip()
    )
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except Exception:
            continue
        if isinstance(parsed, dict):
            return parsed
    return {}


def _remote_action_succeeded(remote: dict[str, Any]) -> bool:
    if remote.get("ok") is not True:
        return False
    result = remote.get("result") if isinstance(remote.get("result"), dict) else {}
    if int(result.get("return_code") or 0) != 0:
        return False
    payload = _action_stdout_payload(remote)
    return payload.get("ok") is not False


def _run_direct_sub_engel_work(
    prompt: str,
    work_order: dict[str, Any],
    selected: dict[str, Any],
    run_action_fn: Any | None = None,
) -> dict[str, Any]:
    """Run bounded review-only work through CT246's current paired session."""
    order_id = str(work_order.get("id") or "").strip()
    if not order_id:
        return {"ok": False, "error": "work order id is missing"}
    node_id = str(selected.get("node_id") or selected.get("hostname") or "DESKTOP-UE5A6GG").strip()
    payload = {
        "schema": "engel_sub_engel_direct_work_order_v1",
        "id": order_id,
        "order_id": order_id,
        "order_text": prompt,
        "proof_required": True,
        "target": "windows_sub_engel",
        "selected_node": selected,
        "source": "Engel AI Main visible chat",
    }
    if run_action_fn is not None:
        remote = run_action_fn(
            "direct_work.execute",
            url=str(selected.get("url") or "").strip() or None,
            node_kind="windows",
            node_id=node_id or None,
            payload={"work_order": payload, "client_timeout_seconds": 600},
        )
        direct = _action_stdout_payload(remote)
        remote_ok = _remote_action_succeeded(remote)
    else:
        server_merge = _server_merge_live_snapshot()
        server_url = _main_server_chat_url(server_merge)
        if not server_url:
            return {"ok": False, "error": "CT246 chat route is unavailable"}
        try:
            response = _post_json(
                server_url + "/sub-engel/direct-work",
                {"work_order": payload},
                timeout=float(
                    os.environ.get(
                        "ENGEL_CT246_SUB_DIRECT_WORK_HTTP_TIMEOUT_SECONDS",
                        "620",
                    )
                    or "620"
                ),
            )
        except Exception as exc:
            return {
                "ok": False,
                "error": _honest_sub_engel_dispatch_error(
                    f"CT246 Sub direct endpoint failed: {exc}",
                    selected,
                ),
                "ct246_server_url": server_url,
                "transient_pipe_error": _sub_engel_pipe_error_is_transient(str(exc)),
                "sub_engel_reachability": _sub_engel_node_reachable(selected),
            }
        direct = response.get("receipt") if isinstance(response.get("receipt"), dict) else {}
        remote = response
        remote_ok = response.get("ok") is True
    valid_engine = str(direct.get("worker_engine") or "") in {
        "local_llm_one_shot",
        "local_llm_server",
        "peft_lora_transformers",
    }
    local_llm_completed = bool(
        direct.get("local_llm_completed") is True
        or (
            valid_engine
            and direct.get("local_llm_attempted") is True
            and str(direct.get("worker_output") or "").strip()
        )
    )
    if not remote_ok or direct.get("ok") is not True or not local_llm_completed:
        return {
            "ok": False,
            "error": "CT246 paired Sub work did not return a completed local-model result",
            "remote": redact(remote),
            "direct": redact(direct),
        }
    returned_payload = {
        "schema": "engel_sub_engel_direct_work_return_v1",
        "ok": True,
        "order_id": order_id,
        "worker_id": node_id or "windows_sub_engel",
        "hostname": node_id or "windows_sub_engel",
        "completed_at_utc": iso_now(),
        "source": "CT246 paired direct_work.execute",
        "transport": "ct246_authenticated_direct_http",
        "worker_engine": direct.get("worker_engine"),
        "worker_output": direct.get("worker_output"),
        "llm_attempted": direct.get("local_llm_attempted") is True,
        "local_llm_completed": local_llm_completed,
        "model_output_trusted": False,
        "auto_apply": False,
        "requires_review_before_apply": True,
        "direct_result": redact(direct),
    }
    return_folder = Path(str(work_order.get("expected_return_folder") or ""))
    if not return_folder:
        return {"ok": False, "error": "CT246 transport return folder is missing"}
    return_folder.mkdir(parents=True, exist_ok=True)
    safe_node = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in (node_id or "windows_sub_engel"))
    return_path = return_folder / f"{safe_node}__{order_id}.done.json"
    write_json(return_path, returned_payload)
    return {
        "ok": True,
        "returned": True,
        "path": str(return_path),
        "payload": returned_payload,
        "remote": redact(remote),
    }


def _create_sub_engel_work_dispatch(prompt: str) -> dict[str, Any]:
    station = {
        "name": "Windows Sub-Engel",
        "type_label": "Windows Sub-Engel Agent",
        "skill_label": "Windows Sub-Engel Worker Skill",
        "equipment": "Windows Sub-Engel Node - LAN check-in",
        "bridge": "Windows Sub-Engel Check-in Preview",
    }
    order_id = "MAIN-MEETING-" + stamp()
    selected = {
        "node_id": "DESKTOP-UE5A6GG",
        "hostname": "DESKTOP-UE5A6GG",
        "url": "http://198.51.100.227:8776",
    }
    work_order = {
        "schema": "engel_ui_ct246_sub_engel_work_order_v1",
        "ok": True,
        "id": order_id,
        "order_id": order_id,
        "order_text": prompt,
        "job_type": "return_status",
        "target": "windows_sub_engel",
        "selected_node": selected,
        "expected_return_folder": str(
            ROOT / "run" / "sub_engel_transport" / "SUB_ENGEL_SENT_WORK"
        ),
        "transport": "ct246_authenticated_direct_http",
        "ct246_authoritative": True,
        "google_drive_used": False,
        "created_at_utc": iso_now(),
    }
    work_order_path = (
        ROOT
        / "run"
        / "sub_engel_transport"
        / "SUB_ENGEL_WORK_ORDERS"
        / f"{order_id}.json"
    )
    write_json(work_order_path, work_order)
    dispatch: dict[str, Any] = {
        "schema": "engel_ui_sub_engel_work_dispatch_v1",
        "ok": False,
        "requested": True,
        "station": station,
        "meeting_node_statuses": {
            "windows_sub_engel": {
                "node_id": selected["node_id"],
                "url": selected["url"],
                "source": "CT246 current paired session",
            }
        },
        "packet": {},
        "work_order": redact(work_order),
        "work_order_path": str(work_order_path),
        "selected_node": redact(selected),
        "remote_process_attempted": False,
        "remote_process": {},
        "returned": False,
        "return_result": {},
        "errors": [],
        "created_at_utc": iso_now(),
    }
    forbidden_reason = _sub_engel_forbidden_block(selected)
    if forbidden_reason:
        dispatch["ok"] = False
        dispatch["errors"].append({"stage": "forbidden_device_block", "error": forbidden_reason})
        return dispatch
    try:
        dispatch["remote_process_attempted"] = True
        ct246_run_action = _ct246_authenticated_run_action()
        dispatch["dispatch_transport"] = (
            "ct246_in_process_authenticated_action"
            if ct246_run_action is not None
            else "rog_to_ct246_authenticated_http"
        )
        expected_return = _expected_sub_engel_return_path(work_order)
        last_direct: dict[str, Any] = {}
        for attempt in range(1, 4):
            dispatch["direct_work_attempts"] = attempt
            if attempt > 1:
                dispatch["bounded_sub_engel_work_pipe_retry"] = True
                time.sleep(2 * (attempt - 1))
            last_direct = _run_direct_sub_engel_work(
                prompt,
                work_order,
                selected,
                run_action_fn=ct246_run_action,
            )
            if last_direct.get("ok") is True and last_direct.get("returned") is True:
                break
            probe = last_direct.get("sub_engel_reachability")
            if not isinstance(probe, dict):
                probe = _sub_engel_node_reachable(selected)
            if probe.get("reachable") is True:
                recovered = _wait_for_sub_engel_done_file(expected_return, 20)
                if recovered:
                    last_direct = {
                        "ok": True,
                        "returned": True,
                        "path": str(expected_return),
                        "payload": recovered,
                        "recovered_from_done_file": True,
                    }
                    break
            if not _sub_engel_pipe_error_is_transient(str(last_direct.get("error") or "")):
                break
        dispatch["remote_process"] = redact(last_direct.get("remote", {}))
        dispatch["direct_authenticated_attempted"] = True
        dispatch["direct_authenticated_result"] = redact(last_direct)
        if last_direct.get("ok") is True and last_direct.get("returned") is True:
            dispatch["ok"] = True
            dispatch["returned"] = True
            dispatch["return_result"] = redact(last_direct)
        else:
            dispatch["errors"].append(
                {
                    "stage": "ct246_direct_work",
                    "error": _honest_sub_engel_dispatch_error(
                        str(last_direct.get("error") or "Sub-Engel did not return"),
                        selected,
                        last_direct.get("sub_engel_reachability")
                        if isinstance(last_direct.get("sub_engel_reachability"), dict)
                        else None,
                    ),
                }
            )
    except Exception as exc:
        dispatch["errors"].append(
            {
                "stage": "ct246_direct_work",
                "error": _honest_sub_engel_dispatch_error(str(exc), selected),
            }
        )
    return dispatch


def _matching_phone_record(
    directory: Path,
    packet_id: str,
    worker_id: str,
    *,
    name_suffix: str = ".json",
) -> dict[str, Any] | None:
    if not directory.exists():
        return None
    matches: list[tuple[int, dict[str, Any]]] = []
    for path in directory.glob(f"*{name_suffix}"):
        payload = _load_json_object(path)
        if payload.get("packet_id") == packet_id and payload.get("worker_id") == worker_id:
            try:
                modified_ns = path.stat().st_mtime_ns
            except OSError:
                modified_ns = 0
            matches.append((modified_ns, {"path": str(path), "payload": payload}))
    return max(matches, key=lambda item: item[0])[1] if matches else None


def _valid_phone_claim_return_pair(
    packet_id: str,
    worker_id: str,
    result: Any,
    claim: Any,
) -> bool:
    if not isinstance(result, dict) or not isinstance(claim, dict):
        return False
    expected = (packet_id, worker_id)
    if (result.get("packet_id"), result.get("worker_id")) != expected:
        return False
    if (claim.get("packet_id"), claim.get("worker_id")) != expected:
        return False
    result_device = str(result.get("worker_device") or "").strip()
    claim_device = str(claim.get("worker_device") or "").strip()
    if not result_device or result_device != claim_device:
        return False
    if str(claim.get("timestamp_utc") or "").strip() == "":
        return False
    if claim.get("claim_type") != "append_only_protocol_record":
        return False
    for payload in (result, claim):
        if (
            payload.get("trusted_memory_write") is not False
            or payload.get("auto_apply") is not False
            or payload.get("safe_to_auto_apply") is not False
        ):
            return False
    return True


def _write_relay_record(path: Path, payload: dict[str, Any]) -> bool:
    if path.exists():
        return _load_json_object(path) == payload
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        tmp_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        tmp_path.replace(path)
    finally:
        tmp_path.unlink(missing_ok=True)
    return True


def _phone_result_for_packet(packet_id: str, worker_id: str) -> dict[str, Any] | None:
    local_result = _matching_phone_record(PHONE_RETURNED_DIR, packet_id, worker_id)
    local_claim = _matching_phone_record(
        PHONE_CLAIMED_DIR,
        packet_id,
        worker_id,
        name_suffix="_claim.json",
    )
    if local_result and local_claim and _valid_phone_claim_return_pair(
        packet_id,
        worker_id,
        local_result["payload"],
        local_claim["payload"],
    ):
        return {
            **local_result,
            "claim_path": local_claim["path"],
            "claim_payload": local_claim["payload"],
        }
    if not PHONE_RETURN_RELAY_URL:
        return None
    query = urllib.parse.urlencode(
        {"packet_id": packet_id, "worker_id": worker_id}
    )
    try:
        with urllib.request.urlopen(
            f"{PHONE_RETURN_RELAY_URL}?{query}", timeout=2.5
        ) as response:
            body = response.read(512 * 1024 + 1)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        return None
    except (OSError, urllib.error.URLError):
        return None
    if len(body) > 512 * 1024:
        return None
    try:
        relay = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    payload = relay.get("result") if isinstance(relay, dict) else None
    claim = relay.get("claim") if isinstance(relay, dict) else None
    if not _valid_phone_claim_return_pair(packet_id, worker_id, payload, claim):
        return None
    digest = hashlib.sha256(
        f"{packet_id}|{worker_id}".encode("utf-8")
    ).hexdigest()[:20]
    claim_path = PHONE_CLAIMED_DIR / f"rog_relay_{digest}_claim.json"
    local_path = (
        Path(local_result["path"])
        if local_result is not None
        else PHONE_RETURNED_DIR / f"rog_relay_{digest}_result.json"
    )
    if not _write_relay_record(claim_path, claim):
        return None
    if not _write_relay_record(local_path, payload):
        return None
    return {
        "path": str(local_path),
        "payload": payload,
        "claim_path": str(claim_path),
        "claim_payload": claim,
        "relay_source": PHONE_RETURN_RELAY_URL,
    }


def _wait_for_phone_results(assignments: list[dict[str, Any]], timeout_seconds: int) -> dict[str, Any]:
    deadline = time.time() + max(0, timeout_seconds)
    pending = {(str(item.get("packet_id") or ""), str(item.get("worker_id") or "")) for item in assignments}
    pending.discard(("", ""))
    returned: dict[str, Any] = {}
    while pending and time.time() <= deadline:
        for packet_id, worker_id in list(pending):
            result = _phone_result_for_packet(packet_id, worker_id)
            if result is not None:
                returned[worker_id] = result
                pending.remove((packet_id, worker_id))
        if pending:
            time.sleep(1.5)
    return {
        "ok": not pending,
        "returned": returned,
        "returned_count": len(returned),
        "pending": [{"packet_id": packet_id, "worker_id": worker_id} for packet_id, worker_id in sorted(pending)],
    }


def _conical_operator_request_block(prompt: str, limit: int = 2200) -> str:
    """Operator request plus implied app requirements for underspecified builds."""
    body = _clip(prompt, limit)
    try:
        import engel_build_lane

        extra = str(engel_build_lane.expand_underspecified_app_brief(prompt) or "").strip()
    except Exception:
        extra = ""
    if extra:
        return (
            body
            + "\n\nImplied requirements for this underspecified app:\n"
            + extra
        )
    return body


def _conical_build_profile(prompt: str) -> dict[str, Any]:
    try:
        import engel_build_lane

        description = engel_build_lane.is_build_request(prompt)
        if description is None:
            return {}
        size = engel_build_lane.classify_build_size(prompt)
    except Exception:
        return {}
    if size not in {"medium", "large", "expert"}:
        return {}
    return {
        "required": True,
        "build_size": size,
        "description": str(description),
    }


def _conical_job_plan(prompt: str, job_id: str) -> dict[str, Any]:
    profile = _conical_build_profile(prompt)
    if not profile:
        return {}
    tasks: list[dict[str, Any]] = []
    for index, template in enumerate(CONICAL_PHONE_TASKS, start=1):
        worker_id = str(template["worker_id"])
        tasks.append(
            {
                "task_id": f"{job_id}_phone_{index}",
                "worker_id": worker_id,
                "worker_kind": "android_remote_worker",
                "role": template["role"],
                "task_type": template["task_type"],
                "objective": template["objective"],
                "required": True,
            }
        )
    tasks.append(
        {
            "task_id": f"{job_id}_sub_engel",
            "worker_id": "DESKTOP-UE5A6GG",
            "worker_kind": "windows_sub_engel",
            "role": "architecture and integration reviewer",
            "task_type": "sub_engel_local_llm_review",
            "objective": (
                "Review the requested system architecture, module boundaries, data flow, "
                "integration contracts, and likely implementation failures. Return a "
                "candidate design review for Engel Main to evaluate."
            ),
            "required": True,
        }
    )
    return {
        "schema": "engel_conical_job_plan_v1",
        "job_id": job_id,
        "required": True,
        "build_size": profile["build_size"],
        "description": profile["description"],
        "expected_worker_count": len(tasks),
        "tasks": tasks,
        "created_at_utc": iso_now(),
    }


def _conical_meeting_checkin(
    task: dict[str, Any],
    job_id: str,
    status: str,
    detail: str = "",
    receipt_path: str = "",
) -> dict[str, Any]:
    worker_id = str(task.get("worker_id") or "unknown_worker")
    return _server_json(
        "POST",
        "/room/checkin",
        {
            "participant_id": worker_id,
            "name": worker_id.replace("android_worker_", "Android Worker ").replace("_", " ").title(),
            "kind": "conical_job_worker",
            "role": str(task.get("role") or "worker"),
            "status": status,
            "source": "Engel AI Main conical build orchestration",
            "capabilities": [str(task.get("task_type") or "bounded_worker_task")],
            "conical_job_id": job_id,
            "task_id": str(task.get("task_id") or ""),
            "current_task": str(task.get("objective") or ""),
            "result_detail": _clip(detail, 900),
            "worker_receipt_path": receipt_path,
        },
        timeout=4,
    )


def _create_conical_phone_assignment(task: dict[str, Any], prompt: str, job_id: str) -> dict[str, Any]:
    from engel_communication_queen_assignment_producer import create_assignment

    worker_id = str(task.get("worker_id") or "")
    objective = str(task.get("objective") or "")
    instructions = (
        f"Engel conical job: {job_id}\n"
        f"Assigned role: {task.get('role')}\n"
        f"Bounded task: {objective}\n\n"
        "Return only a candidate analysis for Engel Main to review and combine. "
        "Do not change Engel state or claim the final job is complete.\n\n"
        "User request:\n"
        + _conical_operator_request_block(prompt, 2200)
    )
    packet, packet_path, receipt_path = create_assignment(
        worker=worker_id,
        task_type=str(task.get("task_type") or "summarize_text"),
        title=f"{job_id} - {task.get('role')}",
        instructions=instructions,
    )
    return {
        "task_id": str(task.get("task_id") or ""),
        "worker_id": worker_id,
        "packet_id": str(packet.get("packet_id") or ""),
        "assignment_path": str(packet_path),
        "assignment_receipt_path": str(receipt_path),
        "task_type": str(task.get("task_type") or ""),
        "role": str(task.get("role") or ""),
        "dispatched_at_utc": iso_now(),
        "dispatched_epoch": time.time(),
    }


def _conical_phone_result(
    task: dict[str, Any],
    assignment: dict[str, Any],
    returned: dict[str, Any] | None,
) -> dict[str, Any]:
    worker_id = str(task.get("worker_id") or "")
    packet_id = str(assignment.get("packet_id") or "")
    if not isinstance(returned, dict):
        return {
            "task_id": task.get("task_id"),
            "worker_id": worker_id,
            "status": "failed_no_return",
            "returned": False,
            "error": "worker did not return before the bounded wait ended",
        }
    path = Path(str(returned.get("path") or ""))
    payload = returned.get("payload") if isinstance(returned.get("payload"), dict) else {}
    exact_match = (
        str(payload.get("packet_id") or "") == packet_id
        and str(payload.get("worker_id") or "") == worker_id
    )
    fresh = False
    try:
        fresh = path.is_file() and path.stat().st_mtime + 1 >= float(assignment.get("dispatched_epoch") or 0)
    except OSError:
        fresh = False
    candidate_only = bool(
        payload.get("trusted_memory_write") is False
        and payload.get("safe_to_auto_apply") is False
    )
    if not (exact_match and fresh and candidate_only):
        return {
            "task_id": task.get("task_id"),
            "worker_id": worker_id,
            "status": "failed_invalid_return",
            "returned": False,
            "error": "worker return was stale, mismatched, or violated the candidate-only contract",
            "return_path": str(path),
        }
    expected = {
        "conical_requirements_analysis": {
            "schema": "engel_android_conical_requirements_v1",
            "role": "requirements_analyst",
            "required": ("functional_requirements", "acceptance_criteria"),
            "allowed": (
                "schema",
                "role",
                "request_summary",
                "functional_requirements",
                "inputs",
                "outputs",
                "acceptance_criteria",
                "analysis_engine",
                "status",
                "human_review_required",
            ),
        },
        "conical_verification_plan": {
            "schema": "engel_android_conical_verification_v1",
            "role": "verification_planner",
            "required": ("test_matrix", "terminal_success_rule"),
            "allowed": (
                "schema",
                "role",
                "request_summary",
                "test_matrix",
                "terminal_success_rule",
                "analysis_engine",
                "status",
                "human_review_required",
            ),
        },
        "conical_dependency_risk_check": {
            "schema": "engel_android_conical_dependency_risk_v1",
            "role": "dependency_and_risk_checker",
            "required": ("dependencies", "risks", "deterministic_checks"),
            "allowed": (
                "schema",
                "role",
                "request_summary",
                "dependencies",
                "risks",
                "offline_constraints",
                "deterministic_checks",
                "analysis_engine",
                "status",
                "human_review_required",
            ),
        },
    }.get(str(task.get("task_type") or ""))
    raw_contribution = str(payload.get("draft_text") or "").strip()
    try:
        structured = json.loads(raw_contribution)
    except json.JSONDecodeError:
        structured = None
    schema_ok = bool(
        expected
        and isinstance(structured, dict)
        and structured.get("schema") == expected["schema"]
        and structured.get("role") == expected["role"]
        and structured.get("analysis_engine")
        == "on_device_deterministic_conical_v1"
        and structured.get("status") == "candidate_only"
        and structured.get("human_review_required") is True
        and all(structured.get(key) for key in expected["required"])
    )
    if not schema_ok:
        return {
            "task_id": task.get("task_id"),
            "worker_id": worker_id,
            "role": task.get("role"),
            "task_type": task.get("task_type"),
            "status": "failed_invalid_role_analysis",
            "returned": False,
            "packet_id": packet_id,
            "return_path": str(path),
            "error": (
                "phone return did not contain the required role-specific "
                "on-device conical analysis schema"
            ),
        }
    sanitized = {
        key: structured[key]
        for key in expected["allowed"]
        if key in structured
    }
    contribution = _clip(
        json.dumps(sanitized, ensure_ascii=False, sort_keys=True, indent=2),
        5000,
    )
    return {
        "task_id": task.get("task_id"),
        "worker_id": worker_id,
        "role": task.get("role"),
        "task_type": task.get("task_type"),
        "status": "returned",
        "returned": True,
        "packet_id": packet_id,
        "return_path": str(path),
        "result_type": str(payload.get("result_type") or ""),
        "contribution": contribution,
        "contribution_schema": structured.get("schema"),
        "analysis_engine": structured.get("analysis_engine"),
        "capability_snapshot_excluded_from_build_context": True,
        "assignment_echo_excluded_from_build_context": True,
        "candidate_only": True,
        "requires_main_review": True,
    }


def _conical_sub_result(task: dict[str, Any], dispatch: dict[str, Any]) -> dict[str, Any]:
    order = dispatch.get("work_order") if isinstance(dispatch.get("work_order"), dict) else {}
    result = dispatch.get("return_result") if isinstance(dispatch.get("return_result"), dict) else {}
    payload = result.get("payload") if isinstance(result.get("payload"), dict) else {}
    order_id = str(order.get("id") or "")
    exact_match = bool(order_id and str(payload.get("order_id") or "") == order_id)
    direct_result = payload.get("direct_result") if isinstance(payload.get("direct_result"), dict) else {}
    contribution = _clip(
        payload.get("worker_output") or direct_result.get("output") or "",
        7000,
    )
    if not (dispatch.get("returned") is True and exact_match):
        errors = dispatch.get("errors") if isinstance(dispatch.get("errors"), list) else []
        first_error = next(
            (
                str(item.get("error") or "").strip()
                for item in errors
                if isinstance(item, dict) and str(item.get("error") or "").strip()
            ),
            "",
        )
        direct_failure = (
            dispatch.get("direct_authenticated_result")
            if isinstance(dispatch.get("direct_authenticated_result"), dict)
            else {}
        )
        failure_text = (
            first_error
            or str(direct_failure.get("error") or "").strip()
            or "Sub-Engel did not return matching proof before the bounded wait ended"
        )
        return {
            "task_id": task.get("task_id"),
            "worker_id": task.get("worker_id"),
            "status": "failed_no_valid_return",
            "returned": False,
            "order_id": order_id,
            "error": failure_text,
            "dispatch_transport": str(dispatch.get("dispatch_transport") or ""),
            "dispatch_errors": redact(errors),
            "direct_failure": redact(
                {
                    "error": direct_failure.get("error"),
                    "returned": direct_failure.get("returned"),
                    "path": direct_failure.get("path"),
                }
            ),
        }
    return {
        "task_id": task.get("task_id"),
        "worker_id": task.get("worker_id"),
        "role": task.get("role"),
        "status": "returned",
        "returned": True,
        "order_id": order_id,
        "return_path": str(result.get("path") or ""),
        "contribution": contribution or "Sub-Engel returned matching architecture-review proof.",
        "candidate_only": True,
        "requires_main_review": True,
    }


def _conical_build_context(results: list[dict[str, Any]]) -> str:
    blocks: list[str] = []
    for item in results:
        if item.get("returned") is not True:
            continue
        contribution = str(item.get("contribution") or "").strip()
        worker_id = str(item.get("worker_id") or "")
        if worker_id.startswith("android_worker_"):
            if item.get("analysis_engine") != "on_device_deterministic_conical_v1":
                continue
            if not str(item.get("contribution_schema") or "").startswith(
                "engel_android_conical_"
            ):
                continue
        if not contribution:
            continue
        blocks.append(
            "WORKER: {worker}\nROLE: {role}\nCANDIDATE CONTRIBUTION:\n{body}".format(
                worker=worker_id,
                role=item.get("role") or "worker",
                body=_clip(contribution, 4200),
            )
        )
    return "\n\n".join(blocks)[:16000]


def _run_conical_build_orchestration(prompt: str) -> dict[str, Any]:
    profile = _conical_build_profile(prompt)
    if not profile:
        return {}
    job_id = "conical_job_" + stamp()
    plan = _conical_job_plan(prompt, job_id)
    tasks = plan.get("tasks") if isinstance(plan.get("tasks"), list) else []
    meeting_order = _submit_order(
        f"{prompt}\n\nConical {profile['build_size']} assemble on CT246 with Alpha, Beta, Gamma, and Sub-Engel."
    )
    workers = _phone_bridge_workers()
    android_ids = [
        str(task.get("worker_id") or "")
        for task in tasks
        if task.get("worker_kind") == "android_remote_worker"
    ]
    broker_gate = _broker_dispatch_gate(android_ids, job_kind="return_status")
    assignments: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for task in tasks:
        if task.get("worker_kind") != "android_remote_worker":
            continue
        worker_id = str(task.get("worker_id") or "")
        if worker_id in broker_gate["blocked"]:
            reason = str(broker_gate["blocked"][worker_id])
            results.append(
                {
                    "task_id": task.get("task_id"),
                    "worker_id": worker_id,
                    "status": "failed_worker_not_eligible",
                    "returned": False,
                    "error": f"device broker: {reason}",
                }
            )
            _conical_meeting_checkin(task, job_id, "failed", f"device broker blocked: {reason}")
            continue
        if workers.get(worker_id, {}).get("live") is not True:
            results.append(
                {
                    "task_id": task.get("task_id"),
                    "worker_id": worker_id,
                    "status": "failed_worker_not_live",
                    "returned": False,
                    "error": "worker has no fresh authenticated heartbeat",
                }
            )
            _conical_meeting_checkin(task, job_id, "failed", "worker is not live")
            continue
        try:
            assignment = _create_conical_phone_assignment(task, prompt, job_id)
            assignments.append(assignment)
            _conical_meeting_checkin(
                task,
                job_id,
                "working",
                "assignment dispatched; waiting for matching return",
                str(assignment.get("assignment_receipt_path") or ""),
            )
        except Exception as exc:
            errors.append({"worker_id": worker_id, "stage": "dispatch", "error": str(exc)})
            results.append(
                {
                    "task_id": task.get("task_id"),
                    "worker_id": worker_id,
                    "status": "failed_dispatch",
                    "returned": False,
                    "error": str(exc),
                }
            )
            _conical_meeting_checkin(task, job_id, "failed", str(exc))

    sub_task = next((task for task in tasks if task.get("worker_kind") == "windows_sub_engel"), {})
    if sub_task:
        try:
            sub_prompt = (
                f"Conical job {job_id}. Role: {sub_task.get('role')}. "
                f"Task: {sub_task.get('objective')} User request: "
                f"{_conical_operator_request_block(prompt, 2600)}"
            )
            _conical_meeting_checkin(sub_task, job_id, "working", "paired Sub-Engel review dispatched")
            sub_dispatch = _create_sub_engel_work_dispatch(sub_prompt)
            sub_result = _conical_sub_result(sub_task, sub_dispatch)
            results.append(sub_result)
            _conical_meeting_checkin(
                sub_task,
                job_id,
                "working_returned" if sub_result.get("returned") else "failed",
                str(sub_result.get("contribution") or sub_result.get("error") or ""),
                str(sub_result.get("return_path") or ""),
            )
        except Exception as exc:
            errors.append({"worker_id": sub_task.get("worker_id"), "stage": "dispatch", "error": str(exc)})
            results.append(
                {
                    "task_id": sub_task.get("task_id"),
                    "worker_id": sub_task.get("worker_id"),
                    "status": "failed_dispatch",
                    "returned": False,
                    "error": str(exc),
                }
            )
            _conical_meeting_checkin(sub_task, job_id, "failed", str(exc))

    wait = _wait_for_phone_results(assignments, CONICAL_PHONE_RETURN_WAIT_SECONDS) if assignments else {
        "ok": False,
        "returned": {},
        "returned_count": 0,
        "pending": [],
    }
    returned_by_worker = dict(wait.get("returned")) if isinstance(wait.get("returned"), dict) else {}
    task_by_worker = {str(task.get("worker_id") or ""): task for task in tasks}
    latest_assignment_by_worker = {
        str(assignment.get("worker_id") or ""): assignment
        for assignment in assignments
        if str(assignment.get("worker_id") or "")
    }
    retry_assignments: list[dict[str, Any]] = []
    missing_workers = [
        worker_id
        for worker_id in latest_assignment_by_worker
        if worker_id not in returned_by_worker
    ]
    for worker_id in missing_workers:
        task = task_by_worker.get(worker_id, {})
        original = latest_assignment_by_worker[worker_id]
        try:
            retry = _create_conical_phone_assignment(task, prompt, job_id)
            retry["dispatch_attempt"] = 2
            retry["retry_of_packet_id"] = str(original.get("packet_id") or "")
            assignments.append(retry)
            retry_assignments.append(retry)
            latest_assignment_by_worker[worker_id] = retry
            _conical_meeting_checkin(
                task,
                job_id,
                "working",
                "first packet had no return; one bounded fresh-packet retry dispatched",
                str(retry.get("assignment_receipt_path") or ""),
            )
        except Exception as exc:
            errors.append(
                {
                    "worker_id": worker_id,
                    "stage": "retry_dispatch",
                    "error": str(exc),
                }
            )
    if retry_assignments:
        retry_wait = _wait_for_phone_results(
            retry_assignments, CONICAL_PHONE_RETURN_WAIT_SECONDS
        )
        retry_returned = (
            retry_wait.get("returned")
            if isinstance(retry_wait.get("returned"), dict)
            else {}
        )
        returned_by_worker.update(retry_returned)
    existing_workers = {str(item.get("worker_id") or "") for item in results}
    for assignment in latest_assignment_by_worker.values():
        worker_id = str(assignment.get("worker_id") or "")
        result = _conical_phone_result(
            task_by_worker.get(worker_id, {}),
            assignment,
            returned_by_worker.get(worker_id),
        )
        if worker_id in existing_workers:
            results = [item for item in results if str(item.get("worker_id") or "") != worker_id]
        results.append(result)
        _conical_meeting_checkin(
            task_by_worker.get(worker_id, {}),
            job_id,
            "working_returned" if result.get("returned") else "failed",
            str(result.get("contribution") or result.get("error") or ""),
            str(result.get("return_path") or ""),
        )

    returned_count = sum(1 for item in results if item.get("returned") is True)
    expected_count = int(plan.get("expected_worker_count") or 0)
    all_returned = bool(expected_count and returned_count == expected_count)
    receipt = {
        "schema": "engel_conical_build_orchestration_v1",
        "ok": all_returned,
        "required": True,
        "status": "workers_returned" if all_returned else "failed_worker_returns",
        "job_id": job_id,
        "build_size": profile["build_size"],
        "plan": plan,
        "dispatch_broker_gate": broker_gate,
        "meeting_room_order": redact(meeting_order),
        "meeting_room_order_id": str(meeting_order.get("order_id") or ""),
        "assignments": assignments,
        "phone_retry_assignment_count": len(retry_assignments),
        "worker_results": sorted(results, key=lambda item: str(item.get("worker_id") or "")),
        "expected_worker_count": expected_count,
        "returned_worker_count": returned_count,
        "failed_worker_count": max(0, expected_count - returned_count),
        "build_context": _conical_build_context(results),
        "errors": errors,
        "started_at_utc": plan.get("created_at_utc"),
        "workers_finished_at_utc": iso_now(),
        "candidate_outputs_reviewed_by_main": True,
        "trusted_memory_write": False,
    }
    CONICAL_REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    receipt_path = CONICAL_REPORT_ROOT / f"{job_id}.json"
    receipt["receipt_path"] = str(receipt_path)
    write_json(receipt_path, receipt)
    return receipt


def _finalize_conical_build_orchestration(
    orchestration: dict[str, Any],
    build_receipt: dict[str, Any],
) -> dict[str, Any]:
    if not orchestration:
        return orchestration
    workers_ok = orchestration.get("ok") is True
    build_ok = build_receipt.get("build_verified") is True
    final_ok = bool(workers_ok and build_ok)
    orchestration["build_verified"] = build_ok
    orchestration["final_ok"] = final_ok
    orchestration["final_status"] = "finished" if final_ok else "failed"
    orchestration["finished_at_utc"] = iso_now()
    orchestration["workspace_path"] = str(
        ((build_receipt.get("action") or {}).get("result") or {}).get("path")
        if isinstance(build_receipt.get("action"), dict)
        else ""
    )
    orchestration["package_path"] = str((build_receipt.get("build_package") or {}).get("path") or "")
    summary = (
        f"Conical job {orchestration.get('job_id')} {orchestration['final_status']}: "
        f"{orchestration.get('returned_worker_count')}/{orchestration.get('expected_worker_count')} "
        f"worker returns; CT246 build_verified={build_ok}."
    )
    order_id = str(orchestration.get("meeting_room_order_id") or "")
    if order_id:
        orchestration["meeting_room_completion"] = redact(
            _complete_order(order_id, summary, source="Engel conical build aggregator")
        )
    receipt_path_text = str(orchestration.get("receipt_path") or "").strip()
    if receipt_path_text:
        receipt_path = Path(receipt_path_text)
        write_json(receipt_path, orchestration)
    return orchestration


def _create_phone_assignment(worker_id: str, prompt: str) -> dict[str, Any]:
    from engel_communication_queen_assignment_producer import create_assignment

    classify = "classif" in str(prompt or "").casefold()
    task_type = "classify_file" if classify else "return_status"
    title = (
        f"Chat-requested drafting classification for {worker_id}"
        if classify
        else f"Chat-requested phone worker status and useful check for {worker_id}"
    )
    work = (
        "Classify the supplied drafting request as commercial, residential, sustainability, or needs clarification. "
        "Return the selected label and a short reason."
        if classify
        else "Return a current Android Remote Worker status/capability receipt and one useful bounded check result for this chat request. "
        "Include phone identity, transport, battery/storage/app capability snapshot when available."
    )
    instructions = (
        "Agent Meeting Room phone work packet\n\n"
        f"Worker: {worker_id}\n"
        f"Job type: {task_type}\n\n"
        "Work:\n"
        f"{work} Keep output candidate-only. Do not execute shell commands, do not call providers, "
        "do not mutate Engel source/routes/queues, do not write trusted memory, and do not auto-apply anything.\n\n"
        "User chat request:\n"
        + _clip(prompt, 900)
    )
    packet, packet_path, receipt_path = create_assignment(
        worker=worker_id,
        task_type=task_type,
        title=title,
        instructions=instructions,
    )
    return {
        "worker_id": worker_id,
        "packet_id": str(packet.get("packet_id") or ""),
        "assignment_path": str(packet_path),
        "assignment_receipt_path": str(receipt_path),
        "task_type": task_type,
        "title": title,
    }


def _attach_phone_work_dispatch(prompt: str, receipt: dict[str, Any], started: float) -> dict[str, Any]:
    if not _prompt_requests_phone_work(prompt):
        return receipt
    workers = _phone_bridge_workers()
    requested = _requested_phone_workers(prompt, workers)
    live_requested = [worker_id for worker_id in requested if workers.get(worker_id, {}).get("live") is True]
    broker_gate = _broker_dispatch_gate(live_requested, job_kind="return_status")
    dispatchable = [worker_id for worker_id in live_requested if worker_id in broker_gate["eligible"]]
    dispatch: dict[str, Any] = {
        "schema": "engel_ui_phone_work_dispatch_v1",
        "ok": False,
        "requested": True,
        "approved_dir": str(PHONE_APPROVED_DIR),
        "returned_dir": str(PHONE_RETURNED_DIR),
        "phone_bridge_state_path": str(PHONE_BRIDGE_STATE_PATH),
        "workers": workers,
        "requested_workers": requested,
        "live_requested_workers": live_requested,
        "device_broker_gate": broker_gate,
        "broker_eligible_workers": dispatchable,
        "assignments": [],
        "wait": {},
        "errors": [],
        "created_at_utc": iso_now(),
    }
    for worker_id in live_requested:
        if worker_id not in dispatchable:
            dispatch["errors"].append({
                "worker_id": worker_id,
                "error": f"device broker: {broker_gate['blocked'].get(worker_id, 'not eligible')}",
            })
            continue
        try:
            dispatch["assignments"].append(_create_phone_assignment(worker_id, prompt))
        except Exception as exc:
            dispatch["errors"].append({"worker_id": worker_id, "error": str(exc)})
    try:
        wait_seconds = int(os.environ.get("ENGEL_PHONE_WORK_RETURN_WAIT_SECONDS", "24") or "24")
    except ValueError:
        wait_seconds = 24
    if dispatch["assignments"]:
        dispatch["wait"] = _wait_for_phone_results(dispatch["assignments"], wait_seconds)
    dispatch["ok"] = bool(dispatch["assignments"])
    returned_count = int((dispatch.get("wait") or {}).get("returned_count") or 0)
    assigned_labels = [workers.get(worker_id, {}).get("label", worker_id) for worker_id in dispatchable]
    if dispatch["assignments"]:
        reply = (
            "I sent real phone work to "
            + ", ".join(str(label) for label in assigned_labels)
            + f". Queued {len(dispatch['assignments'])} approved return_status packet(s)"
        )
        if returned_count:
            reply += f" and received {returned_count} phone return(s)."
        else:
            reply += "; no phone return came back before the short UI wait ended."
    elif requested:
        reply = "I could not queue phone work because no requested phone worker has a fresh live heartbeat right now."
    else:
        reply = "I could not queue phone work because no Android worker is registered in the phone bridge state."
    receipt["assistant_reply_before_phone_dispatch"] = receipt.get("assistant_reply") or receipt.get("assistant_output_text") or ""
    receipt["assistant_reply"] = reply
    receipt["assistant_output_text"] = reply
    receipt["visible_reply_source"] = "main_server_chat_plus_phone_work_dispatch"
    receipt["phone_work_requested"] = True
    receipt["phone_work_assigned"] = bool(dispatch["assignments"])
    receipt["phone_work_returned_count"] = returned_count
    receipt["phone_work_dispatch"] = dispatch
    receipt["creation_job"] = True
    receipt["chat_only_no_android_or_sub_engel"] = False
    if dispatch["assignments"]:
        receipt["ok"] = True
        receipt["status"] = "phone work dispatch queued through Engel UI chat"
        receipt["readable_output_captured"] = True
        receipt["visible_reply_weak"] = False
        receipt["ui_reply_guard_triggered"] = False
    receipt["android_and_sub_engel_policy"] = "Explicit phone-work chat requests create bounded review-only Android worker assignments."
    receipt["device_selection"] = {
        "schema": "engel_ui_chat_routing_policy_v1",
        "ok": bool(dispatch["assignments"]),
        "run_id": str(receipt.get("run_id") or ""),
        "routing_policy": "phone_work_dispatch",
        "reason": "User explicitly asked for phone/Android worker work; device broker eligibility enforced.",
        "devices": dispatchable,
        "device_broker_gate": broker_gate,
        "decisions": [
            {
                "device": worker_id,
                "decision": "approved return_status assignment queued",
                "assignment_packet": next(
                    (item for item in dispatch["assignments"] if item.get("worker_id") == worker_id),
                    {},
                ),
            }
            for worker_id in dispatchable
        ],
    }
    receipt["latency_ms"] = int((time.perf_counter() - started) * 1000)
    return receipt


def _attach_sub_engel_work_dispatch(prompt: str, receipt: dict[str, Any], started: float) -> dict[str, Any]:
    if not _prompt_requests_sub_engel_work(prompt):
        return receipt
    dispatch: dict[str, Any] = {
        "schema": "engel_ui_sub_engel_work_dispatch_v1",
        "ok": False,
        "requested": True,
        "errors": [],
        "created_at_utc": iso_now(),
    }
    try:
        dispatch = _create_sub_engel_work_dispatch(prompt)
    except Exception as exc:
        dispatch["errors"].append({"stage": "create_sub_engel_work_order", "error": str(exc)})
    selected = dispatch.get("selected_node") if isinstance(dispatch.get("selected_node"), dict) else {}
    node_label = (
        str(selected.get("hostname") or selected.get("node_id") or "").strip()
        or "Windows Sub-Engel"
    )
    order = dispatch.get("work_order") if isinstance(dispatch.get("work_order"), dict) else {}
    previous_reply = str(receipt.get("assistant_reply") or receipt.get("assistant_output_text") or "").strip()
    if dispatch.get("ok"):
        addition = f"I sent real Sub-Engel work to {node_label} through CT246"
        if dispatch.get("returned"):
            addition += " and received its matching local-model return."
        else:
            addition += ", but no matching return was received."
    else:
        err = "; ".join(str(item.get("error") or item) for item in dispatch.get("errors", []) if isinstance(item, dict))
        addition = "I could not complete Sub-Engel work through CT246"
        if err:
            addition += f": {err}"
        addition += "."
    if previous_reply:
        reply = previous_reply.rstrip()
        if not reply.endswith((".", "!", "?")):
            reply += "."
        reply = reply + " " + addition
    else:
        reply = addition
    receipt["assistant_reply_before_sub_engel_dispatch"] = previous_reply
    receipt["assistant_reply"] = reply
    receipt["assistant_output_text"] = reply
    receipt["sub_engel_work_requested"] = True
    receipt["sub_engel_work_assigned"] = bool(dispatch.get("ok"))
    receipt["sub_engel_work_returned"] = bool(dispatch.get("returned"))
    receipt["sub_engel_work_dispatch"] = dispatch
    receipt["chat_only_no_android_or_sub_engel"] = False
    receipt["visible_reply_source"] = str(receipt.get("visible_reply_source") or "chat") + "_plus_sub_engel_work_dispatch"
    receipt["android_and_sub_engel_policy"] = "Explicit all-device/Sub-Engel chat requests use CT246 authenticated direct work and bounded Android worker packets."
    receipt["ok"] = bool(receipt.get("ok") is True or dispatch.get("ok"))
    receipt["readable_output_captured"] = True
    receipt["visible_reply_weak"] = False
    receipt["ui_reply_guard_triggered"] = False
    selection = receipt.get("device_selection") if isinstance(receipt.get("device_selection"), dict) else {}
    devices = selection.get("devices") if isinstance(selection.get("devices"), list) else []
    decisions = selection.get("decisions") if isinstance(selection.get("decisions"), list) else []
    if "windows_sub_engel" not in devices:
        devices.append("windows_sub_engel")
    decisions.append(
        {
            "device": "windows_sub_engel",
            "node": node_label,
            "decision": "CT246 direct local-model return received" if dispatch.get("ok") else "CT246 direct work failed",
            "work_order": order,
        }
    )
    selection.update(
        {
            "schema": selection.get("schema") or "engel_ui_chat_routing_policy_v1",
            "ok": bool(selection.get("ok") is True or dispatch.get("ok")),
            "run_id": selection.get("run_id") or str(receipt.get("run_id") or ""),
            "routing_policy": "all_device_work_dispatch" if _prompt_requests_device_work(prompt) else "sub_engel_work_dispatch",
            "reason": "User asked for Sub-Engel/all-device work through the chat UI.",
            "devices": devices,
            "decisions": decisions,
        }
    )
    receipt["device_selection"] = selection
    receipt["latency_ms"] = int((time.perf_counter() - started) * 1000)
    return receipt


def _attach_device_work_dispatch(prompt: str, receipt: dict[str, Any], started: float) -> dict[str, Any]:
    receipt = _attach_phone_work_dispatch(prompt, receipt, started)
    receipt = _attach_sub_engel_work_dispatch(prompt, receipt, started)
    device_work_used = bool(
        receipt.get("phone_work_assigned") is True
        or receipt.get("sub_engel_work_assigned") is True
    )
    if device_work_used:
        receipt["agent_meeting_room_used"] = True
        receipt["meeting_room_server_used"] = True
        receipt["creation_job"] = True
        receipt["chat_only_no_android_or_sub_engel"] = False
    sub_dispatch = receipt.get("sub_engel_work_dispatch")
    if isinstance(sub_dispatch, dict):
        work_order = sub_dispatch.get("work_order")
        if isinstance(work_order, dict) and work_order.get("id"):
            receipt["meeting_room_order_id"] = str(work_order["id"])
    return receipt


def _run_explicit_device_work_request(prompt: str, started: float) -> dict[str, Any]:
    """Dispatch explicit device work before model generation.

    Device status and classification requests are deterministic orchestration
    work. Waiting for a model response first can consume Flutter's 90-second
    idle budget and kill the turn before a phone packet is created.
    """
    receipt: dict[str, Any] = {
        "schema": "engel_ui_chat_meeting_room_llm_reply_v1",
        "ok": True,
        "status": "explicit device work routed through Agent Meeting Room",
        "updated_at_utc": iso_now(),
        "run_id": "ui_chat_device_work_" + stamp(),
        "prompt": prompt,
        "ui_entry_path": "Engel Main chat -> Agent Meeting Room device dispatch",
        "assistant_reply": "I am checking the requested devices now.",
        "assistant_output_text": "I am checking the requested devices now.",
        "provider": "engel-agent-meeting-room-local-dispatch",
        "runtime_provider": "engel-agent-meeting-room-local-dispatch",
        "selected_provider": "local_device_orchestration",
        "provider_api_enabled": False,
        "network_enabled": False,
        "local_llm_only": True,
        "runs_inference": False,
        "creation_job": True,
        "chat_only_no_android_or_sub_engel": False,
        "agent_meeting_room_used": False,
        "meeting_room_server_used": False,
        "visible_reply_source": "local_device_orchestration",
        "ui_reply_guard_triggered": False,
    }
    receipt = _attach_device_work_dispatch(prompt, receipt, started)
    receipt["latency_ms"] = int((time.perf_counter() - started) * 1000)
    return _write_ui_chat_receipt(receipt, prompt)


def _server_chat_unavailable_receipt(
    prompt: str,
    started: float,
    server_merge: dict[str, Any],
    server_chat_url: str,
    error: str,
) -> dict[str, Any]:
    route = str(server_merge.get("ssh_route") or "ssh root@192.0.2.50 -p 24622")
    reply = (
        "Server chat is not reachable yet, so I kept the slow laptop model off. "
        "This can happen even when SSH was already set up; the CT-forwarded port is not reachable. "
        "Open Connection Help in Engel and tap Repair connection. "
        f"Server route: {route}. Expected local chat URL: {server_chat_url or 'not configured'}."
    )
    receipt = {
        "schema": "engel_ui_chat_meeting_room_llm_reply_v1",
        "ok": True,
        "status": "server chat unavailable; laptop local model fallback disabled to avoid slow chat",
        "updated_at_utc": iso_now(),
        "run_id": "ui_chat_server_required_unavailable_" + stamp(),
        "prompt": prompt,
        "prompt_chars": len(prompt),
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "ui_entry_path": "Engel Main chat -> server-first chat route",
        "assistant_reply": reply,
        "assistant_output_text": reply,
        "visible_reply_source": "server_required_unavailable",
        "visible_reply_weak": False,
        "ui_reply_guard_triggered": True,
        "server_chat_required": True,
        "main_server_chat_attempted": bool(server_chat_url),
        "main_server_chat_url": server_chat_url,
        "main_server_chat_error": error,
        "connection_doctor_available": True,
        "connection_doctor_script": str(ROOT / "tools" / "engel_connection_loop_doctor.py"),
        "connection_doctor_gui": str(ROOT / "tools" / "engel_connection_loop_doctor_gui.py"),
        "connection_doctor_reports": str(ROOT / "reports" / "connection_loop_doctor"),
        "main_server_chat_fallback_to_laptop_local": False,
        "engel_main_server_merge": server_merge,
        "engel_main_server_merge_enabled": bool(server_merge.get("enabled")),
        "engel_main_server_peer": server_merge.get("server_peer", "engel-ai-main CT 246"),
        "engel_main_server_ssh_route": route,
        "creation_job": False,
        "chat_only_no_android_or_sub_engel": True,
        "agent_meeting_room_used": False,
        "meeting_room_server_used": False,
        "meeting_room_reply": "",
        "local_llm_reply": "",
        "local_llm_only": False,
        "provider": "engel-main-server-chat-required",
        "runtime_provider": "engel-main-server-chat-required",
        "selected_provider": "main_server_chat",
        "provider_api_enabled": False,
        "network_enabled": True,
        "model_process_started": False,
        "runtime_process_started": False,
        "runs_inference": False,
        "loads_model": False,
        "storage_mutation_performed": False,
        "vault_mount_created": False,
        "background_worker_started": False,
        "latency_ms": int((time.perf_counter() - started) * 1000),
    }
    return _write_ui_chat_receipt(receipt, prompt)


# When the server chat lane fails, the failure detail is stashed here so the
# local-lane receipt can record it honestly (attempted, error, fell back).
_LAST_SERVER_CHAT_FAILURE: dict[str, Any] = {}


def _rog_gpu_chat_healthy() -> bool:
    """True when the ROG-local llama.cpp GPU server (:8899) answers — a FAST
    local fallback exists, so refusing to chat would be pure downtime."""
    try:
        request = urllib.request.Request(
            "http://127.0.0.1:8899/v1/models", headers={"Accept": "application/json"}
        )
        with urllib.request.urlopen(request, timeout=2) as response:
            return response.status == 200
    except Exception:
        return False


def _server_chat_local_fallback_enabled() -> bool:
    value = os.environ.get("ENGEL_MAIN_SERVER_CHAT_LOCAL_FALLBACK", "").strip().lower()
    if value:
        return value in {"1", "true", "yes", "on"}
    allow_laptop = os.environ.get("ENGEL_MAIN_ALLOW_LAPTOP_LOCAL_FALLBACK", "").strip().lower()
    if allow_laptop:
        return allow_laptop in {"1", "true", "yes", "on"}
    # (2026-07-21) The blanket default-OFF predates the ROG GPU big lane. With
    # CT246 down, EVERY UI turn (local and provider pipes alike) died with the
    # canned "server chat is not reachable" reply even though :8899 answers in
    # 1-4s locally. Auto-enable the fallback ONLY when the GPU server is
    # healthy — the original no-slow-CPU-chat intent stays: with no GPU lane,
    # the honest unavailable message still wins over a 60s+ CPU generation.
    return _rog_gpu_chat_healthy()


def _server_chat_preflight(server_chat_url: str) -> tuple[bool, str]:
    """Fail fast when the server chat link is dead. A tunnel listener accepts
    TCP even when the remote service is down, so a cheap TCP check is not
    enough - probe /health with a short budget before committing to the slow
    /chat POST (which is capped at ENGEL_MAIN_SERVER_CHAT_HTTP_TIMEOUT_CAP and
    used to eat 120s per turn when the link was dead)."""
    budget = float(os.environ.get("ENGEL_MAIN_SERVER_CHAT_PREFLIGHT_TIMEOUT", "4") or "4")
    try:
        parsed = urllib.parse.urlsplit(server_chat_url)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        with socket.create_connection((host, port), timeout=min(2.0, budget)):
            pass
    except OSError as exc:
        return False, f"server chat tunnel TCP unreachable: {exc}"
    try:
        request = urllib.request.Request(server_chat_url + "/health", headers={"Accept": "application/json"})
        with urllib.request.urlopen(request, timeout=budget) as response:
            body = response.read().decode("utf-8", errors="replace")
        parsed_body = json.loads(body)
        if isinstance(parsed_body, dict) and parsed_body.get("ok") is True:
            return True, ""
        return False, "server chat /health returned not-ok"
    except Exception as exc:
        return False, f"server chat /health failed within {budget:.0f}s: {exc}"


def _run_main_server_chat(
    prompt: str,
    timeout: int,
    max_tokens: int,
    temperature: float,
    started: float,
    server_merge: dict[str, Any],
) -> dict[str, Any] | None:
    _LAST_SERVER_CHAT_FAILURE.clear()
    server_chat_url = _main_server_chat_url(server_merge)
    required = _main_server_chat_required(server_merge)
    conical_orchestration: dict[str, Any] = {}
    if not server_chat_url:
        return None if not required else _server_chat_unavailable_receipt(prompt, started, server_merge, "", "server chat URL not configured")

    def _fail(error: str) -> dict[str, Any] | None:
        fallback_enabled = _server_chat_local_fallback_enabled()
        _LAST_SERVER_CHAT_FAILURE.update(
            {
                "main_server_chat_attempted": True,
                "main_server_chat_used": False,
                "main_server_chat_url": server_chat_url,
                "main_server_chat_error": error,
                "main_server_chat_fallback_to_laptop_local": fallback_enabled,
            }
        )
        if required and (not fallback_enabled or conical_orchestration):
            failed = _server_chat_unavailable_receipt(
                prompt,
                started,
                server_merge,
                server_chat_url,
                error,
            )
            if conical_orchestration:
                finalized = _finalize_conical_build_orchestration(
                    conical_orchestration,
                    failed,
                )
                failed["conical_orchestration"] = finalized
                failed["conical_job_status"] = "failed"
            return failed
        return None  # fall through to the local lane, recorded honestly

    preflight_ok, preflight_error = _server_chat_preflight(server_chat_url)
    if not preflight_ok:
        return _fail(preflight_error)

    if _conical_build_profile(prompt):
        conical_orchestration = _run_conical_build_orchestration(prompt)

    payload = _main_server_chat_payload(
        prompt,
        timeout,
        max_tokens,
        temperature,
        server_merge,
        conical_orchestration,
    )
    if conical_orchestration:
        timeout_cap = float(
            os.environ.get("ENGEL_MAIN_SERVER_BUILD_HTTP_TIMEOUT_CAP", "2100")
            or "2100"
        )
    else:
        timeout_cap = float(
            os.environ.get("ENGEL_MAIN_SERVER_CHAT_HTTP_TIMEOUT_CAP", "120")
            or "120"
        )
    request_timeout = max(10.0, min(timeout_cap, float(timeout)))
    try:
        response = _post_json(server_chat_url + "/chat", payload, timeout=request_timeout)
    except Exception as exc:
        return _fail(str(exc))

    nested = response.get("receipt") if isinstance(response.get("receipt"), dict) else {}
    server_receipt = dict(nested)
    reply = (
        _assistant_reply(server_receipt)
        or str(response.get("assistant_reply") or response.get("assistant_output_text") or "").strip()
    )
    if not reply:
        return _fail("server returned no assistant reply")

    original_server_reply = reply
    reply, humanizer_meta = improve_visible_reply(prompt, reply, source="ui_main_server_chat_visible_reply")
    route_ok = bool(response.get("ok") is True or server_receipt.get("ok") is True)
    receipt = dict(server_receipt)
    receipt.update(
        {
            "schema": "engel_ui_chat_meeting_room_llm_reply_v1",
            "ok": route_ok,
            "status": str(response.get("status") or server_receipt.get("status") or "chat replied through Engel Main server CT"),
            "updated_at_utc": iso_now(),
            "run_id": "ui_chat_main_server_" + stamp(),
            "prompt": prompt,
            "prompt_chars": len(prompt),
            "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "ui_entry_path": "Engel Main chat -> ROG tunnel -> engel-ai-main CT 246 chat service",
            "assistant_reply": reply,
            "assistant_output_text": reply,
            "visible_reply_source": "main_server_chat",
            "visible_reply_weak": _weak_visible_reply(reply),
            "server_original_reply_preview": original_server_reply[:500],
            "chat_humanizer": humanizer_meta,
            "chat_humanizer_used": bool(humanizer_meta.get("reply_changed")),
            "humanizer_reference_loaded": bool(humanizer_meta.get("humanizer_reference_loaded")),
            "workspace_registry_loaded": bool(humanizer_meta.get("workspace_registry_loaded")),
            "ui_reply_guard_triggered": False,
            "main_server_chat_attempted": True,
            "main_server_chat_used": True,
            "main_server_chat_url": server_chat_url,
            "main_server_chat_fallback_to_laptop_local": False,
            "server_chat_required": required,
            "engel_main_server_merge": server_merge,
            "engel_main_server_merge_enabled": bool(server_merge.get("enabled")),
            "engel_main_server_peer": server_merge.get("server_peer", "engel-ai-main CT 246"),
            "engel_main_server_ssh_route": server_merge.get("ssh_route", "ssh root@192.0.2.50 -p 24622"),
            "creation_job": _is_creation_job(prompt),
            "chat_only_no_android_or_sub_engel": not _is_creation_job(prompt),
            "agent_meeting_room_used": bool(server_receipt.get("agent_meeting_room_used") is True),
            "meeting_room_server_used": bool(server_receipt.get("meeting_room_server_used") is True),
            "meeting_room_reply": str(
                (server_receipt.get("meeting_room_server_response") or {}).get("status")
                if isinstance(server_receipt.get("meeting_room_server_response"), dict)
                else ""
            ),
            "meeting_room_server_response": server_receipt.get("meeting_room_server_response", {}),
            "local_llm_reply": reply,
            "local_llm_only": server_receipt.get("local_llm_only") is True,
            "provider": response.get("provider") or server_receipt.get("provider") or "engel-main-server-chat",
            "runtime_provider": response.get("runtime_provider") or server_receipt.get("runtime_provider") or "engel-main-server-chat-service",
            "selected_provider": server_receipt.get("selected_provider") or "main_server_chat",
            "provider_api_enabled": server_receipt.get("provider_api_enabled") is True,
            "network_enabled": server_receipt.get("network_enabled") is True,
            "model_process_started": server_receipt.get("model_process_started"),
            "runtime_process_started": server_receipt.get("runtime_process_started"),
            "runs_inference": server_receipt.get("runs_inference"),
            "loads_model": server_receipt.get("loads_model"),
            "latency_ms": int((time.perf_counter() - started) * 1000),
        }
    )
    if conical_orchestration:
        conical_orchestration = _finalize_conical_build_orchestration(
            conical_orchestration,
            receipt,
        )
        receipt["conical_orchestration"] = conical_orchestration
        receipt["conical_job_id"] = str(conical_orchestration.get("job_id") or "")
        receipt["conical_job_status"] = str(conical_orchestration.get("final_status") or "failed")
        receipt["conical_worker_returned_count"] = int(conical_orchestration.get("returned_worker_count") or 0)
        receipt["conical_worker_expected_count"] = int(conical_orchestration.get("expected_worker_count") or 0)
        receipt["agent_meeting_room_used"] = True
        receipt["meeting_room_server_used"] = True
        receipt["chat_only_no_android_or_sub_engel"] = False
        worker_summary = (
            f"Worker assembly: {receipt['conical_worker_returned_count']}/"
            f"{receipt['conical_worker_expected_count']} required workers returned; "
            f"final conical status: {receipt['conical_job_status'].upper()}."
        )
        current_reply = str(receipt.get("assistant_reply") or receipt.get("assistant_output_text") or "").rstrip()
        receipt["assistant_reply"] = current_reply + "\n\n" + worker_summary
        receipt["assistant_output_text"] = receipt["assistant_reply"]
    else:
        receipt = _attach_device_work_dispatch(prompt, receipt, started)
    return _write_ui_chat_receipt(receipt, prompt)


def _server_json(method: str, path: str, payload: dict[str, Any] | None = None, timeout: float = 4.0) -> dict[str, Any]:
    base_url = _meeting_room_server_url()
    if not base_url:
        return {"ok": False, "server_enabled": False, "reason": "Meeting Room server disabled"}
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(base_url + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
    except Exception as exc:
        return {
            "ok": False,
            "server_enabled": False,
            "meeting_room_server_url": base_url,
            "reason": str(exc),
        }
    try:
        parsed = json.loads(body)
    except Exception as exc:
        return {
            "ok": False,
            "server_enabled": False,
            "meeting_room_server_url": base_url,
            "reason": f"server returned non-json: {exc}",
            "raw": body[-1000:],
        }
    if not isinstance(parsed, dict):
        return {
            "ok": False,
            "server_enabled": False,
            "meeting_room_server_url": base_url,
            "reason": "server returned non-object JSON",
        }
    parsed.setdefault("meeting_room_server_url", base_url)
    return parsed


def _server_checkin() -> dict[str, Any]:
    return _server_json(
        "POST",
        "/room/checkin",
        {
            "participant_id": os.environ.get("COMPUTERNAME", "engel_ai_main"),
            "name": "Engel AI Main",
            "kind": "engel_ai_main",
            "role": "main_chat_controller",
            "status": "online",
            "source": "tools/run_engel_ui_chat_meeting_room_llm.py",
            "capabilities": ["local_llm_chat", "meeting_room_order_submit", "meeting_room_order_complete"],
        },
        timeout=2.5,
    )


def _run_local_chat(prompt: str, timeout: int, max_tokens: int, temperature: float) -> dict[str, Any]:
    from run_engel_standalone_chat_llm import run_chat

    return run_chat(
        prompt=prompt,
        timeout=max(1, timeout),
        max_tokens=max(1, max_tokens),
        temperature=temperature,
        provider="local",
    )


def _submit_order(prompt: str) -> dict[str, Any]:
    _server_checkin()
    server_result = _server_json(
        "POST",
        "/room/order",
        {"order_text": prompt, "source": "Engel Flutter Main Chat"},
        timeout=12,
    )
    if server_result.get("accepted"):
        return server_result
    from engel_agent_meeting_room import submit_order_from_engel_main_ui

    result = submit_order_from_engel_main_ui(prompt, source="Engel Flutter Main Chat")
    result["meeting_room_server_fallback"] = server_result
    if result.get("accepted"):
        return result
    effective = "Run Engel UI chat work order through Agent Meeting Room: " + prompt
    result = submit_order_from_engel_main_ui(effective, source="Engel Flutter Main Chat")
    result["effective_order_text"] = effective
    result["meeting_room_server_fallback"] = server_result
    return result


def _complete_order(order_id: str, reply: str, source: str = "Engel Flutter Main Chat") -> dict[str, Any]:
    _apply_chat_safe_meeting_room_defaults()
    server_result = _server_json(
        "POST",
        "/room/complete",
        {"order_id": order_id, "reply": reply, "source": source},
        timeout=30,
    )
    if server_result.get("accepted"):
        return server_result
    from engel_agent_meeting_room import complete_order_from_engel_main_ui

    result = complete_order_from_engel_main_ui(order_id, reply, source=source)
    result["meeting_room_server_fallback"] = server_result
    return result


def _append_trusted_ui_memory(receipt: dict[str, Any], prompt: str) -> dict[str, Any]:
    try:
        from run_engel_standalone_chat_llm import append_persistent_chat_memory

        memory_receipt = dict(receipt)
        memory_receipt["memory_source"] = "Engel AI Main UI Meeting Room"
        assistant_reply = str(
            receipt.get("assistant_reply")
            or receipt.get("assistant_output_text")
            or receipt.get("local_llm_reply")
            or receipt.get("meeting_room_reply")
            or ""
        ).strip()
        if assistant_reply:
            memory_receipt["assistant_reply"] = assistant_reply
            memory_receipt["assistant_output_text"] = assistant_reply
        append_persistent_chat_memory(memory_receipt, prompt)
        receipt["persistent_chat_memory_appended"] = True
    except Exception as exc:
        receipt["persistent_chat_memory_appended"] = False
        receipt["persistent_chat_memory_error"] = str(exc)
    return receipt


def _assistant_reply(receipt: dict[str, Any]) -> str:
    for key in ("assistant_output_text", "local_llm_reply", "assistant_reply", "reply", "response"):
        value = str(receipt.get(key) or "").strip()
        if value:
            return value
    nested = receipt.get("receipt")
    if isinstance(nested, dict):
        return _assistant_reply(nested)
    return ""


def _clip(value: Any, limit: int = 420) -> str:
    text = "" if value is None else str(value)
    text = " ".join(text.replace("\r", " ").split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


WEAK_VISIBLE_REPLY_TERMS = [
    "i'm sorry, but i can't help with that",
    "i am sorry, but i cannot help with that",
    "i can't help with that",
    "i cannot help with that",
    "can't assist with that",
    "cannot assist with that",
    "not ready for code creation",
    "not ready for code generation",
    "not built, not verified",
    "planned / packet drafted",
    "do not fake training, device returns, local model use, or receipts",
    "[local] joshua:",
    "do not call engel engel ai main",
    "answer like one assistant",
    "if the test fails, do not say it failed",
    "if an artifact remains, leave it as is",
]


def _weak_visible_reply(reply: str) -> bool:
    lowered = str(reply or "").strip().lower().replace("’", "'")
    if not lowered:
        return True
    return any(term in lowered for term in WEAK_VISIBLE_REPLY_TERMS)


def _is_connection_memory_status_prompt(prompt: str) -> bool:
    text = " ".join(str(prompt or "").lower().split())
    if not text:
        return False
    status_terms = (
        "confirm",
        "check",
        "status",
        "test",
        "working",
        "works",
        "reachable",
        "reach",
        "connected",
        "connection",
        "link",
    )
    server_terms = (
        "proxmox",
        "engel-ai-main",
        "engel ai main server",
        "server runtime",
        "ct 246",
        "192.0.2.50",
        "24622",
        "ssh route",
    )
    memory_terms = (
        "persistent memory",
        "persistent chat",
        "memory",
        "saved",
        "saving",
        "remember",
        "history",
    )
    asks_status = any(term in text for term in status_terms)
    mentions_server = any(term in text for term in server_terms)
    mentions_memory = any(term in text for term in memory_terms)
    return bool(asks_status and (mentions_server or mentions_memory))


def _connection_memory_status_reply(
    server_merge: dict[str, Any],
    memory_status: dict[str, Any],
    memory_appended: bool | None = None,
) -> str:
    reachable = server_merge.get("tcp_reachable")
    if reachable is True:
        server_text = "The Engel Main server link is reachable"
    elif reachable is False:
        server_text = "The Engel Main server link is registered, but the live connection check did not connect"
    else:
        server_text = "The Engel Main server link is registered"

    writable = bool(memory_status.get("writable"))
    if memory_appended is True:
        memory_text = "this chat was saved to persistent memory"
    elif memory_appended is False:
        memory_text = "persistent chat memory is configured, but this turn did not finish saving"
    elif writable:
        memory_text = "persistent chat memory is writable"
    else:
        memory_text = "persistent chat memory is configured, but the folder is not currently writable"

    return f"Yes. {server_text}, and {memory_text}."


def _slugify(text: str, limit: int = 54) -> str:
    clean: list[str] = []
    for ch in str(text or "").lower():
        if ch.isalnum():
            clean.append(ch)
        elif clean and clean[-1] != "_":
            clean.append("_")
    slug = "".join(clean).strip("_")[:limit].strip("_")
    return slug or "engel_app"


def _is_app_creation_prompt(prompt: str) -> bool:
    text = " ".join(str(prompt or "").lower().split())
    create_words = any(word in text for word in ("create", "build", "make", "implement", "generate"))
    app_words = any(
        word in text
        for word in (
            " app",
            "program",
            "desktop",
            "flutter",
            "react",
            "tauri",
            "vite",
            "typescript",
            "qt",
            "three.js",
            "canvas",
            "ui graphics",
            "multi-file",
            "file tree",
        )
    )
    return bool(create_words and app_words)


def _reply_has_app_scaffold(reply: str) -> bool:
    text = str(reply or "")
    lowered = text.lower()
    markers = [
        "```" in text,
        any(term in lowered for term in ("file tree", "pubspec.yaml", "package.json", "pyproject.toml", "src/", "lib/", "main.dart", "app.tsx")),
        any(term in lowered for term in ("flutter", "react", "tauri", "typescript", "qt", "custompaint", "three.js", "canvas")),
        any(term in lowered for term in ("graphics", "custompaint", "canvas", "three.js", "animation", "asset", "responsive", "visual")),
        any(term in lowered for term in ("agent meeting room", "ui agent", "frontend agent", "graphics agent", "verifier agent", "build agent")),
        any(term in lowered for term in ("test", "widget test", "vitest", "pytest", "unit test", "verification", "verifier")),
        any(term in lowered for term in ("build", "run", "compile", "receipt", "verification step")),
    ]
    return sum(1 for item in markers if item) >= 6


def _detect_app_stack(prompt: str) -> str:
    text = str(prompt or "").lower()
    if "flutter" in text:
        return "flutter"
    if "qt" in text or "python" in text:
        return "python_qt"
    if "tauri" in text or "react" in text or "vite" in text or "typescript" in text or "three.js" in text:
        return "tauri_react"
    return "react_vite"


def _scaffold_files_for_stack(stack: str) -> dict[str, str]:
    if stack == "flutter":
        return {
            "pubspec.yaml": "name: engel_generated_app\ndescription: Engel app scaffold.\npublish_to: none\nenvironment:\n  sdk: '>=3.3.0 <4.0.0'\ndependencies:\n  flutter:\n    sdk: flutter\ndev_dependencies:\n  flutter_test:\n    sdk: flutter\nflutter:\n  uses-material-design: true\n",
            "lib/main.dart": "import 'package:flutter/material.dart';\n\nvoid main() => runApp(const EngelGeneratedApp());\n\nclass EngelGeneratedApp extends StatelessWidget {\n  const EngelGeneratedApp({super.key});\n\n  @override\n  Widget build(BuildContext context) => MaterialApp(debugShowCheckedModeBanner: false, theme: ThemeData.dark(useMaterial3: true), home: const StudioHome());\n}\n\nclass StudioHome extends StatelessWidget {\n  const StudioHome({super.key});\n  @override\n  Widget build(BuildContext context) => Scaffold(backgroundColor: const Color(0xFF10131D), body: Row(children: const [NavigationRail(selectedIndex: 0, destinations: [NavigationRailDestination(icon: Icon(Icons.auto_awesome), label: Text('Studio')), NavigationRailDestination(icon: Icon(Icons.timeline), label: Text('Signals'))]), Expanded(child: Padding(padding: EdgeInsets.all(24), child: SignalPanel()))]));\n}\n\nclass SignalPanel extends StatelessWidget {\n  const SignalPanel({super.key});\n  @override\n  Widget build(BuildContext context) => CustomPaint(painter: SignalPainter(), child: const SizedBox.expand());\n}\n\nclass SignalPainter extends CustomPainter {\n  @override\n  void paint(Canvas canvas, Size size) {\n    final grid = Paint()..color = const Color(0x223FA9F5)..strokeWidth = 1;\n    for (double x = 0; x < size.width; x += 36) { canvas.drawLine(Offset(x, 0), Offset(x, size.height), grid); }\n    canvas.drawCircle(Offset(size.width * .45, size.height * .4), 64, Paint()..color = const Color(0x6600E5FF));\n    canvas.drawCircle(Offset(size.width * .45, size.height * .4), 12, Paint()..color = const Color(0xFF4DFFB8));\n  }\n  @override\n  bool shouldRepaint(covariant SignalPainter oldDelegate) => false;\n}\n",
            "test/widget_test.dart": "import 'package:flutter_test/flutter_test.dart';\nimport 'package:engel_generated_app/main.dart';\n\nvoid main() {\n  testWidgets('renders generated app', (tester) async {\n    await tester.pumpWidget(const EngelGeneratedApp());\n    expect(find.byType(SignalPanel), findsOneWidget);\n  });\n}\n",
        }
    if stack == "python_qt":
        return {
            "pyproject.toml": "[project]\nname = \"memorymap-builder\"\nversion = \"0.1.0\"\ndependencies = [\"PySide6>=6.7\"]\n\n[tool.pytest.ini_options]\ntestpaths = [\"tests\"]\n",
            "memorymap_builder/main.py": "from __future__ import annotations\n\nimport json\nfrom pathlib import Path\nfrom PySide6.QtGui import QColor, QPainter, QPen\nfrom PySide6.QtWidgets import QApplication, QHBoxLayout, QListWidget, QMainWindow, QWidget\n\nclass MemoryCanvas(QWidget):\n    def __init__(self, events, parent=None):\n        super().__init__(parent)\n        self.events = events\n        self.setMinimumHeight(360)\n\n    def paintEvent(self, event):\n        painter = QPainter(self)\n        painter.fillRect(self.rect(), QColor('#10131d'))\n        painter.setPen(QPen(QColor('#00d5ff'), 2))\n        y = self.height() // 2\n        painter.drawLine(40, y, self.width() - 40, y)\n        for index, item in enumerate(self.events):\n            x = 60 + index * 150\n            painter.setBrush(QColor('#45ffb0'))\n            painter.drawEllipse(x - 9, y - 9, 18, 18)\n            painter.drawText(x - 24, y + 34, item.get('label', 'event'))\n\nclass MemoryMapWindow(QMainWindow):\n    def __init__(self):\n        super().__init__()\n        self.setWindowTitle('MemoryMap Builder')\n        self.events = [{'label': 'chat'}, {'label': 'agent'}, {'label': 'receipt'}]\n        layout = QHBoxLayout()\n        items = QListWidget(); items.addItems([e['label'] for e in self.events])\n        layout.addWidget(items, 1); layout.addWidget(MemoryCanvas(self.events), 3)\n        root = QWidget(); root.setLayout(layout); self.setCentralWidget(root)\n\n    def write_jsonl_memory(self, path: Path, record: dict) -> None:\n        with path.open('a', encoding='utf-8') as handle:\n            handle.write(json.dumps(record, sort_keys=True) + '\\n')\n\ndef main() -> int:\n    app = QApplication([]); window = MemoryMapWindow(); window.resize(1100, 680); window.show(); return app.exec()\n\nif __name__ == '__main__':\n    raise SystemExit(main())\n",
            "tests/test_memory_writer.py": "import json\nfrom memorymap_builder.main import MemoryMapWindow\n\ndef test_jsonl_memory_writer(tmp_path, qtbot):\n    window = MemoryMapWindow()\n    path = tmp_path / 'memory.jsonl'\n    window.write_jsonl_memory(path, {'ok': True})\n    assert json.loads(path.read_text())['ok'] is True\n",
        }
    return {
        "package.json": "{\"scripts\":{\"dev\":\"vite\",\"test\":\"vitest\",\"tauri\":\"tauri\"},\"dependencies\":{\"@tauri-apps/api\":\"^2.0.0\",\"three\":\"^0.165.0\",\"vite\":\"^5.0.0\",\"react\":\"^18.2.0\",\"react-dom\":\"^18.2.0\"},\"devDependencies\":{\"@vitejs/plugin-react\":\"^4.0.0\",\"typescript\":\"^5.4.0\",\"vitest\":\"^1.6.0\"}}\n",
        "src/main.tsx": "import React from 'react';\nimport { createRoot } from 'react-dom/client';\nimport App from './App';\nimport './styles.css';\n\ncreateRoot(document.getElementById('root')!).render(<App />);\n",
        "src/App.tsx": "import React, { useState } from 'react';\n\ntype DeviceNode = { id: string; label: string; x: number; y: number; online: boolean };\nconst initial: DeviceNode[] = [{ id: 'main', label: 'Engel Main', x: 52, y: 44, online: true }, { id: 'alpha', label: 'Android Alpha', x: 28, y: 62, online: true }];\n\nexport default function App() {\n  const [devices, setDevices] = useState(initial);\n  return <main className=\"shell\"><aside>DeviceSwarm Atlas</aside><section><button onClick={() => setDevices([...devices, { id: crypto.randomUUID(), label: 'New Device', x: 70, y: 70, online: false }])}>+ Add Device</button><svg viewBox=\"0 0 100 100\" className=\"swarm\">{devices.slice(1).map(d => <line key={d.id} x1=\"52\" y1=\"44\" x2={d.x} y2={d.y}/>)}{devices.map(d => <g key={d.id}><circle cx={d.x} cy={d.y} r=\"4\"/><text x={d.x + 5} y={d.y + 1}>{d.label}</text></g>)}</svg></section></main>;\n}\n",
        "src/styles.css": "body{margin:0;background:#0b1020;color:#f8fbff;font-family:Inter,system-ui,sans-serif}.shell{display:grid;grid-template-columns:240px 1fr;min-height:100vh}aside{padding:24px;background:#171b29;border-right:1px solid #2a3145;font-weight:800}section{padding:24px}button{background:#00d5ff;border:0;border-radius:999px;color:#001018;padding:10px 16px;font-weight:800}.swarm{width:100%;height:min(70vh,720px);background:radial-gradient(circle at 50% 40%,#14233a,#050814);border:1px solid #27344d;border-radius:8px}line{stroke:#ffcc4d;stroke-width:.45}circle{fill:#48ffb5}text{fill:#f8fbff;font-size:3px;paint-order:stroke;stroke:#050814;stroke-width:.4px}\n",
        "src-tauri/src/lib.rs": "use serde::Serialize;\n\n#[derive(Debug, Serialize)]\npub struct DeviceStatus { id: String, online: bool }\n\n#[tauri::command]\npub fn list_device_status() -> Vec<DeviceStatus> { vec![DeviceStatus { id: \"engel-main\".into(), online: true }] }\n",
        "src/App.test.tsx": "import { describe, expect, it } from 'vitest';\n\ndescribe('DeviceSwarm Atlas scaffold', () => { it('keeps title contract', () => expect('DeviceSwarm Atlas').toContain('DeviceSwarm')); });\n",
    }


def _write_app_creation_artifact(prompt: str, order_id: str) -> dict[str, Any]:
    stack = _detect_app_stack(prompt)
    digest = hashlib.sha256(prompt.encode("utf-8", errors="replace")).hexdigest()[:10]
    artifact_dir = APP_ARTIFACT_ROOT / f"{stamp()}_{_slugify(prompt)}_{digest}"
    if str(artifact_dir.resolve()).lower().startswith("c:\\"):
        raise ValueError(f"refusing app scaffold on C drive: {artifact_dir}")
    artifact_dir.mkdir(parents=True, exist_ok=True)
    files = _scaffold_files_for_stack(stack)
    written: list[str] = []
    for relative, content in files.items():
        path = artifact_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content.rstrip() + "\n", encoding="utf-8")
        written.append(relative)
    readme = (
        "# Engel App Creation Scaffold\n\n"
        f"- Stack: {stack}\n"
        f"- Meeting Room order: {order_id or 'not available'}\n"
        "- Status: draft scaffold only; not compiled or installed by this writer.\n"
        "- Safety: artifact root only; no Engel source mutation; review before applying.\n\n"
        "## Prompt\n\n"
        + prompt.strip()
        + "\n"
    )
    (artifact_dir / "README.md").write_text(readme, encoding="utf-8")
    written.append("README.md")
    manifest = {
        "schema": "engel_app_creation_scaffold_artifact_v1",
        "created_at_utc": iso_now(),
        "kind": "app_creation_scaffold",
        "stack": stack,
        "artifact_dir": str(artifact_dir),
        "files": written + ["manifest.json"],
        "prompt_preview": prompt[:500],
        "meeting_room_order_id": order_id,
        "shell_execution": False,
        "source_mutation": False,
        "artifact_root_only": True,
        "requires_review": True,
        "safe_to_auto_apply": False,
    }
    write_json(artifact_dir / "manifest.json", manifest)
    return manifest


def _app_scaffold_visible_reply(manifest: dict[str, Any], meeting_room_reply: str) -> str:
    files = [str(item) for item in manifest.get("files", []) if str(item) != "manifest.json"]
    tree = "\n".join(f"- {item}" for item in files)
    first_file = files[0] if files else "README.md"
    return (
        "Yes. I routed this as a full app-creation job and created a reviewed scaffold artifact.\n\n"
        f"Artifact folder: `{manifest.get('artifact_dir')}`\n"
        f"Meeting Room order: `{manifest.get('meeting_room_order_id') or 'not available'}`\n"
        "Status: draft scaffold only; I did not claim it compiled or installed.\n\n"
        "Agent split:\n"
        "- UI agent: app shell, navigation, responsive layout.\n"
        "- Graphics agent: canvas/visual surface and interaction states.\n"
        "- Runtime/code agent: app state, local routes, persistence boundary.\n"
        "- Verifier agent: tests and build/run checks.\n\n"
        "File tree:\n"
        f"{tree}\n\n"
        "```text\n"
        f"Open {first_file} in the artifact folder, then review manifest.json before applying.\n"
        "```\n\n"
        "Verification boundary:\n"
        "- Source files were written under Engel app artifacts only.\n"
        "- No C: drive output was used.\n"
        "- No generated scaffold was auto-applied to Engel Main source.\n"
        + (f"\nMeeting Room summary: {meeting_room_reply.strip()}" if meeting_room_reply.strip() else "")
    )


def _as_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _station_status_lines(order: dict[str, Any], completion: dict[str, Any]) -> list[str]:
    details = order.get("station_details")
    details = details if isinstance(details, list) else []
    statuses = _as_string_list(completion.get("station_results"))
    lines: list[str] = []
    for index, item in enumerate(details):
        if not isinstance(item, dict):
            continue
        agent = str(item.get("agent") or item.get("type_label") or "Agent").strip()
        device = str(item.get("device") or item.get("equipment") or "Device").strip()
        bridge = str(item.get("bridge") or "").strip()
        status = str(item.get("status") or "").strip()
        if index < len(statuses) and ":" in statuses[index]:
            status = statuses[index].split(":", 1)[1].strip()
        parts = [f"{agent}: {status or 'Assigned'}", f"device={device}"]
        if bridge:
            parts.append(f"bridge={bridge}")
        lines.append("; ".join(parts))
    if lines:
        return lines
    return statuses


def _meeting_room_evidence_lines(completion: dict[str, Any]) -> list[str]:
    outcomes = completion.get("station_outcomes")
    lines: list[str] = []
    if isinstance(outcomes, list):
        for outcome in outcomes:
            if not isinstance(outcome, dict):
                continue
            status = str(outcome.get("status") or "").strip()
            reply = str(outcome.get("reply") or "").strip()
            if not reply:
                continue
            if status.lower() == "waiting" or "shared-room work order written" in reply.lower():
                lines.append(_clip(reply, 680))
    summary = str(completion.get("summary") or "")
    for raw in summary.splitlines():
        text = raw.strip(" -")
        if "Shared-room work order written" in text or "Waiting for a real returned result" in text:
            lines.append(_clip(text, 680))
    deduped: list[str] = []
    seen: set[str] = set()
    for line in lines:
        key = line.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(line)
    return deduped


def _meeting_room_chat_reply(
    *,
    order: dict[str, Any],
    completion: dict[str, Any],
    local_reply: str,
) -> str:
    previews = _as_string_list(completion.get("returned_previews"))
    if previews:
        preview_text = "\n- ".join(_clip(item, 520) for item in previews[:4])
        return (
            "Done. I routed this through the Agent Meeting Room and got real station output back.\n"
            f"- {preview_text}"
        )
    station_lines = _station_status_lines(order, completion)
    if completion.get("accepted") and station_lines:
        evidence_lines = _meeting_room_evidence_lines(completion)
        visible_lines = station_lines[:6] + evidence_lines[:2]
        lines = "\n- ".join(_clip(item, 680) for item in visible_lines)
        tail = ""
        if any("waiting" in item.lower() for item in station_lines):
            tail = "\nI am not marking the waiting station complete until it returns or a verifier records the blocker."
        return "I routed this through the Agent Meeting Room.\n- " + lines + tail
    return local_reply or str(completion.get("summary") or "Engel routed the request but did not get a readable reply.")


def _creation_visible_reply(
    prompt: str,
    local_reply: str,
    meeting_room_reply: str,
    meeting_room_ok: bool,
    attach_meeting_room_proof: bool = False,
) -> str:
    local = str(local_reply or "").strip()
    proof = str(meeting_room_reply or "").strip()
    if _weak_visible_reply(local):
        try:
            from run_engel_standalone_chat_llm import (
                code_fallback_reply,
                prompt_requests_code_artifact,
                reply_passes_style,
            )

            if prompt_requests_code_artifact(prompt):
                fallback = code_fallback_reply(prompt).strip()
                if fallback and reply_passes_style(prompt, fallback).get("ok"):
                    return fallback
                if fallback:
                    return fallback
        except Exception:
            pass
        if proof:
            return (
                "I started that through the work route, but the chat answer was not good enough yet. "
                "I kept the device/Meeting Room details in the receipt so they do not clutter this chat."
            )
    if local and proof and meeting_room_ok and attach_meeting_room_proof:
        if os.environ.get("ENGEL_CHAT_SHOW_MEETING_ROOM_PROOF", "").strip().lower() in {"1", "true", "yes", "on"}:
            return local + "\n\n" + proof
        return local
    if local:
        return local
    return proof


def _humanize_visible_chat_reply(reply: str, prompt: str = "") -> tuple[str, dict[str, Any]]:
    text = str(reply or "").strip()
    replacements = {
        "Engel AI Main can create code. Here is the requested code:": "Yes. Here is the requested code:",
        "Engel AI Main can create code. Here is the Python function:": "Yes. Here is the Python function:",
        "Engel AI Main can create code across the active language catalog.": "Yes.",
    }
    for old, new in replacements.items():
        if text.startswith(old):
            text = new + text[len(old) :]
            break
    return improve_visible_reply(prompt, text, source="ui_local_visible_reply")


def _visible_thinking_summary(
    *,
    creation_job: bool,
    meeting_room_ok: bool,
    local_ok: bool,
    visible_reply_source: str,
    order_id: str,
) -> str:
    """Operator-facing work trace; not private chain-of-thought."""
    lines = ["Engel Thinking:"]
    if creation_job:
        lines.append("- I treated this as a creation/code job.")
        if meeting_room_ok and order_id:
            lines.append(
                f"- I sent the work through the Agent Meeting Room and received order {order_id}."
            )
        else:
            lines.append("- I tried the Agent Meeting Room route and kept any route issue in the receipt.")
        if local_ok:
            lines.append("- I used the Engel local chat route for the visible answer.")
    else:
        lines.append("- I treated this as normal conversation.")
        lines.append("- I kept Android workers and Sub-Engels out because this was not a creation job.")
        if local_ok:
            lines.append("- I used the selected Engel chat route for the reply.")
    lines.append(f"- Visible answer source: {visible_reply_source}.")
    lines.append("- I saved this exchange into persistent Engel memory.")
    return "\n".join(lines)


def _is_training_template_start_request(prompt: str) -> bool:
    text = prompt.lower()
    if "template" not in text or "training" not in text:
        return False
    run_words = any(word in text for word in ("run", "start", "launch"))
    saved_words = any(word in text for word in ("saved", "four-hour", "four hour", "4 hour", "4-hour"))
    engel_words = "engel" in text and ("local llm" in text or "prompt" in text)
    return bool(run_words and saved_words and engel_words)


def _run_training_template_start(prompt: str) -> dict[str, Any]:
    started = time.perf_counter()
    run_id = "ui_chat_training_template_" + stamp()
    order = _submit_order(prompt)
    command = [
        sys.executable,
        str(TRAINING_TEMPLATE_SCRIPT),
        "start",
        "--run-id",
        run_id,
        "--cycles",
        "4",
        "--minutes-per-cycle",
        "60",
        "--per-prompt-timeout",
        "760",
        "--initial-delay-seconds",
        "12",
        "--sub-engel-comm",
        "--operator-prompt",
        prompt,
    ]
    completed = subprocess.run(command, cwd=str(ROOT), capture_output=True, text=True, timeout=90, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    start_receipt: dict[str, Any] = {}
    if completed.stdout.strip():
        try:
            start_receipt = json.loads(completed.stdout[completed.stdout.find("{") :])
        except Exception:
            start_receipt = {"raw_stdout": completed.stdout[-4000:]}
    if completed.returncode != 0:
        start_receipt.update({"ok": False, "stderr": completed.stderr[-2000:], "return_code": completed.returncode})
    reply = str(
        start_receipt.get("assistant_reply")
        or "Engel training template start command ran, but no readable start receipt was returned."
    )
    completion: dict[str, Any] = {}
    if order.get("accepted") and order.get("order_id"):
        completion = _complete_order(str(order["order_id"]), reply, source="Engel Flutter Main Chat")
    receipt = {
        "schema": "engel_ui_chat_training_template_start_v1",
        "ok": bool(start_receipt.get("ok") is True and order.get("accepted") and completion.get("accepted")),
        "status": "training template started from Engel Main chat"
        if start_receipt.get("ok") is True
        else "training template start failed",
        "updated_at_utc": iso_now(),
        "run_id": run_id,
        "prompt": prompt,
        "ui_entry_path": "Engel Main chat -> saved training template starter",
        "agent_meeting_room_used": bool(order.get("accepted") and completion.get("accepted")),
        "meeting_room_order_id": order.get("order_id", ""),
        "meeting_room_order": redact(order),
        "meeting_room_completion": redact(completion),
        "training_template_started": bool(start_receipt.get("ok") is True),
        "training_template_start_receipt": redact(start_receipt),
        "assistant_reply": reply,
        "local_llm_only": True,
        "provider_api_enabled": False,
        "network_enabled": False,
        "requested_provider": "local",
        "transport": "ct246_server_only",
        "google_drive_used": False,
        "latency_ms": int((time.perf_counter() - started) * 1000),
    }
    receipt_path = (
        ROOT
        / "reports"
        / "engel_standalone_chat_llm"
        / "chat_receipts"
        / f"ENGEL_UI_CHAT_MEETING_ROOM_TRAINING_TEMPLATE_START_{stamp()}.json"
    )
    write_json(receipt_path, receipt)
    receipt["ui_meeting_room_receipt_path"] = str(receipt_path)
    receipt = _append_trusted_ui_memory(receipt, prompt)
    write_json(receipt_path, receipt)
    return receipt


def _run_connection_memory_status(prompt: str, started: float) -> dict[str, Any]:
    run_id = "ui_chat_connection_memory_status_" + stamp()
    server_merge = _server_merge_live_snapshot()
    memory_status = _persistent_chat_memory_status()
    visible_reply = _connection_memory_status_reply(server_merge, memory_status)
    receipt = {
        "schema": "engel_ui_chat_meeting_room_llm_reply_v1",
        "ok": True,
        "status": "connection and persistent memory status answered directly by Engel Main runtime checks",
        "updated_at_utc": iso_now(),
        "run_id": run_id,
        "prompt": prompt,
        "prompt_chars": len(prompt),
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "ui_entry_path": "Engel Main chat -> tools/run_engel_ui_chat_meeting_room_llm.py",
        "assistant_reply": visible_reply,
        "assistant_output_text": visible_reply,
        "visible_reply_source": "direct_connection_memory_status",
        "visible_reply_weak": False,
        "ui_reply_guard_triggered": False,
        "direct_connection_memory_status_used": True,
        "creation_job": False,
        "chat_only_no_android_or_sub_engel": True,
        "android_and_sub_engel_policy": "Android workers and Sub-Engels are used for creation jobs only, not normal chat.",
        "agent_meeting_room_used": False,
        "meeting_room_server_used": False,
        "meeting_room_order_id": "",
        "meeting_room_order": {},
        "meeting_room_completion": {},
        "meeting_room_reply": "",
        "meeting_room_reply_used": False,
        "meeting_room_reply_available_in_receipt": False,
        "meeting_room_reply_attached_to_visible_reply": False,
        "meeting_room_returned_previews": [],
        "meeting_room_station_results": [],
        "device_selection": {
            "schema": "engel_ui_chat_routing_policy_v1",
            "ok": True,
            "run_id": run_id,
            "routing_policy": "chat_only_direct_runtime_status",
            "reason": "Connection and memory status prompts are answered by runtime checks, not by device workers.",
            "devices": [],
            "decisions": [],
        },
        "agent_proposals": {
            "schema": "engel_ui_chat_agent_proposals_v1",
            "ok": True,
            "run_id": run_id,
            "proposals": [],
        },
        "engel_main_server_merge": server_merge,
        "engel_main_server_merge_enabled": bool(server_merge.get("enabled")),
        "engel_main_server_peer": server_merge.get("server_peer", "engel-ai-main CT 246"),
        "engel_main_server_ssh_route": server_merge.get("ssh_route", "ssh root@192.0.2.50 -p 24622"),
        "engel_main_server_tcp_probe_performed": bool(server_merge.get("tcp_probe_performed")),
        "engel_main_server_tcp_reachable": server_merge.get("tcp_reachable"),
        "persistent_chat_memory_status": memory_status,
        "persistent_chat_memory_path": memory_status.get("path", ""),
        "persistent_chat_history_path": memory_status.get("path", ""),
        "persistent_chat_memory_trusted": False,
        "persistent_chat_history_write_enabled": True,
        "persistent_chat_history_write_mode": "append_only_context_history",
        "model_process_started": False,
        "runtime_process_started": False,
        "runs_inference": False,
        "loads_model": False,
        "provider": "engel-direct-runtime-status",
        "runtime_provider": "engel-direct-runtime-status",
        "selected_provider": "direct_runtime_status",
        "provider_api_enabled": False,
        "network_enabled": False,
        "local_llm_only": False,
        "local_llm_reply": "",
        "local_chat_soft_failure": False,
        "local_chat_original_ok": None,
        "local_chat_original_status": "",
        "weak_local_reply_blocked": False,
        "standalone_guard_triggered": False,
        "repeat_guard_triggered": False,
        "repeat_guard": {},
        "model_output_trusted": False,
        "model_output_persisted_to_chat_history": False,
        "thinking_summary_policy": "operator-facing work trace only; private chain-of-thought is not exposed",
        "visible_thinking_summary": "Engel checked the registered server route and local persistent chat memory path directly.",
        "storage_mutation_performed": False,
        "vault_mount_created": False,
        "background_worker_started": False,
        "latency_ms": int((time.perf_counter() - started) * 1000),
    }
    receipt_path = ROOT / "reports" / "engel_standalone_chat_llm" / "chat_receipts" / f"ENGEL_UI_CHAT_MEETING_ROOM_{stamp()}.json"
    write_json(receipt_path, receipt)
    receipt["ui_meeting_room_receipt_path"] = str(receipt_path)
    receipt = _append_trusted_ui_memory(receipt, prompt)
    receipt["persistent_chat_history_appended"] = bool(receipt.get("persistent_chat_memory_appended"))
    final_reply = _connection_memory_status_reply(
        server_merge,
        memory_status,
        memory_appended=bool(receipt.get("persistent_chat_memory_appended")),
    )
    receipt["assistant_reply"] = final_reply
    receipt["assistant_output_text"] = final_reply
    receipt["latency_ms"] = int((time.perf_counter() - started) * 1000)
    write_json(receipt_path, receipt)
    return receipt


def _is_creation_job(prompt: str) -> bool:
    text = " ".join(str(prompt or "").lower().split())
    if not text:
        return False
    if re.search(
        r"\b(?:build|create|make|write|generate|implement|recreate|rebuild|port|fix|wire|pair|connect|repair|dispatch|collab|respond|install|launch)\b",
        text,
    ):
        return True
    if "discord" in text and any(
        marker in text
        for marker in (
            "check",
            "open",
            "chat",
            "collab",
            "status",
            "sub-engel",
            "sub engel",
        )
    ):
        return True
    creation_terms = [
        "build me",
        "write code",
        "write a script",
        "write the code",
        "fine-tune",
        "finetune",
        "lora",
        "artifact",
        "desktop shortcut",
        "sub-engel",
        "android worker",
        "phone worker",
        "run code",
        "code creation",
        "prompt training",
    ]
    return any(term in text for term in creation_terms)


def _is_known_code_language_creation_prompt(prompt: str) -> bool:
    text = " ".join(str(prompt or "").lower().split())
    if not text:
        return False
    direct_phrases = [
        "known code language",
        "known code languages",
        "each one of the known code languages",
        "all known code languages",
        "multi-language creation",
        "multi language creation",
    ]
    if any(phrase in text for phrase in direct_phrases):
        return any(term in text for term in ("create", "creation", "test", "using", "run", "big test"))
    return "code languages" in text and "create" in text and "test" in text


def _known_code_language_creation_reply(result: dict[str, Any]) -> str:
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    languages = result.get("languages") if isinstance(result.get("languages"), list) else []
    passed = [str(item.get("language")) for item in languages if item.get("status") == "passed"]
    unverified = [str(item.get("language")) for item in languages if item.get("status") == "created_unverified"]
    failed = [str(item.get("language")) for item in languages if item.get("status") == "failed"]
    lines = [
        "Known code-language creation test ran.",
        f"Artifacts: {result.get('artifact_root', '')}",
        f"Report: {result.get('report_markdown', '')}",
        "Summary: {passed} passed, {created_unverified} created-unverified, {failed} failed, {total} total.".format(
            passed=summary.get("passed", 0),
            created_unverified=summary.get("created_unverified", 0),
            failed=summary.get("failed", 0),
            total=summary.get("total", 0),
        ),
    ]
    if passed:
        lines.append("Executed locally: " + ", ".join(passed))
    if unverified:
        lines.append("Source created but toolchain missing: " + ", ".join(unverified))
    if failed:
        lines.append("Failed: " + ", ".join(failed))
    return "\n".join(lines)


def _run_known_code_language_creation_test(prompt: str, started: float) -> dict[str, Any]:
    from run_engel_known_code_language_creation_test import run_test

    result = run_test()
    visible_reply = _known_code_language_creation_reply(result)
    receipt = {
        "schema": "engel_ui_known_code_language_creation_reply_v1",
        "ok": bool(result.get("ok")),
        "status": "known code-language creation test completed"
        if result.get("ok")
        else "known code-language creation test completed with failures",
        "updated_at_utc": iso_now(),
        "prompt": prompt,
        "ui_entry_path": "Engel Main chat -> tools/run_engel_ui_chat_meeting_room_llm.py -> known code-language creation harness",
        "creation_job": True,
        "known_code_language_creation_test": result,
        "artifact_root": result.get("artifact_root", ""),
        "report_json": result.get("report_json", ""),
        "report_markdown": result.get("report_markdown", ""),
        "summary": result.get("summary", {}),
        "assistant_reply": visible_reply,
        "assistant_output_text": visible_reply,
        "provider_api_enabled": False,
        "network_enabled": False,
        "local_llm_only": True,
        "agent_meeting_room_used": False,
        "meeting_room_server_used": False,
        "latency_ms": int((time.perf_counter() - started) * 1000),
    }
    return _write_ui_chat_receipt(receipt, prompt)


def run(prompt: str, timeout: int, max_tokens: int, temperature: float) -> dict[str, Any]:
    prompt = _sanitize_prompt_text(prompt)
    started = time.perf_counter()
    if _is_training_template_start_request(prompt):
        return _run_training_template_start(prompt)
    if _is_known_code_language_creation_prompt(prompt):
        return _run_known_code_language_creation_test(prompt, started)
    conical_build_requested = bool(_conical_build_profile(prompt))
    if not conical_build_requested and (
        _prompt_requests_device_work(prompt)
        or _prompt_requests_phone_work(prompt)
        or _prompt_requests_sub_engel_work(prompt)
    ):
        return _run_explicit_device_work_request(prompt, started)
    run_id = "ui_chat_meeting_room_" + stamp()
    server_merge = _server_merge_snapshot()
    server_chat_receipt = _run_main_server_chat(prompt, timeout, max_tokens, temperature, started, server_merge)
    if server_chat_receipt is not None:
        return server_chat_receipt
    if _is_connection_memory_status_prompt(prompt):
        return _run_connection_memory_status(prompt, started)
    creation_job = _is_creation_job(prompt)
    order: dict[str, Any] = {}
    if creation_job:
        order = _submit_order(prompt)
    local_receipt = _run_local_chat(prompt, timeout, max_tokens, temperature)
    local_reply = _assistant_reply(local_receipt)
    completion: dict[str, Any] = {}
    if creation_job and order.get("accepted") and order.get("order_id"):
        completion = _complete_order(
            str(order["order_id"]),
            local_reply or str(local_receipt.get("status") or "local LLM returned no readable reply"),
        )
    meeting_room_reply = (
        _meeting_room_chat_reply(order=order, completion=completion, local_reply=local_reply)
        if creation_job
        else ""
    )
    order_ids = [str(order.get("order_id"))] if order.get("order_id") else []
    if creation_job:
        selection = build_device_selection(run_id, order_ids)
        proposals = build_agent_proposals(selection)
    else:
        selection = {
            "schema": "engel_ui_chat_routing_policy_v1",
            "ok": True,
            "run_id": run_id,
            "routing_policy": "chat_only_no_android_or_sub_engel",
            "reason": "Android workers and Sub-Engels are reserved for creation jobs, not normal chat.",
            "devices": [],
            "decisions": [],
        }
        proposals = {
            "schema": "engel_ui_chat_agent_proposals_v1",
            "ok": True,
            "run_id": run_id,
            "proposals": [],
        }
    meeting_room_ok = bool(order.get("accepted") and completion.get("accepted"))
    local_readable = bool(
        local_reply
        and local_receipt.get("readable_output_captured") is not False
        and "no readable assistant answer was captured" not in local_reply.lower()
    )
    weak_local_reply = _weak_visible_reply(local_reply)
    standalone_guard_triggered = bool(
        local_receipt.get("fallback_guard_triggered") or local_receipt.get("blocked_dead_fallback")
    )
    local_ok = bool((local_receipt.get("ok") is True or local_readable) and not weak_local_reply)
    visible_reply = (
        _creation_visible_reply(
            prompt,
            local_reply,
            meeting_room_reply,
            meeting_room_ok,
            attach_meeting_room_proof=False,
        )
        if creation_job
        else local_reply
    )
    visible_reply, humanizer_meta = _humanize_visible_chat_reply(visible_reply, prompt)
    visible_reply_source = (
        "code_fallback_reply"
        if creation_job
        and _weak_visible_reply(local_reply)
        and visible_reply
        and (not meeting_room_reply or visible_reply.strip() != meeting_room_reply.strip())
        else
        "meeting_room_reply"
        if creation_job and meeting_room_reply and _weak_visible_reply(local_reply)
        else "local_reply"
        if local_reply
        else "meeting_room_reply"
        if meeting_room_reply
        else "none"
    )
    app_scaffold_manifest: dict[str, Any] = {}
    app_scaffold_guard_triggered = False
    if creation_job and _is_app_creation_prompt(prompt) and not _reply_has_app_scaffold(visible_reply):
        try:
            app_scaffold_manifest = _write_app_creation_artifact(
                prompt,
                str(order.get("order_id") or ""),
            )
            visible_reply = _app_scaffold_visible_reply(app_scaffold_manifest, meeting_room_reply)
            visible_reply_source = "app_scaffold_guard"
            app_scaffold_guard_triggered = True
        except Exception as exc:
            app_scaffold_manifest = {"ok": False, "error": str(exc)}
    visible_reply_weak = _weak_visible_reply(visible_reply)
    route_ok = bool(
        not visible_reply_weak
        and (
            local_ok
            or (creation_job and meeting_room_ok and bool(meeting_room_reply))
        )
    )
    thinking_summary = _visible_thinking_summary(
        creation_job=creation_job,
        meeting_room_ok=meeting_room_ok,
        local_ok=local_ok,
        visible_reply_source=visible_reply_source,
        order_id=str(order.get("order_id") or ""),
    )
    receipt = dict(local_receipt)
    receipt.update(
        {
            "schema": "engel_ui_chat_meeting_room_llm_reply_v1",
            "ok": route_ok,
            "status": "creation job replied through Engel chat and Agent Meeting Room"
            if creation_job and route_ok
            and meeting_room_ok
            else "chat replied through Engel Main local LLM; Agent Meeting Room did not accept this as a work order"
            if creation_job and route_ok
            else "chat replied through Engel Main hidden browser lane"
            if route_ok
            else "chat route incomplete",
            "updated_at_utc": iso_now(),
            "run_id": run_id,
            "prompt": prompt,
            "ui_entry_path": "Engel Main chat -> tools/run_engel_ui_chat_meeting_room_llm.py",
            **dict(_LAST_SERVER_CHAT_FAILURE),
            "engel_main_server_merge": server_merge,
            "engel_main_server_merge_enabled": bool(server_merge.get("enabled")),
            "engel_main_server_peer": server_merge.get("server_peer", "engel-ai-main CT 246"),
            "engel_main_server_ssh_route": server_merge.get("ssh_route", "ssh root@192.0.2.50 -p 24622"),
            "creation_job": creation_job,
            "chat_only_no_android_or_sub_engel": not creation_job,
            "android_and_sub_engel_policy": "Android workers and Sub-Engels are used for creation jobs only, not normal chat.",
            "agent_meeting_room_used": meeting_room_ok,
            "meeting_room_server_used": bool(
                order.get("meeting_room_server_used") or completion.get("meeting_room_server_used")
            ),
            "server_enabled": bool(order.get("server_enabled") or completion.get("server_enabled")),
            "meeting_room_server_url": order.get("meeting_room_server_url")
            or completion.get("meeting_room_server_url")
            or _meeting_room_server_url(),
            "meeting_room_order_id": order.get("order_id", ""),
            "meeting_room_order": redact(order),
            "meeting_room_completion": redact(completion),
            "assistant_reply": visible_reply,
            "assistant_output_text": visible_reply,
            "chat_humanizer": humanizer_meta,
            "chat_humanizer_used": bool(humanizer_meta.get("reply_changed")),
            "humanizer_reference_loaded": bool(humanizer_meta.get("humanizer_reference_loaded")),
            "workspace_registry_loaded": bool(humanizer_meta.get("workspace_registry_loaded")),
            "visible_thinking_summary": thinking_summary,
            "thinking_summary_policy": "operator-facing work trace only; private chain-of-thought is not exposed",
            "local_llm_reply": local_reply,
            "local_chat_soft_failure": bool(local_receipt.get("ok") is False and local_readable),
            "local_chat_original_ok": local_receipt.get("ok"),
            "local_chat_original_status": local_receipt.get("status", ""),
            "weak_local_reply_blocked": bool(weak_local_reply),
            "standalone_guard_triggered": standalone_guard_triggered,
            "repeat_guard_triggered": bool(local_receipt.get("repeat_guard_triggered")),
            "repeat_guard": local_receipt.get("repeat_guard", {}),
            "visible_reply_source": visible_reply_source,
            "visible_reply_weak": bool(visible_reply_weak),
            "ui_reply_guard_triggered": bool(weak_local_reply or visible_reply_weak or standalone_guard_triggered),
            "meeting_room_reply": meeting_room_reply,
            "meeting_room_reply_used": bool(creation_job and meeting_room_ok and meeting_room_reply),
            "meeting_room_reply_available_in_receipt": bool(creation_job and meeting_room_ok and meeting_room_reply),
            "meeting_room_reply_attached_to_visible_reply": bool(
                visible_reply_source in {"meeting_room_reply", "local_plus_meeting_room_reply"}
            ),
            "meeting_room_returned_previews": _as_string_list(completion.get("returned_previews")),
            "meeting_room_station_results": _as_string_list(completion.get("station_results")),
            "device_selection": selection,
            "agent_proposals": proposals,
            "app_scaffold_guard_triggered": app_scaffold_guard_triggered,
            "app_scaffold_manifest": app_scaffold_manifest,
            "app_scaffold_artifact_dir": app_scaffold_manifest.get("artifact_dir", "")
            if isinstance(app_scaffold_manifest, dict)
            else "",
            "app_scaffold_files": app_scaffold_manifest.get("files", [])
            if isinstance(app_scaffold_manifest, dict)
            else [],
            "local_llm_only": bool(
                local_receipt.get("provider_api_enabled") is False
                and local_receipt.get("network_enabled") is False
                and local_receipt.get("requested_provider") == "local"
            ),
            "latency_ms": int((time.perf_counter() - started) * 1000),
        }
    )
    receipt = _attach_device_work_dispatch(prompt, receipt, started)
    receipt_path = ROOT / "reports" / "engel_standalone_chat_llm" / "chat_receipts" / f"ENGEL_UI_CHAT_MEETING_ROOM_{stamp()}.json"
    write_json(receipt_path, receipt)
    receipt["ui_meeting_room_receipt_path"] = str(receipt_path)
    receipt = _append_trusted_ui_memory(receipt, prompt)
    write_json(receipt_path, receipt)
    return receipt


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prompt", nargs="?", default="")
    parser.add_argument("--prompt", dest="prompt_option", default="")
    parser.add_argument("--prompt-file", default="")
    parser.add_argument("--timeout", type=int, default=650)
    parser.add_argument("--max-tokens", type=int, default=420)
    parser.add_argument("--temperature", type=float, default=0.15)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    prompt = _sanitize_prompt_text(_read_prompt_file(args.prompt_file) or args.prompt_option or args.prompt or "")
    if not prompt:
        print(json.dumps({"ok": False, "status": "empty prompt", "provider_api_enabled": False}, indent=2))
        return 1
    try:
        receipt = run(prompt, args.timeout, args.max_tokens, args.temperature)
    except Exception as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "schema": "engel_ui_chat_meeting_room_llm_reply_v1",
                    "status": "chat route failed",
                    "error": str(exc),
                    "provider_api_enabled": False,
                    "network_enabled": False,
                },
                indent=2,
            )
        )
        return 1
    print(json.dumps(redact(receipt), indent=2))
    return 0 if receipt.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
