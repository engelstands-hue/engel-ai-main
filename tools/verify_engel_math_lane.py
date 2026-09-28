#!/usr/bin/env python3
"""Gate for Engel's deterministic math lane.

Three failure classes this verifier exists to catch, all observed while building:

  1. WRONG-EXPRESSION-FAITHFULLY-VERIFIED — extraction swept clause words into the
     expression ("x^3 - 4x x 2" via implicit multiplication) and the lane then
     correctly verified the wrong math. Verification only proves the answer matches
     the EXTRACTED input, so extraction is battery-tested against exact answers.
  2. INTENT HIJACK — the documented bug class ('training'+'build' co-occurrence).
     Every red-team false-positive trap must stay normal chat, forever.
  3. POLICY DRIFT in the service wiring — math replies routed through the
     humanizer, receipts marked training-eligible, missing depth-0 mapping, or the
     lane placed above the imperative order lanes. All statically enforced here.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LANE = ROOT / "tools" / "engel_math_lane.py"
# The lane is normally exercised through its CLI (below), but the parser-containment checks
# added 2026-08-06 must call parse_expr_safe DIRECTLY -- a subprocess would only tell us the
# lane refused an expression, not whether the parser resolved a forbidden name on the way.
sys.path.insert(0, str(ROOT / "tools"))
import engel_math_lane  # noqa: E402
SERVICE = ROOT / "tools" / "engel_main_server_chat_http_service.py"

CHECKS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    CHECKS.append((name, bool(ok), detail))
    print(("PASS " if ok else "FAIL ") + name + (f"  ({detail})" if detail else ""))


MATH = [
    ("solve 3x + 7 = 25", "x = 6"),
    ("What does x have to be so that 3x + 7 gives 25?", "x = 6"),
    ("integrate x^2 * exp(x)", "(x**2 - 2*x + 2)*exp(x) + C"),
    ("what is the area under e^-x from 0 to infinity", "1"),
    ("is 9973 prime", "prime"),
    ("is 9991 prime", "not prime"),
    ("determinant of [[2,1],[5,3]]", "1"),
    ("differentiate sin(x)*x^2", "x**2*cos(x) + 2*x*sin(x)"),
    ("How steep is the curve x^3 - 4x right at the point where x is 2?", "slope is 8"),
    ("factor x^2 - 5x + 6", "(x - 3)*(x - 2)"),
    ("Rewrite x^2 + 5x + 6 as two brackets multiplied together.", "(x + 2)*(x + 3)"),
    ("what is 2^100", "1267650600228229401496703205376"),
    ("What's (17 percent of 2,340,000)?", "397800"),
    ("As x gets huge, what does (2x + 1)/(x - 3) settle down to?", "2"),
    ("Turn 0.727272 repeating into a plain fraction", "8/11"),
    ("greatest common divisor of 84 and 60", "12"),
    ("lcm of 4 and 6", "12"),
    ("eigenvalues of [[2,0],[0,3]]", "2"),
    ("inverse of the matrix [[2,1],[5,3]]", "[[3, -1], [-5, 2]]"),
    ("simplify (x^2 - 1)/(x - 1)", "x + 1"),
    ("limit of sin(x)/x as x -> 0", "1"),
    ("solve x^2 - 4x + 3 = 0", "1, 3"),
]

# Red-team traps: math-flavored words in Engel's operational vocabulary. Routing
# ANY of these to the math lane is a regression of the documented hijack bug.
FALSE_POSITIVES = [
    "Solve my worker dispatch problem on CT246 — alpha and beta pair fine but gamma times out after 30 seconds.",
    "Integrate the new intent_router SLM into the chat service before Sunday's retrain lands.",
    "How do we differentiate quick-lane replies from big-lane replies in the receipts log?",
    "Factor in the RTX 2070 being 86% full before you schedule the sdxl-turbo image lane.",
    "Simplify the deploy script — it re-pins the manifest twice and the diff is +214/-86 lines.",
    "What was the determinant factor in the 20260701 bridge outage — the codex gate or the chatgpt singleton?",
    "What is the limit on concurrent agents in the meeting room, and can we raise it from 6 to 8?",
    "Is the persona style card a derivative work of the OpenClaw MIT code?",
    "The reverse tunnel maps 8899 -> 24680 and chat is 8765, not 24680 — confirm that before I restart anything.",
    "2 phones failed to pair; the third is on Android 13 so adb push provisioning is blocked.",
    "Upgrade Flutter from 3.19.6 to 3.22.1 — any breaking changes for the main.dart toolRoots merge?",
    "Set tau = 0.62 in the NT-2 drop-in and restart the service.",
    "Is CT246 the prime node for the meeting room now, or is that still the ROG?",
    "ssh root@192.0.2.50 -p 24622 times out — can you check the nftables rules?",
    "The cron expression 0 3 * * 0 — when does that fire, and is it UTC or local?",
    "What does 'exit 1' mean in the verifier output when 76/76 tests pass?",
    "We need to solve for latency here, not throughput — the quick lane is the product priority.",
    "Evaluate whether the canary should block deploy — loss went 1.81 to 0.19, which looks fine to me.",
    "Does the regex ^\\d+\\.\\d+$ match 1.0.12, or do I need a third capture group?",
    "Divide the backlog between the ROG worker and CT246, then sum up what's left in the Tasks panel.",
    # training-material prompts must reach the MODEL lanes, not the math lane
    "Help me start working through limits, derivatives, and integrals Engel can cross-check deterministically. Separate confirmed inputs from open inputs.",
]


def run_lane(prompt: str) -> dict:
    out = subprocess.run(
        [sys.executable, str(LANE), prompt],
        capture_output=True, text=True, timeout=120, check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    try:
        return json.loads(out.stdout.strip().splitlines()[-1])
    except Exception:  # noqa: BLE001
        return {"parse_error": (out.stdout or out.stderr)[-200:]}


def main() -> int:
    try:
        import sympy  # noqa: F401
        have_sympy = True
    except ImportError:
        have_sympy = False
    check("sympy_available_to_this_interpreter", have_sympy,
          "run under runtime\\python310 (ROG) or the deep-reasoning venv (CT)")

    if have_sympy:
        for prompt, expect in MATH:
            r = run_lane(prompt)
            ok = bool(r.get("ok")) and bool(r.get("verified")) and expect in str(r.get("result_text", ""))
            check(f"math[{prompt[:44]}]", ok,
                  "" if ok else f"got {str(r.get('result_text', r.get('status', r)))[:80]}")
        for prompt in FALSE_POSITIVES:
            r = run_lane(prompt)
            check(f"not_math[{prompt[:44]}]", not r.get("math_request"),
                  "" if not r.get("math_request") else f"HIJACKED as {r.get('operation')}")

    # ---- math REASONING routing (deepseek-r1 specialist) --------------------
    sys.path.insert(0, str(ROOT / "tools"))
    from engel_math_lane import detect_math_reasoning_request

    reasoning_yes = [
        "I have 60 meters of fence and a wall for one side - what rectangle gives the biggest area?",
        "Rolling two dice, what is the chance the total comes to at least 10?",
        "A 200-liter tank drains at 3 liters a minute and there are 140 liters in it now - how long until it is empty?",
        "I put 2,500 in at 4.5% compounded monthly - what is it worth after 6 years?",
        "Training loss went from 1.81 down to 0.19 - what percent drop is that, exactly?",
        "Our GPU pushes 42 tokens a second and the transcript is 18,500 tokens - how many minutes will generation take?",
    ]
    reasoning_no = [
        "What does 'exit 1' mean in the verifier output when 76/76 tests pass?",
        "The cron expression 0 3 * * 0 - when does that fire, and is it UTC or local?",
        "Upgrade Flutter from 3.19.6 to 3.22.1 - any breaking changes for the main.dart toolRoots merge?",
        "What is the limit on concurrent agents in the meeting room, and can we raise it from 6 to 8?",
        "Is CT246 the prime node for the meeting room now, or is that still the ROG?",
        "Help me start checking Engel's probability and statistics claims against simulation and exact enumeration. Separate confirmed inputs from open inputs.",
    ]
    for prompt in reasoning_yes:
        check(f"reasoning_yes[{prompt[:40]}]", detect_math_reasoning_request(prompt))
    for prompt in reasoning_no:
        check(f"reasoning_no[{prompt[:40]}]", not detect_math_reasoning_request(prompt))

    # ---- service wiring policy (static, source-of-truth on the ROG copy) ----
    text = SERVICE.read_text(encoding="utf-8", errors="replace")
    check("service_has_math_lane_handler", "_math_lane_turn" in text)
    check("service_depth_map_has_ct_math_lane",
          bool(re.search(r'"ct_math_lane":\s*0', text)),
          "depth-0 mapping prevents telemetry/SFT depth skew")
    order = [text.find("training_turn = _training_request_turn"),
             text.find("math_turn = _math_lane_turn"),
             text.find("install_turn = _model_install_action")]
    check("dispatch_order_training_then_math_then_install",
          -1 not in order and order[0] < order[1] < order[2],
          f"offsets {order} — imperative order lanes must outrank math on ties")
    handler = text.split("def _math_lane_turn", 1)[-1].split("\ndef ", 1)[0]
    check("math_receipt_never_training_eligible",
          '"training_sample_eligible": False' in handler
          and '"persistent_chat_memory_training_eligible": False' in handler,
          "receipts are the SFT corpus; deterministic template voice must stay out")
    check("math_receipt_declares_zero_inference", '"runs_inference": False' in handler)
    check("math_reply_not_humanized", "_apply_chat_humanizer" not in handler,
          "a style rewrite on exact symbolic output is the gate-collision bug")
    check("math_lane_fails_open", "return None" in handler and "except Exception" in handler,
          "any lane failure must fall through to the model lanes, never break chat")
    check("math_lane_uses_training_venv", "_TRAIN_VENV_PY" in handler,
          "CT system python3 has no sympy")
    check("math_lane_subprocess_bounded", "timeout=20" in handler)

    # reasoning specialist policy
    check("service_has_reasoning_handler", "_math_reasoning_receipt" in text)
    check("reasoning_depth_mapped_big_lane",
          bool(re.search(r'"ct_math_reasoning_lane":\s*2', text)))
    check("reasoning_dispatch_after_deterministic",
          text.find("math_turn = _math_lane_turn") <
          text.find("needs_math_reasoning") <
          text.find("install_turn = _model_install_action"),
          "exact sympy first; the model only gets what sympy declined")
    reasoner = text.split("def _math_reasoning_receipt", 1)[-1].split("\ndef ", 1)[0]
    check("reasoning_answer_contract", '"ANSWER:" not in visible' in reasoner,
          "a thought-only R1 response must fall through, not ship half a derivation")
    check("reasoning_strips_think_blocks", "_MATH_REASON_THINK_RE" in reasoner)
    check("reasoning_no_system_prompt", 'extra_system=""' in reasoner,
          "R1 distills degrade on system prompts (ornith-9B gotcha class)")
    check("reasoning_output_untrusted",
          '"model_output_trusted": False' in reasoner
          and '"training_sample_eligible": False' in reasoner)
    check("reasoning_fails_open", "return None" in reasoner and "except Exception" in reasoner)
    check("reasoning_defaults_to_deepseek", "deepseek-r1-distill-qwen-7b" in reasoner,
          "operator direction 2026-07-30: strongest model for math")

    # --- parser containment (2026-08-06) -----------------------------------------
    # parse_expr_safe eats untrusted text: chat prompts and model-generated replies.
    # Its _FORBIDDEN_RE is a BLOCKLIST, and sympy's parse_expr used to inject the whole
    # sympy namespace plus builtins via the default global_dict -- so arbitrary execution
    # was reachable without typing a banned word:
    #   parse_expr_safe("globals()[(chr(101)+chr(118)+chr(97)+chr(108))](chr(50)+chr(43)+chr(50))")
    #   returned 4, i.e. eval("2+2") ran. An explicit global_dict is what closes it.
    # Both directions are asserted: a leak here is remote code execution, and an
    # over-tight whitelist silently breaks the live math chat lane.
    def _rejects(expression: str) -> bool:
        try:
            engel_math_lane.parse_expr_safe(expression)
        except Exception:
            return True
        return False

    for probe in (
        "globals()",
        "globals()[(chr(101)+chr(118)+chr(97)+chr(108))](chr(50)+chr(43)+chr(50))",
        "getattr(pi, chr(110))",
        "Lambda(x, x)",
    ):
        check(f"parser_rejects[{probe[:24]}]", _rejects(probe),
              "an unlisted name must raise, never resolve -- global_dict is the control")

    # An unlisted FUNCTION name must degrade to an inert symbol rather than resolve to the
    # real callable. zeta(2) must not become pi**2/6; it becomes 2*zeta, which is harmless.
    try:
        inert = str(engel_math_lane.parse_expr_safe("zeta(2)"))
    except Exception:
        inert = "raised"
    check("unlisted_function_stays_inert", "pi" not in inert,
          f"zeta(2) must not evaluate to the real sympy zeta; got {inert!r}")

    # Stacked exponentiation COMPUTES during parse and never returns -- measured hanging
    # past 45s from a plain chat prompt. The shape, not the caret count, is the signature:
    # 9^9^9^9 has three carets and hangs; 2^3 + 4^2 has two and is trivial.
    for hazard in ("9^9^9^9", "2^2^2^2^2", "99^9999"):
        check(f"parser_refuses_explosive[{hazard}]", _rejects(hazard),
              "an expression that cannot evaluate in bounded time must be refused, not attempted")

    for expression, expected in (
        ("2*x + 1", "2*x + 1"),
        ("sqrt(16)", "4"),
        ("sin(pi/2)", "1"),
        ("factorial(5)", "120"),
        ("binomial(5,3)", "10"),
        ("x^2 - 5*x + 6", "x**2 - 5*x + 6"),
        # Implicit multiplication against a parenthesis. sympy rewrites an unlisted name
        # before "(" into Function(...), so leaving Function out of the whitelist broke ALL
        # of these with "NameError: name 'Function' is not defined" -- ordinary school
        # algebra, dead in the live chat lane, and the first fixture set missed it entirely
        # because every case happened to use explicit operators.
        ("3x(x+2)", "3*x*(x + 2)"),
        ("x(x+1)", "x*(x + 1)"),
        ("x(x-2)", "x*(x - 2)"),
        ("2^100", "1267650600228229401496703205376"),
    ):
        try:
            got = str(engel_math_lane.parse_expr_safe(expression))
        except Exception as exc:
            got = f"RAISED {type(exc).__name__}"
        check(f"parser_keeps[{expression}]", got == expected,
              f"legitimate maths must still parse; got {got!r} wanted {expected!r}")

    failed = [name for name, ok, _ in CHECKS if not ok]
    print(f"\n{len(CHECKS) - len(failed)}/{len(CHECKS)} checks passed")
    if failed:
        print("FAILED: " + ", ".join(failed[:8]))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
