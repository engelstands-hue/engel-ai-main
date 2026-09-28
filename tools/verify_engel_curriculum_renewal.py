#!/usr/bin/env python3
"""Verify all five canonical Engel curricula have real novel eight-hour paths.

This verifier is read-only.  It builds the templates in memory, hashes their base prompts
against immutable pack and reservation history, rehashes grounding artifacts, and proves
that all eighty Math School prompts resolve to independent declared ground truth.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
for candidate in (ROOT, TOOLS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import engel_construction_renewal_curriculum as construction  # noqa: E402
import engel_curriculum_renewal as renewal  # noqa: E402
import engel_math_problems as math_problems  # noqa: E402
import sync_engel_training_assets as assets  # noqa: E402
from engel_prompt_novelty import (  # noqa: E402
    DEFAULT_PACKS_DIR,
    canonical_base_prompt_sha256,
    evaluate_scheduled_prompt_novelty,
    load_prompt_history,
    material_card_sha256,
)


checks: list[dict[str, Any]] = []


def check(name: str, ok: bool, detail: Any) -> None:
    checks.append(
        {
            "name": name,
            "status": "PASS" if ok else "FAIL",
            "detail": detail if isinstance(detail, str) else json.dumps(detail, sort_keys=True),
        }
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


# Reviewed independently from ``engel_math_problems.PROBLEMS``.  Do not generate this
# table from MathProblem.question or MathProblem.answer: it is the second authority that
# makes registry drift observable.  Exact question/kind/answer binding is deliberate -- a
# changed exercise or result needs a fresh review instead of silently inheriting the old
# approval.  The runtime grader is exercised below with the answer from this table, never
# with ``problem.answer``.
INDEPENDENT_MATH_RENEWAL_ORACLE: dict[str, tuple[str, str, str]] = {
    "ren-alg-01": ("Solve 5x - 7 = 33 for x.", "value", "8"),
    "ren-alg-02": ("Solve 4x + 9 = -11 for x.", "value", "-5"),
    "ren-alg-03": ("Solve 7(x - 2) = 35 for x.", "value", "7"),
    "ren-alg-04": ("Solve 2x/3 + 5 = 13 for x.", "value", "12"),
    "ren-alg-05": ("Solve x^2 - 7x + 12 = 0 for x.", "set", "3,4"),
    "ren-alg-06": ("Solve x^2 + x - 20 = 0 for x.", "set", "-5,4"),
    "ren-alg-07": (
        "Simplify (x^2 - 16)/(x - 4) for x != 4.",
        "expression",
        "x + 4",
    ),
    "ren-alg-08": (
        "Simplify (x^2 + 5x + 6)/(x + 2) for x != -2.",
        "expression",
        "x + 3",
    ),
    "ren-alg-09": ("Solve 2^x = 32 for x.", "value", "5"),
    "ren-alg-10": ("Solve 3x + 2 = 2x + 11 for x.", "value", "9"),
    "ren-cal-01": (
        "Differentiate 5x^3 - 4x with respect to x.",
        "expression",
        "15*x**2 - 4",
    ),
    "ren-cal-02": (
        "Differentiate x^4 + 3x^2 - 7 with respect to x.",
        "expression",
        "4*x**3 + 6*x",
    ),
    "ren-cal-03": (
        "Integrate 8x^3 with respect to x, ignoring the constant of integration.",
        "expression",
        "2*x**4",
    ),
    "ren-cal-04": (
        "Integrate 3x^2 + 2 with respect to x, ignoring the constant of integration.",
        "expression",
        "x**3 + 2*x",
    ),
    "ren-cal-05": (
        "Evaluate the limit of (x^2 - 9)/(x - 3) as x approaches 3.",
        "value",
        "6",
    ),
    "ren-cal-06": (
        "Evaluate the limit of (x^3 - 8)/(x - 2) as x approaches 2.",
        "value",
        "12",
    ),
    "ren-cal-07": (
        "Evaluate the derivative of x^3 - x at x = 2.",
        "value",
        "11",
    ),
    "ren-cal-08": (
        "Evaluate the definite integral of 3x^2 from x = 0 to x = 2.",
        "value",
        "8",
    ),
    "ren-cal-09": (
        "Differentiate sin(x) + x^2 with respect to x.",
        "expression",
        "cos(x) + 2*x",
    ),
    "ren-cal-10": (
        "Integrate cos(x) with respect to x, ignoring the constant of integration.",
        "expression",
        "sin(x)",
    ),
    "ren-lin-01": (
        "Compute the determinant of [[3, 2], [5, 4]].",
        "value",
        "2",
    ),
    "ren-lin-02": (
        "Compute the determinant of [[6, 1], [2, 5]].",
        "value",
        "28",
    ),
    "ren-lin-03": (
        "Compute the determinant of [[-1, 3], [4, 2]].",
        "value",
        "-14",
    ),
    "ren-lin-04": (
        "Compute the determinant of [[7, 0], [0, -3]].",
        "value",
        "-21",
    ),
    "ren-lin-05": (
        "Compute the determinant of [[1, 2, 0], [0, 3, 4], [0, 0, 5]].",
        "value",
        "15",
    ),
    "ren-lin-06": (
        "Compute the determinant of [[2, 0, 1], [3, 1, 0], [0, 4, 1]].",
        "value",
        "14",
    ),
    "ren-lin-07": (
        "Compute the determinant of [[4, 2], [1, 3]].",
        "value",
        "10",
    ),
    "ren-lin-08": (
        "Compute the determinant of [[5, -2], [-3, 1]].",
        "value",
        "-1",
    ),
    "ren-lin-09": (
        "Compute the determinant of [[1, 0, 2], [0, 2, 0], [3, 0, 1]].",
        "value",
        "-10",
    ),
    "ren-lin-10": (
        "Compute the determinant of [[-2, 1, 0], [0, 4, 2], [0, 0, 3]].",
        "value",
        "-24",
    ),
    "ren-prb-01": (
        "A fair coin is flipped 5 times. What is the probability of exactly 3 heads? Give the answer as a fraction.",
        "value",
        "5/16",
    ),
    "ren-prb-02": (
        "Two fair six-sided dice are rolled. What is the probability that their sum is 7? Give the answer as a fraction.",
        "value",
        "1/6",
    ),
    "ren-prb-03": (
        "Two fair six-sided dice are rolled. What is the probability of at least one 6? Give the answer as a fraction.",
        "value",
        "11/36",
    ),
    "ren-prb-04": (
        "One card is drawn from a standard 52-card deck. What is the probability it is an ace? Give the answer as a fraction.",
        "value",
        "1/13",
    ),
    "ren-prb-05": (
        "One card is drawn from a standard 52-card deck. What is the probability it is red? Give the answer as a fraction.",
        "value",
        "1/2",
    ),
    "ren-prb-06": (
        "A bag has 5 red and 3 blue tokens. Two tokens are drawn without replacement. What is the probability both are red? Give the answer as a fraction.",
        "value",
        "5/14",
    ),
    "ren-prb-07": (
        "A fair coin is flipped 6 times. What is the probability of exactly 2 heads? Give the answer as a fraction.",
        "value",
        "15/64",
    ),
    "ren-prb-08": (
        "A fair six-sided die is rolled once. What is the probability of a result greater than 4? Give the answer as a fraction.",
        "value",
        "1/3",
    ),
    "ren-prb-09": (
        "A fair coin and a fair six-sided die are used once. What is the probability of heads or a 6? Give the answer as a fraction.",
        "value",
        "7/12",
    ),
    "ren-prb-10": (
        "A bag has 4 green and 6 black tokens. A token is drawn, replaced, and drawn again. What is the probability both draws are green? Give the answer as a fraction.",
        "value",
        "4/25",
    ),
    "ren-num-01": ("Compute gcd(126, 210).", "value", "42"),
    "ren-num-02": ("Compute lcm(18, 24).", "value", "72"),
    "ren-num-03": ("Compute 11^4 mod 7.", "value", "4"),
    "ren-num-04": ("Compute 2^10 mod 7.", "value", "2"),
    "ren-num-05": ("Compute gcd(391, 299).", "value", "23"),
    "ren-num-06": ("Compute Euler's totient phi(20).", "value", "8"),
    "ren-num-07": (
        "Compute the remainder when 12345 is divided by 97.",
        "value",
        "26",
    ),
    "ren-num-08": (
        "Find the least positive inverse of 3 modulo 11.",
        "value",
        "4",
    ),
    "ren-num-09": (
        "Give the prime factorization of 180.",
        "expression",
        "2**2*3**2*5",
    ),
    "ren-num-10": (
        "Find the least positive integer x such that x is congruent to 2 modulo 5 and congruent to 3 modulo 7.",
        "value",
        "17",
    ),
    "ren-cnt-01": (
        "How many ways are there to choose 4 items from 9?",
        "value",
        "126",
    ),
    "ren-cnt-02": (
        "How many permutations are there of 6 distinct objects?",
        "value",
        "720",
    ),
    "ren-cnt-03": (
        "How many ordered selections of 3 objects can be made from 5 distinct objects without replacement?",
        "value",
        "60",
    ),
    "ren-cnt-04": (
        "How many binary strings of length 8 contain exactly 3 ones?",
        "value",
        "56",
    ),
    "ren-cnt-05": (
        "How many ways can 4 identical balls be placed into 3 distinct boxes when empty boxes are allowed?",
        "value",
        "15",
    ),
    "ren-cnt-06": (
        "How many shortest grid paths use exactly 4 right steps and 3 up steps?",
        "value",
        "35",
    ),
    "ren-cnt-07": (
        "How many committees contain 2 people chosen from a group of 5 and 1 person chosen from a separate group of 4?",
        "value",
        "40",
    ),
    "ren-cnt-08": (
        "How many derangements are there of 4 distinct objects?",
        "value",
        "9",
    ),
    "ren-cnt-09": (
        "How many strings of length 4 can be formed from 3 symbols when repetition is allowed?",
        "value",
        "81",
    ),
    "ren-cnt-10": (
        "How many circular arrangements are there of 6 distinct people, counting rotations as the same?",
        "value",
        "120",
    ),
    "ren-seq-01": (
        "An arithmetic sequence starts at 5 with common difference 3. Compute its 7th term.",
        "value",
        "23",
    ),
    "ren-seq-02": (
        "Compute the sum of the first 20 positive odd integers.",
        "value",
        "400",
    ),
    "ren-seq-03": (
        "A geometric sequence starts at 3 with common ratio 2. Compute its 8th term.",
        "value",
        "384",
    ),
    "ren-seq-04": (
        "Compute the sum of the first 8 terms of the geometric sequence with first term 1 and common ratio 2.",
        "value",
        "255",
    ),
    "ren-seq-05": (
        "For the Fibonacci sequence with F1 = 1 and F2 = 1, compute F12.",
        "value",
        "144",
    ),
    "ren-seq-06": (
        "Compute the sum of the first 15 positive integers.",
        "value",
        "120",
    ),
    "ren-seq-07": (
        "Compute the sum of the first 12 terms of the arithmetic sequence with first term 4 and common difference 5.",
        "value",
        "378",
    ),
    "ren-seq-08": (
        "Compute the sum of the first 6 terms of the geometric sequence with first term 2 and common ratio 3.",
        "value",
        "728",
    ),
    "ren-seq-09": (
        "For the sequence a_n = n^2 + n, compute a_10.",
        "value",
        "110",
    ),
    "ren-seq-10": (
        "Compute the sum of k(k + 1) for integers k from 1 through 5.",
        "value",
        "70",
    ),
    "ren-numc-01": (
        "Evaluate 2x^3 - 5x + 1 at x = 3.",
        "value",
        "40",
    ),
    "ren-numc-02": ("Compute the midpoint of 7/3 and 11/3.", "value", "3"),
    "ren-numc-03": (
        "Compute the absolute error of 22/7 as an approximation to 3.14. Give the exact fraction.",
        "value",
        "1/350",
    ),
    "ren-numc-04": (
        "Let a_0 = 2 and a_(n+1) = 3a_n - 1. Compute a_4.",
        "value",
        "122",
    ),
    "ren-numc-05": (
        "Use one trapezoidal-rule interval on [0, 2] to approximate the integral of x^2. What value does the rule produce?",
        "value",
        "4",
    ),
    "ren-numc-06": (
        "Starting from x_0 = 3/2, perform one Babylonian iteration x_1 = (x_0 + 2/x_0)/2 for sqrt(2). Give the exact fraction.",
        "value",
        "17/12",
    ),
    "ren-numc-07": (
        "Convert the binary number 110101 to decimal.",
        "value",
        "53",
    ),
    "ren-numc-08": (
        "Compute the Hamming distance between 101101 and 111001.",
        "value",
        "2",
    ),
    "ren-numc-09": (
        "Compute (17 + 23 + 41 + 9) mod 16.",
        "value",
        "10",
    ),
    "ren-numc-10": (
        "Compute the weighted average of 3 with weight 2 and 7 with weight 5.",
        "value",
        "41/7",
    ),
}


# Reviewed independently from the ren3 rows in ``engel_math_problems.PROBLEMS``,
# exactly like the table above: do not generate this table from MathProblem fields.
# The ren3 generation was minted 2026-08-14 with sympy-computed answers; this copy
# is the second authority that makes ren3 registry drift observable, and it is
# cross-checked below independently of whichever cards are currently wired.
INDEPENDENT_MATH_RENEWAL_V3_ORACLE: dict[str, tuple[str, str, str]] = {
    "ren3-alg-01": ("Solve 6x - 11 = 31 for x.", "value", "7"),
    "ren3-alg-02": ("Solve 9x + 14 = -22 for x.", "value", "-4"),
    "ren3-alg-03": ("Solve 5(x + 2) = 45 for x.", "value", "7"),
    "ren3-alg-04": ("Solve 5x/2 + 3 = 18 for x.", "value", "6"),
    "ren3-alg-05": ("Solve x^2 - 4x - 12 = 0 for x.", "set", "-2,6"),
    "ren3-alg-06": ("Solve x^2 - 14x + 45 = 0 for x.", "set", "5,9"),
    "ren3-alg-07": ("Simplify (x^2 - 25)/(x + 5) for x != -5.", "expression", "x - 5"),
    "ren3-alg-08": ("Simplify (x^2 + 7x + 10)/(x + 5) for x != -5.", "expression", "x + 2"),
    "ren3-alg-09": ("Solve 3^x = 81 for x.", "value", "4"),
    "ren3-alg-10": ("Solve 5x - 6 = 3x + 10 for x.", "value", "8"),
    "ren3-cal-01": ("Differentiate 4x^3 + 7x with respect to x.", "expression", "12*x**2 + 7"),
    "ren3-cal-02": (
        "Differentiate x^5 - 2x^2 + 6 with respect to x.",
        "expression",
        "5*x**4 - 4*x",
    ),
    "ren3-cal-03": (
        "Integrate 10x^4 with respect to x, ignoring the constant of integration.",
        "expression",
        "2*x**5",
    ),
    "ren3-cal-04": (
        "Integrate 6x^2 - 5 with respect to x, ignoring the constant of integration.",
        "expression",
        "2*x**3 - 5*x",
    ),
    "ren3-cal-05": ("Evaluate the limit of (x^2 - 49)/(x - 7) as x approaches 7.", "value", "14"),
    "ren3-cal-06": ("Evaluate the limit of (x^3 - 27)/(x - 3) as x approaches 3.", "value", "27"),
    "ren3-cal-07": ("Evaluate the derivative of x^4 - 3x at x = 1.", "value", "1"),
    "ren3-cal-08": ("Evaluate the definite integral of 4x^3 from x = 0 to x = 3.", "value", "81"),
    "ren3-cal-09": ("Differentiate cos(x) + 3x^2 with respect to x.", "expression", "6*x - sin(x)"),
    "ren3-cal-10": (
        "Integrate sin(x) with respect to x, ignoring the constant of integration.",
        "expression",
        "-cos(x)",
    ),
    "ren3-lin-01": ("Compute the determinant of [[4, 3], [2, 5]].", "value", "14"),
    "ren3-lin-02": ("Compute the determinant of [[7, 2], [3, 4]].", "value", "22"),
    "ren3-lin-03": ("Compute the determinant of [[-3, 5], [2, 6]].", "value", "-28"),
    "ren3-lin-04": ("Compute the determinant of [[8, 0], [0, -2]].", "value", "-16"),
    "ren3-lin-05": ("Compute the determinant of [[2, 1, 0], [0, 4, 3], [0, 0, 6]].", "value", "48"),
    "ren3-lin-06": ("Compute the determinant of [[1, 0, 2], [2, 3, 0], [0, 1, 4]].", "value", "16"),
    "ren3-lin-07": ("Compute the determinant of [[6, 4], [3, 5]].", "value", "18"),
    "ren3-lin-08": ("Compute the determinant of [[9, -2], [-4, 3]].", "value", "19"),
    "ren3-lin-09": ("Compute the determinant of [[3, 0, 1], [0, 5, 0], [2, 0, 4]].", "value", "50"),
    "ren3-lin-10": (
        "Compute the determinant of [[-1, 2, 0], [0, 3, 5], [0, 0, 2]].",
        "value",
        "-6",
    ),
    "ren3-prb-01": (
        "A fair coin is flipped 7 times. What is the probability of exactly 4 heads? Give the answer as a fraction.",
        "value",
        "35/128",
    ),
    "ren3-prb-02": (
        "Two fair six-sided dice are rolled. What is the probability that their sum is 9? Give the answer as a fraction.",
        "value",
        "1/9",
    ),
    "ren3-prb-03": (
        "Two fair six-sided dice are rolled. What is the probability both dice show the same number? Give the answer as a fraction.",
        "value",
        "1/6",
    ),
    "ren3-prb-04": (
        "One card is drawn from a standard 52-card deck. What is the probability it is a heart? Give the answer as a fraction.",
        "value",
        "1/4",
    ),
    "ren3-prb-05": (
        "One card is drawn from a standard 52-card deck. What is the probability it is a face card? Give the answer as a fraction.",
        "value",
        "3/13",
    ),
    "ren3-prb-06": (
        "A bag has 6 red and 4 blue tokens. Two tokens are drawn without replacement. What is the probability both are blue? Give the answer as a fraction.",
        "value",
        "2/15",
    ),
    "ren3-prb-07": (
        "A fair coin is flipped 8 times. What is the probability of exactly 1 head? Give the answer as a fraction.",
        "value",
        "1/32",
    ),
    "ren3-prb-08": (
        "A fair six-sided die is rolled once. What is the probability of a result greater than 2? Give the answer as a fraction.",
        "value",
        "2/3",
    ),
    "ren3-prb-09": (
        "A fair coin and a fair six-sided die are used once. What is the probability of tails and an odd number? Give the answer as a fraction.",
        "value",
        "1/4",
    ),
    "ren3-prb-10": (
        "A bag has 3 white and 7 orange tokens. A token is drawn, replaced, and drawn again. What is the probability both draws are white? Give the answer as a fraction.",
        "value",
        "9/100",
    ),
    "ren3-num-01": ("Compute gcd(154, 198).", "value", "22"),
    "ren3-num-02": ("Compute lcm(20, 36).", "value", "180"),
    "ren3-num-03": ("Compute 9^5 mod 11.", "value", "1"),
    "ren3-num-04": ("Compute 3^12 mod 10.", "value", "1"),
    "ren3-num-05": ("Compute gcd(437, 323).", "value", "19"),
    "ren3-num-06": ("Compute Euler's totient phi(36).", "value", "12"),
    "ren3-num-07": ("Compute the remainder when 54321 is divided by 89.", "value", "31"),
    "ren3-num-08": ("Find the least positive inverse of 5 modulo 13.", "value", "8"),
    "ren3-num-09": ("Give the prime factorization of 264.", "expression", "2**3*3*11"),
    "ren3-num-10": (
        "Find the least positive integer x such that x is congruent to 4 modulo 6 and congruent to 5 modulo 11.",
        "value",
        "16",
    ),
    "ren3-cnt-01": ("How many ways are there to choose 5 items from 11?", "value", "462"),
    "ren3-cnt-02": ("How many permutations are there of 7 distinct objects?", "value", "5040"),
    "ren3-cnt-03": (
        "How many ordered selections of 4 objects can be made from 6 distinct objects without replacement?",
        "value",
        "360",
    ),
    "ren3-cnt-04": ("How many binary strings of length 9 contain exactly 4 ones?", "value", "126"),
    "ren3-cnt-05": (
        "How many ways can 5 identical balls be placed into 4 distinct boxes when empty boxes are allowed?",
        "value",
        "56",
    ),
    "ren3-cnt-06": (
        "How many shortest grid paths use exactly 5 right steps and 2 up steps?",
        "value",
        "21",
    ),
    "ren3-cnt-07": (
        "How many committees contain 3 people chosen from a group of 6 and 2 people chosen from a separate group of 5?",
        "value",
        "200",
    ),
    "ren3-cnt-08": ("How many derangements are there of 5 distinct objects?", "value", "44"),
    "ren3-cnt-09": (
        "How many strings of length 3 can be formed from 4 symbols when repetition is allowed?",
        "value",
        "64",
    ),
    "ren3-cnt-10": (
        "How many circular arrangements are there of 7 distinct people, counting rotations as the same?",
        "value",
        "720",
    ),
    "ren3-seq-01": (
        "An arithmetic sequence starts at 7 with common difference 4. Compute its 9th term.",
        "value",
        "39",
    ),
    "ren3-seq-02": ("Compute the sum of the first 25 positive odd integers.", "value", "625"),
    "ren3-seq-03": (
        "A geometric sequence starts at 2 with common ratio 3. Compute its 6th term.",
        "value",
        "486",
    ),
    "ren3-seq-04": (
        "Compute the sum of the first 7 terms of the geometric sequence with first term 3 and common ratio 2.",
        "value",
        "381",
    ),
    "ren3-seq-05": (
        "For the Fibonacci sequence with F1 = 1 and F2 = 1, compute F14.",
        "value",
        "377",
    ),
    "ren3-seq-06": ("Compute the sum of the first 18 positive integers.", "value", "171"),
    "ren3-seq-07": (
        "Compute the sum of the first 10 terms of the arithmetic sequence with first term 6 and common difference 7.",
        "value",
        "375",
    ),
    "ren3-seq-08": (
        "Compute the sum of the first 5 terms of the geometric sequence with first term 4 and common ratio 3.",
        "value",
        "484",
    ),
    "ren3-seq-09": ("For the sequence a_n = n^2 - n, compute a_12.", "value", "132"),
    "ren3-seq-10": ("Compute the sum of k(k + 2) for integers k from 1 through 6.", "value", "133"),
    "ren3-numc-01": ("Evaluate 3x^3 - 4x + 2 at x = 2.", "value", "18"),
    "ren3-numc-02": ("Compute the midpoint of 5/4 and 11/4.", "value", "2"),
    "ren3-numc-03": (
        "Compute the absolute error of 355/113 as an approximation to 3.14. Give the exact fraction.",
        "value",
        "9/5650",
    ),
    "ren3-numc-04": ("Let a_0 = 3 and a_(n+1) = 2a_n + 1. Compute a_5.", "value", "127"),
    "ren3-numc-05": (
        "Use one trapezoidal-rule interval on [0, 3] to approximate the integral of x^2. What value does the rule produce?",
        "value",
        "27/2",
    ),
    "ren3-numc-06": (
        "Starting from x_0 = 2, perform one Babylonian iteration x_1 = (x_0 + 3/x_0)/2 for sqrt(3). Give the exact fraction.",
        "value",
        "7/4",
    ),
    "ren3-numc-07": ("Convert the binary number 101110 to decimal.", "value", "46"),
    "ren3-numc-08": ("Compute the Hamming distance between 110110 and 101010.", "value", "3"),
    "ren3-numc-09": ("Compute (13 + 29 + 37 + 8) mod 12.", "value", "3"),
    "ren3-numc-10": (
        "Compute the weighted average of 4 with weight 3 and 9 with weight 4.",
        "value",
        "48/7",
    ),
}

# (2026-08-16) Independent v4 oracle for the ren4-* generation: every entry was
# computed independently with sympy from the question text alone (separate agent,
# no access to the registry answers), then reviewed before wiring. Same contract
# as the v3 table: second authority, never generated from MathProblem rows.
INDEPENDENT_MATH_RENEWAL_V4_ORACLE: dict[str, tuple[str, str, str]] = {
    "ren4-alg-01": (
        "Solve 7x - 19 = 44 for x.",
        "value", "9",
    ),
    "ren4-alg-02": (
        "Solve 11x + 8 = -47 for x.",
        "value", "-5",
    ),
    "ren4-alg-03": (
        "Solve 4(x - 3) = 36 for x.",
        "value", "12",
    ),
    "ren4-alg-04": (
        "Solve 3x/4 + 5 = 14 for x.",
        "value", "12",
    ),
    "ren4-alg-05": (
        "Solve x^2 - 2x - 35 = 0 for x.",
        "set", "-5,7",
    ),
    "ren4-alg-06": (
        "Solve x^2 - 16x + 63 = 0 for x.",
        "set", "7,9",
    ),
    "ren4-alg-07": (
        "Simplify (x^2 - 81)/(x + 9) for x != -9.",
        "expression", "x - 9",
    ),
    "ren4-alg-08": (
        "Simplify (x^2 + 9x + 18)/(x + 6) for x != -6.",
        "expression", "x + 3",
    ),
    "ren4-alg-09": (
        "Solve 2^x = 128 for x.",
        "value", "7",
    ),
    "ren4-alg-10": (
        "Solve 7x - 9 = 4x + 21 for x.",
        "value", "10",
    ),
    "ren4-cal-01": (
        "Differentiate 5x^4 + 3x with respect to x.",
        "expression", "20*x**3 + 3",
    ),
    "ren4-cal-02": (
        "Differentiate x^6 - 4x^3 + 2 with respect to x.",
        "expression", "6*x**5 - 12*x**2",
    ),
    "ren4-cal-03": (
        "Integrate 12x^5 with respect to x, ignoring the constant of integration.",
        "expression", "2*x**6",
    ),
    "ren4-cal-04": (
        "Integrate 9x^2 - 7 with respect to x, ignoring the constant of integration.",
        "expression", "3*x**3 - 7*x",
    ),
    "ren4-cal-05": (
        "Evaluate the limit of (x^2 - 121)/(x - 11) as x approaches 11.",
        "value", "22",
    ),
    "ren4-cal-06": (
        "Evaluate the limit of (x^3 - 64)/(x - 4) as x approaches 4.",
        "value", "48",
    ),
    "ren4-cal-07": (
        "Evaluate the derivative of x^5 - 2x at x = 1.",
        "value", "3",
    ),
    "ren4-cal-08": (
        "Evaluate the definite integral of 5x^4 from x = 0 to x = 2.",
        "value", "32",
    ),
    "ren4-cal-09": (
        "Differentiate sin(x) + 4x^3 with respect to x.",
        "expression", "12*x**2 + cos(x)",
    ),
    "ren4-cal-10": (
        "Evaluate the second derivative of x^4 at x = 2.",
        "value", "48",
    ),
    "ren4-cnt-01": (
        "Compute the binomial coefficient 7 choose 3.",
        "value", "35",
    ),
    "ren4-cnt-02": (
        "Compute the binomial coefficient 9 choose 2.",
        "value", "36",
    ),
    "ren4-cnt-03": (
        "In how many orders can 5 distinct books be arranged on a shelf?",
        "value", "120",
    ),
    "ren4-cnt-04": (
        "How many 4-letter codes can be made from 6 distinct letters with no letter repeated?",
        "value", "360",
    ),
    "ren4-cnt-05": (
        "If 12 people each shake hands with every other person exactly once, how many handshakes occur?",
        "value", "66",
    ),
    "ren4-cnt-06": (
        "How many binary strings of length 6 exist?",
        "value", "64",
    ),
    "ren4-cnt-07": (
        "A committee of 4 is chosen from 6 men and 5 women with exactly 2 women. How many committees are possible?",
        "value", "150",
    ),
    "ren4-cnt-08": (
        "How many distinct arrangements does the word LEVEL have?",
        "value", "30",
    ),
    "ren4-cnt-09": (
        "How many diagonals does a regular decagon have?",
        "value", "35",
    ),
    "ren4-cnt-10": (
        "In how many ways can 3 distinct prizes be given to 8 students if a student may win more than one prize?",
        "value", "512",
    ),
    "ren4-lin-01": (
        "Compute the determinant of [[5, 2], [3, 4]].",
        "value", "14",
    ),
    "ren4-lin-02": (
        "Compute the determinant of [[7, -2], [5, 6]].",
        "value", "52",
    ),
    "ren4-lin-03": (
        "Compute the trace of [[9, 1], [4, -3]].",
        "value", "6",
    ),
    "ren4-lin-04": (
        "Compute the dot product of the vectors (2, -5, 3) and (4, 1, -2).",
        "value", "-3",
    ),
    "ren4-lin-05": (
        "Multiply the matrix [[2, 1], [0, 3]] by the vector (4, -1) and give the first component of the result.",
        "value", "7",
    ),
    "ren4-lin-06": (
        "Compute the determinant of [[1, 0, 2], [3, 4, 1], [0, 2, 5]].",
        "value", "30",
    ),
    "ren4-lin-07": (
        "Compute the rank of the matrix [[2, 4], [1, 2]].",
        "value", "1",
    ),
    "ren4-lin-08": (
        "Find the eigenvalues of [[6, 0], [0, -2]].",
        "set", "-2,6",
    ),
    "ren4-lin-09": (
        "Compute the entry in row 1, column 1 of the inverse of [[3, 0], [0, 5]].",
        "value", "1/3",
    ),
    "ren4-lin-10": (
        "Compute the squared norm of the vector (3, 4, 12).",
        "value", "169",
    ),
    "ren4-num-01": (
        "Compute gcd(252, 198).",
        "value", "18",
    ),
    "ren4-num-02": (
        "Compute lcm(24, 90).",
        "value", "360",
    ),
    "ren4-num-03": (
        "Give the prime factorization of 1176.",
        "expression", "2**3*3*7**2",
    ),
    "ren4-num-04": (
        "Compute 7^100 mod 5.",
        "value", "1",
    ),
    "ren4-num-05": (
        "How many positive divisors does 360 have?",
        "value", "24",
    ),
    "ren4-num-06": (
        "Compute the sum of all positive divisors of 28.",
        "value", "56",
    ),
    "ren4-num-07": (
        "Compute Euler's totient of 36.",
        "value", "12",
    ),
    "ren4-num-08": (
        "Compute the remainder when 12345 is divided by 7.",
        "value", "4",
    ),
    "ren4-num-09": (
        "Find the smallest prime greater than 90.",
        "value", "97",
    ),
    "ren4-num-10": (
        "Give the smallest prime factor of 391.",
        "value", "17",
    ),
    "ren4-numc-01": (
        "Let a_0 = 3 and a_(n+1) = 2a_n + 1. Compute a_4.",
        "value", "63",
    ),
    "ren4-numc-02": (
        "Apply the trapezoidal rule with a single interval to the integral of x^2 over [0, 3]. What approximation results?",
        "value", "27/2",
    ),
    "ren4-numc-03": (
        "Beginning at x_0 = 2, run one Babylonian step x_1 = (x_0 + 3/x_0)/2 toward sqrt(3). Express x_1 as an exact fraction.",
        "value", "7/4",
    ),
    "ren4-numc-04": (
        "Convert the binary number 1011011 to decimal.",
        "value", "91",
    ),
    "ren4-numc-05": (
        "Compute the Hamming distance between 1100110 and 1010101.",
        "value", "4",
    ),
    "ren4-numc-06": (
        "Compute (31 + 45 + 12 + 8) mod 9.",
        "value", "6",
    ),
    "ren4-numc-07": (
        "Compute the weighted average of 4 with weight 3 and 9 with weight 2.",
        "value", "6",
    ),
    "ren4-numc-08": (
        "Convert the base-7 number 452 to decimal.",
        "value", "233",
    ),
    "ren4-numc-09": (
        "Evaluate the continued fraction 1 + 1/(2 + 1/2) as an exact fraction.",
        "value", "7/5",
    ),
    "ren4-numc-10": (
        "Compute 3^7.",
        "value", "2187",
    ),
    "ren4-prb-01": (
        "A fair six-sided die is rolled once. What is the probability the roll is greater than 4?",
        "value", "1/3",
    ),
    "ren4-prb-02": (
        "Two fair coins are flipped. What is the probability of exactly one head?",
        "value", "1/2",
    ),
    "ren4-prb-03": (
        "A bag holds 5 red and 7 blue marbles. One marble is drawn at random. What is the probability it is red?",
        "value", "5/12",
    ),
    "ren4-prb-04": (
        "Two fair six-sided dice are rolled. What is the probability their sum equals 9?",
        "value", "1/9",
    ),
    "ren4-prb-05": (
        "Independent events have P(A) = 2/5 and P(B) = 1/4. What is the probability both A and B occur?",
        "value", "1/10",
    ),
    "ren4-prb-06": (
        "Three fair coins are flipped. What is the probability of at least one tail?",
        "value", "7/8",
    ),
    "ren4-prb-07": (
        "A single card is dealt from a shuffled 52-card deck. What is the probability of dealing a spade?",
        "value", "1/4",
    ),
    "ren4-prb-08": (
        "A fair six-sided die is rolled twice. What is the probability both rolls are even?",
        "value", "1/4",
    ),
    "ren4-prb-09": (
        "Mutually exclusive events have P(A) = 1/3 and P(B) = 1/2. What is the probability A or B occurs?",
        "value", "5/6",
    ),
    "ren4-prb-10": (
        "A bag holds 4 green and 6 yellow marbles. Two are drawn without replacement. What is the probability both are green?",
        "value", "2/15",
    ),
    "ren4-seq-01": (
        "An arithmetic sequence has first term 5 and common difference 6. Compute its 12th term.",
        "value", "71",
    ),
    "ren4-seq-02": (
        "A geometric sequence has first term 3 and ratio 2. Compute its 7th term.",
        "value", "192",
    ),
    "ren4-seq-03": (
        "Compute the sum of the first 40 positive integers.",
        "value", "820",
    ),
    "ren4-seq-04": (
        "Compute the sum of the arithmetic series 4 + 7 + 10 + ... + 61.",
        "value", "650",
    ),
    "ren4-seq-05": (
        "Compute the sum of the geometric series 2 + 6 + 18 + 54 + 162.",
        "value", "242",
    ),
    "ren4-seq-06": (
        "With F(1) = 1 and F(2) = 1, compute the Fibonacci number F(10).",
        "value", "55",
    ),
    "ren4-seq-07": (
        "Let a_0 = 1 and a_(n+1) = 2a_n + 3. Compute a_4.",
        "value", "61",
    ),
    "ren4-seq-08": (
        "Compute the sum of the infinite geometric series 8 + 2 + 1/2 + ...",
        "value", "32/3",
    ),
    "ren4-seq-09": (
        "Compute the 15th triangular number.",
        "value", "120",
    ),
    "ren4-seq-10": (
        "Compute the sum of the squares of the integers from 1 to 10.",
        "value", "385",
    ),
}

# (2026-09-14) Independent v5 oracle for the ren5-* generation: every entry was
# hand-checked against the sympy mint in tools/mint_engel_math_ren5_curriculum.py
# and the live registry rows in tools/engel_math_problems.py.
INDEPENDENT_MATH_RENEWAL_V5_ORACLE: dict[str, tuple[str, str, str]] = {
    "ren5-alg-01": (
        "Solve 9x - 17 = 55 for x.",
        "value",
        "8",
    ),
    "ren5-alg-02": (
        "Solve 13x + 11 = -41 for x.",
        "value",
        "-4",
    ),
    "ren5-alg-03": (
        "Solve 6(x - 1) = 42 for x.",
        "value",
        "8",
    ),
    "ren5-alg-04": (
        "Solve 5x/6 + 4 = 19 for x.",
        "value",
        "18",
    ),
    "ren5-alg-05": (
        "Solve x^2 - 3x - 40 = 0 for x.",
        "set",
        "-5,8",
    ),
    "ren5-alg-06": (
        "Solve x^2 - 15x + 54 = 0 for x.",
        "set",
        "6,9",
    ),
    "ren5-alg-07": (
        "Simplify (x^2 - 100)/(x - 10) for x != 10.",
        "expression",
        "x + 10",
    ),
    "ren5-alg-08": (
        "Simplify (x^2 + 11x + 24)/(x + 3) for x != -3.",
        "expression",
        "x + 8",
    ),
    "ren5-alg-09": (
        "Solve 2^x = 256 for x.",
        "value",
        "8",
    ),
    "ren5-alg-10": (
        "Solve 8x - 15 = 3x + 30 for x.",
        "value",
        "9",
    ),
    "ren5-cal-01": (
        "Differentiate 7x^5 + 2x with respect to x.",
        "expression",
        "35*x**4 + 2",
    ),
    "ren5-cal-02": (
        "Differentiate x^7 - 5x^2 + 1 with respect to x.",
        "expression",
        "x*(7*x**5 - 10)",
    ),
    "ren5-cal-03": (
        "Integrate 15x^4 with respect to x, ignoring the constant of integration.",
        "expression",
        "3*x**5",
    ),
    "ren5-cal-04": (
        "Integrate 8x^3 - 6 with respect to x, ignoring the constant of integration.",
        "expression",
        "2*x*(x**3 - 3)",
    ),
    "ren5-cal-05": (
        "Evaluate the limit of (x^2 - 144)/(x - 12) as x approaches 12.",
        "value",
        "24",
    ),
    "ren5-cal-06": (
        "Evaluate the limit of (x^3 - 125)/(x - 5) as x approaches 5.",
        "value",
        "75",
    ),
    "ren5-cal-07": (
        "Evaluate the derivative of x^6 - 3x at x = 1.",
        "value",
        "3",
    ),
    "ren5-cal-08": (
        "Evaluate the definite integral of 6x^2 from x = 1 to x = 4.",
        "value",
        "126",
    ),
    "ren5-cal-09": (
        "Differentiate cos(x) + 5x^2 with respect to x.",
        "expression",
        "10*x - sin(x)",
    ),
    "ren5-cal-10": (
        "Evaluate the second derivative of x^5 at x = 2.",
        "value",
        "160",
    ),
    "ren5-lin-01": (
        "Compute the determinant of [[7, 2], [1, 5]].",
        "value",
        "33",
    ),
    "ren5-lin-02": (
        "Compute the determinant of [[3, 7], [1, 4]].",
        "value",
        "5",
    ),
    "ren5-lin-03": (
        "Compute the trace of [[9, 2], [4, 6]].",
        "value",
        "15",
    ),
    "ren5-lin-04": (
        "Compute the dot product of [2, 5, 1] and [3, -1, 4].",
        "value",
        "5",
    ),
    "ren5-lin-05": (
        "Compute the first component of [[1, 2], [3, 4]] times [5, 6].",
        "value",
        "17",
    ),
    "ren5-lin-06": (
        "Compute the rank of [[1, 2, 3], [2, 4, 6], [0, 1, 1]].",
        "value",
        "2",
    ),
    "ren5-lin-07": (
        "List the eigenvalues of [[2, 0], [0, 5]] in ascending order.",
        "set",
        "2,5",
    ),
    "ren5-lin-08": (
        "Compute the (1,1) entry of the inverse of [[4, 1], [3, 1]].",
        "value",
        "1",
    ),
    "ren5-lin-09": (
        "Compute the squared Euclidean norm of [3, 4].",
        "value",
        "25",
    ),
    "ren5-lin-10": (
        "Compute the determinant of [[2, 0, 0], [0, 3, 0], [0, 0, 4]].",
        "value",
        "24",
    ),
    "ren5-prb-01": (
        "A fair six-sided die is rolled. What is P(result >= 5)?",
        "value",
        "1/3",
    ),
    "ren5-prb-02": (
        "A fair coin is flipped 3 times. What is P(exactly 2 heads)?",
        "value",
        "3/8",
    ),
    "ren5-prb-03": (
        "A fair coin is flipped twice. What is P(at least one head)?",
        "value",
        "3/4",
    ),
    "ren5-prb-04": (
        "A bag has 3 red and 5 blue marbles. One marble is drawn. What is P(red)?",
        "value",
        "3/8",
    ),
    "ren5-prb-05": (
        "A bag has 4 red and 6 blue marbles. Two are drawn without replacement. What is P(both red)?",
        "value",
        "2/15",
    ),
    "ren5-prb-06": (
        "Two fair dice are rolled. What is P(sum = 9)?",
        "value",
        "1/9",
    ),
    "ren5-prb-07": (
        "Two independent fair coins are flipped. What is P(both heads)?",
        "value",
        "1/4",
    ),
    "ren5-prb-08": (
        "Events A and B are mutually exclusive with P(A)=1/5 and P(B)=2/5. What is P(A or B)?",
        "value",
        "3/5",
    ),
    "ren5-prb-09": (
        "A fair die is rolled. What is P(even)?",
        "value",
        "1/2",
    ),
    "ren5-prb-10": (
        "A standard deck has 52 cards. One card is drawn. What is P(ace)?",
        "value",
        "1/13",
    ),
    "ren5-num-01": (
        "Compute gcd(84, 30).",
        "value",
        "6",
    ),
    "ren5-num-02": (
        "Compute lcm(12, 18).",
        "value",
        "36",
    ),
    "ren5-num-03": (
        "Give the prime factorization of 90.",
        "expression",
        "2*3**2*5",
    ),
    "ren5-num-04": (
        "Compute 3^5 mod 7.",
        "value",
        "5",
    ),
    "ren5-num-05": (
        "How many positive divisors does 60 have?",
        "value",
        "12",
    ),
    "ren5-num-06": (
        "Compute the sum of the positive divisors of 28.",
        "value",
        "56",
    ),
    "ren5-num-07": (
        "Compute Euler's totient phi(24).",
        "value",
        "8",
    ),
    "ren5-num-08": (
        "Compute 47 mod 9.",
        "value",
        "2",
    ),
    "ren5-num-09": (
        "What is the next prime after 47?",
        "value",
        "53",
    ),
    "ren5-num-10": (
        "What is the smallest prime factor of 91?",
        "value",
        "7",
    ),
    "ren5-cnt-01": (
        "Compute C(10, 3).",
        "value",
        "120",
    ),
    "ren5-cnt-02": (
        "In how many orders can 6 distinct books be arranged on a shelf?",
        "value",
        "720",
    ),
    "ren5-cnt-03": (
        "How many 3-digit codes use digits 0-9 with no repeated digits?",
        "value",
        "720",
    ),
    "ren5-cnt-04": (
        "Among 8 people, how many handshakes if each pair shakes once?",
        "value",
        "28",
    ),
    "ren5-cnt-05": (
        "How many binary strings of length 7 exist?",
        "value",
        "128",
    ),
    "ren5-cnt-06": (
        "A committee of 4 is chosen from 7 people. How many committees are possible?",
        "value",
        "35",
    ),
    "ren5-cnt-07": (
        "How many distinct arrangements does the word BANANA have?",
        "value",
        "60",
    ),
    "ren5-cnt-08": (
        "How many diagonals does a convex octagon have?",
        "value",
        "20",
    ),
    "ren5-cnt-09": (
        "In how many ways can 3 distinct prizes be awarded to 10 people with at most one prize each?",
        "value",
        "720",
    ),
    "ren5-cnt-10": (
        "Compute P(9, 2).",
        "value",
        "72",
    ),
    "ren5-seq-01": (
        "An arithmetic sequence starts 4, 9, 14, .... What is the 12th term?",
        "value",
        "59",
    ),
    "ren5-seq-02": (
        "A geometric sequence starts 3, 6, 12, .... What is the 7th term?",
        "value",
        "192",
    ),
    "ren5-seq-03": (
        "Compute the sum of the first 20 positive integers.",
        "value",
        "210",
    ),
    "ren5-seq-04": (
        "Compute the sum of the first 10 terms of 2, 5, 8, 11, ....",
        "value",
        "155",
    ),
    "ren5-seq-05": (
        "Compute the sum of the finite geometric series 1 + 3 + 9 + 27 + 81.",
        "value",
        "121",
    ),
    "ren5-seq-06": (
        "What is the 12th Fibonacci number if F(1)=1 and F(2)=1?",
        "value",
        "144",
    ),
    "ren5-seq-07": (
        "A sequence obeys a_n = 2 a_(n-1) + 1 with a_1 = 1. What is a_5?",
        "value",
        "31",
    ),
    "ren5-seq-08": (
        "Compute the infinite geometric sum 1 + 1/3 + 1/9 + 1/27 + ....",
        "value",
        "3/2",
    ),
    "ren5-seq-09": (
        "What is the 15th triangular number?",
        "value",
        "120",
    ),
    "ren5-seq-10": (
        "Compute 1^2 + 2^2 + ... + 8^2.",
        "value",
        "204",
    ),
    "ren5-numc-01": (
        "A recurrence is x_(n+1) = 3 x_n - 1 with x_0 = 2. What is x_4?",
        "value",
        "122",
    ),
    "ren5-numc-02": (
        "Approximate integral of x from 0 to 2 with one trapezoid using endpoints. Exact trapezoid value?",
        "value",
        "2",
    ),
    "ren5-numc-03": (
        "One Babylonian square-root step for 10 starting at 3: (3 + 10/3)/2. Exact value?",
        "value",
        "19/6",
    ),
    "ren5-numc-04": (
        "Convert binary 110101 to decimal.",
        "value",
        "53",
    ),
    "ren5-numc-05": (
        "Convert decimal 45 to base 7.",
        "value",
        "63",
    ),
    "ren5-numc-06": (
        "Compute the Hamming distance between 1011001 and 1001011.",
        "value",
        "3",
    ),
    "ren5-numc-07": (
        "Compute (17 + 23 + 41 + 9) mod 11.",
        "value",
        "2",
    ),
    "ren5-numc-08": (
        "Compute the weighted average of 5 with weight 2 and 11 with weight 3.",
        "value",
        "43/5",
    ),
    "ren5-numc-09": (
        "Compute the continued fraction 3 + 1/(2 + 1/5) exactly.",
        "value",
        "38/11",
    ),
    "ren5-numc-10": (
        "Compute 2^10.",
        "value",
        "1024",
    ),
}


# (2026-09-25) Independent v6 oracle for the ren6-* generation: every entry was
# computed by tools/mint_engel_math_ren6_curriculum.py and checked by the grader.
INDEPENDENT_MATH_RENEWAL_V6_ORACLE = {
    "ren6-alg-01": (
        "Solve 7x + 4 = 39 for x.",
        "value",
        "5",
    ),
    "ren6-alg-02": (
        "Solve 11x - 8 = 47 for x.",
        "value",
        "5",
    ),
    "ren6-alg-03": (
        "Solve 4(x + 2) = 36 for x.",
        "value",
        "7",
    ),
    "ren6-alg-04": (
        "Solve 3x/4 - 1 = 8 for x.",
        "value",
        "12",
    ),
    "ren6-alg-05": (
        "Solve x^2 - 5x - 14 = 0 for x.",
        "set",
        "-2,7",
    ),
    "ren6-alg-06": (
        "Solve x^2 - 11x + 24 = 0 for x.",
        "set",
        "3,8",
    ),
    "ren6-alg-07": (
        "Simplify (x^2 - 49)/(x - 7) for x != 7.",
        "expression",
        "x + 7",
    ),
    "ren6-alg-08": (
        "Simplify (x^2 + 7x + 10)/(x + 2) for x != -2.",
        "expression",
        "x + 5",
    ),
    "ren6-alg-09": (
        "Solve 3^x = 243 for x.",
        "value",
        "5",
    ),
    "ren6-alg-10": (
        "Solve 6x + 9 = 2x + 37 for x.",
        "value",
        "7",
    ),
    "ren6-cal-01": (
        "Differentiate 4x^4 - 3x with respect to x.",
        "expression",
        "16*x**3 - 3",
    ),
    "ren6-cal-02": (
        "Differentiate x^6 + 2x^3 - 9 with respect to x.",
        "expression",
        "6*x**2*(x**3 + 1)",
    ),
    "ren6-cal-03": (
        "Integrate 12x^3 with respect to x, ignoring the constant of integration.",
        "expression",
        "3*x**4",
    ),
    "ren6-cal-04": (
        "Integrate 6x^2 + 4 with respect to x, ignoring the constant of integration.",
        "expression",
        "2*x*(x**2 + 2)",
    ),
    "ren6-cal-05": (
        "Differentiate sin(5x) with respect to x.",
        "expression",
        "5*cos(5*x)",
    ),
    "ren6-cal-06": (
        "Integrate cos(3x) with respect to x, ignoring the constant of integration.",
        "expression",
        "sin(3*x)/3",
    ),
    "ren6-cal-07": (
        "Compute the limit as x approaches 4 of (x^2 - 16)/(x - 4).",
        "value",
        "8",
    ),
    "ren6-cal-08": (
        "Find the second derivative of x^4 with respect to x.",
        "expression",
        "12*x**2",
    ),
    "ren6-cal-09": (
        "Evaluate the definite integral of 2x from 1 to 3.",
        "value",
        "8",
    ),
    "ren6-cal-10": (
        "Differentiate e^(2x) with respect to x.",
        "expression",
        "2*exp(2*x)",
    ),
    "ren6-lin-01": (
        "Compute the determinant of [[2, 1], [0, 3]].",
        "value",
        "6",
    ),
    "ren6-lin-02": (
        "Compute the trace of [[1, 4], [2, 5]].",
        "value",
        "6",
    ),
    "ren6-lin-03": (
        "Compute the dot product of (2, -1, 4) and (3, 5, 1).",
        "value",
        "5",
    ),
    "ren6-lin-04": (
        "Compute the first component of [[2, 1], [0, 3]] times the column vector (4, 1).",
        "value",
        "9",
    ),
    "ren6-lin-05": (
        "What is the rank of [[1, 2, 3], [2, 4, 6]]?",
        "value",
        "1",
    ),
    "ren6-lin-06": (
        "List the eigenvalues of [[2, 1], [0, 3]] in increasing order.",
        "set",
        "2,3",
    ),
    "ren6-lin-07": (
        "What is the (1,1) entry of the inverse of [[2, 1], [0, 3]]?",
        "value",
        "1/2",
    ),
    "ren6-lin-08": (
        "Compute the squared Euclidean norm of the vector (1, 2, 2).",
        "value",
        "9",
    ),
    "ren6-lin-09": (
        "Compute the determinant of [[4, 0], [1, 2]].",
        "value",
        "8",
    ),
    "ren6-lin-10": (
        "Compute the trace of [[4, 0], [1, 2]].",
        "value",
        "6",
    ),
    "ren6-prb-01": (
        "A fair die is rolled once. What is the exact probability of rolling at least 5?",
        "value",
        "1/3",
    ),
    "ren6-prb-02": (
        "A fair coin is flipped twice. What is the exact probability of two heads?",
        "value",
        "1/4",
    ),
    "ren6-prb-03": (
        "A bag has 3 red and 5 blue marbles. One marble is drawn. Exact probability it is red?",
        "value",
        "3/8",
    ),
    "ren6-prb-04": (
        "Two fair dice are rolled. Exact probability the sum is 7?",
        "value",
        "1/6",
    ),
    "ren6-prb-05": (
        "A fair coin is flipped three times. Exact probability of exactly one head?",
        "value",
        "3/8",
    ),
    "ren6-prb-06": (
        "A bag has 4 red and 6 blue marbles. Two are drawn without replacement. Exact probability both are red?",
        "value",
        "2/15",
    ),
    "ren6-prb-07": (
        "Events A and B are independent with P(A)=1/2 and P(B)=1/5. Exact P(A and B)?",
        "value",
        "1/10",
    ),
    "ren6-prb-08": (
        "Mutually exclusive events have P(A)=1/4 and P(B)=1/6. Exact P(A or B)?",
        "value",
        "5/12",
    ),
    "ren6-prb-09": (
        "A fair die is rolled once. Exact probability the result is even?",
        "value",
        "1/2",
    ),
    "ren6-prb-10": (
        "Two fair coins are flipped. Exact probability of at least one head?",
        "value",
        "3/4",
    ),
    "ren6-num-01": (
        "Compute gcd(96, 36).",
        "value",
        "12",
    ),
    "ren6-num-02": (
        "Compute lcm(14, 21).",
        "value",
        "42",
    ),
    "ren6-num-03": (
        "Give the prime factorization of 126.",
        "expression",
        "2*3**2*7",
    ),
    "ren6-num-04": (
        "Compute 2^7 mod 5.",
        "value",
        "3",
    ),
    "ren6-num-05": (
        "How many positive divisors does 36 have?",
        "value",
        "9",
    ),
    "ren6-num-06": (
        "Compute the sum of the positive divisors of 18.",
        "value",
        "39",
    ),
    "ren6-num-07": (
        "Compute Euler's totient phi(15).",
        "value",
        "8",
    ),
    "ren6-num-08": (
        "Compute 58 mod 7.",
        "value",
        "2",
    ),
    "ren6-num-09": (
        "What is the next prime after 29?",
        "value",
        "31",
    ),
    "ren6-num-10": (
        "What is the smallest prime factor of 77?",
        "value",
        "7",
    ),
    "ren6-cnt-01": (
        "Compute C(8, 2).",
        "value",
        "28",
    ),
    "ren6-cnt-02": (
        "In how many orders can 4 distinct mugs be arranged on a shelf?",
        "value",
        "24",
    ),
    "ren6-cnt-03": (
        "How many 2-digit codes use digits 0-9 with no repeated digits?",
        "value",
        "90",
    ),
    "ren6-cnt-04": (
        "Among 6 people, how many handshakes if each pair shakes once?",
        "value",
        "15",
    ),
    "ren6-cnt-05": (
        "How many binary strings of length 5 exist?",
        "value",
        "32",
    ),
    "ren6-cnt-06": (
        "A committee of 3 is chosen from 8 people. How many committees are possible?",
        "value",
        "56",
    ),
    "ren6-cnt-07": (
        "How many distinct arrangements does the word PEPPER have?",
        "value",
        "60",
    ),
    "ren6-cnt-08": (
        "How many diagonals does a convex hexagon have?",
        "value",
        "9",
    ),
    "ren6-cnt-09": (
        "In how many ways can 2 distinct prizes be awarded to 7 people with at most one prize each?",
        "value",
        "42",
    ),
    "ren6-cnt-10": (
        "Compute P(6, 3).",
        "value",
        "120",
    ),
    "ren6-seq-01": (
        "An arithmetic sequence starts 5, 8, 11, .... What is the 10th term?",
        "value",
        "32",
    ),
    "ren6-seq-02": (
        "A geometric sequence starts 2, 6, 18, .... What is the 6th term?",
        "value",
        "486",
    ),
    "ren6-seq-03": (
        "Compute the sum of the first 25 positive integers.",
        "value",
        "325",
    ),
    "ren6-seq-04": (
        "Compute the sum of the first 8 terms of 3, 7, 11, 15, ....",
        "value",
        "136",
    ),
    "ren6-seq-05": (
        "Compute the sum of the finite geometric series 1 + 2 + 4 + 8 + 16.",
        "value",
        "31",
    ),
    "ren6-seq-06": (
        "What is the 10th Fibonacci number if F(1)=1 and F(2)=1?",
        "value",
        "55",
    ),
    "ren6-seq-07": (
        "A sequence obeys a_n = 3 a_(n-1) + 1 with a_1 = 1. What is a_4?",
        "value",
        "40",
    ),
    "ren6-seq-08": (
        "Compute the infinite geometric sum 1 + 1/4 + 1/16 + 1/64 + ....",
        "value",
        "4/3",
    ),
    "ren6-seq-09": (
        "What is the 12th triangular number?",
        "value",
        "78",
    ),
    "ren6-seq-10": (
        "Compute 1^2 + 2^2 + ... + 6^2.",
        "value",
        "91",
    ),
    "ren6-numc-01": (
        "A recurrence is x_(n+1) = 2 x_n + 3 with x_0 = 1. What is x_4?",
        "value",
        "61",
    ),
    "ren6-numc-02": (
        "Approximate integral of x from 0 to 4 with one trapezoid using endpoints. Exact trapezoid value?",
        "value",
        "8",
    ),
    "ren6-numc-03": (
        "One Babylonian square-root step for 13 starting at 4: (4 + 13/4)/2. Exact value?",
        "value",
        "29/8",
    ),
    "ren6-numc-04": (
        "Convert binary 101011 to decimal.",
        "value",
        "43",
    ),
    "ren6-numc-05": (
        "Convert decimal 23 to base 5.",
        "value",
        "43",
    ),
    "ren6-numc-06": (
        "Compute the Hamming distance between 1100101 and 1010111.",
        "value",
        "3",
    ),
    "ren6-numc-07": (
        "Compute (12 + 19 + 8 + 6) mod 9.",
        "value",
        "0",
    ),
    "ren6-numc-08": (
        "Compute the weighted average of 4 with weight 3 and 10 with weight 2.",
        "value",
        "32/5",
    ),
    "ren6-numc-09": (
        "Compute the continued fraction 2 + 1/(3 + 1/4) exactly.",
        "value",
        "30/13",
    ),
    "ren6-numc-10": (
        "Compute 3^5.",
        "value",
        "243",
    ),
}

expected_ids = [
    "capabilities",
    "math_school",
    "self_build",
    "construction",
    "chat_communication",
]
expected_titles = {
    "capabilities": "Engel Capabilities",
    "math_school": "Math School",
    "self_build": "Self-Build",
    "construction": "Construction Coordination",
    "chat_communication": "Chat Communication",
}

check(
    "canonical_picker_is_exactly_five_stable_choices",
    [item.get("id") for item in assets.ALL_CURRICULA] == expected_ids
    and len(assets.ALL_CURRICULA) == 5
    and {
        item.get("id"): item.get("title")
        for item in assets.ALL_CURRICULA
    }
    == expected_titles,
    [
        {
            "id": item.get("id"),
            "title": item.get("title"),
            "material_source": item.get("material_source"),
            "generated_source_id": item.get("generated_source_id"),
        }
        for item in assets.ALL_CURRICULA
    ],
)
source_contract = {
    str(item.get("id")): {
        "material_source": item.get("material_source"),
        "generated_source_id": item.get("generated_source_id"),
    }
    for item in assets.ALL_CURRICULA
}
check(
    "generated_material_overlays_canonical_construction_and_chat_slots",
    source_contract.get("construction", {}).get("material_source")
    == "adopted_generated"
    and bool(source_contract.get("construction", {}).get("generated_source_id"))
    and source_contract.get("chat_communication", {}).get("material_source")
    == "adopted_generated"
    and bool(
        source_contract.get("chat_communication", {}).get(
            "generated_source_id"
        )
    )
    and all(
        source_contract.get(curriculum_id, {}).get("material_source")
        == "canonical_handwritten"
        and not source_contract.get(curriculum_id, {}).get(
            "generated_source_id"
        )
        for curriculum_id in ("capabilities", "math_school", "self_build")
    ),
    source_contract,
)
check(
    "non_aec_renewal_structure_is_valid",
    not renewal.validate_renewal_curricula(),
    renewal.validate_renewal_curricula(),
)
check(
    "construction_renewal_structure_is_valid",
    not construction.validate_renewal_cards(),
    construction.validate_renewal_cards(),
)

history = load_prompt_history(DEFAULT_PACKS_DIR)
check(
    "immutable_prompt_history_is_readable",
    history.get("ok") is True,
    {
        "packs": history.get("history_pack_count"),
        "reservations": history.get("history_valid_reservation_count"),
        "unique_prompts": history.get("history_unique_prompt_count"),
        "problems": history.get("problems"),
    },
)
historical_hashes = set(history.get("history_prompt_hashes") or [])
all_renewal_hashes: set[str] = set()
all_math_problem_ids: list[str] = []

for curriculum in assets.ALL_CURRICULA:
    curriculum_id = str(curriculum["id"])
    cards = curriculum["cards"]
    template = assets.build_template(
        cards=cards,
        version=curriculum["version"],
        template_id=f"verify_{curriculum_id}",
        discipline=curriculum["discipline"],
    )
    cycles = template.get("cycle_prompt_sets") or []
    prompts = [
        str(prompt)
        for cycle in cycles
        for prompt in (cycle.get("prompts") or [])
    ]
    prompt_hashes = [canonical_base_prompt_sha256(prompt) for prompt in prompts]
    replayed = sorted(set(prompt_hashes).intersection(historical_hashes))
    cross_curriculum_duplicates = sorted(
        set(prompt_hashes).intersection(all_renewal_hashes)
    )
    preflight = evaluate_scheduled_prompt_novelty(prompts, DEFAULT_PACKS_DIR)
    check(
        f"{curriculum_id}_is_eight_distinct_ten_prompt_cycles",
        len(cards) == 8
        and len(cycles) == 8
        and all(len(cycle.get("prompts") or []) == 10 for cycle in cycles)
        and len(prompts) == 80
        and len(set(prompt_hashes)) == 80,
        {
            "cards": len(cards),
            "cycles": len(cycles),
            "prompts": len(prompts),
            "unique": len(set(prompt_hashes)),
        },
    )
    check(
        f"{curriculum_id}_is_hash_novel_against_current_history",
        not replayed
        and not cross_curriculum_duplicates
        and preflight.get("ok") is True
        and preflight.get("decision") == "PASS"
        and preflight.get("novel_prompt_count") == 80,
        {
            "replayed": len(replayed),
            "cross_curriculum_duplicates": len(cross_curriculum_duplicates),
            "decision": preflight.get("decision"),
            "novel": preflight.get("novel_prompt_count"),
        },
    )
    check(
        f"{curriculum_id}_template_binds_renewal_material",
        (
            curriculum.get("material_source") == "adopted_generated"
            and bool(curriculum.get("generated_source_id"))
            and "generated"
            in str(template.get("material_version") or "").casefold()
        )
        or (
            curriculum.get("material_source") == "canonical_handwritten"
            and (
                "renewal" in str(template.get("material_version") or "")
                or (
                    curriculum_id == "math_school"
                    and "declared"
                    in str(template.get("material_version") or "")
                )
            )
        ),
        {
            "material_version": template.get("material_version"),
            "material_source": curriculum.get("material_source"),
            "generated_source_id": curriculum.get("generated_source_id"),
        },
    )
    all_renewal_hashes.update(prompt_hashes)

    for card_index, card in enumerate(cards, start=1):
        artifact_paths = card.get("artifacts") or []
        artifact_ok = bool(artifact_paths)
        for raw_path in artifact_paths:
            relative = Path(str(raw_path or ""))
            candidate = ROOT / relative
            try:
                resolved = candidate.resolve(strict=True)
            except OSError:
                artifact_ok = False
                continue
            artifact_ok = artifact_ok and (
                not relative.is_absolute()
                and not relative.drive
                and ".." not in relative.parts
                and ROOT.resolve() in resolved.parents
                and candidate.is_file()
                and not candidate.is_symlink()
            )
        check(
            f"{curriculum_id}_card_{card_index}_artifacts_exist",
            artifact_ok,
            artifact_paths,
        )

        # AEC material proves grounding through corpus evidence anchors that must
        # resolve to a real local excerpt before delivery, not through repository
        # artifact byte records. Key that exemption on the DISCIPLINE rather than the
        # literal id "construction", so generated AEC curricula are judged by the same
        # rule as the hand-written one instead of an engineering contract they were
        # never meant to satisfy.
        if str(curriculum.get("discipline") or "") != "aec":
            records = card.get("_grounding_artifact_records") or []
            record_ok = len(records) == len(artifact_paths)
            for record, raw_path in zip(records, artifact_paths):
                path = ROOT / str(raw_path)
                record_ok = record_ok and (
                    record.get("path") == Path(str(raw_path)).as_posix()
                    and record.get("bytes") == path.stat().st_size
                    and record.get("sha256") == sha256_file(path)
                )
            check(
                f"{curriculum_id}_card_{card_index}_artifact_bytes_are_bound",
                record_ok,
                records,
            )

    if curriculum["discipline"] == "engineering":
        engineering_prompts_grounded = all(
            all(str(path) in prompt for path in card.get("artifacts") or [])
            for card, cycle in zip(cards, cycles)
            for prompt in cycle.get("prompts") or []
        )
        check(
            f"{curriculum_id}_every_prompt_supplies_its_allowed_artifacts",
            engineering_prompts_grounded,
            "engineering generator appends the exact card artifact allowlist",
        )

    if curriculum_id == "math_school":
        matched = [math_problems.find_problem(prompt) for prompt in prompts]
        all_math_problem_ids = [
            problem.problem_id for problem in matched if problem is not None
        ]
        check(
            "math_all_80_prompts_resolve_to_distinct_decidable_ground_truth",
            len(matched) == 80
            and all(problem is not None and problem.decidable for problem in matched)
            and len(set(all_math_problem_ids)) == 80
            and not any("pose one" in prompt.casefold() for prompt in prompts),
            {
                "prompts": len(prompts),
                "matched": len(all_math_problem_ids),
                "distinct_problem_ids": len(set(all_math_problem_ids)),
            },
        )
        renewal_registry_ids = {
            problem.problem_id
            for problem in math_problems.PROBLEMS
            if problem.problem_id.startswith("ren-")
        }
        oracle_ids = set(INDEPENDENT_MATH_RENEWAL_ORACLE)
        check(
            "math_independent_oracle_covers_exactly_the_80_renewal_problems",
            len(oracle_ids) == 80 and oracle_ids == renewal_registry_ids,
            {
                "oracle": len(oracle_ids),
                "registry": len(renewal_registry_ids),
                "missing_from_oracle": sorted(renewal_registry_ids - oracle_ids),
                "unknown_to_registry": sorted(oracle_ids - renewal_registry_ids),
            },
        )
        drift_failures: list[dict[str, str]] = []
        runtime_failures: list[dict[str, str]] = []
        for problem in matched:
            if problem is None:
                drift_failures.append(
                    {"problem_id": "<unmatched>", "detail": "prompt has no registry problem"}
                )
                continue
            # (2026-09-14) live cards moved to the ren5 generation; a live problem's
            # double-entry row lives in whichever oracle matches its generation.
            oracle = (
                INDEPENDENT_MATH_RENEWAL_ORACLE.get(problem.problem_id)
                or INDEPENDENT_MATH_RENEWAL_V3_ORACLE.get(problem.problem_id)
                or INDEPENDENT_MATH_RENEWAL_V4_ORACLE.get(problem.problem_id)
                or INDEPENDENT_MATH_RENEWAL_V5_ORACLE.get(problem.problem_id)
                or INDEPENDENT_MATH_RENEWAL_V6_ORACLE.get(problem.problem_id)
            )
            if oracle is None:
                drift_failures.append(
                    {
                        "problem_id": problem.problem_id,
                        "detail": "problem is absent from the independent oracle",
                    }
                )
                continue
            expected_question, expected_kind, expected_answer = oracle
            drift: list[str] = []
            if problem.question != expected_question:
                drift.append("question")
            if problem.kind != expected_kind:
                drift.append("kind")
            if problem.answer != expected_answer:
                drift.append("answer")
            if drift:
                drift_failures.append(
                    {
                        "problem_id": problem.problem_id,
                        "detail": f"independent oracle mismatch: {', '.join(drift)}",
                    }
                )
            verdict, detail = math_problems.verify_against_truth(
                f"Result: {expected_answer}\nWork: independent oracle\nCheck: reviewed fixture",
                problem,
            )
            if verdict != math_problems.VERDICT_CORRECT:
                runtime_failures.append(
                    {"problem_id": problem.problem_id, "detail": detail}
                )
        check(
            "math_questions_kinds_and_answers_match_the_independent_oracle",
            not drift_failures,
            drift_failures,
        )
        check(
            "math_independent_oracle_answers_are_accepted_by_the_runtime_grader",
            not runtime_failures,
            runtime_failures,
        )
        first_card = dict(cards[0])
        original_hash = material_card_sha256(first_card)
        first_card["problem_ids"] = list(reversed(first_card["problem_ids"]))
        check(
            "math_material_hash_binds_problem_identity_and_order",
            original_hash != material_card_sha256(first_card),
            {"original": original_hash, "reordered": material_card_sha256(first_card)},
        )

# The operator contract is five stable picker slots, each backed by its current
# non-overlapping 80-prompt material set. Generated material replaces a spent slot;
# it never creates a sixth curriculum identity.
_expected_distinct_prompts = 400
check(
    "every_curriculum_contributes_80_distinct_prompts",
    len(all_renewal_hashes) == _expected_distinct_prompts,
    {
        "expected": _expected_distinct_prompts,
        "curricula": len(assets.ALL_CURRICULA),
        "actual": len(all_renewal_hashes),
        "history_unique": len(historical_hashes),
    },
)
check(
    # (2026-09-25) the live cards now use the ren6 generation; earlier rows
    # stay registered for pack-history reproducibility but are no longer "used".
    "math_registry_contains_exactly_80_used_renewal_problems",
    len(all_math_problem_ids) == 80
    and len(set(all_math_problem_ids)) == 80
    and set(all_math_problem_ids)
    == {
        problem.problem_id
        for problem in math_problems.PROBLEMS
        if problem.problem_id.startswith("ren6-")
    },
    {
        "used": len(set(all_math_problem_ids)),
        "registered": len(
            [
                problem
                for problem in math_problems.PROBLEMS
                if problem.problem_id.startswith("ren6-")
            ]
        ),
    },
)

# --- v3 (ren3) double-entry: registry rows vs the independent v3 oracle ----------
# The ren3 generation is registered ahead of its card wiring, so its double-entry
# check binds registry rows to the v3 oracle directly instead of riding on the
# currently-live card prompts: same drift rule, same runtime grader.
ren3_registry = {
    problem.problem_id: problem
    for problem in math_problems.PROBLEMS
    if problem.problem_id.startswith("ren3-")
}
oracle_v3_ids = set(INDEPENDENT_MATH_RENEWAL_V3_ORACLE)
check(
    "math_v3_independent_oracle_covers_exactly_the_80_ren3_problems",
    len(oracle_v3_ids) == 80 and oracle_v3_ids == set(ren3_registry),
    {
        "oracle": len(oracle_v3_ids),
        "registry": len(ren3_registry),
        "missing_from_oracle": sorted(set(ren3_registry) - oracle_v3_ids),
        "unknown_to_registry": sorted(oracle_v3_ids - set(ren3_registry)),
    },
)
v3_drift_failures: list[dict[str, str]] = []
v3_runtime_failures: list[dict[str, str]] = []
for v3_problem_id in sorted(ren3_registry):
    v3_problem = ren3_registry[v3_problem_id]
    v3_oracle = INDEPENDENT_MATH_RENEWAL_V3_ORACLE.get(v3_problem_id)
    if v3_oracle is None:
        continue  # already reported by the coverage check above
    v3_question, v3_kind, v3_answer = v3_oracle
    v3_drift = []
    if v3_problem.question != v3_question:
        v3_drift.append("question")
    if v3_problem.kind != v3_kind:
        v3_drift.append("kind")
    if v3_problem.answer != v3_answer:
        v3_drift.append("answer")
    if v3_drift:
        v3_drift_failures.append(
            {
                "problem_id": v3_problem_id,
                "detail": f"independent oracle mismatch: {', '.join(v3_drift)}",
            }
        )
    v3_verdict, v3_detail = math_problems.verify_against_truth(
        f"Result: {v3_answer}\nWork: independent oracle\nCheck: reviewed fixture",
        v3_problem,
    )
    if v3_verdict != math_problems.VERDICT_CORRECT:
        v3_runtime_failures.append(
            {"problem_id": v3_problem_id, "detail": v3_detail}
        )
check(
    "math_v3_questions_kinds_and_answers_match_the_independent_oracle",
    not v3_drift_failures,
    v3_drift_failures,
)
check(
    "math_v3_independent_oracle_answers_are_accepted_by_the_runtime_grader",
    not v3_runtime_failures,
    v3_runtime_failures,
)

# --- v4 (ren4) double-entry: registry rows vs the independent v4 oracle ----------
# The ren4 generation is registered ahead of its card wiring, so its double-entry
# check binds registry rows to the v4 oracle directly instead of riding on the
# currently-live card prompts: same drift rule, same runtime grader.
ren4_registry = {
    problem.problem_id: problem
    for problem in math_problems.PROBLEMS
    if problem.problem_id.startswith("ren4-")
}
oracle_v4_ids = set(INDEPENDENT_MATH_RENEWAL_V4_ORACLE)
check(
    "math_v4_independent_oracle_covers_exactly_the_80_ren4_problems",
    len(oracle_v4_ids) == 80 and oracle_v4_ids == set(ren4_registry),
    {
        "oracle": len(oracle_v4_ids),
        "registry": len(ren4_registry),
        "missing_from_oracle": sorted(set(ren4_registry) - oracle_v4_ids),
        "unknown_to_registry": sorted(oracle_v4_ids - set(ren4_registry)),
    },
)
v4_drift_failures: list[dict[str, str]] = []
v4_runtime_failures: list[dict[str, str]] = []
for v4_problem_id in sorted(ren4_registry):
    v4_problem = ren4_registry[v4_problem_id]
    v4_oracle = INDEPENDENT_MATH_RENEWAL_V4_ORACLE.get(v4_problem_id)
    if v4_oracle is None:
        continue  # already reported by the coverage check above
    v4_question, v4_kind, v4_answer = v4_oracle
    v4_drift = []
    if v4_problem.question != v4_question:
        v4_drift.append("question")
    if v4_problem.kind != v4_kind:
        v4_drift.append("kind")
    if v4_problem.answer != v4_answer:
        v4_drift.append("answer")
    if v4_drift:
        v4_drift_failures.append(
            {
                "problem_id": v4_problem_id,
                "detail": f"independent oracle mismatch: {', '.join(v4_drift)}",
            }
        )
    v4_verdict, v4_detail = math_problems.verify_against_truth(
        f"Result: {v4_answer}\nWork: independent oracle\nCheck: reviewed fixture",
        v4_problem,
    )
    if v4_verdict != math_problems.VERDICT_CORRECT:
        v4_runtime_failures.append(
            {"problem_id": v4_problem_id, "detail": v4_detail}
        )
check(
    "math_v4_questions_kinds_and_answers_match_the_independent_oracle",
    not v4_drift_failures,
    v4_drift_failures,
)
check(
    "math_v4_independent_oracle_answers_are_accepted_by_the_runtime_grader",
    not v4_runtime_failures,
    v4_runtime_failures,
)


# --- v5 (ren5) double-entry: registry rows vs the independent v5 oracle ----------
# The ren5 generation is the live card wiring for v5 renewal: same drift rule,
# same runtime grader as prior generations.
ren5_registry = {
    problem.problem_id: problem
    for problem in math_problems.PROBLEMS
    if problem.problem_id.startswith("ren5-")
}
oracle_v5_ids = set(INDEPENDENT_MATH_RENEWAL_V5_ORACLE)
check(
    "math_v5_independent_oracle_covers_exactly_the_80_ren5_problems",
    len(oracle_v5_ids) == 80 and oracle_v5_ids == set(ren5_registry),
    {
        "oracle": len(oracle_v5_ids),
        "registry": len(ren5_registry),
        "missing_from_oracle": sorted(set(ren5_registry) - oracle_v5_ids),
        "unknown_to_registry": sorted(oracle_v5_ids - set(ren5_registry)),
    },
)
v5_drift_failures: list[dict[str, str]] = []
v5_runtime_failures: list[dict[str, str]] = []
for v5_problem_id in sorted(ren5_registry):
    v5_problem = ren5_registry[v5_problem_id]
    v5_oracle = INDEPENDENT_MATH_RENEWAL_V5_ORACLE.get(v5_problem_id)
    if v5_oracle is None:
        continue  # already reported by the coverage check above
    v5_question, v5_kind, v5_answer = v5_oracle
    v5_drift = []
    if v5_problem.question != v5_question:
        v5_drift.append("question")
    if v5_problem.kind != v5_kind:
        v5_drift.append("kind")
    if v5_problem.answer != v5_answer:
        v5_drift.append("answer")
    if v5_drift:
        v5_drift_failures.append(
            {
                "problem_id": v5_problem_id,
                "detail": f"independent oracle mismatch: {', '.join(v5_drift)}",
            }
        )
    v5_verdict, v5_detail = math_problems.verify_against_truth(
        f"Result: {v5_answer}\nWork: independent oracle\nCheck: reviewed fixture",
        v5_problem,
    )
    if v5_verdict != math_problems.VERDICT_CORRECT:
        v5_runtime_failures.append(
            {"problem_id": v5_problem_id, "detail": v5_detail}
        )
check(
    "math_v5_questions_kinds_and_answers_match_the_independent_oracle",
    not v5_drift_failures,
    v5_drift_failures,
)
check(
    "math_v5_independent_oracle_answers_are_accepted_by_the_runtime_grader",
    not v5_runtime_failures,
    v5_runtime_failures,
)


failed = [item for item in checks if item["status"] != "PASS"]
print(
    json.dumps(
        {
            "schema": "engel_curriculum_renewal_verifier_v1",
            "status": "FAIL" if failed else "PASS",
            "passed": len(checks) - len(failed),
            "total": len(checks),
            "failed": [item["name"] for item in failed],
            "checks": checks,
        },
        indent=2,
        sort_keys=True,
    )
)
raise SystemExit(1 if failed else 0)
