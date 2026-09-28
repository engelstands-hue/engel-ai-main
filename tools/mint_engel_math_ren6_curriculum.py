#!/usr/bin/env python3
"""Mint ren6-* math problems + an independent oracle for curriculum v6.

Local-only. Every answer is computed with sympy and checked through
engel_math_problems.verify_against_truth before it is written.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))

from engel_math_problems import MathProblem, verify_against_truth, VERDICT_CORRECT  # noqa: E402

try:
    import sympy as sp
except ImportError as exc:  # pragma: no cover
    raise SystemExit(f"sympy required to mint ren6 problems: {exc}") from exc


def _value(expr) -> str:
    return str(sp.simplify(expr))


def _set(values) -> str:
    return ",".join(str(sp.Integer(v)) for v in sorted(values, key=lambda item: int(item)))


def _expr(expr) -> str:
    return str(sp.simplify(expr))


PROBLEMS: list[MathProblem] = []


def add(pid: str, topic: str, question: str, kind: str, answer: str) -> None:
    PROBLEMS.append(MathProblem(pid, topic, question, kind, answer))


x = sp.symbols("x")

add("ren6-alg-01", "algebra", "Solve 7x + 4 = 39 for x.", "value", _value(5))
add("ren6-alg-02", "algebra", "Solve 11x - 8 = 47 for x.", "value", _value(5))
add("ren6-alg-03", "algebra", "Solve 4(x + 2) = 36 for x.", "value", _value(7))
add("ren6-alg-04", "algebra", "Solve 3x/4 - 1 = 8 for x.", "value", _value(12))
add("ren6-alg-05", "algebra", "Solve x^2 - 5x - 14 = 0 for x.", "set", _set([-2, 7]))
add("ren6-alg-06", "algebra", "Solve x^2 - 11x + 24 = 0 for x.", "set", _set([3, 8]))
add("ren6-alg-07", "algebra", "Simplify (x^2 - 49)/(x - 7) for x != 7.", "expression", _expr(x + 7))
add("ren6-alg-08", "algebra", "Simplify (x^2 + 7x + 10)/(x + 2) for x != -2.", "expression", _expr(x + 5))
add("ren6-alg-09", "algebra", "Solve 3^x = 243 for x.", "value", _value(5))
add("ren6-alg-10", "algebra", "Solve 6x + 9 = 2x + 37 for x.", "value", _value(7))

add("ren6-cal-01", "calculus", "Differentiate 4x^4 - 3x with respect to x.", "expression", _expr(sp.diff(4 * x**4 - 3 * x, x)))
add("ren6-cal-02", "calculus", "Differentiate x^6 + 2x^3 - 9 with respect to x.", "expression", _expr(sp.diff(x**6 + 2 * x**3 - 9, x)))
add("ren6-cal-03", "calculus", "Integrate 12x^3 with respect to x, ignoring the constant of integration.", "expression", _expr(sp.integrate(12 * x**3, x)))
add("ren6-cal-04", "calculus", "Integrate 6x^2 + 4 with respect to x, ignoring the constant of integration.", "expression", _expr(sp.integrate(6 * x**2 + 4, x)))
add("ren6-cal-05", "calculus", "Differentiate sin(5x) with respect to x.", "expression", _expr(sp.diff(sp.sin(5 * x), x)))
add("ren6-cal-06", "calculus", "Integrate cos(3x) with respect to x, ignoring the constant of integration.", "expression", _expr(sp.integrate(sp.cos(3 * x), x)))
add("ren6-cal-07", "calculus", "Compute the limit as x approaches 4 of (x^2 - 16)/(x - 4).", "value", _value(8))
add("ren6-cal-08", "calculus", "Find the second derivative of x^4 with respect to x.", "expression", _expr(sp.diff(x**4, x, 2)))
add("ren6-cal-09", "calculus", "Evaluate the definite integral of 2x from 1 to 3.", "value", _value(sp.integrate(2 * x, (x, 1, 3))))
add("ren6-cal-10", "calculus", "Differentiate e^(2x) with respect to x.", "expression", _expr(sp.diff(sp.exp(2 * x), x)))

A = sp.Matrix([[2, 1], [0, 3]])
B = sp.Matrix([[1, 4], [2, 5]])
add("ren6-lin-01", "linear algebra", "Compute the determinant of [[2, 1], [0, 3]].", "value", _value(A.det()))
add("ren6-lin-02", "linear algebra", "Compute the trace of [[1, 4], [2, 5]].", "value", _value(B.trace()))
add("ren6-lin-03", "linear algebra", "Compute the dot product of (2, -1, 4) and (3, 5, 1).", "value", _value(2 * 3 + (-1) * 5 + 4 * 1))
add("ren6-lin-04", "linear algebra", "Compute the first component of [[2, 1], [0, 3]] times the column vector (4, 1).", "value", _value((A * sp.Matrix([4, 1]))[0]))
add("ren6-lin-05", "linear algebra", "What is the rank of [[1, 2, 3], [2, 4, 6]]?", "value", _value(sp.Matrix([[1, 2, 3], [2, 4, 6]]).rank()))
evals = A.eigenvals()
add(
    "ren6-lin-06",
    "linear algebra",
    "List the eigenvalues of [[2, 1], [0, 3]] in increasing order.",
    "set",
    _set(evals.keys()),
)
inv = A.inv()
add("ren6-lin-07", "linear algebra", "What is the (1,1) entry of the inverse of [[2, 1], [0, 3]]?", "value", _value(inv[0, 0]))
add("ren6-lin-08", "linear algebra", "Compute the squared Euclidean norm of the vector (1, 2, 2).", "value", _value(1 + 4 + 4))
C = sp.Matrix([[4, 0], [1, 2]])
add("ren6-lin-09", "linear algebra", "Compute the determinant of [[4, 0], [1, 2]].", "value", _value(C.det()))
add("ren6-lin-10", "linear algebra", "Compute the trace of [[4, 0], [1, 2]].", "value", _value(C.trace()))

add("ren6-prb-01", "probability", "A fair die is rolled once. What is the exact probability of rolling at least 5?", "value", "1/3")
add("ren6-prb-02", "probability", "A fair coin is flipped twice. What is the exact probability of two heads?", "value", "1/4")
add("ren6-prb-03", "probability", "A bag has 3 red and 5 blue marbles. One marble is drawn. Exact probability it is red?", "value", "3/8")
add("ren6-prb-04", "probability", "Two fair dice are rolled. Exact probability the sum is 7?", "value", "1/6")
add("ren6-prb-05", "probability", "A fair coin is flipped three times. Exact probability of exactly one head?", "value", "3/8")
add("ren6-prb-06", "probability", "A bag has 4 red and 6 blue marbles. Two are drawn without replacement. Exact probability both are red?", "value", "2/15")
add("ren6-prb-07", "probability", "Events A and B are independent with P(A)=1/2 and P(B)=1/5. Exact P(A and B)?", "value", "1/10")
add("ren6-prb-08", "probability", "Mutually exclusive events have P(A)=1/4 and P(B)=1/6. Exact P(A or B)?", "value", "5/12")
add("ren6-prb-09", "probability", "A fair die is rolled once. Exact probability the result is even?", "value", "1/2")
add("ren6-prb-10", "probability", "Two fair coins are flipped. Exact probability of at least one head?", "value", "3/4")

add("ren6-num-01", "number theory", "Compute gcd(96, 36).", "value", _value(sp.gcd(96, 36)))
add("ren6-num-02", "number theory", "Compute lcm(14, 21).", "value", _value(sp.lcm(14, 21)))
add("ren6-num-03", "number theory", "Give the prime factorization of 126.", "expression", "2*3**2*7")
add("ren6-num-04", "number theory", "Compute 2^7 mod 5.", "value", _value(pow(2, 7, 5)))
add("ren6-num-05", "number theory", "How many positive divisors does 36 have?", "value", _value(sp.divisor_count(36)))
add("ren6-num-06", "number theory", "Compute the sum of the positive divisors of 18.", "value", _value(sp.divisor_sigma(18)))
add("ren6-num-07", "number theory", "Compute Euler's totient phi(15).", "value", _value(sp.totient(15)))
add("ren6-num-08", "number theory", "Compute 58 mod 7.", "value", _value(58 % 7))
add("ren6-num-09", "number theory", "What is the next prime after 29?", "value", _value(sp.nextprime(29)))
add("ren6-num-10", "number theory", "What is the smallest prime factor of 77?", "value", _value(min(sp.primefactors(77))))

add("ren6-cnt-01", "counting", "Compute C(8, 2).", "value", _value(sp.binomial(8, 2)))
add("ren6-cnt-02", "counting", "In how many orders can 4 distinct mugs be arranged on a shelf?", "value", _value(sp.factorial(4)))
add("ren6-cnt-03", "counting", "How many 2-digit codes use digits 0-9 with no repeated digits?", "value", _value(10 * 9))
add("ren6-cnt-04", "counting", "Among 6 people, how many handshakes if each pair shakes once?", "value", _value(sp.binomial(6, 2)))
add("ren6-cnt-05", "counting", "How many binary strings of length 5 exist?", "value", _value(2**5))
add("ren6-cnt-06", "counting", "A committee of 3 is chosen from 8 people. How many committees are possible?", "value", _value(sp.binomial(8, 3)))
add("ren6-cnt-07", "counting", "How many distinct arrangements does the word PEPPER have?", "value", _value(sp.factorial(6) // (sp.factorial(3) * sp.factorial(2))))
add("ren6-cnt-08", "counting", "How many diagonals does a convex hexagon have?", "value", _value(sp.binomial(6, 2) - 6))
add("ren6-cnt-09", "counting", "In how many ways can 2 distinct prizes be awarded to 7 people with at most one prize each?", "value", _value(7 * 6))
add("ren6-cnt-10", "counting", "Compute P(6, 3).", "value", _value(6 * 5 * 4))

add("ren6-seq-01", "sequences", "An arithmetic sequence starts 5, 8, 11, .... What is the 10th term?", "value", _value(5 + 9 * 3))
add("ren6-seq-02", "sequences", "A geometric sequence starts 2, 6, 18, .... What is the 6th term?", "value", _value(2 * (3**5)))
add("ren6-seq-03", "sequences", "Compute the sum of the first 25 positive integers.", "value", _value(25 * 26 // 2))
add("ren6-seq-04", "sequences", "Compute the sum of the first 8 terms of 3, 7, 11, 15, ....", "value", _value(sum(3 + 4 * i for i in range(8))))
add("ren6-seq-05", "sequences", "Compute the sum of the finite geometric series 1 + 2 + 4 + 8 + 16.", "value", _value((2**5 - 1) // (2 - 1)))
fib = [0, 1]
while len(fib) <= 10:
    fib.append(fib[-1] + fib[-2])
add("ren6-seq-06", "sequences", "What is the 10th Fibonacci number if F(1)=1 and F(2)=1?", "value", _value(fib[10]))
add("ren6-seq-07", "sequences", "A sequence obeys a_n = 3 a_(n-1) + 1 with a_1 = 1. What is a_4?", "value", "40")
add("ren6-seq-08", "sequences", "Compute the infinite geometric sum 1 + 1/4 + 1/16 + 1/64 + ....", "value", "4/3")
add("ren6-seq-09", "sequences", "What is the 12th triangular number?", "value", _value(12 * 13 // 2))
add("ren6-seq-10", "sequences", "Compute 1^2 + 2^2 + ... + 6^2.", "value", _value(sum(i * i for i in range(1, 7))))

add("ren6-numc-01", "numerical checks", "A recurrence is x_(n+1) = 2 x_n + 3 with x_0 = 1. What is x_4?", "value", "61")
add("ren6-numc-02", "numerical checks", "Approximate integral of x from 0 to 4 with one trapezoid using endpoints. Exact trapezoid value?", "value", "8")
add("ren6-numc-03", "numerical checks", "One Babylonian square-root step for 13 starting at 4: (4 + 13/4)/2. Exact value?", "value", "29/8")
add("ren6-numc-04", "numerical checks", "Convert binary 101011 to decimal.", "value", _value(int("101011", 2)))
add("ren6-numc-05", "numerical checks", "Convert decimal 23 to base 5.", "value", "43")
add("ren6-numc-06", "numerical checks", "Compute the Hamming distance between 1100101 and 1010111.", "value", "3")
add("ren6-numc-07", "numerical checks", "Compute (12 + 19 + 8 + 6) mod 9.", "value", _value((12 + 19 + 8 + 6) % 9))
add("ren6-numc-08", "numerical checks", "Compute the weighted average of 4 with weight 3 and 10 with weight 2.", "value", "32/5")
add("ren6-numc-09", "numerical checks", "Compute the continued fraction 2 + 1/(3 + 1/4) exactly.", "value", "30/13")
add("ren6-numc-10", "numerical checks", "Compute 3^5.", "value", _value(3**5))


def render_mathproblem(problem: MathProblem) -> str:
    question = problem.question.replace("\\", "\\\\").replace('"', '\\"')
    if (
        problem.kind == "expression"
        or "/" in problem.answer
        or "**" in problem.answer
        or "cos" in problem.answer
        or "sin" in problem.answer
        or "exp" in problem.answer
    ):
        return (
            "    MathProblem(\n"
            f'        "{problem.problem_id}", "{problem.topic}",\n'
            f'        "{question}",\n'
            f'        "{problem.kind}", "{problem.answer}",\n'
            "    ),"
        )
    return (
        f'    MathProblem("{problem.problem_id}", "{problem.topic}", '
        f'"{question}", "{problem.kind}", "{problem.answer}"),'
    )


def render_oracle(problem: MathProblem) -> str:
    question = problem.question.replace("\\", "\\\\").replace('"', '\\"')
    return (
        f'    "{problem.problem_id}": (\n'
        f'        "{question}",\n'
        f'        "{problem.kind}",\n'
        f'        "{problem.answer}",\n'
        "    ),"
    )


def _apply(snippet: str, oracle: str) -> None:
    registry = TOOLS / "engel_math_problems.py"
    text = registry.read_text(encoding="utf-8")
    marker = "    # --- NOT decidable: proofs and conceptual statements"
    if "ren6-alg-01" in text:
        raise SystemExit("ren6 problems are already registered")
    if marker not in text:
        raise SystemExit("math registry insertion marker is missing")
    registry.write_text(
        text.replace(marker, snippet.rstrip() + "\n" + marker, 1),
        encoding="utf-8",
    )

    verifier = TOOLS / "verify_engel_curriculum_renewal.py"
    source = verifier.read_text(encoding="utf-8")
    if "INDEPENDENT_MATH_RENEWAL_V6_ORACLE" in source:
        raise SystemExit("v6 oracle is already present")
    oracle_block = (
        "\n# (2026-09-25) Independent v6 oracle for the ren6-* generation: every entry was\n"
        "# computed by tools/mint_engel_math_ren6_curriculum.py and checked by the grader.\n"
        "INDEPENDENT_MATH_RENEWAL_V6_ORACLE = {\n"
        + oracle.rstrip()
        + "\n}\n\n"
    )
    anchor = "\nexpected_ids = ["
    if anchor not in source:
        raise SystemExit("verifier oracle insertion anchor is missing")
    source = source.replace(anchor, oracle_block + anchor.lstrip("\n"), 1)
    source = source.replace(
        "or INDEPENDENT_MATH_RENEWAL_V5_ORACLE.get(problem.problem_id)",
        "or INDEPENDENT_MATH_RENEWAL_V5_ORACLE.get(problem.problem_id)\n"
        "                or INDEPENDENT_MATH_RENEWAL_V6_ORACLE.get(problem.problem_id)",
        1,
    )
    old_used = '''    == {
        problem.problem_id
        for problem in math_problems.PROBLEMS
        if problem.problem_id.startswith("ren5-")
    },'''
    new_used = '''    == {
        problem.problem_id
        for problem in math_problems.PROBLEMS
        if problem.problem_id.startswith("ren6-")
    },'''
    if old_used not in source:
        raise SystemExit("used-problem check was not the ren5 form")
    source = source.replace(old_used, new_used, 1)
    source = source.replace(
        'if problem.problem_id.startswith("ren5-")\n            ]\n        ),\n    },\n)',
        'if problem.problem_id.startswith("ren6-")\n            ]\n        ),\n    },\n)',
        1,
    )
    verifier.write_text(source, encoding="utf-8")


def main() -> int:
    if len(PROBLEMS) != 80:
        raise SystemExit(f"expected 80 ren6 problems, got {len(PROBLEMS)}")
    import engel_math_problems as registry

    existing_questions = {problem.question for problem in registry.PROBLEMS}
    live_ids = {problem.problem_id for problem in registry.PROBLEMS}
    for problem in PROBLEMS:
        if problem.question in existing_questions:
            raise SystemExit(f"question collides with existing registry: {problem.problem_id}")
        if problem.problem_id in live_ids:
            raise SystemExit(f"id already registered: {problem.problem_id}")
        verdict, detail = verify_against_truth(
            f"Result: {problem.answer}\nWork: mint\nCheck: sympy",
            problem,
        )
        if verdict != VERDICT_CORRECT:
            raise SystemExit(f"{problem.problem_id} grader rejected its own answer: {detail}")

    snippet = "\n".join(render_mathproblem(problem) for problem in PROBLEMS)
    oracle = "\n".join(render_oracle(problem) for problem in PROBLEMS)
    out = ROOT / "memory" / "training" / "engel_main" / "generated" / "ENGEL_MATH_REN6_MINT.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(
            {
                "schema": "engel_math_ren6_mint_v1",
                "count": len(PROBLEMS),
                "problems": [
                    {
                        "problem_id": problem.problem_id,
                        "topic": problem.topic,
                        "question": problem.question,
                        "kind": problem.kind,
                        "answer": problem.answer,
                    }
                    for problem in PROBLEMS
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    if "--apply" in sys.argv:
        _apply(snippet, oracle)
    print(json.dumps({"ok": True, "count": len(PROBLEMS), "applied": "--apply" in sys.argv}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
