#!/usr/bin/env python3
"""Evidence-backed live/claim/return state for Engel's four required workers."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ANDROID_ROOT = ROOT / "remote_workers" / "communication_queen_assignments"
ANDROID_CLAIMED_DIR = ANDROID_ROOT / "claimed"
ANDROID_RETURNED_DIR = ANDROID_ROOT / "returned"
SUB_TRANSPORT_ROOT = ROOT / "run" / "sub_engel_transport"
SUB_ORDER_DIR = SUB_TRANSPORT_ROOT / "SUB_ENGEL_WORK_ORDERS"
SUB_DISPATCH_DIR = SUB_TRANSPORT_ROOT / "receipts"
SUB_RETURN_DIR = SUB_TRANSPORT_ROOT / "SUB_ENGEL_SENT_WORK"
REPORT_ROOT = ROOT / "run" / "self_update" / "worker_live_claim_return"
LATEST_REPORT = REPORT_ROOT / "latest.json"

REQUIRED_WORKERS = (
    "android_worker_alpha",
    "android_worker_beta",
    "android_worker_gamma",
    "DESKTOP-UE5A6GG",
)
ANDROID_WORKERS = REQUIRED_WORKERS[:3]
SUB_WORKER = REQUIRED_WORKERS[3]


def _env_seconds(name: str, default: float) -> float:
    try:
        return max(1.0, float(os.environ.get(name, "") or default))
    except (TypeError, ValueError):
        return default


WORK_FRESHNESS_SECONDS = _env_seconds(
    "ENGEL_WORKER_PROOF_FRESHNESS_SECONDS",
    1800.0,
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _parse_utc(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        match = re.fullmatch(r"(\d{8}T\d{6})(\d{1,9})?Z", text)
        if not match:
            return None
        fraction = (match.group(2) or "")[:6].ljust(6, "0")
        try:
            parsed = datetime.strptime(
                match.group(1) + fraction,
                "%Y%m%dT%H%M%S%f",
            ).replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _evidence_time(
    path: Path,
    payload: dict[str, Any],
    fields: tuple[str, ...],
) -> datetime | None:
    for field in fields:
        parsed = _parse_utc(payload.get(field))
        if parsed is not None:
            return parsed
    for field in ("packet_id", "order_id", "id"):
        match = re.search(
            r"(\d{8}T\d{6}(?:\d{1,9})?Z)",
            str(payload.get(field) or ""),
        )
        if match:
            parsed = _parse_utc(match.group(1))
            if parsed is not None:
                return parsed
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
    except OSError:
        return None


def _evidence(
    path: Path | None,
    payload: dict[str, Any] | None,
    fields: tuple[str, ...],
    *,
    packet_fields: tuple[str, ...] = ("packet_id", "order_id", "id"),
) -> dict[str, Any]:
    if path is None or payload is None:
        return {
            "present": False,
            "path": "",
            "at_utc": "",
            "packet_id": "",
        }
    observed = _evidence_time(path, payload, fields)
    packet_id = ""
    for field in packet_fields:
        packet_id = str(payload.get(field) or "").strip()
        if packet_id:
            break
    return {
        "present": path.is_file(),
        "path": str(path),
        "at_utc": observed.isoformat().replace("+00:00", "Z")
        if observed
        else "",
        "packet_id": packet_id,
    }


def _newest_worker_file(
    directory: Path,
    suffix: str,
    worker_id: str,
    time_fields: tuple[str, ...],
) -> tuple[Path | None, dict[str, Any] | None]:
    newest: tuple[datetime, Path, dict[str, Any]] | None = None
    if not directory.is_dir():
        return None, None
    for path in directory.glob(f"*{suffix}"):
        payload = _read_json(path)
        if str(payload.get("worker_id") or "").strip() != worker_id:
            continue
        observed = _evidence_time(path, payload, time_fields)
        if observed is None:
            continue
        if newest is None or observed > newest[0]:
            newest = (observed, path, payload)
    return (newest[1], newest[2]) if newest else (None, None)


def _newest_sub_file(
    directory: Path,
    pattern: str,
    time_fields: tuple[str, ...],
) -> tuple[Path | None, dict[str, Any] | None]:
    newest: tuple[datetime, Path, dict[str, Any]] | None = None
    if not directory.is_dir():
        return None, None
    for path in directory.glob(pattern):
        payload = _read_json(path)
        observed = _evidence_time(path, payload, time_fields)
        if observed is None:
            continue
        if newest is None or observed > newest[0]:
            newest = (observed, path, payload)
    return (newest[1], newest[2]) if newest else (None, None)


def _broker_rows() -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    try:
        import engel_device_broker

        decision = engel_device_broker.broker_decision()
    except Exception as exc:
        return {}, {"ok": False, "error": str(exc)}
    rows: dict[str, dict[str, Any]] = {}
    for raw in decision.get("candidates", []):
        if not isinstance(raw, dict):
            continue
        worker_id = str(raw.get("device_id") or "").strip()
        if worker_id:
            rows[worker_id.lower()] = raw
    return rows, {
        "ok": True,
        "selected_device_ids": list(decision.get("selected_device_ids") or []),
        "forbidden_devices": list(decision.get("forbidden_devices") or []),
        "candidate_count": int(decision.get("candidate_count") or 0),
    }


def _age_seconds(value: str, now: datetime) -> float | None:
    parsed = _parse_utc(value)
    if parsed is None:
        return None
    return round((now - parsed).total_seconds(), 3)


def _worker_record(
    worker_id: str,
    worker_class: str,
    broker: dict[str, Any],
    claim: dict[str, Any],
    returned: dict[str, Any],
    now: datetime,
) -> dict[str, Any]:
    claim_age = _age_seconds(str(claim.get("at_utc") or ""), now)
    return_age = _age_seconds(str(returned.get("at_utc") or ""), now)
    claim_time = _parse_utc(claim.get("at_utc"))
    return_time = _parse_utc(returned.get("at_utc"))
    unreturned_claim = bool(
        claim.get("present")
        and (return_time is None or (claim_time is not None and claim_time > return_time))
    )
    claim_fresh = bool(
        unreturned_claim
        and claim_age is not None
        and 0 <= claim_age <= WORK_FRESHNESS_SECONDS
    )
    return_fresh = bool(
        returned.get("present")
        and return_age is not None
        and 0 <= return_age <= WORK_FRESHNESS_SECONDS
    )
    broker_eligible = broker.get("eligible") is True
    reachable = broker.get("reachable") is True
    half_alive = bool(
        (reachable and not broker_eligible)
        or (unreturned_claim and not claim_fresh)
        or (claim_fresh and not reachable)
    )
    if claim_fresh:
        work_state = "claimed"
    elif return_fresh:
        work_state = "returned"
    elif reachable:
        work_state = "idle"
    else:
        work_state = "unreachable"
    protected_eligible = bool(
        reachable
        and broker_eligible
        and not half_alive
    )
    reasons: list[str] = []
    if half_alive:
        reasons.append("half_alive_or_stale_unreturned_claim")
    if not reachable:
        reasons.append("not_reachable")
    if not broker_eligible:
        reasons.append(str(broker.get("reason") or "broker_ineligible"))
    if not reasons:
        reasons.append("live_and_evidence_consistent")
    return {
        "worker_id": worker_id,
        "worker_class": worker_class,
        "live": reachable,
        "broker_eligible": broker_eligible,
        "half_alive": half_alive,
        "protected_assignment_eligible": protected_eligible,
        "work_state": work_state,
        "work_fresh": claim_fresh or return_fresh,
        "active_claim": claim_fresh,
        "last_claim_utc": str(claim.get("at_utc") or ""),
        "last_return_utc": str(returned.get("at_utc") or ""),
        "claim_age_seconds": claim_age,
        "return_age_seconds": return_age,
        "claim": claim,
        "return": returned,
        "broker_reason": str(broker.get("reason") or ""),
        "reason": "; ".join(reasons),
    }


def worker_live_claim_return_snapshot() -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    broker_rows, broker_summary = _broker_rows()
    workers: dict[str, dict[str, Any]] = {}
    for worker_id in ANDROID_WORKERS:
        claim_path, claim_payload = _newest_worker_file(
            ANDROID_CLAIMED_DIR,
            "_claim.json",
            worker_id,
            ("timestamp_utc", "claimed_at_utc", "stored_at_utc"),
        )
        return_path, return_payload = _newest_worker_file(
            ANDROID_RETURNED_DIR,
            "_result.json",
            worker_id,
            ("stored_at_utc", "timestamp_utc", "completed_at_utc"),
        )
        workers[worker_id] = _worker_record(
            worker_id,
            "android_worker",
            broker_rows.get(worker_id.lower(), {}),
            _evidence(
                claim_path,
                claim_payload,
                ("timestamp_utc", "claimed_at_utc", "stored_at_utc"),
            ),
            _evidence(
                return_path,
                return_payload,
                ("stored_at_utc", "timestamp_utc", "completed_at_utc"),
            ),
            now,
        )

    order_path, order_payload = _newest_sub_file(
        SUB_ORDER_DIR,
        "*.json",
        ("dispatched_at_utc", "created_at_utc"),
    )
    dispatch_path, dispatch_payload = _newest_sub_file(
        SUB_DISPATCH_DIR,
        "*.dispatch.json",
        ("dispatched_at_utc", "created_at_utc", "completed_at_utc"),
    )
    claim_path = dispatch_path or order_path
    claim_payload = dispatch_payload or order_payload
    return_path, return_payload = _newest_sub_file(
        SUB_RETURN_DIR,
        f"{SUB_WORKER}__*.done*.json",
        ("completed_at_utc", "returned_at_utc"),
    )
    sub_claim = _evidence(
        claim_path,
        claim_payload,
        ("dispatched_at_utc", "created_at_utc", "completed_at_utc"),
        packet_fields=("order_id", "id"),
    )
    if order_payload and order_path and claim_path == dispatch_path:
        order_id = str(
            dispatch_payload.get("order_id")
            or dispatch_payload.get("id")
            or order_payload.get("order_id")
            or order_payload.get("id")
            or ""
        )
        sub_claim["packet_id"] = order_id
    workers[SUB_WORKER] = _worker_record(
        SUB_WORKER,
        "windows_sub_engel",
        broker_rows.get(SUB_WORKER.lower(), {}),
        sub_claim,
        _evidence(
            return_path,
            return_payload,
            ("completed_at_utc", "returned_at_utc"),
            packet_fields=("order_id", "id"),
        ),
        now,
    )

    active_workers = [
        worker_id
        for worker_id, row in workers.items()
        if row.get("active_claim") is True
    ]
    half_alive_workers = [
        worker_id
        for worker_id, row in workers.items()
        if row.get("half_alive") is True
    ]
    protected_eligible_workers = [
        worker_id
        for worker_id, row in workers.items()
        if row.get("protected_assignment_eligible") is True
    ]
    evidence_present = all(
        (
            not row["claim"].get("path")
            or row["claim"].get("present") is True
        )
        and (
            not row["return"].get("path")
            or row["return"].get("present") is True
        )
        for row in workers.values()
    )
    return {
        "schema": "engel_worker_live_claim_return_proof_v1",
        "goal_id": "engel_conical_agentic_sentient_self_upgrading_system",
        "ok": (
            set(workers) == set(REQUIRED_WORKERS)
            and evidence_present
            and broker_summary.get("ok") is True
        ),
        "generated_at_utc": now.isoformat().replace("+00:00", "Z"),
        "freshness_seconds": WORK_FRESHNESS_SECONDS,
        "required_worker_count": len(REQUIRED_WORKERS),
        "worker_count": len(workers),
        "active_worker_count": len(active_workers),
        "active_worker_ids": active_workers,
        "half_alive_worker_ids": half_alive_workers,
        "protected_assignment_eligible_worker_ids": protected_eligible_workers,
        "all_evidence_paths_present": evidence_present,
        "workers": workers,
        "broker": broker_summary,
        "assignment_rule": (
            "A worker may receive protected work only when current broker "
            "evidence is eligible and no stale/unreturned half-alive condition exists."
        ),
        "mutation_performed": False,
        "trusted_memory_write": False,
    }


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp-{os.getpid()}")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def write_snapshot(path: Path = LATEST_REPORT) -> dict[str, Any]:
    payload = worker_live_claim_return_snapshot()
    _atomic_write_json(path, payload)
    result = dict(payload)
    result["receipt_path"] = str(path)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        nargs="?",
        choices=("status", "snapshot"),
        default="status",
    )
    args = parser.parse_args(argv)
    payload = (
        write_snapshot()
        if args.command == "snapshot"
        else worker_live_claim_return_snapshot()
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
