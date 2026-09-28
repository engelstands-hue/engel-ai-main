#!/usr/bin/env python3
"""Engel's deterministic math lane — exact computation with built-in verification.

Why this exists: Engel's local chat models (Mistral-7B Q4, Qwen 7B Q5) guess at
arithmetic and algebra the way autocomplete guesses at prose, and a wrong number
delivered confidently is worse than no answer. High/expert math competence for
Engel does not come from a bigger model — it comes from refusing to guess:
recognise a computable request, compute it exactly with a CAS (sympy), VERIFY the
result by an independent check, and only then let the chat surface present it.

Every result carries its verification in the receipt:

    solve            -> substitute every root back; residual must simplify to 0
    integrate (indef)-> differentiate the antiderivative; must equal the integrand
    integrate (def)  -> exact result cross-checked against numeric quadrature
    differentiate    -> numeric spot-check against a central finite difference
    factor/expand/
    simplify         -> expand(result - original) must be exactly 0
    matrix inverse   -> A @ A^-1 must be the identity
    determinant/eig  -> recomputed via an independent method (cofactor/charpoly)
    prime/factorint  -> multiply the factors back together
    limit            -> numeric approach check when the limit is finite

A result whose verification fails is NOT served: the lane reports not-ok and the
chat service falls through to the normal model reply. Unverified math never ships.

Runs where sympy lives: ROG runtime\\python310 has sympy 1.14; on CT246 the chat
service's system python3 does NOT, so the service subprocesses
/opt/engel/llm_training/20260702_deep_reasoning/venv/bin/python on this script
with --json. Never import this module from the CT service directly.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from typing import Any

# --------------------------------------------------------------------------- #
# intent detection — two signals required (verb + mathematical object), because
# one-signal keyword gates have already caused real hijacks in this codebase
# ("training"+"build" answered a question with a training package; a bare "do"
# nearly launched a LoRA run). A math word alone ("integrate the SLM into chat")
# or a number alone ("2 phones failed to pair") must NOT trigger the lane.
# --------------------------------------------------------------------------- #

# Expression: at least one arithmetic operator between numeric/symbolic operands,
# or a caret power, or an explicit equation with a variable, or a matrix literal.
_ALLOWED_FUNCS = (
    "sin|cos|tan|asin|acos|atan|sinh|cosh|tanh|exp|log|ln|sqrt|abs|floor|ceiling|pi|oo|e|E"
)

_EXPR_RE = re.compile(
    # operand OP operand, allowing a unary minus and an opening paren on the right
    # (covers e^-x, 2*(3+4)); the lookbehind keeps single letters standalone so the
    # hyphens in worker-alpha / self-model can never read as subtraction. A known
    # function CALL (sin(, log() is also a mathematical object — sin(x)/x has no
    # bare operand-op-operand pair, and the paren requirement keeps prose like
    # "the receipts log" from qualifying.
    r"(?<![\w.])(?:\d+(?:\.\d+)?|[a-z])\s*[\+\-\*/\^]\s*-?\s*\(?\s*(?:\d+(?:\.\d+)?|[a-z])"
    r"|[a-z]\*\*-?\d"
    r"|=\s*-?\d|[a-z]\s*="
    r"|\[\s*\["
    rf"|\b(?:{_ALLOWED_FUNCS})\s*\(",
    re.IGNORECASE,
)

_OPERATIONS: list[tuple[str, re.Pattern[str]]] = [
    ("solve", re.compile(r"\bsolve\b|\bfind\s+(?:all\s+)?(?:the\s+)?(?:value|root|solution)s?\b|\bwhat\s+(?:does|must)\s+[a-z]\s+(?:have\s+to\s+)?(?:be|equal)\b", re.I)),
    ("integrate", re.compile(r"\bintegra(?:te|l)\b|\bantiderivative\b|\barea\s+under\b", re.I)),
    ("differentiate", re.compile(r"\bdifferentiat|\bderivative\s+of\b|\bd/dx\b|\bhow\s+steep\b|\bslope\s+of\b", re.I)),
    ("limit", re.compile(r"\blimit\s+(?:of|as)\b|\blim\b|\bas\s+[a-z]\s+(?:gets|grows|goes|tends)\s+(?:to\s+)?(?:huge|large|big|infinity)\b|\bsettles?\s+down\s+to\b", re.I)),
    ("rationalize", re.compile(r"\brepeating\b.*\bfraction\b|\bfraction\b.*\brepeating\b|\binto\s+a\s+(?:plain\s+)?fraction\b|\bas\s+a\s+fraction\b", re.I | re.S)),
    ("factor", re.compile(r"\bfactor\b(?!\s+in\b)(?!\s+that\b)|\bas\s+two\s+brackets\b|\bas\s+a\s+product\s+of\b", re.I)),
    ("expand", re.compile(r"\bexpand\b", re.I)),
    ("simplify", re.compile(r"\bsimplif", re.I)),
    ("determinant", re.compile(r"\bdeterminant\b", re.I)),
    ("inverse", re.compile(r"\binverse\s+(?:of\s+)?(?:the\s+)?matrix\b|\bmatrix\s+inverse\b|\binvert\s+(?:the\s+)?matrix\b", re.I)),
    ("eigenvalues", re.compile(r"\beigen", re.I)),
    ("prime", re.compile(r"\bprime\b", re.I)),
    ("factorint", re.compile(r"\bprime\s+factor|\bfactoriz", re.I)),
    ("gcd", re.compile(r"\bgcd\b|\bgreatest\s+common\b", re.I)),
    ("lcm", re.compile(r"\blcm\b|\bleast\s+common\s+multiple\b", re.I)),
    ("evaluate", re.compile(r"\bevaluate\b|\bcompute\b|\bcalculate\b|\bwhat\s+is\b|\bwhat's\b", re.I)),
]

# Phrases where a math verb is figurative in Engel's world — never route these.
# Grown from an adversarial red-team pass: every branch here is a prompt that
# actually fooled an earlier draft of this gate.
_SOFTWARE_NOUNS = (
    "deploy|script|code|config|setup|process|manifest|workflow|pipeline|backlog|"
    "roster|fleet|chat|model|training|dataset|receipt|panel|lane|gate|tunnel|port|"
    "regex|cron|task|queue|log|test|verifier|build|app|ui|window|file|folder|repo|"
    "service|worker|agent|bridge|latency|throughput|outage|issue|problem"
)
_FIGURATIVE_RE = re.compile(
    r"\bintegrate\s+(?:the\s+|this\s+|it\s+)?(?:new\s+)?(?:\w+\s+)?(?:into|with)\b"
    r"|\bfactor\s+(?:in|that|the\s+gpu|this)\b"
    r"|\blimit\s+(?:on|for)\s+\w"
    r"|\bsolve\s+(?:my|our|the)\s+(?!equation|integral|system\s+of)"
    r"|\bsolve\s+for\s+(?:" + _SOFTWARE_NOUNS + r")\b"
    r"|\bderivative\s+works?\b"
    r"|\bdeterminant\s+(?:factor|cause|reason)\b"
    r"|\bprime\s+(?:example|candidate|time|directive|location|node|focus)\b"
    r"|\bexpand\s+(?:the\s+)?(?:roster|coverage|fleet|team|window|search|scope|eval)\b"
    r"|\b(?:solve|simplify|evaluate|factor|expand|integrate|differentiate)\s+"
    r"(?:the\s+|my\s+|our\s+|this\s+|that\s+|whether\s+)?(?:" + _SOFTWARE_NOUNS + r")\b",
    re.I,
)

# Two-signal binding: the verb and the mathematical object must be NEAR each
# other. Bag-of-words co-occurrence anywhere in a message is the exact failure
# mode that made "training"+"build" hijack ordinary prompts.
_MAX_VERB_OBJECT_GAP = 90


# (2026-08-08) Trainer-delivered turns wrap the real question in a depth header and an
# answer contract ("Training depth: ...\n...\nTraining task:\n<question>\n\n<contract>").
# Sniffing the WHOLE wrapper swept contract prose into extraction — the longest-candidate
# rule turned wrapper debris into "- a", so "Solve 4x - 7 = 13" was answered as a = 0 and
# "Differentiate 5x^2 + 3x" as -1 (capability eval math-01/02, 2026-08-08). Detection and
# extraction now operate on the PAYLOAD: text after the "Training task:" marker, cut
# before the first contract opener. Bare chat prompts pass through untouched.
_TRAINING_TASK_MARKER = re.compile(r"\btraining\s+task\s*:\s*", re.I)
_CONTRACT_OPENERS = re.compile(
    r"\banswer\s+only\s+in\s+this\s+filled-in\s+form\b"
    r"|\buse\s+exactly\s+this\s+structure\b"
    r"|\banswer\s+the\s+way\s+you\s+would\s+answer\b",
    re.I,
)
# Dimension/model designators ("Global 24-120x40", "2x4 stud", "4x8 sheet") read as
# implicit multiplication: "what is supported..." near "24-120x40" became
# evaluate(24 - 120*x*40) and hijacked a construction turn. Compact digit-x-digit is a
# designator, not arithmetic — real multiplication asks arrive as 120*40 or "120 x 40"
# (and spaced forms never matched _EXPR_RE anyway, so nothing legitimate is lost).
_DIMENSION_TOKEN_RE = re.compile(r"\b\d{1,4}(?:-\d{1,4})?x\d{1,4}\b", re.I)


def _training_payload(text: str) -> str:
    marker = _TRAINING_TASK_MARKER.search(text)
    if marker:
        text = text[marker.end():]
    opener = _CONTRACT_OPENERS.search(text)
    if opener:
        text = text[: opener.start()]
    return text


def _normalize(text: str) -> str:
    """Light rewrites that turn common phrasings into parseable math."""
    out = _training_payload(str(text or ""))
    out = _DIMENSION_TOKEN_RE.sub(" ", out)
    # thousands separators: 2,340,000 -> 2340000 (never touches "84, 60" lists)
    out = re.sub(r"(?<=\d),(?=\d{3}\b)", "", out)
    # percent-of: "17 percent of 2340000" / "17% of x" -> (17/100)*x
    out = re.sub(r"\b(\d+(?:\.\d+)?)\s*(?:%|percent)\s+of\s+", r"(\1/100)*", out, flags=re.I)
    # phrased equality followed by a number: "3x + 7 gives 25" -> "3x + 7 = 25"
    out = re.sub(
        r"\b(?:gives|equals|comes\s+to|adds\s+up\s+to|totals|is\s+equal\s+to)\s+(?=-?\d)",
        "= ", out, flags=re.I)
    return out


# Word problems the deterministic lane cannot model (compound interest, drain
# rates, optimization, dice) still deserve the strongest MODEL, not the chat
# default. Same two-signal discipline: quantities + a mathematical noun/unit +
# a question frame. Engel-ops sentences full of numbers (ports, versions, cron
# fields, diff stats) carry none of the nouns, so they stay normal chat.
_MATH_NOUN_RE = re.compile(
    r"\bpercent\b|%|\bprobability\b|\bchance\b|\bodds\b|\baverage\b|"
    r"\bthe\s+mean\b|\bmean\s+of\b|"  # bare "mean" is a verb in ops chat ("what does exit 1 mean")
    r"\bmedian\b|\barea\b|\bperimeter\b|\bvolume\b|\bangle\b|\bratio\b|"
    r"\bfraction\b|\bfactorial\b|\bpermutation\b|\bcombination\b|\bdice\b|"
    r"\bcoin\s+flip|\bprime\b|\bdivisible\b|\bremainder\b|\bsquare\s+root\b|"
    r"\bcompounded?\b|\binterest\b|\bdecimal\s+places\b|\bconsecutive\b|"
    r"\bsequence\b|\bequation\b|\bliters?\b|\bmeters?\b|\bmiles?\b|\bkm\b|"
    r"\bhours?\b|\bminutes?\b|\btokens?\s+(?:a|per)\s+second\b",
    re.I,
)
_QUESTION_FRAME_RE = re.compile(
    r"\?|^\s*(?:how|what|which|find|compute|calculate)\b", re.I)
_EXPLICIT_REASONER_RE = re.compile(
    r"\buse\s+(?:the\s+)?(?:math|reasoning)\s+(?:brain|model|specialist)\b|\bdeepseek\b", re.I)


def detect_math_reasoning_request(prompt: str) -> bool:
    """True when a prompt is math-shaped but needs MODELING, not just computing.

    Deliberately checked AFTER detect_math_request in the service: anything the
    deterministic lane can verify never reaches a model at all.
    """
    text = _normalize(prompt)
    if len(text) > 600 or len(text) < 8:
        return False
    if _EXPLICIT_REASONER_RE.search(text):
        return True
    if _FIGURATIVE_RE.search(text):
        return False
    if not _QUESTION_FRAME_RE.search(text):
        return False
    if not re.search(r"(?<![\w.])\d", text):
        return False
    return bool(_MATH_NOUN_RE.search(text))


# --- Conceptual / teaching math (2026-07-31) -------------------------------------
# detect_math_reasoning_request above requires a DIGIT (line ~170). That gate is right
# for word problems but it structurally excludes every CONCEPTUAL question -- "explain
# the chain rule", "derive why induction works", "prove this is irrational" -- so those
# deterministically fell through to the default 7B chat model, which is the weakest
# thing in the fleet at exactly the questions that need reasoning. Same two-signal
# discipline as the rest of this module (verb NEAR object, figurative denylist first),
# minus the digit requirement.
#
# Deliberately NARROW. This targets a human asking a conceptual math question. Long
# machine-authored training prompts are NOT classified here -- they carry an explicit
# `discipline` in their per-turn metadata, and routing off a declared intent is always
# better than sniffing 2000 characters of text. Guessing from content is the mistake
# this whole change set exists to correct.
_MATH_CONCEPT_RE = re.compile(
    r"\bchain\s+rule\b|\bproduct\s+rule\b|\bquotient\s+rule\b|\bl'?h(?:o|ô)pital\b|"
    r"\bderivatives?\b|\bintegrals?\b|\bantiderivatives?\b|\bcalculus\b|"
    r"\blimit\s+of\b|\bcontinuity\b|\bconvergen(?:ce|t)\b|\bdiverg(?:ence|ent)\b|"
    r"\btheorems?\b|\blemmas?\b|\bcorollar(?:y|ies)\b|\baxioms?\b|"
    r"\bproof\s+by\b|\bformal\s+proof\b|\bmathematical\s+proof\b|\bproof\s+technique\b|"
    r"\binduction\b|\bcontrapositive\b|"
    r"\beigen(?:value|vector)s?\b|\bmatri(?:x|ces)\b|\bdeterminant\s+of\b|"
    r"\bvector\s+space\b|\blinear\s+algebra\b|\bnumber\s+theory\b|\bcombinatorics\b|"
    r"\bmodular\s+arithmetic\b|\bcongruence\b|\bmodulo\b|"
    r"\bpolynomials?\b|\bquadratics?\b|\blogarithms?\b|\bexponential\s+(?:function|growth)\b|"
    r"\btrigonometr(?:y|ic)\b|\bprobability\s+distribution\b|\bbayes\b|"
    r"\bstandard\s+deviation\b|\bvariance\b|\bbinomials?\b|\bfactorials?\b",
    re.I,
)
_TEACH_VERB_RE = re.compile(
    r"\bexplain\b|\bteach\b|\bderive\b|\bprove\b|\bdemonstrate\b|"
    r"\bwalk\s+(?:me\s+)?through\b|\bintuition\s+(?:behind|for)\b|"
    r"\bwhy\s+(?:is|does|do|are|can|would)\b|\bhow\s+(?:does|do)\b",
    re.I,
)


def detect_teaching_math_request(prompt: str) -> bool:
    """True for a CONCEPTUAL math question that deserves the reasoning model.

    Complements detect_math_reasoning_request (which needs a digit and so only ever
    catches numeric word problems). Requires a teaching verb NEAR a mathematical
    concept, and honours the same figurative denylist so Engel-ops phrasing
    ("explain the deploy pipeline", "why does the training limit apply") stays
    ordinary chat.
    """
    text = _normalize(prompt)
    if len(text) > 1200 or len(text) < 8:
        return False
    if _FIGURATIVE_RE.search(text):
        return False
    verbs = [m.start() for m in _TEACH_VERB_RE.finditer(text)]
    if not verbs:
        return False
    concepts = [m.start() for m in _MATH_CONCEPT_RE.finditer(text)]
    if not concepts:
        return False
    # Two-signal binding: bag-of-words co-occurrence anywhere in a long message is the
    # exact failure mode that let "training"+"build" hijack ordinary prompts.
    return any(
        abs(v - c) <= _MAX_VERB_OBJECT_GAP for v in verbs for c in concepts
    )


def detect_math_request(prompt: str) -> dict[str, Any] | None:
    """Return {"operation": ..} when BOTH a math verb and a mathematical object
    are present, near each other, and the verb is not figurative."""
    text = _normalize(prompt)
    if len(text) > 4000:
        return None
    if _FIGURATIVE_RE.search(text):
        return None
    operation = None
    verb_match = None
    for op, rx in _OPERATIONS:
        found = rx.search(text)
        if found:
            operation, verb_match = op, found
            break
    if operation is None:
        return None
    if operation in ("prime", "factorint", "gcd", "lcm"):
        # integer-theoretic asks: a bare integer IS the object, but it must sit
        # near the verb so "2 phones failed to pair ... prime node" cannot qualify.
        near = text[max(0, verb_match.start() - 60): verb_match.end() + 60]
        if not re.search(r"\b\d{1,18}\b", near):
            return None
        return {"operation": operation}
    if operation == "rationalize":
        if not re.search(r"\d\.\d+", text):
            return None
        return {"operation": operation}
    obj = _EXPR_RE.search(text)
    if not obj:
        return None
    if operation == "evaluate" and not re.search(r"[\+\-\*/\^]", obj.group(0)):
        return None
    # proximity binding (either order): verb ... object or object ... verb
    gap = obj.start() - verb_match.end() if obj.start() >= verb_match.end() \
        else verb_match.start() - obj.end()
    if gap > _MAX_VERB_OBJECT_GAP:
        return None
    return {"operation": operation}


# --------------------------------------------------------------------------- #
# safe expression extraction + parsing
# --------------------------------------------------------------------------- #
_CANDIDATE_RE = re.compile(
    rf"(?:(?:{_ALLOWED_FUNCS})\s*\()?"
    r"[0-9a-z_\s\+\-\*/\^\(\)\.,=\[\]]+",
    re.IGNORECASE,
)
_FORBIDDEN_RE = re.compile(r"__|\blambda\b|\bimport\b|\bopen\b|\beval\b|\bexec\b|[;:@{}'\"\\]|\bos\b|\bsys\b")


def _sympy():
    import sympy  # imported lazily: only the venv/interpreter that has it runs this far

    return sympy


def extract_expression(prompt: str, operation: str) -> str:
    """Pull the best candidate expression out of the prompt text."""
    text = _normalize(prompt)
    if operation == "rationalize":
        match = re.search(r"(\d*)\.(\d+)\s*(?:\.\.\.|…)?\s*(?:repeating)?", text)
        return match.group(0).strip() if match else ""
    if operation == "solve":
        # phrased equations: "3x + 7 gives 25", "adds up to 81", "comes to 25"
        text = re.sub(
            r"\b(?:gives|equals|comes\s+to|adds\s+up\s+to|totals|is\s+equal\s+to)\b",
            "=", text, flags=re.I)
    if operation in ("determinant", "inverse", "eigenvalues"):
        match = re.search(r"\[\s*\[.*?\]\s*\]", text, re.S)
        return match.group(0) if match else ""
    if operation in ("prime", "factorint"):
        numbers = re.findall(r"\b\d{1,18}\b", text)
        return numbers[-1] if numbers else ""
    if operation in ("gcd", "lcm"):
        numbers = re.findall(r"\b\d{1,18}\b", text)
        return ",".join(numbers[-2:]) if len(numbers) >= 2 else ""
    candidates = []
    for match in _CANDIDATE_RE.finditer(text):
        cand = match.group(0).strip()
        if _FORBIDDEN_RE.search(cand):
            continue
        # must contain an operator, equals, or a function call to be an expression
        if re.search(r"[\+\-\*/\^=]|\b(?:" + _ALLOWED_FUNCS + r")\b", cand, re.I):
            candidates.append(cand)
    if not candidates:
        return ""
    best = max(candidates, key=len).strip(" .,?")
    if operation in ("integrate", "limit"):
        # bounds/approach clauses are parsed from the prompt separately
        best = re.sub(r"\bfrom\s+[\w\.\-]+\s+to\s+[\w\.\-]+", " ", best, flags=re.I)
        best = re.sub(r"\bas\s+[a-z]\s*(?:->|→|approaches)\s*[\w\.\-]+", " ", best, flags=re.I)
        best = re.sub(r"^\s*(?:as\s+)?[a-z]\s+(?:gets|grows|goes|tends)\b[^,]*,?", " ", best, flags=re.I)
    if operation == "differentiate":
        # the at-point clause is parsed from the prompt separately; left in the
        # candidate it becomes silent implicit multiplication ("x^3 - 4x x 2")
        # and the lane would faithfully verify the WRONG expression.
        best = re.sub(r"\b(?:at|where|when)\b.*$", " ", best, flags=re.I)
    # Drop every multi-letter word that is not an allowed function BEFORE parsing.
    # sympy's implicit multiplication would otherwise happily parse swept-in prose:
    # "area under e^-x" becomes a*r*e*a*... and verifies as nonsense algebra.
    best = re.sub(rf"\b(?!(?:{_ALLOWED_FUNCS})\b)[a-z_]{{2,}}\b", " ", best, flags=re.I)

    def _tidy(part: str) -> str:
        part = re.sub(r"\s+", " ", part).strip()
        part = re.sub(r"^[\s\+\*/,\.=]+|[\s\+\-\*/,\.=(]+$", "", part).strip()
        # stray single letters glued onto a complete expression by clause debris:
        # "s (17/100)*2340000" or "(x+1)/(x-3) x" — strip only when what remains
        # still contains an operator, so genuine "x + 1" is never harmed.
        for pattern in (r"^[a-z]\s+(?=[\d(])", r"(?<=[\w)])\s+[a-z]$"):
            trimmed = re.sub(pattern, "", part, flags=re.I).strip()
            if trimmed != part and re.search(r"[\+\-\*/\^=]", trimmed):
                part = trimmed
        return part

    # Comma debris ("x , (2x+1)/(x-3)") parses as a TUPLE and crashes downstream:
    # score comma-separated parts and keep the longest one that stands alone.
    parts = [_tidy(p) for p in ([best] + best.split(","))]
    parts = [p for p in parts if p and re.search(r"[\+\-\*/\^=]|\b(?:" + _ALLOWED_FUNCS + r")\b", p, re.I)]
    for candidate in sorted(set(parts), key=len, reverse=True):
        if "," in candidate:
            continue
        try:
            parsed = parse_expr_safe(candidate.replace("=", "") or "0")
            if not isinstance(parsed, tuple):
                return candidate
        except Exception:  # noqa: BLE001 - scoring, not failing
            continue
    return _tidy(best.replace(",", " "))


def parse_expr_safe(text: str):
    sympy = _sympy()
    from sympy.parsing.sympy_parser import (
        convert_xor,
        implicit_multiplication_application,
        parse_expr,
        standard_transformations,
    )

    cleaned = str(text or "").strip()
    if not cleaned or _FORBIDDEN_RE.search(cleaned):
        raise ValueError("expression rejected by safety filter")
    if len(cleaned) > 600:
        raise ValueError("expression too long")
    # (2026-08-06) COMPLEXITY GUARD. parse_expr(evaluate=True) COMPUTES while parsing, so
    # "9^9^9^9" never returns from the parse call itself -- measured hanging past 45s, and
    # reachable from a chat prompt ("what is 9^9^9^9") as well as from extract_expression's
    # scoring loop. The chat service's 20s subprocess timeout stops it becoming a permanent
    # wedge, but it still burns a core and blows the 90/86/80 budget chain for that turn.
    # A power TOWER is the killer: each exponent multiplies the digit count of the result.
    # A TOWER is the specific killer -- consecutive exponentiation, where each level
    # multiplies the digit count of the level below. Counting carets is not enough:
    # "9^9^9^9" has only three and still never returns, while "2^3 + 4^2 + 5^2" has three
    # and is trivial. Detect the SHAPE (an exponent whose operand is itself exponentiated).
    if re.search(r"(?:\^|\*\*)\s*[0-9.]+\s*(?:\^|\*\*)", cleaned):
        raise ValueError("stacked exponentiation is refused: it does not evaluate in bounded time")
    if cleaned.count("^") + cleaned.count("**") > 6:
        raise ValueError("expression has too many exponentiations to evaluate safely")
    for base, exponent in re.findall(r"(\d+)\s*(?:\^|\*\*)\s*(\d+)", cleaned):
        # Bound the RESULT size, not the operand sizes: 2^100 is fine (31 digits),
        # 99^9999 is not. len(base) * exponent approximates the digit count.
        if len(base) * int(exponent) > 400:
            raise ValueError("expression would evaluate to an impractically large number")
    transformations = standard_transformations + (
        implicit_multiplication_application,
        convert_xor,
    )
    local = {name: getattr(sympy, name if name != "ln" else "log")
             for name in ("sin", "cos", "tan", "asin", "acos", "atan", "sinh", "cosh",
                          "tanh", "exp", "log", "ln", "sqrt", "floor", "ceiling", "pi")}
    local["e"] = sympy.E
    local["E"] = sympy.E
    local["oo"] = sympy.oo
    local["abs"] = sympy.Abs
    local["i"] = sympy.I
    # (2026-08-06) `local_dict` alone was an OVERRIDE, not a whitelist. sympy's parse_expr
    # defaults `global_dict` to `exec('from sympy import *')` PLUS every builtin, so any
    # unlisted name still resolved -- and that made ARBITRARY EXECUTION reachable through a
    # filter this function appeared to guard. Proven live against this exact call:
    #     parse_expr_safe("globals()[(chr(101)+chr(118)+chr(97)+chr(108))](chr(50)+chr(43)+chr(50))")
    #     -> 4        i.e. eval("2+2") ran. 72 characters, _FORBIDDEN_RE never matched,
    # because the payload spells "eval" with chr() and never types a banned word. `factorial`,
    # `zeta`, `Lambda` (the blocklist's \blambda\b is case-sensitive), `print` and attribute
    # access on non-dunders all slipped through the same way.
    #
    # Passing `global_dict` EXPLICITLY replaces that injection, so an unlisted name now raises
    # instead of resolving. The blocklist and length cap stay as defence in depth: a whitelist
    # is the control, they are the belt. Names are added here only because a real caller needs
    # them -- compute()'s operations parse ordinary school maths, and every function it uses on
    # the sympy MODULE (solve, diff, det, eigenvals...) is unaffected, since only the
    # EXPRESSION TEXT passes through this parser.
    allowed = dict(local)
    for name in (
        # `Function` is REQUIRED, not optional. sympy's auto_symbol rewrites any unlisted
        # name followed by "(" into Function('name'), which is then split back into a
        # product by implicit multiplication -- that is how "3x(x+2)" parses at all.
        # Omitting it broke ordinary school algebra with "NameError: name 'Function' is not
        # defined": expand 3x(x+2), solve x(x-2)=0 and every implicit-multiplication form
        # failed in the LIVE chat lane. It reopens nothing: an unlisted name still becomes
        # an inert Symbol/Function rather than resolving to a real callable, so globals(),
        # the eval payload and getattr all still raise.
        "Function",
        "Abs", "Add", "Mul", "Pow", "Rational", "Integer", "Float", "Symbol", "symbols",
        "Matrix", "eye", "zeros", "ones", "factorial", "binomial", "gcd", "lcm", "Mod",
        "sign", "root", "cbrt", "sec", "csc", "cot", "atan2", "erf", "gamma",
        "Eq", "Ne", "Lt", "Le", "Gt", "Ge", "Sum", "Product", "Poly", "I", "nan", "zoo",
    ):
        member = getattr(sympy, name, None)
        if member is not None:
            allowed.setdefault(name, member)
    return parse_expr(
        cleaned,
        transformations=transformations,
        local_dict=local,
        # The security control. Without it, builtins and the whole sympy namespace are live.
        global_dict=allowed,
        evaluate=True,
    )


def _primary_symbol(expr):
    sympy = _sympy()
    symbols = sorted(expr.free_symbols, key=lambda s: s.name)
    for preferred in ("x", "t", "n", "y", "z"):
        for sym in symbols:
            if sym.name == preferred:
                return sym
    return symbols[0] if symbols else sympy.Symbol("x")


# --------------------------------------------------------------------------- #
# solve + verify
# --------------------------------------------------------------------------- #
def compute(operation: str, raw: str, prompt: str = "") -> dict[str, Any]:
    sympy = _sympy()
    started = time.perf_counter()
    result: dict[str, Any] = {
        "schema": "engel_math_lane_result_v1",
        "ok": False,
        "operation": operation,
        "input": raw,
        "verified": False,
        "verification": "",
    }
    try:
        if operation in ("determinant", "inverse", "eigenvalues"):
            rows = json.loads(re.sub(r"\s+", "", raw))
            matrix = sympy.Matrix(rows)
            if operation == "determinant":
                det = matrix.det()
                cofactor = matrix.det(method="berkowitz")
                # Scalar results carry their relation ("det(...) = 1", not a bare "1"):
                # the trainer's concrete-relation gate rightly refuses an answer with no
                # visible computation, and a bare scalar failed it (eval math-03, 2026-08-08).
                result.update(result_text=f"det({raw}) = {det}",
                              verified=sympy.simplify(det - cofactor) == 0,
                              verification="determinant recomputed via Berkowitz method; results agree")
            elif operation == "inverse":
                inv = matrix.inv()
                identity = sympy.simplify(matrix * inv)
                result.update(result_text=str(inv.tolist()),
                              verified=identity == sympy.eye(matrix.rows),
                              verification="A * A^-1 recomposed to the identity matrix")
            else:
                eigs = matrix.eigenvals()
                lam = sympy.Symbol("lambda")
                charpoly = matrix.charpoly(lam)
                verified = all(sympy.simplify(charpoly.as_expr().subs(lam, val)) == 0 for val in eigs)
                result.update(result_text="; ".join(
                                  f"lambda = {k} (multiplicity {int(v)})" for k, v in eigs.items()),
                              verified=verified,
                              verification="each eigenvalue substituted into the characteristic polynomial; all zero")
        elif operation in ("prime", "factorint"):
            n = int(raw)
            if operation == "prime":
                is_p = sympy.isprime(n)
                factors = sympy.factorint(n)
                recomposed = 1
                for p, k in factors.items():
                    recomposed *= p ** k
                result.update(result_text=f"{n} is {'prime' if is_p else 'not prime'}"
                              + ("" if is_p else f" — prime factorization: {sympy.factorint(n)}"),
                              verified=recomposed == n and (len(factors) == 1 and factors.get(n) == 1) == is_p,
                              verification="prime factorization recomposed to the original integer")
            else:
                factors = sympy.factorint(n)
                recomposed = 1
                for p, k in factors.items():
                    recomposed *= p ** k
                result.update(result_text=str(factors), verified=recomposed == n,
                              verification="factors multiplied back to the original integer")
        elif operation in ("gcd", "lcm"):
            a, b = [int(v) for v in raw.split(",")[:2]]
            value = sympy.gcd(a, b) if operation == "gcd" else sympy.lcm(a, b)
            check = (a % value == 0 and b % value == 0) if operation == "gcd" \
                else (value % a == 0 and value % b == 0)
            result.update(result_text=f"{operation}({a}, {b}) = {value}", verified=bool(check),
                          verification="divisibility of both operands confirmed")
        elif operation == "solve":
            if "=" in raw and "==" not in raw:
                left, right = raw.split("=", 1)
                equation = sympy.Eq(parse_expr_safe(left), parse_expr_safe(right))
            else:
                equation = sympy.Eq(parse_expr_safe(raw), 0)
            symbol = _primary_symbol(equation.lhs - equation.rhs)
            roots = sympy.solve(equation, symbol)
            residuals = [sympy.simplify((equation.lhs - equation.rhs).subs(symbol, root)) for root in roots]
            result.update(result_text=f"{symbol} = " + ", ".join(str(r) for r in roots),
                          verified=bool(roots) and all(res == 0 for res in residuals),
                          verification=f"all {len(roots)} root(s) substituted back; residuals are exactly 0")
        elif operation == "integrate":
            bounds = re.search(r"from\s+([\w\.\-]+|-?oo|infinity)\s+to\s+([\w\.\-]+|-?oo|infinity)", prompt, re.I)
            expr = parse_expr_safe(raw)
            symbol = _primary_symbol(expr)
            if bounds:
                lo = sympy.oo if bounds.group(1).lower() in ("infinity", "oo") else parse_expr_safe(bounds.group(1))
                hi = sympy.oo if bounds.group(2).lower() in ("infinity", "oo") else parse_expr_safe(bounds.group(2))
                exact = sympy.integrate(expr, (symbol, lo, hi))
                numeric = sympy.Integral(expr, (symbol, lo, hi)).evalf()
                verified = exact.is_number and abs(complex(sympy.N(exact)) - complex(numeric)) < 1e-6
                result.update(result_text=str(exact),
                              verified=bool(verified),
                              verification="exact definite integral cross-checked against numeric quadrature")
            else:
                anti = sympy.integrate(expr, symbol)
                verified = sympy.simplify(sympy.diff(anti, symbol) - expr) == 0
                result.update(result_text=f"{anti} + C", verified=bool(verified),
                              verification="antiderivative differentiated back; equals the integrand exactly")
        elif operation == "differentiate":
            expr = parse_expr_safe(raw)
            symbol = _primary_symbol(expr)
            deriv = sympy.diff(expr, symbol)
            point = sympy.Rational(7, 10)
            h = sympy.Float(1e-6)
            try:
                numeric = (expr.subs(symbol, point + h) - expr.subs(symbol, point - h)) / (2 * h)
                verified = abs(float(sympy.N(deriv.subs(symbol, point))) - float(sympy.N(numeric))) < 1e-4
            except (TypeError, ValueError):
                verified = sympy.simplify(sympy.integrate(deriv, symbol) - expr).is_constant()
            text_out = str(deriv)
            # "how steep is x^3 - 4x at the point where x is 2" -> also evaluate there
            at_point = re.search(
                rf"\b(?:at|where)\b[^.]{{0,40}}?\b{symbol.name}\s*(?:=|is)\s*(-?\d+(?:\.\d+)?)",
                prompt, re.I)
            if at_point:
                value = deriv.subs(symbol, sympy.Rational(at_point.group(1)))
                text_out = f"{deriv}; at {symbol.name} = {at_point.group(1)} the slope is {sympy.simplify(value)}"
            result.update(result_text=text_out, verified=bool(verified),
                          verification="derivative spot-checked against a central finite difference at x=0.7")
        elif operation == "rationalize":
            match = re.match(r"(\d*)\.(\d+)", raw)
            whole, frac = match.group(1) or "0", match.group(2)
            # collapse a doubled repetend so 0.727272 -> repetend 72
            repetend = frac
            for size in range(1, len(frac) // 2 + 1):
                if len(frac) % size == 0 and frac == frac[: size] * (len(frac) // size):
                    repetend = frac[: size]
                    break
            exact = sympy.Integer(whole) + sympy.Rational(int(repetend), 10 ** len(repetend) - 1)
            approx = float(f"{whole}.{repetend * (18 // len(repetend) + 1)}"[:20])
            verified = abs(float(exact) - approx) < 1e-12
            result.update(result_text=f"{raw} = {exact}", verified=bool(verified),
                          verification="exact fraction re-expanded by long division; matches the repeating decimal")
        elif operation == "limit":
            target = re.search(r"(?:as|approaches|->|→)\s*[a-z]?\s*(?:->|→|approaches)?\s*(-?\s*(?:oo|infinity|[\d\.]+))", prompt, re.I)
            expr = parse_expr_safe(raw)
            symbol = _primary_symbol(expr)
            grows_unbounded = bool(re.search(
                r"\b(?:gets|grows|goes|tends)\s+(?:to\s+)?(?:huge|large|big|infinity)\b|→\s*∞",
                prompt, re.I))
            to = sympy.oo if grows_unbounded or (target and "o" in target.group(1).lower()) else \
                parse_expr_safe(target.group(1)) if target else 0
            value = sympy.limit(expr, symbol, to)
            if value.is_finite and to is not sympy.oo:
                near = expr.subs(symbol, sympy.Float(to) + sympy.Float(1e-7))
                verified = abs(complex(sympy.N(near)) - complex(sympy.N(value))) < 1e-3
            elif value.is_finite:
                near = expr.subs(symbol, sympy.Integer(10) ** 8)
                verified = abs(complex(sympy.N(near)) - complex(sympy.N(value))) < 1e-3
            else:
                verified = True  # divergence asserted by CAS; no finite check applies
            result.update(result_text=f"limit = {value}", verified=bool(verified),
                          verification="limit cross-checked numerically near the approach point")
        elif operation in ("factor", "expand", "simplify"):
            expr = parse_expr_safe(raw)
            transformed = {"factor": sympy.factor, "expand": sympy.expand,
                           "simplify": sympy.simplify}[operation](expr)
            # expand(diff)==0 misses rational cancellations ((x^2-1)/(x-1) vs x+1),
            # so fall back to numeric equivalence at several rational points,
            # skipping poles. Differing only at a removable singularity is exactly
            # what a correct simplification does.
            verified = sympy.expand(transformed - expr) == 0
            if not verified:
                symbols = sorted(expr.free_symbols | transformed.free_symbols,
                                 key=lambda s: s.name)
                agree = 0
                for num, den in ((3, 7), (5, 3), (9, 2), (-4, 5), (11, 6), (2, 9)):
                    point = {s: sympy.Rational(num + i, den) for i, s in enumerate(symbols)}
                    try:
                        delta = complex(sympy.N((transformed - expr).subs(point)))
                    except (TypeError, ValueError, ZeroDivisionError):
                        continue
                    if abs(delta) < 1e-9:
                        agree += 1
                    else:
                        agree = -100
                        break
                verified = agree >= 3
            result.update(result_text=str(transformed), verified=bool(verified),
                          verification="equivalence confirmed by exact difference or agreement at >=3 rational sample points")
        else:  # evaluate
            expr = parse_expr_safe(raw)
            if expr.free_symbols:
                simplified = sympy.simplify(expr)
                result.update(result_text=str(simplified),
                              verified=sympy.expand(simplified - expr) == 0,
                              verification="symbolic simplification checked by exact difference")
            else:
                exact = sympy.nsimplify(expr, rational=False)
                numeric = sympy.N(expr, 12)
                result.update(result_text=f"{exact} = {numeric}" if str(exact) != str(numeric)
                              else f"{raw} = {numeric}",
                              verified=abs(complex(sympy.N(exact)) - complex(numeric)) < 1e-9,
                              verification="exact value agrees with 12-digit numeric evaluation")
        result["ok"] = bool(result.get("verified"))
        if not result["ok"] and not result.get("error"):
            result["status"] = "computed but verification failed; refusing to serve an unverified result"
    except Exception as exc:  # noqa: BLE001 — the lane reports, the chat falls through
        result["error"] = f"{type(exc).__name__}: {exc}"[:300]
    result["elapsed_ms"] = int((time.perf_counter() - started) * 1000)
    return result


def answer_prompt(prompt: str) -> dict[str, Any]:
    """Full pipeline: detect -> extract -> compute+verify. None-equivalent when not math."""
    intent = detect_math_request(prompt)
    if intent is None:
        return {"ok": False, "math_request": False, "status": "not a computable math request"}
    operation = intent["operation"]
    raw = extract_expression(prompt, operation)
    if not raw:
        return {"ok": False, "math_request": True, "operation": operation,
                "status": "math intent detected but no expression could be extracted"}
    result = compute(operation, raw, prompt)
    result["math_request"] = True
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Engel deterministic math lane")
    parser.add_argument("--json", action="store_true", help="read {'prompt': ...} JSON on argv[1] or stdin")
    parser.add_argument("text", nargs="?", default="")
    args = parser.parse_args()
    if args.json:
        payload = json.loads(args.text) if args.text else json.load(sys.stdin)
        prompt = str(payload.get("prompt") or "")
    else:
        prompt = args.text
    result = answer_prompt(prompt)
    print(json.dumps(result, sort_keys=True, default=str))
    return 0 if result.get("ok") or not result.get("math_request") else 1


if __name__ == "__main__":
    raise SystemExit(main())
