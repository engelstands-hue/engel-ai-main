#!/usr/bin/env python3
"""Run an Engel-owned local training-control job.

This is local Engel training control, not RunPod. It refreshes the current LoRA
training package, runs local safety/personality verifiers, records missing
dataset inputs as blockers, and writes receipts that Engel AI Main can use to
decide the next training step. It does not claim model-weight improvement unless
a separate adapter receipt verifies trained files.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
RUN_ROOT = ROOT / "runtime" / "training_runs"
MEMORY_DIR = ROOT / "memory" / "training"
TRAINING_MEMORY = MEMORY_DIR / "ENGEL_MAIN_LOCAL_TRAINING_MEMORY.jsonl"
LATEST_STATUS = MEMORY_DIR / "ENGEL_MAIN_LOCAL_TRAINING_LATEST_RUN.json"


def iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def parse_json_object(stdout: str) -> dict[str, Any]:
    text = str(stdout or "")
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return {}
    try:
        value = json.loads(text[start : end + 1])
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def run_step(name: str, command: list[str], timeout: int) -> dict[str, Any]:
    started = time.perf_counter()
    payload: dict[str, Any] = {
        "name": name,
        "command": command,
        "started_at_utc": iso_now(),
    }
    try:
        completed = subprocess.run(
            command,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        payload.update(
            {
                "ok": completed.returncode == 0,
                "returncode": completed.returncode,
                "stdout_tail": (completed.stdout or "")[-6000:],
                "stderr_tail": (completed.stderr or "")[-3000:],
                "parsed_json": parse_json_object(completed.stdout),
            }
        )
    except subprocess.TimeoutExpired:
        payload.update({"ok": False, "error": f"timed out after {timeout}s"})
    except Exception as exc:
        payload.update({"ok": False, "error": str(exc)})
    payload["duration_seconds"] = round(time.perf_counter() - started, 3)
    payload["finished_at_utc"] = iso_now()
    return payload


def dataset_source_present() -> bool:
    return (ROOT / "data" / "local_llm_training" / "engel_customer_conversation_seed_v1.jsonl").is_file()


def run_cycle(cycle: int) -> dict[str, Any]:
    steps: list[dict[str, Any]] = []
    py = sys.executable
    steps.append(run_step("build_lora_training_package", [py, str(TOOLS / "build_engel_lora_training_package.py")], 240))
    steps.append(run_step("verify_training_capture_filter", [py, str(TOOLS / "verify_engel_training_capture_filter.py")], 120))
    steps.append(run_step("verify_local_personality_training", [py, str(TOOLS / "verify_engel_local_personality_training.py")], 120))
    if dataset_source_present():
        steps.append(run_step("prepare_local_sft_dataset", [py, str(TOOLS / "prepare_local_llm_training_dataset.py")], 120))
        steps.append(run_step("verify_local_sft_training_prep", [py, str(TOOLS / "verify_local_llm_training_prep.py")], 120))
    else:
        steps.append(
            {
                "name": "prepare_local_sft_dataset",
                "ok": False,
                "skipped": True,
                "blocker": "missing data/local_llm_training/engel_customer_conversation_seed_v1.jsonl",
                "finished_at_utc": iso_now(),
            }
        )

    blockers: list[str] = []
    for step in steps:
        if step.get("ok") is not True:
            blockers.append(str(step.get("blocker") or step.get("error") or step.get("stderr_tail") or step.get("name")))
    package_step = steps[0] if steps else {}
    package_json = package_step.get("parsed_json") if isinstance(package_step.get("parsed_json"), dict) else {}
    return {
        "cycle": cycle,
        "started_at_utc": steps[0].get("started_at_utc") if steps else iso_now(),
        "finished_at_utc": iso_now(),
        "ok": not blockers,
        "steps": steps,
        "blockers": blockers,
        "training_package_zip": package_json.get("zip_path"),
        "training_package_rows": package_json.get("dataset_rows"),
        "adapter_weight_update_claimed": False,
    }


def run_job(args: argparse.Namespace) -> dict[str, Any]:
    run_id = args.run_id or "engel_local_training_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_dir = RUN_ROOT / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    target_seconds = max(1, int(args.target_seconds or 60))
    cycle_seconds = max(5, int(args.cycle_seconds or 60))
    started = time.perf_counter()
    status: dict[str, Any] = {
        "schema": "engel_local_training_job_status_v1",
        "run_id": run_id,
        "status": "RUNNING",
        "started_at_utc": iso_now(),
        "operator_prompt": args.operator_prompt,
        "target_seconds": target_seconds,
        "cycle_seconds": cycle_seconds,
        "runpod_used": False,
        "ct245_used": False,
        "offline_ct245_vault_used": False,
        "model_weight_update_claimed": False,
        "cycles": [],
        "blockers": [],
        "run_dir": str(run_dir),
    }
    write_json(LATEST_STATUS, status)
    append_jsonl(TRAINING_MEMORY, {"event": "local_training_started", **status})

    cycle = 0
    while True:
        cycle += 1
        cycle_result = run_cycle(cycle)
        status["cycles"].append(cycle_result)
        status["blockers"] = [item for result in status["cycles"] for item in result.get("blockers", [])]
        status["latest_cycle_finished_at_utc"] = iso_now()
        status["elapsed_seconds"] = round(time.perf_counter() - started, 3)
        write_json(run_dir / f"cycle_{cycle:03d}.json", cycle_result)
        write_json(LATEST_STATUS, status)
        append_jsonl(TRAINING_MEMORY, {"event": "local_training_cycle_finished", "run_id": run_id, "cycle": cycle, "result": cycle_result})
        if time.perf_counter() - started >= target_seconds:
            break
        sleep_for = min(cycle_seconds, max(0.0, target_seconds - (time.perf_counter() - started)))
        if sleep_for > 0:
            time.sleep(sleep_for)

    status["finished_at_utc"] = iso_now()
    status["elapsed_seconds"] = round(time.perf_counter() - started, 3)
    status["status"] = "PASS_WITH_BLOCKERS" if status["blockers"] else "PASS"
    status["summary_path"] = str(run_dir / "summary.json")
    status["training_memory"] = str(TRAINING_MEMORY)
    write_json(run_dir / "summary.json", status)
    write_json(LATEST_STATUS, status)
    append_jsonl(TRAINING_MEMORY, {"event": "local_training_finished", **status})
    return status


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--operator-prompt", default="")
    parser.add_argument("--target-seconds", type=int, default=60)
    parser.add_argument("--cycle-seconds", type=int, default=60)
    args = parser.parse_args()
    result = run_job(args)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("status") in {"PASS", "PASS_WITH_BLOCKERS"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
