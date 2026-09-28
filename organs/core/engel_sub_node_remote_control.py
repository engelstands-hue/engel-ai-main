#!/usr/bin/env python3
"""Engel App client for pair-gated Sub-Engel node remote control.

This client talks to the node-side engel-remote endpoint. It does not open a
listener, start a worker, run arbitrary shell commands, or bypass the node's
allowlist.
"""

from __future__ import annotations

import argparse
import concurrent.futures
from datetime import datetime, timedelta, timezone
import ipaddress
import json
import os
import re
import secrets
from pathlib import Path
import socket
import subprocess
import sys
from typing import Any
from urllib import error, parse, request


ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
STATE_DIR = ROOT / "remote_nodes" / "sub_engel"
SESSION_PATH = STATE_DIR / "session.json"
WINDOWS_STATE_DIR = ROOT / "remote_nodes" / "windows_sub_engel"
WINDOWS_SESSION_PATH = WINDOWS_STATE_DIR / "session.json"
REPORT_DIR = ROOT / "reports" / "sub_engel_remote_control"
DEFAULT_CONTROLLER_NAME = "Engel AI Controller"
DEFAULT_TIMEOUT = 12
DEFAULT_SESSION_TTL_SECONDS = 30 * 24 * 60 * 60
DISCOVERY_CONNECT_TIMEOUT = 0.22
DISCOVERY_HTTP_TIMEOUT = 2
DISCOVERY_MAX_WORKERS = 128
CT246_SSH_TARGET = os.environ.get("ENGEL_CT246_SSH_TARGET", "root@192.0.2.50")
CT246_SSH_PORT = int(os.environ.get("ENGEL_CT246_SSH_PORT", "24622"))
CT246_SSH_KEY = Path(
    os.environ.get(
        "ENGEL_CT246_SSH_KEY",
        str(Path.home() / ".ssh" / "engel_ai_main_ct246_ed25519"),
    )
)

ALLOWED_ACTIONS = [
    "node.status",
    "node.hardware",
    "node.safety",
    "node.controller",
    "net.status",
    "net.diagnose",
    "net.firmware",
    "install.status",
    "install.preflight",
    "install.list_disks",
    "ui.dashboard",
    "ui.visible_status",
    "local_llm.status",
    "direct_work.execute",
    "session.renew",
    "training.status",
    "training_safe.execute",
    "main.control_status",
    "main.shell",
    "disk.control",
    "memory.status",
    # (2026-07-28) Restored: the 20260727 CT-authoritative relay rework
    # dropped this bounded read-only shared-room status action; the client
    # contract (verify_sub_engel_controller_client) still requires it.
    "shared_room.status",
    "remote.status",
]

DISABLED_AGENT_MEETING_STATUSES = {
    "not_selectable",
    "not_selectable_external_jobs",
    "reserved_external_jobs",
    "disabled",
    "retired",
}

BLOCKED_ACTIONS = [
    "shell",
    "exec",
    "ssh",
    "reboot",
    "shutdown",
    "package.install",
    "install.install",
    "disk.partition",
    "disk.format",
    "disk.erase",
    "wifi.connect",
    "provider.start",
    "model.start",
    "controller.runtime.start",
    "background.worker.start",
    "shared_room.status",
    "shared_room.process_latest_work_order",
    "shared_room.process_pending_work_orders",
]


def utc_stamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def record_is_disabled(data: dict[str, Any]) -> bool:
    if not isinstance(data, dict):
        return False
    if data.get("disabled_for_engel_main") is True or data.get("do_not_use_for_engel_ai_main") is True:
        return True
    status = str(data.get("agent_meeting_status") or "").strip().lower()
    if status in DISABLED_AGENT_MEETING_STATUSES:
        return True
    node = data.get("node") if isinstance(data.get("node"), dict) else {}
    node_id = str(
        data.get("node_id")
        or data.get("hostname")
        or node.get("node_id")
        or node.get("hostname")
        or node.get("computer_name")
        or ""
    ).strip()
    if node_id:
        session = read_json(node_session_path("windows", node_id))
        if session.get("disabled_for_engel_main") is True or session.get("do_not_use_for_engel_ai_main") is True:
            return True
        session_status = str(session.get("agent_meeting_status") or "").strip().lower()
        if session_status in DISABLED_AGENT_MEETING_STATUSES:
            return True
    return False


def is_os_drive_text(value: Any) -> bool:
    text = str(value or "").replace("/", "\\").lower()
    return text.startswith("c:\\") or text.startswith("\\\\?\\c:\\")


def decode_action_stdout(response: dict[str, Any]) -> dict[str, Any]:
    result = response.get("result") if isinstance(response.get("result"), dict) else {}
    stdout = result.get("stdout") if isinstance(result, dict) else ""
    if not isinstance(stdout, str) or not stdout.strip():
        return {}
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def action_stdout_text(response: dict[str, Any]) -> str:
    result = response.get("result") if isinstance(response.get("result"), dict) else {}
    stdout = result.get("stdout") if isinstance(result, dict) else ""
    return stdout if isinstance(stdout, str) else ""


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def redacted(value: str) -> str:
    if len(value) <= 4:
        return "****"
    return "*" * (len(value) - 4) + value[-4:]


def append_receipt(record: dict[str, Any]) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    receipt = {"timestamp_utc": utc_stamp(), **record}
    path = REPORT_DIR / "remote_control_receipts.jsonl"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(receipt, sort_keys=True) + "\n")


def node_kind_key(node_kind: str | None = None) -> str:
    raw = str(node_kind or "linux").strip().lower().replace("-", "_").replace(" ", "_")
    if "win" in raw:
        return "windows"
    return "linux"


def session_path_for_node_kind(node_kind: str | None = None) -> Path:
    if node_kind_key(node_kind) == "windows":
        return WINDOWS_SESSION_PATH
    return SESSION_PATH


def infer_node_kind(response: dict[str, Any] | None = None, url: str = "", requested: str | None = None) -> str:
    if requested and str(requested).strip().lower() not in {"", "auto"}:
        return node_kind_key(requested)
    data = response or {}
    hints = " ".join([
        str(data.get("node_kind", "")),
        str(data.get("node_os", "")),
        str(data.get("role", "")),
        str(url or ""),
    ]).lower()
    if "windows" in hints or ":8776" in hints:
        return "windows"
    return "linux"


def state_dir_for_node_kind(node_kind: str | None = None) -> Path:
    return WINDOWS_STATE_DIR if node_kind_key(node_kind) == "windows" else STATE_DIR


def nodes_registry_dir(node_kind: str | None = None) -> Path:
    """Per-node registry dir so multiple nodes of one kind never evict each other."""
    return state_dir_for_node_kind(node_kind) / "nodes"


def _safe_node_id(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "")).strip("._")
    return (safe or "node")[:90]


def node_id_for_session(data: dict[str, Any]) -> str:
    data = data or {}
    host = str(data.get("hostname") or data.get("computer_name") or "").strip()
    if not host:
        h, p, _scheme = parsed_url_host_port(str(data.get("url") or ""), 0)
        host = f"{h}_{p}" if h else "node"
    return _safe_node_id(host)


def node_session_path(node_kind: str | None, node_id: str) -> Path:
    return nodes_registry_dir(node_kind) / _safe_node_id(node_id) / "session.json"


def load_session(node_kind: str | None = None, node_id: str | None = None) -> dict[str, Any]:
    """Load the active node (legacy path) by default, or a specific registered node."""
    if node_id:
        data = read_json(node_session_path(node_kind, node_id))
        if data:
            return data
    return read_json(session_path_for_node_kind(node_kind))


def save_session(data: dict[str, Any], node_kind: str | None = None) -> None:
    kind = node_kind or str(data.get("connection_family") or data.get("node_kind") or data.get("node_os") or "linux")
    # Active/default node (legacy path) — preserved for backward compatibility.
    write_json(session_path_for_node_kind(kind), data)
    # Per-node registry copy so additional nodes of the same kind coexist.
    write_json(node_session_path(kind, node_id_for_session(data)), data)


def list_node_sessions(node_kind: str | None = None) -> list[dict[str, Any]]:
    """Every paired node of a kind: per-node registry plus the active/legacy file."""
    kind = node_kind_key(node_kind)
    out: dict[str, dict[str, Any]] = {}
    reg = nodes_registry_dir(kind)
    if reg.is_dir():
        for child in sorted(reg.iterdir()):
            data = read_json(child / "session.json")
            if data:
                out[node_id_for_session(data)] = data
    legacy = read_json(session_path_for_node_kind(kind))
    if legacy:
        out.setdefault(node_id_for_session(legacy), legacy)
    filtered: list[dict[str, Any]] = []
    for nid, data in sorted(out.items()):
        status = str(data.get("agent_meeting_status") or "").lower()
        if data.get("disabled_for_engel_main") is True or status in {
            "not_selectable",
            "not_selectable_external_jobs",
            "reserved_external_jobs",
            "disabled",
            "retired",
        }:
            continue
        filtered.append({"node_id": nid, "session": data})
    return filtered


def runtime_node_url(session: dict[str, Any]) -> str:
    if os.name != "nt" and session.get("ct_relay_url"):
        return str(session.get("ct_relay_url") or "")
    return str(session.get("url") or "")


def should_use_ct246_control_relay(
    *,
    kind: str,
    node_id: str | None,
    explicit_url: str | None,
    explicit_token: str | None,
) -> bool:
    return bool(
        os.name == "nt"
        and node_kind_key(kind) == "windows"
        and str(node_id or "").strip()
        and not explicit_url
        and not explicit_token
        and CT246_SSH_KEY.is_file()
        and os.environ.get("ENGEL_CT246_SUB_CONTROL_RELAY", "1").strip().lower()
        not in {"0", "false", "no", "off"}
    )


def run_action_via_ct246(
    action: str,
    *,
    node_id: str,
    payload: dict[str, Any] | None = None,
    timeout: int = DEFAULT_TIMEOUT + 20,
) -> dict[str, Any]:
    safe_node_id = _safe_node_id(node_id)
    remote_command = (
        "cd /opt/engel && "
        "python3 engel_sub_node_remote_control.py command "
        f"--action {action} --node-kind windows --node {safe_node_id}"
    )
    input_text: str | None = None
    if payload:
        remote_command += " --payload-file /dev/stdin"
        input_text = json.dumps(payload)
    try:
        completed = subprocess.run(
            [
                "ssh",
                "-i",
                str(CT246_SSH_KEY),
                "-p",
                str(CT246_SSH_PORT),
                "-o",
                "BatchMode=yes",
                "-o",
                "ConnectTimeout=8",
                CT246_SSH_TARGET,
                remote_command,
            ],
            input=input_text,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=max(15, min(630, int(timeout) + 15)),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "ok": False,
            "ct246_relay_reached": False,
            "error": f"CT246 Sub-Engel control relay unavailable: {exc}",
        }
    try:
        response = json.loads(completed.stdout)
    except (json.JSONDecodeError, TypeError):
        return {
            "ok": False,
            "ct246_relay_reached": False,
            "error": "CT246 Sub-Engel control relay returned invalid JSON",
            "return_code": completed.returncode,
            "stderr_tail": completed.stderr[-500:],
        }
    if not isinstance(response, dict):
        return {
            "ok": False,
            "ct246_relay_reached": False,
            "error": "CT246 Sub-Engel control relay returned a non-object response",
        }
    response["ct246_relay_reached"] = True
    response["control_transport"] = "rog_ssh_to_ct246_authenticated_sub_control"
    return response


def request_json(
    method: str,
    url: str,
    payload: dict[str, Any] | None = None,
    token: str | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = request.Request(url, data=body, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except error.HTTPError as exc:
        try:
            body_text = exc.read().decode("utf-8")
            data = json.loads(body_text) if body_text else {}
        except Exception:
            data = {"error": str(exc)}
        data.setdefault("ok", False)
        data.setdefault("http_status", exc.code)
        return data
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def normalized_url(base_url: str, suffix: str) -> str:
    return base_url.rstrip("/") + suffix


def parsed_url_host_port(url: str, fallback_port: int) -> tuple[str, int, str]:
    candidate = str(url or "").strip()
    if candidate and "://" not in candidate:
        candidate = "http://" + candidate
    parsed = parse.urlparse(candidate)
    host = parsed.hostname or ""
    port = int(parsed.port or fallback_port)
    scheme = parsed.scheme or "http"
    return host, port, scheme


def make_base_url(host: str, port: int, scheme: str = "http") -> str:
    return f"{scheme}://{host}:{port}"


def discovery_port_for_kind(kind: str) -> int:
    return 8776 if node_kind_key(kind) == "windows" else 8775


def _add_url_once(urls: list[str], seen: set[str], url: str) -> None:
    clean = str(url or "").strip().rstrip("/")
    if not clean:
        return
    if "://" not in clean:
        clean = "http://" + clean
    if clean not in seen:
        seen.add(clean)
        urls.append(clean)


def _ip_urls_from_payload(payload: dict[str, Any], port: int) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    if not isinstance(payload, dict):
        return urls
    for key in ("node_ip", "remote_addr", "ip", "host"):
        value = payload.get(key)
        if value:
            text = str(value)
            if "://" in text:
                _add_url_once(urls, seen, text)
            else:
                _add_url_once(urls, seen, make_base_url(text, port))
    for key in ("node_ips", "last_known_ips", "local_ips", "ip_addresses", "ips"):
        values = payload.get(key)
        if isinstance(values, str):
            values = [values]
        if isinstance(values, list):
            for value in values:
                _add_url_once(urls, seen, make_base_url(str(value), port))
    for section_key in ("node", "network"):
        section = payload.get(section_key)
        if not isinstance(section, dict):
            continue
        for key in ("ip_addresses", "local_ips", "ips"):
            values = section.get(key)
            if isinstance(values, str):
                values = [values]
            if isinstance(values, list):
                for value in values:
                    _add_url_once(urls, seen, make_base_url(str(value), port))
    return urls


def disabled_windows_hosts() -> set[str]:
    hosts: set[str] = set()
    for session_path in sorted((WINDOWS_STATE_DIR / "nodes").glob("*/session.json")):
        session = read_json(session_path)
        if not record_is_disabled(session):
            continue
        for candidate in [str(session.get("url") or ""), str(session.get("hostname") or "")]:
            host, _port, _scheme = parsed_url_host_port(candidate, discovery_port_for_kind("windows"))
            if host:
                hosts.add(host.lower())
        values = session.get("last_known_ips")
        if isinstance(values, str):
            values = [values]
        if isinstance(values, list):
            for value in values:
                host = str(value or "").strip().lower()
                if host:
                    hosts.add(host)
    return hosts


def candidate_urls_from_state(kind: str, session: dict[str, Any]) -> list[str]:
    port = discovery_port_for_kind(kind)
    urls: list[str] = []
    seen: set[str] = set()
    _add_url_once(urls, seen, str(session.get("url") or ""))
    hostname = str(session.get("hostname") or session.get("computer_name") or "").strip()
    if hostname:
        _add_url_once(urls, seen, make_base_url(hostname, port))
    for key in ("last_known_ips", "local_ips", "ips"):
        values = session.get(key)
        if isinstance(values, str):
            values = [values]
        if isinstance(values, list):
            for value in values:
                _add_url_once(urls, seen, make_base_url(str(value), port))
    if node_kind_key(kind) == "windows":
        ready = ROOT / "runtime" / "windows_sub_engel_bootstrap" / "latest_node_ready.json"
        for url in _ip_urls_from_payload(read_json(ready), port):
            _add_url_once(urls, seen, url)
        checkins = WINDOWS_STATE_DIR / "checkins"
        try:
            paths = sorted(checkins.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
        except OSError:
            paths = []
        for path in paths[:4]:
            checkin = read_json(path)
            if record_is_disabled(checkin):
                continue
            for url in _ip_urls_from_payload(checkin, port):
                _add_url_once(urls, seen, url)
    return urls


def tcp_open(host: str, port: int, timeout: float = DISCOVERY_CONNECT_TIMEOUT) -> bool:
    sock = socket.socket()
    sock.settimeout(timeout)
    try:
        return sock.connect_ex((host, port)) == 0
    except OSError:
        return False
    finally:
        sock.close()


def health_matches_kind(payload: dict[str, Any], kind: str) -> bool:
    if not payload.get("ok"):
        return False
    text = " ".join([
        str(payload.get("node_kind", "")),
        str(payload.get("node_os", "")),
        str(payload.get("role", "")),
        str(payload.get("service", "")),
    ]).lower()
    if node_kind_key(kind) == "windows":
        return "windows" in text
    return "windows" not in text


def private_scan_hosts(seed_url: str, kind: str) -> list[str]:
    host, _port, _scheme = parsed_url_host_port(seed_url, discovery_port_for_kind(kind))
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return []
    if address.version != 4 or not address.is_private:
        return []
    hosts: list[str] = []
    seen: set[str] = set()
    for prefix in (24, 22):
        try:
            network = ipaddress.ip_network(f"{address}/{prefix}", strict=False)
        except ValueError:
            continue
        for candidate in network.hosts():
            text = str(candidate)
            if text not in seen:
                seen.add(text)
                hosts.append(text)
    return hosts


def network_error(response: dict[str, Any]) -> bool:
    if response.get("ok"):
        return False
    err = str(response.get("error") or "").lower()
    return any(token in err for token in ("urlopen error", "timed out", "refused", "failed to respond", "unreachable"))


def render_help() -> str:
    return "\n".join([
        "Sub-Engel node remote control",
        "",
        "Engel OS node-side first:",
        "  sudo engel-remote token",
        "  sudo engel-remote serve --lan --approve APPROVE_ENGEL_REMOTE_CONTROL",
        "",
        "Windows laptop/desktop node-side first:",
        "  python engel_windows_sub_node_agent.py token",
        "  python engel_windows_sub_node_agent.py serve --lan --approve APPROVE_ENGEL_WINDOWS_SUB_NODE",
        "",
        "Controller-side:",
        "  python engel_sub_node_remote_control.py pair --url http://NODE-IP:8775 --pairing-code CODE",
        "  python engel_sub_node_remote_control.py pair --url http://WINDOWS-NODE-IP:8776 --pairing-code CODE",
        "  python engel_sub_node_remote_control.py command --action node.status",
        "",
        "Allowed actions:",
        *[f"  {action}" for action in ALLOWED_ACTIONS],
        "",
        "Blocked actions:",
        *[f"  {action}" for action in BLOCKED_ACTIONS],
    ])


def _render_registered_nodes(kind: str) -> list[str]:
    nodes = list_node_sessions(kind)
    if not nodes:
        return []
    lines = [f"Registered {kind} nodes: {len(nodes)}"]
    for entry in nodes:
        s = entry["session"]
        lines.append(
            f"  - {entry['node_id']}: {s.get('url', '?')} "
            f"(expires {s.get('expires_at_utc', '?')})"
        )
    return lines


def render_status(node_kind: str | None = None) -> str:
    kind = node_kind_key(node_kind)
    label = "Windows Sub-Engel node" if kind == "windows" else "Sub-Engel node"
    session = load_session(kind)
    if not session:
        lines = [
            f"{label} remote control: not paired",
            "Listener opened by Engel App: no",
            "Raw shell: disabled",
            "Remote disk install/format/partition: disabled",
            "Provider/model runtime: inactive",
        ]
        return "\n".join(lines + _render_registered_nodes(kind))
    lines = [
        f"{label} remote control: paired session stored",
        f"Node URL: {session.get('url', 'unknown')}",
        f"Node kind: {session.get('node_kind', session.get('role', 'unknown'))}",
        f"Connection family: {session.get('connection_family', kind)}",
        f"Controller name: {session.get('controller_name', DEFAULT_CONTROLLER_NAME)}",
        f"Token hint: {session.get('session_token_hint', 'stored')}",
        f"Session expires UTC: {session.get('expires_at_utc', 'unknown')}",
        "Listener opened by Engel App: no",
        "Raw shell: disabled",
        "Remote disk install/format/partition: disabled",
        "Provider/model runtime: inactive",
    ]
    return "\n".join(lines + _render_registered_nodes(kind))


def pair_node(
    url: str,
    pairing_code: str,
    controller_name: str = DEFAULT_CONTROLLER_NAME,
    store: bool = True,
    node_kind: str = "auto",
) -> dict[str, Any]:
    # The controller proposes the bearer so a network timeout after the node
    # commits pairing cannot strand both sides with different session tokens.
    proposed_token = secrets.token_urlsafe(32)
    response = request_json(
        "POST",
        normalized_url(url, "/pair"),
        {
            "pairing_code": pairing_code,
            "controller_name": controller_name,
            "proposed_session_token": proposed_token,
        },
        timeout=DEFAULT_TIMEOUT,
    )
    recovered_after_timeout = False
    if not response.get("ok") and network_error(response):
        proof = actions(url, proposed_token)
        if proof.get("ok"):
            recovered_after_timeout = True
            response = {
                "ok": True,
                "role": "windows_sub_engel_node"
                if node_kind_key(node_kind) == "windows"
                else "sub_engel_node",
                "node_kind": "windows_sub_engel_node"
                if node_kind_key(node_kind) == "windows"
                else "sub_engel_node",
                "node_os": "windows" if node_kind_key(node_kind) == "windows" else "linux",
                "session_token": proposed_token,
                "expires_at_utc": (
                    datetime.now(timezone.utc)
                    + timedelta(seconds=DEFAULT_SESSION_TTL_SECONDS)
                ).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                "allowed_actions": proof.get("allowed_actions", ALLOWED_ACTIONS),
                "pair_timeout_recovered": True,
            }
    if response.get("ok"):
        token = str(response.get("session_token") or proposed_token)
        if not token:
            return {
                "ok": False,
                "error": "pairing response did not establish a session token",
            }
        connection_family = infer_node_kind(response, url, node_kind)
        session = {
            "url": url.rstrip("/"),
            "controller_name": controller_name,
            "session_token": token,
            "session_token_hint": redacted(token),
            "role": response.get("role", "unknown"),
            "node_kind": response.get("node_kind", response.get("role", "unknown")),
            "node_os": response.get("node_os", "unknown"),
            "connection_family": connection_family,
            "expires_at_utc": response.get("expires_at_utc", "unknown"),
            "allowed_actions": response.get("allowed_actions", ALLOWED_ACTIONS),
            "paired_at_utc": utc_stamp(),
            "pair_timeout_recovered": recovered_after_timeout,
        }
        if response.get("hostname"):
            session["hostname"] = response.get("hostname")
        ips = response.get("local_ips")
        if isinstance(ips, list):
            session["last_known_ips"] = [str(ip) for ip in ips]
        if store:
            save_session(session, connection_family)
        append_receipt({
            "event": "paired_windows_sub_engel_node" if connection_family == "windows" else "paired_sub_engel_node",
            "url": url.rstrip("/"),
            "controller_name": controller_name,
            "connection_family": connection_family,
            "session_token_hint": redacted(token),
            "pair_timeout_recovered": recovered_after_timeout,
        })
        safe_response = dict(response)
        safe_response["session_token_hint"] = redacted(token)
        safe_response["connection_family"] = connection_family
        safe_response["pair_timeout_recovered"] = recovered_after_timeout
        if store:
            safe_response.pop("session_token", None)
        return safe_response
    return response


def health(url: str) -> dict[str, Any]:
    return request_json("GET", normalized_url(url, "/health"), timeout=DEFAULT_TIMEOUT)


def actions(url: str, token: str) -> dict[str, Any]:
    return request_json("GET", normalized_url(url, "/actions"), token=token, timeout=DEFAULT_TIMEOUT)


def discover_node_url(
    node_kind: str | None = None,
    token: str | None = None,
    session: dict[str, Any] | None = None,
    scan: bool = True,
    store: bool = False,
) -> dict[str, Any]:
    """Find a paired node after LAN/WiFi IP changes without opening a listener."""
    kind = node_kind_key(node_kind)
    session_data = dict(session or load_session(kind))
    port = discovery_port_for_kind(kind)
    candidates = candidate_urls_from_state(kind, session_data)
    checked: list[str] = []
    disabled_hosts = disabled_windows_hosts() if kind == "windows" else set()

    def try_url(url: str) -> dict[str, Any] | None:
        host, actual_port, _scheme = parsed_url_host_port(url, port)
        if not host:
            return None
        if host.lower() in disabled_hosts:
            checked.append(f"{url}:disabled")
            return None
        if not tcp_open(host, actual_port):
            checked.append(f"{url}:closed")
            return None
        health_payload = request_json("GET", normalized_url(url, "/health"), timeout=DISCOVERY_HTTP_TIMEOUT)
        if not health_matches_kind(health_payload, kind):
            checked.append(f"{url}:not-node")
            return None
        if token:
            action_payload = actions(url, token)
            if not action_payload.get("ok"):
                checked.append(f"{url}:token-rejected")
                return None
        return {"ok": True, "url": url.rstrip("/"), "health": health_payload, "checked": checked}

    for url in candidates:
        found = try_url(url)
        if found:
            found["source"] = "stored-state"
            if store and session_data:
                session_data["url"] = found["url"]
                session_data["last_resolved_at_utc"] = utc_stamp()
                session_data["last_resolved_source"] = found["source"]
                save_session(session_data, kind)
            return found

    if scan:
        scan_hosts: list[str] = []
        seen_hosts: set[str] = set()
        for url in candidates:
            for host in private_scan_hosts(url, kind):
                if host not in seen_hosts:
                    seen_hosts.add(host)
                    scan_hosts.append(host)
        open_hosts: list[str] = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=DISCOVERY_MAX_WORKERS) as executor:
            future_map = {executor.submit(tcp_open, host, port): host for host in scan_hosts}
            for future in concurrent.futures.as_completed(future_map):
                host = future_map[future]
                try:
                    is_open = future.result()
                except Exception:
                    is_open = False
                if is_open:
                    open_hosts.append(host)
        for host in sorted(open_hosts, key=lambda value: tuple(int(part) for part in value.split("."))):
            url = make_base_url(host, port)
            found = try_url(url)
            if found:
                found["source"] = "lan-scan"
                found["scanned_hosts"] = len(scan_hosts)
                if store and session_data:
                    session_data["url"] = found["url"]
                    session_data["last_resolved_at_utc"] = utc_stamp()
                    session_data["last_resolved_source"] = found["source"]
                    save_session(session_data, kind)
                return found
    return {"ok": False, "error": "paired node not found on stored URLs or LAN scan", "checked": checked}


def update_session_from_action(kind: str, session: dict[str, Any], node_url: str, action: str, response: dict[str, Any]) -> None:
    if not session:
        return
    if not response.get("ok"):
        session["live_health_ok"] = False
        session["last_auth_probe_ok"] = False
        session["last_auth_probe_at_utc"] = utc_stamp()
        session["last_auth_error"] = str(response.get("error") or "authenticated action failed")[:500]
        if int(response.get("http_status") or 0) in {401, 403}:
            session["paired"] = False
            session["meeting_ready"] = False
            session["session_invalid"] = True
        save_session(session, kind)
        return
    session["url"] = node_url.rstrip("/")
    session["last_seen_utc"] = utc_stamp()
    session["live_health_ok"] = True
    session["paired"] = True
    session["meeting_ready"] = True
    session["session_invalid"] = False
    session["last_auth_probe_ok"] = True
    session["last_auth_probe_at_utc"] = utc_stamp()
    session["last_auth_error"] = ""
    result = response.get("result") if isinstance(response.get("result"), dict) else {}
    stdout = result.get("stdout") if isinstance(result, dict) else ""
    if action == "session.renew":
        renewed = decode_action_stdout(response)
        token = str(renewed.get("session_token") or "")
        if token:
            session["session_token"] = token
            session["session_token_hint"] = str(renewed.get("session_token_hint") or redacted(token))
            session["expires_at_utc"] = str(renewed.get("expires_at_utc") or session.get("expires_at_utc") or "")
            session["controller_name"] = str(renewed.get("controller_name") or session.get("controller_name") or DEFAULT_CONTROLLER_NAME)
            session["renewed_at_utc"] = str(renewed.get("renewed_at_utc") or utc_stamp())
    if action == "node.status" and isinstance(stdout, str):
        try:
            status = json.loads(stdout)
        except json.JSONDecodeError:
            status = {}
        if isinstance(status, dict):
            if status.get("hostname"):
                session["hostname"] = status.get("hostname")
            if status.get("node_root"):
                session["node_root"] = status.get("node_root")
                session["node_root_on_os_drive"] = bool(status.get("node_root_on_os_drive"))
            if status.get("state_dir"):
                session["state_dir"] = status.get("state_dir")
                session["state_dir_on_os_drive"] = bool(status.get("state_dir_on_os_drive"))
            ips = status.get("local_ips")
            if isinstance(ips, list):
                session["last_known_ips"] = [str(ip) for ip in ips]
            if status.get("platform"):
                session["platform"] = status.get("platform")
    save_session(session, kind)


def run_action(
    action: str,
    url: str | None = None,
    token: str | None = None,
    node_kind: str | None = None,
    node_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if action not in ALLOWED_ACTIONS:
        return {
            "ok": False,
            "error": "action blocked by Engel App client allowlist",
            "action": action,
            "allowed_actions": ALLOWED_ACTIONS,
            "blocked_actions": BLOCKED_ACTIONS,
        }
    kind = node_kind_key(node_kind)
    request_timeout = DEFAULT_TIMEOUT + 20
    if payload:
        for timeout_key in ("client_timeout_seconds", "http_timeout_seconds"):
            if timeout_key not in payload:
                continue
            try:
                request_timeout = int(float(payload[timeout_key]))
            except (TypeError, ValueError):
                request_timeout = DEFAULT_TIMEOUT + 20
            request_timeout = max(2, min(600, request_timeout))
            break
    if should_use_ct246_control_relay(
        kind=kind,
        node_id=node_id,
        explicit_url=url,
        explicit_token=token,
    ):
        relay_response = run_action_via_ct246(
            action,
            node_id=str(node_id),
            payload=payload,
            timeout=request_timeout,
        )
        if relay_response.get("ct246_relay_reached") is True:
            append_receipt({
                "event": "sub_engel_remote_action",
                "url": "ct246-authoritative-relay",
                "action": action,
                "connection_family": kind,
                "control_transport": relay_response.get("control_transport"),
                "ok": bool(relay_response.get("ok")),
                "return_code": relay_response.get("result", {}).get("return_code")
                if isinstance(relay_response.get("result"), dict)
                else None,
            })
            return relay_response
    session = load_session(kind, node_id)
    node_url = (url or runtime_node_url(session)).rstrip("/")
    session_token = token or str(session.get("session_token", ""))
    if not node_url:
        return {"ok": False, "error": f"no node URL provided and no stored {kind} Sub-Engel session exists"}
    if not session_token:
        return {"ok": False, "error": f"no session token provided and no stored {kind} Sub-Engel session exists"}
    request_payload = {"action": action, "payload": payload or {}}
    if payload:
        for key, value in payload.items():
            if key != "action":
                request_payload[key] = value
    response = request_json(
        "POST",
        normalized_url(node_url, "/node/command"),
        request_payload,
        token=session_token,
        timeout=request_timeout,
    )
    if network_error(response) and not url:
        resolved = discover_node_url(kind, session_token, session, scan=True, store=True)
        if resolved.get("ok"):
            node_url = str(resolved.get("url") or node_url).rstrip("/")
            session = load_session(kind)
            response = request_json(
                "POST",
                normalized_url(node_url, "/node/command"),
                request_payload,
                token=session_token,
                timeout=request_timeout,
            )
            if isinstance(response, dict):
                response.setdefault("rediscovered_url", node_url)
                response.setdefault("rediscovery_source", resolved.get("source"))
    append_receipt({
        "event": "sub_engel_remote_action",
        "url": node_url,
        "action": action,
        "connection_family": kind,
        "ok": bool(response.get("ok")),
        "return_code": response.get("result", {}).get("return_code") if isinstance(response.get("result"), dict) else None,
    })
    update_session_from_action(kind, session, node_url, action, response)
    return response


def audit_windows_no_c() -> dict[str, Any]:
    nodes = list_node_sessions("windows")
    results: list[dict[str, Any]] = []
    for item in nodes:
        node_id = str(item.get("node_id") or "node")
        session = item.get("session") if isinstance(item.get("session"), dict) else {}
        url = str(session.get("url") or "").rstrip("/")
        node_result: dict[str, Any] = {
            "node_id": node_id,
            "url": url,
            "ok": False,
            "issues": [],
        }
        if not url:
            node_result["issues"].append("missing_url")
            results.append(node_result)
            continue
        health_payload = health(url)
        status_response = run_action("node.status", node_kind="windows", node_id=node_id)
        remote_response = run_action("remote.status", node_kind="windows", node_id=node_id)
        status_payload = decode_action_stdout(status_response)
        remote_text = action_stdout_text(remote_response)

        node_root = health_payload.get("node_root") or status_payload.get("node_root") or session.get("node_root") or ""
        state_dir = health_payload.get("state_dir") or status_payload.get("state_dir") or session.get("state_dir") or ""
        node_root_on_os_drive = health_payload.get("node_root_on_os_drive")
        if node_root_on_os_drive is None:
            node_root_on_os_drive = status_payload.get("node_root_on_os_drive")
        if node_root_on_os_drive is None:
            node_root_on_os_drive = is_os_drive_text(node_root)
        state_dir_on_os_drive = health_payload.get("state_dir_on_os_drive")
        if state_dir_on_os_drive is None:
            state_dir_on_os_drive = status_payload.get("state_dir_on_os_drive")
        if state_dir_on_os_drive is None:
            state_dir_on_os_drive = is_os_drive_text(state_dir)

        remote_status_mentions_c_state = "state directory: c:\\" in remote_text.replace("/", "\\").lower()
        missing_health_fields = not ("node_root_on_os_drive" in health_payload and "state_dir_on_os_drive" in health_payload)
        missing_status_fields = not ("node_root_on_os_drive" in status_payload and "state_dir_on_os_drive" in status_payload)

        issues: list[str] = []
        if not health_payload.get("ok"):
            issues.append("health_not_ok")
        if not status_response.get("ok"):
            issues.append("node_status_not_ok")
        if not remote_response.get("ok"):
            issues.append("remote_status_not_ok")
        if missing_health_fields and missing_status_fields:
            issues.append("missing_no_c_health_status_fields")
        if bool(node_root_on_os_drive):
            issues.append("node_root_on_os_drive")
        if bool(state_dir_on_os_drive):
            issues.append("state_dir_on_os_drive")
        if remote_status_mentions_c_state:
            issues.append("remote_status_reports_c_state")

        node_result.update({
            "ok": not issues,
            "issues": issues,
            "hostname": health_payload.get("hostname") or status_payload.get("hostname") or session.get("hostname", ""),
            "node_root": node_root,
            "state_dir": state_dir,
            "node_root_on_os_drive": bool(node_root_on_os_drive),
            "state_dir_on_os_drive": bool(state_dir_on_os_drive),
            "health_has_no_c_fields": not missing_health_fields,
            "status_has_no_c_fields": not missing_status_fields,
            "remote_status_mentions_c_state": remote_status_mentions_c_state,
        })
        results.append(node_result)
    report = {
        "ok": bool(results) and all(item.get("ok") for item in results),
        "created_at_utc": utc_stamp(),
        "node_count": len(results),
        "nodes": results,
    }
    write_json(REPORT_DIR / "windows_no_c_audit_latest.json", report)
    return report


def forget(node_kind: str | None = None, node_id: str | None = None) -> None:
    if node_id:
        try:
            node_session_path(node_kind, node_id).unlink()
        except FileNotFoundError:
            pass
        # If the removed node was also the active/legacy node, clear that too.
        active = read_json(session_path_for_node_kind(node_kind))
        if active and node_id_for_session(active) == _safe_node_id(node_id):
            try:
                session_path_for_node_kind(node_kind).unlink()
            except FileNotFoundError:
                pass
        return
    try:
        session_path_for_node_kind(node_kind).unlink()
    except FileNotFoundError:
        pass


def print_json(data: dict[str, Any]) -> int:
    print(json.dumps(data, indent=2, sort_keys=True))
    return 0 if data.get("ok", True) else 1


def parse_payload_arg(raw: str) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"--payload-json is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit("--payload-json must decode to a JSON object")
    return data


def parse_payload_file(path_text: str) -> dict[str, Any]:
    if not path_text:
        return {}
    path = Path(path_text)
    data = read_json(path)
    if not data:
        raise SystemExit(f"--payload-file did not contain a JSON object: {path}")
    return data


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Engel App Sub-Engel node remote-control client")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("help", help="show protocol help")
    status_parser = sub.add_parser("status", help="show stored pairing status")
    status_parser.add_argument("--node-kind", choices=["linux", "windows"], default="linux")
    forget_parser = sub.add_parser("forget", help="remove stored Sub-Engel session")
    forget_parser.add_argument("--node-kind", choices=["linux", "windows"], default="linux")
    forget_parser.add_argument("--node", default=None, help="target a specific registered node id (default: active node)")

    health_parser = sub.add_parser("health", help="query node health endpoint")
    health_parser.add_argument("--url", required=True)

    pair_parser = sub.add_parser("pair", help="pair with a node using a node-generated code")
    pair_parser.add_argument("--url", required=True)
    pair_parser.add_argument("--pairing-code", required=True)
    pair_parser.add_argument("--controller-name", default=DEFAULT_CONTROLLER_NAME)
    pair_parser.add_argument("--node-kind", choices=["auto", "linux", "windows"], default="auto")
    pair_parser.add_argument("--no-store", action="store_true")

    actions_parser = sub.add_parser("actions", help="list node-reported actions")
    actions_parser.add_argument("--url")
    actions_parser.add_argument("--session-token")
    actions_parser.add_argument("--node-kind", choices=["linux", "windows"], default="linux")
    actions_parser.add_argument("--node", default=None, help="target a specific registered node id")

    discover_parser = sub.add_parser("discover", help="rediscover a paired node after LAN/WiFi IP changes")
    discover_parser.add_argument("--node-kind", choices=["linux", "windows"], default="windows")
    discover_parser.add_argument("--no-store", action="store_true")
    discover_parser.add_argument("--node", default=None, help="target a specific registered node id")

    command_parser = sub.add_parser("command", help="run one allowlisted node action")
    command_parser.add_argument("--action", required=True, choices=ALLOWED_ACTIONS)
    command_parser.add_argument("--url")
    command_parser.add_argument("--session-token")
    command_parser.add_argument("--node-kind", choices=["linux", "windows"], default="linux")
    command_parser.add_argument("--node", default=None, help="target a specific registered node id")
    command_parser.add_argument("--payload-json", default="", help="optional JSON object passed as node command payload")
    command_parser.add_argument("--payload-file", default="", help="optional JSON file passed as node command payload")
    sub.add_parser("audit-no-c", help="audit paired Windows Sub-Engel nodes for C-backed state")

    args = parser.parse_args(argv)
    command = args.command or "status"

    if command == "help":
        print(render_help())
        return 0
    if command == "status":
        print(render_status(getattr(args, "node_kind", "linux")))
        return 0
    if command == "forget":
        forget(getattr(args, "node_kind", "linux"), getattr(args, "node", None))
        print("Stored Sub-Engel node session removed.")
        return 0
    if command == "health":
        return print_json(health(args.url))
    if command == "pair":
        return print_json(pair_node(
            args.url,
            args.pairing_code,
            args.controller_name,
            store=not args.no_store,
            node_kind=args.node_kind,
        ))
    if command == "actions":
        session = load_session(args.node_kind, getattr(args, "node", None))
        url = (args.url or str(session.get("url", ""))).rstrip("/")
        token = args.session_token or str(session.get("session_token", ""))
        if not url or not token:
            return print_json({"ok": False, "error": "actions requires --url/--session-token or a stored session"})
        return print_json(actions(url, token))
    if command == "discover":
        session = load_session(args.node_kind, getattr(args, "node", None))
        token = str(session.get("session_token", ""))
        return print_json(discover_node_url(args.node_kind, token, session, scan=True, store=not args.no_store))
    if command == "command":
        payload = parse_payload_file(args.payload_file) if args.payload_file else parse_payload_arg(args.payload_json)
        return print_json(run_action(
            args.action,
            args.url,
            args.session_token,
            args.node_kind,
            getattr(args, "node", None),
            payload,
        ))
    if command == "audit-no-c":
        return print_json(audit_windows_no_c())
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
