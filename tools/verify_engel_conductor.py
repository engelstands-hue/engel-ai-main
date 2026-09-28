#!/usr/bin/env python3
"""Prove the Conductor closes the loop Engel never had.

Before this module (measured 2026-07-31): drafts ended with "Drafts never run
automatically.", no code anywhere consumed a run receipt to produce a next
step, ``govern("allow", ...)`` had zero production callers, and the only
cross-turn state in the chat path was one in-memory variable dropped on any
reply that was not yes/no.

What must hold for the Conductor to be trustworthy:

  1. LOOP -- a goal conducts end to end: saved plans run; drafted plans are
     validated, run, OBSERVED, and repaired once from their own receipt.
  2. BOUNDED -- an always-broken drafter stops at MAX_ROUNDS; the repair is
     Governor-escalation-gated; no unbounded loops.
  3. PERSISTENT -- goals land in the ledger, survive re-entry, and fold their
     recorded problems into the next draft.
  4. GRANTS DEFAULT OFF -- without the operator grants file, allow_actions
     changes nothing; with it, exactly the listed route ids run, each step
     carrying a Governor allow verdict; belts (slow-lane, script-engine,
     conductor recursion, Governor-down) all still refuse.
  5. WIRED -- routes resolve (exact aliases beat the payload prefix), the
     registry dispatches the renderers, and the chat worker intercept answers
     locally without a model.

Exit 0 = the loop closes.
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

import engel_conductor as ec  # noqa: E402
import engel_script as es  # noqa: E402

CHECKS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    CHECKS.append((name, bool(ok), detail))
    print(f"{'PASS' if ok else 'FAIL'} {name}" + (f" -- {detail}" if detail and not ok else ""))


def _fake_router(phrase: str):
    return True, f"REPLY[{phrase}]"


VALID_PLAN = (
    'plan "verify loop"\n'
    'ask $s = route "engel status"\n'
    'say "status: " + $s\n'
)
INVALID_PLAN = "route\n"  # bare route: parse error
BLOCKED_STEP_PLAN = (
    'plan "verify blocked"\n'
    'route "stage code sub engel"\n'  # real ACTION route -> blocked read-only
    'say "tried"\n'
)


def run_loop() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        old = (ec.GOAL_DIR, ec.RECEIPT_DIR, es.SCRIPT_DIR, es.RECEIPT_DIR)
        ec.GOAL_DIR = Path(tmp) / "goals"
        ec.RECEIPT_DIR = Path(tmp) / "conducts"
        es.SCRIPT_DIR = Path(tmp) / "plans"
        es.RECEIPT_DIR = Path(tmp) / "runs"
        try:
            # 1. A goal that names a saved plan conducts it directly.
            es.SCRIPT_DIR.mkdir(parents=True)
            (es.SCRIPT_DIR / "fleet_check_plan.engel").write_text(
                VALID_PLAN, encoding="utf-8"
            )
            receipt = ec.conduct("fleet_check_plan", router=_fake_router)
            check(
                "loop: a saved plan conducts to done in one round",
                receipt["status"] == "done"
                and receipt["ok"] is True
                and len(receipt["rounds"]) == 1,
                receipt["status"],
            )
            check(
                "loop: the run receipt path is captured in the round",
                bool(receipt["rounds"][0].get("run_receipt_path")),
            )
            verdict = receipt["rounds"][0].get("allow_verdict") or {}
            check(
                "governor: the conduct-level allow class is finally called in production",
                verdict.get("rule_id") == "allow.gate.conductor_run"
                and verdict.get("outcome") == "allow",
                str(verdict),
            )
            check(
                "ledger: the conducted goal persists with its receipt",
                (ec.GOAL_DIR / f"{ec.goal_slug('fleet_check_plan')}.json").is_file(),
                str(sorted(p.name for p in ec.GOAL_DIR.glob("*.json"))),
            )

            # 2. Unknown goal, no drafter: honest degradation, never a crash.
            receipt = ec.conduct("summarize the weather on mars", router=_fake_router)
            check(
                "loop: no drafter + no saved plan = honest 'no planner available'",
                receipt["status"] == "no planner available",
                receipt["status"],
            )

            # 3. Repair from VALIDATION: invalid first draft, valid second.
            drafts = []

            def _flaky_drafter(prompt: str) -> str:
                drafts.append(prompt)
                return INVALID_PLAN if len(drafts) == 1 else VALID_PLAN

            receipt = ec.conduct(
                "check engel and report", draft_fn=_flaky_drafter, router=_fake_router
            )
            check(
                "repair: an invalid draft is repaired once and then succeeds",
                receipt["status"] == "done"
                and len(receipt["rounds"]) == 2
                and receipt["rounds"][0].get("validate_errors")
                and receipt["rounds"][1].get("observation", {}).get("ok") is True,
                f"status={receipt['status']} rounds={len(receipt['rounds'])}",
            )
            check(
                "repair: the repair prompt carries the validator's own errors",
                len(drafts) == 2 and "What went wrong" in drafts[1],
            )
            esc = receipt["rounds"][0].get("escalate_verdict") or {}
            check(
                "governor: each repair round is escalation-gated and receipted",
                esc.get("outcome") is True and esc.get("rule_id") == "escalate.granted",
                str(esc),
            )

            # 4. Repair from OBSERVATION: a blocked action step is read back
            # from the run receipt and repaired -- the read-back that did not
            # exist anywhere in the system.
            drafts.clear()

            def _observing_drafter(prompt: str) -> str:
                drafts.append(prompt)
                return BLOCKED_STEP_PLAN if len(drafts) == 1 else VALID_PLAN

            receipt = ec.conduct(
                "get a fleet code job staged", draft_fn=_observing_drafter, router=_fake_router
            )
            first_obs = receipt["rounds"][0].get("observation", {})
            check(
                "observe: a blocked step becomes a problem the next round repairs",
                receipt["status"] == "done"
                and len(receipt["rounds"]) == 2
                and first_obs.get("blocked_routes") == 1
                and any("blocked" in p for p in first_obs.get("problems", [])),
                f"status={receipt['status']} obs={first_obs}",
            )
            check(
                "observe: the repair prompt quotes the blocked step's reason",
                len(drafts) == 2 and "blocked" in drafts[1],
            )

            # 5. Bounded: an always-broken drafter stops at MAX_ROUNDS.
            calls = {"n": 0}

            def _broken_drafter(prompt: str) -> str:
                calls["n"] += 1
                return INVALID_PLAN

            receipt = ec.conduct(
                "a goal that cannot plan", draft_fn=_broken_drafter, router=_fake_router
            )
            check(
                "bounded: an always-invalid drafter stops at MAX_ROUNDS",
                receipt["status"] == "plan invalid"
                and len(receipt["rounds"]) == ec.MAX_ROUNDS
                and calls["n"] == ec.MAX_ROUNDS,
                f"status={receipt['status']} draft_calls={calls['n']}",
            )

            # 6. Persistence: continue_goal re-enters with history folded in.
            drafts.clear()

            def _history_drafter(prompt: str) -> str:
                drafts.append(prompt)
                return VALID_PLAN

            resumed = ec.continue_goal(
                "a goal that cannot plan", draft_fn=_history_drafter, router=_fake_router
            )
            check(
                "ledger: continue_goal re-enters a stored goal and can finish it",
                resumed["status"] == "done",
                resumed["status"],
            )
            check(
                "ledger: the re-entry draft carries the goal's recorded problems",
                drafts and "What went wrong" in drafts[0],
            )
            check(
                "ledger: an unknown slug is an honest error, not a fresh goal",
                ec.continue_goal("never_seen_before_goal")["status"] == "unknown goal",
            )
            check(
                "ledger: the goal ledger renders with statuses and slugs",
                "fleet_check_plan" in ec.render_goal_status()
                and "[done]" in ec.render_goal_status(),
            )
        finally:
            ec.GOAL_DIR, ec.RECEIPT_DIR, es.SCRIPT_DIR, es.RECEIPT_DIR = old


NARRATED_PLAN = 'plan "check the fleet"\nsay "the fleet is healthy"\n'


def run_evidence() -> None:
    """A conduct may only claim success on EVIDENCE. (2026-08-01 review) A
    plan that ran zero routes was reported done/ok -- exactly what small local
    models emit when they narrate instead of planning -- so Engel claimed a
    goal was achieved having checked nothing, and the repair round that exists
    to catch that never fired."""
    with tempfile.TemporaryDirectory() as tmp:
        old = (ec.GOAL_DIR, ec.RECEIPT_DIR, es.SCRIPT_DIR, es.RECEIPT_DIR)
        ec.GOAL_DIR = Path(tmp) / "goals"
        ec.RECEIPT_DIR = Path(tmp) / "conducts"
        es.SCRIPT_DIR = Path(tmp) / "plans"
        es.RECEIPT_DIR = Path(tmp) / "runs"
        try:
            receipt = ec.conduct(
                "narrated goal",
                draft_fn=lambda _p: NARRATED_PLAN,
                router=_fake_router,
                max_rounds=1,
            )
            check(
                "evidence: a plan that executes ZERO routes is never 'done'",
                receipt["ok"] is False and receipt["status"] != "done",
                receipt["status"],
            )
            check(
                "evidence: the receipt says plainly that nothing was proven",
                any(
                    "executed no routes" in p
                    for p in receipt["rounds"][0]["observation"]["problems"]
                ),
                str(receipt["rounds"][0]["observation"]["problems"]),
            )
            # And a plan that DOES run a route still succeeds.
            receipt = ec.conduct(
                "real goal",
                draft_fn=lambda _p: 'ask $s = route "engel status"\nsay $s\n',
                router=_fake_router,
                max_rounds=1,
            )
            check(
                "evidence: a plan that really runs a route still forges through to done",
                receipt["ok"] is True and receipt["status"] == "done",
                receipt["status"],
            )
        finally:
            ec.GOAL_DIR, ec.RECEIPT_DIR, es.SCRIPT_DIR, es.RECEIPT_DIR = old


def run_ledger_robustness() -> None:
    long_a = "review the android worker fleet health and report the results for alpha"
    long_b = "review the android worker fleet health and report the results for beta"
    check(
        "ledger: two long goals that share a 60-char prefix get DISTINCT slugs",
        ec.goal_slug(long_a) != ec.goal_slug(long_b),
        f"{ec.goal_slug(long_a)} vs {ec.goal_slug(long_b)}",
    )
    check(
        "ledger: a slug round-trips through goal_slug unchanged",
        ec.goal_slug(ec.goal_slug(long_a)) == ec.goal_slug(long_a),
        ec.goal_slug(ec.goal_slug(long_a)),
    )
    with tempfile.TemporaryDirectory() as tmp:
        old = (ec.GOAL_DIR, ec.RECEIPT_DIR, es.SCRIPT_DIR, es.RECEIPT_DIR)
        ec.GOAL_DIR = Path(tmp) / "goals"
        ec.RECEIPT_DIR = Path(tmp) / "conducts"
        es.SCRIPT_DIR = Path(tmp) / "plans"
        es.RECEIPT_DIR = Path(tmp) / "runs"
        try:
            ec.GOAL_DIR.mkdir(parents=True)
            slug = ec.goal_slug("corrupt goal")
            (ec.GOAL_DIR / f"{slug}.json").write_text(
                json.dumps(
                    {
                        "schema": "engel_goal_v1",
                        "slug": slug,
                        "goal": "corrupt goal",
                        "rounds_spent": "many",
                        "conducts": "not-a-list",
                        "last_problems": None,
                    }
                ),
                encoding="utf-8",
            )
            receipt = ec.conduct("corrupt goal", router=_fake_router, max_rounds=1)
            check(
                "ledger: a hand-corrupted record degrades instead of raising",
                isinstance(receipt, dict) and receipt.get("status"),
                str(receipt)[:120],
            )
            resumed = ec.continue_goal("corrupt goal", router=_fake_router)
            check(
                "ledger: continue_goal survives a corrupted record too",
                isinstance(resumed, dict) and resumed.get("status"),
                str(resumed)[:120],
            )
        finally:
            ec.GOAL_DIR, ec.RECEIPT_DIR, es.SCRIPT_DIR, es.RECEIPT_DIR = old


def run_grants() -> None:
    action_phrase_plan = 'route "stage code sub engel"\n'
    with tempfile.TemporaryDirectory() as tmp:
        old_grants, old_receipts = es.GRANTS_PATH, es.RECEIPT_DIR
        es.GRANTS_PATH = Path(tmp) / "grants.json"
        es.RECEIPT_DIR = Path(tmp) / "runs"
        try:
            # Default OFF: no grants file -> allow_actions changes nothing.
            receipt = es.execute_engel_script(
                action_phrase_plan, allow_actions=True, router=_fake_router,
                write_receipt=False,
            )
            step = receipt["steps"][0]
            check(
                "grants: absent grants file = blocked even with allow_actions=True",
                step.get("blocked") is True
                and "grants file" in step.get("grant_denied_reason", ""),
                str(step),
            )
            check(
                "grants: the receipt records the mode honestly",
                receipt["mode"] == "action_grants_enabled"
                and receipt["allow_actions_requested"] is True,
            )

            # Operator grant + Governor allow: exactly this route id runs.
            es.GRANTS_PATH.write_text(
                json.dumps({"granted_route_ids": ["engel.code.stage_sub_engel"]}),
                encoding="utf-8",
            )
            phrases: list[str] = []

            def _capture_router(phrase: str):
                phrases.append(phrase)
                return True, "STAGED"

            receipt = es.execute_engel_script(
                action_phrase_plan, allow_actions=True, router=_capture_router,
                write_receipt=False,
            )
            step = receipt["steps"][0]
            check(
                "grants: a granted route id runs and reaches the router",
                step.get("granted") is True and phrases == ["stage code sub engel"],
                str(step),
            )
            check(
                "grants: the granted step carries the Governor's allow rule id",
                step.get("allow_rule_id") == "allow.gate.engel_script_action_grant",
                str(step.get("allow_rule_id")),
            )

            # The flag still gates: grants file present but allow_actions=False.
            receipt = es.execute_engel_script(
                action_phrase_plan, allow_actions=False, router=_fake_router,
                write_receipt=False,
            )
            check(
                "grants: allow_actions=False ignores the grants file entirely",
                receipt["steps"][0].get("blocked") is True
                and "granted" not in receipt["steps"][0],
                str(receipt["steps"][0]),
            )

            # Belts stay on under grant.
            slow_id = next(
                (
                    rid
                    for rid in es._routes_by_id()
                    if any(rid.endswith(s) for s in es.SLOW_ROUTE_SUFFIXES)
                ),
                "",
            )
            if slow_id:
                es.GRANTS_PATH.write_text(
                    json.dumps({"granted_route_ids": [slow_id]}), encoding="utf-8"
                )
                slow_grant = es._action_grant_for(slow_id)
                check(
                    "grants: slow-lane routes refuse even when granted",
                    slow_grant["granted"] is False
                    and "slow-lane" in slow_grant["reason"],
                    f"{slow_id} -> {slow_grant}",
                )
            else:
                check("grants: slow-lane routes refuse even when granted", True,
                      "no slow-suffix route in registry")
            check(
                "grants: the conductor itself is never grantable (no recursion)",
                es._action_grant_for("engel.conductor.goal")["granted"] is False,
            )
            check(
                "grants: a malformed grants file grants nothing",
                (es.GRANTS_PATH.write_text("not json", encoding="utf-8") or True)
                and es.load_action_grants() == set(),
            )

            # Governor down = fail closed.
            es.GRANTS_PATH.write_text(
                json.dumps({"granted_route_ids": ["engel.code.stage_sub_engel"]}),
                encoding="utf-8",
            )
            saved = sys.modules.get("engel_governor")
            sys.modules["engel_governor"] = None  # type: ignore[assignment]
            try:
                denied = es._action_grant_for("engel.code.stage_sub_engel")
            finally:
                if saved is not None:
                    sys.modules["engel_governor"] = saved
                else:
                    sys.modules.pop("engel_governor", None)
            check(
                "grants: Governor unavailable denies the grant (allow fails closed)",
                denied["granted"] is False and "fail closed" in denied["reason"],
                str(denied),
            )
        finally:
            es.GRANTS_PATH, es.RECEIPT_DIR = old_grants, old_receipts


def run_safety_belts() -> None:
    verdict = es.route_step_safety("engel goal check the fleet")
    check(
        "belt: scripts may not invoke the Conductor (no recursion by phrase)",
        verdict["allowed"] is False and "script engine" in verdict["reason"],
        str(verdict),
    )
    verdict = es.route_step_safety("engel goal status")
    check(
        "belt: the goal ledger route is also refused inside scripts",
        verdict["allowed"] is False,
        str(verdict),
    )


def run_wireup() -> None:
    from engel_ai_update_routes import (
        ROUTE_BY_ID,
        render_update_route,
        resolve_update_route,
    )
    from engel_communication_router import classify_user_input

    check(
        "wireup: conductor routes are registered",
        all(
            rid in ROUTE_BY_ID
            for rid in (
                "engel.conductor.docs",
                "engel.conductor.goal",
                "engel.conductor.status",
            )
        ),
    )
    goal_route = ROUTE_BY_ID["engel.conductor.goal"]
    check(
        "wireup: the goal route mirrors engel.script.run's flags",
        goal_route.read_only
        and goal_route.safe_for_ai_route
        and not goal_route.status_only,
    )
    check(
        "wireup: exact ledger alias beats the payload prefix",
        classify_user_input("engel goal status").route_target
        == "engel.conductor.status",
        classify_user_input("engel goal status").route_target,
    )
    # A near-miss of the ledger phrase must NOT open a phantom goal named
    # "status please" and write it permanently into the ledger (2026-08-01).
    import engel_main_local_model_worker as _worker

    for phrase in ("engel goal status please", "engel goal status for today",
                   "engel goals status update"):
        check(
            f"wireup: {phrase!r} reads the ledger instead of conducting a phantom goal",
            bool(_worker._ENGEL_CONDUCTOR_STATUS_RE.match(phrase)),
            "would be conducted as a new goal",
        )
    check(
        "wireup: a real goal phrase is still conducted, not swallowed by status",
        _worker._ENGEL_CONDUCTOR_STATUS_RE.match("engel goal check the fleet") is None,
    )
    check(
        "wireup: a payload-carrying goal phrase resolves to the goal route",
        classify_user_input("engel goal check the fleet").route_target
        == "engel.conductor.goal",
        classify_user_input("engel goal check the fleet").route_target,
    )
    check(
        "wireup: continue phrasing resolves to the goal route",
        classify_user_input("continue engel goal fleet_check_plan").route_target
        == "engel.conductor.goal",
    )
    check(
        "wireup: docs alias resolves",
        resolve_update_route("engel conductor docs") == "engel.conductor.docs",
    )
    rendered = render_update_route("engel.conductor.docs", "engel conductor docs")
    check(
        "wireup: the registry dispatches the docs renderer",
        "Conductor" in rendered and "engel goal" in rendered,
        rendered[:120],
    )

    import engel_main_local_model_worker as worker

    reply = worker._engel_conductor_chat_intercept("engel goal status", "verify-cd1")
    check(
        "chat: the worker answers the goal ledger locally, without a model",
        isinstance(reply, dict)
        and reply.get("engel_conductor_used") is True
        and reply.get("status") == "engel goal ledger",
        str(reply)[:160],
    )
    reply = worker._engel_conductor_chat_intercept("engel conductor docs", "verify-cd2")
    check(
        "chat: the worker renders conductor docs locally",
        isinstance(reply, dict) and "loop" in reply.get("assistant_reply", ""),
    )
    check(
        "chat: a normal prompt is untouched by the conductor intercept",
        worker._engel_conductor_chat_intercept("how are you today", "verify-cd3")
        is None,
    )
    source = (TOOLS / "engel_main_local_model_worker.py").read_text(encoding="utf-8")
    conductor_block = source.split("def _engel_conductor_chat_intercept", 1)[1]
    draft_block = conductor_block.split("def _draft", 1)[1].split("with _request", 1)[0]
    check(
        "chat: the conductor's drafter is chat_only with the long budget "
        "(the draft text must never trip the build detector)",
        "chat_only=True" in draft_block and "generation_seconds" in draft_block,
    )
    # (2026-08-11) Markers are matched on the CALL SITE and must both be present.
    # This searched for the literal "_run_fleet_dispatch(prompt, request_id)" while the
    # call site passes `operator_prompt`, so find() returned -1 and the gate went red
    # for an argument rename even though the live order was correct. Worse, a missing
    # FIRST marker also returns -1, which would make the comparison pass by accident --
    # so absence is now a loud failure in either position.
    conductor_at = source.find("= _engel_conductor_chat_intercept(")
    fleet_at = source.find("= _run_fleet_dispatch(")
    check(
        "chat: the conductor intercept runs BEFORE the fleet/build detectors",
        conductor_at >= 0 and fleet_at >= 0 and conductor_at < fleet_at,
        {"conductor_intercept_at": conductor_at, "fleet_dispatch_at": fleet_at},
    )


def main() -> int:
    run_loop()
    run_evidence()
    run_ledger_robustness()
    run_grants()
    run_safety_belts()
    run_wireup()
    failed = [name for name, ok, _ in CHECKS if not ok]
    print(f"\n{len(CHECKS) - len(failed)}/{len(CHECKS)} checks passed")
    if failed:
        print("FAILED:")
        for name in failed:
            print(f"  - {name}")
        return 1
    print("verify_engel_conductor: GREEN")
    return 0


if __name__ == "__main__":
    sys.exit(main())
