#!/usr/bin/env python3
"""Verifier for the Engel Conical Self-Upgrade Cycle (engel_conical_self_upgrade_cycle.py).

Proves the ONE governed flow really enforces its ordering and honesty:

  1. Dry-run requires exact four-worker review, then runs
     intake->route->distributed_work->candidate->quorum->legacy_gate and
     applies NOTHING.
  2. The cycle receipt's stage chain hash recomputes (tamper-evident).
  3. Execute without APPROVE_FIX_CANDIDATE -> blocked_at_quorum, no mutation.
  4. The memory-promotion token never reaches apply (separate chains).
  5. Fully-tokened execute -> applied AND post-deploy committed -> upgraded_verified.
  6. The apply receipt carries required_verifiers (post-deploy gate input).
  7. A verifier that fails ONLY post-apply -> AUTO-ROLLBACK, target restored
     byte-identical -> applied_then_rolled_back (honest, no false success).
  8. Medium-risk candidate -> quorum may pass but the legacy low-risk gate
     blocks -> blocked_at_legacy_gate, no mutation.
  9. Forbidden-storage target halts before apply.
 10. The rewired apply engine refuses without an AUTHORIZED matching quorum
     decision (argparse-level and loader-level fail-closed).

All fixture receipts are redirected into runtime/temp so real evidence dirs
stay clean. Emits {"ok": bool, ...}; exit 0 pass / 1 fail.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT), str(ROOT / "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

import engel_conical_self_upgrade_cycle as cycle  # noqa: E402
import engel_self_patch_quorum as quorum_mod  # noqa: E402
import engel_deployment_rollback_automation as rollback_mod  # noqa: E402
import engel_self_upgrade_apply_engine as engine  # noqa: E402
from engel_self_upgrade_system import SelfUpgradeError  # noqa: E402

system = cycle.system
CHECKS: list[dict] = []

FIX = "APPROVE_FIX_CANDIDATE"
MEM = "APPROVE_PROMOTE_MEMORY_CANDIDATE"
GATE = system.LOW_RISK_GATE_TOKEN
APPLY = system.LOW_RISK_APPLY_TOKEN
ELEVATED_GATE = system.ELEVATED_RISK_GATE_TOKEN
ELEVATED_APPLY = system.ELEVATED_RISK_APPLY_TOKEN


def record(name: str, ok: bool, detail: str = "") -> None:
    CHECKS.append({"check": name, "ok": bool(ok), "detail": detail})


def stage_names(result: dict) -> list[str]:
    return [s["stage"] for s in result.get("stages", [])]


def main() -> int:
    fx = ROOT / "runtime" / "temp" / f"cycle_verify_{os.getpid()}"
    fx_reports = fx / "reports"
    fx.mkdir(parents=True, exist_ok=True)
    # The legacy gate only accepts verifier evidence under real reports\, so the
    # fixture quorum receipts land in a labeled, cleaned-up subdir there.
    fx_quorum = ROOT / "reports" / "self_upgrade" / f"cycle_verify_fixture_{os.getpid()}"

    target = fx / "target_module.py"
    original_bytes = b"x = 1\n"
    target.write_bytes(original_bytes)
    target_rel = system.project_relative(target)
    original_sha = system.sha256_file(target)

    pass_verifier = fx / "fixture_pass_verifier.py"
    pass_verifier.write_bytes(b"import sys; sys.exit(0)\n")
    content_verifier = fx / "fixture_content_verifier.py"
    content_verifier.write_bytes(
        (
            "import sys\n"
            f"text = open({str(target)!r}, encoding='utf-8').read()\n"
            "sys.exit(0 if 'x = 1' in text else 1)\n"
        ).encode("utf-8")
    )

    def request(**over) -> dict:
        base = {
            "source": "verifier",
            "symptom": "fixture constant drift detected in cycle fixture module",
            "severity": "low",
            "affected_surface": "chat",
            "evidence_paths": [],
            "diagnosis": "the fixture constant is stale and should be updated",
            "patch_plan": "adjust the fixture constant to the corrected value",
            "files_to_change": [target_rel],
            "operations": [{"op": "replace_text", "file": target_rel,
                            "old_text": "x = 1", "new_text": "x = 2"}],
            "lesson": "Cycle fixture lesson: constants drift and need verifier coverage.",
        }
        base.update(over)
        return base

    # --- redirect every receipt write into the fixture tree -----------------
    saved = {
        "surface_matrix": system.surface_matrix,
        "write_issue": system.write_issue,
        "write_route": system.write_route,
        "write_meeting_room_work_order": system.write_meeting_room_work_order,
        "write_patch_candidate": system.write_patch_candidate,
        "write_file_patch": system.write_file_patch,
        "write_gate_receipt": system.write_gate_receipt,
        "write_apply_receipt": system.write_apply_receipt,
        "write_memory_candidate": system.write_memory_candidate,
        "apply_candidate_patch": system.apply_candidate_patch,
        "cycle_dir": cycle.CYCLE_DIR,
        "system_report_root": system.REPORT_ROOT,
        "quorum_report_root": quorum_mod.REPORT_ROOT,
        "rollback_report_root": rollback_mod.REPORT_ROOT,
        "complete_meeting_room_order": cycle._complete_meeting_room_order,
    }
    fixture_matrix = {
        "owner": "ct246_engel_ai_main",
        "supporting_workers": [],
        "preferred_model_route": "local_llm_first",
        "required_verifiers": [system.project_relative(pass_verifier)],
        "runtime_checks": [],
    }
    system.surface_matrix = lambda surface: dict(fixture_matrix)
    system.write_issue = lambda issue: saved["write_issue"](issue, fx_reports)
    system.write_route = lambda route: saved["write_route"](route, fx_reports)
    system.write_meeting_room_work_order = (
        lambda order: saved["write_meeting_room_work_order"](
            order,
            memory_dir=fx_reports / "meeting_room" / "memory",
            runtime_dir=fx_reports / "meeting_room" / "runtime",
        )
    )
    system.write_patch_candidate = lambda cand: saved["write_patch_candidate"](cand, fx_reports)
    system.write_file_patch = lambda patch, cand: saved["write_file_patch"](patch, cand, fx_reports)
    system.write_gate_receipt = lambda receipt: saved["write_gate_receipt"](receipt, fx_reports)
    system.write_apply_receipt = lambda receipt: saved["write_apply_receipt"](receipt, fx_reports)
    system.write_memory_candidate = lambda cand: saved["write_memory_candidate"](cand, fx_reports)
    system.apply_candidate_patch = (
        lambda cand, gate, patch, **kw: saved["apply_candidate_patch"](
            cand, gate, patch, report_root=fx_reports, **kw))
    cycle.CYCLE_DIR = fx_reports / "cycles"
    system.REPORT_ROOT = fx_reports
    quorum_mod.REPORT_ROOT = fx_quorum
    rollback_mod.REPORT_ROOT = fx_reports

    review_counter = 0
    completed_room_orders: list[dict] = []

    def complete_meeting_room_order(cycle_receipt: dict, final_status: str) -> dict:
        receipt = {
            "ok": True,
            "accepted": True,
            "meeting_room_server_used": True,
            "order_id": cycle_receipt.get("meeting_room_order_id"),
            "final_status": final_status,
        }
        completed_room_orders.append(receipt)
        return receipt

    cycle._complete_meeting_room_order = complete_meeting_room_order

    def distributed_review(_issue: dict, _route: dict, _request: dict) -> dict:
        nonlocal review_counter
        review_counter += 1
        receipt_path = fx_reports / "worker_reviews" / f"review_{review_counter}.json"
        payload = {
            "schema": "engel_conical_build_orchestration_v1",
            "ok": True,
            "status": "workers_returned",
            "job_id": f"fixture_review_{review_counter}",
            "meeting_room_order_id": f"fixture_order_{review_counter}",
            "expected_worker_count": len(cycle.CONICAL_REQUIRED_WORKERS),
            "returned_worker_count": len(cycle.CONICAL_REQUIRED_WORKERS),
            "worker_results": [
                {
                    "worker_id": worker_id,
                    "returned": True,
                    "status": "returned",
                    "candidate_only": True,
                }
                for worker_id in cycle.CONICAL_REQUIRED_WORKERS
            ],
            "receipt_path": str(receipt_path),
            "trusted_memory_write": False,
        }
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return payload

    import engel_build_lane
    import engel_device_broker

    original_broker_decision = engel_device_broker.broker_decision
    engel_device_broker.broker_decision = lambda job_kind=None: {
        "candidates": [
            {
                "device_id": "android_worker_alpha",
                "eligible": True,
                "allowed": True,
            }
        ]
    }
    try:
        broker_evidence = cycle._broker_evidence(
            {"supporting_workers": ["android_worker_alpha"]}
        )
    finally:
        engel_device_broker.broker_decision = original_broker_decision
    record(
        "cycle consumes the broker's real candidates key",
        broker_evidence.get("eligible_devices") == ["android_worker_alpha"],
        str(broker_evidence),
    )

    captured_prompt: dict[str, str] = {}
    original_orchestrator_module = sys.modules.get(
        "run_engel_ui_chat_meeting_room_llm"
    )
    fake_orchestrator = types.SimpleNamespace(
        _run_conical_build_orchestration=lambda prompt: (
            captured_prompt.update({"prompt": prompt})
            or {"schema": "engel_conical_build_orchestration_v1"}
        )
    )
    sys.modules["run_engel_ui_chat_meeting_room_llm"] = fake_orchestrator
    try:
        default_review = cycle._default_distributed_review(
            {"symptom": "fixture symptom"},
            {},
            {
                "affected_surface": "chat",
                "diagnosis": "fixture diagnosis",
                "patch_plan": "fixture plan",
                "files_to_change": ["fixture.py"],
                "operations": [
                    {
                        "op": "replace_text",
                        "file": "fixture.py",
                        "old_text": "x" * 5000,
                        "new_text": "y" * 5000,
                    }
                ],
            },
        )
    finally:
        if original_orchestrator_module is None:
            sys.modules.pop("run_engel_ui_chat_meeting_room_llm", None)
        else:
            sys.modules[
                "run_engel_ui_chat_meeting_room_llm"
            ] = original_orchestrator_module
    review_prompt = captured_prompt.get("prompt", "")
    record(
        "default distributed review reaches the real UI build intent",
        bool(default_review)
        and engel_build_lane.is_build_request(review_prompt) is not None
        and engel_build_lane.classify_build_size(review_prompt) == "large",
        review_prompt[:180],
    )
    record(
        "distributed review prompt is bounded and binds full operations by hash",
        len(review_prompt) < 5000
        and "old_sha256" in review_prompt
        and "new_sha256" in review_prompt
        and ("x" * 500) not in review_prompt
        and ("y" * 500) not in review_prompt,
        f"chars={len(review_prompt)}",
    )

    try:
        # 1+2: dry run --------------------------------------------------------
        result = cycle.run_cycle(request(), dry_run=True, fix_approval_token=FIX,
                                 gate_token=GATE,
                                 distributed_review_fn=distributed_review)
        record("dry-run completes through the quorum without applying",
               result["final_status"] == "dry_run_complete"
               and stage_names(result) == [
                   "intake", "route", "distributed_work", "candidate",
                   "provenance", "quorum", "legacy_gate",
                   "meeting_room_visibility",
               ]
               and result.get("meeting_room_completion", {}).get("accepted") is True
               and target.read_bytes() == original_bytes,
               result["final_status"])
        record(
            "terminal cycle state is propagated to its visible Meeting Room order",
            completed_room_orders[-1].get("order_id")
            == result.get("meeting_room_order_id")
            and completed_room_orders[-1].get("final_status")
            == "dry_run_complete"
            and result["stages"][-1].get("stage")
            == "meeting_room_visibility"
            and result["stages"][-1].get("ok") is True,
            str(completed_room_orders[-1]),
        )
        result_without_apply_approval = cycle.run_cycle(
            request(),
            dry_run=True,
            distributed_review_fn=distributed_review,
        )
        review_quorum = next(
            (
                stage
                for stage in result_without_apply_approval["stages"]
                if stage["stage"] == "quorum"
            ),
            {},
        )
        record(
            "review-only cycle completes while preserving denied apply votes",
            result_without_apply_approval["final_status"] == "dry_run_complete"
            and review_quorum.get("ok") is False
            and "apply" not in stage_names(result_without_apply_approval)
            and target.read_bytes() == original_bytes,
            result_without_apply_approval["final_status"],
        )
        receipt_file = system.project_path_from_relative(result["cycle_receipt_path"])
        on_disk = json.loads(receipt_file.read_text(encoding="utf-8"))
        record("cycle receipt chain hash recomputes (tamper-evident)",
               receipt_file.is_file()
               and cycle._chain_sha256(on_disk["stages"]) == on_disk["receipt_chain_sha256"],
               on_disk.get("receipt_chain_sha256", "")[:16])
        candidate_stage = next(
            (stage for stage in result["stages"] if stage["stage"] == "candidate"),
            {},
        )
        candidate_receipt = json.loads(
            system.project_path_from_relative(
                candidate_stage["receipt_path"]
            ).read_text(encoding="utf-8")
        )
        record(
            "candidate binds the exact distributed review receipt and four workers",
            bool(candidate_receipt.get("distributed_review_receipt"))
            and len(str(candidate_receipt.get("distributed_review_sha256") or "")) == 64
            and candidate_receipt.get("distributed_review_worker_ids")
            == list(cycle.CONICAL_REQUIRED_WORKERS),
            str(candidate_receipt.get("distributed_review_worker_ids")),
        )
        provenance_stage = next(
            (
                stage
                for stage in result["stages"]
                if stage["stage"] == "provenance"
            ),
            {},
        )
        provenance_receipt = json.loads(
            system.project_path_from_relative(
                provenance_stage["receipt_path"]
            ).read_text(encoding="utf-8")
        )
        record(
            "cycle binds an immutable prompt-to-patch provenance entry before quorum",
            bool(provenance_receipt.get("provenance_id"))
            and len(str(provenance_receipt.get("request_sha256") or "")) == 64
            and provenance_receipt.get("source_mutation_performed") is False
            and provenance_stage.get("entry_sha256")
            == provenance_receipt.get("entry_sha256"),
            str(provenance_receipt.get("provenance_id") or ""),
        )

        def incomplete_review(issue: dict, route: dict, req: dict) -> dict:
            payload = distributed_review(issue, route, req)
            payload["worker_results"] = payload["worker_results"][:-1]
            payload["returned_worker_count"] = len(payload["worker_results"])
            Path(payload["receipt_path"]).write_text(
                json.dumps(payload, indent=2), encoding="utf-8"
            )
            return payload

        result = cycle.run_cycle(
            request(), dry_run=True, fix_approval_token=FIX,
            gate_token=GATE, distributed_review_fn=incomplete_review)
        distributed_stage = next(
            (
                stage
                for stage in result["stages"]
                if stage.get("stage") == "distributed_work"
            ),
            {},
        )
        record(
            "missing one required worker blocks before candidate and preserves the failed review receipt",
            result["final_status"] == "blocked_at_distributed_work"
            and stage_names(result) == [
                "intake",
                "route",
                "distributed_work",
                "meeting_room_visibility",
            ]
            and bool(distributed_stage.get("receipt_path"))
            and len(
                str(
                    distributed_stage.get("distributed_review_sha256")
                    or ""
                )
            )
            == 64
            and target.read_bytes() == original_bytes,
            result["final_status"],
        )

        cycle._complete_meeting_room_order = (
            lambda _cycle_receipt, _final_status: {
                "ok": False,
                "accepted": False,
                "reason": "fixture room completion rejected",
            }
        )
        result = cycle.run_cycle(
            request(),
            dry_run=True,
            fix_approval_token=FIX,
            gate_token=GATE,
            distributed_review_fn=distributed_review,
        )
        record(
            "successful cycle cannot claim visible completion when the room rejects it",
            result["final_status"] == "failed_at_meeting_room_visibility"
            and result.get("pre_visibility_final_status") == "dry_run_complete"
            and result["stages"][-1].get("stage")
            == "meeting_room_visibility"
            and result["stages"][-1].get("ok") is False
            and target.read_bytes() == original_bytes,
            result["final_status"],
        )
        cycle._complete_meeting_room_order = complete_meeting_room_order

        # 3: execute without fix token ---------------------------------------
        result = cycle.run_cycle(
            request(), dry_run=False, gate_token=GATE, apply_token=APPLY,
            distributed_review_fn=distributed_review)
        record("execute without APPROVE_FIX_CANDIDATE is blocked at the quorum",
               result["final_status"] == "blocked_at_quorum"
               and "apply" not in stage_names(result)
               and target.read_bytes() == original_bytes,
               result["final_status"])

        # 4: memory-promotion token ------------------------------------------
        result = cycle.run_cycle(request(), dry_run=False, fix_approval_token=MEM,
                                 gate_token=GATE, apply_token=APPLY,
                                 distributed_review_fn=distributed_review)
        record("memory-promotion token never authorizes the fix chain",
               result["final_status"] == "blocked_at_quorum"
               and target.read_bytes() == original_bytes,
               result["final_status"])

        # 5+6: full execute, committed ---------------------------------------
        result = cycle.run_cycle(request(), dry_run=False, fix_approval_token=FIX,
                                 gate_token=GATE, apply_token=APPLY,
                                 distributed_review_fn=distributed_review)
        apply_stage = next((s for s in result["stages"] if s["stage"] == "apply"), {})
        post_stage = next((s for s in result["stages"] if s["stage"] == "post_deploy_gate"), {})
        lesson_stage = next((s for s in result["stages"] if s["stage"] == "lesson"), {})
        record("fully-tokened execute applies, verifies, and commits",
               result["final_status"] == "upgraded_verified"
               and target.read_bytes() == b"x = 2\n"
               and post_stage.get("detail") == "decision=committed"
               and lesson_stage.get("ok") is True,
               result["final_status"])
        apply_receipt = json.loads(system.project_path_from_relative(
            apply_stage["receipt_path"]).read_text(encoding="utf-8"))
        record("apply receipt carries required_verifiers for the post-deploy gate",
               apply_receipt.get("required_verifiers") == [system.project_relative(pass_verifier)],
               str(apply_receipt.get("required_verifiers")))
        target.write_bytes(original_bytes)  # reset fixture for the next legs

        # 7: rollback leg — verifier passes pre-apply, fails post-apply -------
        result = cycle.run_cycle(
            request(extra_required_verifiers=[system.project_relative(content_verifier)]),
            dry_run=False, fix_approval_token=FIX, gate_token=GATE,
            apply_token=APPLY, distributed_review_fn=distributed_review)
        post_stage = next((s for s in result["stages"] if s["stage"] == "post_deploy_gate"), {})
        record("post-apply verifier failure auto-rolls-back, restore hash-proven",
               result["final_status"] == "applied_then_rolled_back"
               and target.read_bytes() == original_bytes
               and system.sha256_file(target) == original_sha
               and post_stage.get("rollback_performed") is True,
               result["final_status"])

        # 8: medium risk blocked by the low-risk legacy gate ------------------
        result = cycle.run_cycle(request(severity="medium"), dry_run=False,
                                 fix_approval_token=FIX, gate_token=GATE,
                                 apply_token=APPLY,
                                 distributed_review_fn=distributed_review)
        record("medium-risk candidate is blocked before apply by the low-risk gate",
               result["final_status"] == "blocked_at_legacy_gate"
               and "apply" not in stage_names(result)
               and target.read_bytes() == original_bytes,
               result["final_status"])

        result = cycle.run_cycle(
            request(severity="medium"),
            dry_run=False,
            fix_approval_token=FIX,
            gate_token=ELEVATED_GATE,
            apply_token=ELEVATED_APPLY,
            distributed_review_fn=distributed_review,
        )
        record(
            "medium-risk candidate applies only with the elevated approval pair",
            result["final_status"] == "upgraded_verified"
            and target.read_bytes() == b"x = 2\n",
            result["final_status"],
        )
        target.write_bytes(original_bytes)

        # 9: forbidden-storage target halts before apply ----------------------
        result = cycle.run_cycle(
            request(files_to_change=["reports\\engel-vault\\x.py"],
                    operations=[{"op": "replace_text", "file": "reports\\engel-vault\\x.py",
                                 "old_text": "a", "new_text": "b"}]),
            dry_run=False, fix_approval_token=FIX, gate_token=GATE,
            apply_token=APPLY, distributed_review_fn=distributed_review)
        record("forbidden-storage target halts the cycle before apply",
               result["final_status"] in {"failed_at_candidate", "blocked_at_quorum"}
               and "apply" not in stage_names(result),
               result["final_status"])

        # 10: rewired apply engine fail-closed --------------------------------
        proc = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "engel_self_upgrade_apply_engine.py"),
             "--candidate", "missing.json", "--gate-receipt", "missing.json"],
            cwd=str(ROOT), capture_output=True, text=True, timeout=60, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        blocked_decision = fx / "blocked_decision.json"
        blocked_decision.write_text(json.dumps({
            "schema": "ENGEL_SELF_PATCH_QUORUM_DECISION_V1",
            "apply_allowed": False, "candidate_id": "c1", "vetoed_by": ["human_approval"],
        }), encoding="utf-8")
        mismatch_decision = fx / "mismatch_decision.json"
        mismatch_decision.write_text(json.dumps({
            "schema": "ENGEL_SELF_PATCH_QUORUM_DECISION_V1",
            "apply_allowed": True, "candidate_id": "someone_else",
        }), encoding="utf-8")
        loader_blocked = loader_mismatch = False
        try:
            engine.load_authorized_quorum_decision(str(blocked_decision), "c1")
        except SelfUpgradeError:
            loader_blocked = True
        try:
            engine.load_authorized_quorum_decision(str(mismatch_decision), "c1")
        except SelfUpgradeError:
            loader_mismatch = True
        record("apply engine refuses without an authorized matching quorum decision",
               proc.returncode == 2 and loader_blocked and loader_mismatch,
               f"argparse_rc={proc.returncode} blocked={loader_blocked} mismatch={loader_mismatch}")
    finally:
        system.surface_matrix = saved["surface_matrix"]
        system.write_issue = saved["write_issue"]
        system.write_route = saved["write_route"]
        system.write_meeting_room_work_order = saved["write_meeting_room_work_order"]
        system.write_patch_candidate = saved["write_patch_candidate"]
        system.write_file_patch = saved["write_file_patch"]
        system.write_gate_receipt = saved["write_gate_receipt"]
        system.write_apply_receipt = saved["write_apply_receipt"]
        system.write_memory_candidate = saved["write_memory_candidate"]
        system.apply_candidate_patch = saved["apply_candidate_patch"]
        cycle.CYCLE_DIR = saved["cycle_dir"]
        system.REPORT_ROOT = saved["system_report_root"]
        quorum_mod.REPORT_ROOT = saved["quorum_report_root"]
        rollback_mod.REPORT_ROOT = saved["rollback_report_root"]
        cycle._complete_meeting_room_order = saved["complete_meeting_room_order"]
        shutil.rmtree(fx, ignore_errors=True)
        shutil.rmtree(fx_quorum, ignore_errors=True)

    failed = [c for c in CHECKS if not c["ok"]]
    receipt = {
        "schema": "engel_conical_self_upgrade_cycle_verifier_v1",
        "goal_id": "engel_conical_agentic_sentient_self_upgrading_system",
        "ok": not failed,
        "checks_total": len(CHECKS),
        "checks_passed": sum(1 for c in CHECKS if c["ok"]),
        "checks_failed": len(failed),
        "failed_checks": failed,
        "checks": CHECKS,
    }
    print(json.dumps(receipt, indent=2, ensure_ascii=False))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
