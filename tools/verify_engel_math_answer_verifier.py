"""Gate for CAS correctness verification of math answers (tools/engel_math_answer_verifier.py).

Two properties matter, and they pull in opposite directions:

  IT MUST CATCH WRONG MATH. Before this module, the math admit gate passed x=4 for 2x+1=7,
  d/dx x^2 = 3x, and integral 2x dx = x^3, because each carried an internally-consistent
  Check. Training on those teaches that verification-shaped prose is verification.

  IT MUST NOT REJECT CORRECT MATH. A false refutation is worse than a missed one: it deletes
  a good sample AND trains against a correct method. So every ambiguous, unparsed or
  expensive case must come back "unverified", never "refuted".

Plus the safety property, because this module eats untrusted model text: parse_expr_safe is
a BLOCKLIST and arbitrary execution is reachable through it (globals() composed with chr()),
so nothing may reach the parser without clearing a strict whitelist first.

All offline. No model, no network.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import engel_math_answer_verifier as mav  # noqa: E402
import run_engel_flutter_main_ui_prompt_training as runner  # noqa: E402

checks: list[dict] = []


def check(name: str, ok: bool, detail: str) -> None:
    checks.append({"name": name, "status": "PASS" if ok else "FAIL", "detail": detail})


# --- 1. SAFETY: untrusted text must never reach the parser as code ----------------
# parse_expr_safe's filter is a blocklist and sympy's parser exposes the whole sympy
# namespace plus builtins by bare name. The exploit is real: globals() composed with chr()
# yields eval in 72 characters. The whitelist below is what stands in front of it.
DANGEROUS = [
    "globals()",
    "globals()[(chr(101)+chr(118)+chr(97)+chr(108))]",
    "chr(52)",
    "factorial(99999)",
    "zeta(2)",
    "Lambda(x, x)",
    "print(1)",
    "sqrt(4).is_integer",
    "__class__",
    "1;2",
]
leaks = [probe for probe in DANGEROUS if mav._safe_fragment(probe) is not None]
check("whitelist_blocks_every_execution_probe", not leaks,
      f"no identifier-bearing fragment may reach the parser; leaked: {leaks}")
check("whitelist_rejects_unknown_identifiers",
      # The rule is an ALLOWLIST, not a ban on multi-character names. Blanket-refusing them
      # was safe but blind -- sqrt/ln/sin appear in most of calculus, so no derivative claim
      # involving them could be checked at all. An unknown name is still refused outright.
      mav._safe_fragment("zeta(2)") is None
      and mav._safe_fragment("mystery(3)") is None
      and mav._safe_fragment("2*x + 1") is not None
      and mav._safe_fragment("factorial(5)") is not None,
      "unknown identifiers are refused; known mathematical functions are verifiable")

# --- 2. HANG GUARD: explosive expressions are declined, not evaluated -------------
check("declines_power_tower", mav._safe_fragment("9^9^9^9") is None,
      "a power tower must never reach the CAS -- it does not return")
check("declines_huge_literal", mav._safe_fragment("9999999999999999 + 1") is None,
      "an oversized literal must be declined")
check("declines_overlong_expression", mav._safe_fragment("1+" * 200 + "1") is None,
      "an overlong expression must be declined")
check("allows_ordinary_exponent", mav._safe_fragment("2^3 + 1") is not None,
      "school-scale arithmetic must still be evaluated")

# --- 3. CATCHES WRONG MATH --------------------------------------------------------
WRONG = {
    "solve": "Result: x = 4\nWork: 2x + 1 = 7 -> 2x = 8 -> x = 4\nCheck: substituted back, 2*4 + 1 = 9",
    "derivative": "Result: d/dx x^2 = 3x\nWork: power rule\nCheck: verified at x=2",
    "integral": "Result: integral of 2x dx = x^3\nWork: raised the exponent\nCheck: differentiated back",
}
for kind, reply in WRONG.items():
    result = mav.verify_reply(reply)
    check(f"refutes_wrong_{kind}", result["refuted"] is True,
          f"a wrong {kind} must be refuted; got {result.get('reason') or 'no refutation'}")
    check(f"gate_rejects_wrong_{kind}",
          runner._math_answer_shows_verification(reply) is False,
          f"the LIVE math gate must reject a wrong {kind} -- this is the whole point")

# --- 4. DOES NOT REJECT CORRECT MATH ---------------------------------------------
RIGHT = {
    "solve": "Result: x = 3\nWork: 2x + 1 = 7 -> 2x = 6 -> x = 3\nCheck: substituted back, 2*3 + 1 = 7",
    "derivative": "Result: d/dx x^2 = 2x\nWork: power rule\nCheck: verified at x=2, 2*2 = 4",
    "integral": "Result: integral of 2x dx = x^2\nWork: power rule\nCheck: differentiated back, 2*1 = 2",
    "integral_with_constant":
        "Result: integral of 2x dx = x^2 + C\nWork: power rule\nCheck: differentiated back, 2*1 = 2",
}
for kind, reply in RIGHT.items():
    result = mav.verify_reply(reply)
    check(f"does_not_refute_correct_{kind}", result["refuted"] is False,
          f"a correct {kind} must never be refuted; reason was {result.get('reason')!r}")
    check(f"gate_admits_correct_{kind}",
          runner._math_answer_shows_verification(reply) is True,
          f"the LIVE math gate must still admit a correct {kind}")

check("confirms_what_it_checks",
      mav.verify_reply(RIGHT["solve"])["confirmed_count"] >= 1,
      "a verified claim should be recorded as confirmed, not merely un-refuted")

# --- 5. AMBIGUITY IS NEVER A REJECTION -------------------------------------------
AMBIGUOUS = {
    "pure prose proof":
        "Result: the sum of two even numbers is even\n"
        "Work: let them be 2a and 2b, so the sum is 2(a+b)\n"
        "Check: 2(a+b) is divisible by 2 by construction",
    "real binomial answer":
        "Result: 10\nWork: 1. Compute C(5,3). 2. Verify 5!/(3!2!) = 120/12 = 10.\n"
        "Check: enumerated all 10 subsets",
    "matrix answer":
        "Result: [[0.8, -0.6], [-0.2, 0.4]]\nWork: 1. determinant (2*4 - 3*1) = 5.\n"
        "Check: Original * Inverse = [[1, 0], [0, 1]]",
    "symbolic with unknown constants":
        "Result: y = mx + b\nWork: general linear form\nCheck: substituting m=1, b=0 gives y = x, 1*1 = 1",
}
for label, reply in AMBIGUOUS.items():
    result = mav.verify_reply(reply)
    check(f"unverifiable_is_not_refuted[{label}]", result["refuted"] is False,
          f"an unparseable/symbolic answer must be 'unverified', never refuted; "
          f"reason was {result.get('reason')!r}")

check("empty_reply_is_not_refuted", mav.verify_reply("")["refuted"] is False,
      "an empty reply must not be treated as proven wrong")

# --- 6. newlines are load-bearing for extraction ----------------------------------
# An earlier cut collapsed whitespace before extracting, which merged Result/Work/Check into
# one line, destroyed every terminator, and silently found ZERO claims -- the verifier passed
# everything while appearing to work.
check("extraction_finds_claims_across_lines",
      len(mav.extract_claims(WRONG["solve"])) >= 1,
      "claims must still be found when Result/Work/Check are on separate lines")
check("extraction_does_not_invent_claims",
      mav.extract_claims("Result: it depends on the context\nWork: none\nCheck: none") == [],
      "prose with no equation must yield no claims rather than a spurious one")

# --- 6b. LaTeX (2026-08-06) --------------------------------------------------------
# Real chat replies are LaTeX. Measured before normalization: the SAME wrong claim was
# refuted as plain text and produced ZERO claims as "$\boxed{3x}$". Wiring the verifier into
# a serving path without this would stamp "checked" on traffic it cannot read.
LATEX_WRONG = {
    "boxed derivative": r"The derivative of $x^2$ is $\boxed{3x}$.",
    "boxed integral": r"The integral of $2x$ dx is $\boxed{x^3}$.",
    # \frac with \sqrt inside: the shape a live sparse-MoE reply actually used.
    "frac over sqrt": r"The derivative of $\sqrt{x-1}\ln(x-1)$ is "
                      r"$\frac{\ln(x-1)+5}{2\sqrt{x-1}}$.",
}
for label, reply in LATEX_WRONG.items():
    check(f"latex_wrong_is_refuted[{label}]", mav.verify_reply(reply)["refuted"] is True,
          f"a wrong claim written in LaTeX must be caught, not silently skipped")

LATEX_RIGHT = {
    "boxed derivative": r"The derivative of $x^2$ is $\boxed{2x}$.",
    "boxed integral": r"The integral of $2x$ dx is $\boxed{x^2}$.",
    "frac over sqrt": r"The derivative of $\sqrt{x-1}\ln(x-1)$ is "
                      r"$\frac{\ln(x-1)+2}{2\sqrt{x-1}}$.",
    "cdot": r"The derivative of $x^2$ is $2 \cdot x$.",
}
for label, reply in LATEX_RIGHT.items():
    check(f"latex_right_survives[{label}]", mav.verify_reply(reply)["refuted"] is False,
          "a CORRECT LaTeX answer must never be refuted")

check("sqrt_before_frac_ordering",
      "((ln(x-1)+5)/(2sqrt(x-1)))" in mav.normalize_reply_text(
          r"$\frac{\ln(x-1)+5}{2\sqrt{x-1}}$"),
      "\\sqrt must be converted before \\frac or a fraction containing a root is lost whole")

# The subject must keep its closing paren. An optional \)? wrapper once ate it, turning
# "sqrt(x-1)ln(x-1)" into "sqrt(x-1)ln(x-1" -- unparseable, so every wrong derivative of a
# composed function passed unchallenged while APPEARING to have been checked.
_claims = mav.extract_claims(mav.normalize_reply_text(LATEX_WRONG["frac over sqrt"]))
check("subject_keeps_balanced_parens",
      bool(_claims) and _claims[0].subject.count("(") == _claims[0].subject.count(")"),
      f"a truncated subject silently disables verification; got "
      f"{_claims[0].subject if _claims else 'no claim'!r}")

# Named functions widen RECALL without widening EXECUTION.
for allowed in ("sqrt(x-1)", "ln(x-1)", "sin(x)*cos(x)"):
    check(f"named_function_allowed[{allowed}]", mav._safe_fragment(allowed) is not None,
          "calculus function names must be verifiable or most derivative claims cannot be checked")
for hazard in ("factorial(99999)", "binomial(99999,2)"):
    check(f"unbounded_growth_refused[{hazard}]", mav._safe_fragment(hazard) is None,
          "factorial/binomial grow faster than the digit cap catches; the argument must be bounded")

# --- 6c. live FPs from the first 8h Math School run (2026-08-07) -------------------
# The run rejected 17 correct, verified answers. Every mechanism is pinned here with the
# text shape that failed live, in both directions: the correct form must survive, and the
# same mistake written wrongly must still be caught.

# (a) Unicode superscripts. "2x² + 5x - 3 = 0" entered extraction with "²" outside the
# expression class; the match began after it, and x=-3 was refuted against a problem the
# model never stated ("+ 5x - 3 = 0").
UNICODE_QUAD_RIGHT = (
    "Result: x = -3, 1/2\n"
    "Work: 1. Equation 2x² + 5x - 3 = 0 2. Factor: (2x - 1)(x + 3) = 0\n"
    "Check: Substitute x=-3: 2(-3)² + 5(-3) -3 = 18-15-3=0"
)
check("unicode_superscript_right_survives",
      mav.verify_reply(UNICODE_QUAD_RIGHT)["refuted"] is False,
      "a correct quadratic written with ² must never be refuted against a mutilated problem")
_uclaims = [c for c in mav.extract_claims(UNICODE_QUAD_RIGHT) if c.kind == "solve"]
check("unicode_superscript_keeps_leading_term",
      bool(_uclaims) and "2x^2" in _uclaims[0].subject,
      f"the stated problem must keep its 2x² term (normalized, not sliced away); got "
      f"{_uclaims[0].subject if _uclaims else 'no solve claim'!r}")
check("unicode_superscript_wrong_now_caught",
      mav.verify_reply("Result: x = 4\nWork: 2x² + 1 = 7\nCheck: substituted back")
      ["refuted"] is True,
      "normalization widens recall: the same unicode shape with a WRONG root is refuted")

# (b) Glue guard: a relation glued to a character normalization cannot translate is a
# mutilated slice -- dropped, never judged.
GLUED = "Result: x = 3\nWork: the equation √x + 3 = 0 rearranges\nCheck: none computed"
check("unrepresentable_glue_drops_claim",
      mav.extract_claims(GLUED) == [] and mav.verify_reply(GLUED)["refuted"] is False,
      "a √-glued fragment must yield no claim at all rather than a sliced one")

# (c) Modular arithmetic is not plain equality (trainer's false-relation extractor).
check("mod_congruence_not_refuted",
      runner._math_check_has_false_relation(
          "Check: residues mod 4: 0²=0, 1²=1, 2²=0, 3²=1 mod4, so n² ≡ 0 or 1 mod 4") is False,
      "3²=1 mod 4 is TRUE; grading it as 9=1 rejected a correct number-theory proof live")
check("plain_false_equality_still_caught",
      runner._math_check_has_false_relation("Check: 3² = 12") is True,
      "the mod guard must not blind the extractor to genuinely false plain equalities")

# (d) Digit-grouping commas slice numbers the same way ² did.
check("thousands_comma_relation_judgeable_true",
      runner._math_check_has_false_relation(
          "Check: Monte Carlo with 10,000 trials: 1,666/10,000 = 0.1666 observed") is False,
      "1,666/10,000 = 0.1666 is TRUE; the comma must group digits, not start a new number")
check("thousands_comma_relation_judgeable_false",
      runner._math_check_has_false_relation(
          "Check: Monte Carlo with 10,000 trials: 1,666/10,000 = 0.3 observed") is True,
      "after stripping grouping commas the SAME shape with wrong arithmetic is refutable")

# (e) Independent methods named in natural maths language (12 live rejections).
NATURAL_METHOD = {
    "differentiate back": "Result: x³/3 + C\nWork: power rule with n=2.\n"
                          "Check: d/dx [x³/3] = 3x²/3 = x² (matches integrand).",
    "matrix multiply back": "Result: [14/5, -3/5]\nWork: Compute A⁻¹ and x = A⁻¹b.\n"
                            "Check: A*x = [2*(14/5)+1*(-3/5), 3*(14/5)+4*(-3/5)] = [5, 6]",
    "monte carlo": "Result: 5/16\nWork: C(5,3)*(1/2)^5 = 10/32 = 5/16.\n"
                   "Check: Simulated 1,000,000 trials, observed 312,517 successes.",
    "isprime": "Result: 29 is prime\nWork: Checked divisibility by 2, 3, 5 using modular "
               "arithmetic\nCheck: sympy.isprime(29) returns True",
}
for label, reply in NATURAL_METHOD.items():
    check(f"natural_method_verification_admitted[{label}]",
          runner._math_answer_shows_verification(reply) is True,
          "a real independent check phrased in maths language must satisfy the form gate")
check("bare_refusal_still_rejected",
      runner._math_answer_shows_verification(
          "No verified result.\nCheck: could not verify this without more context.") is False,
      "widened signals must not re-admit canned refusals with no concrete computation")

# --- 7. bounded cost ---------------------------------------------------------------
start = time.time()
for reply in list(WRONG.values()) + list(RIGHT.values()):
    mav.verify_reply(reply)
elapsed = time.time() - start
check("verification_is_cheap_enough_for_a_run",
      elapsed < 20.0,
      f"7 verifications took {elapsed:.1f}s; an 80-prompt run must not be slowed materially")

failed = sum(1 for c in checks if c["status"] != "PASS")
print(json.dumps(
    {
        "schema": "engel_math_answer_verifier_verifier_v1",
        "status": "FAIL" if failed else "PASS",
        "passed": len(checks) - failed,
        "total": len(checks),
        "checks": checks,
    },
    indent=2,
))
raise SystemExit(1 if failed else 0)
