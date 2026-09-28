#!/usr/bin/env python3
"""Verifier: the semantic rewrite template is domain-scoped (issue e769c4a2).

The four-section construction-document rewrite (Known / Missing or
conflicting / Hold and owner / Next step + field-survey-lead roles) must be
used ONLY when the original request is a genuine incomplete-inputs project
judgment; every other prompt gets the plain-prose rewrite with no imported
boilerplate. Fixtures reuse the proven detector fixtures from
verify_engel_incomplete_input_gate_scope.py.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for entry in (str(ROOT), str(ROOT / "tools")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import engel_main_server_chat_http_service as svc  # noqa: E402

CHECKS: list[tuple[str, bool]] = []

GENERAL_PROMPT = ("If Joshua asked you to skip the quorum just once for a tiny fix, "
                  "what should you say and why?")
PROJECT_PROMPT = ("The drawings show different clearances between sheet A3 and the "
                  "elevation; the support detail is not indicated. What should we do?")
BOILERPLATE = ("Hold and owner", "field survey lead")


def check(name: str, ok: bool) -> None:
    CHECKS.append((name, bool(ok)))
    print(("PASS " if ok else "FAIL ") + name)


def main() -> int:
    general = svc._semantic_local_repair_request(
        GENERAL_PROMPT, "draft answer", ["directness"])
    project = svc._semantic_local_repair_request(
        PROJECT_PROMPT, "draft answer", ["completeness"])

    check("detector_fixtures_still_split",
          not svc._prompt_has_incomplete_project_inputs(GENERAL_PROMPT)
          and svc._prompt_has_incomplete_project_inputs(PROJECT_PROMPT))
    check("general_rewrite_has_no_boilerplate",
          not any(term in general for term in BOILERPLATE))
    check("general_rewrite_still_bounded",
          "140 words" in general and "do not discuss this rewrite" in general)
    check("project_rewrite_keeps_discipline",
          all(term in project for term in BOILERPLATE))
    check("both_carry_original_request",
          GENERAL_PROMPT[:40] in general and PROJECT_PROMPT[:40] in project)

    failed = [name for name, ok in CHECKS if not ok]
    print(f"\n{len(CHECKS) - len(failed)}/{len(CHECKS)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
