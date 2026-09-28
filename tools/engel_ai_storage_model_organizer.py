#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
from datetime import datetime, timezone
from typing import Any


MODEL_EXTENSIONS = {".gguf", ".bin", ".safetensors", ".pt", ".ckpt"}
SCAN_ROOTS = [Path("/"), Path("/root"), Path("/mnt"), Path("/var"), Path("/home")]
ACTIVE_SSD_MOUNTPOINT = "/mnt/ssd-ai"
DELL_POWEREDGE_HDD_VAULT_MOUNTPOINT = "/mnt/engel-hdd-vault"
OFFLINE_CT245_VAULT_MOUNTPOINT = "/mnt/" + "engel-vault"
SKIP_DIR_NAMES = {
    ".git",
    "__pycache__",
    "proc",
    "sys",
    "dev",
    "run",
    "tmp",
    "lost+found",
    ".cache/pip",
}
SKIP_PREFIXES = (
    "/proc",
    "/sys",
    "/dev",
    "/run",
    "/tmp",
    "/var/tmp",
    "/var/cache/apt",
    "/var/lib/apt",
    "/var/log/journal",
)
TRAINING_MARKERS = (
    "shared-730xd-training",
    "engel-distributed-training",
    "training-output",
    "training_outputs",
    "training-outputs",
    "checkpoint",
    "checkpoints",
    "lora",
    "trainer",
    "runs",
    "wandb",
    "tensorboard",
)
ACTIVE_MARKERS = (
    "/models-active/",
    "/models/active/",
    "/runtime/ollama/",
    "/runtime/vllm/",
    "/runtime/openwebui/",
)
ARCHIVE_MARKERS = (
    "/models-archive/",
    "/old-models/",
    "/datasets-archive/",
    "/training-outputs/",
    "/archive/",
    "/backups/",
    "/snapshots/",
)


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def run_text(args: list[str]) -> str:
    try:
        return subprocess.check_output(args, text=True, stderr=subprocess.STDOUT, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).strip()
    except Exception as exc:
        return f"ERROR: {exc}"


def path_exists(path: Path) -> bool:
    try:
        return path.exists()
    except OSError:
        return False


def findmnt_target(path: Path) -> dict[str, str]:
    try:
        raw = subprocess.check_output(
            ["findmnt", "-J", "-T", str(path), "-o", "TARGET,SOURCE,FSTYPE,SIZE,USED,AVAIL"],
            text=True,
            stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        data = json.loads(raw)
        filesystems = data.get("filesystems") or []
        if filesystems and isinstance(filesystems[0], dict):
            return {k: str(v) for k, v in filesystems[0].items()}
    except Exception:
        pass
    return {}


def mount_state(path: Path) -> dict[str, Any]:
    info = findmnt_target(path)
    target = info.get("target", "")
    mounted_exact = target == str(path)
    return {
        "path": str(path),
        "exists": path_exists(path),
        "findmnt": info,
        "mounted_exact": mounted_exact,
        "safe_for_archive_writes": mounted_exact and str(path) == DELL_POWEREDGE_HDD_VAULT_MOUNTPOINT,
        "offline_ct245_vault_path": str(path) == OFFLINE_CT245_VAULT_MOUNTPOINT,
    }


def ensure_structure(ssd_root: Path, hdd_root: Path, *, apply: bool) -> dict[str, Any]:
    ssd_dirs = [
        "models/active",
        "models/quantized",
        "models/gguf",
        "models/transformers",
        "runtime/ollama",
        "runtime/vllm",
        "runtime/openwebui",
        "vector-db/chroma",
        "vector-db/faiss",
        "vector-db/qdrant",
        "cache/hf-cache",
        "cache/downloads",
        "datasets/working",
        "datasets/cleaned",
        "logs",
    ]
    hdd_dirs = [
        "models-archive",
        "datasets-archive",
        "training-outputs",
        "logs",
        "snapshots",
        "iso",
        "old-models",
    ]
    hdd_state = mount_state(hdd_root)
    created: list[str] = []
    skipped: list[dict[str, str]] = []
    if apply:
        for rel in ssd_dirs:
            target = ssd_root / rel
            target.mkdir(parents=True, exist_ok=True)
            created.append(str(target))
        if hdd_state["safe_for_archive_writes"]:
            for rel in hdd_dirs:
                target = hdd_root / rel
                target.mkdir(parents=True, exist_ok=True)
                created.append(str(target))
        else:
            for rel in hdd_dirs:
                skipped.append(
                    {
                        "path": str(hdd_root / rel),
                        "reason": (
                            "Dell PowerEdge engel-hdd-vault is not an exact mount; refusing to create "
                            "archive tree on SSD root or the CT245 offline-vault path"
                        ),
                    }
                )
    else:
        created = [str(ssd_root / rel) for rel in ssd_dirs]
        skipped = [{"path": str(hdd_root / rel), "reason": "dry-run"} for rel in hdd_dirs]
    return {
        "apply": apply,
        "ssd_root": str(ssd_root),
        "hdd_root": str(hdd_root),
        "hdd_state": hdd_state,
        "created_or_confirmed": created,
        "skipped": skipped,
    }


def should_skip_dir(path: Path) -> bool:
    sp = str(path)
    if any(sp == prefix or sp.startswith(prefix + "/") for prefix in SKIP_PREFIXES):
        return True
    name = path.name
    if name in SKIP_DIR_NAMES:
        return True
    return False


def iter_model_files() -> list[Path]:
    found: dict[str, Path] = {}
    for root in SCAN_ROOTS:
        if not root.exists():
            continue
        for dirpath, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
            current = Path(dirpath)
            dirnames[:] = [
                name for name in dirnames
                if not should_skip_dir(current / name)
            ]
            if should_skip_dir(current):
                dirnames[:] = []
                continue
            for filename in filenames:
                path = current / filename
                if path.suffix.lower() in MODEL_EXTENSIONS:
                    found.setdefault(str(path), path)
    return sorted(found.values(), key=lambda item: str(item))


def quick_fingerprint(path: Path, size: int) -> str:
    h = hashlib.sha256()
    h.update(str(path.name).encode("utf-8", errors="ignore"))
    h.update(str(size).encode("ascii"))
    try:
        with path.open("rb") as handle:
            first = handle.read(1024 * 1024)
            h.update(first)
            if size > 2 * 1024 * 1024:
                handle.seek(max(0, size - 1024 * 1024))
                h.update(handle.read(1024 * 1024))
    except Exception as exc:
        h.update(str(exc).encode("utf-8", errors="ignore"))
    return h.hexdigest()


def classify(path: Path, size: int) -> dict[str, Any]:
    sp = str(path)
    low = sp.lower()
    ext = path.suffix.lower()
    name = path.name.lower()
    quantized = ext == ".gguf" or any(token in name for token in ("q4", "q5", "q6", "q8", "gguf"))
    training_output = any(marker in low for marker in TRAINING_MARKERS)
    in_active = any(marker in low for marker in ACTIVE_MARKERS)
    in_archive = any(marker in low for marker in ARCHIVE_MARKERS)
    hf_cache = "/.cache/huggingface/" in low or "/huggingface/hub/" in low
    if in_active or (quantized and "/opt/engel/models-active/" in low):
        bucket = "ACTIVE"
        reason = "active runtime or quantized model under active model root"
        target_hint = "/mnt/ssd-ai/models/active" if ext != ".gguf" else "/mnt/ssd-ai/models/gguf"
    elif training_output:
        bucket = "ARCHIVE"
        reason = "training/checkpoint/output artifact"
        target_hint = f"{DELL_POWEREDGE_HDD_VAULT_MOUNTPOINT}/training-outputs"
    elif in_archive:
        bucket = "ARCHIVE"
        reason = "already in archive-style path"
        target_hint = f"{DELL_POWEREDGE_HDD_VAULT_MOUNTPOINT}/models-archive"
    elif hf_cache:
        bucket = "ARCHIVE"
        reason = "HuggingFace cache artifact; keep only if runtime needs it"
        target_hint = f"{ACTIVE_SSD_MOUNTPOINT}/cache/hf-cache or {DELL_POWEREDGE_HDD_VAULT_MOUNTPOINT}/models-archive"
    elif quantized:
        bucket = "ACTIVE_CANDIDATE"
        reason = "quantized inference-friendly model"
        target_hint = f"{ACTIVE_SSD_MOUNTPOINT}/models/gguf"
    elif ext in {".safetensors", ".ckpt", ".pt"}:
        bucket = "ARCHIVE_CANDIDATE"
        reason = "checkpoint/full-weight artifact; review before active SSD placement"
        target_hint = f"{DELL_POWEREDGE_HDD_VAULT_MOUNTPOINT}/models-archive"
    else:
        bucket = "REVIEW"
        reason = "model-like file needs manual classification"
        target_hint = ""
    return {
        "bucket": bucket,
        "reason": reason,
        "target_hint": target_hint,
        "quantized": quantized,
        "training_output": training_output,
        "hf_cache": hf_cache,
        "already_archive_path": in_archive,
        "already_active_path": in_active,
    }


def collect_inventory(*, hash_files: bool) -> list[dict[str, Any]]:
    inventory: list[dict[str, Any]] = []
    for path in iter_model_files():
        try:
            stat = path.stat()
            size = int(stat.st_size)
            item = {
                "path": str(path),
                "name": path.name,
                "extension": path.suffix.lower(),
                "size_bytes": size,
                "size_gib": round(size / (1024 ** 3), 4),
                "mtime_utc": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat().replace("+00:00", "Z"),
            }
            item.update(classify(path, size))
            if hash_files:
                item["quick_fingerprint_sha256"] = quick_fingerprint(path, size)
            inventory.append(item)
        except Exception as exc:
            inventory.append({"path": str(path), "error": str(exc)})
    return inventory


def duplicate_report(inventory: list[dict[str, Any]]) -> dict[str, Any]:
    by_name_size: dict[tuple[str, int], list[dict[str, Any]]] = {}
    by_size: dict[int, list[dict[str, Any]]] = {}
    by_family: dict[str, list[dict[str, Any]]] = {}
    by_fingerprint: dict[str, list[dict[str, Any]]] = {}
    for item in inventory:
        if "error" in item:
            continue
        name = str(item["name"]).lower()
        size = int(item["size_bytes"])
        by_name_size.setdefault((name, size), []).append(item)
        by_size.setdefault(size, []).append(item)
        fingerprint = item.get("quick_fingerprint_sha256")
        if fingerprint:
            by_fingerprint.setdefault(str(fingerprint), []).append(item)
        family = name
        for token in ("q2", "q3", "q4", "q5", "q6", "q8", "f16", "fp16", "bf16"):
            family = family.replace(token, "qX")
        family = family.replace(".gguf", "").replace(".safetensors", "").replace(".bin", "")
        by_family.setdefault(family, []).append(item)
    exact_candidates = [
        {"name": key[0], "size_bytes": key[1], "paths": [x["path"] for x in values]}
        for key, values in by_name_size.items()
        if len(values) > 1
    ]
    same_size_candidates = [
        {"size_bytes": size, "paths": [x["path"] for x in values]}
        for size, values in by_size.items()
        if len(values) > 1
    ]
    quantization_families = [
        {
            "family": family,
            "count": len(values),
            "total_gib": round(sum(int(x["size_bytes"]) for x in values) / (1024 ** 3), 4),
            "paths": [x["path"] for x in values],
        }
        for family, values in by_family.items()
        if len(values) > 1
    ]
    fingerprint_candidates = [
        {
            "quick_fingerprint_sha256": fingerprint,
            "count": len(values),
            "size_bytes_each": int(values[0]["size_bytes"]),
            "savings_bytes": sum(int(x["size_bytes"]) for x in values[1:]),
            "paths": [x["path"] for x in values],
        }
        for fingerprint, values in by_fingerprint.items()
        if len(values) > 1
    ]
    name_size_savings = sum(
        sum(Path(path).stat().st_size for path in group["paths"][1:] if Path(path).exists())
        for group in exact_candidates
    )
    fingerprint_savings = sum(int(group["savings_bytes"]) for group in fingerprint_candidates)
    return {
        "same_name_and_size_candidates": exact_candidates,
        "same_size_candidates": same_size_candidates[:200],
        "same_model_family_or_quantization_candidates": quantization_families[:200],
        "same_quick_fingerprint_candidates": fingerprint_candidates[:200],
        "safe_deletion_candidates_count": 0,
        "estimated_name_size_duplicate_savings_bytes": name_size_savings,
        "estimated_name_size_duplicate_savings_gib": round(name_size_savings / (1024 ** 3), 4),
        "estimated_quick_fingerprint_savings_bytes": fingerprint_savings,
        "estimated_quick_fingerprint_savings_gib": round(fingerprint_savings / (1024 ** 3), 4),
        "estimated_exact_duplicate_savings_bytes": name_size_savings,
        "estimated_exact_duplicate_savings_gib": round(name_size_savings / (1024 ** 3), 4),
        "deletion_policy": "No deletion is safe until duplicates are hash-confirmed and approved by Josh.",
    }


def summarize(inventory: list[dict[str, Any]]) -> dict[str, Any]:
    totals: dict[str, dict[str, Any]] = {}
    for item in inventory:
        bucket = str(item.get("bucket") or "ERROR")
        size = int(item.get("size_bytes") or 0)
        entry = totals.setdefault(bucket, {"count": 0, "bytes": 0, "gib": 0.0})
        entry["count"] += 1
        entry["bytes"] += size
        entry["gib"] = round(entry["bytes"] / (1024 ** 3), 4)
    return {
        "model_file_count": len(inventory),
        "total_bytes": sum(int(item.get("size_bytes") or 0) for item in inventory),
        "total_gib": round(sum(int(item.get("size_bytes") or 0) for item in inventory) / (1024 ** 3), 4),
        "by_bucket": totals,
    }


def write_reports(report_root: Path, payload: dict[str, Any]) -> dict[str, str]:
    report_root.mkdir(parents=True, exist_ok=True)
    tag = stamp()
    json_path = report_root / f"ENGEL_AI_STORAGE_MODEL_INVENTORY_{tag}.json"
    md_path = report_root / f"ENGEL_AI_STORAGE_MODEL_REPORT_{tag}.md"
    csv_path = report_root / f"ENGEL_AI_STORAGE_MODEL_INVENTORY_{tag}.csv"
    duplicate_md_path = report_root / f"ENGEL_AI_STORAGE_DUPLICATES_{tag}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    fieldnames = [
        "bucket",
        "size_gib",
        "size_bytes",
        "extension",
        "name",
        "path",
        "device",
        "mtime_utc",
        "classification_reason",
        "quick_fingerprint_sha256",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for item in payload["inventory"]:
            writer.writerow({key: item.get(key, "") for key in fieldnames})
    lines = [
        "# Engel AI Storage Model Organization Report",
        "",
        f"- generated: `{payload['generated_at_utc']}`",
        f"- host: `{payload['host']}`",
        f"- mode: `{'APPLY' if payload['apply'] else 'REPORT_ONLY'}`",
        f"- model files: `{payload['summary']['model_file_count']}`",
        f"- total model GiB: `{payload['summary']['total_gib']}`",
        "",
        "## Mount Safety",
        "",
        f"- `{payload['mounts']['ssd']['path']}`: `{payload['mounts']['ssd']['findmnt']}`",
        f"- `{payload['mounts']['hdd']['path']}`: `{payload['mounts']['hdd']['findmnt']}`",
        f"- CT245 offline-vault path `{OFFLINE_CT245_VAULT_MOUNTPOINT}` is not used for this report",
        f"- HDD archive writes safe: `{payload['mounts']['hdd']['safe_for_archive_writes']}`",
        "",
        "## Bucket Summary",
        "",
    ]
    for bucket, entry in sorted(payload["summary"]["by_bucket"].items()):
        lines.append(f"- `{bucket}`: {entry['count']} files, {entry['gib']} GiB")
    lines.extend(
        [
            "",
            "## Duplicate Candidates",
            "",
            f"- same name+size groups: `{len(payload['duplicates']['same_name_and_size_candidates'])}`",
            f"- same quick-fingerprint groups: `{len(payload['duplicates']['same_quick_fingerprint_candidates'])}`",
            f"- same family/quantization groups: `{len(payload['duplicates']['same_model_family_or_quantization_candidates'])}`",
            f"- estimated quick-fingerprint savings: `{payload['duplicates']['estimated_quick_fingerprint_savings_gib']} GiB`",
            f"- estimated name+size savings: `{payload['duplicates']['estimated_name_size_duplicate_savings_gib']} GiB`",
            "- deletions recommended now: `0`",
            "",
            "## Safe Next Actions",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in payload["safe_next_actions"])
    lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")

    duplicate_lines = [
        "# Engel AI Storage Duplicate Candidates",
        "",
        f"- generated: `{payload['generated_at_utc']}`",
        "- deletion recommendation: `0 files`",
        "- policy: hash-confirm and get Josh approval before deleting anything",
        "",
        "## Quick-Fingerprint Candidates",
        "",
    ]
    fingerprint_groups = sorted(
        payload["duplicates"]["same_quick_fingerprint_candidates"],
        key=lambda group: int(group.get("savings_bytes") or 0),
        reverse=True,
    )
    if fingerprint_groups:
        for group in fingerprint_groups[:100]:
            duplicate_lines.append(
                f"- `{round(int(group['savings_bytes']) / (1024 ** 3), 4)} GiB possible savings` "
                f"from {group['count']} files"
            )
            duplicate_lines.extend(f"  - `{path}`" for path in group["paths"])
    else:
        duplicate_lines.append("- No quick-fingerprint duplicate groups were computed. Run with `--hash-files`.")
    duplicate_lines.extend(["", "## Same Name + Size Candidates", ""])
    name_size_groups = sorted(
        payload["duplicates"]["same_name_and_size_candidates"],
        key=lambda group: int(group.get("size_bytes") or 0),
        reverse=True,
    )
    for group in name_size_groups[:100]:
        duplicate_lines.append(
            f"- `{group['name']}` `{round(int(group['size_bytes']) / (1024 ** 3), 4)} GiB each`"
        )
        duplicate_lines.extend(f"  - `{path}`" for path in group["paths"])
    duplicate_lines.extend(["", "## Same Model Family / Quantization Candidates", ""])
    family_groups = sorted(
        payload["duplicates"]["same_model_family_or_quantization_candidates"],
        key=lambda group: float(group.get("total_gib") or 0),
        reverse=True,
    )
    for group in family_groups[:100]:
        duplicate_lines.append(f"- `{group['family']}`: {group['count']} files, {group['total_gib']} GiB total")
        duplicate_lines.extend(f"  - `{path}`" for path in group["paths"])
    duplicate_lines.append("")
    duplicate_md_path.write_text("\n".join(duplicate_lines), encoding="utf-8")
    return {
        "json": str(json_path),
        "markdown": str(md_path),
        "inventory_csv": str(csv_path),
        "duplicates_markdown": str(duplicate_md_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="create safe SSD folders; HDD archive folders only if mounted exactly")
    parser.add_argument("--hash-files", action="store_true", help="compute quick first/last MiB fingerprints for inventory")
    parser.add_argument("--ssd-root", default=ACTIVE_SSD_MOUNTPOINT)
    parser.add_argument("--hdd-root", default=DELL_POWEREDGE_HDD_VAULT_MOUNTPOINT)
    parser.add_argument("--report-root", default="/opt/engel/reports/storage_model_organization")
    args = parser.parse_args()

    ssd_root = Path(args.ssd_root)
    hdd_root = Path(args.hdd_root)
    structure = ensure_structure(ssd_root, hdd_root, apply=args.apply)
    inventory = collect_inventory(hash_files=args.hash_files)
    payload = {
        "schema": "engel_ai_storage_model_organization_report_v1",
        "generated_at_utc": iso_now(),
        "host": run_text(["hostname"]),
        "apply": bool(args.apply),
        "rules": {
            "no_delete_performed": True,
            "no_model_move_performed": True,
            "no_zfs_or_block_device_change_performed": True,
            "hdd_archive_writes_require_exact_mount": True,
        },
        "mounts": {
            "ssd": mount_state(ssd_root),
            "hdd": mount_state(hdd_root),
            "root_df": run_text(["df", "-hT", "/"]),
            "opt_engel_df": run_text(["df", "-hT", "/opt/engel"]),
        },
        "structure": structure,
        "summary": summarize(inventory),
        "inventory": inventory,
        "duplicates": duplicate_report(inventory),
        "safe_next_actions": [
            f"Mount or bind the real SSD runtime path at {ACTIVE_SSD_MOUNTPOINT}, or approve using root SSD ext4 as {ACTIVE_SSD_MOUNTPOINT}.",
            f"Mount/bind the Dell PowerEdge engel-hdd-vault ZFS dataset at {DELL_POWEREDGE_HDD_VAULT_MOUNTPOINT} before any archive copy.",
            f"Do not use {OFFLINE_CT245_VAULT_MOUNTPOINT}; CT245 offline-vault storage is intentionally disabled.",
            "Hash-confirm duplicate candidates before deletion.",
            "Copy active runtime models to SSD first; do not run inference from HDD.",
            "Do not touch external training outputs unless their source path is mounted and inactive.",
        ],
    }
    paths = write_reports(Path(args.report_root), payload)
    result = {
        "ok": True,
        "schema": "engel_ai_storage_model_organizer_result_v1",
        "report_paths": paths,
        "summary": payload["summary"],
        "mounts": payload["mounts"],
        "duplicate_summary": {
            "same_name_size_groups": len(payload["duplicates"]["same_name_and_size_candidates"]),
            "same_quick_fingerprint_groups": len(payload["duplicates"]["same_quick_fingerprint_candidates"]),
            "same_family_groups": len(payload["duplicates"]["same_model_family_or_quantization_candidates"]),
            "estimated_quick_fingerprint_savings_gib": payload["duplicates"]["estimated_quick_fingerprint_savings_gib"],
            "estimated_name_size_duplicate_savings_gib": payload["duplicates"]["estimated_name_size_duplicate_savings_gib"],
            "estimated_exact_duplicate_savings_gib": payload["duplicates"]["estimated_exact_duplicate_savings_gib"],
        },
        "structure": structure,
        "rules": payload["rules"],
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
