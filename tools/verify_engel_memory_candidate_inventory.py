#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "engel_memory_candidate_inventory.py"


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
        "REPORT_ONLY_STATIC_INVENTORY",
        "NO_MEMORY_PROMOTION",
        "NO_TRUSTED_MEMORY_WRITE",
        "NO_APPROVED_MEMORY_WRITE",
        "NO_FIX_APPLY",
        "NO_SOURCE_MUTATION",
        "NO_QUEUE_ROUTE_MUTATION",
        "engel_approved_memory_promotion.discover_candidates()",
        "APPROVAL_RECEIPT",
        "extra_runtime_candidates",
        "missing_runtime_candidates",
    ]:
        require(needle in source, "inventory source missing required boundary text: " + needle)
    for forbidden in [
        "write_text(",
        "write_bytes(",
        "mkdir(",
        "unlink(",
        "rmtree(",
        "copyfile(",
        "move(",
        "write_receipt(",
        "APPROVE_PROMOTE_MEMORY_CANDIDATE",
        "APPROVE_FIX_CANDIDATE",
        "requests",
        "urllib",
        "socket",
        "subprocess",
    ]:
        require(forbidden not in source, "inventory source contains forbidden behavior: " + forbidden)


def check_cli() -> None:
    status = run_module("status")
    require(status.returncode == 0, "inventory status command failed: " + status.stderr)
    require("Engel Memory Candidate Inventory" in status.stdout, "status output missing title")
    require("report-only static inventory" in status.stdout, "status output missing report-only mode")
    require("NO_TRUSTED_MEMORY_WRITE" in status.stdout, "status output missing trusted-memory boundary")

    report = run_module("report")
    require(report.returncode == 0, "inventory report command failed: " + report.stderr)
    require("Candidate Paths:" in report.stdout, "report output missing candidate paths section")

    rendered = run_module("json")
    require(rendered.returncode == 0, "inventory json command failed: " + rendered.stderr)
    payload = json.loads(rendered.stdout)
    require(payload["schema"] == "engel_memory_candidate_inventory_v1", "unexpected inventory schema")
    require(payload["mode"] == "REPORT_ONLY_STATIC_INVENTORY", "inventory mode changed")
    require(payload["expected_memory_candidate_count"] == 24, "expected memory count should remain 24")
    require(payload["approved_receipt_memory_candidate_count"] == 24, "approved receipt memory count should remain 24")
    require(isinstance(payload["runtime_memory_candidate_count"], int), "runtime memory count missing")
    if payload["counts_match"]:
        require(payload["runtime_memory_candidate_count"] == 24, "matching count should be 24")
        require(payload["finding"] == "current_memory_candidate_count_matches_approved_receipt", "matching finding is wrong")
    else:
        require(
            payload["extra_runtime_candidates"] or payload["missing_runtime_candidates"],
            "mismatch must explain extra or missing candidates",
        )
    safety = payload["safety"]
    for key in [
        "memory_promotion_enabled",
        "trusted_memory_write_enabled",
        "approved_memory_write_enabled",
        "candidate_approval_enabled",
        "fix_apply_enabled",
        "source_mutation_enabled",
        "queue_route_mutation_enabled",
        "provider_calls_enabled",
        "model_runtime_enabled",
        "background_worker_enabled",
    ]:
        require(safety[key] is False, "unsafe inventory flag enabled: " + key)


def main() -> int:
    try:
        require(MODULE.exists(), "inventory module missing")
        check_source_static()
        check_cli()
    except CheckFailure as exc:
        print("[FAIL] " + str(exc))
        return 1
    print("[PASS] ENGEL memory candidate inventory verifier passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
