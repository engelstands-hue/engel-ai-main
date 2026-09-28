"""Engel AI ↔ bundled engelsandbox (Linux/KVM hypervisor) integration runner.

Backs the ``engel.engel_sandbox.*`` routes registered in
``engel_ai_update_routes``. The vendored tree at
``D:\\b.WorkSpace\\Engel App\\engelsandbox_main`` is a fork of
Tencent Cloud's CubeSandbox, case-preservingly renamed
(cube→engel everywhere — 948 files, 22,843 substitutions,
94 path renames). EngelSandbox is an E2B-compatible
hardware-isolated sandbox platform that boots Linux microVMs
in tens of milliseconds.

Critical runtime constraint: EngelSandbox's SERVER side requires
Linux + KVM. It cannot run natively on Windows. On a Windows
host you bring it up inside WSL2 (with nested virtualization)
or point Engel AI at a remote EngelSandbox cluster.

This runner is a thin HTTP client that talks to a running
EngelSandbox server via the dashboard API (``/engelapi/v1/``)
and the E2B-compatible sandbox API. When ``ENGEL_SANDBOX_URL``
is unset or unreachable, every route degrades gracefully with
a "server not configured" message that points at the bring-up
guide rather than fabricating success.

Public surface:

    render_engel_sandbox_status()       — health + cluster overview
    render_engel_sandbox_nodes()        — list cluster nodes
    render_engel_sandbox_list()         — list active sandboxes (E2B)
    render_engel_sandbox_create()       — POST /sandboxes
    render_engel_sandbox_delete()       — DELETE /sandboxes/<id>
    render_engel_sandbox_bring_up()     — WSL2 bring-up instructions
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

import httpx

SANDBOX_ROOT: Path = Path(__file__).resolve().parent / "engelsandbox_main"
DEFAULT_URL = "http://localhost:3000"
DASHBOARD_PREFIX = "/engelapi/v1"


def _server_url() -> str:
    return os.environ.get("ENGEL_SANDBOX_URL", DEFAULT_URL).rstrip("/")


def _auth_token() -> Optional[str]:
    return os.environ.get("ENGEL_SANDBOX_API_KEY") or os.environ.get("ENGEL_SANDBOX_TOKEN")


def _wrap(title: str, body: str, *, configured: bool = True) -> str:
    safety_lines = [
        "Safety:",
        f"- Server URL: {_server_url()} (override via ENGEL_SANDBOX_URL)",
        "- Engel Sandbox SERVER requires Linux/KVM; run via WSL2 or remote host.",
        "- Routes are HTTP-only — no source mutation, no kernel ops, no host changes.",
        "- Autonomy and background work permitted (2026-05-19 ruling).",
    ]
    if not configured:
        safety_lines.append("- Ask 'engel sandbox bring up' for WSL2 setup steps.")
    return f"{title}\n\n{body}\n\n" + "\n".join(safety_lines)


def _client() -> httpx.Client:
    headers: dict[str, str] = {"Accept": "application/json"}
    tok = _auth_token()
    if tok:
        headers["Authorization"] = f"Bearer {tok}"
    return httpx.Client(timeout=httpx.Timeout(5.0, connect=2.0), headers=headers)


def _format_unreachable(action: str, exc: Exception) -> str:
    return _wrap(
        f"Engel Sandbox — {action} (server not reachable)",
        (
            f"Could not reach {_server_url()}: {type(exc).__name__}: {exc}\n"
            "\n"
            "Likely causes:\n"
            "  1. Engel Sandbox server is not running (most common on Windows).\n"
            "  2. Wrong ENGEL_SANDBOX_URL — currently '" + _server_url() + "'.\n"
            "  3. Firewall blocking the port (default 3000).\n"
            "\n"
            "To bring the server up locally on Windows, ask Engel AI:\n"
            "  engel sandbox bring up"
        ),
        configured=False,
    )


def _format_status_error(action: str, resp: httpx.Response) -> str:
    body = (resp.text or "").strip()[:2000]
    return _wrap(
        f"Engel Sandbox — {action} returned HTTP {resp.status_code}",
        body or "(empty body)",
    )


def _format_json(obj: Any) -> str:
    try:
        return json.dumps(obj, indent=2, sort_keys=True)
    except (TypeError, ValueError):
        return str(obj)


def render_engel_sandbox_status(_payload: str = "") -> str:
    url = _server_url() + DASHBOARD_PREFIX
    try:
        with _client() as c:
            health = c.get(url + "/health")
            cluster = c.get(url + "/cluster/overview")
    except httpx.HTTPError as exc:
        return _format_unreachable("status", exc)

    lines = [f"Dashboard API base    : {url}"]
    if health.is_success:
        try:
            lines.append("Health                : " + _format_json(health.json()))
        except ValueError:
            lines.append(f"Health                : (HTTP {health.status_code} non-JSON body)")
    else:
        lines.append(f"Health                : HTTP {health.status_code}")
    if cluster.is_success:
        try:
            lines.append("Cluster overview      : " + _format_json(cluster.json()))
        except ValueError:
            lines.append(f"Cluster overview      : HTTP {cluster.status_code}")
    else:
        lines.append(f"Cluster overview      : HTTP {cluster.status_code} (endpoint may be cluster-only)")
    return _wrap("Engel Sandbox — server status", "\n".join(lines))


def render_engel_sandbox_nodes(_payload: str = "") -> str:
    url = _server_url() + DASHBOARD_PREFIX + "/nodes"
    try:
        with _client() as c:
            resp = c.get(url)
    except httpx.HTTPError as exc:
        return _format_unreachable("nodes", exc)
    if not resp.is_success:
        return _format_status_error("nodes", resp)
    try:
        return _wrap("Engel Sandbox — cluster nodes", _format_json(resp.json()))
    except ValueError:
        return _wrap("Engel Sandbox — cluster nodes (non-JSON)", resp.text[:4000])


def render_engel_sandbox_list(_payload: str = "") -> str:
    # E2B-compatible API — sandboxes live under /v1/sandboxes on the
    # sandbox-API port (same root server, different prefix).
    url = _server_url() + "/sandboxes"
    try:
        with _client() as c:
            resp = c.get(url)
    except httpx.HTTPError as exc:
        return _format_unreachable("list sandboxes", exc)
    if not resp.is_success:
        return _format_status_error("list sandboxes", resp)
    try:
        return _wrap("Engel Sandbox — active sandboxes", _format_json(resp.json()))
    except ValueError:
        return _wrap("Engel Sandbox — active sandboxes (non-JSON)", resp.text[:4000])


def render_engel_sandbox_create(_payload: str = "") -> str:
    url = _server_url() + "/sandboxes"
    payload = {"template": "base", "metadata": {"created_by": "engel_ai"}}
    try:
        with _client() as c:
            resp = c.post(url, json=payload)
    except httpx.HTTPError as exc:
        return _format_unreachable("create sandbox", exc)
    if not resp.is_success:
        return _format_status_error("create sandbox", resp)
    try:
        return _wrap("Engel Sandbox — sandbox created", _format_json(resp.json()))
    except ValueError:
        return _wrap("Engel Sandbox — sandbox created (non-JSON)", resp.text[:4000])


def render_engel_sandbox_delete(payload: str = "") -> str:
    sandbox_id = (payload or "").strip().split()[-1] if payload else ""
    if not sandbox_id or sandbox_id == "delete":
        return _wrap(
            "Engel Sandbox — delete usage",
            "Provide a sandbox id after the trigger:\n"
            "  engel sandbox delete <sandbox_id>\n"
            "List active sandboxes with 'engel sandbox list'.",
        )
    url = f"{_server_url()}/sandboxes/{sandbox_id}"
    try:
        with _client() as c:
            resp = c.delete(url)
    except httpx.HTTPError as exc:
        return _format_unreachable("delete sandbox", exc)
    if not resp.is_success:
        return _format_status_error(f"delete sandbox {sandbox_id}", resp)
    return _wrap(
        f"Engel Sandbox — sandbox {sandbox_id} deleted",
        (resp.text or "(server returned empty body)")[:2000],
    )


def render_engel_sandbox_bring_up(_payload: str = "") -> str:
    readme = SANDBOX_ROOT / "docs" / "guide" / "quickstart.md"
    excerpt = ""
    if readme.is_file():
        try:
            text = readme.read_text(encoding="utf-8")
            excerpt = "\n".join(text.splitlines()[:30])
        except OSError:
            excerpt = "(quickstart.md present but unreadable)"
    else:
        excerpt = "(bundled quickstart.md missing)"

    body = (
        "Engel Sandbox is a Linux/KVM hypervisor — its SERVER cannot run\n"
        "natively on Windows. Bring it up via WSL2:\n"
        "\n"
        "  1) Verify the WSL distro is registered:\n"
        "       wsl --list --verbose\n"
        "     You should see Ubuntu-22.04 with VERSION 2. If it's\n"
        "     missing, run:\n"
        "       wsl --install -d Ubuntu-22.04 --no-launch\n"
        "  2) Open PowerShell, then:\n"
        "       wsl -d Ubuntu-22.04\n"
        "     Set up the Ubuntu user when prompted (first launch only).\n"
        "  3) Inside the Ubuntu shell, verify KVM:\n"
        "       ls -la /dev/kvm\n"
        "     If /dev/kvm is missing, enable Nested Virtualization on\n"
        "     your CPU (BIOS) and ensure WSL2 has it via\n"
        "     %UserProfile%\\.wslconfig:\n"
        "         [wsl2]\n"
        "         nestedVirtualization=true\n"
        "  4) From inside the WSL distro, run the one-click installer\n"
        "     (the vendored bundle's instructions remain in the\n"
        "     rebranded quickstart):\n"
        "       cd /mnt/d/b.WorkSpace/Engel\\ App/engelsandbox_main\n"
        "       cat docs/guide/quickstart.md\n"
        "     and follow the steps. The E2B-compatible REST API binds\n"
        "     on port 3000.\n"
        "  5) Once the server is up, point Engel AI at it:\n"
        "       set ENGEL_SANDBOX_URL=http://localhost:3000\n"
        "     Then 'engel sandbox status' will return real data.\n"
        "\n"
        "─── bundled quickstart.md (first 30 lines) ───\n" + excerpt
    )
    return _wrap("Engel Sandbox — WSL2 bring-up guide", body, configured=False)
