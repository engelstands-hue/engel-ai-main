#!/usr/bin/env python3
"""NT-2 verifier — fire-past-threshold quick-lane escalation.

Read-only, no model runtime, no provider calls. Emits a receipt. ok=True iff:
  (a) _quick_lane_confidence scores a clean reply high and a degenerate one low,
  (b) the confidence gate is default-OFF (ENGEL_QUICK_LANE_ESCALATION_ENABLED unset -> accept),
  (c) with the flag ON, a sub-tau reply escalates (accept -> False) and a clean one is kept,
  (d) fail-open: a raising/empty case still returns accept (True),
  (e) an escalated turn sets the loop guard so it can't re-enter the quick lane.

  python tools/verify_nt2_quick_lane_escalation.py
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
RECEIPT_DIR = ROOT / "reports" / "engel_nt2_quick_lane_escalation"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


CLEAN = "Yes — the tunnel is live and the chat service is healthy. Want me to check the GPU lane next?"
DEGENERATE = "I think I think I think I think I think I think I think I think I think"
DEGENERATE_TERMINAL = DEGENERATE + "."
TRUNCATED = "Sure, here is the function:\n```python\ndef f(x):\n    return x +"


def main() -> int:
    failures: list[str] = []
    import_ok = False
    try:
        import engel_main_server_chat_http_service as svc  # noqa: E402
        import_ok = True
    except Exception as exc:
        failures.append(f"import failed: {exc}")

    if import_ok:
        conf = svc._quick_lane_confidence
        accept = svc._quick_reply_accept
        tau = svc._QUICK_LANE_ESCALATION_TAU

        # (a) confidence separates clean from degenerate
        c_clean, _ = conf("you good engel?", CLEAN)
        c_deg, _ = conf("explain the routing design in detail", DEGENERATE)
        c_trunc, _ = conf("write a function", TRUNCATED)
        if not (c_clean >= tau):
            failures.append(f"clean reply confidence {c_clean:.2f} should be >= tau {tau}")
        if not (c_deg < tau):
            failures.append(f"degenerate reply confidence {c_deg:.2f} should be < tau {tau}")
        if not (c_trunc < tau):
            failures.append(f"truncated reply confidence {c_trunc:.2f} should be < tau {tau}")

        # (b) default OFF -> always accept, reply never altered, but shadow telemetry stamped
        os.environ.pop("ENGEL_QUICK_LANE_ESCALATION_ENABLED", None)
        r = {"assistant_reply": DEGENERATE_TERMINAL, "ok": True}
        req = {}
        if accept("explain in detail", req, r) is not True:
            failures.append("flag OFF: degenerate reply should still be ACCEPTED (byte-invariance)")
        if "quick_lane_confidence" not in r:
            failures.append("flag OFF: shadow confidence telemetry not stamped")
        if req.get("_escalate_past_quick"):
            failures.append("flag OFF: must NOT set the escalation guard")

        # An explicit request for a useful automation question is a semantic
        # contract. A reply about chat repetition must always reach the large
        # local lane, even when threshold-based escalation is disabled.
        requested_question = "What is one useful question you could ask before automating a repeated task?"
        off_topic = "It was repeating because casual chat was falling back to canned lines."
        rq = {"assistant_reply": off_topic, "ok": True}
        qq = {}
        if accept(requested_question, qq, rq) is not False:
            failures.append("requested automation question: off-topic quick reply should ESCALATE")
        if "requested automation question" not in str(rq.get("quick_lane_forced_escalation_reason") or ""):
            failures.append("requested automation question: forced reason was not recorded")

        # (c) flag ON -> degenerate escalates, clean kept
        os.environ["ENGEL_QUICK_LANE_ESCALATION_ENABLED"] = "1"
        r2 = {"assistant_reply": DEGENERATE, "ok": True}
        req2 = {}
        if accept("explain in detail", req2, r2) is not False:
            failures.append("flag ON: degenerate reply should ESCALATE (accept -> False)")
        if req2.get("_escalate_past_quick") is not True:
            failures.append("flag ON: escalation must set _escalate_past_quick loop guard")
        if req2.get("_engel_escalated_from") != 1:
            failures.append("flag ON: escalation must mark _engel_escalated_from=1 (quick->big)")
        r3 = {"assistant_reply": CLEAN, "ok": True}
        req3 = {}
        if accept("you good?", req3, r3) is not True:
            failures.append("flag ON: clean reply should be KEPT (accept -> True)")

        os.environ.pop("ENGEL_QUICK_LANE_ESCALATION_ENABLED", None)

        # (d) fail-open: an internal exception (e.g. a non-dict receipt) must return accept (True),
        # so a bug in the gate can never break a turn — it degrades to current behaviour.
        if accept("x", {}, None) is not True:
            failures.append("fail-open: an exception in the gate must return accept (True)")

    ok = not failures
    receipt = {
        "schema": "engel_nt2_quick_lane_escalation_receipt_v1",
        "task": "NT-2 fire-past-threshold escalation",
        "created_at_utc": _now(),
        "ok": ok,
        "import_ok": import_ok,
        "failures": failures,
        "read_only": True,
        "model_runtime_loaded": False,
        "provider_calls_made": False,
    }
    RECEIPT_DIR.mkdir(parents=True, exist_ok=True)
    rp = RECEIPT_DIR / f"ENGEL_NT2_QUICK_LANE_ESCALATION_{_now()}.json"
    rp.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"NT-2 verifier: {'PASS' if ok else 'FAIL'}  ({len(failures)} failures)")
    for f in failures:
        print("  !!", f)
    print(f"  receipt: {rp}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
