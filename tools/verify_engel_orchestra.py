#!/usr/bin/env python3
"""Prove the Orchestra joins the fan-out island to the Conductor loop.

Before this module (measured 2026-07-31): ``engel_subagents.fan_out`` had zero
production callers outside the harness and the doctor, the Conductor conducted
strictly serially, and a multi-part goal meant either one long serial plan or
several chat turns the operator sequenced by hand.

What must hold for the Orchestra to be trustworthy:

  1. SPLIT   -- the operator's `|` split always wins; a drafted split needs the
     injected drafter; with neither, the goal degrades to a single Conductor
     lane (never broken).
  2. PARALLEL -- lanes genuinely overlap their route I/O, yet every lane draft
     goes through ONE lock (the local model allows one in-flight call).
  3. BOUNDED -- more explicit parts than MAX_LANES is an honest refusal, not a
     silent clip; each lane inherits the Conductor's own bounds.
  4. HONEST MERGE -- the parent is ok only when EVERY lane is ok; a failed
     lane's problems are lane-prefixed and its continue-slug is printed.
  5. READ-ONLY -- orchestrate() has no allow_actions parameter at all; scripts
     cannot invoke the Orchestra; the Orchestra is never grantable.
  6. WIRED -- routes resolve (exact status alias beats the payload prefix),
     the registry dispatches the renderers, the chat worker answers status/
     docs locally, the run branch drafts chat_only, and the intercept runs
     before the fleet/build detectors.

Exit 0 = the section plays.
"""
from __future__ import annotations

import inspect
import json
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
for _p in (str(ROOT), str(TOOLS)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import engel_conductor as ec  # noqa: E402
import engel_orchestra as eo  # noqa: E402
import engel_script as es  # noqa: E402

CHECKS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    CHECKS.append((name, bool(ok), detail))
    print(f"{'PASS' if ok else 'FAIL'} {name}" + (f" -- {detail}" if detail and not ok else ""))


def _fake_router(phrase: str):
    return True, f"REPLY[{phrase}]"


VALID_PLAN = (
    'plan "verify lane"\n'
    'ask $s = route "engel status"\n'
    'say "status: " + $s\n'
)


class _Dirs:
    """Redirect every receipt/ledger dir into a tempdir for the test body."""

    def __enter__(self):
        self._tmp = tempfile.TemporaryDirectory()
        tmp = Path(self._tmp.name)
        self._old = (ec.GOAL_DIR, ec.RECEIPT_DIR, es.SCRIPT_DIR, es.RECEIPT_DIR, eo.RECEIPT_DIR)
        ec.GOAL_DIR = tmp / "goals"
        ec.RECEIPT_DIR = tmp / "conducts"
        es.SCRIPT_DIR = tmp / "plans"
        es.RECEIPT_DIR = tmp / "runs"
        eo.RECEIPT_DIR = tmp / "orchestras"
        return tmp

    def __exit__(self, *exc):
        ec.GOAL_DIR, ec.RECEIPT_DIR, es.SCRIPT_DIR, es.RECEIPT_DIR, eo.RECEIPT_DIR = self._old
        self._tmp.cleanup()
        return False


def _save_plans(*names: str) -> None:
    es.SCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    for name in names:
        (es.SCRIPT_DIR / f"{name}.engel").write_text(VALID_PLAN, encoding="utf-8")


def run_split() -> None:
    with _Dirs():
        _save_plans("lane_alpha", "lane_beta", "lane_gamma")
        receipt = eo.orchestrate(
            "lane_alpha | lane_beta | lane_gamma", router=_fake_router
        )
        check(
            "split: the operator's `|` split fans into one lane per part",
            receipt["split_origin"] == "operator split"
            and len(receipt["lanes"]) == 3,
            f"origin={receipt['split_origin']} lanes={len(receipt['lanes'])}",
        )
        check(
            "merge: all lanes ok = parent done",
            receipt["ok"] is True and receipt["status"] == "done",
            receipt["status"],
        )
        check(
            "receipts: every lane links its own conduct receipt",
            all(lane.get("conduct_receipt") for lane in receipt["lanes"]),
            str([lane.get("conduct_receipt") for lane in receipt["lanes"]]),
        )
        check(
            "receipts: the orchestra receipt is written",
            bool(receipt.get("receipt_path"))
            and Path(receipt["receipt_path"]).is_file(),
        )
        parent = ec.load_goal(receipt["slug"])
        check(
            "ledger: a kind-marked parent record sits next to the lane goals",
            isinstance(parent, dict)
            and parent.get("kind") == "orchestra"
            and len(parent.get("lane_slugs", [])) == 3
            and len(list(ec.GOAL_DIR.glob("*.json"))) == 4,
            str(parent)[:160],
        )
        verdict = receipt.get("fan_out_verdict") or {}
        check(
            "governor: the fan-out verdict is recorded",
            verdict.get("rule_id") == "allow.gate.orchestra_fan_out"
            and verdict.get("outcome") == "allow",
            str(verdict),
        )

        # Drafted split: no `|`, drafter splits into two lanes, lanes draft.
        drafts: list[str] = []

        def _drafter(prompt: str) -> str:
            drafts.append(prompt)
            if "Split this goal" in prompt:
                return "check the engel status\ncheck the workers status"
            if "Combine them" in prompt:
                return "Both parts are healthy."
            return VALID_PLAN

        receipt = eo.orchestrate(
            "review engel and the workers", draft_fn=_drafter, router=_fake_router
        )
        check(
            "split: a plain goal is drafted into lanes (one decomposition call)",
            receipt["split_origin"] == "drafted split"
            and len(receipt["lanes"]) == 2
            and sum("Split this goal" in d for d in drafts) == 1,
            f"origin={receipt['split_origin']} lanes={len(receipt['lanes'])}",
        )
        check(
            "synthesize: lane outputs merge through one injected call",
            receipt.get("synthesis") == "Both parts are healthy.",
            str(receipt.get("synthesis")),
        )
        check(
            "split: decomposition asks for sub-goals, never build vocabulary",
            drafts
            and "sub-goals" in drafts[0]
            and not any(w in drafts[0].lower() for w in ("build", "create a script")),
            drafts[0][:120] if drafts else "(no draft)",
        )

        # Degradation ladder: no `|`, no drafter -> single Conductor lane.
        receipt = eo.orchestrate("summarize the weather on mars", router=_fake_router)
        check(
            "degrade: no split + no drafter = a single honest Conductor lane",
            receipt["mode"] == "single_lane"
            and len(receipt["lanes"]) == 1
            and receipt["lanes"][0]["status"] == "no planner available",
            f"mode={receipt['mode']} status={receipt['lanes'][0]['status'] if receipt['lanes'] else '?'}",
        )
        # A single saved plan name still conducts to done.
        receipt = eo.orchestrate("lane_alpha", router=_fake_router)
        check(
            "degrade: a single saved plan conducts to done through one lane",
            receipt["ok"] is True and len(receipt["lanes"]) == 1,
            receipt["status"],
        )


def run_parallel() -> None:
    with _Dirs():
        _save_plans("slow_a", "slow_b", "slow_c")

        def _slow_router(phrase: str):
            time.sleep(0.5)
            return True, f"REPLY[{phrase}]"

        started = time.perf_counter()
        receipt = eo.orchestrate("slow_a | slow_b | slow_c", router=_slow_router)
        elapsed = time.perf_counter() - started
        check(
            "parallel: three 0.5s lanes overlap instead of queueing",
            receipt["ok"] is True and elapsed < 1.2,
            f"elapsed={elapsed:.2f}s (serial would be >=1.5s)",
        )

        # One model in flight: concurrent lane drafts must never overlap.
        state = {"active": 0, "max_active": 0}
        gate = threading.Lock()

        def _tracking_drafter(prompt: str) -> str:
            with gate:
                state["active"] += 1
                state["max_active"] = max(state["max_active"], state["active"])
            time.sleep(0.05)
            with gate:
                state["active"] -= 1
            return VALID_PLAN

        receipt = eo.orchestrate(
            "check the engel status | check the workers status",
            draft_fn=_tracking_drafter,
            router=_fake_router,
        )
        check(
            "parallel: lane drafts serialize through one lock (one model in flight)",
            receipt["ok"] is True and state["max_active"] == 1,
            f"max concurrent drafts={state['max_active']}",
        )


def run_bounds() -> None:
    with _Dirs():
        receipt = eo.orchestrate("a 1 | b 2 | c 3 | d 4 | e 5", router=_fake_router)
        check(
            "bounded: more parts than MAX_LANES is an honest refusal, no lanes run",
            "too many lanes" in receipt["status"]
            and receipt["lanes"] == []
            and len(receipt.get("subgoals", [])) == 5,
            receipt["status"],
        )
        check(
            "bounded: the refusal never writes a parent ledger record",
            not ec.GOAL_DIR.is_dir() or not list(ec.GOAL_DIR.glob("*.json")),
        )
    check(
        "read-only: orchestrate() has no allow_actions parameter at all",
        "allow_actions" not in inspect.signature(eo.orchestrate).parameters,
        str(list(inspect.signature(eo.orchestrate).parameters)),
    )
    lane_src = inspect.getsource(eo._conduct_lane)
    check(
        "read-only: every lane conducts with allow_actions=False, hardcoded",
        "allow_actions=False" in lane_src,
    )


def run_honest_merge() -> None:
    with _Dirs():
        _save_plans("good_lane")
        receipt = eo.orchestrate(
            "good_lane | a goal with no plan anywhere", router=_fake_router
        )
        check(
            "merge: one failed lane means the parent is NOT ok",
            receipt["ok"] is False and receipt["status"].startswith("1/2"),
            receipt["status"],
        )
        check(
            "merge: problems are lane-prefixed so the story reads",
            receipt["problems"] and all(p.startswith("lane ") for p in receipt["problems"]),
            str(receipt["problems"])[:160],
        )
        story = eo.render_orchestrate_result(receipt)
        failed_slug = next(
            lane["slug"] for lane in receipt["lanes"] if not lane["ok"] and lane["slug"]
        )
        check(
            "merge: the failed lane's continue-slug is printed for re-entry",
            f"continue engel goal {failed_slug}" in story,
            story[:200],
        )
        # A lane that crashes outright is a failed lane, not a crashed section.
        def _crashing_router(phrase: str):
            raise RuntimeError("router down")

        receipt = eo.orchestrate("good_lane | good_lane", router=_crashing_router)
        check(
            "merge: a crashing lane degrades to a failed lane, never an exception",
            isinstance(receipt, dict) and receipt["ok"] is False,
            receipt.get("status", "?"),
        )


def run_safety_belts() -> None:
    verdict = es.route_step_safety("engel orchestra status")
    check(
        "belt: scripts may not read the orchestra ledger",
        verdict["allowed"] is False,
        str(verdict),
    )
    verdict = es.route_step_safety("engel orchestra check the fleet")
    check(
        "belt: scripts may not invoke the Orchestra (no recursion by phrase)",
        verdict["allowed"] is False and "script engine" in verdict["reason"],
        str(verdict),
    )
    check(
        "belt: the Orchestra is never grantable",
        es._action_grant_for("engel.orchestra.run")["granted"] is False,
    )


def run_wireup() -> None:
    from engel_ai_update_routes import (
        ROUTE_BY_ID,
        render_update_route,
        resolve_update_route,
    )
    from engel_communication_router import classify_user_input

    check(
        "wireup: orchestra routes are registered",
        all(
            rid in ROUTE_BY_ID
            for rid in (
                "engel.orchestra.docs",
                "engel.orchestra.run",
                "engel.orchestra.status",
            )
        ),
    )
    run_route = ROUTE_BY_ID["engel.orchestra.run"]
    check(
        "wireup: the run route mirrors engel.conductor.goal's flags",
        run_route.read_only
        and run_route.safe_for_ai_route
        and not run_route.status_only,
    )
    check(
        "wireup: exact status alias beats the payload prefix",
        classify_user_input("engel orchestra status").route_target
        == "engel.orchestra.status",
        classify_user_input("engel orchestra status").route_target,
    )
    check(
        "wireup: a payload-carrying phrase resolves to the run route",
        classify_user_input("engel orchestra check the fleet").route_target
        == "engel.orchestra.run",
        classify_user_input("engel orchestra check the fleet").route_target,
    )
    check(
        "wireup: docs alias resolves",
        resolve_update_route("engel orchestra docs") == "engel.orchestra.docs",
    )
    rendered = render_update_route("engel.orchestra.docs", "engel orchestra docs")
    check(
        "wireup: the registry dispatches the docs renderer",
        "Orchestra" in rendered and "engel orchestra" in rendered,
        rendered[:120],
    )

    import engel_main_local_model_worker as worker

    # The phantom-goal lesson, applied here: status-with-filler reads the
    # ledger; a real multi-part goal is never swallowed by the status branch.
    for phrase in ("engel orchestra status please", "engel orchestra runs today"):
        check(
            f"wireup: {phrase!r} reads the ledger instead of opening a phantom goal",
            bool(worker._ENGEL_ORCHESTRA_STATUS_RE.match(phrase)),
        )
    check(
        "wireup: a real goal phrase is not swallowed by the status branch",
        worker._ENGEL_ORCHESTRA_STATUS_RE.match("engel orchestra check the fleet")
        is None,
    )
    reply = worker._engel_orchestra_chat_intercept("engel orchestra status", "verify-or1")
    check(
        "chat: the worker answers the orchestra ledger locally, without a model",
        isinstance(reply, dict)
        and reply.get("engel_orchestra_used") is True
        and reply.get("status") == "engel orchestra ledger",
        str(reply)[:160],
    )
    reply = worker._engel_orchestra_chat_intercept("engel orchestra docs", "verify-or2")
    check(
        "chat: the worker renders orchestra docs locally",
        isinstance(reply, dict) and "parallel" in reply.get("assistant_reply", ""),
    )
    check(
        "chat: a normal prompt is untouched by the orchestra intercept",
        worker._engel_orchestra_chat_intercept("how are you today", "verify-or3")
        is None,
    )
    source = (TOOLS / "engel_main_local_model_worker.py").read_text(encoding="utf-8")
    orchestra_block = source.split("def _engel_orchestra_chat_intercept", 1)[1]
    draft_block = orchestra_block.split("def _draft", 1)[1].split("with _request", 1)[0]
    check(
        "chat: the orchestra's drafter is chat_only with the long budget",
        "chat_only=True" in draft_block and "generation_seconds" in draft_block,
    )
    # (2026-08-11) Call-site markers, both required present -- see the same fix in
    # verify_engel_conductor.py: the old literal pinned the argument NAME, so a rename
    # to `operator_prompt` turned this red while the real ordering never changed.
    orchestra_at = source.find("= _engel_orchestra_chat_intercept(")
    fleet_at = source.find("= _run_fleet_dispatch(")
    check(
        "chat: the orchestra intercept runs BEFORE the fleet/build detectors",
        orchestra_at >= 0 and fleet_at >= 0 and orchestra_at < fleet_at,
    )

    import engel_agent_harness as harness

    check(
        "harness: orchestrate_goal is a registered tool (the island's first "
        "Engel-native wiring)",
        any(t["name"] == "orchestrate_goal" for t in harness.list_tools()),
        str([t["name"] for t in harness.list_tools()]),
    )


def main() -> int:
    run_split()
    run_parallel()
    run_bounds()
    run_honest_merge()
    run_safety_belts()
    run_wireup()
    failed = [name for name, ok, _ in CHECKS if not ok]
    print(f"\n{len(CHECKS) - len(failed)}/{len(CHECKS)} checks passed")
    if failed:
        print("FAILED:")
        for name in failed:
            print(f"  - {name}")
        return 1
    print("verify_engel_orchestra: GREEN")
    return 0


if __name__ == "__main__":
    sys.exit(main())
