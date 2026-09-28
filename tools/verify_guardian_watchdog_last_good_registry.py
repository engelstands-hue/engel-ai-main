#!/usr/bin/env python3
"""
Verifier for ENGEL_GUARDIAN_WATCHDOG_LAST_GOOD_REGISTRY_V1.

This verifier checks the Guardian last-known-good registry by reading the
registry, recomputing current live EXE hashes, and comparing them to the
latest verified build/promote report. It does not restore, modify live EXEs,
modify backups, build, promote, start/stop Engel, stage, or commit.
"""

from __future__ import annotations

import hashlib
import json
import py_compile
import sys
from pathlib import Path
from typing import Any


_FILE = globals().get("__file__")
if not _FILE or not isinstance(_FILE, str) or _FILE.startswith("<"):
    ROOT = Path.cwd()
else:
    try:
        ROOT = Path(_FILE).resolve().parents[1]
    except (OSError, ValueError, IndexError):
        ROOT = Path.cwd()

REGISTRY_PATH = ROOT / "memory" / "ENGEL_GUARDIAN_LAST_KNOWN_GOOD_V1.json"
REPORTS_ROOT = ROOT / "reports" / "codex_bridge"
CONTRACT_VERIFIER = ROOT / "tools" / "verify_guardian_watchdog_contract.py"
SUCCESS_MARKER = "GUARDIAN_WATCHDOG_LAST_GOOD_REGISTRY_VERIFICATION_PASS"
CONTRACT_SUCCESS_MARKER = "GUARDIAN_WATCHDOG_CONTRACT_VERIFICATION_PASS"

REQUIRED_TOP_LEVEL_KEYS = [
    "record_id",
    "timestamp",
    "live_engel_exe_path",
    "live_engel_super_swarm_hive_3d_exe_path",
    "sha_256_hashes",
    "backup_path",
    "build_promote_report_path",
    "smoke_result",
    "verifier_result",
    "process_cleanup_result",
    "marked_good_by",
    "configuration_source",
    "current_hash_verified",
]

EXPECTED_LIVE_EXES = {
    "Engel.exe": "live\\app\\Engel.exe",
    "EngelSuperSwarmHive3D.exe": "live\\app\\EngelSuperSwarmHive3D.exe",
}


class CheckFailure(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def pass_line(label: str) -> None:
    print(f"PASS {label}")


def workspace_path(relative_path: str) -> Path:
    candidate = (ROOT / relative_path).resolve(strict=False)
    root = ROOT.resolve(strict=False)
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise CheckFailure(f"path escapes workspace: {relative_path}") from exc
    return candidate


def read_registry() -> dict[str, Any]:
    require(REGISTRY_PATH.exists(), f"missing registry: {REGISTRY_PATH}")
    with REGISTRY_PATH.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    require(isinstance(data, dict), "registry must be a JSON object")
    return data


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def find_latest_verified_build_promote_report() -> Path | None:
    if not REPORTS_ROOT.exists():
        return None
    candidates: list[Path] = []
    for path in REPORTS_ROOT.glob("*.md"):
        text = path.read_text(encoding="utf-8", errors="replace")
        if (
            "Build/promote is complete" in text
            and "Promotion result: PASS" in text
            and "Promoted live smoke result: PASS" in text
            and "ENGEL_CODEX_VERIFY_PASS" in text
        ):
            candidates.append(path)
    if not candidates:
        return None
    return max(candidates, key=lambda item: item.stat().st_mtime)


def check_registry_identity(data: dict[str, Any]) -> None:
    require(data.get("registry_id") == "ENGEL_GUARDIAN_LAST_KNOWN_GOOD_V1", "registry_id mismatch")
    require(data.get("status") == "registry_current_report_only", "registry status mismatch")
    require(data.get("active_workspace") == "D:\\b.WorkSpace\\Engel App", "active_workspace mismatch")
    missing = [key for key in REQUIRED_TOP_LEVEL_KEYS if key not in data]
    require(not missing, f"missing required registry keys: {missing}")
    require(data.get("record_id"), "record_id must be non-empty")
    require(data.get("timestamp"), "timestamp must be non-empty")
    require(data.get("configuration_source") == "existing_verified_build_promote_report", "configuration source mismatch")
    require(data.get("current_hash_verified") is True, "current_hash_verified must be true")
    pass_line("registry_identity_and_required_keys")


def check_latest_report_alignment(data: dict[str, Any]) -> str:
    report_rel = data.get("build_promote_report_path")
    require(isinstance(report_rel, str) and report_rel, "build_promote_report_path must be a string")
    report_path = workspace_path(report_rel)
    require(report_path.exists(), f"build/promote report missing: {report_path}")
    latest = find_latest_verified_build_promote_report()
    require(latest is not None, "no verified build/promote report with promotion and live smoke PASS was found")
    require(report_path.resolve(strict=False) == latest.resolve(strict=False), f"registry report is not latest verified build/promote report: {latest}")
    text = report_path.read_text(encoding="utf-8", errors="replace")
    require("Promotion result: PASS" in text, "build/promote report missing promotion PASS")
    require("Staged smoke result: PASS" in text, "build/promote report missing staged smoke PASS")
    require("Promoted live smoke result: PASS" in text, "build/promote report missing promoted live smoke PASS")
    require("Process Cleanup Result" in text and "PASS" in text, "build/promote report missing process cleanup PASS")
    require("ENGEL_CODEX_VERIFY_PASS" in text, "build/promote report missing full verifier PASS")
    pass_line("latest_verified_build_promote_report_alignment")
    return text


def check_live_hashes(data: dict[str, Any], report_text: str) -> None:
    hashes = data.get("sha_256_hashes")
    live_exes = data.get("live_exes")
    require(isinstance(hashes, dict), "sha_256_hashes must be an object")
    require(isinstance(live_exes, dict), "live_exes must be an object")
    for exe_name, expected_rel in EXPECTED_LIVE_EXES.items():
        record = live_exes.get(exe_name)
        require(isinstance(record, dict), f"missing live_exes record for {exe_name}")
        require(record.get("path") == expected_rel, f"{exe_name} registry path mismatch")
        live_path = workspace_path(expected_rel)
        require(live_path.exists(), f"live EXE missing: {live_path}")
        require(live_path.is_file(), f"live EXE path is not a file: {live_path}")
        computed_hash = sha256_file(live_path)
        recorded_hash = str(record.get("sha256", "")).upper()
        require(recorded_hash == computed_hash, f"{exe_name} hash mismatch: registry {recorded_hash}, current {computed_hash}")
        require(str(record.get("size_bytes")) == str(live_path.stat().st_size), f"{exe_name} size mismatch")
        require(computed_hash in report_text, f"{exe_name} current hash missing from build/promote report")
    require(hashes.get("live_engel_exe") == live_exes["Engel.exe"]["sha256"], "top-level Engel live hash mismatch")
    require(
        hashes.get("live_engel_super_swarm_hive_3d_exe") == live_exes["EngelSuperSwarmHive3D.exe"]["sha256"],
        "top-level Super Swarm live hash mismatch",
    )
    pass_line("current_live_hashes_verified")


def check_backup_records(data: dict[str, Any], report_text: str) -> None:
    backup_rel = data.get("backup_path")
    require(isinstance(backup_rel, str) and backup_rel, "backup_path must be a string")
    backup_root = workspace_path(backup_rel)
    require(backup_root.exists(), f"backup path missing: {backup_root}")
    require(backup_root.is_dir(), f"backup path must be a directory: {backup_root}")
    require(backup_rel in report_text, "backup path missing from build/promote report")
    live_exes = data["live_exes"]
    for exe_name, record in live_exes.items():
        backup_rel_path = record.get("backup_path")
        require(isinstance(backup_rel_path, str) and backup_rel_path, f"backup_path missing for {exe_name}")
        backup_path = workspace_path(backup_rel_path)
        require(backup_path.exists(), f"backup EXE missing: {backup_path}")
        require(backup_path.is_file(), f"backup EXE path is not a file: {backup_path}")
        computed_hash = sha256_file(backup_path)
        recorded_hash = str(record.get("backup_sha256", "")).upper()
        require(recorded_hash == computed_hash, f"{exe_name} backup hash mismatch")
        require(str(record.get("backup_size_bytes")) == str(backup_path.stat().st_size), f"{exe_name} backup size mismatch")
        require(computed_hash in report_text, f"{exe_name} backup hash missing from build/promote report")
    pass_line("backup_records_verified_read_only")


def check_results_and_safety(data: dict[str, Any]) -> None:
    smoke = data.get("smoke_result")
    verifier = data.get("verifier_result")
    safety = data.get("registry_safety")
    require(isinstance(smoke, dict), "smoke_result must be an object")
    require(smoke.get("staged_smoke") == "PASS", "staged smoke result must be PASS")
    require(smoke.get("promoted_live_smoke") == "PASS", "promoted live smoke result must be PASS")
    require(isinstance(verifier, dict), "verifier_result must be an object")
    require(verifier.get("pre_build_full_verifier") == "ENGEL_CODEX_VERIFY_PASS", "verifier result must be ENGEL_CODEX_VERIFY_PASS")
    require(data.get("process_cleanup_result") == "PASS", "process_cleanup_result must be PASS")
    require(data.get("marked_good_by"), "marked_good_by must be non-empty")
    require(isinstance(safety, dict), "registry_safety must be an object")
    unsafe = [key for key, value in safety.items() if value is not False]
    require(not unsafe, f"registry safety flags must be false: {unsafe}")
    pass_line("smoke_verifier_cleanup_and_safety_results")


def run_contract_verifier() -> None:
    require(CONTRACT_VERIFIER.exists(), f"missing contract verifier: {CONTRACT_VERIFIER}")
    import subprocess

    result = subprocess.run(
        [sys.executable, str(CONTRACT_VERIFIER)],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        check=False,
    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if result.stdout:
        for line in result.stdout.splitlines():
            print(f"INFO contract_verifier {line}")
    if result.stderr:
        for line in result.stderr.splitlines():
            print(f"INFO contract_verifier_stderr {line}")
    require(result.returncode == 0, "contract verifier failed")
    require(CONTRACT_SUCCESS_MARKER in result.stdout, "contract verifier success marker missing")
    pass_line("contract_verifier_passes")


def main() -> int:
    print("INFO Guardian Watchdog last-known-good registry verifier")
    print("INFO Mode: read-only registry/hash verification; no restore, build, promote, start, or stop")
    try:
        py_compile.compile(__file__, doraise=True)
        data = read_registry()
        check_registry_identity(data)
        report_text = check_latest_report_alignment(data)
        check_live_hashes(data, report_text)
        check_backup_records(data, report_text)
        check_results_and_safety(data)
        run_contract_verifier()
    except (CheckFailure, py_compile.PyCompileError, OSError, json.JSONDecodeError) as exc:
        print(f"FAIL {exc}")
        return 1
    print(SUCCESS_MARKER)
    return 0


if __name__ == "__main__":
    sys.exit(main())
