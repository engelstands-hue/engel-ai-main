#!/usr/bin/env python3
"""Verifier for the conical failure -> issue ingestion (engel_conical_failure_to_issue.py).

Proves the repair loop's intake edge is real, bounded, deduped, and honest:
  1. A failed conical job receipt becomes ONE issue whose evidence path is the
     receipt itself, and the ledger records the ingestion.
  2. Re-running ingests nothing (dedup by job_id).
  3. Finished jobs are never ingested.
  4. The per-run limit is respected and the overflow is reported, not hidden.
  5. The symptom names the workers whose proof is missing.
  6. Issues are intake-only records (no source mutation, candidate-only).

Fixtures live in a labeled reports/self_upgrade subdir (evidence paths must be
under reports/) and are removed afterward. Emits {"ok": bool,...}; exit 0/1.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT), str(ROOT / "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

import engel_conical_failure_to_issue as ingest_mod  # noqa: E402

system = ingest_mod.system
CHECKS: list[dict] = []


def record(name: str, ok: bool, detail: str = "") -> None:
    CHECKS.append({"check": name, "ok": bool(ok), "detail": detail})


def _job(job_id: str, status: str, final: str, missing: "list[str]") -> dict:
    return {
        "schema": "engel_conical_build_orchestration_v1",
        "job_id": job_id,
        "status": status,
        "final_status": final,
        "expected_worker_count": 4,
        "returned_worker_count": 4 - len(missing),
        "worker_results": (
            [{"worker_id": w, "returned": False} for w in missing]
            + [{"worker_id": f"ok_{i}", "returned": True} for i in range(4 - len(missing))]
        ),
    }


def main() -> int:
    fx = ROOT / "reports" / "self_upgrade" / f"failure_ingest_fixture_{os.getpid()}"
    jobs = fx / "conical_jobs"
    jobs.mkdir(parents=True, exist_ok=True)

    saved = {
        "jobs_dir": ingest_mod.CONICAL_JOBS_DIR,
        "ledger": ingest_mod.LEDGER_PATH,
        "write_issue": system.write_issue,
    }
    ingest_mod.CONICAL_JOBS_DIR = jobs
    ingest_mod.LEDGER_PATH = fx / "ledger.json"
    system.write_issue = lambda issue: saved["write_issue"](issue, fx)

    try:
        for i in range(3):
            (jobs / f"job_fail_{i}.json").write_text(json.dumps(
                _job(f"conical_job_fail_{i}", "failed_worker_returns", "failed",
                     ["DESKTOP-UE5A6GG"])), encoding="utf-8")
        (jobs / "job_ok.json").write_text(json.dumps(
            _job("conical_job_ok", "workers_returned", "finished", [])), encoding="utf-8")

        # 4: limit respected -------------------------------------------------
        result = ingest_mod.ingest(limit=2)
        record("per-run limit respected and overflow reported",
               result["issues_created_count"] == 2 and result["skipped_beyond_limit"] == 1
               and result["failed_jobs_pending"] == 3,
               f"created={result['issues_created_count']} skipped={result['skipped_beyond_limit']}")

        # 1: issue content + evidence + ledger -------------------------------
        first = result["issues_created"][0]
        issue = json.loads((ROOT / first["issue_path"]).read_text(encoding="utf-8"))
        record("failed job becomes one issue with the receipt as evidence",
               issue["schema"] == "ENGEL_SELF_UPGRADE_ISSUE_V1"
               and issue["source"] == "meeting_room"
               and len(issue["evidence_paths"]) == 1
               and "conical_jobs" in issue["evidence_paths"][0]
               and json.loads(ingest_mod.LEDGER_PATH.read_text(encoding="utf-8"))["ingested"]
                       .get(first["job_id"], {}).get("issue_id") == issue["issue_id"],
               issue["issue_id"])

        # 5: symptom names missing workers -----------------------------------
        record("symptom names the workers whose proof is missing",
               "DESKTOP-UE5A6GG" in issue["symptom"] and "3 of 4" in issue["symptom"],
               issue["symptom"][:110])

        # 6: intake-only record ----------------------------------------------
        record("issue is intake-only (no mutation, candidate-only)",
               issue["source_mutation"] is False and issue["trusted_memory_write"] is False
               and issue["candidate_only"] is True, "")

        # 3 + remainder: finished job never ingested; rerun drains then dedups
        result = ingest_mod.ingest(limit=10)
        record("finished job is never ingested",
               result["issues_created_count"] == 1
               and all("ok" not in c["job_id"] for c in result["issues_created"]),
               str([c["job_id"] for c in result["issues_created"]]))

        # 2: dedup ------------------------------------------------------------
        result = ingest_mod.ingest(limit=10)
        record("re-run ingests nothing (dedup by job_id)",
               result["issues_created_count"] == 0 and result["failed_jobs_pending"] == 0,
               str(result["issues_created_count"]))
    finally:
        ingest_mod.CONICAL_JOBS_DIR = saved["jobs_dir"]
        ingest_mod.LEDGER_PATH = saved["ledger"]
        system.write_issue = saved["write_issue"]
        shutil.rmtree(fx, ignore_errors=True)

    failed = [c for c in CHECKS if not c["ok"]]
    receipt = {
        "schema": "engel_conical_failure_to_issue_verifier_v1",
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
