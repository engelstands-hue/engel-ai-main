"""Let Engel AI Main CREATE an agent and give it standing direction.

What was missing
----------------
Engel could already RUN agent-shaped work -- `engel_subagents.spawn_subagent(task)` fans a
task out, `engel_conductor.py` drives a goal loop, the Meeting Room dispatches orders. But
every one of those is fire-and-forget: you hand over a task string, work happens, and
afterwards NO AGENT EXISTS. There is no roster, no role that persists between turns, no
standing direction to revise, and no record of who was told to do what. Engel could act
like an agent; it could not *make* one.

This module adds the missing noun. An authored agent is a durable, reviewable record:

    identity   name + generated agent_id + who authored it and when
    purpose    one line: what this agent is FOR
    direction  the standing instruction it works under, revisable with history
    bounds     allowed tools, an action grant that is OFF unless granted, a turn budget
    status     draft -> active -> retired, with an audit trail for every change

Direction is versioned rather than overwritten. "Give the direction" is the operating verb
here, and an agent whose instructions can be silently rewritten is not auditable -- when a
run goes wrong the first question is what it was told at the time, so every revision keeps
its predecessor and a reason.

Safety posture (matches the rest of this system)
------------------------------------------------
  * `allow_actions` defaults FALSE. An authored agent is read-only until a human grants
    otherwise, mirroring the Conductor's default-off action grants.
  * Tools must come from a declared allowlist; an agent cannot name a capability the
    registry does not know.
  * Authoring is not running. This module writes and validates records; execution stays
    with the existing harnesses, so nothing here can start work by itself.
  * Every mutation appends to the agent's `history`, so the record is add-only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
REGISTRY_DIR = ROOT / "memory" / "agents"
REGISTRY = REGISTRY_DIR / "ENGEL_AGENT_REGISTRY.json"

SCHEMA = "engel_authored_agent_registry_v1"
AGENT_SCHEMA = "engel_authored_agent_v1"

STATUSES = ("draft", "active", "retired")

# Capabilities an authored agent may be given. Naming a tool outside this set is refused:
# an agent that could declare arbitrary capability text would be describing powers nothing
# grants, which is how a roster stops matching reality.
KNOWN_TOOLS = (
    "read_files",
    "search_repo",
    "run_verifier",
    "summarize",
    "draft_report",
    "chat_reply",
    "capability_eval",
    "propose_curriculum",
)

# Tools that touch anything outside a read/summarize loop. Granting one of these requires
# allow_actions, which only a human sets.
PRIVILEGED_TOOLS = frozenset({"run_verifier", "propose_curriculum", "capability_eval"})

MAX_NAME = 60
MAX_DIRECTION = 2000
_NAME_OK = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _.-]*$")


class AgentAuthorError(ValueError):
    """Raised when a proposed agent record is not admissible."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _agent_id(name: str, created_at: str) -> str:
    digest = hashlib.sha256(f"{name}|{created_at}".encode("utf-8")).hexdigest()[:12]
    return f"engel_agent_{digest}"


def load_registry(path: Path = REGISTRY) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        data = {}
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        return {"schema": SCHEMA, "updated_at_utc": None, "agents": [], "tasks": []}
    data.setdefault("agents", [])
    data.setdefault("tasks", [])
    for agent in data["agents"]:
        if isinstance(agent, dict):
            agent.setdefault("skills", [])
            agent.setdefault("pending_tools", [])
    return data


def save_registry(registry: dict[str, Any], path: Path = REGISTRY) -> None:
    registry["schema"] = SCHEMA
    registry["updated_at_utc"] = _utc_now()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(registry, indent=2, sort_keys=False), encoding="utf-8")


def validate_direction(direction: str) -> str:
    text = " ".join(str(direction or "").split())
    if len(text) < 20:
        raise AgentAuthorError(
            "direction is too thin to act on -- say what the agent should do, on what, "
            "and when to stop"
        )
    if len(text) > MAX_DIRECTION:
        raise AgentAuthorError(f"direction exceeds {MAX_DIRECTION} characters")
    return text


def validate_tools(tools: list[str] | tuple[str, ...], allow_actions: bool) -> list[str]:
    cleaned: list[str] = []
    for tool in tools or ():
        name = str(tool).strip()
        if name not in KNOWN_TOOLS:
            raise AgentAuthorError(
                f"unknown tool {name!r} -- an agent cannot be given a capability the "
                f"registry does not define (known: {', '.join(KNOWN_TOOLS)})"
            )
        if name in PRIVILEGED_TOOLS and not allow_actions:
            raise AgentAuthorError(
                f"tool {name!r} does more than read, so it requires allow_actions=true, "
                "which is an explicit human grant"
            )
        if name not in cleaned:
            cleaned.append(name)
    return cleaned


def author_agent(
    name: str,
    purpose: str,
    direction: str,
    *,
    tools: list[str] | tuple[str, ...] = (),
    allow_actions: bool = False,
    max_turns: int = 8,
    authored_by: str = "engel_ai_main",
    registry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a new authored agent record. Does NOT run anything."""
    clean_name = " ".join(str(name or "").split())
    if not clean_name or not _NAME_OK.match(clean_name) or len(clean_name) > MAX_NAME:
        raise AgentAuthorError(
            "name must be 1-60 chars, start alphanumeric, and use only letters, digits, "
            "space, dot, underscore or hyphen"
        )
    clean_purpose = " ".join(str(purpose or "").split())
    if len(clean_purpose) < 10:
        raise AgentAuthorError("purpose must say what the agent is for")
    clean_direction = validate_direction(direction)
    clean_tools = validate_tools(tools, allow_actions)
    if not isinstance(max_turns, int) or not 1 <= max_turns <= 50:
        raise AgentAuthorError("max_turns must be an int between 1 and 50")

    reg = load_registry() if registry is None else registry
    reg.setdefault("agents", [])
    reg.setdefault("tasks", [])
    if any(a.get("name", "").casefold() == clean_name.casefold() for a in reg["agents"]):
        raise AgentAuthorError(f"an agent named {clean_name!r} already exists")

    created = _utc_now()
    agent = {
        "schema": AGENT_SCHEMA,
        "agent_id": _agent_id(clean_name, created),
        "name": clean_name,
        "purpose": clean_purpose,
        "direction": clean_direction,
        "direction_version": 1,
        "status": "draft",
        "tools": clean_tools,
        # High-level skills are bound by engel_mipl_agent_work.  Keeping the
        # fields in every record makes older authoring clients forward
        # compatible without letting them invent skill authority.
        "skills": [],
        "pending_tools": [],
        # Default OFF. An authored agent is read-only until a human says otherwise.
        "allow_actions": bool(allow_actions),
        "max_turns": max_turns,
        "authored_by": authored_by,
        "created_at_utc": created,
        "updated_at_utc": created,
        "history": [
            {
                "at_utc": created,
                "event": "authored",
                "by": authored_by,
                "direction_version": 1,
                "note": "agent created as draft; activation is a separate step",
            }
        ],
    }
    reg["agents"].append(agent)
    return agent


def find_agent(registry: dict[str, Any], ref: str) -> dict[str, Any]:
    needle = str(ref or "").strip().casefold()
    for agent in registry.get("agents", []):
        if needle in (agent.get("agent_id", "").casefold(), agent.get("name", "").casefold()):
            return agent
    raise AgentAuthorError(f"no agent matches {ref!r}")


def give_direction(
    registry: dict[str, Any],
    ref: str,
    direction: str,
    *,
    reason: str = "",
    by: str = "engel_ai_main",
) -> dict[str, Any]:
    """Revise an agent's standing direction, keeping the previous one.

    Overwriting would make a misbehaving run un-diagnosable: the first question is always
    what the agent was told AT THE TIME. So the prior text is retained in history."""
    agent = find_agent(registry, ref)
    if agent.get("status") == "retired":
        raise AgentAuthorError("a retired agent cannot be given new direction; re-author it")
    new_direction = validate_direction(direction)
    previous = agent.get("direction", "")
    if new_direction == previous:
        raise AgentAuthorError("direction is unchanged")
    agent["direction"] = new_direction
    agent["direction_version"] = int(agent.get("direction_version", 1)) + 1
    agent["updated_at_utc"] = _utc_now()
    agent["history"].append(
        {
            "at_utc": agent["updated_at_utc"],
            "event": "direction_revised",
            "by": by,
            "direction_version": agent["direction_version"],
            "previous_direction": previous,
            "reason": " ".join(str(reason or "").split()) or "no reason given",
        }
    )
    return agent


def set_status(
    registry: dict[str, Any], ref: str, status: str, *, by: str = "engel_ai_main"
) -> dict[str, Any]:
    if status not in STATUSES:
        raise AgentAuthorError(f"status must be one of {STATUSES}")
    agent = find_agent(registry, ref)
    if status == "active" and not agent.get("direction"):
        raise AgentAuthorError("an agent cannot be activated without a direction")
    previous = agent.get("status")
    agent["status"] = status
    agent["updated_at_utc"] = _utc_now()
    agent["history"].append(
        {"at_utc": agent["updated_at_utc"], "event": "status_changed", "by": by,
         "from": previous, "to": status}
    )
    return agent


def grant_actions(
    registry: dict[str, Any], ref: str, *, granted_by: str, reason: str
) -> dict[str, Any]:
    """Turn on the action grant. Deliberately requires a named human and a reason."""
    who = " ".join(str(granted_by or "").split())
    why = " ".join(str(reason or "").split())
    if not who or who == "engel_ai_main":
        raise AgentAuthorError(
            "an action grant must be made by a named operator -- Engel cannot grant "
            "itself the ability to act"
        )
    if len(why) < 10:
        raise AgentAuthorError("an action grant must record why it was given")
    agent = find_agent(registry, ref)
    pending_tools = validate_tools(list(agent.get("pending_tools") or ()), True)
    tools = list(agent.get("tools") or ())
    for tool in pending_tools:
        if tool not in tools:
            tools.append(tool)
    agent["tools"] = tools
    agent["pending_tools"] = []
    agent["allow_actions"] = True
    agent["updated_at_utc"] = _utc_now()
    agent["history"].append(
        {"at_utc": agent["updated_at_utc"], "event": "actions_granted",
         "by": who, "reason": why, "enabled_tools": pending_tools}
    )
    return agent


def revoke_actions(
    registry: dict[str, Any], ref: str, *, revoked_by: str = "engel_ai_main", reason: str = ""
) -> dict[str, Any]:
    """Withdraw an action grant.

    Deliberately asymmetric with `grant_actions`: granting authority requires a named
    operator, REMOVING it does not. A safety control that is harder to switch off than on
    is one people route around, and there is no scenario where taking away an agent's
    ability to act needs to be gated behind a signature."""
    agent = find_agent(registry, ref)
    was = bool(agent.get("allow_actions"))
    tools = list(agent.get("tools") or ())
    privileged = [tool for tool in tools if tool in PRIVILEGED_TOOLS]
    agent["tools"] = [tool for tool in tools if tool not in PRIVILEGED_TOOLS]
    pending = list(agent.get("pending_tools") or ())
    for tool in privileged:
        if tool not in pending:
            pending.append(tool)
    agent["pending_tools"] = pending
    agent["allow_actions"] = False
    agent["updated_at_utc"] = _utc_now()
    agent["history"].append(
        {
            "at_utc": agent["updated_at_utc"],
            "event": "actions_revoked",
            "by": " ".join(str(revoked_by or "").split()) or "engel_ai_main",
            "was_granted": was,
            "disabled_tools": privileged,
            "reason": " ".join(str(reason or "").split()) or "no reason given",
        }
    )
    return agent


def agent_brief(agent: dict[str, Any]) -> str:
    """The text an execution harness would hand the agent at the start of a run."""
    lines = [
        f"You are {agent['name']}, an Engel agent.",
        f"Purpose: {agent['purpose']}",
        f"Direction (v{agent.get('direction_version', 1)}): {agent['direction']}",
        f"Tools you may use: {', '.join(agent.get('tools') or []) or 'none'}",
        f"Skills assigned: {', '.join(agent.get('skills') or []) or 'none'}",
        f"Turn budget: {agent.get('max_turns')}",
    ]
    if agent.get("pending_tools"):
        lines.append(
            "Operator-gated tools not currently available: "
            + ", ".join(agent.get("pending_tools") or [])
        )
    if not agent.get("allow_actions"):
        lines.append(
            "You are READ-ONLY: report and propose, and do not change files, start "
            "processes, or take any outward action."
        )
    lines.append(
        "If the direction cannot be followed honestly, say so plainly and stop rather "
        "than inventing a result."
    )
    return "\n".join(lines)


def _print(payload: Any) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_new = sub.add_parser("create", help="author a new agent")
    p_new.add_argument("--name", required=True)
    p_new.add_argument("--purpose", required=True)
    p_new.add_argument("--direction", required=True)
    p_new.add_argument("--tools", default="", help="comma-separated, from the known set")
    p_new.add_argument("--max-turns", type=int, default=8)
    p_new.add_argument("--allow-actions", action="store_true")

    p_dir = sub.add_parser("direct", help="give an existing agent new direction")
    p_dir.add_argument("--agent", required=True)
    p_dir.add_argument("--direction", required=True)
    p_dir.add_argument("--reason", default="")

    p_st = sub.add_parser("status", help="set draft/active/retired")
    p_st.add_argument("--agent", required=True)
    p_st.add_argument("--to", required=True, choices=STATUSES)

    p_gr = sub.add_parser("grant-actions", help="human grant so the agent may act")
    p_gr.add_argument("--agent", required=True)
    p_gr.add_argument("--granted-by", required=True)
    p_gr.add_argument("--reason", required=True)

    p_rv = sub.add_parser("revoke-actions", help="withdraw an agent's action grant")
    p_rv.add_argument("--agent", required=True)
    p_rv.add_argument("--reason", default="")

    sub.add_parser("list", help="show the roster")
    p_brief = sub.add_parser("brief", help="print the run brief for an agent")
    p_brief.add_argument("--agent", required=True)

    args = parser.parse_args(argv)
    registry = load_registry()

    try:
        if args.cmd == "create":
            tools = [t for t in (args.tools or "").split(",") if t.strip()]
            agent = author_agent(
                args.name, args.purpose, args.direction,
                tools=[t.strip() for t in tools],
                allow_actions=args.allow_actions,
                max_turns=args.max_turns,
                registry=registry,
            )
            save_registry(registry)
            _print({"ok": True, "created": agent})
        elif args.cmd == "direct":
            agent = give_direction(registry, args.agent, args.direction, reason=args.reason)
            save_registry(registry)
            _print({"ok": True, "agent_id": agent["agent_id"],
                    "direction_version": agent["direction_version"],
                    "direction": agent["direction"]})
        elif args.cmd == "status":
            agent = set_status(registry, args.agent, args.to)
            save_registry(registry)
            _print({"ok": True, "agent_id": agent["agent_id"], "status": agent["status"]})
        elif args.cmd == "grant-actions":
            agent = grant_actions(registry, args.agent, granted_by=args.granted_by,
                                  reason=args.reason)
            save_registry(registry)
            _print({"ok": True, "agent_id": agent["agent_id"], "allow_actions": True})
        elif args.cmd == "revoke-actions":
            agent = revoke_actions(registry, args.agent, reason=args.reason)
            save_registry(registry)
            _print({"ok": True, "agent_id": agent["agent_id"], "allow_actions": False})
        elif args.cmd == "list":
            _print({
                "ok": True,
                "count": len(registry.get("agents", [])),
                "agents": [
                    {k: a.get(k) for k in
                     ("agent_id", "name", "status", "purpose", "direction_version",
                      "tools", "allow_actions")}
                    for a in registry.get("agents", [])
                ],
            })
        elif args.cmd == "brief":
            _print({"ok": True, "brief": agent_brief(find_agent(registry, args.agent))})
    except AgentAuthorError as exc:
        _print({"ok": False, "error": str(exc)})
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
