#!/usr/bin/env python3
"""Verify the visible Flutter runner retries only evidence-free lost builds."""
from __future__ import annotations

from pathlib import Path
import json
import py_compile
import shutil
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def decision(module, **overrides) -> bool:
    values = {
        "build_prompt": True,
        "ui_submission_accepted": False,
        "submission_attempts": 1,
        "now": 60.0,
        "probe_deadline": 60.0,
        "ct_memory_ok": False,
        "wrapper_seen": False,
        "conical_seen": False,
    }
    values.update(overrides)
    return module._should_retry_lost_build_submission(**values)


def main() -> None:
    target = ROOT / "tools" / "run_engel_flutter_main_ui_prompt_training.py"
    py_compile.compile(str(target), doraise=True)
    source = target.read_text(encoding="utf-8")
    # (2026-07-31) The old prefix allowlist ('local'/'ct_local'/...) was replaced
    # by a cloud-marker DENY-list precisely because it mislabelled every new local
    # CT lane (ct_sparse_moe_specialist, ct_deep_local_specialist, math lanes) as
    # non-local. Assert the deny-list mechanism, not the retired literal.
    require(
        "_EXTERNAL_PROVIDER_MARKERS = (" in source
        and "marker in provider.casefold() for marker in _EXTERNAL_PROVIDER_MARKERS"
        in source,
        "visible UI local-only proof misclassifies CT246 local build models",
    )
    ui_route_source = (
        ROOT / "tools" / "run_engel_ui_chat_meeting_room_llm.py"
    ).read_text(encoding="utf-8")
    require(
        '"local_llm_only": server_receipt.get("local_llm_only") is True'
        in ui_route_source
        and '"selected_provider": server_receipt.get("selected_provider")'
        in ui_route_source,
        "ROG UI wrapper overwrites CT246 local-only build provenance",
    )
    from tools import run_engel_flutter_main_ui_prompt_training as module

    require(decision(module), "evidence-free lost build input should retry once")
    require(not decision(module, build_prompt=False), "normal chat must not use build retry")
    require(not decision(module, ui_submission_accepted=True), "accepted build must not duplicate")
    require(not decision(module, submission_attempts=2), "build retry must be bounded to one retry")
    require(not decision(module, now=59.9), "retry must wait for the probe deadline")
    require(not decision(module, ct_memory_ok=True), "CT memory evidence must suppress retry")
    require(not decision(module, wrapper_seen=True), "wrapper evidence must suppress retry")
    require(not decision(module, conical_seen=True), "conical receipt evidence must suppress retry")

    temp_root = ROOT / "runtime" / "temp" / "verify_flutter_conical_terminal"
    if temp_root.exists():
        shutil.rmtree(temp_root)
    conical_dir = temp_root / "conical_jobs"
    chat_dir = temp_root / "chat_receipts"
    conical_dir.mkdir(parents=True)
    old_conical_dir = module.CONICAL_REPORT_DIR
    old_chat_dir = module.CHAT_RECEIPT_DIR
    old_local_only_sentinel = module.LOCAL_ONLY_TRAINING_SENTINEL
    old_diagnostic_path = module.FLUTTER_CHAT_DIAGNOSTIC_PATH
    try:
        module.CONICAL_REPORT_DIR = conical_dir
        module.CHAT_RECEIPT_DIR = chat_dir
        module.LOCAL_ONLY_TRAINING_SENTINEL = temp_root / "local-only-active.json"
        module.FLUTTER_CHAT_DIAGNOSTIC_PATH = temp_root / "flutter-diagnostic.jsonl"
        module.FLUTTER_CHAT_DIAGNOSTIC_PATH.write_text(
            json.dumps({"event": "worker_result_received", "exit_code": 1}) + "\n",
            encoding="utf-8",
        )
        diagnostic_offset = module.FLUTTER_CHAT_DIAGNOSTIC_PATH.stat().st_size
        with module.FLUTTER_CHAT_DIAGNOSTIC_PATH.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps({"event": "worker_result_received", "exit_code": 0})
                + "\n"
            )
        fresh_result = module._wait_for_flutter_worker_result(
            diagnostic_offset,
            timeout=1,
        )
        require(
            fresh_result.get("ok") is True
            and (fresh_result.get("event") or {}).get("exit_code") == 0,
            "visible UI proof accepted a stale Flutter worker result",
        )
        # The readable active sentinel is never concurrency authority. Exercise the
        # production contract with a real kernel-released claim so this verifier cannot
        # accidentally normalize the retired, unsafe sentinel-only ownership path.
        claim_path = temp_root / "prompt-run.lock"
        with module.acquire_prompt_run_claim(
            claim_path, "verify-local-only-guard"
        ) as prompt_run_claim:
            guard = module._activate_local_only_guard(
                "verify-local-only-guard",
                time.time() + 600,
                prompt_run_claim=prompt_run_claim,
                scheduled_hours=1,
                requested_minutes=60.0,
                training_level="low",
                level_profile=module.training_level_profile("low"),
                trainings_per_hour=module.DEFAULT_TRAININGS_PER_HOUR,
                cadence_seconds=3600.0 / module.DEFAULT_TRAININGS_PER_HOUR,
            )
            guard_payload = json.loads(
                module.LOCAL_ONLY_TRAINING_SENTINEL.read_text(encoding="utf-8")
            )
            require(
                guard.get("owned") is True,
                "visible UI runner did not own its local-only guard",
            )
            require(
                guard_payload.get("status") == "RUNNING"
                and guard_payload.get("provider_policy") == "local_only"
                and (guard_payload.get("prompt_run_claim") or {}).get("run_id")
                == "verify-local-only-guard",
                "visible UI runner did not bind its local-only sentinel to the OS claim",
            )
            module._finish_local_only_guard(
                "verify-local-only-guard",
                "COMPLETED",
                prompt_run_claim=prompt_run_claim,
            )
            finished_guard = json.loads(
                module.LOCAL_ONLY_TRAINING_SENTINEL.read_text(encoding="utf-8")
            )
            require(
                finished_guard.get("status") == "COMPLETED"
                and finished_guard.get("expires_at_epoch") == 0,
                "visible UI runner left its local-only sentinel active",
            )
        require(
            not prompt_run_claim.held,
            "the verifier's prompt-run claim did not release with its owner process",
        )
        prompt = "Build a small web page that shows each phone worker by name and status."
        receipt_path = conical_dir / "conical_job_verify_terminal.json"
        receipt_path.write_text(
            json.dumps(
                {
                    "schema": "engel_conical_build_orchestration_v1",
                    "job_id": "conical_job_verify_terminal",
                    "prompt": prompt,
                    "started_at_utc": time.strftime(
                        "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
                    ),
                    "status": "failed_worker_returns",
                    "final_status": "failed",
                    "expected_worker_count": 4,
                    "returned_worker_count": 3,
                    "worker_results": [
                        {"worker_id": "android_worker_alpha", "returned": True},
                        {"worker_id": "android_worker_beta", "returned": True},
                        {"worker_id": "android_worker_gamma", "returned": True},
                        {"worker_id": "DESKTOP-UE5A6GG", "returned": False},
                    ],
                }
            )
            + "\n",
            encoding="utf-8",
        )
        match = module._matching_conical_receipt(prompt, time.time() - 5, set())
        require(match.get("ok") is True, "matching local conical receipt was not detected")
        require(match.get("terminal_failure") is True, "terminal conical failure was not detected")
        wrapper_path = module._write_conical_terminal_wrapper(match, prompt, "verify", 1)
        wrapper = json.loads(wrapper_path.read_text(encoding="utf-8"))
        require(wrapper.get("ok") is False, "synthetic terminal wrapper claimed success")
        require(wrapper.get("persistent_chat_memory_appended") is False, "local fallback claimed CT memory")
        require(wrapper.get("ct246_conical_persistence_ok") is False, "local fallback claimed CT proof")
        require(wrapper.get("conical_worker_returned_count") == 3, "worker count was lost")

        stale_path = conical_dir / "conical_job_stale_same_prompt.json"
        stale_path.write_text(
            json.dumps(
                {
                    "schema": "engel_conical_build_orchestration_v1",
                    "job_id": "conical_job_stale_same_prompt",
                    "prompt": prompt,
                    "started_at_utc": "2020-01-01T00:00:00Z",
                    "status": "failed_worker_returns",
                    "final_status": "failed",
                    "expected_worker_count": 4,
                    "returned_worker_count": 0,
                    "worker_results": [],
                }
            )
            + "\n",
            encoding="utf-8",
        )
        current_match = module._matching_conical_receipt(
            prompt, time.time() - 5, set()
        )
        require(
            current_match.get("path") == str(receipt_path),
            "a late-written prior submission replaced the current conical receipt",
        )

        complete_failure = dict(match)
        complete_failure["payload"] = {
            "schema": "engel_conical_build_orchestration_v1",
            "job_id": "conical_job_complete_workers_failed_build",
            "prompt": prompt,
            "status": "workers_returned",
            "final_status": "failed",
            "expected_worker_count": 4,
            "returned_worker_count": 4,
            "worker_results": [
                {"worker_id": worker_id, "returned": True}
                for worker_id in (
                    "android_worker_alpha",
                    "android_worker_beta",
                    "android_worker_gamma",
                    "DESKTOP-UE5A6GG",
                )
            ],
        }
        complete_wrapper_path = module._write_conical_terminal_wrapper(
            complete_failure, prompt, "verify-complete", 2
        )
        complete_wrapper = json.loads(
            complete_wrapper_path.read_text(encoding="utf-8")
        )
        complete_reply = str(complete_wrapper.get("assistant_reply") or "")
        require(
            "completed conical worker assembly at 4/4" in complete_reply,
            "post-worker build failure was reported as missing workers",
        )
        require(
            "Missing:" not in complete_reply,
            "4/4 worker completion still claimed a missing worker",
        )
    finally:
        module.CONICAL_REPORT_DIR = old_conical_dir
        module.CHAT_RECEIPT_DIR = old_chat_dir
        module.LOCAL_ONLY_TRAINING_SENTINEL = old_local_only_sentinel
        module.FLUTTER_CHAT_DIAGNOSTIC_PATH = old_diagnostic_path
        shutil.rmtree(temp_root, ignore_errors=True)
    print("ENGEL_FLUTTER_UI_SUBMISSION_RETRY_VERIFY_PASS")


if __name__ == "__main__":
    main()
