from __future__ import annotations

import argparse
import json
import socket
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from run_engel_lora_training_on_runpod import (
    download_artifacts,
    require_inputs,
    ssh_test,
    train_remote,
    upload_package,
    verify_artifacts,
    write_receipt,
)


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def tcp_probe(host: str, port: int, timeout_seconds: float) -> Path:
    started = time.perf_counter()
    payload: dict[str, Any] = {
        "ok": False,
        "schema": "engel_existing_runpod_ssh_tcp_preflight_v1",
        "checked_at_utc": iso_now(),
        "ssh_host": host,
        "ssh_port": port,
        "timeout_seconds": timeout_seconds,
    }
    try:
        with socket.create_connection((host, port), timeout=timeout_seconds):
            payload["ok"] = True
            payload["elapsed_seconds"] = round(time.perf_counter() - started, 3)
    except OSError as exc:
        payload["elapsed_seconds"] = round(time.perf_counter() - started, 3)
        payload["error"] = str(exc)
    receipt = write_receipt("RUNPOD_ENGEL_LORA_EXISTING_SSH_TCP_PREFLIGHT", payload)
    print(json.dumps(payload, indent=2, sort_keys=True), flush=True)
    print(f"receipt={receipt}", flush=True)
    if not payload["ok"]:
        raise RuntimeError(f"RunPod SSH TCP preflight failed. receipt={receipt}")
    return receipt


def compute_target_seconds(args: argparse.Namespace) -> int:
    if args.target_seconds and args.target_seconds > 0:
        return int(args.target_seconds)
    if args.budget_usd > 0 and args.cost_per_hr > 0:
        seconds = int((args.budget_usd / args.cost_per_hr * 3600.0) - args.stop_margin_seconds)
        return max(60, seconds)
    return 60


def run_existing_ssh(args: argparse.Namespace) -> int:
    require_inputs()
    receipts: dict[str, str] = {}
    started = time.perf_counter()

    target_seconds = compute_target_seconds(args)

    try:
        receipts["tcp_preflight"] = str(tcp_probe(args.ssh_host, args.ssh_port, args.tcp_timeout_seconds))
        receipts["ssh_test"] = str(ssh_test(args.ssh_host, args.ssh_port))
        if args.preflight_only:
            summary = {
                "ok": True,
                "schema": "engel_existing_runpod_ssh_preflight_only_v1",
                "finished_at_utc": iso_now(),
                "pod_label": args.pod_label,
                "ssh_host": args.ssh_host,
                "ssh_port": args.ssh_port,
                "elapsed_seconds": round(time.perf_counter() - started, 3),
                "stage_receipts": receipts,
                "training_started": False,
            }
            receipt = write_receipt("RUNPOD_ENGEL_LORA_EXISTING_SSH_PREFLIGHT_ONLY", summary)
            print(json.dumps(summary, indent=2, sort_keys=True), flush=True)
            print(f"receipt={receipt}", flush=True)
            return 0

        budget_plan: dict[str, Any] = {
            "ok": target_seconds > 0,
            "schema": "engel_existing_runpod_ssh_budget_plan_v1",
            "planned_at_utc": iso_now(),
            "pod_label": args.pod_label,
            "ssh_host": args.ssh_host,
            "ssh_port": args.ssh_port,
            "budget_usd": args.budget_usd,
            "cost_per_hr": args.cost_per_hr,
            "target_seconds": target_seconds,
            "max_steps": args.max_steps,
            "base_model": args.base_model,
            "preflight_passed": True,
            "api_key_used": False,
            "api_key_value_visible": False,
            "pod_stop_available": False,
            "pod_stop_note": "No RunPod API key was used; stop the manually-rented pod in the RunPod console after training.",
        }
        budget_receipt = write_receipt("RUNPOD_ENGEL_LORA_EXISTING_SSH_BUDGET_PLAN", budget_plan)
        receipts["budget_plan"] = str(budget_receipt)
        print(json.dumps(budget_plan, indent=2, sort_keys=True), flush=True)
        print(f"receipt={budget_receipt}", flush=True)

        receipts["upload"] = str(upload_package(args.ssh_host, args.ssh_port))
        receipts["training"] = str(
            train_remote(
                args.ssh_host,
                args.ssh_port,
                args.max_steps,
                args.max_length,
                args.base_model,
                args.lr,
                target_seconds,
                args.logging_steps,
            )
        )
        local_target, external_target, download_receipt = download_artifacts(args.ssh_host, args.ssh_port, args.pod_label)
        receipts["download"] = str(download_receipt)
        receipts["verify"] = str(verify_artifacts(local_target, external_target, args.pod_label, receipts))
        summary = {
            "ok": True,
            "schema": "engel_existing_runpod_ssh_training_summary_v1",
            "finished_at_utc": iso_now(),
            "pod_label": args.pod_label,
            "ssh_host": args.ssh_host,
            "ssh_port": args.ssh_port,
            "elapsed_seconds": round(time.perf_counter() - started, 3),
            "target_seconds": target_seconds,
            "stage_receipts": receipts,
            "api_key_used": False,
            "api_key_value_visible": False,
            "manual_stop_required": True,
        }
        receipt = write_receipt("RUNPOD_ENGEL_LORA_EXISTING_SSH_SUMMARY", summary)
        print(json.dumps(summary, indent=2, sort_keys=True), flush=True)
        print(f"receipt={receipt}", flush=True)
        return 0
    except Exception as exc:
        failure = {
            "ok": False,
            "schema": "engel_existing_runpod_ssh_training_failure_v1",
            "failed_at_utc": iso_now(),
            "pod_label": args.pod_label,
            "ssh_host": args.ssh_host,
            "ssh_port": args.ssh_port,
            "error": str(exc),
            "stage_receipts": receipts,
            "api_key_used": False,
            "api_key_value_visible": False,
            "manual_stop_required": True,
        }
        receipt = write_receipt("RUNPOD_ENGEL_LORA_EXISTING_SSH_FAILURE", failure)
        print(json.dumps(failure, indent=2, sort_keys=True), flush=True)
        print(f"receipt={receipt}", flush=True)
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Engel LoRA training on an already-rented RunPod SSH pod.")
    parser.add_argument("--ssh-host", required=True)
    parser.add_argument("--ssh-port", type=int, required=True)
    parser.add_argument("--pod-label", default="manual-runpod")
    parser.add_argument("--base-model", default="mistralai/Mistral-7B-Instruct-v0.3")
    parser.add_argument("--max-steps", type=int, default=100000)
    parser.add_argument("--max-length", type=int, default=768)
    parser.add_argument("--lr", type=float, default=2e-4)
    parser.add_argument("--target-seconds", type=int, default=0)
    parser.add_argument("--budget-usd", type=float, default=25.0)
    parser.add_argument("--cost-per-hr", type=float, default=0.0)
    parser.add_argument("--stop-margin-seconds", type=int, default=120)
    parser.add_argument("--logging-steps", type=int, default=25)
    parser.add_argument("--tcp-timeout-seconds", type=float, default=6.0)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    return run_existing_ssh(args)


if __name__ == "__main__":
    raise SystemExit(main())
