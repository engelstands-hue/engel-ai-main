#!/usr/bin/env python3
"""
Engel AI Main — doctor (OpenClaw `openclaw doctor` port).

Ported concept from OpenClaw (MIT): a one-shot health/repair check that reports
each subsystem's state and can --fix simple problems. This checks Engel's live
lanes + the OpenClaw-ported feature modules (failover loop, verbose, cron,
context compaction, sub-agents, MCP client, channels) and reports PASS/WARN/FAIL.

Usage:
  python tools/engel_doctor.py            # human report
  python tools/engel_doctor.py --json     # machine-readable
  python tools/engel_doctor.py --fix      # create missing dirs/catalog

MIT-attributed.
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

PORTED_MODULES = [
    "engel_agent_failover_loop", "engel_verbose", "engel_cron",
    "engel_context", "engel_subagents", "engel_mcp_client", "engel_channels",
    "engel_browser_tool", "engel_agent_harness", "engel_sandbox", "engel_usage",
    "engel_voice", "engel_canvas", "engel_media_gen",
]
# lane_id -> a cheap health URL to probe
LANE_HEALTH = {
    "rog-gpu": "http://127.0.0.1:8899/v1/models",
    "ct246-local": "http://127.0.0.1:24680/health",
    "gemini-api": "http://127.0.0.1:24886/health",
    "grok-cli": "http://127.0.0.1:24880/health",
    "claude-cli": "http://127.0.0.1:24882/health",
    "codex-cli": "http://127.0.0.1:24888/health",
    "chatgpt-browser": "http://127.0.0.1:24884/health",
}


def _probe(url: str, timeout: float = 3.0) -> tuple[bool, str]:
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            code = r.status
        return (200 <= code < 500), f"HTTP {code} {int((time.perf_counter()-t0)*1000)}ms"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {str(exc)[:60]}"


def run_doctor(fix: bool = False) -> dict:
    checks: list[dict] = []

    def add(name, ok, detail, level="PASS"):
        checks.append({"name": name, "level": "PASS" if ok else level, "detail": detail})

    # 1) ported feature modules importable
    for mod in PORTED_MODULES:
        try:
            importlib.import_module(mod)
            add(f"module {mod}", True, "importable")
        except Exception as exc:
            add(f"module {mod}", False, str(exc)[:80], "FAIL")

    # 1b) browser/computer-use tool needs Playwright in browser_ai_venv
    venv_py = ROOT / "runtime" / "browser_ai_venv" / "Scripts" / "python.exe"
    if venv_py.exists():
        try:
            import subprocess
            r = subprocess.run([str(venv_py), "-c", "from playwright.sync_api import sync_playwright"],
                               capture_output=True, timeout=25, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            add("browser tool (Playwright)", r.returncode == 0,
                "browser_ai_venv Playwright ready" if r.returncode == 0 else "playwright import failed", "WARN")
        except Exception as exc:
            add("browser tool (Playwright)", False, str(exc)[:60], "WARN")
    else:
        add("browser tool (Playwright)", False, "browser_ai_venv missing", "WARN")

    # 2) failover catalog valid
    cat = ROOT / "runtime" / "config" / "engel_failover_catalog.json"
    if cat.exists():
        try:
            data = json.loads(cat.read_text(encoding="utf-8"))
            n = len(data.get("lanes", {}))
            add("failover catalog", True, f"{n} lanes, chain={len(data.get('default_chain', []))}")
        except Exception as exc:
            add("failover catalog", False, f"invalid JSON: {exc}", "FAIL")
    else:
        if fix:
            add("failover catalog", False, "missing (run the port to regenerate)", "WARN")
        else:
            add("failover catalog", False, "missing", "WARN")

    # 3) cron store dir + verbose log dir
    for label, p in [("cron store dir", ROOT / "runtime" / "cron"),
                     ("verbose log dir", Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Engel AI Main" / "logs")]:
        if p.exists():
            add(label, True, str(p))
        elif fix:
            try:
                p.mkdir(parents=True, exist_ok=True)
                add(label, True, f"created {p}")
            except Exception as exc:
                add(label, False, str(exc), "FAIL")
        else:
            add(label, False, f"missing {p} (use --fix)", "WARN")

    # 4) live failover lanes
    up = 0
    for lane, url in LANE_HEALTH.items():
        ok, detail = _probe(url)
        if ok:
            up += 1
        add(f"lane {lane}", ok, detail, "WARN")
    add("failover chain readiness", up >= 2, f"{up}/{len(LANE_HEALTH)} lanes reachable"
        + ("" if up >= 2 else " — need >=2 for real failover"), "WARN")

    fails = sum(1 for c in checks if c["level"] == "FAIL")
    warns = sum(1 for c in checks if c["level"] == "WARN")
    passes = sum(1 for c in checks if c["level"] == "PASS")
    return {"checks": checks, "pass": passes, "warn": warns, "fail": fails,
            "healthy": fails == 0 and up >= 2}


def _cli(argv=None) -> int:
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    ap = argparse.ArgumentParser(description="Engel doctor (OpenClaw doctor port).")
    ap.add_argument("--fix", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    report = run_doctor(fix=a.fix)
    if a.json:
        print(json.dumps(report, indent=2))
        return 0 if report["healthy"] else 1
    glyph = {"PASS": "✓", "WARN": "!", "FAIL": "✗"}
    print("=== Engel AI Main — doctor ===")
    for c in report["checks"]:
        print(f"  {glyph.get(c['level'], '?')} [{c['level']:4}] {c['name']:32} {c['detail']}")
    print(f"\n  {report['pass']} pass · {report['warn']} warn · {report['fail']} fail  -> "
          + ("HEALTHY" if report["healthy"] else "NEEDS ATTENTION"))
    return 0 if report["healthy"] else 1


if __name__ == "__main__":
    raise SystemExit(_cli())
