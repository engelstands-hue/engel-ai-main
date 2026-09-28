#!/usr/bin/env python3
"""Gate for execution verification of programming answers (engel_code_answer_verifier).

Two properties, pulling in opposite directions -- the same pair the math gate holds:

  IT MUST CATCH BROKEN CODE. Before this module, a fenced block with the right names
  passed form grading whether or not it could run: compilation-shaped text was treated
  as code, the exact habit the math work removed from arithmetic.

  IT MUST NOT REFUTE HONEST CODE. Partial snippets, other languages, gate-refused and
  expensive code all come back "unverified", never "refuted" -- a false refutation
  deletes a good sample AND trains against a correct program.

Plus the safety property: model code only ever runs through the Code Forge's proven
chain (AST allowlist gate -> sandbox tier -> silent-failure detector). This gate proves
gated code is REFUSED rather than executed, with a canary that would be visible if it
ever ran.

All offline. No model, no network.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT), str(ROOT / "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import engel_code_answer_verifier as cav  # noqa: E402
import engel_code_forge as cf  # noqa: E402

checks: list[dict] = []


def check(name: str, ok: bool, detail: str) -> None:
    checks.append({"name": name, "status": "PASS" if ok else "FAIL", "detail": detail})


def fenced(body: str) -> str:
    return f"Here is the implementation:\n```python\n{body}\n```\n"


# --- 1. CONFIRMS code that proves itself -------------------------------------------
GOOD = fenced(
    "def double(x):\n"
    "    return 2 * x\n"
    "\n"
    "assert double(2) == 4\n"
    "assert double(-3) == -6\n"
)
good = cav.verify_reply(GOOD)
check("self_proving_code_confirmed",
      good["refuted"] is False and good["confirmed_count"] == 1,
      f"refuted={good['refuted']} confirmed={good['confirmed_count']}")
check("grade_stamps_exactly_verified",
      cav.grade_reply(GOOD).get("exactly_verified") is True,
      "the admission stamp mirrors math_exactly_verified")

# --- 2. REFUTES code whose own check fails -----------------------------------------
BAD_ASSERT = fenced(
    "def double(x):\n"
    "    return 3 * x\n"
    "\n"
    "assert double(2) == 4\n"
)
bad = cav.verify_reply(BAD_ASSERT)
check("failing_self_test_refuted", bad["refuted"] is True,
      f"reason: {bad['reason'][:100]}")

BAD_SYNTAX = fenced(
    "def double(x)\n"
    "    return 2 * x\n"
    "\n"
    "assert double(2) == 4\n"
)
check("complete_block_with_syntax_error_refuted",
      cav.verify_reply(BAD_SYNTAX)["refuted"] is True,
      "a complete labelled block that cannot parse is provably broken")

# --- 3. NEVER refutes what it cannot prove -----------------------------------------
ELIDED = fenced("def helper(x):\n    ...\n# rest of the module elided\ndef broken(:\n")
check("elided_fragment_unverified", cav.verify_reply(ELIDED)["refuted"] is False,
      "deliberate elision must not be punished as broken code")

OTHER_LANG = "Use this:\n```bash\necho hello\n```\n"
check("other_language_yields_no_blocks",
      cav.verify_reply(OTHER_LANG)["blocks"] == [] and cav.verify_reply(OTHER_LANG)["refuted"] is False,
      "no Python toolchain claim is made about bash")

NO_ASSERTS = fenced("def double(x):\n    return 2 * x\n")
na = cav.verify_reply(NO_ASSERTS)
check("assert_free_code_unverified",
      na["refuted"] is False and na["confirmed_count"] == 0,
      "code that proves nothing about itself is unverified, not wrong")

check("empty_reply_not_refuted", cav.verify_reply("")["refuted"] is False,
      "an empty reply must not be treated as proven broken")

# --- 4. SAFETY: gated code is refused, not executed --------------------------------
canary = ROOT / "runtime" / "temp" / "code_answer_verify" / "CANARY_SHOULD_NEVER_EXIST"
canary.parent.mkdir(parents=True, exist_ok=True)
canary.unlink(missing_ok=True)
GATED = fenced(
    "import os\n"
    f"open(r'{canary}', 'w').write('escaped')\n"
    "assert True\n"
)
gated = cav.verify_reply(GATED)
check("gated_code_refused_not_executed",
      gated["refuted"] is False and not canary.exists()
      and "security gate" in (gated["blocks"][0]["detail"] if gated["blocks"] else ""),
      f"verdict={gated['blocks'][0]['detail'][:80] if gated['blocks'] else 'no block'}; "
      f"canary_exists={canary.exists()}")

DUNDER = fenced(
    "x = getattr(__builtins__, '__imp' + 'ort__')\n"
    "assert x\n"
)
d = cav.verify_reply(DUNDER)
check("dunder_escape_refused_not_executed",
      d["refuted"] is False and "security gate" in (d["blocks"][0]["detail"] if d["blocks"] else ""),
      "the Forge's proven escape-hatch family stays refused here too")

# --- 5. BOUNDED: an infinite loop is expensive, not wrong --------------------------
_orig_timeout = cf.RUN_TIMEOUT_S
cf.RUN_TIMEOUT_S = 5
try:
    started = time.time()
    LOOP = fenced("while True:\n    pass\nassert True\n")
    loop = cav.verify_reply(LOOP)
    elapsed = time.time() - started
finally:
    cf.RUN_TIMEOUT_S = _orig_timeout
check("infinite_loop_killed_and_unverified",
      loop["refuted"] is False and elapsed < 60,
      f"killed in {elapsed:.1f}s; timeout is 'unverified', never 'refuted'")

# --- 6. wiring: the trainer and the capability eval consume this verifier ----------
trainer_source = (ROOT / "tools" / "run_engel_flutter_main_ui_prompt_training.py").read_text(
    encoding="utf-8")
check("trainer_executes_engineering_code",
      "_code_answer_truth" in trainer_source
      and '"code_truth_verdict"' in trainer_source
      and "code answer's own program fails when run" in trainer_source,
      "a proven-broken code answer must lose its training row")
eval_source = (ROOT / "tools" / "engel_capability_eval.py").read_text(encoding="utf-8")
check("capability_eval_measures_code_execution",
      "code_executes" in eval_source and 'discipline == "code"' in eval_source
      and "CODE_SUITE" in eval_source,
      "programming progress is measured by execution across cycles, like math_correct")

failed = sum(1 for c in checks if c["status"] != "PASS")
print(json.dumps(
    {
        "schema": "engel_code_answer_verifier_verifier_v1",
        "status": "FAIL" if failed else "PASS",
        "passed": len(checks) - failed,
        "total": len(checks),
        "checks": checks,
    },
    indent=2,
))
raise SystemExit(1 if failed else 0)
