"""Split ren5 oracle out of V4 and wire v5 used-problem checks."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(r"D:\b.WorkSpace\Engel App")
VERIFY = ROOT / "tools" / "verify_engel_curriculum_renewal.py"


def main() -> None:
    text = VERIFY.read_text(encoding="utf-8")
    if "INDEPENDENT_MATH_RENEWAL_V5_ORACLE" not in text:
        start = text.find(
            "INDEPENDENT_MATH_RENEWAL_V4_ORACLE: dict[str, tuple[str, str, str]] = {"
        )
        if start < 0:
            raise SystemExit("V4 oracle start not found")
        brace = text.find("{", start)
        end_marker = "\n}\n\n\nexpected_ids"
        end = text.find(end_marker, brace)
        if end < 0:
            raise SystemExit("V4 oracle end not found")
        body = text[brace + 1 : end]
        lines = body.splitlines(keepends=True)
        ren4_lines: list[str] = []
        ren5_lines: list[str] = []
        i = 0
        while i < len(lines):
            line = lines[i]
            if '"ren5-' in line or '"ren4-' in line:
                block = [line]
                i += 1
                while i < len(lines):
                    block.append(lines[i])
                    if lines[i].rstrip().endswith("),"):
                        i += 1
                        break
                    i += 1
                if '"ren5-' in block[0]:
                    ren5_lines.extend(block)
                else:
                    ren4_lines.extend(block)
                continue
            if line.strip().startswith("#") and "ren5" in line.lower():
                ren5_lines.append(line)
                i += 1
                continue
            if not line.strip():
                i += 1
                continue
            ren4_lines.append(line)
            i += 1

        ren5_key_count = sum(1 for item in ren5_lines if '"ren5-' in item)
        ren4_key_count = sum(1 for item in ren4_lines if '"ren4-' in item)
        if ren5_key_count != 80:
            raise SystemExit(f"expected 80 ren5 keys, got {ren5_key_count}")
        if ren4_key_count != 80:
            raise SystemExit(f"expected 80 ren4 keys, got {ren4_key_count}")

        new_v4 = (
            "INDEPENDENT_MATH_RENEWAL_V4_ORACLE: dict[str, tuple[str, str, str]] = {\n"
            + "".join(ren4_lines).rstrip()
            + "\n}\n"
        )
        new_v5 = (
            "\n# (2026-09-14) Independent v5 oracle for the ren5-* generation: every entry was\n"
            "# hand-checked against the sympy mint in tools/mint_engel_math_ren5_curriculum.py\n"
            "# and the live registry rows in tools/engel_math_problems.py.\n"
            "INDEPENDENT_MATH_RENEWAL_V5_ORACLE: dict[str, tuple[str, str, str]] = {\n"
            + "".join(ren5_lines).rstrip()
            + "\n}\n"
        )
        text = text[:start] + new_v4 + new_v5 + text[end + len("\n}\n") :]

    old_used = (
        "    # (2026-08-16) the live cards now use the ren4 generation; the spent ren-/ren3- rows\n"
        '    # stay registered for pack-history reproducibility but are no longer "used".\n'
        '    "math_registry_contains_exactly_80_used_renewal_problems",\n'
        "    len(all_math_problem_ids) == 80\n"
        "    and len(set(all_math_problem_ids)) == 80\n"
        "    and set(all_math_problem_ids)\n"
        "    == {\n"
        "        problem.problem_id\n"
        "        for problem in math_problems.PROBLEMS\n"
        '        if problem.problem_id.startswith("ren4-")\n'
        "    },\n"
        "    {\n"
        '        "used": len(set(all_math_problem_ids)),\n'
        '        "registered": len(\n'
        "            [\n"
        "                problem\n"
        "                for problem in math_problems.PROBLEMS\n"
        '                if problem.problem_id.startswith("ren4-")\n'
        "            ]\n"
        "        ),\n"
        "    },\n"
        ")"
    )
    new_used = (
        "    # (2026-09-14) the live cards now use the ren5 generation; ren4/ren3 rows\n"
        '    # stay registered for pack-history reproducibility but are no longer "used".\n'
        '    "math_registry_contains_exactly_80_used_renewal_problems",\n'
        "    len(all_math_problem_ids) == 80\n"
        "    and len(set(all_math_problem_ids)) == 80\n"
        "    and set(all_math_problem_ids)\n"
        "    == {\n"
        "        problem.problem_id\n"
        "        for problem in math_problems.PROBLEMS\n"
        '        if problem.problem_id.startswith("ren5-")\n'
        "    },\n"
        "    {\n"
        '        "used": len(set(all_math_problem_ids)),\n'
        '        "registered": len(\n'
        "            [\n"
        "                problem\n"
        "                for problem in math_problems.PROBLEMS\n"
        '                if problem.problem_id.startswith("ren5-")\n'
        "            ]\n"
        "        ),\n"
        "    },\n"
        ")"
    )
    if old_used in text:
        text = text.replace(old_used, new_used, 1)
    elif 'if problem.problem_id.startswith("ren5-")' not in text[
        text.find("math_registry_contains_exactly_80_used_renewal_problems") : text.find(
            "math_registry_contains_exactly_80_used_renewal_problems"
        )
        + 500
    ]:
        raise SystemExit("used-renewal block not updated")

    if "math_v5_independent_oracle_covers_exactly_the_80_ren5_problems" not in text:
        v5_block = '''
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
        f"Result: {v5_answer}\\nWork: independent oracle\\nCheck: reviewed fixture",
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

'''
        # The f-string above escaped newlines for the verify_against_truth call incorrectly
        # when written as a Python string with \\n — fix by building with real escapes.
        v5_block = v5_block.replace(
            'f"Result: {v5_answer}\\nWork: independent oracle\\nCheck: reviewed fixture"',
            'f"Result: {v5_answer}\\nWork: independent oracle\\nCheck: reviewed fixture"',
        )
        # Ensure the generated verifier source contains real \n escapes inside the f-string.
        v5_block = v5_block.replace(
            "f\"Result: {v5_answer}\\nWork: independent oracle\\nCheck: reviewed fixture\"",
            'f"Result: {v5_answer}\\nWork: independent oracle\\nCheck: reviewed fixture"',
        )
        anchor = (
            "check(\n"
            '    "math_v4_independent_oracle_answers_are_accepted_by_the_runtime_grader",\n'
            "    not v4_runtime_failures,\n"
            "    v4_runtime_failures,\n"
            ")\n"
        )
        if anchor not in text:
            raise SystemExit("v4 runtime grader anchor not found")
        text = text.replace(anchor, anchor + "\n" + v5_block, 1)

    VERIFY.write_text(text, encoding="utf-8")
    print("patched", VERIFY)


if __name__ == "__main__":
    main()
