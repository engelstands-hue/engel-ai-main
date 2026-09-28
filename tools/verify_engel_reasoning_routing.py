#!/usr/bin/env python3
"""Verify conceptual/teaching math reaches a reasoning lane, not the default 7B (2026-07-31).

Root cause this locks down: `detect_math_reasoning_request` — the only non-explicit path
to a real reasoning model — requires a DIGIT in the prompt (engel_math_lane.py ~line 170).
Every conceptual question ("explain the chain rule", "derive why induction works") failed
that gate structurally and fell through to the default aligned 7B, the weakest model in
the fleet at exactly the questions that need reasoning.

Gates:
  1. Conceptual math is now detected (the digit gate no longer excludes it).
  2. Engel-ops phrasing is still NOT detected — the figurative/software denylist must
     hold, or "explain the deploy pipeline" starts costing minutes on a CPU reasoner.
  3. The two-signal NEAR binding holds (bag-of-words co-occurrence must not route).
  4. The service consults the new detector AND an explicit route hint.
  5. The reasoning dispatch is DIRECT — it must never route by setting
     `_escalate_past_quick`, because the specialist lanes are guarded by
     `not request.get("_escalate_past_quick")` and that flag would SKIP them.
  6. Fail-open: a detector exception leaves the turn as normal chat.
  7. The word-problem path is unchanged (no regression to the shipped behaviour).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
for _p in (ROOT, TOOLS):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import engel_math_lane as ml  # noqa: E402

SERVICE_SRC = (TOOLS / "engel_main_server_chat_http_service.py").read_text(
    encoding="utf-8", errors="replace"
)

checks: list[dict[str, object]] = []


def check(name: str, ok: bool, detail: str) -> None:
    checks.append({"name": name, "status": "PASS" if ok else "FAIL", "detail": detail})


CONCEPTUAL = [
    "Explain the chain rule and why it works.",
    "Can you teach me proof by induction?",
    "Derive the quadratic formula.",
    "Why does the determinant of a singular matrix equal zero?",
    "Walk me through eigenvalues and eigenvectors.",
    "Explain modular arithmetic and congruence.",
    "How do integrals relate to derivatives?",
    "Prove the theorem about infinitely many primes.",
    "Explain the intuition behind Bayes and probability distribution.",
    "Why is the standard deviation the square root of variance?",
]

# Engel-ops phrasing that must stay ordinary chat. Every one of these contains a
# teaching verb; only the OBJECT distinguishes them from real math.
OPS_PHRASING = [
    "Explain the deploy pipeline and why it fails.",
    "Why does the training limit apply to the fleet roster?",
    "Walk me through the build lane config.",
    "How does the chat model handle a receipt?",
    "Explain the verifier gate for the dataset.",
    "Prove the deploy script works end to end.",
    "Why is the GPU latency so high on this worker?",
    "Teach me how the Meeting Room bridge works.",
    "Explain how to integrate the SLM into chat.",
    "Walk me through the backlog and the cron task queue.",
    "Explain the proof requirement in the training contract.",
    "Why is the sparse MoE lane slower than the GPU lane?",
]


def main() -> int:
    detected = [p for p in CONCEPTUAL if ml.detect_teaching_math_request(p)]
    check(
        "conceptual_math_detected",
        len(detected) == len(CONCEPTUAL),
        f"{len(detected)}/{len(CONCEPTUAL)} conceptual math prompts route to reasoning",
    )

    false_pos = [p for p in OPS_PHRASING if ml.detect_teaching_math_request(p)]
    check(
        "ops_phrasing_not_hijacked",
        not false_pos,
        f"{len(false_pos)} false positives on Engel-ops phrasing (must be 0): {false_pos[:2]}",
    )

    # the old detector genuinely excluded these — proves the digit gate was the blocker
    old_missed = [p for p in CONCEPTUAL if not ml.detect_math_reasoning_request(p)]
    check(
        "digit_gate_was_the_blocker",
        len(old_missed) >= len(CONCEPTUAL) - 1,
        f"{len(old_missed)}/{len(CONCEPTUAL)} were excluded by the pre-fix digit gate",
    )

    # two-signal NEAR binding: verb and concept far apart must NOT route
    far = (
        "Explain the deploy rollback procedure for the worker fleet in detail. "
        + ("Filler about receipts and lanes and ports. " * 4)
        + "Separately, a derivative is involved somewhere."
    )
    check(
        "near_binding_enforced",
        ml.detect_teaching_math_request(far) is False,
        "a teaching verb far from the math concept must not route (no bag-of-words)",
    )

    # word-problem path unchanged
    check(
        "word_problem_path_unchanged",
        ml.detect_math_reasoning_request(
            "If a tank drains 12 liters per minute, how long for 300 liters?"
        )
        is True,
        "the shipped numeric word-problem route must still fire",
    )
    check(
        "figurative_denylist_intact",
        ml.detect_math_reasoning_request("Can you factor in the GPU cost for 3 workers?")
        is False,
        "figurative math verbs must still be refused",
    )

    # service wiring
    check(
        "service_consults_teaching_detector",
        "detect_teaching_math_request" in SERVICE_SRC,
        "chat service must consult the conceptual-math detector",
    )
    check(
        "service_honours_route_hint",
        '"route_hint"' in SERVICE_SRC or "'route_hint'" in SERVICE_SRC,
        "chat service must honour an explicit declared route hint",
    )
    check(
        "teaching_lane_kill_switch",
        "ENGEL_TEACHING_MATH_LANE_ENABLED" in SERVICE_SRC,
        "the new lane must be flag-gated so it reverts to prior behaviour",
    )

    # the dispatch must be DIRECT, never via the escalate flag
    block = SERVICE_SRC.split("needs_math_reasoning = math_turn ==", 1)
    ok_direct = False
    if len(block) > 1:
        seg = block[1].split("install_turn = _model_install_action", 1)[0]
        ok_direct = (
            "_math_reasoning_receipt(prompt, started)" in seg
            and "_escalate_past_quick" not in seg
        )
    check(
        "reasoning_dispatch_is_direct",
        ok_direct,
        "must call the specialist receipt directly; setting _escalate_past_quick would "
        "SKIP the specialist lanes (they are guarded by `not _escalate_past_quick`)",
    )

    # fail-open: the detector is wrapped so an exception becomes normal chat
    check(
        "detector_fails_open",
        re.search(
            r"except Exception:.*?#\s*noqa: BLE001 — detector failure = normal chat",
            SERVICE_SRC,
            re.S,
        )
        is not None,
        "a detector exception must fall through to normal chat, never raise into a turn",
    )

    passed = sum(1 for c in checks if c["status"] == "PASS")
    total = len(checks)
    print(
        json.dumps(
            {
                "schema": "engel_reasoning_routing_verifier_v1",
                "ok": passed == total,
                "passed": passed,
                "total": total,
                "checks": checks,
            },
            indent=2,
        )
    )
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
