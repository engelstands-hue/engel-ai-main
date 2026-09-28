#!/usr/bin/env python3
"""Fail-closed checks for exact prompt-pack consumption on both CT builders.

The remote builder receipt is an integrity boundary: transferring five hash-verified
packs is not enough if a stale or faulty builder silently reads only one of their rows.
These probes never contact CT.  They replace the SSH adapter with deterministic receipt
fixtures and require a 1-of-400 echo to fail while an exact 400-of-400 echo passes.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
for candidate in (ROOT, TOOLS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import run_engel_real_training_cycle as cycle  # noqa: E402


checks: list[tuple[str, bool, Any]] = []


def check(name: str, ok: bool, detail: Any) -> None:
    checks.append((name, bool(ok), detail))


def base_receipt() -> dict[str, Any]:
    return {
        "steps": [],
        "blockers": [],
        "warnings": [],
        "dataset": {},
        "slm": {},
        "construction_corpus": {
            "mode": "empty",
            "ct_root": "/opt/engel/run/exact-consumption/corpus",
            "bundle_sha256": "",
        },
    }


def builder_summary(target: str, rows_seen: int, explicit_rows: int) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "training_target": target,
        "prompt_training_target_filter": {
            "training_target": target,
            "rows_seen": rows_seen,
            "rows_explicitly_targeting": explicit_rows,
        },
        "construction_corpus_root": "/opt/engel/run/exact-consumption/corpus",
        "construction_corpus_verified": False,
        "construction_corpus_bundle_sha256": "",
    }
    if target == "llm":
        summary.update(
            {
                "raw_counts": {"prompt_training": 1},
                "train": 64,
                "val": 8,
                "dataset": "/opt/engel/datasets/fixture",
            }
        )
    else:
        summary["datasets"] = {
            "train_admit": {"rows": 2, "balance": {"admit": 1, "reject": 1}}
        }
    return summary


def run_sft_probe(rows_seen: int, explicit_rows: int) -> tuple[bool, dict[str, Any]]:
    receipt = base_receipt()
    summary = builder_summary("llm", rows_seen, explicit_rows)

    def fake_ssh(
        _cfg: dict[str, Any], remote_command: str, _timeout: float, **_kwargs: Any
    ) -> dict[str, Any]:
        payload = {} if remote_command.startswith("cat ") else summary
        return {
            "ok": True,
            "returncode": 0,
            "stdout": json.dumps(payload),
            "stderr": "",
        }

    original_ssh = cycle.ssh_run
    original_event = cycle.event
    try:
        cycle.ssh_run = fake_ssh
        cycle.event = lambda *_args, **_kwargs: None
        ok = cycle.step_build_dataset(
            receipt,
            {"target": "fixture"},
            "python3",
            1,
            "/opt/engel/run/exact-consumption/packs",
            expected_rows_seen=400,
            expected_explicit_rows=400,
        )
    finally:
        cycle.ssh_run = original_ssh
        cycle.event = original_event
    return ok, receipt


def run_slm_probe(rows_seen: int, explicit_rows: int) -> tuple[bool, dict[str, Any]]:
    receipt = base_receipt()
    summary = builder_summary("slm", rows_seen, explicit_rows)

    def fake_ssh(
        _cfg: dict[str, Any], _remote_command: str, _timeout: float, **_kwargs: Any
    ) -> dict[str, Any]:
        return {
            "ok": True,
            "returncode": 0,
            "stdout": json.dumps(summary),
            "stderr": "",
        }

    original_ssh = cycle.ssh_run
    original_event = cycle.event
    try:
        cycle.ssh_run = fake_ssh
        cycle.event = lambda *_args, **_kwargs: None
        ok = cycle.step_slm_datasets(
            receipt,
            {"target": "fixture"},
            "python3",
            "/opt/engel/run/exact-consumption/packs",
            "/opt/engel/run/exact-consumption/slm-dataset",
            1,
            expected_rows_seen=400,
            expected_explicit_rows=400,
        )
    finally:
        cycle.ssh_run = original_ssh
        cycle.event = original_event
    return ok, receipt


sft_partial_ok, sft_partial = run_sft_probe(1, 1)
check(
    "sft_one_of_400_is_refused",
    not sft_partial_ok
    and sft_partial["dataset"].get("exact_pack_consumption") is False
    and any("exact validated pack roster" in item for item in sft_partial["blockers"]),
    {"dataset": sft_partial["dataset"], "blockers": sft_partial["blockers"]},
)

sft_exact_ok, sft_exact = run_sft_probe(400, 400)
check(
    "sft_400_of_400_is_accepted",
    sft_exact_ok and sft_exact["dataset"].get("exact_pack_consumption") is True,
    sft_exact["dataset"],
)

slm_partial_ok, slm_partial = run_slm_probe(1, 1)
check(
    "slm_one_of_400_is_refused",
    not slm_partial_ok
    and slm_partial["slm"].get("exact_pack_consumption") is False
    and any("exact validated pack roster" in item for item in slm_partial["blockers"]),
    {"slm": slm_partial["slm"], "blockers": slm_partial["blockers"]},
)

slm_exact_ok, slm_exact = run_slm_probe(400, 400)
check(
    "slm_400_of_400_is_accepted",
    slm_exact_ok and slm_exact["slm"].get("exact_pack_consumption") is True,
    slm_exact["slm"],
)

for name, ok, detail in checks:
    print(f"{'PASS' if ok else 'FAIL'} {name}: {detail}")
passed = sum(1 for _, ok, _ in checks if ok)
print(f"SUMMARY {passed}/{len(checks)} checks passed")
raise SystemExit(0 if passed == len(checks) else 1)
