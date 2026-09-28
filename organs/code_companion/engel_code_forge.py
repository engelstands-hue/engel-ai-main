"""Engel Code Forge -- real code, proven by running it (v1).

Spec: docs/ENGEL_CODE_FORGE_DESIGN.md. Verifier: tools/verify_engel_code_forge.py.

Engel's local models could already EMIT code -- into reports/generated_code/
(prompt-only artifacts, never executed), into scaffolded apps (failures stop
the run, the error never reaches a model again), into the Code Companion's
workspace (a human presses Run). Emission was everywhere; verification was
nowhere. The Forge closes it: generate -> gate -> run -> observe -> repair,
with the sandboxed run's own stderr as the teacher.

Contract culture (same as the Conductor):

* **No model calls in this module.** ``generate_fn`` is injected by the
  caller that owns a model lane (the chat worker).
* **Bounded.** MAX_ROUNDS generate/run rounds; repairs are Governor-
  escalation-gated; per-run sandbox timeout; file count/size caps.
* **Proven, not claimed.** ``forged`` requires every emitted test_*.py to
  exit 0 in the sandbox. No tests emitted is a problem, never a pass.
* **Safe by allowlist.** v1 forges the pure-computation Python kernel: the
  import allowlist + deny tokens are the primary (deterministic, Governor-
  receipted) gate; engel_sandbox tiers stay on underneath as belts.
* **A dataset flywheel.** Every round appends one line to
  reports/engel_forge/forge_outcomes.jsonl -- goal, error class, error tail,
  fixed-by-next-round -- the (code, error, repair, outcome) corpus the SLM
  roster's failure_triage/reply_grader lanes were missing.
"""
from __future__ import annotations

import ast
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

ROOT = __import__('engel_project_paths').resolve_engel_app_root(__file__)
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

WORKSPACE_ROOT = ROOT / "runtime" / "forge_workspaces"
RECEIPT_DIR = ROOT / "reports" / "engel_forge"
OUTCOMES_NAME = "forge_outcomes.jsonl"

MAX_ROUNDS = 3
MAX_FILES = 8
MAX_FILE_BYTES = 48_000
RUN_TIMEOUT_S = 30
ERROR_TAIL_CHARS = 900
RESPONSE_CLIP = 400

GenerateFn = Callable[[str], str]

_SLUG_RE = re.compile(r"[^a-z0-9]+")
_SAFE_NAME_RE = re.compile(r"^[a-z0-9_][a-z0-9_\-]{0,60}\.py$")
_FILE_MARKER_RE = re.compile(r"^\s*(?:#\s*|//\s*)?FILE:\s*([^\s]+)\s*$")
_FENCE_RE = re.compile(r"```(?:python|py)?\s*\n(.*?)```", re.DOTALL)
_IMPORT_RE = re.compile(r"^\s*(?:import|from)\s+([A-Za-z0-9_.]+)", re.MULTILINE)

# The pure-computation kernel. Anything outside it -- os, sys, subprocess,
# socket, pathlib, shutil, importlib -- is a gate violation, reported and
# repairable. Over-blocking a benign import is the SAFE failure for
# model-generated code (the sandbox denylist documents the same philosophy).
ALLOWED_IMPORTS = frozenset(
    """abc bisect collections copy dataclasses datetime decimal enum fractions
    functools heapq itertools json math operator random re statistics string
    textwrap typing unittest""".split()
)

# Escape-hatch builtins, denied as BARE NAMES (ast.Name) rather than as text.
# getattr/setattr/vars are here because the proven bypass was
# getattr(__builtins__, '__imp' + 'ort__') -- no import statement, and the
# split string defeated any substring scan. Dunder names and attributes are
# denied separately by _is_dunder, which closes the __class__/__subclasses__/
# __globals__ family in one rule.
_DENY_NAMES = frozenset(
    """eval exec compile open input breakpoint globals locals vars getattr
    setattr delattr dir memoryview exit quit help
    __import__ __builtins__ __loader__ __spec__""".split()
)

# Dunders a normal pure-computation program legitimately uses. Everything else
# in the dunder family is denied, which is what closes the classic escape
# chains (__class__ -> __bases__ -> __subclasses__, __globals__, __code__,
# __dict__, __mro__) without needing to enumerate them.
_BENIGN_DUNDERS = frozenset(
    """__name__ __main__ __init__ __post_init__ __repr__ __str__ __format__
    __eq__ __ne__ __lt__ __le__ __gt__ __ge__ __hash__ __bool__ __len__
    __iter__ __next__ __contains__ __getitem__ __setitem__ __delitem__
    __enter__ __exit__ __call__ __doc__ __add__ __sub__ __mul__ __truediv__
    __floordiv__ __mod__ __pow__ __neg__ __abs__ __round__""".split()
)


def _is_dunder(name: str) -> bool:
    text = str(name or "")
    if text in _BENIGN_DUNDERS:
        return False
    return len(text) > 4 and text.startswith("__") and text.endswith("__")

# Every name the standard library owns. A generated file may NEVER be named
# after one, and a local file never grants its own name as an import.
#
# (2026-08-01 adversarial test, proven live) Without this the gate had a
# critical hole: `local_modules` was every emitted file's stem, so emitting a
# trivial `os.py` put "os" in the allowed set and `import os` PASSED the gate.
# At run time the child process resolves `os` to the REAL stdlib module --
# it is already in sys.modules from interpreter startup, so the local file
# never even shadows it -- handing model-generated code os.system(). The
# sandbox cannot catch that: its denylist inspects the argv WE pass, never
# what the child spawns. Verified payload lives in verify_engel_code_forge.
_STDLIB_NAMES = frozenset(getattr(sys, "stdlib_module_names", ())) | ALLOWED_IMPORTS | {
    "os", "sys", "subprocess", "socket", "pathlib", "shutil", "importlib",
    "builtins", "ctypes", "pickle", "signal", "threading", "multiprocessing",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def forge_slug(goal: str) -> str:
    slug = _SLUG_RE.sub("_", str(goal or "").strip().casefold()).strip("_")
    return slug[:48].rstrip("_") or "forge"


# ---------------------------------------------------------------------------
# Prompts (deterministic; the model call stays with the caller).
# ---------------------------------------------------------------------------
# Wording note (live 2026-07-31/08-01): the card must dodge TWO upstream
# detectors, both proven live before this text reached a model at all.
#   1. CT's protected command gate (_blocked_command_turn) fires on
#      run/execute/command/shell + a planner hit -- the card's own safety
#      sentence ("NO os/sys/subprocess, NO eval/exec") tripped it.
#   2. CT's help-next reflex (_prompt_requests_help_next) matches the BARE
#      substring "modules" -- "only these modules:" answered a code request
#      with "what should we work on next?" and never called a model.
# Both are live routing/safety surfaces and stay untouched; the card instead
# states only what IS allowed (the deterministic allowlist gate enforces the
# rest). Same class of lesson as the EngelScript draft text tripping the
# build detector. verify_engel_code_forge.run_prompt_safety guards it.
# The shape is shown CONCRETELY, not described. Live 2026-08-01: a described
# format ("<plain-assert tests>") produced a round with no test file at all and
# a round of unittest-with-exit=False; small local models copy an example far
# more reliably than they follow a description.
FORGE_RULES = (
    "Rules:\n"
    "- Reply with ONLY two files in exactly this shape, and nothing else:\n"
    "\n"
    "FILE: solution.py\n"
    "def fib(n):\n"
    "    return n if n < 2 else fib(n - 1) + fib(n - 2)\n"
    "\n"
    "FILE: test_solution.py\n"
    "from solution import fib\n"
    "assert fib(0) == 0\n"
    "assert fib(7) == 13\n"
    "\n"
    "- That is the whole format: the FILE: line, then the plain code. No\n"
    "  markdown fences, no prose, no headings.\n"
    "- test_solution.py is bare `assert` lines at the left margin. No test\n"
    "  framework, no classes, no main block, nothing to call. It prints\n"
    "  nothing when it passes.\n"
    "- Standard library only, and only these imports: "
    + ", ".join(sorted(ALLOWED_IMPORTS))
    + ".\n"
    "- Pure computation only: no files, no network, no other imports.\n"
    "- Keep the whole reply under 120 lines."
)


def forge_prompt(goal: str) -> str:
    return "\n".join(
        [
            "Write working Python for this task. The tests must pass.",
            "",
            FORGE_RULES,
            "",
            "Task: " + " ".join(str(goal or "").split()),
        ]
    )


def repair_forge_prompt(goal: str, files: dict[str, str], problems: list[str]) -> str:
    parts = [
        "Your previous Python for this task FAILED its tests. Fix it. "
        "Reply with ONLY the corrected files in the same FILE: format.",
        "",
        FORGE_RULES,
        "",
        "Previous files:",
    ]
    for name in sorted(files):
        parts.append(f"FILE: {name}")
        parts.append(files[name].rstrip())
    parts += ["", "What failed:"]
    parts.extend(f"- {p}" for p in problems[:8])
    parts += ["", "Task: " + " ".join(str(goal or "").split())]
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Extraction. FILE: markers first; fenced-block fallback for models that
# ignore the format (small local models narrate despite instructions).
# ---------------------------------------------------------------------------
def extract_files(reply: str) -> tuple[dict[str, str], list[str]]:
    text = str(reply or "")
    files: dict[str, str] = {}
    problems: list[str] = []
    # The canonical extractor (FILE: markers + JSON bundle + filename-comment
    # salvage + bare-code heuristics, hardened against the live coder-3b
    # failure shapes) lives in the worker; reuse it and fall back to the local
    # parser only when it is unavailable or finds nothing.
    try:
        from engel_main_local_model_worker import _extract_project_files

        files = dict(_extract_project_files(text, "solution.py") or {})
    except Exception:  # noqa: BLE001 -- the local parser below is the fallback
        files = {}
    if files:
        # The shared extractor collapses a narrated multi-fence reply onto the
        # default entry, which silently drops the TEST file -- and a forge with
        # no test can never be proven. Recover it from the fences.
        if not any(str(n).split("/")[-1].casefold().startswith("test_") for n in files):
            for fence in (m.group(1).strip("\n") for m in _FENCE_RE.finditer(text)):
                if "assert" in fence and fence not in "".join(files.values()):
                    files["test_solution.py"] = fence + "\n"
                    break
        return _sanitize_files(files, problems)
    current: Optional[str] = None
    lines: list[str] = []

    def _flush() -> None:
        nonlocal current, lines
        if current is not None:
            body = "\n".join(lines).strip("\n")
            if body.startswith("```"):
                # models sometimes fence each file's body; unwrap it
                match = _FENCE_RE.search(
                    body if body.rstrip().endswith("```") else body + "\n```"
                )
                if match:
                    body = match.group(1).strip("\n")
            files[current] = body + "\n"
        current, lines = None, []

    for line in text.splitlines():
        marker = _FILE_MARKER_RE.match(line)
        if marker:
            _flush()
            current = marker.group(1).strip().casefold()
            continue
        if current is not None:
            lines.append(line)
    _flush()

    if not files:
        fences = [m.group(1).strip("\n") for m in _FENCE_RE.finditer(text)]
        if fences:
            files["solution.py"] = fences[0] + "\n"
            test_body = next((f for f in fences[1:] if "assert" in f), None)
            if test_body:
                files["test_solution.py"] = test_body + "\n"

    if not files:
        return {}, ["reply contained no FILE: blocks and no fenced code"]
    return _sanitize_files(files, problems)


def _sanitize_files(
    files: dict[str, str], problems: list[str]
) -> tuple[dict[str, str], list[str]]:
    clean: dict[str, str] = {}
    for name, body in files.items():
        base = str(name).replace("\\", "/").split("/")[-1].casefold()
        if not _SAFE_NAME_RE.match(base):
            problems.append(f"unsafe or non-python file name {name!r} dropped")
            continue
        if base[:-3] in _STDLIB_NAMES:
            problems.append(
                f"file name {base!r} shadows a standard library name; "
                "name it something else"
            )
            continue
        if len(body.encode("utf-8", errors="replace")) > MAX_FILE_BYTES:
            problems.append(f"{base} exceeds {MAX_FILE_BYTES} bytes; dropped")
            continue
        clean[base] = body if body.endswith("\n") else body + "\n"
    if len(clean) > MAX_FILES:
        problems.append(f"more than {MAX_FILES} files; extras dropped")
        clean = dict(sorted(clean.items())[:MAX_FILES])
    if clean and not any(n.startswith("test_") for n in clean):
        problems.append(FATAL_NO_TESTS)
    return clean, problems


# Extraction notes come in two kinds and conflating them was a real defect
# (2026-08-01 review): a reply carrying an extra non-.py file logged the
# advisory "dropped" note, which then vetoed a run whose tests had actually
# PASSED -- reporting 'needs attention', discarding proven artifacts, and
# telling the model "your code FAILED its tests. Fix it." Only fatal notes may
# block; advisory notes ride the receipt as warnings.
FATAL_NO_TESTS = "no test_*.py file was emitted -- tests are required to prove the code"


def _fatal_notes(problems: list[str]) -> list[str]:
    return [p for p in problems if p == FATAL_NO_TESTS]


def _advisory_notes(problems: list[str]) -> list[str]:
    return [p for p in problems if p != FATAL_NO_TESTS]


# ---------------------------------------------------------------------------
# The deterministic gate (primary), then compile, then the sandboxed run.
# ---------------------------------------------------------------------------
def gate_files(files: dict[str, str]) -> list[str]:
    """Decide whether generated code may run. Structural (AST), not textual.

    (2026-08-01 adversarial review) The original text-scanning gate was
    defeated two ways, both proven end-to-end writing a file OUTSIDE the
    workspace while the run still returned 'forged':
      * ``import math, os`` -- the regex captured only the FIRST name, so the
        second import rode in free and os.system() ran;
      * ``getattr(__builtins__, '__imp' + 'ort__')('os')`` -- no import
        statement at all, and the split string defeated the token scan.
    Substring scanning also produced the mirror-image failure, refusing
    innocent code: ``re.compile(`` matched the 'compile(' token even though
    ``re`` is on the allowlist and is advertised to the model, permanently
    gate-blocking every regex task; ``def retrieval(`` matched 'eval('.

    So the gate now parses each file and judges NODES: every import alias
    (comma-separated and continuation forms included), every bare call to an
    escape-hatch builtin, and every dunder name/attribute (the ``__class__``/
    ``__subclasses__``/``__globals__`` family). ``re.compile`` is an attribute
    of an allowlisted module and passes; ``getattr`` and ``__builtins__`` do
    not. A file that will not parse is refused rather than guessed at.

    Honest limit, unchanged: this is a static gate over source, backed by the
    sandbox tier. It is not a syscall boundary -- see design doc section 3.
    """
    problems: list[str] = []
    # A local file grants its OWN name as an importable module -- but never a
    # name the standard library owns (see _STDLIB_NAMES: that hole handed
    # generated code the real `os`). Shadowing names are refused in
    # _sanitize_files too; this is the second, independent guard.
    local_modules = {name[:-3] for name in files} - _STDLIB_NAMES
    for name in sorted(files):
        body = files[name]
        try:
            tree = ast.parse(body)
        except SyntaxError as exc:
            problems.append(f"{name}: will not parse, so it cannot be gated: {exc.msg}")
            continue
        except ValueError as exc:  # NUL bytes and friends
            problems.append(f"{name}: cannot be parsed for gating: {exc}")
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = str(alias.name or "").split(".")[0]
                    if root not in local_modules and root not in ALLOWED_IMPORTS:
                        problems.append(
                            f"{name}: import of {root!r} is outside the allowlist "
                            "(pure-computation stdlib only)"
                        )
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    problems.append(f"{name}: relative imports are not allowed")
                    continue
                root = str(node.module or "").split(".")[0]
                if root not in local_modules and root not in ALLOWED_IMPORTS:
                    problems.append(
                        f"{name}: import of {root!r} is outside the allowlist "
                        "(pure-computation stdlib only)"
                    )
            elif isinstance(node, ast.Name):
                if node.id in _DENY_NAMES or _is_dunder(node.id):
                    problems.append(
                        f"{name}: use of {node.id!r} is not allowed in forged code"
                    )
            elif isinstance(node, ast.Attribute):
                if _is_dunder(node.attr):
                    problems.append(
                        f"{name}: attribute access {node.attr!r} is not allowed"
                    )
    # dedupe while keeping order, so a repeated idiom reports once
    seen: set[str] = set()
    unique = []
    for problem in problems:
        if problem not in seen:
            seen.add(problem)
            unique.append(problem)
    return unique


# A test file that merely DEFINES its checks proves nothing. Live 2026-08-01
# the model emitted `def test_group_anagrams(): assert ...` and never called
# it: the file exited 0 with zero assertions executed and was reported GREEN --
# and one of those never-executed asserts was itself wrong. Exit code and
# output scanning both look clean in that case, so this is a THIRD, static
# guard: at least one assertion must actually be reachable when the file runs.
_MODULE_BLOCKS = (ast.If, ast.Try, ast.With, ast.For, ast.While)
if hasattr(ast, "AsyncFor"):
    _MODULE_BLOCKS = _MODULE_BLOCKS + (ast.AsyncFor, ast.AsyncWith)


def _module_level_statements(tree: "ast.Module") -> list:
    """Statements that execute when the file runs, descending into module-level
    blocks -- if/try/with AND loops.

    (2026-08-01 review) Loops were missing, so the ordinary table-driven test
    shape (`for a, b, want in CASES:` / `    assert f(a, b) == want`) had no
    module-level Assert anywhere the scan could see and was wrongly reported
    as asserting nothing -- rejecting correct, genuinely-executing tests and
    writing a mislabeled `inert_test` row into the training corpus."""
    out: list = []
    stack = list(tree.body)
    while stack:
        node = stack.pop()
        out.append(node)
        if isinstance(node, _MODULE_BLOCKS):
            for attr in ("body", "orelse", "finalbody", "handlers"):
                for child in getattr(node, attr, []) or []:
                    stack.append(child)
        elif isinstance(node, ast.ExceptHandler):
            for child in node.body or []:
                stack.append(child)
    return out


def _contains_assertion(node) -> bool:
    for sub in ast.walk(node):
        if isinstance(sub, ast.Assert):
            return True
        if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute):
            if sub.func.attr.startswith("assert"):
                return True
    return False


def _called_name(node: "ast.Call") -> str:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def test_assertions_can_execute(source: str) -> bool:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return True  # compile_files reports syntax errors on its own
    top = _module_level_statements(tree)
    if any(isinstance(node, ast.Assert) for node in top):
        return True
    asserting = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and _contains_assertion(node)
    }
    for node in top:
        for sub in ast.walk(node):
            if not isinstance(sub, ast.Call):
                continue
            name = _called_name(sub)
            # a framework entry point really does run the cases (and a failure
            # then shows up in the output scanner)
            if name == "main" or name in asserting:
                return True
    return False


def check_tests_executable(files: dict[str, str]) -> list[str]:
    problems: list[str] = []
    for name in sorted(n for n in files if n.startswith("test_")):
        if not test_assertions_can_execute(files[name]):
            problems.append(
                f"{name} never executes any assertion -- it only DEFINES checks "
                "(nothing calls them), so it exits 0 without testing anything. "
                "Put the assert lines at the left margin, not inside a function."
            )
    return problems


def compile_files(files: dict[str, str]) -> list[str]:
    problems: list[str] = []
    for name in sorted(files):
        try:
            compile(files[name], name, "exec")
        except SyntaxError as exc:
            problems.append(f"{name}: syntax error line {exc.lineno}: {exc.msg}")
        except ValueError as exc:
            # compile() raises ValueError (not SyntaxError) on source
            # containing NUL bytes -- which local llama.cpp streaming has
            # produced. Report it as a compile problem the model can repair
            # instead of letting it escape and destroy the receipt.
            problems.append(f"{name}: cannot be compiled: {exc}")
    return problems


# A zero exit code is NOT proof. Live 2026-08-01 the first forged suite ended
# with `unittest.main(argv=[''], exit=False)` -- which SWALLOWS the exit code,
# so a suite whose assertions fail still exits 0 and would be reported green.
# Scan the real output for failure markers as well, so "forged" means the
# tests actually passed rather than merely returned.
_FAILURE_MARKERS = (
    re.compile(r"^FAILED \(", re.M),
    re.compile(r"^FAIL: ", re.M),
    re.compile(r"^ERROR: ", re.M),
    re.compile(r"Traceback \(most recent call last\)"),
)


def _silent_failure(output: str) -> str:
    for marker in _FAILURE_MARKERS:
        found = marker.search(output)
        if found:
            return found.group(0).strip()
    return ""


def run_tests(workspace: Path, files: dict[str, str]) -> dict[str, Any]:
    import engel_sandbox

    tests = sorted(n for n in files if n.startswith("test_"))
    runs: list[dict[str, Any]] = []
    problems: list[str] = []
    error_class = "none"
    for name in tests:
        result = engel_sandbox.run_sandboxed(
            [sys.executable, name],
            tier="restricted",
            timeout=RUN_TIMEOUT_S,
            cwd=str(workspace),
        )
        combined = f"{result.get('stdout') or ''}\n{result.get('stderr') or ''}"
        tail = str(result.get("stderr") or result.get("error") or "")[-ERROR_TAIL_CHARS:]
        silent = _silent_failure(combined) if result.get("ok") else ""
        run_rec = {
            "test": name,
            "ok": bool(result.get("ok")) and not silent,
            "returncode": result.get("returncode"),
            "stderr_tail": tail,
        }
        if silent:
            run_rec["exit_code_lied"] = silent
        runs.append(run_rec)
        if run_rec["ok"]:
            continue
        if silent:
            kind = "assert" if "AssertionError" in combined else "runtime"
            problems.append(
                f"{name} reported {silent!r} but exited 0 (a suite using "
                f"exit=False hides its failures): {tail or combined[-ERROR_TAIL_CHARS:]}"
            )
            if error_class == "none":
                error_class = kind
            continue
        if "timed out" in str(result.get("error", "")):
            kind = "timeout"
        elif result.get("blocked"):
            kind = "gate"
        elif "AssertionError" in tail:
            kind = "assert"
        else:
            kind = "runtime"
        if error_class == "none":
            error_class = kind
        problems.append(f"{name} failed ({kind}): {tail or 'no stderr'}")
    if not tests:
        # An honest class: this round failed because there was nothing to run.
        # Reporting 'none' here made a failed round look clean in the corpus.
        error_class = "no_tests"
    return {
        "ok": bool(tests) and not problems,
        "tests_run": len(tests),
        "runs": runs,
        "problems": problems,
        "error_class": error_class,
    }


# ---------------------------------------------------------------------------
# Governor + SLM advisory (best-effort, per the roster's advisory ladder).
# ---------------------------------------------------------------------------
def _govern(decision: str, features: dict[str, Any]) -> Optional[dict[str, Any]]:
    try:
        from engel_governor import govern

        return govern(decision, features)
    except Exception:  # noqa: BLE001 -- absence handled per class at the call site
        return None


def _slm_intent(goal: str) -> str:
    try:
        from engel_slm_runtime import get_slm_runtime

        runtime = get_slm_runtime()
        if not runtime.is_ready():
            return "unavailable"
        verdict = runtime.intent(goal)
        return str(verdict.get("label")) if verdict else "unavailable"
    except Exception:  # noqa: BLE001 -- advisory only
        return "unavailable"


# ---------------------------------------------------------------------------
# The loop.
# ---------------------------------------------------------------------------
def forge(
    goal: str,
    *,
    generate_fn: GenerateFn,
    write_receipt: bool = True,
    max_rounds: int = MAX_ROUNDS,
) -> dict[str, Any]:
    goal_text = " ".join(str(goal or "").split())
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    slug = forge_slug(goal_text)
    receipt: dict[str, Any] = {
        "schema": "engel_forge_run_v1",
        "started_at_utc": _now(),
        "goal": goal_text,
        "slug": slug,
        "workspace": str(WORKSPACE_ROOT / f"{slug}_{stamp}"),
        "slm_intent_advisory": _slm_intent(goal_text),
        "rounds": [],
        "status": "",
        "ok": False,
        "artifacts": [],
    }
    if not goal_text:
        receipt["status"] = "empty goal"
        return _finish(receipt, write_receipt)

    try:
        return _forge_rounds(receipt, goal_text, generate_fn, write_receipt, max_rounds)
    except Exception as exc:  # noqa: BLE001 -- a crash must still leave a receipt
        # Receipts ARE the corpus: a run that vanishes because compile() raised
        # ValueError on a stray NUL byte is a run nobody can audit or learn
        # from. Record the crash honestly and still write the receipt.
        receipt["status"] = "crashed"
        receipt["ok"] = False
        receipt["error"] = f"{type(exc).__name__}: {exc}"
        if receipt["rounds"]:
            receipt["rounds"][-1].setdefault("error_class", "crash")
            receipt["rounds"][-1].setdefault(
                "problems", [f"{type(exc).__name__}: {exc}"]
            )
        return _finish(receipt, write_receipt)


def _forge_rounds(
    receipt: dict[str, Any],
    goal_text: str,
    generate_fn: GenerateFn,
    write_receipt: bool,
    max_rounds: int,
) -> dict[str, Any]:
    prompt = forge_prompt(goal_text)
    files: dict[str, str] = {}
    repair_spent = False
    round_no = 0
    while round_no < max(1, int(max_rounds)):
        round_no += 1
        round_rec: dict[str, Any] = {"round": round_no}
        receipt["rounds"].append(round_rec)

        reply = _call_generate(generate_fn, prompt)
        if not reply.strip():
            round_rec["problems"] = ["model returned no reply"]
            round_rec["error_class"] = "extract"
            receipt["status"] = "nothing forged"
            break
        extracted, problems = extract_files(reply)
        advisory = _advisory_notes(problems)
        problems = _fatal_notes(problems)
        if advisory:
            round_rec["warnings"] = advisory
        round_rec["files"] = sorted(extracted)
        round_rec["files_sha256"] = _files_sha(extracted)
        if not extracted:
            round_rec["problems"] = problems + advisory
            round_rec["error_class"] = "extract"
            # Keep the last round that DID produce code: repairing from an
            # empty "Previous files:" section throws away work the model
            # already got right and spends the round re-deriving from nothing.
            prompt = _next_prompt(goal_text, files,
                                  problems + advisory + ["your last reply contained no code files"],
                                  round_rec, generate_fn, repair_spent, round_no, max_rounds)
            if prompt is None:
                receipt["status"] = "nothing forged"
                break
            repair_spent = True
            continue
        files = extracted

        # COMPILE FIRST: a file that will not parse cannot be meaningfully
        # gated, and "syntax error line 3" is a far more actionable repair
        # message than a policy refusal. compile() only produces bytecode --
        # nothing executes here -- so the gate still precedes all execution.
        compile_problems = compile_files(files)
        if compile_problems:
            all_problems = problems + compile_problems
            round_rec["problems"] = all_problems
            round_rec["error_class"] = "compile"
            prompt = _next_prompt(goal_text, files, all_problems, round_rec,
                                  generate_fn, repair_spent, round_no, max_rounds)
            if prompt is None:
                receipt["status"] = "needs attention"
                break
            repair_spent = True
            continue

        gate_problems = gate_files(files)
        gate_ok = not gate_problems
        allow_verdict = _govern(
            "allow",
            {"gate": "forge_code_gate", "gate_result": gate_ok, "files": sorted(files)},
        )
        round_rec["allow_verdict"] = allow_verdict
        if not gate_ok or allow_verdict is None or allow_verdict.get("outcome") != "allow":
            all_problems = problems + gate_problems
            if allow_verdict is None:
                all_problems.append("governor unavailable; forge runs fail closed")
            round_rec["problems"] = all_problems
            round_rec["error_class"] = "gate"
            prompt = _next_prompt(goal_text, files, all_problems, round_rec,
                                  generate_fn, repair_spent, round_no, max_rounds)
            if prompt is None:
                receipt["status"] = "gate blocked"
                break
            repair_spent = True
            continue

        inert_problems = check_tests_executable(files)
        if inert_problems:
            all_problems = problems + inert_problems
            round_rec["problems"] = all_problems
            round_rec["error_class"] = "inert_test"
            prompt = _next_prompt(goal_text, files, all_problems, round_rec,
                                  generate_fn, repair_spent, round_no, max_rounds)
            if prompt is None:
                receipt["status"] = "needs attention"
                break
            repair_spent = True
            continue

        workspace = Path(receipt["workspace"]) / f"round_{round_no}"
        try:
            workspace.mkdir(parents=True, exist_ok=True)
            for name, body in files.items():
                (workspace / name).write_text(body, encoding="utf-8")
        except OSError as exc:
            round_rec["problems"] = [f"workspace write failed: {exc}"]
            receipt["status"] = "needs attention"
            break
        round_rec["workspace"] = str(workspace)

        observation = run_tests(workspace, files)
        round_rec["observation"] = observation
        round_rec["error_class"] = observation["error_class"] if not observation["ok"] else "none"
        all_problems = problems + observation["problems"]
        # Only the tests decide. Advisory extraction notes (a dropped README,
        # an extra file) must never veto a run whose tests actually passed --
        # that discarded proven artifacts and told the model its working code
        # had failed. `problems` here is fatal-only by construction.
        if observation["ok"] and not problems:
            receipt["status"] = "forged"
            receipt["ok"] = True
            round_rec["round_ok"] = True
            receipt["artifacts"] = [str(workspace / name) for name in sorted(files)]
            break
        round_rec["problems"] = all_problems
        prompt = _next_prompt(goal_text, files, all_problems, round_rec,
                              generate_fn, repair_spent, round_no, max_rounds)
        if prompt is None:
            receipt["status"] = "needs attention"
            break
        repair_spent = True

    if not receipt["status"]:
        receipt["status"] = "needs attention"
    return _finish(receipt, write_receipt)


def _call_generate(generate_fn: GenerateFn, prompt: str) -> str:
    try:
        return str(generate_fn(prompt) or "")
    except Exception:  # noqa: BLE001 -- a generator crash degrades, never raises
        return ""


def _next_prompt(
    goal_text: str,
    files: dict[str, str],
    problems: list[str],
    round_rec: dict[str, Any],
    generate_fn: GenerateFn,
    repair_spent: bool,
    round_no: int,
    max_rounds: int,
) -> Optional[str]:
    """Governor-gated repair: the next round's prompt, or None when no repair
    is possible (rounds exhausted / escalation spent)."""
    if round_no >= max(1, int(max_rounds)):
        return None
    # The escalate verdict is RECEIPT-ONLY and is recorded with the true
    # already_escalated value. It does not gate the loop: max_rounds is the
    # sole bound. Passing already_escalated=False on every repair (as this
    # did) wrote a feature into the receipt that contradicted reality, which
    # breaks replay -- the whole point of inputs_hash. The Governor's
    # escalate class means "spend one expensive escalation per turn", which is
    # not what a bounded retry is; saying so plainly beats borrowing the
    # semantics and then lying in the features.
    verdict = _govern(
        "escalate",
        {
            "already_escalated": bool(repair_spent),
            "t0_uncertain": True,
            "high_stakes": True,
            "repair_round": round_no,
        },
    )
    if isinstance(verdict, dict):
        verdict = dict(verdict)
        verdict["advisory_only"] = True
    round_rec["escalate_verdict"] = verdict
    return repair_forge_prompt(goal_text, files, problems)


def _files_sha(files: dict[str, str]) -> str:
    digest = hashlib.sha256()
    for name in sorted(files):
        digest.update(name.encode("utf-8"))
        digest.update(files[name].encode("utf-8", errors="replace"))
    return digest.hexdigest()


def _slm_failure_outlook(
    goal: str, error_class: str, problems: list[Any]
) -> dict[str, Any] | None:
    """Ask the gated failure-triage head for a shadow opinion, never a retry decision."""
    try:
        from engel_slm_runtime import get_slm_runtime

        runtime = get_slm_runtime()
        if not runtime.is_ready():
            return None
        prediction = runtime.failure_outlook(
            goal,
            error_class,
            " | ".join(str(problem)[:200] for problem in problems[:3]),
        )
        return prediction if isinstance(prediction, dict) else None
    except Exception:  # noqa: BLE001 -- advisory absence never changes Forge behavior
        return None


def _finish(receipt: dict[str, Any], write: bool) -> dict[str, Any]:
    # The SLM is deliberately consulted only after the bounded loop has already
    # decided. Its output becomes comparison telemetry, never permission for an
    # extra round and never a substitute for the deterministic error class.
    for round_rec in receipt.get("rounds") or []:
        if not isinstance(round_rec, dict):
            continue
        error_class = str(round_rec.get("error_class") or "")
        if not error_class or error_class == "none":
            continue
        outlook = _slm_failure_outlook(
            str(receipt.get("goal") or ""),
            error_class,
            list(round_rec.get("problems") or []),
        )
        if outlook:
            round_rec["slm_failure_triage"] = outlook
    receipt["finished_at_utc"] = _now()
    if write:
        try:
            RECEIPT_DIR.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            path = RECEIPT_DIR / f"FORGE_{stamp}.json"
            path.write_text(
                json.dumps(receipt, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            receipt["receipt_path"] = str(path)
        except OSError as exc:
            receipt["receipt_write_error"] = str(exc)
        _append_outcomes(receipt)
    return receipt


def _append_outcomes(receipt: dict[str, Any]) -> None:
    """One JSONL line per round: the (code, error, repair, outcome) corpus.
    fixed_by_next is the label the failure_triage lane never had."""
    try:
        RECEIPT_DIR.mkdir(parents=True, exist_ok=True)
        rounds = receipt.get("rounds", [])
        lines = []
        for index, round_rec in enumerate(rounds):
            # Label from ONE source of truth: round_ok is stamped only where a
            # round actually reached 'forged'. Keying off error_class=='none'
            # mislabeled repairs as successful when the next round merely
            # failed in a way that left the class untouched -- poisoning the
            # corpus this file exists to produce.
            next_ok = (
                rounds[index + 1].get("round_ok") is True
                if index + 1 < len(rounds)
                else None
            )
            lines.append(
                json.dumps(
                    {
                        "schema": "engel_forge_outcome_v1",
                        "ts": receipt.get("finished_at_utc", ""),
                        "goal": receipt.get("goal", ""),
                        "slug": receipt.get("slug", ""),
                        "round": round_rec.get("round"),
                        "error_class": round_rec.get("error_class", ""),
                        "error_tail": " | ".join(
                            str(p)[:200] for p in round_rec.get("problems", [])[:3]
                        ),
                        "files_sha256": round_rec.get("files_sha256", ""),
                        "fixed_by_next": next_ok,
                        "final_status": receipt.get("status", ""),
                    },
                    ensure_ascii=False,
                )
            )
        if lines:
            with (RECEIPT_DIR / OUTCOMES_NAME).open("a", encoding="utf-8") as handle:
                handle.write("\n".join(lines) + "\n")
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Route render functions (engel.forge.*).
# ---------------------------------------------------------------------------
def list_forges(limit: int = 8) -> list[dict[str, Any]]:
    if not RECEIPT_DIR.is_dir():
        return []
    records = []
    for path in sorted(RECEIPT_DIR.glob("FORGE_*.json"), reverse=True)[:limit]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict):
            records.append(data)
    return records


def render_forge_docs(text: str = "") -> str:
    return (
        "Engel Code Forge -- real code, proven by running it "
        "(docs/ENGEL_CODE_FORGE_DESIGN.md).\n"
        "Loop: generate -> gate -> run -> observe -> repair, bounded at "
        f"{MAX_ROUNDS} rounds,\nGovernor-receipted, sandboxed "
        "(pure-computation Python allowlist, plain-assert tests).\n\n"
        "Phrases:\n"
        "  forge code <task>        forge and PROVE code in the main chat\n"
        "  engel forge status       recent forges: rounds, outcome, artifacts\n"
        "  engel forge docs         this reference\n\n"
        "Artifacts land in runtime/forge_workspaces/ (candidate outputs, never\n"
        "auto-deployed). Receipts: reports/engel_forge/. Every round feeds\n"
        "forge_outcomes.jsonl -- the code-outcome training corpus for the SLM "
        "roster."
    )


def render_forge_status(text: str = "") -> str:
    records = list_forges()
    if not records:
        return (
            "Engel forge ledger: no forges yet. In the main chat, say: "
            "forge code <task>."
        )
    lines = [f"Engel forges ({len(records)} most recent):"]
    for rec in records:
        rounds = rec.get("rounds", [])
        lines.append(
            f"  - [{rec.get('status', '?')}] {str(rec.get('goal', ''))[:80]}  "
            f"(rounds={len(rounds)})"
        )
        if rec.get("ok") and rec.get("artifacts"):
            lines.append(f"      artifacts: {rec['artifacts'][0]} (+{max(0, len(rec['artifacts']) - 1)} more)")
        elif rounds:
            last = rounds[-1]
            for problem in last.get("problems", [])[:1]:
                lines.append(f"      last problem: {str(problem)[:140]}")
    lines.append("Receipts: reports/engel_forge/")
    return "\n".join(lines)


def render_forge_result(receipt: dict[str, Any]) -> str:
    lines = [
        f"Engel Code Forge -- task: {receipt.get('goal', '')}",
        f"Status: {receipt.get('status', '?')}",
    ]
    for round_rec in receipt.get("rounds", []):
        observation = round_rec.get("observation") or {}
        if observation:
            head = (
                f"Round {round_rec.get('round')}: {observation.get('tests_run', 0)} "
                f"test file(s) ran -- "
                + ("GREEN" if observation.get("ok") else f"failed ({round_rec.get('error_class')})")
            )
        else:
            head = f"Round {round_rec.get('round')}: stopped before running ({round_rec.get('error_class', '?')})"
        lines.append(head)
        for problem in (round_rec.get("problems") or [])[:3]:
            lines.append(f"    problem: {str(problem)[:200]}")
    if receipt.get("ok"):
        lines.append("Artifacts (proven by their own tests, never auto-deployed):")
        lines.extend(f"  {path}" for path in receipt.get("artifacts", []))
    if receipt.get("receipt_path"):
        lines.append(f"Receipt: {receipt['receipt_path']}")
    return "\n".join(lines)


_FORGE_PREFIXES = ("forge code", "engel forge code", "engel forge")


def render_forge(text: str = "") -> str:
    low = str(text or "").strip()
    payload = ""
    for prefix in _FORGE_PREFIXES:
        if low.casefold().startswith(prefix):
            payload = low[len(prefix):].strip()
            break
    if not payload:
        return (
            "Usage: forge code <task in plain words>\n" + render_forge_status()
        )
    # The route surface has no model lane attached; forging happens in the
    # main chat where the worker injects the local model as generate_fn.
    return (
        f"Forge task noted: {payload}\n"
        "This surface has no model lane attached. In the main chat, say: "
        f"forge code {payload}\n\n" + render_forge_status()
    )
