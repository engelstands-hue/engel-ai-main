#!/usr/bin/env python3
"""Local-only Engel chat health probe that can file self-upgrade issues."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import sys
from pathlib import Path
from urllib import request


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import engel_self_upgrade_system as system


DEFAULT_TARGETS = [
    ("rog_chat_tunnel", "http://127.0.0.1:24680/health", "chat"),
    ("grok_bridge", "http://127.0.0.1:24880/health", "provider_bridge"),
    ("claude_bridge", "http://127.0.0.1:24882/health", "provider_bridge"),
    ("chatgpt_bridge", "http://127.0.0.1:24884/health", "provider_bridge"),
    ("gemini_bridge", "http://127.0.0.1:24886/health", "provider_bridge"),
    ("codex_bridge", "http://127.0.0.1:24888/health", "provider_bridge"),
]


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def local_only_url(url: str) -> bool:
    return url.startswith("http://127.0.0.1:") or url.startswith("http://localhost:")


def probe_url(url: str, timeout: float) -> dict[str, object]:
    if not local_only_url(url):
        return {"ok": False, "error": "non-local URL refused", "url": url}
    try:
        with request.urlopen(url, timeout=timeout) as response:
            raw = response.read(2048).decode("utf-8", errors="replace")
            return {"ok": 200 <= response.status < 300, "status": response.status, "body_preview": raw[:500], "url": url}
    except Exception as exc:
        return {"ok": False, "error": type(exc).__name__ + ": " + str(exc), "url": url}


def run_probe(timeout: float) -> dict[str, object]:
    checks = []
    for name, url, surface in DEFAULT_TARGETS:
        result = probe_url(url, timeout)
        result["name"] = name
        result["surface"] = surface
        checks.append(result)
    return {
        "schema": "ENGEL_CHAT_SELF_HEAL_PROBE_V1",
        "created_at_utc": now_utc(),
        "local_only": True,
        "checks": checks,
        "ok": all(bool(item.get("ok")) for item in checks),
    }


def write_probe_report(report: dict[str, object]) -> Path:
    out = system.REPORT_ROOT / "chat_self_heal"
    out.mkdir(parents=True, exist_ok=True)
    path = out / ("chat_self_heal_probe_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + ".json")
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def create_issues_for_failures(report: dict[str, object], report_path: Path) -> list[str]:
    issue_paths: list[str] = []
    checks = report.get("checks", [])
    if not isinstance(checks, list):
        return issue_paths
    for check in checks:
        if not isinstance(check, dict) or check.get("ok") is True:
            continue
        issue = system.build_issue(
            source="chat_self_heal_probe",
            symptom=f"{check.get('name')} failed health check: {check.get('error') or check.get('status')}",
            severity="medium",
            affected_surface=str(check.get("surface") or "chat"),
            evidence_paths=[str(report_path)],
        )
        path = system.write_issue(issue)
        issue_paths.append(system.project_relative(path))
    return issue_paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Engel local-only chat self-heal probe.")
    parser.add_argument("--timeout", type=float, default=2.0)
    parser.add_argument("--write-issues", action="store_true", help="Write self-upgrade issues for failed checks.")
    args = parser.parse_args(argv)
    report = run_probe(args.timeout)
    report_path = write_probe_report(report)
    issue_paths = create_issues_for_failures(report, report_path) if args.write_issues else []
    print(json.dumps({"ok": report["ok"], "report_path": system.project_relative(report_path), "issue_paths": issue_paths, "report": report}, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
