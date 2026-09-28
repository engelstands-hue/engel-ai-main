#!/usr/bin/env python3
"""Prove the Forge turns emitted text into PROVEN code.

Before this module (measured 2026-07-31): reports/generated_code/ held
prompt-only artifacts nothing ever executed; the ROG build path observed a
compile error and replied "Ask me to fix it and I'll rebuild"; the Code
Companion's runner reported "not_run_by_runner_v1_no_shell_execution"; the
coder lane returned chat text nobody compiled. Emission everywhere,
verification nowhere.

What must hold for the Forge to be trustworthy:

  1. LOOP -- a scripted model that FAILS then FIXES ends 'forged', with the
     real stderr folded into the repair prompt (not a re-ask).
  2. PROOF, NOT CLAIM -- code whose tests fail is never 'forged'; code with no
     tests is never 'forged'; a passing forge really executed in the sandbox.
  3. GATE -- the import allowlist and deny tokens block os/subprocess/eval
     BEFORE anything runs, Governor-receipted, fail-closed when it is down.
  4. BOUNDED -- an always-broken model stops at MAX_ROUNDS; no unbounded loop.
  5. CORPUS -- every round appends a labeled outcome line (error class, tail,
     fixed_by_next) -- the code-outcome dataset the SLM roster lacked.
  6. WIRED -- routes resolve, the registry dispatches, the chat intercept
     answers locally, and the ROG build path now REPAIRS instead of asking the
     operator to ask again.

Exit 0 = Engel can create real, verified-working code.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
for _p in (str(ROOT), str(TOOLS)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import engel_code_forge as cf  # noqa: E402
from engel_code_forge import forge_prompt  # noqa: E402

CHECKS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    CHECKS.append((name, bool(ok), detail))
    print(f"{'PASS' if ok else 'FAIL'} {name}" + (f" -- {detail}" if detail and not ok else ""))


GOOD = (
    "FILE: solution.py\n"
    "def add(a, b):\n"
    "    return a + b\n"
    "FILE: test_solution.py\n"
    "from solution import add\n"
    "assert add(2, 3) == 5\n"
)
WRONG_LOGIC = (
    "FILE: solution.py\n"
    "def add(a, b):\n"
    "    return a - b\n"
    "FILE: test_solution.py\n"
    "from solution import add\n"
    "assert add(2, 3) == 5\n"
)
SYNTAX_BAD = (
    "FILE: solution.py\n"
    "def add(a, b:\n"
    "    return a + b\n"
    "FILE: test_solution.py\n"
    "from solution import add\n"
    "assert add(2, 3) == 5\n"
)
FORBIDDEN = (
    "FILE: solution.py\n"
    "import os\n"
    "def add(a, b):\n"
    "    os.system('echo hi')\n"
    "    return a + b\n"
    "FILE: test_solution.py\n"
    "from solution import add\n"
    "assert add(2, 3) == 5\n"
)
NO_TESTS = "FILE: solution.py\ndef add(a, b):\n    return a + b\n"
# The exact shape the local model emitted on the first live forge: a unittest
# suite ending in exit=False, so the process exits 0 even when a test FAILS.
_UNITTEST_TAIL = (
    "\nif __name__ == '__main__':\n    unittest.main(argv=[''], exit=False)\n"
)
EXIT_FALSE_LIAR = (
    "FILE: solution.py\n"
    "def add(a, b):\n"
    "    return a - b\n"  # wrong on purpose
    "FILE: test_solution.py\n"
    "import unittest\n"
    "from solution import add\n"
    "class T(unittest.TestCase):\n"
    "    def test_add(self):\n"
    "        self.assertEqual(add(2, 3), 5)\n" + _UNITTEST_TAIL
)
EXIT_FALSE_HONEST = (
    "FILE: solution.py\n"
    "def add(a, b):\n"
    "    return a + b\n"
    "FILE: test_solution.py\n"
    "import unittest\n"
    "from solution import add\n"
    "class T(unittest.TestCase):\n"
    "    def test_add(self):\n"
    "        self.assertEqual(add(2, 3), 5)\n" + _UNITTEST_TAIL
)


class _Scripted:
    """A deterministic stand-in for the local model lane."""

    def __init__(self, replies: list[str]) -> None:
        self.replies = list(replies)
        self.prompts: list[str] = []

    def __call__(self, prompt: str) -> str:
        self.prompts.append(prompt)
        index = min(len(self.prompts) - 1, len(self.replies) - 1)
        return self.replies[index]


def _sandboxed(tmp: str):
    """Point the Forge's workspace + receipts at a temp dir."""
    cf.WORKSPACE_ROOT = Path(tmp) / "ws"
    cf.RECEIPT_DIR = Path(tmp) / "receipts"


def run_loop() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        old = (cf.WORKSPACE_ROOT, cf.RECEIPT_DIR)
        _sandboxed(tmp)
        try:
            # 1. Happy path: really runs, really passes.
            model = _Scripted([GOOD])
            receipt = cf.forge("add two numbers", generate_fn=model)
            check(
                "loop: a working first draft forges in one round",
                receipt["status"] == "forged"
                and receipt["ok"] is True
                and len(receipt["rounds"]) == 1,
                receipt["status"],
            )
            observation = receipt["rounds"][0]["observation"]
            check(
                "proof: the tests were really executed in the sandbox",
                observation["tests_run"] == 1
                and observation["runs"][0]["returncode"] == 0,
                str(observation),
            )
            check(
                "proof: artifacts exist on disk and contain the forged code",
                bool(receipt["artifacts"])
                and Path(receipt["artifacts"][0]).is_file()
                and "def add" in Path(receipt["artifacts"][0]).read_text(encoding="utf-8"),
                str(receipt["artifacts"]),
            )
            verdict = receipt["rounds"][0].get("allow_verdict") or {}
            check(
                "governor: every forge run carries an allow verdict",
                verdict.get("rule_id") == "allow.gate.forge_code_gate"
                and verdict.get("outcome") == "allow",
                str(verdict),
            )

            # 2. Repair from a REAL assertion failure.
            model = _Scripted([WRONG_LOGIC, GOOD])
            receipt = cf.forge("add two numbers correctly", generate_fn=model)
            check(
                "repair: failing tests are repaired and the second round forges",
                receipt["status"] == "forged" and len(receipt["rounds"]) == 2,
                f"{receipt['status']} rounds={len(receipt['rounds'])}",
            )
            check(
                "observe: the first round is labeled an assert failure",
                receipt["rounds"][0]["error_class"] == "assert",
                receipt["rounds"][0]["error_class"],
            )
            check(
                "repair: the repair prompt carries the REAL stderr (AssertionError)",
                len(model.prompts) == 2
                and "What failed" in model.prompts[1]
                and "AssertionError" in model.prompts[1],
                model.prompts[1][-200:] if len(model.prompts) > 1 else "",
            )

            # 3. Repair from a syntax error (caught at compile, before running).
            model = _Scripted([SYNTAX_BAD, GOOD])
            receipt = cf.forge("add numbers with valid syntax", generate_fn=model)
            check(
                "repair: a syntax error is caught at compile and repaired",
                receipt["status"] == "forged"
                and receipt["rounds"][0]["error_class"] == "compile",
                str(receipt["rounds"][0].get("error_class")),
            )

            # 4. Proof, not claim: broken forever never passes.
            model = _Scripted([WRONG_LOGIC])
            receipt = cf.forge("never fixed", generate_fn=model)
            check(
                "proof: code whose tests keep failing is NEVER reported forged",
                receipt["status"] == "needs attention" and receipt["ok"] is False,
                receipt["status"],
            )
            check(
                "bounded: an always-failing model stops at MAX_ROUNDS",
                len(receipt["rounds"]) == cf.MAX_ROUNDS
                and len(model.prompts) == cf.MAX_ROUNDS,
                f"rounds={len(receipt['rounds'])} calls={len(model.prompts)}",
            )

            # 5. A zero exit code is not proof. The FIRST live forge
            # (2026-08-01) emitted `unittest.main(argv=[''], exit=False)`,
            # which swallows the exit code -- a suite whose assertions fail
            # still exits 0. Proven live before the fix; guarded forever here.
            model = _Scripted([EXIT_FALSE_LIAR])
            receipt = cf.forge("exit code lies", generate_fn=model, max_rounds=1)
            check(
                "proof: a failing suite that exits 0 (exit=False) is NOT forged",
                receipt["ok"] is False and receipt["status"] == "needs attention",
                receipt["status"],
            )
            run_rec = receipt["rounds"][0]["observation"]["runs"][0]
            check(
                "proof: the lying exit code is recorded as such in the receipt",
                run_rec["returncode"] == 0
                and run_rec["ok"] is False
                and run_rec.get("exit_code_lied"),
                str(run_rec)[:200],
            )
            check(
                "proof: a genuinely passing unittest suite still forges",
                cf.forge("honest unittest", generate_fn=_Scripted([EXIT_FALSE_HONEST]))[
                    "ok"
                ]
                is True,
            )

            # 5b. Advisory extraction notes must never veto proven tests.
            with_extra = (
                "FILE: readme.md\n"
                "notes\n" + GOOD
            )
            receipt = cf.forge(
                "extra file", generate_fn=_Scripted([with_extra]), max_rounds=1
            )
            check(
                "honesty: a passing run is NOT failed by an advisory extraction note",
                receipt["ok"] is True and receipt["status"] == "forged",
                f"{receipt['status']} problems={receipt['rounds'][0].get('problems')}",
            )
            check(
                "honesty: the dropped-file note rides the receipt as a warning",
                any(
                    "readme" in w.casefold()
                    for w in receipt["rounds"][0].get("warnings", [])
                ),
                str(receipt["rounds"][0].get("warnings")),
            )

            # 5c. A round that could not run tests is never classed 'none'.
            receipt = cf.forge(
                "no tests class", generate_fn=_Scripted([NO_TESTS]), max_rounds=1
            )
            check(
                "honesty: a round with no tests is classed 'no_tests', never 'none'",
                receipt["rounds"][0]["error_class"] == "no_tests",
                receipt["rounds"][0]["error_class"],
            )

            # 5d. A crash still leaves a receipt (receipts ARE the corpus).
            def _boom(_prompt: str) -> str:
                raise RuntimeError("generator exploded")

            receipt = cf.forge("crashing run", generate_fn=_boom, max_rounds=1)
            check(
                "honesty: a generator crash is caught and still yields a receipt",
                receipt.get("status") in ("nothing forged", "crashed")
                and receipt.get("ok") is False
                and receipt.get("receipt_path"),
                str(receipt.get("status")),
            )

            # 6. No tests emitted is a problem, never a pass.
            model = _Scripted([NO_TESTS])
            receipt = cf.forge("untested code", generate_fn=model)
            check(
                "proof: code with no tests is never forged",
                receipt["ok"] is False
                and any(
                    "no test_" in p
                    for p in receipt["rounds"][0].get("problems", [])
                ),
                str(receipt["rounds"][0].get("problems")),
            )

            # 6. An empty model reply degrades honestly.
            receipt = cf.forge("silent model", generate_fn=lambda p: "")
            check(
                "loop: an empty model reply is honest, not a crash",
                receipt["status"] == "nothing forged" and receipt["ok"] is False,
                receipt["status"],
            )
        finally:
            cf.WORKSPACE_ROOT, cf.RECEIPT_DIR = old


# The exact shape the local model emitted live on 2026-08-01: the checks are
# DEFINED and never called, so the file exits 0 having asserted nothing -- and
# one of those never-executed asserts (group([""]) == [[]]) was itself wrong.
# Exit code and output scanning both look clean here, which is why this needs
# its own static guard.
INERT_TEST = (
    "FILE: solution.py\n"
    "def group_anagrams(words):\n"
    "    groups = {}\n"
    "    for word in words:\n"
    "        groups.setdefault(''.join(sorted(word)), []).append(word)\n"
    "    return list(groups.values())\n"
    "FILE: test_solution.py\n"
    "from solution import group_anagrams\n"
    "def test_group_anagrams():\n"
    "    assert group_anagrams(['eat', 'tea']) == [['eat', 'tea']]\n"
    "    assert group_anagrams(['']) == [[]]\n"
)


def run_inert_tests() -> None:
    check(
        "inert test: checks defined but never called are detected",
        cf.test_assertions_can_execute(
            "def test_x():\n    assert 1 == 2\n"
        )
        is False,
    )
    check(
        "inert test: bare module-level asserts are accepted",
        cf.test_assertions_can_execute("from solution import f\nassert f(1) == 1\n")
        is True,
    )
    check(
        "inert test: a called test function is accepted",
        cf.test_assertions_can_execute(
            "def test_x():\n    assert 1 == 1\ntest_x()\n"
        )
        is True,
    )
    check(
        "inert test: a table-driven for-loop of asserts is accepted "
        "(loops were invisible to the scan)",
        cf.test_assertions_can_execute(
            "from solution import add\n"
            "CASES = [(1, 2, 3), (2, 3, 5)]\n"
            "for a, b, want in CASES:\n"
            "    assert add(a, b) == want\n"
        )
        is True,
    )
    check(
        "inert test: a while-loop of asserts is accepted",
        cf.test_assertions_can_execute(
            "i = 0\nwhile i < 3:\n    assert i < 3\n    i += 1\n"
        )
        is True,
    )
    check(
        "inert test: a main-guarded loop of asserts is accepted",
        cf.test_assertions_can_execute(
            "if __name__ == '__main__':\n"
            "    for x in [1, 2]:\n"
            "        assert x > 0\n"
        )
        is True,
    )
    check(
        "inert test: a unittest.main() entry point is accepted",
        cf.test_assertions_can_execute(
            "import unittest\n"
            "class T(unittest.TestCase):\n"
            "    def test_x(self):\n"
            "        self.assertEqual(1, 1)\n"
            "if __name__ == '__main__':\n"
            "    unittest.main()\n"
        )
        is True,
    )
    with tempfile.TemporaryDirectory() as tmp:
        old = (cf.WORKSPACE_ROOT, cf.RECEIPT_DIR)
        _sandboxed(tmp)
        try:
            receipt = cf.forge(
                "group anagrams", generate_fn=_Scripted([INERT_TEST]), max_rounds=1
            )
            check(
                "inert test: a suite that asserts nothing is NEVER forged "
                "(live 2026-08-01 shape)",
                receipt["ok"] is False,
                receipt["status"],
            )
            check(
                "inert test: it is caught statically, before anything runs",
                receipt["rounds"][0]["error_class"] == "inert_test"
                and "observation" not in receipt["rounds"][0],
                str(receipt["rounds"][0].get("error_class")),
            )
            check(
                "inert test: the repair problem tells the model exactly what to fix",
                any(
                    "never executes any assertion" in p
                    for p in receipt["rounds"][0]["problems"]
                ),
                str(receipt["rounds"][0]["problems"])[:200],
            )
        finally:
            cf.WORKSPACE_ROOT, cf.RECEIPT_DIR = old


def run_prompt_safety() -> None:
    """The cards must survive TWO upstream detectors, both proven live to eat
    a forge before any model saw it:
      1. _blocked_command_turn -- run/execute/command/shell + a planner hit;
         the card's own safety sentence tripped it (2026-07-31).
      2. _prompt_requests_help_next -- bare substring "modules"; "only these
         modules:" got answered with "what should we work on next?" and never
         called a model (2026-08-01).
    Both are live routing/safety surfaces and stay untouched; the CARDS stay
    out of their vocabulary."""
    import re as _re

    command_re = _re.compile(
        r"\b(run|execute|cmd|command|powershell|terminal|shell)\b", _re.I
    )
    # The literal terms _prompt_requests_help_next substring-matches that a
    # code-generation card could plausibly contain.
    reflex_terms = ("modules", "workspace", "resources", "what parts", "what can engel")
    cards = (
        ("forge card", forge_prompt("add two numbers")),
        (
            "repair card",
            cf.repair_forge_prompt(
                "add two numbers", {"solution.py": "x = 1\n"}, ["test failed"]
            ),
        ),
    )
    for label, text in cards:
        hit = command_re.search(text)
        check(
            f"prompt safety: the {label} avoids command vocabulary "
            "(CT's blocked-command gate)",
            hit is None,
            f"matched {hit.group(0)!r}" if hit else "",
        )
        low = text.casefold()
        caught = [term for term in reflex_terms if term in low]
        check(
            f"prompt safety: the {label} avoids the help-next reflex vocabulary",
            not caught,
            f"matched {caught}",
        )
    check(
        "prompt safety: the card still names the FILE: contract and the allowlist",
        "FILE: solution.py" in forge_prompt("x") and "math" in forge_prompt("x"),
    )


# The exact payload that defeated the gate on 2026-08-01 before _STDLIB_NAMES
# existed: a trivial os.py put "os" into local_modules, so `import os` passed
# the gate -- and the child then resolved the REAL os (already in sys.modules
# from interpreter startup), reaching os.system. Tests went green, so the run
# would have been blessed "forged". The sandbox could not catch it: its
# denylist inspects the argv WE pass, never what the child spawns.
STDLIB_SHADOW_ATTACK = (
    "FILE: os.py\n"
    "SHADOW = True\n"
    "FILE: solution.py\n"
    "import os\n"
    "def add(a, b):\n"
    "    return a + b if not hasattr(os, 'system') else 0\n"
    "FILE: test_solution.py\n"
    "from solution import add\n"
    "assert add(2, 3) == 5\n"
)


def run_shadow_attack() -> None:
    files, problems = cf.extract_files(STDLIB_SHADOW_ATTACK)
    check(
        "shadow attack: a generated file named os.py is refused outright",
        "os.py" not in files and any("shadows" in p for p in problems),
        f"files={sorted(files)} problems={problems}",
    )
    check(
        "shadow attack: `import os` is still rejected by the gate "
        "(second, independent guard)",
        any("os" in p and "allowlist" in p for p in cf.gate_files(files)),
        str(cf.gate_files(files)),
    )
    # Even if a shadowing file somehow reached gate_files, the local-module
    # allowance must never cover a stdlib name.
    check(
        "shadow attack: local_modules never grants a stdlib name",
        any(
            "allowlist" in p
            for p in cf.gate_files(
                {"os.py": "X = 1\n", "solution.py": "import os\n"}
            )
        ),
        str(cf.gate_files({"os.py": "X = 1\n", "solution.py": "import os\n"})),
    )
    for shadow in ("json.py", "math.py", "socket.py", "subprocess.py"):
        clean, probs = cf.extract_files(
            f"FILE: {shadow}\nX = 1\nFILE: test_solution.py\nassert True\n"
        )
        if shadow in clean or not any("shadows" in p for p in probs):
            check(f"shadow attack: {shadow} is refused", False, str(probs))
            return
    check("shadow attack: every stdlib-shadowing file name is refused", True)
    # A non-stdlib local helper must STILL work (the fix must not over-block).
    check(
        "shadow attack: a legitimate local helper module is still importable",
        cf.gate_files(
            {
                "helpers.py": "def twice(x):\n    return 2 * x\n",
                "solution.py": "from helpers import twice\n",
                "test_solution.py": "from solution import *\n",
            }
        )
        == [],
    )


def run_gate_escapes() -> None:
    """The two PROVEN escapes from the 2026-08-01 adversarial review, plus the
    false positives the old substring gate produced. Both escapes were verified
    end-to-end writing a sentinel OUTSIDE the workspace while forge() still
    returned 'forged'."""
    escapes = (
        (
            "multi-import (`import math, os`) -- the regex read only the first name",
            {
                "solution.py": "import math, os\ndef add(a, b):\n    os.system('echo x')\n    return a + b\n",
                "test_solution.py": "from solution import add\nassert add(2, 3) == 5\n",
            },
        ),
        (
            "ambient __builtins__ + split-string getattr (no import at all)",
            {
                "test_solution.py": (
                    "_imp = getattr(__builtins__, '__imp' + 'ort__')\n"
                    "_imp('os').system('echo x')\n"
                    "assert True\n"
                )
            },
        ),
        (
            "dunder escape chain (__class__/__bases__/__subclasses__)",
            {"test_solution.py": "assert ().__class__.__bases__[0].__subclasses__()\n"},
        ),
        (
            "from-import of a forbidden module",
            {"test_solution.py": "from subprocess import run\nassert True\n"},
        ),
        (
            "relative import",
            {"test_solution.py": "from . import sneaky\nassert True\n"},
        ),
    )
    for label, files in escapes:
        check(f"gate escape blocked: {label}", bool(cf.gate_files(files)), str(files)[:120])

    # The mirror-image failure: a substring gate ALSO refused innocent code.
    allowed = (
        (
            "re.compile on an allowlisted module",
            {"solution.py": "import re\nPAT = re.compile(r'x')\n"},
        ),
        (
            "identifiers that merely contain banned substrings",
            {"solution.py": "def retrieval(q):\n    return q\ndef reopen(x):\n    return x\ndef user_input(v):\n    return v\n"},
        ),
        (
            "dataclass with dunder methods and a __name__ main guard",
            {
                "solution.py": "from dataclasses import dataclass\n@dataclass\nclass P:\n    x: int\n    def __repr__(self):\n        return 'P'\n",
                "test_solution.py": "import unittest\nif __name__ == '__main__':\n    unittest.main()\n",
            },
        ),
    )
    for label, files in allowed:
        check(
            f"gate allows legitimate code: {label}",
            cf.gate_files(files) == [],
            str(cf.gate_files(files)),
        )
    check(
        "gate: a file that will not parse is refused, not guessed at",
        bool(cf.gate_files({"solution.py": "def f(:\n"})),
    )


def run_gate() -> None:
    problems = cf.gate_files({"solution.py": "import os\nos.system('x')\n"})
    check(
        "gate: an out-of-allowlist import is refused",
        any("os" in p for p in problems),
        str(problems),
    )
    check(
        "gate: subprocess/socket are refused",
        cf.gate_files({"a.py": "import subprocess\n"})
        and cf.gate_files({"a.py": "import socket\n"}),
    )
    check(
        "gate: eval/exec/open are refused even without an import",
        cf.gate_files({"a.py": "x = eval('1+1')\n"})
        and cf.gate_files({"a.py": "open('f').read()\n"}),
    )
    check(
        "gate: allowlisted stdlib passes",
        cf.gate_files({"a.py": "import math, json\nfrom collections import deque\n"}) == [],
    )
    check(
        "gate: a local sibling module import passes",
        cf.gate_files(
            {"solution.py": "def a(): pass\n", "test_solution.py": "from solution import a\n"}
        )
        == [],
    )

    with tempfile.TemporaryDirectory() as tmp:
        old = (cf.WORKSPACE_ROOT, cf.RECEIPT_DIR)
        _sandboxed(tmp)
        try:
            model = _Scripted([FORBIDDEN, GOOD])
            receipt = cf.forge("use the operating system", generate_fn=model)
            first = receipt["rounds"][0]
            check(
                "gate: forbidden code is blocked BEFORE any execution",
                first["error_class"] == "gate" and "observation" not in first,
                str(first.get("error_class")),
            )
            check(
                "gate: the violation becomes a repair problem and the next round forges",
                receipt["status"] == "forged"
                and any("allowlist" in p for p in first["problems"]),
                str(first["problems"])[:200],
            )

            # Governor down = fail closed (nothing runs).
            model = _Scripted([GOOD])
            saved = sys.modules.get("engel_governor")
            sys.modules["engel_governor"] = None  # type: ignore[assignment]
            try:
                receipt = cf.forge("governor down", generate_fn=model, max_rounds=1)
            finally:
                if saved is not None:
                    sys.modules["engel_governor"] = saved
                else:
                    sys.modules.pop("engel_governor", None)
            check(
                "gate: with the Governor unavailable the forge runs nothing (fail closed)",
                receipt["ok"] is False and receipt["status"] == "gate blocked",
                receipt["status"],
            )
        finally:
            cf.WORKSPACE_ROOT, cf.RECEIPT_DIR = old


def run_extraction() -> None:
    files, problems = cf.extract_files(GOOD)
    check(
        "extract: FILE: blocks split into named files",
        sorted(files) == ["solution.py", "test_solution.py"] and not problems,
        str(sorted(files)) + str(problems),
    )
    fenced = "here you go:\n```python\ndef a():\n    return 1\n```\n```python\nfrom solution import a\nassert a() == 1\n```\n"
    files, _ = cf.extract_files(fenced)
    check(
        "extract: a narrated fenced reply still yields solution + test",
        "solution.py" in files and any(n.startswith("test_") for n in files),
        str(sorted(files)),
    )
    files, problems = cf.extract_files("FILE: ../../etc/passwd\nx = 1\n")
    check(
        "extract: path-escaping names are dropped, not written",
        files == {} and any("unsafe" in p for p in problems),
        str(problems),
    )
    files, problems = cf.extract_files("no code here at all")
    check(
        "extract: a reply with no code is an honest problem",
        files == {} and problems,
        str(problems),
    )
    big = "FILE: solution.py\n" + ("x = 1\n" * 20000)
    files, problems = cf.extract_files(big)
    check(
        "extract: an oversized file is dropped with a reason",
        "solution.py" not in files and any("exceeds" in p for p in problems),
        str(problems)[:160],
    )


def run_corpus() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        old = (cf.WORKSPACE_ROOT, cf.RECEIPT_DIR)
        _sandboxed(tmp)
        try:
            model = _Scripted([WRONG_LOGIC, GOOD])
            receipt = cf.forge("corpus check", generate_fn=model)
            path = cf.RECEIPT_DIR / cf.OUTCOMES_NAME
            check("corpus: the outcomes dataset file is written", path.is_file())
            rows = [
                json.loads(line)
                for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            check(
                "corpus: one labeled row per round",
                len(rows) == len(receipt["rounds"]) == 2,
                str(len(rows)),
            )
            check(
                "corpus: the failing round carries its error class and tail",
                rows[0]["error_class"] == "assert" and rows[0]["error_tail"],
                str(rows[0])[:200],
            )
            check(
                "corpus: fixed_by_next labels whether the repair worked "
                "(the label failure_triage never had)",
                rows[0]["fixed_by_next"] is True and rows[1]["fixed_by_next"] is None,
                str([r["fixed_by_next"] for r in rows]),
            )
            # The label must come from round_ok, not from error_class: a next
            # round that merely failed without setting a class was previously
            # recorded as a SUCCESSFUL repair, poisoning the corpus.
            bad = cf.forge(
                "mislabel guard",
                generate_fn=_Scripted([WRONG_LOGIC, NO_TESTS]),
                max_rounds=2,
            )
            bad_rows = [
                json.loads(line)
                for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ][-2:]
            check(
                "corpus: a repair that did NOT succeed is never labeled fixed",
                bad_rows[0]["fixed_by_next"] is not True
                and bad["ok"] is False,
                str([(r["error_class"], r["fixed_by_next"]) for r in bad_rows]),
            )
            check(
                "corpus: rows carry the final status for outcome learning",
                all(r["final_status"] == "forged" for r in rows),
            )
            check(
                "receipt: the forge receipt is on disk and re-loadable",
                Path(receipt["receipt_path"]).is_file()
                and json.loads(Path(receipt["receipt_path"]).read_text(encoding="utf-8"))[
                    "schema"
                ]
                == "engel_forge_run_v1",
            )
        finally:
            cf.WORKSPACE_ROOT, cf.RECEIPT_DIR = old


def run_wireup() -> None:
    from engel_ai_update_routes import ROUTE_BY_ID, render_update_route, resolve_update_route
    from engel_communication_router import classify_user_input

    check(
        "wireup: forge routes are registered",
        all(
            rid in ROUTE_BY_ID
            for rid in ("engel.forge.docs", "engel.forge.code", "engel.forge.status")
        ),
    )
    check(
        "wireup: exact status alias beats the payload prefix",
        classify_user_input("engel forge status").route_target == "engel.forge.status",
        classify_user_input("engel forge status").route_target,
    )
    check(
        "wireup: a payload-carrying forge phrase resolves to the code route",
        classify_user_input("forge code a prime sieve").route_target
        == "engel.forge.code",
        classify_user_input("forge code a prime sieve").route_target,
    )
    check(
        "wireup: docs alias resolves",
        resolve_update_route("engel forge docs") == "engel.forge.docs",
    )
    rendered = render_update_route("engel.forge.docs", "engel forge docs")
    check(
        "wireup: the registry dispatches the docs renderer",
        "Forge" in rendered and "forge code" in rendered,
        rendered[:120],
    )
    check(
        "wireup: scripts may not invoke the forge (no recursion by phrase)",
        __import__("engel_script").route_step_safety("forge code something")["allowed"]
        is False,
    )

    import engel_main_local_model_worker as worker

    reply = worker._engel_forge_chat_intercept("engel forge status", "verify-f1")
    check(
        "chat: the worker answers forge status locally, without a model",
        isinstance(reply, dict) and reply.get("engel_forge_used") is True,
        str(reply)[:140],
    )
    check(
        "chat: a normal prompt is untouched by the forge intercept",
        worker._engel_forge_chat_intercept("how are you today", "verify-f2") is None,
    )
    source = (TOOLS / "engel_main_local_model_worker.py").read_text(encoding="utf-8")
    forge_block = source.split("def _engel_forge_chat_intercept", 1)[1]
    gen_block = forge_block.split("def _generate", 1)[1].split("with _request", 1)[0]
    check(
        "chat: the forge generator is chat_only with the long budget",
        "chat_only=True" in gen_block and "generation_seconds" in gen_block,
    )
    check(
        "chat: lane non-answers are retried, not spent as a forge round "
        "(style-gate meta-reply, live 2026-08-01)",
        "_looks_like_lane_non_answer" in gen_block and "for _attempt in" in gen_block,
    )
    check(
        "chat: a style-gate meta-reply is recognised as a non-answer",
        worker._looks_like_lane_non_answer(
            "The local model answered in 7.1 seconds, but the reply did not pass "
            "Engel's style/quality gate and the repair attempts were exhausted."
        )
        is True,
    )
    check(
        "chat: a reply carrying code is NEVER treated as a non-answer",
        worker._looks_like_lane_non_answer(
            "FILE: solution.py\ndef add(a, b):\n    return a + b\n"
        )
        is False
        and worker._looks_like_lane_non_answer("```python\ndef f():\n    pass\n```")
        is False,
    )
    # Dispatch ORDER, measured on the dispatch call sites (not definitions):
    # the forge must claim its phrases before the fleet/build detectors run.
    dispatch = source.split("conductor_reply = _engel_conductor_chat_intercept", 1)[1]
    # Routing defects proven live 2026-08-01: these phrasings escaped the
    # forge intercept entirely and reached _requested_app_build, turning a
    # forge request into a real CT246 app-build order.
    for phrase in (
        "engel code forge a parser",
        "engel forge code a parser",
        "forge code a parser",
    ):
        matched = worker._ENGEL_FORGE_CODE_RE.match(phrase)
        check(
            f"routing: {phrase!r} is claimed by the forge intercept",
            bool(matched) and bool((matched.group(1) or "").strip()),
            "would fall through to the app-build detector",
        )
    check(
        "routing: bare 'engel forge' still reaches docs, not a forge with no task",
        bool(worker._ENGEL_FORGE_DOCS_RE.match("engel forge")),
    )
    check(
        "chat: the forge intercept runs BEFORE the fleet/build detectors",
        # (2026-08-11) Call-site markers, both required present. The old form pinned
        # the argument NAME ("_run_fleet_dispatch(prompt, request_id)") while the call
        # site passes `operator_prompt`, so find() returned -1 and this went red for a
        # rename rather than a real reordering.
        dispatch.find("forge_reply = _engel_forge_chat_intercept") >= 0
        and dispatch.find("= _run_fleet_dispatch(") >= 0
        and dispatch.find("forge_reply = _engel_forge_chat_intercept")
        < dispatch.find("= _run_fleet_dispatch("),
        "forge intercept must precede fleet dispatch in the action-lane chain",
    )

    # The ROG-local build FALLBACK must repair from the compiler's own words
    # rather than telling the operator to ask again. (By policy this helper
    # runs only after CT246 -- verify_engel_worker_ct_build_policy -- so this
    # is the degraded path, not the primary build lane.)
    build_fn = source.split("def _run_app_build", 1)[1].split("\ndef ", 1)[0]
    check(
        "rog fallback: the 'ask me to fix it' dead end is gone from the reply",
        "Ask me to fix it" not in build_fn,
        build_fn[-400:],
    )
    check(
        "rog fallback: a compile error is fed back to the model and re-executed",
        "_regenerate_from_error" in build_fn
        and "compile_error" in build_fn.split("_regenerate_from_error", 1)[1][:4000]
        and build_fn.count("_execute_project(") >= 2,
    )


def main() -> int:
    run_extraction()
    run_prompt_safety()
    run_inert_tests()
    run_shadow_attack()
    run_gate_escapes()
    run_gate()
    run_loop()
    run_corpus()
    run_wireup()
    failed = [name for name, ok, _ in CHECKS if not ok]
    print(f"\n{len(CHECKS) - len(failed)}/{len(CHECKS)} checks passed")
    if failed:
        print("FAILED:")
        for name in failed:
            print(f"  - {name}")
        return 1
    print("verify_engel_code_forge: GREEN")
    return 0


if __name__ == "__main__":
    sys.exit(main())
