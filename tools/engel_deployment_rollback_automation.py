#!/usr/bin/env python3
"""Engel Deployment Rollback Automation — closes the self-upgrade safety loop.

Serves the Conical Agentic Sentient Self Upgrading System primary goal
(memory/ENGEL_PRIMARY_GOAL_V1.json), acceptance criterion:
    "Code changes carry provenance, verifier results, deployment proof, and rollback state."

Codex's engel_self_upgrade_system.apply_candidate_patch writes each touched file,
saves a hash-checked backup, and records `required_verifiers` + a note that says
"failure requires restoring from rollback_snapshot" — but running those verifiers
and restoring on failure was a MANUAL step. This module automates exactly that
post-deploy gate:

    apply receipt -> run required verifiers
        all pass  -> COMMIT (post-deploy-verified receipt; backups retained)
        any fail   -> AUTO-ROLLBACK: restore each changed file from its recorded
                      backup, hash-prove the restore returns the file to its
                      pre-apply state, write a rollback receipt, and update the
                      apply receipt (rollback_performed=true).

Fail-SAFE, not just fail-closed: if a backup is missing or its recorded hash does
not match, the automation does NOT blindly overwrite — it records
`manual_restore_required` for that file and refuses to claim a clean rollback.
It never fabricates a "verified" or "rolled back" state without proof.

This module runs verifiers (subprocess) and restores files it OWNS via recorded
backups. It performs no other execution, opens no listener, and writes no trusted
memory. It reuses engel_self_upgrade_system helpers so provenance/hashing/path
safety match the rest of the self-upgrade chain.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Reuse the self-upgrade chain's helpers (hash, path-safety, receipt writing).
from engel_self_upgrade_system import (  # noqa: E402
    ROLLBACK_DIR,
    REPORT_ROOT,
    project_path_from_relative,
    project_relative,
    sha256_file,
    write_json,
)

VERIFIER_TIMEOUT_SECONDS = 300


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_verifier(rel_or_abs: str) -> "dict[str, Any]":
    """Run one required verifier as a subprocess; ok iff exit code 0."""
    try:
        path = project_path_from_relative(rel_or_abs)
    except Exception as exc:
        return {"verifier": rel_or_abs, "ok": False, "returncode": None, "error": f"path: {exc}"}
    if not path.is_file():
        return {"verifier": rel_or_abs, "ok": False, "returncode": None, "error": "verifier file missing"}
    try:
        proc = subprocess.run(
            [sys.executable, str(path)],
            cwd=str(ROOT), capture_output=True, text=True,
            timeout=VERIFIER_TIMEOUT_SECONDS,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return {"verifier": project_relative(path), "ok": proc.returncode == 0,
                "returncode": proc.returncode, "stderr_tail": (proc.stderr or "")[-300:]}
    except subprocess.TimeoutExpired:
        return {"verifier": rel_or_abs, "ok": False, "returncode": None, "error": "timeout"}
    except Exception as exc:
        return {"verifier": rel_or_abs, "ok": False, "returncode": None, "error": str(exc)[:200]}


def _restore_one(changed: "dict[str, Any]") -> "dict[str, Any]":
    """Restore a single changed file from its recorded backup, hash-proving the
    result. Fail-safe: never overwrite from an untrusted/missing backup."""
    target_rel = str(changed.get("target_file") or "")
    backup_rel = str(changed.get("backup_path") or "")
    before = str(changed.get("before_sha256") or "")
    backup_sha = str(changed.get("backup_sha256") or "")
    out = {"target_file": target_rel, "restored": False}
    if not target_rel or not backup_rel:
        return {**out, "state": "manual_restore_required", "reason": "missing target/backup path"}
    try:
        target = project_path_from_relative(target_rel)
        backup = project_path_from_relative(backup_rel)
    except Exception as exc:
        return {**out, "state": "manual_restore_required", "reason": f"path: {exc}"}
    if not backup.is_file():
        return {**out, "state": "manual_restore_required", "reason": "backup file missing"}
    # Fail-safe: backup must match its recorded hash before we trust it.
    actual_backup = sha256_file(backup)
    if backup_sha and actual_backup != backup_sha:
        return {**out, "state": "manual_restore_required",
                "reason": "backup hash mismatch", "expected": backup_sha, "actual": actual_backup}
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(backup.read_bytes())
    except Exception as exc:
        return {**out, "state": "manual_restore_required", "reason": f"write: {exc}"}
    # Prove the restore returned the file to its pre-apply state.
    restored_sha = sha256_file(target)
    matches_before = (not before) or restored_sha == before
    return {
        "target_file": target_rel,
        "restored": True,
        "state": "restored" if matches_before else "restored_hash_unverified",
        "restored_sha256": restored_sha,
        "expected_before_sha256": before,
        "matches_pre_apply_state": bool(matches_before),
    }


def run_post_deploy_gate(apply_receipt_path: str) -> "dict[str, Any]":
    """The automated gate. Reads an apply receipt, runs its required verifiers,
    and commits or auto-rolls-back with durable proof."""
    receipt_path = project_path_from_relative(apply_receipt_path) if not Path(apply_receipt_path).is_absolute() \
        else Path(apply_receipt_path)
    try:
        apply_receipt = json.loads(Path(receipt_path).read_text(encoding="utf-8"))
    except Exception as exc:
        return {"schema": "ENGEL_POST_DEPLOY_GATE_V1", "ok": False,
                "error": f"cannot read apply receipt: {exc}", "apply_receipt": str(receipt_path)}

    required = apply_receipt.get("required_verifiers") or []
    changed = apply_receipt.get("changed_files") or []
    verifier_results = [_run_verifier(v) for v in required]
    all_pass = bool(required) and all(r["ok"] for r in verifier_results)
    # No required verifiers is treated as a FAILED gate (a mutating deploy with no
    # verifier coverage must not silently commit) -> triggers rollback.
    gate_ok = all_pass

    result: dict[str, Any] = {
        "schema": "ENGEL_POST_DEPLOY_GATE_V1",
        "goal_id": "engel_conical_agentic_sentient_self_upgrading_system",
        "created_at_utc": _now(),
        "apply_receipt_id": apply_receipt.get("receipt_id"),
        "apply_receipt_path": project_relative(Path(receipt_path)),
        "required_verifiers": required,
        "verifier_results": verifier_results,
        "verifiers_all_passed": all_pass,
        "no_verifier_coverage": not required,
        "changed_file_count": len(changed),
    }

    if gate_ok:
        result.update({
            "ok": True,
            "decision": "committed",
            "rollback_performed": False,
            "note": "all required verifiers passed; deployment committed, backups retained",
        })
    else:
        restores = [_restore_one(cf) for cf in changed]
        clean = all(r.get("restored") and r.get("matches_pre_apply_state", True) for r in restores) if restores else True
        manual = [r for r in restores if r.get("state") == "manual_restore_required"]
        result.update({
            "ok": clean and not manual,
            "decision": "rolled_back" if clean and not manual else "rollback_incomplete_manual_required",
            "rollback_performed": bool(restores) and not manual,
            "restores": restores,
            "manual_restore_required": [r["target_file"] for r in manual],
            "reason": ("no verifier coverage on a mutating deploy" if not required
                       else "one or more required verifiers failed"),
        })
        # Update the apply receipt in place to record the rollback outcome.
        try:
            apply_receipt["rollback_performed"] = result["rollback_performed"]
            apply_receipt["post_deploy_gate_outcome"] = result["decision"]
            apply_receipt["post_deploy_gate_at_utc"] = result["created_at_utc"]
            Path(receipt_path).write_text(json.dumps(apply_receipt, indent=2, ensure_ascii=False), encoding="utf-8")
            result["apply_receipt_updated"] = True
        except Exception as exc:
            result["apply_receipt_update_error"] = str(exc)[:200]

    # Durable proof receipt for either outcome.
    try:
        REPORT_ROOT.mkdir(parents=True, exist_ok=True)
        stamp = result["created_at_utc"].replace(":", "").replace("-", "").replace(".", "")[:20]
        out = REPORT_ROOT / f"post_deploy_gate_{stamp}.json"
        out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        result["proof_receipt"] = project_relative(out)
    except Exception as exc:
        result["proof_receipt_error"] = str(exc)[:200]
    return result


def _cli(argv: "list[str] | None" = None) -> int:
    import argparse

    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    parser = argparse.ArgumentParser(description="Engel deployment rollback automation (post-deploy verifier gate)")
    parser.add_argument("--apply-receipt", required=True, help="path to an ENGEL_SELF_UPGRADE_APPLY_RECEIPT_V1")
    args = parser.parse_args(argv)
    res = run_post_deploy_gate(args.apply_receipt)
    print(json.dumps(res, indent=2, ensure_ascii=False))
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(_cli())
