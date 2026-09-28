#!/usr/bin/env python3
"""Engel Self-Patch Quorum — the multi-member PRE-apply gate.

Serves the Conical Agentic Sentient Self Upgrading System primary goal
(memory/ENGEL_PRIMARY_GOAL_V1.json). It is the safety gate that runs BEFORE a
self-patch is allowed to apply, completing the change-control loop:

    candidate patch
      -> SELF-PATCH QUORUM  (this module: multiple independent members must agree)
      -> apply_candidate_patch (engel_self_upgrade_system: writes files + backups)
      -> DEPLOYMENT ROLLBACK AUTOMATION (post-apply verifier gate + auto-restore)

No single signal may authorize a source-mutating self-patch. Five independent
members vote; EVERY safety member can hard-VETO. The quorum authorizes apply
only when there is no veto AND the allow-vote count meets the threshold. It is
FAIL-CLOSED: any member that errors votes deny+veto — uncertainty never allows.

Members:
  1. verifier_quorum   - the candidate's required_verifiers must ALL pass (each a
                         voter). A source-mutating patch with NO verifier coverage
                         is a hard veto.
  2. permission_authority - the actor must hold matrix authority for the protected
                         apply action (only owner_joshua per the permission matrix).
  3. storage_boundary  - every target file must resolve INSIDE the Engel App root
                         and touch NO permanently-excluded external storage.
  4. human_approval    - a source-mutating fix candidate requires the correct
                         APPROVE_FIX_CANDIDATE token. The memory-promotion token
                         (APPROVE_PROMOTE_MEMORY_CANDIDATE) is explicitly REJECTED
                         here (constitution boundary: those chains are separate).
  5. forbidden_content - the patch must not enable autonomy / provider / network /
                         trusted-memory writes, or touch forbidden storage/devices.

This module DECIDES and writes a gate receipt. It does not itself write patched
source, dispatch, execute arbitrary code, open a listener, or write trusted
memory. It runs the candidate's declared verifiers (subprocess) as evidence.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

from engel_self_upgrade_system import (  # noqa: E402
    is_relative_to,
    project_path_from_relative,
    REPORT_ROOT,
)

FIX_APPROVAL_TOKEN = "APPROVE_FIX_CANDIDATE"
# The memory-promotion token must NEVER authorize a fix apply (CODEX_JOB.md).
MEMORY_PROMOTION_TOKEN = "APPROVE_PROMOTE_MEMORY_CANDIDATE"
PROTECTED_APPLY_ACTION = "approve_protected"
VERIFIER_TIMEOUT_SECONDS = 300

# Permanently-excluded storage (goal + storage-rules memory). A target under any
# of these is a hard veto even if it path-resolves.
FORBIDDEN_STORAGE_MARKERS = ("engel-vault", "powervault", "ct245", "/mnt/engel-vault")

# Content the patch must not introduce (autonomy / network / trusted writes).
FORBIDDEN_CONTENT_PATTERNS = (
    r"trusted_memory_write\s*=\s*True",
    r"ALIVE_STATE",
    r"autonomous_loop",
    r"provider_api_enabled\s*=\s*True",
    r"network_enabled\s*=\s*True",
    r"desktop-fib17o7",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _member(name: str, allow: bool, veto: bool, reason: str, evidence: "dict[str, Any] | None" = None) -> "dict[str, Any]":
    return {"member": name, "vote": "allow" if allow else "deny", "veto": bool(veto and not allow),
            "reason": reason, "evidence": evidence or {}}


def _run_verifier(rel: str) -> "dict[str, Any]":
    try:
        path = project_path_from_relative(rel)
    except Exception as exc:
        return {"verifier": rel, "ok": False, "error": f"path: {exc}"}
    if not path.is_file():
        return {"verifier": rel, "ok": False, "error": "verifier file missing"}
    try:
        proc = subprocess.run([sys.executable, str(path)], cwd=str(ROOT),
                              capture_output=True, text=True, timeout=VERIFIER_TIMEOUT_SECONDS, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return {"verifier": rel, "ok": proc.returncode == 0, "returncode": proc.returncode}
    except Exception as exc:
        return {"verifier": rel, "ok": False, "error": str(exc)[:200]}


def _member_verifier_quorum(candidate: "dict[str, Any]") -> "dict[str, Any]":
    required = candidate.get("required_verifiers") or []
    if not required:
        return _member("verifier_quorum", False, True,
                       "no required verifiers on a source-mutating candidate", {"required": []})
    results = [_run_verifier(v) for v in required]
    all_ok = all(r["ok"] for r in results)
    return _member("verifier_quorum", all_ok, True,
                   "all required verifiers passed" if all_ok else "one or more required verifiers failed",
                   {"results": results, "passed": sum(1 for r in results if r["ok"]), "total": len(results)})


def _member_permission_authority(candidate: "dict[str, Any]") -> "dict[str, Any]":
    actor = str(candidate.get("actor") or "engel_self_agent")
    try:
        import engel_patch_permission_matrix as pm

        matrix = pm.load_matrix()
        decision = pm.decide(matrix, actor=actor, action=PROTECTED_APPLY_ACTION, context={})
        allowed = bool(decision.get("allowed"))
        return _member("permission_authority", allowed, True,
                       f"matrix {decision.get('decision')} for {actor}:{PROTECTED_APPLY_ACTION}",
                       {"actor": actor, "action": PROTECTED_APPLY_ACTION, "decision": decision.get("decision")})
    except Exception as exc:
        return _member("permission_authority", False, True, f"permission matrix error: {exc}", {})


def _member_storage_boundary(candidate: "dict[str, Any]") -> "dict[str, Any]":
    targets = [str(cf.get("target_file") or cf) for cf in (candidate.get("changed_files") or candidate.get("paths") or [])]
    if not targets:
        return _member("storage_boundary", False, True, "candidate declares no target files", {})
    problems = []
    for t in targets:
        low = t.replace("\\", "/").lower()
        if any(mark in low for mark in FORBIDDEN_STORAGE_MARKERS):
            problems.append({"target": t, "why": "forbidden external storage"})
            continue
        try:
            resolved = project_path_from_relative(t)
            if not is_relative_to(resolved, ROOT):
                problems.append({"target": t, "why": "escapes Engel App root"})
        except Exception as exc:
            problems.append({"target": t, "why": f"path error: {exc}"})
    ok = not problems
    return _member("storage_boundary", ok, True,
                   "all targets inside Engel App, none in forbidden storage" if ok else "target boundary violation",
                   {"targets": targets, "problems": problems})


def _member_human_approval(candidate: "dict[str, Any]", approval_token: str) -> "dict[str, Any]":
    requires = bool(candidate.get("human_approval_required") or candidate.get("approval_required")
                    or candidate.get("source_mutation"))
    token = str(approval_token or "").strip()
    if not requires:
        return _member("human_approval", True, False, "no human approval required for this candidate",
                       {"required": False})
    if token == MEMORY_PROMOTION_TOKEN:
        return _member("human_approval", False, True,
                       "memory-promotion token cannot authorize a fix apply (separate chains)",
                       {"required": True, "wrong_token": True})
    if token == FIX_APPROVAL_TOKEN:
        return _member("human_approval", True, False, "valid APPROVE_FIX_CANDIDATE token present",
                       {"required": True})
    return _member("human_approval", False, True,
                   "source-mutating fix requires APPROVE_FIX_CANDIDATE; none present",
                   {"required": True, "token_present": bool(token)})


def _member_forbidden_content(candidate: "dict[str, Any]") -> "dict[str, Any]":
    after_blob = str(candidate.get("patch_content") or candidate.get("diff") or "")
    before_blob = ""
    if isinstance(candidate.get("changed_files"), list):
        for cf in candidate["changed_files"]:
            after_blob += "\n" + str(cf.get("after_content") or cf.get("content") or "")
            before_blob += "\n" + str(cf.get("before_content") or "")
    # The rule is "must not INTRODUCE": a pattern already present in the
    # pre-patch content does not veto; one that first appears with this patch
    # does. With no before_content this stays the original strict scan
    # (fail-closed). Case-insensitive so 'True'/'true' variants all match.
    hits = [p for p in FORBIDDEN_CONTENT_PATTERNS
            if re.search(p, after_blob, re.IGNORECASE)
            and not re.search(p, before_blob, re.IGNORECASE)]
    ok = not hits
    return _member("forbidden_content", ok, True,
                   "no forbidden autonomy/network/trusted-write/forbidden-device content introduced" if ok
                   else "patch introduces forbidden content", {"hits": hits})


def evaluate_quorum(candidate: "dict[str, Any]", *, approval_token: str = "",
                    quorum_threshold: "int | None" = None) -> "dict[str, Any]":
    """Run every quorum member and decide whether apply is authorized.
    apply_allowed iff NO member vetoed AND allow_votes >= threshold."""
    members = []
    for fn in (
        lambda: _member_verifier_quorum(candidate),
        lambda: _member_permission_authority(candidate),
        lambda: _member_storage_boundary(candidate),
        lambda: _member_human_approval(candidate, approval_token),
        lambda: _member_forbidden_content(candidate),
    ):
        try:
            members.append(fn())
        except Exception as exc:  # fail-closed: an erroring member vetoes
            members.append(_member("member_error", False, True, f"member crashed: {exc}", {}))
    allow_votes = sum(1 for m in members if m["vote"] == "allow")
    vetoed = [m["member"] for m in members if m["veto"]]
    threshold = quorum_threshold if quorum_threshold is not None else len(members)
    apply_allowed = (not vetoed) and (allow_votes >= threshold)
    return {
        "schema": "ENGEL_SELF_PATCH_QUORUM_DECISION_V1",
        "goal_id": "engel_conical_agentic_sentient_self_upgrading_system",
        "decided_at_utc": _now(),
        "candidate_id": candidate.get("candidate_id"),
        "apply_allowed": apply_allowed,
        "decision": "apply_authorized" if apply_allowed else "apply_blocked",
        "quorum_threshold": threshold,
        "member_count": len(members),
        "allow_votes": allow_votes,
        "vetoed_by": vetoed,
        "members": members,
        "gate_ordering": "quorum -> apply_candidate_patch -> deployment_rollback_automation",
        "actor_note": "decision/observe + runs declared verifiers; writes no patched source, no trusted memory",
    }


def evaluate_and_record(candidate: "dict[str, Any]", *, approval_token: str = "") -> "dict[str, Any]":
    decision = evaluate_quorum(candidate, approval_token=approval_token)
    try:
        REPORT_ROOT.mkdir(parents=True, exist_ok=True)
        stamp = decision["decided_at_utc"].replace(":", "").replace("-", "").replace(".", "")[:20]
        out = REPORT_ROOT / f"self_patch_quorum_{stamp}.json"
        out.write_text(json.dumps(decision, indent=2, ensure_ascii=False), encoding="utf-8")
        decision["gate_receipt"] = str(out.relative_to(ROOT))
    except Exception as exc:
        decision["gate_receipt_error"] = str(exc)[:200]
    return decision


def _cli(argv: "list[str] | None" = None) -> int:
    import argparse

    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    parser = argparse.ArgumentParser(description="Engel self-patch quorum (pre-apply multi-member gate)")
    parser.add_argument("--candidate", required=True, help="path to a patch candidate JSON")
    parser.add_argument("--approval-token", default="", help="APPROVE_FIX_CANDIDATE when human-approved")
    args = parser.parse_args(argv)
    candidate = json.loads(Path(args.candidate).read_text(encoding="utf-8"))
    res = evaluate_and_record(candidate, approval_token=args.approval_token)
    print(json.dumps(res, indent=2, ensure_ascii=False))
    return 0 if res.get("apply_allowed") else 1


if __name__ == "__main__":
    raise SystemExit(_cli())
