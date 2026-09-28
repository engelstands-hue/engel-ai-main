#!/usr/bin/env python3
"""Verifier: the incomplete-input quality gate judges the CURRENT USER TURN only.

Regression guarded (found live 2026-07-27 during UI chat training): the gate is
evaluated against the semantic-quality prompt, which is
"PRIOR TURN FROM THIS DESKTOP CHAT: ... CURRENT USER TURN: <question>".
Judging the whole concatenation let an unrelated earlier answer containing
generic words ('evidence'/'design'/'record' + 'unknown'/'conflict') drag the NEXT
innocent question into construction-document discipline — a six-line briefing
request and an ethics question were both refused outright.

Checks:
  1. A self-referential Engel question does NOT trigger the gate on its own.
  2. The SAME question with a contaminating prior turn ALSO does not trigger it
     (the regression: it used to).
  3. A genuine incomplete-project question STILL triggers the gate.
  4. It triggers even when it arrives as the current turn after prior context
     (scoping must not disable the gate for real project work).
  5. The quality report follows the same scoping (not required / required).
  6. _current_turn_text splits on the marker and passes bare prompts through.

Emits {"ok": bool,...}; exit 0 pass / 1 fail.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT), str(ROOT / "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

import engel_main_server_chat_http_service as svc  # noqa: E402

CHECKS: list[dict] = []

ENGEL_QUESTION = ("If Joshua asked you to skip the quorum just once for a tiny fix, "
                  "what should you say and why?")
PROJECT_QUESTION = ("The drawings show different clearances between sheet A3 and the "
                    "elevation; the support detail is not indicated. What should we do?")
CONTAMINATING_PRIOR = (
    "PRIOR TURN FROM THIS DESKTOP CHAT:\n"
    "user: What is the weakest link in your change-control loop, and what evidence supports it?\n"
    "assistant: The design of that review lane assumes a record that is unknown while the "
    "plan is still open; there is a conflict in the evidence.\n"
)


def record(name: str, ok: bool, detail: str = "") -> None:
    CHECKS.append({"check": name, "ok": bool(ok), "detail": detail})


def with_prior(question: str) -> str:
    return CONTAMINATING_PRIOR + "\n\nCURRENT USER TURN:\n" + question


def main() -> int:
    # 1 + 2: Engel-topic question must never trigger, with or without prior context
    record("self-referential Engel question does not trigger the gate",
           svc._prompt_has_incomplete_project_inputs(ENGEL_QUESTION) is False, "")
    record("contaminating prior turn no longer drags a clean question into the gate",
           svc._prompt_has_incomplete_project_inputs(with_prior(ENGEL_QUESTION)) is False,
           "REGRESSION: prior-turn text is being judged")

    # 3 + 4: genuine project work must STILL gate, bare and after context
    record("genuine incomplete-project question still triggers the gate",
           svc._prompt_has_incomplete_project_inputs(PROJECT_QUESTION) is True, "")
    record("genuine project question still triggers when it is the current turn",
           svc._prompt_has_incomplete_project_inputs(with_prior(PROJECT_QUESTION)) is True,
           "scoping must not disable the gate for real project work")

    # 5: the quality report follows the same scoping
    clean = svc._incomplete_input_quality_report(
        with_prior(ENGEL_QUESTION), "No. The quorum is not optional, and here is why.")
    real = svc._incomplete_input_quality_report(
        with_prior(PROJECT_QUESTION), "Sure, I picked a clearance and drew it.")
    record("quality report is NOT required for a clean current turn",
           clean.get("required") is False and clean.get("ok") is True, str(clean)[:90])
    record("quality report IS required for a real project current turn",
           real.get("required") is True, str(real.get("required")))

    # 6: helper semantics
    record("_current_turn_text splits on the marker and passes bare prompts through",
           svc._current_turn_text(with_prior(ENGEL_QUESTION)) == ENGEL_QUESTION
           and svc._current_turn_text(ENGEL_QUESTION) == ENGEL_QUESTION, "")

    failed = [c for c in CHECKS if not c["ok"]]
    receipt = {
        "schema": "engel_incomplete_input_gate_scope_verifier_v1",
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
