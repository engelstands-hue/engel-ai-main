#!/usr/bin/env python3
"""Fail-closed completion audit for Engel AI Main's primary system goal."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
GOAL_PATH = ROOT / "memory" / "ENGEL_PRIMARY_GOAL_V1.json"
REPORT_ROOT = ROOT / "reports" / "self_upgrade"
OUTPUT_ROOT = REPORT_ROOT / "goal_completion"
LATEST_PATH = OUTPUT_ROOT / "latest.json"
REQUIRED_WORKERS = {
    "android_worker_alpha",
    "android_worker_beta",
    "android_worker_gamma",
    "DESKTOP-UE5A6GG",
}
SUCCESSFUL_CYCLE_STATUSES = {
    "dry_run_complete",
    "upgraded_verified",
    "applied_then_rolled_back",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _relative(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(path)


def _newest_json(
    directory: Path,
    pattern: str = "*.json",
    *,
    predicate: Callable[[dict[str, Any]], bool] | None = None,
) -> tuple[Path | None, dict[str, Any]]:
    if not directory.is_dir():
        return None, {}
    for path in sorted(
        directory.glob(pattern),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    ):
        payload = _read_json(path)
        if payload and (predicate is None or predicate(payload)):
            return path, payload
    return None, {}


def _stage(cycle: dict[str, Any], name: str) -> dict[str, Any]:
    for item in cycle.get("stages") or []:
        if isinstance(item, dict) and item.get("stage") == name:
            return item
    return {}


def _bound_path(root: Path, value: Any) -> Path | None:
    text = str(value or "").strip().replace("\\", "/")
    if not text:
        return None
    candidate = Path(text)
    if not candidate.is_absolute():
        candidate = root / candidate
    try:
        candidate.resolve().relative_to(root.resolve())
    except ValueError:
        return None
    return candidate


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _receipt_matches(stage: dict[str, Any], root: Path) -> bool:
    path = _bound_path(root, stage.get("receipt_path"))
    expected = str(stage.get("receipt_sha256") or "").lower()
    return bool(path and path.is_file() and expected and _sha256(path) == expected)


def _evidence(path: Path | None, root: Path) -> str:
    return _relative(path, root) if path and path.is_file() else ""


def _criterion(
    index: int,
    text: str,
    ok: bool,
    detail: str,
    paths: list[str],
) -> dict[str, Any]:
    return {
        "index": index,
        "criterion": text,
        "ok": bool(ok),
        "status": "proven" if ok else "not_proven",
        "detail": detail,
        "evidence_paths": [path for path in paths if path],
    }


def build_audit(root: Path = ROOT) -> dict[str, Any]:
    goal_path = root / "memory" / "ENGEL_PRIMARY_GOAL_V1.json"
    report_root = root / "reports" / "self_upgrade"
    goal = _read_json(goal_path)
    criteria = goal.get("acceptance_criteria")
    if not isinstance(criteria, list) or len(criteria) != 10:
        return {
            "schema": "ENGEL_PRIMARY_GOAL_COMPLETION_AUDIT_V1",
            "ok": False,
            "complete": False,
            "error": "primary goal must contain exactly ten acceptance criteria",
            "goal_path": _relative(goal_path, root),
            "generated_at_utc": _now(),
        }

    cycle_path, cycle = _newest_json(
        report_root / "cycles",
        predicate=lambda item: (
            item.get("goal_id") == goal.get("goal_id")
            and item.get("final_status") in SUCCESSFUL_CYCLE_STATUSES
        ),
    )
    distributed = _stage(cycle, "distributed_work")
    conical_path = _bound_path(root, distributed.get("receipt_path"))
    conical = _read_json(conical_path) if conical_path else {}
    order_id = str(
        cycle.get("meeting_room_order_id")
        or distributed.get("meeting_room_order_id")
        or ""
    )
    room_path = (
        root / "runtime" / "meeting_room" / "main_ui_orders" / f"{order_id}.json"
    )
    room = _read_json(room_path)

    chat_path, chat = _newest_json(
        root / "reports" / "engel_standalone_chat_llm" / "chat_receipts",
        "ENGEL_MAIN_SERVER_SELF_UPGRADE_CHAT_REVIEW_*.json",
        predicate=lambda item: str(cycle.get("cycle_id") or "") in json.dumps(item),
    )
    worker_results = [
        item
        for item in (conical.get("worker_results") or [])
        if isinstance(item, dict)
    ]
    returned_ids = {
        str(item.get("worker_id") or "")
        for item in worker_results
        if item.get("returned") is True
    }
    worker_paths = [
        _bound_path(root, item.get("return_path")) for item in worker_results
    ]
    sub_return_path = next(
        (
            _bound_path(root, item.get("return_path"))
            for item in worker_results
            if item.get("worker_id") == "DESKTOP-UE5A6GG"
        ),
        None,
    )
    sub_return = _read_json(sub_return_path) if sub_return_path else {}
    exact_worker_receipts = (
        returned_ids == REQUIRED_WORKERS
        and len(worker_results) == 4
        and all(path is not None and path.is_file() for path in worker_paths)
    )
    station_results = set(str(item) for item in (room.get("station_results") or []))
    expected_station_results = {
        "Engel Core: Returned",
        "Android Phone Alpha Agent: Returned",
        "Android Phone Beta Agent: Returned",
        "Android Phone Gamma Agent: Returned",
        "Windows Sub-Engel Agent: Returned",
        "Verifier Agent: Returned",
    }

    route_stage = _stage(cycle, "route")
    broker_stage = (
        route_stage.get("broker_evidence")
        if isinstance(route_stage.get("broker_evidence"), dict)
        else {}
    )
    eligible = set(str(item) for item in (broker_stage.get("eligible_devices") or []))
    assigned = {
        str(item.get("worker_id") or item.get("device_id") or "")
        for item in (conical.get("assignments") or [])
        if isinstance(item, dict)
    }
    if not assigned:
        assigned = returned_ids

    self_model_path = root / "memory" / "self_model" / "ENGEL_SELF_MODEL_V1.json"
    self_model = _read_json(self_model_path)
    reps_state_path = root / "memory" / "reps" / "ENGEL_REPS_RUNTIME_STATE.json"
    reps_state = _read_json(reps_state_path)
    issue_path, issue = _newest_json(report_root / "issues")

    upgraded_path, upgraded = _newest_json(
        report_root / "cycles",
        predicate=lambda item: item.get("final_status") == "upgraded_verified",
    )
    upgraded_required = {
        "candidate",
        "provenance",
        "quorum",
        "apply",
        "post_deploy_gate",
        "lesson",
    }
    upgraded_stages = {
        str(item.get("stage")): item
        for item in (upgraded.get("stages") or [])
        if isinstance(item, dict)
    }
    upgraded_chain_ok = bool(
        upgraded
        and upgraded_required.issubset(upgraded_stages)
        and all(upgraded_stages[name].get("ok") is True for name in upgraded_required)
        and all(_receipt_matches(upgraded_stages[name], root) for name in upgraded_required)
        and str(upgraded.get("receipt_chain_sha256") or "")
    )

    rollback_receipt_path = (
        report_root
        / "receipts"
        / "ENGEL_SELF_UPGRADE_DEPLOYMENT_ROLLBACK_AUTOMATION_20260722.json"
    )
    rollback_receipt = _read_json(rollback_receipt_path)
    rollback_source_sync = (
        rollback_receipt.get("source_sync_proof")
        if isinstance(rollback_receipt.get("source_sync_proof"), dict)
        else {}
    )
    rollback_verifier = (
        rollback_receipt.get("verifier")
        if isinstance(rollback_receipt.get("verifier"), dict)
        else {}
    )
    rollback_proven = bool(
        (
            rollback_receipt.get("ok") is True
            and (
                rollback_receipt.get("rollback_verified") is True
                or "rollback" in json.dumps(rollback_receipt).lower()
            )
        )
        or (
            rollback_receipt.get("status") == "deployed_verified"
            and rollback_source_sync.get("rog_ct246_hashes_match") is True
            and rollback_source_sync.get("ct246_verifier") == "PASS"
            and rollback_verifier.get("ok") is True
            and int(rollback_verifier.get("checks_passed") or 0)
            == int(rollback_verifier.get("checks_total") or -1)
        )
    )
    scorecard_count = int(
        reps_state.get("scorecard_count_tail")
        or reps_state.get("evaluation_count_tail")
        or 0
    )

    teaching_path = (
        report_root
        / "receipts"
        / "ENGEL_SELF_UPGRADE_CATALOG_TRAINED_20260726.json"
    )
    teaching = _read_json(teaching_path)
    parity_path = (
        report_root
        / "receipts"
        / "ENGEL_DISCORD_DESKTOP_ROUTE_PARITY_20260722.json"
    )
    parity = _read_json(parity_path)
    parity_acceptance = (
        parity.get("acceptance")
        if isinstance(parity.get("acceptance"), dict)
        else {}
    )
    recall_proven = bool(
        teaching.get("training", {}).get("recall_proof")
        and parity.get("ok") is True
        and parity_acceptance.get("desktop_and_discord_share_one_route_ledger")
        is True
        and parity_acceptance.get("same_identity_guard_applies_to_both") is True
        and reps_state.get("ok") is True
    )

    claim_verifier_path = (
        report_root
        / "receipts"
        / "ENGEL_SELF_UPGRADE_MEETING_ROOM_EVENT_STREAM_20260722.json"
    )
    claim_verifier = _read_json(claim_verifier_path)
    claim_source_sync = (
        claim_verifier.get("source_sync_proof")
        if isinstance(claim_verifier.get("source_sync_proof"), dict)
        else {}
    )
    claim_verifier_result = (
        claim_verifier.get("verifier")
        if isinstance(claim_verifier.get("verifier"), dict)
        else {}
    )
    claim_contract_proven = bool(
        claim_verifier.get("ok") is True
        or (
            claim_verifier.get("status") == "deployed_verified"
            and claim_source_sync.get("rog_ct246_hashes_match") is True
            and claim_source_sync.get("ct246_verifier") == "PASS"
            and claim_verifier_result.get("ok") is True
        )
    )
    completion_claim_boundary = bool(
        self_model.get("ok") is True
        and self_model.get("introspection", {}).get(
            "completion_claim_allowed_without_current_proof"
        )
        is False
        and claim_contract_proven
        and exact_worker_receipts
        and station_results == expected_station_results
    )
    authoritative = (
        room.get("authoritative_cycle_completion")
        if isinstance(room.get("authoritative_cycle_completion"), dict)
        else {}
    )

    checks = [
        _criterion(
            1,
            str(criteria[0]),
            bool(
                cycle
                and cycle.get("goal_id") == goal.get("goal_id")
                and room.get("source") == "Engel Flutter Main Chat"
                and room.get("order_id") == order_id
                and chat.get("provider") == "local-ct246-self-upgrade"
            ),
            f"UI order {order_id or 'missing'} -> cycle {cycle.get('cycle_id') or 'missing'}",
            [
                _evidence(room_path, root),
                _evidence(cycle_path, root),
                _evidence(chat_path, root),
            ],
        ),
        _criterion(
            2,
            str(criteria[1]),
            bool(
                conical.get("ok") is True
                and conical.get("build_size") in {"medium", "large", "expert"}
                and conical.get("expected_worker_count") == 4
                and len(conical.get("assignments") or []) >= 3
                and returned_ids == REQUIRED_WORKERS
            ),
            (
                f"build_size={conical.get('build_size')}; "
                f"assignments={len(conical.get('assignments') or [])}"
            ),
            [_evidence(conical_path, root)],
        ),
        _criterion(
            3,
            str(criteria[2]),
            bool(
                broker_stage.get("ok") is True
                and REQUIRED_WORKERS.issubset(eligible)
                and assigned.issubset(eligible)
                and "desktop-fib17o7" not in {item.lower() for item in assigned}
            ),
            f"eligible={sorted(eligible)}; assigned={sorted(assigned)}",
            [_evidence(cycle_path, root), _evidence(conical_path, root)],
        ),
        _criterion(
            4,
            str(criteria[3]),
            exact_worker_receipts,
            (
                f"returned={sorted(returned_ids)}; "
                f"receipt_files={sum(bool(path and path.is_file()) for path in worker_paths)}/4"
            ),
            [_evidence(conical_path, root)]
            + [_evidence(path, root) for path in worker_paths],
        ),
        _criterion(
            5,
            str(criteria[4]),
            bool(
                room.get("completed_at")
                and station_results == expected_station_results
                and authoritative.get("dispatch_performed") is False
            ),
            (
                f"terminal_stations={len(station_results)}/6; "
                "authoritative_projection=true"
            ),
            [_evidence(room_path, root)],
        ),
        _criterion(
            6,
            str(criteria[5]),
            bool(
                chat.get("provider") == "local-ct246-self-upgrade"
                and chat.get("selected_provider") == "ct_self_upgrade_chat_review"
                and "providers were not called"
                in str(chat.get("assistant_reply") or "").lower()
                and all(
                    item.get("analysis_engine")
                    == "on_device_deterministic_conical_v1"
                    for item in worker_results
                    if str(item.get("worker_id") or "").startswith("android_worker_")
                )
                and sub_return.get("local_llm_completed") is True
                and sub_return.get("worker_engine") == "local_llm_one_shot"
            ),
            (
                f"provider={chat.get('provider') or 'missing'}; "
                "provider escalation=false"
            ),
            [
                _evidence(chat_path, root),
                _evidence(conical_path, root),
                _evidence(sub_return_path, root),
            ],
        ),
        _criterion(
            7,
            str(criteria[6]),
            bool(
                issue.get("issue_id")
                and scorecard_count > 0
                and int(reps_state.get("proposal_count_tail") or 0) > 0
            ),
            (
                f"latest_issue={issue.get('issue_id') or 'missing'}; "
                f"evaluations={scorecard_count}; "
                f"proposals={reps_state.get('proposal_count_tail') or 0}"
            ),
            [_evidence(issue_path, root), _evidence(reps_state_path, root)],
        ),
        _criterion(
            8,
            str(criteria[7]),
            upgraded_chain_ok and rollback_proven,
            (
                f"upgrade_cycle={upgraded.get('cycle_id') or 'missing'}; "
                f"provenance/deploy receipts={'valid' if upgraded_chain_ok else 'invalid'}; "
                f"rollback_contract={'valid' if rollback_proven else 'invalid'}"
            ),
            [_evidence(upgraded_path, root), _evidence(rollback_receipt_path, root)],
        ),
        _criterion(
            9,
            str(criteria[8]),
            recall_proven,
            (
                f"reps_ready={reps_state.get('ok') is True}; "
                f"desktop_discord_parity={parity.get('ok') is True}; "
                "recall_receipt="
                f"{bool(teaching.get('training', {}).get('recall_proof'))}"
            ),
            [
                _evidence(teaching_path, root),
                _evidence(parity_path, root),
                _evidence(reps_state_path, root),
            ],
        ),
        _criterion(
            10,
            str(criteria[9]),
            completion_claim_boundary,
            (
                "claim_boundary="
                f"{self_model.get('introspection', {}).get('completion_claim_allowed_without_current_proof')}; "
                f"worker_receipts={len(returned_ids)}/4; "
                f"room_terminal={len(station_results)}/6"
            ),
            [
                _evidence(self_model_path, root),
                _evidence(claim_verifier_path, root),
                _evidence(room_path, root),
            ],
        ),
    ]
    proven = sum(1 for item in checks if item["ok"])
    return {
        "schema": "ENGEL_PRIMARY_GOAL_COMPLETION_AUDIT_V1",
        "ok": True,
        "complete": proven == len(checks),
        "goal_id": goal.get("goal_id"),
        "goal_status": goal.get("status"),
        "source_of_truth": goal.get("source_of_truth"),
        "criteria_total": len(checks),
        "criteria_proven": proven,
        "criteria_not_proven": len(checks) - proven,
        "checks": checks,
        "generated_at_utc": _now(),
        "actor_note": (
            "Observe-only acceptance audit. It reads exact CT246 receipts and "
            "fails closed; it does not dispatch, mutate source, promote memory, "
            "approve a change, or call a provider."
        ),
    }


def write_audit(audit: dict[str, Any], root: Path = ROOT) -> Path:
    output_root = root / "reports" / "self_upgrade" / "goal_completion"
    output_root.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = output_root / f"ENGEL_PRIMARY_GOAL_COMPLETION_{timestamp}.json"
    rendered = json.dumps(audit, indent=2, sort_keys=True) + "\n"
    path.write_text(rendered, encoding="utf-8")
    latest = output_root / "latest.json"
    temp = latest.with_suffix(".tmp")
    temp.write_text(rendered, encoding="utf-8")
    temp.replace(latest)
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=("audit", "status"),
        nargs="?",
        default="audit",
    )
    args = parser.parse_args(argv)
    audit = build_audit()
    path = write_audit(audit) if args.command == "audit" else LATEST_PATH
    result = dict(audit)
    result["receipt_path"] = _relative(path, ROOT)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if audit.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
