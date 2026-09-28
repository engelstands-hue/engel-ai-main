from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

from run_engel_lora_training_on_runpod import (  # noqa: E402
    KNOWN_HOSTS_PATH,
    SSH_KEY_PATH,
    infer_ssh_target,
    iso_now,
    redact_pod,
    runpod_request,
    status_pod,
    stop_pod,
    wait_for_ssh_target,
    write_json,
    write_receipt,
)


BACKUP_ROOT = ROOT / "runtime" / "runpod" / "full_storage_backups"
SSH_PUBLIC_KEY_PATH = Path("D:/pod/id_ed25519.pub")

SECRET_EXCLUDES = [
    "./.ssh",
    "./.ssh/*",
    "./*/.ssh",
    "./*/.ssh/*",
    "./.env",
    "./*/.env",
    "./id_rsa",
    "./id_rsa.pub",
    "./id_ed25519",
    "./id_ed25519.pub",
    "./*.pem",
    "./*.key",
    "./runpod_api_key.txt",
    "./secrets",
    "./secrets/*",
]


def ssh_base_safe(ip: str, port: int) -> list[str]:
    KNOWN_HOSTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    return [
        "ssh",
        "-i",
        str(SSH_KEY_PATH),
        "-p",
        str(port),
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        f"UserKnownHostsFile={KNOWN_HOSTS_PATH}",
        "-o",
        "ConnectTimeout=20",
        "-o",
        "ConnectionAttempts=1",
        "-o",
        "BatchMode=yes",
        "-o",
        "ServerAliveInterval=10",
        "-o",
        "ServerAliveCountMax=3",
        f"root@{ip}",
    ]


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def run_ssh_text(ip: str, port: int, command: str, *, timeout: int = 300) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ssh_base_safe(ip, port) + [command],
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def start_pod(pod_id: str) -> Path:
    before = status_pod(pod_id)
    response = runpod_request("POST", f"/pods/{pod_id}/start", {})
    payload = {
        "ok": True,
        "schema": "engel_runpod_storage_pod_start_v1",
        "started_at_utc": iso_now(),
        "pod_id": pod_id,
        "before": redact_pod(before),
        "response": redact_pod(response),
    }
    receipt = write_receipt("RUNPOD_ENGEL_STORAGE_POD_START", payload)
    print(json.dumps({k: payload[k] for k in ("ok", "schema", "pod_id", "started_at_utc")}, sort_keys=True), flush=True)
    print(f"receipt={receipt}", flush=True)
    return receipt


def ssh_auth_check(ip: str, port: int) -> None:
    result = run_ssh_text(ip, port, "echo ENGEL_STORAGE_SSH_OK && uname -a", timeout=60)
    if result.returncode != 0 or "ENGEL_STORAGE_SSH_OK" not in result.stdout:
        raise RuntimeError("SSH authentication check failed: " + result.stdout[-2000:])


def delete_pod(pod_id: str) -> Path:
    try:
        response = runpod_request("DELETE", f"/pods/{pod_id}")
        ok = True
        error = ""
    except Exception as exc:
        response = {}
        ok = False
        error = str(exc)
    payload = {
        "ok": ok,
        "schema": "engel_runpod_storage_temp_pod_delete_v1",
        "deleted_at_utc": iso_now(),
        "pod_id": pod_id,
        "response": redact_pod(response),
        "error": error,
    }
    receipt = write_receipt("RUNPOD_ENGEL_STORAGE_TEMP_POD_DELETE", payload)
    print(json.dumps({k: payload[k] for k in ("ok", "schema", "pod_id", "deleted_at_utc", "error")}, sort_keys=True), flush=True)
    print(f"receipt={receipt}", flush=True)
    return receipt


def make_backup_dir(label: str, pod_id: str) -> Path:
    safe_label = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in label).strip("_") or "runpod_storage"
    target = BACKUP_ROOT / f"{safe_label}_{pod_id}_{utc_stamp()}"
    target.mkdir(parents=True, exist_ok=False)
    return target


def remote_inventory(ip: str, port: int, root_path: str) -> dict[str, Any]:
    code = f"""
import json, os, stat, time
root = {root_path!r}
secret_names = {{'.env', 'id_rsa', 'id_rsa.pub', 'id_ed25519', 'id_ed25519.pub', 'runpod_api_key.txt'}}
secret_dirs = {{'.ssh', 'secrets'}}
secret_suffixes = ('.pem', '.key')
summary = {{
    'ok': os.path.exists(root),
    'root': root,
    'scanned_at_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
    'file_count': 0,
    'dir_count': 0,
    'symlink_count': 0,
    'total_file_bytes': 0,
    'sample_files': [],
    'excluded_secret_like_paths': [],
}}
def is_secret_like(rel):
    parts = rel.split(os.sep)
    name = parts[-1] if parts else rel
    return name in secret_names or name.endswith(secret_suffixes) or any(part in secret_dirs for part in parts)
if os.path.exists(root):
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        summary['dir_count'] += len(dirnames)
        for filename in filenames:
            path = os.path.join(dirpath, filename)
            rel = os.path.relpath(path, root)
            if is_secret_like(rel):
                if len(summary['excluded_secret_like_paths']) < 200:
                    summary['excluded_secret_like_paths'].append(rel)
                continue
            try:
                st = os.lstat(path)
            except OSError:
                continue
            if stat.S_ISLNK(st.st_mode):
                summary['symlink_count'] += 1
            else:
                summary['file_count'] += 1
                summary['total_file_bytes'] += int(st.st_size)
            if len(summary['sample_files']) < 200:
                summary['sample_files'].append({{'path': rel, 'bytes': int(st.st_size), 'mode': oct(st.st_mode)}})
print(json.dumps(summary, indent=2, sort_keys=True))
"""
    result = run_ssh_text(ip, port, "python3 - <<'PY'\n" + code + "\nPY", timeout=900)
    if result.returncode != 0:
        raise RuntimeError(result.stdout[-4000:])
    return json.loads(result.stdout)


def tar_command(root_path: str) -> str:
    exclude_args = " ".join(f"--exclude={item!r}" for item in SECRET_EXCLUDES)
    return f"test -d {root_path!r} && tar -C {root_path!r} {exclude_args} --warning=no-file-changed -cf - ."


def stream_tar(ip: str, port: int, root_path: str, target_tar: Path, *, timeout: int) -> dict[str, Any]:
    target_tmp = target_tar.with_suffix(target_tar.suffix + ".partial")
    if target_tmp.exists():
        target_tmp.unlink()
    started = time.perf_counter()
    with target_tmp.open("wb") as handle:
        result = subprocess.run(
            ssh_base_safe(ip, port) + [tar_command(root_path)],
            stdout=handle,
            stderr=subprocess.PIPE,
            timeout=timeout,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    stderr = result.stderr.decode("utf-8", errors="replace") if result.stderr else ""
    if result.returncode != 0:
        raise RuntimeError(f"tar stream failed rc={result.returncode}: {stderr[-4000:]}")
    target_tmp.replace(target_tar)
    digest = sha256_file(target_tar)
    sha_path = target_tar.with_suffix(target_tar.suffix + ".sha256")
    sha_path.write_text(f"{digest}  {target_tar.name}\n", encoding="utf-8")
    return {
        "ok": True,
        "archive_path": str(target_tar),
        "archive_sha256_path": str(sha_path),
        "archive_sha256": digest,
        "archive_bytes": target_tar.stat().st_size,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "stderr_tail": stderr[-4000:],
    }


def verify_tar_list(target_tar: Path) -> dict[str, Any]:
    result = subprocess.run(
        ["tar", "-tf", str(target_tar)],
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=1800,
    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    listing_path = target_tar.with_suffix(target_tar.suffix + ".listing.txt")
    listing_path.write_text(result.stdout, encoding="utf-8")
    return {
        "ok": result.returncode == 0,
        "listing_path": str(listing_path),
        "entry_count": len(lines),
        "listing_tail": result.stdout[-4000:],
    }


def recover_connected_pod(args: argparse.Namespace) -> int:
    pod_id = args.pod_id
    label = args.label or pod_id
    backup_dir = make_backup_dir(label, pod_id)
    receipts: dict[str, str] = {}
    started_at = time.perf_counter()
    cost_per_hr = 0.0
    start_state = status_pod(pod_id)
    try:
        cost_per_hr = float(start_state.get("costPerHr") or 0.0)
    except (TypeError, ValueError):
        cost_per_hr = 0.0
    ip = ""
    port = 0
    try:
        if str(start_state.get("desiredStatus") or "").upper() != "RUNNING":
            receipts["start"] = str(start_pod(pod_id))
        ip, port, ready_state, ready_receipt = wait_for_ssh_target(pod_id, args.ready_attempts, args.ready_delay)
        receipts["ready"] = str(ready_receipt)
        ssh_auth_check(ip, port)
        inventory = remote_inventory(ip, port, args.remote_root)
        inventory_path = backup_dir / "remote_inventory.json"
        write_json(inventory_path, inventory)
        if not inventory.get("ok"):
            raise RuntimeError(f"remote root not found: {args.remote_root}")
        if inventory.get("total_file_bytes", 0) > shutil.disk_usage(BACKUP_ROOT).free:
            raise RuntimeError("local F: backup target does not have enough free space for inventory byte count")
        archive = backup_dir / f"{label}_{pod_id}_workspace.tar"
        stream = stream_tar(ip, port, args.remote_root, archive, timeout=args.timeout)
        listing = verify_tar_list(archive)
        receipt_payload = {
            "ok": stream["ok"] and listing["ok"],
            "schema": "engel_runpod_full_storage_recovery_v1",
            "finished_at_utc": iso_now(),
            "pod_id": pod_id,
            "label": label,
            "remote_root": args.remote_root,
            "backup_dir": str(backup_dir),
            "inventory_path": str(inventory_path),
            "inventory": {k: inventory.get(k) for k in ("ok", "root", "file_count", "dir_count", "symlink_count", "total_file_bytes")},
            "stream": stream,
            "listing": listing,
            "cost_per_hr": cost_per_hr,
            "elapsed_seconds": round(time.perf_counter() - started_at, 3),
            "estimated_compute_spend_usd": round(cost_per_hr * (time.perf_counter() - started_at) / 3600.0, 4) if cost_per_hr else 0.0,
            "stage_receipts": receipts,
            "secret_like_paths_excluded_count": len(inventory.get("excluded_secret_like_paths") or []),
        }
        receipt = write_receipt("RUNPOD_ENGEL_FULL_STORAGE_RECOVERY", receipt_payload)
        print(json.dumps({k: receipt_payload[k] for k in ("ok", "pod_id", "label", "backup_dir", "estimated_compute_spend_usd")}, indent=2, sort_keys=True), flush=True)
        print(f"receipt={receipt}", flush=True)
        return 0 if receipt_payload["ok"] else 1
    except Exception as exc:
        failure = {
            "ok": False,
            "schema": "engel_runpod_full_storage_recovery_failure_v1",
            "failed_at_utc": iso_now(),
            "pod_id": pod_id,
            "label": label,
            "backup_dir": str(backup_dir),
            "ssh_ip_present": bool(ip),
            "ssh_port_present": bool(port),
            "error": str(exc),
            "stage_receipts": receipts,
        }
        receipt = write_receipt("RUNPOD_ENGEL_FULL_STORAGE_RECOVERY_FAILURE", failure)
        print(json.dumps(failure, indent=2, sort_keys=True), flush=True)
        print(f"receipt={receipt}", flush=True)
        return 1
    finally:
        if args.stop:
            receipts["stop"] = str(stop_pod(pod_id))
            summary = {
                "ok": True,
                "schema": "engel_runpod_full_storage_stop_summary_v1",
                "finished_at_utc": iso_now(),
                "pod_id": pod_id,
                "label": label,
                "cost_per_hr": cost_per_hr,
                "elapsed_seconds": round(time.perf_counter() - started_at, 3),
                "estimated_compute_spend_usd": round(cost_per_hr * (time.perf_counter() - started_at) / 3600.0, 4) if cost_per_hr else 0.0,
                "stage_receipts": receipts,
            }
            receipt = write_receipt("RUNPOD_ENGEL_FULL_STORAGE_STOP_SUMMARY", summary)
            print(json.dumps(summary, indent=2, sort_keys=True), flush=True)
            print(f"receipt={receipt}", flush=True)


def create_temp_cpu_pod_for_volume(network_volume_id: str, data_center_id: str, name: str) -> tuple[str, Path]:
    public_key = SSH_PUBLIC_KEY_PATH.read_text(encoding="utf-8").strip()
    payload = {
        "name": name,
        "cloudType": "SECURE",
        "computeType": "CPU",
        "cpuFlavorIds": ["cpu3c", "cpu3g", "cpu3m"],
        "cpuFlavorPriority": "availability",
        "dataCenterIds": [data_center_id],
        "dataCenterPriority": "custom",
        "imageName": "runpod/pytorch:2.1.0-py3.10-cuda11.8.0-devel-ubuntu22.04",
        "containerDiskInGb": 20,
        "networkVolumeId": network_volume_id,
        "volumeMountPath": "/workspace",
        "ports": ["22/tcp"],
        "supportPublicIp": True,
        "env": {
            "SSH_PUBLIC_KEY": public_key,
            "PUBLIC_KEY": public_key,
            "JUPYTER_PASSWORD": "engel-storage-recovery",
        },
    }
    response = runpod_request("POST", "/pods", payload)
    pod_id = str(response.get("id") or "")
    receipt_payload = {
        "ok": bool(pod_id),
        "schema": "engel_runpod_storage_temp_cpu_pod_create_v1",
        "created_at_utc": iso_now(),
        "pod_id": pod_id,
        "name": name,
        "network_volume_id": network_volume_id,
        "data_center_id": data_center_id,
        "response": redact_pod(response),
    }
    receipt = write_receipt("RUNPOD_ENGEL_STORAGE_TEMP_CPU_POD_CREATE", receipt_payload)
    print(json.dumps({k: receipt_payload[k] for k in ("ok", "pod_id", "name", "network_volume_id", "data_center_id")}, indent=2, sort_keys=True), flush=True)
    print(f"receipt={receipt}", flush=True)
    if not pod_id:
        raise RuntimeError(f"failed to create temporary CPU pod for network volume {network_volume_id}")
    return pod_id, receipt


def recover_network_volume(args: argparse.Namespace) -> int:
    name = args.label or f"engel-storage-recovery-{args.network_volume_id}-{utc_stamp()}"
    pod_id = ""
    create_receipt = ""
    try:
        pod_id, receipt = create_temp_cpu_pod_for_volume(args.network_volume_id, args.data_center_id, name)
        create_receipt = str(receipt)
        next_args = argparse.Namespace(
            pod_id=pod_id,
            label=name,
            remote_root="/workspace",
            ready_attempts=args.ready_attempts,
            ready_delay=args.ready_delay,
            timeout=args.timeout,
            stop=True,
        )
        rc = recover_connected_pod(next_args)
        if args.delete_temp_pod:
            delete_pod(pod_id)
        return rc
    except Exception as exc:
        payload = {
            "ok": False,
            "schema": "engel_runpod_network_volume_recovery_failure_v1",
            "failed_at_utc": iso_now(),
            "network_volume_id": args.network_volume_id,
            "data_center_id": args.data_center_id,
            "pod_id": pod_id,
            "create_receipt": create_receipt,
            "error": str(exc),
        }
        receipt = write_receipt("RUNPOD_ENGEL_NETWORK_VOLUME_RECOVERY_FAILURE", payload)
        print(json.dumps(payload, indent=2, sort_keys=True), flush=True)
        print(f"receipt={receipt}", flush=True)
        if pod_id:
            stop_pod(pod_id)
            if args.delete_temp_pod:
                delete_pod(pod_id)
        return 1


def inventory() -> int:
    pods_raw = runpod_request("GET", "/pods")
    pods = pods_raw if isinstance(pods_raw, list) else pods_raw.get("pods") or pods_raw.get("results") or pods_raw.get("data") or []
    volumes = runpod_request("GET", "/networkvolumes")
    payload = {
        "ok": True,
        "schema": "engel_runpod_storage_inventory_v1",
        "checked_at_utc": iso_now(),
        "pods": redact_pod(pods),
        "network_volumes": redact_pod(volumes),
    }
    receipt = write_receipt("RUNPOD_ENGEL_STORAGE_INVENTORY", payload)
    print(json.dumps(payload, indent=2, sort_keys=True), flush=True)
    print(f"receipt={receipt}", flush=True)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Recover paid RunPod storage into Engel local storage.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("inventory")

    pod = sub.add_parser("recover-pod")
    pod.add_argument("--pod-id", required=True)
    pod.add_argument("--label", default="")
    pod.add_argument("--remote-root", default="/workspace")
    pod.add_argument("--ready-attempts", type=int, default=90)
    pod.add_argument("--ready-delay", type=int, default=10)
    pod.add_argument("--timeout", type=int, default=7200)
    pod.add_argument("--stop", action=argparse.BooleanOptionalAction, default=True)

    volume = sub.add_parser("recover-network-volume")
    volume.add_argument("--network-volume-id", required=True)
    volume.add_argument("--data-center-id", required=True)
    volume.add_argument("--label", default="")
    volume.add_argument("--ready-attempts", type=int, default=90)
    volume.add_argument("--ready-delay", type=int, default=10)
    volume.add_argument("--timeout", type=int, default=7200)
    volume.add_argument("--delete-temp-pod", action=argparse.BooleanOptionalAction, default=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "inventory":
        return inventory()
    if args.command == "recover-pod":
        return recover_connected_pod(args)
    if args.command == "recover-network-volume":
        return recover_network_volume(args)
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
