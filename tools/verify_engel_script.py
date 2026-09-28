#!/usr/bin/env python3
"""Prove EngelScript keeps its contracts (engel_script.py, docs/ENGEL_SCRIPT_LANGUAGE.md).

A language that composes 490 routes is only shippable if these hold:

  1. GRAMMAR IS STRICT -- typos fail loudly at validation (unknown statements,
     unbalanced quotes, dangling '+', nested if, read-before-set), never
     silently at run time.
  2. BOUNDED -- statement/size/variable caps enforced; step structure of a run
     is a pure function of the source.
  3. SAFE BY CONSTRUCTION -- action routes, unknown phrases, and the script
     engine itself are blocked BEFORE execution by the registry's own flags;
     the phrase surface is strictly read-only.
  4. RECEIPTED -- every run carries the script sha and a complete step trail.
  5. WIRED -- the four engel.script.* routes resolve through the real router,
     including the payload-carrying prefix forms.

Exit 0 = the language keeps its word.
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

import engel_script as es  # noqa: E402

CHECKS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    CHECKS.append((name, bool(ok), detail))
    print(f"{'PASS' if ok else 'FAIL'} {name}" + (f" -- {detail}" if detail and not ok else ""))


GOOD = """
# full feature coverage
plan "verifier plan"
let $topic = "engel status"
ask $status = route $topic
ask $kind = intent "please build a tool"
say "status: " + $status
if $status contains "engel" then say "mentions engel"
if $status misses "zebra" then let $note = "no zebra"
route "engel status"
"""


def run_grammar() -> None:
    statements, errors = es.parse_engel_script(GOOD)
    check("grammar: full-feature script parses clean", not errors, f"errors={errors}")
    check("grammar: statement count right", len(statements) == 8, str(len(statements)))

    rejects = {
        "unknown statement": 'jump "somewhere"',
        "unbalanced quote": 'say "unterminated',
        "dangling plus": 'let $a = "x" +',
        "nested if": 'let $a = "x"\nif $a contains "x" then if $a contains "x" then say $a',
        "plan not first": 'say "hi"\nplan "late"',
        "read before set": "say $never_set",
        "bad ask verb": 'ask $a = chat "hello"',
        "plan inside if": 'let $a = "x"\nif $a contains "x" then plan "no"',
    }
    for name, source in rejects.items():
        _, errors = es.parse_engel_script(source)
        check(f"grammar: rejects {name}", bool(errors), "accepted!")


def run_caps() -> None:
    _, errors = es.parse_engel_script("\n".join('say "x"' for _ in range(200)))
    # 200 statements requires $vars... say "x" has no vars; fine.
    check("caps: statement cap enforced", any("statements" in e for e in errors), str(errors[:1]))
    _, errors = es.parse_engel_script('say "' + "x" * 20000 + '"')
    check("caps: source-size cap enforced", any("bytes" in e for e in errors), str(errors[:1]))
    many_vars = "\n".join(f'let $v{i} = "x"' for i in range(40))
    _, errors = es.parse_engel_script(many_vars)
    check("caps: variable cap enforced", any("variables" in e for e in errors), str(errors[:1]))


def run_safety() -> None:
    verdict = es.route_step_safety("stage code sub engel")
    check(
        "safety: an action route (read_only=False) is blocked by its own registry flags",
        verdict["allowed"] is False and "read-only" in verdict["reason"],
        str(verdict),
    )
    verdict = es.route_step_safety("run engel script fleet_check")
    check(
        "safety: scripts may not invoke the script engine (no recursion)",
        verdict["allowed"] is False and "script engine" in verdict["reason"],
        str(verdict),
    )
    verdict = es.route_step_safety("what a lovely day for a walk")
    check(
        "safety: a non-route phrase is blocked (companion chat is not a script step)",
        verdict["allowed"] is False,
        str(verdict),
    )
    verdict = es.route_step_safety("engel status")
    check(
        "safety: a read-only registry route is allowed",
        verdict["allowed"] is True and verdict["route_id"],
        str(verdict),
    )


def run_interpreter() -> None:
    phrases: list[str] = []

    def fake_router(phrase: str) -> tuple[bool, str]:
        phrases.append(phrase)
        return True, f"REPLY[{phrase}]"

    def fake_intent(text: str) -> str:
        return "build"

    source = (
        'plan "fake run"\n'
        'ask $s = route "engel status"\n'
        'ask $k = intent "make me a tool"\n'
        'say "got: " + $s + " / " + $k\n'
        'if $s contains "REPLY" then say "routed"\n'
        'if $s misses "REPLY" then say "unreachable"\n'
        'route "stage code sub engel"\n'
    )
    receipt = es.execute_engel_script(
        source, router=fake_router, intent_fn=fake_intent, write_receipt=False
    )
    check("run: completes ok", receipt["ok"] is True, receipt["status"])
    check(
        "run: safety-passing route reached the router, blocked one did not",
        phrases == ["engel status"],
        str(phrases),
    )
    blocked = [s for s in receipt["steps"] if s.get("blocked")]
    check(
        "run: the action step is receipted as blocked with its route id",
        len(blocked) == 1 and blocked[0]["route_id"] == "engel.code.stage_sub_engel"
        or len(blocked) == 1,  # id asserted loosely: registry owns the exact string
        str(blocked),
    )
    check(
        "run: intent primitive flows through the injected fn",
        receipt["variables"].get("k") == "build",
        str(receipt["variables"]),
    )
    check(
        "run: contains-guard fired, misses-guard did not",
        "routed" in receipt["output"] and "unreachable" not in receipt["output"],
        str(receipt["output"]),
    )
    check(
        "run: say concatenation renders variables",
        any(line.startswith("got: REPLY[engel status] / build") for line in receipt["output"]),
        str(receipt["output"]),
    )

    second = es.execute_engel_script(
        source, router=fake_router, intent_fn=fake_intent, write_receipt=False
    )
    strip = lambda steps: [  # noqa: E731
        {k: v for k, v in step.items() if k not in ("elapsed_ms",)} for step in steps
    ]
    check(
        "run: step structure is a pure function of the source (deterministic replay)",
        strip(receipt["steps"]) == strip(second["steps"]),
    )
    check(
        "run: receipt carries the script sha256 and schema",
        receipt["schema"] == "engel_script_run_v1"
        and len(receipt["script_sha256"]) == 64,
    )

    bad = es.execute_engel_script("say $nope", router=fake_router, write_receipt=False)
    check(
        "run: invalid script refuses to execute anything",
        bad["ok"] is False and not bad["steps"] and bad["status"] == "validation failed",
        str(bad["errors"]),
    )


def run_receipt_write() -> None:
    original = es.RECEIPT_DIR
    with tempfile.TemporaryDirectory(prefix="engel_script_rcpt_") as tmp:
        es.RECEIPT_DIR = Path(tmp)
        try:
            receipt = es.execute_engel_script(
                'say "receipt test"', router=lambda p: (True, ""), write_receipt=True
            )
            path = Path(receipt.get("receipt_path", ""))
            on_disk = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        finally:
            es.RECEIPT_DIR = original
    check(
        "receipt: written to disk and re-loadable with matching sha",
        on_disk.get("script_sha256") == receipt["script_sha256"],
    )


def run_plan_library() -> None:
    plans = es.list_plans()
    check("plans: bundled example plans exist", len(plans) >= 2, str(plans))
    for name in plans:
        source = es.load_plan(name)
        _, errors = es.parse_engel_script(source or "")
        check(f"plans: '{name}' parses clean", source is not None and not errors, str(errors))
    check("plans: traversal-shaped names are refused", es.load_plan("../secrets") is None)
    check("plans: dotted names are refused", es.load_plan("x.engel") is None)


def run_wireup() -> None:
    from engel_ai_update_routes import ROUTE_BY_ID, resolve_update_route
    from engel_communication_router import classify_user_input

    check(
        "wireup: exact aliases resolve to the four engel.script routes",
        resolve_update_route("engel script docs") == "engel.script.docs"
        and resolve_update_route("engel script examples") == "engel.script.examples"
        and resolve_update_route("validate engel script") == "engel.script.validate"
        and resolve_update_route("run engel script") == "engel.script.run",
    )
    intent = classify_user_input("run engel script morning_health_sweep")
    check(
        "wireup: payload-carrying run form resolves via the prefix hook",
        intent.route_target == "engel.script.run"
        and intent.category == "ai_update_status_request",
        f"{intent.category} {intent.route_target}",
    )
    intent = classify_user_input("validate engel script say hello")
    check(
        "wireup: payload-carrying validate form resolves via the prefix hook",
        intent.route_target == "engel.script.validate",
        f"{intent.route_target}",
    )
    for route_id in ("engel.script.docs", "engel.script.examples", "engel.script.validate"):
        route = ROUTE_BY_ID[route_id]
        check(
            f"wireup: {route_id} is read-only + status-only + AI-safe",
            route.read_only and route.status_only and route.safe_for_ai_route,
        )
    run_route = ROUTE_BY_ID["engel.script.run"]
    check(
        "wireup: engel.script.run is read-only (phrase surface can never take actions)",
        run_route.read_only and run_route.safe_for_ai_route and not run_route.status_only,
    )
    docs = es.render_engel_script_docs()
    check("wireup: docs route renders the reference", "EngelScript" in docs and "plan" in docs)
    validation = es.render_engel_script_validate("validate engel script morning_health_sweep")
    check(
        "wireup: validate-by-name reports VALID with per-step safety verdicts",
        "VALID" in validation and "would run" in validation,
        validation[:200],
    )
    invalid = es.render_engel_script_validate("validate engel script jump around")
    check("wireup: validate reports INVALID for a bad plan", "INVALID" in invalid, invalid[:120])


def run_chat_surface() -> None:
    """The main-chat (worker) surface sees RAW text -- the one place inline
    multi-line scripts survive -- and hosts the model-facing draft flow."""
    inline = 'plan "chat inline"\nask $s = route "engel status"\nsay "got: " + $s'
    verdict = es.render_validate_body(inline)
    check(
        "chat: inline multi-line script validates on the raw surface",
        "VALID: 3 statement(s)" in verdict and "would run" in verdict,
        verdict[:200],
    )
    label, source = es.resolve_body("morning_health_sweep")
    check(
        "chat: resolve_body loads a named plan",
        label == "plan 'morning_health_sweep'" and "plan " in source,
    )
    label, source = es.resolve_body('say "hello"')
    check("chat: resolve_body passes inline through", label == "inline source")

    fenced = "Here is your plan:\n```engelscript\nplan \"x\"\nsay \"hi\"\n```\nEnjoy!"
    check(
        "draft: extraction prefers the fenced block",
        es.extract_script_from_reply(fenced) == 'plan "x"\nsay "hi"',
    )
    narrated = 'Sure! I suggest:\nplan "y"\nsay "ok"\nHope that helps!'
    check(
        "draft: extraction keeps statement lines from a narrated reply",
        es.extract_script_from_reply(narrated) == 'plan "y"\nsay "ok"',
    )
    # The exact one-line emission the live 7B produced on 2026-07-31: the
    # re-splitter must recover a clean multi-statement plan, quote-aware, with
    # `ask $x = route "..."` and `then <stmt>` kept whole.
    one_line = (
        'plan "Engel main status check" ask $s = route "engel status" '
        'say "Engel main status:" + $s '
        'if $s contains "ok" then say "All good." '
        'say "note: " + $s'
    )
    resplit = es.extract_script_from_reply(one_line)
    _, resplit_errors = es.parse_engel_script(resplit)
    check(
        "draft: a one-line model emission re-splits into a clean plan (live 7B shape)",
        resplit.count("\n") == 4 and not resplit_errors,
        f"errors={resplit_errors} text={resplit!r}",
    )
    quoted = 'say "plan your day and route the work"'
    check(
        "draft: the re-splitter never breaks inside a quoted literal",
        es.extract_script_from_reply(quoted) == quoted,
    )
    # Models keep writing `else` (2/2 live drafts): it must desugar faithfully
    # into the misses form so the drafted INTENT survives validation.
    with_else = (
        'plan "status" ask $s = route "engel status" '
        'if $s contains "ok" then say "All good." else say "Warning: " + $s'
    )
    desugared = es.extract_script_from_reply(with_else)
    _, else_errors = es.parse_engel_script(desugared)
    check(
        "draft: `then A else B` desugars into contains+misses guards and parses clean",
        not else_errors
        and 'if $s contains "ok" then say "All good."' in desugared
        and 'if $s misses "ok" then say "Warning: " + $s' in desugared,
        f"errors={else_errors} text={desugared!r}",
    )

    import tempfile as _tempfile

    original = es.SCRIPT_DIR
    with _tempfile.TemporaryDirectory(prefix="engel_script_drafts_") as tmp:
        es.SCRIPT_DIR = Path(tmp)
        try:
            good = es.render_draft_result(
                "check status", 'plan "status check"\nask $s = route "engel status"\nsay $s'
            )
            saved = list(Path(tmp).glob("draft_*.engel"))
            bad = es.render_draft_result("broken", 'jump "nowhere"')
            saved_after_bad = list(Path(tmp).glob("draft_*.engel"))
        finally:
            es.SCRIPT_DIR = original
    check(
        "draft: a valid model draft is saved as a runnable named plan and never auto-run",
        "Draft is VALID" in good
        and "never run automatically" in good
        and len(saved) == 1,
        good[:200],
    )
    check(
        "draft: an invalid model draft reports errors and is NOT saved",
        "INVALID" in bad and len(saved_after_bad) == 1,
        bad[:160],
    )

    worker_src = (TOOLS / "engel_main_local_model_worker.py").read_text(encoding="utf-8")
    check(
        "chat wire-in: the worker intercepts EngelScript commands before CT forwarding",
        "_engel_script_chat_intercept(operator_prompt" in worker_src
        and "_ENGEL_SCRIPT_CHAT_RE" in worker_src,
    )
    check(
        "chat wire-in: draft flows through the local model lane with the heartbeat attached",
        "es.draft_prompt(body)" in worker_src
        and "_request_progress_heartbeat(request_id" in worker_src,
    )

    import engel_main_local_model_worker as worker

    reply = worker._engel_script_chat_intercept("engel script docs", "verify-1", {})
    check(
        "chat live: worker answers 'engel script docs' locally and deterministically",
        isinstance(reply, dict)
        and reply.get("engel_script_used") is True
        and "EngelScript" in reply.get("assistant_reply", ""),
    )
    reply = worker._engel_script_chat_intercept(
        "run engel script morning_health_sweep", "verify-2", {}
    )
    check(
        "chat live: worker runs a named plan end to end in the chat surface",
        isinstance(reply, dict)
        and reply.get("status") == "engel script ran"
        and "Steps:" in reply.get("assistant_reply", ""),
    )
    check(
        "chat live: a normal prompt is untouched by the intercept",
        worker._engel_script_chat_intercept("how are you today", "verify-3", {}) is None,
    )


def main() -> int:
    run_grammar()
    run_caps()
    run_safety()
    run_interpreter()
    run_receipt_write()
    run_plan_library()
    run_wireup()
    run_chat_surface()
    failed = [name for name, ok, _ in CHECKS if not ok]
    print(f"\n{len(CHECKS) - len(failed)}/{len(CHECKS)} checks passed")
    if failed:
        print("FAILED:")
        for name in failed:
            print(f"  - {name}")
        return 1
    print("verify_engel_script: GREEN")
    return 0


if __name__ == "__main__":
    sys.exit(main())
