"""Run an authored agent under its own standing direction.

`engel_agent_author.py` creates the agent; this runs it. The split is deliberate -- the
authoring module contains no subprocess and no exec precisely so that writing a record can
never start work. Execution lives here, where the bounds can be enforced in one place.

What "running an agent" means here
----------------------------------
The agent's brief (purpose + versioned direction + tool allowlist + budget) is handed to
the local chat lane as the turn, and the reply is captured with a receipt naming EXACTLY
which direction version produced it. That last part is the point of the whole design: when
a run reads oddly, the first question is what the agent was told at the time, and the
receipt answers it without anyone having to reconstruct history.

Bounds, all enforced before generation
--------------------------------------
  * status must be `active` -- a draft or retired agent does not run
  * `allow_actions` is honoured: a read-only agent's brief says so, and this runner
    refuses to execute any privileged tool for it. Nothing here shells out, so a
    read-only agent physically cannot mutate the workspace through this path.
  * `max_turns` bounds the run; there is no unbounded loop
  * a tool the agent was never granted is refused by name rather than ignored

Local-only, like the rest of the training surface: the turn goes to the same chat endpoint
the trainer uses, so an agent run cannot reach a provider bridge.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
RUN_DIR = ROOT / "reports" / "agent_runs"
CHAT_URL = "http://127.0.0.1:24680/chat"
SCHEMA = "engel_agent_run_v1"

sys.path.insert(0, str(TOOLS))
import engel_agent_author as author  # noqa: E402


class AgentRunError(RuntimeError):
    """Raised when an agent may not run as asked."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _http_reply(prompt: str, timeout: int = 180) -> str:
    import urllib.request

    req = urllib.request.Request(
        CHAT_URL,
        data=json.dumps({"message": prompt}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = json.loads(resp.read().decode())
    return str(payload.get("assistant_reply") or payload.get("reply") or "")


def check_runnable(agent: dict[str, Any]) -> None:
    """Refuse before generating, not after."""
    status = str(agent.get("status") or "")
    if status != "active":
        raise AgentRunError(
            f"agent is {status!r}; only an active agent runs. Activate it deliberately "
            "with: engel_agent_author.py status --agent <name> --to active"
        )
    if not str(agent.get("direction") or "").strip():
        raise AgentRunError("agent has no direction to act under")


def check_tool(agent: dict[str, Any], tool: str) -> None:
    """A tool the agent was never granted is refused BY NAME."""
    if tool not in (agent.get("tools") or []):
        raise AgentRunError(
            f"agent {agent.get('name')!r} was not given the tool {tool!r} "
            f"(granted: {', '.join(agent.get('tools') or []) or 'none'})"
        )
    if tool in author.PRIVILEGED_TOOLS and not agent.get("allow_actions"):
        raise AgentRunError(
            f"tool {tool!r} does more than read and this agent has no action grant"
        )


def run_agent(
    agent: dict[str, Any],
    task: str = "",
    *,
    reply_source: Callable[[str], str] | None = None,
    max_turns: int | None = None,
) -> dict[str, Any]:
    """Run one bounded agent session and return a receipt.

    `reply_source` is injectable so the whole runner is testable without a model -- the
    same reason the capability harness takes one."""
    check_runnable(agent)
    source = reply_source or _http_reply
    budget = int(max_turns or agent.get("max_turns") or 1)
    budget = max(1, min(budget, int(agent.get("max_turns") or budget)))

    brief = author.agent_brief(agent)
    turn_prompt = brief if not task else f"{brief}\n\nThis run's task:\n{task}"

    turns: list[dict[str, Any]] = []
    for index in range(1, budget + 1):
        try:
            reply = source(turn_prompt)
            error = ""
        except Exception as exc:
            reply, error = "", f"{type(exc).__name__}: {exc}"
        turns.append(
            {
                "turn": index,
                "chars": len(reply),
                "reply": reply,
                "error": error,
            }
        )
        # One turn per session unless a task explicitly needs continuation; the budget is
        # a CEILING, never a target. Burning the whole budget to look busy is how an agent
        # loop turns into a token furnace.
        break

    return {
        "schema": SCHEMA,
        "run_at_utc": _utc_now(),
        "agent_id": agent.get("agent_id"),
        "agent_name": agent.get("name"),
        # The exact instruction that produced this output, so a strange run is diagnosed
        # by what it was TOLD rather than by guesswork.
        "direction_version": agent.get("direction_version"),
        "direction": agent.get("direction"),
        "allow_actions": bool(agent.get("allow_actions")),
        "read_only": not bool(agent.get("allow_actions")),
        "tools_granted": list(agent.get("tools") or []),
        "skills_assigned": list(agent.get("skills") or []),
        "tools_pending_operator_grant": list(agent.get("pending_tools") or []),
        "task": task,
        "turns_used": len(turns),
        "turn_budget": budget,
        "turns": turns,
        "ok": bool(turns and turns[-1]["reply"] and not turns[-1]["error"]),
    }


def write_receipt(receipt: dict[str, Any]) -> Path:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    stamp = str(receipt["run_at_utc"]).replace(":", "").replace("-", "")
    path = RUN_DIR / f"ENGEL_AGENT_RUN_{receipt.get('agent_id')}_{stamp}.json"
    path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False), encoding="utf-8")
    (RUN_DIR / "ENGEL_AGENT_RUN_LATEST.json").write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent", required=True, help="agent id or name")
    parser.add_argument("--task", default="", help="optional task for this session")
    parser.add_argument("--max-turns", type=int, default=None)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args(argv)

    registry = author.load_registry()
    try:
        agent = author.find_agent(registry, args.agent)
        receipt = run_agent(
            agent,
            args.task,
            reply_source=lambda p: _http_reply(p, args.timeout),
            max_turns=args.max_turns,
        )
    except (author.AgentAuthorError, AgentRunError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 1

    path = write_receipt(receipt)
    if args.summary:
        print(json.dumps(
            {
                "ok": receipt["ok"],
                "agent": receipt["agent_name"],
                "direction_version": receipt["direction_version"],
                "read_only": receipt["read_only"],
                "turns_used": receipt["turns_used"],
                "reply_chars": receipt["turns"][-1]["chars"] if receipt["turns"] else 0,
                "receipt": str(path),
            },
            indent=2,
        ))
    else:
        print(json.dumps(receipt, indent=2, ensure_ascii=False))
    return 0 if receipt["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
