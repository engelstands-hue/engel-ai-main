"""Gate for agent authoring (tools/engel_agent_author.py).

An authored agent is a standing instruction with a name attached, so the risky part is not
the happy path -- it is what the record ALLOWS. These checks are written against the
refusals: an agent must not be able to grant itself the power to act, name a capability
nothing defines, be activated without direction, or have its direction quietly rewritten.

Every check runs against an in-memory registry, so the real roster on disk is never
touched by the gate.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import engel_agent_author as aa  # noqa: E402

checks: list[dict] = []


def check(name: str, ok: bool, detail: str) -> None:
    checks.append({"name": name, "status": "PASS" if ok else "FAIL", "detail": detail})


def fresh() -> dict:
    return {"schema": aa.SCHEMA, "updated_at_utc": None, "agents": []}


def _tool_refused(runner_mod, agent: dict, tool: str) -> bool:
    try:
        runner_mod.check_tool(agent, tool)
    except runner_mod.AgentRunError:
        return True
    except Exception:
        return False
    return False


def refused(fn, *a, **kw) -> bool:
    try:
        fn(*a, **kw)
    except aa.AgentAuthorError:
        return True
    except Exception:
        return False
    return False


GOOD_DIRECTION = (
    "Review the newest prompt-training pack, group the rejected answers by their stated "
    "reason, and report the three largest groups with one example each. Do not modify any "
    "file; stop after the report."
)

# --- 1. the happy path produces a complete, durable record ------------------------
reg = fresh()
agent = aa.author_agent(
    "Pack Reviewer",
    "Summarize why training answers were rejected",
    GOOD_DIRECTION,
    tools=["read_files", "summarize"],
    registry=reg,
)
check("creates_agent_record",
      agent["schema"] == aa.AGENT_SCHEMA and agent["agent_id"].startswith("engel_agent_"),
      "authoring must produce a schema-stamped record with a generated id")
check("new_agent_starts_as_draft", agent["status"] == "draft",
      "a new agent must start as a draft, not active")
check("new_agent_cannot_act_by_default", agent["allow_actions"] is False,
      "allow_actions must default OFF -- an authored agent is read-only until granted")
check("records_authorship", agent["authored_by"] == "engel_ai_main" and agent["history"],
      "the record must say who authored it and keep a history")
check("registry_holds_the_agent", len(reg["agents"]) == 1,
      "the authored agent must land in the registry")

# --- 2. validation refuses records that cannot be acted on ------------------------
check("refuses_empty_name", refused(aa.author_agent, "", "a purpose here", GOOD_DIRECTION, registry=fresh()),
      "an unnamed agent must be refused")
check("refuses_thin_direction",
      refused(aa.author_agent, "Thin", "a purpose here", "do stuff", registry=fresh()),
      "a direction too thin to act on must be refused")
check("refuses_thin_purpose",
      refused(aa.author_agent, "NoPurpose", "x", GOOD_DIRECTION, registry=fresh()),
      "an agent with no stated purpose must be refused")
check("refuses_duplicate_name",
      refused(aa.author_agent, "Pack Reviewer", "another purpose", GOOD_DIRECTION, registry=reg),
      "two agents must not share a name")
check("refuses_bad_max_turns",
      refused(aa.author_agent, "Budget", "a purpose here", GOOD_DIRECTION, max_turns=0, registry=fresh()),
      "a turn budget outside 1-50 must be refused")

# --- 3. capability bounds ----------------------------------------------------------
check("refuses_unknown_tool",
      refused(aa.author_agent, "Toolless", "a purpose here", GOOD_DIRECTION,
              tools=["delete_everything"], registry=fresh()),
      "an agent cannot be given a capability the registry does not define")
check("privileged_tool_needs_action_grant",
      refused(aa.author_agent, "Runner", "a purpose here", GOOD_DIRECTION,
              tools=["run_verifier"], registry=fresh()),
      "a tool that does more than read must require allow_actions")
granted = aa.author_agent("Runner2", "a purpose here", GOOD_DIRECTION,
                          tools=["run_verifier"], allow_actions=True, registry=fresh())
check("privileged_tool_allowed_when_granted", granted["tools"] == ["run_verifier"],
      "with allow_actions the privileged tool must be accepted")

# --- 4. Engel must not be able to grant itself the power to act -------------------
check("engel_cannot_grant_itself_actions",
      refused(aa.grant_actions, reg, "Pack Reviewer", granted_by="engel_ai_main",
              reason="I would like to act now"),
      "the action grant must require a named operator, never Engel itself")
check("action_grant_requires_a_reason",
      refused(aa.grant_actions, reg, "Pack Reviewer", granted_by="Joshua", reason="ok"),
      "an action grant must record why it was given")
aa.grant_actions(reg, "Pack Reviewer", granted_by="Joshua",
                 reason="approved to run read-only verifiers for the weekly report")
check("human_grant_records_who_and_why",
      reg["agents"][0]["allow_actions"] is True
      and reg["agents"][0]["history"][-1]["event"] == "actions_granted"
      and reg["agents"][0]["history"][-1]["by"] == "Joshua",
      "a granted action must be attributed to the human who granted it")

# --- 5. direction is versioned, never silently overwritten ------------------------
NEW_DIRECTION = (
    "Review the newest two packs, group rejected answers by reason, and additionally list "
    "any reason that appears in one pack but not the other. Report only; change nothing."
)
before = reg["agents"][0]["direction"]
aa.give_direction(reg, "Pack Reviewer", NEW_DIRECTION, reason="widen to two packs")
after = reg["agents"][0]
check("direction_version_increments", after["direction_version"] == 2,
      "revising direction must bump its version")
check("previous_direction_is_kept",
      any(h.get("previous_direction") == before for h in after["history"]),
      "the prior direction must be retained -- a run is diagnosed by what it was TOLD")
check("revision_records_reason",
      after["history"][-1].get("reason") == "widen to two packs",
      "a direction change must record why")
check("refuses_unchanged_direction",
      refused(aa.give_direction, reg, "Pack Reviewer", NEW_DIRECTION),
      "a no-op revision must be refused rather than create an empty audit entry")
check("refuses_thin_new_direction",
      refused(aa.give_direction, reg, "Pack Reviewer", "go"),
      "a revision must meet the same bar as the original direction")

# --- 6. lifecycle ------------------------------------------------------------------
aa.set_status(reg, "Pack Reviewer", "active")
check("can_activate_with_direction", reg["agents"][0]["status"] == "active",
      "an agent with a direction must be activatable")
check("refuses_unknown_status", refused(aa.set_status, reg, "Pack Reviewer", "sentient"),
      "status must be one of draft/active/retired")
aa.set_status(reg, "Pack Reviewer", "retired")
check("retired_agent_refuses_new_direction",
      refused(aa.give_direction, reg, "Pack Reviewer", GOOD_DIRECTION + " Extra clause."),
      "a retired agent must not accept new direction")
check("history_is_add_only",
      len(reg["agents"][0]["history"]) >= 5,
      "every mutation must append to history rather than replace it")
check("unknown_agent_is_refused", refused(aa.find_agent, reg, "nobody"),
      "an unknown agent reference must raise, not return a default")

# --- 7. the brief an execution harness would use ----------------------------------
readonly = aa.author_agent("Briefee", "a purpose here", GOOD_DIRECTION,
                           tools=["read_files"], registry=fresh())
brief = aa.agent_brief(readonly)
check("brief_states_readonly",
      "READ-ONLY" in brief and "do not change files" in brief.casefold(),
      "a non-granted agent's brief must state plainly that it may not act")
check("brief_carries_direction_and_purpose",
      readonly["direction"][:40] in brief and readonly["purpose"] in brief,
      "the brief must carry the agent's purpose and standing direction")
check("brief_tells_it_to_stop_rather_than_invent",
      "rather than inventing" in brief.casefold(),
      "the brief must instruct an honest stop instead of a fabricated result")
granted_brief = aa.agent_brief(granted)
check("granted_brief_drops_readonly_line", "READ-ONLY" not in granted_brief,
      "an action-granted agent's brief must not claim to be read-only")

# --- 8. authoring never runs anything ---------------------------------------------
src = (ROOT / "tools" / "engel_agent_author.py").read_text(encoding="utf-8")
check(
    "authoring_module_cannot_execute",
    not any(tok in src for tok in ("subprocess.", "os.system(", "eval(", "exec(")),
    "the authoring module must not be able to start work -- it writes records only",
)

# --- 8b. revoking is deliberately easier than granting -----------------------------
rev_reg = fresh()
aa.author_agent("Revokee", "a purpose here", GOOD_DIRECTION, registry=rev_reg)
aa.grant_actions(rev_reg, "Revokee", granted_by="Joshua",
                 reason="approved to write findings for the weekly review")
check("revoke_turns_the_grant_off",
      aa.revoke_actions(rev_reg, "Revokee", reason="demo finished")["allow_actions"] is False,
      "revoking must actually withdraw the grant")
check("revoke_is_recorded",
      rev_reg["agents"][0]["history"][-1]["event"] == "actions_revoked"
      and rev_reg["agents"][0]["history"][-1]["was_granted"] is True,
      "a revocation must be recorded, including that a grant was in force")
check("revoke_needs_no_named_operator",
      aa.revoke_actions(rev_reg, "Revokee")["allow_actions"] is False,
      "removing authority must NOT be gated behind a signature -- a control that is "
      "harder to switch off than on gets routed around")

# --- 9. the runner enforces the record's bounds -----------------------------------
# Authoring writes the bounds; the runner is where they either hold or do not.
import engel_agent_runner as runner  # noqa: E402

run_reg = fresh()
drafted = aa.author_agent("Runnable", "a purpose here", GOOD_DIRECTION,
                          tools=["read_files"], registry=run_reg)


def run_refused(agent, **kw) -> bool:
    try:
        runner.run_agent(agent, reply_source=lambda _p: "ok", **kw)
    except (runner.AgentRunError, aa.AgentAuthorError):
        return True
    except Exception:
        return False
    return False


check("runner_refuses_draft_agent", run_refused(drafted),
      "a draft agent must not run -- activation is deliberate")
aa.set_status(run_reg, "Runnable", "active")
receipt = runner.run_agent(drafted, "list the newest pack", reply_source=lambda _p: "a reply")
check("runner_runs_active_agent", receipt["ok"] is True and receipt["turns_used"] == 1,
      "an active agent must run and produce a receipt")
check("receipt_pins_direction_version",
      receipt["direction_version"] == drafted["direction_version"]
      and receipt["direction"] == drafted["direction"],
      "the receipt must name the exact direction that produced the output")
check("receipt_marks_read_only", receipt["read_only"] is True,
      "a non-granted agent's run must be recorded as read-only")
check("runner_honours_turn_budget", receipt["turns_used"] <= drafted["max_turns"],
      "a run must never exceed the agent's turn budget")

captured: dict[str, str] = {}
runner.run_agent(drafted, reply_source=lambda p: captured.setdefault("p", p) or "x")
check("runner_sends_the_brief",
      "READ-ONLY" in captured["p"] and drafted["direction"][:30] in captured["p"],
      "the agent must be run under its own brief, not a bare task string")

check("runner_refuses_ungranted_tool",
      run_refused(drafted) is False and _tool_refused(runner, drafted, "run_verifier"),
      "a tool the agent was never granted must be refused by name")
check("runner_refuses_privileged_tool_without_grant",
      _tool_refused(runner, drafted, "capability_eval"),
      "a privileged tool must be refused when there is no action grant")

aa.set_status(run_reg, "Runnable", "retired")
check("runner_refuses_retired_agent", run_refused(drafted),
      "a retired agent must not run")

runner_src = (ROOT / "tools" / "engel_agent_runner.py").read_text(encoding="utf-8")
check(
    "runner_cannot_shell_out",
    not any(tok in runner_src for tok in ("subprocess.", "os.system(", "eval(", "exec(")),
    "the runner must not shell out -- a read-only agent physically cannot mutate the "
    "workspace through this path",
)

failed = sum(1 for c in checks if c["status"] != "PASS")
print(json.dumps(
    {
        "schema": "engel_agent_author_verifier_v1",
        "status": "FAIL" if failed else "PASS",
        "passed": len(checks) - failed,
        "total": len(checks),
        "checks": checks,
    },
    indent=2,
))
raise SystemExit(1 if failed else 0)
