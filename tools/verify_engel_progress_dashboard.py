#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "engel_progress_dashboard.py"


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def run_module(command: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(MODULE), command],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=20,
        check=False,
    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def check_source_static() -> None:
    source = MODULE.read_text(encoding="utf-8")
    for needle in [
        "READ_ONLY_PROGRESS_STATUS",
        "ENGEL_FEATURE_EXPANSION_PACK_V1",
        "engel_memory_candidate_inventory.build_inventory()",
        "engel_archive_shelf_manager.build_archive_shelf_status()",
        "new_ui_backend_wired",
        "known_full_verifier_blocker",
        "packaging_status",
        "NO_PACKAGING",
        "NO_RUNTIME_ENABLEMENT",
        "NO_TRUSTED_MEMORY_WRITE",
        "NO_MEMORY_PROMOTION",
        "NO_ROUTE_QUEUE_MUTATION",
    ]:
        require(needle in source, "progress dashboard source missing required text: " + needle)
    for forbidden in [
        "write_text(",
        "write_bytes(",
        "mkdir(",
        "unlink(",
        "rmtree(",
        "copyfile(",
        "move(",
        "APPROVE_PROMOTE_MEMORY_CANDIDATE",
        "APPROVE_FIX_CANDIDATE",
        "subprocess",
        "requests",
        "urllib",
        "socket",
    ]:
        require(forbidden not in source, "progress dashboard source contains forbidden behavior: " + forbidden)


def check_cli() -> None:
    status = run_module("status")
    require(status.returncode == 0, "progress dashboard status command failed: " + status.stderr)
    require("Engel Progress Dashboard" in status.stdout, "status output missing title")
    require("D:\\b.WorkSpace\\Engel App" in status.stdout, "status output missing active B workspace")
    require("Code Companion:" in status.stdout, "status output missing Code Companion section")
    require("Memory Candidate Inventory:" in status.stdout, "status output missing inventory section")
    require("Archive Shelf Manager:" in status.stdout, "status output missing archive section")
    require("Packaging:" in status.stdout and "skipped" in status.stdout, "status output missing packaging skipped")
    require("NO_TRUSTED_MEMORY_WRITE" in status.stdout, "status output missing trusted-memory boundary")

    report = run_module("report")
    require(report.returncode == 0, "progress dashboard report command failed: " + report.stderr)
    require("# Engel Progress Dashboard" in report.stdout, "report output missing markdown title")

    rendered = run_module("json")
    require(rendered.returncode == 0, "progress dashboard json command failed: " + rendered.stderr)
    payload = json.loads(rendered.stdout)
    require(payload["schema"] == "engel_progress_dashboard_v1", "unexpected progress dashboard schema")
    require(payload["mode"] == "READ_ONLY_PROGRESS_STATUS", "progress dashboard mode changed")
    require(payload["feature_expansion_pack"] == "ENGEL_FEATURE_EXPANSION_PACK_V1", "feature pack name changed")
    require(payload["active_workspace"] == str(ROOT), "active workspace mismatch")
    require(payload["code_companion"]["new_ui_backend_wired"] is True, "new Code Companion UI/backend not detected")
    require(payload["code_companion"]["explicit_run_button"] is True, "explicit Run button not detected")
    require(payload["code_companion"]["run_timeout_seconds"] == 20, "Code Companion run timeout changed")
    require(payload["archive_shelf_manager"]["external_archive_required"] is False, "archive became required")
    require(payload["packaging_status"] == "skipped", "packaging status changed")
    safety = payload["safety"]
    for key in [
        "packaging_enabled",
        "runtime_enabled",
        "provider_calls_enabled",
        "network_enabled",
        "trusted_memory_write_enabled",
        "memory_promotion_enabled",
        "candidate_approval_enabled",
        "source_mutation_from_candidate_enabled",
        "route_mutation_enabled",
        "queue_mutation_enabled",
        "background_worker_enabled",
        "autonomy_enabled",
    ]:
        require(safety[key] is False, "unsafe progress dashboard flag enabled: " + key)


def main() -> int:
    try:
        require(MODULE.exists(), "progress dashboard module missing")
        check_source_static()
        check_cli()
    except CheckFailure as exc:
        print("[FAIL] " + str(exc))
        return 1
    print("[PASS] ENGEL progress dashboard verifier passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
