#!/usr/bin/env python3
"""Dependency-free regression checks for the staged SLM release lifecycle.

No SSH, training, model deserialization, or serving-process action occurs here.  The
checks exercise report/run binding and same-volume directory promotion with tiny inert
files, including the post-swap rollback path.
"""
from __future__ import annotations

import hashlib
import io
import json
import shutil
import sys
import tempfile
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
for candidate in (str(ROOT), str(TOOLS)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

import run_engel_real_training_cycle as cycle  # noqa: E402


checks: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str) -> None:
    checks.append((name, bool(ok), detail))
    print(("PASS " if ok else "FAIL ") + name + f" :: {detail}")


def digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def report_fixture(
    run_id: str,
    candidate_dir: str,
    dataset_dir: str,
    tasks: list[str],
    payloads: dict[str, bytes],
) -> dict[str, Any]:
    results = []
    for task in tasks:
        name = f"engel_slm_{task}.joblib"
        results.append(
            {
                "task": task,
                "ok": True,
                "candidate_ok": True,
                "selected_ok": True,
                "selected_head": "candidate",
                "artifact": f"{candidate_dir}/{name}",
                "artifact_sha256": digest(payloads[name]),
            }
        )
    return {
        "schema": cycle.slm_roster.TRAINING_REPORT_SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "output_dir": candidate_dir,
        "data_dir": dataset_dir,
        "incumbent_dir": cycle.CT_SLM_DIR,
        "staged": True,
        "requested_tasks": tasks,
        "results": results,
        "selected_ok": tasks,
        "trained_ok": tasks,
    }


run_id = cycle.unique_cycle_run_id()
candidate_dir = cycle.ct_slm_candidate_dir(run_id)
dataset_dir = cycle.ct_slm_dataset_dir(run_id)
tasks = ["intent_router", "style_checks"]
payloads = {
    "engel_slm_intent_router.joblib": b"inert-intent-artifact",
    "engel_slm_style_checks.joblib": b"inert-style-artifact",
}
report = report_fixture(run_id, candidate_dir, dataset_dir, tasks, payloads)
started = (datetime.now(timezone.utc) - timedelta(seconds=2)).isoformat()
problems, selected, artifacts = cycle.validate_slm_training_report(
    report,
    run_id=run_id,
    candidate_dir=candidate_dir,
    dataset_dir=dataset_dir,
    requested_tasks=tasks,
    cycle_started_at_utc=started,
)
check(
    "fresh_report_binds_to_exact_cycle_and_full_roster",
    not problems and selected == tasks and len(artifacts) == len(tasks),
    f"problems={problems}; selected={selected}; artifacts={sorted(artifacts)}",
)

wrong_run = dict(report, run_id="realtrain_wrong")
wrong_problems, _, _ = cycle.validate_slm_training_report(
    wrong_run,
    run_id=run_id,
    candidate_dir=candidate_dir,
    dataset_dir=dataset_dir,
    requested_tasks=tasks,
    cycle_started_at_utc=started,
)
check(
    "wrong_run_report_is_rejected",
    any("run_id" in problem for problem in wrong_problems),
    str(wrong_problems),
)

partial = dict(report, selected_ok=[tasks[0]], trained_ok=[tasks[0]])
partial_problems, _, _ = cycle.validate_slm_training_report(
    partial,
    run_id=run_id,
    candidate_dir=candidate_dir,
    dataset_dir=dataset_dir,
    requested_tasks=tasks,
    cycle_started_at_utc=started,
)
check(
    "partial_roster_is_not_a_release",
    any("every requested task" in problem for problem in partial_problems),
    str(partial_problems),
)

escaped = json.loads(json.dumps(report))
escaped["results"][0]["artifact"] = f"{cycle.CT_SLM_DIR}/engel_slm_intent_router.joblib"
escaped_problems, _, _ = cycle.validate_slm_training_report(
    escaped,
    run_id=run_id,
    candidate_dir=candidate_dir,
    dataset_dir=dataset_dir,
    requested_tasks=tasks,
    cycle_started_at_utc=started,
)
check(
    "serving_directory_artifact_is_rejected",
    any("not canonical" in problem for problem in escaped_problems),
    str(escaped_problems),
)

work = Path(
    tempfile.mkdtemp(prefix="engel_slm_promotion_verify_", dir=str(ROOT / "runtime" / "temp"))
)
try:
    live = work / "slm_models"
    stage = work / "slm_models_candidate_release_a"
    live.mkdir()
    (live / "old.txt").write_bytes(b"previous-release")
    stage.mkdir()
    release_payloads = {
        "LATEST_TRAINING.json": json.dumps(report, sort_keys=True).encode("utf-8"),
        **payloads,
    }
    for name, payload in release_payloads.items():
        (stage / name).write_bytes(payload)
    expected = {name: digest(payload) for name, payload in release_payloads.items()}
    promoted = cycle.atomic_promote_slm_release(
        stage, live, run_id="release_a", expected_hashes=expected
    )
    backup = Path(str(promoted.get("backup") or ""))
    check(
        "verified_release_promotes_by_directory_swap",
        promoted.get("ok") is True
        and not stage.exists()
        and not cycle.verify_local_slm_release(live, expected),
        str(promoted),
    )
    check(
        "promotion_preserves_unique_previous_release",
        backup.is_dir() and (backup / "old.txt").read_bytes() == b"previous-release",
        str(backup),
    )

    live_b = work / "slm_models_b"
    stage_b = work / "slm_models_b_candidate"
    live_b.mkdir()
    (live_b / "sentinel.txt").write_bytes(b"must-stay")
    stage_b.mkdir()
    (stage_b / "artifact.joblib").write_bytes(b"tampered")
    rejected = cycle.atomic_promote_slm_release(
        stage_b,
        live_b,
        run_id="release_b",
        expected_hashes={"artifact.joblib": digest(b"expected")},
    )
    check(
        "bad_stage_never_mutates_live_release",
        rejected.get("ok") is False
        and (live_b / "sentinel.txt").read_bytes() == b"must-stay",
        str(rejected),
    )

    live_c = work / "slm_models_c"
    stage_c = work / "slm_models_c_candidate"
    live_c.mkdir()
    (live_c / "sentinel.txt").write_bytes(b"rollback-target")
    stage_c.mkdir()
    (stage_c / "artifact.joblib").write_bytes(b"valid")
    expected_c = {"artifact.joblib": digest(b"valid")}
    original_verify = cycle.verify_local_slm_release
    calls = {"count": 0}

    def fail_after_swap(directory: Path, expected_hashes: dict[str, str]) -> list[str]:
        calls["count"] += 1
        if calls["count"] == 2:
            return ["forced post-swap integrity failure"]
        return original_verify(directory, expected_hashes)

    cycle.verify_local_slm_release = fail_after_swap
    try:
        rolled_back = cycle.atomic_promote_slm_release(
            stage_c,
            live_c,
            run_id="release_c",
            expected_hashes=expected_c,
        )
    finally:
        cycle.verify_local_slm_release = original_verify
    check(
        "post_swap_failure_restores_previous_release",
        rolled_back.get("ok") is False
        and rolled_back.get("rolled_back") is True
        and (live_c / "sentinel.txt").read_bytes() == b"rollback-target",
        str(rolled_back),
    )
finally:
    shutil.rmtree(work, ignore_errors=True)

source = Path(cycle.__file__).read_text(encoding="utf-8")
check(
    "cycle_trains_only_into_run_specific_stage",
    '"--out-dir",\n        candidate_dir' in source
    and '"--incumbent-dir",\n        CT_SLM_DIR' in source
    and '"--run-id",\n        run_id' in source,
    "trainer command binds stage, read-only incumbent, and run id",
)
other_run_id = cycle.unique_cycle_run_id()
check(
    "concurrent_cycles_cannot_share_slm_dataset_input",
    other_run_id != run_id
    and cycle.ct_slm_dataset_dir(other_run_id) != dataset_dir
    and '"--data-dir",\n        dataset_dir' in source
    and '"--out",\n        dataset_dir' in source,
    f"first={dataset_dir}; second={cycle.ct_slm_dataset_dir(other_run_id)}",
)
check(
    "candidate_verifier_never_defaults_to_serving_directory",
    'ENGEL_SLM_MODEL_DIR={candidate_dir}' in source,
    "CT verifier is explicitly pointed at the staged candidate",
)

reload_receipt: dict[str, Any] = {
    "steps": [],
    "blockers": [],
    "slm": {"release_report_sha256": "a" * 64},
}
reload_ok = cycle.step_slm_reload_pending(reload_receipt)
check(
    "filesystem_swap_never_claims_serving_activation",
    reload_ok is False
    and reload_receipt["slm"].get("reload_required") is True
    and reload_receipt["slm"].get("reload_acknowledged") is False
    and bool(reload_receipt["blockers"]),
    str(reload_receipt),
)
check(
    "cycle_does_not_measure_old_memory_as_new_release",
    source.count("step_capability_gate(receipt") == 1
    and "the serving process has not acknowledged" in source,
    "capability measurement waits for an authenticated in-process reload",
)

lock_path = ROOT / "runtime" / "temp" / "engel_slm_lifecycle_verify.lock"
original_lock_path = cycle.CYCLE_LOCK_PATH
original_run_cycle = cycle.run_cycle
original_argv = sys.argv[:]
try:
    with cycle.exclusive_cycle_lock(lock_path):
        second_failed = False
        try:
            with cycle.exclusive_cycle_lock(lock_path):
                pass
        except cycle.CycleLockBusy:
            second_failed = True
        cycle.CYCLE_LOCK_PATH = lock_path
        run_calls = {"count": 0}

        def should_not_run(_: Any) -> dict[str, Any]:
            run_calls["count"] += 1
            raise AssertionError("run_cycle reached while the exclusive lock was busy")

        cycle.run_cycle = should_not_run
        sys.argv = ["verify-cycle-lock", "--no-ct"]
        with redirect_stdout(io.StringIO()):
            busy_exit = cycle.main()
    # The byte remains, but a released OS lock is immediately reusable. This proves
    # existence is not interpreted as a stale/busy state.
    with cycle.exclusive_cycle_lock(lock_path):
        reacquired = True
    check(
        "exclusive_cycle_lock_blocks_overlap_and_has_no_stale_state",
        second_failed
        and busy_exit == 1
        and run_calls["count"] == 0
        and reacquired
        and lock_path.is_file(),
        f"second_failed={second_failed}; busy_exit={busy_exit}; "
        f"run_calls={run_calls['count']}; reacquired={reacquired}; path={lock_path}",
    )
finally:
    cycle.CYCLE_LOCK_PATH = original_lock_path
    cycle.run_cycle = original_run_cycle
    sys.argv = original_argv
    try:
        lock_path.unlink()
    except OSError:
        pass

failed = [name for name, ok, _ in checks if not ok]
print(f"\n{len(checks) - len(failed)}/{len(checks)} checks passed")
print("verify_engel_slm_promotion_lifecycle: " + ("GREEN" if not failed else "RED"))
raise SystemExit(0 if not failed else 1)
