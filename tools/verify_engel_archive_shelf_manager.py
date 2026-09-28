#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "engel_archive_shelf_manager.py"


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
        "STATUS_ONLY_OPTIONAL_ARCHIVE_SHELF_MANAGER",
        "build_memory_archive_snapshot()",
        "external_archive_required",
        "missing_external_archive_is_failure",
        "NO_I_DRIVE_REQUIRED",
        "NO_ARCHIVE_MIGRATION",
        "NO_ARCHIVE_COPY",
        "NO_ARCHIVE_SYNC",
        "NO_ARCHIVE_DELETE",
        "NO_TRUSTED_MEMORY_WRITE",
    ]:
        require(needle in source, "archive shelf source missing required boundary text: " + needle)
    for forbidden in [
        "write_text(",
        "write_bytes(",
        "mkdir(",
        "unlink(",
        "rmtree(",
        "copyfile(",
        "copytree(",
        "move(",
        "promote",
        "APPROVE_PROMOTE_MEMORY_CANDIDATE",
        "subprocess",
        "requests",
        "urllib",
        "socket",
    ]:
        require(forbidden not in source, "archive shelf source contains forbidden behavior: " + forbidden)


def check_cli() -> None:
    status = run_module("status")
    require(status.returncode == 0, "archive shelf status command failed: " + status.stderr)
    require("Engel Archive Shelf Manager" in status.stdout, "status output missing title")
    require("E:\\ENGEL_APP_MEMORY" in status.stdout, "E archive root missing")
    require("F:\\ENGEL_APP_MEMORY" in status.stdout, "F archive root missing")
    require("G:\\ENGEL_APP_MEMORY" in status.stdout, "G archive root missing")
    require("I:\\ENGEL_APP_MEMORY (not required)" in status.stdout, "I deprecated path boundary missing")
    require("NO_ARCHIVE_MIGRATION" in status.stdout, "status output missing migration boundary")

    report = run_module("report")
    require(report.returncode == 0, "archive shelf report command failed: " + report.stderr)
    require("# Engel Archive Shelf Manager" in report.stdout, "report output missing markdown title")

    rendered = run_module("json")
    require(rendered.returncode == 0, "archive shelf json command failed: " + rendered.stderr)
    payload = json.loads(rendered.stdout)
    require(payload["schema"] == "engel_archive_shelf_manager_v1", "unexpected archive shelf schema")
    require(payload["mode"] == "STATUS_ONLY_OPTIONAL_ARCHIVE_SHELF_MANAGER", "archive shelf mode changed")
    require(payload["external_archive_required"] is False, "external archive became required")
    require(payload["missing_external_archive_is_failure"] is False, "missing archive became failure")
    root_paths = [root["path"] for root in payload["configured_archive_roots"]]
    for expected in ["E:\\ENGEL_APP_MEMORY", "F:\\ENGEL_APP_MEMORY", "G:\\ENGEL_APP_MEMORY"]:
        require(expected in root_paths, "configured archive root missing: " + expected)
    require("I:\\ENGEL_APP_MEMORY" in payload["deprecated_paths"], "I path must remain deprecated only")
    safety = payload["safety"]
    for key in [
        "archive_migration_enabled",
        "archive_copy_enabled",
        "archive_sync_enabled",
        "archive_delete_enabled",
        "archive_create_enabled",
        "trusted_memory_write_enabled",
        "memory_promotion_enabled",
        "source_patch_apply_enabled",
        "queue_route_mutation_enabled",
        "provider_calls_enabled",
        "model_runtime_enabled",
        "background_worker_enabled",
    ]:
        require(safety[key] is False, "unsafe archive shelf flag enabled: " + key)


def main() -> int:
    try:
        require(MODULE.exists(), "archive shelf manager module missing")
        check_source_static()
        check_cli()
    except CheckFailure as exc:
        print("[FAIL] " + str(exc))
        return 1
    print("[PASS] ENGEL archive shelf manager verifier passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
