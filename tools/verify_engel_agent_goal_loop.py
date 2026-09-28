"""Gate for the multi-turn goal loop (tools/engel_agent_goal_loop.py).

The whole safety of a multi-turn agent rests on one property: the agent's opinion about
whether it finished must not be able to end the run. So the central fixture here is a
LIAR -- an agent that announces completion on every single turn while the observed state
never changes. It must burn its stall limit and terminate as `stalled`, with its false
claims recorded rather than honoured.

The rest of the checks defend the other two ways these loops fail: running forever
(budget), and producing text while nothing moves (repetition and stall detection).

Everything runs offline against a temp directory. No model, no network, and the real
workspace is never mutated.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import engel_agent_author as aa  # noqa: E402
import engel_agent_goal_loop as gl  # noqa: E402
import engel_agent_runner as ar  # noqa: E402

checks: list[dict] = []


def check(name: str, ok: bool, detail: str) -> None:
    checks.append({"name": name, "status": "PASS" if ok else "FAIL", "detail": detail})


def refused(fn, *a, **kw) -> bool:
    try:
        fn(*a, **kw)
    # AgentRunError is a RuntimeError, not a ValueError -- the runner's status refusal
    # would otherwise read as "did not refuse" and silently pass this gate.
    except (gl.GoalError, aa.AgentAuthorError, ar.AgentRunError, ValueError):
        return True
    except Exception:
        return False
    return False


DIRECTION = (
    "Work toward the stated goal one step at a time, report what changed each turn, and "
    "say plainly when you cannot make progress. Do not modify files."
)


def active_agent(name: str = "Goal Agent", **kw) -> dict:
    reg = {"schema": aa.SCHEMA, "updated_at_utc": None, "agents": []}
    agent = aa.author_agent(name, "iterate toward a measurable goal", DIRECTION,
                            tools=["read_files"], registry=reg, **kw)
    aa.set_status(reg, name, "active")
    return agent


# --- 1. completion checks must be observable, bounded, and inside the workspace ----
check("rejects_unknown_check_kind",
      refused(gl.parse_check, {"kind": "agent_says_so", "target": "x.json"}),
      "a goal may only complete on a check the loop can observe")
check("rejects_absolute_target",
      refused(gl.parse_check, {"kind": "file_exists", "target": "C:/windows/system32/x"}),
      "completion targets must be repo-relative")
check("rejects_escaping_target",
      refused(gl.parse_check, {"kind": "file_exists", "target": "../../etc/passwd"}),
      "a completion target must not escape the workspace")
check("rejects_numeric_check_without_number",
      refused(gl.parse_check, {"kind": "json_field_at_least", "target": "a.json",
                               "field": "x", "value": "high"}),
      "a threshold check needs a numeric threshold")
check("accepts_wellformed_check",
      gl.parse_check({"kind": "json_field_at_least", "target": "a.json", "field": "overall",
                      "value": 0.5}).field == "overall",
      "a well-formed check must parse")

# --- 2. observation is real, both directions --------------------------------------
with tempfile.TemporaryDirectory() as tmp:
    rel = Path(tmp).name  # unused; we write inside the repo-relative temp below
# Use a repo-relative scratch file so the check's own path rules apply.
scratch_dir = ROOT / "runtime" / "temp" / "goal_loop_verify"
scratch_dir.mkdir(parents=True, exist_ok=True)
scratch = scratch_dir / "state.json"
rel_target = str(scratch.relative_to(ROOT)).replace("\\", "/")

scratch.write_text(json.dumps({"overall": 0.2, "status": "FAIL"}), encoding="utf-8")
low_check = gl.parse_check({"kind": "json_field_at_least", "target": rel_target,
                            "field": "overall", "value": 0.5})
met, _, _ = gl.evaluate_check(low_check)
check("check_unmet_when_below_threshold", met is False,
      "a value below the threshold must not read as met")
scratch.write_text(json.dumps({"overall": 0.8, "status": "PASS"}), encoding="utf-8")
met, _, _ = gl.evaluate_check(low_check)
check("check_met_when_above_threshold", met is True,
      "a value at or above the threshold must read as met")

missing = gl.parse_check({"kind": "file_exists", "target": "runtime/temp/goal_loop_verify/nope.json"})
met, _, _ = gl.evaluate_check(missing)
check("missing_file_is_not_met", met is False, "an absent file must not read as met")

equals = gl.parse_check({"kind": "json_field_equals", "target": rel_target,
                         "field": "status", "value": "PASS"})
met, _, _ = gl.evaluate_check(equals)
check("equality_check_works", met is True, "an equality check must compare the real value")

check("all_checks_must_be_met",
      gl.evaluate_goal([equals, gl.parse_check(
          {"kind": "json_field_at_least", "target": rel_target, "field": "overall", "value": 0.99}
      )])[0] is False,
      "a goal with several checks is met only when ALL are")

# --- 3. THE CENTRAL PROPERTY: a lying agent cannot stop the loop -------------------
scratch.write_text(json.dumps({"overall": 0.1, "status": "FAIL"}), encoding="utf-8")
unreachable = gl.parse_check({"kind": "json_field_at_least", "target": rel_target,
                              "field": "overall", "value": 0.99})
agent = active_agent()

liar_turns = {"n": 0}


def liar(_prompt: str) -> str:
    liar_turns["n"] += 1
    return f"Task complete. I am done -- the goal has been achieved. (turn {liar_turns['n']})"


receipt = gl.run_goal_loop(agent, "reach 0.99 overall", [unreachable],
                           reply_source=liar, max_turns=10, stall_limit=3)
check("liar_cannot_end_the_run", receipt["goal_met"] is False,
      "an agent announcing completion must NOT satisfy the goal")
check("liar_run_terminates_as_stalled", receipt["outcome"] == "stalled",
      f"a lying, non-progressing agent must stop as stalled; got {receipt['outcome']}")
check("liar_stops_at_stall_limit", receipt["turns_used"] == 3,
      f"the run must end at the stall limit (3), not the budget (10); used {receipt['turns_used']}")
check("false_claims_are_recorded",
      receipt["unsupported_completion_claims"] == [1, 2, 3],
      "every turn that claimed completion while the state disagreed must be recorded")
check("liar_run_is_not_ok", receipt["ok"] is False,
      "a run that never met its goal must not report ok")

# --- 4. a real completion ends the run, and only when the state actually moves -----
scratch.write_text(json.dumps({"overall": 0.1, "status": "FAIL"}), encoding="utf-8")
reach = gl.parse_check({"kind": "json_field_at_least", "target": rel_target,
                        "field": "overall", "value": 0.75})
progress = {"n": 0}


def worker(_prompt: str) -> str:
    progress["n"] += 1
    if progress["n"] == 2:  # the world changes on the second turn
        scratch.write_text(json.dumps({"overall": 0.9, "status": "PASS"}), encoding="utf-8")
    return f"working, step {progress['n']}"


receipt2 = gl.run_goal_loop(agent, "raise overall to 0.75", [reach],
                            reply_source=worker, max_turns=8, stall_limit=3)
check("real_completion_ends_the_run", receipt2["goal_met"] is True
      and receipt2["outcome"] == "goal_met",
      "the loop must end when the observed state satisfies the checks")
check("stops_as_soon_as_met", receipt2["turns_used"] == 2,
      f"it must stop on the turn the state met the goal; used {receipt2['turns_used']}")
check("budget_is_a_ceiling_not_a_target", receipt2["turns_used"] < receipt2["turn_budget"],
      "a converging run must not spend its whole budget")

# --- 5. budget is enforced when progress happens but the goal is never met ---------
scratch.write_text(json.dumps({"overall": 0.1}), encoding="utf-8")
drift = {"n": 0}


def crawler(_prompt: str) -> str:
    drift["n"] += 1
    # state changes every turn, so it never stalls -- only the budget can stop this
    scratch.write_text(json.dumps({"overall": 0.1 + drift["n"] / 1000}), encoding="utf-8")
    return f"nudging, {drift['n']}"


receipt3 = gl.run_goal_loop(agent, "reach 0.99", [unreachable],
                            reply_source=crawler, max_turns=4, stall_limit=99)
check("budget_terminates_endless_progress",
      receipt3["outcome"] == "budget_exhausted" and receipt3["turns_used"] == 4,
      f"a run that keeps moving but never arrives must stop at the budget; got "
      f"{receipt3['outcome']} after {receipt3['turns_used']}")

# --- 6. goals without an external check are refused --------------------------------
check("refuses_goal_with_no_checks",
      refused(gl.run_goal_loop, agent, "do something", [], reply_source=lambda _p: "x"),
      "without a check nothing but the agent's opinion could end the run")
check("refuses_empty_goal",
      refused(gl.run_goal_loop, agent, "  ", [reach], reply_source=lambda _p: "x"),
      "a goal needs a description to work toward")

draft = aa.author_agent("Draft Goal Agent", "a purpose here", DIRECTION,
                        registry={"schema": aa.SCHEMA, "agents": []})
check("refuses_inactive_agent",
      refused(gl.run_goal_loop, draft, "g", [reach], reply_source=lambda _p: "x"),
      "a draft agent must not run a goal loop")

# --- 7. bounds and provenance ------------------------------------------------------
capped = gl.run_goal_loop(active_agent("Capped", max_turns=2), "reach 0.99", [unreachable],
                          reply_source=lambda _p: "different text " + str(id(object())),
                          max_turns=50, stall_limit=99)
check("agent_max_turns_caps_the_request", capped["turns_used"] <= 2,
      "the agent's own max_turns must cap a larger requested budget")
check("receipt_pins_direction_version",
      receipt2["direction_version"] == agent["direction_version"],
      "the receipt must name the direction version that produced the run")
check("receipt_records_readonly", receipt2["read_only"] is True,
      "a non-granted agent's goal run must be recorded read-only")
check("receipt_keeps_every_turn",
      len(receipt["turns"]) == receipt["turns_used"] and all(
          "state_signature" in t and "claimed_done" in t for t in receipt["turns"]
      ),
      "each turn must record the observed state and whether completion was claimed")

src = (ROOT / "tools" / "engel_agent_goal_loop.py").read_text(encoding="utf-8")
check("goal_loop_cannot_execute",
      not any(tok in src for tok in ("subprocess.", "os.system(", "eval(", "exec(")),
      "the loop must not shell out -- it observes state, it never brings it about by force")

try:
    scratch.unlink()
    scratch_dir.rmdir()
except OSError:
    pass

failed = sum(1 for c in checks if c["status"] != "PASS")
print(json.dumps(
    {
        "schema": "engel_agent_goal_loop_verifier_v1",
        "status": "FAIL" if failed else "PASS",
        "passed": len(checks) - failed,
        "total": len(checks),
        "checks": checks,
    },
    indent=2,
))
raise SystemExit(1 if failed else 0)
