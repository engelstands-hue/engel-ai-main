#!/usr/bin/env python3
"""Verifier for the Engel Self-Patch Quorum (engel_self_patch_quorum.py).

Proves the multi-member pre-apply gate: it AUTHORIZES apply only when every
safety member agrees, and any single member HARD-VETOES. Uses synthetic
candidates + fixture verifiers under the app root. Emits {"ok": bool,...};
exit 0 pass / 1 fail.

Invariants (goal change-control: no single signal authorizes a self-patch):
  1. Fully-approved candidate (owner actor + passing verifier + APPROVE_FIX_CANDIDATE
     + in-root target + clean content) -> apply_authorized.
  2. A FAILED required verifier alone -> apply_blocked (veto).
  3. NO required verifiers on a mutating candidate -> apply_blocked (veto).
  4. Unauthorized actor (not owner) -> apply_blocked (permission veto).
  5. Missing human approval -> apply_blocked.
  6. WRONG token: APPROVE_PROMOTE_MEMORY_CANDIDATE never authorizes a fix apply.
  7. Target in forbidden external storage -> apply_blocked (storage veto).
  8. Forbidden content (trusted-write / autonomy / forbidden device) -> apply_blocked.
  9. Fail-closed: an erroring member vetoes (no allow on uncertainty).
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

import engel_self_patch_quorum as q  # noqa: E402

CHECKS: list[dict] = []


def record(name: str, ok: bool, detail: str = "") -> None:
    CHECKS.append({"check": name, "ok": bool(ok), "detail": detail})


def _rel(p: Path) -> str:
    return str(p.relative_to(ROOT)).replace("/", "\\")


def main() -> int:
    fx = ROOT / "runtime" / "temp" / f"quorum_verify_{os.getpid()}"
    fx.mkdir(parents=True, exist_ok=True)
    try:
        pass_v = fx / "pass_verifier.py"
        fail_v = fx / "fail_verifier.py"
        pass_v.write_text("import sys; sys.exit(0)\n", encoding="utf-8")
        fail_v.write_text("import sys; sys.exit(1)\n", encoding="utf-8")
        good_target = fx / "patched_target.py"
        good_target.write_text("x = 1\n", encoding="utf-8")

        def cand(**over):
            base = {
                "candidate_id": "c",
                "source_mutation": True,
                "human_approval_required": True,
                "actor": "owner_joshua",
                "required_verifiers": [_rel(pass_v)],
                "changed_files": [{"target_file": _rel(good_target), "after_content": "x = 1\n"}],
            }
            base.update(over)
            return base

        FIX = "APPROVE_FIX_CANDIDATE"
        MEM = "APPROVE_PROMOTE_MEMORY_CANDIDATE"

        # 1. fully approved -> authorized
        d = q.evaluate_quorum(cand(), approval_token=FIX)
        record("fully-approved candidate is authorized", d["apply_allowed"] is True and not d["vetoed_by"], str(d["vetoed_by"]))

        # 2. failed verifier -> blocked
        d = q.evaluate_quorum(cand(required_verifiers=[_rel(pass_v), _rel(fail_v)]), approval_token=FIX)
        record("a failed verifier blocks apply", d["apply_allowed"] is False and "verifier_quorum" in d["vetoed_by"], str(d["vetoed_by"]))

        # 3. no verifiers -> blocked
        d = q.evaluate_quorum(cand(required_verifiers=[]), approval_token=FIX)
        record("no verifier coverage blocks apply", d["apply_allowed"] is False and "verifier_quorum" in d["vetoed_by"], "")

        # 4. unauthorized actor -> blocked
        d = q.evaluate_quorum(cand(actor="engel_self_agent"), approval_token=FIX)
        record("unauthorized actor blocks apply", d["apply_allowed"] is False and "permission_authority" in d["vetoed_by"], str(d["vetoed_by"]))

        # 5. missing approval -> blocked
        d = q.evaluate_quorum(cand(), approval_token="")
        record("missing human approval blocks apply", d["apply_allowed"] is False and "human_approval" in d["vetoed_by"], "")

        # 6. wrong token (memory promotion) -> blocked
        d = q.evaluate_quorum(cand(), approval_token=MEM)
        record("memory-promotion token never authorizes a fix apply",
               d["apply_allowed"] is False and "human_approval" in d["vetoed_by"], "")

        # 7. forbidden storage target -> blocked
        d = q.evaluate_quorum(cand(changed_files=[{"target_file": "reports\\engel-vault\\x.py"}]), approval_token=FIX)
        record("forbidden external-storage target blocks apply",
               d["apply_allowed"] is False and "storage_boundary" in d["vetoed_by"], str(d["vetoed_by"]))

        # 8. forbidden content -> blocked
        d = q.evaluate_quorum(cand(changed_files=[{"target_file": _rel(good_target), "after_content": "trusted_memory_write = True\n"}]), approval_token=FIX)
        record("forbidden content blocks apply", d["apply_allowed"] is False and "forbidden_content" in d["vetoed_by"], str(d["vetoed_by"]))

        # 8b. PRE-EXISTING forbidden mention does not veto (rule is "introduce")
        d = q.evaluate_quorum(cand(changed_files=[{
            "target_file": _rel(good_target),
            "before_content": "docs: the forbidden node is desktop-fib17o7\nx = 1\n",
            "after_content": "docs: the forbidden node is desktop-fib17o7\nx = 2\n"}]), approval_token=FIX)
        record("pre-existing forbidden mention does not veto (only introduced content does)",
               d["apply_allowed"] is True and "forbidden_content" not in d["vetoed_by"], str(d["vetoed_by"]))

        # 8c. NEWLY introduced pattern still vetoes even with before_content present
        d = q.evaluate_quorum(cand(changed_files=[{
            "target_file": _rel(good_target),
            "before_content": "x = 1\n",
            "after_content": "x = 1\nautonomous_loop = start()\n"}]), approval_token=FIX)
        record("introduced forbidden pattern vetoes even with before_content",
               d["apply_allowed"] is False and "forbidden_content" in d["vetoed_by"], str(d["vetoed_by"]))

        # 9. fail-closed: a member that raises -> veto. Monkeypatch one member to raise.
        orig = q._member_storage_boundary
        q._member_storage_boundary = lambda c: (_ for _ in ()).throw(RuntimeError("boom"))
        try:
            d = q.evaluate_quorum(cand(), approval_token=FIX)
            record("erroring member fails closed (vetoes)", d["apply_allowed"] is False and bool(d["vetoed_by"]), str(d["vetoed_by"]))
        finally:
            q._member_storage_boundary = orig
    finally:
        shutil.rmtree(fx, ignore_errors=True)

    failed = [c for c in CHECKS if not c["ok"]]
    receipt = {
        "schema": "engel_self_patch_quorum_verifier_v1",
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
