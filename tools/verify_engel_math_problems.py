"""Gate for ground-truth math grading (tools/engel_math_problems.py).

This module decides whether a math answer is RIGHT, and a wrong verdict costs a training
row its admission. That makes two failure directions dangerous in opposite ways:

  Too lenient  -> wrong mathematics enters the corpus and teaches confident error.
  Too strict   -> correct mathematics is thrown away and the model is trained against its
                  own correct method, which is the worse of the two.

So every check below is paired: the wrong answer must be caught AND the correct answer, in
whatever reasonable form a model writes it, must survive.

It also gates the honesty property: a proof has no decidable answer, and the module must say
so rather than grade it as verified. A corpus that cannot distinguish "checked against a
known result" from "looked well-formed" cannot weight them apart later.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import engel_math_problems as mp  # noqa: E402
import run_engel_flutter_main_ui_prompt_training as runner  # noqa: E402

checks: list[dict] = []


def check(name: str, ok: bool, detail: str) -> None:
    checks.append({"name": name, "status": "PASS" if ok else "FAIL", "detail": detail})


def prompt_for(problem: mp.MathProblem) -> str:
    return f"Training task:\n{problem.question}\nAnswer in the Result/Work/Check form."


# --- 1. the problem set itself ----------------------------------------------------
check("problem_ids_unique",
      len({p.problem_id for p in mp.PROBLEMS}) == len(mp.PROBLEMS),
      "every problem needs a unique id so a verdict names one question")
check("has_decidable_and_undecidable",
      len(mp.DECIDABLE) >= 10 and len(mp.UNDECIDABLE) >= 1,
      f"need a real decidable set plus honest undecidable ones; got "
      f"{len(mp.DECIDABLE)}/{len(mp.UNDECIDABLE)}")
check("decidable_problems_declare_an_answer",
      all(p.answer.strip() for p in mp.DECIDABLE),
      "a decidable problem with no declared answer cannot grade anything")
check("undecidable_problems_declare_no_answer",
      all(not p.answer.strip() and p.note for p in mp.UNDECIDABLE),
      "an undecidable problem must carry a reason instead of a fake answer")

# Every declared answer must itself be reachable by the CAS -- a ground truth the verifier
# cannot parse would silently mark every correct reply wrong.
unparsable = []
for problem in mp.DECIDABLE:
    if problem.kind == "set":
        parts = [x.strip() for x in problem.answer.split(",")]
    else:
        parts = [problem.answer]
    for part in parts:
        try:
            import engel_math_answer_verifier as mav
            if mav._parse(part) is None:
                unparsable.append((problem.problem_id, part))
        except Exception as exc:  # pragma: no cover
            unparsable.append((problem.problem_id, f"{part} ({exc})"))
check("every_declared_answer_parses", not unparsable,
      f"a ground truth the CAS cannot parse would fail every correct reply; {unparsable[:3]}")

# --- 2. catches wrong answers ------------------------------------------------------
WRONG = {
    "alg-01": "Result: x = 7\nWork: 3x = 21\nCheck: substituted back, 3*7 + 4 = 25",
    "cal-01": "Result: 6x + 5\nWork: power rule\nCheck: evaluated at x=1, 6*1 + 5 = 11",
    "lin-01": "Result: 10\nWork: 2*3 + 4*1 = 10\nCheck: recomputed, 2*3 + 4 = 10",
    "num-02": "Result: 6\nWork: listed divisors\nCheck: recomputed, 6*2 = 12",
}
for pid, reply in WRONG.items():
    problem = mp.BY_ID[pid]
    verdict, detail = mp.verify_against_truth(reply, problem)
    check(f"catches_wrong[{pid}]", verdict == mp.VERDICT_WRONG,
          f"a wrong answer to {problem.question!r} must be caught; got {verdict} ({detail})")

# --- 3. does NOT reject correct answers, in the forms models actually write --------
RIGHT = {
    "alg-01": [
        "Result: x = 5\nWork: 3x = 15\nCheck: substituted back, 3*5 + 4 = 19",
        "Result: 5\nWork: 3x = 15 so x = 5\nCheck: recomputed, 3*5 + 4 = 19",
        "Result: The solution is x = 5.\nWork: subtract 4, divide by 3\nCheck: 3*5 + 4 = 19",
    ],
    "cal-01": [
        "Result: 6x + 2\nWork: power rule\nCheck: evaluated at x=1, 6*1 + 2 = 8",
        "Result: dy/dx = 6x + 2\nWork: term by term\nCheck: recomputed at x=2, 6*2 + 2 = 14",
    ],
    "lin-02": [
        "Result: -2\nWork: 1*4 - 2*3 = -2\nCheck: recomputed, 4 - 6 = -2",
    ],
    "cnt-01": [
        "Result: 35\nWork: C(7,3) = 7!/(3!4!)\nCheck: recomputed, 210/6 = 35",
    ],
    "prb-01": [
        "Result: 3/8\nWork: C(4,2)/16 = 6/16\nCheck: recomputed, 6/16 = 3/8",
    ],
}
for pid, replies in RIGHT.items():
    problem = mp.BY_ID[pid]
    for index, reply in enumerate(replies):
        verdict, detail = mp.verify_against_truth(reply, problem)
        check(f"accepts_correct[{pid}#{index}]", verdict == mp.VERDICT_CORRECT,
              f"a correct answer must not be marked wrong; got {verdict} ({detail})")

# The deterministic lane serves everything on ONE line, Check prose included; the stated
# answer must not drag the check's own numbers into comparison (a live correct x = 5 was
# graded wrong against the check's trailing "0" before the section cut, 2026-08-08).
lane_form = mp.verify_against_truth(
    "Verified math result: x = 5. Check: all 1 root(s) substituted back; residuals are "
    "exactly 0. Computed exactly by Engel's deterministic math lane.",
    mp.BY_ID["alg-01"])
check("accepts_lane_single_line_form", lane_form[0] == mp.VERDICT_CORRECT,
      f"the lane's one-line serving format must grade by its Result value; got {lane_form}")
lane_wrong = mp.verify_against_truth(
    "Verified math result: x = 7. Check: all 1 root(s) substituted back; residuals are "
    "exactly 0.",
    mp.BY_ID["alg-01"])
check("lane_single_line_wrong_still_caught", lane_wrong[0] == mp.VERDICT_WRONG,
      f"the section cut must not blunt wrong-answer detection; got {lane_wrong}")

# multi-root sets
roots_ok = mp.verify_against_truth(
    "Result: x = 2 and x = 3\nWork: factored (x-2)(x-3)\nCheck: substituted both, 2*3 = 6",
    mp.BY_ID["alg-02"])
check("accepts_correct_root_set", roots_ok[0] == mp.VERDICT_CORRECT,
      f"both roots stated must be accepted; got {roots_ok}")
roots_bad = mp.verify_against_truth(
    "Result: x = 2 and x = 5\nWork: factored\nCheck: substituted, 2*5 = 10",
    mp.BY_ID["alg-02"])
check("catches_wrong_root_set", roots_bad[0] == mp.VERDICT_WRONG,
      f"a wrong root must be caught; got {roots_bad}")

# --- 4. honesty about the undecidable ---------------------------------------------
proof = mp.BY_ID["prf-01"]
verdict, _ = mp.verify_against_truth(
    "Result: the sum of two even integers is even\nWork: 2a + 2b = 2(a+b)\n"
    "Check: recomputed, 2*(1+2) = 6", proof)
check("proof_is_undecidable_not_wrong", verdict == mp.VERDICT_UNDECIDABLE,
      f"a proof must be reported undecidable, never graded wrong; got {verdict}")
graded = mp.grade_reply("Result: anything\nWork: x\nCheck: 1 = 1", prompt_for(proof))
check("proof_never_counts_as_exactly_verified",
      graded["exactly_verified"] is False and graded["wrong"] is False,
      "an undecidable problem must be neither 'verified' nor 'wrong'")

# --- 5. an unknown prompt is not graded against someone else's answer -------------
unknown = mp.grade_reply("Result: 42\nWork: none\nCheck: 1 = 1", "Solve some other problem entirely.")
check("unknown_prompt_is_not_graded",
      unknown["matched"] is False and unknown["wrong"] is False,
      "a prompt outside the set must fall through to form grading, never be marked wrong")
check("no_result_line_is_not_wrong",
      mp.verify_against_truth("I am not sure about this one.", mp.BY_ID["alg-01"])[0]
      == mp.VERDICT_NO_ANSWER,
      "a missing Result line is 'no answer found', not a wrong answer")

# --- 6. the LIVE gate rejects a wrong answer and keeps a right one ----------------
def eligibility(reply: str, prompt: str) -> dict:
    result = {
        "status": "DONE", "base_prompt": prompt,
        "wrapper_receipt": {"assistant_reply": reply}, "wrapper_receipt_path": "x",
        "local_only_training": True, "training_sample_eligible": True,
    }
    runner._apply_discipline_eligibility(result, "math")
    return result

wrong_live = eligibility(WRONG["alg-01"], prompt_for(mp.BY_ID["alg-01"]))
check("live_gate_rejects_wrong_answer",
      wrong_live.get("training_sample_eligible") is False
      and wrong_live.get("math_truth_verdict") == "wrong",
      "the live math gate must refuse an answer that contradicts the known result")
right_live = eligibility(RIGHT["alg-01"][0], prompt_for(mp.BY_ID["alg-01"]))
check("live_gate_admits_correct_answer",
      right_live.get("training_sample_eligible") is True
      and right_live.get("math_exactly_verified") is True,
      "a correct answer must stay admitted and be stamped exactly verified")
proof_live = eligibility(
    "Result: the sum of two even integers is even\nWork: 2a + 2b = 2(a+b)\n"
    "Check: recomputed, 2*(1+2) = 6", prompt_for(proof))
check("live_gate_admits_proof_without_claiming_verification",
      proof_live.get("training_sample_eligible") is True
      and proof_live.get("math_exactly_verified") is False,
      "a proof stays trainable on form but must never be stamped exactly verified")

failed = sum(1 for c in checks if c["status"] != "PASS")
print(json.dumps(
    {
        "schema": "engel_math_problems_verifier_v1",
        "status": "FAIL" if failed else "PASS",
        "passed": len(checks) - failed,
        "total": len(checks),
        "decidable": len(mp.DECIDABLE),
        "undecidable": len(mp.UNDECIDABLE),
        "checks": checks,
    },
    indent=2,
))
raise SystemExit(1 if failed else 0)
