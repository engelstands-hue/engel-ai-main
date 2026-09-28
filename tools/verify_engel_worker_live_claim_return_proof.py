#!/usr/bin/env python3
"""Verify Engel's evidence-backed worker live/claim/return contract."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import engel_worker_live_claim_return_proof as proof


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    return path


def compact(value: datetime) -> str:
    return value.strftime("%Y%m%dT%H%M%S%fZ")


def main() -> int:
    checks: list[str] = []
    now = datetime.now(timezone.utc)
    with tempfile.TemporaryDirectory(prefix="engel-worker-proof-") as temp_text:
        root = Path(temp_text)
        claimed = root / "android" / "claimed"
        returned = root / "android" / "returned"
        sub_orders = root / "sub" / "SUB_ENGEL_WORK_ORDERS"
        sub_dispatch = root / "sub" / "receipts"
        sub_returns = root / "sub" / "SUB_ENGEL_SENT_WORK"
        for directory in (
            claimed,
            returned,
            sub_orders,
            sub_dispatch,
            sub_returns,
        ):
            directory.mkdir(parents=True, exist_ok=True)

        alpha_claim_at = now - timedelta(seconds=80)
        alpha_return_at = now - timedelta(seconds=40)
        beta_claim_at = now - timedelta(seconds=25)
        gamma_claim_at = now - timedelta(hours=2)
        write_json(
            claimed / "alpha_claim.json",
            {
                "worker_id": "android_worker_alpha",
                "packet_id": "alpha-1",
                "timestamp_utc": compact(alpha_claim_at),
            },
        )
        write_json(
            returned / "alpha_result.json",
            {
                "worker_id": "android_worker_alpha",
                "packet_id": "alpha-1",
                "stored_at_utc": compact(alpha_return_at),
            },
        )
        write_json(
            claimed / "beta_claim.json",
            {
                "worker_id": "android_worker_beta",
                "packet_id": "beta-1",
                "timestamp_utc": compact(beta_claim_at),
            },
        )
        write_json(
            claimed / "gamma_claim.json",
            {
                "worker_id": "android_worker_gamma",
                "packet_id": "gamma-stale",
                "timestamp_utc": compact(gamma_claim_at),
            },
        )
        sub_order_at = now - timedelta(seconds=90)
        sub_return_at = now - timedelta(seconds=30)
        sub_order_id = "MAIN-MEETING-" + compact(sub_order_at) + "_fixture"
        write_json(
            sub_orders / f"{sub_order_id}.json",
            {
                "id": sub_order_id,
            },
        )
        write_json(
            sub_dispatch / f"{sub_order_id}.dispatch.json",
            {
                "order_id": sub_order_id,
                "dispatched_at_utc": sub_order_at.isoformat(),
            },
        )
        write_json(
            sub_returns / f"DESKTOP-UE5A6GG__{sub_order_id}.done.json",
            {
                "order_id": sub_order_id,
                "completed_at_utc": sub_return_at.isoformat(),
            },
        )

        saved = {
            "claimed": proof.ANDROID_CLAIMED_DIR,
            "returned": proof.ANDROID_RETURNED_DIR,
            "sub_order": proof.SUB_ORDER_DIR,
            "sub_dispatch": proof.SUB_DISPATCH_DIR,
            "sub_return": proof.SUB_RETURN_DIR,
            "freshness": proof.WORK_FRESHNESS_SECONDS,
            "broker": proof._broker_rows,
        }
        proof.ANDROID_CLAIMED_DIR = claimed
        proof.ANDROID_RETURNED_DIR = returned
        proof.SUB_ORDER_DIR = sub_orders
        proof.SUB_DISPATCH_DIR = sub_dispatch
        proof.SUB_RETURN_DIR = sub_returns
        proof.WORK_FRESHNESS_SECONDS = 600

        def broker_rows():
            rows = {
                worker.lower(): {
                    "device_id": worker,
                    "eligible": True,
                    "reachable": True,
                    "reason": "fixture live",
                }
                for worker in proof.REQUIRED_WORKERS
            }
            return rows, {
                "ok": True,
                "selected_device_ids": list(proof.REQUIRED_WORKERS),
                "forbidden_devices": ["desktop-fib17o7"],
                "candidate_count": 4,
            }

        proof._broker_rows = broker_rows
        try:
            snapshot = proof.worker_live_claim_return_snapshot()
            receipt = proof.write_snapshot(root / "latest.json")
        finally:
            proof.ANDROID_CLAIMED_DIR = saved["claimed"]
            proof.ANDROID_RETURNED_DIR = saved["returned"]
            proof.SUB_ORDER_DIR = saved["sub_order"]
            proof.SUB_DISPATCH_DIR = saved["sub_dispatch"]
            proof.SUB_RETURN_DIR = saved["sub_return"]
            proof.WORK_FRESHNESS_SECONDS = saved["freshness"]
            proof._broker_rows = saved["broker"]

        require(snapshot.get("ok") is True, f"snapshot failed: {snapshot}")
        require(snapshot.get("worker_count") == 4, "not all four workers projected")
        checks.append("all three Android workers and Sub-Engel are projected")

        workers = snapshot["workers"]
        require(
            workers["android_worker_alpha"]["work_state"] == "returned",
            "fresh Alpha return was not recognized",
        )
        require(
            workers["android_worker_beta"]["work_state"] == "claimed"
            and workers["android_worker_beta"]["active_claim"] is True,
            "fresh unreturned Beta claim was not recognized",
        )
        require(
            workers["DESKTOP-UE5A6GG"]["work_state"] == "returned",
            "Sub order/dispatch/return lifecycle was not recognized",
        )
        checks.append("fresh claim and return stages come from real receipt files")

        gamma = workers["android_worker_gamma"]
        require(
            gamma["half_alive"] is True
            and gamma["protected_assignment_eligible"] is False,
            "stale unreturned worker remained protected-work eligible",
        )
        checks.append("stale unreturned half-alive worker is blocked from protected work")

        require(
            snapshot.get("all_evidence_paths_present") is True
            and all(
                not row["claim"]["path"] or Path(row["claim"]["path"]).is_file()
                for row in workers.values()
            )
            and all(
                not row["return"]["path"] or Path(row["return"]["path"]).is_file()
                for row in workers.values()
            ),
            "snapshot contains evidence paths that do not exist",
        )
        checks.append("every reported claim/return path exists")

        require(
            receipt.get("mutation_performed") is False
            and receipt.get("trusted_memory_write") is False
            and Path(receipt["receipt_path"]).is_file(),
            "snapshot writer claimed mutation or failed to persist",
        )
        checks.append("durable projection is atomic and observe-only")

    server_source = (
        proof.ROOT / "tools" / "engel_meeting_room_lan_server.py"
    ).read_text(encoding="utf-8")
    require(
        "worker_live_claim_return_snapshot" in server_source
        and '"worker_live_claim_return_proof"' in server_source,
        "Meeting Room does not expose worker proof",
    )
    stream_source = (
        proof.ROOT / "tools" / "engel_meeting_room_event_stream.py"
    ).read_text(encoding="utf-8")
    require(
        'doc.get("worker_id") or doc.get("worker_device")' in stream_source,
        "Meeting Room event stream does not preserve Android worker identity",
    )
    checks.append("Meeting Room and event stream consume the proof contract")

    print(
        json.dumps(
            {
                "schema": "engel_worker_live_claim_return_proof_verifier_v1",
                "goal_id": "engel_conical_agentic_sentient_self_upgrading_system",
                "ok": True,
                "check_count": len(checks),
                "checks": checks,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
