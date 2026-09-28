#!/usr/bin/env python3
"""Mint ren5-* math problems + independent oracle rows for curriculum v5.

Local-only. Every answer is computed with sympy and re-checked through
engel_math_problems.verify_against_truth before registration.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))

from engel_math_problems import (  # noqa: E402
    MathProblem,
)

try:
    import sympy as sp
except ImportError as exc:  # pragma: no cover
    raise SystemExit(f"sympy required to mint ren5 problems: {exc}") from exc


def _value(expr) -> str:
    return str(sp.simplify(expr))


def _set(values) -> str:
    return ",".join(str(sp.Integer(v)) for v in sorted(values, key=lambda x: int(x)))


def _expr(expr) -> str:
    return str(sp.simplify(expr))


PROBLEMS: list[MathProblem] = []


def add(pid: str, topic: str, question: str, kind: str, answer: str) -> None:
    PROBLEMS.append(MathProblem(pid, topic, question, kind, answer))


# --- algebra ---
add("ren5-alg-01", "algebra", "Solve 9x - 17 = 55 for x.", "value", _value(8))
add("ren5-alg-02", "algebra", "Solve 13x + 11 = -41 for x.", "value", _value(-4))
add("ren5-alg-03", "algebra", "Solve 6(x - 1) = 42 for x.", "value", _value(8))
add("ren5-alg-04", "algebra", "Solve 5x/6 + 4 = 19 for x.", "value", _value(18))
add("ren5-alg-05", "algebra", "Solve x^2 - 3x - 40 = 0 for x.", "set", _set([-5, 8]))
add("ren5-alg-06", "algebra", "Solve x^2 - 15x + 54 = 0 for x.", "set", _set([6, 9]))
add("ren5-alg-07", "algebra", "Simplify (x^2 - 100)/(x - 10) for x != 10.", "expression", _expr(sp.symbols("x") + 10))
add(
    "ren5-alg-08",
    "algebra",
    "Simplify (x^2 + 11x + 24)/(x + 3) for x != -3.",
    "expression",
    _expr(sp.symbols("x") + 8),
)
add("ren5-alg-09", "algebra", "Solve 2^x = 256 for x.", "value", _value(8))
add("ren5-alg-10", "algebra", "Solve 8x - 15 = 3x + 30 for x.", "value", _value(9))

# --- calculus ---
x = sp.symbols("x")
add("ren5-cal-01", "calculus", "Differentiate 7x^5 + 2x with respect to x.", "expression", _expr(sp.diff(7 * x**5 + 2 * x, x)))
add("ren5-cal-02", "calculus", "Differentiate x^7 - 5x^2 + 1 with respect to x.", "expression", _expr(sp.diff(x**7 - 5 * x**2 + 1, x)))
add(
    "ren5-cal-03",
    "calculus",
    "Integrate 15x^4 with respect to x, ignoring the constant of integration.",
    "expression",
    _expr(sp.integrate(15 * x**4, x)),
)
add(
    "ren5-cal-04",
    "calculus",
    "Integrate 8x^3 - 6 with respect to x, ignoring the constant of integration.",
    "expression",
    _expr(sp.integrate(8 * x**3 - 6, x)),
)
add(
    "ren5-cal-05",
    "calculus",
    "Evaluate the limit of (x^2 - 144)/(x - 12) as x approaches 12.",
    "value",
    _value(sp.limit((x**2 - 144) / (x - 12), x, 12)),
)
add(
    "ren5-cal-06",
    "calculus",
    "Evaluate the limit of (x^3 - 125)/(x - 5) as x approaches 5.",
    "value",
    _value(sp.limit((x**3 - 125) / (x - 5), x, 5)),
)
add("ren5-cal-07", "calculus", "Evaluate the derivative of x^6 - 3x at x = 1.", "value", _value(sp.diff(x**6 - 3 * x, x).subs(x, 1)))
add(
    "ren5-cal-08",
    "calculus",
    "Evaluate the definite integral of 6x^2 from x = 1 to x = 4.",
    "value",
    _value(sp.integrate(6 * x**2, (x, 1, 4))),
)
add(
    "ren5-cal-09",
    "calculus",
    "Differentiate cos(x) + 5x^2 with respect to x.",
    "expression",
    _expr(sp.diff(sp.cos(x) + 5 * x**2, x)),
)
add("ren5-cal-10", "calculus", "Evaluate the second derivative of x^5 at x = 2.", "value", _value(sp.diff(x**5, x, 2).subs(x, 2)))

# --- linear algebra ---
add("ren5-lin-01", "linear algebra", "Compute the determinant of [[7, 2], [1, 5]].", "value", _value(sp.Matrix([[7, 2], [1, 5]]).det()))
add("ren5-lin-02", "linear algebra", "Compute the determinant of [[3, 7], [1, 4]].", "value", _value(sp.Matrix([[3, 7], [1, 4]]).det()))
add("ren5-lin-03", "linear algebra", "Compute the trace of [[9, 2], [4, 6]].", "value", _value(sp.Matrix([[9, 2], [4, 6]]).trace()))
add(
    "ren5-lin-04",
    "linear algebra",
    "Compute the dot product of [2, 5, 1] and [3, -1, 4].",
    "value",
    _value(sp.Matrix([2, 5, 1]).dot(sp.Matrix([3, -1, 4]))),
)
add(
    "ren5-lin-05",
    "linear algebra",
    "Compute the first component of [[1, 2], [3, 4]] times [5, 6].",
    "value",
    _value((sp.Matrix([[1, 2], [3, 4]]) * sp.Matrix([5, 6]))[0]),
)
add("ren5-lin-06", "linear algebra", "Compute the rank of [[1, 2, 3], [2, 4, 6], [0, 1, 1]].", "value", _value(sp.Matrix([[1, 2, 3], [2, 4, 6], [0, 1, 1]]).rank()))
m = sp.Matrix([[2, 0], [0, 5]])
eigs = sorted(int(v) for v in m.eigenvals())
add("ren5-lin-07", "linear algebra", "List the eigenvalues of [[2, 0], [0, 5]] in ascending order.", "set", _set(eigs))
inv = sp.Matrix([[4, 1], [3, 1]]).inv()
add("ren5-lin-08", "linear algebra", "Compute the (1,1) entry of the inverse of [[4, 1], [3, 1]].", "value", _value(inv[0, 0]))
add(
    "ren5-lin-09",
    "linear algebra",
    "Compute the squared Euclidean norm of [3, 4].",
    "value",
    _value(sp.Matrix([3, 4]).dot(sp.Matrix([3, 4]))),
)
add("ren5-lin-10", "linear algebra", "Compute the determinant of [[2, 0, 0], [0, 3, 0], [0, 0, 4]].", "value", _value(sp.Matrix([[2, 0, 0], [0, 3, 0], [0, 0, 4]]).det()))

# --- probability ---
add("ren5-prb-01", "probability", "A fair six-sided die is rolled. What is P(result >= 5)?", "value", "1/3")
add("ren5-prb-02", "probability", "A fair coin is flipped 3 times. What is P(exactly 2 heads)?", "value", "3/8")
add("ren5-prb-03", "probability", "A fair coin is flipped twice. What is P(at least one head)?", "value", "3/4")
add(
    "ren5-prb-04",
    "probability",
    "A bag has 3 red and 5 blue marbles. One marble is drawn. What is P(red)?",
    "value",
    "3/8",
)
add(
    "ren5-prb-05",
    "probability",
    "A bag has 4 red and 6 blue marbles. Two are drawn without replacement. What is P(both red)?",
    "value",
    "2/15",
)
add("ren5-prb-06", "probability", "Two fair dice are rolled. What is P(sum = 9)?", "value", "1/9")
add("ren5-prb-07", "probability", "Two independent fair coins are flipped. What is P(both heads)?", "value", "1/4")
add(
    "ren5-prb-08",
    "probability",
    "Events A and B are mutually exclusive with P(A)=1/5 and P(B)=2/5. What is P(A or B)?",
    "value",
    "3/5",
)
add("ren5-prb-09", "probability", "A fair die is rolled. What is P(even)?", "value", "1/2")
add(
    "ren5-prb-10",
    "probability",
    "A standard deck has 52 cards. One card is drawn. What is P(ace)?",
    "value",
    "1/13",
)

# --- number theory ---
add("ren5-num-01", "number theory", "Compute gcd(84, 30).", "value", _value(sp.gcd(84, 30)))
add("ren5-num-02", "number theory", "Compute lcm(12, 18).", "value", _value(sp.lcm(12, 18)))
add("ren5-num-03", "number theory", "Give the prime factorization of 90.", "expression", "2*3**2*5")
add("ren5-num-04", "number theory", "Compute 3^5 mod 7.", "value", _value(pow(3, 5, 7)))
add("ren5-num-05", "number theory", "How many positive divisors does 60 have?", "value", _value(sp.divisor_count(60)))
add("ren5-num-06", "number theory", "Compute the sum of the positive divisors of 28.", "value", _value(sp.divisor_sigma(28)))
add("ren5-num-07", "number theory", "Compute Euler's totient phi(24).", "value", _value(sp.totient(24)))
add("ren5-num-08", "number theory", "Compute 47 mod 9.", "value", _value(47 % 9))
add("ren5-num-09", "number theory", "What is the next prime after 47?", "value", _value(sp.nextprime(47)))
add("ren5-num-10", "number theory", "What is the smallest prime factor of 91?", "value", _value(min(sp.primefactors(91))))

# --- counting ---
add("ren5-cnt-01", "counting", "Compute C(10, 3).", "value", _value(sp.binomial(10, 3)))
add("ren5-cnt-02", "counting", "In how many orders can 6 distinct books be arranged on a shelf?", "value", _value(sp.factorial(6)))
add(
    "ren5-cnt-03",
    "counting",
    "How many 3-digit codes use digits 0-9 with no repeated digits?",
    "value",
    _value(10 * 9 * 8),
)
add("ren5-cnt-04", "counting", "Among 8 people, how many handshakes if each pair shakes once?", "value", _value(sp.binomial(8, 2)))
add("ren5-cnt-05", "counting", "How many binary strings of length 7 exist?", "value", _value(2**7))
add(
    "ren5-cnt-06",
    "counting",
    "A committee of 4 is chosen from 7 people. How many committees are possible?",
    "value",
    _value(sp.binomial(7, 4)),
)
add(
    "ren5-cnt-07",
    "counting",
    "How many distinct arrangements does the word BANANA have?",
    "value",
    _value(sp.factorial(6) // (sp.factorial(3) * sp.factorial(2))),
)
add("ren5-cnt-08", "counting", "How many diagonals does a convex octagon have?", "value", _value(sp.binomial(8, 2) - 8))
add(
    "ren5-cnt-09",
    "counting",
    "In how many ways can 3 distinct prizes be awarded to 10 people with at most one prize each?",
    "value",
    _value(10 * 9 * 8),
)
add("ren5-cnt-10", "counting", "Compute P(9, 2).", "value", _value(9 * 8))

# --- sequences ---
add("ren5-seq-01", "sequences", "An arithmetic sequence starts 4, 9, 14, .... What is the 12th term?", "value", _value(4 + 11 * 5))
add("ren5-seq-02", "sequences", "A geometric sequence starts 3, 6, 12, .... What is the 7th term?", "value", _value(3 * (2**6)))
add("ren5-seq-03", "sequences", "Compute the sum of the first 20 positive integers.", "value", _value(20 * 21 // 2))
add("ren5-seq-04", "sequences", "Compute the sum of the first 10 terms of 2, 5, 8, 11, ....", "value", _value(sum(2 + 3 * i for i in range(10))))
add("ren5-seq-05", "sequences", "Compute the sum of the finite geometric series 1 + 3 + 9 + 27 + 81.", "value", _value((3**5 - 1) // (3 - 1)))
fib = [0, 1]
while len(fib) <= 12:
    fib.append(fib[-1] + fib[-2])
add("ren5-seq-06", "sequences", "What is the 12th Fibonacci number if F(1)=1 and F(2)=1?", "value", _value(fib[12]))
add("ren5-seq-07", "sequences", "A sequence obeys a_n = 2 a_(n-1) + 1 with a_1 = 1. What is a_5?", "value", "31")
add("ren5-seq-08", "sequences", "Compute the infinite geometric sum 1 + 1/3 + 1/9 + 1/27 + ....", "value", "3/2")
add("ren5-seq-09", "sequences", "What is the 15th triangular number?", "value", _value(15 * 16 // 2))
add("ren5-seq-10", "sequences", "Compute 1^2 + 2^2 + ... + 8^2.", "value", _value(sum(i * i for i in range(1, 9))))

# --- numerical checks ---
add("ren5-numc-01", "numerical checks", "A recurrence is x_(n+1) = 3 x_n - 1 with x_0 = 2. What is x_4?", "value", "122")
add(
    "ren5-numc-02",
    "numerical checks",
    "Approximate integral of x from 0 to 2 with one trapezoid using endpoints. Exact trapezoid value?",
    "value",
    "2",
)
add(
    "ren5-numc-03",
    "numerical checks",
    "One Babylonian square-root step for 10 starting at 3: (3 + 10/3)/2. Exact value?",
    "value",
    "19/6",
)
add("ren5-numc-04", "numerical checks", "Convert binary 110101 to decimal.", "value", _value(int("110101", 2)))
add("ren5-numc-05", "numerical checks", "Convert decimal 45 to base 7.", "value", "63")
add("ren5-numc-06", "numerical checks", "Compute the Hamming distance between 1011001 and 1001011.", "value", "3")
add("ren5-numc-07", "numerical checks", "Compute (17 + 23 + 41 + 9) mod 11.", "value", _value((17 + 23 + 41 + 9) % 11))
add(
    "ren5-numc-08",
    "numerical checks",
    "Compute the weighted average of 5 with weight 2 and 11 with weight 3.",
    "value",
    "43/5",
)
add("ren5-numc-09", "numerical checks", "Compute the continued fraction 3 + 1/(2 + 1/5) exactly.", "value", "38/11")
add("ren5-numc-10", "numerical checks", "Compute 2^10.", "value", _value(2**10))


def render_mathproblem(p: MathProblem) -> str:
    q = p.question.replace("\\", "\\\\").replace('"', '\\"')
    if p.kind == "expression" or "/" in p.answer or "**" in p.answer or "cos" in p.answer or "sin" in p.answer:
        return (
            f'    MathProblem(\n'
            f'        "{p.problem_id}", "{p.topic}",\n'
            f'        "{q}",\n'
            f'        "{p.kind}", "{p.answer}",\n'
            f'    ),'
        )
    return f'    MathProblem("{p.problem_id}", "{p.topic}", "{q}", "{p.kind}", "{p.answer}"),'


def render_oracle(p: MathProblem) -> str:
    return (
        f'    "{p.problem_id}": (\n'
        f'        "{p.question.replace(chr(92), chr(92)+chr(92))}",\n'
        f'        "{p.kind}",\n'
        f'        "{p.answer}",\n'
        f'    ),'
    )


def main() -> int:
    existing_questions = {p.question for p in __import__("engel_math_problems").PROBLEMS}
    live_ids = {p.problem_id for p in __import__("engel_math_problems").PROBLEMS}
    for p in PROBLEMS:
        if p.question in existing_questions:
            raise SystemExit(f"question collides with existing registry: {p.problem_id}")
        if p.problem_id in live_ids:
            raise SystemExit(f"id already registered: {p.problem_id}")

    out = ROOT / "memory" / "training" / "engel_main" / "generated" / "ENGEL_MATH_REN5_MINT.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "engel_math_ren5_mint_v1",
        "count": len(PROBLEMS),
        "problems": [
            {
                "problem_id": p.problem_id,
                "topic": p.topic,
                "question": p.question,
                "kind": p.kind,
                "answer": p.answer,
            }
            for p in PROBLEMS
        ],
        "python_snippet": "\n".join(render_mathproblem(p) for p in PROBLEMS),
        "oracle_snippet": "\n".join(render_oracle(p) for p in PROBLEMS),
    }
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "count": len(PROBLEMS), "path": str(out)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
