#!/usr/bin/env python3
"""Serving-side math verdict verifier.

The training gate refuses to LEARN from CAS-refuted maths; `_attach_math_verdict`
records the same verdict on every SERVING receipt so a wrong spoken answer is at
least visible. This gate proves BOTH halves:

  wiring   - the service calls the check at the one finalize chokepoint, after the
             SLM advisory and before persistent memory, with the advisory contract
             (kill-switched, fail-open, ct_math_lane skipped, latency bounded);
  behavior - the underlying verifier refutes what a CAS can prove wrong (plain AND
             LaTeX forms), admits correct maths, invents no claims from prose, and
             returns within its stated budget on pathological input.

Read-only except its own receipt. Loads NO model runtime, imports the answer
verifier only (never the http service module -- importing the service would drag
the full runtime into a gate).

  python tools/verify_engel_math_serving_verdict.py
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

SERVICE_PATH = ROOT / "tools" / "engel_main_server_chat_http_service.py"
RECEIPT_DIR = ROOT / "reports" / "engel_math_serving_verdict"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def main() -> int:
    checks: list[dict[str, str]] = []

    def check(name: str, passed: bool, detail: str) -> None:
        checks.append({"name": name, "status": "PASS" if passed else "FAIL", "detail": detail})
        print(f"{'PASS' if passed else 'FAIL'} {name} :: {detail}")

    source = SERVICE_PATH.read_text(encoding="utf-8")

    # ---- wiring: the chokepoint order is the design -------------------------------
    fn_def = source.find("def _attach_math_verdict(")
    check("service_defines_attach_math_verdict", fn_def != -1,
          "the serving check exists in the chat service")

    finalize = source.find("def _finalize_chat_receipt(", fn_def if fn_def != -1 else 0)
    advisory_call = source.find("_attach_slm_advisory(receipt, prompt, reply)", finalize)
    verdict_call = source.find("_attach_math_verdict(receipt, reply, source)", finalize)
    memory_call = source.find("_ensure_final_chat_memory(receipt, prompt, reply, source)", finalize)
    check("verdict_called_after_advisory_before_memory",
          -1 < advisory_call < verdict_call < memory_call,
          "finalize order: slm advisory -> math verdict -> persistent memory")

    body_end = source.find("def _finalize_chat_receipt(")
    body = source[fn_def:body_end] if -1 < fn_def < body_end else ""
    check("verdict_is_kill_switched",
          'ENGEL_MATH_SERVING_VERDICT_ENABLED' in body,
          "operator can disable the serving check without a deploy")
    check("verdict_skips_ct_math_lane",
          '"ct_math_lane"' in body or "'ct_math_lane'" in body,
          "the deterministic lane is already CAS-verified; re-checking invents junk claims")
    check("verdict_fails_open",
          "except Exception" in body,
          "a serving-side check must never cost a turn")
    check("verdict_bounds_latency",
          "max_claims=" in body,
          "worst case is bounded; a user is waiting on this path")
    check("verdict_never_touches_the_reply",
          "assistant_reply" not in body and "assistant_output_text" not in body,
          "advisory contract: records a verdict, never rewrites what Engel said")

    # ---- behavior: the verdict the receipt will carry -----------------------------
    from engel_math_answer_verifier import verify_reply

    wrong_plain = verify_reply("Result: the derivative of x^2 is 3*x")
    check("refutes_wrong_derivative_plain", bool(wrong_plain["refuted"]),
          f"reason: {wrong_plain['reason'][:100]}")

    wrong_latex = verify_reply(r"The derivative of $x^2$ is $\boxed{3x}$.")
    check("refutes_wrong_derivative_latex", bool(wrong_latex["refuted"]),
          "real chat replies are LaTeX; the check must read them")

    right = verify_reply("Result: the derivative of x^2 is 2*x")
    check("admits_correct_derivative", not right["refuted"],
          "a correct answer is never flagged")

    prose = verify_reply(
        "The build pipeline stages the artifacts, verifies each hash against the "
        "manifest, and restarts the worker when the receipt is green.")
    check("invents_no_claims_from_prose",
          len(prose["claims"]) == 0 and not prose["refuted"],
          f"claims={len(prose['claims'])} on engineering prose")

    t0 = time.perf_counter()
    tower = verify_reply("Result: 9^9^9^9 = 42")
    tower_s = time.perf_counter() - t0
    check("pathological_input_returns_in_budget",
          tower_s < 10.0 and not tower["refuted"],
          f"power tower handled in {tower_s:.2f}s, unproven stays unflagged (fail open)")

    # six real claims, so the cap is actually exercised (a fixture that extracts to
    # zero claims would pass this check without proving anything)
    six_claims = "\n".join(f"The derivative of x^{i} is {i + 1}*x" for i in range(2, 8))
    unbounded = verify_reply(six_claims)
    bounded = verify_reply(six_claims, max_claims=4)
    check("max_claims_bounds_the_work",
          len(unbounded["claims"]) == 6 and len(bounded["claims"]) == 4,
          f"6 claims offered, {len(bounded['claims'])} verified at max_claims=4")

    ok = all(c["status"] == "PASS" for c in checks)
    passed = sum(1 for c in checks if c["status"] == "PASS")
    receipt = {
        "schema": "engel_math_serving_verdict_verify_v1",
        "generated_utc": _now(),
        "ok": ok,
        "passed": passed,
        "failed": len(checks) - passed,
        "service": str(SERVICE_PATH),
        "checks": checks,
    }
    RECEIPT_DIR.mkdir(parents=True, exist_ok=True)
    out = RECEIPT_DIR / f"VERIFY_MATH_SERVING_VERDICT_{_now()}.json"
    out.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    (RECEIPT_DIR / "LATEST.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(f"\n{passed}/{len(checks)} checks passed")
    print(f"verify_engel_math_serving_verdict: {'GREEN' if ok else 'RED'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
