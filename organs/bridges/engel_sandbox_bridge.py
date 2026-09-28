from __future__ import annotations

import json
import os
import threading
from pathlib import Path

try:
    import requests
except ImportError:
    requests = None  # bridge will report this gracefully

ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
SANDBOX_SRC = ROOT / "external" / "CubeSandbox-master"

_LOCK = threading.Lock()
_CFG: dict = {
    "endpoint": os.environ.get("E2B_API_URL", "http://127.0.0.1:8080"),
    "api_key": os.environ.get("E2B_API_KEY", ""),
    "current_sandbox": None,
}


def _src_present() -> bool:
    return (SANDBOX_SRC / "CubeAPI" / "Cargo.toml").exists()


def _headers() -> dict:
    h = {"Content-Type": "application/json"}
    if _CFG["api_key"]:
        h["X-API-Key"] = _CFG["api_key"]
    return h


def _ep(path: str) -> str:
    base = _CFG["endpoint"].rstrip("/")
    return f"{base}{path}"


def sandbox_status() -> str:
    lines = ["# CubeSandbox Bridge Status", ""]
    lines.append(f"Source tree:    {'READY' if _src_present() else 'NOT FOUND'}  [{SANDBOX_SRC}]")
    lines.append(f"Endpoint:       {_CFG['endpoint']}")
    lines.append(f"API key:        {'SET' if _CFG['api_key'] else '(none)'}")
    lines.append(f"Active sandbox: {_CFG['current_sandbox'] or '(none)'}")
    lines.append("")

    if requests is None:
        lines.append("requests library not available — install with: pip install requests")
        return "\n".join(lines)

    try:
        r = requests.get(_ep("/health"), timeout=3)
        if r.status_code == 200:
            lines.append("Health:         REACHABLE ✓")
        else:
            lines.append(f"Health:         HTTP {r.status_code}")
    except Exception as exc:
        lines.append(f"Health:         UNREACHABLE — {exc}")
        lines.append("")
        lines.append("CubeSandbox is a Linux+KVM hypervisor service. To use it:")
        lines.append("  1. Deploy CubeSandbox on a Linux host (see external/CubeSandbox-master/README.md)")
        lines.append("  2. Point Engel at it: sandbox endpoint <url>")
        lines.append("  3. Set API key if needed: sandbox key <api_key>")

    lines += [
        "",
        "Commands:",
        "  sandbox status                — show this page",
        "  sandbox endpoint <url>        — set CubeSandbox API URL",
        "  sandbox key <api_key>         — set API key",
        "  sandbox list                  — list sandboxes",
        "  sandbox create [template]     — create a sandbox (default template if omitted)",
        "  sandbox info <id>             — get details for a sandbox",
        "  sandbox kill <id>             — destroy a sandbox",
        "  sandbox use <id>              — set active sandbox",
        "  sandbox pause <id>            — pause a sandbox (preserves memory)",
        "  sandbox connect <id>          — connect/resume a sandbox",
    ]
    return "\n".join(lines)


def _require_requests() -> str | None:
    if requests is None:
        return "requests library not installed. Run: pip install requests"
    return None


def sandbox_set_endpoint(url: str) -> str:
    url = url.strip()
    if not url:
        return "Usage: sandbox endpoint <url>"
    _CFG["endpoint"] = url
    return f"Endpoint set to {url}"


def sandbox_set_key(key: str) -> str:
    _CFG["api_key"] = key.strip()
    return "API key updated." if key.strip() else "API key cleared."


def sandbox_list() -> str:
    err = _require_requests()
    if err:
        return err
    try:
        r = requests.get(_ep("/sandboxes"), headers=_headers(), timeout=10)
    except Exception as exc:
        return f"Request failed: {exc}"
    if r.status_code != 200:
        return f"HTTP {r.status_code}: {r.text[:300]}"
    try:
        data = r.json()
    except Exception:
        return f"Non-JSON response: {r.text[:300]}"
    if not data:
        return "No sandboxes."
    out = ["Sandboxes:"]
    items = data if isinstance(data, list) else data.get("sandboxes", [])
    for s in items[:20]:
        sid = s.get("sandboxID") or s.get("id") or "?"
        state = s.get("state") or s.get("status") or "?"
        tmpl = s.get("templateID") or s.get("template") or "?"
        out.append(f"  {sid}  state={state}  template={tmpl}")
    return "\n".join(out)


def sandbox_create(template: str = "") -> str:
    err = _require_requests()
    if err:
        return err
    body: dict = {}
    if template.strip():
        body["templateID"] = template.strip()
    try:
        r = requests.post(_ep("/sandboxes"), headers=_headers(), json=body, timeout=30)
    except Exception as exc:
        return f"Request failed: {exc}"
    if r.status_code not in (200, 201):
        return f"HTTP {r.status_code}: {r.text[:300]}"
    try:
        data = r.json()
    except Exception:
        return f"Created but non-JSON response: {r.text[:300]}"
    sid = data.get("sandboxID") or data.get("id")
    if sid:
        _CFG["current_sandbox"] = sid
        return f"Created sandbox {sid} (set as active)\n{json.dumps(data, indent=2)[:600]}"
    return f"Created:\n{json.dumps(data, indent=2)[:600]}"


def sandbox_info(sid: str) -> str:
    err = _require_requests()
    if err:
        return err
    sid = sid.strip() or _CFG["current_sandbox"]
    if not sid:
        return "Usage: sandbox info <id>  (or 'sandbox use <id>' first)"
    try:
        r = requests.get(_ep(f"/sandboxes/{sid}"), headers=_headers(), timeout=10)
    except Exception as exc:
        return f"Request failed: {exc}"
    if r.status_code != 200:
        return f"HTTP {r.status_code}: {r.text[:300]}"
    try:
        return json.dumps(r.json(), indent=2)[:1500]
    except Exception:
        return r.text[:1500]


def sandbox_kill(sid: str) -> str:
    err = _require_requests()
    if err:
        return err
    sid = sid.strip() or _CFG["current_sandbox"]
    if not sid:
        return "Usage: sandbox kill <id>"
    try:
        r = requests.delete(_ep(f"/sandboxes/{sid}"), headers=_headers(), timeout=15)
    except Exception as exc:
        return f"Request failed: {exc}"
    if r.status_code in (200, 204):
        if _CFG["current_sandbox"] == sid:
            _CFG["current_sandbox"] = None
        return f"Destroyed sandbox {sid}."
    return f"HTTP {r.status_code}: {r.text[:300]}"


def sandbox_use(sid: str) -> str:
    sid = sid.strip()
    if not sid:
        _CFG["current_sandbox"] = None
        return "Active sandbox cleared."
    _CFG["current_sandbox"] = sid
    return f"Active sandbox set to {sid}"


def sandbox_pause(sid: str) -> str:
    err = _require_requests()
    if err:
        return err
    sid = sid.strip() or _CFG["current_sandbox"]
    if not sid:
        return "Usage: sandbox pause <id>"
    try:
        r = requests.post(_ep(f"/sandboxes/{sid}/pause"), headers=_headers(), timeout=15)
    except Exception as exc:
        return f"Request failed: {exc}"
    if r.status_code in (200, 204):
        return f"Paused {sid}."
    return f"HTTP {r.status_code}: {r.text[:300]}"


def sandbox_connect(sid: str) -> str:
    err = _require_requests()
    if err:
        return err
    sid = sid.strip() or _CFG["current_sandbox"]
    if not sid:
        return "Usage: sandbox connect <id>"
    try:
        r = requests.post(_ep(f"/sandboxes/{sid}/connect"), headers=_headers(), timeout=15)
    except Exception as exc:
        return f"Request failed: {exc}"
    if r.status_code in (200, 201):
        _CFG["current_sandbox"] = sid
        try:
            return f"Connected to {sid}\n{json.dumps(r.json(), indent=2)[:600]}"
        except Exception:
            return f"Connected to {sid}"
    return f"HTTP {r.status_code}: {r.text[:300]}"


def handle_sandbox_command(args: str) -> str:
    text = (args or "").strip()
    if not text or text == "status":
        return sandbox_status()
    if text.startswith("endpoint"):
        return sandbox_set_endpoint(text[8:].strip())
    if text.startswith("key"):
        return sandbox_set_key(text[3:].strip())
    if text == "list":
        return sandbox_list()
    if text.startswith("create"):
        return sandbox_create(text[6:].strip())
    if text.startswith("info"):
        return sandbox_info(text[4:].strip())
    if text.startswith("kill"):
        return sandbox_kill(text[4:].strip())
    if text.startswith("use"):
        return sandbox_use(text[3:].strip())
    if text.startswith("pause"):
        return sandbox_pause(text[5:].strip())
    if text.startswith("connect"):
        return sandbox_connect(text[7:].strip())
    return f"Unknown sandbox subcommand: '{text}'. Try 'sandbox status'."
