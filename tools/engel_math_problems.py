"""Math problems that carry their own ground truth, so admission can be EXACT.

The gap this closes
-------------------
The math curriculum asks the model to invent its own problem ("Solve one concrete algebra
problem you can confirm..."). That makes exact grading impossible: nothing knows what the
intended answer was, so the best a grader can do is check the answer against the problem the
model itself stated. That catches a wrong root, but it cannot catch a model that quietly
swaps the problem for an easier one and solves that correctly.

A problem with declared ground truth removes the ambiguity. The prompt POSES a specific
question, this module knows the answer, and admission becomes a decision instead of an
inference: did the model get it right, yes or no. That is the strongest training signal
available anywhere in this system, and math is the only discipline where it is obtainable.

Honesty about what cannot be decided
------------------------------------
Not every math topic reduces to a checkable value. A proof ("show the sum of two even
numbers is even") has no single correct string, and pretending otherwise would mean either
grading proofs by keyword â€” which rewards imitation â€” or silently dropping the topic.
Neither is acceptable, so such problems are marked `decidable=False` and keep the existing
form-based grading, and every pack row records WHICH grading it received
(`math_truth_verdict`). Downstream training can then weight or separate exactly-verified
rows from form-graded ones instead of treating a proof and an arithmetic answer as equally
proven. Undecidable is a property of the question, not a failure of the grader, and the
receipt should say so plainly.

Scale
-----
Every problem is school-scale on purpose. The CAS answers instantly, and nothing here can
produce the power-tower blowup that hangs sympy â€” the admit gate learned that the hard way.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

SCHEMA = "engel_math_problem_v1"

VERDICT_CORRECT = "correct"
VERDICT_WRONG = "wrong"
VERDICT_UNDECIDABLE = "undecidable"
VERDICT_NO_ANSWER = "no_answer_found"


@dataclass(frozen=True)
class MathProblem:
    problem_id: str
    topic: str
    question: str
    # kind: value | expression | set  -- how `answer` is compared
    kind: str = "value"
    answer: str = ""
    symbol: str = "x"
    decidable: bool = True
    note: str = ""
    aliases: tuple[str, ...] = field(default_factory=tuple)


PROBLEMS: tuple[MathProblem, ...] = (
    # --- algebra ---------------------------------------------------------------
    MathProblem("alg-01", "algebra", "Solve 3x + 4 = 19 for x.", "value", "5"),
    MathProblem("alg-02", "algebra", "Solve x^2 - 5x + 6 = 0 for x.", "set", "2,3"),
    MathProblem("alg-03", "algebra", "Simplify (x^2 - 9)/(x - 3) for x != 3.", "expression", "x + 3"),
    # --- calculus --------------------------------------------------------------
    MathProblem("cal-01", "calculus", "Differentiate 3x^2 + 2x with respect to x.", "expression", "6*x + 2"),
    MathProblem("cal-02", "calculus", "Integrate 6x with respect to x (ignore the constant).", "expression", "3*x**2"),
    MathProblem("cal-03", "calculus", "Evaluate the limit of (x^2 - 1)/(x - 1) as x approaches 1.", "value", "2"),
    # --- linear algebra --------------------------------------------------------
    MathProblem("lin-01", "linear algebra", "Compute the determinant of [[2, 1], [4, 3]].", "value", "2"),
    MathProblem("lin-02", "linear algebra", "Compute the determinant of [[1, 2], [3, 4]].", "value", "-2"),
    # --- number theory ---------------------------------------------------------
    MathProblem("num-01", "number theory", "Give the prime factorization of 84.", "expression", "2**2*3*7"),
    MathProblem("num-02", "number theory", "Compute gcd(84, 36).", "value", "12"),
    MathProblem("num-03", "number theory", "Compute 7^3 mod 5.", "value", "3"),
    # --- counting and probability ---------------------------------------------
    MathProblem("cnt-01", "counting", "How many ways are there to choose 3 items from 7?", "value", "35"),
    MathProblem("cnt-02", "counting", "Compute 5! (five factorial).", "value", "120"),
    MathProblem(
        "prb-01", "probability",
        "A fair coin is flipped 4 times. What is the probability of exactly 2 heads? "
        "Give the answer as a fraction.",
        "value", "3/8",
    ),
    # --- sequences -------------------------------------------------------------
    MathProblem(
        "seq-01", "sequences",
        "Compute the sum of the first 10 positive integers.", "value", "55",
    ),
    # --- 2026-08-09 renewal: algebra -------------------------------------------
    # These eighty questions are the declared ground truth for the eight-hour Math
    # School renewal.  Each question is intentionally small enough for the bounded CAS
    # admit gate and is posed verbatim by the curriculum generator; the model never
    # invents or silently substitutes the problem being graded.
    MathProblem("ren-alg-01", "algebra", "Solve 5x - 7 = 33 for x.", "value", "8"),
    MathProblem("ren-alg-02", "algebra", "Solve 4x + 9 = -11 for x.", "value", "-5"),
    MathProblem("ren-alg-03", "algebra", "Solve 7(x - 2) = 35 for x.", "value", "7"),
    MathProblem("ren-alg-04", "algebra", "Solve 2x/3 + 5 = 13 for x.", "value", "12"),
    MathProblem("ren-alg-05", "algebra", "Solve x^2 - 7x + 12 = 0 for x.", "set", "3,4"),
    MathProblem("ren-alg-06", "algebra", "Solve x^2 + x - 20 = 0 for x.", "set", "-5,4"),
    MathProblem(
        "ren-alg-07", "algebra",
        "Simplify (x^2 - 16)/(x - 4) for x != 4.",
        "expression", "x + 4",
    ),
    MathProblem(
        "ren-alg-08", "algebra",
        "Simplify (x^2 + 5x + 6)/(x + 2) for x != -2.",
        "expression", "x + 3",
    ),
    MathProblem("ren-alg-09", "algebra", "Solve 2^x = 32 for x.", "value", "5"),
    MathProblem("ren-alg-10", "algebra", "Solve 3x + 2 = 2x + 11 for x.", "value", "9"),
    # --- renewal: calculus ------------------------------------------------------
    MathProblem(
        "ren-cal-01", "calculus",
        "Differentiate 5x^3 - 4x with respect to x.",
        "expression", "15*x**2 - 4",
    ),
    MathProblem(
        "ren-cal-02", "calculus",
        "Differentiate x^4 + 3x^2 - 7 with respect to x.",
        "expression", "4*x**3 + 6*x",
    ),
    MathProblem(
        "ren-cal-03", "calculus",
        "Integrate 8x^3 with respect to x, ignoring the constant of integration.",
        "expression", "2*x**4",
    ),
    MathProblem(
        "ren-cal-04", "calculus",
        "Integrate 3x^2 + 2 with respect to x, ignoring the constant of integration.",
        "expression", "x**3 + 2*x",
    ),
    MathProblem(
        "ren-cal-05", "calculus",
        "Evaluate the limit of (x^2 - 9)/(x - 3) as x approaches 3.",
        "value", "6",
    ),
    MathProblem(
        "ren-cal-06", "calculus",
        "Evaluate the limit of (x^3 - 8)/(x - 2) as x approaches 2.",
        "value", "12",
    ),
    MathProblem(
        "ren-cal-07", "calculus",
        "Evaluate the derivative of x^3 - x at x = 2.",
        "value", "11",
    ),
    MathProblem(
        "ren-cal-08", "calculus",
        "Evaluate the definite integral of 3x^2 from x = 0 to x = 2.",
        "value", "8",
    ),
    MathProblem(
        "ren-cal-09", "calculus",
        "Differentiate sin(x) + x^2 with respect to x.",
        "expression", "cos(x) + 2*x",
    ),
    MathProblem(
        "ren-cal-10", "calculus",
        "Integrate cos(x) with respect to x, ignoring the constant of integration.",
        "expression", "sin(x)",
    ),
    # --- renewal: linear algebra ------------------------------------------------
    MathProblem("ren-lin-01", "linear algebra", "Compute the determinant of [[3, 2], [5, 4]].", "value", "2"),
    MathProblem("ren-lin-02", "linear algebra", "Compute the determinant of [[6, 1], [2, 5]].", "value", "28"),
    MathProblem("ren-lin-03", "linear algebra", "Compute the determinant of [[-1, 3], [4, 2]].", "value", "-14"),
    MathProblem("ren-lin-04", "linear algebra", "Compute the determinant of [[7, 0], [0, -3]].", "value", "-21"),
    MathProblem(
        "ren-lin-05", "linear algebra",
        "Compute the determinant of [[1, 2, 0], [0, 3, 4], [0, 0, 5]].",
        "value", "15",
    ),
    MathProblem(
        "ren-lin-06", "linear algebra",
        "Compute the determinant of [[2, 0, 1], [3, 1, 0], [0, 4, 1]].",
        "value", "14",
    ),
    MathProblem("ren-lin-07", "linear algebra", "Compute the determinant of [[4, 2], [1, 3]].", "value", "10"),
    MathProblem("ren-lin-08", "linear algebra", "Compute the determinant of [[5, -2], [-3, 1]].", "value", "-1"),
    MathProblem(
        "ren-lin-09", "linear algebra",
        "Compute the determinant of [[1, 0, 2], [0, 2, 0], [3, 0, 1]].",
        "value", "-10",
    ),
    MathProblem(
        "ren-lin-10", "linear algebra",
        "Compute the determinant of [[-2, 1, 0], [0, 4, 2], [0, 0, 3]].",
        "value", "-24",
    ),
    # --- renewal: probability ---------------------------------------------------
    MathProblem(
        "ren-prb-01", "probability",
        "A fair coin is flipped 5 times. What is the probability of exactly 3 heads? Give the answer as a fraction.",
        "value", "5/16",
    ),
    MathProblem(
        "ren-prb-02", "probability",
        "Two fair six-sided dice are rolled. What is the probability that their sum is 7? Give the answer as a fraction.",
        "value", "1/6",
    ),
    MathProblem(
        "ren-prb-03", "probability",
        "Two fair six-sided dice are rolled. What is the probability of at least one 6? Give the answer as a fraction.",
        "value", "11/36",
    ),
    MathProblem(
        "ren-prb-04", "probability",
        "One card is drawn from a standard 52-card deck. What is the probability it is an ace? Give the answer as a fraction.",
        "value", "1/13",
    ),
    MathProblem(
        "ren-prb-05", "probability",
        "One card is drawn from a standard 52-card deck. What is the probability it is red? Give the answer as a fraction.",
        "value", "1/2",
    ),
    MathProblem(
        "ren-prb-06", "probability",
        "A bag has 5 red and 3 blue tokens. Two tokens are drawn without replacement. What is the probability both are red? Give the answer as a fraction.",
        "value", "5/14",
    ),
    MathProblem(
        "ren-prb-07", "probability",
        "A fair coin is flipped 6 times. What is the probability of exactly 2 heads? Give the answer as a fraction.",
        "value", "15/64",
    ),
    MathProblem(
        "ren-prb-08", "probability",
        "A fair six-sided die is rolled once. What is the probability of a result greater than 4? Give the answer as a fraction.",
        "value", "1/3",
    ),
    MathProblem(
        "ren-prb-09", "probability",
        "A fair coin and a fair six-sided die are used once. What is the probability of heads or a 6? Give the answer as a fraction.",
        "value", "7/12",
    ),
    MathProblem(
        "ren-prb-10", "probability",
        "A bag has 4 green and 6 black tokens. A token is drawn, replaced, and drawn again. What is the probability both draws are green? Give the answer as a fraction.",
        "value", "4/25",
    ),
    # --- renewal: number theory -------------------------------------------------
    MathProblem("ren-num-01", "number theory", "Compute gcd(126, 210).", "value", "42"),
    MathProblem("ren-num-02", "number theory", "Compute lcm(18, 24).", "value", "72"),
    MathProblem("ren-num-03", "number theory", "Compute 11^4 mod 7.", "value", "4"),
    MathProblem("ren-num-04", "number theory", "Compute 2^10 mod 7.", "value", "2"),
    MathProblem("ren-num-05", "number theory", "Compute gcd(391, 299).", "value", "23"),
    MathProblem("ren-num-06", "number theory", "Compute Euler's totient phi(20).", "value", "8"),
    MathProblem("ren-num-07", "number theory", "Compute the remainder when 12345 is divided by 97.", "value", "26"),
    MathProblem("ren-num-08", "number theory", "Find the least positive inverse of 3 modulo 11.", "value", "4"),
    MathProblem("ren-num-09", "number theory", "Give the prime factorization of 180.", "expression", "2**2*3**2*5"),
    MathProblem(
        "ren-num-10", "number theory",
        "Find the least positive integer x such that x is congruent to 2 modulo 5 and congruent to 3 modulo 7.",
        "value", "17",
    ),
    # --- renewal: combinatorics -------------------------------------------------
    MathProblem("ren-cnt-01", "counting", "How many ways are there to choose 4 items from 9?", "value", "126"),
    MathProblem("ren-cnt-02", "counting", "How many permutations are there of 6 distinct objects?", "value", "720"),
    MathProblem("ren-cnt-03", "counting", "How many ordered selections of 3 objects can be made from 5 distinct objects without replacement?", "value", "60"),
    MathProblem("ren-cnt-04", "counting", "How many binary strings of length 8 contain exactly 3 ones?", "value", "56"),
    MathProblem("ren-cnt-05", "counting", "How many ways can 4 identical balls be placed into 3 distinct boxes when empty boxes are allowed?", "value", "15"),
    MathProblem("ren-cnt-06", "counting", "How many shortest grid paths use exactly 4 right steps and 3 up steps?", "value", "35"),
    MathProblem("ren-cnt-07", "counting", "How many committees contain 2 people chosen from a group of 5 and 1 person chosen from a separate group of 4?", "value", "40"),
    MathProblem("ren-cnt-08", "counting", "How many derangements are there of 4 distinct objects?", "value", "9"),
    MathProblem("ren-cnt-09", "counting", "How many strings of length 4 can be formed from 3 symbols when repetition is allowed?", "value", "81"),
    MathProblem("ren-cnt-10", "counting", "How many circular arrangements are there of 6 distinct people, counting rotations as the same?", "value", "120"),
    # --- renewal: sequences and series -----------------------------------------
    MathProblem("ren-seq-01", "sequences", "An arithmetic sequence starts at 5 with common difference 3. Compute its 7th term.", "value", "23"),
    MathProblem("ren-seq-02", "sequences", "Compute the sum of the first 20 positive odd integers.", "value", "400"),
    MathProblem("ren-seq-03", "sequences", "A geometric sequence starts at 3 with common ratio 2. Compute its 8th term.", "value", "384"),
    MathProblem("ren-seq-04", "sequences", "Compute the sum of the first 8 terms of the geometric sequence with first term 1 and common ratio 2.", "value", "255"),
    MathProblem("ren-seq-05", "sequences", "For the Fibonacci sequence with F1 = 1 and F2 = 1, compute F12.", "value", "144"),
    MathProblem("ren-seq-06", "sequences", "Compute the sum of the first 15 positive integers.", "value", "120"),
    MathProblem("ren-seq-07", "sequences", "Compute the sum of the first 12 terms of the arithmetic sequence with first term 4 and common difference 5.", "value", "378"),
    MathProblem("ren-seq-08", "sequences", "Compute the sum of the first 6 terms of the geometric sequence with first term 2 and common ratio 3.", "value", "728"),
    MathProblem("ren-seq-09", "sequences", "For the sequence a_n = n^2 + n, compute a_10.", "value", "110"),
    MathProblem("ren-seq-10", "sequences", "Compute the sum of k(k + 1) for integers k from 1 through 5.", "value", "70"),
    # --- renewal: bounded numerical and discrete checks -------------------------
    MathProblem("ren-numc-01", "numerical checks", "Evaluate 2x^3 - 5x + 1 at x = 3.", "value", "40"),
    MathProblem("ren-numc-02", "numerical checks", "Compute the midpoint of 7/3 and 11/3.", "value", "3"),
    MathProblem("ren-numc-03", "numerical checks", "Compute the absolute error of 22/7 as an approximation to 3.14. Give the exact fraction.", "value", "1/350"),
    MathProblem("ren-numc-04", "numerical checks", "Let a_0 = 2 and a_(n+1) = 3a_n - 1. Compute a_4.", "value", "122"),
    MathProblem("ren-numc-05", "numerical checks", "Use one trapezoidal-rule interval on [0, 2] to approximate the integral of x^2. What value does the rule produce?", "value", "4"),
    MathProblem("ren-numc-06", "numerical checks", "Starting from x_0 = 3/2, perform one Babylonian iteration x_1 = (x_0 + 2/x_0)/2 for sqrt(2). Give the exact fraction.", "value", "17/12"),
    MathProblem("ren-numc-07", "numerical checks", "Convert the binary number 110101 to decimal.", "value", "53"),
    MathProblem("ren-numc-08", "numerical checks", "Compute the Hamming distance between 101101 and 111001.", "value", "2"),
    MathProblem("ren-numc-09", "numerical checks", "Compute (17 + 23 + 41 + 9) mod 16.", "value", "10"),
    MathProblem("ren-numc-10", "numerical checks", "Compute the weighted average of 3 with weight 2 and 7 with weight 5.", "value", "41/7"),
    # --- 2026-08-14 v3 renewal (ren3-*): generated with sympy-computed answers --
    # Second-generation renewal set minted 2026-08-14.  Every answer below was
    # computed by sympy at mint time and proven through the production grading
    # path (find_problem + grade_reply) before registration; none was derived by
    # hand.  Fresh parameters throughout, and no question is a substring of any
    # other registered question, so find_problem's substring matching stays
    # unambiguous in both directions.
    # --- v3 renewal: algebra -------------------------------------------------------------
    MathProblem("ren3-alg-01", "algebra", "Solve 6x - 11 = 31 for x.", "value", "7"),
    MathProblem("ren3-alg-02", "algebra", "Solve 9x + 14 = -22 for x.", "value", "-4"),
    MathProblem("ren3-alg-03", "algebra", "Solve 5(x + 2) = 45 for x.", "value", "7"),
    MathProblem("ren3-alg-04", "algebra", "Solve 5x/2 + 3 = 18 for x.", "value", "6"),
    MathProblem("ren3-alg-05", "algebra", "Solve x^2 - 4x - 12 = 0 for x.", "set", "-2,6"),
    MathProblem("ren3-alg-06", "algebra", "Solve x^2 - 14x + 45 = 0 for x.", "set", "5,9"),
    MathProblem("ren3-alg-07", "algebra", "Simplify (x^2 - 25)/(x + 5) for x != -5.", "expression", "x - 5"),
    MathProblem(
        "ren3-alg-08", "algebra",
        "Simplify (x^2 + 7x + 10)/(x + 5) for x != -5.",
        "expression", "x + 2",
    ),
    MathProblem("ren3-alg-09", "algebra", "Solve 3^x = 81 for x.", "value", "4"),
    MathProblem("ren3-alg-10", "algebra", "Solve 5x - 6 = 3x + 10 for x.", "value", "8"),
    # --- v3 renewal: calculus ------------------------------------------------------------
    MathProblem(
        "ren3-cal-01", "calculus",
        "Differentiate 4x^3 + 7x with respect to x.",
        "expression", "12*x**2 + 7",
    ),
    MathProblem(
        "ren3-cal-02", "calculus",
        "Differentiate x^5 - 2x^2 + 6 with respect to x.",
        "expression", "5*x**4 - 4*x",
    ),
    MathProblem(
        "ren3-cal-03", "calculus",
        "Integrate 10x^4 with respect to x, ignoring the constant of integration.",
        "expression", "2*x**5",
    ),
    MathProblem(
        "ren3-cal-04", "calculus",
        "Integrate 6x^2 - 5 with respect to x, ignoring the constant of integration.",
        "expression", "2*x**3 - 5*x",
    ),
    MathProblem(
        "ren3-cal-05", "calculus",
        "Evaluate the limit of (x^2 - 49)/(x - 7) as x approaches 7.",
        "value", "14",
    ),
    MathProblem(
        "ren3-cal-06", "calculus",
        "Evaluate the limit of (x^3 - 27)/(x - 3) as x approaches 3.",
        "value", "27",
    ),
    MathProblem("ren3-cal-07", "calculus", "Evaluate the derivative of x^4 - 3x at x = 1.", "value", "1"),
    MathProblem(
        "ren3-cal-08", "calculus",
        "Evaluate the definite integral of 4x^3 from x = 0 to x = 3.",
        "value", "81",
    ),
    MathProblem(
        "ren3-cal-09", "calculus",
        "Differentiate cos(x) + 3x^2 with respect to x.",
        "expression", "6*x - sin(x)",
    ),
    MathProblem(
        "ren3-cal-10", "calculus",
        "Integrate sin(x) with respect to x, ignoring the constant of integration.",
        "expression", "-cos(x)",
    ),
    # --- v3 renewal: linear algebra ------------------------------------------------------
    MathProblem(
        "ren3-lin-01", "linear algebra",
        "Compute the determinant of [[4, 3], [2, 5]].",
        "value", "14",
    ),
    MathProblem(
        "ren3-lin-02", "linear algebra",
        "Compute the determinant of [[7, 2], [3, 4]].",
        "value", "22",
    ),
    MathProblem(
        "ren3-lin-03", "linear algebra",
        "Compute the determinant of [[-3, 5], [2, 6]].",
        "value", "-28",
    ),
    MathProblem(
        "ren3-lin-04", "linear algebra",
        "Compute the determinant of [[8, 0], [0, -2]].",
        "value", "-16",
    ),
    MathProblem(
        "ren3-lin-05", "linear algebra",
        "Compute the determinant of [[2, 1, 0], [0, 4, 3], [0, 0, 6]].",
        "value", "48",
    ),
    MathProblem(
        "ren3-lin-06", "linear algebra",
        "Compute the determinant of [[1, 0, 2], [2, 3, 0], [0, 1, 4]].",
        "value", "16",
    ),
    MathProblem(
        "ren3-lin-07", "linear algebra",
        "Compute the determinant of [[6, 4], [3, 5]].",
        "value", "18",
    ),
    MathProblem(
        "ren3-lin-08", "linear algebra",
        "Compute the determinant of [[9, -2], [-4, 3]].",
        "value", "19",
    ),
    MathProblem(
        "ren3-lin-09", "linear algebra",
        "Compute the determinant of [[3, 0, 1], [0, 5, 0], [2, 0, 4]].",
        "value", "50",
    ),
    MathProblem(
        "ren3-lin-10", "linear algebra",
        "Compute the determinant of [[-1, 2, 0], [0, 3, 5], [0, 0, 2]].",
        "value", "-6",
    ),
    # --- v3 renewal: probability ---------------------------------------------------------
    MathProblem(
        "ren3-prb-01", "probability",
        "A fair coin is flipped 7 times. What is the probability of exactly 4 heads? Give the answer as a fraction.",
        "value", "35/128",
    ),
    MathProblem(
        "ren3-prb-02", "probability",
        "Two fair six-sided dice are rolled. What is the probability that their sum is 9? Give the answer as a fraction.",
        "value", "1/9",
    ),
    MathProblem(
        "ren3-prb-03", "probability",
        "Two fair six-sided dice are rolled. What is the probability both dice show the same number? Give the answer as a fraction.",
        "value", "1/6",
    ),
    MathProblem(
        "ren3-prb-04", "probability",
        "One card is drawn from a standard 52-card deck. What is the probability it is a heart? Give the answer as a fraction.",
        "value", "1/4",
    ),
    MathProblem(
        "ren3-prb-05", "probability",
        "One card is drawn from a standard 52-card deck. What is the probability it is a face card? Give the answer as a fraction.",
        "value", "3/13",
    ),
    MathProblem(
        "ren3-prb-06", "probability",
        "A bag has 6 red and 4 blue tokens. Two tokens are drawn without replacement. What is the probability both are blue? Give the answer as a fraction.",
        "value", "2/15",
    ),
    MathProblem(
        "ren3-prb-07", "probability",
        "A fair coin is flipped 8 times. What is the probability of exactly 1 head? Give the answer as a fraction.",
        "value", "1/32",
    ),
    MathProblem(
        "ren3-prb-08", "probability",
        "A fair six-sided die is rolled once. What is the probability of a result greater than 2? Give the answer as a fraction.",
        "value", "2/3",
    ),
    MathProblem(
        "ren3-prb-09", "probability",
        "A fair coin and a fair six-sided die are used once. What is the probability of tails and an odd number? Give the answer as a fraction.",
        "value", "1/4",
    ),
    MathProblem(
        "ren3-prb-10", "probability",
        "A bag has 3 white and 7 orange tokens. A token is drawn, replaced, and drawn again. What is the probability both draws are white? Give the answer as a fraction.",
        "value", "9/100",
    ),
    # --- v3 renewal: number theory -------------------------------------------------------
    MathProblem("ren3-num-01", "number theory", "Compute gcd(154, 198).", "value", "22"),
    MathProblem("ren3-num-02", "number theory", "Compute lcm(20, 36).", "value", "180"),
    MathProblem("ren3-num-03", "number theory", "Compute 9^5 mod 11.", "value", "1"),
    MathProblem("ren3-num-04", "number theory", "Compute 3^12 mod 10.", "value", "1"),
    MathProblem("ren3-num-05", "number theory", "Compute gcd(437, 323).", "value", "19"),
    MathProblem("ren3-num-06", "number theory", "Compute Euler's totient phi(36).", "value", "12"),
    MathProblem(
        "ren3-num-07", "number theory",
        "Compute the remainder when 54321 is divided by 89.",
        "value", "31",
    ),
    MathProblem(
        "ren3-num-08", "number theory",
        "Find the least positive inverse of 5 modulo 13.",
        "value", "8",
    ),
    MathProblem(
        "ren3-num-09", "number theory",
        "Give the prime factorization of 264.",
        "expression", "2**3*3*11",
    ),
    MathProblem(
        "ren3-num-10", "number theory",
        "Find the least positive integer x such that x is congruent to 4 modulo 6 and congruent to 5 modulo 11.",
        "value", "16",
    ),
    # --- v3 renewal: combinatorics -------------------------------------------------------
    MathProblem(
        "ren3-cnt-01", "counting",
        "How many ways are there to choose 5 items from 11?",
        "value", "462",
    ),
    MathProblem(
        "ren3-cnt-02", "counting",
        "How many permutations are there of 7 distinct objects?",
        "value", "5040",
    ),
    MathProblem(
        "ren3-cnt-03", "counting",
        "How many ordered selections of 4 objects can be made from 6 distinct objects without replacement?",
        "value", "360",
    ),
    MathProblem(
        "ren3-cnt-04", "counting",
        "How many binary strings of length 9 contain exactly 4 ones?",
        "value", "126",
    ),
    MathProblem(
        "ren3-cnt-05", "counting",
        "How many ways can 5 identical balls be placed into 4 distinct boxes when empty boxes are allowed?",
        "value", "56",
    ),
    MathProblem(
        "ren3-cnt-06", "counting",
        "How many shortest grid paths use exactly 5 right steps and 2 up steps?",
        "value", "21",
    ),
    MathProblem(
        "ren3-cnt-07", "counting",
        "How many committees contain 3 people chosen from a group of 6 and 2 people chosen from a separate group of 5?",
        "value", "200",
    ),
    MathProblem(
        "ren3-cnt-08", "counting",
        "How many derangements are there of 5 distinct objects?",
        "value", "44",
    ),
    MathProblem(
        "ren3-cnt-09", "counting",
        "How many strings of length 3 can be formed from 4 symbols when repetition is allowed?",
        "value", "64",
    ),
    MathProblem(
        "ren3-cnt-10", "counting",
        "How many circular arrangements are there of 7 distinct people, counting rotations as the same?",
        "value", "720",
    ),
    # --- v3 renewal: sequences and series ------------------------------------------------
    MathProblem(
        "ren3-seq-01", "sequences",
        "An arithmetic sequence starts at 7 with common difference 4. Compute its 9th term.",
        "value", "39",
    ),
    MathProblem(
        "ren3-seq-02", "sequences",
        "Compute the sum of the first 25 positive odd integers.",
        "value", "625",
    ),
    MathProblem(
        "ren3-seq-03", "sequences",
        "A geometric sequence starts at 2 with common ratio 3. Compute its 6th term.",
        "value", "486",
    ),
    MathProblem(
        "ren3-seq-04", "sequences",
        "Compute the sum of the first 7 terms of the geometric sequence with first term 3 and common ratio 2.",
        "value", "381",
    ),
    MathProblem(
        "ren3-seq-05", "sequences",
        "For the Fibonacci sequence with F1 = 1 and F2 = 1, compute F14.",
        "value", "377",
    ),
    MathProblem(
        "ren3-seq-06", "sequences",
        "Compute the sum of the first 18 positive integers.",
        "value", "171",
    ),
    MathProblem(
        "ren3-seq-07", "sequences",
        "Compute the sum of the first 10 terms of the arithmetic sequence with first term 6 and common difference 7.",
        "value", "375",
    ),
    MathProblem(
        "ren3-seq-08", "sequences",
        "Compute the sum of the first 5 terms of the geometric sequence with first term 4 and common ratio 3.",
        "value", "484",
    ),
    MathProblem("ren3-seq-09", "sequences", "For the sequence a_n = n^2 - n, compute a_12.", "value", "132"),
    MathProblem(
        "ren3-seq-10", "sequences",
        "Compute the sum of k(k + 2) for integers k from 1 through 6.",
        "value", "133",
    ),
    # --- v3 renewal: bounded numerical and discrete checks -------------------------------
    MathProblem("ren3-numc-01", "numerical checks", "Evaluate 3x^3 - 4x + 2 at x = 2.", "value", "18"),
    MathProblem("ren3-numc-02", "numerical checks", "Compute the midpoint of 5/4 and 11/4.", "value", "2"),
    MathProblem(
        "ren3-numc-03", "numerical checks",
        "Compute the absolute error of 355/113 as an approximation to 3.14. Give the exact fraction.",
        "value", "9/5650",
    ),
    MathProblem(
        "ren3-numc-04", "numerical checks",
        "Let a_0 = 3 and a_(n+1) = 2a_n + 1. Compute a_5.",
        "value", "127",
    ),
    MathProblem(
        "ren3-numc-05", "numerical checks",
        "Use one trapezoidal-rule interval on [0, 3] to approximate the integral of x^2. What value does the rule produce?",
        "value", "27/2",
    ),
    MathProblem(
        "ren3-numc-06", "numerical checks",
        "Starting from x_0 = 2, perform one Babylonian iteration x_1 = (x_0 + 3/x_0)/2 for sqrt(3). Give the exact fraction.",
        "value", "7/4",
    ),
    MathProblem(
        "ren3-numc-07", "numerical checks",
        "Convert the binary number 101110 to decimal.",
        "value", "46",
    ),
    MathProblem(
        "ren3-numc-08", "numerical checks",
        "Compute the Hamming distance between 110110 and 101010.",
        "value", "3",
    ),
    MathProblem("ren3-numc-09", "numerical checks", "Compute (13 + 29 + 37 + 8) mod 12.", "value", "3"),
    MathProblem(
        "ren3-numc-10", "numerical checks",
        "Compute the weighted average of 4 with weight 3 and 9 with weight 4.",
        "value", "48/7",
    ),
    # --- 2026-08-16 v4 renewal (ren4-*): generated with sympy-computed answers --
    # Third-generation renewal set minted 2026-08-16. Every answer below was
    # computed by sympy at mint time and proven through the production grading
    # path (find_problem + verify_against_truth) before registration; none was
    # derived by hand. Fresh parameters throughout, and no question is a
    # substring of any other registered question.
    MathProblem("ren4-alg-01", "algebra", "Solve 7x - 19 = 44 for x.", "value", "9"),
    MathProblem("ren4-alg-02", "algebra", "Solve 11x + 8 = -47 for x.", "value", "-5"),
    MathProblem("ren4-alg-03", "algebra", "Solve 4(x - 3) = 36 for x.", "value", "12"),
    MathProblem("ren4-alg-04", "algebra", "Solve 3x/4 + 5 = 14 for x.", "value", "12"),
    MathProblem("ren4-alg-05", "algebra", "Solve x^2 - 2x - 35 = 0 for x.", "set", "-5,7"),
    MathProblem("ren4-alg-06", "algebra", "Solve x^2 - 16x + 63 = 0 for x.", "set", "7,9"),
    MathProblem("ren4-alg-07", "algebra", "Simplify (x^2 - 81)/(x + 9) for x != -9.", "expression", "x - 9"),
    MathProblem(
        "ren4-alg-08", "algebra",
        "Simplify (x^2 + 9x + 18)/(x + 6) for x != -6.",
        "expression", "x + 3",
    ),
    MathProblem("ren4-alg-09", "algebra", "Solve 2^x = 128 for x.", "value", "7"),
    MathProblem("ren4-alg-10", "algebra", "Solve 7x - 9 = 4x + 21 for x.", "value", "10"),
    MathProblem(
        "ren4-cal-01", "calculus",
        "Differentiate 5x^4 + 3x with respect to x.",
        "expression", "20*x**3 + 3",
    ),
    MathProblem(
        "ren4-cal-02", "calculus",
        "Differentiate x^6 - 4x^3 + 2 with respect to x.",
        "expression", "6*x**5 - 12*x**2",
    ),
    MathProblem(
        "ren4-cal-03", "calculus",
        "Integrate 12x^5 with respect to x, ignoring the constant of integration.",
        "expression", "2*x**6",
    ),
    MathProblem(
        "ren4-cal-04", "calculus",
        "Integrate 9x^2 - 7 with respect to x, ignoring the constant of integration.",
        "expression", "3*x**3 - 7*x",
    ),
    MathProblem(
        "ren4-cal-05", "calculus",
        "Evaluate the limit of (x^2 - 121)/(x - 11) as x approaches 11.",
        "value", "22",
    ),
    MathProblem(
        "ren4-cal-06", "calculus",
        "Evaluate the limit of (x^3 - 64)/(x - 4) as x approaches 4.",
        "value", "48",
    ),
    MathProblem("ren4-cal-07", "calculus", "Evaluate the derivative of x^5 - 2x at x = 1.", "value", "3"),
    MathProblem(
        "ren4-cal-08", "calculus",
        "Evaluate the definite integral of 5x^4 from x = 0 to x = 2.",
        "value", "32",
    ),
    MathProblem(
        "ren4-cal-09", "calculus",
        "Differentiate sin(x) + 4x^3 with respect to x.",
        "expression", "12*x**2 + cos(x)",
    ),
    MathProblem("ren4-cal-10", "calculus", "Evaluate the second derivative of x^4 at x = 2.", "value", "48"),
    MathProblem(
        "ren4-lin-01", "linear algebra",
        "Compute the determinant of [[5, 2], [3, 4]].",
        "value", "14",
    ),
    MathProblem(
        "ren4-lin-02", "linear algebra",
        "Compute the determinant of [[7, -2], [5, 6]].",
        "value", "52",
    ),
    MathProblem("ren4-lin-03", "linear algebra", "Compute the trace of [[9, 1], [4, -3]].", "value", "6"),
    MathProblem(
        "ren4-lin-04", "linear algebra",
        "Compute the dot product of the vectors (2, -5, 3) and (4, 1, -2).",
        "value", "-3",
    ),
    MathProblem(
        "ren4-lin-05", "linear algebra",
        "Multiply the matrix [[2, 1], [0, 3]] by the vector (4, -1) and give the first component of the result.",
        "value", "7",
    ),
    MathProblem(
        "ren4-lin-06", "linear algebra",
        "Compute the determinant of [[1, 0, 2], [3, 4, 1], [0, 2, 5]].",
        "value", "30",
    ),
    MathProblem(
        "ren4-lin-07", "linear algebra",
        "Compute the rank of the matrix [[2, 4], [1, 2]].",
        "value", "1",
    ),
    MathProblem("ren4-lin-08", "linear algebra", "Find the eigenvalues of [[6, 0], [0, -2]].", "set", "-2,6"),
    MathProblem(
        "ren4-lin-09", "linear algebra",
        "Compute the entry in row 1, column 1 of the inverse of [[3, 0], [0, 5]].",
        "value", "1/3",
    ),
    MathProblem(
        "ren4-lin-10", "linear algebra",
        "Compute the squared norm of the vector (3, 4, 12).",
        "value", "169",
    ),
    MathProblem(
        "ren4-prb-01", "probability",
        "A fair six-sided die is rolled once. What is the probability the roll is greater than 4?",
        "value", "1/3",
    ),
    MathProblem(
        "ren4-prb-02", "probability",
        "Two fair coins are flipped. What is the probability of exactly one head?",
        "value", "1/2",
    ),
    MathProblem(
        "ren4-prb-03", "probability",
        "A bag holds 5 red and 7 blue marbles. One marble is drawn at random. What is the probability it is red?",
        "value", "5/12",
    ),
    MathProblem(
        "ren4-prb-04", "probability",
        "Two fair six-sided dice are rolled. What is the probability their sum equals 9?",
        "value", "1/9",
    ),
    MathProblem(
        "ren4-prb-05", "probability",
        "Independent events have P(A) = 2/5 and P(B) = 1/4. What is the probability both A and B occur?",
        "value", "1/10",
    ),
    MathProblem(
        "ren4-prb-06", "probability",
        "Three fair coins are flipped. What is the probability of at least one tail?",
        "value", "7/8",
    ),
    MathProblem(
        "ren4-prb-07", "probability",
        "A single card is dealt from a shuffled 52-card deck. What is the probability of dealing a spade?",
        "value", "1/4",
    ),
    MathProblem(
        "ren4-prb-08", "probability",
        "A fair six-sided die is rolled twice. What is the probability both rolls are even?",
        "value", "1/4",
    ),
    MathProblem(
        "ren4-prb-09", "probability",
        "Mutually exclusive events have P(A) = 1/3 and P(B) = 1/2. What is the probability A or B occurs?",
        "value", "5/6",
    ),
    MathProblem(
        "ren4-prb-10", "probability",
        "A bag holds 4 green and 6 yellow marbles. Two are drawn without replacement. What is the probability both are green?",
        "value", "2/15",
    ),
    MathProblem("ren4-num-01", "number theory", "Compute gcd(252, 198).", "value", "18"),
    MathProblem("ren4-num-02", "number theory", "Compute lcm(24, 90).", "value", "360"),
    MathProblem(
        "ren4-num-03", "number theory",
        "Give the prime factorization of 1176.",
        "expression", "2**3*3*7**2",
    ),
    MathProblem("ren4-num-04", "number theory", "Compute 7^100 mod 5.", "value", "1"),
    MathProblem("ren4-num-05", "number theory", "How many positive divisors does 360 have?", "value", "24"),
    MathProblem(
        "ren4-num-06", "number theory",
        "Compute the sum of all positive divisors of 28.",
        "value", "56",
    ),
    MathProblem("ren4-num-07", "number theory", "Compute Euler's totient of 36.", "value", "12"),
    MathProblem(
        "ren4-num-08", "number theory",
        "Compute the remainder when 12345 is divided by 7.",
        "value", "4",
    ),
    MathProblem("ren4-num-09", "number theory", "Find the smallest prime greater than 90.", "value", "97"),
    MathProblem("ren4-num-10", "number theory", "Give the smallest prime factor of 391.", "value", "17"),
    MathProblem("ren4-cnt-01", "counting", "Compute the binomial coefficient 7 choose 3.", "value", "35"),
    MathProblem("ren4-cnt-02", "counting", "Compute the binomial coefficient 9 choose 2.", "value", "36"),
    MathProblem(
        "ren4-cnt-03", "counting",
        "In how many orders can 5 distinct books be arranged on a shelf?",
        "value", "120",
    ),
    MathProblem(
        "ren4-cnt-04", "counting",
        "How many 4-letter codes can be made from 6 distinct letters with no letter repeated?",
        "value", "360",
    ),
    MathProblem(
        "ren4-cnt-05", "counting",
        "If 12 people each shake hands with every other person exactly once, how many handshakes occur?",
        "value", "66",
    ),
    MathProblem("ren4-cnt-06", "counting", "How many binary strings of length 6 exist?", "value", "64"),
    MathProblem(
        "ren4-cnt-07", "counting",
        "A committee of 4 is chosen from 6 men and 5 women with exactly 2 women. How many committees are possible?",
        "value", "150",
    ),
    MathProblem(
        "ren4-cnt-08", "counting",
        "How many distinct arrangements does the word LEVEL have?",
        "value", "30",
    ),
    MathProblem("ren4-cnt-09", "counting", "How many diagonals does a regular decagon have?", "value", "35"),
    MathProblem(
        "ren4-cnt-10", "counting",
        "In how many ways can 3 distinct prizes be given to 8 students if a student may win more than one prize?",
        "value", "512",
    ),
    MathProblem(
        "ren4-seq-01", "sequences",
        "An arithmetic sequence has first term 5 and common difference 6. Compute its 12th term.",
        "value", "71",
    ),
    MathProblem(
        "ren4-seq-02", "sequences",
        "A geometric sequence has first term 3 and ratio 2. Compute its 7th term.",
        "value", "192",
    ),
    MathProblem(
        "ren4-seq-03", "sequences",
        "Compute the sum of the first 40 positive integers.",
        "value", "820",
    ),
    MathProblem(
        "ren4-seq-04", "sequences",
        "Compute the sum of the arithmetic series 4 + 7 + 10 + ... + 61.",
        "value", "650",
    ),
    MathProblem(
        "ren4-seq-05", "sequences",
        "Compute the sum of the geometric series 2 + 6 + 18 + 54 + 162.",
        "value", "242",
    ),
    MathProblem(
        "ren4-seq-06", "sequences",
        "With F(1) = 1 and F(2) = 1, compute the Fibonacci number F(10).",
        "value", "55",
    ),
    MathProblem(
        "ren4-seq-07", "sequences",
        "Let a_0 = 1 and a_(n+1) = 2a_n + 3. Compute a_4.",
        "value", "61",
    ),
    MathProblem(
        "ren4-seq-08", "sequences",
        "Compute the sum of the infinite geometric series 8 + 2 + 1/2 + ...",
        "value", "32/3",
    ),
    MathProblem("ren4-seq-09", "sequences", "Compute the 15th triangular number.", "value", "120"),
    MathProblem(
        "ren4-seq-10", "sequences",
        "Compute the sum of the squares of the integers from 1 to 10.",
        "value", "385",
    ),
    MathProblem(
        "ren4-numc-01", "numerical checks",
        "Let a_0 = 3 and a_(n+1) = 2a_n + 1. Compute a_4.",
        "value", "63",
    ),
    MathProblem(
        "ren4-numc-02", "numerical checks",
        "Apply the trapezoidal rule with a single interval to the integral of x^2 over [0, 3]. What approximation results?",
        "value", "27/2",
    ),
    MathProblem(
        "ren4-numc-03", "numerical checks",
        "Beginning at x_0 = 2, run one Babylonian step x_1 = (x_0 + 3/x_0)/2 toward sqrt(3). Express x_1 as an exact fraction.",
        "value", "7/4",
    ),
    MathProblem(
        "ren4-numc-04", "numerical checks",
        "Convert the binary number 1011011 to decimal.",
        "value", "91",
    ),
    MathProblem(
        "ren4-numc-05", "numerical checks",
        "Compute the Hamming distance between 1100110 and 1010101.",
        "value", "4",
    ),
    MathProblem("ren4-numc-06", "numerical checks", "Compute (31 + 45 + 12 + 8) mod 9.", "value", "6"),
    MathProblem(
        "ren4-numc-07", "numerical checks",
        "Compute the weighted average of 4 with weight 3 and 9 with weight 2.",
        "value", "6",
    ),
    MathProblem(
        "ren4-numc-08", "numerical checks",
        "Convert the base-7 number 452 to decimal.",
        "value", "233",
    ),
    MathProblem(
        "ren4-numc-09", "numerical checks",
        "Evaluate the continued fraction 1 + 1/(2 + 1/2) as an exact fraction.",
        "value", "7/5",
    ),
    MathProblem("ren4-numc-10", "numerical checks", "Compute 3^7.", "value", "2187"),
    # --- 2026-09-14 v5 renewal (ren5-*): sympy-minted local renewal set ---
    MathProblem("ren5-alg-01", "algebra", "Solve 9x - 17 = 55 for x.", "value", "8"),
    MathProblem("ren5-alg-02", "algebra", "Solve 13x + 11 = -41 for x.", "value", "-4"),
    MathProblem("ren5-alg-03", "algebra", "Solve 6(x - 1) = 42 for x.", "value", "8"),
    MathProblem("ren5-alg-04", "algebra", "Solve 5x/6 + 4 = 19 for x.", "value", "18"),
    MathProblem("ren5-alg-05", "algebra", "Solve x^2 - 3x - 40 = 0 for x.", "set", "-5,8"),
    MathProblem("ren5-alg-06", "algebra", "Solve x^2 - 15x + 54 = 0 for x.", "set", "6,9"),
    MathProblem(
        "ren5-alg-07", "algebra",
        "Simplify (x^2 - 100)/(x - 10) for x != 10.",
        "expression", "x + 10",
    ),
    MathProblem(
        "ren5-alg-08", "algebra",
        "Simplify (x^2 + 11x + 24)/(x + 3) for x != -3.",
        "expression", "x + 8",
    ),
    MathProblem("ren5-alg-09", "algebra", "Solve 2^x = 256 for x.", "value", "8"),
    MathProblem("ren5-alg-10", "algebra", "Solve 8x - 15 = 3x + 30 for x.", "value", "9"),
    MathProblem(
        "ren5-cal-01", "calculus",
        "Differentiate 7x^5 + 2x with respect to x.",
        "expression", "35*x**4 + 2",
    ),
    MathProblem(
        "ren5-cal-02", "calculus",
        "Differentiate x^7 - 5x^2 + 1 with respect to x.",
        "expression", "x*(7*x**5 - 10)",
    ),
    MathProblem(
        "ren5-cal-03", "calculus",
        "Integrate 15x^4 with respect to x, ignoring the constant of integration.",
        "expression", "3*x**5",
    ),
    MathProblem(
        "ren5-cal-04", "calculus",
        "Integrate 8x^3 - 6 with respect to x, ignoring the constant of integration.",
        "expression", "2*x*(x**3 - 3)",
    ),
    MathProblem("ren5-cal-05", "calculus", "Evaluate the limit of (x^2 - 144)/(x - 12) as x approaches 12.", "value", "24"),
    MathProblem("ren5-cal-06", "calculus", "Evaluate the limit of (x^3 - 125)/(x - 5) as x approaches 5.", "value", "75"),
    MathProblem("ren5-cal-07", "calculus", "Evaluate the derivative of x^6 - 3x at x = 1.", "value", "3"),
    MathProblem("ren5-cal-08", "calculus", "Evaluate the definite integral of 6x^2 from x = 1 to x = 4.", "value", "126"),
    MathProblem(
        "ren5-cal-09", "calculus",
        "Differentiate cos(x) + 5x^2 with respect to x.",
        "expression", "10*x - sin(x)",
    ),
    MathProblem("ren5-cal-10", "calculus", "Evaluate the second derivative of x^5 at x = 2.", "value", "160"),
    MathProblem("ren5-lin-01", "linear algebra", "Compute the determinant of [[7, 2], [1, 5]].", "value", "33"),
    MathProblem("ren5-lin-02", "linear algebra", "Compute the determinant of [[3, 7], [1, 4]].", "value", "5"),
    MathProblem("ren5-lin-03", "linear algebra", "Compute the trace of [[9, 2], [4, 6]].", "value", "15"),
    MathProblem("ren5-lin-04", "linear algebra", "Compute the dot product of [2, 5, 1] and [3, -1, 4].", "value", "5"),
    MathProblem("ren5-lin-05", "linear algebra", "Compute the first component of [[1, 2], [3, 4]] times [5, 6].", "value", "17"),
    MathProblem("ren5-lin-06", "linear algebra", "Compute the rank of [[1, 2, 3], [2, 4, 6], [0, 1, 1]].", "value", "2"),
    MathProblem("ren5-lin-07", "linear algebra", "List the eigenvalues of [[2, 0], [0, 5]] in ascending order.", "set", "2,5"),
    MathProblem("ren5-lin-08", "linear algebra", "Compute the (1,1) entry of the inverse of [[4, 1], [3, 1]].", "value", "1"),
    MathProblem("ren5-lin-09", "linear algebra", "Compute the squared Euclidean norm of [3, 4].", "value", "25"),
    MathProblem("ren5-lin-10", "linear algebra", "Compute the determinant of [[2, 0, 0], [0, 3, 0], [0, 0, 4]].", "value", "24"),
    MathProblem(
        "ren5-prb-01", "probability",
        "A fair six-sided die is rolled. What is P(result >= 5)?",
        "value", "1/3",
    ),
    MathProblem(
        "ren5-prb-02", "probability",
        "A fair coin is flipped 3 times. What is P(exactly 2 heads)?",
        "value", "3/8",
    ),
    MathProblem(
        "ren5-prb-03", "probability",
        "A fair coin is flipped twice. What is P(at least one head)?",
        "value", "3/4",
    ),
    MathProblem(
        "ren5-prb-04", "probability",
        "A bag has 3 red and 5 blue marbles. One marble is drawn. What is P(red)?",
        "value", "3/8",
    ),
    MathProblem(
        "ren5-prb-05", "probability",
        "A bag has 4 red and 6 blue marbles. Two are drawn without replacement. What is P(both red)?",
        "value", "2/15",
    ),
    MathProblem(
        "ren5-prb-06", "probability",
        "Two fair dice are rolled. What is P(sum = 9)?",
        "value", "1/9",
    ),
    MathProblem(
        "ren5-prb-07", "probability",
        "Two independent fair coins are flipped. What is P(both heads)?",
        "value", "1/4",
    ),
    MathProblem(
        "ren5-prb-08", "probability",
        "Events A and B are mutually exclusive with P(A)=1/5 and P(B)=2/5. What is P(A or B)?",
        "value", "3/5",
    ),
    MathProblem(
        "ren5-prb-09", "probability",
        "A fair die is rolled. What is P(even)?",
        "value", "1/2",
    ),
    MathProblem(
        "ren5-prb-10", "probability",
        "A standard deck has 52 cards. One card is drawn. What is P(ace)?",
        "value", "1/13",
    ),
    MathProblem("ren5-num-01", "number theory", "Compute gcd(84, 30).", "value", "6"),
    MathProblem("ren5-num-02", "number theory", "Compute lcm(12, 18).", "value", "36"),
    MathProblem(
        "ren5-num-03", "number theory",
        "Give the prime factorization of 90.",
        "expression", "2*3**2*5",
    ),
    MathProblem("ren5-num-04", "number theory", "Compute 3^5 mod 7.", "value", "5"),
    MathProblem("ren5-num-05", "number theory", "How many positive divisors does 60 have?", "value", "12"),
    MathProblem("ren5-num-06", "number theory", "Compute the sum of the positive divisors of 28.", "value", "56"),
    MathProblem("ren5-num-07", "number theory", "Compute Euler's totient phi(24).", "value", "8"),
    MathProblem("ren5-num-08", "number theory", "Compute 47 mod 9.", "value", "2"),
    MathProblem("ren5-num-09", "number theory", "What is the next prime after 47?", "value", "53"),
    MathProblem("ren5-num-10", "number theory", "What is the smallest prime factor of 91?", "value", "7"),
    MathProblem("ren5-cnt-01", "counting", "Compute C(10, 3).", "value", "120"),
    MathProblem("ren5-cnt-02", "counting", "In how many orders can 6 distinct books be arranged on a shelf?", "value", "720"),
    MathProblem("ren5-cnt-03", "counting", "How many 3-digit codes use digits 0-9 with no repeated digits?", "value", "720"),
    MathProblem("ren5-cnt-04", "counting", "Among 8 people, how many handshakes if each pair shakes once?", "value", "28"),
    MathProblem("ren5-cnt-05", "counting", "How many binary strings of length 7 exist?", "value", "128"),
    MathProblem("ren5-cnt-06", "counting", "A committee of 4 is chosen from 7 people. How many committees are possible?", "value", "35"),
    MathProblem("ren5-cnt-07", "counting", "How many distinct arrangements does the word BANANA have?", "value", "60"),
    MathProblem("ren5-cnt-08", "counting", "How many diagonals does a convex octagon have?", "value", "20"),
    MathProblem("ren5-cnt-09", "counting", "In how many ways can 3 distinct prizes be awarded to 10 people with at most one prize each?", "value", "720"),
    MathProblem("ren5-cnt-10", "counting", "Compute P(9, 2).", "value", "72"),
    MathProblem("ren5-seq-01", "sequences", "An arithmetic sequence starts 4, 9, 14, .... What is the 12th term?", "value", "59"),
    MathProblem("ren5-seq-02", "sequences", "A geometric sequence starts 3, 6, 12, .... What is the 7th term?", "value", "192"),
    MathProblem("ren5-seq-03", "sequences", "Compute the sum of the first 20 positive integers.", "value", "210"),
    MathProblem("ren5-seq-04", "sequences", "Compute the sum of the first 10 terms of 2, 5, 8, 11, ....", "value", "155"),
    MathProblem("ren5-seq-05", "sequences", "Compute the sum of the finite geometric series 1 + 3 + 9 + 27 + 81.", "value", "121"),
    MathProblem("ren5-seq-06", "sequences", "What is the 12th Fibonacci number if F(1)=1 and F(2)=1?", "value", "144"),
    MathProblem("ren5-seq-07", "sequences", "A sequence obeys a_n = 2 a_(n-1) + 1 with a_1 = 1. What is a_5?", "value", "31"),
    MathProblem(
        "ren5-seq-08", "sequences",
        "Compute the infinite geometric sum 1 + 1/3 + 1/9 + 1/27 + ....",
        "value", "3/2",
    ),
    MathProblem("ren5-seq-09", "sequences", "What is the 15th triangular number?", "value", "120"),
    MathProblem("ren5-seq-10", "sequences", "Compute 1^2 + 2^2 + ... + 8^2.", "value", "204"),
    MathProblem("ren5-numc-01", "numerical checks", "A recurrence is x_(n+1) = 3 x_n - 1 with x_0 = 2. What is x_4?", "value", "122"),
    MathProblem("ren5-numc-02", "numerical checks", "Approximate integral of x from 0 to 2 with one trapezoid using endpoints. Exact trapezoid value?", "value", "2"),
    MathProblem(
        "ren5-numc-03", "numerical checks",
        "One Babylonian square-root step for 10 starting at 3: (3 + 10/3)/2. Exact value?",
        "value", "19/6",
    ),
    MathProblem("ren5-numc-04", "numerical checks", "Convert binary 110101 to decimal.", "value", "53"),
    MathProblem("ren5-numc-05", "numerical checks", "Convert decimal 45 to base 7.", "value", "63"),
    MathProblem("ren5-numc-06", "numerical checks", "Compute the Hamming distance between 1011001 and 1001011.", "value", "3"),
    MathProblem("ren5-numc-07", "numerical checks", "Compute (17 + 23 + 41 + 9) mod 11.", "value", "2"),
    MathProblem(
        "ren5-numc-08", "numerical checks",
        "Compute the weighted average of 5 with weight 2 and 11 with weight 3.",
        "value", "43/5",
    ),
    MathProblem(
        "ren5-numc-09", "numerical checks",
        "Compute the continued fraction 3 + 1/(2 + 1/5) exactly.",
        "value", "38/11",
    ),
    MathProblem("ren5-numc-10", "numerical checks", "Compute 2^10.", "value", "1024"),
    MathProblem("ren6-alg-01", "algebra", "Solve 7x + 4 = 39 for x.", "value", "5"),
    MathProblem("ren6-alg-02", "algebra", "Solve 11x - 8 = 47 for x.", "value", "5"),
    MathProblem("ren6-alg-03", "algebra", "Solve 4(x + 2) = 36 for x.", "value", "7"),
    MathProblem("ren6-alg-04", "algebra", "Solve 3x/4 - 1 = 8 for x.", "value", "12"),
    MathProblem("ren6-alg-05", "algebra", "Solve x^2 - 5x - 14 = 0 for x.", "set", "-2,7"),
    MathProblem("ren6-alg-06", "algebra", "Solve x^2 - 11x + 24 = 0 for x.", "set", "3,8"),
    MathProblem(
        "ren6-alg-07", "algebra",
        "Simplify (x^2 - 49)/(x - 7) for x != 7.",
        "expression", "x + 7",
    ),
    MathProblem(
        "ren6-alg-08", "algebra",
        "Simplify (x^2 + 7x + 10)/(x + 2) for x != -2.",
        "expression", "x + 5",
    ),
    MathProblem("ren6-alg-09", "algebra", "Solve 3^x = 243 for x.", "value", "5"),
    MathProblem("ren6-alg-10", "algebra", "Solve 6x + 9 = 2x + 37 for x.", "value", "7"),
    MathProblem(
        "ren6-cal-01", "calculus",
        "Differentiate 4x^4 - 3x with respect to x.",
        "expression", "16*x**3 - 3",
    ),
    MathProblem(
        "ren6-cal-02", "calculus",
        "Differentiate x^6 + 2x^3 - 9 with respect to x.",
        "expression", "6*x**2*(x**3 + 1)",
    ),
    MathProblem(
        "ren6-cal-03", "calculus",
        "Integrate 12x^3 with respect to x, ignoring the constant of integration.",
        "expression", "3*x**4",
    ),
    MathProblem(
        "ren6-cal-04", "calculus",
        "Integrate 6x^2 + 4 with respect to x, ignoring the constant of integration.",
        "expression", "2*x*(x**2 + 2)",
    ),
    MathProblem(
        "ren6-cal-05", "calculus",
        "Differentiate sin(5x) with respect to x.",
        "expression", "5*cos(5*x)",
    ),
    MathProblem(
        "ren6-cal-06", "calculus",
        "Integrate cos(3x) with respect to x, ignoring the constant of integration.",
        "expression", "sin(3*x)/3",
    ),
    MathProblem("ren6-cal-07", "calculus", "Compute the limit as x approaches 4 of (x^2 - 16)/(x - 4).", "value", "8"),
    MathProblem(
        "ren6-cal-08", "calculus",
        "Find the second derivative of x^4 with respect to x.",
        "expression", "12*x**2",
    ),
    MathProblem("ren6-cal-09", "calculus", "Evaluate the definite integral of 2x from 1 to 3.", "value", "8"),
    MathProblem(
        "ren6-cal-10", "calculus",
        "Differentiate e^(2x) with respect to x.",
        "expression", "2*exp(2*x)",
    ),
    MathProblem("ren6-lin-01", "linear algebra", "Compute the determinant of [[2, 1], [0, 3]].", "value", "6"),
    MathProblem("ren6-lin-02", "linear algebra", "Compute the trace of [[1, 4], [2, 5]].", "value", "6"),
    MathProblem("ren6-lin-03", "linear algebra", "Compute the dot product of (2, -1, 4) and (3, 5, 1).", "value", "5"),
    MathProblem("ren6-lin-04", "linear algebra", "Compute the first component of [[2, 1], [0, 3]] times the column vector (4, 1).", "value", "9"),
    MathProblem("ren6-lin-05", "linear algebra", "What is the rank of [[1, 2, 3], [2, 4, 6]]?", "value", "1"),
    MathProblem("ren6-lin-06", "linear algebra", "List the eigenvalues of [[2, 1], [0, 3]] in increasing order.", "set", "2,3"),
    MathProblem(
        "ren6-lin-07", "linear algebra",
        "What is the (1,1) entry of the inverse of [[2, 1], [0, 3]]?",
        "value", "1/2",
    ),
    MathProblem("ren6-lin-08", "linear algebra", "Compute the squared Euclidean norm of the vector (1, 2, 2).", "value", "9"),
    MathProblem("ren6-lin-09", "linear algebra", "Compute the determinant of [[4, 0], [1, 2]].", "value", "8"),
    MathProblem("ren6-lin-10", "linear algebra", "Compute the trace of [[4, 0], [1, 2]].", "value", "6"),
    MathProblem(
        "ren6-prb-01", "probability",
        "A fair die is rolled once. What is the exact probability of rolling at least 5?",
        "value", "1/3",
    ),
    MathProblem(
        "ren6-prb-02", "probability",
        "A fair coin is flipped twice. What is the exact probability of two heads?",
        "value", "1/4",
    ),
    MathProblem(
        "ren6-prb-03", "probability",
        "A bag has 3 red and 5 blue marbles. One marble is drawn. Exact probability it is red?",
        "value", "3/8",
    ),
    MathProblem(
        "ren6-prb-04", "probability",
        "Two fair dice are rolled. Exact probability the sum is 7?",
        "value", "1/6",
    ),
    MathProblem(
        "ren6-prb-05", "probability",
        "A fair coin is flipped three times. Exact probability of exactly one head?",
        "value", "3/8",
    ),
    MathProblem(
        "ren6-prb-06", "probability",
        "A bag has 4 red and 6 blue marbles. Two are drawn without replacement. Exact probability both are red?",
        "value", "2/15",
    ),
    MathProblem(
        "ren6-prb-07", "probability",
        "Events A and B are independent with P(A)=1/2 and P(B)=1/5. Exact P(A and B)?",
        "value", "1/10",
    ),
    MathProblem(
        "ren6-prb-08", "probability",
        "Mutually exclusive events have P(A)=1/4 and P(B)=1/6. Exact P(A or B)?",
        "value", "5/12",
    ),
    MathProblem(
        "ren6-prb-09", "probability",
        "A fair die is rolled once. Exact probability the result is even?",
        "value", "1/2",
    ),
    MathProblem(
        "ren6-prb-10", "probability",
        "Two fair coins are flipped. Exact probability of at least one head?",
        "value", "3/4",
    ),
    MathProblem("ren6-num-01", "number theory", "Compute gcd(96, 36).", "value", "12"),
    MathProblem("ren6-num-02", "number theory", "Compute lcm(14, 21).", "value", "42"),
    MathProblem(
        "ren6-num-03", "number theory",
        "Give the prime factorization of 126.",
        "expression", "2*3**2*7",
    ),
    MathProblem("ren6-num-04", "number theory", "Compute 2^7 mod 5.", "value", "3"),
    MathProblem("ren6-num-05", "number theory", "How many positive divisors does 36 have?", "value", "9"),
    MathProblem("ren6-num-06", "number theory", "Compute the sum of the positive divisors of 18.", "value", "39"),
    MathProblem("ren6-num-07", "number theory", "Compute Euler's totient phi(15).", "value", "8"),
    MathProblem("ren6-num-08", "number theory", "Compute 58 mod 7.", "value", "2"),
    MathProblem("ren6-num-09", "number theory", "What is the next prime after 29?", "value", "31"),
    MathProblem("ren6-num-10", "number theory", "What is the smallest prime factor of 77?", "value", "7"),
    MathProblem("ren6-cnt-01", "counting", "Compute C(8, 2).", "value", "28"),
    MathProblem("ren6-cnt-02", "counting", "In how many orders can 4 distinct mugs be arranged on a shelf?", "value", "24"),
    MathProblem("ren6-cnt-03", "counting", "How many 2-digit codes use digits 0-9 with no repeated digits?", "value", "90"),
    MathProblem("ren6-cnt-04", "counting", "Among 6 people, how many handshakes if each pair shakes once?", "value", "15"),
    MathProblem("ren6-cnt-05", "counting", "How many binary strings of length 5 exist?", "value", "32"),
    MathProblem("ren6-cnt-06", "counting", "A committee of 3 is chosen from 8 people. How many committees are possible?", "value", "56"),
    MathProblem("ren6-cnt-07", "counting", "How many distinct arrangements does the word PEPPER have?", "value", "60"),
    MathProblem("ren6-cnt-08", "counting", "How many diagonals does a convex hexagon have?", "value", "9"),
    MathProblem("ren6-cnt-09", "counting", "In how many ways can 2 distinct prizes be awarded to 7 people with at most one prize each?", "value", "42"),
    MathProblem("ren6-cnt-10", "counting", "Compute P(6, 3).", "value", "120"),
    MathProblem("ren6-seq-01", "sequences", "An arithmetic sequence starts 5, 8, 11, .... What is the 10th term?", "value", "32"),
    MathProblem("ren6-seq-02", "sequences", "A geometric sequence starts 2, 6, 18, .... What is the 6th term?", "value", "486"),
    MathProblem("ren6-seq-03", "sequences", "Compute the sum of the first 25 positive integers.", "value", "325"),
    MathProblem("ren6-seq-04", "sequences", "Compute the sum of the first 8 terms of 3, 7, 11, 15, ....", "value", "136"),
    MathProblem("ren6-seq-05", "sequences", "Compute the sum of the finite geometric series 1 + 2 + 4 + 8 + 16.", "value", "31"),
    MathProblem("ren6-seq-06", "sequences", "What is the 10th Fibonacci number if F(1)=1 and F(2)=1?", "value", "55"),
    MathProblem("ren6-seq-07", "sequences", "A sequence obeys a_n = 3 a_(n-1) + 1 with a_1 = 1. What is a_4?", "value", "40"),
    MathProblem(
        "ren6-seq-08", "sequences",
        "Compute the infinite geometric sum 1 + 1/4 + 1/16 + 1/64 + ....",
        "value", "4/3",
    ),
    MathProblem("ren6-seq-09", "sequences", "What is the 12th triangular number?", "value", "78"),
    MathProblem("ren6-seq-10", "sequences", "Compute 1^2 + 2^2 + ... + 6^2.", "value", "91"),
    MathProblem("ren6-numc-01", "numerical checks", "A recurrence is x_(n+1) = 2 x_n + 3 with x_0 = 1. What is x_4?", "value", "61"),
    MathProblem("ren6-numc-02", "numerical checks", "Approximate integral of x from 0 to 4 with one trapezoid using endpoints. Exact trapezoid value?", "value", "8"),
    MathProblem(
        "ren6-numc-03", "numerical checks",
        "One Babylonian square-root step for 13 starting at 4: (4 + 13/4)/2. Exact value?",
        "value", "29/8",
    ),
    MathProblem("ren6-numc-04", "numerical checks", "Convert binary 101011 to decimal.", "value", "43"),
    MathProblem("ren6-numc-05", "numerical checks", "Convert decimal 23 to base 5.", "value", "43"),
    MathProblem("ren6-numc-06", "numerical checks", "Compute the Hamming distance between 1100101 and 1010111.", "value", "3"),
    MathProblem("ren6-numc-07", "numerical checks", "Compute (12 + 19 + 8 + 6) mod 9.", "value", "0"),
    MathProblem(
        "ren6-numc-08", "numerical checks",
        "Compute the weighted average of 4 with weight 3 and 10 with weight 2.",
        "value", "32/5",
    ),
    MathProblem(
        "ren6-numc-09", "numerical checks",
        "Compute the continued fraction 2 + 1/(3 + 1/4) exactly.",
        "value", "30/13",
    ),
    MathProblem("ren6-numc-10", "numerical checks", "Compute 3^5.", "value", "243"),
    # --- NOT decidable: proofs and conceptual statements -----------------------
    MathProblem(
        "prf-01", "proofs",
        "Show that the sum of two even integers is even.",
        decidable=False,
        note="a proof has no single correct answer string; graded on form, never counted as exactly verified",
    ),
    MathProblem(
        "prf-02", "proofs",
        "Explain why the square of an odd integer is odd.",
        decidable=False,
        note="conceptual explanation; form-graded only",
    ),
)

BY_ID = {problem.problem_id: problem for problem in PROBLEMS}
DECIDABLE = tuple(p for p in PROBLEMS if p.decidable)
UNDECIDABLE = tuple(p for p in PROBLEMS if not p.decidable)


def find_problem(prompt: str) -> MathProblem | None:
    """Match a delivered prompt back to its problem. Exact-ish, never fuzzy.

    Matching on the QUESTION TEXT keeps this honest: a prompt that merely resembles a known
    problem is not graded against that problem's answer, because grading the wrong answer as
    wrong is the worst outcome available here."""
    text = " ".join(str(prompt or "").split()).casefold()
    if not text:
        return None
    for problem in PROBLEMS:
        needle = " ".join(problem.question.split()).casefold()
        if needle and needle in text:
            return problem
        for alias in problem.aliases:
            if alias.casefold() in text:
                return problem
    return None


_RESULT_LINE = re.compile(r"result\s*:\s*(.+)", re.IGNORECASE)
# The deterministic lane serves one line ("Verified math result: x = 5. Check: residuals
# are exactly 0.") â€” without this cut the Check prose rode along in the stated answer and
# the trailing-number heuristic compared the check's "0" against the truth (2026-08-08:
# a correct live x = 5 graded wrong with "expected 5").
_SECTION_CUT = re.compile(r"[.;,]?\s*\b(?:work|check)\s*:", re.IGNORECASE)


def _clip_at_section(text: str) -> str:
    cut = _SECTION_CUT.search(text)
    return (text[: cut.start()] if cut else text).strip(" .;,")


def _stated_result(reply: str) -> str:
    """The text of the Result line, which is where the answer contract puts the answer."""
    for line in str(reply or "").splitlines():
        match = _RESULT_LINE.match(line.strip())
        if match:
            return _clip_at_section(match.group(1).strip())
    # Some replies put everything on one line.
    match = _RESULT_LINE.search(" ".join(str(reply or "").split()))
    return _clip_at_section(match.group(1).strip()) if match else ""


def _numbers_in(text: str) -> list[str]:
    return re.findall(r"-?\d+(?:\.\d+)?(?:\s*/\s*-?\d+)?", str(text or ""))


_SUPERSCRIPT_DIGITS = {"⁰": "0", "¹": "1", "²": "2", "³": "3", "⁴": "4",
                       "⁵": "5", "⁶": "6", "⁷": "7", "⁸": "8", "⁹": "9"}


def _normalize_notation(text: str) -> str:
    """Fair-parse normalization applied to CANDIDATES before CAS comparison.

    The CAS equivalence check stays the only authority on correctness - this just
    lets honestly-written answers reach it. Live 2026-08-16: '20x**3 + 3' written
    with unicode superscripts, and an answer wrapped in markdown emphasis, were
    graded WRONG purely on notation while being exactly correct. Normalized
    variants are ADDED alongside the raw candidates, never substituted, so a bad
    normalization can only fail to help - it can never flip a wrong answer right."""
    out = str(text or "").strip()
    if out.startswith("**") and out.endswith("**") and len(out) > 4:
        inner = out[2:-2].strip()
        if "**" not in inner:  # pure markdown decoration, not a power expression
            out = inner
    sup_class = "".join(_SUPERSCRIPT_DIGITS)

    def _sup(match: "re.Match[str]") -> str:
        digits = "".join(_SUPERSCRIPT_DIGITS[ch] for ch in match.group(2))
        return match.group(1) + "**" + digits

    out = re.sub("([0-9a-zA-Z)])([" + sup_class + "]+)", _sup, out)
    out = out.replace("^", "**")
    out = re.sub(r"(\d)\s*([a-zA-Z(])", r"\1*\2", out)
    return out


def verify_against_truth(reply: str, problem: MathProblem) -> tuple[str, str]:
    """(verdict, detail). Exact comparison against declared ground truth."""
    if not problem.decidable:
        return VERDICT_UNDECIDABLE, problem.note or "no decidable answer for this problem"

    stated = _stated_result(reply)
    if not stated:
        return VERDICT_NO_ANSWER, "no Result line to compare against the known answer"

    try:
        import engel_math_answer_verifier as mav
        import engel_math_lane as ml

        sympy = ml._sympy()
    except Exception as exc:  # pragma: no cover
        return VERDICT_UNDECIDABLE, f"CAS unavailable: {exc}"

    def _equal(a: str, b: str) -> bool | None:
        left, right = mav._parse(a), mav._parse(b)
        if left is None or right is None:
            return None
        try:
            return mav._is_zero(sympy.simplify(left - right))
        except Exception:
            return None

    if problem.kind == "set":
        wanted = [w.strip() for w in problem.answer.split(",") if w.strip()]
        found = _numbers_in(stated) or _numbers_in(_normalize_notation(stated))
        if len(found) < len(wanted):
            return VERDICT_WRONG, f"expected {len(wanted)} roots ({problem.answer}), saw {found or 'none'}"
        matched = 0
        for want in wanted:
            if any(_equal(got, want) for got in found):
                matched += 1
        return (
            (VERDICT_CORRECT, f"all roots {problem.answer} present")
            if matched == len(wanted)
            else (VERDICT_WRONG, f"expected roots {problem.answer}, got {stated[:60]}")
        )

    # value / expression: compare the stated answer to the truth symbolically.
    candidates = [stated]
    # A Result line often reads "x = 5" or "The determinant is -2"; try the trailing value too.
    tail = _numbers_in(stated)
    if tail:
        candidates.append(tail[-1])
    equals_part = stated.split("=")[-1].strip() if "=" in stated else ""
    if equals_part:
        candidates.append(equals_part)
    # fair-parse variants ride ALONGSIDE the raw candidates (see _normalize_notation)
    for raw in list(candidates):
        normalized = _normalize_notation(raw)
        if normalized != raw:
            candidates.append(normalized)

    for candidate in candidates:
        verdict = _equal(candidate, problem.answer)
        if verdict:
            return VERDICT_CORRECT, f"answer matches {problem.answer}"
    return VERDICT_WRONG, f"expected {problem.answer}, answer line was {stated[:60]!r}"


def grade_reply(reply: str, prompt: str) -> dict[str, Any]:
    """Grade a reply against ground truth when the prompt is a known problem."""
    problem = find_problem(prompt)
    if problem is None:
        return {
            "schema": SCHEMA,
            "matched": False,
            "verdict": VERDICT_UNDECIDABLE,
            "detail": "prompt is not a declared problem; form grading applies",
            "exactly_verified": False,
            "wrong": False,
        }
    verdict, detail = verify_against_truth(reply, problem)
    return {
        "schema": SCHEMA,
        "matched": True,
        "problem_id": problem.problem_id,
        "topic": problem.topic,
        "decidable": problem.decidable,
        "verdict": verdict,
        "detail": detail,
        "exactly_verified": verdict == VERDICT_CORRECT,
        # Only a proven-wrong answer should ever cost a row its admission.
        "wrong": verdict == VERDICT_WRONG,
    }


def main(argv: list[str] | None = None) -> int:
    import argparse
    import json

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="show the problem set")
    parser.add_argument("--reply", default="")
    parser.add_argument("--prompt", default="")
    args = parser.parse_args(argv)

    if args.list:
        print(json.dumps(
            {
                "total": len(PROBLEMS),
                "decidable": len(DECIDABLE),
                "undecidable": len(UNDECIDABLE),
                "problems": [
                    {"id": p.problem_id, "topic": p.topic, "question": p.question,
                     "kind": p.kind, "answer": p.answer, "decidable": p.decidable}
                    for p in PROBLEMS
                ],
            },
            indent=2,
        ))
        return 0
    print(json.dumps(grade_reply(args.reply, args.prompt), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
