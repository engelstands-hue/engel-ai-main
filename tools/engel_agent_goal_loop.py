"""Run an authored agent MULTI-TURN toward a goal, with a stop the agent cannot fake.

The problem this solves
-----------------------
A single-turn agent is safe and useless for anything that takes iteration. A multi-turn
agent that decides for itself when it is finished is worse than useless: the failure mode
is not "it stops too early", it is that the loop never converges and nobody notices,
because every turn produces confident prose. Three specific ways these loops go wrong, all
observed in real systems and all designed against here:

  1. THE AGENT GRADES ITS OWN HOMEWORK. It announces success and the harness believes it.
  2. IT REPEATS ITSELF. Turn 7 restates turn 3 in new words; text is produced, nothing moves.
  3. IT RUNS FOREVER. A budget exists but nothing notices the run stopped making progress
     ten turns ago, so the full budget is always spent.

The rule that makes this safe
-----------------------------
**A claim of completion never terminates the loop.** The agent's "I am done" is recorded
as an observation and nothing more. The loop ends when a COMPLETION PREDICATE -- fixed
before the run starts, evaluated by this module, over state on disk -- agrees. If the
predicate and the agent disagree, the predicate wins and the disagreement is recorded,
because an agent that believes it succeeded while the state says otherwise is the single
most valuable thing this receipt can capture.

Completion checks are OBSERVATIONS, not executions
--------------------------------------------------
Every check reads state; none runs anything. This module shells out nowhere -- no
subprocess, no exec -- for the same reason the runner and author do not: an agent surface
that cannot execute cannot be talked into executing. So "the verifier passes" is expressed
as "that verifier's receipt on disk says PASS", which is an observation of a result
someone else produced. The loop can therefore iterate toward a goal without ever being
able to bring the goal about by force.

Progress is measured, not claimed
---------------------------------
Each turn the loop hashes the observed state and the agent's own reply. State unchanged
AND reply substantially repeated counts as a no-progress turn; `stall_limit` consecutive
no-progress turns ends the run as `stalled`. This is what keeps a budget from being a
target: a converging run stops when it converges, and a stuck run stops early instead of
spending everything to look busy.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
RUN_DIR = ROOT / "reports" / "agent_runs"
SCHEMA = "engel_agent_goal_run_v1"

sys.path.insert(0, str(TOOLS))
import engel_agent_author as author  # noqa: E402
import engel_agent_runner as runner  # noqa: E402

# Every check is a READ of state on disk. Nothing here executes anything, so an agent can
# never satisfy its own completion predicate by force -- only by the world changing.
KNOWN_CHECKS = ("file_exists", "json_field_at_least", "json_field_at_most", "json_field_equals")

# Ceilings. A budget is a ceiling, never a target.
MAX_TURN_CEILING = 25
DEFAULT_STALL_LIMIT = 3

# Phrases an agent uses to announce completion. Recorded, never obeyed.
_DONE_CLAIMS = (
    "task complete", "goal achieved", "i am done", "i'm done", "completed the goal",
    "nothing further", "no further action", "this is complete", "finished the task",
)


class GoalError(ValueError):
    """Raised when a goal is not admissible or a run may not proceed."""


@dataclass(frozen=True)
class CompletionCheck:
    kind: str
    target: str            # repo-relative path
    field: str = ""        # dotted path inside a JSON document
    value: Any = None      # threshold / expected value

    def describe(self) -> str:
        if self.kind == "file_exists":
            return f"{self.target} exists"
        return f"{self.target}:{self.field} {self.kind.replace('json_field_', '')} {self.value!r}"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dig(doc: Any, dotted: str) -> Any:
    cur = doc
    for part in [p for p in str(dotted or "").split(".") if p]:
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def parse_check(spec: dict[str, Any]) -> CompletionCheck:
    kind = str(spec.get("kind") or "").strip()
    if kind not in KNOWN_CHECKS:
        raise GoalError(
            f"unknown completion check {kind!r} -- a goal may only be completed by a check "
            f"this module can observe (known: {', '.join(KNOWN_CHECKS)})"
        )
    target = str(spec.get("target") or "").strip()
    if not target:
        raise GoalError("a completion check must name the file it observes")
    if Path(target).is_absolute() or ".." in Path(target).parts:
        raise GoalError("completion targets are repo-relative and may not escape the workspace")
    check = CompletionCheck(
        kind=kind,
        target=target,
        field=str(spec.get("field") or ""),
        value=spec.get("value"),
    )
    if kind != "file_exists":
        if not check.field:
            raise GoalError(f"{kind} needs a field to read")
        if kind in ("json_field_at_least", "json_field_at_most") and not isinstance(
            check.value, (int, float)
        ):
            raise GoalError(f"{kind} needs a numeric value")
        if kind == "json_field_equals" and check.value is None:
            raise GoalError("json_field_equals needs an expected value")
    return check


def evaluate_check(check: CompletionCheck) -> tuple[bool, str, str]:
    """(met, observed_signature, detail). Pure observation of disk state."""
    path = ROOT / check.target
    if check.kind == "file_exists":
        met = path.is_file()
        return met, f"exists={met}", f"{check.target} {'exists' if met else 'is missing'}"
    if not path.is_file():
        return False, "missing", f"{check.target} does not exist yet"
    try:
        doc = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        return False, "unreadable", f"{check.target} is not readable JSON ({exc})"
    observed = _dig(doc, check.field)
    sig = f"{check.field}={observed!r}"
    if observed is None:
        return False, sig, f"{check.target}:{check.field} is absent"
    try:
        if check.kind == "json_field_at_least":
            met = float(observed) >= float(check.value)
        elif check.kind == "json_field_at_most":
            met = float(observed) <= float(check.value)
        else:
            met = observed == check.value
    except (TypeError, ValueError):
        return False, sig, f"{check.target}:{check.field} is {observed!r}, not comparable"
    return met, sig, f"{check.target}:{check.field} is {observed!r} ({'met' if met else 'not met'})"


def evaluate_goal(checks: list[CompletionCheck]) -> tuple[bool, str, list[str]]:
    """ALL checks must be met. Returns (met, state_signature, details)."""
    met_all = True
    sigs: list[str] = []
    details: list[str] = []
    for check in checks:
        met, sig, detail = evaluate_check(check)
        met_all = met_all and met
        sigs.append(f"{check.kind}:{check.target}:{sig}")
        details.append(detail)
    signature = hashlib.sha256("|".join(sigs).encode("utf-8")).hexdigest()[:16]
    return met_all, signature, details


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", "", " ".join(str(text or "").split()).casefold())


def _reply_signature(text: str) -> str:
    return hashlib.sha256(_normalize(text).encode("utf-8")).hexdigest()[:16]


def claims_done(text: str) -> bool:
    low = _normalize(text)
    return any(_normalize(claim) in low for claim in _DONE_CLAIMS)


def run_goal_loop(
    agent: dict[str, Any],
    goal: str,
    checks: list[CompletionCheck],
    *,
    reply_source: Callable[[str], str] | None = None,
    max_turns: int = 6,
    stall_limit: int = DEFAULT_STALL_LIMIT,
) -> dict[str, Any]:
    """Iterate toward `goal` until the checks agree, progress stops, or the budget ends."""
    runner.check_runnable(agent)
    if not checks:
        raise GoalError(
            "a goal needs at least one completion check -- without one, nothing but the "
            "agent's own opinion could end the run"
        )
    if not str(goal or "").strip():
        raise GoalError("a goal needs a description the agent can work toward")
    budget = max(1, min(int(max_turns), int(agent.get("max_turns") or MAX_TURN_CEILING),
                        MAX_TURN_CEILING))
    source = reply_source or runner._http_reply

    brief = author.agent_brief(agent)
    met, signature, details = evaluate_goal(checks)
    turns: list[dict[str, Any]] = []
    seen_replies: set[str] = set()
    no_progress = 0
    outcome = "goal_met_before_start" if met else ""

    while not met and len(turns) < budget:
        turn_no = len(turns) + 1
        prompt = (
            f"{brief}\n\n"
            f"GOAL: {goal}\n"
            f"This goal is complete only when ALL of these are true, checked by the system "
            f"and not by you:\n"
            + "\n".join(f"  - {c.describe()}" for c in checks)
            + f"\n\nCurrent observed state:\n"
            + "\n".join(f"  - {d}" for d in details)
            + f"\n\nTurn {turn_no} of at most {budget}. Say what you did or found this turn "
            f"and what remains. Saying you are finished does not end the run: the checks "
            f"above decide that. If you cannot make progress, say so plainly."
        )
        try:
            reply = source(prompt)
            error = ""
        except Exception as exc:
            reply, error = "", f"{type(exc).__name__}: {exc}"

        met, new_signature, details = evaluate_goal(checks)
        reply_sig = _reply_signature(reply)
        state_moved = new_signature != signature
        reply_repeated = reply_sig in seen_replies
        seen_replies.add(reply_sig)
        progressed = state_moved and not error
        no_progress = 0 if progressed else no_progress + 1
        signature = new_signature

        turns.append(
            {
                "turn": turn_no,
                "chars": len(reply),
                "error": error,
                "state_signature": new_signature,
                "state_moved": state_moved,
                "reply_repeated": reply_repeated,
                # Recorded, never obeyed. A run where this is True while goal_met is False
                # is the most valuable row in the receipt.
                "claimed_done": claims_done(reply),
                "goal_met_after_turn": met,
                "reply": reply,
            }
        )
        if met:
            outcome = "goal_met"
            break
        if no_progress >= stall_limit:
            outcome = "stalled"
            break

    if not outcome:
        outcome = "budget_exhausted"

    false_claims = [t["turn"] for t in turns if t["claimed_done"] and not t["goal_met_after_turn"]]
    return {
        "schema": SCHEMA,
        "run_at_utc": _utc_now(),
        "agent_id": agent.get("agent_id"),
        "agent_name": agent.get("name"),
        "direction_version": agent.get("direction_version"),
        "direction": agent.get("direction"),
        "read_only": not bool(agent.get("allow_actions")),
        "goal": goal,
        "completion_checks": [
            {"kind": c.kind, "target": c.target, "field": c.field, "value": c.value,
             "describe": c.describe()}
            for c in checks
        ],
        "turn_budget": budget,
        "stall_limit": stall_limit,
        "turns_used": len(turns),
        "outcome": outcome,
        "goal_met": bool(met),
        "final_state": details,
        # Turns where the agent said it was finished and the state disagreed.
        "unsupported_completion_claims": false_claims,
        "turns": turns,
        "ok": bool(met),
    }


def write_receipt(receipt: dict[str, Any]) -> Path:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    stamp = str(receipt["run_at_utc"]).replace(":", "").replace("-", "")
    path = RUN_DIR / f"ENGEL_AGENT_GOAL_{receipt.get('agent_id')}_{stamp}.json"
    path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False), encoding="utf-8")
    (RUN_DIR / "ENGEL_AGENT_GOAL_LATEST.json").write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent", required=True)
    parser.add_argument("--goal", required=True)
    parser.add_argument(
        "--check",
        action="append",
        default=[],
        required=True,
        help=(
            'JSON completion check, repeatable. e.g. '
            '\'{"kind":"json_field_at_least","target":"reports/capability_eval/'
            'ENGEL_CAPABILITY_EVAL_LATEST.json","field":"overall","value":0.5}\''
        ),
    )
    parser.add_argument("--max-turns", type=int, default=6)
    parser.add_argument("--stall-limit", type=int, default=DEFAULT_STALL_LIMIT)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args(argv)

    registry = author.load_registry()
    try:
        agent = author.find_agent(registry, args.agent)
        checks = [parse_check(json.loads(raw)) for raw in args.check]
        receipt = run_goal_loop(
            agent,
            args.goal,
            checks,
            reply_source=lambda p: runner._http_reply(p, args.timeout),
            max_turns=args.max_turns,
            stall_limit=args.stall_limit,
        )
    except (author.AgentAuthorError, runner.AgentRunError, GoalError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 1

    path = write_receipt(receipt)
    if args.summary:
        print(json.dumps(
            {
                "ok": receipt["ok"],
                "agent": receipt["agent_name"],
                "outcome": receipt["outcome"],
                "goal_met": receipt["goal_met"],
                "turns_used": f"{receipt['turns_used']}/{receipt['turn_budget']}",
                "unsupported_completion_claims": receipt["unsupported_completion_claims"],
                "final_state": receipt["final_state"],
                "receipt": str(path),
            },
            indent=2,
        ))
    else:
        print(json.dumps(receipt, indent=2, ensure_ascii=False))
    return 0 if receipt["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
