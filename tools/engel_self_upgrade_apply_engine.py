#!/usr/bin/env python3
"""Apply an approved low-risk Engel self-upgrade patch with rollback receipts.

Change-control ordering is ENFORCED here, not documented: this engine refuses
to apply without a matching AUTHORIZED self-patch quorum decision
(ENGEL_SELF_PATCH_QUORUM_DECISION_V1, apply_allowed=true, same candidate_id),
and after a successful apply it always runs the deployment rollback
automation's post-deploy verifier gate — a failed gate auto-restores the
touched files from their hash-checked backups. The single-signal legacy gate
receipt alone can no longer authorize a source mutation.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT), str(ROOT / "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import engel_self_upgrade_system as system
from engel_deployment_rollback_automation import run_post_deploy_gate

QUORUM_DECISION_SCHEMA = "ENGEL_SELF_PATCH_QUORUM_DECISION_V1"


def load_authorized_quorum_decision(path: str, candidate_id: str) -> dict:
    """Fail-closed: the decision must exist, match the schema, authorize apply,
    and be for THIS candidate. Anything else refuses the apply."""
    decision = json.loads(Path(path).read_text(encoding="utf-8"))
    if decision.get("schema") != QUORUM_DECISION_SCHEMA:
        raise system.SelfUpgradeError("quorum decision schema mismatch")
    if decision.get("apply_allowed") is not True:
        raise system.SelfUpgradeError(
            "quorum decision does not authorize apply"
            + (f" (vetoed_by={decision.get('vetoed_by')})" if decision.get("vetoed_by") else ""))
    if str(decision.get("candidate_id") or "") != str(candidate_id):
        raise system.SelfUpgradeError("quorum decision is for a different candidate")
    return decision


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Engel self-upgrade protected apply engine.")
    parser.add_argument("--candidate", required=True, help="Path to an Engel patch candidate JSON.")
    parser.add_argument("--gate-receipt", required=True, help="Path to the approved gate receipt JSON.")
    parser.add_argument("--quorum-decision", required=True,
                        help="Path to the AUTHORIZED self-patch quorum decision JSON for this candidate.")
    parser.add_argument("--patch-file", default=None, help="Path to an Engel file patch JSON. Defaults to candidate.patch_file.")
    parser.add_argument("--approval-token", default="", help="Exact low-risk apply token.")
    parser.add_argument("--skip-post-deploy-gate", action="store_true",
                        help="Skip the post-deploy verifier gate (testing only; the gate is the default).")
    args = parser.parse_args(argv)
    try:
        candidate = system.load_patch_candidate(args.candidate)
        gate_receipt = system.load_gate_receipt(args.gate_receipt)
        quorum_decision = load_authorized_quorum_decision(
            args.quorum_decision, str(candidate.get("candidate_id")))
        patch_file = args.patch_file or candidate.get("patch_file")
        if not patch_file:
            raise system.SelfUpgradeError("patch file required by --patch-file or candidate.patch_file")
        patch = system.load_file_patch(str(patch_file), candidate)
        receipt = system.apply_candidate_patch(
            candidate,
            gate_receipt,
            patch,
            approval_token=args.approval_token,
        )
        receipt["quorum_decision_receipt"] = args.quorum_decision
        receipt["quorum_decided_at_utc"] = quorum_decision.get("decided_at_utc")
        # The post-deploy gate reads required_verifiers from the apply receipt.
        receipt["required_verifiers"] = list(candidate.get("required_verifiers", []))
        path = system.write_apply_receipt(receipt)
    except system.SelfUpgradeError as exc:
        print(f"ENGEL_SELF_UPGRADE_APPLY_ENGINE_ERROR: {exc}", file=sys.stderr)
        return 2
    applied = receipt.get("status") == "applied"
    post_gate = None
    if applied and not args.skip_post_deploy_gate:
        post_gate = run_post_deploy_gate(system.project_relative(path))
    committed = post_gate is None or post_gate.get("decision") == "committed"
    print(json.dumps({
        "ok": applied and committed,
        "apply_receipt_path": system.project_relative(path),
        "apply_receipt": receipt,
        "post_deploy_gate": post_gate,
    }, indent=2, sort_keys=True))
    return 0 if applied and committed else 1


if __name__ == "__main__":
    raise SystemExit(main())
