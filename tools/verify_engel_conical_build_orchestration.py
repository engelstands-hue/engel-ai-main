#!/usr/bin/env python3
from __future__ import annotations

import contextlib
import json
import inspect
import os
from pathlib import Path
import shutil
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
for value in (str(ROOT), str(TOOLS)):
    if value not in sys.path:
        sys.path.insert(0, value)

import engel_build_lane as build_lane
import engel_main_local_model_worker as local_worker
import engel_main_server_chat_http_service as server_service
import run_engel_ui_chat_meeting_room_llm as ui_lane


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    prompt = "Build me a medium multi-file Python maintenance planner app with tests"
    plan = ui_lane._conical_job_plan(prompt, "verify_conical_job")
    tasks = plan.get("tasks") if isinstance(plan.get("tasks"), list) else []
    workers = [str(task.get("worker_id") or "") for task in tasks]
    require(plan.get("required") is True, "medium build must require conical orchestration")
    require(
        workers == [
            "android_worker_alpha",
            "android_worker_beta",
            "android_worker_gamma",
            "DESKTOP-UE5A6GG",
        ],
        f"worker split mismatch: {workers}",
    )
    require(
        [str(task.get("task_type") or "") for task in tasks[:3]]
        == [
            "conical_requirements_analysis",
            "conical_verification_plan",
            "conical_dependency_risk_check",
        ],
        "phone workers are not assigned distinct conical analysis types",
    )
    for expected_size in ("medium", "large", "expert"):
        level_plan = ui_lane._conical_job_plan(
            f"Build me an {expected_size} multi-file Python app with automated tests",
            f"verify_{expected_size}_conical_job",
        )
        require(
            level_plan.get("build_size") == expected_size,
            f"{expected_size} build did not enter conical orchestration",
        )
        require(
            len(level_plan.get("tasks") or []) == 4,
            f"{expected_size} build did not require all four workers",
        )
    require(not ui_lane._conical_job_plan("How are you today?", "not_a_job"), "normal chat must not dispatch build workers")
    all_device_build = (
        "This is a large job. Build me a Python dashboard with tests. "
        "Split the review across all three phones and Sub-Engel."
    )
    require(
        ui_lane._conical_build_profile(all_device_build).get("build_size") == "large",
        "all-device large build did not classify as conical",
    )
    require(
        ui_lane._prompt_requests_device_work(all_device_build),
        "all-device large build did not exercise the device-dispatch overlap",
    )
    original_fleet_dispatch = local_worker._run_fleet_dispatch
    original_server_chat = local_worker._main_server_fast_chat
    original_progress_heartbeat = local_worker._request_progress_heartbeat
    fleet_called = False
    build_heartbeat_wrapped = False

    def forbidden_fleet_dispatch(*_args, **_kwargs):
        nonlocal fleet_called
        fleet_called = True
        raise AssertionError("fleet dispatcher preempted a conical build")

    @contextlib.contextmanager
    def observed_progress_heartbeat(
        request_id: str,
        *,
        enabled: bool,
        interval_seconds: float = 15.0,
    ):
        nonlocal build_heartbeat_wrapped
        del interval_seconds
        build_heartbeat_wrapped = request_id == "verify-build-before-fleet" and enabled
        yield

    try:
        local_worker._run_fleet_dispatch = forbidden_fleet_dispatch
        local_worker._request_progress_heartbeat = observed_progress_heartbeat
        local_worker._main_server_fast_chat = lambda **_kwargs: {
            "ok": True,
            "status": "fixture CT246 build route",
            "assistant_reply": "fixture build receipt",
        }
        routed_build = local_worker._handle(
            {
                "id": "verify-build-before-fleet",
                "command": "chat",
                "prompt": all_device_build,
                "timeout": 60,
                "max_tokens": 500,
            }
        )
    finally:
        local_worker._run_fleet_dispatch = original_fleet_dispatch
        local_worker._main_server_fast_chat = original_server_chat
        local_worker._request_progress_heartbeat = original_progress_heartbeat
    require(not fleet_called, "explicit device wording preempted a real build")
    require(
        build_heartbeat_wrapped,
        "Flutter watchdog heartbeat does not wrap the complete conical build action",
    )
    require(
        routed_build.get("status") == "fixture CT246 build route",
        f"build did not reach CT246 before fleet dispatch: {routed_build}",
    )
    run_source = inspect.getsource(ui_lane.run)
    require(
        "if not conical_build_requested and (" in run_source,
        "ordinary device dispatch can still preempt a conical build",
    )
    worker_handle_source = inspect.getsource(local_worker._handle)
    # Order is the contract: the build check must gate the fleet-dispatch call, so
    # build text never becomes a device-only dispatch. Match the call by NAME, not
    # by its argument list -- the argument was deliberately narrowed to
    # `operator_prompt` so capability/training wrappers stop tripping dispatch, and
    # pinning the old literal turned this gate red for a correct change.
    build_guard_index = worker_handle_source.find(
        "if _requested_app_build(operator_prompt) is None:"
    )
    fleet_dispatch_index = worker_handle_source.find("_run_fleet_dispatch(")
    require(
        build_guard_index != -1,
        "persistent Flutter worker lost the build guard in front of fleet dispatch",
    )
    require(
        fleet_dispatch_index != -1,
        "persistent Flutter worker no longer calls fleet dispatch from _handle",
    )
    require(
        build_guard_index < fleet_dispatch_index,
        "persistent Flutter worker can still route build text into fleet-only dispatch",
    )
    status_build_prompt = (
        "Build a small web page that shows each phone worker by name, model, and current status."
    )
    require(
        local_worker._server_prompt_override_for_truth_route(status_build_prompt)
        == status_build_prompt,
        "phone-status truth routing rewrote a real build request",
    )
    require(
        local_worker._server_prompt_override_for_truth_route("Which workers are live?")
        == "phone status",
        "short worker-status truth routing regressed",
    )

    temp_root = ROOT / "runtime" / "temp" / "verify_conical_orchestration"
    if temp_root.exists():
        shutil.rmtree(temp_root)
    temp_root.mkdir(parents=True)
    try:
        schemas = {
            "conical_requirements_analysis": {
                "schema": "engel_android_conical_requirements_v1",
                "role": "requirements_analyst",
                "functional_requirements": ["Show every worker return."],
                "acceptance_criteria": ["Visible worker proof."],
            },
            "conical_verification_plan": {
                "schema": "engel_android_conical_verification_v1",
                "role": "verification_planner",
                "test_matrix": [{"check": "startup", "proof": "HTTP 200"}],
                "terminal_success_rule": "All required checks pass.",
            },
            "conical_dependency_risk_check": {
                "schema": "engel_android_conical_dependency_risk_v1",
                "role": "dependency_and_risk_checker",
                "dependencies": ["Python"],
                "risks": ["Malformed JSON"],
                "deterministic_checks": ["Run fixture twice."],
            },
        }
        phone_results = []
        for phone_task in tasks[:3]:
            worker_id = str(phone_task.get("worker_id") or "")
            task_type = str(phone_task.get("task_type") or "")
            packet_id = "packet_verify_" + worker_id
            assignment = {
                "packet_id": packet_id,
                "worker_id": worker_id,
                "dispatched_epoch": time.time() - 1,
            }
            return_path = temp_root / f"{worker_id}_return.json"
            return_path.write_text("{}\n", encoding="utf-8")
            draft = {
                **schemas[task_type],
                "request_summary": "Build a maintenance planner.",
                "analysis_engine": "on_device_deterministic_conical_v1",
                "status": "candidate_only",
                "human_review_required": True,
                "capability_snapshot": {"must_not_reach_build_context": True},
            }
            valid_return = {
                "path": str(return_path),
                "payload": {
                    "packet_id": packet_id,
                    "worker_id": worker_id,
                    "draft_text": json.dumps(draft),
                    "result_type": f"{task_type}_draft_result",
                    "trusted_memory_write": False,
                    "safe_to_auto_apply": False,
                },
            }
            valid = ui_lane._conical_phone_result(
                phone_task, assignment, valid_return
            )
            require(
                valid.get("returned") is True,
                f"matching role-specific phone return rejected: {valid}",
            )
            require(
                valid.get("analysis_engine")
                == "on_device_deterministic_conical_v1",
                "phone analysis engine proof was lost",
            )
            require(
                "capability_snapshot" not in str(valid.get("contribution") or ""),
                "capability snapshot leaked into build context",
            )
            phone_results.append(valid)

        mismatch = json.loads(json.dumps(valid_return))
        mismatch["payload"]["packet_id"] = "stale_other_packet"
        rejected = ui_lane._conical_phone_result(phone_task, assignment, mismatch)
        require(rejected.get("status") == "failed_invalid_return", "mismatched packet must be rejected")
        assignment_echo = json.loads(json.dumps(valid_return))
        assignment_echo["payload"]["draft_text"] = (
            "UNTRUSTED candidate. User request copied without analysis."
        )
        echo_rejected = ui_lane._conical_phone_result(
            phone_task, assignment, assignment_echo
        )
        require(
            echo_rejected.get("status") == "failed_invalid_role_analysis",
            "assignment echo was accepted as conical analysis",
        )
        compact_context = ui_lane._conical_build_context(phone_results)
        require(
            "on_device_deterministic_conical_v1" in compact_context,
            "validated phone analysis did not enter compact build context",
        )
        require(
            "capability_snapshot" not in compact_context,
            "capability snapshot contaminated compact build context",
        )

        sub_task = tasks[-1]
        valid_sub = ui_lane._conical_sub_result(
            sub_task,
            {
                "returned": True,
                "work_order": {"id": "order_verify"},
                "return_result": {
                    "path": "sub.done.json",
                    "payload": {"order_id": "order_verify", "worker_output": "Architecture review."},
                },
            },
        )
        require(valid_sub.get("returned") is True, f"matching Sub return rejected: {valid_sub}")
        invalid_sub = ui_lane._conical_sub_result(
            sub_task,
            {
                "returned": True,
                "work_order": {"id": "order_verify"},
                "return_result": {"payload": {"order_id": "other_order"}},
            },
        )
        require(invalid_sub.get("returned") is False, "mismatched Sub order must be rejected")
        truthful_sub_failure = ui_lane._conical_sub_result(
            sub_task,
            {
                "returned": False,
                "work_order": {"id": "order_verify"},
                "dispatch_transport": "ct246_in_process_authenticated_action",
                "errors": [
                    {
                        "stage": "ct246_direct_work",
                        "error": "authenticated Sub model process exceeded its bounded timeout",
                    }
                ],
            },
        )
        require(
            truthful_sub_failure.get("error")
            == "authenticated Sub model process exceeded its bounded timeout",
            f"Sub failure detail was flattened: {truthful_sub_failure}",
        )
        require(
            truthful_sub_failure.get("dispatch_transport")
            == "ct246_in_process_authenticated_action",
            "Sub dispatch transport proof was lost",
        )
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)

    server_temp = ROOT / "runtime" / "temp" / "verify_ct246_conical_persistence"
    if server_temp.exists():
        shutil.rmtree(server_temp)
    server_temp.mkdir(parents=True)
    old_conical_dir = server_service.CONICAL_REPORT_DIR
    old_chat_dir = server_service.CHAT_RECEIPT_DIR
    old_memory_path = server_service.PERSISTENT_CHAT_MEMORY_PATH
    old_run_build = build_lane.run_build
    run_build_called = False

    def forbidden_run_build(*_args, **_kwargs):
        nonlocal run_build_called
        run_build_called = True
        raise AssertionError("generation ran despite a failed four-worker gate")

    try:
        server_service.CONICAL_REPORT_DIR = server_temp / "conical_jobs"
        server_service.CHAT_RECEIPT_DIR = server_temp / "chat_receipts"
        server_service.PERSISTENT_CHAT_MEMORY_PATH = server_temp / "memory" / "chat.jsonl"
        build_lane.run_build = forbidden_run_build
        failed_conical = {
            "schema": "engel_conical_build_orchestration_v1",
            "required": True,
            "ok": False,
            "status": "failed_worker_returns",
            "job_id": "verify_failed_conical_job",
            "expected_worker_count": 4,
            "returned_worker_count": 3,
            "plan": {"tasks": tasks},
            "worker_results": [
                {
                    "worker_id": worker,
                    "task_id": f"task_{index}",
                    "returned": index < 3,
                    "status": "returned" if index < 3 else "failed_no_valid_return",
                    "error": "" if index < 3 else "bounded wait ended",
                    "contribution": "candidate proof" if index < 3 else "",
                }
                for index, worker in enumerate(workers)
            ],
            "receipt_path": r"D:\b.WorkSpace\Engel App\reports\conical_jobs\controller.json",
        }
        failure_receipt = server_service._build_lane_receipt(
            prompt,
            time.perf_counter(),
            {"source": "engel_ai_main_ui", "conical_orchestration": failed_conical},
        )
        require(isinstance(failure_receipt, dict), "failed worker gate fell through to ordinary chat")
        require(not run_build_called, "failed worker gate invoked the generator")
        require(failure_receipt.get("conical_terminal_failure") is True, "terminal failure was not explicit")
        require(failure_receipt.get("build_verified") is False, "failed worker gate claimed a build")
        require(failure_receipt.get("build_artifact_created") is False, "failed worker gate claimed an artifact")
        require(failure_receipt.get("ct246_conical_persistence_ok") is True, "CT246 failure proof was not durable")
        failed_proof_path = Path(str(failure_receipt.get("ct246_conical_receipt_path") or ""))
        require(failed_proof_path.is_file(), "CT246 conical failure receipt is missing")
        failed_proof = json.loads(failed_proof_path.read_text(encoding="utf-8"))
        require(failed_proof.get("final_status") == "failed", "failure proof status is not failed")
        require(
            failed_proof.get("missing_worker_ids") == ["DESKTOP-UE5A6GG"],
            f"failure proof missing-worker list is wrong: {failed_proof.get('missing_worker_ids')}",
        )
        require(
            str(failed_proof.get("receipt_path") or "").startswith(str(server_temp)),
            "CT receipt retained the Windows controller path as authoritative",
        )
        require(
            failed_proof.get("controller_receipt_path")
            == r"D:\b.WorkSpace\Engel App\reports\conical_jobs\controller.json",
            "controller receipt provenance was lost",
        )
        memory_rows = [
            json.loads(line)
            for line in server_service.PERSISTENT_CHAT_MEMORY_PATH.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        require(
            any(row.get("schema") == "engel_ct246_conical_job_memory_v1" for row in memory_rows),
            "CT246 conical memory row is missing",
        )

        complete_conical = json.loads(json.dumps(failed_conical))
        complete_conical["job_id"] = "verify_finished_conical_job"
        complete_conical["ok"] = True
        complete_conical["status"] = "workers_returned"
        complete_conical["returned_worker_count"] = 4
        for row in complete_conical["worker_results"]:
            row["returned"] = True
            row["status"] = "returned"
            row["error"] = ""
            row["contribution"] = "candidate proof"
        success_proof = server_service._persist_ct246_conical_receipt(
            complete_conical,
            prompt=prompt,
            source="verifier",
            build_execution_verified=True,
            provider_api_used=False,
        )
        require(success_proof.get("ok") is True, f"successful conical proof did not persist: {success_proof}")
        success_payload = json.loads(Path(success_proof["receipt_path"]).read_text(encoding="utf-8"))
        require(success_payload.get("final_status") == "finished", "successful proof did not finish")
        require(success_payload.get("build_verified") is True, "successful proof lost build verification")
    finally:
        build_lane.run_build = old_run_build
        server_service.CONICAL_REPORT_DIR = old_conical_dir
        server_service.CHAT_RECEIPT_DIR = old_chat_dir
        server_service.PERSISTENT_CHAT_MEMORY_PATH = old_memory_path
        shutil.rmtree(server_temp, ignore_errors=True)

    conical = {
        "schema": "engel_conical_build_orchestration_v1",
        "required": True,
        "ok": True,
        "job_id": "verify_conical_job",
        "expected_worker_count": 4,
        "returned_worker_count": 4,
        "build_context": "WORKER: alpha\nCANDIDATE CONTRIBUTION:\nrequirements",
    }
    receipt = build_lane._receipt(
        "verify",
        True,
        "verified",
        "python",
        {"ok": True, "path": "/opt/engel/workspaces/verify"},
        {"ran": True, "exit_code": 0},
        conical_orchestration=conical,
        artifact_verified=True,
    )
    require(receipt.get("conical_job_required") is True, "build receipt must preserve conical requirement")
    require(receipt.get("conical_workers_ok") is True, "build receipt must preserve worker success")

    long_review = build_lane._files_for_review(
        {"app.js": "const head = true;\n" + ("x" * 5000) + "\nwindow.ActionLogBoard = api;\n"},
        limit=2000,
    )
    require("const head = true" in long_review, "long-file review lost the file head")
    require("window.ActionLogBoard = api" in long_review, "long-file review lost the file tail")
    require(
        "middle clipped for review; real file continues" in long_review,
        "long-file review does not identify middle-only clipping",
    )

    ui_source = (TOOLS / "run_engel_ui_chat_meeting_room_llm.py").read_text(encoding="utf-8")
    worker_source = (TOOLS / "engel_main_local_model_worker.py").read_text(encoding="utf-8")
    build_source = (TOOLS / "engel_build_lane.py").read_text(encoding="utf-8")
    service_source = (TOOLS / "engel_main_server_chat_http_service.py").read_text(encoding="utf-8")
    meeting_source = (TOOLS / "engel_meeting_room_lan_server.py").read_text(encoding="utf-8")
    visible_runner_source = (TOOLS / "run_engel_flutter_main_ui_prompt_training.py").read_text(encoding="utf-8")
    require("_run_conical_build_orchestration(prompt)" in ui_source, "UI lane does not run conical orchestration")
    require(
        '"SUB_ENGEL_WORK_ORDERS"' in ui_source
        and "write_json(work_order_path, work_order)" in ui_source
        and '"work_order_path": str(work_order_path)' in ui_source,
        "ROG projection does not retain the exact CT246 Sub-Engel claim",
    )
    require('payload["conical_orchestration"]' in ui_source, "UI lane does not send worker context to CT246")
    require(
        "_run_conical_build_orchestration(operator_prompt)" in worker_source,
        "primary Flutter worker does not run conical orchestration",
    )
    require(
        'request_payload["conical_orchestration"]' in worker_source,
        "primary Flutter worker does not send worker context to CT246",
    )
    require(
        "_finalize_conical_build_orchestration(" in worker_source,
        "primary Flutter worker does not aggregate the final conical result",
    )
    require(
        'normalized["conical_final_receipt_written"] = True' in worker_source
        and "os.replace(temp_path, receipt_path)" in worker_source,
        "primary Flutter worker does not durably persist the final conical result",
    )
    require(
        "worker_context=conical_context or None" in service_source,
        "CT chat service does not pass worker context",
    )
    require(
        "structured_files_required = bool(" in service_source
        and "has_closed_fence = text.count" in service_source
        and "has_file_marker = bool" in service_source
        and "substantial_structured_result = bool" in service_source
        and "_build_lane_reply_usable(gen_prompt, reply)" in service_source,
        "CT build routing accepts non-file provider prose as generated code",
    )
    generate_pos = service_source.find("def _build_lane_generate")
    grok_pos = service_source.find("_call_grok46_build_bridge", generate_pos)
    local_pos = service_source.find("_build_lane_local_generate", generate_pos)
    codex_pos = service_source.find("_call_codex_cli_bridge", local_pos)
    claude_pos = service_source.find("_call_claude_cli_bridge", codex_pos)
    gemini_pos = service_source.find("_call_gemini_api_bridge", claude_pos)
    require(
        0 <= grok_pos < local_pos < codex_pos < claude_pos < gemini_pos,
        "CT build routing is not ordered Grok 4.6, local model, attached Codex, then gated providers",
    )
    require(
        'os.environ.get("ENGEL_BUILD_ALLOW_PROVIDER_APIS", "0")' in service_source
        and '"provider_api_enabled": provider_api_used' in service_source
        and '"build_generation_routes": generation_routes' in service_source,
        "CT build routing does not disable provider APIs by default with route receipts",
    )
    require(
        "cap = min(stage_cap, configured_cap)" in service_source,
        "global local-build token cap overrides bounded plan/review/repair budgets",
    )
    require(
        "local_only=local_only_requested" in service_source
        and '"local_llm_only": actual_local_only' in service_source
        and '"local_only_training": local_only_requested' in service_source,
        "strict local-only UI requests do not constrain or stamp the CT246 build lane",
    )
    require(
        '"final_status": "finished" if final_ok else "failed"' in service_source
        and 'receipt["conical_job_status"]' in service_source,
        "CT246 build memory does not persist the finalized conical status",
    )
    require(
        "def _persist_ct246_conical_receipt(" in service_source
        and "def _conical_build_failure_receipt(" in service_source
        and "required conical worker gate failed" in service_source
        and '"ct246_conical_persistence_ok"' in service_source,
        "CT246 does not fail closed with durable conical success/failure proof",
    )
    heartbeat_rows: list[dict[str, object]] = []
    original_response = local_worker._response
    try:
        local_worker._response = lambda payload: heartbeat_rows.append(dict(payload))
        with local_worker._request_progress_heartbeat(
            "verify-long-build",
            enabled=True,
            interval_seconds=0.05,
        ):
            time.sleep(0.12)
    finally:
        local_worker._response = original_response
    require(
        any(
            row.get("id") == "verify-long-build"
            and row.get("delta") == ""
            and row.get("progress") == "ct246_action_running"
            for row in heartbeat_rows
        ),
        "long CT246 build wait does not emit Flutter watchdog heartbeats",
    )
    old_local = server_service._build_lane_local_generate
    old_rog_gpu_local = server_service._build_lane_rog_gpu_local_generate
    old_ct246_cpu_local = server_service._build_lane_ct246_cpu_generate
    old_codex = server_service._call_codex_cli_bridge
    old_claude = server_service._call_claude_cli_bridge
    old_gemini = server_service._call_gemini_api_bridge
    old_grok46 = server_service._call_grok46_build_bridge
    old_provider_gate = os.environ.pop("ENGEL_BUILD_ALLOW_PROVIDER_APIS", None)
    old_grok46_gate = os.environ.get("ENGEL_BUILD_GROK46_FIRST")
    os.environ.pop("ENGEL_BUILD_GROK46_FIRST", None)
    try:
        local_files = "FILE: main.py\n```python\nprint('local')\n```"
        codex_files = "FILE: main.py\n```python\nprint('codex')\n```"
        gpu_calls = 0
        cpu_calls = 0

        def usable_rog_gpu(*_args, **_kwargs):
            nonlocal gpu_calls
            gpu_calls += 1
            return {
                "ok": True,
                "assistant_reply": local_files,
                "provider": "local",
                "bridge_kind": "ct246_to_rog_gpu_local_llm",
                "model": "rog-gpu-local-test.gguf",
            }

        def unexpected_cpu(*_args, **_kwargs):
            nonlocal cpu_calls
            cpu_calls += 1
            raise AssertionError("CT246 CPU ran despite usable ROG GPU local output")

        server_service._build_lane_rog_gpu_local_generate = usable_rog_gpu
        server_service._build_lane_ct246_cpu_generate = unexpected_cpu
        selected_local = server_service._build_lane_local_generate(
            "The user asked Engel to build this: proof\nThis is a small job.",
            60,
            1200,
        )
        require(
            selected_local.get("bridge_kind") == "ct246_to_rog_gpu_local_llm"
            and selected_local.get("assistant_reply") == local_files
            and gpu_calls == 1
            and cpu_calls == 0,
            f"usable ROG GPU local route did not win: {selected_local}",
        )

        def usable_ct246_cpu(*_args, **_kwargs):
            nonlocal cpu_calls
            cpu_calls += 1
            return {
                "ok": True,
                "assistant_reply": local_files,
                "provider": "local",
                "bridge_kind": "ct246_local_coder_gguf",
                "model": "ct246-cpu-local-test.gguf",
            }

        gpu_calls = 0

        def format_retry_rog_gpu(*_args, **_kwargs):
            nonlocal gpu_calls
            gpu_calls += 1
            return {
                "ok": True,
                "assistant_reply": (
                    "I cannot complete that request." if gpu_calls == 1 else local_files
                ),
                "provider": "local",
                "bridge_kind": "ct246_to_rog_gpu_local_llm",
                "model": "rog-gpu-local-test.gguf",
            }

        server_service._build_lane_rog_gpu_local_generate = format_retry_rog_gpu
        server_service._build_lane_ct246_cpu_generate = unexpected_cpu
        cpu_calls = 0
        selected_local = server_service._build_lane_local_generate(
            "The user asked Engel to build this: proof\nThis is a small job.",
            60,
            1200,
        )
        attempts = selected_local.get("local_route_attempts") or []
        require(
            selected_local.get("bridge_kind") == "ct246_to_rog_gpu_local_llm"
            and selected_local.get("assistant_reply") == local_files
            and gpu_calls == 2
            and cpu_calls == 0
            and [row.get("route") for row in attempts]
            == [
                "ct246_to_rog_gpu_local_llm",
                "ct246_to_rog_gpu_local_llm",
            ]
            and attempts[0].get("usable") is False,
            f"ROG GPU format miss did not retry locally without CT CPU: {selected_local}",
        )

        def unavailable_rog_gpu(*_args, **_kwargs):
            return {
                "ok": False,
                "assistant_reply": "",
                "provider": "local",
                "bridge_kind": "ct246_to_rog_gpu_local_llm",
                "model": "",
                "error": "connection refused",
            }

        cpu_calls = 0
        server_service._build_lane_rog_gpu_local_generate = unavailable_rog_gpu
        server_service._build_lane_ct246_cpu_generate = usable_ct246_cpu
        selected_local = server_service._build_lane_local_generate(
            "The user asked Engel to build this: proof\nThis is a small job.",
            60,
            1200,
        )
        attempts = selected_local.get("local_route_attempts") or []
        require(
            selected_local.get("bridge_kind") == "ct246_local_coder_gguf"
            and selected_local.get("assistant_reply") == local_files
            and cpu_calls == 1
            and [row.get("route") for row in attempts]
            == ["ct246_to_rog_gpu_local_llm", "ct246_local_coder_gguf"],
            f"unavailable ROG GPU did not fall back to CT246 CPU: {selected_local}",
        )
        server_service._build_lane_rog_gpu_local_generate = old_rog_gpu_local
        server_service._build_lane_ct246_cpu_generate = old_ct246_cpu_local
        require(
            not server_service._build_lane_reply_usable(
                "The user asked Engel to build this: proof\nThis is a medium job.",
                local_files,
            ),
            "a tiny one-file draft incorrectly satisfied a medium build",
        )
        local_json_files = json.dumps(
            {
                "files": [
                    {"path": "main.py", "content": "print('local')\n"},
                    {"path": "test_main.py", "content": "def test_ok():\n    assert True\n"},
                ]
            }
        )
        require(
            server_service._build_lane_reply_usable(
                "Repair this Engel build and return changed files.",
                f"```json\n{local_json_files}\n```",
            ),
            "a complete local-model JSON repair bundle was rejected",
        )
        require(
            server_service._build_lane_json_project_file_count(local_json_files) == 2,
            "local-model JSON repair file count is incorrect",
        )
        nested_local_json_files = json.dumps(
            {
                "files": {
                    "main.py": {"content": "print('nested local')\n"},
                    "test_main.py": {
                        "content": "def test_nested_local():\n    assert True\n"
                    },
                }
            }
        )
        require(
            server_service._build_lane_reply_usable(
                "Repair this Engel build and return changed files.",
                f"```json\n{nested_local_json_files}\n```",
            )
            and server_service._build_lane_json_project_file_count(
                nested_local_json_files
            )
            == 2,
            "nested local-model JSON repair bundle was rejected",
        )
        raw_python_repair = (
            "```python\n"
            "from __future__ import annotations\n\n"
            "def repaired_receipt(record: dict) -> dict:\n"
            "    result = dict(record)\n"
            "    result.setdefault('workers', [])\n"
            "    result.setdefault('final_status', 'unknown')\n"
            "    result.setdefault('package_path', '')\n"
            "    result.setdefault('rollback_path', '')\n"
            "    return result\n"
            "```"
        )
        raw_repair_prompt = (
            "Repair this Engel build.\n"
            "ENGEL_SINGLE_FILE_TARGET: conical_proof_viewer.py\n"
        )
        require(
            server_service._build_lane_reply_usable(
                raw_repair_prompt,
                raw_python_repair,
            )
            and server_service._build_lane_single_target_code_file(
                raw_repair_prompt,
                raw_python_repair,
            )
            == "conical_proof_viewer.py",
            "complete single-target local Python repair was rejected",
        )
        require(
            not server_service._build_lane_reply_usable(
                raw_repair_prompt,
                '```json\n{"status":"candidate_only"}\n```',
            ),
            "single-target repair accepted JSON status prose as source code",
        )
        server_service._build_lane_local_generate = lambda *_args, **_kwargs: {
            "ok": True,
            "assistant_reply": local_files,
            "provider": "local",
            "model": "local-test.gguf",
        }
        server_service._call_codex_cli_bridge = lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("attached Codex ran despite usable local generation")
        )
        server_service._call_claude_cli_bridge = lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("Claude provider ran while provider gate was disabled")
        )
        server_service._call_gemini_api_bridge = lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("Gemini provider ran while provider gate was disabled")
        )
        routes: list[dict[str, object]] = []
        generated = server_service._build_lane_generate(
            "The user asked Engel to build this: proof\nThis is a small job.",
            60,
            1200,
            route_log=routes,
        )
        require(generated == local_files, "usable CT local generation was not selected")
        require(
            [row.get("route") for row in routes] == ["ct246_local_coder_gguf"],
            f"local success did not stop routing: {routes}",
        )
        server_service._build_lane_local_generate = lambda *_args, **_kwargs: {
            "ok": True,
            "assistant_reply": f"```json\n{local_json_files}\n```",
            "provider": "local",
            "model": "local-test.gguf",
        }
        routes = []
        generated = server_service._build_lane_generate(
            "Repair this Engel build and return changed files.",
            60,
            1200,
            route_log=routes,
        )
        require(
            generated == f"```json\n{local_json_files}\n```",
            "usable CT local JSON repair did not stop at the local route",
        )
        require(
            len(routes) == 1
            and routes[0].get("route") == "ct246_local_coder_gguf"
            and routes[0].get("route_attempt") == 1
            and routes[0].get("usable") is True
            and routes[0].get("json_file_count") == 2,
            f"local JSON repair provenance is incorrect: {routes}",
        )
        server_service._build_lane_local_generate = lambda *_args, **_kwargs: {
            "ok": True,
            "assistant_reply": raw_python_repair,
            "provider": "local",
            "model": "local-test.gguf",
        }
        routes = []
        generated = server_service._build_lane_generate(
            raw_repair_prompt,
            60,
            1800,
            route_log=routes,
            local_only=True,
        )
        require(
            generated == raw_python_repair
            and len(routes) == 1
            and routes[0].get("single_target_code_file")
            == "conical_proof_viewer.py",
            f"single-target local repair did not stay on CT246: {routes}",
        )

        retry_count = 0

        def local_retry_then_success(*_args, **_kwargs):
            nonlocal retry_count
            retry_count += 1
            return {
                "ok": True,
                "assistant_reply": "I cannot complete that request." if retry_count == 1 else local_files,
                "provider": "local",
                "model": "local-test.gguf",
            }

        server_service._build_lane_local_generate = local_retry_then_success
        server_service._call_codex_cli_bridge = lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("attached Codex ran before the second local attempt")
        )
        routes = []
        generated = server_service._build_lane_generate(
            "The user asked Engel to build this: local retry proof\nThis is a small job.",
            60,
            1200,
            route_log=routes,
        )
        require(generated == local_files, "second CT local generation attempt was not selected")
        require(
            [row.get("route_attempt") for row in routes] == [1, 2]
            and all(row.get("route") == "ct246_local_coder_gguf" for row in routes),
            f"second local attempt provenance is incorrect: {routes}",
        )

        server_service._build_lane_local_generate = lambda *_args, **_kwargs: {
            "ok": False,
            "assistant_reply": "",
            "provider": "local",
            "error": "bounded local miss",
        }
        server_service._call_codex_cli_bridge = lambda *_args, **_kwargs: {
            "ok": True,
            "assistant_reply": codex_files,
            "provider": "codex",
            "model": "attached-codex-test",
        }
        routes = []
        generated = server_service._build_lane_generate(
            "The user asked Engel to build this: proof\nThis is a small job.",
            60,
            1200,
            route_log=routes,
        )
        require(generated == codex_files, "attached Codex fallback did not return")
        require(
            [row.get("route") for row in routes]
            == [
                "ct246_local_coder_gguf",
                "ct246_local_coder_gguf",
                "rog_attached_codex_cli",
            ]
            and [row.get("route_attempt") for row in routes] == [1, 2, 1],
            f"provider-free fallback order mismatch: {routes}",
        )
        require(
            all(row.get("provider_api_enabled") is False for row in routes),
            "provider-free local/Codex routes were labelled as provider APIs",
        )

        # A force_provider flag does not skip the local coder. The router
        # starts on the local lane even when the request names Codex.
        old_explicit_local = server_service._build_lane_local_generate
        old_explicit_codex = server_service._call_codex_cli_bridge
        try:
            def codex_should_wait(*_args, **_kwargs):
                raise AssertionError("auto route called Codex before the local coder")

            server_service._build_lane_local_generate = lambda *_args, **_kwargs: {
                "ok": True,
                "assistant_reply": local_files,
                "provider": "local",
                "model": "local-test.gguf",
            }
            server_service._call_codex_cli_bridge = codex_should_wait
            auto_routes: list[dict[str, object]] = []
            auto_selection: dict[str, object] = {}
            generated = server_service._build_lane_generate(
                "The user asked Engel to build this: explicit provider proof\nThis is a small job.",
                60,
                1200,
                route_log=auto_routes,
                provider_request={
                    "provider": "codex",
                    "force_provider": True,
                    "model": "codex-test-model",
                    "allow_provider_fallback": False,
                },
                provider_selection=auto_selection,
            )
            require(
                generated == local_files
                and auto_routes
                and auto_routes[0].get("route") == "ct246_local_coder_gguf"
                and auto_selection.get("selected_provider") == "local"
                and auto_selection.get("requested_provider") in {"", None},
                f"force_provider still skipped the local coder: {auto_routes} {auto_selection}",
            )
        finally:
            server_service._build_lane_local_generate = old_explicit_local
            server_service._call_codex_cli_bridge = old_explicit_codex

        repair_routes: list[dict[str, object]] = []
        generated = server_service._build_lane_generate(
            "Repair this Engel build in place: proof",
            60,
            1200,
            route_log=repair_routes,
        )
        require(generated == codex_files, "attached Codex fallback did not repair after the local miss")
        require(
            [row.get("route") for row in repair_routes]
            == [
                "ct246_local_coder_gguf",
                "ct246_local_coder_gguf",
                "rog_attached_codex_cli",
            ]
            and [row.get("route_attempt") for row in repair_routes] == [1, 2, 1]
            and all(row.get("stage") == "repair" for row in repair_routes),
            f"repair stage did not remain local-first with bounded fallback: {repair_routes}",
        )
        server_service._call_codex_cli_bridge = lambda *_args, **_kwargs: (
            _ for _ in ()
        ).throw(AssertionError("strict local-only build attempted attached Codex"))
        local_only_routes: list[dict[str, object]] = []
        generated = server_service._build_lane_generate(
            "Repair this Engel build in place: strict local proof",
            60,
            1200,
            route_log=local_only_routes,
            local_only=True,
        )
        require(generated == "", "failed strict local-only generation fabricated output")
        require(
            [row.get("route") for row in local_only_routes]
            == ["ct246_local_coder_gguf", "ct246_local_coder_gguf"],
            f"strict local-only generation escaped CT246 local routes: {local_only_routes}",
        )

        grok_files = "FILE: main.py\n```python\nprint('grok46')\n```"
        os.environ["ENGEL_BUILD_GROK46_FIRST"] = "1"
        server_service._call_grok46_build_bridge = lambda *_args, **_kwargs: {
            "ok": True,
            "assistant_reply": grok_files,
            "provider": "xai",
            "model": "grok-4.6",
            "bridge_kind": "rog_grok46_super_cli",
        }
        server_service._build_lane_local_generate = lambda *_args, **_kwargs: (
            _ for _ in ()
        ).throw(AssertionError("local build ran despite usable Grok 4.6"))
        grok_routes: list[dict[str, object]] = []
        generated = server_service._build_lane_generate(
            "The user asked Engel to build this: grok first proof\nThis is a small job.",
            60,
            1200,
            route_log=grok_routes,
        )
        require(generated == grok_files, "usable Grok 4.6 build was not selected")
        require(
            [row.get("route") for row in grok_routes] == ["rog_grok46_super_cli"]
            and grok_routes[0].get("model") == "grok-4.6",
            f"Grok 4.6 success did not stop routing: {grok_routes}",
        )

        server_service._call_grok46_build_bridge = lambda *_args, **_kwargs: {
            "ok": False,
            "assistant_reply": "",
            "provider": "xai",
            "model": "grok-4.6",
            "bridge_kind": "rog_grok46_super_cli",
            "error": "Grok 4.6 Super CLI bridge not available",
        }
        server_service._build_lane_local_generate = lambda *_args, **_kwargs: {
            "ok": True,
            "assistant_reply": local_files,
            "provider": "local",
            "model": "local-test.gguf",
        }
        fallback_routes: list[dict[str, object]] = []
        generated = server_service._build_lane_generate(
            "The user asked Engel to build this: grok fallback proof\nThis is a small job.",
            60,
            1200,
            route_log=fallback_routes,
        )
        require(generated == local_files, "local build lane did not run after Grok 4.6 miss")
        require(
            [row.get("route") for row in fallback_routes]
            == ["rog_grok46_super_cli", "ct246_local_coder_gguf"],
            f"Grok 4.6 miss did not fall back to local: {fallback_routes}",
        )

        local_only_grok_routes: list[dict[str, object]] = []
        generated = server_service._build_lane_generate(
            "The user asked Engel to build this: grok local-only proof\nThis is a small job.",
            60,
            1200,
            route_log=local_only_grok_routes,
            local_only=True,
        )
        require(
            generated == local_files
            and all(row.get("route") != "rog_grok46_super_cli" for row in local_only_grok_routes),
            f"strict local-only still called Grok 4.6: {local_only_grok_routes}",
        )
    finally:
        server_service._build_lane_local_generate = old_local
        server_service._build_lane_rog_gpu_local_generate = old_rog_gpu_local
        server_service._build_lane_ct246_cpu_generate = old_ct246_cpu_local
        server_service._call_codex_cli_bridge = old_codex
        server_service._call_claude_cli_bridge = old_claude
        server_service._call_gemini_api_bridge = old_gemini
        server_service._call_grok46_build_bridge = old_grok46
        if old_provider_gate is not None:
            os.environ["ENGEL_BUILD_ALLOW_PROVIDER_APIS"] = old_provider_gate
        else:
            os.environ.pop("ENGEL_BUILD_ALLOW_PROVIDER_APIS", None)
        if old_grok46_gate is None:
            os.environ.pop("ENGEL_BUILD_GROK46_FIRST", None)
        else:
            os.environ["ENGEL_BUILD_GROK46_FIRST"] = old_grok46_gate
    require("CANDIDATE WORKER CONTRIBUTIONS" in build_source, "build generator does not consume worker returns")
    require(
        "Make every generated sample-data, proof, and packaging command repeatable"
        in build_source,
        "build generator does not require repeatable proof and package commands",
    )
    require(
        'residual_limit = 4 if build_size == "expert" else 3 if build_size == "large" else 2'
        in build_source,
        "build lane does not provide enough residual repair passes",
    )
    require(
        '28672 if build_size == "expert" else 20480 if build_size == "large" else 8192'
        in build_source,
        "large and expert build output budgets are too small for complete multi-file results",
    )
    require(
        "def _bounded_new_project_generation(" in build_source
        and "def _should_split_build_into_hive_packages(" in build_source
        and '"mode": "bounded_per_file"' in build_source
        and '"whole_project_generation_used": False' in build_source
        and "min(effective_timeout, 150)" in build_source
        and "min(effective_tokens, 4096)" in build_source,
        "hive package split / bounded per-file generation is missing",
    )
    require(
        "def _infer_build_language_for_request(" in build_source,
        "explicit language selection can still lose to a generic app target",
    )
    require(
        "for generation_attempt in range(1, 3)" in build_source
        and "previous generation attempt returned no complete parseable project"
        in build_source
        and '"generate_retry"' in build_source,
        "build lane does not retry an empty or unparseable generation response",
    )
    require('"worker_dispatch"' in build_source, "build lifecycle lacks worker dispatch stage")
    require(
        'retry["dispatch_attempt"] = 2' in ui_source
        and 'retry["retry_of_packet_id"]' in ui_source
        and '"phone_retry_assignment_count": len(retry_assignments)' in ui_source,
        "conical phone dispatch lacks a bounded exact-packet retry",
    )
    require(
        "bounded_sub_engel_work_pipe_retry" in ui_source
        and "This is not an unpaired node" in ui_source
        and "def _honest_sub_engel_dispatch_error(" in ui_source,
        "conical Sub-Engel dispatch treats a CT246 pipe reset as disconnected",
    )
    require("conical_checkins" in meeting_source, "Meeting Room does not display conical worker tasks")
    require(
        "_close_previous_build_preview(hwnd)" in visible_runner_source,
        "visible UI runner does not restore the composer after a build preview",
    )
    require(
        "ui_submission_accepted" in visible_runner_source
        and "submission_probe_deadline" in visible_runner_source
        and "def _matching_conical_receipt(" in visible_runner_source
        and "conical_terminal_grace_deadline" in visible_runner_source,
        "visible UI runner does not prove build-prompt acceptance",
    )
    require(
        "def _is_delivery_failure(" in visible_runner_source
        and "consecutive_delivery_failures >= _MAX_CONSECUTIVE_DELIVERY_FAILURES"
        in visible_runner_source,
        "paced UI runner stops early only on repeated delivery failures, not the first "
        "quality-blocked turn",
    )
    require(
        'prompt_to_send = f"Overwrite and rebuild this request: {prompt}"'
        in visible_runner_source,
        "resumed UI build retries do not bypass duplicate-workspace refusal",
    )
    require(
        '"expected_build_lane": payload.get("expected_build_lane")' in visible_runner_source
        and "creation_verified = bool(" in visible_runner_source
        and "build_execution_verified" in visible_runner_source
        and "conical_proof.get(\"ok\") is True" in visible_runner_source
        and "def _build_proof(" in visible_runner_source
        and "def _conical_proof(" in visible_runner_source
        and "EXPECTED_CONICAL_WORKERS" in visible_runner_source,
        "visible UI runner allows orchestration activity to substitute for verified build output",
    )

    print("PASS: medium-to-expert jobs split across Alpha, Beta, Gamma, and Sub-Engel")
    print("PASS: exact current phone packet and Sub order receipts are required")
    print("PASS: returned candidate work reaches CT246 generation and final receipts")
    print("PASS: Meeting Room consumes live conical worker check-ins")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
