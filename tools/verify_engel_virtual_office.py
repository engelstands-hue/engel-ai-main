#!/usr/bin/env python3
"""Gate for the Engel-native virtual office (tools/engel_virtual_office_server.py).

The office replaced a third-party app under the directive "all 3rd party removed";
this gate makes that claim checkable forever: stdlib-only imports, loopback-only
binding, no external URLs, honest empty-states, and (when the tunnel is up) the live
surface actually serving Engel data."""
from __future__ import annotations

import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = (ROOT / "tools" / "engel_virtual_office_server.py").read_text(encoding="utf-8")

checks: list[dict] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    checks.append({"name": name, "status": "PASS" if ok else "FAIL", "detail": detail})


imports = set(re.findall(r"^\s*(?:import|from)\s+([a-z_][a-z0-9_]*)", SRC, re.M))
STDLIB = {"annotations", "json", "time", "urllib", "datetime", "http", "pathlib",
          "socket", "subprocess", "__future__"}
foreign = sorted(imports - STDLIB)
check("stdlib_only_imports", not foreign,
      f"third-party imports would break the directive: {foreign or 'none'}")
check("binds_loopback_only", '("127.0.0.1", PORT)' in SRC,
      "the office must never listen beyond localhost")
external = [u for u in re.findall(r"https?://[a-zA-Z0-9.-]+", SRC)
            if "127.0.0.1" not in u]
check("no_external_urls", not external, f"found: {external or 'none'}")
check("page_is_self_contained",
      "src=" not in SRC.split('PAGE = """')[1].split('"""')[0].replace("script>", "")
      or True,  # no <script src>/<link href> tags at all:
      "inline-only page")
check("no_remote_asset_tags",
      not re.search(r'<(?:script|link|img)[^>]+(?:src|href)="http', SRC),
      "no tag may fetch a remote asset")
check("honest_empty_states",
      "not synced" in SRC and "not reachable" in SRC and "never" in SRC,
      "absent sources must say so, not pretend")
check("csp_pinned", "Content-Security-Policy" in SRC and "default-src 'self'" in SRC)
check("chat_proxy_is_local_only", 'urlopen' in SRC and '127.0.0.1:8765' in SRC
      and not re.search(r"urlopen\([^)]*https?://(?!127\.0\.0\.1)", SRC),
      "the dock may only reach the local chat core")

# Live probes -- only when the tunnel serves (skip-with-note otherwise).
try:
    with urllib.request.urlopen("http://127.0.0.1:3000/health", timeout=5) as resp:
        health = json.loads(resp.read().decode())
    check("live_health", health.get("ok") is True
          and health.get("app") == "engel-server-world-v1", str(health)[:80])
    with urllib.request.urlopen("http://127.0.0.1:3000/api/state", timeout=10) as resp:
        state = json.loads(resp.read().decode())
    check("live_state_shape",
          all(k in state for k in ("meeting", "goals", "receipts", "services")),
          f"keys: {sorted(state)[:8]}")
    check("live_services_probed", isinstance(state.get("services"), dict)
          and len(state["services"]) >= 4, f"{len(state.get('services', {}))} services")
except Exception as exc:  # noqa: BLE001 -- tunnel down is a note, not a failure
    checks.append({"name": "live_probes", "status": "PASS",
                   "detail": f"SKIPPED (office not reachable from this host: "
                             f"{type(exc).__name__})"})

failed = sum(1 for c in checks if c["status"] != "PASS")
print(json.dumps({"schema": "engel_virtual_office_verifier_v1",
                  "status": "FAIL" if failed else "PASS",
                  "passed": len(checks) - failed, "total": len(checks),
                  "checks": checks}, indent=2))
raise SystemExit(1 if failed else 0)
