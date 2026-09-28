#!/usr/bin/env python3
"""Verify the Android worker fleet's capability layers agree.

Approved R.E.P.S. guardrail R20260704T172306436438Z (2026-07-04): three config
layers drift independently — the producer's WORKER_ALLOWED_TASK_TYPES, each
worker's config/worker_capabilities.json, and config/queen_choice_policy.json —
and the device map can silently leave a paired worker unroutable (gamma idled
through 4,445 assignments with zero warnings).

Checks, per worker in the producer registry:
  1. device map assigns a phone (adb_serial) to the worker
  2. worker_capabilities.json exists and its allowed_jobs ⊇ producer set
     (modulo return_* plumbing types, which the producer always allows)
  3. queen_choice_policy.json exists and its allowed_job_types ⊆ capabilities
  4. worker has >0 lifetime assignments in the returned/ history (WARN only —
     a brand-new worker legitimately starts at zero)

Exit 0 = parity OK (warnings allowed), 1 = drift found, 2 = cannot check.
Read-only; writes nothing. Run after any worker/capability change and from the
health check's fleet section.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRODUCER = ROOT / "engel_communication_queen_assignment_producer.py"
DEVICE_MAP = ROOT / "memory" / "ENGEL_PHONE_DEVICE_MAP_V1.json"
WORKERS_DIR = ROOT / "remote_workers"
RETURNED_DIR = WORKERS_DIR / "communication_queen_assignments" / "returned"

PLUMBING = {"return_status", "return_logs", "return_receipt"}


def load_producer_sets() -> dict[str, set[str]]:
    """Parse WORKER_ALLOWED_TASK_TYPES out of the producer without importing it
    (importing would pull the whole router)."""
    text = PRODUCER.read_text(encoding="utf-8-sig")
    match = re.search(
        r"WORKER_ALLOWED_TASK_TYPES\s*:\s*dict\[str,\s*set\[str\]\]\s*=\s*\{(.*?)\n\}",
        text,
        re.S,
    )
    if not match:
        raise RuntimeError("WORKER_ALLOWED_TASK_TYPES block not found in producer")
    block = match.group(1)
    sets: dict[str, set[str]] = {}
    for worker_match in re.finditer(r'"(android_worker_[a-z0-9_]+)"\s*:\s*\{(.*?)\}', block, re.S):
        worker = worker_match.group(1)
        types = set(re.findall(r'"([a-z0-9_]+)"', worker_match.group(2)))
        sets[worker] = types
    return sets


def main() -> int:
    problems: list[str] = []
    warnings: list[str] = []

    try:
        producer_sets = load_producer_sets()
    except (OSError, RuntimeError) as exc:
        print(f"CANNOT CHECK: {exc}")
        return 2

    try:
        device_map = json.loads(DEVICE_MAP.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"CANNOT CHECK: device map unreadable: {exc}")
        return 2
    assigned = {
        p.get("assigned_worker_id"): p.get("adb_serial")
        for p in device_map.get("phones", [])
        if isinstance(p, dict)
    }

    # lifetime assignment counts from returned packet filenames
    counts: dict[str, int] = {}
    if RETURNED_DIR.is_dir():
        for f in RETURNED_DIR.glob("*.json"):
            m = re.search(r"(android_worker_[a-z0-9]+)", f.name)
            if m:
                counts[m.group(1)] = counts.get(m.group(1), 0) + 1

    print(f"fleet parity check — {len(producer_sets)} workers in producer registry\n")
    for worker, producer_types in sorted(producer_sets.items()):
        tag = f"[{worker}]"
        serial = assigned.get(worker)
        if not serial:
            problems.append(f"{tag} not assigned to any phone in the device map")
        cfg_dir = WORKERS_DIR / worker / "config"
        caps_path = cfg_dir / "worker_capabilities.json"
        policy_path = cfg_dir / "queen_choice_policy.json"

        caps: set[str] = set()
        if caps_path.is_file():
            try:
                caps = set(json.loads(caps_path.read_text(encoding="utf-8-sig")).get("allowed_jobs", []))
            except (json.JSONDecodeError, OSError) as exc:
                problems.append(f"{tag} worker_capabilities.json unreadable: {exc}")
        else:
            problems.append(f"{tag} worker_capabilities.json missing")

        if caps:
            missing = (producer_types - PLUMBING) - caps
            if missing:
                problems.append(f"{tag} producer allows types absent from capabilities: {sorted(missing)}")

        if policy_path.is_file():
            try:
                policy_types = set(
                    json.loads(policy_path.read_text(encoding="utf-8-sig")).get("allowed_job_types", [])
                )
                orphaned = policy_types - caps - PLUMBING
                if caps and orphaned:
                    problems.append(f"{tag} queen policy allows types absent from capabilities: {sorted(orphaned)}")
            except (json.JSONDecodeError, OSError) as exc:
                problems.append(f"{tag} queen_choice_policy.json unreadable: {exc}")
        else:
            problems.append(f"{tag} queen_choice_policy.json missing")

        lifetime = counts.get(worker, 0)
        if serial and lifetime == 0:
            warnings.append(f"{tag} paired (serial {serial}) but ZERO lifetime returned assignments — verify routing")

        print(f"  {worker}: producer={len(producer_types)} types, capabilities={len(caps)}, "
              f"phone={'yes (' + str(serial) + ')' if serial else 'NO'}, lifetime_returns={lifetime}")

    print()
    for w in warnings:
        print(f"WARN  {w}")
    for p in problems:
        print(f"DRIFT {p}")
    verdict = "PARITY OK" if not problems else "DRIFT FOUND"
    print(f"\n{verdict}  (problems={len(problems)}, warnings={len(warnings)})")
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
