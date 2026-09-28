#!/usr/bin/env python3
"""Engel Conical Failure -> Issue ingestion (closes the repair loop's intake).

Serves the Conical Agentic Sentient Self Upgrading System primary goal,
acceptance criterion: "Failures create issues, evaluations, and bounded
upgrade proposals." Before this module, conical jobs that ended in
failed_worker_returns wrote honest failure receipts that NOTHING consumed —
every self-upgrade issue on disk was a manual hand-seed.

This converter scans reports/conical_jobs/ receipts and files ONE bounded,
evidence-backed self-upgrade issue per failed job:

    conical receipt (final_status=failed / failed_worker_returns)
        -> engel_self_upgrade_system.build_issue(source="meeting_room", ...)
           with the receipt as the evidence path
        -> dedup ledger so a job is never ingested twice

It is DECISION/INTAKE only: it writes issues (which mutate nothing) and a
ledger. It never routes, patches, applies, dispatches, or writes trusted
memory — downstream stages remain the governed conical self-upgrade cycle
with its quorum and human tokens.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT), str(ROOT / "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import engel_self_upgrade_system as system  # noqa: E402

CONICAL_JOBS_DIR = ROOT / "reports" / "conical_jobs"
LEDGER_PATH = system.REPORT_ROOT / "conical_failure_ingest_ledger.json"
DEFAULT_LIMIT = 5
MAX_SCAN_FILES = 400


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_ledger() -> "dict[str, Any]":
    try:
        data = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("ingested"), dict):
            return data
    except Exception:
        pass
    return {"schema": "ENGEL_CONICAL_FAILURE_INGEST_LEDGER_V1", "ingested": {}}


def _job_failed(receipt: "dict[str, Any]") -> bool:
    if receipt.get("final_status") == "failed":
        return True
    if receipt.get("final_status") in {"finished", "dry_run_complete"}:
        return False
    return receipt.get("status") == "failed_worker_returns"


def _failure_symptom(receipt: "dict[str, Any]") -> str:
    job_id = str(receipt.get("job_id") or "unknown_job")
    expected = int(receipt.get("expected_worker_count") or 0)
    returned = int(receipt.get("returned_worker_count") or 0)
    missing = [
        str(item.get("worker_id") or "")
        for item in (receipt.get("worker_results") or [])
        if isinstance(item, dict) and item.get("returned") is not True
    ]
    missing_note = ", ".join(w for w in missing if w) or "unknown workers"
    return (f"conical job {job_id} failed worker convergence: {returned} of {expected} "
            f"returns arrived; missing proof from {missing_note}")


def scan_failed_jobs() -> "list[dict[str, Any]]":
    """Newest-first failed conical job receipts not yet in the ledger."""
    ledger = _load_ledger()
    seen = ledger["ingested"]
    out: list[dict[str, Any]] = []
    if not CONICAL_JOBS_DIR.is_dir():
        return out
    files = sorted(CONICAL_JOBS_DIR.glob("*.json"),
                   key=lambda p: p.stat().st_mtime, reverse=True)[:MAX_SCAN_FILES]
    for path in files:
        try:
            receipt = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(receipt, dict) or not _job_failed(receipt):
            continue
        job_id = str(receipt.get("job_id") or path.stem)
        if job_id in seen:
            continue
        out.append({
            "job_id": job_id,
            "receipt_path": system.project_relative(path),
            "symptom": _failure_symptom(receipt),
        })
    return out


def ingest(limit: int = DEFAULT_LIMIT) -> "dict[str, Any]":
    """File bounded issues for un-ingested failed conical jobs."""
    candidates = scan_failed_jobs()
    ledger = _load_ledger()
    created: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for entry in candidates[:max(0, int(limit))]:
        try:
            issue = system.build_issue(
                source="meeting_room",
                symptom=entry["symptom"],
                severity="medium",
                affected_surface="workers",
                evidence_paths=[entry["receipt_path"]],
            )
            issue_path = system.write_issue(issue)
            ledger["ingested"][entry["job_id"]] = {
                "issue_id": issue["issue_id"],
                "issue_path": system.project_relative(issue_path),
                "ingested_at_utc": _now(),
            }
            created.append({"job_id": entry["job_id"], "issue_id": issue["issue_id"],
                            "issue_path": system.project_relative(issue_path)})
        except Exception as exc:
            errors.append({"job_id": entry["job_id"], "error": str(exc)[:200]})
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    LEDGER_PATH.write_text(json.dumps(ledger, indent=2, ensure_ascii=False), encoding="utf-8")
    return {
        "schema": "ENGEL_CONICAL_FAILURE_INGEST_RUN_V1",
        "goal_id": "engel_conical_agentic_sentient_self_upgrading_system",
        "ran_at_utc": _now(),
        "failed_jobs_pending": len(candidates),
        "limit": int(limit),
        "issues_created": created,
        "issues_created_count": len(created),
        "skipped_beyond_limit": max(0, len(candidates) - int(limit)),
        "errors": errors,
        "actor_note": "intake only: files issues + ledger; no route/patch/apply/dispatch/trusted-memory",
    }


def _cli(argv: "list[str] | None" = None) -> int:
    import argparse

    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    parser = argparse.ArgumentParser(
        description="Engel conical failure -> self-upgrade issue ingestion (bounded, deduped)")
    parser.add_argument("command", choices=["scan", "ingest", "status"], nargs="?", default="scan")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    args = parser.parse_args(argv)
    if args.command == "scan":
        pending = scan_failed_jobs()
        print(json.dumps({"pending_failed_jobs": pending, "count": len(pending)},
                         indent=2, ensure_ascii=False))
        return 0
    if args.command == "status":
        ledger = _load_ledger()
        print(json.dumps({"ingested_count": len(ledger["ingested"]),
                          "ledger_path": system.project_relative(LEDGER_PATH)
                          if LEDGER_PATH.exists() else None},
                         indent=2, ensure_ascii=False))
        return 0
    result = ingest(limit=args.limit)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(_cli())
