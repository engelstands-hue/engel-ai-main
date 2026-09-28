#!/usr/bin/env python3
"""Engel Conical Self-Upgrade Cycle — the ONE governed flow for self-patching.

Serves the Conical Agentic Sentient Self Upgrading System primary goal
(memory/ENGEL_PRIMARY_GOAL_V1.json). Before this module, every change-control
stage existed as a separately hand-invoked primitive and the two strongest
gates (the multi-member self-patch quorum and the post-deploy rollback
automation) were called by NOTHING. This module drives one failure or owner
request through the whole loop as a single fail-closed cycle:

    intake   -> engel_self_upgrade_system.build_issue / write_issue
    route    -> route_issue (+ device-broker eligibility recorded as evidence)
    workers  -> visible Meeting Room order + exact Alpha/Beta/Gamma/Sub returns
    candidate-> build_patch_candidate + build_file_patch (provenance)
    quorum   -> engel_self_patch_quorum.evaluate_and_record  [AUTHORITATIVE
                pre-apply gate: 5 members, any veto blocks; runs verifiers]
    gate     -> legacy gate_candidate receipt (apply-lane schema requirement)
    apply    -> apply_candidate_patch (hash-checked backups)  [execute only]
    post-gate-> engel_deployment_rollback_automation.run_post_deploy_gate
                [verifiers re-run against the LIVE tree; failure auto-restores]
    lesson   -> build_memory_candidate_from_gate (candidate-only memory)
    receipt  -> ONE chained cycle receipt binding every stage receipt by sha256

Ordering is ENFORCED, not documented: apply never runs unless the quorum
decision in THIS cycle authorized it. Every stage failure halts the cycle with
an honest partial receipt (final_status blocked_at_*/failed_at_*). The cycle
    requires real bounded worker review, writes no trusted memory, and claims
    nothing without the underlying stage receipt.

Default mode is DRY-RUN: distributed work, candidate construction, and the
quorum are receipted, but no source is written. Execute mode additionally
requires three explicit human tokens (APPROVE_FIX_CANDIDATE plus the
risk-matched gate/apply pair) - no autonomous path can reach apply.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT), str(ROOT / "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import engel_self_upgrade_system as system  # noqa: E402
import engel_self_patch_quorum as quorum  # noqa: E402
import engel_prompt_patch_provenance as provenance  # noqa: E402
from engel_deployment_rollback_automation import run_post_deploy_gate  # noqa: E402

CYCLE_DIR = system.REPORT_ROOT / "cycles"
GOAL_ID = "engel_conical_agentic_sentient_self_upgrading_system"
REQUEST_REQUIRED_FIELDS = (
    "source", "symptom", "severity", "affected_surface",
    "diagnosis", "patch_plan", "files_to_change", "operations", "lesson",
)
CONICAL_REQUIRED_WORKERS = (
    "android_worker_alpha",
    "android_worker_beta",
    "android_worker_gamma",
    "DESKTOP-UE5A6GG",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_path(path: Path) -> str:
    return system.sha256_file(path)


def _stage(name: str, ok: bool, detail: str, receipt_path: "Path | None" = None,
           extra: "dict[str, Any] | None" = None) -> "dict[str, Any]":
    entry: dict[str, Any] = {"stage": name, "ok": bool(ok), "detail": detail}
    if receipt_path is not None:
        entry["receipt_path"] = system.project_relative(receipt_path)
        entry["receipt_sha256"] = _sha256_path(receipt_path)
    if extra:
        entry.update(extra)
    return entry


def _projected_contents(operations: "list[dict[str, Any]]") -> "tuple[dict[str, str], dict[str, str]]":
    """Replay replace_text operations in memory (byte-faithful, same rule as
    the apply lane: old_text must occur exactly once). Returns
    (before_contents, after_contents) so the quorum can judge what the patch
    INTRODUCES rather than what the file already contained."""
    before: dict[str, str] = {}
    projected: dict[str, str] = {}
    for op in operations:
        target = system.project_path_from_relative(str(op["file"]))
        rel = system.project_relative(target)
        if rel not in projected:
            before[rel] = target.read_bytes().decode("utf-8")
            projected[rel] = before[rel]
        old_text = str(op["old_text"])
        if projected[rel].count(old_text) != 1:
            raise system.SelfUpgradeError(f"old_text must occur exactly once in {rel}")
        projected[rel] = projected[rel].replace(old_text, str(op["new_text"]), 1)
    return before, projected


def _quorum_candidate(candidate: "dict[str, Any]", operations: "list[dict[str, Any]]",
                      actor: str) -> "dict[str, Any]":
    """Adapt a patch candidate + operations into the quorum's candidate shape.
    source_mutation is ALWAYS True here: this cycle exists to mutate source, so
    the human-approval member must always demand the fix token."""
    before, projected = _projected_contents(operations)
    diff_lines = []
    for op in operations:
        diff_lines.append(f"--- {op['file']}")
        diff_lines.append(f"-{op['old_text']}")
        diff_lines.append(f"+{op['new_text']}")
    return {
        "candidate_id": candidate["candidate_id"],
        "actor": actor,
        "source_mutation": True,
        "human_approval_required": True,
        "required_verifiers": list(candidate.get("required_verifiers", [])),
        "changed_files": [
            {"target_file": rel, "after_content": text,
             "before_content": before.get(rel, "")}
            for rel, text in projected.items()
        ],
        "patch_content": "\n".join(diff_lines),
    }


def _broker_evidence(route: "dict[str, Any]") -> "dict[str, Any]":
    """Record device-broker eligibility for the route's supporting workers.
    The following stage performs the required dispatch. A broker error is
    recorded honestly and never fabricated."""
    try:
        import engel_device_broker as broker

        decision = broker.broker_decision()
        supporting = [str(w) for w in route.get("supporting_workers", [])]
        devices = (
            decision.get("candidates")
            if isinstance(decision.get("candidates"), list)
            else (
                decision.get("devices")
                if isinstance(decision.get("devices"), list)
                else []
            )
        )
        return {
            "ok": True,
            "eligible_devices": [d.get("device_id") for d in devices if d.get("eligible")],
            "forbidden_devices": [d.get("device_id") for d in devices if not d.get("allowed", True)],
            "supporting_workers_declared": supporting,
            "note": "broker decision recorded before required distributed dispatch",
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:200]}


def _require_conical_workers(route: "dict[str, Any]") -> "dict[str, Any]":
    """Make the self-upgrade route match the four-worker goal."""
    workers = [str(value) for value in route.get("supporting_workers", []) if str(value)]
    for worker_id in CONICAL_REQUIRED_WORKERS:
        if worker_id not in workers:
            workers.append(worker_id)
    route["supporting_workers"] = workers
    route["equipment_target"] = "ct246_plus_full_conical_cluster"
    card = route.get("meeting_room_card")
    if isinstance(card, dict):
        card["supporting_workers"] = list(workers)
    route["distributed_work_required"] = True
    route["required_worker_ids"] = list(CONICAL_REQUIRED_WORKERS)
    return route


def _operation_review_manifest(request: "dict[str, Any]") -> "list[dict[str, Any]]":
    """Bound the worker prompt while preserving exact operation identities."""
    manifest: list[dict[str, Any]] = []
    operations = request.get("operations")
    if not isinstance(operations, list):
        return manifest
    for index, operation in enumerate(operations, start=1):
        if not isinstance(operation, dict):
            continue
        old_text = str(operation.get("old_text") or "")
        new_text = str(operation.get("new_text") or "")
        manifest.append(
            {
                "index": index,
                "op": str(operation.get("op") or ""),
                "file": str(operation.get("file") or ""),
                "old_chars": len(old_text),
                "new_chars": len(new_text),
                "old_sha256": hashlib.sha256(old_text.encode("utf-8")).hexdigest(),
                "new_sha256": hashlib.sha256(new_text.encode("utf-8")).hexdigest(),
            }
        )
    return manifest


def _default_distributed_review(
    issue: "dict[str, Any]",
    route: "dict[str, Any]",
    request: "dict[str, Any]",
) -> "dict[str, Any]":
    """Use the same real dispatcher used by Engel's UI build lane."""
    import run_engel_ui_chat_meeting_room_llm as ui_orchestrator

    operation_manifest = _operation_review_manifest(request)
    prompt = (
        "Build a large review tool output for this bounded self-upgrade candidate; "
        "do not mutate source or trusted memory. Review the diagnosis, patch "
        "plan, operation manifest, verifier coverage, rollback risks, and user "
        "impact for Engel AI Main. "
        f"Issue: {issue.get('symptom')}. "
        f"Surface: {issue.get('affected_surface')}. "
        f"Diagnosis: {request.get('diagnosis')}. "
        f"Patch plan: {request.get('patch_plan')}. "
        f"Files: {json.dumps(request.get('files_to_change') or [])}. "
        f"Operation manifest: {json.dumps(operation_manifest)}. "
        "The authoritative candidate and provenance ledger retain the full "
        "old and new source text."
    )
    result = ui_orchestrator._run_conical_build_orchestration(prompt)
    if not isinstance(result, dict) or not result:
        raise system.SelfUpgradeError("distributed review dispatcher returned no receipt")
    return result


def _validate_distributed_review(review: "dict[str, Any]") -> Path:
    if review.get("schema") != "engel_conical_build_orchestration_v1":
        raise system.SelfUpgradeError("distributed review schema mismatch")
    results = review.get("worker_results")
    if not isinstance(results, list):
        raise system.SelfUpgradeError("distributed review has no worker results")
    by_worker = {
        str(item.get("worker_id") or ""): item
        for item in results
        if isinstance(item, dict) and item.get("worker_id")
    }
    missing = [worker_id for worker_id in CONICAL_REQUIRED_WORKERS if worker_id not in by_worker]
    failed = [
        worker_id
        for worker_id in CONICAL_REQUIRED_WORKERS
        if worker_id in by_worker and by_worker[worker_id].get("returned") is not True
    ]
    if missing or failed:
        raise system.SelfUpgradeError(
            f"distributed review incomplete; missing={missing} failed={failed}"
        )
    if review.get("ok") is not True:
        raise system.SelfUpgradeError("distributed review did not pass its exact-return gate")
    if int(review.get("expected_worker_count") or 0) != len(CONICAL_REQUIRED_WORKERS):
        raise system.SelfUpgradeError("distributed review expected-worker count mismatch")
    if int(review.get("returned_worker_count") or 0) != len(CONICAL_REQUIRED_WORKERS):
        raise system.SelfUpgradeError("distributed review returned-worker count mismatch")
    receipt_raw = str(review.get("receipt_path") or "")
    if not receipt_raw:
        raise system.SelfUpgradeError("distributed review receipt path missing")
    receipt_path = Path(receipt_raw)
    if not receipt_path.is_absolute():
        receipt_path = system.ROOT / receipt_path
    receipt_path = receipt_path.resolve(strict=False)
    if not system.is_relative_to(receipt_path, system.ROOT):
        raise system.SelfUpgradeError("distributed review receipt escaped Engel root")
    if not receipt_path.is_file():
        raise system.SelfUpgradeError("distributed review receipt file missing")
    return receipt_path


def _chain_sha256(stages: "list[dict[str, Any]]") -> str:
    chained = "|".join(
        f"{s['stage']}:{s.get('receipt_sha256', 'none')}" for s in stages
    )
    return hashlib.sha256(chained.encode("utf-8")).hexdigest()


def _complete_meeting_room_order(
    cycle: "dict[str, Any]",
    final_status: str,
) -> "dict[str, Any]":
    """Close the visible Meeting Room order with the cycle's authoritative outcome."""
    order_id = str(cycle.get("meeting_room_order_id") or "").strip()
    if not order_id:
        return {
            "ok": True,
            "accepted": True,
            "skipped": True,
            "reason": "cycle did not create a Meeting Room server order",
        }
    distributed = next(
        (
            stage
            for stage in cycle.get("stages", [])
            if isinstance(stage, dict) and stage.get("stage") == "distributed_work"
        ),
        {},
    )
    returned = int(distributed.get("returned_worker_count") or 0)
    summary = (
        f"Conical self-upgrade cycle {cycle.get('cycle_id')} finished as "
        f"{final_status}; distributed worker returns "
        f"{returned}/{len(CONICAL_REQUIRED_WORKERS)}."
    )
    from engel_agent_meeting_room import complete_order_from_engel_main_ui

    worker_results = cycle.get("_authoritative_worker_results")
    if not isinstance(worker_results, list):
        worker_results = []
    result = complete_order_from_engel_main_ui(
        order_id,
        summary,
        source="Engel conical self-upgrade cycle",
        authoritative_worker_results=worker_results,
        authoritative_final_status=final_status,
    )
    if not isinstance(result, dict):
        raise system.SelfUpgradeError(
            "Meeting Room completion returned a non-object response"
        )
    return result


def _finish(cycle: "dict[str, Any]", final_status: str) -> "dict[str, Any]":
    cycle["final_status"] = final_status
    cycle["finished_at_utc"] = _now()
    order_id = str(cycle.get("meeting_room_order_id") or "").strip()
    if order_id:
        try:
            completion = _complete_meeting_room_order(cycle, final_status)
            accepted = completion.get("accepted") is True
            cycle["meeting_room_completion"] = completion
            cycle["stages"].append(
                _stage(
                    "meeting_room_visibility",
                    accepted,
                    (
                        f"order {order_id} completed with {final_status}"
                        if accepted
                        else f"order {order_id} rejected terminal status {final_status}"
                    ),
                    extra={
                        "meeting_room_order_id": order_id,
                        "meeting_room_server_used": completion.get(
                            "meeting_room_server_used"
                        )
                        is True,
                    },
                )
            )
            if not accepted and final_status in {
                "dry_run_complete",
                "upgraded_verified",
                "applied_then_rolled_back",
            }:
                cycle["pre_visibility_final_status"] = final_status
                cycle["final_status"] = "failed_at_meeting_room_visibility"
        except Exception as exc:
            cycle["meeting_room_completion"] = {
                "ok": False,
                "accepted": False,
                "error": str(exc)[:300],
            }
            cycle["stages"].append(
                _stage(
                    "meeting_room_visibility",
                    False,
                    f"order {order_id} completion failed: {exc}",
                    extra={"meeting_room_order_id": order_id},
                )
            )
            if final_status in {
                "dry_run_complete",
                "upgraded_verified",
                "applied_then_rolled_back",
            }:
                cycle["pre_visibility_final_status"] = final_status
                cycle["final_status"] = "failed_at_meeting_room_visibility"
    cycle.pop("_authoritative_worker_results", None)
    cycle["receipt_chain_sha256"] = _chain_sha256(cycle["stages"])
    CYCLE_DIR.mkdir(parents=True, exist_ok=True)
    out = CYCLE_DIR / f"{system.safe_slug(cycle['cycle_id'])}.json"
    out.write_text(json.dumps(cycle, indent=2, ensure_ascii=False), encoding="utf-8")
    cycle["cycle_receipt_path"] = system.project_relative(out)
    return cycle


def run_cycle(request: "dict[str, Any]", *, dry_run: bool = True,
              actor: str = "owner_joshua", fix_approval_token: str = "",
              gate_token: str = "", apply_token: str = "",
              distributed_review_fn: "Callable[[dict[str, Any], dict[str, Any], dict[str, Any]], dict[str, Any]] | None" = None,
              ) -> "dict[str, Any]":
    """Drive one self-upgrade request through the whole governed loop."""
    started = _now()
    cycle: dict[str, Any] = {
        "schema": "ENGEL_CONICAL_SELF_UPGRADE_CYCLE_V1",
        "goal_id": GOAL_ID,
        "cycle_id": "engel_cycle_" + system.short_hash(f"{request.get('symptom', '')}|{started}"),
        "started_at_utc": started,
        "mode": "dry_run" if dry_run else "execute",
        "actor": actor,
        "gate_ordering_enforced": (
            "distributed_work -> candidate -> provenance -> quorum -> legacy_gate -> "
            "apply -> post_deploy_gate -> lesson"
        ),
        "stages": [],
        "actor_note": "cycle requires exact bounded worker returns; no trusted-memory "
                      "write and no claim without the underlying stage receipt",
    }
    stages: list[dict[str, Any]] = cycle["stages"]

    missing = [f for f in REQUEST_REQUIRED_FIELDS if not request.get(f)]
    if missing:
        stages.append(_stage("intake", False, f"request missing fields: {missing}"))
        return _finish(cycle, "failed_at_intake")

    # ---- intake: real failure/request -> issue --------------------------------
    try:
        issue = system.build_issue(
            source=str(request["source"]), symptom=str(request["symptom"]),
            severity=str(request["severity"]), affected_surface=str(request["affected_surface"]),
            evidence_paths=list(request.get("evidence_paths") or []),
        )
        issue_path = system.write_issue(issue)
        stages.append(_stage("intake", True, f"issue {issue['issue_id']} filed", issue_path))
    except Exception as exc:
        stages.append(_stage("intake", False, f"issue build failed: {exc}"))
        return _finish(cycle, "failed_at_intake")

    # ---- route: matrix owner/workers/verifiers + broker evidence --------------
    try:
        route = _require_conical_workers(system.route_issue(issue))
        route_path = system.write_route(route)
        stages.append(_stage("route", True,
                             f"routed to {route['owner']} risk={route['risk_level']}",
                             route_path, {"broker_evidence": _broker_evidence(route)}))
    except Exception as exc:
        stages.append(_stage("route", False, f"route failed: {exc}"))
        return _finish(cycle, "failed_at_route")

    # ---- distributed work: visible order + exact four-worker return gate -----
    distributed_review: dict[str, Any] = {}
    try:
        work_order = system.build_meeting_room_work_order(issue, route)
        work_order_paths = system.write_meeting_room_work_order(work_order)
        dispatcher = distributed_review_fn or _default_distributed_review
        distributed_review = dispatcher(issue, route, request)
        cycle["_authoritative_worker_results"] = [
            dict(item)
            for item in distributed_review.get("worker_results", [])
            if isinstance(item, dict)
        ]
        cycle["meeting_room_order_id"] = str(
            distributed_review.get("meeting_room_order_id") or ""
        )
        distributed_receipt_path = _validate_distributed_review(distributed_review)
        stages.append(
            _stage(
                "distributed_work",
                True,
                "Alpha, Beta, Gamma, and Sub-Engel returned exact bounded review receipts",
                distributed_receipt_path,
                {
                    "work_order_paths": [
                        system.project_relative(path) for path in work_order_paths
                    ],
                    "work_order_sha256": [
                        _sha256_path(path) for path in work_order_paths
                    ],
                    "required_worker_ids": list(CONICAL_REQUIRED_WORKERS),
                    "returned_worker_count": len(CONICAL_REQUIRED_WORKERS),
                    "meeting_room_order_id": distributed_review.get(
                        "meeting_room_order_id", ""
                    ),
                },
            )
        )
    except Exception as exc:
        distributed_failure_path: Path | None = None
        review_path_text = str(distributed_review.get("receipt_path") or "").strip()
        if review_path_text:
            candidate_path = Path(review_path_text)
            if candidate_path.is_file():
                distributed_failure_path = candidate_path
        failure_extra: dict[str, Any] = {
            "required_worker_ids": list(CONICAL_REQUIRED_WORKERS),
            "distributed_review_job_id": str(
                distributed_review.get("job_id") or ""
            ),
            "returned_worker_count": int(
                distributed_review.get("returned_worker_count") or 0
            ),
        }
        if distributed_failure_path is not None:
            failure_extra.update(
                {
                    "distributed_review_receipt": system.project_relative(
                        distributed_failure_path
                    ),
                    "distributed_review_sha256": _sha256_path(
                        distributed_failure_path
                    ),
                }
            )
        stages.append(
            _stage(
                "distributed_work",
                False,
                f"required distributed review failed closed: {exc}",
                distributed_failure_path,
                extra=failure_extra,
            )
        )
        return _finish(cycle, "blocked_at_distributed_work")

    # ---- candidate: provenance-carrying patch candidate + file patch ----------
    try:
        candidate = system.build_patch_candidate(
            issue, route,
            diagnosis=str(request["diagnosis"]),
            files_to_change=list(request["files_to_change"]),
            patch_plan=str(request["patch_plan"]),
        )
        extra = [str(v) for v in (request.get("extra_required_verifiers") or [])]
        for verifier in extra:
            if verifier not in candidate["required_verifiers"]:
                candidate["required_verifiers"].append(verifier)
        candidate["distributed_review_receipt"] = system.project_relative(
            distributed_receipt_path
        )
        candidate["distributed_review_sha256"] = _sha256_path(
            distributed_receipt_path
        )
        candidate["distributed_review_worker_ids"] = list(
            CONICAL_REQUIRED_WORKERS
        )
        candidate_path = system.write_patch_candidate(candidate)
        patch = system.build_file_patch(candidate, operations=list(request["operations"]))
        patch_path = system.write_file_patch(patch, candidate)
        stages.append(_stage("candidate", True,
                             f"candidate {candidate['candidate_id']} risk={candidate['risk_level']} "
                             f"verifiers={len(candidate['required_verifiers'])}",
                             candidate_path,
                             {"patch_path": system.project_relative(patch_path),
                              "patch_sha256": _sha256_path(patch_path)}))
    except Exception as exc:
        stages.append(_stage("candidate", False, f"candidate build failed: {exc}"))
        return _finish(cycle, "failed_at_candidate")

    # ---- provenance: immutable prompt -> worker review -> candidate -> patch --
    try:
        provenance_root = system.REPORT_ROOT / "provenance"
        provenance_record = provenance.record_cycle_provenance(
            cycle_id=cycle["cycle_id"],
            actor=actor,
            request=request,
            issue_path=issue_path,
            distributed_review_path=distributed_receipt_path,
            candidate_path=candidate_path,
            patch_path=patch_path,
            candidate=candidate,
            operations=list(patch["operations"]),
            root=system.ROOT,
            ledger_path=provenance_root / "prompt_patch_ledger.jsonl",
            entry_root=provenance_root / "entries",
        )
        provenance_path = Path(str(provenance_record["receipt_path"]))
        stages.append(
            _stage(
                "provenance",
                True,
                f"prompt and patch bound by {provenance_record['provenance_id']}",
                provenance_path,
                {
                    "provenance_id": provenance_record["provenance_id"],
                    "entry_sha256": provenance_record["entry_sha256"],
                    "previous_entry_sha256": provenance_record[
                        "previous_entry_sha256"
                    ],
                    "request_sha256": provenance_record["request_sha256"],
                    "ledger_path": system.project_relative(
                        provenance_root / "prompt_patch_ledger.jsonl"
                    ),
                },
            )
        )
    except Exception as exc:
        stages.append(
            _stage(
                "provenance",
                False,
                f"prompt-to-patch provenance failed closed: {exc}",
            )
        )
        return _finish(cycle, "failed_at_provenance")

    # ---- quorum: the AUTHORITATIVE multi-member pre-apply gate ----------------
    try:
        qcand = _quorum_candidate(candidate, patch["operations"], actor)
        decision = quorum.evaluate_and_record(qcand, approval_token=fix_approval_token)
        q_ok = decision.get("apply_allowed") is True
        receipt_rel = decision.get("gate_receipt")
        q_path = system.project_path_from_relative(receipt_rel) if receipt_rel else None
        stages.append(_stage("quorum", q_ok,
                             decision.get("decision", "unknown")
                             + (f" (vetoed_by={decision['vetoed_by']})" if decision.get("vetoed_by") else ""),
                             q_path,
                             {"allow_votes": decision.get("allow_votes"),
                              "member_count": decision.get("member_count")}))
        # A dry review must record the real apply quorum result without
        # pretending that it authorizes mutation. Missing apply approval is a
        # valid review outcome; it blocks only an executing cycle.
        if not q_ok and not dry_run:
            return _finish(cycle, "blocked_at_quorum")
    except Exception as exc:
        stages.append(_stage("quorum", False, f"quorum error (fail-closed): {exc}"))
        return _finish(cycle, "failed_at_quorum")

    # ---- legacy gate: apply-lane schema requirement ---------------------------
    # Its verifier_results input is RESULT evidence under reports/, and the
    # quorum decision receipt (which embeds every verifier run) is exactly that.
    try:
        verifier_evidence = [receipt_rel] if receipt_rel else []
        gate_receipt = system.gate_candidate(
            candidate, verifier_results=verifier_evidence,
            approval_token=gate_token,
        )
        gate_path = system.write_gate_receipt(gate_receipt)
        gate_ok = gate_receipt.get("apply_allowed") is True
        stages.append(_stage("legacy_gate", gate_ok, gate_receipt.get("reason", ""), gate_path))
        if dry_run:
            return _finish(cycle, "dry_run_complete")
        if not gate_ok:
            return _finish(cycle, "blocked_at_legacy_gate")
    except Exception as exc:
        stages.append(_stage("legacy_gate", False, f"gate failed: {exc}"))
        return _finish(cycle, "failed_at_legacy_gate")

    # ---- apply: hash-checked backups; only reachable with BOTH gates green ----
    try:
        apply_receipt = system.apply_candidate_patch(
            candidate, gate_receipt, patch, approval_token=apply_token,
        )
        # The post-deploy gate reads required_verifiers from the APPLY receipt;
        # apply_candidate_patch does not carry them, so the cycle injects them.
        apply_receipt["required_verifiers"] = list(candidate["required_verifiers"])
        apply_path = system.write_apply_receipt(apply_receipt)
        applied = apply_receipt.get("status") == "applied"
        stages.append(_stage("apply", applied,
                             f"status={apply_receipt.get('status')}", apply_path,
                             {"changed_file_count": len(apply_receipt.get("changed_files") or [])}))
        if not applied:
            return _finish(cycle, "failed_at_apply")
    except Exception as exc:
        stages.append(_stage("apply", False, f"apply failed: {exc}"))
        return _finish(cycle, "failed_at_apply")

    # ---- post-deploy gate: verifiers vs the LIVE tree; auto-restore on fail ---
    try:
        gate_result = run_post_deploy_gate(system.project_relative(apply_path))
        proof_rel = gate_result.get("proof_receipt")
        proof_path = system.project_path_from_relative(proof_rel) if proof_rel else None
        committed = gate_result.get("decision") == "committed"
        stages.append(_stage("post_deploy_gate", bool(gate_result.get("ok")),
                             f"decision={gate_result.get('decision')}", proof_path,
                             {"verifiers_all_passed": gate_result.get("verifiers_all_passed"),
                              "rollback_performed": gate_result.get("rollback_performed")}))
    except Exception as exc:
        stages.append(_stage("post_deploy_gate", False, f"post-deploy gate error: {exc}"))
        return _finish(cycle, "failed_at_post_deploy_gate")

    # ---- lesson: preserved as CANDIDATE memory (promotion is a separate,     --
    # ---- separately-tokened human chain — never this cycle)                  --
    try:
        outcome = "verified and committed" if committed else \
                  f"rolled back by post-deploy gate ({gate_result.get('reason', 'verifier failure')})"
        lesson_text = f"{request['lesson']} Outcome: {outcome}."
        memory_candidate = system.build_memory_candidate_from_gate(gate_receipt, lesson=lesson_text)
        memory_path = system.write_memory_candidate(memory_candidate)
        stages.append(_stage("lesson", True, "candidate lesson preserved (promotion requires "
                             "the separate memory chain)", memory_path))
    except Exception as exc:
        stages.append(_stage("lesson", False, f"lesson preservation failed: {exc}"))

    if committed:
        return _finish(cycle, "upgraded_verified")
    if gate_result.get("decision") == "rolled_back":
        return _finish(cycle, "applied_then_rolled_back")
    return _finish(cycle, "rollback_incomplete_manual_required")


def _cli(argv: "list[str] | None" = None) -> int:
    import argparse

    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    parser = argparse.ArgumentParser(
        description="Engel conical self-upgrade cycle (one governed issue->lesson flow)")
    parser.add_argument("--request", required=True, help="path to a cycle request JSON")
    parser.add_argument("--execute", action="store_true",
                        help="apply for real (default is dry-run through the quorum)")
    parser.add_argument("--actor", default="owner_joshua")
    parser.add_argument("--fix-approval-token", default="", help="APPROVE_FIX_CANDIDATE when human-approved")
    parser.add_argument("--gate-token", default="", help="risk-matched gate token")
    parser.add_argument("--apply-token", default="", help="risk-matched apply token")
    args = parser.parse_args(argv)
    request = json.loads(Path(args.request).read_text(encoding="utf-8"))
    result = run_cycle(
        request, dry_run=not args.execute, actor=args.actor,
        fix_approval_token=args.fix_approval_token,
        gate_token=args.gate_token, apply_token=args.apply_token,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["final_status"] in {"dry_run_complete", "upgraded_verified",
                                           "applied_then_rolled_back"} else 1


if __name__ == "__main__":
    raise SystemExit(_cli())
