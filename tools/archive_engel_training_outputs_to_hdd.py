#!/usr/bin/env python3
"""Archive Engel training artifacts to the Dell PowerEdge HDD vault.

This is copy-first and non-destructive. Active training/runtime work stays on
the fast CT SSD under /mnt/ssd-ai/training. Historical outputs, logs, package
copies, and training receipts are copied to /mnt/engel-hdd-vault.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SSD_TRAINING_ROOT = Path("/mnt/ssd-ai/training")
HDD_VAULT_ROOT = Path("/mnt/engel-hdd-vault")
HDD_TRAINING_OUTPUTS = HDD_VAULT_ROOT / "training-outputs"
OFFLINE_CT245_VAULT = Path("/mnt/" + "engel-vault")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def is_forbidden_path(path: Path) -> bool:
    text = str(path).replace("\\", "/").lower()
    return text == str(OFFLINE_CT245_VAULT) or text.startswith(str(OFFLINE_CT245_VAULT) + "/")


def run_findmnt(path: Path) -> dict[str, str]:
    try:
        completed = subprocess.run(
            ["findmnt", "-T", str(path), "-no", "TARGET,SOURCE,FSTYPE"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except Exception as exc:
        return {"ok": "false", "error": str(exc)}
    line = (completed.stdout or "").strip().splitlines()
    fields = line[0].split(None, 2) if line else []
    return {
        "ok": "true" if completed.returncode == 0 and len(fields) >= 3 else "false",
        "target": fields[0] if len(fields) >= 1 else "",
        "source": fields[1] if len(fields) >= 2 else "",
        "fstype": fields[2] if len(fields) >= 3 else "",
        "stderr": (completed.stderr or "").strip(),
    }


def require_safe_paths(dest_root: Path, apply: bool) -> dict[str, Any]:
    if is_forbidden_path(dest_root):
        raise RuntimeError("refusing CT245 offline-vault path")
    if is_forbidden_path(SSD_TRAINING_ROOT):
        raise RuntimeError("refusing CT245 offline-vault path for SSD training root")
    mount = run_findmnt(HDD_VAULT_ROOT)
    result: dict[str, Any] = {
        "hdd_vault_root": str(HDD_VAULT_ROOT),
        "destination_root": str(dest_root),
        "ssd_training_root": str(SSD_TRAINING_ROOT),
        "findmnt": mount,
    }
    if apply:
        if mount.get("target") != str(HDD_VAULT_ROOT):
            raise RuntimeError(f"{HDD_VAULT_ROOT} is not a mounted target: {mount}")
        if mount.get("source") in {"", "/"}:
            raise RuntimeError(f"{HDD_VAULT_ROOT} is not backed by the Dell HDD vault: {mount}")
        try:
            dest_root.mkdir(parents=True, exist_ok=True)
            probe = dest_root / ".engel_archive_write_test"
            probe.write_text("ok\n", encoding="utf-8")
            probe.unlink(missing_ok=True)
        except PermissionError as exc:
            raise RuntimeError(
                f"{dest_root} is mounted but not writable from CT246. "
                "Fix host-side bind ownership/ACL for the unprivileged CT before archiving."
            ) from exc
    return result


def ensure_training_layout(apply: bool) -> list[str]:
    dirs = [
        SSD_TRAINING_ROOT / "packages",
        SSD_TRAINING_ROOT / "runs",
        SSD_TRAINING_ROOT / "logs",
        SSD_TRAINING_ROOT / "datasets",
        SSD_TRAINING_ROOT / "receipts",
        Path("/mnt/ssd-ai/cache/hf-cache"),
        HDD_TRAINING_OUTPUTS / "legacy-root",
        HDD_TRAINING_OUTPUTS / "reports",
        HDD_TRAINING_OUTPUTS / "memory",
        HDD_TRAINING_OUTPUTS / "receipts",
        HDD_VAULT_ROOT / "datasets-archive",
        HDD_VAULT_ROOT / "models-archive",
        HDD_VAULT_ROOT / "logs",
    ]
    if apply:
        for directory in dirs:
            if is_forbidden_path(directory):
                raise RuntimeError(f"refusing CT245 offline-vault path: {directory}")
            directory.mkdir(parents=True, exist_ok=True)
    return [str(directory) for directory in dirs]


def copy_file(source: Path, dest: Path, apply: bool) -> dict[str, Any]:
    record: dict[str, Any] = {"source": str(source), "destination": str(dest), "kind": "file"}
    if not source.exists():
        record["status"] = "missing"
        return record
    record["bytes"] = source.stat().st_size
    if apply:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
        record["status"] = "copied"
    else:
        record["status"] = "would_copy"
    return record


def copy_tree(source: Path, dest: Path, apply: bool) -> dict[str, Any]:
    record: dict[str, Any] = {"source": str(source), "destination": str(dest), "kind": "directory"}
    if not source.exists():
        record["status"] = "missing"
        return record
    total_files = 0
    total_bytes = 0
    for path in source.rglob("*"):
        if path.is_file():
            total_files += 1
            total_bytes += path.stat().st_size
    record["files"] = total_files
    record["bytes"] = total_bytes
    if apply:
        if is_forbidden_path(dest):
            raise RuntimeError(f"refusing CT245 offline-vault path: {dest}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, dest, dirs_exist_ok=True, copy_function=shutil.copy2)
        record["status"] = "copied"
    else:
        record["status"] = "would_copy"
    return record


def build_copy_plan(dest_root: Path) -> list[tuple[Path, Path, str]]:
    return [
        (Path("/mnt/ssd-ai/training/packages/engel-training-convo-20260701"), dest_root / "active-ssd" / "packages" / "engel-training-convo-20260701", "hdd_archive_active_ssd_training_package"),
        (Path("/mnt/ssd-ai/training/distributed/laptop-shared-730xd-training"), dest_root / "active-ssd" / "distributed" / "laptop-shared-730xd-training", "hdd_archive_laptop_shared_training_stage"),
        (Path("/mnt/ssd-ai/training/distributed/package"), dest_root / "active-ssd" / "distributed" / "package", "hdd_archive_distributed_package"),
        (Path("/mnt/ssd-ai/training/receipts"), dest_root / "active-ssd" / "receipts", "hdd_archive_active_ssd_receipts"),
        (Path("/root/engel-training-convo-20260701"), SSD_TRAINING_ROOT / "packages" / "engel-training-convo-20260701", "ssd_active_package"),
        (Path("/root/engel-training-convo-20260701"), dest_root / "legacy-root" / "engel-training-convo-20260701", "hdd_archive_legacy_package"),
        (Path("/root/engel-distributed-training"), SSD_TRAINING_ROOT / "distributed", "ssd_active_distributed_training"),
        (Path("/root/engel-distributed-training"), dest_root / "legacy-root" / "engel-distributed-training", "hdd_archive_distributed_training"),
        (Path("/opt/engel/reports/ai_local_open_chat_supervised_run"), dest_root / "reports" / "ai_local_open_chat_supervised_run", "hdd_archive_training_report"),
        (Path("/opt/engel/reports/storage_model_organization"), dest_root / "reports" / "storage_model_organization", "hdd_archive_storage_report"),
        (Path("/opt/engel/memory/discord_bridge"), dest_root / "memory" / "discord_bridge", "hdd_archive_discord_training_memory"),
        (Path("/opt/engel/runtime/engel_lora_training_package"), SSD_TRAINING_ROOT / "packages" / "engel_lora_training_package", "ssd_active_lora_package"),
        (Path("/opt/engel/runtime/engel_lora_training_package"), dest_root / "legacy-root" / "engel_lora_training_package", "hdd_archive_lora_package"),
    ]


def collect_root_globs(dest_root: Path, apply: bool) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for pattern in ["engel-lora*", "engel-*train*.log", "730xd-*train*.log", "730xd-launch.log"]:
        for source in sorted(Path("/root").glob(pattern)):
            dest = dest_root / "legacy-root" / "root-files" / source.name
            if source.is_dir():
                records.append(copy_tree(source, dest, apply))
            elif source.is_file():
                records.append(copy_file(source, dest, apply))
    return records


def archive(apply: bool, dest_root: Path) -> dict[str, Any]:
    safety = require_safe_paths(dest_root, apply)
    ensured = ensure_training_layout(apply)
    records: list[dict[str, Any]] = []
    for source, dest, category in build_copy_plan(dest_root):
        record = copy_tree(source, dest, apply) if source.is_dir() or not source.suffix else copy_file(source, dest, apply)
        record["category"] = category
        records.append(record)
    records.extend(collect_root_globs(dest_root, apply))

    copied = [record for record in records if record.get("status") == "copied"]
    planned = [record for record in records if record.get("status") == "would_copy"]
    missing = [record for record in records if record.get("status") == "missing"]
    total_bytes = sum(int(record.get("bytes", 0) or 0) for record in copied or planned)
    receipt = {
        "ok": True,
        "schema": "engel_training_storage_archive_v1",
        "mode": "apply" if apply else "dry-run",
        "created_at_utc": utc_now(),
        "host": os.uname().nodename if hasattr(os, "uname") else "",
        "safety": safety,
        "ensured_directories": ensured,
        "copy_records": records,
        "copied_count": len(copied),
        "planned_count": len(planned),
        "missing_count": len(missing),
        "total_bytes": total_bytes,
        "policy": {
            "active_training": str(SSD_TRAINING_ROOT),
            "archive_training_outputs": str(dest_root),
            "offline_ct245_vault_forbidden": str(OFFLINE_CT245_VAULT),
            "copy_first_no_delete": True,
        },
    }
    if apply:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        receipt_path = dest_root / "receipts" / f"engel_training_storage_archive_{stamp}.json"
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        latest_path = dest_root / "receipts" / "engel_training_storage_archive_latest.json"
        latest_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        receipt["receipt_path"] = str(receipt_path)
        latest_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Actually create directories and copy artifacts.")
    parser.add_argument("--dest-root", default=str(HDD_TRAINING_OUTPUTS))
    args = parser.parse_args(argv)
    dest_root = Path(args.dest_root)
    if is_forbidden_path(dest_root):
        raise SystemExit("refusing CT245 offline-vault path")
    receipt = archive(args.apply, dest_root)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if receipt.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
