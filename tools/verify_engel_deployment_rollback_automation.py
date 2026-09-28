#!/usr/bin/env python3
"""Verifier for Engel Deployment Rollback Automation (engel_deployment_rollback_automation.py).

Proves the post-deploy gate closes the self-upgrade safety loop, using synthetic
fixtures under the app root (so path-safety accepts them). Emits {"ok": bool,...};
exit 0 pass / 1 fail.

Invariants (goal: "Code changes carry ... deployment proof, and rollback state."):
  1. All required verifiers PASS -> decision "committed", no rollback, applied file kept.
  2. A required verifier FAILS -> AUTO-ROLLBACK: file restored from backup, restored
     hash matches the recorded pre-apply hash, decision "rolled_back", proof written.
  3. NO verifier coverage on a mutating deploy -> gate FAILS -> rollback (never a
     silent commit).
  4. FAIL-SAFE: a backup whose recorded hash does not match is NOT trusted; the
     automation refuses to overwrite (manual_restore_required) and does not claim
     a clean rollback; the applied file is left untouched.
  5. A durable proof receipt is written for every outcome.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT), str(ROOT / "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

import engel_deployment_rollback_automation as rb  # noqa: E402

CHECKS: list[dict] = []
BEFORE = "PRE-APPLY-CONTENT\n"
AFTER = "MUTATED-APPLIED-CONTENT\n"


def record(name: str, ok: bool, detail: str = "") -> None:
    CHECKS.append({"check": name, "ok": bool(ok), "detail": detail})


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _rel(p: Path) -> str:
    return str(p.relative_to(ROOT)).replace("/", "\\")


def main() -> int:
    fx = ROOT / "runtime" / "temp" / f"rollback_verify_{os.getpid()}"
    fx.mkdir(parents=True, exist_ok=True)
    try:
        target = fx / "apply_target.txt"
        backup = fx / "apply_target.bak"
        # write_bytes (not write_text) so no OS newline translation skews the
        # recorded hashes the automation checks against.
        backup.write_bytes(BEFORE.encode("utf-8"))   # the saved pre-apply copy
        pass_v = fx / "pass_verifier.py"
        fail_v = fx / "fail_verifier.py"
        pass_v.write_text("import sys; sys.exit(0)\n", encoding="utf-8")
        fail_v.write_text("import sys; sys.exit(1)\n", encoding="utf-8")

        def make_receipt(required, backup_sha):
            return {
                "schema": "ENGEL_SELF_UPGRADE_APPLY_RECEIPT_V1",
                "receipt_id": "verify_synthetic_apply",
                "status": "applied",
                "source_mutation": True,
                "rollback_performed": False,
                "required_verifiers": required,
                "changed_files": [{
                    "target_file": _rel(target),
                    "backup_path": _rel(backup),
                    "before_sha256": _sha(BEFORE),
                    "backup_sha256": backup_sha,
                    "after_sha256": _sha(AFTER),
                }],
            }

        rp = fx / "apply_receipt.json"

        # --- 1: all verifiers pass -> committed, applied file kept -----------
        target.write_bytes(AFTER.encode("utf-8"))
        rp.write_text(json.dumps(make_receipt([_rel(pass_v)], _sha(BEFORE))), encoding="utf-8")
        r1 = rb.run_post_deploy_gate(_rel(rp))
        record("all verifiers pass -> committed", r1.get("decision") == "committed" and r1.get("ok") is True, str(r1.get("decision")))
        record("commit keeps the applied file", target.read_text(encoding="utf-8") == AFTER, "")
        record("commit writes a proof receipt", bool(r1.get("proof_receipt")), str(r1.get("proof_receipt")))

        # --- 2: a verifier fails -> auto-rollback to pre-apply state ---------
        target.write_bytes(AFTER.encode("utf-8"))
        rp.write_text(json.dumps(make_receipt([_rel(pass_v), _rel(fail_v)], _sha(BEFORE))), encoding="utf-8")
        r2 = rb.run_post_deploy_gate(_rel(rp))
        record("failed verifier -> decision rolled_back", r2.get("decision") == "rolled_back", str(r2.get("decision")))
        record("rollback restores the pre-apply content", target.read_text(encoding="utf-8") == BEFORE, "")
        restored_ok = bool(r2.get("restores")) and r2["restores"][0].get("matches_pre_apply_state") is True
        record("restore hash matches recorded before_sha256", restored_ok, str(r2.get("restores")))
        record("rollback updates apply receipt", json.loads(rp.read_text(encoding="utf-8")).get("rollback_performed") is True, "")
        record("rollback writes a proof receipt", bool(r2.get("proof_receipt")), "")

        # --- 3: no verifier coverage on a mutating deploy -> rollback --------
        target.write_bytes(AFTER.encode("utf-8"))
        rp.write_text(json.dumps(make_receipt([], _sha(BEFORE))), encoding="utf-8")
        r3 = rb.run_post_deploy_gate(_rel(rp))
        record("no verifier coverage never silently commits",
               r3.get("decision") != "committed" and r3.get("no_verifier_coverage") is True, str(r3.get("decision")))
        record("no-coverage rolls back to pre-apply content", target.read_text(encoding="utf-8") == BEFORE, "")

        # --- 4: FAIL-SAFE: corrupt backup -> manual, applied file untouched --
        target.write_bytes(AFTER.encode("utf-8"))
        rp.write_text(json.dumps(make_receipt([_rel(fail_v)], "deadbeef" * 8)), encoding="utf-8")  # wrong backup hash
        r4 = rb.run_post_deploy_gate(_rel(rp))
        record("corrupt backup flags manual_restore_required",
               bool(r4.get("manual_restore_required")) and r4.get("ok") is False, str(r4.get("decision")))
        record("fail-safe does NOT overwrite from an untrusted backup",
               target.read_text(encoding="utf-8") == AFTER, "applied file must be untouched")
    finally:
        shutil.rmtree(fx, ignore_errors=True)

    failed = [c for c in CHECKS if not c["ok"]]
    receipt = {
        "schema": "engel_deployment_rollback_automation_verifier_v1",
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
