#!/usr/bin/env python3
"""Verify the self-upgrade backlog driver (groom + bounded dry-run drafting).

Offline: every check runs against an isolated temp report root with injected
planner/cycle fakes. Each fixture isolates one invariant.
"""
from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
ROOT = TOOLS_DIR.parent
for entry in (str(ROOT), str(TOOLS_DIR)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import engel_self_upgrade_system as system  # noqa: E402
import engel_self_upgrade_backlog_driver as driver  # noqa: E402

CHECKS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    CHECKS.append((name, bool(ok), detail))
    print(("PASS " if ok else "FAIL ") + name + (f"  ({detail})" if detail and not ok else ""))


def _iso(offset_minutes: int = 0) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=offset_minutes)).isoformat()


def make_issue(report_root: Path, symptom: str, *, surface: str = "workers",
               source: str = "meeting_room", severity: str = "medium",
               created_at: str | None = None) -> dict:
    issue = system.build_issue(
        source=source, symptom=symptom, severity=severity,
        affected_surface=surface, evidence_paths=[], created_at=created_at)
    system.write_issue(issue, report_root)
    return issue


def load_by_id(report_root: Path, issue_id: str) -> dict:
    for issue in driver.load_backlog(report_root):
        if issue["issue_id"] == issue_id:
            return issue
    raise AssertionError(f"issue not found: {issue_id}")


def write_conical_receipt(conical_dir: Path, *, ok: bool, returned: int,
                          started_at: str) -> Path:
    conical_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "engel_conical_build_orchestration_v1", "ok": ok,
        "expected_worker_count": 4, "returned_worker_count": returned,
        "failed_worker_count": 4 - returned, "started_at_utc": started_at,
    }
    out = conical_dir / f"conical_job_{started_at.replace(':', '').replace('+', '')}.json"
    out.write_text(json.dumps(payload), encoding="utf-8")
    return out


def main() -> int:
    # 1. normalize_symptom collapses job ids so convergence duplicates cluster.
    a = driver.normalize_symptom("conical job conical_job_20260727T06_p1_aa failed worker convergence: 3/4")
    b = driver.normalize_symptom("conical job conical_job_20260727T07_p2_bb failed worker convergence: 3/4")
    check("normalize_collapses_job_ids", a == b, f"{a!r} != {b!r}")

    # 2. duplicate grooming keeps the oldest representative open.
    with tempfile.TemporaryDirectory() as tmp:
        report_root = Path(tmp) / "self_upgrade"
        oldest = make_issue(report_root, "Improve the planner error message.",
                            surface="source_patch", source="chat_ui", created_at=_iso(-30))
        dup1 = make_issue(report_root, "Improve  the planner error message.",
                          surface="source_patch", source="chat_ui", created_at=_iso(-20))
        dup2 = make_issue(report_root, "improve the planner error message.",
                          surface="source_patch", source="chat_ui", created_at=_iso(-10))
        result = driver.groom(report_root, Path(tmp) / "conical_jobs")
        rep = load_by_id(report_root, oldest["issue_id"])
        d1 = load_by_id(report_root, dup1["issue_id"])
        d2 = load_by_id(report_root, dup2["issue_id"])
        check("dedup_keeps_oldest_open", rep["status"] == "open")
        check("dedup_closes_duplicates",
              d1["status"] == "rejected" and d2["status"] == "rejected"
              and d1.get("superseded_by") == oldest["issue_id"]
              and d2.get("superseded_by") == oldest["issue_id"])
        closed = [x for x in result["groom_actions"] if x["action"] == "closed_duplicate"]
        check("dedup_actions_recorded", len(closed) == 2, json.dumps(result["groom_actions"]))

    # 3. stale convergence closes ONLY with a newer 4/4 proof receipt.
    with tempfile.TemporaryDirectory() as tmp:
        report_root = Path(tmp) / "self_upgrade"
        conical_dir = Path(tmp) / "conical_jobs"
        stale = make_issue(report_root,
                           "conical job conical_job_A failed worker convergence: 3/4",
                           created_at=_iso(-60))
        write_conical_receipt(conical_dir, ok=True, returned=4, started_at=_iso(-5))
        driver.groom(report_root, conical_dir)
        got = load_by_id(report_root, stale["issue_id"])
        check("stale_closed_with_proof",
              got["status"] == "rejected"
              and got.get("driver_resolution") == "stale_condition_cleared"
              and got.get("driver_evidence_paths"))
    with tempfile.TemporaryDirectory() as tmp:
        report_root = Path(tmp) / "self_upgrade"
        conical_dir = Path(tmp) / "conical_jobs"
        kept = make_issue(report_root,
                          "conical job conical_job_B failed worker convergence: 3/4",
                          created_at=_iso(-10))
        write_conical_receipt(conical_dir, ok=True, returned=4, started_at=_iso(-60))
        write_conical_receipt(conical_dir, ok=True, returned=3, started_at=_iso(-5))
        write_conical_receipt(conical_dir, ok=False, returned=4, started_at=_iso(-4))
        driver.groom(report_root, conical_dir)
        got = load_by_id(report_root, kept["issue_id"])
        check("no_proof_stays_open", got["status"] == "open")

    # 4. resolutions manifest requires existing evidence.
    with tempfile.TemporaryDirectory() as tmp:
        report_root = Path(tmp) / "self_upgrade"
        target = make_issue(report_root, "Provenance stage detail wording request.",
                            surface="source_patch", source="chat_ui")
        keep = make_issue(report_root, "Another real request without a resolution.",
                          surface="source_patch", source="chat_ui")
        evidence = Path(tmp) / "evidence.json"
        evidence.write_text("{}", encoding="utf-8")
        manifest = Path(tmp) / "resolutions.json"
        manifest.write_text(json.dumps({
            target["issue_id"]: {"reason": "shipped 20260727",
                                 "evidence_paths": [str(evidence)]},
            keep["issue_id"]: {"reason": "no evidence",
                               "evidence_paths": [str(Path(tmp) / "missing.json")]},
        }), encoding="utf-8")
        driver.groom(report_root, Path(tmp) / "conical_jobs", manifest)
        check("resolution_with_evidence_closes",
              load_by_id(report_root, target["issue_id"])["status"] == "rejected")
        check("resolution_missing_evidence_skips",
              load_by_id(report_root, keep["issue_id"])["status"] == "open")

    # 5. draft success: dry-run only, no tokens, issue -> candidate_ready.
    with tempfile.TemporaryDirectory() as tmp:
        report_root = Path(tmp) / "self_upgrade"
        issue = make_issue(report_root, "Improve one bounded error message in the planner.",
                           surface="source_patch", source="chat_ui")
        seen: dict = {}

        def fake_planner(payload):
            seen["payload"] = payload
            return {"cycle_request": {"symptom": payload["request_text"]}}

        def fake_cycle(request, **kwargs):
            seen["kwargs"] = kwargs
            return {"final_status": "dry_run_complete",
                    "cycle_receipt_path": "reports/self_upgrade/cycles/x.json"}

        result = driver.draft(report_root, limit=1,
                              planner_fn=fake_planner, cycle_fn=fake_cycle)
        got = load_by_id(report_root, issue["issue_id"])
        check("draft_marks_candidate_ready",
              got["status"] == "candidate_ready"
              and got.get("driver_cycle_receipt") == "reports/self_upgrade/cycles/x.json")
        check("draft_is_dry_run_only",
              seen["kwargs"].get("dry_run") is True
              and not any(k for k in seen["kwargs"]
                          if "token" in k and seen["kwargs"][k]))
        check("draft_payload_from_issue",
              seen["payload"]["request_text"].startswith("Improve one bounded"))
        check("draft_result_recorded",
              result["draft_results"][0]["outcome"] == "candidate_ready")

    # 6. draft failure leaves the issue open and records the attempt.
    with tempfile.TemporaryDirectory() as tmp:
        report_root = Path(tmp) / "self_upgrade"
        issue = make_issue(report_root, "A request the local planner cannot draft.",
                           surface="source_patch", source="chat_ui")

        def broken_planner(payload):
            raise ValueError("planner rejected the request")

        driver.draft(report_root, limit=1, planner_fn=broken_planner,
                     cycle_fn=lambda *a, **k: {})
        got = load_by_id(report_root, issue["issue_id"])
        check("plan_failure_stays_open",
              got["status"] == "open" and got.get("driver_attempts"))

    # 7. limit is respected and hard-capped.
    with tempfile.TemporaryDirectory() as tmp:
        report_root = Path(tmp) / "self_upgrade"
        for index in range(3):
            make_issue(report_root, f"Bounded request number {index} for limits.",
                       surface="source_patch", source="chat_ui",
                       created_at=_iso(-30 + index))
        calls = {"count": 0}

        def counting_planner(payload):
            calls["count"] += 1
            return {"cycle_request": {"symptom": payload["request_text"]}}

        def ok_cycle(request, **kwargs):
            return {"final_status": "dry_run_complete", "cycle_receipt_path": "r.json"}

        driver.draft(report_root, limit=1, planner_fn=counting_planner, cycle_fn=ok_cycle)
        check("limit_respected", calls["count"] == 1, str(calls))
        result = driver.draft(report_root, limit=99, planner_fn=counting_planner,
                              cycle_fn=ok_cycle)
        check("limit_hard_capped", result["draft_limit"] == driver.MAX_DRAFT_LIMIT)

    # 8. driver receipt is candidate-only with no apply claim, and a caller
    #    payload can never override the fixed safety flags.
    with tempfile.TemporaryDirectory() as tmp:
        report_root = Path(tmp) / "self_upgrade"
        out = driver.write_driver_receipt(
            report_root, {"command": "drive", "apply_performed": True})
        receipt = json.loads(out.read_text(encoding="utf-8"))
        check("receipt_shape",
              receipt["schema"] == driver.DRIVER_SCHEMA
              and receipt["apply_performed"] is False
              and receipt["candidate_only"] is True
              and receipt["trusted_memory_write"] is False)

    # 9. the CLI works with a report root OUTSIDE the project root — the
    #    receipt path falls back to an absolute path instead of crashing.
    with tempfile.TemporaryDirectory() as tmp:
        import contextlib
        import io

        report_root = Path(tmp) / "self_upgrade"
        make_issue(report_root, "Outside-root receipt path smoke check.",
                   surface="source_patch", source="chat_ui")
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            rc = driver._cli(["groom", "--report-root", str(report_root)])
        printed = json.loads(buffer.getvalue())
        check("cli_outside_root_receipt",
              rc == 0 and bool(printed.get("receipt_path"))
              and Path(printed["receipt_path"]).exists())

    failed = [name for name, ok, _ in CHECKS if not ok]
    print(f"\n{len(CHECKS) - len(failed)}/{len(CHECKS)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
