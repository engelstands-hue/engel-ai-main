#!/usr/bin/env python3
"""Execution verification for programming answers -- the code lane's CAS.

(2026-08-07) Code replies were graded on FORM: a fenced block with the right names
passed, whether or not it could ever run. That is the exact failure the math gate had
before the CAS verifier ("verification-shaped prose IS verification"), transplanted to
programming, where it trains the habit that compilation-shaped text is code.

Same asymmetry as `engel_math_answer_verifier`: REFUTE only what execution PROVES broken.
  REFUTED    - a complete, labelled Python block that will not parse, or whose OWN
               assertions fail when run. The reply's code contradicts the reply.
  CONFIRMED  - the block carries executable assertions and they pass in the sandbox.
  UNVERIFIED - everything else: other languages (no toolchain here), deliberately
               partial snippets, security-gated code (refused, not judged), timeouts
               (expensive is not wrong), assert-free code (nothing to prove).

Execution reuses the Code Forge's proven machinery end to end -- `gate_files` (the
post-RCE AST allowlist gate), assertion-reachability, and the sandboxed `run_tests`
with its silent-failure detector. Nothing here invents a second sandbox.

Workspaces live under runtime/temp (no-C rule) and are removed after each run.
"""
from __future__ import annotations

import re
import shutil
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT), str(ROOT / "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SCHEMA = "engel_code_answer_verification_v1"
WORK_ROOT = ROOT / "runtime" / "temp" / "code_answer_verify"
MAX_BLOCKS_EXECUTED = 2

VERDICT_REFUTED = "refuted"
VERDICT_CONFIRMED = "confirmed"
VERDICT_UNVERIFIED = "unverified"

_FENCE = re.compile(r"```(?:python|py)\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)
# Markers of a DELIBERATELY partial snippet. Refuting an intentional fragment for a
# SyntaxError would punish honest elision, so these downgrade to unverified instead.
_ELISION = re.compile(r"\.\.\.|<snip|# *(?:etc|elided|omitted|rest of)", re.IGNORECASE)


def extract_python_blocks(reply: str) -> list[str]:
    """Labelled Python fences only. Missing a block is fine; inventing one is not."""
    return [match.group(1).strip() for match in _FENCE.finditer(str(reply or "")) if match.group(1).strip()]


def _verify_block(block: str) -> tuple[str, str]:
    """(verdict, detail) for one fenced block, using the Forge's gates end to end."""
    import ast

    import engel_code_forge as cf

    try:
        ast.parse(block)
    except SyntaxError as exc:
        if _ELISION.search(block) or block.count("\n") < 2:
            return VERDICT_UNVERIFIED, "fragment does not parse; treated as deliberate elision"
        return VERDICT_REFUTED, f"complete python block will not parse: {exc.msg} (line {exc.lineno})"
    except ValueError:
        return VERDICT_UNVERIFIED, "block cannot be parsed for gating"

    files = {"test_reply_block.py": block if block.endswith("\n") else block + "\n"}
    # ANY gate problem refuses execution. The first cut of this function used
    # cf._fatal_notes to pick "serious" problems and the canary test caught `import os` +
    # open() actually RUNNING: the fatal/advisory split is the Forge's repair-loop
    # taxonomy, not an execution permission -- in the Forge itself any gate problem blocks
    # the run. Verified by the canary in verify_engel_code_answer_verifier.
    gate_problems = cf.gate_files(files)
    if gate_problems:
        return VERDICT_UNVERIFIED, f"security gate refused to run it: {gate_problems[0][:160]}"
    if not cf.test_assertions_can_execute(files["test_reply_block.py"]):
        return VERDICT_UNVERIFIED, "no reachable assertions -- nothing the code proves about itself"

    stamp = time.strftime("%Y%m%dT%H%M%S") + f"_{time.perf_counter_ns() % 100000}"
    workspace = WORK_ROOT / stamp
    workspace.mkdir(parents=True, exist_ok=True)
    try:
        for name, body in files.items():
            (workspace / name).write_text(body, encoding="utf-8")
        outcome = cf.run_tests(workspace, files)
    finally:
        shutil.rmtree(workspace, ignore_errors=True)

    if outcome.get("ok"):
        return VERDICT_CONFIRMED, "its own assertions pass in the sandbox"
    if outcome.get("error_class") in ("timeout", "gate"):
        return VERDICT_UNVERIFIED, f"run declined ({outcome.get('error_class')}); expensive or blocked is not wrong"
    problem = (outcome.get("problems") or ["run failed"])[0]
    return VERDICT_REFUTED, f"its own check fails when run: {problem[:200]}"


def verify_reply(reply: str, *, max_blocks: int = MAX_BLOCKS_EXECUTED) -> dict[str, Any]:
    """Verify each labelled Python block. `refuted` True means one is provably broken."""
    results = []
    for block in extract_python_blocks(reply)[:max_blocks]:
        verdict, detail = _verify_block(block)
        results.append({"lines": block.count("\n") + 1, "verdict": verdict, "detail": detail})
    refuted = [r for r in results if r["verdict"] == VERDICT_REFUTED]
    confirmed = [r for r in results if r["verdict"] == VERDICT_CONFIRMED]
    return {
        "schema": SCHEMA,
        "blocks": results,
        "refuted": bool(refuted),
        "confirmed_count": len(confirmed),
        "reason": refuted[0]["detail"] if refuted else "",
    }


def grade_reply(reply: str) -> dict[str, Any]:
    """Admission-gate summary, mirroring engel_math_problems.grade_reply's shape."""
    result = verify_reply(reply)
    if not result["blocks"]:
        return {"verdict": "undecidable", "refuted": False, "exactly_verified": False,
                "detail": "no labelled python block"}
    if result["refuted"]:
        return {"verdict": "wrong", "refuted": True, "exactly_verified": False,
                "detail": result["reason"]}
    if result["confirmed_count"]:
        return {"verdict": "verified", "refuted": False, "exactly_verified": True,
                "detail": "code proves itself: assertions pass in the sandbox"}
    return {"verdict": "undecidable", "refuted": False, "exactly_verified": False,
            "detail": result["blocks"][0]["detail"]}


def main(argv: list[str] | None = None) -> int:
    import argparse
    import json

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reply", required=True)
    args = parser.parse_args(argv)
    print(json.dumps(verify_reply(args.reply), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
