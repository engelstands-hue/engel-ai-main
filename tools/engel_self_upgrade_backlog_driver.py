#!/usr/bin/env python3
"""Backlog driver: move open self-upgrade issues through the governed gates.

The gap this closes (handoff 2026-07-27, open item 2): issues pile up as
status=open because nothing turns them into routed cycle requests with drafted
candidates. This driver is that movement, in two bounded lanes:

  groom  - deterministic, no model: close duplicate issues (superseded_by the
           oldest representative), close stale worker-convergence issues when a
           NEWER conical job receipt proves 4/4 workers return, and close
           issues listed in an explicit resolutions manifest whose evidence
           files exist. Every closure cites its evidence path.
  draft  - local-LLM-first: for surviving open issues (severity, then age),
           run engel_local_self_upgrade_planner.plan_request to draft a full
           cycle request, then engel_conical_self_upgrade_cycle.run_cycle in
           DRY-RUN through route -> distributed review -> candidate ->
           provenance -> quorum -> lesson. Success moves the issue to
           candidate_ready with the cycle receipt linked.

This driver NEVER applies patches: run_cycle is always dry_run=True and no
approval/gate/apply token is ever passed. Applying stays with the separately
tokened human chain (constitution: observe -> propose -> verify -> report ->
approve -> apply). One invocation processes at most --limit draft issues and
then exits; there is no loop and no daemon mode.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

TOOLS_DIR = Path(__file__).resolve().parent
ROOT = TOOLS_DIR.parent
for entry in (str(ROOT), str(TOOLS_DIR)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import engel_self_upgrade_system as system  # noqa: E402

DRIVER_SCHEMA = "ENGEL_BACKLOG_DRIVER_RECEIPT_V1"
CONVERGENCE_MARKER = "failed worker convergence"
JOB_ID_PATTERN = re.compile(r"conical_job_\S+")
NORMALIZE_LIMIT = 160
DEFAULT_DRAFT_LIMIT = 1
MAX_DRAFT_LIMIT = 5


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _relative(path: Path) -> str:
    try:
        return system.project_relative(path)
    except ValueError:
        return str(path)


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def normalize_symptom(symptom: str) -> str:
    text = JOB_ID_PATTERN.sub("conical_job_*", str(symptom or ""))
    text = re.sub(r"\s+", " ", text).strip().casefold()
    return text[:NORMALIZE_LIMIT]


def load_backlog(report_root: Path) -> list[dict[str, Any]]:
    issues = []
    issues_dir = report_root / "issues"
    if not issues_dir.exists():
        return issues
    for path in sorted(issues_dir.glob("*.json")):
        try:
            issue = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if issue.get("schema") != "ENGEL_SELF_UPGRADE_ISSUE_V1":
            continue
        issue["_path"] = path
        issues.append(issue)
    return issues


def _save_issue(issue: dict[str, Any]) -> None:
    path = issue.pop("_path")
    try:
        system.validate_issue(issue)
        path.write_text(
            json.dumps(issue, indent=2, ensure_ascii=False), encoding="utf-8")
    finally:
        issue["_path"] = path


def _close_issue(issue: dict[str, Any], resolution: str, reason: str,
                 evidence_paths: list[str]) -> None:
    issue["status"] = "rejected"
    issue["driver_resolution"] = resolution
    issue["driver_reason"] = reason
    issue["driver_evidence_paths"] = evidence_paths
    issue["driver_updated_utc"] = _now()
    _save_issue(issue)


def _comparable_utc(stamp: str) -> str:
    """Normalize '+00:00' and 'Z' suffixes so ISO stamps compare as strings."""
    return str(stamp or "").replace("+00:00", "Z")


def find_fresh_convergence_proof(conical_dir: Path, after_utc: str) -> Path | None:
    """Newest conical job receipt proving 4/4 workers returned after the issue."""
    best: tuple[str, Path] | None = None
    after_utc = _comparable_utc(after_utc)
    if not conical_dir.exists():
        return None
    for path in conical_dir.glob("conical_job_*.json"):
        try:
            receipt = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        started = _comparable_utc(receipt.get("started_at_utc"))
        if not receipt.get("ok"):
            continue
        try:
            expected = int(receipt.get("expected_worker_count") or 0)
            returned = int(receipt.get("returned_worker_count") or 0)
            failed = int(receipt.get("failed_worker_count") or 0)
        except (TypeError, ValueError):
            continue
        if expected != 4 or returned != 4 or failed != 0:
            continue
        if started <= after_utc:
            continue
        if best is None or started > best[0]:
            best = (started, path)
    return best[1] if best else None


def groom(report_root: Path, conical_dir: Path,
          resolutions_path: Path | None = None) -> dict[str, Any]:
    actions: list[dict[str, Any]] = []
    resolutions: dict[str, Any] = {}
    if resolutions_path is not None:
        resolutions = json.loads(resolutions_path.read_text(encoding="utf-8"))

    backlog = [i for i in load_backlog(report_root) if i.get("status") == "open"]

    # Lane 1: explicit resolutions manifest (issue_id -> reason + evidence).
    for issue in backlog:
        entry = resolutions.get(issue.get("issue_id", ""))
        if not isinstance(entry, dict) or issue.get("status") != "open":
            continue
        evidence = [str(p) for p in entry.get("evidence_paths") or []]
        missing = [p for p in evidence
                   if not (Path(p) if Path(p).is_absolute() else ROOT / p).exists()]
        if not evidence or missing:
            actions.append({"issue_id": issue["issue_id"], "action": "skipped",
                            "reason": f"resolution evidence missing: {missing or 'none given'}"})
            continue
        _close_issue(issue, "resolved_elsewhere",
                     str(entry.get("reason") or "resolved elsewhere"), evidence)
        actions.append({"issue_id": issue["issue_id"], "action": "closed_resolved",
                        "evidence_paths": evidence})

    # Lane 2: stale worker-convergence issues, only with a newer 4/4 receipt.
    for issue in backlog:
        if issue.get("status") != "open":
            continue
        if CONVERGENCE_MARKER not in normalize_symptom(issue.get("symptom", "")):
            continue
        proof = find_fresh_convergence_proof(
            conical_dir, str(issue.get("first_seen_utc") or ""))
        if proof is None:
            continue
        _close_issue(issue, "stale_condition_cleared",
                     "worker convergence restored: a newer conical job receipt "
                     "proves 4/4 workers returned with 0 failures",
                     [_relative(proof)])
        actions.append({"issue_id": issue["issue_id"], "action": "closed_stale",
                        "evidence_paths": [_relative(proof)]})

    # Lane 3: duplicates - keep the oldest representative per normalized symptom.
    clusters: dict[str, list[dict[str, Any]]] = {}
    for issue in backlog:
        if issue.get("status") != "open":
            continue
        clusters.setdefault(normalize_symptom(issue.get("symptom", "")), []).append(issue)
    for cluster in clusters.values():
        if len(cluster) < 2:
            continue
        cluster.sort(key=lambda i: str(i.get("first_seen_utc") or ""))
        representative = cluster[0]
        for duplicate in cluster[1:]:
            duplicate["superseded_by"] = representative["issue_id"]
            _close_issue(duplicate, "duplicate",
                         f"duplicate of {representative['issue_id']}",
                         [_relative(representative["_path"])])
            actions.append({"issue_id": duplicate["issue_id"], "action": "closed_duplicate",
                            "superseded_by": representative["issue_id"]})

    return {"groom_actions": actions}


def _severity_rank(severity: str) -> int:
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    return order.get(str(severity or "").casefold(), 9)


def draft(report_root: Path, *, limit: int = DEFAULT_DRAFT_LIMIT,
          issue_id: str = "",
          planner_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
          cycle_fn: Callable[..., dict[str, Any]] | None = None) -> dict[str, Any]:
    limit = max(1, min(int(limit), MAX_DRAFT_LIMIT))
    if planner_fn is None:
        from engel_local_self_upgrade_planner import plan_request
        planner_fn = plan_request
    if cycle_fn is None:
        from engel_conical_self_upgrade_cycle import run_cycle
        cycle_fn = run_cycle

    candidates = [i for i in load_backlog(report_root) if i.get("status") == "open"]
    if issue_id:
        candidates = [i for i in candidates if i.get("issue_id") == issue_id]
    candidates.sort(key=lambda i: (_severity_rank(i.get("severity", "")),
                                   str(i.get("first_seen_utc") or "")))

    results: list[dict[str, Any]] = []
    for issue in candidates[:limit]:
        entry: dict[str, Any] = {"issue_id": issue["issue_id"],
                                 "symptom": str(issue.get("symptom", ""))[:200]}
        payload = {
            "request_text": str(issue.get("symptom") or ""),
            "severity": str(issue.get("severity") or "medium"),
            "affected_surface": str(issue.get("affected_surface") or ""),
        }
        try:
            plan_receipt = planner_fn(payload)
            cycle_request = plan_receipt.get("cycle_request")
            if not isinstance(cycle_request, dict):
                raise ValueError("planner returned no cycle_request")
            entry["plan_ok"] = True
        except Exception as exc:
            entry.update({"plan_ok": False, "outcome": "plan_failed",
                          "error": str(exc)[:500]})
            _record_attempt(issue, entry)
            results.append(entry)
            continue
        try:
            # Always the governed DRY-RUN: no execute, no approval/gate/apply
            # tokens. Applying stays with the separately tokened human chain.
            cycle = cycle_fn(cycle_request, dry_run=True, actor="owner_joshua")
        except Exception as exc:
            entry.update({"outcome": "cycle_error", "error": str(exc)[:500]})
            _record_attempt(issue, entry)
            results.append(entry)
            continue
        entry["final_status"] = str(cycle.get("final_status") or "")
        entry["cycle_receipt_path"] = str(cycle.get("cycle_receipt_path") or "")
        if entry["final_status"] == "dry_run_complete":
            issue["status"] = "candidate_ready"
            issue["driver_cycle_receipt"] = entry["cycle_receipt_path"]
            issue["driver_updated_utc"] = _now()
            _save_issue(issue)
            entry["outcome"] = "candidate_ready"
        else:
            entry["outcome"] = "cycle_incomplete"
            _record_attempt(issue, entry)
        results.append(entry)
    return {"draft_results": results, "draft_limit": limit}


def _record_attempt(issue: dict[str, Any], entry: dict[str, Any]) -> None:
    attempts = issue.setdefault("driver_attempts", [])
    attempts.append({"at_utc": _now(), "outcome": entry.get("outcome"),
                     "error": entry.get("error", "")})
    del attempts[:-5]
    issue["driver_updated_utc"] = _now()
    _save_issue(issue)


def backlog_status(report_root: Path) -> dict[str, Any]:
    counts: dict[str, int] = {}
    open_rows = []
    for issue in load_backlog(report_root):
        status = str(issue.get("status") or "unknown")
        counts[status] = counts.get(status, 0) + 1
        if status == "open":
            open_rows.append({
                "issue_id": issue.get("issue_id"),
                "severity": issue.get("severity"),
                "first_seen_utc": issue.get("first_seen_utc"),
                "affected_surface": issue.get("affected_surface"),
                "symptom": str(issue.get("symptom", ""))[:140],
            })
    open_rows.sort(key=lambda r: (_severity_rank(r["severity"]),
                                  str(r["first_seen_utc"] or "")))
    return {"counts": counts, "open_issues": open_rows}


def write_driver_receipt(report_root: Path, payload: dict[str, Any]) -> Path:
    # Fixed safety flags are stamped AFTER the payload so a caller can never
    # override them (this receipt schema promises candidate-only, no apply).
    receipt = {
        **payload,
        "schema": DRIVER_SCHEMA,
        "created_at_utc": _now(),
        "candidate_only": True,
        "trusted_memory_write": False,
        "source_mutation": False,
        "apply_performed": False,
    }
    out_dir = report_root / "receipts"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"ENGEL_BACKLOG_DRIVER_{_stamp()}.json"
    out.write_text(json.dumps(receipt, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


def _cli(argv: list[str] | None = None) -> int:
    import argparse

    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    parser = argparse.ArgumentParser(
        description="Engel self-upgrade backlog driver (groom + bounded dry-run drafting)")
    parser.add_argument("command", choices=["status", "groom", "draft", "drive"])
    parser.add_argument("--limit", type=int, default=DEFAULT_DRAFT_LIMIT,
                        help=f"max issues to draft per invocation (cap {MAX_DRAFT_LIMIT})")
    parser.add_argument("--issue", default="", help="target one issue id")
    parser.add_argument("--resolutions", default="",
                        help="path to an explicit resolutions manifest JSON")
    parser.add_argument("--report-root", default="",
                        help="override the self-upgrade report root (tests)")
    args = parser.parse_args(argv)

    report_root = Path(args.report_root) if args.report_root else system.REPORT_ROOT
    conical_dir = report_root.parent / "conical_jobs"
    resolutions = Path(args.resolutions) if args.resolutions else None

    outcome: dict[str, Any] = {"command": args.command}
    if args.command in {"groom", "drive"}:
        outcome.update(groom(report_root, conical_dir, resolutions))
    if args.command in {"draft", "drive"}:
        outcome.update(draft(report_root, limit=args.limit, issue_id=args.issue))
    if args.command == "status":
        outcome.update(backlog_status(report_root))
    else:
        outcome["backlog_after"] = backlog_status(report_root)["counts"]
        outcome["receipt_path"] = _relative(
            write_driver_receipt(report_root, outcome))
    print(json.dumps(outcome, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
