#!/usr/bin/env python3
"""Verify the fail-closed Engel primary-goal completion audit."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import engel_primary_goal_completion_audit as audit  # noqa: E402


def _write(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    return path


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    fixture = (
        ROOT
        / "runtime"
        / "temp"
        / f"primary_goal_audit_{Path(__file__).stem}_{id(object())}"
    )
    shutil.rmtree(fixture, ignore_errors=True)
    checks: list[dict] = []

    def record(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"check": name, "ok": bool(ok), "detail": detail})

    try:
        criteria = [f"criterion {index}" for index in range(1, 11)]
        _write(
            fixture / "memory" / "ENGEL_PRIMARY_GOAL_V1.json",
            {
                "goal_id": "engel_conical_agentic_sentient_self_upgrading_system",
                "status": "active",
                "source_of_truth": "CT246 /opt/engel",
                "acceptance_criteria": criteria,
            },
        )
        _write(
            fixture / "memory" / "self_model" / "ENGEL_SELF_MODEL_V1.json",
            {
                "ok": True,
                "introspection": {
                    "completion_claim_allowed_without_current_proof": False,
                },
            },
        )
        _write(
            fixture / "memory" / "reps" / "ENGEL_REPS_RUNTIME_STATE.json",
            {
                "ok": True,
                "scorecard_count_tail": 2,
                "proposal_count_tail": 1,
            },
        )
        _write(
            fixture / "reports" / "self_upgrade" / "issues" / "issue.json",
            {"issue_id": "issue-1"},
        )
        receipt_root = fixture / "reports" / "self_upgrade" / "receipts"
        _write(
            receipt_root
            / "ENGEL_SELF_UPGRADE_DEPLOYMENT_ROLLBACK_AUTOMATION_20260722.json",
            {"ok": True, "rollback_verified": True},
        )
        _write(
            receipt_root / "ENGEL_SELF_UPGRADE_CATALOG_TRAINED_20260726.json",
            {"training": {"recall_proof": "desktop and Discord recall"}},
        )
        _write(
            receipt_root / "ENGEL_DISCORD_DESKTOP_ROUTE_PARITY_20260722.json",
            {
                "ok": True,
                "acceptance": {
                    "desktop_and_discord_share_one_route_ledger": True,
                    "same_identity_guard_applies_to_both": True,
                },
            },
        )
        _write(
            receipt_root
            / "ENGEL_SELF_UPGRADE_MEETING_ROOM_EVENT_STREAM_20260722.json",
            {"ok": True},
        )

        worker_results = []
        for worker_id in sorted(audit.REQUIRED_WORKERS):
            return_path = fixture / "returns" / f"{worker_id}.json"
            return_payload = {"worker_id": worker_id, "returned": True}
            if worker_id == "DESKTOP-UE5A6GG":
                return_payload.update(
                    {
                        "local_llm_completed": True,
                        "worker_engine": "local_llm_one_shot",
                    }
                )
            _write(return_path, return_payload)
            row = {
                "worker_id": worker_id,
                "returned": True,
                "return_path": str(return_path.relative_to(fixture)),
            }
            if worker_id.startswith("android_worker_"):
                row["analysis_engine"] = "on_device_deterministic_conical_v1"
            worker_results.append(row)
        phone_assignments = [
            {"worker_id": item["worker_id"]}
            for item in worker_results
            if item["worker_id"].startswith("android_worker_")
        ]
        conical_path = _write(
            fixture / "reports" / "conical_jobs" / "job.json",
            {
                "ok": True,
                "build_size": "large",
                "expected_worker_count": 4,
                "assignments": phone_assignments,
                "worker_results": worker_results,
            },
        )

        upgraded_stages = []
        for name in (
            "candidate",
            "provenance",
            "quorum",
            "apply",
            "post_deploy_gate",
            "lesson",
        ):
            receipt = _write(
                fixture
                / "reports"
                / "self_upgrade"
                / "stage_receipts"
                / f"{name}.json",
                {"stage": name, "ok": True},
            )
            upgraded_stages.append(
                {
                    "stage": name,
                    "ok": True,
                    "receipt_path": str(receipt.relative_to(fixture)),
                    "receipt_sha256": _hash(receipt),
                }
            )
        _write(
            fixture / "reports" / "self_upgrade" / "cycles" / "upgrade.json",
            {
                "goal_id": "engel_conical_agentic_sentient_self_upgrading_system",
                "cycle_id": "upgrade-cycle",
                "final_status": "upgraded_verified",
                "receipt_chain_sha256": "abc",
                "stages": upgraded_stages,
            },
        )
        order_id = "MAIN-fixture"
        cycle_path = _write(
            fixture / "reports" / "self_upgrade" / "cycles" / "latest.json",
            {
                "goal_id": "engel_conical_agentic_sentient_self_upgrading_system",
                "cycle_id": "review-cycle",
                "final_status": "dry_run_complete",
                "meeting_room_order_id": order_id,
                "stages": [
                    {
                        "stage": "route",
                        "ok": True,
                        "broker_evidence": {
                            "ok": True,
                            "eligible_devices": sorted(audit.REQUIRED_WORKERS),
                            "forbidden_devices": [],
                        },
                    },
                    {
                        "stage": "distributed_work",
                        "ok": True,
                        "receipt_path": str(conical_path.relative_to(fixture)),
                        "meeting_room_order_id": order_id,
                    },
                ],
            },
        )
        cycle_path.touch()
        station_results = [
            "Engel Core: Returned",
            "Android Phone Alpha Agent: Returned",
            "Android Phone Beta Agent: Returned",
            "Android Phone Gamma Agent: Returned",
            "Windows Sub-Engel Agent: Returned",
            "Verifier Agent: Returned",
        ]
        _write(
            fixture
            / "runtime"
            / "meeting_room"
            / "main_ui_orders"
            / f"{order_id}.json",
            {
                "order_id": order_id,
                "source": "Engel Flutter Main Chat",
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "station_results": station_results,
                "authoritative_cycle_completion": {"dispatch_performed": False},
            },
        )
        _write(
            fixture
            / "reports"
            / "engel_standalone_chat_llm"
            / "chat_receipts"
            / "ENGEL_MAIN_SERVER_SELF_UPGRADE_CHAT_REVIEW_fixture.json",
            {
                "provider": "local-ct246-self-upgrade",
                "selected_provider": "ct_self_upgrade_chat_review",
                "assistant_reply": "review-cycle completed; providers were not called",
            },
        )

        complete = audit.build_audit(fixture)
        record(
            "all ten criteria require exact receipt-backed evidence",
            complete.get("complete") is True
            and complete.get("criteria_proven") == 10
            and all(
                item.get("status") == "proven"
                for item in complete.get("checks") or []
            ),
            f"{complete.get('criteria_proven')}/10",
        )
        record(
            "audit is explicitly observe-only",
            "does not dispatch" in str(complete.get("actor_note") or "")
            and "call a provider" in str(complete.get("actor_note") or ""),
        )

        missing_return = fixture / "returns" / "android_worker_beta.json"
        missing_return.unlink()
        failed = audit.build_audit(fixture)
        worker_check = next(
            item for item in failed["checks"] if item["index"] == 4
        )
        record(
            "missing worker return fails closed",
            failed.get("complete") is False
            and worker_check.get("status") == "not_proven"
            and failed.get("criteria_proven") == 8,
            worker_check.get("detail", ""),
        )
        _write(
            missing_return,
            {"worker_id": "android_worker_beta", "returned": True},
        )

        forged = _read(cycle_path)
        forged["stages"][0]["broker_evidence"]["eligible_devices"] = [
            "android_worker_alpha",
            "DESKTOP-FIB17O7",
        ]
        _write(cycle_path, forged)
        cycle_path.touch()
        broker_failed = audit.build_audit(fixture)
        broker_check = next(
            item for item in broker_failed["checks"] if item["index"] == 3
        )
        record(
            "ineligible or forbidden assignment evidence fails closed",
            broker_check.get("status") == "not_proven",
            broker_check.get("detail", ""),
        )

        _write(
            fixture / "memory" / "ENGEL_PRIMARY_GOAL_V1.json",
            {"goal_id": "bad", "acceptance_criteria": ["only one"]},
        )
        malformed = audit.build_audit(fixture)
        record(
            "malformed primary goal cannot be declared complete",
            malformed.get("ok") is False and malformed.get("complete") is False,
            malformed.get("error", ""),
        )
    finally:
        shutil.rmtree(fixture, ignore_errors=True)

    failed_checks = [item for item in checks if not item["ok"]]
    result = {
        "schema": "ENGEL_PRIMARY_GOAL_COMPLETION_AUDIT_VERIFIER_V1",
        "ok": not failed_checks,
        "checks_total": len(checks),
        "checks_passed": len(checks) - len(failed_checks),
        "checks_failed": len(failed_checks),
        "failed_checks": failed_checks,
        "checks": checks,
        "provider_called": False,
        "source_mutation_performed": False,
    }
    print(json.dumps(result, indent=2))
    return 1 if failed_checks else 0


if __name__ == "__main__":
    raise SystemExit(main())
