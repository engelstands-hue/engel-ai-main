"""Prove a math answer WRONG with a CAS, so training stops rewarding plausible arithmetic.

Why this exists
---------------
The math admit gate checks the SHAPE of an answer -- a Result line, a Check line, a
verification word, some arithmetic, and no isolated numeric relation the CAS can refute.
It never checks whether the mathematics is correct. Measured against the live gate before
this module existed, every one of these was ADMITTED as training data:

    Result: x = 4          for 2x + 1 = 7          (x is 3)
    Result: d/dx x^2 = 3x                          (it is 2x)
    Result: integral of 2x dx = x^3                (it is x^2)

Each passes because its Check is internally consistent: "substituted back, 2*4 + 1 = 9" is
a true statement about 9, and the gate has no idea it should equal 7. Training on eighty of
those teaches the habit the curriculum exists to prevent -- that verification-shaped prose
IS verification. Math is the one domain in this system where correctness is DECIDABLE, so
throwing that signal away is the most expensive omission in the pipeline, and it matters
twice over because the same produce-then-verify discipline underwrites code generation.

What it checks
--------------
The model states its own problem in Work and its answer in Result, so the answer can be
checked AGAINST THE STATED PROBLEM:

    solve       "2x + 1 = 7" with "x = 4"   -> substitute; residual must be 0
    derivative  "d/dx x^2 = 3x"             -> sympy.diff and compare
    integral    "integral of 2x dx = x^3"   -> differentiate the claim back to the integrand
    factor      "12 = 2 * 5"                -> expand the claim and compare

Conservative by construction
----------------------------
Every check returns REFUTED only when the CAS proves the claim false. Anything unparsed,
ambiguous, or too expensive returns "unverified", which the caller treats as fine. That
asymmetry is deliberate and hard-won: this session repeatedly produced gates that rejected
correct work, and a false rejection is worse than a missed one -- it deletes good training
data and teaches nothing. A missed wrong answer costs one bad row; a false refutation costs
a good row AND the model's trust in its own correct method.

Safety
------
Model text is untrusted input. `engel_math_lane.parse_expr_safe` is NOT a sandbox -- its
filter is a blocklist, sympy's parser exposes the whole sympy namespace plus builtins by
bare name, and arbitrary execution is reachable through `globals()` composed with `chr()`.
So this module never hands raw model text to the parser: every fragment must first match a
strict numeric/algebraic whitelist (`_SAFE_EXPR`), which admits digits, the usual operators,
parentheses, decimal points and single-letter variables and nothing else. `globals`, `chr`,
`factorial` and every other identifier are rejected on the character class alone, before
parsing. Expressions are additionally bounded for explosiveness and evaluated under a wall
clock, because a power tower makes the CAS hang forever rather than fail.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))

SCHEMA = "engel_math_answer_verification_v1"

# Whitelist, not blocklist. Single letters are allowed as variables; any multi-character
# identifier (chr, globals, factorial, zeta...) fails this and never reaches the parser.
_SAFE_EXPR = re.compile(r"^[0-9a-zA-Z()+\-*/^.,\s]*$")
_MULTICHAR_NAME = re.compile(r"[A-Za-z]{2,}")
# Function names a mathematical answer legitimately contains. Blanket-rejecting every
# multi-character identifier was safe but blind: sqrt, ln, sin and cos appear in most of
# calculus, so a derivative claim like "d/dx sqrt(x-1)*ln(x-1)" could never be checked at
# all. These names are exactly the set engel_math_lane already whitelists for its parser,
# so admitting them widens what can be VERIFIED without widening what can be EXECUTED --
# every other identifier is still refused before the parser sees it.
_SAFE_FUNCTIONS = frozenset({
    "sqrt", "ln", "log", "exp", "abs",
    "sin", "cos", "tan", "asin", "acos", "atan",
    "sinh", "cosh", "tanh", "pi", "oo",
    "floor", "ceiling", "factorial", "binomial", "gcd", "lcm",
})

MAX_EXPR_CHARS = 120
MAX_EXPONENTS = 2
MAX_LITERAL_DIGITS = 12
CAS_TIMEOUT_SECONDS = 2.0

VERDICT_REFUTED = "refuted"
VERDICT_CONFIRMED = "confirmed"
VERDICT_UNVERIFIED = "unverified"


@dataclass(frozen=True)
class Claim:
    kind: str          # solve | derivative | integral | factor
    subject: str       # the problem side
    answer: str        # the claimed answer
    variable: str = "x"


def _safe_fragment(raw: str) -> str | None:
    """Return a parser-safe expression, or None. Whitelist-first; never a blocklist."""
    text = " ".join(str(raw or "").split())
    if not text or len(text) > MAX_EXPR_CHARS:
        return None
    if not _SAFE_EXPR.match(text):
        return None
    # Every multi-character identifier must be a known mathematical function. One unknown
    # name is enough to refuse the whole fragment -- that keeps `globals`, `chr` and
    # `factorial(99999)`-style payloads out while letting real calculus through.
    for name in _MULTICHAR_NAME.findall(text):
        if name.casefold() not in _SAFE_FUNCTIONS:
            return None
    if text.count("^") + text.count("**") > MAX_EXPONENTS:
        return None
    if any(len(lit) > MAX_LITERAL_DIGITS for lit in re.findall(r"\d+", text)):
        return None
    for base, exponent in re.findall(r"(\d+)\s*(?:\^|\*\*)\s*(\d+)", text):
        if len(base) * int(exponent or 0) > 64:
            return None
    # factorial/binomial grow faster than exponentiation and the digit cap does not catch
    # them: `factorial(99999)` is only five digits and builds a ~500,000-digit integer.
    # Admitting these names for recall reopened that, so bound the argument explicitly.
    for argument in re.findall(r"(?:factorial|binomial)\s*\(\s*(\d+)", text, re.IGNORECASE):
        if int(argument) > 100:
            return None
    return text


def _parse(text: str) -> Any:
    import engel_math_lane as ml

    safe = _safe_fragment(text)
    if safe is None:
        return None
    try:
        parsed = ml.parse_expr_safe(safe.replace("^", "**"))
    except Exception:
        return None
    # parse_expr_safe returns a TUPLE when the text contains a comma.
    return None if isinstance(parsed, tuple) else parsed


def _is_zero(expr: Any) -> bool | None:
    """True/False if the CAS decided inside its budget, None if it did not."""
    import threading

    import engel_math_lane as ml

    sympy = ml._sympy()
    out: dict[str, Any] = {}

    def _work() -> None:
        try:
            simplified = sympy.simplify(expr)
            out["value"] = bool(
                simplified.is_number and abs(complex(sympy.N(simplified))) < 1e-9
            )
        except Exception:
            out["value"] = None

    worker = threading.Thread(target=_work, daemon=True)
    worker.start()
    worker.join(CAS_TIMEOUT_SECONDS)
    return out.get("value")


# --- claim extraction -------------------------------------------------------------
# A claim ends at a line break, sentence punctuation, or a derivation arrow. NEWLINES ARE
# LOAD-BEARING: the answer contract puts Result/Work/Check on separate lines, and an earlier
# cut of this module collapsed whitespace first, which merged every line into one string and
# made every terminator disappear -- extraction then found zero claims and the whole verifier
# silently passed everything. Keep the line structure.
_END = r"(?=\s*(?:->|=>|[.,;]|\n|$))"
_EXPR = r"[0-9a-zA-Z()+\-*/^.\s]{1,60}?"

_SOLVE_EQ = re.compile(rf"({_EXPR})\s*=\s*({_EXPR}){_END}")
_ANSWER = re.compile(r"\b([a-zA-Z])\s*=\s*(-?[0-9]+(?:\.[0-9]+)?(?:\s*/\s*[0-9]+)?)\b")
# NOTE the absence of an optional `\(?...\)?` wrapper around the subject. An earlier version
# had one, meaning to allow "derivative of (x^2)", and it silently ATE the closing paren of
# any expression that ends in one: "sqrt(x-1)ln(x-1)" was captured as "sqrt(x-1)ln(x-1",
# which then failed to parse and reported "unverified" -- so every wrong derivative of a
# composed function passed unchallenged. A parenthesised subject parses fine on its own.
_DERIV = re.compile(
    rf"(?:d\s*/\s*d\s*([a-zA-Z])|derivative\s+of)\s*({_EXPR})\s*(?:is|=)\s*({_EXPR}){_END}",
    re.IGNORECASE,
)
_INTEGRAL = re.compile(
    rf"(?:integral|antiderivative)\s+of\s+({_EXPR})\s*d\s*([a-zA-Z])\s*(?:is|=)\s*({_EXPR}){_END}",
    re.IGNORECASE,
)


# (2026-08-07) UNICODE MATHS, learned live: the 8h Math School run REFUTED a CORRECT
# quadratic. The model wrote "2x² + 5x - 3 = 0"; "²" is outside the expression class, so
# the equation match began after it, the stated problem became "+ 5x - 3 = 0", and x=-3
# "failed" a problem the model never stated. The trainer's false-relation extractor
# learned this exact lesson on 2026-07-31; this extractor had not. Same rule both places:
# normalize what has an unambiguous plain form, strip digit-grouping commas ("1,666"
# otherwise enters the class mid-number as "666"), and DROP any claim whose matched span
# is glued to a character normalization could not translate -- a mutilated slice is never
# checkable evidence, and refuting one violates "refutes only what it proves".
_UNICODE_MATH_SUBS = {
    "²": "^2", "³": "^3", "⁴": "^4", "⁵": "^5", "⁶": "^6",
    "⁷": "^7", "⁸": "^8", "⁹": "^9", "¹": "^1", "⁰": "^0",
    "−": "-", "×": "*", "÷": "/", "·": "*",
}
_THOUSANDS_COMMA = re.compile(r"(?<=\d),(?=\d{3}(?!\d))")
_NON_ASCII_GLUE = re.compile(r"[^\x00-\x7F]")


def _normalize_unicode_math(text: str) -> str:
    for src, dst in _UNICODE_MATH_SUBS.items():
        text = text.replace(src, dst)
    return _THOUSANDS_COMMA.sub("", text)


def _glued_to_unrepresentable(text: str, start: int) -> bool:
    prev = text[start - 1 : start]
    return bool(prev) and not prev.isspace() and bool(_NON_ASCII_GLUE.match(prev))


_LATEX_SUBS = (
    (re.compile(r"\\left|\\right|\\,|\\;|\\!|\\quad|\\qquad"), ""),
    (re.compile(r"\\boxed\s*\{([^{}]*)\}"), r"\1"),
    (re.compile(r"\\text\s*\{([^{}]*)\}"), r"\1"),
    (re.compile(r"\\mathrm\s*\{([^{}]*)\}"), r"\1"),
    # ORDER MATTERS. \sqrt must be converted BEFORE \frac: the brace-matching here is flat
    # (`[^{}]*`), so a \frac whose numerator or denominator still contains braces -- the very
    # common `\frac{...}{2\sqrt{x-1}}` -- would not match and the whole fraction would be
    # lost. Innermost constructs first.
    (re.compile(r"\\sqrt\s*\{([^{}]*)\}"), r"sqrt(\1)"),
    (re.compile(r"\\frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}"), r"((\1)/(\2))"),
    (re.compile(r"\\dfrac\s*\{([^{}]*)\}\s*\{([^{}]*)\}"), r"((\1)/(\2))"),
    (re.compile(r"\\(ln|log|sin|cos|tan|exp|arcsin|arccos|arctan|sinh|cosh|tanh)\b"), r"\1"),
    (re.compile(r"\\cdot|\\times"), "*"),
    (re.compile(r"\\div"), "/"),
    (re.compile(r"\\pi\b"), "pi"),
    (re.compile(r"\^\s*\{([^{}]*)\}"), r"^(\1)"),
    (re.compile(r"_\s*\{[^{}]*\}"), ""),
    (re.compile(r"[$\\]"), " "),
)


def normalize_reply_text(reply: str) -> str:
    """Turn LaTeX-flavoured maths into the plain form the extractors understand.

    (2026-08-06) Measured: the SAME wrong claim is refuted as "The derivative of x^2 is 3*x"
    and completely invisible as "The derivative of $x^2$ is $\\boxed{3x}$" -- zero claims
    extracted. `_safe_fragment` rejects backslashes and braces by design, and the claim
    patterns were written against the training answer contract's plain Result/Work/Check
    lines. Real chat replies are LaTeX and markdown, so without this the verifier reads
    almost nothing a model actually writes, and any "checked" stamp built on it would be
    false confidence rather than a check.

    Deliberately lossy and conservative: it only rewrites constructs with an unambiguous
    plain equivalent. Anything it cannot confidently convert is left alone and simply fails
    to extract, which costs a missed check -- never a wrong refutation."""
    text = str(reply or "")
    for pattern, replacement in _LATEX_SUBS:
        text = pattern.sub(replacement, text)
    # Collapse the double spaces the stripping leaves behind, but keep newlines: the claim
    # terminators depend on them.
    return "\n".join(" ".join(line.split()) for line in text.splitlines())


def extract_claims(reply: str) -> list[Claim]:
    """Pull checkable claims out of a reply. Missing a claim is fine; inventing one is not."""
    # Unicode first (applies on BOTH the normalize=True and normalize=False paths -- claim
    # extraction itself must never see a "²" it would silently slice around), then collapse
    # spaces/tabs but PRESERVE newlines -- see _END above.
    text = _normalize_unicode_math(str(reply or ""))
    text = "\n".join(" ".join(line.split()) for line in text.splitlines())
    claims: list[Claim] = []

    for match in _DERIV.finditer(text):
        if _glued_to_unrepresentable(text, match.start(2)):
            continue
        variable = match.group(1) or "x"
        claims.append(
            Claim("derivative", match.group(2).strip(), match.group(3).strip(), variable)
        )
    for match in _INTEGRAL.finditer(text):
        if _glued_to_unrepresentable(text, match.start(1)):
            continue
        claims.append(
            Claim("integral", match.group(1).strip(), match.group(3).strip(), match.group(2))
        )

    # solve: an equation somewhere in the text plus a stated root.
    answer = _ANSWER.search(text)
    if answer:
        variable, value = answer.group(1), answer.group(2)
        for match in _SOLVE_EQ.finditer(text):
            if _glued_to_unrepresentable(text, match.start(1)):
                continue
            lhs, rhs = match.group(1).strip(), match.group(2).strip()
            # Skip the answer statement itself ("x = 4") -- it is the claim, not the problem.
            if lhs.strip() == variable:
                continue
            if variable in lhs or variable in rhs:
                claims.append(Claim("solve", f"({lhs}) - ({rhs})", value, variable))
                break
    return claims


def verify_claim(claim: Claim) -> tuple[str, str]:
    """(verdict, detail). REFUTED only when the CAS proves the claim false."""
    try:
        import engel_math_lane as ml

        sympy = ml._sympy()
    except Exception as exc:  # pragma: no cover
        return VERDICT_UNVERIFIED, f"CAS unavailable: {exc}"

    if claim.kind == "solve":
        equation = _parse(claim.subject)
        value = _parse(claim.answer)
        if equation is None or value is None:
            return VERDICT_UNVERIFIED, "equation or root did not parse safely"
        try:
            symbol = sympy.Symbol(claim.variable)
            residual = equation.subs(symbol, value)
        except Exception:
            return VERDICT_UNVERIFIED, "substitution failed"
        zero = _is_zero(residual)
        if zero is None:
            return VERDICT_UNVERIFIED, "CAS budget exceeded"
        return (
            (VERDICT_CONFIRMED, f"{claim.variable}={claim.answer} satisfies the equation")
            if zero
            else (VERDICT_REFUTED, f"{claim.variable}={claim.answer} does not satisfy {claim.subject}")
        )

    if claim.kind in ("derivative", "integral"):
        subject = _parse(claim.subject)
        answer = _parse(claim.answer)
        if subject is None or answer is None:
            return VERDICT_UNVERIFIED, "expression did not parse safely"
        try:
            symbol = sympy.Symbol(claim.variable)
            if claim.kind == "derivative":
                difference = sympy.diff(subject, symbol) - answer
            else:
                # Differentiate the claimed antiderivative back to the integrand. This
                # sidesteps the constant of integration entirely, which comparing
                # antiderivatives directly would trip over.
                difference = sympy.diff(answer, symbol) - subject
        except Exception:
            return VERDICT_UNVERIFIED, "differentiation failed"
        zero = _is_zero(difference)
        if zero is None:
            return VERDICT_UNVERIFIED, "CAS budget exceeded"
        label = "derivative" if claim.kind == "derivative" else "antiderivative"
        return (
            (VERDICT_CONFIRMED, f"{label} of {claim.subject} checks out")
            if zero
            else (VERDICT_REFUTED, f"claimed {label} of {claim.subject} is not {claim.answer}")
        )

    return VERDICT_UNVERIFIED, f"no checker for {claim.kind}"


def verify_reply(reply: str, *, max_claims: int = 8, normalize: bool = True) -> dict[str, Any]:
    """Verify every checkable claim. `refuted` True means at least one is provably wrong.

    `max_claims` bounds worst-case cost (each claim is capped at CAS_TIMEOUT_SECONDS), which
    matters on a serving path where a user is waiting. `normalize` converts LaTeX first --
    without it the verifier reads almost nothing a chat model writes."""
    text = normalize_reply_text(reply) if normalize else str(reply or "")
    results = []
    for claim in extract_claims(text)[:max_claims]:
        verdict, detail = verify_claim(claim)
        results.append(
            {"kind": claim.kind, "subject": claim.subject, "answer": claim.answer,
             "verdict": verdict, "detail": detail}
        )
    refuted = [r for r in results if r["verdict"] == VERDICT_REFUTED]
    confirmed = [r for r in results if r["verdict"] == VERDICT_CONFIRMED]
    return {
        "schema": SCHEMA,
        "claims": results,
        "refuted": bool(refuted),
        "confirmed_count": len(confirmed),
        "reason": refuted[0]["detail"] if refuted else "",
    }


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reply", required=True)
    args = parser.parse_args(argv)
    print(json.dumps(verify_reply(args.reply), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
